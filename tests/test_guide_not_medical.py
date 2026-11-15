""""Not medical advice, Zanshin is not a medical device" - in the app.

KNOWN_ISSUES.md #5: that sentence lived only in the README, while the Guide
showed physiology and breathing techniques with breath holds without a
single word. History already says "Observations and tips, not diagnoses" -
the Guide should speak just as quietly: one muted sentence, not a warning
banner. And it never goes into the game.

Static, without Tk - same as test_overlay_features.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import i18n

KLUC = "guide.not_medical_note"


def _read(name):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, name), encoding="utf-8-sig") as fh:
        return fh.read()


def _funkcia(src, hlavicka):
    """Function body from `hlavicka` to the next two empty lines."""
    telo = src[src.index(hlavicka):]
    return telo[:telo.index(chr(10) * 3)]


def test_veta_hovori_to_podstatne_a_ticho():
    preklady = i18n.STRINGS[KLUC]
    assert set(preklady) == set(i18n.LANGUAGES)
    sk, en = preklady["sk"], preklady["en"]

    assert "nie lekárska rada" in sk and "nie je zdravotnícka pomôcka" in sk
    assert "not medical advice" in en and "not a medical device" in en
    assert "srdc" in sk and "heart" in en     # with heart problems see a doctor
    # The rest of the Guide is translated into all languages - the only
    # English sentence among them would be exactly the one the person should
    # read.
    for lang in i18n.LANGUAGES:
        if lang not in ("sk", "en"):
            assert preklady[lang] != en, lang

    # Whisper, not shout: no exclamation mark, no CAPITAL words, no paragraph.
    for text in (sk, en):
        assert "!" not in text, text
        assert not [w for w in text.split() if len(w) > 2 and w.isupper()], text
        assert len(text) <= 200, "ma to byt jedna ticha veta, nie odstavec"


def test_sprievodca_ju_ma_v_hlavicke_a_pri_dychani():
    guide = _read("guide_panel.py")
    # One place that draws the text - the header and the card only call it.
    assert guide.count(f'tr("{KLUC}")') == 1

    pomocnik = _funkcia(guide, "def not_medical_note")
    assert 'pal["text_faint"]' in pomocnik and "ui_kit.ui(10)" in pomocnik
    kod = pomocnik[pomocnik.index('"""', pomocnik.index('"""') + 3):]
    for hlasne in ('"bold"', "danger", "warn", "border_width", "fg_color"):
        assert hlasne not in kod, f"poznamka ma septat, nie kricat ({hlasne})"

    # the Guide window: right under the subtitle, visible without expanding
    okno = guide[guide.index("class GuidePanel"):]
    assert "not_medical_note(header" in okno
    # and it must not get cut off: the window can be narrowed to minsize 560,
    # the header has padx 22
    import re
    wrap = int(re.search(r"not_medical_note\(header, pal, wraplength=(\d+)\)",
                         okno).group(1))
    assert wrap <= 560 - 2 * 22, wrap

    # breathing techniques (box breathing has holds) - the `techniques`
    # branch; the same function also draws the breathing cue card
    # (ui_dialogs.SlotCard)
    telo = _funkcia(guide, "def populate_card_body")
    techniky = telo[telo.index('card.get("techniques")'):
                    telo.index('elif card.get("custom_blocks")')]
    assert "not_medical_note(text_col" in techniky
    # the other cards do not repeat it - a refrain would no longer be a whisper
    assert telo.count("not_medical_note(") == 1


def test_na_jednej_obrazovke_najviac_raz():
    """The Guide window header stands ABOVE the scroll, so it is always
    visible. If the expanded breathing card repeated it too, the same
    sentence would be on the screen twice - that is a refrain, not a
    whisper."""
    guide = _read("guide_panel.py")
    okno = guide[guide.index("class GuidePanel"):]
    assert "_GuideContent(scroll, pal, medical_note=False)" in okno

    # the breathing cue card (the Cues page) has no header - there it stays
    dialogs = _read("ui_dialogs.py")
    volanie = dialogs[dialogs.index("guide_panel.populate_card_body("):]
    volanie = volanie[:volanie.index(")") + 1]
    assert "medical_note" not in volanie


def test_techniky_su_len_na_karte_dychania():
    """The note hangs on the `techniques` branch. If another card got
    techniques too, the note would quietly multiply with them - let
    someone see it."""
    import guide_content
    s_technikami = [c["id"] for c in guide_content.guide_cards()
                    if c["techniques"] is not None]
    assert s_technikami == ["breath"]


def test_do_hry_nejde():
    """While playing, nothing asks the player anything or reminds them."""
    for modul in ("overlay.py", "hud.py", "hud_paint.py", "layer_window.py"):
        if os.path.exists(os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), modul)):
            src = _read(modul)
            assert KLUC not in src and "not_medical_note" not in src, modul
