"""Testy metrik z cisteho BPM (hr_stats), analyzy historie (hr_insights) a
kandidatskych IP (netinfo). Vsetko bez Tk, bez siete (netinfo len cita
adresy z OS, nikam neposiela).
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hr_insights
import hr_stats
import netinfo


def _samples(values, start=1000.0, step=1.0):
    return [(start + i * step, float(v)) for i, v in enumerate(values)]


def _feed(stats, values, start=1000.0, step=1.0):
    for i, bpm in enumerate(values):
        stats.add(bpm, ts=start + i * step)
    return start + len(values) * step


# --------------------------------------------------------------------------
# HRR
# --------------------------------------------------------------------------

def test_hrr_is_peak_minus_bpm_one_minute_later():
    """Tep 170 na vrchole, o minutu 140 -> HRR 30 (zadanie)."""
    # 3 min pokoj 70, nastup na 170, potom linearne dole na 140 za 60 s
    values = [70] * 180 + [100, 130, 160, 170] + [170 - (30 * i / 60.0) for i in range(1, 61)] + [140] * 30
    events = hr_stats.heart_rate_recovery(_samples(values))
    assert events, "vrchol 170 musi byt najdeny"
    top = max(events, key=lambda e: e["peak_bpm"])
    assert top["peak_bpm"] == 170
    assert abs(top["recovery"] - 30) <= 1
    assert hr_stats.hrr_headline(events) == 30


def test_hrr_ignores_small_wiggles_and_peaks_without_a_minute_after():
    stats_wiggle = hr_stats.heart_rate_recovery(_samples([70, 72, 71, 73, 70, 74, 71] * 30))
    assert stats_wiggle == [], "drobne zuby +-4 BPM nie su vrchol"
    # vrchol na uplnom konci - minutu po nom nic nie je -> ziadna udalost
    events = hr_stats.heart_rate_recovery(_samples([70] * 120 + [120, 150, 160]))
    assert events == []


def test_hrr_negative_when_heart_rate_keeps_rising_after_local_peak():
    values = [70] * 120 + [110, 100, 95, 92] + [92] * 60 + [130] * 10
    events = hr_stats.heart_rate_recovery(_samples(values))
    assert any(e["peak_bpm"] == 110 and e["recovery"] > 0 for e in events)


def test_heartstats_exposes_hrr_and_summary_fields():
    stats = hr_stats.HeartStats(110)
    values = [70] * 180 + [170] + [170 - (30 * i / 60.0) for i in range(1, 61)] + [140] * 30
    _feed(stats, values)
    assert stats.hrr == 30
    summary = stats.summary()
    for key in ("baseline_bpm", "zone_seconds", "hrr_bpm", "hrr_events", "hrpi",
                "trigger_offsets_s"):
        assert key in summary, key
    assert summary["hrr_bpm"] == 30 and summary["hrr_events"] >= 1


# --------------------------------------------------------------------------
# Pokojova zakladna relacie + trend
# --------------------------------------------------------------------------

def test_session_baseline_is_20th_percentile_of_whole_session():
    values = [60] * 50 + [100] * 150        # 25 % vzoriek na 60 -> 20. percentil = 60
    assert hr_stats.session_baseline(_samples(values)) == 60
    assert hr_stats.session_baseline(_samples([60] * 20 + [100] * 180)) == 100
    assert hr_stats.session_baseline(_samples([60] * 10)) is None


def test_baseline_trend_across_sessions_rising():
    day = 86400.0
    sessions = [{"started": 1000 + i * day, "baseline_bpm": 60 + i} for i in range(7)]
    trend = hr_stats.baseline_trend(sessions)
    assert trend["first"] == 60 and trend["last"] == 66 and trend["delta"] == 6
    assert 6.5 < trend["slope_per_week"] < 7.5
    assert trend["insufficient_span"] is False
    assert hr_stats.baseline_trend([])["points"] == []
    assert hr_stats.baseline_trend([{"started": 1, "avg_bpm": 80}])["slope_per_week"] == 0.0


def test_baseline_trend_flags_insufficient_span_instead_of_exploding():
    """Bug (opraveny): relacie par minut od seba davali "-3009 BPM/tyzden"
    a podobne nezmysly, lebo regresia delila takmer nulovym casovym
    rozptylom. Teraz sa slope pri kratkom rozostupe vobec neuvadza."""
    sessions = [
        {"started": 1000.0, "baseline_bpm": 62.0},
        {"started": 1000.0 + 5 * 60, "baseline_bpm": 58.0},   # o 5 minut neskor
        {"started": 1000.0 + 11 * 60, "baseline_bpm": 61.0},  # o dalsich 6 minut
    ]
    trend = hr_stats.baseline_trend(sessions)
    assert trend["insufficient_span"] is True
    assert trend["slope_per_week"] == 0.0
    # first/last/delta su nezavisle od regresie a mozu ostat pouzitelne
    assert trend["first"] == 62.0 and trend["last"] == 61.0

    # presne na hranici (2 dni) uz je rozostup dostatocny
    sessions_ok = [
        {"started": 1000.0, "baseline_bpm": 60.0},
        {"started": 1000.0 + hr_stats.MIN_TREND_SPAN_S, "baseline_bpm": 64.0},
    ]
    assert hr_stats.baseline_trend(sessions_ok)["insufficient_span"] is False


# --------------------------------------------------------------------------
# Casove obdobia (Historia: Den / Tyzden / Mesiac / Rok)
# --------------------------------------------------------------------------

def test_aggregate_by_period_buckets_same_day_together():
    # realisticky (aktualna era) zaklad - datetime.timestamp() na Windows
    # nezvlada zaporne/tesne-pri-epoche hodnoty, ktore by "started" nikdy
    # v skutocnosti nemalo (vzdy z time.time())
    base = time.mktime((2026, 3, 10, 9, 0, 0, 0, 0, -1))
    day = 86400.0
    sessions = [
        {"started": base, "baseline_bpm": 60.0, "hrr_bpm": 10, "time_over_s": 30, "peak_stress": 20},
        {"started": base + 3600, "baseline_bpm": 70.0, "hrr_bpm": 20, "time_over_s": 90, "peak_stress": 40},
        {"started": base + day, "baseline_bpm": 80.0, "hrr_bpm": None, "time_over_s": 0, "peak_stress": 10},
    ]
    buckets = hr_stats.aggregate_by_period(sessions, hr_stats.PERIOD_DAY)
    assert len(buckets) == 2, "prve dve relacie su v ten isty den"
    first, second = buckets
    assert first["count"] == 2
    assert first["baseline"] == 65.0          # (60+70)/2
    assert first["hrr"] == 15.0               # (10+20)/2
    assert first["over_s"] == 60.0            # (30+90)/2
    assert second["count"] == 1
    assert second["baseline"] == 80.0
    assert second["hrr"] is None, "None sa nezapocitava do priemeru"
    assert first["started"] < second["started"]


def test_aggregate_by_period_month_and_year_bucketing():
    """"Mesiac -> denne priemery, rok -> mesacne" - presne ako v zadani."""
    sessions = [
        {"started": time.mktime((2026, 1, 5, 10, 0, 0, 0, 0, -1)), "baseline_bpm": 60.0},
        {"started": time.mktime((2026, 1, 5, 18, 0, 0, 0, 0, -1)), "baseline_bpm": 62.0},
        {"started": time.mktime((2026, 1, 20, 10, 0, 0, 0, 0, -1)), "baseline_bpm": 70.0},
        {"started": time.mktime((2026, 6, 1, 10, 0, 0, 0, 0, -1)), "baseline_bpm": 65.0},
    ]
    by_day = hr_stats.aggregate_by_period(sessions, hr_stats.PERIOD_DAY)
    assert len(by_day) == 3, "5.1. (x2), 20.1., 1.6. -> 3 dni"
    by_month = hr_stats.aggregate_by_period(sessions, hr_stats.PERIOD_MONTH)
    assert len(by_month) == 2, "januar + jun"
    assert by_month[0]["count"] == 3 and by_month[1]["count"] == 1


def test_aggregate_by_period_skips_sessions_without_started():
    assert hr_stats.aggregate_by_period([{"baseline_bpm": 60.0}, "junk", None],
                                        hr_stats.PERIOD_WEEK) == []


def test_period_start_ts_week_is_a_monday_midnight():
    # stvrtok 2026-01-15 15:30 -> pondelok 2026-01-12 00:00
    thursday = time.mktime((2026, 1, 15, 15, 30, 0, 0, 0, -1))
    start = hr_stats.period_start_ts(hr_stats.PERIOD_WEEK, now=thursday)
    start_struct = time.localtime(start)
    assert start_struct.tm_wday == 0        # pondelok
    assert (start_struct.tm_hour, start_struct.tm_min, start_struct.tm_sec) == (0, 0, 0)
    assert start <= thursday


def test_count_sessions_since_filters_and_sums_duration():
    sessions = [
        {"started": 100.0, "duration_s": 120.0},
        {"started": 200.0, "duration_s": 60.0},
        {"started": 50.0, "duration_s": 999.0},   # pred hranicou
        "junk",
    ]
    count, duration = hr_stats.count_sessions_since(sessions, since_ts=100.0)
    assert count == 2 and duration == 180.0


# --------------------------------------------------------------------------
# Cas v pasmach - v sekundach, nie vo vzorkach
# --------------------------------------------------------------------------

def test_time_in_zones_counts_seconds_not_samples():
    critical = 110
    slow = _samples([60] * 60 + [130] * 60, step=1.0)            # 60 s pokoj, 60 s kriticke
    fast = _samples([60] * 120 + [130] * 120, step=0.5)          # to iste pri 2 Hz
    zs = hr_stats.time_in_zones(slow, critical, baseline=60)
    zf = hr_stats.time_in_zones(fast, critical, baseline=60)
    assert abs(zs[hr_stats.ZONE_CRITICAL] - 60) <= 1.5
    assert abs(zf[hr_stats.ZONE_CRITICAL] - 60) <= 1.5
    assert abs(zs[hr_stats.ZONE_CALM] - zf[hr_stats.ZONE_CALM]) <= 1.5


def test_live_zone_seconds_accumulate_in_seconds():
    slow = hr_stats.HeartStats(100)
    _feed(slow, [62] * 120 + [130] * 120, step=1.0)
    fast = hr_stats.HeartStats(100)
    _feed(fast, [62] * 240 + [130] * 240, step=0.5)
    total_slow = sum(slow.zone_seconds.values())
    total_fast = sum(fast.zone_seconds.values())
    assert abs(total_slow - total_fast) < 2.0
    assert slow.zone_seconds[hr_stats.ZONE_CRITICAL] + slow.zone_seconds[hr_stats.ZONE_HIGH] > 60


# --------------------------------------------------------------------------
# HRPI
# --------------------------------------------------------------------------

def test_hrpi_is_largest_k_with_bpm_at_least_k_for_k_seconds():
    # 120 BPM po 2 minuty -> k = 120 (120 s >= 120)
    assert hr_stats.persistence_index(_samples([120] * 121)) == 120
    # 120 BPM len 91 s -> k je 91 (91 s pri >= 91 BPM plati, 92 uz nie)
    assert hr_stats.persistence_index(_samples([120] * 91)) == 91
    # 85 BPM po 3 hodiny -> 85
    assert hr_stats.persistence_index(_samples([85] * 3 * 3600)) == 85
    assert hr_stats.persistence_index([]) == 0


def test_hrpi_uses_time_not_sample_count():
    one_hz = hr_stats.persistence_index(_samples([100] * 100, step=1.0))
    two_hz = hr_stats.persistence_index(_samples([100] * 200, step=0.5))
    assert one_hz == two_hz == 100


# --------------------------------------------------------------------------
# Analyza historie
# --------------------------------------------------------------------------

def _session(started, duration_s=3600, baseline=62, hrr=18, triggers=(), over=0):
    return {"started": started, "duration_s": duration_s, "samples": duration_s,
            "baseline_bpm": baseline, "hrr_bpm": hrr, "avg_bpm": baseline + 15,
            "min_bpm": baseline - 2, "max_bpm": 140, "time_over_s": over,
            "trigger_offsets_s": list(triggers), "triggers": len(triggers),
            "peak_stress": 60}


def test_analysis_survives_empty_and_single_history():
    assert hr_insights.analyze([]) [0]["key"] == "need_more"
    assert hr_insights.analyze(None)[0]["key"] == "need_more"
    one = hr_insights.analyze([_session(1000)])
    assert one[0]["key"] == "need_more" and one[0]["params"]["n"] == 1
    # rozbite zaznamy sa ignoruju, nespadne
    assert hr_insights.analyze([None, "x", {"duration_s": "abc"}])[0]["key"] == "need_more"


def test_analysis_detects_rising_resting_baseline():
    now = 20 * 86400.0
    prev = [_session(now - 12 * 86400 + i * 3600, baseline=60) for i in range(3)]
    recent = [_session(now - 2 * 86400 + i * 3600, baseline=67) for i in range(3)]
    keys = [i["key"] for i in hr_insights.analyze(prev + recent, now=now)]
    assert "resting_up" in keys and "steady" not in keys


def test_analysis_detects_improving_hrr():
    now = 20 * 86400.0
    prev = [_session(now - 12 * 86400 + i * 3600, hrr=14) for i in range(3)]
    recent = [_session(now - 2 * 86400 + i * 3600, hrr=24) for i in range(3)]
    out = hr_insights.analyze(prev + recent, now=now)
    hrr = next(i for i in out if i["key"] == "hrr_up")
    assert hrr["tone"] == hr_insights.TONE_GOOD and hrr["params"]["delta"] == 10


def test_analysis_flags_late_triggers_in_long_sessions():
    now = 10 * 86400.0
    sessions = [_session(now - i * 86400, duration_s=3 * 3600,
                         triggers=(8000, 8500, 9000)) for i in range(3)]
    keys = [i["key"] for i in hr_insights.analyze(sessions, now=now)]
    assert "triggers_late" in keys


# --------------------------------------------------------------------------
# Kedy prichadzaju spustenia - hustota, nie podiel (B3a)
#
# V 90-min relacii je prva hodina dve tretiny casu, takze aj rovnomerne
# spustenia davali ~67 % "v prvej hodine" a stary prah 66 % hlasil vzor,
# ktory tam nebol. To iste "po dvoch hodinach" v 4-5 h relaciach.
# --------------------------------------------------------------------------

def _timing_keys(duration_s, triggers, n=3):
    now = 10 * 86400.0
    sessions = [_session(now - i * 86400, duration_s=duration_s, triggers=triggers)
                for i in range(n)]
    return {i["key"]: i for i in hr_insights.analyze(sessions, now=now)}


def test_even_triggers_in_90min_sessions_are_not_early():
    # kazdych 15 min, v strede useku: 4 v prvej hodine, 2 po nej = 67 %,
    # ale hustota je vsade rovnaka
    out = _timing_keys(90 * 60, (450, 1350, 2250, 3150, 4050, 4950))
    assert "triggers_early" not in out and "triggers_late" not in out


def test_front_loaded_triggers_are_early():
    out = _timing_keys(90 * 60, (300, 1200, 2100, 3000))
    assert out["triggers_early"]["params"]["share"] == 100
    assert out["triggers_early"]["tone"] == hr_insights.TONE_INFO


def test_front_loading_is_seen_even_below_two_thirds_in_long_sessions():
    # 3 h: prva hodina 3 spustenia, dalsie dve hodiny 2 - podiel len 60 %,
    # ale prva hodina je 3x hustejsia. Stary podiel to prehliadol.
    out = _timing_keys(3 * 3600, (600, 1500, 2400, 5000, 9000), n=4)
    assert out["triggers_early"]["params"]["share"] == 60


def test_few_front_loaded_triggers_stay_quiet():
    # 6 z 6 v prvej hodine 90-min relacii - pri rovnomernom rozlozeni to
    # vyjde nahodou skoro v kazdom desiatom pripade (2/3)^6 = 8,8 %
    out = _timing_keys(90 * 60, (900, 2700))
    assert "triggers_early" not in out


def test_even_triggers_in_5h_sessions_are_not_late():
    # kazdych 30 min: 6 z 10 az po dvoch hodinach (60 % > stary prah 50 %),
    # ale tie hodiny su aj 60 % casu - nic neskoro nehustne
    out = _timing_keys(5 * 3600, tuple(900 + 1800 * k for k in range(10)))
    assert "triggers_late" not in out and "triggers_early" not in out


def test_timing_survives_years_of_history_and_broken_duration():
    # 300 relacii = 1500 spusteni: naivne math.comb(1500, k) * float pretecie
    now = 400 * 86400.0
    sessions = [_session(now - i * 86400, duration_s=90 * 60,
                         triggers=(300, 1200, 2100, 3000, 4000)) for i in range(300)]
    keys = [i["key"] for i in hr_insights.analyze(sessions, now=now)]
    assert "triggers_early" in keys
    # nekonecne trvanie (pokazeny JSON) nesmie zhodit analyzu v pozadi
    broken = [_session(now - i * 86400, duration_s=90 * 60, triggers=(300, 1200))
              for i in range(3)]
    broken.append(dict(broken[0], duration_s=float("inf"), started=now - 5 * 86400))
    hr_insights.analyze(broken, now=now)


def _even(duration_s, n):
    # n spusteni, kazde v strede rovnakeho useku - dokonale rovnomerne
    return tuple(duration_s * (i + 0.5) / n for i in range(n))


def _mixed_keys(parts):
    now = 30 * 86400.0
    sessions, i = [], 0
    for count, duration_s, triggers in parts:
        for _ in range(count):
            sessions.append(_session(now - i * 86400, duration_s=duration_s,
                                     triggers=triggers))
            i += 1
    return {x["key"] for x in hr_insights.analyze(sessions, now=now)}


def test_tense_short_evenings_next_to_calm_long_ones_are_not_early():
    # V KAZDEJ relacii su spustenia rovnomerne. Napate su len kratke vecery,
    # pokojne su dlhe - scitany cas by z toho urobil "prva hodina je
    # hustejsia" (Simpson). Ocakavanie po relaciach to nesmie.
    keys = _mixed_keys([(3, 90 * 60, _even(90 * 60, 7)),
                        (4, 5 * 3600, _even(5 * 3600, 5))])
    assert "triggers_early" not in keys


def test_tense_long_evenings_next_to_calm_ones_are_not_late():
    # dve napate 5-h relacie (2/h rovnomerne) + sest pokojnych 150-min bez
    # spustenia: nic neprislo "az po dvoch hodinach", len dlhe vecery boli
    # napate od zaciatku
    keys = _mixed_keys([(2, 5 * 3600, _even(5 * 3600, 10)),
                        (6, 150 * 60, ())])
    assert "triggers_late" not in keys


def test_one_broken_duration_does_not_silence_timing_forever():
    now = 10 * 86400.0
    sessions = [_session(now - i * 86400, duration_s=90 * 60,
                         triggers=(300, 1200, 2100, 3000)) for i in range(3)]
    for bad in (float("nan"), float("inf")):
        broken = sessions + [dict(sessions[0], duration_s=bad, started=now - 5 * 86400)]
        keys = {x["key"] for x in hr_insights.analyze(broken, now=now)}
        assert "triggers_early" in keys


def test_analysis_reports_steady_when_nothing_stands_out():
    now = 10 * 86400.0
    sessions = [_session(now - i * 86400) for i in range(4)]
    keys = [i["key"] for i in hr_insights.analyze(sessions, now=now)]
    assert keys == ["steady"]


def test_insights_save_and_load(tmp_path):
    path = str(tmp_path / "hr_insights.json")
    assert hr_insights.save_insights(path, [{"key": "steady", "tone": "good", "params": {}}])
    loaded = hr_insights.load_insights(path)
    assert loaded["insights"][0]["key"] == "steady" and loaded["computed_at"]
    assert hr_insights.load_insights(str(tmp_path / "nope.json"))["insights"] == []


# --------------------------------------------------------------------------
# netinfo
# --------------------------------------------------------------------------

def test_local_ip_candidates_are_real_ipv4_without_loopback():
    import ipaddress
    cands = netinfo.local_ip_candidates()
    for ip in cands:
        addr = ipaddress.IPv4Address(ip)
        assert not addr.is_loopback and not addr.is_link_local
    assert len(cands) == len(set(cands)), "bez duplicit"
    preferred = netinfo.preferred_local_ip()
    if preferred:
        assert cands[0] == preferred, "preferovana adresa musi byt prva"


# --------------------------------------------------------------------------
# Odporúčania o tichu (18. 9.)
#
# Jediné insighty, ktoré hráčovi hovoria, ČO MÁ UROBIŤ. Preto stoja na
# tvrdých číslach zo spúšťača, nie na dojme z tepu — a preto je dôležité,
# aby netrafili nesprávnu príčinu: rada „ozvi sa častejšie" pri vypadávajúcich
# hodinkách by ho poslala ladiť prah namiesto pripojenia.
# --------------------------------------------------------------------------

def _relacia(**kw):
    zaklad = {"started": 1789000000.0, "duration_s": 2400.0, "samples": 900,
              "baseline_bpm": 70, "auto_triggers": 0, "above_runs": 0,
              "longest_above_s": 0.0, "runs_cancelled_gap": 0,
              "stress_hold_s": 45.0}
    zaklad.update(kw)
    return zaklad


def _kluce(relacie):
    return {i["key"] for i in hr_insights.analyze(relacie, now=1789200000.0)}


def test_vypadky_maju_prednost_pred_ladenim():
    """Pri výpadkoch je „najdlhší úsek" rozsekaný dierami v dátach, nie
    fyziológiou. Radiť podľa neho by poslalo hráča opravovať nesprávnu vec."""
    relacie = [_relacia(started=1789000000.0 + i * 86400.0,
                        above_runs=9, longest_above_s=11.0,
                        runs_cancelled_gap=8) for i in range(4)]
    kluce = _kluce(relacie)
    assert "cue_dropouts" in kluce
    assert "cue_almost" not in kluce and "cue_far" not in kluce


def test_telo_sa_ani_raz_nedostalo_hore():
    """Politika nepomôže — hranica tepu je nastavená privysoko."""
    relacie = [_relacia(started=1789000000.0 + i * 86400.0) for i in range(4)]
    assert "cue_never_above" in _kluce(relacie)


def test_tesne_vedla_radi_zmenu_politiky():
    relacie = [_relacia(started=1789000000.0 + i * 86400.0,
                        above_runs=5, longest_above_s=38.0) for i in range(4)]
    assert "cue_almost" in _kluce(relacie)


def test_hlboko_pod_radi_hranicu_tepu():
    """Telo ide hore-dole rýchlejšie, než appka čaká — skracovať čakanie
    tu nestačí a rada to musí povedať."""
    relacie = [_relacia(started=1789000000.0 + i * 86400.0,
                        above_runs=6, longest_above_s=9.0) for i in range(4)]
    kluce = _kluce(relacie)
    assert "cue_far" in kluce and "cue_almost" not in kluce


def test_zadrzane_hlasky_netvrdia_ze_zataz_nevydrzala():
    """0.2 (stress-gate): spúšťač sa natiahol a appka sama mlčala. Záťaž
    teda hore vydržala — „len na chvíľu" by klamalo, a „nič som si
    nevšimla" tiež. Radšej žiadna rada."""
    relacie = [_relacia(started=1789000000.0 + i * 86400.0,
                        above_runs=6, longest_above_s=9.0,
                        cues_withheld={"bez_pauzy": 0, "nevhodna_chvila": 2,
                                       "nedalo_sa": 0})
               for i in range(4)]
    kluce = _kluce(relacie)
    assert not (kluce & {"cue_almost", "cue_far", "steady"})
    # pokazená hodnota nezhodí analýzu a nič nepredstiera
    relacie = [_relacia(started=1789000000.0 + i * 86400.0,
                        above_runs=6, longest_above_s=9.0,
                        cues_withheld={"nevhodna_chvila": "x"})
               for i in range(4)]
    assert "cue_far" in _kluce(relacie)


def test_ked_hlasky_chodia_sa_nerieskuje_nic():
    """Odporúčanie o tichu nesmie prísť do večera, v ktorom appka hovorila."""
    relacie = [_relacia(started=1789000000.0 + i * 86400.0,
                        auto_triggers=4, above_runs=6, longest_above_s=60.0)
               for i in range(4)]
    kluce = _kluce(relacie)
    assert not (kluce & {"cue_never_above", "cue_almost", "cue_far"})


def test_stare_relacie_bez_pocitadiel_neradia_nic():
    """Relácie uložené pred 17. 9. tie čísla nemajú. Radiť z chýbajúcich
    dát by znamenalo hádať."""
    relacie = []
    for i in range(4):
        r = _relacia(started=1789000000.0 + i * 86400.0)
        for k in ("above_runs", "longest_above_s", "runs_cancelled_gap",
                  "stress_hold_s"):
            del r[k]
        relacie.append(r)
    kluce = _kluce(relacie)
    assert not (kluce & {"cue_dropouts", "cue_never_above", "cue_almost", "cue_far"})


def test_kroky_su_rozdiel_nie_kumulativny_sucet():
    """Hodinky posielajú súčet za deň — ten o pohybe TERAZ nehovorí nič."""
    st = hr_stats.HeartStats(critical_bpm=110)
    t = 1000.0
    for i in range(4):
        st.note_metrics(steps=1000, ts=t + i * 1.5)
    assert st.steps_per_min(now=t + 5) == 0.0, "stojaci počet = sedí"

    t2 = t + 10
    for i, spolu in enumerate(range(1000, 1090, 10)):
        st.note_metrics(steps=spolu, ts=t2 + i * 1.5)
    assert 70 <= st.steps_per_min(now=t2 + 13) <= 90


def test_bez_krokov_je_to_nevieme_nie_nula():
    """„Nevieme" a „nula krokov" sú dve rôzne veci.

    Zameniť ich by znamenalo tvrdiť, že hráč sedí, vždy keď hodinky kroky
    neposielajú — a práve na tom má stáť vyraďovanie okien.
    """
    st = hr_stats.HeartStats(critical_bpm=110)
    assert st.steps_per_min(now=1000.0) is None
    st.note_metrics(speed=0.0, ts=1000.0)
    assert st.steps_per_min(now=1000.0) is None, "rychlost nie je pocet krokov"


def test_restart_pocitadla_na_hodinkach_nevyrobi_kroky():
    """O polnoci (alebo pri reštarte appky na hodinkách) súčet spadne na nulu.

    Záporný rozdiel sa musí zahodiť — inak by sa z neho stal obrovský
    záporný prírastok alebo, pri naivnom abs(), falošná dávka krokov.
    """
    st = hr_stats.HeartStats(critical_bpm=110)
    t = 1000.0
    st.note_metrics(steps=9000, ts=t)
    st.note_metrics(steps=5, ts=t + 1.5)
    assert st.steps_per_min(now=t + 2) == 0.0


def test_appka_mlci_kym_chodia_kroky():
    """Tep od pohybu odlíšiť nejde, takže sa pri chôdzi nesmie ozvať.

    Uendes a kol. (2026, JMIR, N=127): model s 55 EKG príznakmi má pri
    strednej fyzickej aktivite špecificitu 0,418 — takmer šesť z desiatich
    okien chôdze označí ako stres. Jeden BPM každých 1,5 s to nezvládne.
    """
    import inspect
    import app as app_mod
    telo = inspect.getsource(app_mod.DandurfApp._cue_can_fire)
    assert "steps_per_min" in telo, "brana na pohyb chyba"
    assert "KROKY_PRAH_ZA_MIN" in telo
    # `None` (hodinky kroky neposielaju) nesmie appku umlcat
    assert "kroky is not None" in telo, "neznalost by umlcala appku"


def test_pokazena_relacia_sa_pozna_podla_nemoznych_skokov():
    """Tep sa medzi dvoma vzorkami (~1,5 s) o 30 bpm neposunie.

    19. 9. to spôsobil parser, ktorý po pridaní krokov a rýchlosti do správy
    z hodiniek čítal raz tep a raz počet krokov. Výsledkom bola 52-minútová
    relácia s priemerom 124 a maximom 235 — a tá by inak natrvalo skrivila
    základňu aj vypočítanú hranicu.
    """
    zdrava = {"curve": [78, 80, 79, 82, 85, 83, 81, 79, 80, 84, 82, 80]}
    assert not hr_stats.je_podozriva(zdrava)

    pokazena = {"curve": [135, 69, 135, 145, 79, 145, 145, 91, 145, 182, 111, 182]}
    assert hr_stats.je_podozriva(pokazena)

    # prikratka krivka sa neposudzuje - radsej nechat, nez zahodit nevinnu
    assert not hr_stats.je_podozriva({"curve": [80, 120]})


def test_podozriva_relacia_neurcuje_zakladnu_ani_hranicu():
    # `duration_s` od 0.2.1: kriticky tep sa uci len z relacii aspon 5 min
    # (`je_dost_dlha`) - bez neho by obe strany padli na zalohu a rovnost
    # nizsie by nic nemerala.
    zdrave = [{"curve": [78, 80, 79, 82, 81, 80, 79, 83, 82, 80] * 30,
               "baseline_bpm": 78, "duration_s": 1800.0} for _ in range(4)]
    pokazena = {"curve": [135, 69, 135, 145, 79, 145, 182, 91, 222, 111] * 30,
                "baseline_bpm": 135, "duration_s": 1800.0}
    assert hr_stats.dlhodoba_zakladna(zdrave + [pokazena]) == \
        hr_stats.dlhodoba_zakladna(zdrave)
    assert hr_stats.dynamicky_kriticky(zdrave) != hr_stats.KRITICKY_ZALOHA
    assert hr_stats.dynamicky_kriticky(zdrave + [pokazena]) == \
        hr_stats.dynamicky_kriticky(zdrave)


def test_kriticky_tep_bez_dat_padne_na_zalohu():
    """Kým nie je z čoho rátať, appka nesmie tvrdiť vypočítané číslo."""
    assert hr_stats.dynamicky_kriticky([]) == hr_stats.KRITICKY_ZALOHA
    assert hr_stats.dynamicky_kriticky(
        [{"curve": [80] * 120}]) == hr_stats.KRITICKY_ZALOHA


def test_kriticky_tep_nesmie_sadnut_na_zakladnu():
    """Headroom nesmie byť symbolický.

    `headroom = max(12, kritický − základňa)`. Keby vypočítaná hranica sadla
    tesne nad základňu, záťaž by sa vyškálovala na pár úderoch a appka by
    reagovala na šum.
    """
    # `duration_s` od 0.2.1 (relacia aspon 5 min) - inak zaloha 110 a test
    # by presiel bez toho, aby poistku vobec skusil.
    pokojne = [{"curve": [70] * 120, "baseline_bpm": 69, "duration_s": 600.0}
               for _ in range(4)]
    h = hr_stats.dynamicky_kriticky(pokojne, baseline=69)
    assert h != hr_stats.KRITICKY_ZALOHA
    assert h >= 69 + hr_stats.KRITICKY_MIN_NAD_ZAKLADNOU


def test_kriticky_tep_uz_nie_je_nastavenie():
    """Pole „Tep, pri ktorom pomôcť" zmizlo zo systému.

    Nedalo sa nastaviť dobre: pri základni 77 dávalo čokoľvek do 89 rovnaký
    výsledok (podlaha headroomu 12), takže hráč posúval číslo a nič sa
    nemenilo — a zároveň robilo z pokojného večera 52 % času v červenom.
    """
    from _zdroj_appky import zdroj_appky
    zdroj = zdroj_appky()
    assert "hr_critical_bpm_var" not in zdroj, "policko sa vratilo"
    assert '"hr_critical_bpm": int(self.hr_critical_bpm)' not in zdroj, \
        "hodnota sa stale uklada ako nastavenie"
    assert "hr_stats.dynamicky_kriticky(" in zdroj, "nic to nepocita"


def test_krivka_aktivity_rozlisi_hru_menu_a_odchod():
    """Odhad „kedy sa naozaj hralo" bez toho, aby sme čítali hru.

    Overwolf by to povedal presne (`scene`), ale je to slepá ulička —
    licenčne nepoužiteľné a technicky injektor. Zostáva hustota vstupu
    z `GetLastInputInfo`, ktorú appka meria tak či tak.
    """
    st = hr_stats.HeartStats(critical_bpm=110)
    t = 1000.0
    for i in range(60):                      # hra: vstup takmer stále
        st.note_activity(True, ts=t + i)
    for i in range(60):                      # menu: občas klik
        st.note_activity(i % 6 == 0, ts=t + 60 + i)
    for i in range(60):                      # preč od PC
        st.note_activity(False, ts=t + 120 + i)

    k = st.activity_trace(points=12)
    assert len(k) == 12
    hra = sum(k[0:4]) / 4
    menu = sum(k[4:8]) / 4
    prec = sum(k[8:12]) / 4
    assert hra > 0.9 and menu < 0.4 and prec == 0.0, (hra, menu, prec)


def test_krivka_aktivity_je_podiel_nie_okamih():
    """Bod krivky je PODIEL aktivity v úseku, nie hodnota v okamihu.

    Inak by z toho bol náhodný šum jednotiek a núl namiesto toho, čo nás
    zaujíma: ako husto sa hralo.
    """
    st = hr_stats.HeartStats(critical_bpm=110)
    t = 1000.0
    for i in range(100):
        st.note_activity(i % 2 == 0, ts=t + i)   # presne polovica
    k = st.activity_trace(points=5)
    assert all(0.3 <= b <= 0.7 for b in k), k


def test_bez_vzoriek_je_krivka_prazdna():
    """Žiadne dáta nie sú to isté čo nulová aktivita."""
    st = hr_stats.HeartStats(critical_bpm=110)
    assert st.activity_trace() == []


# --------------------------------------------------------------------------
# Otrávenie kalibrácie pokazenými / cudzími dátami (B8–B12)
# --------------------------------------------------------------------------

def test_pokazena_relacia_bez_krivky_je_podozriva():
    """B11/B12: nemožné maximum (kroky čítané ako tep) sa musí chytiť aj keď
    krivka chýba alebo ju podvzorkovanie zahladilo. `max_bpm` je zo surových."""
    assert hr_stats.je_podozriva({"max_bpm": 235, "avg_bpm": 124}) is True
    assert hr_stats.je_podozriva(
        {"max_bpm": 235, "avg_bpm": 124, "curve": [120] * 600}) is True
    # zdravá relácia (aj intenzívna) prejde
    assert hr_stats.je_podozriva(
        {"max_bpm": 165, "avg_bpm": 100,
         "curve": [90 + i % 20 for i in range(600)]}) is False


def test_importovana_relacia_sa_nezapocita_do_kalibracie():
    """B10: cudzie telo nesmie určovať základňu ani prahy."""
    vlastna = {"curve": [90] * 600, "baseline_bpm": 72, "max_bpm": 150,
               "avg_bpm": 95, "duration_s": 1800}
    cudzia = dict(vlastna, imported=True, baseline_bpm=55)
    assert cudzia not in hr_stats.ciste_relacie([vlastna, cudzia])
    assert len(hr_stats.ciste_relacie([vlastna, cudzia])) == 1


def test_kriticky_tep_ma_strop():
    """B9: jedna nezmyselná krivka nesmie vytlačiť kritický prah mimo dosah
    a umlčať appku. `dynamicky_prah_zataze` strop má, tento ho tiež musí mať."""
    nezmysel = [{"curve": [235] * 600, "baseline_bpm": 70, "max_bpm": 180,
                 "avg_bpm": 160, "duration_s": 1800} for _ in range(3)]
    h = hr_stats.dynamicky_kriticky(nezmysel, baseline=70)
    assert h <= hr_stats.KRITICKY_STROP[1]


def test_hr_insights_filtruje_pokazene_relacie():
    """B8: pokazená relácia nesmie vyrobiť falošné rady."""
    import hr_insights
    zdrave = [{"started": 1000.0 + i, "duration_s": 1800, "samples": 500,
               "baseline_bpm": 72, "max_bpm": 150, "avg_bpm": 95,
               "curve": [90] * 600} for i in range(4)]
    pokazena = {"started": 9000.0, "duration_s": 1800, "samples": 500,
                "baseline_bpm": 135, "max_bpm": 235, "avg_bpm": 160,
                "curve": [235] * 600}
    # analýza s pokazenou aj bez nej dá to isté — pokazená neprispela
    assert hr_insights.analyze(zdrave + [pokazena]) == hr_insights.analyze(zdrave)


# --------------------------------------------------------------------------
# Pokrytie signalu (C4): prah sa uci len z casu, ked tep chodil
# --------------------------------------------------------------------------

_ZONY_1800 = {"calm": 900.0, "raised": 600.0, "high": 300.0, "critical": 0.0}


def _vlna(hore, opakovani=60):
    """Plynula krivka ako telo - bez skokov, ktore by chytil `je_podozriva`."""
    vlna = []
    for _ in range(opakovani):
        vlna.extend(range(70, hore, 5))
        vlna.extend(range(hore, 70, -5))
    return vlna


def test_pokrytie_signalu_z_ulozenych_poli():
    """Sucet pasiem / trvanie - z toho, co kazdy suhrn uz uklada."""
    p = hr_stats.pokrytie_signalu(
        {"duration_s": 1000.0,
         "zone_seconds": {"calm": 600.0, "raised": 200.0, "high": 100.0,
                          "critical": 0.0}})
    assert abs(p - 0.9) < 1e-9
    # zaokruhlenie v suhrne moze dat o chlp viac nez trvanie - strop je 1
    assert hr_stats.pokrytie_signalu(
        {"duration_s": 100.0, "zone_seconds": {"calm": 100.4}}) == 1.0


def test_pokrytie_signalu_ked_sa_to_nevie_je_none():
    """Nevedet nie je „0 %": stare relacie, pokazene subory a hodinky, ktore
    posielali ridsie nez kazdych 12 s (kazda medzera vypadok, sucet nula)."""
    zony = {"calm": 500.0}
    for relacia in (
            {"duration_s": 1000.0},                              # stara
            {"duration_s": 1000.0, "zone_seconds": {}},
            {"duration_s": 1000.0, "zone_seconds": None},
            {"duration_s": 0, "zone_seconds": zony},
            {"duration_s": -5.0, "zone_seconds": zony},
            {"zone_seconds": zony},                              # bez trvania
            {"duration_s": 1000.0, "zone_seconds": {"calm": 0.0}},
            {"duration_s": 1000.0, "zone_seconds": {"calm": "x"}},
            {"duration_s": 1000.0, "zone_seconds": {"calm": None}},
            {"duration_s": 1000.0, "zone_seconds": [1, 2, 3]},
            {"duration_s": "dlho", "zone_seconds": zony},
            {"duration_s": float("nan"), "zone_seconds": zony},
            {"duration_s": 1000.0, "zone_seconds": {"calm": float("nan")}},
            None, "relacia", 42, []):
        assert hr_stats.pokrytie_signalu(relacia) is None, relacia


def test_prehravanie_prahu_nevazi_vecer_podla_dier():
    """Krivka je preriedena podla vzoriek, nie casu - diery v nej nie su.

    Ten isty vecer s dvojnasobnym `duration_s` (polovicu casu hodinky
    mlcali) a tym istym suctom pasiem sa musi prehrat rovnako - rovnaky
    pocet bodov, rovnaky 80. percentil. Predtym sa natiahol na cely cas a
    v prahu vazil dvakrat viac.
    """
    celistvy = {"curve": _vlna(130), "duration_s": 1800.0,
                "zone_seconds": dict(_ZONY_1800)}
    dierava = dict(celistvy, duration_s=3600.0)
    assert hr_stats.pokrytie_signalu(dierava) == 0.5
    a = hr_stats.load_z_krivky(celistvy, 70.0, 110)
    b = hr_stats.load_z_krivky(dierava, 70.0, 110)
    assert a and abs(len(a) - len(b)) <= 1
    assert hr_stats._percentile(sorted(a), 0.8) == \
        hr_stats._percentile(sorted(b), 0.8)
    # bez pasiem (stara relacia) sa natiahne na cele trvanie ako doteraz
    stara = {k: v for k, v in dierava.items() if k != "zone_seconds"}
    assert len(hr_stats.load_z_krivky(stara, 70.0, 110)) > 1.9 * len(a)


def test_relacia_bez_pokrytia_sa_prehra_ako_doteraz():
    """Bez pasiem, s nulovym suctom aj s plnym pokrytim - to iste ako pred C4."""
    krivka = [70 + (i % 20) for i in range(600)]
    bez = {"curve": krivka, "duration_s": 600.0}
    ocakavane = hr_stats.load_z_krivky(bez, 65.0, 110)
    assert len(ocakavane) == int(600.0 / 1.5) - 29   # ako test kalibracie
    for zony in ({"calm": 0.0, "raised": 0.0}, {"calm": 400.0, "raised": 200.0},
                 {"calm": 700.0}):
        assert hr_stats.load_z_krivky(
            dict(bez, zone_seconds=zony), 65.0, 110) == ocakavane, zony


def test_do_prahu_patri_ta_ista_relacia_aj_s_malym_pokrytim():
    """Podmienka „aspon 5 minut" ostava na `duration_s` - ktore relacie sa
    rataju do prahu (a do „vypocitane z n relacii"), sa nemeni."""
    relacia = {"curve": [70 + (i % 20) for i in range(600)], "duration_s": 600.0,
               "zone_seconds": {"calm": 180.0}}             # pokrytie 0,3
    body = hr_stats.load_z_krivky(relacia, 65.0, 110)
    assert len(body) == int(180.0 / 1.5) - 29


def test_dierava_relacia_neposunie_prah_viac_nez_celistva():
    """Vecer s dierami ma v prahu rovnaku vahu ako ten isty vecer bez nich.

    Pred C4 sa jeho krivka natiahla aj cez diery, takze do 80. percentilu
    vlozil dvakrat viac bodov nez celistvy dvojca a prah posunul (tu 76 -> 78).
    """
    zdrave = [{"curve": _vlna(110), "duration_s": 1800.0, "baseline_bpm": 70,
               "zone_seconds": dict(_ZONY_1800)} for _ in range(4)]
    dierava = {"curve": _vlna(140), "duration_s": 3600.0, "baseline_bpm": 70,
               "zone_seconds": dict(_ZONY_1800)}
    dvojca = dict(dierava, duration_s=1800.0)
    assert not hr_stats.je_podozriva(dierava)
    s_dierami = hr_stats.dynamicky_prah_zataze(
        zdrave + [dierava], baseline=70, critical=110)
    assert s_dierami is not None
    assert s_dierami == hr_stats.dynamicky_prah_zataze(
        zdrave + [dvojca], baseline=70, critical=110)
    # kontrola, ze test nieco meria: natiahnuta cez diery by prah posunula
    natiahnuta = {k: v for k, v in dierava.items() if k != "zone_seconds"}
    assert hr_stats.dynamicky_prah_zataze(
        zdrave + [natiahnuta], baseline=70, critical=110) != s_dierami


def test_brana_na_pokrytie_zamerne_nie_je():
    """Vecer s malym pokrytim sa z ucenia NEVYRADUJE (C4, viz komentar pri
    `pokrytie_signalu`): pomer klesne aj pri uspatom PC alebo hodinkach na
    nabijacke a tie vecery maju dobre data. Kto branu postavi, zmeni tento
    test vedome - a s datami zo skutocneho zleho vecera."""
    slaba = {"curve": [80 + i % 5 for i in range(600)], "duration_s": 3600.0,
             "max_bpm": 90, "zone_seconds": {"calm": 700.0}}   # pokrytie ~0,19
    assert hr_stats.pokrytie_signalu(slaba) < 0.5
    assert hr_stats.ciste_relacie([slaba]) == [slaba]


# --------------------------------------------------------------------------
# Zive pokrytie pre widget kvality signalu
# --------------------------------------------------------------------------

def test_zive_pokrytie_je_none_kym_nie_je_z_coho():
    st = hr_stats.HeartStats(critical_bpm=110)
    assert st.signal_coverage_at(now=5000.0) is None          # ziadna vzorka
    koniec = _feed(st, [75] * 30, start=1000.0)
    assert st.signal_coverage_at(now=koniec) is None           # 30 s < minuta
    assert st.signal_coverage_at(now=1000.0 + 59.9) is None
    assert st.signal_coverage_at(now=1000.0 + 60.0) is not None


def test_zive_pokrytie_nekolise_medzi_vzorkami():
    """Hodinky posielaju kazde ~3 s. Medzi dvoma vzorkami nesmie cislo klesat
    a pri dalsej skocit spat - otvoreny interval sa zarata (najviac 5 s)."""
    st = hr_stats.HeartStats(critical_bpm=110)
    koniec = _feed(st, [75] * 40, start=1000.0, step=3.0)    # posledna 1117
    posledna = koniec - 3.0
    for po in (0.0, 1.0, 2.9, 4.99):
        assert abs(st.signal_coverage_at(now=posledna + po) - 1.0) < 1e-9, po
    # po 5 s ticha uz cas so signalom nepribuda (ten isty strop ako `add`)
    pokr = st.signal_coverage_at(now=posledna + 8.0)
    assert abs(pokr - (117.0 + 5.0) / 125.0) < 1e-9


def test_zive_pokrytie_meria_od_prvej_vzorky_nie_od_zapnutia():
    """Cakanie, kym sa hodinky pripoja, nie je slaby signal."""
    st = hr_stats.HeartStats(critical_bpm=110)
    st.session_start = 0.0                     # relacia otvorena davno predtym
    koniec = _feed(st, [75] * 120, start=1000.0)
    assert abs(st.signal_coverage_at(now=koniec - 0.5) - 1.0) < 1e-9


def test_zive_pokrytie_sedi_s_vypadkom_a_je_vedla_neho():
    """Vypadok: pokrytie klesne presne o slepy cas a widget ma vedla neho aj
    pocet vypadkov (`dropouts`) a slepe sekundy (`blind_seconds`)."""
    st = hr_stats.HeartStats(critical_bpm=110)
    _feed(st, [75] * 60, start=1000.0)                       # 1000..1059
    st.note_dropout(od=1059.0)
    st.clear_live()
    # pocas vypadku otvoreny interval nie je - tep nechodi
    pocas = st.signal_coverage_at(now=1080.0)
    assert abs(pocas - 59.0 / 80.0) < 1e-9
    _feed(st, [75] * 60, start=1090.0)                       # 1090..1149
    teraz = 1149.5
    pokr = st.signal_coverage_at(now=teraz)
    assert st.dropouts == 1
    assert st.blind_seconds(now=teraz) == 31.0
    assert abs(pokr - (1.0 - 31.0 / (teraz - 1000.0))) < 1e-9


def test_zive_pokrytie_zarata_aj_sekundy_z_kalibracie():
    """Prvy vecer bez zakladne: sekundy cakaju v `_zony_cakaju`, kym zakladna
    nepride - aj tie su cas so signalom."""
    st = hr_stats.HeartStats(critical_bpm=110)
    koniec = _feed(st, [75] * 25, start=1000.0, step=3.0)    # 1000..1072
    assert st.is_calibrating and st._zony_cakaju
    assert abs(st.signal_coverage_at(now=koniec - 2.0) - 1.0) < 1e-9


def test_zive_pokrytie_je_vlastnost_pre_widget_a_nuluje_sa_s_relaciou():
    st = hr_stats.HeartStats(critical_bpm=110)
    t0 = time.time() - 120.0
    _feed(st, [75] * 120, start=t0)
    pokr = st.signal_coverage
    assert pokr is not None and pokr > 0.95
    st.note_dropout()
    st.reset_session()
    assert st.signal_coverage is None
    assert st.dropouts == 0 and st.blind_seconds() == 0.0
