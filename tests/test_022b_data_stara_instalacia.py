# -*- coding: utf-8 -*-
"""Odinstalator 0.2 nesmie potichu zmazat historiu ZIP verzie (0.2.2).

0.2 sa instalovala instalackou (Dandurf.iss). Jej odinstalator sa pyta
"Ponechat nastavenia...?" a pri Nie zmaze %APPDATA%\\Zanshin - ten isty
priecinok pouziva aj Zanshin zo ZIP-u. Strazi sa:

  * `paths.stara_instalacia` najde kluc odinstalovania `<AppId>_is1` (HKCU,
    aj HKLM v oboch pohladoch), s presnym AppId z Dandurf.iss, a nikdy
    nespadne - chybajuci winreg, kluc ci pokazeny register = None,
  * ked bezi prave nainstalovana appka, nevaruje,
  * appka to povie RAZ (zapamata si to v nastaveniach), len v zabalenej
    verzii, a az po starte okna,
  * README (krok 0 v "A. Ready-made ZIP") aj KNOWN_ISSUES to hovoria.

Register sa nedotyka - vsetko cez falosny winreg.
"""
import re
import sys
import types

import pytest

import i18n
import paths
from _zdroj_appky import zdroj_metody, zdroj_suboru

KLUC = ("Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\"
        "{30295CDB-462B-4151-B225-582E82027A33}_is1")
INSTALOVANA = r"C:\Users\hrac\AppData\Local\Programs\Zanshin"


class _Kluc:
    def __init__(self, hodnoty):
        self.hodnoty = hodnoty

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _FalosnyWinreg:
    """Len to, co `paths.stara_instalacia` z winreg pouziva."""
    HKEY_CURRENT_USER = "HKCU"
    HKEY_LOCAL_MACHINE = "HKLM"
    KEY_READ = 0x20019
    KEY_WOW64_64KEY = 0x0100
    KEY_WOW64_32KEY = 0x0200

    def __init__(self, kluce=None, chyba=None):
        # {(koren, pohlad): {meno hodnoty: hodnota}}; pohlad 0 = HKCU
        self.kluce = kluce or {}
        self.chyba = chyba
        self.otvorene = []

    def OpenKey(self, koren, cesta, _rezervovane, pristup):
        self.otvorene.append((koren, cesta, pristup))
        if self.chyba is not None:
            raise self.chyba
        pohlad = pristup & (self.KEY_WOW64_64KEY | self.KEY_WOW64_32KEY)
        hodnoty = self.kluce.get((koren, pohlad))
        if hodnoty is None or cesta != KLUC:
            raise FileNotFoundError(2, "kluc nie je")
        return _Kluc(hodnoty)

    def QueryValueEx(self, kluc, meno):
        if meno not in kluc.hodnoty:
            raise FileNotFoundError(2, "hodnota nie je")
        return kluc.hodnoty[meno], 1


def _hodnoty(miesto=INSTALOVANA + "\\", verzia="0.2"):
    h = {"DisplayVersion": verzia}
    if miesto is not None:
        h["InstallLocation"] = miesto
    return h


ZIP_EXE = r"C:\Games\Zanshin\Zanshin.exe"


# --------------------------------------------------------------------------
# paths.stara_instalacia
# --------------------------------------------------------------------------

def test_app_id_sedi_s_instalackou():
    """Kluc odinstalovania je `<AppId>_is1`; v .iss je AppId so zdvojenou
    `{{` (escapovanie Inno Setup)."""
    iss = zdroj_suboru("Dandurf.iss")
    najdene = re.search(r"^AppId=\{(\{[0-9A-F-]+\})\s*$", iss, re.M)
    assert najdene, "AppId v Dandurf.iss"
    assert paths.INSTALLER_APP_ID == najdene.group(1)
    assert paths._UNINSTALL_KEY == KLUC


def test_najde_instalaciu_v_hkcu():
    reg = _FalosnyWinreg({("HKCU", 0): _hodnoty(verzia="0.2")})
    assert paths.stara_instalacia(reg, exe=ZIP_EXE) == {
        "location": INSTALOVANA + "\\", "version": "0.2"}


@pytest.mark.parametrize("pohlad", [0x0100, 0x0200])
def test_najde_aj_instalaciu_pre_vsetkych_v_hklm(pohlad):
    reg = _FalosnyWinreg({("HKLM", pohlad): _hodnoty(verzia="0.2.1")})
    assert paths.stara_instalacia(reg, exe=ZIP_EXE)["version"] == "0.2.1"


def test_bez_kluca_nic():
    reg = _FalosnyWinreg({})
    assert paths.stara_instalacia(reg, exe=ZIP_EXE) is None
    assert {k for k, _c, _p in reg.otvorene} == {"HKCU", "HKLM"}


def test_bezi_prave_nainstalovana_appka():
    reg = _FalosnyWinreg({("HKCU", 0): _hodnoty()})
    exe = INSTALOVANA + r"\Zanshin.exe"
    assert paths.stara_instalacia(reg, exe=exe) is None
    # velkost pismen v ceste Windows nerozlisuje
    assert paths.stara_instalacia(reg, exe=exe.upper()) is None


def test_podobny_priecinok_nie_je_ten_isty():
    """...\\Zanshin a ...\\Zanshin-0.2.2 su dva rozne priecinky."""
    reg = _FalosnyWinreg({("HKCU", 0): _hodnoty()})
    exe = INSTALOVANA + r"-0.2.2\Zanshin.exe"
    assert paths.stara_instalacia(reg, exe=exe) is not None


def test_bez_install_location_aj_tak_varuje():
    reg = _FalosnyWinreg({("HKCU", 0): _hodnoty(miesto=None, verzia=None)})
    assert paths.stara_instalacia(reg, exe=ZIP_EXE) == {"location": None,
                                                        "version": None}


@pytest.mark.parametrize("chyba", [PermissionError(5, "pristup odmietnuty"),
                                   ValueError("pokazeny register"),
                                   OSError("nieco ine")])
def test_pokazeny_register_nespadne(chyba):
    assert paths.stara_instalacia(_FalosnyWinreg(chyba=chyba), exe=ZIP_EXE) is None


def test_bez_winreg_nic(monkeypatch):
    """Mimo Windows (alebo bez winreg) sa nic nehlada a nic nespadne."""
    monkeypatch.setitem(sys.modules, "winreg", None)      # import zlyha
    assert paths.stara_instalacia(exe=ZIP_EXE) is None


# --------------------------------------------------------------------------
# upozornenie v appke
# --------------------------------------------------------------------------

def _appka(monkeypatch, najdene, frozen=True):
    import app as app_mod
    import app_data
    if frozen:
        monkeypatch.setattr(sys, "frozen", True, raising=False)
    else:
        monkeypatch.delattr(sys, "frozen", raising=False)
    hladane = []

    def _hladaj():
        hladane.append(True)
        if isinstance(najdene, Exception):
            raise najdene
        return najdene

    # `_upozorni_na_staru_instalaciu` byva v app_data a meno si importuje
    # z paths - podstrcit treba tam.
    monkeypatch.setattr(app_data, "stara_instalacia", _hladaj)
    zobrazene = []
    monkeypatch.setattr(app_data.messagebox, "showinfo",
                        lambda titul, text: zobrazene.append(text))
    planovane, denn, ulozene = [], [], []
    a = types.SimpleNamespace(
        old_installer_warned=False, log=denn.append,
        save_settings=lambda: ulozene.append(a.old_installer_warned),
        root=types.SimpleNamespace(after=lambda ms, fn: planovane.append((ms, fn))))
    spusti = lambda: app_mod.DandurfApp._upozorni_na_staru_instalaciu(a)  # noqa: E731
    return a, spusti, types.SimpleNamespace(
        hladane=hladane, zobrazene=zobrazene, planovane=planovane, denn=denn,
        ulozene=ulozene)


def test_upozorni_raz_az_po_starte_a_zapamata_si_to(monkeypatch):
    a, spusti, s = _appka(monkeypatch, {"location": INSTALOVANA, "version": "0.2"})
    spusti()
    assert s.zobrazene == [], "dialog az ked okno stoji"
    (ms, fn), = s.planovane
    assert ms > 0
    fn()
    assert len(s.zobrazene) == 1 and "0.2" in s.zobrazene[0]
    assert a.old_installer_warned is True and s.ulozene == [True]
    assert s.denn == s.zobrazene
    # dalsi start (flag z nastaveni) uz nic
    spusti()
    assert len(s.planovane) == 1 and len(s.hladane) == 1


def test_beh_zo_zdrojakov_register_necita(monkeypatch):
    _a, spusti, s = _appka(monkeypatch, {"location": INSTALOVANA, "version": "0.2"},
                           frozen=False)
    spusti()
    assert s.hladane == [] and s.planovane == []


def test_bez_starej_instalacie_ani_chyba_nic_neukaze(monkeypatch):
    for najdene in (None, RuntimeError("register")):
        a, spusti, s = _appka(monkeypatch, najdene)
        spusti()
        assert s.planovane == [] and s.denn == []
        assert a.old_installer_warned is False


def test_flag_prezije_prve_ulozenie_pri_starte():
    """`__init__` uklada nastavenia hned po postaveni okna - flag musi byt
    nacitany skor, inak by sa zapisal False a varovanie chodilo stale."""
    init = zdroj_metody("__init__")
    assert (init.index('self.old_installer_warned = bool(settings.get("old_installer_warned"))')
            < init.index("self._ready = True"))
    assert "'old_installer_warned'" in zdroj_metody("save_settings").replace('"', "'")
    nacitaj = zdroj_metody("load_settings")
    assert 'data["old_installer_warned"] = bool(loaded.get("old_installer_warned", False))' in nacitaj
    # pri prvom starte bezi sprievodca - povie sa to az pri dalsom
    assert "if not settings[\"first_run\"]:\n            self._upozorni_na_staru_instalaciu()" in init


def test_text_vo_vsetkych_jazykoch():
    for jazyk in i18n.LANGUAGES:
        assert "{version}" in i18n.STRINGS["data.old_installer"][jazyk], jazyk
    assert i18n.tr_lang("sk", "data.old_installer", version="0.2") == (
        "Máš ešte nainštalovanú verziu 0.2. Keď ju budeš odinštalovať, na otázku "
        "o dátach odpovedz Áno — inak zmaže aj históriu tejto verzie.")
    en = i18n.STRINGS["data.old_installer"]["en"]
    for jazyk in ("ja", "zh", "ru", "es", "de", "fr", "pt", "cs", "bg"):
        assert i18n.STRINGS["data.old_installer"][jazyk] != en, jazyk


# --------------------------------------------------------------------------
# dokumenty
# --------------------------------------------------------------------------

def _plain(meno):
    return " ".join(" ".join(r.lstrip(">") for r in zdroj_suboru(meno).splitlines()).split())


def test_readme_krok_nula_v_zip_navode():
    readme = zdroj_suboru("README.md")
    sekcia = readme[readme.index("### A. Ready-made ZIP"):readme.index("### B. Build it yourself")]
    plain = " ".join(sekcia.split())
    assert plain.index("0. **Had the 0.2 installer?**") < plain.index("1. On the GitHub page")
    assert "answer **Yes** to *Keep your settings…*" in plain
    assert "**No** deletes `%APPDATA%\\Zanshin`, which this version uses too." in plain


def test_known_issues_v_sekcii_022():
    k = zdroj_suboru("KNOWN_ISSUES.md")
    sekcia = " ".join(k[k.index("## What 0.2.2 changes"):k.index("## What 0.2.1 fixes")].split())
    assert "The 0.2 uninstaller can delete this version's data." in sekcia
    assert "**No** deletes that folder" in sekcia and "Answer **Yes**." in sekcia
    # otazka odinstalatora citovana presne podla Dandurf.iss
    otazka = re.search(r"^english\.KeepDataQuestion=(.+)$", zdroj_suboru("Dandurf.iss"), re.M)
    assert "*%s*" % otazka.group(1).strip() in sekcia
