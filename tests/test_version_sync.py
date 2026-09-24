# -*- coding: utf-8 -*-
"""Jedna verzia zije na STYROCH miestach - musia sedet.

POZOR: tento subor sa NEPODARILO obnovit zo zaloh - je napisany nanovo.
Povodny test mohol kontrolovat viac veci; toto je minimum, ktore pokryva
chybu, kvoli ktorej vznikol.

Kazde z tych styroch miest vidi iny clovek:

  app.version_short v i18n.py     hrac, v titulnej liste
  MyAppVersion v Dandurf.iss      samostatny instalator
  version_info.txt                Windows -> Vlastnosti -> Podrobnosti
  "*Alpha X.Y" v README.md        kazdy na GitHube, este pred appkou

Raz sa uz rozisli: popis buildu hlasil "0.5 - alpha", kym titulna lista aj
instalator hovorili 1.0. Nikto si toho nevsimol, lebo kazde z tych miest
vidi niekto iny a nikdy nie naraz. (Piate miesto, popis Steam buildu,
zaniklo s celym Steam buildom - Zanshin nema ziadnu integraciu so Steamom.)

Test je staticky (cita zdrojak), aby bezal bez Tk aj bez buildu.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def _verzia_z_i18n():
    """Napr. 'version 2.0' -> '2.0'."""
    hodnota = i18n.STRINGS["app.version_short"]["en"]
    m = re.search(r"(\d+\.\d+)", hodnota)
    assert m, f"app.version_short/en neobsahuje cislo verzie: {hodnota!r}"
    return m.group(1)


def test_i18n_ma_verziu_vo_vsetkych_jazykoch():
    """Titulna lista nesmie v jednom jazyku hlasit inu verziu nez v inom."""
    verzia = _verzia_z_i18n()
    for kod in i18n.LANGUAGES:
        hodnota = i18n.STRINGS["app.version_short"][kod]
        assert verzia in hodnota, (
            f"app.version_short/{kod} = {hodnota!r}, cakala sa verzia {verzia}")


def test_installer_sedi_s_titulnou_listou():
    m = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', _read("Dandurf.iss"))
    assert m, "Dandurf.iss neobsahuje #define MyAppVersion"
    assert m.group(1) == _verzia_z_i18n(), (
        f"Dandurf.iss hlasi {m.group(1)}, i18n {_verzia_z_i18n()}")


def test_metadata_exe_sedia_s_titulnou_listou():
    """filevers/prodvers su 4 cisla, FileVersion/ProductVersion retazce -
    vsetky styri musia vychadzat z tej istej verzie."""
    src = _read("version_info.txt")
    verzia = _verzia_z_i18n()
    hlavna, vedlajsia = verzia.split(".")
    ntica = f"({hlavna}, {vedlajsia}, 0, 0)"

    for pole in ("filevers", "prodvers"):
        m = re.search(rf"{pole}=\(([^)]*)\)", src)
        assert m, f"version_info.txt neobsahuje {pole}"
        assert f"({m.group(1)})" == ntica, (
            f"version_info.txt {pole}=({m.group(1)}), cakalo sa {ntica}")

    for pole in ("FileVersion", "ProductVersion"):
        m = re.search(rf"StringStruct\('{pole}',\s*'([^']+)'\)", src)
        assert m, f"version_info.txt neobsahuje {pole}"
        assert m.group(1) == f"{verzia}.0.0", (
            f"version_info.txt {pole}={m.group(1)}, cakalo sa {verzia}.0.0")


def test_readme_sedi_s_titulnou_listou():
    """README vidi kazdy na GitHube este skor nez appku. Test ho doteraz
    nestrazil, a tak po zdvihnuti na 0.2 ostalo v hlavicke "Alpha 0.1", kym
    lista, instalator aj exe hlasili 0.2."""
    m = re.search(r"^\*Alpha (\d+\.\d+) ·", _read("README.md"), re.M)
    assert m, "README.md nema v hlavicke riadok '*Alpha X.Y · ...'"
    assert m.group(1) == _verzia_z_i18n(), (
        f"README.md hlasi {m.group(1)}, i18n {_verzia_z_i18n()}")
