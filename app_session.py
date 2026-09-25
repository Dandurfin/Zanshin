"""Senzor tepu a meracia relacia - cast hlavnej appky (DandurfApp z app.py).

SessionMixin je mixin DandurfApp: app.py ho dedi a cely stav (prijem tepu z
hodiniek a stav spojenia, otvorena relacia a jej prahy, zaznam aktivity)
zije na DandurfApp. Tu su len metody, ktore s nim pracuju cez `self` -
mixin nema __init__ ani vlastne atributy.

Presunuty z app.py bez zmeny zvysok sekcie "Auto-Profile Engine
(rozpoznanie beziacej hry)" - stal pod tou znackou, hoci s rozpoznanim hry
nesuvisi (prva cast sekcie je v app_profiles.py), preto tu ma novu znacku:
nastavenie a zapnutie senzora, otvorenie meracej relacie (svet, dlhodoba
zakladna, kriticky tep, prahy spustaca, stupen rebrika), prijem tepu,
krokov a stavu spojenia, vypadky tepu, opakovana vazba na obsadeny port,
stav senzora v Nastaveniach, skryta IP a tiky relacie a aktivity. Pomocnici
`_hr_overlay_available` a `_warn_hr_overlay_disabled_once` (pouziva ich
dorucenie hlasky) stali v tej istej sekcii. Zatvorenie relacie
(`_close_hr_session`) je v app_data.py.

Konstanta `HR_NO_CLIENT_AFTER_MS` ostala v triede DandurfApp medzi
ostatnymi konstantami triedy - `_schedule_no_client_check` ju cita cez
`self`.

Pozor v testoch: `_open_hr_session`, `_apply_hr_bpm` a
`_tick_nonstop_input` citaju `time` z tohto modulu - falosne hodiny treba
podstrcit aj tu (`app_session.time`), nie len na module app.
"""

import time

import activity
import hr_stats
import measure
import netinfo
import rebrik
import theme as theme_mod
import trigger
from heart_rate import ANY_INTERFACE
from i18n import tr
from settings_model import clamp_int

from app_spolocne import app_log


class SessionMixin:
    """Senzor tepu a meracia relacia (mixin DandurfApp)."""

    # ---------- senzor tepu a meracia relacia ----------

    def on_hr_config_change(self):
        # prazdne policko = "pocuvaj na vsetkych sietach", nie "vrat povodnu
        # hodnotu" - hrac musi mat sposob, ako sa k tomu bezpecnemu stavu
        # dostat aj ked si tam raz napisal nefunkcnu adresu
        ip = self.hr_ip_var.get().strip() or ANY_INTERFACE
        port = clamp_int(self.hr_port_var.get(), 1, 65535, self.hr_port)
        critical = int(self.hr_critical_bpm)      # rata sa, nenastavuje
        network_changed = (ip != self.hr_ip) or (port != self.hr_port)
        self.hr_ip, self.hr_port, self.hr_critical_bpm = ip, port, critical
        self.hr_stats.critical_bpm = critical
        self.hud.configure(critical_bpm=critical)
        self.hr_ip_var.set(ip)
        self.hr_port_var.set(str(port))
        self.refresh_hr_status_label()
        self.save_settings()
        if network_changed and self.hr_monitoring_enabled:
            self.start_heart_rate_monitor()

    def on_hr_toggle(self):
        self.hr_monitoring_enabled = bool(self.hr_enabled_var.get())
        self.save_settings()
        if self.hr_monitoring_enabled:
            self.start_heart_rate_monitor()
        else:
            self.stop_heart_rate_monitor()

    def start_heart_rate_monitor(self):
        """Otvori novu meraciu relaciu A naštartuje sietovy prijem.

        Ked treba len novu relaciu (zapnutie pocuvania, ked uz hodinky
        posielaju), vola sa `_open_hr_session` priamo - restart socketu by
        hodinky na chvilu odpojil.
        """
        self._open_hr_session(meria=self.listening)
        self._hr_generation = self.heart_rate_monitor.start(self.hr_ip, self.hr_port)
        self.log(tr("log.hr_enabled", ip=self._hr_ip_display(), port=self.hr_port))
        # Ak sa do N sekúnd nepripojí ani jeden klient, povedz to inak než
        # "Pripája sa…" - "bound, ale nikto sa nepripojil" je iný problém
        # (najčastejšie firewall) a hráč to má vedieť (B2).
        self._schedule_no_client_check()
        # Varovanie o exkluzívnom fullscreene sa TU nekontroluje: v tejto
        # chvíli je popredím Zanshin (hráč práve klikol), takže hru by nikdy
        # nezachytilo (bug A3). Rieši to `_tick_session`, keď je popredím hra.

    def _open_hr_session(self, prepoj=True, meria=True):
        """Zacne novu meraciu relaciu. Siete sa NEDOTYKA.

        `prepoj=False` znamena "prijem uz bezi a hodinky posielaju" - vtedy
        sa stav pripojenia nesmie zhodit na "connecting", lebo by okno
        tvrdilo, ze sa prave pripaja, hoci data chodia.
        """
        # Predosla relacia sa musi KOREKTNE ZATVORIT, nie len prepisat.
        # `hr_stats.reset_session()` nizsie zmaze `cues` aj `_all`, takze bez
        # tohto by sa meracie okna uz nemali z coho zostavit - a jedina
        # cesta, ktora sem vedie s otvorenou relaciou, je zmena IP/portu
        # uprostred vecera (`apply_hr_settings`). Odmerane: cely vecer dat
        # zmizol bez jedineho riadku v logu.
        if getattr(self, "_hr_session_open", False):
            self._close_hr_session()
        if prepoj:
            self._hr_state = "connecting"
        self._hr_last_bpm = None
        # Vypadok patri do predoslej relacie, aj ked sa otvara bez prepojenia
        # (`start_listening` pocas vypadku). Inak by sa priznak preniesol do
        # novej relacie a riadok "tep je spat" by ratal od casu, ktory
        # `reset_session` nizsie prepise.
        self._hr_lost = False
        self._hr_lost_od = None
        self._hr_over_since = None
        self._hr_overlay_warned = False
        self._hr_retry_job = None
        self._hr_bind_retries = 0
        self._hr_client_linked = False
        self.hr_stats.critical_bpm = self.hr_critical_bpm
        # SVET RELACIE SA PECATI TU (B3-worlds), pri otvoreni - nie pri
        # zatvoreni. Kto si uprostred hry len prepne na Pracu, aby videl
        # pracovne statistiky, a zabudne prepnut spat, nema mat hru
        # zapisanu ako pracu. Ide do suhrnu ako `world` (`_close_hr_session`)
        # a urcuje, ci hlaska smie mat hlas (nizsie, `open_session`).
        self._session_world = self.world
        # Pokojovy tep z predchadzajucich vecerov. Bez neho appka v suvislom
        # strese nevidi ziadnu zataz - zakladna sa jej dotiahne za stresom a
        # pocita voci nemu (viz `hr_stats.dlhodoba_zakladna`).
        try:
            historia = self._history_sessions()
            # Zakladna zo VSETKYCH relacii - telo je jedno (B3-worlds).
            self.hr_stats.long_baseline = hr_stats.dlhodoba_zakladna(historia)
            # Kriticky tep a prah zataze len z HERNYCH relacii (B3-worlds,
            # viz `ALGORITMUS_SVET`). Plati aj pre pracovnu relaciu - tam
            # sa hlaska aj tak ukaze len obrazom.
            herna = hr_stats.sessions_in_world(historia, self.ALGORITMUS_SVET)
            # Kriticky tep sa prepocita RAZ ZA RELACIU, nie priebezne.
            # Menit skalu zataze uprostred vecera by znamenalo, ze okna z
            # prvej polovice a z druhej sa nedaju porovnat - to iste
            # pravidlo, ake plati pre prahy spustaca (zadanie §3.3).
            self.hr_critical_bpm = int(hr_stats.dynamicky_kriticky(
                herna, baseline=self.hr_stats.long_baseline))
            # Prah zataze z vlastnych relacii. None = este nie je z coho,
            # vtedy ostavaju cisla pre priemerneho hraca.
            self._prah_z_dat = hr_stats.dynamicky_prah_zataze(
                herna, baseline=self.hr_stats.long_baseline,
                critical=self.hr_critical_bpm)
            # To iste pravidlo ako vypocet (`je_dost_dlha`): pokazene
            # `duration_s` tu nesmie vyhodit vynimku, inak by `except` nizsie
            # zahodil aj dlhodobu zakladnu.
            self._prah_z_relacii = len([
                r for r in hr_stats.ciste_relacie(herna)
                if hr_stats.je_dost_dlha(r)])
        except Exception:
            self.hr_stats.long_baseline = None
            app_log.exception("dlhodoba zakladna / kriticky tep zlyhali")
        self.hr_stats.critical_bpm = self.hr_critical_bpm
        self.hud.configure(critical_bpm=self.hr_critical_bpm)
        self._refresh_kriticky_popis()
        self._refresh_citlivost_detail()
        self.hr_stats.reset_session()
        # Prvych par sprav s krokmi zapis do denniku - z nich sa nastavi prah.
        self._metrics_log_left = 10
        # Zaznam aktivity sa vynuluje spolu s relaciou, aby meracie okna
        # nevideli nic spred zapnutia senzora.
        self.activity.reset_session()
        # Riadok "ziadna pauza vo vstupe" je raz za relaciu.
        self._nonstop_input.reset()
        # Podiel tichych hlasok klesne po kalibracii (25 % -> 10 %), ale
        # nikdy nie na nulu. Pocet relacii sa berie z historie.
        self._cue_log = []
        # Prahy sa beru AZ TU, cize az pri novej relacii (§3.3): menit ich
        # uprostred vecera znamena merat pohyblivy ciel.
        #
        # Poradie je zamerne. Najprv volba "ako casto sa ozvem" (cely
        # slovnik, takze prepnutie spat na "bezne" naozaj vrati vychodiskove
        # cisla a nenecha visiet stare), az potom vyvojarska vrstva, ktora
        # je jemnejsi nastroj a smie prekryt hocico.
        # Cisla pre priemerneho hraca z literatury; prvá relácia bezi na nich.
        self.cue_trigger.params.update(trigger.default_params())
        if getattr(self, "_prah_z_dat", None) is not None:
            self.cue_trigger.params["stress_threshold"] = float(self._prah_z_dat)
        if getattr(self, "_dev_params", None):
            self.cue_trigger.params.update(self._dev_params)
        podiel = self._silent_share_for_next_session()
        # REBRIK HLASKY (0.2): na akom stupni bezi tato relacia. Pauza =
        # automat sa vobec nenatiahne (diagnostika bezi dalej).
        self._urci_stupen_hlasky()
        if self._cue_rung == rebrik.PAUZA:
            self.cue_trigger.params["cues_enabled"] = False
        self._snooze_po_hlaske = None
        self._snooze_rel_s = 0.0
        self._snooze_rel_od = None
        # PRACA = LEN OBRAZ (B3-worlds, rozhodnutie zadavatela). Kto sa v
        # praci sustredi, nema mu do toho nic hovorit ani cinkat - vizual v
        # rohu oka staci. Plati pre celu relaciu podla sveta, v ktorom zacala.
        # Pod stupnom hlasu (rebrik) tiez len obraz - `hlas` v udalosti tak
        # hovori pravdu o tom, co mohlo zaznet.
        self.cue_trigger.open_session(silent_share=podiel,
                                      voice=self._session_world != "work"
                                      and self._cue_rung == rebrik.HLAS)
        # "TERAZ NIE" PLATI AJ CEZ NOVU RELACIU. `open_session` automat
        # zdvihne - a nova relacia sa da otvorit aj pocas stisenia (stop a
        # start, zapnutie senzora, zmena IP), odkedy snooze pocuvanie
        # nezastavuje (24. 9.).
        if getattr(self, "_snooze_job", None) is not None:
            self._suspend_cue_trigger(trigger.A_SNOOZE)
            # Aj do `snoozed_s` novej relacie - od jej zaciatku.
            if meria:
                self._snooze_rel_od = time.time()
        # MERIA SA LEN, KED SVIETI ZELENA.
        #
        # `hr_stats.add()` bezi pri kazdej vzorke bez ohladu na to, ci appka
        # pocuva - takze relacia otvorena SAMOTNYM ZAPNUTIM SENZORA by
        # zbierala trvanie, pasma aj zakladnu z casu, v ktorom hlaska nemohla
        # padnut. V exporte by z toho bola "relacia", v ktorej sa nemeralo
        # nic, a v pocte vecerov do zaveru by sa ratala ako plnohodnotna.
        #
        # `meria=False` teda nechá senzor bezat (aby bolo vidiet tep pri
        # parovani), ale relaciu NEOTVORI. Otvori ju az `start_listening`.
        self._hr_session_open = bool(meria)
        if meria:
            # Nova relacia: vynuluj sledovac viditelnosti HUD-u.
            self._hud_vis_s = 0.0
            self._hud_active_s = 0.0
            self._hud_tick_t = time.time()
        if prepoj:
            self.hud.set_connected(False)
        self.hud.configure(critical_bpm=self.hr_critical_bpm)
        self.refresh_hr_status_label()

    def stop_heart_rate_monitor(self):
        self.heart_rate_monitor.stop()
        self._cancel_no_client_check()
        # generacia 0 = ziadne bezuce vlakno, takze uz odoslane (a este
        # nedorucene) aktualizacie z prave zastaveneho vlakna sa zahodia
        self._hr_generation = 0
        self._hr_state = "disconnected"
        self._hr_last_bpm = None
        self._hr_over_since = None
        self._hr_client_linked = False
        # Senzor vypol hrac - to uz nie je vypadok. Relacia sa zatvara az
        # nizsie, takze vypadok, ktory prave trval, sa do suhrnu este zarata.
        self._hr_lost = False
        self._hr_lost_od = None
        self._close_hr_session()
        self.hud.set_connected(False)
        self.hr_stats.clear_live()
        self.refresh_hr_status_label()
        self.log(tr("log.hr_disabled"))

    def _schedule_no_client_check(self):
        self._cancel_no_client_check()
        try:
            self._hr_no_client_job = self.root.after(
                self.HR_NO_CLIENT_AFTER_MS, self._hr_no_client)
        except Exception:
            self._hr_no_client_job = None

    def _cancel_no_client_check(self):
        job = getattr(self, "_hr_no_client_job", None)
        if job is not None:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
            self._hr_no_client_job = None

    def _hr_no_client(self):
        self._hr_no_client_job = None
        # Stále "connecting" a nikto sa nepripojil → povedz to narovinu.
        if self._hr_state == "connecting" and self.hr_monitoring_enabled:
            self._hr_state = "no_client"
            self.refresh_hr_status_label()
            self._refresh_kamae_state_text()

    def _hr_ip_display(self):
        """IP pre riadok v denniku appky - skryta, kym ju hrac neodkryje
        (0.0.0.0 sa neskryva, nie je to adresa PC)."""
        ip = self.hr_ip if self.hr_ip.strip() else ANY_INTERFACE
        return netinfo.ip_for_screen(ip, self.show_ip)

    def set_show_ip(self, show):
        """Ukazat / Skryt IP pre celu appku (okno parovania aj pole IP v
        Nastaveniach). Len v pamati - po restarte je IP znova skryta, preto
        to `save_settings` ZAMERNE nezapisuje."""
        self.show_ip = bool(show)
        var = getattr(self, "show_ip_var", None)
        if var is not None:
            try:
                if bool(var.get()) != self.show_ip:
                    var.set(self.show_ip)
            except Exception:
                pass
        self._apply_hr_ip_mask()

    def _apply_hr_ip_mask(self):
        """Pole IP v Nastaveniach kresli skutocnu adresu bodkami, kym nie je
        `show_ip`. Prazdne pole a 0.0.0.0 ostavaju citatelne."""
        entry = getattr(self, "hr_ip_entry", None)
        var = getattr(self, "hr_ip_var", None)
        if entry is None or var is None:
            return
        try:
            maska = netinfo.entry_mask(var.get(), self.show_ip)
            if str(entry.cget("show")) != maska:
                entry.configure(show=maska)
        except Exception:
            pass            # pole uz neexistuje (prestavba UI)

    def on_hr_bpm(self, bpm, generation):
        self.ui_call(lambda: self._apply_hr_bpm(bpm, generation))

    def _apply_hr_bpm(self, bpm, generation=None):
        if generation is not None and generation != self._hr_generation:
            return                      # sprava od uz zastaveneho vlakna
        self._hr_state = "connected"
        self._hr_bind_retries = 0       # port sa uvolnil, pocitadlo odznova
        self._hr_last_bpm = bpm
        self.hr_stats.add(bpm)
        # Vypadok konci az PLATNOU vzorkou - tou istou, ktora v `hr_stats`
        # uzavrie slepy cas, aby riadok v denniku a suhrn nehovorili ine.
        if self._hr_lost and self.hr_stats.last_bpm is not None:
            self._tep_je_spat()
        self.hud.set_connected(True)
        self._refresh_hud_session_text()
        self._refresh_dnes_stats()
        self.refresh_hr_status_label()
        # Pás flipne z "Čakám na tep" na "Sledujem tep", len čo dáta chodia
        # (bug A2 - pás sa dovtedy prekresľoval len z `_set_enso_armed`).
        self._refresh_kamae_state_text()
        now = time.time()
        # Faza 2: spusta ZATAZ drziaca nad prahom, nie surove BPM prekracujuce
        # kriticku hranicu. Zataz uz v sebe nesie `sustained` - podiel
        # poslednych dvoch minut nad zakladnou - takze "spicka po headshote
        # nie je stres" je zabudovane v samotnom cisle, nie dolepene.
        # ZATAZ SA PODAVA AUTOMATU LEN POCAS RELACIE.
        #
        # Volalo sa to pri kazdej vzorke, aj ked relacia nebezala (senzor
        # zapnuty, pocuvanie vypnute). Automat sa teda natiahol, prstenec na
        # ense sa rozsvietil - a `_tick_cue_trigger` sa kvoli
        # `_hr_session_open` hned vracal, takze uz ho nemal co zhodit.
        # Prstenec "natiahnute" potom svietil donekonecna a tvrdil stav,
        # ktory neexistoval.
        if not self._hr_session_open:
            return
        self.cue_trigger.resume(now)
        # Pocas kalibracie (prvych ~30 vzoriek relacie) sa nic nenatiahne -
        # viz `trigger.CueTrigger.note_load`.
        # `zona` je pre BRANU hlasky (0.2): pasmo TEPU (`zone_of_bpm`, to
        # iste slovo ako na HUD-e), None ked ho appka nepozna. Nikdy nie
        # pasma zataze - nad hranicou vysokeho tepu hlas nezaznie.
        udalost = self.cue_trigger.note_load(
            self.hr_stats.stress, now,
            calibrating=self.hr_stats.is_calibrating,
            zona=self.hr_stats.known_zone)
        if udalost is not None:
            self._on_cue_event(udalost)

    def on_hr_metrics(self, metrics, generation):
        self.ui_call(lambda: self._apply_hr_metrics(metrics, generation))

    def _apply_hr_metrics(self, metrics, generation=None):
        """Kroky a rychlost z hodiniek. Bezi na Tk vlakne ako `_apply_hr_bpm`."""
        if generation is not None and generation != self._hr_generation:
            return
        try:
            self.hr_stats.note_metrics(steps=metrics.get("steps"),
                                       speed=metrics.get("speed"),
                                       zdroj=metrics.get("zdroj"))
        except Exception:
            app_log.exception("kroky z hodiniek sa nepodarilo zapisat")
            return
        if self._metrics_log_left > 0:
            self._metrics_log_left -= 1
            app_log.info("hodinky posielaju [%s]: kroky=%s rychlost=%s "
                         "(za minutu %s)", metrics.get("zdroj") or "bez mena",
                         metrics.get("steps"), metrics.get("speed"),
                         self.hr_stats.steps_per_min())

    def on_hr_status(self, status, generation):
        self.ui_call(lambda: self._apply_hr_status(status, generation))

    def _apply_hr_status(self, status, generation=None):
        if generation is not None and generation != self._hr_generation:
            return                      # sprava od uz zastaveneho vlakna
        kind, payload = status
        if kind == "bound_any":
            # zadanu IP toto PC nema - pocuvame na vsetkych sietach, nech
            # hracovi funkcia nezomrie kvoli jednemu zlemu cislu
            self.log(tr("log.hr_bind_fallback",
                        ip=netinfo.ip_for_screen(payload, self.show_ip)))
            return
        if kind == "client":
            # hodinky drzia spojenie - to este NEznamena, ze posielaju tep
            self._cancel_no_client_check()      # klient prisiel (B2)
            self._hr_client_linked = True
            self._hr_state = "linked"
            self.log(tr("log.hr_client_connected"))
        elif kind == "client_gone":
            self._zaznamenaj_vypadok(kind)      # PRED clear_live
            self.hud.set_connected(False)
            self.hr_stats.clear_live()
            self._hr_client_linked = False
            self._hr_state = "connecting"
            self._hr_last_bpm = None
            self._hr_over_since = None
            self._suspend_cue_trigger(trigger.A_TEP_VYPADOL)
            self.log(tr("log.hr_client_gone"))
        elif kind == "connecting":
            self._hr_state = "connecting"
            self._hr_last_bpm = None
        elif kind == "disconnected":
            # tep prestal chodit; ak hodinky spojenie stale drzia, je to
            # "pripojene, ale bez dat", nie "odpojene" - iny problem, iny text
            self._zaznamenaj_vypadok(kind)      # PRED clear_live
            self.hud.set_connected(False)
            self.hr_stats.clear_live()
            self._hr_state = "linked" if self._hr_client_linked else "disconnected"
            self._hr_last_bpm = None
            self._hr_over_since = None
            self._suspend_cue_trigger(trigger.A_TEP_VYPADOL)
        elif kind == "busy":
            # OBSADENY PORT JE DOCASNY STAV, NIE ROZHODNUTIE HRACA.
            #
            # Doteraz sa sem padalo spolu s "error": appka vypla
            # `hr_monitoring_enabled` a hned to ULOZILA na disk. Z kolizie,
            # ktora trva par sekund (druha instancia appky sa prave zatvara,
            # alebo ju niekto omylom spustil dvakrat), sa tak stalo trvale
            # nastavenie - senzor ostal vypnuty aj potom, co sa port uvolnil,
            # a hrac nemal ako zistit preco. Jediny signal bol riadok v
            # DENNIKU, ktory je predvolene zabaleny.
            #
            # Teraz sa prepinac nechava zapnuty, do nastaveni sa neuklada nic
            # a vazba sa par krat zopakuje. Az ked port drzi niekto natrvalo,
            # sa senzor vzda - a vtedy to uz naozaj je stav, o ktorom ma
            # zmysel hraca informovat.
            self._hr_state = "busy"
            self._hr_last_bpm = None
            self._hr_over_since = None
            self._hr_client_linked = False
            self._hr_lost = False           # port, nie vypadok tepu
            self._hr_lost_od = None
            self._hr_generation = 0
            self._close_hr_session()
            self._hr_bind_retries = getattr(self, "_hr_bind_retries", 0) + 1
            if self._hr_bind_retries <= self.HR_BIND_RETRIES:
                self.log(tr("log.hr_port_busy_retry", port=payload,
                            n=self._hr_bind_retries, z=self.HR_BIND_RETRIES))
                self._hr_retry_job = self.root.after(
                    self.HR_BIND_RETRY_MS, self._retry_hr_bind)
            else:
                self.hr_monitoring_enabled = False
                if self.hr_enabled_var is not None:
                    self.hr_enabled_var.set(False)
                self.save_settings()
                # Stav sa MUSÍ zmeniť z "busy" - inak štítok navždy tvrdí
                # "skúšam znova", hoci sme to vzdali (B3).
                self._hr_state = "busy_gave_up"
                self.log(tr("log.hr_port_busy", port=payload))
            self.refresh_hr_status_label()
            self._refresh_dnes_stats()
            self._refresh_kamae_state_text()   # pás nesmie tvrdiť "sledujem"
            return
        elif kind == "error":
            self._hr_state = "disconnected"
            self._hr_last_bpm = None
            self._hr_over_since = None
            self._hr_client_linked = False
            self._hr_lost = False           # senzor je vypnuty, nie slepy
            self._hr_lost_od = None
            self.hr_monitoring_enabled = False
            if self.hr_enabled_var is not None:
                self.hr_enabled_var.set(False)
            self.save_settings()
            # Prepinac sa prave vypol, ale relacia zostavala OTVORENA: uz
            # sa nedala vypnut cez `stop_heart_rate_monitor` (ten vola len
            # `on_hr_toggle`, a prepinac je uz v polohe vypnute), takze sa
            # ulozila az pri ukonceni appky - a `summary()` medzitym ratal
            # `duration_s` z `time.time()`, cize relacia narastla o cely
            # zvysok vecera. Zatvarame ju tu, kym su cisla este pravdive.
            # Generacia 0 zaroven zahodi spravy z uz mrtveho vlakna.
            self._hr_generation = 0
            self._close_hr_session()
            self.log(tr("log.hr_socket_error", err=payload))
        self.refresh_hr_status_label()
        self._refresh_dnes_stats()
        # Pás aj text pod ensom musia sledovať SKUTOČNÝ stav spojenia
        # (connecting / disconnected / client_gone), nie len prepínač — inak
        # tvrdia "Sledujem tep" aj keď hodinky vypadli (bug A2).
        self._refresh_kamae_state_text()

    def _zaznamenaj_vypadok(self, kind):
        """Tep, ktory appka pocula, prestal chodit - zapamataj si to.

        Vola sa z vetiev `disconnected` a `client_gone` PRED `clear_live`
        (potom uz `hr_stats` nevie, kedy prisla posledna vzorka). Len ked
        appka tep naozaj pocula: vypadok pred prvou vzorkou je "este nic
        neprislo" a ma vlastny text. Obe udalosti mozu prist za sebou (TCP
        spojenie padne az po 12 s ticha, alebo naopak) - druha uz `_hr_last_bpm`
        nema, takze sa ten isty vypadok nerata dvakrat.

        ZIADNY NOVY CASOVAC, ZVUK ANI OKNO. Hranica 12 s je ta ista ako doteraz
        (`heart_rate.STALE_AFTER_S`); tu sa len prestane tvarit, ze hodinky
        ani neboli sparovane (Dnes necha zivy blok a stopu relacie).
        """
        if self._hr_last_bpm is None:
            return
        self._hr_lost = True
        self._hr_lost_od = self.hr_stats.last_beat_ts
        try:
            self.hr_stats.note_dropout(od=self._hr_lost_od)
        except Exception:
            app_log.exception("vypadok tepu sa nepodarilo zapisat")
        app_log.info("tep vypadol (%s)", kind)

    def _tep_je_spat(self):
        """Prva platna vzorka po vypadku: jeden riadok do dennika, nic viac."""
        od = self._hr_lost_od
        self._hr_lost = False
        self._hr_lost_od = None
        if od is None:
            return
        sekund = max(0, int(round(self.hr_stats.last_beat_ts - od)))
        self.log(tr("log.hr_back", s=sekund))
        app_log.info("tep je spat po %d s", sekund)

    # POZN: tu bol `_maybe_trigger_hr_breathing` - starý automatický spúšťač
    # z fázy 1 (tep nad kritickou 5 s → dýchací kruh). Už ho nič nevolalo,
    # nahradil ho `trigger.CueTrigger` (záťaž nad prahom 90 s, odklad na
    # pauzu). Zmazaný aj s konštantami HR_TRIGGER_* (B28). Pomocníci
    # `_hr_overlay_available` / `_warn_hr_overlay_disabled_once` ostávajú -
    # používa ich živá cesta hlášok.

    def _hr_overlay_available(self):
        """True, ak ma aspon JEDEN slot zapnuty in-game vizual.

        Do 19. 9. sa pytala vylucne na slot 3 (dychaci kruh). To bolo spravne,
        kym vsetky hlasky chodili na ten jeden slot - lenze od zavedenia
        striedania kategorii (`_dalsi_cue_slot`) sa hlaska moze dorucit na
        hociktory zo styroch. Brana teda povolila hlasku, ked bezal dychaci
        kruh, a poslala ju na slot, ktory kreslit nemal - alebo naopak
        umlcala appku, ktora mala tri vizualy zapnute a len ten stvrty nie.

        Samotny vyber uz zapnutost vizualu zohladnuje, takze tu staci, ze
        existuje aspon jeden pouzitelny.
        """
        try:
            return any(bool(cfg["enabled"]) for cfg in self.overlay_configs)
        except (KeyError, TypeError):
            return False

    def _warn_hr_overlay_disabled_once(self):
        if self._hr_overlay_warned:
            return
        self._hr_overlay_warned = True
        self.log(tr("log.hr_overlay_disabled"))

    def _retry_hr_bind(self):
        """Skusi znova otvorit UDP prijem po obsadenom porte.

        Nevola `on_hr_toggle` - prepinac je stale zapnuty a nesmie sa hybat.
        Otvara priamo novy socket, rovnako ako `_open_hr_session` pri starte.
        """
        self._hr_retry_job = None
        if not self.hr_monitoring_enabled:
            return                      # hrac medzitym vypol sam
        try:
            self._hr_state = "connecting"
            self.refresh_hr_status_label()
            self._hr_generation = self.heart_rate_monitor.start(self.hr_ip,
                                                                self.hr_port)
            # SOCKET JE SPÄŤ - ALE RELÁCIA SA V "busy" VETVE ZAVRELA.
            #
            # Bez tohto by appka po obnovenom porte ukazovala živý tep, no
            # `_hr_session_open` by ostalo False - `_tick_cue_trigger` sa pri
            # zatvorenej relácii hneď vracia, takže by sa NIKDY neozvala a na
            # konci by neuložila NIČ. Pás pritom sľubuje "sledujem". Otvárame
            # ju nanovo (siete sa to nedotýka; `start()` ju už obnovil),
            # rovnako ako pri štarte. Dáta spred výpadku sú už uložené
            # (`busy` vetva volá `_close_hr_session`, ktorý ukladá).
            self._open_hr_session(prepoj=False, meria=self.listening)
            self._schedule_no_client_check()   # čerstvých 20 s na klienta (B2)
        except Exception:
            app_log.exception("opakovana vazba na UDP port zlyhala")

    def _hr_status_display(self):
        pal = self.pal
        if self._hr_state == "connected" and self._hr_last_bpm is not None:
            # farby pasiem, nie success/danger - inak by stav tepu svietil
            # inou zelenou, nez akou appka kresli pokoj (viz theme.ZONE_TOKENS)
            zone = "critical" if self._hr_last_bpm > self.hr_critical_bpm else "calm"
            return f"❤️ {self._hr_last_bpm} BPM", theme_mod.zone_color(pal, zone)
        if self._hr_state == "linked":
            return tr("settings.hr_status_waiting"), pal["warn"]
        if self._hr_state == "busy":
            # Vlastny stav, nie "Odpojene": hrac vidi presne to, co sa deje,
            # priamo pri prepinaci a nemusi rozbalovat dennik.
            return tr("settings.hr_status_busy"), pal["warn"]
        if self._hr_state == "busy_gave_up":
            # Pokusy vycerpane - uz to neskusa, tak to ani netvrdi (B3).
            return tr("settings.hr_status_busy_gave_up"), pal["danger"]
        if self._hr_state == "connecting":
            return tr("settings.hr_status_connecting"), pal["text_dim"]
        if self._hr_state == "no_client":
            # Počúvame, ale za N s sa nikto nepripojil - iný problém než
            # "pripája sa" (najčastejšie firewall / iná Wi-Fi) (B2).
            return tr("settings.hr_status_no_client"), pal["warn"]
        return tr("settings.hr_status_disconnected"), pal["text_dim"]

    def refresh_hr_status_label(self):
        if self.hr_status_label is None:
            return
        text, color = self._hr_status_display()
        try:
            self.hr_status_label.configure(text=text, text_color=color)
        except Exception:
            pass

    def _tick_session(self):
        """Raz za sekundu obnovi "naposledy sa ozvala pred X min" a pri
        otvorenej relacii skontroluje exkluzivny fullscreen.

        Popri nom bezi este `_tick_activity` (4x za sekundu); vsetko ostatne
        sa prekresluje az na zaklade prichadzajucich dat.

        POZN: bol tu aj `_refresh_kamae_metrics()` - tri cisla vpravo v
        pase. S ich odstranenim (viz `ui_kit.KamaeBar`) uz pas nema co
        posuvat po sekundach.
        """
        try:
            # "Naposledy sa ozvala pred X min" sa pocita z `time.time()` az
            # pri prekresleni. Vsetky ostatne cesty k `_refresh_dnes_stats`
            # visia na prichadzajucom tepe, takze bez tohto riadku sa cislo
            # zastavilo na hodnote spred poslednej vzorky a uz sa nepohlo -
            # a po vypadku hodiniek klamalo donekonecna.
            self._refresh_last_cue()
        except Exception:
            pass
        # Exkluzívny fullscreen: Windows v ňom naše overlay okná nevykreslí,
        # takže vizuál (jadro appky) ticho zmizne. Kontrola má zmysel LEN keď
        # je popredím hra — čo počas relácie väčšinou je, a nikdy to nie je
        # počas `start_heart_rate_monitor`, kde kontrola pôvodne bola a bola
        # preto mŕtva (bug A3). Raz za spustenie appky (flag
        # `_fullscreen_warned` sa nenuluje) - a len ako odhad: rovnako veľké
        # je aj okno bez okrajov, preto text hovorí „ak vizuály nevidíš“.
        if getattr(self, "_hr_session_open", False):
            try:
                self._warn_exclusive_fullscreen_once()
            except Exception:
                pass
        try:
            self.root.after(1000, self._tick_session)
        except Exception:
            pass

    def _tick_activity(self):
        """4x za sekundu sa spyta Windowsu, ako dlho je hrac necinny.

        Je to jedno `GetLastInputInfo` - ziadny hook, ziadna informacia o
        tom, co hrac stlacil. Beha aj mimo relacie, aby `pause_s()` malo
        zmysel hned, ked sa senzor zapne; zaznam do meracich okien sa pri
        zapnuti senzora aj tak vynuluje.

        `after` id sa drzi, aby sa dalo pri ukonceni zrusit - inak by sa
        4x za sekundu zvysovala sanca, ze jeden callback dobehne az nad
        rozobratym oknom.
        """
        try:
            idle = self.activity.poll()
        except Exception:
            idle = None
        # Krivka aktivity do relacie - z nej sa neskor spocita, kedy sa
        # naozaj hralo a kedy sa sedelo v menu. Zapisuje sa LEN pocas
        # relacie, rovnako ako vsetko ostatne: mimo nej by to len riedilo
        # priemer casom, ked hrac appku ani nepouziva.
        if idle is not None and getattr(self, "_hr_session_open", False):
            try:
                self.hr_stats.note_activity(idle <= measure.ACTIVE_IDLE_MS)
            except Exception:
                pass
        try:
            self._tick_nonstop_input()
        except Exception:
            app_log.exception("vstup bez pauzy: tick zlyhal")
        try:
            self._tick_cue_trigger()
        except Exception:
            app_log.exception("spustac hlasky: tick zlyhal")
        try:
            self._activity_job = self.root.after(
                int(activity.POLL_S * 1000), self._tick_activity)
        except Exception:
            self._activity_job = None

    def _tick_nonstop_input(self, now=None):
        """Tichy riadok na Dnes, ked appka uz dlho nevidela ani kratku pauzu
        vo vstupe (`activity.NonstopInputWatch`).

        Stalo sa to zadavatelovi: gyroskop ovladaca hlasil Windowsu vstup
        kazdych ~16 ms a appka nemala kedy najst pauzu. Rata sa, len ked
        appka pocuva a tep chodi (hrac je pri PC). LEN na Dnes - nie v hre,
        nie v HUD-e; hrac to uvidi, ked sa na appku sam pozrie.
        """
        now = time.time() if now is None else now
        watching = bool(self.listening
                        and getattr(self, "_hr_session_open", False)
                        and self._hr_state == "connected"
                        and self._hr_last_bpm is not None
                        and not getattr(self, "_hr_lost", False))
        try:
            potrebna = float(self.cue_trigger.params.get("pause_s", 2.5))
        except Exception:
            potrebna = 2.5
        ukaz = self._nonstop_input.update(
            now, self.activity.pause_s(now), watching, pause_needed_s=potrebna)
        text = ""
        if ukaz and self.listening:
            text = tr("dnes.nonstop_input",
                      min=int(self._nonstop_input.after_s // 60))
        if text != getattr(self, "_dnes_nonstop_text", ""):
            if text:
                app_log.info("vstup: %d min bez jedinej pauzy - riadok na Dnes",
                             int(self._nonstop_input.after_s // 60))
            self._dnes_nonstop_text = text
            self._refresh_dnes_backdrop(force=False)
