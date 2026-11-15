"""Auto-Profile Engine - detects a running game by its process name and,
based on that, switches the profile and turns listening on/off by itself.
Purely read-only: it only periodically reads the list of running processes
(psutil), launches nothing, closes nothing and interferes with nothing.

Runs ONLY with the "auto_profile_enabled" switch on - app.py stops it when
it is switched off, so then the process list is not read at all.
"""

import threading
import time

try:
    import psutil
    PSUTIL_AVAILABLE = True
except Exception:
    psutil = None
    PSUTIL_AVAILABLE = False


# "bootstrapper.exe" is no longer here: it is a generic launcher name under
# which other programs run too, so the app could start listening by itself
# and create a "Call of Duty" profile for something completely different.
GAME_PROCESS_MAP = {
    "cod.exe": "Call of Duty",
    "r5apex.exe": "Apex Legends",
    "cs2.exe": "CS2",
    "valorant-win64-shipping.exe": "Valorant",
}


def known_games():
    """Names of the games the auto-profile knows - for texts in the app, so
    that the sentence about starting with a game names exactly the games the
    map really contains."""
    return sorted(set(GAME_PROCESS_MAP.values()), key=str.lower)


class GameProcessWatcher(threading.Thread):
    """Every `interval` seconds (3-5s) checks the running processes against
    `GAME_PROCESS_MAP`. On the first detection of a known process it calls
    `on_game_found(profile_name)`; when all known processes of that game
    disappear, it calls `on_game_gone()`. Runs only if `psutil` is
    available."""

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
