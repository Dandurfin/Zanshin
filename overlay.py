"""In-game somatic visuals (Overlay) - one independent visual for each of
the 4 slots (grounding / jaw / release / breath).

What changed since alpha 0.4, and why
-------------------------------------
1. RESOLUTION. Visual sizes are given in "1080p pixels" and are
   multiplied by `Monitor.scale` (monitor height / 1080). So on 4K
   everything is 2x larger and takes up the same PART of the screen -
   before, the visual on 4K was a quarter of the size.

2. MULTIPLE MONITORS. The position is computed relative to a specific
   monitor from `display.resolve_target()`, not relative to
   `winfo_screenwidth()` (which is always only the primary screen).
   Whoever has the game on a second monitor will finally see the visual
   there. The default, "auto", takes the monitor that has the active
   window - i.e. the game.

3. LOOK. Drawing moved from tk.Canvas (hard edges, emoji) to PIL +
   UpdateLayeredWindow (per-pixel alpha, glow, antialiasing) - see
   hud_paint.py and layer_window.py.

Anti-cheat
----------
No change from the original design, only stricter: the window is
click-through (WS_EX_TRANSPARENT), never activates (WS_EX_NOACTIVATE),
is not in Alt+Tab (WS_EX_TOOLWINDOW), injects nothing and knows nothing
about the game except which monitor has the active window right now.
Details in layer_window.py.
"""

import time

try:
    from PIL import ImageDraw
except Exception:  # pragma: no cover
    ImageDraw = None

import display
import hud_paint
import logging_setup
from hud_paint import Style
from settings_model import OVERLAY_DEFAULT_POS
from layer_window import LayeredSurface

log = logging_setup.get_logger("overlay")


class _SlotOverlay:
    """One specific in-game visual (for 1 slot).

    The skeleton is shared by all 4:
      * its own click-through window (LayeredSurface),
      * fade-in -> animation -> fade-out, all through Tk `.after()` (no
        time.sleep - the same thread also serves the activity poll and
        the cue trigger, so sleeping in it would stop both),
      * a new trigger while an old animation is running cancels it at
        once (`play() -> self.stop()`) and starts from zero.

    The fade costs nothing extra: only the constant alpha of the layered
    window changes, the frame is not redrawn.
    """

    TICK_MS = 40                 # 25 fps - breathing and an impact need no more
    FADE_MS = 260
    HOLD_S = 3.0

    # breathing cycle - default 4 s inhale / 6 s exhale, the player can
    # change them in Settings (see SomaticOverlayManager.set_breath_seconds)
    INHALE_S_DEFAULT = 4.0
    EXHALE_S_DEFAULT = 6.0
    CYCLES = 2                   # 2 cycles per slot trigger

    # How long the "intro" animation of each visual runs. After it ends
    # the frame is NO LONGER REDRAWN (the image is static), so keeping
    # the visual on screen costs no performance.
    INTRO_S = {"grounding": 1.35, "jaw": 0.95, "release": 1.15}

    def __init__(self, root, visual, base_size, manager):
        self.root = root
        self.visual = visual
        self.base_w, self.base_h = base_size
        self.manager = manager

        self.enabled = False
        self.scale = 1.0
        self.pos = (50.0, 50.0)     # % of the width/height of the TARGET monitor
        self.color = None           # None = theme accent; otherwise #rrggbb
        self.inhale_s = self.INHALE_S_DEFAULT
        self.exhale_s = self.EXHALE_S_DEFAULT

        self.surface = None
        self.w = self.h = 0
        self._job = None
        self._gen = 0
        self._start_time = None
        self._ss = 2
        self._static_done = False
        self._label = None
        # "Test visual" mode (drag & drop). When it is on, the visual does
        # NOT hide after HOLD_S and can be grabbed with the mouse; when it
        # ends, the new position is saved via on_test_moved and
        # click-through comes back.
        self._test_mode = False
        self._drag_origin = None
        self.on_test_moved = None    # callback(index_pos_x, index_pos_y) - set by the manager

    # ---------- configuration ----------

    def configure(self, enabled=None, scale=None, pos=None, color=None):
        if enabled is not None:
            self.enabled = bool(enabled)
            if not self.enabled:
                self.stop()
        if scale is not None:
            self.scale = max(0.5, min(2.0, float(scale)))
        if pos is not None:
            self.pos = pos
        if color is not None:
            # "" (empty string) means "go back to the theme colour"
            self.color = color or None

    def set_label(self, label):
        self._label = label

    def set_breath_seconds(self, inhale_s, exhale_s):
        self.inhale_s = max(0.5, float(inhale_s))
        self.exhale_s = max(0.5, float(exhale_s))

    # ---------- triggering ----------

    def trigger(self):
        """Returns True if the visual really started drawing.

        The silent branch has the visual as its ONLY stimulus — when it
        fails, the measurement would compare the cue against nothing and
        mark the window `valid:True` without a confirmed delivery (bug
        B17). The return value tells the caller. A disabled visual
        (`not enabled`) is not a failure — then the cue was not supposed
        to be delivered at all; it returns False so that it is not
        measured.
        """
        if self.enabled:
            return self.play()
        return False

    @property
    def is_active(self):
        return self.surface is not None

    def test(self):
        """The "Test visual" button - NEW behaviour (drag & drop).

        The visual is shown PERMANENTLY (until the player turns the test
        off) and can be grabbed with the mouse and dragged anywhere.
        Before, it was only a 3-second preview at a fixed position, so the
        position could not be fine-tuned visually.

        A second call of test() (or stop_test) ends the mode and saves the
        position.
        """
        if self._test_mode:
            self.stop_test()
            return
        self._test_mode = True
        self.play()

    def stop_test(self):
        """Ends drag mode, saves the position and restores click-through."""
        if not self._test_mode:
            return
        self._save_test_position()
        self._test_mode = False
        self.stop()

    def _save_test_position(self):
        """Converts the window position back to monitor % and reports it."""
        if self.surface is None or self.surface.top is None:
            return
        try:
            monitor = self.manager.target_monitor()
            x = self.surface.top.winfo_x()
            y = self.surface.top.winfo_y()
            # window centre in % of the monitor area (same convention as display.place)
            cx = x + self.w / 2.0
            cy = y + self.h / 2.0
            px = max(0.0, min(100.0, (cx - monitor.x) / monitor.width * 100.0))
            py = max(0.0, min(100.0, (cy - monitor.y) / monitor.height * 100.0))
            self.pos = (px, py)
            if callable(self.on_test_moved):
                self.on_test_moved(px, py)
        except Exception:
            pass

    def play(self):
        """Draws the visual. Returns True on success, False on failure.

        The error branches are LOGGED — until now it was a silent
        `_destroy(); return`, so when the visual did not draw, no trace
        was left and the measurement counted it as valid anyway (bug B17).
        """
        self.stop()
        self._gen += 1
        gen = self._gen
        try:
            self._build_window()
        except Exception:
            log.exception("in-game vizuál sa nepodarilo postaviť (slot %s)",
                          getattr(self, "index", "?"))
            self._destroy()
            return False
        self._static_done = False
        self._start_time = time.time()
        try:
            self._render(0.0)
        except Exception:
            log.exception("in-game vizuál sa nepodarilo vykresliť (slot %s)",
                          getattr(self, "index", "?"))
            self._destroy()
            return False
        self.surface.set_alpha(0.0)
        self.surface.show()
        if self._test_mode:
            self._enable_drag()
        self._fade(0.0, 1.0, self.FADE_MS, lambda: self._start_main(gen), gen)
        return True

    def _enable_drag(self):
        """Test mode: click-through off, the window can be dragged by mouse."""
        if self.surface is None or self.surface.top is None:
            return
        self.surface.set_click_through(False)
        top = self.surface.top

        def _press(event):
            self._drag_origin = (event.x_root, event.y_root,
                                 top.winfo_x(), top.winfo_y())

        def _motion(event):
            if not self._drag_origin:
                return
            sx, sy, wx, wy = self._drag_origin
            top.geometry(f"+{wx + event.x_root - sx}+{wy + event.y_root - sy}")

        def _release(_event):
            self._drag_origin = None

        # bind on the window and its canvas/label (whatever LayeredSurface draws with)
        for target in (top,) + tuple(top.winfo_children()):
            try:
                target.bind("<ButtonPress-1>", _press, add="+")
                target.bind("<B1-Motion>", _motion, add="+")
                target.bind("<ButtonRelease-1>", _release, add="+")
                target.configure(cursor="fleur")
            except Exception:
                pass

    def stop(self):
        self._gen += 1
        if self._job is not None and self.surface is not None and self.surface.top:
            try:
                self.surface.top.after_cancel(self._job)
            except Exception:
                pass
        self._job = None
        self._destroy()

    # ---------- window ----------

    def _build_window(self):
        monitor = self.manager.target_monitor()
        total = self.scale * monitor.scale
        self.w = max(48, int(round(self.base_w * total)))
        self.h = max(48, int(round(self.base_h * total)))
        x, y = display.place(monitor, self.w, self.h, self.pos[0], self.pos[1])
        self.surface = LayeredSurface(self.root)
        self.surface.create(x, y, self.w, self.h)
        # On 4K the surfaces are 4x larger than on 1080p; supersampling 3
        # on the breath ring (redrawn 25x per second) would already eat
        # performance, so we lower it on large surfaces.
        self._ss = 2 if (self.w * self.h) > 240000 else 3

    def _destroy(self):
        if self.surface is not None:
            try:
                self.surface.destroy()
            except Exception:
                pass
        self.surface = None

    def _after(self, ms, fn):
        if self.surface is None or self.surface.top is None:
            return
        self._job = self.surface.top.after(ms, fn)

    def _fade(self, start, end, duration_ms, on_done, gen):
        steps = max(1, duration_ms // self.TICK_MS)

        def step(i):
            if gen != self._gen or self.surface is None:
                return
            self.surface.set_alpha(start + (end - start) * (i / steps))
            if i >= steps:
                on_done()
            else:
                self._after(self.TICK_MS, lambda: step(i + 1))

        step(0)

    def _start_main(self, gen):
        if gen != self._gen or self.surface is None:
            return
        self._start_time = time.time()
        self._tick(gen)

    def _tick(self, gen):
        if gen != self._gen or self.surface is None:
            return
        elapsed = time.time() - self._start_time
        try:
            finished = self._step(elapsed)
        except Exception:
            self._destroy()
            return
        if finished:
            self._fade(1.0, 0.0, self.FADE_MS,
                       lambda: self._on_fade_out_done(gen), gen)
            return
        self._after(self.TICK_MS, lambda: self._tick(gen))

    def _on_fade_out_done(self, gen):
        if gen == self._gen:
            self._destroy()

    # ---------- drawing ----------

    def _render(self, elapsed):
        style = self.manager.style
        if self.color:
            style = style.tinted(self.color)
        if self.visual == "breath":
            cycle = self.inhale_s + self.exhale_s
            t_in_cycle = elapsed % cycle
            inhale = t_in_cycle < self.inhale_s
            phase = (t_in_cycle / self.inhale_s if inhale
                     else (t_in_cycle - self.inhale_s) / self.exhale_s)
            image = hud_paint.render_breath(self.w, self.h, style, phase=phase,
                                            inhale=inhale,
                                            cycle_text=self.manager.breath_text(inhale),
                                            ss=self._ss)
        else:
            intro = self.INTRO_S.get(self.visual, 1.0)
            t = min(1.0, elapsed / intro) if intro else 1.0
            image = hud_paint.render_visual(self.visual, self.w, self.h, style,
                                            t=t, label=self._label, ss=self._ss)
        if self._test_mode:
            image = self._decorate_test(image, style)
        self.surface.draw(image)

    # Frame in test mode: dash length / gap / inset from the edge (px)
    TEST_DASH = 8
    TEST_GAP = 5
    TEST_INSET = 2

    def _decorate_test(self, image, style):
        """Adjusts the image for drag mode so it can be GRABBED ANYWHERE.

        Windows lets the mouse through the pixels of a layered window
        that have alpha 0 (the hit-test is per-pixel). A pictogram is
        mostly empty space - live, the window could be grabbed on only
        3-10 % of its area, exactly on the drawn line. Therefore:

          1. every pixel gets an alpha of at least 1 (optically
             invisible, but "solid" for the hit-test), so the whole
             window area holds;
          2. a subtle dashed frame shows where the window's edge is and
             what the player is holding.

        Outside test mode none of this is drawn - in the game the window
        stays exactly as it was (and click-through).
        """
        if image is None or ImageDraw is None:
            return image
        try:
            img = image if image.mode == "RGBA" else image.convert("RGBA")
            alpha = img.getchannel("A").point(lambda v: 1 if v < 1 else v)
            img.putalpha(alpha)
            w, h = img.size
            d = ImageDraw.Draw(img)
            color = tuple(style.accent) + (96,)
            i = self.TEST_INSET
            self._dashed_rect(d, i, i, w - 1 - i, h - 1 - i, color)
            return img
        except Exception:
            return image

    def _dashed_rect(self, d, x0, y0, x1, y1, color):
        dash, gap = self.TEST_DASH, self.TEST_GAP
        for (ax, ay, bx, by) in ((x0, y0, x1, y0), (x0, y1, x1, y1),
                                 (x0, y0, x0, y1), (x1, y0, x1, y1)):
            horizontal = ay == by
            length = (bx - ax) if horizontal else (by - ay)
            pos = 0
            while pos < length:
                end = min(pos + dash, length)
                if horizontal:
                    d.line([(ax + pos, ay), (ax + end, ay)], fill=color, width=1)
                else:
                    d.line([(ax, ay + pos), (ax, ay + end)], fill=color, width=1)
                pos = end + gap

    def _step(self, elapsed):
        if self.visual == "breath":
            # in test mode it breathes round and round (the player is
            # fine-tuning the position), otherwise 2 cycles and the end
            if not self._test_mode and elapsed >= self.CYCLES * (self.inhale_s + self.exhale_s):
                return True
            self._render(elapsed)
            return False

        intro = self.INTRO_S.get(self.visual, 1.0)
        if elapsed <= intro + 0.05:
            self._render(elapsed)
        elif not self._static_done:
            # the animation has finished - we draw the end state once, and
            # from then on the window just hangs on screen without a single
            # redraw
            self._render(intro)
            self._static_done = True
        # in test mode it NEVER ends by itself - it stays until the player
        # turns the test off
        if self._test_mode:
            return False
        return elapsed >= self.HOLD_S


class SomaticOverlayManager:
    """Manager of the 4 independent in-game visuals.

    It holds the shared colour style (by the app's theme), the target
    monitor and the labels - the individual `_SlotOverlay`s take
    everything shared from it, so that a theme/language/monitor change
    does not have to go through four objects.
    """

    VISUALS = ("grounding", "jaw", "release", "breath")

    # Sizes are in 1080p pixels - they are multiplied by Monitor.scale.
    BASE_SIZES = {
        "grounding": (240, 160),
        "jaw": (170, 175),
        "release": (170, 155),
        "breath": (170, 170),
    }

    def __init__(self, root, color="#00d2ff", danger_color="#ff5c73", pal=None):
        self.root = root
        self.style = Style(pal or {"accent": color, "danger": danger_color})
        self.monitor_target = display.TARGET_AUTO
        self._labels = {}
        self._breath_labels = ("", "")
        self._monitor_cache = (0.0, None)
        self._slots = [_SlotOverlay(root, visual, self.BASE_SIZES[visual], self)
                       for visual in self.VISUALS]
        for i, overlay in enumerate(self._slots):
            overlay.pos = OVERLAY_DEFAULT_POS.get(i, (50.0, 50.0))

    # ---------- shared state ----------

    def set_palette(self, pal):
        self.style = Style(pal)

    def set_colors(self, color, danger_color):
        """Kept for backward compatibility with app.py."""
        self.style = Style({"accent": color, "danger": danger_color})

    def set_labels(self, labels, breath_inhale="", breath_exhale=""):
        """`labels` is {index: text} - the label under the visual."""
        self._labels = labels or {}
        self._breath_labels = (breath_inhale, breath_exhale)
        for i, overlay in enumerate(self._slots):
            overlay.set_label(self._labels.get(i))

    def breath_text(self, inhale):
        return self._breath_labels[0] if inhale else self._breath_labels[1]

    def set_breath_seconds(self, inhale_s, exhale_s):
        """Inhale/exhale length (in seconds) for the breath ring - the player
        changes it in Settings (see app.py on_breath_seconds_change)."""
        for overlay in self._slots:
            if overlay.visual == "breath":
                overlay.set_breath_seconds(inhale_s, exhale_s)

    def set_monitor_target(self, target):
        self.monitor_target = target or display.TARGET_AUTO
        self._monitor_cache = (0.0, None)

    def target_monitor(self):
        """Target monitor with a short cache.

        Enumerating monitors is cheap but not free, and when a visual is
        triggered it is on the GUI thread. A one-second cache is enough -
        monitors do not get rewired within one second.
        """
        now = time.time()
        if self._monitor_cache[1] is not None and now - self._monitor_cache[0] < 1.0:
            return self._monitor_cache[1]
        monitor = display.resolve_target(self.monitor_target, self.root)
        self._monitor_cache = (now, monitor)
        return monitor

    # ---------- slot control ----------

    def configure(self, index, enabled=None, scale=None, pos=None, color=None):
        if 0 <= index < len(self._slots):
            self._slots[index].configure(enabled=enabled, scale=scale, pos=pos,
                                         color=color)

    def trigger(self, index):
        """Returns True if the slot's visual really started drawing (see
        `_SlotOverlay.trigger`). Invalid index = nothing was drawn."""
        if 0 <= index < len(self._slots):
            return bool(self._slots[index].trigger())
        return False

    def is_active(self, index):
        if 0 <= index < len(self._slots):
            return self._slots[index].is_active
        return False

    def test(self, index):
        """Toggles the slot's drag-test mode. Returns True if it is on AFTER
        the call (the visual is on screen and can be dragged), False if
        it was just turned off."""
        if 0 <= index < len(self._slots):
            # if another slot's test is running, turn it off first - two
            # persistent test visuals at once would overlap and clash
            for i, ov in enumerate(self._slots):
                if i != index and ov._test_mode:
                    ov.stop_test()
            self._slots[index].test()
            return self._slots[index]._test_mode
        return False

    def stop_test(self, index):
        if 0 <= index < len(self._slots):
            self._slots[index].stop_test()

    def is_testing(self, index):
        if 0 <= index < len(self._slots):
            return self._slots[index]._test_mode
        return False

    def set_test_moved_callback(self, index, callback):
        """Sets callback(px, py), which is called when the test ends with the
        visual's new position (in monitor percentages) - the app saves
        it."""
        if 0 <= index < len(self._slots):
            self._slots[index].on_test_moved = callback

    def stop_all(self):
        for overlay in self._slots:
            overlay.stop_test()
            overlay.stop()

    def stop_all_tests(self):
        """Ends ALL drag tests and restores click-through.

        WHY THIS HAS ITS OWN METHOD: test mode turns click-through off
        (`_enable_drag` -> `set_click_through(False)`), so the visual over
        the game swallows mouse clicks - and it never ends on its own
        (`_step` in test mode returns False forever). Whoever clicked Test
        and forgot had an unclickable area in the middle of the screen
        and no way to find out why.

        Returns the number of tests ended, so that the caller knows
        whether to tell the player about it.
        """
        ukoncene = 0
        for overlay in self._slots:
            if overlay._test_mode:
                overlay.stop_test()
                ukoncene += 1
        return ukoncene
