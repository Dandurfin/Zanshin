# -*- coding: utf-8 -*-
"""
generate_zen_audio.py
=====================

Procedurally synthesizes the Zanshin Zen sound palette with **numpy** and writes
`.wav` files with **scipy.io.wavfile** (falling back to the stdlib `wave` module
when SciPy is not installed, so the script always runs).

Aesthetic target: the deep, calm, organic feel of "ZANSHIN (残心) : Total
Awareness | Japanese Zen Music" — low resonant drones, wooden percussion and
delicate metallic chimes. Nothing here is a sample; every sound is built from
oscillators, shaped noise and physical-model-style synthesis.

Run this FIRST to create the sounds, then run `onboarding_ui.py`:

    python generate_zen_audio.py

Outputs (into ./zen_audio/):
    zanshin_ambient.wav   - looping meditative drone (wind + distant monks)
    koto_pluck.wav        - short organic koto pluck (UI click)
    earth_thud.wav        - deep muffled taiko/earth impact  (trigger: Grounded)
    temple_block.wav      - hollow wooden mokugyo knock       (trigger: Teeth/Jaw)
    breath_chime.wav      - airy exhale + delicate tingsha    (trigger: Breathe)
"""

import os
import numpy as np

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
SR = 44_100                       # sample rate (Hz) — CD quality
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zen_audio")


# --------------------------------------------------------------------------
# WAV writer  (SciPy if available, else stdlib `wave`)
# --------------------------------------------------------------------------
def write_wav(path, audio, sr=SR):
    """Write a float array in [-1, 1] to a 16-bit PCM WAV.

    `audio` may be mono, shape (n,), or stereo, shape (n, 2). We prefer
    `scipy.io.wavfile` (as requested) but transparently fall back to the
    standard-library `wave` module when SciPy is absent.
    """
    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767.0).astype(np.int16)
    try:
        from scipy.io import wavfile          # honored when installed
        wavfile.write(path, sr, pcm)
    except Exception:
        import wave                            # always present
        channels = 1 if pcm.ndim == 1 else pcm.shape[1]
        with wave.open(path, "wb") as w:
            w.setnchannels(channels)
            w.setsampwidth(2)                  # 16-bit
            w.setframerate(sr)
            w.writeframes(pcm.tobytes())       # C-order interleaves L,R,L,R


# --------------------------------------------------------------------------
# Small DSP toolkit (numpy only — no scipy.signal dependency)
# --------------------------------------------------------------------------
def tarr(dur):
    """Time axis (seconds) for a clip of length `dur`."""
    return np.arange(int(dur * SR), dtype=np.float64) / SR


def normalize(x, peak=0.9):
    """Scale so the loudest sample sits at `peak` (avoids clipping)."""
    m = np.max(np.abs(x))
    return x * (peak / m) if m > 1e-9 else x


def fade(x, fin=0.005, fout=0.02):
    """Cosine fade-in / fade-out (seconds) to kill clicks at the edges."""
    n = len(x)
    ni, no = int(fin * SR), int(fout * SR)
    if ni > 0:
        x[:ni] *= 0.5 * (1 - np.cos(np.linspace(0, np.pi, ni)))
    if no > 0:
        x[-no:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, no)))
    return x


def attack_decay(n, attack, decay):
    """Percussive envelope: quick linear attack, exponential decay."""
    t = np.arange(n) / SR
    env = np.exp(-t / decay)
    a = int(attack * SR)
    if a > 0:
        env[:a] *= np.linspace(0.0, 1.0, a)
    return env


def fft_filter(x, mask):
    """Apply a frequency-domain magnitude mask (real FFT), return same length."""
    X = np.fft.rfft(x)
    return np.fft.irfft(X * mask, n=len(x))


def _soft_edge(f, corner, kind):
    """Smooth (tanh) 0/1 transition around `corner` Hz for gentle filters."""
    width = max(1.0, corner * 0.3)
    s = np.tanh((f - corner) / width)
    return 0.5 * (1 - s) if kind == "low" else 0.5 * (1 + s)


def lowpass(x, cutoff):
    """Gentle low-pass via a smooth spectral roll-off (no ringing)."""
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    return fft_filter(x, _soft_edge(f, cutoff, "low"))


def bandpass(x, low, high):
    """Gentle band-pass = high-pass * low-pass in the frequency domain."""
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    return fft_filter(x, _soft_edge(f, low, "high") * _soft_edge(f, high, "low"))


def swept_sine(dur, f_start, f_end, tau):
    """Sine whose frequency glides f_start -> f_end (exp, time-constant tau).

    The instantaneous frequency is integrated into phase so there are no
    discontinuities — this is what gives a taiko/earth hit its 'boom' pitch drop.
    """
    t = tarr(dur)
    inst = f_end + (f_start - f_end) * np.exp(-t / tau)
    phase = 2 * np.pi * np.cumsum(inst) / SR
    return np.sin(phase)


def modal(dur, modes):
    """Sum of exponentially-decaying sinusoids (physical 'modal' synthesis).

    `modes` = list of (frequency_Hz, amplitude, decay_seconds). Inharmonic
    frequency ratios read as 'wood'; harmonic ones read as 'metal/string'.
    """
    t = tarr(dur)
    out = np.zeros_like(t)
    for freq, amp, dec in modes:
        out += amp * np.sin(2 * np.pi * freq * t) * np.exp(-t / dec)
    return out


def karplus_strong(freq, dur, decay=0.996, seed=0, burst_lowpass=None):
    """Karplus-Strong plucked-string model — organic, string-like, cheap.

    A short noise burst is fed through a tuned averaging delay line; the result
    is a decaying, slightly evolving pluck. Low-passing the initial burst makes
    it mellow (koto) rather than harsh.
    """
    n_delay = max(2, int(round(SR / freq)))
    length = int(dur * SR)
    rng = np.random.default_rng(seed)
    buf = rng.uniform(-1.0, 1.0, n_delay)
    if burst_lowpass:
        buf = lowpass(buf, burst_lowpass)
    out = np.empty(length, dtype=np.float64)
    idx = 0
    for i in range(length):                    # short clips -> loop is fine
        out[i] = buf[idx]
        nxt = (idx + 1) % n_delay
        buf[idx] = decay * 0.5 * (buf[idx] + buf[nxt])   # low-pass feedback
        idx = nxt
    return out


def make_loopable(x, xfade=0.5):
    """Crossfade a stereo/mono buffer's tail into its head for a seamless loop.

    We synthesize `xfade` seconds of extra tail, then equal-power blend it over
    the head so that the wrap-around (last sample -> first sample) is smooth for
    `pygame.mixer.music.play(-1)`.
    """
    xs = int(xfade * SR)
    L = len(x) - xs
    w = np.linspace(0.0, 1.0, xs)
    if x.ndim == 2:
        w = w[:, None]                         # broadcast across channels
    x[:xs] = x[:xs] * w + x[L:L + xs] * (1.0 - w)
    return x[:L]


def stereo(left, right):
    """Interleave two mono channels into an (n, 2) stereo array."""
    n = min(len(left), len(right))
    return np.stack([left[:n], right[:n]], axis=1)


# --------------------------------------------------------------------------
# 1) Onboarding ambient drone  — wind + deep sine + distant monks
# --------------------------------------------------------------------------
def make_ambient(dur=20.0):
    """Looping meditative drone.

    Layers:
      * a deep detuned sine 'choir' (C2 + fifth + octave) — the body,
      * a slow vowel-like formant swell — the 'distant monks',
      * low-passed noise with a slow LFO — 'wind', decorrelated L/R for width,
      * one shared 10 s breathing swell over everything (matches the app tempo).
    An extra 0.5 s tail is generated and crossfaded for a click-free loop.
    """
    xfade = 0.5
    t = tarr(dur + xfade)

    # --- deep sine choir: fundamental C2 with slightly detuned partners ---
    base = 65.41                                   # C2
    drone = np.zeros_like(t)
    for f, a in [(base, 0.6), (base * 1.5, 0.22),  # fifth
                 (base * 2.0, 0.16)]:              # octave
        drone += a * np.sin(2 * np.pi * f * t)
        drone += a * 0.5 * np.sin(2 * np.pi * f * 1.003 * t)  # detune -> beating

    # --- distant 'monks': a soft vowel formant that slowly breathes in/out ---
    monks = np.zeros_like(t)
    for f, a in [(196.0, 0.10), (392.0, 0.06), (588.0, 0.035)]:
        monks += a * np.sin(2 * np.pi * f * t)
    monks *= 0.5 + 0.5 * np.sin(2 * np.pi * t / 12.0)   # 12 s slow swell

    # --- wind: low-passed noise, independent per channel for stereo width ---
    def wind(seed):
        rng = np.random.default_rng(seed)
        n = lowpass(rng.standard_normal(len(t)), 420.0)
        lfo = 0.55 + 0.45 * np.sin(2 * np.pi * t / 9.0)  # gusts
        return normalize(n, 0.9) * lfo * 0.25

    body = drone * 0.5 + monks
    left = body + wind(11)
    right = body + wind(23)

    # --- one shared 10 s breathing swell (the app's inhale/exhale tempo) ---
    breath = 0.6 + 0.4 * (0.5 - 0.5 * np.cos(2 * np.pi * t / 10.0))
    left *= breath
    right *= breath

    buf = stereo(normalize(left, 0.8), normalize(right, 0.8))
    buf = make_loopable(buf, xfade)
    return normalize(buf, 0.72)                    # leave headroom under the UI


# --------------------------------------------------------------------------
# 2) UI koto pluck  — short, organic, string-like
# --------------------------------------------------------------------------
def make_koto():
    """A subtle koto pluck for button clicks (Karplus-Strong, E4, mellow)."""
    dur = 0.5
    pluck = karplus_strong(329.63, dur, decay=0.9955, seed=7, burst_lowpass=2600)
    # a touch of fundamental body so the pitch reads clearly
    t = tarr(dur)
    pluck += 0.15 * np.sin(2 * np.pi * 329.63 * t) * np.exp(-t / 0.18)
    pluck *= attack_decay(len(pluck), attack=0.002, decay=0.22)
    return fade(normalize(pluck, 0.85))


# --------------------------------------------------------------------------
# 3) Trigger: Grounded  — deep muffled taiko / earth thud
# --------------------------------------------------------------------------
def make_earth_thud():
    """Heavy, resonant, low impact: pitch-dropping sine + muffled skin transient."""
    dur = 0.9
    boom = swept_sine(dur, 88.0, 43.0, tau=0.08)       # the 'boom' pitch drop
    boom *= attack_decay(len(boom), attack=0.004, decay=0.42)

    # struck-skin transient: a short low-passed noise burst at the very start
    rng = np.random.default_rng(3)
    skin = lowpass(rng.standard_normal(len(boom)), 220.0)
    skin *= attack_decay(len(skin), attack=0.001, decay=0.045)

    hit = boom + 0.4 * normalize(skin, 1.0)
    hit = np.tanh(hit * 1.4)                            # gentle saturation = body
    hit = lowpass(hit, 300.0)                           # muffled
    return fade(normalize(hit, 0.92), fin=0.001, fout=0.05)


# --------------------------------------------------------------------------
# 4) Trigger: Teeth/Jaw  — hollow wooden mokugyo / temple block
# --------------------------------------------------------------------------
def make_temple_block():
    """Sharp, hollow, wooden knock via inharmonic modal synthesis + click."""
    dur = 0.22
    # inharmonic wood modes (ratios chosen to read as 'hollow block', not pitch)
    block = modal(dur, [
        (720.0, 1.00, 0.075),
        (1180.0, 0.55, 0.045),
        (2560.0, 0.30, 0.025),
        (430.0, 0.35, 0.11),        # low body resonance = the hollow 'tok'
    ])
    # wooden knock transient: a couple ms of high-passed noise
    rng = np.random.default_rng(5)
    click = bandpass(rng.standard_normal(len(block)), 1500.0, 6000.0)
    click *= attack_decay(len(click), attack=0.0003, decay=0.006)

    hit = block * attack_decay(len(block), 0.0005, 0.09) + 0.5 * normalize(click, 1.0)
    return fade(normalize(hit, 0.9), fin=0.0003, fout=0.03)


# --------------------------------------------------------------------------
# 5) Trigger: Breathe  — airy exhale followed by a delicate tingsha chime
# --------------------------------------------------------------------------
def make_breath_chime():
    """A soft exhale (shaped noise) then a tiny, shimmering high chime."""
    dur = 1.9
    n = int(dur * SR)
    t = tarr(dur)

    # --- exhale: band-passed noise, breath-shaped envelope (quick in, slow out) ---
    rng = np.random.default_rng(9)
    breath = bandpass(rng.standard_normal(n), 500.0, 2600.0)
    b_env = np.exp(-((t - 0.28) ** 2) / (2 * 0.22 ** 2))   # gaussian 'huff'
    breath = normalize(breath, 1.0) * b_env * 0.35

    # --- tingsha chime: bright inharmonic partials with slow shimmer decay ---
    start = int(0.42 * SR)                                  # enters as breath fades
    tc = np.arange(n - start) / SR
    chime = np.zeros(n - start)
    for f, a in [(1050.0, 0.30),     # bowl body
                 (2100.0, 1.00),     # the bright strike tone
                 (3160.0, 0.45),
                 (4300.0, 0.22)]:
        chime += a * np.sin(2 * np.pi * f * tc)
        chime += a * 0.6 * np.sin(2 * np.pi * f * 1.004 * tc)  # detune -> shimmer
    chime *= np.exp(-tc / 0.9)                              # long, delicate ring
    chime[:int(0.006 * SR)] *= np.linspace(0, 1, int(0.006 * SR))  # soft strike

    out = breath.copy()
    out[start:] += 0.6 * normalize(chime, 1.0)
    return fade(normalize(out, 0.85), fin=0.002, fout=0.08)


# --------------------------------------------------------------------------
# Build everything
# --------------------------------------------------------------------------
SOUNDS = {
    "zanshin_ambient.wav": make_ambient,
    "koto_pluck.wav":      make_koto,
    "earth_thud.wav":      make_earth_thud,
    "temple_block.wav":    make_temple_block,
    "breath_chime.wav":    make_breath_chime,
}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("Synthesizing Zanshin Zen audio -> %s\n" % OUT_DIR)
    for name, builder in SOUNDS.items():
        audio = builder()
        path = os.path.join(OUT_DIR, name)
        write_wav(path, audio)
        secs = len(audio) / SR
        kind = "stereo" if audio.ndim == 2 else "mono"
        print("  %-22s %5.2fs  %s" % (name, secs, kind))
    print("\nDone. Now run:  python onboarding_ui.py")


if __name__ == "__main__":
    main()
