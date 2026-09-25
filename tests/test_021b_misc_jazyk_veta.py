# -*- coding: utf-8 -*-
"""Veta pod vyberom jazyka hovori pravdu (review 0.2.1, bug 4).

Do 0.2.1 tam stalo „Mení sa aj jazyk ukážkových hlások.“ / "Also changes
the language of the sample phrases." - nepravda. Prepnutie jazyka texty
hlasok v existujucich profiloch neprepise: zabudovane slova sa beru v jazyku
appky len pri zalozeni profilu (`settings_model.default_slots`, pre sk/cs
anglicke). Spravanie sa NEMENI, opravena je len veta.
"""
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

import i18n  # noqa: E402
from _zdroj_appky import zdroj_metody  # noqa: E402

KLUC = "settings.language_sub"

# Povodne (nepravdive) znenia - nesmu sa vratit v ziadnom jazyku.
STARE = {
    "Mení sa aj jazyk ukážkových hlások.",
    "Also changes the language of the sample phrases.",
    "サンプルのセリフの言語も変わる。",
    "示例台词的语言也会一起改变。",
    "Меняется и язык образцовых фраз.",
    "También cambia el idioma de las frases de ejemplo.",
    "Ändert auch die Sprache der Beispielsätze.",
    "Change aussi la langue des phrases d’exemple.",
    "Muda também o idioma das frases de exemplo.",
    "Mění se i jazyk ukázkových hlášek.",
    "Сменя се и езикът на примерните подсказки.",
}


def test_veta_uz_neslubuje_preklad_hlasok_v_ziadnom_jazyku():
    zaznam = i18n.STRINGS[KLUC]
    for jazyk in i18n.LANGUAGES:
        text = zaznam.get(jazyk, "")
        assert text.strip(), jazyk
        assert text not in STARE, (jazyk, text)
    assert "sample phrases" not in zaznam["en"].lower()
    assert "ukážkových" not in zaznam["sk"]


def test_veta_je_prelozena_a_kratka():
    """Kazdy jazyk ma vlastny preklad (nie anglicku kopiu) a veta sa zmesti
    do riadku nastavenia (SettingRow, wrap 430 px pri pisme 11)."""
    zaznam = i18n.STRINGS[KLUC]
    for jazyk in i18n.LANGUAGES:
        if jazyk != "en":
            assert zaznam[jazyk] != zaznam["en"], jazyk
        assert len(zaznam[jazyk]) <= 60, (jazyk, zaznam[jazyk])


def test_prepnutie_jazyka_naozaj_neprepisuje_hlasky():
    """Veta tvrdi, ze hlasky, ktore uz hrac ma, si nechaju svoje slova.
    Ked niekto raz prida pretlmocenie hlasok pri prepnuti jazyka, tento test
    padne - a pripomenie, ze treba prepisat aj vetu v Nastaveniach."""
    src = zdroj_metody("on_lang_switch")
    assert "default_slots" not in src
    assert "slot.default" not in src
    assert '["text"]' not in src and "['text']" not in src
