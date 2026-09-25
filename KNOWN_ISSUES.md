# Known issues — Zanshin alpha 0.2.1

Zanshin 0.1 was my first public release. In places it promised more than it could
keep, and some things didn't work the way it said they did. Here are the main
points of what I've found so far: what 0.2 fixes, what 0.2.1 fixes after a
review of the 0.2 code, and what's still open. The seven problems named in the
0.1 version of this file are all below.

I'm not a programmer. I build Zanshin with AI and learn as I go. If you spot
something, or know a better way, I'd be glad to hear it. **0.2, partly** means
only part is fixed. Where something stays as it was, such as the online voice
being the default, I say so.

**About 0.1 in this repository's history.** Along with the 0.1 code, some
things went into the repository that didn't belong in public. Nothing
terrible, but not meant to be there. So I set the repository up again: 0.1 is
in the history as it was, only without those things, and 0.2 follows it. That
was the lesson: work stays work, private stays private, and I check every file
before publishing. What 0.1 got wrong in the app itself is written down below.

## What 0.2.1 fixes

0.2.1 is a bug-fix release after a review of the 0.2 code: in a few places it
didn't do what the README says. None of it was harmful as far as I know. It
adds one thing: "Not now" is also in the tray icon's menu. And it changes how
you get Zanshin: there is no installer; the release has a ready-made ZIP with
its SHA-256 fingerprint, or you build the app yourself (see the README).

### The online voice

- **The natural voice also sent lines it would never speak in a game**: the
  wording of switched-off reminders, of ones whose in-game picture is off, of
  ones that play your own recording, and of extra reminders kept from 0.1,
  which the app never fires by itself. **0.2.1:** only the four reminders are
  sent, and of those only the ones switched on, with their picture on, set to
  speak and without your own recording. Switching one or its picture on, or
  removing its recording, prepares it then.
- **Switching to the Windows voice didn't stop preparing that was already
  running**, so its remaining lines still went to Microsoft. The same after
  switching to the sound or picture-only style or to Work, switching a
  reminder or its picture off or creating a profile. **0.2.1:** preparing
  stops at once; only a line already on its way is finished. A new profile's
  lines are now prepared right away too; before, a line not yet in the cache
  played in the Windows voice until something else started preparing.
- **Switching the language to Japanese, Chinese, Russian or Bulgarian also
  switched the natural voice to that language** (while you were on the
  default voice), but your reminders kept their words, for most people
  English ones. The new voice then read English words it may mangle or not
  say at all. **0.2.1:** the voice follows the words, not the menu. Switching
  the language changes it only if the reminders that speak in your current
  profile use that language's built-in words, and a profile created in one of
  these languages gets its voice. A voice other than the default is never
  changed, so if an earlier switch already changed yours, pick it again under
  *Voice* in Settings → Sound. One voice still reads all your profiles, so a
  profile in another language is read by it too.

### Cues and what the app learns

- **A cue could be drawn after only a few seconds of load above the
  threshold.** When your load kept briefly crossing the threshold, the time
  just under it counted towards the hold time (45 s by default). In a test
  with 1 s above and 19 s below, a cue was drawn after a minute with only four
  readings above. **0.2.1:** a short dip below the threshold (under 20 s)
  still doesn't restart the count, but only the time actually above it counts.
- **The "longest stretch" after a session could say you reached the time a
  cue needs, in a session with no cue**, for example after the watch
  disconnected, because the seconds before the dropout was noticed counted
  too. **0.2.1:** it counts only time above the threshold, up to the last
  reading above it: the same number the app uses to decide when to draw.
  Sessions saved before 0.2.1 keep their old, sometimes larger figure.
- **A few short sessions could lower your high heart-rate limit.** In a test,
  three 2-minute pairing sessions at rest moved it from 110 to 80 BPM, and a
  lower limit makes your load read higher and more of your play count as
  Peak. **0.2.1:** the high heart-rate limit, like the load threshold, learns
  only from play sessions of five minutes or more. The resting baseline still
  uses the short ones.
- **"Three sessions of about ten minutes are enough" was true only with an
  almost perfect signal.** The load threshold needed heart rate for about
  91% of those minutes. **0.2.1:** three ten-minute sessions are enough from
  about 82%; three of five minutes still aren't.
- **The README said a session stays in the world it started in**, but your
  answer to *Were you playing or working?* at the end moves it, on purpose.
  **0.2.1:** the code is the same; the README now says so.
- **The cue ladder counted a cue whose picture failed to draw as one you had
  seen**, so after such sessions it could climb back towards the voice.
  **0.2.1:** only cues that actually showed count (a silent picture-only cue
  does).

### "Not now"

- **If another app held Ctrl+Alt+Z, the only way to quiet the cues was to
  stop listening**, which also stops measuring. **0.2.1:** "Not now" is also
  in the tray icon's menu (right-click), and the start-up log line points
  there.

### The heart-rate port

- **Port 4455 could stop taking heart rate until you restarted the sensor.**
  Once its connection limit was full (a port scanner, or a watch that kept
  reconnecting over bad Wi-Fi and left dead connections behind), it stopped
  accepting new ones, even after the old ones closed. **0.2.1:** only the
  extra connection is refused, and heart rate keeps coming in. Silent
  connections are closed: 10 s to finish connecting, and after a minute of
  silence the app pings the other side and closes the connection only if
  nothing answers within another minute, so a quiet but connected watch
  isn't dropped. A single message over 64 KB is refused.
- **If another program held UDP port 4455, heart rate over UDP or OSC (the
  iPhone route) never arrived, and nothing said why**: the status stayed at
  "Connecting...". **0.2.1:** Zanshin keeps listening on TCP, so the Android
  route still works. It says so in its log and shows *Listening on TCP only —
  UDP didn’t open* next to the switch until something connects. It doesn't
  retry UDP: close the other program, then switch *Listen for heart rate
  from the watch* off and on.
- **The log file kept the first 40 raw messages from the watch every time the
  sensor started.** **0.2.1:** 5, which is enough to see what the companion
  sends when pairing doesn't work.

### Your data

- **Import was less strict than the README said.** Only each record's start
  time and length were checked. Other fields were copied unchecked, and one
  wrong value could break the History chart or the CSV export for good.
  NaN/Infinity and impossible dates got through, a file not saved as UTF-8
  ended in a raw error, and there was no size limit. **0.2.1:** files over 50 MB are
  refused, and a file not in UTF-8 gets the "not a valid JSON file" message.
  Every field is checked: a bad field is dropped and the record kept. Records
  with an unusable start time (NaN/Infinity, or a date before 2000 or after
  2100) are skipped and counted. Text the app couldn't save back (broken
  Unicode) is dropped too, so an import can no longer fail halfway through,
  after the backup was taken. The message after an import counts skipped
  records, not dropped fields.
- **Replacing a missing sound from GitHub had no size limit**: the download
  was read whole into memory before its checksum was checked. **0.2.1:** it
  stops above 256 KB. This only happens if one of the bundled sounds is
  missing.

### Smaller fixes

- **The line under the language picker said switching the language also
  changes the sample phrases.** It doesn't: reminders you already have keep
  their wording. **0.2.1:** the line says so.
- **If Zanshin failed while starting, before its window opened, `crash.log`
  recorded nothing**, and a crash while the main window was being built was
  written to it twice. **0.2.1:** both are recorded, each once (in
  `%APPDATA%\Zanshin\logs` for the built app).
- **For people who build from source:** on a Windows PC without internet,
  `check_sources.py` reported every study link as dead. **0.2.1:** it says
  you're offline and checks nothing.

## What 0.1 got wrong, and what 0.2 changed

### Privacy and what's on screen

- **The online voice was the default, while the README and the *Your data* panel
  said nothing is sent.** Your cue texts (never your heart rate) went to
  Microsoft at first start, and mid-game if a line wasn't ready yet, for example
  right after you changed it; only PRIVACY.md listed it. **0.2:** it's still the
  default, but the docs and the app say so, and say when text is sent: after the
  first start and after you change a line, the voice, the speed or the language.
  Nothing is sent while Zanshin is listening; a line that isn't ready plays in
  the Windows voice and is prepared after you stop.
- **Two unneeded downloads.** With the online voice, every launch fetched
  Microsoft's voice list (undocumented), and the first launch fetched two sounds
  from GitHub that the installer already had. Neither request carried personal
  data, though GitHub saw your IP address for nothing. **0.2:** the list is built
  in, and GitHub is contacted only if a sound is missing.
- **Your PC's local IP address was on screen** in the pairing window, where a
  stream or screenshot could show it. **0.2:** it stays hidden until you click
  *Show IP*.
- **Shared profile codes could reveal your Windows user name** through the file
  paths of your own sounds or recordings. **0.2:** codes contain no file paths.
- **The heart-rate port was more open than documented, and × didn't close the
  app.** Port 4455 accepts connections from any network your PC is on, without a
  password, while PRIVACY.md said "local network"; × moved Zanshin to the tray
  without telling you, where it kept the port open and kept measuring.
  **0.2, partly:** the docs say so and advise home network only, and the first ×
  explains the tray. The port is unchanged.
- **The docs described a Steam presence that never ran.** Nothing was ever sent
  to Steam. **0.2:** there's no Steam code at all.

### Safety next to games

- **The colour eyedropper captured the screen, while the docs said "never".** It
  held all your monitors in memory while you picked a pixel; nothing was saved or
  sent. **0.2:** the eyedropper is gone.
- **"Anti-cheat safe" was a promise only anti-cheat makers can give.** The
  technical part (no injection, no hooks, no reading game memory) was true.
  **0.2:** the tag reads "Built to stay out of the game". The panel lists what
  the app does and doesn't do, names the one exception (during the visual test
  the pictures take mouse clicks so you can drag them), and says only the
  anti-cheat's maker can guarantee it won't flag you.
- **The names of running programs were read even with auto-profile off**, every
  4 seconds; nothing was sent. The *Today* page also said the app starts "when a
  game launches", though it knew only four games. **0.2:** with the switch off
  they aren't read (it's still on by default), and the texts name the four
  games.
- **SAFETY.md's "complete" list wasn't complete.** It missed the microphone
  (used only while you record your own cue), your PC's IP addresses (shown for
  pairing) and the monitor list, and misdescribed the controller and walking.
  **0.2, partly:** SAFETY.md and PRIVACY.md have the full list, but SAFETY.md is
  still only in Slovak.
- **Players already on Borderless got a log line telling them to switch to
  Borderless**, because the check can't tell borderless from exclusive
  fullscreen. **0.2, partly:** the log line is now a hedged guess; the check is
  unchanged.

### Your data

- **Import was risky.** The buttons didn't match the text; Replace, which
  overwrites your history, had no second confirmation and didn't back up your
  heart-rate readings; and after a merge the count showed your whole history.
  **0.2:** a clear Merge / Replace / Cancel dialog; Replace asks twice and backs
  up everything it replaces, and the message counts only what was imported.
- **Imported history quietly stayed out of calibration, and "Export everything"
  exported only history.** Moving to a new PC started calibration from zero.
  **0.2:** the note says so (the app can't be sure an export is yours, so this
  stays), and the button is "Export history".
- **The uninstaller didn't name your heart-rate history**, though answering No
  deleted it. **0.2:** the question names it.
- **"Delete history" could leave copies that came back**, if you had used a
  pre-release build or a portable copy. **0.2:** old copies are deleted too.

### Things that didn't work

- **Ordinary gaps between readings counted as dropouts, so the app barely
  spoke.** Any gap over 5 s wiped the build-up to a cue: over several evenings of
  my testing, 194 of 199 build-ups, and one spoken cue in over four hours. The
  end-of-session note also told you to move the watch closer to the PC, though
  the watch talks to the phone. **0.2:** only a gap of 12 s or more counts, and
  the dropout advice follows the real chain: watch to phone to PC.
- **The controller listener never heard a controller.** Windows mostly covered
  for it on my PC, but on a PC where Windows doesn't count controller input, the
  app couldn't tell controller play from a pause at all. Either way, a cue could
  come while you were playing. **0.2:** it hears sticks, triggers, buttons and
  the D-pad.
- **Gyro, or a stick with no deadzone, kept the voice silent without saying
  why**, because input never paused. **0.2:** after 20 minutes without a pause, a
  quiet line on *Today* says what may be causing it (gyro or a stick with no
  deadzone); the app can't change your controller's settings.
- **"Never mid-fight" was more than the app could know.** Its "break" was just
  2.5 s without input, whatever your pulse was doing. **0.2:** the voice also
  waits until your load stops climbing and never speaks in the Peak zone (your
  pulse at or above your high heart-rate limit).
  The README now says a still moment mid-fight can still count as a pause.
- **"Not now" (Ctrl+Alt+Z) ended the whole session**, could pop up the
  questionnaire mid-game and stopped recording heart rate for 30 minutes.
  **0.2:** it only quiets cues.
- **"+ Add trigger" made cues that never spoke, and removing one put texts under
  the wrong picture.** **0.2, partly:** the four categories are fixed and you
  switch one off instead. In a 0.1 profile where you had removed a cue, a text
  can still sit under the wrong picture; a new profile avoids it.
- **The HUD looked confident before it had a baseline.** **0.2:** for the first
  ~30 readings it shows "calibrating…", and cues can't fire.
- **Smaller display bugs.** The cue counter on *Today* always showed 0×, zone
  words meant different things in different places, a dropout looked like not
  being paired, and some choices got reset (visuals you switched off came back
  at every start; replaying the intro reset theme and volume). **0.2:** fixed,
  except that the counter and the *Cues* card can still show different numbers.

### What the app said about itself

- **Insights sounded more certain than the data**, from a 4 BPM change and as
  few as two sessions a week. **0.2, partly:** the texts are hedged and name
  other possible reasons, but what triggers them is mostly unchanged (only the
  session-start insight now needs a pattern unlikely to be chance).
- **Heart-rate recovery was framed as a fitness test**, with norms from
  maximum-effort exercise tests. **0.2:** it's your own rough trend, not a
  fitness score.
- **The Guide stated physiology as fact, with no medical note.** **0.2:** it's
  called "Why it may help", each card says where the idea comes from (a study
  where there is one, otherwise practice or tradition), and it says Zanshin is
  not a medical device: with heart or breathing problems, ask a doctor first.
- **Texts promised effects nobody had measured**, like "trains you to leave the
  match calmer" and a chart called "Which cue works". **0.2, partly:** the texts
  say Zanshin is meant to help, but the chart still colours a pulse drop as good.
- **Claims about the licence and source code weren't true.** The installer had
  no source or GPL text, though About said the source came with it, and the
  README reserved the look and layout for me, although they are GPL code and the
  GPL doesn't allow that. **0.2:** About links to the repository, the licence is
  installed, and all code is under GPLv3 or later; only the icon and the dojo
  picture stay mine.

### Heart-rate sources and pairing

- **Cloud services (Pulsoid, HypeRate, Stromno) were described as usable
  sources**, but Zanshin has no client for them. **0.2:** the docs say Zanshin
  deliberately doesn't use them.
- **The iPhone route was presented as working**, through a paid app I had never
  been able to test, followed by steps that apply only to Android. **0.2:** the
  app and README say it's untested and paid, and that the password, scene and
  source steps are for Android only.
- **Two pairing texts were wrong.** The docs called the QR codes pairing codes,
  but they are store links to other people's companion apps (the captions in the
  app were right). And the pairing guide named the phone source "Heart rate",
  though it's called "Tep" (Slovak for heart rate). **0.2:** corrected; Zanshin
  itself has no mobile app.

### Languages

- **Nine languages, without saying seven were unreviewed AI translations**, some
  out of date. Since the app picks your Windows language on first start, you
  could land in one without being told. **0.2, partly:** now eleven (Czech and
  Bulgarian are new and also unreviewed), and a line under the language picker
  and the README say that all but Slovak are unreviewed AI-assisted
  translations.
- **Japanese, Chinese and Russian cue words went to an English voice, and the
  Ctrl+K palette was in Slovak everywhere.** **0.2:** matching voices (while you
  keep the default voice), and a translated palette.

### Smaller leftovers

- **The old name "DojoSync"** was left in texts and the repository. **0.2,
  partly:** removed, except where needed to import 0.1 exports and find old
  data, and in a few code comments.
- **For people who build from source:** the build skipped two module checks, and
  .gitignore could let your recordings or heart-rate data be committed. The 0.1
  repository also held test scripts (one asked Windows for the state of chosen
  keys) and an unused module with its own port; none was part of the app or the
  installer. **0.2:** fixed, and those scripts and the module are gone. The
  three GUI test scripts that remain (two of them move the mouse, all three take
  screenshots of the app's own windows) are described in the README and
  SAFETY.md.

### Corrections to the 0.1 version of this file

- It said seven languages "fall back to English". None did (a few texts, like
  the Ctrl+K palette, stayed in Slovak instead); they were unreviewed, partly
  outdated AI translations. It also planned to mark them as partial; 0.2
  doesn't, and says instead that every language except Slovak is unreviewed.
- It called the online voice "optional" and said your settings never leave your
  PC; the voice was the default and sent your cue texts out. It also said a
  "Steam build" sends a fixed presence token; no Steam build was released, and
  nothing was sent to Steam.

## Still open — planned for 0.3

As far as I know, none of these is harmful. Some are limits you should know
about, and a few will stay.

- **Zanshin can't see the game.** A pause is about 2.5 s without input, so a still
  moment mid-fight counts, and aiming with gyro means no pause at all.
  Controllers were tested on one PC.
- **Exclusive fullscreen hides the pictures and the HUD** (voice still plays),
  and the app can only guess it. It still counts such a picture as shown, which
  skews the data on cues that stay silent on purpose (see below) and the "HUD
  seen %" export column. Use Borderless.
- **Port 4455 accepts connections from every network your PC is connected to,
  without a password** (only your firewall limits who can reach it), so anything
  that reaches it could send a fake heart rate, or keep all its connections
  busy so your watch can't get in. Allow it on your home network only.
- **Ctrl+Alt+Z is reserved.** While Zanshin runs, even in the tray, a game
  that uses that one key combination may not receive it. In 0.1 the start-up
  log line said input is read with "no blocking"; in 0.2 it names the
  shortcut as the one exception.
- **Zanshin isn't code-signed.** The ready-made ZIP gets Windows' "unknown
  publisher" warning (*More info → Run anyway*); building it yourself avoids
  it. With Smart App Control on, Windows can block unsigned programs
  outright, with no "Run anyway" button. The README says so, but how it
  treats the ZIP or a Zanshin you built yourself is untested.
- **Not a medical device.** Load, recovery and HRPI (one number for how high your
  pulse ran and for how long) are rough trends from a consumer watch, not
  diagnoses, and nothing is clinically validated. This stays.
- **Your data:** imported history never feeds calibration (by design).
  Steps from the watch only keep cues quiet: time you spend walking still
  counts in your saved sessions and in what the app learns from them
  (resting baseline, load threshold, high heart-rate limit).
- **Languages:** no translation has been checked by a native speaker, and
  SAFETY.md is Slovak-only. *In-game language* (what the HUD and captions show;
  English by default, on purpose) is separate from the app language and sits in
  the panel about which screen to draw on, so the two are easy to mix up.
- **The iPhone / Apple Watch route** is still untested.
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
- **Texts and controls:** a few explanations and settings texts claim a bit more
  than the code does, onboarding misdescribes where the pictures sit, and the
  "not now" shortcut can't be changed in the app (since 0.2.1, "Not now" is
  also in the tray icon's menu). If Windows is slow at start-up, the log can
  say another app holds the shortcut even though it works a moment later.

## How to help

Found something that doesn't work as it says, or know a better way? Please open
an issue: <https://github.com/Dandurfin/Zanshin/issues>. A plain description is
enough. I'd especially welcome native speakers for the translations, anyone who
tries the iPhone route, reports from other controllers, and advice on code
signing, anti-cheat or heart-rate data.

Please don't post heart-rate files or logs publicly: heart-rate files are health
data, and logs can name your devices and files. Describe what you saw instead.

— **Dandurfin** · GPLv3 or later
