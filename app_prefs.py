"""Player's preferences - part of the main app (DandurfApp from app.py).

PrefsMixin is a mixin of DandurfApp: app.py inherits it and the whole state
(language, world, theme, palette, volume, profiles, widgets) lives on
DandurfApp. Here are only the methods that work with it through `self` - the
mixin has no __init__ and no attributes of its own.

Four sections moved from app.py unchanged:
  * language switching - rebuilding the window in the new language,
  * world switching (play / work) - the world, its look and switches
    (the constant ALGORITMUS_SVET stayed in DandurfApp - these methods do
    not read it, it is read by `_kriticky_popis` in app.py and
    `_open_hr_session` in app_session.py),
  * theme switching - recolouring the already built window,
  * settings - loading and saving dandurf_settings.json, volume,
    SFX/voice balance and the "Edge TTS missing" banner.

WARNING for tests: `load_settings` / `save_settings` read SETTINGS_PATH from
this module - the test must redirect it here (`app_prefs.SETTINGS_PATH`),
not in the app module.
"""

import json
import os
import shutil
import time
import tkinter as tk

import customtkinter as ctk

import audio_engine
import background
import hotkey
import hr_stats
import hud_paint
import rebrik
import theme as theme_mod
import theme_recolor
import ui_kit
import ui_shell
from guided_tour import GuidedTour
from heart_rate import ANY_INTERFACE, DEFAULT_PORT as HR_DEFAULT_PORT
from i18n import LANGUAGES, LANG_EN, LANG_SAME_AS_APP, LANG_SK, set_lang, system_lang, tr
from paths import APP_NAME, SETTINGS_PATH, nahrad_subor, resolve_audio_path
from settings_model import (DEFAULT_AUDIO, DEFAULT_BREATH_EXHALE_S,
                            DEFAULT_BREATH_INHALE_S, DEFAULT_DASHBOARD_STATS,
                            DEFAULT_EDGE_VOICE, DEFAULT_HIGH_HR_RING_BPM,
                            DEFAULT_MONITOR_TARGET,
                            ENGINE_EDGE, ENGINE_SAPI, clamp_int, default_hud_config,
                            default_overlay_configs, default_slots, doplnit_kategorie,
                            engine_labels, jazyk_hlasu, jazyky_hlasok,
                            migrate_profile_texts,
                            move_old_grounding_position, normalize_breath_seconds,
                            normalize_dashboard_stats, normalize_high_hr_ring_bpm,
                            normalize_hud_config,
                            normalize_monitor_target, normalize_overlay_config,
                            normalize_slot, suggested_voice)

from app_spolocne import (DEFAULT_SNOOZE_HOTKEY, LABEL_TO_LANG, LANG_NATIVE_LABELS,
                          SNOOZE_HOTKEY_MINUTES, app_log)

# Notice about the restored settings (`_oznam_obnovu_nastaveni`) only once
# the window is up.
OZNAM_OBNOVY_MS = 1200


def _citaj_nastavenia(cesta):
    """Contents of the settings file as a dict. Raises when it is not a dict -
    even a valid JSON list or number is a broken file for settings."""
    with open(cesta, "r", encoding="utf-8") as fh:
        obsah = json.load(fh)
    if not isinstance(obsah, dict):
        raise ValueError("nastavenia nie su JSON objekt")
    return obsah


def zaloha_nastaveni(cesta):
    """Copies the previous VALID settings file to `<cesta>.bak` (atomically).

    Only a valid one: if the file got broken in the meantime, backing it up
    would overwrite the only good copy. So the backup is always one write
    behind - that is the last state that could be loaded. Returns True when
    a backup was made.
    """
    try:
        with open(cesta, "rb") as fh:
            obsah = fh.read()
    except OSError:
        return False                      # does not exist yet (first start)
    try:
        if not isinstance(json.loads(obsah.decode("utf-8")), dict):
            return False
    except Exception:
        return False
    bak = cesta + ".bak"
    tmp = bak + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(obsah)
    # .bak may be held briefly by an antivirus or indexing (WinError 5 in the
    # log of a test copy) - `nahrad_subor` retries. If even that fails, the
    # error goes to the caller as before, just without a forgotten .bak.tmp
    # next to the settings.
    nahrad_subor(tmp, bak, uprac_zdroj=True)
    return True


def nacitaj_nastavenia(cesta, teraz=None):
    """Loads the settings. Returns (dict or None, obnova or None).

    File does not exist -> (None, None): first start, defaults. File cannot
    be read -> the broken one is MOVED ASIDE as
    `<cesta>.corrupt-RRRRmmdd-HHMMSS` (so it can be rescued and so the first
    `save_settings` does not overwrite it) and `.bak` is tried. `obnova` =
    {"odlozene": name of the moved-aside file (without the path - the path
    in %APPDATA% carries the account name), "zo_zalohy": bool}.
    """
    if not os.path.exists(cesta):
        return None, None
    try:
        return _citaj_nastavenia(cesta), None
    except Exception:
        app_log.exception("load_settings: %s sa neda precitat - odkladam ho "
                          "a skusam zalohu", cesta)
    znacka = time.strftime("%Y%m%d-%H%M%S",
                           time.localtime(time.time() if teraz is None else teraz))
    odlozene = "%s.corrupt-%s" % (cesta, znacka)
    try:
        # With retries here too: a short lock would otherwise end with just a
        # copy and the broken file would stay in place. The source is NOT
        # deleted on error.
        nahrad_subor(cesta, odlozene)
    except OSError:
        # Another app holds the file (editor, sync) - at least a copy.
        try:
            shutil.copy2(cesta, odlozene)
        except OSError:
            app_log.exception("load_settings: pokazeny subor sa nedal odlozit")
            odlozene = None
    loaded = None
    try:
        loaded = _citaj_nastavenia(cesta + ".bak")
    except FileNotFoundError:
        pass
    except Exception:
        app_log.exception("load_settings: ani zaloha %s.bak sa neda precitat", cesta)
    if loaded is not None:
        # Put the backup back in place right away. If the app crashed before
        # the first `save_settings` writes the file, the next start would not
        # find the file and would begin as a first start - even though a good
        # backup lies next to it.
        try:
            tmp = cesta + ".tmp"
            shutil.copyfile(cesta + ".bak", tmp)
            nahrad_subor(tmp, cesta, uprac_zdroj=True)
        except OSError:
            app_log.exception("load_settings: zalohu sa nepodarilo vratit na miesto")
    if odlozene is None:
        # Without a moved-aside copy the player has nothing to look for - the
        # notice would lie.
        return loaded, None
    return loaded, {"odlozene": os.path.basename(odlozene),
                    "zo_zalohy": loaded is not None}


class PrefsMixin:
    """Language, world, theme and settings (mixin of DandurfApp)."""

    # ---------- language switching ----------

    @staticmethod
    def _lang_switch_value(code):
        return LANG_NATIVE_LABELS.get(code, LANG_NATIVE_LABELS[LANG_SK])

    def on_lang_switch(self, label):
        code = LABEL_TO_LANG.get(label, LANG_SK)
        if code == self.lang:
            return
        self.lang = code
        set_lang(code)
        # The language's voice (`VOICE_HINTS`) only when the active profile's
        # cues really are in that language - switching does not translate them,
        # see `_hlas_k_hlaskam`.
        self._hlas_k_hlaskam(self.slot_dicts())
        self.save_settings()
        was_listening = self.listening
        # Changing the language changes TEXTS, so (unlike a theme change) the
        # whole window has to be rebuilt via `_build_ui` - 1300+ widgets that
        # would otherwise assemble piece by piece in front of the player
        # (flicker). We freeze drawing for the rebuild and redraw once at the
        # end.
        ui_kit.freeze_repaint(self.root, True)
        try:
            self._build_ui()
            self.refresh_edge_banner()
            if audio_engine.EDGE_AVAILABLE:
                # voice descriptions (female/male) are in the UI language
                self._load_edge_voices(pregen=False)
            self.refresh_voice_box()
            self.refresh_slot_summaries()
            self.refresh_hr_status_label()
            if was_listening:
                self._apply_listening_visuals()
            self._apply_overlay_labels()
            self._apply_hud_labels()
            self.log(tr("log.lang_switched", lang=tr(f"lang.{code}")))
            self._refresh_guide_panel_theme()
        finally:
            self.root.update_idletasks()
            ui_kit.freeze_repaint(self.root, False)
        # Edge TTS preparation is not UI - only after the window is unfrozen.
        if self.engine == ENGINE_EDGE:
            self.pregenerate()

    def _hlas_k_hlaskam(self, slots):
        """Default Edge voice -> app language voice if `slots` cues are in it.

        VOICE_HINTS is here for cues whose built-in words are not English
        (ja/zh/ru/bg, since 0.3 also es/de/fr/pt): an English voice would
        not pronounce them or would garble them. Until 0.2.1d the voice
        followed the INTERFACE language - but switching the language does
        not translate the texts of existing profiles (built-in words are
        taken when the profile is created, English for sk/cs). So after
        switching to Japanese a Japanese voice read the English "Grounded"
        and could garble it or stay silent - exactly what VOICE_HINTS was
        meant to prevent.

        Now the language of the TEXTS decides (`jazyky_hlasok`): the voice
        changes only when the speaking cues are built-in words of the app
        language - after switching the language (profile created in that
        language) and also for a new profile (its words are in the app
        language). Custom or mixed texts -> the voice stays. A voice other
        than the default is never changed (`suggested_voice`), not even
        back: the app does not know whether the player picked it.

        Returns True when the voice changed - the caller refreshes the voice
        selection and the cue preparation (`schedule_pregenerate` /
        `pregenerate`).
        """
        if self.lang not in jazyky_hlasok(slots):
            return False
        novy = suggested_voice(self.lang, self.edge_voice_id)
        if novy == self.edge_voice_id:
            return False
        self.edge_voice_id = novy
        app_log.info("hlas %s k hlaskam v jazyku %s", novy, self.lang)
        return True

    # ---------- world switching (play / work) ----------

    @staticmethod
    def _world_label(world):
        """'play'/'work' -> "Play"/"Work" in the UI language."""
        return tr("world.work") if world == "work" else tr("world.play")

    def _world_labels(self):
        return [self._world_label("play"), self._world_label("work")]

    def _on_world_label(self, label):
        """Click on the "Play | Work" segment (title bar and Settings)."""
        self.set_world("work" if label == self._world_label("work") else "play")

    def set_world(self, world):
        """Switches the world: look, history, insights. NOT THE RUNNING SESSION.

        The look goes via `on_theme_switch` - recolouring without rebuilding
        the window, including the HUD and the in-game visuals (it flickers a
        little in the corner of the eye, that is expected). The detail in
        History is an index into the world's session list, so it is reset.
        The other world's insights are thrown away and recomputed.

        An open session stays in the world it started in
        (`_session_world`), including whether it may have a voice - looking
        at work statistics in the middle of a game does not rewrite the game
        as work.
        """
        world = hr_stats.normalize_activity(world) or hr_stats.WORLD_DEFAULT
        if world == self.world:
            self._sync_world_switches()
            return
        self.world = world
        self.history_detail_index = None
        self._hr_insights = []
        self._hr_insights_at = None
        tema_pred = self.theme_key
        # `on_theme_switch` saves the settings itself - already with the new
        # world.
        self.on_theme_switch(tr(f"theme.{theme_mod.WORLD_THEME[world]}.label"))
        if self.theme_key == tema_pred:
            self.save_settings()
        self._sync_world_switches()
        # "In-game" is called "Screen" in the Work world (0.3 batch 4,
        # `app_today._sync_world_nazvy`; the test dummies do not have it).
        nazvy = getattr(self, "_sync_world_nazvy", None)
        if callable(nazvy):
            nazvy()
        app_log.info("svet prepnuty na %s", world)
        # Switching WHILE WATCHING (0.3): the session and its cues stay in
        # the world they started in (voice, sounds, `_hlasky_hovoria`) - so
        # each world's history stays clean. It is said once, so the player
        # does not expect Play to turn into Work midway.
        svet_relacie = getattr(self, "_session_world", None)
        if (getattr(self, "_hr_session_open", False)
                and svet_relacie in hr_stats.ACTIVITY_KINDS and svet_relacie != world):
            self.log(tr("log.world_switch_session",
                        world=self._world_label(svet_relacie),
                        new=self._world_label(world)))
        try:
            self._refresh_history_page()
        except Exception:
            app_log.exception("historia: prekreslenie po prepnuti sveta zlyhalo")
        self._refresh_dnes_stats()
        self.run_hr_analysis()
        # In Work a cue does not speak, so nothing is prepared for it
        # (`_hlasky_hovoria`); after returning to Play the rest get prepared.
        self.schedule_pregenerate(200)

    def _sync_world_switches(self):
        """Both world switches (title bar, Settings) show the current world.

        CTkSegmentedButton does not change its selected segment by itself
        when the world is switched by something other than a click on it."""
        label = self._world_label(self.world)
        lista = getattr(self, "titlebar", None)
        if lista is not None and hasattr(lista, "set_world"):
            lista.set_world(label)
        prepinac = getattr(self, "world_switch", None)
        if prepinac is not None:
            try:
                prepinac.set(label)
            except Exception:
                pass
            # CTk `set()` changes only the fill - the text of the selected
            # world (accent) has to be redrawn, also after the theme recolour.
            ui_kit.oznac_zvoleny_segment(prepinac, getattr(self, "pal", None) or {})

    # ---------- theme switching ----------

    def on_theme_switch(self, label):
        """Switches the theme by RECOLOURING the built window, not rebuilding it.

        Previously this called `_build_ui()`, which destroyed and rebuilt
        everything: measured 1374 widgets, 101 878 Tk calls and **2.97 s**
        of blocking, during which the window assembled piece by piece in
        front of the player (29 different intermediate states). There was
        no single slow spot - it is sheer volume, every CustomTkinter
        widget draws on its own canvas.

        Colours are the only thing that changes with the theme (texts
        stay), so it is enough to walk the tree and rewrite them - see
        `theme_recolor`.

        If the recolour failed for any reason, it falls back to the
        original rebuild: better slow and correct than fast and broken.

        Since 0.2 (B3-worlds) the theme belongs to the world - it is called
        via `set_world`, not directly; otherwise the look and the world
        would drift apart (on the next start the theme would follow the
        world anyway).
        """
        key = theme_mod.ZEN if label == tr("theme.zen.label") else theme_mod.MODERN
        if key == self.theme_key:
            return
        stara_pal = self.pal
        self.theme_key = key
        self.pal = theme_mod.tokens(key)
        self.overlay_manager.set_palette(self.pal)
        self.hud.set_style(self.overlay_manager.style)
        self._apply_hud_labels()
        self.save_settings()
        self.log(tr("log.theme_switched", theme=tr(f"theme.{key}.label")))
        was_listening = self.listening

        try:
            self._recolor_ui(stara_pal, self.pal)
        except Exception:
            app_log.exception("prefarbenie temy zlyhalo - stavam okno znova")
            self._build_ui()
            self.refresh_edge_banner()
            self.refresh_voice_box()
            self.refresh_slot_summaries()
            self.refresh_hr_status_label()

        if was_listening:
            self._apply_listening_visuals()
        self._refresh_guide_panel_theme()

    def _recolor_ui(self, stara_pal, nova_pal):
        """Recolours the whole window without destroying anything."""
        mapa = theme_recolor.build_color_map(stara_pal, nova_pal)
        ui_shell.set_theme_pal(nova_pal)
        self.root.configure(fg_color=nova_pal["bg"])
        # The HUD and the in-game visuals are separate Toplevel windows with
        # their own path for changing the theme (overlay_manager.set_palette /
        # hud.set_style above) - we keep them out of the tree recolour.
        theme_recolor.recolor_tree(self.root, mapa, skip=(tk.Toplevel,))

        # What can NOT be recoloured, because it is an image or its own copy of
        # the palette - each such element has its own `set_pal()`.
        for widget in (getattr(self, "sidebar", None),
                       getattr(self, "titlebar", None)):
            if widget is None:
                continue
            try:
                widget.set_pal(nova_pal)
            except Exception:
                app_log.exception("set_pal zlyhal na %r", widget)

        for keycap in self._najdi_keycapy():
            try:
                keycap.set_pal(nova_pal)
            except Exception:
                pass

        # Charts and stat cards: `recolor_tree` can rewrite the widget's
        # OPTIONS, but not what already lies on the canvas - a line would stay
        # in the old colour until something redraws it. The live chart heals
        # itself with the next heart-rate sample, the chart in History stays.
        # KamaeBar was missing here. It is not a `PalCanvas` but a bare
        # `tk.Canvas`, and it draws from its own `self.pal` - so after a theme
        # switch a brown panel with a golden line stayed in an indigo window.
        # It is the header of the Today page, i.e. the first thing you see
        # after the switch.
        # `SlotIcon` is a visual's image with the colour baked in (In-game,
        # Cues).
        for widget in self._najdi_widgety((ui_kit.PalCanvas, ui_kit.StatCard,
                                           ui_kit.QrReveal, ui_kit.KamaeBar,
                                           ui_kit.SlotIcon)):
            try:
                widget.set_pal(nova_pal)
            except Exception:
                app_log.exception("set_pal zlyhal na %r", widget)

        # The middle of the Today page is a tk.Canvas with its own drawing
        # (dojo + enso + text) - the same case as KamaeBar: `recolor_tree`
        # rewrites at most the OPTION `bg`, but not what lies on the canvas.
        # The enso is also an IMAGE (colour baked in), so it needs an explicit
        # `set_pal`, which also throws away the frame cache and redraws the
        # whole middle in the new theme (`_emit` -> `_refresh_dnes_backdrop`).
        # `self.enso` is an `_EnsoHero`, not a widget, so `_najdi_widgety` does
        # not find it.
        try:
            if getattr(self, "enso", None) is not None:
                self.enso.set_pal(nova_pal)
        except Exception:
            app_log.exception("set_pal zlyhal na ense (stred Dnes)")

        # `ui_kit.Collapsible` SEPARATELY and with `zostup=True`.
        #
        # It computes its header colour from its own palette only at the moment
        # it is expanded, so an expanded section would glow with the old
        # theme's accent after a theme switch. But it can NOT be put in the
        # list above: that one no longer descends into a found widget and
        # Collapsible would shadow everything inside it - a chart placed in a
        # collapsed section would stay in the old theme.
        # Its own `set_pal` does not touch the children, so descending breaks
        # nothing.
        # `SubNav` computes its active tab (the accent line) from its own
        # palette - without the new one the next click on a tab would bring
        # back the old theme.
        for widget in self._najdi_widgety((ui_kit.Collapsible, ui_kit.SubNav),
                                          zostup=True):
            try:
                widget.set_pal(nova_pal)
            except Exception:
                app_log.exception("set_pal zlyhal na %r", widget)

        # The world switch (formerly the theme switch) does not change its
        # selected segment by itself when the world is changed by something
        # other than a click on it (title bar vs. Settings, the guide). On a
        # rebuild `.set()` in `_build_ui` handles it, here we have to call it
        # ourselves - otherwise the switch would show the old world although
        # the app already runs in the new one.
        self._sync_world_switches()
        # The trend period in History is also a segmented switch: the tree
        # recolour rewrites the text of all segments to one colour, the
        # selected segment has to be highlighted again.
        obdobie = getattr(self, "history_period_switch", None)
        if obdobie is not None:
            ui_kit.oznac_zvoleny_segment(obdobie, nova_pal)

        self._redraw_dnes_preview(nova_pal)

    def _najdi_widgety(self, triedy, zostup=False):
        """Widgets of the given classes in the window (no separate Toplevels).

        `zostup=False` does not descend further into a found widget - its
        `set_pal` recolours its descendants itself. So a StatCard recolours
        its own micro-chart and does not need to be searched for separately.
        """
        najdene = []
        zasobnik = [self.root]
        while zasobnik:
            w = zasobnik.pop()
            if isinstance(w, tk.Toplevel):
                continue
            if isinstance(w, triedy):
                najdene.append(w)
                if not zostup:
                    continue
            try:
                zasobnik.extend(w.winfo_children())
            except Exception:
                pass
        return najdene

    def _najdi_keycapy(self):
        """Trigger keys - they have their own `set_pal`, because in the Sumi theme
        `keycap_text` has the same value as `accent` and the mechanical map
        would give them the accent (see theme_recolor)."""
        return self._najdi_widgety(ui_kit.Keycap)

    def _redraw_dnes_preview(self, pal):
        """HUD preview on the Today page is a PIL image - it gets redrawn."""
        label = getattr(self, "dnes_preview_label", None)
        if label is None or not label.winfo_exists():
            return
        try:
            style = hud_paint.Style(pal)
            img = hud_paint.render_hud(
                style, bpm=72, stress=18,
                history=[64 + ((i * 5) % 14) for i in range(90)],
                threshold=self.hr_critical_bpm, baseline=64,
                labels={"load": tr("hud.load")}, pulse=0.0, session="", ss=2)
            img = img.resize((int(img.width * 0.62), int(img.height * 0.62)))
            img.putalpha(img.getchannel("A").point(lambda v: int(v * 0.45)))
            photo = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            label.configure(image=photo)
            label.image = photo
        except Exception:
            app_log.exception("nahlad HUD na Dnes sa nepodarilo prekreslit")

    # ---------- settings ----------

    def load_settings(self):
        # The language is detected right at the start - the sample slots for
        # new installs must already be generated in the right language.
        #
        # NOTE: `LANG_SK` was hard-coded here. The app is also downloaded by
        # Germans or Japanese, and on the first start Slovak popped up at them,
        # including the "Sparovat hodinky" (Pair your watch) button, which is
        # the first step of the onboarding. A first install now takes the
        # Windows language and, if we do not know it, English.
        lang = system_lang()
        # ONE BAD BYTE NO LONGER WIPES EVERYTHING (0.3). Until now an
        # unreadable file = default profiles, texts and positions, and
        # `__init__` overwrote it a second later (`save_settings`). Now the
        # broken file is moved aside and the last backup is loaded (`.bak`, see
        # `save_settings`); the player learns about it once
        # (`_oznam_obnovu_nastaveni`).
        loaded, obnova = nacitaj_nastavenia(SETTINGS_PATH)
        try:
            self._nastavenia_obnova = obnova
        except Exception:
            pass
        # NOTE: `in (LANG_SK, LANG_EN, LANG_JA)` stood here - a list
        # from the times when the app knew three languages. The switch
        # in Settings meanwhile offers NINE of them and saves the choice
        # correctly, but this filter threw it away on the next start and
        # fell back to Slovak. And since `__init__` calls
        # `save_settings()` right after start, the degraded value was
        # written back to the file - the player's choice was gone for
        # good. Verified: zh, ru, es, de, fr, pt were all lost, only
        # sk/en/ja survived. Always compare against `LANGUAGES`, not
        # against a hand-copied trio.
        if loaded is not None and loaded.get("lang") in LANGUAGES:
            lang = loaded["lang"]
        set_lang(lang)

        default_profile_name = tr("profile.default_name")
        data = {
            "profiles": [{"name": default_profile_name, "slots": default_slots()}],
            "active_profile": default_profile_name,
            # cooldown / rate / volume / balance / overlap - see
            # settings_model.DEFAULT_AUDIO (the same is used by the
            # "Restore recommended" button on the Sound page)
            **DEFAULT_AUDIO,
            "voice_id": "",
            "engine_pref": ENGINE_EDGE,
            # First start: Windows in a language from VOICE_HINTS (e.g.
            # Bulgarian, German) gets a voice of its language - the default
            # cues are in it.
            "edge_voice": suggested_voice(lang),
            "theme": theme_mod.DEFAULT_THEME,
            # World (B3-worlds). A new player starts in Play - it is an app for
            # gamers; they pick their main world in the onboarding (step 4).
            "world": hr_stats.WORLD_DEFAULT,
            # Cue style (voice / sound without words / picture only). Sets the
            # top of the cue ladder (`rebrik.py`); a missing key = voice.
            "cue_style": rebrik.STYL_HLAS,
            "first_run": True,
            "tour_seen": False,
            "tour_step": 0,
            # English even for the Slovak interface: the HUD and the in-game
            # labels end up on the stream and on screenshots in the store.
            "game_lang": LANG_EN,
            "lang": lang,
            "start_minimized": False,
            "tray_close_explained": False,
            "auto_profile_enabled": True,
            "overlay_configs": default_overlay_configs(),
            "hr_ip": ANY_INTERFACE,
            "hr_port": HR_DEFAULT_PORT,
            "hr_monitoring_enabled": False,
            "zanshin_graduated": False,
            "zanshin_graduated_at": None,
            "snooze_hotkey": DEFAULT_SNOOZE_HOTKEY,
            # Did the player pick the shortcut themselves (Settings ->
            # General)? Until then the app may swap it on a clash with the
            # keyboard layout (`_vyber_skratku_pri_starte`, 0.3).
            "snooze_hotkey_chosen": False,
            "background_opacity": background.DEFAULT_OPACITY,
            "monitor_target": DEFAULT_MONITOR_TARGET,
            "hud_config": default_hud_config(),
            "dashboard_stats": list(DEFAULT_DASHBOARD_STATS),
            "breath_inhale_s": DEFAULT_BREATH_INHALE_S,
            "breath_exhale_s": DEFAULT_BREATH_EXHALE_S,
            # The ring at high heart rate: off by default, limit 110 BPM.
            # A setting of the app, not of a game profile - it is in neither
            # the profiles nor the profile codes.
            "high_hr_ring": False,
            "high_hr_ring_bpm": DEFAULT_HIGH_HR_RING_BPM,
            "old_installer_warned": False,
        }
        if loaded is not None:
            try:
                profiles_raw = loaded.get("profiles")
                profiles = []
                if isinstance(profiles_raw, list):
                    for p in profiles_raw:
                        if not isinstance(p, dict):
                            continue
                        name = str(p.get("name") or "").strip()
                        if not name:
                            continue
                        pslots = p.get("slots")
                        pslots = ([normalize_slot(s) for s in pslots if isinstance(s, dict)]
                                  if isinstance(pslots, list) else [])
                        # A profile without slots gets four categories - the
                        # player has no way to add them any more (the button is
                        # gone).
                        profiles.append({"name": name,
                                         "slots": pslots or [normalize_slot(s)
                                                             for s in default_slots()]})
                if not profiles:
                    # migration from the old flat schema (Dandurf/pre-profile version)
                    legacy_slots = loaded.get("slots")
                    if isinstance(legacy_slots, list) and legacy_slots:
                        legacy_slots = [normalize_slot(s) for s in legacy_slots
                                       if isinstance(s, dict)]
                    if legacy_slots:
                        profiles = [{"name": default_profile_name, "slots": legacy_slots}]
                if profiles:
                    data["profiles"] = profiles
                names = [p["name"] for p in data["profiles"]]
                active = str(loaded.get("active_profile") or "")
                data["active_profile"] = active if active in names else names[0]

                data["voice_id"] = str(loaded.get("voice_id") or "")
                data["rate"] = clamp_int(loaded.get("rate"), -10, 10, 0)
                data["volume"] = clamp_int(loaded.get("volume"), 0, 100, 100)
                data["balance"] = clamp_int(loaded.get("balance"), 0, 100, 50)
                data["start_minimized"] = bool(loaded.get("start_minimized", False))
                data["tray_close_explained"] = bool(loaded.get("tray_close_explained", False))
                data["auto_profile_enabled"] = bool(loaded.get("auto_profile_enabled", True))
                overlay_raw = loaded.get("overlay_configs")
                if isinstance(overlay_raw, list) and len(overlay_raw) >= 4:
                    data["overlay_configs"] = [normalize_overlay_config(overlay_raw[i], i)
                                              for i in range(4)]
                else:
                    # migration from the old simple switch (only the breathing
                    # circle, slot 4) - the other 3 new visuals stay off.
                    cfgs = default_overlay_configs()
                    cfgs[3]["enabled"] = bool(loaded.get("breathing_overlay_enabled", False))
                    data["overlay_configs"] = cfgs
                # ONE-TIME MOVE: grounding from the bottom centre to the left
                # middle (it would sit under the exhale ring that now comes
                # with every cue). Only a visual still at exactly the old
                # default moves - a dragged position stays. ONCE, like
                # `visuals_repaired` below: `save_settings` writes
                # `grounding_moved`, so a player who later puts it back at
                # the bottom keeps it there.
                if not loaded.get("grounding_moved"):
                    move_old_grounding_position(data["overlay_configs"])
                data["hr_ip"] = str(loaded.get("hr_ip") or ANY_INTERFACE)
                # 65432 was the old default port from the times when the
                # receiver knew only UDP. Apps for OBS (including
                # HeartRateOnStream) go to 4455, so on that old port the player
                # would wait forever - we move it once to the working default.
                stored_port = clamp_int(loaded.get("hr_port"), 1, 65535, HR_DEFAULT_PORT)
                data["hr_port"] = HR_DEFAULT_PORT if stored_port == 65432 else stored_port
                data["hr_monitoring_enabled"] = bool(loaded.get("hr_monitoring_enabled", False))
                data["zanshin_graduated"] = bool(loaded.get("zanshin_graduated", False))
                _zg = loaded.get("zanshin_graduated_at")
                data["zanshin_graduated_at"] = _zg if isinstance(_zg, (int, float)) else None
                # Empty string = off. A nonsensical combination silently
                # falls back to the default - the player could have edited it
                # by hand in the JSON and the app must not crash because of it.
                hk = loaded.get("snooze_hotkey", DEFAULT_SNOOZE_HOTKEY)
                hk = "" if hk in (None, "") else str(hk).strip().lower()
                data["snooze_hotkey"] = (
                    hk if (hk == "" or hotkey.is_valid(hk))
                    else DEFAULT_SNOOZE_HOTKEY)
                data["snooze_hotkey_chosen"] = bool(loaded.get("snooze_hotkey_chosen", False))
                # Background subtlety. The cap is in `background.py`, not
                # here - whoever wants to change it changes it in one place.
                data["background_opacity"] = background.clamp_opacity(
                    loaded.get("background_opacity"))
                data["monitor_target"] = normalize_monitor_target(loaded.get("monitor_target"))
                data["hud_config"] = normalize_hud_config(loaded.get("hud_config"))
                # NOTE: "dojo_intensity" was loaded here too (photo strip above
                # the title bar). Nobody reads the key any more - it may stay
                # in old dandurf_settings.json files, it is just ignored and
                # drops out on the next save.
                data["dashboard_stats"] = normalize_dashboard_stats(loaded.get("dashboard_stats"))
                data["breath_inhale_s"], data["breath_exhale_s"] = normalize_breath_seconds(
                    loaded.get("breath_inhale_s"), loaded.get("breath_exhale_s"))
                # Off by default, so only a real `true` switches the ring on -
                # a hand-edited "yes" or 1 does not.
                data["high_hr_ring"] = loaded.get("high_hr_ring") is True
                data["high_hr_ring_bpm"] = normalize_high_hr_ring_bpm(
                    loaded.get("high_hr_ring_bpm"))
                # ONE-TIME FIX: all four visuals off.
                #
                # Until 19. 9. they were off BY DEFAULT and `_cue_can_fire`
                # does not let a cue through without a visual on - so in this
                # state the app stays silent and the player has no way to find
                # out why. Nobody chose this, it came from the default, so we
                # fix it once.
                #
                # REALLY ONCE (0.2). The assumption "whoever turns them off
                # themselves has at least one on" did not hold - the UI lets
                # you turn off all four, and the app then turned them back on
                # at EVERY start, although the log promised they could be
                # turned off. After the first load `visuals_repaired` is
                # written to the settings and from then on turning them off is
                # the player's decision, which the app does not override.
                if (not loaded.get("visuals_repaired")
                        and all(not cfg["enabled"] for cfg in data["overlay_configs"])):
                    for cfg in data["overlay_configs"]:
                        cfg["enabled"] = True
                    data["_vizualy_napravene"] = True
                if loaded.get("engine_pref") in (ENGINE_EDGE, ENGINE_SAPI):
                    data["engine_pref"] = loaded["engine_pref"]
                data["edge_voice"] = str(loaded.get("edge_voice")
                                         or DEFAULT_EDGE_VOICE)
                data["tour_seen"] = bool(loaded.get("tour_seen", False))
                data["tour_step"] = clamp_int(loaded.get("tour_step"), 0,
                                              GuidedTour.STEP_COUNT - 1, 0)
                game_lang = loaded.get("game_lang")
                if game_lang in LANGUAGES or game_lang == LANG_SAME_AS_APP:
                    data["game_lang"] = game_lang
                # A saved theme is the MARKER "first start already happened" -
                # and it stays that way; but the look itself is now decided by
                # the world (below).
                if loaded.get("theme") in (theme_mod.ZEN, theme_mod.MODERN):
                    data["theme"] = loaded["theme"]
                    data["first_run"] = False
                # WORLD (B3-worlds). Missing or nonsensical -> Play. MIGRATION:
                # settings from an older version have no world, even when the
                # player had Aizome selected. The world is NOT DERIVED from the
                # theme - otherwise their gaming would start counting as work;
                # it goes to Play and the theme follows the world (the author's
                # decision).
                data["world"] = (hr_stats.normalize_activity(loaded.get("world"))
                                 or hr_stats.WORLD_DEFAULT)
                data["cue_style"] = rebrik.normalize_cue_style(loaded.get("cue_style"))
                data["old_installer_warned"] = bool(loaded.get("old_installer_warned", False))
            except Exception:
                app_log.exception("load_settings: castocne poskodeny/neocakavany "
                                  "obsah %s - pouzijem defaulty pre chybajuce polia",
                                  SETTINGS_PATH)
        # The look belongs to the world - also after a damaged file, also on
        # the first start.
        data["theme"] = theme_mod.WORLD_THEME.get(data["world"], theme_mod.DEFAULT_THEME)
        # ONE-TIME CHANGE of the old default words to the ones with the
        # exhale. ONCE, like `grounding_moved`: `save_settings` writes
        # `exhale_words`, so a player who later types an old word back
        # ("Jaw") keeps it - from then on it is their own word.
        prelozit_slova = not (loaded is not None and loaded.get("exhale_words"))
        # An old default word shared by several languages (ja/zh 呼吸, es/pt
        # Mandíbula...) that the rest of the profile does not settle: the
        # language of the voice that reads it first, then the app language.
        jazyky_slov = (jazyk_hlasu(data["edge_voice"]), data["lang"])
        for profile in data["profiles"]:
            # A profile with fewer than four slots (created by hand in 0.1,
            # where slots were added with a button, or after a removal) gets
            # the missing categories at the end, OFF. The "+ Pridat spustac" (+
            # Add trigger) button is gone, so otherwise the category could no
            # longer be put back into the profile.
            profile["slots"] = doplnit_kategorie(profile["slots"])
            # Old default word ("Grounded", ja 重心, the 0.1 "Teeth"...) ->
            # the new one with the exhale, in the same language. Only on
            # load and when a profile code from before 0.3.1 is imported,
            # see `settings_model.migrate_profile_texts`.
            if prelozit_slova:
                migrate_profile_texts(profile["slots"], jazyky_slov)
            for slot in profile["slots"]:
                slot["audio_path"] = resolve_audio_path(slot["audio_path"])
                slot["voice_path"] = resolve_audio_path(slot["voice_path"])
        return data

    def save_settings(self):
        if not self._ready or not self.slots:
            return
        self._sync_active_profile_slots()
        data = {
            "profiles": self.profiles,
            "active_profile": self.active_profile_name,
            "voice_id": self.saved_voice_id,
            "rate": int(self.rate_value),
            "volume": int(self.volume_value),
            "balance": int(self.balance_value),
            "engine_pref": self.engine_pref,
            "edge_voice": self.edge_voice_id,
            # `theme` is still saved: it is the marker "first start already
            # happened" (`load_settings`). On start the world overwrites it
            # anyway.
            "theme": self.theme_key,
            "world": getattr(self, "world", hr_stats.WORLD_DEFAULT),
            "cue_style": getattr(self, "cue_style", rebrik.STYL_HLAS),
            "lang": self.lang,
            "start_minimized": bool(self.start_minimized),
            "tray_close_explained": bool(getattr(self, "tray_close_explained", False)),
            "auto_profile_enabled": bool(self.auto_profile_enabled),
            "overlay_configs": self.overlay_configs,
            "tour_seen": bool(getattr(self, "tour_seen", False)),
            "tour_step": int(getattr(self, "tour_step", 0)),
            "game_lang": getattr(self, "game_lang", LANG_EN),
            "hr_ip": self.hr_ip,
            "hr_port": int(self.hr_port),
            # A sensor switched off by a port/bind error goes to the file as
            # on: it was not the player's decision and the next start should
            # try again (app_session._senzor_vypla_chyba, 0.3).
            "hr_monitoring_enabled": bool(
                self.hr_monitoring_enabled
                or getattr(self, "_hr_vypnute_chybou", False)),
            "zanshin_graduated": bool(self.zanshin_graduated),
            "zanshin_graduated_at": self.zanshin_graduated_at,
            "snooze_hotkey": self.snooze_hotkey,
            "snooze_hotkey_chosen": bool(getattr(self, "snooze_hotkey_chosen", False)),
            "background_opacity": self.background_opacity,
            "monitor_target": self.monitor_target,
            "hud_config": self.hud_config,
            "dashboard_stats": list(self.dashboard_stats),
            "breath_inhale_s": float(self.breath_inhale_s),
            "breath_exhale_s": float(self.breath_exhale_s),
            "high_hr_ring": bool(getattr(self, "high_hr_ring", False)),
            "high_hr_ring_bpm": normalize_high_hr_ring_bpm(
                getattr(self, "high_hr_ring_bpm", DEFAULT_HIGH_HR_RING_BPM)),
            # The one-time fix of switched-off visuals has already run (or was
            # not needed) - see `load_settings`. From now on switched-off
            # visuals are the player's choice.
            "visuals_repaired": True,
            # The one-time move of an untouched grounding visual to the left
            # middle has already run (or was not needed) - see
            # `load_settings`. From now on its position is the player's.
            "grounding_moved": True,
            # The one-time change of the old default cue words to the ones
            # with the exhale has already run - see `load_settings`. From now
            # on every word in a slot is the player's.
            "exhale_words": True,
            # The warning about an installed 0.2 has already been shown (once,
            # see `_upozorni_na_staru_instalaciu`).
            "old_installer_warned": bool(getattr(self, "old_installer_warned", False)),
        }
        # Before every write: the previous VALID file -> .bak. A failure of the
        # backup must not stop the save itself (the file may be held by an
        # antivirus or sync), so it has its own try.
        try:
            zaloha_nastaveni(SETTINGS_PATH)
        except Exception:
            app_log.exception("save_settings: zalohu nastaveni sa nepodarilo zapisat")
        try:
            # Atomic write: first .tmp, only then os.replace() - the same pattern
            # the app already uses in sfx_assets._save_wav()/_try_download().
            # Without this a crash/power cut DURING the write (and it saves on
            # every slider change!) could leave an empty/truncated JSON and with
            # it the loss of all profiles at the next start. `nahrad_subor`
            # survives a short file lock (antivirus, indexing).
            tmp_path = f"{SETTINGS_PATH}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            nahrad_subor(tmp_path, SETTINGS_PATH, uprac_zdroj=True)
        except Exception as exc:
            self.log(tr("log.settings_save_error", err=exc))
            app_log.exception("save_settings zlyhalo")

    def _oznam_obnovu_nastaveni(self):
        """Once after start: settings could not be loaded (`nacitaj_nastavenia`).

        A journal line and a message, only once the window is up (`after`) -
        the start does not stop because of it. Called from `__init__` after
        the window is built, because the journal does not exist before that
        and the text must be in the language from the restored settings
        (set by `load_settings`)."""
        obnova = getattr(self, "_nastavenia_obnova", None)
        self._nastavenia_obnova = None
        if not obnova:
            return
        if obnova.get("zo_zalohy"):
            text = tr("log.settings_restored_backup", name=obnova.get("odlozene"))
        else:
            text = tr("log.settings_restored_defaults", name=obnova.get("odlozene"))
        self.log(text)

        def _ukaz():
            try:
                # the app's own window, not a system one (0.3, batch 4)
                ui_kit.notify(getattr(self, "root", None), getattr(self, "pal", None),
                              APP_NAME, text, kind="warning")
            except Exception:
                app_log.exception("oznam o obnove nastaveni sa neukazal")

        try:
            self.root.after(OZNAM_OBNOVY_MS, _ukaz)
        except Exception:
            app_log.exception("oznam o obnove nastaveni sa nenaplanoval")


    def on_volume_change(self):
        try:
            value = int(self.volume_var.get())
        except Exception:
            return
        self.volume_value = max(0, min(100, value))
        self.volume_value_label.configure(text=f"{self.volume_value} %")
        self._apply_volumes()
        self.save_settings()

    def on_balance_change(self):
        try:
            value = int(self.balance_var.get())
        except Exception:
            return
        self.balance_value = max(0, min(100, value))
        self.balance_value_label.configure(text=self._balance_label_text())
        self._apply_volumes()
        self.save_settings()

    def _balance_label_text(self):
        if self.balance_value == 50:
            return tr("settings.balance_center")
        side = tr("settings.balance_tts") if self.balance_value > 50 else tr("settings.balance_sfx")
        return f"{abs(self.balance_value - 50) * 2}% {side}"

    def _apply_volumes(self):
        self._recompute_volumes()
        self.audio.sfx_volume = self.sfx_volume
        self.audio.tts_volume = self.tts_volume
        self.worker.set_volume(self.tts_volume)


    def refresh_edge_banner(self):
        if audio_engine.EDGE_AVAILABLE or self.engine_pref != ENGINE_EDGE:
            self.banner.pack_forget()
            return
        self.banner_label.configure(text=tr("banner.edge_missing"))
        self.banner.pack(fill="x", padx=20, pady=(0, 8), before=self.main_grid)

    def retry_edge_import(self):
        if audio_engine.load_edge():
            self.log(tr("log.edge_loaded"))
            self.engine = self.engine_pref = ENGINE_EDGE
            self.engine_var.set(engine_labels()[ENGINE_EDGE])
            self.refresh_edge_banner()
            self.save_settings()
            self._load_edge_voices()
        else:
            self.log(tr("log.edge_still_missing", err=audio_engine.EDGE_IMPORT_ERROR))
            ui_kit.notify(
                getattr(self, "root", None), getattr(self, "pal", None), APP_NAME,
                tr("msgbox.edge_still_missing", err=audio_engine.EDGE_IMPORT_ERROR),
                kind="warning")

    # ---------- "not now" shortcut (0.3) ----------
    #
    # The registration itself is in app.py (`start_snooze_hotkey`, reads
    # TRAY_AVAILABLE). Here is what gets decided around it: the clash with
    # the keyboard layout at start, the choice in Settings -> General and
    # the shortcut's wording for the sentences that name it to the player.

    def _skratka_teraz_nie(self):
        """Display form of the shortcut, ONLY if really registered; else "".

        The bar (`kamae.snoozed_sub`) and the tour pick their sentence by
        it: they must not promise a shortcut that is off or held by
        another program."""
        drzi = getattr(self, "_hotkey", None)
        if drzi is None or not getattr(drzi, "registered", False):
            return ""
        return hotkey.format_combo(getattr(self, "snooze_hotkey", "") or "")

    def _vyber_skratku_pri_starte(self, kolizia=None):
        """Before registering: would the default shortcut swallow a letter?

        AltGr is Ctrl+Alt on Windows - on the Polish layout AltGr+Z types
        "ż" and a registered Ctrl+Alt+Z would take it from the player in
        every window. Applies ONLY to the default shortcut that the player
        did not pick themselves (`snooze_hotkey_chosen`); the app does not
        change their own choice. The replacement is the first free preset
        (`hotkey.prva_volna`), otherwise none. It is said ONCE: the
        replacement is saved, so on the next start it is no longer the
        default.

        `kolizia(combo) -> znak` can be injected (tests). Returns the
        replacement, "" (shortcut off) or None (nothing changed)."""
        combo = getattr(self, "snooze_hotkey", "") or ""
        if combo != DEFAULT_SNOOZE_HOTKEY or getattr(self, "snooze_hotkey_chosen", False):
            return None
        zisti = kolizia or hotkey.znak_kolizie
        try:
            znak = zisti(combo)
        except Exception:
            app_log.exception("hotkey: kontrola rozlozenia klavesnice zlyhala")
            return None
        if not znak:
            return None
        nahrada = hotkey.prva_volna(hotkey.PRESETS, preskoc=(combo,), kolizia=zisti)
        self.snooze_hotkey = nahrada
        stara = hotkey.format_combo(combo)
        if nahrada:
            self.log(tr("log.hotkey_layout_swapped", combo=stara, char=znak,
                        new=hotkey.format_combo(nahrada)))
        else:
            self.log(tr("log.hotkey_layout_off", combo=stara, char=znak))
        # app.log in English even in German ("Ctrl", not "Strg") - like
        # `hotkey`
        app_log.info("hotkey: %s pise znak na rozlozeni klavesnice, nahrada: %s",
                     hotkey.format_combo(combo, lang="en"), nahrada or "ziadna")
        try:
            self.save_settings()
        except Exception:
            app_log.exception("hotkey: nahradu skratky sa nepodarilo ulozit")
        return nahrada

    def _snooze_hotkey_volby(self, kolizia=None):
        """[(label, combination)] for the shortcut dropdown.

        Presets (`hotkey.PRESETS`), the shortcut from a hand-edited file if
        it is not among them, and at the end "off" (""). A preset that
        would type a character on some layout is NOT HIDDEN (the player may
        have had it selected), it is only marked with the character it
        would swallow."""
        zisti = kolizia or hotkey.znak_kolizie
        kombinacie = list(hotkey.PRESETS)
        sucasna = getattr(self, "snooze_hotkey", "") or ""
        if sucasna and sucasna not in kombinacie and hotkey.is_valid(sucasna):
            kombinacie.append(sucasna)
        volby = []
        for combo in kombinacie:
            popis = hotkey.format_combo(combo)
            try:
                znak = zisti(combo)
            except Exception:
                znak = ""
            if znak:
                popis = tr("settings.snooze_hotkey_types", combo=popis, char=znak)
            volby.append((popis, combo))
        volby.append((tr("settings.snooze_hotkey_none"), ""))
        return volby

    def _snooze_hotkey_sub(self):
        """The sentence under the shortcut choice - by what really applies."""
        combo = getattr(self, "snooze_hotkey", "") or ""
        if not combo:
            return tr("settings.snooze_hotkey_off_sub")
        pekne = hotkey.format_combo(combo)
        if getattr(self, "_hotkey_zlyhala", False):
            return tr("settings.snooze_hotkey_taken", combo=pekne)
        return tr("settings.snooze_hotkey_sub", combo=pekne, minutes=SNOOZE_HOTKEY_MINUTES)

    def _build_snooze_hotkey_row(self, parent, pal):
        """Settings -> General: choosing the "not now" shortcut (0.3).

        Before 0.3 it could only be changed by hand in the settings file -
        and whoever had the shortcut taken by another program, or had it
        eat a letter, had no way to do it."""
        panel = ui_kit.Panel(parent, pal, title=tr("settings.snooze_hotkey_title"))
        panel.pack(fill="x", pady=(14, 0))
        row = ui_kit.SettingRow(panel.body, pal, tr("settings.snooze_hotkey"),
                                self._snooze_hotkey_sub())
        self.snooze_hotkey_row = row
        volby = self._snooze_hotkey_volby()
        self._snooze_hotkey_podla_popisu = dict(volby)
        sucasna = getattr(self, "snooze_hotkey", "") or ""
        zvolena = next((popis for popis, combo in volby if combo == sucasna), volby[-1][0])
        self.snooze_hotkey_var = tk.StringVar(value=zvolena)
        self.snooze_hotkey_menu = ui_kit.option_menu(
            row.control, pal, values=[popis for popis, _c in volby],
            variable=self.snooze_hotkey_var, command=self.on_snooze_hotkey_pick)
        self.snooze_hotkey_menu.pack()

    def _refresh_snooze_hotkey_row(self):
        """Shortcut row by what really applies. Called after the choice in
        Settings and also AFTER THE REGISTRATION AT START (`__init__`): the
        row is built in `_build_ui` before the shortcut is registered, and
        the start may also swap it (`_vyber_skratku_pri_starte`) - without
        this the row would claim that a taken shortcut works, and the menu
        would show the old one.

        When Windows does not finish the registration within 2 s, it is
        called once more - only after the real result from the shortcut
        thread (`_po_registracii_skratky`, 0.3 batch 4b). Until then the
        row does not claim that another program holds the shortcut."""
        row = getattr(self, "snooze_hotkey_row", None)
        label = getattr(row, "sub_label", None)
        if label is None:
            return
        try:
            label.configure(text=self._snooze_hotkey_sub())
        except Exception:
            pass            # the page is being rebuilt right now
        var = getattr(self, "snooze_hotkey_var", None)
        sucasna = getattr(self, "snooze_hotkey", "") or ""
        popis = next((p for p, c in getattr(self, "_snooze_hotkey_podla_popisu", {}).items()
                      if c == sucasna), None)
        if var is not None and popis is not None:
            try:
                if var.get() != popis:
                    var.set(popis)
            except Exception:
                pass

    def on_snooze_hotkey_pick(self, label):
        """The player picked a shortcut. It applies AT ONCE: the old one is
        unregistered and the new one registered (`start_snooze_hotkey`).
        When another program holds it, the choice STAYS (it goes to the
        file), only the row and the journal say so - once that program is
        closed, it takes effect on the next start."""
        combo = getattr(self, "_snooze_hotkey_podla_popisu", {}).get(label)
        if combo is None:
            return
        self.snooze_hotkey_chosen = True
        zmena = combo != (getattr(self, "snooze_hotkey", "") or "")
        self.snooze_hotkey = combo
        self.save_settings()
        if zmena or getattr(self, "_hotkey_zlyhala", False):
            self.start_snooze_hotkey(po_zmene=True)
            if not combo:
                self.log(tr("log.hotkey_off"))
        self._refresh_snooze_hotkey_row()
        obnov = getattr(self, "_refresh_kamae_state_text", None)
        if callable(obnov):
            try:
                obnov()
            except Exception:
                app_log.exception("hotkey: pas sa po zmene skratky neobnovil")
