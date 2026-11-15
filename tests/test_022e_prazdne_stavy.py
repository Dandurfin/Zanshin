# -*- coding: utf-8 -*-
"""Empty states after batch 4 of the UX audit (0.3): one sentence, at most
one action - not dashes, zeros and empty charts that look like a
measurement.

Guarded:
  * `ui_kit.EmptyState` (sentence + optional action, colours from the
    palette),
  * Today without heart rate: "Pair your watch" opens the pairing guide,
  * History, "One session up close" without a session: only a sentence,
    after the first session the trace, legend and grid come back in the
    original order,
  * an empty sentence under the 80 px trend chart takes no space.
"""
import os
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import hr_stats  # noqa: E402
import i18n  # noqa: E402
import theme  # noqa: E402
from _zdroj_appky import zdroj_metody  # noqa: E402


@pytest.fixture
def sk():
    povodny = i18n._lang["code"]
    i18n.set_lang("sk")
    yield
    i18n.set_lang(povodny)


def _app():
    import app as app_mod
    return app_mod.DandurfApp


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


# --------------------------------------------------------------------------
# ui_kit.EmptyState
# --------------------------------------------------------------------------

@pytest.mark.parametrize("tema", [theme.ZEN, theme.MODERN])
def test_emptystate_veta_a_jedna_akcia(tema):
    import customtkinter as ctk
    import ui_kit
    root = _tk_root()
    try:
        pal = theme.tokens(tema)
        klik = []
        stav = ui_kit.EmptyState(root, pal, "Zatiaľ nič.", action="Spárovať hodinky",
                                 command=lambda: klik.append(1))
        stav.pack()
        root.update_idletasks()
        assert stav.label.cget("text") == "Zatiaľ nič."
        # content text, not decoration: text_dim (>= 4.5:1)
        assert stav.label.cget("text_color") == pal["text_dim"]
        assert isinstance(stav.action, ctk.CTkButton)
        assert stav.action.cget("text") == "Spárovať hodinky"
        stav.action.invoke()
        assert klik == [1]
        stav.set_text("Iná veta.")
        assert stav.label.cget("text") == "Iná veta."
        # without an action (or without a command) no button
        holy = ui_kit.EmptyState(root, pal, "Len veta.")
        assert holy.action is None
        bez_prikazu = ui_kit.EmptyState(root, pal, "Veta", action="Nic")
        assert bez_prikazu.action is None
    finally:
        root.destroy()


def test_dnes_bez_tepu_ponuka_parovanie(sk):
    stavba = zdroj_metody("_build_dnes_page")
    assert ('self.dnes_empty = ui_kit.EmptyState(\n'
            '            hr_panel.body, pal, tr("dnes.empty_body"), action=tr("dnes.empty_btn"),\n'
            '            command=self.open_watch_pairing)') in stavba
    # pairing guide turns HR reception on (player need not find the toggle)
    assert "self._enable_hr_monitoring()" in zdroj_metody("open_watch_pairing")
    assert "self.hr_monitoring_enabled = True" in zdroj_metody("_enable_hr_monitoring")
    assert i18n.tr("dnes.empty_btn") == "Spárovať hodinky"
    # no made-up heart rate in the HUD preview
    assert "render_hud(" not in stavba


# --------------------------------------------------------------------------
# History: One session up close
# --------------------------------------------------------------------------

def test_detail_bez_relacie_je_len_veta_a_po_relacii_sa_vrati(sk):
    import customtkinter as ctk
    import ui_kit
    root = _tk_root()
    try:
        pal = theme.tokens(theme.ZEN)
        panel = ui_kit.Panel(root, pal, title=i18n.tr("history.detail_title"))
        panel.pack(fill="x")
        stopa = ctk.CTkFrame(panel.body, height=96)
        stopa.pack(fill="x")
        legenda = ctk.CTkLabel(panel.body, text="legenda")
        legenda.pack(fill="x", pady=(6, 0))
        mriezka = ctk.CTkFrame(panel.body)
        mriezka.pack(fill="x", pady=(10, 0))
        veta = ui_kit.EmptyState(panel.body, pal, i18n.tr("history.detail_empty"))
        a = types.SimpleNamespace(history_detail_empty=veta, history_detail_panel=panel,
                                  _history_detail_packy=None)
        okraje = [w.pack_info()["pady"] for w in (stopa, legenda, mriezka)]
        D = _app()
        for _kolo in range(3):
            D._history_detail_prazdny(a, True)
            assert panel.body.pack_slaves() == [veta]
            D._history_detail_prazdny(a, True)          # a second time breaks nothing
            assert panel.body.pack_slaves() == [veta]
            D._history_detail_prazdny(a, False)
            assert panel.body.pack_slaves() == [stopa, legenda, mriezka]
            # margins are not multiplied by the DPI scale again on return
            assert [w.pack_info()["pady"] for w in (stopa, legenda, mriezka)] == okraje
            assert a._history_detail_packy is None
    finally:
        root.destroy()


def test_detail_historie_vola_prazdny_stav():
    telo = zdroj_metody("_refresh_history_detail")
    assert "self._history_detail_prazdny(True)" in telo
    assert "self._history_detail_prazdny(False)" in telo
    stavba = zdroj_metody("_build_historia_page")
    assert ('self.history_detail_empty = ui_kit.EmptyState(\n'
            '            dp.body, pal, tr("history.detail_empty")') in stavba
    assert i18n.tr_lang("sk", "history.detail_empty").startswith("Zatiaľ žiadna relácia")


# --------------------------------------------------------------------------
# History: empty sentence under the trend chart
# --------------------------------------------------------------------------

class _Label:
    def __init__(self, zabaleny=True):
        self.text = ""
        self.m = "pack" if zabaleny else ""
        self.kw = {}

    def configure(self, **kw):
        self.text = kw.get("text", self.text)

    def winfo_manager(self):
        return self.m

    def pack(self, **kw):
        self.m = "pack"
        self.kw = kw

    def pack_forget(self):
        self.m = ""

    def winfo_exists(self):
        return True


class _Graf:
    def set_series(self, values, **kw):
        self.values, self.kw = list(values), kw


def _atrapa_trendu(sessions):
    D = _app()
    a = types.SimpleNamespace(
        history_trend_caption=_Label(), history_trend=_Graf(),
        history_trend_delta=_Label(), history_info_wrap=_Label(),
        pal=theme.tokens(theme.ZEN), history_metric="baseline",
        history_period=hr_stats.PERIOD_WEEK,
        _history_sessions=lambda: sessions, _world_sessions=lambda: sessions)
    for meno in ("HISTORY_METRICS", "_METRIC_BUCKET_KEY", "_METRIC_BARS",
                 "_METRIC_SCALE", "_METRIC_DECIMALS"):
        setattr(a, meno, getattr(D, meno))
    return D, a


def test_prazdna_veta_pod_grafom_nezabera_miesto(sk):
    import time
    D, a = _atrapa_trendu([])
    D._refresh_history_trend(a)
    assert a.history_trend.kw["empty_text"] == i18n.tr("history.empty_period")
    assert a.history_trend_delta.text == ""
    assert a.history_trend_delta.m == "", "prazdny riadok sa schova"
    # with a session the sentence comes back - above the metric explanation
    now = time.time()
    relacie = [{"started": now - 86400, "duration_s": 1800.0, "baseline_bpm": 62,
                "samples": 1800}]
    a._world_sessions = a._history_sessions = lambda: relacie
    D._refresh_history_trend(a)
    assert a.history_trend_delta.text
    assert a.history_trend_delta.m == "pack"
    assert a.history_trend_delta.kw.get("before") is a.history_info_wrap


def test_graf_bez_dat_ma_80_px():
    import ui_kit
    assert ui_kit.TrendChart.EMPTY_H == 80
