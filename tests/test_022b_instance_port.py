# -*- coding: utf-8 -*-
"""Chyba portu ci vazby nie je rozhodnutie hraca (0.2.2, audit UX).

Do 0.2.2 appka po obsadenom porte (po troch pokusoch, ~24 s) aj po chybe
vazby vypla `hr_monitoring_enabled` a ULOZILA to do nastaveni. Druha kopia
appky tak prvej vypla prijem tepu natrvalo - ten isty subor nastaveni. Teraz:

  * busy aj error vypnu senzor len V PAMATI (prepinac ukaze vypnute, lebo tep
    naozaj nechodi), do suboru ide dalej zapnute - nech ulozenie spusti
    ktorekolvek miesto appky, aj ukoncenie,
  * dalsi start to skusi znova; zmena IP/portu (oprava, ktoru radi dennik)
    to skusi hned,
  * vlastny klik hraca na prepinac plati ako doteraz,
  * adresa, ktoru PC nema (WinError 10049), skusi 0.0.0.0 RAZ - to uz robi
    `heart_rate._bind` a ulozenu IP neprepisuje,
  * `log.hr_port_busy` menuje castu pricinu (OBS) a opravu (iny port).
"""
import errno
import json
import os
import re
import socket
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import heart_rate  # noqa: E402
import i18n  # noqa: E402
from _zdroj_appky import zdroj_metody  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _D():
    import app as app_mod
    return app_mod.DandurfApp


def _nic(*_a, **_k):
    return None


class _Var:
    def __init__(self, hodnota):
        self.hodnota = hodnota

    def get(self):
        return self.hodnota

    def set(self, hodnota):
        self.hodnota = hodnota


def _atrapa(**navyse):
    """To, co `_apply_hr_status` vo vetvach busy/error cita a vola."""
    denn, ulozenia, naplanovane = [], [], []
    a = types.SimpleNamespace(
        _hr_generation=1, _hr_state="connecting", _hr_last_bpm=None,
        _hr_lost=False, _hr_lost_od=None, _hr_over_since=None,
        _hr_client_linked=False, _hr_bind_retries=0,
        hr_monitoring_enabled=True, hr_enabled_var=_Var(True),
        HR_BIND_RETRIES=3, HR_BIND_RETRY_MS=8000,
        log=denn.append, denn=denn, ulozenia=ulozenia,
        save_settings=lambda: ulozenia.append(a.hr_monitoring_enabled),
        _close_hr_session=_nic, _retry_hr_bind=_nic,
        root=types.SimpleNamespace(after=lambda ms, fn: naplanovane.append(ms) or "job"),
        naplanovane=naplanovane,
        refresh_hr_status_label=_nic, _refresh_dnes_stats=_nic,
        _refresh_kamae_state_text=_nic,
    )
    a.__dict__.update(navyse)
    return a


def _stav(a, kind, payload):
    _D()._apply_hr_status(a, (kind, payload), a._hr_generation)


# --------------------------------------------------------------------------
# busy a error: vypnute len v pamati
# --------------------------------------------------------------------------

def test_obsadeny_port_pocas_pokusov_nic_nevypina_ani_neuklada():
    a = _atrapa()
    for n in range(1, 4):
        a._hr_generation = 1
        _stav(a, "busy", 4455)
        assert a._hr_state == "busy" and a.hr_monitoring_enabled is True
        assert a.denn[-1] == i18n.tr("log.hr_port_busy_retry", port=4455, n=n, z=3)
    assert a.naplanovane == [8000] * 3, "opakovanie ostava"
    assert a.ulozenia == []


def test_po_vzdani_vypnute_len_v_pamati_a_nic_sa_neulozi():
    a = _atrapa(_hr_bind_retries=3)
    _stav(a, "busy", 4455)
    assert a._hr_state == "busy_gave_up"
    assert a.hr_monitoring_enabled is False, "tep nechodi - prepinac to ukaze"
    assert a.hr_enabled_var.get() is False
    assert a._hr_vypnute_chybou is True, "save_settings musi vediet, ze to nebol hrac"
    assert a.ulozenia == [], "vzdanie sa nesmie ulozit vypnutie"
    # atrapa nema `_nazov_vhre` -> meno stranky z Hry (0.2.2 davka 4b)
    assert a.denn[-1] == i18n.tr("log.hr_port_busy", port=4455,
                                 page=i18n.tr("nav.vhre_short"))
    assert a.naplanovane == [], "po vzdani sa uz nic neplanuje"


@pytest.mark.parametrize("chyba", [
    "[WinError 10013] An attempt was made to access a socket in a way forbidden",
    "[WinError 10049] The requested address is not valid in its context",
])
def test_chyba_vazby_vypnute_len_v_pamati(chyba):
    a = _atrapa()
    _stav(a, "error", chyba)
    assert a.hr_monitoring_enabled is False and a.hr_enabled_var.get() is False
    assert a._hr_vypnute_chybou is True
    assert a.ulozenia == []
    assert a.denn == [i18n.tr("log.hr_socket_error", err=chyba)]
    assert a._hr_generation == 0, "spravy mrtveho vlakna sa zahodia ako doteraz"


def test_bez_prepinaca_v_okne_to_nespadne():
    """Stranka s prepinacom este nemusi byt postavena (hr_enabled_var None)."""
    for kind, payload, navyse in (("busy", 4455, {"_hr_bind_retries": 3}),
                                  ("error", "x", {})):
        a = _atrapa(hr_enabled_var=None, **navyse)
        _stav(a, kind, payload)
        assert a.hr_monitoring_enabled is False and a._hr_vypnute_chybou is True


def test_novy_beh_zrusi_cakajuci_pokus_predosleho():
    """Iny port ci vypnutie a zapnutie POCAS pokusov po obsadenom porte: stary
    pokus (`after`) by o par sekund restartoval novy prijem - hodinky by sa
    odpojili a relacia otvorila nanovo. Novy beh ho zrusi."""
    zrusene, otvorene = [], []
    a = _atrapa(
        _hr_retry_job="stary-pokus", listening=True, hr_ip="0.0.0.0", hr_port=4456,
        root=types.SimpleNamespace(after_cancel=zrusene.append),
        heart_rate_monitor=types.SimpleNamespace(start=lambda ip, port: 7),
        _hr_ip_display=lambda: "0.0.0.0", _schedule_no_client_check=_nic)
    a._open_hr_session = lambda meria=True: otvorene.append(a._hr_retry_job)
    _D().start_heart_rate_monitor(a)
    assert zrusene == ["stary-pokus"]
    assert otvorene == [None] and a._hr_retry_job is None
    assert a._hr_generation == 7
    # bez cakajuceho pokusu sa nic nerusi (`after_cancel(None)` Tk odmietne)
    zrusene.clear()
    _D().start_heart_rate_monitor(a)
    assert zrusene == []


def test_pokus_o_vazbu_uz_nehovori_druha_kopia():
    """Druha kopia sa od 0.2.2 k portu nedostane (main.py) - veta pri
    pokusoch nema hraca posielat hladat ju. Pricinu povie `log.hr_port_busy`."""
    for jazyk in i18n.LANGUAGES:
        text = i18n.STRINGS["log.hr_port_busy_retry"][jazyk]
        assert set(re.findall(r"\{(\w+)\}", text)) == {"port", "n", "z"}, jazyk
    assert i18n.tr_lang("sk", "log.hr_port_busy_retry", port=4455, n=1, z=3) == (
        "Port 4455 drží iný program — skúšam znova (1/3).")
    assert "copy" not in i18n.tr_lang("en", "log.hr_port_busy_retry",
                                      port=4455, n=1, z=3)


def test_apply_hr_status_nastavenia_neuklada_vobec():
    """Ziadna vetva stavu spojenia nie je volba hraca."""
    assert "save_settings" not in zdroj_metody("_apply_hr_status")
    assert "save_settings" not in zdroj_metody("_retry_hr_bind")


# --------------------------------------------------------------------------
# kazde dalsie ulozenie zapise zapnute; dalsi start skusi znova
# --------------------------------------------------------------------------

@pytest.fixture
def appka(tmp_path, monkeypatch):
    """Atrapa so skutocnym `load_settings` / `save_settings` nad docasnym
    suborom (rovnako ako tests/test_zanshin_easter_egg.py)."""
    import app_prefs
    cesta = str(tmp_path / "dandurf_settings.json")
    monkeypatch.setattr(app_prefs, "SETTINGS_PATH", cesta)
    D = _D()

    def nova(**zmeny):
        d = D.load_settings(types.SimpleNamespace())
        d.update(zmeny)
        a = _atrapa(
            _ready=True, slots=list(d["profiles"][0]["slots"]),
            _sync_active_profile_slots=_nic,
            profiles=d["profiles"], active_profile_name=d["active_profile"],
            saved_voice_id=d["voice_id"], rate_value=d["rate"],
            volume_value=d["volume"], balance_value=d["balance"],
            engine_pref=d["engine_pref"], edge_voice_id=d["edge_voice"],
            theme_key=d["theme"], world=d["world"], cue_style=d["cue_style"],
            lang=d["lang"], start_minimized=d["start_minimized"],
            auto_profile_enabled=d["auto_profile_enabled"],
            overlay_configs=d["overlay_configs"], tour_seen=d["tour_seen"],
            tour_step=d["tour_step"], game_lang=d["game_lang"],
            hr_ip=d["hr_ip"], hr_port=d["hr_port"],
            hr_monitoring_enabled=d["hr_monitoring_enabled"],
            hr_enabled_var=_Var(d["hr_monitoring_enabled"]),
            zanshin_graduated=d["zanshin_graduated"],
            zanshin_graduated_at=d["zanshin_graduated_at"],
            snooze_hotkey=d["snooze_hotkey"],
            background_opacity=d["background_opacity"],
            monitor_target=d["monitor_target"], hud_config=d["hud_config"],
            dashboard_stats=d["dashboard_stats"],
            breath_inhale_s=d["breath_inhale_s"],
            breath_exhale_s=d["breath_exhale_s"])
        a.save_settings = lambda: D.save_settings(a)
        return a

    def ulozene():
        with open(cesta, encoding="utf-8") as fh:
            return json.load(fh)["hr_monitoring_enabled"]

    nova.ulozene = ulozene
    return nova


@pytest.mark.parametrize("kind, payload", [("busy", 4455), ("error", "zle")])
def test_neskorsie_ulozenie_zapise_zapnute(appka, kind, payload):
    a = appka(hr_monitoring_enabled=True)
    a.save_settings()
    assert appka.ulozene() is True
    a._hr_bind_retries = 3
    _stav(a, kind, payload)
    assert a.hr_monitoring_enabled is False
    # hocijake dalsie ulozenie (posuvnik, jazyk, ukoncenie appky)
    a.save_settings()
    assert appka.ulozene() is True, "chyba portu sa nesmie dostat do nastaveni"
    # dalsi start: senzor je zapnuty a skusi to znova
    druha = appka()
    assert druha.hr_monitoring_enabled is True


def test_klik_hraca_na_prepinac_plati(appka):
    a = appka(hr_monitoring_enabled=True)
    a._hr_bind_retries = 3
    _stav(a, "busy", 4455)
    spustene, zastavene = [], []
    a.start_heart_rate_monitor = lambda: spustene.append(1)
    a.stop_heart_rate_monitor = lambda: zastavene.append(1)
    # hrac prepinac zapne -> skusi sa znova a ulozi sa zapnute
    a.hr_enabled_var.set(True)
    _D().on_hr_toggle(a)
    assert spustene == [1] and a._hr_vypnute_chybou is False
    assert appka.ulozene() is True
    # hrac ho vypne -> to uz je jeho volba a uklada sa
    a.hr_enabled_var.set(False)
    _D().on_hr_toggle(a)
    assert zastavene == [1] and appka.ulozene() is False


def test_hracom_vypnuty_senzor_ostava_vypnuty(appka):
    a = appka(hr_monitoring_enabled=False)
    a.save_settings()
    assert appka.ulozene() is False


# --------------------------------------------------------------------------
# zmena portu po vzdani to skusi hned (to radi log.hr_port_busy)
# --------------------------------------------------------------------------

def _konfig(**navyse):
    spustene = []
    a = _atrapa(
        hr_ip="0.0.0.0", hr_port=4455, hr_critical_bpm=150,
        hr_ip_var=_Var("0.0.0.0"), hr_port_var=_Var("4455"),
        hr_stats=types.SimpleNamespace(critical_bpm=150),
        hud=types.SimpleNamespace(configure=_nic),
        start_heart_rate_monitor=lambda: spustene.append(a.hr_port),
        spustene=spustene)
    a.__dict__.update(navyse)
    return a


def test_zmena_portu_po_chybe_skusi_znova():
    a = _konfig(hr_monitoring_enabled=False, _hr_vypnute_chybou=True,
                hr_enabled_var=_Var(False))
    a.hr_port_var.set("4456")
    _D().on_hr_config_change(a)
    assert a.spustene == [4456]
    assert a.hr_monitoring_enabled is True and a.hr_enabled_var.get() is True
    assert a._hr_vypnute_chybou is False


def test_zmena_portu_hracom_vypnuty_senzor_nezapne():
    a = _konfig(hr_monitoring_enabled=False, hr_enabled_var=_Var(False))
    a.hr_port_var.set("4456")
    _D().on_hr_config_change(a)
    assert a.spustene == [] and a.hr_monitoring_enabled is False


def test_bez_zmeny_cisla_sa_nic_nespusta():
    a = _konfig(hr_monitoring_enabled=False, _hr_vypnute_chybou=True,
                hr_enabled_var=_Var(False))
    _D().on_hr_config_change(a)
    assert a.spustene == [] and a._hr_vypnute_chybou is True


# --------------------------------------------------------------------------
# WinError 10049: 0.0.0.0 raz, ulozena IP ostava
# --------------------------------------------------------------------------

def _monitor(chyby):
    """HeartRateMonitor so `_bind_to`, ktory pre adresy z `chyby` hodi chybu."""
    mon = heart_rate.HeartRateMonitor(_nic, _nic)
    volania = []

    def _bind_to(kind, host, port):
        volania.append(host)
        if host in chyby:
            raise chyby[host]
        return "socket"

    mon._bind_to = _bind_to
    return mon, volania


def _nema_adresu():
    if sys.platform.startswith("win"):
        return OSError(0, "The requested address is not valid in its context",
                       None, 10049)
    return OSError(errno.EADDRNOTAVAIL, "Cannot assign requested address")


def test_adresa_ktoru_pc_nema_skusi_vsetky_siete_raz():
    mon, volania = _monitor({"192.168.1.20": _nema_adresu()})
    assert mon._bind(socket.SOCK_STREAM, "192.168.1.20", 4455) == ("socket", True)
    assert volania == ["192.168.1.20", ""], "zaloha na 0.0.0.0 prave raz"


def test_zaloha_ktora_tiez_zlyha_sa_neopakuje():
    """0.0.0.0 obsadene -> chyba ide von ako "busy", ziadny treti pokus."""
    mon, volania = _monitor({"192.168.1.20": _nema_adresu(),
                             "": OSError(errno.EADDRINUSE, "obsadene")})
    with pytest.raises(OSError) as chyba:
        mon._bind(socket.SOCK_STREAM, "192.168.1.20", 4455)
    assert heart_rate._err_no(chyba.value) in heart_rate._PORT_BUSY_ERRNOS
    assert volania == ["192.168.1.20", ""]


@pytest.mark.parametrize("host", ["0.0.0.0", "", "  "])
def test_vsetky_siete_ziadnu_zalohu_nepotrebuju(host):
    mon, volania = _monitor({host.strip(): _nema_adresu()})
    with pytest.raises(OSError):
        mon._bind(socket.SOCK_STREAM, host, 4455)
    assert volania == [host.strip()], "ziadny druhy pokus"


def test_serve_hlasi_zalohu_raz_za_beh():
    import inspect
    src = inspect.getsource(heart_rate.HeartRateMonitor._serve)
    assert src.count('"bound_any"') == 1


def test_appka_po_zalohe_ip_neprepise_ani_neulozi():
    a = _atrapa(hr_ip="192.168.1.20", show_ip=False)
    _stav(a, "bound_any", "192.168.1.20")
    assert a.hr_ip == "192.168.1.20", "ulozena IP ostava"
    assert a.ulozenia == [] and a.hr_monitoring_enabled is True
    assert len(a.denn) == 1
    assert "0.0.0.0" in a.denn[0] and "192.168.1.20" not in a.denn[0]


# --------------------------------------------------------------------------
# texty
# --------------------------------------------------------------------------

def test_obsadeny_port_menuje_obs_a_opravu():
    # meno stranky dosadza appka podla sveta (`{page}`, 0.2.2 davka 4b)
    sk = i18n.tr_lang("sk", "log.hr_port_busy", port=4455,
                      page=i18n.tr_lang("sk", "nav.vhre_short"))
    assert sk == ("Port 4455 už používa iný program — často OBS so zapnutým "
                  "WebSocket serverom alebo druhá kópia Zanshinu. Na stránke "
                  "„V hre“ zmeň port (napr. na 4456) a rovnaké číslo zadaj v "
                  "appke na telefóne.")
    for jazyk in i18n.LANGUAGES:
        text = i18n.STRINGS["log.hr_port_busy"][jazyk]
        assert set(re.findall(r"\{(\w+)\}", text)) == {"port", "page"}, jazyk
        assert "OBS" in text and "4456" in text, jazyk


def test_dokumenty_hovoria_to_iste_co_kod():
    def plain(meno):
        with open(os.path.join(ROOT, meno), encoding="utf-8-sig") as fh:
            return " ".join(fh.read().split())
    privacy = plain("PRIVACY.md")
    assert "the app also switches it off if it can't open the TCP port" not in privacy
    assert "your setting stays on" in privacy
    known = plain("CHANGELOG.md")       # historia verzii od davky 4
    zaciatok = known.index("## What 0.2.2 changes")
    sekcia = known[zaciatok:known.index("## What 0.2.1 fixes")]
    assert "Starting Zanshin a second time could switch heart rate off for good" in sekcia
    assert "the next start tries again" in sekcia
