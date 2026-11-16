"""Today page - part of the main app (DandurfApp from app.py).

TodayMixin is a mixin of DandurfApp: app.py inherits it and the whole state
(the centre of the Today page and the enso, the cue trigger and its record,
the heart-rate sensor and session statistics, the "My stats" cards and
their order) lives on DandurfApp. Here are only the methods that work with
it through `self` - the mixin has no __init__ and no attributes of its own.

Moved from app.py unchanged:
  * live dojo (empty-state hero) - animation of the Today centre (the enso
    and the dojo behind it), the sentence under the mark, the live
    heart-rate block, load, the session trace and zones; the section also
    carries the delivery of the automatic cue (`_tick_cue_trigger`,
    `_cue_can_fire`, `_on_cue_event`, `_dalsi_cue_slot`,
    `_fire_somatic_cue`), the "armed" ring on the enso and the badges in
    the side menu, which were already in it in app.py,
  * optional stats on Today ("My stats") - the catalogue and values of the
    cards, the grid, card selection and moving a card by dragging,
  * the centre of the Today page on the canvas - drawing the dojo, the enso
    and the text on `dnes_canvas`, click on the enso and on the credit. In
    app.py it sat without its own marker in the section "cue style
    (onboarding step 5, Settings -> Sound)" (its first part is in
    app_cues.py), which is why it has a new marker here.

The constants `HERO_PERIOD_S`, `DASHBOARD_DRAG_PX` and `BACKDROP_DEBOUNCE_MS`
stayed in the DandurfApp class among the other class constants -
`_dashboard_drag` and `_naplanuj_backdrop` read theirs through `self`
(`HERO_PERIOD_S` is read by nothing today).

Careful in tests: `_tick_cue_trigger`, `_refresh_session_trace`,
`_history_cached` and `_dashboard_stat_value` read `time` from this module
and `_fire_somatic_cue` reads `threading` - the fake clock and the
synchronous thread must be slipped in here too (`app_today.time`,
`app_today.threading`), not only on the app module.
"""

import math
import threading
import time
import tkinter as tk
from tkinter import font as tkfont

import customtkinter as ctk

import background
import hr_stats
import measure
import rebrik
import theme as theme_mod
import trigger
import ui_kit
from i18n import tr
from settings_model import (dashboard_stat_clickable, swap_dashboard_stats,
                            toggle_dashboard_stat)

from app_spolocne import _ImageTk, app_log, obnov_texty_stranky, stranka_vhre


def _text_bez_tepu(app):
    """Right-hand text of the "Heart rate and load" header while no HR (0.3).

    Before, it always said "waiting for watch" there - even with reception
    switched off, with the port busy and when the phone never connected at
    all, i.e. exactly when the watch COULD NOT come. "Waiting" now stays
    only for connecting and for a phone that is connected but has not sent
    heart rate yet.

    A module function, not a method: `_refresh_dnes_stats` also runs in
    tests on dummies (SimpleNamespace) that would not have a new method.
    """
    stav = getattr(app, "_hr_state", None)
    if stav in ("busy", "busy_gave_up"):
        return tr("dnes.hr_busy")
    if not getattr(app, "hr_monitoring_enabled", True):
        return tr("dnes.hr_off")
    if stav == "no_client":
        return tr("dnes.hr_no_client")
    return tr("dnes.hr_waiting")


class TodayMixin:
    """Today page centre and cards, cue delivery (DandurfApp mixin)."""

    # ---------- live dojo (empty-state hero) ----------

    def _dnes_anim_active(self):
        """Is anything MOVING still being drawn? Now only when the enso is alive
        or it is the moon (listening / graduation). The STOPPED state STANDS
        STILL - the dojo no longer BREATHES, because redrawing (almost)
        identical content 8x/s made the window flicker. The bar says the
        same: "otherwise it rests"."""
        enso = getattr(self, "enso", None)
        return bool(enso is not None and (enso._live or enso._moon))

    def _ensure_dnes_tick(self):
        """Starts the centre's animation tick if it is not running and the enso
        moves. The only place (together with the end of `_tick_dnes`) where
        `_dnes_tick_job` is created.

        Schedules via `after` and sets the job RIGHT AWAY - not by calling
        `_tick_dnes` directly (that would recurse through the redraw and
        back into `_ensure_dnes_tick`, while `_tick_dnes` holds the job
        cleared at its start)."""
        if getattr(self, "_dnes_tick_job", None) is not None:
            return
        if not self._dnes_anim_active():
            return
        try:
            self._dnes_tick_job = self.root.after(self.DNES_TICK_MS, self._tick_dnes)
        except Exception:
            self._dnes_tick_job = None

    def _on_enso_change(self):
        """`_EnsoHero._emit()` reports a state change here (set_live/armed/
        graduate/set_pal). Redraws the centre and starts the tick if the
        enso came to life."""
        self._refresh_dnes_backdrop(force=False)
        self._ensure_dnes_tick()

    def _tick_dnes(self):
        """One step of the centre animation - now only for the enso (listening /
        moon). The dojo is static, so it does not move; we redraw the canvas
        and the enso swaps its frame in place (`itemconfigure`, no
        flicker)."""
        self._dnes_tick_job = None
        if not self._dnes_anim_active():
            return
        try:
            viditelne = bool(self.root.winfo_viewable())
        except Exception:
            viditelne = True
        if viditelne:
            self._refresh_dnes_backdrop(force=False)
        interval = self.DNES_TICK_MS if viditelne else self.DNES_TICK_MS * 4
        try:
            self._dnes_tick_job = self.root.after(interval, self._tick_dnes)
        except Exception:
            self._dnes_tick_job = None

    def _start_dnes_hero(self):
        """Turns on the BRIGHT dojo behind the enso (stopped state). The dojo is
        STATIC - it no longer BREATHES (that made it flicker). The enso and
        the text stand still; the centre is redrawn once and then nothing
        moves - exactly as the bar says: "otherwise it rests"."""
        self._dnes_hero_on = True
        # Static, but with a pleasant glow (not at the minimum) - a fixed
        # breath phase.
        self._dnes_breath_phase = 0.25
        self._refresh_dnes_backdrop(force=True)
        self._ensure_dnes_tick()

    def _sync_dnes_hero(self):
        """Photo brightness behind the enso: WATCHING or not (0.3, UX audit).

        Before 0.3 the brightness was driven by the watch connection: the
        same "Not watching anything" state had a dimmed photo one time and
        a bright one another time, depending on whether heart rate was
        coming - while the hero claimed the app was stopped. Now: stopped =
        bright dojo, watching = dimmed (only the bar breathes now). Redrawn
        only on change."""
        jasne = not bool(getattr(self, "listening", False))
        if jasne == bool(getattr(self, "_dnes_hero_on", False)):
            return
        if jasne:
            self._start_dnes_hero()
        else:
            self._stop_dnes_hero()

    def _stop_dnes_hero(self):
        """Switches the dojo to the dimmed photo (listening). The enso may live
        on (listening / moon) - the animation tick stops by itself when
        nothing moves any more."""
        self._dnes_hero_on = False
        self._refresh_dnes_backdrop(force=True)
        self._ensure_dnes_tick()

    def _refresh_dnes_state_text(self):
        """Heading and the sentence under the mark. The same text as in the
        breathing bar - `_kamae_state_text` is the single source, so they
        cannot drift apart. The text is stored and the centre is redrawn
        (`_paint_dnes_canvas` draws it)."""
        if not hasattr(self, "dnes_canvas"):
            return
        try:
            titul, veta = self._kamae_state_text()
            self._dnes_titul = titul
            self._dnes_veta = veta
            self._refresh_dnes_backdrop(force=False)
        except Exception:
            app_log.exception("stav na Dnes: prepis textu zlyhal")

    def _hodinky_vypadli(self):
        """Watching, HR reception on, but the watch's heart rate dropped out.

        The app has recognised a dropout for a long time
        (`app_session._zaznamenaj_vypadok`: heart rate was coming and 12 s
        of silence, `heart_rate.STALE_AFTER_S`) and holds it in `_hr_lost`
        until a valid sample arrives (`_tep_je_spat`). Nothing new is
        measured here - it is just said outside the Today page too."""
        return bool(getattr(self, "listening", False)
                    and getattr(self, "hr_monitoring_enabled", False)
                    and getattr(self, "_hr_lost", False))

    def _refresh_state_dot(self):
        """Status dot in the side panel: "watching, but heart rate dropped out"
        (0.3 batch 4). Called from `_refresh_kamae_state_text`, i.e. on
        every change of heart-rate state and of watching. Watching itself
        (filled / hollow dot) is set by `_apply_listening_visuals` via
        `set_live`."""
        sidebar = getattr(self, "sidebar", None)
        bodka = getattr(sidebar, "state_dot", None) if sidebar is not None else None
        if bodka is None or not hasattr(bodka, "set_lost"):
            return
        try:
            bodka.set_lost(TodayMixin._hodinky_vypadli(self))
        except Exception:
            app_log.exception("bodka stavu: vypadok tepu sa nepodarilo ukazat")

    def _nazov_vhre(self, dlhy=False):
        """Name of the "In-game" page by world (0.3 batch 4, UX audit).

        In the "Work" world nothing happens "in game" - the page carries the
        watch and the pictures on the screen, so there it is called
        "Screen". `dlhy=True` is the full name (command palette Ctrl+K):
        "Watch and in-game" / "Watch and screen"."""
        praca = getattr(self, "world", hr_stats.WORLD_DEFAULT) == "work"
        if dlhy:
            return tr("nav.vhre_work") if praca else tr("nav.vhre")
        return tr("nav.vhre_work_short") if praca else tr("nav.vhre_short")

    def _sync_world_nazvy(self):
        """After a world switch, rewrites the name of the "In-game" page in the
        side panel. The world is switched by recolouring the window, not by
        rebuilding (`set_world`), so the label built at `_build_ui` would
        otherwise stay from the other world. Because the busy-port sentence
        contains the page name, the state on Today is rewritten too.

        The same holds for texts with `{page}` that are built once (0.3
        batch 4b): the explanations in History (`obnov_texty_stranky`) and
        the ⓘ of the cards on Today (the cards are rebuilt - there are
        four)."""
        sidebar = getattr(self, "sidebar", None)
        if sidebar is not None and hasattr(sidebar, "set_label"):
            try:
                sidebar.set_label("vhre", self._nazov_vhre())
            except Exception:
                app_log.exception("bocny panel: meno stranky sa neprepisalo")
        obnov_texty_stranky(self)
        karty = getattr(self, "_rebuild_dashboard_stats_grid", None)
        if callable(karty) and getattr(self, "dashboard_grid", None) is not None:
            try:
                karty()
            except Exception:
                app_log.exception("Dnes: karty sa po prepnuti sveta neprestavali")
        self._refresh_kamae_state_text()

    def _resume_cue_trigger(self):
        """Deliberately lifts the trigger's pause.

        `resume(force=True)`, because the ordinary `resume()` from
        `_apply_hr_bpm` NOW lifts ONLY a heart-rate dropout - it must not
        lift snooze or stopped listening. It must ALWAYS be called, even
        when `start_listening` is not called: with snooze started in a
        non-listening state the trigger would otherwise stay paused forever.

        WHILE "NOT NOW" IS IN EFFECT, IT LIFTS NOTHING. Since 24. 9. snooze
        does not stop listening, so `start_listening` (the player pressed
        stop and start while muted) would otherwise silently
        cancel it. The end and cancellation of snooze clear `_snooze_job`
        BEFORE the call.
        """
        if getattr(self, "_snooze_job", None) is not None:
            return
        try:
            self.cue_trigger.resume(force=True)
        except Exception:
            app_log.exception("spustac hlasky: resume zlyhal")

    def _set_enso_armed(self, armed):
        """Carries "armed" over into the mark in the side panel.

        An inner ring, not a third colour - according to `theme.py` the
        colour of the enso has a single job in the whole interface, and that
        is to say whether the app is listening.

        Via `getattr` and `try`, because this can be reached even before the
        sidebar is built (the trigger ticks from `_tick_activity`, which
        runs from start).
        """
        armed = bool(armed)
        self._cue_armed = armed
        sidebar = getattr(self, "sidebar", None)
        if sidebar is not None:
            try:
                sidebar.enso.set_armed(armed)
            except Exception:
                pass
        # The mark and the bar carry the same state - they must change in
        # one place, otherwise one day they drift apart and nobody notices.
        self._refresh_kamae_state_text()

    def _cue_can_fire(self, now):
        """May a cue be delivered right now?

        This does NOT cancel the arming - if it may not, it keeps waiting.
        It is cancelled only when `max_wait_s` passes.
        """
        if not self.listening:
            # The enso is the only carrier of state. While `danger` is lit,
            # the app must not say anything - otherwise that colour would lie.
            return False
        if getattr(self, "_snooze_job", None) is not None:
            return False            # "not now" covers the body too, not just keys
        if not self._hr_overlay_available():
            self._warn_hr_overlay_disabled_once()
            return False
        # Is ANY visual already running? Asking only about slot 3 was not
        # enough: since rotation of categories was introduced, any of the
        # four can be running, and a second cue on top of the first is
        # exactly the visual noise the app avoids. Since 0.3.1 the exhale
        # ring (slot 3's visual) comes with every grounding / jaw / release
        # cue (`SomaticOverlayManager.trigger`) - it is part of that cue, so
        # the next one waits for it too (about 6.5 s with the default exhale;
        # far below the gap between cues). The ring at high heart rate
        # (experiment, `_tick_high_hr_ring`) is slot 3's ring as well, so no
        # cue comes while it breathes - on purpose.
        if any(self.overlay_manager.is_active(i) for i in range(4)):
            return False
        # While steps are coming, the app stays silent. `None` means the watch
        # does not send steps - then there is nothing to go by and it blocks
        # nothing.
        kroky = self.hr_stats.steps_per_min()
        if kroky is not None and kroky >= self.KROKY_PRAH_ZA_MIN:
            return False
        if now - self.last_global_trigger_time < self.cooldown_value:
            return False
        return True

    def _tick_cue_trigger(self):
        """4x per second. The only caller is `_tick_activity`, i.e. the Tk
        thread - and that is necessary: it touches `hr_stats` and
        `overlay_manager`."""
        if not self._hr_session_open:
            return
        now = time.time()
        # HUD visibility for this tick. dt < 5 s is a safety net against PC
        # sleep (after waking, one "tick" would add hours) - short gaps are
        # normal running. Active time always grows, visible time only when the
        # HUD is on - the share is then counted from the same base (see
        # `_close_hr_session`).
        if self._hud_tick_t is not None:
            dt = now - self._hud_tick_t
            if 0.0 < dt < 5.0:
                self._hud_active_s += dt
                if self._hud_is_visible():
                    self._hud_vis_s += dt
        self._hud_tick_t = now
        udalost = self.cue_trigger.tick(
            pause_s=self.activity.pause_s(now),
            now=now,
            can_fire=self._cue_can_fire(now))
        if udalost is not None:
            self._on_cue_event(udalost)

    def _hud_is_visible(self):
        """Whether the player is seeing their heart rate right now - i.e. the HUD
        panel is on. The saved state is used (`hud_config['enabled']`), so
        toggling changes it at once; a temporary 'test_hud' does not count
        (that is not playing)."""
        try:
            return bool(self.hud_config.get("enabled"))
        except Exception:
            return False

    def _on_cue_event(self, ev):
        """One event from the state machine. Everything is recorded - even
        cancelled armings, because their ratio is used to tune the
        thresholds.

        It is also the only place where the ring on the enso is switched on.
        It is switched off in three others (delivery, cancellation,
        `_suspend_cue_trigger`) - the state machine has more states than the
        UI, but every way out of ARMED leads through one of them.
        """
        zaznam = dict(ev)
        self._cue_log.append(zaznam)
        if ev["typ"] == trigger.E_DELIVER:
            self._set_enso_armed(False)
            # Whether the cue was REALLY delivered (not all slots off, not a
            # failed visual). Without this the questionnaire counted
            # undelivered ones too and reported "I spoke up 3x" while the app
            # was silent (bug B19).
            zaznam["delivered"] = bool(self._fire_somatic_cue(ev))
        elif ev["typ"] == trigger.E_ARMED:
            self._set_enso_armed(True)
            app_log.info("hlaska natiahnuta (rameno %s)", ev.get("arm"))
        else:
            self._set_enso_armed(False)
            app_log.info("natiahnutie zrusene: %s", ev.get("reason"))

    def _dalsi_cue_slot(self):
        """Which category sounds now. They rotate round-robin.

        Only takes into account slots that are ON and also have the in-game
        visual on. When there is not a single one, it returns None and the
        cue is NOT DELIVERED - switching off is the player's decision and
        the app must not get around it.

        The order is remembered within one app run, not between starts:
        after a restart it begins from the first enabled category. With a
        cap of five cues per hour that is a difference that gets lost in the
        data.
        """
        zapnute = []
        for slot in getattr(self, "slots", ()):
            try:
                index = int(slot.index)
            except (TypeError, ValueError):
                continue
            if not getattr(slot, "enabled_value", True):
                continue
            # AND it MUST also have the in-game visual on.
            #
            # `_fire_somatic_cue` draws `overlay_manager.trigger(index)` in
            # BOTH arms - that is the only thing the silent arm gets. A slot
            # with the visual off would deliver nothing in the silent arm and
            # the window would be recorded as a valid measurement of a cue
            # that never happened. That is why such a slot is skipped.
            try:
                if not self.overlay_configs[index]["enabled"]:
                    continue
            except (IndexError, KeyError, TypeError):
                continue
            zapnute.append(index)
        dalsi = measure.next_slot(zapnute, getattr(self, "_posledny_cue_slot", None))
        if dalsi is None:
            # No category is usable - NO FALLBACK. Until 19. 9. this returned
            # `CUE_SLOT_INDEX` (3), i.e. the breathing circle - "better for
            # the app to say something than nothing". But exactly that slot
            # may have its visual off, and then the cue would be "delivered"
            # without anything being drawn. And switching a cue off is the
            # player's decision, which the app must not get around: whoever
            # turned off all four wanted silence and got breathing.
            return None
        self._posledny_cue_slot = dalsi
        return dalsi

    def _fire_somatic_cue(self, ev):
        """Delivers a cue. VISUAL IN BOTH ARMS, sound only in the voice arm.

        If the silent arm did not show even the visual, the arms could not
        be compared - it would measure the difference between "something
        happened" and "nothing happened", not between a cue and silence.

        The SAME line goes to the app log in both arms. The player hears
        anyway whether something sounded, so it cannot be blinded - but the
        log should not be one more place where the arms differ.
        """
        index = self._dalsi_cue_slot()
        if index is None:
            # All cues off (or none has a visual). Until now, a fallback - the
            # breathing circle - was delivered in this state, so switching off
            # all four toggles did NOT SILENCE the app. The player switched off
            # everything that could be switched off, and the app kept speaking
            # up.
            self.log(tr("log.cue_skipped_all_off"))
            return False
        self.last_global_trigger_time = ev["ts"]
        # THE VISUAL IS THE COMMON STIMULUS OF BOTH ARMS. When it is not drawn,
        # the silent arm gets NOTHING and the measurement would compare a cue
        # against nothing. `note_trigger(delivered=...)` carries this into the
        # window, which `measure` then invalidates (bug B17).
        vykreslene = bool(self.overlay_manager.trigger(index))
        if not vykreslene:
            self.log(tr("log.cue_visual_failed"))

        # By attribute, not by position in the list: `handle_trigger` also
        # looks up via `slot.index`, so the order in `self.slots` may not
        # match.
        slot = next((s for s in self.slots if s.index == index), None)
        label = (slot.text_value if slot is not None else "") or ""
        # `hlas` is always False in the work world (B3-worlds) - the state
        # machine decides (`CueTrigger.open_session(voice=...)`), not this
        # branch, so that the event record also tells the truth about what
        # sounded.
        #
        # LADDER (0.2): sound ONLY on the voice rung. Below it, the cue goes
        # only as a picture in both arms - the state machine already knows
        # this (`voice` at open), this is a second safety net. Style "zvuk"
        # (sound) = the voice rung with muted words: the slot plays its
        # sound, no TTS and no recording.
        stupen = getattr(self, "_cue_rung", rebrik.HLAS)
        bez_slov = (getattr(self, "_cue_style_rel", rebrik.STYL_HLAS)
                    == rebrik.STYL_ZVUK)
        zaznie = False
        if ev.get("hlas") and slot is not None and stupen == rebrik.HLAS:
            zaznie = self._slot_zaznie(slot, bez_slov)
            # `_emit` plays and blocks - in the Tk thread it would freeze the
            # window.
            threading.Thread(target=self._emit, args=(slot,),
                             kwargs={"bez_slov": bez_slov}, daemon=True).start()

        # The delivery record goes into the window (`measure.build_window`):
        # the rung, whether something really sounded, load and its peak, the
        # heart-rate zone.
        self.hr_stats.note_trigger(
            ts=ev["ts"], auto=True,
            category=measure.category_for_slot(index),
            cue_id=f"slot{index}", arm=ev["arm"], source="auto",
            delivery=ev.get("delivery"), delivered=vykreslene,
            rung=stupen, audible=zaznie, load_at=ev.get("load"),
            load_peak=ev.get("load_peak"), zone_at=ev.get("zone_at"))
        self.log(tr("log.cue_delivered", label=label))
        # Counter in the journal header (`session.summary`,
        # "Grounding 2× | ..."). Until now only `_deliver` increased it at
        # source=="trigger" - but the automatic cue never goes that way, so
        # the line showed 0× for all four while the card on Today reported
        # three cues.
        # Only a cue that was really shown counts, not the silent control arm
        # (that is a measurement, not a cue for the player).
        if vykreslene and ev.get("arm") != trigger.ARM_SILENT:
            pocty = getattr(self, "session_counts", None)
            if isinstance(pocty, dict):
                pocty[index] = pocty.get(index, 0) + 1
                obnov = getattr(self, "update_session_label", None)
                if callable(obnov):
                    obnov()
        self._refresh_hud_session_text()
        self._refresh_dnes_stats()
        return vykreslene

    def _refresh_nav_badges(self):
        """Number of triggers on the Cues tab, a dot by "In-game" (now a
        separate sidebar item, not a tab) when the heart-rate sensor
        runs."""
        sidebar = getattr(self, "sidebar", None)
        if sidebar is None or not hasattr(sidebar, "set_badge"):
            return
        try:
            # The CUE COUNT by the "Cues" tab is GONE.
            #
            # The number made sense while the player assigned slots to keys and
            # needed to see how many were active. Today there are four, the app
            # rotates them itself and the player does not add any - so it was
            # just a figure that reported nothing and drew the eye to the wrong
            # thing.
            nav = getattr(self, "settings_nav", None)
            if nav is not None:
                nav.set_badge("spustace", "")
            sidebar.set_badge("vhre", "●" if self.hr_monitoring_enabled else "")
        except Exception:
            pass

    def _refresh_dnes_stats(self):
        """Rewrites heart rate, load and the session summary on the Today page.

        Called on every heart-rate sample and once per second from
        `_tick_session`, so that the session time runs too. When the page
        is not built yet (happens while switching theme/language), it
        silently does nothing.

        WHY ERRORS ARE COUNTED HERE
        The whole body is in one `except`, and deliberately: it runs 1-4x
        per second and an exception from the redraw must not bring down
        either the measurement or the session. But `pass` meant a broken
        page showed up in NO WAY. gui_screenshots reports "0 chyb v Tk",
        because it only catches exceptions that ESCAPE from a Tk callback -
        and this one does not escape. So the app could have a completely
        frozen Today page and the whole test pass green.

        That is why the first occurrence is logged in full and later ones
        are only counted (`app_log.exception` on every call would flood the
        log). gui_screenshots checks `_dnes_refresh_fails`.
        """
        if getattr(self, "dnes_bpm", None) is None:
            return
        stats = self.hr_stats
        connected = self._hr_state == "connected" and stats.last_bpm is not None
        # A DROPOUT IS NOT "I HAVEN'T HEARD YOU YET". During a dropout the live
        # block and the session trace stay (no "Pair your watch" in the middle
        # of the evening), but the number is "--" and the zone "—" -
        # `connected` below handles that, so there is no false calm.
        lost = bool(getattr(self, "_hr_lost", False)) and not connected
        ukaz = connected or lost
        pal = self.pal
        try:
            # The number is smoothed (`display_bpm`), `connected` above stays
            # on the raw `last_bpm` - it decides the connection state as before.
            self.dnes_bpm.configure(
                text=str(stats.display_bpm) if connected else "--",
                text_color=pal["text"] if connected else pal["text_faint"])
            self.dnes_spark.set_series(stats.series(120) if connected else [],
                                       threshold=self.hr_critical_bpm,
                                       baseline=stats.baseline)
            # While the session is calibrating, the bar stays empty and instead
            # of the zone there is a quiet "calibrating…" - just like the
            # in-game HUD. Right after heart rate returns (`is_settling`) the
            # same, only with "…" instead of the word: load ramps up from zero
            # and would otherwise claim "Calm" for a few seconds.
            kalibruje = connected and stats.is_calibrating
            usadza = connected and not kalibruje and stats.is_settling
            tlmene = kalibruje or usadza
            # The word and the colour of the filled segments are `stats.zone`
            # (heart rate relative to rest) - the same as on the HUD and on the
            # heart-rate indicator. The length of the bar is load.
            zone = stats.zone if connected and not tlmene else None
            self.dnes_load.set_value(stats.stress if connected and not tlmene else 0,
                                     zone=zone)
            if kalibruje:
                zone_text = tr("hud.calibrating")
            elif usadza:
                zone_text = "…"
            else:
                zone_text = tr(f"hud.zone.{zone}") if zone else "—"
            self.dnes_zone.configure(
                text=zone_text,
                text_color=theme_mod.zone_color(pal, zone) if zone else pal["text_faint"])
            self._refresh_session_trace(ukaz)
            self._refresh_zone_panel()
            self._refresh_dashboard_stats()
            if getattr(self, "hr_panel", None) is not None:
                if connected:
                    vpravo = tr("dnes.hr_connected")
                elif lost:
                    vpravo = tr("dnes.hr_lost")
                else:
                    vpravo = _text_bez_tepu(self)
                self.hr_panel.set_right(vpravo)
            empty, live = getattr(self, "dnes_empty", None), getattr(self, "dnes_live", None)
            if empty is not None and live is not None:
                if ukaz and not live.winfo_ismapped():
                    empty.pack_forget()
                    live.pack(fill="x")
                elif not ukaz and not empty.winfo_ismapped():
                    live.pack_forget()
                    empty.pack(fill="x", pady=(6, 0))
                # BUSY PORT (0.3 batch 4b): both the bar and the panel header
                # state the problem ("port is busy") - the sentence "Once you
                # pair your watch..." would be a second, different message,
                # and the watch is fine.
                # The button stays (the pairing guide also shows the reception
                # status).
                ukaz_vetu = getattr(empty, "ukaz_vetu", None)
                if callable(ukaz_vetu):
                    ukaz_vetu(getattr(self, "_hr_state", None)
                              not in ("busy", "busy_gave_up"))
                # via the class: tests call this method on a dummy app
                TodayMixin._sync_dnes_hero(self)
            # Before the first session with heart rate: cards and zones with
            # only dashes are hidden (0.3 batch 4) - see
            # `_sync_dnes_prazdny_stav`.
            TodayMixin._sync_dnes_prazdny_stav(self)
        except Exception:
            self._dnes_refresh_fails = getattr(self, "_dnes_refresh_fails", 0) + 1
            if self._dnes_refresh_fails == 1:
                app_log.exception(
                    "Dnes: obnovenie zlyhalo (dalsie vyskyty sa uz nevypisu)")
        TodayMixin._refresh_dnes_learning(self)
        self._refresh_last_cue()

    def _dnes_ma_tep(self):
        """Has a session with heart rate ever come in? (0.3 batch 4)

        Yes when heart rate is coming in this session (`session_count`), or
        when there is at least one saved session in history - every saved
        one has heart rate (`hr_stats.je_ulozitelna`: at least 10 samples
        and a minute). From both worlds: the point is whether the watch has
        ever sent heart rate, not what is happening in the "Work" world.
        History comes from the cache (`_history_cached`), because this runs
        on every sample. Dummies without a cache (tests) get the full
        view."""
        stats = getattr(self, "hr_stats", None)
        if getattr(stats, "session_count", 0):
            return True
        historia = getattr(self, "_history_cached", None)
        if not callable(historia):
            return True
        try:
            return bool(historia())
        except Exception:
            return True

    def _sync_dnes_prazdny_stav(self):
        """Empty Today state before the first HR session (0.3 batch 4).

        UX audit: without data the page showed a big "--", four cards with
        dashes and "0:00 over the limit" and four "0 %" rows - it looked
        like a measurement, not like "nothing yet", and the only call to
        action that made sense (pairing the watch) was below the edge of
        the window. While there is no session with heart rate
        (`_dnes_ma_tep`):
          * the "Heart rate and load" panel has only a sentence and "Pair
            your watch" (`dnes_empty`) - the heart-rate number with its
            sentence (`dnes_bpm_box`) is hidden,
          * the header and the grid of the "My stats" cards are hidden,
          * the zones panel has one sentence instead of the bar and four
            rows (`dnes_zone_empty`) and does not stretch to the full
            column height.
        The first heart-rate sample brings back the full view. Rebuilt only
        on change."""
        ma_tep = TodayMixin._dnes_ma_tep(self)
        if ma_tep == getattr(self, "_dnes_ma_tep_stav", None):
            return
        bpm_box = getattr(self, "dnes_bpm_box", None)
        head = getattr(self, "dnes_stats_head", None)
        grid = getattr(self, "dashboard_grid", None)
        zone_panel = getattr(self, "dnes_zone_panel", None)
        obsah = getattr(self, "dnes_zone_obsah", None)
        veta = getattr(self, "dnes_zone_empty", None)
        if any(w is None for w in (bpm_box, head, grid, zone_panel, obsah, veta)):
            return
        self._dnes_ma_tep_stav = ma_tep

        def zabaleny(widget):
            try:
                return widget.winfo_manager() == "pack"
            except Exception:
                return False

        if ma_tep:
            if not zabaleny(bpm_box):
                # the heart-rate number is first in the panel - before the
                # live block / empty state
                pred = next((w for w in (getattr(self, "dnes_live", None),
                                         getattr(self, "dnes_empty", None))
                             if w is not None and zabaleny(w)), None)
                if pred is not None:
                    bpm_box.pack(fill="x", before=pred)
                else:
                    bpm_box.pack(fill="x")
            if not zabaleny(head):
                head.pack(fill="x", pady=(0, 10), before=zone_panel)
            if not zabaleny(grid):
                grid.pack(fill="x", before=zone_panel)
            if zabaleny(veta):
                veta.pack_forget()
            if not zabaleny(obsah):
                obsah.pack(fill="x")
            TodayMixin._rozpinaj(zone_panel, True)
        else:
            for widget in (bpm_box, head, grid, obsah):
                if zabaleny(widget):
                    widget.pack_forget()
            if not zabaleny(veta):
                veta.pack(fill="x", pady=(2, 4))
            TodayMixin._rozpinaj(zone_panel, False)

    @staticmethod
    def _rozpinaj(widget, rozpinaj):
        """Changes only a packed widget's `expand`, keeping its place in order.

        A CTk widget is repacked with what it was packed with
        (`_last_geometry_manager_call`, margins NOT multiplied by the scale)
        - CTk remembers it and reapplies it on a DPI change, so a bare
        `pack_configure` would be reverted after moving the window to
        another monitor. Everything else (dummies in tests) via
        `pack_configure`."""
        posledne = getattr(widget, "_last_geometry_manager_call", None)
        if isinstance(posledne, dict) and isinstance(posledne.get("kwargs"), dict):
            kw = dict(posledne["kwargs"])
            kw["expand"] = bool(rozpinaj)
            widget.pack(**kw)
        else:
            widget.pack_configure(expand=bool(rozpinaj))

    # How many sessions the app needs before it works out its own HR limit
    # (`hr_stats.dynamicky_kriticky`): the same rule as the sentence by the
    # sensor (`_kriticky_popis`) - pure PLAY sessions at least 5 minutes
    # long.
    def _relacie_na_ucenie(self, historia):
        """How many of `historia` count towards learning the limit - at most
        `KRITICKY_MIN_RELACII` (no need to know more, and going from the
        newest it can stop early: for a seasoned player it does not re-check
        400 curves)."""
        svet = getattr(self, "ALGORITMUS_SVET", hr_stats.WORLD_DEFAULT)
        treba = hr_stats.KRITICKY_MIN_RELACII
        n = 0
        for relacia in reversed(hr_stats.sessions_in_world(historia or [], svet)):
            if hr_stats.je_dost_dlha(relacia) and hr_stats.ciste_relacie([relacia]):
                n += 1
                if n >= treba:
                    break
        return n

    def _refresh_dnes_learning(self):
        """Quiet sentence under the state on Today while the app learns the limit
        (0.3 batch 4): "Still getting to know you — 1 of 3 play sessions".

        Only in the "Play" world (Work does not learn the limit and the
        sentence there would ask for play sessions forever) and only once
        some heart rate has arrived - before the first session Today has its
        own empty state. It disappears after the third session. Computed
        only on new history from the cache (once per ~20 s or after a
        session is saved), not on every sample."""
        try:
            text = ""
            svet = getattr(self, "ALGORITMUS_SVET", hr_stats.WORLD_DEFAULT)
            historia_fn = getattr(self, "_history_cached", None)
            if (getattr(self, "world", svet) == svet and callable(historia_fn)
                    and TodayMixin._dnes_ma_tep(self)):
                historia = historia_fn()
                kluc = (id(historia), svet)
                if kluc == getattr(self, "_dnes_learning_key", None):
                    text = getattr(self, "_dnes_learning_text", "")
                else:
                    n = TodayMixin._relacie_na_ucenie(self, historia)
                    celkom = hr_stats.KRITICKY_MIN_RELACII
                    text = tr("dnes.learning", n=n, celkom=celkom) if n < celkom else ""
                    self._dnes_learning_key = kluc
            else:
                self._dnes_learning_key = None
            if text != getattr(self, "_dnes_learning_text", ""):
                self._dnes_learning_text = text
                if callable(getattr(self, "_refresh_dnes_backdrop", None)):
                    self._refresh_dnes_backdrop(force=False)
        except Exception:
            app_log.exception("Dnes: veta o uceni sa nepodarilo obnovit")

    def _refresh_session_trace(self, connected):
        """Session trace on Today.

        Drawn from `HeartStats.trace()`, i.e. from the WHOLE session thinned
        out to 120 points - not from the last window. Without a sensor it
        stays empty, but the panel does not disappear: an empty outline is
        information ("I have not measured anything yet"), while a missing
        panel is a hole in the page.
        """
        trace = getattr(self, "dnes_trace", None)
        if trace is None or not trace.winfo_exists():
            return
        stats = self.hr_stats
        elapsed = max(0.0, time.time() - stats.session_start)
        if connected and stats.session_count >= 2:
            # No label: Today is the page the player looks at WHILE playing,
            # and every extra sentence pulls them out of the game. What the bar
            # means is explained by the questionnaire after the session and the
            # detail in History.
            trace.set_trace(stats.trace(), baseline=stats.session_baseline,
                            threshold=self.hr_critical_bpm, duration_s=elapsed,
                            triggers=stats.trigger_offsets,
                            activity=stats.activity_trace())
            meta = tr("dnes.trace_meta", time=self._fmt_minutes(elapsed),
                      n=stats.auto_triggers)
        else:
            trace.set_trace([])
            meta = ""
        self.dnes_trace_meta.configure(text=meta)

    def _refresh_zone_panel(self):
        """Split of the session's time into zones (bar + four rows)."""
        bar = getattr(self, "dnes_zone_bar", None)
        if bar is None or not bar.winfo_exists():
            return
        zones = self.hr_stats.zone_seconds
        bar.set_zones(zones)
        celkom = sum(max(0.0, float(v or 0.0)) for v in zones.values())
        for zone, label in self.dnes_zone_rows.items():
            sekundy = max(0.0, float(zones.get(zone, 0.0) or 0.0))
            podiel = (100.0 * sekundy / celkom) if celkom > 0 else 0.0
            label.configure(text=f"{podiel:.0f} %")

    # ---------- optional stats on Today ("My stats") ----------

    def _dashboard_stat_catalog(self):
        """(id, name, colour TOKEN) for all optional stats, in the order of the
        picker. In the grid the order is the player's (self.dashboard_stats)
        - it changes by dragging a card onto another.

        A token, not a value: the card and the dot in the picker have to be
        recoloured after a theme change, and a token finds its new colour
        by itself."""
        # COLOUR MARKS STATE, NOT THE METRIC (0.3, UX audit) - the same rule
        # as `HISTORY_METRICS`: a number is `text`, only a value that is a zone
        # gets a zone colour (calm, time over the limit), `blue` only recovery.
        # "Highest heart rate" in `zone_critical` looked like an alarm at an
        # ordinary in-game maximum.
        return [
            # heart rate belongs to the zone row, not to
            # success/warn/danger - otherwise the "Resting baseline" card
            # would glow a different green than the calm in the bar next to
            # it (see theme.ZONE_TOKENS)
            ("baseline", tr("metric.baseline.title"), "zone_calm"),
            ("hrr", tr("metric.hrr.title"), "blue"),
            ("over", tr("metric.over.title"), "zone_high"),
            ("breath", tr("metric.breath.title"), "text"),
            ("avg", tr("metric.avg.title"), "text"),
            ("max", tr("metric.max.title"), "text"),
            ("peak", tr("metric.peak.title"), "text"),
            ("week", tr("metric.week.title"), "text"),
            # 0.2: the same colour as the line of the same metric in History
            # (HISTORY_METRICS) - the card and the chart are one thing
            ("session_len", tr("metric.session_len.title"), "text"),
            ("last_cue", tr("metric.last_cue.title"), "text"),
            ("calm_time", tr("metric.calm_time.title"), "zone_calm"),
            ("signal", tr("metric.signal.title"), "text"),
            # neutral colour: neither of the two numbers is "the right one"
            ("felt_vs_measured", tr("metric.felt_vs_measured.title"), "text"),
        ]

    # NOTE: here used to be `_STAT_HISTORY` (which field of the saved summary
    # matches which card) and `_STAT_LOWER_IS_BETTER` (where "less" is good
    # news). Both existed EXCLUSIVELY for the micro-chart and the deviation
    # sentence on the card; along with them `_dashboard_stat_live` and
    # `ui_kit.MicroChart` went too. The reason is below at
    # `_dashboard_stat_value`.

    def _history_cached(self, max_age=20.0):
        """Session history from disk, at most once per `max_age` seconds.

        The cards are redrawn on EVERY heart-rate sample (and once per
        second even without one). The "Sessions this week" card read the
        JSON every time - several file opens per second for nothing. The
        cache is dropped after a session is saved (`_close_hr_session`), so
        a new record shows up right away, not 20 seconds later.
        """
        now = time.time()
        stamp, data = getattr(self, "_history_cache", (0.0, None))
        if data is None or now - stamp > max_age:
            data = self._history_sessions()
            self._history_cache = (now, data)
        return data

    # NOTE: here used to be `_dashboard_stat_live(stat_id)` (the card's current
    # value as a NUMBER, for comparing with history) and
    # `_dashboard_stat_trend(stat_id)` (a series of the last sessions, today's
    # deviation from their average and a colour by whether it is an
    # improvement). It was drawn on the card as a micro-chart plus a sentence
    # under the number.
    #
    # It went along with the card rework (see `ui_kit.StatCard`): a card
    # should be ONE calm figure, and the micro-chart with the sentence made it
    # three. The idea itself was right - "62 BPM" says nothing until you know
    # what is normal for you - and it lives on in History, where there is a
    # whole chart for the trend.
    #
    # Removed along with it too: `_STAT_HISTORY`, `_STAT_LOWER_IS_BETTER`,
    # `ui_kit.MicroChart` and the language keys `dashboard.delta_*`.

    def _dashboard_stat_value(self, stat_id):
        """(value, label) for one card - from the live self.hr_stats, "week"
        and "felt_vs_measured" from the saved session history
        (hr_sessions.json, via `_history_cached`)."""
        stats = self.hr_stats
        # WITHOUT HEART RATE "—", NOT ZERO (0.3, UX audit). A card derived from
        # heart rate that has not arrived yet showed "0:00 over the limit" and
        # an ASCII "-" - it looked like a measurement, not like "nothing yet".
        # The cue count stays a number: zero cues is a real value.
        bez_tepu = not getattr(stats, "session_count", 0)
        if stat_id == "baseline":
            base = stats.session_baseline
            return (str(int(round(base))) if base else "—", tr("dashboard.unit.baseline"))
        if stat_id == "hrr":
            hrr = stats.hrr if stats.session_count else None
            return (f"{hrr:+d}" if hrr is not None else "—", tr("dashboard.unit.hrr"))
        if stat_id == "over":
            if bez_tepu:
                return ("—", tr("dashboard.unit.over"))
            # from an hour on "1 h 15 min", not "75:12"
            # (`ui_kit.cas_text`, 0.3 4b)
            return (ui_kit.cas_text(int(stats.time_over)), tr("dashboard.unit.over"))
        if stat_id == "breath":
            return (str(stats.auto_triggers), tr("dashboard.unit.breath"))
        if stat_id == "avg":
            return (str(int(round(stats.average))) if stats.average else "—",
                    tr("dashboard.unit.avg"))
        if stat_id == "max":
            return (str(int(stats.session_max)) if stats.session_max else "—",
                    tr("dashboard.unit.max"))
        if stat_id == "peak":
            if bez_tepu:
                return ("—", tr("dashboard.unit.peak"))
            return (str(int(round(stats.peak_stress))), tr("dashboard.unit.peak"))
        if stat_id == "week":
            try:
                since = hr_stats.period_start_ts(hr_stats.PERIOD_WEEK)
                # Only the current world (B3-worlds). The saved list is
                # filtered, so a world switch shows at once, without
                # reading the disk.
                count, duration = hr_stats.count_sessions_since(
                    hr_stats.sessions_in_world(self._history_cached(), self.world),
                    since)
            except Exception:
                count, duration = 0, 0.0
            hours, rem = divmod(int(duration), 3600)
            minutes = rem // 60
            sub = f"{hours}h {minutes}m" if hours else f"{minutes}m"
            return (str(count), sub)
        # --- 0.2 (widgets-history). What is not known is "—", not zero. ---
        # Length, last cue and signal are only asked of an OPEN session: after
        # it is closed the clock would keep running from the start of an
        # already finished session and coverage would silently drop towards
        # zero.
        otvorena = getattr(self, "_hr_session_open", False)
        if stat_id == "session_len":
            unit = tr("dashboard.unit.session_len")
            if not otvorena:
                return ("—", unit)
            return (self._fmt_dlzka(time.time() - stats.session_start), unit)
        if stat_id == "last_cue":
            unit = tr("dashboard.unit.last_cue")
            ts = stats.last_auto_cue_ts() if otvorena else None
            if ts is None:
                return ("—", unit)
            return (tr("dashboard.fmt.min", n=int(max(0.0, time.time() - ts) // 60)), unit)
        if stat_id == "calm_time":
            # Like "over the limit": a session summary, it stays even after
            # the session is closed.
            calm = stats.calm_seconds()
            return ("—" if calm is None else tr("dashboard.fmt.min", n=int(calm // 60)),
                    tr("dashboard.unit.calm_time"))
        if stat_id == "signal":
            unit = tr("dashboard.unit.signal")
            pokrytie = stats.signal_coverage if otvorena else None
            if pokrytie is None:
                return ("—", unit)
            text = self._fmt_pokrytie(pokrytie)
            if stats.dropouts:
                text = f"{text} · {stats.dropouts}×"
            return (text, unit)
        if stat_id == "felt_vs_measured":
            try:
                # The last session of the CURRENT world (B3-worlds).
                par = hr_stats.citene_a_merane(hr_stats.posledna_relacia(
                    hr_stats.sessions_in_world(self._history_cached(), self.world)))
            except Exception:
                par = None
            return (self._fmt_citene_merane(par), tr("dashboard.unit.felt_vs_measured"))
        return ("—", "")

    def _rebuild_dashboard_stats_grid(self):
        grid = getattr(self, "dashboard_grid", None)
        if grid is None:
            return
        pal = self.pal
        for child in grid.winfo_children():
            child.destroy()
        self.dashboard_cards = {}
        self._dashboard_drag_state = None     # the old cards are gone
        catalog = {s[0]: s for s in self._dashboard_stat_catalog()}
        # The last card has no ✕ - one always stays (toggle_dashboard_stat).
        removable = len(self.dashboard_stats) > 1
        for i, stat_id in enumerate(self.dashboard_stats):
            meta = catalog.get(stat_id)
            if meta is None:
                continue
            _id, _title, color_token = meta
            value, _sub = self._dashboard_stat_value(stat_id)
            row, col = divmod(i, 2)
            # `metric.*.tag`, not `title`: the card shows a big number and
            # ONE WORD under it. `title` is a whole sentence and in German,
            # French and Russian it widens the whole right column at the
            # expense of the centre.
            card = ui_kit.StatCard(
                grid, pal, color_token, tr(f"metric.{stat_id}.tag"), value,
                # name of the "In-game" page by world (`metric.over.more`)
                tr(f"metric.{stat_id}.more", page=stranka_vhre(self)),
                on_remove=((lambda k=stat_id: self._toggle_dashboard_stat(k))
                           if removable else None),
                on_drag=lambda phase, e, k=stat_id: self._dashboard_drag(k, phase, e))
            card.grid(row=row, column=col, sticky="nsew",
                     padx=(0, 7) if col == 0 else (7, 0),
                     pady=(7, 0) if row > 0 else (0, 0))
            self.dashboard_cards[stat_id] = card
        self._refresh_dashboard_stats()

    def _refresh_dashboard_stats(self):
        # NOTE: here was also `card.set_trend(...)` from
        # `_dashboard_stat_trend` - a micro-chart of the last sessions and a
        # sentence about the deviation. The card is one figure now, not
        # three; the trend belongs in History, where there is a chart for it.
        for stat_id, card in getattr(self, "dashboard_cards", {}).items():
            value, _sub = self._dashboard_stat_value(stat_id)
            card.set_value(value)

    def _open_dashboard_picker(self):
        existing = getattr(self, "_dashboard_picker", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.destroy()
                    self._dashboard_picker = None
                    return
            except Exception:
                pass
        pal = self.pal
        btn = self.dashboard_edit_btn
        btn.update_idletasks()
        top = ui_kit.priprav_popup(tk.Toplevel(self.root))
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.configure(bg=pal["border"])
        self._dashboard_picker = top

        # The frame takes its height from its content. There used to be
        # `pack_propagate(False)` here without a height, so the frame stayed at
        # CTkFrame's default 200 px: 3 rows were visible, the fourth half, and
        # the rest could not be picked at all. The width (230) is held by a
        # zero-height spacer.
        frame = ctk.CTkFrame(top, fg_color=pal["surface"], corner_radius=ui_kit.RADIUS_PANEL,
                             border_width=1, border_color=pal["border"], width=230)
        frame.pack(padx=1, pady=1)
        ctk.CTkFrame(frame, width=228, height=0, fg_color="transparent").pack()
        ctk.CTkLabel(frame, text=tr("dashboard.picker_title").upper(), font=ui_kit.ui(10, "bold"),
                     text_color=pal["text_faint"], anchor="w").pack(fill="x", padx=12, pady=(10, 4))
        self._dashboard_picker_rows = ctk.CTkFrame(frame, fg_color="transparent")
        self._dashboard_picker_rows.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        self._render_dashboard_picker_rows()
        # one quiet line: the 4-card cap and that they can be moved
        ctk.CTkLabel(frame, text=tr("dashboard.picker_hint"), font=ui_kit.ui(10),
                     text_color=pal["text_faint"], anchor="w", justify="left",
                     wraplength=200).pack(fill="x", padx=12, pady=(0, 10))

        # right edge of the popup = right edge of the button (same as the
        # mockup's `position:absolute; top:100%; right:0`) - only AFTER the
        # content is built, otherwise the width would not be known yet. When
        # it does not fit below the button (low screen, window at the bottom),
        # it pops up above it.
        top.update_idletasks()
        w, h = top.winfo_reqwidth(), top.winfo_reqheight()
        x = btn.winfo_rootx() + btn.winfo_width() - w
        y = btn.winfo_rooty() + btn.winfo_height() + 4
        x, y = ui_kit.fit_popup(x, y, w, h, ui_kit.work_area(btn), btn.winfo_rooty())
        top.geometry(f"+{x}+{y}")

        top.bind("<FocusOut>", lambda _e: self._close_dashboard_picker())
        top.bind("<Escape>", lambda _e: self._close_dashboard_picker())
        top.after(60, top.focus_force)

    def _close_dashboard_picker(self):
        top = getattr(self, "_dashboard_picker", None)
        if top is not None:
            try:
                top.destroy()
            except Exception:
                pass
        self._dashboard_picker = None

    def _render_dashboard_picker_rows(self):
        container = getattr(self, "_dashboard_picker_rows", None)
        if container is None:
            return
        try:
            if not container.winfo_exists():
                return
        except Exception:
            return
        for child in container.winfo_children():
            child.destroy()
        pal = self.pal
        for stat_id, title, color_token in self._dashboard_stat_catalog():
            on = stat_id in self.dashboard_stats
            # A row where a click does nothing has no hand cursor:
            #  - an unselected metric when the 4 cards are full -> also faded
            #    text (freed up once you remove a card)
            #  - the last selected metric (one card always stays) -> looks
            #    selected, it just does not react
            clickable = dashboard_stat_clickable(self.dashboard_stats, stat_id)
            if on:
                text_color = pal["text"]
            elif clickable:
                text_color = pal["text_dim"]
            else:
                text_color = pal["text_faint"]
            row = ctk.CTkFrame(container, fg_color=pal["surface_alt"] if on else "transparent",
                               corner_radius=6)
            row.pack(fill="x", pady=1)
            inner = ctk.CTkFrame(row, fg_color="transparent")
            # Lower rows (label 20 px instead of CTkLabel's default 28, margin
            # 4 instead of 6): since 0.2 the catalogue has 13 metrics and the
            # picker must stay on screen in full. Measured at 150 %: row 60 ->
            # 42 px, the whole picker with 13 rows 719 px (before, with 8 rows,
            # 643).
            inner.pack(fill="x", padx=8, pady=4)
            ctk.CTkFrame(inner, width=8, height=8, corner_radius=4,
                        fg_color=pal[color_token] if (on or clickable) else pal["text_faint"]
                        ).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(inner, text=title, font=ui_kit.ui(12), height=20,
                         text_color=text_color,
                         anchor="w").pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(inner, text="✓" if on else "", font=ui_kit.ui(11, "bold"),
                         text_color=pal["accent"], width=16, height=20).pack(side="right")
            if not clickable:
                continue
            for w in (row, inner) + tuple(inner.winfo_children()):
                try:
                    w.configure(cursor="hand2")
                except Exception:
                    pass
                w.bind("<Button-1>", lambda _e, k=stat_id: self._toggle_dashboard_stat(k))

    def _toggle_dashboard_stat(self, stat_id):
        """Click on a row in the picker or ✕ on a card. Both the card cap and
        "the last one stays" are handled by `toggle_dashboard_stat`; when
        nothing changes, nothing is saved or rebuilt."""
        new = toggle_dashboard_stat(self.dashboard_stats, stat_id)
        if new == self.dashboard_stats:
            return
        self.dashboard_stats = new
        self.save_settings()
        self._rebuild_dashboard_stats_grid()
        self._render_dashboard_picker_rows()

    # ---- moving a card by dragging (swapping places) ----
    #
    # You grab a card (number, label, edge - not ⓘ/✕), drag it at least
    # DASHBOARD_DRAG_PX and drop it on another card: they swap places. With
    # a 2x2 grid the swap is exactly predictable - the highlighted card is
    # exactly where yours will land. No "ghost" window, animation or
    # shifting of the other cards.
    #
    # THE RELEASE DECIDES, not the movement: the press->release distance and
    # the card under the release point. Movement only draws the highlight
    # and the cursor. With a real mouse, sometimes not a single B1-Motion
    # reaches Tk (a quick flick, touchpad) - a drop that depended on it
    # would be silently lost.

    def _dashboard_card_at(self, x_root, y_root):
        """stat_id of the card under a screen point, or None (gap, outside)."""
        for stat_id, card in getattr(self, "dashboard_cards", {}).items():
            try:
                x0, y0 = card.winfo_rootx(), card.winfo_rooty()
                if (x0 <= x_root < x0 + card.winfo_width()
                        and y0 <= y_root < y0 + card.winfo_height()):
                    return stat_id
            except Exception:
                continue
        return None

    def _dashboard_drag_reset(self):
        """Drops the highlight and the cursor. Called on EVERY press: when the
        release got lost (alt-tab mid-drag), nothing is left hanging."""
        st, self._dashboard_drag_state = getattr(self, "_dashboard_drag_state", None), None
        for card in getattr(self, "dashboard_cards", {}).values():
            try:
                card.set_drag_look(None)
            except Exception:
                pass
        if st and st.get("widget") is not None:
            try:
                st["widget"].configure(cursor="")
            except Exception:
                pass

    def _dashboard_drag(self, stat_id, phase, event):
        if phase == "press":
            self._dashboard_drag_reset()
            self._dashboard_drag_state = {
                "id": stat_id, "x": event.x_root, "y": event.y_root,
                "widget": event.widget, "active": False, "target": None}
            return
        st = getattr(self, "_dashboard_drag_state", None)
        if not st or st["id"] != stat_id:
            return
        moved = (abs(event.x_root - st["x"]) + abs(event.y_root - st["y"])
                 >= self.DASHBOARD_DRAG_PX)
        cards = getattr(self, "dashboard_cards", {})
        if phase == "move":
            if not st["active"]:
                if not moved:
                    return
                st["active"] = True
                if stat_id in cards:
                    cards[stat_id].set_drag_look("source")
                try:
                    st["widget"].configure(cursor="fleur")
                except Exception:
                    pass
            target = self._dashboard_card_at(event.x_root, event.y_root)
            if target == stat_id:
                target = None
            if target != st["target"]:
                if st["target"] in cards:
                    cards[st["target"]].set_drag_look(None)
                if target in cards:
                    cards[target].set_drag_look("target")
                st["target"] = target
            return
        if phase != "release":
            return
        self._dashboard_drag_reset()
        if not moved:
            return                              # an ordinary click
        target = self._dashboard_card_at(event.x_root, event.y_root)
        new = swap_dashboard_stats(self.dashboard_stats, stat_id, target)
        if new == self.dashboard_stats:
            return                              # gap, outside, onto itself
        self.dashboard_stats = new
        self.save_settings()
        # after_idle: the rebuild also destroys the widget handling the event
        self.root.after_idle(self._rebuild_dashboard_stats_grid)

    # NOTE: here used to be `_refresh_kamae_metrics()` - session length, cue
    # count and heart rate, drawn on the right in the breathing bar. Removed:
    # length and count are right beside it in the right panel of this same
    # page, so the bar only repeated them, and the bar should carry state,
    # not a score.
    # `self._listen_started` is still used (session length in the panel).

    # ---------- Today page centre on the canvas (dojo, enso, text) ----------

    def _build_dnes_backdrop(self, parent, pal):
        """Hooks the redraw of the centre onto a size change.

        No longer builds a widget - the dojo, enso and text are drawn by
        `_paint_dnes_canvas` on `self.dnes_canvas` (built in
        `_build_dnes_page`). Here only the veil colour is stored and
        `<Configure>` is hooked. The photo is in `background.py`; when
        there is none, `background.hero/load` returns None and the theme
        background stays.
        """
        self._backdrop_size = (0, 0)
        self._dnes_dojo_tk = None
        parent.bind("<Configure>", self._naplanuj_backdrop, add="+")

    def _naplanuj_backdrop(self, _event=None):
        """Recomputes the background only once the size settles for a moment.

        This is not cosmetics: when smoothly dragging the window between
        screens the photo would otherwise be rescaled at every intermediate
        step, and of those only one is used - the last one.
        """
        job = getattr(self, "_backdrop_job", None)
        if job is not None:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
        try:
            self._backdrop_job = self.root.after(
                self.BACKDROP_DEBOUNCE_MS, self._refresh_dnes_backdrop)
        except Exception:
            # The window is closing - there is nothing left to redraw.
            self._backdrop_job = None

    def _refresh_dnes_backdrop(self, _event=None, force=False):
        """Redraws the Today centre (dojo + enso + text) on `dnes_canvas`.

        Two dojo modes: in the STOPPED state the bright DOJO HERO, which
        is static - one fixed breath phase (`_start_dnes_hero`); it no
        longer breathes (that made the window flicker). When the app is
        listening, a dimmed photo. The expensive LANCZOS is done only when
        size/breath/theme changes (key `_backdrop_size`); the enso and text
        are always redrawn (they are cheap). Called from: `<Configure>`
        (debounced), the animation tick (now only for the enso), a state
        change, `_EnsoHero._emit()` (set_live/armed/graduate/set_pal)."""
        canvas = getattr(self, "dnes_canvas", None)
        stred = getattr(self, "dnes_stred", None)
        if canvas is None or stred is None:
            return
        try:
            w, h = stred.winfo_width(), stred.winfo_height()
        except Exception:
            return
        if w < 40 or h < 40:
            return
        # --- 1) DOJO image (expensive LANCZOS) - cached by size/breath/theme ---
        hero_on = bool(getattr(self, "_dnes_hero_on", False))
        faza = getattr(self, "_dnes_breath_phase", 0.0)
        breath = round(((1.0 - math.cos(2.0 * math.pi * faza)) / 2.0) * 8) / 8.0
        scrim = self.pal["bg"]
        kluc = (w, h, hero_on, breath if hero_on else 0, scrim)
        if force or _ImageTk is None or kluc != getattr(self, "_backdrop_size", None):
            self._backdrop_size = kluc
            self._dnes_dojo_tk = self._build_dojo_photo(w, h, hero_on, breath, scrim)
        # --- 2) redraw the canvas: dojo + enso + text (cheap) ---
        # WARNING: `_ensure_dnes_tick()` MUST NOT be called here. The redraw
        # also runs from inside `_tick_dnes`, and when `_tick_dnes` clears the
        # job at its start, `_ensure_dnes_tick` would see it as "not running"
        # and start another chain (or recurse directly). Only a state change
        # starts the tick (below).
        try:
            self._paint_dnes_canvas(canvas, w, h, getattr(self, "_dnes_dojo_tk", None))
        except Exception:
            app_log.exception("Dnes canvas: prekreslenie zlyhalo")

    def _build_dojo_photo(self, w, h, hero_on, breath, scrim):
        """PIL -> ImageTk dojo for the Canvas. The Canvas uses PHYSICAL
        pixels 1:1 (unlike `CTkImage`, which scales logical pixels by
        itself), so we build directly at (w, h) from `winfo_*` and draw
        without rescaling."""
        if _ImageTk is None:
            return None
        try:
            peak = self.DNES_SCRIM_PEAK
            if hero_on:
                img = background.hero(w, h, breath=breath, scrim=scrim,
                                      scrim_peak=peak, blur=True,
                                      log=self.log_threadsafe)
            else:
                img = background.load(w, h, self.background_opacity,
                                      log=self.log_threadsafe)
                if img is not None and scrim:
                    try:
                        img = background._pridaj_scrim(img.convert("RGBA"),
                                                       scrim, peak)
                    except Exception:
                        pass
            if img is None:
                return None
            return _ImageTk.PhotoImage(img)
        except Exception:
            app_log.exception("Dnes dojo: obrazok zlyhal")
            return None

    def _cvfont(self, size, weight="normal", underline=False):
        """Tk font for drawing on the Canvas in PHYSICAL pixels.

        `create_text` is not a CTk widget, so we have to add the DPI scale
        ourselves: logical size * scale = physical px (a negative size =
        px, which `tk scaling` no longer multiplies). We cache the fonts -
        building them 8x/s is not needed."""
        mierka = getattr(self, "_dnes_mierka", 1.0)
        kluc = (size, weight, underline, round(mierka, 2))
        f = self._dnes_fonts.get(kluc)
        if f is None:
            # Font from `ui_kit.fonts()`, not hard-coded "Segoe UI": in
            # Japanese and Chinese the app has its own font with CJK glyphs
            # (otherwise Tk looked up every character in another fallback font
            # and the line fell apart).
            f = tkfont.Font(family=ui_kit.fonts()["ui"],
                            size=-max(1, int(round(size * mierka))),
                            weight=weight, underline=underline)
            self._dnes_fonts[kluc] = f
        return f

    def _paint_dnes_canvas(self, canvas, w, h, dojo):
        """Composes dojo + enso + text onto one surface - no box and NO FLICKER.

        There are two keys against flicker:
          (1) if NOTHING changed visually, the redraw is SKIPPED entirely -
              otherwise the stopped state was redrawn 8x/s (every tick a
              new `PhotoImage`, even when the frame is the same) and the
              window flickered;
          (2) image items (dojo, enso) are PERMANENT - only their content
              changes via `itemconfigure`, they are never deleted
              (`delete`), so not even the enso animation flickers. The
              text block is rebuilt only when text/size/theme changes
              (`_layout_dnes_items`).
        `render()` returns a cached frame (same object = same frame), so
        `id()` is enough for the comparison."""
        pal = self.pal
        try:
            mierka = (ctk.ScalingTracker.get_widget_scaling(self.dnes_stred)
                      or 1.0)
        except Exception:
            mierka = 1.0
        self._dnes_mierka = mierka
        enso = getattr(self, "enso", None)
        enso_px = max(48, int(self.ENSO_SIZE * mierka))
        pil = None
        if enso is not None:
            try:
                pil = enso.render(enso_px)
            except Exception:
                pil = None
        titul = getattr(self, "_dnes_titul", "") or ""
        veta = getattr(self, "_dnes_veta", "") or ""
        last = getattr(self, "_dnes_lastcue_text", "") or ""
        # The quiet "no pause in the input" line goes under it, just as dimmed.
        nonstop = getattr(self, "_dnes_nonstop_text", "") or ""
        if nonstop:
            last = f"{last}\n{nonstop}" if last else nonstop
        # And at the very bottom "still getting to know you"
        # (`_refresh_dnes_learning`).
        ucenie = getattr(self, "_dnes_learning_text", "") or ""
        if ucenie:
            last = f"{last}\n{ucenie}" if last else ucenie

        # (1) SKIP an identical redraw.
        frame_sig = (w, h, round(mierka, 2), id(dojo), id(pil),
                     titul, veta, last, pal["bg"])
        if frame_sig == getattr(self, "_dnes_frame_sig", None):
            return
        self._dnes_frame_sig = frame_sig

        try:
            canvas.configure(bg=pal["bg"])
        except Exception:
            pass

        # (2) we rebuild the text block + positions only when the
        # text/size/theme changes.
        text_sig = (w, h, round(mierka, 2), titul, veta, last, enso_px,
                    pal["text"], pal["text_dim"], pal["text_faint"])
        if (getattr(self, "_dnes_items", None) is None
                or text_sig != getattr(self, "_dnes_text_sig", None)):
            self._layout_dnes_items(canvas, w, h, mierka, enso_px,
                                    titul, veta, last, pal)
            self._dnes_text_sig = text_sig

        items = self._dnes_items or {}
        # dojo (permanent item at the back) - swap the image ONLY when it
        # really changed.
        di = items.get("dojo")
        if di is not None:
            if dojo is not None:
                if dojo is not getattr(self, "_dnes_cur_dojo", None):
                    try:
                        canvas.itemconfigure(di, image=dojo, state="normal")
                        canvas.coords(di, w // 2, h // 2)
                    except Exception:
                        pass
                    self._dnes_tk_imgs["dojo"] = dojo
                    self._dnes_cur_dojo = dojo
            else:
                try:
                    canvas.itemconfigure(di, state="hidden")
                except Exception:
                    pass
                self._dnes_cur_dojo = None
        # enso (permanent item) - a new PhotoImage and a swap ONLY when the
        # frame really changed (`render()` returns a cached object; same id =
        # same frame). Without this guard the enso was swapped on EVERY redraw
        # (even when it stood still) and the window flickered.
        ei = items.get("enso")
        if (ei is not None and pil is not None and _ImageTk is not None
                and pil is not getattr(self, "_dnes_cur_pil", None)):
            try:
                tkimg = _ImageTk.PhotoImage(pil)
                self._dnes_tk_imgs["enso"] = tkimg
                canvas.itemconfigure(ei, image=tkimg)
            except Exception:
                pass
            self._dnes_cur_pil = pil

    def _layout_dnes_items(self, canvas, w, h, mierka, enso_px, titul, veta,
                           last, pal):
        """(Re)builds the permanent image items (dojo, enso) + the text block
        and centres the whole block vertically. Called ONLY when
        text/size/theme changes, not every tick - which is why it can afford
        to measure and move. The enso has the tag "block" (it is centred
        with the text), but NOT "dtext" (rebuilding the text must not delete
        it, it is a permanent item changed via `itemconfigure`)."""
        self._dnes_hit = {}
        # The items may have just been created - reset "what is on the canvas",
        # so that `_paint` applies both the dojo and the enso image again.
        self._dnes_cur_dojo = None
        self._dnes_cur_pil = None
        items = getattr(self, "_dnes_items", None)
        if items is None:
            items = self._dnes_items = {}
        # dojo - permanent item at the very back
        if items.get("dojo") is None:
            items["dojo"] = canvas.create_image(w // 2, h // 2, anchor="center")
        try:
            canvas.tag_lower(items["dojo"])
        except Exception:
            pass
        # enso - permanent item
        if items.get("enso") is None:
            items["enso"] = canvas.create_image(w // 2, 0, anchor="n",
                                                tags=("block", "enso"))
        canvas.coords(items["enso"], w // 2, 0)

        canvas.delete("dtext")          # only the text block; the images stay
        cx = w // 2
        gap = max(4, int(10 * mierka))
        wrap = min(int(360 * mierka), max(140, w - int(48 * mierka)))
        y = enso_px + gap
        if titul:
            y = self._canvas_text(canvas, cx, y, titul, self._cvfont(19, "bold"),
                                  pal["text"], wrap=wrap, shadow=True) + gap
        if veta:
            y = self._canvas_text(canvas, cx, y, veta, self._cvfont(12),
                                  pal["text_dim"], wrap=wrap, shadow=True) + int(gap * 1.4)
        # NOTE: here was the line "© 2026 Dandurfin · GPLv3" (name clickable to
        # Twitch). It left the hero (0.3, UX audit): the licence and version
        # are in the title bar on every page and the author with links in
        # About (ⓘ) - in the centre of the state it was a third, least needed
        # line.
        if last:
            y = self._canvas_text(canvas, cx, y, last, self._cvfont(10),
                                  pal["text_faint"], wrap=wrap) + gap

        # Block = enso (top, height enso_px) + text under it (bottom `y`).
        # WARNING: bbox("block") does NOT INCLUDE the enso, because its image is
        # set only in `_paint_dnes_canvas` (here the item has no image yet ->
        # bbox ~ a point). That is why we centre by the KNOWN height of the
        # block [0, y], not by bbox - otherwise the enso "fell out" of the
        # measurement and the whole block sat too high.
        dy = int(h / 2 - y / 2)
        if dy:
            canvas.move("block", 0, dy)
        # Click zone of the enso - also from the known geometry (bbox("enso")
        # is None while the item has no image), otherwise the enso would be
        # UNCLICKABLE.
        ex0 = w // 2 - enso_px // 2
        ey0 = dy
        self._dnes_hit["enso"] = (ex0, ey0, ex0 + enso_px, ey0 + enso_px)
        self._record_dnes_hits(canvas)   # credit via bbox (has text); enso stays
        TodayMixin._podlozka_textu(self, canvas, mierka, pal, items)

    # Backing under the status text (0.3 batch 4b): opacity in the centre
    # (0-255) and how many logical px it extends beyond the text.
    PODLOZKA_ALFA = 170
    PODLOZKA_OKRAJ = (20, 10)
    PODLOZKA_ROZMAZ = 14

    def _podlozka_textu(self, canvas, mierka, pal, items):
        """Soft dark backing behind the status text - only if a photo is there.

        Short states ("Stopped") sat in the darkened centre of the photo
        (`background._scrim_maska`), but the long sentence about the busy
        port reached all the way to the glow of the lanterns and the
        reflection on the floor - light text on a light background (de/ja
        are even longer). The backing goes behind the text block, however
        long it is: colour `bg`, blurred edges, no box with an edge (the
        same principle as the veil behind the enso). It is an image with
        alpha between the dojo and the text; it is rebuilt with the text
        (tag "dtext"). Never raises an exception - without the backing the
        text stays with its shadow as before."""
        try:
            if getattr(self, "_dnes_dojo_tk", None) is None or _ImageTk is None:
                return
            box = canvas.bbox("dtext")
            if not box:
                return
            from PIL import Image, ImageDraw, ImageFilter
            ox, oy = (int(v * mierka) for v in self.PODLOZKA_OKRAJ)
            rozmaz = max(2, int(self.PODLOZKA_ROZMAZ * mierka))
            sirka = (box[2] - box[0]) + 2 * (ox + rozmaz)
            vyska = (box[3] - box[1]) + 2 * (oy + rozmaz)
            maska = Image.new("L", (sirka, vyska), 0)
            ImageDraw.Draw(maska).rounded_rectangle(
                [rozmaz, rozmaz, sirka - rozmaz, vyska - rozmaz],
                radius=int(14 * mierka), fill=self.PODLOZKA_ALFA)
            maska = maska.filter(ImageFilter.GaussianBlur(rozmaz / 2.0))
            farba = pal["bg"].lstrip("#")
            obr = Image.new("RGBA", (sirka, vyska),
                            tuple(int(farba[i:i + 2], 16) for i in (0, 2, 4)) + (0,))
            obr.putalpha(maska)
            tkimg = _ImageTk.PhotoImage(obr)
            self._dnes_tk_imgs["podlozka"] = tkimg
            polozka = canvas.create_image((box[0] + box[2]) // 2, (box[1] + box[3]) // 2,
                                          image=tkimg, anchor="center",
                                          tags=("dtext", "podlozka"))
            # above the dojo, below the enso and the text
            canvas.tag_lower(polozka)
            if items.get("dojo") is not None:
                canvas.tag_raise(polozka, items["dojo"])
        except Exception:
            app_log.debug("Dnes: podlozka pod textom sa nenakreslila", exc_info=True)

    def _canvas_text(self, canvas, cx, y_top, text, font, fill, wrap=0, shadow=False):
        """Centred (multi-line) text from `y_top` downward; returns the bottom.
        `shadow` adds a dark +1px shadow for legibility without a box.

        Japanese and Chinese are broken in advance by
        `ui_kit.zalom_kinsoku` (0.3 batch 4b) - Tk would start a line with
        「。」 or 「）」."""
        kw = dict(anchor="n", justify="center", font=font)
        if wrap:
            kw["width"] = wrap
            zmeraj = getattr(font, "measure", None)
            if callable(zmeraj):
                text = ui_kit.zalom_kinsoku(text, wrap, zmeraj)
        if shadow:
            canvas.create_text(cx + 1, y_top + 1, text=text, fill="#0b0b0f",
                               tags=("block", "dtext"), **kw)
        item = canvas.create_text(cx, y_top, text=text, fill=fill,
                                  tags=("block", "dtext"), **kw)
        bb = canvas.bbox(item)
        return bb[3] if bb else y_top

    def _record_dnes_hits(self, canvas):
        """Remembers the bboxes of the click zones (enso) AFTER centring."""
        for tag in ("enso",):
            try:
                bb = canvas.bbox(tag)
            except Exception:
                bb = None
            if bb:
                self._dnes_hit[tag] = bb

    def _dnes_set_cursor(self, cur):
        if cur == getattr(self, "_dnes_cursor", ""):
            return
        self._dnes_cursor = cur
        try:
            self.dnes_canvas.configure(cursor=cur)
        except Exception:
            pass

    @staticmethod
    def _in_bbox(x, y, bb):
        return bb is not None and bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3]

    def _dnes_canvas_motion(self, event):
        hit = getattr(self, "_dnes_hit", {})
        over = self._in_bbox(event.x, event.y, hit.get("enso"))
        self._dnes_set_cursor("hand2" if over else "")

    def _dnes_canvas_click(self, event):
        hit = getattr(self, "_dnes_hit", {})
        if self._in_bbox(event.x, event.y, hit.get("enso")):
            # Click on the mark = listening switch (just as the widget had it).
            try:
                self.toggle_listening()
            except Exception:
                app_log.exception("enso klik: prepnutie zlyhalo")
