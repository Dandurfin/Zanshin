"""„Nie je to lekarska rada, Zanshin nie je zdravotnicka pomocka“ - v appke.

KNOWN_ISSUES.md #5: ta veta zila len v README, kym Sprievodca ukazoval
fyziologiu a dychacie techniky so zadrzami bez jedineho slova. Historia uz
hovori „postrehy a tipy, nie diagnozy“ - Sprievodca ma hovorit rovnako
ticho: jedna tlmena veta, nie varovny banner. A do hry nejde nikdy.

Staticke, bez Tk - rovnako ako test_overlay_features.
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
    """Telo funkcie od `hlavicka` po najblizsie dva prazdne riadky."""
    telo = src[src.index(hlavicka):]
    return telo[:telo.index(chr(10) * 3)]


def test_veta_hovori_to_podstatne_a_ticho():
    preklady = i18n.STRINGS[KLUC]
    assert set(preklady) == set(i18n.LANGUAGES)
    sk, en = preklady["sk"], preklady["en"]

    assert "nie lekárska rada" in sk and "nie je zdravotnícka pomôcka" in sk
    assert "not medical advice" in en and "not a medical device" in en
    assert "srdc" in sk and "heart" in en     # s tazkostami so srdcom k lekarovi
    # Zvysok Sprievodcu je prelozeny do vsetkych jazykov - jedina anglicka
    # veta medzi nimi by bola prave ta, ktoru ma clovek precitat.
    for lang in i18n.LANGUAGES:
        if lang not in ("sk", "en"):
            assert preklady[lang] != en, lang

    # Septat, nie kricat: ziadny vykricnik, ziadne VELKE slova, ziadny odstavec.
    for text in (sk, en):
        assert "!" not in text, text
        assert not [w for w in text.split() if len(w) > 2 and w.isupper()], text
        assert len(text) <= 200, "ma to byt jedna ticha veta, nie odstavec"


def test_sprievodca_ju_ma_v_hlavicke_a_pri_dychani():
    guide = _read("guide_panel.py")
    # Jedno miesto, ktore text kresli - hlavicka aj karta ho len volaju.
    assert guide.count(f'tr("{KLUC}")') == 1

    pomocnik = _funkcia(guide, "def not_medical_note")
    assert 'pal["text_faint"]' in pomocnik and "ui_kit.ui(10)" in pomocnik
    kod = pomocnik[pomocnik.index('"""', pomocnik.index('"""') + 3):]
    for hlasne in ('"bold"', "danger", "warn", "border_width", "fg_color"):
        assert hlasne not in kod, f"poznamka ma septat, nie kricat ({hlasne})"

    # okno Sprievodca: hned pod podtitulkom, vidno ju bez rozbalovania
    okno = guide[guide.index("class GuidePanel"):]
    assert "not_medical_note(header" in okno
    # a nesmie sa orezat: okno ide zuzit na minsize 560, hlavicka ma padx 22
    import re
    wrap = int(re.search(r"not_medical_note\(header, pal, wraplength=(\d+)\)",
                         okno).group(1))
    assert wrap <= 560 - 2 * 22, wrap

    # dychacie techniky (box breathing ma zadrze) - vetva `techniques`;
    # ta ista funkcia kresli aj kartu dychovej hlasky (ui_dialogs.SlotCard)
    telo = _funkcia(guide, "def populate_card_body")
    techniky = telo[telo.index('card.get("techniques")'):
                    telo.index('elif card.get("custom_blocks")')]
    assert "not_medical_note(text_col" in techniky
    # ostatne karty ju neopakuju - refren by uz nebol septanie
    assert telo.count("not_medical_note(") == 1


def test_na_jednej_obrazovke_najviac_raz():
    """Hlavicka okna Sprievodca stoji NAD scrollom, takze je vidno stale.
    Keby ju zopakovala aj rozbalena karta dychania, ta ista veta by bola na
    obrazovke dvakrat - to uz je refren, nie septanie."""
    guide = _read("guide_panel.py")
    okno = guide[guide.index("class GuidePanel"):]
    assert "_GuideContent(scroll, pal, medical_note=False)" in okno

    # karta dychovej hlasky (stranka Hlasky) hlavicku nema - tam ostava
    dialogs = _read("ui_dialogs.py")
    volanie = dialogs[dialogs.index("guide_panel.populate_card_body("):]
    volanie = volanie[:volanie.index(")") + 1]
    assert "medical_note" not in volanie


def test_techniky_su_len_na_karte_dychania():
    """Poznamka visi na vetve `techniques`. Keby techniky dostala aj ina
    karta, poznamka by sa s nimi potichu rozmnozila - nech to niekto vidi."""
    import guide_content
    s_technikami = [c["id"] for c in guide_content.guide_cards()
                    if c["techniques"] is not None]
    assert s_technikami == ["breath"]


def test_do_hry_nejde():
    """Pocas hrania sa hraca nic nepyta a nic mu nepripomina."""
    for modul in ("overlay.py", "hud.py", "hud_paint.py", "layer_window.py"):
        if os.path.exists(os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), modul)):
            src = _read(modul)
            assert KLUC not in src and "not_medical_note" not in src, modul
