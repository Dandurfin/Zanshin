# -*- coding: utf-8 -*-
"""Export, import a mazanie — najmä to, čo sa nesmie stať potichu.

Import je jediná z tých troch vecí, ktorá vie uškodiť, a robí to bez toho,
aby to bolo vidieť: cudzie dáta otrávia základňu aj model a appka len začne
byť horšia. Väčšina testov nižšie je práve o tom.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import data_io  # noqa: E402
import hr_stats  # noqa: E402


def relacia(started=1000.0, **kw):
    z = {"started": started, "duration_s": 3600.0, "avg_bpm": 80}
    z.update(kw)
    return z


def okno(ts=1000.0, **kw):
    z = {"ts": ts, "cue_id": "slot3", "arm": "voice", "valid": True}
    z.update(kw)
    return z


def zapis(tmp_path, bundle, meno="export.json"):
    cesta = str(tmp_path / meno)
    with open(cesta, "w", encoding="utf-8") as fh:
        json.dump(bundle, fh)
    return cesta


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

def test_export_a_import_prezije_kolo(tmp_path):
    bundle = data_io.build_bundle([relacia()], [okno()], {"x": 1}, "2.1")
    cesta = data_io.write_bundle(str(tmp_path / "e.json"), bundle)
    sessions, windows, zahodene = data_io.parse_bundle(cesta)
    assert len(sessions) == 1 and len(windows) == 1 and zahodene == 0


def test_zapis_neostane_polovicny(tmp_path):
    cesta = str(tmp_path / "e.json")
    data_io.write_bundle(cesta, data_io.build_bundle([relacia()], []))
    assert not os.path.exists(cesta + ".tmp")


# --------------------------------------------------------------------------
# Import — čo sa musí odmietnuť
# --------------------------------------------------------------------------

def test_cudzi_json_sa_odmietne(tmp_path):
    cesta = zapis(tmp_path, {"neco": "ine"})
    try:
        data_io.parse_bundle(cesta)
        assert False, "cudzí súbor musí byť odmietnutý"
    except data_io.ImportError_ as exc:
        assert "foreign" in str(exc)


def test_nie_json_sa_odmietne(tmp_path):
    cesta = str(tmp_path / "x.json")
    with open(cesta, "w", encoding="utf-8") as fh:
        fh.write("toto nie je JSON")
    try:
        data_io.parse_bundle(cesta)
        assert False
    except data_io.ImportError_ as exc:
        assert "not_json" in str(exc)


def test_novsia_verzia_sa_odmietne(tmp_path):
    bundle = data_io.build_bundle([relacia()], [])
    bundle["version"] = data_io.EXPORT_VERSION + 1
    try:
        data_io.parse_bundle(zapis(tmp_path, bundle))
        assert False
    except data_io.ImportError_ as exc:
        assert "newer" in str(exc)


def test_ziadny_pickle_ani_eval():
    """Import je jediné miesto, kam vstupuje cudzí súbor. Nesmie tam byť
    nič, čo by vedelo spustiť kód.

    Kontroluje sa AST, nie výskyt slova — v docstringu sa `pickle` spomína
    zámerne (vysvetľuje, prečo tam nie je).
    """
    import ast
    cesta = os.path.join(os.path.dirname(__file__), "..", "data_io.py")
    strom = ast.parse(open(cesta, encoding="utf-8").read())

    ZAKAZANE = {"pickle", "marshal", "shelve", "subprocess"}
    ZAKAZANE_VOLANIA = {"eval", "exec", "compile", "__import__"}

    for uzol in ast.walk(strom):
        if isinstance(uzol, ast.Import):
            for meno in uzol.names:
                assert meno.name.split(".")[0] not in ZAKAZANE, \
                    f"data_io.py importuje {meno.name}"
        elif isinstance(uzol, ast.ImportFrom):
            assert (uzol.module or "").split(".")[0] not in ZAKAZANE, \
                f"data_io.py importuje z {uzol.module}"
        elif isinstance(uzol, ast.Call) and isinstance(uzol.func, ast.Name):
            assert uzol.func.id not in ZAKAZANE_VOLANIA, \
                f"data_io.py vola {uzol.func.id}()"


def test_rozbite_zaznamy_sa_zahodia_a_spocitaju(tmp_path):
    bundle = data_io.build_bundle(
        [relacia(), {"started": "vcera"}, None, {"duration_s": 5}],
        [okno(), {"ts": None}])
    sessions, windows, zahodene = data_io.parse_bundle(zapis(tmp_path, bundle))
    assert len(sessions) == 1
    assert len(windows) == 1
    assert zahodene == 4


def test_uplne_prazdny_import_sa_odmietne(tmp_path):
    bundle = data_io.build_bundle([{"started": "zle"}], [])
    try:
        data_io.parse_bundle(zapis(tmp_path, bundle))
        assert False
    except data_io.ImportError_ as exc:
        assert "empty" in str(exc)


# --------------------------------------------------------------------------
# Import — príznak a zlučovanie
# --------------------------------------------------------------------------

def test_importovane_su_oznacene(tmp_path):
    """Cudzie telo nie je tvoje telo. Bez príznaku by importované relácie
    ticho posunuli základňu aj výpočet účinnosti."""
    bundle = data_io.build_bundle([relacia()], [okno()])
    sessions, windows, _ = data_io.parse_bundle(zapis(tmp_path, bundle))
    assert sessions[0]["imported"] is True
    assert windows[0]["imported"] is True


def test_zlucenie_nezdvoji_to_iste(tmp_path):
    moje = [relacia(started=1000.0)]
    bundle = data_io.build_bundle([relacia(started=1000.0), relacia(started=2000.0)], [])
    cudzie, _, _ = data_io.parse_bundle(zapis(tmp_path, bundle))
    spolu = data_io.merge_sessions(moje, cudzie)
    assert len(spolu) == 2


def test_pri_zluceni_vyhrava_vlastny_zaznam(tmp_path):
    """Import vlastného exportu nesmie prepísať vlastné relácie ich kópiou
    s príznakom `imported` — inak by si človek jedným kliknutím vyradil
    vlastné dáta z výpočtu účinnosti."""
    moje = [relacia(started=1000.0)]
    bundle = data_io.build_bundle([relacia(started=1000.0)], [])
    cudzie, _, _ = data_io.parse_bundle(zapis(tmp_path, bundle))
    spolu = data_io.merge_sessions(moje, cudzie)
    assert len(spolu) == 1
    assert spolu[0].get("imported") is not True


def test_zlucenie_zoradi_podla_casu(tmp_path):
    spolu = data_io.merge_sessions([relacia(started=3000.0)],
                                   [relacia(started=1000.0, imported=True)])
    assert [s["started"] for s in spolu] == [1000.0, 3000.0]


# --------------------------------------------------------------------------
# Mazanie
# --------------------------------------------------------------------------

def test_plan_mazania_vymenuje_co_zmizne(tmp_path):
    """Musí sa dať ukázať MENOVITE, čo zmazanie odstráni. Sľub 'všetko
    ostáva u teba' znamená aj to, že 'zmazať' naozaj zmaže."""
    for meno in ("hr_sessions.json", "hr_events.jsonl"):
        (tmp_path / meno).write_text("[]", encoding="utf-8")
    plan = data_io.delete_plan(str(tmp_path))
    mena = [p["label"] for p in plan]
    for kluc in ("data.delete.sessions", "data.delete.events",
                 "data.delete.windows", "data.delete.insights"):
        assert kluc in mena, kluc
    assert next(p for p in plan if p["label"] == "data.delete.events")["exists"]


def test_zaznamy_hlasok_sa_zmazu(tmp_path):
    """B1: hr_events.jsonl je tep/záťaž/hra za KAŽDÝ večer — pri 'Zmazať
    históriu' sa NESMIE nechať na disku. Dovtedy prežíval a dialóg pritom
    hlásil 'Zmazané'. Toto je jadro chyby B1."""
    p = tmp_path / "hr_events.jsonl"
    p.write_text('{"typ":"x"}\n', encoding="utf-8")
    data_io.delete_all(str(tmp_path))
    assert not p.exists()


def test_zalohy_a_docasne_subory_sa_zmazu(tmp_path):
    """Záloha spred prepočtu a .bak/.tmp nesmú prežiť — sú to kópie dát."""
    (tmp_path / "hr_sessions.json").write_text("[]", encoding="utf-8")
    zalohy = [
        tmp_path / "hr_windows.json.pred-prepoctom-20260919-145129",
        tmp_path / "hr_sessions.json.bak",
        tmp_path / "hr_sessions.json.tmp",
    ]
    for z in zalohy:
        z.write_text("[]", encoding="utf-8")
    data_io.delete_all(str(tmp_path))
    for z in zalohy:
        assert not z.exists(), z


def test_tts_cache_sa_zmaze(tmp_path):
    """Vyslovené hlášky sú cache na disku — pri 'zmazať' musia zmiznúť."""
    cache = tmp_path / "audio" / "tts_cache"
    cache.mkdir(parents=True)
    (cache / "hlas.mp3").write_text("x", encoding="utf-8")
    data_io.delete_all(str(tmp_path))
    assert not (cache / "hlas.mp3").exists()


def test_mazanie_nezhodi_cely_priecinok_logs(tmp_path):
    """V dev režime je data_dir priečinok projektu a logs/ v ňom drží
    gui_screenshots aj iné veci mimo histórie hráča. rmtree celého priečinka
    ich mazal — smú sa mazať len vlastné logy appky."""
    logs = tmp_path / "logs"
    (logs / "gui_screenshots").mkdir(parents=True)
    (logs / "gui_screenshots" / "01.png").write_text("obrazok", encoding="utf-8")
    (logs / "app.log").write_text("živý", encoding="utf-8")   # za behu zamknutý
    (logs / "app.log.1").write_text("stary", encoding="utf-8")
    (logs / "crash.log").write_text("pad", encoding="utf-8")

    data_io.delete_all(str(tmp_path))

    assert (logs / "gui_screenshots" / "01.png").exists(), "zmazalo nesúvisiace"
    assert (logs / "app.log").exists(), "živý app.log sa nemá mazať"
    assert not (logs / "app.log.1").exists(), "rotovaný log má zmiznúť"
    assert not (logs / "crash.log").exists(), "crash.log má zmiznúť"


def test_mazanie_naozaj_zmaze_vsetko(tmp_path):
    for meno in ("hr_sessions.json", "hr_events.jsonl", "hr_windows.json",
                 "hr_insights.json"):
        (tmp_path / meno).write_text("[]", encoding="utf-8")
    (tmp_path / "hr_windows.json.pred-prepoctom-1").write_text("[]", encoding="utf-8")
    assert data_io.delete_all(str(tmp_path)) == 5
    for p in data_io.delete_plan(str(tmp_path)):
        assert not p["exists"], f"{p['path']} prežilo mazanie"


def test_mazanie_na_prazdnom_priecinku_nespadne(tmp_path):
    assert data_io.delete_all(str(tmp_path)) == 0


# --------------------------------------------------------------------------
# Kontext relácie
# --------------------------------------------------------------------------

def test_kontext_sa_normalizuje():
    assert hr_stats.normalize_context(["grind", "call"]) == ["call", "grind"]
    assert hr_stats.normalize_context(["vymysleny"]) == []
    assert hr_stats.normalize_context(["call", "call"]) == ["call"]


def test_preskocenie_nie_je_to_iste_co_nic_z_toho():
    """None = hráč sa nevyjadril. [] = povedal 'nič z toho'.

    Zlúčiť ich by znamenalo stratiť informáciu, ktorá je pri čistení dát
    to jediné podstatné: či sa na kontext dá spoľahnúť.
    """
    assert hr_stats.normalize_context(None) is None
    assert hr_stats.normalize_context([]) == []


def test_kontext_sa_pripoji_k_ulozenej_relacii(tmp_path):
    cesta = str(tmp_path / "hr_sessions.json")
    with open(cesta, "w", encoding="utf-8") as fh:
        json.dump([relacia(started=1000.0), relacia(started=2000.0)], fh)

    assert hr_stats.attach_context(cesta, 2000.0, ["grind"]) is True
    with open(cesta, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data[0].get("context") is None
    assert data[1]["context"] == ["grind"]


def test_kontext_k_neexistujucej_relacii_nie_je_chyba(tmp_path):
    """Krátka relácia sa neuloží vôbec - dotazník na ňu potom nemá čo
    naviazať a nie je to dôvod na chybu."""
    cesta = str(tmp_path / "hr_sessions.json")
    with open(cesta, "w", encoding="utf-8") as fh:
        json.dump([relacia(started=1000.0)], fh)
    assert hr_stats.attach_context(cesta, 9999.0, ["chill"]) is False


def test_neulozeny_kontext_zanecha_stopu_v_logu(tmp_path):
    """B16: kontext (káva/alkohol/spánok) je najväčší vysvetliteľný zdroj
    rozptylu — stratiť ho POTICHU je najhorší druh chyby. Každý prípad, keď
    sa neuloží, musí prejsť cez `log`, aby to volajúci vedel oznámiť hráčovi."""
    cesta = str(tmp_path / "hr_sessions.json")
    with open(cesta, "w", encoding="utf-8") as fh:
        json.dump([relacia(started=1000.0)], fh)

    logy = []
    # relácia sa nenašla → False + záznam
    assert hr_stats.attach_context(cesta, 9999.0, ["chill"], log=logy.append) is False
    assert logy, "nenájdená relácia musí zanechať stopu"
    # súbor neexistuje → False + záznam
    logy.clear()
    assert hr_stats.attach_context(str(tmp_path / "niet.json"), 1.0, [],
                                   log=logy.append) is False
    assert logy


def test_uspesny_kontext_nelogu_je(tmp_path):
    """Pri úspechu sa nič nesťažuje — log je len pre zlyhania."""
    cesta = str(tmp_path / "hr_sessions.json")
    with open(cesta, "w", encoding="utf-8") as fh:
        json.dump([relacia(started=2000.0)], fh)
    logy = []
    assert hr_stats.attach_context(cesta, 2000.0, ["grind"], log=logy.append) is True
    assert logy == []


# --------------------------------------------------------------------------
# Udalosti automatu (bod 6 zadania z 18. 9.)
#
# `_cue_log` zbieral každú udalosť a na konci relácie sa z neho použil len
# POČET do dialógu. Potom sa zahodil — priebeh večera sa spätne nedal
# prečítať ani pri diagnostike.
# --------------------------------------------------------------------------

def test_udalosti_sa_dopisuju_a_nie_prepisuju(tmp_path):
    p = str(tmp_path / "u.jsonl")
    data_io.append_events(p, [{"typ": "armed", "ts": 1.0}])
    data_io.append_events(p, [{"typ": "deliver", "ts": 2.0}])
    von = data_io.read_events(p)
    assert [u["typ"] for u in von] == ["armed", "deliver"]


def test_udalosti_nesu_zaciatok_relacie(tmp_path):
    """Bez toho sa dajú zoskupiť len hádaním z časov."""
    p = str(tmp_path / "u.jsonl")
    data_io.append_events(p, [{"typ": "armed", "ts": 10.0}], started=5.0)
    assert data_io.read_events(p)[0]["session_started"] == 5.0


def test_poskodeny_riadok_log_nezhodi(tmp_path):
    """Log sa číta pri diagnostike, teda vtedy, keď už je niečo zle. Vtedy
    je najhoršie, keď sa nedá otvoriť vôbec."""
    p = str(tmp_path / "u.jsonl")
    data_io.append_events(p, [{"typ": "armed", "ts": 1.0}])
    with open(p, "a", encoding="utf-8") as fh:
        fh.write("toto nie je json\n")
    data_io.append_events(p, [{"typ": "deliver", "ts": 2.0}])
    assert len(data_io.read_events(p)) == 2


def test_log_nerastie_donekonecna(tmp_path):
    p = str(tmp_path / "u.jsonl")
    for i in range(40):
        data_io.append_events(p, [{"typ": "armed", "ts": float(i)}],
                              max_riadkov=10)
    von = data_io.read_events(p)
    assert len(von) == 10
    assert von[-1]["ts"] == 39.0, "zahadzovat sa maju NAJSTARSIE"


def test_prazdny_zoznam_subor_nevyrobi(tmp_path):
    p = str(tmp_path / "u.jsonl")
    assert data_io.append_events(p, []) == 0
    assert not os.path.exists(p)


# --------------------------------------------------------------------------
# Export do tabuľky
# --------------------------------------------------------------------------

def test_export_berie_stlpce_zo_vsetkych_riadkov(tmp_path):
    """Kľúč, ktorý pribudol až neskôr (napr. nová kategória hlášky), by
    z exportu inak ticho vypadol."""
    p = str(tmp_path / "t.csv")
    data_io.export_rows_csv([{"a": 1}, {"a": 2, "b": 3}], p)
    # newline="" - bez neho Python prevedie CRLF na LF uz pri citani a test
    # by presiel aj vtedy, keby sa cely subor zapisal ako jediny riadok.
    with open(p, encoding="utf-8-sig", newline="") as fh:
        riadky = [r for r in fh.read().split("\r\n") if r]
    assert len(riadky) == 3, riadky
    assert riadky[0].split(";") == ["a", "b"], riadky[0]


def test_export_pouziva_desatinnu_ciarku(tmp_path):
    """Excel v SK/CZ vidí bodku ako text, nie ako číslo."""
    p = str(tmp_path / "t.csv")
    data_io.export_rows_csv([{"x": 1.5}], p)
    assert "1,5" in open(p, encoding="utf-8-sig").read()


def test_export_neprepusti_oddelovac_do_bunky(tmp_path):
    """Bodkočiarka v texte by riadok rozsypala na viac stĺpcov."""
    p = str(tmp_path / "t.csv")
    data_io.export_rows_csv([{"x": "a;b", "y": "c\nd"}], p)
    with open(p, encoding="utf-8-sig", newline="") as fh:
        riadky = [r for r in fh.read().split("\r\n") if r]
    assert len(riadky) == 2, "novy riadok v bunke rozsypal subor: %r" % riadky
    assert all(r.count(";") == 1 for r in riadky), riadky


def test_export_prazdneho_zoznamu_nic_nezapise(tmp_path):
    p = str(tmp_path / "t.csv")
    assert data_io.export_rows_csv([], p) == 0
    assert not os.path.exists(p)


def test_citatelny_cas_sa_prida_k_timestampu():
    von = data_io.s_casom([{"ts": 1789620987.3}])
    assert "kedy" in von[0] and ":" in von[0]["kedy"]


def test_citatelny_cas_znesie_chybajuci_timestamp():
    von = data_io.s_casom([{"nic": 1}])
    assert von and "kedy" not in von[0]


# --------------------------------------------------------------------------
# História — odolnosť voči pokazenému súboru (B15)
# --------------------------------------------------------------------------

def test_pokazeny_subor_historie_sa_neprepise_ale_odlozi(tmp_path):
    """B15: keď je hr_sessions.json pokazený, uloženie novej relácie ho
    NESMIE prepísať — inak sa všetky predošlé večery stratia navždy a odvtedy
    každý ďalší rovnako ticho. Pokazený súbor sa odloží bokom na záchranu."""
    import glob
    import hr_stats
    p = str(tmp_path / "hr_sessions.json")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("{ toto nie je platny json")

    logy = []
    r = {"samples": 50, "duration_s": 120.0, "started": 1.0, "avg_bpm": 90}
    assert hr_stats.save_session(p, r, log=logy.append) is True
    # pôvodný pokazený obsah je odložený, nie zahodený
    assert glob.glob(p + ".corrupt-*"), "pokazený súbor sa mal odložiť na záchranu"
    # a ukladanie pokračuje s platným zoznamom
    with open(p, encoding="utf-8") as fh:
        assert isinstance(json.load(fh), list)
    assert logy, "strata dát musí zanechať stopu v logu"


def test_load_sessions_rozlisi_prazdne_od_necitatelneho(tmp_path):
    """Prázdny zoznam z `load_sessions` pri POKAZENOM súbore znamená
    'nedalo sa prečítať', nie 'žiadne relácie' — a musí zanechať stopu.
    Neexistujúci súbor je naopak ticho (hráč ešte nič nenameral)."""
    import hr_stats
    logy = []
    assert hr_stats.load_sessions(str(tmp_path / "niet.json"), log=logy.append) == []
    assert logy == [], "neexistujúci súbor nie je chyba"

    p = str(tmp_path / "hr_sessions.json")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("nie json")
    logy2 = []
    assert hr_stats.load_sessions(p, log=logy2.append) == []
    assert logy2, "nečitateľná história musí zanechať stopu"
