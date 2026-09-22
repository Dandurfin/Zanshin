"""Auto-Profile Engine - rozpozna beziacu hru podla nazvu procesu a podla
toho sama prepne profil a zapne/vypne odpocuvanie. Cisto read-only:
len periodicky vycitava zoznam beziacich procesov (psutil), nic
nespusta, nezatvara ani do niceho nezasahuje.
"""

import threading
import time

try:
    import psutil
    PSUTIL_AVAILABLE = True
except Exception:
    psutil = None
    PSUTIL_AVAILABLE = False


GAME_PROCESS_MAP = {
    "cod.exe": "Call of Duty",
    "bootstrapper.exe": "Call of Duty",
    "r5apex.exe": "Apex Legends",
    "cs2.exe": "CS2",
    "valorant-win64-shipping.exe": "Valorant",
}


class GameProcessWatcher(threading.Thread):
    """Kazdych `interval` sekund (3-5s) skontroluje beziace procesy oproti
    `GAME_PROCESS_MAP`. Pri prvom zachyteni znameho procesu zavola
    `on_game_found(profile_name)`; ked vsetky zname procesy danej hry
    zmiznu, zavola `on_game_gone()`. Bezi len ak je `psutil` dostupny."""

    def __init__(self, on_game_found, on_game_gone, interval=4.0):
        super().__init__(daemon=True)
        self.on_game_found = on_game_found
        self.on_game_gone = on_game_gone
        self.interval = interval
        self._running = True
        self._current = None

    def stop(self):
        self._running = False

    def run(self):
        if not PSUTIL_AVAILABLE:
            return
        while self._running:
            try:
                self._scan()
            except Exception:
                pass
            for _ in range(int(self.interval * 10)):
                if not self._running:
                    return
                time.sleep(0.1)

    def _scan(self):
        found = None
        for proc in psutil.process_iter(["name"]):
            try:
                name = (proc.info.get("name") or "").lower()
            except Exception:
                continue
            profile_name = GAME_PROCESS_MAP.get(name)
            if profile_name:
                found = profile_name
                break
        if found != self._current:
            self._current = found
            if found:
                self.on_game_found(found)
            else:
                self.on_game_gone()
