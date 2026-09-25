# -*- coding: utf-8 -*-
"""0.2.1: upratanie po review a počítadlo v denníku len z Tk vlákna.

  * `_deliver` beží na vlastnom vlákne; `session_counts` mení LEN Tk vlákno
    (cez `ui_call`) - `start_listening` ho medzitým vymieňa za nový slovník,
  * mŕtve importy (`random` v app.py, `os` v make_icon.py) sú preč,
  * main.py menuje vzhľady tak, ako sa volajú (Sumi / Aizome),
  * Dandurf.spec vysvetľuje vypnuté UPX raz, nie dvakrát rovnakým textom.
"""
import ast
import os
import re
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

KOREN = os.path.join(os.path.dirname(__file__), "..")


def _zdroj(meno):
    with open(os.path.join(KOREN, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _importy(meno):
    mena = set()
    for uzol in ast.walk(ast.parse(_zdroj(meno))):
        if isinstance(uzol, ast.Import):
            mena.update(a.asname or a.name for a in uzol.names)
    return mena


def _pouzite_mena(meno):
    return {u.id for u in ast.walk(ast.parse(_zdroj(meno)))
            if isinstance(u, ast.Name)}


# --------------------------------------------------------------------------
# `_deliver`: počítadlo cez `ui_call`
# --------------------------------------------------------------------------

def _dorucenie(source):
    import app as app_mod
    fronta = []
    a = types.SimpleNamespace(
        _emit=lambda slot: None, log_threadsafe=lambda *x: None,
        ui_call=fronta.append, session_counts={0: 0, 1: 0, 2: 0, 3: 0},
        obnovene=[])
    a.update_session_label = lambda: a.obnovene.append(dict(a.session_counts))
    slot = types.SimpleNamespace(index=2, text_value="Ramena", audio_path="",
                                 mode="tts")
    app_mod.DandurfApp._deliver(a, slot, False, source)
    return a, fronta


def test_deliver_nemeni_pocitadlo_z_cudzieho_vlakna():
    a, fronta = _dorucenie("trigger")
    assert a.session_counts == {0: 0, 1: 0, 2: 0, 3: 0}, \
        "vlakno `_deliver` nesmie siahat na `session_counts`"
    assert len(fronta) == 1
    # `start_listening` medzitym slovnik vymeni - prirastok ide do toho,
    # ktory plati, ked sa to vykona na Tk vlakne
    a.session_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    fronta.pop()()
    assert a.session_counts == {0: 0, 1: 0, 2: 1, 3: 0}
    assert a.obnovene == [{0: 0, 1: 0, 2: 1, 3: 0}], "riadok sa prekresli"


def test_deliver_test_ani_hud_nerata():
    for zdroj in ("test", "hud_panel"):
        a, fronta = _dorucenie(zdroj)
        assert a.session_counts == {0: 0, 1: 0, 2: 0, 3: 0}
        assert fronta == []


def test_v_deliver_nie_je_priamy_zapis_pocitadla():
    """Priradenie do `session_counts` smie byť len vo vnorenej funkcii,
    ktorú dostane `ui_call` - nie v tele `_deliver` samom."""
    fn = next(u for u in ast.walk(ast.parse(_zdroj("app.py")))
              if isinstance(u, ast.FunctionDef) and u.name == "_deliver")
    vnorene = [u for u in ast.walk(fn)
               if isinstance(u, ast.FunctionDef) and u is not fn]
    vo_vnorenych = {id(x) for f in vnorene for x in ast.walk(f)}
    for u in ast.walk(fn):
        if isinstance(u, (ast.Assign, ast.AugAssign)) and id(u) not in vo_vnorenych:
            assert "session_counts" not in ast.unparse(u), ast.unparse(u)
    assert any("ui_call" in ast.unparse(u) for u in ast.walk(fn)
               if isinstance(u, ast.Call))


# --------------------------------------------------------------------------
# Mŕtve importy
# --------------------------------------------------------------------------

def test_app_neimportuje_random():
    assert "random" not in _importy("app.py")
    assert "random" not in _pouzite_mena("app.py")


def test_make_icon_neimportuje_os():
    assert "os" not in _importy("make_icon.py")
    assert "os" not in _pouzite_mena("make_icon.py")


def test_note_cue_ostava_lebo_sa_vola():
    """`_note_cue` je zámerný prázdny háčik - volá ho `fire_slot` a stráži ho
    tests/test_measure.py. Upratanie ho preto nechalo tak."""
    src = _zdroj("app.py")
    assert "def _note_cue(" in src
    assert "self._note_cue(" in src


# --------------------------------------------------------------------------
# Texty v kóde
# --------------------------------------------------------------------------

def test_main_menuje_vzhlady_ako_sa_volaju():
    doc = ast.get_docstring(ast.parse(_zdroj("main.py")))
    assert "Zen / Modern" not in doc
    assert "Sumi" in doc and "Aizome" in doc


def test_spec_vysvetluje_upx_raz():
    spec = _zdroj("Dandurf.spec")
    nastavenia = re.findall(r"^\s*upx=(\w+),", spec, re.M)
    assert nastavenia == ["False", "False"], "UPX musi ostat vypnuty v EXE aj COLLECT"
    assert spec.count("signatura baleneho malveru") == 1
    assert spec.count("# UPX VYPNUTY") == 2
