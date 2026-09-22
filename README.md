# 残 Zanshin

*Alpha 0.1 · Windows · GPLv3 (code) + protected design*

**Calm-reminders for gamers, triggered by your body — not a keystroke.**
Zanshin watches your **heart rate from a smartwatch** and, when strain stays
elevated for a while, it waits for a break in the action and then plays a spoken
reminder (TTS), a sound effect (SFX), or both — a quiet nudge to unclench your
jaw, drop your shoulders, and breathe.

> **Privacy first.** Your heart rate, sessions, insights and settings never
> leave your computer. There is no telemetry, no analytics, and no account.
> The few things that can touch the network (an optional online TTS voice, a
> first-run sound download) are listed honestly in **[PRIVACY.md](PRIVACY.md)**.

> **Since 2.1 the app does not capture the keyboard.** The global keyboard hook
> is gone from the code. Whether you're actively playing is read via
> `GetLastInputInfo` — a Win32 call that returns a single number: milliseconds
> since the last input. *Which* key you pressed the app has no way to know.
> Details in **[SAFETY.md](SAFETY.md)**.

## Features

- **Your body triggers the reminder, not a key.** When strain (computed from
  heart rate) spends enough time above your threshold, the app *draws* and then
  waits for a pause in play. The moment of greatest need and the worst moment to
  interrupt are the same second — so the reminder is deferred to a break, by at
  most 90 s.
- **Nothing to tune by hand.** Your strain threshold, resting baseline, and
  high-HR line are all computed from *your own* sessions. The first session runs
  on average-player numbers.
- **Silent while you move.** As long as steps are coming from the watch, the app
  stays quiet — walking raises heart rate just like stress, and the two can't be
  told apart from BPM alone.
- **Two visual + sound modes.** *Sumi* (zen, gold) and *Aizome* (modern, indigo),
  switchable at any time without a restart.
- **Two TTS engines.** *Edge Natural* (neural voices, pre-generated to a local
  cache — no latency in-game, needs the network only when you edit a phrase) and
  *Windows SAPI5* (works fully offline).
- **Built-in SFX library.** Eight sounds across the two modes, generated locally
  on first run (with two optional CC0 downloads, synthesised locally as a
  fallback).
- **Nine-language UI.** English, Slovak, Japanese, Chinese, Russian, Spanish,
  German, French, Portuguese — switchable at runtime.
- **In-game HUD & overlays.** Optional heart-rate/strain HUD and click-through
  somatic visuals, DPI-aware with multi-monitor and 4K support.
- **Guide — "the science behind it".** A slide-out panel explaining the
  biomechanics and neurobiology behind each trigger.

## Install (for players)

Download and run `installer/Zanshin-<version>-setup.exe` from the release. The
installer asks for a language (9 available, English default) and installs
**without administrator rights** (no UAC) into `%LOCALAPPDATA%\Programs\Zanshin`.
Your data (settings, recordings, generated speech and SFX) always goes to
`%APPDATA%\Zanshin`, wherever the app is installed.

**Why no admin rights:** the app draws a window over the game. An elevated
process doing that is exactly what anti-cheats (Vanguard, EAC, VAC) treat most
harshly, and Steam does not support elevation. See `SAFETY.md` and
`STEAM_BUILD.md`.

Windows SmartScreen may warn on first launch that the file is from an unknown
publisher — choose **More info → Run anyway**. (Removing that warning
permanently requires signing the `.exe` with a code-signing certificate, which
is outside the scope of this build.)

## Getting your heart rate in

Zanshin **listens on your local network** (port `4455`) so a phone/watch app can
push readings to it — it only receives, it never sends your heart rate out. The
QR codes shown in the app are for **pairing that local companion**, not links to
an app store. As of alpha 0.1 there is **no mobile version** on the App Store or
Google Play.

For a **fully local** chain, prefer a companion that sends heart rate over **OSC**
on your LAN. Cloud-based companions (Pulsoid, HypeRate, Stromno) work too, but
route your heart rate through *their* servers — see [PRIVACY.md](PRIVACY.md).

## Prior art & related work

Zanshin builds on a handful of earlier projects. None of them do the specific
thing Zanshin is built around — *watch your heart rate while you play and coach
you back down at a safe moment* — but each solves a neighbouring piece, and it
would be dishonest not to name them.

| Project | What it does | How Zanshin differs |
|---|---|---|
| **[Cardia](https://github.com/uwburn/cardia)** (GPLv3) | Windows, local-first; reads a BLE strap/watch and **shows** your heart rate. | Closest in spirit — the same open, local-first, Windows values. But Cardia *displays* the number; Zanshin *acts on it* — deciding when strain is high and delivering a somatic cue at a break in play. |
| **Pulsoid · HypeRate · Stromno** | Stream heart rate to an on-screen overlay for your viewers. | Cloud-routed and closed; they exist to **show the number to an audience**. Zanshin keeps it on your machine and uses it to help *you*. (You can still feed Zanshin from these — see above.) |
| **Pauser** and similar stress apps | Detect stress and walk you through a breathing exercise, mostly on mobile. | Same detect→regulate idea, but not gaming-aware and not tied to a live HR gate. Zanshin fires only when *your body* crosses *your own* threshold — and never mid-fight. |
| **Unclench** and somatic-reminder scripts | Periodic "drop your shoulders, unclench your jaw" nudges. | Timer-based, not signal-based. Zanshin's whole premise is that the *right second* is chosen by your heart rate, not a clock. |

**In one line:** existing tools either *show* your heart rate or *remind* you on a
timer. Zanshin is the only one we could find that **reads your heart rate and
coaches you** — locally, silently, and only when you actually need it.

**What Zanshin is deliberately _not_:** a streaming overlay, a fitness tracker, a
medical device, or a cloud service. It doesn't score you, gamify calm, or send a
byte anywhere. If you know a project that overlaps more than the ones above,
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

The script (1) checks/installs Python deps and PyInstaller, (2) packages the app
into `dist\` (onedir, no admin manifest, UPX off), and (3) assembles the
installer with Inno Setup 6 into `installer\` (if Inno Setup 6 is installed;
otherwise you can run the `.exe` straight from `dist\`).

## Tests

```bash
python -m pytest tests/
```

## License

Zanshin is **dual-licensed**:

| Layer | License | File |
|---|---|---|
| **Source code** | **GNU GPL v3.0 or later** — free and open | [`LICENSE`](LICENSE) |
| **Design, UI/UX, artwork** (the 残 mark, imagery, colour themes, layout, look & feel) | **Proprietary — © Dandurfin, all rights reserved** | [`LICENSE-DESIGN.md`](LICENSE-DESIGN.md) |

You may read, run, study, modify, and contribute to the **code** freely under
the GPL. The **design and artwork** may be reused **only with the author's
express prior written consent** — including any **mobile port** that would reuse
the design, visuals, layout, or feature arrangement. A fork must ship its own
distinct design. See [`LICENSE-DESIGN.md`](LICENSE-DESIGN.md).

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
| `i18n.py` | UI translations (9 languages) |
| `sfx_assets.py` | Built-in SFX library — synthesis and optional download |
| `heart_rate.py` | Local-network receiver for BPM/steps from a companion app |
| `activity.py` | Whether the player is active (`GetLastInputInfo`, **no hook**) |
| `trigger.py` | Reminder state machine — draw, defer to a break, silent arm |
| `measure.py` | Measurement windows around a reminder and their validity |
| `hr_stats.py` | Resting baseline, strain index, session summaries & history |
| `data_io.py` | Export / import / delete — strict parser, no pickle |
| `overlay.py`, `hud.py`, `hud_paint.py` | In-game visuals and HUD (PIL rendering) |
| `ui_shell.py`, `ui_dialogs.py` | Main-window shell, dialogs, onboarding |
| `guide_content.py`, `guide_panel.py` | The "Guide / science behind it" panel |
| `background.py` | The dojo backdrop and the "Today" hero |
| `Dandurf.spec`, `build.bat`, `build_all.ps1`, `Dandurf.iss` | PyInstaller + Inno Setup build |

See also **[SAFETY.md](SAFETY.md)** (anti-cheat / no-injection) and
**[PRIVACY.md](PRIVACY.md)** (what is local vs. networked).
