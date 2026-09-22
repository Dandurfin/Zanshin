"""Testy kreslenia (hud_paint.py) - bezia bez Tk aj bez Windows.

Nekontroluju "ci to pekne vyzera" (to sa testovat neda), ale to, co sa
rozbije ticho: zle rozmery, prazdny obrazok, pad pri okrajovych hodnotach
(nulova historia, nulova zataz, chybajuce popisky).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hud_paint
import theme as theme_mod

pytestmark = pytest.mark.skipif(not hud_paint.PIL_AVAILABLE,
                                reason="pillow nie je nainstalovany")


@pytest.fixture
def style():
    return hud_paint.Style(theme_mod.tokens(theme_mod.MODERN))


def _has_content(image):
    """Aspon jeden nepriehladny pixel - chyti 'nakreslilo sa nic'."""
    return image.getchannel("A").getextrema()[1] > 0


@pytest.mark.parametrize("name", ["grounding", "jaw", "release"])
@pytest.mark.parametrize("t", [0.0, 0.5, 1.0])
def test_visuals_render_at_every_animation_phase(style, name, t):
    image = hud_paint.render_visual(name, 240, 160, style, t=t, label="TEST", ss=2)
    assert image.size == (240, 160)
    assert _has_content(image)


def test_visual_scales_to_4k_size(style):
    """Na 4K sa kresli dvojnasobok - nesmie to spadnut ani zmenit pomer."""
    image = hud_paint.render_visual("grounding", 480, 320, style, ss=2)
    assert image.size == (480, 320)
    assert _has_content(image)


def test_unknown_visual_returns_blank_instead_of_crashing(style):
    image = hud_paint.render_visual("neexistuje", 100, 100, style, ss=1)
    assert image.size == (100, 100)


@pytest.mark.parametrize("phase", [0.0, 0.33, 0.99])
@pytest.mark.parametrize("inhale", [True, False])
def test_breath_ring_renders_whole_cycle(style, phase, inhale):
    image = hud_paint.render_breath(160, 160, style, phase=phase, inhale=inhale,
                                    cycle_text="NADYCH", ss=2)
    assert image.size == (160, 160)
    assert _has_content(image)


def test_hud_renders_with_full_data(style):
    history = [60 + (i % 30) for i in range(90)]
    image = hud_paint.render_hud(style, bpm=118, stress=72, history=history,
                                 threshold=110, baseline=64,
                                 labels={"load": "ZATAZ", "high": "Vysoka"},
                                 pulse=0.2, session="12:30", ss=2)
    assert image.size == (int(hud_paint.HUD_WIDTH), int(hud_paint.HUD_HEIGHT))
    assert _has_content(image)


def test_hud_renders_with_no_data_at_all(style):
    """Stav 'este nic nechodi' je ten, ktory hrac uvidi ako prvy."""
    image = hud_paint.render_hud(style, bpm=None, stress=0.0, history=[],
                                 threshold=110, connected=False, ss=2)
    assert _has_content(image)


def test_hud_survives_flat_history(style):
    """Konstantny tep = nulovy rozsah; delenie nulou by krivku zhodilo."""
    image = hud_paint.render_hud(style, bpm=70, stress=5, history=[70] * 40,
                                 threshold=110, baseline=70, ss=2)
    assert _has_content(image)


def test_slot_icons_render_for_ui(style):
    for name in ("grounding", "jaw", "release", "breath", "heart"):
        image = hud_paint.render_slot_icon(name, 48, style, ss=2)
        assert image.size == (48, 48)
        assert _has_content(image), name


def test_both_themes_produce_different_accents():
    modern = hud_paint.Style(theme_mod.tokens(theme_mod.MODERN))
    zen = hud_paint.Style(theme_mod.tokens(theme_mod.ZEN))
    assert modern.accent != zen.accent
    assert modern.hot != modern.accent, "svetle jadro tahu musi byt jasnejsie"


# --------------------------------------------------------------------------
# Enso a prstenec "natiahnute"
# --------------------------------------------------------------------------

@pytest.mark.parametrize("live", [False, True])
@pytest.mark.parametrize("phase", [0.0, 0.45, 0.99])
def test_enso_renders_in_every_state(style, live, phase):
    image = hud_paint.render_enso(68, style, live=live, phase=phase, ss=2)
    assert image.size == (68, 68)
    assert _has_content(image)


def test_armed_ring_changes_the_picture(style):
    """Prstenec musi byt VIDNO - `armed=True` nesmie vratit ten isty obrazok."""
    bez = hud_paint.render_enso(68, style, live=True, phase=0.45, ss=2)
    s_prstencom = hud_paint.render_enso(68, style, live=True, phase=0.45,
                                        armed=True, ss=2)
    assert bez.tobytes() != s_prstencom.tobytes()


def test_armed_ring_only_when_live(style):
    """Natiahnute sa bez pocuvania stat neda; kreslit sa nesmie ani omylom."""
    bez = hud_paint.render_enso(68, style, live=False, phase=0.45, ss=2)
    s_prstencom = hud_paint.render_enso(68, style, live=False, phase=0.45,
                                        armed=True, ss=2)
    assert bez.tobytes() == s_prstencom.tobytes()


def test_armed_ring_stays_inside_the_canvas(style):
    """Prstenec ide DOVNUTRA, nie von.

    Vonku uz prstenec je (nacitavaci, r*1.20) a ten sa pri plnom nadychu
    plátna uz dotyka. Keby natiahnutie pridalo cokolvek von, orezalo by sa.
    Test porovnava alfu na okraji platna s tou istou snimkou bez prstenca -
    nesmie narast.
    """
    for phase in (0.0, 0.45):
        bez = hud_paint.render_enso(68, style, live=True, phase=phase, ss=2)
        s_prstencom = hud_paint.render_enso(68, style, live=True, phase=phase,
                                            armed=True, ss=2)
        assert _okraj(s_prstencom) <= _okraj(bez), f"faza {phase}"


def _okraj(image):
    """Najvyssia alfa na krajnych riadkoch a stlpcoch obrazka."""
    a = image.getchannel("A")
    w, h = a.size
    pasy = (a.crop((0, 0, w, 1)), a.crop((0, h - 1, w, h)),
            a.crop((0, 0, 1, h)), a.crop((w - 1, 0, w, h)))
    return max(pas.getextrema()[1] for pas in pasy)


def test_armed_ring_contracts_with_the_breath(style):
    """Stahovanie sa pocita z NEDYCHAJUCEHO zakladu.

    Keby sa pocitalo z `r`, dychanie tahu (0.955 -> 1.045) by stahovanie
    prstenca takmer vyrusilo (z 12 % by ostalo ~1,5 %) a prstenec by stal.

    Polomer sa meria ako ROZDIEL oproti tej istej snimke bez prstenca. Prvy
    pokus meral najdalsi pixel vo vnutornej polovici obrazka a meral tym
    ziaru okolo tahu - vysla rovnaka hodnota pre obe fazy a test padol na
    spravnom kode.
    """
    vydych = _polomer_prstenca(style, 0.0)
    nadych = _polomer_prstenca(style, 0.45)
    assert nadych < vydych - 1.0, (
        f"prstenec sa nestahuje: vydych {vydych:.1f}, nadych {nadych:.1f}")


def _polomer_prstenca(style, phase, size=68):
    """Stredovy polomer prstenca "natiahnute" v pixeloch.

    Berie sa rozdiel alfy medzi snimkou s prstencom a bez neho - to je
    presne on a nic ine. Z pixelov, kde rozdiel prekroci polovicu maxima,
    sa vrati priemerna vzdialenost od stredu.
    """
    bez = hud_paint.render_enso(size, style, live=True, phase=phase,
                                ss=2).getchannel("A")
    s_nim = hud_paint.render_enso(size, style, live=True, phase=phase,
                                  armed=True, ss=2).getchannel("A")
    stred = size / 2.0
    body = []
    najviac = 0
    for y in range(size):
        for x in range(size):
            rozdiel = s_nim.getpixel((x, y)) - bez.getpixel((x, y))
            if rozdiel > 0:
                najviac = max(najviac, rozdiel)
                body.append((rozdiel, x, y))
    assert body, f"prstenec sa vobec nenakreslil (faza {phase})"
    prah = najviac / 2.0
    vzdialenosti = [((x + 0.5 - stred) ** 2 + (y + 0.5 - stred) ** 2) ** 0.5
                    for rozdiel, x, y in body if rozdiel >= prah]
    assert vzdialenosti
    return sum(vzdialenosti) / len(vzdialenosti)
