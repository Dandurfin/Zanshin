# -*- coding: utf-8 -*-
"""One version lives in FOUR places - they have to match.

WARNING: this file could NOT be restored from the backups - it is written
anew. The original test may have checked more things; this is the minimum
that covers the bug it was created for.

Each of those four places is seen by a different person:

  app.version_short in i18n.py     the player, in the title bar
  MyAppVersion in Dandurf.iss      the standalone installer
  version_info.txt                 Windows -> Properties -> Details
  "*Alpha X.Y.Z" in README.md      everyone on GitHub, even before the app

They have drifted apart once already: the build description said
"0.5 - alpha", while the title bar and the installer said 1.0. Nobody
noticed, because each of those places is seen by someone else and never at
the same time. (A fifth place, the Steam build description, went away with
the whole Steam build - Zanshin has no Steam integration at all.)

THREE NUMBERS (0.2.1). The version no longer has to be just "X.Y". The test
used to take the first "X.Y" from the string - from "alpha 0.2.1" it would
pull "0.2", and a language left at "alpha 0.2" would pass (substring),
while the installer and the exe said 0.2.1. So the version is taken whole
and compared exactly.

The test is static (it reads the source), so that it runs without Tk and
without a build.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")

# The whole version: 2 to 4 numbers separated by dots ("0.2", "0.2.1").
_VERZIA = r"\d+(?:\.\d+){1,3}"


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def _cela_verzia(text):
    """E.g. 'alpha 0.2.1' -> '0.2.1' (not '0.2')."""
    m = re.search(_VERZIA, text)
    return m.group(0) if m else None


def _verzia_z_i18n():
    hodnota = i18n.STRINGS["app.version_short"]["en"]
    verzia = _cela_verzia(hodnota)
    assert verzia, f"app.version_short/en neobsahuje cislo verzie: {hodnota!r}"
    return verzia


def _vydana_verzia():
    verzia = _verzia_z_i18n()
    zmeny = _read("CHANGELOG.md")
    if f"\n## What {verzia} changes (not released yet)\n" not in zmeny:
        return verzia
    nadpisy = re.findall(rf"^## What ({_VERZIA}) ", zmeny, re.M)
    assert len(nadpisy) >= 2 and nadpisy[0] == verzia, (
        f"CHANGELOG.md: the unreleased {verzia} must be the first section, "
        f"followed by the last release: {nadpisy}")
    return nadpisy[1]


def _styri_cisla(verzia):
    """Windows wants 4 numbers in VERSIONINFO - the missing ones are zeros."""
    cisla = [int(x) for x in verzia.split(".")]
    return cisla + [0] * (4 - len(cisla))


def test_cela_verzia_sa_neoreze():
    """Regression of 0.2.1: a three-number version must not be cut to "X.Y"."""
    assert _cela_verzia("alpha 0.2.1") == "0.2.1"
    assert _cela_verzia("アルファ 0.2.1") == "0.2.1"
    assert _cela_verzia("alfa 0.2") == "0.2"
    assert _styri_cisla("0.2.1") == [0, 2, 1, 0]
    assert _styri_cisla("0.2") == [0, 2, 0, 0]


def test_i18n_ma_verziu_vo_vsetkych_jazykoch():
    """The title bar must not report a different version in one language than
    in another - not even a shorter one ("alpha 0.2" next to "alpha 0.2.1")."""
    verzia = _verzia_z_i18n()
    for kod in i18n.LANGUAGES:
        hodnota = i18n.STRINGS["app.version_short"][kod]
        assert _cela_verzia(hodnota) == verzia, (
            f"app.version_short/{kod} = {hodnota!r}, cakala sa verzia {verzia}")


def test_installer_sedi_s_titulnou_listou():
    m = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', _read("Dandurf.iss"))
    assert m, "Dandurf.iss neobsahuje #define MyAppVersion"
    assert m.group(1) == _verzia_z_i18n(), (
        f"Dandurf.iss hlasi {m.group(1)}, i18n {_verzia_z_i18n()}")


def test_metadata_exe_sedia_s_titulnou_listou():
    """filevers/prodvers are 4 numbers, FileVersion/ProductVersion strings -
    all four must come from the same version."""
    src = _read("version_info.txt")
    cisla = _styri_cisla(_verzia_z_i18n())
    ntica = "(" + ", ".join(str(c) for c in cisla) + ")"
    retazec = ".".join(str(c) for c in cisla)

    for pole in ("filevers", "prodvers"):
        m = re.search(rf"{pole}=\(([^)]*)\)", src)
        assert m, f"version_info.txt neobsahuje {pole}"
        assert f"({m.group(1)})" == ntica, (
            f"version_info.txt {pole}=({m.group(1)}), cakalo sa {ntica}")

    for pole in ("FileVersion", "ProductVersion"):
        m = re.search(rf"StringStruct\('{pole}',\s*'([^']+)'\)", src)
        assert m, f"version_info.txt neobsahuje {pole}"
        assert m.group(1) == retazec, (
            f"version_info.txt {pole}={m.group(1)}, cakalo sa {retazec}")


def test_readme_sedi_s_titulnou_listou():
    """Everyone on GitHub sees the README even before the app. The test did
    not guard it until now, so after the bump to 0.2 the header still said
    "Alpha 0.1", while the title bar, the installer and the exe all said
    0.2."""
    m = re.search(rf"^\*Alpha ({_VERZIA}) ·", _read("README.md"), re.M)
    assert m, "README.md nema v hlavicke riadok '*Alpha X.Y.Z · ...'"
    assert m.group(1) == _verzia_z_i18n(), (
        f"README.md hlasi {m.group(1)}, i18n {_verzia_z_i18n()}")


def test_known_issues_nesie_aktualnu_verziu():
    """KNOWN_ISSUES.md is the list for THIS version - the heading has to name
    it, otherwise the reader would not know whether the list applies to
    what they have in hand."""
    prvy = _read("KNOWN_ISSUES.md").splitlines()[0]
    m = re.search(rf"alpha ({_VERZIA})\s*$", prvy)
    assert m, f"KNOWN_ISSUES.md: nadpis nekonci 'alpha X.Y.Z': {prvy!r}"
    assert m.group(1) == _vydana_verzia(), (
        f"KNOWN_ISSUES.md hlasi {m.group(1)}, vydana verzia {_vydana_verzia()}")
