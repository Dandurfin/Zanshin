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
    do %APPDATA%\\Zanshin. Pri spusteni zo zdrojakov ostava vsetko
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
    predoslych nazvov appky (LEGACY_APP_NAMES) do %APPDATA%\\Zanshin.

    LEN PRI PRVOM STARTE na novom mieste (v cieli este nie su nastavenia).
    Kopia od .exe sa predtym spustala pri KAZDOM starte a doplnala, co v
    cieli chyba - takze "Zmazat historiu" nevydrzala: pri dalsom spusteni
    sa stara historia spoza .exe vratila. Stare priecinky sa nepresuvaju
    (copy2/copytree), preto ich `legacy_data_dirs` vie najst a mazanie
    historie (`data_io.delete_plan`) aj odinstalovanie ich zmazu tiez."""
    if not getattr(sys, "frozen", False):
        return
    try:
        if os.path.exists(os.path.join(target, "dandurf_settings.json")):
            return
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


def legacy_data_dirs(target=None):
    """Stare priecinky s datami, z ktorych mohla kopirovat migracia.

    %APPDATA%\\Zanshin DojoSync, %APPDATA%\\Dandurf a priecinok vedla .exe
    (stara prenosna verzia) - len tie, co existuju, a nikdy nie samotny
    `target`. Migracia ich len KOPIROVALA, takze v nich ostala kopia
    historie tepu; mazanie historie ich preto musi zmazat tiez, inak by
    "Zmazat" nechalo druhu kopiu. Pri behu zo zdrojakov sa nemigruje nic,
    takze nie je co vracat.
    """
    if not getattr(sys, "frozen", False):
        return []
    target = os.path.normcase(os.path.abspath(target or data_dir()))
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    kandidati = [os.path.join(base, meno) for meno in LEGACY_APP_NAMES]
    kandidati.append(os.path.dirname(sys.executable))
    von = []
    for cesta in kandidati:
        norm = os.path.normcase(os.path.abspath(cesta))
        if (os.path.isdir(cesta) and norm != target
                and norm not in (os.path.normcase(os.path.abspath(x)) for x in von)):
            von.append(cesta)
    return von


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
