"""UI dialogy a karty hlavneho okna - vsetko, co otvara vlastny CTkToplevel
alebo je samostatny vizualny "widget" (karta slotu, tooltip, stepper).

Vsetky triedy tu pracuju s `app` (instancia DandurfApp z app.py) len cez
jeho verejne metody/atributy - neduplikuju ziadnu logiku, len ju volaju.
"""

import os
import shutil
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import numpy as np

import customtkinter as ctk

import guide_panel
import ui_kit

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

import hr_stats           # CONTEXT_IDS pre dotaznik na konci relacie
import rebrik             # stupen rebrika hlasky (obraz / pauza)
import trigger            # dovody, preco sa appka sama rozhodla mlcat
import hud_paint          # onboarding kresli realne piktogramy a HUD
import netinfo            # skryta IP v okne parovania (mask_ip)
import sfx_assets
import theme as theme_mod
from audio_engine import MicRecorder, play_audio_file
from i18n import tr
from paths import APP_NAME, AUDIO_DIR, images_dir
from settings_model import (BREATH_SECONDS_MAX, BREATH_SECONDS_MIN, MODE_COMBO, MODE_ORDER,
                            MODE_SFX, MODE_TTS, je_kategoria, label_to_mode,
                            mode_labels, normalize_slot, sfx_choice_display,
                            sfx_dropdown_options)


# --------------------------------------------------------------------------
# Jednoduchy hover tooltip (obycajny tk.Toplevel - nepotrebuje CTk temovanie)
# --------------------------------------------------------------------------

class HoverTooltip:
    """Priradi sa na existujuci widget - po najazdeni po chvili zobrazi
    maly popis pod nim, po odchode mysi zmizne."""

    def __init__(self, widget, text, pal, delay=350):
        self.widget = widget
        self.text = text
        self.pal = pal
        self.delay = delay
        self._after_id = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel_timer()
        self._after_id = self.widget.after(self.delay, self._show)

    def _cancel_timer(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        if self._tip is not None or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 6
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
            self._tip = ui_kit.priprav_popup(tk.Toplevel(self.widget))
            self._tip.wm_overrideredirect(True)
            self._tip.attributes("-topmost", True)
            self._tip.wm_geometry(f"+{x}+{y}")
            # Rovnaky tvar ako bubliny v bocnom paneli (`ui_shell._HoverTip`):
            # zaoblene, s ramom z temy. `tk.Label(relief="solid")` kreslil
            # hranaty ram systemovou farbou - jedine miesto v appke, kde bol
            # ostry ciernobiely okraj.
            frame = ctk.CTkFrame(self._tip, fg_color=self.pal["surface_alt"],
                                 corner_radius=8, border_width=1,
                                 border_color=self.pal["border"])
            frame.pack()
            ctk.CTkLabel(frame, text=self.text, justify="left", fg_color="transparent",
                         text_color=self.pal["text"], font=ui_kit.ui(10),
                         padx=10, pady=6, wraplength=260).pack()
        except Exception:
            self._tip = None

    def _hide(self, _event=None):
        self._cancel_timer()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


# --------------------------------------------------------------------------
# Dialog s podrobnym nastavenim jedneho slotu
# --------------------------------------------------------------------------

class SlotSettingsDialog:
    """Hlas jednej hlasky. Nic viac.

    Do 18. 9. tu sedelo aj cele casovanie - vlastna pauza, oneskorenie,
    "kazde N-te spustenie", opakovanie a rozptyl. Ziadna z tych hodnot sa pri
    hrani necitala: automaticku hlasku spusta `trigger.CueTrigger` podla
    zataze tela a doruci ju `_emit`, ktory z karty berie text, rezim a zvuk.
    Sest posuvnikov teda ladilo jedine tlacidlo Test.

    Kedy sa appka ozve sa nastavuje na jednom mieste pre vsetky hlasky
    (stranka Hlasky, "ako casto sa ozvem"), lebo to je vlastnost cloveka,
    nie jednotlivej vety.
    """

    def __init__(self, app, slot):
        self.app = app
        self.slot = slot
        pal = app.pal
        app.set_typing(True)

        self.top = ctk.CTkToplevel(app.root)
        self.top.title(tr("dialog.slot_settings_title", n=slot.index + 1))
        self.top.configure(fg_color=pal["bg"])
        self.top.resizable(False, False)
        self.top.transient(app.root)
        self.top.grab_set()

        chrome = ui_kit.DialogChrome(
            self.top, pal, tr("dialog.slot_settings_title", n=slot.index + 1), on_close=self.close)
        body = ctk.CTkFrame(chrome.body, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=16)

        ctk.CTkLabel(body, text=tr("dialog.voice_label"),
                     font=ui_kit.ui(12, "bold"), text_color=pal["text"],
                     anchor="w").pack(fill="x")
        self.voice_var = tk.StringVar()
        names = [tr("voice.global")] + app.current_voice_names()
        self.voice_box = ctk.CTkOptionMenu(
            body, values=names, variable=self.voice_var, width=340,
            fg_color=pal["surface_alt"], button_color=pal["accent2"],
            button_hover_color=pal["accent2_hover"], text_color=pal["text"],
            dropdown_fg_color=pal["surface"], dropdown_text_color=pal["text"])
        self.voice_box.pack(fill="x", pady=(6, 6))
        self.voice_var.set(app.slot_voice_label(slot) or tr("voice.global"))

        ctk.CTkLabel(body, text=tr("dialog.voice_note"), font=ui_kit.ui(10),
                     text_color=pal["text_dim"], anchor="w", justify="left",
                     wraplength=340).pack(fill="x", pady=(0, 14))

        # --- Vlastna nahravka hlasu ------------------------------------------
        # Namiesto strojoveho hlasu (TTS) sa da pouzit vlastna nahravka: tvoj
        # hlas povie "dychaj". Ak je nastavena, prehra sa namiesto TTS (viz
        # app._speak_text) - cela a cista, bez filtra na kroky, rovnako ako
        # offline hlas. Zije tu, lebo je to sucast "hlasu jednej hlasky".
        ctk.CTkLabel(body, text=tr("dialog.voice_rec_label"),
                     font=ui_kit.ui(12, "bold"), text_color=pal["text"],
                     anchor="w").pack(fill="x")
        self.voice_clip_status = ctk.CTkLabel(
            body, text=self._voice_clip_text(), font=ui_kit.ui(11),
            text_color=pal["text_dim"], anchor="w", justify="left", wraplength=340)
        self.voice_clip_status.pack(fill="x", pady=(4, 6))

        vrow = ctk.CTkFrame(body, fg_color="transparent")
        vrow.pack(fill="x", pady=(0, 4))
        ctk.CTkButton(vrow, text=tr("dialog.voice_rec_record"), width=104,
                      fg_color=pal["surface_alt"], hover_color=pal["border"],
                      text_color=pal["text"], command=self.record_voice).pack(side="left")
        ctk.CTkButton(vrow, text=tr("dialog.voice_rec_file"), width=104,
                      fg_color=pal["surface_alt"], hover_color=pal["border"],
                      text_color=pal["text"], command=self.choose_voice).pack(side="left", padx=8)
        ctk.CTkButton(vrow, text=tr("dialog.voice_rec_clear"), width=88,
                      fg_color=pal["surface_alt"], hover_color=pal["border"],
                      text_color=pal["text"], command=self.clear_voice).pack(side="right")

        ctk.CTkLabel(body, text=tr("dialog.voice_rec_note"), font=ui_kit.ui(10),
                     text_color=pal["text_dim"], anchor="w", justify="left",
                     wraplength=340).pack(fill="x", pady=(0, 14))

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x")
        ctk.CTkButton(buttons, text=tr("common.cancel"), width=90,
                      fg_color=pal["surface_alt"], hover_color=pal["border"],
                      text_color=pal["text"], command=self.close).pack(side="right")
        ctk.CTkButton(buttons, text=tr("common.save"), width=90,
                      fg_color=pal["accent"], hover_color=pal["accent_hover"],
                      text_color=pal["bg"], command=self.save).pack(
            side="right", padx=(0, 8))

        self.top.protocol("WM_DELETE_WINDOW", self.close)

    def save(self):
        app, slot = self.app, self.slot
        label = self.voice_var.get()
        if label == tr("voice.global"):
            app.set_slot_voice(slot, "")
        else:
            app.set_slot_voice(slot, app.voice_id_for_label(label))
        slot.refresh_summary()
        app.save_settings()
        app.schedule_pregenerate(200)
        app.log(tr("log.slot_voice_saved", n=slot.index + 1, voice=label))
        self.close()

    def close(self):
        self.app.set_typing(False)
        try:
            self.top.grab_release()
        except Exception:
            pass
        self.top.destroy()

    # ---- vlastna nahravka hlasu ----
    #
    # Nahravka je okamzita operacia so suborom, preto sa (na rozdiel od vyberu
    # hlasu v rozbalovacke) uklada hned - Zrusit nema co brat spat a clovek by
    # neprisiel o nahravku len preto, ze zavrel dialog.

    def _voice_clip_text(self):
        vp = getattr(self.slot, "voice_path", "")
        if vp and os.path.exists(vp):
            return tr("dialog.voice_rec_set", name=os.path.basename(vp))
        return tr("dialog.voice_rec_none")

    def _commit_voice(self, log_msg):
        try:
            self.voice_clip_status.configure(text=self._voice_clip_text())
        except Exception:
            pass
        self.slot.refresh_summary()
        self.app.save_settings()
        self.app.schedule_pregenerate(200)
        self.app.log(log_msg)

    def record_voice(self):
        target = os.path.join(AUDIO_DIR, f"voice_{self.slot.uid}.wav")
        dialog = RecordDialog(self.app, self.slot.index + 1, target)
        self.app.root.wait_window(dialog.top)
        try:
            self.top.grab_set()   # vrat grab spat tomuto dialogu
        except Exception:
            pass
        if dialog.saved_path:
            self.slot.voice_path = dialog.saved_path
            self._commit_voice(tr("log.slot_voice_recorded", n=self.slot.index + 1))

    def choose_voice(self):
        path = filedialog.askopenfilename(
            title=tr("dialog.choose_voice_title", n=self.slot.index + 1),
            filetypes=[(tr("filetype.audio"), "*.wav *.mp3"),
                       (tr("filetype.all"), "*.*")])
        if not path:
            return
        try:
            self.slot.voice_path = self.slot._import_into_store(
                path, f"voice_pick_{self.slot.uid}")
        except Exception as exc:
            messagebox.showerror(APP_NAME, tr("record.save_error", err=exc),
                                 parent=self.top)
            return
        self._commit_voice(tr("log.slot_voice_set", n=self.slot.index + 1,
                              name=os.path.basename(self.slot.voice_path)))

    def clear_voice(self):
        if not getattr(self.slot, "voice_path", ""):
            return
        self.slot.voice_path = ""
        self._commit_voice(tr("log.slot_voice_cleared", n=self.slot.index + 1))

# --------------------------------------------------------------------------
# Dialog na vytvorenie noveho profilu (hry)
# --------------------------------------------------------------------------

class NewProfileDialog:
    def __init__(self, app):
        self.app = app
        pal = app.pal
        app.set_typing(True)

        self.top = ctk.CTkToplevel(app.root)
        self.top.title(tr("profile.new_title"))
        self.top.configure(fg_color=pal["bg"])
        self.top.resizable(False, False)
        self.top.transient(app.root)
        self.top.grab_set()

        chrome = ui_kit.DialogChrome(
            self.top, pal, tr("profile.new_title"), on_close=self.close)
        body = ctk.CTkFrame(chrome.body, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=16)

        ctk.CTkLabel(body, text=tr("profile.name_label"), text_color=pal["text"]).pack(
            anchor="w", pady=(0, 6))
        self.name_var = tk.StringVar()
        self.name_entry = ctk.CTkEntry(body, textvariable=self.name_var, width=300,
                                       fg_color=pal["entry_bg"], border_color=pal["border"],
                                       text_color=pal["text"])
        self.name_entry.pack(fill="x", pady=(0, 14))
        self.name_entry.bind("<Return>", lambda _e: self.confirm())
        self.name_entry.focus_set()

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x")
        ctk.CTkButton(buttons, text=tr("common.cancel"), width=90, fg_color=pal["surface_alt"],
                     hover_color=pal["border"], text_color=pal["text"],
                     command=self.close).pack(side="right")
        ctk.CTkButton(buttons, text=tr("common.save"), width=90, fg_color=pal["accent"],
                     hover_color=pal["accent_hover"], text_color=pal["bg"],
                     command=self.confirm).pack(side="right", padx=(0, 8))

        self.top.protocol("WM_DELETE_WINDOW", self.close)

    def confirm(self):
        self.app.create_profile(self.name_var.get())
        self.close()

    def close(self):
        self.app.set_typing(False)
        try:
            self.top.grab_release()
        except Exception:
            pass
        self.top.destroy()


class DevLayerDialog:
    """Vyvojarska vrstva: cisla zo zadania §2, editovatelne za behu.

    PRECO EXISTUJE: tie cisla su odhady z literatury, nie z tela tohto
    hraca. Prve tyzdne sa bude zistovat, ze hlaska chodi bud priskoro,
    alebo vobec. Bez moznosti otocit to za behu by sa muselo rebuildovat
    kazdy vecer.

    PRECO SA DA EDITOVAT LEN MEDZI RELACIAMI: zadanie §3.3. Menit prahy
    uprostred relacie znamena merat pohyblivy ciel - okna z prvej polovice
    vecera a z druhej by sa nedali porovnat a nikto by uz spatne nezistil,
    ktore bolo ktore. Preto sa polia pri beziacej relacii ZAMKNU; nie je
    to odporucanie v texte, ale vynutene.
    """

    POLIA = (
        ("stress_threshold", "0-100"),
        ("stress_hold_s", "s"),
        ("dip_grace_s", "s"),
        ("pause_s", "s"),
        ("max_wait_s", "s"),
        ("away_s", "s"),
        ("min_gap_s", "s"),
    )

    def __init__(self, app):
        self.app = app
        self.entries = {}
        pal = app.pal
        bezi = app._hr_session_open

        self.top = ctk.CTkToplevel(app.root)
        self.top.title(tr("dev.title"))
        self.top.configure(fg_color=pal["bg"])
        self.top.resizable(False, True)
        self.top.transient(app.root)

        chrome = ui_kit.DialogChrome(
            self.top, pal, tr("dev.title"), on_close=self.close)
        body = ctk.CTkFrame(chrome.body, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=18)

        ctk.CTkLabel(body, text=tr("dev.title"), font=ui_kit.ui(15, "bold"),
                     text_color=pal["text"], anchor="w").pack(fill="x")
        ctk.CTkLabel(body, text=tr("dev.locked" if bezi else "dev.hint"),
                     font=ui_kit.ui(11),
                     text_color=pal["warn"] if bezi else pal["text_dim"],
                     anchor="w", justify="left", wraplength=430).pack(
            fill="x", pady=(4, 14))

        mriezka = ctk.CTkFrame(body, fg_color="transparent")
        mriezka.pack(fill="x")
        params = app.cue_trigger.params
        for riadok, (kluc, jednotka) in enumerate(self.POLIA):
            ctk.CTkLabel(mriezka, text=tr(f"dev.param.{kluc}"), font=ui_kit.ui(12),
                         text_color=pal["text_dim"], anchor="w").grid(
                row=riadok, column=0, sticky="w", pady=3)
            var = tk.StringVar(value=f"{params[kluc]:g}")
            entry = ctk.CTkEntry(mriezka, textvariable=var, width=72, height=26,
                                 fg_color=pal["entry_bg"], border_width=1,
                                 border_color=pal["line_soft"],
                                 text_color=pal["text"], font=ui_kit.mono(12))
            entry.grid(row=riadok, column=1, padx=(14, 6), pady=3)
            if bezi:
                entry.configure(state="disabled")
            ctk.CTkLabel(mriezka, text=jednotka, font=ui_kit.ui(10),
                         text_color=pal["text_faint"], anchor="w").grid(
                row=riadok, column=2, sticky="w")
            self.entries[kluc] = var

        # Podiel ticha zvlast - nie je to prah, je to navrh pokusu.
        ctk.CTkLabel(body, text=tr("dev.silent"), font=ui_kit.ui(12),
                     text_color=pal["text_dim"], anchor="w").pack(
            fill="x", pady=(14, 4))
        self.silent_var = tk.StringVar(value=f"{app.cue_trigger.silent_share:g}")
        silent_entry = ctk.CTkEntry(body, textvariable=self.silent_var, width=72,
                                    height=26, fg_color=pal["entry_bg"],
                                    border_width=1, border_color=pal["line_soft"],
                                    text_color=pal["text"], font=ui_kit.mono(12))
        silent_entry.pack(anchor="w")
        if bezi:
            silent_entry.configure(state="disabled")

        tlacidla = ctk.CTkFrame(body, fg_color="transparent")
        tlacidla.pack(fill="x", pady=(16, 0))
        if not bezi:
            ctk.CTkButton(tlacidla, text=tr("common.save"), width=110, height=32,
                          corner_radius=ui_kit.RADIUS_CONTROL, fg_color=pal["accent"],
                          hover_color=pal["accent_hover"], text_color=pal["bg"],
                          command=self.confirm).pack(side="left", padx=(0, 8))
            ctk.CTkButton(tlacidla, text=tr("dev.reset"), width=110, height=32,
                          corner_radius=ui_kit.RADIUS_CONTROL,
                          fg_color=pal["surface_alt"], hover_color=pal["border"],
                          text_color=pal["text"],
                          command=self.reset).pack(side="left", padx=(0, 8))
        ctk.CTkButton(tlacidla, text=tr("dev.fire"), width=140, height=32,
                      corner_radius=ui_kit.RADIUS_CONTROL, fg_color=pal["surface_alt"],
                      hover_color=pal["border"], text_color=pal["text"],
                      command=self.fire).pack(side="left")

        # Surovy vypis poslednych okien - to jedine, co o merani povie pravdu.
        ctk.CTkLabel(body, text=tr("dev.windows"), font=ui_kit.ui(9, "bold"),
                     text_color=pal["text_faint"], anchor="w").pack(
            fill="x", pady=(18, 4))
        self.vypis = ctk.CTkTextbox(body, height=150, fg_color=pal["entry_bg"],
                                    border_width=1, border_color=pal["line_soft"],
                                    text_color=pal["text_dim"], font=ui_kit.mono(10))
        self.vypis.pack(fill="both", expand=True)
        self._nacitaj_okna()

        self.top.protocol("WM_DELETE_WINDOW", self.close)

    def _nacitaj_okna(self):
        try:
            import measure
            okna = measure.load_windows(self.app.hr_windows_path)[-12:]
        except Exception as exc:
            okna = []
            self.vypis.insert("end", f"{exc}\n")
        if not okna:
            self.vypis.insert("end", tr("dev.windows_empty"))
            return
        for w in okna:
            self.vypis.insert("end", (
                f"{w.get('arm', '?'):6} {w.get('delivery', '?'):8} "
                f"pre {w.get('pre_bpm')} -> post {w.get('post_bpm')}  "
                f"{'OK' if w.get('valid') else ','.join(w.get('reasons') or [])}\n"))

    def confirm(self):
        nove = {}
        for kluc, var in self.entries.items():
            try:
                nove[kluc] = float(str(var.get()).replace(",", "."))
            except ValueError:
                messagebox.showerror(tr("dev.title"), tr("dev.bad_number"))
                return
        try:
            podiel = float(str(self.silent_var.get()).replace(",", "."))
        except ValueError:
            messagebox.showerror(tr("dev.title"), tr("dev.bad_number"))
            return
        self.app.apply_dev_params(nove, max(0.0, min(1.0, podiel)))
        self.close()

    def reset(self):
        import trigger
        for kluc, hodnota in trigger.default_params().items():
            if kluc in self.entries:
                self.entries[kluc].set(f"{hodnota:g}")

    def fire(self):
        self.app.dev_force_cue()

    def close(self):
        self.top.destroy()


class SessionEndDialog:
    """Koniec relacie: co sa dialo, nie ako sa hrac cital.

    Nie je to dotaznik na pocity. Je to CISTENIE DAT. Rozpravanie je
    najhorsi konfunder v tomto merani: ked hovoris, meni sa dych a tep ide
    hore, takze hlaska, ktora do toho zaznie, vyzera neucinne - hoci s tym
    nema nic spolocne.

    "Preskocit" je rovnako velke tlacidlo ako "Ulozit" a je to zamerne.
    Keby bolo mensie alebo len odkaz, raz sa odklikne naslepo - a nahodne
    odkliknuty kontext su HORSIE data nez ziadny kontext.
    """

    def __init__(self, app, summary, cues=0, silent=0):
        self.app = app
        self.summary = summary
        self.vybrane = set()
        self.chips = {}
        self.activity = None          # 'play' / 'work' / None (nevyjadril sa)
        self._activity_btns = {}
        # Svet relacie (B3-worlds): ten, v ktorom ZACALA (`world` zo
        # `_close_hr_session`). Riadok hral/pracoval ho len ZVYRAZNI -
        # `self.activity` ostava None, kym hrac naozaj neklikne, aby sa
        # "len som klikol Ulozit" nezapisalo ako jeho odpoved.
        self._svet = hr_stats.session_world(summary)
        self.note_box = None          # volna poznamka (CTkTextbox)
        # Subjektivna vrstva (vyskum 2026-09-22) - to, co TEP NEVIDI.
        self.sleep = None             # 'rested'/'mid'/'broken'
        self.felt_load = None         # 0-10 (vnimana zataz), None kym sa nedotkne
        self.valence = None           # -2..+2 (zle..dobre)
        self._body_sel = set()        # telo pocas spicky (viacvyber)
        self.cue_verdict = None       # landed/unneeded/disruptive/agitated/missed
        self._cue_fired = bool(cues)
        self._sleep_btns = {}
        self._val_btns = {}
        self._body_btns = {}
        self._cue_btns = {}
        pal = app.pal

        minuty = int((summary.get("duration_s") or 0) // 60)

        self.top = ctk.CTkToplevel(app.root)
        # S CASOM, nie s prazdnou medzerou. Bez neho bolo v titulku okna aj
        # v liste uloh doslova "Hral si ." - veta, ktorej chyba to jedine
        # cislo, kvoli ktoremu tam je.
        # Pracovna relacia nema v titulku "Hral si".
        titulok = tr("session.end.title_work" if self._svet == "work"
                     else "session.end.title", time=self._cas(minuty))
        self.top.title(titulok)
        self.top.configure(fg_color=pal["bg"])
        self.top.resizable(False, False)
        self.top.transient(app.root)
        self.top.grab_set()

        chrome = ui_kit.DialogChrome(self.top, pal, titulok, on_close=self.close)
        # Podval s tlacidlami je PRIPNUTY dole (vzdy viditelny), obsah nad nim
        # SCROLLUJE. Dotaznik narastol o subjektivnu vrstvu a na 1366x768 by sa
        # inak k Ulozit/Preskocit nedalo dostat (nadvazuje na B33).
        footer = ctk.CTkFrame(chrome.body, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=22, pady=(6, 16))
        self._footer = footer
        body = ctk.CTkScrollableFrame(
            chrome.body, fg_color="transparent", height=540,
            scrollbar_button_color=pal["surface_alt"],
            scrollbar_button_hover_color=pal["accent"])
        body.pack(fill="both", expand=True, padx=(22, 10), pady=(18, 4))

        # PROMOCIA (easter egg): raz, ked hrac dosiahol "plny Zanshin".
        # `_maybe_graduate` oznaci summary; kruh sa uz uzavrel do zlateho
        # mesiaca, tu pribudne mysticka sprava (plt cez rieku).
        if summary.get("zen_graduation"):
            zen = ctk.CTkFrame(body, fg_color=pal["surface"],
                               corner_radius=ui_kit.RADIUS_CONTROL,
                               border_width=1, border_color=pal["accent"])
            zen.pack(fill="x", pady=(0, 14))
            zin = ctk.CTkFrame(zen, fg_color="transparent")
            zin.pack(fill="x", padx=16, pady=14)
            ctk.CTkLabel(zin, text="残  " + tr("session.zanshin.title"),
                         font=ui_kit.ui(16, "bold"), text_color=pal["accent"],
                         anchor="w").pack(fill="x")
            ctk.CTkLabel(zin, text=tr("session.zanshin.body"),
                         font=ui_kit.ui(12), text_color=pal["text"], anchor="w",
                         justify="left", wraplength=420).pack(fill="x", pady=(6, 0))

        # V praci ide kazda hlaska len obrazom (B3-worlds) - veta o "naschval
        # som mlcala" by tam tvrdila rozdiel, ktory nebol.
        if cues and self._svet == "work":
            podnadpis = tr("session.end.cues_work", n=cues)
        elif cues and summary.get("cue_rung") == rebrik.OBRAZ:
            # To iste v hre na stupni "obraz" (rebrik hlasky, 0.2).
            podnadpis = tr("session.end.cues_visual", n=cues)
        elif cues:
            podnadpis = tr("session.end.cues", n=cues, silent=silent)
        else:
            podnadpis = tr("session.end.cues_none")
        ctk.CTkLabel(body, text=podnadpis, font=ui_kit.ui(13),
                     text_color=pal["text"], anchor="w", justify="left",
                     wraplength=420).pack(fill="x")

        # KED SA NEOZVALA, POVEDZ PRECO.
        # Samotne "neozvala som sa" necha hraca hadat medzi tromi velmi
        # roznymi vecami: bol pokojny, appka ma pritvrde pravidlo, alebo mu
        # vypadavali hodinky. Kazda z nich ma ine riesenie, tak sa rozlisia.
        # Cisla dodava `CueTrigger` cez suhrn relacie (app.py,
        # `_close_hr_session`); ked tam nie su, riadok sa proste nezobrazi.
        preco = self._preco_ticho(summary) if not cues else ""
        ctk.CTkLabel(body, text=preco, font=ui_kit.ui(11),
                     text_color=pal["text_faint"], anchor="w", justify="left",
                     wraplength=420).pack(fill="x", pady=(3, 10))

        # AKO TO SLO - krivka celeho vecera priamo nad otazkami.
        #
        # Dotaznik sa pyta, co sa dialo. Bez obrazka si to hrac musi
        # vybavit z hlavy; s nim vidi, kde tep vyskocil a kedy sa appka
        # ozvala, a odpoveda na to, co ma pred ocami. Je to ta ista
        # `SessionTrace`, ktora je na Dnes aj v Historii - ziadny novy graf.
        krivka = summary.get("curve") or []
        if len(krivka) >= 10:
            stopa = ui_kit.SessionTrace(body, pal, height=84)
            stopa.pack(fill="x", pady=(0, 4))
            stopa.set_trace(
                krivka,
                baseline=summary.get("baseline_bpm"),
                threshold=summary.get("critical_bpm"),
                duration_s=summary.get("duration_s") or 0.0,
                triggers=summary.get("trigger_offsets_s") or (),
                activity=summary.get("activity_curve") or ())
            ctk.CTkLabel(body, text=tr("session.end.trace_hint"),
                         font=ui_kit.ui(10), text_color=pal["text_faint"],
                         anchor="w", justify="left", wraplength=420).pack(
                fill="x", pady=(0, 14))

        # -- AKO SA TO CITILO (subjektivne) - to, co TEP NEVIDI --------------
        # Aktivacia (tep) a valencia (dobre/zle) su dve NEZAVISLE osi; hlavny
        # nalez je ROZCHOD merane x citene (tep moze byt plochy, a clovek sa
        # pritom citi zle). Preto ordinalne skaly s pevnymi id, nie volny text.
        ctk.CTkLabel(body, text=tr("session.felt.header").upper(),
                     font=ui_kit.ui(9, "bold"), text_color=pal["text_faint"],
                     anchor="w").pack(fill="x", pady=(0, 8))

        # Vnimana zataz 0-10 (posuvnik). None kym sa nedotkne (0 != nevyjadril sa).
        load_row = ctk.CTkFrame(body, fg_color="transparent")
        load_row.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(load_row, text=tr("session.felt.load"), font=ui_kit.ui(12),
                     text_color=pal["text_dim"]).pack(side="left")
        self._load_val = ctk.CTkLabel(load_row, text="—", width=28,
                                      font=ui_kit.mono(12), text_color=pal["accent"])
        self._load_val.pack(side="right")
        sl = ui_kit.block_slider_wheel(ctk.CTkSlider(
            body, from_=0, to=10, number_of_steps=10,
            progress_color=pal["accent"], button_color=pal["accent"],
            fg_color=pal["switch_off"], button_hover_color=pal["accent_hover"],
            command=self._on_load))
        sl.set(0)
        sl.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(body, text=tr("session.felt.load_hint"), font=ui_kit.ui(9),
                     text_color=pal["text_faint"], anchor="w").pack(fill="x", pady=(0, 10))

        # Valencia (5 stupnov, jednovyber).
        ctk.CTkLabel(body, text=tr("session.felt.valence"), font=ui_kit.ui(12),
                     text_color=pal["text_dim"], anchor="w").pack(fill="x", pady=(0, 6))
        val_row = ctk.CTkFrame(body, fg_color="transparent")
        val_row.pack(fill="x", pady=(0, 10))
        for _c in range(5):
            val_row.grid_columnconfigure(_c, weight=1, uniform="val")
        for i, v in enumerate((-2, -1, 0, 1, 2)):
            btn = ctk.CTkButton(
                val_row, text=tr(f"session.felt.valence.{v}"), height=30, width=40,
                corner_radius=ui_kit.RADIUS_CONTROL, border_width=1,
                fg_color="transparent", border_color=pal["card_border"],
                hover_color=pal["surface_alt"], text_color=pal["text_dim"],
                font=ui_kit.ui(11),
                command=lambda x=v: self._pick_one("valence", x, self._val_btns))
            btn.grid(row=0, column=i, padx=(0, 4), sticky="ew")
            self._val_btns[v] = btn

        # Telo pocas spicky (viacvyber, ZAZITKOVE dlazdice - nie symptomovy skrining).
        ctk.CTkLabel(body, text=tr("session.felt.body_q"), font=ui_kit.ui(12),
                     text_color=pal["text_dim"], anchor="w").pack(fill="x", pady=(0, 6))
        body_row = ctk.CTkFrame(body, fg_color="transparent")
        body_row.pack(fill="x", pady=(0, 10))
        for i, bid in enumerate(hr_stats.BODY_PEAK_IDS):
            btn = ctk.CTkButton(
                body_row, text=tr(f"session.felt.body.{bid}"), height=30,
                corner_radius=ui_kit.RADIUS_CONTROL, border_width=1,
                fg_color="transparent", border_color=pal["card_border"],
                hover_color=pal["surface_alt"], text_color=pal["text_dim"],
                font=ui_kit.ui(12), command=lambda b=bid: self._toggle_body(b))
            btn.grid(row=i // 3, column=i % 3, padx=(0, 6), pady=(0, 4), sticky="w")
            self._body_btns[bid] = btn

        # Verdikt o hlaske - otazka podla toho, ci cue zaznel. "Rozhodila ma"
        # (0.2) je ina vec nez "rusila": vzrusenie, nie pozornost. Obe
        # stisia rebrik hlasky o stupen (`rebrik.py`).
        if self._cue_fired:
            cue_q, cue_opts = tr("session.felt.cue_q_fired"), (
                "landed", "unneeded", "disruptive", "agitated")
        else:
            cue_q, cue_opts = tr("session.felt.cue_q_silent"), ("missed", "unneeded")
        ctk.CTkLabel(body, text=cue_q, font=ui_kit.ui(12), text_color=pal["text_dim"],
                     anchor="w", justify="left", wraplength=420).pack(fill="x", pady=(0, 6))
        cue_row = ctk.CTkFrame(body, fg_color="transparent")
        cue_row.pack(fill="x", pady=(0, 12))
        for v in cue_opts:
            btn = ctk.CTkButton(
                cue_row, text=tr(f"session.felt.cue.{v}"), height=30,
                corner_radius=ui_kit.RADIUS_CONTROL, border_width=1,
                fg_color="transparent", border_color=pal["card_border"],
                hover_color=pal["surface_alt"], text_color=pal["text_dim"],
                font=ui_kit.ui(12),
                command=lambda x=v: self._pick_one("cue_verdict", x, self._cue_btns))
            btn.pack(side="left", padx=(0, 6))
            self._cue_btns[v] = btn

        ctk.CTkFrame(body, fg_color=pal["line_soft"], height=1,
                     corner_radius=0).pack(fill="x", pady=(2, 12))

        # CINNOST: hral alebo pracoval? Jednovyber (nie cipy - su to vylucne
        # moznosti). Navrchu zamerne: je to najzakladnejsi kontext vecera a
        # od neho sa bude dat oddelit "praca" od "hry" - z realnych dat, nie
        # dohadom. Bez kliku = hrac sa nevyjadril (None), rovnako ako pri
        # cipoch; relacia potom patri svetu, v ktorom zacala (`world`).
        ctk.CTkLabel(body, text=tr("session.context.activity_question").upper(),
                     font=ui_kit.ui(9, "bold"), text_color=pal["text_faint"],
                     anchor="w").pack(fill="x", pady=(0, 8))
        akt_row = ctk.CTkFrame(body, fg_color="transparent")
        akt_row.pack(fill="x", pady=(0, 10))
        for kind in hr_stats.ACTIVITY_KINDS:
            btn = ctk.CTkButton(
                akt_row, text=tr(f"session.context.activity.{kind}"), height=30,
                corner_radius=ui_kit.RADIUS_CONTROL, border_width=1,
                fg_color="transparent", border_color=pal["card_border"],
                hover_color=pal["surface_alt"], text_color=pal["text_dim"],
                font=ui_kit.ui(12), command=lambda k=kind: self._set_activity(k))
            btn.pack(side="left", padx=(0, 6))
            self._activity_btns[kind] = btn
        # Svet, v ktorom relacia zacala, je hned vidno - kto zabudol prepnut,
        # opravi to jednym klikom. Ulozi sa ale az ten klik.
        self._paint_activity(self._svet)

        # DVA RADY, nie jeden. Prvy je "co sa dialo pocas vecera", druhy
        # "s cim si do neho sadol" - su to rozne veci a posuvaju rozne
        # cisla. Deviatim cipom v jednom rade by sa navyse dialog rozsypal:
        # `pack(side="left")` nezalamuje a posledne by vypadli von.
        for nadpis, skupina in (("session.context.question", hr_stats.CONTEXT_DIANIE),
                                ("session.context.body_question", hr_stats.CONTEXT_TELO)):
            ctk.CTkLabel(body, text=tr(nadpis).upper(),
                         font=ui_kit.ui(9, "bold"), text_color=pal["text_faint"],
                         anchor="w").pack(fill="x", pady=(0, 8))
            chips = ctk.CTkFrame(body, fg_color="transparent")
            chips.pack(fill="x", pady=(0, 10))
            # GRID, nie pack(side="left"): rad čipov sa nezalamuje, a šesť
            # čipov vedľa seba nafúklo dialóg na 1416 px - na 1366×768 sa
            # potom nedalo dostať k Uložiť/Preskočiť (B33). Tri stĺpce ho
            # držia v rozumnej šírke a čipy sa zalomia na viac riadkov.
            for i, cid in enumerate(skupina):
                btn = ctk.CTkButton(
                    chips, text=tr(f"session.context.{cid}"), height=30,
                    corner_radius=ui_kit.RADIUS_CONTROL, border_width=1,
                    fg_color="transparent", border_color=pal["card_border"],
                    hover_color=pal["surface_alt"], text_color=pal["text_dim"],
                    font=ui_kit.ui(12),
                    command=lambda c=cid: self._prepni(c))
                btn.grid(row=i // 3, column=i % 3, padx=(0, 6), pady=(0, 4),
                         sticky="w")
                self.chips[cid] = btn

        # SPANOK minulu noc (nahradza binarne 'unavený'): 3 urovne, jednovyber.
        # Nevyspatie dvíha osobnu zakladnu na cely den - vysvetľuje, preco ta
        # ista hra raz "nič" a inokedy "zle".
        ctk.CTkLabel(body, text=tr("session.sleep.q").upper(), font=ui_kit.ui(9, "bold"),
                     text_color=pal["text_faint"], anchor="w").pack(fill="x", pady=(2, 8))
        sleep_row = ctk.CTkFrame(body, fg_color="transparent")
        sleep_row.pack(fill="x", pady=(0, 10))
        for lvl in hr_stats.SLEEP_LEVELS:
            btn = ctk.CTkButton(
                sleep_row, text=tr(f"session.sleep.{lvl}"), height=30,
                corner_radius=ui_kit.RADIUS_CONTROL, border_width=1,
                fg_color="transparent", border_color=pal["card_border"],
                hover_color=pal["surface_alt"], text_color=pal["text_dim"],
                font=ui_kit.ui(12),
                command=lambda l=lvl: self._pick_one("sleep", l, self._sleep_btns))
            btn.pack(side="left", padx=(0, 6))
            self._sleep_btns[lvl] = btn

        ctk.CTkLabel(body, text=tr("session.context.why"), font=ui_kit.ui(11),
                     text_color=pal["text_faint"], anchor="w", justify="left",
                     wraplength=420).pack(fill="x", pady=(14, 12))

        # VLASTNA POZNAMKA: volny text k veceru (co cipy nezachytia - nova hra,
        # zle spanok, hadka, cokolvek). Appka ju len drzi a ukaze, neinterpretuje.
        ctk.CTkLabel(body, text=tr("session.context.note_label").upper(),
                     font=ui_kit.ui(9, "bold"), text_color=pal["text_faint"],
                     anchor="w").pack(fill="x", pady=(0, 6))
        self.note_box = ctk.CTkTextbox(
            body, height=58, font=ui_kit.ui(12), fg_color=pal["surface_alt"],
            text_color=pal["text"], border_width=1, border_color=pal["card_border"],
            corner_radius=ui_kit.RADIUS_CONTROL, wrap="word")
        self.note_box.pack(fill="x", pady=(0, 18))

        tlacidla = ctk.CTkFrame(self._footer, fg_color="transparent")
        tlacidla.pack(fill="x")
        # Rovnaka sirka oboch: preskocenie musi byt rovnako lahke ako ulozenie.
        ctk.CTkButton(tlacidla, text=tr("common.save"), width=132, height=34,
                      corner_radius=ui_kit.RADIUS_CONTROL, fg_color=pal["accent"],
                      hover_color=pal["accent_hover"], text_color=pal["bg"],
                      command=self.confirm).pack(side="left")
        ctk.CTkButton(tlacidla, text=tr("session.end.skip"), width=132, height=34,
                      corner_radius=ui_kit.RADIUS_CONTROL, fg_color=pal["surface_alt"],
                      hover_color=pal["border"], text_color=pal["text"],
                      command=self.close).pack(side="left", padx=(8, 0))

        self.top.protocol("WM_DELETE_WINDOW", self.close)

        # PEVNA VELKOST okna. Bez nej sa pri resizable(False) toplevel roztiahne
        # na celu vysku obsahu (aj pod spodok obrazovky, tlacidla mimo) a suzi
        # sa na sirku scroll-kanvasu (~pravy stlpec cipov orezany). S pevnou
        # geometriou telo scrolluje vnutri a footer ostava pripnuty a viditelny.
        # Rozmery su LOGICKE - CTk ich prenasobi mierkou DPI.
        self.top.geometry("660x680")
        try:
            self.top.update_idletasks()
            sirka, vyska = self.top.winfo_width(), self.top.winfo_height()
            sw, sh = self.top.winfo_screenwidth(), self.top.winfo_screenheight()
            x, y = max(0, (sw - sirka) // 2), max(0, (sh - vyska) // 3)
            self.top.geometry(f"+{x}+{y}")
        except Exception:
            pass

    @staticmethod
    def _preco_ticho(summary):
        """Preco za celu relaciu nezaznela ani jedna hlaska.

        Poradie podmienok NIE JE lubovolne: vypadky tepu sa pytaju ako prve,
        lebo pri nich su ostatne cisla nedoveryhodne - najdlhsi usek moze
        vyzerat kratko len preto, ze ho rozsekali diery v datach.

        Potom BRANA (0.2): ani jedna pauza vo vstupe za dlhu relaciu je
        podozrenie na vstup, ktory nikdy neutichne (gyro, packa bez mrtvej
        zony) - hracovi to treba povedat, nie ho z toho vinit. A ked sa
        appka sama rozhodla mlcat (zataz este stupala alebo bol tep v
        kritickom pasme), nesmie to zniet ako "zataz nebola dost dlho hore".

        Uplne na zaciatku PAUZA REBRIKA (0.2): appka mala hlasky vypnute,
        takze kazda ina veta by vysvetlovala ticho, ktore si vybrala sama.
        """
        if summary.get("cue_rung") == rebrik.PAUZA:
            return tr("session.end.none_paused")
        behov = summary.get("above_runs")
        if behov is None:
            return ""                      # starsia relacia, cisla nemá
        vypadkov = summary.get("runs_cancelled_gap") or 0
        if vypadkov >= 2 and vypadkov >= (summary.get("runs_cancelled_dip") or 0):
            return tr("session.end.none_dropouts", n=vypadkov)
        # "TERAZ NIE" POCAS RELACIE (od 24. 9. ju nezatvara). Automat vtedy
        # spal, takze pocitadla nizsie ten cas nevidia: "zataz sa ani raz
        # nedostala nad hranicu" by mohlo tvrdit ticho, ktore si hrac vybral
        # sam. Vypadky vyssie su pravda aj tak (mimo stisenia).
        try:
            stisene = float(summary.get("snoozed_s") or 0)
        except (TypeError, ValueError):
            stisene = 0.0
        if stisene > 0:
            return tr("session.end.none_snoozed",
                      min=max(1, int(round(stisene / 60.0))))
        pauz = summary.get("pause_episodes")
        try:
            trvanie = float(summary.get("duration_s") or 0)
        except (TypeError, ValueError):
            trvanie = 0.0
        # `is not None`: stara relacia pocet pauz nema a nula by klamala.
        if pauz is not None and pauz == 0 and trvanie >= 300:
            return tr("session.end.none_nopause")
        zadrzane = summary.get("cues_withheld")
        try:
            branou = (sum(float(zadrzane.get(d) or 0)
                          for d in (trigger.A_BEZ_PAUZY,
                                    trigger.A_NEVHODNA_CHVILA))
                      if isinstance(zadrzane, dict) else 0)
        except (TypeError, ValueError):
            branou = 0
        if branou > 0:
            # Len brana (telo), nie `nedalo_sa` (odstup, snooze, chodza) -
            # veta hovori o tepe a pri tom by nebola pravdiva.
            return tr("session.end.none_withheld")
        if not behov:
            return tr("session.end.none_never")
        return tr("session.end.none_short",
                  najdlhsie=int(summary.get("longest_above_s") or 0),
                  treba=int(summary.get("stress_hold_s") or 0))

    @staticmethod
    def _cas(minuty):
        """Bez `@staticmethod` posielal `self._cas(minuty)` dva argumenty a
        cely dotaznik padol na TypeError uz pri prvom riadku. Bol to DRUHY
        dovod, preco sa kontext relacie nikdy nepodarilo vyplnit - prvym
        bolo, ze sa dialog pri zatvarani appky zahodil skor, nez sa vykreslil."""
        if minuty < 60:
            return tr("history.minutes", m=minuty)
        return f"{minuty // 60}:{minuty % 60:02d}"

    def _set_activity(self, kind):
        """Jednovyber hral/pracoval. Klik je ODPOVED hraca - az ten sa ulozi
        do `activity`, aj ked klikne na uz zvyrazneny svet (potvrdenie).

        Druhy klik uz odpoved nerusi: riadok ukazuje svet relacie, ktory by
        po zruseni ostal aj tak zvyrazneny, takze "zrusenie" by nebolo
        vidno. (Do B3-worlds tu druhy klik vracal "nevyjadril sa".)"""
        self.activity = kind
        self._paint_activity(kind)

    def _paint_activity(self, zvyrazneny):
        """Prefarbi tlacidla hral/pracoval - zvyrazni len `zvyrazneny`."""
        pal = self.app.pal
        for k, btn in self._activity_btns.items():
            if k == zvyrazneny:
                btn.configure(fg_color=pal["accent2"], border_color=pal["accent"],
                              text_color=pal["accent"])
            else:
                btn.configure(fg_color="transparent", border_color=pal["card_border"],
                              text_color=pal["text_dim"])

    def _prepni(self, cid):
        pal = self.app.pal
        btn = self.chips[cid]
        if cid in self.vybrane:
            self.vybrane.discard(cid)
            btn.configure(fg_color="transparent", border_color=pal["card_border"],
                          text_color=pal["text_dim"])
        else:
            self.vybrane.add(cid)
            btn.configure(fg_color=pal["accent2"], border_color=pal["accent"],
                          text_color=pal["accent"])

    def _on_load(self, v):
        """Posuvnik vnimanej zataze. Prvy dotyk = uz vyjadril sa (0 by inak
        nebolo odlisitelne od 'nevyjadril sa')."""
        self.felt_load = int(round(float(v)))
        try:
            self._load_val.configure(text=str(self.felt_load))
        except Exception:
            pass

    def _pick_one(self, group, value, btns):
        """Jednovyber (valencia/spanok/verdikt): druhy klik na to iste zrusi
        (spat na None). `group` je nazov atributu, `btns` slovnik tlacidiel."""
        pal = self.app.pal
        nova = None if getattr(self, group) == value else value
        setattr(self, group, nova)
        for v, btn in btns.items():
            if v == nova:
                btn.configure(fg_color=pal["accent2"], border_color=pal["accent"],
                              text_color=pal["accent"])
            else:
                btn.configure(fg_color="transparent", border_color=pal["card_border"],
                              text_color=pal["text_dim"])

    def _toggle_body(self, bid):
        """Viacvyber dlazdic 'telo pocas spicky'."""
        pal = self.app.pal
        btn = self._body_btns[bid]
        if bid in self._body_sel:
            self._body_sel.discard(bid)
            btn.configure(fg_color="transparent", border_color=pal["card_border"],
                          text_color=pal["text_dim"])
        else:
            self._body_sel.add(bid)
            btn.configure(fg_color=pal["accent2"], border_color=pal["accent"],
                          text_color=pal["accent"])

    def confirm(self):
        # Prazdny zoznam NIE JE to iste, co preskocenie: [] znamena
        # "nic z toho sa nedialo", None znamena "hrac sa nevyjadril".
        poznamka = ""
        if self.note_box is not None:
            try:
                poznamka = self.note_box.get("1.0", "end")
            except Exception:
                poznamka = ""
        self.app.save_session_context(
            self.summary, sorted(self.vybrane),
            activity=self.activity, note=poznamka,
            sleep=self.sleep, felt_load=self.felt_load, valence=self.valence,
            body_peak=(sorted(self._body_sel) or None), cue_verdict=self.cue_verdict)
        self.close()

    def close(self):
        try:
            self.top.grab_release()
        except Exception:
            pass
        self.top.destroy()


# --------------------------------------------------------------------------
# Import profilu z kodu (Base64/JSON) - na rychle zdielanie napr. na Discorde
# --------------------------------------------------------------------------

class ImportProfileDialog:
    def __init__(self, app):
        self.app = app
        pal = app.pal
        app.set_typing(True)

        self.top = ctk.CTkToplevel(app.root)
        self.top.title(tr("import.title"))
        self.top.configure(fg_color=pal["bg"])
        self.top.resizable(False, False)
        self.top.transient(app.root)
        self.top.grab_set()

        chrome = ui_kit.DialogChrome(
            self.top, pal, tr("import.title"), on_close=self.close)
        body = ctk.CTkFrame(chrome.body, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=16)

        ctk.CTkLabel(body, text=tr("import.hint"), text_color=pal["text"],
                    wraplength=380, justify="left").pack(anchor="w", pady=(0, 8))
        self.code_box = ctk.CTkTextbox(body, width=380, height=110,
                                       fg_color=pal["entry_bg"], text_color=pal["text"])
        self.code_box.pack(fill="x", pady=(0, 10))
        self.code_box.bind("<FocusIn>", lambda _e: app.set_typing(True))
        self.code_box.bind("<FocusOut>", lambda _e: app.set_typing(True))

        self.error_label = ctk.CTkLabel(body, text="", text_color=pal["danger"],
                                        wraplength=380, justify="left")
        self.error_label.pack(anchor="w", pady=(0, 6))

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x")
        ctk.CTkButton(buttons, text=tr("common.cancel"), width=90, fg_color=pal["surface_alt"],
                     hover_color=pal["border"], text_color=pal["text"],
                     command=self.close).pack(side="right")
        ctk.CTkButton(buttons, text=tr("import.confirm"), width=140, fg_color=pal["accent"],
                     hover_color=pal["accent_hover"], text_color=pal["bg"],
                     command=self.confirm).pack(side="right", padx=(0, 8))

        self.top.protocol("WM_DELETE_WINDOW", self.close)

    def confirm(self):
        code = self.code_box.get("1.0", "end").strip()
        if not code:
            self.close()
            return
        try:
            self.app.import_profile_from_code(code)
        except Exception as exc:
            self.error_label.configure(text=tr("import.error", err=exc))
            return
        self.close()

    def close(self):
        self.app.set_typing(False)
        try:
            self.top.grab_release()
        except Exception:
            pass
        self.top.destroy()


class ImportDataDialog:
    """Import dat (Historia -> Tvoje data): Zlucit / Nahradit / Zrusit.

    Predtym to bol systemovy `askyesnocancel` s textom natvrdo
    "Zlucit = Ano / Nahradit = Nie": slova po slovensky v kazdom jazyku a
    tlacidla v jazyku Windowsu, takze v anglickom rozhrani (alebo na
    anglickom Windowse) volby nesedeli s tlacidlami - a nevratne NAHRADIT
    bolo na "Nie". Teraz su volby priamo na tlacidlach (i18n) a NAHRADIT
    ide az na druhy klik, s vetou, co presne sa prepise a ze sa odlozi
    zaloha.

    `on_choice("merge" | "replace")` sa zavola az po potvrdeni a az po
    zatvoreni dialogu; Zrusit, krizik ani Escape nevolaju nic.
    """

    def __init__(self, app, message, on_choice):
        self.app = app
        self.pal = pal = app.pal
        self.message = message
        self.on_choice = on_choice

        self.top = ctk.CTkToplevel(app.root)
        self.top.title(tr("data.import.title"))
        self.top.configure(fg_color=pal["bg"])
        self.top.resizable(False, False)
        self.top.transient(app.root)
        self.top.grab_set()

        chrome = ui_kit.DialogChrome(
            self.top, pal, tr("data.import.title"), on_close=self.close)
        body = ctk.CTkFrame(chrome.body, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=16)

        self.text = ctk.CTkLabel(body, text=message, text_color=pal["text"],
                                 wraplength=440, justify="left", anchor="w")
        self.text.pack(anchor="w", fill="x", pady=(0, 14))
        self.buttons = ctk.CTkFrame(body, fg_color="transparent")
        self.buttons.pack(fill="x")
        self._choose()

        self.top.protocol("WM_DELETE_WINDOW", self.close)

    def _button(self, text, command, primary=False, danger=False, width=120):
        pal = self.pal
        if primary:
            kw = dict(fg_color=pal["accent"], hover_color=pal["accent_hover"],
                      text_color=pal["bg"])
        elif danger:
            kw = dict(fg_color="transparent", border_width=1,
                      border_color=pal["danger"], hover_color=pal["danger"],
                      text_color=pal["text"])
        else:
            kw = dict(fg_color=pal["surface_alt"], hover_color=pal["border"],
                      text_color=pal["text"])
        btn = ctk.CTkButton(self.buttons, text=text, width=width,
                            corner_radius=ui_kit.RADIUS_CONTROL, command=command, **kw)
        btn.pack(side="right", padx=(8, 0))
        return btn

    def _clear(self):
        for w in self.buttons.winfo_children():
            w.destroy()

    def _choose(self):
        """Prvy krok: co je v subore a tri volby. Zlucit je predvolena
        (bezpecna) - Nahradit je obrysove, nie plne tlacidlo."""
        self._clear()
        self.text.configure(text=self.message)
        self._button(tr("common.cancel"), self.close, width=90)
        self._button(tr("data.import.replace"), self._confirm_replace, danger=True)
        self._button(tr("data.import.merge"), lambda: self._done("merge"),
                     primary=True)

    def _confirm_replace(self):
        """Druhy krok pre NAHRADIT - co presne sa prepise a kam ide zaloha."""
        self._clear()
        self.text.configure(text=tr("data.import.replace_confirm"))
        self._button(tr("data.import.back"), self._choose, width=90)
        self._button(tr("data.import.replace_yes"), lambda: self._done("replace"),
                     danger=True)

    def _done(self, volba):
        self.close()
        self.on_choice(volba)

    def close(self):
        try:
            self.top.grab_release()
        except Exception:
            pass
        self.top.destroy()


# --------------------------------------------------------------------------
# Nastavenie in-game vizualnych overlayov - velkost, poloha a test pre
# vsetky 4 sloty naraz, v jednom modalnom okne.
# --------------------------------------------------------------------------

# Rohove predvolby polohy HUD-u (v % sirky/vysky monitora). Stredy su
# zamerne posunute od okrajov - killfeed a chat v strielackach sedia
# tesne pri ramci obrazovky.
HUD_POSITION_PRESETS = [
    (13.0, 8.0), (50.0, 6.0), (87.0, 8.0),
    (13.0, 90.0), (50.0, 93.0), (87.0, 90.0),
]


class OverlaySettingsDialog:
    GRID_PRESETS = [
        (10.0, 10.0), (50.0, 10.0), (90.0, 10.0),
        (10.0, 50.0), (50.0, 50.0), (90.0, 50.0),
        (10.0, 90.0), (50.0, 90.0), (90.0, 90.0),
    ]

    def __init__(self, app):
        self.app = app
        pal = app.pal
        app.set_typing(True)
        self._rows = []

        self.top = ctk.CTkToplevel(app.root)
        self.top.title(tr("overlay.dialog_title"))
        self.top.configure(fg_color=pal["bg"])
        self.top.geometry("520x760")
        self.top.minsize(470, 480)
        self.top.transient(app.root)
        self.top.grab_set()

        chrome = ui_kit.DialogChrome(self.top, pal, tr("overlay.dialog_title"),
                                     on_close=self.close)
        header = ctk.CTkFrame(chrome.body, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 6))
        ctk.CTkLabel(header, text=tr("overlay.dialog_hint"), font=ui_kit.ui(11),
                    text_color=pal["text_dim"], wraplength=430, justify="left").pack(
            anchor="w")

        # POZN: tu sa kreslil vyber obrazovky a nizsie cela karta HUD-u.
        # Boli to DRUHE kopie tych istych nastaveni, ktore su v
        # Nastavenia -> Vseobecne, a rozchadzali sa: prepnutie HUD-u v tomto
        # dialogu prepisalo `hud_config`, ale premennu prepinaca na stranke
        # uz nie - hrac potom videl vypnute na jednom mieste a zapnute na
        # druhom a nemal ako zistit, ktora hodnota plati.
        #
        # Tento dialog je na POLOHU A VELKOST. Co sa zapina a na ktorej
        # obrazovke, je jedno miesto - stranka Vseobecne.

        scroll = ctk.CTkScrollableFrame(
            chrome.body, fg_color="transparent", scrollbar_button_color=pal["surface_alt"],
            scrollbar_button_hover_color=pal["accent"])
        scroll.pack(fill="both", expand=True, padx=14, pady=10)


        for i in range(4):
            self._build_row(scroll, i, pal)

        footer = ctk.CTkFrame(chrome.body, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 16))
        ctk.CTkButton(footer, text=tr("common.close"), width=100,
                     fg_color=pal["accent2"], hover_color=pal["accent2_hover"],
                     text_color=pal["text"], command=self.close).pack(side="right")

        self.top.protocol("WM_DELETE_WINDOW", self.close)





    def _build_row(self, parent, index, pal):
        cfg = self.app.overlay_configs[index]
        card = ctk.CTkFrame(parent, fg_color=pal["surface"], corner_radius=ui_kit.RADIUS_PANEL,
                            border_width=1, border_color=pal["card_border"])
        card.pack(fill="x", pady=7)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)

        head = ctk.CTkFrame(inner, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text=tr(f"overlay.slot.{index}"), font=ui_kit.ui(13, "bold"),
                    text_color=pal["text"]).pack(side="left")
        enabled_var = tk.BooleanVar(value=cfg["enabled"])
        ctk.CTkSwitch(head, text=tr("overlay.enable"), variable=enabled_var,
                     progress_color=pal["accent"], text_color=pal["text_dim"],
                     command=lambda idx=index, var=enabled_var: self.app.on_overlay_config_change(
                         idx, enabled=var.get())).pack(side="right")

        scale_row = ctk.CTkFrame(inner, fg_color="transparent")
        scale_row.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(scale_row, text=tr("overlay.scale"), text_color=pal["text_dim"],
                    width=90, anchor="w").pack(side="left")
        scale_value_label = ctk.CTkLabel(scale_row, text=f"{cfg['scale']:.2f}x",
                                         text_color=pal["text_faint"], width=50)
        scale_value_label.pack(side="right")
        scale_var = tk.DoubleVar(value=cfg["scale"])

        def on_scale(_v, idx=index, var=scale_var, label=scale_value_label):
            value = round(float(var.get()), 2)
            label.configure(text=f"{value:.2f}x")
            self.app.on_overlay_config_change(idx, scale=value)

        ui_kit.block_slider_wheel(ctk.CTkSlider(scale_row, from_=0.5, to=2.0, variable=scale_var,
                     number_of_steps=30, progress_color=pal["accent"],
                     button_color=pal["accent"], button_hover_color=pal["accent_hover"],
                     command=on_scale)).pack(side="left", fill="x", expand=True, padx=(8, 8))

        if index == 3:
            self._build_breath_seconds_rows(inner, pal)

        ctk.CTkLabel(inner, text=tr("overlay.position"), text_color=pal["text_dim"]).pack(
            anchor="w", pady=(12, 4))

        pos_area = ctk.CTkFrame(inner, fg_color="transparent")
        pos_area.pack(fill="x")

        grid = ctk.CTkFrame(pos_area, fg_color=pal["entry_bg"], corner_radius=8)
        grid.pack(side="left", padx=(0, 14))
        pos_x_var = tk.DoubleVar(value=cfg["pos_x"])
        pos_y_var = tk.DoubleVar(value=cfg["pos_y"])

        for gi, (gx, gy) in enumerate(self.GRID_PRESETS):
            r, gc = divmod(gi, 3)
            ctk.CTkButton(
                grid, text="", width=26, height=22, corner_radius=ui_kit.RADIUS_CONTROL,
                fg_color=pal["surface_alt"], hover_color=pal["accent2"],
                command=lambda x=gx, y=gy, idx=index, xv=pos_x_var, yv=pos_y_var:
                    self._apply_preset(idx, x, y, xv, yv)).grid(
                row=r, column=gc, padx=3, pady=3)

        sliders = ctk.CTkFrame(pos_area, fg_color="transparent")
        sliders.pack(side="left", fill="x", expand=True)

        x_label = ctk.CTkLabel(sliders, text=f"X {cfg['pos_x']:.0f}%",
                               text_color=pal["text_faint"], anchor="w")
        x_label.pack(fill="x")

        def on_pos_x(_v, idx=index, var=pos_x_var, other=pos_y_var, label=x_label):
            value = round(float(var.get()), 1)
            label.configure(text=f"X {value:.0f}%")
            self.app.on_overlay_config_change(idx, pos=(value, other.get()))

        ui_kit.block_slider_wheel(ctk.CTkSlider(sliders, from_=0, to=100, variable=pos_x_var,
                     number_of_steps=100, progress_color=pal["accent2"],
                     button_color=pal["accent2"], button_hover_color=pal["accent2_hover"],
                     command=on_pos_x)).pack(fill="x", pady=(2, 8))

        y_label = ctk.CTkLabel(sliders, text=f"Y {cfg['pos_y']:.0f}%",
                               text_color=pal["text_faint"], anchor="w")
        y_label.pack(fill="x")

        def on_pos_y(_v, idx=index, var=pos_y_var, other=pos_x_var, label=y_label):
            value = round(float(var.get()), 1)
            label.configure(text=f"Y {value:.0f}%")
            self.app.on_overlay_config_change(idx, pos=(other.get(), value))

        ui_kit.block_slider_wheel(ctk.CTkSlider(sliders, from_=0, to=100, variable=pos_y_var,
                     number_of_steps=100, progress_color=pal["accent2"],
                     button_color=pal["accent2"], button_hover_color=pal["accent2_hover"],
                     command=on_pos_y)).pack(fill="x", pady=(2, 0))

        self._rows.append({"x_label": x_label, "y_label": y_label})

        ctk.CTkButton(inner, text=tr("overlay.test"), height=32,
                     fg_color="transparent", border_width=1, border_color=pal["border"],
                     hover_color=pal["surface_alt"], text_color=pal["text"],
                     command=lambda idx=index: self.app.test_overlay(idx)).pack(
            fill="x", pady=(12, 0))

    def _build_breath_seconds_rows(self, parent, pal):
        """Dlzka nadychu/vydychu (v sekundach) - len pri slote Dych (index 3),
        vedla existujuceho posuvnika Velkost."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(row, text=tr("overlay.breath_seconds"), text_color=pal["text_dim"],
                    anchor="w").pack(anchor="w")

        self._breath_seconds(row, pal, tr("overlay.breath_inhale"),
                             self.app.breath_inhale_s,
                             lambda v: self.app.on_breath_seconds_change(inhale=v))
        self._breath_seconds(row, pal, tr("overlay.breath_exhale"),
                             self.app.breath_exhale_s,
                             lambda v: self.app.on_breath_seconds_change(exhale=v))

    def _breath_seconds(self, parent, pal, label, value, on_change):
        sub = ctk.CTkFrame(parent, fg_color="transparent")
        sub.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(sub, text=label, text_color=pal["text_dim"], width=90,
                    anchor="w").pack(side="left")
        value_label = ctk.CTkLabel(sub, text=f"{value:.0f} s",
                                   text_color=pal["text_faint"], width=40)
        value_label.pack(side="right")
        var = tk.DoubleVar(value=value)

        def handler(_v, var=var, label=value_label, cb=on_change):
            current = round(float(var.get()))
            label.configure(text=f"{current:.0f} s")
            cb(current)

        steps = int(BREATH_SECONDS_MAX - BREATH_SECONDS_MIN)
        ui_kit.block_slider_wheel(ctk.CTkSlider(
            sub, from_=BREATH_SECONDS_MIN, to=BREATH_SECONDS_MAX, variable=var,
            number_of_steps=steps, progress_color=pal["accent"],
            button_color=pal["accent"], button_hover_color=pal["accent_hover"],
            command=handler)).pack(side="left", fill="x", expand=True, padx=(8, 8))

    def _apply_preset(self, index, x, y, pos_x_var, pos_y_var):
        pos_x_var.set(x)
        pos_y_var.set(y)
        row = self._rows[index] if index < len(self._rows) else None
        if row is not None:
            row["x_label"].configure(text=f"X {x:.0f}%")
            row["y_label"].configure(text=f"Y {y:.0f}%")
        self.app.on_overlay_config_change(index, pos=(x, y))

    def close(self):
        # DRAG-TEST SA MUSI UKONCIT SO ZATVORENIM DIALOGU.
        #
        # Test rezim vypina klik-through, cize vizual nad hrou pohlcuje kliky
        # mysou - a sam od seba nikdy neskonci. Kto klikol Test, zatvoril
        # dialog a spustil hru, mal uprostred obrazovky nekliknutelnu plochu
        # a ziadny sposob, ako zistit preco. Zatvorenie dialogu je posledny
        # moment, kedy to appka vie chytit.
        try:
            if self.app.overlay_manager.stop_all_tests():
                self.app.log(tr("log.overlay_test_ukonceny"))
                self.app._refresh_test_button()
        except Exception:
            pass
        self.app.set_typing(False)
        try:
            self.top.grab_release()
        except Exception:
            pass
        self.top.destroy()


def watch_app_qr(parent, pal, **pack_kw):
    """QR na appku do telefonu - navonok len znacka, kod az na klik.

    Je to ta ista vec na dvoch miestach (krokovy navod na parovanie aj
    karta senzora v Nastaveniach), takze zije tu a nie dvakrat. Ked
    obrazok chyba (napr. rozbity build), nevrati sa nic - chybajuci QR
    nesmie zhodit dialog ani stranku.
    """
    base = images_dir()
    codes = [(os.path.join(base, "qr_watch_play.png"), tr("hr.qr_android")),
             (os.path.join(base, "qr_watch_appstore.png"), tr("hr.qr_ios"))]
    widget = ui_kit.QrReveal(parent, pal, codes, tr("hr.qr_show"),
                             tr("hr.qr_hide"))
    widget.pack(anchor="w", **(pack_kw or {"pady": (8, 0)}))
    return widget


class WatchPairingDialog:
    """Krokovy navod, ako dostat tep z hodiniek do appky.

    Preco to potrebuje vlastny dialog: appka NEprijima tep priamo. Predstiera
    OBS (obs-websocket v5) a spolieha sa na to, ze na telefone bezi appka,
    ktora tep do OBS posiela - najbeznejsia je "HeartRateOnStream for OBS".
    Hrac teda musi v telefone nastavit OBS spojenie na IP tohto pocitaca, co
    je bez navodu takmer nemozne uhadnut.

    Dialog ukazuje aj REALNU IP a port tohto PC (nie zastupne priklady),
    takze si ich hrac len prepise do telefonu. IP sa zisti best-effort - ak
    sa neda, ukaze sa rada, ako ju najst rucne.

    SKRYTA IP (0.2): adresa je zamaskovana (`netinfo.mask_ip`), kym hrac
    neklikne "Ukazat IP" - okno parovania byva na streame aj na screenshote
    pre testera. Tlacidlo prepina `app.show_ip`, ktore plati pre celu appku
    (aj pole IP v Nastaveniach a dennik) a len do restartu.
    """

    def __init__(self, app):
        self.app = app
        pal = app.pal
        app.set_typing(True)

        self.top = ctk.CTkToplevel(app.root)
        self.top.title(tr("hr.pair_title"))
        self.top.configure(fg_color=pal["bg"])
        self.top.geometry("560x640")
        self.top.minsize(520, 560)
        self.top.transient(app.root)
        self.top.grab_set()
        self.top.protocol("WM_DELETE_WINDOW", self.close)

        chrome = ui_kit.DialogChrome(self.top, pal, tr("hr.pair_title"),
                                     on_close=self.close)
        root = chrome.body

        header = ctk.CTkFrame(root, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(18, 6))
        ctk.CTkLabel(header, text=tr("hr.pair_intro"), font=ui_kit.ui(12),
                     text_color=pal["text_dim"], wraplength=500, anchor="w",
                     justify="left").pack(fill="x")

        scroll = ctk.CTkScrollableFrame(
            root, fg_color="transparent", scrollbar_button_color=pal["surface_alt"],
            scrollbar_button_hover_color=pal["accent"])
        scroll.pack(fill="both", expand=True, padx=18, pady=12)

        # panel s realnou IP/portom tohto PC
        net = ctk.CTkFrame(scroll, fg_color=pal["surface"], corner_radius=ui_kit.RADIUS_CONTROL,
                           border_width=1, border_color=pal["accent2"])
        net.pack(fill="x", pady=(0, 14))
        net_in = ctk.CTkFrame(net, fg_color="transparent")
        net_in.pack(fill="x", padx=16, pady=14)
        ctk.CTkLabel(net_in, text=tr("hr.pair_this_pc"), font=ui_kit.ui(11),
                     text_color=pal["text_faint"], anchor="w").pack(fill="x")
        candidates = self._local_ips()
        self._candidates = candidates
        ip = candidates[0] if candidates else None
        self._ip = ip
        addr_row = ctk.CTkFrame(net_in, fg_color="transparent")
        addr_row.pack(fill="x", pady=(4, 0))
        self.ip_label = ctk.CTkLabel(addr_row, text=tr("hr.pair_ip_unknown"),
                                     font=ui_kit.mono(20),
                                     text_color=pal["accent_hover"], anchor="w")
        self.ip_label.pack(side="left", fill="x", expand=True)
        self.ip_toggle = None
        self.other_ips_label = None
        self.ip_hidden_label = None
        if not ip:
            ctk.CTkLabel(net_in, text=tr("hr.pair_ip_help"), font=ui_kit.ui(10),
                         text_color=pal["text_faint"], wraplength=480, anchor="w",
                         justify="left").pack(fill="x", pady=(6, 0))
        else:
            self.ip_toggle = ui_kit.chip(addr_row, pal, tr("hr.ip_show"),
                                         self._toggle_ip)
            self.ip_toggle.pack(side="right", padx=(8, 0))
            # veta pod skrytou adresou - ako ju odkryt (len kym je skryta)
            self.ip_hidden_label = ctk.CTkLabel(
                net_in, text=tr("hr.ip_hidden_note"), font=ui_kit.ui(10),
                text_color=pal["text_faint"], wraplength=480, anchor="w",
                justify="left")
            self._ip_hidden_after = addr_row
            # PC s Wi-Fi + Ethernet + VPN ma adries viac a appka nevie, na
            # ktorej su hodinky - ukazeme aj ostatne, nech si hrac vyberie
            if len(candidates) > 1:
                self.other_ips_label = ctk.CTkLabel(
                    net_in, text="", font=ui_kit.ui(10), text_color=pal["text_dim"],
                    wraplength=480, anchor="w", justify="left")
                self.other_ips_label.pack(fill="x", pady=(6, 0))
            ctk.CTkLabel(net_in, text=tr("hr.pair_ip_note"), font=ui_kit.ui(10),
                         text_color=pal["text_faint"], wraplength=480, anchor="w",
                         justify="left").pack(fill="x", pady=(4, 0))
        self._render_ips()

        # kroky; krok 2 je "stiahni si appku do telefonu" - tam patri QR,
        # aby hrac nemusel na telefone nic pisat
        steps = [
            (tr("hr.step1_title"), tr("hr.step1_body"), None),
            (tr("hr.step2_title"), tr("hr.step2_body"), watch_app_qr),
            (tr("hr.step3_title"), tr("hr.step3_body"), None),
            (tr("hr.step4_title"), tr("hr.step4_body"), None),
            (tr("hr.step5_title"), tr("hr.step5_body"), None),
        ]
        for i, (title, body, extra) in enumerate(steps, 1):
            self._step_row(scroll, pal, i, title, body,
                           extra=(lambda col, fn=extra: fn(col, pal)) if extra else None)

        # co ak to nechodi
        trouble = ctk.CTkFrame(scroll, fg_color=pal["surface"], corner_radius=ui_kit.RADIUS_CONTROL,
                               border_width=1, border_color=pal["line_soft"])
        trouble.pack(fill="x", pady=(6, 0))
        stripe = ctk.CTkFrame(trouble, fg_color=pal["warn"], width=3, corner_radius=0)
        stripe.pack(side="left", fill="y")
        tb = ctk.CTkFrame(trouble, fg_color="transparent")
        tb.pack(side="left", fill="x", expand=True, padx=14, pady=13)
        ctk.CTkLabel(tb, text=tr("hr.trouble_title"), font=ui_kit.ui(12, "bold"),
                     text_color=pal["text"], anchor="w").pack(fill="x")
        ctk.CTkLabel(tb, text=tr("hr.trouble_body"), font=ui_kit.ui(11),
                     text_color=pal["text_dim"], wraplength=470, anchor="w",
                     justify="left").pack(fill="x", pady=(5, 0))
        # Ovladac s gyrom / bez mrtvej zony hlasi vstup bez prestania a appka
        # nenajde pauzu - ta ista rada ako riadok na Dnes (`dnes.nonstop_input`).
        ctk.CTkLabel(tb, text=tr("hr.trouble_pad"), font=ui_kit.ui(11),
                     text_color=pal["text_dim"], wraplength=470, anchor="w",
                     justify="left").pack(fill="x", pady=(8, 0))

        footer = ctk.CTkFrame(root, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=(0, 16))
        ctk.CTkButton(footer, text=tr("common.close"), width=110, height=32,
                      corner_radius=ui_kit.RADIUS_CONTROL, fg_color=pal["accent2"],
                      hover_color=pal["accent2_hover"], text_color=pal["text"],
                      command=self.close).pack(side="right")

    def _step_row(self, parent, pal, number, title, body, extra=None):
        """`extra(col)` prida pod text kroku dalsi prvok (napr. QR na appku
        do telefonu) - kroky, ktore ho nemaju, ostavaju cistym textom."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 12))
        badge = ctk.CTkLabel(row, text=str(number), width=26, height=26,
                             corner_radius=13, fg_color=pal["accent2"],
                             text_color=pal["text"], font=ui_kit.mono(12))
        badge.pack(side="left", anchor="n", padx=(0, 12))
        col = ctk.CTkFrame(row, fg_color="transparent")
        col.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(col, text=title, font=ui_kit.ui(13, "bold"),
                     text_color=pal["text"], anchor="w", justify="left").pack(fill="x")
        ctk.CTkLabel(col, text=body, font=ui_kit.ui(11), text_color=pal["text_dim"],
                     wraplength=460, anchor="w", justify="left").pack(fill="x", pady=(2, 0))
        if extra is not None:
            extra(col)

    def _local_ips(self):
        """Vsetky IPv4 adresy tohto PC, preferovana prva (viz netinfo). Nikam
        sa nepripaja - len sa opyta OS. Bez loopbacku a bez 169.254.x.x."""
        try:
            import netinfo
            return netinfo.local_ip_candidates()
        except Exception:
            return []

    def _local_ip(self):
        """Zachovane pre spatnu kompatibilitu - preferovana adresa alebo None."""
        ips = self._local_ips()
        return ips[0] if ips else None

    def _render_ips(self):
        """Prekresli adresy podla `app.show_ip` - skryte, kym ich hrac
        vyslovne neodkryje (texty sklada `netinfo`, nie tento dialog)."""
        show = bool(getattr(self.app, "show_ip", False))
        try:
            if self._ip:
                self.ip_label.configure(text=netinfo.pairing_address(
                    self._ip, self.app.hr_port, show))
            if self.other_ips_label is not None:
                self.other_ips_label.configure(text=tr(
                    "hr.pair_other_ips",
                    ips=netinfo.pairing_other_ips(self._candidates[1:], show)))
            if self.ip_toggle is not None:
                self.ip_toggle.configure(
                    text=tr("hr.ip_hide") if show else tr("hr.ip_show"))
            if self.ip_hidden_label is not None:
                if show:
                    self.ip_hidden_label.pack_forget()
                else:
                    self.ip_hidden_label.pack(fill="x", pady=(6, 0),
                                              after=self._ip_hidden_after)
        except Exception:
            pass            # dialog medzitym zavreli

    def _toggle_ip(self):
        """Ukazat / Skryt IP - plati pre celu appku, len do restartu."""
        nove = not bool(getattr(self.app, "show_ip", False))
        setter = getattr(self.app, "set_show_ip", None)
        if setter is not None:
            setter(nove)
        else:
            self.app.show_ip = nove
        self._render_ips()

    def close(self):
        self.app.set_typing(False)
        try:
            self.top.grab_release()
        except Exception:
            pass
        self.top.destroy()


# --------------------------------------------------------------------------
# Karta slotu v hlavnom okne
# --------------------------------------------------------------------------

class SlotCard:
    CARET_ZAVRETA = "▸"   # >
    CARET_OTVORENA = "▾"  # v

    def __init__(self, app, index, data):
        self.app = app
        self.index = index
        # Styri kategorie (sloty 0-3) su pevne - kategoriu, obrazok v hre aj
        # meranie urcuje pozicia, takze ich odstranenie by posunulo texty pod
        # cudziu kategoriu. Vypinaju sa prepinacom. Zaskrtavatko a ✕ ma len
        # slot navyse z 0.1 (index 4+).
        self.removable = not je_kategoria(index)
        data = normalize_slot(data)

        # POZN: `key_type` a `key_repr` sa tu uz nedrzia. Hlasku nespusta
        # stlacenie, takze karta nemala co s nimi robit - a `display_key()`
        # z nich robila popisok, ktory sa kreslil aj do hry pod ikonku.
        # V ulozenych profiloch kluce ostavaju (settings_model.DEFAULT_SLOT),
        # aby sa stare subory nerozbili.
        self.mode = data["mode"]
        self.audio_path = data["audio_path"]
        self.sfx_key = data["sfx_key"]
        self.voice_edge = data["voice_edge"]
        self.voice_sapi = data["voice_sapi"]
        self.voice_path = data["voice_path"]   # vlastna nahravka hlasu
        self.uid = data["uid"]                 # stabilne meno pre nahravky
        # CASOVANIE JEDNOTLIVEJ HLASKY TU UZ NIE JE.
        #
        # Vlastny cooldown, oneskorenie, "kazde N-te" a rozptyl sa citali
        # jedine vo `fire_slot`, teda pri tlacidle Test a pri kliku v HUD
        # nahlade. Automaticku hlasku spusta `_fire_somatic_cue` cez `_emit`,
        # ktory z karty berie len `mode`, `sfx_path` a `text`. Tie polia teda
        # nastavovali nieco, co sa pri hrani nikdy nepouzilo - a pritom
        # vyzerali ako hlavny ovladac appky.
        #
        # V ulozenych profiloch kluce ostavaju (`settings_model.DEFAULT_SLOT`),
        # aby sa stare subory nerozbili; appka ich uz len necita.
        self.last_triggered = 0.0

        # Plain-python zrkadla hodnot - listener vlakna NIKDY nesiahaju na Tk.
        self.text_value = data["text"]
        self.enabled_value = data["enabled"]

        pal = app.pal
        self.pal = pal

        # --- Pevny raster namiesto auto-sirok -------------------------------
        # Keycap si berie svoj stlpec bez ohladu na to, aky je siroky, takze
        # fraza kazdeho spustaca zacina na tej istej zvislici. Sirka keycapu
        # tak stale nesie typ vstupu (klaves / mys / ovladac), ale uz netlaci
        # text vedla seba - to bola jedina vec, ktora sa na maketе nezhodovala.
        #
        # Tk minsize stlpec NEOREZE, len ho nafukne, ak je obsah sirsi -
        # preto ma kazdy prvok v rastri pevnu `width`.
        self.frame = ctk.CTkFrame(app.slots_container, fg_color=pal["card"],
                                  border_width=1, border_color=pal["line_soft"],
                                  corner_radius=ui_kit.RADIUS_CONTROL)
        self.frame.pack(fill="x", padx=2, pady=5)

        grid = ctk.CTkFrame(self.frame, fg_color="transparent")
        grid.pack(fill="x", padx=16, pady=12)
        # Stlpec 0 mal 138 px pre keycap. Keycap zmizol vo faze 3 (hlasku
        # nespusta klaves) a stlpec s pauzou (54 px) spolu s per-slot
        # casovanim. Uvolnene miesto dostala fraza - jediny rastuci stlpec.
        #
        # Dnes stlpec 0 nesie tri veci v poradi, v akom sa pouzivaju:
        # sipku na rozbalenie, zaskrtavatko na hromadny vyber a piktogram -
        # presne ten, ktory hrac uvidi v hre.
        COLUMNS = ((0, 92, 0), (1, 210, 1), (2, 104, 0),
                   (3, 150, 0), (4, 96, 0), (5, 40, 0))
        for index, minsize, weight in COLUMNS:
            grid.grid_columnconfigure(index, minsize=minsize, weight=weight,
                                      pad=0)

        # 0 - sipka, vyber (na hromadne odstranenie), piktogram
        col0 = ctk.CTkFrame(grid, fg_color="transparent")
        col0.grid(row=0, column=0, sticky="w", padx=(0, 14))

        # Vysvetlivka existuje len pre styri zakladne hlasky - vlastny slot
        # hraca ju nema, a vtedy sa sipka nekresli vobec. Zakazane tlacidlo
        # by slubovalo obsah, ktory neexistuje.
        self.guide_card = guide_panel.card_for_slot(self.index)
        self._detail_built = False
        if self.guide_card is not None:
            self.caret = ctk.CTkButton(
                col0, text=self.CARET_ZAVRETA, width=22, height=22,
                corner_radius=ui_kit.RADIUS_CONTROL, fg_color="transparent",
                hover_color=pal["surface_alt"], text_color=pal["text_dim"],
                font=ui_kit.ui(14), command=self.toggle_detail)
            self.caret.pack(side="left", padx=(0, 4))
        else:
            self.caret = None
            ctk.CTkFrame(col0, fg_color="transparent", width=26,
                         height=22).pack(side="left")

        self.select_var = tk.BooleanVar(value=False)
        self.select_check = None
        if self.removable:
            self.select_check = ctk.CTkCheckBox(
                col0, text="", width=20, checkbox_width=18, checkbox_height=18,
                corner_radius=ui_kit.RADIUS_CONTROL, border_width=2, fg_color=pal["accent"],
                hover_color=pal["surface_alt"], border_color=pal["text_faint"],
                command=self.app._on_slot_selection_change)
            self.select_check.configure(variable=self.select_var)
            self.select_check.pack(side="left", padx=(0, 6))
        if self.guide_card is not None:
            # TEN ISTY stetec ako in-game vizual (`hud_paint.render_slot_icon`),
            # nie ilustracna ikonka: co hrac vidi v zozname, to uvidi aj v hre.
            try:
                obrazok = guide_panel.sketch_or_image(
                    col0, pal, self.guide_card["id"], size=26)
                obrazok.pack(side="left")
                obrazok.bind("<Button-1>", self.toggle_detail)
                obrazok.configure(cursor="hand2")
            except Exception:
                pass
        # FAZA 3: klaves tu uz nie je. Hlasku nespusta stlacenie, ale telo -
        # zataz drziaca nad prahom (`trigger.CueTrigger`). Karta ostava, lebo
        # nesie OBSAH: text hlasky, hlas, zvuk a vizual. To appka potrebuje
        # dalej; zmizla len ta cast, ktora rozhodovala KEDY.
        # Prekreslenie celej stranky je faza 5.

        # 1 - fraza + suhrn casovania pod nou
        text_col = ctk.CTkFrame(grid, fg_color="transparent")
        text_col.grid(row=0, column=1, sticky="ew", padx=(0, 14))
        self.text_var = tk.StringVar(value=self.text_value)
        self.entry = ctk.CTkEntry(text_col, textvariable=self.text_var,
                                  placeholder_text=tr("slot.text_placeholder"),
                                  height=28, corner_radius=ui_kit.RADIUS_CONTROL,
                                  fg_color=pal["entry_bg"], border_width=1,
                                  border_color=pal["line_soft"],
                                  text_color=pal["text"], font=ui_kit.ui(13))
        self.text_var.trace_add("write", lambda *_: self.on_text_change())
        self.entry.bind("<FocusIn>", lambda _e: app.set_typing(True))
        self.entry.bind("<FocusOut>", lambda _e: app.set_typing(False))
        self.entry.pack(fill="x")

        self.summary_label = ctk.CTkLabel(text_col, text=self.summary_text(),
                                          text_color=pal["text_faint"],
                                          font=ui_kit.ui(11), anchor="w")
        # Odkedy riadok nesie uz len prestaveny hlas, je vacsinou prazdny -
        # a prazdny stitok je stale vysoky ako riadok textu. Pakuje sa preto
        # az vtedy, ked ma co povedat.
        self._sync_summary_visibility()

        # 2 - rezim (hlas / zvuk / oboje)
        self.mode_var = tk.StringVar(value=mode_labels()[self.mode])
        self.mode_box = ctk.CTkOptionMenu(
            grid, values=[mode_labels()[m] for m in MODE_ORDER],
            variable=self.mode_var, width=104, height=28, corner_radius=ui_kit.RADIUS_CONTROL,
            fg_color=pal["surface_alt"], button_color=pal["accent2"],
            button_hover_color=pal["accent2_hover"], text_color=pal["text"],
            dropdown_fg_color=pal["surface"], dropdown_text_color=pal["text"],
            font=ui_kit.ui(11), command=self.on_mode_change)
        self.mode_box.grid(row=0, column=2, sticky="w", padx=(0, 14))

        # 3 - zvuk + mikrofon/subor
        self.sfx_group = ctk.CTkFrame(grid, fg_color="transparent", width=150)
        self.sfx_group.grid(row=0, column=3, sticky="w", padx=(0, 14))
        self.sfx_options = sfx_dropdown_options()
        self.sfx_var = tk.StringVar(value=sfx_choice_display(self.sfx_key, self.audio_path))
        self.sfx_box = ctk.CTkOptionMenu(
            self.sfx_group, values=[d for d, _ in self.sfx_options],
            variable=self.sfx_var, width=150, height=28, corner_radius=ui_kit.RADIUS_CONTROL,
            fg_color=pal["surface_alt"], button_color=pal["accent2"],
            button_hover_color=pal["accent2_hover"], text_color=pal["text"],
            dropdown_fg_color=pal["surface"], dropdown_text_color=pal["text"],
            font=ui_kit.ui(11), command=self.on_sfx_choice)
        self.sfx_box.pack(side="top", fill="x")
        sfx_tools = ctk.CTkFrame(self.sfx_group, fg_color="transparent")
        sfx_tools.pack(side="top", fill="x", pady=(4, 0))
        self.rec_button = ctk.CTkButton(
            sfx_tools, text=tr("slot.record_short"), height=22, corner_radius=ui_kit.RADIUS_CONTROL,
            fg_color="transparent", border_width=1, border_color=pal["line_soft"],
            hover_color=pal["surface_alt"], text_color=pal["text_dim"],
            font=ui_kit.ui(10), command=self.record_audio)
        self.rec_button.pack(side="left", fill="x", expand=True, padx=(0, 2))
        self.file_button = ctk.CTkButton(
            sfx_tools, text=tr("slot.file_short"), height=22, corner_radius=ui_kit.RADIUS_CONTROL,
            fg_color="transparent", border_width=1, border_color=pal["line_soft"],
            hover_color=pal["surface_alt"], text_color=pal["text_dim"],
            font=ui_kit.ui(10), command=self.choose_file)
        self.file_button.pack(side="left", fill="x", expand=True, padx=(2, 0))

        # 4 - akcie
        actions = ctk.CTkFrame(grid, fg_color="transparent")
        actions.grid(row=0, column=4, sticky="e", padx=(0, 12))
        akcie = [(tr("common.test"), self.test, False),
                 (tr("common.edit"), self.open_settings, False)]
        if self.removable:
            akcie.append(("✕", self.remove, True))
        for text, cmd, danger in akcie:
            ctk.CTkButton(
                actions, text=text, width=26 if danger else 34, height=26,
                corner_radius=ui_kit.RADIUS_CONTROL, fg_color="transparent", border_width=1,
                border_color=pal["line_soft"],
                hover_color=pal["danger"] if danger else pal["surface_alt"],
                text_color=pal["text_dim"], font=ui_kit.ui(10),
                command=cmd).pack(side="left", padx=2)

        # 5 - zapnute/vypnute
        self.enabled_var = tk.BooleanVar(value=self.enabled_value)
        ctk.CTkSwitch(grid, text="", variable=self.enabled_var, width=40,
                      switch_width=36, switch_height=18,
                      progress_color=pal["accent"], button_color=pal["text_faint"],
                      button_hover_color=pal["accent_hover"],
                      fg_color=pal["switch_off"],
                      command=self.on_enabled_change).grid(row=0, column=5, sticky="e")

        # --- vysvetlivka, zabalena ---
        #
        # Sedi v TEJ ISTEJ karte ako hlaska, nie o pol stranky nizsie:
        # "preco zrovna celust" sa clovek pyta pri celusti. Obsah je ten
        # isty, co ma Sprievodca (`guide_panel.populate_card_body`), takze
        # sa tie dve miesta nemaju ako rozist.
        self.detail_wrap = ctk.CTkFrame(self.frame, fg_color="transparent")

        self.refresh_mode_widgets()

    # ---- zobrazenie ----

    @property
    def selected(self):
        try:
            return bool(self.select_var.get())
        except Exception:
            return False

    def set_selected(self, value):
        if not self.removable:
            return
        try:
            self.select_var.set(bool(value))
        except Exception:
            pass

    def summary_text(self):
        """Riadok pod frazou. Od 18. 9. nesie uz len hlas.

        Predtym tu stal prehlad casovania (cd 30s, +2s, kazde 3.), teda
        cisel, ktore sa pri hrani necitali. Ked hlas nie je prestaveny,
        nie je co hlasit a riadok ostane prazdny - lepsie nez "predvolene".
        """
        if self.mode not in (MODE_TTS, MODE_COMBO):
            return ""
        return (self.app.slot_voice_label(self) or "").split(" (")[0]

    def refresh_summary(self):
        try:
            self.summary_label.configure(text=self.summary_text())
            self._sync_summary_visibility()
        except Exception:
            pass

    def _sync_summary_visibility(self):
        if self.summary_text():
            if not self.summary_label.winfo_ismapped():
                self.summary_label.pack(fill="x", pady=(3, 0))
        else:
            self.summary_label.pack_forget()

    def refresh_mode_widgets(self):
        """Zhasne to, co k rezimu nepatri - ale stlpec NEODOBERIE.

        Keby sa prvok z rastra odstranil, riadok by sa presypal a sloty by
        prestali byt zarovnane pod sebou. Preto sa len zablokuje a stmavi.
        """
        show_text = self.mode in (MODE_TTS, MODE_COMBO)
        show_sfx = self.mode in (MODE_SFX, MODE_COMBO)
        pal = self.pal
        try:
            self.entry.configure(state="normal" if show_text else "disabled",
                                 text_color=pal["text"] if show_text else pal["text_faint"])
            for widget in (self.sfx_box, self.rec_button, self.file_button):
                widget.configure(state="normal" if show_sfx else "disabled")
        except Exception:
            pass

    # ---- vysvetlivka ----

    @property
    def detail_open(self):
        try:
            return bool(self.detail_wrap.winfo_ismapped())
        except Exception:
            return False

    def toggle_detail(self, _event=None):
        """Rozbali/zabali vysvetlivku k tejto hlaske.

        Telo sa stavia AZ PRI PRVOM ROZBALENI. Styri karty naraz znamenaju
        styri piktogramy a par obrazoviek textu; postavit to vsetko pri
        kazdom prekresleni stranky (zmena temy, zmena jazyka, pridanie
        slotu) by bolo vidno ako seknutie.
        """
        if self.guide_card is None:
            return
        if self.detail_open:
            self.detail_wrap.pack_forget()
            sipka = self.CARET_ZAVRETA
        else:
            self._build_detail()
            self.detail_wrap.pack(fill="x", padx=16, pady=(0, 14))
            sipka = self.CARET_OTVORENA
        try:
            # Rozbalena sipka dostane farbu prizvuku - v zozname styroch
            # kariet je tak na prvy pohlad vidno, ktora je otvorena.
            self.caret.configure(
                text=sipka,
                text_color=(self.pal["accent"] if self.detail_open
                            else self.pal["text_dim"]))
        except Exception:
            pass

    def _build_detail(self):
        if self._detail_built or self.guide_card is None:
            return
        self._detail_built = True
        pal = self.pal

        # ZASUVKA, nie pokracovanie karty.
        #
        # Vysvetlivka ma vlastnu plochu a ram, aby bolo na prvy pohlad
        # vidno, kde koncia ovladace hlasky a kde zacina text o tele. Bez
        # toho sa obe casti zlievali do jedneho vysokeho obdlznika.
        zasuvka = ctk.CTkFrame(self.detail_wrap, fg_color=pal["surface"],
                               corner_radius=ui_kit.RADIUS_CONTROL,
                               border_width=1, border_color=pal["line_soft"])
        zasuvka.pack(fill="x")

        # Tenky pruh vo farbe prizvuku po lavej hrane - viaze zasuvku k
        # hlaske nad nou, aby nevyzerala ako samostatna karta.
        pruh = ctk.CTkFrame(zasuvka, fg_color="transparent")
        pruh.pack(fill="x", padx=2, pady=2)
        ctk.CTkFrame(pruh, fg_color=pal["accent2"], width=3,
                     corner_radius=2).pack(side="left", fill="y")

        vnutro = ctk.CTkFrame(pruh, fg_color="transparent")
        vnutro.pack(side="left", fill="both", expand=True, padx=(14, 14),
                    pady=12)

        head = ctk.CTkFrame(vnutro, fg_color="transparent")
        head.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(head, text=self.guide_card["title"],
                     font=ui_kit.ui(13, "bold"), text_color=pal["text"],
                     anchor="w").pack(side="left")
        # `trigger` je popis okamihu v hre (drep, prebijanie, mierenie) -
        # NIE klaves, ktory by hlasku spustal. Tie uz appka necita; ostava
        # ako kontext, aby clovek vedel, kedy sa mu to typicky stane.
        ctk.CTkLabel(head, text=self.guide_card["trigger"],
                     font=ui_kit.ui(11), text_color=pal["text_faint"],
                     anchor="w").pack(side="left", padx=(12, 0))

        guide_panel.populate_card_body(vnutro, self.guide_card, pal,
                                       wraplength=620, sketch_side="left",
                                       sketch_size=104)

    # ---- eventy (main thread) ----

    def on_enabled_change(self):
        self.enabled_value = bool(self.enabled_var.get())
        self.app.save_settings()
        # Pripravuju sa len zapnute hlasky (`_slot_na_pripravu` v
        # app_audio.py): zapnutu treba pripravit (mimo hry hned, inak po
        # hre), vypnutej sa zvysok rozbehnutej pripravy uz neposle.
        self.app.schedule_pregenerate(200)

    def on_text_change(self):
        self.text_value = self.text_var.get()
        self.app.save_settings()
        self.app.schedule_pregenerate()

    def on_mode_change(self, label=None):
        self.mode = label_to_mode().get(self.mode_var.get(), MODE_TTS)
        if self.mode in (MODE_SFX, MODE_COMBO) and not self.sfx_key and not self.audio_path:
            self.sfx_var.set(tr("sfx.auto"))
        self.refresh_mode_widgets()
        self.app.save_settings()
        self.app.schedule_pregenerate()

    def on_sfx_choice(self, display):
        value = next((v for d, v in self.sfx_options if d == display), "")
        self.sfx_key = value
        self.app.save_settings()
        self.refresh_summary()

    def open_settings(self):
        SlotSettingsDialog(self.app, self)

    def remove(self):
        if self.removable:
            self.app.remove_slot(self.index)

    def _import_into_store(self, src, name):
        """Skopiruje vybrany zvuk do priecinka audio/ pod stabilnym menom a
        vrati novu cestu. Ponechat cudziu cestu "tak ako je" by znamenalo, ze
        slot stratí zvuk, ked sa povodny subor presunie ci zmaze - a v cistom
        exporte by taky odkaz viedol mimo dat appky (B2)."""
        os.makedirs(AUDIO_DIR, exist_ok=True)
        ext = os.path.splitext(src)[1].lower() or ".wav"
        dest = os.path.join(AUDIO_DIR, name + ext)
        if os.path.normcase(os.path.abspath(src)) != os.path.normcase(os.path.abspath(dest)):
            shutil.copy2(src, dest)
        return dest

    def choose_file(self):
        path = filedialog.askopenfilename(
            title=tr("dialog.choose_sfx_title", n=self.index + 1),
            filetypes=[(tr("filetype.audio"), "*.wav *.mp3"),
                      (tr("filetype.all"), "*.*")],
        )
        if path:
            try:
                self.audio_path = self._import_into_store(path, f"pick_{self.uid}")
            except Exception as exc:
                messagebox.showerror(APP_NAME, tr("record.save_error", err=exc))
                return
            self.sfx_key = "__custom__"
            self.sfx_var.set(sfx_choice_display(self.sfx_key, self.audio_path))
            if self.mode == MODE_TTS:
                self.mode = MODE_SFX
                self.mode_var.set(mode_labels()[self.mode])
                self.refresh_mode_widgets()
                # Hlaska uz nehovori - rovnako ako `on_mode_change`: zvysok
                # rozbehnutej pripravy jej text uz Microsoftu neposle.
                self.app.schedule_pregenerate()
            self.app.save_settings()
            self.app.log(tr("log.slot_sfx_set", n=self.index + 1,
                            name=os.path.basename(self.audio_path)))

    def record_audio(self):
        # Meno podla stabilneho uid slotu, nie podla poradia (slot{n}.wav sa
        # krizilo medzi profilmi = strata dat, B1).
        target = os.path.join(AUDIO_DIR, f"rec_{self.uid}.wav")
        dialog = RecordDialog(self.app, self.index + 1, target)
        self.app.root.wait_window(dialog.top)
        if dialog.saved_path:
            self.audio_path = dialog.saved_path
            self.sfx_key = "__custom__"
            self.sfx_var.set(sfx_choice_display(self.sfx_key, self.audio_path))
            if self.mode == MODE_TTS:
                self.mode = MODE_SFX
                self.mode_var.set(mode_labels()[self.mode])
                self.refresh_mode_widgets()
                # Vlastna nahravka namiesto hlasu: text sa uz nepripravuje a
                # zvysok rozbehnutej pripravy ho neposle (PRIVACY to slubuje).
                self.app.schedule_pregenerate()
            self.app.save_settings()
            self.app.log(tr("log.slot_recorded", n=self.index + 1,
                            name=os.path.basename(dialog.saved_path)))

    def test(self):
        self.app.fire_slot(self, ignore_cooldown=True, source="test")

    def to_dict(self):
        # `key_type`/`key_repr` sa uz nezapisuju - karta ich nedrzi a hlasku
        # nespusta klaves. `normalize_slot` ich pri nacitani doplni z
        # `DEFAULT_SLOT`, takze stare profily sa nerozbiju.
        return {
            "text": self.text_value,
            "mode": self.mode,
            "audio_path": self.audio_path,
            "sfx_key": self.sfx_key,
            "enabled": self.enabled_value,
            "voice_edge": self.voice_edge,
            "voice_sapi": self.voice_sapi,
            "voice_path": self.voice_path,
            "uid": self.uid,
        }


class RecordDialog:
    def __init__(self, app, slot_no, target_path):
        self.app = app
        self.target = target_path
        self.saved_path = None
        self.recorder = MicRecorder()
        self.start_time = None
        self._tick_job = None
        pal = app.pal

        self.top = ctk.CTkToplevel(app.root)
        self.top.title(tr("record.title", n=slot_no))
        self.top.configure(fg_color=pal["bg"])
        self.top.resizable(False, False)
        self.top.transient(app.root)
        self.top.grab_set()

        chrome = ui_kit.DialogChrome(
            self.top, pal, tr("record.title", n=slot_no), on_close=self.close)
        body = ctk.CTkFrame(chrome.body, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=16)

        ctk.CTkLabel(body, text=tr("record.hint"),
                    text_color=pal["text"]).pack(anchor="w")
        self.status = ctk.CTkLabel(body, text=tr("record.ready"), text_color=pal["text"],
                                   font=ui_kit.ui(13, "bold"))
        self.status.pack(anchor="w", pady=(10, 14))

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")
        self.rec_btn = ctk.CTkButton(row, text=tr("record.start"), fg_color=pal["danger"],
                                     hover_color=pal["warn"], text_color=pal["bg"],
                                     command=self.toggle)
        self.rec_btn.pack(side="left")
        self.preview_btn = ctk.CTkButton(row, text=tr("record.preview"),
                                         fg_color=pal["surface_alt"],
                                         hover_color=pal["border"], text_color=pal["text"],
                                         state="disabled", command=self.preview)
        self.preview_btn.pack(side="left", padx=8)
        ctk.CTkButton(row, text=tr("common.close"), fg_color=pal["surface_alt"],
                     hover_color=pal["border"], text_color=pal["text"],
                     command=self.close).pack(side="right")

        if os.path.exists(target_path):
            self.preview_btn.configure(state="normal")
            self.status.configure(text=tr("record.exists", name=os.path.basename(target_path)))

        self.top.protocol("WM_DELETE_WINDOW", self.close)

    def toggle(self):
        if self.recorder.active:
            try:
                self.recorder.stop_and_save(self.target)
            except Exception as exc:
                messagebox.showerror(APP_NAME, tr("record.save_error", err=exc),
                                     parent=self.top)
                self._reset_ui()
                return
            self.saved_path = self.target
            self._reset_ui()
            self.status.configure(text=tr("record.saved", name=os.path.basename(self.target)))
            self.preview_btn.configure(state="normal")
        else:
            try:
                self.recorder.start()
            except Exception as exc:
                messagebox.showerror(APP_NAME, tr("record.start_error", err=exc),
                                     parent=self.top)
                return
            self.start_time = time.time()
            self.rec_btn.configure(text=tr("record.stop"))
            self._tick()

    def _tick(self):
        if not self.recorder.active:
            return
        elapsed = time.time() - self.start_time
        self.status.configure(text=tr("record.recording", t=f"{elapsed:0.1f}"))
        self._tick_job = self.top.after(100, self._tick)

    def _reset_ui(self):
        if self._tick_job:
            self.top.after_cancel(self._tick_job)
            self._tick_job = None
        self.rec_btn.configure(text=tr("record.start"))

    def preview(self):
        path = self.saved_path or self.target
        if os.path.exists(path):
            self.app.worker.play(path, self.app.sfx_volume)

    def close(self):
        if self.recorder.active:
            self.recorder.cancel()
        self._reset_ui()
        self.top.grab_release()
        self.top.destroy()


# --------------------------------------------------------------------------
# Procedura pozadie pre "hero" uvodnu obrazovku Onboardingu - tmavy
# bridlicovy gradient + jemny dymovy Enso kruh (~15% opacity). Cisto
# dekorativne - ak PIL chyba alebo cokolvek zlyha, vrati None a volajuci
# pouzije obycajnu plnu farbu ako doteraz.
# --------------------------------------------------------------------------

def _build_hero_background(width, height):
    if not PIL_AVAILABLE:
        return None
    try:
        yy, xx = np.mgrid[0:height, 0:width]
        cx, cy = width * 0.5, height * 0.32
        max_dist = float(np.hypot(width * 0.5, height * 0.68)) or 1.0
        dist = np.hypot(xx - cx, yy - cy)
        t = np.clip(dist / max_dist, 0.0, 1.0)
        base = np.array([12.0, 16.0, 14.0])       # #0c100e
        edge = np.array([5.0, 7.0, 6.0])
        rgb = base[None, None, :] + (edge - base)[None, None, :] * t[:, :, None]
        img = Image.fromarray(rgb.astype(np.uint8), mode="RGB").convert("RGBA")

        # Jemny, mierne nepravidelny Enso (zenovy kruh) - ~15% opacity (38/255).
        ring = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(ring)
        r = min(width, height) * 0.32
        ccx, ccy = int(width * 0.5), int(height * 0.42)
        draw.arc([ccx - r, ccy - r, ccx + r, ccy + r], start=24, end=328,
                 fill=(226, 183, 106, 38), width=max(6, int(r * 0.09)))
        ring = ring.filter(ImageFilter.GaussianBlur(radius=max(4, int(r * 0.05))))
        return Image.alpha_composite(img, ring).convert("RGB")
    except Exception:
        return None


# --------------------------------------------------------------------------
# Onboarding wizard (prve spustenie) - vyber vizualneho / zvukoveho rezimu
# --------------------------------------------------------------------------


# Styl hlasky (`rebrik.py`, nastavenie `cue_style`) a jeho popisok. Tie iste
# vety su v onboardingu aj v Nastaveniach -> Zvuk, aby jedna volba nemala
# dve mena. Poradie je od najhlasnejsieho, rovnako ako `rebrik.STYLY`.
CUE_STYLE_LABELS = ((rebrik.STYL_HLAS, "ob.cue.voice"),
                    (rebrik.STYL_ZVUK, "ob.cue.sound"),
                    (rebrik.STYL_OBRAZ, "ob.cue.visual"))


class OnboardingWizard:
    """Sprievodca prvym spustenim - 5 krokov, kazdy nieco UKAZE alebo sa
    na jednu vec opyta:

      1) Co appka robi   - realne piktogramy overlay (grounding/jaw/breath)
      2) Ako to vyzera v hre - HUD + piktogram nad hernym pozadim
      3) Hodinky (nepovinne) - preco a "Sparovat teraz / Neskor"
      4) Hlavny svet + test zvuku - Hra · Sumi / Praca · Aizome, hlasitost
      5) Ako sa ma appka ozvat, ked hraca hra vytoci (styl hlasky)

    Predtym to boli 3 textove kroky (filozofia + diagnostika + vyber), ktore
    nikdy neukazali NA CO appka je ani PRECO hodinky. Diagnostika symptomov
    sa vypustila - novy hrac ma najprv pochopit produkt, nie rozhodovat o
    slotoch skor, nez vie o co ide (predvolene su zapnute vsetky styri).

    Vizualy sa GENERUJU za behu z hud_paint (piktogramy, HUD) - ziadne PNG
    na disku, konzistentne s tym, co hrac uvidi v hre, a bez viazanosti na
    konkretnu hru (copyright).

    Rozhranie pre app.py ostava: .confirmed, .choice, .volume_value,
    .diagnostics, .top. Pribudlo .wants_pairing (ci hrac klikol "Sparovat
    teraz" - app potom otvori WatchPairingDialog) a .cue_style (styl hlasky
    z kroku 5; None = hrac nevybral nic a ostava, co bolo).
    """

    STEP_COUNT = 5
    # Prvy krok, v ktorom sa nieco vybera (svet). "Preskocit uvod" skoci
    # sem, nie na posledny krok: uvod su vysvetlenia, volby sa neprekakuju.
    PRVA_VOLBA = 3

    def __init__(self, root, choice=None, volume=None):
        # `choice`/`volume`: aktualny svet (tema) a hlasitost, ked sa uvod
        # pusta znova z palety (`replay_onboarding`). Bez nich sprievodca
        # zacinal na predvolenom svete a 80 % - kto ho len preklikol, skoncil
        # z Prace v Hre (kde hlasky mozu hovorit nahlas) a s inou hlasitostou.
        self.choice = (choice if choice in (theme_mod.ZEN, theme_mod.MODERN)
                       else theme_mod.DEFAULT_THEME)
        self.confirmed = False
        self.wants_pairing = False        # klikol "Sparovat hodinky teraz"?
        # Styl hlasky z kroku 5. NIC nie je predvybrane (zadavatel: ziadne
        # predsudzovanie) - kto nevyberie, ostava na tom, co mal (novy hrac
        # na hlase, ako pri "neviem").
        self.cue_style = None
        self._cue_volba = None            # ktore z tlacidiel (aj "neviem")
        try:
            self.volume_value = 80 if volume is None else max(0, min(100, int(volume)))
        except (TypeError, ValueError):
            self.volume_value = 80
        # diagnostika sa uz nepyta - predvolene vsetky sloty zapnute
        self.diagnostics = {0: True, 1: True, 2: True, 3: True}
        self._assets_ready = sfx_assets.missing_count() == 0
        self.test_btn = None
        self._step = 0
        # Chrome onboardingu (nie len karty v kroku 4) ma sediet s
        # DEFAULT_THEME - predtym bolo natvrdo MODERN, co bolo pri
        # DEFAULT_THEME=MODERN neviditelne, ale po redizajne ("Sumi noc",
        # DEFAULT_THEME=ZEN) by prve okno, ktore hrac vidi, svietilo do
        # modra namiesto zlata.
        self._pal = theme_mod.tokens(self.choice)
        self._photos = []                 # drz referencie na obrazky (GC)

        title = tr("onboarding.welcome", app=APP_NAME)
        self.top = ctk.CTkToplevel(root)
        self.top.title(title)
        self.top.configure(fg_color=self._pal["bg"])
        # 600, nie 680: kroky su rozne vysoke a pri 680 ostavala pod
        # najkratsim z nich takmer tretina okna prazdna. Obsah sa navyse v
        # tele centruje (viz `_show_step`), takze rozdiel vysok medzi krokmi
        # uz nevytvara dieru nad patkou.
        self.top.geometry(self._centered_geometry(root, 720, 600))
        self.top.resizable(False, False)
        self.top.transient(root)
        self.top.grab_set()
        # Onboarding sa NESMIE dat zavriet "do prazdna" - krizik OS ramu
        # prehltneme a vlastna lista (DialogChrome) ho vobec nema.
        self.top.protocol("WM_DELETE_WINDOW", lambda: None)

        # Rovnaka tmava lista ako hlavne okno a ostatne dialogy (Sprievodca,
        # parovanie) - onboarding bol posledne okno s Windows titulkom.
        # closable=False: ziadny krizik ani Escape, on_close sa nevola.
        self.chrome = ui_kit.DialogChrome(self.top, self._pal, title,
                                          on_close=lambda: None, closable=False)
        host = self.chrome.body

        # obsah kroku + spodna navigacna lista (obe do chrome.body, nie do top)
        self.footer = ctk.CTkFrame(host, fg_color=self._pal["surface"],
                                   height=64, corner_radius=0)
        self.footer.pack(fill="x", side="bottom")
        self.footer.pack_propagate(False)
        self.body = ctk.CTkFrame(host, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=0, pady=0)
        self._build_footer()

        threading.Thread(target=self._prepare_assets, daemon=True).start()
        self._show_step(0)

    @staticmethod
    def _centered_geometry(root, width, height):
        """Geometria vycentrovana na monitore, kde je kurzor.

        Bezramove okno nikto neumiestni (OS ho nespravuje), takze by ostalo
        v rohu. CTk nasobi v geometry() SIRKU a VYSKU skalovanim, poziciu
        nie - preto sa stred rata z fyzickych rozmerov (width * scaling).

        POZN: tento postup sem bol prevzaty z
        `ui_shell.TitleBar._maximized_geometry`, ktora uz neexistuje
        (maximalizacia bola z appky odstranena) - odkaz zostava len ako
        vysvetlenie povodu, nehladaj ju.
        """
        try:
            import display
            mon = display.monitor_at_cursor(root)
            scaling = 1.0
            try:
                from customtkinter.windows.widgets.scaling.scaling_tracker \
                    import ScalingTracker
                scaling = ScalingTracker.get_window_scaling(root) or 1.0
            except Exception:
                pass
            px_w, px_h = int(width * scaling), int(height * scaling)
            x = mon.work_x + max(0, (mon.work_width - px_w) // 2)
            y = mon.work_y + max(0, (mon.work_height - px_h) // 2)
            return f"{width}x{height}+{x}+{y}"
        except Exception:
            return f"{width}x{height}"

    # ---- priprava audio balickov na pozadi ----

    def _prepare_assets(self):
        def progress(done, total):
            self.top.after(0, lambda: self._update_progress(done, total))
        sfx_assets.ensure_assets(progress=progress)

    def _update_progress(self, done, total):
        if total <= 0:
            return
        if done >= total:
            self._assets_ready = True
            if self.test_btn is not None:
                try:
                    self.test_btn.configure(state="normal",
                                            text=tr("onboarding.test_sound"))
                except Exception:
                    pass

    # ---- navigacia ----

    def _build_footer(self):
        pal = self._pal
        # vlavo: preskocit uvod (rovno na prvu volbu - svet, potom styl)
        self.skip_btn = ctk.CTkButton(
            self.footer, text=tr("ob.skip"), width=120, height=34,
            corner_radius=ui_kit.RADIUS_CONTROL, fg_color="transparent", hover_color=pal["surface_alt"],
            text_color=pal["text_faint"], font=ui_kit.ui(11),
            command=lambda: self._show_step(self.PRVA_VOLBA))
        self.skip_btn.pack(side="left", padx=24)

        # bodky postupu
        self.dots = ctk.CTkFrame(self.footer, fg_color="transparent")
        self.dots.pack(side="left", expand=True)
        self._dot_widgets = []
        for i in range(self.STEP_COUNT):
            d = ctk.CTkFrame(self.dots, width=8, height=8, corner_radius=4,   # bodka, nie ovladac
                             fg_color=pal["surface_alt"])
            d.pack(side="left", padx=4)
            self._dot_widgets.append(d)

        # vpravo: spat + dalej/vstupit
        self.next_btn = ctk.CTkButton(
            self.footer, text=tr("ob.next"), width=150, height=38,
            corner_radius=ui_kit.RADIUS_CONTROL, fg_color=pal["accent"], hover_color=pal["accent_hover"],
            text_color=pal["bg"], font=ui_kit.ui(12, "bold"),
            command=self._on_next)
        self.next_btn.pack(side="right", padx=(6, 24))
        self.back_btn = ctk.CTkButton(
            self.footer, text=tr("ob.back"), width=90, height=38,
            corner_radius=ui_kit.RADIUS_CONTROL, fg_color="transparent", border_width=1,
            border_color=pal["border"], hover_color=pal["surface_alt"],
            text_color=pal["text_dim"], font=ui_kit.ui(12),
            command=self._on_back)
        self.back_btn.pack(side="right", padx=6)

    def _on_next(self):
        if self._step >= self.STEP_COUNT - 1:
            self._confirm()
        else:
            self._show_step(self._step + 1)

    def _on_back(self):
        if self._step > 0:
            self._show_step(self._step - 1)

    def _show_step(self, index):
        self._step = index
        for w in self.body.winfo_children():
            w.destroy()
        self._photos.clear()
        # Obsah kroku ide do ramca, ktory sa v tele VYCENTRUJE (expand bez
        # fill). Predtym sa pakoval priamo do `body`, takze sedel nalepeny
        # hore a pod nim ostavala az tretina okna prazdna - kazdy zo styroch
        # krokov je inak vysoky a pevna vyska okna sa ich nikdy netrafi.
        inner = ctk.CTkFrame(self.body, fg_color="transparent")
        inner.pack(expand=True)
        builder = (self._step1, self._step2, self._step3, self._step4,
                   self._step5)[index]
        builder(inner)

        # stav navigacie
        pal = self._pal
        for i, d in enumerate(self._dot_widgets):
            d.configure(fg_color=pal["accent"] if i == index else pal["surface_alt"])
        # "Spat" sa na prvom kroku SKRYJE, nie zasedivie - nie je kam ist a
        # zasedivene tlacidlo vyzera ako nefunkcne rozhranie
        if index == 0:
            self.back_btn.pack_forget()
        elif not self.back_btn.winfo_ismapped():
            self.back_btn.pack(side="right", padx=6)
        # Od prvej volby dalej uz nie je co preskakovat (skok by viedol na
        # krok, na ktorom hrac prave je).
        self.skip_btn.pack_forget() if index >= self.PRVA_VOLBA \
            else self.skip_btn.pack(side="left", padx=24, before=self.dots)
        last = index == self.STEP_COUNT - 1
        self.next_btn.configure(text=tr("onboarding.confirm") if last else tr("ob.next"))

    # ---- spolocne prvky ----

    def _icon_image(self, name, size):
        """Piktogram overlay ako CTkImage (drzi referenciu kvoli GC)."""
        style = hud_paint.Style(self._pal)
        img = hud_paint.render_slot_icon(name, size, style)
        photo = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
        self._photos.append(photo)
        return photo

    def _kicker(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=ui_kit.ui(10, "bold"),
                     text_color=self._pal["accent"]).pack(pady=(30, 4))

    def _heading(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=ui_kit.ui(22, "bold"),
                     text_color=self._pal["text"], justify="center",
                     wraplength=560).pack(pady=(0, 12))

    def _para(self, parent, text, width=520):
        ctk.CTkLabel(parent, text=text, font=ui_kit.ui(12),
                     text_color=self._pal["text_dim"], justify="center",
                     wraplength=width).pack(pady=(0, 4))

    # ---- KROK 1: co appka robi ----

    def _step1(self, parent):
        pal = self._pal
        self._kicker(parent, tr("ob.step1.kicker"))
        self._heading(parent, tr("ob.step1.title"))

        # VSETKY STYRI realne piktogramy vedla seba.
        #
        # Boli tu tri (chybalo Uvolnenie), lenze appka si nainstaluje styri
        # spustace a karta Spustace hned hlasi "4" - prva obrazovka si tak
        # protirecila s druhou. Ikony su preto uzsie (84 px, mensie okraje),
        # aby sa styri do sirky okna zmestili.
        icons = ctk.CTkFrame(parent, fg_color="transparent")
        icons.pack(pady=(8, 16))
        for name, cap_key in (("grounding", "ob.step1.cap_grounding"),
                              ("jaw", "ob.step1.cap_jaw"),
                              ("release", "ob.step1.cap_release"),
                              ("breath", "ob.step1.cap_breath")):
            col = ctk.CTkFrame(icons, fg_color=pal["surface"], corner_radius=ui_kit.RADIUS_PANEL,
                               border_width=1, border_color=pal["border"])
            col.pack(side="left", padx=7)
            ctk.CTkLabel(col, text="", image=self._icon_image(name, 84)).pack(
                padx=16, pady=(16, 6))
            ctk.CTkLabel(col, text=tr(cap_key), font=ui_kit.ui(11, "bold"),
                         text_color=pal["text_dim"]).pack(pady=(0, 14))

        self._para(parent, tr("ob.step1.body"), width=560)
        # Ako sa to spusta - mechanizmus, ktory v celom uvode nikde nebol.
        # Prave on je dovod, preco appka neotravuje: nic sa nepripomina
        # navyse, visi to na klavesoch, ktore hrac aj tak tlaci.
        ctk.CTkLabel(parent, text=tr("ob.step1.how"), font=ui_kit.ui(11),
                     text_color=pal["accent"], justify="center",
                     wraplength=560).pack(pady=(10, 0))

    # ---- KROK 2: ako to vyzera v hre ----

    def _step2(self, parent):
        pal = self._pal
        self._kicker(parent, tr("ob.step2.kicker"))
        self._heading(parent, tr("ob.step2.title"))

        # nahlad "obrazovky" - tmava plocha s mriezkou, HUD dole a piktogram
        preview = self._build_screen_preview(parent)
        preview.pack(pady=(6, 16))

        self._para(parent, tr("ob.step2.body"), width=540)

        # Dve otazky, ktore si pri tejto appke polozi kazdy: "nezabanuju ma
        # za to?" a "kam idu moje data?". Obe maju odpoved hned tu, nie az
        # niekde v nastaveniach.
        for kluc in ("ob.step2.tag_safe", "ob.step2.tag_local"):
            tag = ctk.CTkFrame(parent, fg_color=pal["surface"], corner_radius=8,
                               border_width=1, border_color=pal["success"])
            tag.pack(pady=(10, 0))
            ctk.CTkLabel(tag, text="✓  " + tr(kluc), font=ui_kit.ui(10),
                         text_color=pal["success"], justify="left",
                         wraplength=520).pack(padx=14, pady=8)

    def _build_screen_preview(self, parent):
        """Male 'okno hry' (16:9) s mriezkou, HUD panelom v rohu a jednym
        piktogramom - aby hrac videl, KDE na obrazovke to sedi."""
        pal = self._pal
        W, H = 520, 292
        canvas = tk.Canvas(parent, width=W, height=H, highlightthickness=1,
                           highlightbackground=pal["border"], bg="#0b0f17", bd=0)
        # mriezka
        for gx in range(0, W, W // 8):
            canvas.create_line(gx, 0, gx, H, fill="#141b26")
        for gy in range(0, H, H // 8):
            canvas.create_line(0, gy, W, gy, fill="#141b26")
        # zameriavac v strede
        cx, cy = W // 2, H // 2
        canvas.create_line(cx - 8, cy, cx + 8, cy, fill="#3a4759")
        canvas.create_line(cx, cy - 8, cx, cy + 8, fill="#3a4759")

        # HUD panel vlavo dole
        try:
            style = hud_paint.Style(pal)
            hud = hud_paint.render_hud(
                style, bpm=118, stress=64,
                history=[70 + (i * 7) % 26 for i in range(90)],
                threshold=110, baseline=64,
                labels={"load": tr("hud.load"), "high": tr("hud.zone.high")},
                pulse=0.2, session="12:30", ss=2)
            hud = hud.resize((int(hud.width * 0.62), int(hud.height * 0.62)))
            photo = ImageTk.PhotoImage(hud)
            self._photos.append(photo)
            canvas.create_image(14, H - 14, image=photo, anchor="sw")
        except Exception:
            pass

        # piktogram (tazisko) dole v strede
        try:
            style = hud_paint.Style(pal)
            ico = hud_paint.render_visual("grounding", 150, 100, style,
                                          t=0.8, label=None, ss=2)
            photo2 = ImageTk.PhotoImage(ico)
            self._photos.append(photo2)
            canvas.create_image(cx, H - 20, image=photo2, anchor="s")
        except Exception:
            pass

        return canvas

    # ---- KROK 3: hodinky ----

    def _step3(self, parent):
        pal = self._pal
        self._kicker(parent, tr("ob.step3.kicker"))
        self._heading(parent, tr("ob.step3.title"))

        # velke srdce + krivka ako ilustracia
        heart = ctk.CTkFrame(parent, fg_color="transparent")
        heart.pack(pady=(4, 14))
        try:
            style = hud_paint.Style(pal)
            hud = hud_paint.render_hud(
                style, bpm=124, stress=78,
                history=[64 + int((i / 89.0) * 60) for i in range(90)],
                threshold=110, baseline=64,
                labels={"load": tr("hud.load"), "critical": tr("hud.zone.critical")},
                pulse=0.1, session=tr("log.hr_breathing_triggered", bpm=124)[:40],
                ss=2)
            hud = hud.resize((int(hud.width * 1.15), int(hud.height * 1.15)))
            photo = ImageTk.PhotoImage(hud)
            self._photos.append(photo)
            tk.Label(heart, image=photo, bd=0, bg=pal["bg"]).pack()
        except Exception:
            pass

        self._para(parent, tr("ob.step3.body"), width=540)
        # druhy dovod pre hodinky: historia relacii a pokrok - tlmenejsi a
        # mensi riadok pod hlavnym textom (doplnok, nie druhy odsek);
        # ziadny dalsi obrazok, krok 3 uz ma HUD
        self.step3_body2 = ctk.CTkLabel(parent, text=tr("ob.step3.body2"),
                                        font=ui_kit.ui(11), text_color=pal["text_faint"],
                                        justify="center", wraplength=520)
        self.step3_body2.pack(pady=(6, 0))

        # JEDNO tlacidlo, nie dve.
        #
        # Boli tu "Spárovať teraz" aj "Preskočiť — spárujem neskôr", a v
        # patke okna k tomu este "Ďalej" - tri cesty dopredu na jednej
        # obrazovke, z toho dve rovnake. Preskocenie uz patka vie (krok je
        # oznaceny ako nepovinny), takze tu ostava len ta akcia, ktora sa
        # inde spravit neda.
        ctk.CTkButton(parent, text="🕑  " + tr("ob.step3.pair_now"), width=230, height=44,
                      corner_radius=8, fg_color=pal["accent"],
                      hover_color=pal["accent_hover"], text_color=pal["bg"],
                      font=ui_kit.ui(12, "bold"),
                      command=self._pair_now).pack(pady=(12, 6))
        ctk.CTkLabel(parent, text=tr("ob.step3.later_note"), font=ui_kit.ui(9),
                     text_color=pal["text_faint"]).pack(pady=(6, 0))

    def _pair_now(self):
        """Hrac chce sparovat hned - dokoncime onboarding a app otvori
        parovaci dialog (cez wants_pairing)."""
        self.wants_pairing = True
        self._confirm()

    # ---- KROK 4: hlavny svet + test zvuku ----

    def _step4(self, parent):
        """Hlavny svet (B3-worlds): Hra · Sumi alebo Praca · Aizome.

        Vzhlad patri svetu, takze sa nevybera zvlast. `self.choice` ostava
        KLUC TEMY (rozhranie pre app.py); svet z neho appka odvodi cez
        `theme_mod.theme_world`."""
        pal = self._pal
        self._kicker(parent, tr("ob.step4.kicker"))
        self._heading(parent, tr("ob.step4.title"))

        cards = ctk.CTkFrame(parent, fg_color="transparent")
        cards.pack(padx=30, pady=(4, 0), fill="x")
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)
        self._card(cards, 0, theme_mod.WORLD_THEME["play"],
                   tr("ob.world.play.title"), tr("ob.world.play.desc"))
        self._card(cards, 1, theme_mod.WORLD_THEME["work"],
                   tr("ob.world.work.title"), tr("ob.world.work.desc"))

        # test zvuku + hlasitost
        test_row = ctk.CTkFrame(parent, fg_color="transparent")
        test_row.pack(pady=(20, 4), padx=36, fill="x")
        self.test_btn = ctk.CTkButton(
            test_row, width=210, height=38,
            text=tr("onboarding.test_sound") if self._assets_ready else tr("assets.preparing"),
            state="normal" if self._assets_ready else "disabled",
            fg_color=pal["accent2"], hover_color=pal["accent2_hover"],
            command=self._test_sound)
        self.test_btn.pack(side="left")
        self.volume_var = tk.IntVar(value=self.volume_value)
        ui_kit.block_slider_wheel(ctk.CTkSlider(
            test_row, from_=0, to=100, number_of_steps=100, variable=self.volume_var,
            width=150, command=lambda _v: self._on_volume_slide())).pack(
            side="left", padx=(12, 6), fill="x", expand=True)
        self.volume_label = ctk.CTkLabel(test_row, text=f"{self.volume_value} %",
                                         text_color=pal["text_dim"], width=44)
        self.volume_label.pack(side="left")

        self._para(parent, tr("ob.step4.body"), width=480)
        self._select(self.choice)

    def _on_volume_slide(self):
        self.volume_value = int(self.volume_var.get())
        self.volume_label.configure(text=f"{self.volume_value} %")

    def _test_sound(self):
        if not self._assets_ready:
            return
        # Vzdy zvuky HRY: v Praci hlasky zvuk nemaju (B3-worlds), takze
        # jediny zvuk, ktory hrac od appky kedy pocuje, je z herneho sveta.
        pack = theme_mod.WORLD_THEME["play"]
        key = sfx_assets.default_sound_for_slot_index(pack, 0)
        if not key:
            items = sfx_assets.library_items(pack)
            key = items[0][0] if items else None
        path = sfx_assets.sound_path(pack, key) if key else None
        if path and os.path.exists(path):
            threading.Thread(target=play_audio_file, args=(path, self.volume_value),
                             daemon=True).start()

    def _card(self, parent, col, key, title, desc):
        pal = theme_mod.tokens(key)
        frame = ctk.CTkFrame(parent, fg_color=pal["surface"], border_width=2,
                             border_color=pal["border"], corner_radius=ui_kit.RADIUS_PANEL,
                             width=260, height=176)
        frame.grid(row=0, column=col, padx=10, sticky="nsew")
        frame.grid_propagate(False)
        ctk.CTkLabel(frame, text=title, font=ui_kit.ui(15, "bold"),
                    text_color=pal["text"]).pack(pady=(18, 8))
        ctk.CTkLabel(frame, text=desc, font=ui_kit.ui(11), justify="center",
                    text_color=pal["text_dim"], wraplength=228).pack(padx=14)
        swatches = ctk.CTkFrame(frame, fg_color="transparent")
        swatches.pack(pady=14)
        for color in (pal["accent"], pal["accent2"], pal["surface_alt"]):
            ctk.CTkFrame(swatches, width=22, height=22, corner_radius=11,
                        fg_color=color).pack(side="left", padx=4)
        for widget in (frame,) + tuple(frame.winfo_children()):
            widget.bind("<Button-1>", lambda _e, k=key: self._select(k))
        frame.bind("<Enter>", lambda _e, f=frame, k=key: self._hover(f, k, True))
        frame.bind("<Leave>", lambda _e, f=frame, k=key: self._hover(f, k, False))
        setattr(self, f"_card_{key}", frame)

    def _hover(self, frame, key, on):
        if self.choice == key:
            return
        pal = theme_mod.tokens(key)
        frame.configure(border_color=pal["accent"] if on else pal["border"])

    def _select(self, key):
        self.choice = key
        for candidate in (theme_mod.ZEN, theme_mod.MODERN):
            frame = getattr(self, f"_card_{candidate}", None)
            if frame is None:
                continue
            pal = theme_mod.tokens(candidate)
            frame.configure(border_color=pal["accent"] if candidate == key
                            else pal["border"])

    # ---- KROK 5: ako sa ma appka ozvat (styl hlasky) ----

    # Styri odpovede v poradi, ktore schvalil zadavatel. "Neviem" sa uklada
    # ako hlas: rebrik (`rebrik.py`) ide o stupen nizsie po prvej vyhrade.
    NEVIEM = "unsure"
    CUE_VOLBY = CUE_STYLE_LABELS + ((NEVIEM, "ob.cue.unsure"),)

    def _step5(self, parent):
        """Styl hlasky (0.2). Styri ROVNAKO velke tlacidla pod sebou, nic
        predvybrane a ziadne "odporucane" - odpoved patri hracovi. Tichy
        riadok pod nimi povie, kde sa to da zmenit a ze appka moze ist sama
        tichsie, hlasnejsie nikdy; druhy, ze prirodzeny hlas posiela texty
        hlasok do Microsoftu a hlas z Windows nic."""
        pal = self._pal
        self._kicker(parent, tr("ob.step5.kicker"))
        self._heading(parent, tr("ob.cue.title"))
        volby = ctk.CTkFrame(parent, fg_color="transparent")
        volby.pack(pady=(4, 0))
        self._cue_buttons = {}
        for volba, kluc in self.CUE_VOLBY:
            btn = ctk.CTkButton(
                volby, text=tr(kluc), width=460, height=46,
                corner_radius=ui_kit.RADIUS_CONTROL, fg_color=pal["surface"],
                hover_color=pal["surface_alt"], border_width=2,
                border_color=pal["border"], text_color=pal["text_dim"],
                font=ui_kit.ui(13), command=lambda v=volba: self._vyber_styl(v))
            btn.pack(pady=5)
            self._cue_buttons[volba] = btn
        # Dva tiche riadky pod odpovedami, oba na sirku nadpisu (560): pri
        # 480 sa zalamuju do viacerych riadkov a okno onboardingu ma pevnu
        # vysku (600) - styri tlacidla a nadpis z nej uz beru vacsinu.
        ctk.CTkLabel(parent, text=tr("ob.cue.note"), font=ui_kit.ui(11),
                     text_color=pal["text_faint"], justify="center",
                     wraplength=560).pack(pady=(14, 0))
        # Co z odpovede "hlasom" odchadza z pocitaca - hrac to ma vediet uz
        # tu, nie az v Nastaveniach (`data.hint` hovori to iste).
        ctk.CTkLabel(parent, text=tr("ob.cue.online_note"), font=ui_kit.ui(11),
                     text_color=pal["text_faint"], justify="center",
                     wraplength=560).pack(pady=(8, 0))
        self._oznac_styl()

    def _vyber_styl(self, volba):
        """Klik na jednu zo styroch odpovedi."""
        self._cue_volba = volba
        self.cue_style = (rebrik.STYL_HLAS if volba == self.NEVIEM
                          else rebrik.normalize_cue_style(volba))
        self._oznac_styl()

    def _oznac_styl(self):
        """Vybrana odpoved ma okraj vo farbe akcentu, ostatne ostanu rovnake."""
        pal = self._pal
        for volba, btn in getattr(self, "_cue_buttons", {}).items():
            vybrana = volba == self._cue_volba
            try:
                btn.configure(
                    border_color=pal["accent"] if vybrana else pal["border"],
                    text_color=pal["text"] if vybrana else pal["text_dim"])
            except Exception:
                pass

    def _confirm(self):
        self.confirmed = True
        try:
            self.top.grab_release()
        except Exception:
            pass
        self.top.destroy()

