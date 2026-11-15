"""Cue trigger and cue style - part of the main app (DandurfApp from app.py).

CuesMixin is a mixin of DandurfApp: app.py inherits it, and all the state (the
`trigger.CueTrigger` state machine, the session's ladder rung and cue style,
the texts on Today) lives on DandurfApp. Only the methods that work with it
via `self` are here - the mixin has no __init__ and no attributes of its own.

Moved from app.py unchanged:
  * the automatic cue trigger (phase 2) - cancelling the arming, the state in
    the breathing bar and in the centre of Today, the "last spoke" line, the
    share of silent cues and the ladder rung for a new session,
  * cue style (onboarding step 5, Settings -> Sound) - the first part of the
    section: labels and the style choice. Drawing the centre of Today, which
    in app.py sat under the same marker, is in app_today.py.

Cue delivery (`_tick_cue_trigger`, `_on_cue_event`,
`_fire_somatic_cue`) is in app_today.py.

WARNING for tests: `_refresh_last_cue` reads `time` from this module - the
fake clock has to be slipped in here too (`app_cues.time`), not only on the
app module.
"""

import time

import data_io
import hr_stats
import rebrik
import trigger
from i18n import tr

from app_spolocne import app_log

# Style names in the "How I speak up" row (Settings -> Sound), 0.3. Until
# then it showed the answers from the introduction
# (`ui_dialogs.CUE_STYLE_LABELS`, e.g. "Voice is fine") - an answer to the
# question "when a game winds you up...", which is not in Settings. The
# introduction keeps its answers; the order and the styles are the same.
CUE_STYLE_SETTINGS_LABELS = ((rebrik.STYL_HLAS, "cue_style.voice"),
                             (rebrik.STYL_ZVUK, "cue_style.sound"),
                             (rebrik.STYL_OBRAZ, "cue_style.visual"))


class CuesMixin:
    """Cue trigger, ladder and cue style (DandurfApp mixin)."""

    # ---------- automatic cue trigger (phase 2) ----------

    def _suspend_cue_trigger(self, reason):
        """Cancels the arming. Call it on a heart-rate dropout and on snooze -
        a half-armed state does not exist, the 90 s count starts over."""
        try:
            udalost = self.cue_trigger.suspend(reason)
        except Exception:
            app_log.exception("spustac hlasky: suspend zlyhal")
            return
        if udalost is not None:
            self._on_cue_event(udalost)
        # `suspend` returns an event ONLY when the state machine was armed;
        # when it was not, it returns None and `_on_cue_event` is not called.
        # That is why the ring is dropped here, not there - otherwise it would
        # stay lit after a snooze in the unarmed state.
        self._set_enso_armed(False)

    def _kamae_state_text(self):
        """(title, subtitle) for the breathing bar - THREE states, not two.

        The spec shifts the Today page's centre of gravity from numbers to
        state, and "armed" is a state that until now could not be read
        anywhere except from the ring on the enso - and that one is 68 px.
        The bar is the largest element of the window, so it is the one that
        can carry the sentence saying WHY nothing is happening.

        Deliberately without a countdown ("47 s left"). Measuring the
        player's own state in front of their eyes is exactly what the app
        must not do; the sentence says it is waiting, and that is enough.
        """
        # PORT IN USE (0.3 batch 4) - before everything else, even before
        # "Stopped". It is a fault the player does not know about and that
        # needs fixing before they start it: the heart rate from the phone
        # will not arrive, whether watching is on or not. Before 0.3 this
        # showed the generic "Waiting for heart rate" (during the retries)
        # and, after giving up, "Without a watch" - but the watch is fine and
        # the player did not turn receiving off; another program holds the
        # port. Applies to the retries ("busy") and to giving up
        # ("busy_gave_up"); the state is cleared only by turning off, a new
        # attempt or a port change (`app_session`).
        if getattr(self, "_hr_state", None) in ("busy", "busy_gave_up"):
            return self._kamae_port_obsadeny()
        if not self.listening:
            # FIRST START (0.3): watching turns on by itself as soon as the
            # voice is ready (`app._zacni_sledovat_po_priprave_hlasu`, at
            # most 15 s). "Stopped, start me with the button" would send the
            # player off to click - and a click would stop the voice
            # preparation.
            if getattr(self, "_prvy_start_caka", False):
                return tr("kamae.voice_prep"), tr("kamae.voice_prep_sub")
            return self._kamae_zastavene()
        # FOURTH STATE: I am listening, but have nothing to listen to.
        #
        # Without a heart-rate source `start_listening` does not start
        # receiving at all and `_tick_cue_trigger` returns right away - so the
        # app really watches nothing. Yet the bar said "Watching your heart
        # rate, waiting for a good moment", i.e. a sentence that was not true.
        # The player went off to play believing the app was running, and
        # waited all evening for a cue that had nowhere to come from.
        if not self.hr_monitoring_enabled:
            return tr("kamae.no_watch"), tr("kamae.no_watch_sub")
        # LISTENING, BUT NO HEART RATE COMING IN.
        #
        # Until now this returned "Watching your heart rate, waiting..." based
        # only on the toggle - even when the watch dropped out, the port was
        # taken or nothing had connected yet. The bar is the largest element
        # of the window; claiming "watching" on it when the app has nothing to
        # go on is exactly the bug that was already fixed once for a
        # switched-off sensor. The truth follows the CONNECTION STATE, not the
        # toggle: we are really watching only when heart rate is coming in.
        if self._hr_state != "connected" or self._hr_last_bpm is None:
            # The "Waiting for heart rate" title also holds for a dropout.
            # The sentence under it does not: "nothing is coming from the
            # watch yet" belongs before the first sample, not in the middle
            # of an evening when heart rate was coming in and stopped.
            if getattr(self, "_hr_lost", False):
                return tr("kamae.no_hr"), tr("kamae.lost_sub")
            # RECEIVING IS ON, BUT THE PHONE DID NOT CONNECT WITHIN ~20 S
            # (`_hr_no_client`). "Waiting for heart rate" would wait here all
            # evening without a single hint, although the cause is almost
            # always on the network side (firewall, Public network, new PC
            # address) - the sentence says which one, and where the steps are.
            if getattr(self, "_hr_state", None) == "no_client":
                return tr("kamae.no_client"), tr("kamae.no_client_sub")
            return tr("kamae.no_hr"), tr("kamae.no_hr_sub")
        # "NOT NOW" (24. 9.): still listening and measuring, but no cue comes.
        # "Waiting for a good moment" would promise exactly what the player
        # turned off.
        if getattr(self, "_snooze_job", None) is not None:
            # The sentence names the shortcut only when it really works
            # (0.3): one that is turned off or held by another program would
            # promise something that does not work. The tray icon menu always
            # works.
            skratka = getattr(self, "_skratka_teraz_nie", lambda: "")()
            if skratka:
                return tr("kamae.snoozed"), tr("kamae.snoozed_sub",
                                               until=self._snooze_do(), combo=skratka)
            return tr("kamae.snoozed"), tr("kamae.snoozed_sub_tray",
                                           until=self._snooze_do())
        if self._cue_armed:
            return tr("kamae.armed"), tr("kamae.armed_sub")
        # The cue ladder is paused (`rebrik.py`): "waiting for a good moment"
        # would promise a cue that will not come in this session.
        if (getattr(self, "_hr_session_open", False)
                and getattr(self, "_cue_rung", None) == rebrik.PAUZA):
            return tr("kamae.running"), tr("kamae.paused_sub")
        return tr("kamae.running"), tr("kamae.running_sub")

    def _kamae_port_obsadeny(self):
        """(title, sentence) for a busy heart-rate port - what is going on and
        what to do about it.

        The most common cause is OBS with its own WebSocket server, which
        uses the same port 4455 (README, "Streaming with OBS?"). The
        sentence names both fixes and the place where the port is changed,
        by the name it has in the window: the "In-game" page is called
        "Screen" in the Work world (`_nazov_vhre`). Test dummies do not have
        `_nazov_vhre` - then the name from Play applies."""
        port = getattr(self, "hr_port", None) or ""
        nazov = getattr(self, "_nazov_vhre", None)
        stranka = nazov() if callable(nazov) else tr("nav.vhre_short")
        return (tr("kamae.port_busy", port=port),
                tr("kamae.port_busy_sub", page=stranka,
                   card=tr("settings.hr_section_title")))

    @staticmethod
    def _texty_pasu():
        """(stopped button text, watching button text, quiet sentence) for
        the main switch in the breathing bar (`ui_kit.KamaeBar`, 0.3
        batch 4).

        The same words as in the tray icon menu (`tray.start` /
        `tray.stop`), just with the ▶ / ■ sign - the player looks for one
        switch, not two different names for the same thing. Which of the
        two texts the button is showing right now is decided by
        `KamaeBar.set_live` (from `_apply_listening_visuals`), not by this
        function - that is why the button cannot drift apart from the
        tray."""
        return tr("dock.start"), tr("dock.stop"), tr("kamae.bar_hint")

    def _refresh_kamae_state_text(self):
        """Rewrites the bar when the state has changed. Called from
        `_set_enso_armed`, i.e. from the same path as the ring - so that
        the text and the marker cannot drift apart.

        It is also the ONLY path that all changes of the heart-rate state
        (`_apply_hr_status`, `_apply_hr_bpm`, receiving turned off, the
        phone did not connect) and of watching go through - which is why
        the dot in the side panel is redrawn from here too
        (`_refresh_state_dot`: watching, but the heart rate dropped out)."""
        bar = getattr(self, "kamae", None)
        if bar is not None:
            try:
                # The bar carries the state through MOTION (breathing/still)
                # and the button; the state itself (Stopped/Watching/...) is in
                # the centre of the page (hero), so it is not duplicated. See
                # the KamaeBar docstring.
                bar.set_texts(*self._texty_pasu())
            except Exception:
                app_log.exception("dychajuci pas: prepis textu zlyhal")
        bodka = getattr(self, "_refresh_state_dot", None)
        if callable(bodka):
            bodka()
        if bar is None:
            return
        self._refresh_dnes_state_text()

    def _refresh_last_cue(self):
        """The "last spoke X min ago" line.

        Until something has happened in the session, the line is NOT SHOWN.
        An empty line with a zero would be a counter, and the app is meant
        to show state, not a score.
        """
        if not hasattr(self, "dnes_canvas"):
            return
        cues = getattr(self.hr_stats, "cues", None) or []
        if not cues or not self.listening:
            if getattr(self, "_dnes_lastcue_text", ""):
                self._dnes_lastcue_text = ""
                self._refresh_dnes_backdrop(force=False)
            return
        posledna = cues[-1]
        # We take the label from the same slot that `_fire_somatic_cue`
        # takes it from - by attribute, not by position in the list.
        slot = next((sl for sl in self.slots if sl.index == self.CUE_SLOT_INDEX), None)
        label = ((slot.text_value if slot is not None else "") or "").strip()
        minut = int(max(0.0, time.time() - float(posledna["ts"])) // 60)
        text = (tr("dnes.lastcue_now", label=label) if minut < 1
                else tr("dnes.lastcue", min=minut, label=label))
        if text != getattr(self, "_dnes_lastcue_text", ""):
            self._dnes_lastcue_text = text
            self._refresh_dnes_backdrop(force=False)

    def _silent_share_for_next_session(self):
        """Share of silent cues for the next session.

        The silent arm is the ONLY fixed point of the measurement - without
        it the result always comes out "it works", even if the app stayed
        silent, because heart rate also comes back down by itself. That is
        why zero is not taken as a value but as an oversight, and is
        overwritten.

        That is exactly what was happening: the tuning dialog was pre-filled
        from `cue_trigger.silent_share`, which is 0.0 before the first
        session. Whoever opened it and clicked Save without touching that
        field turned the silent arm off for the whole app run, and there
        was not a word about it anywhere.

        Whoever really wants to turn it off has the developer overlay for
        that and will see a warning there - but they have to do it
        knowingly.
        """
        podiel = getattr(self, "_dev_silent_share", None)
        try:
            podiel = float(podiel) if podiel is not None else None
        except (TypeError, ValueError):
            podiel = None
        if not podiel:                  # both None and 0.0
            # Only OWN sessions: imported ones (someone else's body) would
            # otherwise move the counter - importing 15 sessions would end the
            # phase in which the silent arm stays silent more often (1/4)
            # before your own body had been compared.
            podiel = trigger.silent_share_for(
                len(data_io.vlastne(self._history_sessions())))
        return podiel

    def _urci_stupen_hlasky(self):
        """CUE LADDER (0.2, `rebrik.py`): the rung for the session that is
        just opening. Called by `_open_hr_session`, only once the world is
        sealed.

        The top is set by the world (work = picture only, B3-worlds - the
        world is not computed again here, the sealed `_session_world` is
        used) and by the style the player chose (`cue_style`); the ladder
        only goes below it. Both the style and the rung hold for the whole
        session, just like the world.

        When the evaluation fails, the session goes with the picture only:
        better quieter than a voice that should have been muted.
        """
        self._cue_style_rel = rebrik.normalize_cue_style(
            getattr(self, "cue_style", None))
        svet = getattr(self, "_session_world", hr_stats.WORLD_DEFAULT)
        try:
            stav = rebrik.stupen(
                hr_stats.sessions_in_world(self._history_sessions(), svet),
                svet=svet, styl=self._cue_style_rel)
        except Exception:
            app_log.exception("rebrik hlasky: vyhodnotenie zlyhalo")
            stav = {"stupen": rebrik.OBRAZ, "dovod": None}
        self._cue_rung = stav["stupen"]
        app_log.info("rebrik hlasky: %s (styl %s, dovod %s)",
                     self._cue_rung, self._cue_style_rel, stav.get("dovod"))
        return stav

    # ---------- cue style (onboarding step 5, Settings -> Sound) ----------

    @staticmethod
    def _cue_style_label(styl):
        """'voice'/'sound'/'visual' -> style name in Settings (UI language)."""
        return tr(dict(CUE_STYLE_SETTINGS_LABELS)[rebrik.normalize_cue_style(styl)])

    def _cue_style_labels(self):
        return [tr(kluc) for _styl, kluc in CUE_STYLE_SETTINGS_LABELS]

    def _on_cue_style_label(self, label):
        """A choice in the "How I speak up" row (Settings -> Sound)."""
        styl = next((s for s, kluc in CUE_STYLE_SETTINGS_LABELS if tr(kluc) == label),
                    None)
        if styl is None:
            return
        self._nastav_styl_hlasky(styl)
        self.save_settings()
        # The style decides whether cue texts are sent for synthesis
        # (`_hlasky_hovoria`) - the voice is prepared right away when the
        # player turns it on.
        self.schedule_pregenerate(200)

    def _prevezmi_styl_z_onboardingu(self, wizard):
        """The style from onboarding step 5. None = the player chose nothing and
        keeps what they had (a new player gets voice - the same as the
        answer "Not sure")."""
        styl = getattr(wizard, "cue_style", None)
        if styl is not None:
            self._nastav_styl_hlasky(styl)

    def _nastav_styl_hlasky(self, styl):
        """The player chose a cue style (onboarding or Settings -> Sound).

        The new style is the top of the ladder from the next session on
        (`_urci_stupen_hlasky`). A QUIETER style also applies RIGHT AWAY,
        in the running session too: the sentence at the choice promises
        "never louder than what you choose here", and a voice that kept
        playing for the rest of the evening after the player chose picture
        only would break that. A louder style waits for the next session -
        the rung is not recomputed mid-session (like the world), and being
        quieter than the player allowed is permitted.
        The session writes into its summary the style and the rung it
        really finished with.
        """
        styl = rebrik.normalize_cue_style(styl)
        self.cue_style = styl
        app_log.info("styl hlasky: %s", styl)
        # The sentence under the preview in Settings -> Sound follows the style
        # RIGHT AWAY - a louder one too, because the preview plays the style,
        # not the rung of the running session.
        veta = getattr(self, "preview_sub_label", None)
        if veta is not None:
            try:
                veta.configure(text=self._preview_sub_text())
            except Exception:
                app_log.exception("ukazka: vetu sa nepodarilo prepisat")
        if not rebrik.je_tichsi(styl, getattr(self, "_cue_style_rel", None)):
            return
        self._cue_style_rel = styl
        svet = getattr(self, "_session_world", hr_stats.WORLD_DEFAULT)
        if (rebrik.vrchol(svet, styl) == rebrik.OBRAZ
                and getattr(self, "_cue_rung", rebrik.HLAS) == rebrik.HLAS):
            # Picture only: the state machine no longer announces a voice
            # (`hlas` in the event tells the truth) and `_fire_somatic_cue`
            # plays nothing below the voice rung.
            self._cue_rung = rebrik.OBRAZ
            automat = getattr(self, "cue_trigger", None)
            if automat is not None:
                automat.voice = False
