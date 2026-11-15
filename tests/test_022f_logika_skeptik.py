# -*- coding: utf-8 -*-
"""Independent check of batch 4b - logic and texts (0.3).

  * Chinese puts the names of pages and buttons in “…” (not in 「…」 like
    Japanese). `ui_kit.zalom_kinsoku` did not know these quotes: a line
    ended with an opening “ and the next began with a closing ” - exactly
    what kinsoku is supposed to prevent.
  * The line to app.log on a shortcut change (AltGr) had the shortcut in
    the app's language ("Strg + Alt + Z"), even though app.log is in
    English (`hotkey.format_combo` with `lang="en"`).

Everything on dummies - no window, made-up data.
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
    """Tk-free width: CJK char 12 px, others 6 px (`_merac_pisma` estimate)."""
    return sum(12 if ui_kit._cjk_znak(c) else 6 for c in text)


def _zlomy(text, sirka):
    """Lines that came from a BREAK (the first line of a paragraph does not
    count - it starts where the author of the text started it)."""
    return [ui_kit.zalom_kinsoku(odsek, sirka, _odhad).split("\n")
            for odsek in text.split("\n")]


def test_cinske_uvodzovky_dodrzia_kinsoku():
    texty = [z["zh"] for z in S.values() if "“" in z.get("zh", "")]
    assert texty, "cinske texty s “…” existuju"
    zle = []
    for text in texty:
        for sirka in range(72, 481, 12):          # 6 to 40 CJK characters per line
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
        # nothing was lost and nothing was added
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
    # the journal is in the app's language...
    assert nemecky in a.denn[0]
    # ...app.log in English
    assert [r for r in log.riadky if anglicky in r], log.riadky
    assert not [r for r in log.riadky if "Strg" in r], log.riadky
