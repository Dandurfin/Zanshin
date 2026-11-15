# -*- coding: utf-8 -*-
"""The app's source code for tests that read it as text or via ast.

`DandurfApp` is split into mixins in the `app_*.py` modules (the state stays
on DandurfApp, the mixins carry only methods). A test that read only app.py
would fail after a method was moved - or, worse, a test of the "the app does
NOT contain X" kind would pass vacuously. That is why all tests read the app
through this module:

  * `subory_appky()`  - app.py and all app_*.py (app.py first, then
    alphabetically),
  * `zdroj_appky()`   - their joined source as one string,
  * `strom_appky()`   - the ast of the joined source,
  * `zdroj_metody(m)` / `uzol_metody(m)` - one method of DandurfApp or of a
    mixin, whichever file it lives in. Instead of cutting text "from
    `def a` to `def b`", which no longer fits after methods move to other
    files.

The joined source is parsed as one module - so app_*.py must not have
`from __future__ import ...` (that has to be at the start of the file).
"""
import ast
import glob
import os

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def subory_appky():
    """The app's file names: app.py first, then app_*.py alphabetically."""
    mixiny = sorted(os.path.basename(p)
                    for p in glob.glob(os.path.join(KOREN, "app_*.py")))
    return ["app.py"] + mixiny


def zdroj_suboru(meno):
    # utf-8-sig: app.py has a BOM at the start and `ast.parse` would fail on it
    with open(os.path.join(KOREN, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def zdroj_appky():
    """Joined source of app.py + app_*.py (in `subory_appky` order)."""
    return "\n".join(zdroj_suboru(meno) for meno in subory_appky())


def strom_appky():
    """ast of the joined source - node positions match `zdroj_appky()`."""
    return ast.parse(zdroj_appky())


def _metody():
    """(file source, node) for every method of DandurfApp and the mixins.

    In app.py only the DandurfApp class, in app_*.py every module-level
    class (they are DandurfApp mixins). Nested functions are not looked
    for."""
    for meno in subory_appky():
        src = zdroj_suboru(meno)
        for trieda in ast.parse(src).body:
            if not isinstance(trieda, ast.ClassDef):
                continue
            if meno == "app.py" and trieda.name != "DandurfApp":
                continue
            for uzol in trieda.body:
                if isinstance(uzol, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield src, uzol


def uzol_metody(meno):
    """ast node of the method `meno` (DandurfApp or a mixin)."""
    for _src, uzol in _metody():
        if uzol.name == meno:
            return uzol
    raise AssertionError(f"metoda {meno} nie je v DandurfApp ani v mixinoch app_*.py")


def zdroj_metody(meno):
    """Source of the method `meno` as text - from `def` to the last line of
    the body (without decorators and without comments after the body)."""
    for src, uzol in _metody():
        if uzol.name == meno:
            return ast.get_source_segment(src, uzol)
    raise AssertionError(f"metoda {meno} nie je v DandurfApp ani v mixinoch app_*.py")
