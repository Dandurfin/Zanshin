# -*- coding: utf-8 -*-
"""Opravy po overeni triaze 0.2 - veci, ktore mohli ublizit.

  * styri kategorie hlasky su pevne: slot 0-3 sa neda odstranit (kategoriu,
    obrazok aj meranie urcuje pozicia) a profil s menej nez styrmi slotmi
    dostane chybajuce kategorie na koniec, vypnute - nic sa nemaze,
  * prvy × povie, ze appka bezi dalej v liste (port, meranie) a da na vyber,
  * SOUL.md netvrdi plosne, ze data neopustia pocitac.
"""
import ast
import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402
import settings_model as sm  # noqa: E402
from _zdroj_appky import uzol_metody  # noqa: E402

KOREN = os.path.join(os.path.dirname(__file__), "..")


def _read(meno):
    with open(os.path.join(KOREN, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _funkcia(subor, trieda, meno):
    if (subor, trieda) == ("app.py", "DandurfApp"):
        # metoda DandurfApp - aj ked byva v mixine v app_*.py
        return ast.unparse(uzol_metody(meno))
    strom = ast.parse(_read(subor))
    for uzol in ast.walk(strom):
        if isinstance(uzol, ast.ClassDef) and uzol.name == trieda:
            for f in uzol.body:
                if isinstance(f, ast.FunctionDef) and f.name == meno:
                    return ast.unparse(f)
    raise AssertionError(f"{trieda}.{meno} v {subor} chyba")


# --------------------------------------------------------------------------
# Styri pevne kategorie
# --------------------------------------------------------------------------

def test_je_kategoria():
    assert [sm.je_kategoria(i) for i in range(6)] == [True] * 4 + [False] * 2
    assert not sm.je_kategoria(-1)
    assert not sm.je_kategoria(None)


def test_prazdny_profil_dostane_styri_zapnute():
    sloty = sm.doplnit_kategorie([])
    assert len(sloty) == 4
    assert all(s["enabled"] for s in sloty)


def test_kratky_profil_sa_doplni_vypnutymi_na_koniec():
    povodny = sm.normalize_slot({"text": "moja veta", "enabled": True})
    sloty = sm.doplnit_kategorie([povodny])
    assert len(sloty) == 4
    assert sloty[0]["text"] == "moja veta" and sloty[0]["uid"] == povodny["uid"]
    assert sloty[0]["enabled"] is True
    assert [s["enabled"] for s in sloty[1:]] == [False, False, False]
    zaklad = sm.default_slots()
    assert [s["text"] for s in sloty[1:]] == [s["text"] for s in zaklad[1:]]


def test_dlhy_profil_ostane_cely():
    sloty = [sm.normalize_slot({"text": f"s{i}"}) for i in range(6)]
    vysledok = sm.doplnit_kategorie(sloty)
    assert [s["text"] for s in vysledok] == [f"s{i}" for i in range(6)]


@pytest.fixture
def nastavenia(tmp_path, monkeypatch):
    import app as app_mod
    cesta = str(tmp_path / "dandurf_settings.json")
    monkeypatch.setattr(app_mod, "SETTINGS_PATH", cesta)
    povodny = i18n._lang["code"]

    def nacitaj(obsah):
        with open(cesta, "w", encoding="utf-8") as fh:
            json.dump(obsah, fh)
        return app_mod.DandurfApp.load_settings(types.SimpleNamespace())
    yield nacitaj
    i18n.set_lang(povodny)


def test_profil_z_01_s_jednym_slotom_dostane_kategorie_spat(nastavenia):
    d = nastavenia({"lang": "sk", "theme": "zen",
                    "profiles": [{"name": "Moja hra",
                                  "slots": [{"text": "Ťažisko", "enabled": True}]}],
                    "active_profile": "Moja hra"})
    sloty = d["profiles"][0]["slots"]
    assert len(sloty) == 4
    assert sloty[0]["text"] == "Ťažisko" and sloty[0]["enabled"]
    assert not any(s["enabled"] for s in sloty[1:])


def test_legacy_ploche_sloty_sa_tiez_doplnia(nastavenia):
    d = nastavenia({"lang": "sk", "theme": "zen",
                    "slots": [{"text": "a"}, {"text": "b"}]})
    assert len(d["profiles"][0]["slots"]) == 4


def _app_so_slotmi(flags):
    zaznam = {"rebuild": None, "saved": 0}
    sloty = [types.SimpleNamespace(selected=f, text_value=f"s{i}", mode="tts",
                                   to_dict=lambda i=i: {"text": f"s{i}"})
             for i, f in enumerate(flags)]
    return types.SimpleNamespace(
        slots=sloty,
        slot_dicts=lambda: [s.to_dict() for s in sloty],
        rebuild_slots=lambda data: zaznam.__setitem__("rebuild", data),
        save_settings=lambda: zaznam.__setitem__("saved", zaznam["saved"] + 1),
        schedule_pregenerate=lambda *_: None,
        log=lambda *_: None), zaznam


def test_kategoria_sa_neda_odstranit(monkeypatch):
    import app as app_mod
    monkeypatch.setattr(app_mod.messagebox, "showinfo",
                        lambda *a, **k: pytest.fail("ziadna hlaska"))
    a, zaznam = _app_so_slotmi([False] * 4)
    for i in range(4):
        app_mod.DandurfApp.remove_slot(a, i)
    assert zaznam["rebuild"] is None and zaznam["saved"] == 0


def test_slot_navyse_z_01_sa_odstranit_da(monkeypatch):
    import app as app_mod
    a, zaznam = _app_so_slotmi([False] * 5)
    app_mod.DandurfApp.remove_slot(a, 4)
    assert [s["text"] for s in zaznam["rebuild"]] == ["s0", "s1", "s2", "s3"]


def test_hromadne_odstranenie_nesiahne_na_kategorie(monkeypatch):
    import app as app_mod
    otazky = []
    monkeypatch.setattr(app_mod.messagebox, "askyesno",
                        lambda *a, **k: otazky.append(a) or True)
    monkeypatch.setattr(app_mod.messagebox, "showinfo", lambda *a, **k: None)
    # oznacene su vsetky styri kategorie -> nic sa nestane, nic sa nepyta
    a, zaznam = _app_so_slotmi([True] * 4)
    app_mod.DandurfApp.remove_selected_slots(a)
    assert zaznam["rebuild"] is None and not otazky
    # kategorie + jeden slot navyse -> odide len ten navyse
    a, zaznam = _app_so_slotmi([True] * 5)
    app_mod.DandurfApp.remove_selected_slots(a)
    assert len(otazky) == 1
    assert [s["text"] for s in zaznam["rebuild"]] == ["s0", "s1", "s2", "s3"]


def test_karta_kategorie_nema_krizik_ani_zaskrtavatko():
    init = " ".join(_funkcia("ui_dialogs.py", "SlotCard", "__init__").split())
    assert "self.removable = not je_kategoria(index)" in init
    assert "if self.removable: akcie.append(('✕', self.remove, True))" in init
    assert "if self.removable: self.select_check = ctk.CTkCheckBox(" in init
    assert init.count("'✕'") == 1
    assert "if not self.removable" in _funkcia("ui_dialogs.py", "SlotCard", "set_selected")


def test_import_profilu_doplni_kategorie():
    zdroj = _funkcia("app.py", "DandurfApp", "import_profile_from_code")
    assert "doplnit_kategorie(slots)" in zdroj
    assert "normalize_slot({})" not in zdroj


# --------------------------------------------------------------------------
# Prvy × - appka povie, ze bezi dalej v liste
# --------------------------------------------------------------------------

def _app_na_zatvorenie(vysvetlene):
    zaznam = []
    return types.SimpleNamespace(
        tray_close_explained=vysvetlene, hr_port=4455,
        save_settings=lambda: zaznam.append("save"),
        minimize_to_tray=lambda: zaznam.append("tray"),
        quit_app=lambda: zaznam.append("quit")), zaznam


@pytest.mark.parametrize("odpoved, ocakavane", [(True, "tray"), (False, "quit")])
def test_prvy_krizik_sa_opyta(monkeypatch, odpoved, ocakavane):
    import app as app_mod
    monkeypatch.setattr(app_mod, "TRAY_AVAILABLE", True)
    otazky = []
    monkeypatch.setattr(app_mod.messagebox, "askyesno",
                        lambda *a, **k: otazky.append(a) or odpoved)
    a, zaznam = _app_na_zatvorenie(False)
    app_mod.DandurfApp.on_close(a)
    assert len(otazky) == 1 and "4455" in otazky[0][1]
    assert a.tray_close_explained is True
    assert zaznam == ["save", ocakavane]


def test_dalsi_krizik_len_schova(monkeypatch):
    import app as app_mod
    monkeypatch.setattr(app_mod, "TRAY_AVAILABLE", True)
    monkeypatch.setattr(app_mod.messagebox, "askyesno",
                        lambda *a, **k: pytest.fail("uz sa nepyta"))
    a, zaznam = _app_na_zatvorenie(True)
    app_mod.DandurfApp.on_close(a)
    assert zaznam == ["tray"]


def test_znacka_krizika_sa_nacita_a_ulozi(nastavenia):
    assert nastavenia({"lang": "sk", "theme": "zen"})["tray_close_explained"] is False
    assert nastavenia({"lang": "sk", "theme": "zen",
                       "tray_close_explained": True})["tray_close_explained"] is True
    zdroj = _funkcia("app.py", "DandurfApp", "save_settings")
    assert "'tray_close_explained'" in zdroj


def test_veta_o_liste_hovori_o_porte_aj_merani():
    zaznam = i18n.STRINGS["tray.close_first"]
    assert set(zaznam) == set(i18n.LANGUAGES)
    assert "{port}" in zaznam["sk"] and "{port}" in zaznam["en"]
    assert "meriam a ukladám" in zaznam["sk"] and "spustená" in zaznam["sk"]
    assert "measuring and saving" in zaznam["en"]
    # jazyková fáza 0.2: každý jazyk má vlastnú vetu z nového SK - s portom,
    # tlačidlom ▶ a otázkou v samostatnom odseku
    for jazyk in i18n.LANGUAGES:
        assert "{port}" in zaznam[jazyk] and "▶" in zaznam[jazyk], jazyk
        assert zaznam[jazyk].count("\n") == zaznam["sk"].count("\n"), jazyk
        if jazyk not in ("sk", "en"):
            assert zaznam[jazyk] != zaznam["en"], jazyk


# --------------------------------------------------------------------------
# SOUL.md - ziadny plosny slub o sukromi
# --------------------------------------------------------------------------

def test_soul_menuje_vynimku_v_sukromi():
    riadok = next(r for r in _read("SOUL.md").splitlines()
                  if r.startswith("- **Not a harvester.**"))
    assert "Microsoft" in riadok and "PRIVACY.md" in riadok
    assert "and it stays on your machine." not in riadok
