"""Ovladanie appky - cast hlavnej appky (DandurfApp z app.py).

ControlsMixin je mixin DandurfApp: app.py ho dedi a cely stav (paleta,
"teraz nie", dennik, sloty, ovladac, overlay) zije na DandurfApp. Tu su len
metody, ktore s nim pracuju cez `self` - mixin nema __init__ ani vlastne
atributy.

Styri sekcie presunute z app.py bez zmeny:
  * command palette (Ctrl+K) - paleta akcii a opakovanie uvodu,
  * rychly dock - "teraz nie" (prepinac zo skratky aj z listy, odlozenie
    hlasok, bodka stavu) a zbalenie dennika. Registracia skratky
    (`start_snooze_hotkey` / `stop_snooze_hotkey`) ostala v app.py pri
    liste - cita TRAY_AVAILABLE, ktore sa pocita v app.py,
  * rebind - len znacka, rebind odisiel vo faze 3,
  * gamepad (uz NIE ako spustac) - aktivita z ovladaca a rucne spustenie
    hlasky (tlacidlo Test, klik v HUD nahlade).

Pozor v testoch: `_start_snooze`, `_snooze_do`, `_zapocitaj_snooze` a
`fire_slot` citaju `time` z tohto modulu (`fire_slot` aj `threading`) -
falosne hodiny treba podstrcit aj tu (`app_controls.time`), nie len na
module app.
"""

import os
import threading
import time

import rebrik
import theme as theme_mod
import trigger
from i18n import tr
from settings_model import mode_labels
from ui_dialogs import OnboardingWizard
from ui_shell import CommandPalette

from app_spolocne import SNOOZE_HOTKEY_MINUTES, app_log


class ControlsMixin:
    """Paleta prikazov, "teraz nie", dennik a ovladac (mixin DandurfApp)."""

    # ---------- command palette (Ctrl+K) ----------

    def open_command_palette(self):
        """Vytvori paletu s aktualnym zoznamom akcii nanovo pri kazdom
        otvoreni - takto nikdy nezastara ani po zmene slotov/profilov
        mimo plneho _build_ui (add_slot/switch_profile ho nevolaju)."""
        # Predosla paleta sa musi zavriet, inak ostane visiet navrchu vsetkeho
        # (je topmost) a uz ju nic nezavrie - instancia sa predtym zahodila
        # do lokalnej premennej, takze jej vlastna poistka na jedinu instanciu
        # nemala co strazit.
        previous = getattr(self, "_palette", None)
        if previous is not None:
            try:
                previous.close()
            except Exception:
                pass
        # `pal=self.pal`: bez nej sa paleta farbila z moduloveho SHELL_PAL,
        # teda z inej farebnej rodiny nez zvysok okna (viz CommandPalette).
        self._palette = CommandPalette(self.root, self._command_palette_items(),
                                       pal=self.pal,
                                       placeholder=tr("palette.placeholder"))
        self._palette.open()

    def _command_palette_items(self):
        # Vsetky texty palety idu cez i18n - predtym tu boli natvrdo po
        # slovensky, takze anglicky hrac videl v inak anglickom okne
        # "Navigácia" a "Pomoc". Sprievodca sa vola rovnako ako jeho panel
        # (guide.panel_title), len bez ikonky: tk.Listbox emoji mimo BMP
        # nevykresli spolahlivo.
        pomoc = tr("palette.cat.help")
        navigacia = tr("palette.cat.nav")
        appka = tr("palette.cat.app")
        profily = tr("palette.cat.profiles")
        sprievodca = tr("guide.panel_title").replace("📖", "").strip()
        items = [
            (tr("palette.replay_intro"), pomoc, self.replay_onboarding),
            (tr("nav.dnes"), navigacia, lambda: self.sidebar._select("dnes")),
            (tr("nav.historia"), navigacia, lambda: self.sidebar._select("historia")),
            (tr("nav.spustace"), navigacia, lambda: self.sidebar._select("spustace")),
            (tr("nav.zvuk"), navigacia, lambda: self.sidebar._select("zvuk")),
            (tr("nav.vhre"), navigacia, lambda: self.sidebar._select("vhre")),
            (tr("nav.nastavenia"), navigacia, lambda: self.sidebar._select("nastavenia")),
            (sprievodca, pomoc, self.open_guide_panel),
            (tr("common.prepare_voices"), tr("palette.cat.sound"),
             lambda: self.pregenerate(force=True)),
            (tr("status.running") + " / " + tr("status.stopped"), appka,
             self.toggle_listening),
            (tr("common.minimize"), appka, self.minimize_to_tray),
        ]
        for profile in self.profiles:
            name = profile["name"]
            items.append((tr("palette.profile", name=name), profily,
                          lambda n=name: (self.sidebar._select("spustace"),
                                          self.switch_profile(n))))
        for slot in self.slots:
            # Bez klavesu v zatvorke: hlasku uz nespusta stlacenie, takze
            # "Slot [c]" by ukazovalo pismeno, ktore nic nerobi.
            label = slot.text_value.strip() or mode_labels().get(slot.mode, "")
            items.append((tr("palette.slot", label=label), profily,
                          lambda: self.sidebar._select("spustace")))
        return items

    def replay_onboarding(self):
        """Znova ukaze Onboarding Wizard (rovnaky ako pri prvom spusteni).
        Na rozdiel od prveho behu NEPREPISUJE zapnutie/vypnutie existujucich
        slotov podla diagnostiky (self._apply_diagnostics) - je to len
        prehliadka appky, nie reset uz nastavenych slotov.

        Svet a hlasitost sa predvyplnia AKTUALNE - kto uvod len preklikne,
        ostane tam, kde bol (napr. v Praci, kde hlasky nehovoria nahlas)."""
        wizard = OnboardingWizard(self.root, choice=self.theme_key,
                                  volume=self.volume_value)
        self.root.wait_window(wizard.top)
        if not wizard.confirmed:
            return
        # Krok 4 vybera hlavny svet (B3-worlds); tema ide s nim. Okno sa
        # nizsie stavia cele znova, takze staci zmenit stav - historia a
        # postrehy sa prepocitaju az na konci.
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
        # Krok 5 (styl hlasky). Kto na nic neklikol, nechava si svoj styl.
        self._prevezmi_styl_z_onboardingu(wizard)
        self._recompute_volumes()
        self._apply_volumes()
        self.save_settings()
        # appka uz bezi - ak si zvolil parovanie, otvor ho hned
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
        # Svet aj styl hlasky rozhoduju, ci sa hlasky pre Edge pripravuju.
        self.schedule_pregenerate(200)

    # ---------- rychly dock (mute / stiszit / rychly profil / stop) ----------

    # POZN: tu bolo `_dock_on_mute(muted)` - prepinac 🔊/🔇 z rychleho
    # doku, ktory stiahol hlasitost na nulu a spat. Odislo s dokom;
    # hlasitost sa nastavuje posuvnikom v Nastaveniach -> Zvuk.

    def _on_snooze_hotkey(self):
        """Prislo stlacenie. Bezi to na VLASTNOM vlakne `hotkey.py`, takze
        sa vsetko musi preniest do Tk cez `ui_call` - rovnako ako callbacky
        z hodiniek."""
        self.ui_call(self._toggle_snooze_from_hotkey)

    def _toggle_snooze_from_hotkey(self):
        """Prepinac, nie jednosmerka: druhe stlacenie ticho zrusi.

        Hrac sa ku klavesnici v hre casto nedostane rychlo a nechat ho
        cakat 30 minut na nieco, co si omylom zapol, by bolo horsie nez
        samotne hlasky.

        Vola ho aj polozka "Teraz nie" v ponuke listy (`setup_tray`, 0.2.1) -
        ta ista vec, len bez klavesu, ked skratku drzi ina appka.
        """
        if getattr(self, "_snooze_job", None) is not None:
            self._cancel_snooze()
        else:
            self._start_snooze(SNOOZE_HOTKEY_MINUTES)

    # POZN: tu bolo `_dock_on_snooze()` - klik na 😴 v doku, ktory
    # rozbalil vyber dlzky (5/20/40/60 min). Tlacidlo odislo s dokom.
    # Odlozenie sa teraz zapina globalnou skratkou na PEVNYCH
    # `SNOOZE_HOTKEY_MINUTES` minut a `_toggle_snooze_menu` tym ostalo
    # bez spustaca - viz poznamka pri nom.

    def _start_snooze(self, minutes):
        """"Teraz nie": stisi HLASKY na `minutes` minut - a nic viac.

        ROZHODNUTIE ZADAVATELA (24. 9.): pocuva a meria sa DALEJ. Relacia
        ostava otvorena, tep sa zapisuje, dotaznik nepride; len spustac je
        pozastaveny s dovodom `A_SNOOZE` (ten sa neratá ako vypadok) a po
        vyprsani alebo zruseni sa zdvihne. Doteraz sa tu volalo
        `stop_listening`, ktore relaciu zatvorilo a otvorilo dotaznik -
        "teraz nie" tak znamenalo "koniec merania", a to hrac nechcel.
        Zastavit pocuvanie je samostatny, vedomy krok (pas, lista).

        Dlzka je pevna zo skratky (`SNOOZE_HOTKEY_MINUTES`); menu s vyberom
        (`_toggle_snooze_menu`) dnes spustac nema."""
        if getattr(self, "_snooze_job", None) is not None:
            self._cancel_snooze()
        now = time.time()
        # "Teraz nie" kratko po hlaske je signal pre rebrik hlasky. Relacia
        # po nom bezi dalej, takze `_close_hr_session` zapise skutocny cas,
        # ktory sa este hralo (`snooze_then_s`).
        self._zapis_snooze_po_hlaske(now)
        # Kolko z relacie platilo "teraz nie" (`snoozed_s` v suhrne). Relacia
        # ho teraz v sebe nesie a pocitadla spustaca ho nevidia - dotaznik by
        # inak ticho vysvetlil "zataz sa ani raz nedostala nad hranicu".
        if getattr(self, "_hr_session_open", False):
            self._snooze_rel_od = now
        # Senzor tepu bezi dalej a relacia tiez - bez tohto riadku by hlaska
        # prisla aj tak. To je presne ten zly moment, pred ktorym snooze chrani.
        self._suspend_cue_trigger(trigger.A_SNOOZE)
        self.log(tr("log.snooze_started", minutes=minutes))

        def _resume():
            self._zapocitaj_snooze()
            self._snooze_job = None
            self._snooze_until = None
            # Pocuvanie sa tu uz NESPUSTA - "teraz nie" ho nezastavilo.
            self._resume_cue_trigger()
            self.log(tr("log.snooze_ended"))
            self._refresh_snooze_indicator()

        self._snooze_job = self.root.after(int(minutes) * 60 * 1000, _resume)
        self._snooze_until = now + int(minutes) * 60
        self._refresh_snooze_indicator()

    def _snooze_do(self):
        """Dokedy "teraz nie" plati, ako 'HH:MM' ('' ked nebezi).

        Cas konca, nie zvysne minuty: text sa nastavi raz a "zostava 30 min"
        by po piatich minutach klamal."""
        do = getattr(self, "_snooze_until", None)
        if do is None or getattr(self, "_snooze_job", None) is None:
            return ""
        try:
            return time.strftime("%H:%M", time.localtime(do))
        except Exception:
            return ""

    def _zapocitaj_snooze(self, now=None):
        """Pripocita beziaci usek "teraz nie" k otvorenej relacii
        (`_snooze_rel_s`). Vola sa pri konci a zruseni snooze; zatvorenie
        relacie (`_close_hr_session`) si beziaci usek dopocita samo a dalej
        sa uz nic nepripocita - cas mimo relacie (zastavene pocuvanie) sa
        nerata."""
        od = getattr(self, "_snooze_rel_od", None)
        if od is None:
            return
        now = time.time() if now is None else now
        self._snooze_rel_s = (getattr(self, "_snooze_rel_s", 0.0)
                              + max(0.0, float(now) - float(od)))
        self._snooze_rel_od = None

    def _zapis_snooze_po_hlaske(self, now):
        """Prislo "teraz nie" do `rebrik.SNOOZE_PO_HLASKE_S` po poslednej
        dorucenej automatickej hlaske? Zapise sa k hlaske (`snooze_after_s`,
        ide do okna) a do relacie (`_close_hr_session`: `snooze_after_cue_s`
        a `snooze_then_s` = kolko relacia po nom este bezala).

        Rebrik ho rata, len ked relacia potom bezala aspon
        `rebrik.SNOOZE_POTOM_S` a verdikt nie je "sadla" - "teraz nie" na
        konci hrania znamena skor "koncim" nez "prekazala si". Zapisuje sa
        len prvy v relacii."""
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
        # Pocuvanie "teraz nie" nezastavilo, takze ho tu netreba spustat.
        self._resume_cue_trigger()
        self.log(tr("log.snooze_cancelled"))
        self._refresh_snooze_indicator()

    def _refresh_snooze_indicator(self):
        """Da bodkou v bocnom rade najavo, ci odlozenie prave bezi.

        POZN K HISTORII: stav nosila najprv textova popiska v Nastaveniach
        ('20m'), potom farba ikony 😴 v rychlom doku. Dok z panela odisiel
        (viz `_build_ui`) a odlozenie sa zapina globalnou skratkou - keby
        stav nemal kam ist, hrac by appku odlozil a NIKDE by nevidel, ze je
        odlozena. Bodka stavu uz je na kazdej stranke, cize je to jedine
        miesto, kde to nezmizne pri prepnuti stranky.

        Cas konca nesie tooltip: farba povie "nieco je inak", cas povie
        dokedy, a na to v 64px rade textovy popisok nie je.

        Od 24. 9. appka pocas "teraz nie" pocuva dalej, takze aj stred
        stranky Dnes musi povedat, ze sa neozve (`_kamae_state_text`) -
        "cakam na spravnu chvilu" by klamalo."""
        self._refresh_dnes_state_text()
        # Fajka pri "Teraz nie" v ponuke listy (`setup_tray`). Pystray menu
        # postavi znova len pri `update_menu` - a klik v liste prepina az cez
        # `ui_call`, teda PO jeho vlastnom prestaveni; skratka ho nevola vobec.
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

    # ---------- gamepad (uz NIE ako spustac) ----------
    #
    # FAZA 3: klavesove a mysacie listenery su PREC. Bolo to jedine miesto
    # v appke, ktore vyzeralo ako keylogger - globalny WH_KEYBOARD_LL hook
    # cez pynput. Hlasku teraz spusta telo (`trigger.CueTrigger`) a to, ci
    # je hrac aktivny, sa zistuje z `GetLastInputInfo`, co vracia jedine
    # pocet milisekund od posledneho vstupu. Ktora klavesa to bola sa appka
    # nema ako dozvediet, ani keby chcela.
    #
    # Gamepad listener ostava, ale UZ NESPUSTA NIC - sluzi ako druhy zdroj
    # detekcie aktivity vedla GetLastInputInfo (viz MERANIE_GAMEPAD.md:
    # na tomto Windowse 11 ho GetLastInputInfo vidi, ale je to jeden
    # pocitac a tiche zlyhanie na inom by sa neprejavilo ako chyba).

    def on_gamepad_button(self, label):
        """Aktivita na ovladaci (tlacidlo, d-pad, pacicka alebo spust za
        mrtvou zonou - aj drzane). Uz nespusta hlasku - len potvrdi, ze hrac
        je aktivny. `label` je vzdy "activity"; ktory prvok to bol, listener
        nepovie (`gamepad.py`)."""
        self.activity.note_external_input()

    def on_gamepad_status(self, message):
        if message.startswith("connected:"):
            self.log_threadsafe(tr("log.gamepad_connected", name=message.split(":", 1)[1]))
        elif message == "disconnected":
            self.log_threadsafe(tr("log.gamepad_disconnected"))

    def fire_slot(self, slot, ignore_cooldown=False, source="trigger"):
        """RUCNE spustenie hlasky - tlacidlo Test na karte a klik v HUD nahlade.

        Sama od seba appka tadialto NECHODI. `_fire_somatic_cue` vola `_emit`
        priamo, lebo o tom, KEDY sa ozve, rozhoduje zataz tela
        (`trigger.CueTrigger`) a nie cislo na karte hlasky. Vlastny cooldown,
        oneskorenie, "kazde N-te" a rozptyl tu preto do 18. 9. sedeli ako
        nastavenia, ktore ovplyvnovali jedine tieto dve tlacidla - a pritom
        vyzerali, ze riadia celu appku. Zmizli.

        Ostal globalny odstup, aby sa dve rychlo po sebe iduce kliknutia
        neprekryli v jednom zvuku.
        """
        if not ignore_cooldown:
            now = time.time()
            if now - slot.last_triggered < self.cooldown_value:
                return
            # Kym neuplynie odstup od POSLEDNEJ rucne spustenej hlasky
            # (hocijakej), nesmie sa spustit dalsia - inak sa dva rychle
            # kliky na Test prekryju v jednom zvuku.
            if now - self.last_global_trigger_time < self.cooldown_value:
                return
            self.last_global_trigger_time = now
            slot.last_triggered = now
        if 0 <= slot.index < 4:
            self.ui_call(lambda i=slot.index: self.overlay_manager.trigger(i))
            # Zaznam pre meracie okno. Musi ist cez `ui_call` - `fire_slot`
            # bezi na vlakne listenera, kym `HeartStats` sa smie dotykat len
            # GUI vlakno. Klavesove spustace vo faze 3 zaniknu; dovtedy su
            # najrychlejsi sposob, ako overit, ze merania naozaj chodia.
            self.ui_call(lambda i=slot.index, s=source: self._note_cue(i, s))
        threading.Thread(target=self._deliver, args=(slot, ignore_cooldown, source),
                         daemon=True).start()

    def _note_cue(self, slot_index, source="trigger"):
        """RUCNE spustena hlaska sa do merania NEZAPISUJE.

        Zapisovala sa - a to bola chyba, ktora tichým spôsobom kazila presne
        tu vec, kvoli ktorej appka meria. `fire_slot` dnes spusta jedine
        tlacidlo Test na karte hlasky a klik v HUD nahlade. Oboje sa deje
        pri nastavovani, casto viackrat za sebou, a hrac pri tom nehra.
        `measure.by_category` pritom filtruje len podla `valid` a `arm` -
        `source` necita vobec - takze kazdy klik na Test sa zaratal do grafu
        "ktora hlaska zabera" a jeho cas zabral refrakternu zonu skutocnej
        hlaske, ktora mohla prist o par sekund neskor.

        Automaticku hlasku zapisuje `_fire_somatic_cue` sam, cez
        `hr_stats.note_trigger(..., source="auto")`. Tadialto teda uz
        nemusi ist nic.

        Metoda ostava (a vola sa), aby bolo z kodu vidno, ze sa o tom
        rozhodlo - a aby sa sem dalo vratit pocitadlo, ktore meranie neruší.
        """
        return

    def _deliver(self, slot, immediate, source):
        # Jedno prehratie, ziadne oneskorenie ani opakovanie: hlaska ma
        # pristat vtedy, ked na nu clovek klikol.
        self._emit(slot)
        label = slot.text_value or (os.path.basename(slot.audio_path)
                                    if slot.audio_path else mode_labels()[slot.mode])
        self.log_threadsafe(f"Slot {slot.index + 1} ({source}): \"{label}\"")
        if source == "trigger" and 0 <= slot.index < 4:
            # POCITADLO PATRI TK VLAKNU. `_deliver` bezi na vlastnom vlakne a
            # `start_listening` medzitym `session_counts` vymiena za novy
            # slovnik - prirastok odtialto by mohol skoncit v starom slovniku
            # alebo sa pobit s prekreslenim riadku. Preto cez `ui_call`,
            # rovnako ako `_note_cue` vo `fire_slot`.
            def zarataj(index=slot.index):
                self.session_counts[index] = self.session_counts.get(index, 0) + 1
                self.update_session_label()
            self.ui_call(zarataj)
