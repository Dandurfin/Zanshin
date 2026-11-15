# -*- coding: utf-8 -*-
"""The top heart-rate zone is called „Špička“ / „Peak“, not „Kritická“ (0.2).

The zone only means „heart rate above your own high heart-rate limit“ -
nothing medical or alarming. „Kritická“, „Critical“, 危険域 („danger zone“)
sounded like a diagnosis. The internal key `critical` (hr_stats, trigger,
HUD, CSV) stays; only what the player reads changes.
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

# The old names of the zone and the sentences that named it, in all languages.
STARE = re.compile(
    r"Kritick|kritick|Critical|critical zone|危険域|临界|Критическ|критическ"
    r"|Критичн|критичн|Crítica|zona crítica|Kritisch|kritischen Zone"
    r"|Critique|zone critique")


def test_meno_pasma_vo_vsetkych_jazykoch():
    for kluc in ("hud.zone.critical", "metric.zones.critical"):
        zaznam = i18n.STRINGS[kluc]
        assert set(zaznam) == set(i18n.LANGUAGES), kluc
        for jazyk, meno in NOVE_MENO.items():
            # the zone legend is lower case (except German, where it is a noun)
            assert zaznam[jazyk].lower() == meno.lower(), (kluc, jazyk)
    stlpec = i18n.STRINGS["history.export_col.critical_min"]
    for jazyk, meno in NOVE_MENO.items():
        assert stlpec[jazyk].startswith(meno), jazyk


def test_ziadny_text_uz_nemenuje_pasmo_po_starom():
    najdene = [(k, j) for k, v in i18n.STRINGS.items()
               for j in i18n.LANGUAGES if STARE.search(str(v.get(j, "")))]
    assert not najdene, najdene


def test_vety_o_mlcani_menuju_nove_pasmo():
    """Every sentence saying „in the top zone the app stays silent“ names the
    same word the player sees in the HUD."""
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
    """The „Špička záťaže“ (Peak load) card (0-100) is not a heart-rate zone -
    its label under the number must no longer be the same word as the zone."""
    tag = i18n.STRINGS["metric.peak.tag"]
    pasmo = i18n.STRINGS["metric.zones.critical"]
    for jazyk in i18n.LANGUAGES:
        assert tag[jazyk].lower() != pasmo[jazyk].lower(), jazyk
        # The label under the number has ~117 px in the card (a 300 px column,
        # two cards); a longer one would stretch the column at the expense of
        # the centre (see ui_kit.StatCard).
        assert len(tag[jazyk]) <= 14, (jazyk, tag[jazyk])
    assert tag["sk"] == "špička záťaže" and tag["en"] == "peak load"


def test_najvyssi_tep_a_telo_v_exporte_nevyzeraju_ako_pasmo():
    """The Najvyšší tep (Highest heart rate) card (`session_max` - the maximum
    of this session) and the export column about the body at the most
    intense moment (question `session.felt.body_q`) stand next to the
    Špička zone / the „Špička (min)“ (Peak (min)) column; so their labels
    must not sound like the zone name."""
    maximum = i18n.STRINGS["dashboard.unit.max"]
    telo = i18n.STRINGS["history.export_col.body_peak"]
    for jazyk, meno in NOVE_MENO.items():
        for zaznam in (maximum, telo):
            assert meno.lower() not in zaznam[jazyk].lower(), (jazyk, zaznam[jazyk])
        # same range as the Priemer (Average) card; label fits under the number
        assert maximum[jazyk] == i18n.STRINGS["dashboard.unit.avg"][jazyk], jazyk
        assert len(maximum[jazyk]) <= 14, jazyk
    assert telo["sk"] == "telo v najintenzívnejšej chvíli"
    assert telo["en"] == "body at the most intense moment"
