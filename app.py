"""Main app (DandurfApp) - main window, sfx/TTS pipeline wiring,
profiles, tray icon.

This is the app's composition root: it creates and wires up
AudioDispatcher/SpeechWorker (audio_engine.py), GamepadListener
(gamepad.py), GameProcessWatcher (game_profiles.py),
SomaticOverlayManager (overlay.py) and all dialogs/tabs (ui_dialogs.py).

Some DandurfApp methods live in the app_*.py mixins (e.g.
app_data.DataMixin), which DandurfApp inherits. The mixins carry only
methods - all the state stays here.

SINCE VERSION 2.1 THERE IS NO KEYBOARD HOOK HERE. A cue is not triggered
by a key press but by the body: `trigger.CueTrigger` watches the load from
the smartwatch, and `activity.py` uses `GetLastInputInfo` to find out
whether the player is active - it returns only the number of milliseconds
since the last input, not what was pressed. The delivery decision stays in
DandurfApp (mixin app_today.TodayMixin), because it is tightly coupled to
the UI (ui_call/log_threadsafe) and to the overlay layer.
"""

import os
import threading
import time
import tkinter as tk

import customtkinter as ctk

# IMPORTANT ordering: `gamepad` MUST be imported before `audio_engine`
# (on import, gamepad sets SDL_AUDIODRIVER=dummy for the windowless
# joystick; audio_engine removes this env var on its own import right before
# pygame.mixer.init() - if the order were reversed, the mixer would stay
# mute).
import gamepad
import activity
import audio_engine
import sfx_assets
import hr_insights
import hr_stats
import rebrik
import trigger
import netinfo
from heart_rate import HeartRateMonitor
from hud import StatsHud
import theme as theme_mod
import ui_kit
from audio_engine import AudioDispatcher, EdgeTTSCache, SpeechWorker
from game_profiles import PSUTIL_AVAILABLE
from guide_panel import GuidePanel, build_guide_into
from guided_tour import GuidedTour
from i18n import LANG_EN, tr
from overlay import SomaticOverlayManager
from paths import APP_NAME, AUDIO_DIR, DATA_DIR, TTS_CACHE_DIR

# The licence as shown in the title bar. It is NOT a translatable string:
# "GPLv3" is the name of the licence, just as "Zanshin" is the name of the
# app - translating it would mean claiming it is a different licence.
LICENCIA = "GPLv3"
from settings_model import (DEFAULT_AUDIO,
                            DASHBOARD_MAX_CARDS,
                            DEFAULT_COOLDOWN,
                            ENGINE_EDGE,
                            ENGINE_SAPI,
                            engine_labels)
from ui_dialogs import (watch_app_qr,
                        DevLayerDialog,
                        OnboardingWizard)
import ui_shell
from ui_shell import (PageContainer, Sidebar,
                      TitleBar, enable_frameless)
from collections import deque

import hotkey
import hud_paint

# The DandurfApp mixins (app_*.py) are imported only here, after all the
# modules above: what they need is already loaded, so they do not change
# the import order (gamepad before audio_engine). The exceptions are
# `background`, `data_io` and `theme_recolor` - app.py itself no longer uses
# them and they are loaded only by the mixin (on import `background` only
# loads PIL, `data_io` and `theme_recolor` only define constants and
# functions). Names shared by app.py and the mixins (app_log, language
# names, the "Not now" shortcut, ImageTk) are in app_spolocne.py - a mixin
# must not import app (circular import).
from app_spolocne import (LANG_NATIVE_LABELS, SNOOZE_HOTKEY_MINUTES,
                          _ImageTk, app_log, stranka_vhre)
# app.py itself does not use these two names: DEFAULT_SNOOZE_HOTKEY is read
# by `load_settings` in app_prefs, LABEL_TO_LANG by the language switches in
# app_prefs and app_hud. They are imported so that `app.DEFAULT_SNOOZE_HOTKEY`
# and `app.LABEL_TO_LANG` (app.py constants up to 0.2.1) stay valid.
from app_spolocne import DEFAULT_SNOOZE_HOTKEY, LABEL_TO_LANG  # noqa: F401
from app_data import DataMixin
from app_prefs import PrefsMixin
from app_controls import ControlsMixin
from app_audio import AudioMixin
from app_hud import HudMixin
from app_today import TodayMixin
from app_profiles import ProfilesMixin
from app_session import SessionMixin
from app_cues import CuesMixin
from app_history import HistoryMixin

try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

try:
    import pystray
    TRAY_AVAILABLE = PIL_AVAILABLE
except Exception:
    TRAY_AVAILABLE = False


class DandurfApp(DataMixin, PrefsMixin, ControlsMixin, AudioMixin, HudMixin,
                 TodayMixin, ProfilesMixin, SessionMixin, CuesMixin,
                 HistoryMixin):
    # FALLBACK slot when none is enabled. 3 = breathing circle.
    #
    # Until 18. 9. this was the ONLY slot the automatic cue used.
    # That was the right decision for measurement (all windows from one
    # category) and the wrong one for the app: the same sentence a hundred
    # times an evening stops working. Now the categories rotate round-robin
    # (`measure.next_slot`) and the category is written into every window, so
    # phase 8 is collecting data from today on.
    #
    # Choosing the category by what WORKS for whom is still phase 8 - that
    # needs data. The rotation is even, not personalised.
    CUE_SLOT_INDEX = 3

    # Since phase 2 the key slots trigger nothing, and phase 3 deleted their
    # code (the pynput hooks). Nothing reads this switch any more - not the
    # developer overlay either; it stays only as a marker.
    KEY_SLOTS_ENABLED = False

    # Busy TCP port: how many times and after how long the bind is retried.
    # (A busy UDP port is not retried - TCP keeps running, see "udp_busy".)
    # Three attempts 8 s apart bridge the usual cause - a second instance of
    # the app that is just closing. Anything longer is no longer temporary.
    HR_BIND_RETRIES = 3
    HR_BIND_RETRY_MS = 8000

    # MOVEMENT: from how many steps per minute the app stays silent.
    #
    # WHY AT ALL: heart rate from movement CANNOT be told apart. Uendes et al.
    # (2026, JMIR, N=127) showed that a model with 55 ECG features has a
    # specificity of 0.418 at moderate physical activity - it flags almost six
    # out of ten walking windows as stress. One BPM every ~1 to 3 s (the
    # watch's cadence, see `trigger.MAX_KROK_S`) manages that even less. So
    # the step gate is not caution, it is the only way.
    #
    # WHY NOT 100 (the established moderate-intensity threshold, 3 METs):
    # slow walking around the flat is 60-90 steps/min and raises heart rate by
    # 10-20 bpm - exactly our artefact, which a threshold of 100 would let
    # through.
    #
    # WHY NOT ZERO: the literature assumes a chest strap. A step counter on
    # the WRIST counts hand movement, and playing is all hand movement, so
    # zero would probably throw everything away.
    #
    # 15 is a PROVISIONAL number from the author, not measured. The
    # first 10 step messages of each session are written to the journal
    # (`_metrics_log_left`) precisely so it can be replaced with a value from
    # our own data.
    KROKY_PRAH_ZA_MIN = 15.0

    # Which world the critical heart rate and the load threshold are computed
    # from. The author's decision (B3-worlds): ONLY from play - both are
    # defined as percentiles of PLAYING (`hr_stats.dynamicky_kriticky`,
    # `dynamicky_prah_zataze`). On test data a single work session in the
    # shared pool pulled play time above the threshold from ~23 % to ~9 %
    # (the target is ~20 %). The resting baseline still comes from everything:
    # there is only one body.
    ALGORITMUS_SVET = "play"

    # The side menu has 4 main items + the enso (Today, History, In-game,
    # Settings); since the "Sumi noc" redesign "vhre" is a separate page, not
    # a tab - SETTINGS_TABS are only the tabs INSIDE Settings. The keys are
    # also page keys, so sidebar._select(key) / _navigate(key)
    # work for all of them (command palette, onboarding "Pair a watch now" ->
    # vhre, guided tour).
    # "guide" was a separate tab here until 18. 9. The explanations and theory
    # belong with the CUES - people look for them exactly when they are reading
    # what each cue says, not two tabs further on. But the key LIVES ON: the
    # guide, the command palette and `Sidebar.GROUPS` refer to it, and
    # `_navigate` redirects it to "spustace" (see below).
    SETTINGS_TABS = ("spustace", "zvuk", "vseobecne")

    # Old keys -> where they go today. Without this, `_navigate("guide")`
    # would fall through to `pages.show("guide")`, i.e. to a page that does
    # not exist, and the window would stay empty - silently, no exception.
    TAB_ALIAS = {"guide": "spustace"}
    # The app is a dashboard with several fixed-layout panels (HUD, command
    # palette, stats grid), not a text editor - freely resizing the window
    # broke the layouts (especially CommandPalette). Instead of fixing every
    # panel for every possible size, the window keeps one fixed size, set in
    # code through geometry() - no dragging the edges by hand (see
    # enable_frameless() and minsize==maxsize below).
    # These are LOGICAL px: CTk multiplies them by the display scale. Where the
    # window does not fit the work area (a 1080p laptop at 150 %, 1366x768),
    # the whole app shrinks at once, not the window size (see
    # `ui_kit.umiestni_pevne_okno`).
    WINDOW_W, WINDOW_H = 1180, 760
    # The mark in the centre of the Today page. At 68 px (its original place
    # in the side panel) the "armed" ring was 1.4 px and got lost. 168 px is
    # the size from the mockup - at that size the ring is about 4 px and
    # really registers in peripheral vision. Above 100 px the frame set is
    # drawn with double (not triple) supersampling, see `ui_shell._EnsoButton`.
    ENSO_SIZE = 168
    # Opacity of the soft central veil behind the enso and the text. < 255 so
    # the dojo SHOWS THROUGH (translucent) - not a dark box, only as much
    # darkening as the text needs to be readable (the rest is carried by the
    # shadow under the text).
    DNES_SCRIM_PEAK = 120
    # Redraw pace of the centre (enso + dojo breathing). 120 ms ~ 8/s = a
    # smooth run of light around the enso, just like the widget had.
    DNES_TICK_MS = 120

    # Heart-rate indicator in the side panel (`_watch_pulse_state` in
    # app_hud.py).
    # zone hysteresis: a new zone has to hold, otherwise the indicator on the
    # boundary (e.g. stress hovering around 25) would blink between two
    # colours on every beat
    WATCH_ZONE_HOLD_S = 1.5

    # Empty-state hero on Today (the live dojo in app_today.py).
    HERO_PERIOD_S = 10.0        # 5 s inhale + 5 s exhale — pace of the bar and the circle

    # Moving a card on Today by dragging (`_dashboard_drag` in app_today.py).
    DASHBOARD_DRAG_PX = 8

    # Heart-rate sensor without a client (`_schedule_no_client_check` in
    # app_session.py). If no client connects within this many ms after
    # switching on, the state changes from "connecting" to "no_client" - a
    # different problem, a different text (B2).
    HR_NO_CLIENT_AFTER_MS = 20000

    # Centre of Today after a resize (`_naplanuj_backdrop` in app_today.py).
    # How long to wait for the size to settle. When the window is moved
    # between monitors, Windows fires `<Configure>` several times in quick
    # succession and EACH of them has a different size, so the guard on
    # `_backdrop_size` does not catch them. Since `background.load()` scales
    # the photo with LANCZOS right in the Tk thread, several recomputes in a
    # row visibly freeze the window.
    BACKDROP_DEBOUNCE_MS = 150

    # History page: table, trend and session detail (app_history.py).
    HISTORY_ROWS = 30          # newest sessions in the table

    # (id, i18n key of the name, theme token of the colour) - also the order
    # of the chips in the picker
    #
    # COLOUR MEANS STATE, NOT METRIC (0.3, UX audit). The session detail had
    # 7 colours in 11 cells and "highest heart rate" in `danger` - an ordinary
    # in-game maximum looked like an alarm, which goes against "this is not a
    # medical device". Now: a number is `text`; a zone colour (`zone_*`) only
    # goes to a value that IS a zone (calm, time over the limit); `blue` only
    # to recovery (HRR), because blue = calm/low (see `theme.py`).
    HISTORY_METRICS = (
        # colours from the row of zones (theme.ZONE_TOKENS), not success/warn -
        # the chart and the zone bar next to it must speak the same colour
        # language
        ("baseline", "metric.baseline.title", "zone_calm"),
        ("hrr", "metric.hrr.title", "blue"),
        ("over", "metric.over.title", "zone_high"),
        ("peak", "metric.peak.title", "text"),
        # 0.2 - History should show the whole picture, not just heart rate:
        # how long the play lasted, how much of it in calm, how well the app
        # could hear and how many cues it sent. The ids and colours are the
        # same as the cards on Today.
        ("session_len", "metric.session_len.title", "text"),
        ("calm_time", "metric.calm_time.title", "zone_calm"),
        ("signal", "metric.signal.title", "text"),
        ("breath", "metric.breath.title", "text"),
    )
    _METRIC_BUCKET_KEY = {"baseline": "baseline", "hrr": "hrr", "over": "over_s", "peak": "peak",
                          "session_len": "duration_s", "calm_time": "calm_s",
                          "signal": "coverage", "breath": "cues"}
    _METRIC_INFO_KEY = {"baseline": "baseline", "hrr": "hrr", "over": "zones", "peak": "peak",
                        "session_len": "session_len", "calm_time": "calm_time",
                        "signal": "signal", "breath": "breath"}
    # What is drawn as bars: quantities whose natural zero means something
    # (zero minutes over the limit is a statement). Baseline and recovery are
    # a line - a bar from zero would leave a few pixels for the 60-70 BPM
    # range. Signal too: it lives around 95-100 % and a bar from zero would
    # hide every dropout in a few pixels at the top.
    _METRIC_BARS = frozenset({"over", "peak", "session_len", "calm_time", "breath"})
    # A bucket holds seconds and coverage 0..1; the chart shows minutes and
    # percentages.
    _METRIC_SCALE = {"over": 1 / 60.0, "session_len": 1 / 60.0,
                     "calm_time": 1 / 60.0, "signal": 100.0}
    # Decimal places on the axis and in "first -> last". Cues are an average
    # per session (1.5 is more honest than a rounded 2).
    _METRIC_DECIMALS = {"over": 1, "breath": 1}

    # Detail of one session: (cell key, i18n key of the label, colour token).
    # The labels are the same words as in the table and on the cards - new
    # ones only where no such word existed yet.
    HISTORY_DETAIL_COLS = 4
    # Colours by the rule at HISTORY_METRICS: a number is `text`, a zone
    # `zone_*`, recovery `blue`. The heart-rate maximum is NO LONGER `danger`.
    HISTORY_DETAIL_CELLS = (
        ("duration", "history.col_duration", "text"),
        ("avg", "history.col_avg", "text"),
        ("max", "history.detail_peak", "text"),
        ("calm", "history.detail_calm", "zone_calm"),
        ("over", "history.col_over", "zone_high"),
        ("breath", "history.detail_breath", "text"),
        ("peak", "history.col_peak", "text"),
        ("hrr", "history.detail_hrr", "blue"),
        ("hrpi", "history.detail_hrpi", "text"),
        ("signal", "history.detail_signal", "text"),
        ("felt", "history.detail_felt", "text"),
    )

    def __init__(self, root):
        self.root = root
        # No flicker when moving between monitors with different scaling:
        # suppresses CTk's drop to alpha 0.15 during the DPI recompute (see
        # ui_kit).
        ui_kit.potlac_dpi_alpha_blik(self.root)
        self.root.title(APP_NAME)
        # Fixed size (see the comment at WINDOW_W above) - the app has no
        # manual resize by the edges, minsize/maxsize are the same as geometry.
        #
        # The window can only be shrunk by scaling, and that has to be chosen
        # BEFORE the first widget exists (the first-start guide as well as
        # `_build_ui`): after a scale change CTk rebuilds every existing
        # widget. Previously the window appeared wherever Windows put it, at
        # full size - on 1366x768 or 1080p at 150 % it was taller than the
        # screen and Settings at the bottom of the side menu were under the
        # taskbar. Now it is centred in the work area of the monitor under the
        # cursor; where it fits, the scale stays as before.
        mierka, mon = ui_kit.umiestni_pevne_okno(
            self.root, self.WINDOW_W, self.WINDOW_H)
        if mierka < 1.0 and mon is not None:
            # To the technical log, not the journal: it tells the player
            # nothing, but with a report like "everything is kind of small" it
            # is the first question.
            app_log.info("okno sa nezmestilo do plochy %dx%d (%d dpi), "
                         "appka zmensena na %.1f %%", mon.work_width,
                         mon.work_height, mon.dpi, mierka * 100.0)
        self.root.minsize(self.WINDOW_W, self.WINDOW_H)
        self.root.maxsize(self.WINDOW_W, self.WINDOW_H)
        # Custom title bar (redesign PHASE 2) - removes the OS frame; the
        # TitleBar itself (in _build_ui) only draws the replacement. Called
        # once here, not in _build_ui, because that only destroys the root's
        # CHILDREN, not the root itself and its bindings.
        enable_frameless(self.root)

        self.listening = False
        self.rebind_index = None
        # NOTE: here used to be `keyboard_listener`, `mouse_listener`,
        # `rebind_kb_listener`, `rebind_mouse_listener` - leftovers from the
        # pynput hooks that phase 3 removed. They were set to None and nobody
        # read them any more (B28). Input is detected today via
        # `GetLastInputInfo`.
        self.gamepad = gamepad.GamepadListener(self.on_gamepad_button,
                                               self.on_gamepad_status)
        self._rebind_gamepad_temp = False
        self.tray_icon = None
        self.typing = False
        self._ready = False
        # The window is cloaked (DWM cloak) until it is fully drawn at
        # startup - see `_zahal_do_dokreslenia` / `_odhal_hotove_okno`.
        self._zahalene = False
        self._listen_started = None
        self.log_collapsed = True
        self._last_log_line = None
        self._guide_panel = None
        self._assets_progress_frame = None
        self._assets_progress_bar = None
        self.session_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        self.session_label = None
        self._auto_started_listening = False
        self.game_watcher = None

        ctk.set_appearance_mode("dark")

        settings = self.load_settings()
        self.lang = settings["lang"]
        # TWO WORLDS, ONE BODY (0.2, B3-worlds). The world (play/work) decides
        # the look (`theme.WORLD_THEME`), which history and insights the app
        # shows and whether a cue may sound. `load_settings` has already
        # ensured that the theme matches the world.
        self.world = settings["world"]
        # The world of the RUNNING session - sealed when it opens, and the
        # switch no longer changes it (see `_open_hr_session`).
        self._session_world = self.world
        # The cue style the player chose, and the ladder rung of the running
        # session (0.2, `rebrik.py`). The rung is decided when the session
        # opens.
        self.cue_style = settings["cue_style"]
        self._cue_style_rel = self.cue_style
        self._cue_rung = rebrik.vrchol(self.world, self.cue_style)
        self._snooze_po_hlaske = None
        self.theme_key = settings["theme"]
        self.pal = theme_mod.tokens(self.theme_key)

        self.start_minimized = bool(settings["start_minimized"])
        # Already told once that × does not quit the app, only hides it in the
        # tray (`on_close`).
        self.tray_close_explained = bool(settings["tray_close_explained"])
        # The warning about an installed 0.2 has already been shown
        # (`_upozorni_na_staru_instalaciu`). Read HERE already, not only at the
        # warning: otherwise the first `save_settings` below would write False
        # and the warning would come on every start.
        self.old_installer_warned = bool(settings.get("old_installer_warned"))
        self.auto_profile_enabled = bool(settings["auto_profile_enabled"]) and PSUTIL_AVAILABLE
        self.overlay_configs = settings["overlay_configs"]
        self._vizualy_napravene = bool(settings.get("_vizualy_napravene"))

        if settings["first_run"]:
            self.root.withdraw()
            wizard = OnboardingWizard(self.root, prvy_start=True)
            self.root.wait_window(wizard.top)
            if getattr(wizard, "quit_requested", False):
                # The player closed the introduction (cross, Esc, Alt+F4) and
                # confirmed Quit. NOTHING is saved: the theme is missing from
                # settings, so the next start shows the introduction again -
                # exactly what the question promised them. No port, shortcut or
                # voice is running yet that would need stopping (the only
                # thread is the guide's sound preparation - a daemon, it writes
                # files via .tmp + replace), and `main()` has not yet started
                # waiting for a second start.
                self.root.destroy()
                raise SystemExit(0)
            if wizard.confirmed:
                # Step 4 chooses the MAIN WORLD; `choice` is its theme.
                self.world = theme_mod.theme_world(wizard.choice)
                self._session_world = self.world
                self.theme_key = theme_mod.WORLD_THEME[self.world]
                self.pal = theme_mod.tokens(self.theme_key)
                self._apply_diagnostics(settings, wizard.diagnostics)
                settings["volume"] = wizard.volume_value
                # Step 5: how the app should speak up (cue style). None = the
                # player chose nothing and the default voice stays (like "Not
                # sure").
                self._prevezmi_styl_z_onboardingu(wizard)
                # if the player clicked "Pair a watch now" in onboarding, we
                # open the pairing dialog only AFTER the window is fully built
                # (see the end of __init__) - right now the app is not ready
                # yet
                self._pending_pairing = bool(getattr(wizard, "wants_pairing", False))
            # The first start NEVER hides into the tray - the window must stay
            # visible, active and in the foreground regardless of
            # `start_minimized`.
            #
            # WARNING (Tk on Windows): a frameless window (overrideredirect) on
            # which withdraw() was called even BEFORE it was first shown does
            # NOT APPEAR after a single deiconify() - it stays "withdrawn" and
            # after onboarding the player sees only the desktop (the guided
            # tour then floated over an empty screen). What helps is processing
            # pending events and calling deiconify again; verified live
            # (gui_harness_onboarding).
            #
            # Cloak only HERE, after the guide: it is `transient(root)`, so the
            # root must not be cloaked while it is open. The player then does
            # not see the pages being built (including the flickering
            # Settings) - the window shows up all at once, finished, only after
            # __init__, when the Tk loop starts (see `_odhal_hotove_okno`).
            self._zahal_do_dokreslenia()
            self.root.deiconify()
            self.root.update()
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()

        self.monitor_target = settings["monitor_target"]
        self.hud_config = settings["hud_config"]
        # Today shows at most DASHBOARD_MAX_CARDS cards (a 2x2 grid). A longer
        # list could only be had by editing the JSON by hand - it cannot be
        # picked.
        self.dashboard_stats = list(settings["dashboard_stats"])[:DASHBOARD_MAX_CARDS]
        self.breath_inhale_s = float(settings["breath_inhale_s"])
        self.breath_exhale_s = float(settings["breath_exhale_s"])
        # The app computes the load threshold itself for every session from its
        # own data (`hr_stats.dynamicky_prah_zataze`). None = nothing to
        # compute it from yet.
        self._prah_z_dat = None
        self._prah_z_relacii = 0
        self.overlay_manager = SomaticOverlayManager(self.root, pal=self.pal)
        self.overlay_manager.set_monitor_target(self.monitor_target)
        self.overlay_manager.set_breath_seconds(self.breath_inhale_s, self.breath_exhale_s)
        self._apply_overlay_labels()
        for i, cfg in enumerate(self.overlay_configs):
            self.overlay_manager.configure(i, enabled=cfg["enabled"], scale=cfg["scale"],
                                           pos=(cfg["pos_x"], cfg["pos_y"]),
                                           color=cfg.get("color") or "")

        # Plain-python mirrors - listener threads must not read Tk variables.
        # The gap for a MANUAL trigger (Test, HUD preview). A constant - see
        # the NOTE at the removed "Timing" panel on the Sound page.
        self.cooldown_value = DEFAULT_COOLDOWN
        self.rate_value = int(settings["rate"])
        self.volume_value = int(settings["volume"])
        self.tour_seen = bool(settings.get("tour_seen", False))
        # Capped at the last step: up to 0.2.1 the tour had 10 steps, and a
        # saved position from it would show "step 9 of 6" in Settings.
        self.tour_step = min(max(0, int(settings.get("tour_step", 0) or 0)),
                             GuidedTour.STEP_COUNT - 1)
        # Language of what the app draws INTO THE GAME - see `_game_text`.
        self.game_lang = settings.get("game_lang", LANG_EN)
        self.balance_value = int(settings["balance"])
        # Constants for a MANUAL trigger (Test button, HUD preview).
        # They cannot be set - how often the app speaks up is governed by the
        # "How often I speak up" option on the Cues page, and that is the only
        # place.
        self.overlap_value = False
        self.last_global_trigger_time = 0.0

        # --- Heart-Rate Sensor (Wi-Fi / UDP biofeedback) ---
        self.hr_ip = str(settings["hr_ip"])
        # HIDDEN IP (0.2): the PC's address is not shown on screen by itself -
        # the app window often ends up on a stream or in a screenshot for a
        # tester. It is revealed only by "Show IP" (pairing, Settings) and only
        # until restart: DELIBERATELY only in memory, it is not written to
        # settings (see netinfo.mask_ip).
        self.show_ip = False
        self.show_ip_var = None
        self.hr_ip_entry = None
        self.hr_port = int(settings["hr_port"])
        # A computed value, not a setting. The real number comes the first time
        # a session opens, from `hr_stats.dynamicky_kriticky`; until then the
        # fallback value.
        self.hr_critical_bpm = int(hr_stats.KRITICKY_ZALOHA)
        self.hr_monitoring_enabled = bool(settings["hr_monitoring_enabled"])
        self.zanshin_graduated = bool(settings["zanshin_graduated"])
        self.zanshin_graduated_at = settings.get("zanshin_graduated_at")
        self._hr_state = "disconnected"   # disconnected | connecting | connected
        self._hr_last_bpm = None
        # Heart rate that the app heard during this run has stopped coming
        # ("dropped out") - as opposed to "nothing has arrived yet". Display
        # and log only; the trigger has its own pause (`_suspend_cue_trigger`).
        # `_hr_lost_od` is the time of the last sample before the dropout (for
        # the journal line).
        self._hr_lost = False
        self._hr_lost_od = None
        self._hr_over_since = None
        self._hr_overlay_warned = False
        self._hr_client_linked = False
        # Generation of the running receiver thread (0 = none). We drop updates
        # with an old generation - otherwise the indicator would freeze on the
        # last BPM even after the sensor is switched off.
        self._hr_generation = 0
        self.hr_status_label = None
        self.hr_enabled_var = None
        self.hr_ip_show_switch = None     # "Show IP" next to the address field
        self.heart_rate_monitor = HeartRateMonitor(
            self.on_hr_bpm, self.on_hr_status, on_metrics=self.on_hr_metrics)
        # How many step messages are still to be written to the journal. Set
        # when a session opens - we need to know WHAT the watch really sends,
        # so the movement threshold can be set from data and not by eye.
        self._metrics_log_left = 0
        # Heart-rate statistics (baseline, load, session summary) + the live
        # HUD panel. `HeartStats` is pure data and is called only from the GUI
        # thread via `_apply_hr_bpm`, so it needs no lock.
        self.hr_stats = hr_stats.HeartStats(self.hr_critical_bpm)
        self.hr_sessions_path = os.path.join(DATA_DIR, "hr_sessions.json")
        # The evening's course, event by event (point 6 of the spec from
        # 18. 9.). Until now `_cue_log` was only counted into a dialog and
        # thrown away - you could not read back when what happened and why
        # the app stayed silent.
        self.hr_events_path = os.path.join(DATA_DIR, "hr_events.jsonl")
        # Measurement windows around cues. A separate file, not part of the
        # session summary: `hr_sessions.json` keeps the last MAX_SESSIONS
        # sessions and silently drops older ones, so the windows would
        # disappear exactly when there start to be enough of them to read
        # something from.
        self.hr_windows_path = os.path.join(DATA_DIR, "hr_windows.json")
        # Whether the player is doing something right now - GetLastInputInfo,
        # no hook. The record serves as the third channel in the measurement
        # window (alongside heart rate and load), and in phase 2 pause
        # detection will also come from it.
        self.activity = activity.ActivityTracker()
        self._activity_job = None
        # 20 minutes without even a short pause in input (controller gyro, a
        # stick without a dead zone)? A quiet line on Today, once per session -
        # see `_tick_nonstop_input`.
        self._nonstop_input = activity.NonstopInputWatch()
        self._dnes_nonstop_text = ""
        # The cue state machine: load above the threshold for 90 s -> armed ->
        # waits for a pause -> cue. A pure module, tested without Tk.
        self.cue_trigger = trigger.CueTrigger()
        self._cue_log = []           # armings and cancellations, for the session summary
        # How many times refreshing the Today page failed. See
        # `_refresh_dnes_stats`: its body is in a single `except`, so a broken
        # page would otherwise show up as nothing at all - neither as an error,
        # nor in gui_screenshots.
        self._dnes_refresh_fails = 0
        # Is the trigger armed? The ONLY source of truth for the UI. The ring
        # on the enso and the text in the breathing bar both read from here -
        # if each derived the state on its own (e.g. from
        # `cue_trigger.is_armed`), one day they would drift apart and nobody
        # would notice. Written only in `_set_enso_armed`.
        self._cue_armed = False
        # Calls from threads that arrived before `mainloop()`. The cap is a
        # safeguard: if the loop never started, the queue must not grow.
        self._ui_pending = deque(maxlen=200)
        self.snooze_hotkey = settings["snooze_hotkey"]
        # The player picked the shortcut themselves - the app will not swap it
        # for them on a clash with the keyboard layout
        # (`_vyber_skratku_pri_starte`, 0.3).
        self.snooze_hotkey_chosen = bool(settings.get("snooze_hotkey_chosen", False))
        # The last shortcut registration failed (another program holds it) -
        # the line in Settings says so (`_snooze_hotkey_sub`).
        self._hotkey_zlyhala = False
        # Background photo. Changing the picture and turning it off are both
        # in `background.py` - here only the chosen softness is kept.
        self.background_opacity = settings["background_opacity"]
        self._hotkey = None
        # insights from the history analysis (hr_insights) - the last saved
        # result is shown right away, a fresh one is computed in the
        # background after start
        self.hr_insights_path = os.path.join(DATA_DIR, "hr_insights.json")
        _stored = hr_insights.load_insights(self.hr_insights_path)
        # Insights are per ONE world (B3-worlds). Ones saved for another world
        # - or from an older version that computed them from everything
        # together - are not shown; fresh ones are computed shortly after start
        # (`run_hr_analysis`).
        if _stored.get("world") != self.world:
            _stored = {}
        self._hr_insights = list(_stored.get("insights") or [])
        self._hr_insights_at = _stored.get("computed_at")
        self._hr_analysis_thread = None
        # Analysis refused because the previous one was still running (e.g.
        # right after a world switch) - it runs again when that one finishes.
        # See `run_hr_analysis`.
        self._hr_analysis_rerun = False
        self._hr_rerun_job = None
        self._hr_session_open = False
        # THE FIRST SESSION AFTER THE INTRODUCTION IS SETUP (0.3): the
        # introduction, pairing and the tour are calm at the desk, not playing.
        # The first saved session gets `setup` and the thresholds do not learn
        # from it (`_suhrn_relacie`, `hr_stats.ciste_relacie`);
        # `_close_hr_session` drops the flag after saving. Only during a run
        # with the introduction - not after a restart.
        self._relacia_nastavovania = bool(settings["first_run"])
        # How many seconds of the session the HUD was visible (biofeedback: a
        # heart rate you can see gets regulated subconsciously). Sampled in
        # `_tick_cue_trigger` so it also catches a toggle in the middle of play;
        # it goes into the summary as a share of the ACTIVE time.
        # `_hud_active_s` is the same time, only without the visibility
        # condition - we divide by it (not by the raw duration), because the
        # tick drops gaps >=5 s (PC sleep), so otherwise the share would
        # artificially fall after a sleep.
        self._hud_vis_s = 0.0
        self._hud_active_s = 0.0
        self._hud_tick_t = None
        self.hud = StatsHud(self.root, self.hr_stats,
                            self.overlay_manager.style,
                            monitor_target=self.monitor_target)
        self._apply_hud_config()
        self.sfx_volume = self.volume_value
        self.tts_volume = self.volume_value
        self._recompute_volumes()

        self.log_text = None
        self.slots = []
        self.profiles = settings["profiles"]
        self.active_profile_name = settings["active_profile"]
        self.voice_map = {}          # description -> SAPI voice id
        self.saved_voice_id = settings["voice_id"]
        self.rate_var = None

        # --- Edge Natural TTS ---
        self.engine_pref = settings["engine_pref"]
        self.engine = (ENGINE_SAPI
                       if self.engine_pref == ENGINE_EDGE and not audio_engine.EDGE_AVAILABLE
                       else self.engine_pref)
        self.edge_voice_id = settings["edge_voice"]
        self.edge_voice_map = {}     # description -> ShortName
        self.edge_cache = EdgeTTSCache(self.log_threadsafe)
        self.edge_status_label = None
        self.edge_retry_btn = None
        # "Update voice" (0.3): a row with the button and a link to the new
        # release; while the update runs, cue preparation waits for its result.
        self.edge_update_row = None
        self.edge_update_btn = None
        self.edge_releases_btn = None
        self._aktualizacia_hlasu_bezi = False
        self._pregen_po_aktualizacii = False
        self._pregen_job = None
        self._pregen_seq = 0
        # A cue that was missing from the cache while listening (`_speak_text`)
        # - it is generated only after `stop_listening`, not in the middle of a
        # game.
        self._pregen_po_hre = False
        # The first start waits with watching until the voice is prepared
        # (`_zacni_sledovat_po_priprave_hlasu`).
        self._prvy_start_caka = False
        self._prvy_start_job = None
        self._prvy_start_do = 0.0

        self.worker = SpeechWorker(self.log_threadsafe, on_voices=self.on_voices_ready)
        self.worker.pending_voice = self.saved_voice_id or None
        self.worker.pending_rate = self.rate_value
        self.worker.pending_volume = self.tts_volume
        self.worker.start()

        self.audio = AudioDispatcher(self.worker, self.log_threadsafe)
        self.audio.overlap = self.overlap_value
        self.audio.rate = self.rate_value
        self.audio.sfx_volume = self.sfx_volume
        self.audio.tts_volume = self.tts_volume

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        # Windows shutdown / restart / sign-out: Tk on Windows maps
        # WM_QUERYENDSESSION to the WM_SAVE_YOURSELF protocol and calls the
        # handler synchronously while Windows waits. Without this, shutting
        # down the PC threw away the whole session - WM_DELETE_WINDOW does not
        # arrive then (`_pri_vypinani_windows`).
        self.root.protocol("WM_SAVE_YOURSELF", self._pri_vypinani_windows)
        self.root.bind_all("<Control-k>", lambda e: self.open_command_palette())
        if TRAY_AVAILABLE:
            self.setup_tray()
        self._apply_window_icon()

        os.makedirs(AUDIO_DIR, exist_ok=True)
        os.makedirs(TTS_CACHE_DIR, exist_ok=True)
        self._ready = True
        self.save_settings()
        self.log(tr("log.ready"))
        self.log(tr("log.safe_mode"))
        if self._vizualy_napravene:
            # The app has just turned on, by itself, the visuals that were
            # muting it. It must not do that silently - the player should know
            # that something in their settings changed, and be able to undo it.
            self.log(tr("log.vizualy_napravene", page=stranka_vhre(self)))
        # The settings could not be loaded and the app reached for the backup
        # or the defaults - it says so once, now into the journal
        # (`load_settings`).
        self._oznam_obnovu_nastaveni()
        # A session that did not get saved last time (crash, Task Manager,
        # power cut) goes into the history BEFORE the sensor opens a new one -
        # and from now on the open session is saved aside every 5 minutes
        # (checkpoint).
        self._obnov_rozpracovanu_relaciu()
        self._naplanuj_rozpracovanu_relaciu()
        # An installed 0.2 shares the data folder - its uninstaller would, on
        # "Nie" (No), delete this history too. Not on the first start (the
        # guide is running), it is said on the next one.
        if not settings["first_run"]:
            self._upozorni_na_staru_instalaciu()

        if PSUTIL_AVAILABLE:
            # The process list is read ONLY when auto-profile is on. Previously
            # the scan always ran and the switch turned off only discarded the
            # result - so every 4 s the app read process names even for a
            # player who had turned it off.
            if self.auto_profile_enabled:
                self._start_game_watcher()
        else:
            self.log(tr("log.auto_profile_unavailable"))

        if self.hr_monitoring_enabled:
            self.start_heart_rate_monitor()
        # NOTE: the optional Steamworks layer used to be switched on here.
        # Zanshin has no Steam integration at all (0.2) - the layer did
        # nothing without the SDK anyway, so the app runs exactly as before.
        self._tick_session()
        self._tick_activity()
        # heart-rate history analysis in the background (not on the GUI
        # thread), only once the window is up
        self.root.after(1500, self.run_hr_analysis)

        # After start the window must stay visible and in the foreground - the
        # app hides into the system tray only at the user's explicit request
        # (the "Minimize to tray" button, or closing the window if it is set
        # up that way), never automatically.
        #
        # But show it only once it is DRAWN: Windows only paints a shown
        # window, so without cloaking the player would first see a translucent
        # frame and then the assembly piece by piece (title bar, breathing bar,
        # empty page, stats, dojo).
        self._zahal_do_dokreslenia()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        if self._zahalene:
            self.root.after(0, self._odhal_hotove_okno)
            # Safeguard: the window must never stay invisible, whatever happens
            # (the reveal does not run, CTk changes the order of steps...).
            self.root.after(self.ODHAL_POISTKA_MS, lambda: self._odhal_hotove_okno(
                pokus=self.ODHAL_MAX_POKUSOV))
        if self.start_minimized and not settings["first_run"] and TRAY_AVAILABLE:
            self.root.after(150, self.minimize_to_tray)

        self.refresh_edge_banner()
        if sfx_assets.missing_count() > 0:
            self.show_assets_progress()
        threading.Thread(target=self._ensure_sfx_assets, daemon=True).start()
        if audio_engine.EDGE_AVAILABLE:
            # The list of Edge voices is fixed (`EDGE_FALLBACK_VOICES`) and is
            # NOT downloaded. Previously every start with Edge - which is the
            # default - pulled the catalogue from Microsoft, only to trim it
            # down to exactly this list. The app goes to Microsoft only during
            # cue preparation (`pregenerate`), and only when the in-game cues
            # really speak.
            self._load_edge_voices()
        else:
            self.log(tr("log.edge_tts_missing"))

        # After onboarding the app STARTS LISTENING by itself.
        #
        # Previously the player clicked through four steps about what the app
        # does and landed on a page with the message
        # "Zastavené. Spúšťače nereagujú." (Stopped. Triggers do not react.) -
        # in the whole introduction they never once heard what they had
        # installed it for. The button on the last step is called "start", so
        # let it really start; stopping takes one click on the same bar.
        # Only now, when the threads are already running: deliver what they
        # managed to log before the loop started.
        self.root.after(0, self._flush_ui_pending)

        # The default shortcut, which on some keyboard layouts would swallow a
        # letter (AltGr = Ctrl+Alt), is swapped before it is even registered.
        self._vyber_skratku_pri_starte()
        self.start_snooze_hotkey()
        # The line in Settings was created before registration: it must report
        # a taken (or swapped) shortcut right from the start.
        self._refresh_snooze_hotkey_row()

        if settings["first_run"]:
            # Only AFTER the voice is prepared (at most `PRVY_START_MAX_S`):
            # while the app is watching, it does not go to Microsoft, so a
            # start 250 ms later stopped the preparation right away and the
            # first evening spoke with the Windows voice.
            self._zacni_sledovat_po_priprave_hlasu()

        # If the player clicked "Pair a watch now" in onboarding, we open the
        # pairing dialog only now - the app window is already finished and
        # visible. The first tour comes only AFTER it (`on_close`), not instead
        # of it: previously pairing skipped it completely, because it was only
        # in the elif branch. The two guides still never overlap.
        prehliadka = settings["first_run"] and not self.tour_seen
        if getattr(self, "_pending_pairing", False):
            self._pending_pairing = False
            self.sidebar._select("vhre")
            po_parovani = self._prehliadka_po_parovani if prehliadka else None
            self.root.after(400, lambda: self.open_watch_pairing(on_close=po_parovani))
        elif prehliadka:
            self.root.after(600, self.start_tour)

    # ---------- start without flicker ----------
    #
    # At start the window was on screen before it was drawn: the first frame
    # almost fully transparent (the desktop showed through), then 4-8
    # intermediate steps. On the first start after onboarding you could see
    # all the pages assembling. It was not the amount of data (at today's
    # history size) - Windows sends painting only to a SHOWN window and Tk
    # paints lazily. The DWM cloak (`ui_kit.zahal_okno`) shows the window and
    # lets it be drawn, it just does not display it.

    # How many times to wait 10 ms for CTk in `mainloop()` to hide the window
    # and show it again (roughly 1-2 s in total, Tk timers on Windows are
    # coarser). After that the window is revealed anyway. Normally CTk
    # manages it in under 0.1 s.
    ODHAL_MAX_POKUSOV = 100
    # Last safeguard: after 10 s at the latest the window is always visible.
    ODHAL_POISTKA_MS = 10000

    def _zahal_do_dokreslenia(self):
        """Cloaks the window right before it is first shown. When Windows
        does not accept it (older system, error), `_zahalene` stays False
        and the start runs as before - just with the flicker."""
        if not getattr(self, "_zahalene", False):
            self._zahalene = ui_kit.zahal_okno(self.root, True)

    def _okno_este_schovane(self):
        try:
            return self.root.state() != "normal"
        except Exception:
            return False

    def _odhal_hotove_okno(self, pokus=0):
        """Shows the window only when fully drawn - all at once, not in pieces.

        In `mainloop()` CTk hides the window once more, recomputes it and
        shows it again (dark title bar, `_windows_set_titlebar_color`);
        `after(0)` runs exactly in that hidden stretch. While the window
        is not "normal", it tries again in 10 ms - at most
        `ODHAL_MAX_POKUSOV` times, then reveals it anyway.

        The waiting is DELIBERATELY outside try/finally: a `return` from
        inside would, via `finally`, reveal the window too early, not yet
        drawn. The reveal itself is in `finally`, so it happens even when
        drawing crashes. If the reveal failed too, `_zahalene` stays True
        and the safeguard (`ODHAL_POISTKA_MS`) tries again."""
        if not getattr(self, "_zahalene", False):
            return
        if pokus < self.ODHAL_MAX_POKUSOV and self._okno_este_schovane():
            try:
                self.root.after(10, lambda: self._odhal_hotove_okno(pokus + 1))
                return
            except Exception:
                app_log.exception("start: odklad odhalenia zlyhal - odhalim hned")
        try:
            self.root.update()               # layout + WM_PAINT + redraw
            self._refresh_dnes_backdrop()    # so the dojo is in the very first frame
            self.root.update_idletasks()
        except Exception:
            app_log.exception("start: dokreslenie pred odhalenim zlyhalo")
        finally:
            self._zahalene = not ui_kit.zahal_okno(self.root, False)

    # ---------- UI ----------

    def _build_ui(self):
        pal = self.pal
        # Elements that do not keep their own copy of the palette (tooltip
        # bubbles) take it from here - otherwise they would draw with the old
        # `ui_shell.PAL`.
        ui_shell.set_theme_pal(pal)
        self.root.configure(fg_color=pal["bg"])
        # recreating the window (theme/language switch) also destroys the
        # SFX preparation progress in the making - we reset the references so
        # we do not try to update an already destroyed widget.
        self._assets_progress_frame = None
        self._assets_progress_bar = None
        # WARNING: the HUD and the in-game visuals are separate Toplevel
        # windows, and they are children of the root too. Blindly deleting all
        # children destroyed them on every theme/language switch - StatsHud
        # never rebuilt them and the HUD stayed empty for good. We only clear
        # the main window's content.
        for child in self.root.winfo_children():
            if isinstance(child, tk.Toplevel):
                continue
            child.destroy()

        # --- outer wrapper: custom title bar on top, body (sidebar + pages)
        # below it. `enable_frameless()` is called only once in __init__, not
        # here - the OS frame need not be removed again on every rebuild. ---
        # The wrapper and the body took `fg_color` from the module-level
        # `ui_shell.PAL` - from the old greenish palette the redesign replaced.
        # On top of that, this took the colour out of theme recolouring
        # (`theme_recolor` only changes what really is in the theme's palette),
        # so when switching Aizome/Sumi the window background stayed the same.
        # Now it is `pal["bg"]`.
        appwrap = ctk.CTkFrame(self.root, fg_color=pal["bg"], corner_radius=0)
        appwrap.pack(fill="both", expand=True)
        self.appwrap = appwrap

        # NOTE: above the title bar there used to be a `DojoBand` here - a
        # photo strip of fixed height 130 px (ui_shell.DojoBand +
        # hud_paint.render_dojo_band / render_lamp_glow). Removed: the title
        # bar belongs at the very top of the window, and the strip above it
        # was 130 px of dead space that only took away from the fixed window
        # height (WINDOW_H). Along with it went the "Dojo background" slider
        # in Settings and the `dojo_intensity` value - without the strip they
        # had nothing left to control.
        # The world switch (Play | Work) sits in the title bar left of ⓘ - see
        # `set_world` and `ui_shell.TitleBar`.
        titlebar = TitleBar(appwrap, root_window=self.root, app_name=APP_NAME,
                            on_close=self.on_close, version=tr("app.version_short"),
                            pal=pal, on_about=self.show_about,
                            about_tip=tr("about.title"), licence=LICENCIA,
                            world_values=self._world_labels(),
                            world_value=self._world_label(self.world),
                            on_world=self._on_world_label,
                            world_tip=tr("world.tip"))
        titlebar.pack(fill="x", side="top")
        self.titlebar = titlebar
        # Fifteen clicks on the version number open debugging (§3.2). A local
        # Tk binding on one widget, not a global hook.
        titlebar.on_dev_layer = self.open_dev_layer

        body = ctk.CTkFrame(appwrap, fg_color=pal["bg"], corner_radius=0)
        body.pack(fill="both", expand=True, side="top")
        self.body = body

        self.pages = PageContainer(body)
        self.page_frames = {}          # key -> page frame (main pages and tabs too)

        def _navigate(_key):
            self._navigate(_key)

        self.sidebar = Sidebar(body, on_navigate=_navigate, pal=pal,
                               version=tr("app.version_short"),
                               on_palette=self.open_command_palette,
                               on_enso_toggle=self.toggle_listening,
                               on_pair_watch=self.open_watch_pairing, labels={
            "pair_tip": tr("dnes.empty_btn"),
            "pair_live_tip": tr("dock.pulse_live_tip"),
            "dnes": tr("nav.dnes"),
            "historia": tr("nav.historia"),
            # in the Work world "Screen" (`_nazov_vhre`, app_today.py)
            "vhre": self._nazov_vhre(),
            "nastavenia": tr("nav.nastavenia"),
            "cmdk": tr("nav.cmdk_hint"),
            "search": tr("nav.search"),
            "watch": tr("nav.watch"),
            "enso_start_tip": tr("dock.start_tip"),
            "enso_stop_tip": tr("dock.stop_tip"),
            "state_tip": tr("sidebar.state_tip"),
        })
        # The heart-rate indicator asks for its state itself on every tick -
        # that way it beats smoothly regardless of how often data arrive from
        # the watch.
        if getattr(self.sidebar, "pair_btn", None) is not None:
            try:
                self.sidebar.pair_btn.set_state_source(self._watch_pulse_state)
            except Exception:
                pass
        self.sidebar.pack(side="left", fill="y")
        self.pages.pack(side="left", fill="both", expand=True)

        built = {}
        for key, builder in (("dnes", self._build_dnes_page),
                             ("historia", self._build_historia_page),
                             ("vhre", self._build_vhre_page),
                             ("nastavenia", self._build_settings_group)):
            frame = ctk.CTkFrame(self.pages, fg_color=pal["bg"])
            self.pages.add_page(key, frame)
            built[key] = frame
            self.page_frames[key] = frame
            builder(frame, pal)

        self.pages.show("dnes")

        self._refresh_nav_badges()

        # command palette (Ctrl+K) - its content is generated anew on every
        # open (see open_command_palette), so it never goes stale after
        # adding/deleting a slot or profile outside a full _build_ui. The
        # button in the side panel calls it directly via `on_palette` (see
        # Sidebar).

        # NOTE: `QuickDock` used to be built here - three icons at the bottom
        # of the side panel (🔊 mute, 😴 snooze, ⌘ quick profile). Removed on
        # purpose, not for lack of space:
        #
        #   One-click MUTING does not belong in this app. Its whole value
        #   rests on interrupting exactly when the body is up - and that is
        #   precisely the moment the player is most annoyed with it. One-click
        #   muting would therefore be used systematically exactly when the
        #   cue is most justified. The volume can be pulled to zero in
        #   Settings -> Sound; that it takes three clicks instead of one is a
        #   FEATURE: turning it off for good should be a decision, not a
        #   reflex.
        #
        #   SNOOZE stayed, it just has no button any more - it has a global
        #   shortcut (Ctrl+Alt+Z, `start_snooze_hotkey`) that works in-game
        #   too, and that is where the player needs it. It is time-limited
        #   and expires by itself, so it is not a switch. That it is running
        #   is shown by the status dot in the row
        #   (`_refresh_snooze_indicator`). Since 0.2.1 it is also in the tray
        #   icon's menu (`setup_tray`) - another app may hold the shortcut.
        #
        #   The PROFILE is reachable via the cog (Settings -> Cues) and via
        #   the Ctrl+K command palette.

        # backward compatibility for
        # show_assets_progress()/_update_assets_progress()/refresh_edge_banner(),
        # which expect self.main (the parent for the banner) and self.main_grid
        # (the "before which" anchor the banner/progress get inserted before).
        self.main = built["dnes"]
        self.main_grid = self._dashboard_anchor_frame
        # An ALIAS, not a second mark. Since 2.1 the mark lives in the centre
        # of the Today page, but `guided_tour.py`, `gui_harness_auto.py` and
        # `gui_harness_onboarding.py` look for it as `app.sidebar.enso` - and
        # they look for it BY NAME, so a rename would make them fail SILENTLY
        # (the tour bubble would just stop pointing at anything). Through this
        # alias they find it, and `Sidebar.set_pal` keeps recolouring it too.
        if getattr(self, "sidebar", None) is not None:
            self.sidebar.enso = self.enso
        # A window rebuild (language, theme rescue) builds the status dot anew
        # and it starts as not snoozed. During a "not now", which since 24. 9.
        # keeps listening, it would then glow green "the app is listening"
        # instead of amber.
        if getattr(self, "_snooze_job", None) is not None:
            self._refresh_snooze_indicator()

    def _build_dnes_page(self, page, pal):
        """Today: breathing bar (start/stop), heart rate with load, session
        summary and journal.

        The original "Dashboard" had a wide button at the top that blinked
        in two colours. Here, instead, there is `KamaeBar` - the only
        moving element in the window, which breathes in the same rhythm as
        the breathing circle in-game and stands still when stopped. So the
        state is not read from a colour but from whether the interface
        moves.
        """
        wrap = ctk.CTkFrame(page, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=ui_kit.PAGE_GUTTER, pady=(20, 20))

        # --- missing edge-tts banner (hidden until refresh_edge_banner shows it) ---
        # Small text on the red `danger` fill had only ~3:1 (0.3 batch 4b, the
        # rule in theme.py) - the banner is now a `surface` area with a
        # `danger_text` border, the text in `text`, "Try again" from
        # `ui_kit.button`.
        self.banner = ctk.CTkFrame(wrap, fg_color=pal["surface"], border_width=1,
                                   border_color=pal["danger_text"],
                                   corner_radius=ui_kit.RADIUS_CONTROL)
        self.banner_label = ctk.CTkLabel(self.banner, text="", justify="left",
                                         anchor="w", text_color=pal["text"],
                                         font=ui_kit.ui(11))
        self.banner_label.pack(side="left", padx=14, pady=10, fill="x", expand=True)
        ui_kit.button(self.banner, pal, tr("common.retry"),
                      command=self.retry_edge_import).pack(side="right", padx=14, pady=10)

        anchor = ctk.CTkFrame(wrap, fg_color="transparent")
        self._dashboard_anchor_frame = anchor
        anchor.pack(fill="x")

        # MAIN SWITCH: the "▶ Start watching" / "■ Stop watching" button in
        # the breathing bar (0.3 batch 4). The texts have one place
        # (`_texty_pasu`, app_cues.py), so that a window rebuild, a state
        # change and an auto-profile switch all set them the same way.
        self.kamae = ui_kit.KamaeBar(anchor, pal, on_toggle=self.toggle_listening)
        self.kamae.set_texts(*self._texty_pasu())
        # The mark (enso) breathes EXACTLY with the breathing line of this
        # header - one window, one rhythm. See `KamaeBar.phase()`.
        # On the right it leaves room for the scrollbar below it, so the bar
        # ends on the same right edge as the cards (audit: the bar reached
        # ~25 px further).
        self.kamae.pack(fill="x", padx=(0, ui_kit.SCROLLBAR_W))

        # When the app last spoke up. Deliberately muted: it is context for
        # the state, not an achievement. When nothing has happened yet, the
        # line is not shown at all - an empty "0x" would be a counter. Since
        # 2.1 it is not a widget but text drawn in the centre
        # (`_paint_dnes_canvas`); `_refresh_last_cue` only changes this string
        # and requests a redraw.
        self._dnes_lastcue_text = ""

        # The window is a fixed 1180x760 (see WINDOW_W/H) and below the
        # breathing bar about 600 px remain. While there were only two cards,
        # it fit; with a third panel it no longer does and the journal would
        # fall out of the window. The bar stays FIXED at the top (its rhythm is
        # the app's state and must not scroll away), everything below it
        # scrolls - just like on History.
        body = ui_kit.stranka_scroll(wrap, pal)
        body.pack(fill="both", expand=True)
        self.dnes_body = body

        # --- state | stats ---
        # The page's centre of gravity is the STATE, not numbers. On the left
        # the mark that carries the state, on the right the numbers. The panel
        # with heart rate and the curve moved BELOW this pair - it is a
        # detail, not the first thing the player should see.
        cols = ctk.CTkFrame(body, fg_color="transparent")
        cols.pack(fill="x", pady=(14, 0))
        cols.grid_columnconfigure(0, weight=1)
        # 300 px fixed: in German and Japanese the card labels are longer, and
        # with a flexible width they would wrap differently in every language.
        cols.grid_columnconfigure(1, weight=0, minsize=300)
        cols.grid_rowconfigure(0, weight=1)

        # The row height is set by the right column (cards and zones). Until
        # there is a session with heart rate, the cards are hidden
        # (`_sync_dnes_prazdny_stav`) and the column is low - so the centre
        # keeps its own minimum that fits the mark, the heading and the
        # longest status sentence (port taken).
        stred = ctk.CTkFrame(cols, fg_color="transparent", height=340)
        stred.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.dnes_stred = stred

        # CENTRE = tk.Canvas, not a frame with labels.
        #
        # WHY: a CTk/tk widget cannot be transparent over a photo -
        # `fg_color="transparent"` inherits the parent's SOLID colour, so the
        # enso and the text over the dojo always sat on a dark SQUARE (and no
        # scrim covered it, because the box is an opaque rectangle). The Canvas
        # draws the dojo, the enso (a TRANSPARENT PNG via `create_image`) and
        # the text (`create_text` = no background) onto one surface - the box
        # disappears, the whole dojo is visible, the enso and the text float.
        # Drawn in `_paint_dnes_canvas`, driven by `_refresh_dnes_backdrop`.
        self.dnes_canvas = tk.Canvas(stred, highlightthickness=0, bd=0,
                                     bg=pal["bg"], takefocus=0)
        self.dnes_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.dnes_canvas.bind("<Button-1>", self._dnes_canvas_click)
        self.dnes_canvas.bind("<Motion>", self._dnes_canvas_motion)
        self.dnes_canvas.bind("<Leave>",
                              lambda _e: self._dnes_set_cursor(""))
        self._dnes_tk_imgs = {}      # holds ImageTk references (Tk drops them otherwise)
        self._dnes_hit = {}          # click zone: "enso" -> (x0,y0,x1,y1)
        self._dnes_cursor = ""
        self._dnes_fonts = {}
        # Persistent canvas items (dojo, enso) and signatures against needless
        # redrawing - a new page starts from scratch (the old canvas is
        # destroyed).
        self._dnes_items = None
        self._dnes_frame_sig = None
        self._dnes_text_sig = None
        self._dnes_cur_dojo = None
        self._dnes_cur_pil = None
        self._dnes_titul = ""
        self._dnes_veta = ""
        self._dnes_lastcue_text = ""
        # A new page (also after a language change): the sentence about
        # learning is written anew in the new language and the empty state
        # (`_sync_dnes_prazdny_stav`) is set up on the new widgets - the old
        # flags belonged to the destroyed page.
        self._dnes_learning_text = ""
        self._dnes_learning_key = None
        self._dnes_ma_tep_stav = None

        # The MARK (残 in the enso) + the state toggle. It is NO LONGER a
        # widget but a drawing on the Canvas (`ui_shell._EnsoHero`). The API
        # stays the same, so the alias `sidebar.enso`,
        # `_apply_listening_visuals`, `_set_enso_armed` and the harness
        # (`enso._live`/`_armed`) work unchanged. The toggle lives in the bar
        # (`ui_kit.KamaeBar`); the enso is what gets read, and a click on it
        # toggles.
        self.enso = ui_shell._EnsoHero(pal, size=self.ENSO_SIZE,
                                       on_change=self._on_enso_change)
        try:
            if getattr(self, "zanshin_graduated", False):
                self.enso.graduate()   # already graduated - the enso stays a golden moon
        except Exception:
            app_log.exception("promocia: obnova mesiaca pri starte zlyhala")
        # The enso breathes EXACTLY with the breathing line in the header -
        # one window, one rhythm. See `KamaeBar.phase()`.
        try:
            self.enso.set_phase_source(self.kamae.phase)
        except Exception:
            app_log.exception("enso: napojenie na dych zlyhalo")

        self._build_dnes_backdrop(stred, pal)   # scrim + <Configure>
        # FILL IT RIGHT AWAY. Otherwise the text is written only from
        # `_apply_listening_visuals` and `_set_enso_armed`, and neither runs
        # while the window is built - after a fresh start the mark would stand
        # over an empty space.
        self._refresh_dnes_state_text()
        self._refresh_dnes_backdrop(force=True)

        # --- heart rate and load (details, below the state) ---
        hr_panel = ui_kit.Panel(body, pal, title=tr("dnes.hr_title"))
        hr_panel.pack(fill="x", pady=(16, 0))
        self.hr_panel = hr_panel

        # The heart-rate number and its sentence are in one frame: before the
        # first session with heart rate the whole frame is hidden (a big "--"
        # would be just another faked measurement) - see
        # `_sync_dnes_prazdny_stav`.
        bpm_box = ctk.CTkFrame(hr_panel.body, fg_color="transparent")
        bpm_box.pack(fill="x")
        self.dnes_bpm_box = bpm_box
        bpm_row = ctk.CTkFrame(bpm_box, fg_color="transparent")
        bpm_row.pack(fill="x")
        self.dnes_bpm = ctk.CTkLabel(bpm_row, text="--", font=ui_kit.display(40),
                                     text_color=pal["text"])
        self.dnes_bpm.pack(side="left")
        ctk.CTkLabel(bpm_row, text=tr("dnes.bpm_unit"), font=ui_kit.ui(11),
                     text_color=pal["text_faint"]).pack(side="left", padx=(9, 0),
                                                        pady=(14, 0))
        # "so the user knows": a sentence by the number + an expandable
        # "what it means"
        self.dnes_info_bpm = self._metric_info(bpm_box, pal, "bpm")
        self.dnes_info_bpm.pack(fill="x", pady=(2, 0))

        # the "live" elements (curve, load) are in one frame, which is hidden
        # without a watch and replaced by the empty state (dnes_empty) -
        # otherwise both would not fit in the compact window, and an empty
        # curve says nothing
        live = ctk.CTkFrame(hr_panel.body, fg_color="transparent")
        self.dnes_live = live
        self.dnes_spark = ui_kit.Sparkline(live, pal, height=62)
        self.dnes_spark.pack(fill="x", pady=(10, 0))

        load_row = ctk.CTkFrame(live, fg_color="transparent")
        load_row.pack(fill="x", pady=(16, 5))
        ctk.CTkLabel(load_row, text=tr("hud.load"), font=ui_kit.ui(12),
                     text_color=pal["text_dim"]).pack(side="left")
        self.dnes_zone = ctk.CTkLabel(load_row, text="—", font=ui_kit.ui(12),
                                      text_color=pal["text_faint"])
        self.dnes_zone.pack(side="right")
        self.dnes_load = ui_kit.SegmentBar(live, pal)
        self.dnes_load.pack(fill="x")
        self.dnes_info_load = self._metric_info(live, pal, "load", wrap=360)
        self.dnes_info_load.pack(fill="x", pady=(9, 0))

        # --- session trace ---
        # The curve above this is a live window of the last three minutes. This
        # is the whole evening: where heart rate jumped, how long it stayed
        # there and when the app started the breathing. Until then a session
        # could only be read in History, and even there only as a row of
        # numbers.
        ui_kit.linka(live, pal).pack(fill="x", pady=(14, 0))
        trace_head = ctk.CTkFrame(live, fg_color="transparent")
        trace_head.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(trace_head, text=tr("dnes.trace_title"), font=ui_kit.ui(12),
                     text_color=pal["text_dim"]).pack(side="left")
        self.dnes_trace_meta = ctk.CTkLabel(trace_head, text="", font=ui_kit.mono(10),
                                            text_color=pal["text_faint"])
        self.dnes_trace_meta.pack(side="right")
        self.dnes_trace = ui_kit.SessionTrace(live, pal, height=88)
        self.dnes_trace.pack(fill="x", pady=(4, 0))
        live.pack(fill="x")

        # EMPTY STATE (0.3 batch 4, `ui_kit.EmptyState`): while no heart rate
        # is coming in, one sentence and one action - "Pair your watch" (opens
        # the pairing guide and switches on heart-rate receiving,
        # `open_watch_pairing`). Before 0.3 there was also a dimmed HUD preview
        # here with a made-up heart rate of 72 and a heading above the
        # sentence - the preview faked a measurement and the heading repeated
        # the panel's heading. It hides once connected (_refresh_dnes_stats).
        self.dnes_empty = ui_kit.EmptyState(
            hr_panel.body, pal, tr("dnes.empty_body"), action=tr("dnes.empty_btn"),
            command=self.open_watch_pairing)
        # which of the pair (live / empty) is visible is handled by
        # _refresh_dnes_stats

        # "My stats" - a configurable 2x2 grid (replaces the original fixed
        # 7-row StatList). "✎ edit" opens a popup with all the metrics, at most
        # 4 can be chosen (DASHBOARD_MAX_CARDS); both the choice and the order
        # are saved to settings (self.dashboard_stats).
        stats_wrap = ctk.CTkFrame(cols, fg_color="transparent")
        stats_wrap.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        # --- quick HUD toggle (heart rate in game) ---
        # Top right, right at hand: turn the heart-rate widget on/off without
        # going to Settings. Whether the player has it on affects the result
        # (biofeedback - a heart rate you can see gets regulated
        # subconsciously), so it is worth keeping it in sight.
        # ⚙ next to it opens the full HUD settings (Settings -> General, the
        # heart-rate panel section) - before 0.3 it led to the In-game page,
        # where the HUD is not.
        hud_row = ctk.CTkFrame(stats_wrap, fg_color="transparent")
        hud_row.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(hud_row, text=tr("hud.quick_label").upper(), font=ui_kit.ui(11, "bold"),
                     text_color=pal["text_faint"], anchor="w").pack(side="left")
        ctk.CTkButton(
            hud_row, text="⚙︎", width=26, height=26, corner_radius=ui_kit.RADIUS_CONTROL,
            fg_color="transparent", hover_color=pal["surface_alt"],
            text_color=pal["text_dim"], font=ui_kit.ui(13),
            command=self.show_hud_settings).pack(side="right")
        self.hud_quick_var = tk.BooleanVar(value=self.hud_config["enabled"])
        ui_kit.switch(
            hud_row, pal, variable=self.hud_quick_var,
            command=lambda: self.on_hud_config_change(
                enabled=self.hud_quick_var.get())).pack(side="right", padx=(0, 8))

        # The header and the card grid are hidden before the first session with
        # heart rate - four cards with dashes say nothing
        # (`_sync_dnes_prazdny_stav`).
        stats_head = ctk.CTkFrame(stats_wrap, fg_color="transparent")
        stats_head.pack(fill="x", pady=(0, 10))
        self.dnes_stats_head = stats_head
        ctk.CTkLabel(stats_head, text=tr("dashboard.stats_title").upper(),
                     font=ui_kit.ui(11, "bold"), text_color=pal["text_faint"],
                     anchor="w").pack(side="left")
        self.dashboard_edit_btn = ctk.CTkButton(
            stats_head, text=tr("dashboard.edit_stats"), height=22, corner_radius=ui_kit.RADIUS_CONTROL,
            fg_color="transparent", hover_color=pal["surface_alt"],
            text_color=pal["accent_hover"], font=ui_kit.ui(11),
            command=self._open_dashboard_picker)
        self.dashboard_edit_btn.pack(side="right")
        self.dashboard_grid = ctk.CTkFrame(stats_wrap, fg_color="transparent")
        self.dashboard_grid.pack(fill="x")
        self.dashboard_grid.grid_columnconfigure(0, weight=1, uniform="dstat")
        self.dashboard_grid.grid_columnconfigure(1, weight=1, uniform="dstat")
        self.dashboard_cards = {}
        self._rebuild_dashboard_stats_grid()

        # --- where you were today ---
        # Below the card grid half the column stayed empty. Meanwhile the app
        # has computed `zone_seconds` from the start and showed them nowhere -
        # four numbers that say more about a session than any single one.
        zone_panel = ui_kit.Panel(stats_wrap, pal, title=tr("dnes.zones_title"))
        zone_panel.pack(fill="both", expand=True, pady=(12, 0))
        self.dnes_zone_panel = zone_panel
        # The strip, the rows and the sentence below them are in one frame -
        # before the first session with heart rate it is replaced by a single
        # sentence (`dnes_zone_empty`): four rows of "0 %" looked like a
        # measurement, not like "nothing yet".
        zone_obsah = ctk.CTkFrame(zone_panel.body, fg_color="transparent")
        zone_obsah.pack(fill="x")
        self.dnes_zone_obsah = zone_obsah
        self.dnes_zone_empty = ui_kit.EmptyState(
            zone_panel.body, pal, tr("dnes.zones_empty"), wraplength=260)
        self.dnes_zone_bar = ui_kit.ZoneBar(zone_obsah, pal)
        self.dnes_zone_bar.pack(fill="x", pady=(0, 10))
        self.dnes_zone_rows = {}
        # Name on the left, SHARE on the right - and nothing in between. Up
        # to 2.1 there was also a coloured dot and a time ("0:00   65 %"). The
        # dot repeated the colour of the strip, which is right above the rows
        # and in the same order, and the time said the same as the share, just
        # differently. Four rows of three values each turned the panel into a
        # table; it should be one glance.
        for zone in ui_kit.ZoneBar.ORDER:
            row = ctk.CTkFrame(zone_obsah, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=tr(f"metric.zones.{zone}"), font=ui_kit.ui(11),
                         text_color=pal["text_dim"], anchor="w").pack(side="left")
            value = ctk.CTkLabel(row, text="0 %", font=ui_kit.mono(11),
                                 text_color=pal["text_faint"], anchor="e")
            value.pack(side="right")
            self.dnes_zone_rows[zone] = value
        self.dnes_zone_note = ctk.CTkLabel(
            zone_obsah, text=tr("dnes.zones_hint"), font=ui_kit.ui(10),
            text_color=pal["text_faint"], anchor="w", justify="left", wraplength=280)
        self.dnes_zone_note.pack(fill="x", pady=(10, 0))
        # Which of the pair (zones / sentence) and whether the cards are
        # visible is handled by `_sync_dnes_prazdny_stav` (from
        # `_refresh_dnes_stats`).

        # --- journal ---
        log_panel = ui_kit.Panel(body, pal)
        log_panel.pack(fill="x", pady=(16, 0))
        log_head = ctk.CTkFrame(log_panel.body, fg_color="transparent")
        log_head.pack(fill="x")
        self.session_label = ctk.CTkLabel(log_head, text=self._session_text(),
                                          text_color=pal["text_faint"],
                                          font=ui_kit.mono(10))
        self.session_label.pack(side="right", padx=(8, 0))
        self.log_toggle_btn = ctk.CTkButton(
            log_head, text=self._log_toggle_text(), fg_color="transparent",
            hover_color=pal["surface_alt"], text_color=pal["text_dim"], anchor="w",
            height=26, corner_radius=ui_kit.RADIUS_CONTROL, font=ui_kit.ui(12), command=self.toggle_log)
        self.log_toggle_btn.pack(side="left", fill="x", expand=True)

        self.log_body = ctk.CTkFrame(log_panel.body, fg_color="transparent")
        self.log_text = ctk.CTkTextbox(self.log_body, height=110, corner_radius=ui_kit.RADIUS_CONTROL,
                                       fg_color=pal["entry_bg"],
                                       text_color=pal["text_dim"],
                                       font=ui_kit.mono(10))
        self.log_text.pack(fill="both", expand=True, pady=(8, 0))
        self.log_text.configure(state="disabled")
        if not self.log_collapsed:
            self.log_body.pack(fill="x")

        # "Why it works" - one sentence below everything, with a link to the
        # Guide. Deliberately inconspicuous: whoever knows it does not read it;
        # whoever is not sure the app is not just a placebo is one click away
        # from the science behind it.
        why = ctk.CTkFrame(body, fg_color="transparent")
        why.pack(fill="x", pady=(14, 0))
        ctk.CTkLabel(why, text=tr("dnes.why_line"), font=ui_kit.ui(11),
                     text_color=pal["text_faint"], anchor="w",
                     justify="left", wraplength=560).pack(side="left")
        ctk.CTkButton(why, text=tr("dnes.why_link"), height=24, corner_radius=ui_kit.RADIUS_CONTROL,
                      fg_color="transparent", hover_color=pal["surface_alt"],
                      text_color=pal["accent_hover"], font=ui_kit.ui(11),
                      command=self.open_guide_panel).pack(side="left", padx=(6, 0))

        self._refresh_dnes_stats()

    def _icon_image(self, name, size):
        """A pictogram from `hud_paint` as a CTkImage for a button.

        The references are kept in a list - a CTkImage without a reference
        gets deleted by the garbage collector and the button is left
        without an icon.
        """
        try:
            img = hud_paint.render_slot_icon(name, size, hud_paint.Style(self.pal))
            photo = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
        except Exception:
            return None
        if not hasattr(self, "_button_icons"):
            self._button_icons = []
        self._button_icons.append(photo)
        return photo

    # ---------- Settings and In-game pages ----------

    def _build_spustace_page(self, page, pal):
        """Cues (key "spustace", once called Triggers): the profile, sharing
        it, the cue cards and the guide below them.

        The page is no longer called "Profiles" - the profile is the
        mechanism, the cue is what the user really sets. The profile
        stays, it just stopped being the name of the whole page.
        """
        # ONE SCROLL FOR THE WHOLE PAGE.
        #
        # Until 18. 9. only the slot list scrolled (a nested
        # CTkScrollableFrame) and the rest of the page stood still. That had
        # two drawbacks: nothing could be put below the slots (explanations,
        # theory), and `before=self.slots_container` failed with a TclError,
        # because a compound widget is not managed by pack - a silent error
        # that was only written to crash.log.
        #
        # Now the whole thing scrolls and `slots_container` is a plain frame
        # that `rebuild_slots` empties without any problem.
        wrap = ui_kit.stranka_scroll(page, pal)
        wrap.pack(fill="both", expand=True, padx=ui_kit.PAGE_GUTTER, pady=(20, 20))
        self.spustace_scroll = wrap

        ctk.CTkLabel(wrap, text=tr("slots.title"), font=ui_kit.ui(17, "bold"),
                     text_color=pal["text"], anchor="w").pack(fill="x")
        ctk.CTkLabel(wrap, text=tr("slots.hint"), font=ui_kit.ui(11),
                     text_color=pal["text_dim"], wraplength=680, anchor="w",
                     justify="left").pack(fill="x", pady=(3, 0))

        self._build_citlivost_card(wrap, pal)

        # --- profile bar ---
        bar = ctk.CTkFrame(wrap, fg_color=pal["surface"], corner_radius=ui_kit.RADIUS_CONTROL,
                           border_width=1, border_color=pal["line_soft"])
        bar.pack(fill="x", pady=(16, 14))
        inner = ctk.CTkFrame(bar, fg_color="transparent")
        # padx 16 like the panel body and the cue cards below the bar - at 14
        # the bar's content started 2 px (3 px at 150 %) to the left of them.
        inner.pack(fill="x", padx=16, pady=11)

        self.profile_var = tk.StringVar(value=self.active_profile_name)
        self.profile_switch = ui_kit.option_menu(
            inner, pal, width=200, values=[p["name"] for p in self.profiles],
            variable=self.profile_var, command=self.on_profile_switch)
        self.profile_switch.pack(side="left", padx=(0, 6))

        # Secondary profile actions as secondary buttons (border >= 3:1),
        # without the emoji from the translation (`bez_ikony`). Delete is NOT
        # right next to "+ New" - it stands as a destructive action at the end
        # of the row, so it cannot be hit by mistake when creating a profile.
        for text, command in ((tr("profile.new"), self.new_profile_dialog),
                              (ui_kit.bez_ikony(tr("profile.export")), self.export_profile_code),
                              (ui_kit.bez_ikony(tr("profile.import")), self.import_profile_dialog)):
            ui_kit.button(inner, pal, text, command=command,
                          height=28).pack(side="left", padx=3)
        ui_kit.button(inner, pal, tr("profile.delete"), kind="danger", width=28,
                      height=28, command=self.delete_current_profile).pack(side="right")

        self.auto_profile_var = tk.BooleanVar(value=self.auto_profile_enabled)
        auto_text = tr("settings.auto_profile") if PSUTIL_AVAILABLE \
            else tr("settings.auto_profile_unavailable")
        # Its own row below the profiles: the sentence under the switch says
        # which games the app knows, that it starts and stops listening by
        # itself, and that when off it does not read processes - it would not
        # fit next to the four profile buttons.
        auto_row = ctk.CTkFrame(bar, fg_color="transparent")
        auto_row.pack(fill="x", padx=16, pady=(0, 11))
        auto_switch = ui_kit.switch(auto_row, pal, text=auto_text,
                                    variable=self.auto_profile_var,
                                    font=ui_kit.ui(11),
                                    command=self.on_auto_profile_toggle)
        auto_switch.pack(anchor="w")
        if not PSUTIL_AVAILABLE:
            auto_switch.configure(state="disabled")
        else:
            ctk.CTkLabel(auto_row, text=tr("settings.auto_profile_sub",
                                           games=self._zname_hry()),
                         font=ui_kit.ui(10), text_color=pal["text_faint"],
                         wraplength=640, anchor="w", justify="left").pack(
                fill="x", pady=(4, 0))

        # --- trigger map ---
        # PHASE 3: the gamepad button legend (A=X, B=O, ...) was here because a
        # cue could be triggered with a button. It no longer can - the
        # controller only reports that the player is active. The key
        # `slots.gamepad_hint` in i18n stays until the page is redrawn in
        # phase 5.
        #
        # THE "+ Add trigger" BUTTON IS NO LONGER HERE (0.2). Cues have four
        # fixed categories (Grounding, Jaw, Release, Breath) - each with its
        # own in-game visual. A fifth or further slot had no visual or
        # category, so `_dalsi_cue_slot` skipped it and it never sounded on its
        # own; meanwhile the log promised the player that "the app decides by
        # itself when it speaks up".
        # Old settings with more than four slots still load (nothing is
        # deleted) - the extra slots sound only via the Test button.

        # --- bulk-selection bar (hidden until something is selected) ---
        # It only appears when the player ticks at least one slot - otherwise
        # an empty strip would hang permanently above the list. Removing
        # several slots at once is one action with one confirmation, not
        # clicking one by one.
        self.bulk_bar = ctk.CTkFrame(wrap, fg_color=pal["surface_alt"],
                                     corner_radius=ui_kit.RADIUS_CONTROL, border_width=1,
                                     border_color=pal["line_soft"], height=44)
        self.bulk_bar.pack_propagate(False)
        bulk_inner = ctk.CTkFrame(self.bulk_bar, fg_color="transparent")
        bulk_inner.pack(fill="both", expand=True, padx=14, pady=6)
        self.bulk_label = ctk.CTkLabel(bulk_inner, text="", font=ui_kit.ui(12),
                                       text_color=pal["text"], anchor="w")
        self.bulk_label.pack(side="left")
        ui_kit.button(bulk_inner, pal, tr("slots.remove_selected"), kind="danger",
                      height=28, font=ui_kit.ui(11),
                      command=self.remove_selected_slots).pack(side="right")
        ui_kit.button(bulk_inner, pal, tr("slots.clear_selection"), kind="quiet",
                      height=28, font=ui_kit.ui(11),
                      command=self.clear_slot_selection).pack(side="right", padx=(0, 8))
        # NOT packed - pack only in _on_slot_selection_change

        # The anchor the bar is inserted before. `before=` must point to a
        # widget that IS managed by pack - and CTkScrollableFrame is not:
        # outwardly it is a compound widget and only its inner frame is packed.
        # `before=self.slots_container` therefore raised a TclError and the bar
        # never showed (the error was only silently written to crash.log, the
        # app kept running).
        self._bulk_anchor = ctk.CTkFrame(wrap, fg_color="transparent", height=0)
        self._bulk_anchor.pack(fill="x")

        self.slots_container = ctk.CTkFrame(wrap, fg_color="transparent")
        self.slots_container.pack(fill="x", pady=(10, 0))
        active_profile = next(
            (p for p in self.profiles if p["name"] == self.active_profile_name),
            self.profiles[0])
        self.rebuild_slots(active_profile["slots"])

        # THE EXPLANATIONS AND THEORY BELONG HERE, not two tabs further on.
        # People look for them exactly when they are reading what each cue
        # says - "why the jaw of all things" is asked at the jaw.
        # A gap, not a line (0.3, UX audit, batch 4): a 1 px line lay right
        # above the border of the Guide card - two lines on top of each other.
        ctk.CTkFrame(wrap, fg_color="transparent", height=16).pack(fill="x")
        self._build_guide_into(wrap, pal)

    def _build_zvuk_page(self, page, pal):
        """Sound: the voice (who speaks, with what voice, how fast), volume
        (+ the sound/voice mix) and timing (pause, overlap).

        This was the only settings page that survived the redesign
        unchanged: a bare grid of `CTkLabel` + slider, without a single
        explanation and without grouping. Yet exactly here are the options
        for which a name is not enough - neither "Sound ↔ voice mix" nor
        "Cues may overlap" can be understood from two words. Now it is
        made of `ui_kit.SettingRow` like the rest of the app (name, a
        sentence below it, the control on the right) in three panels, and
        at the end a button that lets you really hear it - a voice cannot
        be chosen by its name.
        """
        wrap = ui_kit.stranka_scroll(page, pal)
        wrap.pack(fill="both", expand=True, padx=ui_kit.PAGE_GUTTER, pady=(20, 20))
        self.zvuk_scroll = wrap

        # The explanations have a lot of room on this page (the controls are
        # narrow), so a wider wrap than the default 430 - otherwise every
        # sentence would take three lines and the page would be twice as long.
        WRAP = 560

        # The slider block (slider + value label) is exactly `ui_kit.CONTROL_W`
        # wide, like the dropdowns above it, and the label is right-aligned -
        # so all the page's controls end on one right edge (audit: the
        # dropdowns ended ~110 px further than the sliders).
        HODNOTA_W = 96
        SLIDER_W = ui_kit.CONTROL_W - HODNOTA_W - 10

        def _slider(parent, **kw):
            """Slider + a value label to its right. The mouse wheel is
            deliberately blocked: the page scrolls, and without this
            scrolling would change the value the cursor is resting on."""
            box = ctk.CTkFrame(parent, fg_color="transparent")
            # one slider style across the whole app (`ui_kit.slider`)
            slider = ui_kit.slider(box, pal, width=SLIDER_W, **kw)
            slider.pack(side="left")
            return box

        def _hodnota(box, text):
            """The value label. It also has a word in it ("balanced", "slow"),
            because a bare "5.0 s" does not say whether that is a lot or
            a little. A longer translation stretches the label to the
            left, the right edge stays."""
            label = ctk.CTkLabel(box, text=text, text_color=pal["text_dim"],
                                 width=HODNOTA_W, font=ui_kit.ui(11), anchor="e")
            label.pack(side="left", padx=(10, 0))
            return label

        # --- voice ---
        # NOTE: above it there used to be a separate untitled panel just for
        # the "How I speak up" row. It is now the first row of the Loudness
        # panel (0.3, UX audit, batch 4: a card for one sentence = a frame
        # without content).
        voice_panel = ui_kit.Panel(wrap, pal, title=tr("settings.audio_voice_title"))
        voice_panel.pack(fill="x")

        row = ui_kit.SettingRow(voice_panel.body, pal, tr("settings.engine"),
                                tr("settings.engine_sub"), wrap=WRAP)
        self.engine_var = tk.StringVar(value=engine_labels()[self.engine])
        self.engine_box = ui_kit.option_menu(
            row.control, pal,
            values=[engine_labels()[ENGINE_EDGE], engine_labels()[ENGINE_SAPI]],
            variable=self.engine_var,
            command=lambda _v: self.on_engine_change())
        self.engine_box.pack()
        # Status of the Edge cue preparation - it belongs below the engine
        # switch, not next to it: it is a progress message, not another
        # setting. Since 0.3 batch 4b it is INSIDE the "Voice source" row
        # (below its explanation, `SettingRow.text_col`): below the panel it
        # lay only after the dividing line, so it looked like the start of the
        # "Voice" row. It is packed only when it has something to say
        # (`set_edge_status`) - an empty label would be a row of blank space.
        self.edge_status_label = ctk.CTkLabel(
            row.text_col, text="", font=ui_kit.ui(10), text_color=pal["text_dim"],
            anchor="w", justify="left", wraplength=WRAP)
        # "Try again" (0.3): shown only below a failed voice preparation
        # (`_edge_priprava_zlyhala`, app_audio.py); while watching,
        # `pregenerate` postpones it until after the game anyway.
        self.edge_retry_btn = ui_kit.button(
            row.text_col, pal, tr("common.retry"), command=self.skus_hlas_znova,
            height=28)
        # "Update voice" (0.3, the author's decision 15. 11. 2026): when
        # Microsoft changes something that only a newer edge-tts fixes, the
        # player downloads it themselves - only on a click, never by itself and
        # never while watching (`aktualizuj_hlas`, app_audio.py; PRIVACY.md). A
        # quiet button: a helper action, not a setting. The row is below the
        # status and "Try again" and is only visible with the natural voice
        # (`_obnov_aktualizaciu_hlasu`). The link to the official releases next
        # to it shows only when it takes a new Zanshin to fix the voice; a
        # chip, because it is an external link (opens the browser).
        rad = ctk.CTkFrame(row.text_col, fg_color="transparent")
        self.edge_update_row = rad
        self.edge_update_btn = ui_kit.button(
            rad, pal, tr("edge.update.btn"), kind="quiet",
            command=self.aktualizuj_hlas, height=28)
        self.edge_update_btn.pack(side="left")
        odkaz = ui_kit.chip(rad, pal, "↗ " + tr("edge.update.releases_btn"),
                            self.otvor_vydania_zanshinu)
        self.edge_releases_btn = odkaz
        self._obnov_aktualizaciu_hlasu()
        if self._aktualizacia_hlasu_bezi:
            # window rebuild (language, theme) in the middle of an update: the
            # status comes back, the result then overwrites it
            self.set_edge_status(tr("edge.update.running"), pal["warn"])

        row = ui_kit.SettingRow(voice_panel.body, pal, tr("settings.voice"),
                                tr("settings.voice_sub"), wrap=WRAP)
        self.voice_var = tk.StringVar()
        self.voice_box = ui_kit.option_menu(
            row.control, pal, values=[tr("voice.loading")], variable=self.voice_var,
            command=lambda _v: self.on_voice_change())
        self.voice_box.pack()

        row = ui_kit.SettingRow(voice_panel.body, pal, tr("settings.rate"),
                                tr("settings.rate_sub"), wrap=WRAP)
        self.rate_var = tk.IntVar(value=self.rate_value)
        box = _slider(row.control, from_=-10, to=10, number_of_steps=20,
                      variable=self.rate_var, command=lambda _v: self.on_rate_change())
        self.rate_value_label = _hodnota(box, self._rate_label_text())
        box.pack()

        # --- volume ---
        loud_panel = ui_kit.Panel(wrap, pal, title=tr("settings.audio_volume_title"))
        loud_panel.pack(fill="x", pady=(14, 0))

        # --- how I speak up (cue style, 0.2) ---
        # The same question as in step 5 of onboarding, with the same
        # sentences. It is the volume ceiling (voice > sound > picture), hence
        # the first row of the Loudness panel - it decides whether anything
        # from the rows below it sounds in-game at all. "Not sure" is not
        # here - in onboarding it means voice.
        row = ui_kit.SettingRow(loud_panel.body, pal, tr("settings.cue_style"),
                                tr("settings.cue_style_sub"), wrap=WRAP)
        self.cue_style_var = tk.StringVar(
            value=self._cue_style_label(getattr(self, "cue_style", None)))
        ui_kit.option_menu(
            row.control, pal, values=self._cue_style_labels(),
            variable=self.cue_style_var,
            command=self._on_cue_style_label).pack()

        row = ui_kit.SettingRow(loud_panel.body, pal, tr("settings.volume"),
                                tr("settings.volume_sub"), wrap=WRAP)
        self.volume_var = tk.IntVar(value=self.volume_value)
        box = _slider(row.control, from_=0, to=100, number_of_steps=100,
                      variable=self.volume_var, command=lambda _v: self.on_volume_change())
        self.volume_value_label = _hodnota(box, f"{self.volume_value} %")
        box.pack()

        row = ui_kit.SettingRow(loud_panel.body, pal, tr("settings.balance"),
                                tr("settings.balance_sub"), wrap=WRAP)
        self.balance_var = tk.IntVar(value=self.balance_value)
        box = _slider(row.control, from_=0, to=100, number_of_steps=100,
                      variable=self.balance_var, command=lambda _v: self.on_balance_change())
        self.balance_value_label = _hodnota(box, self._balance_label_text())
        box.pack()

        # The sentence below the preview follows the cue style - the "How I
        # speak up" option above rewrites it too (`_nastav_styl_hlasky`).
        row = ui_kit.SettingRow(loud_panel.body, pal, tr("settings.preview"),
                                self._preview_sub_text(), wrap=WRAP)
        self.preview_sub_label = row.sub_label
        ui_kit.button(row.control, pal, tr("settings.preview_btn"),
                      command=self.preview_sound).pack(anchor="e")

        # NOTE: here used to be the "Timing" panel with a "Pause between cues"
        # slider (0.2-30 s) and a "Cues may overlap" switch.
        #
        # They were the biggest controls in the section and promised exactly
        # what the player is looking for - "a short pause reminds often, a long
        # one lets you play". Yet they had no effect at all on the automatic
        # cue: the gap between cues is handled by
        # `trigger.params["min_gap_s"]`, which has a hard floor of 210 s, i.e.
        # seven times the maximum of that slider. The player thought they had
        # tuned the app and changed nothing - and on top of that they were
        # working against the "How often I speak up" option, which really does
        # it.
        #
        # Both values stay as constants for a MANUAL trigger (the Test button,
        # a click in the HUD preview), where they make sense and nobody has to
        # set them.

        # --- restore recommended ---
        # The sliders can be twisted into a state you cannot get out of on your
        # own (volume 3 %, pause 30 s), without knowing what it was originally.
        # One button, no "really?" - all five values are visible right above it
        # and can be moved back by hand.
        # The last row of the Loudness panel, not a card of its own for one
        # sentence (audit: a card for one sentence = a frame without content).
        row = ui_kit.SettingRow(loud_panel.body, pal, tr("settings.audio_reset"),
                                tr("settings.audio_reset_sub"), wrap=WRAP)
        ui_kit.button(row.control, pal, tr("settings.audio_reset_btn"), kind="quiet",
                      command=self.reset_audio_settings).pack(anchor="e")

    def _rate_label_text(self):
        """Speech speed as "+3 · fast". A bare number -10..10 says neither
        the direction nor what it means - a sign and a word do."""
        value = self.rate_value
        if value <= -3:
            slovo = tr("settings.speed_slow")
        elif value >= 3:
            slovo = tr("settings.speed_fast")
        else:
            slovo = tr("settings.speed_normal")
        return f"{value:+d} · {slovo}" if value else f"0 · {slovo}"


    def reset_audio_settings(self):
        """Restores volume, mix, speed, pause and overlap to the
        recommended values (`settings_model.DEFAULT_AUDIO`).

        Neither the voice nor the engine changes - that is not a broken
        setting but a choice, and overwriting it behind the player's back
        would be a surprise, not help.
        """
        self.volume_var.set(DEFAULT_AUDIO["volume"])
        self.on_volume_change()
        self.balance_var.set(DEFAULT_AUDIO["balance"])
        self.on_balance_change()
        self.rate_var.set(DEFAULT_AUDIO["rate"])
        self.on_rate_change()
        self.log(tr("log.audio_reset"))

    # The sentence below "How it sounds" by cue style (decision of 24. 9.).
    PREVIEW_SUB = {rebrik.STYL_HLAS: "settings.preview_sub",
                   rebrik.STYL_ZVUK: "settings.preview_sub_sound",
                   rebrik.STYL_OBRAZ: "settings.preview_sub_visual"}

    def _preview_sub_text(self):
        """What the preview will really do - by the style the player chose."""
        styl = rebrik.normalize_cue_style(getattr(self, "cue_style", None))
        return tr(self.PREVIEW_SUB[styl])

    def preview_sound(self):
        """Plays the first enabled cue the way it sounds in-game in the
        chosen cue STYLE (`cue_style`, decision of 24. 9.):

          * voice   - `_emit` with sound and words, no visual (as before);
          * sound   - the slot's sound and its picture, no words (`bez_slov`);
          * picture - nothing sounds, only the picture.
        Previously the voice always sounded - even for a player who chose
        "only a picture, say nothing", and the sentence below the button
        promised them that this is exactly how it sounds in-game.

        A voice cannot be chosen by its name: "Natural voice (Edge)" and
        "Windows voice" are two phrases that say nothing about the result,
        and the same goes for the volume and the sound/voice mix. `_emit`
        is run with a real slot (not `fire_slot`), so the preview is NOT
        counted in the session.
        """
        styl = rebrik.normalize_cue_style(getattr(self, "cue_style", None))
        if styl == rebrik.STYL_HLAS:
            slot = next((s for s in self.slots if s.enabled_value), None)
            if slot is None and self.slots:
                slot = self.slots[0]
            if slot is None:
                return
            threading.Thread(target=self._emit, args=(slot,), daemon=True).start()
            return
        # Sound and picture: in these styles the picture is the whole cue (or
        # half of it), so the preview shows it. This runs on the Tk thread (a
        # click). The slot is taken as in-game (`_dalsi_cue_slot`): enabled AND
        # with the in-game picture enabled. The first enabled slot without a
        # picture would show nothing after the click and in "only a picture"
        # would not play anything either - the button would stay silent and the
        # sentence below it would promise a picture.
        slot = next((s for s in self.slots
                     if s.enabled_value and self._ma_obrazok_v_hre(s)), None)
        if slot is None:
            # In-game it would not speak up at all in this style
            # (`_dalsi_cue_slot` returns None) - this is said plainly, not with
            # a silent click.
            self.log(tr("log.preview_no_picture"))
            return
        try:
            self.overlay_manager.trigger(slot.index)
        except Exception:
            app_log.exception("ukazka: obrazok sa nepodarilo ukazat")
        if styl == rebrik.STYL_ZVUK:
            threading.Thread(target=self._emit, args=(slot,),
                             kwargs={"bez_slov": True}, daemon=True).start()

    def _ma_obrazok_v_hre(self, slot):
        """Does the slot have the in-game picture enabled? The same condition
        as in `_dalsi_cue_slot` - without it the cue is not delivered
        in-game at all."""
        try:
            return bool(self.overlay_configs[int(slot.index)]["enabled"])
        except (AttributeError, IndexError, KeyError, TypeError, ValueError):
            return False

    def _build_vhre_page(self, page, pal):
        """Watch: pair it and see what the app draws from it into the game.

        Until 18. 9. EVERYTHING the app does during play was here - feature
        icons, screen choice, the in-game language, the heart-rate panel
        and the anti-cheat explanation. It was six sections one below the
        other, and the card people come here for - pairing the watch - got
        lost among them.

        Two things remained, and both are about the same thing: the sensor
        and what of it is visible on screen. The rest moved, collapsed,
        into the General settings (`_build_ingame_sections_into`) - these
        are things you set once and never come back to.
        """
        scroll = ui_kit.stranka_scroll(page, pal)
        scroll.pack(fill="both", expand=True, padx=ui_kit.PAGE_GUTTER, pady=(20, 20))
        self.vhre_scroll = scroll

        # Pairing comes first: without a watch the widget has nothing to draw.
        self._build_heart_rate_card(scroll, pal, pady=(0, 0))

        # --- slot visuals ---
        vis_panel = ui_kit.Panel(scroll, pal, title=tr("overlay.dialog_title"))
        vis_panel.pack(fill="x", pady=(14, 0))
        ctk.CTkLabel(vis_panel.body, text=tr("overlay.drag_hint"), font=ui_kit.ui(10),
                     text_color=pal["text_faint"], wraplength=440, anchor="w",
                     justify="left").pack(fill="x", pady=(0, 8))
        self.vhre_vis_switches = []
        self.vhre_test_buttons = {}
        vizualy = ("grounding", "jaw", "release", "breath")
        for index in range(4):
            cfg = self.overlay_configs[index]
            # The icon is THE SAME picture the player will see in-game
            # (`ui_kit.SlotIcon` -> `hud_paint.render_slot_icon`), not the
            # emoji from the translation - 🥾 💀 🖱️ never show in-game, and the
            # skull was the loudest symbol of a quiet app. The column has a
            # fixed width, so the names start on one vertical line.
            title = ui_kit.bez_ikony(tr(f"overlay.slot.{index}"))
            row = ui_kit.SettingRow(vis_panel.body, pal, title,
                                    icon_slot=vizualy[index])
            if index == 0:
                self.vhre_slot_rows = []
            self.vhre_slot_rows.append(row)
            test_btn = ui_kit.button(
                row.control, pal, tr("overlay.test"), height=26, font=ui_kit.ui(11),
                command=lambda i=index: self.toggle_overlay_test(i))
            test_btn.pack(side="left", padx=(0, 6))
            self.vhre_test_buttons[index] = test_btn
            # the colour of this visual's pictogram (color picker)
            swatch = ctk.CTkButton(
                row.control, text="", width=26, height=26, corner_radius=ui_kit.RADIUS_CONTROL,
                fg_color=self._overlay_color(index), border_width=1,
                border_color=pal["border"], hover_color=self._overlay_color(index),
                command=lambda i=index: self.pick_overlay_color(i))
            swatch.pack(side="left", padx=(0, 8))
            self.vhre_color_swatches = getattr(self, "vhre_color_swatches", {})
            self.vhre_color_swatches[index] = swatch
            var = tk.BooleanVar(value=cfg["enabled"])
            ui_kit.switch(row.control, pal, variable=var,
                          command=lambda i=index, v=var: self.on_overlay_config_change(
                              i, enabled=v.get())).pack(side="left")
            self.vhre_vis_switches.append(var)

        # Natural width, not across the whole card: a button ~1500 px wide
        # shouted louder than the list of visuals it fine-tunes.
        ui_kit.button(vis_panel.body, pal, tr("overlay.fine_tune"),
                      command=self.open_overlay_settings).pack(anchor="w", pady=(12, 0))

    def _build_ingame_sections_into(self, parent, pal):
        """Four sections moved from the watch page to General.

        They are COLLAPSED on purpose. The in-game icons, the screen, the
        in-game language and the heart-rate panel are set once at first
        start; the anti-cheat text is read once. Expanded, they would make
        General the longest page in the app, one you scroll through to get
        to the theme and language.
        """
        # --- monitor ---
        mon_panel = ui_kit.Collapsible(parent, pal,
                                       title=tr("overlay.monitor.label"))
        mon_panel.pack(fill="x", pady=(10, 0))
        # --- language of what is visible IN THE GAME ---
        # Separate from the window language on purpose: the HUD at the bottom
        # left and the labels below the visuals end up on stream and in store
        # screenshots, where they are also read by people who do not know the
        # UI language. Hence English by default, even when the app runs in
        # Slovak.
        row = ui_kit.SettingRow(mon_panel.body, pal, tr("settings.game_lang"),
                                tr("settings.game_lang_sub"), wrap=520)
        self.game_lang_var = tk.StringVar(value=self._game_lang_label(self.game_lang))
        ui_kit.option_menu(
            row.control, pal, values=[tr("settings.game_lang_same")]
            + list(LANG_NATIVE_LABELS.values()),
            variable=self.game_lang_var,
            command=self.on_game_lang_change).pack()

        row = ui_kit.SettingRow(mon_panel.body, pal, tr("overlay.monitor.pick"),
                                tr("overlay.monitor.hint"))
        options = self.monitor_choices()
        self._monitor_labels = {label: value for label, value in options}
        current = next((label for label, value in options
                        if value == self.monitor_target), options[0][0])
        self.monitor_box = ui_kit.option_menu(
            row.control, pal, values=[label for label, _ in options],
            command=self._on_monitor_pick)
        self.monitor_box.set(current)
        self.monitor_box.pack()

        # --- HUD ---
        hud_panel = ui_kit.Collapsible(parent, pal,
                                       title=tr("hud.section_title"))
        hud_panel.pack(fill="x", pady=(10, 0))
        # ⚙ by "Heart rate in game" on Today jumps here and expands the section
        # (`show_hud_settings`).
        self.hud_section = hud_panel
        row = ui_kit.SettingRow(hud_panel.body, pal, tr("hud.enable"), tr("hud.hint"))
        ui_kit.button(row.control, pal, tr("hud.test"), height=26, font=ui_kit.ui(11),
                      command=self.test_hud).pack(side="left", padx=(0, 8))
        self.hud_enabled_var = tk.BooleanVar(value=self.hud_config["enabled"])
        ui_kit.switch(row.control, pal, variable=self.hud_enabled_var,
                      command=lambda: self.on_hud_config_change(
                          enabled=self.hud_enabled_var.get())).pack(side="left")

        # --- FEATURE ICONS: a subordinate option, not a separate section ---
        #
        # Until 19. 9. they had their own collapsed panel, and ABOVE the
        # heart-rate panel at that. But `hud.StatsHud` draws them inside the
        # heart-rate panel: while the panel is off, the icons switch does
        # nothing at all. The player turned on the top switch, nothing
        # happened, and they had no hint that they were missing a second one
        # two panels lower. It looked like a broken switch.
        #
        # Now they sit below their parent and while the panel is off they are
        # greyed out - then it is immediately clear what has to be turned on
        # first.
        ui_kit.linka(hud_panel.body, pal).pack(fill="x", pady=(12, 0))
        ctk.CTkLabel(hud_panel.body, text=tr("hud.trigger_row.sub"),
                     font=ui_kit.ui(10), text_color=pal["text_faint"],
                     wraplength=440, anchor="w", justify="left").pack(
            fill="x", pady=(10, 0))

        row = ui_kit.SettingRow(hud_panel.body, pal, tr("hud.trigger_row.toggle"))
        self.hud_trigger_var = tk.BooleanVar(value=self.hud_config["show_triggers"])
        self.hud_trigger_switch = ui_kit.switch(
            row.control, pal, variable=self.hud_trigger_var,
            command=lambda: self.on_hud_config_change(
                show_triggers=self.hud_trigger_var.get()))
        self.hud_trigger_switch.pack(side="left")

        color_row = ui_kit.SettingRow(hud_panel.body, pal, tr("hud.trigger_row.color"))
        self.hud_trigger_swatch = ctk.CTkButton(
            color_row.control, text="", width=26, height=26,
            corner_radius=ui_kit.RADIUS_CONTROL,
            fg_color=self._hud_trigger_color_display(), border_width=1,
            border_color=pal["border"], hover_color=self._hud_trigger_color_display(),
            command=self.pick_hud_trigger_color)
        self.hud_trigger_swatch.pack(side="left")
        self._sync_hud_trigger_state()

        for key, label, low, high, fmt in (
                ("scale", tr("overlay.scale"), 0.6, 2.0, "{:.2f}×"),
                ("opacity", tr("hud.opacity"), 0.25, 1.0, "{:.0%}")):
            row = ui_kit.SettingRow(hud_panel.body, pal, label)
            value_label = ctk.CTkLabel(row.control, text=fmt.format(self.hud_config[key]),
                                       width=52, font=ui_kit.mono(11),
                                       text_color=pal["text_dim"])
            value_label.pack(side="right", padx=(8, 0))
            var = tk.DoubleVar(value=self.hud_config[key])
            ui_kit.slider(row.control, pal, from_=low, to=high, variable=var, width=180,
                          number_of_steps=28,
                          command=lambda _v, k=key, v=var, lbl=value_label, f=fmt:
                              self._on_hud_slider(k, v, lbl, f)).pack(side="right")

        # --- anti-cheat ---
        #
        # It is PURE TEXT, no setting: what the app does and does not do
        # towards the game. You read it once, when deciding whether to run it
        # at all - hence collapsed, so it does not take up half the page
        # forever.
        safety = ui_kit.Collapsible(parent, pal, title=tr("safety.title"))
        safety.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(safety.body, text=tr("safety.body"), font=ui_kit.ui(11),
                     text_color=pal["text_dim"], wraplength=620, anchor="w",
                     justify="left").pack(fill="x")

    def _on_monitor_pick(self, label):
        self.on_monitor_target_change(self._monitor_labels.get(label, "auto"))

    def _on_hud_slider(self, key, var, label, fmt):
        value = round(float(var.get()), 3)
        try:
            label.configure(text=fmt.format(value))
        except Exception:
            pass
        self.on_hud_config_change(**{key: value})

    # NOTE: `_on_dojo_slider` and `_update_dojo_readout` used to be here - the
    # handler of the "Dojo background" slider and its live feedback (bands
    # off/subtle/medium/strong/full). They disappeared along with the photo
    # strip above the title bar, which was the only thing they controlled
    # (see the NOTE in `_build_ui`).

    def _build_citlivost_card(self, parent, pal):
        """What the app has computed about me. No switch any more.

        WHY THE SWITCH DISAPPEARED: it had three positions (less / normal /
        more) and the player had no way of knowing what each would do FOR
        THEM. Load is scaled against their own baseline, so the same number
        means something different for everyone - and measured on real data
        it turned out that the difference between the positions is smaller
        than the difference between two evenings.

        The app computes the threshold from its own sessions (the 80th
        percentile of load), just as it already computed the baseline and
        the high-heart-rate limit. Here it is only SHOWN.
        """
        # NO CARD (0.3, UX audit): a frame around a single sentence was a card
        # for nothing - the heading and the sentence stand directly on the
        # page, as an introduction above them.
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.pack(fill="x", pady=(18, 0))
        ctk.CTkLabel(panel, text=tr("cue_rate.title"), font=ui_kit.ui(13, "bold"),
                     text_color=pal["text"], anchor="w").pack(fill="x")
        self.citlivost_detail = ctk.CTkLabel(
            panel, text=self._citlivost_detail_text(), font=ui_kit.ui(11),
            text_color=pal["text_dim"], anchor="w", justify="left",
            wraplength=640)
        self.citlivost_detail.pack(fill="x", pady=(4, 0))
        return panel

    def _citlivost_detail_text(self):
        """The sentence is read FROM THE PARAMETERS, not from the translation -
        otherwise after the first change it would drift apart from what
        the app really does."""
        p = self.cue_trigger.params
        if getattr(self, "_prah_z_dat", None) is None:
            return tr("cue_rate.learning",
                      prah=f"{p['stress_threshold']:g}",
                      hold=f"{p['stress_hold_s']:g}")
        return tr("cue_rate.computed",
                  prah=f"{p['stress_threshold']:g}",
                  hold=f"{p['stress_hold_s']:g}",
                  strop=f"{p['max_per_hour']:g}",
                  odstup=f"{p['min_gap_s'] / 60.0:g}",
                  n=self._prah_z_relacii)

    def _refresh_citlivost_detail(self):
        popis = getattr(self, "citlivost_detail", None)
        if popis is None:
            return
        try:
            popis.configure(text=self._citlivost_detail_text())
        except Exception:
            pass

    def _build_guide_into(self, parent, pal):
        """Explanations and theory, inserted below the cue content.

        The `self.guide_content` reference stays, because
        `gui_screenshots.py` expands the cards through it (otherwise they
        can only be expanded by a click).
        """
        self.guide_content = build_guide_into(parent, pal)

    def _navigate(self, key):
        key = self.TAB_ALIAS.get(key, key)
        """Switches the page. The Settings tabs (SETTINGS_TABS) are nested:
        shows the Settings group and the given tab inside it; "nastavenia"
        on its own opens the last used tab (the first time, Cues).

        NOTE: this used to start with `dojo_band.suspend_briefly()`, which
        paused redrawing the lanterns in the photo strip for 180 ms - fast
        clicking through the sidebar otherwise landed in the middle of that
        redraw and it looked like "the whole app was reconfiguring". The
        photo strip was removed (see the NOTE in `_build_ui`), so the source
        of that flicker went with it - there is nothing left to pause.
        """
        if key in self.SETTINGS_TABS:
            self.pages.show("nastavenia")
            self.settings_pages.show(key)
            self.settings_nav.set_active(key)
            self._settings_last_tab = key
        elif key == "nastavenia":
            self.pages.show("nastavenia")
            tab = getattr(self, "_settings_last_tab", "spustace")
            self.settings_pages.show(tab)
            self.settings_nav.set_active(tab)
        else:
            self.pages.show(key)
        # The side panel must light up where you really are - even when the
        # page was switched by code (ⓘ About, ⚙ by Heart rate in game, Ctrl+K,
        # the tour), not by a click in the panel. Otherwise the content was
        # Settings and the panel showed "Today".
        sidebar = getattr(self, "sidebar", None)
        if sidebar is not None and hasattr(sidebar, "mark_active"):
            sidebar.mark_active(key)

    def _build_settings_group(self, page, pal):
        """The Settings group: a row of tabs at the top (Cues | Sound |
        General) and a nested PageContainer below it.

        "Guide" was a separate tab until 18. 9. - it now sits at the bottom
        of the Cues page and `TAB_ALIAS` sends the old key there.

        "In-game" is no longer a tab - it is a separate item in the side
        menu (the "Sumi noc" redesign), because it is the biggest part of
        the app.
        """
        head = ctk.CTkFrame(page, fg_color="transparent")
        # A tab is text with an 8 px inner margin (the button's rounding) - the
        # row is shifted 8 px to the left so that the TEXT of the first tab
        # starts on the page's left edge, exactly above the cards below it.
        head.pack(fill="x", padx=(ui_kit.PAGE_GUTTER - ui_kit.RADIUS_CONTROL,
                                   ui_kit.PAGE_GUTTER), pady=(16, 0))
        self.settings_nav = ui_kit.SubNav(
            head, pal, [(k, tr(f"nav.nastavenia_tabs.{k}")) for k in self.SETTINGS_TABS],
            on_select=self.sidebar._select)
        self.settings_nav.pack(anchor="w")
        self.settings_pages = PageContainer(page)
        self.settings_pages.configure(fg_color=pal["bg"])
        self.settings_pages.pack(fill="both", expand=True, pady=(8, 0))
        for key, builder in (("spustace", self._build_spustace_page),
                             ("zvuk", self._build_zvuk_page),
                             ("vseobecne", self._build_nastavenia_page)):
            frame = ctk.CTkFrame(self.settings_pages, fg_color=pal["bg"])
            self.settings_pages.add_page(key, frame)
            self.page_frames[key] = frame
            builder(frame, pal)
        tab = getattr(self, "_settings_last_tab", "spustace")
        self.settings_pages.show(tab)
        self.settings_nav.set_active(tab)

    def _build_nastavenia_page(self, page, pal):
        """General settings (a tab in the Settings group): now only things
        that get set once or are rarely needed - your data, About, the
        in-game sections, look and language, the "Not now" shortcut, the
        guide.

        A scrollable frame (not just a CTkFrame): with the fixed window
        size (see DandurfApp.WINDOW_H) all these panels may not fit
        vertically - without scrolling the bottom panels would be
        unreachable.

        NOTE: originally the "Dojo background", "Minimalist mode" and
        "Behaviour" panels were also listed here - all three have since
        been removed, so they are no longer a reason for the scroll.
        """
        wrap = ui_kit.stranka_scroll(page, pal)
        wrap.pack(fill="both", expand=True, padx=ui_kit.PAGE_GUTTER, pady=(20, 20))

        # NOTE: the first panel here used to be "Dojo background" - an
        # intensity slider for the photo strip above the title bar, with live
        # feedback on readability. The strip was removed (see the NOTE in
        # `_build_ui`), so the slider had nothing left to control. Look is now
        # the first panel. PHASE 4: data as the FIRST panel, not buried at the
        # bottom. The "everything stays with you" sub is on the store page and
        # is a real difference from the competition - it should be easy to
        # verify, not something you have to look for.
        # Reference to the scrolling frame: `show_about` uses it to scroll the
        # page to the About section. Without it the button in the title bar
        # would open the right page, but the player would stay at its top and
        # have to find the section themselves - so the button would do only
        # half of its job.
        self.vseobecne_wrap = wrap

        self._build_data_panel(wrap, pal)

        # "About" RIGHT BELOW THE DATA. They are two sides of the same
        # question: what the app does with my data and who is behind it. People
        # looking for one usually look for the other too.
        self._build_about_panel(wrap, pal)

        # Things the app draws into the game. They came here from the watch
        # page, where they covered up the one thing people go there for.
        self._build_ingame_sections_into(wrap, pal)

        look = ui_kit.Panel(wrap, pal, title=tr("settings.look_title"))
        look.pack(fill="x", pady=(14, 0))

        # WORLD instead of a colour theme (0.2, B3-worlds). The look belongs to
        # the world - Play is Sumi, Work is Aizome - so a separate theme choice
        # would only break what one look at the window is supposed to say. It
        # is the same switch as in the title bar at the top (`set_world`); the
        # sentence below it says honestly everything that changes with it. (Up
        # to 0.2 there was a "Colour theme" here with the sentence "try both" -
        # now that would relabel sessions.)
        row = ui_kit.SettingRow(look.body, pal, tr("settings.world"),
                                tr("settings.world_sub"))
        self.world_switch = ctk.CTkSegmentedButton(
            row.control, values=self._world_labels(),
            selected_color=pal["accent2"], selected_hover_color=pal["accent2_hover"],
            unselected_color=pal["surface_alt"], unselected_hover_color=pal["border"],
            text_color=pal["text"], fg_color=pal["surface_alt"],
            font=ui_kit.ui(12), command=self._on_world_label)
        self.world_switch.set(self._world_label(self.world))
        self.world_switch.pack()
        # the chosen world carries its text in the accent colour (the `accent2`
        # fill alone is not enough)
        ui_kit.oznac_zvoleny_segment(self.world_switch, pal)

        # The sentence below the language choice says honestly what is the
        # source and what is a translation: the app is written in Slovak, the
        # other languages are AI translations that no native speaker has read
        # yet. It is shown in all languages (it is translated like the other
        # texts).
        row = ui_kit.SettingRow(look.body, pal, tr("settings.language"),
                                tr("settings.language_sub"),
                                note=tr("settings.language_note"))
        self.lang_var = tk.StringVar(value=self._lang_switch_value(self.lang))
        self.lang_switch = ui_kit.option_menu(
            row.control, pal, values=list(LANG_NATIVE_LABELS.values()),
            variable=self.lang_var, command=self.on_lang_switch)
        self.lang_switch.pack()

        # NOTE: here used to be a "Behaviour" panel with a single switch, "Only
        # one cue at a time". It was the only switch in the whole panel, so it
        # came across as an important setting - and yet the state machine did
        # not read it at all: it does not and cannot fire two cues at once
        # (`min_gap_s` is 210 s and up). The only reader was `fire_slot`, i.e.
        # the Test button. There the protection makes sense, so it stayed
        # there - hard-coded, without a switch.

        # NOTE: the "Minimalist mode" switch used to be here (it shrank the
        # whole app window to 320x160) - removed. The same function (BPM + 4
        # icons) is now part of the in-game HUD panel, see "Show the panel in
        # game" in _build_vhre_page - that is the right place, because it is an
        # IN-GAME visual, not a mode of the app itself.

        # The "not now" shortcut (0.3) - previously it could only be changed in
        # the file.
        self._build_snooze_hotkey_row(wrap, pal)

        guide = ui_kit.Panel(wrap, pal, title=tr("settings.guide_title"))
        guide.pack(fill="x", pady=(14, 0))
        row = ui_kit.SettingRow(guide.body, pal, tr("settings.guide_row"),
                                tr("settings.guide_sub"))
        ui_kit.button(row.control, pal, tr("common.open"),
                      command=self.open_guide_panel).pack(anchor="e")
        self.tour_row = ui_kit.SettingRow(guide.body, pal, tr("settings.tour_row"),
                                          tr("settings.tour_sub"))
        self.tour_btn = ui_kit.button(self.tour_row.control, pal,
                                      tr("settings.tour_btn"), command=self.start_tour)
        self.tour_btn.pack(anchor="e")
        self._refresh_tour_row()      # an unfinished tour offers Continue

    def _build_heart_rate_card(self, page, pal, pady=(14, 0)):
        """Heart-Rate Sensor (Wi-Fi / UDP) - receives BPM from the watch (e.g.
        HeartRateOnStream for OBS) and the automatic biofeedback trigger
        of the breathing circle (Slot 4) on a long-lasting raised heart
        rate.

        `pady` is the panel's top padding - the first panel on the page
        has it at zero, the others 14 px (the same convention as the rest
        of the page)."""
        # NOTE: the card used to build its own CTkFrame here with
        # `pack(padx=20)` and its own heading in the grid, while ALL the other
        # panels on the page go through `ui_kit.Panel` and are packed without
        # padx. So the card was indented 20 px relative to them and had a
        # different heading and margin - reported as "does not line up with the
        # others". Now it is the same Panel as the rest, so the alignment holds
        # by itself.
        panel = ui_kit.Panel(page, pal, title=tr("settings.hr_section_title"))
        panel.pack(fill="x", pady=pady)
        self.hr_card = panel          # target of the tour step about the heart-rate sensor
        inner = ctk.CTkFrame(panel.body, fg_color="transparent")
        inner.pack(fill="x")
        inner.grid_columnconfigure(1, weight=1)

        # CARD ORDER (0.3): heart-rate receiving -> status -> pairing guide ->
        # only then the network fields. The field with 0.0.0.0 was the first
        # thing the player saw on the card, and it tempted them to enter that
        # number into the phone - pairing then failed without a single message.
        # The guide shows the PC's address, not the field.
        self.hr_enabled_var = tk.BooleanVar(value=self.hr_monitoring_enabled)
        ui_kit.switch(inner, pal, text=tr("settings.hr_enable_switch"),
                      variable=self.hr_enabled_var, text_color=pal["text"],
                      font=ui_kit.ui(13),
                      command=self.on_hr_toggle).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        # Wrapping like the critical heart rate description below: since 0.3
        # the heart rate may be followed by a sentence about two heart-rate
        # streams in one source.
        self.hr_status_label = ctk.CTkLabel(inner, text="", font=ui_kit.ui(13, "bold"),
                                            anchor="w", wraplength=430, justify="left")
        self.hr_status_label.grid(row=1, column=0, columnspan=2, sticky="w")
        self.refresh_hr_status_label()

        # Pairing the watch is the least intuitive part of the whole app - the
        # player has to know that the app pretends to be OBS and that in the
        # phone they are setting up an OBS connection. Hence a separate
        # step-by-step guide, not just a hint under the field (see
        # WatchPairingDialog).
        # A secondary button of natural width (`ui_kit.button`), not a gold
        # frame across the whole card (~1500 px) - that was the loudest element
        # on the page and drowned out the receiving status above it.
        ui_kit.button(inner, pal, tr("hr.pair_button"), height=32,
                      command=self.open_watch_pairing).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(14, 0))

        # The QR code for the phone app is here too, not only in the
        # step-by-step guide - whoever already knows what they are doing wants
        # to download it without opening the guide. Outwardly it is just a
        # badge, the white code only expands on a click (see ui_kit.QrReveal).
        qr_row = ctk.CTkFrame(inner, fg_color="transparent")
        qr_row.grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.hr_qr = watch_app_qr(qr_row, pal, pady=0)

        # THE CRITICAL HEART RATE IS NO LONGER A FIELD.
        #
        # It could not be set well. It enters the load formula as
        # `headroom = max(12, kriticky - zakladna)`, so with a baseline of 77
        # anything up to 89 gave the same result - the player moved the number
        # and nothing changed. And at the same time it defines the "critical"
        # zone, so a value that was too low turned a calm evening into 52 % of
        # the time in the red.
        #
        # The app computes it from its own sessions
        # (`hr_stats.dynamicky_kriticky`, the 90th percentile of playing). Here
        # it is only SHOWN, so you can see what the app is working with and how
        # that changes over time.
        self.hr_critical_label = ctk.CTkLabel(
            inner, text=self._kriticky_popis(), font=ui_kit.ui(11),
            text_color=pal["text_dim"], anchor="w", justify="left",
            wraplength=430)
        self.hr_critical_label.grid(row=4, column=0, columnspan=2, sticky="w",
                                    pady=(14, 10))

        self.hr_ip_var = tk.StringVar(value=self.hr_ip)
        # The IP field is hidden like a password until the player reveals it
        # with the switch next to it (hidden IP, see `set_show_ip`). Saving the
        # value does not change because of it - the mask is only how the field
        # is drawn.
        self.show_ip_var = tk.BooleanVar(value=self.show_ip)

        # The switch only shows when there is a real address in the field: with
        # 0.0.0.0 it had nothing to reveal and the player expected it to show
        # the PC's address. It is shown by `_apply_hr_ip_mask` (on every change
        # of the field).
        def _prepinac_ip(bunka):
            self.hr_ip_show_switch = ui_kit.switch(
                bunka, pal, text=tr("hr.ip_show"), variable=self.show_ip_var,
                font=ui_kit.ui(11),
                command=lambda: self.set_show_ip(self.show_ip_var.get()))

        self.hr_ip_entry = self._hr_entry(inner, pal, 5, tr("settings.hr_ip_label"),
                                          self.hr_ip_var, extra=_prepinac_ip)
        self.hr_ip_var.trace_add("write", lambda *_a: self._apply_hr_ip_mask())
        self._apply_hr_ip_mask()
        # The hint keeps a reference: when the field holds the address of a
        # VPN/virtual adapter, `_apply_hr_ip_mask` adds a sentence to it (0.3).
        self.hr_ip_hint_label = self._hr_hint(inner, pal, 6, tr("settings.hr_ip_hint"))
        self._hr_ip_virtual_hint(self.hr_ip_var.get())

        self.hr_port_var = tk.StringVar(value=str(self.hr_port))
        self.hr_port_entry = self._hr_entry(inner, pal, 7, tr("settings.hr_port_label"),
                                            self.hr_port_var)
        self._hr_hint(inner, pal, 8, tr("settings.hr_port_hint"))

    def _hr_entry(self, inner, pal, row, label, variable, extra=None):
        """One "label + field" row of the Heart-Rate Sensor card.

        set_typing() is called here just as in the slots (see SlotCard),
        but nothing reads the flag any more. Before phase 3 a global
        keyboard catcher ran even while the player was typing into the
        settings, so without it typing "110" would fire the slot bound to
        the "1" key. Phase 3 removed the hooks (KEY_SLOTS_ENABLED is
        False).

        `extra(bunka)` adds another control next to the field (the
        "Show IP" switch) - the field stays in the same place on the
        axis."""
        # fixed label width + the same field width: all three rows (IP, port,
        # heart rate) sit on one axis (feedback: "they are not on one axis")
        ctk.CTkLabel(inner, text=label, text_color=pal["text"], width=190,
                     anchor="w", justify="left").grid(
            row=row, column=0, sticky="w", pady=6)
        bunka = inner
        if extra is not None:
            bunka = ctk.CTkFrame(inner, fg_color="transparent")
            bunka.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=6)
        entry = ctk.CTkEntry(bunka, textvariable=variable, width=150, height=30,
                             corner_radius=ui_kit.RADIUS_CONTROL,
                             fg_color=pal["entry_bg"], border_color=pal["border"],
                             text_color=pal["text"])
        if extra is not None:
            entry.pack(side="left")
            extra(bunka)
        else:
            entry.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=6)
        entry.bind("<FocusIn>", lambda _e: self.set_typing(True))
        entry.bind("<FocusOut>", lambda _e: (self.set_typing(False),
                                             self.on_hr_config_change()))
        entry.bind("<Return>", lambda _e: self.on_hr_config_change())
        return entry

    def _kriticky_popis(self):
        """The sentence below the sensor fields - what the app computed and
        from what.

        From what = from PLAY sessions (B3-worlds), just like the
        computation itself in `_open_hr_session`; work evenings are not
        counted in `n`.

        SHORT SESSIONS ARE NOT COUNTED (0.2.1) - `dynamicky_kriticky`
        learns only from sessions at least 5 minutes long
        (`hr_stats.je_dost_dlha`). Without this, after three short
        sessions the sentence would claim "computed from 3 sessions",
        while in fact the fallback of 110 applies."""
        n = len([r for r in hr_stats.ciste_relacie(hr_stats.sessions_in_world(
            self._history_sessions(), self.ALGORITMUS_SVET))
            if hr_stats.je_dost_dlha(r)])
        if n < hr_stats.KRITICKY_MIN_RELACII:
            return tr("settings.hr_critical_learning",
                      bpm=int(self.hr_critical_bpm),
                      treba=hr_stats.KRITICKY_MIN_RELACII - n)
        return tr("settings.hr_critical_computed",
                  bpm=int(self.hr_critical_bpm), n=n)

    def _refresh_kriticky_popis(self):
        popis = getattr(self, "hr_critical_label", None)
        if popis is None:
            return
        try:
            popis.configure(text=self._kriticky_popis())
        except Exception:
            pass

    def _hr_hint(self, inner, pal, row, text):
        """A hint below one field of the Heart-Rate Sensor card.

        A separate method (instead of repeating grid() in every place), so
        that all three rows (IP/Port/Heart rate) are guaranteed the same
        left alignment and the same vertical spacing - feedback from a
        test ("different indentation") showed that copying the same grid()
        arguments in 3 places drifts apart over time."""
        label = ctk.CTkLabel(inner, text=text, text_color=pal["text_dim"],
                             font=ui_kit.ui(10), wraplength=320, justify="left",
                             anchor="w")
        label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 4))
        return label

    # ---------- Somatic Session Tracker ----------

    def _session_text(self):
        c = self.session_counts
        return tr("session.summary", g=c.get(0, 0), j=c.get(1, 0),
                 r=c.get(2, 0), b=c.get(3, 0))

    def update_session_label(self):
        if self.session_label is not None:
            try:
                self.session_label.configure(text=self._session_text())
            except Exception:
                pass

    # ---------- guide ----------

    def open_guide_panel(self):
        if self._guide_panel is not None and self._guide_panel.top.winfo_exists():
            self._guide_panel.top.lift()
            self._guide_panel.top.focus_force()
            return
        self._guide_panel = GuidePanel(self)

    def start_tour(self, from_start=False):
        """Starts the guided tour of the app (where things are).

        It is called once after the first onboarding and any time from
        Settings. We keep one instance so that two tours do not overlap.

        `from_start=True` starts from the beginning; otherwise it picks up
        where the player last left it (`tour_step`) - always starting over
        means that the second time they will not look at anything.
        """
        existing = getattr(self, "_tour", None)
        if existing is not None:
            existing.finish()
        self._tour = GuidedTour(self, start_index=0 if from_start else self.tour_step)
        self._tour.start()

    def _prehliadka_po_parovani(self):
        """First start with "Pair a watch now": the pairing guide has
        closed, now the first tour comes. Only if the player has not seen
        it in the meantime and none is running - this is checked ONLY
        NOW, not when the guide opens."""
        if self.tour_seen or getattr(self, "_tour", None) is not None:
            return
        # A short delay (as after the introduction): `on_close` runs right
        # after the guide's destroy(), before the main window has been
        # redrawn - the bubble measures the target's position on screen and
        # would get it from the old frame.
        self.root.after(300, self.start_tour)

    def save_tour_progress(self, index):
        """Where the tour ended (0 = it ran to the end)."""
        self.tour_step = max(0, int(index or 0))
        self._refresh_tour_row()
        self.save_settings()

    def _refresh_tour_row(self):
        """The tour row in Settings - an unfinished tour offers Continue and
        shows where you stopped."""
        row = getattr(self, "tour_row", None)
        button = getattr(self, "tour_btn", None)
        if row is None or button is None:
            return
        try:
            rozpracovana = self.tour_step > 0
            row.title_label.configure(
                text=tr("settings.tour_row_at", n=self.tour_step + 1,
                        total=GuidedTour.STEP_COUNT) if rozpracovana
                else tr("settings.tour_row"))
            button.configure(text=tr("settings.tour_resume") if rozpracovana
                             else tr("settings.tour_btn"))
        except Exception:
            pass

    def mark_tour_seen(self):
        """Tour done or skipped - we will not start it by ourselves again."""
        self.tour_seen = True
        self._tour = None
        self.save_settings()

    def _refresh_guide_panel_theme(self):
        if self._guide_panel is not None and self._guide_panel.top.winfo_exists():
            self._guide_panel.top.destroy()
            self._guide_panel = GuidePanel(self)

    # ---------- developer overlay (phase 5, §3.2) ----------

    def open_dev_layer(self):
        """Opens debugging. Called by the 15th click on the version number."""
        try:
            DevLayerDialog(self)
        except Exception:
            app_log.exception("vyvojarska vrstva sa nepodarila otvorit")

    def apply_dev_params(self, params, silent_share):
        """Saves the new thresholds. They apply only FROM THE NEXT session.

        Spec §3.3: the parameters change only between sessions. The dialog
        already enforced that by locking the fields during a running
        session; here the values are only set aside and
        `start_heart_rate_monitor` picks them up.
        """
        params = dict(params)
        # THE HARD SAFEGUARD APPLIES HERE TOO.
        #
        # The developer overlay is for tuning thresholds, not for getting
        # around the limit that protects the measurement: with a gap below
        # `measure.REFRACTORY_AFTER_S` (180 s) the second cue lands in the
        # first one's measurement window and both windows become invalid. A
        # typo in the field would then spoil not one evening but a whole week
        # of data - and in the data it would look like "the cue did not work".
        odstup = params.get("min_gap_s")
        if odstup is not None and float(odstup) < trigger.MIN_GAP_FLOOR_S:
            params["min_gap_s"] = trigger.MIN_GAP_FLOOR_S
            self.log(tr("dev.min_gap_clamped", s=f"{trigger.MIN_GAP_FLOOR_S:g}"))
        self._dev_params = params
        self._dev_silent_share = silent_share
        self.cue_trigger.params.update(params)
        self.cue_trigger.silent_share = silent_share
        self.log(tr("dev.applied"))

    def dev_force_cue(self):
        """Fires a cue right away, without waiting for the body or a pause.

        It deliberately does NOT USE `cue_trigger` - a forced cue is not a
        measurement and must not get into the windows or burn the
        refractory zone. It is only there so the sound can be heard and
        the visual seen.
        """
        index = self.CUE_SLOT_INDEX
        try:
            self.overlay_manager.trigger(index)
            slot = next((s for s in self.slots if s.index == index), None)
            if slot is not None:
                threading.Thread(target=self._emit, args=(slot,), daemon=True).start()
        except Exception:
            app_log.exception("vynutena hlaska zlyhala")

    # ---------- log ----------

    def log(self, message):
        stamp = time.strftime("%H:%M:%S")
        self._last_log_line = f"[{stamp}] {message}"
        if self.log_text is None:
            print(self._last_log_line)
            return
        # THE JOURNAL MAY NO LONGER EXIST. The window goes away at
        # `root.destroy()` in `_quit`, and code still running at that moment
        # keeps logging - e.g. `_close_hr_session` after the questionnaire (a
        # crash in app.log from a build: TclError "invalid command name
        # ...!ctktextbox.!text"). Writing to the journal is only display, it
        # must not bring down the caller; the line at least goes to the file.
        try:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", f"{self._last_log_line}\n")
            self.log_text.see("end")
            if int(self.log_text.index("end-1c").split(".")[0]) > 200:
                self.log_text.delete("1.0", "50.0")
            self.log_text.configure(state="disabled")
        except tk.TclError:
            self._dennik_bez_okna(message)
            return
        try:
            self.log_toggle_btn.configure(text=self._log_toggle_text())
        except Exception:
            pass

    def _dennik_bez_okna(self, message):
        """A journal line that has nowhere to go any more - to app.log WITHOUT
        addresses.

        Journal lines may carry the PC's IP address (after "Show IP", in
        full), and according to PRIVACY.md app.log must not contain it -
        hence the mask. `log` itself deliberately does not touch the file
        at all (test_ip_skryta): only this substitute line goes to the
        file, once the window is gone."""
        try:
            app_log.info("dennik (okno uz nie je): %s",
                         netinfo.mask_ips_in_text(message))
        except Exception:
            pass

    def ui_call(self, func):
        """Schedules a call on the GUI thread. Safe from any thread, even
        while the application is shutting down (Tk then rejects the call).

        THE FIRST FAILURE IS LOGGED. Previously there was a bare `pass`
        here, and that hides a whole class of bugs: `root.after` from a
        foreign thread raises RuntimeError("main thread is not in main
        loop") whenever Tk is not running in `mainloop()`, and the caller
        learns nothing about it - the callback just never arrives. That
        happened while debugging the hotkey: the key press got all the way
        to `_on_snooze_hotkey`, `ui_call` swallowed it and the snooze did
        not start.

        Further occurrences are only counted: when the app is quitting,
        many rejected calls can arrive at once and the log would be
        flooded.
        """
        try:
            self.root.after(0, func)
            return
        except RuntimeError:
            # Tk is not in `mainloop()` yet. This happens on EVERY start:
            # `_ensure_sfx_assets` and the Edge cue preparation both run on
            # their own thread right from `__init__` and start logging before
            # the loop gets going. Previously those lines were silently
            # dropped.
            #
            # We set them aside and deliver them once the loop runs -
            # `_flush_ui_pending` is scheduled from the main thread, so `after`
            # works on it.
            try:
                self._ui_pending.append(func)
            except Exception:
                pass
            return
        except Exception:
            pass
        self._ui_call_fails = getattr(self, "_ui_call_fails", 0) + 1
        if self._ui_call_fails == 1:
            app_log.exception(
                "ui_call: volanie sa nepodarilo naplanovat "
                "(dalsie vyskyty sa uz nevypisu)")

    def _flush_ui_pending(self):
        """Delivers calls that came from threads before `mainloop()` got
        going. Called once, as soon as the loop runs."""
        fronta, self._ui_pending = list(self._ui_pending), deque(maxlen=200)
        for func in fronta:
            try:
                func()
            except Exception:
                app_log.exception("ui_call: odlozene volanie zlyhalo")

    def log_threadsafe(self, message):
        self.ui_call(lambda: self.log(message))

    def set_typing(self, value):
        self.typing = bool(value)

    # ---------- start / stop ----------

    # FIRST START: WATCH ONLY AFTER THE VOICE IS PREPARED (0.3).
    #
    # After the introduction the app starts watching by itself (`__init__`).
    # It did that after 250 ms - but while it is watching it does not go to
    # Microsoft, not even for cue preparation (`pregenerate`), so the
    # preparation stopped right away and the first evening, by which the app
    # gets judged, mostly spoke with the Windows voice. Now it waits until the
    # cues are in the cache, at most `PRVY_START_MAX_S` (a failed preparation
    # without a network must not postpone the start forever). The state is
    # read by `_kamae_state_text`.
    PRVY_START_MAX_S = 15.0
    PRVY_START_KROK_MS = 500

    def _hlas_pripraveny(self):
        """Are the cues the natural voice will say in-game already cached?

        True also when nothing needs preparing (Windows voice, Edge
        missing, a style without words, Work, all cues disabled -
        `pregen_jobs` is empty): then there is nothing to wait for. The
        same question as in `pregenerate`."""
        if self.engine != ENGINE_EDGE or not audio_engine.EDGE_AVAILABLE:
            return True
        try:
            rate = self.rate_value
            return all(self.edge_cache.has(text, hlas, rate)
                       for text, hlas in self.pregen_jobs())
        except Exception:
            # Better to start watching right away than to hang - that is how it
            # was until now.
            app_log.exception("prvy start: stav pripravy hlasu sa nedal zistit")
            return True

    def _zacni_sledovat_po_priprave_hlasu(self):
        """First start: watching begins once the voice is prepared or after
        `PRVY_START_MAX_S` - whichever comes first. The preparation is
        started by `_load_edge_voices` still in `__init__`, this only lets
        it finish."""
        if self._hlas_pripraveny():
            self.root.after(250, self.start_listening)
            return
        self._prvy_start_caka = True
        self._prvy_start_do = time.monotonic() + self.PRVY_START_MAX_S
        self._refresh_kamae_state_text()
        self._prvy_start_job = self.root.after(self.PRVY_START_KROK_MS,
                                               self._prvy_start_krok)

    def _prvy_start_krok(self):
        """Once every `PRVY_START_KROK_MS`: voice ready, or time up?"""
        self._prvy_start_job = None
        if not self._prvy_start_caka:
            return
        if self.listening:
            # Started by the player or by a game - no second start needed.
            self._zrus_cakanie_prveho_startu()
            return
        if self._hlas_pripraveny() or time.monotonic() >= self._prvy_start_do:
            self.start_listening()
            return
        self._prvy_start_job = self.root.after(self.PRVY_START_KROK_MS,
                                               self._prvy_start_krok)

    def _zrus_cakanie_prveho_startu(self):
        """End of the voice wait - the bar must no longer promise a start."""
        self._prvy_start_caka = False
        job, self._prvy_start_job = self._prvy_start_job, None
        if job is not None:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
        self._refresh_kamae_state_text()

    def toggle_listening(self):
        if self.listening:
            self.stop_listening()
        else:
            self.start_listening()

    def start_listening(self):
        """Turns listening on. From this moment the enso glows `success`.

        PHASE 3 changed what "listening" means. Until then it was "the key
        hooks are running"; now it is "the app watches the body and may
        speak up". No hook is installed any more - activity is detected
        via `GetLastInputInfo`, which returns only the number of
        milliseconds since the last input.

        The enso is the only carrier of state in the whole interface, so
        this is NOT just cosmetics: `_cue_can_fire` asks about
        `self.listening`, so while the enso glows `danger`, the app really
        is silent.
        """
        if self.listening:
            return
        # The first start no longer waits for the voice (`_prvy_start_krok`) -
        # it was started by the player with the button, by a game
        # (auto-profile) or by the waiting itself. Without this, a player who
        # meanwhile pressed ▶ and right away ■ would get a second start a
        # moment later.
        if getattr(self, "_prvy_start_caka", False):
            self._zrus_cakanie_prveho_startu()
        # The drag test must not survive listening being started.
        #
        # The test visual has click-through turned off, so over the game it
        # swallows clicks. A player who fine-tuned the position and then turned
        # on listening goes to play right after - and would have an unclickable
        # area in the middle of the screen.
        try:
            if self.overlay_manager.stop_all_tests():
                self.log(tr("log.overlay_test_ukonceny"))
                self._refresh_all_test_buttons()
        except Exception:
            app_log.exception("ukoncenie drag-testu zlyhalo")
        if self.gamepad.available:
            # No longer as a trigger - only as a second source of information
            # on whether the player is active, and as the only way to tell a
            # controller from a keyboard (`GetLastInputInfo` sees both, but
            # does not say which).
            self.gamepad.start()
        self.activity.set_gamepad_watched(self.gamepad.available)
        # A NEW MEASUREMENT SESSION EVERY TIME LISTENING IS TURNED ON.
        #
        # The session was tied to the SENSOR, not to listening: it was opened
        # only in `start_heart_rate_monitor`. Ever since `stop_listening`
        # closes it properly, this turned into a silent failure - after the
        # first stop/start cycle NO session was open and nothing was measured.
        # (In the CSV from 18. 9. this shows as four short sessions instead of
        # one: 17:03, 18:01, 18:04, 18:07 - they came about only by restarting
        # the app, because otherwise a new session could not be opened.)
        #
        # We do NOT TOUCH the network here: when receiving is already running,
        # a socket restart would disconnect the watch for a moment - and it is
        # exactly short dropouts that break the continuity counting (see
        # points 2 and 5 of the spec).
        if self.hr_monitoring_enabled and not getattr(self, "_hr_session_open", False):
            if self.heart_rate_monitor.running:
                self._open_hr_session(prepoj=False, meria=True)
            else:
                # `self.listening` is not True yet, so it is said directly.
                self._open_hr_session(meria=True)
                self._hr_generation = self.heart_rate_monitor.start(
                    self.hr_ip, self.hr_port)
        # `stop_listening` pauses the trigger; without this it would only be
        # lifted by some other path and until then the app would stay silent.
        # While "not now" holds, it lifts nothing (`_resume_cue_trigger`) - the
        # muting still applies.
        self._resume_cue_trigger()
        self.listening = True
        self.session_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        self.update_session_label()
        self._apply_listening_visuals()
        self.log(tr("log.listening_on"))
        self.update_tray_icon()

    def stop_listening(self):
        self.gamepad.stop()
        self.activity.set_gamepad_watched(False)
        self.listening = False
        self._suspend_cue_trigger(trigger.A_SNOOZE)
        # THE SESSION ENDS HERE, not only when the app is closed.
        # `_close_hr_session` hung only on switching the SENSOR off and on
        # `_quit`. Whoever pressed stop and left the app open still had the
        # session open - it was not saved, the context question was not asked,
        # and if the process ended other than through `_quit`, the whole
        # evening of measurement was lost. It happened.
        #
        # When not listening, no cue can fire, so nothing is measured any
        # more - there is no reason for the session to stay open.
        # `_hr_session_open` guards against the second caller (switching the
        # sensor off, `_quit`) repeating it.
        self._close_hr_session()
        self._apply_listening_visuals()
        self.log(tr("log.listening_off"))
        self.update_tray_icon()
        self._dopriprav_hlasky_po_hre()

    def _dopriprav_hlasky_po_hre(self):
        """Cues that were missing from the cache during the game
        (`_speak_text`) are prepared only now - while listening the app
        does not go to Microsoft."""
        if getattr(self, "_pregen_po_hre", False):
            self._pregen_po_hre = False
            self.schedule_pregenerate(200)

    def _apply_listening_visuals(self):
        """Carries the state over to the breathing bar and the quick dock.

        No blinking is needed any more - `KamaeBar` drives its rhythm by
        itself and stands still when stopped, so no `after()` chain is
        started here (the original `_pulse_status` ran twice a second the
        whole time the app was running).
        """
        if self.listening and getattr(self, "_listen_started", None) is None:
            self._listen_started = time.time()
        elif not self.listening:
            self._listen_started = None
        # The button in the bar switches its text (Start <-> Stop) by itself in
        # `set_live` - this is the only path all starts and stops go through
        # (button, tray menu, game), so they do not drift apart.
        if getattr(self, "kamae", None) is not None:
            self.kamae.set_live(self.listening)
        # Status text on Today and the dot in the panel (watching, but the
        # heart rate dropped out).
        self._refresh_kamae_state_text()
        # the brightness of the photo behind the enso follows the watching
        # state, not the watch
        if hasattr(self, "_sync_dnes_hero"):
            self._sync_dnes_hero()
        if getattr(self, "sidebar", None) is not None:
            try:
                # The indicator in the panel is the only status information on
                # five of the six pages - the mark and the bar live on the
                # Today page.
                bodka = getattr(self.sidebar, "state_dot", None)
                if bodka is not None:
                    bodka.set_live(self.listening)
                self.sidebar.enso.set_live(self.listening)
                # A window rebuild (language change, theme rescue) builds the
                # ENSO ANEW, and it starts with `_armed = False`, while
                # `self._cue_armed` keeps its state. The bar would then report
                # "Armed" above a mark without a ring until the next event of
                # the state machine. `set_live` does not save this - it drops
                # that flag only on a True -> False transition.
                self.sidebar.enso.set_armed(self._cue_armed and self.listening)
            except Exception:
                pass
        # The HUD trigger row ("Show the panel in game") does not redraw its
        # feature list by itself - once on every change of the listening state
        # is enough for the icons to reflect the current enabled/disabled
        # slots.
        self._refresh_hud_trigger_row()
        self._refresh_nav_badges()


    def make_tray_image(self):
        """The system tray icon - the same mark as the app icon.

        The ring carries the state (running / stopped), the 残 glyph
        carries the identity. Originally it was just a green or red dot
        that could not be told apart from the other icons in the tray.

        `make_icon` is an ordinary module without module-level code, so it
        can be imported at runtime too; if drawing fails for any reason
        (a missing font with CJK glyphs), it falls back to the original dot
        - an app without a tray icon could not be brought back from being
        minimised.
        """
        size = 64
        pal = self.pal
        ring = pal["success"] if self.listening else pal["danger"]
        try:
            import make_icon
            rgb = tuple(int(ring.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
            return make_icon.tray_mark(size, rgb)
        except Exception:
            app_log.exception("make_tray_image: kreslenie znacky zlyhalo")
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            color = (60, 160, 60, 255) if self.listening else (160, 60, 60, 255)
            ImageDraw.Draw(img).ellipse((4, 4, size - 4, size - 4), fill=color)
            return img

    def setup_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem(lambda _item: tr("tray.show"), self.show_window, default=True),
            # The item says what WILL HAPPEN on a click (0.3, UX audit): a
            # static "Start / Stop" did not say whether the app is watching
            # right now. The text is recomputed on `update_menu` in
            # `update_tray_icon`.
            pystray.MenuItem(
                lambda _item: (tr("tray.stop") if getattr(self, "listening", False)
                               else tr("tray.start")),
                lambda *_: self.ui_call(self.toggle_listening)),
            # "NOT NOW" EVEN WITHOUT THE SHORTCUT (0.2.1). When another app
            # holds Ctrl+Alt+Z, `RegisterHotKey` fails - and then the cues
            # could only be muted by stopping listening, which also stops the
            # measurement. The item does exactly what the shortcut does: a
            # toggle for `SNOOZE_HOTKEY_MINUTES` minutes, the tick says whether
            # it is in effect right now. The click arrives on the tray thread,
            # so it goes through `ui_call` just like a shortcut press.
            pystray.MenuItem(
                lambda _item: tr("tray.snooze", minutes=SNOOZE_HOTKEY_MINUTES),
                lambda *_: self.ui_call(self._toggle_snooze_from_hotkey),
                checked=lambda _item: getattr(self, "_snooze_job", None) is not None),
            pystray.MenuItem(lambda _item: tr("tray.quit"), self.quit_app),
        )
        self.tray_icon = pystray.Icon(APP_NAME, self.make_tray_image(), APP_NAME, menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def update_tray_icon(self):
        if self.tray_icon:
            try:
                self.tray_icon.icon = self.make_tray_image()
            except Exception:
                pass
            # On Windows pystray builds the menu texts only on `update_menu` -
            # without it "Start watching / Stop watching" would stay as it was.
            try:
                self.tray_icon.update_menu()
            except Exception:
                app_log.exception("lista: menu sa nepodarilo obnovit")
        self._apply_window_icon()

    def _apply_window_icon(self):
        """Window icon (taskbar / alt-tab) = the same gold enso in the state
        colour (green listening / red not) as the tray mark. Best effort:
        with a frameless window it may not show everywhere, so it is all
        in try/except and the app keeps running without it. We keep the
        reference to the image, otherwise Tk drops it and the icon turns
        white.

        200 ms after the window is created, CustomTkinter sets its OWN
        icon directly on the window (`CTk._windows_set_titlebar_icon`),
        unless the app has called `iconbitmap()` by then. It does not know
        about `iconphoto()`, so the taskbar and Alt-Tab kept showing the
        CustomTkinter logo instead of the enso. Two paths:
          * normal start - the CTk timer only fires in `mainloop()`, i.e.
            AFTER this method. So we set the flag by which CTk remembers
            "the app has its own icon" ourselves (only when the enso was
            really set; otherwise better the CTk icon than none);
          * first start - the timer fires already during the guide, BEFORE
            this method. `iconphoto(True, ...)` only changes the default
            icon, and that is overridden by the window's own icon - so the
            main window also gets the enso directly
            (`iconphoto(False, ...)`).
        A test in tests/test_ui_fixes.py guards that CTk still reads the
        flag."""
        try:
            photo = _ImageTk.PhotoImage(self.make_tray_image())
            self.root.iconphoto(True, photo)     # default for the app's windows
            self.root.iconphoto(False, photo)    # the main window's own icon
            self._window_icon_ref = photo
        except Exception:
            return
        if hasattr(self.root, "_iconbitmap_method_called"):
            self.root._iconbitmap_method_called = True

    def minimize_to_tray(self):
        if TRAY_AVAILABLE:
            self.root.withdraw()
        else:
            self.root.iconify()

    def show_window(self, *_):
        self.ui_call(self._show_window)

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def on_close(self):
        if not TRAY_AVAILABLE:
            self.quit_app()
            return
        # FIRST ×: say that the app does not quit. Until now × silently hid the
        # window into the tray - the port for the phone stayed open and heart
        # rate kept being measured and saved, although the player thought they
        # had closed the app. It says so once and gives a choice; after that ×
        # only hides.
        #
        # TWO BUTTONS, NOT YES/NO (0.3, batch 4): the system dialog had buttons
        # in the Windows language and the sentence had to explain "(No = quit
        # right away)". Now it is an app dialog (`ui_kit.choose`) with "Keep
        # running in the tray" (default, Enter) and "Quit Zanshin". Escape and
        # × in the dialog = nothing happens, the window stays - and it asks
        # again on the next ×, because the player has not chosen yet.
        if not getattr(self, "tray_close_explained", True):
            volba = ui_kit.choose(
                getattr(self, "root", None), getattr(self, "pal", None), APP_NAME,
                tr("tray.close_first", port=self.hr_port),
                [("tray", tr("tray.keep_running"), "primary"),
                 ("quit", tr("tray.quit_app"), "secondary")],
                cancel=None, default="tray")
            if volba is None:
                return
            self.tray_close_explained = True
            self.save_settings()
            if volba == "quit":
                self.quit_app()
                return
        self.minimize_to_tray()

    def quit_app(self, *_):
        self.ui_call(self._quit)

    def _quit(self):
        # QUITTING MUST NOT RUN TWICE, NESTED.
        #
        # `stop_listening` -> `_close_hr_session` -> `_ask_session_context`
        # WAITS for the questionnaire on closing (`wait_window`). That is a
        # nested Tk loop, and it also handles another "Quit" from the tray. The
        # second `_quit` then ran all the way to `root.destroy()`, the
        # questionnaire went away with the window and the first `_quit`
        # continued in an already destroyed window - `log` in
        # `_close_hr_session` crashed with a TclError (a crash in app.log from
        # a build). A second "Quit" now only closes the questionnaire and the
        # first `_quit` finishes the quitting, in the order below. FILLED-IN
        # ANSWERS ARE NOT LOST (0.3, the author's decision): when the
        # player touched at least one answer, they are saved (as with "Save");
        # when not, it closes as with "Skip".
        if getattr(self, "_quit_bezi", False):
            dotaznik = getattr(self, "_dotaznik_pri_zatvarani", None)
            if dotaznik is None:
                return
            self._dokonci_dotaznik(dotaznik)
            return
        self._quit_bezi = True
        # While this is True, `_ask_session_context` waits for the
        # questionnaire.
        self._zatvara_sa = True
        # A questionnaire from a normal Stop that is still open (0.3 batch 4b):
        # the same rule as with a second "Quit" - otherwise `root.destroy()`
        # below would throw it away along with the answers. BEFORE
        # `stop_listening`, so that the new closing questionnaire does not open
        # on top of the old one.
        try:
            self._dokonci_otvorene_dotazniky()
        except Exception:
            app_log.exception("ukoncenie: otvorene dotazniky sa nepodarilo dokoncit")

        # EACH STEP SEPARATELY. An exception in one step (e.g.
        # `stop_listening`) skipped everything after it: the HUD, the in-game
        # visuals, the shortcut, the port for the watch and the tray icon kept
        # running and `root.destroy()` never came.
        def krok(meno, fn):
            try:
                fn()
            except Exception:
                app_log.exception("ukoncenie: krok %s zlyhal - pokracujem dalsim", meno)

        try:
            # The session is saved FIRST (`stop_listening` ->
            # `_close_hr_session`).
            krok("stop_listening", self.stop_listening)
            for attr in ("_pregen_job", "_snooze_job", "_activity_job",
                         "_hr_retry_job"):
                job = getattr(self, attr, None)
                if job is not None:
                    try:
                        self.root.after_cancel(job)
                    except Exception:
                        pass
                    setattr(self, attr, None)
            krok("_close_hr_session", self._close_hr_session)
            krok("hud", lambda: self.hud.stop())
            krok("vizualy", lambda: self.overlay_manager.stop_all())
            krok("ovladac", lambda: self.gamepad.stop())
            # The hotkey holds its own thread with a `GetMessageW` loop - without
            # this it would hang until the end of the process and the key
            # combination would stay taken.
            # Deliberately only HERE, not in `stop_listening` or `on_close`: "not
            # now" has to work even when the app is not listening and even when
            # it is minimised to the tray.
            krok("hotkey", self.stop_snooze_hotkey)
            krok("senzor tepu", lambda: self.heart_rate_monitor.stop())
            if self.game_watcher is not None:
                krok("game_watcher", lambda: self.game_watcher.stop())
            krok("hlas", lambda: self.worker.stop())
            if self.tray_icon:
                try:
                    self.tray_icon.stop()
                except Exception:
                    pass
            krok("root.destroy", self.root.destroy)
        finally:
            self._quit_bezi = False

    # Registration of the global "not now" shortcut (from the quick dock
    # section). The rest of "not now" (the toggle, snoozing the cues, the
    # status dot) is in app_controls.ControlsMixin. These two methods stayed
    # in app.py next to the tray: `start_snooze_hotkey` reads TRAY_AVAILABLE,
    # which is computed here together with the pystray/PIL import (and the
    # tests change it on the app module).
    def start_snooze_hotkey(self, po_zmene=False):
        """Registers the global key for "not now" (spec §1.9).

        This is NOT a return of the hook that phase 3 removed - see the
        header of `hotkey.py`. The app announces a SINGLE combination to
        Windows and learns nothing about any other key.

        When the combination is taken by another app, registration fails
        and the app keeps running without it - `hotkey.GlobalHotkey` logs
        it. The button in the dock is gone; since 0.2.1 "not now" is also
        in the tray icon's menu (`setup_tray`) and the journal line
        (`log.hotkey_failed_tray`) sends the player there. Without a tray
        (pystray/PIL missing) the only option left is to stop listening,
        which also stops the measurement - that is what
        `log.hotkey_failed` says.

        `po_zmene=True`: the player has just picked another shortcut in
        Settings (`on_snooze_hotkey_pick`). The old one is unregistered
        first (the first line below), the result of the new one goes to
        the journal just like at start and to the settings row
        (`_hotkey_zlyhala`).
        """
        self.stop_snooze_hotkey()
        self._hotkey_zlyhala = False
        self._hotkey_caka = False
        # Every registration has its own number: a late result of an old
        # shortcut (the player picked another one meanwhile) is dropped
        # (`_po_registracii_skratky`).
        self._hotkey_gen = getattr(self, "_hotkey_gen", 0) + 1
        gen = self._hotkey_gen
        if not self.snooze_hotkey:
            return False
        try:
            self._hotkey = hotkey.GlobalHotkey(
                self.snooze_hotkey, self._on_snooze_hotkey,
                # NOT `log_threadsafe`: the hotkey is registered on its own
                # thread already during `__init__`, i.e. BEFORE
                # `root.mainloop()`. At that point `ui_call` cannot schedule
                # yet ("main thread is not in main loop") and the message would
                # be silently lost - which is exactly what was happening.
                # `app_log` is thread-safe and always writes to the file. The
                # registration result is logged to the window only by
                # `start_snooze_hotkey` below, from the main thread.
                log=app_log.info)
            # THE REAL RESULT, NOT A GUESS BY TIME (0.3 batch 4b).
            # `start()` waits at most 2 s; when Windows is slow at startup,
            # it returns False even though nobody holds the shortcut - the
            # Settings row and the journal then claimed "another program
            # holds it". The thread reports the result itself once it has
            # it; `ui_call` carries it over to Tk (`root.after(0)`, before
            # `mainloop()` via `_ui_pending`).
            self._hotkey.on_result = (
                lambda ok, g=gen: self.ui_call(
                    lambda: self._po_registracii_skratky(g, ok)))
            ok = self._hotkey.start()
        except Exception:
            app_log.exception("hotkey: registracia zlyhala")
            self._hotkey = None
            self._hotkey_zlyhala = True
            return False
        if getattr(self._hotkey, "caka", False):
            # Not done yet - the row does not show "taken" and the journal
            # shows nothing until the result comes from the thread.
            self._hotkey_caka = True
            return False
        # The result may have finished only between `start()` and the `caka`
        # check: `start()` then still returned False, but the thread had
        # already finished successfully and its `on_result` is dropped (because
        # `_hotkey_caka` is False). When `caka` does not hold, `registered` is
        # already final - the thread sets it BEFORE `_ready`
        # (`GlobalHotkey._hotovo`).
        ok = bool(getattr(self._hotkey, "registered", ok))
        self._ohlas_vysledok_skratky(ok)
        return ok

    def _po_registracii_skratky(self, gen, ok):
        """The registration result from the shortcut thread
        (`GlobalHotkey.on_result`), already on the Tk thread. It applies
        only when `start()` did not wait for it (`caka`) and it belongs to
        the latest registration - otherwise `start_snooze_hotkey` has
        already reported it, or it belongs to a shortcut the player has
        swapped in the meantime."""
        if gen != getattr(self, "_hotkey_gen", None) or not getattr(self, "_hotkey_caka", False):
            return
        self._hotkey_caka = False
        self._ohlas_vysledok_skratky(bool(ok))
        for meno in ("_refresh_snooze_hotkey_row", "_refresh_kamae_state_text"):
            obnov = getattr(self, meno, None)
            if callable(obnov):
                try:
                    obnov()
                except Exception:
                    app_log.exception("hotkey: %s po registracii zlyhal", meno)

    def _ohlas_vysledok_skratky(self, ok):
        """State for the Settings row (`_hotkey_zlyhala`) and one line in the
        journal - after the real result of the registration."""
        self._hotkey_zlyhala = not ok
        if ok:
            self.log(tr("log.hotkey_on",
                        combo=hotkey.format_combo(self.snooze_hotkey)))
        elif TRAY_AVAILABLE:
            # The failure is reported ONCE - `start_snooze_hotkey` is called
            # once at start - and the sentence points to the tray item, not to
            # stopping.
            self.log(tr("log.hotkey_failed_tray",
                        combo=hotkey.format_combo(self.snooze_hotkey)))
        else:
            self.log(tr("log.hotkey_failed",
                        combo=hotkey.format_combo(self.snooze_hotkey)))

    def stop_snooze_hotkey(self):
        if self._hotkey is None:
            return
        try:
            self._hotkey.stop()
        except Exception:
            app_log.exception("hotkey: zastavenie zlyhalo")
        self._hotkey = None
