# -*- coding: utf-8 -*-
"""Brána hlášky (0.2, stress-gate): hlas až po vrchole, nikdy nad hranicou.

Hláška sa predtým po natiahnutí prestala pozerať na telo. Prehovorila na
prvej 2,5 s pauze, aj keď záťaž ešte stúpala (často hneď po smrti v hre), a
nad nameranou hranicou vysokého tepu rovnako nahlas. Keď do 90 s pauza
neprišla, ukázala obrázok aj uprostred boja.

Teraz ide hláška (hlas aj jej zvuk) len na pauze, a len keď:
  * pásmo tepu je známe a nie je kritické (`HeartStats.known_zone`),
  * záťaž už nestúpa (posledná hodnota vs. spred 15 s, nanajvýš +1),
  * appka smie (`can_fire`).
Tichý obrázok po 90 s ostáva, ale za tou istou bránou; inak sa natiahnutie
zruší s dôvodom. Pokoj hlášku NEruší.

Testy idú realistickou kadenciou: vzorka tepu každé 3 s, tik 4x za sekundu,
pauza v hre trvá, kým hráč nič nestlačí (nie je to jeden tik).
"""
import ast
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import heart_rate  # noqa: E402
import hr_stats  # noqa: E402
import i18n  # noqa: E402
import measure  # noqa: E402
import trigger  # noqa: E402

KOREN = os.path.join(os.path.dirname(__file__), "..")


class Hodiny:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class Hra:
    """Automat + hodiny + stav pauzy, ako ich kŕmi appka."""

    TIK_S = 0.25

    def __init__(self, silent_share=0.0, **params):
        self.h = Hodiny()
        self.t = trigger.CueTrigger(params=params, rng=random.Random(1),
                                    clock=self.h)
        self.t.open_session(silent_share=silent_share)
        self.pauza_od = None
        self.udalosti = []

    def krok(self, zataz, zona="high", pauza=False, dt=3.0, nevieme=False):
        """Jedna vzorka tepu a tiky počas `dt`. `pauza=True` = hráč práve
        nič nestláča (pauza začne alebo pokračuje). Vráti nové udalosti."""
        nove = []
        ev = self.t.note_load(zataz, self.h.t, zona=zona)
        if ev:
            nove.append(ev)
        if pauza and self.pauza_od is None:
            self.pauza_od = self.h.t
        if not pauza:
            self.pauza_od = None
        for _ in range(int(round(dt / self.TIK_S))):
            self.h.t += self.TIK_S
            if nevieme:
                p = None
            elif self.pauza_od is not None:
                p = self.h.t - self.pauza_od
            else:
                p = 0.0
            ev = self.t.tick(pause_s=p, now=self.h.t)
            if ev:
                nove.append(ev)
        self.udalosti += nove
        return nove

    def natiahni(self, zataz=80.0, zona="high"):
        for _ in range(60):
            if any(e["typ"] == trigger.E_ARMED for e in self.krok(zataz, zona)):
                return
        raise AssertionError("nenatiahlo sa")


def _typu(udalosti, typ):
    return [e for e in udalosti if e["typ"] == typ]


# --------------------------------------------------------------------------
# Hlas až po vrchole
# --------------------------------------------------------------------------

def test_stupajuca_zataz_a_pauza_po_smrti_nehovori():
    """Najčastejší prípad: záťaž ide hore, hráč umrie, death cam = pauza."""
    g = Hra()
    g.natiahni(75.0)
    evs = []
    for i in range(6):                          # stúpa 80 -> 100
        evs += g.krok(80.0 + i * 4, pauza=i >= 3)   # od 4. vzorky pauza 9 s
    assert not _typu(evs, trigger.E_DELIVER), "hlas počas stúpania"
    assert g.t.state == trigger.ARMED, "čaká sa ďalej, nezruší sa"
    assert g.t._preskocene[trigger.P_STUPA] == 1, "jedna pauza, jeden záznam"
    assert g.t.pause_episodes == 1


def test_po_vrchole_na_pauze_jedna_hlasna_hlaska():
    g = Hra()
    g.natiahni(75.0)
    for i in range(6):                          # vrchol 75 -> 100
        g.krok(75.0 + i * 5)
    evs = []
    for i in range(8):                          # klesá 99 -> 71, potom pauza
        evs += g.krok(99.0 - i * 4, pauza=i >= 6)
    d = _typu(evs, trigger.E_DELIVER)
    assert len(d) == 1
    assert d[0]["hlas"] is True and d[0]["delivery"] == trigger.D_PAUSE
    assert d[0]["load"] < d[0]["load_peak"]
    assert d[0]["load_peak"] >= 100.0
    assert d[0]["zone_at"] == "high"


def test_pokoj_hlasku_nerusi():
    """Žiadne zrušenie v pokoji: pokojné telo si hlášku so stresom nespojí
    a zrušenie by len ubralo hlášky tým, čo ich majú málo."""
    g = Hra()
    g.natiahni(70.0)
    evs = []
    for i in range(10):
        evs += g.krok(70.0 - i, zona="calm", pauza=i >= 7)
    assert not _typu(evs, trigger.E_ABORT)
    d = _typu(evs, trigger.E_DELIVER)
    assert len(d) == 1 and d[0]["hlas"] is True
    assert d[0]["zone_at"] == "calm"


# --------------------------------------------------------------------------
# Nad hranicou vysokého tepu mlčí
# --------------------------------------------------------------------------

def test_kriticke_pasmo_s_pauzami_mlci():
    g = Hra()
    g.natiahni(90.0, zona="critical")
    evs = []
    for i in range(20):                         # klesá, ale tep je stále hore
        evs += g.krok(95.0 - i, zona="critical", pauza=i % 2 == 1)
    assert not _typu(evs, trigger.E_DELIVER)
    assert g.t._preskocene[trigger.P_KRITICKE] >= 5


def test_kriticke_cele_cakanie_zrusi_s_dovodom():
    g = Hra()
    g.natiahni(90.0, zona="critical")
    evs = []
    for i in range(40):                         # 120 s kritického plata
        evs += g.krok(90.0, zona="critical", pauza=i % 3 == 2)
    assert not _typu(evs, trigger.E_DELIVER), "ani obrázok nad hranicou"
    ab = _typu(evs, trigger.E_ABORT)
    assert len(ab) == 1
    assert ab[0]["reason"] == trigger.A_NEVHODNA_CHVILA
    assert ab[0]["skipped"][trigger.P_KRITICKE] >= 1
    assert ab[0]["zone_at"] == "critical"
    assert g.t.zadrzane[trigger.A_NEVHODNA_CHVILA] == 1


# --------------------------------------------------------------------------
# Bez pauzy: tichý obrázok po 90 s, ale len cez bránu
# --------------------------------------------------------------------------

def test_bez_pauzy_klesajuca_nekriticka_jeden_obrazok_po_90_s():
    g = Hra()
    g.natiahni(85.0)
    evs = []
    for i in range(40):                         # 120 s, hráč nepustí vstup
        evs += g.krok(85.0 - i * 0.5)
    d = _typu(evs, trigger.E_DELIVER)
    assert len(d) == 1, "jeden obrázok, nie viac"
    assert d[0]["delivery"] == trigger.D_TIMEOUT
    assert d[0]["hlas"] is False, "bez pauzy nikdy hlas"
    assert d[0]["waited_s"] >= 90.0
    assert not _typu(evs, trigger.E_ABORT)


def test_bez_pauzy_v_kritickom_pasme_zrusi():
    g = Hra()
    g.natiahni(90.0, zona="critical")
    evs = []
    for _ in range(40):
        evs += g.krok(90.0, zona="critical")
    assert not _typu(evs, trigger.E_DELIVER)
    ab = _typu(evs, trigger.E_ABORT)
    assert len(ab) == 1 and ab[0]["reason"] == trigger.A_BEZ_PAUZY
    assert g.t.zadrzane[trigger.A_BEZ_PAUZY] == 1


def test_bez_pauzy_pri_stupajucej_zatazi_zrusi():
    g = Hra()
    g.natiahni(70.0)
    evs = []
    for i in range(40):                         # stále stúpa
        evs += g.krok(70.0 + i)
    assert not _typu(evs, trigger.E_DELIVER), "obrázok uprostred stúpania"
    ab = _typu(evs, trigger.E_ABORT)
    assert len(ab) == 1 and ab[0]["reason"] == trigger.A_BEZ_PAUZY


def test_ked_brana_pusti_ale_appka_nesmie_je_to_nedalo_sa():
    """Odstup/snooze/chôdza (`can_fire`) nie je telo - vlastný dôvod."""
    g = Hra()
    g.natiahni(80.0)
    h, t = g.h, g.t
    ev = None
    for _ in range(95 * 4):
        h.t += 0.25
        if int(h.t * 4) % 12 == 0:
            t.note_load(80.0, h.t, zona="high")
        ev = t.tick(pause_s=0.0, now=h.t, can_fire=False) or ev
        if ev:
            break
    assert ev["typ"] == trigger.E_ABORT
    assert ev["reason"] == trigger.A_NEDALO_SA
    assert t.zadrzane[trigger.A_NEDALO_SA] == 1


# --------------------------------------------------------------------------
# Neznáme pásmo = žiadny hlas
# --------------------------------------------------------------------------

def test_nezname_pasmo_nehovori():
    """Volajúci, ktorý pásmo nepošle (alebo ho appka nepozná), dostane ticho,
    nie hlas nad hranicou."""
    g = Hra()
    g.natiahni(80.0, zona=None)
    evs = []
    for i in range(40):
        evs += g.krok(80.0, zona=None, pauza=i % 3 == 2)
    assert not _typu(evs, trigger.E_DELIVER)
    ab = _typu(evs, trigger.E_ABORT)
    assert ab and ab[0]["reason"] == trigger.A_NEVHODNA_CHVILA
    assert ab[0]["skipped"][trigger.P_NEZNAME] >= 1

    g = Hra()
    g.natiahni(80.0)
    assert g.t.note_load(80.0, g.h.t) is None   # default zona=None
    assert g.t._zona is None


def test_neznama_pauza_nikdy_hlas():
    g = Hra()
    g.natiahni(80.0)
    evs = []
    for _ in range(40):
        evs += g.krok(80.0, nevieme=True)
    d = _typu(evs, trigger.E_DELIVER)
    assert len(d) == 1 and d[0]["delivery"] == trigger.D_TIMEOUT
    assert d[0]["hlas"] is False
    assert g.t.pause_episodes == 0


# --------------------------------------------------------------------------
# Počítadlo páuz
# --------------------------------------------------------------------------

def test_pause_episodes_pocita_prechody_do_pauzy():
    h = Hodiny()
    t = trigger.CueTrigger(rng=random.Random(1), clock=h)
    t.open_session(silent_share=0.0)
    for p in (0.0, 1.0, 2.4, 2.5, 3.0, 9.0, 0.0,   # 1. pauza (od 2,5 s)
              3.0, 3.25,                            # 2. pauza
              None, 2.6,                            # nevieme ju preruší, 3.
              0.0, 0.0):
        h.t += 0.25
        t.tick(pause_s=p, now=h.t)
    assert t.pause_episodes == 3

    # ráta sa v každom stave, aj počas snooze
    t.suspend(trigger.A_SNOOZE, now=h.t)
    for p in (0.0, 3.0, 0.0):
        h.t += 0.25
        t.tick(pause_s=p, now=h.t)
    assert t.pause_episodes == 4

    # a nová relácia začína od nuly
    t.open_session(silent_share=0.0)
    assert t.pause_episodes == 0
    assert t.zadrzane == {r: 0 for r in trigger.ZADRZANE}


def test_snooze_ani_koniec_relacie_sa_neratajú_ako_zadrzane():
    g = Hra()
    g.natiahni(80.0)
    g.t.suspend(trigger.A_SNOOZE, now=g.h.t)
    g.t.resume(now=g.h.t, force=True)
    g.natiahni(80.0)
    g.t.close_session(now=g.h.t)
    assert sum(g.t.zadrzane.values()) == 0


# --------------------------------------------------------------------------
# Tiché rameno, strop a odstup
# --------------------------------------------------------------------------

def test_tiche_rameno_ma_tu_istu_branu():
    g = Hra(silent_share=1.0)
    g.natiahni(75.0)
    evs = []
    for i in range(6):
        evs += g.krok(80.0 + i * 4, pauza=i >= 3)
    assert not _typu(evs, trigger.E_DELIVER), "tiché rameno by nebolo kontrolné"
    for i in range(8):
        evs += g.krok(99.0 - i * 4, pauza=i >= 6)
    d = _typu(evs, trigger.E_DELIVER)
    assert len(d) == 1
    assert d[0]["arm"] == trigger.ARM_SILENT and d[0]["hlas"] is False
    assert d[0]["delivery"] == trigger.D_PAUSE


def test_strop_a_odstup_platia_dalej():
    """Dve hodiny nekritického plata s pauzou každých 30 s."""
    g = Hra()
    rnd = random.Random(3)
    for i in range(2 * 1200):
        g.krok(80.0 + rnd.uniform(-0.4, 0.4), pauza=i % 10 == 9)
    d = [e["ts"] for e in _typu(g.udalosti, trigger.E_DELIVER)]
    assert d, "plató bez stúpania musí prehovoriť"
    for a, b in zip(d, d[1:]):
        assert b - a >= 240.0, (a, b)
    for t0 in d:
        assert len([x for x in d if t0 <= x < t0 + trigger.HOUR_S]) <= 5
    assert all(e["hlas"] for e in _typu(g.udalosti, trigger.E_DELIVER))


# --------------------------------------------------------------------------
# Appka: pásmo tepu, nie pásmo záťaže
# --------------------------------------------------------------------------

def _zdroj(meno):
    with open(os.path.join(KOREN, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _telo(meno_suboru, meno_funkcie):
    strom = ast.parse(_zdroj(meno_suboru))
    for uzol in ast.walk(strom):
        if isinstance(uzol, ast.FunctionDef) and uzol.name == meno_funkcie:
            telo = uzol.body
            if (telo and isinstance(telo[0], ast.Expr)
                    and isinstance(telo[0].value, ast.Constant)):
                telo = telo[1:]
            return "\n".join(ast.unparse(p) for p in telo)
    raise AssertionError(f"{meno_funkcie} sa v {meno_suboru} nenašla")


def test_apply_hr_bpm_posiela_pasmo_tepu():
    telo = _telo("app.py", "_apply_hr_bpm")
    assert "zona=self.hr_stats.known_zone" in telo, \
        "spúšťač musí dostať pásmo tepu, inak brána nepustí nič"
    assert "zone_for" not in telo, "pásma záťaže by umlčali priveľa"
    # simulácia kŕmi bránu rovnako ako appka
    assert "zona=stats.known_zone" in _telo("simulate.py", "odsimuluj")


def test_suhrn_relacie_nesie_pauzy_a_zadrzane():
    telo = _telo("app.py", "_close_hr_session")
    # `ast.unparse` píše reťazce v apostrofoch
    assert "summary['pause_episodes'] = self.cue_trigger.pause_episodes" in telo
    assert "summary['cues_withheld'] = dict(self.cue_trigger.zadrzane)" in telo


def _stats(critical=109, bpm=95, n=160, t=1000.0):
    st = hr_stats.HeartStats(critical_bpm=critical)
    st.long_baseline = 76.0
    for _ in range(n):
        st.add(bpm, ts=t)
        t += 1.5
    return st, t


def test_known_zone_je_zone_of_bpm_ked_ho_appka_pozna():
    # spúšťač hr_stats neimportuje - reťazec musí sedieť
    assert trigger.ZONA_KRITICKA == hr_stats.ZONE_CRITICAL
    st, _ = _stats(bpm=95)
    assert st.known_zone == st.zone == hr_stats.ZONE_RAISED
    st, _ = _stats(bpm=112)
    assert st.known_zone == hr_stats.ZONE_CRITICAL
    # záťaž pri 95 BPM je „vysoká" podľa starých pásiem - brána ju nesmie brať
    st, _ = _stats(bpm=95)
    assert hr_stats.zone_for(st.stress) != st.known_zone


def test_known_zone_je_none_ked_ho_appka_nepozna():
    st = hr_stats.HeartStats(critical_bpm=109)
    assert st.known_zone is None                # bez tepu
    st.add(80, ts=1000.0)
    assert st.is_calibrating and st.known_zone is None
    assert st.zone == hr_stats.ZONE_CALM, "obrazovka si pomôže pokojom, brána nie"
    st, t = _stats(bpm=112)
    st.clear_live()
    assert st.known_zone is None                # tep vypadol
    st.add(112, ts=t)
    assert st.is_settling and st.known_zone is None
    for _ in range(5):
        t += 1.5
        st.add(112, ts=t)
    assert st.known_zone == hr_stats.ZONE_CRITICAL


# --------------------------------------------------------------------------
# Meracie okno: stratený paket nie je diera v dátach
# --------------------------------------------------------------------------

def test_meracie_okno_ma_tu_istu_hranicu_vypadku_ako_spustac():
    assert measure.MAX_GAP_S == trigger.DIERA_S
    assert measure.MAX_GAP_S == heart_rate.HeartRateMonitor.STALE_AFTER_S


def _ridke(start, koniec, krok=2.9, strata_kazdy=4, diera=None):
    out, t, i = [], start, 0
    while t <= koniec:
        if not (diera and diera[0] <= t <= diera[1]):
            out.append((t, 90.0))
        i += 1
        t += krok * 2 if i % strata_kazdy == 0 else krok   # stratený paket
    return out


def test_strateny_paket_okno_nezneplatni():
    cue = 50_000.0
    w = measure.build_window(
        {"ts": cue, "category": "breath", "cue_id": "x", "arm": "voice",
         "source": "auto"}, _ridke(cue - 120.0, cue + 240.0), [cue])
    assert measure.R_GAP not in w["reasons"], w["reasons"]
    assert w["valid"] is True


def test_skutocny_vypadok_okno_stale_zneplatni():
    cue = 50_000.0
    w = measure.build_window(
        {"ts": cue, "category": "breath", "cue_id": "x", "arm": "voice",
         "source": "auto"},
        _ridke(cue - 120.0, cue + 240.0, diera=(cue + 30.0, cue + 45.0)), [cue])
    assert measure.R_GAP in w["reasons"]


# --------------------------------------------------------------------------
# Veta po relácii bez hlášky
# --------------------------------------------------------------------------

def _preco(**summary):
    import ui_dialogs
    return ui_dialogs.SessionEndDialog._preco_ticho(summary)


ZAKLAD = dict(above_runs=4, runs_cancelled_gap=0, runs_cancelled_dip=4,
              longest_above_s=30.0, stress_hold_s=45.0, duration_s=1800.0)


def test_ziadna_pauza_za_vecer_povie_o_gyre():
    veta = _preco(**ZAKLAD, pause_episodes=0)
    assert veta == i18n.tr("session.end.none_nopause")
    assert "gyro" in veta
    # platí aj v pracovnom svete, kde hlas nie je vôbec - veta ho nesľubuje
    assert "hlas" not in i18n.STRINGS["session.end.none_nopause"]["sk"]
    assert "voice" not in i18n.STRINGS["session.end.none_nopause"]["en"]


def test_ziadna_pauza_v_kratkej_relacii_nic_netvrdi():
    veta = _preco(**dict(ZAKLAD, duration_s=240.0), pause_episodes=0)
    assert veta != i18n.tr("session.end.none_nopause")


def test_stara_relacia_bez_poctu_pauz_nic_netvrdi():
    veta = _preco(**ZAKLAD)
    assert veta != i18n.tr("session.end.none_nopause")
    assert veta != i18n.tr("session.end.none_withheld")


def test_vypadky_maju_prednost_pred_pauzami():
    veta = _preco(**dict(ZAKLAD, runs_cancelled_gap=5, runs_cancelled_dip=1),
                  pause_episodes=0)
    assert veta == i18n.tr("session.end.none_dropouts", n=5)


def test_zadrzane_branou_povie_ze_mlcala_sama():
    veta = _preco(**ZAKLAD, pause_episodes=12,
                  cues_withheld={"bez_pauzy": 0, "nevhodna_chvila": 2,
                                 "nedalo_sa": 0})
    assert veta == i18n.tr("session.end.none_withheld")


def test_nedalo_sa_samo_vetu_o_tepe_netvrdi():
    """`nedalo_sa` je odstup/snooze/chôdza, nie tep - veta o tepe by klamala."""
    veta = _preco(**ZAKLAD, pause_episodes=12,
                  cues_withheld={"bez_pauzy": 0, "nevhodna_chvila": 0,
                                 "nedalo_sa": 3})
    assert veta != i18n.tr("session.end.none_withheld")


def test_rozbity_suhrn_nezhodi_dotaznik():
    for zle in ({"nevhodna_chvila": "x"}, ["a"], "zle", None):
        assert isinstance(_preco(**ZAKLAD, pause_episodes="?",
                                 cues_withheld=zle), str)


# --------------------------------------------------------------------------
# Texty sľubujú len to, čo kód robí
# --------------------------------------------------------------------------

def test_texty_o_nacasovani_uz_nesluboju_najblizsiu_prestavku():
    zakazane = ("najbližšej prestávke", "next break", "next pause",
                "nächsten Pause", "siguiente pausa", "prochaine pause",
                "pausa seguinte", "ближайшей паузе", "次の小休止", "下一个间隙",
                "次の休み", "下一次停顿")
    for kluc in ("ob.step1.how", "tour.triggers.body", "slots.hint"):
        for jazyk, text in i18n.STRINGS[kluc].items():
            for z in zakazane:
                assert z not in text, (kluc, jazyk, z)
        assert "nestúpa" in i18n.STRINGS[kluc]["sk"]
        assert "v pásme Špička" in i18n.STRINGS[kluc]["sk"]


def test_nove_vety_maju_vsetky_jazyky():
    for kluc in ("session.end.none_nopause", "session.end.none_withheld"):
        assert set(i18n.STRINGS[kluc]) == set(i18n.LANGUAGES), kluc
    assert "mlčala" in i18n.STRINGS["session.end.none_withheld"]["sk"]
