# Known issues & a commitment (alpha 0.2)

I build Zanshin by one rule above the rest: **honest over polished.** If a line —
in the app or in these docs — promises more than the code actually delivers, that
line is the bug, not the missing feature.

After the first public alpha I audited Zanshin against a single question: *does it
claim more than it can back?* In places, it did. Rather than quietly patch them, I'm
naming them here, in the open, and committing to correct them in the 0.2 line. None
of them change what Zanshin **is** — a local, quiet, heart-rate nudge for gamers —
but each is a spot where the words ran ahead of the code.

Grouped by theme, with a representative example or two each.

## 1. Privacy wording — absolutes the code doesn't earn

The core guarantee is real and I stand behind it: **your heart rate, sessions,
insights, recordings and settings never leave your computer.** But a few lines state
it as an unconditional absolute the code doesn't back — and which Zanshin's own
[`PRIVACY.md`](PRIVACY.md) was deliberately written to avoid. Examples: the README's
"…or send a byte anywhere," and the in-app *Your data* panel's "Nothing is sent
anywhere." A few things *do* touch the network: the optional online TTS voice sends
the reminder *phrase text* to Microsoft; the first run may fetch two CC0 sound
effects from GitHub; the Steam build sends a fixed, non-personal presence token. The
README also says that online voice "needs the network only when you edit a phrase" —
but it also fetches its voice list.

**0.2:** every privacy claim scoped to match `PRIVACY.md` — precise about the few
things that leave, absolute only about the things that never do. (The QR-code and
cloud-service wording is corrected in the same spirit: the in-app QR codes are
download links to third-party companion apps, and cloud services like Pulsoid,
HypeRate or Stromno can't be used as a source at all.)

## 2. Insights that sound more certain than the data

Zanshin's insights read *ordinary gaming heart rate*, not a controlled test — so a
handful of them state a cause or a trend more firmly than a few noisy sessions
warrant. Examples: "you settle down faster than before" and "your body looks more
rested" (from small shifts across as few as two recent sessions); "the start of a
session winds you up the most" (a threshold that isn't adjusted for how long the
session is); "the game keeps you tense longer than before" (measured against a limit
the app recomputes from your own recent sessions, with no control for sleep or
caffeine); a "this week vs. the previous week" wording that also fires when the
comparison is really just the last few sessions; and a "steady" summary that can call
a metric steady before enough sessions exist to judge it. The app already hedges some
of these correctly — I'll make the rest match.

**0.2:** softer, honest phrasing; name the confounders; fix the timeframe wording and
the thresholds.

## 3. Heart-rate recovery framed as a fitness test

The HRR card cites clinical/fitness numbers — "typically 12–23, trained people 29 and
more, faster recovery goes with better fitness." Zanshin's HRR is read from ordinary
gaming peaks, not a max-effort test, so those norms don't really apply.

**0.2:** drop the clinical numbers and the fitness framing; keep HRR as what it
honestly is — a rough sense of how fast you came back down.

## 4. The "science" cards state mechanisms as fact

Under a header literally called *The science*, a few cards state physiological
mechanisms as settled fact without a citation — for example grounding "restricts
blood flow to the brain and activates the amygdala," or the breathing cards' "the
fastest biological mechanism for lowering heart rate" and "stabilizes the
parasympathetic system."

**0.2:** soften to hedged, attributed wording (or add a real citation where one
exists); where it's background reasoning rather than proof, say so.

## 5. "Not a medical device" — said where it matters

Zanshin is deliberately **not** a medical device, and the README says so — but that
line lives only in the README, while the clinical-sounding claims, the HRR numbers
and the breath-hold instructions appear in the app's *Guide*, which carries no such
note. The History screen already hedges ("observations and tips, not diagnoses"); the
Guide should too.

**0.2:** carry a short "general wellbeing, not medical advice; not a medical device"
line into the Guide and the breathing screens.

## 6. Nine languages offered, two complete

The switcher lists nine languages, but only **Slovak and English** are fully
translated; the other seven fall back to English for anything not yet translated.

**0.2:** mark the seven as partial, so the choice is honest.

## 7. Onboarding, HUD warm-up, and leftovers

Onboarding implies the app will show, in numbers, that the game "strains you less" —
but that particular decreasing-strain insight doesn't exist yet, and "after a few
days" is really closer to a few weeks. The in-game HUD also shows a confident load
reading from its very first samples: until it has about 30 readings it has no real
resting baseline, so it measures strain against a rough minimum instead of telling
you it's still calibrating. And a couple of cosmetic leftovers from the old name
("DojoSync", "Since 2.1") are still around.

**0.2:** reword onboarding to what actually exists; give the HUD a short
"calibrating…" warm-up; clean up the leftover strings.

---

**The commitment.** Everything above is being corrected in the 0.2 line. Where
something isn't verified yet — for example the iPhone / Apple Watch path, which is in
the code but untested because I don't own Apple hardware — the app will say so plainly
rather than imply it works. Zanshin will only claim what it can actually do.

Truth without varnish. Alpha is a beginning, not an apology.

— **Dandurfin** · GPLv3
