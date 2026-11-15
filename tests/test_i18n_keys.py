"""Every static key the app passes to `tr()` must exist in i18n.

Why this exists: `tr()` does not crash on an unknown key - it returns the
key itself. The window then shows literally "history.days" instead of the
text and nothing reports it. That is exactly what happened: a key was
renamed in i18n and the call in app.py stayed. The static check catches it
earlier than the GUI.

Dynamic keys (f-strings like tr(f"metric.{id}.title")) do not get in here
- those are guarded by `check_translations.py` and manual checking.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import i18n
from _zdroj_appky import subory_appky

PROJ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# tr("key") or tr('key') - f-strings deliberately do not belong here
_VOLANIE = re.compile(r"""\btr\(\s*(['"])([A-Za-z0-9_.]+)\1""")

# Files that build the UI. Not the harness and the tests - those may
# experiment.
# App = app.py and the DandurfApp mixins in app_*.py.
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
    """A safeguard against the test passing only because the regex found
    nothing (e.g. after renaming `tr`)."""
    assert sum(len(_kluce(meno)) for meno in subory_appky()) > 100


def test_appka_ma_jedenast_jazykov():
    """sk, en, 7 Steam player languages and, since 0.2, Czech and Bulgarian."""
    assert i18n.LANGUAGES == ("sk", "en", "ja", "zh", "ru", "es", "de", "fr",
                              "pt", "cs", "bg")


def test_kazdy_kluc_ma_vsetkych_jedenast_jazykov():
    chybne = [kluc for kluc, preklady in i18n.STRINGS.items()
              if set(preklady) != set(i18n.LANGUAGES)]
    assert not chybne, f"kluce s neuplnou sadou jazykov: {chybne[:10]}"


def test_kazda_karta_na_dnes_ma_vsetky_tri_texty():
    """A stats card needs `tag`, `more` and `title`.

    `metric.over.more` was missing - and "Over the limit" is one of the
    FOUR default cards on the main page. A click on the question mark thus
    showed the raw translation key 'metric.over.more'. `tr()` returns a
    missing key as it got it: it does not crash, it just looks like a
    broken app.
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
    """“…“ instead of “…” (a typo in hr.pair_ip_help and overlay.drag_hint)."""
    otv, zatv = "“", "”"
    zle = [k for k, v in i18n.STRINGS.items()
           if re.search(otv + "[^" + otv + zatv + "]*" + otv, v.get("en", ""))
           or v.get("en", "").count(otv) != v.get("en", "").count(zatv)]
    assert not zle, zle
    assert "“IPv4 Address”" in i18n.STRINGS["hr.pair_ip_help"]["en"]
