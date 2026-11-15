"""App controls - part of the main app (DandurfApp from app.py).

ControlsMixin is a mixin of DandurfApp: app.py inherits it and all the state
(palette, "not now", journal, slots, controller, overlay) lives on
DandurfApp. Here are only the methods that work with it through `self` - the
mixin has no __init__ and no attributes of its own.

Four sections moved from app.py unchanged:
  * command palette (Ctrl+K) - the action palette and replaying the
    introduction,
  * quick dock - "not now" (toggle from the shortcut and from the tray,
    snoozing cues, status dot) and collapsing the journal. Registering the
    shortcut (`start_snooze_hotkey` / `stop_snooze_hotkey`) stayed in app.py
    next to the tray - it reads TRAY_AVAILABLE, which is computed in app.py,
  * rebind - only a marker, rebind left in phase 3,
  * gamepad (NO LONGER as a trigger) - activity from the controller and
    firing a cue manually (Test button, click in the HUD preview).

WARNING for tests: `_start_snooze`, `_snooze_do`, `_zapocitaj_snooze` and
`fire_slot` read `time` from this module (`fire_slot` also `threading`) - a
fake clock has to be injected here too (`app_controls.time`), not only on the
app module.
"""

import os
import threading
import time

import rebrik
import theme as theme_mod
import trigger
from i18n import tr
from settings_model import ENGINE_EDGE, mode_labels
from ui_dialogs import OnboardingWizard
from ui_shell import CommandPalette

from app_spolocne import SNOOZE_HOTKEY_MINUTES, app_log


class ControlsMixin:
    """Command palette, "not now", journal, controller (DandurfApp mixin)."""

    # ---------- command palette (Ctrl+K) ----------

    def open_command_palette(self):
        """Builds the palette from scratch, with the current list of actions,
        every time it opens - so it never goes stale, not even after
        slots/profiles change outside the full _build_ui
        (add_slot/switch_profile do not call it)."""
        # The previous palette has to be closed, otherwise it stays hanging on
        # top of everything (it is topmost) and nothing closes it anymore - the
        # instance used to be thrown away in a local variable, so its own
        # single-instance safeguard had nothing to guard.
        previous = getattr(self, "_palette", None)
        if previous is not None:
            try:
                previous.close()
            except Exception:
                pass
        # `pal=self.pal`: without it the palette took its colours from the
        # module's SHELL_PAL, i.e. from a different colour family than the rest
        # of the window (see CommandPalette).
        self._palette = CommandPalette(self.root, self._command_palette_items(),
                                       pal=self.pal,
                                       placeholder=tr("palette.placeholder"))
        self._palette.open()

    def _command_palette_items(self):
        # All palette texts go through i18n - they used to be hard-coded in
        # Slovak here, so an English player saw "Navigácia" and "Pomoc" in an
        # otherwise English window. The guide is named the same as its panel
        # (guide.panel_title). That one has no emoji anymore (0.3 batch 4,
        # guarded by test_022e_nastavenia), so there is no need to strip it.
        pomoc = tr("palette.cat.help")
        navigacia = tr("palette.cat.nav")
        appka = tr("palette.cat.app")
        profily = tr("palette.cat.profiles")
        sprievodca = tr("guide.panel_title")
        items = [
            (tr("palette.replay_intro"), pomoc, self.replay_onboarding),
            (tr("nav.dnes"), navigacia, lambda: self.sidebar._select("dnes")),
            (tr("nav.historia"), navigacia, lambda: self.sidebar._select("historia")),
            (tr("nav.spustace"), navigacia, lambda: self.sidebar._select("spustace")),
            (tr("nav.zvuk"), navigacia, lambda: self.sidebar._select("zvuk")),
            # in the "Work" world "Watch and screen" (`_nazov_vhre`, 0.3)
            (self._nazov_vhre(dlhy=True), navigacia, lambda: self.sidebar._select("vhre")),
            (tr("nav.nastavenia"), navigacia, lambda: self.sidebar._select("nastavenia")),
            (sprievodca, pomoc, self.open_guide_panel),
            (tr("common.prepare_voices"), tr("palette.cat.sound"),
             lambda: self.pregenerate(force=True)),
            # "Update voice" (0.3) - only with the natural voice, same as the
            # button (the Windows voice sends nothing, not even a test word).
            # Goes to Settings → Sound, which shows the update status and any
            # link to a new release. While watching it does not go to the
            # network (`aktualizuj_hlas`); it never starts by itself.
            *([(tr("edge.update.btn"), tr("palette.cat.sound"),
                lambda: (self.sidebar._select("zvuk"), self.aktualizuj_hlas()))]
              if getattr(self, "engine", None) == ENGINE_EDGE else []),
            # The item says what WILL HAPPEN once it is picked - the same
            # words as the button in the bar and the menu in the tray (0.3
            # batch 4). The palette is built on every opening, so the state
            # is right.
            (tr("tray.stop") if getattr(self, "listening", False) else tr("tray.start"),
             appka, self.toggle_listening),
            (tr("common.minimize"), appka, self.minimize_to_tray),
        ]
        for profile in self.profiles:
            name = profile["name"]
            items.append((tr("palette.profile", name=name), profily,
                          lambda n=name: (self.sidebar._select("spustace"),
                                          self.switch_profile(n))))
        for slot in self.slots:
            # No key in brackets: a key press no longer fires the cue, so
            # "Slot [c]" would show a letter that does nothing.
            label = slot.text_value.strip() or mode_labels().get(slot.mode, "")
            items.append((tr("palette.slot", label=label), profily,
                          lambda: self.sidebar._select("spustace")))
        return items

    def replay_onboarding(self):
        """Shows the Onboarding Wizard again (the same as on the first start).
        Unlike the first run it does NOT OVERWRITE the enabling/disabling of
        existing slots according to the diagnostics
        (self._apply_diagnostics) - it is only a tour of the app, not a
        reset of slots that are already set up.

        World and volume are pre-filled with the CURRENT values - whoever
        just clicks through the introduction stays where they were (e.g. in
        the Work world, where cues do not speak out loud)."""
        wizard = OnboardingWizard(self.root, choice=self.theme_key,
                                  volume=self.volume_value)
        self.root.wait_window(wizard.top)
        if not wizard.confirmed:
            return
        # Step 4 picks the main world (B3-worlds); the theme goes with it. The
        # whole window is rebuilt below, so changing the state is enough -
        # history and insights are recomputed only at the end.
        novy_svet = theme_mod.theme_world(wizard.choice)
        svet_sa_zmenil = novy_svet != self.world
        if svet_sa_zmenil:
            self.world = novy_svet
            self.history_detail_index = None
            self._hr_insights = []
            self._hr_insights_at = None
        self.theme_key = theme_mod.WORLD_THEME[self.world]
        self.pal = theme_mod.tokens(self.theme_key)
        self.overlay_manager.set_colors(self.pal["accent"], self.pal["danger"])
        self.volume_value = wizard.volume_value
        # Step 5 (cue style). Whoever clicked nothing keeps their own style.
        self._prevezmi_styl_z_onboardingu(wizard)
        self._recompute_volumes()
        self._apply_volumes()
        self.save_settings()
        # the app is already running - if you chose pairing, open it right away
        if getattr(wizard, "wants_pairing", False):
            self.sidebar._select("vhre")
            self.root.after(300, self.open_watch_pairing)
        was_listening = self.listening
        self._build_ui()
        self.refresh_edge_banner()
        self.refresh_voice_box()
        self.refresh_slot_summaries()
        self.refresh_hr_status_label()
        if was_listening:
            self._apply_listening_visuals()
        self.log(tr("log.theme_switched", theme=tr(f"theme.{self.theme_key}.label")))
        if svet_sa_zmenil:
            self.run_hr_analysis()
        # Both the world and the cue style decide whether cues for Edge get
        # prepared.
        self.schedule_pregenerate(200)

    # ---------- quick dock (mute / quieten / quick profile / stop) ----------

    # NOTE: here used to be `_dock_on_mute(muted)` - the 🔊/🔇 toggle from the
    # quick dock, which pulled the volume down to zero and back. It left with
    # the dock; volume is set with the slider in Settings -> Sound.

    def _on_snooze_hotkey(self):
        """A key press came in. This runs on `hotkey.py`'s OWN thread, so
        everything has to be passed to Tk through `ui_call` - same as the
        callbacks from the smartwatch."""
        self.ui_call(self._toggle_snooze_from_hotkey)

    def _toggle_snooze_from_hotkey(self):
        """A toggle, not a one-way switch: a second press quietly cancels it.

        In a game the player often cannot get to the keyboard quickly, and
        making them wait 30 minutes for something they turned on by mistake
        would be worse than the cues themselves.

        It is also called by the "Not now" item in the tray menu
        (`setup_tray`, 0.2.1) - the same thing, just without the key, when
        another app holds the shortcut.
        """
        if getattr(self, "_snooze_job", None) is not None:
            self._cancel_snooze()
        else:
            self._start_snooze(SNOOZE_HOTKEY_MINUTES)

    # NOTE: here used to be `_dock_on_snooze()` - a click on 😴 in the dock,
    # which unfolded the length picker (5/20/40/60 min). The button left with
    # the dock. Snooze is now switched on by the global shortcut for a FIXED
    # `SNOOZE_HOTKEY_MINUTES` minutes, and that left `_toggle_snooze_menu`
    # without a trigger - see the note next to it.

    def _start_snooze(self, minutes):
        """"Not now": silences CUES for `minutes` minutes - and nothing more.

        THE AUTHOR'S DECISION (24. 9.): listening and measuring CONTINUE.
        The session stays open, heart rate is recorded, the questionnaire
        does not come; only the trigger is paused with the reason
        `A_SNOOZE` (that one does not count as a dropout) and it is lifted
        when it expires or is cancelled. Until now `stop_listening` was
        called here, which closed the session and opened the questionnaire
        - so "not now" meant "end of measuring", and the player did not
        want that. Stopping listening is a separate, deliberate step (bar,
        tray).

        The length is fixed by the shortcut (`SNOOZE_HOTKEY_MINUTES`); the
        menu with a picker (`_toggle_snooze_menu`) has no trigger today."""
        if getattr(self, "_snooze_job", None) is not None:
            self._cancel_snooze()
        now = time.time()
        # "Not now" shortly after a cue is a signal for the cue ladder. The
        # session keeps running after it, so `_close_hr_session` records how
        # long play actually went on (`snooze_then_s`).
        self._zapis_snooze_po_hlaske(now)
        # How much of the session "not now" was in effect for (`snoozed_s` in
        # the summary). The session now carries it itself and the trigger
        # counters do not see it - otherwise the questionnaire would quietly
        # explain it as "the load never once got above the threshold".
        if getattr(self, "_hr_session_open", False):
            self._snooze_rel_od = now
        # The heart rate sensor keeps running and so does the session - without
        # this line the cue would come anyway. That is exactly the bad moment
        # snooze protects against.
        self._suspend_cue_trigger(trigger.A_SNOOZE)
        self.log(tr("log.snooze_started", minutes=minutes))

        def _resume():
            self._zapocitaj_snooze()
            self._snooze_job = None
            self._snooze_until = None
            # Listening is NO LONGER started here - "not now" did not stop it.
            self._resume_cue_trigger()
            self.log(tr("log.snooze_ended"))
            self._refresh_snooze_indicator()

        self._snooze_job = self.root.after(int(minutes) * 60 * 1000, _resume)
        self._snooze_until = now + int(minutes) * 60
        self._refresh_snooze_indicator()

    def _snooze_do(self):
        """Until when "not now" lasts, as 'HH:MM' ('' when it is not running).

        The end time, not the remaining minutes: the text is set once and
        "30 min left" would be lying after five minutes."""
        do = getattr(self, "_snooze_until", None)
        if do is None or getattr(self, "_snooze_job", None) is None:
            return ""
        try:
            return time.strftime("%H:%M", time.localtime(do))
        except Exception:
            return ""

    def _zapocitaj_snooze(self, now=None):
        """Adds the running "not now" stretch to the open session
        (`_snooze_rel_s`). Called when snooze ends or is cancelled; closing
        the session (`_close_hr_session`) adds the running stretch itself,
        and nothing more is added after that - time outside a session
        (stopped listening) does not count."""
        od = getattr(self, "_snooze_rel_od", None)
        if od is None:
            return
        now = time.time() if now is None else now
        self._snooze_rel_s = (getattr(self, "_snooze_rel_s", 0.0)
                              + max(0.0, float(now) - float(od)))
        self._snooze_rel_od = None

    def _zapis_snooze_po_hlaske(self, now):
        """Did "not now" come within `rebrik.SNOOZE_PO_HLASKE_S` after the last
        delivered automatic cue? It is recorded on the cue (`snooze_after_s`,
        goes into the window) and in the session (`_close_hr_session`:
        `snooze_after_cue_s` and `snooze_then_s` = how long the session
        kept running after it).

        The ladder counts it only when the session then ran for at least
        `rebrik.SNOOZE_POTOM_S` and the verdict is not "sadla" (it landed) -
        "not now" at the end of playing means "I'm done" rather than "you
        got in my way". Only the first one in a session is recorded."""
        if not getattr(self, "_hr_session_open", False):
            return
        if getattr(self, "_snooze_po_hlaske", None) is not None:
            return
        try:
            posledna = self.hr_stats.last_auto_cue_ts()
            if posledna is None:
                return
            po = float(now) - float(posledna)
            if not 0.0 <= po <= rebrik.SNOOZE_PO_HLASKE_S:
                return
            self._snooze_po_hlaske = (round(po, 1), float(now))
            for cue in reversed(self.hr_stats.cues):
                if cue.get("ts") == posledna:
                    cue["snooze_after_s"] = round(po, 1)
                    break
        except Exception:
            app_log.exception("rebrik hlasky: snooze po hlaske sa nezapisal")

    def _cancel_snooze(self):
        job = getattr(self, "_snooze_job", None)
        if job is None:
            return
        try:
            self.root.after_cancel(job)
        except Exception:
            pass
        self._zapocitaj_snooze()
        self._snooze_job = None
        self._snooze_until = None
        # "Not now" did not stop listening, so it does not need starting here.
        self._resume_cue_trigger()
        self.log(tr("log.snooze_cancelled"))
        self._refresh_snooze_indicator()

    def _refresh_snooze_indicator(self):
        """Shows with a dot in the side rail whether snooze is running right now.

        NOTE ON HISTORY: the state was first carried by a text label in
        Settings ('20m'), then by the colour of the 😴 icon in the quick
        dock. The dock left the panel (see `_build_ui`) and snooze is
        switched on by a global shortcut - if the state had nowhere to go,
        the player would snooze the app and see NOWHERE that it is snoozed.
        The status dot is already on every page, so it is the only place
        where it does not disappear when the page is switched.

        The end time is carried by the tooltip: the colour says "something
        is different", the time says until when, and a 64px rail has no
        room for a text label.

        Since 24. 9. the app keeps listening during "not now", so the
        centre of the Today page also has to say that it will not speak up
        (`_kamae_state_text`) - "waiting for a good moment" would be
        lying."""
        self._refresh_dnes_state_text()
        # The tick next to "Not now" in the tray menu (`setup_tray`). Pystray
        # rebuilds the menu only on `update_menu` - and a click in the tray
        # toggles only through `ui_call`, i.e. AFTER its own rebuild; the
        # shortcut does not call it at all.
        ikona = getattr(self, "tray_icon", None)
        if ikona is not None:
            try:
                ikona.update_menu()
            except Exception:
                app_log.exception("lista: menu sa nepodarilo obnovit")
        bodka = getattr(getattr(self, "sidebar", None), "state_dot", None)
        if bodka is None:
            return
        active = getattr(self, "_snooze_job", None) is not None
        try:
            bodka.set_snoozed(
                active,
                tip=(tr("dock.snooze_active_tip", until=self._snooze_do())
                     if active else tr("sidebar.state_tip")))
        except Exception:
            app_log.exception("bodka stavu: odlozenie sa nepodarilo ukazat")


    def _log_toggle_text(self):
        arrow = "▾" if not self.log_collapsed else "▸"
        if self.log_collapsed and self._last_log_line:
            return f"{arrow}  {self._last_log_line}"
        return f"{arrow}  {tr('common.log')}"

    def toggle_log(self):
        self.log_collapsed = not self.log_collapsed
        if self.log_collapsed:
            self.log_body.pack_forget()
        else:
            self.log_body.pack(fill="x")
        self.log_toggle_btn.configure(text=self._log_toggle_text())

    # ---------- rebind ----------

    # ---------- gamepad (NO LONGER as a trigger) ----------
    #
    # PHASE 3: the keyboard and mouse listeners are GONE. It was the only place
    # in the app that looked like a keylogger - a global WH_KEYBOARD_LL hook
    # via pynput. The cue is now fired by the body (`trigger.CueTrigger`), and
    # whether the player is active is found out from `GetLastInputInfo`, which
    # returns only the number of milliseconds since the last input. Which key
    # it was, the app has no way to learn, not even if it wanted to.
    #
    # The gamepad listener stays, but it NO LONGER FIRES ANYTHING - it serves
    # as a second source of activity detection next to GetLastInputInfo (see
    # MERANIE_GAMEPAD.md: on this Windows 11 GetLastInputInfo sees it, but it
    # is one computer and a silent failure on another one would not show up
    # as an error).

    def on_gamepad_button(self, label):
        """Activity on the controller (button, d-pad, stick or trigger past the
        dead zone - also when held). It no longer fires a cue - it only
        confirms that the player is active. `label` is always "activity";
        which element it was, the listener does not say (`gamepad.py`)."""
        self.activity.note_external_input()

    def on_gamepad_status(self, message):
        if message.startswith("connected:"):
            self.log_threadsafe(tr("log.gamepad_connected", name=message.split(":", 1)[1]))
        elif message == "disconnected":
            self.log_threadsafe(tr("log.gamepad_disconnected"))

    def fire_slot(self, slot, ignore_cooldown=False, source="trigger"):
        """MANUAL firing of a cue - the Test button on the card and a click in
        the HUD preview.

        The app NEVER goes through here on its own. `_fire_somatic_cue`
        calls `_emit` directly, because WHEN it speaks up is decided by the
        body load (`trigger.CueTrigger`) and not by a number on the cue
        card. Its own cooldown, delay, "every N-th" and spread therefore sat
        here until 18. 9. as settings that affected only these two buttons
        - and yet they looked like they controlled the whole app. They are
        gone.

        What stayed is the global gap, so that two clicks in quick
        succession do not overlap in one sound.
        """
        if not ignore_cooldown:
            now = time.time()
            if now - slot.last_triggered < self.cooldown_value:
                return
            # Until the gap since the LAST manually fired cue (any one) has
            # passed, another one must not fire - otherwise two quick
            # clicks on Test overlap in one sound.
            if now - self.last_global_trigger_time < self.cooldown_value:
                return
            self.last_global_trigger_time = now
            slot.last_triggered = now
        if 0 <= slot.index < 4:
            self.ui_call(lambda i=slot.index: self.overlay_manager.trigger(i))
            # `_note_cue` no longer records anything (see its docstring).
            # It still goes through `ui_call` - a leftover from when
            # `fire_slot` also ran on the key listener's thread, while only
            # the GUI thread may touch `HeartStats`. The key triggers and
            # their listeners were removed in phase 3; today only the Test
            # button and a click in the HUD preview come here.
            self.ui_call(lambda i=slot.index, s=source: self._note_cue(i, s))
        threading.Thread(target=self._deliver, args=(slot, ignore_cooldown, source),
                         daemon=True).start()

    def _note_cue(self, slot_index, source="trigger"):
        """A MANUALLY fired cue is NOT recorded in the measurement.

        It used to be - and that was a bug that silently spoiled exactly
        the thing the app measures for. `fire_slot` today is fired only by
        the Test button on the cue card and a click in the HUD preview. Both
        happen while setting things up, often several times in a row, and
        the player is not playing then. `measure.by_category` meanwhile
        filters only by `valid` and `arm` - it does not read `source` at
        all - so every click on Test was counted into the "which cue works"
        chart, and its time took the refractory zone away from a real cue
        that could come a few seconds later.

        The automatic cue is recorded by `_fire_somatic_cue` itself, via
        `hr_stats.note_trigger(..., source="auto")`. So nothing needs to go
        through here anymore.

        The method stays (and is called) so that the code shows this was
        decided - and so that a counter that does not disturb the
        measurement could be brought back here.
        """
        return

    def _deliver(self, slot, immediate, source):
        # One playback, no delay or repetition: the cue should arrive at the
        # moment the person clicked on it.
        self._emit(slot)
        label = slot.text_value or (os.path.basename(slot.audio_path)
                                    if slot.audio_path else mode_labels()[slot.mode])
        self.log_threadsafe(f"Slot {slot.index + 1} ({source}): \"{label}\"")
        if source == "trigger" and 0 <= slot.index < 4:
            # THE COUNTER BELONGS TO THE TK THREAD. `_deliver` runs on its
            # own thread and `start_listening` meanwhile swaps `session_counts`
            # for a new dict - an increment from here could end up in the old
            # dict or clash with the row being redrawn. Hence through
            # `ui_call`, same as `_note_cue` in `fire_slot`.
            def zarataj(index=slot.index):
                self.session_counts[index] = self.session_counts.get(index, 0) + 1
                self.update_session_label()
            self.ui_call(zarataj)
