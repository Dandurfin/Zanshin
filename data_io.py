"""Export, import and deletion of the player's data.

THREE THINGS, EACH WITH A DIFFERENT RISK
----------------------------------------
DELETION has to list exactly what it deletes, and really delete all of
it. The promise "everything stays with you" is on the store page; if
deletion left something behind, it would be the worst kind of bug - one
that nobody sees.

EXPORT is harmless. It comes in two kinds: a CSV of sessions (that is in
`hr_stats`, for a person, into a spreadsheet) and a JSON with EVERYTHING
including the measurement windows - for moving to another computer or
"send it to me, I'm a beta tester".

IMPORT is the only one of the three that can do harm, and it does so
SILENTLY. Foreign data poisons the baseline and the model and it shows
nowhere - the app just starts getting worse. Hence:

  * a strict parser, no `pickle`, no `eval`. The file is at most
    `MAX_IMPORT_BAJTOV`, UTF-8 only, only `json.loads` and then a type
    check of every field (`clean_session`, `clean_window`) - neither NaN
    nor infinity gets through anywhere. A session without a usable
    `started`/`duration_s` and a window without `ts` are dropped whole and
    counted; a field of the wrong type is dropped on its own and the
    record stays, as if it came from an older version of the app.
  * imported records get `imported: True` and the app does not learn from
    them: the baseline, limits and threshold (`hr_stats.ciste_relacie`),
    the cue ladder, insights, effectiveness (`measure`) and the last
    session card all skip them. A foreign body is not your body.
  * the player chooses MERGE or REPLACE - it is never guessed for them.
    REPLACE only after a second confirmation and always with a backup of
    both files (`zaloha_pred_importom`).

The module is purely about data: no Tk, no dialogs. It gets its paths
from outside, so the whole thing can be tested in a tmp folder.
"""

import glob
import json
import math
import os
from datetime import datetime
import shutil

# os.replace that survives a short file lock on Windows (antivirus,
# indexing). `paths` pulls in no app module - no Tk and no cycle.
from paths import nahrad_subor

# Format version. Once the shape of the data changes, an old file can be
# recognised and either migrated or politely refused - instead of silent
# nonsense.
EXPORT_VERSION = 1

# Everything that can be deleted. The order is the order in the list for
# the player. `label` is an i18n key, not finished text - the module
# knows nothing about language.
MAZATELNE = (
    ("data.delete.sessions", "hr_sessions.json"),
    # hr_events.jsonl is a record of EVERY cue for every evening (heart
    # rate, load, game). Until now "Delete history" did NOT delete it -
    # while the dialog reported "Deleted". Exactly the worst kind of bug the
    # header of this module warns about: a deletion that leaves something.
    ("data.delete.events", "hr_events.jsonl"),
    ("data.delete.windows", "hr_windows.json"),
    ("data.delete.insights", "hr_insights.json"),
    # Checkpoint of the open session (`hr_stats.ROZPRACOVANA_MENO`) - the
    # same summary as in hr_sessions.json, just not closed yet. Without it,
    # after "Delete" the recovery at the next start would bring the last
    # evening back into the history.
    ("data.delete.open_session", "hr_session_open.json"),
    # Sessions that could not be saved (`hr_stats.CAKAJUCA_MENO`, 0.3) -
    # without this entry they would come back into the history at the next
    # start after "Delete".
    ("data.delete.pending_session", "hr_session_pending.json"),
)
# Folders that are deleted whole (and created again empty right away if
# the app writes into them while running). `logs` is NOT here ON PURPOSE:
# in dev mode `data_dir` is the project folder and `logs/` in it holds
# gui_screenshots and other things that have nothing to do with the
# player's history - an rmtree of the whole folder deleted them. The
# app's own logs are therefore deleted file by file (see `_LOG_SUBORY` in
# `delete_plan`).
MAZATELNE_PRIECINKY = (
    ("data.delete.tts", os.path.join("audio", "tts_cache")),
)
# The app's own log files. The live `app.log` is NOT here - while running
# it is locked (open handler) and carries only this session; rotation
# overwrites it anyway. The rotated copies and crash.log are deleted.
_LOG_SUBORY = ("crash.log",) + tuple("app.log.%d" % i for i in range(1, 6))


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

# The most events kept in the log. One evening produces on the order of
# dozens, so 20 000 is something like half a year of playing - and a file
# under 5 MB.
MAX_UDALOSTI = 20000


def append_events(path, events, started=None, max_riadkov=MAX_UDALOSTI):
    """Appends state machine events to the JSONL log. Returns the count.

    WHY JSONL AND NOT JSON
    ----------------------
    One event per line means that even a half-written file can be read,
    appended to without loading the whole, and opened in whatever you
    like. A whole JSON would have to be loaded, parsed and rewritten on
    every write.

    WHY IT IS SAVED AT ALL
    ----------------------
    `app._cue_log` collected every event of the state machine - arming,
    deliveries and cancellations with a reason - and at the end of the
    session used their COUNT in the dialog. Then they were thrown away.
    So the course of the evening could not be read back afterwards,
    neither for diagnostics nor when looking for why the app stayed
    silent.

    `started` is the start of the session; it is written with every
    event, so they can be grouped without guessing from the times.
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
    nahrad_subor(tmp, path, uprac_zdroj=True)
    return len(riadky)


def read_events(path):
    """Events from the JSONL log. A damaged line is skipped, not a crash."""
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


# Columns that go first, if they are in the data. The rest is added in
# alphabetical order - so that the file does not change every time a key
# is added.
_PORADIE = ("kedy", "ts", "typ", "arm", "delivery", "category", "reason",
            "cue_id", "valid", "reasons", "pre_bpm", "post_bpm",
            "pre_load", "post_load", "offset_s", "game")


def _bunka(hodnota):
    """One cell for Excel. A decimal COMMA (SK/CZ Excel sees text otherwise),
    a list as space-separated text, None as empty."""
    if hodnota is None:
        return ""
    if isinstance(hodnota, bool):
        return "1" if hodnota else "0"
    if isinstance(hodnota, float):
        return ("%.3f" % hodnota).rstrip("0").rstrip(".").replace(".", ",")
    if isinstance(hodnota, (list, tuple)):
        return " ".join(str(x) for x in hodnota)
    text = str(hodnota)
    # The semicolon is the separator (see hr_stats.CSV_SEPARATOR) - it has no
    # business in text, otherwise the row falls apart into more columns.
    return text.replace(";", ",").replace("\r", " ").replace("\n", " ")


def export_rows_csv(rows, path, separator=";"):
    """List of dicts to CSV. Returns the number of rows.

    Columns are derived from ALL rows, not from the first - otherwise a
    key that only appeared later (e.g. a new cue category) would silently
    drop out of the export.

    Column names are NOT TRANSLATED. This is diagnostic data: whoever
    opens it is looking for `pre_bpm` and `arm`, not "heart rate before".
    Translating twenty such names into all the app's languages would be
    work that helps nobody.
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
    # utf-8-sig: without a BOM Excel mangled diacritics (same as in hr_stats)
    with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
        fh.write("\r\n".join(von) + "\r\n")
    nahrad_subor(tmp, path, uprac_zdroj=True)
    return len(riadky)


def s_casom(rows, kluc="ts"):
    """Adds a readable time to rows that have a Unix timestamp.

    Without it the table has a column of numbers like 1789620987.3, which
    you cannot do anything with in Excel without a formula.
    """
    von = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        z = dict(r)
        try:
            z["kedy"] = datetime.fromtimestamp(float(r[kluc])).strftime(
                "%d.%m.%Y %H:%M:%S")
        # OverflowError/OSError: time out of range (on Windows already the year
        # 3001) - such a number could end up in a window imported before 0.2.1.
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
            pass
        von.append(z)
    return von


def build_bundle(sessions, windows, insights=None, app_version=""):
    """Everything at once, as a plain JSON-serialisable dict."""
    return {
        "format": "zanshin-dojosync",
        "version": EXPORT_VERSION,
        "app_version": app_version,
        "sessions": list(sessions or []),
        "windows": list(windows or []),
        "insights": insights or {},
    }


def write_bundle(path, bundle):
    """Write via `.tmp` + `os.replace` - a crash midway does not leave a half
    file where the player expects a backup."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(bundle, fh, ensure_ascii=False, indent=2)
    nahrad_subor(tmp, path, uprac_zdroj=True)
    return path


# --------------------------------------------------------------------------
# Import - the only place a foreign file enters
# --------------------------------------------------------------------------

class ImportError_(Exception):
    """The file cannot be used. The text is for the player, not a traceback."""


# The largest file the import will open at all. A full export (400
# sessions with a curve, 5000 windows with parameters, notes at the
# limit) is around 12.5 MB, so 50 MB is about four times that. A larger
# file cannot be an export from Zanshin - and `json.loads` would make
# several times more of it in memory.
MAX_IMPORT_BAJTOV = 50 * 1024 * 1024

# Sensible timestamp range (`started`, `ts`): 1. 1. 2000 to 1. 1. 2100.
# A stamp outside it is not from this app - and the History chart
# (`aggregate_by_period`) crashes on it on Windows (OSError): past the
# year 2100 already `datetime.fromtimestamp`, in 1970 the rounding to
# the start of a day, month or year that in local time (e.g. UTC+1)
# falls before 1970. A bad record would thus bring down the page on
# every opening, not once. That is why the lower bound is NOT zero.
MIN_CAS = 946684800.0
MAX_CAS = 4102444800.0

# Caps for ONE field. The app's own data is far below them (a note has
# `hr_stats.NOTE_MAX` = 280 characters, a curve `hr_stats.CURVE_POINTS` =
# 600 points, nesting one level: `zone_seconds`, `params`). They are here
# so that one foreign record does not bloat the history so much that
# History takes minutes to draw.
MAX_TEXT = 2000
MAX_POLOZIEK = 100000
MAX_HLBKA = 4


_NIE_CISLO = object()


def _nie_cislo(_text):
    """`parse_constant` for `json.loads`: NaN, Infinity and -Infinity.

    Without it `json.loads` silently accepts them as float - and one NaN
    in an average makes NaN of the whole chart. It returns an object that
    passes none of the type checks below: a field with it is dropped, and
    so is a record with it in `started` or `ts` (and it is counted)."""
    return _NIE_CISLO


def _konecne(hodnota):
    """A plain finite number? Not bool, NaN or infinity.

    `1e999` gives infinity from `json.loads` even without
    `parse_constant`. An integer beyond the float range (10**400) cannot
    be converted by `math.isfinite` - OverflowError, so also no."""
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


# --- type check of a single field -----------------------------------------
#
# WHY `started` AND `ts` ARE NOT ENOUGH
# The import writes directly into hr_sessions.json and hr_windows.json -
# and from there History, the charts and the CSV export read it. A field
# of the wrong type used to be carried over unchecked and stayed in the
# history for good: `"baseline_bpm": "abc"` brings down the History chart
# (`float` in `aggregate_by_period`), `"context": 5` or
# `"zone_seconds": "x"` the CSV export (`session_row`), `"cue_id": [..]`
# the next import (an unhashable key in `merge_windows`). So known fields
# are checked for the type the app writes them in; unknown ones (another
# app version) must at least be plain JSON data with finite numbers.
# Whatever fails is dropped - the record stays, as if it came from an
# older version that did not have that field yet. None always passes:
# the app itself writes it as "we don't know".

def _je_text(hodnota):
    """Text that can also be WRITTEN. `json.loads` even accepts a lone
    surrogate (`"\\ud800"`), but `zapis_zoznam` (UTF-8) crashes on it -
    only AFTER the backup and possibly with half of the import on disk
    (sessions written, windows not)."""
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
    """Text, number, bool or None - can also be used as a key in a set
    (`merge_windows` pairs windows by `(ts, cue_id)`)."""
    return (hodnota is None or isinstance(hodnota, bool)
            or _konecne(hodnota) or _je_text(hodnota))


def _je_cisla(hodnota):
    """Curve: a list of numbers. None is a gap (`activity_trace`)."""
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
    """Plain JSON data: a scalar, or a list/dict of them, at most `hlbka`
    levels deep. The check for an UNKNOWN field."""
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
    """A window's `params`: a dict of plain values (numbers, texts, bool)."""
    return isinstance(hodnota, dict) and _je_obycajne(hodnota)


# Fields the app writes into a session, and the type it reads them as.
# Source: `hr_stats.HeartStats.summary` (+ `kadencia_vzoriek`),
# `app._close_hr_session` and `hr_stats.attach_context`. A new field that
# is missing here is not a bug - it passes the unknown-field check
# (`_je_obycajne`).
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

# The same for a measurement window: `measure.build_window` and
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
    """Copy of the record minus fields that fail the type check (see above)."""
    out = {}
    for kluc, hodnota in raw.items():
        if not _je_text(kluc):
            continue
        if hodnota is None or typy.get(kluc, _je_obycajne)(hodnota):
            out[kluc] = hodnota
    return out


def clean_session(raw):
    """One session from a foreign file, or None.

    `started` and `duration_s` have to make sense, otherwise nothing can
    be computed from the record - without them it is dropped whole (and
    counted). The other fields go through the type check
    (`_ocistene_polia`): unknown ones are carried over if they are plain
    data - another app version may store more and throwing it away would
    be a loss -, a field of the wrong type is dropped on its own.
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
    """One measurement window from a foreign file, or None. Rules as for
    `clean_session`; without a usable `ts` the window is dropped whole."""
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
    """Content of a foreign file as JSON, or `ImportError_`.

    The size is checked BEFORE reading and the reading is capped anyway
    (the file may grow in the meantime). The encoding is UTF-8 only (that
    is what `write_bundle` writes), a BOM is tolerated - Notepad can add
    one. Another encoding, broken JSON, a number with thousands of digits
    (ValueError) and nesting beyond the recursion limit are all "this is
    not valid JSON", not a traceback.
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
        # UnicodeDecodeError and JSONDecodeError are subclasses of ValueError.
        raise ImportError_("data.import.not_json")


def parse_bundle(path):
    """Loads and checks a foreign file. Returns (sessions, windows, zahodene).

    Raises `ImportError_` with a sentence for the player when the file
    cannot be used. An oversized file is "foreign": an export from
    Zanshin cannot be like that.
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
    """Merges sessions and sorts them by time. Duplicate = the same `started`.

    Your own record wins: if an export from the same computer were
    imported, there is no point in overwriting your own session with its
    copy flagged `imported`.
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
    """Only your own records, without imported ones (`imported`).

    Where the app counts "how many sessions you already have" (e.g. the
    dosing of silent cues, `trigger.silent_share_for`), foreign sessions
    must not move the counter - importing 15 sessions from a friend would
    otherwise end the phase in which your body is still only being
    compared."""
    return [z for z in (zaznamy or ()) if isinstance(z, dict) and not z.get("imported")]


def vysledok_importu(moje_s, moje_w, cudzie_s, cudzie_w, nahradit,
                     max_s=None, max_w=None, info=None):
    """What an import writes - and HOW MANY RECORDS THE FILE REALLY ADDED.

    Returns (relacie, okna, pridane_relacie, pridane_okna). The report
    after an import used to show the length of the whole merged list:
    after merging with 200 of your own sessions it claimed "imported:
    205", although the file added 5. So what is counted is how many
    records from the file really are in the list being written - neither
    a duplicate (your own record wins) nor what the history length cap
    (`max_s`, `max_w`) cuts off is counted.

    `info` (an optional dict, 0.3) receives how many sessions the `max_s`
    cap cut off: `vypadlo` in total, of which `vypadlo_vlastnych` (those
    are in the pre-import backup) - the report should say so, not trim
    silently.
    """
    cudzie_s = [s for s in (cudzie_s or ()) if isinstance(s, dict)]
    cudzie_w = [w for w in (cudzie_w or ()) if isinstance(w, dict)]
    zo_suboru_s = {id(s) for s in cudzie_s}
    if nahradit:
        relacie = sorted(cudzie_s, key=lambda s: s.get("started") or 0)
        okna = sorted(cudzie_w, key=lambda w: w.get("ts") or 0)
    else:
        relacie = merge_sessions([s for s in (moje_s or ()) if isinstance(s, dict)],
                                 cudzie_s)
        okna = merge_windows([w for w in (moje_w or ()) if isinstance(w, dict)],
                             cudzie_w)
    vypadli = []
    if max_s:
        vypadli = relacie[:max(0, len(relacie) - int(max_s))]
        relacie = relacie[-int(max_s):]
    if max_w:
        okna = okna[-int(max_w):]
    if info is not None:
        info["vypadlo"] = len(vypadli)
        info["vypadlo_vlastnych"] = sum(1 for s in vypadli if id(s) not in zo_suboru_s)
    # The same objects (neither merge nor sorted copies them) - by identity
    # it can be said exactly which ones came from the file.
    zo_suboru_w = {id(w) for w in cudzie_w}
    return (relacie, okna,
            sum(1 for s in relacie if id(s) in zo_suboru_s),
            sum(1 for w in okna if id(w) in zo_suboru_w))


def zaloha_pred_importom(cesty, znacka=None):
    """Puts the current data files aside next to the originals as
    `<súbor>.pred-importom-<čas>.bak`. Returns the list of backups.

    A 1:1 copy (`shutil.copy2`), not a rewrite into another shape. The
    previous backup `hr_sessions.json.bak` was in the export format, which
    `load_sessions` cannot load - you could not go back from it even by
    renaming - and the measurement windows (`hr_windows.json`) were
    overwritten on REPLACE with no backup at all. The suffix makes it a
    sibling of the original file, so "Delete history" (`delete_plan`)
    deletes the backups too.
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
    """List to JSON via `.tmp` + `os.replace` - a crash midway does not leave
    a half history (the import used to write directly via open('w'))."""
    tmp = cesta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(list(data), fh, ensure_ascii=False, indent=2)
    nahrad_subor(tmp, cesta, uprac_zdroj=True)
    return cesta


# --------------------------------------------------------------------------
# Deletion
# --------------------------------------------------------------------------

def delete_plan(data_dir, legacy_dirs=()):
    """What gets deleted, as a list of (i18n key, path, exists, size).

    It is returned BEFORE deleting, so the player can be shown exactly
    what will disappear. The promise "everything stays with you" also
    means that "delete" really deletes - and that can only be shown by
    name.

    `legacy_dirs` are old folders from which the migration COPIED the
    data when the app was renamed (`paths.legacy_data_dirs`). A copy of
    the heart rate history stayed in them - without them "delete" would
    leave a second copy, exactly the worst kind of bug from the module
    header. From them only things that really are there go into the plan,
    with the key `legacy` = that folder.
    """
    plan = _plan_priecinka(data_dir, _LOG_SUBORY)
    ciel = os.path.normcase(os.path.abspath(data_dir))
    for stary in legacy_dirs or ():
        if os.path.normcase(os.path.abspath(stary)) == ciel:
            continue
        # Nothing lives in the old folder, so `app.log` goes too.
        for polozka in _plan_priecinka(stary, ("app.log",) + _LOG_SUBORY):
            if polozka["exists"]:
                polozka["legacy"] = stary
                plan.append(polozka)
    return plan


def plan_riadky(plan):
    """The deletion plan put together into rows for the dialog.

    Returns [{"label", "params", "exists", "bytes"}]. Items of the current
    folder go one by one as before. Copies in old folders are summed up
    into ONE row per folder (`data.delete.legacy`) - the player should
    know that those disappear too and how many there are; a list of files
    would swamp the dialog. Only the folder name, not the full path: a
    path in %APPDATA% carries the Windows account name.
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
    """Deletion plan for one data folder (see `delete_plan`)."""
    plan = []
    for kluc, meno in MAZATELNE:
        cesta = os.path.join(data_dir, meno)
        plan.append({"label": kluc, "path": cesta, "exists": os.path.exists(cesta),
                     "bytes": os.path.getsize(cesta) if os.path.exists(cesta) else 0})
        # SIBLINGS: backups and temporary files
        # (hr_windows.json.pred-prepoctom-*, hr_sessions.json.bak, *.tmp).
        # Without them "delete" leaves a copy of the data. `glob.escape` on the
        # base, so any [ ] * in the path do not confuse glob.
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
    # The app's own logs FILE BY FILE, not the whole folder - in dev mode
    # `logs/` also holds gui_screenshots and other things outside the
    # player's history.
    logs_dir = os.path.join(data_dir, "logs")
    for meno in log_subory:
        cesta = os.path.join(logs_dir, meno)
        if os.path.exists(cesta):
            plan.append({"label": "data.delete.logs", "path": cesta,
                         "exists": True, "bytes": os.path.getsize(cesta)})
    return plan


def delete_all(data_dir, log=None, legacy_dirs=()):
    """Deletes all of `delete_plan`. Returns the number of deleted items.

    A folder from the plan (the cue cache) is deleted with its contents
    and created again empty right away - the app writes into it while
    running. In the old folders (`legacy`) nothing is created again: the
    app no longer writes there.
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
