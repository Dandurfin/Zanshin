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
- sessions recovered after Zanshin ended without saving them (from 0.2.2; see
  [KNOWN_ISSUES.md](../KNOWN_ISSUES.md)),
- sessions marked *Just setting up the app* (from 0.2.2; the first one saved
  after the introduction gets the mark by itself, and you can change it in the
  questions at the end),
- sessions you marked afterwards as affected by illness, alcohol or exercise
  just before playing.

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
so if you only ever use Work, they stay on the average-player numbers.

A running session stays in the world it started in, even if you flip the
switch meanwhile. At the end, your answer to *Were you playing or working?*
has the last word: pick the other world and the session moves there — in
History, and in what the load threshold and high heart-rate limit learn from.
Skip the question and it stays where it started.

## The heart-rate number on screen

From 0.2.2 the heart-rate number on screen (the heart-rate panel in the game,
*Today* and the line next to the switch) is the median of the last 3 seconds
of readings, so it doesn't jump with every message; measuring still uses every
reading. If the companion writes two different heart rates into one source,
Zanshin says so (see *Troubleshooting* in the README).

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
voice still plays); use borderless or windowed mode.

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
