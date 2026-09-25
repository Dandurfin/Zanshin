# -*- coding: utf-8 -*-
"""Bezpečnosť dát hráča (0.2): import, mazanie, staré kópie po migrácii,
odinštalovanie.

  * import hlási, koľko zo súboru NAOZAJ pribudlo, pred zápisom odloží
    oba súbory 1:1 a NAHRADIŤ ide až na druhý klik,
  * importované (cudzie) relácie neposúvajú dávkovanie tichých hlášok,
  * „Zmazať históriu“ zmaže aj kópie, ktoré v starých priečinkoch nechala
    migrácia - a zmazaná história sa už nevráti spoza .exe,
  * odinštalovanie sa pýta aj na históriu tepu a pri „Nie“ zmaže aj staré
    priečinky.

Bez Tk: `data_io`/`paths` sú čisto dátové, z `app.py` len metóda na atrape
a zdrojový text.
"""
import json
import os
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import data_io  # noqa: E402
import hr_stats  # noqa: E402
import i18n  # noqa: E402
from _zdroj_appky import zdroj_metody  # noqa: E402


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8-sig") as fh:
        return fh.read()


def relacia(started=1000.0, **kw):
    z = {"started": started, "duration_s": 3600.0, "avg_bpm": 80}
    z.update(kw)
    return z


def okno(ts=1000.0, **kw):
    z = {"ts": ts, "cue_id": "slot3", "arm": "voice", "valid": True}
    z.update(kw)
    return z


# --------------------------------------------------------------------------
# Import - počty, záloha, zápis
# --------------------------------------------------------------------------

def test_hlasi_sa_len_to_co_naozaj_pribudlo():
    """Po zlúčení s 200 vlastnými reláciami hlásenie tvrdilo „importované:
    205“, hoci zo súboru pribudlo 5. Duplikát ani to, čo odreže strop
    histórie, sa nepočíta."""
    moje_s = [relacia(started=float(i)) for i in range(1, 201)]
    moje_w = [okno(ts=float(i)) for i in range(1, 51)]
    cudzie_s = [relacia(started=float(i), imported=True) for i in (5, 1000, 1001)]
    cudzie_w = [okno(ts=1000.0, imported=True)]
    s, w, n_s, n_w = data_io.vysledok_importu(moje_s, moje_w, cudzie_s, cudzie_w, False)
    assert (len(s), len(w)) == (202, 51)
    assert (n_s, n_w) == (2, 1), "started=5 už mám - vlastný záznam vyhráva"


def test_co_odreze_strop_historie_sa_nerata():
    moje_s = [relacia(started=float(i)) for i in range(1, 201)]
    stare = [relacia(started=0.5, imported=True)]
    s, _w, n_s, _n_w = data_io.vysledok_importu(moje_s, [], stare, [], False, max_s=200)
    assert len(s) == 200 and n_s == 0


def test_nahradit_zapise_len_obsah_suboru():
    moje = [relacia(started=1.0)]
    cudzie = [relacia(started=9.0, imported=True), relacia(started=3.0, imported=True)]
    s, w, n_s, n_w = data_io.vysledok_importu(moje, [okno()], cudzie, [], True)
    assert [x["started"] for x in s] == [3.0, 9.0] and w == []
    assert (n_s, n_w) == (2, 0)


def test_zaloha_pred_importom_je_kopia_1_na_1(tmp_path):
    """Predošlá záloha bola vo formáte exportu (load_sessions ju nevedel
    načítať) a meracie okná sa pri NAHRADIŤ prepísali bez zálohy vôbec."""
    rel = tmp_path / "hr_sessions.json"
    okn = tmp_path / "hr_windows.json"
    rel.write_text(json.dumps([relacia()]), encoding="utf-8")
    okn.write_text(json.dumps([okno()]), encoding="utf-8")
    zalohy = data_io.zaloha_pred_importom(
        [str(rel), str(okn), str(tmp_path / "niet.json")], znacka="20260924-070000")
    assert [os.path.basename(z) for z in zalohy] == [
        "hr_sessions.json.pred-importom-20260924-070000.bak",
        "hr_windows.json.pred-importom-20260924-070000.bak"]
    assert hr_stats.load_sessions(zalohy[0]) == [relacia()], \
        "zálohu musí vedieť načítať appka"
    with open(zalohy[1], encoding="utf-8") as fh:
        assert fh.read() == okn.read_text(encoding="utf-8")


def test_zalohy_z_importu_zmaze_aj_zmazat_historiu(tmp_path):
    for meno in ("hr_sessions.json", "hr_windows.json"):
        (tmp_path / meno).write_text("[]", encoding="utf-8")
    zalohy = data_io.zaloha_pred_importom(
        [str(tmp_path / "hr_sessions.json"), str(tmp_path / "hr_windows.json")])
    data_io.delete_all(str(tmp_path))
    for z in zalohy:
        assert not os.path.exists(z), z


def test_zapis_zoznamu_je_atomicky(tmp_path):
    cesta = str(tmp_path / "hr_sessions.json")
    data_io.zapis_zoznam(cesta, [relacia()])
    assert not os.path.exists(cesta + ".tmp")
    assert hr_stats.load_sessions(cesta) == [relacia()]


def test_vlastne_vynecha_importovane():
    zaznamy = [relacia(), relacia(started=2.0, imported=True), "zle", None]
    assert data_io.vlastne(zaznamy) == [relacia()]


def test_tiche_hlasky_ratame_len_z_vlastnych_relacii():
    """Import 15+ relácií od kamaráta nesmie ukončiť fázu, v ktorej tiché
    rameno mlčí častejšie (1/4) - cudzie telo sa nepočíta."""
    import app as app_mod
    cudzie = [relacia(started=float(i), imported=True) for i in range(20)]
    atrapa = types.SimpleNamespace(_dev_silent_share=None,
                                   _history_sessions=lambda: cudzie)
    assert app_mod.DandurfApp._silent_share_for_next_session(atrapa) == 0.25
    vlastne = [relacia(started=float(i)) for i in range(20)]
    atrapa._history_sessions = lambda: vlastne
    assert app_mod.DandurfApp._silent_share_for_next_session(atrapa) == 0.10


def test_import_nema_natvrdo_ano_nie_a_nahradit_je_na_dva_kliky():
    """Systémový askyesnocancel mal „= Áno / = Nie“ natvrdo po slovensky a
    tlačidlá v jazyku Windowsu. NAHRADIŤ bolo na „Nie“ bez potvrdenia."""
    # import = dialog (`import_all_json`) + zapis vysledku (`_zapis_import`)
    imp = zdroj_metody("import_all_json") + "\n" + zdroj_metody("_zapis_import")
    assert "messagebox.askyesnocancel(" not in imp and "= Áno" not in imp
    assert "ImportDataDialog(" in imp
    assert "data_io.zaloha_pred_importom(" in imp
    assert imp.index("zaloha_pred_importom(") < imp.index("zapis_zoznam("), \
        "najprv záloha, potom zápis"
    dlg_src = _read("ui_dialogs.py")
    dlg = dlg_src[dlg_src.index("class ImportDataDialog"):]
    dlg = dlg[:dlg.index("\nclass ")]
    for kluc in ("data.import.merge", "data.import.replace", "common.cancel",
                 "data.import.replace_confirm", "data.import.replace_yes"):
        assert kluc in dlg, kluc
    # NAHRADIŤ z prvého kroku ešte nič nezapisuje - len druhý krok
    prvy = dlg[dlg.index("def _choose"):dlg.index("def _confirm_replace")]
    assert '"replace"' not in prvy


def test_texty_importu_su_vo_vsetkych_jazykoch():
    for kluc in ("data.import.question", "data.import.replace_confirm",
                 "data.import.replace_yes", "data.import.back",
                 "data.import.backup", "data.import.flagged", "data.delete.legacy"):
        assert set(i18n.STRINGS[kluc]) >= set(i18n.LANGUAGES), kluc


def test_text_o_oznaceni_menuje_co_sa_vyraduje():
    sk = i18n.STRINGS["data.import.flagged"]["sk"]
    for slovo in ("základne", "hranice vysokého tepu", "prahu", "postrehov",
                  "grafu", "karty poslednej relácie", "pauzu"):
        assert slovo in sk, slovo
    assert "účinnosti nevstúpia" not in sk


# --------------------------------------------------------------------------
# Mazanie - staré kópie po migrácii (paths.legacy_data_dirs)
# --------------------------------------------------------------------------

def _stary_priecinok(koren):
    koren.mkdir()
    (koren / "hr_sessions.json").write_text("[1]", encoding="utf-8")
    (koren / "hr_sessions.json.bak").write_text("[1]", encoding="utf-8")
    (koren / "hr_events.jsonl").write_text("{}\n", encoding="utf-8")
    (koren / "dandurf_settings.json").write_text("{}", encoding="utf-8")
    (koren / "logs").mkdir()
    (koren / "logs" / "app.log").write_text("stary log", encoding="utf-8")
    (koren / "audio" / "tts_cache").mkdir(parents=True)
    (koren / "audio" / "tts_cache" / "a.mp3").write_text("x", encoding="utf-8")
    return koren


def test_zmazat_historiu_zmaze_aj_kopie_v_starych_priecinkoch(tmp_path):
    """Migrácia pri premenovaní appky dáta KOPÍROVALA, takže v starom
    priečinku ostala druhá kópia histórie tepu. „Zmazať“ ju nesmie nechať."""
    ciel = tmp_path / "Zanshin"
    ciel.mkdir()
    (ciel / "hr_sessions.json").write_text("[]", encoding="utf-8")
    stary = _stary_priecinok(tmp_path / "Dandurf")

    plan = data_io.delete_plan(str(ciel), legacy_dirs=[str(stary)])
    stare = [p for p in plan if p.get("legacy")]
    assert stare and all(p["exists"] for p in stare)

    data_io.delete_all(str(ciel), legacy_dirs=[str(stary)])
    for meno in ("hr_sessions.json", "hr_sessions.json.bak", "hr_events.jsonl",
                 os.path.join("logs", "app.log")):
        assert not (stary / meno).exists(), meno
    assert not (stary / "audio" / "tts_cache").exists(), \
        "v starom priečinku sa cache nevytvára nanovo"
    assert (stary / "dandurf_settings.json").exists(), \
        "Zmazať históriu maže históriu, nie nastavenia"
    assert not (ciel / "hr_sessions.json").exists()


def test_dialog_mazania_spomenie_stare_kopie_menom_priecinka(tmp_path):
    ciel = tmp_path / "Zanshin"
    ciel.mkdir()
    stary = _stary_priecinok(tmp_path / "Zanshin DojoSync")
    riadky = data_io.plan_riadky(
        data_io.delete_plan(str(ciel), legacy_dirs=[str(stary)]))
    stare = [r for r in riadky if r["label"] == "data.delete.legacy"]
    assert len(stare) == 1, "jeden riadok na priečinok, nie zoznam súborov"
    assert stare[0]["params"] == {"folder": "Zanshin DojoSync"}
    assert stare[0]["bytes"] > 0
    # bez starých priečinkov je plán rovnaký ako doteraz
    assert all(r["label"] != "data.delete.legacy"
               for r in data_io.plan_riadky(data_io.delete_plan(str(ciel))))
    assert "{folder}" in i18n.STRINGS["data.delete.legacy"]["sk"]


def test_app_posiela_stare_priecinky_do_mazania_aj_dialogu():
    telo = zdroj_metody("delete_history")
    assert "legacy_data_dirs()" in telo
    assert "data_io.plan_riadky(plan)" in telo
    assert "legacy_dirs=stare" in telo


def test_ciel_sa_ako_stary_priecinok_nezmaze_dvakrat(tmp_path):
    (tmp_path / "hr_sessions.json").write_text("[]", encoding="utf-8")
    plan = data_io.delete_plan(str(tmp_path), legacy_dirs=[str(tmp_path)])
    assert not any(p.get("legacy") for p in plan)


def _zmrazena_appka(monkeypatch, tmp_path):
    import paths
    appdata = tmp_path / "Roaming"
    appdata.mkdir()
    exe_dir = tmp_path / "Programs" / "Zanshin"
    exe_dir.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "Zanshin.exe"))
    monkeypatch.setenv("APPDATA", str(appdata))
    return paths, appdata, exe_dir


def test_zmazana_historia_sa_nevrati_z_kopie_vedla_exe(monkeypatch, tmp_path):
    """Kópia od .exe bežala pri KAŽDOM štarte a dopĺňala, čo v cieli chýba -
    zmazaná história sa pri ďalšom spustení vrátila. Migruje sa len pri
    prvom štarte (v cieli ešte nie sú nastavenia)."""
    paths, appdata, exe_dir = _zmrazena_appka(monkeypatch, tmp_path)
    (exe_dir / "hr_sessions.json").write_text("[1]", encoding="utf-8")
    ciel = appdata / "Zanshin"
    ciel.mkdir()
    (ciel / "dandurf_settings.json").write_text("{}", encoding="utf-8")
    paths.migrate_legacy_data(str(ciel))
    assert not (ciel / "hr_sessions.json").exists()


def test_prvy_start_stale_migruje(monkeypatch, tmp_path):
    paths, appdata, exe_dir = _zmrazena_appka(monkeypatch, tmp_path)
    stary = appdata / "Dandurf"
    stary.mkdir()
    (stary / "dandurf_settings.json").write_text("{}", encoding="utf-8")
    (stary / "hr_sessions.json").write_text("[1]", encoding="utf-8")
    (exe_dir / "hr_windows.json").write_text("[]", encoding="utf-8")
    ciel = appdata / "Zanshin"
    paths.migrate_legacy_data(str(ciel))
    for meno in ("dandurf_settings.json", "hr_sessions.json", "hr_windows.json"):
        assert (ciel / meno).exists(), meno


def test_stare_priecinky_najde_len_zabalena_appka(monkeypatch, tmp_path):
    import paths
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert paths.legacy_data_dirs(str(tmp_path)) == []

    paths, appdata, exe_dir = _zmrazena_appka(monkeypatch, tmp_path)
    (appdata / "Dandurf").mkdir()
    ciel = appdata / "Zanshin"
    ciel.mkdir()
    najdene = paths.legacy_data_dirs(str(ciel))
    assert str(appdata / "Dandurf") in najdene
    assert str(exe_dir) in najdene
    assert str(appdata / "Zanshin DojoSync") not in najdene, "neexistuje"
    assert str(ciel) not in najdene


# --------------------------------------------------------------------------
# Odinštalovanie (Dandurf.iss)
# --------------------------------------------------------------------------

def _iss():
    with open(os.path.join(ROOT, "Dandurf.iss"), "rb") as fh:
        return fh.read()


def test_iss_ostava_utf8_s_bom_a_lf():
    d = _iss()
    assert d.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in d


def test_otazka_pri_odinstalovani_spomenie_historiu_tepu_vo_vsetkych_jazykoch():
    text = _iss().decode("utf-8-sig")
    otazky = {r.split(".KeepDataQuestion=")[0]: r.split("=", 1)[1]
              for r in text.splitlines() if ".KeepDataQuestion=" in r}
    assert len(otazky) == 11, otazky
    assert otazky["slovak"] == ("Ponechať tvoje nastavenia, históriu tepu, "
                                "nahrávky a vygenerované hlásky?")
    assert otazky["english"] == ("Keep your settings, heart-rate history, "
                                 "recordings and generated voice lines?")
    slovo = {"japanese": "心拍", "chinesesimplified": "心率", "russian": "пульс",
             "spanish": "cardíaca", "german": "Herzfrequenz",
             "french": "cardiaque", "portuguese": "cardíaca",
             "czech": "historii tepu", "bulgarian": "историята на пулса"}
    for jazyk, kus in slovo.items():
        assert kus in otazky[jazyk], jazyk


@pytest.mark.parametrize("priecinok", ["{#MyAppName}", "Zanshin DojoSync", "Dandurf"])
def test_pri_nie_sa_zmazu_aj_stare_priecinky(priecinok):
    kod = _iss().decode("utf-8-sig")
    kod = kod[kod.index("[Code]"):]
    assert "ExpandConstant('{userappdata}\\%s')" % priecinok in kod
    assert "DelTree(Dirs[I], True, True, True)" in kod
