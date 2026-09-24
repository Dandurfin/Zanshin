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

In development these live next to the program; in the installed build they live
in `%APPDATA%\Zanshin`. There is **no telemetry, no analytics, and no
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
     - **When:** after the first start (the default reminders), and after that
       only for lines that aren't in the cache yet — after you change a
       reminder's wording, the voice, the speed, the language, the profile or
       the reminder style, when you test a reminder whose line isn't ready, or
       when you ask for all voices to be prepared again (the *Ctrl+K* command
       palette).
     - **Only if your reminders actually speak.** With the *sound* or
       *picture only* style, and in the *Work* world, nothing is prepared and
       nothing is sent.
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
   the app; on first launch the installed app copies them into its data folder.
   Only if one is missing (for example a damaged install) does the app replace
   it: two small CC0 sounds are fetched from GitHub
   (`raw.githubusercontent.com`, checksum-verified — like any download, GitHub
   sees your IP address, and the request names the app), the rest are
   synthesised locally. If that download fails, those two are synthesised too.

3. **Opening links.** Clicking a creator link, the link to the source code on
   GitHub or a cited research link opens the page in your default browser —
   only when you click it. No app data is added
   to the request.

4. **The heart-rate port on your network.** To receive your heart rate, Zanshin
   **listens** on port `4455` — TCP (obs-websocket) and UDP (OSC / plain UDP)
   — on **all of your PC's network interfaces** (unless you enter one of this
   PC's own addresses in the heart-rate sensor settings; an address the PC
   doesn't have falls back to all interfaces, and the log says so), and
   **without a password**:
   anything that can reach that port could send it a heart-rate value. It only
   **receives** — it never sends your heart rate out. What keeps other
   networks out is your **firewall**: Windows asks about it the first time you
   turn on the heart-rate sensor (or pair your watch). Allow it on your
   private home network, not on public networks. The app hides your PC's IP
   address on screen by default, so it doesn't end up on a stream or in a
   screenshot; the **Show IP** toggle reveals it (until the app restarts).

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
same GPLv3, clearly marked as its own version and not the official Zanshin (see
[`LICENSE-DESIGN.md`](LICENSE-DESIGN.md)).

---

See also [`SAFETY.md`](SAFETY.md) (in Slovak for now) for the anti-cheat /
no-injection details (no memory reads, no keyboard hook, no screen capture).
