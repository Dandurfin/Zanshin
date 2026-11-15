# -*- coding: utf-8 -*-
"""When the voice speaks - the documents must say what trigger.py does.

The voice waits for a short pause in the INPUT (~2.5 s without a key, the
mouse, the controller) when the load has stopped rising, and never in the
critical zone. The app does not see the game - a quiet moment in the middle
of a fight can count as a pause. „Never during action“ or „between rounds“
is a promise the code cannot give.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trigger  # noqa: E402

KOREN = os.path.join(os.path.dirname(__file__), "..")


def _read(meno):
    with open(os.path.join(KOREN, meno), encoding="utf-8") as fh:
        return fh.read()


DOKUMENTY = ("SOUL.md", "README.md", "docs/HOW-IT-WORKS.md")   # 0.3d: the rules too


def test_pauza_v_dokumentoch_sedi_s_kodom():
    assert trigger.default_params()["pause_s"] == 2.5
    for meno in DOKUMENTY:
        text = _read(meno)
        assert "2.5 s" in text, meno
        assert "can't see the game" in text, meno


def test_ziadne_absolutne_sluby_o_boji():
    for meno in DOKUMENTY:
        text = _read(meno).lower()
        for zle in ("never spoken over the action", "never speaks over the fight",
                    "on top of the play", "natural pauses", "never mid-fight",
                    "already easing"):
            assert zle not in text, (meno, zle)
