# -*- coding: utf-8 -*-
"""The app speaks of itself in the feminine (0.2, final integration).

„Ozvala som sa“, „sama sa neozvem“, „radšej som mlčala“ - that is how the
app sounds in Slovak. In the final check of the 0.2 branch, „tú hranicu som
si spočítal“ (`cue_rate.computed`, text changed in B3-worlds) was found -
the masculine in the app's mouth. This test catches any other such case in
any SK text.

The masculine is fine where the app is NOT the one speaking: the author's
text („Ako to vzniklo“, „O appke“), the player about themselves in the
post-session questionnaire („jedol som“, „Hral som“) and heart rate („tep
klesá aj sám“). Older texts from before 0.2 with a masculine app („Ukončil
som test vizuálu“, „Odstup som zdvihol“, „{app} pripravený“) were fixed in
the languages phase; the list of known debt is empty.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402

# „<verb>l som“ / „som (sa|si) <verb>l“ - past tense in the masculine.
_MUZSKY_MINULY = re.compile(
    r"\b(\w+l)\s+som\b|\bsom\s+(?:sa\s+|si\s+)?(\w+l)\b", re.IGNORECASE)
_SAM = re.compile(r"\bsám\b", re.IGNORECASE)
# Words ending in -l that are not a verb („som naschvál mlčala“).
_NIE_SLOVESO = {"naschvál"}

# Not the app speaking.
_NIE_APPKA = {
    "origin.text",        # author: „Postavil som ho pomocou AI“
    "about.body",         # author: the origin story
    "history.effect_hint",  # „tep klesá aj sám“ - about heart rate
}
_NIE_APPKA_PREFIX = ("session.context.",)   # the player about themselves in the questionnaire

# Older texts with a masculine app - KNOWN DEBT for later, not an exception
# for new texts. When they are fixed, remove them from here. Paid off in
# full in the 0.2 languages phase („Ukončila som test vizuálu“, „Odstup
# som zdvihla“).
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
    """When an old text is fixed, it should disappear from the debt list too
    - otherwise the list would quietly cover a new masculine form under an
    old key."""
    for kluc in _ZNAMY_DLH:
        assert _muzsky_rod(i18n.STRINGS[kluc]["sk"]), kluc


def test_zenske_tvary_appky_ostali():
    """A few lines where the app speaks of itself - they must stay feminine."""
    for kluc, tvar in (("session.end.none_withheld", "som mlčala"),
                       ("session.end.cues_visual", "Ozvala som sa"),
                       ("dnes.nonstop_input", "som nezachytila"),
                       ("history.rebrik.why.missed", "som sa mala ozvať"),
                       ("kamae.lost_sub", "sama sa neozvem"),
                       ("session.zanshin.body", "som ti bola plťou"),
                       # fixed in the 0.2 languages phase (masculine before)
                       ("log.overlay_test_ukonceny", "Skryla som"),
                       ("dev.min_gap_clamped", "som zdvihla"),
                       ("log.vizualy_napravene", "Zapla som"),
                       ("kamae.stopped_sub_auto", "spustím sama"),
                       ("log.ready", "Som pripravená")):
        assert tvar in i18n.STRINGS[kluc]["sk"], kluc


def test_appka_nie_je_pripraveny():
    """The test above does not catch an adjective in the masculine (it is not
    a verb ending in -l) - „{app} pripravený“ was in the log from the
    start. The app is pripravená, not pripravený."""
    zle = {kluc: zaznam["sk"] for kluc, zaznam in i18n.STRINGS.items()
           if kluc not in _NIE_APPKA
           and not kluc.startswith(_NIE_APPKA_PREFIX)
           and re.search(r"\bsom\s+pripravený\b|\{app\}\s+pripravený\b",
                         zaznam.get("sk") or "", re.IGNORECASE)}
    assert not zle, zle
