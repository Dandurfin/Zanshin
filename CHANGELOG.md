# Changelog — Zanshin

What each version changed, newest first: 0.2.2 (in the code here, not
released yet), 0.2.1, and what 0.1 got wrong. What doesn't work yet, or works
only partly, is in [KNOWN_ISSUES.md](KNOWN_ISSUES.md).

**0.2, partly** means only part was fixed. Where something stayed as it was,
such as the online voice being the default, I say so.

## What 0.2.2 changes (not released yet)

These are in the code here, not in a release yet: the 0.2.1 ZIP doesn't
have them.

### Heart rate, the window and your data

- **The heart-rate number could jump by several BPM within one second.** Some
  companion setups write two different heart rates into the same source; in
  mine, one ran 5 to 10 BPM below the other. The number showed whichever came
  last. **0.2.2:** the heart-rate panel in the game, *Today* and the line next
  to the switch show the median of the last 3 seconds of readings. Measuring
  doesn't change: load, zones and saved sessions still use every reading.
- **Nothing told you the companion was sending two heart rates**, and both
  went into your measurements. **0.2.2:** when the readings in one source keep
  jumping between two values, Zanshin says so in its log and shows *Two
  different heart rates in one source — check the watch app* next to the
  switch while heart rate comes in, until heart-rate receiving is switched off
  or restarted. It doesn't separate the two; the fix is in the companion's
  settings: only the live heart rate should write into the heart-rate source.
- **Starting Zanshin a second time could switch heart rate off for good.** ×
  only hides Zanshin in the tray, and on Windows 11 the tray icon is often
  hidden under the ^ arrow, so it was easy to start it again. The second copy
  couldn't open the heart-rate port (the first one held it), gave up and saved
  heart-rate receiving as off, so the next start didn't receive heart rate
  either. Any other port error saved it as off too. **0.2.2:** a second
  start just shows the window of the copy already running (if it can't, it
  says where to find it). If the port is busy or won't open, the switch goes
  off for that run only: your setting stays on and the next start tries
  again, and so does changing the port. The log line about a busy port names
  the usual cause (OBS with its WebSocket server on) and the fix.
- **The window didn't fit smaller laptop screens.** It has one fixed size and
  can't be resized or maximized, so on 1920×1080 at 150 % or on 1366×768 its
  bottom, with *Settings* in the sidebar, ended up under the taskbar.
  **0.2.2:** Zanshin opens on the screen with the mouse pointer, centred in
  the space the taskbar leaves free. If the window doesn't fit there, the
  whole interface gets smaller until it does, down to 70 % at most; if even
  that isn't enough, the title bar stays at the top of the screen. Where the
  window already fits, its size stays as it was. The smaller size stays until
  the next start, even if you move the window to a bigger screen.
- **Shutting down the PC threw away the whole session**, and so did a crash,
  ending Zanshin in Task Manager, a power cut or `build.bat` closing it: a
  session was saved only when it ended normally. **0.2.2:** when Windows shuts
  down, restarts or signs you out, Zanshin saves the session and your settings
  first, without the questions at the end. If the shutdown is then cancelled,
  it goes on measuring in a new session after about 20 seconds. While a
  session runs, Zanshin also keeps a copy of it every 5 minutes
  (`hr_session_open.json`, next to `hr_sessions.json`). If Zanshin ends any
  other way, the next start adds that
  copy to your history and says so in the log. Its last few minutes are
  missing, and so are its cue records and measurement windows, which are only
  written when a session ends. You see it in History, but the load threshold,
  high heart-rate limit and resting baseline don't learn from it: its end is
  cut off and it never got the questions where you could mark illness or
  alcohol. *Delete history* deletes the copy too.
- **One bad byte in the settings file reset everything**: profiles, cue
  wording and positions went back to the defaults, and the broken file was
  overwritten a second later. **0.2.2:** before each save, Zanshin keeps the
  previous good file as `dandurf_settings.json.bak`. If the settings can't be
  read, it sets the broken file aside as
  `dandurf_settings.json.corrupt-<date>-<time>`, loads the backup (or, if
  there's none, starts with the defaults) and tells you once, in the log and
  in a message.
- **A file Windows held for a moment could make a save fail.** Right after
  Zanshin writes a file, Windows Defender, Windows Search or a sync app may
  open it briefly, and replacing it then fails with *Access is denied*. In my
  test copy of 0.2.2 that's how the new settings backup failed, and it left a
  `dandurf_settings.json.bak.tmp` behind. **0.2.2:** when a file is held like
  that, the save waits and tries again, up to six tries in about 0.3 seconds,
  and only then reports the error as before; other errors, such as a full
  disk, still fail at once. This covers the settings and their backup, the
  heart-rate history (saving, deleting a session, an import), the
  measurement windows (`hr_windows.json`), the copy of a running session,
  sessions kept aside, insights, cue records, exports, your own recordings
  and the prepared voice. If the last try fails too, the temporary file is deleted instead of staying next
  to your data or your export, and `app.log` notes every save that needed
  more than one try.
- **The 0.2 uninstaller can delete this version's data.** Zanshin installed
  with the 0.2 installer and Zanshin from the ZIP (or one you built) share one
  data folder, `%APPDATA%\Zanshin`. When you uninstall 0.2, it asks *Keep your
  settings, heart-rate history, recordings and generated voice lines?*, and
  **No** deletes that folder, with this version's history in it. Answer
  **Yes**. **0.2.2:** if Zanshin finds 0.2 still installed, it tells you this
  once.

### The first start

- **"Pair a watch now" in the intro skipped the rest of it.** The intro
  ended on the spot, so the Play / Work step, the step where you choose how
  the app speaks up (and where the intro says what the natural voice sends
  to Microsoft) and the tour never showed. **0.2.2:** the intro carries on;
  pairing opens after it, and the tour starts when you close the pairing
  guide.
- **"Skip intro" also skipped the watch step.** **0.2.2:** on steps 1–2 it
  is *Skip to the watch* and lands on that step; after that it's hidden.
- **The intro couldn't be closed.** ✕, Esc and Alt+F4 did nothing, and with
  no taskbar button another window could hide it. **0.2.2:** closing it asks
  *Quit Zanshin?*. Quit saves nothing, so the intro shows again at the next
  start. On the first start the intro stays on top while it's the app's only
  window. The intro replayed from the Ctrl+K palette just closes and changes
  nothing.
- **The intro asked how the app should speak up, but its only test played a
  sound, one step earlier.** **0.2.2:** the test is gone from the Play / Work
  step. The speak-up step has a preview that matches your answer (voice,
  sound or picture) and the volume slider. The voice preview uses the Windows
  voice and says so: the intro sends nothing to Microsoft. Choosing Work
  shows a note that the question is about Play, and the Play / Work step says
  the app learns your own limits from Play only.
- **The tour described the ensō wrong.** It said the ensō turns green when the
  app runs and red when it's stopped, but the ensō is always in the theme's
  accent colour. **0.2.2:** the tour says what really shows the state: the
  ensō breathes while the app is watching and is still when stopped, a slow
  ring inside means it's waiting for a good moment, a click starts or stops
  it, and the dot at the top left shows the state too.
- **The tour had 10 bubbles and promised "a few seconds".** **0.2.2:** it
  shows five places in about a minute: the ensō, heart-rate receiving (with a
  *Pair your watch* button; the tour goes on after pairing), cues, history
  and the end. Without heart rate coming in, the last bubble points at the
  watch icon and says the app stays silent without a watch. A tour place
  saved by 0.2.1 is capped to the new last step.
- **The first evening spoke mostly in the Windows voice.** Zanshin started
  watching a quarter of a second after the intro, and while it watches it
  prepares nothing new, so preparing the natural voice stopped almost at
  once. Spanish, German, French and Portuguese players also heard the
  English default voice read cue words in their own language.
  **0.2.2:** on the very first start, watching begins once the lines are
  prepared or after 15 seconds, whichever comes first (*Today* shows
  *Preparing the voice*). Spanish, German, French and Portuguese (Brazil)
  cues get a voice of their language (Elvira, Katja, Denise, Francisca)
  by the same rule as Japanese, Chinese, Russian and Bulgarian: only while
  you're on the default voice, and only when the cues that speak use
  that language's built-in words.
- **Setting the app up at the desk counted as play.** The intro, pairing and
  the tour easily take more than five minutes, and that calm session was
  saved like play and pulled the high heart-rate limit and the load
  threshold down, the same problem as 110 → 80 BPM in 0.2.1. **0.2.2:** the
  first session saved after the intro is marked *Just setting up the app*. It
  stays in History, but the load threshold, high heart-rate limit and resting
  baseline don't learn from it. The questions at the end show the mark:
  untick it if you actually played, or tick it for any later session spent
  only setting things up. Export and import keep it.

### Pairing your watch

- **The pairing guide never showed whether pairing worked, and its last step
  switched heart rate off.** Opening the guide already switches heart-rate
  receiving on, but step 5 said to switch it on, so anyone who did turned it
  off. Whether heart rate came in showed only behind the guide. **0.2.2:**
  under the address the guide shows the live state, from *Waiting for the
  phone to connect…* to *Heart rate is coming in: N BPM*, and says when the
  phone hasn't connected yet, another program holds the port or receiving
  didn't start. Step 5 says nothing needs switching, and step 1 that Windows
  may now ask about the network: allow private (home) networks only. The
  guide opens centred on the screen with the mouse pointer.
- **When the phone never connected, Zanshin said "Waiting for heart rate"
  all evening.** The only firewall hint sat under *Watch connects but no
  heart rate?*, the opposite case. **0.2.2:** if nothing connects within
  about 20 seconds, *Today* says *The phone didn’t connect*, names the usual
  causes (Windows Firewall, a network set to Public, a new PC address after a
  router restart) and points to the watch icon on the left. The guide has a
  new box, *Watch won’t connect at all?*, with four checks, including where
  to set your network to Private and allow Zanshin through the firewall.
- **"Waiting for watch" on *Today* even when the watch couldn't come.**
  **0.2.2:** the *Heart rate and load* header says *heart-rate receiving
  off*, *port is busy* or *phone didn’t connect*; *waiting for watch* is left
  for while it connects, or while the phone is connected but no heart rate
  has come yet. With receiving off, *Today* points to the watch icon instead
  of a switch on another page.
- **The `0.0.0.0` field invited you to type `0.0.0.0` into the phone.** It
  was the first control on *In-game → Watch and heart rate*, its *Show IP*
  switch did nothing at `0.0.0.0`, and the QR captions said to enter "this
  PC's IP", which the page didn't show. **0.2.2:** the card starts with the
  receiving switch, the status and *How to pair your watch…*. The field comes
  last, is called *Network address (advanced)* and says not to type its
  number into the phone; *Show IP* next to it appears only when it holds a
  real address. The QR captions point to the pairing guide for the address
  and port.
- **The English pairing guide showed `THIS PC\u2019S` literally.** **0.2.2:**
  it reads "THIS PC’S ADDRESS AND PORT — enter it in the phone app", and
  `check_translations.py` fails on any literal `\uXXXX` in a translation.

### Words and looks

- **One thing had several names.** The main switch was called *listening*
  (in the Slovak original, also a word for eavesdropping), a cue was also a
  reminder, a line, a trigger or a slot, and *limit* and *threshold* were
  mixed up. **0.2.2:** one word each. Zanshin is *watching* or stopped, and
  the tray menu says *Start watching* or *Stop watching* (it said *Start /
  Stop*). The heart-rate switch is *Receive heart rate from the phone* (it
  was *Listen for heart rate from the watch*). A cue is always a cue; a
  *limit* is for heart rate (BPM), a *threshold* for load (x/100). Other new
  names: *Triggers* → *Cues*, *Spoken lines* → *Cue voice*, *Voice comes
  from* → *Voice source*, *Visuals in game* → *In-game pictures*, *▶ Test
  visual* → *▶ Show*, *In-game HR* → *On-screen HR panel*, the sound sets
  *Zen* / *Modern* → *Sumi* / *Aizome*, *HRPI* → *HR persistence*. The
  README already uses the new names.
- **After a session Zanshin could say that 0 of its cues stayed silent on
  purpose**, and the intro never said that some cues are picture-only on
  purpose, so whoever chose the voice could think it was broken. **0.2.2:**
  with none silent the line just counts the cues; otherwise it says how many
  were picture-only on purpose. The speak-up step of the intro says that at
  first about one cue in four is picture-only.
- **A switch that was on looked like one that was off** (the two tracks
  differed by 1.07:1), and the state dot in the sidebar was red whenever
  Zanshin was stopped, which is a normal state. **0.2.2:** a switch that is on
  is in the theme's accent colour. The dot is filled green while Zanshin is
  watching, a hollow ring when it's stopped and an amber ring during "not
  now".
- **The sidebar highlighted the wrong page** after ⓘ, ⚙, Ctrl+K or the tour
  opened another one, and ⚙ next to the heart-rate panel switch led to a page
  without its settings. **0.2.2:** the sidebar marks the page you're on, and
  ⚙ opens the panel's settings.
- **Small text was hard to read.** Explanations, axes and legends had a
  contrast of 2.85:1, some text was very small, and the thin dividers were
  never actually drawn. **0.2.2:** that text has at least 4.5:1, the
  smallest text is bigger, the dividers show, and Japanese and Chinese use
  one Windows UI font almost everywhere (the exceptions are in
  [KNOWN_ISSUES.md](KNOWN_ISSUES.md)).
- **Empty pages looked like measurements, and some dialogs had no place on
  the screen.** Before any heart rate, tiles on *Today* showed numbers, and
  History offered *Recompute* when there was nothing to compute yet; the
  slider in the questions after a session stood at 0 before you touched it,
  which looked like an answer. The pairing guide and the Guide could open in
  a corner. **0.2.2:** tiles fed by heart rate show "—" until it comes,
  *Recompute* waits for the first insight, and the slider stays neutral until
  you move it. The in-game pictures dialog, the pairing guide, the questions
  after a session and the Guide open centred and shrink to fit the screen.
  Deleting your history asks in Zanshin's own window, with *Cancel* focused.
- **The licence had two names.** The app's title bar and *About* said
  "GPLv3", the README and the other documents "GPLv3 or later". **0.2.2:**
  everything says GPLv3 (version 3 of the GNU GPL). Copies of 0.2 and 0.2.1
  you already have keep the wording they came with.
- **The README didn't say which watch was tested.** **0.2.2:** it names it:
  a Samsung Galaxy Watch7 with an Android phone.

### Fewer dead ends

- **The main switch was an icon.** *Today* had a ▶ in a bar titled *Main
  switch*, with "Click ▶ on the left" under it. **0.2.2:** it's one button
  that says what it does, **▶ Start watching** or **■ Stop watching**, the
  same words as in the tray menu and the Ctrl+K palette. Tab reaches it, and
  Enter or Space presses it.
- **The sidebar hid two of its places.** *Settings* and an unlabelled search
  magnifier sat at the bottom, and the watch ring had no caption.
  **0.2.2:** *Settings* and *Search* (Ctrl+K) follow *In-game*, with labels,
  and the ring is captioned *Watch*. In the Work world *In-game* is called
  *Screen*. The state dot has a fourth state: a triangle while Zanshin is
  watching but the heart rate from the watch has dropped out.
- **Before the first heart rate, *Today* still looked like a measurement**,
  with empty tiles and zone bars. **0.2.2:** until your first session with
  heart rate it shows one sentence and *Pair your watch*, and the zones say
  *Zones show up after your first session with heart rate.* *One session up
  close* in History shows only a sentence until there is a session. While
  Zanshin is still learning your limits, a quiet line on *Today* counts your
  play sessions: *Still getting to know you — 1 of 3 play sessions (5+ min
  each)*.
- **A busy heart-rate port showed only in a small header.** **0.2.2:** when
  OBS or another program holds it, *Today* says *Port 4455 is busy*, names
  the usual cause (OBS with its WebSocket server on) and both fixes: switch
  that server off, or change the port in Zanshin and in the phone app. It's
  the only message there then (the pairing sentence stays hidden), on a soft
  dark backing so it reads well over the picture.
- **Questions and messages came in Windows' own boxes**, with buttons in the
  language of Windows, and the first × asked Yes or No. **0.2.2:** they open
  in Zanshin's own window, in the app's language, with the safe button
  focused. Windows' box is left only for when that window can't show one:
  before it exists, or while Zanshin is hidden in the tray. The first ×
  offers *Keep running in the tray* (Enter) and *Quit Zanshin*; Esc keeps
  the window open, and it asks again next time. Before you choose, it says
  what happens if you keep Zanshin in the tray. Zanshin's dialogs have a thin
  border, so their edges show against the dark window behind them.
- **The "not now" shortcut could be changed only in the settings file, and
  on some keyboards it took a letter.** AltGr is the same as Ctrl+Alt, so on
  a Polish keyboard Ctrl+Alt+Z swallowed every ż, even with Zanshin in the
  tray. **0.2.2:** Settings → General → *Keyboard shortcut* offers
  Ctrl+Alt+Z, Ctrl+Alt+F9, Ctrl+Alt+F12, Ctrl+Shift+F12 or *Off*, and marks
  one that would type a letter on one of your keyboard layouts. If you never
  picked one and the default would type a letter, Zanshin takes the first
  free one (or none) and says so once in its log. If another program holds
  yours, the row says so. *Today* and the tour name the shortcut, or point to
  the tray icon's menu when there is none. The row and the log wait for
  Windows' own answer, so a slow start-up no longer reports a working
  shortcut as taken (0.2.1's log could). In German the keys read *Strg* and
  *Umschalt*, as on a German keyboard.
- **Sleep made one long session.** With the PC asleep while Zanshin was
  watching, one session ran through the night, its sleeping heart rate went
  into your resting baseline, and the only fix was deleting your whole
  history. **0.2.2:** when a session's regular ticks stop for more than two
  minutes (sleep or hibernation), it ends where the gap began, without the
  questions, and a new one starts after it if Zanshin is still watching.
  *One session up close* in History has **Delete this session**: it asks
  first, naming the date and length, then recomputes the insights without
  it. The session being recorded can't be deleted.
- ***Delete history* asked one Yes / No question, and a running session saved
  itself again right after.** **0.2.2:** it offers *Delete history*, *Export
  first…* and *Cancel* (focused). While Zanshin is watching, the button is
  off, with *Stop watching first — the running session would save itself
  again after the delete.* under it.
- **A session that couldn't be saved was lost without a word.** **0.2.2:** if
  writing the history fails (a full disk, a locked file), Zanshin says so
  (not while it's quitting), keeps the session in `hr_session_pending.json`
  next to `hr_sessions.json` and adds it to your history at the next start,
  or after the next session that saves. Like a recovered copy, it doesn't
  feed what Zanshin learns. *Delete history* deletes that file too. A
  session of a minute or more that got almost no heart rate (fewer than 10
  readings) still isn't saved, but the log now says so.
- **Backups were hard to find, and an import dropped your oldest sessions
  silently.** **0.2.2:** *Your data* has *Open the data folder*, the message
  after an import says the backups are there, and an import that goes over
  the 400-session limit says how many of the oldest were dropped.
- **Every failed voice preparation said "check your internet connection"**,
  even when Microsoft refused the request, and only the Ctrl+K palette could
  retry. **0.2.2:** a line in the *Voice source* row tells an unreachable
  service from a refused request and other errors, with a *Try again* button
  right there, and the log says where to retry (Settings → Sound, or
  Ctrl+K). Like *Prepare the cue voice*, it sends nothing while Zanshin is
  watching. The voice menu next to it grows wide enough for long Windows
  voice names.
- **Microsoft started refusing the natural voice.** Since about November 2026
  its speech service refuses the voice library Zanshin used (`edge-tts`
  7.2.8, also the one inside the 0.2.1 ZIP) with HTTP 403. Lines prepared
  before then still played, but every new one fell back to the Windows voice.
  Building Zanshin again didn't help: the build installed only libraries that
  were missing and kept an old one. **0.2.2:** Zanshin needs `edge-tts` 7.3.1
  or newer (`requirements.txt`). `build.bat` fetches the newest 7.x
  `edge-tts` on every build: if Microsoft changes something again and a new
  7.x `edge-tts` fixes it, a build made later gets that fix too (a ready-made
  ZIP keeps the one it was built with). Offline it keeps an installed one
  that's new enough and says it couldn't check; with an older one it stops
  with a red **CHYBA:** line instead of building an app whose natural voice
  is refused. The build log names the `edge-tts` version that went in. When
  Microsoft refuses the request, the line under *Voice source* and the log in
  the window now add that if it keeps happening, this Zanshin version is
  probably outdated and the new one is on the official GitHub (Releases). A failed preparation also goes into `app.log`, with the
  installed `edge-tts` version, once per kind of error until preparing works
  again; before, it was only in the log in the window. Run from source,
  `py -m pip install -r requirements.txt` updates an older `edge-tts` (and a
  library it uses, only if the new version needs a newer one) and leaves the
  rest as it is, and `check_before_run.py` warns about an older one.
- **Switching Play / Work while watching** changed how the running session's
  cues spoke, though the session itself stayed in its world. **0.2.2:** the
  session and its cues keep their world, the switch applies from the next
  time you start watching, and the log says so.
- **With a VPN on, the pairing guide could show the VPN's address**, which
  the phone can't reach. **0.2.2:** it lists the PC's real network adapters
  first and marks VPN and virtual ones *(VPN/virtual)*, with a note on what
  to do; the *Network address (advanced)* field warns about such an address
  too. An address of Windows' Mobile hotspot is marked *(hotspot)* instead,
  without a warning, and a Hyper-V external switch that carries your home
  network counts as a real adapter.
- **Quitting again while the questions after a session were open threw away
  your answers.** Quitting while Zanshin is watching saves the session and
  opens its questions first. **0.2.2:** a second Quit while they're open saves
  the answers you've touched as with *Save*; untouched questions close as
  with *Skip*. The same happens when the questions after an earlier stop
  are still open and you quit from the tray or Windows shuts down; the log
  says which it was. The questions now start with how
  long you played, and after a Play session with a cue while the game filled
  the whole screen, they say the pictures may not have shown and suggest
  Borderless.
- **History was hard to read.** The *Consistency* grid showed a whole year,
  mostly empty, load was a bare number and decimals always used a dot.
  **0.2.2:** the grid shows the weeks since your first session (8 to 26)
  with month and weekday labels in the app's language, load reads *x/100*,
  numbers use your language's decimal mark and a real minus sign, and a
  session of an hour or more reads like *1 h 10 min*. The grid grows with
  the panel and names all seven weekdays when there's room. Dates in
  History, the trend chart, the insights and the delete question follow the
  app language (*12 Nov 2026* in English, *12. 11. 2026* in Slovak), and time
  over your heart-rate limit reads like *1 h 15 min* from an hour up, on
  *Today*, in History and on the heart-rate panel.
- **Some texts sent you to *In-game* in the Work world**, where the sidebar
  calls that page *Screen*. **0.2.2:** every text that points to that page
  uses the name your world shows, and texts already on screen change when
  you switch worlds.
- ***watch connected* was the phone.** **0.2.2:** while heart rate comes in,
  *Today* says *phone connected*, and before it does, the line next to the
  switch says *Phone connected — waiting for heart rate…*: what connects to
  Zanshin is the phone app.
- **Buttons looked different from window to window.** **0.2.2:** buttons,
  menus and dialog buttons all come from one set, and a button that's off
  looks the same everywhere (a *Delete* button that's off is no longer red).
  *Show IP* in the pairing guide is an ordinary button, not a link-style
  chip; *Pair a watch now* in the intro and the sound menu have no emoji;
  and small red text, such as an error or the limit on the heart-rate
  panel's chart, uses the readable red.
- **Japanese and Chinese lines could start with 。 or ）, and the heart-rate
  panel drew Japanese and Chinese text as empty boxes.** **0.2.2:** wrapped
  text in those languages follows their line-breaking rules, and the panel,
  its captions and its preview in the intro draw that text in a Japanese or
  Chinese font.
- **Smaller things.** Cue cards show the category's name above your wording;
  *How I speak up* is the first row of *Loudness* on the Sound page; in Aizome
  the calm zone is teal-green, so blue means recovery only; the intro's first
  step says what you'll need: a smartwatch with its companion phone app, as
  the README says. More texts in every language use the app's own words, and
  more of them speak in the first person. In Work, the hint under the
  session's curve in the questions after it says when you were probably
  working, not playing; the
  Bulgarian session title is grammatical for any length; Chinese uses one
  dash style (——); and the log line about a session that wasn't saved
  states the real rule (at least a minute and at least 10 heart-rate
  readings). Running the tests from source no longer writes into the app's
  own log.

## What 0.2.1 fixes

0.2.1 is a bug-fix release after a review of the 0.2 code: in a few places it
didn't do what the README says. None of it was harmful as far as I know. It
adds one thing: "Not now" is also in the tray icon's menu. And it changes how
you get Zanshin: there is no installer; the release has a ready-made ZIP with
its SHA-256 fingerprint, or you build the app yourself (see the README).

### The online voice

- **The natural voice also sent lines it would never speak in a game**: the
  wording of switched-off cues, of ones whose in-game picture is off, of
  ones that play your own recording, and of extra cues kept from 0.1,
  which the app never fires by itself. **0.2.1:** only the four cues are
  sent, and of those only the ones switched on, with their picture on, set to
  speak and without your own recording. Switching one or its picture on, or
  removing its recording, prepares it then.
- **Switching to the Windows voice didn't stop preparing that was already
  running**, so its remaining lines still went to Microsoft. The same after
  switching to the sound or picture-only style or to Work, switching a
  cue or its picture off or creating a profile. **0.2.1:** preparing
  stops at once; only a line already on its way is finished. A new profile's
  lines are now prepared right away too; before, a line not yet in the cache
  played in the Windows voice until something else started preparing.
- **Switching the language to Japanese, Chinese, Russian or Bulgarian also
  switched the natural voice to that language** (while you were on the
  default voice), but your cues kept their words, for most people
  English ones. The new voice then read English words it may mangle or not
  say at all. **0.2.1:** the voice follows the words, not the menu. Switching
  the language changes it only if the cues that speak in your current
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
  stop watching**, which also stops measuring. **0.2.1:** "Not now" is also
  in the tray icon's menu (right-click), and the start-up log line points
  there.

### The heart-rate port

- **Port 4455 could stop taking heart rate until you restarted heart-rate
  receiving.** Once its connection limit was full (a port scanner, or a watch
  that kept reconnecting over bad Wi-Fi and left dead connections behind), it
  stopped accepting new ones, even after the old ones closed. **0.2.1:** only
  the extra connection is refused, and heart rate keeps coming in. Silent
  connections are closed: 10 s to finish connecting, and after a minute of
  silence the app pings the other side and closes the connection only if
  nothing answers within another minute, so a quiet but connected watch
  isn't dropped. A single message over 64 KB is refused.
- **If another program held UDP port 4455, heart rate over UDP or OSC (the
  iPhone route) never arrived, and nothing said why**: the status stayed at
  "Connecting...". **0.2.1:** Zanshin keeps listening on TCP, so the Android
  route still works. It says so in its log and shows a note next to the
  switch until something connects: in 0.2.1 *Listening on TCP only — UDP
  didn’t open*, from 0.2.2 *Android can connect, iPhone (PulseOSC) can’t*. It
  doesn't retry UDP: close the other program, then switch *Receive heart rate
  from the phone* off and on (in 0.2.1 it's called *Listen for heart rate
  from the watch*).
- **The log file kept the first 40 raw messages from the watch every time
  heart-rate receiving started.** **0.2.1:** 5, which is enough to see what
  the companion sends when pairing doesn't work.

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
  changes the sample phrases.** It doesn't: cues you already have keep
  their wording. **0.2.1:** the line says so.
- **If Zanshin failed while starting, before its window opened, `crash.log`
  recorded nothing**, and a crash while the main window was being built was
  written to it twice. **0.2.1:** both are recorded, each once (in
  `%APPDATA%\Zanshin\logs` for the built app).
- **For people who build from source:** on a Windows PC without internet,
  `check_sources.py` reported every study link as dead. **0.2.1:** it says
  you're offline and checks nothing.

## Before 0.2

Zanshin 0.1 was my first public release. In places it promised more than it
could keep, and some things didn't work the way it said they did. Below are
the main points of what I've found: what 0.2 fixed and what it left open. The
seven problems named in the 0.1 version of KNOWN_ISSUES.md are all below.

**About 0.1 in this repository's history.** Along with the 0.1 code, some
things went into the repository that didn't belong in public. Nothing
terrible, but not meant to be there. So I set the repository up again: 0.1 is
in the history as it was, only without those things, and 0.2 follows it. That
was the lesson: work stays work, private stays private, and I check every file
before publishing. What 0.1 got wrong in the app itself is written down below.

## What 0.1 got wrong, and what 0.2 changed

### Privacy and what's on screen

- **The online voice was the default, while the README and the *Your data* panel
  said nothing is sent.** Your cue texts (never your heart rate) went to
  Microsoft at first start, and mid-game if a line wasn't ready yet, for example
  right after you changed it; only PRIVACY.md listed it. **0.2:** it's still the
  default, but the docs and the app say so, and say when text is sent: after the
  first start and after you change a line, the voice, the speed or the language.
  Nothing is sent while Zanshin is watching; a line that isn't ready plays in
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
  the app does and doesn't do, names the one exception (while you preview a
  picture, it takes mouse clicks so you can drag it), and says only the
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
  still mostly in Slovak (it now starts with an English summary).
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
- **The heart-rate panel looked confident before it had a baseline.** **0.2:**
  for the first ~30 readings it shows "calibrating…", and cues can't fire.
- **Smaller display bugs.** The cue counter on *Today* always showed 0×, zone
  words meant different things in different places, a dropout looked like not
  being paired, and some choices got reset (pictures you switched off came back
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
  screenshots of the app's own windows) are described in DEVELOPMENT.md and
  SAFETY.md.

### Corrections to the 0.1 version of KNOWN_ISSUES.md

- It said seven languages "fall back to English". None did (a few texts, like
  the Ctrl+K palette, stayed in Slovak instead); they were unreviewed, partly
  outdated AI translations. It also planned to mark them as partial; 0.2
  doesn't, and says instead that every language except Slovak is unreviewed.
- It called the online voice "optional" and said your settings never leave your
  PC; the voice was the default and sent your cue texts out. It also said a
  "Steam build" sends a fixed presence token; no Steam build was released, and
  nothing was sent to Steam.

— **Dandurfin** · GPLv3
