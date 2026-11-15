"""Zanshin (formerly Zanshin DojoSync and Dandurf) - a mindfulness/biofeedback
assistant for playing games.

This is only the entry point - it checks the dependencies and starts the
main app (DandurfApp in app.py). The whole architecture is split into
modules:

  paths.py           - data paths (%APPDATA%), migration from older versions
  theme.py           - colour tokens of the Sumi (play) / Aizome (work) looks
  i18n.py            - interface translations (11 languages; cs/bg in
                        i18n_cs_bg.py)
  settings_model.py  - data model of slots/settings (default values,
                        normalisation, labels)
  sfx_assets.py       - built-in SFX library (synthesis and download)
  audio_engine.py     - TTS (Edge Natural + SAPI5) and playback of SFX/recordings
  gamepad.py          - controllers via pygame/SDL2; NO LONGER A TRIGGER, only a
                        second source of information on whether the player is
                        active
  game_profiles.py    - Auto-Profile Engine (detecting the running game)
  activity.py         - whether the player is doing something right now
                        (GetLastInputInfo, NO hook) and what they play with
                        (controller / keyboard)
  trigger.py          - cue state machine: arming after 90 s of load,
                        postponing to a break, silent control arm
  measure.py          - measurement windows around a cue and their validity
  data_io.py          - export/import/deletion of data (strict parser, no pickle)
  overlay.py          - in-game somatic visuals (click-through windows)
  guide_content.py,
  guide_panel.py       - the "Guide / What's behind it" panel
  ui_dialogs.py        - dialogs and cards of the main window (incl. Onboarding)
  app.py              - DandurfApp: main window, wiring everything together
  app_audio.py        - AudioMixin (part of DandurfApp): SFX library, volume,
                        voices, preparing Edge cues, playing a slot
  app_controls.py     - ControlsMixin (part of DandurfApp): command palette,
                        "not now", journal, controller and manual cue (Test)
  app_cues.py         - CuesMixin (part of DandurfApp): state of the cue
                        trigger, ladder step for the session, cue style
  app_data.py         - DataMixin (part of DandurfApp): export/import/deletion
                        of data, saving a session, sharing profiles by code
  app_history.py      - HistoryMixin (part of DandurfApp): History page
                        (trend, table, session detail, CSV export) and
                        background history analysis
  app_hud.py          - HudMixin (part of DandurfApp): HUD in game and the icon
                        row, game language, monitor, heart rate indicator,
                        in-game visuals
  app_prefs.py        - PrefsMixin (part of DandurfApp): switching language,
                        world and theme, loading/saving settings
  app_profiles.py     - ProfilesMixin (part of DandurfApp): slots, game
                        profiles and auto-profile (detecting the running game)
  app_session.py      - SessionMixin (part of DandurfApp): heart rate sensor,
                        receiving heart rate and connection state, opening a
                        measurement session
  app_spolocne.py     - names shared by app.py and its mixins (app_log,
                        language names, the "Not now" shortcut, ImageTk)
  app_today.py        - TodayMixin (part of DandurfApp): the centre (drawing)
                        and the live block of the Today page, cue delivery,
                        "My stats"

Two TTS engines:
  * "edge"  - Microsoft Edge Natural (neural voices). Cues are
              generated IN ADVANCE into a cache in audio/tts_cache/ and when
              a cue is delivered, the ready MP3 file is just played - no
              network communication or latency while playing.
  * "sapi"  - classic offline Windows SAPI5 voices.

The interface has two looks and they go with the world: Sumi for play,
Aizome for work (keys `zen` / `modern`, see `theme.WORLD_THEME`).
Switching the world recolours them at any time without a restart - the
colour tokens are in theme.py. The built-in SFX library (downloaded or
generated locally) is in sfx_assets.py.
"""

import os
import sys
import threading
import tkinter as tk
import types
from tkinter import messagebox

# DPI awareness MUST be set EVEN BEFORE importing customtkinter
# (which sets its own, weaker mode on import) and before the first Tk
# window is created - after that Windows no longer changes the
# process's mode. Without it the app on a 4K monitor with scaling gets
# misleading screen dimensions and Windows also blurs it with bitmap
# upscaling. See display.py.
import display
display.enable_dpi_awareness()

try:
    import customtkinter as ctk
except Exception as exc:  # pragma: no cover - sanity guard for a missing dependency
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Zanshin",
        "Chýba knižnica 'customtkinter', bez ktorej appka nevie zobraziť "
        "rozhranie. / Missing the 'customtkinter' library - the app can't "
        f"display its interface without it.\n\nChyba / Error: {exc}\n\n"
        "Nainštaluj ju príkazom / Install it with:\n"
        "    pip install customtkinter",
    )
    sys.exit(1)


def _install_crash_hooks():
    """Sets up writing unhandled exceptions to crash.log (main thread and
    own threads) and returns `log_crash` for Tk callbacks.

    logging_setup is light (only stdlib + paths), so we can load it
    before app without slowing down the start. Importing paths determines
    DATA_DIR (in the build %APPDATA%\\Zanshin) and migrates old data -
    exactly what the import of app would otherwise do later. The logs/
    folder is only created on the first write to the log, i.e. only AFTER
    the migration - that one is driven by whether the target folder
    already exists, so logs/ must not get ahead of it.
    """
    from logging_setup import log_crash

    # Exceptions OUTSIDE Tk on the MAIN thread (e.g. the import of app, even
    # before root is created) are caught by sys.excepthook.
    def _sys_excepthook(exc_type, exc_value, exc_tb):
        log_crash(exc_type, exc_value, exc_tb)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _sys_excepthook

    # Exceptions in OUR OWN THREADS. Since Python 3.8 they do NOT go through
    # sys.excepthook (the comment above once claimed that - it was untrue),
    # but here. The app has ~20 threads (network, audio, TTS, analysis);
    # without this a crash of any of them would leave not a byte in
    # crash.log, and in the packaged build (console=False) stderr goes
    # nowhere - the error would vanish completely without a trace.
    def _thread_excepthook(args):
        if args.exc_type is SystemExit:
            return
        log_crash(args.exc_type, args.exc_value, args.exc_traceback)

    threading.excepthook = _thread_excepthook
    return log_crash


# --- SINGLE INSTANCE OF THE APP (0.3) ---------------------------------------
#
# × only hides the app in the tray, and on Windows 11 the tray icon is
# hidden under the ^ arrow by default. Whoever did not find it there ran
# Zanshin.exe again - and the second copy failed on the Ctrl+Alt+Z
# shortcut ("another app holds it") and on the heart rate port that the
# first one holds. Until 0.3 it also SAVED, after ~24 s, the sensor as
# turned off into the shared settings, so heart rate was not received at
# the next start either. Hence a named mutex: the second copy only tells
# the first one "show the window" (a named event) and quietly exits.
# "Local\\" = within one player's login session.
_MUTEX_MENO = "Local\\Zanshin-single"
_UDALOST_MENO = "Local\\Zanshin-show"
# A bypass for development and tests that really need two copies at once.
# Under pytest the guard is skipped by itself (`PYTEST_CURRENT_TEST` is
# inherited by processes the test starts too) - otherwise a test that
# runs main.py would fail just because Zanshin happens to be running on
# the same PC.
POVOL_VIAC_KOPII = "ZANSHIN_ALLOW_MULTI"
_ERROR_ACCESS_DENIED = 5
_ERROR_ALREADY_EXISTS = 183
_EVENT_MODIFY_STATE = 0x0002
_WAIT_OBJECT_0 = 0x0
_WAIT_TIMEOUT = 0x102
_ASFW_ANY = 0xFFFFFFFF
_MB_ICONINFORMATION = 0x40
_MB_SETFOREGROUND = 0x10000
# While the process lives, the mutex handle (and the event's) is kept
# here. A handle in ctypes is just a number that closes nothing by
# itself - the mutex goes away only with the process, exactly when the
# second copy may start.
_JEDNA_KOPIA = None
# Only if importing i18n failed too - normally the text comes from
# `tray.already_running`.
_UZ_BEZI_ZALOHA = (
    "Zanshin is already running — you'll find it in the tray by the clock "
    "(if you don't see the icon, click the ^ arrow).\n\n"
    "Zanshin už beží — nájdeš ho v lište pri hodinách (ak ikonu nevidíš, "
    "klikni na šípku ^).")


def _win32():
    """kernel32 and user32 with exact types - our own WinDLL, not
    `ctypes.windll`, so that `argtypes` do not change the calls in other
    modules."""
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    u32 = ctypes.WinDLL("user32", use_last_error=True)
    for fn, args, res in (
            (k32.CreateMutexW, (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR),
             wintypes.HANDLE),
            (k32.CreateEventW, (wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL,
                                wintypes.LPCWSTR), wintypes.HANDLE),
            (k32.OpenEventW, (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR),
             wintypes.HANDLE),
            (k32.SetEvent, (wintypes.HANDLE,), wintypes.BOOL),
            (k32.CloseHandle, (wintypes.HANDLE,), wintypes.BOOL),
            (k32.WaitForSingleObject, (wintypes.HANDLE, wintypes.DWORD),
             wintypes.DWORD),
            (u32.MessageBoxW, (wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
                               wintypes.UINT), ctypes.c_int),
            (u32.AllowSetForegroundWindow, (wintypes.DWORD,), wintypes.BOOL)):
        fn.argtypes, fn.restype = args, res
    return types.SimpleNamespace(k32=k32, u32=u32,
                                 posledna_chyba=ctypes.get_last_error)


def _straz_jednej_kopie(api=None, environ=None, platforma=None):
    """First copy: returns {api, mutex, udalost} - keep until the process ends.
    Another copy already running: gives it the "show window" signal and exits
    (SystemExit 0).
    None: the guard is skipped (another OS, bypass, Windows API error).

    The guard must NEVER prevent the start - when something fails for it,
    the app starts as before 0.3. A second copy caught wrongly is less harm
    than an app that cannot be started at all.
    """
    environ = os.environ if environ is None else environ
    platforma = sys.platform if platforma is None else platforma
    if environ.get(POVOL_VIAC_KOPII) == "1" or "PYTEST_CURRENT_TEST" in environ:
        return None
    if not platforma.startswith("win"):
        return None
    try:
        api = api or _win32()
        mutex = api.k32.CreateMutexW(None, False, _MUTEX_MENO)
        chyba = api.posledna_chyba()
    except Exception:
        return None
    # ACCESS_DENIED without a handle: the mutex exists, it was just created by
    # a process with higher rights (Zanshin run as administrator). Also
    # already running.
    if chyba == _ERROR_ALREADY_EXISTS or (not mutex and chyba == _ERROR_ACCESS_DENIED):
        if not _daj_znamenie_prvej_kopii(api):
            _ukaz_uz_bezi(api)
        sys.exit(0)
    if not mutex:
        return None
    # The event right after the mutex, even before the long import of app: a
    # second copy started during loading thus finds the event and the signal
    # is not lost - an auto-reset event stays set until the first copy's
    # thread picks it up (`_cakaj_na_dalsi_start`).
    try:
        udalost = api.k32.CreateEventW(None, False, False, _UDALOST_MENO)
    except Exception:
        udalost = None
    return types.SimpleNamespace(api=api, mutex=mutex, udalost=udalost or None)


def _daj_znamenie_prvej_kopii(api):
    """Tells the running copy "show window". True if the signal worked."""
    try:
        # Only the process the player has just started may bring a window to
        # the foreground - i.e. this one. Without permission the first copy's
        # window would just flash in the taskbar behind whatever is on top.
        api.u32.AllowSetForegroundWindow(_ASFW_ANY)
    except Exception:
        pass
    try:
        handle = api.k32.OpenEventW(_EVENT_MODIFY_STATE, False, _UDALOST_MENO)
    except Exception:
        return False
    if not handle:
        return False
    try:
        return bool(api.k32.SetEvent(handle))
    except Exception:
        return False
    finally:
        try:
            api.k32.CloseHandle(handle)
        except Exception:
            pass


def _ulozeny_jazyk():
    """Language from the saved settings, None when it cannot be read safely.

    Only `json` - the app has not been loaded here yet and should not be
    for one sentence. A broken or missing file means "we don't know", not
    a crash."""
    try:
        import json
        from paths import SETTINGS_PATH
        with open(SETTINGS_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        lang = data.get("lang") if isinstance(data, dict) else None
        return lang if isinstance(lang, str) else None
    except Exception:
        return None


def _text_uz_bezi(lang=None):
    """Box text: in the player's language, otherwise English and Slovak."""
    try:
        import i18n
        if lang in i18n.LANGUAGES:
            return i18n.tr_lang(lang, "tray.already_running")
        return "%s\n\n%s" % (i18n.tr_lang(i18n.LANG_EN, "tray.already_running"),
                             i18n.tr_lang(i18n.LANG_SK, "tray.already_running"))
    except Exception:
        return _UZ_BEZI_ZALOHA


def _ukaz_uz_bezi(api):
    """The signal did not arrive (the first copy is just closing or runs with
    different rights) - at least say where to find the app. A native
    message box, not Tk: the second copy should not load the whole GUI for
    one sentence."""
    try:
        api.u32.MessageBoxW(None, _text_uz_bezi(_ulozeny_jazyk()), "Zanshin",
                            _MB_ICONINFORMATION | _MB_SETFOREGROUND)
    except Exception:
        pass


def _cakaj_na_dalsi_start(kopia, ukaz, stop, krok_ms=500):
    """Thread of the first copy: until `stop`, waits for the signal of a second
    start and on it calls `ukaz` (DandurfApp.show_window - it goes through
    ui_call itself).

    It waits in chunks of `krok_ms`, so that it stops by itself on quit and
    does not hang in an endless wait. On a handle error (WAIT_FAILED) it
    ends - spinning idly makes no sense."""
    k32 = kopia.api.k32
    while not stop.is_set():
        try:
            vysledok = k32.WaitForSingleObject(kopia.udalost, krok_ms)
        except Exception:
            return
        if vysledok == _WAIT_OBJECT_0:
            if stop.is_set():
                return
            try:
                ukaz()
            except Exception:
                from logging_setup import get_logger
                get_logger("main").exception("druhy start: okno sa neukazalo")
        elif vysledok != _WAIT_TIMEOUT:
            return


def _spusti_cakanie_na_dalsi_start(kopia, ukaz, stop):
    """Returns the thread (or None when there is nothing to wait for)."""
    if kopia is None or not getattr(kopia, "udalost", None):
        return None
    vlakno = threading.Thread(target=_cakaj_na_dalsi_start,
                              args=(kopia, ukaz, stop),
                              name="zanshin-druhy-start", daemon=True)
    vlakno.start()
    return vlakno


def main():
    # Hooks BEFORE importing app. Importing app pulls in dozens of modules
    # (audio, network, controller, TTS...) and an error in any of them - a
    # missing dependency, a typo - is exactly the one that the app without a
    # console saves nowhere: pythonw throws it away, the packaged .exe
    # (console=False) shows it only in a PyInstaller window that disappears
    # once closed. While importing app was the first line of main(), such a
    # crash did not even leave a crash.log.
    log_crash = _install_crash_hooks()
    # Single instance BEFORE importing app: the second copy has nothing to
    # load - it tells the first one "show window" and exits before it would
    # touch the port, the shortcut or the settings. Only after the hooks, so
    # that a crash in it also ends up in crash.log.
    global _JEDNA_KOPIA
    _JEDNA_KOPIA = _straz_jednej_kopie()
    from app import DandurfApp

    # Unhandled exceptions INSIDE Tk callbacks (e.g. command= on a button)
    # do not stop the mainloop and do not propagate up like a normal Python
    # exception - Tk only prints them to stderr via report_callback_exception.
    # We override it so that they are written to crash.log too.
    def _tk_callback_exception(exc_type, exc_value, exc_tb):
        log_crash(exc_type, exc_value, exc_tb)

    root = ctk.CTk()
    root.report_callback_exception = _tk_callback_exception
    # A crash in the constructor or in the mainloop is written to crash.log by
    # sys.excepthook (set above, before importing app; both Python and the
    # PyInstaller bootloader call it). Until 0.2.1 there was also a
    # try/except here with its own log_crash, so one crash was in crash.log
    # twice - as if the app had crashed twice.
    app = DandurfApp(root)
    # A second start shows this copy's window - the same path as "Show" in
    # the tray. The thread is started only now that the app is up: a signal
    # from a second start during loading waits in the event.
    stop = threading.Event()
    _spusti_cakanie_na_dalsi_start(_JEDNA_KOPIA, app.show_window, stop)
    try:
        root.mainloop()
    finally:
        stop.set()


if __name__ == "__main__":
    main()
