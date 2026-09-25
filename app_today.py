"""Stranka Dnes - cast hlavnej appky (DandurfApp z app.py).

TodayMixin je mixin DandurfApp: app.py ho dedi a cely stav (stred stranky
Dnes a enso, spustac hlasky a jeho zaznam, senzor tepu a statistiky
relacie, karty "Moje statistiky" a ich poradie) zije na DandurfApp. Tu su
len metody, ktore s nim pracuju cez `self` - mixin nema __init__ ani
vlastne atributy.

Dve sekcie presunute z app.py bez zmeny:
  * zive dojo (hero prazdneho stavu) - animacia stredu Dnes (enso a dojo
    za nim), veta pod znackou, zivy blok tepu, zataze, stopy relacie a
    pasiem; sekcia nesie aj dorucenie automatickej hlasky
    (`_tick_cue_trigger`, `_cue_can_fire`, `_on_cue_event`,
    `_dalsi_cue_slot`, `_fire_somatic_cue`), prstenec "natiahnute" na
    ense a odznaky v bocnom menu, ktore v nej boli uz v app.py,
  * volitelne statistiky na Dnes ("Moje statistiky") - katalog a hodnoty
    kariet, mriezka, vyber kariet a presun karty potiahnutim.

Konstanty `HERO_PERIOD_S` a `DASHBOARD_DRAG_PX` ostali v triede DandurfApp
medzi ostatnymi konstantami triedy - `_dashboard_drag` cita
`DASHBOARD_DRAG_PX` cez `self`.

Pozor v testoch: `_tick_cue_trigger`, `_refresh_session_trace`,
`_history_cached` a `_dashboard_stat_value` citaju `time` z tohto modulu a
`_fire_somatic_cue` `threading` - falosne hodiny aj synchronne vlakno treba
podstrcit aj tu (`app_today.time`, `app_today.threading`), nie len na
module app.
"""

import threading
import time
import tkinter as tk

import customtkinter as ctk

import hr_stats
import measure
import rebrik
import theme as theme_mod
import trigger
import ui_kit
from i18n import tr
from settings_model import (dashboard_stat_clickable, swap_dashboard_stats,
                            toggle_dashboard_stat)

from app_spolocne import app_log


class TodayMixin:
    """Stred a karty stranky Dnes, dorucenie hlasky (mixin DandurfApp)."""

    # ---------- živé dojo (hero prázdneho stavu) ----------

    def _dnes_anim_active(self):
        """Kresli sa este nieco POHYBLIVE? Uz len ked enso zije alebo je mesiac
        (pocuvanie / promocia). ZASTAVENY stav STOJI - dojo sa uz NEDYCHA, lebo
        prekreslovanie (skoro) identickeho obsahu 8x/s okno preblikavalo. Pas to
        cita rovnako: "inak stoji"."""
        enso = getattr(self, "enso", None)
        return bool(enso is not None and (enso._live or enso._moon))

    def _ensure_dnes_tick(self):
        """Rozbehne animacny tik stredu, ak nebezi a enso sa hybe. Jedine
        miesto (spolu s koncom `_tick_dnes`), kde `_dnes_tick_job` vznika.

        Planuje cez `after` a job nastavi HNED - nie priamym volanim
        `_tick_dnes` (to by cez prekreslenie a spatne `_ensure_dnes_tick`
        zarekurzovalo, kym `_tick_dnes` job na zaciatku drzi vynulovany)."""
        if getattr(self, "_dnes_tick_job", None) is not None:
            return
        if not self._dnes_anim_active():
            return
        try:
            self._dnes_tick_job = self.root.after(self.DNES_TICK_MS, self._tick_dnes)
        except Exception:
            self._dnes_tick_job = None

    def _on_enso_change(self):
        """`_EnsoHero._emit()` sem hlasi zmenu stavu (set_live/armed/graduate/
        set_pal). Prekresli stred a rozbehne tik, ak enso zacalo zit."""
        self._refresh_dnes_backdrop(force=False)
        self._ensure_dnes_tick()

    def _tick_dnes(self):
        """Jeden krok animacie stredu - uz len pre enso (pocuva / mesiac). Dojo
        je staticke, takze sa nehybe; prekreslime canvas a enso vymeni snimku v
        mieste (`itemconfigure`, bez blikania)."""
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
        """Zapne JASNE dojo za ensom (zastaveny stav). Dojo je STATICKE - uz sa
        NEDYCHA (to blikanie preblo). Enso aj text stoja; stred sa prekresli raz
        a potom sa nehybe nic - presne ako to hlasi pas: "inak stoji"."""
        self._dnes_hero_on = True
        # Staticke, ale s prijemnou ziarou (nie na minime) - fixna faza dychu.
        self._dnes_breath_phase = 0.25
        self._refresh_dnes_backdrop(force=True)
        self._ensure_dnes_tick()

    def _stop_dnes_hero(self):
        """Prepne dojo na tlmenu fotku (pocuvanie). Enso môže žiť ďalej (počúva /
        mesiac) - animacny tik sa sam zastavi, ked sa nehybe uz nic."""
        self._dnes_hero_on = False
        self._refresh_dnes_backdrop(force=True)
        self._ensure_dnes_tick()

    def _refresh_dnes_state_text(self):
        """Nadpis a veta pod znackou. Ten isty text ako v dychajucom pase -
        `_kamae_state_text` je jediny zdroj, aby sa nemohli rozist. Text sa
        ulozi a stred sa prekresli (kresli ho `_paint_dnes_canvas`)."""
        if not hasattr(self, "dnes_canvas"):
            return
        try:
            titul, veta = self._kamae_state_text()
            self._dnes_titul = titul
            self._dnes_veta = veta
            self._refresh_dnes_backdrop(force=False)
        except Exception:
            app_log.exception("stav na Dnes: prepis textu zlyhal")

    def _resume_cue_trigger(self):
        """Vedome zdvihne pozastavenie spustaca.

        `resume(force=True)`, lebo bezny `resume()` z `_apply_hr_bpm` zdvihne
        UZ LEN vypadok tepu - snooze ani zastavene pocuvanie zdvihnut nesmie.
        Volat treba VZDY, aj ked sa `start_listening` nezavola: pri snooze
        spustenom v nepocuvajucom stave by inak spustac ostal pozastaveny
        navzdy.

        KYM PLATI "TERAZ NIE", NEZDVIHNE NIC. Od 24. 9. snooze pocuvanie
        nezastavuje, takze `start_listening` (hrac dal stop a start pocas
        stisenia) by ho inak ticho zrusil. Koniec a zrusenie snooze nulu
        `_snooze_job` PRED volanim.
        """
        if getattr(self, "_snooze_job", None) is not None:
            return
        try:
            self.cue_trigger.resume(force=True)
        except Exception:
            app_log.exception("spustac hlasky: resume zlyhal")

    def _set_enso_armed(self, armed):
        """Prenesie "natiahnute" do znacky v bocnom paneli.

        Vnutorny prstenec, nie tretia farba - farba ensa ma podla `theme.py`
        v celom rozhrani jedinu ulohu a tou je povedat, ci appka pocuva.

        Cez `getattr` a `try`, lebo sem sa da dostat aj skor, nez je sidebar
        postaveny (spustac tika z `_tick_activity`, ten bezi od startu).
        """
        armed = bool(armed)
        self._cue_armed = armed
        sidebar = getattr(self, "sidebar", None)
        if sidebar is not None:
            try:
                sidebar.enso.set_armed(armed)
            except Exception:
                pass
        # Znacka a pas nesu ten isty stav - musia sa menit na jednom mieste,
        # inak sa raz rozidu a nikto si toho nevsimne.
        self._refresh_kamae_state_text()

    def _cue_can_fire(self, now):
        """Smie sa prave teraz hlaska dorucit?

        Natiahnutie sa tym NEZRUSI - ked sa nesmie, caka sa dalej. Zrusi sa
        az ked uplynie `max_wait_s`.
        """
        if not self.listening:
            # Enso je jediny nositel stavu. Kym svieti `danger`, appka
            # nesmie povedat nic - inak by ta farba klamala.
            return False
        if getattr(self, "_snooze_job", None) is not None:
            return False            # "teraz nie" plati aj na telo, nie len na klavesy
        if not self._hr_overlay_available():
            self._warn_hr_overlay_disabled_once()
            return False
        # Bezi uz NIEKTORY vizual? Pytat sa len na slot 3 nestacilo: od
        # zavedenia striedania kategorii moze bezat hociktory zo styroch a
        # dva prekryte piktogramy naraz su presne ten vizualny sum, ktoremu
        # sa appka vyhyba.
        if any(self.overlay_manager.is_active(i) for i in range(4)):
            return False
        # Kym chodia kroky, appka mlci. `None` znamena, ze hodinky kroky
        # neposielaju - vtedy sa nema na co odvolavat a nebrani nicomu.
        kroky = self.hr_stats.steps_per_min()
        if kroky is not None and kroky >= self.KROKY_PRAH_ZA_MIN:
            return False
        if now - self.last_global_trigger_time < self.cooldown_value:
            return False
        return True

    def _tick_cue_trigger(self):
        """4x za sekundu. Jediny volajuci je `_tick_activity`, cize Tk vlakno -
        a to je nutne: dotyka sa `hr_stats` aj `overlay_manager`."""
        if not self._hr_session_open:
            return
        now = time.time()
        # Viditelnost HUD-u za tento tik. dt < 5 s je poistka proti uspaniu PC
        # (po prebudeni by jeden "tik" pridal hodiny) - kratke medzery su beh.
        # Aktivny cas rastie vzdy, viditelny len ked je HUD zapnuty - podiel
        # sa potom rata z rovnakej zakladne (viz `_close_hr_session`).
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
        """Ci hrac prave vidi svoj tep - t.j. HUD panel je zapnuty. Berie sa
        ulozeny stav (`hud_config['enabled']`), takze prepnutie ho hned zmeni;
        docasny 'test_hud' sa nepocita (nie je to hranie)."""
        try:
            return bool(self.hud_config.get("enabled"))
        except Exception:
            return False

    def _on_cue_event(self, ev):
        """Jedna udalost z automatu. Vsetko sa zapise - aj zrusene
        natiahnutia, lebo podla ich pomeru sa ladia prahy.

        Je to zaroven jediné miesto, kde sa prstenec na ense zapina. Zhasina
        sa na troch dalsich (dorucenie, zrusenie, `_suspend_cue_trigger`) -
        automat ma stavov viac nez UI, ale von z ARMED vedie kazda cesta cez
        niektoru z nich.
        """
        zaznam = dict(ev)
        self._cue_log.append(zaznam)
        if ev["typ"] == trigger.E_DELIVER:
            self._set_enso_armed(False)
            # Ci sa hlaska NAOZAJ dorucila (nie vypnute vsetky sloty, nie
            # zlyhany vizual). Bez toho dotaznik ratal aj nedorucene a hlasil
            # "Ozvala som sa 3x", ked appka mlcala (bug B19).
            zaznam["delivered"] = bool(self._fire_somatic_cue(ev))
        elif ev["typ"] == trigger.E_ARMED:
            self._set_enso_armed(True)
            app_log.info("hlaska natiahnuta (rameno %s)", ev.get("arm"))
        else:
            self._set_enso_armed(False)
            app_log.info("natiahnutie zrusene: %s", ev.get("reason"))

    def _dalsi_cue_slot(self):
        """Ktora kategoria zaznie teraz. Striedaju sa kolo-dokola.

        Berie do uvahy len sloty, ktore su ZAPNUTE a maju zapnuty aj
        in-game vizual. Ked taky nie je ani jeden, vracia None a hlaska sa
        NEDORUCI - vypnutie je rozhodnutie hraca a appka ho obchadzat nesmie.

        Poradie sa pamata v ramci behu appky, nie medzi spusteniami: po
        restarte sa zacina od prvej zapnutej kategorie. Pri strope pat
        hlasok za hodinu je to rozdiel, ktory sa v datach stratí.
        """
        zapnute = []
        for slot in getattr(self, "slots", ()):
            try:
                index = int(slot.index)
            except (TypeError, ValueError):
                continue
            if not getattr(slot, "enabled_value", True):
                continue
            # A MUSI mat aj zapnuty in-game vizual.
            #
            # `_fire_somatic_cue` kresli `overlay_manager.trigger(index)` v
            # OBOCH ramenach - to je jedina vec, ktoru dostane tiche rameno.
            # Slot s vypnutym vizualom by v tichom rameni nedorucil nic a
            # okno by sa zapisalo ako platne meranie hlasky, ktora sa nikdy
            # nestala. Preto sa taky slot preskakuje.
            try:
                if not self.overlay_configs[index]["enabled"]:
                    continue
            except (IndexError, KeyError, TypeError):
                continue
            zapnute.append(index)
        dalsi = measure.next_slot(zapnute, getattr(self, "_posledny_cue_slot", None))
        if dalsi is None:
            # Ziadna kategoria nie je pouzitelna. `CUE_SLOT_INDEX` (3) bola
            # zaloha natvrdo, lenze prave ten slot moze mat vypnuty vizual -
            # a potom by sa hlaska "dorucila" bez toho, aby sa cokolvek
            # nakreslilo. Berieme prvy slot, ktory naozaj ma co ukazat.
            # ZIADNA ZALOHA. Do 19. 9. sa tu vracal `CUE_SLOT_INDEX` (3),
            # teda dychovy kruh - "radsej nech appka povie nieco nez nic".
            # Lenze vypnutie hlasky je rozhodnutie hraca a appka ho obchadzat
            # nesmie: kto vypol vsetky styri, chcel ticho a dostal dychanie.
            return None
        self._posledny_cue_slot = dalsi
        return dalsi

    def _fire_somatic_cue(self, ev):
        """Doruci hlasku. VIZUAL IDE V OBOCH RAMENACH, zvuk len v hlasnom.

        Keby sa tichemu ramenu nezobrazil ani vizual, ramena by sa nedali
        porovnat - meral by sa rozdiel medzi "nieco sa stalo" a "nestalo sa
        nic", nie medzi hlaskou a tichom.

        Do logu appky ide ROVNAKY riadok v oboch ramenach. Hrac aj tak pocuje,
        ci nieco zaznelo, takze zaslepit sa to neda - ale log nema byt dalsim
        miestom, kde sa ramena rozchadzaju.
        """
        index = self._dalsi_cue_slot()
        if index is None:
            # Vsetky hlasky vypnute (alebo ziadna nema vizual). Doteraz sa v
            # tomto stave dorucila zaloha - dychovy kruh - takze vypnutie
            # vsetkych styroch prepinacov appku NEUMLCALO. Hrac vypol vsetko,
            # co sa vypnut dalo, a appka sa ozvala dalej.
            self.log(tr("log.cue_skipped_all_off"))
            return False
        self.last_global_trigger_time = ev["ts"]
        # VIZUAL JE SPOLOCNY PODNET OBOCH RAMIEN. Ked sa nevykresli, tiche
        # rameno nedostane NIC a meranie by porovnavalo hlasku proti nicomu.
        # `note_trigger(delivered=...)` to prenesie do okna, ktore `measure`
        # v takom pripade zneplatni (bug B17).
        vykreslene = bool(self.overlay_manager.trigger(index))
        if not vykreslene:
            self.log(tr("log.cue_visual_failed"))

        # Podla atributu, nie podla poradia v zozname: `handle_trigger` tiez
        # hlada cez `slot.index`, takze poradie v `self.slots` nemusi sediet.
        slot = next((s for s in self.slots if s.index == index), None)
        label = (slot.text_value if slot is not None else "") or ""
        # `hlas` je v pracovnom svete vzdy False (B3-worlds) - rozhoduje
        # automat (`CueTrigger.open_session(voice=...)`), nie tato vetva,
        # aby aj zaznam udalosti hovoril pravdu o tom, co zaznelo.
        #
        # REBRIK (0.2): zvuk LEN na stupni hlasu. Pod nim ide hlaska len
        # obrazom v oboch ramenach - automat to uz vie (`voice` pri
        # otvoreni), tu je to druha poistka. Styl "zvuk" = stupen hlasu so
        # stlmenymi slovami: slot zahra svoj zvuk, TTS ani nahravka nie.
        stupen = getattr(self, "_cue_rung", rebrik.HLAS)
        bez_slov = (getattr(self, "_cue_style_rel", rebrik.STYL_HLAS)
                    == rebrik.STYL_ZVUK)
        zaznie = False
        if ev.get("hlas") and slot is not None and stupen == rebrik.HLAS:
            zaznie = self._slot_zaznie(slot, bez_slov)
            # `_emit` prehrava a blokuje - v Tk vlakne by zamrazilo okno.
            threading.Thread(target=self._emit, args=(slot,),
                             kwargs={"bez_slov": bez_slov}, daemon=True).start()

        # Zaznam o doruceni ide do okna (`measure.build_window`): stupen,
        # ci naozaj nieco zaznelo, zataz a jej vrchol, pasmo tepu.
        self.hr_stats.note_trigger(
            ts=ev["ts"], auto=True,
            category=measure.category_for_slot(index),
            cue_id=f"slot{index}", arm=ev["arm"], source="auto",
            delivery=ev.get("delivery"), delivered=vykreslene,
            rung=stupen, audible=zaznie, load_at=ev.get("load"),
            load_peak=ev.get("load_peak"), zone_at=ev.get("zone_at"))
        self.log(tr("log.cue_delivered", label=label))
        # Pocitadlo v hlavicke dennika (`session.summary`, "Ťažisko 2× | ...").
        # Doteraz ho zvysoval len `_deliver` pri source=="trigger" - lenze
        # tadial automaticka hlaska nikdy nechodi, takze riadok ukazoval 0×
        # pri vsetkych styroch, kym karta na Dnes hlasila tri hlasky.
        # Rata sa len hlaska, ktora sa naozaj ukazala, a nie tiche kontrolne
        # rameno (to je meranie, nie hlaska pre hraca).
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
        """Pocet spustacov na karte Spustace, bodka pri "V hre" (teraz
        samostatna polozka sidebaru, nie karta), ked senzor tepu bezi."""
        sidebar = getattr(self, "sidebar", None)
        if sidebar is None or not hasattr(sidebar, "set_badge"):
            return
        try:
            # POCET HLASOK pri karte "Spustace" uz NIE JE.
            #
            # Cislo malo zmysel, kym si hrac sloty priradoval ku klavesom a
            # potreboval vidiet, kolko ich je aktivnych. Dnes su styri, appka
            # si ich strieda sama a hrac ich nepridava - tak to bola len
            # cifra, ktora nic nehlasila a tahala oko k nesprávnej veci.
            nav = getattr(self, "settings_nav", None)
            if nav is not None:
                nav.set_badge("spustace", "")
            sidebar.set_badge("vhre", "●" if self.hr_monitoring_enabled else "")
        except Exception:
            pass

    def _refresh_dnes_stats(self):
        """Prepise tep, zataz a suhrn relacie na stranke Dnes.

        Vola sa pri kazdej vzorke tepu a raz za sekundu z `_tick_session`,
        aby bezal aj cas relacie. Ked stranka este nie je postavena (deje sa
        pri prepnuti temy/jazyka), ticho sa nerobi nic.

        PRECO SA TU CHYBA POCITA
        Cele telo je v jednom `except`, a to zamerne: bezi to 1-4x za
        sekundu a vynimka z prekreslenia nesmie zhodit ani meranie, ani
        relaciu. Lenze `pass` znamenal, ze rozbita stranka sa neprejavila
        NICIM. gui_screenshots hlasi "0 chyb v Tk", lebo to chyta len
        vynimky, ktore z Tk callbacku UNIKNU - a tato neunikne. Appka teda
        mohla mat uplne zamrznutu stranku Dnes a cely test prejst nazeleno.

        Prvy vyskyt sa preto zaloguje cely a dalsie sa uz len pocitaju
        (`app_log.exception` pri kazdom volani by log zaplavil). Na
        `_dnes_refresh_fails` sa pyta gui_screenshots.
        """
        if getattr(self, "dnes_bpm", None) is None:
            return
        stats = self.hr_stats
        connected = self._hr_state == "connected" and stats.last_bpm is not None
        # VYPADOK NIE JE "ESTE SOM TA NEPOCULA". Pocas vypadku ostava zivy
        # blok aj stopa relacie (ziadne "Sparuj hodinky" uprostred vecera),
        # ale cislo je "--" a pasmo "—" - to riesi `connected` nizsie, takze
        # ziadny falosny pokoj.
        lost = bool(getattr(self, "_hr_lost", False)) and not connected
        ukaz = connected or lost
        pal = self.pal
        try:
            self.dnes_bpm.configure(
                text=str(int(stats.last_bpm)) if connected else "--",
                text_color=pal["text"] if connected else pal["text_faint"])
            self.dnes_spark.set_series(stats.series(120) if connected else [],
                                       threshold=self.hr_critical_bpm,
                                       baseline=stats.baseline)
            # Kym sa relacia kalibruje, pruh ostane prazdny a namiesto pasma
            # je tiche "kalibrujem…" - rovnako ako HUD v hre. Hned po navrate
            # tepu (`is_settling`) to iste, len namiesto slova "…": zataz sa
            # rozbieha od nuly a inak by par sekund tvrdila "Pokoj".
            kalibruje = connected and stats.is_calibrating
            usadza = connected and not kalibruje and stats.is_settling
            tlmene = kalibruje or usadza
            # Slovo aj farba plnych dielikov su `stats.zone` (tep voci
            # pokoju) - to iste ako na HUD-e a na kontrolke tepu. Dlzka
            # pruhu je zataz.
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
                    vpravo = tr("dnes.hr_waiting")
                self.hr_panel.set_right(vpravo)
            empty, live = getattr(self, "dnes_empty", None), getattr(self, "dnes_live", None)
            if empty is not None and live is not None:
                if ukaz and not live.winfo_ismapped():
                    empty.pack_forget()
                    live.pack(fill="x")
                    self._stop_dnes_hero()       # dýcha už len pás
                elif not ukaz and not empty.winfo_ismapped():
                    live.pack_forget()
                    empty.pack(fill="x", pady=(6, 0))
                    self._start_dnes_hero()      # rozdýchaj dojo za ensom
        except Exception:
            self._dnes_refresh_fails = getattr(self, "_dnes_refresh_fails", 0) + 1
            if self._dnes_refresh_fails == 1:
                app_log.exception(
                    "Dnes: obnovenie zlyhalo (dalsie vyskyty sa uz nevypisu)")
        self._refresh_last_cue()

    def _refresh_session_trace(self, connected):
        """Stopa relacie na Dnes.

        Kresli sa z `HeartStats.trace()`, cize z CELEJ relacie preriedenej
        na 120 bodov - nie z posledneho okna. Bez senzora ostava prazdna,
        ale panel nezmizne: prazdny obrys je informacia ("este som nic
        nezmeral"), zatial co chybajuci panel je diera v stranke.
        """
        trace = getattr(self, "dnes_trace", None)
        if trace is None or not trace.winfo_exists():
            return
        stats = self.hr_stats
        elapsed = max(0.0, time.time() - stats.session_start)
        if connected and stats.session_count >= 2:
            # Bez popisku: Dnes je stranka, na ktoru sa hrac pozera POCAS
            # hrania a kazda veta navyse ho z hry vytrhne. Co pruh znamena,
            # vysvetluje dotaznik po relacii a detail v Historii.
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
        """Rozdelenie casu relacie do pasiem (pruh + styri riadky)."""
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

    # ---------- volitelne statistiky na Dnes ("Moje štatistiky") ----------

    def _dashboard_stat_catalog(self):
        """(id, nazov, TOKEN farby) pre vsetky volitelne statistiky, v poradi
        vo vybere. V mriezke je poradie hracovo (self.dashboard_stats) -
        meni sa potiahnutim karty na inu.

        Token, nie hodnota: kartu aj bodku vo vybere treba po zmene temy
        prefarbit, a token si novu farbu najde sam."""
        return [
            # tep patri do radu pasiem, nie do success/warn/danger - inak by
            # karta "pokojová základňa" svietila inou zelenou, nez akou je
            # pokoj v pruhu vedla nej (viz theme.ZONE_TOKENS)
            ("baseline", tr("metric.baseline.title"), "zone_calm"),
            ("hrr", tr("metric.hrr.title"), "blue"),
            ("over", tr("metric.over.title"), "zone_high"),
            ("breath", tr("metric.breath.title"), "murasaki"),
            ("avg", tr("metric.avg.title"), "zone_calm"),
            ("max", tr("metric.max.title"), "zone_critical"),
            ("peak", tr("metric.peak.title"), "accent"),
            ("week", tr("metric.week.title"), "blue"),
            # 0.2: ta ista farba ako ciara tej istej metriky v Historii
            # (HISTORY_METRICS) - karta a graf su jedna vec
            ("session_len", tr("metric.session_len.title"), "text_dim"),
            ("last_cue", tr("metric.last_cue.title"), "murasaki"),
            ("calm_time", tr("metric.calm_time.title"), "zone_calm"),
            ("signal", tr("metric.signal.title"), "blue"),
            # neutralna farba: ani jedno z dvoch cisel nie je "to spravne"
            ("felt_vs_measured", tr("metric.felt_vs_measured.title"), "text"),
        ]

    # POZN: tu boli `_STAT_HISTORY` (ktore pole ulozeneho suhrnu zodpoveda
    # ktorej karte) a `_STAT_LOWER_IS_BETTER` (kde je "menej" dobra sprava).
    # Oboje existovalo VYLUCNE pre mikrograf a vetu o odchylke na karte;
    # s nimi odisli aj `_dashboard_stat_live` a `ui_kit.MicroChart`.
    # Dovod je nizsie pri `_dashboard_stat_value`.

    def _history_cached(self, max_age=20.0):
        """Historia relacii z disku, najviac raz za `max_age` sekund.

        Karty sa prekresluju pri KAZDEJ vzorke tepu (a raz za sekundu aj
        bez nej). Karta "Relácie tento týždeň" pritom citala JSON zakazdym
        - niekolko otvoreni suboru za sekundu za nic. Cache sa zahodi po
        ulozeni relacie (`_close_hr_session`), cize novy zaznam sa objavi
        hned, nie o 20 sekund.
        """
        now = time.time()
        stamp, data = getattr(self, "_history_cache", (0.0, None))
        if data is None or now - stamp > max_age:
            data = self._history_sessions()
            self._history_cache = (now, data)
        return data

    # POZN: tu boli `_dashboard_stat_live(stat_id)` (aktualna hodnota karty
    # ako CISLO, na porovnanie s historiou) a `_dashboard_stat_trend(stat_id)`
    # (seria poslednych relacii, odchylka dneska od ich priemeru a farba
    # podla toho, ci je to zlepsenie). Kreslilo sa to na karte ako mikrograf
    # plus veta pod cislom.
    #
    # Odislo spolu s prestavbou karty (viz `ui_kit.StatCard`): karta ma byt
    # JEDEN pokojny udaj, a mikrograf s vetou z nej robili tri. Myslienka
    # sama bola spravna - "62 BPM" nehovori nic, kym clovek nevie, co je
    # uneho bezne - a zije dalej v Historii, kde je na trend cely graf.
    #
    # Odstranene s tym aj: `_STAT_HISTORY`, `_STAT_LOWER_IS_BETTER`,
    # `ui_kit.MicroChart` a jazykove kluce `dashboard.delta_*`.

    def _dashboard_stat_value(self, stat_id):
        """(hodnota, popisok) pre jednu kartu - zo ziveho self.hr_stats,
        "week" a "felt_vs_measured" z ulozenej historie relacii
        (hr_sessions.json, cez `_history_cached`)."""
        stats = self.hr_stats
        if stat_id == "baseline":
            base = stats.session_baseline
            return (str(int(round(base))) if base else "-", tr("dashboard.unit.baseline"))
        if stat_id == "hrr":
            hrr = stats.hrr if stats.session_count else None
            return (f"{hrr:+d}" if hrr is not None else "-", tr("dashboard.unit.hrr"))
        if stat_id == "over":
            over = int(stats.time_over)
            return (f"{over // 60}:{over % 60:02d}", tr("dashboard.unit.over"))
        if stat_id == "breath":
            return (str(stats.auto_triggers), tr("dashboard.unit.breath"))
        if stat_id == "avg":
            return (str(int(round(stats.average))) if stats.average else "-",
                    tr("dashboard.unit.avg"))
        if stat_id == "max":
            return (str(int(stats.session_max)) if stats.session_max else "-",
                    tr("dashboard.unit.max"))
        if stat_id == "peak":
            return (str(int(round(stats.peak_stress))), tr("dashboard.unit.peak"))
        if stat_id == "week":
            try:
                since = hr_stats.period_start_ts(hr_stats.PERIOD_WEEK)
                # Len aktualny svet (B3-worlds). Filtruje sa ulozeny zoznam,
                # takze prepnutie sveta sa prejavi hned, bez citania disku.
                count, duration = hr_stats.count_sessions_since(
                    hr_stats.sessions_in_world(self._history_cached(), self.world),
                    since)
            except Exception:
                count, duration = 0, 0.0
            hours, rem = divmod(int(duration), 3600)
            minutes = rem // 60
            sub = f"{hours}h {minutes}m" if hours else f"{minutes}m"
            return (str(count), sub)
        # --- 0.2 (widgets-history). Co sa nevie, je "—", nie nula. ---
        # Dlzka, posledna hlaska a signal sa pytaju len OTVORENEJ relacie:
        # po jej zatvoreni by hodiny bezali dalej od zaciatku uz skoncenej
        # relacie a pokrytie by ticho klesalo k nule.
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
            # Ako "nad hranicou": suhrn relacie, ostava aj po jej zatvoreni.
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
                # Posledna relacia AKTUALNEHO sveta (B3-worlds).
                par = hr_stats.citene_a_merane(hr_stats.posledna_relacia(
                    hr_stats.sessions_in_world(self._history_cached(), self.world)))
            except Exception:
                par = None
            return (self._fmt_citene_merane(par), tr("dashboard.unit.felt_vs_measured"))
        return ("-", "")

    def _rebuild_dashboard_stats_grid(self):
        grid = getattr(self, "dashboard_grid", None)
        if grid is None:
            return
        pal = self.pal
        for child in grid.winfo_children():
            child.destroy()
        self.dashboard_cards = {}
        self._dashboard_drag_state = None     # stare karty su prec
        catalog = {s[0]: s for s in self._dashboard_stat_catalog()}
        # Posledna karta nema ✕ - jedna ostava vzdy (toggle_dashboard_stat).
        removable = len(self.dashboard_stats) > 1
        for i, stat_id in enumerate(self.dashboard_stats):
            meta = catalog.get(stat_id)
            if meta is None:
                continue
            _id, _title, color_token = meta
            value, _sub = self._dashboard_stat_value(stat_id)
            row, col = divmod(i, 2)
            # `metric.*.tag`, nie `title`: karta ukazuje velke cislo a pod
            # nim JEDNO SLOVO. `title` je cela veta a v nemcine, francuzstine
            # a rustine rozsiruje cely pravy stlpec na ukor stredu.
            card = ui_kit.StatCard(
                grid, pal, color_token, tr(f"metric.{stat_id}.tag"), value,
                tr(f"metric.{stat_id}.more"),
                on_remove=((lambda k=stat_id: self._toggle_dashboard_stat(k))
                           if removable else None),
                on_drag=lambda phase, e, k=stat_id: self._dashboard_drag(k, phase, e))
            card.grid(row=row, column=col, sticky="nsew",
                     padx=(0, 7) if col == 0 else (7, 0),
                     pady=(7, 0) if row > 0 else (0, 0))
            self.dashboard_cards[stat_id] = card
        self._refresh_dashboard_stats()

    def _refresh_dashboard_stats(self):
        # POZN: bol tu aj `card.set_trend(...)` z `_dashboard_stat_trend` -
        # mikrograf poslednych relacii a veta o odchylke. Karta je teraz
        # jeden udaj, nie tri; trend patri do Historie, kde je na to graf.
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

        # Vysku berie ramec z obsahu. Kedysi tu bolo `pack_propagate(False)`
        # bez vysky, takze ramec ostal na predvolenych 200 px CTkFrame: vidno
        # boli 3 riadky, stvrty napoly a zvysok sa vybrat vobec nedal. Sirku
        # (230) drzi nulovo vysoka rozpera.
        frame = ctk.CTkFrame(top, fg_color=pal["surface"], corner_radius=ui_kit.RADIUS_PANEL,
                             border_width=1, border_color=pal["border"], width=230)
        frame.pack(padx=1, pady=1)
        ctk.CTkFrame(frame, width=228, height=0, fg_color="transparent").pack()
        ctk.CTkLabel(frame, text=tr("dashboard.picker_title").upper(), font=ui_kit.ui(9, "bold"),
                     text_color=pal["text_faint"], anchor="w").pack(fill="x", padx=12, pady=(10, 4))
        self._dashboard_picker_rows = ctk.CTkFrame(frame, fg_color="transparent")
        self._dashboard_picker_rows.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        self._render_dashboard_picker_rows()
        # jeden tichy riadok: strop 4 kariet a ze sa daju presuvat
        ctk.CTkLabel(frame, text=tr("dashboard.picker_hint"), font=ui_kit.ui(10),
                     text_color=pal["text_faint"], anchor="w", justify="left",
                     wraplength=200).pack(fill="x", padx=12, pady=(0, 10))

        # pravy okraj popupu = pravy okraj tlacidla (rovnake ako makety
        # `position:absolute; top:100%; right:0`) - az PO postaveni obsahu,
        # inak by sirka este nebola znama. Ked sa pod tlacidlo nezmesti
        # (nizka obrazovka, okno dole), vysunie sa nad neho.
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
            # Riadok, na ktorom klik nic neurobi, nema ruku na kurzore:
            #  - nezvolena metrika, ked su 4 karty plne -> aj bledy text
            #    (uvolni sa, ked jednu kartu odoberies)
            #  - posledna zvolena metrika (jedna karta ostava vzdy) -> vyzera
            #    ako zvolena, len nereaguje
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
            # Nizsie riadky (popisok 20 px namiesto predvolenych 28 CTkLabel,
            # okraj 4 namiesto 6): od 0.2 je v katalogu 13 metrik a vyber musi
            # ostat na obrazovke cely. Odmerane pri 150 %: riadok 60 -> 42 px,
            # cely vyber s 13 riadkami 719 px (predtym s 8 riadkami 643).
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
        """Klik na riadok vo vybere alebo ✕ na karte. Strop kariet aj
        "posledna ostava" rata `toggle_dashboard_stat`; ked sa nic nezmeni,
        nic sa neuklada ani neprestavuje."""
        new = toggle_dashboard_stat(self.dashboard_stats, stat_id)
        if new == self.dashboard_stats:
            return
        self.dashboard_stats = new
        self.save_settings()
        self._rebuild_dashboard_stats_grid()
        self._render_dashboard_picker_rows()

    # ---- presun karty potiahnutim (vymena miest) ----
    #
    # Chytis kartu (cislo, popisok, okraj - nie ⓘ/✕), potiahnes aspon
    # DASHBOARD_DRAG_PX a pustis ju na inu kartu: vymenia si miesto. Pri
    # mriezke 2x2 je vymena presne predvidatelna - zvyraznena karta je
    # presne tam, kam tvoja dopadne. Ziadne "duchove" okno, animacia ani
    # posuvanie ostatnych kariet.
    #
    # ROZHODUJE PUSTENIE, nie pohyb: vzdialenost stlacenie->pustenie a
    # karta pod bodom pustenia. Pohyb len kresli zvyraznenie a kurzor.
    # Pri skutocnej mysi totiz niekedy do Tk nepride ani jeden B1-Motion
    # (rychly svih, touchpad) - drop, ktory by na nom zavisel, by sa ticho
    # stratil.

    def _dashboard_card_at(self, x_root, y_root):
        """stat_id karty pod bodom obrazovky, alebo None (medzera, mimo)."""
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
        """Zhodi zvyraznenie aj kurzor. Vola sa pri KAZDOM stlaceni: ked sa
        pustenie stratilo (alt-tab uprostred tahu), nic neostane visiet."""
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
            return                              # obycajny klik
        target = self._dashboard_card_at(event.x_root, event.y_root)
        new = swap_dashboard_stats(self.dashboard_stats, stat_id, target)
        if new == self.dashboard_stats:
            return                              # medzera, mimo, sama na seba
        self.dashboard_stats = new
        self.save_settings()
        # after_idle: prestavba znici aj widget, ktory prave vybavuje event
        self.root.after_idle(self._rebuild_dashboard_stats_grid)

    # POZN: tu bolo `_refresh_kamae_metrics()` - dlzka relacie, pocet
    # pripomienok a tep, kreslene vpravo v dychajucom pase. Odstranene:
    # dlzka aj pocet su o kusok vedla v pravom paneli tejto istej stranky,
    # takze pas ich len opakoval, a pas ma niest stav, nie skore.
    # `self._listen_started` sa pouziva dalej (dlzka relacie v paneli).
