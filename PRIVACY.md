# Privacy — what stays on your machine, and what can leave

Zanshin is built to keep your data on your computer. This page is deliberately
precise: instead of a blanket "nothing ever leaves", it states exactly what is
local and the few things that can touch the network, so the claim holds up.

## Your health and usage data never leave your machine

The following are written **only** to local files and are **never transmitted**
anywhere:

- **Heart-rate readings** received from your phone/watch (and steps or speed,
  if your watch app sends them),
- **Session history** (`hr_sessions.json`), and two files that keep a
  session from getting lost:
  - `hr_session_open.json`, a copy of the session still running, written
    every 5 minutes. It's deleted once the session is saved; if Zanshin ended
    without saving it (a crash, a power cut), the next start adds the copy
    to your history and then deletes it.
  - `hr_session_pending.json`, sessions that couldn't be saved (a full disk,
    a locked file). Zanshin adds them to your history at the next start, or
    right after the next session that saves, and then deletes the file. If
    it can't read that file, it doesn't delete it but keeps it as
    `hr_session_pending.json.corrupt-<time>`; a history file it can't read
    is kept the same way, as `hr_sessions.json.corrupt-<time>`,
- **Insights and baselines** (`hr_insights.json`),
- **Measurement windows / raw events** (`hr_windows.json`, `hr_events.jsonl`),
- **Backups before an import** (`<file>.pred-importom-<time>.bak`, next to
  the files the import replaced),
- **Your recorded audio.** The microphone is used only while you record your
  own voice for a cue — it switches on when you click **Record** on a cue
  card, and the recording stays in the local `audio/` folder. A sound file
  you pick for a cue is copied there too,
- **Prepared voice clips** (`audio/tts_cache`): your cue wording spoken by
  the natural voice, kept so cues play without the network,
- **Settings**, and their backup (`dandurf_settings.json.bak`; a settings
  file that can't be read is kept as
  `dandurf_settings.json.corrupt-<date>-<time>`) — with one exception: the
  **wording of your spoken cues**, which the natural voice sends to
  Microsoft to turn into speech (see *Text-to-speech* below),
- **Logs / crash log** (`logs/app.log` with its older copies, and
  `logs/crash.log` — local files only; there is **no** remote crash
  reporting).

Run from source (`python main.py`), these live next to the program; in the
built app (`Zanshin.exe`) they live in `%APPDATA%\Zanshin`. **Open the data
folder** under *Settings → General → Your data* opens that folder, and
**Delete history** there deletes the session, insight and measurement files
above with their backups, the prepared voice clips, the crash log and older
logs (not your settings or recordings). There is **no telemetry, no
analytics, and no update-checker** anywhere in the app.

## The few things that can use the network

1. **Text-to-speech — the natural voice is the default.**
   Zanshin has two voices (*Settings → Sound → Voice source*):
   - **Natural (online, Microsoft)** — online, and **selected by default**. To
     turn a spoken cue into speech, the app sends **the text of that cue**
     (e.g. "Breathe out"), the chosen voice and the speed to Microsoft's
     speech service, then **caches the clip locally**. Your heart rate,
     sessions and insights are never sent. The text is the wording of your
     cues — the built-in ones, or whatever you type yourself. As with any
     connection, Microsoft sees your IP address.
     - **Which cues:** only those of the four in your current profile
       that are switched on, have their in-game picture on, are set to speak
       and don't play your own recording. A cue that is switched off or
       has its picture off, one that plays your own recording and an extra
       cue kept from a 0.1 profile are never sent (testing one that is off,
       has its picture off or is an extra one plays the Windows voice).
     - **When:** after the first start (the default cues), and after that
       only for lines that aren't in the cache yet — at every start (for
       example a line still waiting when you quit), after you change a
       cue's wording, switch a cue or its picture on, switch it to speak or
       remove its own recording, change the voice, the speed, the language or
       the profile (or create one), import a profile, switch back to
       *Voice, sound and picture*, to Play or to the natural voice, when you
       test a cue whose line isn't ready, or when you ask for the voice to be
       prepared again (*Prepare the cue voice* in the *Ctrl+K* command
       palette, or, from 0.2.2, *Try again* under *Voice source* after
       preparing failed).
     - **Only if your cues actually speak.** With *Sound and picture* or
       *Picture only* (*Settings → Sound → How I speak up*), and in the *Work*
       world, nothing is prepared and nothing is sent. The style you picked
       decides, so lines are still prepared while the app has quietened
       itself to picture only or a pause.
     - **Switching away stops it.** If you switch a cue or its picture off,
       give it your own recording, change or create a profile, or switch to
       *Sound and picture* or *Picture only*, to *Work* or to the Windows voice
       while lines are being prepared, preparing stops at once; only the line
       already on its way is finished.
     - **Never while Zanshin is watching** — whether you started it or a game
       did (automatic profile switching). Whatever would need preparing then,
       including a line you change mid-game, waits until you stop watching; a
       cue whose line isn't ready plays in the Windows voice. If watching
       starts while lines are being prepared, only the line already on its way
       is finished.
     - **On the very first start** Zanshin starts watching by itself after
       the introduction, but (from 0.2.2) only once the lines are prepared,
       or after about 15 seconds at most. Lines that aren't ready by then
       (for example offline) are prepared after you stop it for the first
       time or at the next start; until then they play in the Windows voice.
     - The list of voices is built into the app; it is not downloaded.
   - **Windows (offline)** — synthesises entirely on your PC, so **nothing
     leaves at all**. Choose it in *Settings → Sound → Voice source* if you
     want even the wording of your cues to stay local. The voice preview in
     the introduction always uses it (from 0.2.2).

2. **Built-in sounds — normally nothing.** The eight sound effects ship with
   the app; on first launch the built app copies them into its data folder.
   Only if one is missing (for example a damaged build) does the app replace
   it: two small CC0 sounds are fetched from GitHub
   (`raw.githubusercontent.com`, checksum-verified, and the download stops if
   it grows past 256 KB — like any download, GitHub sees your IP address, and
   the request names the app), the rest are
   synthesised locally. If that download fails, those two are synthesised too.

3. **Opening links.** Clicking a creator link, the link to the source code on
   GitHub or a cited research link opens the page in your default browser —
   only when you click it. No app data is added
   to the request.

4. **The heart-rate port on your network.** To receive your heart rate, Zanshin
   **listens** on port `4455` — TCP (obs-websocket) and UDP (OSC / plain UDP)
   — on **all of your PC's network interfaces** (unless you enter one of this
   PC's own addresses under **Network address (advanced)** in *In-game →
   Watch and heart rate*; an address the PC doesn't have falls back to all
   interfaces, and the log says so), and **without a password**:
   anything that can reach that port could send it a heart-rate value.
   - **When it's open:** the port stays closed until you switch on *Receive
     heart rate from the phone* (*In-game → Watch and heart rate*) or open
     the pairing guide (*Pair your watch* or *How to pair your watch…*), which
     switches it on too. From then on it's open whenever Zanshin runs — also
     while it sits in the tray, and again at every start — until you switch
     it off. If the app can't open the TCP port, it stops trying until the
     next start or until you change the port, but your setting stays on.
   - **What it sends back:** only what the connection needs. On TCP it
     pretends to be OBS (the obs-websocket replies, and a ping after a minute
     of silence); on UDP it replies nothing. It **never sends your heart rate
     out** and never connects anywhere by itself.
   - **If UDP won't open** (another program holds the port, or Windows
     refuses it), Zanshin keeps listening on TCP only. Once per start of the
     listener it says so in the log in its window and writes one warning to
     the local `app.log`: the port number and Windows' error message, not
     your PC's address.
   - What keeps other networks out is your **firewall**: Windows asks about
     it the first time the port opens. Allow it on your private home network,
     not on public networks. The app hides your PC's IP address on screen by
     default, so it doesn't end up on a stream or in a screenshot; the
     **Show IP** button in the pairing guide (a switch next to the *Network
     address (advanced)* field) reveals it until you hide it again or the app
     restarts.

5. **No Steam.** Zanshin has no Steam integration — it doesn't load the Steam
   SDK or talk to Steam in any way.

## A note on your phone/watch sensor app

**The companion app isn't part of Zanshin — and the choice is yours.** The app
that reads your heart rate on your phone or watch is made by someone else,
whatever it uses to reach Zanshin (obs-websocket, OSC or plain UDP). Zanshin
only *receives* heart rate sent straight to this PC and never uploads it — but
what a companion does on its own side (whether it also keeps a copy in its own
cloud, what its own privacy policy says) is between you and that app. I can't
vouch for it, and Zanshin won't lock you into one.

Zanshin deliberately doesn't connect to cloud heart-rate services (for example
Pulsoid, HypeRate, Stromno): they route your heart rate through their own
servers, and Zanshin only takes heart rate sent straight to this PC. For a fully local
chain, pick a companion that sends heart rate over your **local network** —
obs-websocket, OSC or plain UDP.

## App-store QR codes

The QR codes shown in Zanshin are **download links** to **third‑party companion
apps — made by someone else, not part of Zanshin** on the App Store / Google Play — the apps that read your heart
rate on your phone or watch and send it to this PC. They aren't a pairing
mechanism in themselves; *pairing* just means pointing that companion at this PC
on your local network. **Zanshin has no mobile app of its own** on any store; a
mobile port, if it ever exists, would be a separate community effort under the
same licence (GPLv3), clearly marked as its own version and not the
official Zanshin (see [`LICENSE-DESIGN.md`](LICENSE-DESIGN.md)).

---

See also [`SAFETY.md`](SAFETY.md) (in Slovak, with an English summary at the
top) for the anti-cheat / no-injection details (no memory reads, no keyboard
hook, no screen capture).
