# -*- coding: utf-8 -*-
"""Cesta cez iPhone je v kode, ale nevyskusana (0.2).

Autor nema zariadenie od Apple a PulseOSC je platena appka. Hrac si ju
nesmie kupit na zaklade vety, ktoru nikto neoveril - preto to musi byt
povedane vsade, kde appka alebo README PulseOSC ponuka.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402

KOREN = os.path.join(os.path.dirname(__file__), "..")


def test_qr_pre_iphone_hovori_platena_a_nevyskusane():
    assert "platená" in i18n.tr_lang("sk", "hr.qr_ios")
    assert "nevyskúšané" in i18n.tr_lang("sk", "hr.qr_ios").lower()
    assert "paid" in i18n.tr_lang("en", "hr.qr_ios")
    assert "not tested" in i18n.tr_lang("en", "hr.qr_ios").lower()


def test_krok_2_parovania_priznava_nevyskusany_iphone():
    sk = i18n.tr_lang("sk", "hr.step2_body")
    en = i18n.tr_lang("en", "hr.step2_body")
    assert "nevyskúšaná" in sk and "platená" in sk and "Apple" in sk
    assert "untested" in en and "paid" in en and "Apple" in en
    # heslo a scena su len pre appku na Androide
    assert "len appky pre Android" in sk
    assert "Android app only" in en
    # stara veta "ktoré appka tiež rozumie" tvrdila overenú vec
    assert "also understands" not in en


def test_readme_priznava_nevyskusany_iphone():
    with open(os.path.join(KOREN, "README.md"), encoding="utf-8") as fh:
        readme = fh.read()
    assert "PulseOSC" in readme
    assert "untested" in readme and "no Apple device" in readme
