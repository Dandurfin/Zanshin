# -*- coding: utf-8 -*-
"""UX skeptic for batch 4b (0.3): fixes found on screenshots of our windows.

Guarded:
  * the Consistency grid squares lie on whole px - Tk drew an anti-aliased
    polygon at fractional coordinates (the step is a fraction of the width,
    e.g. 40.5 px) with jagged spikes on the edges,
  * month and day labels follow the same whole px,
  * the session row in the in-game heart-rate panel fits in the panel even
    with "1 h 15 min" (since 4b) in every language - before, it overflowed
    the right edge,
  * Japanese and Chinese text in the heart-rate panel (and in its preview
    in the introduction) has a font with those characters, not empty
    squares,
  * "nad hranicou" (above the limit) in the heart-rate panel is the
    heart-rate limit, not the load threshold, also in ja/zh/ru/fr.

Synthetic data, no Tk window (canvas dummy, PIL image in memory).
"""
import os
import sys
from datetime import date, timedelta

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import hud_paint  # noqa: E402
import i18n  # noqa: E402
import theme  # noqa: E402
import ui_kit  # noqa: E402

JAZYKY = ("sk", "en", "ja", "zh", "ru", "es", "de", "fr", "pt", "cs", "bg")


class _Platno:
    """tk.Canvas dummy: items with coordinates, bbox ~7 px/char."""

    def __init__(self, sirka):
        self.sirka = sirka
        self.polozky = {}
        self._id = 0

    def winfo_width(self):
        return self.sirka

    def delete(self, tag):
        if tag == "all":
            self.polozky.clear()
        else:
            self.polozky.pop(tag, None)

    def _nova(self, druh, coords, **kw):
        self._id += 1
        self.polozky[self._id] = {"druh": druh, "coords": list(coords), **kw}
        return self._id

    def create_text(self, x, y, **kw):
        return self._nova("text", (x, y), **kw)

    def create_polygon(self, points, **kw):
        return self._nova("poly", points, **kw)

    def coords(self, polozka, *xy):
        self.polozky[polozka]["coords"] = list(xy)

    def bbox(self, polozka):
        p = self.polozky.get(polozka)
        if not p:
            return None
        x, y = p["coords"][:2]
        sirka = 7 * len(str(p.get("text", "")))
        return (x, y - 6, x + sirka, y + 6)


def _mriezka(sirka, mierka, tyzdnov=26):
    g = object.__new__(ui_kit.DayGrid)
    g.pal = theme.tokens(theme.ZEN)
    g.canvas = _Platno(sirka)
    g.height = g.vyska_mriezky(g.CELL, g.GAP)
    g._get_widget_scaling = lambda: mierka
    g.configure = lambda **kw: None
    dnes = date(2026, 11, 15)
    prvy = dnes - timedelta(days=tyzdnov * 7 - 1)
    g._days = [{"date": prvy + timedelta(days=i), "seconds": (i % 3) * 1800.0}
               for i in range(tyzdnov * 7)]
    g._legend = ("menej", "viac")
    g._months = tuple("jan feb mar apr maj jun jul aug sep okt nov dec".split())
    g._weekdays = tuple("po ut st st2 pi so ne".split())
    g._redraw()
    return g


def test_stvorceky_mriezky_lezia_na_celych_px():
    # 150 % DPI and a width at which the step comes out fractional
    # (screenshot: 40.5 px)
    for sirka, mierka in ((1253, 1.5), (1001, 1.25), (777, 1.0)):
        g = _mriezka(sirka, mierka)
        polygony = [p for p in g.canvas.polozky.values() if p["druh"] == "poly"]
        assert len(polygony) >= 26 * 7
        for p in polygony:
            xs, ys = p["coords"][0::2], p["coords"][1::2]
            for v in (min(xs), max(xs), min(ys), max(ys)):
                assert float(v).is_integer(), (sirka, mierka, v)
            assert max(xs) <= sirka, "stvorcek nepresahuje platno"


def test_popisky_mriezky_sedia_na_celych_px_stlpcov():
    g = _mriezka(1253, 1.5)
    bunky = [p for p in g.canvas.polozky.values() if p["druh"] == "poly"
             and max(p["coords"][0::2]) - min(p["coords"][0::2]) >= g.CELL * 1.5 - 1]
    stlpce = {min(b["coords"][0::2]) for b in bunky}
    riadky = sorted({min(b["coords"][1::2]) for b in bunky})
    strana = min(max(b["coords"][1::2]) - min(b["coords"][1::2]) for b in bunky)
    mesiace = [p for p in g.canvas.polozky.values()
               if p["druh"] == "text" and p.get("text") in g._months]
    assert mesiace
    for m in mesiace:
        assert m["coords"][0] in stlpce, m
    dni = [p for p in g.canvas.polozky.values()
           if p["druh"] == "text" and p.get("text") in g._weekdays]
    assert len(dni) == 7
    for d in dni:
        assert any(d["coords"][1] == y + strana / 2.0 for y in riadky), d


# --------------------------------------------------------------------------
# In-game heart-rate panel (hud_paint)
# --------------------------------------------------------------------------

def _hud_riadok(monkeypatch, jazyk, cas_nad_s=4512):
    """Draws the heart-rate panel with a long session row (like
    `HudMixin._refresh_hud_session_text`) and returns (painter, text, size,
    letter spacing) with which the row was really drawn."""
    if not hud_paint.PIL_AVAILABLE:
        pytest.skip("bez PIL")

    def t(kluc, **kw):
        return i18n.tr_lang(jazyk, kluc, **kw)

    session = "  ·  ".join([
        "125:00", t("hud.session.triggers", n=12),
        t("hud.session.over", time=ui_kit.cas_text(cas_nad_s, preklad=t))])
    zaznam = []
    povodny = hud_paint.Painter.text

    def text(self, x, y, value, color, size, *args, **kw):
        zaznam.append((self, value, size, kw.get("tracking", 0.0)))
        return povodny(self, x, y, value, color, size, *args, **kw)

    monkeypatch.setattr(hud_paint.Painter, "text", text)
    hud_paint.render_hud(
        hud_paint.Style(theme.tokens(theme.ZEN)), bpm=124, stress=78,
        history=[64 + i // 2 for i in range(90)], threshold=110, baseline=64,
        labels={"load": t("hud.load"), "critical": t("hud.zone.critical")},
        session=session, ss=1)
    monkeypatch.setattr(hud_paint.Painter, "text", povodny)
    riadok = [z for z in zaznam if z[1] == session]
    assert riadok, jazyk
    return riadok[-1]


def test_riadok_relacie_v_paneli_tepu_sa_zmesti_v_kazdom_jazyku(monkeypatch):
    """Since 4b the time above the limit is "1 h 15 min" from an hour on -
    with "ÜBER DER GRENZE" or "НАД ГРАНИЦАТА" the row overflowed the
    panel's right edge."""
    sirka = hud_paint.HUD_WIDTH - 2 * 14.0
    for jazyk in JAZYKY:
        p, text, velkost, prestrk = _hud_riadok(monkeypatch, jazyk)
        assert p.measure(text, velkost, tracking=prestrk) <= sirka + 0.01, (jazyk, text)
        assert velkost >= hud_paint.SESSION_MIN, jazyk


def test_kratky_riadok_relacie_ostava_v_plnej_velkosti(monkeypatch):
    p, text, velkost, prestrk = _hud_riadok(monkeypatch, "en", cas_nad_s=125)
    assert (velkost, prestrk) == (8.5, 0.5), "kratky riadok sa nemeni"


def test_cjk_text_v_paneli_tepu_dostane_pismo_s_tymi_znakmi():
    druh = hud_paint._druh_pisma
    assert druh("label", "LOAD") == "label"
    assert druh("label", "НАГРУЗКА") == "label", "cyriliku ma uz Segoe/Bahnschrift"
    assert druh("label", "負荷") == "label_ja"
    assert druh("label", "ピーク") == "label_ja"
    assert druh("display", "残心 124") == "display_ja"
    # simplified characters (负) are missing from Japanese fonts -> Chinese
    # font
    assert druh("label", "负荷") == "label_zh"
    assert druh("label", "超过上限 1 小时 15 分") == "label_zh"
    # the 残 character in the enso has its own brush font
    assert druh("cjk", "残") == "cjk"
    for kind in ("label_ja", "label_zh", "display_ja", "display_zh"):
        assert hud_paint._FONT_CANDIDATES[kind], kind


def test_cjk_pismo_sa_naozaj_nacita_ked_je_vo_windows():
    priecinok = hud_paint._FONT_DIRS[0]
    for kind, text in (("label_ja", "負荷"), ("label_zh", "负荷")):
        mena = [m.lower() for m in hud_paint._FONT_CANDIDATES[kind]
                if os.path.exists(os.path.join(priecinok, m))]
        if not mena:
            continue                    # machine without CJK fonts
        hud_paint._font_cache.pop((kind, 30), None)
        pismo = hud_paint._load_font(hud_paint._druh_pisma("label", text), 30)
        assert os.path.basename(getattr(pismo, "path", "")).lower() in mena, kind


def test_nad_hranicou_v_paneli_tepu_je_hranica_tepu_nie_prah():
    hranica = {"ja": "上限", "zh": "上限", "ru": "границ", "fr": "limite"}
    prah = {"ja": "しきい値", "zh": "阈", "ru": "порог", "fr": "seuil"}
    for jazyk in hranica:
        text = i18n.tr_lang(jazyk, "hud.session.over", time="1:15").lower()
        assert hranica[jazyk] in text, jazyk
        assert prah[jazyk] not in text, jazyk
