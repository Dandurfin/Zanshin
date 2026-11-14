"""Stranka Historia - cast hlavnej appky (DandurfApp z app.py).

HistoryMixin je mixin DandurfApp: app.py ho dedi a cely stav (widgety
stranky Historia, zvolena metrika a obdobie trendu, vybrana relacia v
detaile, postrehy z analyzy a jej vlakno) zije na DandurfApp. Tu su len
metody, ktore s nim pracuju cez `self` - mixin nema __init__ ani vlastne
atributy.

Presunute z app.py bez zmeny:
  * info k metrikam - veta pri cisle s rozbalitelnym vysvetlenim
    (`_metric_info`); pouziva ju aj stranka Dnes v app.py,
  * stranka Historia - stavba stranky, nacitanie historie relacii
    (`_history_sessions`, `_world_sessions` - volaju ich aj ostatne casti
    appky) a format minut,
  * trend: metrika + casove obdobie (chips) - graf trendu, tabulka
    relacii, veta rebrika, graf "ktora hlaska zabera" a export do CSV,
  * pravidelnost a detail jednej relacie - mriezka dni, detail vybranej
    relacie, formaty hodnot (`_fmt_*` pouzivaju aj karty na Dnes v
    app_today.py) a postrehy z analyzy,
  * analyza historie na pozadi - len jej prva cast: spustenie analyzy vo
    vlakne, prevzatie vysledku a jej zopakovanie. Zvysok tej sekcie
    (stavba stranok Nastaveni a V hre, karta senzora tepu) s historiou
    nesuvisi - ostal v app.py pod novou znackou "stranky Nastaveni a V hre".

Konstanty stranky (`HISTORY_ROWS`, `HISTORY_METRICS`, `_METRIC_*`,
`HISTORY_DETAIL_COLS`, `HISTORY_DETAIL_CELLS`) ostali v triede DandurfApp medzi ostatnymi
konstantami triedy - metody ich citaju cez `self`.

Pozor v testoch: `_refresh_history_page`, `export_sessions_csv`,
`_refresh_history_detail`, `_render_hr_insights` a `_apply_hr_insights`
citaju `time` z tohto modulu a `run_hr_analysis` `threading` - falosne
hodiny aj synchronne vlakno treba podstrcit aj tu (`app_history.time`,
`app_history.threading`), nie len na module app.
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

from app_spolocne import app_log


class HistoryMixin:
    """Stranka Historia a analyza historie na pozadi (mixin DandurfApp)."""

    # ---------- info k metrikam ("aby pouzivatel vedel") ----------

    def _metric_info(self, parent, pal, metric, wrap=420, titled=False):
        """Veta pri cisle + rozbalitelne 'co to znamena' (ui_kit.InfoRow).
        Texty su v i18n pod metric.<id>.short / .more - presne znenie zo
        zadania, pre hraca, nie pre lekara.

        `titled=True` da nad vetu meno metriky (metric.<id>.title) - pre
        vysvetlivky pod tabulkou, kde hlavicky stlpcov uz odrolovali a tri
        "ⓘ co to znamena" pod sebou nehovorili, ku ktoremu cislu patria."""
        nazov = tr(f"metric.{metric}.title") if titled else None
        return ui_kit.InfoRow(parent, pal, tr(f"metric.{metric}.short"),
                              tr(f"metric.{metric}.more"), tr("history.info_more"),
                              tr("history.info_less"), wrap=wrap, title=nazov)

    # ---------- stranka Historia ----------

    def _build_historia_page(self, page, pal):
        """Historia relacii tepu: postrehy z analyzy na pozadi, trend
        pokojovej zakladne napriec relaciami, tabulka relacii s metrikami
        z cisteho BPM a panel 'Preco to funguje' so studiami.

        Data: hr_sessions.json (hr_stats.save_session) + hr_insights.json
        (hr_insights.analyze v pozadi). Stranka sa prekresli pri postaveni,
        po ulozeni relacie a po dobehnuti analyzy (_refresh_history_page).
        """
        scroll = ui_kit.stranka_scroll(page, pal)
        scroll.pack(fill="both", expand=True, padx=ui_kit.PAGE_GUTTER, pady=(20, 20))
        self.history_scroll = scroll

        ctk.CTkLabel(scroll, text=tr("history.title"), font=ui_kit.ui(17, "bold"),
                     text_color=pal["text"], anchor="w").pack(fill="x")
        ctk.CTkLabel(scroll, text=tr("history.subtitle"), font=ui_kit.ui(11),
                     text_color=pal["text_dim"], wraplength=680, anchor="w",
                     justify="left").pack(fill="x", pady=(4, 2))
        # Ktory svet stranka ukazuje (B3-worlds). Bez tejto vety by prazdna
        # Praca vyzerala ako stratena historia. Text doplna
        # `_refresh_history_page`, lebo svet sa meni bez prestavby stranky.
        self.history_world_note = ctk.CTkLabel(
            scroll, text="", font=ui_kit.ui(10), text_color=pal["text_faint"],
            wraplength=680, anchor="w", justify="left")
        self.history_world_note.pack(fill="x", pady=(0, 10))

        # --- postrehy (analyza na pozadi) ---
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
        # Vedlajsie tlacidlo, nie chip (chip je len externy odkaz). Kym je
        # jedinym "postrehom" pocitadlo "0 z 3 relacii", nie je co prepocitat
        # a tlacidlo sa skryje (`_render_hr_insights`).
        self.history_recompute_btn = ui_kit.button(foot, pal, tr("history.recompute"),
                                                   command=self.run_hr_analysis,
                                                   height=28)
        self.history_recompute_btn.pack(side="right")

        # --- trend napriec relaciami: metrika + casove obdobie sa daju
        # prepnut, graf aj text sa prekreslia (_refresh_history_trend) ---
        tp = ui_kit.Panel(scroll, pal, title=tr("history.trend_title"))
        tp.pack(fill="x", pady=(14, 0))

        # Dva rady chipov pod sebou vyzerali ako jedna mriezka osmich
        # tlacidiel - z obrazovky sa nedalo precitat, ze horny rad meni CO
        # a dolny ZA AKE OBDOBIE. Popisok vlavo to povie jednym slovom.
        #
        # DVA OVLADACE, NIE DVANAST RAMOV (0.2.2, audit UX). Osem chipov
        # metriky a styri obdobia boli dvanast oramovanych tlacidiel, ktore
        # vizualne prebili graf, ktory ovladaju - a ten isty chip znamenal v
        # appke aj kartu, akciu a odkaz. Metrika je jedna rozbalovacka (vyber
        # jednej z osmich), obdobie jeden segmentovy prepinac (styri vedla
        # seba, jedno zvolene - zvolene nesie text v akcente).
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
        # Veta, nie vypis z konzoly: monospace je len v tabulke a na osiach.
        self.history_trend_delta = ctk.CTkLabel(tp.body, text="", font=ui_kit.ui(12),
                                                text_color=pal["text"], anchor="w")
        self.history_trend_delta.pack(fill="x", pady=(4, 0))
        self.history_info_wrap = ctk.CTkFrame(tp.body, fg_color="transparent")
        self.history_info_wrap.pack(fill="x", pady=(6, 0))
        self._render_history_metric_info()

        # --- ktora hlaska zabera ---
        # Da sa pytat az odkedy sa kategorie striedaju (`measure.next_slot`).
        # Do 18. 9. hrala appka vzdy jednu, takze porovnavat nebolo co.
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
        # REBRIK HLASKY (0.2): jedna ticha veta, len ked sa appka sama
        # stisila pod vrchol - s dovodom. Na vrchole sa nezobrazi vobec
        # (`_refresh_rebrik_note`).
        self.history_rebrik_note = ctk.CTkLabel(
            ep.body, text="", font=ui_kit.ui(10),
            text_color=pal["text_faint"], anchor="w", justify="left",
            wraplength=560)

        # --- pravidelnost: mriezka dni + serie ---
        # Jedina vec na tejto stranke, ktora nehovori o jednej relacii, ale
        # o vzore: vikendy, serie vecerov, tyzden, ked appka lezala vypnuta.
        gp = ui_kit.Panel(scroll, pal, title=tr("history.rhythm_title"), right="")
        gp.pack(fill="x", pady=(14, 0))
        self.history_rhythm_panel = gp
        grid_row = ctk.CTkFrame(gp.body, fg_color="transparent")
        grid_row.pack(fill="x")
        self.history_daygrid = ui_kit.DayGrid(grid_row, pal)
        self.history_daygrid.pack(side="left", fill="x", expand=True)
        # height treba zadat: CTkFrame ma predvolenu ziadanu vysku 200 px a
        # s pack_propagate(False) by si ju panel nechal aj s tromi riadkami
        # textu - pod mriezkou by ostala prazdna tretina panela.
        days_box = ctk.CTkFrame(grid_row, fg_color="transparent", width=150, height=118)
        days_box.pack(side="right", padx=(18, 0))
        days_box.pack_propagate(False)
        # Popisok nesie pocet tyzdnov mriezky - ten sa meni s historiou,
        # preto si ho stranka drzi (`_refresh_history_rhythm`).
        self.history_days_label = ctk.CTkLabel(
            days_box, text=tr("history.days_played",
                              weeks=self.RYTMUS_MAX_TYZDNOV).upper(),
            font=ui_kit.ui(10, "bold"), text_color=pal["text_faint"],
            anchor="w", justify="left", wraplength=150)
        self.history_days_label.pack(fill="x")
        # Farba je `text`, nie `success`: zelena bola z cias, ked to bola
        # seria a dala sa "drzat". Pocet dni nie je uspech ani neuspech.
        self.history_days_value = ctk.CTkLabel(days_box, text="—",
                                               font=ui_kit.display(22),
                                               text_color=pal["text"], anchor="w")
        self.history_days_value.pack(fill="x")

        # --- detail jednej relacie ---
        # Tabulka nizsie je hustá a presna, ale relacia sa z nej da uz len
        # PRECITAT. Tu sa da POZRIET - z krivky ulozenej v suhrne.
        dp = ui_kit.Panel(scroll, pal, title=tr("history.detail_title"), right="")
        dp.pack(fill="x", pady=(14, 0))
        self.history_detail_panel = dp
        self.history_detail_index = None      # None = najnovsia relacia
        # PRAZDNY STAV (0.2.2 davka 4, `ui_kit.EmptyState`): bez relacie bola
        # v paneli prazdna stopa, jedenast pomlciek a veta az pod nimi. Teraz
        # len veta - co sa tu objavi (`_history_detail_prazdny`). Nepakuje
        # sa tu: ukaze ju az `_refresh_history_detail`.
        self.history_detail_empty = ui_kit.EmptyState(
            dp.body, pal, tr("history.detail_empty"), pady=(18, 18))
        self._history_detail_packy = None
        self.history_detail_trace = ui_kit.SessionTrace(dp.body, pal, height=96)
        self.history_detail_trace.pack(fill="x")
        # Ten isty popis ako pod grafom v dotazniku po relacii - nie novy
        # text. Pruh "kde sa hralo" treba vysvetlit raz a rovnako; dva
        # vlastne popisy toho isteho obrazka by sa casom rozisli.
        self.history_detail_legend = ctk.CTkLabel(
            dp.body, text=tr("session.end.trace_hint"), font=ui_kit.ui(10),
            text_color=pal["text_faint"], anchor="w", justify="left",
            wraplength=640)
        self.history_detail_legend.pack(fill="x", pady=(6, 0))
        # VSETKY hodnoty vybranej relacie (0.2: "Historia = cely obraz"),
        # v mriezke po styroch - v jednom rade by sa jedenast buniek
        # nezmestilo. Poradie a popisky v `HISTORY_DETAIL_CELLS`.
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
        # "ZMAZAT TUTO RELACIU" (0.2.2, audit 4): napr. 14-hodinova "relacia"
        # cez uspany PC by inak tlacila spankovy tep do pokojovej zakladne a
        # jedinou napravou bolo zmazat celu historiu. Nenapadne - vpravo pod
        # detailom, mensie; potvrdenie s datumom a dlzkou (fokus na Zrusit) je
        # v `delete_history_session` (app_data.py). Prave nahravanu relaciu
        # neponuka (`_refresh_history_detail`).
        zmaz_rad = ctk.CTkFrame(dp.body, fg_color="transparent")
        zmaz_rad.pack(fill="x", pady=(10, 0))
        self._history_detail_session = None
        self.history_detail_delete_btn = ui_kit.button(
            zmaz_rad, pal, tr("history.delete_session.btn"), kind="danger", height=28,
            command=lambda: self.delete_history_session(
                getattr(self, "_history_detail_session", None)))
        self.history_detail_delete_btn.pack(side="right")

        # --- tabulka relacii ---
        sp = ui_kit.Panel(scroll, pal, title=tr("history.sessions_title"), right="")
        sp.pack(fill="x", pady=(14, 0))
        self.history_sessions_panel = sp
        self.history_sessions_box = ctk.CTkFrame(sp.body, fg_color="transparent")
        self.history_sessions_box.pack(fill="x")
        # --- export do tabulky ---
        # Data su hracove, takze si ich musi vediet zobrat. A hned pri
        # tlacidle aj veta o tom, ze appka ich nikam neposiela - to je
        # otazka, ktoru si pri appke merajucej tep polozi kazdy.
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
        # "Cítené · merané" v detaile su dve cisla bez sipky a bez verdiktu -
        # bez vety o tom, co je co, by sa "6 · 8" citalo ako "appka tvrdi,
        # ze sa mylis". Graf tuto metriku nema, tak vysvetlenie stoji tu.
        self.history_info_felt = self._metric_info(infos, pal, "felt_vs_measured", wrap=640,
                                                   titled=True)
        self.history_info_felt.pack(fill="x", pady=(10, 0))

        # --- Ako to vzniklo: rozbalitelny panel, text autora + tri priklady ---
        # (0.2) Namiesto dlheho zoznamu studii - cely je v ZDROJE.md.
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
        # rovnaky mechanizmus ako Sprievodca: "↗ zdroj" -> webbrowser.open,
        # zoznam je ten isty (guide_content.PHILOSOPHY_SOURCES)
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
        # `log` odovzdaný zámerne: nečitateľná história sa nesmie tváriť ako
        # "žiadne relácie" bez stopy (bug B15).
        return [s for s in hr_stats.load_sessions(self.hr_sessions_path,
                                                  log=self.log_threadsafe)
                if isinstance(s, dict)]

    def _world_sessions(self):
        """Relacie AKTUALNEHO sveta - len pre POHLADY (B3-worlds).

        Historia, trend a jeho pasmo, tabulka, rytmus, detail, karty na Dnes
        a postrehy ukazuju len svoj svet. Algoritmus sa na toto NEPYTA:
        pokojova zakladna ide zo vsetkych relacii (telo je jedno), kriticky
        tep a prah zataze len z hernych (viz `_open_hr_session`). Export
        berie vzdy vsetko."""
        return hr_stats.sessions_in_world(self._history_sessions(), self.world)

    @staticmethod
    def _fmt_minutes(seconds):
        try:
            total = int(float(seconds or 0))
        except (TypeError, ValueError):
            total = 0
        return f"{total // 60}:{total % 60:02d}"

    # ---------- trend: metrika + casove obdobie (chips) ----------

    def _render_history_metric_info(self):
        """ⓘ vysvetlenie pod grafom - preto samostatny wrap, ktory sa pri
        prepnuti metriky zbura a postavi znova (InfoRow nema setter)."""
        wrap = getattr(self, "history_info_wrap", None)
        if wrap is None or not wrap.winfo_exists():
            return
        for child in wrap.winfo_children():
            child.destroy()
        metric_key = self._METRIC_INFO_KEY.get(self.history_metric, "baseline")
        info = self._metric_info(wrap, self.pal, metric_key, wrap=640)
        info.pack(fill="x")

    def _history_metric_label(self, metric):
        """Zobrazovane meno metriky trendu (popisok v rozbalovacke)."""
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
        """Prekresli graf + text trendu podla zvolenej metriky a obdobia.

        Obdobie urcuje, ktore relacie sa poctaju (napr. "Tyzden" = od
        pondelka) a do akych bucketov sa zoskupia pre graf (mesiac -> denne
        priemery, rok -> mesacne - presne ako v zadani); metrika urcuje,
        ktora hodnota bucketu sa vykresli.
        """
        caption = getattr(self, "history_trend_caption", None)
        if caption is None or not caption.winfo_exists():
            return
        pal = self.pal
        metric = self.history_metric
        period = self.history_period
        # Len aktualny svet - aj pasmo "bezne rozpatie" nizsie (B3-worlds).
        sessions = self._world_sessions()
        # Posuvne okno, nie kalendarne obdobie - viz hr_stats.rolling_start_ts
        since = hr_stats.rolling_start_ts(period)
        period_sessions = [s for s in sessions if isinstance(s, dict)
                          and isinstance(s.get("started"), (int, float))
                          and s["started"] >= since]
        bucket_period = hr_stats.CHART_BUCKET_FOR_PERIOD.get(period, period)
        # `bucket_axis` doplni dni bez relacie - bez neho by sa os zmrstila
        # a pauza by z grafu zmizla (viz hr_stats.bucket_axis)
        buckets = hr_stats.bucket_axis(
            hr_stats.aggregate_by_period(period_sessions, bucket_period),
            bucket_period, since)
        bucket_key = self._METRIC_BUCKET_KEY[metric]
        # casy su v sekundach - na grafe citatelnejsie v minutach; pokrytie
        # signalu je 0..1 - na grafe percenta (viz _METRIC_SCALE)
        scale = self._METRIC_SCALE.get(metric, 1.0)
        decimals = self._METRIC_DECIMALS.get(metric, 0)
        # Bucket BEZ dat sa posiela ako None, nie ako vynechany bod: inak
        # by sa stredajsia pauza na grafe nezobrazila a utorok by sa
        # posunul na jej miesto. Popisky osi x su uz spocitane v buckete.
        chart_values = [None if b[bucket_key] is None else b[bucket_key] * scale
                        for b in buckets]
        labels = [b["label"] for b in buckets]
        raw_values = [b[bucket_key] for b in buckets if b[bucket_key] is not None]
        title_key = {k: t for k, t, _c in self.HISTORY_METRICS}[metric]
        color_token = {k: c for k, _t, c in self.HISTORY_METRICS}[metric]
        bars = metric in self._METRIC_BARS

        # "Tvoje bezne rozpatie" (p25-p75) sa rata z CELEJ historie SVETA v
        # tom istom rozliseni bucketov - aby sa porovnavali rovnake veliciny.
        # Bez neho je kazdy bod len cislo; s nim je jasne, ktory z nich je
        # naozaj mimo.
        vsetky = hr_stats.aggregate_by_period(sessions, bucket_period)
        band = hr_stats.usual_range([b[bucket_key] * scale for b in vsetky
                                     if b[bucket_key] is not None])

        caption.configure(text=f"{tr(title_key)}  ·  {tr(f'history.unit.{metric}')}")
        # Prazdne obdobie: jedna veta v strede nizsieho grafu namiesto
        # prazdnej plochy ~230 px a vety o nicom pod nou (audit UX).
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
                    # Cisla vo vete podla jazyka (`i18n.cislo`): "−2,0", nie
                    # "-2.0" v slovenskej vete (0.2.2, davka 4).
                    delta_text = tr("history.trend_delta", first=int(round(first_v)),
                                    last=int(round(last_v)),
                                    slope=cislo(trend["slope_per_week"], 1, sign=True))
                else:
                    delta_text = tr("history.trend_need_more")
            elif metric == "over":
                delta_text = tr("history.trend_simple_delta",
                                first=cislo(first_v / 60.0, 1), last=cislo(last_v / 60.0, 1))
            elif scale != 1.0 or decimals:
                # nove metriky 0.2: v tych istych jednotkach ako graf
                delta_text = tr("history.trend_simple_delta",
                                first=cislo(first_v * scale, decimals),
                                last=cislo(last_v * scale, decimals))
            else:
                delta_text = tr("history.trend_simple_delta",
                                first=int(round(first_v)), last=int(round(last_v)))
        elif raw_values:
            delta_text = tr("history.sessions_count", n=len(period_sessions))
        else:
            delta_text = ""          # veta je uz v grafe (`empty_text`)
        self.history_trend_delta.configure(text=delta_text)
        # PRAZDNY RIADOK NEZABERA MIESTO (0.2.2 davka 4): graf bez dat ma 80 px
        # a vetu nesie sam (`empty_text`). CTkLabel s prazdnym textom si drzi
        # vysku riadku, takze pod grafom ostavala dalsia diera.
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
            pass        # atrapy v testoch nevedia pack; stranka sa zatvara

    def _refresh_history_page(self):
        """Prekresli trend, tabulku a postrehy z aktualnych suborov. Ked
        stranka este nie je postavena (prepnutie temy), nerobi nic."""
        box = getattr(self, "history_sessions_box", None)
        if box is None or not box.winfo_exists():
            return
        pal = self.pal
        # Len relacie aktualneho sveta (B3-worlds); detail je index do
        # PRAVE tohto zoznamu, preto ho `set_world` nuluje.
        sessions = self._world_sessions()
        note = getattr(self, "history_world_note", None)
        if note is not None:
            # Graf "ktora hlaska zabera" rata len herne hlasky, ktore
            # zazneli (viz `_refresh_cue_effect`) - veta to musi povedat,
            # inak by stranka s napisom "Svet: Praca" ukazovala herne hlasky
            # bez slova.
            note.configure(text=tr("history.world_note",
                                   world=self._world_label(self.world),
                                   chart=tr("history.effect_title")))
        self._refresh_history_trend()

        # tabulka
        for child in box.winfo_children():
            child.destroy()
        self.history_sessions_panel.set_right(tr("history.sessions_count", n=len(sessions)))
        if not sessions:
            ctk.CTkLabel(box, text=tr("history.empty"), font=ui_kit.ui(11),
                         text_color=pal["text_faint"], wraplength=620, anchor="w",
                         justify="left").pack(fill="x")
        else:
            cols = (("col_date", 118), ("col_duration", 62), ("col_avg", 66),
                    ("col_minmax", 84), ("col_over", 86), ("col_triggers", 70),
                    ("col_peak", 92), ("col_hrr", 52), ("col_hrpi", 52))

            # TABULKA NA CELU SIRKU (0.2.2, audit UX). Stlpce mali pevne
            # sirky a tabulka koncila v dvoch tretinach panela; cisla boli
            # zarovnane vlavo, takze jednotky a desiatky nesli pod sebou.
            # Teraz je to mriezka: sirka zo zoznamu je minimum a zaroven vaha,
            # takze sa stlpce natiahnu na celu sirku v tom istom pomere -
            # hlavicka aj kazdy riadok maju rovnaku konfiguraciu, preto sedia
            # pod sebou. Datum vlavo, cisla vpravo.
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
                index = len(sessions) - 1 - poradie      # index do `sessions`
                vybrana = index == self._history_detail_index(sessions)
                row = ctk.CTkFrame(box, fg_color=pal["surface_alt"] if vybrana
                                   else "transparent", corner_radius=0)
                row.pack(fill="x")
                _stlpce(row)
                started = float(s.get("started") or 0)
                date = time.strftime("%d.%m.%Y %H:%M", time.localtime(started)) if started else "-"
                hrr = s.get("hrr_bpm")
                # Hlasky = to iste cislo ako detail, graf aj CSV: len tie,
                # ktore appka poslala sama (`hlasky_relacie`). Stare
                # `triggers` ratalo aj klavesu a tlacidlo "Test".
                hlasky = hr_stats.hlasky_relacie(s)
                # Dlzka ako v detaile nad tabulkou ("1 h 24 min"), nie
                # "84:54" - to vyzeralo ako cas a ta ista relacia mala na
                # jednej stranke dva zapisy (audit UX, davka 4).
                dlzka = s.get("duration_s")
                cells = (date, self._fmt_dlzka(dlzka) if dlzka else "-",
                         str(s.get("avg_bpm") or "-"),
                         f"{s.get('min_bpm') or '-'} / {s.get('max_bpm') or '-'}",
                         self._fmt_minutes(s.get("time_over_s")),
                         str(hlasky) if hlasky is not None else "-",
                         # zataz je vsade "x/100", nie percenta (audit UX)
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

                # Hover = `surface_alt`, ako vybrany riadok: riadok je
                # klikatelny a bez odozvy pod mysou to nebolo poznat.
                def _hover(_e=None, r=row, zap=True, vyb=vybrana):
                    try:
                        r.configure(fg_color=self.pal["surface_alt"] if (zap or vyb)
                                    else "transparent")
                    except Exception:
                        pass
                # Riadok je klikatelny: otvori tu istu relaciu v detaile
                # nad tabulkou. Bindovat treba aj kazdu bunku - klik na
                # popisok sa na ramec nepropaguje.
                for w in bunky:
                    try:
                        w.configure(cursor="hand2")
                    except Exception:
                        pass
                    # `_e=None`, nie `_e`: zhruba v kazdom druhom behu
                    # `gui_screenshots.py` sa tento handler zavolal BEZ
                    # udalosti a Tk to zapisalo ako chybu
                    # ("missing 1 required positional argument: '_e'").
                    # Kto ho takto vola, som NEODHALIL - viem len, ze sa to
                    # deje po scrollovani Historie, teda okolo prestavby
                    # riadkov v CTkScrollableFrame. Handler tu udalost
                    # nepouziva (potrebuje len `index`), takze nema dovod ju
                    # vyzadovat; tym chyba zmizne, ale PRICINA je stale
                    # neznama a nerobim, ze nie je.
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
        """Jedna ticha veta pod grafom ucinnosti, ked je rebrik hlasky
        (`rebrik.py`) v zobrazenom svete POD vrcholom: co appka teraz robi,
        preco a kolko relacii chyba do dalsieho pokusu. Na vrchole nic -
        appka nema co vysvetlovat. `sessions` su relacie zobrazeneho sveta.
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
        """Veta pre stav rebrika, alebo "" na vrchole."""
        if not stav or stav.get("stupen") == stav.get("vrchol"):
            return ""
        dovod = stav.get("dovod")
        preco = (tr(f"history.rebrik.why.{dovod}")
                 if dovod in rebrik.DOVODY_POD_VRCHOLOM else "")
        kluc = ("history.rebrik.pause" if stav["stupen"] == rebrik.PAUZA
                else "history.rebrik.visual")
        # Bez dovodu (peciatka po orezani historie) by ostali dve medzery.
        return " ".join(tr(kluc, dovod=preco, n=stav.get("zostava", 0)).split())

    def _refresh_cue_effect(self):
        """Naplni graf "ktora hlaska zabera".

        Pocita sa LEN z hlasneho ramena (viz `measure.by_category`) - tiche
        okna su referencia pre to, ci hlaska funguje vobec, nie pre
        porovnanie kategorii medzi sebou.

        Od 0.2 (rebrik + brana) len hlasky, ktore naozaj zazneli, dorucene
        na pauze a z HRY - v praci je hlaska len obrazom. Ked uz su okna s
        branou, len tie (`measure.by_category`); veta pod grafom hovori, ze
        pokles po hlaske nie je dokaz.
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
        # Poradie podla `measure.CATEGORIES`, nie podla toho, ktora ma
        # najviac okien - inak by sa riadky pri kazdom otvoreni presuvali.
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
        """Ulozi historiu relacii ako tabulku pre Excel.

        Data su hracove - appka mu ich nesmie drzat v JSON-e, ktory bezny
        clovek neotvori. CSV Excel otvori dvojklikom a appka na to
        nepotrebuje ziadnu kniznicu navyse (viz hr_stats.export_sessions_csv).

        Vzdy VSETKY relacie, z oboch svetov (B3-worlds) - su to jeho data.
        """
        sessions = self._history_sessions()
        # Oznamy v okne appky (`ui_kit.notify`), nie systemove (0.2.2).
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
        """Vedla relacii ulozi aj meracie okna a udalosti. Vrati nazvy.

        PRECO TRI SUBORY A NIE JEDEN ZOSIT
        ----------------------------------
        Tri roviny dat maju rozne stlpce aj rozny pocet riadkov - do jednej
        tabulky sa nedaju. Excel s viacerymi harkami by znamenal `openpyxl`,
        teda dalsiu zavislost v builde; CSV appka zapise sama a Excel ho
        otvori dvojklikom. To bol dovod uz pri povodnom exporte relacii.

        Nazvy sa odvodia od suboru, ktory si hrac vybral, takze vsetky tri
        skoncia vedla seba a s rovnakym datumom.
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

    # ---------- pravidelnost a detail jednej relacie ----------

    def _history_detail_index(self, sessions):
        """Index relacie v detaile: vybrana, inak najnovsia, inak None."""
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
        """Mriezka dni + pocet dni, v ktorych nejaka relacia bola."""
        grid = getattr(self, "history_daygrid", None)
        if grid is None or not grid.winfo_exists():
            return
        # NAJVIAC 26 TYZDNOV, OD PRVEJ RELACIE (0.2.2, audit UX, davka 4).
        # Cely rok (371 dni) bol z 85 % prazdny - data v siedmich stlpcoch z
        # 53. Prvy stlpec je vzdy pondelok, posledny tento tyzden.
        tyzdne = self._rytmus_tyzdne(sessions)
        dni = hr_stats.day_activity(
            sessions, days=(tyzdne - 1) * 7 + time.localtime().tm_wday + 1)
        # Mesiace a dni v jazyku APPKY (nie Windowsu) - `strftime` by na
        # slovenskom Windowse pisal po slovensky aj japonskemu hracovi.
        grid.set_days(dni, legend=(tr("history.grid_less"), tr("history.grid_more")),
                      months=tr("history.grid_months").split(),
                      weekdays=tr("history.grid_weekdays").split())
        stitok = getattr(self, "history_days_label", None)
        if stitok is not None:
            stitok.configure(text=tr("history.days_played", weeks=tyzdne).upper())
        # Cislo samo, jednotka je v popisku nad nim ("Dní s reláciou · 26 týž.").
        # Slovencina sklonuje "deň/dni/dní" podla poctu a appka ma vela
        # jazykov - cislo bez podstatneho mena je spravne v kazdom z nich.
        aktivne = sum(1 for den in dni if den.get("count"))
        self.history_days_value.configure(text=str(aktivne) if aktivne else "—")

    # Kolko tyzdnov ukazuje mriezka Pravidelnost: od tyzdna prvej relacie,
    # ale aspon RYTMUS_MIN (inak by mesiace nad stlpcami nemali kam ist) a
    # najviac RYTMUS_MAX (pol roka; starsie vzory su v grafe trendu).
    RYTMUS_MIN_TYZDNOV = 8
    RYTMUS_MAX_TYZDNOV = 26

    def _rytmus_tyzdne(self, sessions, now=None):
        """Pocet tyzdnov (stlpcov) mriezky Pravidelnost pre `sessions`."""
        now = time.time() if now is None else now
        zaciatky = [s.get("started") for s in sessions or ()
                    if isinstance(s, dict)
                    and isinstance(s.get("started"), (int, float))]
        if not zaciatky:
            return self.RYTMUS_MIN_TYZDNOV
        dnes = time.localtime(now)
        prvy = time.localtime(min(zaciatky))
        # pondelok tohto tyzdna a tyzdna prvej relacie, v dnoch od epochy
        # (cez kalendarny den, nie sekundy - prechod na letny cas by inak
        # posunul hranicu tyzdna o hodinu)
        dnes_den = int(time.mktime((dnes.tm_year, dnes.tm_mon, dnes.tm_mday,
                                    12, 0, 0, 0, 0, -1)) // 86400) - dnes.tm_wday
        prvy_den = int(time.mktime((prvy.tm_year, prvy.tm_mon, prvy.tm_mday,
                                    12, 0, 0, 0, 0, -1)) // 86400) - prvy.tm_wday
        tyzdne = (dnes_den - prvy_den) // 7 + 1
        return max(self.RYTMUS_MIN_TYZDNOV, min(self.RYTMUS_MAX_TYZDNOV, tyzdne))

    def _refresh_history_detail(self, sessions):
        """Krivka a cisla jednej relacie - z `curve` ulozenej v suhrne.

        Relacie z predoslych verzii krivku nemaju (pole pribudlo neskor);
        vtedy sa panel neschova, len ukaze, ze tvar tejto relacie sa uz
        dopocitat neda - zahodene surove vzorky sa spatne nevytvoria.
        """
        trace = getattr(self, "history_detail_trace", None)
        if trace is None or not trace.winfo_exists():
            return
        index = self._history_detail_index(sessions)
        session = sessions[index] if index is not None else None
        # Ktoru relaciu zmaze "Zmazat tuto relaciu" - a ci ju vobec ponuknut:
        # prave nahravana sa zmazat neda (`_je_nahravana_relacia`).
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
            time.strftime("%d.%m.%Y %H:%M", time.localtime(started)) if started else "")
        curve = session.get("curve") or []
        # `activity_curve` pribudla neskor - starsie relacie ju nemaju a
        # vtedy sa pruh proste nekresli (viz `SessionTrace._draw_activity`).
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
        """Panel "Relacia zblizka" bez relacie = len jedna veta (0.2.2
        davka 4). Prazdna stopa a jedenast pomlciek pod nou vyzerali ako
        meranie, nie ako "zatial nic".

        Schova VSETKO, co je v paneli zabalene (stopa, legenda, mriezka,
        veta pod nou), a zapamata si poradie - pri prvej relacii ich vrati
        presne tak, ako boli postavene, nech sa uz poradie v
        `_build_historia_page` zmeni akokolvek.

        POZOR NA MIERKU: `pack_info()` vracia okraje uz NASOBENE mierkou DPI
        a CTk widget ich pri `pack()` nasobi znova - pri 150 % by sa okraj
        po kazdom prazdnom stave zvacsil. Preto sa berie to, s cim widget
        naozaj zabalili (`_last_geometry_manager_call`, nenasobene); holy
        tk widget mierku nema, tomu staci `pack_info()`."""
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
                        # poradie drzi samo poradie zoznamu - odkazy na
                        # susedov by pri navrate mierili na nezabaleny widget
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
        """{kluc bunky: text} pre VSETKY bunky detailu jednej relacie.

        Co relacia nema (stara verzia, import, preskoceny dotaznik), je "—",
        nie nula - "nevieme" a "nic" su dve rozne vypovede.
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
            # zataz ako "x/100" - ta ista miera ako prah na strane Hlasky
            "peak": self._fmt_zataz(session.get("peak_stress"), "—"),
            "hrr": hrr_text,
            "hrpi": cislo("hrpi"),
            "signal": self._fmt_pokrytie(pokrytie),
            "felt": self._fmt_citene_merane(par),
        }

    @staticmethod
    def _fmt_dlzka(seconds):
        """Dlzka "45 min" alebo "1 h 05 min" - karta "Dĺžka relácie" aj
        detail relacie v Historii. Pokazena hodnota -> "—". Ten isty text
        pise aj os stopy relacie (`ui_kit.dlzka_text`), preto jeden zdroj."""
        return ui_kit.dlzka_text(seconds)

    @staticmethod
    def _fmt_zataz(value, prazdne="—"):
        """Zataz 0..100 ako "83/100" - v tabulke aj v detaile relacie
        (0.2.2, audit UX: raz "90 %", raz holé "90", inde "nad 55").
        Chybajuca alebo pokazena hodnota -> `prazdne`."""
        if value in (None, ""):
            return prazdne
        try:
            return f"{int(round(float(value)))}/100"
        except (TypeError, ValueError, OverflowError):
            return prazdne

    @staticmethod
    def _fmt_pokrytie(pokrytie):
        """Pokrytie signalu 0..1 -> "97 %", None -> "—"."""
        if pokrytie is None:
            return "—"
        return tr("dashboard.fmt.pct", n=int(round(float(pokrytie) * 100)))

    @staticmethod
    def _fmt_citene_merane(par):
        """(citene, merane) -> "6 · 8"; bez dotaznika "—". Dve cisla vedla
        seba, ziadny rozdiel ani sipka - ktore je "spravne", appka nevie."""
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
            # height=8: CTkFrame ma predvolenu ziadanu vysku 200 px a riadok
            # by sa natiahol na nu; takto prúžok len vyplni vysku textu
            ctk.CTkFrame(row, fg_color=farba, width=3, height=8,
                         corner_radius=0).pack(side="left", fill="y", padx=(0, 10))
            ctk.CTkLabel(row, text=text, font=ui_kit.ui(11), text_color=pal["text"],
                         wraplength=600, anchor="w", justify="left").pack(side="left", fill="x",
                                                                          expand=True)
            # "0 z 3 relácií" je stav postupu, nie postreh - bodky ho
            # povedia skor, nez sa veta docita.
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
                # Rozdiel, o ktorom postreh hovori, ako cislo - veta
                # povie preco, cislo povie kolko.
                ctk.CTkLabel(row, text=f"{int(params['delta']):+d}",
                             font=ui_kit.mono(12), text_color=farba,
                             anchor="e").pack(side="right", padx=(10, 0))
        # PRAZDNY STAV (0.2.2, audit UX): kym je jedinym postrehom pocitadlo
        # "0 z 3 relacii", "Prepocitat" aj "Analyza z ..." slubovali vysledok,
        # ktory este nemoze existovat. Skryju sa, vratia sa s prvym postrehom.
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
                when=time.strftime("%d.%m. %H:%M", time.localtime(stamp))))
        else:
            # Po prepnuti sveta sa postrehy zahodia - cas analyzy druheho
            # sveta by pri nich klamal.
            self.history_insights_panel.set_right("")

    # ---------- analyza historie na pozadi ----------

    def run_hr_analysis(self, *_):
        """Spusti hr_insights.analyze() v samostatnom vlakne - nie na GUI
        vlakne (historia moze mat desiatky relacii a analyza nesmie
        zaseknut okno). Vysledok sa zapise do hr_insights.json a do UI sa
        dostane cez ui_call. Bezi po starte, po kazdej ulozenej relacii,
        po prepnuti sveta a na tlacidlo 'Prepocitat'.

        Postrehy su za JEDEN svet - ten, ktory platil pri spusteni
        (B3-worlds). Ked uz analyza bezi, nova sa neodmietne potichu:
        zapise sa `_hr_analysis_rerun` a po dobehnuti bezucej sa spusti
        znova (viz `_po_analyze`). Inak by po rychlom prepnuti sveta
        ostali na obrazovke postrehy druheho sveta."""
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
        """Vysledok analyzy do UI - len ked je za AKTUALNY svet.

        Vysledok za iny svet (prepnuty pocas analyzy) sa zahodi a analyza
        sa spusti znova. `world=None` = volajuci svet nepozna, berie sa."""
        if world is None or world == self.world:
            self._hr_insights = list(insights or [])
            self._hr_insights_at = time.time()
        self._po_analyze(world)
        self._render_hr_insights()

    def _po_analyze(self, world):
        """Dobehla analyza (aj neuspesna). Treba ju zopakovat?

        Ano, ked medzitym niekto poziadal o novu (`_hr_analysis_rerun`) alebo
        ked bola za iny svet, nez aky plati teraz."""
        if self._hr_analysis_rerun or (world is not None and world != self.world):
            self._hr_analysis_rerun = False
            self._naplanuj_analyzu()

    def _naplanuj_analyzu(self):
        """Spusti analyzu, AZ KED dobehne bezuce vlakno.

        `_apply_hr_insights` prichadza cez `ui_call` zvnutra vlakna, takze
        vlakno moze byt v tej chvili este nazive - priame `run_hr_analysis`
        by sa odmietlo a poziadavka by sa stratila. Caka sa preto po 100 ms;
        naplanovane je najviac jedno cakanie naraz."""
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
