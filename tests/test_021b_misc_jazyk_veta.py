# -*- coding: utf-8 -*-
"""The sentence under the language picker is true (review 0.2.1, bug 4).

Until 0.2.1 it said „Mení sa aj jazyk ukážkových hlások.“ / "Also changes
the language of the sample phrases." - untrue. Switching the language
does not rewrite the cue texts in existing profiles: the built-in words
are taken in the app's language only when a profile is created
(`settings_model.default_slots`, English for sk/cs). The behaviour does
NOT change, only the sentence is fixed.
"""
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

import i18n  # noqa: E402
from _zdroj_appky import zdroj_metody  # noqa: E402

KLUC = "settings.language_sub"

# The original (untrue) wordings - they must not come back in any language.
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
    """Every language has its own translation (not an English copy) and the
    sentence fits into a settings row (SettingRow, wrap 430 px at font
    11)."""
    zaznam = i18n.STRINGS[KLUC]
    for jazyk in i18n.LANGUAGES:
        if jazyk != "en":
            assert zaznam[jazyk] != zaznam["en"], jazyk
        assert len(zaznam[jazyk]) <= 60, (jazyk, zaznam[jazyk])


def test_prepnutie_jazyka_naozaj_neprepisuje_hlasky():
    """The sentence claims that cues the player already has keep their words.
    When someone one day adds re-translating cues on a language switch, this
    test fails - and reminds that the sentence in Settings has to be
    rewritten too."""
    src = zdroj_metody("on_lang_switch")
    assert "default_slots" not in src
    assert "slot.default" not in src
    assert '["text"]' not in src and "['text']" not in src
