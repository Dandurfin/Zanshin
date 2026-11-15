"""Colour tokens for two visual modes.

SUMI (default) - a warm ink variant with a gold accent ("Sumi night").
Gold (`accent`/`kin`) is the main accent across the whole UI; blue
(`blue`) is used only to mark calm/low values (e.g. heart rate recovery),
not as decoration.

AIZOME - the indigo variant. The same architecture, just a different base
and a blue accent. Since 0.2 it is the look of the WORK world (see
`WORLD_THEME`). Here too, a number in blue (`blue`) is only heart rate
recovery - that is why the calm zone (`zone_calm`) is not blue but asagi
(blue-green).

STATUS COLOURS (0.3, UX audit). The status dot in the side panel
(`ui_shell._StateDot`) is solid `success` while watching, when stopped it
is just a hollow ring in `text_faint`, and "not now" has an amber ring
(`warn`). A stopped app is a NORMAL state, not an alarm - red (`danger`)
would scream there every time the PC starts. `danger` is only for an
error and for a destructive action (delete), never for "stopped" nor for
the heart rate maximum.

RULES that follow from the tokens (so that each place does not have to
work them out itself):
  * ON and SELECTED = `accent` (toggle, active tab, selected world).
    `accent2` is only a muted fill UNDER a frame in `accent`, on its own
    it means nothing - an enabled toggle in `accent2` had a contrast of
    1.07:1 against a disabled one.
  * Content text (explanations, axes, legends) has a contrast of at least
    4.5:1 on `surface`; that is why `text_faint` is lighter since 0.3
    (2.85 -> 4.72 in Sumi, 3.01 -> 4.76 in Aizome). Hierarchy is carried
    by size and weight, not invisibility.
  * Divider lines (`rule`) have at least 1.5:1, otherwise they are just
    unexplained gaps. The panel frame stays quiet (`line_soft`) - a frame
    should not scream.
  * The frame of a secondary button (`control_border`) has at least 3:1,
    otherwise the button looks disabled. The text of a destructive action
    (`danger_text`) has 4.5:1; `danger` itself is too dark for small text:
    SMALL RED TEXT (state, error, a sentence under a control) is always
    `danger_text`, `danger` only an area (fill, close-button hover) and
    large type.
  * A DISABLED button has one look for all kinds (`ui_kit.
    vzhlad_vypnuteho`): text `text_faint`, frame `control_border`, no red
    and no gold - a disabled "Delete" must not look ready.
  * The dialog window frame (`ui_kit.DIALOG_RAM_TOKEN`) is `rule`: it is
    the edge of an area like a divider line, not a control -
    `control_border` would turn the window into a button.

WARNING ABOUT KEYS: `ZEN` and `MODERN` are NOT just names of colour
schemes - they are also identifiers of SFX sets (`sfx_key` in the settings
has the form "zen:earth_thud"). They MUST NOT be renamed, otherwise every
existing profile loses its sounds. The displayed theme names are in i18n
(theme.modern.label / theme.zen.label: Aizome / Sumi).
"""

ZEN = "zen"
MODERN = "modern"
DEFAULT_THEME = ZEN

# TWO WORLDS, TWO LOOKS (0.2, B3-worlds). The theme is no longer a matter
# of taste but a sign of the world: one look at the window tells you
# whether you are in Play or in Work. The world keys are the same as
# `hr_stats.ACTIVITY_KINDS` - written by hand so that the theme does not
# have to import hr_stats.
WORLD_THEME = {"play": ZEN, "work": MODERN}


def theme_world(theme_key):
    """Inverse of `WORLD_THEME`: theme -> world. An unknown theme is Play."""
    for world, key in WORLD_THEME.items():
        if key == theme_key:
            return world
    return "play"

THEMES = {
    # ---- AIZOME (indigo) ----
    MODERN: {
        "font_family": "Segoe UI",
        "bg": "#0D1119",
        "surface": "#121826",
        "surface_alt": "#182033",
        "card": "#121826",
        "card_border": "#212B41",
        "border": "#212B41",
        "line_soft": "#18202F",
        "accent": "#5C86C9",
        "accent_hover": "#8FB0E8",
        "accent2": "#26395F",
        "accent2_hover": "#35507F",
        "text": "#E7EAF2",
        "text_dim": "#8F99B2",
        # 4.76:1 on surface (before #5A6480 = 3.01:1 - the explanations under
        # the settings and the chart axes were hard to read)
        "text_faint": "#7A84A0",
        "success": "#7FB39A",
        "danger": "#C04A3E",
        "danger_text": "#D86A5E",    # "Delete" text/frame: 5.19:1 on surface
        "warn": "#C9A24D",
        "entry_bg": "#0B0F17",
        "switch_off": "#212B41",
        "rule": "#2C3854",           # divider lines: 1.52:1 on surface
        "control_border": "#56658A",  # secondary button frame: 3.06:1
        # --- elements of the new UI ---
        "plate": "#101725",          # calm state of the breathing bar
        "plate_glow": "#1B2740",     # peak of the in-breath
        # The stopped bar was the only warm area of the window in Aizome
        # (#131013 with a brown frame) - it looked cut out of Sumi. Now it is
        # dark indigo, the bar "does not breathe" by being darker than `plate`.
        "plate_idle": "#0F131C",
        "plate_idle_border": "#26324A",
        "keycap_face": "#1C2536",
        "keycap_edge": "#2C374F",
        "keycap_text": "#8FB0E8",
        "washi": "#DCD3C0",          # the 残 mark
        # --- status/secondary colours (dashboard, enso) ---
        "bengara": "#C04A3E",        # NOTE: enso now uses success/danger
        "blue": "#5C86C9",           # calm/low values (Aizome is already blue)
        "murasaki": "#9C8FC9",
        # --- heart rate zones (see the note under THEMES) ---
        # Aizome starts at the COLD end, the hot end stays hot - warmth is
        # warmth in every theme. Calm is ASAGI (blue-green, a shade from the
        # same indigo dye works), NOT blue: before 0.3 it was #6FA5C9 and the
        # "Resting HR" card next to the "Recovery" card (`blue`) were two
        # blues - and blue belongs only to recovery (0.3 batch 4, UX audit). As
        # in Sumi, where calm is matcha: greenish, cooler than the rest of the
        # row. 7.15:1 on surface; it differs from `success` in both hue and
        # saturation.
        "zone_calm": "#5FB3A3",
        "zone_raised": "#B9A25F",
        "zone_high": "#C97C43",
        "zone_critical": "#C04A3E",
    },
    # ---- SUMI night (ink + gold) ----
    ZEN: {
        "font_family": "Segoe UI",
        "bg": "#0D0E13",
        "surface": "#191A22",
        "surface_alt": "#20222C",
        "card": "#191A22",
        "card_border": "#2A2B36",
        "border": "#2A2B36",
        "line_soft": "#22232E",
        "accent": "#D9B868",
        "accent_hover": "#E3CA8E",
        "accent2": "#2A2620",
        "accent2_hover": "#3A342A",
        "text": "#ECE8E0",
        "text_dim": "#9A9488",
        # 4.72:1 on surface (before #66625A = 2.85:1)
        "text_faint": "#8A857B",
        "success": "#8FBF9F",
        "danger": "#C1553D",
        "danger_text": "#D46F57",    # "Delete" text/frame: 5.12:1 on surface
        "warn": "#C9A24D",
        "entry_bg": "#0A0B0F",
        "switch_off": "#2A2B36",
        "rule": "#393A46",           # divider lines: 1.54:1 on surface
        "control_border": "#66676F",  # secondary button frame: 3.08:1
        "plate": "#17181F",
        "plate_glow": "#29241A",
        "plate_idle": "#131319",
        "plate_idle_border": "#3A2F22",
        "keycap_face": "#20212B",
        "keycap_edge": "#2E2F3B",
        "keycap_text": "#D9B868",
        "washi": "#DCD3C0",
        # --- status/secondary colours (dashboard, enso) ---
        "bengara": "#A6432E",        # NOTE: enso now uses success/danger
        "blue": "#7B93C9",           # calm/low values (e.g. HRR recovery)
        "murasaki": "#B888C0",
        # --- heart rate zones (see the note under THEMES) ---
        # Sumi keeps the whole row in the warm family: matcha -> gold -> plum
        # blossom -> bengara. It is ink and gold, nothing cold.
        #
        # `zone_calm` was originally #8FBF9F - a mint green that read as a
        # foreign element in ink with gold (reported). Matcha is warm, greenish
        # and from the same vocabulary as the rest of the theme; `success`
        # (running / OK) stays the original one, that is a state, not a heart
        # rate zone.
        "zone_calm": "#9CAE7B",
        "zone_raised": "#C9A24D",
        "zone_high": "#D9843F",
        "zone_critical": "#C1553D",
    },
}

# HEART RATE ZONES - each theme has its own row of colours
# --------------------------------------------------------
# The four zones (calm / raised / high / critical) were originally drawn
# success -> accent -> warn -> danger. Two problems at once:
#
#   * in Sumi `accent` is #D9B868 and `warn` #C9A24D - two almost
#     identical golds that nobody can tell apart next to each other on one
#     bar;
#   * in Aizome `accent` is blue and `blue` (calm, low values) has the
#     same value, so blue would mean both "calm" and "raised".
#
# The first fix introduced an orange in-between step and a shared row
# success -> warn -> orange -> danger. But `warn` has the same value in
# BOTH themes (#C9A24D), so the load bar in the indigo Aizome glowed with
# Sumi gold - it looked cut out of the other theme.
#
# That is why each theme now has its own `zone_*` tokens:
#   Sumi   - all of it in the warm family (green -> gold -> plum -> bengara)
#   Aizome - a cold start (asagi, blue-green for calm - blue `blue`
#            belongs only to heart rate recovery), the hot end stays hot,
#            because warmth is warmth in every theme
#
# What holds in both: the row must be monotonic in TEMPERATURE (from calm
# to hot) and all four colours distinguishable from each other - guarded
# by `tests/test_hr_charts.py`. The accent is not among them at all; it
# belongs to controls, not to the heart rate state.
#
# A zone's colour is ONE across the whole UI - the session trace, the
# legend and the load bar all take it via `zone_color` below.
ZONE_TOKENS = {
    "calm": "zone_calm",
    "raised": "zone_raised",
    "high": "zone_high",
    "critical": "zone_critical",
}


def zone_color(pal, zone):
    """HR zone colour from the palette - one source of truth for all charts."""
    return pal[ZONE_TOKENS.get(zone, "accent")]


def tokens(theme_key):
    return THEMES.get(theme_key, THEMES[DEFAULT_THEME])


def mix(color_a, color_b, t):
    """Linear mix of two #rrggbb colours (t = 0 -> a, 1 -> b).

    Used by the breathing bar: Tk cannot animate transparency or scale, so
    the "breath" is done by a smooth transition of the fill between
    `plate` and `plate_glow`.
    """
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    a = [int(color_a.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(color_b.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(
        int(round(x + (y - x) * t)) for x, y in zip(a, b))
