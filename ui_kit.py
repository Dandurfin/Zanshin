"""Building blocks of the new interface - what CSS did in the mockup.

Why a separate module
---------------------
The mockup relied on things CSS gives for free and Tk cannot do at all:
transparency, scale, transitions, `grid-template-columns`. Each such element
has one class here that does it by hand - and app.py then only assembles
finished parts, not pixels.

Three things that had to be solved differently than in HTML:

  * BREATHING BAR. In CSS it was a scale and opacity animation. Tk can do
    neither, so `KamaeBar` breathes by a SMOOTH FILL TRANSITION between
    `plate` and `plate_glow` (see theme.mix) plus a growing line on the
    bottom edge. That is two signals instead of one, so it also works for
    someone who cannot see the colour difference.

  * KEYCAP. `border-bottom: 3px` cannot be set on a CTkFrame, so the keycap
    is two frames on top of each other: a darker bottom one (the edge) and a
    lighter top one (the face), shifted 3 px up.

  * FIXED GRID. `grid-template-columns: 108px 1fr 100px ...` is
    `grid_columnconfigure(i, minsize=..., weight=...)` in Tk. The difference
    is that Tk minsize does NOT CLIP the content - a wider widget stretches
    the column. That is why all elements in the grid have a fixed `width`.

No element here has app logic of its own - it takes everything via callbacks.
"""

import math
import os
import sys
import time
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox    # only a fallback for the app's windows (`_systemove_okno`)

import customtkinter as ctk

import display as display_mod     # `display` is a font in this module (below)
import hr_stats
import theme as theme_mod


# --------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------
#
# The mockup used Zen Kaku Gothic New and Chivo Mono from Google Fonts. Tk
# only knows fonts installed in the system, so the first available one from
# the list is taken. Bahnschrift (a narrow DIN-style technical cut) ships
# with both Windows 10 and 11 and is the closest to the technical character
# the numbers on the HUD need.

_UI = ["Segoe UI Variable Text", "Segoe UI", "Inter", "DejaVu Sans", "TkDefaultFont"]
_DISPLAY = ["Bahnschrift", "Segoe UI Semibold", "Segoe UI", "DejaVu Sans"]
_MONO = ["Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Courier New"]

# JAPANESE AND CHINESE have their own font (0.3, UX audit). Segoe UI has
# no kanji, so Tk looked up each character in a different fallback font -
# "メインスイッチ" came out thin, "心拍と負荷" in another cut, two fonts on
# one line. A font with CJK characters from Windows (Yu Gothic UI /
# Microsoft YaHei UI) draws Latin and the characters in one cut. It applies
# to texts and headings; numbers (mono) stay.
_UI_LANG = {
    "ja": ["Yu Gothic UI", "Meiryo UI", "MS UI Gothic"],
    "zh": ["Microsoft YaHei UI", "Microsoft YaHei", "SimHei"],
}

_resolved = {}


def _pick(candidates):
    try:
        available = {name.lower() for name in tkfont.families()}
    except Exception:
        return candidates[-1]
    for name in candidates:
        if name.lower() in available:
            return name
    return candidates[-1]


def _jazyk_pisma():
    """The interface language if it has its own font (ja/zh), otherwise "".

    It is read on every call: switching the language rebuilds the window,
    so the new widgets pick up the new font by themselves."""
    try:
        import i18n
        kod = i18n._lang.get("code", "")
    except Exception:
        return ""
    return kod if kod in _UI_LANG else ""


def fonts():
    """Font names - found once per language, only once a Tk root exists."""
    kod = _jazyk_pisma()
    if kod not in _resolved:
        sada = {"mono": _pick(_MONO)}
        if kod:
            cjk = _pick(_UI_LANG[kod] + _UI)
            sada["ui"] = cjk
            sada["display"] = cjk
        else:
            sada["ui"] = _pick(_UI)
            sada["display"] = _pick(_DISPLAY)
        _resolved[kod] = sada
    return _resolved[kod]


# Kanji and hanzi have more strokes per character than Latin - at 10 px
# they blur together (audit: "kanji at 9 pt"). So in Japanese and Chinese
# the smallest interface font is 11.
_CJK_MIN_SIZE = 11


def ui(size, weight="normal"):
    if _jazyk_pisma() and size < _CJK_MIN_SIZE:
        size = _CJK_MIN_SIZE
    return (fonts()["ui"], size, weight)


def display(size, weight="normal"):
    return (fonts()["display"], size, weight)


def mono(size, weight="normal"):
    return (fonts()["mono"], size, weight)


# --------------------------------------------------------------------------
# Drawing on a Canvas
# --------------------------------------------------------------------------

def round_rect(canvas, x0, y0, x1, y1, r, **kw):
    """Rounded rectangle - Tk Canvas does not have it as a primitive.

    It is made of one smoothed polygon; the doubled corner points force
    `smooth=True` to round only the corners and keep the edges straight.
    """
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    points = [
        x0 + r, y0, x1 - r, y0, x1 - r, y0, x1, y0,
        x1, y0 + r, x1, y1 - r, x1, y1 - r, x1, y1,
        x1 - r, y1, x0 + r, y1, x0 + r, y1, x0, y1,
        x0, y1 - r, x0, y0 + r, x0, y0 + r, x0, y0,
    ]
    return canvas.create_polygon(points, smooth=True, **kw)


# --------------------------------------------------------------------------
# Uniform rounding
# --------------------------------------------------------------------------
#
# Feedback from testing: the app mixed square (radius 3-4) and rounded
# (12-14) elements. From now on ONE style: panels and cards RADIUS_PANEL,
# buttons, fields and chips RADIUS_CONTROL. New elements should use these
# constants, not numbers.

RADIUS_PANEL = 10
RADIUS_CONTROL = 8


# --------------------------------------------------------------------------
# One measure for the whole app (0.3, UX audit)
# --------------------------------------------------------------------------
#
# The audit found four left edges (cards at x=161, content at 171, headings
# once at 170, once at 179) and a jagged right column: dropdowns ended at a
# different x than the sliders, because CTkOptionMenu without
# `dynamic_resizing=False` grows with the text of the selected item. From
# now on:
#   * PAGE_GUTTER - the left and right margin of every page, of the tab row
#     (SubNav) and of the breathing bar, so everything starts on one
#     vertical line,
#   * CONTROL_W - the width of a control in the right column of a settings
#     row (dropdown, slider), so they share one right edge.

PAGE_GUTTER = 24
CONTROL_W = 250
# Width of the vertical scrollbar of CTkScrollableFrame including its 1 px
# border (CTkScrollbar is 16 px). An element ABOVE the scrolling area (the
# breathing bar on Today) leaves it free on the right so that it ends where
# the cards below it do.
SCROLLBAR_W = 17


def linka(master, pal, token="rule"):
    """A horizontal 1 px divider line in the colour `pal[token]`.

    WHY NOT A BARE `CTkFrame(height=1)`: at a height of 1 px CTk draws a
    rectangle with zero height (y0 == y1) and the canvas under it has the
    PARENT's colour - the line was not visible at all, regardless of
    contrast (checked on CTk 6.0). Hence the "unexplained gaps" from the
    audit. A `bg_color` in the same colour paints the canvas itself, so the
    line is always exactly 1 px. `_drz_pozadie_linky` keeps the parent from
    overwriting it on a theme change."""
    farba = pal[token]
    ciara = ctk.CTkFrame(master, fg_color=farba, bg_color=farba, height=1,
                         corner_radius=0)
    _drz_pozadie_linky(ciara)
    return ciara


def _drz_pozadie_linky(ciara):
    """The line's background is ALWAYS its own colour (`bg_color` = `fg_color`).

    WHY: when its `fg_color` changes, a CTkFrame sends all its CTk children
    `configure(bg_color=<its fill>)` (and a transparent frame sends
    "transparent"). `theme_recolor` recolours the parent BEFORE the child,
    so after switching the world Play <-> Work the line got the panel's
    background and vanished again - in screenshots 09/09b no line under the
    panel heading until the window was rebuilt. So every `bg_color` here is
    replaced with the line's fill (the new fill, if it came in the same
    call). A method of its own on the INSTANCE, not a subclass:
    `ctk.CTkFrame` can be replaced by a fake in tests."""
    povodne = getattr(ciara, "configure", None)
    if povodne is None:
        return

    def configure(require_redraw=False, **kw):
        if "fg_color" in kw:
            kw["bg_color"] = kw["fg_color"]
        elif "bg_color" in kw:
            kw["bg_color"] = getattr(ciara, "_fg_color", None) or kw["bg_color"]
        return povodne(require_redraw=require_redraw, **kw)

    try:
        ciara.configure = configure
    except Exception:
        pass


def stranka_scroll(master, pal):
    """A page's scrolling area with the shared look.

    `corner_radius=0` is not cosmetic: CTkScrollableFrame indents its
    content by its radius (6 px by default), so the cards in it started 6 px
    further in than the tab row and the bar above them - hence the "four
    left edges" from the audit. The caller packs it with
    `padx=PAGE_GUTTER`."""
    return ctk.CTkScrollableFrame(
        master, fg_color="transparent", corner_radius=0,
        scrollbar_button_color=pal["surface_alt"],
        scrollbar_button_hover_color=pal["accent"])


def switch(master, pal, text="", **kw):
    """The app's one and only switch.

    When on, the track is `accent`, when off `switch_off`; the knob is
    always light (`text`). Before 0.3 seven of the nine switches had the on
    track in `accent2` - against the off one that was a contrast of 1.07:1,
    so "Grounding" switched on looked exactly like off (reported in the
    audit). The other two had a gold track, so the app had two styles at
    once.

    Without text the switch is compact (36x18), as in the right column of a
    settings row; with text it has the CTk default size. Everything can be
    overridden via `kw`, except the state colours - those are a rule, not
    taste.
    """
    style = {
        "progress_color": pal["accent"],
        "fg_color": pal["switch_off"],
        "button_color": pal["text"],
        "button_hover_color": pal["accent_hover"],
        "text_color": pal["text_dim"],
        "font": ui(12),
    }
    if not text:
        style.update(width=40, switch_width=36, switch_height=18)
    style.update(kw)
    return ctk.CTkSwitch(master, text=text, **style)


def nastav_prepinac_aktivny(sw, pal, aktivny):
    """Greys out a switch that has nothing to control right now (e.g. the
    HUD icons while the heart-rate panel is off).

    `state="disabled"` in CTk greys out only the text - a gold "on" track
    would keep claiming "on and working". So the track and the knob are
    dimmed too."""
    try:
        if aktivny:
            sw.configure(state="normal", progress_color=pal["accent"],
                         button_color=pal["text"])
        else:
            sw.configure(state="disabled", progress_color=pal["control_border"],
                         button_color=pal["text_faint"])
    except Exception:
        pass


# Four button kinds. Previously every place put its colours together on its
# own, so "Export" had a fill, "Delete history" looked like "Import" and the
# "Record"/"File" border had a contrast of 1.11:1 - the buttons looked
# disabled.
BUTTON_KINDS = ("primary", "secondary", "quiet", "danger")
_BUTTON_PAD_X = 14          # inner text padding at natural width


def _sirka_textu(text, font):
    """Text width in LOGICAL px (a CTk font has its size in px, not points).

    Without a Tk root (tests) it returns an estimate - precision here is not
    about function, only looks."""
    try:
        family, size = font[0], font[1]
        weight = font[2] if len(font) > 2 else "normal"
        return tkfont.Font(family=family, size=-abs(int(size)),
                           weight=weight).measure(str(text))
    except Exception:
        return int(len(str(text)) * float(font[1]) * 0.6)


def button(master, pal, text, command=None, kind="secondary", width=None,
           height=30, font=None, fit_texts=(), **kw):
    """A button of one of the four kinds (`BUTTON_KINDS`).

      primary   - fill `accent`; at most one per card, it is "the main
                  thing you are here for",
      secondary - border `control_border` (>= 3:1), text `text`,
      quiet     - no border, text `text_dim` (helper actions),
      danger    - border and text in `danger_text` (delete, remove).

    `width=None` = NATURAL width by the text. A button stretched across the
    whole card (e.g. "How to pair your watch..." across ~1500 px) shouted
    louder than the card's content. The radius is the same as for the other
    controls (`RADIUS_CONTROL`), not its own.

    `fit_texts` = further texts the button will show later (the "Show IP" /
    "Hide IP" toggle): the natural width is taken from the longest, so the
    button does not jump when toggled.

    A DISABLED BUTTON (0.3 batch 4b) has one look for all kinds
    (`vzhlad_vypnuteho`): text `text_faint`, border `control_border`. With
    `state="disabled"` CTk greys out only the text - "Delete history" during
    watching kept its red border and looked enabled. The look switches on
    every `configure(state=...)` and comes back when enabled
    (`_drz_vzhlad_vypnuteho`), so the caller does not have to do anything
    else.
    """
    if kind not in BUTTON_KINDS:
        kind = "secondary"
    font = font or ui(12)
    style = _farby_druhu(kind, pal)
    style["text_color_disabled"] = pal["text_faint"]
    if width is None:
        width = max(_sirka_textu(t, font) for t in (text,) + tuple(fit_texts or ())) \
            + 2 * _BUTTON_PAD_X
    style.update(corner_radius=RADIUS_CONTROL, height=height, width=width, font=font)
    style.update(kw)
    vypnute = str(style.get("state", "")) == "disabled"
    style.pop("state", None)
    btn = ctk.CTkButton(master, text=text, command=command, **style)
    _drz_vzhlad_vypnuteho(btn, kind, pal)
    if vypnute:
        try:
            btn.configure(state="disabled")
        except Exception:
            pass
    return btn


def _farby_druhu(kind, pal):
    """Colours of an ENABLED button of kind `kind` (see `button`)."""
    if kind == "primary":
        return {"fg_color": pal["accent"], "hover_color": pal["accent_hover"],
                "text_color": pal["bg"], "border_width": 0}
    if kind == "danger":
        return {"fg_color": "transparent", "hover_color": pal["surface_alt"],
                "text_color": pal["danger_text"], "border_width": 1,
                "border_color": pal["danger_text"]}
    if kind == "quiet":
        return {"fg_color": "transparent", "hover_color": pal["surface_alt"],
                "text_color": pal["text_dim"], "border_width": 0}
    return {"fg_color": "transparent", "hover_color": pal["surface_alt"],
            "text_color": pal["text"], "border_width": 1,
            "border_color": pal["control_border"]}


# Text token of an enabled button - it tells which theme the button is in
# right now (`_paleta_podla_farby`), even if the world was switched since.
_TOKEN_TEXTU = {"primary": "bg", "secondary": "text", "quiet": "text_dim",
                "danger": "danger_text"}
_FARBY_TLACIDLA = ("fg_color", "hover_color", "text_color", "border_color")


def vzhlad_vypnuteho(kind, pal):
    """Colours of a DISABLED button - one look for all kinds.

    Text `text_faint` (>= 4.5:1, so you can read why it is there), border
    `control_border` for the kinds that have a border (`danger` too - a
    disabled "Delete" must not glow red), `primary` loses its gold fill. A
    disabled button has no hover; CTk takes care of that itself."""
    st = {"text_color": pal["text_faint"], "text_color_disabled": pal["text_faint"]}
    if kind == "primary":
        st["fg_color"] = pal["surface_alt"]
    if kind in ("secondary", "danger"):
        st["border_color"] = pal["control_border"]
    return st


def _paleta_podla_farby(farba, token):
    """Palette of the theme where `token` has the value `farba` (else None)."""
    farba = str(farba or "").lower()
    for paleta in theme_mod.THEMES.values():
        if str(paleta.get(token, "")).lower() == farba:
            return paleta
    return None


def _drz_vzhlad_vypnuteho(btn, kind, pal):
    """`configure(state=...)` on the button also switches its look.

    A method of its own on the INSTANCE (like `_drz_pozadie_linky`), not a
    subclass - `ctk.CTkButton` can be replaced by a fake in tests. When
    disabled, it remembers the colours the button has right now (including
    ones changed by the caller, e.g. Test during a test), and gives them back
    when enabled. If the theme was switched in the meantime (`theme_recolor`
    recolouring changes colours by value), the remembered colours are
    translated into the new theme. Colours the caller sends in the same call
    take precedence. Never raises an exception of its own."""
    povodne = getattr(btn, "configure", None)
    if povodne is None:
        return
    stav = {"zapnute": None, "pal": pal}

    def _cget(meno):
        try:
            return btn.cget(meno)
        except Exception:
            return None

    def _doplnok(kw):
        """Colours that need adding to `kw` (never the ones already in it)."""
        novy = str(kw.get("state", ""))
        vypnut = novy == "disabled"
        bolo_vypnute = stav["zapnute"] is not None
        if vypnut and not bolo_vypnute:
            aktualna = (_paleta_podla_farby(_cget("text_color"), _TOKEN_TEXTU[kind])
                        or stav["pal"])
            stav["zapnute"] = {k: _cget(k) for k in _FARBY_TLACIDLA}
            stav["pal"] = aktualna
            return vzhlad_vypnuteho(kind, aktualna)
        if novy == "normal" and bolo_vypnute:
            aktualna = (_paleta_podla_farby(_cget("text_color"), "text_faint")
                        or stav["pal"])
            zapnute, stav["zapnute"] = stav["zapnute"], None
            mapa = {}
            if aktualna is not stav["pal"]:
                import theme_recolor
                mapa = theme_recolor.build_color_map(stav["pal"], aktualna)
            stav["pal"] = aktualna
            von = {}
            for meno, farba in zapnute.items():
                if farba is None:
                    continue
                von[meno] = mapa.get(str(farba).lower(), farba) \
                    if isinstance(farba, str) else farba
            return von
        if bolo_vypnute and "text_color" in kw and "state" not in kw:
            # theme recolouring while disabled - the disabled-state text too
            return {"text_color_disabled": kw["text_color"]}
        return {}

    def configure(require_redraw=False, **kw):
        try:
            for meno, farba in _doplnok(kw).items():
                kw.setdefault(meno, farba)
        except Exception:
            pass
        if require_redraw:
            return povodne(require_redraw=True, **kw)
        return povodne(**kw)

    try:
        btn.configure = configure
    except Exception:
        pass


_MENU_CHROME_W = 56        # left text padding + arrow on the right + slack


def option_menu(master, pal, width=CONTROL_W, **kw):
    """A fixed-width dropdown (`CONTROL_W`), so that all of them in one column
    end at the same right edge - otherwise CTk inflates it by the text of
    the selected item and it would jump on every selection.

    Fixed, but not clipping: when one of the `values` is longer than fits
    into `width` (a long translation, a voice engine name), the width is set
    once by the longest - the text is never cut off and no longer jumps on
    selection. The right edge stays the same because the settings row keeps
    the control on the right."""
    font = kw.get("font") or ui(12)
    hodnoty = kw.get("values") or []
    min_width = width
    if hodnoty and not kw.get("dynamic_resizing"):
        width = sirka_menu(hodnoty, font, min_width)
    style = {
        "width": width, "height": 28, "corner_radius": RADIUS_CONTROL,
        "dynamic_resizing": False,
        "fg_color": pal["surface_alt"], "button_color": pal["accent2"],
        "button_hover_color": pal["accent2_hover"], "text_color": pal["text"],
        "dropdown_fg_color": pal["surface"], "dropdown_text_color": pal["text"],
        "dropdown_hover_color": pal["surface_alt"], "font": font,
    }
    style.update(kw)
    style["width"] = width
    menu = ctk.CTkOptionMenu(master, **style)
    try:
        menu._zanshin_menu = (font, min_width, bool(kw.get("dynamic_resizing")))
    except Exception:
        pass
    return menu


def sirka_menu(hodnoty, font, min_width=CONTROL_W):
    """Width of a dropdown that fits the longest of `hodnoty` (at least
    `min_width`) - the `option_menu` rule in one place."""
    try:
        najdlhsia = max(_sirka_textu(h, font) for h in hodnoty)
    except ValueError:
        return min_width
    return max(min_width, najdlhsia + _MENU_CHROME_W)


def nastav_hodnoty_menu(menu, values):
    """New items for a dropdown from `option_menu` - and a new width with them.

    `configure(values=...)` does not change the width: the voice choice is
    filled only after start (Windows voices, natural voices), so the
    dropdown stayed at the width of "Nacitavam..." (Loading...) and a long
    Windows voice name ("Microsoft Hedda Desktop - German (Germany)") got
    clipped. So the width is recomputed by the same rule as at build time
    (`sirka_menu`); never smaller than the original minimum. Never raises an
    exception."""
    values = list(values or [])
    try:
        font, min_width, dynamicka = getattr(menu, "_zanshin_menu", (ui(12), CONTROL_W, False))
        kw = {"values": values}
        if values and not dynamicka:
            kw["width"] = sirka_menu(values, font, min_width)
        menu.configure(**kw)
    except Exception:
        try:
            menu.configure(values=values)
        except Exception:
            pass


def oznac_zvoleny_segment(seg, pal):
    """The selected segment of a CTkSegmentedButton has its text in
    `accent_hover`, the others in `text_dim`.

    The fill of the selected segment (`accent2`) had a contrast of 1.15:1
    against an unselected one - in the "Play | Work" bar you could not see
    which world you were in. CTk cannot do text colour per segment, so it is
    set directly on the buttons (`_buttons_dict`, the same thing the bubble
    in `ui_shell.TitleBar` goes through). CTk's `set()` changes only the
    fill, so the text has to be redrawn after every `set()` and after a
    theme recolour. Never raises an exception."""
    try:
        zvolene = seg.get()
        for hodnota, tlacidlo in getattr(seg, "_buttons_dict", {}).items():
            tlacidlo.configure(text_color=pal["accent_hover"] if hodnota == zvolene
                               else pal["text_dim"])
    except Exception:
        pass


# --------------------------------------------------------------------------
# Panel
# --------------------------------------------------------------------------

class Panel(ctk.CTkFrame):
    """A panel with a header and a body.

    The difference from the original cards: the header has its own divider
    line and the body its own padding, so content can be poured into it
    without every place in the app padding it on its own (and differently
    each time).
    """

    def __init__(self, master, pal, title=None, right=None, **kw):
        kw.setdefault("fg_color", pal["surface"])
        kw.setdefault("corner_radius", RADIUS_PANEL)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", pal["line_soft"])
        super().__init__(master, **kw)
        self.pal = pal
        self.right_label = None

        # SPACING 8/16 (0.3, UX audit, batch 4): heading -> line -> body
        # had 9 + 14 px and the settings row below added its own 9, so there
        # were 23 px between the line and the first text - more than between
        # two panels. Now 8 px above the line and below it (+ the row padding).
        if title is not None:
            head = ctk.CTkFrame(self, fg_color="transparent", height=40)
            head.pack(fill="x", padx=16, pady=(11, 0))
            ctk.CTkLabel(head, text=title, font=ui(13, "bold"),
                         text_color=pal["text"]).pack(side="left")
            # The sentence on the right ("3 sessions", "Analysis from ...") is
            # prose, not a number in a table - monospace made it look like
            # console output.
            self.right_label = ctk.CTkLabel(head, text=right or "",
                                            font=ui(11), text_color=pal["text_dim"])
            self.right_label.pack(side="right")
            # `rule` (>= 1.5:1), not `line_soft` (1.11:1): a line you cannot
            # see only leaves an unexplained gap under the heading.
            rule = linka(self, pal)
            rule.pack(fill="x", pady=(8, 0))

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=16,
                       pady=(8 if title is not None else 14, 14))

    def set_right(self, text):
        if self.right_label is not None:
            try:
                self.right_label.configure(text=text)
            except Exception:
                pass


def priprav_popup(top):
    """A plain `tk.Toplevel` that CTk widgets are about to go into.

    CUSTOMTKINTER REGISTERS SUCH A WINDOW EVEN THOUGH IT IS NOT ITS OWN. It
    is enough to put a single CTk widget into it and `ScalingTracker` adds
    it to a list that it then walks periodically, calling
    `block_update_dimensions_event()` on it. That method exists only on
    `CTk`/`CTkToplevel`, so on a plain `tk.Toplevel` it fails with an
    AttributeError - in an `after` callback, so it does not bring the app
    down, it just quietly ends up in crash.log on every DPI change.

    We cannot use `CTkToplevel` here: it redraws itself with its own title
    bar and `overrideredirect` does not take it away. So we add those two
    methods - there is nothing to block, these windows set their size
    themselves and do not listen for size changes.

    Returns the same window so it can be called in a chain.
    """
    top.block_update_dimensions_event = lambda: None
    top.unblock_update_dimensions_event = lambda: None
    return top


def fit_popup(x, y, width, height, area, above_y, margin=8):
    """Position (x, y) of a popup such that it stays entirely within `area` =
    (x0, y0, x1, y1).

    Horizontally it is just pushed inwards. When it does not fit BELOW the
    anchor, it moves ABOVE it: `above_y` is the top edge of the anchor (the
    button) and the popup then ends 4 px above it - the same as ⓘ on a card
    (`StatCard._toggle_info`)."""
    x0, y0, x1, y1 = area
    x = max(x0 + margin, min(int(x), x1 - width - margin))
    if y + height > y1 - margin:
        y = max(y0 + margin, above_y - height - 4)
    return int(x), int(y)


def work_area(widget):
    """Work area (without the taskbar) of THE monitor the centre of `widget`
    is on - in virtual desktop coordinates, like winfo_rootx/rooty.

    Not `winfo_screenwidth/height`: that returns only the primary screen,
    so on a second monitor the popup would jump back to the first one."""
    try:
        cx = widget.winfo_rootx() + widget.winfo_width() // 2
        cy = widget.winfo_rooty() + widget.winfo_height() // 2
        for mon in display_mod.monitors(widget):
            if mon.contains(cx, cy):
                return (mon.work_x, mon.work_y,
                        mon.work_x + mon.work_width, mon.work_y + mon.work_height)
    except Exception:
        pass
    return (0, 0, widget.winfo_screenwidth(), widget.winfo_screenheight())


def _window_hwnd(window):
    try:
        import ctypes
        u = ctypes.windll.user32
        u.GetAncestor.restype = ctypes.c_void_p
        u.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        return u.GetAncestor(ctypes.c_void_p(int(window.winfo_id())), 2)  # GA_ROOT
    except Exception:
        return None


def pripni_k_vlastnikovi(top):
    """Windows: let the dialog BELONG to the main window - then it is always
    above it.

    On Windows, Tk drops the owner of borderless (overrideredirect) windows
    ("Parent must be desktop even if we have a transient parent" in
    tkWinWm.c), so `transient(root)` has no effect. The main window can
    then cover the dialog - on 24. 9. the after-session questionnaire stayed
    hidden behind the app and the player could not fill it in (the main
    window had WS_EX_TOPMOST).

    We set the owner directly (GWLP_HWNDPARENT). In Windows' window order an
    owned window is ALWAYS above its owner. If the owner is topmost, the
    dialog gets topmost too, so it always gets in front of it. Our own
    WinDLL handle - we do not change the argtypes of shared windll
    functions. Never raises an exception; returns True when the owner was
    set."""
    try:
        import ctypes
        master = getattr(top, "master", None)
        if master is None:
            return False
        dlg = _window_hwnd(top)
        own = _window_hwnd(master.winfo_toplevel())
        if not dlg or not own or int(dlg) == int(own):
            return False
        u = ctypes.WinDLL("user32")
        nastav = getattr(u, "SetWindowLongPtrW", None) or u.SetWindowLongW
        nastav.restype = ctypes.c_void_p
        nastav.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        nastav(ctypes.c_void_p(dlg), -8, ctypes.c_void_p(own))    # GWLP_HWNDPARENT
        u.GetWindowLongW.restype = ctypes.c_long
        u.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        if u.GetWindowLongW(ctypes.c_void_p(own), -20) & 0x00000008:   # WS_EX_TOPMOST
            top.attributes("-topmost", True)
        return True
    except Exception:
        return False


def freeze_repaint(window, frozen):
    """Freezes/unfreezes a window's drawing via WM_SETREDRAW.

    Used around a UI rebuild (language change -> the whole `_build_ui`) and
    around DPI rescaling (moving to a monitor with a different scale): the
    intermediate steps would otherwise show up as flicker/rebuilding. While
    frozen, Windows does not draw; after unfreezing, ONE clean redraw of the
    whole window is forced. The geometry (layout, scale) is recomputed
    normally in the meantime - WM_SETREDRAW blocks only DRAWING, not
    layout."""
    try:
        import ctypes
        h = _window_hwnd(window)
        if not h:
            return
        u = ctypes.windll.user32
        u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                   ctypes.c_void_p, ctypes.c_void_p]
        u.SendMessageW(h, 0x000B, 1 if not frozen else 0, 0)   # WM_SETREDRAW
        if not frozen:
            u.RedrawWindow.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                       ctypes.c_void_p, ctypes.c_uint]
            # RDW_INVALIDATE | RDW_ERASE | RDW_ALLCHILDREN | RDW_UPDATENOW
            u.RedrawWindow(h, None, None, 0x0001 | 0x0004 | 0x0080 | 0x0100)
    except Exception:
        pass


# DWM "cloak" (Windows 8+). For Windows a cloaked window is SHOWN - it gets
# WM_PAINT and Tk draws it normally -, only DWM does not let it onto the
# screen. That is exactly what is needed at start: the window shows only
# once it is fully drawn, all at once.
_DWMWA_CLOAK = 13      # write: 1 = cloak, 0 = uncloak
_DWMWA_CLOAKED = 14    # read: non-zero = window is cloaked (by the app/shell)
_dwmapi = None


def _dwm():
    """Our own handle to dwmapi.dll, NOT the shared `ctypes.windll.dwmapi`.

    CustomTkinter calls the same `DwmSetWindowAttribute` via `windll` (the
    dark title bar in ctk_tk.py) without `argtypes`. If we set them on the
    shared object, we would change the libraries' call path. `WinDLL` has
    its own function objects, so nobody else sees our `argtypes`."""
    global _dwmapi
    if _dwmapi is None:
        import ctypes
        lib = ctypes.WinDLL("dwmapi")
        for meno in ("DwmSetWindowAttribute", "DwmGetWindowAttribute"):
            fn = getattr(lib, meno)
            fn.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                           ctypes.c_void_p, ctypes.c_uint]
            fn.restype = ctypes.c_long            # HRESULT, 0 = S_OK
        _dwmapi = lib
    return _dwmapi


def zahal_okno(window, zahalit):
    """Cloaks (`zahalit=True`) or uncloaks a window via DWM (DWMWA_CLOAK).

    Unlike `withdraw()`, the window is still drawn normally, it just cannot
    be seen. Returns True when Windows accepted it; otherwise False and
    nothing happens - the window behaves as before. Never raises an
    exception (best effort, like `freeze_repaint`).

    WARNING: it applies to the HWND of the window's wrapper.
    `overrideredirect(False)` (e.g. minimising the borderless window in
    `ui_shell.TitleBar`) makes Tk create the wrapper again, and the NEW
    window is not cloaked - so it shows. That is the safe side (the window
    never stays invisible); do not fix it by cloaking the old handle
    again."""
    try:
        import ctypes
        h = _window_hwnd(window)
        if not h:
            return False
        hodnota = ctypes.c_int(1 if zahalit else 0)
        return _dwm().DwmSetWindowAttribute(
            h, _DWMWA_CLOAK, ctypes.byref(hodnota), ctypes.sizeof(hodnota)) == 0
    except Exception:
        return False


def je_zahalene(window):
    """Is the window cloaked right now (DWMWA_CLOAKED)? False on any error.

    For harnesses: a cloaked window still has `winfo_viewable()` True, so
    judging by Tk alone an "invisible" app would pass every check."""
    try:
        import ctypes
        h = _window_hwnd(window)
        if not h:
            return False
        stav = ctypes.c_uint(0)
        hr = _dwm().DwmGetWindowAttribute(
            h, _DWMWA_CLOAKED, ctypes.byref(stav), ctypes.sizeof(stav))
        return hr == 0 and stav.value != 0
    except Exception:
        return False


def potlac_dpi_alpha_blik(window):
    """Prevents both the "ghost" and the window rebuild when moving between
    monitors.

    On a DPI change (even when the window just moves to a monitor with a
    different scale) CUSTOMTKINTER dims the window to `-alpha 0.15`,
    recomputes the scale and sets it back to 1 - to hide the rebuild DURING
    the rescaling. But while moving it fires again and again, and the result
    is a see-through "ghost"/flicker (exactly what a player reported).

    Those two alpha calls, however, are exactly the BOUNDARIES of the
    rescaling. Instead of dimming to 0.15 (ghost) we FREEZE/UNFREEZE drawing
    on them (`freeze_repaint`): the window stays opaque (no ghost) and the
    rebuild during rescaling does not show (no flicker). An `after` safety
    net unfreezes even if the second call never comes (an exception in
    CTk), so the window never stays frozen. A query
    (`attributes('-alpha')`) and other attributes pass through."""
    try:
        orig = window.wm_attributes
    except Exception:
        return window

    def _wrap(*args):
        if len(args) >= 2 and str(args[0]) in ("-alpha", "alpha"):
            try:
                a = float(args[1])
            except (TypeError, ValueError):
                return orig(*args)
            if a < 1.0:
                freeze_repaint(window, True)
                try:
                    window.after(160, lambda: freeze_repaint(window, False))
                except Exception:
                    pass
            else:
                freeze_repaint(window, False)
            return          # we never change the alpha itself (no ghost)
        return orig(*args)

    window.wm_attributes = _wrap
    window.attributes = _wrap
    return window


# --------------------------------------------------------------------------
# A fixed-size window on a monitor: scale and centre
# --------------------------------------------------------------------------
#
# How CTk computes sizes (checked in customtkinter/.../scaling_tracker.py):
#
#   physical window size = logical * monitor DPI * ScalingTracker.window_scaling
#   physical widget size = logical * monitor DPI * ScalingTracker.widget_scaling
#
# `window_scaling` and `widget_scaling` are ONE value for the whole app (a
# class attribute, not per window) and `ctk.set_*_scaling(x)` OVERWRITES it,
# it does not multiply. CTk keeps DPI per window (`window_dpi_scaling_dict`)
# and every 100 ms checks whether the window has moved to a monitor with a
# different DPI.
#
# So shrinking the app means multiplying BOTH values by the same factor: if
# only the window shrank, content designed for 1180x760 would spill out of it.


def _ctk_tracker():
    """`ScalingTracker` from customtkinter. A separate function so that tests
    can replace it - the real tracker is global state of the whole process."""
    from customtkinter.windows.widgets.scaling.scaling_tracker import ScalingTracker
    return ScalingTracker


def dpi_mierka_monitora(mon):
    """The DPI part of the CTk scale on monitor `mon` (without the app scale).

    On old Windows (before 8.1) CTk does not track DPI at all and multiplies
    only by the app scale - then the DPI part is 1.0, whatever the monitor
    reports."""
    try:
        if _ctk_tracker().deactivate_automatic_dpi_awareness:
            return 1.0
    except Exception:
        pass
    return display_mod.dpi_scale(mon)


def zosuladi_dpi_s_monitorom(window, mon):
    """Sets the CTk window scale to the DPI of monitor `mon` RIGHT AWAY, not
    100 ms later.

    Tk creates the window where Windows puts it (usually the main monitor),
    and CTk remembers the DPI from there. When we then immediately move the
    window to a monitor with a different scale, CTk only finds out at the
    next check - after `_build_ui`, i.e. over more than a thousand finished
    widgets, which it would all rebuild in front of the player. While the
    window is empty, the rescaling is cheap.

    If the window ends up elsewhere after all, CTk fixes it itself as
    before. Returns True when the scale changed. Never raises an
    exception."""
    try:
        st = _ctk_tracker()
        if st.deactivate_automatic_dpi_awareness:
            return False
        if window not in st.window_dpi_scaling_dict:
            return False
        nova = dpi_mierka_monitora(mon)
        if abs(float(st.window_dpi_scaling_dict[window]) - nova) < 1e-6:
            return False
        st.window_dpi_scaling_dict[window] = nova
        st.update_scaling_callbacks_for_window(window)
        return True
    except Exception:
        return False


def prisposob_mierku_monitoru(width, height, mon):
    """Shrinks the whole app if a `width` x `height` window (logical px) does
    not fit into the work area of monitor `mon`. Returns the factor used
    (1.0 = nothing changed).

    Call it BEFORE building the UI: on a scale change CTk rebuilds every
    widget, and while there are none, it costs nothing. The factor is
    computed from the scale the app already has, so a second call does not
    shrink the app once more - the window already fits. The change applies
    to the whole app (dialogs too), not just one window."""
    try:
        st = _ctk_tracker()
        okna = float(st.window_scaling or 1.0)
        prvky = float(st.widget_scaling or 1.0)
        faktor = display_mod.window_fit_factor(
            width, height, dpi_mierka_monitora(mon) * okna,
            mon.work_width, mon.work_height)
        if faktor < 1.0:
            st.set_widget_scaling(prvky * faktor)
            st.set_window_scaling(okna * faktor)
        return faktor
    except Exception:
        return 1.0


def vycentrovana_geometria(window, width, height, mon=None):
    """Geometry "WxH+x+y" of a window centred in a monitor's work area.

    Nobody places a borderless window (the OS does not manage it), and in
    `geometry()` CTk multiplies only the WIDTH and HEIGHT by the scale, not
    the position - so the centre is computed from the physical size on the
    TARGET monitor (its DPI, not the DPI of the monitor the window is on
    now). `mon=None` = the monitor under the cursor: that is where the user
    is looking right now. When the window does not fit, it sticks to the
    top (see `display.center_in_work_area`). On any error it returns only
    the size.
    """
    try:
        if mon is None:
            mon = display_mod.monitor_at_cursor(window)
        try:
            okna = float(_ctk_tracker().window_scaling or 1.0)
        except Exception:
            okna = 1.0
        mierka = dpi_mierka_monitora(mon) * okna
        x, y = display_mod.center_in_work_area(
            mon, round(width * mierka), round(height * mierka))
        return f"{width}x{height}+{x}+{y}"
    except Exception:
        return f"{width}x{height}"


def umiestni_pevne_okno(window, width, height, mon=None):
    """Puts a fixed app window on screen: monitor, scale, centre - in this
    order.

    1. the monitor under the cursor (the same one the first-start guide
       shows up on),
    2. the CTk window scale by the DPI of THAT monitor
       (`zosuladi_dpi_s_monitorom`),
    3. if the window does not fit into the work area, the whole app shrinks
       (`prisposob_mierku_monitoru`),
    4. the window is centred in the work area.

    Where the window fits (1080p at 100 %, 1440p, 4K at 150 %...), the scale
    stays exactly as before. The caller sets `minsize`/`maxsize`. Returns
    (factor, monitor); the monitor is None if it could not be determined."""
    if mon is None:
        try:
            mon = display_mod.monitor_at_cursor(window)
        except Exception:
            mon = None
    if mon is None:
        window.geometry(f"{width}x{height}")
        return 1.0, None
    zosuladi_dpi_s_monitorom(window, mon)
    faktor = prisposob_mierku_monitoru(width, height, mon)
    window.geometry(vycentrovana_geometria(window, width, height, mon))
    return faktor, mon


def rozmer_dialogu(window, width, height, mon=None):
    """(width, height, monitor) of a dialog in LOGICAL px, shrunk so that the
    whole window fits into the work area of monitor `mon` (with the margin
    `display.WINDOW_FIT_MARGIN_PX`).

    The main window fits thanks to shrinking the whole app
    (`prisposob_mierku_monitoru`), but that stops at 70 %. On 1366x768 at
    125-150 % a 640 px tall dialog is taller than the area even after
    shrinking, and its bottom with the Close button ended up under the
    taskbar - in a borderless window that cannot be shrunk by dragging its
    edge. So the dialog here would rather stay shorter; the content has a
    scrollbar, the footer with the buttons stays visible. On any error it
    returns the size unchanged and the monitor None."""
    try:
        if mon is None:
            mon = display_mod.monitor_at_cursor(window)
        try:
            okna = float(_ctk_tracker().window_scaling or 1.0)
        except Exception:
            okna = 1.0
        mierka = dpi_mierka_monitora(mon) * okna
        if not mierka > 0:
            mierka = 1.0
        okraj = display_mod.WINDOW_FIT_MARGIN_PX
        max_w = int((mon.work_width - okraj) / mierka)
        max_h = int((mon.work_height - okraj) / mierka)
        return max(1, min(int(width), max_w)), max(1, min(int(height), max_h)), mon
    except Exception:
        return int(width), int(height), None


def umiestni_dialog(top, owner, width, height, min_width=None, min_height=None):
    """A borderless dialog (DialogChrome) in the centre of the work area and
    entirely on it.

    The OS neither places nor shrinks a borderless window: without a
    position it opened in the corner of the screen, and when taller than the
    area it had its buttons outside it. `rozmer_dialogu` shrinks the size,
    `vycentrovana_geometria` computes the centre (the same calculation as
    for the main window and the guide). `minsize` is never bigger than the
    size that fits on the area - otherwise Tk would stretch it back over the
    edge. Returns (width, height) in logical px."""
    w, h, mon = rozmer_dialogu(owner, width, height)
    try:
        top._zanshin_umiestnene = True      # DialogChrome no longer moves it
    except Exception:
        pass
    try:
        if min_width or min_height:
            top.minsize(min(int(min_width or w), w), min(int(min_height or h), h))
        if mon is not None:
            top.geometry(vycentrovana_geometria(owner, w, h, mon))
        else:
            top.geometry(f"{w}x{h}")
    except Exception:
        pass
    return w, h


def vycentruj_podla_obsahu(top, owner=None):
    """Moves a dialog that sizes itself by its content (no fixed geometry) to
    the centre of the work area of the monitor under the cursor.

    Tk puts a borderless window without a position into the top left corner
    - with two monitors even on a different one than the user is on. The
    size is left as the content asked for; only the position changes (CTk
    does not scale it)."""
    try:
        top.update_idletasks()
        sirka = max(top.winfo_reqwidth(), top.winfo_width())
        vyska = max(top.winfo_reqheight(), top.winfo_height())
        mon = display_mod.monitor_at_cursor(owner or top)
        x, y = display_mod.center_in_work_area(mon, sirka, vyska)
        top.geometry(f"+{x}+{y}")
    except Exception:
        pass


class Collapsible(ctk.CTkFrame):
    """A panel that can be collapsed. From outside it behaves like `Panel` -
    it has a `.body` that content is poured into, so it can directly
    replace a `Panel`.

    WHY IT EXISTS: the app had three places where something expands (the
    Guide cards, the cue card, the settings sections), and each wrote it on
    its own. Three implementations mean three different arrow widths, three
    different paddings and three places where you can forget to flip the
    arrow back.

    It starts COLLAPSED. A section that opens by itself is not collapsed -
    it is just a panel with a decorative arrow.
    """

    SIPKA_ZAVRETA = "▸"    # >
    SIPKA_OTVORENA = "▾"   # v

    def __init__(self, master, pal, title, expanded=False, **kw):
        kw.setdefault("fg_color", pal["surface"])
        kw.setdefault("corner_radius", RADIUS_PANEL)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", pal["line_soft"])
        super().__init__(master, **kw)
        self.pal = pal
        self._title = title
        self._expanded = bool(expanded)

        self.header = ctk.CTkButton(
            self, text=self._header_text(), anchor="w", height=34,
            corner_radius=RADIUS_PANEL, fg_color="transparent",
            hover_color=pal["surface_alt"], text_color=pal["text"],
            font=ui(13, "bold"), command=self.toggle)
        self.header.pack(fill="x", padx=6, pady=6)

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        if self._expanded:
            self._pack_body()

    def _header_text(self):
        sipka = self.SIPKA_OTVORENA if self._expanded else self.SIPKA_ZAVRETA
        return f"{sipka}   {self._title}"

    def _pack_body(self):
        self.body.pack(fill="both", expand=True, padx=16, pady=(0, 14))

    @property
    def expanded(self):
        return self._expanded

    def toggle(self, _event=None):
        self._expanded = not self._expanded
        if self._expanded:
            self._pack_body()
        else:
            self.body.pack_forget()
        self._apply_header_color()

    def _apply_header_color(self):
        self.header.configure(
            text=self._header_text(),
            text_color=self.pal["accent"] if self._expanded else self.pal["text"])

    def set_pal(self, pal):
        """Recolours the header on a theme change.

        `theme_recolor.recolor_tree` rewrites colours by VALUE, but the
        header colour here is computed from `self.pal` only at the moment of
        expanding - after a theme switch an expanded section would glow
        with the accent of the old palette. The rest of the content is plain
        CTk widgets, the tree handles those by itself.
        """
        self.pal = pal
        try:
            self.configure(fg_color=pal["surface"], border_color=pal["line_soft"])
            self.header.configure(hover_color=pal["surface_alt"])
            self._apply_header_color()
        except Exception:
            pass


class SlotIcon(ctk.CTkLabel):
    """Pictogram of a visual (grounding / jaw / release / breath ...) drawn
    with the same brush that draws the game (`hud_paint.render_slot_icon`).

    It is an IMAGE with the colour baked in, so `theme_recolor` does not
    recolour it on a theme change - `set_pal` draws it again (called by
    `DandurfApp._recolor_ui`). Without that, gold icons would remain in an
    indigo window after switching the world."""

    def __init__(self, master, pal, name, size=26):
        super().__init__(master, text="", width=size, height=size)
        self._name = name
        self._size = size
        self._photo = None
        self.set_pal(pal)

    def set_pal(self, pal):
        try:
            import hud_paint      # lazy: ui_kit is also imported without a GUI
            img = hud_paint.render_slot_icon(self._name, self._size,
                                             hud_paint.Style(pal))
            self._photo = ctk.CTkImage(light_image=img, dark_image=img,
                                       size=(self._size, self._size))
            self.configure(image=self._photo)
        except Exception:
            pass


def bez_ikony(text):
    """Strips the leading symbol: "🥾 Tazisko (drep/slide)" -> "Tazisko ...".

    The visual names in the translations carry emoji (🥾 💀 🖱️ 🫁). Next to
    the picture the app draws itself (`hud_paint.render_slot_icon`), the
    emoji were a third icon style in a quiet interface - and the skull by
    the jaw the loudest symbol in the whole app. The first "token" is
    removed only when it contains no letter or digit, so a text without
    emoji stays whole (even if a translation loses its emoji one day, the
    name is not cut off)."""
    text = str(text or "")
    prvy, medzera, zvysok = text.partition(" ")
    # Only a non-ASCII symbol (emoji, pictogram) - "+ New" keeps its plus.
    if (medzera and zvysok.strip() and prvy
            and not any(ch.isalnum() for ch in prvy)
            and any(ord(ch) > 0x2000 for ch in prvy)):
        return zvysok.strip()
    return text


def dlzka_text(seconds, preklad=None):
    """Length "45 min" or "2 h 05 min" in the app language; a broken value
    -> "—". One source for the "Session length" card, the session detail
    in History (`HistoryMixin._fmt_dlzka`) and the end of the session trace
    axis.

    `preklad` = a custom `tr` function (the in-game HUD writes in the game
    language, `_game_text`); without it, the app language."""
    try:
        total_min = int(max(0.0, float(seconds or 0.0)) // 60)
    except (TypeError, ValueError, OverflowError):
        return "—"
    if preklad is None:
        from i18n import tr as preklad
    hodiny, minuty = divmod(total_min, 60)
    if hodiny:
        return preklad("dashboard.fmt.h_min", h=hodiny, m=f"{minuty:02d}")
    return preklad("dashboard.fmt.min", n=minuty)


# From one hour up, time is written as a duration ("1 h 15 min"), not m:ss -
# "75:12" looked like a time on a clock (0.3, UX audit). The same threshold
# applies to the end of the session trace axis (`SessionTrace.OS_DLZKA_OD_S`).
DLZKA_OD_S = 3600


def cas_text(seconds, preklad=None):
    """Time "m:ss" under an hour, from one hour on "1 h 15 min" (`dlzka_text`).

    For "Over the limit" (Today, History, the in-game panel) and the session
    time above the trace - the same as the trace axis. A broken value ->
    "—"."""
    try:
        total = int(max(0.0, float(seconds or 0.0)))
    except (TypeError, ValueError, OverflowError):
        return "—"
    if total >= DLZKA_OD_S:
        return dlzka_text(total, preklad)
    return f"{total // 60}:{total % 60:02d}"


# --------------------------------------------------------------------------
# The date in the app language (0.3 batch 4b)
# --------------------------------------------------------------------------
#
# "%d.%m.%Y" is not a date in every language: an English speaker reads
# "12.11.2026" as 11 December, and a Japanese speaker does not write it that
# way at all. Each language has one form (with year / without year); the
# month abbreviations are the same as above the Consistency grid
# (`history.grid_months`) - one source. The time stays HH:MM, the exported
# file name ISO (`zanshin-relacie-2026-11-12.csv`).
# {d} day, {dd} day with a leading zero, {m}/{mm} month, {mes} month
# abbreviation, {r} year.
_TVAR_DATUMU = {
    "sk": ("{d}. {m}. {r}", "{d}. {m}."),
    "cs": ("{d}. {m}. {r}", "{d}. {m}."),
    "de": ("{dd}.{mm}.{r}", "{dd}.{mm}."),
    "ru": ("{dd}.{mm}.{r}", "{dd}.{mm}"),
    "bg": ("{dd}.{mm}.{r}", "{dd}.{mm}"),
    "en": ("{d} {mes} {r}", "{d} {mes}"),
    "fr": ("{d} {mes} {r}", "{d} {mes}"),
    "es": ("{d} {mes} {r}", "{d} {mes}"),
    "pt": ("{d} {mes} {r}", "{d} {mes}"),
    "ja": ("{r}年{m}月{d}日", "{m}月{d}日"),
    "zh": ("{r}年{m}月{d}日", "{m}月{d}日"),
}
_TVAR_MESIACA = {"ja": "{r}年{m}月", "zh": "{r}年{m}月", "de": "{mes} {r}",
                 "ru": "{mm}.{r}", "bg": "{mm}.{r}"}


def _jazyk_appky():
    try:
        import i18n
        return i18n._lang.get("code", "sk")
    except Exception:
        return "sk"


def _cast_datumu(ts):
    """time.struct_time from the time `ts` (seconds), or None if invalid."""
    try:
        return time.localtime(float(ts))
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _mesiac_skratka(mesiac, jazyk):
    try:
        from i18n import tr_lang
        mena = tr_lang(jazyk, "history.grid_months").split()
        if len(mena) == 12:
            return mena[mesiac - 1]
    except Exception:
        pass
    return str(mesiac)


def _vypln_tvar(tvar, t, jazyk):
    return tvar.format(d=t.tm_mday, dd=f"{t.tm_mday:02d}", m=t.tm_mon,
                       mm=f"{t.tm_mon:02d}", r=t.tm_year,
                       mes=_mesiac_skratka(t.tm_mon, jazyk) if "{mes}" in tvar else "")


def datum_text(ts, rok=True, cas=False, jazyk=None):
    """Session date in the app language: sk "12. 11. 2026", de "12.11.2026",
    en "12 Nov 2026", fr "12 nov. 2026", ja "2026年11月12日".

    `rok=False` - short form ("12. 11.", "12 Nov", "11月12日"),
    `cas=True` - " HH:MM" after the date. A broken time -> "—"."""
    t = _cast_datumu(ts)
    if t is None:
        return "—"
    jazyk = jazyk or _jazyk_appky()
    tvar = _TVAR_DATUMU.get(jazyk, _TVAR_DATUMU["en"])[0 if rok else 1]
    text = _vypln_tvar(tvar, t, jazyk)
    if cas:
        text += f" {t.tm_hour:02d}:{t.tm_min:02d}"
    return text


def mesiac_text(ts, jazyk=None):
    """Month and year ("nov 2026", "Nov 2026", "2026年11月") - the label of a
    monthly column in the trend chart."""
    t = _cast_datumu(ts)
    if t is None:
        return "—"
    jazyk = jazyk or _jazyk_appky()
    return _vypln_tvar(_TVAR_MESIACA.get(jazyk, "{mes} {r}"), t, jazyk)


# --------------------------------------------------------------------------
# Wrapping Japanese and Chinese (kinsoku, 0.3 batch 4b)
# --------------------------------------------------------------------------
#
# Tk wraps only at spaces; text without spaces (ja/zh) it breaks ANYWHERE -
# a line then started with 「。」 or 「）」, which is an error in Japanese
# typesetting. `zalom_kinsoku` breaks the text itself: a line does not start
# with a closing character, punctuation or a small kana, and does not end
# with an opening bracket (the character then moves to the next line, it
# never sticks out - Tk would otherwise break it again). Latin words in the
# text are not split.
_KINSOKU_ZACIATOK = frozenset(
    "、。，．・：；？！ー）」』】〕〉》〙〗｝］〟"
    "ぁぃぅぇぉっゃゅょゎゕゖァィゥェォッャュョヮヵヶㇰㇱㇲㇳㇴㇵㇶㇷㇸㇹㇺㇻㇼㇽㇾㇿ々〻"
    "゛゜ゝゞヽヾ〜～…‥%,.!?:;)]}"
    # Chinese puts names in “…” (not 「…」): the closing ” must not start a
    # line, the opening “ must not end it (`_KINSOKU_KONIEC`)
    "”’")
_KINSOKU_KONIEC = frozenset("（「『【〔〈《〘〖｛［〝([{“‘")


def _cjk_znak(ch):
    o = ord(ch)
    return (0x3000 <= o <= 0x30FF or 0x31F0 <= o <= 0x31FF or 0x3400 <= o <= 0x9FFF
            or 0xF900 <= o <= 0xFAFF or 0xFF00 <= o <= 0xFFEF)


def _tokeny_zlomu(riadok):
    """Pieces between which a break is allowed: every CJK character, every
    space and a whole Latin word."""
    tokeny, slovo = [], ""
    for ch in riadok:
        if ch == " " or _cjk_znak(ch):
            if slovo:
                tokeny.append(slovo)
                slovo = ""
            tokeny.append(ch)
        else:
            slovo += ch
    if slovo:
        tokeny.append(slovo)
    return tokeny


def zalom_kinsoku(text, sirka, zmeraj):
    """`text` with line breaks ("\\n") such that no line is wider than `sirka`
    (in the units of the function `zmeraj(retazec) -> sirka`) and kinsoku
    is respected (see above). Text without CJK characters is returned
    unchanged - Tk wraps Latin text correctly at spaces. Existing breaks
    stay."""
    text = "" if text is None else str(text)
    if not text or not sirka or sirka <= 0 or not any(_cjk_znak(c) for c in text):
        return text
    von = []
    for odsek in text.split("\n"):
        tokeny = _tokeny_zlomu(odsek)
        n, start, i = len(tokeny), 0, 0
        while i < n:
            if i > start and zmeraj("".join(tokeny[start:i + 1]).rstrip()) > sirka:
                zlom = i
                while zlom - start > 1 and (tokeny[zlom][0] in _KINSOKU_ZACIATOK
                                            or tokeny[zlom - 1][-1] in _KINSOKU_KONIEC):
                    zlom -= 1
                von.append("".join(tokeny[start:zlom]).rstrip())
                start = zlom
                while start < n and tokeny[start] == " ":
                    start += 1
                i = start
                continue
            i += 1
        von.append("".join(tokeny[start:]).rstrip())
    return "\n".join(von)


def _merac_pisma(font):
    """`zmeraj(retazec) -> px` for a label's font (tuple or CTkFont) in
    LOGICAL px - the same ones as `wraplength` (CTk multiplies both by the
    same scale). Without Tk (tests), an estimate from the font size."""
    try:
        if isinstance(font, (tuple, list)):
            family, size = font[0], font[1]
            weight = font[2] if len(font) > 2 else "normal"
        else:
            family, size, weight = font.cget("family"), font.cget("size"), font.cget("weight")
        return tkfont.Font(family=family, size=-abs(int(size)), weight=weight).measure
    except Exception:
        try:
            velkost = float(font[1])
        except Exception:
            velkost = 12.0

        def zmeraj(s):
            return sum(velkost if _cjk_znak(c) else velkost * 0.55 for c in s)
        return zmeraj


def _kinsoku_labelu(label):
    """A CTkLabel with `wraplength` in Japanese/Chinese shows the text broken
    by kinsoku (`zalom_kinsoku`), 2 % under `wraplength`, so that Tk does
    not break it again.

    Only the inner tk.Label gets the breaks - the CTkLabel's `_text` stays
    the original, so `cget("text")` returns exactly what the caller sent.
    Other languages, and a label without `wraplength` or with
    `textvariable`, do not change. Never raises an exception."""
    try:
        if not _jazyk_pisma():
            return
        text, wrap = getattr(label, "_text", None), getattr(label, "_wraplength", 0)
        if not isinstance(text, str) or not text or not wrap:
            return
        zlomeny = zalom_kinsoku(text, float(wrap) * 0.98, _merac_pisma(label._font))
        if zlomeny != text:
            label._label.configure(text=zlomeny)
    except Exception:
        pass


def zapni_kinsoku_v_labeloch(trieda=None):
    """Every CTkLabel with `wraplength` breaks ja/zh text by kinsoku - when
    built and on `configure(text= / wraplength= / font=)`.

    There are over a hundred labels with `wraplength` in the app (Settings,
    dialogs, Guide, History); adjusting each one separately would mean a
    hundred places where it can be forgotten. So one hook on the class, once
    when `ui_kit` is imported (calling it again does nothing). Latin and
    Cyrillic are left alone - Tk wraps those correctly at spaces."""
    trieda = trieda or ctk.CTkLabel
    if getattr(trieda, "_zanshin_kinsoku", False):
        return
    povodny_init, povodny_configure = trieda.__init__, trieda.configure

    def __init__(self, *args, **kwargs):
        povodny_init(self, *args, **kwargs)
        _kinsoku_labelu(self)

    def configure(self, require_redraw=False, **kwargs):
        zmena = bool(kwargs.keys() & {"text", "wraplength", "font"})
        vysledok = povodny_configure(self, require_redraw=require_redraw, **kwargs)
        if zmena:
            _kinsoku_labelu(self)
        return vysledok

    trieda.__init__ = __init__
    trieda.configure = configure
    trieda._zanshin_kinsoku = True


try:
    zapni_kinsoku_v_labeloch()
except Exception:              # pragma: no cover - fake ctk without CTkLabel
    pass


class SettingRow(ctk.CTkFrame):
    """A settings row: the name, the explanation under it, the control on the
    right.

    The explanation is part of the row, not a tooltip - a setting that only
    gets explained once you find the question mark is a setting nobody
    turns on.

    `icon` (optional) goes into a FIXED-width column before the name - every
    emoji has a different width, so the name in the text "🖱️ Uvolnenie"
    (Release) started somewhere else than "🥾 Tazisko" (Grounding) (reported
    as "switch off the axis"). The same principle as the side menu
    (_NavRow).

    `note` (optional) is a small, quieter footnote under the WHOLE row -
    under the name and under the control, still above the divider line. It
    is for a sentence that belongs to the choice but is not its description
    (e.g. the sentence about translations under the language choice).
    """

    ICON_W = 40      # even wider emoji (🖱️ with a variation selector) fit

    def __init__(self, master, pal, title, sub=None, wrap=430, icon=None,
                 note=None, note_wrap=560, icon_slot=None):
        super().__init__(master, fg_color="transparent")
        self.pack(fill="x")
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="x", pady=9)

        self.control = ctk.CTkFrame(inner, fg_color="transparent")
        self.control.pack(side="right", padx=(14, 0))

        # `icon_slot` (the visual's name) takes precedence over a text icon:
        # the image from `hud_paint` is what the player sees in game - emoji
        # not.
        if icon_slot:
            ikona_wrap = ctk.CTkFrame(inner, fg_color="transparent",
                                      width=self.ICON_W, height=26)
            ikona_wrap.pack(side="left")
            ikona_wrap.pack_propagate(False)
            self.icon = SlotIcon(ikona_wrap, pal, icon_slot, size=26)
            self.icon.pack(side="left")
        elif icon:
            self.icon = ctk.CTkLabel(inner, text=icon, width=self.ICON_W, anchor="w",
                                     font=ui(13), text_color=pal["text"])
            self.icon.pack(side="left")
        text_col = ctk.CTkFrame(inner, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True)
        # The text column is public (0.3 batch 4b): a state that belongs to
        # the row (voice preparation under "Voice source") goes UNDER the
        # explanation - still above the row's divider line, not below it into
        # the next row.
        self.text_col = text_col
        self.title_label = ctk.CTkLabel(text_col, text=title, font=ui(13),
                                        text_color=pal["text"], anchor="w", justify="left")
        self.title_label.pack(fill="x")
        # We keep the sentence so it can be rewritten when what it describes
        # changes (the sound preview follows the cue style).
        self.sub_label = None
        if sub:
            # The explanation is CONTENT (why and what it does), not decoration
            # - hence `text_dim` (5.75:1), not `text_faint`. In ja/zh kinsoku
            # breaks it (`zapni_kinsoku_v_labeloch`) - Tk would start a line
            # with 「。」.
            self.sub_label = ctk.CTkLabel(
                text_col, text=sub, font=ui(11), text_color=pal["text_dim"],
                anchor="w", justify="left", wraplength=wrap)
            self.sub_label.pack(fill="x", pady=(2, 0))

        self.note_label = None
        if note:
            self.note_label = ctk.CTkLabel(
                self, text=note, font=ui(10), text_color=pal["text_faint"],
                anchor="w", justify="left", wraplength=note_wrap)
            self.note_label.pack(fill="x", pady=(0, 9))

        # The divider line is BETWEEN rows, not under the last one (0.3, UX
        # audit, batch 4): under a panel's last row it lay ~13 px above the
        # panel's border - two lines right on top of each other. Whether a row
        # is the last one is only known once the whole panel is built.
        # `after_idle` alone was not enough: a dropdown in the NEXT row calls
        # `update_idletasks` while being built, so the check ran before the
        # next row existed, and the lines vanished between rows too. So it is
        # recomputed on every size change of the parent (a row added = the
        # parent grows) - `obnov_linky`.
        self.deliaca_linka = linka(self, pal)
        self.deliaca_linka.pack(fill="x")
        self._linka_vidno = True
        master = self.master
        try:
            if not getattr(master, "_zanshin_linky_riadkov", False):
                master._zanshin_linky_riadkov = True
                # `tk.Misc.bind` directly on the frame (CTk `bind` would put it
                # on the inner canvas) and "+" - CTk has its own <Configure>
                # there.
                tk.Misc.bind(master, "<Configure>",
                             lambda _e, m=master: SettingRow.obnov_linky(m), "+")
            self.after_idle(lambda m=master: SettingRow.obnov_linky(m))
        except Exception:
            pass

    @staticmethod
    def obnov_linky(master):
        """A line under every settings row in `master` except the last one.

        The last row of its parent has no line under it. A row that is
        still followed by something (another row, a button, a sentence)
        has one - it separates it from what is below. Called repeatedly
        (every <Configure> of the parent); changes only what has changed.
        Never raises an exception."""
        try:
            susedia = master.pack_slaves()
        except Exception:
            return
        for i, riadok in enumerate(susedia):
            if not isinstance(riadok, SettingRow):
                continue
            riadok._nastav_linku(i < len(susedia) - 1)

    def _nastav_linku(self, vidno):
        try:
            if vidno and not self._linka_vidno:
                self.deliaca_linka.pack(fill="x")
            elif not vidno and self._linka_vidno:
                self.deliaca_linka.pack_forget()
            self._linka_vidno = bool(vidno)
        except Exception:
            pass

    def skry_linku_ak_je_posledny(self):
        """Recomputes the lines of all rows in the parent (`obnov_linky`)."""
        SettingRow.obnov_linky(self.master)


def chip(master, pal, text, command=None, pressed=False, width=0):
    """A flat bordered button - the basic control of the whole interface."""
    btn = ctk.CTkButton(
        master, text=text, command=command, height=28,
        corner_radius=RADIUS_CONTROL, border_width=1,
        border_color=pal["accent"] if pressed else pal["border"],
        fg_color=pal["accent2"] if pressed else "transparent",
        hover_color=pal["surface_alt"],
        text_color=pal["text"] if pressed else pal["text_dim"],
        font=ui(12))
    if width:
        btn.configure(width=width)
    return btn


# --------------------------------------------------------------------------
# Empty state
# --------------------------------------------------------------------------

class EmptyState(ctk.CTkFrame):
    """Empty state: ONE sentence and at most ONE action (0.3 batch 4).

    UX audit: without data the app showed dashes, "0 %" and empty charts -
    that looked like a measurement, not like "nothing yet". On top of that,
    the only prompt that made sense (pair the watch) was below the edge of
    the window. An empty state should say what will appear here and what to
    do for it - nothing more.

    The action is `button(kind="secondary")`, not `chip()`: chip stays for
    external links (design rules in the audit). The kind can be changed via
    `kind`. The sentence is in `text_dim` (>= 4.5:1), because it is content,
    not decoration. The colours come from the palette, so the theme
    recolouring (`theme_recolor`) handles them without a `set_pal` of its
    own.
    """

    def __init__(self, master, pal, text, action=None, command=None,
                 kind="secondary", wraplength=440, anchor="center", pady=(8, 8)):
        super().__init__(master, fg_color="transparent")
        self.pal = pal
        stred = anchor == "center"
        self.label = ctk.CTkLabel(self, text=text, font=ui(12),
                                  text_color=pal["text_dim"], wraplength=wraplength,
                                  justify="center" if stred else "left",
                                  anchor="center" if stred else "w")
        self.action = None
        if action and command is not None:
            self._veta_pack = dict(anchor=anchor, pady=(pady[0], 0))
            self.label.pack(**self._veta_pack)
            self.action = button(self, pal, action, command=command, kind=kind)
            self.action.pack(anchor=anchor, pady=(10, pady[1]))
        else:
            self._veta_pack = dict(anchor=anchor, pady=pady)
            self.label.pack(**self._veta_pack)

    def set_text(self, text):
        try:
            self.label.configure(text=text)
        except Exception:
            pass

    def ukaz_vetu(self, ukaz):
        """Hides / restores the sentence, the action stays (0.3 batch 4b).

        On a busy heart-rate port both the bar and the panel header talk
        about the problem - "Once you pair your watch..." below that would
        be a second, different message (and untrue as well: the watch is
        fine). Never raises an exception."""
        try:
            vidno = bool(self.label.winfo_manager())
            if ukaz and not vidno:
                if self.action is not None and self.action.winfo_manager():
                    self.label.pack(before=self.action, **self._veta_pack)
                else:
                    self.label.pack(**self._veta_pack)
            elif not ukaz and vidno:
                self.label.pack_forget()
        except Exception:
            pass


# --------------------------------------------------------------------------
# Keycap
# --------------------------------------------------------------------------

class Keycap(ctk.CTkFrame):
    """A trigger looks like a key because it is a key.

    The width carries the input type (key / mouse / controller) - the map
    can be read without anyone writing labels for it. The bottom edge is a
    second, darker frame under the face; CTkFrame does not know
    `border-bottom`.
    """

    FACE_H = 42
    LIP = 3

    def __init__(self, master, pal, text, width=48, command=None):
        super().__init__(master, fg_color=pal["keycap_edge"], corner_radius=RADIUS_CONTROL,
                         width=width, height=self.FACE_H + self.LIP)
        self.pack_propagate(False)
        self.grid_propagate(False)
        self.face = ctk.CTkButton(
            self, text=text, command=command, corner_radius=RADIUS_CONTROL,
            height=self.FACE_H, width=width,
            fg_color=pal["keycap_face"], hover_color=pal["surface_alt"],
            border_width=1, border_color=pal["keycap_edge"],
            text_color=pal["keycap_text"],
            font=mono(13 if len(str(text)) <= 3 else 10))
        self.face.pack(fill="x", side="top")

    def set_text(self, text):
        try:
            self.face.configure(text=text,
                                font=mono(13 if len(str(text)) <= 3 else 10))
        except Exception:
            pass

    def set_pal(self, pal):
        """Recolours the key on a theme change.

        Needed separately: `theme_recolor` maps colours by VALUE, and in the
        Sumi theme `keycap_text` has the same value as `accent` (#d9b868),
        while in Modern they differ (#8FB0E8 vs #5C86C9). A mechanical map
        would therefore give the key the accent instead of its own colour.
        Here we set it from the token, so it is always right.
        """
        try:
            self.configure(fg_color=pal["keycap_edge"])
            self.face.configure(fg_color=pal["keycap_face"],
                                hover_color=pal["surface_alt"],
                                border_color=pal["keycap_edge"],
                                text_color=pal["keycap_text"])
        except Exception:
            pass


def set_label_text(widget, text):
    """Rewrites a widget's label regardless of whether it is a Keycap or a
    plain CTkButton/CTkLabel.

    It exists because Keycap is a composite CTkFrame and `.configure(text=)`
    on it raises ValueError. That is exactly where rebinding a trigger
    crashed: one call was fixed to set_text(), the other
    (app.begin_rebind) remained and crashed on every click on the key. The
    caller no longer has to know which of the two widgets it is holding."""
    setter = getattr(widget, "set_text", None)
    if setter is not None:
        setter(text)
    else:
        widget.configure(text=text)


# --------------------------------------------------------------------------
# Kamae - the breathing bar
# --------------------------------------------------------------------------

class KamaeBar(ctk.CTkFrame):
    """The main switch on the Today page - and the only moving element in the
    window.

    It breathes in the same rhythm as the breathing circle in game (5 s
    inhale, 5 s exhale) and when the app is stopped, it stands still. The
    state is read not from a badge or the text colour but from whether the
    interface moves.

    ONE BUTTON WITH TEXT (0.3 batch 4, UX audit). Before 0.3 there was a
    34 px circle with ▶ here, the heading "Main switch" and under it the
    instruction "Click ▶ on the left" - a control that needed instructions.
    Now on the left there is one button "▶ Start watching" / "■ Stop
    watching" (texts `dock.start` / `dock.stop`, the same words as in the
    tray icon menu) and next to it only a quiet sentence on why the bar
    breathes. A stopped app has a `primary` button (fill `accent`), a
    watching one `secondary` (border `control_border`) - the same colours
    as `button(kind=...)`. Every path switches the state the same way
    (`DandurfApp._apply_listening_visuals` -> `set_live`): the button, the
    tray menu and starting via the game.

    KEYBOARD: the canvas can take focus (Tab) and Enter or Space toggle the
    same thing as a click. Focus shows a ring around the button - a mouse
    click does not focus the canvas, so the ring does not pop up on every
    click.

    WHY DRAWN, NOT A CTkButton: the plate under the button breathes while
    watching - every 90 ms it has a different fill. A CTkButton has corners
    in the background colour, which is set once, so a little island of a
    different colour would sit in the breathing plate. So the button is an
    image with transparent corners (smoothed via PIL; without PIL a plain
    polygon) and the text is canvas text.

    The animation always stops when the window is not visible (minimised to
    the tray) - the app runs in the background for the whole gaming session,
    and redrawing something nobody is looking at would be a waste.
    """

    # 92 -> 64 (0.3 batch 4): the bar no longer carries two lines of text
    # (heading and instructions), only the button and one sentence. The window
    # has a fixed height and every line of the bar is taken from the page
    # below.
    HEIGHT = 64
    TICK_MS = 90
    # The button on the left of the bar. Until version 2.1 there was only a
    # coloured dot here and a CLICK ANYWHERE on the bar toggled it - which the
    # player only learned from the guide. NOW ONLY the button toggles: one
    # intent, one place.
    BTN_X = 14
    BTN_SIZE = 36               # button height (logical px), audit: 36 px
    BTN_PAD = 18                # text padding inside the button
    BTN_MIN_W = 150
    FOCUS_GAP = 3               # gap between the button and the focus ring
    FOCUS_W = 2                 # focus ring thickness
    HALF_CYCLE_MS = 5000.0      # same phase as _SlotOverlay.HALF_CYCLE_S

    def __init__(self, master, pal, on_toggle, start_label="", stop_label="",
                 hint=""):
        super().__init__(master, fg_color="transparent", height=self.HEIGHT)
        self.pack_propagate(False)
        self.pal = pal
        self.on_toggle = on_toggle
        self.live = False
        self._phase = 0.0
        self._job = None
        self._start_label = start_label
        self._stop_label = stop_label
        self._hint = hint
        # Button state: cursor over it / focused by keyboard. The button
        # images are cached by (size, kind, state, colours) - they do not
        # change on a breath tick, they are swapped only on a state change.
        self._hover_btn = False
        self._focus = False
        self._btn_imgs = {}
        self._btn_stav = None
        self._btn_rect = None     # (x0, y0, x1, y1) in the canvas's PHYSICAL px
        # Reusing canvas items instead of delete("all") + re-creating them
        # every tick (90 ms). `_it` are the item ids, `_it_sig` is the (width,
        # height, scale) they were built for - on a change they are built anew,
        # otherwise only adjusted (coords/itemconfigure). Same pattern as the
        # Today centre.
        self._it = None
        self._it_sig = None       # (w, h, mierka) the items were built for
        self._last_mierka = 1.0

        # `takefocus=1`: the main switch can be reached with the keyboard
        # (Tab).
        self.canvas = tk.Canvas(self, height=self.HEIGHT, bg=pal["bg"],
                                highlightthickness=0, bd=0, takefocus=1)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._clicked)
        self.canvas.bind("<Motion>", self._hover)
        self.canvas.bind("<Leave>", self._leave)
        self.canvas.bind("<Configure>", lambda _e: self._redraw())
        self.canvas.bind("<FocusIn>", lambda _e: self._set_focus(True))
        self.canvas.bind("<FocusOut>", lambda _e: self._set_focus(False))
        for klaves in ("<Return>", "<KP_Enter>", "<space>"):
            self.canvas.bind(klaves, self._key)

    def _set_scaling(self, *args, **kwargs):
        """Redraws on a DPI change too (window moved to a monitor with a
        different scale).

        `<Configure>` fires only when the PHYSICAL size of the canvas
        changes. Two monitors with the same width in px but a different DPI:
        on a move the scale changes (and the font size), but the canvas
        stays the same size - Configure does not fire and the text stays
        wrapped the old way (to the old `width=`). CTk sends the new scale
        here, so we redraw to the correct width right then."""
        try:
            super()._set_scaling(*args, **kwargs)
        except Exception:
            pass
        try:
            self._it = None      # new scale -> rebuild items (font/wrapping)
            self._redraw()
        except Exception:
            pass

    # ---- public ----

    def set_live(self, live):
        live = bool(live)
        # We reset the phase ONLY on a real state change. `set_live` is
        # also called on a window rebuild (theme/language change) with the
        # same value, and then the breath got cut off to zero - on top of
        # that the mark now also hangs on it (the enso reads `phase()`), so
        # both would jump at once.
        if live != self.live:
            self._phase = 0.0
        self.live = live
        self._redraw()
        self._schedule()

    def set_texts(self, start_label, stop_label, hint=""):
        """The button texts (stopped / watching) and the quiet sentence next to
        it.

        The button width is computed from the LONGER of the two texts, so
        that it does not jump on toggling - that is why the items are built
        anew when the text changes. It is called often (every heart-rate
        sample rewrites the state on Today), so identical texts do nothing."""
        texty = (start_label, stop_label, hint)
        if texty == (self._start_label, self._stop_label, self._hint):
            return
        self._start_label, self._stop_label, self._hint = texty
        self._it = None
        self._redraw()

    def button_label(self):
        """The text the button shows right now (for tests and the tour)."""
        return self._stop_label if self.live else self._start_label

    def set_pal(self, pal):
        """Redraws the bar in the new theme.

        Without this method the bar kept the palette from the moment it was
        created. `theme_recolor.recolor_tree` rewrites only widget OPTIONS,
        so the canvas background changed, but the plate, the breath line,
        the dot and the text are drawn from `self.pal` and stayed in the old
        theme - after switching from Sumi to Aizome a brown plate with a
        gold line sat in an indigo window.

        Nobody caught it: `PalCanvas` has `set_pal` and is in the searched
        list in `_recolor_ui`, but `KamaeBar` is a bare `tk.Canvas` and was
        not in that list. `theme_recolor.find_theme_colored` is made exactly
        for this, but nothing calls it.
        """
        self.pal = pal
        # the button images have their colours baked in - the old theme does
        # not belong in the new one
        self._btn_imgs = {}
        self._btn_stav = None
        try:
            self.canvas.configure(bg=pal["bg"])
        except Exception:
            pass
        self._redraw()

    # NOTE: there used to be `set_metrics([(hodnota, popisok), ...])` here -
    # three numbers on the right of the bar: session length, number of cues,
    # heart rate. Removed because the length and the count sit right next to
    # it in the right panel of the Today page and the bar only repeated them.
    # The bar is meant to carry STATE, not a score - that is the whole reason
    # it has the switch and why it breathes.
    #
    # With that, HEART RATE disappeared from the other pages entirely (in the
    # right panel it is only on Today). It is a deliberate trade-off for a
    # quieter bar, not an oversight.

    def phase(self):
        """Breath phase 0..1 - the app's PUBLIC rhythm.

        `KamaeBar` is the only moving element of the header and its breath
        line on the bottom edge sets the tempo. The mark (the enso in the
        side panel) reads it from here, so both breathe AT ONCE and in one
        rhythm - if each computed its own phase, they would have the same
        period but gradually drift apart, and two things would move against
        each other in the window.
        """
        return self._phase if self.live else 0.0

    def stop(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    # ---- internals ----

    def _v_spinaci(self, event):
        """Is the click inside the button? Event coordinates are PHYSICAL px -
        so the button rectangle is remembered from drawing (`_btn_rect`,
        already scaled). Until it is drawn, an estimate from the constants
        and the real canvas height - otherwise at 150 % a click would miss
        where the button is."""
        rect = self._btn_rect
        if rect is None:
            m = self._last_mierka or 1.0
            bs = self.BTN_SIZE * m
            bx = self.BTN_X * m
            try:
                h = int(self.canvas.winfo_height())
            except Exception:
                h = int(self.HEIGHT * m)
            by = (h - bs) / 2.0
            rect = (bx, by, bx + self.BTN_MIN_W * m, by + bs)
        x0, y0, x1, y1 = rect
        return x0 <= event.x <= x1 and y0 <= event.y <= y1

    def _clicked(self, event):
        if self._v_spinaci(event) and callable(self.on_toggle):
            self.on_toggle()

    def _key(self, _event=None):
        """Enter / Space on the focused bar = a click on the button."""
        if callable(self.on_toggle):
            self.on_toggle()
        return "break"

    def _hover(self, event):
        """Hand cursor and highlight only over the button. The cursor is the
        only preview the player gets before a click - if the hand were over the
        whole bar, it would promise an action that no longer happens
        anywhere else."""
        nad = self._v_spinaci(event)
        try:
            self.canvas.configure(cursor="hand2" if nad else "")
        except Exception:
            pass
        if nad != self._hover_btn:
            self._hover_btn = nad
            self._redraw()

    def _leave(self, _event=None):
        if self._hover_btn:
            self._hover_btn = False
            self._redraw()

    def _set_focus(self, zamerane):
        zamerane = bool(zamerane)
        if zamerane != self._focus:
            self._focus = zamerane
            self._redraw()

    def _schedule(self):
        self.stop()
        if not self.live:
            return
        self._job = self.after(self.TICK_MS, self._tick)

    def _tick(self):
        self._job = None
        if not self.live:
            return
        try:
            visible = bool(self.winfo_viewable())
        except Exception:
            visible = False
        if visible:
            self._phase = (self._phase + self.TICK_MS / (self.HALF_CYCLE_MS * 2)) % 1.0
            self._redraw()
        self._schedule()

    def _breath(self):
        """0..1 - a smooth inhale and exhale, slowed down at the ends."""
        return 0.5 - 0.5 * math.cos(2 * math.pi * self._phase)

    def _redraw(self):
        try:
            w = int(self.canvas.winfo_width())
            h = int(self.canvas.winfo_height())
        except Exception:
            return
        if w < 40 or h < 10:
            return
        # DPI: the canvas is a plain tk.Canvas, so we add the scaling ourselves
        # - otherwise on a 150 % display it drew into the top 92 px of ~138 px
        # and a dark hole remained under the bar (+ the switch and text were
        # too small and off to the left).
        try:
            mierka = float(ctk.ScalingTracker.get_widget_scaling(self)) or 1.0
        except Exception:
            mierka = 1.0
        self._last_mierka = mierka
        sig = (w, h, round(mierka, 2))
        if self._it is None or self._it_sig != sig:
            self._build_items(w, h, mierka)
            self._it_sig = sig
        self._update_items(w, h, mierka, self._breath() if self.live else 0.0)

    def _cvfont(self, size, weight="normal"):
        """Font for drawing on a Canvas in PHYSICAL px (a negative size = px,
        which `tk scaling` no longer multiplies) - the same trick as the
        Today centre."""
        return (ui(size)[0], -max(1, int(round(size * self._last_mierka))), weight)

    def _build_items(self, w, h, m):
        """Builds the canvas items ONCE for the given (width, height, scale); on
        every tick they are only adjusted (`_update_items`) - no
        delete("all") and no re-creating, so the bar does not flicker even
        on Tk builds without double buffering. `w`/`h` are the canvas's
        PHYSICAL px; we scale the logical constants (button, gaps) by `m` so
        that at 150 % they fill the bar proportionally."""
        c = self.canvas
        c.delete("all")
        it = {"glow": []}
        it["plate"] = round_rect(c, 1, 1, w - 1, h - 1, int(round(7 * m)),
                                 fill="", outline="")
        # FILLING SHEEN - a fixed pool of 22 rectangles from the centre to the
        # sides; which are visible is decided by `state` on each tick (a
        # constant number of items).
        seg = 22
        for i in range(seg):
            x0 = 2 + (w - 4) * i / seg
            x1 = 2 + (w - 4) * (i + 1) / seg
            it["glow"].append(c.create_rectangle(x0, 2, x1, h - 2, fill="",
                                                 outline="", state="hidden"))
        it["line"] = c.create_line(0, h - 3, 0, h - 3, width=max(1, int(round(2 * m))),
                                   capstyle="round", state="hidden")
        # BUTTON. Width from the wider of the two texts - when toggling Start
        # <-> Stop neither the button nor the sentence next to it may jump.
        pismo = self._cvfont(13, "bold")
        try:
            meradlo = tkfont.Font(family=pismo[0], size=pismo[1], weight=pismo[2])
            sirka_textu = max(meradlo.measure(t) for t in
                              (self._start_label, self._stop_label, ""))
        except Exception:
            sirka_textu = int(max(len(self._start_label), len(self._stop_label)) * 8 * m)
        bw = int(round(max(self.BTN_MIN_W * m, sirka_textu + 2 * self.BTN_PAD * m)))
        bh = int(round(self.BTN_SIZE * m))
        bx = int(round(self.BTN_X * m))
        by = int((h - bh) / 2)
        self._btn_rect = (bx, by, bx + bw, by + bh)
        okraj = self._btn_okraj(m)
        it["btn_img"] = c.create_image(bx - okraj, by - okraj, anchor="nw")
        it["btn_poly"] = round_rect(c, bx, by, bx + bw, by + bh,
                                    int(round(RADIUS_CONTROL * m)), fill="",
                                    outline="", state="hidden")
        it["btn_text"] = c.create_text(bx + bw / 2.0, by + bh / 2.0, text="",
                                       anchor="center", font=pismo)
        # QUIET SENTENCE next to the button - why the bar breathes. When it
        # does not fit (narrow window, long button translation), better none
        # than clipped.
        tx = bx + bw + 16 * m
        sirka = int(w - tx - 16 * m)
        it["hint"] = c.create_text(tx, h / 2.0, text=self._hint if sirka > 80 * m else "",
                                   anchor="w", font=self._cvfont(12),
                                   width=max(1, sirka))
        self._it = it
        self._btn_stav = None       # new items -> draw the button again

    def _btn_okraj(self, m):
        """How much bigger the button image is than the button (room for the
        focus ring), in physical px."""
        return int(math.ceil((self.FOCUS_GAP + self.FOCUS_W) * m))

    def _btn_obrazok(self, bw, bh, m, vypln, ram, prstenec):
        """A smoothed button (and focus ring) as an image with transparent
        corners, or None without PIL. It is drawn 4x bigger and scaled
        down - on Windows a Tk polygon does not smooth its edges. It is
        scaled down in premultiplied alpha ("RGBa"), otherwise transparent
        pixels would mix black into the edge."""
        kluc = (bw, bh, round(m, 2), vypln, ram, prstenec)
        obr = self._btn_imgs.get(kluc)
        if obr is not None:
            return obr
        try:
            from PIL import Image, ImageDraw, ImageTk
        except Exception:
            return None
        try:
            ss = 4
            okraj = self._btn_okraj(m)
            sirka, vyska = bw + 2 * okraj, bh + 2 * okraj
            img = Image.new("RGBA", (sirka * ss, vyska * ss), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            r = RADIUS_CONTROL * m
            if prstenec:
                hr = (self.FOCUS_GAP + self.FOCUS_W) * m
                d.rounded_rectangle(
                    [(okraj - hr) * ss, (okraj - hr) * ss,
                     (okraj + bw + hr) * ss - 1, (okraj + bh + hr) * ss - 1],
                    radius=(r + hr) * ss, outline=prstenec,
                    width=max(1, int(round(self.FOCUS_W * m * ss))))
            d.rounded_rectangle(
                [okraj * ss, okraj * ss, (okraj + bw) * ss - 1, (okraj + bh) * ss - 1],
                radius=r * ss, fill=vypln, outline=ram,
                width=max(1, int(round(m * ss))) if ram else 0)
            img = img.convert("RGBa").resize((sirka, vyska), Image.LANCZOS).convert("RGBA")
            obr = ImageTk.PhotoImage(img, master=self.canvas)
        except Exception:
            return None
        if len(self._btn_imgs) > 24:
            self._btn_imgs = {}
        self._btn_imgs[kluc] = obr
        return obr

    def _kresli_tlacidlo(self, druh, m):
        """Redraws the button for `druh` ("primary" stopped / "secondary"
        watching), the cursor over it and focus. The colours are the same as
        for `button(kind=...)`: primary = fill `accent` and text `bg`,
        secondary = border `control_border` (>= 3:1) and text `text`."""
        c, it, pal = self.canvas, self._it, self.pal
        x0, y0, x1, y1 = self._btn_rect
        if druh == "primary":
            vypln = pal["accent_hover"] if self._hover_btn else pal["accent"]
            ram, farba_textu = None, pal["bg"]
        else:
            vypln = pal["surface_alt"] if self._hover_btn else None
            ram, farba_textu = pal["control_border"], pal["text"]
        prstenec = pal["accent_hover"] if self._focus else None
        obr = self._btn_obrazok(x1 - x0, y1 - y0, m, vypln, ram, prstenec)
        if obr is not None:
            c.itemconfigure(it["btn_img"], image=obr, state="normal")
            c.itemconfigure(it["btn_poly"], state="hidden")
        else:
            c.itemconfigure(it["btn_img"], state="hidden")
            c.itemconfigure(it["btn_poly"], state="normal", fill=vypln or "",
                            outline=prstenec or ram or "",
                            width=max(1, int(round((2 if prstenec else 1) * m))))
        c.itemconfigure(it["btn_text"], text=self.button_label(), fill=farba_textu)

    def _update_items(self, w, h, m, t):
        """Adjusts the colour/position/visibility of the items by state and
        breath phase, without deleting. It takes all colours from the
        CURRENT palette, so it handles a theme change too (`set_pal` ->
        `_redraw` -> here)."""
        c = self.canvas
        it = self._it
        pal = self.pal
        live = self.live
        if live:
            fill = theme_mod.mix(pal["plate"], pal["plate_glow"], t)
            outline = theme_mod.mix(pal["accent2"], pal["accent"], 0.5 * t)
        else:
            fill = pal["plate_idle"]
            outline = pal["plate_idle_border"]
        c.itemconfigure(it["plate"], fill=fill, outline=outline)
        cxf = w / 2.0
        seg = len(it["glow"])
        for i, rid in enumerate(it["glow"]):
            if live and t > 0.01:
                x0 = 2 + (w - 4) * i / seg
                x1 = 2 + (w - 4) * (i + 1) / seg
                d = abs((x0 + x1) / 2.0 - cxf) / (w / 2.0)
                jas = max(0.0, 1.0 - d) ** 1.6 * t
                if jas >= 0.02:
                    c.itemconfigure(rid, state="normal",
                                    fill=theme_mod.mix(fill, pal["accent_hover"], 0.5 * jas))
                    continue
            c.itemconfigure(rid, state="hidden")
        if live:
            half = (w * 0.06) + (w * 0.40) * t
            cx = w / 2.0
            c.coords(it["line"], cx - half, h - 3, cx + half, h - 3)
            c.itemconfigure(it["line"], fill=pal["accent_hover"], state="normal")
        else:
            c.itemconfigure(it["line"], state="hidden")
        # The button is redrawn only on a state change, not on every breath
        # tick: the image has transparent corners and a `secondary` interior,
        # so the breathing plate under it shows through by itself.
        druh = "secondary" if live else "primary"
        stav = (druh, self._hover_btn, self._focus, self._btn_rect)
        if stav != self._btn_stav:
            self._btn_stav = stav
            self._kresli_tlacidlo(druh, m)
        c.itemconfigure(it["hint"], fill=pal["text_dim"] if live else pal["text_faint"])


# --------------------------------------------------------------------------
# Heart-rate curve
# --------------------------------------------------------------------------

class PalCanvas(ctk.CTkFrame):
    """The shared base of everything drawn on a `tk.Canvas`.

    It holds the canvas, the palette and the redraw on a width change.
    `set_pal` is here because theme recolouring (`theme_recolor`) can
    rewrite a widget's OPTIONS, but not what already lies on the canvas - a
    line would stay in the old colour until something redraws it. Live
    charts are redrawn with every heart-rate sample and heal themselves;
    the chart in History stands still until someone clicks through it, so
    without `set_pal` it would glow the old way after a theme change.
    `DandurfApp._recolor_ui` walks the tree and calls it on every
    descendant.
    """

    def __init__(self, master, pal, height):
        super().__init__(master, fg_color="transparent", height=height)
        self.pack_propagate(False)
        self.pal = pal
        self.height = height
        self.canvas = tk.Canvas(self, height=height, bg=pal["surface"],
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._redraw())

    def set_pal(self, pal):
        self.pal = pal
        try:
            self.canvas.configure(bg=pal["surface"])
        except Exception:
            pass
        self._redraw()

    def _canvas_size(self, min_width=20):
        """(width, height, scale) of the canvas in REAL pixels; (0, 0, 1.0)
        until it is laid out.

        `mierka` is the ratio of the canvas's real height to the widget's
        logical height. CustomTkinter takes sizes in "its own" units and
        multiplies them by the display scale itself, but the `tk.Canvas`
        under them draws in real pixels. On a 150 % display (a common
        setting on Windows) the chart would draw into the top two thirds of
        the canvas and leave a hole below - exactly what happened in this
        app. So all sizes in `_redraw` are multiplied by this scale.
        """
        try:
            w = int(self.canvas.winfo_width())
            h = int(self.canvas.winfo_height())
        except Exception:
            return 0, 0, 1.0
        if w < min_width or h < 2:
            return 0, 0, 1.0
        return w, h, (h / float(self.height)) if self.height else 1.0

    def _redraw(self):
        pass


class Sparkline(PalCanvas):
    """Heart-rate course with the critical limit and your own resting
    baseline.

    Without the baseline the curve is unreadable: 90 BPM is calm for one
    person and panic for another. That is why both lines are in the chart -
    the limit (dashed) and the baseline (thin), and only against them does
    the curve mean something.
    """

    def __init__(self, master, pal, height=64):
        super().__init__(master, pal, height)
        self._values, self._threshold, self._baseline = [], None, None
        self._color = None

    def set_series(self, values, threshold=None, baseline=None, color=None):
        """`color` is an optional override of the line colour (e.g. History
        changes the colour by the selected metric) - without it the default
        accent stays.

        WATCH OUT FOR ZERO: the filter here used to be `if v`, so it also
        dropped zeros. For heart rate it does not matter (0 BPM does not
        exist), but History also sends "time over the limit" here - and
        there zero is a VALID value. A day without exceeding dropped out of
        the chart and the curve shifted by one point.
        """
        self._values = [v for v in (values or []) if v is not None]
        self._threshold = threshold
        self._baseline = baseline
        self._color = color
        self._redraw()

    def _redraw(self):
        pal, c = self.pal, self.canvas
        w, h, s = self._canvas_size()
        if not w:
            return
        c.delete("all")
        pad = 6 * s
        values = self._values

        if len(values) < 2:
            c.create_line(0, h - pad, w, h - pad, fill=pal["text_faint"], width=1)
            return

        lo, hi = min(values), max(values)
        if self._threshold:
            lo, hi = min(lo, self._threshold - 4), max(hi, self._threshold + 4)
        if hi - lo < 12:
            mid = (hi + lo) / 2.0
            lo, hi = mid - 6, mid + 6
        span = float(hi - lo)

        def y_of(value):
            return h - pad - (value - lo) / span * (h - 2 * pad)

        if self._baseline and lo <= self._baseline <= hi:
            c.create_line(0, y_of(self._baseline), w, y_of(self._baseline),
                          fill=pal["text_faint"], width=1)
        if self._threshold and lo <= self._threshold <= hi:
            c.create_line(0, y_of(self._threshold), w, y_of(self._threshold),
                          fill=pal["danger"], width=1, dash=(4, 4))

        step = w / float(len(values) - 1)
        points = []
        for i, value in enumerate(values):
            points.extend((i * step, y_of(value)))
        c.create_line(*points, fill=self._color or pal["accent_hover"],
                      width=max(1, round(2 * s)), smooth=True, capstyle="round",
                      joinstyle="round")
        r = 3 * s
        c.create_oval(points[-2] - r, points[-1] - r, points[-2] + r, points[-1] + r,
                      fill=pal["text"], outline="")


class SegmentBar(PalCanvas):
    """Load as a segmented bar. A smooth bar would claim a precision that a
    heart-rate number does not have - twenty segments are more honest.

    The length is the load, the colour of the filled segments is the
    CURRENT zone (`zone` from `HeartStats.zone`, heart rate against rest) -
    all the same, as on the HUD. The bar has no zone boundaries of its own:
    before, it coloured the segments by 35/60/80 % of the length, so at
    load 57 it ended "elevated", the HUD at the same load "high" (quarters
    of the bar), and the word above it could say something else again.
    Without `zone` the segments are neutral (accent).
    """

    SEGMENTS = 20

    def __init__(self, master, pal, height=8):
        super().__init__(master, pal, height)
        self._value = 0.0
        self._zone = None

    def set_value(self, percent, zone=None):
        self._value = max(0.0, min(100.0, float(percent or 0)))
        self._zone = zone
        self._redraw()

    def _redraw(self):
        pal, c = self.pal, self.canvas
        w, h, _s = self._canvas_size()
        if not w:
            return
        c.delete("all")
        filled = int(round(self.SEGMENTS * self._value / 100.0))
        seg = w / float(self.SEGMENTS)
        plna = theme_mod.zone_color(pal, self._zone)
        for i in range(self.SEGMENTS):
            x0 = i * seg
            x1 = x0 + seg * 0.72
            color = plna if i < filled else pal["switch_off"]
            c.create_rectangle(x0, 0, x1, h, fill=color, outline="")


# --------------------------------------------------------------------------
# History and session charts
# --------------------------------------------------------------------------

class ZoneBar(PalCanvas):
    """The split of a session's time into zones as one proportional bar.

    The app computed `zone_seconds` from the start and showed them nowhere.
    Yet a single number ("12 minutes over the limit") does not tell what the
    proportion tells: whether the evening was mostly calm with two spikes,
    or an hour in the red.
    """

    ORDER = ("calm", "raised", "high", "critical")

    def __init__(self, master, pal, height=14):
        super().__init__(master, pal, height)
        self._zones = {}

    def set_zones(self, zone_seconds):
        self._zones = dict(zone_seconds or {})
        self._redraw()

    def _redraw(self):
        pal, c = self.pal, self.canvas
        w, h, s = self._canvas_size()
        if not w:
            return
        c.delete("all")
        diely = [(z, max(0.0, float(self._zones.get(z, 0.0) or 0.0))) for z in self.ORDER]
        celkom = sum(d for _z, d in diely)
        if celkom <= 0:
            round_rect(c, 0, 0, w, h, 3 * s, fill=pal["line_soft"], outline="")
            return
        x = 0.0
        for zona, sekundy in diely:
            sirka = sekundy / celkom * w
            if sirka <= 0:
                continue
            c.create_rectangle(x, 0, min(float(w), x + sirka), h,
                               fill=theme_mod.zone_color(pal, zona), outline="")
            x += sirka


class TrendChart(PalCanvas):
    """How a metric develops across sessions - columns or a line, with axes.

    Why axes: originally `Sparkline` drew it, i.e. a bare line without a
    single label - you could read neither WHEN nor HOW MUCH from the chart.
    Yet `hr_stats.aggregate_by_period` already computes the label of every
    bucket, nobody just drew it.

    The shape depends on the metric: time and peaks are columns from zero
    (zero is a statement then, not a gap), baseline and recovery are a line
    around their own level - for them a column from zero would spend the
    whole chart height getting to the 60-70 BPM band the player cares
    about.

    `band` is "your usual range" (p25-p75 from the history): a value inside
    the band is your normal, a value outside it is the only thing that
    deserves attention.
    """

    PAD_L = 48      # y-axis labels
    PAD_R = 10
    PAD_T = 12
    PAD_B = 20      # x-axis labels
    MAX_X_LABELS = 8

    # EMPTY STATE (0.3, UX audit): without data there was an empty ~230 px area
    # where the chart is, and the "nothing yet" sentence only below it. Now the
    # chart shrinks to EMPTY_H and writes the sentence in its centre.
    EMPTY_H = 80

    def __init__(self, master, pal, height=150):
        super().__init__(master, pal, height)
        self._full_height = height
        self._values, self._labels = [], []
        self._color, self._band, self._band_label = None, None, ""
        self._bars = False
        self._decimals = 0
        self._empty_text = ""

    def set_series(self, values, labels=None, color=None, band=None,
                   band_label="", bars=False, decimals=0, empty_text=""):
        self._values = list(values or [])
        self._labels = list(labels or [])
        self._color = color
        self._band = band
        self._band_label = band_label or ""
        self._bars = bool(bars)
        self._decimals = int(decimals)
        self._empty_text = empty_text or ""
        prazdny = not [v for v in self._values if v is not None]
        vyska = self.EMPTY_H if (prazdny and self._empty_text) else self._full_height
        if vyska != self.height:
            # `self.height` is also the basis of the scale in `_canvas_size`
            self.height = vyska
            try:
                self.configure(height=vyska)
            except Exception:
                pass
        self._redraw()

    def _fmt(self, value):
        return f"{value:.{self._decimals}f}"

    def _bounds(self):
        """(lo, hi) of the y axis. Columns always from zero, a line with
        headroom around the data."""
        values = [v for v in self._values if v is not None]
        lo, hi = min(values), max(values)
        if self._band:
            lo, hi = min(lo, self._band[0]), max(hi, self._band[1])
        if self._bars:
            lo = 0.0
            if hi <= 0:
                hi = 1.0
        else:
            if hi - lo < 1.0:
                mid = (hi + lo) / 2.0
                lo, hi = mid - 0.5, mid + 0.5
            rezerva = (hi - lo) * 0.15
            lo, hi = lo - rezerva, hi + rezerva
        return lo, hi

    def _draw_x_labels(self, x0, slot, h, s):
        """X-axis labels, thinned out so they do not overlap. The last bucket is
        always drawn - "where am I now" is what you look for."""
        pal, c = self.pal, self.canvas
        n = len(self._labels)
        every = max(1, int(math.ceil(n / float(self.MAX_X_LABELS))))
        indexy = list(range(0, n, every))
        if n and indexy[-1] != n - 1:
            if n - 1 - indexy[-1] < max(1, every // 2):
                indexy.pop()
            indexy.append(n - 1)
        for i in indexy:
            c.create_text(x0 + slot * (i + 0.5), h - 5 * s, text=self._labels[i],
                          anchor="s", fill=pal["text_faint"], font=mono(10))

    def _redraw(self):
        pal, c = self.pal, self.canvas
        w, h, s = self._canvas_size(120)
        if not w:
            return
        c.delete("all")
        x0, x1 = self.PAD_L * s, w - self.PAD_R * s
        y0, y1 = self.PAD_T * s, h - self.PAD_B * s
        if not [v for v in self._values if v is not None]:
            if self._empty_text:
                c.create_text(w / 2.0, h / 2.0, text=self._empty_text,
                              fill=pal["text_dim"], font=ui(12),
                              width=max(40, int(w - 2 * self.PAD_L * s)))
            else:
                c.create_line(x0, y1, x1, y1, fill=pal["line_soft"], width=1)
            return

        lo, hi = self._bounds()
        span = float(hi - lo) or 1.0

        def y_of(value):
            return y1 - (value - lo) / span * (y1 - y0)

        if self._band:
            # The band is background, not data: `accent2` at full width was so
            # loud it drowned out the line itself. An accent gently mixed into
            # the base keeps the meaning ("this is where you usually are") and
            # does not steal attention.
            vrch_pasu = y_of(self._band[1])
            c.create_rectangle(x0, vrch_pasu, x1, y_of(self._band[0]),
                               fill=theme_mod.mix(pal["surface"], pal["accent"], 0.14),
                               outline="")
            # A band without a label is just a coloured rectangle - you have no
            # idea whether it is a goal, a norm or decoration.
            if self._band_label:
                c.create_text(x1, vrch_pasu - 3 * s, text=self._band_label,
                              anchor="se", fill=pal["text_faint"], font=ui(10))
        for value in (lo, (lo + hi) / 2.0, hi):
            y = y_of(value)
            c.create_line(x0, y, x1, y, fill=pal["line_soft"], width=1)
            c.create_text(x0 - 7 * s, y, text=self._fmt(value), anchor="e",
                          fill=pal["text_faint"], font=mono(10))

        color = self._color or pal["accent_hover"]
        n = len(self._values)
        slot = (x1 - x0) / float(n)
        if self._bars:
            sirka = max(3.0 * s, min(30.0 * s, slot * 0.62))
            spodok = y_of(lo)
            for i, value in enumerate(self._values):
                if value is None:
                    continue
                stred = x0 + slot * (i + 0.5)
                vrch = y_of(value)
                # a zero day should stay visible as zero, not disappear
                if spodok - vrch < 2.0 * s:
                    vrch = spodok - 2.0 * s
                c.create_rectangle(stred - sirka / 2, vrch, stred + sirka / 2,
                                   spodok, fill=color, outline="")
        else:
            body = []
            for i, value in enumerate(self._values):
                if value is None:
                    continue
                body.extend((x0 + slot * (i + 0.5), y_of(value)))
            if len(body) >= 4:
                c.create_line(*body, fill=color, width=max(1, round(2 * s)),
                              smooth=True, capstyle="round", joinstyle="round")
            if body:
                r = 3 * s
                c.create_oval(body[-2] - r, body[-1] - r, body[-2] + r,
                              body[-1] + r, fill=pal["text"], outline="")
        if self._labels:
            self._draw_x_labels(x0, slot, h, s)


class SessionTrace(PalCanvas):
    """Trace of the WHOLE session: the curve, the limit, the baseline, the
    zone strip and the marks where breathing was triggered.

    `Sparkline` next to it shows the last three minutes - that is "now".
    This is "the whole evening": where the heart rate jumped, how long it
    stayed there and when the app triggered breathing. Without this, a
    session could only be read as a row of numbers.

    The strip under the curve colours time by `hr_stats.zone_of_bpm` - the
    same function that sums up the seconds in the zones. If the zone strip
    computed it on its own, the picture and the numbers under it would stop
    matching over time.
    """

    STRIP_H = 9
    ACT_H = 7        # the 'where you played' strip
    TIME_H = 14
    # Right-hand margin for the limit and baseline numbers (0.3, UX audit). The
    # labels lay ON the curve, which after an evening with heart rate near the
    # limit covered both "110" and "76". The curve, the bands and the marks end
    # before the margin; the numbers are in it.
    LABEL_W = 28

    def __init__(self, master, pal, height=88):
        super().__init__(master, pal, height)
        self._values, self._baseline, self._threshold = [], None, None
        self._duration, self._triggers = 0.0, []
        self._activity = []

    def set_trace(self, values, baseline=None, threshold=None, duration_s=0.0,
                  triggers=(), activity=()):
        self._values = [v for v in (values or []) if v]
        self._baseline = baseline
        self._threshold = threshold
        self._duration = float(duration_s or 0.0)
        self._triggers = list(triggers or [])
        self._activity = [a for a in (activity or [])]
        self._redraw()

    @staticmethod
    def _mmss(seconds):
        total = int(max(0.0, seconds))
        return f"{total // 60}:{total % 60:02d}"

    # From one hour up, the end of the axis is written as a duration ("2 h 18
    # min"), not m:ss: "138:02" looked like a time on a clock (0.3, UX audit,
    # batch 4). The same threshold as `cas_text` ("Over the limit", session
    # time).
    OS_DLZKA_OD_S = DLZKA_OD_S

    @classmethod
    def os_popisky(cls, duration_s):
        """(start, end) of the time axis for a session `duration_s` long."""
        if duration_s >= cls.OS_DLZKA_OD_S:
            return dlzka_text(0), dlzka_text(duration_s)
        return "0:00", cls._mmss(duration_s)

    def _draw_strip(self, w, top, vyska):
        """The zone strip - adjacent identical zones merge into one rectangle,
        so the canvas does not hold 120 shapes instead of five."""
        pal, c = self.pal, self.canvas
        base = self._baseline or min(self._values)
        critical = self._threshold or (base + 40)
        n = len(self._values)
        krok = w / float(n)
        start, zona = 0, hr_stats.zone_of_bpm(self._values[0], base, critical)
        for i in range(1, n + 1):
            aktualna = (hr_stats.zone_of_bpm(self._values[i], base, critical)
                        if i < n else None)
            if aktualna == zona:
                continue
            c.create_rectangle(start * krok, top, i * krok, top + vyska,
                               fill=theme_mod.zone_color(pal, zona), outline="")
            start, zona = i, aktualna

    def _draw_activity(self, w, top, vyska):
        """A thin strip above the zone strip: where you really played.

        Each point is the SHARE of time with input in the given slice (0..1),
        not a value at an instant. A high value = dense input = playing; low
        = a menu or away from the PC.

        It is an ESTIMATE, not the truth about the game. `GetLastInputInfo`
        sees input anywhere, so typing in Discord during a game looks the
        same as playing. That is why it is drawn faintly and without a label
        that would claim more than we know.
        """
        if not self._activity:
            return
        pal, c = self.pal, self.canvas
        n = len(self._activity)
        krok = w / float(n)
        for i, hodnota in enumerate(self._activity):
            if hodnota is None:
                continue
            try:
                podiel = max(0.0, min(1.0, float(hodnota)))
            except (TypeError, ValueError):
                continue
            if podiel <= 0.02:
                continue
            # The column height carries the density; the colour stays one, so
            # the strip is not mistaken for the zone strip right below it.
            #
            # `text_faint`, not `text_dim` and certainly not the accent: it is
            # an ESTIMATE, not a measurement. With `text_dim` (#9A9488) the
            # strip was brighter than the heart-rate curve itself - the
            # estimate drowned out the very thing the chart exists for. It has
            # to be readable and subordinate at the same time.
            vyska_st = max(1.0, vyska * podiel)
            c.create_rectangle(i * krok, top + vyska - vyska_st,
                               (i + 1) * krok, top + vyska,
                               fill=pal["text_faint"], outline="")

    def _draw_triggers(self, w, bottom, s):
        """When the app triggered breathing - a small mark above the zones."""
        pal, c = self.pal, self.canvas
        if not self._triggers or self._duration <= 0:
            return
        for offset in self._triggers:
            try:
                podiel = float(offset) / self._duration
            except (TypeError, ValueError, ZeroDivisionError):
                continue
            if not 0.0 <= podiel <= 1.0:
                continue
            x = podiel * w
            c.create_polygon(x - 4 * s, bottom - 6 * s, x + 4 * s, bottom - 6 * s,
                             x, bottom, fill=pal["murasaki"], outline="")

    def _redraw(self):
        pal, c = self.pal, self.canvas
        w, h, s = self._canvas_size(60)
        if not w:
            return
        c.delete("all")
        strip_h, time_h = self.STRIP_H * s, self.TIME_H * s
        strip_top = h - time_h - strip_h
        values = self._values
        if len(values) < 2:
            c.create_line(0, strip_top, w, strip_top, fill=pal["line_soft"], width=1)
            return

        lo, hi = min(values), max(values)
        for ciara in (self._threshold, self._baseline):
            if ciara:
                lo, hi = min(lo, ciara - 3), max(hi, ciara + 3)
        if hi - lo < 12:
            mid = (hi + lo) / 2.0
            lo, hi = mid - 6, mid + 6
        span = float(hi - lo)
        vrch, spodok = 4 * s, strip_top - 10 * s
        pw = max(10.0, w - self.LABEL_W * s)     # curve width without the margin
        obsadene = []                             # y of numbers already drawn

        def y_of(value):
            return spodok - (value - lo) / span * (spodok - vrch)

        def popisok(y, hodnota, farba):
            """A number for a line in the right margin, at the line's height. Two
            close lines (the limit just above the baseline) would overlap
            their numbers - the second one moves down a row."""
            riadok = 11 * s
            for ine in obsadene:
                if abs(y - ine) < riadok:
                    y = ine - riadok if y <= ine else ine + riadok
            y = min(max(y, 6 * s), spodok)
            obsadene.append(y)
            c.create_text(w - 1 * s, y, text=str(int(round(hodnota))), anchor="e",
                          fill=farba, font=mono(10))

        if self._baseline and lo <= self._baseline <= hi:
            y = y_of(self._baseline)
            c.create_line(0, y, pw, y, fill=pal["text_faint"], width=1)
            popisok(y, self._baseline, pal["text_faint"])
        if self._threshold and lo <= self._threshold <= hi:
            y = y_of(self._threshold)
            c.create_line(0, y, pw, y, fill=pal["danger"], width=1, dash=(4, 4))
            # the number is small text (mono 10) - `danger_text`, not `danger`
            # (the rule in theme.py); the line stays `danger`
            popisok(y, self._threshold, pal["danger_text"])

        krok = pw / float(len(values) - 1)
        body = []
        for i, value in enumerate(values):
            body.extend((i * krok, y_of(value)))
        c.create_line(*body, fill=pal["accent_hover"], width=max(1, round(2 * s)),
                      smooth=True, capstyle="round", joinstyle="round")

        self._draw_triggers(pw, strip_top - 2 * s, s)
        self._draw_activity(pw, strip_top - self.ACT_H - 2, self.ACT_H)
        self._draw_strip(pw, strip_top, strip_h)
        if self._duration > 0:
            zaciatok, koniec = self.os_popisky(self._duration)
            c.create_text(0, h - 2 * s, text=zaciatok, anchor="sw",
                          fill=pal["text_faint"], font=mono(10))
            c.create_text(pw, h - 2 * s, text=koniec, anchor="se",
                          fill=pal["text_faint"], font=mono(10))


# NOTE: there used to be a `MicroChart` class here - a mini chart next to
# the number on a stats card, without axes or scale. Its only job was to
# say "rising / falling / flat".
#
# It went away with the rebuild of the card (`StatCard`): the card is meant
# to be ONE calm figure, and the mini chart with the deviation sentence
# made it three. It had a single caller, so it was left here unused. The
# trend lives on in History, where there is a whole chart for it
# (`Sparkline`, `DayGrid`).


class CueEffectChart(PalCanvas):
    """Effectiveness of the individual cue categories - one row per category.

    WHAT IT DRAWS
    -------------
    The horizontal axis is the heart-rate shift after a cue. Zero is in the
    middle; to the left it dropped, to the right it rose. The bar is the
    estimate, the thin line through it is the 95% interval.

    WHY AN INTERVAL AND NOT A BARE NUMBER
    -------------------------------------
    With six windows, "-4.2 BPM" is a number about as trustworthy as a
    weather forecast for next month. The interval shows it at first glance:
    when the line crosses zero, the difference may even be the opposite.
    Spec 2.1b, B2: "the output should be an estimate with an interval, never
    a bare number".

    WHEN THERE IS LITTLE DATA, NO BAR IS DRAWN AT ALL
    -------------------------------------------------
    Below `measure.MIN_OKIEN` only the number of windows is shown. A bar
    across half the panel would claim something that is not in the data -
    and precisely at the start, when the player opens the chart most often.
    """

    RIADOK = 26          # height of one row in logical px
    POPIS = 84           # width of the category name column

    def __init__(self, master, pal, height=120):
        super().__init__(master, pal, height)
        self._riadky = []
        self._malo_textu = ""

    def set_data(self, riadky, malo_textu=""):
        """`riadky` are (nazov, n, delta_bpm, ci95, dost_dat)."""
        self._riadky = list(riadky or [])
        self._malo_textu = malo_textu or ""
        # `self.height` must go with `configure(height=...)` - `_canvas_size`
        # computes the scale from it; without that the scale would be off
        # after the number of rows changes.
        self.height = max(self.RIADOK * max(1, len(self._riadky)) + 18, 40)
        self.configure(height=self.height)
        self._redraw()

    def _redraw(self):
        c, pal = self.canvas, self.pal
        try:
            c.delete("all")
        except Exception:
            return
        w, h, s = self._canvas_size()
        if w < 60 or not self._riadky:
            return

        popis = self.POPIS * s
        lavo = popis + 8 * s
        pravo = w - 10 * s
        stred = (lavo + pravo) / 2.0
        if pravo - lavo < 40 * s:
            return

        # Scale: the largest value (interval included) should fill half.
        vrchol = 1.0
        for _n, _p, delta, ci, dost in self._riadky:
            if not dost or delta is None:
                continue
            vrchol = max(vrchol, abs(delta) + (ci or 0.0))
        jednotka = (pravo - stred) / vrchol

        # zero axis
        c.create_line(stred, 4 * s, stred, h - 4 * s,
                      fill=pal["border"], width=max(1, round(s)))

        y = 12 * s
        for nazov, n, delta, ci, dost in self._riadky:
            c.create_text(popis, y, text=nazov, anchor="e",
                          fill=pal["text_dim"], font=ui(11))
            if not dost:
                c.create_text(lavo + 4 * s, y, text=self._malo_textu.format(n=n),
                              anchor="w", fill=pal["text_faint"], font=ui(10))
                y += self.RIADOK * s
                continue

            # Negative shift = heart rate dropped = the cue worked.
            dobra = delta < 0
            farba = pal["success"] if dobra else pal["warn"]
            x = stred + delta * jednotka
            c.create_rectangle(min(stred, x), y - 5 * s, max(stred, x), y + 5 * s,
                               fill=farba, outline="")
            if ci:
                c1, c2 = x - ci * jednotka, x + ci * jednotka
                c.create_line(c1, y, c2, y, fill=pal["text_faint"],
                              width=max(1, round(s)))
                for kx in (c1, c2):
                    c.create_line(kx, y - 4 * s, kx, y + 4 * s,
                                  fill=pal["text_faint"], width=max(1, round(s)))
            # number by the app language ("−4,2", not "-4.2" - `i18n.cislo`)
            from i18n import cislo
            c.create_text(pravo, y, text="%s  (n=%d)" % (cislo(delta, 1, sign=True), n),
                          anchor="e",
                          fill=pal["text_faint"], font=mono(10))
            y += self.RIADOK * s


class DayGrid(PalCanvas):
    """Grid of days - a column is a week, a row a day of the week (Monday on
    top), the saturation of a square how much you played that day.

    It shows what no other chart in the app shows: the pattern. Weekends,
    runs of evenings, the week the app lay switched off. So the empty days
    are as important as the full ones and are drawn too.
    """

    # SQUARE SIZE BY WIDTH (0.3 batch 4b). A fixed 12 px drew 26 weeks into
    # ~170 px of a ~1000 px wide panel - the rest was empty space and you had
    # to search for the pattern in tiny squares. The square now grows until
    # the weeks fill the width (`rozmer_bunky`), at most to CELL_MAX - with a
    # few weeks they would otherwise be huge. The gap grows with it
    # (GAP..GAP_MAX), and with them the grid height; the month and day labels
    # follow the same step, so they sit above the columns and next to the rows.
    CELL = 12           # smallest square (narrow window)
    CELL_MAX = 22
    GAP = 3
    GAP_MAX = 5
    LEGEND_H = 18
    # LABELS (0.3, UX audit, batch 4): months above the columns and days on the
    # left. Without them you could not tell from the grid which column is which
    # week or which row is Sunday - the pattern (weekends, evenings) could not
    # be read.
    MONTH_H = 15
    STEPS = 4       # how many shades above "empty day"
    # Which rows carry a day name: Monday, Wednesday, Friday - a seventh label
    # at a 12 px row would merge with its neighbours. From the step
    # VSETKY_DNI_OD (square + gap) on, every day's name fits, Saturday and
    # Sunday too.
    DAY_ROWS = (0, 2, 4)
    VSETKY_DNI_OD = 20

    def __init__(self, master, pal):
        super().__init__(master, pal, self.vyska_mriezky(self.CELL, self.GAP))
        self._days = []
        self._legend = ("", "")
        self._months = ()
        self._weekdays = ()

    def set_days(self, days, legend=("", ""), months=(), weekdays=()):
        """`days` is the output of `hr_stats.day_activity` (oldest first).

        `months` = 12 month abbreviations (January first), `weekdays` = 7 day
        abbreviations (Monday first) - in the APP language, which is why the
        caller supplies them from i18n. Empty = no labels."""
        self._days = list(days or [])
        self._legend = legend
        self._months = tuple(months or ())
        self._weekdays = tuple(weekdays or ())
        self._redraw()

    @staticmethod
    def stlpce_mesiacov(prvy_datum, prvy_den, stlpcov):
        """[(column, month 1..12)] - where a month starts above the grid.

        A month is written above the column that holds its 1st day. The
        first column gets the month of its first day only when at least
        three columns are left until the next label - otherwise two
        abbreviations would overlap."""
        from datetime import timedelta
        vysledok = []
        for stlpec in range(stlpcov):
            for riadok in range(7):
                index = stlpec * 7 + riadok - prvy_den
                if index < 0:
                    continue
                datum = prvy_datum + timedelta(days=index)
                if datum.day == 1:
                    vysledok.append((stlpec, datum.month))
                    break
        if not vysledok or vysledok[0][0] >= 3:
            vysledok.insert(0, (0, prvy_datum.month))
        return vysledok

    @classmethod
    def rozmer_bunky(cls, sirka, stlpcov):
        """(square, gap) in logical px so that `stlpcov` weeks fill `sirka` - the
        square at most CELL_MAX, at least CELL (then the start of the
        history gets cut off, see `_redraw`)."""
        if stlpcov <= 0 or sirka <= 0:
            return float(cls.CELL), float(cls.GAP)
        # gap ~18 % of the step; there is no gap after the last column
        medzera = float(max(cls.GAP, min(cls.GAP_MAX,
                                         round((float(sirka) + cls.GAP) / stlpcov * 0.18))))
        krok = (float(sirka) + medzera) / stlpcov
        bunka = max(float(cls.CELL), min(float(cls.CELL_MAX), krok - medzera))
        return bunka, medzera

    @classmethod
    def vyska_mriezky(cls, bunka, medzera):
        """Height of the element in logical px: months + 7 rows + legend."""
        return int(math.ceil(cls.MONTH_H + 7 * (bunka + medzera) - medzera
                             + cls.LEGEND_H))

    def _mierka(self):
        """The element's DPI scale (physical px / logical) - not from the canvas
        height: the height changes with the width here, so the scale would
        change with it."""
        try:
            return float(self._get_widget_scaling()) or 1.0
        except Exception:
            try:
                return int(self.canvas.winfo_height()) / float(self.height)
            except Exception:
                return 1.0

    def _odtiene(self):
        # shades towards the theme's CALM colour, not towards a universal
        # green - in the indigo theme the grid was the only green island
        return [theme_mod.mix(self.pal["surface_alt"],
                              theme_mod.zone_color(self.pal, "calm"),
                              (i + 1) / float(self.STEPS))
                for i in range(self.STEPS)]

    def _redraw(self):
        pal, c = self.pal, self.canvas
        try:
            w = int(c.winfo_width())
        except Exception:
            return
        if w < 60 or not self._days:
            return
        s = self._mierka()
        c.delete("all")
        odtiene = self._odtiene()
        # The threshold of each shade is a percentile of YOUR days, not a fixed
        # number of minutes - an hour a day is someone's maximum and someone
        # else's warm-up.
        aktivne = sorted(d["seconds"] for d in self._days if d["seconds"] > 0)
        prahy = [aktivne[min(len(aktivne) - 1, int(len(aktivne) * (i + 1) / float(self.STEPS)))]
                 for i in range(self.STEPS)] if aktivne else []
        # The labels are in `text_faint` (>= 4.5:1 in both themes) and ui(10) -
        # the app's smallest content text.
        farba_popisu = pal["text_faint"]
        vrch = self.MONTH_H * s
        # Day column on the left: width by the longest label in this language
        # ("Mon" / "月" / "seg"), not hard-coded - otherwise "lun" would cover
        # the grid. The labels are only measured first; where they go is known
        # only with the step.
        lavo = 0
        popisky_dni = []
        if len(self._weekdays) == 7:
            for riadok in range(7):
                polozka = c.create_text(0, 0, text=self._weekdays[riadok], anchor="w",
                                        fill=farba_popisu, font=ui(10))
                box = c.bbox(polozka)
                if box:
                    lavo = max(lavo, box[2] - box[0])
                popisky_dni.append((riadok, polozka))
            lavo += 6 * s if lavo else 0
        # Square size by the width and the number of weeks (`rozmer_bunky`).
        tyzdnov = max(1, (len(self._days) + self._days[0]["date"].weekday() + 6) // 7)
        bunka, medzera = self.rozmer_bunky((w - lavo) / s, tyzdnov)
        vyska = self.vyska_mriezky(bunka, medzera)
        if vyska != self.height:
            # The height goes with the width: the new one is set and
            # <Configure> redraws.
            self.height = vyska
            try:
                self.configure(height=vyska)
            except Exception:
                pass
        cell, gap = bunka * s, medzera * s
        krok = cell + gap
        # WHOLE PX (UX skeptic 4b): the step is a fraction of the width (e.g.
        # 40.5 px) and Tk draws a smoothed polygon on fractional coordinates
        # with spikes on the edges - big squares had jagged edges. The square's
        # corner goes down to a whole px, the side is rounded; the labels use
        # the same coordinates, so they sit exactly above the column and next
        # to the row.
        strana = max(1, int(round(cell)))

        def px(v):
            return math.floor(v + 1e-6)
        vsetky_dni = bunka + medzera >= self.VSETKY_DNI_OD
        for riadok, polozka in popisky_dni:
            if vsetky_dni or riadok in self.DAY_ROWS:
                c.coords(polozka, 0, px(vrch + riadok * krok) + strana / 2.0)
            else:
                c.delete(polozka)
        # How many weeks fit - and it is the START that gets cut, not the end:
        # today must always be in the grid, even if the history does not fit
        # whole. So the caller can safely send a whole year.
        # (+1e-6: the step is exactly a fraction of the width - 25.9999 weeks
        # is not 25)
        stlpcov = max(1, int((w - lavo + gap) / krok + 1e-6))
        dni = self._days
        for _ in range(3):
            prebytok = len(dni) + dni[0]["date"].weekday() - stlpcov * 7
            if prebytok <= 0:
                break
            dni = dni[prebytok:]
        prvy_den = dni[0]["date"].weekday()
        for i, den in enumerate(dni):
            poradie = i + prvy_den
            x = lavo + (poradie // 7) * krok
            y = vrch + (poradie % 7) * krok
            if x + cell > w + 0.5:
                break
            if den["seconds"] <= 0:
                farba = pal["line_soft"]
            else:
                stupen = sum(1 for p in prahy if den["seconds"] > p)
                farba = odtiene[min(stupen, self.STEPS - 1)]
            x, y = px(x), px(y)
            round_rect(c, x, y, x + strana, y + strana, max(3.0, bunka * 0.2) * s,
                       fill=farba, outline="")
        if len(self._months) == 12:
            pouzite = (len(dni) + prvy_den + 6) // 7
            koniec = -1.0
            for stlpec, mesiac in self.stlpce_mesiacov(dni[0]["date"], prvy_den,
                                                       min(stlpcov, pouzite)):
                x = px(lavo + stlpec * krok)
                if x < koniec:
                    continue            # would overlap the previous abbreviation
                polozka = c.create_text(x, vrch - 3 * s, text=self._months[mesiac - 1],
                                        anchor="sw", fill=farba_popisu, font=ui(10))
                box = c.bbox(polozka)
                koniec = (box[2] if box else x) + 4 * s
        legenda_y = vrch + 7 * krok - gap + (self.LEGEND_H - 6) * s
        menej, viac = self._legend
        polozka = c.create_text(0, legenda_y, text=menej, anchor="sw",
                                fill=pal["text_faint"], font=ui(10))
        # The legend squares after the word "menej" by its real width -
        # "weniger" / "меньше" are wider than the Slovak "menej".
        box = c.bbox(polozka)
        x = max(46 * s, (box[2] + 6 * s) if box else 0)
        for farba in [pal["line_soft"]] + odtiene:
            x0, y0 = px(x), px(legenda_y - 10 * s)
            round_rect(c, x0, y0, x0 + int(round(10 * s)), y0 + int(round(10 * s)), 2 * s,
                       fill=farba, outline="")
            x += 13 * s
        c.create_text(x + 3 * s, legenda_y, text=viac, anchor="sw",
                      fill=pal["text_faint"], font=ui(10))


class StatList(ctk.CTkFrame):
    """A "name ... value" list with divider lines and a fixed order."""

    def __init__(self, master, pal):
        super().__init__(master, fg_color="transparent")
        self.pal = pal
        self._values = {}

    def add(self, key, name, value="-"):
        pal = self.pal
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkLabel(row, text=name, font=ui(12), text_color=pal["text_dim"],
                     anchor="w").pack(side="left", pady=7)
        label = ctk.CTkLabel(row, text=str(value), font=mono(13),
                             text_color=pal["text"], anchor="e")
        label.pack(side="right", pady=7)
        linka(self, pal).pack(fill="x")
        self._values[key] = label
        return label

    def set(self, key, value):
        label = self._values.get(key)
        if label is not None:
            try:
                label.configure(text=str(value))
            except Exception:
                pass


# --------------------------------------------------------------------------
# StatCard - one selectable statistic on the Today page (2x2 grid)
# --------------------------------------------------------------------------

class StatCard(ctk.CTkFrame):
    """Card for one metric: a BIG coloured number and a one-word label under
    it. ⓘ expands a short explanation, ✕ (only when hovering over the card)
    removes it from the selection. A card can be grabbed (number, label or
    edge - not ⓘ/✕) and dropped on another: they swap places (`on_drag`,
    the app decides).

    The number's colour is the metric's identity - the same colour as the
    dot in the selection in `_build_dnes_page`, so the player can connect
    the card and the item in the selection even without reading the text.
    It is held as a palette TOKEN, not as a value: on a theme change the
    card can find it by itself (`set_pal`).

    WHY THE NUMBER ON TOP AND THE LABEL BELOW
    -----------------------------------------
    Until 2.1 it was the other way round: the label on top
    (`metric.*.title`, a whole phrase like "POKOJOVA ZAKLADNA" - RESTING
    BASELINE), the number under it, a second line under that, and a mini
    chart on the right. That had two problems at once:
      - The card read like a table row, not like one figure.
      - `title` is long, and in German, French and Russian it widened the
        whole right column at the expense of the centre, where the mark
        is. Measured: the centre dropped from 659 to 554 px, i.e. by as
        much as 105 px, and the text was NOT clipped in the process - the
        mark paid for it.
    Now the label carries the key `metric.*.tag` - one word ("pokoj",
    "zotavenie" - calm, recovery) that does not grow with the language.

    That makes ⓘ MORE important, not less: "POKOJ" (CALM) on its own does
    not say what it is about, and that holds in all languages.

    NOTE: the mini chart of the last sessions and the deviation sentence
    left this place (`set_trend`, `MicroChart`). It was an honest idea -
    "62 BPM" says nothing until you know what is usual for you - but on a
    card meant to be one calm figure, that was three figures. The trend
    belongs in History, where there is a whole chart for it.
    """

    def __init__(self, master, pal, color_token, tag, value, info_text,
                on_remove=None, on_drag=None):
        super().__init__(master, fg_color=pal["surface"], corner_radius=RADIUS_PANEL,
                         border_width=1, border_color=pal["line_soft"])
        self.pal = pal
        self.color_token = color_token

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=13, pady=11)

        self.value_label = ctk.CTkLabel(body, text=str(value), font=display(22),
                                        text_color=pal[color_token], anchor="w")
        self.value_label.pack(fill="x")

        # The label and the controls are on one row UNDER the number. ✕ is on
        # the right, ⓘ right after the text - it belongs to the label, not to
        # the corner.
        head = ctk.CTkFrame(body, fg_color="transparent")
        head.pack(fill="x", pady=(2, 0))
        self.tag_label = ctk.CTkLabel(head, text=tag.upper(), font=ui(10, "bold"),
                                      text_color=pal["text_faint"], anchor="w")
        self.tag_label.pack(side="left")
        self._info_btn = ctk.CTkButton(
            head, text="ⓘ", width=16, height=16, corner_radius=8,
            fg_color="transparent", hover_color=pal["surface_alt"],
            text_color=pal["text_faint"], font=ui(10), command=self._toggle_info)
        self._info_btn.pack(side="left", padx=(5, 0))

        self._remove_btn = None
        if on_remove is not None:
            self._remove_btn = ctk.CTkButton(
                head, text="✕", width=16, height=16, corner_radius=8,
                fg_color="transparent", hover_color=pal["surface_alt"],
                text_color=pal["text_faint"], font=ui(10), command=on_remove)
        # Enter/Leave always: shows ✕ (if there is one) and above all closes
        # the ⓘ popup when the cursor leaves the card.
        for widget in (self, body, head):
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)

        # The ⓘ explanation NO LONGER EXPANDS inside the card, it shows in a
        # floating popup. An inline expansion grows the card -> the stats grid
        # -> and since the centre (dojo/enso) is in the same grid row, the
        # whole hero suddenly grew on a click on ⓘ (especially in
        # Russian/German, where the text is long). The popup has no effect on
        # the page layout.
        self._info_text = info_text
        self._info_pop = None
        self.bind("<Destroy>", lambda _e: self._close_info())

        # Drag to move. The card only REPORTS press / motion / release; what
        # to do with it (swap, save) is up to the app. It binds only to the
        # card's surfaces, NEVER to ⓘ and ✕ - those are buttons and must click
        # normally. After a press Tk sends motion and release to the widget
        # that got the press (implicit grab), so no global grab is needed.
        if on_drag is not None:
            def _press(event):
                self._close_info()
                on_drag("press", event)
            for widget in (self, body, head, self.value_label, self.tag_label):
                widget.bind("<ButtonPress-1>", _press)
                widget.bind("<B1-Motion>", lambda e: on_drag("move", e))
                widget.bind("<ButtonRelease-1>", lambda e: on_drag("release", e))

    def set_drag_look(self, role=None):
        """Border while dragging: 'source' = the card you are holding, 'target'
        = the card it will swap places with. None = the normal border."""
        color = {"source": "accent", "target": "accent_hover"}.get(role, "line_soft")
        try:
            self.configure(border_color=self.pal[color])
        except Exception:
            pass

    def set_value(self, value):
        try:
            self.value_label.configure(text=str(value))
        except Exception:
            pass

    def set_pal(self, pal):
        """The number holds its colour as a value, not as a widget option -
        after a theme change it has to take it from the new palette by
        itself."""
        self.pal = pal
        try:
            self.value_label.configure(text_color=pal[self.color_token])
        except Exception:
            pass

    def _toggle_info(self):
        if self._info_pop is not None:
            self._close_info()
            return
        pop = priprav_popup(tk.Toplevel(self))
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        pop.configure(bg=self.pal["line_soft"])
        frame = ctk.CTkFrame(pop, fg_color=self.pal["surface_alt"], corner_radius=8,
                             border_width=1, border_color=self.pal["line_soft"])
        frame.pack(fill="both", expand=True, padx=1, pady=1)
        ctk.CTkLabel(frame, text=self._info_text, font=ui(10),
                     text_color=self.pal["text_dim"], anchor="w", justify="left",
                     wraplength=250).pack(padx=12, pady=10)
        self._info_pop = pop
        pop.update_idletasks()
        bx = self._info_btn.winfo_rootx()
        by = self._info_btn.winfo_rooty() + self._info_btn.winfo_height() + 4
        try:
            pw, ph = pop.winfo_reqwidth(), pop.winfo_reqheight()
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            if bx + pw > sw - 8:
                bx = max(8, sw - pw - 8)
            if by + ph > sh - 8:            # does not fit below -> move above the button
                by = max(8, self._info_btn.winfo_rooty() - ph - 4)
        except Exception:
            pass
        pop.geometry(f"+{int(bx)}+{int(by)}")
        # Close the popup when it loses focus (a click elsewhere, the Ctrl+K
        # command palette, minimising to the tray) or when it is clicked.
        # Pages are not rebuilt (place+tkraise), so without this the popup
        # would stay floating over the new page or the desktop after
        # switching without moving the mouse.
        pop.bind("<FocusOut>", lambda _e: self._close_info())
        pop.bind("<Button-1>", lambda _e: self._close_info())
        try:
            pop.focus_set()
        except Exception:
            pass

    def _close_info(self):
        pop, self._info_pop = self._info_pop, None
        if pop is not None:
            try:
                pop.destroy()
            except Exception:
                pass

    def _on_enter(self, _event=None):
        if self._remove_btn is not None and not self._remove_btn.winfo_ismapped():
            self._remove_btn.pack(side="right")

    def _on_leave(self, _event=None):
        # Leave also arrives when moving onto our own child - react only once
        # the cursor has really left the whole card (same trick as
        # _NavRow._leave).
        if self._still_inside():
            return
        if self._remove_btn is not None:
            self._remove_btn.pack_forget()
        self._close_info()

    def _still_inside(self):
        try:
            px, py = self.winfo_pointerxy()
            x0, y0 = self.winfo_rootx(), self.winfo_rooty()
            return (x0 <= px < x0 + self.winfo_width()
                    and y0 <= py < y0 + self.winfo_height())
        except Exception:
            return False


# --------------------------------------------------------------------------
# QrReveal - a QR mark that reveals the code only on a click
# --------------------------------------------------------------------------

class QrReveal(ctk.CTkFrame):
    """QR pictogram + label; the real code expands BELOW it only on a click.

    A real QR has to be a white square with sharp modules, otherwise the
    phone cannot read it - and a white square is the loudest thing a dark
    panel can contain. Yet most people do not even need it: whoever already
    has the app on the phone does not want to see the code at all. So on
    the outside there is only a mark drawn with the same brush as the app's
    other pictograms (`hud_paint.render_slot_icon("qr")`), in the theme
    accent.

    The image is loaded only on the first open - until someone clicks, the
    app does not even open the file.
    """

    ICON = 40

    def __init__(self, master, pal, codes, show_label, hide_label, size=150):
        """`codes` is [(path to PNG, label)] - as many codes, as many columns
        side by side (Android and iOS are two different apps, so two
        codes)."""
        super().__init__(master, fg_color="transparent")
        self.pal = pal
        self._codes = [c for c in codes if c and os.path.exists(c[0])]
        self._size = size
        self._show_label, self._hide_label = show_label, hide_label
        self._open = False
        self._built = False
        self._photos = []
        self._captions = []

        self.toggle = ctk.CTkButton(
            self, text="  " + show_label, image=self._icon(pal), compound="left",
            anchor="w", height=self.ICON + 10, corner_radius=RADIUS_CONTROL,
            fg_color="transparent", hover_color=pal["surface_alt"],
            text_color=pal["accent_hover"], font=ui(11), command=self._flip)
        self.toggle.pack(anchor="w")

        self.holder = ctk.CTkFrame(self, fg_color="transparent")

    def _icon(self, pal):
        try:
            import hud_paint      # lazy: ui_kit is also imported without a GUI
            img = hud_paint.render_slot_icon("qr", self.ICON, hud_paint.Style(pal))
            self._icon_photo = ctk.CTkImage(light_image=img, dark_image=img,
                                            size=(self.ICON, self.ICON))
            return self._icon_photo
        except Exception:
            return None

    def _build_codes(self):
        """The codes are loaded and built only on the first open - until
        someone clicks, the app does not even open the files."""
        from PIL import Image as PILImage
        pal = self.pal
        for cesta, popis in self._codes:
            stlpec = ctk.CTkFrame(self.holder, fg_color="transparent")
            stlpec.pack(side="left", anchor="n", padx=(0, 16))
            img = PILImage.open(cesta).convert("RGB")
            photo = ctk.CTkImage(light_image=img, dark_image=img,
                                 size=(self._size, self._size))
            self._photos.append(photo)          # keep a reference, otherwise GC
            ctk.CTkLabel(stlpec, text="", image=photo).pack(anchor="w",
                                                            pady=(6, 4))
            popisok = ctk.CTkLabel(stlpec, text=popis, font=ui(10),
                                   text_color=pal["text_faint"], anchor="w",
                                   justify="left", wraplength=self._size + 30)
            popisok.pack(anchor="w")
            self._captions.append(popisok)

    def _flip(self):
        if self._open:
            self.holder.pack_forget()
            self.toggle.configure(text="  " + self._show_label)
            self._open = False
            return
        # our own flag, not `winfo_children()` - `holder` may have children
        # right from the constructor and a "has no children" test would never
        # hold (it happened)
        if not self._built:
            try:
                self._build_codes()
            except Exception:
                return      # a missing image must not crash the dialog
            self._built = True
        self.holder.pack(fill="x", anchor="w")
        self.toggle.configure(text="  " + self._hide_label)
        self._open = True

    def set_pal(self, pal):
        """The mark is an image with the colour baked in - after a theme change
        it has to be redrawn (`DandurfApp._recolor_ui` walks the tree
        itself)."""
        self.pal = pal
        try:
            self.toggle.configure(image=self._icon(pal),
                                  text_color=pal["accent_hover"],
                                  hover_color=pal["surface_alt"])
            for popisok in self._captions:
                popisok.configure(text_color=pal["text_faint"])
        except Exception:
            pass


# --------------------------------------------------------------------------
# SubNav - tabs at the top of a group page (Settings)
# --------------------------------------------------------------------------

class SubNav(ctk.CTkFrame):
    """A row of tabs above the content - Cues | Sound | General.

    After feedback the side menu has only 3 main items; everything else is
    tabs here. Every tab has a key that is also the page key, so
    `app.navigate(key)` works for tabs the same as for the main items. A
    badge (number of triggers, sensor dot) is attached to the tab text.

    TABS ARE TEXT, NOT CHIPS (0.3, UX audit). A bordered chip meant four
    different things in the app at once (tab, filter, action, link), so the
    tabs did not look like tabs. Now a tab is bare text and the active one
    is marked by a 2 px line in `accent` under it plus full `text` - two
    signals, not just colour. The caller sets the left edge of the row
    (`PAGE_GUTTER`)."""

    LINE_H = 2

    def __init__(self, master, pal, items, on_select):
        """items: [(key, label)]"""
        super().__init__(master, fg_color="transparent")
        self.pal = pal
        self.on_select = on_select
        self.buttons = {}
        self._lines = {}
        self._labels = {}
        self._badges = {}
        self.active = None
        for poradie, (key, label) in enumerate(items):
            tab = ctk.CTkFrame(self, fg_color="transparent", width=1, height=1)
            # the first tab starts exactly at the page's left edge, the next
            # ones are 20 px apart - text without a border needs air, not a
            # border
            tab.pack(side="left", padx=(0 if poradie == 0 else 20, 0))
            btn = ctk.CTkButton(
                tab, text=label, height=30, width=0, corner_radius=RADIUS_CONTROL,
                border_width=0, fg_color="transparent",
                hover_color=pal["surface_alt"], text_color=pal["text_dim"],
                font=ui(13), command=lambda k=key: self.select(k))
            btn.pack(side="top")
            # width=1: otherwise CTkFrame asks for the default 200 px and
            # every tab would be 200 px wide regardless of the text
            line = ctk.CTkFrame(tab, fg_color="transparent", height=self.LINE_H,
                                width=1, corner_radius=0)
            line.pack(side="top", fill="x", padx=8)
            self.buttons[key] = btn
            self._lines[key] = line
            self._labels[key] = label

    def select(self, key, notify=True):
        self.set_active(key)
        if notify and callable(self.on_select):
            self.on_select(key)

    def set_active(self, key):
        self.active = key
        pal = self.pal
        for k, btn in self.buttons.items():
            active = (k == key)
            try:
                btn.configure(text_color=pal["text"] if active else pal["text_dim"])
                self._lines[k].configure(
                    fg_color=pal["accent"] if active else "transparent")
            except Exception:
                pass

    def set_pal(self, pal):
        """Recolours the line and the text of the active tab from the new
        palette (on a theme change) - the active state is computed from
        `self.pal`, not from the widget."""
        self.pal = pal
        self.set_active(self.active)

    def set_badge(self, key, text=""):
        btn = self.buttons.get(key)
        if btn is None:
            return
        self._badges[key] = str(text or "")
        suffix = f"   {self._badges[key]}" if self._badges[key] else ""
        try:
            btn.configure(text=f"{self._labels[key]}{suffix}")
        except Exception:
            pass


# --------------------------------------------------------------------------
# Info row for a metric: a sentence by the number + an expandable "what it
# means"
# --------------------------------------------------------------------------

class InfoRow(ctk.CTkFrame):
    """A short text under a metric and a "ⓘ what it means" toggle that
    expands 2-3 sentences for the player. The texts are in i18n
    (metric.<id>.short / .more) - here they are only assembled; no app
    logic.

    Why expanding and not a tooltip: a tooltip is visible only with the
    mouse over the question mark, and the player usually never finds it.
    The sentence by the number is always visible, the details are one click
    away and stay open."""

    def __init__(self, master, pal, short, more, more_label, less_label, wrap=420,
                 title=None):
        super().__init__(master, fg_color="transparent")
        self.pal = pal
        self._more_label, self._less_label = more_label, less_label
        self._open = False
        # The metric name above the sentence (optional): three explanations
        # one under another without a name were three identical "ⓘ what it
        # means" with no addressee.
        if title:
            ctk.CTkLabel(self, text=title, font=ui(11, "bold"), text_color=pal["text"],
                         anchor="w", justify="left", wraplength=wrap).pack(fill="x")
        # The sentence is content, not decoration - `text_dim` (>= 4.5:1).
        ctk.CTkLabel(self, text=short, font=ui(11), text_color=pal["text_dim"],
                     anchor="w", justify="left", wraplength=wrap).pack(fill="x")
        self.toggle = ctk.CTkButton(
            self, text=more_label, height=22, corner_radius=RADIUS_CONTROL, anchor="w",
            fg_color="transparent", hover_color=pal["surface_alt"],
            text_color=pal["accent_hover"], font=ui(10), command=self._flip)
        self.toggle.pack(anchor="w", pady=(2, 0))
        self.more = ctk.CTkLabel(self, text=more, font=ui(11), text_color=pal["text_dim"],
                                 anchor="w", justify="left", wraplength=wrap)

    def _flip(self):
        self._open = not self._open
        if self._open:
            self.more.pack(fill="x", pady=(2, 4))
            self.toggle.configure(text=self._less_label)
        else:
            self.more.pack_forget()
            self.toggle.configure(text=self._more_label)

    @property
    def is_open(self):
        return self._open


# --------------------------------------------------------------------------
# Our own title bar for dialogs (no OS frame)
# --------------------------------------------------------------------------

DIALOG_RAM_TOKEN = "rule"


def nastav_ram_okna(top, pal):
    """A 1 px border around a dialog window in the colour
    `pal[DIALOG_RAM_TOKEN]`.

    Tk `highlightthickness` on the window itself: the border is INSIDE the
    window and the content (pack) comes only after it, so nothing covers
    it. `highlightcolor` (window with focus) and `highlightbackground`
    (without focus) have the same colour - the border does not change on a
    click. Called via `tk.Misc.configure` because `CTkToplevel.configure`
    does not know `highlightcolor`. Never raises an exception."""
    try:
        farba = pal[DIALOG_RAM_TOKEN]
        tk.Misc.configure(top, highlightthickness=1, highlightbackground=farba,
                          highlightcolor=farba)
    except Exception:
        pass


class DialogChrome:
    """Gives a dialog (CTkToplevel) its own title bar like the main window has.

    Why it exists
    -------------
    The app's main window runs without an OS frame (overrideredirect=True)
    with its own title bar. The dialogs, however, were plain CTkToplevel
    WITH an OS frame, so above "About" and co. the Windows title bar showed
    through - an element the main window does not have, so it felt
    foreign.

    The solution is the same as for the main window: overrideredirect(True)
    + our own title bar with the name and a close button + dragging by it.
    So that a modal dialog (grab_set) with the frame turned off works
    reliably, we restore the override after every <Map> (the same pattern
    as enable_frameless for the root).

    CAREFUL WHEN CHECKING ON WINDOWS: a borderless modal window is delicate
    in Tk. Check that it can be dragged by the title bar, that it can be
    closed with the cross and with Escape, and that the dialog does not
    disappear after minimising the main window and coming back. If the
    override on a modal window caused problems (window without focus /
    cannot be dragged), change `_FRAMELESS` below to False - the dialog
    then keeps the OS frame (cosmetically worse, but reliable).
    """

    _FRAMELESS = True    # False = keep the OS frame (fallback, if the override misbehaves)

    def __init__(self, top, pal, title, on_close, closable=True):
        """`closable=False` = no cross and no Escape - for windows that must not
        be closed "into nothing" (onboarding). `on_close` is not called
        then."""
        self.top = top
        self.pal = pal
        self.on_close = on_close
        self.closable = bool(closable)
        self.close_btn = None
        self._drag = None

        if self._FRAMELESS:
            try:
                top.overrideredirect(True)
                # restore the override after coming back from minimised (like
                # root) and after every showing pin it to the main window
                # again - Tk drops the owner when restoring overrideredirect
                top.bind("<Map>", lambda _e: (top.overrideredirect(True),
                                              pripni_k_vlastnikovi(top)), add="+")
            except Exception:
                pass

        # WINDOW BORDER 1 px (0.3 batch 4b). A window without an OS frame had
        # the `bg` background like the main window behind it - a dialog over
        # the dark app had no edge and blended into it. `rule` is the token
        # for a surface edge (>= 1.5:1, see theme.py), not a control: the
        # window border should not look like a button. The Tk window draws it
        # itself (highlight), so it goes around all the content and does not
        # depend on what anyone packs into the window.
        nastav_ram_okna(top, pal)

        bar = ctk.CTkFrame(top, fg_color=pal["bg"], height=34, corner_radius=0)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)
        self.bar = bar

        # WARNING: the font size MUST be a number, not a string. customtkinter
        # multiplies it by a float when scaling, so ui("11") ends in
        # TypeError: can't multiply sequence by non-int of type 'float'
        # and the whole dialog does not open.
        self.title_label = ctk.CTkLabel(bar, text=title, font=ui(11),
                                        text_color=pal["text_dim"], anchor="w")
        self.title_label.pack(side="left", padx=14)
        if self.closable:
            self.close_btn = ctk.CTkButton(
                bar, text="✕", width=40, height=34, corner_radius=0,
                fg_color="transparent", hover_color=pal["danger"],
                text_color=pal["text_dim"], font=ui(12), command=on_close)
            self.close_btn.pack(side="right")

        rule = linka(top, pal)
        rule.pack(fill="x", side="top")

        # dragging by the bar - also by its label (the label covers most of it)
        for widget in (bar, self.title_label):
            widget.bind("<ButtonPress-1>", self._begin)
            widget.bind("<B1-Motion>", self._move)
        # Escape closes the dialog (even when it has no OS cross). But the
        # bind alone is NOT ENOUGH: keys go to the window that has focus, and
        # after opening that stayed on the main window - so Escape never got
        # here. We set focus with a small delay, because CTkToplevel withdraws
        # and deiconifies itself in __init__ (because of the dark title bar)
        # and an immediate focus_force would override that trick.
        def _take_focus():
            try:
                pripni_k_vlastnikovi(top)   # otherwise the main window can cover it
                top.lift()
                top.focus_force()
            except Exception:
                pass          # the dialog was closed meanwhile

        try:
            if self.closable:
                top.bind("<Escape>", lambda _e: on_close())
            top.after(10, _take_focus)
        except Exception:
            pass

        # POSITION (0.3, UX audit). A dialog that did not set its size
        # itself via `umiestni_dialog` (its content gives it the size: new
        # profile, import, recording, colour picker...) is centred in the
        # work area of the monitor under the cursor once its content is
        # built. Tk puts a borderless window without a position into the top
        # left corner of the main monitor.
        def _vycentruj():
            if not getattr(top, "_zanshin_umiestnene", False):
                vycentruj_podla_obsahu(top)

        try:
            top.after(15, _vycentruj)
        except Exception:
            pass

        self.body = ctk.CTkFrame(top, fg_color="transparent")
        self.body.pack(fill="both", expand=True)

    def _begin(self, event):
        self._drag = (event.x_root, event.y_root,
                      self.top.winfo_x(), self.top.winfo_y())

    def _move(self, event):
        if not self._drag:
            return
        sx, sy, wx, wy = self._drag
        self.top.geometry(f"+{wx + event.x_root - sx}+{wy + event.y_root - sy}")


# --------------------------------------------------------------------------
# App windows instead of system ones (confirm / notify / choose)
# --------------------------------------------------------------------------
#
# WHY (0.3, UX audit): a white system window in a dark app had buttons in
# the Windows language ("Ano / Nie"), not the app's, and looked like
# another program. All three functions build the same window
# (`_okno_appky`): our own title bar (DialogChrome), text wrapped at
# DIALOG_TEXT_W, buttons at the bottom right, centred in the work area and
# entirely on it. The system window remains only a FALLBACK - when the app
# window cannot be built (no main window, TclError).

DIALOG_TEXT_W = 440       # text wrap in the app window (logical px)
DIALOG_MIN_W = 400        # a short notice should not be a narrow strip


class _OknoSaNedaPostavit(Exception):
    """The app window cannot be built - the caller shows a system window."""


def _systemove_okno(druh, title, text):
    """FALLBACK: a Windows system window. `druh` "yesno" returns True/False,
    "warning" / "error" / "info" return None. Never raises an exception."""
    try:
        if druh == "yesno":
            return bool(messagebox.askyesno(title, text))
        {"warning": messagebox.showwarning,
         "error": messagebox.showerror}.get(druh, messagebox.showinfo)(title, text)
    except Exception:
        pass
    return False if druh == "yesno" else None


def _vlastnik_pouzitelny(owner):
    """Can a visible modal window be built over `owner`?

    Not without a main window. And not over a window hidden in the tray
    either: `transient` inherits the owner's state, so the dialog would
    stay hidden with a grab - the app would wait for an answer nobody sees.
    A fake without these methods (tests) counts as usable."""
    if owner is None:
        return False
    try:
        if hasattr(owner, "winfo_exists") and not owner.winfo_exists():
            return False
        if hasattr(owner, "winfo_viewable") and not owner.winfo_viewable():
            return False
    except Exception:
        return False
    return True


def _okno_appky(owner, pal, title, text, tlacidla, zrusit, fokus):
    """A modal app window with text and buttons; returns the clicked value.

    `tlacidla` = [(hodnota, text, druh), ...] left to right, `druh` from
    `BUTTON_KINDS`. Escape, the cross and a failed wait = `zrusit`. Enter
    presses the focused button - and after opening, focus is on the one
    with the value `fokus` (the safe one: Enter by mistake must not delete
    or quit anything).

    When the window cannot be built, it raises `_OknoSaNedaPostavit`."""
    if pal is None or not _vlastnik_pouzitelny(owner):
        raise _OknoSaNedaPostavit("bez pouzitelneho hlavneho okna")
    vysledok = {"hodnota": zrusit}
    top = None
    hotove = []               # (hodnota, tlacidlo) right to left

    def zavri(hodnota):
        vysledok["hodnota"] = hodnota
        try:
            top.grab_release()
        except Exception:
            pass
        try:
            top.destroy()
        except Exception:
            pass

    try:
        top = ctk.CTkToplevel(owner)
        top.title(title)
        top.configure(fg_color=pal["bg"])
        top.resizable(False, False)
        top.protocol("WM_DELETE_WINDOW", lambda: zavri(zrusit))
        chrome = DialogChrome(top, pal, title, on_close=lambda: zavri(zrusit))
        # The footer is packed FIRST and to the bottom: when the text is taller
        # than fits on the area, the text gets clipped, not the buttons.
        paticka = ctk.CTkFrame(chrome.body, fg_color="transparent")
        paticka.pack(side="bottom", fill="x", padx=24, pady=(0, 18))
        telo = ctk.CTkFrame(chrome.body, fg_color="transparent")
        telo.pack(fill="both", expand=True, padx=24, pady=(18, 16))
        ctk.CTkLabel(telo, text=text, font=ui(12), text_color=pal["text"],
                     anchor="w", justify="left",
                     wraplength=DIALOG_TEXT_W).pack(fill="x")
        for hodnota, popis, druh in reversed(list(tlacidla)):
            tlacidlo = button(paticka, pal, popis, kind=druh,
                              command=lambda h=hodnota: zavri(h))
            tlacidlo.pack(side="right", padx=(0, 8) if hotove else 0)
            hotove.append((hodnota, tlacidlo))
    except Exception as exc:
        if top is not None:
            try:
                top.destroy()
            except Exception:
                pass
        raise _OknoSaNedaPostavit(str(exc)) from exc

    def enter(_e=None):
        try:
            meno = str(top.focus_get() or "")
        except Exception:
            meno = ""
        for hodnota, tlacidlo in hotove:
            cesta = str(tlacidlo)
            if meno and (meno == cesta or meno.startswith(cesta + ".")):
                zavri(hodnota)
                return "break"
        zavri(fokus)
        return "break"

    def umiestni():
        # The content gives the size; `umiestni_dialog` shrinks it to the work
        # area and puts it in its centre (otherwise a borderless window would
        # stand in the corner).
        top.update_idletasks()
        try:
            mierka = float(top._get_window_scaling() or 1.0)
        except Exception:
            mierka = 1.0
        sirka = int(top.winfo_reqwidth() / mierka) + 1
        vyska = int(top.winfo_reqheight() / mierka) + 1
        umiestni_dialog(top, owner, max(sirka, DIALOG_MIN_W), vyska)

    fokus_tlacidlo = next((t for h, t in hotove if h == fokus), None)
    # A notice above ANOTHER modal dialog (recording, cue settings) takes its
    # grab; after closing it has to be given back, otherwise that dialog would
    # stop being modal. The system messagebox did that by itself.
    try:
        predosly_grab = top.grab_current()
    except Exception:
        predosly_grab = None
    # Each step separately: when only `grab_set` fails (another grab, the
    # window not mapped yet), the dialog IS already on screen - if `zrusit`
    # were returned right away, it would stay there with a button that does
    # nothing. Without a grab the dialog is just non-modal; the answer is
    # waited for anyway.
    kroky = [lambda: top.bind("<Return>", enter),
             lambda: top.bind("<KP_Enter>", enter),
             umiestni,
             lambda: top.transient(owner), top.grab_set]
    if fokus_tlacidlo is not None:
        kroky.append(lambda: top.after(30, fokus_tlacidlo.focus_set))
    for krok in kroky:
        try:
            krok()
        except Exception:
            pass
    try:
        owner.wait_window(top)
    except Exception:
        zavri(zrusit)         # we did not wait - an invisible "yes" must not remain
        return zrusit
    if predosly_grab is not None:
        try:
            if predosly_grab.winfo_exists():
                predosly_grab.grab_set()
        except Exception:
            pass
    return vysledok["hodnota"]


def confirm(owner, pal, title, text, ok_label, cancel_label, danger=False):
    """A yes/no question in an app window (DialogChrome), not a system
    messagebox.

    The buttons carry the action verb (`ok_label`); a destructive action is
    `danger`, not the main button. Focus and Enter are on "no"
    (`cancel_label`) - Enter by mistake must not delete. Escape and the
    cross = no. Modal: returns True/False only after closing. When the app
    window cannot be built, it asks with a system window."""
    try:
        return bool(_okno_appky(
            owner, pal, title, text,
            [(True, ok_label, "danger" if danger else "primary"),
             (False, cancel_label, "secondary")],
            zrusit=False, fokus=False))
    except _OknoSaNedaPostavit:
        return _systemove_okno("yesno", title, text)


def notify(owner, pal, title, text, ok_label=None, kind="info"):
    """A notice in an app window instead of messagebox.showinfo /
    showwarning / showerror. One button (`ok_label`, otherwise "OK" in the
    app language); Enter, Escape and the cross close it. Modal - returns
    after closing.

    `kind` ("info" / "warning" / "error") decides only about the system
    window shown when the app window cannot be built. The app window looks
    the same for all three: calm, without an exclamation mark - the
    sentence carries the severity."""
    if ok_label is None:
        try:
            from i18n import tr
            ok_label = tr("dialog.ok")
        except Exception:
            ok_label = "OK"
    try:
        _okno_appky(owner, pal, title, text, [(True, ok_label, "primary")],
                    zrusit=None, fokus=True)
    except _OknoSaNedaPostavit:
        _systemove_okno(kind, title, text)


def choose(owner, pal, title, text, choices, cancel=None, default=None):
    """A choice from several buttons in an app window.

    `choices` = [(hodnota, text, druh), ...] left to right. Escape and the
    cross return `cancel` (nothing happens), Enter and the focus after
    opening belong to `default`. When the app window cannot be built, it
    says the text with a system window and returns `default` - the safe
    choice that deletes or quits nothing."""
    try:
        return _okno_appky(owner, pal, title, text, choices,
                           zrusit=cancel, fokus=default)
    except _OknoSaNedaPostavit:
        _systemove_okno("info", title, text)
        return default


# --------------------------------------------------------------------------
# Blocking the mouse wheel on sliders
# --------------------------------------------------------------------------

def block_slider_wheel(slider):
    """Stops a slider from changing its value with the mouse wheel.

    Why it exists
    -------------
    CTkSlider reacts to the mouse wheel by default. But sliders tend to sit
    on scrollable pages (e.g. the slot detail, the visual settings) - when
    the player only wants to scroll the content down and the cursor passes
    over a slider, they change the value by mistake. The classic "stolen
    scroll".

    Solution: we catch the wheel events on the slider and instead of
    changing the value we PASS THEM ON to the parent scrollframe (so the
    page still scrolls). The slider can then only be changed by dragging,
    exactly as it should.

    Covers Windows/Mac (<MouseWheel>) and Linux/X11 (<Button-4/5>).

    WHY IT BINDS TO `slider._canvas`, NOT VIA `slider.bind()`
    ---------------------------------------------------------
    `CTkSlider.bind()` always ADDS (add=True) and deliberately refuses
    anything else, so the internal wheel handler (`_mouse_scroll_event`)
    stays first in order. Tk runs a widget's handlers in the order they
    were added - the internal one CHANGED the value before our
    `return "break"` even got its turn. Checked live (ctk 6.0, Tk 9.0): the
    wheel changed the value even with the wrapper. A plain
    `tkinter.Canvas.bind` without `add` replaces the internal handler.
    """
    def _redirect(event):
        widget = slider.master
        # find the nearest parent canvas of a scrollframe and scroll it
        while widget is not None:
            if isinstance(widget, ctk.CTkScrollableFrame):
                canvas = getattr(widget, "_parent_canvas", None)
                if canvas is not None:
                    try:
                        # the same steps as CTkScrollableFrame: on Windows the
                        # canvas has yscrollincrement=1 px, so 1 "unit" per
                        # notch would barely move the page
                        if getattr(event, "num", None) == 4:
                            canvas.yview_scroll(-1, "units")
                        elif getattr(event, "num", None) == 5:
                            canvas.yview_scroll(1, "units")
                        elif sys.platform.startswith("win"):
                            canvas.yview_scroll(-int(event.delta / 6), "units")
                        elif sys.platform == "darwin":
                            canvas.yview_scroll(-int(event.delta), "units")
                        else:
                            canvas.yview_scroll(int(-event.delta / 120), "units")
                    except Exception:
                        pass
                break
            widget = getattr(widget, "master", None)
        return "break"      # NEVER let the slider handle the wheel

    canvas = getattr(slider, "_canvas", None)
    for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        if canvas is not None:
            canvas.bind(seq, _redirect)      # REPLACES the internal handler
        else:
            slider.bind(seq, _redirect)
    return slider


def slider(master, pal, **kw):
    """The app's one and only slider: track `switch_off`, the filled part and
    the knob `accent`, wheel blocked (`block_slider_wheel`).

    WHY (0.3, UX audit, batch 4): in the "Fine-tune picture size and
    position" window the X/Y sliders had a dark `accent2` fill and the size
    slider right above them a gold one - two styles in one card, and X/Y
    looked disabled. Sizes and range can be overridden via `kw`, colours
    only deliberately (e.g. an unfilled slider in the questionnaire that
    only the first touch colours in)."""
    style = {"progress_color": pal["accent"], "button_color": pal["accent"],
             "button_hover_color": pal["accent_hover"],
             "fg_color": pal["switch_off"]}
    style.update(kw)
    return block_slider_wheel(ctk.CTkSlider(master, **style))
