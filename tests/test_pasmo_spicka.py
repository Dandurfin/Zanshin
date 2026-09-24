# -*- coding: utf-8 -*-
"""Najvyššie pásmo tepu sa volá „Špička“ / „Peak“, nie „Kritická“ (0.2).

Pásmo znamená len „tep nad tvojou vlastnou hranicou vysokého tepu“ - nič
zdravotné ani poplašné. „Kritická“, „Critical“, 危険域 („nebezpečná zóna“)
zneli ako diagnóza. Interný kľúč `critical` (hr_stats, trigger, HUD, CSV)
ostáva; mení sa len to, čo hráč číta.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import hr_stats  # noqa: E402
import i18n  # noqa: E402
import trigger  # noqa: E402

NOVE_MENO = {"sk": "Špička", "en": "Peak", "ja": "ピーク", "zh": "高峰",
             "ru": "Пик", "es": "Pico", "de": "Spitze", "fr": "Pic",
             "pt": "Pico", "cs": "Špička", "bg": "Връх"}

# Staré mená pásma aj vety, ktoré ho menovali, vo všetkých jazykoch.
STARE = re.compile(
    r"Kritick|kritick|Critical|critical zone|危険域|临界|Критическ|критическ"
    r"|Критичн|критичн|Crítica|zona crítica|Kritisch|kritischen Zone"
    r"|Critique|zone critique")


def test_meno_pasma_vo_vsetkych_jazykoch():
    for kluc in ("hud.zone.critical", "metric.zones.critical"):
        zaznam = i18n.STRINGS[kluc]
        assert set(zaznam) == set(i18n.LANGUAGES), kluc
        for jazyk, meno in NOVE_MENO.items():
            # legenda pásiem píše malým (okrem nemčiny, kde je to podstatné meno)
            assert zaznam[jazyk].lower() == meno.lower(), (kluc, jazyk)
    stlpec = i18n.STRINGS["history.export_col.critical_min"]
    for jazyk, meno in NOVE_MENO.items():
        assert stlpec[jazyk].startswith(meno), jazyk


def test_ziadny_text_uz_nemenuje_pasmo_po_starom():
    najdene = [(k, j) for k, v in i18n.STRINGS.items()
               for j in i18n.LANGUAGES if STARE.search(str(v.get(j, "")))]
    assert not najdene, najdene


def test_vety_o_mlcani_menuju_nove_pasmo():
    """Každá veta, ktorá hovorí „v najvyššom pásme appka mlčí“, menuje to
    isté slovo, aké hráč vidí v HUD."""
    for kluc in ("slots.hint", "tour.triggers.body", "ob.step1.how",
                 "session.end.none_withheld"):
        z = i18n.STRINGS[kluc]
        assert "pásme Špička" in z["sk"], kluc
        assert "peak zone" in z["en"], kluc
        assert "pásmu Špička" in z["cs"], kluc
    viac = i18n.STRINGS["metric.load.more"]
    for jazyk, meno in NOVE_MENO.items():
        assert viac[jazyk].count(meno) >= 2, jazyk


def test_interny_kluc_ostal():
    assert hr_stats.ZONE_CRITICAL == "critical"
    assert trigger.ZONA_KRITICKA == "critical"


def test_karta_spicky_zataze_sa_s_pasmom_nebije():
    """Karta „Špička záťaže“ (0-100) nie je pásmo tepu - jej popisok pod
    číslom už nesmie byť to isté slovo ako pásmo."""
    tag = i18n.STRINGS["metric.peak.tag"]
    pasmo = i18n.STRINGS["metric.zones.critical"]
    for jazyk in i18n.LANGUAGES:
        assert tag[jazyk].lower() != pasmo[jazyk].lower(), jazyk
        # Popisok pod číslom má v karte ~117 px (stĺpec 300 px, dve karty);
        # dlhší by roztiahol stĺpec na úkor stredu (viz ui_kit.StatCard).
        assert len(tag[jazyk]) <= 14, (jazyk, tag[jazyk])
    assert tag["sk"] == "špička záťaže" and tag["en"] == "peak load"


def test_najvyssi_tep_a_telo_v_exporte_nevyzeraju_ako_pasmo():
    """Karta Najvyšší tep (`session_max` - maximum tejto relácie) a stĺpec
    exportu o tele v najintenzívnejšej chvíli (otázka `session.felt.body_q`)
    stoja vedľa pásma Špička / stĺpca „Špička (min)“; ich popisky preto
    nesmú znieť ako meno pásma."""
    maximum = i18n.STRINGS["dashboard.unit.max"]
    telo = i18n.STRINGS["history.export_col.body_peak"]
    for jazyk, meno in NOVE_MENO.items():
        for zaznam in (maximum, telo):
            assert meno.lower() not in zaznam[jazyk].lower(), (jazyk, zaznam[jazyk])
        # rovnaký rozsah ako karta Priemer; popisok sa zmestí pod číslo
        assert maximum[jazyk] == i18n.STRINGS["dashboard.unit.avg"][jazyk], jazyk
        assert len(maximum[jazyk]) <= 14, jazyk
    assert telo["sk"] == "telo v najintenzívnejšej chvíli"
    assert telo["en"] == "body at the most intense moment"
