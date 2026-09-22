"""Kedy sa hláška natiahne a kedy vystrelí.

PRECO TO NIE JE V app.py
------------------------
Ani jeden test v tests/ neimportuje `app.py` - ten tahá tkinter,
customtkinter, pynput aj pygame (audio_engine pri importe robi
pygame.mixer.init()). Logika, ktora by zila tam, by sa testovat nedala.
Tento modul je cisto datovy: ziadny Tk, ziadne I/O, hodiny sa daju
podstrcit. Rovnaka disciplina ako `measure.py` a `activity.py`.

AKO TO FUNGUJE
--------------
    zataz nad prahom NAZBIERA `stress_hold_s` (default 45 s)   (nie spicka!)
         v                (nie suvisle - kumulativne za klzavym oknom, viz
         v                 `note_load`; realny boj sa vracia dole v cykloch)
    NATIAHNUTE  -  appka este nic nespravi, len caka
         v
    caka na pauzu v aktivite >= 2,5 s, najviac `max_wait_s`
         v
    pauza prisla  ->  hlaska (hlas + vizual)
    pauza neprisla ->  tichy vizual bez hlasu

Cisla vyssie su defaulty pre priemerneho hraca (`default_params`); casom ich
nahradi prah spocitany z vlastnych dat (`hr_stats.dynamicky_prah_zataze`).
Preco nie na spicku: skok po headshote nie je stres, dlhsia zataz ano.
Preco odklad na pauzu: najvyssia potreba a najhorsi moment na prerusenie
su ta ista sekunda.

DVE VECI, KTORE SA NESMU ZLUCIT
-------------------------------
`arm` a `delivery` su ROZNE veci a musia ostat oddelene az do analyzy:

  arm       "voice" / "silent"  - losuje sa pri NATIAHNUTI, este pred
                                  tym, nez sa cokolvek stane. Toto je
                                  tiche kontrolne rameno.
  delivery  "pause" / "timeout" - ako sa to nakoniec doruzilo.

Ked pauza nepride, hlaska ide ticho - ale to NIE JE kontrolne rameno.
Keby sa oboje zapisalo ako "silent", `measure.summarize()` by porovnaval
dve uplne rozne veci: jedna skupina mala pauzu, druha nie, a rozdiel by
meral prave to. Kontrolna skupina by prestala byt kontrolna.

LOSOVANIE MA VLASTNY GENERATOR
------------------------------
`random.Random()` a nie modulovy `random`: `app.fire_slot` pouziva
`random.uniform` na jitter a akykolvek `random.seed()` inde v appke by
posunul aj rameno. Kontrolna skupina by prestala byt nahodna a nikto by
si toho nevsimol.
"""

import random
import time

import measure

# --------------------------------------------------------------------------
# Stavy
# --------------------------------------------------------------------------

DORMANT = "dormant"      # relacia nebezi, tep vypadol, alebo bezi snooze
IDLE = "idle"            # relacia bezi, zataz je pod prahom
RISING = "rising"        # zataz drzi nad prahom, pocita sa suvislost
ARMED = "armed"          # natiahnute, caka sa na pauzu
COOLDOWN = "cooldown"    # prave sa dorucilo, drzi sa odstup

# Udalosti, ktore modul vracia volajucemu
E_ARMED = "armed"
E_DELIVER = "deliver"
E_ABORT = "abort"

# Preco sa natiahnutie zrusilo - zapisuje sa, aby sa dalo ladit
A_ZATAZ_KLESLA = "zataz_klesla"
A_ODISIEL = "odisiel_od_pc"
A_TEP_VYPADOL = "tep_vypadol"
A_SNOOZE = "snooze"
A_KONIEC_RELACIE = "koniec_relacie"
A_NEDALO_SA = "nedalo_sa"

ARM_VOICE = "voice"
ARM_SILENT = "silent"

D_PAUSE = "pause"
D_TIMEOUT = "timeout"


def default_params():
    """Vychodiskove cisla. Su z literatury, nie z tela hraca - zadanie s
    nimi tak aj pocita a prve vecery sa budu ladit.

    Kazda relacia si ich ulozi so sebou (zadanie §3.3): bez toho sa o
    mesiac neda povedat, ci bol rozdiel v tom, co sa zmenilo, alebo v tom,
    ako sa hrac vyspal.
    """
    return {
        # Zataz (hr_stats.stress, 0-100). zone_for: 50 = high, 75 = critical.
        "stress_threshold": 55.0,
        # Ako dlho musi drzat nad prahom, nez sa natiahne.
        #
        # 90 -> 45 PO PRVOM SKUTOCNOM VECERI. The Finals, 36 minut, spicka
        # zataze 87 pri prahu 55, 2:40 v hornych pasmach - a NULA hlasok.
        # Prah teda problem nebol; nikdy sa nenaplnilo "suvisle".
        # Povodnych 90 s bolo pisanych na "dve minuty na 120", co je iny typ
        # hry. V kolovej strielacke ide telo hore-dole v cykloch po
        # desiatkach sekund: umres, respawn, pokoj. 90 s bez vacsieho nez
        # patsekundoveho prepadu tam nenastane prakticky nikdy.
        "stress_hold_s": 45.0,
        # Kratky prepad pod prah natiahnutie NERUSI - stress je vyhladeny
        # exponencialnym priemerom a na hranici kmita. Dlhsi prepad ano.
        #
        # 5 -> 20 z toho isteho dovodu: 5 s prekleni kmitanie vyhladeneho
        # priemeru, ale nie respawn. Dvadsat sekund preklenie aj ten, takze
        # sa jeden bojovy usek nerozpadne na tri kratke.
        "dip_grace_s": 20.0,
        # Pauza v aktivite, ktora sa povazuje za zlomovy bod.
        # POZN: 2,5 s je rozhodnutie zadavatela. Publikovany vyskum
        # (Iqbal & Bailey, CHI 2008) hovori, ze najjemnejsie zlomove body
        # dopadli horsie nez stredne a hrube. Preto je to parameter a
        # preto sa zapisuje do kazdeho okna - z dat sa to da spatne overit.
        "pause_s": 2.5,
        # Najdlhsie, co sa caka na pauzu. 90 s je publikovany, hracmi
        # akceptovany odklad notifikacie.
        "max_wait_s": 90.0,
        # Dlhsia pauza uz nie je mikropauza - hrac odisiel od PC.
        "away_s": 120.0,
        # Minimalny odstup medzi hlaskami. MUSI byt vacsi nez
        # measure.REFRACTORY_AFTER_S (180), inak si dve hlasky navzajom
        # zneplatnia meracie okna a mesiac merania je na nic.
        "min_gap_s": 240.0,
        # Strop hlasok za hodinu (zadanie §2). `min_gap_s` sam nestaci:
        # 240 s odstup dovoli az 15 za hodinu. Odmerane simulaciou - pri
        # vypatom vecere vychadzalo 6,9 za hodinu, cize nad zadanim.
        #
        # Odstup a strop su dve rozne veci: odstup chrani MERANIE (aby si
        # dve hlasky nezneplatnili okna), strop chrani HRACA (aby appka
        # nebola ukecana). Preto su to dva parametre a nie jeden.
        "max_per_hour": 5.0,
    }


# --------------------------------------------------------------------------
# Ako casto sa appka ozve - jeden ovladac namiesto styroch cisel
# --------------------------------------------------------------------------
#
# Prah, drzanie, odstup a strop sa NEDAJU nastavovat samostatne bez toho,
# aby si protirecili: znizit prah bez skratenia drzania neurobi takmer nic
# (telo sa cez prah prehupne, ale suvisly usek sa aj tak nenaplni), a
# skratit odstup bez zvysenia stropu tiez nie (strop zatne skor). Preto sa
# hybu vsetky styri naraz, jednou volbou.
#
# Zvysok cisel (pause_s, max_wait_s, away_s, dip_grace_s) sa NEMENI: to su
# vlastnosti okamihu dorucenia, nie toho, ako casto sa ozve.

# TVRDA POISTKA, nie nastavenie.
#
# Po hlaske bezi meracie okno `measure.REFRACTORY_AFTER_S` (180 s). Keby
# odstup klesol pod nu, druha hlaska by pristala do okna prvej, obe okna by
# sa zneplatnili - a z celeho vecera by neostalo nic na vyhodnotenie.
# Rezerva 30 s kryje to, ze hlaska nepada v okamihu natiahnutia, ale az na
# najblizsej pauze.
MIN_GAP_FLOOR_S = measure.REFRACTORY_AFTER_S + 30.0   # 210 s

CITLIVOST_MENEJ = "menej"
CITLIVOST_BEZNE = "bezne"
CITLIVOST_VIAC = "viac"
CITLIVOSTI = (CITLIVOST_MENEJ, CITLIVOST_BEZNE, CITLIVOST_VIAC)

_CITLIVOST = {
    # Pre vecery, ked appka rusi viac, nez pomaha.
    CITLIVOST_MENEJ: {"stress_threshold": 65.0, "stress_hold_s": 60.0,
                      "min_gap_s": 420.0, "max_per_hour": 3.0},
    # Cisla zo zadania - to, co je vo `default_params()`.
    CITLIVOST_BEZNE: {},
    # Pre telo, ktore sa cez prah prehupne len kratko. Odstup ide na
    # poistku, nie pod nu.
    CITLIVOST_VIAC: {"stress_threshold": 48.0, "stress_hold_s": 30.0,
                     "min_gap_s": MIN_GAP_FLOOR_S, "max_per_hour": 8.0},
}


def params_for(citlivost):
    """Kompletne parametre pre zvolenu citlivost.

    Vracia CELY slovnik, nie len rozdiel - volajuci ho vie rovno pouzit a
    nemusi vediet, ktore kluce sa menia. Neznama hodnota padne na "bezne".
    """
    out = default_params()
    out.update(_CITLIVOST.get(citlivost, _CITLIVOST[CITLIVOST_BEZNE]))
    # Poistka plati aj ked sa niekto v tabulke pomyli.
    out["min_gap_s"] = max(out["min_gap_s"], MIN_GAP_FLOOR_S)
    return out


# Kumulativne okno je nasobok pozadovaneho drzania: pri `stress_hold_s` 45 s
# sa pozera na poslednych 90 s. Zamerne to NIE JE dalsi parameter - bol by to
# piaty knoflik na to iste a nikto by nevedel, ako ho nastavit voci ostatnym.
OKNO_NASOBOK = 2.0

# Najdlhsia medzera medzi vzorkami, ktora sa este rata ako "meralo sa".
# Hodinky posielaju cca kazde 1,5 s; pri vacsej diere sa cas nepripocita,
# aby vypadok spojenia nevyzeral ako drzanie nad prahom.
MAX_KROK_S = 5.0

# Okno, v ktorom sa strop pocita. Nie je to parameter: "za hodinu" je
# jednotka zo zadania, meni sa `max_per_hour`.
HOUR_S = 3600.0


class CueTrigger:
    """Stavovy automat jednej relacie. Bez Tk, bez I/O, s podstrcitelnymi
    hodinami - takze sa da cely prejst v testoch bez cakania."""

    def __init__(self, params=None, rng=None, clock=time.time):
        self.params = dict(default_params())
        if params:
            self.params.update(params)
        self._rng = rng if rng is not None else random.Random()
        self._clock = clock
        self.silent_share = 0.0
        self._delivered_at = []
        self.reset()

    # ---------- zivotny cyklus ----------

    def reset(self):
        self.state = DORMANT
        self._above_since = None     # odkedy zataz drzi nad prahom
        self._below_since = None     # odkedy je pod nim (kvoli tolerancii)
        self._armed_at = None
        self._arm = None             # vylosovane rameno, uz pri natiahnuti
        self._cooldown_until = 0.0
        self._last_load = None
        # Preco je automat pozastaveny. Viz `suspend` / `resume`.
        self._suspended_by = None
        self.armed_count = 0
        self.delivered_count = 0
        self._delivered_at = []
        # PRECO SA TOTO POCITA
        # Prvy skutocny vecer (The Finals, 36 min) skoncil s NULOU hlasok,
        # hoci spicka zataze bola 87 pri prahu 55. Prah teda problem nebol -
        # zlyhala podmienka "SUVISLE stress_hold_s". Zo suhrnu relacie sa to
        # ale nedalo rozlisit od uplne inej priciny (vypadky tepu, ktore
        # pocitadlo suvislosti vynuluju).
        #
        # Tieto styri cisla to rozlisia bez toho, aby sa ukladala cela
        # krivka: ked je najdlhsi beh 40 s, je pravidlo prisne; ked je 10 s
        # a behov su desiatky, su to vypadky.
        # [(cas, dlzka)] usekov nad prahom v kumulativnom okne
        self._nad_okno = []
        self._posledny_load_ts = None
        self._posledny_nad_koniec = None
        self.najdlhsi_nad_s = 0.0    # najdlhsi SUVISLY usek nad prahom
        self.behov_nad = 0           # kolkokrat sa taky usek zacal
        self.zrusenych_prepadom = 0  # ... a skoncil poklesom pod prah
        self.zrusenych_vypadkom = 0  # ... alebo uspanim (vypadok tepu)

    def open_session(self, now=None, silent_share=0.10):
        """Nova relacia. Hodinovy strop sa NEVYNULUJE.

        "Pat za hodinu" je o hracovi, nie o relacii. Keby sa strop cistil s
        kazdou relaciou, stacilo by vypnut a zapnut senzor a appka by mohla
        hovorit dalej - a hrac by to urobil prave vtedy, ked ho stve.
        """
        historia = list(self._delivered_at)
        self.reset()
        self._delivered_at = historia
        self.silent_share = float(silent_share)
        self.state = IDLE
        self._cooldown_until = 0.0
        return None

    def close_session(self, now=None):
        """Relacia konci. Ak sa cakalo na pauzu, je to informacia - podla
        toho, ako casto sa to stava, sa da ladit `max_wait_s`."""
        now = self._clock() if now is None else now
        udalost = None
        if self.state == ARMED:
            udalost = self._abort(A_KONIEC_RELACIE, now)
        self.state = DORMANT
        return udalost

    def suspend(self, reason, now=None):
        """Snooze alebo vypadok tepu. Natiahnutie sa zrusi - nedrzi sa.

        DOVOD SA PAMATA. Bez neho nevie `resume` rozlisit, ci ho zdvihnut
        smie: vypadok tepu ma zdvihnut prva dalsia vzorka, ale snooze ani
        zastavene pocuvanie nie.
        """
        now = self._clock() if now is None else now
        udalost = self._abort(reason, now) if self.state == ARMED else None
        if self._above_since is not None:
            # Rozbehnuty usek nad prahom konci uspanim, nie poklesom. Je to
            # ina pricina a musi sa dat odlisit - viz `reset`.
            self.najdlhsi_nad_s = max(self.najdlhsi_nad_s,
                                      now - self._above_since)
            self.zrusenych_vypadkom += 1
        self._above_since = None
        self._below_since = None
        # NAZBIERANÝ ČAS NAD PRAHOM SA MUSÍ ZAHODIŤ AJ TU.
        #
        # `note_load` má poistku proti diere v dátach, ale tá sa spustí len
        # keď `_above_since is not None` - a to `suspend` práve vynulovalo.
        # Bez tohto by po výpadku 12–40 s (medzi MAX_KROK_S a oknom
        # OKNO_NASOBOK*drzanie) stará nazbieraná záťaž prežila a prvá vzorka
        # po návrate by natiahla hlášku na čase, ktorý nikto nemeral (B4).
        # `_posledny_load_ts=None` zároveň zaručí, že prvý krok po návrate je
        # 0 (žiadny fiktívny prírastok).
        self._nad_okno = []
        self._posledny_load_ts = None
        self._suspended_by = reason
        self.state = DORMANT
        return udalost

    def resume(self, now=None, force=False):
        """Zdvihne pozastavenie. 90 s sa pocita ODZNOVA - polovicne
        natiahnuty stav neexistuje.

        `force=False` znamena "prisla vzorka tepu" a zdvihne LEN vypadok
        tepu. Vola sa z `_apply_hr_bpm`, teda KAZDU SEKUNDU, a preto nesmie
        zdvihnut nic ine: "teraz nie" by zrusil prvy uder srdca o sekundu
        neskor. Odmerane - pri 30-minutovom snooze sa takto natiahlo 10x a
        do kazdeho meracieho okna relacie sa zapisal nafuknuty `natiahnuti`.

        `force=True` je vedome zdvihnutie: koniec snooze, zrusenie snooze,
        spustenie pocuvania.

        ODSTUP MEDZI HLASKAMI SA NESTRACA. Predtym isiel stav rovno na IDLE
        a `_cooldown_until` uz nikto necital, lebo sa cita len v stave
        COOLDOWN - jeden vypadok tepu tak zmazal styri minuty odstupu. A ten
        odstup MUSI byt vacsi nez `measure.REFRACTORY_AFTER_S`, inak si dve
        hlasky navzajom zneplatnia meracie okna.
        """
        if self.state != DORMANT:
            return None
        if not force and self._suspended_by not in (None, A_TEP_VYPADOL):
            return None
        now = self._clock() if now is None else now
        self._suspended_by = None
        self.state = COOLDOWN if now < self._cooldown_until else IDLE
        self._above_since = None
        self._below_since = None
        return None

    # ---------- vstupy ----------

    def note_load(self, stress, now=None):
        """Jedna vzorka zataze. Vola sa z `_apply_hr_bpm` (Tk vlakno).

        Vracia udalost E_ARMED, ked sa prave natiahlo, inak None.
        """
        now = self._clock() if now is None else now
        self._last_load = stress
        if self.state in (DORMANT, ARMED):
            return None
        if self.state == COOLDOWN:
            if now < self._cooldown_until:
                return None
            self.state = IDLE
            self._above_since = None
            self._below_since = None

        prah = self.params["stress_threshold"]
        drzanie = self.params["stress_hold_s"]

        # KUMULATIVNE OKNO namiesto "suvisle nad prahom".
        #
        # Povodne pravidlo vyzadovalo jeden neprerusovany usek. V realnej hre
        # sa telo vracia dole v cykloch po desiatkach sekund (umres, respawn,
        # pokoj), takze suvisly usek dlzky 45 s prakticky nenastane. Merany
        # vecer to ukazal doslova: 88 minut, 13 behov nad prahom, VSETKY
        # zrusene prepadom, najdlhsi 44,1 s pri pozadovanych 45,0 - chybala
        # jedna sekunda a appka nepovedala za cely vecer nic.
        #
        # Teraz sa pocita, kolko casu bolo nad prahom za poslednych
        # `OKNO_NASOBOK * drzanie` sekund. Prepad beh nemaze, len sa
        # nepripocita - to je presne ten rozdiel medzi "telo je pod zatazou"
        # a "telo drzi jednu dlhu krivku".
        krok = 0.0
        diera = False
        if self._posledny_load_ts is not None:
            surovy = max(0.0, now - self._posledny_load_ts)
            diera = surovy > MAX_KROK_S
            krok = min(surovy, MAX_KROK_S)
        self._posledny_load_ts = now

        # DIERA V DATACH NIE JE DRZANIE NAD PRAHOM.
        #
        # Appka na vypadok tepu reaguje aj sama (`_suspend_cue_trigger`
        # s A_TEP_VYPADOL po `heart_rate.STALE_AFTER_S`), ale spoliehat sa
        # na to nestaci: medzi poslednou vzorkou a vyhlasenim vypadku je
        # okno, v ktorom sa nemeria nic - a bez tejto poistky by sa cely ten
        # cas pripisal ako suvisly usek nad prahom. Dvadsatminutovy vypadok
        # spojenia by po navrate natiahol hlasku okamzite, na zaklade casu,
        # ktory nikto nezmeral.
        if diera and self._above_since is not None:
            self.najdlhsi_nad_s = max(self.najdlhsi_nad_s,
                                      self._posledny_nad_koniec - self._above_since
                                      if self._posledny_nad_koniec else 0.0)
            self.zrusenych_vypadkom += 1
            self._above_since = None
            self._below_since = None
            self._nad_okno = []
            if self.state == RISING:
                self.state = IDLE
        if stress >= prah:
            self._posledny_nad_koniec = now
            if krok > 0.0:
                self._nad_okno.append((now, krok))
        hranica = now - OKNO_NASOBOK * drzanie
        while self._nad_okno and self._nad_okno[0][0] < hranica:
            self._nad_okno.pop(0)
        nazbierane = sum(d for _, d in self._nad_okno)

        if stress >= prah:
            self._below_since = None
            if self._above_since is None:
                self._above_since = now
                self.behov_nad += 1
                self.state = RISING
            else:
                self.najdlhsi_nad_s = max(self.najdlhsi_nad_s,
                                          now - self._above_since)
            if (self._above_since is not None
                    and (now - self._above_since >= drzanie
                         or nazbierane >= drzanie)):
                if self._hodina_plna(now):
                    # Strop je vycerpany - NENATIAHNE sa vobec. Natiahnut a
                    # potom nedorucit by znamenalo, ze prstenec na ense
                    # svieti a nic nepride; radsej nech mlci uplne.
                    # Pocita sa odznova, takze sa to skusi o dalsich 90 s,
                    # nie pri kazdej vzorke.
                    self._above_since = now
                    self._nad_okno = []
                    return None
                return self._arm_now(now)
            return None

        # pod prahom - kratky prepad toleruj, dlhsi zrus
        if self._above_since is None:
            return None
        if self._below_since is None:
            self._below_since = now
        elif now - self._below_since > self.params["dip_grace_s"]:
            self.najdlhsi_nad_s = max(self.najdlhsi_nad_s,
                                      self._below_since - self._above_since)
            self.zrusenych_prepadom += 1
            self._above_since = None
            self._below_since = None
            self.state = IDLE
        return None

    def tick(self, pause_s, now=None, can_fire=True):
        """Vola sa 4x za sekundu z `_tick_activity` (Tk vlakno).

        `pause_s` je z `activity.ActivityTracker.pause_s()` a smie byt
        None - to znamena "system idle nehlasi, nevieme". Vtedy sa NECAKA
        na pauzu donekonecna, ale ani sa nepredstiera, ze ziadna nie je:
        necha sa dobehnut `max_wait_s` a dorucis sa ticho. Bez toho by na
        takom stroji vsetky hlasky spadli do tichej vetvy okamzite.

        `can_fire` rozhoduje appka - cooldowny, snooze, dostupnost vizualu.
        Ked je False, natiahnutie sa NESPALI: caka sa dalej.
        """
        now = self._clock() if now is None else now

        if self.state == COOLDOWN and now >= self._cooldown_until:
            self.state = IDLE
            self._above_since = None
            self._below_since = None
            return None
        if self.state != ARMED:
            return None

        cakane = now - self._armed_at

        # Hrac odisiel od PC - to nie je mikropauza, na ktoru sa caka.
        if pause_s is not None and pause_s > self.params["away_s"]:
            return self._abort(A_ODISIEL, now)

        if cakane >= self.params["max_wait_s"]:
            if not can_fire:
                return self._abort(A_NEDALO_SA, now)
            return self._fire(D_TIMEOUT, now, cakane)

        if (pause_s is not None and pause_s >= self.params["pause_s"]
                and can_fire):
            return self._fire(D_PAUSE, now, cakane)
        return None

    # ---------- vnutro ----------

    def _hodina_plna(self, now):
        """Padlo uz v poslednej hodine `max_per_hour` hlasok?

        Klzave okno, nie pevna hodina od zapnutia: pri pevnej by sa na
        prelome mohlo ozvat 5x tesne pred a 5x tesne po sebe, cize 10 hlasok
        v kratkom useku, a strop by formalne platil.
        """
        strop = self.params.get("max_per_hour")
        try:
            strop = float(strop)
        except (TypeError, ValueError):
            return False
        if strop <= 0:
            return False            # 0 alebo zaporne = bez stropu
        self._delivered_at = [t for t in self._delivered_at
                              if now - t < HOUR_S]
        return len(self._delivered_at) >= strop

    def _arm_now(self, now):
        """Natiahnutie. Rameno sa losuje TU - este pred tym, nez sa
        cokolvek stane, aby sa dalo zalogovat aj ked sa hlaska nakoniec
        vobec nedoruci."""
        self.state = ARMED
        self._armed_at = now
        self._above_since = None
        self._below_since = None
        # Nazbierany cas sa spotreboval na TOTO natiahnutie. Bez vycistenia
        # by hned po cooldowne stacila jedna vzorka nad prahom a okno by
        # bolo plne uz od minula.
        self._nad_okno = []
        self._arm = (ARM_SILENT if self._rng.random() < self.silent_share
                     else ARM_VOICE)
        self.armed_count += 1
        return {"typ": E_ARMED, "ts": now, "arm": self._arm,
                "load": self._last_load}

    def _fire(self, delivery, now, waited):
        """Doruci sa. `arm` je vylosovane rameno, `delivery` je sposob -
        su to dve rozne veci (viz hlavicka modulu).

        Zvuk zaznie len ked su splnene OBE: rameno je hlasne a pauza
        naozaj prisla. Vizual sa ukaze vzdy, v oboch ramenach - inak by
        sa ramena nedali porovnat.
        """
        self.state = COOLDOWN
        self._cooldown_until = now + self.params["min_gap_s"]
        self._armed_at = None
        self.delivered_count += 1
        self._delivered_at.append(now)
        arm = self._arm
        self._arm = None
        return {"typ": E_DELIVER, "ts": now, "arm": arm,
                "delivery": delivery, "waited_s": round(waited, 1),
                "hlas": arm == ARM_VOICE and delivery == D_PAUSE,
                "load": self._last_load}

    def _abort(self, reason, now):
        cakane = (now - self._armed_at) if self._armed_at else 0.0
        arm = self._arm
        self.state = IDLE
        self._armed_at = None
        self._arm = None
        self._above_since = None
        self._below_since = None
        return {"typ": E_ABORT, "ts": now, "reason": reason, "arm": arm,
                "waited_s": round(cakane, 1)}

    # ---------- pre UI a pre zapis ----------

    @property
    def is_armed(self):
        return self.state == ARMED

    def snapshot(self):
        """Stav pre UI - stranka Dnes ukazuje 'natiahnute' ako prstenec."""
        return {"state": self.state, "armed": self.state == ARMED,
                "armed_count": self.armed_count,
                "delivered_count": self.delivered_count}


def silent_share_for(session_count, calibration_sessions=15,
                     during=0.25, after=0.10):
    """Podiel tichych hlasok. 25 % pocas kalibracie, potom 10 % navzdy.

    Nikdy nie nula: je to jediny pevny bod, ked sa vyber hlasok zacne
    hybat. Bez kontrolneho ramena vyjde "funguje" vzdy, aj keby appka
    mlcala - tep sa vracia dole aj sam.
    """
    return during if session_count < calibration_sessions else after
