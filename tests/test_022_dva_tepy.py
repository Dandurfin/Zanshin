# -*- coding: utf-8 -*-
"""Dva rozne tepy v jednom zdroji - appka to rozpozna a povie (0.2.2).

Appka na hodinkach vie do jedneho OBS zdroja pisat dva rady tepu prepletene
(v tej istej sekunde hodnota z jedneho radu a hned z druheho, jeden rad o
5-10 BPM nizsie). Meranie
potom dostava tep, ktory skace hore-dole, a hrac nema ako zistit preco.

Strazi sa:
  * rozpoznanie (`heart_rate.dva_rady_v_okne`, `DvaRadyTepu`): dva rady
    5-10 BPM od seba sa najdu do ~20-30 s; jeden sumny rad pri 1 Hz,
    duplikaty, jednorazove spicky, davka po zaseknutej Wi-Fi ani splyvajuce
    rady pri pokojnom tepe poplach nevyvolaju,
  * prijimac to hlasi RAZ za beh a len pre pomenovany zdroj, tep ide dalej
    nezmeneny, do app.log ide meno zdroja bez hodnot,
  * appka zapise jeden riadok do dennika a ukaze text pri prepinaci - len
    kym tep chodi, UDP a stav spojenia maju prednost, novy beh ho zahodi,
  * texty su vo vsetkych 11 jazykoch, README a KNOWN_ISSUES hovoria pravdu.

Vsetky rady su umele (nahodne s pevnym seedom) - ziadne skutocne namerane data.
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
# umele rady [(cas, bpm)]
# --------------------------------------------------------------------------

def _tep(rng, n, start=80.0):
    """Pomaly sa meniaci "skutocny" tep - nahodna prechadzka."""
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
    """Kazde citanie pride dvakrat, druhe o 0,5 s neskor - neskodne."""
    out = []
    for t, bpm in _jeden_sumny(seed, dlzka, jitter=0.0):
        out += [(t, bpm), (t + 0.5, bpm)]
    return out


def _dva_rady(seed, odstup, dlzka=90, t0=0.0):
    """Kazdu sekundu jedna hodnota z vyssieho radu a o 0,5 s z nizsieho."""
    rng = random.Random(seed)
    hr = _tep(rng, dlzka)
    out = []
    for i in range(dlzka):
        out.append((t0 + i, round(hr[i] + odstup + rng.gauss(0, 0.7))))
        out.append((t0 + i + 0.5, round(hr[i] + rng.gauss(0, 0.7))))
    return out


def _dva_rady_v_paroch(seed, odstup, dlzka=180):
    """Par sprav (vyssi, nizsi rad) kazde 2-4 s - riedka kadencia hodiniek."""
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
    """Cas prvej vzorky, pri ktorej okno nesie dva rady - alebo None."""
    okno = heart_rate.DvaRadyTepu()
    for t, bpm in rad:
        if okno.pridaj(bpm, t):
            return t
    return None


# --------------------------------------------------------------------------
# 1. rozpoznanie
# --------------------------------------------------------------------------

def test_prahy():
    """Cisla, na ktorych stoji rozpoznanie (preco - viz heart_rate.py)."""
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
    # aj vela sumny a s horsim jitterom Wi-Fi
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
    """Par sprav kazde 2-4 s: okno potrebuje 16 vzoriek, cize ~8 parov
    (na tychto seedoch 20-23 s)."""
    kedy = _prvy_poplach(_dva_rady_v_paroch(seed, odstup))
    assert kedy is not None and kedy <= 30.0, kedy


@pytest.mark.parametrize("seed", SEMENA)
def test_splyvajuce_rady_nie_az_ked_sa_rozidu(seed):
    """Pri pokojnom tepe su oba rady rovnake (alebo o 1 BPM) - to nie je
    poplach. Az ked sa rozidu, appka to najde."""
    rng = random.Random(seed)
    hr = _tep(rng, 240)
    rad = []
    for i in range(120):                       # 2 minuty spolu
        rad.append((float(i), round(hr[i])))
        rad.append((i + 0.5, round(hr[i]) + rng.choice((-1, 0, 0, 1))))
    assert _prvy_poplach(rad) is None
    for i in range(120, 240):                  # nizsi rad o 8 BPM dole
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
        if rng.random() < 0.05:                 # obcas ujdena hodnota navyse
            rad.append((t + 0.3, bpm + rng.choice((-15, 15))))
    assert _prvy_poplach(rad) is None


@pytest.mark.parametrize("seed", SEMENA)
def test_davky_po_zaseknutej_wifi_nie(seed):
    """Po pripojeni pride 25 starych sprav naraz, potom kazdych 20 s davka
    12 sprav za sebou - stale jeden (sumny) rad."""
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
    # potom minuta jedneho radu - stare dvojice z okna vypadnu
    for i in range(70):
        vysledok = okno.pridaj(80, 30.0 + i)
    assert vysledok is False
    assert okno._vzorky[0][0] >= 99.0 - heart_rate.DVA_TEPY_OKNO_S
    for i in range(2000):
        okno.pridaj(80, 200.0 + i * 0.001)
    assert len(okno._vzorky) <= heart_rate.DVA_TEPY_MAX_VZORIEK


# --------------------------------------------------------------------------
# 2. prijimac: raz za beh, len pomenovany zdroj, tep ide dalej
# --------------------------------------------------------------------------

def test_raz_za_beh_a_len_pomenovany_zdroj():
    run = heart_rate._Run(1)
    hlasenia = [run.note_bpm("Tep", bpm, t) for t, bpm in _dva_rady(2, 8)]
    assert hlasenia.count(True) == 1
    # UDP / klient bez mena zdroja: nehlada sa
    run = heart_rate._Run(2)
    assert not any(run.note_bpm(None, bpm, t) for t, bpm in _dva_rady(2, 8))
    # sprava bez tepu (kroky) do okna nejde
    assert run.note_bpm("Kroky", None, 0.0) is False
    assert run.dva_tepy == {}


def test_kazdy_zdroj_ma_vlastne_okno_a_je_ich_obmedzene():
    """Vyssi rad do "Tep", nizsi do "HR": v kazdom zdroji jeden rad - to je
    v poriadku a poplach to nie je."""
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
        mon._emit(b"1045", run, "Kroky")         # kroky okno neovplyvnia
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
# 3. appka: dennik raz za beh, text pri prepinaci, prednost
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
    # nic z toho, co robi padnute spojenie
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
    """Upozornenie patri k tepu, ktory chodi. Bez dat hrac potrebuje vediet
    skutocny stav spojenia - ten ostava presne ako doteraz."""
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
    # tep je spat v tom istom behu - upozornenie tiez
    a._hr_state, a._hr_last_bpm = "connected", 75
    assert tr("settings.hr_status_two_series") in _stitok(a)[0]


def test_vypnutie_a_restart_upozornenie_zahodia():
    a = _atrapa()
    _stav(a, "two_series", "Tep")
    # vypnuty senzor (generacia 0)
    a._hr_generation, a._hr_state, a._hr_last_bpm = 0, "disconnected", None
    assert _stitok(a)[0] == tr("settings.hr_status_disconnected")
    # novy beh (zapnutie, restart, iny port) ma novu generaciu
    a._hr_generation, a._hr_state, a._hr_last_bpm = 6, "connected", 70
    assert _stitok(a)[0] == "❤️ 70 BPM"
    # a v novom behu sa smie nahlasit znova - raz
    _stav(a, "two_series", "Tep", gen=6)
    _stav(a, "two_series", "Tep", gen=6)
    assert len(a.denn) == 2


def test_stop_a_start_menia_generaciu():
    """Na tom stoji "zmizne po vypnuti / restarte" - priznak sa nikde rucne
    nenuluje, zahodi ho nova generacia behu."""
    assert "self._hr_generation = 0" in zdroj_metody("stop_heart_rate_monitor")
    assert ("self._hr_generation = self.heart_rate_monitor.start("
            in zdroj_metody("start_heart_rate_monitor"))
    assert "self.heart_rate_monitor.start(" in zdroj_metody("_retry_hr_bind")


# --------------------------------------------------------------------------
# 4. texty a dokumenty
# --------------------------------------------------------------------------

def test_texty_maju_vsetky_jazyky_a_su_kratke():
    for kluc in ("log.hr_two_series", "settings.hr_status_two_series"):
        for jazyk in i18n.LANGUAGES:
            assert i18n.tr_lang(jazyk, kluc).strip(), (kluc, jazyk)
        assert i18n.tr_lang("sk", kluc) != i18n.tr_lang("en", kluc)
    for jazyk in i18n.LANGUAGES:
        assert "{source}" in i18n.STRINGS["log.hr_two_series"][jazyk], jazyk
        # stitok stoji za cislom tepu - kratky
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
    # Audit 0.2.2d: nevydana 0.2.2 nepatri do navodu pre 0.2.1 - README ma
    # len riadok v Troubleshooting (stitok + co s tym), median je v
    # docs/HOW-IT-WORKS.md a cely bod v KNOWN_ISSUES.
    stitok = i18n.STRINGS["settings.hr_status_two_series"]["en"]
    readme = _plain("README.md")
    ako = _plain("docs/HOW-IT-WORKS.md")
    # Od 0.2.2 (davka 4) je bod o oprave v CHANGELOG.md, nie v KNOWN_ISSUES.
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
    # 0.2.2 este nevyslo - dokumenty to hovoria a verzia sa nezdvihla
    riadok = readme[readme.index("*%s*" % stitok):][:200]
    assert "(from 0.2.2)" in riadok
    assert "From 0.2.2" in ako
    with open(os.path.join(ROOT, "KNOWN_ISSUES.md"), encoding="utf-8-sig") as fh:
        k = fh.read()
    assert k.splitlines()[0].endswith("alpha 0.2.1")
    with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8-sig") as fh:
        c = fh.read()
    assert (c.index("## What 0.2.2 changes (not released yet)")
            < c.index("## What 0.2.1 fixes"))
