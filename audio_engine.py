"""Sound engine: TTS (Edge Natural + SAPI5) and playback of SFX/recordings.

Two TTS engines:
  * "edge"  - Microsoft Edge Natural (neural voices). Cues are
              generated AHEAD into the cache in audio/tts_cache/, and
              in-game only a ready MP3 file is played. app.py does not
              generate a missing cue while listening (SAPI5 speaks it,
              it is prepared after the game).
  * "sapi"  - classic offline Windows SAPI5 voices.

IMPORTANT import order in app.py: the `gamepad` module MUST be imported
before this module. On import, `gamepad` sets SDL_AUDIODRIVER=dummy (the
windowless joystick), which would also silently mute the mixer below -
so here, right before pygame.mixer.init(), we remove this env var and let
SDL pick a real audio driver by itself (WASAPI/DirectSound). If this
module were imported BEFORE gamepad, the environment order would be
reversed and the mixer would stay mute.
"""

import ctypes
import hashlib
import importlib
import os
import threading
import queue
import time

import numpy as np

import hlas_kniznica
from i18n import tr
from paths import IS_WINDOWS, TTS_CACHE_DIR, nahrad_subor
from settings_model import EDGE_FALLBACK_VOICES, EDGE_PREMIUM_HINT

os.environ.pop("SDL_AUDIODRIVER", None)
import pygame  # noqa: E402  (must come after SDL_AUDIODRIVER is removed)

try:
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    pygame.mixer.set_num_channels(16)
    MIXER_AVAILABLE = True
except Exception:
    MIXER_AVAILABLE = False


# --------------------------------------------------------------------------
# edge-tts can also be installed at runtime -> the import is in a function
# so it can be retried with the "Try again" button without restarting the
# application.
# --------------------------------------------------------------------------

EDGE_AVAILABLE = False
asyncio = None
edge_tts = None
EDGE_IMPORT_ERROR = ""
# The version of the edge-tts currently in use, and whether it is the
# library downloaded with the "Update voice" button (hlas_kniznica.py).
# `importlib.metadata` always reports the BUNDLED version - the downloaded
# package has no dist-info.
EDGE_VERZIA = None
EDGE_STIAHNUTY = False


def load_edge():
    """Tries to import edge-tts (again). Returns True on success.

    A newer DOWNLOADED library (the "Update voice" button) takes priority
    over the bundled one - `hlas_kniznica.nacitaj_pri_starte` loads it
    under the real name "edge_tts". When it does not load, the bundled one
    is used and the downloaded one is marked as broken (app.log), so it is
    not tried on every start. The next Zanshin release with a newer bundled
    edge-tts wins by itself (newer version)."""
    global EDGE_AVAILABLE, asyncio, edge_tts, EDGE_IMPORT_ERROR, EDGE_VERZIA, EDGE_STIAHNUTY
    try:
        importlib.invalidate_caches()
        import asyncio as _asyncio
        try:
            stiahnuta = hlas_kniznica.nacitaj_pri_starte()
        except Exception:
            stiahnuta = None    # safeguard: the downloaded library must not break startup
        if stiahnuta is not None:
            _edge_tts, verzia = stiahnuta
        else:
            import edge_tts as _edge_tts
            verzia = hlas_kniznica.verzia_modulu(_edge_tts)
        asyncio, edge_tts = _asyncio, _edge_tts
        EDGE_VERZIA, EDGE_STIAHNUTY = verzia, stiahnuta is not None
        EDGE_AVAILABLE = True
        EDGE_IMPORT_ERROR = ""
    except Exception as exc:
        EDGE_AVAILABLE = False
        EDGE_VERZIA, EDGE_STIAHNUTY = None, False
        EDGE_IMPORT_ERROR = str(exc)
    return EDGE_AVAILABLE


def nastav_edge_tts(modul, verzia, stiahnuty=False, cache=None, cakanie_s=30.0):
    """Swaps the edge-tts module at runtime - `hlas_kniznica.aktualizuj`
    after a successful test word. From the return on, every cue goes
    through the new module.

    Call it from a HELPER thread: it waits (at most `cakanie_s`) for the
    `cache._lock` lock, which `EdgeTTSCache.ensure` holds during the whole
    synthesis and only reads `edge_tts` inside it - so after the return no
    cue is half-done with the old module. When the lock cannot be
    acquired, the swap happens anyway: assigning the module is atomic, and
    a cue that is in flight finishes with the old module it already holds.
    Returns True when the lock was held."""
    global EDGE_AVAILABLE, asyncio, edge_tts, EDGE_IMPORT_ERROR, EDGE_VERZIA, EDGE_STIAHNUTY
    import asyncio as _asyncio
    zamok = getattr(cache, "_lock", None)
    drzim = False
    if zamok is not None:
        try:
            drzim = bool(zamok.acquire(timeout=cakanie_s))
        except Exception:
            drzim = False
    try:
        # module before EDGE_AVAILABLE: whoever sees True has the module too
        asyncio, edge_tts = _asyncio, modul
        EDGE_VERZIA, EDGE_STIAHNUTY = verzia, bool(stiahnuty)
        EDGE_IMPORT_ERROR = ""
        EDGE_AVAILABLE = True
    finally:
        if drzim:
            zamok.release()
    return drzim


load_edge()


# --------------------------------------------------------------------------
# Audio playback / recording via Windows MCI (winmm) - no extra dependencies
# --------------------------------------------------------------------------

if IS_WINDOWS:
    _winmm = ctypes.WinDLL("winmm")
    _winmm.mciSendStringW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p,
                                      ctypes.c_uint, ctypes.c_void_p]
    _winmm.mciSendStringW.restype = ctypes.c_uint
else:
    _winmm = None


def mci(command):
    """Sends an MCI command; on error raises RuntimeError with details."""
    if _winmm is None:
        raise RuntimeError("MCI je dostupne len na Windows")
    buf = ctypes.create_unicode_buffer(512)
    err = _winmm.mciSendStringW(command, buf, 511, None)
    if err:
        ebuf = ctypes.create_unicode_buffer(512)
        _winmm.mciGetErrorStringW(err, ebuf, 511)
        raise RuntimeError(f"{ebuf.value.strip()} (prikaz: {command})")
    return buf.value


# --------------------------------------------------------------------------
# Notch filter (2000-4000 Hz) - protects the audibility of footsteps/reloads
# in competitive FPS games. It is applied to EVERY playback (SFX and the
# pre-generated Edge TTS cue alike), because both go through
# `play_audio_file` - filtering happens only after decoding (so it works the
# same for .wav and .mp3 sources).
# --------------------------------------------------------------------------

FOOTSTEP_NOTCH_LOW = 2000.0
FOOTSTEP_NOTCH_HIGH = 4000.0


def _notch_channel(samples, sr, low, high):
    n = len(samples)
    if n == 0:
        return samples
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    spec = np.fft.rfft(samples)
    spec[(freqs >= low) & (freqs <= high)] = 0.0
    return np.fft.irfft(spec, n)


def _notch_pcm16(raw_bytes, channels, sr, low=FOOTSTEP_NOTCH_LOW, high=FOOTSTEP_NOTCH_HIGH):
    """Zeroes the frequency band [low, high] Hz in a 16-bit PCM buffer
    (interleaved, if stereo). Uses an FFT - for short SFX/TTS clips it is
    practically instant."""
    samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float64)
    if channels == 2 and len(samples) % 2 == 0:
        stereo = samples.reshape(-1, 2)
        left = _notch_channel(stereo[:, 0], sr, low, high)
        right = _notch_channel(stereo[:, 1], sr, low, high)
        out = np.stack([left, right], axis=1).reshape(-1)
    else:
        out = _notch_channel(samples, sr, low, high)
    return np.clip(out, -32768, 32767).astype(np.int16).tobytes()


_NOTCH_MAX_S = 12.0     # above this clip length we skip the notch (see below)


def _apply_footstep_notch(sound):
    """Creates a new `pygame.mixer.Sound` with the 2-4 kHz band zeroed.

    If something goes wrong (unsupported format, silence, FFT error), it
    returns the original sound without the filter - better an unfiltered
    sound than none."""
    try:
        init = pygame.mixer.get_init()
        if not init:
            return sound
        freq, fmt, channels = init
        if abs(fmt) != 16:
            return sound
        raw = sound.get_raw()
        if not raw:
            return sound
        # A long custom clip (e.g. 2 min of music as SFX) would go through the
        # FFT whole on the playback thread = a stutter of several seconds
        # before playing. The notch makes sense for short SFX/cues; for long
        # ones we would rather skip it.
        if len(raw) > _NOTCH_MAX_S * max(1, freq) * max(1, channels) * 2:
            return sound
        filtered = _notch_pcm16(raw, channels, freq)
        return pygame.mixer.Sound(buffer=filtered)
    except Exception:
        return sound


def play_audio_file(path, volume=100, notch=True):
    """Plays a WAV/MP3 file through pygame.mixer and waits for it to finish
    (blocks the calling thread - always call it from a helper thread, never
    from the GUI).

    Every call uses its own `pygame.mixer.Sound`, so several files can
    sound at once on different channels - that is the basis of the
    "cues/SFX over each other" mode as well as the TTS+SFX combination.
    The volume is set directly on the given sound (0-100 -> 0.0-1.0), so
    the Volume slider immediately affects both what is playing right now
    and all further playbacks.

    `notch=True` (the default, used for SFX and Edge TTS): before playing,
    the 2-4 kHz band (opponents' footsteps/reloads in FPS games) is zeroed
    in the output, so DojoSync never covers the game sound. `notch=False`
    plays the file whole and clean - used for a CUSTOM VOICE RECORDING,
    which is deliberately as intelligible to a person as the offline
    (SAPI) voice, which does not go through the filter either."""
    if not MIXER_AVAILABLE:
        raise RuntimeError("pygame.mixer nie je dostupny")
    sound = pygame.mixer.Sound(path)
    if notch:
        sound = _apply_footstep_notch(sound)
    sound.set_volume(max(0.0, min(1.0, int(volume) / 100.0)))
    channel = sound.play()
    if channel is not None:
        while channel.get_busy():
            time.sleep(0.02)


def speak_sapi_isolated(text, voice_id, rate, volume=100):
    """Speaks text with its own SAPI instance - usable from several threads."""
    import comtypes
    import comtypes.client
    try:
        comtypes.CoInitialize()
    except Exception:
        pass
    try:
        voice = comtypes.client.CreateObject("SAPI.SpVoice")
        if voice_id:
            tokens = voice.GetVoices()
            for i in range(tokens.Count):
                token = tokens.Item(i)
                if token.Id == voice_id:
                    voice.Voice = token
                    break
        try:
            voice.Rate = int(rate)
        except Exception:
            pass
        try:
            voice.Volume = int(volume)
        except Exception:
            pass
        voice.Speak(text)
    finally:
        try:
            comtypes.CoUninitialize()
        except Exception:
            pass


class MicRecorder:
    """Recording from the microphone via MCI waveaudio."""

    ALIAS = "dandurf_rec"

    def __init__(self):
        self.active = False

    def start(self):
        if self.active:
            return
        mci(f"open new type waveaudio alias {self.ALIAS}")
        self.active = True
        for cmd in ("time format ms", "bitspersample 16", "channels 1",
                    "samplespersec 22050", "alignment 2", "bytespersec 44100"):
            try:
                mci(f"set {self.ALIAS} {cmd}")
            except Exception:
                pass
        mci(f"record {self.ALIAS}")

    def stop_and_save(self, path):
        if not self.active:
            return False
        # We save to .part first and only then atomically move the finished
        # file to its target place. If the MCI save failed halfway (full disk,
        # driver error), the previous good recording at `path` stays
        # untouched - not overwritten by a half-written, unplayable one (B3).
        # The old logic deleted `path` even before saving, so a failure meant
        # losing both.
        tmp = path + ".part"
        try:
            mci(f"stop {self.ALIAS}")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            mci(f'save {self.ALIAS} "{tmp}"')
            # The antivirus opens a fresh recording right away - `nahrad_subor`
            # survives such a short lock (.part is deleted by `finally` below).
            nahrad_subor(tmp, path)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            self._close()
        return True

    def cancel(self):
        if not self.active:
            return
        try:
            mci(f"stop {self.ALIAS}")
        except Exception:
            pass
        self._close()

    def _close(self):
        try:
            mci(f"close {self.ALIAS}")
        except Exception:
            pass
        self.active = False


# --------------------------------------------------------------------------
# Edge Natural TTS with a pre-generated cache
# --------------------------------------------------------------------------

def edge_rate_str(rate):
    """Slider -10..10 -> a string for edge-tts, e.g. '-20%'."""
    pct = int(rate) * 5
    return f"{pct:+d}%"


# --------------------------------------------------------------------------
# Kind of natural-voice error (0.3, audit 4)
# --------------------------------------------------------------------------
#
# WHY: every preparation failure said "check your internet" - even when the
# internet worked and Microsoft merely refused the request (HTTP
# 401/403/429, a refused WebSocket handshake). The player then looked for a
# fault in a network that was fine. Three kinds, each with different advice:
#   offline - connection, DNS, timeout: "check your internet"
#   refused - Microsoft said no: "try later or switch to Windows",
#             and if it persists, a new Zanshin version (an old edge-tts
#             gets refused)
#   other   - anything else (empty output, full disk, library error)
# The decision is made by the class NAMES in the exception and its causes
# (`__cause__`, `__context__`), not by importing aiohttp - it does not have
# to be here and the tests slip in their own classes. A pure function, no
# error gets out.
EDGE_CHYBA_OFFLINE = "offline"
EDGE_CHYBA_ODMIETNUTE = "refused"
EDGE_CHYBA_INA = "other"

_EDGE_ODMIETNUTE_STATUSY = (401, 403, 429)
_EDGE_ODMIETNUTE_TRIEDY = frozenset({"WSServerHandshakeError"})
_EDGE_OFFLINE_TRIEDY = frozenset({
    "ClientConnectorError", "ClientConnectorDNSError", "ClientConnectionError",
    "ClientOSError", "ServerDisconnectedError",
    "ServerTimeoutError", "ConnectionTimeoutError", "SocketTimeoutError",
    "ClientProxyConnectionError", "gaierror", "herror", "timeout", "TimeoutError",
    "ConnectionError", "ConnectionRefusedError", "ConnectionResetError",
    "ConnectionAbortedError",
})


def druh_chyby_edge(exc):
    """Kind of error while preparing the natural voice: `EDGE_CHYBA_*`."""
    try:
        offline = False
        videne = set()
        while exc is not None and id(exc) not in videne and len(videne) < 8:
            videne.add(id(exc))
            mena = {c.__name__ for c in type(exc).__mro__}
            try:
                status = int(getattr(exc, "status", None) or 0)
            except (TypeError, ValueError):
                status = 0
            if mena & _EDGE_ODMIETNUTE_TRIEDY or status in _EDGE_ODMIETNUTE_STATUSY:
                return EDGE_CHYBA_ODMIETNUTE
            if mena & _EDGE_OFFLINE_TRIEDY:
                offline = True
            exc = exc.__cause__ or exc.__context__
        return EDGE_CHYBA_OFFLINE if offline else EDGE_CHYBA_INA
    except Exception:
        return EDGE_CHYBA_INA


class EdgeTTSCache:
    """Generates MP3 cues via edge-tts and keeps them in audio/tts_cache/.

    The goal is that no network is called during play: all cues are ready
    in advance and the trigger only plays a local file. When one is
    missing, `app._speak_text` does not go to the network while listening
    and postpones it until later.
    """

    def __init__(self, log):
        self.log = log
        self._lock = threading.Lock()
        # The last `ensure` error - SEPARATELY FOR EACH THREAD: the preparation
        # and a cue postponed until after the game are called by different
        # threads, and one must not overwrite why the other failed
        # (`posledna_chyba`, 0.3).
        self._chyba = threading.local()

    def posledna_chyba(self):
        """(kind, exception) of the last failed `ensure` in THIS thread, or
        None when the last `ensure` did not fail. Kind is `EDGE_CHYBA_*`."""
        chyba = getattr(self, "_chyba", None)
        return getattr(chyba, "posledna", None) if chyba is not None else None

    def _zapamataj_chybu(self, exc):
        chyba = getattr(self, "_chyba", None)
        if chyba is None:
            return
        chyba.posledna = None if exc is None else (druh_chyby_edge(exc), exc)

    # ---- paths ----

    @staticmethod
    def key_for(text, voice, rate):
        raw = f"{voice}|{edge_rate_str(rate)}|{text}".encode("utf-8")
        return hashlib.sha1(raw).hexdigest()[:20]

    def path_for(self, text, voice, rate):
        return os.path.join(TTS_CACHE_DIR, f"{self.key_for(text, voice, rate)}.mp3")

    def has(self, text, voice, rate):
        try:
            return os.path.getsize(self.path_for(text, voice, rate)) > 0
        except OSError:
            return False

    # ---- generation ----

    def ensure(self, text, voice, rate, abort=None):
        """Generates a cue if it is not in the cache yet. Returns a path or None.

        Blocks - always call it from a helper thread, never from the GUI
        or from a listener.

        `abort` (optional, no arguments) is asked right before sending to
        Microsoft - already AFTER acquiring the lock. The preparation
        thread may wait on the lock while another thread finishes its cue;
        if listening was turned on in the meantime (or the preparation was
        replaced by a newer one), `abort()` returns True and the new
        request is not started - None is returned. A finished file from
        the cache is returned anyway (it does not go to the network).
        """
        self._zapamataj_chybu(None)
        if not (EDGE_AVAILABLE and text and text.strip() and voice):
            return None
        path = self.path_for(text, voice, rate)
        if self.has(text, voice, rate):
            return path

        with self._lock:
            if self.has(text, voice, rate):
                return path
            if abort is not None and abort():
                return None
            os.makedirs(TTS_CACHE_DIR, exist_ok=True)
            tmp = f"{path}.{os.getpid()}.part"

            async def _run():
                comm = edge_tts.Communicate(text, voice, rate=edge_rate_str(rate))
                await comm.save(tmp)

            try:
                asyncio.run(_run())
                if os.path.getsize(tmp) <= 0:
                    raise RuntimeError(tr("internal.empty_output"))
                # `nahrad_subor` survives a short lock on the fresh
                # .part (antivirus); on error the except below deletes .part
                nahrad_subor(tmp, path)
            except Exception as exc:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                self._zapamataj_chybu(exc)
                self.log(tr("log.edge_gen_failed", text=text, err=exc))
                return None
        return path

    # ---- voice list ----

    @staticmethod
    def list_voices():
        """Selection of Edge voices for the combobox - a fixed list from
        `EDGE_FALLBACK_VOICES`, WITHOUT THE NETWORK.

        Previously a live catalogue was pulled from Microsoft here (on
        every start, while Edge was selected - and it is the default),
        only to be trimmed down to exactly this hand-picked list and to
        add a translated word for the gender. The gender is now right in
        the list and the description is put together via tr(), so the app
        goes to Microsoft only when preparing the cues themselves
        (`ensure`). Returns [(short_name, popis)] in list order."""
        rod = {"f": tr("voice.female"), "m": tr("voice.male")}
        items = []
        for short, meno, pohlavie in EDGE_FALLBACK_VOICES:
            locale = "-".join(short.split("-")[:2])
            premium = any(h in short for h in EDGE_PREMIUM_HINT)
            suffix = f", {tr('voice.most_natural')}" if premium else ""
            items.append((short, f"{locale} · {meno} ({rod.get(pohlavie, '')}{suffix})"))
        return items

    # ---- maintenance ----

    @staticmethod
    def prune(keep_paths):
        """Deletes files from the cache that no slot uses any more."""
        keep = {os.path.normcase(p) for p in keep_paths if p}
        try:
            names = os.listdir(TTS_CACHE_DIR)
        except OSError:
            return
        for name in names:
            full = os.path.join(TTS_CACHE_DIR, name)
            if os.path.normcase(full) in keep:
                continue
            try:
                os.remove(full)
            except OSError:
                pass


# --------------------------------------------------------------------------
# Sound thread: TTS (SAPI5) + file playback in one queue
# --------------------------------------------------------------------------

class SpeechWorker(threading.Thread):
    """One thread for all sound. The GUI and listeners never get blocked.

    TTS goes primarily straight through SAPI.SpVoice (comtypes) - that is
    more reliable than repeated pyttsx3 runAndWait(), which often freezes
    after the first playback, and further cues no longer sound.
    """

    def __init__(self, log, on_voices=None):
        super().__init__(daemon=True)
        self.log = log
        self.on_voices = on_voices
        self.queue = queue.Queue()
        self._running = True
        self._voice = None          # SAPI SpVoice
        self._tokens = {}           # id -> token
        self.pending_voice = None
        self.pending_rate = None
        self.pending_volume = None
        self._voice_id = None
        self._rate = 0
        self._volume = 100

    # ---- public API (callable from any thread) ----

    def speak(self, text, voice_id=None):
        if text and text.strip():
            self.queue.put(("say", (text, voice_id)))

    def play(self, path, volume=None):
        """`volume` overrides the current global volume for this one
        playback - used for the separate SFX/TTS volumes."""
        self.queue.put(("play", (path, volume)))

    def set_voice(self, voice_id):
        self.queue.put(("voice", voice_id))

    def set_rate(self, rate):
        self.queue.put(("rate", rate))

    def set_volume(self, volume):
        self.queue.put(("volume", volume))

    def stop(self):
        self._running = False
        self.queue.put(("quit", None))

    # ---- internal ----

    def _init_sapi(self):
        try:
            import comtypes
            import comtypes.client
            try:
                comtypes.CoInitialize()
            except Exception:
                pass
            self._voice = comtypes.client.CreateObject("SAPI.SpVoice")
            voices = self._voice.GetVoices()
            items = []
            for i in range(voices.Count):
                tok = voices.Item(i)
                try:
                    name = tok.GetDescription()
                except Exception:
                    name = tr("voice.fallback_name", n=i + 1)
                self._tokens[tok.Id] = tok
                items.append((tok.Id, name))
            if self.on_voices:
                self.on_voices(items)
            self.log(tr("log.sapi_ready", n=len(items)))
        except Exception as exc:
            self._voice = None
            self.log(tr("log.sapi_unavailable", err=exc))

    def _say_sapi(self, text, voice_id):
        token = self._tokens.get(voice_id or self._voice_id)
        if token is not None:
            try:
                self._voice.Voice = token
            except Exception:
                pass
        self._voice.Speak(text)

    def _say_pyttsx3(self, text, voice_id):
        # Always a fresh engine - a shared engine in pyttsx3 often stops
        # speaking after the first runAndWait().
        import pyttsx3
        engine = pyttsx3.init()
        try:
            target = voice_id or self._voice_id
            if target:
                try:
                    engine.setProperty("voice", target)
                except Exception:
                    pass
            try:
                engine.setProperty("rate", max(60, 200 + int(self._rate) * 15))
            except Exception:
                pass
            try:
                engine.setProperty("volume", max(0.0, min(1.0, self._volume / 100.0)))
            except Exception:
                pass
            engine.say(text)
            engine.runAndWait()
        finally:
            try:
                engine.stop()
            except Exception:
                pass
            del engine

    def run(self):
        # START INSIDE try = a single COM error (an uninstalled/broken SAPI
        # voice, a failed init, a saved voice that no longer exists) killed the
        # whole sound thread BEFORE the loop - and from then on no TTS, no SFX,
        # no cue, without a single word (bug B14). When the start fails, we
        # fall back to pyttsx3 (`_voice = None`) and the thread keeps running,
        # so the app at least speaks and plays sounds.
        try:
            if IS_WINDOWS:
                self._init_sapi()
            if self.pending_voice:
                self._apply_voice(self.pending_voice)
            if self.pending_rate is not None:
                self._apply_rate(self.pending_rate)
            if self.pending_volume is not None:
                self._apply_volume(self.pending_volume)
        except Exception as exc:
            self.log(tr("log.audio_error", err=exc))
            self._voice = None

        while self._running:
            kind, payload = self.queue.get()
            if kind == "quit":
                break
            try:
                if kind == "say":
                    text, voice_id = payload
                    if self._voice is not None:
                        self._say_sapi(text, voice_id)
                    else:
                        self._say_pyttsx3(text, voice_id)
                elif kind == "play":
                    path, volume = payload
                    play_audio_file(path, self._volume if volume is None else volume)
                elif kind == "voice":
                    self._apply_voice(payload)
                elif kind == "rate":
                    self._apply_rate(payload)
                elif kind == "volume":
                    self._apply_volume(payload)
            except Exception as exc:
                self.log(tr("log.audio_error", err=exc))

    def _apply_voice(self, voice_id):
        self._voice_id = voice_id
        if self._voice is None or not voice_id:
            return
        tok = self._tokens.get(voice_id)
        if tok is not None:
            self._voice.Voice = tok

    def _apply_rate(self, rate):
        self._rate = int(rate)
        if self._voice is None:
            return
        self._voice.Rate = int(rate)

    def _apply_volume(self, volume):
        self._volume = int(volume)
        if self._voice is None:
            return
        try:
            self._voice.Volume = self._volume
        except Exception:
            pass


class AudioDispatcher:
    """Decides whether sounds play one after another (a queue) or over
    each other.

    SFX (sound effects) and TTS (voice) have separate volumes -
    `sfx_volume` and `tts_volume` - both derived from the global Volume
    slider and the SFX/Voice balance slider (see
    DandurfApp._recompute_volumes)."""

    def __init__(self, worker, log):
        self.worker = worker
        self.log = log
        self.overlap = False
        self.rate = 0
        self.sfx_volume = 100
        self.tts_volume = 100

    def play(self, path, volume=None):
        """Plays an SFX file. `volume` (if given) overrides `sfx_volume` -
        used when it is in fact TTS content (see `play_tts`)."""
        vol = self.sfx_volume if volume is None else volume
        if self.overlap:
            threading.Thread(target=self._play_now, args=(path, vol),
                             daemon=True).start()
        else:
            self.worker.play(path, vol)

    def play_tts(self, path):
        """Plays a pre-generated Edge TTS cue (.mp3) - always at TTS volume."""
        self.play(path, volume=self.tts_volume)

    def speak(self, text, voice_id):
        if not (text and text.strip()):
            return
        if self.overlap:
            threading.Thread(target=self._speak_now, args=(text, voice_id),
                             daemon=True).start()
        else:
            self.worker.speak(text, voice_id)

    def _play_now(self, path, volume):
        try:
            play_audio_file(path, volume)
        except Exception as exc:
            self.log(tr("log.playback_error", err=exc))

    def _speak_now(self, text, voice_id):
        try:
            speak_sapi_isolated(text, voice_id, self.rate, self.tts_volume)
        except Exception as exc:
            self.log(tr("log.tts_error", err=exc))
