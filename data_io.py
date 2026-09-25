"""Export, import a mazanie dát hráča.

TRI VECI, KAŽDÁ S INÝM RIZIKOM
------------------------------
MAZANIE musí presne vymenovať, čo maže, a naozaj to všetko zmazať. Sľub
"všetko ostáva u teba" je na store page; keby mazanie niečo nechalo, bol by
to najhorší druh chyby - taký, ktorý nikto nevidí.

EXPORT je neškodný. Robí sa dvojaký: CSV relácií (to je v `hr_stats`, pre
človeka do tabuľky) a JSON so VŠETKÝM vrátane meracích okien - na prenos na
iný počítač alebo "pošli mi to, som beta tester".

IMPORT je jediný z tých troch, ktorý vie uškodiť, a robí to POTICHU. Cudzie
dáta otrávia základňu aj model a nikde sa to neprejaví - appka len začne
byť horšia. Preto:

  * prisny parser, ziadny `pickle`, ziadny `eval`. Subor najviac
    `MAX_IMPORT_BAJTOV`, len UTF-8, len `json.loads` a potom kontrola typu
    kazdeho pola (`clean_session`, `clean_window`) - NaN ani nekonecno
    neprejdu nikde. Relacia bez pouzitelneho `started`/`duration_s` a okno
    bez `ts` sa zahodia cele a spocitaju; pole zleho typu sa zahodi samo a
    zaznam ostane, ako keby bol zo starsej verzie appky.
  * importované záznamy dostanú `imported: True` a appka sa z nich neučí:
    základňa, hranice a prah (`hr_stats.ciste_relacie`), rebrík hlášky,
    postrehy, účinnosť (`measure`) aj karta poslednej relácie ich
    preskakujú. Cudzie telo nie je tvoje telo.
  * hráč si vyberie ZLÚČIŤ alebo NAHRADIŤ - nikdy sa to neuhádne za neho.
    NAHRADIŤ až na druhé potvrdenie a vždy so zálohou oboch súborov
    (`zaloha_pred_importom`).

Modul je čisto dátový: žiadny Tk, žiadne dialógy. Cesty dostáva zvonku,
takže sa celý dá otestovať v tmp priečinku.
"""

import glob
import json
import math
import os
from datetime import datetime
import shutil

# Verzia formátu. Keď sa raz zmení tvar dát, starý súbor sa dá rozpoznať
# a buď domigrovať, alebo slušne odmietnuť - namiesto tichého nezmyslu.
EXPORT_VERSION = 1

# Čo všetko sa dá vymazať. Poradie je poradie v zozname pre hráča.
# `label` je i18n kľúč, nie hotový text - modul nevie o jazyku.
MAZATELNE = (
    ("data.delete.sessions", "hr_sessions.json"),
    # hr_events.jsonl je záznam KAŽDEJ hlášky za každý večer (tep, záťaž,
    # hra). Doteraz sa pri "Zmazať históriu" NEMAZAL - dialóg pritom hlásil
    # "Zmazané". Presne ten najhorší druh chyby, pred ktorým varuje hlavička
    # tohto modulu: mazanie, ktoré niečo nechá.
    ("data.delete.events", "hr_events.jsonl"),
    ("data.delete.windows", "hr_windows.json"),
    ("data.delete.insights", "hr_insights.json"),
)
# Priečinky, ktoré sa zmažú celé (a hneď vytvoria prázdne, ak do nich appka
# píše za behu). `logs` tu ZÁMERNE NIE JE: v dev režime je `data_dir`
# priečinok projektu a `logs/` v ňom drží gui_screenshots aj ďalšie veci, čo
# s históriou hráča nesúvisia - rmtree celého priečinka ich mazal. Vlastné
# logy appky sa preto mažú po súboroch (viz `_LOG_SUBORY` v `delete_plan`).
MAZATELNE_PRIECINKY = (
    ("data.delete.tts", os.path.join("audio", "tts_cache")),
)
# Vlastné log súbory appky. Živý `app.log` tu NIE JE - počas behu je
# zamknutý (open handler) a nesie len túto reláciu; rotáciou sa aj tak
# prepíše. Mažú sa rotované kópie a crash.log.
_LOG_SUBORY = ("crash.log",) + tuple("app.log.%d" % i for i in range(1, 6))


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

# Najviac udalosti, ktore sa v logu drzia. Jeden vecer ich urobi radovo
# desiatky, takze 20 000 je nieco ako pol roka hrania - a subor pod 5 MB.
MAX_UDALOSTI = 20000


def append_events(path, events, started=None, max_riadkov=MAX_UDALOSTI):
    """Prida udalosti automatu do JSONL logu. Vrati pocet zapisanych.

    PRECO JSONL A NIE JSON
    ----------------------
    Jedna udalost na riadok znamena, ze sa da citat aj rozpisany subor,
    dopisovat bez nacitania celku, a otvorit v com chces. Cely JSON by sa
    musel pri kazdom zapise nacitat, rozparsovat a prepisat.

    PRECO SA TO VOBEC UKLADA
    ------------------------
    `app._cue_log` zbieral kazdu udalost stavoveho automatu - natiahnutia,
    dorucenia aj zrusenia s dovodom - a na konci relacie ich POCET pouzil
    v dialogu. Potom sa zahodili. Priebeh vecera sa tak nedal precitat
    spatne ani pri diagnostike, ani pri hladani, preco appka mlcala.

    `started` je zaciatok relacie; zapise sa ku kazdej udalosti, aby sa
    dali zoskupit bez hadania z casov.
    """
    udalosti = [u for u in (events or []) if isinstance(u, dict)]
    if not udalosti:
        return 0
    riadky = []
    for u in udalosti:
        zaznam = dict(u)
        if started is not None:
            zaznam.setdefault("session_started", round(float(started), 1))
        riadky.append(json.dumps(zaznam, ensure_ascii=False, sort_keys=True))

    stare = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                stare = [r for r in fh.read().split("\n") if r.strip()]
        except OSError:
            stare = []
    vsetko = (stare + riadky)[-int(max_riadkov):]

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(vsetko) + "\n")
    os.replace(tmp, path)
    return len(riadky)


def read_events(path):
    """Udalosti z JSONL logu. Poskodeny riadok sa preskoci, nie zhodi."""
    von = []
    if not os.path.exists(path):
        return von
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for riadok in fh:
                riadok = riadok.strip()
                if not riadok:
                    continue
                try:
                    zaznam = json.loads(riadok)
                except ValueError:
                    continue
                if isinstance(zaznam, dict):
                    von.append(zaznam)
    except OSError:
        return von
    return von


# Stlpce, ktore idu na zaciatok, ak v datach su. Zvysok sa doplni podla
# abecedy - aby sa subor nezmenil zakazdym, ked pribudne kluc.
_PORADIE = ("kedy", "ts", "typ", "arm", "delivery", "category", "reason",
            "cue_id", "valid", "reasons", "pre_bpm", "post_bpm",
            "pre_load", "post_load", "offset_s", "game")


def _bunka(hodnota):
    """Jedna bunka pre Excel. Desatinna CIARKA (SK/CZ Excel inak vidi text),
    zoznam ako medzerou oddeleny text, None ako prazdno."""
    if hodnota is None:
        return ""
    if isinstance(hodnota, bool):
        return "1" if hodnota else "0"
    if isinstance(hodnota, float):
        return ("%.3f" % hodnota).rstrip("0").rstrip(".").replace(".", ",")
    if isinstance(hodnota, (list, tuple)):
        return " ".join(str(x) for x in hodnota)
    text = str(hodnota)
    # Bodkocarka je oddelovac (viz hr_stats.CSV_SEPARATOR) - v texte nema co
    # robit, inak sa riadok rozpadne na viac stlpcov.
    return text.replace(";", ",").replace("\r", " ").replace("\n", " ")


def export_rows_csv(rows, path, separator=";"):
    """Zoznam slovnikov do CSV. Vrati pocet riadkov.

    Stlpce sa odvodia zo VSETKYCH riadkov, nie z prveho - inak by kluc,
    ktory pribudol az neskor (napr. nova kategoria hlasky), z exportu ticho
    vypadol.

    Nazvy stlpcov sa NEPREKLADAJU. Su to diagnosticke data: kto ich otvara,
    hlada `pre_bpm` a `arm`, nie "tep pred". Prekladat dvadsat takych nazvov
    do vsetkych jazykov appky by bola praca, ktora nikomu nepomoze.
    """
    riadky = [r for r in (rows or []) if isinstance(r, dict)]
    if not riadky:
        return 0
    kluce = set()
    for r in riadky:
        kluce.update(r.keys())
    poradie = [k for k in _PORADIE if k in kluce]
    poradie += sorted(k for k in kluce if k not in poradie)

    von = [separator.join(poradie)]
    for r in riadky:
        von.append(separator.join(_bunka(r.get(k)) for k in poradie))

    tmp = path + ".tmp"
    # utf-8-sig: bez BOM zjedol Excel diakritiku (to iste ako v hr_stats)
    with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
        fh.write("\r\n".join(von) + "\r\n")
    os.replace(tmp, path)
    return len(riadky)


def s_casom(rows, kluc="ts"):
    """Prida citatelny cas k riadkom, ktore maju Unix timestamp.

    Bez toho je v tabulke stlpec cisel typu 1789620987.3, s ktorym sa v
    Exceli neda nic robit bez vzorca.
    """
    von = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        z = dict(r)
        try:
            z["kedy"] = datetime.fromtimestamp(float(r[kluc])).strftime(
                "%d.%m.%Y %H:%M:%S")
        # OverflowError/OSError: cas mimo rozsahu (vo Windows uz rok 3001)
        # - v okne naimportovanom pred 0.2.1 sa take cislo mohlo ocitnut.
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
            pass
        von.append(z)
    return von


def build_bundle(sessions, windows, insights=None, app_version=""):
    """Všetko naraz, ako obyčajný JSON-ovateľný slovník."""
    return {
        "format": "zanshin-dojosync",
        "version": EXPORT_VERSION,
        "app_version": app_version,
        "sessions": list(sessions or []),
        "windows": list(windows or []),
        "insights": insights or {},
    }


def write_bundle(path, bundle):
    """Zápis cez `.tmp` + `os.replace` - pád uprostred nenechá polovičný
    súbor tam, kde hráč čaká zálohu."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(bundle, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path


# --------------------------------------------------------------------------
# Import - jediné miesto, kam vstupuje cudzí súbor
# --------------------------------------------------------------------------

class ImportError_(Exception):
    """Súbor sa nedá použiť. Text je pre hráča, nie traceback."""


# Najvacsi subor, ktory import vobec otvori. Plny export (400 relacii s
# krivkou, 5000 okien s parametrami, poznamky na doraz) ma okolo 12,5 MB,
# takze 50 MB je asi styrnasobok. Vacsi subor export zo Zanshinu byt nemoze
# - a `json.loads` by z neho v pamati spravil este niekolkonasobne viac.
MAX_IMPORT_BAJTOV = 50 * 1024 * 1024

# Rozumny rozsah casovej znacky (`started`, `ts`): 1. 1. 2000 az 1. 1. 2100.
# Znacka mimo neho nie je z tejto appky - a graf Historie
# (`aggregate_by_period`) na nej vo Windows padne (OSError): za rokom 2100
# uz `datetime.fromtimestamp`, v roku 1970 zaokruhlenie na zaciatok dna,
# mesiaca ci roka, ktory v miestnom case (napr. UTC+1) vyjde pred 1970. Zly
# zaznam by tak zhodil stranku pri kazdom otvoreni, nie raz. Preto spodna
# hranica NIE JE nula.
MIN_CAS = 946684800.0
MAX_CAS = 4102444800.0

# Stropy pre JEDNO pole. Vlastne data su hlboko pod nimi (poznamka ma
# `hr_stats.NOTE_MAX` = 280 znakov, krivka `hr_stats.CURVE_POINTS` = 600
# bodov, vnorenie jedna uroven: `zone_seconds`, `params`). Su tu, aby jeden
# cudzi zaznam nenafukol historiu tak, ze sa Historia kresli minuty.
MAX_TEXT = 2000
MAX_POLOZIEK = 100000
MAX_HLBKA = 4


_NIE_CISLO = object()


def _nie_cislo(_text):
    """`parse_constant` pre `json.loads`: NaN, Infinity a -Infinity.

    `json.loads` ich bez toho ticho prijme ako float - a jedno NaN v priemere
    spravi NaN z celeho grafu. Vrati sa objekt, ktory neprejde ziadnou
    kontrolou typu nizsie: pole s nim sa zahodi, zaznam s nim v `started`
    alebo `ts` tiez (a spocita sa)."""
    return _NIE_CISLO


def _konecne(hodnota):
    """Obycajne konecne cislo? bool, NaN ani nekonecno nie.

    `1e999` da z `json.loads` nekonecno aj bez `parse_constant`. Cele cislo
    nad rozsah floatu (10**400) `math.isfinite` neprevedie - OverflowError,
    teda tiez nie."""
    if isinstance(hodnota, bool) or not isinstance(hodnota, (int, float)):
        return False
    try:
        return math.isfinite(hodnota)
    except OverflowError:
        return False


def _cislo(hodnota, minimum=None, maximum=None):
    if not _konecne(hodnota):
        return None
    if minimum is not None and hodnota < minimum:
        return None
    if maximum is not None and hodnota > maximum:
        return None
    return hodnota


# --- kontrola typu jedneho pola -------------------------------------------
#
# PRECO NESTACI `started` A `ts`
# Import zapisuje priamo do hr_sessions.json a hr_windows.json - a odtial to
# cita Historia, grafy aj CSV export. Pole zleho typu sa predtym prenieslo
# bez kontroly a ostalo v historii natrvalo: `"baseline_bpm": "abc"` zhodi
# graf Historie (`float` v `aggregate_by_period`), `"context": 5` alebo
# `"zone_seconds": "x"` CSV export (`session_row`), `"cue_id": [..]` dalsi
# import (nehashovatelny kluc v `merge_windows`). Znamym poliam sa preto
# kontroluje typ, v akom ich appka zapisuje; nezname (ina verzia appky)
# musia byt aspon obycajne JSON data s konecnymi cislami. Co neprejde,
# zahodi sa - zaznam ostane, ako keby bol zo starsej verzie, ktora to pole
# este nemala. None prejde vzdy: appka ho sama zapisuje ako "nevieme".

def _je_text(hodnota):
    """Text, ktory sa da aj ZAPISAT. `json.loads` prijme aj osamely surrogate
    (`"\\ud800"`), `zapis_zoznam` (UTF-8) na nom ale padne - az PO zalohe a
    pripadne s polovicou importu na disku (relacie zapisane, okna nie)."""
    if not isinstance(hodnota, str) or len(hodnota) > MAX_TEXT:
        return False
    try:
        hodnota.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _je_bool(hodnota):
    return isinstance(hodnota, bool)


def _je_skalar(hodnota):
    """Text, cislo, bool alebo None - da sa pouzit aj ako kluc v mnozine
    (`merge_windows` pari okna podla `(ts, cue_id)`)."""
    return (hodnota is None or isinstance(hodnota, bool)
            or _konecne(hodnota) or _je_text(hodnota))


def _je_cisla(hodnota):
    """Krivka: zoznam cisel. None je diera (`activity_trace`)."""
    return (isinstance(hodnota, list) and len(hodnota) <= MAX_POLOZIEK
            and all(x is None or _konecne(x) for x in hodnota))


def _je_texty(hodnota):
    return (isinstance(hodnota, list) and len(hodnota) <= MAX_POLOZIEK
            and all(_je_text(x) for x in hodnota))


def _je_cisla_podla(hodnota):
    """{"calm": 1200.5, ...} - `zone_seconds`, `cues_withheld`."""
    return (isinstance(hodnota, dict) and len(hodnota) <= MAX_POLOZIEK
            and all(_je_text(k) and (v is None or _konecne(v))
                    for k, v in hodnota.items()))


def _je_obycajne(hodnota, hlbka=MAX_HLBKA):
    """Obycajne JSON data: skalar, alebo zoznam/slovnik z nich, najviac
    `hlbka` urovni. Kontrola NEZNAMEHO pola."""
    if _je_skalar(hodnota):
        return True
    if hlbka <= 0:
        return False
    if isinstance(hodnota, list):
        return (len(hodnota) <= MAX_POLOZIEK
                and all(_je_obycajne(x, hlbka - 1) for x in hodnota))
    if isinstance(hodnota, dict):
        return (len(hodnota) <= MAX_POLOZIEK
                and all(_je_text(k) and _je_obycajne(v, hlbka - 1)
                        for k, v in hodnota.items()))
    return False


def _je_slovnik(hodnota):
    """`params` okna: slovnik obycajnych hodnot (cisla, texty, bool)."""
    return isinstance(hodnota, dict) and _je_obycajne(hodnota)


# Polia, ktore appka do relacie zapisuje, a typ, v akom ich cita. Zdroj:
# `hr_stats.HeartStats.summary` (+ `kadencia_vzoriek`), `app._close_hr_session`
# a `hr_stats.attach_context`. Nove pole, ktore tu chyba, nie je chyba -
# prejde kontrolou neznameho pola (`_je_obycajne`).
_TYPY_RELACIE = {
    **dict.fromkeys((
        "min_bpm", "avg_bpm", "max_bpm", "time_over_s", "time_high_s",
        "peak_stress", "triggers", "auto_triggers", "critical_bpm", "samples",
        "sample_dt_median_s", "sample_dt_p90_s", "sample_gaps_over_5s",
        "dropouts", "blind_s", "baseline_bpm", "hrr_bpm", "hrr_events", "hrpi",
        "longest_above_s", "above_runs", "runs_cancelled_dip",
        "runs_cancelled_gap", "stress_hold_s", "stress_threshold",
        "pause_episodes", "snooze_after_cue_s", "snooze_then_s",
        "long_baseline_bpm", "snoozed_s", "hud_visible_s", "hud_visible_frac",
        "felt_load", "valence"), _konecne),
    **dict.fromkeys(("world", "activity", "note", "sleep", "cue_verdict",
                     "cue_rung", "cue_style"), _je_text),
    **dict.fromkeys(("curve", "activity_curve", "trigger_offsets_s"), _je_cisla),
    **dict.fromkeys(("context", "body_peak"), _je_texty),
    **dict.fromkeys(("zone_seconds", "cues_withheld"), _je_cisla_podla),
    **dict.fromkeys(("zen_graduation", "imported"), _je_bool),
}

# To iste pre meracie okno: `measure.build_window` a
# `app._save_measure_windows`.
_TYPY_OKNA = {
    **dict.fromkeys((
        "pre_bpm", "post_bpm", "durability_bpm", "pre_load", "post_load",
        "pre_activity", "post_activity", "load_at", "load_peak",
        "snooze_after_s", "session_started", "offset_s", "natiahnuti"),
        _konecne),
    **dict.fromkeys(("arm", "source", "category", "delivery", "rung",
                     "zone_at", "game", "world"), _je_text),
    **dict.fromkeys(("valid", "audible", "imported"), _je_bool),
    "cue_id": _je_skalar,
    "reasons": _je_texty,
    "params": _je_slovnik,
}


def _ocistene_polia(raw, typy):
    """Kopia zaznamu bez poli, ktore neprejdu kontrolou typu (viz vyssie)."""
    out = {}
    for kluc, hodnota in raw.items():
        if not _je_text(kluc):
            continue
        if hodnota is None or typy.get(kluc, _je_obycajne)(hodnota):
            out[kluc] = hodnota
    return out


def clean_session(raw):
    """Jedna relacia z cudzieho suboru, alebo None.

    `started` a `duration_s` musia davat zmysel, inak sa zo zaznamu neda
    nic spocitat - bez nich sa zahodi cely (a spocita). Ostatne polia
    prejdu kontrolou typu (`_ocistene_polia`): nezname sa prenesu, ak su to
    obycajne data - ina verzia appky moze ukladat viac a zahadzovat to by
    bola strata -, pole zleho typu sa zahodi samo.
    """
    if not isinstance(raw, dict):
        return None
    started = _cislo(raw.get("started"), minimum=MIN_CAS, maximum=MAX_CAS)
    duration = _cislo(raw.get("duration_s"), minimum=0, maximum=60 * 60 * 24)
    if started is None or duration is None:
        return None
    out = _ocistene_polia(raw, _TYPY_RELACIE)
    out["started"] = float(started)
    out["duration_s"] = float(duration)
    out["imported"] = True
    return out


def clean_window(raw):
    """Jedno meracie okno z cudzieho suboru, alebo None. Pravidla ako pri
    `clean_session`; bez pouzitelneho `ts` sa okno zahodi cele."""
    if not isinstance(raw, dict):
        return None
    ts = _cislo(raw.get("ts"), minimum=MIN_CAS, maximum=MAX_CAS)
    if ts is None:
        return None
    out = _ocistene_polia(raw, _TYPY_OKNA)
    out["ts"] = float(ts)
    out["imported"] = True
    return out


def _nacitaj_json(path):
    """Obsah cudzieho suboru ako JSON, alebo `ImportError_`.

    Velkost sa overi PRED citanim a citanie je aj tak zastropovane (subor
    moze medzitym narast). Kodovanie je len UTF-8 (tak pise `write_bundle`),
    BOM sa znesie - Notepad ho vie pridat. Ine kodovanie, rozbity JSON,
    cislo s tisickami cifier (ValueError) aj vnorenie nad strop rekurzie
    su "toto nie je platny JSON", nie traceback.
    """
    try:
        if os.path.getsize(path) > MAX_IMPORT_BAJTOV:
            raise ImportError_("data.import.foreign")
        with open(path, "rb") as fh:
            obsah = fh.read(MAX_IMPORT_BAJTOV + 1)
    except OSError:
        raise ImportError_("data.import.unreadable")
    if len(obsah) > MAX_IMPORT_BAJTOV:
        raise ImportError_("data.import.foreign")
    try:
        return json.loads(obsah.decode("utf-8-sig"), parse_constant=_nie_cislo)
    except (ValueError, RecursionError):
        # UnicodeDecodeError aj JSONDecodeError su podtriedy ValueError.
        raise ImportError_("data.import.not_json")


def parse_bundle(path):
    """Načíta a overí cudzí súbor. Vracia (sessions, windows, zahodene).

    Vyhodí `ImportError_` s vetou pre hráča, keď sa súbor použiť nedá.
    Privelky subor je "foreign": export zo Zanshinu taky byt nemoze.
    """
    raw = _nacitaj_json(path)

    if not isinstance(raw, dict) or raw.get("format") != "zanshin-dojosync":
        raise ImportError_("data.import.foreign")
    if _cislo(raw.get("version"), minimum=1) is None:
        raise ImportError_("data.import.foreign")
    if raw.get("version") > EXPORT_VERSION:
        raise ImportError_("data.import.newer")

    surove_s = raw.get("sessions")
    surove_w = raw.get("windows")
    if not isinstance(surove_s, list) or not isinstance(surove_w, list):
        raise ImportError_("data.import.foreign")

    sessions = [s for s in (clean_session(x) for x in surove_s) if s]
    windows = [w for w in (clean_window(x) for x in surove_w) if w]
    zahodene = (len(surove_s) - len(sessions)) + (len(surove_w) - len(windows))

    if not sessions and not windows:
        raise ImportError_("data.import.empty")
    return sessions, windows, zahodene


def merge_sessions(existing, incoming):
    """Zlúči relácie a zoradí podľa času. Duplikát = rovnaký `started`.

    Vlastný záznam vyhráva: keby sa importoval export z toho istého
    počítača, nemá zmysel prepísať vlastnú reláciu jej kópiou s príznakom
    `imported`.
    """
    known = {s.get("started") for s in existing if isinstance(s, dict)}
    spolu = list(existing) + [s for s in incoming if s.get("started") not in known]
    return sorted(spolu, key=lambda s: s.get("started") or 0)


def merge_windows(existing, incoming):
    known = {(w.get("ts"), w.get("cue_id")) for w in existing if isinstance(w, dict)}
    spolu = list(existing) + [w for w in incoming
                              if (w.get("ts"), w.get("cue_id")) not in known]
    return sorted(spolu, key=lambda w: w.get("ts") or 0)


def vlastne(zaznamy):
    """Len vlastné záznamy, bez importovaných (`imported`).

    Kde appka ráta "koľko relácií už máš" (napr. dávkovanie tichých
    hlášok, `trigger.silent_share_for`), cudzie relácie nesmú posunúť
    počítadlo - import 15 relácií od kamaráta by inak ukončil fázu, v
    ktorej sa tvoje telo ešte len porovnáva."""
    return [z for z in (zaznamy or ()) if isinstance(z, dict) and not z.get("imported")]


def vysledok_importu(moje_s, moje_w, cudzie_s, cudzie_w, nahradit,
                     max_s=None, max_w=None):
    """Čo sa po importe zapíše - a KOĽKO ZO SÚBORU NAOZAJ PRIBUDLO.

    Vracia (relacie, okna, pridane_relacie, pridane_okna). Hlásenie po
    importe predtým ukazovalo dĺžku celého zlúčeného zoznamu: po zlúčení s
    200 vlastnými reláciami tvrdilo "importované: 205", hoci zo súboru
    pribudlo 5. Ráta sa preto, koľko záznamov zo súboru v zapisovanom
    zozname naozaj je - duplikát (vlastný záznam vyhráva) ani to, čo odreže
    strop dĺžky histórie (`max_s`, `max_w`), sa nepočíta.
    """
    cudzie_s = [s for s in (cudzie_s or ()) if isinstance(s, dict)]
    cudzie_w = [w for w in (cudzie_w or ()) if isinstance(w, dict)]
    if nahradit:
        relacie = sorted(cudzie_s, key=lambda s: s.get("started") or 0)
        okna = sorted(cudzie_w, key=lambda w: w.get("ts") or 0)
    else:
        relacie = merge_sessions([s for s in (moje_s or ()) if isinstance(s, dict)],
                                 cudzie_s)
        okna = merge_windows([w for w in (moje_w or ()) if isinstance(w, dict)],
                             cudzie_w)
    if max_s:
        relacie = relacie[-int(max_s):]
    if max_w:
        okna = okna[-int(max_w):]
    # Tie isté objekty (merge ani sorted ich nekopírujú) - podľa identity sa
    # dá presne povedať, ktoré prišli zo súboru.
    zo_suboru_s = {id(s) for s in cudzie_s}
    zo_suboru_w = {id(w) for w in cudzie_w}
    return (relacie, okna,
            sum(1 for s in relacie if id(s) in zo_suboru_s),
            sum(1 for w in okna if id(w) in zo_suboru_w))


def zaloha_pred_importom(cesty, znacka=None):
    """Odloží aktuálne súbory dát vedľa pôvodných ako
    `<súbor>.pred-importom-<čas>.bak`. Vracia zoznam záloh.

    Kópia 1:1 (`shutil.copy2`), nie prepis do iného tvaru. Predošlá záloha
    `hr_sessions.json.bak` bola vo formáte exportu, ktorý `load_sessions`
    nevie načítať - vrátiť sa z nej nedalo ani premenovaním - a meracie
    okná (`hr_windows.json`) sa pri NAHRADIŤ prepísali bez zálohy vôbec.
    Prípona je súrodenec pôvodného súboru, takže "Zmazať históriu"
    (`delete_plan`) zmaže aj zálohy.
    """
    znacka = znacka or datetime.now().strftime("%Y%m%d-%H%M%S")
    zalohy = []
    for cesta in cesty or ():
        if not os.path.isfile(cesta):
            continue
        ciel = "%s.pred-importom-%s.bak" % (cesta, znacka)
        shutil.copy2(cesta, ciel)
        zalohy.append(ciel)
    return zalohy


def zapis_zoznam(cesta, data):
    """Zoznam do JSON cez `.tmp` + `os.replace` - pád uprostred nenechá
    polovičnú históriu (predtým sa importovalo priamo cez open('w'))."""
    tmp = cesta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(list(data), fh, ensure_ascii=False, indent=2)
    os.replace(tmp, cesta)
    return cesta


# --------------------------------------------------------------------------
# Mazanie
# --------------------------------------------------------------------------

def delete_plan(data_dir, legacy_dirs=()):
    """Čo sa zmaže, ako zoznam (i18n kľúč, cesta, existuje, veľkosť).

    Vracia sa to PRED mazaním, aby sa dalo hráčovi presne ukázať, čo
    zmizne. Sľub "všetko ostáva u teba" znamená aj to, že "zmazať" naozaj
    zmaže - a to sa dá ukázať len menovite.

    `legacy_dirs` sú staré priečinky, z ktorých migrácia pri premenovaní
    appky dáta KOPÍROVALA (`paths.legacy_data_dirs`). Kópia histórie tepu
    v nich zostala - bez nich by "zmazať" nechalo druhú kópiu, presne ten
    najhorší druh chyby z hlavičky modulu. Z nich idú do plánu len veci,
    ktoré tam naozaj sú, s kľúčom `legacy` = ten priečinok.
    """
    plan = _plan_priecinka(data_dir, _LOG_SUBORY)
    ciel = os.path.normcase(os.path.abspath(data_dir))
    for stary in legacy_dirs or ():
        if os.path.normcase(os.path.abspath(stary)) == ciel:
            continue
        # V starom priečinku nič nežije, takže ide aj `app.log`.
        for polozka in _plan_priecinka(stary, ("app.log",) + _LOG_SUBORY):
            if polozka["exists"]:
                polozka["legacy"] = stary
                plan.append(polozka)
    return plan


def plan_riadky(plan):
    """Plán mazania zložený do riadkov pre dialóg.

    Vracia [{"label", "params", "exists", "bytes"}]. Položky aktuálneho
    priečinka idú po jednej ako doteraz. Kópie v starých priečinkoch sa
    zhrnú do JEDNÉHO riadku na priečinok (`data.delete.legacy`) - hráč má
    vedieť, že zmiznú aj tie a koľko ich je; zoznam súborov by dialóg
    zahltil. Len meno priečinka, nie celá cesta: cesta v %APPDATA% nesie
    meno účtu vo Windows.
    """
    riadky, stare = [], {}
    for polozka in plan or ():
        stary = polozka.get("legacy")
        if not stary:
            riadky.append({"label": polozka["label"], "params": {},
                           "exists": polozka["exists"], "bytes": polozka["bytes"]})
            continue
        if stary not in stare:
            meno = os.path.basename(os.path.normpath(stary)) or stary
            stare[stary] = {"label": "data.delete.legacy", "params": {"folder": meno},
                            "exists": True, "bytes": 0}
            riadky.append(stare[stary])
        stare[stary]["bytes"] += polozka["bytes"]
    return riadky


def _plan_priecinka(data_dir, log_subory):
    """Plán mazania jedného priečinka dát (viz `delete_plan`)."""
    plan = []
    for kluc, meno in MAZATELNE:
        cesta = os.path.join(data_dir, meno)
        plan.append({"label": kluc, "path": cesta, "exists": os.path.exists(cesta),
                     "bytes": os.path.getsize(cesta) if os.path.exists(cesta) else 0})
        # SÚRODENCI: zálohy a dočasné súbory (hr_windows.json.pred-prepoctom-*,
        # hr_sessions.json.bak, *.tmp). Bez nich "zmazať" nechá kópiu dát.
        # `glob.escape` na základe, nech prípadné [ ] * v ceste nemätie glob.
        for subor in sorted(glob.glob(glob.escape(cesta) + ".*")):
            plan.append({"label": "data.delete.backup", "path": subor,
                         "exists": True, "bytes": os.path.getsize(subor)})
    for kluc, meno in MAZATELNE_PRIECINKY:
        cesta = os.path.join(data_dir, meno)
        velkost = 0
        if os.path.isdir(cesta):
            for koren, _d, subory in os.walk(cesta):
                for f in subory:
                    try:
                        velkost += os.path.getsize(os.path.join(koren, f))
                    except OSError:
                        pass
        plan.append({"label": kluc, "path": cesta, "exists": os.path.isdir(cesta),
                     "bytes": velkost})
    # Vlastné logy po SÚBOROCH, nie celý priečinok - v dev režime `logs/`
    # drží aj gui_screenshots a iné veci mimo histórie hráča.
    logs_dir = os.path.join(data_dir, "logs")
    for meno in log_subory:
        cesta = os.path.join(logs_dir, meno)
        if os.path.exists(cesta):
            plan.append({"label": "data.delete.logs", "path": cesta,
                         "exists": True, "bytes": os.path.getsize(cesta)})
    return plan


def delete_all(data_dir, log=None, legacy_dirs=()):
    """Zmaže všetko z `delete_plan`. Vracia počet zmazaných položiek.

    Priečinok z plánu (cache hlášok) sa zmaže aj s obsahom a hneď vytvorí
    prázdny - appka doň píše za behu. V starých priečinkoch (`legacy`) sa
    nič znova nevytvára: tam už appka nepíše.
    """
    zmazane = 0
    for polozka in delete_plan(data_dir, legacy_dirs):
        cesta = polozka["path"]
        if not polozka["exists"]:
            continue
        try:
            if os.path.isdir(cesta):
                shutil.rmtree(cesta)
                if not polozka.get("legacy"):
                    os.makedirs(cesta, exist_ok=True)
            else:
                os.remove(cesta)
            zmazane += 1
        except Exception as exc:
            if log:
                log(f"nepodarilo sa zmazat {cesta}: {exc}")
    return zmazane
