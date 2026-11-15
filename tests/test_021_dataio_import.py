# -*- coding: utf-8 -*-
"""Importing a foreign file (0.2.1): a strict parser that really is one.

The README promises "strict parser, no pickle". There was no pickle or eval,
but it was not strict: `clean_session`/`clean_window` carried over every
field except `started`/`ts` unchecked, `json.loads` accepted NaN and
Infinity, a file in an encoding other than UTF-8 ended in a traceback instead
of a sentence for the player, and the file size had no cap. Imported records
go straight into hr_sessions.json and hr_windows.json - a bad field in them
crashed History or the CSV export on every open, not just once.

And at the same time: nothing the app itself exports (including older
versions without the newer fields) may get lost on the round trip.
"""
import json
import math
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import data_io  # noqa: E402
import hr_stats  # noqa: E402
import measure  # noqa: E402
import rebrik  # noqa: E402
import trigger  # noqa: E402


def zapis_text(tmp_path, text, meno="export.json", kodovanie="utf-8"):
    cesta = str(tmp_path / meno)
    with open(cesta, "wb") as fh:
        fh.write(text.encode(kodovanie))
    return cesta


def bundle_text(sessions=(), windows=(), version="1"):
    """Export as TEXT - `json.dumps` would not write NaN/Infinity/1e999 the
    way a foreign file can contain them."""
    return ('{"format": "zanshin-dojosync", "version": %s, "app_version": "x",'
            ' "sessions": [%s], "windows": [%s], "insights": {}}'
            % (version, ", ".join(sessions), ", ".join(windows)))


def chyba(cesta):
    with pytest.raises(data_io.ImportError_) as exc:
        data_io.parse_bundle(cesta)
    return str(exc.value)


# --------------------------------------------------------------------------
# Records in exactly the shape the app writes them
# --------------------------------------------------------------------------

def _plna_relacia_a_okna(tmp_path):
    """A session and windows via the app's REAL writers, not hand-made dicts:
    `HeartStats.summary`, the fields from `app._close_hr_session` (the same
    expressions), the questionnaire via `hr_stats.attach_context` and the
    windows via `measure.build_windows` with what
    `app._save_measure_windows` adds.
    """
    t0 = time.time() - 3700.0
    stats = hr_stats.HeartStats(critical_bpm=110)
    stats.session_start = t0
    for i in range(1800):
        ts = t0 + i * 2.0
        stats.add(70 + (i % 45), ts=ts)
        # activity only in the first and last third - activity curve has holes
        if i < 600 or i > 1200:
            stats.note_activity(i % 3 != 0, ts=ts)
    t_hlasky = t0 + 1800.0
    stats.note_trigger(ts=t_hlasky, auto=True, category="breath",
                       cue_id="slot3", arm="voice", source="auto",
                       delivery="pause", delivered=True, rung=rebrik.HLAS,
                       audible=True, load_at=61.5, load_peak=70.2,
                       zone_at="high")
    stats.cues[-1]["snooze_after_s"] = 20.0      # `_zapis_snooze_po_hlaske`

    summary = stats.summary()
    aut = trigger.CueTrigger()
    aut.open_session(silent_share=0.1)
    # app._close_hr_session
    summary["world"] = hr_stats.WORLD_DEFAULT
    summary["longest_above_s"] = round(aut.najdlhsi_nad_s, 1)
    summary["above_runs"] = aut.behov_nad
    summary["runs_cancelled_dip"] = aut.zrusenych_prepadom
    summary["runs_cancelled_gap"] = aut.zrusenych_vypadkom
    summary["stress_hold_s"] = aut.params["stress_hold_s"]
    summary["stress_threshold"] = aut.params["stress_threshold"]
    summary["pause_episodes"] = aut.pause_episodes
    summary["cues_withheld"] = dict(aut.zadrzane)
    summary["cue_rung"] = rebrik.HLAS
    summary["cue_style"] = rebrik.STYL_HLAS
    summary["snooze_after_cue_s"] = 12.0
    summary["snooze_then_s"] = round(max(0.0, 300.25), 1)
    summary["long_baseline_bpm"] = round(float(66.25), 1)
    summary["snoozed_s"] = round(95.5, 1)
    summary["hud_visible_s"] = round(1200.0, 1)
    summary["hud_visible_frac"] = round(max(0.0, min(1.0, 0.5)), 3)
    # `_maybe_graduate`; hrr_bpm via the real `hrr_headline` (the artificial
    # data above have no recovery)
    summary["zen_graduation"] = True
    summary["hrr_bpm"] = hr_stats.hrr_headline([{"peak_bpm": 150, "recovery": 31.6}])

    cesta = str(tmp_path / "hr_sessions.json")
    assert hr_stats.save_session(cesta, summary)
    assert hr_stats.attach_context(
        cesta, summary["started"], ["call", "caffeine"], activity="play",
        note="dobry vecer, " + "x" * 300, sleep="mid", felt_load=6,
        valence=1, body_peak=["flow", "tense"], cue_verdict="landed")
    with open(cesta, encoding="utf-8") as fh:
        relacia = json.load(fh)[-1]

    aktivita = [(t0 + i, 200.0 if i % 4 else 3000.0) for i in range(3600)]
    okna = measure.build_windows(stats.cues, stats._all, load=stats._load,
                                 activity=aktivita, session_started=t0,
                                 game="The Finals")
    params = dict(aut.params)
    params["silent_share"] = aut.silent_share
    for w in okna:
        w["params"] = params
        w["natiahnuti"] = aut.armed_count
        w["world"] = hr_stats.WORLD_DEFAULT
    return relacia, okna


def test_plny_export_prejde_tam_a_spat_bez_straty(tmp_path):
    """Every field the app writes comes back the same after export and
    import - just with `imported: True`. The new type check must not drop
    anything of our own."""
    relacia, okna = _plna_relacia_a_okna(tmp_path)
    cesta = data_io.write_bundle(
        str(tmp_path / "e.json"),
        data_io.build_bundle([relacia], okna, {"x": 1}, "0.2.1"))
    sessions, windows, zahodene = data_io.parse_bundle(cesta)
    assert zahodene == 0
    assert sessions == [dict(relacia, imported=True)]
    assert windows == [dict(w, imported=True) for w in okna]


def test_tabulka_typov_je_overena_skutocnymi_datami(tmp_path):
    """Every field from the type tables has a value in a real app record
    (not None - None always passes, so it would not check the type). If a
    type in the table were wrong, the test above would lose that field;
    this one guards that every field really gets tried there."""
    relacia, okna = _plna_relacia_a_okna(tmp_path)
    for kluc in data_io._TYPY_RELACIE:
        if kluc == "imported":
            continue
        assert relacia.get(kluc) is not None, kluc
        assert data_io._TYPY_RELACIE[kluc](relacia[kluc]), kluc
    for kluc in data_io._TYPY_OKNA:
        if kluc == "imported":
            continue
        assert okna[0].get(kluc) is not None, kluc
        assert data_io._TYPY_OKNA[kluc](okna[0][kluc]), kluc


def test_starsi_export_bez_novsich_poli_prejde(tmp_path):
    """An export from an older version has no `cues_withheld`, `world`,
    `activity` or activity curve - and it may have a field the app no
    longer writes (`sleep` replaced `tired`). None of that is a reason to
    drop the record."""
    stara = {"started": 1700000000.0, "duration_s": 3600.0, "avg_bpm": 80,
             "max_bpm": 130, "curve": [80, 81, 82], "context": ["chill"],
             "tired": True, "zone_seconds": {"calm": 3000.0, "raised": 600.0}}
    okno = {"ts": 1700000100.0, "cue_id": "slot3", "arm": "voice",
            "valid": True, "reasons": [], "pre_bpm": 90.0, "post_bpm": 85.0}
    cesta = data_io.write_bundle(str(tmp_path / "e.json"),
                                 data_io.build_bundle([stara], [okno]))
    sessions, windows, zahodene = data_io.parse_bundle(cesta)
    assert zahodene == 0
    assert sessions == [dict(stara, imported=True)]
    assert windows == [dict(okno, imported=True)]


def test_neznamy_obycajny_udaj_sa_prenesie(tmp_path):
    """A newer app version may store more. Plain data is carried over."""
    nove = {"started": 1700000000.0, "duration_s": 60.0,
            "nove_pole": {"a": [1, 2.5, None, {"b": "c"}], "d": False}}
    cesta = data_io.write_bundle(str(tmp_path / "e.json"),
                                 data_io.build_bundle([nove], []))
    sessions, _w, _z = data_io.parse_bundle(cesta)
    assert sessions[0]["nove_pole"] == nove["nove_pole"]


# --------------------------------------------------------------------------
# NaN, infinity, nonsense numbers
# --------------------------------------------------------------------------

@pytest.mark.parametrize("zle", ["NaN", "Infinity", "-Infinity", "1e999",
                                 "-1e999", "1" + "0" * 400, "1e12", "-5",
                                 "0", "1000", "86400"],
                         ids=["nan", "inf", "-inf", "1e999", "-1e999",
                              "10na400", "rok33658", "zaporny",
                              "nula", "rok1970", "rok1970-den2"])
def test_nekonecny_alebo_nezmyselny_cas_zaznam_zahodi(tmp_path, zle):
    """`json.loads` accepts NaN and Infinity, and `1e999` is infinity. A time
    outside 2000-2100 would crash the History chart on Windows (OSError) on
    every open - beyond 2100 and also in 1970. An integer with 400 digits
    must not end in OverflowError on `float()`."""
    text = bundle_text(
        sessions=['{"started": %s, "duration_s": 60}' % zle,
                  '{"started": 1700000000, "duration_s": 60}'],
        windows=['{"ts": %s}' % zle, '{"ts": 1700000100}'])
    sessions, windows, zahodene = data_io.parse_bundle(zapis_text(tmp_path, text))
    assert [s["started"] for s in sessions] == [1700000000.0]
    assert [w["ts"] for w in windows] == [1700000100.0]
    assert zahodene == 2, "zahodene zaznamy sa musia spocitat"
    for obdobie in (hr_stats.PERIOD_HOUR,) + hr_stats.PERIODS:
        hr_stats.aggregate_by_period(sessions, obdobie)


def test_hranice_casu_graf_historie_znesie():
    """The `MIN_CAS`..`MAX_CAS` range must be safe for the History chart in
    every period - before the fix, `started=1000` (year 1970) crashed it on
    Windows (OSError) on every open, even though the import accepted it."""
    for cas in (data_io.MIN_CAS, data_io.MAX_CAS):
        relacia = data_io.clean_session({"started": cas, "duration_s": 60})
        assert relacia is not None, cas
        for obdobie in (hr_stats.PERIOD_HOUR,) + hr_stats.PERIODS:
            hr_stats.aggregate_by_period([relacia], obdobie)
        assert data_io.s_casom([{"ts": cas}])[0]["kedy"]
    assert data_io.clean_session({"started": data_io.MIN_CAS - 1,
                                  "duration_s": 60}) is None
    assert data_io.clean_window({"ts": data_io.MAX_CAS + 1}) is None


@pytest.mark.parametrize("zle", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_nekonecno_v_inom_poli_zahodi_len_to_pole(tmp_path, zle):
    """A single NaN in `avg_bpm` would turn the whole chart into NaN via the
    average. But the record is not dropped because of it - only that field,
    as if it did not have it."""
    text = bundle_text(sessions=[
        '{"started": 1700000000, "duration_s": 60, "avg_bpm": %s,'
        ' "curve": [80, %s, 82], "zone_seconds": {"calm": %s},'
        ' "nove": {"x": [%s]}, "max_bpm": 130}' % (zle, zle, zle, zle)])
    sessions, _w, zahodene = data_io.parse_bundle(zapis_text(tmp_path, text))
    assert zahodene == 0
    s = sessions[0]
    for kluc in ("avg_bpm", "curve", "zone_seconds", "nove"):
        assert kluc not in s, kluc
    assert s["max_bpm"] == 130
    # nothing the import returns contains NaN or infinity any more
    json.dumps(sessions, allow_nan=False)


def test_nan_vo_verzii_je_cudzi_subor(tmp_path):
    cesta = zapis_text(tmp_path, bundle_text(
        sessions=['{"started": 1700000000, "duration_s": 60}'], version="NaN"))
    assert chyba(cesta) == "data.import.foreign"


def test_nekonecno_nezostane_ako_float(tmp_path):
    """`parse_constant` makes no float of NaN/Infinity - even deep inside."""
    text = bundle_text(sessions=['{"started": 1700000000, "duration_s": 60,'
                                 ' "a": [[[NaN]]]}'])
    sessions, _w, _z = data_io.parse_bundle(zapis_text(tmp_path, text))
    assert "a" not in sessions[0]
    assert not any(isinstance(v, float) and not math.isfinite(v)
                   for v in sessions[0].values())


# --------------------------------------------------------------------------
# Field of the wrong type: the field is dropped, the record stays - and the
# app does not crash
# --------------------------------------------------------------------------

def test_pole_zleho_typu_sa_zahodi_a_historia_nespadne(tmp_path):
    """Before 0.2.1 this session would have permanently crashed the History
    chart (`float("abc")`) and the CSV export (`t in 5`, `"x".get`)."""
    zla = {"started": 1700000000.0, "duration_s": 3600.0, "avg_bpm": 80,
           "baseline_bpm": "abc", "context": 5, "zone_seconds": "x",
           "curve": "abcdefghijkl", "hrr_bpm": [1], "world": {"a": 1},
           "note": "x" * (data_io.MAX_TEXT + 1), "zen_graduation": "ano",
           "body_peak": [1, 2], "cues_withheld": {"bez_pauzy": "x"}}
    cesta = data_io.write_bundle(str(tmp_path / "e.json"),
                                 data_io.build_bundle([zla], []))
    sessions, _w, zahodene = data_io.parse_bundle(cesta)
    assert zahodene == 0, "zaznam s pouzitelnym casom sa nezahadzuje"
    s = sessions[0]
    for kluc in ("baseline_bpm", "context", "zone_seconds", "curve", "hrr_bpm",
                 "world", "note", "zen_graduation", "body_peak",
                 "cues_withheld"):
        assert kluc not in s, kluc
    assert s["avg_bpm"] == 80 and s["imported"] is True
    # what History and the CSV export read
    hr_stats.aggregate_by_period(sessions, hr_stats.PERIOD_DAY)
    hr_stats.session_row(s)
    assert hr_stats.session_world(s) == hr_stats.WORLD_DEFAULT


def test_okno_so_zlym_cue_id_nezhodi_dalsi_import(tmp_path):
    """`merge_windows` pairs windows by `(ts, cue_id)` in a set - a list as
    `cue_id` would end in a TypeError on the next merge."""
    zle = {"ts": 1700000100.0, "cue_id": [1, 2], "valid": "ano",
           "reasons": "x", "params": [1], "pre_bpm": "90", "arm": "voice"}
    cesta = data_io.write_bundle(str(tmp_path / "e.json"),
                                 data_io.build_bundle([], [zle]))
    _s, windows, zahodene = data_io.parse_bundle(cesta)
    assert zahodene == 0
    w = windows[0]
    for kluc in ("cue_id", "valid", "reasons", "params", "pre_bpm"):
        assert kluc not in w, kluc
    assert w["arm"] == "voice"
    data_io.merge_windows([{"ts": 1.0, "cue_id": "slot3"}], windows)


def test_text_ktory_sa_neda_zapisat_sa_zahodi(tmp_path):
    """`json.loads` accepts a lone surrogate (`\\ud800`) - in a note, in a
    window and in a key. `zapis_zoznam` (UTF-8) only failed on it AFTER the
    backup: the sessions were written, the windows were not, and a `.tmp`
    was left on disk. So the field is dropped already when reading, and the
    import can really be written."""
    text = bundle_text(
        sessions=['{"started": 1700000000, "duration_s": 60, "avg_bpm": 80,'
                  ' "note": "a\\ud800b", "nove": ["\\udfff"],'
                  ' "zone_seconds": {"\\ud800": 5}, "\\ud800": 1}'],
        windows=['{"ts": 1700000100, "arm": "voice", "game": "\\ud83d",'
                 ' "reasons": ["\\ud800"], "cue_id": "\\udc00"}'])
    sessions, windows, zahodene = data_io.parse_bundle(zapis_text(tmp_path, text))
    assert zahodene == 0
    s, w = sessions[0], windows[0]
    for kluc in ("note", "nove", "zone_seconds", "\ud800"):
        assert kluc not in s, repr(kluc)
    for kluc in ("game", "reasons", "cue_id"):
        assert kluc not in w, kluc
    assert s["avg_bpm"] == 80 and w["arm"] == "voice"
    # and the main thing: the result can be written where the app writes it
    data_io.zapis_zoznam(str(tmp_path / "hr_sessions.json"), sessions)
    data_io.zapis_zoznam(str(tmp_path / "hr_windows.json"), windows)
    assert not list(tmp_path.glob("*.tmp"))
    # a valid pair (emoji) can be written - no need to drop that one
    assert data_io._je_text("gg \U0001F600")


def test_prilis_hlboke_nezname_pole_sa_zahodi(tmp_path):
    hlboke = 1
    for _ in range(data_io.MAX_HLBKA + 1):
        hlboke = [hlboke]
    s = {"started": 1700000000.0, "duration_s": 60.0, "hlboke": hlboke,
         "akurat": [[[[1]]]]}
    cesta = data_io.write_bundle(str(tmp_path / "e.json"),
                                 data_io.build_bundle([s], []))
    sessions, _w, _z = data_io.parse_bundle(cesta)
    assert "hlboke" not in sessions[0]
    assert sessions[0]["akurat"] == [[[[1]]]]


# --------------------------------------------------------------------------
# Encoding and a broken file: a sentence for the player, not a traceback
# --------------------------------------------------------------------------

def test_subor_v_inom_kodovani_nez_utf8_je_slusna_chyba(tmp_path):
    """Previously a UnicodeDecodeError that `parse_bundle` did not catch."""
    text = bundle_text(sessions=['{"started": 1700000000, "duration_s": 60,'
                                 ' "note": "ľadový"}'])
    assert chyba(zapis_text(tmp_path, text, kodovanie="cp1250")) == "data.import.not_json"
    assert chyba(zapis_text(tmp_path, text, "u16.json", "utf-16")) == "data.import.not_json"


def test_utf8_s_bom_sa_nacita(tmp_path):
    """Notepad can add a BOM on save - but the content is still our export."""
    text = bundle_text(sessions=['{"started": 1700000000, "duration_s": 60}'])
    sessions, _w, _z = data_io.parse_bundle(
        zapis_text(tmp_path, text, kodovanie="utf-8-sig"))
    assert len(sessions) == 1


def test_prilis_hlboke_vnorenie_je_slusna_chyba(tmp_path):
    """`json.loads` raises RecursionError on this, not JSONDecodeError."""
    assert chyba(zapis_text(tmp_path, "[" * 100000)) == "data.import.not_json"


def test_cislo_s_tisickami_cifier_je_slusna_chyba(tmp_path):
    """Above 4300 digits `json.loads` raises a plain ValueError."""
    text = bundle_text(sessions=['{"started": %s, "duration_s": 60}' % ("1" * 5000)])
    assert chyba(zapis_text(tmp_path, text)) == "data.import.not_json"


# --------------------------------------------------------------------------
# File size
# --------------------------------------------------------------------------

def test_privelky_subor_sa_odmietne_pred_citanim(tmp_path, monkeypatch):
    """Above the cap the file is not even opened: even invalid content is
    "foreign", not "not JSON" - nobody looked at the content."""
    monkeypatch.setattr(data_io, "MAX_IMPORT_BAJTOV", 200)
    cesta = str(tmp_path / "velky.json")
    with open(cesta, "wb") as fh:
        fh.write(b"\xff" * 201)
    assert chyba(cesta) == "data.import.foreign"

    platny = data_io.write_bundle(str(tmp_path / "e.json"), data_io.build_bundle(
        [{"started": 1700000000.0 + i, "duration_s": 60.0} for i in range(10)], []))
    assert os.path.getsize(platny) > 200
    assert chyba(platny) == "data.import.foreign"


def test_citanie_je_zastropovane_aj_ked_velkost_klame(tmp_path, monkeypatch):
    """The file can grow between the size check and the read - the read
    itself has a cap."""
    monkeypatch.setattr(data_io, "MAX_IMPORT_BAJTOV", 200)
    cesta = zapis_text(tmp_path, bundle_text(sessions=[
        '{"started": %d, "duration_s": 60}' % (1700000000 + i) for i in range(10)]))
    with monkeypatch.context() as m:
        m.setattr(data_io.os.path, "getsize", lambda _p: 0)
        assert chyba(cesta) == "data.import.foreign"


def test_strop_velkosti_je_daleko_nad_plnym_exportom(tmp_path):
    """A full export - 400 sessions (`MAX_SESSIONS`) and 5000 windows
    (`MAX_WINDOWS`) in their real shape, the note at full length - must be
    far below the cap, otherwise the import would reject our own backup.
    Today ~12.5 MB; when this test fails, so much has been added to the
    records that `MAX_IMPORT_BAJTOV` needs raising."""
    relacia, okna = _plna_relacia_a_okna(tmp_path)
    relacia = dict(relacia, note="x" * hr_stats.NOTE_MAX)
    bundle = data_io.build_bundle(
        [dict(relacia, started=relacia["started"] + i)
         for i in range(hr_stats.MAX_SESSIONS)],
        [dict(okna[0], ts=okna[0]["ts"] + i) for i in range(measure.MAX_WINDOWS)],
        {}, "0.2.1")
    velkost = len(json.dumps(bundle, ensure_ascii=False, indent=2).encode("utf-8"))
    assert velkost * 3 < data_io.MAX_IMPORT_BAJTOV, velkost
