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
    pauza prisla a brana pusti   ->  hlaska (hlas + vizual)
    pauza prisla, brana nepusti  ->  caka dalej, na dalsiu pauzu
    `max_wait_s` bez hlasky      ->  tichy vizual bez hlasu - ale len ked
                                     brana pusti; inak sa natiahnutie zrusi

BRANA (0.2, stress-gate). Hlaska ide len vtedy, ked:
  * pasmo tepu je zname a nie je kriticke (`zona` z `note_load`, teda
    `HeartStats.known_zone` = `zone_of_bpm`; NIKDY pasma zataze `zone_for`),
  * zataz uz nestupa (`_stupa`: posledna hodnota nie je o viac nez
    `STUPA_O` vyssie nez spred `VRCHOL_OKNO_S`; malo dat = stupa),
  * a appka smie (`can_fire`).
Plati pre obe ramena aj pre tichy vizual po `max_wait_s`. Na vrchole a
nad hranicou vysokeho tepu hlaska skor prekazi, nez pomoze (overene to v
hrach nie je - je to opatrnost); appka radsej pocka, kym to zacne
povolovat, a ked sa to nestane, mlci. Pokoj hlasku NERUSI - na to nie je
bezpecnostny dovod a zrusenie by len ubralo hlasky tym, ktori ich uz maju
malo.

V pracovnom svete (0.2, B3-worlds) je hlas vypnuty pre celu relaciu
(`open_session(voice=False)`): vsetko ostatne bezi rovnako, len kazda
hlaska ide tichym vizualom.

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
# Po `max_wait_s` by brana tichy vizual pustila, ale appka nesmela
# (`can_fire`: odstup, snooze, chodza, vypnuty vizual).
A_NEDALO_SA = "nedalo_sa"
# Po `max_wait_s` nepustila brana ani tichy vizual (0.2, stress-gate):
A_BEZ_PAUZY = "bez_pauzy"              # ... a pauza za cele cakanie neprisla
A_NEVHODNA_CHVILA = "nevhodna_chvila"  # ... pauzy prisli, kazdu zastavila

# Zrusenia, pri ktorych sa appka SAMA rozhodla mlcat. Pocitaju sa do
# suhrnu relacie (`zadrzane`); snooze, odchod, vypadok ani koniec relacie
# medzi ne nepatria - to nerozhodla appka.
ZADRZANE = (A_BEZ_PAUZY, A_NEVHODNA_CHVILA, A_NEDALO_SA)

# Pasmo tepu z `hr_stats` (`zone_of_bpm`). Retazec, nie import: modul ostava
# samostatny. None = pasmo nepozname (kalibracia, navrat tepu) -> brana
# nepusti.
ZONA_KRITICKA = "critical"

# "Nestupa": posledna zataz nie je o viac nez STUPA_O vyssie nez posledna
# vzorka stara aspon VRCHOL_OKNO_S. Historia sa drzi HIST_S sekund.
VRCHOL_OKNO_S = 15.0
STUPA_O = 1.0
HIST_S = 40.0

# Co zastavilo pauzu (pocita sa raz za pauzu, do udalosti ako `skipped`).
P_NEZNAME = "nezname_pasmo"
P_KRITICKE = "kriticke"
P_STUPA = "stupa"
P_NESMIE = "nesmie"

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
        # Zataz (hr_stats.stress, 0-100). Slovo pasma na HUD-e/Dnes s tym
        # NESUVISI - to je tep voci pokoju (HeartStats.zone); "Vysoka" teda
        # neznamena "nad prahom" ani "hlaska ide".
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
        # Smie sa vobec natiahnut? False = stupen "pauza" z rebrika
        # (`rebrik.py`): automat sa sprava ako pri plnej hodine - nenatiahne
        # sa, ale diagnostika (behy nad prahom, pauzy) sa zbiera dalej.
        "cues_enabled": True,
        # Znacka brany (0.2, stress-gate). Kazde okno si parametre nesie
        # (`app._save_measure_windows`), takze okna po zmene casovania sa
        # nezlucia so starsimi (`measure.by_category`).
        "brana": "po_vrchole",
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

# STROP NA KREDIT: najviac tolkoto sekund sa z JEDNEJ medzery medzi vzorkami
# pripise do kumulativneho okna ako "meralo sa". Dlhsia medzera sa zapocita
# len do tejto hranice - cas, ktory nikto nemeral, sa nerata ako drzanie.
#
# Kadencia hodiniek NIE JE 1,5 s, ako tu stalo predtym. Namerane: ~0,9 s aj
# ~2,9 s na vzorku podla toho, co hodinky posielaju (od 20. 9. sa tep v OBS
# strieda s krokmi - zdroje Tep/Steps/steps), a pri ~2,9 s je jeden strateny
# paket medzera ~5,6 s. Chvost medzier tesne nad 5 s je teda BEZNY, nie
# vypadok - o vypadku rozhoduje az `DIERA_S`.
MAX_KROK_S = 5.0

# OD AKEJ MEDZERY JE TO VYPADOK, nie len ridsia kadencia hodiniek.
#
# Rovnake cislo ako `heart_rate.HeartRateMonitor.STALE_AFTER_S` (test to
# strazi): kratsiu medzeru appka za vypadok nepovazuje - HUD ukazuje posledny
# tep a "Odpojene" nehlasi - tak ju nesmie za vypadok povazovat ani spustac.
#
# Predtym tuto ulohu robil `MAX_KROK_S` (5 s) a kazda dlhsia medzera zmazala
# cely nazbierany cas. Vecery od 20. 9. (kadencia ~2,9 s): 199 usekov nad
# prahom, 194 z nich zrusenych "vypadkom", za vyse 4 hodiny JEDNA hlaska - a
# po vecere veta "Tep 119x vypadol", hoci skutocnych vypadkov (12 s a viac)
# mohlo byt v tom vecere najviac 5.
DIERA_S = 12.0

# Okno, v ktorom sa strop pocita. Nie je to parameter: "za hodinu" je
# jednotka zo zadania, meni sa `max_per_hour`.
HOUR_S = 3600.0


def _nove_preskocene():
    """Pocty pauz, ktore brana zastavila, podla prekazky (od natiahnutia)."""
    return {P_NEZNAME: 0, P_KRITICKE: 0, P_STUPA: 0, P_NESMIE: 0}


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
        # Smie hlaska vobec zazniet? False v PRACOVNOM svete (B3-worlds):
        # tam ide kazda hlaska len obrazom. Plati pre celu relaciu - svet sa
        # urcuje pri jej otvoreni (`open_session`), nie priebezne.
        self.voice = True
        self._delivered_at = []
        self.reset()

    # ---------- zivotny cyklus ----------

    def reset(self):
        self.state = DORMANT
        self._above_since = None     # odkedy zataz drzi nad prahom
        self._below_since = None     # odkedy je pod nim (kvoli tolerancii)
        # Sucet skoncenych tolerovanych prepadov v tomto useku. Do drzania sa
        # NERATAJU - viz `_nad_v_behu`. Nuluje sa vsade s `_above_since`.
        self._prepady_s = 0.0
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
        # Najdlhsi usek nad prahom - LEN cas naozaj nad prahom, tolerovane
        # prepady sa nerataju (0.2.1, `_nad_v_behu`). Veta po relacii ho
        # porovnava so `stress_hold_s`, takze musi merat to iste co spustac.
        self.najdlhsi_nad_s = 0.0
        self.behov_nad = 0           # kolkokrat sa taky usek zacal
        self.zrusenych_prepadom = 0  # ... a skoncil poklesom pod prah
        # ... alebo vypadkom tepu: medzera >= DIERA_S, alebo
        # suspend(A_TEP_VYPADOL). Snooze sem NEPATRI.
        self.zrusenych_vypadkom = 0
        # BRANA (viz hlavicka modulu).
        self._zona = None            # pasmo tepu z poslednej vzorky
        self._load_hist = []         # [(cas, zataz)] za HIST_S
        self._vrchol = None          # najvyssia zataz od natiahnutia
        self._preskocene = _nove_preskocene()
        self._preskocena_pauza = None
        # KOLKO PAUZ APPKA ZA RELACIU VOBEC VIDELA (prechody do pauzy
        # >= `pause_s`). Nula za dlhy vecer znamena, ze hlas nemal kedy
        # zaznet - a casto, ze nieco hlasi vstup bez prestavky (gyro v
        # ovladaci). Bez toho cisla by sa to nedalo odlisit od pokoja.
        self.pause_episodes = 0
        self._v_pauze = False
        # Kolko natiahnuti appka sama zrusila, podla dovodu (`ZADRZANE`).
        self.zadrzane = {r: 0 for r in ZADRZANE}

    def open_session(self, now=None, silent_share=0.10, voice=True):
        """Nova relacia. Hodinovy strop sa NEVYNULUJE.

        "Pat za hodinu" je o hracovi, nie o relacii. Keby sa strop cistil s
        kazdou relaciou, stacilo by vypnut a zapnut senzor a appka by mohla
        hovorit dalej - a hrac by to urobil prave vtedy, ked ho stve.

        `voice=False` = pracovny svet: automat bezi rovnako (natiahnutie,
        pauza, rameno sa losuje dalej), len `hlas` pri doruceni je vzdy
        False - hlaska ide len obrazom. Rameno sa NEPREPISUJE: vylosovane
        je pred dorucenim a zlucit ho so sposobom dorucenia sa nesmie (viz
        hlavicka modulu); okno si nesie svet, takze sa to da oddelit.
        """
        historia = list(self._delivered_at)
        self.reset()
        self._delivered_at = historia
        self.silent_share = float(silent_share)
        self.voice = bool(voice)
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
                                      self._nad_v_behu())
            # Za vypadok sa rata LEN vypadok tepu. "Teraz nie" (snooze) je
            # rozhodnutie hraca, nie chyba hodiniek - inak by mu appka po
            # vecere napisala "Tep 3x vypadol, daj hodinky blizsie", hoci
            # ju len trikrat umlcal.
            if reason == A_TEP_VYPADOL:
                self.zrusenych_vypadkom += 1
        self._above_since = None
        self._below_since = None
        self._prepady_s = 0.0
        # NAZBIERANÝ ČAS NAD PRAHOM SA MUSÍ ZAHODIŤ AJ TU.
        #
        # `note_load` má poistku proti diere v dátach, ale tá sa spustí len
        # keď `_above_since is not None` - a to `suspend` práve vynulovalo.
        # Bez tohto by po výpadku dlhšom než `DIERA_S`, ale kratšom než okno
        # `OKNO_NASOBOK*drzanie`, stará nazbieraná záťaž prežila a prvá vzorka
        # po návrate by natiahla hlášku na čase, ktorý nikto nemeral (B4).
        # `_posledny_load_ts=None` zároveň zaručí, že prvý krok po návrate je
        # 0 (žiadny fiktívny prírastok).
        self._nad_okno = []
        self._posledny_load_ts = None
        # Ani "stupa/nestupa" sa neporovnava cez dieru - po navrate sa
        # historia zataze zbiera odznova.
        self._load_hist = []
        # SLABSI DOVOD NEPREPISE SILNEJSI. Vypadok tepu pocas "teraz nie"
        # (od 24. 9. relaciu nezatvara, meria sa dalej) by inak prepisal
        # dovod na `A_TEP_VYPADOL` - a prva vzorka po navrate by cez
        # `resume()` bez `force` snooze ticho zrusila (REVIZIA_2_NALEZY).
        if not (reason == A_TEP_VYPADOL
                and self._suspended_by not in (None, A_TEP_VYPADOL)):
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
        self._prepady_s = 0.0
        return None

    # ---------- vstupy ----------

    def note_load(self, stress, now=None, calibrating=False, zona=None):
        """Jedna vzorka zataze. Vola sa z `_apply_hr_bpm` (Tk vlakno).

        Vracia udalost E_ARMED, ked sa prave natiahlo, inak None.

        `calibrating=True` (`HeartStats.is_calibrating`) znamena, ze relacia
        este nema vlastnu zakladnu a zataz je len odhad. Vtedy sa NIC
        nenazbiera: bez toho by sa pri citlivosti "viac" (30 s drzania) dalo
        natiahnut este pocas kalibracie, a pri beznej by cas nazbierany v nej
        skratil cakanie hned po nej. Radsej prvu minutu ticho, nez hlaska
        postavena na cisle, ktoremu appka sama neveri.

        `zona` je pasmo TEPU (`HeartStats.known_zone`), nie pasmo zataze.
        None = nepozname - a vtedy brana hlasku nepusti. Default je None
        zamerne: volajuci, ktory pasmo zabudne poslat, dostane ticho, nie
        hlas nad hranicou vysokeho tepu.
        """
        now = self._clock() if now is None else now
        self._last_load = stress
        # BRANA sa krmi pri KAZDEJ vzorke - aj v stave ARMED, lebo prave
        # vtedy sa podla nej rozhoduje (preto pred navratom nizsie).
        self._zona = zona
        self._load_hist.append((now, stress))
        while self._load_hist and self._load_hist[0][0] < now - HIST_S:
            self._load_hist.pop(0)
        if self.state == ARMED:
            self._vrchol = (stress if self._vrchol is None
                            else max(self._vrchol, stress))
        if self.state in (DORMANT, ARMED):
            return None
        if calibrating:
            # Ako diera v datach: nazbierany cas prec a prvy krok po
            # kalibracii je nula (`_posledny_load_ts=None`), nie fiktivny
            # prirastok za celu kalibraciu.
            self._above_since = None
            self._below_since = None
            self._prepady_s = 0.0
            self._nad_okno = []
            self._posledny_load_ts = None
            if self.state == RISING:
                self.state = IDLE
            return None
        if self.state == COOLDOWN:
            if now < self._cooldown_until:
                return None
            self.state = IDLE
            self._above_since = None
            self._below_since = None
            self._prepady_s = 0.0

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
            # Dve rozne hranice, dve rozne otazky (viz `DIERA_S`): vypadok
            # je medzera `DIERA_S` a viac, kredit z jednej medzery je
            # najviac `MAX_KROK_S`.
            diera = surovy >= DIERA_S
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
        #
        # RIDSIA KADENCIA ALE DIERA NIE JE. Medzera kratsia nez `DIERA_S`
        # usek nerusi a okno nemaze; do okna z nej ide najviac `MAX_KROK_S`.
        # POCTIVO: to plati len pre okno (`nazbierane`). Suvisla cesta nizsie
        # (`_nad_v_behu`) meria nastenne hodiny, takze ticho kratsie nez
        # `DIERA_S` po vzorke NAD prahom v nej zaratane JE - rovnako, ako ho
        # appka inde povazuje za "pripojene" a HUD vtedy ukazuje posledny
        # tep. Cas POD prahom (tolerovany prepad) sa v nej ale nerata.
        if diera and self._above_since is not None:
            # K poslednej vzorke nad prahom, nie po `now` - dieru nikto
            # nemeral (`_nad_v_behu`).
            self.najdlhsi_nad_s = max(self.najdlhsi_nad_s,
                                      self._nad_v_behu())
            self.zrusenych_vypadkom += 1
            self._above_since = None
            self._below_since = None
            self._prepady_s = 0.0
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
            if self._below_since is not None:
                # Tolerovany prepad sa skoncil. Usek zije dalej, ale cas pod
                # prahom sa do drzania nepripise (`_nad_v_behu`).
                self._prepady_s += now - self._below_since
            self._below_since = None
            if self._above_since is None:
                self._above_since = now
                self.behov_nad += 1
                self.state = RISING
            else:
                self.najdlhsi_nad_s = max(self.najdlhsi_nad_s,
                                          self._nad_v_behu())
            # `_nad_v_behu()` je tu cas k `now` - tato vzorka je posledna
            # nad prahom (`_posledny_nad_koniec = now` vyssie).
            if (self._above_since is not None
                    and (self._nad_v_behu() >= drzanie
                         or nazbierane >= drzanie)):
                if (self._hodina_plna(now)
                        or not self.params.get("cues_enabled", True)):
                    # Strop je vycerpany (alebo rebrik hlasky vypol) -
                    # NENATIAHNE sa vobec. Natiahnut a
                    # potom nedorucit by znamenalo, ze prstenec na ense
                    # svieti a nic nepride; radsej nech mlci uplne.
                    # Pocita sa odznova, takze sa to skusi o dalsich 90 s,
                    # nie pri kazdej vzorke.
                    self._above_since = now
                    self._prepady_s = 0.0
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
                                      self._nad_v_behu())
            self.zrusenych_prepadom += 1
            self._above_since = None
            self._below_since = None
            self._prepady_s = 0.0
            self.state = IDLE
        return None

    def tick(self, pause_s, now=None, can_fire=True):
        """Vola sa 4x za sekundu z `_tick_activity` (Tk vlakno).

        `pause_s` je z `activity.ActivityTracker.pause_s()` a smie byt
        None - to znamena "system idle nehlasi, nevieme". Vtedy sa NECAKA
        na pauzu donekonecna, ale ani sa nepredstiera, ze nejaka je:
        necha sa dobehnut `max_wait_s` a potom plati to iste ako bez pauzy
        (tichy vizual, ak brana pusti). Hlas bez pauzy nezaznie nikdy.

        `can_fire` rozhoduje appka - cooldowny, snooze, dostupnost vizualu.
        Ked je False, natiahnutie sa NESPALI: caka sa dalej.

        BRANA (viz hlavicka modulu) plati na pauze aj po `max_wait_s`, pre
        obe ramena rovnako - inak by tiche rameno prestalo byt kontrolne.
        """
        now = self._clock() if now is None else now

        # Pauzy sa pocitaju v KAZDOM stave (aj mimo natiahnutia): otazka je,
        # ci ich appka za vecer vobec vidi, nie ci na ne prave caka.
        pauza = pause_s is not None and pause_s >= self.params["pause_s"]
        if pauza and not self._v_pauze:
            self.pause_episodes += 1
        self._v_pauze = pauza

        if self.state == COOLDOWN and now >= self._cooldown_until:
            self.state = IDLE
            self._above_since = None
            self._below_since = None
            self._prepady_s = 0.0
            return None
        if self.state != ARMED:
            return None

        cakane = now - self._armed_at

        # Hrac odisiel od PC - to nie je mikropauza, na ktoru sa caka.
        if pause_s is not None and pause_s > self.params["away_s"]:
            return self._abort(A_ODISIEL, now)

        prekazka = self._prekazka(now)

        if cakane >= self.params["max_wait_s"]:
            # Tichy obrazok bez pauzy - ale nie na vrchole ani nad hranicou
            # vysokeho tepu. Radsej nic nez obrazok uprostred najhorsieho.
            if prekazka is None:
                if can_fire:
                    return self._fire(D_TIMEOUT, now, cakane)
                return self._abort(A_NEDALO_SA, now)
            dovod = (A_NEVHODNA_CHVILA if any(self._preskocene.values())
                     else A_BEZ_PAUZY)
            return self._abort(dovod, now)

        if not pauza:
            return None
        if prekazka is None and not can_fire:
            prekazka = P_NESMIE
        if prekazka is None:
            return self._fire(D_PAUSE, now, cakane)
        # Pauza prisla, ale chvila nie je vhodna - caka sa na dalsiu. Rata
        # sa raz za pauzu, nie 4x za sekundu.
        if self._preskocena_pauza != self.pause_episodes:
            self._preskocene[prekazka] += 1
            self._preskocena_pauza = self.pause_episodes
        return None

    # ---------- vnutro ----------

    def _nad_v_behu(self):
        """Kolko sekund rozbehnuteho useku bolo naozaj NAD prahom - k
        poslednej vzorke nad nim.

        TOLEROVANY PREPAD NIE JE DRZANIE (0.2.1). `dip_grace_s` len drzi usek
        nazive, aby ho respawn nerozbil na tri kratke. Suvisla cesta sa ale
        predtym pocitala ako `now - _above_since`, teda nastennymi hodinami
        VRATANE prepadov: vzorec "1 s nad prahom, 19 s pod nim" natiahol
        hlasku po minute, hoci nad prahom boli styri vzorky. README slubuje
        hlasku, ked zataz nad hranicou "stravi dost casu" - a appka ma radsej
        mlcat, nez sa ozvat naplano.

        Prepad trva od prvej vzorky pod prahom po prvu nad nim (`_prepady_s`).
        Kratke ticho PO VZORKE NAD prahom sa rata ako nad, ked usek pokracuje
        dalsou vzorkou nad prahom - viz POCTIVO v `note_load`.

        PRECO K POSLEDNEJ VZORKE NAD PRAHOM, a nie k `now`. Presne toto
        cislo vidi podmienka natiahnutia a z neho ide `najdlhsi_nad_s` do
        vety "najdlhsie X s, treba Y s". Keby sa pri konci useku pripocital
        aj cas po poslednej vzorke nad prahom - rozbehnuty prepad, alebo 12 s
        bez dat pred `suspend(A_TEP_VYPADOL)` - veta by o useku, ktory sa
        nenatiahol, tvrdila "najdlhsie 46 s, treba 45 s".

        `is None`, nie pravdivost: cas 0.0 je platny cas (hodiny sa daju
        podstrcit), nie "chyba".
        """
        if self._above_since is None or self._posledny_nad_koniec is None:
            return 0.0
        return max(0.0, self._posledny_nad_koniec - self._above_since
                   - self._prepady_s)

    def _prekazka(self, now):
        """Co z tela brani hlaske PRAVE TERAZ, alebo None.

        Poradie je poradie dolezitosti: nezname pasmo, kriticke pasmo,
        stupajuca zataz. `can_fire` sem nepatri - to nie je telo, ale
        appka (a do dovodu zrusenia ide zvlast)."""
        if self._zona is None:
            return P_NEZNAME
        if self._zona == ZONA_KRITICKA:
            return P_KRITICKE
        if self._stupa(now):
            return P_STUPA
        return None

    def _stupa(self, now):
        """Stupa zataz este? Posledna hodnota vs. posledna vzorka stara
        aspon `VRCHOL_OKNO_S`. Ked sa to povedat neda (menej nez dve
        vzorky, alebo ziadna taka stara), berie sa to ako "stupa" - chyba
        smerom k tichu, nie k hlasu na vrchole."""
        h = self._load_hist
        if len(h) < 2:
            return True
        ref = None
        for ts, hodnota in h:
            if ts <= now - VRCHOL_OKNO_S:
                ref = hodnota
            else:
                break
        if ref is None:
            return True
        return h[-1][1] - ref > STUPA_O

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
        self._prepady_s = 0.0
        # Nazbierany cas sa spotreboval na TOTO natiahnutie. Bez vycistenia
        # by hned po cooldowne stacila jedna vzorka nad prahom a okno by
        # bolo plne uz od minula.
        self._nad_okno = []
        # Brana: vrchol sa sleduje od tejto chvile, preskocene pauzy odznova.
        self._vrchol = self._last_load
        self._preskocene = _nove_preskocene()
        self._preskocena_pauza = None
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
        sa ramena nedali porovnat. V pracovnom svete (`voice=False`) zvuk
        nezaznie nikdy.
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
                "hlas": (arm == ARM_VOICE and delivery == D_PAUSE
                         and self.voice),
                "load": self._last_load, **self._brana_zaznam()}

    def _abort(self, reason, now):
        cakane = (now - self._armed_at) if self._armed_at else 0.0
        arm = self._arm
        self.state = IDLE
        self._armed_at = None
        self._arm = None
        self._above_since = None
        self._below_since = None
        self._prepady_s = 0.0
        if reason in self.zadrzane:
            self.zadrzane[reason] += 1
        return {"typ": E_ABORT, "ts": now, "reason": reason, "arm": arm,
                "waited_s": round(cakane, 1), **self._brana_zaznam()}

    def _brana_zaznam(self):
        """Co brana videla - do udalosti (hr_events), aby sa dalo spatne
        overit, ze hlas nezaznel na vrchole ani nad hranicou."""
        return {"zone_at": self._zona, "load_peak": self._vrchol,
                "skipped": dict(self._preskocene)}

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
