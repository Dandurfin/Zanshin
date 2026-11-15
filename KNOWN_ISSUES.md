# Known issues — Zanshin alpha 0.3

What doesn't work yet, or works only partly. What each version changed is in
[CHANGELOG.md](CHANGELOG.md).

I'm not a programmer. I build Zanshin with AI and learn as I go. If you spot
something, or know a better way, I'd be glad to hear it. Where something stays
as it is, such as the online voice being the default, I say so.

## Still open (some planned for a later version, some by design)

As far as I know, none of these is harmful. Some are limits you should know
about, and a few will stay.

- ***Update voice* can't fix everything** (0.3). It helps only when a newer
  `edge-tts` fixes the problem and works with the libraries inside your
  Zanshin; otherwise it says a newer Zanshin is needed and keeps the current
  voice. It trusts PyPI and the `edge-tts` project: what its checks don't
  protect against is in [SAFETY.md](SAFETY.md). So far it has been tested
  against a simulated PyPI and a simulated test word, and in a real update
  (the real PyPI, a real test word) only from source and in a test program
  packaged like Zanshin, not yet in a released Zanshin.
- **Zanshin can't see the game.** A pause is about 2.5 s without input, so a still
  moment mid-fight counts, and aiming with gyro means no pause at all.
  Controllers were tested on one PC.
- **Exclusive fullscreen hides the pictures and the heart-rate panel** (voice
  still plays), and the app can only guess it. It still counts such a picture
  as shown, which skews the data on cues that stay silent on purpose (see
  below) and the "HUD seen %" export column. Use Borderless. From 0.3 the
  questions after a Play session with a cue say so when the guess fired.
- **Port 4455 accepts connections from every network your PC is connected to,
  without a password** (only your firewall limits who can reach it), so anything
  that reaches it could send a fake heart rate, or keep all its connections
  busy so your phone can't get in. Allow it on your home network only.
- **The "not now" shortcut is reserved.** While Zanshin runs, even in the
  tray, a game that uses that one key combination may not receive it. It's
  Ctrl+Alt+Z by default; from 0.3 you can pick another or switch it off in
  Settings → General → *Keyboard shortcut*, and "Not now" is also in the tray
  icon's menu. In 0.1 the start-up log line said input is read with "no
  blocking"; in 0.2 it names the shortcut as the one exception. If Windows
  takes more than two seconds to register the shortcut at start-up, its line
  in Settings already says it works while Windows hasn't confirmed it yet; the
  line and the log follow Windows' answer once it comes.
- **Zanshin isn't code-signed.** The ready-made ZIP gets Windows' "unknown
  publisher" warning (*More info → Run anyway*); building it yourself avoids
  it. With Smart App Control on, Windows can block unsigned programs
  outright, with no "Run anyway" button. On my PC, with it on, Windows ran
  the 0.3 Zanshin I built but blocked my older 0.2.1 build. How it treats
  the downloaded ZIP is untested.
- **Not a medical device.** Load, heart rate recovery and HR persistence (one
  number for how high your pulse ran and for how long) are rough trends from a
  consumer watch, not diagnoses, and nothing is clinically validated. This
  stays.
- **Your data:** imported history never feeds calibration (by design).
  Steps from the watch only keep cues quiet: time you spend walking still
  counts in your saved sessions and in what the app learns from them
  (resting baseline, load threshold, high heart-rate limit).
- **Languages:** no translation has been checked by a native speaker, and
  SAFETY.md is in Slovak apart from its English summary at the top.
  *In-game language* (what the heart-rate panel and captions show; English by
  default, on purpose) is separate from the app language and sits in the panel
  about which screen to draw on, so the two are easy to mix up. The tour's
  bubbles and the Ctrl+K list still use a fixed Latin font, so Japanese and
  Chinese text there comes out in whatever font Windows substitutes, not the
  one the rest of the window uses.
- **Untested:** the iPhone / Apple Watch route. Two checks new in 0.3 were
  tested only with simulated data, never on a PC with that setup: how the
  pairing guide recognises VPN and virtual network adapters (including
  Windows' Mobile hotspot and a Hyper-V external switch), and whether the
  "not now" shortcut would type a letter on one of your keyboard layouts,
  such as ż on a Polish one.
- **The voice-versus-picture comparison isn't shown yet**, though some cues stay
  silent on purpose to collect it (about one in four in the first 15 sessions,
  then one in ten). When it comes, it will compare voice plus picture with
  picture only, not a cue with no cue.
- **Numbers and labels:** the cue chart colours a pulse drop as good, some notes
  are simpler than the math or name the wrong time span or unit, and the CSV
  export is half-translated. A cue whose picture failed to draw (rare; the log
  says so) is counted two ways: History, the CSV "breathing" column, insights
  and the cue card on *Today* count it, while the questionnaire, the cue
  ladder and "not now" treat it as not shown, even if its voice played.
- **Texts and controls:** a few explanations and settings texts may still
  claim a bit more than the code does (0.3 rewrote many of them). The
  pairing guide's boxes *Watch won’t connect at all?* and *Watch connects
  but no heart rate?* name the watch, though what connects to Zanshin is
  the phone app. In the Work world, History without sessions still asks you
  to play for at least a minute, and the hint under *One session up close*
  still says when you were probably playing.
- **The icon's licence:** `Dandurf.ico` is the same ensō that `make_icon.py`
  draws from the GPL code, so it isn't clear yet where the free drawing ends
  and the icon that stays mine begins (see [LICENSE-DESIGN.md](LICENSE-DESIGN.md)).
- **No clip of a cue over a game yet.** The README shows Zanshin's own window
  only; a short GIF of a cue over a game in Borderless is still missing.

## How to help

Found something that doesn't work as it says, or know a better way? Please open
an issue: <https://github.com/Dandurfin/Zanshin/issues>. A plain description is
enough. I'd especially welcome native speakers for the translations, anyone who
tries the iPhone route, reports from other controllers, and advice on code
signing, anti-cheat or heart-rate data.

Please don't post heart-rate files or logs publicly: heart-rate files are health
data, and logs can name your devices and files. Describe what you saw instead.

## What changed in each version

What 0.3 changes, what 0.2.1 fixed and what 0.1 got wrong:
[CHANGELOG.md](CHANGELOG.md).

— **Dandurfin** · GPLv3
