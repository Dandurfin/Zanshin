"""Export of the session history to a spreadsheet for Excel.

Two things it hinges on in Central Europe, and which break easily: the
semicolon as the separator and the decimal COMMA in numbers. Without them
Excel opens the file as a single column of text.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hr_stats


def _session(started, **kwargs):
    base = {
        "started": started, "duration_s": 3661.0, "min_bpm": 54, "avg_bpm": 72,
        "max_bpm": 131, "time_over_s": 125.0, "peak_stress": 83,
        "triggers": 5, "auto_triggers": 3, "baseline_bpm": 61,
        "hrr_bpm": 22, "hrpi": 104,
        "zone_seconds": {"calm": 1800.0, "raised": 900.0, "high": 600.0,
                         "critical": 361.0},
    }
    base.update(kwargs)
    return base


def _read(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return [r for r in fh.read().split("\r\n") if r]


def test_hlavicka_a_riadok(tmp_path):
    cesta = str(tmp_path / "relacie.csv")
    count = hr_stats.export_sessions_csv([_session(1_700_000_000)], cesta)
    assert count == 1
    riadky = _read(cesta)
    assert len(riadky) == 2
    assert riadky[0].split(";") == list(hr_stats.CSV_COLUMNS)
    bunky = riadky[1].split(";")
    assert len(bunky) == len(hr_stats.CSV_COLUMNS)


def test_desatinna_ciarka_nie_bodka(tmp_path):
    """Excel in SK/CZ reads "61.0" as text, "61,0" as a number."""
    cesta = str(tmp_path / "r.csv")
    hr_stats.export_sessions_csv([_session(1_700_000_000)], cesta)
    riadok = _read(cesta)[1]
    assert "61,0" in riadok or "61,03" in riadok      # length 3661 s = 61,0 min
    assert ".0" not in riadok


def test_subor_ma_bom(tmp_path):
    """Without a BOM Excel reads the file as ANSI and mangles diacritics."""
    cesta = str(tmp_path / "r.csv")
    hr_stats.export_sessions_csv([_session(1_700_000_000)], cesta,
                                 headers=["Dátum"] + list(hr_stats.CSV_COLUMNS[1:]))
    with open(cesta, "rb") as fh:
        assert fh.read(3) == b"\xef\xbb\xbf"


def test_relacie_su_chronologicky(tmp_path):
    cesta = str(tmp_path / "r.csv")
    hr_stats.export_sessions_csv(
        [_session(1_700_200_000), _session(1_700_000_000)], cesta)
    riadky = _read(cesta)[1:]
    assert riadky[0] < riadky[1] or riadky[0] != riadky[1]
    assert len(riadky) == 2


def test_prazdna_historia_da_len_hlavicku(tmp_path):
    cesta = str(tmp_path / "r.csv")
    assert hr_stats.export_sessions_csv([], cesta) == 0
    assert len(_read(cesta)) == 1


def test_chybajuce_polia_nezhodia_export(tmp_path):
    """Sessions from older versions lack some fields - the column stays empty."""
    cesta = str(tmp_path / "r.csv")
    hr_stats.export_sessions_csv([{"started": 1_700_000_000}], cesta)
    bunky = _read(cesta)[1].split(";")
    assert bunky[0]                      # the date is there
    assert bunky[3] == ""                # average heart rate missing


def test_prelozene_nazvy_stlpcov(tmp_path):
    cesta = str(tmp_path / "r.csv")
    hlavicky = [f"stlpec{i}" for i in range(len(hr_stats.CSV_COLUMNS))]
    hr_stats.export_sessions_csv([_session(1_700_000_000)], cesta, headers=hlavicky)
    assert _read(cesta)[0].split(";") == hlavicky


def _falosna_instancia():
    """A dialog instance WITHOUT `__init__` — so no Tk and no window.

    The helpers that `__init__` calls do not touch `self`, so they can be
    tried exactly the way the real code calls them: through an instance.
    """
    import ui_dialogs
    trieda = ui_dialogs.SessionEndDialog
    return trieda.__new__(trieda)


def test_dotaznik_vie_naformatovat_cas_bez_instancie():
    """`_cas` without `@staticmethod` crashed the questionnaire on line one.

    `self._cas(minuty)` passed two arguments to a function taking one. It
    was the second reason why History has 13 sessions and not one with
    context — the first was that the dialog was thrown away on app close
    before it managed to render.
    """
    import ui_dialogs
    assert ui_dialogs.SessionEndDialog._cas(30)
    assert ui_dialogs.SessionEndDialog._cas(90)


def test_pomocnikov_dotaznika_sa_da_volat_TAK_AKO_ICH_VOLA_DIALOG():
    """This is the test that should have been there — and was not.

    `SessionEndDialog._cas(30)` on the CLASS passes even without
    `@staticmethod`: the unbound function gets `minuty=30` and returns the
    correct result. So the test was green exactly when the questionnaire
    was broken — the error only arises with `self._cas(...)`, where `self`
    takes the first argument.

    The journal confirms it: on 17. 9. and 19. 9., seven `TypeError` in
    total and not a single red test. That is why it is called through an
    instance here.
    """
    d = _falosna_instancia()
    assert d._cas(30)
    # 0.3 batch 4: readable length from 1 h on ("1 h 30 min"), not "1:30"
    import i18n
    assert d._cas(90) == i18n.tr("dashboard.fmt.h_min", h=1, m="30")
    assert isinstance(d._preco_ticho({}), str)


def test_preco_ticho_znesie_aj_suhrn_zo_starsej_verzie():
    """Old sessions lack progress fields — the dialog must not choke on them."""
    d = _falosna_instancia()
    for suhrn in ({}, {"above_runs": None}, {"runs_cancelled_gap": 3},
                  {"above_runs": 0, "longest_above_s": None,
                   "stress_hold_s": None}):
        assert isinstance(d._preco_ticho(suhrn), str), suhrn
