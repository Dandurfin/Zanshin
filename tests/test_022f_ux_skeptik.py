# -*- coding: utf-8 -*-
"""Skeptik UX davky 4b (0.2.2): opravy najdene na snimkach vlastnych okien.

Strazi sa:
  * stvorceky mriezky Pravidelnost lezia na celych px - Tk kreslil
    vyhladeny polygon na zlomkovych suradniciach (krok je podiel sirky,
    napr. 40,5 px) so zubatymi ostnami na hranach,
  * popisky mesiacov a dni idu po tych istych celych px,
  * riadok relacie v paneli tepu v hre sa zmesti do panela aj s "1 h 15
    min" (od 4b) v kazdom jazyku - predtym presahoval pravy okraj,
  * japonsky a cinsky text v paneli tepu (a v jeho nahlade v uvode) ma
    pismo s tymi znakmi, nie prazdne stvorceky,
  * "nad hranicou" v paneli tepu je hranica tepu, nie prah zataze, aj
    v ja/zh/ru/fr.

Synteticke data, ziadne Tk okno (atrapa platna, PIL obrazok v pamati).
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
    """Atrapa tk.Canvas: polozky so suradnicami, bbox ~7 px/znak."""

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
    # 150 % DPI a sirka, pri ktorej krok vyjde zlomkovy (snimka: 40,5 px)
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
# Panel tepu v hre (hud_paint)
# --------------------------------------------------------------------------

def _hud_riadok(monkeypatch, jazyk, cas_nad_s=4512):
    """Vykresli panel tepu s dlhym riadkom relacie (ako
    `HudMixin._refresh_hud_session_text`) a vrati (painter, text, velkost,
    prestrkanie), ktorymi sa riadok naozaj kreslil."""
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
    """Od 4b je cas nad hranicou od hodiny "1 h 15 min" - s "ÜBER DER
    GRENZE" ci "НАД ГРАНИЦАТА" riadok presahoval pravy okraj panela."""
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
    # zjednodusene znaky (负) japonske pisma nemaju -> cinske pismo
    assert druh("label", "负荷") == "label_zh"
    assert druh("label", "超过上限 1 小时 15 分") == "label_zh"
    # znak 残 v ense ma vlastne stetcove pismo
    assert druh("cjk", "残") == "cjk"
    for kind in ("label_ja", "label_zh", "display_ja", "display_zh"):
        assert hud_paint._FONT_CANDIDATES[kind], kind


def test_cjk_pismo_sa_naozaj_nacita_ked_je_vo_windows():
    priecinok = hud_paint._FONT_DIRS[0]
    for kind, text in (("label_ja", "負荷"), ("label_zh", "负荷")):
        mena = [m.lower() for m in hud_paint._FONT_CANDIDATES[kind]
                if os.path.exists(os.path.join(priecinok, m))]
        if not mena:
            continue                    # stroj bez CJK pisiem
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
