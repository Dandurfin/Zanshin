"""History page - part of the main app (DandurfApp from app.py).

HistoryMixin is a mixin of DandurfApp: app.py inherits it and all the state
(the widgets of the History page, the chosen trend metric and period, the
session selected in the detail, the insights from the analysis and its
thread) lives on DandurfApp. Here are only the methods that work with it
through `self` - the mixin has no __init__ and no attributes of its own.

Moved from app.py unchanged:
  * metric info - a sentence next to a number with an expandable
    explanation (`_metric_info`); the Today page in app.py uses it too,
  * History page - building the page, loading the session history
    (`_history_sessions`, `_world_sessions` - other parts of the app call
    them too) and the minute format,
  * trend: metric + time period (chips) - the trend chart, the sessions
    table, the ladder sentence, the "which cue works" chart and CSV export,
  * consistency and the detail of one session - the day grid, the detail
    of the selected session, value formats (`_fmt_*` are also used by the
    cards on Today in app_today.py) and the insights from the analysis,
  * background history analysis - only its first part: starting the
    analysis in a thread, taking over the result and re-running it. The
    rest of that section (building the Settings and In game pages, the
    heart rate sensor card) has nothing to do with history - it stayed in
    app.py under the new marker for "the Settings and In game pages".

Page constants (`HISTORY_ROWS`, `HISTORY_METRICS`, `_METRIC_*`,
`HISTORY_DETAIL_COLS`, `HISTORY_DETAIL_CELLS`) stayed in the DandurfApp
class among the other class constants - the methods read them through
`self`.

Careful in tests: `_refresh_history_page`, `export_sessions_csv`,
`_refresh_history_detail`, `_render_hr_insights` and `_apply_hr_insights`
read `time` from this module and `run_hr_analysis` reads `threading` - a
fake clock and a synchronous thread have to be slipped in here too
(`app_history.time`, `app_history.threading`), not only on the app module.
"""

import os
import threading
import time
import webbrowser
from tkinter import filedialog

import customtkinter as ctk

import data_io
import hr_insights
import hr_stats
import measure
import rebrik
import ui_kit
from guide_content import origin_sources
from i18n import cislo, tr
from paths import APP_NAME

from app_spolocne import app_log, stranka_vhre, zapamataj_text_stranky


class HistoryMixin:
    """History page and background history analysis (DandurfApp mixin)."""

    # ---------- metric info ("so the user knows") ----------

    def _metric_info(self, parent, pal, metric, wrap=420, titled=False):
        """Sentence by a number + expandable 'what it means' (ui_kit.InfoRow).
        The texts are in i18n under metric.<id>.short / .more - the exact
        wording from the spec, for the player, not for a doctor.

        `titled=True` puts the metric name (metric.<id>.title) above the
        sentence - for the explanations under the table, where the column
        headers have already scrolled away and three "ⓘ what it means" one
        under another did not say which number they belong to."""
        nazov = tr(f"metric.{metric}.title") if titled else None
        # `page`: `metric.over.more` points to the "In game" page by its name
        # in the current world (0.3 batch 4b); the other texts do not use it.
        # After a world switch `obnov_texty_stranky` rewrites it.
        riadok = ui_kit.InfoRow(parent, pal, tr(f"metric.{metric}.short"),
                                tr(f"metric.{metric}.more", page=stranka_vhre(self)),
                                tr("history.info_more"),
                                tr("history.info_less"), wrap=wrap, title=nazov)
        zapamataj_text_stranky(self, getattr(riadok, "more", None), f"metric.{metric}.more")
        return riadok

    # ---------- History page ----------

    def _build_historia_page(self, page, pal):
        """History of heart rate sessions: insights from the background
        analysis, the trend of the resting baseline across sessions, a
        table of sessions with metrics from clean BPM and a 'Why it works'
        panel with studies.

        Data: hr_sessions.json (hr_stats.save_session) + hr_insights.json
        (hr_insights.analyze in the background). The page is redrawn when
        it is built, after a session is saved and after the analysis
        finishes (_refresh_history_page).
        """
        scroll = ui_kit.stranka_scroll(page, pal)
        scroll.pack(fill="both", expand=True, padx=ui_kit.PAGE_GUTTER, pady=(20, 20))
        self.history_scroll = scroll

        ctk.CTkLabel(scroll, text=tr("history.title"), font=ui_kit.ui(17, "bold"),
                     text_color=pal["text"], anchor="w").pack(fill="x")
        ctk.CTkLabel(scroll, text=tr("history.subtitle"), font=ui_kit.ui(11),
                     text_color=pal["text_dim"], wraplength=680, anchor="w",
                     justify="left").pack(fill="x", pady=(4, 2))
        # Which world the page shows (B3-worlds). Without this sentence an
        # empty Work world would look like lost history. The text is filled in
        # by `_refresh_history_page`, because the world changes without the
        # page being rebuilt.
        self.history_world_note = ctk.CTkLabel(
            scroll, text="", font=ui_kit.ui(10), text_color=pal["text_faint"],
            wraplength=680, anchor="w", justify="left")
        self.history_world_note.pack(fill="x", pady=(0, 10))

        # --- insights (background analysis) ---
        ins = ui_kit.Panel(scroll, pal, title=tr("history.insights_title"), right="")
        ins.pack(fill="x")
        self.history_insights_panel = ins
        self.history_insights_box = ctk.CTkFrame(ins.body, fg_color="transparent")
        self.history_insights_box.pack(fill="x")
        foot = ctk.CTkFrame(ins.body, fg_color="transparent")
        foot.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(foot, text=tr("history.insights_note"), font=ui_kit.ui(10),
                     text_color=pal["text_faint"], anchor="w", justify="left",
                     wraplength=520).pack(side="left", fill="x", expand=True)
        # A secondary button, not a chip (a chip is only an external link).
        # While the only "insight" is the counter "0 of 3 sessions", there is
        # nothing to recompute and the button is hidden
        # (`_render_hr_insights`).
        self.history_recompute_btn = ui_kit.button(foot, pal, tr("history.recompute"),
                                                   command=self.run_hr_analysis,
                                                   height=28)
        self.history_recompute_btn.pack(side="right")

        # --- trend across sessions: the metric + time period can be
        # switched, chart and text are redrawn (_refresh_history_trend) ---
        tp = ui_kit.Panel(scroll, pal, title=tr("history.trend_title"))
        tp.pack(fill="x", pady=(14, 0))

        # Two rows of chips one under the other looked like a single grid of
        # eight buttons - from the screen you could not read that the top row
        # changes WHAT and the bottom one OVER WHAT PERIOD. A label on the
        # left says it in one word.
        #
        # TWO CONTROLS, NOT TWELVE FRAMES (0.3, UX audit). Eight metric chips
        # and four periods were twelve framed buttons that visually
        # overpowered the chart they control - and in the app the same chip
        # also meant a tab, an action and a link. The metric is one dropdown
        # (pick one of eight), the period one segmented switch (four side by
        # side, one selected - the selected one carries its text in the
        # accent colour).
        self.history_metric = getattr(self, "history_metric", "baseline")
        self._history_metric_by_label = {tr(t): k for k, t, _c in self.HISTORY_METRICS}
        metric_row = ctk.CTkFrame(tp.body, fg_color="transparent")
        metric_row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(metric_row, text=tr("history.pick_metric").upper(), width=74,
                     font=ui_kit.ui(10, "bold"), text_color=pal["text_faint"],
                     anchor="w").pack(side="left")
        self.history_metric_menu = ui_kit.option_menu(
            metric_row, pal, values=list(self._history_metric_by_label),
            command=lambda label: self._set_history_metric(
                self._history_metric_by_label.get(label, self.history_metric)))
        self.history_metric_menu.set(self._history_metric_label(self.history_metric))
        self.history_metric_menu.pack(side="left")

        self.history_period = getattr(self, "history_period", hr_stats.PERIOD_WEEK)
        self._history_period_by_label = {tr(f"history.period.{k}"): k
                                         for k in hr_stats.PERIODS}
        period_row = ctk.CTkFrame(tp.body, fg_color="transparent")
        period_row.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(period_row, text=tr("history.pick_period").upper(), width=74,
                     font=ui_kit.ui(10, "bold"), text_color=pal["text_faint"],
                     anchor="w").pack(side="left")
        self.history_period_switch = ctk.CTkSegmentedButton(
            period_row, values=list(self._history_period_by_label), height=28,
            font=ui_kit.ui(12), fg_color=pal["surface_alt"],
            selected_color=pal["accent2"], selected_hover_color=pal["accent2_hover"],
            unselected_color=pal["surface_alt"], unselected_hover_color=pal["border"],
            text_color=pal["text"],
            command=lambda label: self._set_history_period(
                self._history_period_by_label.get(label, self.history_period)))
        self.history_period_switch.set(tr(f"history.period.{self.history_period}"))
        self.history_period_switch.pack(side="left")
        ui_kit.oznac_zvoleny_segment(self.history_period_switch, pal)

        self.history_trend_caption = ctk.CTkLabel(tp.body, text="", font=ui_kit.ui(11),
                                                  text_color=pal["text_dim"], anchor="w")
        self.history_trend_caption.pack(fill="x")
        self.history_trend = ui_kit.TrendChart(tp.body, pal, height=158)
        self.history_trend.pack(fill="x", pady=(6, 0))
        # A sentence, not a console printout: monospace is only in the table
        # and on the axes.
        self.history_trend_delta = ctk.CTkLabel(tp.body, text="", font=ui_kit.ui(12),
                                                text_color=pal["text"], anchor="w")
        self.history_trend_delta.pack(fill="x", pady=(4, 0))
        self.history_info_wrap = ctk.CTkFrame(tp.body, fg_color="transparent")
        self.history_info_wrap.pack(fill="x", pady=(6, 0))
        self._render_history_metric_info()

        # --- which cue works ---
        # This can only be asked since the categories alternate
        # (`measure.next_slot`). Until 18. 9. the app always played one, so
        # there was nothing to compare.
        ep = ui_kit.Panel(scroll, pal, title=tr("history.effect_title"), right="")
        ep.pack(fill="x", pady=(14, 0))
        self.history_effect_panel = ep
        self.history_effect = ui_kit.CueEffectChart(ep.body, pal)
        self.history_effect.pack(fill="x")
        self.history_effect_hint = ctk.CTkLabel(
            ep.body, text=tr("history.effect_hint"), font=ui_kit.ui(10),
            text_color=pal["text_faint"], anchor="w", justify="left",
            wraplength=560)
        self.history_effect_hint.pack(fill="x", pady=(8, 0))
        # CUE LADDER (0.2): one quiet sentence, only when the app has turned
        # itself down below the top - with the reason. At the top it is not
        # shown at all (`_refresh_rebrik_note`).
        self.history_rebrik_note = ctk.CTkLabel(
            ep.body, text="", font=ui_kit.ui(10),
            text_color=pal["text_faint"], anchor="w", justify="left",
            wraplength=560)

        # --- consistency: day grid + streaks ---
        # The only thing on this page that does not talk about one session
        # but about a pattern: weekends, streaks of evenings, a week when the
        # app lay switched off.
        gp = ui_kit.Panel(scroll, pal, title=tr("history.rhythm_title"), right="")
        gp.pack(fill="x", pady=(14, 0))
        self.history_rhythm_panel = gp
        grid_row = ctk.CTkFrame(gp.body, fg_color="transparent")
        grid_row.pack(fill="x")
        self.history_daygrid = ui_kit.DayGrid(grid_row, pal)
        self.history_daygrid.pack(side="left", fill="x", expand=True)
        # height has to be given: CTkFrame has a default requested height of
        # 200 px and with pack_propagate(False) the panel would keep it even
        # with three lines of text - an empty third of the panel would be
        # left under the grid.
        days_box = ctk.CTkFrame(grid_row, fg_color="transparent", width=150, height=118)
        # top, not centre: the grid grows with the width (0.3 batch 4b) and
        # the number should stay at the height of the first rows, not float
        # below them
        days_box.pack(side="right", padx=(18, 0), anchor="n")
        days_box.pack_propagate(False)
        # The label carries the number of weeks in the grid - that changes
        # with the history, so the page keeps a reference to it
        # (`_refresh_history_rhythm`).
        self.history_days_label = ctk.CTkLabel(
            days_box, text=tr("history.days_played",
                              weeks=self.RYTMUS_MAX_TYZDNOV).upper(),
            font=ui_kit.ui(10, "bold"), text_color=pal["text_faint"],
            anchor="w", justify="left", wraplength=150)
        self.history_days_label.pack(fill="x")
        # The colour is `text`, not `success`: green was from the days when
        # it was a streak and could be "kept". A number of days is neither a
        # success nor a failure.
        self.history_days_value = ctk.CTkLabel(days_box, text="—",
                                               font=ui_kit.display(22),
                                               text_color=pal["text"], anchor="w")
        self.history_days_value.pack(fill="x")

        # --- detail of one session ---
        # The table below is dense and precise, but a session can only be
        # READ from it. Here it can be SEEN - from the curve saved in the
        # summary.
        dp = ui_kit.Panel(scroll, pal, title=tr("history.detail_title"), right="")
        dp.pack(fill="x", pady=(14, 0))
        self.history_detail_panel = dp
        self.history_detail_index = None      # None = the newest session
        # EMPTY STATE (0.3 batch 4, `ui_kit.EmptyState`): without a session
        # the panel had an empty trace, eleven dashes and the sentence only
        # below them. Now just the sentence - what will appear here
        # (`_history_detail_prazdny`). It is not packed here: only
        # `_refresh_history_detail` shows it.
        self.history_detail_empty = ui_kit.EmptyState(
            dp.body, pal, tr("history.detail_empty"), pady=(18, 18))
        self._history_detail_packy = None
        self.history_detail_trace = ui_kit.SessionTrace(dp.body, pal, height=96)
        self.history_detail_trace.pack(fill="x")
        # The same description as under the chart in the post-session
        # questionnaire - not a new text. The "where you played" strip has to
        # be explained once and the same way; two separate descriptions of
        # the same picture would drift apart over time.
        self.history_detail_legend = ctk.CTkLabel(
            dp.body, text=tr("session.end.trace_hint"), font=ui_kit.ui(10),
            text_color=pal["text_faint"], anchor="w", justify="left",
            wraplength=640)
        self.history_detail_legend.pack(fill="x", pady=(6, 0))
        # ALL values of the selected session (0.2: "History = the whole
        # picture"), in a grid of four per row - eleven cells would not fit
        # in one row. Order and labels in `HISTORY_DETAIL_CELLS`.
        detail_grid = ctk.CTkFrame(dp.body, fg_color="transparent")
        detail_grid.pack(fill="x", pady=(10, 0))
        for col in range(self.HISTORY_DETAIL_COLS):
            detail_grid.grid_columnconfigure(col, weight=1, uniform="detail")
        self.history_detail_cells = {}
        for i, (key, label_key, token) in enumerate(self.HISTORY_DETAIL_CELLS):
            row, col = divmod(i, self.HISTORY_DETAIL_COLS)
            cell = ctk.CTkFrame(detail_grid, fg_color="transparent")
            cell.grid(row=row, column=col, sticky="w", padx=(0, 12),
                      pady=(10, 0) if row else (0, 0))
            ctk.CTkLabel(cell, text=tr(label_key).upper(),
                         font=ui_kit.ui(10, "bold"), text_color=pal["text_faint"],
                         anchor="w").pack(fill="x")
            value = ctk.CTkLabel(cell, text="—", font=ui_kit.display(18),
                                 text_color=pal[token], anchor="w")
            value.pack(fill="x")
            self.history_detail_cells[key] = value
        self.history_detail_hint = ctk.CTkLabel(
            dp.body, text=tr("history.detail_hint"), font=ui_kit.ui(10),
            text_color=pal["text_faint"], anchor="w", justify="left", wraplength=640)
        self.history_detail_hint.pack(fill="x", pady=(10, 0))
        # "DELETE THIS SESSION" (0.3, audit 4): e.g. a 14-hour "session"
        # through a sleeping PC would otherwise push sleeping heart rate into
        # the resting baseline, and the only fix was to delete the whole
        # history. Unobtrusive - on the right under the detail, smaller; the
        # confirmation with date and length (focus on Cancel) is in
        # `delete_history_session` (app_data.py). It does not offer the
        # session that is being recorded right now (`_refresh_history_detail`).
        zmaz_rad = ctk.CTkFrame(dp.body, fg_color="transparent")
        zmaz_rad.pack(fill="x", pady=(10, 0))
        self._history_detail_session = None
        self.history_detail_delete_btn = ui_kit.button(
            zmaz_rad, pal, tr("history.delete_session.btn"), kind="danger", height=28,
            command=lambda: self.delete_history_session(
                getattr(self, "_history_detail_session", None)))
        self.history_detail_delete_btn.pack(side="right")

        # --- sessions table ---
        sp = ui_kit.Panel(scroll, pal, title=tr("history.sessions_title"), right="")
        sp.pack(fill="x", pady=(14, 0))
        self.history_sessions_panel = sp
        self.history_sessions_box = ctk.CTkFrame(sp.body, fg_color="transparent")
        self.history_sessions_box.pack(fill="x")
        # --- export to a spreadsheet ---
        # The data is the player's, so they have to be able to take it. And
        # right by the button a sentence saying the app does not send it
        # anywhere - that is the question everyone asks about an app that
        # measures heart rate.
        export_row = ctk.CTkFrame(sp.body, fg_color="transparent")
        export_row.pack(fill="x", pady=(12, 0))
        self.history_export_btn = ui_kit.button(
            export_row, pal, "  " + tr("history.export_btn"),
            image=self._icon_image("table", 26), compound="left",
            width=210, height=34, command=self.export_sessions_csv)
        self.history_export_btn.pack(side="left")
        self.history_export_note = ctk.CTkLabel(
            export_row, text=tr("history.export_local"), font=ui_kit.ui(10),
            text_color=pal["text_faint"], anchor="w", justify="left", wraplength=470)
        self.history_export_note.pack(side="left", padx=(12, 0))

        infos = ctk.CTkFrame(sp.body, fg_color="transparent")
        infos.pack(fill="x", pady=(10, 0))
        self.history_info_hrr = self._metric_info(infos, pal, "hrr", wrap=640,
                                                  titled=True)
        self.history_info_hrr.pack(fill="x")
        self.history_info_zones = self._metric_info(infos, pal, "zones", wrap=640,
                                                    titled=True)
        self.history_info_zones.pack(fill="x", pady=(10, 0))
        self.history_info_hrpi = self._metric_info(infos, pal, "hrpi", wrap=640,
                                                   titled=True)
        self.history_info_hrpi.pack(fill="x", pady=(10, 0))
        # "Felt · measured" in the detail is two numbers without an arrow
        # and without a verdict - without a sentence about which is which,
        # "6 · 8" would read as "the app claims you are wrong". The chart
        # does not have this metric, so the explanation stands here.
        self.history_info_felt = self._metric_info(infos, pal, "felt_vs_measured", wrap=640,
                                                   titled=True)
        self.history_info_felt.pack(fill="x", pady=(10, 0))

        # --- How it came about: an expandable panel, the author's text +
        # three examples ---
        # (0.2) Instead of a long list of studies - the whole list is in
        # ZDROJE.md.
        sc = ui_kit.Panel(scroll, pal)
        sc.pack(fill="x", pady=(14, 0))
        self.history_science_btn = ctk.CTkButton(
            sc.body, text=f"▸   {tr('origin.title')}", anchor="w",
            fg_color="transparent", hover_color=pal["surface_alt"], text_color=pal["text"],
            font=ui_kit.ui(13, "bold"), command=self._toggle_history_science)
        self.history_science_btn.pack(fill="x")
        self.history_science_body = ctk.CTkFrame(sc.body, fg_color="transparent")
        ctk.CTkLabel(self.history_science_body, text=tr("origin.text"),
                     font=ui_kit.ui(11), text_color=pal["text_dim"], wraplength=640,
                     anchor="w", justify="left").pack(fill="x", pady=(6, 4))
        ctk.CTkLabel(self.history_science_body, text=tr("origin.examples"),
                     font=ui_kit.ui(11), text_color=pal["text_dim"], wraplength=640,
                     anchor="w", justify="left").pack(fill="x", pady=(4, 0))
        # the same mechanism as the Guide: "↗ zdroj" -> webbrowser.open,
        # the list is the same one (guide_content.PHILOSOPHY_SOURCES)
        self.history_source_links = []
        for label, url in origin_sources():
            link = ctk.CTkLabel(self.history_science_body, text=f"↗ {label}",
                                font=ui_kit.ui(10, "underline"), text_color=pal["accent"],
                                anchor="w", justify="left", cursor="hand2", wraplength=640)
            link.pack(fill="x", pady=(2, 0))
            link.bind("<Button-1>", lambda _e, u=url: webbrowser.open(u))
            self.history_source_links.append((link, url))
        ctk.CTkLabel(self.history_science_body, text=tr("origin.full_list"),
                     font=ui_kit.ui(10), text_color=pal["text_faint"], wraplength=640,
                     anchor="w", justify="left").pack(fill="x", pady=(8, 0))

        self._refresh_history_page()

    def _toggle_history_science(self):
        body = self.history_science_body
        if body.winfo_ismapped():
            body.pack_forget()
            self.history_science_btn.configure(text=f"▸   {tr('origin.title')}")
        else:
            body.pack(fill="x", pady=(4, 0))
            self.history_science_btn.configure(text=f"▾   {tr('origin.title')}")

    def _history_sessions(self):
        # `log` passed on purpose: an unreadable history must not pretend to
        # be "no sessions" without a trace (bug B15).
        return [s for s in hr_stats.load_sessions(self.hr_sessions_path,
                                                  log=self.log_threadsafe)
                if isinstance(s, dict)]

    def _world_sessions(self):
        """Sessions of the CURRENT world - only for VIEWS (B3-worlds).

        History, the trend and its band, the table, the rhythm, the detail,
        the cards on Today and the insights show only their own world. The
        algorithm does NOT ask this: the resting baseline comes from all
        sessions (there is one body), the critical heart rate and the load
        threshold only from the play ones (see `_open_hr_session`). Export
        always takes everything."""
        return hr_stats.sessions_in_world(self._history_sessions(), self.world)

    @staticmethod
    def _fmt_minutes(seconds):
        """Time "m:ss", from an hour on "1 h 15 min" (`ui_kit.cas_text`, 0.3
        batch 4b) - "Over the limit" for a long evening showed "75:12",
        which looked like a clock time. The same threshold as the trace
        axis."""
        try:
            total = int(float(seconds or 0))
        except (TypeError, ValueError):
            total = 0
        return ui_kit.cas_text(total)

    @staticmethod
    def _popisok_bucketu(bucket, period):
        """Label of a trend chart column in the app's language (0.3 batch 4b).

        `hr_stats` gives the label via `strftime` ("12.11", "11.2026") -
        that is the date format of one language. Day and week are a short
        date without the year, month is "nov 2026" / "2026年11月", hour and
        year stay as they are."""
        started = bucket.get("started")
        if started is None:
            return bucket.get("label", "")
        if period in (hr_stats.PERIOD_DAY, hr_stats.PERIOD_WEEK):
            return ui_kit.datum_text(started, rok=False)
        if period == hr_stats.PERIOD_MONTH:
            return ui_kit.mesiac_text(started)
        return bucket.get("label", "")

    # ---------- trend: metric + time period (chips) ----------

    def _render_history_metric_info(self):
        """ⓘ explanation under the chart - hence a separate wrap that is torn
        down and built again when the metric switches (InfoRow has no
        setter)."""
        wrap = getattr(self, "history_info_wrap", None)
        if wrap is None or not wrap.winfo_exists():
            return
        for child in wrap.winfo_children():
            child.destroy()
        metric_key = self._METRIC_INFO_KEY.get(self.history_metric, "baseline")
        info = self._metric_info(wrap, self.pal, metric_key, wrap=640)
        info.pack(fill="x")

    def _history_metric_label(self, metric):
        """Display name of a trend metric (the label in the dropdown)."""
        for key, title_key, _c in self.HISTORY_METRICS:
            if key == metric:
                return tr(title_key)
        return tr(self.HISTORY_METRICS[0][1])

    def _set_history_metric(self, metric):
        self.history_metric = metric
        menu = getattr(self, "history_metric_menu", None)
        if menu is not None:
            try:
                menu.set(self._history_metric_label(metric))
            except Exception:
                pass
        self._render_history_metric_info()
        self._refresh_history_trend()

    def _set_history_period(self, period):
        self.history_period = period
        prepinac = getattr(self, "history_period_switch", None)
        if prepinac is not None:
            try:
                prepinac.set(tr(f"history.period.{period}"))
            except Exception:
                pass
            ui_kit.oznac_zvoleny_segment(prepinac, self.pal)
        self._refresh_history_trend()

    def _refresh_history_trend(self):
        """Redraws the trend chart + text for the chosen metric and period.

        The period decides which sessions count (e.g. "Week" = from
        Monday) and into which buckets they are grouped for the chart
        (month -> daily averages, year -> monthly - exactly as in the
        spec); the metric decides which value of a bucket is drawn.
        """
        caption = getattr(self, "history_trend_caption", None)
        if caption is None or not caption.winfo_exists():
            return
        pal = self.pal
        metric = self.history_metric
        period = self.history_period
        # Only the current world - the "usual range" band below too
        # (B3-worlds).
        sessions = self._world_sessions()
        # Rolling window, not a calendar period - see hr_stats.rolling_start_ts
        since = hr_stats.rolling_start_ts(period)
        period_sessions = [s for s in sessions if isinstance(s, dict)
                          and isinstance(s.get("started"), (int, float))
                          and s["started"] >= since]
        bucket_period = hr_stats.CHART_BUCKET_FOR_PERIOD.get(period, period)
        # `bucket_axis` fills in days without a session - without it the axis
        # would shrink and the break would vanish from the chart (see
        # hr_stats.bucket_axis)
        buckets = hr_stats.bucket_axis(
            hr_stats.aggregate_by_period(period_sessions, bucket_period),
            bucket_period, since)
        bucket_key = self._METRIC_BUCKET_KEY[metric]
        # times are in seconds - more readable in minutes on the chart;
        # signal coverage is 0..1 - percent on the chart (see _METRIC_SCALE)
        scale = self._METRIC_SCALE.get(metric, 1.0)
        decimals = self._METRIC_DECIMALS.get(metric, 0)
        # A bucket WITHOUT data is sent as None, not as a skipped point:
        # otherwise Wednesday's break would not show on the chart and Tuesday
        # would shift into its place. The x-axis labels are already computed
        # in the bucket.
        chart_values = [None if b[bucket_key] is None else b[bucket_key] * scale
                        for b in buckets]
        # Axis labels in the date format of the APP'S LANGUAGE (0.3 batch 4b,
        # `ui_kit.datum_text`): "12. 11." / "12 Nov" / "11月12日", not "12.11"
        # everywhere. Via the class: tests call this method on an app dummy.
        labels = [HistoryMixin._popisok_bucketu(b, bucket_period) for b in buckets]
        raw_values = [b[bucket_key] for b in buckets if b[bucket_key] is not None]
        title_key = {k: t for k, t, _c in self.HISTORY_METRICS}[metric]
        color_token = {k: c for k, _t, c in self.HISTORY_METRICS}[metric]
        bars = metric in self._METRIC_BARS

        # "Your usual range" (p25-p75) is computed from the WHOLE history of
        # the WORLD at the same bucket resolution - so that like is compared
        # with like. Without it every point is just a number; with it, it is
        # clear which of them is really off.
        vsetky = hr_stats.aggregate_by_period(sessions, bucket_period)
        band = hr_stats.usual_range([b[bucket_key] * scale for b in vsetky
                                     if b[bucket_key] is not None])

        caption.configure(text=f"{tr(title_key)}  ·  {tr(f'history.unit.{metric}')}")
        # Empty period: one sentence in the middle of the lower chart instead
        # of an empty ~230 px area and a sentence about nothing below it (UX
        # audit).
        prazdne = tr("history.empty_period") if not raw_values else ""
        self.history_trend.set_series(chart_values, labels=labels,
                                      color=pal[color_token], band=band,
                                      band_label=tr("history.band_label"), bars=bars,
                                      decimals=decimals, empty_text=prazdne)

        if len(raw_values) >= 2:
            first_v, last_v = raw_values[0], raw_values[-1]
            if metric == "baseline":
                trend = hr_stats.baseline_trend(period_sessions)
                if not trend["insufficient_span"]:
                    # Numbers in the sentence by language (`i18n.cislo`):
                    # "−2,0", not "-2.0" in a Slovak sentence (0.3, batch 4).
                    delta_text = tr("history.trend_delta", first=int(round(first_v)),
                                    last=int(round(last_v)),
                                    slope=cislo(trend["slope_per_week"], 1, sign=True))
                else:
                    delta_text = tr("history.trend_need_more")
            elif metric == "over":
                delta_text = tr("history.trend_simple_delta",
                                first=cislo(first_v / 60.0, 1), last=cislo(last_v / 60.0, 1))
            elif scale != 1.0 or decimals:
                # new metrics in 0.2: in the same units as the chart
                delta_text = tr("history.trend_simple_delta",
                                first=cislo(first_v * scale, decimals),
                                last=cislo(last_v * scale, decimals))
            else:
                delta_text = tr("history.trend_simple_delta",
                                first=int(round(first_v)), last=int(round(last_v)))
        elif raw_values:
            delta_text = tr("history.sessions_count", n=len(period_sessions))
        else:
            delta_text = ""          # the sentence is already in the chart (`empty_text`)
        self.history_trend_delta.configure(text=delta_text)
        # AN EMPTY LINE TAKES NO SPACE (0.3 batch 4): a chart without data is
        # 80 px and carries the sentence itself (`empty_text`). A CTkLabel
        # with empty text keeps its line height, so another gap was left
        # under the chart.
        riadok = self.history_trend_delta
        try:
            zabaleny = riadok.winfo_manager() == "pack"
            if delta_text and not zabaleny:
                dalsi = getattr(self, "history_info_wrap", None)
                if dalsi is not None and dalsi.winfo_manager() == "pack":
                    riadok.pack(fill="x", pady=(4, 0), before=dalsi)
                else:
                    riadok.pack(fill="x", pady=(4, 0))
            elif not delta_text and zabaleny:
                riadok.pack_forget()
        except Exception:
            pass        # test dummies cannot pack; the page is closing

    def _refresh_history_page(self):
        """Redraws the trend, table and insights from the current files. When
        the page is not built yet (theme switch), does nothing."""
        box = getattr(self, "history_sessions_box", None)
        if box is None or not box.winfo_exists():
            return
        pal = self.pal
        # Only sessions of the current world (B3-worlds); the detail is an
        # index into EXACTLY this list, which is why `set_world` resets it.
        sessions = self._world_sessions()
        note = getattr(self, "history_world_note", None)
        if note is not None:
            # The "which cue works" chart counts only play cues that
            # actually sounded (see `_refresh_cue_effect`) - the sentence
            # must say so, otherwise a page labelled "World: Work" would
            # show play cues without a word.
            note.configure(text=tr("history.world_note",
                                   world=self._world_label(self.world),
                                   chart=tr("history.effect_title")))
        self._refresh_history_trend()

        # table
        for child in box.winfo_children():
            child.destroy()
        self.history_sessions_panel.set_right(tr("history.sessions_count", n=len(sessions)))
        if not sessions:
            ctk.CTkLabel(box, text=tr("history.empty", page=stranka_vhre(self)),
                         font=ui_kit.ui(11),
                         text_color=pal["text_faint"], wraplength=620, anchor="w",
                         justify="left").pack(fill="x")
        else:
            cols = (("col_date", 118), ("col_duration", 62), ("col_avg", 66),
                    ("col_minmax", 84), ("col_over", 86), ("col_triggers", 70),
                    ("col_peak", 92), ("col_hrr", 52), ("col_hrpi", 52))

            # FULL-WIDTH TABLE (0.3, UX audit). The columns had fixed
            # widths and the table ended at two thirds of the panel; the
            # numbers were left-aligned, so units and tens did not line
            # up. Now it is a grid: the width from the list is both the
            # minimum and the weight, so the columns stretch to the full
            # width in the same ratio - the header and every row have
            # the same configuration, which is why they line up. Date on
            # the left, numbers on the right.
            def _stlpce(ramec):
                for i, (_k, sirka) in enumerate(cols):
                    ramec.grid_columnconfigure(i, minsize=sirka, weight=sirka)

            def _zarovnanie(i):
                return "w" if i == 0 else "e"

            head = ctk.CTkFrame(box, fg_color="transparent")
            head.pack(fill="x")
            _stlpce(head)
            for i, (key, width) in enumerate(cols):
                ctk.CTkLabel(head, text=tr(f"history.{key}"), width=width,
                             anchor=_zarovnanie(i), font=ui_kit.ui(10, "bold"),
                             text_color=pal["text_faint"]).grid(
                    row=0, column=i, sticky="ew", padx=(0, 0 if i == 0 else 6))
            ui_kit.linka(box, pal).pack(fill="x")
            for poradie, s in enumerate(reversed(sessions)):
                if poradie >= self.HISTORY_ROWS:
                    break
                index = len(sessions) - 1 - poradie      # index into `sessions`
                vybrana = index == self._history_detail_index(sessions)
                row = ctk.CTkFrame(box, fg_color=pal["surface_alt"] if vybrana
                                   else "transparent", corner_radius=0)
                row.pack(fill="x")
                _stlpce(row)
                started = float(s.get("started") or 0)
                # date in the app's language (0.3 batch 4b), time HH:MM
                date = ui_kit.datum_text(started, cas=True) if started else "-"
                hrr = s.get("hrr_bpm")
                # Cues = the same number as the detail, chart and CSV: only
                # the ones the app sent by itself (`hlasky_relacie`). The old
                # `triggers` also counted the key and the "Test" button.
                hlasky = hr_stats.hlasky_relacie(s)
                # Length as in the detail above the table ("1 h 24 min"), not
                # "84:54" - that looked like a clock time and the same session
                # had two notations on one page (UX audit, batch 4).
                dlzka = s.get("duration_s")
                cells = (date, self._fmt_dlzka(dlzka) if dlzka else "-",
                         str(s.get("avg_bpm") or "-"),
                         f"{s.get('min_bpm') or '-'} / {s.get('max_bpm') or '-'}",
                         self._fmt_minutes(s.get("time_over_s")),
                         str(hlasky) if hlasky is not None else "-",
                         # load is "x/100" everywhere, not percent (UX audit)
                         self._fmt_zataz(s.get("peak_stress"), "-"),
                         f"{int(hrr):+d}" if hrr is not None else "-",
                         str(s.get("hrpi") if s.get("hrpi") is not None else "-"))
                bunky = [row]
                for i, ((key, width), text) in enumerate(zip(cols, cells)):
                    label = ctk.CTkLabel(row, text=text, width=width,
                                         anchor=_zarovnanie(i),
                                         font=ui_kit.mono(10), text_color=pal["text"])
                    label.grid(row=0, column=i, sticky="ew",
                               padx=(0, 0 if i == 0 else 6))
                    bunky.append(label)

                # Hover = `surface_alt`, like the selected row: the row is
                # clickable and without feedback under the mouse you could
                # not tell.
                def _hover(_e=None, r=row, zap=True, vyb=vybrana):
                    try:
                        r.configure(fg_color=self.pal["surface_alt"] if (zap or vyb)
                                    else "transparent")
                    except Exception:
                        pass
                # The row is clickable: it opens the same session in the
                # detail above the table. Every cell has to be bound too - a
                # click on a label does not propagate to the frame.
                for w in bunky:
                    try:
                        w.configure(cursor="hand2")
                    except Exception:
                        pass
                    # `_e=None`, not `_e`: in roughly every second run of
                    # `gui_screenshots.py` this handler was called WITHOUT an
                    # event and Tk logged it as an error
                    # ("missing 1 required positional argument: '_e'").
                    # Who calls it like this I have NOT found out - I only know
                    # it happens after scrolling History, i.e. around the
                    # rebuild of rows in CTkScrollableFrame. The handler does
                    # not use the event (it only needs `index`), so it has no
                    # reason to require it; that makes the error go away, but
                    # the CAUSE is still unknown and I am not pretending it is
                    # not.
                    w.bind("<Button-1>",
                           lambda _e=None, i=index: self._pick_history_session(i))
                    w.bind("<Enter>", lambda _e=None, h=_hover: h(zap=True), add="+")
                    w.bind("<Leave>", lambda _e=None, h=_hover: h(zap=False), add="+")
                ui_kit.linka(box, pal).pack(fill="x")

        self._refresh_history_rhythm(sessions)
        self._refresh_history_detail(sessions)
        self._refresh_cue_effect()
        self._refresh_rebrik_note(sessions)
        self._render_hr_insights()

    def _refresh_rebrik_note(self, sessions):
        """One quiet sentence under the effect chart, when the cue ladder
        (`rebrik.py`) in the displayed world is BELOW the top: what the app
        is doing now, why, and how many sessions are left until the next
        try. At the top nothing - the app has nothing to explain.
        `sessions` are the sessions of the displayed world.
        """
        label = getattr(self, "history_rebrik_note", None)
        if label is None or not label.winfo_exists():
            return
        text = ""
        try:
            stav = rebrik.stupen(sessions, svet=self.world,
                                 styl=getattr(self, "cue_style", None))
            text = self._rebrik_veta(stav)
        except Exception:
            app_log.exception("historia: veta rebrika zlyhala")
        try:
            if text:
                label.configure(text=text)
                label.pack(fill="x", pady=(6, 0))
            else:
                label.pack_forget()
        except Exception:
            pass

    @staticmethod
    def _rebrik_veta(stav):
        """Sentence for the ladder state, or "" at the top."""
        if not stav or stav.get("stupen") == stav.get("vrchol"):
            return ""
        dovod = stav.get("dovod")
        preco = (tr(f"history.rebrik.why.{dovod}")
                 if dovod in rebrik.DOVODY_POD_VRCHOLOM else "")
        kluc = ("history.rebrik.pause" if stav["stupen"] == rebrik.PAUZA
                else "history.rebrik.visual")
        # Without a reason (a stamp after the history was trimmed) two spaces
        # would be left.
        return " ".join(tr(kluc, dovod=preco, n=stav.get("zostava", 0)).split())

    def _refresh_cue_effect(self):
        """Fills the "which cue works" chart.

        Computed ONLY from the loud arm (see `measure.by_category`) - the
        silent windows are the reference for whether a cue works at all,
        not for comparing the categories with each other.

        Since 0.2 (ladder + gate) only cues that really sounded, delivered
        during a pause and from PLAY - at work a cue is only a picture.
        Once there are windows with the gate, only those
        (`measure.by_category`); the sentence under the chart says that a
        drop after a cue is not proof.
        """
        graf = getattr(self, "history_effect", None)
        if graf is None or not graf.winfo_exists():
            return
        try:
            okna = measure.load_windows(self.hr_windows_path)
        except Exception:
            app_log.exception("graf ucinnosti: okna sa nepodarilo nacitat")
            okna = []
        podla = measure.by_category(okna)
        riadky = []
        # Order by `measure.CATEGORIES`, not by which one has the most
        # windows - otherwise the rows would move around on every opening.
        for kat in measure.CATEGORIES:
            udaj = podla.get(kat)
            if udaj is None:
                continue
            riadky.append((tr("cue.category.%s" % kat), udaj["n"],
                           udaj["delta_bpm"], udaj["ci95"], udaj["dost_dat"]))
        graf.set_data(riadky, malo_textu=tr("history.effect_few"))
        try:
            self.history_effect_hint.configure(
                text=tr("history.effect_hint") if riadky
                else tr("history.effect_empty"))
        except Exception:
            pass

    def export_sessions_csv(self):
        """Saves the session history as a table for Excel.

        The data is the player's - the app must not keep it from them in a
        JSON that an ordinary person will not open. Excel opens a CSV with
        a double-click and the app needs no extra library for it (see
        hr_stats.export_sessions_csv).

        Always ALL sessions, from both worlds (B3-worlds) - it is their
        data.
        """
        sessions = self._history_sessions()
        # Notices in the app window (`ui_kit.notify`), not system ones (0.3).
        okno, pal = getattr(self, "root", None), getattr(self, "pal", None)
        if not sessions:
            ui_kit.notify(okno, pal, APP_NAME, tr("history.export_empty"))
            return
        default = time.strftime("zanshin-relacie-%Y-%m-%d.csv")
        path = filedialog.asksaveasfilename(
            parent=self.root, title=tr("history.export_btn"),
            defaultextension=".csv", initialfile=default,
            filetypes=[(tr("history.export_filetype"), "*.csv")])
        if not path:
            return
        try:
            count = hr_stats.export_sessions_csv(
                sessions, path,
                headers=[tr(f"history.export_col.{key}")
                         for key in hr_stats.CSV_COLUMNS])
            dalsie = self._export_podrobnosti(path)
        except Exception as exc:
            app_log.exception("export relacii zlyhal")
            ui_kit.notify(okno, pal, APP_NAME, tr("history.export_failed", err=exc),
                          kind="error")
            return
        self.log(tr("log.sessions_exported", n=count))
        sprava = tr("history.export_done", n=count, path=os.path.basename(path))
        if dalsie:
            sprava += "\n\n" + tr("history.export_extra",
                                   files="\n".join(dalsie))
        ui_kit.notify(okno, pal, APP_NAME, sprava)

    def _export_podrobnosti(self, path):
        """Saves measurement windows and events beside sessions. Returns names.

        WHY THREE FILES AND NOT ONE WORKBOOK
        ------------------------------------
        The three levels of data have different columns and a different
        number of rows - they do not fit into one table. Excel with several
        sheets would mean `openpyxl`, i.e. another dependency in the build;
        the app writes CSV itself and Excel opens it with a double-click.
        That was already the reason for the original session export.

        The names are derived from the file the player chose, so all three
        end up next to each other and with the same date.
        """
        zaklad, _pripona = os.path.splitext(path)
        # "zanshin-relacie-2026-09-18" -> "zanshin-okna-2026-09-18"
        okna_cesta = zaklad.replace("relacie", "okna") + ".csv"
        udal_cesta = zaklad.replace("relacie", "udalosti") + ".csv"
        if okna_cesta == path:
            okna_cesta = zaklad + "-okna.csv"
        if udal_cesta == path:
            udal_cesta = zaklad + "-udalosti.csv"

        von = []
        try:
            okna = measure.load_windows(self.hr_windows_path)
        except Exception:
            okna = []
        if okna and data_io.export_rows_csv(data_io.s_casom(okna), okna_cesta):
            von.append(os.path.basename(okna_cesta))

        udalosti = data_io.read_events(self.hr_events_path)
        if udalosti and data_io.export_rows_csv(data_io.s_casom(udalosti), udal_cesta):
            von.append(os.path.basename(udal_cesta))
        return von

    # ---------- consistency and the detail of one session ----------

    def _history_detail_index(self, sessions):
        """Detail session index: selected, else the newest, else None."""
        if not sessions:
            return None
        index = self.history_detail_index
        if index is None or not 0 <= index < len(sessions):
            return len(sessions) - 1
        return index

    def _pick_history_session(self, index):
        self.history_detail_index = index
        self._refresh_history_page()

    def _refresh_history_rhythm(self, sessions):
        """Day grid + the number of days on which there was some session."""
        grid = getattr(self, "history_daygrid", None)
        if grid is None or not grid.winfo_exists():
            return
        # AT MOST 26 WEEKS, FROM THE FIRST SESSION (0.3, UX audit, batch 4).
        # A whole year (371 days) was 85 % empty - data in seven columns out
        # of 53. The first column is always a Monday, the last one this week.
        tyzdne = self._rytmus_tyzdne(sessions)
        dni = hr_stats.day_activity(
            sessions, days=(tyzdne - 1) * 7 + time.localtime().tm_wday + 1)
        # Months and days in the APP'S language (not Windows') - `strftime`
        # would write in Slovak even to a Japanese player on a Slovak Windows.
        grid.set_days(dni, legend=(tr("history.grid_less"), tr("history.grid_more")),
                      months=tr("history.grid_months").split(),
                      weekdays=tr("history.grid_weekdays").split())
        stitok = getattr(self, "history_days_label", None)
        if stitok is not None:
            stitok.configure(text=tr("history.days_played", weeks=tyzdne).upper())
        # Just the number; the unit is in the label above it
        # ("Dní s reláciou · 26 týž.", "Days with a session · 26 wk").
        # Slovak declines "deň/dni/dní" by count and the app has many
        # languages - a number without a noun is correct in every one of them.
        aktivne = sum(1 for den in dni if den.get("count"))
        self.history_days_value.configure(text=str(aktivne) if aktivne else "—")

    # How many weeks the Consistency grid shows: from the week of the first
    # session, but at least RYTMUS_MIN (otherwise the months above the
    # columns would have nowhere to go) and at most RYTMUS_MAX (half a
    # year; older patterns are in the trend chart).
    RYTMUS_MIN_TYZDNOV = 8
    RYTMUS_MAX_TYZDNOV = 26

    def _rytmus_tyzdne(self, sessions, now=None):
        """Week count (columns) of the Consistency grid for `sessions`."""
        now = time.time() if now is None else now
        zaciatky = [s.get("started") for s in sessions or ()
                    if isinstance(s, dict)
                    and isinstance(s.get("started"), (int, float))]
        if not zaciatky:
            return self.RYTMUS_MIN_TYZDNOV
        dnes = time.localtime(now)
        prvy = time.localtime(min(zaciatky))
        # Monday of this week and of the week of the first session, in days
        # since the epoch (via the calendar day, not seconds - the switch to
        # summer time would otherwise shift the week boundary by an hour)
        dnes_den = int(time.mktime((dnes.tm_year, dnes.tm_mon, dnes.tm_mday,
                                    12, 0, 0, 0, 0, -1)) // 86400) - dnes.tm_wday
        prvy_den = int(time.mktime((prvy.tm_year, prvy.tm_mon, prvy.tm_mday,
                                    12, 0, 0, 0, 0, -1)) // 86400) - prvy.tm_wday
        tyzdne = (dnes_den - prvy_den) // 7 + 1
        return max(self.RYTMUS_MIN_TYZDNOV, min(self.RYTMUS_MAX_TYZDNOV, tyzdne))

    def _refresh_history_detail(self, sessions):
        """One session's curve and numbers - from `curve` saved in the summary.

        Sessions from earlier versions have no curve (the field was added
        later); then the panel does not hide, it just shows that the shape
        of this session can no longer be computed - discarded raw samples
        cannot be recreated afterwards.
        """
        trace = getattr(self, "history_detail_trace", None)
        if trace is None or not trace.winfo_exists():
            return
        index = self._history_detail_index(sessions)
        session = sessions[index] if index is not None else None
        # Which session "Delete this session" deletes - and whether to offer it
        # at all: the one being recorded right now cannot be deleted
        # (`_je_nahravana_relacia`).
        self._history_detail_session = session or None
        tlacidlo = getattr(self, "history_detail_delete_btn", None)
        if tlacidlo is not None:
            try:
                nahravana = bool(session) and self._je_nahravana_relacia(session)
                tlacidlo.configure(state="disabled" if (not session or nahravana)
                                   else "normal")
            except Exception:
                pass
        if not session:
            trace.set_trace([])
            self.history_detail_panel.set_right("")
            for cell in self.history_detail_cells.values():
                cell.configure(text="—")
            self.history_detail_hint.configure(text=tr("history.detail_empty"))
            self._history_detail_prazdny(True)
            return
        self._history_detail_prazdny(False)
        started = float(session.get("started") or 0)
        self.history_detail_panel.set_right(
            ui_kit.datum_text(started, cas=True) if started else "")
        curve = session.get("curve") or []
        # `activity_curve` was added later - older sessions do not have it
        # and then the strip is simply not drawn (see
        # `SessionTrace._draw_activity`).
        trace.set_trace(curve, baseline=session.get("baseline_bpm"),
                        threshold=session.get("critical_bpm"),
                        duration_s=session.get("duration_s") or 0,
                        triggers=session.get("trigger_offsets_s") or [],
                        activity=session.get("activity_curve") or ())
        hodnoty = self._history_detail_values(session)
        for key, cell in self.history_detail_cells.items():
            cell.configure(text=hodnoty.get(key, "—"))
        self.history_detail_hint.configure(
            text=tr("history.detail_hint") if curve else tr("history.detail_no_curve"))

    def _history_detail_prazdny(self, prazdny):
        """The "One session up close" panel without a session = just one
        sentence (0.3 batch 4). An empty trace and eleven dashes under it
        looked like a measurement, not like "nothing yet".

        Hides EVERYTHING packed in the panel (trace, legend, grid, the
        sentence under it) and remembers the order - with the first
        session it puts them back exactly as they were built, however the
        order in `_build_historia_page` may change.

        WARNING ON SCALING: `pack_info()` returns paddings already
        MULTIPLIED by the DPI scale and a CTk widget multiplies them again
        on `pack()` - at 150 % the padding would grow after every empty
        state. That is why what the widget was really packed with is taken
        (`_last_geometry_manager_call`, unmultiplied); a plain tk widget
        has no scaling, for it `pack_info()` is enough."""
        veta = getattr(self, "history_detail_empty", None)
        panel = getattr(self, "history_detail_panel", None)
        if veta is None or panel is None:
            return
        try:
            if prazdny:
                if self._history_detail_packy is None:
                    packy = []
                    for widget in panel.body.pack_slaves():
                        if widget is veta:
                            continue
                        posledne = getattr(widget, "_last_geometry_manager_call", None)
                        if isinstance(posledne, dict) and posledne.get("kwargs") is not None:
                            info = dict(posledne["kwargs"])
                        else:
                            info = dict(widget.pack_info())
                        # the order is kept by the list order itself - links
                        # to neighbours would point at an unpacked widget on
                        # the way back
                        for kluc in ("in", "in_", "before", "after"):
                            info.pop(kluc, None)
                        packy.append((widget, info))
                        widget.pack_forget()
                    self._history_detail_packy = packy
                if veta.winfo_manager() != "pack":
                    veta.pack(fill="x")
            elif self._history_detail_packy is not None:
                veta.pack_forget()
                for widget, info in self._history_detail_packy:
                    widget.pack(**info)
                self._history_detail_packy = None
        except Exception:
            app_log.exception("historia: prazdny stav detailu zlyhal")

    def _history_detail_values(self, session):
        """{cell key: text} for ALL cells of the detail of one session.

        Whatever the session lacks (old version, import, skipped
        questionnaire) is "—", not zero - "we don't know" and "nothing" are
        two different statements.
        """
        def cislo(key):
            v = session.get(key)
            return str(v) if v not in (None, "") else "—"

        hrr = session.get("hrr_bpm")
        try:
            hrr_text = f"{int(hrr):+d}" if hrr is not None else "—"
        except (TypeError, ValueError):
            hrr_text = "—"
        calm = hr_stats.cas_v_pokoji_s(session)
        hlasky = hr_stats.hlasky_relacie(session)
        pokrytie = hr_stats.pokrytie_signalu(session)
        par = hr_stats.citene_a_merane(session)
        duration = session.get("duration_s")
        over = session.get("time_over_s")
        return {
            "duration": self._fmt_dlzka(duration) if duration else "—",
            "avg": cislo("avg_bpm"),
            "max": cislo("max_bpm"),
            "calm": ("—" if calm is None
                     else tr("dashboard.fmt.min", n=int(calm // 60))),
            "over": self._fmt_minutes(over) if over is not None else "—",
            "breath": str(hlasky) if hlasky is not None else "—",
            # load as "x/100" - the same measure as the threshold on the
            # Cues page
            "peak": self._fmt_zataz(session.get("peak_stress"), "—"),
            "hrr": hrr_text,
            "hrpi": cislo("hrpi"),
            "signal": self._fmt_pokrytie(pokrytie),
            "felt": self._fmt_citene_merane(par),
        }

    @staticmethod
    def _fmt_dlzka(seconds):
        """Length "45 min" or "1 h 05 min" - the "Session length" card and the
        session detail in History. A broken value -> "—". The session trace
        axis writes the same text (`ui_kit.dlzka_text`), hence one source."""
        return ui_kit.dlzka_text(seconds)

    @staticmethod
    def _fmt_zataz(value, prazdne="—"):
        """Load 0..100 as "83/100" - in the table and in the session detail
        (0.3, UX audit: once "90 %", once a bare "90", elsewhere "over 55").
        A missing or broken value -> `prazdne`."""
        if value in (None, ""):
            return prazdne
        try:
            return f"{int(round(float(value)))}/100"
        except (TypeError, ValueError, OverflowError):
            return prazdne

    @staticmethod
    def _fmt_pokrytie(pokrytie):
        """Signal coverage 0..1 -> "97 %", None -> "—"."""
        if pokrytie is None:
            return "—"
        return tr("dashboard.fmt.pct", n=int(round(float(pokrytie) * 100)))

    @staticmethod
    def _fmt_citene_merane(par):
        """(felt, measured) -> "6 · 8"; no questionnaire -> "—". Two numbers
        side by side, no difference and no arrow - the app does not know
        which one is "right"."""
        if par is None:
            return "—"
        citene, merane = par
        return f"{citene} · {'—' if merane is None else merane}"

    def _render_hr_insights(self):
        box = getattr(self, "history_insights_box", None)
        if box is None or not box.winfo_exists():
            return
        pal = self.pal
        for child in box.winfo_children():
            child.destroy()
        running = getattr(self, "_hr_analysis_thread", None) is not None \
            and self._hr_analysis_thread.is_alive()
        if running and not self._hr_insights:
            ctk.CTkLabel(box, text=tr("history.analysis_running"), font=ui_kit.ui(11),
                         text_color=pal["text_faint"], anchor="w").pack(fill="x")
        tone_color = {"good": pal["success"], "watch": pal["warn"], "info": pal["accent"]}
        for item in self._hr_insights:
            params = item.get("params") or {}
            try:
                text = tr(f"insight.{item.get('key')}", **params)
            except Exception:
                text = str(item.get("key"))
            farba = tone_color.get(item.get("tone"), pal["accent"])
            row = ctk.CTkFrame(box, fg_color="transparent")
            row.pack(fill="x", pady=2)
            # height=8: CTkFrame has a default requested height of 200 px and
            # the row would stretch to it; this way the strip only fills the
            # height of the text
            ctk.CTkFrame(row, fg_color=farba, width=3, height=8,
                         corner_radius=0).pack(side="left", fill="y", padx=(0, 10))
            ctk.CTkLabel(row, text=text, font=ui_kit.ui(11), text_color=pal["text"],
                         wraplength=600, anchor="w", justify="left").pack(side="left", fill="x",
                                                                          expand=True)
            # "0 of 3 sessions" is a progress state, not an insight - the dots
            # say it sooner than the sentence can be read to the end.
            if item.get("key") == "need_more":
                dots = ctk.CTkFrame(row, fg_color="transparent")
                dots.pack(side="right", padx=(10, 0))
                hotovo = int(params.get("n", 0) or 0)
                treba = int(params.get("need", 0) or 0)
                for i in range(treba):
                    ctk.CTkFrame(dots, width=8, height=8, corner_radius=4,
                                 fg_color=farba if i < hotovo else pal["switch_off"]
                                 ).pack(side="left", padx=2)
            elif params.get("delta") is not None:
                # The difference the insight talks about, as a number - the
                # sentence says why, the number says how much.
                ctk.CTkLabel(row, text=f"{int(params['delta']):+d}",
                             font=ui_kit.mono(12), text_color=farba,
                             anchor="e").pack(side="right", padx=(10, 0))
        # EMPTY STATE (0.3, UX audit): while the only insight is the counter
        # "0 of 3 sessions", "Recompute" and "Analysis from ..." promised a
        # result that cannot exist yet. They are hidden and come back with the
        # first insight.
        len_postup = bool(self._hr_insights) and all(
            i.get("key") == "need_more" for i in self._hr_insights)
        tlacidlo = getattr(self, "history_recompute_btn", None)
        if tlacidlo is not None:
            try:
                if len_postup:
                    tlacidlo.pack_forget()
                elif not tlacidlo.winfo_manager():
                    tlacidlo.pack(side="right")
            except Exception:
                pass
        stamp = None if len_postup else self._hr_insights_at
        if stamp:
            self.history_insights_panel.set_right(tr(
                "history.analysis_stamp",
                when=ui_kit.datum_text(stamp, rok=False, cas=True)))
        else:
            # After a world switch the insights are thrown away - the analysis
            # time of the other world would be misleading next to them.
            self.history_insights_panel.set_right("")

    # ---------- background history analysis ----------

    def run_hr_analysis(self, *_):
        """Runs hr_insights.analyze() in a separate thread - not on the GUI
        thread (the history can have dozens of sessions and the analysis
        must not freeze the window). The result is written to
        hr_insights.json and reaches the UI via ui_call. Runs after start,
        after every saved session, after a world switch and on the
        'Recompute' button.

        Insights are for ONE world - the one that applied at launch
        (B3-worlds). When an analysis is already running, a new one is not
        refused silently: `_hr_analysis_rerun` is recorded and after the
        running one finishes it runs again (see `_po_analyze`). Otherwise,
        after a quick world switch, the other world's insights would stay
        on the screen."""
        existing = getattr(self, "_hr_analysis_thread", None)
        if existing is not None and existing.is_alive():
            self._hr_analysis_rerun = True
            return
        self._hr_analysis_rerun = False
        world = self.world
        sessions_path, insights_path = self.hr_sessions_path, self.hr_insights_path

        def work():
            try:
                sessions = hr_stats.sessions_in_world(
                    hr_stats.load_sessions(sessions_path), world)
                insights = hr_insights.analyze(sessions)
                hr_insights.save_insights(insights_path, insights,
                                          log=self.log_threadsafe, world=world)
            except Exception as exc:
                app_log.exception("HR analyza zlyhala")
                self.log_threadsafe(f"HR analysis failed: {exc}")
                self.ui_call(lambda: self._po_analyze(world))
                return
            self.ui_call(lambda: self._apply_hr_insights(insights, world))

        self._hr_analysis_thread = threading.Thread(target=work, daemon=True,
                                                    name="hr-analysis")
        self._hr_analysis_thread.start()
        self._render_hr_insights()

    def _apply_hr_insights(self, insights, world=None):
        """Analysis result into the UI - only when it is for the CURRENT world.

        A result for another world (switched during the analysis) is thrown
        away and the analysis runs again. `world=None` = the caller does
        not know the world, the result is taken."""
        if world is None or world == self.world:
            self._hr_insights = list(insights or [])
            self._hr_insights_at = time.time()
        self._po_analyze(world)
        self._render_hr_insights()

    def _po_analyze(self, world):
        """Analysis finished (even unsuccessfully). Does it need repeating?

        Yes, when someone has asked for a new one in the meantime
        (`_hr_analysis_rerun`) or when it was for a different world than
        the one that applies now."""
        if self._hr_analysis_rerun or (world is not None and world != self.world):
            self._hr_analysis_rerun = False
            self._naplanuj_analyzu()

    def _naplanuj_analyzu(self):
        """Starts the analysis only ONCE the running thread has finished.

        `_apply_hr_insights` arrives via `ui_call` from inside the thread,
        so the thread may still be alive at that moment - a direct
        `run_hr_analysis` would be refused and the request would be lost.
        So it waits in steps of 100 ms; at most one wait is scheduled at a
        time."""
        if getattr(self, "_hr_rerun_job", None) is not None:
            return
        vlakno = getattr(self, "_hr_analysis_thread", None)
        if vlakno is not None and vlakno.is_alive():
            def znova():
                self._hr_rerun_job = None
                self._naplanuj_analyzu()
            try:
                self._hr_rerun_job = self.root.after(100, znova)
            except Exception:
                self._hr_rerun_job = None
            return
        self.run_hr_analysis()
