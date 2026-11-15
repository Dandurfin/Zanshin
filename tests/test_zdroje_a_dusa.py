# -*- coding: utf-8 -*-
"""Sources in the app, ZDROJE.md and SOUL.md (0.2, sources-soul).

The author's decisions these tests guard:
  * there are only THREE sources in the app - exactly the ones the Guide
    cards cite "in the sources below" - under his text "How it came about"
    (`origin.*`), the same in the Guide and in History; every citation in
    the cards can be found among them (surname + year),
  * the full list is in ZDROJE.md - including everything that was in the
    app up to 0.2,
  * the sentence "about every tenth cue is silent on purpose" matches the
    silent arm,
  * SOUL.md goes out: in the repository, a link at the end of the README
    and in the installer next to the licence.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import guide_content  # noqa: E402
import i18n  # noqa: E402
import trigger  # noqa: E402
from _zdroj_appky import zdroj_appky, zdroj_metody  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")

# What the app showed up to 0.2 (guide_content.PHILOSOPHY_SOURCES before
# sources-soul). It left the app, it must not leave ZDROJE.md.
_BYVALE_URL = (
    "https://doi.org/10.3389/fnhum.2018.00353",
    "https://doi.org/10.3389/fpsyg.2014.00756",
    "https://doi.org/10.1017/S0033291717001003",
    "https://doi.org/10.1001/jamainternmed.2013.13018",
    "https://doi.org/10.1007/s10484-015-9293-x",
    "https://doi.org/10.1177/0956797610371339",
    "https://doi.org/10.1016/j.tics.2008.01.005",
    "https://ieeexplore.ieee.org/document/8319498/",
    "https://dl.acm.org/doi/10.1145/3706599.3720103",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC7272664/",
    "https://pubmed.ncbi.nlm.nih.gov/38638448/",
    "https://doi.org/10.1080/1750984X.2020.1723122",
    "https://doi.org/10.1056/NEJM199910283411804",
    "https://doi.org/10.30773/pi.2017.08.17",
    "https://doi.org/10.1016/j.jpsychores.2005.06.074",
)

# How the Guide cards refer to a source - in every language (languages
# phase 0.2). Japanese and Chinese write brackets and the comma in full
# width.
_CITACIA = {"sk": "v zdrojoch nižšie", "en": "in the sources below",
            "ja": "下の出典を参照", "zh": "见下方参考来源",
            "ru": "в источниках ниже", "es": "en las fuentes de abajo",
            "de": "in den Quellen unten", "fr": "dans les sources ci-dessous",
            "pt": "nas fontes abaixo", "cs": "ve zdrojích níže",
            "bg": "в източниците по-долу"}


def _read(nazov):
    # utf-8-sig: Dandurf.iss has a BOM
    with open(os.path.join(ROOT, nazov), encoding="utf-8-sig") as fh:
        return fh.read()


def _autor_rok(popisok):
    """„… (Lehrer & Gevirtz, 2014)“ -> ("Lehrer", "2014"); ja/zh: （…） too."""
    m = re.search(r"[(（](\w[\w-]*)[^()（）]*?(\d{4})[)）]\s*$", popisok)
    assert m, f"popisok zdroja nekončí (Autor …, rok): {popisok!r}"
    return m.group(1), m.group(2)


def test_v_appke_su_len_tri_zdroje():
    kluce = [k for k, _ in guide_content.PHILOSOPHY_SOURCES]
    assert kluce == ["guide.philosophy.source12", "guide.philosophy.source11",
                     "guide.philosophy.source10"]
    assert len(guide_content.origin_sources()) == 3
    # The other labels vanished from i18n too (with _tr7) - nobody translates
    # them needlessly and seven languages no longer have a label for a
    # different link.
    zvysne = sorted(k for k in i18n.STRINGS
                    if k.startswith("guide.philosophy.source")
                    and k != "guide.philosophy.sources_title")
    assert zvysne == sorted(kluce)
    assert not [k for k in i18n.STRINGS if k.startswith("history.science_")]


def test_kazda_citacia_v_kartach_sa_da_najst_v_zdrojoch():
    for jazyk in i18n.LANGUAGES:
        fraza = _CITACIA[jazyk]
        zdroje = {_autor_rok(i18n.STRINGS[k][jazyk])
                  for k, _ in guide_content.PHILOSOPHY_SOURCES}
        citacie = [(kluc, zaznam[jazyk]) for kluc, zaznam in i18n.STRINGS.items()
                   if fraza in zaznam[jazyk]]
        if jazyk in _CITACIA:
            assert len(citacie) >= 3, jazyk      # safeguard against an empty test
        pouzite = set()
        for kluc, text in citacie:
            for m in re.finditer(r"[(（]([^()（）]*?)[,，、]\s*" + re.escape(fraza)
                                 + r"[)）]", text):
                najdene = {(a, r) for a, r in zdroje
                           if a in m.group(1) and r in m.group(1)}
                assert najdene, (f"{kluc}[{jazyk}]: „{m.group(1)}“ nie je medzi "
                                 f"zdrojmi v appke {sorted(zdroje)}")
                pouzite |= najdene
        if citacie:
            assert pouzite == zdroje, f"{jazyk}: necitovaný zdroj {zdroje - pouzite}"


def test_sprievodca_ukazuje_text_autora_a_tie_iste_tri_zdroje():
    karta = next(c for c in guide_content.guide_cards() if c["id"] == "philosophy")
    assert [(s["label"], s["url"]) for s in karta["sources"]] == \
        guide_content.origin_sources()
    assert karta["custom_blocks"][-1] == {"title": i18n.tr("origin.title"),
                                          "text": i18n.tr("origin.text")}
    assert karta["sources_intro"] == i18n.tr("origin.examples")
    assert karta["sources_note"] == i18n.tr("origin.full_list")
    # the other cards have none of this
    for c in guide_content.guide_cards():
        if c["id"] != "philosophy":
            assert c["sources"] is None and c["sources_note"] is None, c["id"]


def test_historia_ukazuje_to_iste():
    """app.py cannot be imported in tests - a check of the panel's source."""
    src = zdroj_appky()
    # the panel is the end of `_build_historia_page` (followed by
    # `_toggle_history_science`)
    blok = zdroj_metody("_build_historia_page")
    blok = blok[blok.index("self.history_science_body = "):]
    for kluc in ("origin.text", "origin.examples", "origin.full_list"):
        assert f'tr("{kluc}")' in blok, kluc
    assert "origin_sources()" in blok
    assert "heart_rate_sources" not in src and "history.science_" not in src


def test_veta_o_kazdej_desiatej_sedi_s_tichym_ramenom():
    """The author's text: „na začiatku asi každá štvrtá, neskôr každá desiata
    hláška zámerne mlčí“ (at first about every fourth, later every tenth
    cue is silent on purpose; the author approved it 24. 9.). At first the
    silent arm is a quarter, after the run-in 10 %; if one of them
    changes, the sentence lies."""
    assert "na začiatku asi každá štvrtá, neskôr každá desiata pripomienka zámerne mlčí" in i18n.STRINGS["origin.text"]["sk"]
    assert "at first roughly one cue in four, later one in ten, stays silent" in i18n.STRINGS["origin.text"]["en"]
    assert trigger.silent_share_for(0) == 0.25
    assert trigger.silent_share_for(10_000) == 0.10


def test_en_hranice_su_prahy_nie_limity_nastroja():
    """„Hranice si appka počíta z tvojich vlastných relácií“ (the app computes
    its limits from your own sessions) are load thresholds (EN elsewhere
    "threshold"). "its limits" would, in a card headed "the tool’s
    limits", sound like "the app works out what it cannot do"."""
    en = i18n.STRINGS["origin.text"]["en"]
    assert "works out its thresholds from your own sessions" in en
    assert "its limits" not in en


def test_zdroje_md_ma_vsetko_co_bolo_v_appke():
    text = _read("ZDROJE.md")
    assert text.startswith("# Zdroje")
    for url in _BYVALE_URL + tuple(u for _, u in guide_content.PHILOSOPHY_SOURCES):
        assert url in text, url
    for jazyk in ("sk", "en"):
        assert "ZDROJE.md" in i18n.STRINGS["origin.full_list"][jazyk]


def test_soul_md_je_v_repozitari_a_na_konci_readme():
    assert _read("SOUL.md").startswith("# Zanshin — the soul behind the app")
    posledny = _read("README.md").rstrip().splitlines()[-1]
    assert "[Soul of the app](SOUL.md)" in posledny


def test_instalator_nesie_licenciu_aj_dusu():
    iss = _read("Dandurf.iss")
    files = iss[iss.index("\n[Files]"):]
    files = files[:files.index("\n[", 1)]
    # LICENSE-DESIGN.md and ZDROJE.md since 24. 9. (the author's decision)
    for nazov in ("LICENSE", "SOUL.md", "LICENSE-DESIGN.md", "ZDROJE.md"):
        assert re.search(r'^Source: "' + re.escape(nazov) + r'"; DestDir: "\{app\}"',
                         files, re.M), nazov
        assert os.path.isfile(os.path.join(ROOT, nazov)), nazov
