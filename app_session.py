"""Heart-rate sensor and measurement session - part of the main app
(DandurfApp from app.py).

SessionMixin is a DandurfApp mixin: app.py inherits it and the whole state
(heart rate received from the watch and the connection state, the open
session and its thresholds, the activity record) lives on DandurfApp. Only
the methods that work with it through `self` are here - the mixin has no
__init__ and no attributes of its own.

Moved from app.py unchanged: the rest of the "Auto-Profile Engine
(recognising a running game)" section - it stood under that marker although
it has nothing to do with game detection (the first part of the section is
in app_profiles.py), so here it has a new marker: setting up and switching
on the sensor, opening a measurement session (world, long-term baseline,
critical heart rate, trigger thresholds, ladder rung), receiving heart rate,
steps and connection state, heart-rate dropouts, repeated binding to a busy
port, sensor status in Settings, the hidden IP, and the session and activity
ticks. The helpers `_hr_overlay_available` and
`_warn_hr_overlay_disabled_once` (cue delivery uses them) stood in the same
section. Closing the session (`_close_hr_session`) is in app_data.py.

The constant `HR_NO_CLIENT_AFTER_MS` stayed in the DandurfApp class among
the other class constants - `_schedule_no_client_check` reads it through
`self`.

Watch out in tests: `_open_hr_session`, `_apply_hr_bpm` and
`_tick_nonstop_input` read `time` from this module - a fake clock must be
patched in here too (`app_session.time`), not only on the app module.
"""

import time

import activity
import hr_stats
import measure
import netinfo
import rebrik
import theme as theme_mod
import trigger
from heart_rate import ANY_INTERFACE
from i18n import tr
from settings_model import clamp_int

from app_spolocne import app_log, stranka_vhre


def _senzor_vypla_chyba(app):
    """Port/binding failed: the sensor is switched off ONLY IN MEMORY (0.3).

    Neither a busy port nor a binding error is the player's decision. The
    switch shows off (heart rate really is not coming), but
    `_hr_vypnute_chybou` tells `save_settings` that the file should still
    say on - whichever of the dozens of places triggers the save (a slider,
    the language, quitting the app). So the next start tries receiving
    again. The flag is cleared only by the player (`on_hr_toggle`) or by a
    new attempt after an IP/port change (`on_hr_config_change`).

    A module function, not a method: `_apply_hr_status` also runs on dummies
    in tests (SimpleNamespace), which would not have a new method.
    """
    app.hr_monitoring_enabled = False
    app._hr_vypnute_chybou = True
    if app.hr_enabled_var is not None:
        app.hr_enabled_var.set(False)


# PC SLEEP (0.3, audit 4). Session ticks (`_tick_activity`, 4x per
# second) and heart-rate samples do not come during sleep/hibernation. A gap
# longer than this means the PC slept (or the app hung) - the session is
# closed at the last tick before the gap and a new one starts after it.
# Without this, a single 14-hour "session" was created and the heart rate
# during sleep went into the resting baseline.
MEDZERA_SPANKU_S = 120.0


def je_medzera_spanku(posledny, teraz, limit=MEDZERA_SPANKU_S):
    """Did the PC sleep in a gap between two session ticks? Pure function.

    A clock going BACKWARDS (time sync, manual change) is not a gap - the
    difference is negative. Neither is a broken number (None, NaN, text)."""
    try:
        rozdiel = float(teraz) - float(posledny)
    except (TypeError, ValueError):
        return False
    return rozdiel > float(limit)      # NaN is always False


def _zrus_pokus_o_vazbu(app):
    """Cancels a pending binding attempt after a busy port (`_retry_hr_bind`).

    The ONLY place where `_hr_retry_job` is discarded (0.3). Until now
    `_open_hr_session` only overwrote it with None: the timer in Tk lived on
    and a few seconds later restarted receiving - even after the sensor was
    switched off, after a port change or after watching was switched on. A
    module function, not a method: it is also called on dummies
    (SimpleNamespace) in the `_apply_hr_status` tests."""
    job = getattr(app, "_hr_retry_job", None)
    app._hr_retry_job = None
    if job is None:
        return False
    try:
        app.root.after_cancel(job)
    except Exception:
        pass
    return True


class SessionMixin:
    """Heart-rate sensor and measurement session (DandurfApp mixin)."""

    # ---------- heart-rate sensor and measurement session ----------

    def on_hr_config_change(self):
        # empty field = "listen on all networks", not "restore the original
        # value" - the player must have a way to get to that safe state even
        # after once typing a non-working address there
        ip = self.hr_ip_var.get().strip() or ANY_INTERFACE
        port = clamp_int(self.hr_port_var.get(), 1, 65535, self.hr_port)
        critical = int(self.hr_critical_bpm)      # computed, not set
        network_changed = (ip != self.hr_ip) or (port != self.hr_port)
        self.hr_ip, self.hr_port, self.hr_critical_bpm = ip, port, critical
        self.hr_stats.critical_bpm = critical
        self.hud.configure(critical_bpm=critical)
        self.hr_ip_var.set(ip)
        self.hr_port_var.set(str(port))
        self.refresh_hr_status_label()
        self.save_settings()
        if (network_changed and not self.hr_monitoring_enabled
                and getattr(self, "_hr_vypnute_chybou", False)):
            # A port or address error switched the sensor off, not the player
            # (`_senzor_vypla_chyba`). A new number in the field is exactly the
            # fix the journal advises (`log.hr_port_busy`) - we try right away,
            # without another click on the switch. A sensor switched off by the
            # player (no flag) is not switched on.
            self.hr_monitoring_enabled = True
            self._hr_vypnute_chybou = False
            if self.hr_enabled_var is not None:
                self.hr_enabled_var.set(True)
        if network_changed and self.hr_monitoring_enabled:
            self.start_heart_rate_monitor()

    def on_hr_toggle(self):
        self.hr_monitoring_enabled = bool(self.hr_enabled_var.get())
        # A click on the switch is the player's decision - what they chose
        # applies, not "on from memory" after a port error
        # (`_senzor_vypla_chyba`).
        self._hr_vypnute_chybou = False
        self.save_settings()
        if self.hr_monitoring_enabled:
            self.start_heart_rate_monitor()
        else:
            self.stop_heart_rate_monitor()

    def start_heart_rate_monitor(self):
        """Opens a new measurement session AND starts network receiving.

        When only a new session is needed (watching switched on while heart
        rate is already coming), `_open_hr_session` is called directly - a
        socket restart would briefly disconnect the app on the phone.
        """
        # A pending attempt after a busy port (`_retry_hr_bind`) belongs to the
        # PREVIOUS run. `_open_hr_session` only forgets it (None), but `after`
        # would still fire it a few seconds later - it would restart this new
        # receiving (another port, off and on), the phone would disconnect and
        # the session would open anew. The new run starts its attempts itself.
        _zrus_pokus_o_vazbu(self)
        # A new run by the player (switching on, another port) = attempts
        # after a busy port are counted from scratch. `_open_hr_session` no
        # longer resets them - otherwise every attempt itself
        # (`_retry_hr_bind`) would reset them too and the app would never
        # give up (0.3).
        self._hr_bind_retries = 0
        self._open_hr_session(meria=self.listening)
        self._hr_generation = self.heart_rate_monitor.start(self.hr_ip, self.hr_port)
        self.log(tr("log.hr_enabled", ip=self._hr_ip_display(), port=self.hr_port))
        # If not a single client connects within N seconds, say it differently
        # from "Connecting..." - "bound, but nobody connected" is a different
        # problem (most often the firewall) and the player should know (B2).
        self._schedule_no_client_check()
        # The warning about exclusive fullscreen is NOT checked HERE: at this
        # moment Zanshin is in the foreground (the player just clicked), so it
        # would never catch the game (bug A3). `_tick_session` handles it when
        # the game is in the foreground.

    def _open_hr_session(self, prepoj=True, meria=True):
        """Starts a new measurement session. Does NOT TOUCH the network.

        `prepoj=False` means "receiving is already running and heart rate is
        coming" - then the connection state must not be dropped to
        "connecting", because the window would claim it is connecting right
        now even though data is coming.
        """
        # The previous session must be CLOSED PROPERLY, not just overwritten.
        # `hr_stats.reset_session()` below erases `cues` and `_all`, so without
        # this the measurement windows would have nothing left to be built
        # from - and the only path that leads here with an open session is an
        # IP/port change in the middle of the evening (`apply_hr_settings`).
        # Measured: a whole evening of data vanished without a single line in
        # the log.
        if getattr(self, "_hr_session_open", False):
            self._close_hr_session()
        if prepoj:
            self._hr_state = "connecting"
        self._hr_last_bpm = None
        # A dropout belongs to the previous session, even when opening without
        # reconnecting (`start_listening` during a dropout). Otherwise the
        # flag would carry over into the new session and the "heart rate is
        # back" line would count from a time that `reset_session` below
        # overwrites.
        self._hr_lost = False
        self._hr_lost_od = None
        self._hr_over_since = None
        self._hr_overlay_warned = False
        # Exclusive fullscreen noticed in THIS session (0.3 batch 4) - goes
        # into the summary as `fullscreen` and the questionnaire uses it to say
        # why the pictures were not visible
        # (`_warn_exclusive_fullscreen_once`).
        self._session_fullscreen = False
        # A PENDING BINDING ATTEMPT IS NOT DISCARDED HERE (0.3). Until now
        # this had `_hr_retry_job = None` and `_hr_bind_retries = 0`: the
        # timer in Tk lived on without a reference, so neither switching the
        # sensor off nor a port change cancelled it any more, and the counter
        # was reset on every attempt (`_retry_hr_bind` opens a session) - the
        # app tried the busy port forever. The attempt is needed here: after a
        # busy port `heart_rate_monitor.running` stays True, so
        # `start_listening` does not restore the socket by itself. It is
        # cancelled by `_zrus_pokus_o_vazbu` (new run, sensor off, quitting).
        # The phone keeps the connection when we do not touch the network
        # (`prepoj=False`). Clearing the flag even then meant that after the
        # next heart-rate dropout (`disconnected`) the window, Today and the
        # guide would claim "disconnected / waiting for the phone to connect",
        # even though it is connected. Since 0.3 this also happens on the
        # first start: the pairing guide switches receiving on and watching
        # starts only after the voice preparation, in the middle of pairing.
        # The client leaving clears the flag by itself (`client_gone`).
        if prepoj:
            self._hr_client_linked = False
        self.hr_stats.critical_bpm = self.hr_critical_bpm
        # THE SESSION'S WORLD IS SEALED HERE (B3-worlds), on opening - not on
        # closing. Someone who just switches to Work in the middle of a game to
        # see the work statistics and forgets to switch back should not have
        # the game recorded as work. It goes into the summary as `world`
        # (`_close_hr_session`) and decides whether a cue may have a voice
        # (below, `open_session`).
        self._session_world = self.world
        # Resting heart rate from previous evenings. Without it the app sees no
        # load during continuous stress - the baseline catches up with the
        # stress and computes against it (see `hr_stats.dlhodoba_zakladna`).
        try:
            historia = self._history_sessions()
            # Baseline from ALL sessions - the body is one (B3-worlds).
            self.hr_stats.long_baseline = hr_stats.dlhodoba_zakladna(historia)
            # Critical heart rate and load threshold only from GAME sessions
            # (B3-worlds, see `ALGORITMUS_SVET`). Also applies to a work
            # session - there the cue is shown only as a picture anyway.
            herna = hr_stats.sessions_in_world(historia, self.ALGORITMUS_SVET)
            # The critical heart rate is recomputed ONCE PER SESSION, not
            # continuously. Changing the load scale mid-evening would mean
            # that windows from the first half and from the second cannot be
            # compared - the same rule as for the trigger thresholds (spec
            # §3.3).
            self.hr_critical_bpm = int(hr_stats.dynamicky_kriticky(
                herna, baseline=self.hr_stats.long_baseline))
            # Load threshold from the player's own sessions. None = nothing
            # to go on yet, then the numbers for the average player stay.
            self._prah_z_dat = hr_stats.dynamicky_prah_zataze(
                herna, baseline=self.hr_stats.long_baseline,
                critical=self.hr_critical_bpm)
            # The same rule as the computation (`je_dost_dlha`): a broken
            # `duration_s` must not raise an exception here, otherwise the
            # `except` below would throw away the long-term baseline too.
            self._prah_z_relacii = len([
                r for r in hr_stats.ciste_relacie(herna)
                if hr_stats.je_dost_dlha(r)])
        except Exception:
            self.hr_stats.long_baseline = None
            app_log.exception("dlhodoba zakladna / kriticky tep zlyhali")
        self.hr_stats.critical_bpm = self.hr_critical_bpm
        self.hud.configure(critical_bpm=self.hr_critical_bpm)
        self._refresh_kriticky_popis()
        self._refresh_citlivost_detail()
        self.hr_stats.reset_session()
        # Write the first few step messages to the journal - the threshold
        # is set from them.
        self._metrics_log_left = 10
        # The activity record is reset together with the session, so that
        # the measurement windows see nothing from before the sensor was
        # switched on.
        self.activity.reset_session()
        # The "no pause in input" line appears once per session.
        self._nonstop_input.reset()
        # The share of silent cues drops after calibration (25 % -> 10 %), but
        # never to zero. The number of sessions is taken from history.
        self._cue_log = []
        # The thresholds are taken ONLY HERE, i.e. only with a new session
        # (§3.3): changing them in the middle of the evening means measuring a
        # moving target.
        #
        # The order is deliberate. First the whole `trigger.default_params()`
        # dictionary - numbers for the average player from the literature, the
        # first session runs on them - so nothing old is left hanging. Then the
        # load threshold from the player's own sessions (`_prah_z_dat`, once
        # there is something to compute it from), and only then the developer
        # overlay, which is a finer tool and may override anything. (Before,
        # a "how often I speak up" choice came first; it is gone.)
        self.cue_trigger.params.update(trigger.default_params())
        if getattr(self, "_prah_z_dat", None) is not None:
            self.cue_trigger.params["stress_threshold"] = float(self._prah_z_dat)
        if getattr(self, "_dev_params", None):
            self.cue_trigger.params.update(self._dev_params)
        podiel = self._silent_share_for_next_session()
        # CUE LADDER (0.2): which rung this session runs on. Pause = the
        # state machine is not armed at all (diagnostics keep running).
        self._urci_stupen_hlasky()
        if self._cue_rung == rebrik.PAUZA:
            self.cue_trigger.params["cues_enabled"] = False
        self._snooze_po_hlaske = None
        self._snooze_rel_s = 0.0
        self._snooze_rel_od = None
        # WORK = PICTURE ONLY (B3-worlds, the author's decision). Whoever is
        # concentrating at work should not have anything talking or chiming at
        # them - a visual in the corner of the eye is enough. Applies to the
        # whole session by the world it started in.
        # Below the voice rung (ladder) also picture only - `hlas` in the event
        # thus tells the truth about what could have been heard.
        self.cue_trigger.open_session(silent_share=podiel,
                                      voice=self._session_world != "work"
                                      and self._cue_rung == rebrik.HLAS)
        # "NOT NOW" ALSO HOLDS ACROSS A NEW SESSION. `open_session` lifts the
        # state machine's suspension - and a new session can also be opened
        # during a snooze (stop and start, sensor switched on, IP change),
        # since snooze no longer stops listening (24. 9.).
        if getattr(self, "_snooze_job", None) is not None:
            self._suspend_cue_trigger(trigger.A_SNOOZE)
            # Also into the new session's `snoozed_s` - from its start.
            if meria:
                self._snooze_rel_od = time.time()
        # MEASURING ONLY WHEN THE GREEN IS LIT.
        #
        # `hr_stats.add()` runs on every sample whether or not the app is
        # listening - so a session opened BY JUST SWITCHING ON THE SENSOR
        # would collect duration, zones and baseline from time in which a cue
        # could not fire. In the export that would become a "session" in which
        # nothing was measured, and in the count of evenings towards the
        # conclusion it would count as a full one.
        #
        # So `meria=False` lets the sensor run (so the heart rate is visible
        # during pairing), but does NOT OPEN the session. Only
        # `start_listening` opens it.
        self._hr_session_open = bool(meria)
        if meria:
            # New session: reset the HUD visibility tracker.
            self._hud_vis_s = 0.0
            self._hud_active_s = 0.0
            self._hud_tick_t = time.time()
            # From this time the gap between ticks is measured (PC sleep,
            # `_hlidaj_medzeru_relacie`).
            self._posledny_tik_relacie = self._hud_tick_t
        # While a session is open, "Delete history" is disabled (0.3).
        obnov = getattr(self, "_refresh_data_delete_state", None)
        if callable(obnov):
            try:
                obnov()
            except Exception:
                app_log.exception("tlacidlo Zmazat historiu sa neobnovilo")
        if prepoj:
            self.hud.set_connected(False)
        self.hud.configure(critical_bpm=self.hr_critical_bpm)
        self.refresh_hr_status_label()

    def stop_heart_rate_monitor(self):
        self.heart_rate_monitor.stop()
        self._cancel_no_client_check()
        # Otherwise the attempt after a busy port would restart receiving a few
        # seconds later (`_retry_hr_bind` only checks `hr_monitoring_enabled`,
        # and that may have been switched on again in the meantime).
        _zrus_pokus_o_vazbu(self)
        self._hr_bind_retries = 0
        # generation 0 = no running thread, so updates already sent (and not
        # yet delivered) from the thread just stopped are thrown away
        self._hr_generation = 0
        self._hr_state = "disconnected"
        self._hr_last_bpm = None
        self._hr_over_since = None
        self._hr_client_linked = False
        # The player switched the sensor off - that is no longer a dropout. The
        # session is closed only below, so a dropout that was just going on is
        # still counted into the summary.
        self._hr_lost = False
        self._hr_lost_od = None
        self._close_hr_session()
        self.hud.set_connected(False)
        self.hr_stats.clear_live()
        self.refresh_hr_status_label()
        # Today and the bar show the status by receiving ("heart-rate
        # receiving off"), not "waiting for the watch" - after switching off
        # they must be rewritten right away, not only at the next event from
        # the watch, which will not come any more.
        self._refresh_dnes_stats()
        self._refresh_kamae_state_text()
        self.log(tr("log.hr_disabled"))

    def _schedule_no_client_check(self):
        self._cancel_no_client_check()
        try:
            self._hr_no_client_job = self.root.after(
                self.HR_NO_CLIENT_AFTER_MS, self._hr_no_client)
        except Exception:
            self._hr_no_client_job = None

    def _cancel_no_client_check(self):
        job = getattr(self, "_hr_no_client_job", None)
        if job is not None:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
            self._hr_no_client_job = None

    def _hr_no_client(self):
        self._hr_no_client_job = None
        # Still "connecting" and nobody connected → say it plainly.
        if self._hr_state == "connecting" and self.hr_monitoring_enabled:
            self._hr_state = "no_client"
            self.refresh_hr_status_label()
            # The bar and Today say "phone didn't connect" and where to
            # look for advice - before, only the label by the switch on the
            # In game page changed.
            self._refresh_kamae_state_text()
            self._refresh_dnes_stats()

    def _hr_ip_display(self):
        """IP for the line in the app journal - hidden until the player reveals
        it (0.0.0.0 is not hidden, it is not the PC's address)."""
        ip = self.hr_ip if self.hr_ip.strip() else ANY_INTERFACE
        return netinfo.ip_for_screen(ip, self.show_ip)

    def set_show_ip(self, show):
        """Show / Hide IP for the whole app (pairing window and the IP field in
        Settings). Only in memory - after a restart the IP is hidden again,
        which is why `save_settings` DELIBERATELY does not write it."""
        self.show_ip = bool(show)
        var = getattr(self, "show_ip_var", None)
        if var is not None:
            try:
                if bool(var.get()) != self.show_ip:
                    var.set(self.show_ip)
            except Exception:
                pass
        self._apply_hr_ip_mask()

    def _apply_hr_ip_mask(self):
        """The IP field in Settings draws the real address as dots unless
        `show_ip` is set. An empty field and 0.0.0.0 stay readable.

        The "Show IP" switch next to the field is visible ONLY with a real
        address (0.3). With the default 0.0.0.0 it had nothing to reveal -
        the player switched it on, expected the PC's address and nothing
        happened. The PC's address is shown by the pairing guide (it has its
        own "Show IP"), not by this field."""
        entry = getattr(self, "hr_ip_entry", None)
        var = getattr(self, "hr_ip_var", None)
        if entry is None or var is None:
            return
        try:
            hodnota = var.get()
            maska = netinfo.entry_mask(hodnota, self.show_ip)
            if str(entry.cget("show")) != maska:
                entry.configure(show=maska)
            prepinac = getattr(self, "hr_ip_show_switch", None)
            if prepinac is not None:
                # `entry_mask(..., False)` is empty exactly when there is
                # nothing to hide in the field - the same definition of
                # "address" as the mask.
                ukaz = netinfo.entry_mask(hodnota, False) != ""
                zobrazeny = bool(prepinac.winfo_manager())
                if ukaz and not zobrazeny:
                    prepinac.pack(side="left", padx=(12, 0))
                elif not ukaz and zobrazeny:
                    prepinac.pack_forget()
            self._hr_ip_virtual_hint(hodnota)
        except Exception:
            pass            # the field no longer exists (UI rebuild)

    def _hr_ip_virtual_hint(self, hodnota, virtualne=None):
        """Does the address in the IP field belong to a VPN or virtual adapter
        (0.3)? Then the explanation under the field gets a sentence that the
        phone (the app that sends heart rate from the watch) usually cannot
        reach it. The Windows mobile hotspot and an external Hyper-V switch
        with the home network do not count as virtual
        (`netinfo.druhy_adries`, 0.3 batch 4b). Returns whether the sentence
        applies. `virtualne` (a set of IPs) can be passed in (tests); by
        default it asks `netinfo`."""
        hodnota = str(hodnota or "").strip()
        if virtualne is None:
            virtualne = netinfo.virtualne_adresy() if netinfo.entry_mask(hodnota, False) else set()
        plati = hodnota in virtualne
        label = getattr(self, "hr_ip_hint_label", None)
        if label is not None:
            text = tr("settings.hr_ip_hint")
            if plati:
                text += "\n" + tr("settings.hr_ip_virtual_note")
            try:
                if label.cget("text") != text:
                    label.configure(text=text)
            except Exception:
                pass
        return plati

    def on_hr_bpm(self, bpm, generation):
        self.ui_call(lambda: self._apply_hr_bpm(bpm, generation))

    def _apply_hr_bpm(self, bpm, generation=None):
        if generation is not None and generation != self._hr_generation:
            return                      # a message from an already stopped thread
        # A sample after the PC slept already belongs to a new session
        # (`_hlidaj_medzeru_relacie`). Dummies in tests do not have this method.
        hlidac = getattr(self, "_hlidaj_medzeru_relacie", None)
        if callable(hlidac):
            try:
                hlidac()
            except Exception:
                app_log.exception("relacia: kontrola medzery po uspani zlyhala")
        self._hr_state = "connected"
        self._hr_bind_retries = 0       # the port was freed, counter starts over
        self._hr_last_bpm = bpm
        self.hr_stats.add(bpm)
        # The dropout ends only with a VALID sample - the same one that closes
        # the blind time in `hr_stats`, so the journal line and the summary do
        # not say different things.
        if self._hr_lost and self.hr_stats.last_bpm is not None:
            self._tep_je_spat()
        self.hud.set_connected(True)
        self._refresh_hud_session_text()
        self._refresh_dnes_stats()
        self.refresh_hr_status_label()
        # The bar flips from "Čakám na tep" (Waiting for heart rate) to
        # "Sledujem tep" (Watching your heart rate) as soon as data comes in
        # (bug A2 - until then the bar was redrawn only from
        # `_set_enso_armed`).
        self._refresh_kamae_state_text()
        now = time.time()
        # Phase 2: the trigger is LOAD holding above the threshold, not raw
        # BPM crossing the critical limit. The load already carries
        # `sustained` - the share of the last two minutes above the
        # baseline - so "a spike after a headshot is not stress" is built
        # into the number itself, not glued on.
        # LOAD IS FED TO THE STATE MACHINE ONLY DURING A SESSION.
        #
        # This was called on every sample, even when no session was running
        # (sensor on, listening off). So the state machine armed, the ring on
        # the enso lit up - and `_tick_cue_trigger` returned right away
        # because of `_hr_session_open`, so nothing could clear it any more.
        # The "armed" ring then stayed lit forever and claimed a state that
        # did not exist.
        if not self._hr_session_open:
            return
        self.cue_trigger.resume(now)
        # During calibration (the first ~30 samples of the session) nothing
        # arms - see `trigger.CueTrigger.note_load`.
        # `zona` is for the cue GATE (0.2): the HEART-RATE zone
        # (`zone_of_bpm`, the same word as on the HUD), None when the app does
        # not know it. Never the load zones - above the high heart-rate limit
        # the voice is not heard.
        udalost = self.cue_trigger.note_load(
            self.hr_stats.stress, now,
            calibrating=self.hr_stats.is_calibrating,
            zona=self.hr_stats.known_zone)
        if udalost is not None:
            self._on_cue_event(udalost)

    def on_hr_metrics(self, metrics, generation):
        self.ui_call(lambda: self._apply_hr_metrics(metrics, generation))

    def _apply_hr_metrics(self, metrics, generation=None):
        """Watch steps and speed. Runs on the Tk thread like `_apply_hr_bpm`."""
        if generation is not None and generation != self._hr_generation:
            return
        try:
            self.hr_stats.note_metrics(steps=metrics.get("steps"),
                                       speed=metrics.get("speed"),
                                       zdroj=metrics.get("zdroj"))
        except Exception:
            app_log.exception("kroky z hodiniek sa nepodarilo zapisat")
            return
        if self._metrics_log_left > 0:
            self._metrics_log_left -= 1
            app_log.info("hodinky posielaju [%s]: kroky=%s rychlost=%s "
                         "(za minutu %s)", metrics.get("zdroj") or "bez mena",
                         metrics.get("steps"), metrics.get("speed"),
                         self.hr_stats.steps_per_min())

    def on_hr_status(self, status, generation):
        self.ui_call(lambda: self._apply_hr_status(status, generation))

    def _apply_hr_status(self, status, generation=None):
        if generation is not None and generation != self._hr_generation:
            return                      # a message from an already stopped thread
        kind, payload = status
        if kind == "bound_any":
            # this PC does not have the given IP - we listen on all networks,
            # so the feature does not die for the player over one wrong number
            self.log(tr("log.hr_bind_fallback",
                        ip=netinfo.ip_for_screen(payload, self.show_ip)))
            return
        if kind in ("udp_busy", "udp_error"):
            # UDP DID NOT OPEN, TCP IS RUNNING. Not "busy"/"error" below: those
            # close the session and switch the sensor off, but the apps for OBS
            # (TCP) keep working here and must not lose the heart rate. A line
            # in the journal and its own text by the switch
            # (`_hr_status_display`) are enough.
            # The flag carries the run's generation: ONCE per run, and a new
            # run (restart, another port, another attempt after a busy TCP)
            # discards it by itself - no need to reset it by hand everywhere
            # `start()` is called.
            if getattr(self, "_hr_udp_off_gen", None) == self._hr_generation:
                return
            self._hr_udp_off_gen = self._hr_generation
            if kind == "udp_busy":
                self.log(tr("log.hr_udp_busy", port=payload))
            else:
                port, err = payload
                self.log(tr("log.hr_udp_error", port=port, err=err))
            self.refresh_hr_status_label()
            return
        if kind == "two_series":
            # TWO DIFFERENT HEART RATES COME INTO ONE SOURCE (0.3, detected by
            # `heart_rate.dva_rady_v_okne`). Measuring and the connection are
            # not touched - heart rate keeps coming and the fix is in the app
            # on the watch. A journal line and the text by the switch
            # (`_hr_status_display`), ONCE per run just like UDP above: the
            # flag carries the generation, a new run (switch-off, restart,
            # another port) discards it by itself.
            if getattr(self, "_hr_dva_tepy_gen", None) == self._hr_generation:
                return
            self._hr_dva_tepy_gen = self._hr_generation
            self.log(tr("log.hr_two_series", source=payload))
            self.refresh_hr_status_label()
            return
        if kind == "client":
            # the app on the phone holds the connection - that does NOT yet
            # mean heart rate is coming (the watch may not be measuring, or
            # may not be near the phone)
            self._cancel_no_client_check()      # client arrived (B2)
            self._hr_client_linked = True
            self._hr_state = "linked"
            self.log(tr("log.hr_client_connected"))
        elif kind == "client_gone":
            self._zaznamenaj_vypadok(kind)      # BEFORE clear_live
            self.hud.set_connected(False)
            self.hr_stats.clear_live()
            self._hr_client_linked = False
            self._hr_state = "connecting"
            self._hr_last_bpm = None
            self._hr_over_since = None
            self._suspend_cue_trigger(trigger.A_TEP_VYPADOL)
            self.log(tr("log.hr_client_gone"))
        elif kind == "connecting":
            self._hr_state = "connecting"
            self._hr_last_bpm = None
        elif kind == "disconnected":
            # heart rate stopped coming; if the phone still holds the
            # connection, it is "connected, but no data", not "disconnected" -
            # a different problem, a different text
            self._zaznamenaj_vypadok(kind)      # BEFORE clear_live
            self.hud.set_connected(False)
            self.hr_stats.clear_live()
            self._hr_state = "linked" if self._hr_client_linked else "disconnected"
            self._hr_last_bpm = None
            self._hr_over_since = None
            self._suspend_cue_trigger(trigger.A_TEP_VYPADOL)
        elif kind == "busy":
            # A BUSY PORT IS A TEMPORARY STATE, NOT THE PLAYER'S DECISION.
            #
            # Until now this landed here together with "error": the app
            # switched `hr_monitoring_enabled` off and SAVED it to disk right
            # away. A collision that lasts a few seconds (a second app instance
            # is just closing, or someone started it twice by mistake) thus
            # became a permanent setting - the sensor stayed off even after the
            # port was freed, and the player had no way to find out why. The
            # only signal was a line in the JOURNAL, which is collapsed by
            # default.
            #
            # Now the switch is left on, nothing is saved to settings and the
            # binding is retried a few times. Only when someone holds the port
            # permanently does the sensor give up - and then it really is a
            # state worth telling the player about.
            self._hr_state = "busy"
            self._hr_last_bpm = None
            self._hr_over_since = None
            self._hr_client_linked = False
            self._hr_lost = False           # port, not a heart-rate dropout
            self._hr_lost_od = None
            self._hr_generation = 0
            self._close_hr_session()
            self._hr_bind_retries = getattr(self, "_hr_bind_retries", 0) + 1
            # Never two attempts at once: the old pending one is cancelled
            # before a new one is scheduled (0.3).
            _zrus_pokus_o_vazbu(self)
            if self._hr_bind_retries <= self.HR_BIND_RETRIES:
                self.log(tr("log.hr_port_busy_retry", port=payload,
                            n=self._hr_bind_retries, z=self.HR_BIND_RETRIES))
                self._hr_retry_job = self.root.after(
                    self.HR_BIND_RETRY_MS, self._retry_hr_bind)
            else:
                # Giving up is NOT the player's decision either (0.3): the
                # switch shows off only for this run, the settings still get
                # on - the next start tries again. Before 0.3 the switch-off
                # was saved here, and a second running copy of the app thus
                # switched off heart-rate receiving for the first one for
                # good (shared settings file).
                _senzor_vypla_chyba(self)
                # The state MUST change from "busy" - otherwise the label
                # claims "retrying" forever, even though we gave up (B3).
                self._hr_state = "busy_gave_up"
                # page name by world ("Screen" in Work, 0.3 batch 4b)
                self.log(tr("log.hr_port_busy", port=payload, page=stranka_vhre(self)))
            self.refresh_hr_status_label()
            self._refresh_dnes_stats()
            self._refresh_kamae_state_text()   # the bar must not claim "watching"
            return
        elif kind == "error":
            self._hr_state = "disconnected"
            self._hr_last_bpm = None
            self._hr_over_since = None
            self._hr_client_linked = False
            self._hr_lost = False           # the sensor is off, not blind
            self._hr_lost_od = None
            # A binding error (e.g. a port reserved by Windows, or an address
            # the PC does not have, where even the fallback to 0.0.0.0 in
            # `heart_rate._bind` did not help) is NOT the player's decision -
            # switched off only in memory, the next start tries again (same as
            # "busy" above).
            _senzor_vypla_chyba(self)
            # Otherwise an attempt after an earlier busy port would restart
            # receiving a few seconds later, although the sensor is off after
            # the error (0.3).
            _zrus_pokus_o_vazbu(self)
            # The switch has just turned off, but the session stayed OPEN: it
            # could no longer be ended via `stop_heart_rate_monitor` (only
            # `on_hr_toggle` calls that, and the switch is already in the off
            # position), so it was saved only when the app quit - and
            # `summary()` meanwhile computed `duration_s` from `time.time()`,
            # i.e. the session grew by the whole rest of the evening. We close
            # it here while the numbers are still true.
            # Generation 0 also throws away messages from the already dead
            # thread.
            self._hr_generation = 0
            self._close_hr_session()
            self.log(tr("log.hr_socket_error", err=payload))
        self.refresh_hr_status_label()
        self._refresh_dnes_stats()
        # The bar and the text under the enso must both follow the REAL
        # connection state (connecting / disconnected / client_gone), not just
        # the switch — otherwise they claim "Sledujem tep" (Watching your
        # heart rate) even when the watch dropped out (bug A2).
        self._refresh_kamae_state_text()

    def _zaznamenaj_vypadok(self, kind):
        """Heart rate that the app was hearing stopped coming - remember that.

        Called from the `disconnected` and `client_gone` branches BEFORE
        `clear_live` (after that `hr_stats` no longer knows when the last
        sample came). Only when the app really heard the heart rate: a
        dropout before the first sample is "nothing has come yet" and has
        its own text. Both events may come one after the other (the TCP
        connection drops only after 12 s of silence, or the other way
        round) - the second no longer has `_hr_last_bpm`, so the same
        dropout is not counted twice.

        NO NEW TIMER, SOUND OR WINDOW. The 12 s limit is the same as before
        (`heart_rate.STALE_AFTER_S`); here it just stops pretending the
        watch was never even paired (Today keeps the live block and the
        session trace).
        """
        if self._hr_last_bpm is None:
            return
        self._hr_lost = True
        self._hr_lost_od = self.hr_stats.last_beat_ts
        try:
            self.hr_stats.note_dropout(od=self._hr_lost_od)
        except Exception:
            app_log.exception("vypadok tepu sa nepodarilo zapisat")
        app_log.info("tep vypadol (%s)", kind)

    def _tep_je_spat(self):
        """First valid sample after a dropout: one journal line, no more."""
        od = self._hr_lost_od
        self._hr_lost = False
        self._hr_lost_od = None
        if od is None:
            return
        sekund = max(0, int(round(self.hr_stats.last_beat_ts - od)))
        self.log(tr("log.hr_back", s=sekund))
        app_log.info("tep je spat po %d s", sekund)

    # NOTE: `_maybe_trigger_hr_breathing` was here - the old automatic trigger
    # from phase 1 (heart rate above critical for 5 s → breathing circle).
    # Nothing called it any more; `trigger.CueTrigger` replaced it (load above
    # the threshold for 90 s, postponed to a pause). Deleted together with the
    # HR_TRIGGER_* constants (B28). The helpers `_hr_overlay_available` /
    # `_warn_hr_overlay_disabled_once` stay - the live cue path uses them.

    def _hr_overlay_available(self):
        """True if at least ONE slot has an in-game visual switched on.

        Until 19. 9. it asked exclusively about slot 3 (breathing circle).
        That was right while all cues went to that one slot - but since
        category rotation was introduced (`_dalsi_cue_slot`) a cue can be
        delivered to any of the four. So the gate allowed a cue when the
        breathing circle was running, and sent it to a slot that was not
        supposed to draw - or the other way round silenced an app that had
        three visuals switched on and only the fourth not.

        The choice itself already takes into account whether the visual is
        on, so here it is enough that at least one usable one exists.
        """
        try:
            return any(bool(cfg["enabled"]) for cfg in self.overlay_configs)
        except (KeyError, TypeError):
            return False

    def _warn_hr_overlay_disabled_once(self):
        if self._hr_overlay_warned:
            return
        self._hr_overlay_warned = True
        self.log(tr("log.hr_overlay_disabled", page=stranka_vhre(self)))

    def _retry_hr_bind(self):
        """Tries again to open receiving after a busy TCP port ("busy").

        A busy UDP port does NOT LEAD here - it has its own branch in
        `_apply_hr_status` ("udp_busy") and is not retried; TCP keeps
        running.

        Does not call `on_hr_toggle` - the switch is still on and must not
        move. Opens a new socket directly, the same as `_open_hr_session`
        at start.
        """
        self._hr_retry_job = None
        if not self.hr_monitoring_enabled:
            return                      # the player switched it off meanwhile
        try:
            self._hr_state = "connecting"
            self.refresh_hr_status_label()
            self._hr_generation = self.heart_rate_monitor.start(self.hr_ip,
                                                                self.hr_port)
            # THE SOCKET IS BACK - BUT THE SESSION CLOSED IN THE "busy" BRANCH.
            #
            # Without this the app would show a live heart rate after the port
            # was restored, but `_hr_session_open` would stay False -
            # `_tick_cue_trigger` returns right away with a closed session, so
            # it would NEVER speak up and would save NOTHING at the end. And
            # the bar promises "watching" all along. We open it anew (this does
            # not touch the network; `start()` has already restored it), the
            # same as at start. Data from before the dropout is already saved
            # (the `busy` branch calls `_close_hr_session`, which saves).
            self._open_hr_session(prepoj=False, meria=self.listening)
            self._schedule_no_client_check()   # a fresh 20 s for the client (B2)
        except Exception:
            app_log.exception("opakovana vazba na port tepu zlyhala")

    def _hr_status_display(self):
        pal = self.pal
        if self._hr_state == "connected" and self._hr_last_bpm is not None:
            # THE NUMBER IS SMOOTHED (0.3) - the same as on the HUD and on
            # Today (`HeartStats.display_bpm`). Whether it is shown is still
            # decided by the raw `_hr_last_bpm`; without `hr_stats` (dummies)
            # it stays raw.
            tep = getattr(getattr(self, "hr_stats", None), "display_bpm", None)
            if tep is None:
                tep = self._hr_last_bpm
            if (self._hr_generation
                    and getattr(self, "_hr_dva_tepy_gen", None) == self._hr_generation):
                # Two heart-rate streams in one source. Only when heart rate is
                # coming - without data the real connection state takes
                # precedence (and UDP below), because that is what the player
                # needs to know right now. The number stays, the text is added
                # after it.
                return (f"❤️ {tep} BPM · {tr('settings.hr_status_two_series')}",
                        pal["warn"])
            # zone colours, not success/danger - otherwise the heart-rate
            # status would glow a different green than the one the app draws
            # calm with (see theme.ZONE_TOKENS)
            zone = "critical" if tep > self.hr_critical_bpm else "calm"
            return f"❤️ {tep} BPM", theme_mod.zone_color(pal, zone)
        if self._hr_state == "linked":
            return tr("settings.hr_status_waiting"), pal["warn"]
        if self._hr_state == "busy":
            # Its own state, not "Disconnected": the player sees exactly what
            # is going on, right by the switch, and does not have to expand the
            # journal.
            return tr("settings.hr_status_busy"), pal["warn"]
        if self._hr_state == "busy_gave_up":
            # Attempts used up - it no longer tries, so it no longer claims to
            # (B3). Small text: `danger_text` (>= 4,5:1), not `danger`
            # (theme.py).
            return tr("settings.hr_status_busy_gave_up"), pal["danger_text"]
        if (self._hr_state in ("connecting", "no_client") and self._hr_generation
                and getattr(self, "_hr_udp_off_gen", None) == self._hr_generation):
            # UDP did not open in this run. While nobody has connected, this is
            # the most likely reason for apps that send only UDP/OSC (iPhone) -
            # without it the player would see only "Connecting...". Once the
            # phone holds a TCP connection or heart rate is coming, UDP is
            # missed by nobody and the label shows the real connection state.
            return tr("settings.hr_status_udp_off"), pal["warn"]
        if self._hr_state == "connecting":
            return tr("settings.hr_status_connecting"), pal["text_dim"]
        if self._hr_state == "no_client":
            # We are listening, but nobody connected within N s - a different
            # problem from "connecting" (most often the firewall / another
            # Wi-Fi) (B2).
            return tr("settings.hr_status_no_client"), pal["warn"]
        return tr("settings.hr_status_disconnected"), pal["text_dim"]

    def refresh_hr_status_label(self):
        if self.hr_status_label is None:
            return
        text, color = self._hr_status_display()
        try:
            self.hr_status_label.configure(text=text, text_color=color)
        except Exception:
            pass

    def _hlidaj_medzeru_relacie(self, teraz=None):
        """Session tick or heart-rate sample: a long gap since the last one?

        Called from `_tick_activity` (4x per second) and from `_apply_hr_bpm`
        BEFORE the sample is written - so a sample after waking up already
        belongs to a new session. The gap is counted only while watching
        with an open session; the time always moves on, so that a session
        opened later does not measure from an old tick. A clock going
        backwards only moves the starting point (`je_medzera_spanku`).
        Returns True when it split the session."""
        teraz = time.time() if teraz is None else float(teraz)
        posledny = getattr(self, "_posledny_tik_relacie", None)
        self._posledny_tik_relacie = teraz
        if not (getattr(self, "listening", False)
                and getattr(self, "_hr_session_open", False)):
            return False
        if posledny is None or not je_medzera_spanku(posledny, teraz):
            return False
        self._rozdel_relaciu_po_medzere(posledny, teraz)
        return True

    def _rozdel_relaciu_po_medzere(self, posledny, teraz):
        """The PC slept: the session ends at the LAST TICK before the gap and a
        new one starts after it, if watching is still on and receiving runs.

        It is saved the usual way (`_close_hr_session(koniec=...)`), so
        everything applies as elsewhere - a short session is not saved,
        nothing is learned from sleep, the checkpoint is deleted. No
        questionnaire (the player was not there). One line to the journal."""
        minut = max(1, int(round((float(teraz) - float(posledny)) / 60.0)))
        app_log.info("relacia: %d s bez tiku (PC asi spalo) - relacia sa rozdeli",
                     int(float(teraz) - float(posledny)))
        try:
            self._close_hr_session(koniec=posledny)
        except Exception:
            app_log.exception("relacia sa po uspani PC nezatvorila")
        nova = False
        if (getattr(self, "listening", False)
                and getattr(self, "hr_monitoring_enabled", False)
                and not getattr(self, "_hr_session_open", False)):
            try:
                if self.heart_rate_monitor.running:
                    # Receiving keeps running, we do not touch the network
                    # (like `start_listening`).
                    self._open_hr_session(prepoj=False, meria=True)
                    nova = bool(getattr(self, "_hr_session_open", False))
            except Exception:
                app_log.exception("nova relacia po uspani PC sa neotvorila")
        self.log(tr("log.session_split_sleep" if nova else "log.session_split_sleep_end",
                    min=minut))
        return nova

    def _tick_session(self):
        """Once a second refreshes "last spoke X min ago" and, with an open
        session, checks for exclusive fullscreen.

        Alongside it `_tick_activity` also runs (4x per second); everything
        else is redrawn only based on incoming data.

        NOTE: `_refresh_kamae_metrics()` was also here - three numbers on the
        right of the bar. With their removal (see `ui_kit.KamaeBar`) the bar
        no longer has anything to move every second.
        """
        try:
            # "Last spoke X min ago" is computed from `time.time()` only on
            # redraw. All other paths to `_refresh_dnes_stats` hang on incoming
            # heart rate, so without this line the number stopped at the value
            # from before the last sample and did not move any more - and after
            # a watch dropout it lied forever.
            self._refresh_last_cue()
        except Exception:
            pass
        # Exclusive fullscreen: Windows does not draw our overlay windows in
        # it, so the visual (the core of the app) silently disappears. The
        # check makes sense ONLY when the game is in the foreground — which
        # during a session it mostly is, and it never is during
        # `start_heart_rate_monitor`, where the check originally was and was
        # therefore dead (bug A3). Once per app start (the `_fullscreen_warned`
        # flag is not reset) - and only as a guess: a borderless window is the
        # same size too, which is why the text says "if you cannot see the
        # visuals".
        if getattr(self, "_hr_session_open", False):
            try:
                self._warn_exclusive_fullscreen_once()
            except Exception:
                pass
        try:
            self.root.after(1000, self._tick_session)
        except Exception:
            pass

    def _tick_activity(self):
        """Asks Windows 4x per second how long the player has been idle.

        It is one `GetLastInputInfo` - no hook, no information about what
        the player pressed. It runs outside a session too, so that
        `pause_s()` makes sense right when the sensor is switched on; the
        record for the measurement windows is reset anyway when the sensor
        is switched on.

        The `after` id is kept so it can be cancelled on quit - otherwise,
        at 4x per second, the chance would grow that a callback runs only
        after the window has already been dismantled.
        """
        # PC sleep: the first tick after waking up came after a long gap.
        try:
            self._hlidaj_medzeru_relacie()
        except Exception:
            app_log.exception("relacia: kontrola medzery po uspani zlyhala")
        try:
            idle = self.activity.poll()
        except Exception:
            idle = None
        # Activity curve into the session - later it is used to compute when
        # the player was really playing and when sitting in a menu. It is
        # written ONLY during a session, like everything else: outside it, it
        # would only dilute the average with time when the player is not even
        # using the app.
        if idle is not None and getattr(self, "_hr_session_open", False):
            try:
                self.hr_stats.note_activity(idle <= measure.ACTIVE_IDLE_MS)
            except Exception:
                pass
        try:
            self._tick_nonstop_input()
        except Exception:
            app_log.exception("vstup bez pauzy: tick zlyhal")
        try:
            self._tick_cue_trigger()
        except Exception:
            app_log.exception("spustac hlasky: tick zlyhal")
        try:
            self._activity_job = self.root.after(
                int(activity.POLL_S * 1000), self._tick_activity)
        except Exception:
            self._activity_job = None

    def _tick_nonstop_input(self, now=None):
        """A quiet line on Today when the app has not seen even a short pause
        in input for a long time (`activity.NonstopInputWatch`).

        It happened to the author: the controller's gyroscope reported
        input to Windows every ~16 ms and the app never had a chance to find
        a pause. It is counted only while the app is listening and heart rate
        is coming (the player is at the PC). ONLY on Today - not in game, not
        in the HUD; the player sees it when they look at the app themselves.
        """
        now = time.time() if now is None else now
        watching = bool(self.listening
                        and getattr(self, "_hr_session_open", False)
                        and self._hr_state == "connected"
                        and self._hr_last_bpm is not None
                        and not getattr(self, "_hr_lost", False))
        try:
            potrebna = float(self.cue_trigger.params.get("pause_s", 2.5))
        except Exception:
            potrebna = 2.5
        ukaz = self._nonstop_input.update(
            now, self.activity.pause_s(now), watching, pause_needed_s=potrebna)
        text = ""
        if ukaz and self.listening:
            text = tr("dnes.nonstop_input",
                      min=int(self._nonstop_input.after_s // 60))
        if text != getattr(self, "_dnes_nonstop_text", ""):
            if text:
                app_log.info("vstup: %d min bez jedinej pauzy - riadok na Dnes",
                             int(self._nonstop_input.after_s // 60))
            self._dnes_nonstop_text = text
            self._refresh_dnes_backdrop(force=False)
