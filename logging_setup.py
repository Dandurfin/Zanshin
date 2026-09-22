"""Centralizovane logovanie do suboru - riesi bod 1 a 3 z code review:

  1. Ziadny top-level crash handler - main.py teraz zapisuje kazdu
     neosetrenu vynimku (aj z mainloop-u) do crash.log v %APPDATA%, takze
     alfa testeri maju co poslat spat, ked appka spadne/zamrzne.
  2. Prilis siroke `except Exception: pass` - ticho prehltnute chyby
     (ukladanie nastaveni, nacitanie hlasov, tray ikona...) teraz idu
     aj do rotujuceho app.log, nie len do UI logu, ktory sa strati po
     restarte appky.

Pouzitie v ostatnych moduloch:
    from logging_setup import get_logger
    log = get_logger(__name__)
    ...
    except Exception:
        log.exception("popis co sa nepodarilo")   # zapise aj traceback

Log subory:
  %APPDATA%\\Zanshin\\logs\\app.log     - rotujuci (5x 1 MB), bezna prevadzka
  %APPDATA%\\Zanshin\\logs\\crash.log   - neosetrene vynimky (append, nikdy sa nemaze)
"""

import logging
import logging.handlers
import os
import sys
import traceback
from datetime import datetime

from paths import DATA_DIR

LOG_DIR = os.path.join(DATA_DIR, "logs")
APP_LOG_PATH = os.path.join(LOG_DIR, "app.log")
CRASH_LOG_PATH = os.path.join(LOG_DIR, "crash.log")

_configured = False


def _ensure_log_dir():
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        return True
    except Exception:
        return False


def _configure_root_logger():
    global _configured
    if _configured:
        return
    _configured = True
    root_logger = logging.getLogger("zanshin")
    root_logger.setLevel(logging.INFO)
    if not _ensure_log_dir():
        # Ak sa ani nepodari vytvorit priecinok (napr. bez prav), aspon
        # necháme logger fungovat do stderr - nikdy nesmie kvoli logovaniu
        # spadnut samotna appka.
        handler = logging.StreamHandler(sys.stderr)
    else:
        try:
            handler = logging.handlers.RotatingFileHandler(
                APP_LOG_PATH, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        except Exception:
            handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
    root_logger.addHandler(handler)


def get_logger(name):
    """Vrati logger `zanshin.<name>`, zapisujuci do app.log. Bezpecne volat
    z ktorehokolvek modulu (setup sa vykona len raz, staticky)."""
    _configure_root_logger()
    return logging.getLogger(f"zanshin.{name}")


def log_crash(exc_type, exc_value, exc_tb):
    """Zapise neosetrenu vynimku do crash.log (append, nikdy sa nemaze -
    na rozdiel od rotujuceho app.log). Volat zo sys.excepthook alebo z
    try/except okolo root.mainloop()."""
    _ensure_log_dir()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    entry = f"\n==== {stamp} ====\n{text}"
    try:
        with open(CRASH_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        # Ak sa ani crash log nepodari zapisat, aspon to vypiseme do
        # konzoly - nikdy nesmieme dalsou vynimkou zakryt povodnu.
        print(entry, file=sys.stderr)
    try:
        get_logger("crash").critical("Neosetrena vynimka - detaily v crash.log:\n%s", text)
    except Exception:
        pass
