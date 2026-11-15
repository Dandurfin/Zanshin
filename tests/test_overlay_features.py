"""Tests of the new visual features: pictogram colour, drag-test mode,
blocking the mouse wheel on sliders. No Tk - the logic and API contract are
tested.
"""
import ast, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import settings_model as sm
from _zdroj_appky import subory_appky, zdroj_appky, zdroj_metody


def test_overlay_config_has_color():
    """Every visual has a color field in its config (None = theme colour)."""
    for cfg in sm.default_overlay_configs():
        assert "color" in cfg and cfg["color"] is None


def test_color_validation():
    """The colour is stored only as a valid #rrggbb, otherwise None."""
    assert sm.normalize_overlay_config({"color": "#AABBCC"}, 0)["color"] == "#aabbcc"
    assert sm.normalize_overlay_config({"color": "#f80"}, 0)["color"] is None      # short
    assert sm.normalize_overlay_config({"color": "red"}, 0)["color"] is None       # a name
    assert sm.normalize_overlay_config({"color": "#GGGGGG"}, 0)["color"] is None   # not hex
    assert sm.normalize_overlay_config({"color": None}, 0)["color"] is None


def _read(name):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, name), encoding="utf-8-sig") as fh:
        return fh.read()


def test_slider_wheel_is_blocked_everywhere():
    """Every CTkSlider must be wrapped with block_slider_wheel - otherwise the
    value can be changed by the mouse wheel by mistake while scrolling the
    page."""
    # the app = app.py and the DandurfApp mixins in app_*.py
    for f in (*subory_appky(), "ui_dialogs.py"):
        src = _read(f)
        raw_sliders = len(re.findall(r"ctk\.CTkSlider\(", src))
        wrapped = len(re.findall(r"block_slider_wheel\(ctk\.CTkSlider\(", src))
        assert raw_sliders == wrapped, \
            f"{f}: {raw_sliders} sliderov, {wrapped} obalenych - vsetky musia byt obalene"


def test_block_slider_wheel_returns_slider():
    """Helper must return the slider so .pack()/.grid() chaining works."""
    src = _read("ui_kit.py")
    body = src[src.index("def block_slider_wheel"):]
    body = body[:body.index("\ndef ", 5)] if "\ndef " in body[5:] else body
    assert "return slider" in body


def test_block_slider_wheel_replaces_internal_handler():
    """Helper must bind directly to slider._canvas (tkinter bind without add),
    otherwise the internal CTkSlider handler runs first and changes the value -
    CTkSlider.bind() always adds (add=True), so 'break' would come too late."""
    src = _read("ui_kit.py")
    body = src[src.index("def block_slider_wheel"):]
    body = body[:body.index("\ndef ", 5)] if "\ndef " in body[5:] else body
    assert '"_canvas"' in body and "canvas.bind(seq, _redirect)" in body


def test_overlay_test_button_text_is_not_timed():
    """Test button may no longer promise '3 s' - it is an untimed drag mode."""
    import i18n
    for lang, text in i18n.STRINGS["overlay.test"].items():
        assert "3 s" not in text and "3秒" not in text and "3 秒" not in text and "3 с" not in text, (lang, text)
    for lang, text in i18n.STRINGS["overlay.dialog_hint"].items():
        assert "3 s" not in text and "3 se" not in text and "3秒" not in text and "3 с" not in text, (lang, text)


def test_overlay_test_mode_decorates_frame_for_hit_testing():
    """In test mode _render must run the frame through _decorate_test (alpha
    >= 1 over the whole area = the window holds the mouse anywhere, not just
    on the line)."""
    src = _read("overlay.py")
    block = src[src.index("    def _render(self, elapsed):"):]
    block = block[:block.index("\n    def ", 5)]
    assert "_decorate_test" in block
    assert "def _decorate_test" in src


def test_overlay_test_is_drag_mode_not_timed():
    """test() of a slot must start the persistent drag mode (_test_mode),
    not a 3-second preview."""
    src = _read("overlay.py")
    block = src[src.index("    def test(self):"):]
    block = block[:block.index("\n    def ", 5)]
    assert "_test_mode" in block, "test() musi prepinat drag rezim"


def test_layered_surface_can_toggle_click_through():
    """Dragging needs a way to switch the window click-through off briefly."""
    src = _read("layer_window.py")
    assert "def set_click_through" in src
    assert "WS_EX_TRANSPARENT" in src


def test_overlay_windows_keep_steam_overlay_flags():
    """Every overlay window must have all FOUR extended styles at once.

    Until now only WS_EX_TRANSPARENT was tested, but the other three are just
    as essential and easily get lost when the window is changed:

      WS_EX_LAYERED      - makes transparent drawing possible at all
      WS_EX_TRANSPARENT  - clicks pass into the game (anti-cheat principle)
      WS_EX_NOACTIVATE   - the window never takes focus, the game keeps it
      WS_EX_TOOLWINDOW   - not in Alt+Tab or on the taskbar

    NOACTIVATE + TOOLWINDOW are also what keeps the app clear of the Steam
    overlay (Shift+Tab): a window that does not ask for focus and does not
    act like an ordinary app does not fight the Steam overlay for the active
    window.
    """
    src = _read("layer_window.py")
    flags = ("WS_EX_LAYERED", "WS_EX_TRANSPARENT",
             "WS_EX_NOACTIVATE", "WS_EX_TOOLWINDOW")

    for flag in flags:
        assert f"{flag} = 0x" in src, f"{flag} nie je definovany"

    # The places where the window is CREATED must set all four at once. We
    # recognise them by adding WS_EX_LAYERED - `set_click_through()`, on the
    # contrary, deliberately toggles just a single bit (TRANSPARENT) and leaves
    # the rest alone, so we do not count it here.
    setups = src.split("WS_EX_LAYERED")[1:]
    # the first item is the constant's definition (`WS_EX_LAYERED = 0x...`)
    setups = [s for s in setups if not s.lstrip().startswith("=")]
    assert len(setups) >= 2, (
        f"cakali sa aspon 2 miesta, kde sa overlay oknu nasadzuju styly, "
        f"najdene: {len(setups)}")
    for i, seg in enumerate(setups, 1):
        head = seg[:200]
        for flag in ("WS_EX_TRANSPARENT", "WS_EX_NOACTIVATE", "WS_EX_TOOLWINDOW"):
            assert flag in head, (
                f"{i}. zakladanie overlay okna nenasadzuje {flag} - overlay "
                f"by prestal byt click-through alebo by sa bil o fokus "
                f"(aj so Steam overlayom)")


def test_guide_je_pod_hlaskami_a_stara_cesta_nezmizla():
    """Since 18. 9. the Guide is NOT a separate tab - explanations and theory
    sit under the cues, because that is exactly where people look for them.

    But the "guide" key must not get lost: `Sidebar.GROUPS`, the command
    palette and the guide itself refer to it. If `_navigate("guide")` fell
    through to `pages.show("guide")`, the window would stay EMPTY - silently,
    without an exception. Hence `TAB_ALIAS`.
    """
    shell = _read("ui_shell.py")
    assert '"guide": "nastavenia"' in shell, "guide musi zostat v GROUPS sidebaru"

    app_src = zdroj_appky()
    riadok = app_src[app_src.index("SETTINGS_TABS = ("):].split("\n")[0]
    assert '"guide"' not in riadok, "guide uz nema byt samostatna karta"

    assert 'TAB_ALIAS = {"guide": "spustace"}' in app_src, \
        "stara cesta na guide musi niekam viest"
    nav = zdroj_metody("_navigate")
    assert "TAB_ALIAS" in nav, "_navigate musi alias naozaj pouzit"

    # and the content is really inserted under the cues
    assert "_build_guide_into" in app_src
    spustace = zdroj_metody("_build_spustace_page")
    assert "_build_guide_into" in spustace, "vysvetlivky nie su na stranke hlasok"

    guide = _read("guide_panel.py")
    assert "def build_guide_into" in guide
    assert "class _GuideContent" in guide
    # The embedded guide MUST NOT have its own scroll - it already sits in a
    # scrolling page and a second scrollbar would squeeze the content into a
    # narrow strip.
    vkladanie = guide[guide.index("def build_guide_into"):]
    vkladanie = vkladanie[:vkladanie.index(chr(10) * 3)]
    # only the CODE under the docstring - the note mentions the word on purpose
    vkladanie = vkladanie[vkladanie.index('"""', vkladanie.index('"""') + 3):]
    assert "CTkScrollableFrame" not in vkladanie, "dvojity scroll sa vratil"

    # And the old guide page is NO LONGER BUILT. While it was built, it ran
    # after the Cues page and overwrote `self.guide_content` - expanding
    # cards then reached for an invisible page.
    assert "_build_guide_page" not in app_src, "mrtva stranka sprievodcu sa vratila"


def test_guide_uses_real_overlay_icons():
    """The Guide must draw the real pictograms from the overlay
    (render_slot_icon), not just illustrative sketches."""
    src = _read("guide_panel.py")
    block = src[src.index("def sketch_or_image"):]
    block = block[:block.index("\nclass ", 5)]
    assert "render_slot_icon" in block, \
        "sketch_or_image musi pouzit realny piktogram z hud_paint"


def test_karta_hlasky_uz_nenastavuje_casovanie():
    """Six timing fields have disappeared from the cue card.

    The own cooldown, delay, "every Nth", repetition, pause between
    repetitions and spread were read ONLY in `fire_slot`, i.e. for the Test
    button and a click in the HUD preview. The automatic cue is fired by
    `_fire_somatic_cue` via `_emit`. So these were controls that did nothing
    while playing - and yet they looked like the app's main setting.
    """
    dialogs = _read("ui_dialogs.py")
    # Only the body of SlotCard - `HoverTooltip` has its own `self.delay`
    # (the bubble delay) and has nothing to do with cue timing.
    karta = dialogs[dialogs.index("class SlotCard:"):]
    karta = karta[:karta.index('\nclass ', 5)]
    for mrtve in ("self.every_n", "self.repeat_gap", "self.jitter",
                  "self.cooldown", "self.delay", "self.repeat",
                  "_cooldown_text", "press_count"):
        assert mrtve not in karta, f"{mrtve} sa vratilo na kartu hlasky"
    assert "class NumberStepper" not in dialogs, "stepper uz nema co ovladat"
    dialog = dialogs[dialogs.index("class SlotSettingsDialog:"):]
    dialog = dialog[:dialog.index('\nclass ', 5)]
    assert "NumberStepper" not in dialog, "dialog hlasky ma nastavovat uz len hlas"
    # "timing" is checked in the code only: the class docstring now explains
    # in English that the timing used to sit here.
    trieda = next(u for u in ast.walk(ast.parse(dialogs))
                  if isinstance(u, ast.ClassDef) and u.name == "SlotSettingsDialog")
    for uzol in ast.walk(trieda):
        telo = getattr(uzol, "body", None)
        if isinstance(telo, list):
            uzol.body = [v for v in telo if not (
                isinstance(v, ast.Expr) and isinstance(v.value, ast.Constant)
                and isinstance(v.value.value, str))] or [ast.Pass()]
    assert "timing" not in ast.unparse(trieda).lower(), "dialog hlasky ma nastavovat uz len hlas"

    # delivery = `fire_slot` + `_note_cue` + `_deliver`
    dorucenie = "\n".join(zdroj_metody(m) for m in ("fire_slot", "_note_cue", "_deliver"))
    for mrtve in ("slot.every_n", "slot.jitter", "slot.repeat", "slot.delay",
                  "slot.cooldown", "press_count"):
        assert mrtve not in dorucenie, f"{mrtve} sa vratilo do dorucenia"


def test_ako_casto_sa_ozvem_riadi_algoritmus_nie_prepinac():
    """The "how often I speak up" choice is gone — threshold comes from data.

    It had three positions (menej / bezne / viac) and the player had no way of
    knowing what each would do FOR THEM: load is scaled against their own
    baseline, so the same number means something different for everyone.

    The first session runs on the numbers for the average player
    (`trigger.default_params()`); one's own threshold comes once there is
    something to compute it from.
    """
    app_src = zdroj_appky()
    assert "cue_sensitivity" not in app_src, "nastavenie sa vratilo"
    assert "self.citlivost_var" not in app_src, "prepinac sa vratil"

    assert "hr_stats.dynamicky_prah_zataze(" in app_src, "prah sa nikde nepocita"
    assert "trigger.default_params()" in app_src,         "chybaju cisla pre priemerneho hraca"

    # Order: the average player, above it the player's own threshold, above
    # that the developer overlay. All three layers are in `_open_hr_session` -
    # the order is measured in it.
    otvor = zdroj_metody("_open_hr_session")
    zaklad = otvor.index("self.cue_trigger.params.update(trigger.default_params())")
    vlastny = otvor.index('self.cue_trigger.params["stress_threshold"] = float(')
    dev = otvor.index("self.cue_trigger.params.update(self._dev_params)")
    assert zaklad < vlastny < dev, "vrstvy sa prekryvaju v zlom poradi"


def test_prah_zataze_sa_rata_z_vlastnych_relacii():
    """The 80th percentile of one's own load — not a number from a table.

    Measured on real data: threshold 73 gives 3,7 delivered cues per hour,
    i.e. under the cap of 5 from the spec. The threshold does not decide HOW
    MANY cues come (that is done by `max_per_hour` and `min_gap_s`), but WHICH
    moments qualify.
    """
    import hr_stats

    # The curve must look like a body: smooth, no jumps over 30 bpm between
    # neighbouring points - otherwise `je_podozriva` (rightly) marks it as
    # broken and it drops out of the computation.
    def relacie(bpm_hore):
        vlna = []
        for i in range(60):
            for b in range(70, bpm_hore, 5):       # smoothly up
                vlna.append(b)
            for b in range(bpm_hore, 70, -5):      # and back down
                vlna.append(b)
        return [{"curve": vlna, "duration_s": 1800.0, "baseline_bpm": 70}
                for _ in range(4)]

    nizky = hr_stats.dynamicky_prah_zataze(relacie(85), baseline=70, critical=110)
    vysoky = hr_stats.dynamicky_prah_zataze(relacie(130), baseline=70, critical=110)
    assert nizky is not None and vysoky is not None
    assert vysoky > nizky, "vyhrotenejsie relacie musia dat vyssi prah"
    lo, hi = hr_stats.PRAH_ROZSAH
    assert lo <= nizky <= hi and lo <= vysoky <= hi

    # without data nothing is claimed
    assert hr_stats.dynamicky_prah_zataze([]) is None
    assert hr_stats.dynamicky_prah_zataze(
        [{"curve": [80] * 600, "duration_s": 1800.0}]) is None

def test_vysvetlivka_sedi_v_karte_hlasky_ku_ktorej_patri():
    """Each of the four cues carries its own explanation.

    The order is NOT random: `guide_content.GUIDE_CARD_IDS` must match slots
    0-3 in the same order as `measure.CATEGORIES`, because these are the same
    four somatic visuals. If one of these lists were reordered, the "Zuby"
    (Teeth) card would silently show the explanation for breathing - no
    exception, no error, just the wrong text.
    """
    import guide_panel
    import measure
    from guide_content import GUIDE_CARD_IDS

    assert len(GUIDE_CARD_IDS) == len(measure.CATEGORIES) + 1
    assert GUIDE_CARD_IDS[-1] == guide_panel.PHILOSOPHY_ID
    for index in range(len(measure.CATEGORIES)):
        karta = guide_panel.card_for_slot(index)
        assert karta is not None and karta["id"] == GUIDE_CARD_IDS[index]

    # The player's own slot has no explanation; philosophy belongs to no cue.
    for mimo in (len(measure.CATEGORIES), 99, -1, None, "x"):
        assert guide_panel.card_for_slot(mimo) is None


def test_obsah_vysvetlivky_ma_jeden_zdroj():
    """The cue card and the Guide draw THE SAME content.

    If each place assembled the blocks itself, the first text change would
    make them diverge - and nobody would notice which of them is outdated.
    """
    guide = _read("guide_panel.py")
    assert "def populate_card_body" in guide
    assert guide.count("populate_card_body(") >= 2
    dialogs = _read("ui_dialogs.py")
    assert "guide_panel.populate_card_body(" in dialogs

    karta = dialogs[dialogs.index("class SlotCard:"):]
    karta = karta[:karta.index(chr(10) + "class ", 5)]
    assert "def toggle_detail" in karta
    # The body is built only on the first expand - four cards at once would
    # show as a stutter on every page redraw.
    assert "_detail_built" in karta


def test_spodny_blok_je_uz_len_filozofia():
    guide = _read("guide_panel.py")
    vkladanie = guide[guide.index("def build_guide_into"):]
    vkladanie = vkladanie[:vkladanie.index(chr(10) * 3)]
    assert "card_ids=[PHILOSOPHY_ID]" in vkladanie, \
        "styri vysvetlivky uz patria do kariet hlasok, nie sem"
    assert "expand_first=False" in vkladanie, \
        "desat odkazov na studie nema visiet rozbalenych pod hlaskami"
