# -*- coding: utf-8 -*-
"""Licencia a ochrana ludi (0.2, LICENSE-DESIGN.md prepisany autorom).

Kod je cely GPLv3 - vratane ensa, tem a rozlozenia. Autorove su len dva
obrazky (ikona a obrazok dojo). Upravena verzia sa musi zretelne oznacit
ako ina a nesmie sa vydavat za oficialny Zanshin. Oficialny zdroj je len
jeden repozitar - aby sa hrac vedel ubranit podvrhnutemu instalatoru.

Testy strazia, aby README, SOUL.md, PRIVACY.md a „O appke“ hovorili to
iste ako LICENSE-DESIGN.md.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import guide_content  # noqa: E402
import i18n  # noqa: E402

KOREN = os.path.join(os.path.dirname(__file__), "..")
REPO = "github.com/Dandurfin/Zanshin"


def _read(meno):
    with open(os.path.join(KOREN, meno), encoding="utf-8") as fh:
        return fh.read()


def test_oficialny_repozitar_je_v_o_appke_klikaci():
    assert guide_content.REPO_URL == "https://" + REPO
    assert ("GitHub", guide_content.REPO_URL) in guide_content.COMMUNITY_LINKS
    assert REPO in _read("LICENSE-DESIGN.md")


def test_copyright_v_appke_nesubuje_zdrojak_v_instalatore():
    for jazyk in i18n.LANGUAGES:
        t = i18n.tr_lang(jazyk, "about.copyright", version="0.2")
        assert REPO in t, jazyk
        assert "LICENSE-DESIGN.md" in t, jazyk
        assert "travels with it" not in t, jazyk
    assert "ide s ním aj jeho zdrojový kód" not in i18n.tr_lang(
        "sk", "about.copyright", version="0.2")


def test_readme_hovori_to_iste_co_license_design():
    readme = _read("README.md")
    hlavicka = readme.splitlines()[2]
    assert "protected design" not in hlavicka and "GPLv3" in hlavicka
    for zle in ("feature arrangement", "written consent", "all rights reserved",
                "dual-licensed"):
        assert zle not in readme, zle
    # Od 0.2.1: instalacka sa nevydava (bez podpisoveho certifikatu). Oficialny
    # je len repozitar - zdrojak a hotovy ZIP v jeho Releases s odtlackom
    # SHA-256, aby si hrac overil, ze ma pravy subor. Kopia odinakial nie je
    # od autora - README aj LICENSE-DESIGN.md to musia povedat rovnako.
    plain = " ".join(readme.split())
    assert "Official source:** only <https://" + REPO + ">" in readme
    assert ("ready-made Zanshin `.exe` or installer anywhere else, it isn't "
            "from me") in plain
    assert "SHA-256" in readme and "Get-FileHash" in readme
    assert "There is no installer" in plain
    assert "Each release lists the installer's SHA-256" not in readme
    licencia = " ".join(_read("LICENSE-DESIGN.md").split())
    assert "fingerprint of the installer" not in licencia
    assert "ready-made ZIP on its Releases page" in licencia
    assert "SHA-256 fingerprint" in licencia
    assert "There is no installer" in licencia


def test_soul_neprivlastnuje_vzhlad():
    soul = _read("SOUL.md")
    assert "the 残 mark, the artwork, the design" not in soul
    assert "app icon and the dojo artwork" in soul


def test_privacy_nepyta_suhlas_na_mobilny_port():
    assert "author's consent" not in _read("PRIVACY.md")
