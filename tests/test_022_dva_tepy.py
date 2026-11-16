# -*- coding: utf-8 -*-
"""Two different heart rates in one source - the app notices and says so (0.3).

The app on the watch can write two heart-rate streams interleaved into one
OBS source (in the same second a value from one stream and right after from
the other, one stream 5-10 BPM lower). The measurement
then gets a heart rate that jumps up and down, and the player has no way of
finding out why.

Guarded:
  * detection (`heart_rate.dva_rady_v_okne`, `DvaRadyTepu`): two streams
    5-10 BPM apart are found within ~20-30 s; a single noisy stream at 1 Hz,
    duplicates, one-off spikes, a burst after a stuck Wi-Fi, or streams that
    merge at a calm heart rate do not raise an alarm,
  * the receiver reports it ONCE per run and only for a named source, the
    heart rate goes on unchanged, app.log gets the source name without values,
  * the app writes one line to the journal and shows a text by the switch -
    only while heart rate is coming in, UDP and the connection state take
    precedence, a new run drops it,
  * the texts are in all 11 languages, README and KNOWN_ISSUES tell the truth.

All streams are artificial (random with a fixed seed) - no real measured data.
"""
import logging
import os
import random
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import heart_rate  # noqa: E402
import hr_stats  # noqa: E402
import i18n  # noqa: E402
import theme  # noqa: E402
from _zdroj_appky import zdroj_metody  # noqa: E402
from i18n import tr  # noqa: E402

SEMENA = range(12)


# --------------------------------------------------------------------------
# artificial streams [(cas, bpm)]
# --------------------------------------------------------------------------

def _tep(rng, n, start=80.0):
    """A slowly changing "real" heart rate - a random walk."""
    hr, out = start, []
    for _ in range(n):
        hr = min(170.0, max(55.0, hr + rng.gauss(0, 0.7)))
        out.append(hr)
    return out


def _jeden_sumny(seed, dlzka=300, sum_bpm=2.5, jitter=0.25):
    rng = random.Random(seed)
    hr = _tep(rng, dlzka)
    return [(i + rng.uniform(-jitter, jitter), round(hr[i] + rng.gauss(0, sum_bpm)))
            for i in range(dlzka)]


def _s_duplikatmi(seed, dlzka=300):
    """Every reading arrives twice, the second 0.5 s later - harmless."""
    out = []
    for t, bpm in _jeden_sumny(seed, dlzka, jitter=0.0):
        out += [(t, bpm), (t + 0.5, bpm)]
    return out


def _dva_rady(seed, odstup, dlzka=90, t0=0.0):
    """Each second one value of the higher stream, 0.5 s later the lower."""
    rng = random.Random(seed)
    hr = _tep(rng, dlzka)
    out = []
    for i in range(dlzka):
        out.append((t0 + i, round(hr[i] + odstup + rng.gauss(0, 0.7))))
        out.append((t0 + i + 0.5, round(hr[i] + rng.gauss(0, 0.7))))
    return out


def _dva_rady_v_paroch(seed, odstup, dlzka=180):
    """Pair of messages (higher, lower) every 2-4 s - sparse watch cadence."""
    rng = random.Random(seed)
    hr = _tep(rng, dlzka + 5)
    out, t = [], 0.0
    while t < dlzka:
        i = int(t)
        out.append((t, round(hr[i] + odstup + rng.gauss(0, 0.7))))
        out.append((t + rng.uniform(0.3, 0.6), round(hr[i] + rng.gauss(0, 0.7))))
        t += rng.uniform(2.0, 4.0)
    return out


def _prvy_poplach(rad):
    """Time of the first sample whose window carries two streams - or None."""
    okno = heart_rate.DvaRadyTepu()
    for t, bpm in rad:
        if okno.pridaj(bpm, t):
            return t
    return None


# --------------------------------------------------------------------------
# 1. detection
# --------------------------------------------------------------------------

def test_prahy():
    """The numbers the detection rests on (why - see heart_rate.py)."""
    assert heart_rate.DVA_TEPY_OKNO_S == 60.0
    assert heart_rate.DVA_TEPY_BLIZKO_S == 0.65
    assert heart_rate.DVA_TEPY_SKOK_BPM == 4
    assert heart_rate.DVA_TEPY_MIN_PODIEL_BLIZKYCH == 0.30
    assert heart_rate.DVA_TEPY_MIN_CIKCAKOV == 8
    assert heart_rate.DVA_TEPY_MIN_ROZPATIE_S == 10.0
    assert heart_rate.DVA_TEPY_POMER == 2.0
    assert heart_rate.DVA_TEPY_MIN_VZORIEK == 16


@pytest.mark.parametrize("seed", SEMENA)
def test_jeden_sumny_rad_pri_1_hz_nie(seed):
    assert _prvy_poplach(_jeden_sumny(seed)) is None
    # even very noisy and with worse Wi-Fi jitter
    assert _prvy_poplach(_jeden_sumny(seed, sum_bpm=4.0, jitter=0.35)) is None


@pytest.mark.parametrize("seed", SEMENA)
def test_jeden_rad_s_duplikatmi_nie(seed):
    assert _prvy_poplach(_s_duplikatmi(seed)) is None


@pytest.mark.parametrize("seed", SEMENA)
@pytest.mark.parametrize("odstup", (5, 7, 10))
def test_dva_prepletene_rady_sa_najdu_do_20_s(seed, odstup):
    kedy = _prvy_poplach(_dva_rady(seed, odstup))
    assert kedy is not None and kedy <= 20.0, kedy


@pytest.mark.parametrize("seed", SEMENA)
@pytest.mark.parametrize("odstup", (5, 8))
def test_dva_rady_v_riedkych_paroch_sa_najdu_do_30_s(seed, odstup):
    """A pair of messages every 2-4 s: the window needs 16 samples, i.e. ~8
    pairs (20-23 s on these seeds)."""
    kedy = _prvy_poplach(_dva_rady_v_paroch(seed, odstup))
    assert kedy is not None and kedy <= 30.0, kedy


@pytest.mark.parametrize("seed", SEMENA)
def test_splyvajuce_rady_nie_az_ked_sa_rozidu(seed):
    """At a calm heart rate both streams are the same (or 1 BPM apart) - that
    is not an alarm. Only when they drift apart does the app find it."""
    rng = random.Random(seed)
    hr = _tep(rng, 240)
    rad = []
    for i in range(120):                       # 2 minutes together
        rad.append((float(i), round(hr[i])))
        rad.append((i + 0.5, round(hr[i]) + rng.choice((-1, 0, 0, 1))))
    assert _prvy_poplach(rad) is None
    for i in range(120, 240):                  # lower stream 8 BPM down
        rad.append((float(i), round(hr[i])))
        rad.append((i + 0.5, round(hr[i]) - 8))
    kedy = _prvy_poplach(rad)
    assert kedy is not None and 120.0 < kedy <= 150.0, kedy


@pytest.mark.parametrize("seed", SEMENA)
def test_jednorazove_spicky_nie(seed):
    rng = random.Random(seed)
    rad = []
    for t, bpm in _jeden_sumny(seed, sum_bpm=1.0, jitter=0.0):
        rad.append((t, bpm))
        if rng.random() < 0.05:                 # now and then a stray extra value
            rad.append((t + 0.3, bpm + rng.choice((-15, 15))))
    assert _prvy_poplach(rad) is None


@pytest.mark.parametrize("seed", SEMENA)
def test_davky_po_zaseknutej_wifi_nie(seed):
    """After connecting, 25 old messages arrive at once, then every 20 s a
    burst of 12 messages in a row - still one (noisy) stream."""
    rad = _jeden_sumny(seed, sum_bpm=4.0)
    t0 = rad[25][0]
    rad = [(t0 + 0.002 * i, b) for i, (_t, b) in enumerate(rad[:25])] + rad[25:]
    davkove = []
    i = 0
    while i < len(rad):
        if i > 25 and i % 20 == 0:
            kusy = rad[i:i + 12]
            koniec = kusy[-1][0]
            davkove += [(koniec + 0.004 * k, b) for k, (_t, b) in enumerate(kusy)]
            i += 12
        else:
            davkove.append(rad[i])
            i += 1
    assert _prvy_poplach(davkove) is None


def test_malo_vzoriek_nerozhoduje():
    rad = _dva_rady(0, 8)[:heart_rate.DVA_TEPY_MIN_VZORIEK - 1]
    assert heart_rate.dva_rady_v_okne(rad) is False
    assert heart_rate.dva_rady_v_okne([]) is False


def test_okno_zabuda_a_je_ohranicene():
    okno = heart_rate.DvaRadyTepu()
    for t, bpm in _dva_rady(1, 8, dlzka=30):
        okno.pridaj(bpm, t)
    # then a minute of a single stream - the old pairs drop out of the window
    for i in range(70):
        vysledok = okno.pridaj(80, 30.0 + i)
    assert vysledok is False
    assert okno._vzorky[0][0] >= 99.0 - heart_rate.DVA_TEPY_OKNO_S
    for i in range(2000):
        okno.pridaj(80, 200.0 + i * 0.001)
    assert len(okno._vzorky) <= heart_rate.DVA_TEPY_MAX_VZORIEK


# --------------------------------------------------------------------------
# 2. receiver: once per run, only a named source, heart rate goes on
# --------------------------------------------------------------------------

def test_raz_za_beh_a_len_pomenovany_zdroj():
    run = heart_rate._Run(1)
    hlasenia = [run.note_bpm("Tep", bpm, t) for t, bpm in _dva_rady(2, 8)]
    assert hlasenia.count(True) == 1
    # UDP / a client without a source name: not checked
    run = heart_rate._Run(2)
    assert not any(run.note_bpm(None, bpm, t) for t, bpm in _dva_rady(2, 8))
    # a message without heart rate (steps) does not go into the window
    assert run.note_bpm("Kroky", None, 0.0) is False
    assert run.dva_tepy == {}


def test_kazdy_zdroj_ma_vlastne_okno_a_je_ich_obmedzene():
    """Higher stream into "Tep", lower into "HR": one stream in each source -
    that is fine and not an alarm."""
    run = heart_rate._Run(1)
    for i, (t, bpm) in enumerate(_dva_rady(3, 8)):
        assert run.note_bpm("Tep" if i % 2 == 0 else "HR", bpm, t) is False
    for k in range(20):
        run.note_bpm(f"zdroj {k}", 80, 100.0 + k)
    assert len(run.dva_tepy) <= heart_rate.DVA_TEPY_MAX_ZDROJOV


def _monitor():
    tepy, stavy = [], []
    mon = heart_rate.HeartRateMonitor(
        on_bpm=lambda bpm, gen: tepy.append(bpm),
        on_status=lambda stav, gen: stavy.append(stav))
    return mon, tepy, stavy


def test_emit_nahlasi_raz_a_tep_ide_dalej_nezmeneny(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="zanshin")
    hodiny = [0.0]
    monkeypatch.setattr(heart_rate, "time",
                        types.SimpleNamespace(monotonic=lambda: hodiny[0]))
    mon, tepy, stavy = _monitor()
    run = heart_rate._Run(1)
    rad = _dva_rady(4, 8)
    for t, bpm in rad:
        hodiny[0] = t
        mon._emit(str(bpm).encode(), run, "Tep")
        mon._emit(b"1045", run, "Kroky")         # steps do not affect the window
    assert tepy == [bpm for _t, bpm in rad], "tep ide von bez zmeny"
    assert stavy == [("two_series", "Tep")]
    riadky = [r.getMessage() for r in caplog.records
              if r.name == "zanshin.hr" and "dva rozne rady" in r.getMessage()]
    assert len(riadky) == 1 and "[Tep]" in riadky[0]
    assert not any(ch.isdigit() for ch in riadky[0]), "ziadne hodnoty tepu"


def test_meno_zdroja_do_dennika_bez_zalomeni_a_skratene():
    assert heart_rate.meno_zdroja_do_dennika("Tep") == "Tep"
    assert heart_rate.meno_zdroja_do_dennika("Te\np\r\n  2") == "Te p 2"
    dlhe = heart_rate.meno_zdroja_do_dennika("T" * 100000)
    assert len(dlhe) == heart_rate.MENO_ZDROJA_MAX == 80


# --------------------------------------------------------------------------
# 3. app: journal once per run, text by the switch, precedence
# --------------------------------------------------------------------------

def _nic(*_a, **_k):
    return None


def _app():
    import app as app_mod
    return app_mod.DandurfApp


def _atrapa(**navyse):
    denn, stitky = [], []
    a = types.SimpleNamespace(
        _hr_generation=5, _hr_state="connected", _hr_last_bpm=72,
        _hr_client_linked=True, _hr_session_open=True,
        hr_monitoring_enabled=True, hr_critical_bpm=110,
        pal=theme.tokens(theme.DEFAULT_THEME),
        log=denn.append, denn=denn, stitky=stitky,
        refresh_hr_status_label=lambda: stitky.append(True),
        _close_hr_session=_nic, save_settings=_nic,
        _refresh_dnes_stats=_nic, _refresh_kamae_state_text=_nic)
    a.__dict__.update(navyse)
    return a


def _stav(a, kind, payload, gen=5):
    _app()._apply_hr_status(a, (kind, payload), gen)


def _stitok(a):
    return _app()._hr_status_display(a)


def test_appka_zapise_do_dennika_raz_za_beh():
    a = _atrapa()
    _stav(a, "two_series", "Tep")
    _stav(a, "two_series", "Tep")
    assert a.denn == [tr("log.hr_two_series", source="Tep")]
    assert "Tep" in a.denn[0]
    assert a.stitky, "text pri prepinaci sa musi prekreslit"
    # none of what a dropped connection does
    assert a._hr_state == "connected" and a._hr_generation == 5
    assert a.hr_monitoring_enabled is True


def test_sprava_zo_stareho_behu_sa_zahodi():
    a = _atrapa()
    _stav(a, "two_series", "Tep", gen=4)
    assert a.denn == []
    assert _stitok(a)[0] == "❤️ 72 BPM"


def test_stitok_ked_tep_chodi_ukaze_cislo_aj_upozornenie():
    a = _atrapa()
    assert _stitok(a)[0] == "❤️ 72 BPM"
    _stav(a, "two_series", "Tep")
    text, farba = _stitok(a)
    assert text == "❤️ 72 BPM · " + tr("settings.hr_status_two_series")
    assert farba == a.pal["warn"]


def test_stav_spojenia_a_udp_maju_prednost():
    """The warning belongs to a heart rate that is coming in. Without data
    the player needs to know the real connection state - that stays
    exactly as before."""
    a = _atrapa()
    _stav(a, "two_series", "Tep")
    a._hr_state, a._hr_last_bpm = "linked", None
    assert _stitok(a)[0] == tr("settings.hr_status_waiting")
    a._hr_state = "connecting"
    assert _stitok(a)[0] == tr("settings.hr_status_connecting")
    a._hr_state = "no_client"
    assert _stitok(a)[0] == tr("settings.hr_status_no_client")
    _stav(a, "udp_busy", 4455)
    assert _stitok(a)[0] == tr("settings.hr_status_udp_off")
    a._hr_state = "busy"
    assert _stitok(a)[0] == tr("settings.hr_status_busy")
    # heart rate is back in the same run - so is the warning
    a._hr_state, a._hr_last_bpm = "connected", 75
    assert tr("settings.hr_status_two_series") in _stitok(a)[0]


def test_vypnutie_a_restart_upozornenie_zahodia():
    a = _atrapa()
    _stav(a, "two_series", "Tep")
    # sensor switched off (generation 0)
    a._hr_generation, a._hr_state, a._hr_last_bpm = 0, "disconnected", None
    assert _stitok(a)[0] == tr("settings.hr_status_disconnected")
    # a new run (switching on, restart, another port) has a new generation
    a._hr_generation, a._hr_state, a._hr_last_bpm = 6, "connected", 70
    assert _stitok(a)[0] == "❤️ 70 BPM"
    # and in the new run it may be reported again - once
    _stav(a, "two_series", "Tep", gen=6)
    _stav(a, "two_series", "Tep", gen=6)
    assert len(a.denn) == 2


def test_stop_a_start_menia_generaciu():
    """This is what "disappears after switching off / restart" rests on -
    the flag is never reset by hand anywhere, a new run generation drops
    it."""
    assert "self._hr_generation = 0" in zdroj_metody("stop_heart_rate_monitor")
    assert ("self._hr_generation = self.heart_rate_monitor.start("
            in zdroj_metody("start_heart_rate_monitor"))
    assert "self.heart_rate_monitor.start(" in zdroj_metody("_retry_hr_bind")


# --------------------------------------------------------------------------
# 4. texts and documents
# --------------------------------------------------------------------------

def test_texty_maju_vsetky_jazyky_a_su_kratke():
    for kluc in ("log.hr_two_series", "settings.hr_status_two_series"):
        for jazyk in i18n.LANGUAGES:
            assert i18n.tr_lang(jazyk, kluc).strip(), (kluc, jazyk)
        assert i18n.tr_lang("sk", kluc) != i18n.tr_lang("en", kluc)
    for jazyk in i18n.LANGUAGES:
        assert "{source}" in i18n.STRINGS["log.hr_two_series"][jazyk], jazyk
        # the label stands after the heart-rate number - short
        assert len(i18n.tr_lang(jazyk, "settings.hr_status_two_series")) <= 80, jazyk
    assert len(i18n.LANGUAGES) == 11
    for jazyk in ("cs", "bg"):
        assert (i18n.tr_lang(jazyk, "settings.hr_status_two_series")
                != i18n.tr_lang("en", "settings.hr_status_two_series")), jazyk


def _plain(meno):
    with open(os.path.join(ROOT, meno), encoding="utf-8-sig") as fh:
        text = fh.read()
    return " ".join(" ".join(r.lstrip(">") for r in text.splitlines()).split())


def test_readme_a_known_issues_hovoria_to_iste_co_kod():
    # Audit 0.3d: 0.3, unreleased then, did not belong in the guide for 0.2.1 -
    # README has only a line in Troubleshooting (the label + what to do about
    # it), the median is in docs/HOW-IT-WORKS.md and the full point in
    # KNOWN_ISSUES.
    stitok = i18n.STRINGS["settings.hr_status_two_series"]["en"]
    readme = _plain("README.md")
    ako = _plain("docs/HOW-IT-WORKS.md")
    # Since 0.3 (batch 4) the point about the fix is in CHANGELOG.md, not in
    # KNOWN_ISSUES.
    known = _plain("CHANGELOG.md")
    assert "*%s*" % stitok in readme
    assert "*%s*" % stitok in known
    for text in (ako, known):
        assert "median of the last 3 seconds of readings" in text
    assert "let only the live heart rate write into the heart-rate source" in readme
    assert "only the live heart rate should write into the heart-rate source" in known
    assert hr_stats.ZOBRAZ_OKNO_S == 3.0
    assert "measuring still uses every reading" in ako
    assert "still use every reading" in known
    # 0.3 is released (0.3.1 is the current release) - the documents say
    # which version brought it
    riadok = readme[readme.index("*%s*" % stitok):][:200]
    assert "(from 0.3)" in riadok
    assert "From 0.3" in ako
    with open(os.path.join(ROOT, "KNOWN_ISSUES.md"), encoding="utf-8-sig") as fh:
        k = fh.read()
    assert k.splitlines()[0].endswith("alpha 0.3.1")
    with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8-sig") as fh:
        c = fh.read()
    assert (c.index("\n## What 0.3 changes\n")
            < c.index("## What 0.2.1 fixes"))
