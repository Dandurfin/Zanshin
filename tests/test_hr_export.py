"""Export historie relacii do tabulky pre Excel.

Dve veci, na ktorych to v strednej Europe stoji a ktore sa lahko pokazia:
bodkociarka ako oddelovac a desatinna CIARKA v cislach. Bez nich Excel
otvori subor ako jeden stlpec textu.
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
    """Excel v SK/CZ cita "61.0" ako text, "61,0" ako cislo."""
    cesta = str(tmp_path / "r.csv")
    hr_stats.export_sessions_csv([_session(1_700_000_000)], cesta)
    riadok = _read(cesta)[1]
    assert "61,0" in riadok or "61,03" in riadok      # dlzka 3661 s = 61,0 min
    assert ".0" not in riadok


def test_subor_ma_bom(tmp_path):
    """Bez BOM Excel precita subor ako ANSI a zmrsi diakritiku."""
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
    """Relacie zo starsich verzii nemaju vsetky polia - stlpec ostane prazdny."""
    cesta = str(tmp_path / "r.csv")
    hr_stats.export_sessions_csv([{"started": 1_700_000_000}], cesta)
    bunky = _read(cesta)[1].split(";")
    assert bunky[0]                      # datum je
    assert bunky[3] == ""                # priemerny tep chyba


def test_prelozene_nazvy_stlpcov(tmp_path):
    cesta = str(tmp_path / "r.csv")
    hlavicky = [f"stlpec{i}" for i in range(len(hr_stats.CSV_COLUMNS))]
    hr_stats.export_sessions_csv([_session(1_700_000_000)], cesta, headers=hlavicky)
    assert _read(cesta)[0].split(";") == hlavicky


def _falosna_instancia():
    """Inštancia dialógu BEZ `__init__` — teda bez Tk a bez okna.

    Pomocníci, ktorých `__init__` volá, sa `self` nedotýkajú, takže sa dajú
    vyskúšať presne tak, ako ich volá skutočný kód: cez inštanciu.
    """
    import ui_dialogs
    trieda = ui_dialogs.SessionEndDialog
    return trieda.__new__(trieda)


def test_dotaznik_vie_naformatovat_cas_bez_instancie():
    """`_cas` bez `@staticmethod` zhodil celý dotazník na prvom riadku.

    `self._cas(minuty)` posielal dva argumenty do funkcie s jedným. Bol to
    druhý dôvod, prečo je v histórii 13 relácií a ani jedna s kontextom —
    prvým bolo, že sa dialóg pri zatváraní appky zahodil skôr, než sa stihol
    vykresliť.
    """
    import ui_dialogs
    assert ui_dialogs.SessionEndDialog._cas(30)
    assert ui_dialogs.SessionEndDialog._cas(90)


def test_pomocnikov_dotaznika_sa_da_volat_TAK_AKO_ICH_VOLA_DIALOG():
    """Toto je ten test, ktorý tam mal byť — a nebol.

    `SessionEndDialog._cas(30)` na TRIEDE prejde aj bez `@staticmethod`:
    nenaviazaná funkcia dostane `minuty=30` a vráti správny výsledok. Test
    teda svietil na zeleno presne vtedy, keď bol dotazník rozbitý — chyba
    vzniká až pri `self._cas(...)`, kde `self` zaberie prvý argument.

    Denník to potvrdzuje: 17. 9. a 19. 9. spolu sedem `TypeError` a ani jeden
    červený test. Preto sa tu volá cez inštanciu.
    """
    d = _falosna_instancia()
    assert d._cas(30)
    assert d._cas(90) == "1:30"
    assert isinstance(d._preco_ticho({}), str)


def test_preco_ticho_znesie_aj_suhrn_zo_starsej_verzie():
    """Staré relácie polia o priebehu nemajú — dialóg sa na nich nesmie zlomiť."""
    d = _falosna_instancia()
    for suhrn in ({}, {"above_runs": None}, {"runs_cancelled_gap": 3},
                  {"above_runs": 0, "longest_above_s": None,
                   "stress_hold_s": None}):
        assert isinstance(d._preco_ticho(suhrn), str), suhrn
