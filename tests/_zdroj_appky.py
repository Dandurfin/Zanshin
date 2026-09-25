# -*- coding: utf-8 -*-
"""Zdrojak appky pre testy, ktore ju citaju ako text alebo cez ast.

`DandurfApp` je rozdelena do mixinov v moduloch `app_*.py` (stav ostava na
DandurfApp, mixiny nesu len metody). Test, ktory by cital iba app.py, by po
presune metody padol - alebo, co je horsie, test typu "v appke NIE JE X"
by presiel naprazdno. Preto vsetky testy citaju appku cez tento modul:

  * `subory_appky()`  - app.py a vsetky app_*.py (app.py prvy, potom abecedne),
  * `zdroj_appky()`   - ich spojeny zdrojak ako jeden retazec,
  * `strom_appky()`   - ast spojeneho zdrojaku,
  * `zdroj_metody(m)` / `uzol_metody(m)` - jedna metoda DandurfApp alebo
    mixinu, nech byva v ktoromkolvek subore. Namiesto rezania textu "od
    `def a` po `def b`", ktore po presune metod do inych suborov nesedi.

Spojeny zdrojak sa parsuje ako jeden modul - app_*.py preto nesmu mat
`from __future__ import ...` (to musi byt na zaciatku suboru).
"""
import ast
import glob
import os

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def subory_appky():
    """Mena suborov appky: app.py prvy, potom app_*.py abecedne."""
    mixiny = sorted(os.path.basename(p)
                    for p in glob.glob(os.path.join(KOREN, "app_*.py")))
    return ["app.py"] + mixiny


def zdroj_suboru(meno):
    # utf-8-sig: app.py ma na zaciatku BOM a `ast.parse` by na nom padol
    with open(os.path.join(KOREN, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def zdroj_appky():
    """Spojeny zdrojak app.py + app_*.py (v poradi `subory_appky`)."""
    return "\n".join(zdroj_suboru(meno) for meno in subory_appky())


def strom_appky():
    """ast spojeneho zdrojaku - pozicie uzlov sedia so `zdroj_appky()`."""
    return ast.parse(zdroj_appky())


def _metody():
    """(zdrojak suboru, uzol) pre kazdu metodu DandurfApp a mixinov.

    V app.py len trieda DandurfApp, v app_*.py kazda trieda na urovni
    modulu (su to mixiny DandurfApp). Vnorene funkcie sa nehladaju."""
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
    """ast uzol metody `meno` (DandurfApp alebo mixin)."""
    for _src, uzol in _metody():
        if uzol.name == meno:
            return uzol
    raise AssertionError(f"metoda {meno} nie je v DandurfApp ani v mixinoch app_*.py")


def zdroj_metody(meno):
    """Zdrojak metody `meno` ako text - od `def` po posledny riadok tela
    (bez dekoratorov a bez komentarov za telom)."""
    for src, uzol in _metody():
        if uzol.name == meno:
            return ast.get_source_segment(src, uzol)
    raise AssertionError(f"metoda {meno} nie je v DandurfApp ani v mixinoch app_*.py")
