"""Guided tour - a guided walk through the app after the first start.

What it is
----------
After the onboarding is closed (or on request from Settings) a short
tour starts: one by one, a bubble with a description of "what is here
and what it is for" appears by individual parts of the interface. The
player clicks Next, or Skip at any time.

Why a separate module
---------------------
The onboarding explains WHY the app exists (before it is opened). The
guided tour explains WHERE WHAT is (in the already opened app). They are
two different things and should not be mixed - hence a separate file.

How it works
------------
Each step points at a specific widget (e.g. a menu item, the breathing
bar). The bubble is placed next to it and the target widget is gently
highlighted with a frame. Before a step, if needed, the right page is
switched to, so that the target element is visible.

The bubble is a separate overrideredirect window (`tk.Toplevel`) - so it
can be placed anywhere over the app and has no OS frame of its own. The
target highlight is a thin coloured frame drawn into an overlay window
above it.

No dependency on the app's content - it gets a reference to the app and
from the list of steps takes the target widgets via lambda (so that they
are evaluated only at the time of the step, when they already exist).
"""

import tkinter as tk

import customtkinter as ctk

import ui_kit
from i18n import tr


# Tour steps in ONE place: (i18n key, page, target, side,
# action).
#
# The target is a description, not a widget - it is evaluated only at
# the time of the step, when it already exists (`_target`). The table is
# static on purpose: the app can tell from it how many steps the tour
# has without having to build it (the "App tour" row in Settings shows
# "step 4 of 6").
#
#   None            - bubble in the centre of the window, no pointing
#   ("nav", key)    - side menu item / tab in Settings
#   ("attr", name)  - app attribute (panel, bar, card)
#   ("enso",)       - the mark in the centre of Today (app state, a click
#                     starts/stops it)
#   ("done",)       - the end: the Settings item when heart rate is
#                     coming in, otherwise the watch indicator in the
#                     side panel (see `_target`)
#
# The action is an extra button in the bubble: "pair" opens the pairing
# guide and after it is closed the tour continues with the next step.
#
# FIVE PLACES, NOT TEN (0.3). The tour had 10 bubbles and promised "a
# few seconds" - together with the introduction and pairing that was
# around 20 numbered stops before the first heart rate reading. The steps
# "kamae" and "dock" talked about the same thing (start / stop), "sound",
# "ingame" and "today" described what the player finds by themselves
# when they click there. What stayed is what the app does not work
# without or what is not visible: the mark and its state, heart rate
# reception, cues, history and where to start the tour again (or that
# without a watch the app stays silent).
_STEPS = (
    ("welcome", "dnes", None, "center", None),
    ("dock", "dnes", ("enso",), "right", None),
    ("sensor", "vhre", ("attr", "hr_card"), "left", "pair"),
    ("triggers", "spustace", ("nav", "spustace"), "below", None),
    ("history", "historia", ("nav", "historia"), "right", None),
    ("done", "dnes", ("done",), "right", None),
)


class TourStep:
    """One step of the tour.

    target_fn : callable -> widget (evaluated only at the step; None = bubble
                in the centre of the window, not pointing at an element)
    page      : which page to switch to before the step (None = no change)
    title/body: texts (i18n keys are translated in the tour, here already text)
    side      : where to place the bubble relative to the target
                ('right'/'left'/'above'/'below'/'center')
    key       : step key from `_STEPS` (the end picks its text only when drawing)
    action    : extra button in the bubble (None / "pair")
    """

    __slots__ = ("target_fn", "page", "title", "body", "side", "key", "action")

    def __init__(self, target_fn=None, page=None, title="", body="", side="right",
                 key="", action=None):
        self.target_fn = target_fn
        self.page = page
        self.title = title
        self.body = body
        self.side = side
        self.key = key
        self.action = action


class GuidedTour:
    """App tour. Create it with a reference to the app and call start()."""

    BUBBLE_W = 300
    # How many steps the tour has - the app needs to know that even without
    # building it (the "App tour" row in Settings).
    STEP_COUNT = len(_STEPS)

    def __init__(self, app, start_index=0):
        self.app = app
        self.pal = app.pal
        self.steps = self._build_steps()
        # The tour can be left midway and CONTINUED later - always starting
        # from the beginning means nobody looks at it a second time.
        self._index = max(0, min(int(start_index or 0), len(self.steps) - 1))
        self._bubble = None
        self._highlight = None
        # _show() draws the bubble with a delay (after 60 ms). If another Next
        # or Skip comes in the meantime, the old delayed _place() would draw a
        # bubble that nothing points to any more - and it would stay hanging
        # forever (caught live: a double click on Next = two bubbles). That is
        # why the waiting job is cancelled and every _place carries the step
        # generation.
        self._place_job = None
        self._gen = 0
        self._finished = False

    # ---- step definitions ----

    def _nav_row(self, key):
        """Navigation target widget: the main item in the side menu, or a tab
        in Settings (Cues/Sound/In game/Guide are tabs after the
        feedback, not menu items). None -> bubble in the centre."""
        app = self.app
        sb = getattr(app, "sidebar", None)
        if sb is not None and key in getattr(sb, "rows", {}):
            return sb.rows[key]
        nav = getattr(app, "settings_nav", None)
        if nav is not None:
            return nav.buttons.get(key)
        return None

    def _target(self, spec):
        """Widget by its `_STEPS` description - at step time, not on build."""
        if spec is None:
            return None
        if spec[0] == "nav":
            return self._nav_row(spec[1])
        if spec[0] == "attr":
            return getattr(self.app, spec[1], None)
        if spec[0] == "enso":
            # The mark is no longer a widget but a drawing in the centre of
            # Today (`_EnsoHero` on `app.dnes_canvas`). The bubble points at
            # the canvas - `app.sidebar.enso` is only a state without
            # `winfo_*`, it could not be targeted.
            return getattr(self.app, "dnes_canvas", None)
        if spec[0] == "done":
            # The end points at the place that belongs to it: where the tour
            # is started again - or, while heart rate is not coming in, at the
            # watch indicator, because without the watch the app stays silent
            # and that is the last thing one needs to know.
            if self._tep_chodi():
                return self._nav_row("nastavenia")
            return getattr(getattr(self.app, "sidebar", None), "pair_btn", None)
        return None

    def _tep_chodi(self):
        """Is heart rate coming in from the watch right now? The same condition
        as the watch indicator in the side panel (`_watch_pulse_state`):
        reception on and the last BPM known."""
        app = self.app
        if not getattr(app, "hr_monitoring_enabled", False):
            return False
        return bool(getattr(getattr(app, "hr_stats", None), "last_bpm", None))

    def _body(self, step):
        """Bubble text. The end is chosen only when drawing, not when building:
        the watch can be paired even DURING the tour (the action in the
        heart rate step) and without it "Enjoy your game" would promise
        something that will not happen - without heart rate the app stays
        silent."""
        if step.key == "done" and not self._tep_chodi():
            return tr("tour.done.no_watch")
        if step.key == "triggers":
            # "NOT NOW" ONCE, AT THE CUES (0.3): before the first cue only
            # the journal mentioned the shortcut. The step says WHEN the app
            # speaks up - right after that, how to silence it at a bad
            # moment. The real key combination is named, and only when it
            # really applies - otherwise it offers the icons in the tray.
            return step.body + " " + self._veta_teraz_nie()
        return step.body

    def _veta_teraz_nie(self):
        """Sentence about "not now" - with the shortcut that really applies."""
        zisti = getattr(self.app, "_skratka_teraz_nie", None)
        try:
            skratka = zisti() if callable(zisti) else ""
        except Exception:
            skratka = ""
        if skratka:
            return tr("tour.triggers.snooze", combo=skratka)
        return tr("tour.triggers.snooze_tray")

    def _build_steps(self):
        return [
            TourStep(target_fn=(lambda s=spec: self._target(s)), page=page,
                     title=tr(f"tour.{key}.title"), body=tr(f"tour.{key}.body"),
                     side=side, key=key, action=action)
            for key, page, spec, side, action in _STEPS
        ]

    # ---- life cycle ----

    def start(self):
        if not self.steps:
            return
        self._show()

    def _save_progress(self, index):
        """Where the tour ended - so it can be resumed, not started over."""
        try:
            self.app.save_tour_progress(index)
        except Exception:
            pass

    def skip(self):
        """Skip = "not now", not "never again". The position is remembered and
        Settings offers Continue."""
        self._finished = True
        self._cleanup()
        self._save_progress(self._index)
        try:
            self.app.mark_tour_seen()
        except Exception:
            pass

    def _cleanup(self):
        self._gen += 1                      # invalidates the delayed _place()
        if self._place_job is not None:
            try:
                self.app.root.after_cancel(self._place_job)
            except Exception:
                pass
            self._place_job = None
        for attr in ("_bubble", "_highlight"):
            w = getattr(self, attr)
            if w is not None:
                try:
                    w.destroy()
                except Exception:
                    pass
                setattr(self, attr, None)

    def finish(self):
        """The tour ran to the end - the position is reset, so the next start
        from Settings begins from the beginning."""
        self._finished = True
        self._cleanup()
        self._save_progress(0)
        # remember that the tour has been seen (app saves it to the settings)
        try:
            self.app.mark_tour_seen()
        except Exception:
            pass

    def _next(self):
        if self._finished:
            return
        self._index += 1
        if self._index >= len(self.steps):
            self.finish()
        else:
            self._save_progress(self._index)
            self._show()

    def _pair(self):
        """Action of the heart rate step: opens the watch pairing guide.

        The bubbles disappear meanwhile - they are topmost and the modal
        guide would otherwise sit under them. The position is saved
        already at the NEXT step, so if the app is closed during pairing,
        the tour in Settings picks up after this step. After the guide is
        closed it continues by itself (`_after_pairing`)."""
        if self._finished:
            return
        self._cleanup()
        self._save_progress(min(self._index + 1, len(self.steps) - 1))
        try:
            self.app.open_watch_pairing(on_close=self._after_pairing)
        except Exception:
            self._after_pairing()

    def _after_pairing(self):
        # In the meantime the tour may have ended or been replaced by a new one
        # (`start_tour` from Settings) - then this one has nothing to show.
        if self._finished or getattr(self.app, "_tour", self) is not self:
            return
        self._next()

    # ---- drawing a step ----

    def _show(self):
        self._cleanup()
        step = self.steps[self._index]
        if step.page:
            try:
                self.app.sidebar._select(step.page)
            except Exception:
                pass
        # let the UI redraw, then place the bubble (the widget must have a size)
        gen = self._gen
        self._place_job = self.app.root.after(60, lambda: self._place(step, gen))

    def _place(self, step, gen=None):
        self._place_job = None
        if self._finished or (gen is not None and gen != self._gen):
            return                          # the step changed meanwhile / the tour ended
        target = None
        if step.target_fn is not None:
            try:
                target = step.target_fn()
            except Exception:
                target = None

        # highlight the target widget
        rect = self._widget_rect(target) if target is not None else None
        if rect is not None:
            self._draw_highlight(rect)

        # build the bubble
        self._draw_bubble(step, rect)

    def _widget_rect(self, widget):
        """(x, y, w, h) of the widget in screen coordinates, or None."""
        try:
            widget.update_idletasks()
            x = widget.winfo_rootx()
            y = widget.winfo_rooty()
            w = widget.winfo_width()
            h = widget.winfo_height()
            if w <= 1 or h <= 1:
                return None
            return (x, y, w, h)
        except Exception:
            return None

    def _draw_highlight(self, rect):
        x, y, w, h = rect
        pad = 4
        hl = ui_kit.priprav_popup(tk.Toplevel(self.app.root))
        hl.overrideredirect(True)
        hl.attributes("-topmost", True)
        try:
            hl.attributes("-transparentcolor", "#010101")
        except Exception:
            pass
        hl.geometry(f"{w + pad * 2}x{h + pad * 2}+{x - pad}+{y - pad}")
        canvas = tk.Canvas(hl, width=w + pad * 2, height=h + pad * 2,
                           bg="#010101", highlightthickness=0, bd=0)
        canvas.pack()
        canvas.create_rectangle(2, 2, w + pad * 2 - 2, h + pad * 2 - 2,
                                outline=self.pal["accent"], width=2)
        self._highlight = hl

    def _draw_bubble(self, step, rect):
        pal = self.pal
        # The bubble holds CTk widgets in a plain tk.Toplevel, so the
        # ScalingTracker registers it - without priprav_popup it would crash
        # on `block_update_dimensions_event` at every DPI change (crash.log).
        bubble = ui_kit.priprav_popup(tk.Toplevel(self.app.root))
        bubble.overrideredirect(True)
        bubble.attributes("-topmost", True)
        bubble.configure(bg=pal["accent2"])

        frame = ctk.CTkFrame(bubble, fg_color=pal["surface"], corner_radius=10,
                             border_width=2, border_color=pal["accent"])
        frame.pack(fill="both", expand=True, padx=2, pady=2)

        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=18, pady=16)

        # step X of Y
        ctk.CTkLabel(inner, text=tr("tour.step_of", n=self._index + 1,
                                    total=len(self.steps)),
                     font=("Segoe UI", 9, "bold"),
                     text_color=pal["accent"]).pack(anchor="w")
        ctk.CTkLabel(inner, text=step.title, font=("Segoe UI", 14, "bold"),
                     text_color=pal["text"], anchor="w", justify="left",
                     wraplength=self.BUBBLE_W - 40).pack(anchor="w", pady=(4, 6))
        ctk.CTkLabel(inner, text=self._body(step), font=("Segoe UI", 11),
                     text_color=pal["text_dim"], anchor="w", justify="left",
                     wraplength=self.BUBBLE_W - 40).pack(anchor="w")

        if step.action == "pair":
            # Pairing straight from the bubble - otherwise the heart rate step
            # only says that without a watch the app stays silent, and the
            # player would look for the guide themselves.
            ctk.CTkButton(inner, text=tr("tour.sensor.pair"), height=30,
                          corner_radius=8, fg_color="transparent", border_width=1,
                          border_color=pal["accent"], hover_color=pal["surface_alt"],
                          text_color=pal["accent"], font=("Segoe UI", 11, "bold"),
                          command=self._pair).pack(anchor="w", pady=(12, 0))

        # buttons
        btns = ctk.CTkFrame(inner, fg_color="transparent")
        btns.pack(fill="x", pady=(14, 0))
        # `ui_kit.button` (0.3 batch 4b): the same kinds of buttons as in
        # the app's windows and the font of the app's language (ja/zh have
        # their own).
        ui_kit.button(btns, pal, tr("tour.skip"), kind="quiet", width=90, height=30,
                      font=ui_kit.ui(11), command=self.skip).pack(side="left")
        last = self._index == len(self.steps) - 1
        ui_kit.button(btns, pal, tr("tour.done_btn") if last else tr("tour.next"),
                      kind="primary", width=110, height=30, font=ui_kit.ui(11, "bold"),
                      command=self._next).pack(side="right")

        bubble.update_idletasks()
        bw = bubble.winfo_reqwidth()
        bh = bubble.winfo_reqheight()
        x, y = self._bubble_position(step, rect, bw, bh)
        bubble.geometry(f"+{x}+{y}")
        self._bubble = bubble

    def _bubble_position(self, step, rect, bw, bh):
        """Bubble position - next to the target, or in the window centre."""
        root = self.app.root
        root.update_idletasks()
        rx, ry = root.winfo_rootx(), root.winfo_rooty()
        rw, rh = root.winfo_width(), root.winfo_height()
        gap = 14

        if rect is None or step.side == "center":
            return (rx + (rw - bw) // 2, ry + (rh - bh) // 2)

        tx, ty, tw, th = rect
        if step.side == "right":
            x, y = tx + tw + gap, ty + th // 2 - bh // 2
        elif step.side == "left":
            x, y = tx - bw - gap, ty + th // 2 - bh // 2
        elif step.side == "above":
            x, y = tx + tw // 2 - bw // 2, ty - bh - gap
        else:  # below
            x, y = tx + tw // 2 - bw // 2, ty + th + gap

        # keep the bubble on the monitor where the app window is.
        # winfo_screenwidth() is ALWAYS the primary screen - on a second
        # monitor (e.g. x < 0) it would pull the bubble to the first one,
        # away from the app.
        left = top = 0
        right, bottom = root.winfo_screenwidth(), root.winfo_screenheight()
        try:
            import display
            cx, cy = rx + rw // 2, ry + rh // 2
            mon = next((m for m in display.monitors(root) if m.contains(cx, cy)), None)
            if mon is not None:
                left, top = mon.x, mon.y
                right, bottom = mon.x + mon.width, mon.y + mon.height
        except Exception:
            pass
        x = max(left + 8, min(right - bw - 8, x))
        y = max(top + 8, min(bottom - bh - 8, y))
        return (x, y)
