# -*- coding: utf-8 -*-
"""Zvoleny jazyk musi prezit restart appky - vsetkych jedenast, nie tri.

Pozadie chyby: `DandurfApp.load_settings()` porovnavala ulozeny jazyk voci
rucne prepisanej trojici `(LANG_SK, LANG_EN, LANG_JA)` z cias, ked appka
vedela tri jazyky. Prepinac v Nastaveniach ich medzitym ponukal devat a
volbu korektne ulozil, ale tento filter ju pri dalsom starte zahodil a
spadol na slovencinu. A kedze `__init__` hned po starte vola
`save_settings()`, zdegradovana hodnota sa zapisala SPAT do
dandurf_settings.json - volba hraca bola nenavratne prec.

Overene naostro pred opravou: zh, ru, es, de, fr, pt sa stratili vsetky.

Testy su staticke (citaju zdrojak), aby bezali aj bez Tk - realny beh
appky pre vsetky jazyky je v manualnom harnesse.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402
from _zdroj_appky import zdroj_appky, zdroj_metody  # noqa: E402


def test_i18n_pozna_jedenast_jazykov():
    """Poistka pre zvysok suboru: ak jazyk pribudne/ubudne, uprav aj testy."""
    assert len(i18n.LANGUAGES) == 11, (
        f"i18n.LANGUAGES ma {len(i18n.LANGUAGES)} jazykov, cakalo sa 11")
    for code in ("sk", "en", "ja", "zh", "ru", "es", "de", "fr", "pt", "cs", "bg"):
        assert code in i18n.LANGUAGES


def test_kazdy_ponukany_jazyk_ma_preklady():
    """Prepinac nesmie ponukat jazyk, pre ktory appka nema retazce."""
    src = zdroj_appky()
    block = src[src.index("LANG_NATIVE_LABELS = {"):]
    block = block[:block.index("}")]
    ponukane = set(re.findall(r"LANG_([A-Z]{2}):", block))
    kody = {name.split("_")[1].lower() for name in ("LANG_" + s for s in ponukane)}
    assert kody == set(i18n.LANGUAGES), (
        f"prepinac ponuka {sorted(kody)}, i18n pozna {sorted(i18n.LANGUAGES)}")


def test_load_settings_neobmedzuje_jazyk_na_rucny_zoznam():
    """Jadro regresie: filter musi ist voci LANGUAGES, nie voci trojici.

    Rucne vypisany zoznam konstant je presne to, co sa raz uz rozislo s
    realitou a ticho zahadzovalo volbu hraca.
    """
    blok = zdroj_metody("load_settings")[:2000]

    assert 'loaded.get("lang") in LANGUAGES' in blok, (
        "load_settings musi porovnavat ulozeny jazyk voci i18n.LANGUAGES")

    # ziadny rucne vypisany zoznam jazykovych konstant v tej istej podmienke
    rucny = re.search(r'loaded\.get\("lang"\)\s+in\s+\(\s*LANG_', blok)
    assert rucny is None, (
        "load_settings znova porovnava jazyk voci rucne vypisanej n-tici "
        "LANG_* - taky zoznam zastara a ticho zahodi volbu hraca")


def test_ulozeny_jazyk_sa_zapisuje_spat():
    """save_settings musi ukladat self.lang (inak by sa volba nedrzala)."""
    blok = zdroj_metody("save_settings")[:2000]
    assert '"lang": self.lang' in blok
