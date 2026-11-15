"""Live in-game HUD panel - heart rate, load and session progress.

What it is
----------
One small click-through window in a corner of the screen that shows:

  * the current heart rate as a big number + a heart that beats in the
    REAL rhythm (so peripheral vision gets the information even without
    reading the number),
  * the heart-rate curve for the last ~3 minutes with the critical limit
    and the player's own resting baseline marked,
  * the "Záťaž" (Load) bar (0-100) - a composite from hr_stats.py, not a
    made-up "stress",
  * the session row: length, number of cues fired, time above the limit.

Why its own window and not part of the slot visuals
---------------------------------------------------
Slot visuals are EVENTS (you pressed a key -> something shows for 3 s).
The HUD is a STATE - it stays there the whole time. Mixing both into one
window would mean that the HUD goes dark every time a slot animation ends.

Performance
-----------
It redraws 8x per second and only when it is really visible. One frame is
~250x105 logical pixels (double on 4K), which is an order of magnitude
smaller than the breathing circle - in a game it is not measurable.

Anti-cheat: the same applies as for overlay.py - no injection, no reading
of the game, the window is click-through and not in Alt+Tab. See
layer_window.py.
"""

import time

import display
import hud_paint
from layer_window import LayeredSurface

REFRESH_MS = 125           # 8 fps - enough for the heart to look alive
REPOSITION_EVERY_S = 2.0   # how often we check whether the monitor changed

# Default position: bottom-left corner, above the usual chat/killfeed spot.
DEFAULT_POS = (13.0, 90.0)

class StatsHud:
    """HUD panel with heart-rate statistics.

    The owner (DandurfApp) only sets its configuration and tells it where
    to take data from (`stats`); it takes care of the window, redrawing and
    moving between monitors itself.
    """

    def __init__(self, root, stats, style, monitor_target=display.TARGET_AUTO):
        self.root = root
        self.stats = stats
        self.style = style
        self.monitor_target = monitor_target

        self.enabled = False
        self.scale = 1.0
        self.pos = DEFAULT_POS
        self.opacity = 0.92
        self.critical_bpm = 110
        self.labels = {}
        self.connected = False
        self.session_text = ""

        self.surface = None
        self._job = None
        self._geometry = None          # (monitor_key, w, h, x, y)
        self._last_reposition = 0.0
        self._ss = 3

        # A row of 4 function icons under the HUD panel (replaces the original
        # app-wide "Minimalisticky rezim" (Minimalist mode) - now it is part of
        # this same panel, which already had BPM/load in game). Off by default,
        # so the panel does not change for anyone who already uses the HUD.
        self.show_triggers = False
        self.trigger_icon_color = None   # None = theme colour (like the HUD)
        self._triggers = []              # [(visual_name, enabled)]
        self._on_trigger_click = None    # callback(index)

    # ---------- configuration ----------

    def configure(self, enabled=None, scale=None, pos=None, opacity=None,
                  critical_bpm=None, monitor_target=None):
        rebuild = False
        if enabled is not None:
            self.enabled = bool(enabled)
        if scale is not None:
            new = max(0.6, min(2.0, float(scale)))
            rebuild = rebuild or new != self.scale
            self.scale = new
        if pos is not None:
            rebuild = rebuild or tuple(pos) != tuple(self.pos)
            self.pos = (float(pos[0]), float(pos[1]))
        if opacity is not None:
            self.opacity = max(0.25, min(1.0, float(opacity)))
            if self.surface is not None:
                self.surface.set_alpha(self.opacity)
        if critical_bpm is not None:
            self.critical_bpm = int(critical_bpm)
        if monitor_target is not None:
            rebuild = rebuild or monitor_target != self.monitor_target
            self.monitor_target = monitor_target

        if not self.enabled:
            self.stop()
            return
        if rebuild:
            self._teardown_window()
        self.start()

    def set_style(self, style):
        self.style = style

    def set_labels(self, labels):
        self.labels = labels or {}

    def set_connected(self, connected):
        self.connected = bool(connected)

    def set_session_text(self, text):
        self.session_text = text or ""

    def configure_triggers(self, show=None, icon_color=None, triggers=None,
                           on_click=None):
        """Row of 4 function icons under the HUD panel ("Show the panel in game"
        in Settings -> In game -> Visuals). Replaces the original app-wide
        "Minimalisticky rezim" (Minimalist mode) - the same display (BPM + 4
        functions), but now it is one part of the in-game HUD panel, not a
        switch of the whole app.

        `triggers`: [(visual_name, enabled), ...] max 4 items.
        `on_click(index)`: called on a click on the i-th icon (by clicking
        the small icon the player fires the same cue as with the key).
        """
        rebuild = False
        if show is not None:
            new_show = bool(show)
            rebuild = rebuild or new_show != self.show_triggers
            self.show_triggers = new_show
        if icon_color is not None:
            self.trigger_icon_color = icon_color or None
        if triggers is not None:
            self._triggers = list(triggers)[:4]
        if on_click is not None:
            self._on_trigger_click = on_click
        if rebuild and self.surface is not None:
            self._teardown_window()

    # ---------- lifecycle ----------

    def start(self):
        if not self.enabled or self._job is not None:
            return
        self._tick()

    def stop(self):
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        self._teardown_window()

    def _teardown_window(self):
        if self.surface is not None:
            try:
                self.surface.destroy()
            except Exception:
                pass
        self.surface = None
        self._geometry = None

    # ---------- drawing ----------

    def _ensure_window(self):
        monitor = display.resolve_target(self.monitor_target, self.root)
        total = self.scale * monitor.scale
        w = max(140, int(round(hud_paint.HUD_WIDTH * total)))
        base_h = hud_paint.HUD_HEIGHT
        if self.show_triggers and self._triggers:
            base_h += 4 + hud_paint.TRIGGER_ROW_HEIGHT
        h = max(60, int(round(base_h * total)))
        x, y = display.place(monitor, w, h, self.pos[0], self.pos[1])
        key = (monitor.x, monitor.y, monitor.width, monitor.height, w, h, x, y)
        if self.surface is not None and self._geometry == key:
            return True
        if self.surface is not None and self._geometry is not None:
            # only the monitor/position changed - moving the window is enough
            if self._geometry[4:6] == (w, h):
                self.surface.move(x, y)
                self._geometry = key
                return True
            self._teardown_window()
        self.surface = LayeredSurface(self.root)
        self.surface.create(x, y, w, h)
        self.surface.set_alpha(self.opacity)
        self._geometry = key
        self._ss = 2 if (w * h) > 90000 else 3
        return True

    def _tick(self):
        self._job = None
        if not self.enabled:
            return
        try:
            self._draw()
        except Exception:
            pass
        try:
            self._job = self.root.after(REFRESH_MS, self._tick)
        except Exception:
            self._job = None

    def _draw(self):
        now = time.time()
        if now - self._last_reposition > REPOSITION_EVERY_S or self.surface is None:
            self._last_reposition = now
            self._ensure_window()
        if self.surface is None:
            return

        stats = self.stats
        # Right after the heart rate returns (`HeartStats.is_settling`) the
        # load ramps up from zero - it takes the same path as calibration
        # (empty bar, neutral colour), only instead of "kalibrujem"
        # (calibrating) there is a quiet "…".
        labels = self.labels
        settling = self.connected and stats.is_settling
        if settling:
            labels = dict(labels, calibrating="…")
        # The zone is computed ONCE, in `HeartStats.zone` (heart rate vs
        # rest) - the same word is shown by Today and the heart-rate indicator.
        # `render_hud` only draws it; calibration, settling and disconnection
        # take precedence.
        # The number is `display_bpm` (median of a few seconds), not the last
        # raw sample - two heart-rate series in one source would otherwise make
        # it jump. The curve, load and zone stay on raw samples.
        image = hud_paint.render_hud(
            self.style,
            bpm=stats.display_bpm if self.connected else None,
            stress=stats.stress,
            zone=stats.zone,
            history=stats.series(90),
            threshold=self.critical_bpm,
            baseline=stats.baseline,
            labels=labels,
            pulse=stats.beat_phase(now) if self.connected else 0.0,
            session=self.session_text,
            connected=self.connected,
            calibrating=self.connected and (stats.is_calibrating or settling),
            ss=self._ss)
        if self.show_triggers and self._triggers:
            row = hud_paint.render_hud_trigger_row(
                hud_paint.HUD_WIDTH, self.style, self._triggers,
                icon_color=self.trigger_icon_color)
            image = hud_paint.render_hud_combined(image, row)
        self.surface.draw(image)
        self.surface.show()

    def handle_click(self, rel_x, rel_y):
        """Maps a clicked point (0..1 in the window) to an icon index in the
        trigger row - USABLE ONLY in the preview inside the app (e.g. the
        "Test" button in Settings), NOT in a real game.

        Quite deliberately: the in-game HUD panel ALWAYS stays
        click-through (WS_EX_TRANSPARENT) - that is the app's basic
        safety/anti-cheat principle (see the layer_window.py header).
        Turning off click-through just for clickable icons would mean the
        app permanently steals clicks from the game, which is exactly the
        risk to avoid. In game the icons are therefore a PURELY VISUAL
        reminder of the function (a pictogram), not a button.
        """
        if not self.show_triggers or not self._triggers:
            return None
        total_h = hud_paint.HUD_HEIGHT + 4 + hud_paint.TRIGGER_ROW_HEIGHT
        row_top = (hud_paint.HUD_HEIGHT + 4) / total_h
        if rel_y < row_top:
            return None
        n = len(self._triggers)
        index = min(n - 1, max(0, int(rel_x * n)))
        if callable(self._on_trigger_click):
            self._on_trigger_click(index)
        return index
