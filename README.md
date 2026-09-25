# 残 Zanshin

*Alpha 0.2.1 · Windows · GPLv3*

**Calm-reminders for gamers, triggered by your body — not a keystroke.**
Zanshin watches your **heart rate from a smartwatch** and, when strain stays
elevated for a while, it waits for a short pause in your input and then plays a spoken
reminder (TTS), a sound effect (SFX), or both — a quiet nudge to unclench your
jaw, drop your shoulders, and breathe.

> **Privacy first.** Your heart rate, sessions and insights never leave your
> computer. There is no telemetry, no analytics, and no account. The one thing
> that normally reaches the internet is the online TTS voice, which is **on by
> default**: it sends only the wording of your spoken reminders to Microsoft to
> turn it into speech, and nothing new while Zanshin is listening (a line
> already on its way when listening starts is finished). Switch to the
> offline Windows voice (Settings → Sound) to keep even that local.
> Everything that can use the network — including the heart-rate port, which is
> open on every network your PC is connected to — is listed in
> **[PRIVACY.md](PRIVACY.md)**.

> **The app does not capture the keyboard.** Pre-release builds had a global
> keyboard hook; it was removed before the first public alpha. Whether you're
> actively playing is read via `GetLastInputInfo` — a Win32 call that returns
> a single number: milliseconds since the last input, not which key it was.
> While it's listening it also watches controller activity through SDL — only
> as a sign that you're active; which button it was is never stored. With
> automatic profile switching on (the default), every few seconds it compares
> the names of running processes with the games it knows (listed under that
> switch), so it can switch the profile and start listening by itself when one
> launches; switch it off and the process list isn't read at all.
> Outside its own window the app hears only one key combination: the
> "not now" shortcut, which silences its cues for half an hour while it keeps
> measuring your heart rate (Ctrl+Alt+Z by default; press it again to end it
> sooner). "Not now" is also in the tray icon's menu (right-click), in case
> another app holds the shortcut. Stopping listening altogether is a separate
> switch. Windows tells it when that one combination is pressed, and about no
> other key. Details in **[SAFETY.md](SAFETY.md)** (in Slovak for now).

## Features

- **Your body triggers the reminder, not a key.** When strain (computed from
  heart rate) spends enough time above your threshold, the app *draws* and then
  waits for a short pause in your input — about 2.5 s with no key, mouse or
  controller. The moment of greatest need and the worst moment to interrupt are
  the same second — so the voice comes only in such a pause, once your strain
  has stopped climbing, and never while your pulse is in the Peak zone (at or
  above your own high heart-rate limit). The app can't see the game itself, so
  a still moment mid-fight can count as a pause too. If no such pause comes
  within 90 s, it shows a silent picture instead, under the same rules;
  otherwise it stays quiet. Some cues stay silent on purpose — about one in
  four in the first 15 sessions, one in ten after that — and show only the
  picture. That collects data for comparing voice with picture only; the app
  doesn't show that comparison yet.
- **It quiets itself when a cue gets in the way.** Answer after a session that
  the cue got in the way or wound you up — or press "not now" within a minute
  of a cue and keep playing for at least two more minutes, unless you then
  answer that it landed — and the next session drops one step: voice →
  picture only → no cues for a few sessions, then the picture again. It
  climbs back slowly, after three sessions with a cue that was actually shown
  and no complaint (a cue whose picture failed to draw doesn't count).
  History says in one quiet line where it is and why. How loud it may ever
  get is your call: voice, a sound and the picture without words, or the
  picture only. You can pick it during onboarding or any time under
  Settings → Sound; the app may still go quieter on its own, but never louder
  than your choice.
- **Nothing to tune by hand.** Your strain threshold, resting baseline, and
  high-HR line are all computed from *your own* sessions, each from at least
  three of them. Until then the threshold and the high-HR line use
  average-player numbers, and your calm is taken from the current session
  only. The threshold and the high-HR line learn only from play sessions of
  five minutes or more, and the strain threshold needs the most: three play
  sessions of five minutes or more that add up to roughly half an hour of
  heart rate — three of about ten minutes are enough, three of five are not.
  Imported sessions, sessions with implausible readings and sessions you
  marked afterwards as affected by illness, alcohol or exercise just before
  playing don't count.
- **Silent while you move.** As long as steps are coming from the watch, the app
  stays quiet — walking raises heart rate just like stress, and the two can't be
  told apart from BPM alone.
- **Two worlds, one body.** A small *Play | Work* switch in the title bar. Each
  world keeps its own history, insights and look — *Sumi* (ink and gold) for
  play, *Aizome* (indigo) for work — and switches without a restart. At work,
  cues are visual only: no voice, no sound. The resting baseline is shared; the
  strain threshold and high-HR line are learned from play sessions only. A
  running session stays in the world it started in, even if you flip the
  switch meanwhile. At the end, your answer to *Were you playing or working?*
  has the last word: pick the other world and the session moves there — in
  History, and in what the strain threshold and high-HR line learn from. Skip
  the question and it stays where it started.
- **Two TTS engines.** The *natural voice (Edge)* is the default: neural
  voices, prepared ahead of time into a local cache, so there's no latency
  in-game. Preparing a line sends its wording to Microsoft — after the first
  start and when you change a line, the voice, the speed, the language or the
  profile, and only while your cues actually speak (not in the sound or
  picture-only style, not in the Work world). **Nothing new is prepared
  while Zanshin is listening** (a line already on its way when listening
  starts is finished): a line that isn't ready then plays in the Windows
  voice, and preparing waits until you stop listening. On the very first
  start Zanshin begins listening by itself right after the introduction, so
  most lines are prepared only after you stop listening for the first time.
  The *Windows voice (SAPI5)* works fully offline.
- **Built-in SFX library.** Eight sounds across the two modes, shipped with the
  app. Only if one goes missing does the app replace it — two of them from
  GitHub (CC0, checksum-verified), the rest synthesised locally.
- **Eleven-language UI.** English, Slovak, Japanese, Chinese, Russian, Spanish,
  German, French, Portuguese, Czech, Bulgarian — switchable at runtime. The app
  is written in Slovak; the other languages are AI-assisted translations not
  yet checked by a native speaker.
- **In-game HUD & overlays.** Optional heart-rate/strain HUD and click-through
  somatic visuals, DPI-aware with multi-monitor and 4K support.
- **Guide — what's behind each cue.** Each built-in reminder has a short note
  (open it from the reminder itself, or all of them in the Guide window): what
  tends to happen in your body, what to try, and where the idea comes from — a
  study from the source list where there is one, practice or tradition where
  there isn't.

## Install (for players)

**Official download:** only <https://github.com/Dandurfin/Zanshin> (Releases).
Each release lists the installer's SHA-256. A copy from anywhere else is not
from me.

Download `Zanshin-<version>-setup.exe` (for this version
`Zanshin-0.2.1-setup.exe`) from the release and run it. The
installer asks for a language (11 available, English default) and installs
**without administrator rights** (no UAC) into `%LOCALAPPDATA%\Programs\Zanshin`.
Your data (settings, recordings, generated speech and SFX) always goes to
`%APPDATA%\Zanshin`, wherever the app is installed.

**Why no admin rights:** the app draws a window over the game. An elevated
process doing that is exactly what anti-cheats (Vanguard, EAC, VAC) treat most
harshly. See `SAFETY.md` (in Slovak).

Zanshin has no Steam integration — it doesn't load the Steam SDK or talk to
Steam in any way.

Windows SmartScreen may warn on first launch that the file is from an unknown
publisher — choose **More info → Run anyway**. (Removing that warning
permanently requires signing the `.exe` with a code-signing certificate, which
is outside the scope of this build.)

## Getting your heart rate in

Zanshin **listens on port `4455`** (TCP and UDP) so a phone or watch app can
push readings to it — it only receives, it never sends your heart rate out. It
listens on **every network your PC is connected to** (unless you enter one of
this PC's own addresses in the heart-rate sensor settings; an address the PC
doesn't have falls back to all networks, and the log says so) and **without a
password**, so anything that can reach that port could send it a heart-rate
value. Only your firewall decides who can: allow Zanshin on your home network
only, not on public Wi-Fi (details in [PRIVACY.md](PRIVACY.md)).

That app is a **third‑party companion you install on your phone or watch — made by someone else, not part of Zanshin.** It reads
your heart rate there and sends it to Zanshin on this PC. The QR codes
shown in Zanshin are just **download links** to those companion apps (they open
the App Store / Google Play). *Pairing* then means pointing the companion at this
PC on your LAN — port `4455`. **Zanshin itself has no mobile app** on any store.
And because that companion is someone else's app, Zanshin can't vouch for what it
does on its own side — so pick one you trust. It's your free choice.

**Android / Wear OS:** *HeartRateOnStream for OBS* (free).
**iPhone / Apple Watch:** *PulseOSC* (paid) sends OSC,
which Zanshin's code can receive — **but the iPhone route is untested so far:
the author has no Apple device.** PulseOSC costs money, so keep that in mind
before you buy it; if you try it, please let me know whether it works for you
(open an issue). The password, scene and source steps in the app's pairing guide
apply to the Android app only; in PulseOSC you only enter this PC's IP and port.

Pick a companion that pushes heart rate **to your own network** — over **OSC**,
plain **UDP**, or **obs‑websocket** (see [PRIVACY.md](PRIVACY.md)). **Zanshin
deliberately doesn't connect to cloud services such as Pulsoid, HypeRate or
Stromno (also third‑party):** they route your heart rate through their own
servers, and Zanshin only takes heart rate sent straight to this PC.

## Prior art & related work

Zanshin builds on a handful of earlier projects. None of them do the specific
thing Zanshin is built around — *watch your heart rate while you play and coach
you back down at a safe moment* — but each solves a neighbouring piece, and it
would be dishonest not to name them.

| Project | What it does | How Zanshin differs |
|---|---|---|
| **[Cardia](https://github.com/uwburn/cardia)** (GPLv3) | Windows, local-first; reads a BLE strap/watch and **shows** your heart rate. | Closest in spirit — the same open, local-first, Windows values. But Cardia *displays* the number; Zanshin *acts on it* — deciding when strain is high and delivering a somatic cue at a short pause in your input. |
| **Pulsoid · HypeRate · Stromno** | Stream heart rate to an on-screen overlay for your viewers. | Cloud-routed and closed; they exist to **show the number to an audience**. Zanshin keeps it on your machine and uses it to help *you*. (Zanshin doesn't take heart rate from them — they route it through their own servers; see above.) |
| **Pauser** and similar stress apps | Detect stress and walk you through a breathing exercise, mostly on mobile. | Same detect→regulate idea, but not gaming-aware and not tied to a live HR gate. Zanshin fires only when your strain stays above a threshold (average-player numbers for the first few sessions, then your own); the voice waits for a short pause in your input and never speaks in the Peak zone. |
| **Unclench** and somatic-reminder scripts | Periodic "drop your shoulders, unclench your jaw" nudges. | Timer-based, not signal-based. Zanshin's whole premise is that the *right second* is chosen by your heart rate, not a clock. |

**In one line:** existing tools either *show* your heart rate or *remind* you on a
timer. Zanshin is the only one we could find that **reads your heart rate and
nudges you** — locally, and only after your strain has stayed high for a
while.

**What Zanshin is deliberately _not_:** a streaming overlay, a fitness tracker, a
medical device, or a cloud service. It doesn't score you or gamify calm, and it
never sends your heart rate, sessions or insights anywhere. The few
things that ever touch the network are listed honestly in [PRIVACY.md](PRIVACY.md). If you know a project that overlaps more than the ones above,
please open an issue — credit where it's due.

## Run from source (development)

```bash
pip install -r requirements.txt
python main.py
```

Requires Python 3.10+ on Windows.

## Build the installer

Easiest: double-click `build.bat` (runs `build_all.ps1`). Or directly:

```powershell
powershell -ExecutionPolicy Bypass -File "build_all.ps1"
```

The script (1) checks/installs Python deps and PyInstaller, draws
`Dandurf.ico` if it's missing, and runs `check_before_run.py` — if that finds
a problem, nothing is built; (2) force-closes a running Zanshin without asking
(Windows locks a running `.exe`), deletes the old `dist\Zanshin\` and packages
the app into `dist\` (onedir, no admin manifest, UPX off); and (3) assembles
the installer with Inno Setup 6 into `installer\` (if Inno Setup 6 is
installed; otherwise you can run the `.exe` straight from `dist\`).

## Tests

With the app's dependencies installed (see above), install the developer
tools first — `requirements-dev.txt` holds pytest and pyflakes — then run the
tests:

```bash
pip install -r requirements-dev.txt
python -m pytest tests/
```

Other developer scripts, run by hand from the repository folder. None of them
is part of the app or the installer:

- `check_before_run.py` — checks what can be checked without opening a
  window: every module compiles, no undefined names (with pyflakes), the
  translations are complete, the main window calls no method or colour token
  that doesn't exist, and no keyboard hook or Steam code has come back.
  `build_all.ps1` runs it before every build.
- `check_translations.py` — missing languages, mismatched `{placeholders}` and
  empty strings in the translations; exits with an error if it finds any.
- `make_translation_todo.py` — writes `preklad_TODO.csv`, the strings still
  waiting for a translation.
- `check_sources.py` — opens every study link in the Guide and reports the
  dead ones. It needs the internet and contacts each linked site.
- `simulate.py` — plays synthetic evenings through the app's own heart-rate,
  activity, trigger and measurement code and says what the cues would have
  done. It checks the mechanism, not whether the thresholds fit your body.
- `prepocitaj_okna.py` — re-checks measurement windows that were already
  saved against today's validity rules. **It rewrites the saved
  `hr_windows.json`** next to `main.py` (the data of Zanshin run from source,
  not of the installed app); a backup copy goes next to it first, and
  `--nahlad` only previews. Nothing is deleted: a window that no longer
  passes is marked invalid, with the reason.

The repository also holds three developer scripts for testing the window by
hand: `gui_harness_auto.py`, `gui_harness_onboarding.py` and
`gui_screenshots.py`. The first two use the real mouse (move, click, drag,
scroll) and press Escape; all three take screenshots of the app's own windows
and pictures, with a small margin around them. None of them is part of the app or the installer:
the build packs `main.py`, the modules it imports and the `assets` folder, and
nothing imports these scripts.

## License

| What | License | File |
|---|---|---|
| **All of the source code** — including the ensō drawn in code, the colour themes and the layout | **GNU GPL v3.0 or later** — free and open | [`LICENSE`](LICENSE) |
| **Two artwork files** — the app icon (`Dandurf.ico`) and the dojo picture (`assets/images/dojo_noc.webp`) | © Dandurfin — they travel with unmodified copies of the official Zanshin | [`LICENSE-DESIGN.md`](LICENSE-DESIGN.md) |

You may read, run, study, change and pass on the code freely under the GPL.
A modified version has to be clearly marked as different from the original —
its own name, or a plain note that it is a modified version — and use its own
icon and picture. It must not present itself as the official Zanshin or as
made or endorsed by Dandurfin (additional terms under GPLv3 section 7; see
[`LICENSE-DESIGN.md`](LICENSE-DESIGN.md)). This is there to protect the people
who use Zanshin, not to make money.

Author: **Dandurfin** — [Twitch](https://www.twitch.tv/dandurfin) ·
[YouTube](https://www.youtube.com/channel/UCzZyqQfTNpiGkt_SIOmKO2w) ·
[Kick](https://kick.com/dandurfin)

## Project structure

| File | Purpose |
|---|---|
| `main.py` | Entry point — checks deps, starts `app.DandurfApp` |
| `app.py` | Main window, wiring for the whole app |
| `paths.py` | Data paths (`%APPDATA%`), migration from older versions |
| `settings_model.py` | Slot/settings data model — defaults, normalisation |
| `audio_engine.py` | TTS (Edge Natural + SAPI5) and SFX/recording playback |
| `theme.py` | Colour tokens for Sumi / Aizome modes |
| `i18n.py` | UI translations (11 languages; Czech and Bulgarian in `i18n_cs_bg.py`) |
| `sfx_assets.py` | Built-in SFX library — copies the bundled sounds; download or synthesis only if one is missing |
| `heart_rate.py` | Local-network receiver for BPM/steps from a companion app |
| `obs_websocket.py` | Minimal obs-websocket v5 server — what *HeartRateOnStream for OBS* writes your heart rate to |
| `netinfo.py` | This PC's local IP addresses for pairing, hidden on screen until *Show IP* |
| `activity.py` | Whether the player is active (`GetLastInputInfo`, **no hook**) |
| `gamepad.py` | Controller activity through SDL (`pygame`) — only "the player is active"; which button is never stored |
| `hotkey.py` | The one global shortcut, "not now" (`RegisterHotKey`, not a hook) |
| `game_profiles.py` | Auto-profile — compares running process names with the known games (only while that switch is on) |
| `trigger.py` | Reminder state machine — draw, defer to a break, silent arm |
| `rebrik.py` | Cue ladder — voice → picture → pause, set per session from your feedback |
| `measure.py` | Measurement windows around a reminder and their validity |
| `hr_stats.py` | Resting baseline, strain index, session summaries & history |
| `hr_insights.py` | Patterns across sessions — hedged notes, not diagnoses |
| `data_io.py` | Export / import / delete — strict parser (50 MB cap, UTF-8 only, NaN/Infinity rejected, every field checked), no pickle |
| `overlay.py`, `hud.py`, `hud_paint.py` | In-game visuals and HUD (PIL rendering) |
| `layer_window.py` | The click-through, see-through window (`UpdateLayeredWindow`) every in-game visual is drawn in |
| `display.py` | Monitors, DPI awareness, and which screen to draw on |
| `ui_shell.py`, `ui_dialogs.py` | Main-window shell, dialogs, onboarding |
| `ui_kit.py` | Building blocks of the main window — the breathing band, keycaps, stat cards, charts |
| `theme_recolor.py` | Recolours the open window when the theme changes, without rebuilding it |
| `color_picker.py` | The app's own colour picker (no eyedropper — it would have to capture the screen) |
| `guided_tour.py` | The guided tour of the window after onboarding |
| `guide_content.py`, `guide_panel.py` | The Guide — per-cue notes, philosophy and source list |
| `background.py` | The dojo backdrop and the "Today" hero |
| `make_icon.py` | Draws the ensō — the `Dandurf.ico` icon, and the tray mark while the app runs |
| `logging_setup.py` | Local log files (`app.log`, `crash.log`) — no remote crash reporting |
| `Dandurf.spec`, `build.bat`, `build_all.ps1`, `Dandurf.iss` | PyInstaller + Inno Setup build |

See also **[SAFETY.md](SAFETY.md)** (anti-cheat / no-injection, in Slovak) and
**[PRIVACY.md](PRIVACY.md)** (what is local vs. networked).

---

**[Soul of the app](SOUL.md)**
