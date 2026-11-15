"""UI dialogs and cards of the main window - everything that opens its own
CTkToplevel or is a standalone visual "widget" (slot card, tooltip, stepper).

All classes here work with `app` (the DandurfApp instance from app.py) only
through its public methods/attributes - they duplicate no logic, they only
call it.
"""

import os
import shutil
import threading
import time
import tkinter as tk
from tkinter import filedialog

import numpy as np

import customtkinter as ctk

import guide_panel
import logging_setup      # pairing window: an error in on_close goes to app.log
import ui_kit

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

import hr_stats           # CONTEXT_IDS for the questionnaire at the end of a session
import rebrik             # cue ladder rung (picture / pause)
import trigger            # reasons why the app decided on its own to stay silent
import hud_paint          # the onboarding draws real pictograms and the HUD
import netinfo            # hidden IP in the pairing window (mask_ip)
import sfx_assets
import theme as theme_mod
# speak_sapi_isolated: voice preview in the introduction - ALWAYS the
# Windows voice, never Edge
from audio_engine import MicRecorder, play_audio_file, speak_sapi_isolated
from i18n import cislo, tr
from paths import APP_NAME, AUDIO_DIR, images_dir
from settings_model import (BREATH_SECONDS_MAX, BREATH_SECONDS_MIN, MODE_COMBO, MODE_ORDER,
                            MODE_SFX, MODE_TTS, je_kategoria, label_to_mode,
                            mode_labels, normalize_slot, sfx_choice_display,
                            sfx_dropdown_options)


# --------------------------------------------------------------------------
# Simple hover tooltip (a plain tk.Toplevel - needs no CTk theming)
# --------------------------------------------------------------------------

class HoverTooltip:
    """Attached to an existing widget - on hover, after a moment it shows a
    small description under it; it disappears when the mouse leaves."""

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
            # The same shape as the tooltips in the sidebar
            # (`ui_shell._HoverTip`): rounded, with a theme frame.
            # `tk.Label(relief="solid")` drew a square frame in the system
            # colour - the only place in the app with a sharp black-and-white
            # edge.
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
# Dialog with the detailed settings of one slot
# --------------------------------------------------------------------------

class SlotSettingsDialog:
    """The voice of one cue. Nothing more.

    Until 18. 9. the whole timing sat here too - its own pause, delay,
    "every N-th trigger", repetition and spread. None of those values was
    read during play: the automatic cue is fired by `trigger.CueTrigger`
    based on the body's load and delivered by `_emit`, which takes the
    text, mode and sound from the card. So six sliders tuned only the Test
    button.

    When the app speaks up is set in one place for all cues (the Cues
    page, "How often I speak up"), because that is a property of the
    person, not of a single sentence.
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
        # `ui_kit.option_menu` (0.3 batch 4b), not a bare CTkOptionMenu: the
        # same look as the voice choice in Settings and a width by the longest
        # voice name - "Microsoft Hedda Desktop - German (Germany)" got cut off
        # in a fixed 340 px.
        self.voice_box = ui_kit.option_menu(
            body, pal, width=340, values=names, variable=self.voice_var)
        self.voice_box.pack(fill="x", pady=(6, 6))
        self.voice_var.set(app.slot_voice_label(slot) or tr("voice.global"))

        ctk.CTkLabel(body, text=tr("dialog.voice_note"), font=ui_kit.ui(10),
                     text_color=pal["text_dim"], anchor="w", justify="left",
                     wraplength=340).pack(fill="x", pady=(0, 14))

        # --- Own voice recording ---------------------------------------------
        # Instead of the machine voice (TTS) your own recording can be used:
        # your voice says "dychaj" (breathe). If set, it is played instead of
        # TTS (see app._speak_text) - whole and clean, without the footsteps
        # filter, the same as the offline voice. It lives here because it is
        # part of "the voice of one cue".
        ctk.CTkLabel(body, text=tr("dialog.voice_rec_label"),
                     font=ui_kit.ui(12, "bold"), text_color=pal["text"],
                     anchor="w").pack(fill="x")
        self.voice_clip_status = ctk.CTkLabel(
            body, text=self._voice_clip_text(), font=ui_kit.ui(11),
            text_color=pal["text_dim"], anchor="w", justify="left", wraplength=340)
        self.voice_clip_status.pack(fill="x", pady=(4, 6))

        # Buttons from `ui_kit.button` (0.3 batch 4b): secondary ones with a
        # `control_border` frame, Save primary - as in all app windows.
        vrow = ctk.CTkFrame(body, fg_color="transparent")
        vrow.pack(fill="x", pady=(0, 4))
        ui_kit.button(vrow, pal, tr("dialog.voice_rec_record"),
                      command=self.record_voice).pack(side="left")
        ui_kit.button(vrow, pal, tr("dialog.voice_rec_file"),
                      command=self.choose_voice).pack(side="left", padx=8)
        ui_kit.button(vrow, pal, tr("dialog.voice_rec_clear"), kind="quiet",
                      command=self.clear_voice).pack(side="right")

        ctk.CTkLabel(body, text=tr("dialog.voice_rec_note"), font=ui_kit.ui(10),
                     text_color=pal["text_dim"], anchor="w", justify="left",
                     wraplength=340).pack(fill="x", pady=(0, 14))

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x")
        ui_kit.button(buttons, pal, tr("common.cancel"),
                      command=self.close).pack(side="right")
        ui_kit.button(buttons, pal, tr("common.save"), kind="primary",
                      command=self.save).pack(side="right", padx=(0, 8))

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

    # ---- own voice recording ----
    #
    # A recording is an immediate file operation, so (unlike the voice choice
    # in the dropdown) it is saved at once - Cancel has nothing to take back
    # and the person would not lose a recording just because they closed the
    # dialog.

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
            self.top.grab_set()   # give the grab back to this dialog
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
            # an app window above this dialog, not a system one (0.3, batch 4)
            ui_kit.notify(self.top, self.app.pal, APP_NAME,
                          tr("record.save_error", err=exc), kind="error")
            return
        self._commit_voice(tr("log.slot_voice_set", n=self.slot.index + 1,
                              name=os.path.basename(self.slot.voice_path)))

    def clear_voice(self):
        if not getattr(self.slot, "voice_path", ""):
            return
        self.slot.voice_path = ""
        self._commit_voice(tr("log.slot_voice_cleared", n=self.slot.index + 1))

# --------------------------------------------------------------------------
# Dialog for creating a new profile (game)
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
        ui_kit.button(buttons, pal, tr("common.cancel"),
                      command=self.close).pack(side="right")
        ui_kit.button(buttons, pal, tr("common.save"), kind="primary",
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
    """Developer overlay: the numbers from spec §2, editable at runtime.

    WHY IT EXISTS: those numbers are estimates from the literature, not
    from this player's body. In the first weeks it will turn out that the
    cue comes either too early or not at all. Without a way to adjust
    that at runtime the app would have to be rebuilt every evening.

    WHY IT CAN BE EDITED ONLY BETWEEN SESSIONS: spec §3.3. Changing
    thresholds in the middle of a session means measuring a moving target -
    windows from the first half of the evening and from the second could
    not be compared and nobody could find out afterwards which was which.
    That is why the fields are LOCKED while a session is running; it is not
    a recommendation in the text, but enforced.
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

        # The silence share separately - it is not a threshold, it is the
        # experiment design.
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

        # Raw listing of the last windows - the only thing that tells the truth
        # about the measurement.
        ctk.CTkLabel(body, text=tr("dev.windows"), font=ui_kit.ui(10, "bold"),
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
                ui_kit.notify(self.top, self.app.pal, tr("dev.title"),
                              tr("dev.bad_number"), kind="error")
                return
        try:
            podiel = float(str(self.silent_var.get()).replace(",", "."))
        except ValueError:
            ui_kit.notify(self.top, self.app.pal, tr("dev.title"),
                          tr("dev.bad_number"), kind="error")
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
    """End of session: what happened, not how the player felt.

    It is not a questionnaire about feelings. It is DATA CLEANING. Talking
    is the worst confounder in this measurement: when you talk, your
    breathing changes and the heart rate goes up, so a cue that sounds
    during it looks ineffective - although it has nothing to do with it.

    "Skip" is a button as big as "Save" and that is deliberate. If it were
    smaller or just a link, at some point it would get clicked away
    blindly - and randomly clicked-through context is WORSE data than no
    context.
    """

    def __init__(self, app, summary, cues=0, silent=0):
        self.app = app
        self.summary = summary
        self.vybrane = set()
        self.chips = {}
        self.activity = None          # 'play' / 'work' / None (did not say)
        self._activity_btns = {}
        # The session's world (B3-worlds): the one it STARTED in (`world` from
        # `_close_hr_session`). The played/worked row only HIGHLIGHTS it -
        # `self.activity` stays None until the player really clicks, so that
        # "I just clicked Save" is not recorded as their answer.
        self._svet = hr_stats.session_world(summary)
        self.note_box = None          # free note (CTkTextbox)
        # Subjective layer (research 2026-09-22) - what the HEART RATE DOES NOT
        # SEE.
        self.sleep = None             # 'rested'/'mid'/'broken'
        self.felt_load = None         # 0-10 (perceived load), None until touched
        self.valence = None           # -2..+2 (bad..good)
        self._body_sel = set()        # body during the peak (multi-select)
        self.cue_verdict = None       # landed/unneeded/disruptive/agitated/missed
        self._cue_fired = bool(cues)
        self._sleep_btns = {}
        self._val_btns = {}
        self._body_btns = {}
        self._cue_btns = {}
        # "Just setting up the app" (0.3). The first session after the
        # introduction has it switched on by the app (`setup` in the summary) -
        # `confirm` sends the chip state.
        self.setup = bool(summary.get("setup"))
        self._setup_btn = None
        pal = app.pal

        minuty = int((summary.get("duration_s") or 0) // 60)

        self.top = ctk.CTkToplevel(app.root)
        # WITH THE TIME, not with an empty gap. Without it the window title and
        # the taskbar literally said "Hral si ." (You played .) - a sentence
        # missing the one number it is there for.
        # A work session has no "Hral si" in the title.
        titulok = tr("session.end.title_work" if self._svet == "work"
                     else "session.end.title", time=self._cas(minuty))
        self.top.title(titulok)
        self.top.configure(fg_color=pal["bg"])
        self.top.resizable(False, False)
        self.top.transient(app.root)
        self.top.grab_set()

        # Only the app name in the title bar: the sentence with the time is the
        # HEADING of the body below (0.3, UX audit - "Hral si 26 min." was the
        # least visible text of the window) and twice, one under the other, it
        # would be pointless.
        chrome = ui_kit.DialogChrome(self.top, pal, APP_NAME, on_close=self.close)
        # The footer with the buttons is PINNED at the bottom (always visible),
        # the content above it SCROLLS. The questionnaire grew by the
        # subjective layer and on 1366x768 Save/Skip could otherwise not be
        # reached (follows up on B33).
        footer = ctk.CTkFrame(chrome.body, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=22, pady=(6, 16))
        self._footer = footer
        body = ctk.CTkScrollableFrame(
            chrome.body, fg_color="transparent", height=540,
            scrollbar_button_color=pal["surface_alt"],
            scrollbar_button_hover_color=pal["accent"])
        body.pack(fill="both", expand=True, padx=(22, 10), pady=(18, 4))

        # BODY HEADING: how long you played (0.3, UX audit, batch 4). It used
        # to be just a small sentence in the window's title bar - exactly the
        # one number that all the questions below relate to.
        self.heading_label = ctk.CTkLabel(
            body, text=titulok, font=ui_kit.ui(16, "bold"), text_color=pal["text"],
            anchor="w", justify="left", wraplength=420)
        self.heading_label.pack(fill="x", pady=(0, 6))
        # EXCLUSIVE FULLSCREEN (0.3 batch 4): while the game filled the whole
        # screen, Windows did not draw the pictures over it - one short
        # sentence right under the heading, otherwise the player would think
        # the app did not speak up. Only when it really did speak up, and not
        # in Work (there it speaks up only with a picture and the sentence
        # about the voice would not hold).
        self.fullscreen_label = None
        if self.ukaz_fullscreen_vetu(summary, cues, self._svet):
            self.fullscreen_label = ctk.CTkLabel(
                body, text=tr("session.end.fullscreen_note"), font=ui_kit.ui(11),
                text_color=pal["text_dim"], anchor="w", justify="left",
                wraplength=420)
            self.fullscreen_label.pack(fill="x", pady=(0, 8))

        # GRADUATION (easter egg): once, when the player reached "full
        # Zanshin". `_maybe_graduate` marks the summary; the circle has already
        # closed into a golden moon, here a mystical message is added (the raft
        # across the river).
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

        # At work every cue is only a picture (B3-worlds) - a sentence about
        # "naschval som mlcala" (I stayed silent on purpose) would claim a
        # difference there that did not exist.
        if cues and self._svet == "work":
            podnadpis = tr("session.end.cues_work", n=cues)
        elif cues and summary.get("cue_rung") == rebrik.OBRAZ:
            # The same in game on the "picture" rung (cue ladder, 0.2).
            podnadpis = tr("session.end.cues_visual", n=cues)
        elif cues and silent:
            # The silent control arm IS part of `cues` (only a picture was
            # shown), not extra - the sentence must say it as "of which", not as
            # a comparison. At zero, "0x som naschval mlcala" would look like a
            # template bug (UX audit, part 3).
            podnadpis = tr("session.end.cues_silent", n=cues, silent=silent)
        elif cues:
            podnadpis = tr("session.end.cues", n=cues)
        else:
            podnadpis = tr("session.end.cues_none")
        ctk.CTkLabel(body, text=podnadpis, font=ui_kit.ui(13),
                     text_color=pal["text"], anchor="w", justify="left",
                     wraplength=420).pack(fill="x")

        # WHEN IT DID NOT SPEAK UP, SAY WHY.
        # A bare "neozvala som sa" (I did not speak up) leaves the player
        # guessing between three very different things: they were calm, the app
        # has too strict a rule, or their watch kept dropping out. Each has a
        # different fix, so they are told apart.
        # The numbers come from `CueTrigger` via the session summary (app.py,
        # `_close_hr_session`); when they are not there, the line simply is not
        # shown.
        preco = self._preco_ticho(summary) if not cues else ""
        if preco:
            ctk.CTkLabel(body, text=preco, font=ui_kit.ui(11),
                         text_color=pal["text_faint"], anchor="w", justify="left",
                         wraplength=420).pack(fill="x", pady=(3, 10))
        else:
            # An empty row was as tall as a line of text - so under the
            # sentence about cues there hung a gap of ~30 px (0.3 batch 4).
            ctk.CTkFrame(body, fg_color="transparent", height=12).pack(fill="x")

        # HOW IT WENT - the curve of the whole evening right above the
        # questions.
        #
        # The questionnaire asks what happened. Without a picture the player
        # has to recall it from memory; with it they see where the heart rate
        # jumped and when the app spoke up, and answer what is in front of
        # their eyes. It is the same `SessionTrace` that is on Today and in
        # History - no new chart.
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
            # in the Work world "when you worked", not "played" (0.3 batch 4b)
            ctk.CTkLabel(body, text=tr("session.end.trace_hint_work" if self._svet == "work"
                                       else "session.end.trace_hint"),
                         font=ui_kit.ui(10), text_color=pal["text_faint"],
                         anchor="w", justify="left", wraplength=420).pack(
                fill="x", pady=(0, 14))

        # -- HOW IT FELT (subjective) - what the HEART RATE DOES NOT SEE -----
        # Activation (heart rate) and valence (good/bad) are two INDEPENDENT
        # axes; the main finding is the DIVERGENCE measured x felt (the heart
        # rate can be flat while the person feels bad). Hence ordinal scales
        # with fixed ids, not free text.
        ctk.CTkLabel(body, text=tr("session.felt.header").upper(),
                     font=ui_kit.ui(10, "bold"), text_color=pal["text_faint"],
                     anchor="w").pack(fill="x", pady=(0, 8))

        # Perceived load 0-10 (slider). None until touched (0 != did not say).
        load_row = ctk.CTkFrame(body, fg_color="transparent")
        load_row.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(load_row, text=tr("session.felt.load"), font=ui_kit.ui(12),
                     text_color=pal["text_dim"]).pack(side="left")
        self._load_val = ctk.CTkLabel(load_row, text="—", width=28,
                                      font=ui_kit.mono(12), text_color=pal["accent"])
        self._load_val.pack(side="right")
        # AN UNFILLED SLIDER DOES NOT LOOK LIKE AN ANSWER (0.3, UX audit). The
        # knob has to be somewhere and it sat at 0 in gold - exactly the bad
        # data point the comment above warns about. Until the player touches
        # it, it is all in `switch_off` (empty track, no value, "—" next to
        # it); the first touch colours it with the accent (`_on_load`).
        sl = ui_kit.block_slider_wheel(ctk.CTkSlider(
            body, from_=0, to=10, number_of_steps=10,
            progress_color=pal["switch_off"], button_color=pal["switch_off"],
            fg_color=pal["switch_off"], button_hover_color=pal["accent_hover"],
            command=self._on_load))
        sl.set(0)
        sl.pack(fill="x", pady=(0, 2))
        self._load_slider = sl
        ctk.CTkLabel(body, text=tr("session.felt.load_hint"), font=ui_kit.ui(10),
                     text_color=pal["text_faint"], anchor="w").pack(fill="x", pady=(0, 10))

        # Valence (5 levels, single choice).
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
                fg_color="transparent", border_color=pal["control_border"],
                hover_color=pal["surface_alt"], text_color=pal["text_dim"],
                font=ui_kit.ui(11),
                command=lambda x=v: self._pick_one("valence", x, self._val_btns))
            btn.grid(row=0, column=i, padx=(0, 4), sticky="ew")
            self._val_btns[v] = btn

        # Body during the peak (multi-select, EXPERIENCE tiles - not symptom
        # screening).
        ctk.CTkLabel(body, text=tr("session.felt.body_q"), font=ui_kit.ui(12),
                     text_color=pal["text_dim"], anchor="w").pack(fill="x", pady=(0, 6))
        body_row = ctk.CTkFrame(body, fg_color="transparent")
        body_row.pack(fill="x", pady=(0, 10))
        for i, bid in enumerate(hr_stats.BODY_PEAK_IDS):
            btn = ctk.CTkButton(
                body_row, text=tr(f"session.felt.body.{bid}"), height=30,
                corner_radius=ui_kit.RADIUS_CONTROL, border_width=1,
                fg_color="transparent", border_color=pal["control_border"],
                hover_color=pal["surface_alt"], text_color=pal["text_dim"],
                font=ui_kit.ui(12), command=lambda b=bid: self._toggle_body(b))
            btn.grid(row=i // 3, column=i % 3, padx=(0, 6), pady=(0, 4), sticky="w")
            self._body_btns[bid] = btn

        # Verdict on the cue - the question depends on whether the cue sounded.
        # "it wound me up" (0.2) is a different thing from "it disrupted":
        # arousal, not attention. Both lower the cue ladder by one rung
        # (`rebrik.py`).
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
                fg_color="transparent", border_color=pal["control_border"],
                hover_color=pal["surface_alt"], text_color=pal["text_dim"],
                font=ui_kit.ui(12),
                command=lambda x=v: self._pick_one("cue_verdict", x, self._cue_btns))
            btn.pack(side="left", padx=(0, 6))
            self._cue_btns[v] = btn

        ui_kit.linka(body, pal).pack(fill="x", pady=(2, 12))

        # ACTIVITY: played or worked? Single choice (not chips - they are
        # mutually exclusive options). At the top on purpose: it is the most
        # basic context of the evening and from it "work" can be separated from
        # "play" - from real data, not by guessing. No click = the player did
        # not say (None), the same as with the chips; the session then belongs
        # to the world it started in (`world`).
        ctk.CTkLabel(body, text=tr("session.context.activity_question").upper(),
                     font=ui_kit.ui(10, "bold"), text_color=pal["text_faint"],
                     anchor="w").pack(fill="x", pady=(0, 8))
        akt_row = ctk.CTkFrame(body, fg_color="transparent")
        akt_row.pack(fill="x", pady=(0, 10))
        for kind in hr_stats.ACTIVITY_KINDS:
            btn = ctk.CTkButton(
                akt_row, text=tr(f"session.context.activity.{kind}"), height=30,
                corner_radius=ui_kit.RADIUS_CONTROL, border_width=1,
                fg_color="transparent", border_color=pal["control_border"],
                hover_color=pal["surface_alt"], text_color=pal["text_dim"],
                font=ui_kit.ui(12), command=lambda k=kind: self._set_activity(k))
            btn.pack(side="left", padx=(0, 6))
            self._activity_btns[kind] = btn
        # The world the session started in is visible at once - whoever forgot
        # to switch fixes it with one click. But only that click gets saved.
        self._paint_activity(self._svet)

        # JUST SETTING UP THE APP (0.3). The introduction, pairing and the tour
        # are calm at the desk, not playing - from such a session the limit and
        # the threshold would be pulled towards calm (the same bug as 110 -> 80
        # in KNOWN_ISSUES), so they are not learnt from it
        # (`hr_stats.ciste_relacie`). Its own row, not a third answer to
        # played/worked: it is a switch and does not change the session's
        # world.
        setup_row = ctk.CTkFrame(body, fg_color="transparent")
        setup_row.pack(fill="x", pady=(0, 2))
        self._setup_btn = ctk.CTkButton(
            setup_row, text=tr("session.context.setup"), height=30,
            corner_radius=ui_kit.RADIUS_CONTROL, border_width=1,
            fg_color="transparent", border_color=pal["control_border"],
            hover_color=pal["surface_alt"], text_color=pal["text_dim"],
            font=ui_kit.ui(12), command=self._prepni_setup)
        self._setup_btn.pack(side="left")
        # The chip that is on at opening was switched on by the app itself (the
        # first session after the introduction - the questionnaire comes right
        # after saving, the player has not seen it yet). Without a sentence
        # they would not know why, and whoever really played during it would
        # leave it on by Saving: the first evening would then not count towards
        # learning.
        setup_hint = (tr("session.context.setup_hint_first") if self.setup
                      else tr("session.context.setup_hint"))
        ctk.CTkLabel(body, text=setup_hint,
                     font=ui_kit.ui(10), text_color=pal["text_faint"],
                     anchor="w", justify="left", wraplength=420).pack(
            fill="x", pady=(0, 10))
        self._paint_setup()

        # TWO ROWS, not one. The first is "what happened during the evening",
        # the second "what you sat down to it with" - they are different things
        # and move different numbers. Nine chips in one row would also make the
        # dialog fall apart: `pack(side="left")` does not wrap and the last
        # ones would fall out.
        for nadpis, skupina in (("session.context.question", hr_stats.CONTEXT_DIANIE),
                                ("session.context.body_question", hr_stats.CONTEXT_TELO)):
            ctk.CTkLabel(body, text=tr(nadpis).upper(),
                         font=ui_kit.ui(10, "bold"), text_color=pal["text_faint"],
                         anchor="w").pack(fill="x", pady=(0, 8))
            chips = ctk.CTkFrame(body, fg_color="transparent")
            chips.pack(fill="x", pady=(0, 10))
            # GRID, not pack(side="left"): a row of chips does not wrap, and
            # six chips side by side bloated the dialog to 1416 px - on
            # 1366×768 it was then impossible to reach Save/Skip (B33). Three
            # columns keep it at a sensible width and the chips wrap onto more
            # rows.
            for i, cid in enumerate(skupina):
                btn = ctk.CTkButton(
                    chips, text=tr(f"session.context.{cid}"), height=30,
                    corner_radius=ui_kit.RADIUS_CONTROL, border_width=1,
                    fg_color="transparent", border_color=pal["control_border"],
                    hover_color=pal["surface_alt"], text_color=pal["text_dim"],
                    font=ui_kit.ui(12),
                    command=lambda c=cid: self._prepni(c))
                btn.grid(row=i // 3, column=i % 3, padx=(0, 6), pady=(0, 4),
                         sticky="w")
                self.chips[cid] = btn

        # SLEEP last night (replaces the binary 'unavený' (tired)): 3 levels,
        # single choice. Lack of sleep raises the personal baseline for the
        # whole day - it explains why the same game is once "nothing" and
        # another time "bad".
        ctk.CTkLabel(body, text=tr("session.sleep.q").upper(), font=ui_kit.ui(10, "bold"),
                     text_color=pal["text_faint"], anchor="w").pack(fill="x", pady=(2, 8))
        sleep_row = ctk.CTkFrame(body, fg_color="transparent")
        sleep_row.pack(fill="x", pady=(0, 10))
        for lvl in hr_stats.SLEEP_LEVELS:
            btn = ctk.CTkButton(
                sleep_row, text=tr(f"session.sleep.{lvl}"), height=30,
                corner_radius=ui_kit.RADIUS_CONTROL, border_width=1,
                fg_color="transparent", border_color=pal["control_border"],
                hover_color=pal["surface_alt"], text_color=pal["text_dim"],
                font=ui_kit.ui(12),
                command=lambda l=lvl: self._pick_one("sleep", l, self._sleep_btns))
            btn.pack(side="left", padx=(0, 6))
            self._sleep_btns[lvl] = btn

        ctk.CTkLabel(body, text=tr("session.context.why"), font=ui_kit.ui(11),
                     text_color=pal["text_faint"], anchor="w", justify="left",
                     wraplength=420).pack(fill="x", pady=(14, 12))

        # OWN NOTE: free text about the evening (what the chips do not capture -
        # a new game, bad sleep, an argument, anything). The app only keeps and
        # shows it, does not interpret it.
        ctk.CTkLabel(body, text=tr("session.context.note_label").upper(),
                     font=ui_kit.ui(10, "bold"), text_color=pal["text_faint"],
                     anchor="w").pack(fill="x", pady=(0, 6))
        self.note_box = ctk.CTkTextbox(
            body, height=58, font=ui_kit.ui(12), fg_color=pal["surface_alt"],
            text_color=pal["text"], border_width=1, border_color=pal["card_border"],
            corner_radius=ui_kit.RADIUS_CONTROL, wrap="word")
        self.note_box.pack(fill="x", pady=(0, 18))

        tlacidla = ctk.CTkFrame(self._footer, fg_color="transparent")
        tlacidla.pack(fill="x")
        # The same width for both: skipping must be as easy as saving.
        # `ui_kit.button` (0.3 batch 4b): Skip is a secondary button with a
        # `control_border` frame as in all windows, not a grey fill.
        ui_kit.button(tlacidla, pal, tr("common.save"), kind="primary", width=132,
                      height=34, command=self.confirm).pack(side="left")
        ui_kit.button(tlacidla, pal, tr("session.end.skip"), width=132, height=34,
                      command=self.close).pack(side="left", padx=(8, 0))

        self.top.protocol("WM_DELETE_WINDOW", self.close)

        # FIXED window SIZE. Without it, with resizable(False) the toplevel
        # stretches to the full height of the content (even below the bottom of
        # the screen, buttons off-screen) and shrinks to the width of the scroll
        # canvas (~the right column of chips cut off). With a fixed geometry the
        # body scrolls inside and the footer stays pinned and visible.
        # The dimensions are LOGICAL - CTk multiplies them by the DPI scale.
        # Centre of the WORK AREA of the monitor under the cursor (not the whole
        # screen of the main monitor) and lower when 680 px do not fit in the
        # work area - the footer with the buttons stays above the taskbar.
        ui_kit.umiestni_dialog(self.top, self.app.root, 660, 680)

    @staticmethod
    def _preco_ticho(summary):
        """Why not a single cue sounded during the whole session.

        The order of conditions is NOT arbitrary: heart-rate dropouts are
        checked first, because with them the other numbers are
        untrustworthy - the longest stretch may look short just because
        gaps in the data chopped it up.

        Then the GATE (0.2): not a single pause in input during a long
        session suggests input that never goes quiet (gyro, a stick
        without a dead zone) - the player needs to be told, not blamed for
        it. And when the app decided by itself to stay silent (the load was
        still rising or the heart rate was in the critical zone), it must
        not sound like "the load was not up long enough".

        At the very start the LADDER PAUSE (0.2): the app had cues switched
        off, so any other sentence would explain a silence it chose itself.
        """
        if summary.get("cue_rung") == rebrik.PAUZA:
            return tr("session.end.none_paused")
        behov = summary.get("above_runs")
        if behov is None:
            return ""                      # older session, has no numbers
        vypadkov = summary.get("runs_cancelled_gap") or 0
        if vypadkov >= 2 and vypadkov >= (summary.get("runs_cancelled_dip") or 0):
            return tr("session.end.none_dropouts", n=vypadkov)
        # "NOT NOW" DURING THE SESSION (since 24. 9. it does not close it). The
        # state machine was asleep then, so the counters below do not see that
        # time: "the load never got above the limit" could claim a silence that
        # the player chose themselves. The dropouts above are true anyway
        # (outside the snooze).
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
        # `is not None`: an old session has no pause count and a zero would
        # lie.
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
            # Only the gate (body), not `nedalo_sa` (gap, snooze,
            # walking) - the sentence talks about the heart rate and would
            # not be true then.
            return tr("session.end.none_withheld")
        if not behov:
            return tr("session.end.none_never")
        return tr("session.end.none_short",
                  najdlhsie=int(summary.get("longest_above_s") or 0),
                  treba=int(summary.get("stress_hold_s") or 0))

    @staticmethod
    def _cas(minuty):
        """Without `@staticmethod`, `self._cas(minuty)` passed two arguments and
        the whole questionnaire crashed on a TypeError at the very first
        line. It was the SECOND reason why the session context could never
        be filled in - the first was that the dialog was thrown away on app
        close before it was drawn."""
        if minuty < 60:
            return tr("history.minutes", m=minuty)
        # From an hour on "2 h 03 min", not "2:03" (0.3 batch 4): in the
        # questionnaire heading "2:03 hrania" (2:03 of playing) read as two
        # minutes. The same format as the "Session length" card and the session
        # trace axis (`ui_kit.dlzka_text`).
        return ui_kit.dlzka_text(minuty * 60)

    def _set_activity(self, kind):
        """Single choice played/worked. The click is the player's ANSWER - only
        it gets saved into `activity`, even when they click the already
        highlighted world (confirmation).

        A second click no longer cancels the answer: the row shows the
        session's world, which would stay highlighted after cancelling
        anyway, so "cancelling" would not be visible. (Until B3-worlds a
        second click here returned "did not say".)"""
        self.activity = kind
        self._paint_activity(kind)

    def _paint_activity(self, zvyrazneny):
        """Repaints played/worked buttons - highlights only `zvyrazneny`."""
        pal = self.app.pal
        for k, btn in self._activity_btns.items():
            if k == zvyrazneny:
                btn.configure(fg_color=pal["accent2"], border_color=pal["accent"],
                              text_color=pal["accent"])
            else:
                btn.configure(fg_color="transparent", border_color=pal["control_border"],
                              text_color=pal["text_dim"])

    def _prepni(self, cid):
        pal = self.app.pal
        btn = self.chips[cid]
        if cid in self.vybrane:
            self.vybrane.discard(cid)
            btn.configure(fg_color="transparent", border_color=pal["control_border"],
                          text_color=pal["text_dim"])
        else:
            self.vybrane.add(cid)
            btn.configure(fg_color=pal["accent2"], border_color=pal["accent"],
                          text_color=pal["accent"])

    def _on_load(self, v):
        """Perceived load slider. First touch = they have answered (0 would
        otherwise be indistinguishable from 'did not say')."""
        self.felt_load = int(round(float(v)))
        try:
            self._load_val.configure(text=str(self.felt_load))
            # from the first touch it is an answer - track and knob in the
            # accent
            pal = self.app.pal
            self._load_slider.configure(progress_color=pal["accent"],
                                        button_color=pal["accent"])
        except Exception:
            pass

    def _pick_one(self, group, value, btns):
        """Single choice (valence/sleep/verdict): a second click on the same
        cancels (back to None). `group` is the attribute name, `btns` a
        dict of buttons."""
        pal = self.app.pal
        nova = None if getattr(self, group) == value else value
        setattr(self, group, nova)
        for v, btn in btns.items():
            if v == nova:
                btn.configure(fg_color=pal["accent2"], border_color=pal["accent"],
                              text_color=pal["accent"])
            else:
                btn.configure(fg_color="transparent", border_color=pal["control_border"],
                              text_color=pal["text_dim"])

    def _toggle_body(self, bid):
        """Multi-select of the 'body during the peak' tiles."""
        pal = self.app.pal
        btn = self._body_btns[bid]
        if bid in self._body_sel:
            self._body_sel.discard(bid)
            btn.configure(fg_color="transparent", border_color=pal["control_border"],
                          text_color=pal["text_dim"])
        else:
            self._body_sel.add(bid)
            btn.configure(fg_color=pal["accent2"], border_color=pal["accent"],
                          text_color=pal["accent"])

    def _prepni_setup(self):
        """The "Just setting up the app" chip - on/off."""
        self.setup = not self.setup
        self._paint_setup()

    def _paint_setup(self):
        """Recolours the setup chip according to `self.setup`."""
        btn = self._setup_btn
        if btn is None:
            return
        pal = self.app.pal
        if self.setup:
            btn.configure(fg_color=pal["accent2"], border_color=pal["accent"],
                          text_color=pal["accent"])
        else:
            btn.configure(fg_color="transparent", border_color=pal["control_border"],
                          text_color=pal["text_dim"])

    @staticmethod
    def ukaz_fullscreen_vetu(summary, cues, svet):
        """Does the exclusive-fullscreen line belong in the header? (0.3 batch 4)

        Only when the app saw a full-screen game during the session
        (`fullscreen` in the summary), really spoke up (`cues` > 0 -
        otherwise there was no picture that could not be seen) and not in
        Work (there everything is only a picture, the sentence about the
        voice would not hold)."""
        try:
            return bool(isinstance(summary, dict) and summary.get("fullscreen")
                        and int(cues or 0) > 0 and svet != "work")
        except (TypeError, ValueError):
            return False

    def bolo_vyplnene(self):
        """Did the player touch at least one answer? (0.3, the second "Quit")

        A second "Quit" from the tray while the questionnaire was open used
        to close it like "Skip" and the filled-in answers disappeared. The
        author's decision: something filled in = save (like "Save"),
        nothing = close like "Skip" (`app._quit`). Neither the highlighted
        session world nor the setup chip set by the app counts as an
        answer - only a click."""
        if (self.vybrane or self._body_sel or self.activity is not None
                or self.sleep is not None or self.felt_load is not None
                or self.valence is not None or self.cue_verdict is not None):
            return True
        if self.setup != bool(self.summary.get("setup")):
            return True
        if self.note_box is not None:
            try:
                return bool(self.note_box.get("1.0", "end").strip())
            except Exception:
                return False
        return False

    def confirm(self):
        # An empty list is NOT the same as skipping: [] means
        # "none of this happened", None means "the player did not say".
        poznamka = ""
        if self.note_box is not None:
            try:
                poznamka = self.note_box.get("1.0", "end")
            except Exception:
                poznamka = ""
        # The save result is returned (0.3 batch 4b): when the app quits, the
        # app finishes the questionnaire (`_dokonci_dotaznik`) and writes to
        # the journal, based on it, whether the answers were saved.
        ok = self.app.save_session_context(
            self.summary, sorted(self.vybrane),
            activity=self.activity, note=poznamka,
            sleep=self.sleep, felt_load=self.felt_load, valence=self.valence,
            body_peak=(sorted(self._body_sel) or None), cue_verdict=self.cue_verdict,
            setup=self.setup)
        self.close()
        return ok

    def close(self):
        try:
            self.top.grab_release()
        except Exception:
            pass
        self.top.destroy()


# --------------------------------------------------------------------------
# Profile import from a code (Base64/JSON) - for quick sharing, e.g. on Discord
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

        # small error text: `danger_text` (>= 4.5:1), not `danger` (theme.py)
        self.error_label = ctk.CTkLabel(body, text="", text_color=pal["danger_text"],
                                        wraplength=380, justify="left")
        self.error_label.pack(anchor="w", pady=(0, 6))

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x")
        ui_kit.button(buttons, pal, tr("common.cancel"),
                      command=self.close).pack(side="right")
        ui_kit.button(buttons, pal, tr("import.confirm"), kind="primary",
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
    """Data import (History -> Your data): Merge / Replace / Cancel.

    Before, it was a system `askyesnocancel` with the hard-coded text
    "Zlucit = Ano / Nahradit = Nie" (Merge = Yes / Replace = No): Slovak
    words in every language and buttons in the Windows language, so in the
    English interface (or on English Windows) the options did not match
    the buttons - and the irreversible REPLACE was on "No". Now the options
    are right on the buttons (i18n) and REPLACE comes only on the second
    click, with a sentence saying exactly what gets overwritten and that a
    backup is set aside.

    `on_choice("merge" | "replace")` is called only after confirmation and
    only after the dialog closes; Cancel, the X and Escape call nothing.
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
        """A button from `ui_kit.button` (0.3 batch 4b): Replace is of the
        `danger` kind (frame and text `danger_text`) like "Delete"
        everywhere in the app, not white text in a dark-red frame with a
        red hover."""
        kind = "primary" if primary else ("danger" if danger else "secondary")
        btn = ui_kit.button(self.buttons, self.pal, text, command=command, kind=kind,
                            width=max(width, ui_kit._sirka_textu(text, ui_kit.ui(12))
                                      + 2 * ui_kit._BUTTON_PAD_X))
        btn.pack(side="right", padx=(8, 0))
        return btn

    def _clear(self):
        for w in self.buttons.winfo_children():
            w.destroy()

    def _choose(self):
        """First step: what is in the file and three options. Merge is the
        default (safe) - Replace is an outline button, not a filled one."""
        self._clear()
        self.text.configure(text=self.message)
        self._button(tr("common.cancel"), self.close, width=90)
        self._button(tr("data.import.replace"), self._confirm_replace, danger=True)
        self._button(tr("data.import.merge"), lambda: self._done("merge"),
                     primary=True)

    def _confirm_replace(self):
        """REPLACE step two: what gets overwritten, where the backup goes."""
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
# Setting up the in-game visual overlays - size, position and test for
# all 4 slots at once, in one modal window.
# --------------------------------------------------------------------------

# Corner presets for the HUD position (in % of monitor width/height). The
# centres are deliberately moved away from the edges - the killfeed and
# chat in shooters sit right by the screen border.
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
        # Centred on the work area and fully on it (760 px never fits on a
        # 768-px screen) - see `ui_kit.umiestni_dialog`.
        ui_kit.umiestni_dialog(self.top, app.root, 520, 760,
                               min_width=470, min_height=480)
        self.top.transient(app.root)
        self.top.grab_set()

        chrome = ui_kit.DialogChrome(self.top, pal, tr("overlay.dialog_title"),
                                     on_close=self.close)
        header = ctk.CTkFrame(chrome.body, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 6))
        ctk.CTkLabel(header, text=tr("overlay.dialog_hint"), font=ui_kit.ui(11),
                    text_color=pal["text_dim"], wraplength=430, justify="left").pack(
            anchor="w")

        # NOTE: the monitor choice was drawn here and the whole HUD card below.
        # They were SECOND copies of the same settings that are in Settings ->
        # General, and they drifted apart: switching the HUD in this dialog
        # overwrote `hud_config`, but not the switch variable on the
        # page - the player then saw it off in one place and on in the other
        # and had no way to find out which value applied.
        #
        # This dialog is for POSITION AND SIZE. What is switched on and on
        # which screen is one place - the General page.

        scroll = ctk.CTkScrollableFrame(
            chrome.body, fg_color="transparent", scrollbar_button_color=pal["surface_alt"],
            scrollbar_button_hover_color=pal["accent"])
        scroll.pack(fill="both", expand=True, padx=14, pady=10)


        for i in range(4):
            self._build_row(scroll, i, pal)

        footer = ctk.CTkFrame(chrome.body, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 16))
        # A secondary button (`ui_kit.button`), not an `accent2` fill without
        # a frame in the CTk default font (0.3 batch 4) - changes apply at
        # once, "Close" is not the main action of the window.
        ui_kit.button(footer, pal, tr("common.close"), command=self.close,
                      width=100).pack(side="right")

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
        # The visual's pictogram with the same brush as in game, not an emoji
        # from the translation.
        vizualy = ("grounding", "jaw", "release", "breath")
        if 0 <= index < len(vizualy):
            ui_kit.SlotIcon(head, pal, vizualy[index], size=22).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(head, text=ui_kit.bez_ikony(tr(f"overlay.slot.{index}")),
                     font=ui_kit.ui(13, "bold"), text_color=pal["text"]).pack(side="left")
        enabled_var = tk.BooleanVar(value=cfg["enabled"])
        ui_kit.switch(head, pal, text=tr("overlay.enable"), variable=enabled_var,
                      command=lambda idx=index, var=enabled_var: self.app.on_overlay_config_change(
                          idx, enabled=var.get())).pack(side="right")

        scale_row = ctk.CTkFrame(inner, fg_color="transparent")
        scale_row.pack(fill="x", pady=(10, 0))
        # The app font (`ui_kit.ui`), not the CTk default; the size with a
        # decimal comma depending on the language and the × sign (0.3 batch 4).
        ctk.CTkLabel(scale_row, text=tr("overlay.scale"), text_color=pal["text_dim"],
                     font=ui_kit.ui(12), width=90, anchor="w").pack(side="left")
        scale_value_label = ctk.CTkLabel(scale_row, text=f"{cislo(cfg['scale'], 2)}×",
                                         text_color=pal["text_faint"], width=50,
                                         font=ui_kit.ui(12))
        scale_value_label.pack(side="right")
        scale_var = tk.DoubleVar(value=cfg["scale"])

        def on_scale(_v, idx=index, var=scale_var, label=scale_value_label):
            value = round(float(var.get()), 2)
            label.configure(text=f"{cislo(value, 2)}×")
            self.app.on_overlay_config_change(idx, scale=value)

        # All sliders of the window in one style (`ui_kit.slider`, 0.3 batch
        # 4): X/Y had a dark `accent2` fill and looked switched off next to the
        # golden size slider.
        ui_kit.slider(scale_row, pal, from_=0.5, to=2.0, variable=scale_var,
                      number_of_steps=30,
                      command=on_scale).pack(side="left", fill="x", expand=True, padx=(8, 8))

        if index == 3:
            self._build_breath_seconds_rows(inner, pal)

        ctk.CTkLabel(inner, text=tr("overlay.position"), text_color=pal["text_dim"],
                     font=ui_kit.ui(12)).pack(anchor="w", pady=(12, 4))

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
                               text_color=pal["text_faint"], anchor="w",
                               font=ui_kit.ui(12))
        x_label.pack(fill="x")

        def on_pos_x(_v, idx=index, var=pos_x_var, other=pos_y_var, label=x_label):
            value = round(float(var.get()), 1)
            label.configure(text=f"X {value:.0f}%")
            self.app.on_overlay_config_change(idx, pos=(value, other.get()))

        ui_kit.slider(sliders, pal, from_=0, to=100, variable=pos_x_var,
                      number_of_steps=100, command=on_pos_x).pack(fill="x", pady=(2, 8))

        y_label = ctk.CTkLabel(sliders, text=f"Y {cfg['pos_y']:.0f}%",
                               text_color=pal["text_faint"], anchor="w",
                               font=ui_kit.ui(12))
        y_label.pack(fill="x")

        def on_pos_y(_v, idx=index, var=pos_y_var, other=pos_x_var, label=y_label):
            value = round(float(var.get()), 1)
            label.configure(text=f"Y {value:.0f}%")
            self.app.on_overlay_config_change(idx, pos=(other.get(), value))

        ui_kit.slider(sliders, pal, from_=0, to=100, variable=pos_y_var,
                      number_of_steps=100, command=on_pos_y).pack(fill="x", pady=(2, 0))

        self._rows.append({"x_label": x_label, "y_label": y_label})

        # A secondary button of natural width (frame >= 3:1), not a frame
        # across the whole card with a contrast of 1.24:1 that looked switched
        # off.
        ui_kit.button(inner, pal, tr("overlay.test"), height=32,
                      command=lambda idx=index: self.app.test_overlay(idx)).pack(
            anchor="w", pady=(12, 0))

    def _build_breath_seconds_rows(self, parent, pal):
        """Inhale/exhale length (in seconds) - only for the Breath slot (index
        3), next to the existing Size slider."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(row, text=tr("overlay.breath_seconds"), text_color=pal["text_dim"],
                     font=ui_kit.ui(12), anchor="w").pack(anchor="w")

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
                     font=ui_kit.ui(12), anchor="w").pack(side="left")
        value_label = ctk.CTkLabel(sub, text=f"{value:.0f} s",
                                   text_color=pal["text_faint"], width=40,
                                   font=ui_kit.ui(12))
        value_label.pack(side="right")
        var = tk.DoubleVar(value=value)

        def handler(_v, var=var, label=value_label, cb=on_change):
            current = round(float(var.get()))
            label.configure(text=f"{current:.0f} s")
            cb(current)

        steps = int(BREATH_SECONDS_MAX - BREATH_SECONDS_MIN)
        ui_kit.slider(
            sub, pal, from_=BREATH_SECONDS_MIN, to=BREATH_SECONDS_MAX, variable=var,
            number_of_steps=steps,
            command=handler).pack(side="left", fill="x", expand=True, padx=(8, 8))

    def _apply_preset(self, index, x, y, pos_x_var, pos_y_var):
        pos_x_var.set(x)
        pos_y_var.set(y)
        row = self._rows[index] if index < len(self._rows) else None
        if row is not None:
            row["x_label"].configure(text=f"X {x:.0f}%")
            row["y_label"].configure(text=f"Y {y:.0f}%")
        self.app.on_overlay_config_change(index, pos=(x, y))

    def close(self):
        # THE DRAG TEST MUST END WHEN THE DIALOG CLOSES.
        #
        # Test mode turns off click-through, i.e. the visual over the game
        # swallows mouse clicks - and it never ends by itself. Whoever clicked
        # Test, closed the dialog and started the game had an unclickable area
        # in the middle of the screen and no way to find out why. Closing the
        # dialog is the last moment when the app can catch it.
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


def _qr_popis(kluc, v_navode=False):
    """Caption under the QR. Its last line sends the player to "How to pair
    your watch…" for the address - correct on the sensor card, but in the
    guide ITSELF the player would look for the button that opened this
    very window. There it is replaced by a reference to the box with the
    address at the top (`hr.qr_addr_above`). Only when the last line
    really refers to the guide - a different form of the translation stays
    whole."""
    text = tr(kluc)
    if v_navode:
        riadky = text.split("\n")
        if tr("hr.pair_button") in riadky[-1]:
            text = "\n".join(riadky[:-1] + [tr("hr.qr_addr_above")])
    return text


def watch_app_qr(parent, pal, v_navode=False, **pack_kw):
    """QR for the phone app - outwardly just a badge, the code only on a click.

    It is the same thing in two places (the step-by-step pairing guide and
    the sensor card in Settings), so it lives here and not twice. When the
    image is missing (e.g. a broken build), nothing is returned - a missing
    QR must not crash the dialog or the page. `v_navode=True` = QR in the
    pairing guide (see `_qr_popis`).
    """
    base = images_dir()
    codes = [(os.path.join(base, "qr_watch_play.png"),
              _qr_popis("hr.qr_android", v_navode)),
             (os.path.join(base, "qr_watch_appstore.png"),
              _qr_popis("hr.qr_ios", v_navode))]
    widget = ui_kit.QrReveal(parent, pal, codes, tr("hr.qr_show"),
                             tr("hr.qr_hide"))
    widget.pack(anchor="w", **(pack_kw or {"pady": (8, 0)}))
    return widget


def _stranka_vhre(app=None, tema=None):
    """Name of the "In-game" page for texts with `{page}` (0.3 batch 4b).

    In the Work world the page is called "Screen", as in the sidebar: with
    the app, `app._nazov_vhre` tells it; in the introduction (no app yet)
    the world of the theme the introduction currently has selected. Dummies
    without either -> the name from Play."""
    nazov = getattr(app, "_nazov_vhre", None)
    if callable(nazov):
        try:
            return nazov()
        except Exception:
            pass
    if tema is not None and theme_mod.theme_world(tema) == "work":
        return tr("nav.vhre_work_short")
    return tr("nav.vhre_short")


def stav_parovania(app):
    """(kind, text) of the pairing window's status row - from REAL receiving.

    Kind: "ok" (heart rate is coming), "caka" (waiting for the phone or the
    heart rate), "pozor" (something is off, but I am still trying),
    "chyba" (receiving is not running). The dialog picks the colour for the
    kind. A module function, not a dialog method, so it can be checked on
    an app dummy without Tk.

    The number is smoothed (`HeartStats.display_bpm`) - the same as on the
    HUD, on Today and at the switch, otherwise the pairing window would
    show a different number than the rest of the app. WHETHER the heart
    rate is coming is decided by the raw `_hr_last_bpm`, the same as in
    `_hr_status_display`.
    """
    stav = getattr(app, "_hr_state", "disconnected")
    port = getattr(app, "hr_port", "")
    if not getattr(app, "hr_monitoring_enabled", False):
        # The window is modal and opening it already turns receiving on, so
        # receiving being off here means a port or network error, not the
        # player's choice.
        if stav == "busy_gave_up":
            return "chyba", tr("hr.pair_status_gave_up", port=port,
                               page=_stranka_vhre(app))
        return "chyba", tr("hr.pair_status_off")
    surovy = getattr(app, "_hr_last_bpm", None)
    if stav == "connected" and surovy is not None:
        tep = getattr(getattr(app, "hr_stats", None), "display_bpm", None)
        if tep is None:
            tep = surovy
        return "ok", tr("hr.pair_status_ok", bpm=tep)
    if stav in ("linked", "connected"):
        # "connected" without a sample = the heart rate was coming and a new
        # session (`start_listening` during pairing, the first start starts it
        # by itself) has just cleared the last number. The phone is connected -
        # "waiting for it to connect" would lie.
        return "caka", tr("hr.pair_status_linked")
    if stav == "busy":
        return "pozor", tr("hr.pair_status_busy", port=port)
    if stav == "no_client":
        # After `HR_NO_CLIENT_AFTER_MS` nobody has connected - the tips are in
        # the "Watch won't connect at all?" box further down in the same
        # window.
        return "pozor", tr("hr.pair_status_no_client")
    return "caka", tr("hr.pair_status_waiting")


class WatchPairingDialog:
    """Step-by-step guide on getting the heart rate from the watch into the app.

    Why it needs its own dialog: the app does NOT receive the heart rate
    directly. It pretends to be OBS (obs-websocket v5) and relies on an app
    running on the phone that sends the heart rate to OBS - the most
    common is "HeartRateOnStream for OBS". So the player has to set up an
    OBS connection on the phone to this computer's IP, which is nearly
    impossible to guess without a guide.

    The dialog also shows the REAL IP and port of this PC (not placeholder
    examples), so the player just copies them into the phone. The IP is
    detected best-effort - if it cannot be, a tip on how to find it by hand
    is shown.

    HIDDEN IP (0.2): the address is masked (`netinfo.mask_ip`) until the
    player clicks "Show IP" - the pairing window tends to be on stream and
    in screenshots for a tester. The button toggles `app.show_ip`, which
    applies to the whole app (also the IP field in Settings and the
    journal) and only until restart.

    LIVE STATUS (0.3): under the address box there is a row that is
    redrawn every second from the real receiving state (`stav_parovania`).
    The dialog was blind before - success was visible only behind the modal
    window - and step 5 advised turning the switch on, although opening the
    guide itself had already turned receiving on (`open_watch_pairing`).
    Whoever followed the advice turned receiving off.

    `on_close` (optional) is called once, only after the window closes -
    the first-start guide starts the app tour after it.
    """

    STAV_OBNOVA_MS = 1000

    def __init__(self, app, on_close=None):
        self.app = app
        self._on_close = on_close
        self._zavrete = False
        self._stav_job = None
        pal = app.pal
        app.set_typing(True)

        self.top = ctk.CTkToplevel(app.root)
        self.top.title(tr("hr.pair_title"))
        self.top.configure(fg_color=pal["bg"])
        # The OS does not place a frameless window (DialogChrome) - without a
        # position it opened in the corner of the screen. The centre is
        # computed by the same helper as for the main window
        # (`ui_kit.vycentrovana_geometria`); on a low screen (1366x768 at
        # 125-150 %) the dialog is lower so the footer with Close stays on the
        # work area - the steps have a scrollbar.
        ui_kit.umiestni_dialog(self.top, app.root, 560, 640,
                               min_width=520, min_height=560)
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

        # panel with the real IP/port of this PC
        net = ctk.CTkFrame(scroll, fg_color=pal["surface"], corner_radius=ui_kit.RADIUS_CONTROL,
                           border_width=1, border_color=pal["accent2"])
        net.pack(fill="x", pady=(0, 8))
        net_in = ctk.CTkFrame(net, fg_color="transparent")
        net_in.pack(fill="x", padx=16, pady=14)
        ctk.CTkLabel(net_in, text=tr("hr.pair_this_pc"), font=ui_kit.ui(11),
                     text_color=pal["text_faint"], anchor="w").pack(fill="x")
        candidates = self._local_ips()
        self._candidates = candidates
        ip = candidates[0] if candidates else None
        self._ip = ip
        # VPN and virtual adapters (0.3): the physical address goes first
        # (`netinfo.local_ip_candidates`), virtual ones carry a label and under
        # the address there is a sentence when even the first one is virtual.
        self._virtualne = self._virtual_ips()
        # Windows Mobile hotspot (0.3 batch 4b): the phone can reach it, so
        # just a neutral "(hotspot)" label, no warning.
        self._hotspoty = self._hotspot_ips()
        addr_row = ctk.CTkFrame(net_in, fg_color="transparent")
        addr_row.pack(fill="x", pady=(4, 0))
        self.ip_label = ctk.CTkLabel(addr_row, text=tr("hr.pair_ip_unknown"),
                                     font=ui_kit.mono(20),
                                     text_color=pal["accent_hover"], anchor="w")
        self.ip_label.pack(side="left", fill="x", expand=True)
        self.ip_toggle = None
        self.other_ips_label = None
        self.ip_hidden_label = None
        self.ip_virtual_label = None
        if not ip:
            ctk.CTkLabel(net_in, text=tr("hr.pair_ip_help"), font=ui_kit.ui(10),
                         text_color=pal["text_faint"], wraplength=480, anchor="w",
                         justify="left").pack(fill="x", pady=(6, 0))
        else:
            # "Show IP" is packed BEFORE the address (`before=`), so it gets
            # its place in the row first. A longer address line otherwise
            # pushed it out of the window and the address then could not be
            # revealed (0.3, VPN label).
            # A secondary button, not a chip (0.3 batch 4b): a chip is only for
            # external links (↗ GitHub). Width by the longer of both texts, so
            # it does not jump on "Show IP" <-> "Hide IP".
            self.ip_toggle = ui_kit.button(
                addr_row, pal, tr("hr.ip_show"), command=self._toggle_ip,
                fit_texts=(tr("hr.ip_hide"),), height=28)
            self.ip_toggle.pack(side="right", padx=(8, 0), before=self.ip_label)
            # sentence under the hidden address - how to reveal it (only while
            # hidden)
            self.ip_hidden_label = ctk.CTkLabel(
                net_in, text=tr("hr.ip_hidden_note"), font=ui_kit.ui(10),
                text_color=pal["text_faint"], wraplength=480, anchor="w",
                justify="left")
            self._ip_hidden_after = addr_row
            if ip in self._virtualne:
                # The "(VPN/virtual)" label NOT in the address row (mono 20):
                # it did not fit there, got cut off and pushed out "Show IP".
                # It is its own small row right under the address; the sentence
                # under it says what to do about it.
                self.ip_virtual_label = ctk.CTkLabel(
                    net_in, text=tr("hr.ip_virtual"), font=ui_kit.ui(11, "bold"),
                    text_color=pal["warn"], anchor="w")
                self.ip_virtual_label.pack(fill="x", pady=(2, 0))
                self._ip_hidden_after = self.ip_virtual_label
                ctk.CTkLabel(net_in, text=tr("hr.ip_virtual_note"), font=ui_kit.ui(10),
                             text_color=pal["warn"], wraplength=480, anchor="w",
                             justify="left").pack(fill="x", pady=(6, 0))
            elif ip in self._hotspoty:
                # the same row under the address, but without the warning
                # colour and sentence
                self.ip_virtual_label = ctk.CTkLabel(
                    net_in, text=tr("hr.ip_hotspot"), font=ui_kit.ui(11, "bold"),
                    text_color=pal["text_dim"], anchor="w")
                self.ip_virtual_label.pack(fill="x", pady=(2, 0))
                self._ip_hidden_after = self.ip_virtual_label
            # A PC with Wi-Fi + Ethernet + VPN has more addresses and the app
            # does not know which one the phone is on - we show the others too,
            # so the player can choose
            if len(candidates) > 1:
                self.other_ips_label = ctk.CTkLabel(
                    net_in, text="", font=ui_kit.ui(10), text_color=pal["text_dim"],
                    wraplength=480, anchor="w", justify="left")
                self.other_ips_label.pack(fill="x", pady=(6, 0))
            ctk.CTkLabel(net_in, text=tr("hr.pair_ip_note"), font=ui_kit.ui(10),
                         text_color=pal["text_faint"], wraplength=480, anchor="w",
                         justify="left").pack(fill="x", pady=(4, 0))
        self._render_ips()

        # LIVE RECEIVING STATUS right under the address - that is where the
        # player looks while copying it into the phone, and they do not have to
        # close the window to see whether it works.
        self.status_label = ctk.CTkLabel(scroll, text="", font=ui_kit.ui(12, "bold"),
                                         anchor="w", justify="left", wraplength=500)
        self.status_label.pack(fill="x", padx=4, pady=(0, 14))
        self._obnov_stav()

        # steps; step 2 is "download the app to your phone" - that is where the
        # QR belongs, so the player does not have to type anything on the phone.
        # The QR caption here points to the address box at the top, not to "How
        # to pair your watch…" (that is this window).
        def qr_v_navode(col, pal_):
            return watch_app_qr(col, pal_, v_navode=True)

        steps = [
            (tr("hr.step1_title"), tr("hr.step1_body"), None),
            (tr("hr.step2_title"), tr("hr.step2_body"), qr_v_navode),
            (tr("hr.step3_title"), tr("hr.step3_body"), None),
            (tr("hr.step4_title"), tr("hr.step4_body"), None),
            (tr("hr.step5_title"), tr("hr.step5_body"), None),
        ]
        for i, (title, body, extra) in enumerate(steps, 1):
            self._step_row(scroll, pal, i, title, body,
                           extra=(lambda col, fn=extra: fn(col, pal)) if extra else None)

        # what if it does not work - TWO different cases, two boxes. The phone
        # not connecting at all (firewall, Public network, a different address)
        # is a different problem from "it connects, but no heart rate comes"
        # (scene/source, the watch does not measure). The tip about the
        # firewall used to be only in the second box, i.e. for the opposite
        # case.
        self._rada_box(scroll, pal, tr("hr.noconnect_title"), tr("hr.noconnect_body"))
        tb = self._rada_box(scroll, pal, tr("hr.trouble_title"), tr("hr.trouble_body"))
        # A controller with a gyro / without a dead zone reports input non-stop
        # and the app finds no pause - the same tip as the row on Today
        # (`dnes.nonstop_input`).
        ctk.CTkLabel(tb, text=tr("hr.trouble_pad"), font=ui_kit.ui(11),
                     text_color=pal["text_dim"], wraplength=470, anchor="w",
                     justify="left").pack(fill="x", pady=(8, 0))

        footer = ctk.CTkFrame(root, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=(0, 16))
        ui_kit.button(footer, pal, tr("common.close"), width=110, height=32,
                      command=self.close).pack(side="right")

    @staticmethod
    def _rada_box(parent, pal, title, body):
        """A tip box (a strip in the warn colour, heading, text). Returns the
        inner frame so another paragraph can be added to it."""
        box = ctk.CTkFrame(parent, fg_color=pal["surface"], corner_radius=ui_kit.RADIUS_CONTROL,
                           border_width=1, border_color=pal["line_soft"])
        box.pack(fill="x", pady=(6, 6))
        # height=1: an empty CTkFrame would otherwise ask for the default 200
        # px and the box had an empty band above the heading and below the
        # text. `fill="y"` stretches it to the box height, the text sets the
        # height.
        stripe = ctk.CTkFrame(box, fg_color=pal["warn"], width=3, height=1, corner_radius=0)
        stripe.pack(side="left", fill="y")
        tb = ctk.CTkFrame(box, fg_color="transparent")
        tb.pack(side="left", fill="x", expand=True, padx=14, pady=13)
        ctk.CTkLabel(tb, text=title, font=ui_kit.ui(12, "bold"),
                     text_color=pal["text"], anchor="w").pack(fill="x")
        ctk.CTkLabel(tb, text=body, font=ui_kit.ui(11),
                     text_color=pal["text_dim"], wraplength=470, anchor="w",
                     justify="left").pack(fill="x", pady=(5, 0))
        return tb

    def _obnov_stav(self):
        """Redraws the status row and schedules the next redraw in a second.

        Polling, not an event: five different paths in the app change the
        receiving state (`_apply_hr_status`, `_apply_hr_bpm`,
        `_hr_no_client`, the repeated bind...) and they do not know about
        this window. Once a second is enough - the heart rate comes at
        roughly this rhythm anyway."""
        self._stav_job = None
        if self._zavrete:
            return
        try:
            druh, text = stav_parovania(self.app)
            pal = self.app.pal
            # the error is text (12 bold) - `danger_text` (>= 4.5:1), not
            # `danger` (~3.7:1 on `bg`, the rule in theme.py)
            farba = {"ok": pal["success"], "pozor": pal["warn"],
                     "chyba": pal.get("danger_text", pal["danger"])}.get(
                         druh, pal["text_dim"])
            self.status_label.configure(text=text, text_color=farba)
            self._stav_job = self.top.after(self.STAV_OBNOVA_MS, self._obnov_stav)
        except Exception:
            pass            # the window has meanwhile gone - no next round needed

    def _step_row(self, parent, pal, number, title, body, extra=None):
        """`extra(col)` adds another element under the step text (e.g. the QR
        for the phone app) - steps without it stay plain text."""
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
        """All IPv4 addresses of this PC, the preferred one first (see netinfo).
        Connects nowhere - it only asks the OS. Without loopback and without
        169.254.x.x."""
        try:
            import netinfo
            return netinfo.local_ip_candidates()
        except Exception:
            return []

    def _virtual_ips(self):
        """Addresses of this PC on VPN / virtual adapters (`netinfo`)."""
        try:
            import netinfo
            return netinfo.virtualne_adresy()
        except Exception:
            return set()

    def _hotspot_ips(self):
        """Windows Mobile hotspot addresses (`netinfo.hotspot_adresy`)."""
        try:
            import netinfo
            return netinfo.hotspot_adresy()
        except Exception:
            return set()

    def _local_ip(self):
        """Kept for backward compatibility - the preferred address or None."""
        ips = self._local_ips()
        return ips[0] if ips else None

    def _render_ips(self):
        """Redraws the addresses by `app.show_ip` - hidden until the player
        explicitly reveals them (`netinfo` composes the texts, not this
        dialog)."""
        show = bool(getattr(self.app, "show_ip", False))
        try:
            if self._ip:
                # no VPN label here - it has its own row (`ip_virtual_label`)
                self.ip_label.configure(text=netinfo.pairing_address(
                    self._ip, self.app.hr_port, show))
            if self.other_ips_label is not None:
                self.other_ips_label.configure(text=tr(
                    "hr.pair_other_ips",
                    ips=netinfo.pairing_other_ips(
                        self._candidates[1:], show,
                        virtualne=getattr(self, "_virtualne", set()),
                        stitok=tr("hr.ip_virtual"),
                        hotspot=getattr(self, "_hotspoty", set()),
                        stitok_hotspot=tr("hr.ip_hotspot"))))
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
            pass            # the dialog was closed meanwhile

    def _toggle_ip(self):
        """Show / Hide IP - applies to the whole app, only until restart."""
        nove = not bool(getattr(self.app, "show_ip", False))
        setter = getattr(self.app, "set_show_ip", None)
        if setter is not None:
            setter(nove)
        else:
            self.app.show_ip = nove
        self._render_ips()

    def close(self):
        # It can be closed with the X, Escape and the button - but `on_close`
        # (e.g. starting the tour) may be called only once.
        if self._zavrete:
            return
        self._zavrete = True
        if self._stav_job is not None:
            try:
                self.top.after_cancel(self._stav_job)
            except Exception:
                pass
            self._stav_job = None
        self.app.set_typing(False)
        try:
            self.top.grab_release()
        except Exception:
            pass
        self.top.destroy()
        if callable(self._on_close):
            try:
                self._on_close()
            except Exception:
                # The window is already closed and the state cleaned up - the
                # caller's error must not fly up to Tk as a "pairing window
                # error".
                logging_setup.get_logger("app").exception(
                    "okno parovania: on_close zlyhal")


# --------------------------------------------------------------------------
# Slot card in the main window
# --------------------------------------------------------------------------

class SlotCard:
    CARET_ZAVRETA = "▸"   # >
    CARET_OTVORENA = "▾"  # v

    def __init__(self, app, index, data):
        self.app = app
        self.index = index
        # The four categories (slots 0-3) are fixed - the position determines
        # the category, the in-game picture and the measurement, so removing
        # them would shift texts under another category. They are turned off
        # with the switch. Only the extra slot from 0.1 (index 4+) has the
        # checkbox and ✕.
        self.removable = not je_kategoria(index)
        data = normalize_slot(data)

        # NOTE: `key_type` and `key_repr` are no longer kept here. A cue is not
        # fired by a key press, so the card had nothing to do with them - and
        # `display_key()` made a label from them that was also drawn into the
        # game under the icon.
        # In saved profiles the keys remain (settings_model.DEFAULT_SLOT), so
        # that old files do not break.
        self.mode = data["mode"]
        self.audio_path = data["audio_path"]
        self.sfx_key = data["sfx_key"]
        self.voice_edge = data["voice_edge"]
        self.voice_sapi = data["voice_sapi"]
        self.voice_path = data["voice_path"]   # own voice recording
        self.uid = data["uid"]                 # stable name for recordings
        # PER-CUE TIMING IS NO LONGER HERE.
        #
        # Its own cooldown, delay, "every N-th" and spread were read only in
        # `fire_slot`, i.e. for the Test button and a click in the HUD preview.
        # The automatic cue is fired by `_fire_somatic_cue` via `_emit`, which
        # takes only `mode`, `sfx_path` and `text` from the card. So those
        # fields set something that was never used during play - and yet they
        # looked like the app's main control.
        #
        # In saved profiles the keys remain (`settings_model.DEFAULT_SLOT`), so
        # that old files do not break; the app just no longer reads them.
        self.last_triggered = 0.0

        # Plain-python mirrors of the values - listener threads NEVER touch Tk.
        self.text_value = data["text"]
        self.enabled_value = data["enabled"]

        pal = app.pal
        self.pal = pal

        # --- Fixed grid instead of auto widths ------------------------------
        # The keycap takes its column regardless of how wide it is, so every
        # trigger's phrase starts on the same vertical line. The keycap width
        # thus still carries the input type (key / mouse / controller), but no
        # longer pushes the text beside it - that was the only thing that did
        # not match the mockup.
        #
        # Tk minsize does NOT clip a column, it only inflates it if the content
        # is wider - that is why every element in the grid has a fixed `width`.
        self.frame = ctk.CTkFrame(app.slots_container, fg_color=pal["card"],
                                  border_width=1, border_color=pal["line_soft"],
                                  corner_radius=ui_kit.RADIUS_CONTROL)
        # No side padding: the card starts and ends on the same vertical line
        # as the profiles panel above it and the Guide below it (PAGE_GUTTER).
        # With `padx=2` it stood 3 px inside - one of the "four left edges"
        # from the audit.
        self.frame.pack(fill="x", pady=5)

        grid = ctk.CTkFrame(self.frame, fg_color="transparent")
        grid.pack(fill="x", padx=16, pady=12)
        # Column 0 had 138 px for the keycap. The keycap disappeared in phase 3
        # (a cue is not fired by a key) and so did the pause column (54 px),
        # together with per-slot timing. The freed space went to the phrase -
        # the only growing column.
        #
        # Today column 0 carries three things in the order they are used: the
        # arrow for expanding, the checkbox for bulk selection and the
        # pictogram - exactly the one the player will see in game.
        COLUMNS = ((0, 92, 0), (1, 210, 1), (2, 104, 0),
                   (3, 150, 0), (4, 96, 0), (5, 40, 0))
        for index, minsize, weight in COLUMNS:
            grid.grid_columnconfigure(index, minsize=minsize, weight=weight,
                                      pad=0)

        # 0 - arrow, selection (for bulk removal), pictogram
        col0 = ctk.CTkFrame(grid, fg_color="transparent")
        col0.grid(row=0, column=0, sticky="w", padx=(0, 14))

        # The explanation exists only for the four basic cues - the player's
        # own slot does not have it, and then the arrow is not drawn at all. A
        # disabled button would promise content that does not exist.
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
            # THE SAME brush as the in-game visual
            # (`hud_paint.render_slot_icon`), not an illustrative icon: what the
            # player sees in the list, they will see in game. The visual's name
            # by slot, not by the Guide card: the card of slot 2 is "periphery"
            # (eye), but in game and in the introduction it is a hand on the
            # mouse ("release") - the list showed a different picture than the
            # game.
            # `ui_kit.SlotIcon` is redrawn on a theme change (a golden icon
            # would otherwise stay in the indigo Work world).
            vizualy = ("grounding", "jaw", "release", "breath")
            try:
                if 0 <= self.index < len(vizualy):
                    obrazok = ui_kit.SlotIcon(col0, pal, vizualy[self.index], size=26)
                else:
                    obrazok = guide_panel.sketch_or_image(
                        col0, pal, self.guide_card["id"], size=26)
                obrazok.pack(side="left")
                obrazok.bind("<Button-1>", self.toggle_detail)
                obrazok.configure(cursor="hand2")
            except Exception:
                pass
        # PHASE 3: there is no key here any more. A cue is not fired by a key
        # press, but by the body - load holding above the threshold
        # (`trigger.CueTrigger`). The card stays because it carries the
        # CONTENT: the cue text, voice, sound and visual. The app still needs
        # that; only the part that decided WHEN is gone.
        # Redrawing the whole page is phase 5.

        # 1 - phrase + timing summary below it
        text_col = ctk.CTkFrame(grid, fg_color="transparent")
        text_col.grid(row=0, column=1, sticky="ew", padx=(0, 14))
        # FIXED CATEGORY NAME above the phrase (0.3, UX audit, batch 4). The
        # player can rewrite the phrase to anything ("Ramena!" (Shoulders!)) -
        # and then the card no longer showed that it is Grounding. The slot
        # position determines the category, so the name is fixed text, not a
        # field. The extra slot from 0.1 (index 4+) has no category, nor a
        # name.
        self.category_label = None
        if je_kategoria(self.index):
            self.category_label = ctk.CTkLabel(
                text_col, text=ui_kit.bez_ikony(tr(f"overlay.slot.{self.index}")),
                font=ui_kit.ui(11), text_color=pal["text_dim"], anchor="w",
                height=16)
            self.category_label.pack(fill="x", pady=(0, 2))
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
        # Since the row only carries a changed voice, it is mostly empty - and
        # an empty label is still as tall as a line of text. So it is packed
        # only when it has something to say.
        self._sync_summary_visibility()

        # 2 - mode (voice / sound / both)
        self.mode_var = tk.StringVar(value=mode_labels()[self.mode])
        # In the card grid the dropdown may grow with the text (longer
        # translations, sound names) - a fixed width would cut the text; the
        # grid column holds it.
        self.mode_box = ui_kit.option_menu(
            grid, pal, width=104, dynamic_resizing=True,
            values=[mode_labels()[m] for m in MODE_ORDER],
            variable=self.mode_var, font=ui_kit.ui(11), command=self.on_mode_change)
        self.mode_box.grid(row=0, column=2, sticky="w", padx=(0, 14))

        # 3 - sound + microphone/file
        self.sfx_group = ctk.CTkFrame(grid, fg_color="transparent", width=150)
        self.sfx_group.grid(row=0, column=3, sticky="w", padx=(0, 14))
        self.sfx_options = sfx_dropdown_options()
        self.sfx_var = tk.StringVar(value=sfx_choice_display(self.sfx_key, self.audio_path))
        self.sfx_box = ui_kit.option_menu(
            self.sfx_group, pal, width=150, dynamic_resizing=True,
            values=[d for d, _ in self.sfx_options],
            variable=self.sfx_var, font=ui_kit.ui(11), command=self.on_sfx_choice)
        self.sfx_box.pack(side="top", fill="x")
        sfx_tools = ctk.CTkFrame(self.sfx_group, fg_color="transparent")
        sfx_tools.pack(side="top", fill="x", pady=(4, 0))
        # Secondary buttons (`ui_kit.button`): a `control_border` frame >= 3:1.
        # With `line_soft` (1.11:1) they looked switched off. The grid column
        # gives the width.
        self.rec_button = ui_kit.button(
            sfx_tools, pal, tr("slot.record_short"), width=0, height=22,
            font=ui_kit.ui(10), command=self.record_audio)
        self.rec_button.pack(side="left", fill="x", expand=True, padx=(0, 2))
        self.file_button = ui_kit.button(
            sfx_tools, pal, tr("slot.file_short"), width=0, height=22,
            font=ui_kit.ui(10), command=self.choose_file)
        self.file_button.pack(side="left", fill="x", expand=True, padx=(2, 0))

        # 4 - actions
        actions = ctk.CTkFrame(grid, fg_color="transparent")
        actions.grid(row=0, column=4, sticky="e", padx=(0, 12))
        akcie = [(tr("common.test"), self.test, False),
                 (tr("common.edit"), self.open_settings, False)]
        if self.removable:
            akcie.append(("✕", self.remove, True))
        for text, cmd, danger in akcie:
            ui_kit.button(
                actions, pal, text, kind="danger" if danger else "secondary",
                width=26 if danger else 34, height=26, font=ui_kit.ui(10),
                command=cmd).pack(side="left", padx=2)

        # 5 - on/off
        self.enabled_var = tk.BooleanVar(value=self.enabled_value)
        ui_kit.switch(grid, pal, variable=self.enabled_var,
                      command=self.on_enabled_change).grid(row=0, column=5, sticky="e")

        # --- explanation, collapsed ---
        #
        # It sits in THE SAME card as the cue, not half a page lower: "why the
        # jaw of all things" is what you ask at the jaw. The content is the
        # same as in the Guide (`guide_panel.populate_card_body`), so the two
        # places have no way to drift apart.
        self.detail_wrap = ctk.CTkFrame(self.frame, fg_color="transparent")

        self.refresh_mode_widgets()

    # ---- display ----

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
        """The line under the phrase. Since 18. 9. it carries only the voice.

        Before, a timing overview stood here (cd 30s, +2s, every 3rd), i.e.
        numbers that were not read during play. When the voice is not
        changed, there is nothing to report and the line stays empty -
        better than "default".
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
        """Dims what does not belong to the mode - but does NOT REMOVE the column.

        If an element were removed from the grid, the row would reshuffle
        and the slots would stop being aligned under each other. So it is
        only disabled and darkened.
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

    # ---- explanation ----

    @property
    def detail_open(self):
        try:
            return bool(self.detail_wrap.winfo_ismapped())
        except Exception:
            return False

    def toggle_detail(self, _event=None):
        """Expands/collapses the explanation for this cue.

        The body is built ONLY ON THE FIRST EXPAND. Four cards at once mean
        four pictograms and a few screens of text; building all of it on
        every page redraw (theme change, language change, adding a slot)
        would show up as a stutter.
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
            # The expanded arrow gets the accent colour - so in a list of
            # four cards you can see at first glance which one is open.
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

        # A DRAWER, not a continuation of the card.
        #
        # The explanation has its own surface and frame, so you can see at a
        # glance where the cue controls end and where the text about the body
        # begins. Without it the two parts merged into one tall rectangle.
        #
        # NO FRAME (0.3, UX audit): at most one level of frame - a card in a
        # card was a frame in a frame. The drawer is set apart by the
        # `surface_alt` fill and a 2 px line in `accent` along the left edge
        # (in `accent2` it could not be seen next to the fill).
        zasuvka = ctk.CTkFrame(self.detail_wrap, fg_color=pal["surface_alt"],
                               corner_radius=ui_kit.RADIUS_CONTROL, border_width=0)
        zasuvka.pack(fill="x")

        # A thin strip in the accent colour along the left edge - ties the
        # drawer to the cue above it, so it does not look like a separate card.
        pruh = ctk.CTkFrame(zasuvka, fg_color="transparent")
        pruh.pack(fill="x", padx=2, pady=2)
        ctk.CTkFrame(pruh, fg_color=pal["accent"], width=2, height=1,
                     corner_radius=0).pack(side="left", fill="y")

        vnutro = ctk.CTkFrame(pruh, fg_color="transparent")
        vnutro.pack(side="left", fill="both", expand=True, padx=(14, 14),
                    pady=12)

        head = ctk.CTkFrame(vnutro, fg_color="transparent")
        head.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(head, text=self.guide_card["title"],
                     font=ui_kit.ui(13, "bold"), text_color=pal["text"],
                     anchor="w").pack(side="left")
        # `trigger` is a description of the in-game moment (crouch, reloading,
        # aiming) - NOT a key that would fire the cue. The app no longer reads
        # keys; it stays as context, so the person knows when it typically
        # happens to them.
        ctk.CTkLabel(head, text=self.guide_card["trigger"],
                     font=ui_kit.ui(11), text_color=pal["text_faint"],
                     anchor="w").pack(side="left", padx=(12, 0))

        guide_panel.populate_card_body(vnutro, self.guide_card, pal,
                                       wraplength=620, sketch_side="left",
                                       sketch_size=104)

    # ---- events (main thread) ----

    def on_enabled_change(self):
        self.enabled_value = bool(self.enabled_var.get())
        self.app.save_settings()
        # Only enabled cues are prepared (`_slot_na_pripravu` in
        # app_audio.py): an enabled one needs preparing (outside a game at
        # once, otherwise after the game), for a disabled one the rest of a
        # running preparation is no longer sent.
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
        """Copies the chosen sound into the audio/ folder under a stable name
        and returns the new path. Keeping a foreign path "as is" would mean
        that the slot loses its sound when the original file is moved or
        deleted - and in a clean export such a reference would lead
        outside the app data (B2)."""
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
                ui_kit.notify(self.app.root, self.pal, APP_NAME,
                              tr("record.save_error", err=exc), kind="error")
                return
            self.sfx_key = "__custom__"
            self.sfx_var.set(sfx_choice_display(self.sfx_key, self.audio_path))
            if self.mode == MODE_TTS:
                self.mode = MODE_SFX
                self.mode_var.set(mode_labels()[self.mode])
                self.refresh_mode_widgets()
                # The cue no longer speaks - the same as `on_mode_change`: the
                # rest of a running preparation no longer sends its text to
                # Microsoft.
                self.app.schedule_pregenerate()
            self.app.save_settings()
            self.app.log(tr("log.slot_sfx_set", n=self.index + 1,
                            name=os.path.basename(self.audio_path)))

    def record_audio(self):
        # Name by the slot's stable uid, not by order (slot{n}.wav clashed
        # between profiles = data loss, B1).
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
                # Own recording instead of the voice: the text is no longer
                # prepared and the rest of a running preparation does not send
                # it (PRIVACY promises that).
                self.app.schedule_pregenerate()
            self.app.save_settings()
            self.app.log(tr("log.slot_recorded", n=self.index + 1,
                            name=os.path.basename(dialog.saved_path)))

    def test(self):
        self.app.fire_slot(self, ignore_cooldown=True, source="test")

    def to_dict(self):
        # `key_type`/`key_repr` are no longer written - the card does not keep
        # them and a cue is not fired by a key. `normalize_slot` fills them in
        # from `DEFAULT_SLOT` on load, so old profiles do not break.
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
        # `ui_kit.button` (0.3 batch 4b): recording is the main action of the
        # window (`primary`), not a red fill with dark text (~3:1 - `danger` is
        # only for errors and deletion, theme.py). Play is disabled until there
        # is something to play - with the single look of a disabled button.
        self.rec_btn = ui_kit.button(row, pal, tr("record.start"), kind="primary",
                                     fit_texts=(tr("record.stop"),), command=self.toggle)
        self.rec_btn.pack(side="left")
        self.preview_btn = ui_kit.button(row, pal, tr("record.preview"),
                                         state="disabled", command=self.preview)
        self.preview_btn.pack(side="left", padx=8)
        ui_kit.button(row, pal, tr("common.close"),
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
                ui_kit.notify(self.top, self.app.pal, APP_NAME,
                              tr("record.save_error", err=exc), kind="error")
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
                ui_kit.notify(self.top, self.app.pal, APP_NAME,
                              tr("record.start_error", err=exc), kind="error")
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
# Procedural background for the onboarding's "hero" intro screen - a dark
# slate gradient + a subtle smoky Enso circle (~15% opacity). Purely
# decorative - if PIL is missing or anything fails, it returns None and the
# caller uses a plain solid colour as before.
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

        # Subtle, slightly irregular Enso (Zen circle) - ~15% opacity (38/255).
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
# Onboarding wizard (first start) - choosing the visual / sound mode
# --------------------------------------------------------------------------


# Cue style (`rebrik.py`, the `cue_style` setting) and its label. The same
# sentences are in the onboarding and in Settings -> Sound, so that one
# choice does not have two names. The order is from the loudest, the same
# as `rebrik.STYLY`.
CUE_STYLE_LABELS = ((rebrik.STYL_HLAS, "ob.cue.voice"),
                    (rebrik.STYL_ZVUK, "ob.cue.sound"),
                    (rebrik.STYL_OBRAZ, "ob.cue.visual"))


class OnboardingWizard:
    """First-start guide - 5 steps, each SHOWS something or asks about one
    thing:

      1) What the app does   - real overlay pictograms (grounding/jaw/breath)
      2) What it looks like in game - HUD + pictogram over a game background
      3) Watch (optional) - why, and "Pair a watch now" (opens after the
         introduction)
      4) Main world - Play · Sumi / Work · Aizome
      5) How the app should speak up when the game winds the player up
         (cue style) + a preview based on the chosen answer, and volume

    Before, these were 3 text steps (philosophy + diagnostics + choice)
    that never showed WHAT the app is for or WHY the watch. The symptom
    diagnostics were dropped - a new player should first understand the
    product, not decide about slots before they know what it is about (by
    default all four are on).

    The visuals are GENERATED at runtime from hud_paint (pictograms, HUD) -
    no PNGs on disk, consistent with what the player will see in game, and
    not tied to a specific game (copyright).

    The interface for app.py stays: .confirmed, .choice, .volume_value,
    .diagnostics, .top. Added: .wants_pairing (whether the player clicked
    "Pair a watch now" - app opens WatchPairingDialog after the
    introduction), .cue_style (cue style from step 5; None = the player
    chose nothing and what was there stays) and .quit_requested (first
    start: the player closed the introduction and confirmed Quit).
    """

    STEP_COUNT = 5
    # The watch step. "Skip to the watch" on steps 1-2 jumps HERE: before, it
    # went straight to the world choice and bypassed exactly the step without
    # which the app stays silent. From it on there is no more skipping - the
    # rest are choices.
    KROK_HODINKY = 2

    def __init__(self, root, choice=None, volume=None, *, prvy_start=False):
        # `choice`/`volume`: the current world (theme) and volume when the
        # introduction is replayed from the command palette
        # (`replay_onboarding`). Without them the guide started on the default
        # world and 80 % - whoever just clicked through it was moved from Work
        # to Play (where cues may speak aloud) and got a different volume.
        #
        # `prvy_start=True` (only `DandurfApp.__init__`): the introduction is
        # the app's only window - closing asks about quitting and the window
        # stays on top. From the palette (the app is already running) closing
        # only cancels the introduction without changes.
        self.choice = (choice if choice in (theme_mod.ZEN, theme_mod.MODERN)
                       else theme_mod.DEFAULT_THEME)
        self.confirmed = False
        self.quit_requested = False       # first start: closed it and chose Quit
        self._prvy_start = bool(prvy_start)
        self._otazka = None               # the "Quit Zanshin?" box while it is shown
        self._otazka_od = 0.0
        self.wants_pairing = False        # clicked "Pair a watch now"?
        # Cue style from step 5. NOTHING is preselected (the author: no
        # prejudging) - whoever does not choose stays with what they had (a new
        # player on voice, as with "Not sure").
        self.cue_style = None
        self._cue_volba = None            # which of the buttons (also "Not sure")
        try:
            self.volume_value = 80 if volume is None else max(0, min(100, int(volume)))
        except (TypeError, ValueError):
            self.volume_value = 80
        # diagnostics are no longer asked - by default all slots on
        self.diagnostics = {0: True, 1: True, 2: True, 3: True}
        self._assets_ready = sfx_assets.missing_count() == 0
        self.preview_btn = None           # preview in step 5 (by answer)
        self._preview_job = None          # hiding the picture preview
        self._preview_img = None
        self._hovori = False              # the voice preview is sounding now
        self._step = 0
        # The onboarding chrome (not only the cards in step 4) should match
        # DEFAULT_THEME - before, it was hard-coded MODERN, which was invisible
        # with DEFAULT_THEME=MODERN, but after the redesign ("Sumi noc" (Sumi
        # night), DEFAULT_THEME=ZEN) the first window the player sees would
        # glow blue instead of gold.
        self._pal = theme_mod.tokens(self.choice)
        self._photos = []                 # keep references to the images (GC)

        title = tr("onboarding.welcome", app=APP_NAME)
        self.top = ctk.CTkToplevel(root)
        self.top.title(title)
        self.top.configure(fg_color=self._pal["bg"])
        # 600, not 680: the steps have different heights and at 680 almost a
        # third of the window stayed empty under the shortest of them. Besides,
        # the content is centred in the body (see `_show_step`), so the
        # difference in heights between steps no longer creates a hole above
        # the footer.
        self.top.geometry(self._centered_geometry(root, 720, 600))
        self.top._zanshin_umiestnene = True     # DialogChrome no longer moves it
        self.top.resizable(False, False)
        self.top.transient(root)
        self.top.grab_set()
        # IT CAN BE CLOSED - with the X, Esc and Alt+F4 - but not "into
        # nothing".
        #
        # Before, it could not be closed at all: the tray icon does not exist
        # yet, a frameless window has no button in the taskbar, so whoever
        # wanted to leave could only kill the process. Now on the first start
        # it asks whether to quit the app (`_on_close_request`); from the
        # palette it only cancels the introduction.
        self.top.protocol("WM_DELETE_WINDOW", self._on_close_request)
        self.top.bind("<Alt-F4>", lambda _e: (self._on_close_request(), "break")[1])
        if self._prvy_start:
            # The app's only window (the main one is hidden) and without a
            # taskbar button: after a click elsewhere it would disappear behind
            # another window and could not be found. On top only while it
            # lives - Windows dialogs (SmartScreen, UAC) come before launch or
            # on the secure desktop, and the firewall prompt only when a port
            # is opened, i.e. AFTER the introduction.
            try:
                self.top.attributes("-topmost", True)
            except Exception:
                pass

        # The same dark title bar as the main window and the other dialogs
        # (Guide, pairing) - the onboarding was the last window with a Windows
        # title bar. The X and Escape go through the same question as the OS
        # X button.
        self.chrome = ui_kit.DialogChrome(self.top, self._pal, title,
                                          on_close=self._on_close_request)
        host = self.chrome.body

        # step content + the bottom navigation bar (both into chrome.body, not
        # into top)
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
        """Geometry centred in the work area of the monitor where the cursor is.

        The calculation is shared with the main window
        (`ui_kit.vycentrovana_geometria`): before, the centre was computed
        here from the DPI of the monitor the root was on, and on two
        monitors with different scaling the guide sat off-centre. The
        scale for small screens needs no separate handling here - the app
        sets it before opening the guide (`ui_kit.umiestni_pevne_okno` in
        `DandurfApp.__init__`) and the guide is smaller than the main
        window, so where that fits, the guide fits too. If not, it stays
        stuck to the top and the title bar is within reach.
        """
        return ui_kit.vycentrovana_geometria(root, width, height)

    # ---- preparing the audio packs in the background ----

    def _prepare_assets(self):
        def progress(done, total):
            self.top.after(0, lambda: self._update_progress(done, total))
        sfx_assets.ensure_assets(progress=progress)

    def _update_progress(self, done, total):
        if total <= 0:
            return
        if done >= total:
            self._assets_ready = True
            self._refresh_preview()       # the sound preview can play now

    # ---- closing: on the first start a question about quitting ----

    # A second close request within this time after the first is THE SAME
    # key: Alt+F4 comes as a key and also as WM_DELETE_WINDOW. Without this
    # the second one would close the question again right away.
    OTAZKA_DUPLIKAT_S = 0.4

    def _on_close_request(self):
        """The X, Esc, Alt+F4. From the palette it cancels the introduction (the
        app keeps running and nothing changes). On the first start it asks:
        the introduction is the app's only window, so closing it means
        quitting Zanshin. The question hangs in the window, not in a system
        dialog: that would have Yes/No buttons and could get lost under the
        always-on-top window. A second Esc / X closes the question
        (= Continue)."""
        if not self._prvy_start:
            self._close(confirmed=False)
            return
        if self._otazka is not None:
            if time.monotonic() - self._otazka_od >= self.OTAZKA_DUPLIKAT_S:
                self._hide_quit_question()
            return
        self._show_quit_question()

    def _show_quit_question(self):
        pal = self._pal
        self._otazka_od = time.monotonic()
        # Over the whole window body (step and footer), so that nothing can be
        # clicked under the question - it is a decision, not a side note.
        cover = ctk.CTkFrame(self.chrome.body, fg_color=pal["bg"], corner_radius=0)
        cover.place(relx=0, rely=0, relwidth=1, relheight=1)
        cover.lift()
        self._otazka = cover
        inner = ctk.CTkFrame(cover, fg_color="transparent")
        inner.place(relx=0.5, rely=0.45, anchor="center")
        ctk.CTkLabel(inner, text=tr("ob.quit.title"), font=ui_kit.ui(20, "bold"),
                     text_color=pal["text"]).pack(pady=(0, 8))
        ctk.CTkLabel(inner, text=tr("ob.quit.body"), font=ui_kit.ui(12),
                     text_color=pal["text_dim"], wraplength=480,
                     justify="center").pack(pady=(0, 22))
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack()
        # `ui_kit.button` (0.3 batch 4b): the `border` frame (1.2:1) looked
        # like a disabled button - a secondary one has a `control_border` frame
        # (>= 3:1).
        ui_kit.button(row, pal, tr("ob.quit.yes"), width=130, height=38,
                      command=self._quit).pack(side="left", padx=6)
        # Continue is the safe and primary button - whoever just pressed Esc by
        # mistake continues with one click or Enter.
        dalej = ui_kit.button(row, pal, tr("ob.quit.no"), kind="primary", width=150,
                              height=38, font=ui_kit.ui(12, "bold"),
                              command=self._hide_quit_question)
        dalej.pack(side="left", padx=6)
        self.top.bind("<Return>", lambda _e: self._hide_quit_question())

    def _hide_quit_question(self):
        cover, self._otazka = self._otazka, None
        try:
            self.top.unbind("<Return>")
        except Exception:
            pass
        if cover is not None:
            try:
                cover.destroy()
            except Exception:
                pass

    def _quit(self):
        """Quit from the question: nothing is saved, the app
        (`DandurfApp.__init__`) ends and the next start shows the
        introduction again."""
        self.quit_requested = True
        self._close(confirmed=False)

    # ---- navigation ----

    def _build_footer(self):
        pal = self._pal
        # left: skip to the watch step (only on steps 1-2)
        # Footer buttons from `ui_kit.button` (0.3 batch 4b): the same kinds as
        # in every app window - Back had a `border` frame (1.2:1), so it looked
        # disabled.
        self.skip_btn = ui_kit.button(
            self.footer, pal, tr("ob.skip"), kind="quiet", width=120, height=34,
            font=ui_kit.ui(11), command=lambda: self._show_step(self.KROK_HODINKY))
        self.skip_btn.pack(side="left", padx=24)

        # progress dots
        self.dots = ctk.CTkFrame(self.footer, fg_color="transparent")
        self.dots.pack(side="left", expand=True)
        self._dot_widgets = []
        for i in range(self.STEP_COUNT):
            d = ctk.CTkFrame(self.dots, width=8, height=8, corner_radius=4,   # dot, not a control
                             fg_color=pal["surface_alt"])
            d.pack(side="left", padx=4)
            self._dot_widgets.append(d)

        # right: back + next/enter
        self.next_btn = ui_kit.button(
            self.footer, pal, tr("ob.next"), kind="primary", width=150, height=38,
            font=ui_kit.ui(12, "bold"), command=self._on_next)
        self.next_btn.pack(side="right", padx=(6, 24))
        self.back_btn = ui_kit.button(
            self.footer, pal, tr("ob.back"), width=90, height=38, command=self._on_back)
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
        self._stop_picture_preview()
        self.preview_btn = None
        for w in self.body.winfo_children():
            w.destroy()
        self._photos.clear()
        # The step content goes into a frame that is CENTRED in the body
        # (expand without fill). Before, it was packed directly into `body`, so
        # it sat stuck to the top and up to a third of the window stayed empty
        # under it - each of the four steps has a different height and a fixed
        # window height never matches them.
        inner = ctk.CTkFrame(self.body, fg_color="transparent")
        inner.pack(expand=True)
        builder = (self._step1, self._step2, self._step3, self._step4,
                   self._step5)[index]
        builder(inner)

        # navigation state
        pal = self._pal
        for i, d in enumerate(self._dot_widgets):
            d.configure(fg_color=pal["accent"] if i == index else pal["surface_alt"])
        # "Back" is HIDDEN on the first step, not greyed out - there is nowhere
        # to go and a greyed-out button looks like a broken interface
        if index == 0:
            self.back_btn.pack_forget()
        elif not self.back_btn.winfo_ismapped():
            self.back_btn.pack(side="right", padx=6)
        # From the watch step on there is nothing more to skip: on it the jump
        # would lead to the same place and after it there are only choices.
        self.skip_btn.pack_forget() if index >= self.KROK_HODINKY \
            else self.skip_btn.pack(side="left", padx=24, before=self.dots)
        last = index == self.STEP_COUNT - 1
        self.next_btn.configure(text=tr("onboarding.confirm") if last else tr("ob.next"))

    # ---- shared elements ----

    def _icon_image(self, name, size):
        """Overlay pictogram as a CTkImage (holds a reference for the GC)."""
        style = hud_paint.Style(self._pal)
        img = hud_paint.render_slot_icon(name, size, style)
        photo = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
        self._photos.append(photo)
        return photo

    def _kicker(self, parent, text, top=30):
        ctk.CTkLabel(parent, text=text, font=ui_kit.ui(10, "bold"),
                     text_color=self._pal["accent"]).pack(pady=(top, 4))

    def _heading(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=ui_kit.ui(22, "bold"),
                     text_color=self._pal["text"], justify="center",
                     wraplength=560).pack(pady=(0, 12))

    def _para(self, parent, text, width=520):
        ctk.CTkLabel(parent, text=text, font=ui_kit.ui(12),
                     text_color=self._pal["text_dim"], justify="center",
                     wraplength=width).pack(pady=(0, 4))

    # ---- STEP 1: what the app does ----

    def _step1(self, parent):
        pal = self._pal
        self._kicker(parent, tr("ob.step1.kicker"))
        self._heading(parent, tr("ob.step1.title"))

        # ALL FOUR real pictograms side by side.
        #
        # There were three here ("Uvolnenie" (Release) was missing), but the
        # app installs four triggers and the Cues tab immediately says "4" - so
        # the first screen contradicted the second. That is why the icons are
        # narrower (84 px, smaller margins), so that four fit into the window
        # width.
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
        # How it is triggered - a mechanism that was nowhere in the whole
        # introduction. It is exactly the reason why the app is not annoying:
        # nothing extra reminds you, it hangs on the keys the player presses
        # anyway.
        ctk.CTkLabel(parent, text=tr("ob.step1.how"), font=ui_kit.ui(11),
                     text_color=pal["accent"], justify="center",
                     wraplength=560).pack(pady=(10, 0))
        # What the player needs for the first heart rate (0.3, batch 4). The
        # introduction did not say it anywhere until now - and without a watch
        # and a shared network the app stays silent. A quiet line under the
        # intro, not another paragraph: it must not outshine the "how".
        ctk.CTkLabel(parent, text=tr("ob.step1.need"), font=ui_kit.ui(11),
                     text_color=pal["text_dim"], justify="center",
                     wraplength=560).pack(pady=(12, 0))

    # ---- STEP 2: what it looks like in game ----

    def _step2(self, parent):
        pal = self._pal
        self._kicker(parent, tr("ob.step2.kicker"))
        self._heading(parent, tr("ob.step2.title"))

        # preview of the "screen" - a dark surface with a grid, the HUD at the
        # bottom and a pictogram
        preview = self._build_screen_preview(parent)
        preview.pack(pady=(6, 16))

        self._para(parent, tr("ob.step2.body", page=_stranka_vhre(tema=self.choice)),
                   width=540)

        # Two questions everyone asks about this app: "will I get banned for
        # it?" and "where does my data go?". Both are answered right here, not
        # somewhere in the settings.
        for kluc in ("ob.step2.tag_safe", "ob.step2.tag_local"):
            tag = ctk.CTkFrame(parent, fg_color=pal["surface"], corner_radius=8,
                               border_width=1, border_color=pal["success"])
            tag.pack(pady=(10, 0))
            ctk.CTkLabel(tag, text="✓  " + tr(kluc), font=ui_kit.ui(10),
                         text_color=pal["success"], justify="left",
                         wraplength=520).pack(padx=14, pady=8)

    def _build_screen_preview(self, parent):
        """A small 'game window' (16:9) with a grid, HUD panel in the corner
        and one pictogram - so the player sees WHERE on the screen it
        sits."""
        pal = self._pal
        W, H = 520, 292
        canvas = tk.Canvas(parent, width=W, height=H, highlightthickness=1,
                           highlightbackground=pal["border"], bg="#0b0f17", bd=0)
        # grid
        for gx in range(0, W, W // 8):
            canvas.create_line(gx, 0, gx, H, fill="#141b26")
        for gy in range(0, H, H // 8):
            canvas.create_line(0, gy, W, gy, fill="#141b26")
        # crosshair in the middle
        cx, cy = W // 2, H // 2
        canvas.create_line(cx - 8, cy, cx + 8, cy, fill="#3a4759")
        canvas.create_line(cx, cy - 8, cx, cy + 8, fill="#3a4759")

        # HUD panel bottom left
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

        # pictogram (grounding) bottom centre
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

    # ---- STEP 3: watch ----

    def _step3(self, parent):
        pal = self._pal
        self._kicker(parent, tr("ob.step3.kicker"))
        self._heading(parent, tr("ob.step3.title"))

        # a big heart + a curve as an illustration
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
        # the second reason for the watch: session history and progress - a
        # more muted and smaller line under the main text (an addition, not a
        # second paragraph); no other picture, step 3 already has the HUD
        self.step3_body2 = ctk.CTkLabel(parent, text=tr("ob.step3.body2"),
                                        font=ui_kit.ui(11), text_color=pal["text_faint"],
                                        justify="center", wraplength=520)
        self.step3_body2.pack(pady=(6, 0))

        # ONE button, not two.
        #
        # There were "Pair now" and "Skip - I'll pair later" here, and in the
        # window footer also "Next" - three ways forward on one screen, two of
        # them the same. The footer can already skip (the step is marked as
        # optional), so only the action that cannot be done elsewhere stays
        # here.
        self.pair_btn = ctk.CTkButton(parent, width=230, height=44, corner_radius=8,
                                      font=ui_kit.ui(12, "bold"), command=self._pair_now)
        self._pair_button_look()
        self.pair_btn.pack(pady=(12, 6))
        ctk.CTkLabel(parent, text=tr("ob.step3.later_note",
                                     page=_stranka_vhre(tema=self.choice)),
                     font=ui_kit.ui(10),
                     text_color=pal["text_faint"]).pack(pady=(6, 0))

    def _pair_button_look(self):
        """The pairing button by whether the player has already chosen
        pairing - whoever comes back to this step sees that the choice
        holds."""
        pal = self._pal
        if self.wants_pairing:
            self.pair_btn.configure(
                text="✓  " + tr("ob.step3.pair_queued"), fg_color="transparent",
                border_width=1, border_color=pal["accent"],
                hover_color=pal["surface_alt"], text_color=pal["accent"])
        else:
            # no emoji (0.3 batch 4b): 🕑 was the only colourful picture on a
            # button in a quiet interface - and a clock is not a watch
            self.pair_btn.configure(
                text=tr("ob.step3.pair_now"), fg_color=pal["accent"],
                border_width=0, hover_color=pal["accent_hover"], text_color=pal["bg"])

    def _pair_now(self):
        """The player wants to pair right away - pairing opens AFTER the
        introduction (`wants_pairing`) and the introduction continues with
        the next step.

        Before, the introduction ended right here: steps 4 and 5 (world,
        volume, cue style - and the only mention of Microsoft) were not
        shown at all and the first tour did not start after pairing."""
        self.wants_pairing = True
        self._pair_button_look()
        self._show_step(self.KROK_HODINKY + 1)

    # ---- STEP 4: main world ----

    def _step4(self, parent):
        """Main world (B3-worlds): Play · Sumi or Work · Aizome.

        The look belongs to the world, so it is not chosen separately.
        `self.choice` stays the THEME KEY (interface for app.py); the app
        derives the world from it via `theme_mod.theme_world`."""
        self._kicker(parent, tr("ob.step4.kicker"))
        self._heading(parent, tr("ob.step4.title"))

        cards = ctk.CTkFrame(parent, fg_color="transparent")
        cards.pack(padx=30, pady=(4, 18), fill="x")
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)
        self._card(cards, 0, theme_mod.WORLD_THEME["play"],
                   tr("ob.world.play.title"), tr("ob.world.play.desc"))
        self._card(cards, 1, theme_mod.WORLD_THEME["work"],
                   tr("ob.world.work.title"), tr("ob.world.work.desc"))

        # NOTE: there was a "Vyskusat zvuk" (Try the sound) with volume here.
        # It played only the sound - nobody heard the voice, and step 5 asked
        # about it anyway. The preview is now at the style question
        # (`_build_preview_row`) and plays what the player chose.
        self._para(parent, tr("ob.step4.body"), width=480)
        self._select(self.choice)

    def _on_volume_slide(self):
        self.volume_value = int(self.volume_var.get())
        self.volume_label.configure(text=f"{self.volume_value} %")

    def _play_sound_preview(self):
        if not self._assets_ready:
            return
        # Always the PLAY sounds: in Work cues have no sound (B3-worlds), so
        # the only sound the player ever hears from the app is from the play
        # world.
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

    # ---- STEP 5: how the app should speak up (cue style) ----

    # Four answers in the order approved by the author. "Not sure" is
    # saved as voice: the ladder (`rebrik.py`) goes one rung lower after the
    # first objection.
    NEVIEM = "unsure"
    CUE_VOLBY = CUE_STYLE_LABELS + ((NEVIEM, "ob.cue.unsure"),)

    def _step5(self, parent):
        """Cue style (0.2). Four EQUALLY big buttons one under the other,
        nothing preselected and no "recommended" - the answer belongs to
        the player. A quiet line under them says where it can be changed
        and that the app may go quieter on its own, never louder; a second
        one says that the natural voice sends the cue texts to Microsoft
        and the Windows voice sends nothing.

        Under the answers there is a PREVIEW based on the chosen answer,
        and volume (`_build_preview_row`) - before, step 4 had only a sound
        test, nobody heard the voice and it was asked about here anyway."""
        pal = self._pal
        # A smaller margin above the kicker: step 5 is the tallest (four
        # answers, preview, two lines) and the window has a fixed height of
        # 600.
        self._kicker(parent, tr("ob.step5.kicker"), top=6)
        self._heading(parent, tr("ob.cue.title"))
        if theme_mod.theme_world(self.choice) == "work":
            # In Work the app speaks up only with a picture (B3-worlds) -
            # without this sentence the question about the voice would
            # pretend it applies there too.
            ctk.CTkLabel(parent, text=tr("ob.cue.work_note"), font=ui_kit.ui(11),
                         text_color=pal["accent"], justify="center",
                         wraplength=560).pack(pady=(0, 6))
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
            btn.pack(pady=4)
            self._cue_buttons[volba] = btn
        self._build_preview_row(parent)
        # Two quiet lines under the answers, both at the heading width (560):
        # at 480 they wrap onto more lines and the onboarding window has a
        # fixed height (600) - four buttons and the heading already take most
        # of it.
        ctk.CTkLabel(parent, text=tr("ob.cue.note"), font=ui_kit.ui(11),
                     text_color=pal["text_faint"], justify="center",
                     wraplength=560).pack(pady=(6, 0))
        # What leaves the computer with the "voice" answer - the player should
        # know it already here, not only in Settings (`data.hint` says the
        # same).
        ctk.CTkLabel(parent, text=tr("ob.cue.online_note"), font=ui_kit.ui(11),
                     text_color=pal["text_faint"], justify="center",
                     wraplength=560).pack(pady=(8, 0))
        self._oznac_styl()

    def _vyber_styl(self, volba):
        """A click on one of the four answers."""
        self._cue_volba = volba
        self.cue_style = (rebrik.STYL_HLAS if volba == self.NEVIEM
                          else rebrik.normalize_cue_style(volba))
        self._oznac_styl()

    def _oznac_styl(self):
        """The chosen answer has an accent border, the others stay unchanged."""
        pal = self._pal
        for volba, btn in getattr(self, "_cue_buttons", {}).items():
            vybrana = volba == self._cue_volba
            try:
                btn.configure(
                    border_color=pal["accent"] if vybrana else pal["border"],
                    text_color=pal["text"] if vybrana else pal["text_dim"])
            except Exception:
                pass
        self._refresh_preview()

    # ---- preview in step 5 ----

    # How many ms the picture preview stays - roughly as long as a pictogram
    # in game.
    PICTURE_PREVIEW_MS = 2600

    def _build_preview_row(self, parent):
        """The row with the preview and volume under the answers.

        It has a FIXED height and while the player has chosen nothing, it
        is empty: the preview belongs to an answer and without one there is
        nothing to show. The fixed height keeps the answers in place -
        otherwise they would jump up after the first click."""
        pal = self._pal
        row = ctk.CTkFrame(parent, fg_color="transparent", height=42)
        row.pack(fill="x", pady=(4, 0))
        row.pack_propagate(False)
        self._preview_row = ctk.CTkFrame(row, fg_color="transparent")
        # A secondary button from `ui_kit.button` (0.3 batch 4b), not an
        # `accent2` fill (that alone means nothing, theme.py); while the sounds
        # are being prepared it is disabled with the single look of a disabled
        # button. The width grows with the answer text (the voice preview has a
        # long sentence, sound and picture a short one).
        self.preview_btn = ui_kit.button(
            self._preview_row, pal, "", width=140, height=36, font=ui_kit.ui(11),
            command=self._play_preview)
        self.preview_btn.pack(side="left")
        self._volume_box = ctk.CTkFrame(self._preview_row, fg_color="transparent")
        self.volume_var = tk.IntVar(value=self.volume_value)
        # slider style as in Settings (`ui_kit.slider`), not the default
        # grey-blue from customtkinter
        ui_kit.slider(
            self._volume_box, pal, from_=0, to=100, number_of_steps=100,
            variable=self.volume_var, width=130,
            command=lambda _v: self._on_volume_slide()).pack(side="left", padx=(12, 6))
        self.volume_label = ctk.CTkLabel(self._volume_box, text=f"{self.volume_value} %",
                                         text_color=pal["text_dim"], width=44)
        self.volume_label.pack(side="left")

    def _refresh_preview(self):
        """Preview text and state by the chosen answer. "Not sure" is saved as
        voice, so the preview is voice too."""
        btn = self.preview_btn
        if btn is None:
            return
        try:
            if self._cue_volba is None:
                self._preview_row.place_forget()
                return
            hlasitost = True
            stav = "normal"
            if self.cue_style == rebrik.STYL_OBRAZ:
                text, hlasitost = tr("ob.preview.visual"), False
            elif self.cue_style == rebrik.STYL_ZVUK:
                text = tr("ob.preview.sound")
                if not self._assets_ready:
                    text, stav = tr("assets.preparing"), "disabled"
            else:
                text = tr("ob.preview.voice")
            btn.configure(text=text, state=stav)
            if hlasitost:
                self._volume_box.pack(side="left")
            else:
                self._volume_box.pack_forget()   # a picture has no volume
            self._preview_row.place(relx=0.5, rely=0.5, anchor="center")
        except Exception:
            pass                                 # the step was rebuilt meanwhile

    def _play_preview(self):
        if self.cue_style == rebrik.STYL_OBRAZ:
            self._show_picture_preview()
        elif self.cue_style == rebrik.STYL_ZVUK:
            self._play_sound_preview()
        elif self._cue_volba is not None:
            self._speak_preview()

    def _speak_preview(self):
        """Voice preview - ALWAYS the Windows voice (SAPI), which runs locally.

        The natural voice (Edge) would send the text to Microsoft and the
        introduction must not send anything anywhere: what the natural voice
        sends, the player learns only one line lower
        (`ob.cue.online_note`). That is why the button label also says it
        is the Windows voice and that the natural one sounds softer. The
        sentence is the same one the app speaks up with in game
        (`slot.default.breath`)."""
        if getattr(self, "_hovori", False):
            return                               # two previews at once = noise
        text = tr("slot.default.breath")
        hlasitost = self.volume_value
        self._hovori = True

        def povedz():
            try:
                speak_sapi_isolated(text, None, 0, hlasitost)
            except Exception:
                pass                             # without SAPI the preview stays silent
            finally:
                self._hovori = False

        threading.Thread(target=povedz, daemon=True).start()

    def _show_picture_preview(self):
        """Picture preview: the pictogram appears briefly at the bottom of the
        window and disappears - as in game at the edge of the screen.
        Grounding (slot 1), the same visual as in step 2 and the same slot
        as the sound preview; breath has no visual in `VISUAL_DRAW` (it is
        drawn by `render_breath`)."""
        self._stop_picture_preview()
        try:
            # CTk does not scale a tk image - at 150 % the pictogram would be
            # smaller than the button that shows it
            mierka = float(ctk.ScalingTracker.get_window_scaling(self.top))
        except Exception:
            mierka = 1.0
        try:
            style = hud_paint.Style(self._pal)
            ico = hud_paint.render_visual("grounding", int(150 * mierka),
                                          int(100 * mierka), style,
                                          t=0.8, label=None, ss=2)
            photo = ImageTk.PhotoImage(ico)
        except Exception:
            return
        label = tk.Label(self.body, image=photo, bd=0, bg=self._pal["bg"])
        label.image = photo                      # reference (GC)
        label.place(relx=0.5, rely=1.0, anchor="s", y=-6)
        self._preview_img = label
        self._preview_job = self.top.after(self.PICTURE_PREVIEW_MS,
                                           self._stop_picture_preview)

    def _stop_picture_preview(self):
        job, self._preview_job = self._preview_job, None
        if job is not None:
            try:
                self.top.after_cancel(job)
            except Exception:
                pass
        label, self._preview_img = self._preview_img, None
        if label is not None:
            try:
                label.destroy()
            except Exception:
                pass

    def _confirm(self):
        self._close(confirmed=True)

    def _close(self, confirmed):
        """Closes the introduction. `confirmed=False` = cancel (palette) or
        Quit on the first start - app.py then takes over nothing from the
        introduction."""
        self.confirmed = bool(confirmed)
        self._stop_picture_preview()
        try:
            self.top.grab_release()
        except Exception:
            pass
        self.top.destroy()

