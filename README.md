# 残 Zanshin

*Alpha 0.2.1 · Windows · code under GPLv3 or later*

**Calm-reminders for gamers, triggered by your body — not a keystroke.**
Zanshin watches your **heart rate from a smartwatch** (a third-party app on your
phone or watch sends it to your PC over your local network; see *Getting your
heart rate in*) and, when strain stays elevated for a while, shows a picture on
screen, usually with a spoken reminder (TTS) and a sound (SFX) timed to a short
pause in your input — a quiet nudge to unclench your jaw, drop your shoulders,
and breathe.

> **Privacy first.** Your heart rate, sessions and insights never leave your
> computer. There is no telemetry, no analytics, and no account. The one thing
> that normally reaches the internet is the online TTS voice, which is **on by
> default**: to turn your reminders into speech, it sends Microsoft the wording
> of those in your current profile that are switched on, with their in-game
> picture on, and set to speak (not ones that play your own recording), with
> the voice and speed you picked (like any connection, it also shows Microsoft
> your IP address).
> It sends nothing new while Zanshin is listening (the state you switch with
> Start / Stop; it has nothing to do with the microphone), and a line already
> on its way when listening starts is finished. Switch to the
> offline Windows voice (Settings → Sound) to keep even that local; that stops
> any preparing at once, except a line already on its way.
> Everything that can use the network is listed in **[PRIVACY.md](PRIVACY.md)**.
> That includes the heart-rate port (`4455` by default). It stays closed until
> you open the watch pairing guide or switch on *Listen for heart rate from the
> watch*. From then on, whenever Zanshin runs (even hidden in the tray, and
> again after a restart), it accepts connections without a password on every
> network your PC is connected to (unless you enter one of this PC's own
> addresses), until you switch that off again.

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
> measuring your heart rate (Ctrl+Alt+Z, which can't be changed in the app
> yet; press it again to end it sooner). Windows reserves that combination for
> Zanshin from start-up until you quit, even while it sits in the tray, so a
> game that uses Ctrl+Alt+Z may not receive it. "Not now" is also in the tray
> icon's menu (right-click), in case another app holds the shortcut. Stopping
> listening altogether is a separate switch. Windows tells it when that one
> combination is pressed, and about no other key. Details in **[SAFETY.md](SAFETY.md)** (in Slovak for now).

## Features

- **Your body triggers the reminder, not a key.** When your *load* — the app's
  measure of strain, computed from heart rate (LOAD on the HUD) — spends enough
  time above your threshold, the app is *armed* (the Today page says so) and
  then waits for a short pause in your input — about 2.5 s with no key, mouse
  or controller. The moment of greatest need and the worst moment to interrupt
  are the same second — so the voice comes only in such a pause, once your
  load has stopped climbing, and never while your pulse is in the Peak zone
  (at or above your high heart-rate limit). The app can't see the game itself,
  so a still moment mid-fight can count as a pause too. If no such pause comes
  within 90 s, it shows a silent picture instead, under the same rules;
  otherwise it stays quiet. Some cues stay silent on purpose — about one in
  four in your first 15 sessions (every session of a minute or more counts,
  Work too), one in ten after that — and show only the picture. That collects
  data for comparing voice with picture only; the app doesn't show that
  comparison yet. At most five cues an hour (restarting the app starts that
  count over), and at least four minutes apart within a session.
- **It quiets itself when a cue gets in the way.** Answer "it disrupted" or
  "it wound me up" in the questionnaire after a session — or press "not now"
  within a minute of a cue and let the session carry on for at least two more
  minutes, unless you then answer that it landed — and the next session in
  the same world (Play or Work) drops one step: voice → picture only → no cues
  for three sessions of five minutes or more (sooner if you answer after a
  session that it should have spoken up), then the picture again. It climbs
  back slowly, after three sessions with a cue that was actually shown and
  none of those signals (a cue whose picture failed to draw doesn't count).
  When it has gone quieter, History says so in one quiet line: why, and how
  many more sessions it needs before it tries a step louder. How loud it may
  ever get is your call: voice, a sound and the picture without words, or the
  picture only. You can pick it during onboarding or any time under
  Settings → Sound; the app may still go quieter on its own, but never louder
  than your choice.
- **Nothing to tune by hand.** Your load threshold, resting baseline and high
  heart-rate limit are all computed from *your own* sessions, each from at
  least three of them. Until then the threshold and the high heart-rate limit
  use average-player numbers, and your calm is taken from the current session
  only. The threshold and the high heart-rate limit learn only from play
  sessions of five minutes or more, and the load threshold needs the most: at
  least three play sessions of five minutes or more that add up to roughly
  half an hour of heart rate — three of about ten minutes are enough, three of
  five are not. Imported sessions, sessions with implausible readings and
  sessions you marked afterwards as affected by illness, alcohol or exercise
  just before playing don't count.
- **Silent while you walk — if your watch sends steps.** While the watch
  reports steps (15 or more in the last minute, for now), the app stays quiet
  — walking raises heart rate just like stress, and the two can't be told
  apart from BPM alone. Not every watch app sends steps; if yours doesn't, the
  app can't tell you're walking, so a walk can look like strain and bring a
  cue.
- **Two worlds, one body.** A small *Play | Work* switch in the title bar. Each
  world keeps its own history, insights and look — *Sumi* (ink and gold) for
  play, *Aizome* (indigo) for work — and switches without a restart. At work,
  cues are visual only: no voice, no sound. The resting baseline is shared; the
  load threshold and high heart-rate limit are learned from play sessions only
  and used in both worlds, so if you only ever use Work, they stay on the
  average-player numbers. A running session stays in the world it started in,
  even if you flip the switch meanwhile. At the end, your answer to *Were you
  playing or working?* has the last word: pick the other world and the session
  moves there — in History, and in what the load threshold and high heart-rate
  limit learn from. Skip the question and it stays where it started.
- **Two TTS engines.** The *natural voice (Edge)* is the default: neural
  voices, prepared ahead of time into a local cache, so in-game nothing waits
  on the network. Preparing sends Microsoft a reminder's wording only if it is
  one of the four, switched on with its in-game picture on, set to speak and
  not playing your own recording, and only if its line isn't in the cache
  yet. That happens at every start (the first time for all of them), and
  again after you change a line (while you type, a pause of about 0.7 s is
  enough, so a half-typed line can go too), switch it or its picture on,
  switch it to speak or remove its own recording, change the voice, the
  speed, the profile (or create one) or the language (when that changes the
  voice), import a profile, and after you switch back to the voice style, to
  Play or to the natural voice. Testing a line that isn't ready, or *Prepare
  voice lines* in the Ctrl+K palette, sends the missing ones too; testing a
  reminder that is switched off or has its picture off, or an extra one kept
  from 0.1, plays the Windows voice and sends nothing. It happens only in the
  voice style and the Play world (not in the sound or picture-only style, not
  in Work), and it still happens while the app has quietened itself to
  picture only or a pause. Switching a reminder or its picture off,
  giving it your own recording, changing or creating a profile, or switching
  to the sound or picture-only style, to Work or to the Windows voice stops
  any preparing already running at once; only a line already on its way is
  finished. **Nothing new is prepared while Zanshin is listening** (a line
  already on its way when listening starts is finished): a line that isn't
  ready then plays in the Windows voice, and preparing waits until listening
  stops. On the very first start Zanshin begins listening by itself right
  after the introduction, so most lines are prepared only after you stop
  listening for the first time, or at the next start if you quit while
  listening. The *Windows voice (SAPI5)* works fully offline.
- **Built-in SFX library.** Eight short sounds in two sets of four, *Zen* and
  *Modern*, shipped with the app. Play cues use the Zen set unless you pick
  another sound for a reminder; Work cues make no sound. If a sound file goes
  missing, the built app copies it back from the `.exe`. Only if that isn't
  possible (or you run from source) are two of them downloaded from GitHub
  (Kenney, CC0, checksum-verified) and the rest synthesised locally, those two
  as well if the download fails.
- **Eleven-language UI.** English, Slovak, Japanese, Chinese (Simplified),
  Russian, Spanish, German, French, Portuguese (Brazil), Czech, Bulgarian,
  switchable at runtime. What the app draws into the game (the HUD and the
  captions under the pictures) stays in English unless you change *In-game
  language*. The built-in reminder words are set in the app's language when a
  profile is created (English ones for Slovak and Czech); switching the
  language later doesn't translate them. With the natural voice, spoken
  reminders keep the default English voice until you pick another. The
  exception is reminders in Japanese, Chinese, Russian or Bulgarian, which
  get a voice of that language while you're still on the default voice: on a
  first start in that language, when a profile is created in it, or when you
  switch to it and the reminders that speak in the profile you're in use its
  built-in words (not reworded ones). The voice follows the words, not the
  menu: switching the language with English words keeps the English voice,
  and switching back doesn't undo a change. One voice reads all your
  profiles, except reminders given a voice of their own. The app is written
  in Slovak; the other languages are AI-assisted translations not yet
  checked by a native speaker.
- **In-game HUD & pictures.** An optional in-game heart-rate panel (the HUD,
  which also shows your load; off by default) and the in-game pictures every
  cue uses (on by default; a reminder whose picture you switch off never
  fires). Both are click-through, drawn by default on the monitor of the
  window in focus (normally your game), and scaled to that screen's height,
  so they take the same share of a 1080p or a 4K screen (DPI-aware). Windows
  doesn't draw them over a game in exclusive fullscreen (the voice still
  plays); use Borderless.
- **Guide — what's behind each cue.** Each of the four built-in reminders has
  a short note. Open it with the ▸ arrow next to the reminder on the
  *Triggers* page, or read them all in the Guide window. It covers what
  happens in your body, why it may help and what to do (for breath, two
  techniques). The breath note cites studies on breathing. The jaw note cites
  one that competitive play raises a stress response, not that you hold it in
  your jaw. The grounding and peripheral-vision notes say plainly they come
  from practice or tradition. The full source list is [ZDROJE.md](ZDROJE.md)
  (notes in Slovak); none of these studies tested Zanshin.

## Install (build it yourself)

**Official source:** only <https://github.com/Dandurfin/Zanshin>. There is no
ready-made download, neither an installer nor an `.exe`. You build Zanshin on
your own PC from the source code, so Zanshin's own code is exactly what you can
read here. The libraries it uses (`requirements.txt`) and PyInstaller, which
packs it into an `.exe`, come from PyPI, the usual Python package index. The
build installs the ones that are missing, in whatever version is newest that
day, and keeps using the ones already installed without updating them, in
later builds too. If anyone offers you a ready-made Zanshin `.exe` or
installer, it isn't from me.

**Why no installer:** Windows warns about programs downloaded from an "unknown
publisher", which is what an app without a code-signing certificate is.
Zanshin has no such certificate, and an app that asks you to click past a
warning like that is not a good start. A program you build on your own PC
wasn't downloaded, so that warning doesn't come up for it.

This is how I install it myself. You need an internet connection. On my PC
the first build downloaded under 100 MB and took about 550 MB on disk, Python
included.

1. **Install Python.** On <https://www.python.org/downloads/> click
   **Download Python install manager**, open the downloaded file and click
   **Install**. It needs no administrator rights and there's nothing to tick.
   You don't have to pick a Python version: the first build (step 3) fetches
   the newest Python 3 by itself. I build and test with Python 3.14. Anything
   newer is untested, and until the libraries and PyInstaller support it, the
   build may stop at a red **CHYBA:** line. If you already have Python 3.10 or newer, you can skip
   this step, but only 3.14 is tested.
2. **Get the source.** On the GitHub page open **Tags** and, next to the
   newest version, click **zip**. Before unpacking, right-click the ZIP →
   **Properties** → tick **Unblock** → **OK**. Windows marks everything you
   download, and without this it shows an "unknown publisher" warning for
   `build.bat` in step 3. Unblock only a ZIP you got from the page above. Then
   right-click the ZIP → **Extract All…** and choose a folder that OneDrive
   doesn't back up, for example `C:\Games` (Desktop and Documents often are in
   OneDrive). You get a folder like `Zanshin-0.2.1`; if there's another folder
   of the same name inside it, open that one too, until you see `build.bat`.
3. **Build it.** Double-click **`build.bat`** (with file extensions hidden, it
   shows as `build`). The first time, it fetches Python through the install
   manager, the packages Zanshin needs and PyInstaller, then builds the app;
   on my PC that took about 3 minutes, and for a while the window shows
   nothing new. The script's own messages are in Slovak, and a lot of English
   text from pip and PyInstaller scrolls past, including WARNING lines about
   PATH: that's normal. Near the end it says *Inno Setup som nenasiel* ("I
   didn't find Inno Setup"): you don't need it. Then *HOTOVO* ("done") shows
   where the app is; press any key to close the window. If it stops at a red
   line starting **CHYBA:** ("error"), the rest says what went wrong:
   *Nenasiel som Python* means Python isn't there or couldn't be downloaded,
   *pip install zlyhal* means the packages couldn't be downloaded or
   installed. Check your connection and step 1, then run `build.bat` again;
   if it still fails, please open an issue and paste the last lines.
4. **Start it.** In the same folder, open `dist`, then `Zanshin`: the app is
   `dist\Zanshin\Zanshin.exe`. For a desktop shortcut, right-click it → on
   Windows 11 **Show more options** → **Send to → Desktop (create shortcut)**.
   Keep the whole `dist\Zanshin\` folder together: the `.exe` needs the
   `_internal` folder next to it. When Zanshin first opens its heart-rate
   port, Windows Firewall may ask whether to allow it; see *Getting your heart
   rate in* below.

**If Windows blocks it:** antivirus programs, Windows Security included,
sometimes flag programs packed with PyInstaller by mistake. The build is a
folder rather than one self-unpacking `.exe`, and UPX compression is off; both
are often blamed for these false alarms, but I can't promise it won't happen.
And with Smart App Control on (Windows Security → App & browser
control), Windows can block unsigned programs outright, with no "Run anyway".
I haven't been able to test how it treats a Zanshin you built yourself. If
either happens, please don't switch your protection off for Zanshin; open an
issue instead, so I know.

**Updating:** quit Zanshin first (right-click its tray icon → **Quit**). If it's
still running, `build.bat` closes it without asking, and a session in progress
isn't saved. Then get the new version and build it the same way. Your data
stays, because it isn't in the build folder. Make a new shortcut to the new
`dist\Zanshin\Zanshin.exe` and delete the old folder. To Windows Firewall it's
a new program, so it may ask again.

**Your data** (settings, heart-rate history, recordings, generated speech and
SFX) lives in `%APPDATA%\Zanshin`, not in the build folder, so rebuilding
doesn't touch it. **To remove Zanshin,** delete the folder you unpacked (for
example `C:\Games\Zanshin-0.2.1`) and the shortcut; your data stays in
`%APPDATA%\Zanshin` until you delete that folder too. Python stays installed:
if you don't need it for anything else, uninstall *Python 3.x* first and then
*Python install manager*, in Settings → Apps → Installed apps. pip keeps what
it downloaded for the build in `%LOCALAPPDATA%\pip\cache` (about 45 MB on my
PC); you can delete that folder, and `%LOCALAPPDATA%\Python` too if it's
still there afterwards.

**No administrator rights,** not for Python's install manager, not for the
build, not for the app, and don't run Zanshin as administrator. The app draws
a window over the game, and I don't want an elevated process doing that,
because anti-cheats (Vanguard, EAC, VAC) may treat it more harshly; only their
makers know what they actually check. See `SAFETY.md` (in Slovak). The one
exception is Windows Firewall's own question in step 4: allowing an app there
takes administrator approval, because it changes a Windows setting.

Zanshin has no Steam integration — it doesn't load the Steam SDK or talk to
Steam in any way.

## Getting your heart rate in

Zanshin **listens on port `4455`** (TCP and UDP) so a phone or watch app can
push readings to it. It replies only as much as the connection needs (on TCP
it pretends to be OBS) and never sends your heart rate out. The port stays
closed until you switch on *Listen for heart rate from the watch* under
**In-game → Watch and heart rate**; opening the pairing guide (*Pair your
watch* or *How to pair your watch…*) switches it on too. After that it opens
every time Zanshin starts, until you switch it off. `4455` is the default; you
can change it in the same panel. It listens on **every network your PC is
connected to** (unless you type one of this PC's own addresses into **IP
address** in that panel; an address the PC doesn't have falls back to all
networks, and the log says so) and **without a password**, so anything that
can reach that port could send it a heart-rate value. Only your firewall
decides who can: allow Zanshin on your home network only, not on public Wi-Fi
(details in [PRIVACY.md](PRIVACY.md)).

If another program already holds UDP port `4455` (or Windows won't open it),
Zanshin keeps listening on TCP, so the Android route below still works. It
says so in its log, and next to the switch it shows *Listening on TCP only —
UDP didn’t open* until something connects. OSC and plain-UDP companions,
PulseOSC included, can't reach it then. It doesn't retry UDP by itself: close
that program, then switch *Listen for heart rate from the watch* off and on.

That app is a **third‑party companion you install on your phone or watch — made by someone else, not part of Zanshin.** It reads
your heart rate there and sends it to Zanshin on this PC. The QR codes
shown in Zanshin are just **download links** to those companion apps (they open
the App Store / Google Play). *Pairing* then means pointing the companion at this
PC on your LAN — port `4455`, unless you changed it in Zanshin. **Zanshin
itself has no mobile app** on any store.
And because that companion is someone else's app, Zanshin can't vouch for what it
does on its own side — so pick one you trust. It's your free choice.

**Android / Wear OS:** *HeartRateOnStream for OBS* (free). The free version
sends heart rate only; steps, which Zanshin uses to stay quiet while you walk,
come only from its premium version.

**iPhone / Apple Watch:** *PulseOSC* (paid) sends OSC,
which Zanshin's code can receive — **but the iPhone route is untested so far:
the author has no Apple device.** PulseOSC costs money, so keep that in mind
before you buy it; if you try it, please let me know whether it works for you
(open an issue). The password, scene and source steps in the app's pairing guide
apply to the Android app only; in PulseOSC you only enter this PC's IP and port.

I've only tested *HeartRateOnStream for OBS* on a real watch. Another
companion may work if it pushes heart rate **to your own network**, straight
to this PC — over **OSC**, plain **UDP** (a bare number or simple JSON), or
**obs‑websocket** (writing the number into a text source); see
[PRIVACY.md](PRIVACY.md). **Zanshin deliberately doesn't connect to cloud
services such as Pulsoid, HypeRate or Stromno (also third‑party):** they route
your heart rate through their own servers, and Zanshin only takes heart rate
sent straight to this PC.

## Prior art & related work

Zanshin isn't the only project near this idea. None of the ones below do the
specific thing Zanshin is built around — *watch your heart rate while you play
and, once your strain has been high for a while, nudge you, holding the voice
for a short pause in your input* — but each solves a neighbouring piece, and it
would be dishonest not to name them.

| Project | What it does | How Zanshin differs |
|---|---|---|
| **[Cardia](https://github.com/uwburn/cardia)** (GPLv3) | Windows heart-rate monitor made for gamers and streamers: reads a Bluetooth heart-rate strap, **shows** your heart rate with a simulated ECG trace, and can raise an alarm (on screen, optionally with a sound) when it goes above or below limits you set. | Closest in spirit — open, runs on your own Windows PC, made for gamers. But Cardia's alarm goes off when your pulse crosses a fixed number; Zanshin looks at strain against your own calm, waits until it has spent a while above your threshold, and holds its voice for a short pause in your input. |
| **Pulsoid · HypeRate · Stromno** | Stream heart rate to an on-screen overlay for your viewers. | Cloud-routed and closed; they exist to **show the number to an audience**. Zanshin keeps it on your machine and uses it to help *you*. (Zanshin doesn't take heart rate from them — they route it through their own servers; see above.) |
| **Pauser** and similar stress apps | Read your heart rate from a smartwatch, alert you when it goes past a limit you set, and walk you through a breathing exercise, on your phone. | Same detect→regulate idea, but not gaming-aware: the alert comes when your pulse passes the limit, mid-fight or not. Zanshin fires only when your strain has spent enough time above a threshold (average-player numbers until it has three play sessions of five minutes or more, about half an hour of heart rate in all, then yours); the voice waits for a short pause in your input and never speaks in the Peak zone. |
| **Unclench** and somatic-reminder scripts | Periodic "drop your shoulders, unclench your jaw" nudges. | Time-based, not body-based. In Zanshin your heart rate decides *whether* a cue is due, and the voice waits for a short pause in your input. |

**In one line:** the tools I found show your heart rate, alert you when it
crosses a number you set, or remind you at set or random times. Zanshin is the
only one I could find that reads your heart rate while you play and holds its
voice for a short pause in your input — on your own PC, and only after your
strain has spent a while above your threshold.

**What Zanshin is deliberately _not_:** a streaming overlay (the small in-game
heart-rate panel can be shown on stream, but it's off by default and not what
Zanshin is for), a fitness tracker, a medical device, or a cloud service. It
shows you no scores, streaks or points, and it never sends your heart rate,
sessions or insights anywhere. The few things that ever touch the network are
listed honestly in [PRIVACY.md](PRIVACY.md). If you know a project that
overlaps more than the ones above, please open an issue — credit where it's
due.

## Run from source (development)

In the folder with `main.py`:

```bash
py -m pip install -r requirements.txt
py main.py
```

It needs Windows and should run on Python 3.10 or newer (I found nothing in
the code that needs a newer one), but I only test 3.14. Run this way, the app
keeps its data next to `main.py`, separate from the built app's
`%APPDATA%\Zanshin`.

## Build the installer (optional)

Players only need to double-click `build.bat` (see *Install* above). For
developers, this is what it does. It runs `build_all.ps1`, which you can also
start directly:

```powershell
powershell -ExecutionPolicy Bypass -File "build_all.ps1"
```

The script (1) checks/installs Python deps and PyInstaller, draws
`Dandurf.ico` if it's missing, and runs `check_before_run.py` — if that finds
a problem, nothing is built; (2) force-closes a running Zanshin without asking
(Windows locks a running `.exe`), deletes the old `dist\Zanshin\` and packages
the app into `dist\` (onedir, no admin manifest, UPX off); and (3) assembles
an installer with Inno Setup 6 into `installer\`, but only if Inno Setup 6 is
installed. I don't publish an installer (see *Install* above); without Inno
Setup the app in `dist\Zanshin\` is ready as it is.

## Tests

With the app's dependencies installed (see above), install the developer
tools first — `requirements-dev.txt` holds pytest and pyflakes — then run the
tests:

```bash
py -m pip install -r requirements-dev.txt
py -m pytest tests/
```

Other developer scripts, run by hand from the repository folder. None of them
is part of the built app:

- `check_before_run.py` — checks what can be checked without opening a
  window: every module parses, every text has all 11 languages (none empty,
  same `{placeholders}`; a text still left in English only gets a note), the
  main window calls no method or colour token that doesn't exist, and no
  keyboard hook or Steam code has come back. With pyflakes installed (the
  developer tools above) it also looks for undefined names; without it, it
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

The repository also holds three developer scripts that test the real window:
`gui_harness_auto.py`, `gui_harness_onboarding.py` and `gui_screenshots.py`.
You start them by hand, with Zanshin closed. The first two use the real mouse
(move, click, drag, scroll) and press Escape, so leave the PC alone while they
run. All three take screenshots of the app's own windows and pictures, with a
small margin around them, into `logs\` by default. While they run, they change
the data of Zanshin run from source next to `main.py`: its settings
(`gui_harness_onboarding.py` deletes them for the run), and for
`gui_harness_auto.py` and `gui_screenshots.py` also its heart-rate history.
They put the originals back at the end. None of them is part of the built app: the build packs `main.py`,
the modules it imports and the `assets` folder, and nothing imports these
scripts.

## License

| What | License | File |
|---|---|---|
| **All of the source code** — including the ensō drawn in code, the colour themes and the layout | **GNU GPL v3.0 or later** — free and open | [`LICENSE`](LICENSE) |
| **Two artwork files** — the app icon (`Dandurf.ico`) and the dojo picture (`assets/images/dojo_noc.webp`) | © Dandurfin — they travel with unmodified copies of the official Zanshin | [`LICENSE-DESIGN.md`](LICENSE-DESIGN.md) |
| **Two sounds** — `sfx_click_reload.wav` and `sfx_lock_ping.wav` in `assets/sounds/modern` | CC0, from Kenney's *Interface Sounds* — their own terms | [`LICENSE-DESIGN.md`](LICENSE-DESIGN.md) |

You may read, run, study, change and pass on the code freely under the GPL.
A modified version has to be clearly marked as different from the original —
its own name, or a plain note that it is a modified version — and use its own
icon and picture. It must not present itself as the official Zanshin or as
made or endorsed by Dandurfin (additional terms under GPLv3 section 7; see
[`LICENSE-DESIGN.md`](LICENSE-DESIGN.md)). This is there to protect the people
who use Zanshin, not to make money.

One thing isn't sorted out yet: `Dandurf.ico` is exactly the ensō that
`make_icon.py` draws from the GPL code (the build redraws it from that code
when the file is missing), and the app draws the same ensō in the tray and in
its window. So it isn't clear yet where the free drawing ends and the icon
that stays mine begins.

Author: **Dandurfin** — [Twitch](https://www.twitch.tv/dandurfin) ·
[YouTube](https://www.youtube.com/channel/UCzZyqQfTNpiGkt_SIOmKO2w) ·
[Kick](https://kick.com/dandurfin)

## Project structure

| File | Purpose |
|---|---|
| `main.py` | Entry point — makes the app DPI-aware, checks that `customtkinter` is installed, sets up crash logging and starts `app.DandurfApp` |
| `app.py` | Main window, wiring for the whole app |
| `app_audio.py` | Part of the main window (a mixin of `DandurfApp`): preparing the built-in sound library, volume and the SFX / voice balance, choosing the voice engine and voice, preparing Edge voice lines ahead of time, and playing a cue's sound, voice or your own recording |
| `app_controls.py` | Part of the main window (a mixin of `DandurfApp`): the command palette (Ctrl+K), "not now" (pausing cues from the shortcut or the tray menu), the collapsible log, gamepad activity, the manual Test cue and showing the introduction again |
| `app_cues.py` | Part of the main window (a mixin of `DandurfApp`): the automatic cue's state shown in the breathing band and on "Today", the "last cue" line, the share of silent cues and the cue ladder step for a new session, and choosing how the app speaks up (cue style) |
| `app_data.py` | Part of the main window (a mixin of `DandurfApp`): export / import / delete of your data, the Data and About panels, what is saved when a session ends and the question after it, sharing a profile as a code, and removing extra cue slots (one or several) |
| `app_history.py` | Part of the main window (a mixin of `DandurfApp`): the "History" page — the trend chart with its metric and period chips, the sessions table, the days-played grid and the detail of one session, the "which cue works" chart, exporting sessions to a spreadsheet (CSV), and the background analysis behind the insights |
| `app_hud.py` | Part of the main window (a mixin of `DandurfApp`): the in-game heart-rate panel (HUD) and its row of 4 icons, the language of what the app draws into the game, choosing the monitor, the heart-rate indicator in the sidebar, pairing the watch, and setting up and testing the in-game visuals |
| `app_prefs.py` | Part of the main window (a mixin of `DandurfApp`): switching language, world (play / work) and theme; loading and saving your settings, volume and balance |
| `app_profiles.py` | Part of the main window (a mixin of `DandurfApp`): the cue slots of the active profile, game profiles (switching, creating, deleting) and the auto-profile (switching to a game's profile while that game runs) |
| `app_session.py` | Part of the main window (a mixin of `DandurfApp`): the heart-rate sensor (its settings, turning it on and off, receiving heart rate, steps and connection state, dropouts, a busy port (TCP is retried, a UDP port that won't open is reported), hiding this PC's IP on screen), opening a measuring session with its thresholds, and the regular ticks: four times a second whether you're at the keyboard (which also drives the cue trigger), once a second the "last cue" line |
| `app_spolocne.py` | Names shared by `app.py` and its mixins (the app logger, language names for the switch, the "not now" shortcut defaults, PIL's `ImageTk`) |
| `app_today.py` | Part of the main window (a mixin of `DandurfApp`): the "Today" page — drawing its animated centre, the live heart-rate, load and session block, delivering the automatic cue, and the "My stats" cards (choosing them, their values, swapping them by dragging) |
| `paths.py` | Where data lives (`%APPDATA%\Zanshin` for the built app, next to `main.py` from source); the built app also copies data over from older versions |
| `settings_model.py` | Slot/settings data model — defaults, normalisation |
| `audio_engine.py` | TTS (Edge Natural + SAPI5) and SFX/recording playback |
| `theme.py` | Colour tokens for Sumi / Aizome modes |
| `i18n.py` | UI translations (11 languages; Czech and Bulgarian in `i18n_cs_bg.py`) |
| `sfx_assets.py` | Built-in SFX library — copies the bundled sounds; download or synthesis only if one is missing |
| `heart_rate.py` | Receiver for heart rate and steps from a companion app — TCP and UDP (OSC included), on port `4455` by default, on every network unless you pick one of this PC's own addresses |
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

### How the main window is split (for developers)

Until the `v0.2.1` tag, the whole main window was one class in one file of
almost 9,000 lines. Since then it is split by topic, and nothing about how the
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

See also **[SAFETY.md](SAFETY.md)** (anti-cheat / no-injection, in Slovak) and
**[PRIVACY.md](PRIVACY.md)** (what is local vs. networked).

---

**[Soul of the app](SOUL.md)**
