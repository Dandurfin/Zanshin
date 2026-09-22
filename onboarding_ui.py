# -*- coding: utf-8 -*-
"""
onboarding_ui.py
================

Zanshin onboarding screen (CustomTkinter) with a full pygame.mixer audio layer.

Run `generate_zen_audio.py` FIRST to create ./zen_audio/*.wav, then run this.

What it does (Task 2):
  1. Starts `zanshin_ambient.wav` on an infinite loop the moment the screen opens.
  2. A volume slider adjusts BOTH the music and the SFX volume in real time.
  3. A mute button that saves the current volume, drops output to 0, and on
     un-mute restores the exact slider value (the slider reflects the state).
  4. `koto_pluck.wav` plays on UI clicks (Mute / Begin). The three "cue" buttons
     preview the Zen trigger sounds themselves, which is their whole purpose.

Aesthetic: the app's "Sumi noc" palette — ink black + warm gold (残).
"""

import os
import customtkinter as ctk

# pygame is imported defensively so the UI still opens if audio is unavailable.
try:
    import pygame
    _PYGAME = True
except Exception:
    _PYGAME = False

# --------------------------------------------------------------------------
# Paths & palette
# --------------------------------------------------------------------------
AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zen_audio")
AMBIENT = "zanshin_ambient.wav"
SFX_FILES = {
    "koto":   "koto_pluck.wav",     # generic UI click
    "earth":  "earth_thud.wav",     # trigger: Grounded
    "temple": "temple_block.wav",   # trigger: Teeth / Jaw
    "breath": "breath_chime.wav",   # trigger: Breathe
}

ZEN = {
    "bg":          "#0D0E13",
    "surface":     "#191A22",
    "surface_alt": "#20222C",
    "border":      "#2A2B36",
    "accent":      "#D9B868",   # kin — the one gold accent
    "accent_hi":   "#E3CA8E",
    "accent2":     "#2A2620",   # dark warm fill (NOT a text color)
    "accent2_hi":  "#3A342A",
    "text":        "#ECE8E0",
    "dim":         "#9A9488",
    "faint":       "#66625A",
    "danger":      "#C1553D",
}


# --------------------------------------------------------------------------
# Audio engine — thin, safe wrapper around pygame.mixer
# --------------------------------------------------------------------------
class AudioEngine:
    """Owns the mixer, the looping ambient music and the one-shot SFX.

    Everything is guarded: if pygame is missing, the mixer fails to init, or a
    wav is absent, `available` stays False and every call becomes a no-op so the
    UI never crashes over sound.
    """

    def __init__(self):
        self.available = False
        self.sfx = {}
        if not _PYGAME:
            print("pygame not installed — running the UI without audio.")
            return
        try:
            # Match the render settings of the generated files (44.1 kHz, stereo).
            pygame.mixer.init(frequency=44_100, size=-16, channels=2, buffer=512)
        except Exception as exc:
            print("Audio device unavailable (%s) — UI runs silently." % exc)
            return

        # One-shot effects -> pygame.mixer.Sound
        for key, fname in SFX_FILES.items():
            path = os.path.join(AUDIO_DIR, fname)
            if os.path.exists(path):
                try:
                    self.sfx[key] = pygame.mixer.Sound(path)
                except Exception as exc:
                    print("Could not load %s (%s)" % (fname, exc))
        self._ambient_path = os.path.join(AUDIO_DIR, AMBIENT)
        self.available = os.path.exists(self._ambient_path) or bool(self.sfx)

    # ----- ambient (streamed, looped) -----
    def play_ambient(self):
        """Load and loop the ambient drone forever (the -1 in play())."""
        if not self.available or not os.path.exists(getattr(self, "_ambient_path", "")):
            return
        try:
            pygame.mixer.music.load(self._ambient_path)
            pygame.mixer.music.play(loops=-1)      # <- infinite loop
        except Exception as exc:
            print("Ambient playback failed (%s)" % exc)

    # ----- volume: one call drives music AND every effect -----
    def set_volume(self, level):
        """Set the effective output level (0..1) for music and all SFX."""
        if not self.available:
            return
        level = max(0.0, min(1.0, float(level)))
        try:
            pygame.mixer.music.set_volume(level)
        except Exception:
            pass
        for snd in self.sfx.values():
            snd.set_volume(level)

    # ----- one-shot -----
    def play(self, key):
        """Fire a named effect (koto / earth / temple / breath)."""
        snd = self.sfx.get(key)
        if snd is not None:
            snd.play()

    def shutdown(self):
        if self.available:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
            except Exception:
                pass


# --------------------------------------------------------------------------
# Onboarding window
# --------------------------------------------------------------------------
class OnboardingApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.audio = AudioEngine()

        # ----- volume / mute state -----
        self._volume = 0.6        # intended level the slider represents (0..1)
        self._muted = False       # when True, output is forced to 0

        # ----- window chrome -----
        ctk.set_appearance_mode("dark")
        self.title("Zanshin — Onboarding")
        self.geometry("460x640")
        self.minsize(420, 600)
        self.configure(fg_color=ZEN["bg"])

        self._build_ui()

        # Start the ambient drone AND apply the initial volume the instant we open.
        self.audio.play_ambient()
        self.audio.set_volume(self._volume)

        # Clean shutdown of the mixer when the window closes.
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------------------------------------------------------- layout
    def _build_ui(self):
        root = ctk.CTkFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=26, pady=26)

        # --- header: 残 mark, wordmark, subtitle ---
        ctk.CTkLabel(root, text="残", font=("Segoe UI", 52, "bold"),
                     text_color=ZEN["accent"]).pack(pady=(6, 0))
        ctk.CTkLabel(root, text="ZANSHIN", font=("Segoe UI", 24, "bold"),
                     text_color=ZEN["text"]).pack()
        ctk.CTkLabel(root, text="Total awareness. Settle in, and breathe.",
                     font=("Segoe UI", 13), text_color=ZEN["dim"]).pack(pady=(2, 20))

        # --- audio card: volume + mute ---
        card = ctk.CTkFrame(root, fg_color=ZEN["surface"], corner_radius=14,
                            border_width=1, border_color=ZEN["border"])
        card.pack(fill="x")

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(18, 6))
        ctk.CTkLabel(row, text="Volume", font=("Segoe UI", 13),
                     text_color=ZEN["dim"]).pack(side="left")
        self.vol_label = ctk.CTkLabel(row, text="60%", font=("Segoe UI", 13),
                                      text_color=ZEN["accent"])
        self.vol_label.pack(side="right")

        self.slider = ctk.CTkSlider(
            card, from_=0.0, to=1.0, command=self._on_volume,
            progress_color=ZEN["accent"], button_color=ZEN["accent"],
            button_hover_color=ZEN["accent_hi"], fg_color=ZEN["accent2"])
        self.slider.set(self._volume)
        self.slider.pack(fill="x", padx=18, pady=(0, 14))

        self.mute_btn = ctk.CTkButton(
            card, text="🔊  Sound on", command=self._toggle_mute,
            font=("Segoe UI", 13), height=38, corner_radius=9,
            fg_color=ZEN["accent2"], hover_color=ZEN["accent2_hi"],
            text_color=ZEN["accent_hi"], border_width=1, border_color=ZEN["border"])
        self.mute_btn.pack(fill="x", padx=18, pady=(0, 18))

        # --- "hear the cues" — previews of the Zen trigger palette (Task 1) ---
        ctk.CTkLabel(root, text="HEAR THE CUES", font=("Segoe UI", 11, "bold"),
                     text_color=ZEN["faint"]).pack(anchor="w", pady=(22, 8))
        cues = ctk.CTkFrame(root, fg_color="transparent")
        cues.pack(fill="x")
        for label, key in [("Grounded", "earth"),
                           ("Jaw", "temple"),
                           ("Breathe", "breath")]:
            ctk.CTkButton(
                cues, text=label, width=120, height=44, corner_radius=9,
                command=lambda k=key: self.audio.play(k),   # preview = its own sound
                font=("Segoe UI", 13), fg_color=ZEN["surface_alt"],
                hover_color=ZEN["accent2"], text_color=ZEN["text"],
                border_width=1, border_color=ZEN["border"]
            ).pack(side="left", expand=True, fill="x", padx=4)

        # --- primary action ---
        ctk.CTkButton(
            root, text="Begin", command=self._begin, height=46, corner_radius=10,
            font=("Segoe UI", 15, "bold"), fg_color=ZEN["accent"],
            hover_color=ZEN["accent_hi"], text_color=ZEN["bg"]
        ).pack(fill="x", pady=(30, 6))

        ctk.CTkLabel(root, text="残  ·  © 2026 Dandurfin", font=("Segoe UI", 10),
                     text_color=ZEN["faint"]).pack(side="bottom")

        if not self.audio.available:
            ctk.CTkLabel(root, text="(audio unavailable — generate zen_audio/ first)",
                         font=("Segoe UI", 10), text_color=ZEN["danger"]
                         ).pack(side="bottom", pady=(0, 4))

    # ------------------------------------------------------------- volume/mute
    def _apply_volume(self):
        """Push the *effective* level (0 while muted) to the audio engine."""
        self.audio.set_volume(0.0 if self._muted else self._volume)

    def _update_vol_label(self):
        self.vol_label.configure(text="%d%%" % round(self._volume * 100))

    def _on_volume(self, value):
        """Slider moved — update the intended volume live (and un-mute)."""
        self._volume = float(value)
        if self._muted:                 # touching the slider naturally un-mutes
            self._muted = False
            self._refresh_mute_btn()
        self._update_vol_label()
        self._apply_volume()

    def _toggle_mute(self):
        """Mute saves the level and silences; un-mute restores the exact state.

        The click sound is always played while audio is live, so both actions
        give feedback: on mute we click *then* silence; on un-mute we restore
        *then* click.
        """
        if self._muted:
            # UN-MUTE: restore the saved volume, reflect it on the slider, click.
            self._muted = False
            self.slider.set(self._volume)          # slider mirrors restored state
            self._update_vol_label()
            self._refresh_mute_btn()
            self._apply_volume()
            self.audio.play("koto")
        else:
            # MUTE: click while still audible, then drop to 0 (slider keeps value).
            self.audio.play("koto")
            self._muted = True
            self._refresh_mute_btn()
            self._apply_volume()

    def _refresh_mute_btn(self):
        if self._muted:
            self.mute_btn.configure(text="🔇  Muted", text_color=ZEN["danger"])
        else:
            self.mute_btn.configure(text="🔊  Sound on", text_color=ZEN["accent_hi"])

    # ------------------------------------------------------------------ actions
    def _begin(self):
        self.audio.play("koto")         # UI click
        # (Onboarding would advance here; for this demo we simply close.)
        self._on_close()

    def _on_close(self):
        self.audio.shutdown()
        self.destroy()


if __name__ == "__main__":
    OnboardingApp().mainloop()
