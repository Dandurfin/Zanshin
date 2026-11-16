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

4. AN EXHALE WITH EVERY CUE. A long exhale is the one thing that fits any
   moment, so no cue comes without it. A grounding / jaw / release visual
   brings the breath ring along in an exhale-only mode (one exhale, the
   ring goes from full to empty), and the breath cue on its own starts
   with the exhale and ends breathed out (exhale -> inhale -> exhale).
   See `SomaticOverlayManager.trigger` and `_SlotOverlay.breath_phases`.

5. THE RING AT HIGH HEART RATE (experiment, off by default). While the
   player's heart rate is above a limit, slot 3's ring breathes in a loop
   (BREATH_LOOP) and ends breathed out once it drops. The app decides when
   (`app_session._tick_high_hr_ring`); here are only the loop and
   `SomaticOverlayManager.start_high_hr_ring` & co.

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

    # breathing - default 4 s inhale / 6 s exhale, the player can change
    # them in Settings (see SomaticOverlayManager.set_breath_seconds)
    INHALE_S_DEFAULT = 4.0
    EXHALE_S_DEFAULT = 6.0

    # What one showing of the breath ring breathes (`breath_phases`):
    #   BREATH_FULL   - the breath cue on its own: exhale -> inhale ->
    #                   exhale. It STARTS with the exhale (it fits any
    #                   moment, the middle of a fight too) and ends
    #                   breathed out, so the ring never leaves the player
    #                   holding a full breath. Until 0.3 it was 2 cycles of
    #                   inhale -> exhale.
    #   BREATH_EXHALE - the companion of grounding / jaw / release
    #                   (`trigger_exhale`): one exhale, full -> empty.
    #   BREATH_LOOP   - the ring at high heart rate (experiment, off by
    #                   default, `start_loop`): exhale -> inhale -> exhale
    #                   ... with no end of its own. `finish_loop` lets it end
    #                   breathed out - it finishes the running exhale, or the
    #                   running inhale and one more exhale - then the usual
    #                   fade-out.
    # Drag-test mode ignores all three and loops exhale -> inhale until the
    # player ends the test.
    BREATH_FULL = "full"
    BREATH_EXHALE = "exhale"
    BREATH_LOOP = "loop"

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
        # set by trigger() / trigger_exhale() / test() / start_loop() before
        # each play()
        self._breath_mode = self.BREATH_FULL
        # BREATH_LOOP: where the loop is - the phase now breathed (inhale or
        # not) and the elapsed second it started at. A cursor instead of
        # `elapsed % cycle`, so that changing the inhale/exhale length while
        # the ring breathes does not make it jump to another phase.
        self._loop_inhale = False
        self._loop_phase_start = 0.0
        self._loop_finishing = False    # finish_loop(): end after an exhale
        self._loop_done = False         # breathed out, the fade-out is running
        # BREATH_LOOP has no end of its own, so a new size / position /
        # target monitor cannot wait for the next showing as with a cue's
        # ring: `follow_placement` asks for it, the next frame applies it
        # (`_apply_pending_placement`).
        self._relayout_pending = False

        self.surface = None
        self.w = self.h = 0
        self._xy = None                 # where the window was placed (x, y)
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
            # The ring at high heart rate has its own switch (Settings) and
            # draws regardless of this slot's own one - turning off the
            # breath cue's picture does not cut it off.
            if not self.enabled and not self.in_loop:
                self.stop()
        if scale is not None:
            self.scale = max(0.5, min(2.0, float(scale)))
        if pos is not None:
            self.pos = pos
        if scale is not None or pos is not None:
            self.follow_placement()
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

        The breath ring breathes its full showing here (BREATH_FULL).
        """
        if self.enabled:
            self._breath_mode = self.BREATH_FULL
            return self.play()
        return False

    def trigger_exhale(self):
        """The companion exhale: the breath ring in BREATH_EXHALE mode, shown
        next to a grounding / jaw / release visual
        (`SomaticOverlayManager.trigger`). One exhale of the player's
        exhale length, the ring going from full to empty, then the usual
        fade-out.

        Returns True if it really started drawing. Nothing is drawn (False)
        when this is not the breath ring, when the breath visual is
        disabled (the player's choice, respected exactly like for the
        breath cue), or when the ring is in drag-test mode - the player is
        placing it right now, and a cue must not turn the test into a short
        exhale that disappears from under the mouse. A ring that is already
        showing (the breath cue, or the previous companion) is restarted
        (`play() -> stop()`) - except the ring at high heart rate
        (`loop_breathing`): it is already breathing, so it just goes on.
        """
        if self.visual != "breath" or not self.enabled or self._test_mode:
            return False
        if self.loop_breathing:
            return False
        self._breath_mode = self.BREATH_EXHALE
        return self.play()

    # ---------- the ring at high heart rate (BREATH_LOOP) ----------

    def start_loop(self):
        """Starts the ring at high heart rate: exhale -> inhale -> exhale ...
        with no end of its own (`finish_loop` / `stop` end it).

        Returns True if it really started drawing. It draws regardless of
        `enabled` - the feature has its own switch - but never on another
        visual than the breath ring and never in drag-test mode."""
        if self.visual != "breath" or self._test_mode:
            return False
        self._breath_mode = self.BREATH_LOOP
        self._loop_inhale = False
        self._loop_phase_start = 0.0
        self._loop_finishing = False
        self._loop_done = False
        self._relayout_pending = False
        return self.play()

    @property
    def in_loop(self):
        """The ring at high heart rate is on screen (its final fade-out
        included)."""
        return (self._breath_mode == self.BREATH_LOOP and self.surface is not None
                and not self._test_mode)

    @property
    def loop_breathing(self):
        """The ring at high heart rate still breathes - looping, or finishing
        its last exhale. False once it is breathed out and fading."""
        return self.in_loop and not self._loop_done

    @property
    def loop_finishing(self):
        return self.loop_breathing and self._loop_finishing

    def finish_loop(self):
        """Lets the loop end breathed out: a running exhale is finished, a
        running inhale is finished and followed by one more exhale; then the
        usual fade-out. Returns True if the loop was breathing."""
        if not self.loop_breathing:
            return False
        self._loop_finishing = True
        return True

    def keep_looping(self):
        """Cancels `finish_loop` - the ring keeps breathing as it is, with no
        fade and no restart. Returns True if the loop was breathing."""
        if not self.loop_breathing:
            return False
        self._loop_finishing = False
        return True

    def _loop_advance(self, elapsed):
        """Moves the loop's cursor forward to `elapsed` (never back).

        Returns True when the finish was asked for and an exhale has just
        been completed - the ring is breathed out and the loop ends. The
        length of each phase is read when the phase is checked, so a new
        inhale/exhale length applies from the running phase on."""
        while True:
            seconds = self.inhale_s if self._loop_inhale else self.exhale_s
            seconds = max(0.5, float(seconds))
            if elapsed - self._loop_phase_start < seconds:
                return False
            if not self._loop_inhale and self._loop_finishing:
                return True
            self._loop_phase_start += seconds
            self._loop_inhale = not self._loop_inhale

    def follow_placement(self):
        """The slot's size, position or target monitor changed. A running
        loop takes it over with its next frame (`_apply_pending_placement`)
        - it has no end of its own, so waiting for the next showing (as a
        cue's ring does) could mean waiting for as long as the heart rate
        stays high. Anything else that is on screen keeps its placement
        until it ends, as before."""
        if self.in_loop:
            self._relayout_pending = True

    def _apply_pending_placement(self):
        """BREATH_LOOP: brings the window to the placement asked for by
        `follow_placement`. The same size only moves the window; another
        size needs a new one (the image buffer has the window's size), and
        the animation goes on in it as it was - its start, the loop's
        cursor, the finish asked for - with no fade-in and no restart.

        Returns True when a new window was built: the caller draws this
        frame into it and then shows it. A failure is logged and raised -
        `_tick` then closes what is left, so no half-built window stays
        (it would count as a running visual and hold back every cue)."""
        if not self._relayout_pending:
            return False
        self._relayout_pending = False
        x, y, w, h = self._placement()
        if (w, h) == (self.w, self.h):
            if (x, y) != self._xy:
                self.surface.move(x, y)
                self._xy = (x, y)
            return False
        self._destroy()
        try:
            self._build_window()
        except Exception:
            log.exception("kruh pri vysokom tepe: okno v novej velkosti sa nepodarilo postavit")
            raise
        return True

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
        position. The breath ring loops exhale -> inhale for as long as the
        test runs (`breath_state`). A ring at high heart rate on screen is
        replaced: the mode goes back to BREATH_FULL, so the loop is not
        "showing" any more (`in_loop`) and the app closes its showing.
        """
        if self._test_mode:
            self.stop_test()
            return
        self._test_mode = True
        self._breath_mode = self.BREATH_FULL
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

    def _placement(self):
        """(x, y, w, h) of the window on the target monitor right now - the
        slot's size and its position in % of the monitor."""
        monitor = self.manager.target_monitor()
        total = self.scale * monitor.scale
        w = max(48, int(round(self.base_w * total)))
        h = max(48, int(round(self.base_h * total)))
        x, y = display.place(monitor, w, h, self.pos[0], self.pos[1])
        return x, y, w, h

    def _build_window(self):
        x, y, self.w, self.h = self._placement()
        self._xy = (x, y)
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

    # ---------- breathing ----------

    def breath_phases(self):
        """The phases of one showing of the breath ring, in order, as
        ((inhale, seconds), ...) - see BREATH_FULL / BREATH_EXHALE.

        Every showing starts with the exhale and ends breathed out. Drag-test
        mode does not use this (it loops, see `breath_state`). BREATH_LOOP
        gives the one cycle it repeats (exhale, inhale) - it has no end of
        its own, `breath_state` follows its cursor."""
        if self._breath_mode == self.BREATH_EXHALE:
            return ((False, self.exhale_s),)
        if self._breath_mode == self.BREATH_LOOP:
            return ((False, self.exhale_s), (True, self.inhale_s))
        return ((False, self.exhale_s), (True, self.inhale_s),
                (False, self.exhale_s))

    def breath_duration(self):
        """Seconds the ring breathes in one showing (without the fades)."""
        return sum(seconds for _inhale, seconds in self.breath_phases())

    def breath_state(self, elapsed):
        """(inhale, phase) of the ring `elapsed` seconds after the fade-in.

        `phase` is 0..1 within the current inhale or exhale - exactly what
        `hud_paint.render_breath` takes (an exhale at 0 is the full ring, at
        1 the empty one). After the end of the showing it stays at the end
        of the last phase, i.e. breathed out. Drag-test mode loops exhale ->
        inhale without an end.

        BREATH_LOOP moves its cursor forward to `elapsed` (`_loop_advance`),
        so it is asked with a growing `elapsed`, as the animation does. Once
        the asked-for finish is breathed out, it stays at the empty ring."""
        if self._test_mode:
            t = elapsed % (self.exhale_s + self.inhale_s)
            if t < self.exhale_s:
                return False, t / self.exhale_s
            return True, (t - self.exhale_s) / self.inhale_s
        if self._breath_mode == self.BREATH_LOOP:
            if self._loop_done or self._loop_advance(float(elapsed)):
                return False, 1.0
            seconds = max(0.5, float(self.inhale_s if self._loop_inhale
                                     else self.exhale_s))
            phase = (float(elapsed) - self._loop_phase_start) / seconds
            return self._loop_inhale, max(0.0, min(1.0, phase))
        t = max(0.0, float(elapsed))
        phases = self.breath_phases()
        for inhale, seconds in phases:
            if t < seconds:
                return inhale, t / seconds
            t -= seconds
        return phases[-1][0], 1.0

    # ---------- drawing ----------

    def _render(self, elapsed):
        style = self.manager.style
        if self.color:
            style = style.tinted(self.color)
        if self.visual == "breath":
            inhale, phase = self.breath_state(elapsed)
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
        if self.visual == "breath" and self.in_loop:
            # the ring at high heart rate: round and round until the finish
            # is asked for; the frame that ends it is the empty ring
            # (`breath_state`), and that frame fades out. A new size,
            # position or monitor applies here, between two frames.
            rebuilt = self._apply_pending_placement()
            done = self._loop_advance(elapsed)
            self._render(elapsed)
            if rebuilt:
                self.surface.set_alpha(1.0)
                self.surface.show()
            if done:
                self._loop_done = True
            return done
        if self.visual == "breath":
            # in test mode it breathes round and round (the player is
            # fine-tuning the position), otherwise the phases of this
            # showing (`breath_phases`) and the end - the last frame is
            # drawn exactly breathed out (the empty ring), not one tick
            # before it, and that frame fades out
            if not self._test_mode:
                duration = self.breath_duration()
                if elapsed >= duration:
                    self._render(duration)
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
    # the slot whose ring also comes as the companion exhale of the others
    BREATH_INDEX = VISUALS.index("breath")

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
        # the ring at high heart rate has no end of its own - it moves to
        # the new monitor now, not when the heart rate drops
        self._slots[self.BREATH_INDEX].follow_placement()

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
        """Shows the slot's visual. Returns True if THE SLOT'S OWN visual
        really started drawing (see `_SlotOverlay.trigger`). Invalid index =
        nothing was drawn.

        EVERY CUE COMES WITH AN EXHALE. With a grounding / jaw / release
        visual the breath ring (slot 3's visual, at slot 3's own position,
        size and colour) is shown at the same time in the exhale-only mode
        (`_SlotOverlay.trigger_exhale`). The cue says what, the ring says
        how: one long exhale.

        The companion never changes the return value. The measurement asks
        whether the CATEGORY's visual was delivered (bug B17): a ring that
        is disabled or failed does not make a drawn grounding visual
        undelivered, and a drawn ring does not make a failed one delivered.
        No companion when the category visual was not drawn (no cue, no
        exhale), when that slot is in drag-test mode, or when the breath
        visual is disabled or in its own drag test (`trigger_exhale`).
        trigger(3) is the breath cue itself (exhale -> inhale -> exhale),
        with no second ring.
        """
        if not (0 <= index < len(self._slots)):
            return False
        overlay = self._slots[index]
        shown = bool(overlay.trigger())
        if shown and index != self.BREATH_INDEX and not overlay._test_mode:
            self._show_companion_exhale()
        return shown

    def _show_companion_exhale(self):
        """The exhale-only breath ring next to a category visual.

        Any failure stays here (logged): it must not reach the caller - the
        in-game cue (`_fire_somatic_cue`) does not catch exceptions around
        `trigger`, and the category visual is already on screen.

        A failure also must not leave a half-built ring behind. `play()`
        cleans up only after a failed build or first frame; an exception
        later (showing it, the fade's first `.after()`) would leave the
        window open with no animation to close it, and an open window counts
        as a running visual for good (`is_active`) - `_cue_can_fire` would
        then hold back every later cue of the session without a word. So the
        ring is stopped here - unless the player is placing it right now
        (drag test): then no companion was started at all and the test's
        window must stay."""
        ring = self._slots[self.BREATH_INDEX]
        try:
            ring.trigger_exhale()
        except Exception:
            log.exception("sprievodny vydych (dychovy kruh) sa nepodarilo ukazat")
            if not ring._test_mode:
                try:
                    ring.stop()
                except Exception:
                    log.exception("sprievodny vydych sa nepodarilo ani zastavit")

    # ---------- the ring at high heart rate (experiment) ----------
    #
    # Slot 3's own ring (its position, size, colour and inhale/exhale
    # lengths) breathing in a loop while the player's heart rate is above
    # a limit - the app decides when (`app_session._tick_high_hr_ring`).
    # It is slot 3's window, so while it is on screen `is_active(3)` is True
    # and `_cue_can_fire` holds every other cue back.

    def start_high_hr_ring(self):
        """Starts the loop, or keeps a breathing one going (a finish asked
        for is cancelled - no fade, no restart, no flicker). Returns True if
        the ring is breathing in the loop after the call.

        Never while ANY slot is in drag-test mode: the player is placing a
        picture. A failure must not leave a half-built ring behind - an open
        window counts as a running visual for good (`is_active`) and
        `_cue_can_fire` would then hold back every cue of the session
        (the same lesson as `_show_companion_exhale`). So it is stopped and
        logged here, and nothing reaches the caller."""
        if any(ov._test_mode for ov in self._slots):
            return False
        ring = self._slots[self.BREATH_INDEX]
        if ring.loop_breathing:
            return ring.keep_looping()
        try:
            if ring.start_loop():
                return True
        except Exception:
            log.exception("kruh pri vysokom tepe sa nepodarilo ukazat")
        try:
            ring.stop()
        except Exception:
            log.exception("kruh pri vysokom tepe sa nepodarilo ani zastavit")
        return False

    def finish_high_hr_ring(self):
        """Lets the loop end breathed out, then fade (`finish_loop`).
        Returns True if the loop was breathing."""
        return self._slots[self.BREATH_INDEX].finish_loop()

    def stop_high_hr_ring(self):
        """Ends the loop at once (snooze, listening off, session closed).
        Only the loop - another showing of the ring (a cue, the drag test)
        is left alone. Returns True if a loop ring was on screen."""
        ring = self._slots[self.BREATH_INDEX]
        if not ring.in_loop:
            return False
        ring.stop()
        return True

    def high_hr_ring_showing(self):
        """The loop is breathing (looping, or finishing its last exhale)."""
        return self._slots[self.BREATH_INDEX].loop_breathing

    def high_hr_ring_finishing(self):
        """The loop was asked to finish and is still breathing towards its
        end (the running inhale, then the last exhale)."""
        return self._slots[self.BREATH_INDEX].loop_finishing

    def is_active(self, index):
        if 0 <= index < len(self._slots):
            return self._slots[index].is_active
        return False

    def test(self, index):
        """Toggles the slot's drag-test mode. Returns True if it is on AFTER
        the call (the visual is on screen and can be dragged), False if
        it was just turned off. It shows ONLY that slot's visual - no
        companion exhale: the player is placing one picture."""
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
        # the companion exhale and the ring at high heart rate are slot 3's
        # own ring, so this stops them too
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
