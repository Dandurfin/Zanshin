"""Zabudovana kniznica kratkych meditacnych / herných SFX zvukov.

Kazdy vizualny rezim (Zen Dojo / Modern Gamer) ma vlastnu sadu 4 zvukov.
Pri prvom starte `ensure_assets()`:
  1. Pre zvuky, kde mame overeny stabilny CC0 zdroj (Kenney Interface
     Sounds, balicek na GitHube), sa skusi stiahnutie (kratky timeout).
  2. Vsetko ostatne - a hlavne organicke/meditativne tony, pre ktore
     ziadny spolahlivy volne dostupny subor neexistuje - sa vygeneruje
     lokalne cez numpy priamo do .wav (ziadna zavislost na sieti).

Vysledne .wav su kratke (0.35 - 1.2 s), bez ticha na zaciatku, mono
16-bit PCM 44100 Hz - hotove na okamzite neblokujuce prehratie.
"""

import hashlib
import os
import urllib.request
import wave

import numpy as np

from i18n import tr
from paths import SOUNDS_DIR

SR = 44100

# Kenney "Interface Sounds" - CC0 1.0, zabalene na GitHube s priamymi
# surovymi (raw) URL na jednotlive .wav subory. Overene priamym stiahnutim.
KENNEY_BASE = ("https://raw.githubusercontent.com/Calinou/kenney-interface-"
               "sounds/master/addons/kenney_interface_sounds/")


# --------------------------------------------------------------------------
# nizkourovnove DSP pomocky (cisto numpy, ziadne scipy)
# --------------------------------------------------------------------------

def _t(dur, sr=SR):
    return np.linspace(0.0, dur, int(sr * dur), endpoint=False)


def _noise(dur, sr=SR):
    n = int(sr * dur)
    return np.random.uniform(-1.0, 1.0, n)


def _band_limit(sig, low, high, sr=SR):
    """FFT orezanie signalu na dane frekvencne pasmo (jednoduchy band/high/low-pass)."""
    n = len(sig)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    spec = np.fft.rfft(sig)
    mask = np.ones_like(freqs, dtype=bool)
    if low is not None:
        mask &= freqs >= low
    if high is not None:
        mask &= freqs <= high
    spec = spec * mask
    return np.fft.irfft(spec, n)


def _fade(sig, fade_in=0.003, fade_out=0.05, sr=SR):
    sig = sig.copy()
    n_in = max(1, int(fade_in * sr))
    n_out = max(1, int(fade_out * sr))
    n_in = min(n_in, len(sig) // 2)
    n_out = min(n_out, len(sig) // 2)
    sig[:n_in] *= np.linspace(0.0, 1.0, n_in)
    sig[-n_out:] *= np.linspace(1.0, 0.0, n_out)
    return sig


def _normalize(sig, peak=0.92):
    m = float(np.max(np.abs(sig))) if len(sig) else 0.0
    if m < 1e-9:
        return sig
    return sig / m * peak


# Kroky a prebijanie protihracov v kompetitivnych FPS su najlepsie citatelne
# v pasme 2-4 kHz - vsetky vygenerovane SFX preto v tomto pasme nesmu niesc
# ziadnu energiu, aby DojoSync nikdy neprekryl herny zvuk (viz. aj rovnaky
# filter aplikovany este raz pri prehravani v main.py - dvojita poistka).
FOOTSTEP_NOTCH_LOW = 2000.0
FOOTSTEP_NOTCH_HIGH = 4000.0


def _notch(sig, low=FOOTSTEP_NOTCH_LOW, high=FOOTSTEP_NOTCH_HIGH, sr=SR):
    """FFT band-stop - vynuluje dane frekvencne pasmo, zvysok necha bezo zmeny."""
    n = len(sig)
    if n == 0:
        return sig
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    spec = np.fft.rfft(sig)
    spec[(freqs >= low) & (freqs <= high)] = 0.0
    return np.fft.irfft(spec, n)


def _save_wav(path, sig, sr=SR):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sig = _notch(sig, sr=sr)
    sig = np.clip(sig, -1.0, 1.0)
    data = (sig * 32767.0).astype(np.int16)
    tmp = f"{path}.tmp"
    with wave.open(tmp, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(data.tobytes())
    os.replace(tmp, path)


# --------------------------------------------------------------------------
# ZEN DOJO - organicke, meditativne tony
# --------------------------------------------------------------------------

def _synth_earth_thud(path):
    """Tlmeny zemity dopad pre ťažisko / crouch (40-80 Hz sine + decay)."""
    dur = 0.5
    t = _t(dur)
    drop = 80.0 - 40.0 * (t / dur)
    tone = np.sin(2 * np.pi * np.cumsum(drop) / SR) * np.exp(-t * 9.0)
    thump = _band_limit(_noise(dur), 40, 260) * np.exp(-t * 22.0)
    sig = _normalize(tone * 0.85 + thump * 0.5)
    _save_wav(path, _fade(sig, fade_out=0.08))


def _synth_wood_temple_block(path):
    """Suché drevene klopnutie kláštorného klepadla pre zuby / reload
    (perkusívny ~800 Hz tón s krátkym dozvukom)."""
    dur = 0.35
    t = _t(dur)
    click = _band_limit(_noise(dur), 600, 2200) * np.exp(-t * 45.0)
    body = np.sin(2 * np.pi * 820 * t) * np.exp(-t * 40.0)
    sig = _normalize(click * 0.7 + body * 0.6)
    _save_wav(path, _fade(sig, fade_out=0.05))


def _synth_singing_bowl(path):
    """Mäkký vibrujúci tón tibetskej misky pre uvoľnenie / ADS
    (528 Hz + harmonické, 1.5 s hladký dozvuk)."""
    dur = 1.6
    t = _t(dur)
    attack = np.clip(t / 0.04, 0.0, 1.0)
    decay = np.exp(-t * 1.5)
    env = attack * decay
    tone = (np.sin(2 * np.pi * 528 * t)
            + 0.6 * np.sin(2 * np.pi * 532 * t)
            + 0.3 * np.sin(2 * np.pi * 1056 * t)
            + 0.15 * np.sin(2 * np.pi * 1584 * t))
    sig = _normalize(tone * env)
    _save_wav(path, _fade(sig, fade_in=0.01, fade_out=1.5))


def _synth_breath_chime(path):
    """Jemný filtrovaný dychový šum (band-pass, 1.2 s) s cinknutím pre
    nádych / F - simuluje pokojný výdych."""
    dur = 1.2
    t = _t(dur)
    swell = np.sin(np.pi * t / dur) ** 1.5
    breath = _band_limit(_noise(dur), 200, 900) * swell * 0.55
    chime_t = _t(dur * 0.45)
    chime = np.zeros_like(t)
    tail = np.sin(2 * np.pi * 1760 * chime_t) * np.exp(-chime_t * 6.0) * 0.35
    chime[-len(tail):] = tail
    sig = _normalize(breath + chime)
    _save_wav(path, _fade(sig, fade_out=0.15))


# --------------------------------------------------------------------------
# MODERN GAMER - takticke, sci-fi UI odozvy
# --------------------------------------------------------------------------

def _synth_mech_bass_thump(path):
    """Hlboký mechanický bass drop pre ťažisko / crouch."""
    dur = 0.4
    t = _t(dur)
    drop = 130.0 - 90.0 * (t / dur)
    tone = np.sin(2 * np.pi * np.cumsum(drop) / SR)
    tone = np.tanh(tone * 1.6) * np.exp(-t * 12.0)
    punch = _band_limit(_noise(0.05), 40, 400)
    punch = np.pad(punch, (0, len(t) - len(punch)))
    sig = _normalize(tone * 0.9 + punch * 0.6)
    _save_wav(path, _fade(sig, fade_out=0.06))


def _synth_click_reload_fallback(path):
    """Hladké sci-fi cvaknutie - pouzije sa len ak zlyha stiahnutie."""
    dur = 0.12
    t = _t(dur)
    tick = _band_limit(_noise(dur), 1500, 6000) * np.exp(-t * 90.0)
    blip = np.sign(np.sin(2 * np.pi * 420 * t)) * np.exp(-t * 70.0) * 0.4
    sig = _normalize(tick * 0.8 + blip)
    _save_wav(path, _fade(sig, fade_in=0.001, fade_out=0.03))


def _synth_lock_ping_fallback(path):
    """Čistý UI ping / laser-lock blip - pouzije sa len ak zlyha stiahnutie."""
    dur = 0.16
    t = _t(dur)
    sweep = 1200.0 + 800.0 * (t / dur)
    tone = np.sin(2 * np.pi * np.cumsum(sweep) / SR) * np.exp(-t * 18.0)
    sig = _normalize(tone)
    _save_wav(path, _fade(sig, fade_in=0.001, fade_out=0.05))


def _synth_vent_release(path):
    """Zvuk pretlakového ventilu / cyber vent release pre dych / F."""
    dur = 0.55
    t = _t(dur)
    env = np.exp(-t * 5.0)
    hiss = _band_limit(_noise(dur), 2200, 7000) * env
    sig = _normalize(hiss)
    _save_wav(path, _fade(sig, fade_in=0.002, fade_out=0.15))


# --------------------------------------------------------------------------
# kniznica
# --------------------------------------------------------------------------

ZEN = "zen"
MODERN = "modern"

SOUND_LIBRARY = {
    ZEN: {
        "earth_thud": {
            "label_key": "sfx.zen.earth_thud",
            "file": "earth_thud.wav",
            "synth": _synth_earth_thud,
        },
        "wood_temple_block": {
            "label_key": "sfx.zen.wood_temple_block",
            "file": "wood_temple_block.wav",
            "synth": _synth_wood_temple_block,
        },
        "zen_singing_bowl": {
            "label_key": "sfx.zen.zen_singing_bowl",
            "file": "zen_singing_bowl.wav",
            "synth": _synth_singing_bowl,
        },
        "soft_breath_chime": {
            "label_key": "sfx.zen.soft_breath_chime",
            "file": "soft_breath_chime.wav",
            "synth": _synth_breath_chime,
        },
    },
    MODERN: {
        "mech_bass_thump": {
            "label_key": "sfx.modern.mech_bass_thump",
            "file": "mech_bass_thump.wav",
            "synth": _synth_mech_bass_thump,
        },
        "sfx_click_reload": {
            "label_key": "sfx.modern.sfx_click_reload",
            "file": "sfx_click_reload.wav",
            "synth": _synth_click_reload_fallback,
            "download_url": KENNEY_BASE + "click_003.wav",
            "sha256": "b035afe3fe08b0fd3517c612bdfd362799bffe762d2cbf8f09e6a50322067358",
        },
        "sfx_lock_ping": {
            "label_key": "sfx.modern.sfx_lock_ping",
            "file": "sfx_lock_ping.wav",
            "synth": _synth_lock_ping_fallback,
            "download_url": KENNEY_BASE + "confirmation_002.wav",
            "sha256": "b23339f3fdcd9f54520ca73caa3a9ae93ecfb3675acdaf1468990feb5d55d5fa",
        },
        "vent_release": {
            "label_key": "sfx.modern.vent_release",
            "file": "vent_release.wav",
            "synth": _synth_vent_release,
        },
    },
}

# Poradie zvukov -> automaticke priradenie novym slotom podla ich indexu
# (slot 1 = ťažisko/crouch, slot 2 = zuby/reload, slot 3 = uvoľnenie/ADS,
#  slot 4 = dych, dalsie sloty uz bez auto-priradenia).
DEFAULT_SLOT_SOUND_ORDER = {
    ZEN: ["earth_thud", "wood_temple_block", "zen_singing_bowl", "soft_breath_chime"],
    MODERN: ["mech_bass_thump", "sfx_click_reload", "sfx_lock_ping", "vent_release"],
}


def sound_path(pack, key):
    info = SOUND_LIBRARY.get(pack, {}).get(key)
    if not info:
        return None
    return os.path.join(SOUNDS_DIR, pack, info["file"])


def sound_label(pack, key):
    info = SOUND_LIBRARY.get(pack, {}).get(key)
    return tr(info["label_key"]) if info else key


def library_items(pack):
    return [(key, tr(info["label_key"])) for key, info in SOUND_LIBRARY.get(pack, {}).items()]


def default_sound_for_slot_index(pack, index):
    order = DEFAULT_SLOT_SOUND_ORDER.get(pack, [])
    return order[index] if 0 <= index < len(order) else ""


def _try_download(url, path, expected_sha256=None, timeout=4.0):
    req = urllib.request.Request(url, headers={"User-Agent": "Zanshin/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    if len(data) < 200 or data[:4] != b"RIFF":
        raise ValueError("neplatný WAV obsah")
    if expected_sha256:
        # Integrity pin: aj ked ide o HTTPS a dovryhodny CC0 zdroj (Kenney),
        # overujeme presny obsah súboru voči hashu zaznamenanému v
        # SOUND_LIBRARY - appka ma aj tak lokalny numpy fallback, takze
        # tu nema zmysel dovcrovat tretej strane viac, nez je nutne.
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected_sha256:
            raise ValueError(
                f"SHA-256 nesedí (očakávané {expected_sha256[:12]}…, "
                f"prišlo {actual[:12]}…) - zdroj sa mohol zmeniť")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _all_sound_paths():
    return [os.path.join(SOUNDS_DIR, pack, info["file"])
            for pack, sounds in SOUND_LIBRARY.items() for info in sounds.values()]


def missing_count():
    """Kolko zo zabudovanych SFX este chyba na disku (0 = vsetko pripravene)."""
    missing = 0
    for path in _all_sound_paths():
        try:
            if os.path.getsize(path) > 0:
                continue
        except OSError:
            pass
        missing += 1
    return missing


def ensure_assets(log=None, progress=None):
    """Zaisti, ze vsetky bundled SFX existuju - stiahne alebo vygeneruje.

    Blokuje (siet + numpy synteza) - vola sa z pomocneho vlakna pri starte.
    `progress(done, total)` sa vola po kazdom vybavenom subore (aj preskocenom),
    aby volajuci mohol zobrazit priebeh (napr. v Onboarding sprievodcovi).
    """
    def _log(msg):
        if log:
            try:
                log(msg)
            except Exception:
                pass

    items = [(pack, key, info) for pack, sounds in SOUND_LIBRARY.items()
             for key, info in sounds.items()]
    total = len(items)

    def _progress(done):
        if progress:
            try:
                progress(done, total)
            except Exception:
                pass

    _progress(0)
    for done, (pack, key, info) in enumerate(items, start=1):
        path = os.path.join(SOUNDS_DIR, pack, info["file"])
        try:
            if os.path.getsize(path) > 0:
                _progress(done)
                continue
        except OSError:
            pass

        label = tr(info["label_key"])
        url = info.get("download_url")
        ok = False
        if url:
            try:
                _try_download(url, path, expected_sha256=info.get("sha256"))
                ok = True
                _log(tr("sfx.log.downloaded", label=label))
            except Exception:
                ok = False

        if not ok:
            try:
                info["synth"](path)
                log_key = "sfx.log.synth_fallback" if url else "sfx.log.synth"
                _log(tr(log_key, label=label))
            except Exception as exc:
                _log(tr("sfx.log.failed", label=label, err=exc))
        _progress(done)
