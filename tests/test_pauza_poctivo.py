# -*- coding: utf-8 -*-
"""Kedy hlas zaznie - dokumenty musia hovorit to, co robi trigger.py.

Hlas caka na kratku pauzu vo VSTUPE (~2,5 s bez klavesu, mysi, ovladaca),
ked zataz prestala stupat, a nikdy v kritickom pasme. Hru appka nevidi -
tichy moment uprostred boja sa moze ratat ako pauza. „Nikdy cez akciu“
alebo „medzi kolami“ je slub, ktory kod nevie dat.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trigger  # noqa: E402

KOREN = os.path.join(os.path.dirname(__file__), "..")


def _read(meno):
    with open(os.path.join(KOREN, meno), encoding="utf-8") as fh:
        return fh.read()


def test_pauza_v_dokumentoch_sedi_s_kodom():
    assert trigger.default_params()["pause_s"] == 2.5
    for meno in ("SOUL.md", "README.md"):
        text = _read(meno)
        assert "2.5 s" in text, meno
        assert "can't see the game" in text, meno


def test_ziadne_absolutne_sluby_o_boji():
    for meno in ("SOUL.md", "README.md"):
        text = _read(meno).lower()
        for zle in ("never spoken over the action", "never speaks over the fight",
                    "on top of the play", "natural pauses", "never mid-fight",
                    "already easing"):
            assert zle not in text, (meno, zle)
