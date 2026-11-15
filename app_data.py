"""Data hraca - cast hlavnej appky (DandurfApp z app.py).

DataMixin je mixin DandurfApp: app.py ho dedi a cely stav (cesty k suborom,
relacia, profily, sloty, widgety) zije na DandurfApp. Tu su len metody, ktore
s nim pracuju cez `self` - mixin nema __init__ ani vlastne atributy.

Dve sekcie presunute z app.py bez zmeny:
  * data: mazanie, export, import (faza 4) - panely Data a O appke,
    export/import/mazanie historie a co sa ulozi na konci merania (suhrn
    relacie, meracie okna, dotaznik kontextu, promocia),
  * import / export profilov (zdielanie kodom) - profil ako kod do schranky
    a odstranenie slotov navyse.

Pozor v testoch: `_close_hr_session`, `_suhrn_relacie` a `_maybe_graduate`
citaju `time` z tohto modulu - falosne hodiny treba podstrcit aj tu
(`app_data.time`), nie len na module app.

Od 0.2.2 tu je aj ochrana relacie mimo normalneho zatvorenia: vypnutie
Windows (`_pri_vypinani_windows`), kontrolny bod kazdych 5 minut
(`_zapis_rozpracovanu_relaciu`) a jeho obnova pri starte
(`_obnov_rozpracovanu_relaciu`).
"""

import base64
import json
import os
import re
import sys
import time
import webbrowser
from tkinter import filedialog

import customtkinter as ctk

import data_io
import display
import guide_content
import hr_insights
import hr_stats
import measure
import rebrik
import trigger
import ui_kit
from i18n import tr
from paths import APP_NAME, DATA_DIR, legacy_data_dirs, stara_instalacia
from settings_model import (doplnit_kategorie, je_kategoria, mode_labels,
                            slot_na_zdielanie, slot_zo_zdielania)
from ui_dialogs import ImportDataDialog, ImportProfileDialog, SessionEndDialog

from app_spolocne import app_log

# Kontrolny bod otvorenej relacie (`_zapis_rozpracovanu_relaciu`). Viac
# by pri pade stratilo dlhy koniec vecera, menej by zapisovalo na disk
# zbytocne casto uprostred hrania.
ROZPRACOVANA_KAZDYCH_MS = 5 * 60 * 1000
# Po WM_SAVE_YOURSELF: ak proces o tolkoto este zije, vypnutie Windows sa
# zrusilo (`_po_zrusenom_vypnuti`). Bezne vypnutie proces ukonci skor.
VYPNUTIE_ZRUSENE_MS = 20 * 1000
# Upozornenie na nainstalovanu 0.2 az ked okno stoji a dobehol start.
STARA_INSTALACIA_MS = 1500


_CESTA_V_TEXTE = re.compile(r"(?:[A-Za-z]:|\\\\)[\\/][^'\"\n]*")


def bez_ciest(text):
    """Chybova sprava bez celych ciest - zostane len meno suboru.

    "[Errno 13] Permission denied: 'C:\\Users\\<ucet>\\...\\hr_sessions.json'"
    by do dennika aj do app.log vyniesla meno uctu vo Windows (PRIVACY.md)."""
    return _CESTA_V_TEXTE.sub(
        lambda z: os.path.basename(z.group(0).rstrip("\\/")) or "…", str(text or ""))


def _ak_vies(app, meno, *args, **kwargs):
    """Zavola `app.<meno>(...)`, ked ho `app` ma - inak nic.

    Zatvorenie relacie (`_close_hr_session`) bezi v testoch aj na atrapach
    so styrmi atributmi. Doplnky 0.2.2 (neulozena relacia, vypnute "Zmazat")
    ich nesmu zhodit - a chyba v nich nesmie zhodit ukladanie relacie."""
    fn = getattr(app, meno, None)
    if not callable(fn):
        return None
    try:
        return fn(*args, **kwargs)
    except Exception:
        app_log.exception("%s zlyhal", meno)
        return None


class DataMixin:
    """Data hraca, koniec relacie a zdielanie profilov (mixin DandurfApp)."""

    # ---------- data: mazanie, export, import (faza 4) ----------

    def _build_data_panel(self, parent, pal):
        panel = ui_kit.Panel(parent, pal, title=tr("data.title"))
        panel.pack(fill="x")
        ctk.CTkLabel(panel.body, text=tr("data.hint"), font=ui_kit.ui(11),
                     text_color=pal["text_dim"], anchor="w",
                     justify="left", wraplength=560).pack(fill="x", pady=(0, 12))

        # HIERARCHIA TLACIDIEL (0.2.2, audit UX). "Zmazat historiu" vyzeralo
        # presne ako "Importovat" a stalo hned vedla - najnebezpecnejsia
        # akcia appky ako neutralna. Teraz: export a import su vedlajsie
        # tlacidla (ram >= 3:1), zmazanie je `danger` (ram aj text v cervenej)
        # a odsadene o 24 px, aby sa netrafilo omylom.
        rad = ctk.CTkFrame(panel.body, fg_color="transparent")
        rad.pack(fill="x")
        # "Otvorit priecinok s datami" (0.2.2): zalohy pred importom, odlozeny
        # pokazeny subor nastaveni aj neulozena relacia lezia tam - a hrac sa
        # k nim inak nevedel dostat.
        for text, prikaz in ((tr("data.export.btn"), self.export_all_json),
                             (tr("data.import.btn"), self.import_all_json),
                             (tr("data.open_folder.btn"), self.open_data_folder)):
            ui_kit.button(rad, pal, text, command=prikaz,
                          height=32).pack(side="left", padx=(0, 8))
        self.data_delete_btn = ui_kit.button(rad, pal, tr("data.delete.btn"), kind="danger",
                                             command=self.delete_history, height=32)
        self.data_delete_btn.pack(side="left", padx=(16, 0))
        # Preco je "Zmazat" vypnute (pocas sledovania). Nepakuje sa, kym nie
        # je co povedat - rovnako ako `data_note` nizsie.
        self.data_delete_reason = ctk.CTkLabel(
            panel.body, text="", font=ui_kit.ui(11), text_color=pal["text_dim"],
            anchor="w", justify="left", wraplength=560)
        self._refresh_data_delete_state()

        # Vysledok exportu/importu. Prazdny riadok sa NEPAKUJE - prazdny
        # CTkLabel je vysoky ako riadok textu a pod tlacidlami ostavala
        # nevysvetlena medzera. Ukaze sa az s prvou spravou (`_data_note`).
        self.data_note = ctk.CTkLabel(panel.body, text="", font=ui_kit.ui(11),
                                      text_color=pal["text_dim"], anchor="w",
                                      justify="left", wraplength=560)

    def show_about(self):
        """Tlacidlo "A" v titulkovej liste: otvor Nastavenia a skoc na O appke.

        Posun sa robi az po prekresleni (`after`), lebo pred nim este nemá
        `winfo_y()` co vratit - stranka nie je rozlozena a sekcia by skoncila
        na nahodnom mieste.
        """
        self._navigate("vseobecne")
        self.root.after(80, self._scroll_to_about)

    def _scroll_to_about(self):
        self._posun_vseobecne_na(getattr(self, "about_panel", None))

    def _posun_vseobecne_na(self, panel):
        """Posunie stranku Vseobecne tak, aby `panel` bol hore. Spolocne pre
        ⓘ (O appke) aj ⚙ pri "Tep v hre" (sekcia panela s tepom)."""
        wrap = getattr(self, "vseobecne_wrap", None)
        if panel is None or wrap is None:
            return
        try:
            canvas = getattr(wrap, "_parent_canvas", None)
            if canvas is None:
                return
            wrap.update_idletasks()
            vyska = float(max(1, wrap.winfo_height()))
            canvas.yview_moveto(max(0.0, min(1.0, panel.winfo_y() / vyska)))
        except Exception:
            # Skrolovanie je pohodlie, nie funkcia. Ked sa nepodari, hrac je
            # aspon na spravnej stranke - to je stale lepsie nez vynimka.
            app_log.debug("posun na sekciu Vseobecne zlyhal", exc_info=True)

    def _build_about_panel(self, parent, pal):
        """Preco appka vznikla a kde najst autora.

        Text je osobny a zamerne nie je v Sprievodcovi: Sprievodca hovori,
        ako to funguje a preco to funguje. Toto hovori, PRECO to vobec
        existuje - a to je ina otazka aj iny hlas.
        """
        panel = ui_kit.Panel(parent, pal, title=tr("about.title"))
        panel.pack(fill="x", pady=(14, 0))
        self.about_panel = panel

        ctk.CTkLabel(panel.body, text=tr("about.lead"),
                     font=ui_kit.ui(12, "bold"), text_color=pal["text"],
                     anchor="w", justify="left", wraplength=560).pack(fill="x")
        ctk.CTkLabel(panel.body, text=tr("about.body"), font=ui_kit.ui(11),
                     text_color=pal["text_dim"], anchor="w", justify="left",
                     wraplength=560).pack(fill="x", pady=(6, 8))

        # ODKAZY HNED ZA VETOU, ktora na ne ukazuje (0.2.2, audit UX). Veta
        # "...zastav sa u nas:" koncila dvojbodkou, za ktorou bolo ~50 px
        # prazdna a dalsia sekcia - odkazy prisli az pod nou s vlastnym
        # nadpisom. Chip je tu spravne: je to externy odkaz (jediny druh,
        # pre ktory chip ostava). Sipka napovie, ze to otvori prehliadac -
        # rovnaky mechanizmus ako zdroje v Sprievodcovi a v Historii.
        rad = ctk.CTkFrame(panel.body, fg_color="transparent")
        rad.pack(fill="x", pady=(0, 16))
        for nazov, url in guide_content.COMMUNITY_LINKS:
            ui_kit.chip(rad, pal, "\u2197 " + nazov,
                        lambda u=url: webbrowser.open(u)).pack(
                side="left", padx=(0, 8))

        # NAJHLBSIA VRSTVA "PRECO" - pre toho, kto cita medzi riadkami.
        # Nie pribeh autora, ale co appka NAOZAJ meria: medzeru medzi meranym
        # a citenym. Zamerne tlmene (text_faint, tenka ciara) - kto cita pomaly
        # a az sem, najde to sam. To je cely zmysel: appka je nastroj na tu
        # medzeru, nie na cislo.
        ui_kit.linka(panel.body, pal).pack(fill="x", pady=(2, 12))
        ctk.CTkLabel(panel.body, text=tr("about.between_lines"), font=ui_kit.ui(11),
                     text_color=pal["text_faint"], anchor="w", justify="left",
                     wraplength=560).pack(fill="x", pady=(0, 4))

        # COPYRIGHT A LICENCIA VIDITELNE, nie zahrabane v subore LICENSE.
        #
        # GPLv3 odporuca, aby interaktivny program vypisal kratke oznamenie
        # o autorstve a zaruke. Hlavne je to ale slub hracovi: appka mu
        # priamo v okne hovori, pod cim ju dostal a co s nou smie robit.
        ui_kit.linka(panel.body, pal).pack(fill="x", pady=(16, 10))
        # Verzia sa berie z `app.version_short`, nie zadrôtovaná - inak sa pri
        # ďalšom bumpe rozíde s titulkom (B27).
        ctk.CTkLabel(panel.body,
                     text=tr("about.copyright", version=tr("app.version_short")),
                     font=ui_kit.ui(10), text_color=pal["text_faint"],
                     anchor="w", justify="left", wraplength=560).pack(fill="x")

    def _refresh_data_delete_state(self):
        """"Zmazat historiu" je pocas otvorenej relacie VYPNUTE (0.2.2).

        Beziaca relacia sa uklada az pri zatvoreni - po zmazani by sa hned
        znova zapisala do prazdnej historie (a s nou aj jej kontrolny bod).
        Veta pod tlacidlom povie preco; po zastaveni sledovania sa tlacidlo
        vrati. Vola sa pri otvoreni a zatvoreni relacie."""
        btn = getattr(self, "data_delete_btn", None)
        if btn is None:
            return
        bezi = bool(getattr(self, "_hr_session_open", False))
        dovod = getattr(self, "data_delete_reason", None)
        try:
            btn.configure(state="disabled" if bezi else "normal")
            if dovod is not None:
                if bezi:
                    dovod.configure(text=tr("data.delete.stop_first"))
                    if not dovod.winfo_manager():
                        dovod.pack(fill="x", pady=(8, 0), after=btn.master)
                elif dovod.winfo_manager():
                    dovod.pack_forget()
        except Exception:
            pass            # panel sa prave prestavuje

    def open_data_folder(self):
        """Otvori priecinok s datami v Prieskumnikovi (`os.startfile`).

        Tam su zalohy pred importom, odlozene pokazene subory aj relacia,
        ktoru sa nepodarilo ulozit. Cesta sa do dennika nepise - v %APPDATA%
        nesie meno uctu (PRIVACY.md)."""
        try:
            os.startfile(DATA_DIR)
        except Exception:
            app_log.exception("priecinok s datami sa nepodarilo otvorit")
            self._data_note(tr("data.open_folder.failed"))

    def _data_note(self, text):
        widget = getattr(self, "data_note", None)
        if widget is not None:
            try:
                widget.configure(text=text)
                if text and not widget.winfo_manager():
                    widget.pack(fill="x", pady=(10, 0))
            except Exception:
                pass
        self.log(text)

    def export_all_json(self):
        """Cela historia aj meracie okna do jedneho suboru."""
        cesta = filedialog.asksaveasfilename(
            defaultextension=".json", initialfile="zanshin-export.json",
            filetypes=[("JSON", "*.json")])
        if not cesta:
            return
        try:
            bundle = data_io.build_bundle(
                self._history_sessions(),
                measure.load_windows(self.hr_windows_path),
                hr_insights.load_insights(self.hr_insights_path),
                app_version=tr("app.version_short"))
            data_io.write_bundle(cesta, bundle)
            self._data_note(tr("data.export.done", path=cesta))
        except Exception as exc:
            app_log.exception("export zlyhal")
            self._data_note(str(exc))

    def import_all_json(self):
        """Jedine miesto, kam vstupuje cudzi subor.

        Prisny parser je v `data_io`; tu sa uz len pyta zlucit/nahradit
        (vlastny dialog `ImportDataDialog`) a zapisuje sa vysledok.
        """
        cesta = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not cesta:
            return
        try:
            sessions, windows, zahodene = data_io.parse_bundle(cesta)
        except data_io.ImportError_ as exc:
            self._data_note(tr(str(exc)))
            return
        except Exception as exc:
            app_log.exception("import zlyhal")
            self._data_note(str(exc))
            return

        sprava = tr("data.import.found", sessions=len(sessions), windows=len(windows))
        if zahodene:
            sprava += "\n" + tr("data.import.dropped", n=zahodene)
        sprava += "\n\n" + tr("data.import.flagged")
        sprava += "\n\n" + tr("data.import.question")
        # Vlastny dialog, nie systemovy askyesnocancel: ten mal tlacidla
        # Ano/Nie v jazyku Windowsu a volby natvrdo v texte ("= Ano"), takze
        # v inom jazyku nesedeli. Nahradit ide az na druhe potvrdenie.
        ImportDataDialog(self, sprava, lambda volba: self._zapis_import(
            sessions, windows, nahradit=(volba == "replace")))

    def _zapis_import(self, sessions, windows, nahradit):
        """Zapise vysledok importu. Najprv ZALOHA oboch suborov (aj pri
        zluceni - aj to ich prepisuje), potom atomicky zapis. Hlasi sa
        pocet zaznamov zo suboru, ktore v historii naozaj pribudli."""
        try:
            orez = {}
            relacie, okna, n_relacii, n_okien = data_io.vysledok_importu(
                self._history_sessions(), measure.load_windows(self.hr_windows_path),
                sessions, windows, nahradit,
                max_s=hr_stats.MAX_SESSIONS, max_w=measure.MAX_WINDOWS, info=orez)
            zalohy = data_io.zaloha_pred_importom(
                [self.hr_sessions_path, self.hr_windows_path])
            data_io.zapis_zoznam(self.hr_sessions_path, relacie)
            data_io.zapis_zoznam(self.hr_windows_path, okna)
            self._history_cache = (0.0, None)
            self._refresh_history_page()
            sprava = tr("data.import.done", sessions=n_relacii, windows=n_okien)
            if orez.get("vypadlo"):
                # STROP HISTORIE (0.2.2): najstarsie relacie nad MAX_SESSIONS
                # vypadli - doteraz potichu. Vlastne su v zalohe pred importom,
                # zo suboru ostavaju v importovanom subore.
                sprava += "\n" + tr("data.import.limit", max=hr_stats.MAX_SESSIONS,
                                    n=orez["vypadlo"])
            if zalohy:
                # len mena suborov - cela cesta v %APPDATA% nesie meno uctu
                sprava += "\n" + tr("data.import.backup", files=", ".join(
                    os.path.basename(z) for z in zalohy))
                sprava += " " + tr("data.import.backup_where")
            self._data_note(sprava)
        except Exception as exc:
            app_log.exception("zapis importu zlyhal")
            self._data_note(str(exc))

    def delete_history(self):
        """Zmaze historiu. MUSI presne vymenovat, co zmize.

        Sub "vsetko ostava u teba" znamena aj to, ze "zmazat" naozaj
        zmaze - a to sa da ukazat len menovite.
        """
        # Stare priecinky po premenovani appky: migracia z nich historiu len
        # KOPIROVALA, takze tam ostala druha kopia - maze sa aj ta a dialog
        # ju menuje (jeden riadok na priecinok, viz data_io.plan_riadky).
        stare = legacy_data_dirs()
        plan = data_io.delete_plan(DATA_DIR, legacy_dirs=stare)
        riadky = []
        for polozka in data_io.plan_riadky(plan):
            meno = tr(polozka["label"], **polozka["params"])
            if not polozka["exists"]:
                riadky.append(f"  · {meno} — {tr('data.delete.empty')}")
            else:
                riadky.append(f"  · {meno} — {polozka['bytes'] / 1024:.0f} kB")
        # POCAS SLEDOVANIA NIE (0.2.2): beziaca relacia by sa pri zatvoreni
        # hned znova ulozila do prazdnej historie. Tlacidlo je vtedy vypnute
        # (`_refresh_data_delete_state`); toto je poistka pre Ctrl+K a pod.
        if getattr(self, "_hr_session_open", False):
            self._data_note(tr("data.delete.stop_first"))
            return
        # Potvrdenie v okne appky, nie systemovy dialog: tlacidlo nesie
        # sloveso "Zmazat historiu" a je cervene, nie "Ano". TRI VOLBY
        # (0.2.2, audit): "Najprv exportovat..." spusti export a otazka sa
        # vrati - zmazat sa tak da az s kopiou v ruke. Predvolene (fokus,
        # Enter, Escape) je Zrusit.
        text = tr("data.delete.intro") + "\n\n" + "\n".join(riadky)
        while True:
            volba = self._spytaj_zmazanie(text)
            if volba == "export":
                self.export_all_json()
                continue
            if volba != "delete":
                return
            break
        if getattr(self, "_hr_session_open", False):
            # sledovanie sa zaplo, kym bola otazka otvorena (napr. auto-profil)
            self._data_note(tr("data.delete.stop_first"))
            return
        pocet = data_io.delete_all(DATA_DIR, log=self.log_threadsafe,
                                   legacy_dirs=stare)
        self._history_cache = (0.0, None)
        self._hr_insights = []
        try:
            self._refresh_history_page()
        except Exception:
            app_log.exception("historia: prekreslenie po mazani zlyhalo")
        self._data_note(tr("data.delete.done", n=pocet))

    def _spytaj_zmazanie(self, text):
        """Otazka pred zmazanim celej historie: "delete" / "export" / "cancel".

        `ui_kit.choose` (tri tlacidla v okne appky, fokus na Zrusit); bez neho
        aspon `ui_kit.confirm` - potom bez volby exportu."""
        choose = getattr(ui_kit, "choose", None)
        if callable(choose):
            return choose(
                self.root, self.pal, tr("data.delete.title"), text,
                [("delete", tr("data.delete.btn"), "danger"),
                 ("export", tr("data.delete.export_first"), "secondary"),
                 ("cancel", tr("common.cancel"), "secondary")],
                cancel="cancel", default="cancel")
        ano = ui_kit.confirm(self.root, self.pal, tr("data.delete.title"), text,
                             ok_label=tr("data.delete.btn"),
                             cancel_label=tr("common.cancel"), danger=True)
        return "delete" if ano else "cancel"

    def delete_history_session(self, session):
        """Zmaze JEDNU ulozenu relaciu z historie (detail v Historii, 0.2.2).

        Napr. 14-hodinova "relacia" cez uspany PC: spankovy tep by inak tlacil
        pokojovu zakladnu a jedinou napravou bolo zmazat celu historiu.
        Potvrdenie menuje datum a dlzku (fokus na Zrusit). Po zmazani sa
        postrehy prepocitaju rovnako ako tlacidlom "Prepocitat" (zakladna,
        hranica a prah sa beru z historie pri dalsej relacii) a stranka sa
        prekresli. Prave nahravana relacia v historii este nie je - a keby
        tam jej `started` bol, appka ju zmazat neponukne."""
        if not isinstance(session, dict) or session.get("started") is None:
            return False
        if self._je_nahravana_relacia(session):
            return False
        try:
            started = float(session.get("started"))
            time.localtime(started)         # cas mimo rozsahu -> vynimka
            # datum v jazyku appky, ako tabulka v Historii (0.2.2 davka 4b)
            kedy = ui_kit.datum_text(started, cas=True)
        except (TypeError, ValueError, OverflowError, OSError):
            return False
        dlzka = self._fmt_dlzka(session.get("duration_s"))
        if not ui_kit.confirm(
                self.root, self.pal, tr("history.delete_session.title"),
                tr("history.delete_session.body", date=kedy, duration=dlzka),
                ok_label=tr("history.delete_session.btn"),
                cancel_label=tr("common.cancel"), danger=True):
            return False
        if not hr_stats.delete_session(self.hr_sessions_path, started,
                                       log=self.log_threadsafe):
            self.log(tr("history.delete_session.failed"))
            return False
        # Meracie okna tej relacie idu s nou - inak by jej hlasky dalej
        # vstupovali do grafu "ktora pripomienka zabera".
        try:
            okna = measure.load_windows(self.hr_windows_path)
            ostava = [w for w in okna if not (
                isinstance(w, dict) and w.get("session_started") is not None
                and abs(float(w["session_started"]) - started) < 0.11)]
            if len(ostava) != len(okna):
                data_io.zapis_zoznam(self.hr_windows_path, ostava)
        except Exception:
            app_log.exception("historia: meracie okna zmazanej relacie ostali")
        self.log(tr("log.session_deleted", date=kedy))
        self.history_detail_index = None
        self._history_cache = (0.0, None)
        try:
            self._refresh_history_page()
        except Exception:
            app_log.exception("historia: prekreslenie po zmazani relacie zlyhalo")
        # To iste ako "Prepocitat" (`history_recompute_btn`).
        self.run_hr_analysis()
        return True

    def _je_nahravana_relacia(self, session):
        """Je to relacia, ktora sa prave nahrava? Tu sa zmazat neda."""
        if not getattr(self, "_hr_session_open", False):
            return False
        try:
            return abs(float(session.get("started"))
                       - float(self.hr_stats.session_start)) < 1e-3
        except (TypeError, ValueError, AttributeError):
            return False

    def _ask_session_context(self, summary):
        """Opyta sa, co sa pri relacii dialo. Otvara sa az PO ulozeni
        relacie - dotaznik sa pripaja k zaznamu, ktory uz existuje.

        Kratke relacie sa neukladaju vobec, takze sa na ne ani nepytame:
        volajuci to riesi tym, ze sem vojde len ked `save_session` uspel.
        """
        try:
            # LEN NAOZAJ DORUCENE. `delivered` doplnil `_on_cue_event`;
            # bez tejto podmienky dotaznik ratal aj hlasky, ktore sa
            # nedorucili (vsetky sloty vypnute, zlyhany vizual) a protirecil
            # ulozenemu poctu `triggers` (bug B19).
            tiche = sum(1 for c in self._cue_log
                        if c.get("typ") == trigger.E_DELIVER
                        and c.get("delivered")
                        and c.get("arm") == trigger.ARM_SILENT)
            vsetky = sum(1 for c in self._cue_log
                         if c.get("typ") == trigger.E_DELIVER
                         and c.get("delivered"))
            dialog = SessionEndDialog(self, summary, cues=vsetky, silent=tiche)
            # Kazdy otvoreny dotaznik si appka pamata (0.2.2 davka 4b): ked
            # hrac ukonci appku z listy alebo sa vypina Windows, kym dotaznik
            # z bezneho Stop este visi, `_dokonci_otvorene_dotazniky` ulozi
            # dotknute odpovede - `root.destroy()` by ich inak zahodil.
            # Zavrete okna sa pri tom zahodia, aby zoznam za dlhy beh nerastol.
            otvorene = []
            for stary in list(getattr(self, "_otvorene_dotazniky", None) or ()):
                try:
                    if stary.top.winfo_exists():
                        otvorene.append(stary)
                except Exception:
                    pass
            otvorene.append(dialog)
            self._otvorene_dotazniky = otvorene
            # PRI ZATVARANI APPKY SA MUSI POCKAT.
            #
            # Dialog robi `grab_set()`, ale nie `wait_window()`, takze sa
            # `_ask_session_context` vratila okamzite. Pri beznom vypnuti
            # merania to je spravne - okno visi a hrac ho vyplni, kedy chce.
            # Lenze `_quit` ide hned na `root.destroy()`, cize sa dotaznik
            # zahodil skor, nez sa stihol vykreslit: pri zatvoreni appky sa
            # kontext relacie NEDAL vyplnit vobec. A prave vtedy sa vypina
            # najcastejsie - dohral som a idem spat.
            if getattr(self, "_zatvara_sa", False):
                # Cez tuto referenciu dotaznik zavrie druhe "Ukoncit" z listy
                # (viz `_quit`). Inak by vo vnorenej slucke `wait_window`
                # prebehlo cele druhe ukoncenie a tento `_quit` by sa vratil
                # do zniceneho okna.
                self._dotaznik_pri_zatvarani = dialog
                try:
                    self.root.wait_window(dialog.top)
                finally:
                    self._dotaznik_pri_zatvarani = None
        except Exception:
            app_log.exception("dotaznik kontextu sa nepodarilo otvorit")

    def _dokonci_dotaznik(self, dotaznik):
        """Dokonci dotaznik, ktory by ukoncenie appky alebo vypnutie Windows
        inak zahodilo (0.2.2, rozhodnutie zadavatela; davka 4b ho rozsirila).

        Dotkol sa hrac aspon jednej odpovede -> ulozi sa ako "Ulozit"; nie ->
        zavrie sa ako "Preskocit". Do dennika ide jeden riadok: ulozene,
        zavrety prazdny, alebo ze sa ulozit nepodarilo. Pocas tohto ulozenia
        `save_session_context` neotvara okno s chybou - pri zatvarani by na
        neho nikto neklikol a vypnutie Windows by cakalo.

        Dotaznik bez `bolo_vyplnene` (atrapy) sa bere ako prazdny. Zavrie sa
        aj ked ulozenie zlyhalo: prvy `_quit` na neho moze cakat
        (`wait_window`)."""
        try:
            vyplneny = bool(getattr(dotaznik, "bolo_vyplnene", lambda: False)())
        except Exception:
            app_log.exception("ukoncenie: stav dotaznika sa nedal zistit")
            vyplneny = False
        if not vyplneny:
            try:
                self.log(tr("log.quit_questionnaire_skipped"))
                dotaznik.close()
            except Exception:
                app_log.exception("ukoncenie: dotaznik sa nepodarilo zavriet")
            return False
        self._dotaznik_bez_okna_chyby = True
        try:
            ok = dotaznik.confirm()
        except Exception:
            app_log.exception("ukoncenie: odpovede dotaznika sa nepodarilo ulozit")
            ok = False
            try:
                dotaznik.close()
            except Exception:
                pass
        finally:
            self._dotaznik_bez_okna_chyby = False
        # `confirm` atrap nic nevracia - None nie je neuspech.
        try:
            self.log(tr("session.context.save_failed") if ok is False
                     else tr("log.quit_questionnaire_saved"))
        except Exception:
            app_log.exception("ukoncenie: riadok o dotazniku sa nezapisal")
        return ok is not False

    def _dokonci_otvorene_dotazniky(self):
        """Kazdy este otvoreny dotaznik po relacii (`_otvorene_dotazniky`,
        zaklada `_ask_session_context`) dokonci podla `_dokonci_dotaznik`.

        Vola sa pri prvom "Ukoncit" a pri vypnuti Windows (WM_SAVE_YOURSELF).
        Okno, ktore uz zaniklo (hrac ho ulozil alebo preskocil), sa preskoci.
        Vracia pocet dokoncenych dotaznikov."""
        zive = []
        for dotaznik in list(getattr(self, "_otvorene_dotazniky", None) or ()):
            top = getattr(dotaznik, "top", None)
            try:
                if top is not None and top.winfo_exists():
                    zive.append(dotaznik)
            except Exception:
                pass
        self._otvorene_dotazniky = []
        for dotaznik in zive:
            self._dokonci_dotaznik(dotaznik)
        return len(zive)

    def save_session_context(self, summary, context, activity=None, note=None,
                             sleep=None, felt_load=None, valence=None,
                             body_peak=None, cue_verdict=None, setup=None):
        """Doplni kontext k prave ulozenej relacii. Vola dialog.

        Vracia True pri uspechu. Kontext (kava/alkohol/spanok - najvacsi
        vysvetlitelny zdroj rozptylu v merani), cinnost (hral/pracoval) aj
        vlastna poznamka sa NESMU stratit potichu: `attach_context` doteraz
        vratil True/False, ale navratovka sa ignorovala a dialog sa zavrel
        presne ako pri uspechu (bug B16). Teraz sa pri neuspechu zapise chyba
        a hrac dostane spravu.
        """
        try:
            ok = hr_stats.attach_context(
                self.hr_sessions_path, summary.get("started"),
                context, activity=activity, note=note,
                sleep=sleep, felt_load=felt_load, valence=valence,
                body_peak=body_peak, cue_verdict=cue_verdict,
                log=self.log_threadsafe, setup=setup)
        except Exception:
            app_log.exception("kontext relacie sa nepodarilo ulozit")
            ok = False
        if ok:
            self._history_cache = (0.0, None)
            # Odpoved hral/pracoval moze relaciu presunut do druheho sveta
            # (B3-worlds): detail by potom ukazoval na inu relaciu a postrehy
            # by boli z inej mnoziny - preto nulovanie a nova analyza.
            zmena_sveta = (hr_stats.normalize_activity(activity) is not None
                           and hr_stats.normalize_activity(activity)
                           != hr_stats.session_world(summary))
            if zmena_sveta:
                self.history_detail_index = None
            # Detail relacie v Historii ukazuje aj "citene · merane" - bez
            # prekreslenia by tam po dotazniku ostala pomlcka do dalsej
            # relacie. (Karta na Dnes si to precita sama pri dalsom tiku.)
            try:
                self._refresh_history_page()
            except Exception:
                app_log.exception("historia: prekreslenie po dotazniku zlyhalo")
            if zmena_sveta:
                self.run_hr_analysis()
        else:
            app_log.error("kontext relacie sa neulozil - relacia sa nenasla "
                          "alebo subor nebolo mozne zapisat")
            # Pri ukonceni / vypnuti Windows dokoncuje dotaznik appka
            # (`_dokonci_dotaznik`) a chybu zapise do dennika - okno by tam
            # nikto nezavrel a vypnutie by na neho cakalo.
            if getattr(self, "_dotaznik_bez_okna_chyby", False):
                return False
            try:
                # okno appky, nie systemove (0.2.2, davka 4)
                ui_kit.notify(getattr(self, "root", None), getattr(self, "pal", None),
                              APP_NAME, tr("session.context.save_failed"),
                              kind="warning")
            except Exception:
                pass
        return bool(ok)

    def _save_measure_windows(self):
        """Zostavi meracie okna prave skoncenej relacie a ulozi ich.

        Pocita sa az tu, na konci: v tom momente je `hr_stats._all` cely,
        takze staci jeden prechod a nic netreba casovat. Cenou je, ze okno
        poslednej hlasky moze byt skratene - zapise sa s dovodom.

        Do suboru nejde ziadna surova krivka, len priemery za pasma okna.
        """
        try:
            cues = list(getattr(self.hr_stats, "cues", ()))
            if not cues:
                return
            windows = measure.build_windows(
                cues,
                self.hr_stats._all,
                load=self.hr_stats._load,
                activity=self.activity.samples,
                session_started=self.hr_stats.session_start,
                game=self.active_profile_name or None,
            )
            # Kazde okno si nesie parametre, s akymi relacia bezala
            # (zadanie §3.3). Bez toho sa o mesiac neda povedat, ci bol
            # rozdiel v tom, co sa zmenilo, alebo v tom, ako sa hrac vyspal.
            params = dict(self.cue_trigger.params)
            params["silent_share"] = self.cue_trigger.silent_share
            # Svet relacie (B3-worlds) priamo v okne: okna ziju dlhsie nez
            # relacie (MAX_SESSIONS), takze spajat ich so suhrnom by casom
            # stratilo prave tie najstarsie. V `world` "work" hlaska nemala
            # hlas ani zvuk - graf ucinnosti ich tak vie raz oddelit.
            svet = getattr(self, "_session_world", hr_stats.WORLD_DEFAULT)
            for w in windows:
                w["params"] = params
                w["natiahnuti"] = self.cue_trigger.armed_count
                w["world"] = svet
            if measure.save_windows(self.hr_windows_path, windows,
                                    log=self.log_threadsafe):
                platne = sum(1 for w in windows if w.get("valid"))
                app_log.info("meracie okna: ulozenych %d, z toho platnych %d",
                             len(windows), platne)
        except Exception:
            # Meranie nesmie zhodit ukladanie relacie - suhrn relacie je
            # dolezitejsi nez okna a uklada sa hned za tymto.
            app_log.exception("meracie okna: zostavenie/ulozenie zlyhalo")

    def _maybe_graduate(self, summary):
        """Po ulozeni relacie: dosiahol hrac "plny Zanshin"? Spusti sa RAZ.

        Cita ULOZENU historiu (vratane prave ulozenej relacie), vyhodnoti
        `hr_stats.zanshin_graduation`; pri splneni nastavi trvaly flag, ulozi
        nastavenia, oznaci summary pre dotaznik (mysticka sprava) a prepne
        znacku na zlaty mesiac. Appka bezi dalej - je to len pozorovanie.

        Len po HERNEJ relacii (`hr_stats.ZEN_SVET`): seria sa rata z hry a
        kruh sa uzavrie po pokojnom vecere pri hre - nie v dotazniku po praci.
        """
        try:
            if self.zanshin_graduated:
                return
            if hr_stats.session_world(summary) != hr_stats.ZEN_SVET:
                return
            sessions = hr_stats.load_sessions(self.hr_sessions_path,
                                              log=self.log_threadsafe)
            vysledok = hr_stats.zanshin_graduation(
                sessions, already_graduated=self.zanshin_graduated)
            if vysledok.get("fire"):
                self.zanshin_graduated = True
                self.zanshin_graduated_at = time.time()
                self.save_settings()
                summary["zen_graduation"] = True
                try:
                    if getattr(self, "enso", None) is not None:
                        self.enso.graduate()
                except Exception:
                    app_log.exception("promocia: znacku sa nepodarilo prepnut")
        except Exception:
            app_log.exception("promocia: vyhodnotenie zlyhalo")

    def _close_hr_session(self, pri_vypnuti=False, koniec=None):
        """Ulozi suhrn prave skoncenej relacie do hr_sessions.json.

        `koniec` (cas, 0.2.2): relacia skoncila uz vtedy - posledny tik pred
        uspanim PC (`_rozdel_relaciu_po_medzere`). Suhrn sa uzavrie k nemu a
        dotaznik sa neotvori, hrac pri konci nebol. Ukladanie je inak to iste
        (`je_ulozitelna`, kontrolny bod, ucenie).

        Kratke relacie (pod minutu alebo bez dat) sa zahadzuju uz v
        hr_stats.save_session - zapnut a hned vypnut senzor nie je relacia.

        `pri_vypnuti=True` (vypinanie Windows, `_pri_vypinani_windows`):
        ulozit a nic viac. Windows caka na odpoved len par sekund, takze bez
        dotaznika (zahodil by sa s procesom), bez promocie (jednorazova
        sprava by sa hracovi nikdy neukazala - vyhodnoti sa po dalsej
        relacii) a bez prekreslovania Historie a analyzy v pozadi.
        """
        if not self._hr_session_open:
            return
        self._hr_session_open = False
        # "Zmazat historiu" sa s koncom relacie vrati (0.2.2).
        _ak_vies(self, "_refresh_data_delete_state")
        # Ak sa prave cakalo na pauzu, zapise sa to. Podla toho, ako casto
        # sa relacia skonci v tomto stave, sa da ladit `max_wait_s`.
        try:
            udalost = self.cue_trigger.close_session()
            if udalost is not None:
                self._cue_log.append(dict(udalost))
        except Exception:
            app_log.exception("spustac hlasky: close_session zlyhal")
        # `close_session` zapisuje do logu priamo, nie cez `_on_cue_event`,
        # takze prstenec treba zhodit rucne. Senzor sa da vypnut bez toho,
        # aby sa prestalo pocuvat - `set_live` to teda nechyti.
        self._set_enso_armed(False)
        self._save_measure_windows()
        # Udalosti automatu natrvalo. Az TU, nie priebezne: zapis na disk
        # pri kazdej udalosti by sa diala v Tk vlakne uprostred hrania.
        try:
            data_io.append_events(self.hr_events_path, self._cue_log,
                                  started=getattr(self.hr_stats, "session_start", None))
        except Exception:
            app_log.exception("udalosti: zapis zlyhal")
        # Relacia skoncila skor nez teraz (posledny tik pred uspanim PC,
        # `_rozdel_relaciu_po_medzere`): suhrn sa uzavrie k tomu casu.
        summary = (self._suhrn_relacie() if koniec is None
                   else self._suhrn_relacie(koniec=koniec))
        # Az PO zostaveni suhrnu: tieto pocitadla patria uz len tejto
        # relacii. `_suhrn_relacie` ich len cita (vola ho aj kontrolny bod
        # uprostred relacie), nulovanie je vec zatvorenia.
        self._snooze_po_hlaske = None
        self._snooze_rel_s = 0.0
        self._snooze_rel_od = None
        self._hud_tick_t = None
        # Chyba zapisu ide do dennika vlastnou vetou (`_relacia_sa_neulozila`),
        # nie technickym riadkom zo `save_session`; ostatne riadky (napr.
        # odlozeny pokazeny subor) idu do dennika ako doteraz.
        chyby_zapisu = []

        def _log_ulozenia(sprava):
            if str(sprava).startswith("HR: session log failed:"):
                chyby_zapisu.append(str(sprava)[len("HR: session log failed:"):].strip())
                app_log.warning("%s", bez_ciest(sprava))
                return
            self.log_threadsafe(sprava)

        ulozitelna = hr_stats.je_ulozitelna(summary)
        ulozena = hr_stats.save_session(self.hr_sessions_path, summary,
                                        log=_log_ulozenia)
        # Kontrolny bod uz netreba - relacia je v historii. Ked sa ulozit
        # nedala (plny disk), ostava a obnova ju skusi pri dalsom starte;
        # kratka relacia, ktora by neprisla ani tak, ho maze tiez.
        if ulozena or not ulozitelna:
            hr_stats.zahod_rozpracovanu(self.hr_sessions_path)
        if not ulozena and ulozitelna:
            # ZAPIS ZLYHAL (0.2.2): plny disk, zakazany pristup, zamknuty
            # subor. Relacia nesmie zmiznut potichu - riadok, oznam a suhrn
            # bokom do hr_session_pending.json (doplni ho dalsi start).
            _ak_vies(self, "_relacia_sa_neulozila",
                     summary, chyby_zapisu[-1] if chyby_zapisu else "?",
                     oznam=not pri_vypnuti and not getattr(self, "_zatvara_sa", False))
        elif not ulozena:
            _ak_vies(self, "_kratka_relacia_bez_tepu", summary)
        if ulozena:
            # Znacku nastavovania nesie len PRVA relacia, ktora sa naozaj
            # ulozila. Kratka (pod minutu, bez tepu - napr. pred sparovanim
            # hodiniek) sa neulozi, takze znacka pocka na dalsiu.
            self._relacia_nastavovania = False
            # Disk je zase zapisovatelny - co minule ostalo bokom, ide dnu.
            if not pri_vypnuti:
                _ak_vies(self, "_dopln_cakajuce_relacie")
        if ulozena and not pri_vypnuti:
            # Po uspani PC (`koniec`) bez dotaznika: hrac pri tom nebol a
            # okno by mu po prebudeni vyskocilo pred hru (0.2.2). A preto ani
            # bez promocie - jej jednorazovu spravu nesie prave dotaznik
            # (`zen_graduation`), takze by sa nikdy neukazala; vyhodnoti sa
            # po dalsej relacii, rovnako ako pri vypinani Windows.
            if koniec is None:
                self._maybe_graduate(summary)
                self._ask_session_context(summary)
        if ulozena:
            self.log(tr("log.hr_session_saved",
                        avg=summary.get("avg_bpm") or "-",
                        max=summary.get("max_bpm") or "-",
                        peak=summary.get("peak_stress")))
            # nova relacia v historii -> prekresli stranku a prepocitaj
            # postrehy (v pozadi). Cache historie musi ist prec ako prva,
            # inak by karty aj graf este 20 sekund kreslili stav spred
            # tejto relacie.
            self._history_cache = (0.0, None)
            if pri_vypnuti:
                return
            try:
                self._refresh_history_page()
            except Exception:
                app_log.exception("historia: prekreslenie zlyhalo")
            self.run_hr_analysis()

    def _suhrn_relacie(self, koniec=None):
        """Suhrn beziacej relacie - presne to, co by ulozilo zatvorenie.

        BEZ VEDLAJSICH UCINKOV: vola ho `_close_hr_session` aj kontrolny bod
        (`_zapis_rozpracovanu_relaciu`) kazdych par minut uprostred hrania,
        takze nic nenuluje ani nepripocitava do stavu appky. Jeden zdroj
        suhrnu, aby sa obnovena relacia nelisila od normalne ulozenej.

        `koniec` (0.2.2) = relacia skoncila uz vtedy (posledny tik pred
        uspanim PC) - vsetky casy v suhrne sa ratau po neho, nie po teraz.
        """
        summary = (self.hr_stats.summary() if koniec is None
                   else self.hr_stats.summary(koniec=koniec))
        teraz = time.time() if koniec is None else float(koniec)
        # SVET, V KTOROM RELACIA ZACALA (B3-worlds). Samostatny kluc, nie
        # `activity`: to je odpoved hraca v dotazniku a strojovy stitok by
        # ju nesmel prekryt - neskor sa musi dat rozlisit, co hrac naozaj
        # potvrdil. Ktory plati, rozhoduje `hr_stats.session_world`.
        summary["world"] = getattr(self, "_session_world", hr_stats.WORLD_DEFAULT)
        # NASTAVOVANIE APPKY (0.2.2): kym sa po uvode neulozi prva relacia,
        # je to sedenie pri stole (parovanie, prehliadka), nie hranie - prahy
        # sa z nej neucia (`hr_stats.ciste_relacie`). Aj do kontrolneho bodu,
        # aby to platilo aj po obnove. Hrac to v dotazniku moze zrusit.
        if getattr(self, "_relacia_nastavovania", False):
            summary["setup"] = True
        # EXKLUZIVNY FULLSCREEN (0.2.2 davka 4): appka ho v tejto relacii
        # zbadala (`_warn_exclusive_fullscreen_once`) - obrazky nad takou
        # hrou Windows nevykresli. Jeden priznak, dotaznik podla neho povie
        # vetu `session.end.fullscreen_note`.
        if getattr(self, "_session_fullscreen", False):
            summary["fullscreen"] = True
        # PRECO SA TOTO PRILEPUJE K SUHRNU
        # Prvy skutocny vecer skoncil s nulou hlasok, hoci spicka zataze bola
        # 87 pri prahu 55. Zo suhrnu sa nedalo rozlisit, ci bolo pravidlo
        # "suvisle 90 s" pritvrde, alebo ci pocitanie rozbijali vypadky tepu.
        # Su to jednotlive cisla, nie krivka - do suboru nejde nic surove.
        try:
            summary["longest_above_s"] = round(self.cue_trigger.najdlhsi_nad_s, 1)
            summary["above_runs"] = self.cue_trigger.behov_nad
            summary["runs_cancelled_dip"] = self.cue_trigger.zrusenych_prepadom
            summary["runs_cancelled_gap"] = self.cue_trigger.zrusenych_vypadkom
            summary["stress_hold_s"] = self.cue_trigger.params["stress_hold_s"]
            # Na AKOM prahu relacia bezala. Po par veceroch sa prah pocita z
            # vlastnych dat (`_prah_z_dat`) a meni sa medzi relaciami - bez
            # neho sa po par veceroch neda povedat, ci bol vecer na 55, 78
            # alebo 72, ani oddelit vecery pred opravou spustaca a po nej.
            summary["stress_threshold"] = self.cue_trigger.params["stress_threshold"]
            # BRANA HLASKY (0.2): kolko pauz vo vstupe appka za relaciu
            # vobec videla a kolko natiahnuti sama zrusila (podla dovodu).
            # Nula pauz za dlhy vecer = hlas nemal kedy zaznet; dotaznik to
            # povie narovinu (`SessionEndDialog._preco_ticho`).
            summary["pause_episodes"] = self.cue_trigger.pause_episodes
            summary["cues_withheld"] = dict(self.cue_trigger.zadrzane)
            # REBRIK HLASKY (0.2, `rebrik.py`): stupen a styl, na ktorych
            # relacia bezala, a "teraz nie" kratko po hlaske - s tym, kolko
            # relacia po nom este bezala (`_zapis_snooze_po_hlaske`).
            summary["cue_rung"] = getattr(self, "_cue_rung", rebrik.HLAS)
            summary["cue_style"] = getattr(self, "_cue_style_rel", rebrik.STYL_HLAS)
            # Kolko automatickych hlasok sa naozaj UKAZALO (0.2.1). Rebrik
            # rata relaciu "s hlaskou" podla tohto, nie podla `auto_triggers`
            # - to zapocita aj hlasku so zlyhanym obrazom, z ktorej hrac nic
            # nevidel (viz `rebrik._hlasok`). Rovnake pravidlo ako dotaznik
            # (`_ask_session_context`) a `hr_stats.last_auto_cue_ts`.
            summary["cues_delivered"] = sum(
                1 for c in getattr(self.hr_stats, "cues", ())
                if c.get("source") == "auto" and c.get("delivered", True))
            snooze = getattr(self, "_snooze_po_hlaske", None)
            if snooze is not None:
                summary["snooze_after_cue_s"] = snooze[0]
                summary["snooze_then_s"] = round(max(0.0, teraz - snooze[1]), 1)
            # Dlhodoba zakladna, voci ktorej sa zataz v tejto relacii ratala
            # (None = este nebola z coho).
            dlhodoba = self.hr_stats.long_baseline
            summary["long_baseline_bpm"] = (round(float(dlhodoba), 1)
                                           if dlhodoba is not None else None)
        except Exception:
            app_log.exception("suhrn: pocitadla spustaca sa nepodarilo pridat")
        # Kolko z relacie platilo "teraz nie" (od 24. 9. relaciu nezatvara).
        # Pocitadla vyssie ten cas nevidia - automat vtedy spal - takze
        # dotaznik aj postrehy podla nich nesmu vysvetlovat ticho, ktore si
        # hrac vybral sam (`SessionEndDialog._preco_ticho`, `hr_insights`).
        od = getattr(self, "_snooze_rel_od", None)
        stisene = getattr(self, "_snooze_rel_s", 0.0) or 0.0
        if od is not None:
            stisene += max(0.0, teraz - od)
        if stisene > 0.0:
            summary["snoozed_s"] = round(stisene, 1)
        # Koľko relácie hráč reálne videl svoj tep (HUD). Doťahuje sa posledný
        # úsek od posledného tiku po teraz - do lokálnych premenných, nie do
        # `_hud_*` (kontrolný bod by inak ten úsek pripočítal dvakrát).
        # Podiel z trvania: relácia s viditeľným HUD je iný experiment než
        # naslepo (biofeedback).
        try:
            videl_s, aktivne_s = self._hud_vis_s, self._hud_active_s
            if self._hud_tick_t is not None:
                dt = teraz - self._hud_tick_t
                if 0.0 < dt < 5.0:
                    aktivne_s += dt
                    if self._hud_is_visible():
                        videl_s += dt
            summary["hud_visible_s"] = round(videl_s, 1)
            # Podiel z AKTIVNEHO casu relacie, nie z hrubeho trvania: citatel
            # aj menovatel zahadzuju rovnake medzery (uspanie PC), takze podiel
            # po uspani neklesne umelo nadol.
            if aktivne_s > 0:
                summary["hud_visible_frac"] = round(
                    max(0.0, min(1.0, videl_s / aktivne_s)), 3)
        except Exception:
            app_log.exception("suhrn: viditelnost HUD-u sa nepodarilo pridat")
        return summary

    # ---------- vypnutie Windows, kontrolny bod, obnova po pade ----------

    def _pri_vypinani_windows(self):
        """Windows sa vypina, restartuje alebo odhlasuje (WM_SAVE_YOURSELF).

        PRECO TOTO A NIE WM_DELETE_WINDOW: pri vypnuti PC Windows okno
        nezatvara, posle WM_QUERYENDSESSION a potom proces ukonci. Tk na
        Windows (tkWinWm.c, WmProc) z WM_QUERYENDSESSION spravi protokol
        WM_SAVE_YOURSELF a obsluhu zavola HNED, synchronne - Windows medzitym
        caka na odpoved. Overene nazivo na Tk 9.0, ktore appka bali
        (tests/test_022b_data_vypnutie.py): WM_QUERYENDSESSION poslana
        bezramovemu oknu schovanemu v liste zavola obsluhu WM_SAVE_YOURSELF,
        WM_DELETE_WINDOW nie. Doteraz appka poznala len WM_DELETE_WINDOW,
        takze vypnutie PC zahodilo celu relaciu aj jej udalosti.

        Musi byt RYCHLE: Windows po par sekundach ukaze "Tato appka brani
        vypnutiu". Preto len ulozit relaciu bez dotaznika a nastavenia -
        `_quit` (dotaznik, zastavenie vlakien) sa tu nevola, proces aj tak
        skonci. Bezpecne aj pocas `_quit` (relacia uz je zavreta, ulozia sa
        len nastavenia) aj dvakrat po sebe (`_hr_session_open` strazi).
        """
        if getattr(self, "_vypnutie_bezi", False):
            return
        self._vypnutie_bezi = True
        try:
            # Otvoreny dotaznik (z bezneho Stop, alebo ten, na ktory caka
            # `_quit`) by proces zahodil: dotknute odpovede sa ulozia ako
            # "Ulozit", nedotknuty sa zavrie ako "Preskocit" (0.2.2 davka 4b,
            # to iste pravidlo ako pri ukonceni). Len zapis do suboru - rychle.
            try:
                self._dokonci_otvorene_dotazniky()
            except Exception:
                app_log.exception("vypnutie Windows: dotaznik sa nepodarilo dokoncit")
            try:
                self._close_hr_session(pri_vypnuti=True)
            except Exception:
                app_log.exception("vypnutie Windows: relaciu sa nepodarilo ulozit")
            try:
                self.save_settings()
            except Exception:
                app_log.exception("vypnutie Windows: nastavenia sa nepodarilo ulozit")
            app_log.info("vypnutie Windows: relacia a nastavenia ulozene")
            # VYPNUTIE SA MOZE ZRUSIT (ina appka ho zablokuje a hrac da
            # Zrusit). Tk to appke nepovie - appka by potom pocuvala, ale
            # bez otvorenej relacie by nemerala nic (presne chyba A1). Ked
            # proces o chvilu este zije, vypnutie neprebehlo: relacia sa
            # otvori znova. Ked Windows vypne, toto uz nikdy nepribehne.
            stary = getattr(self, "_vypnutie_job", None)
            if stary is not None:
                try:
                    self.root.after_cancel(stary)
                except Exception:
                    pass
            try:
                self._vypnutie_job = self.root.after(
                    VYPNUTIE_ZRUSENE_MS, self._po_zrusenom_vypnuti)
            except Exception:
                self._vypnutie_job = None
        finally:
            self._vypnutie_bezi = False

    def _po_zrusenom_vypnuti(self):
        """Windows sa napokon nevyplo - meranie pokracuje novou relaciou."""
        self._vypnutie_job = None
        if getattr(self, "_quit_bezi", False) or getattr(self, "_zatvara_sa", False):
            return
        if (not getattr(self, "listening", False)
                or not getattr(self, "hr_monitoring_enabled", False)
                or getattr(self, "_hr_session_open", False)):
            return
        try:
            if self.heart_rate_monitor.running:
                # Prijem bezi dalej, siete sa nedotykame (ako `start_listening`).
                self._open_hr_session(prepoj=False, meria=True)
                app_log.info("vypnutie Windows sa zrusilo - nova relacia otvorena")
        except Exception:
            app_log.exception("po zrusenom vypnuti sa relacia neotvorila")

    def _naplanuj_rozpracovanu_relaciu(self):
        """Dalsi kontrolny bod o `ROZPRACOVANA_KAZDYCH_MS`. Vola sa raz z
        `__init__`, potom sa tik planuje sam."""
        try:
            self._rozpracovana_job = self.root.after(
                ROZPRACOVANA_KAZDYCH_MS, self._tik_rozpracovanej_relacie)
        except Exception:
            self._rozpracovana_job = None
            app_log.exception("kontrolny bod relacie sa nepodarilo naplanovat")

    def _tik_rozpracovanej_relacie(self):
        self._rozpracovana_job = None
        # Pocas ukoncovania nic: relacia sa prave uklada normalne a po
        # `root.destroy()` uz niet kam planovat.
        if getattr(self, "_quit_bezi", False) or getattr(self, "_zatvara_sa", False):
            return
        try:
            self._zapis_rozpracovanu_relaciu()
        except Exception:
            app_log.exception("kontrolny bod relacie zlyhal")
        self._naplanuj_rozpracovanu_relaciu()

    def _zapis_rozpracovanu_relaciu(self):
        """Kontrolny bod: suhrn otvorenej relacie do hr_session_open.json.

        PRECO KAZDYCH 5 MINUT, NIE PRI KAZDEJ VZORKE: zapis bezi v Tk vlakne
        uprostred hrania (rovnaky dovod, preco sa udalosti pisu az na konci).
        Pri pade sa strati najviac poslednych 5 minut, nie cely vecer.
        Udalosti a meracie okna sa tu NEZAPISUJU - patria k zatvoreniu (okna
        sa skladaju z celej relacie naraz), po pade preto chybaju.
        Vracia True, ked sa zapisalo."""
        if not getattr(self, "_hr_session_open", False):
            return False
        summary = self._suhrn_relacie()
        if not hr_stats.je_ulozitelna(summary):
            return False
        return hr_stats.zapis_rozpracovanu(self.hr_sessions_path, summary,
                                           log=app_log.warning)

    def _obnov_rozpracovanu_relaciu(self):
        """Pri starte: relacia, ktora sa minule neulozila, ide do historie.

        Vola sa z `__init__` pred zapnutim senzora (nova relacia sa este
        neotvorila). Do dennika jeden riadok, technicke dovody len do app.log.

        Najprv relacie, ktore sa minule nedali ULOZIT (`hr_session_pending`,
        0.2.2): su uplne, kym kontrolny bod tej istej relacie je az 5 minut
        stary - ten sa potom zahodi ako duplikat (`_uz_v_historii`).
        """
        _ak_vies(self, "_dopln_cakajuce_relacie")
        try:
            obnovena = hr_stats.obnov_rozpracovanu(self.hr_sessions_path,
                                                   log=app_log.info)
        except Exception:
            app_log.exception("obnova rozpracovanej relacie zlyhala")
            return None
        if obnovena is None:
            return None
        # Rovnaky tvar datumu ako zoznam relacii v Historii (jazyk appky).
        kedy = ui_kit.datum_text(obnovena["started"], cas=True)
        self.log(tr("log.hr_session_recovered", time=kedy))
        self._history_cache = (0.0, None)
        try:
            self._refresh_history_page()
        except Exception:
            app_log.exception("historia: prekreslenie po obnove zlyhalo")
        return obnovena

    # ---------- relacia, ktoru sa nepodarilo ulozit (0.2.2) ----------

    def _relacia_sa_neulozila(self, summary, chyba, oznam=True):
        """Zapis relacie zlyhal (plny disk, zakazany pristup, JSON).

        Do 0.2.2 zmizla potichu: technicky riadok v denniku a nic viac. Teraz
        jeden riadok, jeden oznam v okne appky (ziadne systemove okno) a
        suhrn bokom do hr_session_pending.json - pri dalsom starte (alebo po
        dalsom uspesnom ulozeni) sa doplni ako obnovena relacia. Kontrolny
        bod tej istej relacie OSTAVA ako druha kopia: start doplni najprv
        tuto (uplnu) a starsi kontrolny bod potom zahodi ako duplikat.
        `oznam=False` pri ukoncovani a vypinani Windows - okno by zablokovalo
        koniec; riadok v denniku a subor bokom ostavaju."""
        chyba = bez_ciest(chyba)
        odlozena = hr_stats.zapis_cakajucu(self.hr_sessions_path, summary,
                                           log=lambda m: app_log.warning("%s", bez_ciest(m)))
        if odlozena:
            text = tr("log.hr_session_save_failed", err=chyba)
        else:
            text = tr("log.hr_session_save_failed_lost", err=chyba)
        app_log.error("relacia sa neulozila (%s), odlozena bokom: %s", chyba, odlozena)
        self.log(text)
        if not oznam:
            return odlozena

        def _ukaz():
            notify = getattr(ui_kit, "notify", None)
            if callable(notify):
                try:
                    notify(self.root, self.pal, tr("session.save_failed.title"), text,
                           kind="warning")
                    return
                except Exception:
                    app_log.exception("oznam o neulozenej relacii sa neukazal")
            # Bez oznamu aspon riadok v paneli dat (dennik uz veta ma).
            widget = getattr(self, "data_note", None)
            if widget is not None:
                try:
                    widget.configure(text=text)
                    if not widget.winfo_manager():
                        widget.pack(fill="x", pady=(10, 0))
                except Exception:
                    pass

        try:
            self.root.after(0, _ukaz)
        except Exception:
            app_log.exception("oznam o neulozenej relacii sa nenaplanoval")
        return odlozena

    def _kratka_relacia_bez_tepu(self, summary):
        """Relacia bezala aspon minutu, ale z hodiniek neprislo ani 10 vzoriek
        tepu - neulozi sa (`je_ulozitelna`). Doteraz bez slova (audit 4)."""
        try:
            trvanie = float(summary.get("duration_s") or 0)
            vzorky = float(summary.get("samples") or 0)
        except (TypeError, ValueError, AttributeError):
            return
        if trvanie >= 60 and vzorky < 10:
            self.log(tr("log.hr_session_no_data"))

    def _dopln_cakajuce_relacie(self):
        """Relacie z hr_session_pending.json do historie (`hr_stats.obnov_cakajuce`).
        Jeden riadok do dennika za kazdu. Vracia zoznam doplnenych."""
        try:
            doplnene = hr_stats.obnov_cakajuce(self.hr_sessions_path, log=app_log.info)
        except Exception:
            app_log.exception("doplnenie neulozenych relacii zlyhalo")
            return []
        for s in doplnene:
            try:
                kedy = ui_kit.datum_text(float(s["started"]), cas=True)
            except Exception:
                kedy = "?"
            self.log(tr("log.hr_session_pending_saved", time=kedy))
        if doplnene:
            self._history_cache = (0.0, None)
        return doplnene

    def _upozorni_na_staru_instalaciu(self):
        """Raz: nainstalovana 0.2 zdiela s touto verziou priecinok dat.

        Jej odinstalator sa pyta "Ponechat nastavenia...?" a pri Nie zmaze
        %APPDATA%\\Zanshin - aj historiu tejto (ZIP) verzie, ktora byva
        v tom istom priecinku. Pri behu zo zdrojakov data lezia vedla
        main.py, takze to tu neplati a kontrola sa preskoci.
        """
        if getattr(self, "old_installer_warned", False):
            return
        if not getattr(sys, "frozen", False):
            return
        try:
            stara = stara_instalacia()
        except Exception:
            app_log.exception("kontrola starej instalacie zlyhala")
            return
        if not stara:
            return
        text = tr("data.old_installer", version=stara.get("version") or "0.2")
        self.log(text)

        def _ukaz():
            # Zapamata sa az po ukazani: ked appka skonci skor, povie sa to
            # pri dalsom starte.
            try:
                ui_kit.notify(getattr(self, "root", None), getattr(self, "pal", None),
                              APP_NAME, text)
            except Exception:
                app_log.exception("upozornenie na staru instalaciu sa neukazalo")
            self.old_installer_warned = True
            self.save_settings()

        try:
            self.root.after(STARA_INSTALACIA_MS, _ukaz)
        except Exception:
            app_log.exception("upozornenie na staru instalaciu sa nenaplanovalo")

    def _warn_exclusive_fullscreen_once(self):
        """Jedna rada do logu, ak hra bezi v exkluzivnom fullscreene.

        V nom Windows cudzie vrstvene okna nevykresli vobec - hrac by
        videl, ze senzor bezi, ale ziadny vizual by sa neukazal a nemal by
        ako zistit preco.

        Riadok do dennika ide raz za beh appky. Od 0.2.2 (davka 4) si to
        navyse pamata KAZDA relacia (`_session_fullscreen`, nuluje ho
        `_open_hr_session`) - suhrn nesie `fullscreen` a dotaznik po hre
        povie jednu vetu, preco obrazky nad tou hrou nebolo vidno. Ked uz
        relacia aj dennik vedia, dalsie sekundy sa okno nekontroluje.
        """
        if (getattr(self, "_fullscreen_warned", False)
                and getattr(self, "_session_fullscreen", False)):
            return
        try:
            if display.is_fullscreen_foreground(self.root):
                if getattr(self, "_hr_session_open", False):
                    self._session_fullscreen = True
                if not getattr(self, "_fullscreen_warned", False):
                    self._fullscreen_warned = True
                    self.log(tr("log.exclusive_fullscreen"))
        except Exception:
            pass

    # ---------- import / export profilov (zdielanie kodom) ----------

    def export_profile_code(self):
        self._sync_active_profile_slots()
        profile = next((p for p in self.profiles if p["name"] == self.active_profile_name),
                       None)
        if profile is None:
            return
        try:
            # Len to, co ma zmysel pre druheho hraca (`slot_na_zdielanie`):
            # BEZ absolutnych ciest k nahravkam (niesli meno uctu vo Windows),
            # bez uid a bez mrtvych poli z cias klavesovych spustacov.
            payload = {"name": profile["name"],
                       "slots": [slot_na_zdielanie(s) for s in profile["slots"]]}
            raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            code = base64.b64encode(raw).decode("ascii")
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            self.root.update()
            self.log(tr("log.profile_exported", name=profile["name"], n=len(code)))
        except Exception as exc:
            self.log(tr("log.profile_export_error", err=exc))

    def import_profile_dialog(self):
        ImportProfileDialog(self)

    def import_profile_from_code(self, code):
        raw = base64.b64decode(code.strip().encode("ascii"), validate=True)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("slots"), list):
            raise ValueError(tr("import.invalid_format"))
        name = str(data.get("name") or tr("import.default_name")).strip() \
            or tr("import.default_name")
        base_name = name
        suffix = 2
        existing = {p["name"] for p in self.profiles}
        while name in existing:
            name = f"{base_name} ({suffix})"
            suffix += 1
        # Importovany profil dostane CERSTVE uid a bez lokalnych nahravok
        # (`slot_zo_zdielania`). uid z ineho profilu/stroja by inak zdielalo
        # subory nahravok (rec_<uid>.wav) a re-nahratie by prepisalo cudzi
        # klip - presne ta strata dat, proti ktorej uid vzniklo (B1). Cesty
        # k .wav sa nuluju VZDY, aj pri prazdnom `sfx_key`: cudzia cesta by
        # sa inak prehrala, keby na tomto PC nahodou existovala. Padne to na
        # TTS / preset SFX.
        slots = [s for s in (slot_zo_zdielania(x) for x in data["slots"]) if s]
        # Kod z 0.1 moze niest menej nez styri sloty - chybajuce kategorie
        # sa doplnia na koniec (vypnute), nic sa neprepise.
        slots = doplnit_kategorie(slots)
        self._sync_active_profile_slots()
        self.profiles.append({"name": name, "slots": slots})
        self.active_profile_name = name
        self.rebuild_slots(slots)
        self.refresh_profile_switch()
        self.save_settings()
        self.schedule_pregenerate(200)
        self.log(tr("log.profile_imported", name=name))

    def remove_slot(self, index):
        # Styri kategorie su pevne: kategoriu, obrazok aj meranie urcuje
        # POZICIA slotu, takze odstranenie by posunulo texty pod cudziu
        # kategoriu a vratit sa uz neda. Vypina sa prepinacom; ✕ ma len
        # slot navyse z 0.1 (index 4+).
        if je_kategoria(index):
            return
        if len(self.slots) <= 1:
            ui_kit.notify(getattr(self, "root", None), getattr(self, "pal", None),
                          APP_NAME, tr("log.slot_only_one"))
            return
        data = self.slot_dicts()
        removed = data.pop(index)
        self.rebuild_slots(data)
        self.save_settings()
        self.schedule_pregenerate(200)
        self.log(tr("log.slot_removed",
                    label=removed.get("text") or mode_labels().get(removed.get("mode"), "")))

    def _on_slot_selection_change(self):
        """Ukaze/schova listu hromadnych akcii podla poctu oznacenych slotov."""
        bar = getattr(self, "bulk_bar", None)
        if bar is None:
            return
        count = sum(1 for slot in self.slots if slot.selected)
        if count:
            self.bulk_label.configure(text=tr("slots.selected_count", n=count))
            if not bar.winfo_ismapped():
                bar.pack(fill="x", before=self._bulk_anchor)
        else:
            bar.pack_forget()

    def clear_slot_selection(self):
        for slot in self.slots:
            slot.set_selected(False)
        self._on_slot_selection_change()

    def remove_selected_slots(self):
        """Odstrani vsetky oznacene sloty naraz - jedna akcia, jedno potvrdenie.

        Rovnako ako remove_slot nedovoli zmazat uplne vsetko: aspon jeden
        slot musi ostat, inak by profil zostal prazdny a appka by nemala co
        spustat. Ak by vyber pokryval vsetky, jeden (prvy neoznaceny, alebo
        posledny) sa zachova a hrac dostane hlasku.
        """
        # Len sloty navyse (index 4+) - styri kategorie sa neodstranuju,
        # viz `remove_slot`.
        selected = [i for i, slot in enumerate(self.slots)
                    if slot.selected and not je_kategoria(i)]
        if not selected:
            return
        okno, pal = getattr(self, "root", None), getattr(self, "pal", None)
        if len(selected) >= len(self.slots):
            ui_kit.notify(okno, pal, APP_NAME, tr("log.slot_only_one"))
            return
        labels = [self.slots[i].text_value.strip()
                  or mode_labels().get(self.slots[i].mode, "")
                  or tr("slots.unnamed", n=i + 1) for i in selected]
        preview = ", ".join(labels[:4]) + ("…" if len(labels) > 4 else "")
        # Okno appky so slovesom na tlacidle, fokus na "Zrusit" (0.2.2).
        if not ui_kit.confirm(
                okno, pal, APP_NAME,
                tr("slots.remove_confirm", n=len(selected), list=preview),
                ok_label=tr("slots.remove_selected"), cancel_label=tr("common.cancel"),
                danger=True):
            return
        keep = [slot.to_dict() for i, slot in enumerate(self.slots)
                if i not in set(selected)]
        self.rebuild_slots(keep)
        self.save_settings()
        self.schedule_pregenerate(200)
        self.log(tr("log.slots_removed_bulk", n=len(selected)))
