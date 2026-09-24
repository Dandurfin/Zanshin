"""Prečo appka vzniká - slová autora (24. 9. 2026) na troch miestach.

Autor ich potvrdil doslova: „O appke“ (Nastavenia), „Ako to vzniklo“
(História aj koniec karty v Sprievodcovi) a SOUL.md. Test stráži, aby sa
tieto tri miesta nerozišli - keď sa veta zmení na jednom mieste, musí sa
zmeniť všade.
"""
import os

import i18n

SK = ("Vyrástol som s hrami ako mnohí z mojej generácie. Za očami sa v nás "
      "deje viac, než vidno. Zanshin je môj pokus skúsiť to v mieri: niečo, "
      "čo si všimne, nič nechce a nič nepredáva.")
EN = ("I grew up with games, like a lot of my generation. More goes on behind "
      "the eyes than anyone sees. Zanshin is my attempt to try it in peace: "
      "something that notices, wants nothing and sells nothing.")

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_o_appke_ma_vetu_autora_v_sk_aj_en():
    assert SK in i18n.tr_lang("sk", "about.body")
    assert EN in i18n.tr_lang("en", "about.body")


def test_o_appke_ma_odsek_vo_vsetkych_jazykoch_na_tom_istom_mieste():
    """Štvrtý odsek zo siedmich - hneď za „z obyčajnej osobnej potreby“."""
    for jazyk in i18n.LANGUAGES:
        odseky = i18n.tr_lang(jazyk, "about.body").split("\n\n")
        assert len(odseky) == 7, jazyk
        assert "Zanshin" in odseky[3], jazyk


def test_ako_to_vzniklo_zacina_vetou_autora():
    assert i18n.STRINGS["origin.text"]["sk"].startswith(SK + "\n\n")
    assert i18n.STRINGS["origin.text"]["en"].startswith(EN + "\n\n")


def test_soul_ma_vetu_autora():
    with open(os.path.join(KOREN, "SOUL.md"), encoding="utf-8") as f:
        assert EN in f.read()
