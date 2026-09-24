# -*- coding: utf-8 -*-
"""Appka o sebe hovorí v ženskom rode (0.2, final integration).

„Ozvala som sa“, „sama sa neozvem“, „radšej som mlčala“ - tak znie appka v
slovenčine. Pri záverečnej kontrole vetvy 0.2 sa našlo „tú hranicu som si
spočítal“ (`cue_rate.computed`, text zmenený v B3-worlds) - mužský rod v
ústach appky. Tento test chytí ďalší taký prípad v ktoromkoľvek SK texte.

Mužský rod je v poriadku tam, kde NEHOVORÍ appka: text autora („Ako to
vzniklo“, „O appke“), hráč o sebe v dotazníku po relácii („jedol som“,
„Hral som“) a tep („tep klesá aj sám“). Staršie texty spred 0.2 s mužským
rodom appky („Ukončil som test vizuálu“, „Odstup som zdvihol“, „{app}
pripravený“) sú vo fáze jazykov opravené; zoznam známeho dlhu je prázdny.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402

# „<sloveso>l som“ / „som (sa|si) <sloveso>l“ - minulý čas v mužskom rode.
_MUZSKY_MINULY = re.compile(
    r"\b(\w+l)\s+som\b|\bsom\s+(?:sa\s+|si\s+)?(\w+l)\b", re.IGNORECASE)
_SAM = re.compile(r"\bsám\b", re.IGNORECASE)
# Slová na -l, ktoré nie sú sloveso („som naschvál mlčala“).
_NIE_SLOVESO = {"naschvál"}

# Nehovorí appka.
_NIE_APPKA = {
    "origin.text",        # autor: „Postavil som ho pomocou AI“
    "about.body",         # autor: príbeh vzniku
    "history.effect_hint",  # „tep klesá aj sám“ - o tepe
}
_NIE_APPKA_PREFIX = ("session.context.",)   # hráč o sebe v dotazníku

# Staršie texty s mužským rodom appky - ZNÁMY DLH na neskôr, nie výnimka
# pre nové texty. Keď sa opravia, vyhoď ich odtiaľto. Vo fáze jazykov 0.2
# splatený celý („Ukončila som test vizuálu“, „Odstup som zdvihla“).
_ZNAMY_DLH = set()


def _muzsky_rod(text):
    for m in _MUZSKY_MINULY.finditer(text):
        slovo = (m.group(1) or m.group(2) or "").lower()
        if slovo not in _NIE_SLOVESO:
            return m.group(0)
    m = _SAM.search(text)
    return m.group(0) if m else None


def test_appka_o_sebe_hovori_v_zenskom_rode():
    zle = {}
    for kluc, zaznam in i18n.STRINGS.items():
        if kluc in _NIE_APPKA or kluc in _ZNAMY_DLH:
            continue
        if kluc.startswith(_NIE_APPKA_PREFIX):
            continue
        najdene = _muzsky_rod(zaznam.get("sk") or "")
        if najdene:
            zle[kluc] = najdene
    assert not zle, zle


def test_hranicu_si_appka_spocitala():
    sk = i18n.STRINGS["cue_rate.computed"]["sk"]
    assert "som si spočítala" in sk
    assert "spočítal " not in sk


def test_znamy_dlh_je_stale_aktualny():
    """Keď sa starý text opraví, nech zmizne aj zo zoznamu dlhu - inak by
    zoznam potichu kryl nový mužský rod pod starým kľúčom."""
    for kluc in _ZNAMY_DLH:
        assert _muzsky_rod(i18n.STRINGS[kluc]["sk"]), kluc


def test_zenske_tvary_appky_ostali():
    """Pár viet, v ktorých appka hovorí o sebe - nech ostanú v ženskom rode."""
    for kluc, tvar in (("session.end.none_withheld", "som mlčala"),
                       ("session.end.cues_visual", "Ozvala som sa"),
                       ("dnes.nonstop_input", "som nezachytila"),
                       ("history.rebrik.why.missed", "som sa mala ozvať"),
                       ("kamae.lost_sub", "sama sa neozvem"),
                       ("session.zanshin.body", "som ti bola plťou"),
                       # opravené vo fáze jazykov 0.2 (predtým mužský rod)
                       ("log.overlay_test_ukonceny", "Ukončila som"),
                       ("dev.min_gap_clamped", "som zdvihla"),
                       ("log.vizualy_napravene", "Zapla som"),
                       ("kamae.stopped_sub_auto", "spustím sama"),
                       ("log.ready", "Som pripravená")):
        assert tvar in i18n.STRINGS[kluc]["sk"], kluc


def test_appka_nie_je_pripraveny():
    """Prídavné meno v mužskom rode test vyššie nechytí (nie je to sloveso
    na -l) - „{app} pripravený“ bol v logu od začiatku. Appka je
    pripravená, nie pripravený."""
    zle = {kluc: zaznam["sk"] for kluc, zaznam in i18n.STRINGS.items()
           if kluc not in _NIE_APPKA
           and not kluc.startswith(_NIE_APPKA_PREFIX)
           and re.search(r"\bsom\s+pripravený\b|\{app\}\s+pripravený\b",
                         zaznam.get("sk") or "", re.IGNORECASE)}
    assert not zle, zle
