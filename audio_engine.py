"""Zvukovy engine: TTS (Edge Natural + SAPI5) a prehravanie SFX/nahravok.

Dva TTS motory:
  * "edge"  - Microsoft Edge Natural (neuronove hlasy). Hlasky sa
              generuju DOPREDU do cache v audio/tts_cache/ a v hre sa uz
              len prehra hotovy MP3 subor. Chybajucu hlasku app.py pocas
              pocuvania negeneruje (zaznie SAPI5, dopripravi sa po hre).
  * "sapi"  - klasicke offline Windows SAPI5 hlasy.

DOLEZITE poradie importov v app.py: modul `gamepad` MUSI byt naimportovany
skor nez tento modul. `gamepad` pri importe nastavi SDL_AUDIODRIVER=dummy
(bezokenny joystick), co by potichu umlcalo aj mixer nizsie - preto tu,
tesne pred pygame.mixer.init(), tento env var odstranime a necháme SDL,
nech si samo vyberie realny zvukovy ovladac (WASAPI/DirectSound). Ak by sa
tento modul naimportoval SKOR nez gamepad, poradie prostredia by sa
prehodilo a mixer by ostal nemy.
"""

import ctypes
import hashlib
import importlib
import os
import threading
import queue
import time

import numpy as np

from i18n import tr
from paths import IS_WINDOWS, TTS_CACHE_DIR
from settings_model import EDGE_FALLBACK_VOICES, EDGE_PREMIUM_HINT

os.environ.pop("SDL_AUDIODRIVER", None)
import pygame  # noqa: E402  (musi byt az po odstraneni SDL_AUDIODRIVER)

try:
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    pygame.mixer.set_num_channels(16)
    MIXER_AVAILABLE = True
except Exception:
    MIXER_AVAILABLE = False


# --------------------------------------------------------------------------
# edge-tts sa da doinstalovat aj za behu -> import je vo funkcii, aby sa dal
# zopakovat tlacidlom "Skusit znova" bez restartu aplikacie.
# --------------------------------------------------------------------------

EDGE_AVAILABLE = False
asyncio = None
edge_tts = None
EDGE_IMPORT_ERROR = ""


def load_edge():
    """Skusi (znovu) naimportovat edge-tts. Vracia True pri uspechu."""
    global EDGE_AVAILABLE, asyncio, edge_tts, EDGE_IMPORT_ERROR
    try:
        importlib.invalidate_caches()
        import asyncio as _asyncio
        import edge_tts as _edge_tts
        asyncio, edge_tts = _asyncio, _edge_tts
        EDGE_AVAILABLE = True
        EDGE_IMPORT_ERROR = ""
    except Exception as exc:
        EDGE_AVAILABLE = False
        EDGE_IMPORT_ERROR = str(exc)
    return EDGE_AVAILABLE


load_edge()


# --------------------------------------------------------------------------
# Prehravanie / nahravanie audia cez Windows MCI (winmm) - bez extra zavislosti
# --------------------------------------------------------------------------

if IS_WINDOWS:
    _winmm = ctypes.WinDLL("winmm")
    _winmm.mciSendStringW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p,
                                      ctypes.c_uint, ctypes.c_void_p]
    _winmm.mciSendStringW.restype = ctypes.c_uint
else:
    _winmm = None


def mci(command):
    """Posle MCI prikaz, pri chybe vyhodi RuntimeError s popisom."""
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
# Notch filter (2000-4000 Hz) - ochrana citatelnosti krokov/prebijania v
# kompetitivnych FPS. Aplikuje sa na KAZDE prehratie (SFX aj predgenerovana
# Edge TTS hlaska), pretoze obe idu cez `play_audio_file` - filtruje sa az
# po dekodovani (funguje teda rovnako pre .wav aj .mp3 zdroje).
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
    """Vynuluje frekvencne pasmo [low, high] Hz v 16-bit PCM bufferi
    (interleaved, ak je stereo). Pouziva FFT - pre kratke SFX/TTS klipy je
    prakticky okamzite."""
    samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float64)
    if channels == 2 and len(samples) % 2 == 0:
        stereo = samples.reshape(-1, 2)
        left = _notch_channel(stereo[:, 0], sr, low, high)
        right = _notch_channel(stereo[:, 1], sr, low, high)
        out = np.stack([left, right], axis=1).reshape(-1)
    else:
        out = _notch_channel(samples, sr, low, high)
    return np.clip(out, -32768, 32767).astype(np.int16).tobytes()


_NOTCH_MAX_S = 12.0     # nad tuto dlzku klipu notch preskocime (viz nizsie)


def _apply_footstep_notch(sound):
    """Vytvori novy `pygame.mixer.Sound` s vynulovanym pasmom 2-4 kHz.

    Ak sa nieco pokazi (nepodporovany format, ticho, chyba FFT), vrati
    povodny zvuk bez filtra - radsej nefiltrovany zvuk nez ziadny."""
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
        # Dlhy vlastny klip (napr. 2-min hudba ako SFX) by cely presiel FFT-om
        # na prehravacom vlakne = viacsekundove seknutie pred prehratim. Notch
        # ma zmysel pre kratke SFX/hlasky; pri dlhych ho radsej preskocime.
        if len(raw) > _NOTCH_MAX_S * max(1, freq) * max(1, channels) * 2:
            return sound
        filtered = _notch_pcm16(raw, channels, freq)
        return pygame.mixer.Sound(buffer=filtered)
    except Exception:
        return sound


def play_audio_file(path, volume=100, notch=True):
    """Prehra WAV/MP3 subor cez pygame.mixer a pocka na dokoncenie (blokuje
    volajuce vlakno - volaj vzdy z pomocneho vlakna, nikdy z GUI).

    Kazde volanie pouziva vlastny `pygame.mixer.Sound`, takze viacero
    suborov moze znieť naraz na roznych kanaloch - to je zaklad rezimu
    "hlasky/SFX cez seba" aj kombinacie TTS+SFX. Hlasitost sa nastavuje
    priamo na danom zvuku (0-100 -> 0.0-1.0), takze posuvnik Hlasitost
    okamzite ovplyvnuje aj prave bezice aj vsetky dalsie prehratia.

    `notch=True` (predvolba, pouziva sa pre SFX aj Edge TTS): pred prehratim
    sa z vystupu vynuluje pasmo 2-4 kHz (kroky/prebijanie protihracov v FPS),
    aby DojoSync nikdy neprekryl herny zvuk. `notch=False` prehra subor cely
    a cisty - pouziva sa pre VLASTNU NAHRAVKU HLASU, ktora je zamerne cloveku
    zrozumitelna rovnako ako offline (SAPI) hlas, co filtrom tiez neprechadza."""
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
    """Povie text vlastnou SAPI instanciou - pouzitelne z viacerych vlakien."""
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
    """Nahravanie z mikrofonu cez MCI waveaudio."""

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
        # Ulozime najprv do .part a hotovy subor az potom atomicky presunieme
        # na cielove miesto. Keby MCI save zlyhal v polovici (plny disk, chyba
        # ovladaca), predosla dobra nahravka na `path` ostane nedotknuta - nie
        # prepisana polovicnou, neprehratelnou (B3). Stara logika mazala `path`
        # este pred ulozenim, takze zlyhanie znamenalo stratu oboch.
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
            os.replace(tmp, path)
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
# Edge Natural TTS s predgenerovanou cache
# --------------------------------------------------------------------------

def edge_rate_str(rate):
    """Slider -10..10 -> retazec pre edge-tts, napr. '-20%'."""
    pct = int(rate) * 5
    return f"{pct:+d}%"


class EdgeTTSCache:
    """Generuje MP3 hlasky cez edge-tts a drzi ich v audio/tts_cache/.

    Cielom je, aby sa pocas hrania nevolala siet: vsetky hlasky su hotove
    dopredu a trigger uz len prehra lokalny subor. Ked niektora chyba,
    `app._speak_text` pocas pocuvania na siet nejde a odlozi ju na potom.
    """

    def __init__(self, log):
        self.log = log
        self._lock = threading.Lock()

    # ---- cesty ----

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

    # ---- generovanie ----

    def ensure(self, text, voice, rate, abort=None):
        """Vygeneruje hlasku, ak este nie je v cache. Vracia cestu alebo None.

        Blokuje - volaj vzdy z pomocneho vlakna, nikdy z GUI ani z listenera.

        `abort` (volitelne, bez argumentov) sa pyta tesne pred odoslanim na
        Microsoft - uz PO ziskani zamku. Vlakno pripravy moze na zamku cakat,
        kym ine vlakno dokonci svoju hlasku; ak sa medzitym zaplo pocuvanie
        (alebo pripravu nahradila novsia), `abort()` vrati True a nova
        poziadavka sa nezacne - vrati sa None. Hotovy subor z cache sa vrati
        aj tak (na siet nejde).
        """
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
                os.replace(tmp, path)
            except Exception as exc:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                self.log(tr("log.edge_gen_failed", text=text, err=exc))
                return None
        return path

    # ---- zoznam hlasov ----

    @staticmethod
    def list_voices():
        """Vyber Edge hlasov pre combobox - pevny zoznam z
        `EDGE_FALLBACK_VOICES`, BEZ SIETE.

        Predtym sa tu z Microsoftu tahal zivy katalog (pri kazdom starte,
        kym bol zvoleny Edge - a ten je predvoleny), len aby sa orezal
        presne na tento rucne vybrany zoznam a doplnilo prelozene slovo
        pre pohlavie. Rod je teraz priamo v zozname a popis sa sklada cez
        tr(), takze na Microsoft ide appka az pri priprave samotnych hlasok
        (`ensure`). Vracia [(short_name, popis)] v poradi zoznamu."""
        rod = {"f": tr("voice.female"), "m": tr("voice.male")}
        items = []
        for short, meno, pohlavie in EDGE_FALLBACK_VOICES:
            locale = "-".join(short.split("-")[:2])
            premium = any(h in short for h in EDGE_PREMIUM_HINT)
            suffix = f", {tr('voice.most_natural')}" if premium else ""
            items.append((short, f"{locale} · {meno} ({rod.get(pohlavie, '')}{suffix})"))
        return items

    # ---- udrzba ----

    @staticmethod
    def prune(keep_paths):
        """Zmaze z cache subory, ktore uz ziadny slot nepouziva."""
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
# Zvukove vlakno: TTS (SAPI5) + prehravanie suborov v jednom fronte
# --------------------------------------------------------------------------

class SpeechWorker(threading.Thread):
    """Jedno vlakno pre vsetok zvuk. GUI ani listenery sa nikdy neblokuju.

    TTS ide primarne priamo cez SAPI.SpVoice (comtypes) - je to
    spolahlivejsie ako opakovane pyttsx3 runAndWait(), ktore po prvom
    prehrani casto zamrzne a dalsie hlasky sa uz neozvu.
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

    # ---- verejne API (volatelne z lubovolneho vlakna) ----

    def speak(self, text, voice_id=None):
        if text and text.strip():
            self.queue.put(("say", (text, voice_id)))

    def play(self, path, volume=None):
        """`volume` prebije aktualnu globalnu hlasitost pre toto jedno
        prehratie - pouzivane na oddelene SFX/TTS hlasitosti."""
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

    # ---- interne ----

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
        # Vzdy cerstvy engine - zdielany engine v pyttsx3 po prvom
        # runAndWait() casto prestane hovorit.
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
        # ŠTART V try = jedna COM chyba (odinštalovaný/poškodený SAPI hlas,
        # zlyhaný init, uložený hlas, ktorý už neexistuje) zabila celé
        # zvukové vlákno PRED slučkou - a od tej chvíle žiadny TTS, žiadny
        # SFX, žiadna hláška, bez jediného slova (bug B14). Keď štart zlyhá,
        # spadneme na pyttsx3 (`_voice = None`) a vlákno beží ďalej, takže
        # appka aspoň hovorí a prehráva zvuky.
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
    """Rozhoduje, ci zvuky idu za sebou (fronta) alebo znejú cez seba.

    SFX (zvukove efekty) a TTS (hlas) maju oddelenu hlasitost - `sfx_volume`
    a `tts_volume` - obe odvodene z globalneho posuvnika Hlasitost a
    posuvnika Vyvazenie SFX/Hlas (pozri DandurfApp._recompute_volumes)."""

    def __init__(self, worker, log):
        self.worker = worker
        self.log = log
        self.overlap = False
        self.rate = 0
        self.sfx_volume = 100
        self.tts_volume = 100

    def play(self, path, volume=None):
        """Prehra SFX subor. `volume` (ak je zadany) prebije `sfx_volume` -
        pouzivane, ked ide v skutocnosti o TTS obsah (pozri `play_tts`)."""
        vol = self.sfx_volume if volume is None else volume
        if self.overlap:
            threading.Thread(target=self._play_now, args=(path, vol),
                             daemon=True).start()
        else:
            self.worker.play(path, vol)

    def play_tts(self, path):
        """Prehra predgenerovanu Edge TTS hlasku (.mp3) - vzdy hlasitostou TTS."""
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
