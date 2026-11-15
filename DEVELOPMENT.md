# Developing Zanshin

This page is for people who run Zanshin from source, run its tests or change
the code. To play, the [README](README.md) is enough.

## Run from source

In the folder with `main.py`:

```bash
py -m pip install -r requirements.txt
py main.py
```

It needs Windows and should run on Python 3.10 or newer (I found nothing in
the code that needs a newer one), but I only test 3.14. Run this way, the app
keeps its data next to `main.py`, separate from the built app's
`%APPDATA%\Zanshin`.

`requirements.txt` gives one library a minimum version: `edge-tts>=7.3.1`,
the library behind the natural voice. Since about November 2026 Microsoft
refuses versions older than the minimum (HTTP 403), and the natural voice then
can't prepare any new line. There is deliberately no upper cap: when
Microsoft changes something again, the fix may come in a new major version,
and a cap would keep exactly that fix out. Instead, a new version is tried
before it's used: every build checks that Zanshin can still call it and has
it say one test word (see *What build.bat does*), and **Update voice** in the
app tries every version it downloads. If you installed the requirements
before, run the same `pip install` again: if your `edge-tts` is older than
the minimum, pip updates it (and a library it uses, only if the new version
needs a newer one) and leaves the other packages as they are. Nothing updates
it later on its own when you run from source;
`py -m pip install --upgrade "edge-tts>=7.3.1"` fetches the newest one, which
is what every build does. `check_before_run.py` and `build_all.ps1` read the
minimum from that line, so no script repeats it. The documents that name it,
this page included, are checked against it by `tests/test_022g_dokumenty.py`,
so after changing it, that test tells you which sentence to update.

*Not released yet (0.2.2):* **Update voice** (Settings → Sound, under *Voice
source*) works from source too. It puts the downloaded `edge-tts` into
`voice_lib\` next to `main.py` (git ignores that folder; the built app uses
`%APPDATA%\Zanshin\voice_lib`), and every start prefers it over the
pip-installed `edge-tts` as long as it's newer. Delete the folder, or install
the same or a newer `edge-tts` with pip, to go back to the installed one.

*Not released yet (0.2.2):* only one copy runs at a time, and a source run
counts as the same app as the built one: starting it again only shows the
window of the copy already running. To run two copies anyway (for testing),
set the environment variable `ZANSHIN_ALLOW_MULTI=1`.

## Tests

With the app's dependencies installed (see above), install the developer
tools first — `requirements-dev.txt` holds pytest and pyflakes — then run the
tests:

```bash
py -m pip install -r requirements-dev.txt
py -m pytest tests/
```

Run from source, the app's data folder is the repository folder itself.
So that a test run can't write next to your own settings and history,
`tests/conftest.py` points the data folder and the log (`app.log`,
`crash.log`) at a temporary folder for the whole run and deletes it at the
end; a test that needs a folder of its own still makes one. The app's own
lookup of its data folder doesn't change.

No test goes to the network. The tests of **Update voice**
(`tests/test_022h_hlas_kniznica.py`, `tests/test_022h_aktualizuj_hlas.py`)
make the download and the test word fail unless a test hands them a local
fake; `tests/test_022g_hlas_edge_tts.py` runs the build's `edge-tts` block in
the real `powershell.exe` with a fake pip and a fake `edge_tts`; and
`tests/test_022h_build_spec.py` runs `Dandurf.spec` with a fake PyInstaller
and checks its list of extra modules (see *What build.bat does*) against the
installed `edge-tts`, read with `ast` only.

Other developer scripts, run by hand from the repository folder. None of them
is part of the built app:

- `check_before_run.py` — checks what can be checked without opening a
  window: every module parses, every text has all 11 languages (none empty,
  same `{placeholders}`; a text still left in English only gets a note), the
  main window calls no method or colour token that doesn't exist, no
  keyboard hook or Steam code has come back, and the installed `edge-tts` is
  at least the minimum in `requirements.txt`. An older or missing `edge-tts`
  only gets a note, because the app still runs with the Windows voice (a build
  never gets this far with one: it installs or updates `edge-tts` first, or
  stops, see below); a `requirements.txt` without that minimum is an error.
  A cap on `edge-tts` there (one the build suggests as a temporary way back,
  see below) only gets a note, so it isn't forgotten. With pyflakes installed
  (the developer tools above) it also looks for undefined names; without it, it
  skips that check and says so. `build_all.ps1` runs it before every build but
  doesn't install pyflakes, so unless you already have it, a build skips the
  undefined-names check.
- `check_translations.py` — missing languages, mismatched `{placeholders}` and
  empty strings in the translations; exits with an error if it finds any.
- `make_translation_todo.py` — writes `preklad_TODO.csv`, the strings still
  waiting for a translation (it finds them where Japanese, Chinese, Russian or
  Bulgarian is still the English text).
- `check_sources.py` — opens the three study links shown in the Guide and
  reports the dead ones; it doesn't check the longer list in `ZDROJE.md`. It
  needs the internet and contacts each linked site. If no site answers and
  every link fails on the network (name lookup, unreachable network or a
  timeout), it says you're offline, checks nothing and exits with 0 instead of
  reporting the links as dead.
- `simulate.py` — plays synthetic evenings through the app's own heart-rate,
  activity, trigger and measurement code and says what the cues would have
  done. It checks the mechanism, not whether the thresholds fit your body. Its
  evenings are tidier than real ones: one heart-rate reading a second with no
  gaps (a real watch sends less often and drops some), and the pauses in your
  input are the script's assumption, not a measurement.
- `prepocitaj_okna.py` — re-checks measurement windows that were already
  saved against today's rule on whether you were at the keyboard. That's the
  one rule it can check from what's saved; rules that need the raw heart-rate
  samples stay as they were. **It rewrites the saved `hr_windows.json`** next
  to `main.py` (the data of Zanshin run from source, not of the built app); a
  backup copy goes next to it first, and `--nahlad` only previews. Nothing is
  deleted: a window that no longer passes is marked invalid, with the reason.

### Scripts that test the real window

The repository also holds three developer scripts that test the real window:
`gui_harness_auto.py`, `gui_harness_onboarding.py` and `gui_screenshots.py`.
You start them by hand, with Zanshin closed. The first two use the real mouse
(move, click, drag, scroll) and press Escape, so leave the PC alone while they
run. All three take screenshots of the app's own windows and pictures, with a
small margin around them (`gui_screenshots.py --okno`: the window alone), into
`logs\` by default. None of them is part of the
built app: the build packs `main.py`, the modules it imports and the `assets`
folder, and nothing imports these scripts.

While they run, they change the data of Zanshin run from source next to
`main.py` (not the built app's data in `%APPDATA%\Zanshin`), and they put the
originals back at the end:

- `gui_harness_onboarding.py` deletes the settings (`dandurf_settings.json`)
  for the run, so the app starts as on a first start.
- `gui_harness_auto.py` changes the settings for a while and puts the
  heart-rate history (`hr_sessions.json`, `hr_insights.json`, the copy of a
  running session, `hr_session_open.json`, and sessions that couldn't be
  saved, `hr_session_pending.json`) aside for part of the run. Before
  its first change it copies these files to disk next to the originals
  (`*.pred-harnessom`) and puts them back after an interruption too (Ctrl+C, a
  closed window, a crash). If the process is killed hard, the next run puts
  them back right at its start; a file it finds in their place that differs
  from the backup isn't overwritten but kept next to it as
  `*.pred-obnovou-<time>`.
- `gui_screenshots.py` overwrites the settings and the heart-rate history
  (synthetic history, the other theme) and puts them back, after a crash too,
  including `hr_session_open.json` and `hr_session_pending.json`, which the
  app would otherwise add to the history at its start and delete. It doesn't
  touch the mouse or the keyboard.

`gui_screenshots.py` takes these options:

```bash
py gui_screenshots.py                    # into logs\gui_screenshots
py gui_screenshots.py C:\some\folder     # somewhere else
py gui_screenshots.py --lang en          # the whole run in one app language
py gui_screenshots.py --okno             # only the app's window, no desktop
```

`--lang` takes a language code (`sk`, `en`, `ja`, …); the German and Japanese
steps then return to it instead of to Slovak. `--okno` (or `--window`)
captures only the app's own window by its handle, so no desktop, taskbar or
other window ends up in the shot, even one lying on top. It also saves
`17_relacia_zblizka.png`, the History panel *One session up close* on its
own. The synthetic sessions start between 18:00 and 23:00, and each one's
cue count matches the triangles in its curve. The shots carry no metadata.
The README images come from
`py gui_screenshots.py --lang en --okno`, run in a copy of the repository:
`docs/img/today.webp` is `01_dnes.png` saved as WebP, and
`docs/img/history-session.png` is `17_relacia_zblizka.png`. The script needs
a settings file where the introduction is already done; without one, the
app opens the introduction first and waits for it.

## What build.bat does

Players only need to double-click `build.bat` (see *Install* in the README).
This is what it does. It runs `build_all.ps1`, which you can also start
directly:

```powershell
powershell -ExecutionPolicy Bypass -File "build_all.ps1"
```

The script (1) checks/installs Python deps and PyInstaller, runs
`pip install --upgrade` on every build for the `edge-tts` line of
`requirements.txt` alone, so the build gets the newest `edge-tts` (pip
touches a library `edge-tts` uses only if the new version needs a newer
one), then asks the package index once more with `--dry-run`, because
pip also succeeds offline when the installed version fits. If pip or that
check fails, the build goes on with the installed `edge-tts` only if it's at
least the minimum there, with a yellow warning, and stops otherwise. Then it
tries the new `edge-tts`. Without the network (online and offline alike) it
imports it and builds `Communicate("Zanshin", "en-GB-SoniaNeural",
rate="+0%")` the way `audio_engine.py` does, and checks that `save` is async;
if that fails, the build stops with **CHYBA:**, a one-line reason and the way
back: the `requirements.txt` line to set, with a cap below the broken
version (`edge-tts>=7.3.1,<8` when 8.0 breaks it, `<7.4.0` when 7.4.0 does),
plus the pip command for running from source. That line matters
because the build upgrades `edge-tts` every time, so a pip command alone
would be undone by the next build. If even the minimum fails, it suggests
`--force-reinstall` of that version instead. The log names the `edge-tts`
version that goes into the build. Online (when the index check worked) it
then has it say one test word, "Zanshin", through Microsoft into a temporary
`%TEMP%\zanshin-edge-tts-<random>.mp3` that is always deleted: a green line
if it works; if Microsoft refuses it or doesn't answer, a loud yellow
warning, and the build goes on, because the exe still works with the Windows
voice and **Update voice** or a later build can repair it. Offline a yellow
note says the test word was skipped. It also draws
`Dandurf.ico` if it's missing, and runs `check_before_run.py` — if that finds
a problem, nothing is built; (2) force-closes a running Zanshin without asking
(Windows locks a running `.exe`), deletes the old `dist\Zanshin\` and packages
the app into `dist\` (onedir, no admin manifest, UPX off). From 0.2.2
`Dandurf.spec` packs a little more than today's `edge-tts` needs, because the
exe's Python only has the modules PyInstaller saw at build time and a newer
`edge-tts` from **Update voice** may import more: the libraries `edge-tts`
depends on, whole and with their version metadata (aiohttp with
aiohappyeyeballs, aiosignal, attrs, frozenlist, multidict, propcache, yarl
and idna; tabulate, typing_extensions and certifi), without aiohttp's test
modules (they would pull in pytest) and without `__main__` modules, plus a
list of standard-library modules. A package that isn't installed is skipped.
I estimate under 2 MB more, but haven't measured it. A newer `edge-tts` that
needs something outside that list is refused by the app as needing a newer
Zanshin. And (3) the script assembles
an installer with Inno Setup 6 into `installer\`, but only if Inno Setup 6 is
installed. I don't publish an installer (see *Install* in the README); without
Inno Setup the app in `dist\Zanshin\` is ready as it is.

## Project structure

| File | Purpose |
|---|---|
| `main.py` | Entry point — makes the app DPI-aware, checks that `customtkinter` is installed, sets up crash logging, lets only one copy run (a second start shows the running copy's window) and starts `app.DandurfApp` |
| `app.py` | Main window, wiring for the whole app |
| `app_audio.py` | Part of the main window (a mixin of `DandurfApp`): preparing the built-in sound library, volume and the sound / voice balance, choosing the voice and its source, preparing the natural voice ahead of time, the **Update voice** button (its worker thread, the status line and the line in the log; the work itself is in `hlas_kniznica.py`), and playing a cue's sound, voice or your own recording |
| `app_controls.py` | Part of the main window (a mixin of `DandurfApp`): the command palette (Ctrl+K), "not now" (pausing cues from the shortcut or the tray menu), the collapsible log, gamepad activity, the manual test cue and showing the introduction again |
| `app_cues.py` | Part of the main window (a mixin of `DandurfApp`): the automatic cue's state shown in the breathing band and on "Today", the "last cue" line, the share of silent cues and the cue ladder step for a new session, and choosing how the app speaks up (cue style) |
| `app_data.py` | Part of the main window (a mixin of `DandurfApp`): export / import / delete of your data (the whole history or one session), opening the data folder, the Data and About panels, what is saved when a session ends and the questions after it (and finishing questions still open when Zanshin quits or Windows shuts down), setting aside a session that couldn't be saved (`hr_session_pending.json`) and adding it back, sharing a profile as a code, and removing extra cue slots (one or several) |
| `app_history.py` | Part of the main window (a mixin of `DandurfApp`): the "History" page — the trend chart with its metric and period controls, the sessions table, the days-played grid and the detail of one session, the "which cue works" chart, exporting sessions to a spreadsheet (CSV), and the background analysis behind the insights |
| `app_hud.py` | Part of the main window (a mixin of `DandurfApp`): the on-screen heart-rate panel (HUD) and its row of 4 icons, the language of what the app draws into the game, choosing the monitor, the heart-rate indicator in the sidebar, pairing the watch, and setting up and showing the in-game pictures |
| `app_prefs.py` | Part of the main window (a mixin of `DandurfApp`): switching language, world (play / work) and theme; loading and saving your settings (with their backup), volume and balance; choosing the "not now" shortcut |
| `app_profiles.py` | Part of the main window (a mixin of `DandurfApp`): the cue slots of the active profile, game profiles (switching, creating, deleting) and the auto-profile (switching to a game's profile while that game runs) |
| `app_session.py` | Part of the main window (a mixin of `DandurfApp`): heart-rate receiving (its settings, turning it on and off, receiving heart rate, steps and connection state, dropouts, a busy port (TCP is retried, a UDP port that won't open is reported), hiding this PC's IP on screen), opening a measuring session with its thresholds, splitting it when the PC slept, and the regular ticks: four times a second whether you're at the keyboard (which also drives the cue trigger), once a second the "last cue" line |
| `app_spolocne.py` | Names shared by `app.py` and its mixins (the app logger, language names for the switch, the "not now" shortcut defaults, PIL's `ImageTk`), and the name of the *In-game* page in the current world for texts with `{page}` (`stranka_vhre`), with refreshing such texts after a world switch |
| `app_today.py` | Part of the main window (a mixin of `DandurfApp`): the "Today" page — drawing its animated centre, the live heart-rate, load and session block, delivering the automatic cue, and the "My stats" cards (choosing them, their values, swapping them by dragging) |
| `paths.py` | Where data lives (`%APPDATA%\Zanshin` for the built app, next to `main.py` from source); the built app also copies data over from older versions. Also `nahrad_subor`, the last step of a safe save (`.tmp` → the real file): while Windows or an antivirus holds the file for a moment, it tries again for about 0.3 s, and on failure it can delete the caller's `.tmp`. The saves in `app_prefs.py`, `data_io.py`, `hr_stats.py`, `hr_insights.py`, `audio_engine.py` and `hlas_kniznica.py` go through it, not through a bare `os.replace` (a test checks that); `paths.py` imports no other module of the app, so any module can use it. From 0.2.2 also `voice_lib_dir()`, the folder for the `edge-tts` that **Update voice** downloads (`voice_lib` in the data folder) |
| `settings_model.py` | Slot/settings data model — defaults, normalisation |
| `audio_engine.py` | Text-to-speech (the natural voice through Edge, the Windows voice through SAPI5) and sound/recording playback; at start it prefers a newer `edge-tts` downloaded by **Update voice** over the bundled one, and swaps the module while the app runs once an update worked |
| `hlas_kniznica.py` | **Update voice** (from 0.2.2), only on click and never while watching: asks PyPI for the newest `edge-tts`, downloads that one wheel from `files.pythonhosted.org`, verifies it (HTTPS and the host, size and SHA-256 from PyPI, the zip entry by entry, only `edge_tts/*.py` written, the code read with `ast`, dependencies already in the app), loads it (under a private module name, because the bundled one is already loaded) with a loader that checks each file's SHA-256, tries the API and one test word, and keeps it only if that works (`manifest.json` in `voice_lib`); at start it loads a valid downloaded version that's newer than the bundled one. Touches no Tk; call `aktualizuj` from a worker thread |
| `theme.py` | Colour tokens for the Sumi / Aizome themes; its docstring states the design rules (on and selected = accent, contrast minimums, red only for errors and deleting) |
| `i18n.py` | UI translations (11 languages; Czech and Bulgarian in `i18n_cs_bg.py`) |
| `sfx_assets.py` | Built-in sound library — copies the bundled sounds; download or synthesis only if one is missing |
| `heart_rate.py` | Receiver for heart rate and steps from a companion app — TCP and UDP (OSC included), on port `4455` by default, on every network unless you pick one of this PC's own addresses |
| `obs_websocket.py` | Minimal obs-websocket v5 server — what *HeartRateOnStream for OBS* writes your heart rate to |
| `netinfo.py` | This PC's local IP addresses for pairing, hidden on screen until *Show IP*; real adapters first, VPN and virtual ones marked, Windows' Mobile hotspot marked as a hotspot, and a Hyper-V external switch that carries the home network counted as real |
| `activity.py` | Whether the player is active (`GetLastInputInfo`, **no hook**) |
| `gamepad.py` | Controller activity through SDL (`pygame`) — only "the player is active"; which button is never stored |
| `hotkey.py` | The one global shortcut, "not now" (`RegisterHotKey`, not a hook), its presets, whether one would type a letter on an installed keyboard layout, key names as the app language writes them (German *Strg*, *Umschalt*) and Windows' registration result, also when it comes after the 2-second wait (`on_result`) |
| `game_profiles.py` | Auto-profile — compares running process names with the known games (only while that switch is on) |
| `trigger.py` | Cue state machine — draw, defer to a pause, silent arm |
| `rebrik.py` | Cue ladder — voice → picture → pause, set per session from your feedback |
| `measure.py` | Measurement windows around a cue and their validity |
| `hr_stats.py` | Resting baseline, strain index, session summaries & history |
| `hr_insights.py` | Patterns across sessions — hedged notes, not diagnoses |
| `data_io.py` | Export / import / delete — strict parser (50 MB cap, UTF-8 only, NaN/Infinity rejected, every field checked), no pickle |
| `overlay.py`, `hud.py`, `hud_paint.py` | In-game pictures and the heart-rate panel (PIL rendering) |
| `layer_window.py` | The click-through, see-through window (`UpdateLayeredWindow`) every in-game picture is drawn in |
| `display.py` | Monitors, DPI awareness, which screen to draw on, and fitting the window to the screen |
| `ui_shell.py`, `ui_dialogs.py` | Main-window shell (sidebar, title bar, state dot), dialogs, onboarding |
| `ui_kit.py` | Building blocks of the main window — switches, buttons (one disabled look for every kind), sliders, option menus, panels, empty states, the in-app message, confirm and choice dialogs with their border, dialog placement, the main switch and its breathing band, keycaps, stat cards, charts, dates and durations in the app language (`datum_text`, `cas_text`), and Japanese / Chinese line breaking for every wrapped label |
| `theme_recolor.py` | Recolours the open window when the theme changes, without rebuilding it |
| `color_picker.py` | The app's own colour picker (no eyedropper — it would have to capture the screen) |
| `guided_tour.py` | The guided tour of the window after onboarding |
| `guide_content.py`, `guide_panel.py` | The Guide — per-cue notes, philosophy and source list |
| `background.py` | The dojo backdrop and the "Today" hero |
| `make_icon.py` | Draws the ensō — the `Dandurf.ico` icon, and the tray mark while the app runs |
| `logging_setup.py` | Local log files (`app.log`, `crash.log`) — no remote crash reporting |
| `Dandurf.spec`, `build.bat`, `build_all.ps1`, `Dandurf.iss` | PyInstaller + Inno Setup build; the spec also packs the extra modules a downloaded `edge-tts` may need (see *What build.bat does*) |

### How the main window is split

Up to version 0.2, the whole main window was one class in one file of
almost 9,000 lines. Since 0.2.1 it is split by topic, and nothing about how the
app behaves has changed. `DandurfApp` is still a single class, but most of its
methods live in the `app_*.py` modules above as *mixins* that `DandurfApp`
inherits. A few rules keep it that way:

- **State lives on `DandurfApp`.** `DandurfApp.__init__` in `app.py` sets most
  of it up, including the window and its pages. A few things are only created
  the first time they're needed (the "not now" timer, for example, or the
  *My stats* picker), and the code reads those with
  `getattr(self, name, None)`. A mixin has no `__init__` and no data of its
  own; its methods use `self` exactly as they did in the single file.
- **Imports go one way.** `app.py` imports the `app_*.py` modules; an
  `app_*.py` never imports `app`, because that would be a circular import.
  Names that `app.py` and the mixins both need live in `app_spolocne.py` and
  stay importable from `app` too.
- **Each method exists once.** A new method goes into the module whose topic
  it belongs to (shared helpers stay in `app.py`). Two mixins must never
  define the same name, because one would silently hide the other.
- **Tests read the app's source through `tests/_zdroj_appky.py`.** Some tests
  read the code as text, for example "there is no keyboard hook" or "the IP
  address is masked in the log". This helper gives them `app.py` together with
  every `app_*.py`, so a new module is covered automatically and such a check
  can't pass just because the code moved to another file. The helper joins the
  files into one source, so an `app_*.py` must not use
  `from __future__ import ...`.
- **A test that replaces a module-level name must replace it in the module
  where the method now lives.** For example, a test that swaps out
  `threading` for a method in `app_today.py` has to patch `app_today`, not
  only `app`.

## Texts, translations and the docs

- **Every text the player sees exists in all 11 languages.** Slovak, English
  and the other seven are in `i18n.py`, Czech and Bulgarian in
  `i18n_cs_bg.py`. When you change a text, change it in every language;
  `check_translations.py` must exit with 0.
- **One word for one thing.** The main switch is *watching*, the heart-rate
  switch is *heart-rate receiving*, what the app gives you is a *cue*; a
  *limit* is in BPM, a *threshold* is for load (x/100). Technical words (TTS,
  OSC, UDP, obs-websocket) belong only in clearly advanced places.
- **A text that sends the player to the *In-game* page names it with
  `{page}`**, filled from `app_spolocne.stranka_vhre(app)`: in the Work world
  that page is called *Screen*. Dates on screen and in the log go through
  `ui_kit.datum_text` (only the CSV export keeps a fixed format); buttons
  through `ui_kit.button(kind=...)`; small red text uses the `danger_text`
  colour token (the rules are in `theme.py`).
- **A text that promises more than the code does is a bug** (see
  [SOUL.md](SOUL.md)). Many tests tie a sentence in the docs to the code: when
  the code changes, the test says which document to rewrite. The README keeps
  only a few such checks (its links, the official source, the version line,
  `Get-FileHash`, the untested iPhone route and the key privacy facts); exact
  wording is checked where it lives: [PRIVACY.md](PRIVACY.md),
  [KNOWN_ISSUES.md](KNOWN_ISSUES.md), [CHANGELOG.md](CHANGELOG.md),
  [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md) and this page.
- Code comments are in Slovak, without diacritics, and say *why*, not what.

See also **[SAFETY.md](SAFETY.md)** (anti-cheat / no-injection) and
**[PRIVACY.md](PRIVACY.md)** (what is local vs. networked).
