"""Common paths to the app's data - shared between main.py and sfx_assets.py.

Also `nahrad_subor`: the last step of an atomic write (.tmp -> target)
that survives a short file lock on Windows. It is here because this module
does not pull in any other app module - anyone can import it without a
circular import.
"""

import errno
import glob
import logging
import os
import shutil
import sys
import time

APP_NAME = "Zanshin"
IS_WINDOWS = sys.platform == "win32"

# Previous names of the app - used only to migrate existing
# settings/recordings to the new folder name in %APPDATA%.
#
# "Zanshin DojoSync" was added when renaming to plain "Zanshin": the
# qualifier "DojoSync" said nothing (syncs what with what?), and the
# clarity is carried by the sentence next to the name, not by the name
# itself. Without this record an installed app would lose its data -
# `data_dir()` looks for it under APP_NAME.
LEGACY_APP_NAMES = ["Zanshin DojoSync", "Dandurf"]


def data_dir():
    """Where we write settings, recordings, the cue cache and the SFX library.

    An installed (frozen) app may sit in Program Files, where Windows does
    not let an ordinary user write - so everything user-related goes to
    %APPDATA%\\Zanshin. When run from source, everything stays next to
    main.py, so that development does not mix with live data.
    """
    if getattr(sys, "frozen", False):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, APP_NAME)
    return os.path.dirname(os.path.abspath(__file__))


# Data files carried over when the app folder is renamed. NOT JUST the
# settings: also the WHOLE HEART RATE HISTORY - sessions (baselines,
# curves), the windows the algorithm computes the threshold from, the
# event journal and the insights. Without them the long-term data would
# be silently lost in the migration and the algorithm would start from
# zero (threshold/baseline gone).
_MIGROVANE_DATA = ["dandurf_settings.json", "hr_sessions.json", "hr_windows.json",
                   "hr_events.jsonl", "hr_insights.json"]


def _copy_data_dir(old, target):
    os.makedirs(target, exist_ok=True)
    # Every data file together with its .bak / rotation / .corrupt-*
    # siblings; we copy only when it is not in the target yet (the same
    # safeguard as before).
    subory = set()
    for meno in _MIGROVANE_DATA:
        for sib in glob.glob(os.path.join(old, meno + "*")):
            subory.add(os.path.basename(sib))
    for meno in sorted(subory):
        src = os.path.join(old, meno)
        dst = os.path.join(target, meno)
        if os.path.isfile(src) and not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
            except OSError:
                pass
    # audio/ = own SFX + voice recordings (not regenerable)
    old_audio = os.path.join(old, "audio")
    new_audio = os.path.join(target, "audio")
    if os.path.isdir(old_audio) and not os.path.isdir(new_audio):
        shutil.copytree(old_audio, new_audio)


def migrate_legacy_data(target):
    """Carries data over from an older portable version (next to the .exe)
    and from previous app names (LEGACY_APP_NAMES) to %APPDATA%\\Zanshin.

    ONLY ON THE FIRST START in the new place (there are no settings in the
    target yet). The copy from next to the .exe used to run at EVERY start
    and fill in what was missing in the target - so "Delete history" did
    not hold: at the next start the old history from next to the .exe
    came back. The old folders are not moved (copy2/copytree), so
    `legacy_data_dirs` can find them, and deleting the history
    (`data_io.delete_plan`) as well as uninstalling delete them too."""
    if not getattr(sys, "frozen", False):
        return
    try:
        if os.path.exists(os.path.join(target, "dandurf_settings.json")):
            return
        if not os.path.isdir(target):
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
            for legacy_name in LEGACY_APP_NAMES:
                legacy_dir = os.path.join(base, legacy_name)
                if os.path.isdir(legacy_dir):
                    _copy_data_dir(legacy_dir, target)
                    break
        old = os.path.dirname(sys.executable)
        if os.path.normcase(old) != os.path.normcase(target):
            _copy_data_dir(old, target)
    except Exception:
        pass


def legacy_data_dirs(target=None):
    """Old data folders that the migration may have copied from.

    %APPDATA%\\Zanshin DojoSync, %APPDATA%\\Dandurf and the folder next to
    the .exe (the old portable version) - only those that exist, and never
    `target` itself. The migration only COPIED them, so a copy of the
    heart rate history stayed in them; deleting the history therefore has
    to delete them too, otherwise "Delete" would leave a second copy. When
    run from source nothing is migrated, so there is nothing to return.
    """
    if not getattr(sys, "frozen", False):
        return []
    target = os.path.normcase(os.path.abspath(target or data_dir()))
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    kandidati = [os.path.join(base, meno) for meno in LEGACY_APP_NAMES]
    kandidati.append(os.path.dirname(sys.executable))
    von = []
    for cesta in kandidati:
        norm = os.path.normcase(os.path.abspath(cesta))
        if (os.path.isdir(cesta) and norm != target
                and norm not in (os.path.normcase(os.path.abspath(x)) for x in von)):
            von.append(cesta)
    return von


DATA_DIR = data_dir()
migrate_legacy_data(DATA_DIR)

SETTINGS_PATH = os.path.join(DATA_DIR, "dandurf_settings.json")
AUDIO_DIR = os.path.join(DATA_DIR, "audio")
TTS_CACHE_DIR = os.path.join(AUDIO_DIR, "tts_cache")
SOUNDS_DIR = os.path.join(DATA_DIR, "assets", "sounds")
VOICE_LIB_NAME = "voice_lib"


def voice_lib_dir():
    """Folder of the downloaded natural voice library (hlas_kniznica.py, the
    "Update voice" button): in the build %APPDATA%\\Zanshin\\voice_lib,
    from source next to main.py. DATA_DIR is read only at call time, so
    tests (conftest) redirect it the same way as the other paths."""
    return os.path.join(DATA_DIR, VOICE_LIB_NAME)


def images_dir():
    """Images shipped with the app (the QR for the watch app, etc.).

    The same logic as `guides_dir()` - they are part of the installation,
    not user data, so they are looked for next to the source / inside the
    packaged .exe, not in %APPDATA%. Both `.spec` files package the whole
    `assets` folder, so nothing needs to be added to the build.
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "assets", "images")


def guides_dir():
    """Folder with (temporary) illustrations for the 'Guide' panel.

    They are parts of the app shipped with the installation (not user
    data), so they are looked for next to the source / inside the packaged
    .exe, not in %APPDATA%. Put a PNG here named after the card id (e.g.
    grounding.png) so that the app uses a real illustration instead of the
    temporary vector sketch.
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "assets", "guides")


# The installer's AppId from Dandurf.iss (written there with a doubled
# brace `{{...}`, which in Inno Setup is just escaping). Inno uses it to
# create the uninstall key `<AppId>_is1`.
INSTALLER_APP_ID = "{30295CDB-462B-4151-B225-582E82027A33}"
_UNINSTALL_KEY = ("Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\"
                  + INSTALLER_APP_ID + "_is1")


def _hodnota_registra(winreg_mod, kluc, meno):
    try:
        hodnota, _typ = winreg_mod.QueryValueEx(kluc, meno)
    except OSError:
        return None
    return str(hodnota).strip() if hodnota else None


def stara_instalacia(winreg_mod=None, exe=None):
    """Is Zanshin from the 0.2 installer installed on the PC? Or None.

    WHY: 0.2 was installed with an installer (Dandurf.iss) and its
    uninstaller asks "Ponechat nastavenia...?" (Keep settings...?). On
    "Nie" (No) it deletes %APPDATA%\\Zanshin - and the ZIP version uses the
    same folder, so its history would vanish too. Returns {"location",
    "version"} from the uninstall key.

    The installer was without admin rights (HKCU); HKLM is tried just in
    case, in both registry views (64/32 bit). When it is the installed app
    itself that is running (the exe lies in its folder), there is nothing
    to warn about. A missing winreg or key is not an error - it returns
    None.
    """
    if winreg_mod is None:
        try:
            import winreg as winreg_mod
        except ImportError:
            return None
    exe = os.path.normcase(os.path.abspath(exe or sys.executable))
    citanie = getattr(winreg_mod, "KEY_READ", 0x20019)
    pokusy = (
        (getattr(winreg_mod, "HKEY_CURRENT_USER", None), 0),
        (getattr(winreg_mod, "HKEY_LOCAL_MACHINE", None),
         getattr(winreg_mod, "KEY_WOW64_64KEY", 0x0100)),
        (getattr(winreg_mod, "HKEY_LOCAL_MACHINE", None),
         getattr(winreg_mod, "KEY_WOW64_32KEY", 0x0200)),
    )
    for koren, pohlad in pokusy:
        if koren is None:
            continue
        try:
            with winreg_mod.OpenKey(koren, _UNINSTALL_KEY, 0, citanie | pohlad) as kluc:
                miesto = (_hodnota_registra(winreg_mod, kluc, "InstallLocation")
                          or _hodnota_registra(winreg_mod, kluc, "Inno Setup: App Path"))
                verzia = _hodnota_registra(winreg_mod, kluc, "DisplayVersion")
        except Exception:
            # OSError = the key is not there; anything else (a broken
            # registry) must not bring down the app start either.
            continue
        if miesto:
            priecinok = os.path.normcase(os.path.abspath(miesto)).rstrip("\\/")
            if exe == priecinok or exe.startswith(priecinok + os.sep):
                return None
        return {"location": miesto, "version": verzia}
    return None


def resolve_audio_path(path):
    """After a data move, old settings hold absolute paths to .wav files.

    If the file is no longer at the original place, we try the same name
    in the new audio/ folder - otherwise a slot would lose its recording
    after installation.
    """
    if not path or os.path.exists(path):
        return path
    candidate = os.path.join(AUDIO_DIR, os.path.basename(path))
    return candidate if os.path.exists(candidate) else path


# --------------------------------------------------------------------------
# Atomic write that survives a short file lock on Windows
# --------------------------------------------------------------------------
#
# WHY: data is written via `.tmp` + `os.replace`. Right after the write,
# though, the file gets opened for a moment by Defender, Windows Search
# indexing or sync - without FILE_SHARE_DELETE - and `os.replace` then
# fails with PermissionError: WinError 5 when they hold the target,
# WinError 32 when they hold the .tmp. In the log of a test copy (0.3)
# the settings backup failed exactly like this ("zalohu nastaveni sa
# nepodarilo zapisat" - the settings backup could not be written,
# .bak.tmp -> .bak). Such a lock lasts milliseconds, so a few short
# attempts are enough.
#
# The pauses grow and add up to 0.31 s per file. No more: `save_settings`
# runs in the GUI thread (it saves on every slider move) and replaces TWO
# files (.bak and the settings) - with both locked the window waits
# 0.62 s at once.
NAHRADA_PAUZY_S = (0.01, 0.02, 0.04, 0.08, 0.16)
# Windows codes for a temporarily held file: 5 access denied (target open
# without FILE_SHARE_DELETE), 32 file used by another process, 33 locked
# region.
_DOCASNY_ZAMOK_WIN = (5, 32, 33)
# A target that did not survive even the last attempt does not hold a
# short lock (a read-only file, open in another program). While writing
# to it keeps failing, it is tried only once, without waiting - otherwise
# while dragging a slider every save would freeze the window for
# 0.31-0.62 s (10 saves = 3 to 6 s, measured with a real lock). Full
# retrying applies again after the first success or when nobody has
# written to the target for `NAHRADA_ODDYCH_S` (the next session an hour
# later waits again).
NAHRADA_ODDYCH_S = 5.0
_zlyhane_ciele = {}         # normcase(abspath(ciel)) -> _hodiny() of the failure
_hodiny = time.monotonic    # own reference: tests replace `paths.time`

_log = logging.getLogger("zanshin.paths")


def _je_docasny_zamok(exc):
    """Does it make sense to try `os.replace` again? Only on a PermissionError
    with a held-file code. Without a Windows code (another system, an
    artificial error in a test) errno decides - EACCES yes, EPERM
    (forbidden operation) no. Another error (full disk, missing file) does
    not get better by retrying - it is raised right away."""
    if not isinstance(exc, PermissionError):
        return False
    winerror = getattr(exc, "winerror", None)
    if winerror is not None:
        return winerror in _DOCASNY_ZAMOK_WIN
    return exc.errno in (None, errno.EACCES)


def _zmaz_potichu(cesta):
    try:
        os.remove(cesta)
    except OSError:
        pass


def nahrad_subor(zdroj, ciel, uprac_zdroj=False):
    """`os.replace(zdroj, ciel)` that survives a short file lock on Windows.

    On a temporary lock (`_je_docasny_zamok`) it retries after the
    `NAHRADA_PAUZY_S` pauses. When even the last attempt fails, it raises
    the LAST error, so the caller handles it the same as the error of a
    bare `os.replace` before. Another error is raised right away, without
    waiting. A target that has just failed like this is tried only once
    while it keeps failing (`NAHRADA_ODDYCH_S`).

    `uprac_zdroj=True`: on failure it deletes `zdroj` (the caller's own
    .tmp), so no forgotten temporary file is left next to the data; a
    failure to delete is swallowed. NEVER when setting a broken file
    aside - there `zdroj` is the only copy of the data.
    """
    try:
        _nahrad_s_pokusmi(zdroj, ciel)
    except BaseException:
        if uprac_zdroj:
            _zmaz_potichu(zdroj)
        raise


def _zapamataj_zlyhanie(kluc):
    teraz = _hodiny()
    # old records out - the dict stays small even with many targets
    for k, kedy in list(_zlyhane_ciele.items()):
        if teraz - kedy >= NAHRADA_ODDYCH_S:
            _zlyhane_ciele.pop(k, None)
    _zlyhane_ciele[kluc] = teraz


def _nahrad_s_pokusmi(zdroj, ciel):
    # Only the file name and the error code go to the log, not the
    # exception text: it holds the whole path, and a path in %APPDATA%
    # carries the account name.
    meno = os.path.basename(ciel)
    kluc = os.path.normcase(os.path.abspath(ciel))
    zlyhal = _zlyhane_ciele.get(kluc)
    bez_cakania = zlyhal is not None and _hodiny() - zlyhal < NAHRADA_ODDYCH_S
    pauzy = [] if bez_cakania else list(NAHRADA_PAUZY_S)
    pokus = 1
    while True:
        try:
            os.replace(zdroj, ciel)
        except OSError as exc:
            zamok = _je_docasny_zamok(exc)
            if pauzy and zamok:
                time.sleep(pauzy.pop(0))
                pokus += 1
                continue
            if zamok:
                # even for the single no-wait try: no waiting while it fails
                _zapamataj_zlyhanie(kluc)
            if pokus > 1:
                _log.warning("nahrad_subor: %s sa nepodarilo nahradit ani na "
                             "%d. pokus (WinError %s, errno %s) - dalsie zapisy "
                             "donho skusaju len raz, kym padaju", meno, pokus,
                             getattr(exc, "winerror", None), exc.errno)
            raise
        _zlyhane_ciele.pop(kluc, None)
        if pokus > 1:
            _log.warning("nahrad_subor: %s nahradeny az na %d. pokus (subor "
                         "na chvilu drzal iny proces)", meno, pokus)
        return
