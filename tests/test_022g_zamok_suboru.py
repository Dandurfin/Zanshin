# -*- coding: utf-8 -*-
"""Atomicky zapis prezije kratky zamok suboru vo Windows (0.2.2).

V logu skusobnej kopie:

    save_settings: zalohu nastaveni sa nepodarilo zapisat
    PermissionError: [WinError 5] Access is denied: '...json.bak.tmp' -> '...json.bak'

Cerstvo zapisany subor si na chvilu otvori Defender, indexovanie alebo
synchronizacia (bez FILE_SHARE_DELETE) a holy `os.replace` vtedy spadne.
Atomicke zapisy dat appky (.tmp -> ciel) preto idu cez `paths.nahrad_subor`:
pri docasnom zamku skusi znova po kratkych pauzach (spolu najviac 0.31 s -
`save_settings` bezi vo vlakne GUI), potom vyhodi POSLEDNU chybu ako predtym.
Pri `uprac_zdroj=True` po sebe neostavi .tmp; pokazeny subor odkladany bokom
sa nikdy nemaze.

Vsetko v tmp_path. Skutocny zamok (subor otvoreny cez open(), teda bez
FILE_SHARE_DELETE) len vo Windows.
"""
import ast
import errno
import json
import logging
import os
import sys
import threading
import time
import types

import pytest

import app_prefs
import audio_engine
import data_io
import hr_insights
import hr_stats
import paths

VO_WINDOWS = sys.platform == "win32"
len_windows = pytest.mark.skipif(not VO_WINDOWS,
                                 reason="zamok suboru je spravanie Windows")
KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Moduly, ktore zapisuju data hraca alebo cache cez .tmp + nahradu.
MODULY = ("app_prefs", "data_io", "hr_stats", "hr_insights", "audio_engine")


def _zamok(winerror=5):
    """Ta ista chyba, aku hodi Windows: errno EACCES + kod Windows."""
    return PermissionError(errno.EACCES, "Access is denied", None, winerror)


def _subor(cesta, obsah):
    with open(cesta, "w", encoding="utf-8") as fh:
        fh.write(obsah)


def _obsah(cesta):
    with open(cesta, encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(autouse=True)
def _ciste_zlyhane_ciele():
    """Pamat cielov, ktore nevydrzali ani posledny pokus, je globalna v
    module paths - kazdy test zacina bez nej."""
    paths._zlyhane_ciele.clear()
    yield
    paths._zlyhane_ciele.clear()


@pytest.fixture
def pauzy(monkeypatch):
    """Pauzy pomocnika sa len zapisu - test necaka. Nahradza sa `time` len
    v module paths, globalny `time.sleep` ostava (ine vlakna ho potrebuju)."""
    zoznam = []
    monkeypatch.setattr(paths, "time", types.SimpleNamespace(sleep=zoznam.append))
    return zoznam


def _replace_padne(monkeypatch, kolko_krat, chyba=_zamok, kedy=lambda src, dst: True):
    """os.replace, ktory pri `kedy(src, dst)` `kolko_krat` padne, potom
    nahradi naozaj. Vracia zoznam volani. `os` je jeden modul - nahradu vidi
    aj `paths.nahrad_subor`."""
    skutocny = os.replace
    volania = []
    zostava = {"n": kolko_krat}

    def _replace(src, dst):
        volania.append((src, dst))
        if kedy(src, dst) and zostava["n"] > 0:
            zostava["n"] -= 1
            raise chyba()
        return skutocny(src, dst)

    monkeypatch.setattr(paths.os, "replace", _replace)
    return volania


# --------------------------------------------------------------------------
# pomocnik paths.nahrad_subor
# --------------------------------------------------------------------------

def test_pauzy_rastu_a_spolu_su_kratke():
    p = paths.NAHRADA_PAUZY_S
    assert len(p) >= 3
    assert all(a < b for a, b in zip(p, p[1:])), "pauzy maju rast"
    assert 0 < sum(p) < 0.5, "save_settings bezi vo vlakne GUI"


def test_skusi_znova_a_podari_sa(tmp_path, monkeypatch, pauzy, caplog):
    ciel, tmp = str(tmp_path / "hr_sessions.json"), str(tmp_path / "hr_sessions.json.tmp")
    _subor(ciel, "stary")
    _subor(tmp, "novy")
    volania = _replace_padne(monkeypatch, 2)
    with caplog.at_level(logging.WARNING, logger="zanshin.paths"):
        paths.nahrad_subor(tmp, ciel, uprac_zdroj=True)
    assert volania == [(tmp, ciel)] * 3
    assert pauzy == list(paths.NAHRADA_PAUZY_S[:2])
    assert _obsah(ciel) == "novy" and not os.path.exists(tmp)
    # stopa v app.log - len meno suboru, cesta nesie meno uctu
    riadky = [r.getMessage() for r in caplog.records if r.name == "zanshin.paths"]
    assert len(riadky) == 1 and "3. pokus" in riadky[0]
    assert "hr_sessions.json" in riadky[0] and str(tmp_path) not in riadky[0]


def test_bez_zamku_ziadna_pauza_ani_log(tmp_path, pauzy, caplog):
    ciel, tmp = str(tmp_path / "a.json"), str(tmp_path / "a.json.tmp")
    _subor(tmp, "novy")
    with caplog.at_level(logging.WARNING, logger="zanshin.paths"):
        paths.nahrad_subor(tmp, ciel)
    assert pauzy == [] and _obsah(ciel) == "novy"
    assert not [r for r in caplog.records if r.name == "zanshin.paths"]


def test_po_limite_vyhodi_poslednu_chybu(tmp_path, monkeypatch, pauzy, caplog):
    ciel, tmp = str(tmp_path / "a.json"), str(tmp_path / "a.json.tmp")
    _subor(ciel, "stary")
    _subor(tmp, "novy")
    chyby = []

    def _vzdy(src, dst):
        chyby.append(_zamok(32 if len(chyby) % 2 else 5))
        raise chyby[-1]

    monkeypatch.setattr(paths.os, "replace", _vzdy)
    with caplog.at_level(logging.WARNING, logger="zanshin.paths"):
        with pytest.raises(PermissionError) as vyhodena:
            paths.nahrad_subor(tmp, ciel)
    assert vyhodena.value is chyby[-1], "volajuci dostane POSLEDNU chybu"
    assert len(chyby) == len(paths.NAHRADA_PAUZY_S) + 1
    assert pauzy == list(paths.NAHRADA_PAUZY_S)
    assert sum(pauzy) < 0.5
    # bez uprac_zdroj ostava zdroj aj ciel tak, ako boli
    assert _obsah(tmp) == "novy" and _obsah(ciel) == "stary"
    riadky = [r.getMessage() for r in caplog.records if r.name == "zanshin.paths"]
    assert len(riadky) == 1 and "nepodarilo" in riadky[0]
    assert str(tmp_path) not in riadky[0]


def test_po_limite_uprace_vlastny_tmp(tmp_path, monkeypatch, pauzy):
    ciel, tmp = str(tmp_path / "a.json"), str(tmp_path / "a.json.tmp")
    _subor(ciel, "stary")
    _subor(tmp, "novy")
    _replace_padne(monkeypatch, 99)
    with pytest.raises(PermissionError):
        paths.nahrad_subor(tmp, ciel, uprac_zdroj=True)
    assert not os.path.exists(tmp)
    assert _obsah(ciel) == "stary"


_NEOPAKOVAT = [
    pytest.param(lambda: FileNotFoundError(errno.ENOENT, "nie je"), id="chyba-subor"),
    pytest.param(lambda: OSError(errno.ENOSPC, "disk je plny"), id="plny-disk"),
    pytest.param(lambda: OSError("disk je plny"), id="oserror-bez-kodu"),
    pytest.param(lambda: PermissionError(errno.EPERM, "zakazane"), id="eperm"),
    # WinError 19 = chranene proti zapisu: tiez EACCES, ale nie docasne
    pytest.param(lambda: PermissionError(errno.EACCES, "chranene", None, 19),
                 id="winerror-19", marks=len_windows),
]


@pytest.mark.parametrize("chyba", _NEOPAKOVAT)
@pytest.mark.parametrize("uprac", [False, True])
def test_ina_chyba_sa_neopakuje(tmp_path, monkeypatch, pauzy, chyba, uprac):
    ciel, tmp = str(tmp_path / "a.json"), str(tmp_path / "a.json.tmp")
    _subor(tmp, "novy")
    volania = _replace_padne(monkeypatch, 99, chyba=chyba)
    with pytest.raises(OSError) as vyhodena:
        paths.nahrad_subor(tmp, ciel, uprac_zdroj=uprac)
    assert type(vyhodena.value) is type(chyba())
    assert len(volania) == 1 and pauzy == []
    assert os.path.exists(tmp) is not uprac


@pytest.mark.parametrize("winerror", [5, 32, 33])
def test_docasne_kody_windows_sa_opakuju(tmp_path, monkeypatch, pauzy, winerror):
    ciel, tmp = str(tmp_path / "a.json"), str(tmp_path / "a.json.tmp")
    _subor(tmp, "novy")
    _replace_padne(monkeypatch, 1, chyba=lambda: _zamok(winerror))
    paths.nahrad_subor(tmp, ciel)
    assert pauzy == [paths.NAHRADA_PAUZY_S[0]] and _obsah(ciel) == "novy"


# --------------------------------------------------------------------------
# ciel, ktory nevydrzal ani posledny pokus: kym pada, uz sa necaka
# --------------------------------------------------------------------------

@pytest.fixture
def hodiny(monkeypatch):
    """Umely cas pre `NAHRADA_ODDYCH_S` (paths._hodiny)."""
    stav = {"t": 1000.0}
    monkeypatch.setattr(paths, "_hodiny", lambda: stav["t"])
    return stav


def test_po_vycerpani_dalsi_zapis_necaka(tmp_path, monkeypatch, pauzy, hodiny):
    """Trvaly zamok (subor len na citanie, otvoreny v inom programe): prvy
    zapis caka 0.31 s, dalsie hned padnu - tahanie slidera nezasekne okno."""
    ciel, tmp = str(tmp_path / "dandurf_settings.json"), str(tmp_path / "a.tmp")
    _subor(ciel, "stary")
    volania = _replace_padne(monkeypatch, 999)
    for i in range(5):
        _subor(tmp, "novy%d" % i)
        hodiny["t"] += 0.05
        with pytest.raises(PermissionError) as chyba:
            paths.nahrad_subor(tmp, ciel, uprac_zdroj=True)
        assert chyba.value.winerror == 5, "volajuci dostane tu istu chybu"
        assert not os.path.exists(tmp)
    assert pauzy == list(paths.NAHRADA_PAUZY_S), "cakal len prvy zapis"
    assert len(volania) == len(paths.NAHRADA_PAUZY_S) + 1 + 4
    assert _obsah(ciel) == "stary"


def test_po_uspechu_zase_plne_opakovanie(tmp_path, monkeypatch, pauzy, hodiny):
    ciel, tmp = str(tmp_path / "a.json"), str(tmp_path / "a.json.tmp")
    _subor(tmp, "1")
    skutocny = os.replace
    _replace_padne(monkeypatch, 99)
    with pytest.raises(PermissionError):
        paths.nahrad_subor(tmp, ciel)
    del pauzy[:]
    monkeypatch.setattr(paths.os, "replace", skutocny)   # zamok povolil
    paths.nahrad_subor(tmp, ciel)            # este v oddychu: jeden pokus, uspech
    assert pauzy == [] and _obsah(ciel) == "1"
    _subor(tmp, "2")
    _replace_padne(monkeypatch, 1)           # novy kratky zamok
    paths.nahrad_subor(tmp, ciel)
    assert pauzy == [paths.NAHRADA_PAUZY_S[0]], "po uspechu sa zase caka"
    assert _obsah(ciel) == "2"


def test_oddych_vyprsi_ked_sa_nezapisuje(tmp_path, monkeypatch, pauzy, hodiny):
    """Kazde dalsie zlyhanie oddych predlzi; az ked do ciela chvilu nikto
    nepise (dalsia relacia o hodinu), zapis zase caka na kratky zamok."""
    ciel, tmp = str(tmp_path / "hr_sessions.json"), str(tmp_path / "x.tmp")
    _subor(tmp, "novy")
    _replace_padne(monkeypatch, 999)
    oddych = paths.NAHRADA_ODDYCH_S
    for posun in (0, oddych * 0.8, oddych * 0.8):
        hodiny["t"] += posun
        with pytest.raises(PermissionError):
            paths.nahrad_subor(tmp, ciel)
    assert len(pauzy) == len(paths.NAHRADA_PAUZY_S), "zlyhania oddych predlzuju"
    hodiny["t"] += oddych + 0.01
    with pytest.raises(PermissionError):
        paths.nahrad_subor(tmp, ciel)
    assert len(pauzy) == 2 * len(paths.NAHRADA_PAUZY_S), "po oddychu zase caka"


def test_oddych_len_pre_ten_isty_ciel(tmp_path, monkeypatch, pauzy, hodiny):
    """.bak drzany natrvalo nesmie vziat opakovanie samotnym nastaveniam."""
    bak = str(tmp_path / "dandurf_settings.json.bak")
    nast = str(tmp_path / "dandurf_settings.json")
    tmp = str(tmp_path / "t.tmp")
    _subor(tmp, "x")
    _replace_padne(monkeypatch, 99, kedy=lambda src, dst: dst == bak)
    with pytest.raises(PermissionError):
        paths.nahrad_subor(tmp, bak)
    del pauzy[:]
    _replace_padne(monkeypatch, 1, kedy=lambda src, dst: dst == nast)
    paths.nahrad_subor(tmp, nast)
    assert pauzy == [paths.NAHRADA_PAUZY_S[0]] and _obsah(nast) == "x"


def test_ina_chyba_oddych_nezaklada(tmp_path, monkeypatch, pauzy, hodiny):
    ciel, tmp = str(tmp_path / "a.json"), str(tmp_path / "a.json.tmp")
    _subor(tmp, "x")
    _replace_padne(monkeypatch, 1, chyba=lambda: OSError(errno.ENOSPC, "plny"))
    with pytest.raises(OSError):
        paths.nahrad_subor(tmp, ciel)
    assert paths._zlyhane_ciele == {}
    _replace_padne(monkeypatch, 1)
    paths.nahrad_subor(tmp, ciel)
    assert pauzy == [paths.NAHRADA_PAUZY_S[0]]


def test_pamat_zlyhanych_cielov_ostava_mala(tmp_path, monkeypatch, pauzy, hodiny):
    _replace_padne(monkeypatch, 10 ** 6)
    for i in range(30):
        tmp = str(tmp_path / ("%d.tmp" % i))
        _subor(tmp, "x")
        hodiny["t"] += paths.NAHRADA_ODDYCH_S       # kazdy uz po oddychu
        with pytest.raises(PermissionError):
            paths.nahrad_subor(tmp, str(tmp_path / ("%d.json" % i)))
    assert len(paths._zlyhane_ciele) == 1


# --------------------------------------------------------------------------
# skutocny zamok vo Windows
# --------------------------------------------------------------------------

def _drz_a_pusti(cesta, po_s):
    """Otvori subor (Python open() nezdiela mazanie - presne ako antivirus
    pocas kontroly) a po `po_s` ho z ineho vlakna zavrie."""
    fh = open(cesta, "rb")
    casovac = threading.Timer(po_s, fh.close)
    return fh, casovac


@len_windows
@pytest.mark.parametrize("drzany,kod", [("ciel", 5), ("zdroj", 32)])
def test_skutocny_zamok_povoli_a_nahrada_sa_podari(tmp_path, caplog, drzany, kod):
    ciel = str(tmp_path / "dandurf_settings.json.bak")
    tmp = ciel + ".tmp"
    _subor(ciel, "stary")
    _subor(tmp, "novy")
    fh, casovac = _drz_a_pusti(ciel if drzany == "ciel" else tmp, 0.05)
    try:
        # poistka: zamok naozaj zastavi holy os.replace (inak test nic nedokaze)
        with pytest.raises(PermissionError) as holy:
            os.replace(tmp, ciel)
        assert holy.value.winerror == kod
        casovac.start()
        with caplog.at_level(logging.WARNING, logger="zanshin.paths"):
            paths.nahrad_subor(tmp, ciel, uprac_zdroj=True)
    finally:
        casovac.cancel()
        fh.close()
    assert _obsah(ciel) == "novy" and not os.path.exists(tmp)
    riadky = [r.getMessage() for r in caplog.records if r.name == "zanshin.paths"]
    assert riadky and "pokus" in riadky[0], "nahrada naozaj cakala na zamok"


@len_windows
def test_skutocny_zamok_zaloha_nastaveni_prezije(tmp_path):
    """Presne pripad z logu: .bak drzi iny proces, kym sa zalohuje."""
    cesta = str(tmp_path / "dandurf_settings.json")
    _subor(cesta, json.dumps({"volume": 80}))
    _subor(cesta + ".bak", json.dumps({"volume": 37}))
    fh, casovac = _drz_a_pusti(cesta + ".bak", 0.05)
    try:
        casovac.start()
        assert app_prefs.zaloha_nastaveni(cesta) is True
    finally:
        casovac.cancel()
        fh.close()
    assert json.loads(_obsah(cesta + ".bak")) == {"volume": 80}
    assert not os.path.exists(cesta + ".bak.tmp")


@len_windows
def test_skutocny_trvaly_zamok_zaloha_vyhodi_a_neostavi_tmp(tmp_path):
    cesta = str(tmp_path / "dandurf_settings.json")
    _subor(cesta, json.dumps({"volume": 80}))
    _subor(cesta + ".bak", json.dumps({"volume": 37}))
    with open(cesta + ".bak", "rb"):
        with pytest.raises(PermissionError) as chyba:
            app_prefs.zaloha_nastaveni(cesta)
    assert chyba.value.winerror == 5
    assert json.loads(_obsah(cesta + ".bak")) == {"volume": 37}
    assert not os.path.exists(cesta + ".bak.tmp"), "ziadny zabudnuty .bak.tmp"


def _appka_nastaveni(dennik):
    """Minimum pre skutocne `PrefsMixin.save_settings` (bez okna)."""
    return types.SimpleNamespace(
        _ready=True, slots=[object()], _sync_active_profile_slots=lambda: None,
        profiles=[{"name": "P", "slots": []}], active_profile_name="P",
        saved_voice_id=None, rate_value=0, volume_value=50, balance_value=0,
        engine_pref="sapi", edge_voice_id="", theme_key="zen", lang="sk",
        start_minimized=False, auto_profile_enabled=False, overlay_configs={},
        hr_ip="", hr_port=5000, hr_monitoring_enabled=False,
        zanshin_graduated=False, zanshin_graduated_at=None, snooze_hotkey="",
        background_opacity=0.5, monitor_target=None, hud_config={},
        dashboard_stats=[], breath_inhale_s=4.0, breath_exhale_s=6.0,
        log=dennik.append)


@len_windows
def test_skutocny_trvaly_zamok_save_settings_nezasekava_okno(tmp_path, monkeypatch):
    """`save_settings` bezi vo vlakne GUI pri kazdom posune slidera. Ked
    nastavenia aj .bak drzi iny program natrvalo, caka len prve ulozenie
    (0.62 s - dva subory); dalsie hned padnu ako pred 0.2.2. Bez toho bolo
    10 ulozeni = 6 s zaseknuteho okna (namerane)."""
    cesta = str(tmp_path / "dandurf_settings.json")
    _subor(cesta, json.dumps({"volume": 37}))
    _subor(cesta + ".bak", json.dumps({"volume": 30}))
    monkeypatch.setattr(app_prefs, "SETTINGS_PATH", cesta)
    spanky = []

    def _spi(s):
        spanky.append(s)
        time.sleep(s)

    monkeypatch.setattr(paths, "time", types.SimpleNamespace(sleep=_spi))
    dennik = []
    a = _appka_nastaveni(dennik)
    with open(cesta, "rb"), open(cesta + ".bak", "rb"):
        for i in range(6):
            a.volume_value = 50 + i
            app_prefs.PrefsMixin.save_settings(a)
            assert len(spanky) == 2 * len(paths.NAHRADA_PAUZY_S), i
    assert len(dennik) == 6, "kazde zlyhanie hlasi dennik ako predtym"
    assert json.loads(_obsah(cesta)) == {"volume": 37}
    assert json.loads(_obsah(cesta + ".bak")) == {"volume": 30}
    assert not [m for m in os.listdir(str(tmp_path)) if m.endswith(".tmp")]
    # zamok povolil: hned dalsie ulozenie prejde (oddych neblokuje uspech)
    a.volume_value = 99
    app_prefs.PrefsMixin.save_settings(a)
    assert json.loads(_obsah(cesta))["volume"] == 99
    assert json.loads(_obsah(cesta + ".bak")) == {"volume": 37}
    assert paths._zlyhane_ciele == {}


@len_windows
def test_skutocny_zamok_pokazenej_historie_kopia_bez_prepisu(tmp_path):
    """Pokazenu historiu drzi iny program cely cas: presun bokom nejde, kopia
    ano, prepis nie - relacia skonci ako neulozena (ide do pending)."""
    cesta = str(tmp_path / "hr_sessions.json")
    _subor(cesta, "[{pokazene vecery")
    with open(cesta, "rb"):
        assert hr_stats.save_session(cesta, _relacia(1000)) is False
    assert _obsah(cesta) == "[{pokazene vecery"
    (odlozene,) = [m for m in os.listdir(str(tmp_path)) if ".corrupt-" in m]
    assert _obsah(os.path.join(str(tmp_path), odlozene)) == "[{pokazene vecery"
    assert not os.path.exists(cesta + ".tmp")


# --------------------------------------------------------------------------
# volajuci
# --------------------------------------------------------------------------

def test_zaloha_nastaveni_po_limite_uprace_bak_tmp(tmp_path, monkeypatch, pauzy):
    cesta = str(tmp_path / "dandurf_settings.json")
    _subor(cesta, json.dumps({"volume": 80}))
    _subor(cesta + ".bak", json.dumps({"volume": 37}))
    _replace_padne(monkeypatch, 99)
    with pytest.raises(PermissionError):
        app_prefs.zaloha_nastaveni(cesta)
    assert not os.path.exists(cesta + ".bak.tmp")
    assert json.loads(_obsah(cesta + ".bak")) == {"volume": 37}
    assert pauzy == list(paths.NAHRADA_PAUZY_S)


def test_zaloha_nastaveni_kratky_zamok_prezije(tmp_path, monkeypatch, pauzy):
    cesta = str(tmp_path / "dandurf_settings.json")
    _subor(cesta, json.dumps({"volume": 80}))
    _replace_padne(monkeypatch, 2)
    assert app_prefs.zaloha_nastaveni(cesta) is True
    assert json.loads(_obsah(cesta + ".bak")) == {"volume": 80}


def test_pokazene_nastavenia_sa_odlozia_aj_obnovia_cez_kratky_zamok(
        tmp_path, monkeypatch, pauzy):
    cesta = str(tmp_path / "dandurf_settings.json")
    _subor(cesta, '{"volume": 4')                       # pokazeny
    _subor(cesta + ".bak", json.dumps({"volume": 37}))
    # kazda nahrada (odlozenie bokom aj vratenie zalohy) raz narazi na zamok
    videne = set()

    def _raz(src, dst):
        if (src, dst) in videne:
            return False
        videne.add((src, dst))
        return True

    _replace_padne(monkeypatch, 99, kedy=_raz)
    data, obnova = app_prefs.nacitaj_nastavenia(cesta, teraz=0)
    assert data == {"volume": 37}
    assert obnova["zo_zalohy"] is True
    odlozene = os.path.join(str(tmp_path), obnova["odlozene"])
    # odlozeny PRESUNOM (nie len kopiou) a zaloha vratena na miesto
    assert _obsah(odlozene) == '{"volume": 4'
    assert json.loads(_obsah(cesta)) == {"volume": 37}
    assert not os.path.exists(cesta + ".tmp")
    assert len(pauzy) == 2


def test_data_io_zapis_zoznam(tmp_path, monkeypatch, pauzy):
    cesta = str(tmp_path / "hr_sessions.json")
    _replace_padne(monkeypatch, 2)
    data_io.zapis_zoznam(cesta, [{"started": 1}])
    assert json.loads(_obsah(cesta)) == [{"started": 1}]
    _replace_padne(monkeypatch, 99)
    with pytest.raises(PermissionError):
        data_io.zapis_zoznam(cesta, [{"started": 2}])
    assert json.loads(_obsah(cesta)) == [{"started": 1}]
    assert not os.path.exists(cesta + ".tmp")


def test_data_io_export_neostavi_tmp_vedla_exportu(tmp_path, monkeypatch, pauzy):
    cesta = str(tmp_path / "zanshin-export.json")
    _replace_padne(monkeypatch, 99)
    with pytest.raises(PermissionError):
        data_io.write_bundle(cesta, data_io.build_bundle([], []))
    assert os.listdir(str(tmp_path)) == []


def test_hr_stats_kontrolny_bod(tmp_path, monkeypatch, pauzy):
    sessions = str(tmp_path / "hr_sessions.json")
    bod = hr_stats.cesta_rozpracovanej(sessions)
    _replace_padne(monkeypatch, 2)
    assert hr_stats.zapis_rozpracovanu(sessions, {"started": 1.0}) is True
    assert json.loads(_obsah(bod)) == {"started": 1.0}
    _replace_padne(monkeypatch, 99)
    assert hr_stats.zapis_rozpracovanu(sessions, {"started": 2.0}) is False
    assert json.loads(_obsah(bod)) == {"started": 1.0}
    assert not os.path.exists(bod + ".tmp")


def _relacia(started):
    return {"started": float(started), "duration_s": 600.0, "samples": 100,
            "avg_bpm": 70.0}


def test_hr_stats_pokazena_historia_sa_odlozi_aj_cez_kratky_zamok(
        tmp_path, monkeypatch, pauzy):
    """Odlozenie bokom skusa znova tiez - inak by zamok, ktory povoli medzi
    odlozenim a zapisom, nechal pokazenu historiu prepisat bez kopie."""
    cesta = str(tmp_path / "hr_sessions.json")
    _subor(cesta, "[{pokazene")
    _replace_padne(monkeypatch, 1, kedy=lambda src, dst: ".corrupt-" in dst)
    assert hr_stats.save_session(cesta, _relacia(1000)) is True
    odlozene = [m for m in os.listdir(str(tmp_path)) if ".corrupt-" in m]
    assert len(odlozene) == 1
    assert _obsah(os.path.join(str(tmp_path), odlozene[0])) == "[{pokazene"
    assert [s["started"] for s in json.loads(_obsah(cesta))] == [1000.0]
    assert pauzy == [paths.NAHRADA_PAUZY_S[0]]


def test_hr_stats_ulozenie_relacie_po_limite(tmp_path, monkeypatch, pauzy):
    cesta = str(tmp_path / "hr_sessions.json")
    assert hr_stats.save_session(cesta, _relacia(1000)) is True
    _replace_padne(monkeypatch, 99)
    assert hr_stats.save_session(cesta, _relacia(2000)) is False
    assert [s["started"] for s in json.loads(_obsah(cesta))] == [1000.0]
    assert not os.path.exists(cesta + ".tmp")


# Pokazeny subor a zamok, ktory nevydrzi odlozenie bokom (6 pokusov), ale
# povoli az pocas pokusov zapisu za nim. Holy os.replace vtedy padol pri
# zapise na ten isty zamok a subor ostal; s opakovanim by ho zapis prepisal
# bez kopie - preto aspon kopia, a bez nej ziadny prepis.
_ODLOZENIE = len(paths.NAHRADA_PAUZY_S) + 1


def _zamok_na(monkeypatch, cesta, pokusov):
    return _replace_padne(monkeypatch, pokusov, kedy=lambda src, dst: cesta in (src, dst))


def _kopia_padne(monkeypatch):
    def _copy2(src, dst, **kw):
        raise PermissionError(errno.EACCES, "Access is denied", None, 32)
    monkeypatch.setattr(hr_stats.shutil, "copy2", _copy2)


def _odlozene_kopie(tmp_path):
    return [m for m in os.listdir(str(tmp_path)) if ".corrupt-" in m]


def test_hr_stats_zamok_az_do_zapisu_necha_kopiu_historie(tmp_path, monkeypatch, pauzy):
    cesta = str(tmp_path / "hr_sessions.json")
    _subor(cesta, "[{pokazene vecery")
    _zamok_na(monkeypatch, cesta, _ODLOZENIE + 2)
    assert hr_stats.save_session(cesta, _relacia(1000)) is True
    (odlozene,) = _odlozene_kopie(tmp_path)
    assert _obsah(os.path.join(str(tmp_path), odlozene)) == "[{pokazene vecery"
    assert [s["started"] for s in json.loads(_obsah(cesta))] == [1000.0]


def test_hr_stats_bez_kopie_pokazenu_historiu_neprepise(tmp_path, monkeypatch, pauzy):
    cesta = str(tmp_path / "hr_sessions.json")
    _subor(cesta, "[{pokazene vecery")
    _zamok_na(monkeypatch, cesta, _ODLOZENIE)    # zapis by uz presiel
    _kopia_padne(monkeypatch)
    spravy = []
    assert hr_stats.save_session(cesta, _relacia(1000), log=spravy.append) is False
    assert _obsah(cesta) == "[{pokazene vecery", "jedina kopia ostala"
    assert _odlozene_kopie(tmp_path) == []
    assert not os.path.exists(cesta + ".tmp")
    # volajuci (`_close_hr_session`) to berie ako neulozenu relaciu
    (chyba,) = [s for s in spravy if s.startswith("HR: session log failed:")]
    assert "Access is denied" in chyba


def test_cakajuce_zamok_az_do_zapisu_necha_kopiu(tmp_path, monkeypatch, pauzy):
    sessions = str(tmp_path / "hr_sessions.json")
    cesta = hr_stats.cesta_cakajucej(sessions)
    _subor(cesta, "[{cele vecery")
    _zamok_na(monkeypatch, cesta, _ODLOZENIE + 2)
    assert hr_stats.zapis_cakajucu(sessions, _relacia(2000)) is True
    (odlozene,) = _odlozene_kopie(tmp_path)
    assert _obsah(os.path.join(str(tmp_path), odlozene)) == "[{cele vecery"
    assert [s["started"] for s in hr_stats.nacitaj_cakajuce(sessions)] == [2000.0]


def test_cakajuce_bez_kopie_neprepise_ani_nezmaze(tmp_path, monkeypatch, pauzy):
    sessions = str(tmp_path / "hr_sessions.json")
    cesta = hr_stats.cesta_cakajucej(sessions)
    _subor(cesta, "[{cele vecery")
    _zamok_na(monkeypatch, cesta, _ODLOZENIE)    # zapis by uz presiel
    _kopia_padne(monkeypatch)
    assert hr_stats.zapis_cakajucu(sessions, _relacia(2000)) is False
    assert _obsah(cesta) == "[{cele vecery"
    # start (`obnov_cakajuce`): necitatelny subor bez kopie ostava, nic nevyhodi
    paths._zlyhane_ciele.clear()
    _zamok_na(monkeypatch, cesta, _ODLOZENIE)
    assert hr_stats.obnov_cakajuce(sessions) == []
    assert _obsah(cesta) == "[{cele vecery"
    assert _odlozene_kopie(tmp_path) == []


def test_hr_insights_ulozenie(tmp_path, monkeypatch, pauzy):
    cesta = str(tmp_path / "hr_insights.json")
    _replace_padne(monkeypatch, 2)
    assert hr_insights.save_insights(cesta, [{"id": "steady"}]) is True
    assert json.loads(_obsah(cesta))["insights"] == [{"id": "steady"}]


# --------------------------------------------------------------------------
# zdrojak: ziadny holy os.replace, upratuje sa len vlastny .tmp
# --------------------------------------------------------------------------

def _strom(modul):
    with open(os.path.join(KOREN, modul + ".py"), encoding="utf-8-sig") as fh:
        return ast.parse(fh.read())


def _volania(strom, meno):
    for uzol in ast.walk(strom):
        if not isinstance(uzol, ast.Call):
            continue
        f = uzol.func
        if (isinstance(f, ast.Name) and f.id == meno) or (
                isinstance(f, ast.Attribute) and f.attr == meno):
            yield uzol


def test_moduly_dat_nevolaju_holy_os_replace():
    for modul in MODULY:
        holy = [u.lineno for u in _volania(_strom(modul), "replace")
                if isinstance(u.func, ast.Attribute)
                and isinstance(u.func.value, ast.Name) and u.func.value.id == "os"]
        assert not holy, (modul, holy)
        assert list(_volania(_strom(modul), "nahrad_subor")), modul


def test_moduly_beru_pomocnika_z_paths():
    """Jeden pomocnik pre vsetkych (monkeypatch podla modulu, kde zije)."""
    for modul in (app_prefs, data_io, hr_stats, hr_insights, audio_engine):
        assert modul.nahrad_subor is paths.nahrad_subor, modul.__name__


def test_uprac_zdroj_len_pri_vlastnom_tmp():
    """`uprac_zdroj=True` zmaze zdroj pri neuspechu - smie byt len pri .tmp
    volajuceho, nikdy pri pokazenom subore, ktory sa odklada bokom."""
    pocet = 0
    for modul in MODULY:
        for u in _volania(_strom(modul), "nahrad_subor"):
            pocet += 1
            zdroj = u.args[0]
            uprac = [k for k in u.keywords if k.arg == "uprac_zdroj"]
            je_tmp = isinstance(zdroj, ast.Name) and "tmp" in zdroj.id
            if uprac:
                assert je_tmp, (modul, u.lineno)
            if not je_tmp:
                assert not uprac, (modul, u.lineno)
    # poistka, ze prechod nieco nasiel: 4 app_prefs + 4 data_io + 7 hr_stats
    # (oba pokazene subory bokom cez jeden `_odloz_pokazeny`) + 1 hr_insights
    # + 2 audio_engine
    assert pocet >= 18


def test_save_settings_zapisuje_cez_pomocnika():
    from _zdroj_appky import zdroj_metody
    zdroj = zdroj_metody("save_settings")
    assert "zaloha_nastaveni(SETTINGS_PATH)" in zdroj
    assert "nahrad_subor(tmp_path, SETTINGS_PATH, uprac_zdroj=True)" in zdroj
