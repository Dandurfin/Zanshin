"""Steam vrstva MUSI byt volitelna - appka bezi rovnako bez SDK.

Toto je bezpecnostna poistka: keby sa niekedy do steam_integration dostal
tvrdy import Steamu na urovni modulu alebo vynimka smerom von, appka by
spadla u kazdeho, kto nema SDK - teda u takmer vsetkych pocas vyvoja aj u
hracov mimo Steamu. Testy overuju, ze sa to nestane.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_import_without_sdk_does_not_raise():
    """Samotny import nesmie nic vyzadovat ani spadnut."""
    import steam_integration
    assert steam_integration.steam is not None
    assert steam_integration.steam.enabled is False


def test_all_public_calls_are_safe_without_sdk():
    """Kazda verejna funkcia sa musi dat volat aj ked SDK/Steam nie je -
    nesmie hodit vynimku, len ticho nic neurobit."""
    from steam_integration import steam
    # ziadne z toho nesmie padnut, aj ked nic nie je pripojene
    assert steam.init() is False
    steam.run_callbacks()
    steam.set_status(True)
    steam.set_status(False)
    steam.shutdown()
    assert steam.enabled is False


def test_init_is_idempotent():
    """Opakovany init() nesmie znova skusat ani padnut."""
    from steam_integration import _SteamState
    state = _SteamState()
    first = state.init()
    second = state.init()
    assert first == second


def test_app_id_from_env(monkeypatch):
    """Ak je SteamAppId v prostredi, modul ho najde - ale bez SDK aj tak
    ostane vypnuty (nema sa cim pripojit)."""
    from steam_integration import _SteamState
    monkeypatch.setenv("SteamAppId", "480")
    state = _SteamState()
    assert state._discover_app_id() == "480"
    # SDK nie je -> init aj tak vrati False, appka bezi dalej
    assert state.init() is False


def test_app_py_guards_every_steam_call():
    """app.py musi kazde volanie steam.* obalit try/except - staticka
    kontrola, ze Steam nikdy nezhodi appku ani pri neocakavanej chybe."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "app.py"), encoding="utf-8-sig") as fh:
        src = fh.read()
    import re
    # najdi vsetky riadky so steam.<nieco>( a over, ze su v ramci try
    for m in re.finditer(r"steam\.(init|run_callbacks|set_status|shutdown)\(", src):
        # 200 znakov pred volanim musi obsahovat "try:"
        window = src[max(0, m.start() - 200):m.start()]
        assert "try:" in window, \
            f"volanie steam.{m.group(1)}() nie je v try/except - moze zhodit appku"
