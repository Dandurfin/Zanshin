# Privacy — what stays on your machine, and what can leave

Zanshin is built to keep your data on your computer. This page is deliberately
precise: instead of a blanket "nothing ever leaves", it states exactly what is
local and the few things that can touch the network, so the claim holds up.

## Your health and usage data never leave your machine

The following are written **only** to local files and are **never transmitted**
anywhere:

- **Heart-rate readings** received from your phone/watch,
- **Session history** (`hr_sessions.json`),
- **Insights and baselines** (`hr_insights.json`),
- **Measurement windows / raw events** (`hr_windows.json`, `hr_events.jsonl`),
- **Settings** and **your recorded audio**,
- **Logs / crash log** (kept in a local file — there is **no** remote crash
  reporting).

In development these live next to the program; in the installed build they live
in `%APPDATA%\Zanshin`. There is **no telemetry, no analytics, and no
update-checker** anywhere in the app.

## The few things that can use the network

1. **Text-to-speech (only the reminder text, only with the online voice).**
   Zanshin has two TTS engines:
   - **Edge Natural** (online) — when you set or edit a spoken reminder, the
     **text of that phrase** (e.g. "breathe out") is sent to Microsoft's TTS
     service to synthesise the clip, which is then **cached locally**. Only the
     phrase text, the chosen voice, and the speed are sent — **never your heart
     rate or any personal data**. During gameplay nothing is sent; the cached
     local audio is played.
   - **System voice (SAPI5)** (offline) — synthesises entirely on your PC, so
     **nothing leaves at all**. Choose this in *Settings → Sound* if you want
     even your reminder wording to stay local.

2. **First-run sound download.** On first launch the app tries to fetch **two**
   small CC0 sound effects from GitHub (`raw.githubusercontent.com`). Like any
   download, GitHub sees your IP address. Each file is checksum-verified, and if
   you are offline the app **synthesises the sounds locally** instead.

3. **Opening links.** Clicking a creator link or a cited research link opens the
   page in your default browser — only when you click it. No app data is added
   to the request.

4. **Local-network heart-rate port.** To receive your heart rate, Zanshin
   **listens** on your local network (port `4455`) so your phone/watch app can
   push readings to it. It only **receives** — it never sends your heart rate
   out. Your firewall may ask you to allow this on first run.

5. **Steam (Steam build only).** If you run a Steam build, Zanshin can set a
   fixed Rich Presence status ("Listening" / "Idle") — a non-personal token, no
   heart-rate or session data. It is optional and does nothing without the Steam
   SDK and an App ID. (The open-source GitHub build does not include Steam.)

## A note on your phone/watch sensor app

Zanshin's receiver is local-network only and never uploads your heart rate.
However, the **companion app you choose** to send heart rate from your phone or
watch may route it through **its own cloud** (for example Pulsoid, HypeRate,
Stromno). That is outside Zanshin's control. If you want a fully local chain,
prefer an app that sends heart rate over **OSC on your local network**.

## App-store QR codes

The QR codes shown in the app are for **pairing a companion sensor on your local
network** — they are **not** links to the App Store or Google Play. As of
alpha 0.1 there is **no mobile version** of Zanshin on any app store; a mobile
port, if it ever exists, would be a separate community effort (and would need
the author's consent to reuse the design — see [`LICENSE-DESIGN.md`](LICENSE-DESIGN.md)).

---

See also [`SAFETY.md`](SAFETY.md) for the anti-cheat / no-injection details
(no memory reads, no keyboard hook, no screen capture).
