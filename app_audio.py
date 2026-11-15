"""Sound and voices - part of the main app (DandurfApp from app.py).

AudioMixin is a DandurfApp mixin: app.py inherits it and the whole state
(TTS engine, voices, rate, volume, Edge cue cache, slots, player) lives on
DandurfApp. Only the methods that work with it through `self` are here - the
mixin has no __init__ and no attributes of its own.

Five sections moved from app.py unchanged:
  * SFX library - preparing the built-in sounds and the progress bar,
  * volume (master + SFX/voice balance) - effective SFX and voice volume;
    the section also carries `_apply_diagnostics` (which slots to switch on
    based on the onboarding diagnostics), which was already in it in app.py,
  * voices - SAPI / Edge voice lists, choosing the engine, voice and rate,
  * Edge cue pregeneration - preparing cues into the cache ahead of time
    (only those the natural voice will really say in game; while listening
    it is postponed until after the game),
  * SFX file decision - which sound a slot plays, and playing the slot
    itself (`_emit`, `_speak_text`, the player's own voice recording).
Since 0.3 also "Update voice" (`aktualizuj_hlas`) - a newer edge-tts from
PyPI on click; the core is in `hlas_kniznica.py`.

Watch out in tests: `pregenerate`, `_prune_cache`, `_play_concurrent`,
`_play_voice_file`, `_speak_text` and `aktualizuj_hlas` read `threading` from
this module - replacing the whole `threading` module on the app module does
not reach them (you need `app_audio.threading`). Changing an attribute of a
shared module (`app.threading.Thread`, `audio_engine.EDGE_AVAILABLE`) applies
here too.
"""

import os
import re
import threading
import webbrowser

import customtkinter as ctk

import audio_engine
import hlas_kniznica
import rebrik
import sfx_assets
import theme as theme_mod
import ui_kit
from app_spolocne import app_log
from audio_engine import EdgeTTSCache, speak_sapi_isolated
from i18n import tr
from paths import APP_NAME
from settings_model import (DEFAULT_EDGE_VOICE, ENGINE_EDGE, ENGINE_SAPI,
                            MODE_COMBO, MODE_SFX, MODE_TTS,
                            engine_labels, je_kategoria, label_to_engine)


def _posledna_chyba_edge(cache):
    """(kind, exception) of the last failed `ensure` in this thread, or
    None. Cache dummies in tests have no `posledna_chyba`."""
    zisti = getattr(cache, "posledna_chyba", None)
    if not callable(zisti):
        return None
    try:
        return zisti()
    except Exception:
        return None


def hlavna_chyba_edge(chyby):
    """Picks the error of one preparation that the player is told about.

    A rejection by Microsoft takes precedence (the advice is different: try
    later / switch to Windows, and if it lasts, a new Zanshin version -
    Microsoft rejects the old edge-tts), then a network outage, then the
    rest. Without a single known error `(EDGE_CHYBA_INA, None)` - a general
    sentence, not "internet"."""
    druhy = [c for c in (chyby or ()) if c]
    for druh in (audio_engine.EDGE_CHYBA_ODMIETNUTE, audio_engine.EDGE_CHYBA_OFFLINE):
        for chyba in druhy:
            if chyba[0] == druh:
                return chyba
    return druhy[0] if druhy else (audio_engine.EDGE_CHYBA_INA, None)


# The drive letter must not follow a letter/digit: otherwise "s:/" from
# "wss://speech..." (Microsoft rejection, aiohttp) would turn the service URL
# into "wsv1?..." - in the journal and in app.log. "C:\", "\\?\C:\" and
# "file:///C:/" are trimmed as before.
_CESTA_V_CHYBE = re.compile(r"(?:(?<![A-Za-z0-9])[A-Za-z]:|\\\\)[\\/][^'\"\n]*")


def _kratka_chyba(exc):
    """Error for a sentence in the journal - the class name if there is no
    text; at most 120 characters and no full paths (%APPDATA% contains the
    account name, PRIVACY.md)."""
    if exc is None:
        return "?"
    text = str(exc).strip() or type(exc).__name__
    text = _CESTA_V_CHYBE.sub(
        lambda z: os.path.basename(z.group(0).rstrip("\\/")) or "…", text)
    return text if len(text) <= 120 else text[:119] + "…"


def _verzia_edge_tts():
    """Version of the edge-tts CURRENTLY IN USE for app.log ("?" when it cannot
    be determined). An old version is the most common cause of a permanent
    rejection: since November 2026 Microsoft rejects older edge-tts (HTTP
    403, the minimum is in requirements.txt).

    After "Update voice" the downloaded library runs (`audio_engine.EDGE_
    STIAHNUTY`) and `importlib.metadata` would report the bundled one -
    the downloaded package has no dist-info. Otherwise the bundled one is
    the one in use."""
    verzia = getattr(audio_engine, "EDGE_VERZIA", None)
    if verzia and getattr(audio_engine, "EDGE_STIAHNUTY", False):
        return "%s (stiahnuta)" % verzia
    try:
        from importlib import metadata
        return metadata.version("edge-tts")
    except Exception:
        return "?"


def _prepni_balenie(widget, ukaz, **pack_kw):
    """Packs (`pack(**pack_kw)`) or hides the widget - only when something
    changes. Never raises: the page may be rebuilding right now."""
    if widget is None:
        return
    try:
        zabaleny = bool(widget.winfo_manager())
        if ukaz and not zabaleny:
            widget.pack(**pack_kw)
        elif not ukaz and zabaleny:
            widget.pack_forget()
    except Exception:
        pass


# Result of "Update voice" (`hlas_kniznica.STAV_*`) -> (status key under
# Voice source, journal line key, success, link to the new release).
# The link to the official releases is shown only where nothing but a new
# Zanshin fixes the voice: Microsoft rejects even the newest edge-tts, or
# this Zanshin cannot use it.
# "busy" (another update is running right now) is not here - the button is
# disabled while it runs, so it could only come from an outside call; it gets
# the general sentence.
# "cancelled" has its own branch (`_aktualizacia_hlasu_hotova`).
_VYSLEDKY_AKTUALIZACIE = {
    hlas_kniznica.STAV_AKTUALNY: (
        "edge.update.up_to_date", "log.edge_update.up_to_date", True, False),
    hlas_kniznica.STAV_AKTUALIZOVANY: (
        "edge.update.updated", "log.edge_update.updated", True, False),
    hlas_kniznica.STAV_STALE_ODMIETNUTY: (
        "edge.update.refused_still", "log.edge_update.refused_still", False, True),
    hlas_kniznica.STAV_OFFLINE: (
        "edge.update.offline", "log.edge_update.offline", False, False),
    hlas_kniznica.STAV_NEKOMPATIBILNY: (
        "edge.update.incompatible", "log.edge_update.incompatible", False, True),
    hlas_kniznica.STAV_OVERENIE_ZLYHALO: (
        "edge.update.verify_failed", "log.edge_update.verify_failed", False, False),
    hlas_kniznica.STAV_CHYBA: (
        "edge.update.error", "log.edge_update.error", False, False),
}


def stranka_zvuku():
    """Where "Try again" of the voice preparation is - the way the player
    really sees it: the Settings page, the Sound tab ("Settings → Sound",
    0.3 batch 4b). Before, `nav.zvuk` ("Sound / Audio") - that is only a
    Ctrl+K command palette item, no page is called that."""
    return f"{tr('nav.nastavenia')} → {tr('nav.nastavenia_tabs.zvuk')}"


class AudioMixin:
    """Sounds, voices, Edge cue preparation, slot playback (DandurfApp mixin)."""

    # ---------- SFX library ----------

    def _ensure_sfx_assets(self):
        def progress(done, total):
            self.ui_call(lambda: self._update_assets_progress(done, total))
        sfx_assets.ensure_assets(log=self.log_threadsafe, progress=progress)

    def show_assets_progress(self):
        """A small unobtrusive strip at the top of the window - only when SFX
        files are really missing (e.g. after %APPDATA% was cleaned out)."""
        if self._assets_progress_frame is not None:
            return
        pal = self.pal
        frame = ctk.CTkFrame(self.main, fg_color=pal["surface_alt"], corner_radius=10)
        frame.pack(fill="x", padx=20, pady=(0, 8), before=self.main_grid)
        ctk.CTkLabel(frame, text=tr("assets.preparing"), text_color=pal["text"],
                    font=("Segoe UI", 11)).pack(side="left", padx=14, pady=10)
        bar = ctk.CTkProgressBar(frame, width=160, progress_color=pal["accent"])
        bar.set(0.0)
        bar.pack(side="right", padx=14, pady=10)
        self._assets_progress_frame = frame
        self._assets_progress_bar = bar

    def _update_assets_progress(self, done, total):
        if total <= 0:
            return
        if self._assets_progress_bar is not None:
            try:
                self._assets_progress_bar.set(done / total)
            except Exception:
                pass
        if done >= total and self._assets_progress_frame is not None:
            self.root.after(600, self._hide_assets_progress)

    def _hide_assets_progress(self):
        if self._assets_progress_frame is not None:
            try:
                self._assets_progress_frame.destroy()
            except Exception:
                pass
            self._assets_progress_frame = None
            self._assets_progress_bar = None

    # ---------- volume (master + SFX/voice balance) ----------

    def _recompute_volumes(self):
        """Master volume + the "Sound ↔ voice mix" slider -> a separate
        effective volume for SFX and for the voice (TTS), both in the
        range 0-100.

        balance 50 = both at the full master volume; 0 = SFX only
        (voice muted), 100 = voice only (SFX muted)."""
        master = self.volume_value
        balance = self.balance_value
        sfx_mult = min(1.0, (100 - balance) / 50.0)
        tts_mult = min(1.0, balance / 50.0)
        self.sfx_volume = round(master * sfx_mult)
        self.tts_volume = round(master * tts_mult)

    def _apply_diagnostics(self, settings, diagnostics):
        """The gaming shadow diagnostics (Onboarding step 2) decides which
        of the 4 already prepared basic slots (data/keys/cues/sounds are
        always the same) are ON after onboarding. Checked symptom -> the
        matching slot stays enabled=True (default from DEFAULT_SLOT);
        unchecked -> the slot is switched off (enabled=False), but stays
        prepared in the list - the user can switch it on any time."""
        if not diagnostics:
            return
        try:
            slots = settings["profiles"][0]["slots"]
        except (KeyError, IndexError):
            return
        # diagnostics 0 = clenched hand/trembling when aiming -> slot 2
        # (Release), 1 = clenched teeth/jaw -> slot 1 (Jaw), 2 =
        # leaning forward/instability -> slot 0 (Grounded), 3 = holding
        # breath/panic -> slot 3 (Breathe).
        mapping = {0: 2, 1: 1, 2: 0, 3: 3}
        for diag_index, slot_index in mapping.items():
            if slot_index < len(slots):
                slots[slot_index]["enabled"] = bool(diagnostics.get(diag_index, True))

    # ---------- voices ----------

    def on_voices_ready(self, items):
        self.ui_call(lambda: self._apply_sapi_voices(items))

    def _apply_sapi_voices(self, items):
        self.voice_map = {name: vid for vid, name in items}
        if not self.saved_voice_id and items:
            self.saved_voice_id = items[0][0]
        if self.saved_voice_id:
            self.worker.set_voice(self.saved_voice_id)
        if self.engine == ENGINE_SAPI:
            self.refresh_voice_box()
        self.refresh_slot_summaries()

    def _load_edge_voices(self, pregen=True):
        """Fills the Edge voice picker from a fixed list - no network, so
        right on the Tk thread (before: a thread + catalogue download)."""
        self._apply_edge_voices(EdgeTTSCache.list_voices(), pregen=pregen)

    def _apply_edge_voices(self, items, pregen=True):
        self.edge_voice_map = {name: short for short, name in items}
        known = set(self.edge_voice_map.values())
        if self.edge_voice_id not in known:
            self.edge_voice_id = (DEFAULT_EDGE_VOICE if DEFAULT_EDGE_VOICE in known
                                  else (items[0][0] if items else DEFAULT_EDGE_VOICE))
        if self.engine == ENGINE_EDGE:
            self.refresh_voice_box()
            if pregen:
                self.pregenerate()
        self.refresh_slot_summaries()

    def current_voice_map(self):
        return (self.edge_voice_map if self.engine == ENGINE_EDGE
                else self.voice_map)

    def current_voice_names(self):
        return list(self.current_voice_map().keys())

    def voice_id_for_label(self, label):
        return self.current_voice_map().get(label, "")

    def slot_voice_label(self, slot):
        vid = slot.voice_edge if self.engine == ENGINE_EDGE else slot.voice_sapi
        if not vid:
            return ""
        for label, candidate in self.current_voice_map().items():
            if candidate == vid:
                return label
        return vid

    def set_slot_voice(self, slot, voice_id):
        if self.engine == ENGINE_EDGE:
            slot.voice_edge = voice_id
        else:
            slot.voice_sapi = voice_id

    def refresh_slot_summaries(self):
        for slot in self.slots:
            slot.refresh_summary()

    def refresh_voice_box(self):
        mapping = self.current_voice_map()
        current = (self.edge_voice_id if self.engine == ENGINE_EDGE
                   else self.saved_voice_id)
        names = list(mapping.keys())
        # New voices = new width (0.3 batch 4b): the dropdown is built with
        # "Nacitavam..." (Loading...) and a long Windows voice name got cut off
        # in it.
        ui_kit.nastav_hodnoty_menu(self.voice_box, names or [tr("voice.none")])
        label = next((n for n, vid in mapping.items() if vid == current), None)
        if label is None and names:
            label = names[0]
        if label:
            self.voice_var.set(label)
            if self.engine == ENGINE_EDGE:
                self.edge_voice_id = mapping[label]
            else:
                self.saved_voice_id = mapping[label]
                self.worker.set_voice(self.saved_voice_id)
        elif not names:
            self.voice_var.set(tr("voice.loading"))
        # "Update voice" belongs to the natural voice: this method is called
        # after every engine change (the switch, "Try again" for a missing
        # edge-tts via `_apply_edge_voices`, a new introduction), so the row
        # with the button is shown or hidden exactly then.
        self._obnov_aktualizaciu_hlasu()

    def on_engine_change(self):
        engine = label_to_engine().get(self.engine_var.get(), ENGINE_SAPI)
        if engine == ENGINE_EDGE and not audio_engine.EDGE_AVAILABLE:
            self.engine_pref = ENGINE_EDGE
            self.engine_var.set(engine_labels()[ENGINE_SAPI])
            self.save_settings()
            self.refresh_edge_banner()
            # the app's window, not the system one (0.3, batch 4)
            ui_kit.notify(getattr(self, "root", None), getattr(self, "pal", None),
                          APP_NAME, tr("msgbox.edge_missing_body"), kind="warning")
            return
        if engine == self.engine:
            return
        self.engine = self.engine_pref = engine
        self.refresh_edge_banner()
        self.refresh_voice_box()
        self.refresh_slot_summaries()
        self.save_settings()
        self.log(tr("log.engine_switched", engine=engine_labels()[engine]))
        if engine == ENGINE_EDGE:
            # Safety net: the Edge voice picker is filled at start (no
            # network); should it be empty, it is filled now - otherwise
            # the combobox would be empty.
            if not getattr(self, "edge_voice_map", None):
                self._load_edge_voices(pregen=False)
            self.pregenerate()
        else:
            # Whoever switched to the Windows voice wants nothing sent to
            # Microsoft - not even the rest of a preparation running right now.
            # Until now it ran to the end.
            self._zrus_rozbehnutu_pripravu()
            self.set_edge_status("")

    def on_voice_change(self):
        label = self.voice_var.get()
        vid = self.current_voice_map().get(label)
        if not vid:
            return
        if self.engine == ENGINE_EDGE:
            self.edge_voice_id = vid
            self.save_settings()
            self.pregenerate()
        else:
            self.saved_voice_id = vid
            self.worker.set_voice(vid)
            self.save_settings()

    def on_rate_change(self):
        self.rate_value = int(self.rate_var.get())
        self.audio.rate = self.rate_value
        self.worker.set_rate(self.rate_value)
        label = getattr(self, "rate_value_label", None)
        if label is not None:
            try:
                label.configure(text=self._rate_label_text())
            except Exception:
                pass
        self.save_settings()
        if self.engine == ENGINE_EDGE:
            self.schedule_pregenerate()

    # ---------- Edge cue pregeneration ----------

    def set_edge_status(self, text, color=None):
        # "Try again" belongs only to a failed preparation - every other state
        # (even an empty one) hides it; `_edge_priprava_zlyhala` shows it only
        # after this. Likewise the link to a new Zanshin release - it belongs
        # only to an "Update voice" result, which shows it only after this.
        self._ukaz_skusit_hlas_znova(False)
        _prepni_balenie(getattr(self, "edge_releases_btn", None), False)
        if self.edge_status_label is not None:
            try:
                self.edge_status_label.configure(text=text,
                                                 text_color=color or self.pal["text_dim"])
                # The label sits in the "Voice source" row (0.3 batch 4b) and
                # is visible only when it says something - empty, it would be
                # just a blank row.
                zabaleny = bool(self.edge_status_label.winfo_manager())
                if text and not zabaleny:
                    # The status goes ABOVE the "Update voice" row, not under
                    # it - the sentence talks about buttons "below".
                    rad = getattr(self, "edge_update_row", None)
                    if rad is not None and rad.winfo_manager():
                        self.edge_status_label.pack(fill="x", pady=(6, 0), before=rad)
                    else:
                        self.edge_status_label.pack(fill="x", pady=(6, 0))
                elif not text and zabaleny:
                    self.edge_status_label.pack_forget()
            except Exception:
                pass

    def _hlasky_hovoria(self):
        """Does a cue in game say anything with the voice (TTS) at all? Only in
        the "hlas" style and outside the Work world - there it goes only as a
        picture (`rebrik.vrchol`). The "zvuk" style plays the slot sound
        without words and "obraz" only a picture.

        DURING AN OPEN SESSION THE SESSION'S WORLD applies (`_session_world`,
        0.3), not the one currently shown: switching Play <-> Work in the
        middle of watching changes only the view (history, appearance), not
        the session and its cues - the same rule as the voice in
        `_open_hr_session` and the sounds in `resolve_sfx_path`. The new
        world applies from the next session."""
        styl = rebrik.normalize_cue_style(getattr(self, "cue_style", None))
        svet = getattr(self, "world", None)
        if getattr(self, "_hr_session_open", False):
            svet = getattr(self, "_session_world", svet)
        return (styl == rebrik.STYL_HLAS
                and rebrik.vrchol(svet, styl) == rebrik.HLAS)

    def _slot_na_pripravu(self, slot):
        """Can the natural voice really say the text of this cue in game?

        Only then may it be sent to Microsoft for preparation. Until now the
        texts of all slots with a voice were sent, even those Edge never says:
          * of a switched-off cue - `_dalsi_cue_slot` skips it in game,
          * of a cue with its in-game picture switched off - `_dalsi_cue_slot`
            skips it too (the same condition, `_ma_obrazok_v_hre`); its
            text went to Microsoft even though it never says it in game,
          * of a cue with its own recording - `_speak_text` plays the
            recording, not TTS (the same condition as there,
            `_slot_voice_clip`),
          * of an extra slot from 0.1 (index 4+, "+ Pridat spustac" (+ Add
            trigger)) - it has no category or picture and the app does not
            fire it by itself (`settings_model.je_kategoria`).
        When the cue or its picture is switched on later, or its recording
        is deleted, that change starts the preparation again
        (`schedule_pregenerate`).
        """
        return bool(
            je_kategoria(slot.index)
            and slot.enabled_value
            and self._ma_obrazok_v_hre(slot)
            and slot.mode in (MODE_TTS, MODE_COMBO)
            and slot.text_value.strip()
            and not self._slot_voice_clip(slot))

    def pregen_jobs(self):
        """[(text, voice)] for the cues the natural voice says in game
        (`_slot_na_pripravu`) - respects each slot's voice.

        Empty when cues do not speak in game (`_hlasky_hovoria`): for a player
        who chose only a picture or a sound without words, or is in the Work
        world, the cue texts would otherwise be sent to Microsoft for nothing.
        """
        if not self._hlasky_hovoria():
            return []
        jobs = []
        for slot in self.slots:
            if not self._slot_na_pripravu(slot):
                continue
            voice = slot.voice_edge or self.edge_voice_id
            pair = (slot.text_value, voice)
            if pair not in jobs:
                jobs.append(pair)
        return jobs

    def _zrus_rozbehnutu_pripravu(self):
        """The rest of a running preparation will no longer go to the network.

        The preparation thread (`work` in `pregenerate`) checks its `seq`
        before each next cue and also right before sending (`abort` after
        getting the cache lock). A cue already in flight finishes - the next
        one does not start. The same as when listening is switched on.
        """
        self._pregen_seq += 1

    def schedule_pregenerate(self, delay_ms=700):
        # Every change that schedules a preparation (cue switched off, style
        # without words, the Work world, another text/voice/rate...) also
        # changes what may be sent. So the old preparation ends RIGHT AWAY, not
        # only after `delay_ms` - in that time it could start sending a cue
        # that will no longer be heard. After the delay the new preparation
        # finds out what is still missing (finished cues are in the cache and
        # do not go to the network).
        self._zrus_rozbehnutu_pripravu()
        if self.engine != ENGINE_EDGE:
            return
        if self._pregen_job is not None:
            try:
                self.root.after_cancel(self._pregen_job)
            except Exception:
                pass
        self._pregen_job = self.root.after(delay_ms, self.pregenerate)

    def pregenerate(self, force=False):
        self._pregen_job = None
        # Every call starts over - even when it turns out nothing is needed
        # (another engine, style without words, Work, all cues switched off).
        # Until now `seq` was raised only for a non-empty list, so a
        # preparation started earlier ran to the end, even though its cues
        # were no longer meant to be heard.
        self._zrus_rozbehnutu_pripravu()
        seq = self._pregen_seq
        if self.engine != ENGINE_EDGE or not audio_engine.EDGE_AVAILABLE:
            return
        if getattr(self, "_aktualizacia_hlasu_bezi", False):
            # While "Update voice" runs, the preparation waits: cues would go
            # to Microsoft through the library the update is replacing right
            # now, and the preparation status would overwrite the update
            # status. Only its result (`_aktualizacia_hlasu_hotova`) starts it,
            # once the voice update succeeded.
            self._pregen_po_aktualizacii = True
            # The status stays "updating the voice" - even if switching to
            # the Windows voice and back erased it in the meantime
            # (`on_engine_change` then calls exactly this); otherwise the
            # button would be disabled without a word.
            self.set_edge_status(tr("edge.update.running"), self.pal["warn"])
            return
        rate = self.rate_value
        jobs = self.pregen_jobs()
        if not jobs:
            # A session from Work, the player switched to Play meanwhile (0.3):
            # while it runs, its world applies and cues stay silent
            # (`_hlasky_hovoria`) - but the next session in Play will speak. It
            # is prepared after watching, with the same delay as a cue that was
            # missing in game.
            if (getattr(self, "listening", False)
                    and getattr(self, "_hr_session_open", False)
                    and getattr(self, "_session_world", None) != getattr(self, "world", None)):
                self._pregen_po_hre = True
            self.set_edge_status("")
            return

        if not force and all(self.edge_cache.has(t, v, rate) for t, v in jobs):
            self.set_edge_status(tr("edge.ready"), self.pal["success"])
            self._prune_cache(jobs, rate)
            return

        if getattr(self, "listening", False):
            # WHILE LISTENING NOTHING GOES TO MICROSOFT - not even to prepare.
            # Auto-profile switches to the game's profile when the game starts
            # (`_handle_game_found` -> `switch_profile` ->
            # `schedule_pregenerate`) and listening is switched on right after,
            # so the preparation would otherwise hit the network exactly while
            # the game is loading. The same goes for a manual profile switch or
            # a voice change mid-game. The preparation is postponed, and it is
            # started only by `stop_listening` (`_dopriprav_hlasky_po_hre`) -
            # the same mechanism as for a cue that was missing in game
            # (`_speak_text`). `_pregen_seq` above has already stopped any
            # running preparation.
            self._pregen_po_hre = True
            self.set_edge_status(tr("edge.after_game"), self.pal["text_dim"])
            return

        self.set_edge_status(tr("edge.generating"), self.pal["warn"])

        def work():
            ok = 0
            chyby = []          # (kind, exception) of failed cues (0.3)
            for text, voice in jobs:
                if seq != self._pregen_seq:
                    return
                if getattr(self, "listening", False):
                    # Listening was switched on mid-preparation: the next cue
                    # no longer goes to the network. `pregenerate` on the GUI
                    # thread decides about the rest - while listening it
                    # postpones it until after the game.
                    self.ui_call(self.pregenerate)
                    return
                # The check above is not enough: `ensure` may wait on the cache
                # lock while another (older) preparation thread finishes its
                # cue - and listening may be switched on meanwhile. So `abort`
                # checks again only once it has the lock, just before sending.
                if self.edge_cache.ensure(
                        text, voice, rate,
                        abort=lambda: (seq != self._pregen_seq
                                       or getattr(self, "listening", False))):
                    ok += 1
                else:
                    chyba = _posledna_chyba_edge(self.edge_cache)
                    if chyba is not None:
                        chyby.append(chyba)
            if seq != self._pregen_seq:
                return
            total = len(jobs)
            if ok < total and getattr(self, "listening", False):
                # The last cue gave up on the lock because listening was
                # switched on (or it failed and the game is already running) -
                # that is not a preparation error; `pregenerate` postpones the
                # rest until after the game.
                self.ui_call(self.pregenerate)
                return
            if ok == total:
                self._edge_chyba_v_denniku = None
                self.ui_call(lambda: self.set_edge_status(
                    tr("edge.ready"), self.pal["success"]))
                self.log_threadsafe(tr("log.edge_cache_ready", n=ok))
                self.ui_call(lambda: self._prune_cache(jobs, rate))
            else:
                druh, exc = hlavna_chyba_edge(chyby)
                self.ui_call(lambda: self._edge_priprava_zlyhala(druh, ok, total, exc))

        threading.Thread(target=work, daemon=True).start()

    # ---------- failed natural voice preparation (0.3) ----------

    def _edge_priprava_zlyhala(self, druh, ok, total, exc=None):
        """Some cues have no natural voice. The status under Voice source and
        one journal line SAY WHY (`audio_engine.druh_chyby_edge`) and how to
        try again - until now always "check your internet connection", even
        when Microsoft had only rejected the request. "Try again" is shown
        under the status.

        Even now nothing goes to the network while watching: both the button
        and Ctrl+K call `pregenerate`, which then postpones it until after
        the game (PRIVACY.md). The journal line goes once per error kind -
        until the preparation succeeds, further failed attempts do not fill
        the journal. Likewise one line goes to app.log once (the journal in
        the window is lost after a restart): the kind, a short error without
        paths (`_kratka_chyba`) and the edge-tts version - an old version is
        the most common cause of a rejection."""
        kluc_stavu = {audio_engine.EDGE_CHYBA_OFFLINE: "edge.partial",
                      audio_engine.EDGE_CHYBA_ODMIETNUTE: "edge.partial_refused"}
        # `danger_text`, not `danger`: the sentence is small text (ui 10) and
        # carries instructions - `danger` has only ~3,7:1 on `surface` (rule in
        # theme.py).
        self.set_edge_status(tr(kluc_stavu.get(druh, "edge.partial_other"),
                                ok=ok, total=total),
                             self.pal.get("danger_text", self.pal["danger"]))
        self._ukaz_skusit_hlas_znova(True)
        if getattr(self, "_edge_chyba_v_denniku", None) == druh:
            return
        self._edge_chyba_v_denniku = druh
        kratka = _kratka_chyba(exc)
        kluc_riadku = {audio_engine.EDGE_CHYBA_OFFLINE: "log.edge_failed_offline",
                       audio_engine.EDGE_CHYBA_ODMIETNUTE: "log.edge_failed_refused"}
        self.log(tr(kluc_riadku.get(druh, "log.edge_failed_other"),
                    err=kratka, page=stranka_zvuku(),
                    retry=tr("common.retry"), cmd=tr("common.prepare_voices")))
        app_log.warning("prirodzeny hlas: priprava zlyhala (%s), hotovych %d/%d, "
                        "edge-tts %s: %s", druh, ok, total, _verzia_edge_tts(), kratka)

    def _ukaz_skusit_hlas_znova(self, ukaz):
        """The "Try again" button under the voice-prep status (Settings → Sound)."""
        tlacidlo = getattr(self, "edge_retry_btn", None)
        stav = getattr(self, "edge_status_label", None)
        if tlacidlo is None:
            return
        try:
            if ukaz and not tlacidlo.winfo_manager():
                rad = getattr(self, "edge_update_row", None)
                if stav is not None and stav.winfo_manager():
                    tlacidlo.pack(anchor="w", pady=(6, 0), after=stav)
                elif rad is not None and rad.winfo_manager():
                    # without a status at least above the "Update voice" row
                    tlacidlo.pack(anchor="w", pady=(6, 0), before=rad)
                else:
                    tlacidlo.pack(anchor="w", pady=(6, 0))
            elif not ukaz and tlacidlo.winfo_manager():
                tlacidlo.pack_forget()
        except Exception:
            pass            # the page is being rebuilt right now

    def skus_hlas_znova(self):
        """Click on "Try again": the same preparation as Ctrl+K -> "Prepare
        the cue voice". While watching nothing goes to the network -
        `pregenerate` postpones it until after the game and says so in the
        status."""
        self._ukaz_skusit_hlas_znova(False)
        self.pregenerate(force=True)

    # ---------- "Update voice" on click (0.3) ----------
    #
    # In November 2026 Microsoft rejected edge-tts 7.2.8, and the fix was a
    # change to the library's CODE - a released Zanshin cannot be fixed with
    # data. The author's decision (15. 11. 2026): the player downloads a newer
    # edge-tts themselves until a new Zanshin comes out. Rules (PRIVACY.md,
    # SAFETY.md): only on click, never by itself (not at start, not on an
    # engine switch) and never while watching.
    # The network, verification, test word and module swap are all done by
    # `hlas_kniznica.aktualizuj` in a helper thread; here there is only the
    # button, the status and the journal.

    def _obnov_aktualizaciu_hlasu(self):
        """The "Update voice" row under Voice source: visible only with the
        natural voice (the Windows voice sends nothing, not even a test word),
        and while the update runs, the button is disabled."""
        rad = getattr(self, "edge_update_row", None)
        if rad is None:
            return
        _prepni_balenie(rad, getattr(self, "engine", None) == ENGINE_EDGE,
                        anchor="w", pady=(6, 0))
        tlacidlo = getattr(self, "edge_update_btn", None)
        if tlacidlo is not None:
            bezi = getattr(self, "_aktualizacia_hlasu_bezi", False)
            try:
                tlacidlo.configure(state="disabled" if bezi else "normal")
            except Exception:
                pass

    def _ukaz_vydania_zanshinu(self, ukaz):
        """Link to the official releases next to "Update voice" - only with a
        result that only a new Zanshin fixes (`_VYSLEDKY_AKTUALIZACIE`).
        Every other status hides it (`set_edge_status`)."""
        _prepni_balenie(getattr(self, "edge_releases_btn", None), ukaz,
                        side="left", padx=(8, 0))

    def otvor_vydania_zanshinu(self):
        """Click on the link: the official Zanshin releases page in the default
        browser - the same mechanism as the links in About and in the
        Guide (`webbrowser.open`). The app itself downloads nothing."""
        try:
            webbrowser.open(hlas_kniznica.RELEASES_URL)
        except Exception:
            app_log.debug("stranku vydani sa nepodarilo otvorit", exc_info=True)

    def aktualizuj_hlas(self):
        """Click on "Update voice" (Settings → Sound or Ctrl+K).

        While watching, it does NOT go to the network even on click - the
        status says it will go after watching (like `edge.after_game`), and
        nothing is postponed: the update never runs by itself. Otherwise it
        disables the button, stops a running preparation (the next cue would
        go through the library that is being changed right now) and starts
        `hlas_kniznica.aktualizuj` in a helper thread. The result goes to the
        GUI thread via `ui_call` - the thread does not touch Tk.

        `abort` is checked before every step that goes to the network:
        watching was switched on or the player switched to the Windows voice
        -> "cancelled"."""
        if getattr(self, "_aktualizacia_hlasu_bezi", False):
            return              # the button is disabled; safety net for Ctrl+K
        if getattr(self, "engine", None) != ENGINE_EDGE:
            return              # the Windows voice sends nothing
        if getattr(self, "listening", False):
            self.set_edge_status(tr("edge.update.after_watching"), self.pal["text_dim"])
            return
        self._aktualizacia_hlasu_bezi = True
        self._pregen_po_aktualizacii = False
        self._zrus_rozbehnutu_pripravu()
        self._obnov_aktualizaciu_hlasu()
        self.set_edge_status(tr("edge.update.running"), self.pal["warn"])
        cache = self.edge_cache

        def zrus():
            return (getattr(self, "listening", False)
                    or getattr(self, "engine", None) != ENGINE_EDGE)

        def work():
            try:
                vysledok = hlas_kniznica.aktualizuj(cache=cache, abort=zrus)
            except Exception as exc:    # `aktualizuj` does not raise - safety net,
                # so the button does not stay disabled forever
                vysledok = hlas_kniznica.Vysledok(
                    hlas_kniznica.STAV_CHYBA, dovod=type(exc).__name__)
            self.ui_call(lambda: self._aktualizacia_hlasu_hotova(vysledok))

        threading.Thread(target=work, daemon=True).start()

    def _aktualizacia_hlasu_hotova(self, vysledok):
        """Result of "Update voice" on the GUI thread: the status under Voice
        source, one short journal line and, on success, preparing the cues
        that lack the voice. The technical reason (`vysledok.dovod`) has
        already been written by the core to app.log - the player only gets
        the i18n sentences by status."""
        self._aktualizacia_hlasu_bezi = False
        po_zmene = getattr(self, "_pregen_po_aktualizacii", False)
        self._pregen_po_aktualizacii = False
        self._obnov_aktualizaciu_hlasu()
        stav = getattr(vysledok, "stav", hlas_kniznica.STAV_CHYBA)
        # The Windows voice has no status under Voice source
        # (`on_engine_change` erases it and `pregenerate` says nothing with
        # it). The player could switch in the middle of an update - a result
        # that arrives after that goes only to the journal, otherwise a
        # sentence about the natural voice would hang under the Windows voice.
        prirodzeny = getattr(self, "engine", None) == ENGINE_EDGE
        if stav == hlas_kniznica.STAV_ZRUSENY:
            # Watching started (or the Windows voice was chosen) - nothing
            # changed. The "only after watching" sentence is shown only when
            # watching is really on (the player could have switched to the
            # Windows voice and back in the meantime).
            if prirodzeny and getattr(self, "listening", False):
                self.set_edge_status(tr("edge.update.after_watching"),
                                     self.pal["text_dim"])
            else:
                self.set_edge_status("")
            self.log(tr("log.edge_update.cancelled"))
            self._priprava_po_neuspechu(po_zmene, hned=True)
            return
        kluc_stavu, kluc_riadku, ok, odkaz = _VYSLEDKY_AKTUALIZACIE.get(
            stav, _VYSLEDKY_AKTUALIZACIE[hlas_kniznica.STAV_CHYBA])
        if stav == hlas_kniznica.STAV_AKTUALIZOVANY:
            verzia = vysledok.nova
        elif stav == hlas_kniznica.STAV_AKTUALNY:
            verzia = vysledok.aktivna or vysledok.najnovsia
        else:
            verzia = getattr(vysledok, "najnovsia", None) or getattr(vysledok, "aktivna", None)
        verzia = verzia or "?"
        # `danger_text`, not `danger`: small text with guidance (theme.py rule)
        farba = (self.pal["success"] if ok
                 else self.pal.get("danger_text", self.pal["danger"]))
        if prirodzeny:
            self.set_edge_status(tr(kluc_stavu, version=verzia), farba)
            if odkaz:
                self._ukaz_vydania_zanshinu(True)
        self.log(tr(kluc_riadku, version=verzia))
        if not ok:
            self._priprava_po_neuspechu(po_zmene)
            return
        # The natural voice may have just come back (EDGE_AVAILABLE) - the
        # banner about a missing edge-tts is recomputed. Cues without a voice
        # (rejected with the old library) are prepared right away
        # (`force=True`); when nothing is needed, the sentence about the
        # update stays in sight, not "voice ready".
        self.refresh_edge_banner()
        if po_zmene or self._chyba_hlas_pripomienkam():
            self.pregenerate(force=True)

    def _priprava_po_neuspechu(self, po_zmene, hned=False):
        """A preparation that `pregenerate` postponed while the update was
        running (`_pregen_po_aktualizacii`) must not get lost on failure.

        While watching, it is put off until after the game (`_pregen_po_hre`,
        the same postponement as in `pregenerate`) - no network and no
        status change.
        Typical case: auto-profile switches the profile when the game starts
        (`schedule_pregenerate`) and watching is switched on right away,
        which cancels the update; without this the new profile's cues would
        not be prepared even after the game.

        Outside watching it starts right away only on cancellation
        (`hned=True`) - then there is nothing to show. On another failure
        its sentence stays in sight (and the link to the new release); the
        next change or game starts the preparation."""
        if not po_zmene:
            return
        if getattr(self, "listening", False):
            self._pregen_po_hre = True
        elif hned:
            self.pregenerate()

    def _chyba_hlas_pripomienkam(self):
        """Is the natural voice missing in the cache for some cue that it says
        in game (`pregen_jobs`)? Only files on disk, no network."""
        if getattr(self, "engine", None) != ENGINE_EDGE:
            return False
        rate = self.rate_value
        try:
            return any(not self.edge_cache.has(t, v, rate) for t, v in self.pregen_jobs())
        except Exception:
            return True

    def _prune_cache(self, jobs, rate):
        keep = [self.edge_cache.path_for(t, v, rate) for t, v in jobs]
        threading.Thread(target=lambda: EdgeTTSCache.prune(keep),
                         daemon=True).start()

    # ---------- SFX file decision ----------

    def resolve_sfx_path(self, slot):
        key = slot.sfx_key
        if key == "__custom__":
            return slot.audio_path if slot.audio_path and os.path.exists(slot.audio_path) \
                else None
        if key and ":" in key:
            pack, sound_key = key.split(":", 1)
            return sfx_assets.sound_path(pack, sound_key)
        if not key and slot.audio_path:
            return slot.audio_path if os.path.exists(slot.audio_path) else None
        # The default set follows the appearance - but during a session it
        # follows the SESSION'S WORLD (B3-worlds): someone who only glances at
        # Work in the middle of a game should not hear the other world's
        # sounds from the next cue.
        pack = self.theme_key
        if getattr(self, "_hr_session_open", False):
            pack = theme_mod.WORLD_THEME.get(
                getattr(self, "_session_world", None), pack)
        default_key = sfx_assets.default_sound_for_slot_index(pack, slot.index)
        if not default_key:
            items = sfx_assets.library_items(pack)
            default_key = items[0][0] if items else None
        return sfx_assets.sound_path(pack, default_key) if default_key else None

    def _play_concurrent(self, path, volume):
        threading.Thread(target=self._play_now_safe, args=(path, volume), daemon=True).start()

    def _play_now_safe(self, path, volume):
        try:
            audio_engine.play_audio_file(path, volume)
        except Exception as exc:
            self.log_threadsafe(tr("log.sfx_playback_error", err=exc))

    def _play_voice_file(self, path):
        """Plays the OWN voice recording - at the TTS volume and without the
        notch filter (2-4 kHz), so that it sounds whole and intelligible,
        like one's own voice. Always in its own thread (concurrent), the
        same as SFX in a combination."""
        threading.Thread(target=self._voice_now_safe, args=(path,), daemon=True).start()

    def _voice_now_safe(self, path):
        try:
            audio_engine.play_audio_file(path, self.tts_volume, notch=False)
        except Exception as exc:
            self.log_threadsafe(tr("log.sfx_playback_error", err=exc))

    def _slot_voice_clip(self, slot):
        """Path to the slot's valid own voice recording, or None."""
        vp = getattr(slot, "voice_path", "")
        return vp if vp and os.path.exists(vp) else None

    def _slot_has_voice(self, slot):
        """Does the slot have something to say by voice? Either typed
        text, or a recording. Thanks to this the recording plays even
        when the text field is empty."""
        return bool(slot.text_value.strip() or self._slot_voice_clip(slot))

    def _speak_text(self, text, slot, concurrent=False):
        # The own voice recording takes precedence over TTS: if someone
        # recorded their own voice, that plays - not a machine reading of the
        # text.
        clip = self._slot_voice_clip(slot)
        if clip:
            self._play_voice_file(clip)
            return
        if self.engine == ENGINE_EDGE and audio_engine.EDGE_AVAILABLE:
            voice = slot.voice_edge or self.edge_voice_id
            if self.edge_cache.has(text, voice, self.rate_value):
                path = self.edge_cache.path_for(text, voice, self.rate_value)
                if concurrent:
                    self._play_concurrent(path, self.tts_volume)
                else:
                    self.audio.play_tts(path)
                return
            if not self._hlasky_hovoria() or not self._slot_na_pripravu(slot):
                # Style without words / the Work world, or a cue Edge does not
                # say in game (switched off, with its in-game picture switched
                # off, extra slot from 0.1): nothing is prepared for it
                # (`pregen_jobs`) - Test/preview plays through SAPI and the
                # journal does not promise a preparation that will not come.
                pass
            elif getattr(self, "listening", False):
                # During a game nothing goes to Microsoft: the cue plays in the
                # Windows voice and is prepared after `stop_listening`.
                self._pregen_po_hre = True
                self.log_threadsafe(tr("log.edge_not_cached_later"))
            else:
                self.log_threadsafe(tr("log.edge_not_cached"))
                self.ui_call(self.pregenerate)

        voice_id = slot.voice_sapi or self.saved_voice_id
        if concurrent:
            threading.Thread(target=speak_sapi_isolated,
                             args=(text, voice_id, self.rate_value, self.tts_volume),
                             daemon=True).start()
        else:
            self.audio.speak(text, voice_id)

    def _slot_zaznie(self, slot, bez_slov=False):
        """Will `_emit(slot, bez_slov)` play anything at all? The same branches
        as `_emit`, just without playback - for `audible` in the cue record
        (the effectiveness chart counts only cues that were really heard)."""
        mode = slot.mode
        sfx_path = self.resolve_sfx_path(slot) if mode in (MODE_SFX, MODE_COMBO) else None
        zvuk = bool(sfx_path and os.path.exists(sfx_path))
        if bez_slov or mode == MODE_SFX:
            # In SFX mode `_emit` has no text (`text` is only for TTS/COMBO),
            # so without a file nothing plays.
            return zvuk
        if mode == MODE_COMBO:
            return zvuk or self._slot_has_voice(slot)
        return self._slot_has_voice(slot)

    def _emit(self, slot, bez_slov=False):
        """Plays the slot. `bez_slov=True` (cue style "zvuk", `rebrik.py`)
        plays ONLY the slot sound - no TTS, no own recording, not even as
        a fallback for a missing sound. A slot without a sound then stays
        silent."""
        mode = slot.mode
        sfx_path = self.resolve_sfx_path(slot) if mode in (MODE_SFX, MODE_COMBO) else None
        text = slot.text_value if mode in (MODE_TTS, MODE_COMBO) else ""

        if bez_slov:
            if sfx_path and os.path.exists(sfx_path):
                self.audio.play(sfx_path)
            elif sfx_path:
                self.log_threadsafe(tr("log.slot_sfx_missing_plain", n=slot.index + 1))
            return

        if mode == MODE_COMBO:
            played_sfx = False
            if sfx_path and os.path.exists(sfx_path):
                self._play_concurrent(sfx_path, self.sfx_volume)
                played_sfx = True
            elif sfx_path:
                self.log_threadsafe(tr("log.slot_sfx_missing", n=slot.index + 1,
                                       name=os.path.basename(sfx_path)))
            if self._slot_has_voice(slot):
                # A combination always plays concurrently (at once) - regardless
                # of the global "cez seba" (overlapping) switch, otherwise SFX+TTS
                # would sound one after the other. `_speak_text` decides by itself
                # whether to say the text (TTS) or play the own recording.
                self._speak_text(text, slot, concurrent=played_sfx)
            return

        if mode == MODE_SFX:
            if sfx_path and os.path.exists(sfx_path):
                self.audio.play(sfx_path)
                return
            if sfx_path:
                key = "log.slot_sfx_missing_fallback" if text.strip() \
                    else "log.slot_sfx_missing_plain"
                self.log_threadsafe(tr(key, n=slot.index + 1))
            if text.strip():
                self._speak_text(text, slot)
            return

        if self._slot_has_voice(slot):
            self._speak_text(text, slot)
