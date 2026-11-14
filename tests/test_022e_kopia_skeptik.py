# -*- coding: utf-8 -*-
"""0.2.2 (UX audit, davka 4, kontrola textov): opravy, ktore nasla nezavisla
kontrola novych a zmenenych klucov vo vsetkych 11 jazykoch.

Co strazi tento test:
  * poznamka o VPN adrese (parovanie aj pole "Sietova adresa") menuje
    TELEFON - na adresu PC sa pripaja appka v telefone, nie hodinky (rovnako
    ako `log.hr_client_gone`, `hr.pair_status_waiting`, `dnes.hr_no_client`),
  * cestina hovori o sebe jednym tvarom ("sleduju", nie "sleduji"),
  * strop historie (400 relacii) sa po slovensky nevola "limit" -
    hranica / limit su len pre tep v BPM,
  * francuzsky zoznam v "Zmazat historiu" vola pripomienky "rappels", nie
    "signaux",
  * cesta "Nastavenia → Vseobecne" v dennikovom riadku o skratke je
    sklonovana (sk) a v uvodzovkach (ru) ako v ostatnych vetach,
  * rusky riadok o uceni ("Я ещё узнаю тебя" sa da citat aj ako "este ta
    spoznam") a bulharska veta o case s vysokym tepom su gramaticky.

Synteticke data: ziadne - test cita len slovnik.
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
    # pole adresy stale radi nechat 0.0.0.0
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
    """`data.import.limit`: po slovensky ani cesky nie "limit"/"hranica" -
    to su slova pre tep v BPM. Ostatne jazyky uz hovoria "najviac"."""
    for jazyk in ("sk", "cs"):
        text = S["data.import.limit"][jazyk]
        assert not re.search(r"\blimit|hranic", text, re.I), (jazyk, text)
    assert S["data.import.limit"]["sk"].startswith("História pojme najviac {max} relácií")
    for jazyk in i18n.LANGUAGES:
        assert "{max}" in S["data.import.limit"][jazyk], jazyk
        assert "{n}" in S["data.import.limit"][jazyk], jazyk
    # ziadny slovensky ani cesky text nepouziva anglicke "limit"
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
    """sk "v Nastaveniach → ..." (ako `ob.cue.note`), ru v uvodzovkach
    («Настройки → ...», ako `insight.cue_never_above`)."""
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
