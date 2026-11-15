# -*- coding: utf-8 -*-
"""Text after batch 4b of the UX audit (0.3): wrapping of Japanese and
Chinese, the date in the app language and long time over the limit.

Guarded:
  * kinsoku: a line does not start with 「。」「、」「）」「」」 or a small kana
    and does not end with an opening bracket; nothing is lost, Latin text
    does not change,
  * every CTkLabel with `wraplength` shows ja/zh text broken by kinsoku,
    `cget("text")` returns the original text; other languages do not change,
  * the date takes the app language's form (sk "12. 11. 2026", de
    "12.11.2026", en "12 Nov 2026", ja "2026年11月12日"), the time stays
    HH:MM, the export file ISO,
  * "Over the limit" from one hour on is "1 h 15 min", not "75:12" - like
    the trace axis.
"""
import os
import sys
import time
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import i18n  # noqa: E402
import ui_kit  # noqa: E402
from _zdroj_appky import zdroj_metody, zdroj_suboru  # noqa: E402
from i18n import tr  # noqa: E402

ZACIATOK_NIE = "、。，．）」』】〕〉》！？：；ーぁぃぅぇぉっゃゅょァィゥェォッャュョ"
KONIEC_NIE = "（「『【〔〈《"


@pytest.fixture
def jazyk():
    povodny = i18n._lang["code"]

    def nastav(kod):
        i18n.set_lang(kod)
    yield nastav
    i18n.set_lang(povodny)


def _tk_root():
    if sys.platform != "win32":
        pytest.skip("len Windows")
    import tkinter as tk
    import customtkinter as ctk
    try:
        root = ctk.CTk()
    except tk.TclError:
        pytest.skip("bez displeja")
    root.withdraw()
    return root


def _kontrola_kinsoku(text, zlomeny, sirka, zmeraj):
    riadky = zlomeny.split("\n")
    assert "".join(riadky).replace(" ", "") == text.replace("\n", "").replace(" ", ""), \
        "ziadny znak sa nestratil"
    for i, riadok in enumerate(riadky):
        assert riadok, "prazdny riadok"
        if i:
            assert riadok[0] not in ZACIATOK_NIE, (i, riadok)
        if i < len(riadky) - 1:
            assert riadok[-1] not in KONIEC_NIE, (i, riadok)
        assert zmeraj(riadok) <= sirka or len(riadok) == 1, (riadok, zmeraj(riadok))


# --------------------------------------------------------------------------
# 12: kinsoku
# --------------------------------------------------------------------------

def _znaky(s):
    return float(len(s))


@pytest.mark.parametrize("sirka", range(4, 14))
def test_kinsoku_pri_kazdej_sirke(sirka):
    text = "これは合図の説明です。重心、顎（あご）、手と視線、呼吸「深く」。ちょっと待って、ゆっくり。"
    zlomeny = ui_kit.zalom_kinsoku(text, sirka, _znaky)
    _kontrola_kinsoku(text, zlomeny, sirka, _znaky)


def test_kinsoku_presunie_bodku_na_koniec_riadku():
    # at width 5 "。" would start the second line - the last character goes
    # with it
    zlomeny = ui_kit.zalom_kinsoku("あいうえお。かき", 5, _znaky)
    assert zlomeny == "あいうえ\nお。かき"


def test_kinsoku_otvaracia_zatvorka_nekonci_riadok():
    zlomeny = ui_kit.zalom_kinsoku("あいう「えお」かき", 4, _znaky)
    assert not any(r.endswith("「") for r in zlomeny.split("\n"))
    _kontrola_kinsoku("あいう「えお」かき", zlomeny, 4, _znaky)


def test_kinsoku_cinstina():
    text = "在最近的记录里，你的心率平均每次有两次中断。每次计时都得从头开始（重新）。"
    for sirka in range(5, 12):
        _kontrola_kinsoku(text, ui_kit.zalom_kinsoku(text, sirka, _znaky), sirka, _znaky)


def test_kinsoku_nedeli_latinske_slova_a_necha_latinku():
    text = "OBS の WebSocket サーバーをオフにしてください。"
    zlomeny = ui_kit.zalom_kinsoku(text, 8, _znaky)
    assert "WebSocket" in zlomeny.replace("\n", " ").split(), zlomeny
    lat = "Port 4455 is busy. Change it on the In-game page."
    assert ui_kit.zalom_kinsoku(lat, 5, _znaky) == lat
    assert ui_kit.zalom_kinsoku("", 5, _znaky) == ""
    assert ui_kit.zalom_kinsoku(None, 5, _znaky) == ""
    assert ui_kit.zalom_kinsoku("あいう", 0, _znaky) == "あいう"


def test_kinsoku_necha_existujuce_zlomy():
    zlomeny = ui_kit.zalom_kinsoku("あいう\nえお", 10, _znaky)
    assert zlomeny == "あいう\nえお"


def test_label_v_japoncine_zlomi_podla_kinsoku(jazyk):
    jazyk("ja")
    root = _tk_root()
    try:
        import customtkinter as ctk
        text = tr("settings.cue_style_sub")
        label = ctk.CTkLabel(root, text=text, font=ui_kit.ui(11), wraplength=160)
        zobrazeny = label._label.cget("text")
        assert "\n" in zobrazeny
        assert label.cget("text") == text, "volajuci vidi povodny text"
        zmeraj = ui_kit._merac_pisma(ui_kit.ui(11))
        _kontrola_kinsoku(text, zobrazeny, 160, zmeraj)
        # new text via configure gets broken too
        druhy = tr("dnes.zones_hint")
        label.configure(text=druhy)
        _kontrola_kinsoku(druhy, label._label.cget("text"), 160, zmeraj)
        # without wraplength nothing gets broken
        holy = ctk.CTkLabel(root, text=text, font=ui_kit.ui(11))
        assert holy._label.cget("text") == text
    finally:
        root.destroy()


def test_label_v_slovencine_sa_nemeni(jazyk):
    jazyk("sk")
    root = _tk_root()
    try:
        import customtkinter as ctk
        text = tr("settings.cue_style_sub")
        label = ctk.CTkLabel(root, text=text, font=ui_kit.ui(11), wraplength=160)
        assert label._label.cget("text") == text
    finally:
        root.destroy()


def test_hacik_na_labeli_je_raz_a_nevyhodi_vynimku():
    import customtkinter as ctk
    assert getattr(ctk.CTkLabel, "_zanshin_kinsoku", False)
    init = ctk.CTkLabel.__init__
    ui_kit.zapni_kinsoku_v_labeloch()
    assert ctk.CTkLabel.__init__ is init, "druhe volanie nic neobali"
    ui_kit._kinsoku_labelu(object())
    ui_kit._kinsoku_labelu(types.SimpleNamespace(_text=None, _wraplength=100))


def test_text_na_platne_dnes_sa_zlomi_podla_kinsoku():
    kod = zdroj_metody("_canvas_text")
    assert "ui_kit.zalom_kinsoku(text, wrap, zmeraj)" in kod


# --------------------------------------------------------------------------
# 13: the date in the app language
# --------------------------------------------------------------------------

TS = time.mktime((2026, 11, 12, 20, 5, 0, 0, 0, -1))
TS_FEB = time.mktime((2026, 2, 3, 9, 7, 0, 0, 0, -1))


@pytest.mark.parametrize("kod, dlhy, kratky, februar", [
    ("sk", "12. 11. 2026", "12. 11.", "3. 2. 2026"),
    ("cs", "12. 11. 2026", "12. 11.", "3. 2. 2026"),
    ("de", "12.11.2026", "12.11.", "03.02.2026"),
    ("ru", "12.11.2026", "12.11", "03.02.2026"),
    ("bg", "12.11.2026", "12.11", "03.02.2026"),
    ("en", "12 Nov 2026", "12 Nov", "3 Feb 2026"),
    ("fr", "12 nov. 2026", "12 nov.", "3 févr. 2026"),
    ("es", "12 nov 2026", "12 nov", "3 feb 2026"),
    ("pt", "12 nov 2026", "12 nov", "3 fev 2026"),
    ("ja", "2026年11月12日", "11月12日", "2026年2月3日"),
    ("zh", "2026年11月12日", "11月12日", "2026年2月3日"),
])
def test_datum_v_kazdom_jazyku(kod, dlhy, kratky, februar):
    assert ui_kit.datum_text(TS, jazyk=kod) == dlhy
    assert ui_kit.datum_text(TS, rok=False, jazyk=kod) == kratky
    assert ui_kit.datum_text(TS, cas=True, jazyk=kod) == dlhy + " 20:05"
    assert ui_kit.datum_text(TS_FEB, cas=True, jazyk=kod) == februar + " 09:07"


def test_datum_berie_jazyk_appky(jazyk):
    jazyk("de")
    assert ui_kit.datum_text(TS) == "12.11.2026"
    jazyk("en")
    assert ui_kit.datum_text(TS) == "12 Nov 2026"


def test_mesiac_v_kazdom_jazyku():
    assert ui_kit.mesiac_text(TS, jazyk="sk") == "nov 2026"
    assert ui_kit.mesiac_text(TS, jazyk="de") == "Nov 2026"
    assert ui_kit.mesiac_text(TS, jazyk="ja") == "2026年11月"
    assert ui_kit.mesiac_text(TS, jazyk="ru") == "11.2026"


@pytest.mark.parametrize("zly", [None, "x", float("inf"), 1e20])
def test_pokazeny_datum(zly):
    assert ui_kit.datum_text(zly, jazyk="sk") == "—"
    assert ui_kit.mesiac_text(zly, jazyk="sk") == "—"


def test_kazdy_jazyk_ma_tvar_datumu_a_12_mesiacov():
    for kod in ("sk", "en", "ja", "zh", "ru", "es", "de", "fr", "pt", "cs", "bg"):
        assert kod in ui_kit._TVAR_DATUMU
        assert len(i18n.tr_lang(kod, "history.grid_months").split()) == 12, kod


def test_historia_pise_datum_v_jazyku_appky():
    zdroj = zdroj_suboru("app_history.py")
    assert '"%d.%m.%Y' not in zdroj and "%d.%m. %H:%M" not in zdroj
    # the sessions table and the detail header
    assert zdroj.count("ui_kit.datum_text(started, cas=True)") >= 2
    assert "when=ui_kit.datum_text(stamp, rok=False, cas=True)" in zdroj
    # the exported file name stays ISO
    assert 'time.strftime("zanshin-relacie-%Y-%m-%d.csv")' in zdroj
    assert "ui_kit.datum_text(started, cas=True)" in zdroj_suboru("app_data.py")


def test_popisky_grafu_trendu(jazyk):
    import hr_stats
    from app_history import HistoryMixin
    jazyk("en")
    b = {"started": TS, "label": "12.11"}
    assert HistoryMixin._popisok_bucketu(b, hr_stats.PERIOD_DAY) == "12 Nov"
    assert HistoryMixin._popisok_bucketu(b, hr_stats.PERIOD_WEEK) == "12 Nov"
    assert HistoryMixin._popisok_bucketu(b, hr_stats.PERIOD_MONTH) == "Nov 2026"
    assert HistoryMixin._popisok_bucketu({"label": "x"}, hr_stats.PERIOD_DAY) == "x"
    jazyk("ja")
    assert HistoryMixin._popisok_bucketu(b, hr_stats.PERIOD_DAY) == "11月12日"


# --------------------------------------------------------------------------
# 14: "Over the limit" from one hour on as a duration
# --------------------------------------------------------------------------

def test_cas_nad_hranicou(jazyk):
    jazyk("sk")
    assert ui_kit.cas_text(0) == "0:00"
    assert ui_kit.cas_text(125) == "2:05"
    assert ui_kit.cas_text(3599) == "59:59"
    assert ui_kit.cas_text(3600) == tr("dashboard.fmt.h_min", h=1, m="00")
    assert ui_kit.cas_text(75 * 60 + 12) == tr("dashboard.fmt.h_min", h=1, m="15")
    assert ui_kit.cas_text("zle") == "—"
    assert ui_kit.cas_text(None) == "0:00"
    # the same boundary as the end of the session trace axis
    assert ui_kit.DLZKA_OD_S == ui_kit.SessionTrace.OS_DLZKA_OD_S == 3600


def test_cas_nad_hranicou_v_jazyku_hry():
    vlastny = []

    def preklad(kluc, **kw):
        vlastny.append(kluc)
        return f"{kw['h']}:{kw['m']}h"
    assert ui_kit.cas_text(75 * 60, preklad=preklad) == "1:15h"
    assert vlastny == ["dashboard.fmt.h_min"]


def test_nad_hranicou_v_historii_dnes_a_v_hre(jazyk):
    jazyk("sk")
    from app_history import HistoryMixin
    assert HistoryMixin._fmt_minutes(4512) == ui_kit.cas_text(4512)
    assert HistoryMixin._fmt_minutes(120) == "2:00"
    from app_today import TodayMixin
    a = types.SimpleNamespace(hr_stats=types.SimpleNamespace(session_count=5, time_over=4512.0))
    hodnota, _popis = TodayMixin._dashboard_stat_value(a, "over")
    assert hodnota == tr("dashboard.fmt.h_min", h=1, m="15")
    assert "ui_kit.cas_text(int(stats.time_over), preklad=self._game_text)" in \
        zdroj_metody("_refresh_hud_session_text")
