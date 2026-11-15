# -*- coding: utf-8 -*-
"""0.2's uninstaller must not silently delete the ZIP version's history (0.3).

0.2 was installed with an installer (Dandurf.iss). Its uninstaller asks
"Ponechat nastavenia...?" (Keep settings...?) and on "Nie" (No) deletes
%APPDATA%\\Zanshin - the same folder that Zanshin from the ZIP uses.
Guarded:

  * `paths.stara_instalacia` finds the uninstall key `<AppId>_is1` (HKCU,
    and HKLM in both views), with the exact AppId from Dandurf.iss, and
    never crashes - a missing winreg, key or a broken registry = None,
  * when it is the installed app itself that is running, it does not warn,
  * the app says it ONCE (it remembers it in the settings), only in the
    packaged version, and only after the window has started,
  * the README (step 0 in "A. Ready-made ZIP") and KNOWN_ISSUES say it too.

The registry is not touched - everything goes through a fake winreg.
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
    """Only what `paths.stara_instalacia` uses from winreg."""
    HKEY_CURRENT_USER = "HKCU"
    HKEY_LOCAL_MACHINE = "HKLM"
    KEY_READ = 0x20019
    KEY_WOW64_64KEY = 0x0100
    KEY_WOW64_32KEY = 0x0200

    def __init__(self, kluce=None, chyba=None):
        # {(root, view): {value name: value}}; view 0 = HKCU
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
    """The uninstall key is `<AppId>_is1`; in the .iss the AppId has a
    doubled `{{` (Inno Setup escaping)."""
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
    # Windows does not distinguish letter case in a path
    assert paths.stara_instalacia(reg, exe=exe.upper()) is None


def test_podobny_priecinok_nie_je_ten_isty():
    """...\\Zanshin and ...\\Zanshin-0.3 are two different folders."""
    reg = _FalosnyWinreg({("HKCU", 0): _hodnoty()})
    exe = INSTALOVANA + r"-0.3\Zanshin.exe"
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
    """Off Windows (or without winreg) nothing is searched or crashes."""
    monkeypatch.setitem(sys.modules, "winreg", None)      # the import fails
    assert paths.stara_instalacia(exe=ZIP_EXE) is None


# --------------------------------------------------------------------------
# the notice in the app
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

    # `_upozorni_na_staru_instalaciu` lives in app_data and imports the name
    # from paths - it has to be injected there.
    monkeypatch.setattr(app_data, "stara_instalacia", _hladaj)
    zobrazene = []
    # 0.3 batch 4: a notice in the app window (`ui_kit.notify`), not a system
    # messagebox - app_data no longer imports it
    import ui_kit
    monkeypatch.setattr(ui_kit, "notify",
                        lambda okno, pal, titul, text, **kw: zobrazene.append(text))
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
    # the next start (flag from the settings) does nothing more
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
    """`__init__` saves the settings right after building the window - the
    flag has to be loaded earlier, otherwise False would be written and
    the warning would keep coming."""
    init = zdroj_metody("__init__")
    assert (init.index('self.old_installer_warned = bool(settings.get("old_installer_warned"))')
            < init.index("self._ready = True"))
    assert "'old_installer_warned'" in zdroj_metody("save_settings").replace('"', "'")
    nacitaj = zdroj_metody("load_settings")
    assert 'data["old_installer_warned"] = bool(loaded.get("old_installer_warned", False))' in nacitaj
    # on the first start the tour runs - it is said only at the next one
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
# documents
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
    # Since 0.3 (batch 4) the version history is in CHANGELOG.md.
    k = zdroj_suboru("CHANGELOG.md")
    sekcia = " ".join(k[k.index("## What 0.3 changes"):k.index("## What 0.2.1 fixes")].split())
    assert "The 0.2 uninstaller can delete this version's data." in sekcia
    assert "**No** deletes that folder" in sekcia and "Answer **Yes**." in sekcia
    # the uninstaller's question quoted exactly as in Dandurf.iss
    otazka = re.search(r"^english\.KeepDataQuestion=(.+)$", zdroj_suboru("Dandurf.iss"), re.M)
    assert "*%s*" % otazka.group(1).strip() in sekcia
