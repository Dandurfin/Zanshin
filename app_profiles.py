"""Slots, game profiles and auto-profile - part of the main app
(DandurfApp from app.py).

ProfilesMixin is a mixin of DandurfApp: app.py inherits it and all the state
(the active profile's slots, the profile list and the profile switcher, the
auto-profile and reading running processes) lives on DandurfApp. Here are
only the methods that work with it through `self` - the mixin has no
__init__ and no attributes of its own.

Moved from app.py unchanged:
  * slots - rebuilding the slot cards of the active profile,
  * game profiles - switching, creating and deleting a profile,
  * Auto-Profile Engine (recognising a running game) - the first part of
    the section: game found and game ended, reading process names
    (`GameProcessWatcher`), the auto-profile switch and the "Stopped"
    status sentence that talks about it. The rest of that section (heart
    rate sensor and the measurement session) is in app_session.py.

WARNING for tests: `_start_game_watcher` reads `GameProcessWatcher` and
`PSUTIL_AVAILABLE` from this module - a fake watcher has to be injected here
(`app_profiles.GameProcessWatcher`), not on the app module.
"""

import ui_kit
from game_profiles import PSUTIL_AVAILABLE, GameProcessWatcher, known_games
from i18n import tr
from paths import APP_NAME
from settings_model import default_slots, normalize_slot
from ui_dialogs import NewProfileDialog, SlotCard


class ProfilesMixin:
    """Slots, game profiles and auto-profile (DandurfApp mixin)."""

    # ---------- slots ----------

    def rebuild_slots(self, data_list):
        """Rebuilds the active profile's slots, syncs the badge in the
        navigation and the bulk-selection bar (after the rebuild nothing is
        selected anymore)."""
        for child in self.slots_container.winfo_children():
            child.destroy()
        self.slots = [SlotCard(self, i, data) for i, data in enumerate(data_list)]
        self._on_slot_selection_change()
        self._refresh_nav_badges()

    def slot_dicts(self):
        return [s.to_dict() for s in self.slots]

    # ---------- game profiles ----------

    def _sync_active_profile_slots(self):
        profile = next((p for p in self.profiles if p["name"] == self.active_profile_name),
                       None)
        if profile is not None:
            profile["slots"] = self.slot_dicts()

    def refresh_profile_switch(self):
        names = [p["name"] for p in self.profiles]
        self.profile_switch.configure(values=names)
        self.profile_var.set(self.active_profile_name)

    def on_profile_switch(self, name):
        self.switch_profile(name)

    def switch_profile(self, name):
        if name == self.active_profile_name:
            return
        profile = next((p for p in self.profiles if p["name"] == name), None)
        if profile is None:
            return
        self._sync_active_profile_slots()
        self.active_profile_name = name
        self.rebuild_slots(profile["slots"])
        self.profile_var.set(name)
        self.save_settings()
        self.schedule_pregenerate(200)
        self.log(tr("log.profile_switched", name=name))

    def new_profile_dialog(self):
        NewProfileDialog(self)

    def create_profile(self, name):
        name = name.strip()
        if not name:
            return
        if any(p["name"] == name for p in self.profiles):
            # App window, not a system one (0.3 batch 4) - see `ui_kit.notify`.
            ui_kit.notify(getattr(self, "root", None), getattr(self, "pal", None),
                          APP_NAME, tr("profile.duplicate_name"))
            return
        self._sync_active_profile_slots()
        # A new profile gets ALL FOUR categories, same as a profile created
        # automatically for a game (`_handle_game_found`). Until now it had one
        # slot and the player "added" the rest with a button - that is gone, so
        # the profile would stay with Grounding only, forever.
        new_slots = [normalize_slot(s) for s in default_slots()]
        self.profiles.append({"name": name, "slots": new_slots})
        self.active_profile_name = name
        self.rebuild_slots(new_slots)
        self.refresh_profile_switch()
        # The new profile's words are in the app's language: in a language from
        # VOICE_HINTS (e.g. Japanese, German) a player with the default voice
        # gets a voice of that language (an English one would not pronounce
        # them). It is saved below and the cue preparation already uses the new
        # voice.
        if self._hlas_k_hlaskam(new_slots):
            self.refresh_voice_box()
        self.save_settings()
        # New profile = different active cues, same as switching profiles
        # (`switch_profile`): preparing the previous profile's cues stops
        # right away (they no longer belong to the active ones) and the enabled
        # cues of the new one get prepared.
        self.schedule_pregenerate(200)
        self.log(tr("log.profile_created", name=name))

    def delete_current_profile(self):
        okno = getattr(self, "root", None)
        pal = getattr(self, "pal", None)
        if len(self.profiles) <= 1:
            ui_kit.notify(okno, pal, APP_NAME, tr("profile.cannot_delete_last"))
            return
        # Confirmation in the app's window: the button carries a verb ("Delete
        # profile") and is destructive, focus and Enter are on "Cancel".
        if not ui_kit.confirm(okno, pal, APP_NAME,
                              tr("profile.confirm_delete", name=self.active_profile_name),
                              ok_label=tr("profile.delete_btn"),
                              cancel_label=tr("common.cancel"), danger=True):
            return
        self.profiles = [p for p in self.profiles if p["name"] != self.active_profile_name]
        new_active = self.profiles[0]
        self.active_profile_name = new_active["name"]
        self.rebuild_slots(new_active["slots"])
        self.refresh_profile_switch()
        self.save_settings()
        self.schedule_pregenerate(200)
        self.log(tr("log.profile_deleted"))

    # ---------- Auto-Profile Engine (recognising a running game) ----------

    def on_game_process_found(self, profile_name):
        self.ui_call(lambda: self._handle_game_found(profile_name))

    def on_game_process_gone(self):
        self.ui_call(self._handle_game_gone)

    def _handle_game_found(self, profile_name):
        if not self.auto_profile_enabled:
            return
        if not any(p["name"] == profile_name for p in self.profiles):
            self._sync_active_profile_slots()
            new_slots = [normalize_slot(s) for s in default_slots()]
            self.profiles.append({"name": profile_name, "slots": new_slots})
            self.refresh_profile_switch()
            # Like `create_profile`: a voice for the new profile's words. It is
            # saved, and the preparation scheduled, by `switch_profile` below.
            if self._hlas_k_hlaskam(new_slots):
                self.refresh_voice_box()
            self.log(tr("log.auto_profile_created", name=profile_name))
        if profile_name != self.active_profile_name:
            self.switch_profile(profile_name)
        self.log(tr("log.auto_profile_detected", name=profile_name))
        if not self.listening:
            self._auto_started_listening = True
            self.start_listening()

    def _handle_game_gone(self):
        if not self.auto_profile_enabled:
            return
        # "Odpocuvanie pozastavene" (Listening paused) is written ONLY when it
        # really stopped. Until now it was always written - even when the
        # player started listening themselves and it kept running (port and
        # measurement), so the journal claimed the opposite.
        if self.listening and self._auto_started_listening:
            self.stop_listening()
            self.log(tr("log.auto_profile_ended"))
        self._auto_started_listening = False

    @staticmethod
    def _zname_hry():
        """Games that the auto-profile knows, for sentences in the app. From the
        map (`game_profiles.GAME_PROCESS_MAP`), so that the sentence cannot
        promise a start for a game the app does not know."""
        return " / ".join(known_games())

    def _start_game_watcher(self):
        """Starts reading process names (auto-profile). A thread cannot be
        started twice, hence a new one on every switch-on."""
        if not PSUTIL_AVAILABLE or getattr(self, "game_watcher", None) is not None:
            return
        self.game_watcher = GameProcessWatcher(self.on_game_process_found,
                                               self.on_game_process_gone)
        self.game_watcher.start()

    def _stop_game_watcher(self):
        """Stops reading processes - a disabled auto-profile reads nothing."""
        watcher, self.game_watcher = getattr(self, "game_watcher", None), None
        if watcher is not None:
            watcher.stop()

    def _kamae_zastavene(self):
        """Pair of texts for the "Stopped" state.

        The app can start by itself when it finds a running game - but only
        with automatic profile switching on (`_handle_game_found`), and
        that can be switched off. So the sentence asks about the real state
        instead of promising something that will not come with switching
        off.
        """
        kluc = ("kamae.stopped_sub_auto" if self.auto_profile_enabled
                else "kamae.stopped_sub")
        return tr("kamae.stopped"), tr(kluc, games=self._zname_hry())

    def on_auto_profile_toggle(self):
        self.auto_profile_enabled = bool(self.auto_profile_var.get())
        if self.auto_profile_enabled:
            self._start_game_watcher()
        else:
            # Off = process names are not read at all. Listening that a
            # game started keeps running - from now on the player controls
            # it, not the detection.
            self._stop_game_watcher()
            self._auto_started_listening = False
        self.save_settings()
        # The sentence about the stopped app (`_kamae_zastavene`, centre of
        # Today) talks about this setting, so it has to be rewritten right
        # away - otherwise after switching off it would still promise a start
        # with a game. Since 0.3 (batch 4) it is carried by the centre of the
        # page, not the bar - the bar only has the button now.
        if not self.listening and getattr(self, "kamae", None) is not None:
            self._refresh_kamae_state_text()
        self.log(tr("log.auto_profile_on") if self.auto_profile_enabled
                else tr("log.auto_profile_off"))
