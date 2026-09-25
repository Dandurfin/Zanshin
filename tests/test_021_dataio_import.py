# -*- coding: utf-8 -*-
"""Import cudzieho suboru (0.2.1): prisny parser, ktory to naozaj je.

README slubuje "strict parser, no pickle". Pickle ani eval tam nebol, ale
prisne to nebolo: `clean_session`/`clean_window` preniesli kazde pole okrem
`started`/`ts` bez kontroly, `json.loads` prijal NaN a Infinity, subor v
inom kodovani nez UTF-8 skoncil tracebackom namiesto vety pre hraca a velkost
suboru nemala strop. Importovane zaznamy idu priamo do hr_sessions.json a
hr_windows.json - zle pole v nich zhodilo Historiu alebo CSV export pri
kazdom otvoreni, nie raz.

A zaroven: nic, co appka sama exportuje (aj starsie verzie bez novsich poli),
sa po ceste tam a spat nesmie stratit.
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
    """Export ako TEXT - `json.dumps` by NaN/Infinity/1e999 nenapisal tak,
    ako ich moze obsahovat cudzi subor."""
    return ('{"format": "zanshin-dojosync", "version": %s, "app_version": "x",'
            ' "sessions": [%s], "windows": [%s], "insights": {}}'
            % (version, ", ".join(sessions), ", ".join(windows)))


def chyba(cesta):
    with pytest.raises(data_io.ImportError_) as exc:
        data_io.parse_bundle(cesta)
    return str(exc.value)


# --------------------------------------------------------------------------
# Zaznamy presne v tvare, v akom ich zapisuje appka
# --------------------------------------------------------------------------

def _plna_relacia_a_okna(tmp_path):
    """Relacia a okna cez SKUTOCNE zapisovace appky, nie rucne slovniky:
    `HeartStats.summary`, pole z `app._close_hr_session` (tie iste vyrazy),
    dotaznik cez `hr_stats.attach_context` a okna cez `measure.build_windows`
    s tym, co prida `app._save_measure_windows`.
    """
    t0 = time.time() - 3700.0
    stats = hr_stats.HeartStats(critical_bpm=110)
    stats.session_start = t0
    for i in range(1800):
        ts = t0 + i * 2.0
        stats.add(70 + (i % 45), ts=ts)
        # aktivita len v prvej a poslednej tretine - krivka aktivity ma diery
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
    # `_maybe_graduate`; hrr_bpm cez skutocny `hrr_headline` (umele data
    # vyssie ziadne zotavenie nemaju)
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
    """Kazde pole, ktore appka zapisuje, sa po exporte a importe vrati
    rovnake - len s `imported: True`. Novy typ kontroly nesmie zahodit nic
    vlastne."""
    relacia, okna = _plna_relacia_a_okna(tmp_path)
    cesta = data_io.write_bundle(
        str(tmp_path / "e.json"),
        data_io.build_bundle([relacia], okna, {"x": 1}, "0.2.1"))
    sessions, windows, zahodene = data_io.parse_bundle(cesta)
    assert zahodene == 0
    assert sessions == [dict(relacia, imported=True)]
    assert windows == [dict(w, imported=True) for w in okna]


def test_tabulka_typov_je_overena_skutocnymi_datami(tmp_path):
    """Kazde pole z tabuliek typov ma v skutocnom zazname appky hodnotu
    (nie None - None prejde vzdy, takze by typ neoveril). Keby sa typ v
    tabulke netrafil, test vyssie by to pole stratil; tento strazi, ze sa
    tam naozaj skusa kazde."""
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
    """Export zo starsej verzie nema `cues_withheld`, `world`, `activity`
    ani krivku aktivity - a moze mat pole, ktore uz appka nepise (`tired`
    nahradil `sleep`). Nic z toho nie je dovod zaznam zahodit."""
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
    """Novsia verzia appky moze ukladat viac. Obycajne data sa prenesu."""
    nove = {"started": 1700000000.0, "duration_s": 60.0,
            "nove_pole": {"a": [1, 2.5, None, {"b": "c"}], "d": False}}
    cesta = data_io.write_bundle(str(tmp_path / "e.json"),
                                 data_io.build_bundle([nove], []))
    sessions, _w, _z = data_io.parse_bundle(cesta)
    assert sessions[0]["nove_pole"] == nove["nove_pole"]


# --------------------------------------------------------------------------
# NaN, nekonecno, nezmyselne cisla
# --------------------------------------------------------------------------

@pytest.mark.parametrize("zle", ["NaN", "Infinity", "-Infinity", "1e999",
                                 "-1e999", "1" + "0" * 400, "1e12", "-5",
                                 "0", "1000", "86400"],
                         ids=["nan", "inf", "-inf", "1e999", "-1e999",
                              "10na400", "rok33658", "zaporny",
                              "nula", "rok1970", "rok1970-den2"])
def test_nekonecny_alebo_nezmyselny_cas_zaznam_zahodi(tmp_path, zle):
    """`json.loads` NaN a Infinity prijme a `1e999` je nekonecno. Cas mimo
    2000-2100 by graf Historie vo Windows zhodil (OSError) pri kazdom
    otvoreni - za 2100 aj v roku 1970. Cele cislo s 400 ciframi nesmie
    skoncit OverflowError pri `float()`."""
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
    """Rozsah `MIN_CAS`..`MAX_CAS` musi byt bezpecny pre graf Historie vo
    vsetkych obdobiach - `started=1000` (rok 1970) ho pred opravou zhodil
    vo Windows (OSError) pri kazdom otvoreni, hoci ho import prijal."""
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
    """Jedno NaN v `avg_bpm` by v priemere spravilo NaN z celeho grafu.
    Zaznam sa kvoli nemu ale nezahodi - len to pole, ako keby ho nemal."""
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
    # nic, co import vrati, uz NaN ani nekonecno neobsahuje
    json.dumps(sessions, allow_nan=False)


def test_nan_vo_verzii_je_cudzi_subor(tmp_path):
    cesta = zapis_text(tmp_path, bundle_text(
        sessions=['{"started": 1700000000, "duration_s": 60}'], version="NaN"))
    assert chyba(cesta) == "data.import.foreign"


def test_nekonecno_nezostane_ako_float(tmp_path):
    """`parse_constant` z NaN/Infinity nespravi float - ani hlboko vnutri."""
    text = bundle_text(sessions=['{"started": 1700000000, "duration_s": 60,'
                                 ' "a": [[[NaN]]]}'])
    sessions, _w, _z = data_io.parse_bundle(zapis_text(tmp_path, text))
    assert "a" not in sessions[0]
    assert not any(isinstance(v, float) and not math.isfinite(v)
                   for v in sessions[0].values())


# --------------------------------------------------------------------------
# Pole zleho typu: zahodi sa pole, zaznam ostane - a appka nespadne
# --------------------------------------------------------------------------

def test_pole_zleho_typu_sa_zahodi_a_historia_nespadne(tmp_path):
    """Pred 0.2.1 by tato relacia natrvalo zhodila graf Historie
    (`float("abc")`) aj CSV export (`t in 5`, `"x".get`)."""
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
    # to, co cita Historia a CSV export
    hr_stats.aggregate_by_period(sessions, hr_stats.PERIOD_DAY)
    hr_stats.session_row(s)
    assert hr_stats.session_world(s) == hr_stats.WORLD_DEFAULT


def test_okno_so_zlym_cue_id_nezhodi_dalsi_import(tmp_path):
    """`merge_windows` pari okna podla `(ts, cue_id)` v mnozine - zoznam
    ako `cue_id` by pri dalsom zluceni skoncil TypeError."""
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
    """`json.loads` prijme osamely surrogate (`\\ud800`) - v poznamke, v okne
    aj v kluci. `zapis_zoznam` (UTF-8) na nom padol az PO zalohe: relacie sa
    zapisali, okna nie, a na disku ostal `.tmp`. Pole sa preto zahodi uz
    pri citani a import sa da naozaj zapisat."""
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
    # a to podstatne: vysledok sa da zapisat tam, kam ho zapisuje appka
    data_io.zapis_zoznam(str(tmp_path / "hr_sessions.json"), sessions)
    data_io.zapis_zoznam(str(tmp_path / "hr_windows.json"), windows)
    assert not list(tmp_path.glob("*.tmp"))
    # platny par (emoji) zapisat ide - ten zahadzovat netreba
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
# Kodovanie a rozbity subor: veta pre hraca, nie traceback
# --------------------------------------------------------------------------

def test_subor_v_inom_kodovani_nez_utf8_je_slusna_chyba(tmp_path):
    """Predtym UnicodeDecodeError, ktory `parse_bundle` nechytal."""
    text = bundle_text(sessions=['{"started": 1700000000, "duration_s": 60,'
                                 ' "note": "ľadový"}'])
    assert chyba(zapis_text(tmp_path, text, kodovanie="cp1250")) == "data.import.not_json"
    assert chyba(zapis_text(tmp_path, text, "u16.json", "utf-16")) == "data.import.not_json"


def test_utf8_s_bom_sa_nacita(tmp_path):
    """Notepad vie pri ulozeni pridat BOM - obsah je ale stale nas export."""
    text = bundle_text(sessions=['{"started": 1700000000, "duration_s": 60}'])
    sessions, _w, _z = data_io.parse_bundle(
        zapis_text(tmp_path, text, kodovanie="utf-8-sig"))
    assert len(sessions) == 1


def test_prilis_hlboke_vnorenie_je_slusna_chyba(tmp_path):
    """`json.loads` na tom hodi RecursionError, nie JSONDecodeError."""
    assert chyba(zapis_text(tmp_path, "[" * 100000)) == "data.import.not_json"


def test_cislo_s_tisickami_cifier_je_slusna_chyba(tmp_path):
    """Nad 4300 cifier `json.loads` hodi obycajny ValueError."""
    text = bundle_text(sessions=['{"started": %s, "duration_s": 60}' % ("1" * 5000)])
    assert chyba(zapis_text(tmp_path, text)) == "data.import.not_json"


# --------------------------------------------------------------------------
# Velkost suboru
# --------------------------------------------------------------------------

def test_privelky_subor_sa_odmietne_pred_citanim(tmp_path, monkeypatch):
    """Nad strop sa subor ani neotvori: aj neplatny obsah je "cudzi", nie
    "nie je JSON" - na obsah sa nepozeralo."""
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
    """Subor moze medzi kontrolou velkosti a citanim narast - citanie samo
    ma strop."""
    monkeypatch.setattr(data_io, "MAX_IMPORT_BAJTOV", 200)
    cesta = zapis_text(tmp_path, bundle_text(sessions=[
        '{"started": %d, "duration_s": 60}' % (1700000000 + i) for i in range(10)]))
    with monkeypatch.context() as m:
        m.setattr(data_io.os.path, "getsize", lambda _p: 0)
        assert chyba(cesta) == "data.import.foreign"


def test_strop_velkosti_je_daleko_nad_plnym_exportom(tmp_path):
    """Plny export - 400 relacii (`MAX_SESSIONS`) a 5000 okien
    (`MAX_WINDOWS`) v skutocnom tvare, poznamka na doraz - musi byt hlboko
    pod stropom, inak by import odmietol vlastnu zalohu. Dnes ~12,5 MB;
    ked tento test padne, pribudlo do zaznamov tolko, ze treba zdvihnut
    `MAX_IMPORT_BAJTOV`."""
    relacia, okna = _plna_relacia_a_okna(tmp_path)
    relacia = dict(relacia, note="x" * hr_stats.NOTE_MAX)
    bundle = data_io.build_bundle(
        [dict(relacia, started=relacia["started"] + i)
         for i in range(hr_stats.MAX_SESSIONS)],
        [dict(okna[0], ts=okna[0]["ts"] + i) for i in range(measure.MAX_WINDOWS)],
        {}, "0.2.1")
    velkost = len(json.dumps(bundle, ensure_ascii=False, indent=2).encode("utf-8"))
    assert velkost * 3 < data_io.MAX_IMPORT_BAJTOV, velkost
