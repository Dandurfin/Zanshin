# How Zanshin works, in detail

The [README](../README.md) says what Zanshin does in a few lines. This page has
the exact rules: when a cue comes, when Zanshin goes quieter, what it learns
from, and when the natural voice talks to Microsoft. Where something is new in
the code here but not in the 0.2.1 release yet, it says *from 0.2.2*.

## When a cue comes

When your *load* spends enough time above your threshold, Zanshin is *armed*
(the *Today* page says so). Load is Zanshin's measure of strain, computed from
heart rate (LOAD on the heart-rate panel). Zanshin then waits for a short pause
in your input: about 2.5 s with no key, mouse or controller. The moment of
greatest need and the worst moment to interrupt are the same second, so the
voice comes only in such a pause, once your load has stopped climbing, and
never while your pulse is in the Peak zone (at or above your high heart-rate
limit). Zanshin can't see the game itself, so a still moment mid-fight can
count as a pause too. If no such pause comes within 90 s, it shows a silent
picture instead, under the same rules; otherwise it stays quiet.

Some cues stay silent on purpose: about one in four in your first 15 sessions
(every session of a minute or more counts, Work too), one in ten after that.
They show only the picture. That collects data for comparing voice with
picture only; Zanshin doesn't show that comparison yet. From 0.2.2 the line
after a session says how many cues were picture-only on purpose.

At most five cues an hour (restarting Zanshin starts that count over), and at
least four minutes apart within a session.

## When it goes quieter

Answer "it disrupted" or "it wound me up" in the questions after a session, or
press "not now" within a minute of a cue and let the session carry on for at
least two more minutes, unless you then answer that it landed. The next
session in the same world (Play or Work) then drops one step: voice → picture
only → no cues for three sessions of five minutes or more (sooner if you
answer after a session that it should have spoken up), then the picture again.
It climbs back slowly, after three sessions with a cue that was actually shown
and none of those signals (a cue whose picture failed to draw doesn't count).
When it has gone quieter, History says so in one quiet line: why, and how many
more sessions it needs before it tries a step louder.

How loud it may ever get is your call: *Voice, sound and picture*, *Sound and
picture* or *Picture only*. You can pick it during the introduction (its voice
preview there uses the Windows voice and sends nothing) or any time under
Settings → Sound → *How I speak up*. Zanshin may still go quieter on its own,
but never louder than your choice.

## "Not now"

"Not now" keeps cues quiet for 30 minutes while Zanshin goes on measuring;
doing it again ends it sooner. It's a global shortcut, Ctrl+Alt+Z by
default, and always also in the tray icon's menu (right-click). From 0.2.2
you pick the shortcut under Settings → General → *Keyboard shortcut*:
Ctrl+Alt+Z, Ctrl+Alt+F9, Ctrl+Alt+F12, Ctrl+Shift+F12 or *Off*. AltGr is the
same as Ctrl+Alt, so on some keyboard layouts a combination types a letter
(AltGr+Z is ż on a Polish keyboard); the menu marks such a choice with that
letter. If you never picked a shortcut and the default would type a letter
on one of your layouts, Zanshin takes the first one that doesn't (or none)
and says so once in its log. If another program already holds your
shortcut, the setting keeps your choice and its line says it doesn't work
right now. From 0.2.2 that line and the log wait for Windows' own answer, so
a slow start-up no longer reports a working shortcut as taken. While "not
now" holds, *Today* says until when and how to end it. In German the app
writes the keys as on a German keyboard: *Strg* and *Umschalt* instead of
Ctrl and Shift.

## What it learns, and from which sessions

Nothing to tune by hand. Your load threshold, resting baseline and high
heart-rate limit are all computed from *your own* sessions, each from at least
three of them. Until then the threshold and the high heart-rate limit use
average-player numbers, and your calm is taken from the current session only.
The threshold and the high heart-rate limit learn only from play sessions of
five minutes or more, and the load threshold needs the most: at least three
play sessions of five minutes or more that add up to roughly half an hour of
heart rate — three of about ten minutes are enough, three of five are not.

These sessions don't count:

- imported sessions,
- sessions with implausible readings,
- sessions recovered after Zanshin ended without saving them, or added later
  because they couldn't be saved at first (from 0.2.2; see
  [Your sessions](#your-sessions) below),
- sessions marked *Just setting up the app* (from 0.2.2; the first one saved
  after the introduction gets the mark by itself, and you can change it in the
  questions at the end),
- sessions you marked afterwards as affected by illness, alcohol or exercise
  just before playing.

From 0.2.2, while Zanshin is still getting to know you, *Today* counts the
play sessions it can already learn from (five minutes or more, none of the
above) in one quiet line, for example *Still getting to know you — 1 of 3
play sessions (5+ min each)*. It shows in Play only, once heart rate has come
in at least once, and goes away after the third.

## Silent while you walk, if your watch sends steps

While the watch reports steps (15 or more in the last minute, for now), Zanshin
stays quiet. Walking raises heart rate just like stress, and the two can't be
told apart from BPM alone. Not every watch app sends steps. If yours doesn't,
Zanshin can't tell you're walking, so a walk can look like strain and bring a
cue. Steps only keep cues quiet: time spent walking still counts in your saved
sessions.

## Play and Work

A small *Play | Work* switch in the title bar. Each world keeps its own
history, insights and look — *Sumi* (ink and gold) for play, *Aizome* (indigo)
for work — and switches without a restart. At work, cues are pictures only: no
voice, no sound. The resting baseline is shared; the load threshold and high
heart-rate limit are learned from play sessions only and used in both worlds,
so if you only ever use Work, they stay on the average-player numbers. From
0.2.2 the *In-game* page is called *Screen* in Work, and every text that
sends you to that page uses the name your world shows.

A running session stays in the world it started in, even if you flip the
switch meanwhile. From 0.2.2 so do its cues: whether they speak or make a
sound follows the session's world, the new world applies from the next time
you start watching, and the log says so. At the end, your answer to *Were you
playing or working?* has the last word: pick the other world and the session
moves there — in History, and in what the load threshold and high heart-rate
limit learn from. Skip the question and it stays where it started.

## The heart-rate number on screen

From 0.2.2 the heart-rate number on screen (the heart-rate panel in the game,
*Today* and the line next to the switch) is the median of the last 3 seconds
of readings, so it doesn't jump with every message; measuring still uses every
reading. If the companion writes two different heart rates into one source,
Zanshin says so (see *Troubleshooting* in the README).

## Today and the sidebar

From 0.2.2 the main switch at the top of *Today* is one button,
**▶ Start watching** or **■ Stop watching**: the same words as in the tray
menu and the Ctrl+K palette, and all three stay in step. The big text under
the ensō says what Zanshin is doing; when another program holds the
heart-rate port, it says *Port 4455 is busy* (with your port number), names
the usual cause (OBS with its WebSocket server on) and how to fix it, and
that's the only message there: the pairing sentence stays hidden meanwhile.
Until your first session with heart rate, *Today* shows one sentence and
*Pair your watch* instead of the tiles and zones. While heart rate comes in,
the *Heart rate and load* header says *phone connected* (from 0.2.2; it's
the phone app that connects to Zanshin, not the watch). While the phone is
connected but no heart rate has come yet, the header says *waiting for
watch* and the line next to the receiving switch *Phone connected — waiting
for heart rate…*.

The sidebar lists *Today*, *History*, *In-game* (*Screen* in Work),
*Settings* and *Search* (the Ctrl+K palette), then the watch ring (*Watch*),
which opens the pairing guide. The dot at the top shows the state: a filled
green dot while Zanshin is watching, a triangle while it's watching but the
heart rate from the watch has dropped out (nothing for 12 seconds), an amber
dot in a ring during "not now", and a hollow ring when it's stopped.

## Your sessions

A session runs while Zanshin is watching. A session of at least a minute with
at least 10 heart-rate readings is saved, and History keeps the last 400.
From 0.2.2:

- **Quitting with the questions open.** If you quit Zanshin while it's
  watching, it saves the session and opens its questions first. If you quit
  again while they're open, the answers you've touched are saved as with
  *Save*; if you touched none, they close as with *Skip*. The same happens
  when the questions after an earlier stop are still open and you quit from
  the tray, or Windows shuts down, restarts or signs you out. The log says
  which it was, or that the answers couldn't be saved.
- **When the PC sleeps.** If a session's regular ticks stop for more than two
  minutes (sleep or hibernation), the session ends where the gap began,
  without the questions, and if Zanshin is still watching, a new one starts
  after it. A clock set backwards doesn't count as a gap.
- **Deleting one session.** History → *One session up close* → **Delete this
  session** asks first, with the session's date and length, deletes it with
  its measurement windows and recomputes the insights without it. The session
  being recorded can't be deleted.
- **Deleting everything.** Settings → General → *Your data* → **Delete
  history** offers *Delete history*, *Export first…* and *Cancel*. While
  Zanshin is watching, the button is off: the running session would save
  itself again right after.
- **A session that can't be saved** (a full disk, a locked file) goes to
  `hr_session_pending.json` next to `hr_sessions.json`. Zanshin tells you,
  and adds it to your history at the next start, or after the next session
  that saves. Like a session recovered from the 5-minute copy, it doesn't
  feed what Zanshin learns.
- **Importing** sets your originals aside as a backup; **Open the data
  folder** under *Your data* opens the folder where it is. If an import takes
  your history over 400 sessions, the oldest drop out, and the message says
  how many.

History's *Consistency* grid shows the weeks since your first session (at
least 8, at most 26) with month and weekday labels, and load reads *x/100*.
From 0.2.2 the grid grows with the panel up to a set cell size and names all
seven weekdays when there's room. Dates in History, the trend chart, the
insights and the delete question are written the way your app language
writes them (*12 Nov 2026* in English, *12. 11. 2026* in Slovak); the CSV
export's file name keeps the `2026-11-12` form. Time over your heart-rate
limit reads like *1 h 15 min* from an hour up, on *Today*, in History and on
the heart-rate panel.

## Which address the pairing guide shows

The pairing guide shows one of this PC's addresses, hidden until you click
**Show IP**. From 0.2.2 it prefers the PC's real network adapters (Wi‑Fi,
Ethernet) to VPN and virtual ones, then the one Windows routes through, then
home-network addresses (192.168.x.x before 10.x.x.x before 172.16–31.x.x). A
VPN or virtual adapter's address is marked *(VPN/virtual)*, with a note to
switch the VPN off or allow local network access in it, and the *Network
address (advanced)* field warns the same way when it holds such an address.
WSL, Hyper-V's *Default Switch*, Docker and loopback adapters count as
virtual too. Two cases the phone can reach don't get that mark: an address
of Windows' Mobile hotspot is marked *(hotspot)* instead, without a
warning, and a Hyper-V external switch (a *vEthernet* adapter that carries
your home network and the route out, with no real adapter in the same
network) counts as a real adapter. For this Zanshin uses only the adapters'
names, descriptions and types and whether they're connected, as Windows
reports them, plus the address Windows would send outgoing traffic from;
nothing is sent anywhere.

## The natural voice: when it prepares lines

There are two voices, under Settings → Sound → *Voice source*.
*Natural (online, Microsoft)* is the default: neural voices, prepared ahead of
time into a local cache, so in-game nothing waits on the network.
*Windows (offline)* uses the voices built into Windows and works fully offline.

Preparing sends Microsoft a cue's wording only if it is one of the four,
switched on with its in-game picture on, set to speak and not playing your own
recording, and only if its line isn't in the cache yet. That happens at every
start (the first time for all of them), and again after you change a cue's
wording (while you type, a pause of about 0.7 s is enough, so a half-typed line
can go too), switch it or its picture on, switch it to speak or remove its own
recording, change the voice, the speed, the profile (or create one) or the
language (when that changes the voice), import a profile, and after you switch
back to *Voice, sound and picture*, to Play or to the natural voice.

Testing a cue whose line isn't ready, or *Prepare the cue voice* in the Ctrl+K
palette, sends the missing ones too; testing a cue that is switched off or has
its picture off, or an extra one kept from 0.1, plays the Windows voice and
sends nothing. It happens only with *Voice, sound and picture* and in the Play
world (not with *Sound and picture* or *Picture only*, not in Work), and it
still happens while Zanshin has quietened itself to picture only or a pause.

Switching a cue or its picture off, giving it your own recording, changing or
creating a profile, or switching to *Sound and picture* or *Picture only*, to
Work or to the Windows voice stops any preparing already running at once; only
a line already on its way is finished.

**Nothing new is prepared while Zanshin is watching** (a line already on its
way when watching starts is finished): a line that isn't ready then plays in
the Windows voice, and preparing waits until you stop watching. On the very
first start Zanshin (from 0.2.2) waits until those lines are prepared, at most
about 15 seconds (*Today* shows *Preparing the voice*), and only then starts
watching by itself, as if you had pressed ▶ on *Today*, so the first evening
can already speak in the natural voice. Lines not ready by then (offline, for
example) are prepared once you stop watching, or at the next start.

If preparing fails, the line under *Voice source* says how many cues have
their voice and, from 0.2.2, why: Microsoft's service couldn't be reached,
it refused the request (try later, or switch to the Windows voice), or
something else went wrong. A *Try again* button appears under it, and the log
says how to retry. *Try again* works like *Prepare the cue voice*: while
Zanshin is watching it sends nothing and waits until you stop.

The full list of what can use the network is in [PRIVACY.md](../PRIVACY.md).

## Voices and languages

The interface has eleven languages: English, Slovak, Japanese, Chinese
(Simplified), Russian, Spanish, German, French, Portuguese (Brazil), Czech and
Bulgarian, switchable without a restart (Settings → General → *Language*).
What Zanshin draws into the game (the heart-rate panel and the captions under
the pictures) stays in English unless you change *In-game language*.

The built-in cue words are set in the app's language when a profile is created
(English ones for Slovak and Czech); switching the language later doesn't
translate them. With the natural voice, spoken cues keep the default English
voice until you pick another. The exception is cues in Japanese, Chinese,
Russian or Bulgarian, and from 0.2.2 also in Spanish, German, French or
Portuguese, which get a voice of that language while you're still on the
default voice: on a first start in that language, when a profile is created in
it, or when you switch to it and the cues that speak in the profile you're in
use its built-in words (not reworded ones). The voice follows the words, not
the menu: switching the language with English words keeps the English voice,
and switching back doesn't undo a change. One voice reads all your profiles,
except cues given a voice of their own.

From 0.2.2 wrapped Japanese and Chinese text follows those languages'
line-breaking rules, so a line doesn't start with 。 or ）, and dates follow
the app language (see [Your sessions](#your-sessions)).

Zanshin is written in Slovak; the other languages are AI-assisted translations
not yet checked by a native speaker.

## Sounds

Eight short sounds in two sets of four, *Sumi* and *Aizome*, ship with the app.
Play cues use the Sumi set unless you pick another sound for a cue; Work cues
make no sound. If a sound file goes missing, the built app copies it back from
the `.exe`. Only if that isn't possible (or you run from source) are two of them
downloaded from GitHub (Kenney, CC0, checksum-verified) and the rest
synthesised locally, those two as well if the download fails.

## In-game pictures and the heart-rate panel

Every cue uses an in-game picture (on by default; a cue whose picture you
switch off never fires). The heart-rate panel is optional (*On-screen HR
panel*, off by default) and also shows your load. Both are click-through,
drawn by default on the monitor of the window in focus (normally your game),
and scaled to that screen's height, so they take the same share of a 1080p or
a 4K screen. Windows doesn't draw them over a game in exclusive fullscreen (the
voice still plays); use borderless or windowed mode. Zanshin can only guess
exclusive fullscreen (a window that covers the whole monitor). From 0.2.2,
when it guessed so during a Play session with a cue, the questions after the
session say the pictures may not have shown and suggest *Borderless*.

## The Guide

Each of the four built-in cues — Grounding, Jaw, Grip & gaze and Breath — has a
short note. Open it with the ▸ arrow next to the cue on the *Cues* page, or
read them all in the Guide (Settings → General → *Guide* → **Open**). It covers
what happens in your body, why it may help and what to do (for breath, two
techniques). The breath note cites studies on breathing. The jaw note cites one
that competitive play raises a stress response, not that you hold it in your
jaw. The grounding and grip & gaze notes say plainly they come from
practice or tradition. The full source list is [ZDROJE.md](../ZDROJE.md) (notes
in Slovak); none of these studies tested Zanshin.
