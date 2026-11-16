"""HUD and in-game visuals - part of the main app (DandurfApp from app.py).

HudMixin is a mixin of DandurfApp: app.py inherits it and the whole state (the
HUD window and its configuration, the overlay manager and the visuals
configuration, the target monitor, the game language, the breath length, the
heart-rate sensor) lives on DandurfApp. Here are only the methods that work
with it through `self` - the mixin has no __init__ and no attributes of its
own.

Three sections moved from app.py unchanged:
  * In-game panel with the 4 basic functions (HUD trigger row) - the row of
    icons under the HUD panel in the game,
  * HUD (live panel with heart-rate statistics) - the language and labels of
    what the app draws into the game, HUD configuration, monitor choice and the
    session text; the section also carries the small snooze-length menu
    (`_toggle_snooze_menu`), which was already in it in app.py,
  * In-Game Visuals (Overlay) - the heart-rate indicator in the sidebar,
    pairing the watch (switching the sensor on), configuration, colour and
    visuals test.

The constant `WATCH_ZONE_HOLD_S` (hysteresis of the heart-rate indicator)
stayed in the DandurfApp class among the other class constants -
`_watch_pulse_state` reads it through `self`.

Watch out in tests: `_watch_pulse_state` and `_refresh_hud_session_text` read
`time` from this module - fake clocks on the app module do not reach them (you
need `app_hud.time`).
"""

import time

import customtkinter as ctk

import display
import ui_kit
from i18n import LANGUAGES, LANG_EN, LANG_SAME_AS_APP, tr, tr_lang
from settings_model import (clamp_float, normalize_breath_seconds,
                            normalize_high_hr_ring_bpm,
                            normalize_hud_config, normalize_monitor_target,
                            normalize_overlay_config)
from ui_dialogs import OverlaySettingsDialog, WatchPairingDialog

from app_spolocne import LABEL_TO_LANG, LANG_NATIVE_LABELS


class HudMixin:
    """HUD, 4-function row, game language, in-game visuals (DandurfApp mixin)"""

    # ---------- In-game panel with 4 basic functions (HUD trigger row) ----------
    #
    # NOTE ON HISTORY: these were originally two methods for the app-wide
    # "Minimalist mode" (it shrank the whole app window to 320x160 -
    # `set_minimal_mode`/`_apply_minimal_mode`, now removed). The same list
    # of 4 functions is useful here too, though - it is the same data
    # (visual name + label + key combination for slots 0..3), only now drawn
    # as a row under the HUD panel in the game
    # (`hud_paint.render_hud_trigger_row`), not as a separate app window.

    def show_hud_settings(self):
        """⚙ next to "On-screen HR panel" on Today: Settings -> General,
        the heart-rate panel section expanded and scrolled to the top.

        Before 0.3 the ⚙ led to the In game page - there are no HUD settings
        there, and the sidebar meanwhile kept highlighting "Today". The scroll
        happens only after a redraw, just like `show_about`."""
        self._navigate("vseobecne")
        sekcia = getattr(self, "hud_section", None)
        try:
            if sekcia is not None and not sekcia.expanded:
                sekcia.toggle()
        except Exception:
            pass
        self.root.after(80, lambda: self._posun_vseobecne_na(sekcia))

    def _sync_hud_trigger_state(self):
        """Greys out the icons while the heart-rate panel is off.

        Without that it is a switch that can be turned on and does nothing -
        and that is worse than a switch that cannot be turned on. The whole
        switch is dimmed (track and knob), not just the text - a gold track
        that is on would otherwise keep claiming "it works".
        """
        aktivny = bool(self.hud_config.get("enabled"))
        prepinac = getattr(self, "hud_trigger_switch", None)
        if prepinac is not None:
            ui_kit.nastav_prepinac_aktivny(prepinac, self.pal, aktivny)
        vzorka = getattr(self, "hud_trigger_swatch", None)
        try:
            if vzorka is not None:
                vzorka.configure(state="normal" if aktivny else "disabled")
        except Exception:
            pass

    def _hud_trigger_info(self):
        """[(visual name, enabled)] for the row of 4 basic functions under the
        HUD panel - by position they match self.slots[0..3].

        THE LABEL UNDER THE ICON IS NO LONGER HERE. Until 19. 9.
        `slot.display_key()` was drawn under each icon, i.e. 'C', 'R', 'Mys:
        right', 'F'. Those were keys from `DEFAULT_SLOT`, which since phase 3
        trigger nothing - the app does not read keys at all. So the player
        read, right in the game, instructions that were not valid, and pressing
        those keys achieved nothing.

        Replacing them with a label makes no sense: the row is a few pixels
        tall and is meant to be peripheral. The icon is the same graphic the
        player sees when the cue comes - that is enough.
        """
        visuals = ("grounding", "jaw", "release", "breath")
        out = []
        # getattr, not self.slots directly: _apply_hud_config() is called from
        # __init__ still BEFORE self.slots = [] (a line lower in __init__),
        # so on the first call the attribute does not exist at all yet.
        slots = getattr(self, "slots", [])
        for i, visual_name in enumerate(visuals):
            enabled = True
            if i < len(slots):
                enabled = bool(getattr(slots[i], "enabled_value", True))
            out.append((visual_name, enabled))
        return out

    def _on_hud_trigger_click(self, index):
        """A click on an icon in the HUD row (only in the preview in the app,
        in the game the panel is click-through - see hud.StatsHud.handle_click)
        fires that cue by hand through `fire_slot`, as the Test button on
        its card does (but keeping the gap between quick clicks); a
        hand-fired cue is not recorded in the measurement (`_note_cue`).
        Before phase 3 it did what pressing the slot's key did."""
        if 0 <= index < len(self.slots):
            self.fire_slot(self.slots[index], source="hud_panel")

    def _refresh_hud_trigger_row(self):
        """Redraws the list of 4 functions in the HUD panel - called on a
        change of slots (key rebind, on/off) and on a language change."""
        hud = getattr(self, "hud", None)
        if hud is None:
            return
        try:
            hud.configure_triggers(triggers=self._hud_trigger_info())
        except Exception:
            pass

    # ---------- HUD (live panel with heart-rate statistics) ----------

    def _apply_overlay_labels(self):
        """Labels under the in-game visuals + the words of the breathing cycle.

        They are drawn into the image, so on a language change they have to be
        handed to the manager again - that is why this is a separate method and
        not a constructor parameter.
        """
        g = self._game_text
        self.overlay_manager.set_labels(
            {0: g("overlay.caption.grounding"),
             1: g("overlay.caption.jaw"),
             2: g("overlay.caption.release")},
            breath_inhale=g("overlay.caption.inhale"),
            breath_exhale=g("overlay.caption.exhale"))

    @staticmethod
    def _game_lang_label(code):
        return (LANG_NATIVE_LABELS.get(code) if code in LANGUAGES
                else tr("settings.game_lang_same"))

    def on_game_lang_change(self, label):
        """Switches the language of what the app draws into the game. Redrawn
        right away - the HUD and the visuals hold their labels as a finished
        image."""
        self.game_lang = LABEL_TO_LANG.get(label, LANG_SAME_AS_APP)
        self.save_settings()
        self._apply_overlay_labels()
        self._apply_hud_labels()
        self.log(tr("log.game_lang", lang=self._game_lang_label(self.game_lang)))

    def _game_text(self, key, **kwargs):
        """Text the app draws INTO THE GAME - its own language, not the window
        language.

        The HUD sits bottom left on the game screen and the labels are under
        the visuals; both end up on stream and in store screenshots, where they
        are also read by people who do not know the interface language. So the
        default is English, even when the app runs in Slovak.
        """
        return tr_lang(getattr(self, "game_lang", LANG_EN), key, **kwargs)

    def _hud_labels(self):
        g = self._game_text
        return {
            "load": g("hud.load"),
            "calm": g("hud.zone.calm"),
            "raised": g("hud.zone.raised"),
            "high": g("hud.zone.high"),
            "critical": g("hud.zone.critical"),
            "waiting": g("hud.waiting"),
            "calibrating": g("hud.calibrating"),
        }

    def _apply_hud_labels(self):
        self.hud.set_labels(self._hud_labels())

    def _apply_hud_config(self):
        """Carries the saved HUD configuration over into the running window."""
        cfg = self.hud_config
        self.hud.set_style(self.overlay_manager.style)
        self._apply_hud_labels()
        self.hud.configure(enabled=cfg["enabled"], scale=cfg["scale"],
                           opacity=cfg["opacity"],
                           pos=(cfg["pos_x"], cfg["pos_y"]),
                           critical_bpm=self.hr_critical_bpm,
                           monitor_target=self.monitor_target)
        self.hud.configure_triggers(
            show=cfg["show_triggers"], icon_color=cfg["trigger_color"],
            triggers=self._hud_trigger_info(),
            on_click=self._on_hud_trigger_click)

    def on_hud_config_change(self, **kwargs):
        cfg = self.hud_config
        if "enabled" in kwargs:
            cfg["enabled"] = bool(kwargs["enabled"])
        if "scale" in kwargs:
            cfg["scale"] = clamp_float(kwargs["scale"], 0.6, 2.0, cfg["scale"])
        if "opacity" in kwargs:
            cfg["opacity"] = clamp_float(kwargs["opacity"], 0.25, 1.0, cfg["opacity"])
        if "pos" in kwargs:
            cfg["pos_x"] = clamp_float(kwargs["pos"][0], 0.0, 100.0, cfg["pos_x"])
            cfg["pos_y"] = clamp_float(kwargs["pos"][1], 0.0, 100.0, cfg["pos_y"])
        if "show_triggers" in kwargs:
            cfg["show_triggers"] = bool(kwargs["show_triggers"])
        if "trigger_color" in kwargs:
            # "" (empty string) means "go back to the theme colour", the same
            # convention as for the colour of the visuals' pictograms
            # (on_overlay_config_change)
            value = kwargs["trigger_color"]
            cfg["trigger_color"] = normalize_hud_config(
                {"trigger_color": value})["trigger_color"] if value else None
        self._apply_hud_config()
        # Turning the panel on/off changes whether the child icons have
        # anything to do.
        self._sync_hud_trigger_state()
        # Two switches for the same thing (in Settings and the quick one on
        # Today) are kept in sync. `.set()` does not call the CTkSwitch's
        # command, so it does not recurse.
        if "enabled" in kwargs:
            for meno in ("hud_enabled_var", "hud_quick_var"):
                var = getattr(self, meno, None)
                if var is not None:
                    try:
                        var.set(bool(kwargs["enabled"]))
                    except Exception:
                        pass
        self.save_settings()

    def _hud_trigger_color_display(self):
        """Swatch colour next to "Show the panel in game" - custom, or the
        theme accent (the same convention as _overlay_color for the 4
        visuals)."""
        return self.hud_config.get("trigger_color") or self.pal["accent"]

    def pick_hud_trigger_color(self):
        """Choice of the icon colour in the row of 4 basic functions under the
        HUD panel - the same system-native color picker as for the visuals
        (pick_overlay_color), only saved to hud_config instead of
        overlay_configs."""
        from color_picker import ask_color, DEFAULT
        current = self._hud_trigger_color_display()
        res = ask_color(self, current, title=tr("overlay.color_title"))
        if res is None:
            return
        self.on_hud_config_change(trigger_color=(None if res == DEFAULT else res))
        swatch = getattr(self, "hud_trigger_swatch", None)
        if swatch is not None:
            try:
                display = self._hud_trigger_color_display()   # None -> theme accent
                swatch.configure(fg_color=display, hover_color=display)
            except Exception:
                pass

    def _toggle_snooze_menu(self):
        """Expands/collapses the small menu for choosing the snooze length
        (5/20/40/60 min) next to the 😴 button in the sidebar dock.

        WARNING - IN 2.1 THIS MENU HAS NO TRIGGER. The 😴 button left with the
        quick dock (see `_build_ui`) and snooze is switched on with a global
        shortcut for a fixed `SNOOZE_HOTKEY_MINUTES` minutes. So the length
        choice is not available anywhere.

        The code is KEPT on purpose, not by oversight: the length choice is a
        natural candidate for one of the five simple controls from spec §3.1,
        which have not been decided yet. When the decision is made, it is
        enough to call it from there; if it is decided otherwise, it should
        be removed.

        It takes its anchor from `quick_dock`, which no longer exists, so the
        method ends right at `anchor is None` - it does not crash, it just does
        nothing.

        Drawn as a CTkToplevel without an OS frame (the same pattern as the
        other temporary popups in the app), it closes with a click outside it
        or another click on 😴.

        NOTE: the menu used to hang under the gear wheel on the In game page.
        That is why it is now anchored to the RIGHT of the button, not below
        it - the dock sits at the bottom edge of the window, so there is no
        room below it and the menu would stick out off the screen."""
        existing = getattr(self, "_snooze_menu", None)
        if existing is not None and existing.winfo_exists():
            existing.destroy()
            self._snooze_menu = None
            return

        dock = getattr(self, "quick_dock", None)
        anchor = getattr(dock, "snooze_btn", None) if dock is not None else None
        if anchor is None or not anchor.winfo_exists():
            return
        pal = self.pal
        menu = ctk.CTkToplevel(self.root)
        menu.overrideredirect(True)
        menu.attributes("-topmost", True)
        card = ctk.CTkFrame(menu, fg_color=pal["surface"], corner_radius=ui_kit.RADIUS_CONTROL,
                            border_width=1, border_color=pal["border"])
        card.pack(fill="both", expand=True)

        def pick(minutes):
            self._start_snooze(minutes)
            menu.destroy()
            self._snooze_menu = None

        for minutes, key in ((5, "hud.snooze.5min"), (20, "hud.snooze.20min"),
                             (40, "hud.snooze.40min"), (60, "hud.snooze.60min")):
            ctk.CTkButton(card, text=tr(key), anchor="w", height=30, width=130,
                         fg_color="transparent", hover_color=pal["surface_alt"],
                         text_color=pal["text"], font=ui_kit.ui(11),
                         command=lambda m=minutes: pick(m)).pack(fill="x", padx=4, pady=2)
        if getattr(self, "_snooze_job", None) is not None:
            ctk.CTkButton(card, text=tr("hud.snooze.cancel"), anchor="w", height=30, width=130,
                         fg_color="transparent", hover_color=pal["danger"],
                         text_color=pal["text"], font=ui_kit.ui(11),
                         command=lambda: (self._cancel_snooze(), menu.destroy(),
                                          setattr(self, "_snooze_menu", None))
                         ).pack(fill="x", padx=4, pady=(2, 4))

        # Position only NOW, when the menu is filled: before the items are
        # packed winfo_reqheight() equals 1 and the menu would be aligned
        # completely off.
        menu.update_idletasks()
        x = anchor.winfo_rootx() + anchor.winfo_width() + 6
        y = anchor.winfo_rooty() + anchor.winfo_height() - menu.winfo_reqheight()
        menu.geometry(f"+{x}+{max(0, y)}")

        menu.bind("<FocusOut>", lambda _e: self.root.after(120, self._close_snooze_menu))
        # A click elsewhere in the main window closes the menu. We bind once
        # per app run (not on every open), the handler itself does nothing when
        # the menu is not open - so nothing has to be unbound and bindings do
        # not pile up.
        if not getattr(self, "_snooze_click_bound", False):
            self.root.bind("<ButtonRelease-1>", self._on_click_outside_snooze, add="+")
            self._snooze_click_bound = True
        menu.focus_force()
        self._snooze_menu = menu

    def _close_snooze_menu(self):
        """Closes the snooze menu when the player switched to ANOTHER APP
        (FocusOut).

        The condition `focus_get() is None` means "no widget of THIS app has
        focus". It looks too loose, but a stricter criterion ("focus is not in
        the menu") does NOT WORK here: the menu is an overrideredirect Toplevel
        and its `focus_force()` does not keep focus on Windows - FocusOut
        arrives right after opening and the menu would vanish before the player
        even noticed it (verified live, it closed within 150 ms).

        A click elsewhere INSIDE the app window is therefore handled by
        `_on_click_outside_snooze`, not by this method."""
        menu = getattr(self, "_snooze_menu", None)
        if menu is not None and menu.winfo_exists():
            try:
                if self.root.focus_get() is None:
                    menu.destroy()
                    self._snooze_menu = None
            except Exception:
                pass

    def _on_click_outside_snooze(self, _event=None):
        """A click anywhere in the main window closes an open snooze menu.

        The menu is a separate Toplevel, so clicks IN IT never get here at
        all - this handler only sees clicks into the main window, i.e. exactly
        the ones "outside the menu".

        Bound to <ButtonRelease-1>, NOT <Button-1>, and that matters: CTkButton
        runs its command only on release and the widget binding runs BEFORE the
        window binding. So a click on 😴 first goes through
        `_toggle_snooze_menu` (which closes the menu) and by the time it gets
        here it is None. If this hung on <Button-1>, the press would close the
        menu and the following release on the button would open it again right
        away - a second click on 😴 would never close the menu."""
        menu = getattr(self, "_snooze_menu", None)
        if menu is None or not menu.winfo_exists():
            return
        try:
            menu.destroy()
        except Exception:
            pass
        self._snooze_menu = None

    def test_hud(self):
        """Shows the HUD even when it is off, so the player can check its
        position against their game's HUD. Hides it again after 4 seconds."""
        was_enabled = self.hud_config["enabled"]
        self.hud.configure(enabled=True)
        if not was_enabled:
            self.root.after(4000, lambda: self.hud.configure(
                enabled=self.hud_config["enabled"]))

    def on_monitor_target_change(self, target):
        """Switching the target monitor for the visuals and the HUD."""
        self.monitor_target = normalize_monitor_target(target)
        self.overlay_manager.set_monitor_target(self.monitor_target)
        self.hud.configure(monitor_target=self.monitor_target)
        self.save_settings()
        self.log(tr("log.monitor_target", target=self._monitor_label(self.monitor_target)))

    def _monitor_label(self, target):
        if target == "auto":
            return tr("overlay.monitor.auto")
        if target == "cursor":
            return tr("overlay.monitor.cursor")
        if target == "primary":
            return tr("overlay.monitor.primary")
        found = display.monitors(self.root)
        idx = int(target) if str(target).isdigit() else 0
        if 0 <= idx < len(found):
            return found[idx].label(idx)
        return tr("overlay.monitor.auto")

    def monitor_choices(self):
        """[(label, value)] for the monitor-choice dropdown."""
        options = [(tr("overlay.monitor.auto"), "auto"),
                   (tr("overlay.monitor.cursor"), "cursor"),
                   (tr("overlay.monitor.primary"), "primary")]
        for i, mon in enumerate(display.monitors(self.root)):
            options.append((mon.label(i), str(i)))
        return options

    def _refresh_hud_session_text(self):
        stats = self.hr_stats
        elapsed = int(max(0.0, time.time() - stats.session_start))
        parts = [f"{elapsed // 60:02d}:{elapsed % 60:02d}",
                 self._game_text("hud.session.triggers", n=stats.triggers)]
        if stats.time_over >= 1.0:
            # from one hour on "1 h 15 min", not "75:12" - in the GAME language
            # (0.3 4b)
            parts.append(self._game_text(
                "hud.session.over",
                time=ui_kit.cas_text(int(stats.time_over), preklad=self._game_text)))
        self.hud.set_session_text("  ·  ".join(parts))

    # ---------- In-Game Visuals (Overlay) ----------

    def _watch_pulse_state(self):
        """State of the heart-rate indicator in the sidebar:
        (connected, waiting_for_heart_rate, zone, beat_phase).

        The phase comes from `HeartStats.beat_phase()` - from the same source
        as the heart on the in-game HUD, so both beat together. A fixed
        animation (e.g. once a second) is a common mistake: the indicator would
        then show a different heart rate than the one the watch really reports.
        """
        if not self.hr_monitoring_enabled:
            # The sensor is off - drop the held zone as well, otherwise after
            # being switched back on the indicator would flash for 1.5 s with
            # the OLD zone from the previous session (the hysteresis would hold
            # e.g. red, although the player has cooled down in the meantime).
            self._watch_zone = None
            self._watch_zone_cakajuce = None
            return False, False, None, 0.0
        stats = self.hr_stats
        bpm = getattr(stats, "last_bpm", None)
        if not bpm:
            # The sensor is running, but no data comes in (not yet arrived, or
            # the watch dropped out). We drop the zone for the same reason as
            # above.
            self._watch_zone = None
            self._watch_zone_cakajuce = None
            return True, True, None, 0.0

        # During calibration the HUD and Today show "kalibrujem…"
        # (calibrating…) - the indicator must not show a zone alongside that.
        # Neutral colour, the heartbeat goes on. The same for a few samples
        # after the heart rate comes back (`is_settling`): the load ramps up
        # from zero and green would claim a calm the app does not know about.
        if (getattr(stats, "is_calibrating", False)
                or getattr(stats, "is_settling", False)):
            nove = "neutral"
        else:
            # The same zone as the HUD and Today - computed only in
            # `HeartStats.zone`.
            nove = stats.zone
        teraz = time.monotonic()
        drzane = getattr(self, "_watch_zone", None)
        if nove != getattr(self, "_watch_zone_cakajuce", None):
            self._watch_zone_cakajuce = nove
            self._watch_zone_od = teraz
        if drzane is None:
            # the first zone after connecting is taken AT ONCE, not after the
            # hysteresis - otherwise the indicator would start in a random zone
            self._watch_zone = nove
        elif (nove != drzane
              and teraz - getattr(self, "_watch_zone_od", teraz) >= self.WATCH_ZONE_HOLD_S):
            self._watch_zone = nove
        return True, False, self._watch_zone, stats.beat_phase()

    def open_watch_pairing(self, on_close=None):
        """The watch icon SWITCHES ON and opens the panel. It cannot switch the
        sensor off (§1.10).

        `on_close` is called once after the pairing guide is closed - the first
        start then runs the app tour, and the tour continues from it with the
        next step.

        Before, it only opened the dialog. When the sensor was off, the player
        got the pairing panel on top of a switched-off sensor: they followed
        it, the app received nothing and nowhere did it say why. Now a click
        means "I want this", so the sensor is switched on right away.

        Switching off stays where it was - the switch in the settings. An icon
        that switches on once and off another time is unreadable with one
        pictogram and no label: the player does not know whether a click
        switches on or off until they click.

        All callers are behind a player's click - two of them only after the
        player chose "Pair a watch now" in the introduction (first start in
        `__init__`, `replay_onboarding`), one is the button in the tour bubble.
        So the app never switches the sensor on by itself.
        """
        self._enable_hr_monitoring()
        WatchPairingDialog(self, on_close=on_close)

    def _enable_hr_monitoring(self):
        """Switches the heart-rate sensor on if it is not running yet. Returns
        True if it really got switched on.

        When it is already running, it DOES NOTHING - the
        `start_heart_rate_monitor` call resets the session
        (`hr_stats.reset_session`), so calling it on a running session
        would throw away an evening of collected data just because the
        player opened the pairing panel.
        """
        if self.hr_monitoring_enabled:
            return False
        self.hr_monitoring_enabled = True
        # The switch in the settings exists only once that page has been built.
        if self.hr_enabled_var is not None:
            try:
                self.hr_enabled_var.set(True)
            except Exception:
                pass
        self.save_settings()
        self.start_heart_rate_monitor()
        self._refresh_nav_badges()
        return True

    def open_overlay_settings(self):
        OverlaySettingsDialog(self)

    def on_overlay_config_change(self, index, **kwargs):
        if not (0 <= index < len(self.overlay_configs)):
            return
        cfg = self.overlay_configs[index]
        if "enabled" in kwargs:
            cfg["enabled"] = bool(kwargs["enabled"])
            if index == 3 and cfg["enabled"]:
                # the breathing circle is on again - we may remind the player
                # of the tip about a switched-off visual if they switch it off
                # again
                self._hr_overlay_warned = False
        if "scale" in kwargs:
            cfg["scale"] = clamp_float(kwargs["scale"], 0.5, 2.0, cfg["scale"])
        if "pos" in kwargs:
            pos_x, pos_y = kwargs["pos"]
            cfg["pos_x"] = clamp_float(pos_x, 0.0, 100.0, cfg["pos_x"])
            cfg["pos_y"] = clamp_float(pos_y, 0.0, 100.0, cfg["pos_y"])
        if "color" in kwargs:
            # None / "" = theme colour; otherwise a validated #rrggbb
            cfg["color"] = normalize_overlay_config({"color": kwargs["color"]},
                                                    index)["color"]
        self.overlay_manager.configure(index, enabled=cfg["enabled"], scale=cfg["scale"],
                                       pos=(cfg["pos_x"], cfg["pos_y"]),
                                       color=cfg["color"] or "")
        self.save_settings()
        if "enabled" in kwargs:
            # A cue with its in-game picture off is not prepared
            # (`_slot_na_pripravu`) - just like a disabled cue
            # (`SlotCard.on_enabled_change`): with the picture turned on it has
            # to be prepared (right away outside a game, otherwise after the
            # game), after switching off the rest of a running preparation no
            # longer sends its text. Size, position and colour have no effect
            # on what is sent - they do not cancel the preparation.
            self.schedule_pregenerate(200)

    def on_breath_seconds_change(self, inhale=None, exhale=None):
        """Inhale/exhale length of the breathing circle (in seconds) - the
        slider in "In-Game Visuals" at the Breath slot."""
        new_inhale = self.breath_inhale_s if inhale is None else inhale
        new_exhale = self.breath_exhale_s if exhale is None else exhale
        self.breath_inhale_s, self.breath_exhale_s = normalize_breath_seconds(
            new_inhale, new_exhale)
        self.overlay_manager.set_breath_seconds(self.breath_inhale_s, self.breath_exhale_s)
        self.save_settings()

    def on_high_hr_ring_change(self, enabled=None, bpm=None):
        """The ring at high heart rate (off by default) - the switch and the
        limit on the Breath card in "In-game pictures" (the switch also on
        Today's quick row). Applies at once: the next tick
        (`_tick_high_hr_ring`, within a quarter of a second) starts the
        ring, or lets a running one finish breathed out."""
        if enabled is not None:
            self.high_hr_ring = bool(enabled)
        if bpm is not None:
            self.high_hr_ring_bpm = normalize_high_hr_ring_bpm(bpm)
        # The quick row on Today shows the same setting: its switch follows
        # the one in the dialog (`.set()` does not call the CTkSwitch's
        # command, so it does not recurse) and its label the limit.
        var = getattr(self, "high_hr_ring_quick_var", None)
        if var is not None and enabled is not None:
            try:
                var.set(bool(self.high_hr_ring))
            except Exception:
                pass
        label = getattr(self, "high_hr_ring_quick_label", None)
        if label is not None and bpm is not None:
            try:
                label.configure(text=self._high_hr_ring_quick_text())
            except Exception:
                pass
        self.save_settings()

    def _high_hr_ring_quick_text(self):
        """Label of the quick row on Today - the limit in it, upper case like
        the HUD row above it."""
        bpm = normalize_high_hr_ring_bpm(getattr(self, "high_hr_ring_bpm", None))
        return tr("dnes.high_hr_ring_quick", bpm=bpm).upper()

    def _overlay_color(self, index):
        """Slot pictogram colour for the UI - custom, or the theme accent."""
        cfg = self.overlay_configs[index]
        return cfg.get("color") or self.pal["accent"]

    def toggle_overlay_test(self, index):
        """Toggles the drag-test mode of a visual.

        The first click shows the visual PERMANENTLY and it can be dragged with
        the mouse; the button changes to "Done". The second click ends the test
        and SAVES the position the player dragged it to. The position comes
        back through the callback set_test_moved_callback ->
        _on_overlay_test_moved.
        """
        # teach the manager where to save the new position after this test ends
        self.overlay_manager.set_test_moved_callback(
            index, lambda px, py, i=index: self._on_overlay_test_moved(i, px, py))
        testing = self.overlay_manager.test(index)
        self._refresh_test_button(index, testing)
        # if testing of another slot was switched on, its button has to be
        # reset
        for i in range(4):
            if i != index:
                self._refresh_test_button(i, self.overlay_manager.is_testing(i))

    def _refresh_all_test_buttons(self):
        """Brings all four Test buttons in line with the real state.

        Call after ending tests in bulk - otherwise a button would keep saying
        "Done" for a visual that is no longer running.
        """
        for index in range(4):
            try:
                self._refresh_test_button(
                    index, self.overlay_manager.is_testing(index))
            except Exception:
                pass

    def _refresh_test_button(self, index, testing):
        btn = getattr(self, "vhre_test_buttons", {}).get(index)
        if btn is None:
            return
        # A test running right now = ON, i.e. the border in `accent` and under
        # it a muted `accent2` fill; otherwise a secondary button
        # (`ui_kit.button`).
        try:
            btn.configure(
                text=tr("overlay.test_done") if testing else tr("overlay.test"),
                fg_color=self.pal["accent2"] if testing else "transparent",
                border_color=self.pal["accent"] if testing else self.pal["control_border"],
                text_color=self.pal["text"])
        except Exception:
            pass

    def _on_overlay_test_moved(self, index, px, py):
        """Visual dragged to a new position - save it to the configuration."""
        cfg = self.overlay_configs[index]
        cfg["pos_x"], cfg["pos_y"] = round(px, 1), round(py, 1)
        self.overlay_manager.configure(index, pos=(cfg["pos_x"], cfg["pos_y"]))
        self.save_settings()
        self._refresh_test_button(index, False)

    def pick_overlay_color(self, index):
        """Opens Zanshin's own pictogram colour picker for the given
        visual.

        Returns a hex colour, DEFAULT (go back to the theme colour =
        color=None), or None on cancel (then nothing changes).
        """
        from color_picker import ask_color, DEFAULT
        current = self._overlay_color(index)
        res = ask_color(self, current, title=tr("overlay.color_title"))
        if res is None:
            return
        self.on_overlay_config_change(index, color=(None if res == DEFAULT else res))
        swatch = getattr(self, "vhre_color_swatches", {}).get(index)
        if swatch is not None:
            try:
                display = self._overlay_color(index)   # None -> theme accent
                swatch.configure(fg_color=display, hover_color=display)
            except Exception:
                pass

    def test_overlay(self, index):
        # kept for backward compatibility (command palette, onboarding)
        self.toggle_overlay_test(index)
