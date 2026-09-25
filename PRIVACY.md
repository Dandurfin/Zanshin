# Privacy — what stays on your machine, and what can leave

Zanshin is built to keep your data on your computer. This page is deliberately
precise: instead of a blanket "nothing ever leaves", it states exactly what is
local and the few things that can touch the network, so the claim holds up.

## Your health and usage data never leave your machine

The following are written **only** to local files and are **never transmitted**
anywhere:

- **Heart-rate readings** received from your phone/watch (and steps or speed,
  if your watch app sends them),
- **Session history** (`hr_sessions.json`),
- **Insights and baselines** (`hr_insights.json`),
- **Measurement windows / raw events** (`hr_windows.json`, `hr_events.jsonl`),
- **Your recorded audio.** The microphone is used only while you record your
  own voice for a reminder — it switches on when you click **Record** on a
  reminder card, and the recording stays in the local `audio/` folder,
- **Settings** — with one exception: the **wording of your spoken reminders**,
  which the online voice sends to Microsoft to turn into speech (see
  *Text-to-speech* below),
- **Logs / crash log** (kept in a local file — there is **no** remote crash
  reporting).

Run from source (`python main.py`), these live next to the program; in the
built app (`Zanshin.exe`) they live in `%APPDATA%\Zanshin`. There is **no telemetry, no analytics, and no
update-checker** anywhere in the app.

## The few things that can use the network

1. **Text-to-speech — the online voice is the default.**
   Zanshin has two TTS engines (*Settings → Sound → Voice comes from*):
   - **Natural voice (Edge)** — online, and **selected by default**. To turn a
     spoken reminder into speech, the app sends **the text of that reminder**
     (e.g. "breathe out"), the chosen voice and the speed to Microsoft's speech
     service, then **caches the clip locally**. Your heart rate, sessions and
     insights are never sent. The text is the wording of your reminders — the
     built-in ones, or whatever you type yourself. As with any connection,
     Microsoft sees your IP address.
     - **Which reminders:** only those of the four in your current profile
       that are switched on, set to speak and don't play your own recording.
       A switched-off reminder, one that plays your own recording and an
       extra reminder kept from a 0.1 profile are never sent (testing a
       switched-off or extra one plays the Windows voice). A reminder whose
       in-game picture you've switched off still counts as switched on, so
       its line is prepared, although the app never fires it by itself.
     - **When:** after the first start (the default reminders), and after that
       only for lines that aren't in the cache yet — at every start (for
       example a line still waiting when you quit), after you change a
       reminder's wording, switch a reminder on, switch it to speak or remove
       its own recording, change the voice, the speed, the language or the
       profile (or create one), import a profile, switch back to the voice
       style, to Play or to the natural voice, when you test a reminder whose
       line isn't ready, or
       when you ask for all voices to be prepared again (the *Ctrl+K* command
       palette).
     - **Only if your reminders actually speak.** With the *sound* or
       *picture only* style, and in the *Work* world, nothing is prepared and
       nothing is sent. The style you picked decides, so lines are still
       prepared while the app has quietened itself to picture only or a
       pause.
     - **Switching away stops it.** If you switch a reminder off, give it
       your own recording, change or create a profile, or switch to the
       *sound* or *picture only* style, to *Work* or to the Windows voice
       while lines are being prepared, preparing stops at once; only the line
       already on its way is finished.
     - **Never while Zanshin is listening** — whether you started listening
       or a game did (automatic profile switching). Whatever would need
       preparing then, including a line you change mid-game, waits until you
       stop listening; a reminder whose line isn't ready plays in the Windows
       voice. If listening starts while lines are being prepared, only the
       line already on its way is finished.
     - **On the very first start** Zanshin starts listening by itself right
       after the introduction, so preparing stops almost at once and the rest
       of the lines are prepared after you stop listening for the first time.
       Until then they play in the Windows voice.
     - The list of voices is built into the app; it is not downloaded.
   - **Windows voice (works offline)** — synthesises entirely on your PC, so
     **nothing leaves at all**. Choose it in *Settings → Sound → Voice comes
     from* if you want even your reminder wording to stay local.

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
   PC's own addresses under **IP address** in *In-game → Watch and heart
   rate*; an address the PC doesn't have falls back to all interfaces, and the
   log says so), and **without a password**:
   anything that can reach that port could send it a heart-rate value.
   - **When it's open:** the port stays closed until you switch on *Listen
     for heart rate from the watch* (*In-game → Watch and heart rate*) or open
     the pairing guide (*Pair your watch* or *How to pair your watch…*), which
     switches it on too. From then on it's open whenever Zanshin runs — also
     while it sits in the tray, and again at every start — until you switch
     it off (the app also switches it off if it can't open the TCP port).
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
     **Show IP** toggle reveals it (until the app restarts).

5. **No Steam.** Zanshin has no Steam integration — it doesn't load the Steam
   SDK or talk to Steam in any way.

## A note on your phone/watch sensor app

**The companion app isn't ours — and the choice is yours.** The app that reads your
heart rate on your phone or watch is made by someone else, whatever it uses to reach
Zanshin (obs-websocket, OSC or plain UDP). Zanshin only *listens* for heart rate
sent straight to this PC and never uploads it — but what a companion does on its own side
(whether it also keeps a copy in its own cloud, what its own privacy policy says) is
between you and that app. We can't vouch for it, and we won't lock you into one.

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
same licence (GPLv3 or later), clearly marked as its own version and not the
official Zanshin (see [`LICENSE-DESIGN.md`](LICENSE-DESIGN.md)).

---

See also [`SAFETY.md`](SAFETY.md) (in Slovak for now) for the anti-cheat /
no-injection details (no memory reads, no keyboard hook, no screen capture).
