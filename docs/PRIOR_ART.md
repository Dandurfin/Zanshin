# Prior art and related work

Zanshin isn't the only project near this idea. None of the ones below do the
specific thing Zanshin is built around — *watch your heart rate while you play
and, once your strain has been high for a while, nudge you, holding the voice
for a short pause in your input* — but each solves a neighbouring piece, and it
would be dishonest not to name them.

| Project | What it does | How Zanshin differs |
|---|---|---|
| **[Cardia](https://github.com/uwburn/cardia)** (GPLv3) | Windows heart-rate monitor made for gamers and streamers: reads a Bluetooth heart-rate strap, **shows** your heart rate with a simulated ECG trace, and can raise an alarm (on screen, optionally with a sound) when it goes above or below limits you set. | Closest in spirit — open, runs on your own Windows PC, made for gamers. But Cardia's alarm goes off when your pulse crosses a fixed number; Zanshin's cues look at strain against your own calm, wait until it has spent a while above your threshold, and hold the voice for a short pause in your input. One thing in Zanshin does work like Cardia's alarm: the breath ring at high heart rate (from 0.3.2, off by default) shows while your pulse is above a number you set, mid-fight or not. It's silent and a ring to breathe with, but it follows that number, not your strain. |
| **Pulsoid · HypeRate · Stromno** | Stream heart rate to an on-screen overlay for your viewers. | Cloud-routed and closed; they exist to **show the number to an audience**. Zanshin keeps it on your machine and uses it to help *you*. (Zanshin doesn't take heart rate from them — they route it through their own servers.) |
| **Pauser** and similar stress apps | Read your heart rate from a smartwatch, alert you when it goes past a limit you set, and walk you through a breathing exercise, on your phone. | Same detect→regulate idea, but not gaming-aware: the alert comes when your pulse passes the limit, mid-fight or not. Zanshin's cues come only when your strain has spent enough time above a threshold (average-player numbers until it has three play sessions of five minutes or more, about half an hour of heart rate in all, then yours); the voice waits for a short pause in your input and never speaks in the Peak zone. The exception is the breath ring at high heart rate (from 0.3.2, off by default): like Pauser's alert, it comes when your pulse passes a limit you set, mid-fight or not, and it shows in the Peak zone too, silently, on your PC's screen. |
| **Unclench** and somatic-reminder scripts | Periodic "drop your shoulders, unclench your jaw" nudges. | Time-based, not body-based. In Zanshin your heart rate decides *whether* a cue is due, and the voice waits for a short pause in your input. |

**In one line:** the tools I found show your heart rate, alert you when it
crosses a number you set, or remind you at set or random times. Zanshin is the
only one I could find that reads your heart rate while you play and holds its
voice for a short pause in your input — on your own PC, and only after your
strain has spent a while above your threshold. (If you switch it on, its
breath ring at high heart rate does show, silently, while your pulse is above
a number you set.)

**What Zanshin is deliberately _not_:** a streaming overlay (the small in-game
heart-rate panel can be shown on stream, but it's off by default and not what
Zanshin is for), a fitness tracker, a medical device, or a cloud service. It
shows you no scores, streaks or points, and it never sends your heart rate,
sessions or insights anywhere. The few things that ever touch the network are
listed honestly in [PRIVACY.md](../PRIVACY.md). If you know a project that
overlaps more than the ones above, please open an issue — credit where it's
due.
