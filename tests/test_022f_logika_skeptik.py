# -*- coding: utf-8 -*-
"""Nezavisla kontrola davky 4b - logika a texty (0.2.2).

  * Cinstina dava nazvy stranok a tlacidiel do “…” (nie do 「…」 ako
    japoncina). `ui_kit.zalom_kinsoku` tieto uvodzovky nepoznal: riadok
    koncil otvaracou “ a dalsi zacinal zatvaracou ” - presne to, co
    kinsoku ma zabranit.
  * Riadok do app.log pri vymene skratky (AltGr) mal skratku v jazyku appky
    ("Strg + Alt + Z"), hoci app.log je po anglicky (`hotkey.format_combo`
    s `lang="en"`).

Vsetko na atrapach - bez okna, data vymyslene.
"""
import pytest

import app as app_mod
import app_prefs
import hotkey
import i18n
import ui_kit
from app_spolocne import DEFAULT_SNOOZE_HOTKEY

S = i18n.STRINGS


def _odhad(text):
    """Sirka bez Tk: znak CJK 12 px, ostatne 6 px (ako odhad `_merac_pisma`)."""
    return sum(12 if ui_kit._cjk_znak(c) else 6 for c in text)


def _zlomy(text, sirka):
    """Riadky, ktore vznikli ZLOMOM (prvy riadok odseku sa nepocita - ten
    zacina tam, kde autor textu)."""
    return [ui_kit.zalom_kinsoku(odsek, sirka, _odhad).split("\n")
            for odsek in text.split("\n")]


def test_cinske_uvodzovky_dodrzia_kinsoku():
    texty = [z["zh"] for z in S.values() if "“" in z.get("zh", "")]
    assert texty, "cinske texty s “…” existuju"
    zle = []
    for text in texty:
        for sirka in range(72, 481, 12):          # 6 az 40 znakov CJK na riadok
            for riadky in _zlomy(text, sirka):
                for i, riadok in enumerate(riadky):
                    if riadok and riadok[-1] in "“‘" and i < len(riadky) - 1:
                        zle.append(("koniec", sirka, riadok))
                    if riadok and riadok[0] in "”’" and i > 0:
                        zle.append(("zaciatok", sirka, riadok))
    assert not zle, zle[:5]


def test_priklad_okna_parovania_v_cinstine():
    text = S["hr.pair_status_gave_up"]["zh"].format(port=4455, page="游戏中")
    for sirka in (60, 66, 102, 198, 204, 234):
        riadky = ui_kit.zalom_kinsoku(text, sirka, _odhad).split("\n")
        assert not [r for r in riadky[:-1] if r.endswith("“")], (sirka, riadky)
        assert not [r for r in riadky[1:] if r.startswith("”")], (sirka, riadky)
        # nic sa nestratilo ani nepribudlo
        assert "".join(riadky).replace(" ", "") == text.replace(" ", "")


class _Log:
    def __init__(self):
        self.riadky = []

    def info(self, sprava, *args):
        self.riadky.append(sprava % args)

    def exception(self, *_a, **_k):
        pass


@pytest.fixture
def nemcina():
    povodny = i18n._lang["code"]
    i18n.set_lang("de")
    yield
    i18n.set_lang(povodny)


def test_app_log_pri_vymene_skratky_ostava_anglicky(monkeypatch, nemcina):
    log = _Log()
    monkeypatch.setattr(app_prefs, "app_log", log)
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.snooze_hotkey = DEFAULT_SNOOZE_HOTKEY
    a.snooze_hotkey_chosen = False
    a.denn = []
    a.log = a.denn.append
    a.save_settings = lambda: None

    def kolizia(combo):
        return "ż" if combo == DEFAULT_SNOOZE_HOTKEY else ""

    nahrada = a._vyber_skratku_pri_starte(kolizia=kolizia)
    assert nahrada
    nemecky = hotkey.format_combo(DEFAULT_SNOOZE_HOTKEY)
    anglicky = hotkey.format_combo(DEFAULT_SNOOZE_HOTKEY, lang="en")
    assert "Strg" in nemecky and "Ctrl" in anglicky
    # dennik je v jazyku appky...
    assert nemecky in a.denn[0]
    # ...app.log po anglicky
    assert [r for r in log.riadky if anglicky in r], log.riadky
    assert not [r for r in log.riadky if "Strg" in r], log.riadky
