# -*- coding: utf-8 -*-
"""Zdroje v appke, ZDROJE.md a SOUL.md (0.2, sources-soul).

Rozhodnutia autora, ktoré tieto testy strážia:
  * v appke sú len TRI zdroje - presne tie, ktoré karty Sprievodcu citujú
    „v zdrojoch nižšie“ - pod jeho textom „Ako to vzniklo“ (`origin.*`),
    v Sprievodcovi aj v Histórii rovnako; každá citácia v kartách sa medzi
    nimi dá nájsť (priezvisko + rok),
  * celý zoznam je v ZDROJE.md - aj všetko, čo bolo v appke do 0.2,
  * veta „asi každá desiata hláška zámerne mlčí“ sedí s tichým ramenom,
  * SOUL.md ide von: v repozitári, odkaz na konci README a v inštalátore
    vedľa licencie.
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

# Čo appka ukazovala do 0.2 (guide_content.PHILOSOPHY_SOURCES pred
# sources-soul). Z appky odišlo, z ZDROJE.md nesmie.
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

# Ako karty Sprievodcu odkazujú na zdroj - v každom jazyku (jazyková fáza
# 0.2). Japončina a čínština píšu zátvorky a čiarku v plnej šírke.
_CITACIA = {"sk": "v zdrojoch nižšie", "en": "in the sources below",
            "ja": "下の出典を参照", "zh": "见下方参考来源",
            "ru": "в источниках ниже", "es": "en las fuentes de abajo",
            "de": "in den Quellen unten", "fr": "dans les sources ci-dessous",
            "pt": "nas fontes abaixo", "cs": "ve zdrojích níže",
            "bg": "в източниците по-долу"}


def _read(nazov):
    # utf-8-sig: Dandurf.iss má BOM
    with open(os.path.join(ROOT, nazov), encoding="utf-8-sig") as fh:
        return fh.read()


def _autor_rok(popisok):
    """„… (Lehrer & Gevirtz, 2014)“ -> ("Lehrer", "2014"); aj （…） v ja/zh."""
    m = re.search(r"[(（](\w[\w-]*)[^()（）]*?(\d{4})[)）]\s*$", popisok)
    assert m, f"popisok zdroja nekončí (Autor …, rok): {popisok!r}"
    return m.group(1), m.group(2)


def test_v_appke_su_len_tri_zdroje():
    kluce = [k for k, _ in guide_content.PHILOSOPHY_SOURCES]
    assert kluce == ["guide.philosophy.source12", "guide.philosophy.source11",
                     "guide.philosophy.source10"]
    assert len(guide_content.origin_sources()) == 3
    # Ostatné popisky zmizli aj z i18n (aj s _tr7) - nikto ich zbytočne
    # neprekladá a sedem jazykov už nemá popisok k inému odkazu.
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
            assert len(citacie) >= 3, jazyk      # poistka proti prázdnemu testu
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
    # ostatné karty nič z toho nemajú
    for c in guide_content.guide_cards():
        if c["id"] != "philosophy":
            assert c["sources"] is None and c["sources_note"] is None, c["id"]


def test_historia_ukazuje_to_iste():
    """app.py sa v testoch importovať nedá - kontrola zdrojáku panela."""
    src = zdroj_appky()
    # panel je koniec `_build_historia_page` (za nim ide `_toggle_history_science`)
    blok = zdroj_metody("_build_historia_page")
    blok = blok[blok.index("self.history_science_body = "):]
    for kluc in ("origin.text", "origin.examples", "origin.full_list"):
        assert f'tr("{kluc}")' in blok, kluc
    assert "origin_sources()" in blok
    assert "heart_rate_sources" not in src and "history.science_" not in src


def test_veta_o_kazdej_desiatej_sedi_s_tichym_ramenom():
    """Text autora: „na začiatku asi každá štvrtá, neskôr každá desiata hláška
    zámerne mlčí“ (autor schválil 24. 9.). Na začiatku je tiché rameno
    štvrtina, po zábehu 10 %; ak sa jedno z nich zmení, veta klame."""
    assert "na začiatku asi každá štvrtá, neskôr každá desiata hláška zámerne mlčí" in i18n.STRINGS["origin.text"]["sk"]
    assert "at first roughly one cue in four, later one in ten, stays silent" in i18n.STRINGS["origin.text"]["en"]
    assert trigger.silent_share_for(0) == 0.25
    assert trigger.silent_share_for(10_000) == 0.10


def test_en_hranice_su_prahy_nie_limity_nastroja():
    """„Hranice si appka počíta z tvojich vlastných relácií“ sú prahy záťaže
    (EN inde „threshold“). „its limits“ by v karte s nadpisom „the tool’s
    limits“ znelo ako „appka si ráta, čo nevie“."""
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
    # LICENSE-DESIGN.md a ZDROJE.md od 24. 9. (rozhodnutie autora)
    for nazov in ("LICENSE", "SOUL.md", "LICENSE-DESIGN.md", "ZDROJE.md"):
        assert re.search(r'^Source: "' + re.escape(nazov) + r'"; DestDir: "\{app\}"',
                         files, re.M), nazov
        assert os.path.isfile(os.path.join(ROOT, nazov)), nazov
