# -*- coding: utf-8 -*-
"""Zanshin nema ziadnu integraciu so Steamom (rozhodnutie autora, 0.2).

Steam vrstva, Steam spec, build skript aj depot su v _archiv. Tieto testy
strazia, ze sa potichu nevratili - a ze dokumenty hovoria to iste.
"""
import os
import re

KOREN = os.path.join(os.path.dirname(__file__), "..")


def _read(meno):
    with open(os.path.join(KOREN, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def test_steam_vrstva_ani_steam_build_v_projekte_nie_su():
    for meno in ("steam_integration.py", "ZanshinDojoSync_steam.spec",
                 "build_steam.ps1", "STEAM_BUILD.md",
                 os.path.join("steam", "app_build.vdf")):
        assert not os.path.exists(os.path.join(KOREN, meno)), meno


def test_appka_steam_neimportuje_ani_nevola():
    dovoz = re.compile(r"^\s*(?:from|import)\s+(?:steam_integration|steamworks)\b", re.M)
    for meno in sorted(os.listdir(KOREN)):
        if meno.endswith(".py"):
            assert not dovoz.search(_read(meno)), meno
    assert not re.search(r"\bsteam\.\w+\(", _read("app.py"))


def test_build_steam_nebali():
    spec = _read("Dandurf.spec")
    for token in ("steam_integration", "steamworks", "steam_appid"):
        assert token not in spec, token


def test_dokumenty_hovoria_ze_steam_integracia_nie_je():
    for meno in ("README.md", "PRIVACY.md"):
        assert "no Steam integration" in _read(meno), meno
    assert "steam_integration" not in _read("PRIVACY.md")
