"""Kazdy staticky kluc, ktory appka posle do `tr()`, musi v i18n existovat.

Preco to je: `tr()` pri neznamom kluci nepadne - vrati sam kluc. V okne sa
potom objavi doslova "history.days" namiesto textu a nic to nenahlasi.
Prave tak sa to aj stalo: kluc sa premenoval v i18n a volanie v app.py
ostalo. Staticka kontrola to chyti skor nez GUI.

Dynamicke kluce (f-stringy typu tr(f"metric.{id}.title")) sa sem
nedostanu - tie strazi `check_translations.py` a rucne overenie.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import i18n
from _zdroj_appky import subory_appky

PROJ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# tr("kluc") alebo tr('kluc') - f-stringy sem zamerne nepatria
_VOLANIE = re.compile(r"""\btr\(\s*(['"])([A-Za-z0-9_.]+)\1""")

# Subory, ktore stavaju rozhranie. Harness a testy nie - tie smu experimentovat.
# Appka = app.py aj mixiny DandurfApp v app_*.py.
_MODULY = (*subory_appky(), "ui_kit.py", "ui_shell.py", "ui_dialogs.py",
           "guide_panel.py", "guide_content.py", "guided_tour.py", "hud.py",
           "overlay.py", "settings_model.py", "main.py")


def _kluce(nazov):
    cesta = os.path.join(PROJ, nazov)
    if not os.path.exists(cesta):
        return []
    with open(cesta, encoding="utf-8") as fh:
        src = fh.read()
    return [(m.group(2), src[:m.start()].count("\n") + 1)
            for m in _VOLANIE.finditer(src)]


def test_vsetky_staticke_kluce_existuju():
    chybaju = []
    for modul in _MODULY:
        for kluc, riadok in _kluce(modul):
            if kluc not in i18n.STRINGS:
                chybaju.append(f"{modul}:{riadok} -> {kluc}")
    assert not chybaju, "kluce, ktore v i18n nie su:\n  " + "\n  ".join(chybaju)


def test_kontrola_naozaj_nieco_najde():
    """Poistka proti tomu, aby test prechadzal len preto, ze regex nic
    nenasiel (napr. po premenovani `tr`)."""
    assert sum(len(_kluce(meno)) for meno in subory_appky()) > 100


def test_appka_ma_jedenast_jazykov():
    """sk, en, 7 jazykov hracov na Steame a od 0.2 cestina a bulharcina."""
    assert i18n.LANGUAGES == ("sk", "en", "ja", "zh", "ru", "es", "de", "fr",
                              "pt", "cs", "bg")


def test_kazdy_kluc_ma_vsetkych_jedenast_jazykov():
    chybne = [kluc for kluc, preklady in i18n.STRINGS.items()
              if set(preklady) != set(i18n.LANGUAGES)]
    assert not chybne, f"kluce s neuplnou sadou jazykov: {chybne[:10]}"


def test_kazda_karta_na_dnes_ma_vsetky_tri_texty():
    """Karta statistiky potrebuje `tag`, `more` aj `title`.

    `metric.over.more` chybal - a "nad hranicou" je jedna zo STYROCH
    predvolenych kariet na hlavnej stranke. Klik na otaznik teda ukazal
    surovy prekladovy kluc 'metric.over.more'. `tr()` chybajuci kluc vracia
    tak, ako ho dostal: nespadne, len to vyzera ako rozbita appka.
    """
    import settings_model
    chyba = []
    for stat_id in settings_model.DASHBOARD_STAT_IDS:
        for cast in ("tag", "more", "title"):
            kluc = f"metric.{stat_id}.{cast}"
            if kluc not in i18n.STRINGS:
                chyba.append(kluc)
    assert not chyba, "chybajuce texty kariet: " + ", ".join(chyba)


def test_anglicke_uvodzovky_su_v_paroch():
    """“…“ namiesto “…” (preklep v hr.pair_ip_help a overlay.drag_hint)."""
    otv, zatv = "“", "”"
    zle = [k for k, v in i18n.STRINGS.items()
           if re.search(otv + "[^" + otv + zatv + "]*" + otv, v.get("en", ""))
           or v.get("en", "").count(otv) != v.get("en", "").count(zatv)]
    assert not zle, zle
    assert "“IPv4 Address”" in i18n.STRINGS["hr.pair_ip_help"]["en"]
