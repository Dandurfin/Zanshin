# -*- coding: utf-8 -*-
"""Dva svety, jedno telo (0.2, B3-worlds).

Hra a praca maju oddelenu historiu, postrehy aj vzhlad (Sumi / Aizome).
Rozhodnutia zadavatela, ktore tieto testy strazia:

  (a) v PRACI ide hlaska len obrazom - bez hlasu a bez zvuku,
  (b) kriticky tep a prah zataze sa rataju LEN z hernych relacii;
      dlhodoba pokojova zakladna ostava zo vsetkych (telo je jedno),
  (c) svet relacie sa pecati pri jej OTVORENI (`world`); prepinac uprostred
      relacie ju neprestitkuje a `activity` je dalej len odpoved hraca,
  (d) Hra = Sumi, Praca = Aizome; stara tema bez sveta -> Hra.

Vacsina testov bezi bez Tk - skutocne metody `DandurfApp` na malej atrape
(rovnako ako test_widgets_history.py). Jediny Tk test (lista) sa preskoci,
ked sa okno vytvorit neda.
"""
import json
import os
import random
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import hr_insights  # noqa: E402
import hr_stats  # noqa: E402
import i18n  # noqa: E402
import theme  # noqa: E402
import trigger  # noqa: E402


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8-sig") as fh:
        return fh.read()


def _metoda(src, nazov):
    """Telo jednej metody `DandurfApp` ako text (po dalsiu `def`)."""
    start = src.index(f"    def {nazov}(")
    koniec = src.find("\n    def ", start + 1)
    return src[start:koniec if koniec > 0 else len(src)]


def _app():
    import app as app_mod
    return app_mod.DandurfApp


@pytest.fixture
def sk():
    povodny = i18n._lang["code"]
    i18n.set_lang("sk")
    yield
    i18n.set_lang(povodny)


# --------------------------------------------------------------------------
# Do ktoreho sveta relacia patri
# --------------------------------------------------------------------------

def test_svet_relacie_odpoved_hraca_vyhrava_nad_pecatou():
    assert hr_stats.session_world({"world": "work"}) == "work"
    assert hr_stats.session_world({"world": "play"}) == "play"
    # Hrac v dotazniku povedal inak nez prepinac -> plati jeho slovo.
    assert hr_stats.session_world({"world": "work", "activity": "play"}) == "play"
    assert hr_stats.session_world({"world": "play", "activity": "work"}) == "work"


def test_relacia_bez_stitku_patri_hre_pevnym_pravidlom():
    """Stare relacie (bez `world`, preskoceny dotaznik) idu natrvalo do Hry -
    nie podla "hlavneho sveta", inak by sa pri jeho zmene presuvali."""
    for zla in ({}, {"activity": None}, {"world": None}, {"activity": 5},
                {"world": "x"}, {"activity": ["work"]}, {"world": {"a": 1}}):
        assert hr_stats.session_world(zla) == "play", zla
    assert hr_stats.session_world(None) == "play"
    assert hr_stats.session_world("work") == "play"


def test_relacie_sveta_rozdeli_zoznam_a_zahodi_nezmysly():
    hra = {"started": 1.0}
    praca = {"started": 2.0, "world": "work"}
    oprava = {"started": 3.0, "world": "work", "activity": "play"}
    vsetko = [hra, praca, "nezmysel", None, oprava]
    assert hr_stats.sessions_in_world(vsetko, "play") == [hra, oprava]
    assert hr_stats.sessions_in_world(vsetko, "work") == [praca]
    # neznamy svet = Hra, rovnako ako pri relacii
    assert hr_stats.sessions_in_world(vsetko, "nieco") == [hra, oprava]
    assert hr_stats.sessions_in_world(None, "play") == []


def test_tema_patri_svetu():
    assert theme.WORLD_THEME == {"play": theme.ZEN, "work": theme.MODERN}
    assert theme.theme_world(theme.ZEN) == "play"
    assert theme.theme_world(theme.MODERN) == "work"
    assert theme.theme_world("nieco") == "play"
    # kluce svetov su tie iste ako v datach relacie
    assert set(theme.WORLD_THEME) == set(hr_stats.ACTIVITY_KINDS)
    assert hr_stats.WORLD_DEFAULT == "play"


# --------------------------------------------------------------------------
# (b) Algoritmus: zakladna spolocna, kriticky tep a prah len z hry
# --------------------------------------------------------------------------

def _hracia(zaklad, started, n=400, world=None, baseline=70):
    rng = random.Random(int(started))
    s = {"started": float(started), "duration_s": 3600.0, "baseline_bpm": baseline,
         "max_bpm": zaklad + 25,
         "curve": [int(zaklad + rng.uniform(-8, 20)) for _ in range(n)]}
    if world:
        s["world"] = world
    return s


def test_pracovna_relacia_neposunie_kriticky_tep_hry():
    hra = [_hracia(85, 1000 + i) for i in range(4)]
    # Pracovne relacie tu maju nizsi pokoj - zakladna zo vsetkeho to ma vidiet.
    praca = [_hracia(125, 2000 + i, world="work", baseline=62) for i in range(3)]
    vsetko = hra + praca
    herna = hr_stats.sessions_in_world(vsetko, "play")
    assert herna == hra
    assert hr_stats.dynamicky_kriticky(herna) == hr_stats.dynamicky_kriticky(hra)
    # Predpoklad testu: zmiesane by to naozaj posunulo (inak by nic nemeral).
    assert hr_stats.dynamicky_kriticky(vsetko) > hr_stats.dynamicky_kriticky(hra)
    # Zakladna ide zo vsetkeho - telo je jedno - a praca ju tu posunie.
    assert hr_stats.dlhodoba_zakladna(vsetko) < hr_stats.dlhodoba_zakladna(hra)


def test_otvorenie_relacie_rata_kriticky_a_prah_z_hry_zakladnu_zo_vsetkeho():
    D = _app()
    assert D.ALGORITMUS_SVET == "play"
    telo = _metoda(_read("app.py"), "_open_hr_session")
    assert "hr_stats.dlhodoba_zakladna(historia)" in telo, "zakladna ma byt zo vsetkeho"
    assert "herna = hr_stats.sessions_in_world(historia, self.ALGORITMUS_SVET)" in telo
    assert "hr_stats.dynamicky_kriticky(\n                herna," in telo
    assert "hr_stats.dynamicky_prah_zataze(\n                herna," in telo
    assert "hr_stats.ciste_relacie(herna)" in telo, "pocet do vety o prahu"
    # tiche rameno (kalibracia) ostava zo vsetkych svetov - len bez
    # importovanych relacii (cudzie telo neposuva fazu 1/4 -> 1/10)
    assert "len(data_io.vlastne(self._history_sessions()))" in _metoda(
        _read("app.py"), "_silent_share_for_next_session")


def test_veta_o_hranici_pocita_len_herne_relacie(sk):
    D = _app()
    hra = [_hracia(85, 1000 + i) for i in range(2)]
    praca = [_hracia(125, 2000 + i, world="work") for i in range(3)]
    a = types.SimpleNamespace(hr_critical_bpm=110, ALGORITMUS_SVET="play",
                              _history_sessions=lambda: hra + praca)
    veta = D._kriticky_popis(a)
    # 2 herne z 3 potrebnych -> este 1; pracovne sa nerataju
    assert veta == i18n.tr("settings.hr_critical_learning", bpm=110, treba=1)
    assert "herných" in veta


# --------------------------------------------------------------------------
# (a) Praca = len obraz
# --------------------------------------------------------------------------

def _doruc(voice):
    class Hodiny:
        t = 1000.0

        def __call__(self):
            return self.t
    h = Hodiny()
    t = trigger.CueTrigger(rng=random.Random(1), clock=h)
    t.open_session(silent_share=0.0, voice=voice)   # vzdy hlasne rameno
    for _ in range(400):
        ev = t.note_load(80.0, h.t, zona="high")   # brana (0.2) pusti
        h.t += 1.0
        if ev and ev["typ"] == trigger.E_ARMED:
            h.t += 5.0
            return t.tick(pause_s=3.0, now=h.t)
    raise AssertionError("nedorucilo sa")


def test_v_praci_hlaska_nema_hlas_ani_pri_pauze():
    hra = _doruc(voice=True)
    praca = _doruc(voice=False)
    assert hra["typ"] == praca["typ"] == trigger.E_DELIVER
    assert hra["arm"] == praca["arm"] == trigger.ARM_VOICE
    assert hra["delivery"] == praca["delivery"] == trigger.D_PAUSE
    assert hra["hlas"] is True
    assert praca["hlas"] is False, "v praci hlaska nesmie zaznet"


def test_hlas_sa_urcuje_pri_otvoreni_a_plati_celu_relaciu():
    t = trigger.CueTrigger()
    assert t.voice is True, "bez sveta sa sprava ako doteraz"
    t.open_session(voice=False)
    assert t.voice is False
    t.open_session()
    assert t.voice is True
    telo = _metoda(_read("app.py"), "_open_hr_session")
    assert 'voice=self._session_world != "work"' in telo


# --------------------------------------------------------------------------
# (c) Svet sa pecati pri otvoreni, `activity` ostava odpovedou hraca
# --------------------------------------------------------------------------

def test_svet_sa_pecati_pri_otvoreni_a_uklada_pri_zatvoreni():
    src = _read("app.py")
    otvor = _metoda(src, "_open_hr_session")
    assert "self._session_world = self.world" in otvor
    # pecat musi byt az PO zatvoreni predoslej relacie
    assert otvor.index("self._close_hr_session()") < otvor.index(
        "self._session_world = self.world")
    zatvor = _metoda(src, "_close_hr_session")
    assert 'summary["world"] = getattr(self, "_session_world"' in zatvor
    assert zatvor.index('summary["world"]') < zatvor.index("hr_stats.save_session(")
    assert 'summary["activity"]' not in zatvor, "stroj nesmie pisat odpoved hraca"
    # meracie okna nesu svet priamo
    assert 'w["world"] = svet' in _metoda(src, "_save_measure_windows")


def _suhrn(**kw):
    s = {"started": 1_700_000_000.5, "duration_s": 600.0, "samples": 400,
         "world": "work"}
    s.update(kw)
    return s


def test_dotaznik_bez_kliku_necha_pecat_a_klik_ju_prebije(tmp_path):
    cesta = str(tmp_path / "hr_sessions.json")
    assert hr_stats.save_session(cesta, _suhrn())
    # Ulozit bez kliku na hral/pracoval: `activity` ostava prazdne.
    assert hr_stats.attach_context(cesta, 1_700_000_000.5, ["call"], activity=None)
    ulozena = hr_stats.load_sessions(cesta)[0]
    assert "activity" not in ulozena
    assert ulozena["world"] == "work"
    assert hr_stats.session_world(ulozena) == "work"
    # Hrac klikol "Hral som" -> odpoved sa ulozi, pecat ostava (provenancia).
    assert hr_stats.attach_context(cesta, 1_700_000_000.5, [], activity="play")
    ulozena = hr_stats.load_sessions(cesta)[0]
    assert ulozena["activity"] == "play"
    assert ulozena["world"] == "work"
    assert hr_stats.session_world(ulozena) == "play"


def test_dotaznik_zvyrazni_svet_ale_neulozi_ho_bez_kliku():
    ud = _read("ui_dialogs.py")
    trieda = ud[ud.index("class SessionEndDialog"):ud.index("class OnboardingWizard")]
    assert "self.activity = None" in trieda
    assert "self._svet = hr_stats.session_world(summary)" in trieda
    assert "self._paint_activity(self._svet)" in trieda
    # klik je odpoved; `confirm` posiela len `self.activity`
    assert "self.activity = kind" in trieda
    assert "activity=self.activity" in trieda
    # pracovna relacia nema v titulku "Hral si" ani vetu o tichom ramene
    assert '"session.end.title_work" if self._svet == "work"' in trieda
    assert 'tr("session.end.cues_work", n=cues)' in trieda


def test_oprava_sveta_v_dotazniku_prepocita_postrehy():
    telo = _metoda(_read("app.py"), "save_session_context")
    assert "zmena_sveta" in telo
    assert "self.history_detail_index = None" in telo
    assert "self.run_hr_analysis()" in telo


# --------------------------------------------------------------------------
# Prepnutie sveta
# --------------------------------------------------------------------------

class _Seg:
    def __init__(self):
        self.value = None

    def set(self, v):
        self.value = v


def _atrapa_sveta(svet="play"):
    D = _app()
    a = types.SimpleNamespace(
        world=svet, _session_world=svet,
        theme_key=theme.WORLD_THEME[svet],
        history_detail_index=3, _hr_insights=[{"key": "steady"}],
        _hr_insights_at=123.0, world_switch=_Seg(), volania=[])
    a.titlebar = types.SimpleNamespace(set_world=lambda lab: a.volania.append(("lista", lab)))

    def tema(label):
        a.volania.append(("tema", label))
        a.theme_key = (theme.ZEN if label == i18n.tr("theme.zen.label")
                       else theme.MODERN)
        a.volania.append(("ulozene", a.world))
    a.on_theme_switch = tema
    a.save_settings = lambda: a.volania.append(("ulozene", a.world))
    a._refresh_history_page = lambda: a.volania.append(("historia",))
    a._refresh_dnes_stats = lambda: a.volania.append(("dnes",))
    a.run_hr_analysis = lambda *_: a.volania.append(("analyza",))
    # v Praci hlaska nehovori - priprava Edge hlasok sa prepocita
    a.schedule_pregenerate = lambda *_: a.volania.append(("pregen", a.world))
    a._build_ui = lambda: a.volania.append(("PRESTAVBA",))
    a._world_label = D._world_label
    a._sync_world_switches = types.MethodType(D._sync_world_switches, a)
    a.set_world = types.MethodType(D.set_world, a)
    return a


def test_prepnutie_sveta_zmeni_vzhlad_pohlady_a_postrehy(sk):
    a = _atrapa_sveta("play")
    a.set_world("work")
    assert a.world == "work"
    assert a.theme_key == theme.MODERN
    assert ("tema", i18n.tr("theme.modern.label")) in a.volania
    assert ("ulozene", "work") in a.volania, "svet sa musi ulozit"
    assert a.history_detail_index is None, "detail je index do zoznamu sveta"
    assert a._hr_insights == [] and a._hr_insights_at is None
    assert ("historia",) in a.volania and ("analyza",) in a.volania
    assert ("lista", "Práca") in a.volania
    assert a.world_switch.value == "Práca"
    assert ("pregen", "work") in a.volania, "priprava hlasok ide za svetom"
    assert ("PRESTAVBA",) not in a.volania, "prepnutie nesmie stavat okno znova"


def test_prepnutie_sveta_neprestitkuje_beziacu_relaciu(sk):
    a = _atrapa_sveta("play")
    a.set_world("work")
    assert a._session_world == "play", "hra ostava hrou aj po pozreti Prace"


def test_ten_isty_svet_nic_neprekresluje(sk):
    a = _atrapa_sveta("work")
    a.set_world("work")
    assert not [v for v in a.volania if v[0] in ("tema", "analyza", "historia")]
    assert a.world_switch.value == "Práca"
    # nezmysel = Hra
    a.set_world("nieco")
    assert a.world == "play"


def test_oba_prepinace_volaju_set_world_a_tema_uz_nie_je_volba():
    src = _read("app.py")
    assert "on_world=self._on_world_label" in src, "lista hore"
    assert "command=self._on_world_label" in src, "Nastavenia"
    assert "self.theme_switch" not in src, "samostatny vyber temy by rozbil svet"
    assert "command=self.on_theme_switch" not in src
    assert "self._sync_world_switches()" in _metoda(src, "_recolor_ui")
    shell = _read("ui_shell.py")
    lista = shell[shell.index("class TitleBar"):shell.index("def enable_frameless")]
    assert "self.world_switch = ctk.CTkSegmentedButton(" in lista
    assert "def set_world(self, label)" in lista
    # bublina na segmentoch (CTkSegmentedButton.bind nevie)
    assert "_HoverTip(segment, lambda: world_tip, below=True)" in lista


def test_harness_prepina_svet_nie_temu():
    for subor in ("gui_harness_auto.py", "gui_screenshots.py"):
        src = _read(subor)
        assert "on_theme_switch(" not in src, subor
        assert "app.set_world(" in src, subor


# --------------------------------------------------------------------------
# Pohlady filtrovane svetom, export a algoritmus nie
# --------------------------------------------------------------------------

def test_pohlady_citaju_svet_export_vsetko():
    src = _read("app.py")
    assert "sessions = self._world_sessions()" in _metoda(src, "_refresh_history_trend")
    assert "sessions = self._world_sessions()" in _metoda(src, "_refresh_history_page")
    karty = _metoda(src, "_dashboard_stat_value")
    assert karty.count("hr_stats.sessions_in_world(self._history_cached(), self.world)") == 2
    assert "sessions = self._history_sessions()" in _metoda(src, "export_sessions_csv")
    assert "self._history_sessions()," in _metoda(src, "export_all_json")


def test_karta_tyzdna_rata_len_svoj_svet(sk):
    import time as _t
    D = _app()
    teraz = _t.time()
    hra = {"started": teraz - 60, "duration_s": 1800.0}
    praca = {"started": teraz - 30, "duration_s": 3600.0, "world": "work"}
    a = types.SimpleNamespace(hr_stats=hr_stats.HeartStats(critical_bpm=110),
                              _hr_session_open=False, world="play",
                              _history_cached=lambda: [hra, praca])
    assert D._dashboard_stat_value(a, "week")[0] == "1"
    a.world = "work"
    assert D._dashboard_stat_value(a, "week") == ("1", "1h 0m")


# --------------------------------------------------------------------------
# Postrehy za jeden svet + opakovanie po prepnuti
# --------------------------------------------------------------------------

def test_postrehy_si_pamataju_svet(tmp_path):
    cesta = str(tmp_path / "hr_insights.json")
    assert hr_insights.save_insights(cesta, [{"key": "steady"}], world="work")
    ulozene = hr_insights.load_insights(cesta)
    assert ulozene["world"] == "work"
    assert ulozene["insights"] == [{"key": "steady"}]
    assert hr_insights.load_insights(str(tmp_path / "nie.json"))["world"] is None
    # bez sveta (stary tvar) -> kluc chyba, load da None
    assert hr_insights.save_insights(cesta, [])
    with open(cesta, encoding="utf-8") as fh:
        assert "world" not in json.load(fh)


def test_pri_starte_sa_postrehy_ineho_sveta_neukazu():
    src = _read("app.py")
    assert 'if _stored.get("world") != self.world:' in src
    assert src.index("self.world = settings[\"world\"]") < src.index(
        'if _stored.get("world") != self.world:')


class _Vlakno:
    def __init__(self, zive):
        self.zive = zive

    def is_alive(self):
        return self.zive


class _Root:
    def __init__(self):
        self.naplanovane = []

    def after(self, ms, fn):
        self.naplanovane.append(fn)
        return len(self.naplanovane)


def _atrapa_analyzy(svet="play", zive=False):
    D = _app()
    a = types.SimpleNamespace(world=svet, _hr_insights=[], _hr_insights_at=None,
                              _hr_analysis_rerun=False, _hr_rerun_job=None,
                              _hr_analysis_thread=_Vlakno(zive), root=_Root(),
                              spustene=[])
    a._render_hr_insights = lambda: None
    for meno in ("_apply_hr_insights", "_po_analyze", "_naplanuj_analyzu"):
        setattr(a, meno, types.MethodType(getattr(D, meno), a))
    a.run_hr_analysis = lambda *_: a.spustene.append(a.world)
    return a, D


def test_vysledok_za_iny_svet_sa_zahodi_a_prepocita():
    a, _D = _atrapa_analyzy("work")
    a._apply_hr_insights([{"key": "steady"}], "play")
    assert a._hr_insights == [], "postrehy hry sa nesmu ukazat v Praci"
    assert a.spustene == ["work"]


def test_vysledok_za_spravny_svet_sa_ukaze():
    a, _D = _atrapa_analyzy("play")
    a._apply_hr_insights([{"key": "steady"}], "play")
    assert a._hr_insights == [{"key": "steady"}]
    assert a._hr_insights_at is not None
    assert a.spustene == []


def test_odmietnuta_analyza_sa_nestrati():
    """Prepnutie sveta pocas bezucej analyzy: nova sa odmietne (vlakno zije),
    ale zapise sa - a spusti sa, az ked vlakno naozaj dobehne."""
    a, D = _atrapa_analyzy("play", zive=True)
    D.run_hr_analysis(a)                       # vlakno zije -> odmietnute
    assert a._hr_analysis_rerun is True
    # vysledok stareho behu pride este ZVNUTRA vlakna (ui_call) - zije
    a._apply_hr_insights([{"key": "steady"}], "play")
    assert a.spustene == [], "kym vlakno zije, nova analyza by sa odmietla"
    assert len(a.root.naplanovane) == 1
    # druha poziadavka nenaplanuje druhe cakanie
    a._naplanuj_analyzu()
    assert len(a.root.naplanovane) == 1
    a._hr_analysis_thread.zive = False
    a.root.naplanovane[0]()
    assert a.spustene == ["play"]
    assert a._hr_analysis_rerun is False


def test_analyza_rata_len_svoj_svet_a_uklada_ho():
    telo = _metoda(_read("app.py"), "run_hr_analysis")
    assert "world = self.world" in telo
    assert "hr_stats.sessions_in_world(\n                    hr_stats.load_sessions(sessions_path), world)" in telo
    assert "world=world)" in telo
    assert "self._apply_hr_insights(insights, world)" in telo


# --------------------------------------------------------------------------
# (d) Nastavenia: svet, migracia, tema ide za svetom
# --------------------------------------------------------------------------

@pytest.fixture
def nastavenia(tmp_path, monkeypatch):
    import app as app_mod
    cesta = str(tmp_path / "dandurf_settings.json")
    monkeypatch.setattr(app_mod, "SETTINGS_PATH", cesta)
    povodny = i18n._lang["code"]

    def nacitaj(obsah=None):
        if obsah is not None:
            with open(cesta, "w", encoding="utf-8") as fh:
                json.dump(obsah, fh)
        return app_mod.DandurfApp.load_settings(types.SimpleNamespace())
    yield nacitaj
    i18n.set_lang(povodny)


def test_prvy_start_je_v_hre(nastavenia):
    d = nastavenia()
    assert d["first_run"] is True
    assert d["world"] == "play" and d["theme"] == theme.ZEN


def test_migracia_aizome_bez_sveta_ide_do_hry(nastavenia):
    """Stary hrac s Aizome: svet sa z temy NEODVODZUJE (hranie by sa mu
    zacalo ratat ako praca) - ide do Hry a tema ide za svetom."""
    d = nastavenia({"lang": "sk", "theme": "modern"})
    assert d["world"] == "play"
    assert d["theme"] == theme.ZEN
    assert d["first_run"] is False, "tema je dalej znacka 'prvy start bol'"


def test_ulozeny_svet_urci_temu(nastavenia):
    d = nastavenia({"lang": "sk", "theme": "zen", "world": "work"})
    assert (d["world"], d["theme"], d["first_run"]) == ("work", theme.MODERN, False)
    d = nastavenia({"lang": "sk", "theme": "modern", "world": "nezmysel"})
    assert (d["world"], d["theme"]) == ("play", theme.ZEN)


def test_svet_sa_uklada_aj_s_temou():
    telo = _metoda(_read("app.py"), "save_settings")
    assert '"world": getattr(self, "world", hr_stats.WORLD_DEFAULT)' in telo
    assert '"theme": self.theme_key' in telo


# --------------------------------------------------------------------------
# Onboarding: krok 4 vybera hlavny svet
# --------------------------------------------------------------------------

def test_onboarding_vybera_hlavny_svet():
    ud = _read("ui_dialogs.py")
    krok = ud[ud.index("    def _step4("):ud.index("    def _on_volume_slide(")]
    assert 'theme_mod.WORLD_THEME["play"],\n                   tr("ob.world.play.title")' in krok
    assert 'theme_mod.WORLD_THEME["work"],\n                   tr("ob.world.work.title")' in krok
    src = _read("app.py")
    assert src.count("theme_mod.theme_world(wizard.choice)") == 2, \
        "prvy start aj opakovany onboarding"
    # test zvuku hra vzdy zvuky hry - v praci zvuk nie je
    assert 'pack = theme_mod.WORLD_THEME["play"]' in ud


# --------------------------------------------------------------------------
# Texty
# --------------------------------------------------------------------------

NOVE_KLUCE = ("world.play", "world.work", "world.tip", "settings.world",
              "settings.world_sub", "history.world_note", "ob.step4.title",
              "ob.step4.body", "ob.world.play.title", "ob.world.play.desc",
              "ob.world.work.title", "ob.world.work.desc",
              "session.end.title_work", "session.end.cues_work",
              "settings.hr_critical_computed", "settings.hr_critical_learning",
              "cue_rate.computed", "cue_rate.learning", "history.insights_note")


def _jeden_tr7(src, kluc):
    """Najviac jeden `_tr7` riadok na kluc - stary preklad nemoze potichu
    prezit pod novym (jazykova faza 0.2 pisala preklady z noveho SK)."""
    return src.count(f"_tr7('{kluc}'") <= 1


def test_nove_texty_maju_vsetkych_jedenast_jazykov():
    for kluc in NOVE_KLUCE:
        assert set(i18n.STRINGS[kluc]) == set(i18n.LANGUAGES), kluc
        # zmenene znenie preložila jazyková fáza 0.2 - vlastný text v ja
        assert i18n.STRINGS[kluc]["ja"] != i18n.STRINGS[kluc]["en"], kluc


def test_svet_hry_nesluboval_hlas_pri_kazdej_hlaske():
    """Asi desatina hlášok naschvál mlčí a hláška bez pauzy je len obrazom -
    „s hlasom aj obrazom" sľubovalo viac, než appka robí."""
    zaznam = i18n.STRINGS["ob.world.play.desc"]
    assert "väčšinou s hlasom" in zaznam["sk"]
    assert "mostly with voice" in zaznam["en"]
    assert "hlasom aj obrazom" not in zaznam["sk"]
    assert "voice and visual" not in zaznam["en"]


def test_stare_znenia_zmizli_zo_vsetkych_jazykov():
    src = _read("i18n.py")
    assert "skús obe" not in src and "try both" not in src
    assert "'settings.theme_sub'" not in src and "'settings.theme'" not in src
    assert "Vyber vzhľad a vstúp" not in src
    assert _jeden_tr7(src, "ob.step4.title") and _jeden_tr7(src, "ob.step4.body")
    # hranica a prah hovoria o hernych relaciach
    for kluc in ("settings.hr_critical_computed", "settings.hr_critical_learning",
                 "cue_rate.computed", "cue_rate.learning"):
        assert "herných" in i18n.STRINGS[kluc]["sk"], kluc
        assert "play sessions" in i18n.STRINGS[kluc]["en"], kluc
    # postrehy sa rataju zo sveta, nie "z celej historie" (v ziadnom jazyku)
    assert _jeden_tr7(src, "history.insights_note")
    assert "celej histórie" not in i18n.STRINGS["history.insights_note"]["sk"]
    assert "tohto sveta" in i18n.STRINGS["history.insights_note"]["sk"]
    assert "whole history" not in i18n.STRINGS["history.insights_note"]["en"]


def test_historia_priznava_spolocny_graf_hlasok(sk):
    """Stranka s napisom "Svet: Praca" nesmie mlcky ukazovat herne hlasky:
    graf "Ktora hlaska zabera" rata od rebrika hlasky (0.2) len hlasky z hry,
    ktore zazneli (v praci je hlaska len obrazom) - veta to povie."""
    veta = i18n.tr("history.world_note", world=i18n.tr("world.work"),
                   chart=i18n.tr("history.effect_title"))
    assert i18n.tr("history.effect_title") in veta
    assert "len hlášky z hry" in veta
    assert "oboch svetov" not in veta
    assert "both worlds" not in i18n.STRINGS["history.world_note"]["en"]
    for jazyk in i18n.LANGUAGES:
        assert "{chart}" in i18n.STRINGS["history.world_note"][jazyk], jazyk
    telo = _metoda(_read("app.py"), "_refresh_history_page")
    assert 'chart=tr("history.effect_title")' in telo


def test_karty_filtrovane_svetom_to_hovoria():
    """Karty "Relacie tento tyzden" a "Citene a merane" ratuju len aktualny
    svet (integracia B3-worlds x widgets-history). Ich vysvetlenie to musi
    povedat a stare znenie ("odohral", "posledna relacia" bez sveta) nesmie
    prezit v ziadnom jazyku."""
    src = _read("i18n.py")
    for kluc in ("metric.week.short", "metric.week.more"):
        assert _jeden_tr7(src, kluc), kluc
        assert i18n.STRINGS[kluc]["ja"] != i18n.STRINGS[kluc]["en"], kluc
    assert "odohral" not in i18n.STRINGS["metric.week.short"]["sk"]
    assert "v tomto svete" in i18n.STRINGS["metric.week.short"]["sk"]
    assert "Hra alebo Práca" in i18n.STRINGS["metric.week.more"]["sk"]
    assert "tohto sveta" in i18n.STRINGS["metric.felt_vs_measured.more"]["sk"]
    assert "this world" in i18n.STRINGS["metric.felt_vs_measured.more"]["en"]
    # a kod naozaj filtruje - inak by veta klamala opacnym smerom
    telo = _metoda(_read("app.py"), "_dashboard_stat_value")
    assert telo.count("sessions_in_world(") >= 2


def test_texty_o_praci_hovoria_pravdu():
    """V praci hlaska nema hlas ani zvuk - kazde miesto, ktore svet opisuje,
    to musi povedat (a nic nesluboval navyse)."""
    for kluc in ("world.tip", "settings.world_sub", "ob.world.work.desc",
                 "session.end.cues_work"):
        sk = i18n.STRINGS[kluc]["sk"]
        assert "obrazom" in sk, kluc
    assert "Práca" == i18n.STRINGS["world.work"]["sk"]
    assert "Hra" == i18n.STRINGS["world.play"]["sk"]


# --------------------------------------------------------------------------
# Lista: skutocny Tk (preskoci sa, ked sa okno vytvorit neda)
# --------------------------------------------------------------------------

def test_lista_ma_prepinac_sveta_s_bublinou():
    ctk = pytest.importorskip("customtkinter")
    import ui_shell
    try:
        root = ctk.CTk()
        root.attributes("-alpha", 0.0)
    except Exception as exc:
        pytest.skip(f"Tk sa neda vytvorit: {exc}")
    try:
        klik = []
        lista = ui_shell.TitleBar(root, root_window=root,
                                  pal=theme.tokens(theme.ZEN),
                                  world_values=["Hra", "Práca"], world_value="Hra",
                                  on_world=klik.append, world_tip="tip")
        lista.pack(fill="x")
        root.update_idletasks()
        assert lista.world_switch is not None
        assert lista.world_switch.get() == "Hra"
        lista.set_world("Práca")
        assert lista.world_switch.get() == "Práca"
        assert klik == [], "set_world nesmie volat on_world (inak slucka)"
        # bez on_world sa prepinac nestavia vobec
        holá = ui_shell.TitleBar(root, root_window=root, pal=theme.tokens(theme.ZEN))
        assert holá.world_switch is None
        holá.set_world("Hra")          # nesmie spadnut
    finally:
        root.destroy()
