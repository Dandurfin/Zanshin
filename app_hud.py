"""HUD a in-game vizualy - cast hlavnej appky (DandurfApp z app.py).

HudMixin je mixin DandurfApp: app.py ho dedi a cely stav (HUD okno a jeho
konfiguracia, overlay manager a konfiguracia vizualov, cielovy monitor,
jazyk hry, dlzka dychu, senzor tepu) zije na DandurfApp. Tu su len metody,
ktore s nim pracuju cez `self` - mixin nema __init__ ani vlastne atributy.

Tri sekcie presunute z app.py bez zmeny:
  * Panel v hre so 4 zakladnymi funkciami (HUD trigger row) - riadok ikon
    pod HUD panelom v hre,
  * HUD (zivy panel so statistikou tepu) - jazyk a popisky toho, co appka
    kresli do hry, konfiguracia HUD-u, vyber monitora a text relacie;
    sekcia nesie aj male menu dlzky stisenia (`_toggle_snooze_menu`), ktore
    v nej bolo uz v app.py,
  * In-Game Vizualy (Overlay) - kontrolka tepu v bocnom paneli, parovanie
    hodiniek (zapnutie senzora), konfiguracia, farba a test vizualov.

Konstanta `WATCH_ZONE_HOLD_S` (hysterezia kontrolky tepu) ostala v triede
DandurfApp medzi ostatnymi konstantami triedy - `_watch_pulse_state` ju
cita cez `self`.

Pozor v testoch: `_watch_pulse_state` a `_refresh_hud_session_text` citaju
`time` z tohto modulu - falosne hodiny na module app ich nezasiahnu (treba
`app_hud.time`).
"""

import time

import customtkinter as ctk

import display
import ui_kit
from i18n import LANGUAGES, LANG_EN, LANG_SAME_AS_APP, tr, tr_lang
from settings_model import (clamp_float, normalize_breath_seconds,
                            normalize_hud_config, normalize_monitor_target,
                            normalize_overlay_config)
from ui_dialogs import OverlaySettingsDialog, WatchPairingDialog

from app_spolocne import LABEL_TO_LANG, LANG_NATIVE_LABELS


class HudMixin:
    """HUD, riadok 4 funkcii, jazyk hry a in-game vizualy (mixin DandurfApp)."""

    # ---------- Panel v hre so 4 zakladnymi funkciami (HUD trigger row) ----------
    #
    # POZNAMKA K HISTORII: toto boli povodne dve metody pre celoappkovy
    # "Minimalisticky rezim" (zmensoval cele okno appky na 320x160 -
    # `set_minimal_mode`/`_apply_minimal_mode`, teraz odstranene). Rovnaky
    # zoznam 4 funkcii sa ale hodi aj tu - je to ten isty udaj (nazov
    # vizualu + popisok + kombinacia klaves pre sloty 0..3), len teraz
    # kresleny ako riadok pod HUD panelom v hre (`hud_paint.render_hud_
    # trigger_row`), nie ako samostatne okno appky.

    def _sync_hud_trigger_state(self):
        """Zosedivi ikonky, kym je panel s tepom vypnuty.

        Bez toho je to prepinac, ktory sa da zapnut a nic nespravi - a to je
        horsie nez prepinac, ktory sa zapnut neda.
        """
        stav = "normal" if self.hud_config.get("enabled") else "disabled"
        for widget in (getattr(self, "hud_trigger_switch", None),
                       getattr(self, "hud_trigger_swatch", None)):
            try:
                if widget is not None:
                    widget.configure(state=stav)
            except Exception:
                pass

    def _hud_trigger_info(self):
        """[(nazov vizualu, enabled)] pre riadok 4 zakladnych funkcii pod HUD
        panelom - poziciou zodpovedaju self.slots[0..3].

        POPISOK POD IKONKOU TU UZ NIE JE.
        Do 19. 9. sa pod kazdu ikonku kreslil `slot.display_key()`, cize
        'C', 'R', 'Mys: right', 'F'. Boli to klavesy z `DEFAULT_SLOT`, ktore
        od fazy 3 nespustaju nic - appka klavesy vobec necita. Hrac teda
        priamo v hre cital navod, ktory neplatil, a stlacanim tych klaves
        nedosiahol nic.

        Nahradzat ich popiskom nema zmysel: riadok je vysoky par pixelov a
        ma byt periferny. Ikonka je ta ista grafika, ktoru hrac uvidi, ked
        hlaska pride - to staci.
        """
        visuals = ("grounding", "jaw", "release", "breath")
        out = []
        # getattr, nie self.slots priamo: _apply_hud_config() sa vola z
        # __init__ este PRED self.slots = [] (riadok nizsie v __init__),
        # takze pri prvom zavolani atribut este neexistuje vobec.
        slots = getattr(self, "slots", [])
        for i, visual_name in enumerate(visuals):
            enabled = True
            if i < len(slots):
                enabled = bool(getattr(slots[i], "enabled_value", True))
            out.append((visual_name, enabled))
        return out

    def _on_hud_trigger_click(self, index):
        """Klik na ikonu v HUD riadku (len v nahlade v appke, v hre je
        panel click-through - viz hud.StatsHud.handle_click) spusti tu
        istu funkciu, ako keby hrac stlacil priradeny kláves."""
        if 0 <= index < len(self.slots):
            self.fire_slot(self.slots[index], source="hud_panel")

    def _refresh_hud_trigger_row(self):
        """Prekresli zoznam 4 funkcii v HUD paneli - vola sa pri zmene
        slotov (rebind klavesy, zapnutie/vypnutie) aj pri zmene jazyka."""
        hud = getattr(self, "hud", None)
        if hud is None:
            return
        try:
            hud.configure_triggers(triggers=self._hud_trigger_info())
        except Exception:
            pass

    # ---------- HUD (zivy panel so statistikou tepu) ----------

    def _apply_overlay_labels(self):
        """Popisky pod in-game vizualmi + slova dychoveho cyklu.

        Kreslia sa do obrazka, takze pri zmene jazyka ich treba manageru
        podat znova - preto je to samostatna metoda a nie parameter
        konstruktora.
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
        """Prepne jazyk toho, co appka kresli do hry. Prekresli sa hned -
        HUD aj vizualy si popisky drzia ako hotovy obrazok."""
        self.game_lang = LABEL_TO_LANG.get(label, LANG_SAME_AS_APP)
        self.save_settings()
        self._apply_overlay_labels()
        self._apply_hud_labels()
        self.log(tr("log.game_lang", lang=self._game_lang_label(self.game_lang)))

    def _game_text(self, key, **kwargs):
        """Text, ktory appka kresli DO HRY - vlastny jazyk, nie jazyk okna.

        HUD sedi vlavo dole na hernej obrazovke a popisky su pod vizualmi;
        oboje konci na streame a na screenshotoch v obchode, kde to citaju
        aj ludia, ktori jazyk rozhrania nevedia. Predvolena je preto
        anglictina, aj ked appka bezi po slovensky.
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
        """Prenesie ulozenu konfiguraciu HUD-u do bezuceho okna."""
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
            # "" (prazdny retazec) znamena "vrat sa na farbu temy", rovnaka
            # konvencia ako pri farbe piktogramov vizualov (on_overlay_config_change)
            value = kwargs["trigger_color"]
            cfg["trigger_color"] = normalize_hud_config(
                {"trigger_color": value})["trigger_color"] if value else None
        self._apply_hud_config()
        # Zapnutie/vypnutie panela meni, ci maju podriadene ikonky co robit.
        self._sync_hud_trigger_state()
        # Dva prepinace na to iste (v Nastaveniach aj rychly na Dnes) drzime v
        # zhode. `.set()` nezavola command CTkSwitch-a, takze to nerekurzuje.
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
        """Farba vzorky pri "Ukazat panel v hre" - vlastna, alebo akcent
        temy (rovnaka konvencia ako _overlay_color pre 4 vizualy)."""
        return self.hud_config.get("trigger_color") or self.pal["accent"]

    def pick_hud_trigger_color(self):
        """Vyber farby ikoniek v riadku 4 zakladnych funkcii pod HUD
        panelom - rovnaky system-native color picker ako pri vizualoch
        (pick_overlay_color), len ulozeny do hud_config namiesto
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
                display = self._hud_trigger_color_display()   # None -> akcent temy
                swatch.configure(fg_color=display, hover_color=display)
            except Exception:
                pass

    def _toggle_snooze_menu(self):
        """Rozbali/zabali male menu s vyberom dlzky stisenia (5/20/40/60
        min) pri tlacidle 😴 v doku bocneho panela.

        POZOR - TOTO MENU NEMA V 2.1 SPUSTAC. Tlacidlo 😴 odislo s rychlym
        dokom (viz `_build_ui`) a odlozenie sa zapina globalnou skratkou na
        pevnych `SNOOZE_HOTKEY_MINUTES` minut. Volba dlzky tak nie je
        dostupna nikde.

        Kod je NECHANY zamerne, nie prehliadnutim: volba dlzky je prirodzeny
        kandidat na jeden z piatich jednoduchych ovladacov zo zadania §3.1,
        o ktorych sa este nerozhodlo. Ked padne rozhodnutie, staci to
        zavolat odtial; ak sa rozhodne inak, patri to prec.

        Anchor si berie z `quick_dock`, ktory uz neexistuje, takze metoda
        skonci hned na `anchor is None` - nespadne, len nic neurobi.

        Kreslene ako CTkToplevel bez OS ramu (rovnaky vzor ako ostatne
        docasne popup-y v appke), zatvara sa klikom mimo neho alebo
        opakovanym klikom na 😴.

        POZN: menu predtym viselo pod ozubenym kolieskom na stranke V hre.
        Kotvi sa preto teraz VPRAVO od tlacidla, nie pod nim - dok sedi pri
        dolnom okraji okna, takze pod nim uz nie je miesto a menu by
        vyliezlo mimo obrazovky."""
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

        # Poloha az TERAZ, ked je menu naplnene: pred zabalenim poloziek je
        # winfo_reqheight() rovne 1 a menu by sa zarovnalo uplne mimo.
        menu.update_idletasks()
        x = anchor.winfo_rootx() + anchor.winfo_width() + 6
        y = anchor.winfo_rooty() + anchor.winfo_height() - menu.winfo_reqheight()
        menu.geometry(f"+{x}+{max(0, y)}")

        menu.bind("<FocusOut>", lambda _e: self.root.after(120, self._close_snooze_menu))
        # Klik inam v hlavnom okne menu zavrie. Viazeme raz za beh appky
        # (nie pri kazdom otvoreni), obsluha sama nic nerobi, ked menu nie
        # je otvorene - tak netreba nic odviazovat a nehromadia sa vazby.
        if not getattr(self, "_snooze_click_bound", False):
            self.root.bind("<ButtonRelease-1>", self._on_click_outside_snooze, add="+")
            self._snooze_click_bound = True
        menu.focus_force()
        self._snooze_menu = menu

    def _close_snooze_menu(self):
        """Zavrie snooze menu, ked hrac prepol na INU APPKU (FocusOut).

        Podmienka `focus_get() is None` znamena "ziadny prvok TEJTO appky
        nema fokus". Vyzera prilis volne, ale prisnejsie kriterium ("fokus
        nie je v menu") tu NEFUNGUJE: menu je overrideredirect Toplevel a
        jeho `focus_force()` na Windows fokus neudrzi - FocusOut priletí
        hned po otvoreni a menu by zmizlo skor, nez by si ho hrac vobec
        vsimol (overene naživo, zavrelo sa do 150 ms).

        Klik inam VO VNUTRI okna appky preto rieši `_on_click_outside_snooze`,
        nie tato metoda."""
        menu = getattr(self, "_snooze_menu", None)
        if menu is not None and menu.winfo_exists():
            try:
                if self.root.focus_get() is None:
                    menu.destroy()
                    self._snooze_menu = None
            except Exception:
                pass

    def _on_click_outside_snooze(self, _event=None):
        """Klik kamkolvek v hlavnom okne zavrie otvorene snooze menu.

        Menu je samostatny Toplevel, takze kliky V NOM sa sem vobec
        nedostanu - tato obsluha vidi len kliky do hlavneho okna, teda
        presne tie "mimo menu".

        Viazane na <ButtonRelease-1>, NIE <Button-1>, a je to podstatne:
        CTkButton spusta svoj command az na release a vazba widgetu bezi
        PRED vazbou okna. Klik na 😴 teda najprv prejde cez
        `_toggle_snooze_menu` (ktore menu zavrie) a sem uz dojde None.
        Keby to viselo na <Button-1>, press by menu zavrel a nasledny
        release na tlacidle by ho hned znova otvoril - druhy klik na 😴
        by menu nikdy nezavrel."""
        menu = getattr(self, "_snooze_menu", None)
        if menu is None or not menu.winfo_exists():
            return
        try:
            menu.destroy()
        except Exception:
            pass
        self._snooze_menu = None

    def test_hud(self):
        """Ukaze HUD aj ked je vypnuty, aby si hrac overil polohu voci
        HUD-u svojej hry. Po 4 sekundach ho zase schova."""
        was_enabled = self.hud_config["enabled"]
        self.hud.configure(enabled=True)
        if not was_enabled:
            self.root.after(4000, lambda: self.hud.configure(
                enabled=self.hud_config["enabled"]))

    def on_monitor_target_change(self, target):
        """Prepnutie cieloveho monitora pre vizualy aj HUD."""
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
        """[(popisok, hodnota)] pre dropdown vyberu monitora."""
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
            over = int(stats.time_over)
            parts.append(self._game_text("hud.session.over",
                                         time=f"{over // 60}:{over % 60:02d}"))
        self.hud.set_session_text("  ·  ".join(parts))

    # ---------- In-Game Vizualy (Overlay) ----------

    def _watch_pulse_state(self):
        """Stav kontrolky tepu v bocnom paneli:
        (spojene, caka_na_tep, pasmo, faza_tepu).

        Faza ide z `HeartStats.beat_phase()` - z toho isteho zdroja ako
        srdce na HUD-e v hre, takze oba bijú naraz. Pevna animacia (napr.
        raz za sekundu) je bezna chyba: kontrolka by potom ukazovala iny
        tep, nez aky hodinky naozaj hlasia.
        """
        if not self.hr_monitoring_enabled:
            # Senzor je vypnuty - zahod aj drzane pasmo, inak by kontrolka
            # po opatovnom zapnuti bliskala 1,5 s STARYM pasmom z predoslej
            # relacie (hysterezia by drzala napr. cervenu, hoci hrac medzitym
            # vychladol).
            self._watch_zone = None
            self._watch_zone_cakajuce = None
            return False, False, None, 0.0
        stats = self.hr_stats
        bpm = getattr(stats, "last_bpm", None)
        if not bpm:
            # Senzor bezi, ale data nechodia (este neprisli, alebo hodinky
            # vypadli). Pasmo zahadzujeme z rovnakeho dovodu ako vyssie.
            self._watch_zone = None
            self._watch_zone_cakajuce = None
            return True, True, None, 0.0

        # Pocas kalibracie HUD aj Dnes pisu "kalibrujem…" - kontrolka nesmie
        # popri tom svietit pasmom. Neutralna farba, tep bije dalej. To iste
        # par vzoriek po navrate tepu (`is_settling`): zataz sa rozbieha od
        # nuly a zelena by tvrdila pokoj, ktory appka nevie.
        if (getattr(stats, "is_calibrating", False)
                or getattr(stats, "is_settling", False)):
            nove = "neutral"
        else:
            # To iste pasmo ako HUD a Dnes - pocita sa len v `HeartStats.zone`.
            nove = stats.zone
        teraz = time.monotonic()
        drzane = getattr(self, "_watch_zone", None)
        if nove != getattr(self, "_watch_zone_cakajuce", None):
            self._watch_zone_cakajuce = nove
            self._watch_zone_od = teraz
        if drzane is None:
            # prve pasmo po pripojeni sa berie HNED, nie az po hysterezii -
            # inak by kontrolka zacala v nahodnom pasme
            self._watch_zone = nove
        elif (nove != drzane
              and teraz - getattr(self, "_watch_zone_od", teraz) >= self.WATCH_ZONE_HOLD_S):
            self._watch_zone = nove
        return True, False, self._watch_zone, stats.beat_phase()

    def open_watch_pairing(self):
        """Ikona hodiniek ZAPINA a otvara panel. Vypnut sa nou neda (§1.10).

        Predtym len otvarala dialog. Ked bol senzor vypnuty, hrac tak dostal
        parovaci panel nad vypnutym senzorom: postupoval podla neho, appka
        nic neprijala a nikde nestalo preco. Teraz klik znamena "chcem to",
        cize sa senzor rovno zapne.

        Vypinanie zostava tam, kde bolo - prepinac v nastaveniach. Ikona,
        ktora raz zapne a inokedy vypne, je pri jednom piktograme bez
        popisku necitatelna: hrac nevie, ci klikom zapina alebo vypina, kym
        neklikne.

        Vsetkych pat volajucich je za klikom hraca - dve z nich az po tom,
        co si v onboardingu vybral "Sparovat hodinky teraz" (app.py:406,
        2336). Appka teda senzor nezapne nikdy sama od seba.
        """
        self._enable_hr_monitoring()
        WatchPairingDialog(self)

    def _enable_hr_monitoring(self):
        """Zapne senzor tepu, ak este nebezi. Vrati True, ak sa naozaj zapol.

        Ked uz bezi, NEROBI NIC - `start_heart_rate_monitor` vynuluje
        relaciu (`hr_stats.reset_session`), takze zavolat ho na beziacej
        relacii by zahodilo vecer nazbieranych dat len preto, ze hrac
        otvoril parovaci panel.
        """
        if self.hr_monitoring_enabled:
            return False
        self.hr_monitoring_enabled = True
        # Prepinac v nastaveniach existuje az po postaveni tej stranky.
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
                # dychaci kruh je zas zapnuty - radu o vypnutom vizuali
                # smieme hracovi pripomenut, ak si ho znova vypne
                self._hr_overlay_warned = False
        if "scale" in kwargs:
            cfg["scale"] = clamp_float(kwargs["scale"], 0.5, 2.0, cfg["scale"])
        if "pos" in kwargs:
            pos_x, pos_y = kwargs["pos"]
            cfg["pos_x"] = clamp_float(pos_x, 0.0, 100.0, cfg["pos_x"])
            cfg["pos_y"] = clamp_float(pos_y, 0.0, 100.0, cfg["pos_y"])
        if "color" in kwargs:
            # None / "" = farba temy; inak overeny #rrggbb
            cfg["color"] = normalize_overlay_config({"color": kwargs["color"]},
                                                    index)["color"]
        self.overlay_manager.configure(index, enabled=cfg["enabled"], scale=cfg["scale"],
                                       pos=(cfg["pos_x"], cfg["pos_y"]),
                                       color=cfg["color"] or "")
        self.save_settings()

    def on_breath_seconds_change(self, inhale=None, exhale=None):
        """Dlzka nadychu/vydychu dychoveho kruhu (v sekundach) - slider v
        "In-Game Vizuály" pri slote Dych."""
        new_inhale = self.breath_inhale_s if inhale is None else inhale
        new_exhale = self.breath_exhale_s if exhale is None else exhale
        self.breath_inhale_s, self.breath_exhale_s = normalize_breath_seconds(
            new_inhale, new_exhale)
        self.overlay_manager.set_breath_seconds(self.breath_inhale_s, self.breath_exhale_s)
        self.save_settings()

    def _overlay_color(self, index):
        """Farba piktogramu slotu pre UI - vlastna, alebo akcent temy."""
        cfg = self.overlay_configs[index]
        return cfg.get("color") or self.pal["accent"]

    def toggle_overlay_test(self, index):
        """Prepne drag-test rezim vizualu.

        Prve kliknutie zobrazi vizual NASTALO a da sa tahat mysou; tlacidlo
        sa zmeni na "Hotovo". Druhe kliknutie test ukonci a ULOZI polohu,
        na ktoru ho hrac potiahol. Poloha sa vrati cez callback
        set_test_moved_callback -> _on_overlay_test_moved.
        """
        # nauc manager, kam ulozit novu polohu po skonceni tohto testu
        self.overlay_manager.set_test_moved_callback(
            index, lambda px, py, i=index: self._on_overlay_test_moved(i, px, py))
        testing = self.overlay_manager.test(index)
        self._refresh_test_button(index, testing)
        # ak sa zaplo testovanie ineho slotu, jeho tlacidlo treba vratit
        for i in range(4):
            if i != index:
                self._refresh_test_button(i, self.overlay_manager.is_testing(i))

    def _refresh_all_test_buttons(self):
        """Zosuladi vsetky styri tlacidla Test so skutocnym stavom.

        Volat po hromadnom ukonceni testov - inak by tlacidlo dalej hlasilo
        "Hotovo" pri vizuale, ktory uz nebezi.
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
        try:
            btn.configure(
                text=tr("overlay.test_done") if testing else tr("overlay.test"),
                fg_color=self.pal["accent2"] if testing else "transparent",
                text_color=self.pal["text"] if testing else self.pal["text_dim"])
        except Exception:
            pass

    def _on_overlay_test_moved(self, index, px, py):
        """Vizual bol potiahnuty na novu polohu - uloz ju do konfiguracie."""
        cfg = self.overlay_configs[index]
        cfg["pos_x"], cfg["pos_y"] = round(px, 1), round(py, 1)
        self.overlay_manager.configure(index, pos=(cfg["pos_x"], cfg["pos_y"]))
        self.save_settings()
        self._refresh_test_button(index, False)

    def pick_overlay_color(self, index):
        """Otvori vlastny (Zanshin) vyber farby piktogramu pre dany vizual.

        Vrati hex farbu, DEFAULT (vrat farbu temy = color=None), alebo None
        pri zruseni (vtedy sa nic nemeni).
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
                display = self._overlay_color(index)   # None -> akcent temy
                swatch.configure(fg_color=display, hover_color=display)
            except Exception:
                pass

    def test_overlay(self, index):
        # zachovane pre spatnu kompatibilitu (paleta prikazov, onboarding)
        self.toggle_overlay_test(index)
