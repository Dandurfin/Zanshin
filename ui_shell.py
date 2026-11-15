"""
ui_shell.py — building blocks of the Zanshin window: a custom title
bar without the OS frame, sidebar navigation, the page container, the
command palette (Ctrl+K). Deliberately kept separate from app.py, which
assembles them in `DandurfApp._build_ui`.

What is here:
  TitleBar       custom title bar (dragging, minimise, close). It takes
                 its colours from the app's theme (`pal`), not from the
                 module PAL, so it matches the rest of the window when
                 switching Aizome/Sumi. It has NO maximise - the app is a
                 fixed dashboard.
  Sidebar        narrow left strip: status indicator, one group (Today,
                 History, In-game, Settings, Search), watch indicator.
  PageContainer  pages stacked on top of each other, switched via `show()`.
  CommandPalette Ctrl+K popup with a fuzzy filter.
  _StateDot      status dot in the column: watching / stopped / snoozed /
                 heart rate dropped out.

THIS FILE DOES NOT RUN BY ITSELF. The app always starts via `main.py` ->
`app.DandurfApp`. `python ui_shell.py` does nothing - there used to be a
test `main()` here with a placeholder UI, which was misleading (see the
NOTE at the end).

Requires: customtkinter (already in requirements.txt).
"""

import sys
import time
import tkinter as tk
import tkinter.font as tkfont

import customtkinter as ctk

import hotkey
import hud_paint
import ui_kit

IS_WINDOWS = sys.platform == "win32"

# ---------------------------------------------------------------------------
# colour tokens - "calm" palette from mockup v4 (one accent, almost
# invisible borders, sage only for the "on" state, terracotta only for
# dangerous actions)
# ---------------------------------------------------------------------------
PAL = {
    "bg": "#0b0f0d",
    "bg_elevated": "#121714",
    "bg_hover": "#171d19",
    "border": "#1c2521",
    "border_strong": "#2a3630",
    "text": "#ece7da",
    "text_2": "#9aa39b",
    "text_3": "#5c645d",
    "accent": "#c9a24d",
    "accent_hover": "#d9b25f",
    "ok": "#8fbf9f",
    "danger": "#c1553d",
}

ctk.set_appearance_mode("dark")


# ---------------------------------------------------------------------------
# Current theme palette for elements WITHOUT their own copy
# ---------------------------------------------------------------------------
#
# `PAL` above is the original palette from mockup v4 - a greenish ink that
# the redesign (Aizome / Sumi) replaced. Most elements get their palette
# from outside, but the tooltip bubbles took it precisely from this module
# `PAL` - and so they remained the only place in the app where the old
# green still showed. Reported as "the tooltips have the old design".
#
# `PAL` cannot be removed (it holds the defaults for elements built before
# the first theme switch), so there is one variable with the CURRENT theme
# here, which the app sets at start and on every switch.
_THEME_PAL = {}


def set_theme_pal(pal):
    """Remembers the current theme palette for elements that keep none."""
    _THEME_PAL.clear()
    _THEME_PAL.update(pal or {})


def theme_pal():
    """The current theme palette; `PAL` only until the app has set one."""
    return _THEME_PAL or PAL


# ---------------------------------------------------------------------------
# Custom title bar - replaces the OS frame
# ---------------------------------------------------------------------------
# Pictogram of the "About" button in the title bar. A circle with an "i"
# is the established symbol for "about the program"; as a single
# character it is drawn by the same `_make_btn` as "–" and "×", so it
# lines up with them to the pixel.
ABOUT_GLYPH = "ⓘ"        # ⓘ


class TitleBar(ctk.CTkFrame):
    """Dragging the bar moves the window; the buttons on the right replicate
    minimise / close without the native OS look.

    Maximise is deliberately NOT here - see the NOTE below at `close()`."""

    def __init__(self, master, root_window=None, app_name="Zanshin", on_close=None,
                 version="", pal=None, on_about=None, about_tip="",
                 licence="", world_values=None, world_value=None, on_world=None,
                 world_tip=""):
        # NOTE: the bar took its colours from the module PAL and only the 残
        # character from the theme. The result was a strip that did not match
        # the rest of the window with the Sumi/Aizome theme (a different
        # black, a different text shade), and after the photo band above it
        # was removed it stood out even more. Now everything goes through
        # `pal`, with the module PAL only as a fallback when someone builds it
        # without a theme.
        self.pal = pal or {}

        # WARNING: reads `self.pal`, NOT the local `pal`. Originally it was a
        # closure over a local variable, so after `set_pal()` it returned the
        # old colours and the bar recoloured itself back to the previous
        # theme on a theme change (caught by the "recolouring == rebuild"
        # test - 20 differences).
        def c(key, fallback):
            return self.pal.get(key, PAL[fallback])

        self._c = c
        super().__init__(master, fg_color=c("surface", "bg"), height=32, corner_radius=0)
        # IMPORTANT: `master` is the parent widget to pack into (pack/grid) -
        # it DOES NOT HAVE TO be the real top-level window (e.g. when the
        # titlebar is packed inside an inner CTkFrame). For .geometry()/
        # .iconify()/.overrideredirect() we need a reference to the real
        # window, which is why `root_window` is a separate parameter that
        # must be passed.
        self.master_root = root_window if root_window is not None else master
        self.on_close_cb = on_close
        self._drag_start = None
        self.pack_propagate(False)

        # A thin line at the bottom separates the bar from the content, the
        # same way the cards on the pages are separated from each other -
        # without it, after the photo band was removed, the bar blended with
        # the window body into one surface.
        #
        # It MUST be packed FIRST, even before `left` and `controls`. Tk hands
        # out parcels in the order of the pack() calls: `left` with
        # side="left" takes a strip across the WHOLE height of the cavity, so
        # a line packed after it would get fill="x" only across the REST of
        # the cavity - it would start only after the app name (measured:
        # x=235 instead of 0 at a bar width of 1770 px) and would be missing
        # under the 残 character. As the first one it gets the full width, and
        # the rest is divided up only below it.
        # `bg_color` in the same colour: a 1 px high CTkFrame otherwise draws
        # a rectangle of zero height and the line is not visible (see
        # `ui_kit.linka`).
        self.divider = ctk.CTkFrame(self, fg_color=c("line_soft", "border"),
                                    bg_color=c("line_soft", "border"), height=1,
                                    corner_radius=0)
        self.divider.pack(side="bottom", fill="x")

        # The logo/mark (残 + name + version) sits in the bar as in the NVIDIA
        # App, not in the body of the side menu - after feedback that one is
        # narrow and icons only.
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", padx=(14, 0))
        ctk.CTkLabel(left, text="残", text_color=c("washi", "accent"),
                     font=("Yu Mincho", 15)).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(left, text=app_name, text_color=c("text", "text"),
                     font=ui_kit.ui(10, "bold")).pack(side="left")
        if version:
            # Fifteen clicks on the version number open the developer overlay.
            # It is a LOCAL Tk binding on one widget, not a global hook - it
            # works only when the app window has focus, and outside it it
            # knows nothing about clicks.
            self.version_label = ctk.CTkLabel(
                left, text=f"   {version}", text_color=c("text_faint", "text_3"),
                font=ui_kit.ui(10))
            self.version_label.pack(side="left")
            self._secret_clicks = 0
            self.version_label.bind("<Button-1>", self._on_version_click)

        if licence:
            # THE LICENCE RIGHT NEXT TO THE VERSION, and in the same font.
            #
            # The app claims to be free - so let that stand where it is always
            # visible, not only in Settings under Data. It is the same claim as
            # "everything stays with you": either it is visible all the time,
            # or there is no need to believe it.
            #
            # ITS OWN LABEL, not appended to the version: the version number
            # carries the fifteen-click binding to the developer overlay, and
            # it would otherwise be triggered by clicking on the licence too.
            self.licence_label = ctk.CTkLabel(
                left, text=f"  ·  {licence}",
                text_color=c("text_faint", "text_3"), font=ui_kit.ui(10))
            self.licence_label.pack(side="left")

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(side="right")
        # WORLD (0.2, B3-worlds): a small "Play | Work" left of ⓘ.
        #
        # In the bar, not on a page: it is the only thing that changes the
        # WHOLE app at once (look, history, insights), so it belongs where it
        # is visible on every page - and it does not clash with the HUD toggle
        # or the ⚙ on Today here. Small and muted: a sign in the corner of the
        # eye, not an exclamation mark.
        #
        # The tooltip goes on EACH segment separately -
        # CTkSegmentedButton.bind() raises NotImplementedError, and the
        # segments are its children.
        self.world_switch = None
        if on_world is not None and world_values:
            self.world_switch = ctk.CTkSegmentedButton(
                controls, values=list(world_values), height=22,
                font=ui_kit.ui(11), fg_color=c("surface", "bg"),
                selected_color=c("accent2", "bg_hover"),
                selected_hover_color=c("accent2_hover", "bg_hover"),
                unselected_color=c("surface", "bg"),
                unselected_hover_color=c("surface_alt", "bg_hover"),
                text_color=c("text", "text"), command=on_world)
            if world_value:
                self.world_switch.set(world_value)
            self.world_switch.pack(side="left", padx=(0, 8), pady=5)
            for segment in getattr(self.world_switch, "_buttons_dict", {}).values():
                _HoverTip(segment, lambda: world_tip, below=True)
            # The chosen world carries its TEXT in the accent - the `accent2`
            # fill had 1.15:1 against the unchosen segment and the world could
            # not be read from the bar.
            ui_kit.oznac_zvoleny_segment(self.world_switch, self.pal or PAL)
        # About to the LEFT of minimise and close.
        #
        # Whoever opens the app for the first time looks for "who made this" in
        # the title bar - not in Settings under Data, where that section lives.
        # The button takes them there, so the section can stay where its
        # content belongs.
        #
        # A PICTOGRAM, not the letter "A": a circle with an "i" is what people
        # recognise in a title bar. A lone "A" between "–" and "×" looks more
        # like a font size control - a symbol should be what it claims to be.
        if on_about is not None:
            self.about_btn = self._make_btn(controls, ABOUT_GLYPH, on_about)
            _HoverTip(self.about_btn, lambda: about_tip)
        self._make_btn(controls, "–", self.minimize)
        self._make_btn(controls, "×", self.close, danger=True)

        # dragging by the bar (not by the buttons) - NO double-click-maximise:
        # the app is a fixed dashboard with a fixed size (WINDOW_W/H in
        # app.py); maximising would stretch it over the whole monitor and
        # break layouts (HUD, command palette - see the comment at
        # DandurfApp.WINDOW_W). That is why the maximise button is no longer
        # in the controls above, and a double click does nothing.
        for widget in (self, left):
            widget.bind("<ButtonPress-1>", self._drag_begin)
            widget.bind("<B1-Motion>", self._drag_move)

    def _on_version_click(self, _event=None):
        """Fifteen clicks on the version -> developer overlay.

        Fifteen and not three: it is easy to click the version number by
        mistake, but not fifteen times in a row. It is meant to be hidden
        so that the player does not find it by chance and start
        re-setting thresholds they do not understand - not because it is
        secret.
        """
        self._secret_clicks += 1
        if self._secret_clicks < 15:
            return
        self._secret_clicks = 0
        otvor = getattr(self, "on_dev_layer", None)
        if callable(otvor):
            otvor()

    def set_pal(self, pal):
        """Rewrites its own copy of the palette on a theme change.

        The widget colours themselves were already recoloured by
        `theme_recolor`, but `self.pal` and the helper `self._c` are used
        on every `_make_btn()` - if the old palette stayed here, every
        title bar button added later would be drawn in the previous
        theme."""
        self.pal = pal or {}
        try:
            self.configure(fg_color=self._c("surface", "bg"))
            self.divider.configure(fg_color=self._c("line_soft", "border"),
                                   bg_color=self._c("line_soft", "border"))
        except Exception:
            pass
        if self.world_switch is not None:
            ui_kit.oznac_zvoleny_segment(self.world_switch, self.pal)

    def set_world(self, label):
        """Marks the world segment without calling `on_world` - the world
        could also have been switched by something else (Settings, the
        guide)."""
        if self.world_switch is None:
            return
        try:
            self.world_switch.set(label)
        except Exception:
            pass
        ui_kit.oznac_zvoleny_segment(self.world_switch, self.pal)

    def _make_btn(self, parent, symbol, cmd, danger=False):
        c = self._c
        btn = ctk.CTkButton(
            parent, text=symbol, width=38, height=32, corner_radius=0,
            fg_color="transparent",
            hover_color=(c("danger", "danger") if danger else c("surface_alt", "bg_hover")),
            text_color=c("text_dim", "text_3"), font=("Segoe UI", 11), command=cmd,
        )
        btn.pack(side="left")
        return btn

    def _drag_begin(self, event):
        self._drag_start = (event.x_root, event.y_root,
                            self.master_root.winfo_x(), self.master_root.winfo_y())

    def _drag_move(self, event):
        # NOTE: there was also a condition `or self._maximized` here - it was
        # left over after maximise was removed, but the attribute was no
        # longer set anywhere, so EVERY drag on the bar raised AttributeError
        # and the window could not be moved at all. The app has a fixed size
        # and cannot be maximised - so the condition is pointless, not just
        # broken.
        if not self._drag_start:
            return
        sx, sy, wx, wy = self._drag_start
        dx, dy = event.x_root - sx, event.y_root - sy
        self.master_root.geometry(f"+{wx + dx}+{wy + dy}")

    def minimize(self):
        # overrideredirect windows have no native taskbar handshake - we turn
        # it off temporarily so that iconify/restore works reliably (a common
        # Tk trick).
        self.master_root.overrideredirect(False)
        self.master_root.iconify()

    # NOTE: `toggle_maximize`/`_maximized_geometry` were here - they
    # bypassed the fixed window size (WINDOW_W/H in app.py,
    # minsize==maxsize) by calling geometry() directly. The app is a fixed
    # dashboard, not a window to be stretched over the whole monitor - so
    # the maximise button was removed entirely (not just hidden/blocked),
    # instead of fixing a behaviour the app is not even supposed to have.

    def close(self):
        if self.on_close_cb:
            self.on_close_cb()
        else:
            self.master_root.destroy()


def enable_frameless(root):
    """Turns on the frameless window and registers restoring
    overrideredirect after returning from being minimised to the taskbar
    (see TitleBar.minimize)."""
    root.overrideredirect(True)

    def _on_map(event):
        if root.state() == "normal":
            root.overrideredirect(True)
    root.bind("<Map>", _on_map)


# NOTE: there was a "Manual resize of the frameless window" block here -
# `RESIZE_GRIP_PX`, `enable_resize_grips()` and `lift_resize_grips()`.
# They drew 4 edges + 4 corners as thin frames over the content (place),
# by which the frameless window could be dragged at its edges.
#
# Removed: the app is a FIXED dashboard (DandurfApp.WINDOW_W/H, minsize
# == maxsize, no maximise), so manual resizing has nothing to do -
# nobody called `enable_resize_grips()` any more, and
# `gui_harness_auto.py` even checks the OPPOSITE ("no manual resize grips
# (fixed window by design)"). It stayed here as ~80 lines of dead code
# with a comment that described manual resizing as a live feature -
# exactly what confuses readers.


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
class Sidebar(ctk.CTkFrame):
    """Side navigation.

    Order from top to bottom (0.3 batch 4):
      1. STATUS INDICATOR - watching / stopped / "not now" / heart rate
         dropped out (`_StateDot`)
      2. ONE GROUP: Today, History, In-game ("Screen" in the Work world),
         Settings and Search (Ctrl+K)
      3. HEART-RATE INDICATOR with the label "Watch" - live sensor state
         + a shortcut to pairing
      4. flexible spacer
    Every element has an icon AND a short label - including the watch and
    the magnifier, which did not have one before 0.3 (UX audit: "elements
    without a label").

    WHY THERE IS NOTHING AT THE BOTTOM ANY MORE: before 0.3, Settings and
    the magnifier sat at the bottom of the panel. The window has a fixed
    height, and on an ordinary gaming laptop (1920x1080 at 150 %,
    1366x768) the bottom ended up under the taskbar - Settings were then
    reachable only via Ctrl+K, which the app does not mention anywhere.
    The audit suggested a safeguard: Settings and the magnifier into the
    top group under "In-game". There is always room at the top.

    NOTE: until 2.1, item 1 here was the ENSO (the mark and also the
    listening switch). The mark moved to the centre of the Today page
    (`app.py`, `_build_dnes_page`) and the switch to the breathing bar
    (`ui_kit.KamaeBar`); in the column only a small coloured dot is left
    after it, so that you can see on the other pages too whether the app
    is listening.
    """

    # After feedback from testing ("overcrowded") only 4 main items.
    # Cues, Sound and Guide are TABS in Settings (ui_kit.SubNav);
    # `_select(kluc_karty)` still works - the group is highlighted and the
    # app switches the tab (GROUPS), so the palette, onboarding and tour
    # did not break.
    #
    # "nastavenia" MUST STAY in `self.rows`: `gui_harness_auto.py` indexes
    # rows["nastavenia"] hard-coded in six places, and `_select`
    # highlights the Settings tabs through it (GROUPS). A missing key =
    # KeyError in the middle of a harness step. Since 0.3 (batch 4) all
    # FOUR are built in one column in this order - no more "the last one
    # goes to the bottom" split. The magnifier (Search) is not a page, so
    # it is not in `rows` (the harness counts `len(rows) == 4`) -
    # `self.cmdk_btn` holds it.
    PAGES = [
        ("dnes", "◗", "Dnes"),
        ("historia", "◷", "História"),
        ("vhre", "◳", "V hre"),
        # `︎` = text (monochrome) presentation. Without it Windows draws
        # ⚙ as an emoji - bigger and bolder than the thin geometric icons
        # ◗ ◷ ◳ next to it, so Settings "stuck out". The text variant
        # unifies it.
        ("nastavenia", "⚙︎", "Nastavenia"),
    ]
    GROUPS = {"spustace": "nastavenia", "zvuk": "nastavenia",
              "guide": "nastavenia", "vseobecne": "nastavenia"}
    # 76 -> 64: the column now carries only navigation and controls, not
    # the mark. Narrowing was blocked by the quick dock - it had two icons
    # SIDE BY SIDE and such a row asks for 70.7 px (a CTkButton with
    # corner_radius=8 asks for 16 px of "shell" + the glyph width, not the
    # given `width=24`). The dock is now vertical, so the widest element at
    # the bottom is a single button ~34 px and 64 px has room to spare.
    # 78 -> 80 (0.3 batch 4): the label under the icon has a 2x8 px margin
    # in the column, so WIDTH - 16 is left for the text. The longest of all
    # 11 languages is the Portuguese "Configurações" (63 px at ui(10)) - at
    # 78 it was a pixel short. The new "Hodinky"/"Hladat" (Watch/Search)
    # are shorter (the longest is the Bulgarian "Часовник", 45 px).
    # Measured by `tests/test_022e_bocny_panel.py`.
    WIDTH = 80

    @staticmethod
    def _mapuj_paletu(pal):
        """The Sidebar uses its own colour names (hover/active/text_2...) -
        the theme palette is translated to them here. Pulled out of
        `__init__` so that the same can be done on a theme change too
        (`set_pal`)."""
        return {
            "bg": pal.get("bg", PAL["bg"]),
            "hover": pal.get("surface", PAL["bg_hover"]),
            "active": pal.get("surface_alt", PAL["bg_hover"]),
            "text": pal.get("text", PAL["text"]),
            "text_2": pal.get("text_dim", PAL["text_2"]),
            "text_3": pal.get("text_faint", PAL["text_3"]),
            "border": pal.get("border", PAL["border"]),
            "accent": pal.get("accent_hover", PAL["accent"]),
            "washi": pal.get("washi", PAL["accent"]),
            "ok": pal.get("success", PAL["ok"]),
        }

    def set_pal(self, pal):
        """Recolours the side panel on a theme change.

        It does what the mechanical tree recolouring cannot: it rewrites
        its own palette copies (Sidebar, every _NavRow and the Ctrl+K row,
        the state dot) and redraws the heart-rate indicator, which is an
        IMAGE (the enso is no longer in the panel; the quick dock is gone).
        Without this the old colours would come back on the first
        hover/click."""
        self._theme_pal = pal
        self.pal = self._mapuj_paletu(pal)
        try:
            self.configure(fg_color=self.pal["bg"])
        except Exception:
            pass
        for row in self.rows.values():
            try:
                row.set_pal(self.pal)
            except Exception:
                pass
        # Since 0.3 (batch 4) the magnifier is a row like the others
        # (`_NavRow`), it just is not in `self.rows` (it is not a page) - it
        # is recoloured separately.
        cmdk = getattr(self, "cmdk_btn", None)
        if cmdk is not None:
            try:
                cmdk.set_pal(self.pal)
            except Exception:
                pass
        # the heart-rate indicator is an IMAGE - the colours are baked into
        # it, the whole set of frames has to be drawn again
        pair = getattr(self, "pair_btn", None)
        if pair is not None:
            try:
                pair.set_pal(pal)
            except Exception:
                pass
        enso = getattr(self, "enso", None)
        if enso is not None:
            try:
                enso.set_pal(pal)
            except Exception:
                pass
        bodka = getattr(self, "state_dot", None)
        if bodka is not None:
            try:
                bodka.set_pal(pal)
            except Exception:
                pass

    def __init__(self, master, on_navigate, labels=None, pal=None, version="",
                 on_palette=None, on_enso_toggle=None, on_pair_watch=None):
        pal = pal or PAL
        self._theme_pal = pal
        self.pal = {
            "bg": pal.get("bg", PAL["bg"]),
            "hover": pal.get("surface", PAL["bg_hover"]),
            "active": pal.get("surface_alt", PAL["bg_hover"]),
            "text": pal.get("text", PAL["text"]),
            "text_2": pal.get("text_dim", PAL["text_2"]),
            "text_3": pal.get("text_faint", PAL["text_3"]),
            "border": pal.get("border", PAL["border"]),
            "accent": pal.get("accent_hover", PAL["accent"]),
            "washi": pal.get("washi", PAL["accent"]),
            "ok": pal.get("success", PAL["ok"]),
        }
        super().__init__(master, fg_color=self.pal["bg"], width=self.WIDTH,
                         corner_radius=0, border_width=0)
        self.pack_propagate(False)
        self.on_navigate = on_navigate
        self.on_palette = on_palette
        # key -> _NavRow (icon + a short label under it, the full name in
        # the tooltip - see `_NavRow`). `buttons` stays as an alias for old
        # code that expected buttons.
        self.rows = {}
        self.buttons = self.rows
        labels = labels or {}
        # the logo (残 DojoSync / version) moved to TitleBar - here there is
        # just a small gap at the top
        ctk.CTkFrame(self, fg_color="transparent", height=10).pack(fill="x")

        # THE MARK MOVED TO THE CENTRE OF THE PAGE (2.1). In the panel it was
        # 68 px and the "armed" ring at that size 1.4 px - in a static image
        # it got lost. It is built by `DandurfApp._build_dnes_page`, which
        # assigns `sidebar.enso` here as an alias, so that the guided tour and
        # the harnesses find the same name; that is why `set_pal` below still
        # recolours it.
        #
        # Nobody calls `on_enso_toggle` any more - the switch is now a button
        # in the breathing bar (`ui_kit.KamaeBar`). The parameter stays for
        # the callers that pass it.
        self.enso = None

        # Status indicator. The mark left for the centre of the Today page,
        # and with it the only information on whether the app is listening -
        # on the other five pages nothing would be left in the window. See
        # `_StateDot`.
        dot_wrap = ctk.CTkFrame(self, fg_color="transparent")
        dot_wrap.pack(fill="x", pady=(8, 8))
        self.state_dot = _StateDot(
            dot_wrap, pal, tip=labels.get("state_tip", ""))
        self.state_dot.pack()

        # ONE GROUP under the dot: all four pages in PAGES order.
        for key, icon, default_label in self.PAGES:
            row = _NavRow(self, self.pal, key, icon, labels.get(key, default_label),
                          on_click=self._select, compact=True)
            row.pack(fill="x", padx=8, pady=2)
            self.rows[key] = row

        # Ctrl+K - last in the group, the same row (icon + short label
        # "Search") as the pages above it. The tooltip gives the full name
        # and the shortcut. It is not in `self.rows`: it is not a page, never
        # lights up as active, and a click on it does not navigate, it only
        # opens the palette. A plain callback, not a virtual event
        # (CTkFrame.bind() goes to the inner canvas, event_generate() to the
        # frame - it would not arrive).
        cmdk_hint = _NavRow(
            self, self.pal, "hladat", "⌕", labels.get("search", "Hľadať"),
            on_click=lambda _k: self.on_palette() if self.on_palette else None,
            compact=True,
            # "Strg K" in German - key names by language (0.3 batch 4b)
            tip=lambda: (f"{labels.get('cmdk', 'Hľadať a prepínať')}   "
                         f"{hotkey.format_combo('ctrl+k', oddelovac=' ')}"))
        cmdk_hint.pack(fill="x", padx=8, pady=2)
        self.cmdk_btn = cmdk_hint

        # HEART-RATE SENSOR INDICATOR with the label "Watch" - below the
        # group, separated by a gap (it is a state and a shortcut, not a
        # page). It is also the shortcut to pairing the watch (the "Watch and
        # heart rate" card on the In-game page).
        #
        # WARNING - FLEXIBLE SPACERS: there may be only ONE, and only BELOW
        # the indicator. Two (above and below) once took all the space and
        # the elements between them got 1 px - Tk did not draw them at all.
        self.pair_btn = None
        if on_pair_watch is not None:
            self.pair_btn = _WatchPulse(
                self, pal, on_click=on_pair_watch,
                tip_fn=lambda: labels.get("pair_tip", "Spárovať hodinky"),
                tip_live_fn=lambda: labels.get("pair_live_tip", "Tep z hodiniek"),
                caption=labels.get("watch", ""))
            self.pair_btn.pack(pady=(12, 0))
        ctk.CTkFrame(self, fg_color="transparent").pack(fill="both", expand=True)

        # NOTE: there was a `dock_slot` here - an empty frame into which
        # `app.py` put the `QuickDock`. The dock is gone (the reason is at its
        # class below). Before 0.3 (batch 4) the magnifier and Settings also
        # sat down here (see the class docstring for why not any more).

        self._select("dnes")

    def set_label(self, key, text):
        """New label for the item `key` without rebuilding the panel -
        "In-game" is called "Screen" in the Work world, and the world is
        switched by recolouring the window, not by rebuilding it
        (`app_prefs.set_world`)."""
        row = self.rows.get(key)
        if row is not None:
            row.set_label(text)

    def set_badge(self, key, text=""):
        """A small number or dot to the right of the item (number of
        triggers, running sensor). The badge is a separate label in the
        right column - only its text changes, the item label is not
        touched."""
        row = self.rows.get(key)
        if row is not None:
            row.set_badge(text)

    def _select(self, key):
        self.mark_active(key)
        self.on_navigate(key)

    def mark_active(self, key):
        """Highlights the item of page `key` (a Settings tab highlights
        "Settings") WITHOUT navigating.

        Before 0.3 only a click in the panel highlighted it (`_select`).
        Paths that switch the page from code - ⓘ in the title bar
        (About), ⚙ by "Heart rate in game", the Ctrl+K palette, the tour -
        went straight to `app._navigate`, so the content was Settings ->
        General while the panel still lit up "Today". Now `_navigate`
        calls this at the end of every navigation."""
        active = self.GROUPS.get(key, key)
        for k, row in self.rows.items():
            row.set_active(k == active)


# ---------------------------------------------------------------------------
# Side panel icons - ONE BRUSH (0.3, UX audit)
# ---------------------------------------------------------------------------
#
# The panel had four Unicode characters and a magnifier - each from a
# different typeface, with a different line weight and a different
# optical centre, and depending on the Windows version the gear was also
# drawn as a colour emoji. Here they are all drawn with the same pen:
# outline, a 1.5 px stroke in a 20 px square, the same margin. Today =
# enso (the app's mark), History = clock, In-game = screen, Settings =
# gear, Search = magnifier.

NAV_ICON_PX = 20
_NAV_ICON_SS = 3          # drawn at triple size, CTk scales it down by the scaling

# item key -> icon name (items without an icon keep the PAGES character)
NAV_ICON_FOR = {"dnes": "enso", "historia": "clock", "vhre": "screen",
                "nastavenia": "gear", "hladat": "search"}


def kresli_nav_ikonu(meno, farba, px=NAV_ICON_PX, ss=_NAV_ICON_SS):
    """PIL RGBA icon `meno` (enso/clock/screen/gear/search) in the colour
    `farba`, size `px` * `ss`. Returns None when PIL is missing or the
    name is unknown - the caller then keeps the character."""
    try:
        import math
        from PIL import Image, ImageDraw
    except Exception:
        return None
    S = px * ss
    k = S / 20.0                       # the coordinates below are in a 20 px square
    w = max(1, int(round(1.5 * k)))   # 1.5 px stroke
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def box(x0, y0, x1, y1):
        return [x0 * k, y0 * k, x1 * k, y1 * k]

    def ciara(*body):
        d.line([(x * k, y * k) for x, y in body], fill=farba, width=w, joint="curve")

    if meno == "enso":
        # a circle with a gap top right - a brush stroke that does not close
        d.arc(box(2.5, 2.5, 17.5, 17.5), start=-35, end=275, fill=farba, width=w)
    elif meno == "clock":
        d.ellipse(box(2.5, 2.5, 17.5, 17.5), outline=farba, width=w)
        ciara((10, 5.8), (10, 10), (13.4, 12))
    elif meno == "screen":
        d.rounded_rectangle(box(2.5, 3.5, 17.5, 13.5), radius=2 * k,
                            outline=farba, width=w)
        ciara((10, 13.5), (10, 16.5))
        ciara((6.5, 16.8), (13.5, 16.8))
    elif meno == "gear":
        cx = cy = 10.0
        for i in range(8):
            u = math.radians(i * 45 + 22.5)
            ciara((cx + 5.6 * math.cos(u), cy + 5.6 * math.sin(u)),
                  (cx + 8.0 * math.cos(u), cy + 8.0 * math.sin(u)))
        d.ellipse(box(cx - 5.6, cy - 5.6, cx + 5.6, cy + 5.6), outline=farba, width=w)
        d.ellipse(box(cx - 2.2, cy - 2.2, cx + 2.2, cy + 2.2), outline=farba, width=w)
    elif meno == "search":
        d.ellipse(box(3, 3, 13.5, 13.5), outline=farba, width=w)
        ciara((12, 12), (17, 17))
    else:
        return None
    return img


def nav_ikona(meno, farba, px=NAV_ICON_PX):
    """`kresli_nav_ikonu` as a CTkImage (or None)."""
    img = kresli_nav_ikonu(meno, farba, px)
    if img is None:
        return None
    try:
        return ctk.CTkImage(light_image=img, dark_image=img, size=(px, px))
    except Exception:
        return None


class _NavRow(ctk.CTkFrame):
    """One side menu item: icon | text | badge in FIXED columns.

    Why not a single button with the text f"{icon}    {label}": the
    glyphs ◗ ⌸ ♪ ◳ ◈ ⚙ each have a different width, so the text of every
    item started on a different vertical and the badge (number of
    triggers, sensor dot) floated somewhere in the middle of the row.
    Here the icon has a fixed-width column (ICON_W, centred), the text
    always starts right after it at the same x coordinate, and the badge
    is aligned to the right - when it is empty, it takes no space.

    The whole row is clickable (icon, text, badge and the empty area) and
    has hover + active state like the original CTkButton.
    """

    HEIGHT = 34
    HEIGHT_COMPACT = 48
    ICON_W = 24

    def __init__(self, master, pal, key, icon, label, on_click, compact=False,
                 tip=None):
        self.compact = bool(compact)
        height = self.HEIGHT_COMPACT if self.compact else self.HEIGHT
        super().__init__(master, fg_color="transparent", height=height, corner_radius=0)
        self.pack_propagate(False)
        self.pal = pal
        self.key = key
        self.on_click = on_click
        self.active = False
        self.text = label
        # Tooltip: by default the full name (`self.text`), the magnifier has
        # its own (the palette's full name + Ctrl K) - `tip` is a function,
        # read only when it is shown.
        self._tip_fn = tip if callable(tip) else (lambda: self.text)

        # "button" - rounded backdrop carrying the hover/active background
        self.box = ctk.CTkFrame(self, fg_color="transparent", corner_radius=8,
                                height=height - 2)
        self.box.pack(fill="both", expand=True, pady=1)
        self.box.pack_propagate(False)

        if self.compact:
            # Icon + a short label under it (Today/History/In-game/Settings).
            # The label came back in 2.1: in a ~78 px panel the short sk/en
            # names fit, and the player does not have to guess what each icon
            # means. The tooltip stays for longer translations that would be
            # cut off. A drawn icon (one brush for the whole panel); the
            # character from PAGES stays only as a fallback, in case PIL is
            # missing.
            self._icon_name = NAV_ICON_FOR.get(key)
            self._icon_imgs = {}
            obrazok = self._ikona(pal["text_2"])
            if obrazok is not None:
                self.icon = ctk.CTkLabel(self.box, text="", image=obrazok,
                                         anchor="center", width=NAV_ICON_PX + 4,
                                         height=NAV_ICON_PX + 4)
                self.icon.pack(side="top", pady=(6, 1))
            else:
                self._icon_name = None
                self.icon = ctk.CTkLabel(self.box, text=icon, anchor="center",
                                         font=("Segoe UI", 18), text_color=pal["text_2"])
                self.icon.pack(side="top", pady=(5, 0))
            self.label = ctk.CTkLabel(self.box, text=label, anchor="center",
                                      font=ui_kit.ui(10), text_color=pal["text_2"])
            self.label.pack(side="top", pady=(0, 2))
            self.badge = ctk.CTkLabel(self.box, text="", anchor="e",
                                      font=ui_kit.ui(10, "bold"), text_color=pal["text_3"])
            _HoverTip(self.box, lambda: self._tip_fn())
        else:
            self.icon = ctk.CTkLabel(self.box, text=icon, width=self.ICON_W,
                                     anchor="center", font=("Segoe UI", 12),
                                     text_color=pal["text_2"])
            self.icon.pack(side="left", padx=(6, 6))
            self.badge = ctk.CTkLabel(self.box, text="", anchor="e",
                                      font=ui_kit.ui(11), text_color=pal["text_3"])
            # the badge is packed only in set_badge (empty takes no space)
            self.label = ctk.CTkLabel(self.box, text=label, anchor="w",
                                      font=ui_kit.ui(12), text_color=pal["text_2"])
            self.label.pack(side="left", fill="x", expand=True)

        for widget in (self.box, self.icon, self.label, self.badge):
            widget.bind("<Button-1>", self._clicked)
            widget.bind("<Enter>", self._enter)
            widget.bind("<Leave>", self._leave)
            try:
                widget.configure(cursor="hand2")
            except Exception:
                pass

    # ---- public ----

    def set_badge(self, text=""):
        text = str(text or "")
        try:
            self.badge.configure(text=text)
            if self.compact:
                if text:
                    self.badge.place(relx=1.0, x=-6, y=3, anchor="ne")
                else:
                    self.badge.place_forget()
                return
            if text and not self.badge.winfo_ismapped():
                self.badge.pack(side="right", padx=(6, 10), before=self.label)
            elif not text and self.badge.winfo_ismapped():
                self.badge.pack_forget()
        except Exception:
            pass

    def set_active(self, active):
        self.active = bool(active)
        self._paint(hover=False)

    def set_label(self, text):
        """New label (and the tooltip, which reads it from `self.text`)."""
        self.text = text
        try:
            self.label.configure(text=text)
        except Exception:
            pass

    def set_pal(self, pal):
        """Rewrites its own copy of the palette and redraws right away.

        The row HOLDS its colours and applies them again on every
        hover/activation (`_paint`). If only the widget colours were
        rewritten on a theme change and not this dict, the first mouse
        pass would bring back the old colours.
        """
        self.pal = pal
        self._paint(hover=False)

    def _ikona(self, farba):
        """The drawn icon in the colour `farba` (from the cache), or None when
        the row has no drawn icon (fallback to the character)."""
        meno = getattr(self, "_icon_name", None)
        if not meno:
            return None
        kluc = str(farba).lower()
        if kluc not in self._icon_imgs:
            self._icon_imgs[kluc] = nav_ikona(meno, farba)
        return self._icon_imgs[kluc]

    # ---- internals ----

    def _clicked(self, _event=None):
        if callable(self.on_click):
            self.on_click(self.key)

    def _enter(self, _event=None):
        self._paint(hover=True)

    def _leave(self, _event=None):
        # Leave also arrives when moving from the backdrop to its own label -
        # we turn the hover off only when the cursor has really left the row
        try:
            px, py = self.winfo_pointerxy()
            x0, y0 = self.box.winfo_rootx(), self.box.winfo_rooty()
            inside = (x0 <= px < x0 + self.box.winfo_width()
                      and y0 <= py < y0 + self.box.winfo_height())
        except Exception:
            inside = False
        self._paint(hover=inside)

    def _paint(self, hover):
        pal = self.pal
        if self.active:
            bg, fg = pal["active"], pal["text"]
        elif hover:
            bg, fg = pal["hover"], pal["text_2"]
        else:
            bg, fg = "transparent", pal["text_2"]
        try:
            self.box.configure(fg_color=bg)
            obrazok = self._ikona(fg)
            if obrazok is not None:
                self.icon.configure(image=obrazok)
            else:
                self.icon.configure(text_color=fg)
            self.label.configure(text_color=fg)
            self.badge.configure(text_color=pal["text_2"] if self.active else pal["text_3"])
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Listening state: the panel's state dot and the enso (残), the app mark -
# since 2.1 in the centre of the Today page (`_EnsoHero`), not in the panel
# ---------------------------------------------------------------------------
class _StateDot(ctk.CTkFrame):
    """Side panel dot: watching / stopped / snoozed / heart rate dropped out.

    WHY IT EXISTS AT ALL
    --------------------
    Until 2.1 the state was carried by the mark at the top of the panel,
    and it was visible on EVERY page. Since the rebuild the mark lives in
    the centre of the Today page, and so does the breathing bar - both
    are children of that page, so on History, In-game, Sound and Settings
    NOTHING was left in the window to say whether the app is listening.
    That is a loss of capability, not a change of look.

    The dot is the smallest thing that brings that capability back. It
    is deliberately NOT a second enso: two marks in one window would
    compete, and a second set of frames would have to be paid for.

    SHAPE, NOT JUST COLOUR (0.3, UX audit): watching = a filled `success`
    dot; stopped = just a hollow circle in `text_faint`. Before 0.3 a
    stopped app was a filled RED dot - a permanent "alarm" in a perfectly
    ordinary state that you look at on every start. Red (`danger`)
    belongs to errors, not to calm (see `theme.py`). Filled vs. hollow
    can be told apart even without colours.

    THIRD STATE: SNOOZED
    --------------------
    Snooze ("not now") is turned on by a global shortcut and had its own
    colour on the 😴 icon in the quick dock. The dock left the panel (see
    `app.py`, `_build_ui`), so snooze could be turned on with the
    shortcut and the player would see NOWHERE that the app is snoozed -
    they would find out only by it being silent. That is the same class
    of bug as when the status indicator vanished from five pages.

    The snoozed dot is therefore AMBER (`warn`) and has a ring - colour
    alone would merge with red in the periphery. Snooze takes precedence
    over listening: when the app is listening but snoozed, snoozed
    applies.

    FOURTH STATE: WATCHING, BUT THE HEART RATE DROPPED OUT (0.3 batch 4)
    --------------------------------------------------------------------
    The watch dropped out in the middle of the evening (`app._hr_lost`:
    after 12 s of silence, `heart_rate.STALE_AFTER_S`) - the app is
    "watching", but has nothing to go on and will not speak up by
    itself. On History or in Settings a filled green dot would claim
    everything is fine. The dropout is the only state that calls for
    action, so it has its own SHAPE - a filled TRIANGLE (warning), not
    another circle - and the colour `danger_text`: the audit reserved it
    for lost watches (theme.py), and on `bg` it has >= 4.5:1 in both
    themes. It also takes precedence over snooze: the player turned "not
    now" on themselves and knows about it, but not about the dropout. It
    is not shown for a stopped app (it is not watching, nothing can drop
    out). The app sends the state via `set_lost`
    (`app_today._refresh_state_dot`).

    It is not a button. There is one switch, and it is in the breathing
    bar.
    """

    SIZE = 10

    def __init__(self, master, pal, tip=""):
        super().__init__(master, fg_color="transparent",
                         width=self.SIZE + 8, height=self.SIZE + 8)
        self.pack_propagate(False)
        self._pal = pal
        self._live = False
        self._snoozed = False
        self._lost = False
        self.canvas = tk.Canvas(self, width=self.SIZE + 8, height=self.SIZE + 8,
                                bg=pal["bg"], highlightthickness=0, bd=0)
        self.canvas.pack()
        self._tip_text = tip
        # The basic tooltip (a description of all states). During snooze
        # `_tip_text` carries the end time; on a dropout the basic one applies.
        self._base_tip = tip
        self._tip = _HoverTip(self.canvas, self._aktualny_tip)
        self._redraw()

    def _aktualny_tip(self):
        if self._lost and self._live:
            return self._base_tip
        return self._tip_text

    def set_lost(self, lost):
        """Watching, but the heart rate from the watch dropped out. Drawn only
        together with `set_live(True)`."""
        lost = bool(lost)
        if lost == self._lost:
            return
        self._lost = lost
        self._redraw()

    def set_live(self, live):
        live = bool(live)
        if live == self._live:
            return
        self._live = live
        self._redraw()

    def set_snoozed(self, snoozed, tip=None):
        """Snoozed app. `tip` also carries the remaining time - without it the
        dot would only say "something is different", not until when."""
        snoozed = bool(snoozed)
        if tip is not None:
            self._tip_text = tip
        if snoozed == self._snoozed:
            return
        self._snoozed = snoozed
        self._redraw()

    def set_pal(self, pal):
        self._pal = pal
        try:
            self.canvas.configure(bg=pal["bg"])
        except Exception:
            pass
        self._redraw()

    def _set_scaling(self, *args, **kwargs):
        """Redraws on a DPI change too (window moved to a monitor with a
        different scaling) - the canvas is a bare tk.Canvas and does its
        own scaling."""
        try:
            super()._set_scaling(*args, **kwargs)
        except Exception:
            pass
        self._redraw()

    def _mierka(self):
        try:
            return float(ctk.ScalingTracker.get_widget_scaling(self)) or 1.0
        except Exception:
            return 1.0

    def _redraw(self):
        c, pal = getattr(self, "canvas", None), getattr(self, "_pal", None)
        if c is None or pal is None:
            return          # `_set_scaling` called before the canvas is built
        try:
            c.delete("all")
        except Exception:
            return
        # DPI (0.3 batch 4): CTk enlarges the frame around the canvas by
        # itself, a bare tk.Canvas does not - at 150 % the dot was a third
        # smaller than the icons under it and the hollow circle fell apart
        # into a few pixels.
        m = self._mierka()
        strana = int(round((self.SIZE + 8) * m))
        try:
            if int(float(c.cget("width"))) != strana:
                c.configure(width=strana, height=strana)
        except Exception:
            pass
        r = self.SIZE / 2.0 * m
        stred = strana / 2.0
        if self._lost and self._live:
            # watching, but heart rate dropped out: filled triangle (warning)
            farba = pal.get("danger_text", pal.get("warn", "#D46F57"))
            c.create_polygon(stred, stred - r - 2 * m, stred - r - 1.5 * m, stred + r,
                             stred + r + 1.5 * m, stred + r, fill=farba, outline="")
            return
        if self._snoozed:
            farba = pal.get("warn", pal["success"])
            # A ring, not just a different colour: amber and green are close
            # in the periphery unless they have a different SHAPE.
            okraj = r + 3 * m
            c.create_oval(stred - okraj, stred - okraj, stred + okraj, stred + okraj,
                          outline=farba, width=max(1, round(m)))
        elif not self._live:
            # stopped: a hollow circle, no fill - calm, not alarm
            farba = pal.get("text_faint", pal.get("text_dim", "#888888"))
            vnutro = r - 1 * m
            c.create_oval(stred - vnutro, stred - vnutro, stred + vnutro, stred + vnutro,
                          outline=farba, width=1.5 * m)
            return
        else:
            farba = pal["success"]
        c.create_oval(stred - r, stred - r, stred + r, stred + r,
                      fill=farba, outline="")


class _EnsoButton(ctk.CTkFrame):
    """The app's mark (残 in the enso) and also the listening switch.

    NO LONGER BUILT ANYWHERE: since 2.1 the mark lives in the centre of
    the Today page and `_EnsoHero` draws it there (not a widget). This
    class stays because `_EnsoHero` borrows its `PHASE_OFFSET` and
    `BIG_PX` and a few tests (`test_trigger`, `test_theme_recolor`) read
    its source. Until 2.1 it sat at the TOP of the side panel - the
    first thing you saw in the window, the app's logo and the state at
    once (before that it was in the middle of the panel and smaller, and
    as a mark it got lost there).

    The colour follows the theme accent (`hud_paint.render_enso`); the
    state is carried by MOTION - a stopped app is one still frame, a
    listening one breathes. Before, COLOUR carried it: green =
    listening, red = not listening. No text label (it was tried, the
    text crossed the character) - the full action name is in the
    tooltip.

    It is NOT a static icon: while listening it breathes slowly with the
    same curve as the breath ring, and a loading ring behind the mark
    fills with the inhale.

    Frames are pre-computed AHEAD (`_frames`); at runtime only the image
    is switched. Rendering one frame (68 px) costs ~1.2 ms - computing it
    on every tick would mean keeping the CPU needlessly busy the whole
    time the app runs. The whole cycle (80 frames) is pre-computed in
    ~125 ms, once.

    ARMED (`set_armed`) is a third state: the body has stayed above the
    threshold for 90 s and the app is waiting for a pause. It is drawn as
    an inner ring (see `hud_paint.render_enso`), with the same colour -
    motion carries the state.

    The frame set for armed is rendered ONLY ON FIRST USE, just like the
    zones in `_WatchPulse._sada`. Ahead of time it would be another 80
    frames (~128 ms) on every start AND on every theme change - and most
    of the time it is not armed. That is why the key is the pair
    `(live, armed)`, not a bare bool.
    """

    # The default 68 px held while the mark sat in the side column and was
    # meant to take up almost its whole width. Since it lives in the centre
    # of the Today page, its size is set by the caller
    # (`app.DandurfApp.ENSO_SIZE`, now 150) and this value is only a
    # fallback for a call without `size`.
    SIZE = 68
    FRAMES = 80
    # Above this size it is drawn with double supersampling instead of
    # triple. Measured at 150 px: the average brightness difference against
    # ss=3 is 4/255 and cannot be told by eye, but the cost drops from
    # 585 ms to 283 ms for the whole set. At ss=1 the jaggedness shows.
    BIG_PX = 100
    # How many frames are finished in one tick of the background drawing.
    BUILD_CHUNK = 8
    # 80 * 125 ms = 10 s = 6 breaths per minute. See hud_paint.enso_breath.
    TICK_MS = hud_paint.ENSO_CYCLE_MS // FRAMES

    def __init__(self, master, pal, on_toggle=None, tip_start="", tip_stop="",
                 size=None):
        super().__init__(master, fg_color="transparent")
        # The size is a parameter since 2.1: the mark moved from the side
        # panel to the centre of the page, and there it has room. At 68 px the
        # "armed" ring was 1.4 px and got lost in a static image.
        #
        # NOTE: `SIZE` stays a class constant and is still the DEFAULT value -
        # but both `_build_frames` and `_show` now read `self.size`.
        self.size = int(size) if size else self.SIZE
        self._pal = pal
        self._on_toggle = on_toggle
        # `_live` deliberately stays a bare bool - gui_harness_auto.py asks
        # for `enso._live is False/True`. Arming is a separate flag.
        self._live = False
        self._armed = False
        self._moon = False        # graduation: enso = golden moon (once)
        self._moon_frames = None
        self._tip_start = tip_start
        self._tip_stop = tip_stop
        self._frames = {}      # (live, armed) -> [CTkImage, ...]
        self._i = 0
        self._after_id = None
        # Its own `after` chain for drawing the set in the background. It is
        # deliberately SEPARATE from `_after_id` (the animation): `_WatchPulse`
        # has it recorded in its header what happens when two chains arise
        # from one tick - 5 -> 88 Tk tasks in 5 seconds, and `destroy()`
        # cancels only one.
        self._build_after = None
        self._build_queue = []
        self._phase_fn = None
        self.btn = ctk.CTkLabel(self, text="", cursor="hand2")
        self.btn.pack()
        self.btn.bind("<Button-1>", self._clicked)
        self._tip = _HoverTip(self.btn, lambda: self._tip_stop if self._live else self._tip_start)
        self._build_frames()
        self._show()
        self._tick()

    def _clicked(self, _event=None):
        if callable(self._on_toggle):
            self._on_toggle()

    def set_live(self, live):
        live = bool(live)
        if live == self._live:
            return
        self._live = live
        if not live:
            # When the app stops listening, the arming no longer holds - the
            # trigger drops it too (`CueTrigger.suspend`). If it stayed here,
            # the ring would be lit from the very first second the next time
            # listening is turned on.
            self._armed = False
        self._show()

    def set_armed(self, armed):
        """The trigger is armed - the body stays up and a pause is awaited."""
        armed = bool(armed)
        if armed == self._armed:
            return
        self._armed = armed
        self._show()

    def set_phase_source(self, fn):
        """`fn()` returns the breath phase 0..1 that the mark should follow.

        The app passes `KamaeBar.phase()` here - the breathing line in
        the header. So the mark does not breathe at its own pace, but
        EXACTLY with it: one window, one rhythm. Without this both would
        have the same period but each a different phase, and after a
        while they would move against each other.
        """
        self._phase_fn = fn

    def set_pal(self, pal):
        """Redraws the enso on a theme change.

        The enso is an IMAGE - the colours are baked into it, so it cannot
        be recoloured with `configure()` and the whole set of frames has
        to be drawn again."""
        self._pal = pal
        self._build_queue = []
        self._cancel_build()
        self._build_frames()
        if self._moon:
            self._build_moon()
        self._show()

    def graduate(self):
        """GRADUATION: the enso closes into a golden moon and stays that way
        (even after a restart - the app restores it from the
        `zanshin_graduated` flag). The app keeps running; it is only a
        mark of achievement, not a change of function."""
        if self._moon:
            return
        self._moon = True
        self._build_moon()
        self._show()

    def _build_moon(self):
        """Frame set of the "golden moon" - a closed circle (close=1) with a
        soft glow (halo) that breathes gently. Built once at graduation /
        at the start of an already graduated app."""
        try:
            style = hud_paint.Style(self._pal)
        except Exception:
            return
        ss = 2 if self.size > self.BIG_PX else hud_paint.SS
        frames = []
        pocet = 48
        for i in range(pocet):
            faza = i / float(pocet)
            dych = hud_paint.enso_breath(faza)
            img = hud_paint.render_enso(self.size, style, live=True, phase=faza,
                                        ss=ss, close=1.0, sheen=False,
                                        halo=0.55 + 0.45 * dych)
            frames.append(ctk.CTkImage(light_image=img, dark_image=img,
                                       size=(self.size, self.size)))
        self._moon_frames = frames

    def destroy(self):
        # Without this the `after` chain would keep running over a destroyed
        # widget and Tk would report "invalid command name" on every tick.
        # There are TWO chains - animation and background drawing - and both
        # need cancelling.
        self._build_queue = []
        self._cancel_build()
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        super().destroy()

    # ---- internals ----

    def _build_frames(self):
        try:
            style = hud_paint.Style(self._pal)
        except Exception:
            return
        self._frames = {}

        ss = 2 if self.size > self.BIG_PX else hud_paint.SS

        def snimok(live, phase, armed=False):
            img = hud_paint.render_enso(self.size, style, live=live,
                                        phase=phase, armed=armed, ss=ss,
                                        sheen=True)
            return ctk.CTkImage(light_image=img, dark_image=img,
                                size=(self.size, self.size))

        self._snimok = snimok

        # A stopped app does NOT MOVE and is at the smallest radius - a single
        # frame. Stillness carries the state here (the colour does not): an
        # app that is not listening must not look alive. (And 80 identical
        # frames would be 96 ms of extra work on every start.)
        try:
            self._frames[(False, False)] = [snimok(False, 0.0)]
        except Exception:
            pass

        # THE ANIMATION IS FINISHED IN THE BACKGROUND. At 150 px the whole set
        # even with ss=2 costs about 283 ms - and it is paid on EVERY start and
        # on EVERY theme change, against a budget of ~673 ms for a theme
        # switch. That is why only the first frame is drawn right away (the
        # mark is in its place immediately, just still) and the rest is
        # finished bit by bit. Until the set is complete, `_phase_index`
        # returns 0, so nothing stutters.
        try:
            self._frames[(True, False)] = [snimok(True, 0.0)]
        except Exception:
            pass
        self._build_queue = [(True, False), (True, True)]
        self._schedule_build()

    def _schedule_build(self):
        """Schedules the next bit of background drawing. The ONLY place where
        `_build_after` is created - so that two chains cannot arise at
        once."""
        self._cancel_build()
        if not self._build_queue:
            return
        try:
            self._build_after = self.after(30, self._build_step)
        except Exception:
            self._build_after = None

    def _cancel_build(self):
        if self._build_after is not None:
            try:
                self.after_cancel(self._build_after)
            except Exception:
                pass
            self._build_after = None

    def _build_step(self):
        """Finishes `BUILD_CHUNK` frames and schedules itself again.

        It is NOT called from anywhere other than `_schedule_build` -
        otherwise two chains would arise from one tick (see
        `_WatchPulse._render_now`).
        """
        self._build_after = None
        tvorca = getattr(self, "_snimok", None)
        if tvorca is None or not self._build_queue:
            self._build_queue = []
            return
        kluc = self._build_queue[0]
        _live, armed = kluc
        sada = self._frames.get(kluc)
        if sada is None:
            sada = self._frames[kluc] = []
        hotovo = 0
        while len(sada) < self.FRAMES and hotovo < self.BUILD_CHUNK:
            try:
                sada.append(tvorca(True, len(sada) / float(self.FRAMES),
                                   armed=armed))
            except Exception:
                self._build_queue = []
                return
            hotovo += 1
        if len(sada) >= self.FRAMES:
            self._build_queue.pop(0)
            self._show()               # the set is complete, the animation starts
        self._schedule_build()

    def _hotova(self, kluc):
        return len(self._frames.get(kluc) or ()) >= self.FRAMES

    def _sada(self, kluc):
        """Frames for the given state; armed is rendered only on first use -
        the same reason as in `_WatchPulse._sada`.

        Ahead of time it would be 80 extra frames (~128 ms) on start and
        on every theme change, and the ring is not lit most of the time.
        """
        sada = self._frames.get(kluc)
        if sada is not None:
            return sada
        live, armed = kluc
        if not live:
            # Stopped + armed cannot happen (`set_live` drops the flag), but if
            # it ever did, better a still frame than nothing.
            return self._frames.get((False, False))
        # The set is NO LONGER rendered synchronously - at 150 px that would
        # be over 280 ms of a frozen window exactly at the moment the app
        # armed. It is queued for background drawing, and until then the
        # ordinary running set is shown.
        if kluc not in self._build_queue:
            self._build_queue.append(kluc)
            self._schedule_build()
        return self._frames.get((True, False))

    # The peak of the enso's breath (end of the inhale + pause) is in the
    # 0.42-0.48 span, so centred at 0.45; the KamaeBar breathing line
    # peaks at 0.50. The enso therefore reads `linka_faza + OFFSET`, and
    # for its plateau to land on 0.50, OFFSET must be negative:
    # 0.45 - OFFSET = 0.50.
    # (At first I had +0.05 here and the enso peaked almost a second
    # EARLIER than the line - it only showed in the measured course of
    # both curves side by side, not by eye.)
    PHASE_OFFSET = -0.05

    def _phase_index(self):
        """Frame index - from the breathing line, if the app provided one."""
        if not self._hotova((True, False)):
            return 0                 # the set is being drawn - the mark stands still
        pocet = len(self._frames.get((True, False)) or ()) or self.FRAMES
        if callable(self._phase_fn):
            try:
                faza = float(self._phase_fn())
            except Exception:
                faza = None
            if faza is not None:
                return int(((faza + self.PHASE_OFFSET) % 1.0) * pocet) % pocet
        return self._i % pocet

    def _show(self):
        if self._moon and self._moon_frames:
            n = len(self._moon_frames)
            faza = 0.0
            if callable(self._phase_fn):
                try:
                    faza = float(self._phase_fn())
                except Exception:
                    faza = 0.0
            idx = int(((faza + self.PHASE_OFFSET) % 1.0) * n) % n
            try:
                self.btn.configure(image=self._moon_frames[idx])
            except Exception:
                pass
            return
        sada = self._sada((self._live, self._armed and self._live))
        if not sada:
            return
        index = self._phase_index() if self._live else 0
        try:
            self.btn.configure(image=sada[index % len(sada)])
        except Exception:
            pass

    def _tick(self):
        # A stopped app has nothing to animate - there is one still frame.
        # But we have to keep ticking, so that the animation starts right
        # away when listening is turned on.
        if self._live or self._moon:
            self._i += 1
            self._show()
        # WARNING: this end of the method is what keeps the animation alive.
        # Once I managed to cut it off during an edit, and the enso ticked
        # only once at start - `_after_id` stayed None and the mark stood
        # still. The frame indices were computed correctly meanwhile, so it
        # only showed in the IMAGE on screen not changing at all.
        try:
            interval = self.TICK_MS if self.winfo_viewable() else self.TICK_MS * 4
        except Exception:
            interval = self.TICK_MS * 4
        try:
            self._after_id = self.after(interval, self._tick)
        except Exception:
            self._after_id = None


class _EnsoHero:
    """The mark (残 in enso) drawn DIRECTLY on Today's Canvas - not a widget.

    WHY not a widget: a CTk/tk widget cannot be transparent over a photo
    (`fg_color="transparent"` inherits the parent's SOLID colour), so the
    enso and the text above the dojo always sat on a dark SQUARE.
    `_EnsoHero` is not a widget: `render()` returns a TRANSPARENT PNG (PIL
    RGBA) that the app places on the centre Canvas via `create_image` -
    the alpha blends with the dojo and the circle floats. The text is
    drawn on the same canvas via `create_text` (without a background).
    That makes the box disappear.

    The state (`_live`/`_armed`/`_moon`) and the API (`set_live`/`set_armed`/
    `set_phase_source`/`graduate`/`set_pal`/`phase`) are IDENTICAL to
    `_EnsoButton`, so the coupling stays unchanged: `app.sidebar.enso`
    (alias), the harness asks for `enso._live`/`_armed`, and
    `_apply_listening_visuals` calls `set_live/
    set_armed`, graduation `graduate()`. `_EnsoButton` stays in this file
    (nothing builds it any more, but this class borrows two of its
    constants and a few tests read its source).

    Instead of pre-computing 80 Tk frames it keeps a small cache of PIL
    frames by phase - the same idea (zero per-tick cost for a repeated
    phase), just without a widget.
    """

    FRAMES = 60
    # The same offset and supersampling threshold as `_EnsoButton`, so the
    # enso in the centre looks the same whether a widget or the Canvas
    # drew it.
    PHASE_OFFSET = _EnsoButton.PHASE_OFFSET
    BIG_PX = _EnsoButton.BIG_PX

    def __init__(self, pal, size, on_change=None):
        self._pal = pal
        self.size = int(size)
        self._on_change = on_change
        # `_live` deliberately stays a bare bool - gui_harness_auto.py asks
        # for `enso._live is False/True`. Arming is a separate flag.
        self._live = False
        self._armed = False
        self._moon = False         # graduation: enso = golden moon (once)
        self._phase_fn = None
        self._cache = {}           # (live, armed, moon, faza_bucket, px) -> PIL RGBA

    def set_phase_source(self, fn):
        """`fn()` returns the breath phase 0..1 (the app passes
        `KamaeBar.phase()`) - the enso breathes EXACTLY with the breathing
        line in the header, not at its own pace."""
        self._phase_fn = fn

    def phase(self):
        if callable(self._phase_fn):
            try:
                return float(self._phase_fn()) % 1.0
            except Exception:
                return 0.0
        return 0.0

    def set_live(self, live):
        live = bool(live)
        if live == self._live:
            return
        self._live = live
        if not live:
            # When the app stops listening, the arming no longer holds.
            self._armed = False
        self._emit()

    def set_armed(self, armed):
        """The trigger is armed - the body stays up and a pause is awaited."""
        armed = bool(armed)
        if armed == self._armed:
            return
        self._armed = armed
        self._emit()

    def graduate(self):
        """GRADUATION: the enso closes into a golden moon and stays that way.
        The app keeps running; it is only a mark of achievement, not a
        change of function."""
        if self._moon:
            return
        self._moon = True
        self._emit()

    def set_pal(self, pal):
        """Redraws the enso on a theme change. The enso is an IMAGE - the
        colour is baked in, so the cache has to be thrown away and the
        app left to redraw the canvas."""
        self._pal = pal
        self._cache.clear()
        self._emit()

    def _emit(self):
        if callable(self._on_change):
            try:
                self._on_change()
            except Exception:
                pass

    def render(self, px):
        """PIL RGBA enso for the current state; `px` = PHYSICAL size on Canvas.

        The phase is quantised to `FRAMES` steps and the frame is cached -
        a repeated tick in the same phase draws nothing any more. The tool
        is `hud_paint.render_enso` with the same parameters `_EnsoButton`
        had."""
        px = max(8, int(px))
        live = self._live
        armed = self._armed and self._live
        moon = self._moon
        if live or moon:
            faza_raw = (self.phase() + self.PHASE_OFFSET) % 1.0
            bucket = int(faza_raw * self.FRAMES) % self.FRAMES
        else:
            bucket = 0        # a stopped enso stands still - a single frame
        kluc = (live, armed, moon, bucket, px)
        img = self._cache.get(kluc)
        if img is not None:
            return img
        try:
            style = hud_paint.Style(self._pal)
        except Exception:
            return None
        ss = 2 if px > self.BIG_PX else hud_paint.SS
        faza = bucket / float(self.FRAMES)
        try:
            if moon:
                dych = hud_paint.enso_breath(faza)
                img = hud_paint.render_enso(px, style, live=True, phase=faza,
                                            ss=ss, close=1.0, sheen=False,
                                            halo=0.55 + 0.45 * dych)
            else:
                img = hud_paint.render_enso(px, style, live=live, phase=faza,
                                            armed=armed, ss=ss, sheen=True)
        except Exception:
            return None
        if len(self._cache) > 240:
            self._cache.clear()
        self._cache[kluc] = img
        return img


class _WatchPulse(ctk.CTkFrame):
    """Heart-rate sensor indicator - a ring with a watch and the label
    "Watch" under the navigation group. A click opens the pairing guide.

    STATE LOGIC (in this order):
      1. NOT PAIRED - the ring is dimmed and STILL, the watch grey. There
         is nothing to reflect, so nothing moves.
      2. PAIRED, HEART RATE NOT ARRIVED YET - the ring glows neutrally and
         breathes slowly: "connected, waiting".
      3. HEART RATE RUNNING - the ring beats in the REAL rhythm of the
         watch and takes its colour from the heart-rate zone
         (`HeartStats.zone` - heart rate relative to rest, not load).

    It takes the rhythm from `HeartStats.beat_phase()` - the same source
    as the heart on the in-game HUD, so both beat together. A fixed
    animation (e.g. once a second) is a common mistake: the indicator
    then SHOWS a different heart rate than the watch actually reports.

    The colour comes from the zones the app already has
    (`hud_paint.zone_color`), so the same colour means the same thing
    here and over the game. But colour is NOT the only carrier - the main
    information is carried by the SPEED of the beating, readable even for
    the ~12 % of men who cannot tell red from green.
    """

    # 56 -> 48 (0.3 batch 4): the indicator has the label "Watch" under it
    # like the other panel items, and without it the ring was the largest
    # element of the panel (UX audit). Together with the label it takes up
    # roughly as much as a navigation row.
    SIZE = 48
    FRAMES = 20
    TICK_MS = 60           # dense enough that the beat does not stutter even at 180 BPM
    WAIT_CYCLE_MS = 2600   # "waiting for heart rate" breathes slowly

    def __init__(self, master, pal, on_click=None, tip_fn=None,
                 tip_live_fn=None, caption=""):
        super().__init__(master, fg_color="transparent")
        self._pal = pal
        self._on_click = on_click
        self._state_fn = None
        self._frames = {}
        self._after_id = None
        self._last_key = None
        self._snimok = None
        self.btn = ctk.CTkLabel(self, text="", cursor="hand2")
        self.btn.pack()
        self.btn.bind("<Button-1>", self._clicked)
        # A short label under the ring ("Watch") - before 0.3 the ring was the
        # only panel element without a label (UX audit). A click on the label
        # does the same as a click on the ring.
        self.caption = None
        if caption:
            self.caption = ctk.CTkLabel(self, text=caption, font=ui_kit.ui(10),
                                        text_color=pal.get("text_dim", PAL["text_2"]),
                                        height=16, cursor="hand2")
            self.caption.pack(pady=(1, 0))
            self.caption.bind("<Button-1>", self._clicked)

        # The tooltip said "Pair your watch" even when it was already paired
        # and the ring was beating - that is confusing then, because the
        # click then opens the pairing guide not because pairing is needed.
        def popis():
            if self._je_zive() and callable(tip_live_fn):
                try:
                    return tip_live_fn()
                except Exception:
                    pass
            return tip_fn() if callable(tip_fn) else "Spárovať hodinky"

        self._tip = _HoverTip(self.btn, popis)
        if self.caption is not None:
            self._tip_caption = _HoverTip(self.caption, popis)
        self._build_frames()
        self._tick()

    def set_state_source(self, fn):
        """`fn()` returns (connected, waiting, zone, phase). The widget calls
        it itself on every tick - so the animation is smooth regardless of
        how often data comes from the watch."""
        self._state_fn = fn

    def set_pal(self, pal):
        self._pal = pal
        self._build_frames()
        self._last_key = None
        if self.caption is not None:
            try:
                self.caption.configure(text_color=pal.get("text_dim", PAL["text_2"]))
            except Exception:
                pass

    def destroy(self):
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        super().destroy()

    # ---- internals ----

    def _clicked(self, _event=None):
        if callable(self._on_click):
            self._on_click()

    def _je_zive(self):
        """Is heart rate coming in right now? (for the tooltip label)"""
        if not callable(self._state_fn):
            return False
        try:
            connected, waiting, _, _ = self._state_fn()
        except Exception:
            return False
        return bool(connected) and not waiting

    def _build_frames(self):
        try:
            style = hud_paint.Style(self._pal)
        except Exception:
            return

        def snimok(**kw):
            img = hud_paint.render_pulse_ring(self.SIZE, style, **kw)
            return ctk.CTkImage(light_image=img, dark_image=img,
                                size=(self.SIZE, self.SIZE))

        self._frames = {}
        self._snimok = snimok
        try:
            # Not paired = a single still frame. The sets for the individual
            # heart-rate zones are NOT rendered ahead of time - see `_sada`.
            self._frames[("off",)] = [snimok(connected=False)]
        except Exception:
            pass

    def _sada(self, kluc):
        """The frame set for the given state - rendered only on first use.

        Ahead of time "wait" and all FOUR heart-rate zones used to be
        rendered too, i.e. 101 frames. Most of them the player never sees
        (whoever does not exercise does not get into the 'critical'
        zone), and they were paid for on EVERY start and on EVERY theme
        change - measured ~210 ms on top of a theme switch that had
        previously been optimised to ~700 ms.
        """
        sada = self._frames.get(kluc)
        if sada is not None:
            return sada
        tvorca = getattr(self, "_snimok", None)
        if tvorca is None:
            return None
        try:
            if kluc == ("wait",):
                sada = [tvorca(connected=True, waiting=True,
                               phase=i / float(self.FRAMES))
                        for i in range(self.FRAMES)]
            elif kluc and kluc[0] == "beat":
                sada = [tvorca(connected=True, zone=kluc[1],
                               phase=i / float(self.FRAMES))
                        for i in range(self.FRAMES)]
            else:
                return None
        except Exception:
            return None
        self._frames[kluc] = sada
        return sada

    def _tick(self):
        try:
            self._render_now()
        except Exception:
            pass
        try:
            viditelne = self.winfo_viewable()
        except Exception:
            viditelne = False
        try:
            self._after_id = self.after(
                self.TICK_MS if viditelne else self.TICK_MS * 8, self._tick)
        except Exception:
            self._after_id = None

    def _render_now(self):
        connected, waiting, zone, phase = False, False, None, 0.0
        if callable(self._state_fn):
            try:
                connected, waiting, zone, phase = self._state_fn()
            except Exception:
                pass

        if not connected:
            kluc, index = ("off",), 0
        elif waiting:
            kluc = ("wait",)
            # its own slow breath - independent of heart rate, as there is none
            index = int((time.monotonic() * 1000.0 / self.WAIT_CYCLE_MS
                         * self.FRAMES)) % self.FRAMES
        else:
            kluc = ("beat", zone or "calm")
            index = int(phase * self.FRAMES) % self.FRAMES

        sada = self._sada(kluc)
        if not sada:
            return
        index = index % len(sada)
        if (kluc, index) == self._last_key:
            return          # the same frame - nothing to redraw
        self._last_key = (kluc, index)
        try:
            self.btn.configure(image=sada[index])
        except Exception:
            pass
        # NOTE: THERE MUST NOT BE ANY `self.after(...)` HERE. Once a
        # scheduling block from `_EnsoButton` strayed in here, and since
        # `_render_now` is called from `_tick`, which schedules its next tick
        # itself, one tick gave rise to TWO independent chains. Measured:
        # with heart rate running, 5 -> 88 tasks in 5 seconds and ~3600 calls
        # of this method, while `self._after_id` always holds only the last
        # one - so `destroy()` cancels one chain out of many. With the sensor
        # OFF it does not show (the frame does not change, the method ends
        # already at `_last_key` above), which is why neither a normal app run
        # nor the GUI harness caught it.
        # Scheduling belongs EXCLUSIVELY in `_tick`.


# NOTE: there was a `DojoBand` class here - a fixed-height 130 px photo
# band packed ABOVE the title bar (drawn by `hud_paint.render_dojo_band`
# + `render_lamp_glow`, pulsing lanterns via its own `.after()` chain,
# the intensity changed by the "Dojo background" slider in Settings).
#
# Removed entirely: the title bar belongs at the very top of the window,
# and the band above it was 130 px of dead space taken from the fixed
# window height. With the class went the slider, the `dojo_intensity`
# value in the settings and `suspend_briefly()`, which only damped the
# flicker caused by this band. In `hud_paint` nobody is left to call
# `render_dojo_band`/`render_lamp_glow`.


# ---------------------------------------------------------------------------
# Page container (Dashboard / Profiles / Sound / Settings)
# ---------------------------------------------------------------------------
class PageContainer(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=PAL["bg"])
        self.pages = {}
        # What is on top right now. Without it there was no way to check from
        # outside whether navigation really switched the page - all frames
        # are `place`d, so `winfo_ismapped()` is True for all of them at once.
        self.current = None

    def add_page(self, key, frame):
        frame.place(in_=self, x=0, y=0, relwidth=1, relheight=1)
        self.pages[key] = frame

    def show(self, key):
        if key in self.pages:
            self.pages[key].tkraise()
            self.current = key


# ---------------------------------------------------------------------------
# Command palette (Ctrl+K) - Toplevel popup, arrows + Enter, fuzzy substring
# ---------------------------------------------------------------------------
class CommandPalette:
    # Window width and the space reserved for the right column (category) -
    # at the original 480px longer labels (e.g. "Ukaz mi appku znova
    # (onboarding tour)", i.e. "Show me the app again") collided with the
    # category and it vanished outside the window.
    WIDTH = 600
    HEIGHT = 340
    _CATEGORY_COL_PX = 130

    def __init__(self, root, commands, pal=None, placeholder=""):
        """commands: list of (label:str, tag:str, action:callable)

        `placeholder` is the sentence in the empty search field. It comes
        from app.py already translated (this module does not know i18n) -
        before, it was hard-coded here in Slovak, even in the English
        window.

        `pal` is the palette of the app's active theme. NOTE: before, the
        command palette did not get it at all and was coloured ENTIRELY
        from the module PAL - which is tuned towards green (#121714 card,
        #2a3630 border, #9aa39b text), while the Sumi theme is neutral
        (#191A22 / #2A2B36 / #9A9488). So after opening, a window from a
        different colour family popped up over the app. The same bug the
        TitleBar had - the module PAL stays here only as a fallback, when
        the palette is built without a theme.
        """
        self.root = root
        self.commands = commands
        self.placeholder = placeholder
        self.pal = pal or {}
        self.top = None
        self.listbox = None
        self.entry = None
        self.filtered = commands
        self._row_font = None

    def _c(self, key, fallback):
        return self.pal.get(key, PAL[fallback])

    def open(self):
        if self.top is not None:
            return
        c = self._c
        self.top = ui_kit.priprav_popup(tk.Toplevel(self.root))
        self.top.overrideredirect(True)
        self.top.configure(bg=c("border", "border_strong"))
        self.top.attributes("-topmost", True)

        # DPI: `self.top` is an ORDINARY tk.Toplevel, not a CTk window - its
        # `geometry()` takes PHYSICAL pixels and scales nothing. But the fonts
        # inside do scale (Tk scaling), so on a 150 % display the palette was
        # physically 600x340 px with a 150 % large font: of 16 commands 7
        # were visible and the last row cut in half, without a scrollbar.
        # That is why we multiply the size by the same scaling that CTk
        # windows use (the same pattern as ui_dialogs._centered_geometry).
        scaling = 1.0
        try:
            from customtkinter.windows.widgets.scaling.scaling_tracker \
                import ScalingTracker
            scaling = ScalingTracker.get_window_scaling(self.root) or 1.0
        except Exception:
            pass
        w = int(round(self.WIDTH * scaling))
        h = int(round(self.HEIGHT * scaling))
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + int(round(90 * scaling))
        self.top.geometry(f"{w}x{h}+{x}+{y}")

        card = ctk.CTkFrame(self.top, fg_color=c("surface", "bg_elevated"),
                            corner_radius=10)
        card.pack(fill="both", expand=True, padx=1, pady=1)

        # Search row: magnifier + text field. The magnifier was not here, and
        # the top strip of the palette looked like an empty hole - CTkEntry
        # hides its placeholder once focused (`focus_set()` below), so until
        # the player starts typing, nothing at all is visible in it. The icon
        # keeps the context even with an empty field, and it is the same
        # magnifier with which the palette is opened from the side panel.
        search = ctk.CTkFrame(card, fg_color="transparent")
        search.pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(search, text="⌕", width=22, anchor="w",
                     text_color=c("text_faint", "text_3"),
                     font=("Segoe UI", 16)).pack(side="left")

        self.entry_var = tk.StringVar()
        self.entry = ctk.CTkEntry(
            search, textvariable=self.entry_var, placeholder_text=self.placeholder,
            fg_color="transparent", border_width=0, text_color=c("text", "text"),
            placeholder_text_color=c("text_faint", "text_3"), height=40,
            font=ui_kit.ui(13),
        )
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry_var.trace_add("write", lambda *a: self._refresh())

        # Divider line under the search - the same pattern as the card header
        # (`ui_kit.Panel`) and the title bar, so that the palette looks like a
        # piece of the same app, not like a foreign window.
        ctk.CTkFrame(card, fg_color=c("line_soft", "border"),
                     bg_color=c("line_soft", "border"), height=1,
                     corner_radius=0).pack(fill="x", padx=1, pady=(8, 0))

        # List + scrollbar in one row. There was NO scrollbar here before:
        # there are 16 commands and even after the DPI fix ~13 of them fit,
        # so the rest was below the edge without any hint that it can be
        # scrolled (tk.Listbox draws no scrollbar by itself). CTkScrollbar is
        # the same element the app's scrollable pages use.
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="both", expand=True, padx=10, pady=10)

        self._row_font = tkfont.Font(family="Segoe UI", size=11)
        self.listbox = tk.Listbox(
            row, bg=c("surface", "bg_elevated"), fg=c("text_dim", "text_2"),
            bd=0, highlightthickness=0,
            selectbackground=c("accent2", "bg_hover"),
            selectforeground=c("accent_hover", "accent"),
            font=self._row_font, activestyle="none",
        )
        self.listbox.pack(side="left", fill="both", expand=True)

        self.scrollbar = ctk.CTkScrollbar(
            row, command=self.listbox.yview, width=12,
            fg_color="transparent", button_color=c("surface_alt", "bg_hover"),
            button_hover_color=c("accent", "accent"))
        self.scrollbar.pack(side="right", fill="y", padx=(6, 0))
        self.listbox.configure(yscrollcommand=self.scrollbar.set)

        self.entry.bind("<Down>", self._move_down)
        self.entry.bind("<Up>", self._move_up)
        self.entry.bind("<Return>", self._activate)
        self.listbox.bind("<Return>", self._activate)
        # A single click RUNS the command straight away (like the palette in
        # editors) - before, a click only selected it and the player waited
        # for something to happen ("can't click it").
        self.listbox.bind("<ButtonRelease-1>", self._activate_from_click)
        self.listbox.bind("<Double-Button-1>", self._activate_from_click)
        # Escape on the `entry` itself was not enough: when the player clicked
        # on the list (e.g. moved the focus out of the text field with the
        # arrows/the mouse), Escape stopped responding. We also bind it on
        # `self.top` (bind_all at the window level), so it works regardless
        # of which element has focus.
        self.entry.bind("<Escape>", lambda e: self.close())
        self.listbox.bind("<Escape>", lambda e: self.close())
        self.top.bind("<Escape>", lambda e: self.close())
        self.top.bind("<FocusOut>", lambda e: self.root.after(120, self._maybe_close))

        self._refresh()
        self.entry.focus_set()

    def _maybe_close(self):
        try:
            if self.top and self.root.focus_get() is None:
                self.close()
        except Exception:
            pass

    def _refresh(self):
        query = self.entry_var.get().strip().lower()
        self.filtered = ([c for c in self.commands if query in c[0].lower()]
                         if query else self.commands)
        self.listbox.delete(0, "end")
        # The alignment of the category (right column) is computed in pixels,
        # not in a number of characters - "Segoe UI" is not monospace, so a
        # fixed number of spaces (the original `:<45`) pushed the category out
        # of the visible window width with a longer label. A label that is too
        # long is rather shortened with "…" than allowed to push the category
        # out.
        font = self._row_font
        space_w = max(1, font.measure(" "))
        prefix = "  "
        text_col_px = max(120, self.WIDTH - self._CATEGORY_COL_PX - font.measure(prefix))
        for label, tag, _ in self.filtered:
            trimmed = label
            if font.measure(trimmed) > text_col_px:
                while trimmed and font.measure(trimmed + "…") > text_col_px:
                    trimmed = trimmed[:-1]
                trimmed = (trimmed + "…") if trimmed else label[:1]
            pad_px = max(space_w, text_col_px - font.measure(trimmed))
            pad = " " * max(1, int(round(pad_px / space_w)))
            self.listbox.insert("end", f"{prefix}{trimmed}{pad}{tag}")
        if self.filtered:
            self.listbox.selection_set(0)

    def _move_down(self, event):
        self._move(1)
        return "break"

    def _move_up(self, event):
        self._move(-1)
        return "break"

    def _move(self, delta):
        if not self.filtered:
            return
        sel = self.listbox.curselection()
        idx = (sel[0] + delta) % len(self.filtered) if sel else 0
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(idx)
        self.listbox.see(idx)

    def _activate(self, event):
        sel = self.listbox.curselection()
        if sel and self.filtered:
            _, _, action = self.filtered[sel[0]]
            self.close()
            action()
        return "break"

    def _activate_from_click(self, event):
        if self.top is None:
            return "break"
        """Click on a row - `curselection()` is already up to date at this
        point (Tk sets the selection BEFORE firing <Double-Button-1>), but we
        rather use the index under the cursor directly, so the click works
        even if the order of events were different."""
        index = self.listbox.nearest(event.y)
        if 0 <= index < len(self.filtered):
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(index)
            _, _, action = self.filtered[index]
            self.close()
            action()
        return "break"

    def close(self):
        if self.top is not None:
            self.top.destroy()
            self.top = None


# ---------------------------------------------------------------------------
# Hover tooltip (`_HoverTip`). The quick dock that used to sit in this
# section is gone - see the `QuickDock` NOTE below.
# ---------------------------------------------------------------------------
class _HoverTip:
    """A simple tooltip attached to a widget - the text is created by
    calling `text_fn()` on every show (not once at creation), so that it
    can reflect the current state (e.g. "Stop" / "Start")."""

    WATCHDOG_MS = 250

    def __init__(self, widget, text_fn, below=False):
        self.widget = widget
        self.text_fn = text_fn
        # `below=True`: the tooltip BELOW the widget. For elements in the
        # title bar - above them there is already the window edge, and a
        # multi-line tooltip over a small element would cover the cursor and
        # flicker (Leave -> hide -> Enter).
        self.below = below
        self.tip = None
        self._watchdog = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)
        # A click on a button often opens a popup (snooze menu, color picker)
        # - the tooltip would stay hanging over it, because it is topmost.
        try:
            widget.bind("<Button-1>", self._hide, add="+")
        except Exception:
            pass

    def _show(self, _event=None):
        if self.tip is not None:
            return
        x = self.widget.winfo_rootx()
        if self.below:
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        else:
            y = self.widget.winfo_rooty() - 30
        self.tip = ui_kit.priprav_popup(tk.Toplevel(self.widget))
        self.tip.overrideredirect(True)
        self.tip.attributes("-topmost", True)
        self.tip.geometry(f"+{x}+{y}")
        # `_dock_pal` is set by the dock (it has the palette at hand),
        # everything else takes the current theme - not the module PAL, which
        # is still from mockup v4.
        pal = getattr(self.widget, "_dock_pal", None) or theme_pal()
        # Border + the same rounding as the panels: the tooltip is an app
        # surface, not a system tooltip. Without the border it merged with the
        # dark window background.
        frame = ctk.CTkFrame(self.tip, fg_color=pal.get("surface_alt", PAL["bg_elevated"]),
                             corner_radius=8, border_width=1,
                             border_color=pal.get("border", PAL["border"]))
        frame.pack()
        ctk.CTkLabel(frame, text=self.text_fn(), fg_color="transparent",
                     text_color=pal.get("text", PAL["text"]),
                     font=ui_kit.ui(10), padx=10, pady=5).pack()
        self._arm_watchdog()

    def _arm_watchdog(self):
        """While the tooltip is visible, check it really has a reason to be.

        <Leave> alone is not enough. The tooltip is a `topmost` Toplevel,
        so once it goes wrong, it hangs over the whole app until it is
        closed - and <Leave> really CAN get lost:
          * the widget disappears when the window is rebuilt (a
            theme/language change calls `_build_ui`) - then nobody is
            left to send <Leave>,
          * the window moves/appears UNDER the cursor, so Tk sends
            <Enter> without the mouse moving at all, and <Leave> never
            comes,
          * a click opens a popup that takes over input.
        That is why every 250 ms we check a hard condition: the widget
        exists and the cursor really is over it. Otherwise we hide the
        tooltip.
        """
        try:
            self._watchdog = self.widget.after(self.WATCHDOG_MS, self._tick)
        except Exception:
            self._watchdog = None

    def _pointer_inside(self):
        try:
            w = self.widget
            if not w.winfo_exists() or not w.winfo_ismapped():
                return False
            px, py = w.winfo_pointerxy()
            x, y = w.winfo_rootx(), w.winfo_rooty()
            return (x <= px < x + w.winfo_width()
                    and y <= py < y + w.winfo_height())
        except Exception:
            return False

    def _tick(self):
        self._watchdog = None
        if self.tip is None:
            return
        if not self._pointer_inside():
            self._hide()
            return
        self._arm_watchdog()

    def _hide(self, _event=None):
        if self._watchdog is not None:
            try:
                self.widget.after_cancel(self._watchdog)
            except Exception:
                pass
            self._watchdog = None
        if self.tip is not None:
            try:
                self.tip.destroy()
            except Exception:
                pass
            self.tip = None


# NOTE: MinimalPanel (BPM + 4 icons + enso in a separate small app
# window) was here - removed. The same function is now part of the
# in-game HUD panel (hud_paint.render_hud_trigger_row + hud.StatsHud.
# configure_triggers), not a separate mode of the whole app. See
# DandurfApp._hud_trigger_info / _refresh_hud_trigger_row in app.py.


# NOTE: there was a `QuickDock` class here - three icons at the bottom
# of the side panel (🔊 mute, 😴 snooze, ⌘ quick profile). Removed
# deliberately; the reason is in `app.py` at `_build_ui`, where it was
# built. In short: one-click muting gets used exactly when the cue is
# most justified, and so it defeats the app. Snooze stayed, but it has
# a global shortcut - that is where the player needs it, not in the
# window.


# ---------------------------------------------------------------------------
# Page demo - in PHASE 2 real content from settings_model/audio_engine goes here
# ---------------------------------------------------------------------------
# NOTE: this file once had its own test `main()` function at the end
# with an old, placeholder UI (non-working buttons with
# `print("TODO...")`, a standalone dashboard not connected to the real
# app). The real app ALWAYS starts via `main.py` -> `app.DandurfApp`;
# this script was never called. It was a dead branch that someone ran
# directly by mistake (`python ui_shell.py`) and so saw the old graphics
# and non-working buttons - which is why it was removed, so that this
# cannot happen again.
