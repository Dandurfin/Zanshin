"""Spolocne cesty k datam appky - zdielane medzi main.py a sfx_assets.py."""

import glob
import os
import shutil
import sys

APP_NAME = "Zanshin"
IS_WINDOWS = sys.platform == "win32"

# Predchadzajuce nazvy appky - pouziva sa len na migraciu existujucich
# nastaveni/nahravok pod novy nazov priecinka v %APPDATA%.
#
# "Zanshin DojoSync" pribudlo pri premenovani na holy "Zanshin": prívlastok
# "DojoSync" nic nehovoril (synchronizuje co s cim?) a zrozumitelnost nesie
# veta vedla mena, nie meno samo. Bez tohto zaznamu by nainstalovanej appke
# zmizli data - `data_dir()` ich hlada pod APP_NAME.
LEGACY_APP_NAMES = ["Zanshin DojoSync", "Dandurf"]


def data_dir():
    """Kam zapisujeme nastavenia, nahravky, cache hlasok a SFX kniznicu.

    Nainstalovana (zamrazena) appka moze sediet v Program Files, kam Windows
    beznemu pouzivatelovi zapisat nedovoli - vsetko pouzivatelske preto ide
    do %APPDATA%\\Zanshin DojoSync. Pri spusteni zo zdrojakov ostava vsetko
    vedla main.py, aby sa vyvoj nemiesal s ostrymi datami.
    """
    if getattr(sys, "frozen", False):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, APP_NAME)
    return os.path.dirname(os.path.abspath(__file__))


# Datove subory prenasane pri premenovani priecinka appky. NIE LEN nastavenia:
# aj CELA HISTORIA TEPU - relacie (zakladne, krivky), okna, z ktorych algoritmus
# rata prah, dennik udalosti a insighty. Bez nich by sa pri migracii dlhodoba
# data ticho stratili a algoritmus by zacinal od nuly (prah/zakladna prec).
_MIGROVANE_DATA = ["dandurf_settings.json", "hr_sessions.json", "hr_windows.json",
                   "hr_events.jsonl", "hr_insights.json"]


def _copy_data_dir(old, target):
    os.makedirs(target, exist_ok=True)
    # Kazdy datovy subor aj s jeho .bak / rotaciami / .corrupt-* surodencami;
    # kopirujeme len ked v cieli este nie je (rovnaka poistka ako predtym).
    subory = set()
    for meno in _MIGROVANE_DATA:
        for sib in glob.glob(os.path.join(old, meno + "*")):
            subory.add(os.path.basename(sib))
    for meno in sorted(subory):
        src = os.path.join(old, meno)
        dst = os.path.join(target, meno)
        if os.path.isfile(src) and not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
            except OSError:
                pass
    # audio/ = vlastne SFX + nahravky hlasu (nie su regenerovatelne)
    old_audio = os.path.join(old, "audio")
    new_audio = os.path.join(target, "audio")
    if os.path.isdir(old_audio) and not os.path.isdir(new_audio):
        shutil.copytree(old_audio, new_audio)


def migrate_legacy_data(target):
    """Prenesie data od starsej prenosnej verzie (vedla .exe) a od
    predoslej znacky appky (Dandurf) do noveho %APPDATA%\\Zanshin DojoSync."""
    if not getattr(sys, "frozen", False):
        return
    try:
        if not os.path.isdir(target):
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
            for legacy_name in LEGACY_APP_NAMES:
                legacy_dir = os.path.join(base, legacy_name)
                if os.path.isdir(legacy_dir):
                    _copy_data_dir(legacy_dir, target)
                    break
        old = os.path.dirname(sys.executable)
        if os.path.normcase(old) != os.path.normcase(target):
            _copy_data_dir(old, target)
    except Exception:
        pass


DATA_DIR = data_dir()
migrate_legacy_data(DATA_DIR)

SETTINGS_PATH = os.path.join(DATA_DIR, "dandurf_settings.json")
AUDIO_DIR = os.path.join(DATA_DIR, "audio")
TTS_CACHE_DIR = os.path.join(AUDIO_DIR, "tts_cache")
SOUNDS_DIR = os.path.join(DATA_DIR, "assets", "sounds")


def images_dir():
    """Obrazky dodavane s appkou (QR na appku do hodiniek a pod.).

    Rovnaka logika ako `guides_dir()` - su to sucasti instalacie, nie
    pouzivatelske data, takze sa hladaju vedla zdrojaku / vo vnutri
    zabaleneho .exe, nie v %APPDATA%. Oba `.spec` subory balia cely
    priecinok `assets`, takze netreba nic dopisovat do buildu.
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "assets", "images")


def guides_dir():
    """Priecinok s (docasnymi) ilustraciami pre panel 'Sprievodca'.

    Su to suceasti appky dodavane s instalaciou (nie pouzivatelske data),
    preto sa hladaju vedla zdrojaku / vo vnutri zabaleneho .exe, nie v
    %APPDATA%. Umiestni sem PNG s nazvom podla id karty (napr.
    grounding.png), aby appka pouzila realnu ilustraciu namiesto
    docasneho vektoroveho nacrtu.
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "assets", "guides")


def resolve_audio_path(path):
    """Po presune dat drzia stare nastavenia absolutne cesty k .wav suborom.

    Ak subor na povodnom mieste uz nie je, skusime rovnaky nazov v novom
    priecinku audio/ - inak by slot po instalacii stratil svoju nahravku.
    """
    if not path or os.path.exists(path):
        return path
    candidate = os.path.join(AUDIO_DIR, os.path.basename(path))
    return candidate if os.path.exists(candidate) else path
