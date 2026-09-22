# -*- coding: utf-8 -*-
"""Meracie okna - co robi okno platnym a co ho zneplatni.

Testuje sa cisty modul `measure` nad vymyslenymi datami, takze to bezi
bez Tk, bez hodiniek a bez cakania v realnom case.

Preco tolko testov na "neplatne" pripady: okno, ktore vyzera platne a
nie je, je horsie nez ziadne - tiche skreslenie sa v grafe neprejavi ako
chyba, len ako iny vysledok.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import measure  # noqa: E402

T0 = 10_000.0          # lubovolny "absolutny" cas, nech su cisla citatelne
CUE = T0 + 300.0       # hlaska 5 minut po zaciatku relacie


def rad(start, end, bpm=80.0, krok=1.0, vynechaj=None):
    """Vzorky 1x za sekundu od `start` po `end`.

    `vynechaj` je (od, do) - diera, ktorou sa simuluje vypadok senzora.
    `bpm` moze byt cislo alebo funkcia casu.
    """
    out = []
    t = start
    while t <= end:
        if vynechaj and vynechaj[0] <= t <= vynechaj[1]:
            t += krok
            continue
        out.append((t, bpm(t) if callable(bpm) else bpm))
        t += krok
    return out


def okno(samples, cues=None, **kw):
    cue = {"ts": CUE, "category": "breath", "cue_id": "x", "arm": "voice",
           "source": "auto"}
    return measure.build_window(cue, samples, cues or [CUE], **kw)


# --------------------------------------------------------------------------
# Ciste vypocty
# --------------------------------------------------------------------------

def test_priemer_berie_len_vzorky_v_intervale():
    samples = [(100.0, 60.0), (150.0, 80.0), (200.0, 100.0)]
    assert measure.mean_in(samples, 140.0, 210.0) == 90.0
    assert measure.mean_in(samples, 300.0, 400.0) is None


def test_diery_sa_rozlisuju_podla_toho_kde_su():
    """Zaciatok, vnutro a koniec musia byt tri rozne cisla.

    Keby sa scitali, skratene okno by sa hlasilo ako vypadok senzora.
    """
    samples = rad(110.0, 190.0)
    zaciatok, vnutro, koniec = measure.gaps(samples, 100.0, 200.0)
    assert zaciatok == 10.0
    assert vnutro == 1.0
    assert koniec == 10.0

    # Suvisly rad: na okrajoch ostava nanajvys jedna vzorkovacia perioda
    # (interval je polootvoreny, takze vzorka presne na konci uz dnu nepatri).
    diera = rad(100.0, 200.0, vynechaj=(140.0, 160.0))
    zaciatok, vnutro, koniec = measure.gaps(diera, 100.0, 200.0)
    assert zaciatok == 0.0
    assert vnutro > 20.0
    assert koniec <= 1.0


def test_prazdny_interval_je_cely_diera():
    assert measure.gaps([], 100.0, 200.0) == (100.0, 0.0, 0.0)


def test_refrakterna_zona_preskakuje_seba_sameho():
    """Volajuci posiela casy VSETKYCH hlasok vratane tejto."""
    assert measure.refractory_conflict(CUE, [CUE]) is False
    assert measure.refractory_conflict(CUE, [CUE, CUE + 30.0]) is True
    assert measure.refractory_conflict(CUE, [CUE, CUE - 30.0]) is True
    # tesne za zonou: -60 a +180 su hranice, cokolvek za nimi uz nevadi
    assert measure.refractory_conflict(CUE, [CUE, CUE + 181.0]) is False
    assert measure.refractory_conflict(CUE, [CUE, CUE - 61.0]) is False


def test_podiel_aktivity():
    aktivita = [(CUE - 10.0, 100), (CUE - 5.0, 5000), (CUE - 1.0, 200)]
    assert measure.active_share(aktivita, CUE - 12.0, CUE) == 2 / 3
    assert measure.active_share([], CUE - 12.0, CUE) is None


def test_kategoria_podla_slotu():
    assert measure.category_for_slot(0) == "grounding"
    assert measure.category_for_slot(3) == "breath"
    assert measure.category_for_slot(4) is None
    assert measure.category_for_slot(None) is None


# --------------------------------------------------------------------------
# Zostavenie okna
# --------------------------------------------------------------------------

def test_cele_okno_je_platne():
    samples = rad(CUE - 120.0, CUE + 240.0)
    w = okno(samples)
    assert w["valid"] is True
    assert w["reasons"] == []
    assert w["pre_bpm"] == 80.0
    assert w["post_bpm"] == 80.0
    assert w["arm"] == "voice"
    assert w["category"] == "breath"


def test_mrtvy_cas_sa_do_po_okna_nepocita():
    """Prvych 10 s po hlaske musi z priemeru vypadnut - inak by doň
    natiekol este stav z momentu hlasky."""
    def bpm(t):
        return 200.0 if CUE <= t < CUE + measure.DEAD_S else 80.0

    w = okno(rad(CUE - 120.0, CUE + 240.0, bpm=bpm))
    assert w["post_bpm"] == 80.0


def test_druha_hlaska_v_zone_zneplatni_obe():
    samples = rad(CUE - 120.0, CUE + 400.0)
    cues = [
        {"ts": CUE, "category": "breath", "arm": "voice"},
        {"ts": CUE + 30.0, "category": "jaw", "arm": "voice"},
    ]
    okna = measure.build_windows(cues, samples)
    assert len(okna) == 2
    for w in okna:
        assert w["valid"] is False
        assert measure.R_REFRACTORY in w["reasons"]


def test_vypadok_senzora_zneplatni_okno_ako_diera():
    samples = rad(CUE - 120.0, CUE + 240.0, vynechaj=(CUE + 20.0, CUE + 50.0))
    w = okno(samples)
    assert w["valid"] is False
    assert measure.R_GAP in w["reasons"]
    # NIE ako skratene okno - relacia bezala dalej, len senzor vypadol
    assert measure.R_POST_SHORT not in w["reasons"]


def test_hlaska_prilis_skoro_je_skratene_pred_okno_nie_diera():
    """Relacia zacala 20 s pred hlaskou - pred-okno chce 60 s."""
    samples = rad(CUE - 20.0, CUE + 240.0)
    w = okno(samples)
    assert w["valid"] is False
    assert measure.R_PRE_SHORT in w["reasons"]
    assert measure.R_GAP not in w["reasons"]


def test_relacia_skoncila_skoro_je_skratene_po_okno():
    samples = rad(CUE - 120.0, CUE + 30.0)
    w = okno(samples)
    assert w["valid"] is False
    assert measure.R_POST_SHORT in w["reasons"]
    assert measure.R_PRE_SHORT not in w["reasons"]


def test_ziadne_data_je_vlastny_dovod():
    w = okno([])
    assert w["valid"] is False
    assert measure.R_NO_DATA in w["reasons"]


def test_okno_nesie_zataz_a_aktivitu():
    samples = rad(CUE - 120.0, CUE + 240.0)
    load = rad(CUE - 120.0, CUE + 240.0, bpm=lambda t: 70.0 if t < CUE else 30.0)
    aktivita = rad(CUE - 120.0, CUE + 240.0, bpm=lambda t: 100 if t < CUE else 9000)
    cue = {"ts": CUE, "category": "breath", "arm": "voice", "load_series": load}
    w = measure.build_window(cue, samples, [CUE], activity=aktivita)
    assert w["pre_load"] == 70.0
    assert w["post_load"] == 30.0
    assert w["pre_activity"] == 1.0
    assert w["post_activity"] == 0.0


def test_offset_a_hra_sa_zapisu_ked_su_zname():
    samples = rad(CUE - 120.0, CUE + 240.0)
    w = okno(samples, session_started=T0, game="Elden Ring")
    assert w["offset_s"] == 300.0
    assert w["game"] == "Elden Ring"


def test_okna_su_zoradene_podla_casu():
    samples = rad(CUE - 400.0, CUE + 600.0)
    cues = [{"ts": CUE + 400.0}, {"ts": CUE}, {"ts": CUE + 200.0}]
    okna = measure.build_windows(cues, samples)
    assert [w["ts"] for w in okna] == sorted(w["ts"] for w in okna)


# --------------------------------------------------------------------------
# Ulozenie
# --------------------------------------------------------------------------

def test_ulozenie_a_nacitanie(tmp_path):
    path = str(tmp_path / "hr_windows.json")
    assert measure.load_windows(path) == []
    assert measure.save_windows(path, [{"ts": 1.0, "valid": True}]) is True
    assert measure.save_windows(path, [{"ts": 2.0, "valid": True}]) is True
    ulozene = measure.load_windows(path)
    assert [w["ts"] for w in ulozene] == [1.0, 2.0]


def test_zapis_neostane_polovicny(tmp_path):
    """Po zapise nesmie vedla ostat `.tmp` - pisalo sa cez premenovanie."""
    path = str(tmp_path / "hr_windows.json")
    measure.save_windows(path, [{"ts": 1.0}])
    assert not os.path.exists(path + ".tmp")


def test_poskodeny_subor_sa_neprepise(tmp_path):
    """Necitatelny subor nie je dovod zahodit vsetko, co sa nameralo.

    Radsej sa nezapise nic - clovek si vsimne, ze okna nepribudaju, a da
    sa to zachranit. Prepisanim prazdnym zoznamom by sa nezachranilo nic.
    """
    path = str(tmp_path / "hr_windows.json")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("toto nie je JSON")
    assert measure.save_windows(path, [{"ts": 1.0}]) is False
    with open(path, encoding="utf-8") as fh:
        assert fh.read() == "toto nie je JSON"


def test_strop_poctu_okien(tmp_path):
    path = str(tmp_path / "hr_windows.json")
    vela = [{"ts": float(i)} for i in range(measure.MAX_WINDOWS + 50)]
    measure.save_windows(path, vela)
    ulozene = measure.load_windows(path)
    assert len(ulozene) == measure.MAX_WINDOWS
    # zahadzuju sa NAJSTARSIE
    assert ulozene[-1]["ts"] == float(measure.MAX_WINDOWS + 49)


def test_prehlad_pocita_len_platne_okna():
    okna = [
        {"arm": "voice", "valid": True, "pre_bpm": 100.0, "post_bpm": 90.0},
        {"arm": "voice", "valid": True, "pre_bpm": 100.0, "post_bpm": 94.0},
        {"arm": "voice", "valid": False, "pre_bpm": 100.0, "post_bpm": 10.0},
        {"arm": "silent", "valid": True, "pre_bpm": 100.0, "post_bpm": 98.0},
    ]
    prehlad = measure.summarize(okna)
    assert prehlad["voice"]["n"] == 2
    assert prehlad["voice"]["delta_bpm"] == -8.0
    assert prehlad["silent"]["n"] == 1
    assert prehlad["silent"]["delta_bpm"] == -2.0


def test_prehlad_nerobi_ziadny_zaver():
    """Vracia cisla, nie verdikt - rozhodnut sa da az pri dost okien."""
    prehlad = measure.summarize([
        {"arm": "voice", "valid": True, "pre_bpm": 100.0, "post_bpm": 50.0}])
    assert set(prehlad["voice"]) == {"n", "delta_bpm"}


# --------------------------------------------------------------------------
# `delivery` v okne — našla revízia
# --------------------------------------------------------------------------

def test_okno_nesie_aj_sposob_dorucenia():
    """`arm` a `delivery` sú rôzne veci a obe musia byť v okne.

    Bez `delivery` sa spätne nedá zistiť, ktoré hlášky prišli na pauzu a
    ktoré až po 90 s ticho — a práve prah pauzy je číslo, o ktorom sa vedie
    spor. Nemal by sa z čoho overiť.
    """
    cue = {"ts": 1000.0, "category": "breath", "cue_id": "slot3",
           "arm": "voice", "source": "auto", "delivery": "timeout"}
    vzorky = [(1000.0 - 60 + i, 70.0) for i in range(140)]
    okno = measure.build_window(cue, vzorky, [1000.0])
    assert okno["delivery"] == "timeout"
    assert okno["arm"] == "voice", "timeout nesmie prepísať rameno"


def test_stare_okno_bez_delivery_nepadne():
    """Dáta z relácií spred tejto zmeny `delivery` nemajú. Musia sa dať
    načítať ďalej — inak by oprava zahodila, čo sa dovtedy nameralo."""
    cue = {"ts": 1000.0, "arm": "silent", "source": "auto"}
    vzorky = [(1000.0 - 60 + i, 70.0) for i in range(140)]
    okno = measure.build_window(cue, vzorky, [1000.0])
    assert okno["delivery"] is None


# --------------------------------------------------------------------------
# Striedanie kategórií (18. 9.)
#
# Do 18. 9. hrala appka vždy jeden pevný slot. Malo to jednu silnú vlastnosť
# — všetky okná z jednej kategórie — a jednu fatálnu: rovnaká veta stokrát
# za večer prestane fungovať.
# --------------------------------------------------------------------------

def test_striedanie_ide_kolo_dokola():
    assert [measure.next_slot([0, 1, 2, 3], p) for p in (None, 0, 1, 2, 3)] \
        == [0, 1, 2, 3, 0]


def test_striedanie_preskoci_vypnute_sloty():
    """Vypnutý slot je rozhodnutie hráča a automat ho obchádzať nesmie."""
    assert [measure.next_slot([1, 3], p) for p in (None, 1, 3)] == [1, 3, 1]


def test_striedanie_pri_jedinom_slote_opakuje():
    """Opakovaniu sa pri jednom zapnutom slote vyhnúť nedá — a je to lepšie
    než mlčať."""
    assert measure.next_slot([2], 2) == 2


def test_striedanie_bez_slotov_vrati_none():
    """Volajúci si potom siahne po zálohe, nie po náhodnom indexe."""
    assert measure.next_slot([], None) is None
    assert measure.next_slot(None, 1) is None


def test_striedanie_znesie_neznamy_posledny():
    """Hráč mohol slot medzitým vypnúť. Nesmie to spadnúť ani zaseknúť
    striedanie na jednej kategórii."""
    assert measure.next_slot([0, 2], 1) == 0


# --------------------------------------------------------------------------
# Účinnosť podľa kategórie
# --------------------------------------------------------------------------

def _okno(kat, pre, post, arm="voice", valid=True):
    return {"category": kat, "pre_bpm": pre, "post_bpm": post,
            "arm": arm, "valid": valid}


def test_ucinnost_pocita_len_hlasne_rameno():
    """Tiché okná sú referencia pre to, či hláška funguje VOBEC — nie pre
    porovnanie kategórií medzi sebou. Zmiešať ich by znamenalo porovnávať
    kategóriu s tichom."""
    okna = [_okno("breath", 100, 95) for _ in range(6)]
    okna += [_okno("breath", 100, 60, arm="silent") for _ in range(6)]
    von = measure.by_category(okna)
    assert von["breath"]["n"] == 6
    assert von["breath"]["delta_bpm"] == -5.0


def test_ucinnost_preskoci_neplatne_okna():
    okna = [_okno("jaw", 100, 90, valid=False) for _ in range(9)]
    assert measure.by_category(okna) == {}


def test_ucinnost_pod_prahom_nedovoli_tvrdit():
    """Pri troch oknách je interval široký ako celý rozsah. Graf, ktorý by
    z toho nakreslil pruh, by tvrdil niečo, čo v dátach nie je."""
    okna = [_okno("jaw", 100, 96 + i) for i in range(3)]
    von = measure.by_category(okna)["jaw"]
    assert von["n"] == 3
    assert von["dost_dat"] is False


def test_ucinnost_vracia_interval_nie_hole_cislo():
    """Zadanie 2.1b, B2: „výstup nech je odhad s intervalom, nikdy holé
    číslo."""
    okna = [_okno("release", 100, 100 - d) for d in (2, 4, 6, 4, 5, 3, 5)]
    von = measure.by_category(okna)["release"]
    assert von["dost_dat"] is True
    assert von["ci95"] is not None and von["ci95"] > 0


def test_ucinnost_jedineho_okna_nema_interval():
    """Z jednej hodnoty sa rozptyl spočítať nedá — a vymyslieť si ho by bolo
    horšie než ho nemať."""
    von = measure.by_category([_okno("breath", 100, 94)])["breath"]
    assert von["ci95"] is None and von["dost_dat"] is False


def test_ucinnost_nerobi_zaver():
    """Nevracia poradie ani „najlepšiu kategóriu". Z prekrývajúcich sa
    intervalov by to spravilo rebríček, ktorý dáta neunesú."""
    okna = [_okno("breath", 100, 94) for _ in range(6)]
    okna += [_okno("jaw", 100, 99) for _ in range(6)]
    von = measure.by_category(okna)
    assert set(von) == {"breath", "jaw"}
    assert all(isinstance(v, dict) for v in von.values())
    assert "best" not in von and "poradie" not in von


def test_rucna_hlaska_sa_do_merania_nezapisuje():
    """Klik na Test nesmie skoncit v grafe ucinnosti.

    `fire_slot` dnes spusta jedine tlacidlo Test a klik v HUD nahlade -
    oboje pri nastavovani, casto viackrat za sebou a bez hrania.
    `by_category` filtruje len podla `valid` a `arm`, `source` necita, takze
    kazdy taky klik by sa zaratal ako hlaska a jeho cas by navyse zabral
    refrakternu zonu skutocnej hlaske o par sekund neskor.
    """
    import inspect
    import app as app_mod
    telo = inspect.getsource(app_mod.DandurfApp._note_cue)
    # az KOD pod docstringom - v poznamke je volanie spomenute zamerne
    telo = telo[telo.index('"""', telo.index('"""') + 3):]
    assert "note_trigger" not in telo, "rucna hlaska sa zapisuje do merania"


def test_hlaska_bez_vizualu_sa_nedoruci():
    """Slot bez zapnuteho in-game vizualu sa do striedania nesmie dostat.

    V tichom rameni je vizual JEDINA vec, ktora sa doruci. Slot s vypnutym
    vizualom by teda v tichom rameni neurobil nic, okno by sa zapisalo ako
    platne - a porovnanie ramien, teda cely dovod, preco ticha hlaska
    existuje, by meralo ticho proti tichu.
    """
    import inspect
    import app as app_mod
    telo = inspect.getsource(app_mod.DandurfApp._dalsi_cue_slot)
    assert "overlay_configs" in telo, "vyber kategorie neoveruje vizual"


def test_importovane_okna_sa_do_ucinnosti_nerataju():
    """`data_io` sľubuje, že importované záznamy sa z účinnosti vylučujú.

    Značku `imported: True` nastavoval, ale nečítal ju NIKTO — ani
    `by_category`, ani `summarize`, ani `hr_insights._valid`. Kto si
    naimportoval zálohu od kamaráta, videl vo svojom grafe jeho telo
    zmiešané so svojím a nemal ako to zistiť.
    """
    okna = [
        {"valid": True, "arm": "voice", "category": "jaw",
         "pre_bpm": 100.0, "post_bpm": 90.0},
        {"valid": True, "arm": "voice", "category": "jaw",
         "pre_bpm": 100.0, "post_bpm": 40.0, "imported": True},
    ]
    podla = measure.by_category(okna)
    assert podla["jaw"]["n"] == 1, "cudzie okno sa zaratalo"
    assert abs(podla["jaw"]["delta_bpm"] - (-10.0)) < 0.001

    suhrn = measure.summarize(okna)
    assert suhrn["voice"]["n"] == 1, "cudzie okno sa zaratalo do suhrnu"


def _aktivita(t0, t1, idle_ms):
    """Rovnomerná aktivita v úseku — [(čas, idle_ms)] ako z ActivityTracker."""
    return [(t, idle_ms) for t in range(int(t0), int(t1), 2)]


def test_hlaska_mimo_klavesnice_sa_do_ucinnosti_nerata():
    """Keď hráč vstane a odíde, tep mu stúpne CHÔDZOU, nie hrou.

    Appka to vidí ako záťaž, ozve sa — a po návrate a sadnutí si tep klesne.
    Okno potom vyzerá ako účinná hláška, pritom nemeria nič iné než to, že si
    človek sadol. `pre_activity` sa zapisovalo od začiatku, ale na platnosť
    okna nemalo vplyv.
    """
    ts = 10_000.0
    vzorky = [(t, 90.0) for t in range(int(ts - 200), int(ts + 400), 2)]
    cue = {"ts": ts, "arm": "voice", "category": "jaw", "cue_id": "slot1"}

    # pri klávesnici (idle 0 ms = vstup chodí) -> platné
    pri_stole = _aktivita(ts - 200, ts + 400, 0)
    okno = measure.build_window(cue, vzorky, [ts], activity=pri_stole)
    assert okno["valid"], okno["reasons"]
    assert okno["pre_activity"] > 0.9

    # preč od PC (idle rastie nad prah) -> neplatné, s dôvodom
    prec = [(t, 60_000) for t in range(int(ts - 200), int(ts + 400), 2)]
    okno = measure.build_window(cue, vzorky, [ts], activity=prec)
    assert not okno["valid"]
    assert measure.R_NEAKTIVNY in okno["reasons"]


def test_neznama_aktivita_okno_nezneplatni():
    """`None` znamená „nevieme", nie „bol preč".

    Staršie relácie aktivitu nezapisovali. Keby ju neznalosť zneplatňovala,
    spätne by sa zahodila celá história.
    """
    ts = 10_000.0
    vzorky = [(t, 90.0) for t in range(int(ts - 200), int(ts + 400), 2)]
    cue = {"ts": ts, "arm": "voice", "category": "jaw", "cue_id": "slot1"}
    okno = measure.build_window(cue, vzorky, [ts], activity=None)
    assert measure.R_NEAKTIVNY not in okno["reasons"], okno["reasons"]


def test_prepocet_okien_pouziva_rovnake_pravidlo_ako_measure():
    """`prepocitaj_okna.py` nesmie mať vlastnú predstavu o platnosti.

    Je to druhé miesto, kde sa rozhoduje, či okno platí. Keby sa rozišlo
    s `measure.build_window`, súbor a grafy by tvrdili každý niečo iné — a
    nikto by nevedel, ktoré číslo je to správne.
    """
    import prepocitaj_okna

    # pod prahom pred aj po -> dôvod
    for pre, post in ((0.1, 1.0), (1.0, 0.0), (0.1, 0.1)):
        okno = {"pre_activity": pre, "post_activity": post}
        assert prepocitaj_okna._dovody_z_aktivity(okno) == [measure.R_NEAKTIVNY], (pre, post)

    # nad prahom -> nič
    assert prepocitaj_okna._dovody_z_aktivity(
        {"pre_activity": 0.9, "post_activity": 0.9}) == []

    # „nevieme" nesmie zneplatniť
    assert prepocitaj_okna._dovody_z_aktivity(
        {"pre_activity": None, "post_activity": None}) == []


def test_prepocet_nesiaha_na_dovody_zo_surovych_vzoriek():
    """Dôvody ako `skratene_po` sa rátali zo vzoriek tepu, ktoré v súbore
    nie sú. Dopočítať ich spätne by znamenalo vyrobiť čísla, ktoré nikto
    nenameral — tak sa ich nástroj nesmie dotknúť.
    """
    import prepocitaj_okna
    zdroj = inspect_source(prepocitaj_okna._dovody_z_aktivity)
    for dovod in ("R_POST_SHORT", "R_PRE_SHORT", "R_GAP", "R_REFRACTORY"):
        assert dovod not in zdroj, dovod


def inspect_source(fn):
    import inspect
    return inspect.getsource(fn)


# --------------------------------------------------------------------------
# Nedoručená hláška sa nesmie merať (B17)
# --------------------------------------------------------------------------

def test_nevykresleny_vizual_zneplatni_okno():
    """B17: tiché rameno má vizuál ako jediný podnet. Keď sa nevykreslil,
    okno by porovnávalo hlášku proti ničomu — musí vypadnúť z merania."""
    samples = rad(T0, CUE + 200.0)
    cue = {"ts": CUE, "category": "breath", "cue_id": "x", "arm": "silent",
           "source": "auto", "delivered": False}
    w = measure.build_window(cue, samples, [CUE])
    assert w["valid"] is False
    assert measure.R_NEDORUCENE in w["reasons"]


def test_dorucena_hlaska_ostava_platna():
    samples = rad(T0, CUE + 200.0)
    cue = {"ts": CUE, "category": "breath", "cue_id": "x", "arm": "silent",
           "source": "auto", "delivered": True}
    assert measure.build_window(cue, samples, [CUE])["valid"] is True


def test_stary_zaznam_bez_delivered_sa_nezneplatni():
    """Staré okná pole `delivered` nemajú (None = nevieme) — nesmú sa
    spätne zahodiť, rovnaké pravidlo ako pri aktivite."""
    samples = rad(T0, CUE + 200.0)
    cue = {"ts": CUE, "category": "breath", "cue_id": "x", "arm": "voice",
           "source": "auto"}   # žiadny 'delivered'
    w = measure.build_window(cue, samples, [CUE])
    assert measure.R_NEDORUCENE not in w["reasons"]


# --------------------------------------------------------------------------
# Čistý koniec relácie nie je výpadok senzora (B5)
# --------------------------------------------------------------------------

def test_cisty_koniec_relacie_nie_je_diera_v_datach():
    """B5: keď hláška padne na konci večera a hráč vypne počúvanie, po-okno
    je prázdne. Dostane správne `skratene_po`, ale NESMIE dostať aj
    `diera_v_datach` — pri ladení to tvrdilo, že vypadli hodinky, hoci hráč
    len dohral. (`gaps()` vracia pri prázdnom okne celý rozsah ako začiatok.)"""
    pred = rad(CUE - 60.0, CUE)              # dáta pred hláškou
    w = measure.build_window(
        {"ts": CUE, "category": "b", "cue_id": "x", "arm": "voice",
         "source": "auto"}, pred, [CUE])
    assert measure.R_POST_SHORT in w["reasons"]
    assert measure.R_GAP not in w["reasons"], "čistý koniec nie je výpadok (B5)"


def test_skutocna_diera_uprostred_ostava_diera():
    """Oprava B5 nesmie umlčať detekciu skutočného výpadku: diera obklopená
    dátami na oboch stranách stále musí byť `diera_v_datach`."""
    a = int(CUE + measure.DEAD_S)
    b = int(CUE + measure.POST_S)
    po = ([(t, 80.0) for t in range(a, a + 5)]
          + [(t, 80.0) for t in range(b - 5, b + 1)])   # diera v strede po-okna
    w = measure.build_window(
        {"ts": CUE, "category": "b", "cue_id": "x", "arm": "voice",
         "source": "auto"}, rad(CUE - 60.0, CUE) + po, [CUE])
    assert measure.R_GAP in w["reasons"]
