# -*- coding: utf-8 -*-
"""0.3 (UX audit, batch 4, text review): fixes found by an independent
review of the new and changed keys in all 11 languages.

What this test guards:
  * the note about the VPN address (pairing and the "Network address" field)
    names the PHONE - it is the app on the phone that connects to the PC's
    address, not the watch (same as `log.hr_client_gone`,
    `hr.pair_status_waiting`, `dnes.hr_no_client`),
  * Czech speaks of itself in one form ("sleduju", not "sleduji"),
  * the history cap (400 sessions) is not called "limit" in Slovak -
    hranica / limit are only for heart rate in BPM,
  * the French list in "Delete history" calls cues "rappels", not
    "signaux",
  * the path "Nastavenia → Vseobecne" in the journal line about the
    shortcut is declined (sk) and in quotation marks (ru) as in the other
    sentences,
  * the Russian line about learning ("Я ещё узнаю тебя" can also be read
    as "este ta spoznam" - "I will yet get to know you") and the Bulgarian
    sentence about time at high heart rate are grammatical.

Synthetic data: none - the test only reads the dictionary.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402

S = i18n.STRINGS

TELEFON = {"sk": "telefón", "en": "phone", "ja": "電話", "zh": "手机", "ru": "телефон",
           "es": "móvil", "de": "Handy", "fr": "téléphone", "pt": "celular",
           "cs": "telefon", "bg": "телефон"}
HODINKY = {"sk": "hodink", "en": "watch", "ja": "時計", "zh": "手表", "ru": "часы",
           "es": "reloj", "de": "Uhr", "fr": "montre", "pt": "relógio",
           "cs": "hodink", "bg": "часовник"}


def test_vpn_poznamka_menuje_telefon_nie_hodinky():
    for kluc in ("hr.ip_virtual_note", "settings.hr_ip_virtual_note"):
        for jazyk in i18n.LANGUAGES:
            text = S[kluc][jazyk]
            assert TELEFON[jazyk] in text, (kluc, jazyk, text)
            assert HODINKY[jazyk] not in text, (kluc, jazyk, text)
    # the address field still advises leaving 0.0.0.0
    for jazyk in i18n.LANGUAGES:
        assert "0.0.0.0" in S["settings.hr_ip_virtual_note"][jazyk], jazyk


def test_cestina_hovori_o_sebe_jednym_tvarom():
    for kluc, zaznam in S.items():
        text = zaznam.get("cs", "")
        assert not re.search(r"\b(?:ne)?sleduji\b", text, re.I), (kluc, text)
    for kluc in ("log.edge_failed_offline", "log.edge_failed_refused",
                 "log.edge_failed_other"):
        assert "Když nesleduju" in S[kluc]["cs"], kluc


def test_strop_historie_nie_je_limit():
    """`data.import.limit`: in Slovak and Czech not "limit"/"hranica" - those
    are the words for heart rate in BPM. The other languages already say
    "at most"."""
    for jazyk in ("sk", "cs"):
        text = S["data.import.limit"][jazyk]
        assert not re.search(r"\blimit|hranic", text, re.I), (jazyk, text)
    assert S["data.import.limit"]["sk"].startswith("História pojme najviac {max} relácií")
    for jazyk in i18n.LANGUAGES:
        assert "{max}" in S["data.import.limit"][jazyk], jazyk
        assert "{n}" in S["data.import.limit"][jazyk], jazyk
    # no Slovak or Czech text uses the English "limit"
    for kluc, zaznam in S.items():
        for jazyk in ("sk", "cs"):
            assert not re.search(r"\blimit", zaznam.get(jazyk, "")), (kluc, jazyk)


def test_francuzsky_zoznam_mazania_vola_pripomienky_rappels():
    assert S["data.delete.events"]["fr"] == "enregistrements des rappels"
    assert S["data.delete.tts"]["fr"] == "rappels vocaux (cache)"
    for kluc, zaznam in S.items():
        if kluc.startswith("data.delete."):
            assert "signa" not in zaznam["fr"], (kluc, zaznam["fr"])


def test_cesta_do_nastaveni_je_sklonovana_ako_v_ostatnych_vetach():
    """sk "v Nastaveniach → ..." (like `ob.cue.note`), ru in quotation marks
    («Настройки → ...», like `insight.cue_never_above`)."""
    sk = S["log.hotkey_layout_swapped"]["sk"]
    assert "v Nastaveniach → Všeobecné" in sk
    assert "v Nastavenia →" not in sk
    assert "«Настройки → Общие»" in S["log.hotkey_layout_swapped"]["ru"]
    for kluc, zaznam in S.items():
        assert "v Nastavenia →" not in zaznam.get("sk", ""), kluc
        assert not re.search(r"\bв Настройки →", zaznam.get("ru", "")), kluc


def test_rusky_riadok_ucenia_a_bulharska_veta_o_pasmach():
    ru = S["dnes.learning"]["ru"]
    assert "знакомлюсь с тобой" in ru
    assert "узнаю" not in ru
    assert "{n}" in ru and "{celkom}" in ru
    assert S["metric.zones.short"]["bg"].startswith("През каква част от сесията")
    assert "през по-голяма част от сесията" in S["insight.over_up"]["bg"]
