# -*- coding: utf-8 -*-
"""Jeden zly bajt v nastaveniach uz nezmaze vsetko (0.2.2).

Doteraz: nečitatelny dandurf_settings.json -> predvolene profily, texty aj
polohy vizualov, a `__init__` o sekundu neskor (`save_settings`) pokazeny
subor prepisal, takze sa uz nedal ani zachranit. Strazi sa:

  * pred kazdym zapisom ide doterajsi PLATNY subor do `.bak` (atomicky),
    pokazeny tam nejde - neprepise jedinu dobru kopiu,
  * pokazeny subor sa pri nacitani odlozi ako `.corrupt-RRRRmmdd-HHMMSS`
    a nacita sa `.bak`; bez zalohy predvolene,
  * hrac sa to dozvie raz - riadok v denniku a sprava az po starte okna,
  * .gitignore kryje `.bak` aj `.corrupt-*`.

Vsetko v tmp priecinku (SETTINGS_PATH presmerovany na module app_prefs).
"""
import fnmatch
import json
import os
import types

import pytest

import i18n
from _zdroj_appky import zdroj_metody, zdroj_suboru


@pytest.fixture
def prostredie(tmp_path, monkeypatch):
    import app_prefs
    cesta = str(tmp_path / "dandurf_settings.json")
    # `load_settings` / `save_settings` citaju SETTINGS_PATH z modulu app_prefs
    monkeypatch.setattr(app_prefs, "SETTINGS_PATH", cesta)
    povodny = i18n._lang["code"]
    yield cesta
    i18n.set_lang(povodny)


def _nacitaj():
    import app as app_mod
    ja = types.SimpleNamespace()
    data = app_mod.DandurfApp.load_settings(ja)
    return data, getattr(ja, "_nastavenia_obnova", None)


def _zapis(cesta, obsah):
    with open(cesta, "w", encoding="utf-8") as fh:
        json.dump(obsah, fh)


def _uloz(data, **zmeny):
    """Skutocne `save_settings` nad stavom z `load_settings`."""
    import app as app_mod
    a = types.SimpleNamespace(
        _ready=True, slots=[object()], _sync_active_profile_slots=lambda: None,
        profiles=data["profiles"], active_profile_name=data["active_profile"],
        saved_voice_id=data["voice_id"], rate_value=data["rate"],
        volume_value=data["volume"], balance_value=data["balance"],
        engine_pref=data["engine_pref"], edge_voice_id=data["edge_voice"],
        theme_key=data["theme"], world=data["world"], cue_style=data["cue_style"],
        lang=data["lang"], start_minimized=data["start_minimized"],
        tray_close_explained=data["tray_close_explained"],
        auto_profile_enabled=data["auto_profile_enabled"],
        overlay_configs=data["overlay_configs"], hr_ip=data["hr_ip"],
        hr_port=data["hr_port"], hr_monitoring_enabled=data["hr_monitoring_enabled"],
        zanshin_graduated=data["zanshin_graduated"],
        zanshin_graduated_at=data["zanshin_graduated_at"],
        snooze_hotkey=data["snooze_hotkey"],
        background_opacity=data["background_opacity"],
        monitor_target=data["monitor_target"], hud_config=data["hud_config"],
        dashboard_stats=data["dashboard_stats"],
        breath_inhale_s=data["breath_inhale_s"],
        breath_exhale_s=data["breath_exhale_s"],
        old_installer_warned=data["old_installer_warned"],
        log=lambda _m: None)
    for k, v in zmeny.items():
        setattr(a, k, v)
    app_mod.DandurfApp.save_settings(a)


def _platne(meno="Moj profil", hlasitost=37):
    return {"lang": "sk", "theme": "zen", "volume": hlasitost,
            "profiles": [{"name": meno, "slots": []}], "active_profile": meno}


# --------------------------------------------------------------------------
# zaloha pred zapisom
# --------------------------------------------------------------------------

def test_ulozenie_zalohuje_predosly_platny_subor(prostredie):
    _zapis(prostredie, _platne(hlasitost=37))
    with open(prostredie, "rb") as fh:
        predtym = fh.read()
    data, _ = _nacitaj()
    _uloz(data, volume_value=80)
    with open(prostredie + ".bak", "rb") as fh:
        assert fh.read() == predtym, ".bak = presne posledny platny subor"
    with open(prostredie, encoding="utf-8") as fh:
        assert json.load(fh)["volume"] == 80
    assert not os.path.exists(prostredie + ".bak.tmp")


def test_pokazeny_subor_neprepise_dobru_zalohu(prostredie):
    import app_prefs
    _zapis(prostredie + ".bak", _platne(hlasitost=11))
    with open(prostredie, "w", encoding="utf-8") as fh:
        fh.write('{"lang": "sk", "volume": 9')           # orezany JSON
    assert app_prefs.zaloha_nastaveni(prostredie) is False
    with open(prostredie + ".bak", encoding="utf-8") as fh:
        assert json.load(fh)["volume"] == 11
    # platny JSON, ale nie objekt nastaveni - tiez nie
    _zapis(prostredie, [1, 2, 3])
    assert app_prefs.zaloha_nastaveni(prostredie) is False


def test_prvy_start_zalohu_nevytvori(prostredie):
    import app_prefs
    assert app_prefs.zaloha_nastaveni(prostredie) is False
    assert not os.path.exists(prostredie + ".bak")


def test_zlyhana_zaloha_nezastavi_ulozenie(prostredie, monkeypatch):
    import app_prefs
    _zapis(prostredie, _platne())
    data, _ = _nacitaj()

    def _pad(_c):
        raise PermissionError("subor drzi antivirus")

    monkeypatch.setattr(app_prefs, "zaloha_nastaveni", _pad)
    _uloz(data, volume_value=55)
    with open(prostredie, encoding="utf-8") as fh:
        assert json.load(fh)["volume"] == 55


# --------------------------------------------------------------------------
# pokazeny subor pri nacitani
# --------------------------------------------------------------------------

def _odlozene(cesta):
    priecinok = os.path.dirname(cesta)
    return sorted(m for m in os.listdir(priecinok)
                  if m.startswith(os.path.basename(cesta) + ".corrupt-"))


def test_pokazeny_subor_sa_odlozi_a_nacita_sa_zaloha(prostredie):
    _zapis(prostredie, _platne(meno="Valorant", hlasitost=42))
    data, _ = _nacitaj()
    _uloz(data)                              # vznikne .bak s profilom Valorant
    with open(prostredie, "w", encoding="utf-8") as fh:
        fh.write('{"lang": "sk", "profiles": [{"name": "Valo')   # jeden zly bajt
    data, obnova = _nacitaj()
    assert [p["name"] for p in data["profiles"]] == ["Valorant"]
    assert data["volume"] == 42 and data["first_run"] is False
    odlozene = _odlozene(prostredie)
    assert len(odlozene) == 1
    # RRRRmmdd-HHMMSS
    znacka = odlozene[0].rsplit(".corrupt-", 1)[1]
    assert len(znacka) == 15 and znacka[8] == "-" and znacka.replace("-", "").isdigit()
    with open(os.path.join(os.path.dirname(prostredie), odlozene[0]), encoding="utf-8") as fh:
        assert "Valo" in fh.read(), "pokazeny obsah sa da zachranit"
    assert obnova == {"odlozene": odlozene[0], "zo_zalohy": True}
    # zaloha je hned spat na mieste - pad pred prvym ulozenim nevyvola prvy start
    with open(prostredie, encoding="utf-8") as fh:
        assert json.load(fh)["profiles"][0]["name"] == "Valorant"


def test_bez_zalohy_predvolene_a_povie_to(prostredie):
    with open(prostredie, "w", encoding="utf-8") as fh:
        fh.write("\x00\x00 to nie je json")
    data, obnova = _nacitaj()
    assert data["first_run"] is True
    assert obnova is not None and obnova["zo_zalohy"] is False
    assert obnova["odlozene"] == _odlozene(prostredie)[0]
    assert not os.path.exists(prostredie), "pokazeny je odlozeny, nie prepisany"


def test_platny_subor_nic_neodklada(prostredie):
    _zapis(prostredie, _platne())
    _data, obnova = _nacitaj()
    assert obnova is None
    assert _odlozene(prostredie) == []


def test_oznam_raz_do_dennika_a_sprava_az_po_starte(monkeypatch):
    import app as app_mod
    import app_prefs
    zobrazene, planovane = [], []
    monkeypatch.setattr(app_prefs.messagebox, "showwarning",
                        lambda titul, text: zobrazene.append(text))
    denn = []
    a = types.SimpleNamespace(
        _nastavenia_obnova={"odlozene": "dandurf_settings.json.corrupt-20261114-213000",
                            "zo_zalohy": True},
        log=denn.append,
        root=types.SimpleNamespace(after=lambda ms, fn: planovane.append((ms, fn))))
    app_mod.DandurfApp._oznam_obnovu_nastaveni(a)
    assert len(denn) == 1
    assert "dandurf_settings.json.corrupt-20261114-213000" in denn[0]
    assert zobrazene == [], "sprava az ked okno stoji, nie pocas startu"
    (ms, fn), = planovane
    assert ms > 0
    fn()
    assert zobrazene == denn
    # druhe volanie uz nic nepovie
    app_mod.DandurfApp._oznam_obnovu_nastaveni(a)
    assert len(denn) == 1 and len(planovane) == 1


def test_oznam_sa_vola_po_postaveni_okna():
    init = zdroj_metody("__init__")
    assert init.index("self._build_ui()") < init.index("self._oznam_obnovu_nastaveni()")


def test_texty_obnovy_nastaveni_vo_vsetkych_jazykoch():
    for kluc in ("log.settings_restored_backup", "log.settings_restored_defaults"):
        for jazyk in i18n.LANGUAGES:
            assert "{name}" in i18n.STRINGS[kluc][jazyk], (kluc, jazyk)
    sk = i18n.tr_lang("sk", "log.settings_restored_backup", name="X")
    assert sk == ("Nastavenia sa nedali načítať. Pôvodný súbor som odložila ako X "
                  "a obnovila som poslednú zálohu.")
    assert "začínam s predvolenými" in i18n.tr_lang(
        "sk", "log.settings_restored_defaults", name="X")


def test_gitignore_kryje_zalohu_aj_odlozeny_subor():
    vzory = [r.strip() for r in zdroj_suboru(".gitignore").splitlines()
             if r.strip() and not r.startswith("#")]
    for meno in ("dandurf_settings.json.bak", "dandurf_settings.json.bak.tmp",
                 "dandurf_settings.json.corrupt-20261114-213000"):
        assert any(fnmatch.fnmatch(meno, v) for v in vzory), meno
