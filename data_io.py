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

  * prísny parser, žiadny `pickle`, žiadny `eval`. Len `json.load` a potom
    kontrola typu každého poľa. Čo neprejde, zahodí sa a spočíta.
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
        except (KeyError, TypeError, ValueError):
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


def _cislo(hodnota, minimum=None, maximum=None):
    if isinstance(hodnota, bool) or not isinstance(hodnota, (int, float)):
        return None
    if hodnota != hodnota:                      # NaN
        return None
    if minimum is not None and hodnota < minimum:
        return None
    if maximum is not None and hodnota > maximum:
        return None
    return hodnota


def clean_session(raw):
    """Jedna relácia z cudzieho súboru, alebo None.

    Kontroluje sa len to, na čom appka naozaj stojí. Neznáme polia sa
    prenesú - iná verzia appky môže ukladať viac a zahadzovať to by bola
    strata. Ale `started` a `duration_s` musia dávať zmysel, inak sa zo
    záznamu nedá nič spočítať.
    """
    if not isinstance(raw, dict):
        return None
    started = _cislo(raw.get("started"), minimum=0)
    duration = _cislo(raw.get("duration_s"), minimum=0, maximum=60 * 60 * 24)
    if started is None or duration is None:
        return None
    out = dict(raw)
    out["started"] = float(started)
    out["duration_s"] = float(duration)
    out["imported"] = True
    return out


def clean_window(raw):
    """Jedno meracie okno z cudzieho súboru, alebo None."""
    if not isinstance(raw, dict):
        return None
    ts = _cislo(raw.get("ts"), minimum=0)
    if ts is None:
        return None
    out = dict(raw)
    out["ts"] = float(ts)
    out["imported"] = True
    return out


def parse_bundle(path):
    """Načíta a overí cudzí súbor. Vracia (sessions, windows, sprava).

    Vyhodí `ImportError_` s vetou pre hráča, keď sa súbor použiť nedá.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except json.JSONDecodeError:
        raise ImportError_("data.import.not_json")
    except OSError:
        raise ImportError_("data.import.unreadable")

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
