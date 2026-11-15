# -*- coding: utf-8 -*-
"""The chosen language must survive an app restart - all eleven, not three.

Background of the bug: `DandurfApp.load_settings()` compared the saved
language against a hand-written triple `(LANG_SK, LANG_EN, LANG_JA)` from
the days when the app knew three languages. The switch in Settings
offered nine of them in the meantime and saved the choice correctly, but
this filter threw it away on the next start and fell back to Slovak. And
since `__init__` calls `save_settings()` right after start, the degraded
value was written BACK to dandurf_settings.json - the player's choice was
gone for good.

Verified for real before the fix: zh, ru, es, de, fr, pt were all lost.

The tests are static (they read the source), so they run even without Tk
- a real run of the app for all languages is in the manual harness.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402
from _zdroj_appky import zdroj_appky, zdroj_metody  # noqa: E402


def test_i18n_pozna_jedenast_jazykov():
    """Guard for this file: add/remove a language, update the tests too."""
    assert len(i18n.LANGUAGES) == 11, (
        f"i18n.LANGUAGES ma {len(i18n.LANGUAGES)} jazykov, cakalo sa 11")
    for code in ("sk", "en", "ja", "zh", "ru", "es", "de", "fr", "pt", "cs", "bg"):
        assert code in i18n.LANGUAGES


def test_kazdy_ponukany_jazyk_ma_preklady():
    """The switch must not offer a language the app has no strings for."""
    src = zdroj_appky()
    block = src[src.index("LANG_NATIVE_LABELS = {"):]
    block = block[:block.index("}")]
    ponukane = set(re.findall(r"LANG_([A-Z]{2}):", block))
    kody = {name.split("_")[1].lower() for name in ("LANG_" + s for s in ponukane)}
    assert kody == set(i18n.LANGUAGES), (
        f"prepinac ponuka {sorted(kody)}, i18n pozna {sorted(i18n.LANGUAGES)}")


def test_load_settings_neobmedzuje_jazyk_na_rucny_zoznam():
    """The core of the regression: the filter must check against LANGUAGES,
    not against the triple.

    A hand-written list of constants is exactly what once already drifted
    apart from reality and silently threw away the player's choice.
    """
    blok = zdroj_metody("load_settings")[:2000]

    assert 'loaded.get("lang") in LANGUAGES' in blok, (
        "load_settings musi porovnavat ulozeny jazyk voci i18n.LANGUAGES")

    # no hand-written list of language constants in the same condition
    rucny = re.search(r'loaded\.get\("lang"\)\s+in\s+\(\s*LANG_', blok)
    assert rucny is None, (
        "load_settings znova porovnava jazyk voci rucne vypisanej n-tici "
        "LANG_* - taky zoznam zastara a ticho zahodi volbu hraca")


def test_ulozeny_jazyk_sa_zapisuje_spat():
    """save_settings must save self.lang (or the choice would not stick)."""
    blok = zdroj_metody("save_settings")[:2000]
    assert '"lang": self.lang' in blok
