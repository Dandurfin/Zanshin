"""Volby hraca - cast hlavnej appky (DandurfApp z app.py).

PrefsMixin je mixin DandurfApp: app.py ho dedi a cely stav (jazyk, svet,
tema, paleta, hlasitost, profily, widgety) zije na DandurfApp. Tu su len
metody, ktore s nim pracuju cez `self` - mixin nema __init__ ani vlastne
atributy.

Styri sekcie presunute z app.py bez zmeny:
  * prepinanie jazyka - prestavba okna v novom jazyku,
  * prepinanie sveta (hra / praca) - svet, jeho vzhlad a prepinace
    (konstanta ALGORITMUS_SVET ostala v DandurfApp - citaju ju len metody
    v app.py),
  * prepinanie temy - prefarbenie uz postaveneho okna,
  * settings - nacitanie a ulozenie dandurf_settings.json, hlasitost,
    vyvazenie SFX/hlas a lista "Edge TTS chyba".

Pozor v testoch: `load_settings` / `save_settings` citaju SETTINGS_PATH z
tohto modulu - test ho musi presmerovat tu (`app_prefs.SETTINGS_PATH`),
nie na module app.
"""

import json
import os
import tkinter as tk
from tkinter import messagebox

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
from paths import APP_NAME, SETTINGS_PATH, resolve_audio_path
from settings_model import (DEFAULT_AUDIO, DEFAULT_BREATH_EXHALE_S,
                            DEFAULT_BREATH_INHALE_S, DEFAULT_DASHBOARD_STATS,
                            DEFAULT_EDGE_VOICE, DEFAULT_MONITOR_TARGET,
                            ENGINE_EDGE, ENGINE_SAPI, clamp_int, default_hud_config,
                            default_overlay_configs, default_slots, doplnit_kategorie,
                            engine_labels, migrate_slot_text, normalize_breath_seconds,
                            normalize_dashboard_stats, normalize_hud_config,
                            normalize_monitor_target, normalize_overlay_config,
                            normalize_slot, suggested_voice)

from app_spolocne import DEFAULT_SNOOZE_HOTKEY, LABEL_TO_LANG, LANG_NATIVE_LABELS, app_log


class PrefsMixin:
    """Jazyk, svet, tema a nastavenia (mixin DandurfApp)."""

    # ---------- prepinanie jazyka ----------

    @staticmethod
    def _lang_switch_value(code):
        return LANG_NATIVE_LABELS.get(code, LANG_NATIVE_LABELS[LANG_SK])

    def on_lang_switch(self, label):
        code = LABEL_TO_LANG.get(label, LANG_SK)
        if code == self.lang:
            return
        self.lang = code
        set_lang(code)
        # Ak si uzivatel hlas nikdy sam nezmenil, pri prepnuti na jazyk s
        # inym pismom (ja/zh/ru/bg) mu rovno ponukneme hlas toho jazyka -
        # viz settings_model.VOICE_HINTS.
        self.edge_voice_id = suggested_voice(code, self.edge_voice_id)
        self.save_settings()
        was_listening = self.listening
        # Zmena jazyka meni TEXTY, takze sa (na rozdiel od zmeny temy) musi
        # cele okno postavit nanovo cez `_build_ui` - 1300+ widgetov, ktore
        # sa inak pred hracom skladaju po castiach (blikanie). Zmrazime
        # kreslenie na cas prestavby a prekreslime raz na konci.
        ui_kit.freeze_repaint(self.root, True)
        try:
            self._build_ui()
            self.refresh_edge_banner()
            if audio_engine.EDGE_AVAILABLE:
                # popisy hlasov (zena/muz) su v jazyku rozhrania
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
        # Pregeneracia Edge TTS nie je UI - az po odmrazeni okna.
        if self.engine == ENGINE_EDGE:
            self.pregenerate()

    # ---------- prepinanie sveta (hra / praca) ----------

    @staticmethod
    def _world_label(world):
        """'play'/'work' -> "Hra"/"Praca" v jazyku rozhrania."""
        return tr("world.work") if world == "work" else tr("world.play")

    def _world_labels(self):
        return [self._world_label("play"), self._world_label("work")]

    def _on_world_label(self, label):
        """Klik na segment "Hra | Praca" (lista hore aj Nastavenia)."""
        self.set_world("work" if label == self._world_label("work") else "play")

    def set_world(self, world):
        """Prepne svet: vzhlad, historiu, postrehy. BEZIACU RELACIU NIE.

        Vzhlad ide cez `on_theme_switch` - prefarbenie bez prestavby okna,
        vratane HUD-u a vizualov v hre (v rohu oka to trochu blikne, s tym
        sa pocita). Detail v Historii je index do zoznamu relacii sveta,
        takze sa nuluje. Postrehy druheho sveta sa zahodia a prepocitaju.

        Otvorena relacia ostava vo svete, v ktorom zacala
        (`_session_world`), aj s tym, ci smie mat hlas - prezriet si
        pracovne statistiky uprostred hry teda hru neprepise na pracu.
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
        # `on_theme_switch` sam ulozi nastavenia - uz aj s novym svetom.
        self.on_theme_switch(tr(f"theme.{theme_mod.WORLD_THEME[world]}.label"))
        if self.theme_key == tema_pred:
            self.save_settings()
        self._sync_world_switches()
        app_log.info("svet prepnuty na %s", world)
        try:
            self._refresh_history_page()
        except Exception:
            app_log.exception("historia: prekreslenie po prepnuti sveta zlyhalo")
        self._refresh_dnes_stats()
        self.run_hr_analysis()
        # V Praci hlaska nehovori, takze sa pre nu nic nepripravuje
        # (`_hlasky_hovoria`); po navrate do Hry sa hlasky dopripravia.
        self.schedule_pregenerate(200)

    def _sync_world_switches(self):
        """Oba prepinace sveta (lista, Nastavenia) ukazu aktualny svet.

        CTkSegmentedButton si vybrany segment nezmeni sam, ked svet prepne
        nieco ine nez klik priamo naň."""
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

    # ---------- prepinanie temy ----------

    def on_theme_switch(self, label):
        """Prepne temu PREFARBENIM uz postaveneho okna, nie prestavbou.

        Predtym sa volalo `_build_ui()`, ktore znicilo a odznova postavilo
        vsetko: odmerane 1374 widgetov, 101 878 volani Tk a **2,97 s**
        blokovania, pocas ktorych sa okno pred hracom skladalo po castiach
        (29 roznych medzistavov). Ziadne jedno pomale miesto tam nebolo -
        je to holy objem, kazdy CustomTkinter widget sa kresli na vlastne
        platno.

        Farby su jediné, co sa pri zmene temy meni (texty ostavaju), takze
        staci prejst strom a prepisat ich - viz `theme_recolor`.

        Keby prefarbenie z akehokolvek dovodu zlyhalo, padne sa spat na
        povodnu prestavbu: radsej pomale a spravne nez rychle a rozbite.

        Od 0.2 (B3-worlds) tema patri svetu - vola sa cez `set_world`, nie
        priamo; inak by sa vzhlad a svet rozisli (pri dalsom starte by tema
        aj tak nasledovala svet).
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
        """Prepise farby celeho okna bez toho, aby sa cokolvek znicilo."""
        mapa = theme_recolor.build_color_map(stara_pal, nova_pal)
        ui_shell.set_theme_pal(nova_pal)
        self.root.configure(fg_color=nova_pal["bg"])
        # HUD a in-game vizualy su samostatne Toplevel okna s vlastnou
        # cestou na zmenu temy (overlay_manager.set_palette / hud.set_style
        # vyssie) - do prefarbenia stromu ich nepustame.
        theme_recolor.recolor_tree(self.root, mapa, skip=(tk.Toplevel,))

        # Co sa prefarbit NEDA, lebo je to obrazok alebo vlastna kopia
        # palety - kazdy taky prvok ma svoj `set_pal()`.
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

        # Grafy a karty statistik: `recolor_tree` vie prepisat VOLBY
        # widgetu, ale nie to, co uz lezi na platne - ciara by ostala v
        # starej farbe, kym ju nieco neprekresli. Zivy graf sa zahoji sam
        # pri najblizsej vzorke tepu, graf v Historii stoji.
        # KamaeBar tu chybal. Nie je to `PalCanvas`, ale holy `tk.Canvas`, a
        # kresli sa z vlastnej `self.pal` - po prepnuti temy tak ostaval hnedy
        # plat so zlatou linkou v indigovom okne. Je to hlavicka stranky Dnes,
        # cize prva vec, ktoru po prepnuti vidno.
        for widget in self._najdi_widgety((ui_kit.PalCanvas, ui_kit.StatCard,
                                           ui_kit.QrReveal, ui_kit.KamaeBar)):
            try:
                widget.set_pal(nova_pal)
            except Exception:
                app_log.exception("set_pal zlyhal na %r", widget)

        # Stred stranky Dnes je tk.Canvas s vlastnou kresbou (dojo + enso +
        # text) - rovnaky pripad ako KamaeBar: `recolor_tree` prepise nanajvys
        # OPTION `bg`, ale nie to, co lezi na platne. Enso je navyse OBRAZOK
        # (farba zapecena), takze si pyta explicitny `set_pal`, ktory zaroven
        # zahodi cache snimok a prekresli cely stred v novej teme (`_emit` ->
        # `_refresh_dnes_backdrop`). `self.enso` je `_EnsoHero`, nie widget,
        # takze ho `_najdi_widgety` nenajde.
        try:
            if getattr(self, "enso", None) is not None:
                self.enso.set_pal(nova_pal)
        except Exception:
            app_log.exception("set_pal zlyhal na ense (stred Dnes)")

        # `ui_kit.Collapsible` ZVLAST a so `zostup=True`.
        #
        # Farbu hlavicky si pocita z vlastnej palety az v okamihu rozbalenia,
        # takze rozbalena sekcia by po prepnuti temy svietila prizvukom zo
        # starej. Do zoznamu vyssie ho ale dat NEMOZNO: ten sa do najdeneho
        # widgetu uz nezanara a Collapsible by tienil vsetko, co v nom lezi -
        # graf vlozeny do zabalenej sekcie by ostal v starej teme.
        # Jeho vlastny `set_pal` sa deti nedotyka, takze zostup nic nepokazi.
        for widget in self._najdi_widgety((ui_kit.Collapsible,), zostup=True):
            try:
                widget.set_pal(nova_pal)
            except Exception:
                app_log.exception("set_pal zlyhal na %r", widget)

        # Prepinac sveta (predtym temy) si sam od seba nezmeni vybrany
        # segment, ked svet zmeni nieco ine nez klik naň (lista hore vs.
        # Nastavenia, sprievodca). Pri prestavbe to riesi `.set()` v
        # `_build_ui`, tu ho musime zavolat sami - inak by prepinac
        # ukazoval stary svet, hoci appka uz bezi v novom.
        self._sync_world_switches()

        self._redraw_dnes_preview(nova_pal)

    def _najdi_widgety(self, triedy, zostup=False):
        """Widgety danych tried v okne (bez samostatnych Toplevel okien).

        `zostup=False` sa pri najdenom widgete dalej nezanara - jeho
        `set_pal` si potomkov prefarbi sam. StatCard si tak prefarbi svoj
        mikrograf a netreba ho hladat zvlast.
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
        """Klavesy spustacov - maju vlastny `set_pal`, lebo v teme Sumi ma
        `keycap_text` tu istu hodnotu ako `accent` a mechanicka mapa by im
        dala akcent (viz theme_recolor)."""
        return self._najdi_widgety(ui_kit.Keycap)

    def _redraw_dnes_preview(self, pal):
        """Nahlad HUD na stranke Dnes je PIL obrazok - prekresli sa."""
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
        # Jazyk sa zisti hned na zaciatku - ukazkove sloty pre nove
        # instalacie musia byt uz vygenerovane v spravnom jazyku.
        #
        # POZN: tu stalo natvrdo `LANG_SK`. Appku si stiahne aj
        # Nemec alebo Japonec a pri prvom spusteni na neho vyskoci
        # slovencina - vratane tlacidla "Sparovat hodinky", ktore je
        # prvym krokom onboardingu. Prva instalacia teraz berie jazyk
        # Windowsu a ked ho nepozname, anglictinu.
        lang = system_lang()
        loaded = None
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                # POZN: tu stalo `in (LANG_SK, LANG_EN, LANG_JA)` - zoznam
                # z cias, ked appka vedela tri jazyky. Prepinac v
                # Nastaveniach ich medzitym ponuka DEVAT a volbu korektne
                # ulozi, ale tento filter ju pri dalsom starte zahodil a
                # spadol spat na slovencinu. A kedze `__init__` hned po
                # starte vola `save_settings()`, zdegradovana hodnota sa
                # zapisala spat do suboru - volba hraca bola nenavratne
                # prec. Overene: zh, ru, es, de, fr, pt sa stratili vsetky,
                # prezili len sk/en/ja. Porovnavaj vzdy voci `LANGUAGES`,
                # nie voci rucne prepisanej trojici.
                if loaded.get("lang") in LANGUAGES:
                    lang = loaded["lang"]
            except Exception:
                app_log.exception("load_settings: nepodarilo sa precitat/parsovat %s "
                                  "- pouzijem predvolene nastavenia", SETTINGS_PATH)
                loaded = None
        set_lang(lang)

        default_profile_name = tr("profile.default_name")
        data = {
            "profiles": [{"name": default_profile_name, "slots": default_slots()}],
            "active_profile": default_profile_name,
            # cooldown / rate / volume / balance / overlap - viz
            # settings_model.DEFAULT_AUDIO (to iste pouziva aj tlacidlo
            # "Vratit odporucane" na stranke Zvuk)
            **DEFAULT_AUDIO,
            "voice_id": "",
            "engine_pref": ENGINE_EDGE,
            # Prvy start: bulharsky (japonsky, cinsky, rusky) Windows dostane
            # hlas svojho jazyka - predvolene hlasky su v jeho pisme.
            "edge_voice": suggested_voice(lang),
            "theme": theme_mod.DEFAULT_THEME,
            # Svet (B3-worlds). Novy hrac zacina v Hre - je to appka pre
            # hracov; hlavny svet si vyberie v onboardingu (krok 4).
            "world": hr_stats.WORLD_DEFAULT,
            # Styl hlasky (hlas / zvuk bez slov / len obraz). Urcuje vrchol
            # rebrika hlasky (`rebrik.py`); chybajuci kluc = hlas.
            "cue_style": rebrik.STYL_HLAS,
            "first_run": True,
            "tour_seen": False,
            "tour_step": 0,
            # Anglictina aj pre slovenske rozhranie: HUD a popisky v hre
            # koncia na streame a na screenshotoch v obchode.
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
            "background_opacity": background.DEFAULT_OPACITY,
            "monitor_target": DEFAULT_MONITOR_TARGET,
            "hud_config": default_hud_config(),
            "dashboard_stats": list(DEFAULT_DASHBOARD_STATS),
            "breath_inhale_s": DEFAULT_BREATH_INHALE_S,
            "breath_exhale_s": DEFAULT_BREATH_EXHALE_S,
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
                        # Profil bez slotov dostane styri kategorie - pridat
                        # si ich hrac uz nema ako (tlacidlo je prec).
                        profiles.append({"name": name,
                                         "slots": pslots or [normalize_slot(s)
                                                             for s in default_slots()]})
                if not profiles:
                    # migracia zo starej plochej schemy (Dandurf/pred-profilova verzia)
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
                    # migracia zo stareho jednoducheho prepinaca (len dychovy
                    # kruh, slot 4) - ostatne 3 nove vizualy ostanu vypnute.
                    cfgs = default_overlay_configs()
                    cfgs[3]["enabled"] = bool(loaded.get("breathing_overlay_enabled", False))
                    data["overlay_configs"] = cfgs
                data["hr_ip"] = str(loaded.get("hr_ip") or ANY_INTERFACE)
                # 65432 bol stary predvoleny port z cias, ked prijimac vedel
                # len UDP. Appky pre OBS (vratane HeartRateOnStream) chodia na
                # 4455, takze na tom starom porte by hrac cakal donekonecna -
                # jednorazovo ho presunieme na funkcny predvoleny.
                stored_port = clamp_int(loaded.get("hr_port"), 1, 65535, HR_DEFAULT_PORT)
                data["hr_port"] = HR_DEFAULT_PORT if stored_port == 65432 else stored_port
                data["hr_monitoring_enabled"] = bool(loaded.get("hr_monitoring_enabled", False))
                data["zanshin_graduated"] = bool(loaded.get("zanshin_graduated", False))
                _zg = loaded.get("zanshin_graduated_at")
                data["zanshin_graduated_at"] = _zg if isinstance(_zg, (int, float)) else None
                # Prazdny retazec = vypnute. Nezmyselna kombinacia sa
                # ticho vrati na predvolenu - hrac ju mohol prepisat
                # rucne v JSON a appka kvoli tomu padnut nesmie.
                hk = loaded.get("snooze_hotkey", DEFAULT_SNOOZE_HOTKEY)
                hk = "" if hk in (None, "") else str(hk).strip().lower()
                data["snooze_hotkey"] = (
                    hk if (hk == "" or hotkey.is_valid(hk))
                    else DEFAULT_SNOOZE_HOTKEY)
                # Jemnost pozadia. Strop je v `background.py`, nie tu -
                # kto ho chce zmenit, meni ho na jednom mieste.
                data["background_opacity"] = background.clamp_opacity(
                    loaded.get("background_opacity"))
                data["monitor_target"] = normalize_monitor_target(loaded.get("monitor_target"))
                data["hud_config"] = normalize_hud_config(loaded.get("hud_config"))
                # POZN: tu sa nacitavalo aj "dojo_intensity" (fotopas nad
                # titulkovou listou). Kluc uz nikto necita - v starych
                # dandurf_settings.json moze zostat, len sa ignoruje a pri
                # dalsom ulozeni vypadne.
                data["dashboard_stats"] = normalize_dashboard_stats(loaded.get("dashboard_stats"))
                data["breath_inhale_s"], data["breath_exhale_s"] = normalize_breath_seconds(
                    loaded.get("breath_inhale_s"), loaded.get("breath_exhale_s"))
                # JEDNORAZOVA NAPRAVA: vsetky styri vizualy vypnute.
                #
                # Do 19. 9. boli vypnute PREDVOLENE a `_cue_can_fire` bez
                # zapnuteho vizualu hlasku nepusti - appka teda v tomto stave
                # mlci a hrac nema ako zistit preco. Nikto si to takto
                # nezvolil, vzniklo to predvolbou, tak to raz narovname.
                #
                # NAOZAJ RAZ (0.2). Predpoklad "kto si ich vypne sam, ma aspon
                # jeden zapnuty" neplatil - UI dovoli vypnut vsetky styri, a
                # appka ich potom pri KAZDOM starte zapla spat, hoci log
                # slubil, ze sa vypnut daju. Po prvom nacitani sa do nastaveni
                # zapise `visuals_repaired` a dalej je vypnutie rozhodnutie
                # hraca, ktore appka neobchadza.
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
                # Ulozena tema je ZNACKA "prvy start uz bol" - tak to aj
                # ostava; samotny vzhlad uz ale urcuje svet (nizsie).
                if loaded.get("theme") in (theme_mod.ZEN, theme_mod.MODERN):
                    data["theme"] = loaded["theme"]
                    data["first_run"] = False
                # SVET (B3-worlds). Chybajuci alebo nezmyselny -> Hra.
                # MIGRACIA: nastavenia zo starsej verzie svet nemaju, a to aj
                # ked mal hrac vybrane Aizome. Svet sa z temy NEODVODZUJE -
                # inak by sa mu hranie zacalo ratat ako praca; ide do Hry a
                # tema ide za svetom (rozhodnutie zadavatela).
                data["world"] = (hr_stats.normalize_activity(loaded.get("world"))
                                 or hr_stats.WORLD_DEFAULT)
                data["cue_style"] = rebrik.normalize_cue_style(loaded.get("cue_style"))
            except Exception:
                app_log.exception("load_settings: castocne poskodeny/neocakavany "
                                  "obsah %s - pouzijem defaulty pre chybajuce polia",
                                  SETTINGS_PATH)
        # Vzhlad patri svetu - aj po poskodenom subore, aj pri prvom starte.
        data["theme"] = theme_mod.WORLD_THEME.get(data["world"], theme_mod.DEFAULT_THEME)
        for profile in data["profiles"]:
            # Profil s menej nez styrmi slotmi (rucne zalozeny v 0.1, kde sa
            # sloty pridavali tlacidlom, alebo po odstraneni) dostane chybajuce
            # kategorie na koniec, VYPNUTE. Tlacidlo "+ Pridat spustac" je
            # prec, takze inak by sa kategoria do profilu uz nedala vratit.
            profile["slots"] = doplnit_kategorie(profile["slots"])
            for index, slot in enumerate(profile["slots"]):
                # Stare predvolene slovo ("Teeth", ja 脱力, zh 放松) -> nove.
                # Len pri nacitani, viz `settings_model.migrate_slot_text`.
                slot["text"] = migrate_slot_text(slot["text"], index)
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
            # `theme` sa uklada dalej: je to znacka "prvy start uz bol"
            # (`load_settings`). Pri starte ju aj tak prepise svet.
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
            "hr_monitoring_enabled": bool(self.hr_monitoring_enabled),
            "zanshin_graduated": bool(self.zanshin_graduated),
            "zanshin_graduated_at": self.zanshin_graduated_at,
            "snooze_hotkey": self.snooze_hotkey,
            "background_opacity": self.background_opacity,
            "monitor_target": self.monitor_target,
            "hud_config": self.hud_config,
            "dashboard_stats": list(self.dashboard_stats),
            "breath_inhale_s": float(self.breath_inhale_s),
            "breath_exhale_s": float(self.breath_exhale_s),
            # Jednorazova naprava vypnutych vizualov uz prebehla (alebo
            # nebola treba) - viz `load_settings`. Odteraz su vypnute
            # vizualy volba hraca.
            "visuals_repaired": True,
        }
        try:
            # Atomicky zapis: najprv .tmp, az potom os.replace() - rovnaky
            # vzor ako uz appka pouziva v sfx_assets._save_wav()/_try_download().
            # Bez tohto by pad/vypadok POCAS zapisu (a uklada sa pri kazdej
            # zmene slidera!) mohol nechat prazdny/orezany JSON a s nim aj
            # stratu vsetkych profilov pri buducom starte.
            tmp_path = f"{SETTINGS_PATH}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, SETTINGS_PATH)
        except Exception as exc:
            self.log(tr("log.settings_save_error", err=exc))
            app_log.exception("save_settings zlyhalo")


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
            messagebox.showwarning(
                APP_NAME,
                tr("msgbox.edge_still_missing", err=audio_engine.EDGE_IMPORT_ERROR))
