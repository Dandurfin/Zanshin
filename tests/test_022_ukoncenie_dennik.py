# -*- coding: utf-8 -*-
"""Ukoncenie z listy nespadne na zniceny dennik (0.2.2).

Pad z app.log buildu (Ukoncit z ikony v liste):

    _quit -> stop_listening -> _close_hr_session -> log
    TclError: invalid command name "...!panel2.!ctkframe.!ctkframe2.!ctktextbox.!text"

Pricina: `_close_hr_session` pri zatvarani caka na dotaznik
(`_ask_session_context` -> `root.wait_window`). V tej vnorenej slucke Tk sa
vybavilo aj druhe "Ukoncit" z listy - druhy `_quit` prebehol cely az po
`root.destroy()`, dotaznik zanikol s oknom a prvy `_quit` sa vratil do
zniceneho okna. Cesta widgetu v chybe je z PRVEJ stavby okna (`.!ctkframe`),
takze nejde o zastaralu referenciu po prestavbe - dennik znicil `root.destroy()`.

Strazi sa:
  * `log` na znicenom denniku nespadne a riadok ide do app.log BEZ adresy PC,
    zivy dennik do suboru nepise nic (test_ip_skryta),
  * `_quit` prejde vsetky kroky, aj ked niektory spadne - a relacia sa
    uklada prva,
  * druhe "Ukoncit" pocas dotaznika len zavrie dotaznik a ukoncenie dokonci
    prvy `_quit` (skutocne Tk, skutocne metody appky na atrape).
"""
import os
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import netinfo  # noqa: E402
from i18n import tr  # noqa: E402

IP = "192.168.1.20"


def _D():
    import app as app_mod
    return app_mod.DandurfApp


class _Zapisovac:
    """Nahrada `app_log` - nic nejde do skutocneho logs/app.log."""

    def __init__(self):
        self.zaznamy = []

    def _zapis(self, uroven, msg, *args, **_kw):
        self.zaznamy.append((uroven, msg % args if args else msg))

    def info(self, msg, *args, **kw):
        self._zapis("info", msg, *args, **kw)

    def warning(self, msg, *args, **kw):
        self._zapis("warning", msg, *args, **kw)

    def error(self, msg, *args, **kw):
        self._zapis("error", msg, *args, **kw)

    def exception(self, msg, *args, **kw):
        self._zapis("exception", msg, *args, **kw)


@pytest.fixture
def zapisovac(monkeypatch):
    import app as app_mod
    import app_data
    z = _Zapisovac()
    monkeypatch.setattr(app_mod, "app_log", z)
    monkeypatch.setattr(app_data, "app_log", z)
    return z


def _ctk_root():
    import customtkinter as ctk
    try:
        root = ctk.CTk()
    except Exception as exc:
        pytest.skip(f"Tk sa neda vytvorit: {exc}")
    root.withdraw()
    return root


# --------------------------------------------------------------------------
# maska adries vo volnom texte (pre nahradny riadok v app.log)
# --------------------------------------------------------------------------

def test_maska_skryje_ipv4_aj_ipv6_v_texte():
    out = netinfo.mask_ips_in_text(f"Pocuvam na {IP}:4455 (UDP aj TCP)")
    assert IP not in out
    assert netinfo.MASKA_IPV4 in out and ":4455" in out
    # Adresa na konci vety - bodka za nou nesmie masku vypnut.
    veta = netinfo.mask_ips_in_text(f"Tep chodi z {IP}. Dalsia veta")
    assert IP not in veta and f"{netinfo.MASKA_IPV4}. Dalsia" in veta
    out6 = netinfo.mask_ips_in_text("adresa fe80::1c2b:3aff:fe4d:5e6f a 2001:db8::7")
    assert "fe80" not in out6 and "2001" not in out6 and "db8" not in out6
    zmiesana = netinfo.mask_ips_in_text(f"::ffff:{IP}")
    assert "192" not in zmiesana and "168" not in zmiesana


def test_maska_necha_cas_verziu_a_nuly():
    """0.0.0.0 nie je adresa PC (viz `mask_ip`); cas a verzia adresou nie su."""
    text = "[12:34:56] Zanshin 0.2.2 pocuva na 0.0.0.0, relacia 1:02:03, cislo 1.2.3.4.5."
    assert netinfo.mask_ips_in_text(text) == text
    assert netinfo.mask_ips_in_text("") == ""
    assert netinfo.mask_ips_in_text(None) is None


# --------------------------------------------------------------------------
# `log` na znicenom denniku
# --------------------------------------------------------------------------

def _atrapa_pre_log(log_text):
    D = _D()

    class _Appka:
        log = D.log
        _dennik_bez_okna = D._dennik_bez_okna

    a = _Appka()
    a.log_text = log_text
    a._last_log_line = ""
    return a


@pytest.mark.skipif(sys.platform != "win32", reason="Tk okno appky je vec Windows")
@pytest.mark.parametrize("co_zanika", ["root", "dennik"])
def test_log_na_znicenom_denniku_nespadne_a_ide_do_suboru_bez_ip(zapisovac, co_zanika):
    import tkinter as tk
    import customtkinter as ctk
    root = _ctk_root()
    try:
        dennik = ctk.CTkTextbox(root, height=110)
        dennik.pack()
        if co_zanika == "root":
            root.destroy()             # presne to, co spravil vnoreny `_quit`
        else:
            dennik.destroy()
        # Predpoklad: toto je ta chyba z app.log - bez opravy by ju `log` pustil dalej.
        with pytest.raises(tk.TclError):
            dennik.configure(state="normal")

        a = _atrapa_pre_log(dennik)
        a.log(f"Relacia ulozena, prijem na {IP}")          # nesmie vyhodit

        assert a._last_log_line.endswith(f"prijem na {IP}")
        riadky = [m for u, m in zapisovac.zaznamy if u == "info"]
        assert len(riadky) == 1, zapisovac.zaznamy
        assert "Relacia ulozena" in riadky[0]
        assert IP not in riadky[0], "adresa PC nesmie do app.log (PRIVACY.md)"
        assert netinfo.MASKA_IPV4 in riadky[0]
    finally:
        try:
            root.destroy()
        except Exception:
            pass


@pytest.mark.skipif(sys.platform != "win32", reason="Tk okno appky je vec Windows")
def test_log_so_zivym_dennikom_pise_len_do_okna(zapisovac):
    import customtkinter as ctk
    root = _ctk_root()
    try:
        dennik = ctk.CTkTextbox(root, height=110)
        dennik.pack()
        dennik.configure(state="disabled")
        a = _atrapa_pre_log(dennik)
        a.log(f"prijem na {IP}")
        assert f"prijem na {IP}" in dennik.get("1.0", "end")
        assert str(dennik.cget("state")) == "disabled"
        assert zapisovac.zaznamy == [], "zivy dennik do app.log nepise (test_ip_skryta)"
    finally:
        root.destroy()


# --------------------------------------------------------------------------
# `_quit` prejde vsetky kroky
# --------------------------------------------------------------------------

KROKY = ["hud", "vizualy", "ovladac", "hotkey", "senzor tepu", "game_watcher",
         "hlas", "lista", "destroy"]


def _atrapa_pre_quit(poradie, padne=None):
    """Atrapa so skutocnym `_quit` a `stop_listening`. `padne` = meno kroku,
    ktory vyhodi vynimku."""
    D = _D()

    def f(meno):
        def _krok(*_a, **_k):
            poradie.append(meno)
            if meno == padne:
                raise RuntimeError(f"{meno} zlyhal")
        return _krok

    class _Appka:
        _quit = D._quit
        stop_listening = D.stop_listening

    a = _Appka()
    a.listening = True
    a._hr_session_open = True

    def _close_hr_session():
        if not a._hr_session_open:
            return
        a._hr_session_open = False
        poradie.append("ulozenie")
        if padne == "ulozenie":
            # Ako v app.log: relacia sa ulozila, potom spadol zapis do dennika.
            import tkinter as tk
            raise tk.TclError('invalid command name ".!ctktextbox.!text"')

    a._close_hr_session = _close_hr_session
    a.gamepad = types.SimpleNamespace(stop=f("ovladac"))
    a.activity = types.SimpleNamespace(set_gamepad_watched=lambda _v: None)
    a._suspend_cue_trigger = lambda _d: None
    a._apply_listening_visuals = lambda: None
    a.log = lambda _m: None
    a.update_tray_icon = lambda: None
    a._dopriprav_hlasky_po_hre = lambda: None
    a.hud = types.SimpleNamespace(stop=f("hud"))
    a.overlay_manager = types.SimpleNamespace(stop_all=f("vizualy"))
    a.stop_snooze_hotkey = f("hotkey")
    a.heart_rate_monitor = types.SimpleNamespace(stop=f("senzor tepu"))
    a.game_watcher = types.SimpleNamespace(stop=f("game_watcher"))
    a.worker = types.SimpleNamespace(stop=f("hlas"))
    a.tray_icon = types.SimpleNamespace(stop=f("lista"))
    a.root = types.SimpleNamespace(destroy=f("destroy"),
                                   after_cancel=lambda _j: poradie.append("after_cancel"))
    a._activity_job = "after#1"
    return a


def test_quit_dokonci_ukoncenie_aj_ked_stop_listening_spadne(zapisovac):
    """Presne pad z app.log: relacia ulozena, potom vynimka zo `stop_listening`."""
    poradie = []
    a = _atrapa_pre_quit(poradie, padne="ulozenie")
    a._quit()                                           # nesmie vyhodit

    assert poradie[0] == "ovladac"          # `stop_listening` zacina ovladacom
    assert poradie[1] == "ulozenie", "relacia sa uklada pred vsetkym ostatnym"
    assert poradie.count("ulozenie") == 1
    assert poradie[2:] == ["after_cancel"] + KROKY, poradie
    assert a._activity_job is None
    chyby = [m for u, m in zapisovac.zaznamy if u == "exception"]
    assert len(chyby) == 1 and "stop_listening" in chyby[0]
    assert a._quit_bezi is False and a._zatvara_sa is True


@pytest.mark.parametrize("padne", ["hud", "vizualy", "hotkey", "senzor tepu",
                                   "game_watcher", "hlas", "destroy"])
def test_quit_pokracuje_za_krokom_ktory_spadne(zapisovac, padne):
    poradie = []
    a = _atrapa_pre_quit(poradie, padne=padne)
    a._quit()
    assert poradie[:2] == ["ovladac", "ulozenie"]
    assert poradie[2:] == ["after_cancel"] + KROKY, (padne, poradie)
    chyby = [m for u, m in zapisovac.zaznamy if u == "exception"]
    assert len(chyby) == 1 and padne in chyby[0]


def test_quit_bez_chyb_nic_neloguje_a_poradie_ostava(zapisovac):
    poradie = []
    a = _atrapa_pre_quit(poradie)
    a._quit()
    assert poradie == ["ovladac", "ulozenie", "after_cancel"] + KROKY
    assert zapisovac.zaznamy == []


# --------------------------------------------------------------------------
# druhe "Ukoncit" pocas dotaznika - skutocne Tk a skutocne metody appky
# --------------------------------------------------------------------------

@pytest.mark.skipif(sys.platform != "win32", reason="Tk okno appky je vec Windows")
def test_druhe_ukoncit_pocas_dotaznika_nerozbije_prve(zapisovac, monkeypatch, tmp_path):
    import tkinter as tk
    import customtkinter as ctk
    import app_data

    D = _D()
    poradie = []
    chyby_tk = []
    ulozene = []

    root = _ctk_root()
    root.report_callback_exception = lambda typ, hodnota, tb: chyby_tk.append(
        f"{typ.__name__}: {hodnota}")
    dennik = ctk.CTkTextbox(root, height=110)
    dennik.pack()
    dennik.configure(state="disabled")

    class _Dotaznik:
        """Nahrada SessionEndDialog: pocas cakania prveho `_quit` pride druhe
        "Ukoncit" z listy (tray -> quit_app -> ui_call)."""

        def __init__(self, app, summary, cues=0, silent=0):
            self.top = tk.Toplevel(app.root)
            self.top.withdraw()
            poradie.append("dotaznik")
            app.root.after(30, app.quit_app)

        def close(self):
            poradie.append("dotaznik zavrety")
            self.top.destroy()

    monkeypatch.setattr(app_data, "SessionEndDialog", _Dotaznik)
    monkeypatch.setattr(app_data.hr_stats, "save_session",
                        lambda cesta, summary, log=None: ulozene.append(summary) or True)
    monkeypatch.setattr(app_data.data_io, "append_events", lambda *a, **k: None)

    class _Appka:
        _quit = D._quit
        quit_app = D.quit_app
        ui_call = D.ui_call
        stop_listening = D.stop_listening
        _close_hr_session = D._close_hr_session
        _suhrn_relacie = D._suhrn_relacie
        _ask_session_context = D._ask_session_context
        log = D.log
        _dennik_bez_okna = D._dennik_bez_okna

    a = _Appka()
    a.root = root
    a.log_text = dennik
    a._last_log_line = ""
    a.listening = True
    a._hr_session_open = True
    a._cue_log = []
    a.hr_sessions_path = str(tmp_path / "hr_sessions.json")
    a.hr_events_path = str(tmp_path / "hr_events.jsonl")
    a.hr_stats = types.SimpleNamespace(
        session_start=0.0, cues=[], long_baseline=None,
        summary=lambda: {"avg_bpm": 80, "max_bpm": 120, "peak_stress": 40,
                         "duration_s": 2100.0})
    a.cue_trigger = types.SimpleNamespace(
        close_session=lambda: None, najdlhsi_nad_s=0.0, behov_nad=0,
        zrusenych_prepadom=0, zrusenych_vypadkom=0,
        params={"stress_hold_s": 90.0, "stress_threshold": 55},
        pause_episodes=0, zadrzane={})
    a._hud_tick_t = None
    a._hud_active_s = 0.0
    a._hud_vis_s = 0.0
    a._hud_is_visible = lambda: False
    a._set_enso_armed = lambda _v: None
    a._save_measure_windows = lambda: None
    a._maybe_graduate = lambda _s: None
    a._refresh_history_page = lambda: None
    a.run_hr_analysis = lambda: None
    a.log_threadsafe = lambda _m: None
    a._ui_pending = []
    a.gamepad = types.SimpleNamespace(stop=lambda: None)
    a.activity = types.SimpleNamespace(set_gamepad_watched=lambda _v: None)
    a._suspend_cue_trigger = lambda _d: None
    a._apply_listening_visuals = lambda: None
    a.update_tray_icon = lambda: None
    a._dopriprav_hlasky_po_hre = lambda: None

    obsah_dennika = []

    def krok(meno):
        def _k(*_a, **_kw):
            poradie.append(meno)
            if meno == "hlas":
                # posledny krok pred `root.destroy()` - dennik este zije
                obsah_dennika.append(dennik.get("1.0", "end"))
        return _k

    a.hud = types.SimpleNamespace(stop=krok("hud"))
    a.overlay_manager = types.SimpleNamespace(stop_all=krok("vizualy"))
    a.stop_snooze_hotkey = krok("hotkey")
    a.heart_rate_monitor = types.SimpleNamespace(stop=krok("senzor tepu"))
    a.game_watcher = None
    a.worker = types.SimpleNamespace(stop=krok("hlas"))
    a.tray_icon = types.SimpleNamespace(stop=krok("lista"))

    povodny_destroy = root.destroy

    def _destroy():
        poradie.append("destroy")
        povodny_destroy()

    root.destroy = _destroy

    def _poistka():
        chyby_tk.append("ukoncenie nedobehlo")
        povodny_destroy()

    root.after(0, a.quit_app)                 # prve "Ukoncit" z listy
    root.after(8000, _poistka)
    try:
        # Zakladna slucka Tk: `CTk.mainloop` pred prvym zobrazenim vola `update()`
        # a to by prve "Ukoncit" vybavilo este pred sluckou - skutocna appka uz v nej je.
        tk.Tk.mainloop(root)
    finally:
        try:
            povodny_destroy()
        except Exception:
            pass

    assert chyby_tk == [], chyby_tk
    assert len(ulozene) == 1, "relacia sa ulozi prave raz"
    assert poradie == ["dotaznik", "dotaznik zavrety", "hud", "vizualy", "hotkey",
                       "senzor tepu", "hlas", "lista", "destroy"], poradie
    # Prvy `_quit` pokracoval v ZIVOM okne: riadok o ulozeni aj o vypnuti
    # pocuvania su v denniku, nic neslo nahradnou cestou do suboru.
    text = obsah_dennika[0]
    assert tr("log.hr_session_saved", avg=80, max=120, peak=40) in text
    assert tr("log.listening_off") in text
    assert zapisovac.zaznamy == [], zapisovac.zaznamy
    assert a._dotaznik_pri_zatvarani is None
    assert a._quit_bezi is False
