"""Player data - part of the main app (DandurfApp from app.py).

DataMixin is a mixin of DandurfApp: app.py inherits it and the whole state
(file paths, session, profiles, slots, widgets) lives on DandurfApp. This
file holds only methods that work with it through `self` - the mixin has no
__init__ and no attributes of its own.

Two sections moved from app.py unchanged:
  * data: delete, export, import (phase 4) - the Data and About panels,
    export/import/delete of the history and what gets saved at the end of
    a measurement (session summary, measurement windows, context
    questionnaire, graduation),
  * profile import / export (sharing by code) - a profile as a code to the
    clipboard and removal of extra slots.

Watch out in tests: `_close_hr_session`, `_suhrn_relacie` and
`_maybe_graduate` read `time` from this module - a fake clock has to be
slipped in here too (`app_data.time`), not just on the app module.

Since 0.3 this also holds the protection of a session outside a normal
close: Windows shutdown (`_pri_vypinani_windows`), a checkpoint every 5
minutes (`_zapis_rozpracovanu_relaciu`) and its recovery at start
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

# Checkpoint of an open session (`_zapis_rozpracovanu_relaciu`). More
# would lose a long end of the evening on a crash, less would write to
# disk needlessly often in the middle of playing.
ROZPRACOVANA_KAZDYCH_MS = 5 * 60 * 1000
# After WM_SAVE_YOURSELF: if the process is still alive after this long,
# the Windows shutdown was cancelled (`_po_zrusenom_vypnuti`). A normal
# shutdown ends the process sooner.
VYPNUTIE_ZRUSENE_MS = 20 * 1000
# Warn about an installed 0.2 only once the window is up and start-up is done.
STARA_INSTALACIA_MS = 1500


_CESTA_V_TEXTE = re.compile(r"(?:[A-Za-z]:|\\\\)[\\/][^'\"\n]*")


def bez_ciest(text):
    """Error message without full paths - only the file name stays.

    "[Errno 13] Permission denied: 'C:\\Users\\<user>\\...\\hr_sessions.json'"
    would carry the Windows account name into the journal and into app.log
    (PRIVACY.md)."""
    return _CESTA_V_TEXTE.sub(
        lambda z: os.path.basename(z.group(0).rstrip("\\/")) or "…", str(text or ""))


def _ak_vies(app, meno, *args, **kwargs):
    """Calls `app.<meno>(...)` when `app` has it - otherwise nothing.

    Closing a session (`_close_hr_session`) also runs in tests on dummies
    with four attributes. The 0.3 add-ons (unsaved session, disabled
    "Zmazat") must not crash them - and an error in them must not crash
    the saving of the session."""
    fn = getattr(app, meno, None)
    if not callable(fn):
        return None
    try:
        return fn(*args, **kwargs)
    except Exception:
        app_log.exception("%s zlyhal", meno)
        return None


class DataMixin:
    """Player data, session end and profile sharing (DandurfApp mixin)."""

    # ---------- data: delete, export, import (phase 4) ----------

    def _build_data_panel(self, parent, pal):
        panel = ui_kit.Panel(parent, pal, title=tr("data.title"))
        panel.pack(fill="x")
        ctk.CTkLabel(panel.body, text=tr("data.hint"), font=ui_kit.ui(11),
                     text_color=pal["text_dim"], anchor="w",
                     justify="left", wraplength=560).pack(fill="x", pady=(0, 12))

        # BUTTON HIERARCHY (0.3, UX audit). "Zmazat historiu" (Delete history)
        # looked exactly like "Importovat" and sat right next to it - the most
        # dangerous action of the app looking neutral. Now: export and import
        # are secondary buttons (border >= 3:1), delete is `danger` (border and
        # text in red) and set 24 px apart so it is not hit by mistake.
        rad = ctk.CTkFrame(panel.body, fg_color="transparent")
        rad.pack(fill="x")
        # "Otvorit priecinok s datami" (Open the data folder, 0.3): backups
        # before import, the set-aside broken settings file and the unsaved
        # session all lie there - and the player had no other way to get to
        # them.
        for text, prikaz in ((tr("data.export.btn"), self.export_all_json),
                             (tr("data.import.btn"), self.import_all_json),
                             (tr("data.open_folder.btn"), self.open_data_folder)):
            ui_kit.button(rad, pal, text, command=prikaz,
                          height=32).pack(side="left", padx=(0, 8))
        self.data_delete_btn = ui_kit.button(rad, pal, tr("data.delete.btn"), kind="danger",
                                             command=self.delete_history, height=32)
        self.data_delete_btn.pack(side="left", padx=(16, 0))
        # Why "Zmazat" (Delete) is disabled (while watching). Not packed until
        # there is something to say - same as `data_note` below.
        self.data_delete_reason = ctk.CTkLabel(
            panel.body, text="", font=ui_kit.ui(11), text_color=pal["text_dim"],
            anchor="w", justify="left", wraplength=560)
        self._refresh_data_delete_state()

        # Result of export/import. An empty line is NOT PACKED - an empty
        # CTkLabel is as tall as a line of text and an unexplained gap was left
        # under the buttons. It shows up only with the first message
        # (`_data_note`).
        self.data_note = ctk.CTkLabel(panel.body, text="", font=ui_kit.ui(11),
                                      text_color=pal["text_dim"], anchor="w",
                                      justify="left", wraplength=560)

    def show_about(self):
        """The "A" button in the title bar: open Settings and jump to About.

        The scroll is done only after the redraw (`after`), because before
        it `winfo_y()` has nothing to return yet - the page is not laid out
        and the section would end up in a random place.
        """
        self._navigate("vseobecne")
        self.root.after(80, self._scroll_to_about)

    def _scroll_to_about(self):
        self._posun_vseobecne_na(getattr(self, "about_panel", None))

    def _posun_vseobecne_na(self, panel):
        """Scrolls the General page so that `panel` is at the top. Shared by
        ⓘ (About) and ⚙ at "Tep v hre" (the heart-rate panel section)."""
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
            # Scrolling is a convenience, not a feature. When it fails, the
            # player is at least on the right page - that is still better than
            # an exception.
            app_log.debug("posun na sekciu Vseobecne zlyhal", exc_info=True)

    def _build_about_panel(self, parent, pal):
        """Why the app came to be and where to find the author.

        The text is personal and deliberately not in the Guide: the Guide
        says how it works and why it works. This says WHY it exists at all
        - and that is a different question and a different voice.
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

        # LINKS RIGHT AFTER THE SENTENCE that points to them (0.3, UX audit).
        # The sentence "...zastav sa u nas:" ended with a colon followed by
        # ~50 px of empty space and the next section - the links came only
        # below it with their own heading. A chip is right here: it is an
        # external link (the only kind for which the chip stays). The arrow
        # hints that it opens the browser - the same mechanism as the sources
        # in the Guide and in History.
        rad = ctk.CTkFrame(panel.body, fg_color="transparent")
        rad.pack(fill="x", pady=(0, 16))
        for nazov, url in guide_content.COMMUNITY_LINKS:
            ui_kit.chip(rad, pal, "\u2197 " + nazov,
                        lambda u=url: webbrowser.open(u)).pack(
                side="left", padx=(0, 8))

        # THE DEEPEST LAYER OF "WHY" - for the one who reads between the lines.
        # Not the author's story, but what the app REALLY measures: the gap
        # between the measured and the felt. Deliberately muted (text_faint,
        # thin line) - whoever reads slowly and all the way here finds it on
        # their own. That is the whole point: the app is a tool for that gap,
        # not for a number.
        ui_kit.linka(panel.body, pal).pack(fill="x", pady=(2, 12))
        ctk.CTkLabel(panel.body, text=tr("about.between_lines"), font=ui_kit.ui(11),
                     text_color=pal["text_faint"], anchor="w", justify="left",
                     wraplength=560).pack(fill="x", pady=(0, 4))

        # COPYRIGHT AND LICENCE VISIBLE, not buried in the LICENSE file.
        #
        # GPLv3 recommends that an interactive program print a short notice
        # about authorship and warranty. But above all it is a promise to the
        # player: the app tells them right in the window under what terms they
        # got it and what they may do with it.
        ui_kit.linka(panel.body, pal).pack(fill="x", pady=(16, 10))
        # The version is taken from `app.version_short`, not hard-coded -
        # otherwise with the next bump it drifts apart from the title (B27).
        ctk.CTkLabel(panel.body,
                     text=tr("about.copyright", version=tr("app.version_short")),
                     font=ui_kit.ui(10), text_color=pal["text_faint"],
                     anchor="w", justify="left", wraplength=560).pack(fill="x")

    def _refresh_data_delete_state(self):
        """"Zmazat historiu" (Delete history) is OFF during an open session (0.3).

        A running session is saved only on close - after a delete it would
        be written right back into the empty history (and its checkpoint
        with it). A sentence under the button says why; after watching
        stops, the button comes back. Called when a session opens and
        closes."""
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
            pass            # the panel is being rebuilt

    def open_data_folder(self):
        """Opens the data folder in Explorer (`os.startfile`).

        It holds the backups before import, set-aside broken files and the
        session that could not be saved. The path is not written into the
        journal - in %APPDATA% it carries the account name (PRIVACY.md)."""
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
        """The whole history and the measurement windows into one file."""
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
        """The only place where a foreign file comes in.

        The strict parser is in `data_io`; here it only asks merge or replace
        (a custom dialog, `ImportDataDialog`) and writes the result.
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
        # A custom dialog, not the system askyesnocancel: that one had Yes/No
        # buttons in the Windows language and the choices hard-coded in the
        # text ("= Ano"), so in another language they did not match. Replace
        # happens only after a second confirmation.
        ImportDataDialog(self, sprava, lambda volba: self._zapis_import(
            sessions, windows, nahradit=(volba == "replace")))

    def _zapis_import(self, sessions, windows, nahradit):
        """Writes the import result. First a BACKUP of both files (also on
        merge - that overwrites them too), then an atomic write. It reports
        the number of records from the file that really got added to the
        history."""
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
                # HISTORY CAP (0.3): the oldest sessions over MAX_SESSIONS
                # dropped out - until now silently. The player's own are in the
                # backup before import, the ones from the file stay in the
                # imported file.
                sprava += "\n" + tr("data.import.limit", max=hr_stats.MAX_SESSIONS,
                                    n=orez["vypadlo"])
            if zalohy:
                # file names only - the full path in %APPDATA% carries the
                # account name
                sprava += "\n" + tr("data.import.backup", files=", ".join(
                    os.path.basename(z) for z in zalohy))
                sprava += " " + tr("data.import.backup_where")
            self._data_note(sprava)
        except Exception as exc:
            app_log.exception("zapis importu zlyhal")
            self._data_note(str(exc))

    def delete_history(self):
        """Deletes the history. It MUST list exactly what will disappear.

        The promise "everything stays with you" also means that "delete"
        really deletes - and that can only be shown by name.
        """
        # Old folders after the app was renamed: the migration only COPIED the
        # history from them, so a second copy stayed there - it gets deleted
        # too and the dialog names it (one line per folder, see
        # data_io.plan_riadky).
        stare = legacy_data_dirs()
        plan = data_io.delete_plan(DATA_DIR, legacy_dirs=stare)
        riadky = []
        for polozka in data_io.plan_riadky(plan):
            meno = tr(polozka["label"], **polozka["params"])
            if not polozka["exists"]:
                riadky.append(f"  · {meno} — {tr('data.delete.empty')}")
            else:
                riadky.append(f"  · {meno} — {polozka['bytes'] / 1024:.0f} kB")
        # NOT WHILE WATCHING (0.3): a running session would be saved right
        # back into the empty history on close. The button is disabled then
        # (`_refresh_data_delete_state`); this is a safeguard for Ctrl+K etc.
        if getattr(self, "_hr_session_open", False):
            self._data_note(tr("data.delete.stop_first"))
            return
        # Confirmation in the app window, not a system dialog: the button
        # carries the verb "Zmazat historiu" (Delete history) and is red, not
        # "Ano" (Yes). THREE CHOICES (0.3, audit): "Najprv exportovat..."
        # (Export first) runs the export and the question comes back - so
        # deleting is possible only with a copy in hand. The default (focus,
        # Enter, Escape) is Cancel.
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
            # watching turned on while the question was open (e.g.
            # auto-profile)
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
        """Question before deleting the whole history: "delete" / "export" /
        "cancel".

        `ui_kit.choose` (three buttons in the app window, focus on Cancel);
        without it at least `ui_kit.confirm` - then without the export
        choice."""
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
        """Deletes ONE saved session from the history (detail in History, 0.3).

        E.g. a 14-hour "session" across a sleeping PC: the sleeping heart
        rate would otherwise push down the resting baseline and the only fix
        was to delete the whole history. The confirmation names the date
        and the length (focus on Cancel). After the delete the insights are
        recomputed the same way as with the "Prepocitat" (Recompute) button
        (the baseline, the limit and the threshold are taken from the
        history at the next session) and the page is redrawn. The session
        being recorded right now is not in the history yet - and if its
        `started` were there, the app would not offer to delete it."""
        if not isinstance(session, dict) or session.get("started") is None:
            return False
        if self._je_nahravana_relacia(session):
            return False
        try:
            started = float(session.get("started"))
            time.localtime(started)         # time out of range -> exception
            # date in the app language, like the table in History
            # (0.3 batch 4b)
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
        # The measurement windows of that session go with it - otherwise its
        # cues would keep entering the "which cue works" chart.
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
        # The same as "Prepocitat" (Recompute, `history_recompute_btn`).
        self.run_hr_analysis()
        return True

    def _je_nahravana_relacia(self, session):
        """Is this the session being recorded now? Cannot be deleted here."""
        if not getattr(self, "_hr_session_open", False):
            return False
        try:
            return abs(float(session.get("started"))
                       - float(self.hr_stats.session_start)) < 1e-3
        except (TypeError, ValueError, AttributeError):
            return False

    def _ask_session_context(self, summary):
        """Asks what was going on during the session. Opens only AFTER the
        session is saved - the questionnaire attaches to a record that
        already exists.

        Short sessions are not saved at all, so we do not ask about them
        either: the caller handles this by coming here only when
        `save_session` succeeded.
        """
        try:
            # ONLY THE REALLY DELIVERED ONES. `delivered` is filled in by
            # `_on_cue_event`; without this condition the questionnaire also
            # counted cues that were not delivered (all slots off, failed
            # visual) and contradicted the saved count of `triggers` (bug B19).
            tiche = sum(1 for c in self._cue_log
                        if c.get("typ") == trigger.E_DELIVER
                        and c.get("delivered")
                        and c.get("arm") == trigger.ARM_SILENT)
            vsetky = sum(1 for c in self._cue_log
                         if c.get("typ") == trigger.E_DELIVER
                         and c.get("delivered"))
            dialog = SessionEndDialog(self, summary, cues=vsetky, silent=tiche)
            # The app remembers every open questionnaire (0.3 batch 4b): when
            # the player quits the app from the tray or Windows is shutting
            # down while a questionnaire from a normal Stop is still open,
            # `_dokonci_otvorene_dotazniky` saves the answers that were
            # touched - `root.destroy()` would otherwise throw them away.
            # Closed windows are dropped along the way so the list does not
            # grow over a long run.
            otvorene = []
            for stary in list(getattr(self, "_otvorene_dotazniky", None) or ()):
                try:
                    if stary.top.winfo_exists():
                        otvorene.append(stary)
                except Exception:
                    pass
            otvorene.append(dialog)
            self._otvorene_dotazniky = otvorene
            # WHEN THE APP IS CLOSING IT HAS TO WAIT.
            #
            # The dialog does `grab_set()`, but not `wait_window()`, so
            # `_ask_session_context` returned immediately. On a normal stop of
            # the measurement that is right - the window stays and the player
            # fills it in whenever they like. But `_quit` goes straight to
            # `root.destroy()`, so the questionnaire was thrown away before it
            # could even be drawn: when closing the app the session context
            # could NOT be filled in at all. And that is exactly when it is
            # turned off most often - I finished playing and I am going to
            # sleep.
            if getattr(self, "_zatvara_sa", False):
                # Through this reference the second "Ukoncit" (Quit) from the
                # tray closes the questionnaire (see `_quit`). Otherwise the
                # whole second quit would run inside the nested `wait_window`
                # loop and this `_quit` would return into a destroyed window.
                self._dotaznik_pri_zatvarani = dialog
                try:
                    self.root.wait_window(dialog.top)
                finally:
                    self._dotaznik_pri_zatvarani = None
        except Exception:
            app_log.exception("dotaznik kontextu sa nepodarilo otvorit")

    def _dokonci_dotaznik(self, dotaznik):
        """Finishes a questionnaire that quitting the app or a Windows shutdown
        would otherwise throw away (0.3, the author's decision; batch 4b
        extended it).

        Did the player touch at least one answer -> it is saved as "Ulozit"
        (Save); no -> it is closed as "Preskocit" (Skip). One line goes into
        the journal: saved, closed empty, or that saving failed. During this
        save `save_session_context` does not open an error window - while
        closing nobody would click it and the Windows shutdown would wait.

        A questionnaire without `bolo_vyplnene` (dummies) is taken as empty.
        It is closed even when saving failed: the first `_quit` may be
        waiting for it (`wait_window`)."""
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
        # The `confirm` of dummies returns nothing - None is not a failure.
        try:
            self.log(tr("session.context.save_failed") if ok is False
                     else tr("log.quit_questionnaire_saved"))
        except Exception:
            app_log.exception("ukoncenie: riadok o dotazniku sa nezapisal")
        return ok is not False

    def _dokonci_otvorene_dotazniky(self):
        """Finishes every questionnaire still open after a session
        (`_otvorene_dotazniky`, set up by `_ask_session_context`) according
        to `_dokonci_dotaznik`.

        Called on the first "Ukoncit" (Quit) and on Windows shutdown
        (WM_SAVE_YOURSELF). A window that is already gone (the player saved
        or skipped it) is skipped. Returns the number of finished
        questionnaires."""
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
        """Adds the context to the session just saved. Called by the dialog.

        Returns True on success. The context (coffee/alcohol/sleep - the
        biggest explainable source of variance in the measurement), the
        activity (playing/working) and the player's own note MUST NOT be
        lost silently: `attach_context` used to return True/False, but the
        return value was ignored and the dialog closed exactly as on success
        (bug B16). Now on failure an error is written and the player gets a
        message.
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
            # The playing/working answer can move the session to the other
            # world (B3-worlds): the detail would then point to a different
            # session and the insights would come from a different set - hence
            # the reset and a new analysis.
            zmena_sveta = (hr_stats.normalize_activity(activity) is not None
                           and hr_stats.normalize_activity(activity)
                           != hr_stats.session_world(summary))
            if zmena_sveta:
                self.history_detail_index = None
            # The session detail in History also shows "citene · merane" (felt
            # · measured) - without a redraw a dash would stay there after the
            # questionnaire until the next session. (The card on Today reads it
            # by itself at the next tick.)
            try:
                self._refresh_history_page()
            except Exception:
                app_log.exception("historia: prekreslenie po dotazniku zlyhalo")
            if zmena_sveta:
                self.run_hr_analysis()
        else:
            app_log.error("kontext relacie sa neulozil - relacia sa nenasla "
                          "alebo subor nebolo mozne zapisat")
            # On quit / Windows shutdown the app finishes the questionnaire
            # itself (`_dokonci_dotaznik`) and writes the error into the
            # journal - nobody would close a window there and the shutdown
            # would wait for it.
            if getattr(self, "_dotaznik_bez_okna_chyby", False):
                return False
            try:
                # app window, not a system one (0.3, batch 4)
                ui_kit.notify(getattr(self, "root", None), getattr(self, "pal", None),
                              APP_NAME, tr("session.context.save_failed"),
                              kind="warning")
            except Exception:
                pass
        return bool(ok)

    def _save_measure_windows(self):
        """Builds the measurement windows of the session that just ended and
        saves them.

        It is computed only here, at the end: at that moment `hr_stats._all`
        is complete, so one pass is enough and nothing needs timing. The
        price is that the window of the last cue may be cut short - it is
        written with a reason.

        No raw curve goes into the file, only averages over the bands of
        the window.
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
            # Every window carries the parameters the session ran with (spec
            # §3.3). Without that, a month later you cannot tell whether the
            # difference was in what changed or in how well the player slept.
            params = dict(self.cue_trigger.params)
            params["silent_share"] = self.cue_trigger.silent_share
            # The session world (B3-worlds) directly in the window: windows
            # live longer than sessions (MAX_SESSIONS), so joining them with
            # the summary would over time lose exactly the oldest ones. In
            # `world` "work" the cue had no voice or sound - so the
            # effectiveness chart can separate them one day.
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
            # The measurement must not crash the saving of the session - the
            # session summary is more important than the windows and is saved
            # right after.
            app_log.exception("meracie okna: zostavenie/ulozenie zlyhalo")

    def _maybe_graduate(self, summary):
        """After a session is saved: has the player reached "full Zanshin"?
        Runs ONCE.

        Reads the SAVED history (including the session just saved),
        evaluates `hr_stats.zanshin_graduation`; when met it sets a
        permanent flag, saves the settings, marks the summary for the
        questionnaire (mystical message) and switches the mark to the
        golden moon. The app keeps running - it is only an observation.

        Only after a GAME session (`hr_stats.ZEN_SVET`): the streak is
        counted from playing and the circle closes after a calm evening of
        playing - not in the questionnaire after work.
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
        """Saves the summary of the session just ended into hr_sessions.json.

        `koniec` (a time, 0.3): the session already ended back then - the
        last tick before the PC went to sleep (`_rozdel_relaciu_po_medzere`).
        The summary is closed at that time and the questionnaire does not
        open, the player was not there at the end. Saving is otherwise the
        same (`je_ulozitelna`, checkpoint, learning).

        Short sessions (under a minute or without data) are thrown away
        already in hr_stats.save_session - turning the sensor on and right
        off again is not a session.

        `pri_vypnuti=True` (Windows shutting down, `_pri_vypinani_windows`):
        save and nothing more. Windows waits for an answer for only a few
        seconds, so no questionnaire (it would be thrown away with the
        process), no graduation (a one-off message would never be shown to
        the player - it is evaluated after the next session) and no redraw
        of History and the analysis in the background.
        """
        if not self._hr_session_open:
            return
        self._hr_session_open = False
        # "Zmazat historiu" (Delete history) comes back with the end of the
        # session (0.3).
        _ak_vies(self, "_refresh_data_delete_state")
        # If it was just waiting for a pause, that gets written. From how often
        # a session ends in this state, `max_wait_s` can be tuned.
        try:
            udalost = self.cue_trigger.close_session()
            if udalost is not None:
                self._cue_log.append(dict(udalost))
        except Exception:
            app_log.exception("spustac hlasky: close_session zlyhal")
        # `close_session` writes to the log directly, not through
        # `_on_cue_event`, so the ring has to be dropped by hand. The sensor
        # can be turned off while listening goes on - so `set_live` will not
        # catch it.
        self._set_enso_armed(False)
        self._save_measure_windows()
        # Events of the state machine, permanently. Only HERE, not as they
        # come: a disk write on every event would happen in the Tk thread in
        # the middle of playing.
        try:
            data_io.append_events(self.hr_events_path, self._cue_log,
                                  started=getattr(self.hr_stats, "session_start", None))
        except Exception:
            app_log.exception("udalosti: zapis zlyhal")
        # The session ended earlier than now (the last tick before the PC went
        # to sleep, `_rozdel_relaciu_po_medzere`): the summary is closed at
        # that time.
        summary = (self._suhrn_relacie() if koniec is None
                   else self._suhrn_relacie(koniec=koniec))
        # Only AFTER the summary is built: these counters still belong to this
        # session only. `_suhrn_relacie` only reads them (the checkpoint calls
        # it too, in the middle of a session); resetting is the job of closing.
        self._snooze_po_hlaske = None
        self._snooze_rel_s = 0.0
        self._snooze_rel_od = None
        self._hud_tick_t = None
        # A write error goes into the journal with its own sentence
        # (`_relacia_sa_neulozila`), not as a technical line from
        # `save_session`; the other lines (e.g. a set-aside broken file) go
        # into the journal as before.
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
        # The checkpoint is no longer needed - the session is in the history.
        # When it could not be saved (full disk), it stays and the recovery
        # tries it at the next start; a short session, which would not get in
        # anyway, deletes it too.
        if ulozena or not ulozitelna:
            hr_stats.zahod_rozpracovanu(self.hr_sessions_path)
        if not ulozena and ulozitelna:
            # WRITE FAILED (0.3): full disk, access denied, locked file. The
            # session must not vanish silently - a line, a notice and the
            # summary set aside into hr_session_pending.json (the next start
            # adds it).
            _ak_vies(self, "_relacia_sa_neulozila",
                     summary, chyby_zapisu[-1] if chyby_zapisu else "?",
                     oznam=not pri_vypnuti and not getattr(self, "_zatvara_sa", False))
        elif not ulozena:
            _ak_vies(self, "_kratka_relacia_bez_tepu", summary)
        if ulozena:
            # The setup mark is carried only by the FIRST session that really
            # got saved. A short one (under a minute, no heart rate - e.g.
            # before the watch is paired) is not saved, so the mark waits for
            # the next one.
            self._relacia_nastavovania = False
            # The disk is writable again - what was left aside last time goes
            # in.
            if not pri_vypnuti:
                _ak_vies(self, "_dopln_cakajuce_relacie")
        if ulozena and not pri_vypnuti:
            # After the PC went to sleep (`koniec`) no questionnaire: the
            # player was not there and the window would pop up in front of the
            # game after wake-up (0.3). And for that reason no graduation
            # either - its one-off message is carried by the questionnaire
            # (`zen_graduation`), so it would never show; it is evaluated after
            # the next session, just like on a Windows shutdown.
            if koniec is None:
                self._maybe_graduate(summary)
                self._ask_session_context(summary)
        if ulozena:
            self.log(tr("log.hr_session_saved",
                        avg=summary.get("avg_bpm") or "-",
                        max=summary.get("max_bpm") or "-",
                        peak=summary.get("peak_stress")))
            # a new session in history -> redraw the page and recompute the
            # insights (in the background). The history cache has to go first,
            # otherwise the cards and the chart would keep drawing the state
            # from before this session for another 20 seconds.
            self._history_cache = (0.0, None)
            if pri_vypnuti:
                return
            try:
                self._refresh_history_page()
            except Exception:
                app_log.exception("historia: prekreslenie zlyhalo")
            self.run_hr_analysis()

    def _suhrn_relacie(self, koniec=None):
        """Summary of the running session - exactly what closing would save.

        NO SIDE EFFECTS: it is called by `_close_hr_session` and also by the
        checkpoint (`_zapis_rozpracovanu_relaciu`) every few minutes in the
        middle of playing, so it resets nothing and adds nothing to the app
        state. One source of the summary, so that a recovered session does not
        differ from a normally saved one.

        `koniec` (0.3) = the session already ended then (the last tick before
        the PC went to sleep) - all times in the summary are counted up to it,
        not up to now.
        """
        summary = (self.hr_stats.summary() if koniec is None
                   else self.hr_stats.summary(koniec=koniec))
        teraz = time.time() if koniec is None else float(koniec)
        # THE WORLD THE SESSION STARTED IN (B3-worlds). A separate key, not
        # `activity`: that is the player's answer in the questionnaire and a
        # machine label must not cover it - later it has to be possible to tell
        # what the player really confirmed. Which one applies is decided by
        # `hr_stats.session_world`.
        summary["world"] = getattr(self, "_session_world", hr_stats.WORLD_DEFAULT)
        # APP SETUP (0.3): until the first session after the introduction is
        # saved, it is time spent at the desk (pairing, tour), not playing -
        # thresholds are not learned from it (`hr_stats.ciste_relacie`). It
        # goes into the checkpoint too, so it still holds after a recovery.
        # The player can cancel it in the questionnaire.
        if getattr(self, "_relacia_nastavovania", False):
            summary["setup"] = True
        # EXCLUSIVE FULLSCREEN (0.3 batch 4): the app noticed it in this
        # session (`_warn_exclusive_fullscreen_once`) - Windows does not draw
        # pictures over such a game. One flag, the questionnaire uses it to say
        # the sentence `session.end.fullscreen_note`.
        if getattr(self, "_session_fullscreen", False):
            summary["fullscreen"] = True
        # WHY THIS IS ATTACHED TO THE SUMMARY
        # The first real evening ended with zero cues, although the peak load
        # was 87 at a threshold of 55. From the summary you could not tell
        # whether the "sustained 90 s" rule was too strict, or whether
        # heart-rate dropouts broke the counting.
        # These are single numbers, not a curve - nothing raw goes to the file.
        try:
            summary["longest_above_s"] = round(self.cue_trigger.najdlhsi_nad_s, 1)
            summary["above_runs"] = self.cue_trigger.behov_nad
            summary["runs_cancelled_dip"] = self.cue_trigger.zrusenych_prepadom
            summary["runs_cancelled_gap"] = self.cue_trigger.zrusenych_vypadkom
            summary["stress_hold_s"] = self.cue_trigger.params["stress_hold_s"]
            # AT WHICH threshold the session ran. After a few evenings the
            # threshold is computed from the player's own data (`_prah_z_dat`)
            # and changes between sessions - without it, after a few evenings
            # you cannot say whether an evening was at 55, 78 or 72, nor
            # separate the evenings before and after the trigger fix.
            summary["stress_threshold"] = self.cue_trigger.params["stress_threshold"]
            # CUE GATE (0.2): how many pauses in the input the app saw at all
            # during the session and how many armings it cancelled itself
            # (by reason). Zero pauses over a long evening = the voice had no
            # moment to sound; the questionnaire says so plainly
            # (`SessionEndDialog._preco_ticho`).
            summary["pause_episodes"] = self.cue_trigger.pause_episodes
            summary["cues_withheld"] = dict(self.cue_trigger.zadrzane)
            # CUE LADDER (0.2, `rebrik.py`): the rung and style the session ran
            # on, and "not now" shortly after a cue - together with how long
            # the session kept running after it (`_zapis_snooze_po_hlaske`).
            summary["cue_rung"] = getattr(self, "_cue_rung", rebrik.HLAS)
            summary["cue_style"] = getattr(self, "_cue_style_rel", rebrik.STYL_HLAS)
            # How many automatic cues were really SHOWN (0.2.1). The ladder
            # counts a session "with a cue" by this, not by `auto_triggers` -
            # that one also counts a cue with a failed picture, of which the
            # player saw nothing (see `rebrik._hlasok`). The same rule as the
            # questionnaire (`_ask_session_context`) and
            # `hr_stats.last_auto_cue_ts`.
            summary["cues_delivered"] = sum(
                1 for c in getattr(self.hr_stats, "cues", ())
                if c.get("source") == "auto" and c.get("delivered", True))
            snooze = getattr(self, "_snooze_po_hlaske", None)
            if snooze is not None:
                summary["snooze_after_cue_s"] = snooze[0]
                summary["snooze_then_s"] = round(max(0.0, teraz - snooze[1]), 1)
            # The long-term baseline the load in this session was computed
            # against (None = there was nothing to build it from yet).
            dlhodoba = self.hr_stats.long_baseline
            summary["long_baseline_bpm"] = (round(float(dlhodoba), 1)
                                           if dlhodoba is not None else None)
        except Exception:
            app_log.exception("suhrn: pocitadla spustaca sa nepodarilo pridat")
        # How much of the session "not now" was in effect (since 24. 9. it does
        # not close the session). The counters above do not see that time - the
        # state machine was asleep then - so the questionnaire and the insights
        # must not use them to explain a silence the player chose themselves
        # (`SessionEndDialog._preco_ticho`, `hr_insights`).
        od = getattr(self, "_snooze_rel_od", None)
        stisene = getattr(self, "_snooze_rel_s", 0.0) or 0.0
        if od is not None:
            stisene += max(0.0, teraz - od)
        if stisene > 0.0:
            summary["snoozed_s"] = round(stisene, 1)
        # How much of the session the player actually saw their heart rate
        # (HUD). The last stretch from the last tick to now is added - into
        # local variables, not into `_hud_*` (otherwise the checkpoint would
        # add that stretch twice). A share of the duration: a session with a
        # visible HUD is a different experiment than a blind one (biofeedback).
        try:
            videl_s, aktivne_s = self._hud_vis_s, self._hud_active_s
            if self._hud_tick_t is not None:
                dt = teraz - self._hud_tick_t
                if 0.0 < dt < 5.0:
                    aktivne_s += dt
                    if self._hud_is_visible():
                        videl_s += dt
            summary["hud_visible_s"] = round(videl_s, 1)
            # A share of the ACTIVE session time, not of the raw duration:
            # numerator and denominator drop the same gaps (PC asleep), so the
            # share does not drop artificially after a sleep.
            if aktivne_s > 0:
                summary["hud_visible_frac"] = round(
                    max(0.0, min(1.0, videl_s / aktivne_s)), 3)
        except Exception:
            app_log.exception("suhrn: viditelnost HUD-u sa nepodarilo pridat")
        return summary

    # ---------- Windows shutdown, checkpoint, crash recovery ----------

    def _pri_vypinani_windows(self):
        """Windows is shutting down, restarting or logging off
        (WM_SAVE_YOURSELF).

        WHY THIS AND NOT WM_DELETE_WINDOW: on PC shutdown Windows does not
        close the window, it sends WM_QUERYENDSESSION and then ends the
        process. Tk on Windows (tkWinWm.c, WmProc) turns WM_QUERYENDSESSION
        into the WM_SAVE_YOURSELF protocol and calls the handler RIGHT AWAY,
        synchronously - Windows meanwhile waits for the answer. Verified live
        on Tk 9.0, which the app bundles (tests/test_022b_data_vypnutie.py):
        WM_QUERYENDSESSION sent to a borderless window hidden in the tray calls
        the WM_SAVE_YOURSELF handler, WM_DELETE_WINDOW does not. Until now the
        app only knew WM_DELETE_WINDOW, so a PC shutdown threw away the whole
        session and its events.

        It must be FAST: after a few seconds Windows shows "This app is
        preventing shutdown". So we only save the session, without the
        questionnaire and settings - `_quit` (questionnaire, stopping threads)
        is not called here, the process ends anyway. Safe also during `_quit`
        (the session is already closed, only the settings are saved) and twice
        in a row (`_hr_session_open` guards it).
        """
        if getattr(self, "_vypnutie_bezi", False):
            return
        self._vypnutie_bezi = True
        try:
            # An open questionnaire (from a normal Stop, or the one `_quit` is
            # waiting for) would be thrown away with the process: touched
            # answers are saved like "Save", an untouched one is closed like
            # "Skip" (0.3 batch 4b, the same rule as on quit). Only a file
            # write - fast.
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
            # THE SHUTDOWN CAN BE CANCELLED (another app blocks it and the
            # player presses Cancel). Tk does not tell the app - the app would
            # then listen, but without an open session it would measure nothing
            # (exactly bug A1). When the process is still alive a moment later,
            # the shutdown did not happen: the session is opened again. When
            # Windows does shut down, this never runs.
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
        """Windows stayed on after all - measuring goes on in a new session."""
        self._vypnutie_job = None
        if getattr(self, "_quit_bezi", False) or getattr(self, "_zatvara_sa", False):
            return
        if (not getattr(self, "listening", False)
                or not getattr(self, "hr_monitoring_enabled", False)
                or getattr(self, "_hr_session_open", False)):
            return
        try:
            if self.heart_rate_monitor.running:
                # Receiving keeps running, we do not touch the network (like
                # `start_listening`).
                self._open_hr_session(prepoj=False, meria=True)
                app_log.info("vypnutie Windows sa zrusilo - nova relacia otvorena")
        except Exception:
            app_log.exception("po zrusenom vypnuti sa relacia neotvorila")

    def _naplanuj_rozpracovanu_relaciu(self):
        """Next checkpoint in `ROZPRACOVANA_KAZDYCH_MS`. Called once from
        `__init__`, after that the tick schedules itself."""
        try:
            self._rozpracovana_job = self.root.after(
                ROZPRACOVANA_KAZDYCH_MS, self._tik_rozpracovanej_relacie)
        except Exception:
            self._rozpracovana_job = None
            app_log.exception("kontrolny bod relacie sa nepodarilo naplanovat")

    def _tik_rozpracovanej_relacie(self):
        self._rozpracovana_job = None
        # Nothing while quitting: the session is being saved normally right now
        # and after `root.destroy()` there is nowhere left to schedule.
        if getattr(self, "_quit_bezi", False) or getattr(self, "_zatvara_sa", False):
            return
        try:
            self._zapis_rozpracovanu_relaciu()
        except Exception:
            app_log.exception("kontrolny bod relacie zlyhal")
        self._naplanuj_rozpracovanu_relaciu()

    def _zapis_rozpracovanu_relaciu(self):
        """Checkpoint: summary of the open session into hr_session_open.json.

        WHY EVERY 5 MINUTES, NOT ON EVERY SAMPLE: the write runs in the Tk
        thread in the middle of playing (the same reason why events are written
        only at the end). On a crash at most the last 5 minutes are lost, not
        the whole evening. Events and measurement windows are NOT WRITTEN
        here - they belong to closing (windows are built from the whole session
        at once), so after a crash they are missing. Returns True when it
        wrote."""
        if not getattr(self, "_hr_session_open", False):
            return False
        summary = self._suhrn_relacie()
        if not hr_stats.je_ulozitelna(summary):
            return False
        return hr_stats.zapis_rozpracovanu(self.hr_sessions_path, summary,
                                           log=app_log.warning)

    def _obnov_rozpracovanu_relaciu(self):
        """At start: a session that was not saved last time goes into history.

        Called from `__init__` before the sensor is switched on (no new session
        is open yet). One line to the journal, technical reasons only to
        app.log.

        First the sessions that could not be SAVED last time
        (`hr_session_pending`, 0.3): they are complete, while the checkpoint of
        the same session is up to 5 minutes old - that one is then thrown away
        as a duplicate (`_uz_v_historii`).
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
        # The same date format as the session list in History (app language).
        kedy = ui_kit.datum_text(obnovena["started"], cas=True)
        self.log(tr("log.hr_session_recovered", time=kedy))
        self._history_cache = (0.0, None)
        try:
            self._refresh_history_page()
        except Exception:
            app_log.exception("historia: prekreslenie po obnove zlyhalo")
        return obnovena

    # ---------- session that could not be saved (0.3) ----------

    def _relacia_sa_neulozila(self, summary, chyba, oznam=True):
        """Writing the session failed (full disk, access denied, JSON).

        Before 0.3 it vanished silently: a technical line in the journal and
        nothing more. Now one line, one notice in the app window (no system
        window) and the summary set aside into hr_session_pending.json - on the
        next start (or after the next successful save) it is added as a
        recovered session. The checkpoint of the same session STAYS as a second
        copy: start first adds this (complete) one and then throws the older
        checkpoint away as a duplicate. `oznam=False` when quitting and on a
        Windows shutdown - a window would block the end; the journal line and
        the set-aside file remain."""
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
            # Without a notice at least a line in the data panel (the journal
            # already has the sentence).
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
        """The session ran for at least a minute, but not even 10 heart-rate
        samples came from the watch - it is not saved (`je_ulozitelna`). Until
        now without a word (audit 4)."""
        try:
            trvanie = float(summary.get("duration_s") or 0)
            vzorky = float(summary.get("samples") or 0)
        except (TypeError, ValueError, AttributeError):
            return
        if trvanie >= 60 and vzorky < 10:
            self.log(tr("log.hr_session_no_data"))

    def _dopln_cakajuce_relacie(self):
        """Sessions from hr_session_pending.json into history
        (`hr_stats.obnov_cakajuce`). One journal line for each. Returns the list of
        the added ones."""
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
        """Once: an installed 0.2 shares the data folder with this version.

        Its uninstaller asks "Ponechat nastavenia...?" (Keep settings...?) and
        on No deletes %APPDATA%\\Zanshin - including the history of this (ZIP)
        version, which lives in the same folder. When running from source the
        data lives next to main.py, so this does not apply here and the check
        is skipped.
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
            # Remembered only after it is shown: if the app ends before that,
            # the warning comes at the next start.
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
        """One tip to the log if the game runs in exclusive fullscreen.

        In it Windows does not draw foreign layered windows at all - the player
        would see that the sensor is running, but no visual would show up and
        they would have no way to find out why.

        The journal line goes once per app run. Since 0.3 (batch 4) EVERY
        session also remembers it (`_session_fullscreen`, reset by
        `_open_hr_session`) - the summary carries `fullscreen` and the
        post-game questionnaire says one sentence about why the pictures could
        not be seen over that game. Once both the session and the journal know,
        the window is not checked in the following seconds.
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

    # ---------- profile import / export (sharing by code) ----------

    def export_profile_code(self):
        self._sync_active_profile_slots()
        profile = next((p for p in self.profiles if p["name"] == self.active_profile_name),
                       None)
        if profile is None:
            return
        try:
            # Only what makes sense for another player (`slot_na_zdielanie`):
            # NO absolute paths to recordings (they carried the Windows account
            # name), no uid and no dead fields from the days of key triggers.
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
        # An imported profile gets a FRESH uid and no local recordings
        # (`slot_zo_zdielania`). A uid from another profile/machine would
        # otherwise share the recording files (rec_<uid>.wav) and re-recording
        # would overwrite someone else's clip - exactly the data loss uid was
        # created against (B1). Paths to .wav are reset ALWAYS, even with an
        # empty `sfx_key`: a foreign path would otherwise be played if it
        # happened to exist on this PC. It falls back to TTS / preset SFX.
        slots = [s for s in (slot_zo_zdielania(x) for x in data["slots"]) if s]
        # A code from 0.1 may carry fewer than four slots - the missing
        # categories are added at the end (disabled), nothing is overwritten.
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
        # The four categories are fixed: the category, picture and measurement
        # are set by the slot's POSITION, so removing one would shift the texts
        # under another category and there is no going back. It is turned off
        # with the switch; only an extra slot from 0.1 (index 4+) has ✕.
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
        """Shows/hides the bulk-action bar by the number of selected slots."""
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
        """Removes all selected slots at once - one action, one confirmation.

        Just like remove_slot it does not allow deleting absolutely everything:
        at least one slot must stay, otherwise the profile would be left empty
        and the app would have nothing to trigger. If the selection covered all
        of them, one (the first unselected, or the last) is kept and the player
        gets a message.
        """
        # Only extra slots (index 4+) - the four categories are not removed,
        # see `remove_slot`.
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
        # App window with a verb on the button, focus on "Cancel" (0.3).
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
