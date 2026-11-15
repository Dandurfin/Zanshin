"""Spolocne cesty k datam appky - zdielane medzi main.py a sfx_assets.py.

Aj `nahrad_subor`: posledny krok atomickeho zapisu (.tmp -> ciel), ktory
prezije kratky zamok suboru vo Windows. Je tu, lebo tento modul nenatahuje
ziadny iny modul appky - importovat ho moze kazdy bez kruhoveho importu.
"""

import errno
import glob
import logging
import os
import shutil
import sys
import time

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


# AppId instalacky z Dandurf.iss (tam je zapisany so zdvojenou zatvorkou
# `{{...}`, co je v Inno Setup len escapovanie). Inno podla neho zaklada
# kluc odinstalovania `<AppId>_is1`.
INSTALLER_APP_ID = "{30295CDB-462B-4151-B225-582E82027A33}"
_UNINSTALL_KEY = ("Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\"
                  + INSTALLER_APP_ID + "_is1")


def _hodnota_registra(winreg_mod, kluc, meno):
    try:
        hodnota, _typ = winreg_mod.QueryValueEx(kluc, meno)
    except OSError:
        return None
    return str(hodnota).strip() if hodnota else None


def stara_instalacia(winreg_mod=None, exe=None):
    """Je na PC nainstalovany Zanshin z instalacky 0.2? Alebo None.

    PRECO: 0.2 sa instalovala instalackou (Dandurf.iss) a jej odinstalator
    sa pyta "Ponechat nastavenia...?". Pri Nie zmaze %APPDATA%\\Zanshin -
    a ten isty priecinok pouziva aj verzia zo ZIP-u, takze by zmizla aj jej
    historia. Vracia {"location", "version"} z kluca odinstalovania.

    Instalacka bola bez admin prav (HKCU), HKLM sa skusa pre istotu v oboch
    pohladoch registra (64/32 bit). Ked bezi prave ta nainstalovana appka
    (exe lezi v jej priecinku), nie je pred cim varovat. Chybajuci winreg
    alebo kluc nie je chyba - vrati None.
    """
    if winreg_mod is None:
        try:
            import winreg as winreg_mod
        except ImportError:
            return None
    exe = os.path.normcase(os.path.abspath(exe or sys.executable))
    citanie = getattr(winreg_mod, "KEY_READ", 0x20019)
    pokusy = (
        (getattr(winreg_mod, "HKEY_CURRENT_USER", None), 0),
        (getattr(winreg_mod, "HKEY_LOCAL_MACHINE", None),
         getattr(winreg_mod, "KEY_WOW64_64KEY", 0x0100)),
        (getattr(winreg_mod, "HKEY_LOCAL_MACHINE", None),
         getattr(winreg_mod, "KEY_WOW64_32KEY", 0x0200)),
    )
    for koren, pohlad in pokusy:
        if koren is None:
            continue
        try:
            with winreg_mod.OpenKey(koren, _UNINSTALL_KEY, 0, citanie | pohlad) as kluc:
                miesto = (_hodnota_registra(winreg_mod, kluc, "InstallLocation")
                          or _hodnota_registra(winreg_mod, kluc, "Inno Setup: App Path"))
                verzia = _hodnota_registra(winreg_mod, kluc, "DisplayVersion")
        except Exception:
            # OSError = kluc nie je; cokolvek ine (pokazeny register) tiez
            # nesmie zhodit start appky.
            continue
        if miesto:
            priecinok = os.path.normcase(os.path.abspath(miesto)).rstrip("\\/")
            if exe == priecinok or exe.startswith(priecinok + os.sep):
                return None
        return {"location": miesto, "version": verzia}
    return None


def resolve_audio_path(path):
    """Po presune dat drzia stare nastavenia absolutne cesty k .wav suborom.

    Ak subor na povodnom mieste uz nie je, skusime rovnaky nazov v novom
    priecinku audio/ - inak by slot po instalacii stratil svoju nahravku.
    """
    if not path or os.path.exists(path):
        return path
    candidate = os.path.join(AUDIO_DIR, os.path.basename(path))
    return candidate if os.path.exists(candidate) else path


# --------------------------------------------------------------------------
# Atomicky zapis, ktory prezije kratky zamok suboru vo Windows
# --------------------------------------------------------------------------
#
# PRECO: data sa zapisuju cez `.tmp` + `os.replace`. Hned po zapise si vsak
# subor na chvilu otvori Defender, indexovanie Windows Search alebo
# synchronizacia - bez FILE_SHARE_DELETE - a `os.replace` vtedy spadne na
# PermissionError: WinError 5, ked drzia ciel, WinError 32, ked drzia .tmp.
# V logu skusobnej kopie (0.2.2) presne takto padla zaloha nastaveni
# ("zalohu nastaveni sa nepodarilo zapisat", .bak.tmp -> .bak). Taky zamok
# trva milisekundy, preto staci par kratkych pokusov.
#
# Pauzy rastu a spolu davaju 0.31 s na jeden subor. Viac nie: `save_settings`
# bezi vo vlakne GUI (uklada sa pri kazdom posune slidera) a nahradza DVA
# subory (.bak aj nastavenia) - pri zamku oboch caka okno 0.62 s naraz.
NAHRADA_PAUZY_S = (0.01, 0.02, 0.04, 0.08, 0.16)
# Kody Windows pre docasne drzany subor: 5 pristup odmietnuty (ciel otvoreny
# bez FILE_SHARE_DELETE), 32 subor pouziva iny proces, 33 zamknuta cast.
_DOCASNY_ZAMOK_WIN = (5, 32, 33)
# Ciel, ktory nevydrzal ani posledny pokus, nedrzi kratky zamok (subor len na
# citanie, otvoreny v inom programe). Kym zapis donho pada dalej, skusa sa
# len raz, bez cakania - inak by pri tahani slidera kazde ulozenie zaseklo
# okno o 0.31-0.62 s (10 ulozeni = 3 az 6 s, namerane so skutocnym zamkom).
# Plne opakovanie plati zas po prvom uspechu alebo ked do ciela
# `NAHRADA_ODDYCH_S` nikto nezapisoval (dalsia relacia o hodinu caka znova).
NAHRADA_ODDYCH_S = 5.0
_zlyhane_ciele = {}         # normcase(abspath(ciel)) -> _hodiny() zlyhania
_hodiny = time.monotonic    # vlastny odkaz: testy nahradzaju `paths.time`

_log = logging.getLogger("zanshin.paths")


def _je_docasny_zamok(exc):
    """Ma zmysel `os.replace` skusit znova? Len pri PermissionError s kodom
    drzaneho suboru. Bez kodu Windows (iny system, umela chyba v teste)
    rozhoduje errno - EACCES ano, EPERM (zakazana operacia) nie. Ina chyba
    (plny disk, chybajuci subor) sa opakovanim nezlepsi - vyhodi sa hned."""
    if not isinstance(exc, PermissionError):
        return False
    winerror = getattr(exc, "winerror", None)
    if winerror is not None:
        return winerror in _DOCASNY_ZAMOK_WIN
    return exc.errno in (None, errno.EACCES)


def _zmaz_potichu(cesta):
    try:
        os.remove(cesta)
    except OSError:
        pass


def nahrad_subor(zdroj, ciel, uprac_zdroj=False):
    """`os.replace(zdroj, ciel)`, ktory prezije kratky zamok suboru vo Windows.

    Pri docasnom zamku (`_je_docasny_zamok`) skusa znova po pauzach
    `NAHRADA_PAUZY_S`. Ked nevyjde ani posledny pokus, vyhodi POSLEDNU chybu,
    takze volajuci ju osetri rovnako ako predtym chybu holeho `os.replace`.
    Ina chyba sa vyhodi hned, bez cakania. Ciel, ktory prave takto nevydrzal,
    sa skusa len raz, kym pada dalej (`NAHRADA_ODDYCH_S`).

    `uprac_zdroj=True`: pri neuspechu zmaze `zdroj` (vlastny .tmp volajuceho),
    nech vedla dat neostane zabudnuty docasny subor; zlyhanie mazania sa
    prehltne. NIKDY nie pri odkladani pokazeneho suboru bokom - tam je
    `zdroj` jedina kopia dat.
    """
    try:
        _nahrad_s_pokusmi(zdroj, ciel)
    except BaseException:
        if uprac_zdroj:
            _zmaz_potichu(zdroj)
        raise


def _zapamataj_zlyhanie(kluc):
    teraz = _hodiny()
    # stare zaznamy prec - slovnik ostane maly aj pri mnohych cieloch
    for k, kedy in list(_zlyhane_ciele.items()):
        if teraz - kedy >= NAHRADA_ODDYCH_S:
            _zlyhane_ciele.pop(k, None)
    _zlyhane_ciele[kluc] = teraz


def _nahrad_s_pokusmi(zdroj, ciel):
    # Do logu len meno suboru a kod chyby, nie text vynimky: v nom je cela
    # cesta a cesta v %APPDATA% nesie meno uctu.
    meno = os.path.basename(ciel)
    kluc = os.path.normcase(os.path.abspath(ciel))
    zlyhal = _zlyhane_ciele.get(kluc)
    bez_cakania = zlyhal is not None and _hodiny() - zlyhal < NAHRADA_ODDYCH_S
    pauzy = [] if bez_cakania else list(NAHRADA_PAUZY_S)
    pokus = 1
    while True:
        try:
            os.replace(zdroj, ciel)
        except OSError as exc:
            zamok = _je_docasny_zamok(exc)
            if pauzy and zamok:
                time.sleep(pauzy.pop(0))
                pokus += 1
                continue
            if zamok:
                # aj pri jedinom pokuse bez cakania: kym pada, necaka sa
                _zapamataj_zlyhanie(kluc)
            if pokus > 1:
                _log.warning("nahrad_subor: %s sa nepodarilo nahradit ani na "
                             "%d. pokus (WinError %s, errno %s) - dalsie zapisy "
                             "donho skusaju len raz, kym padaju", meno, pokus,
                             getattr(exc, "winerror", None), exc.errno)
            raise
        _zlyhane_ciele.pop(kluc, None)
        if pokus > 1:
            _log.warning("nahrad_subor: %s nahradeny az na %d. pokus (subor "
                         "na chvilu drzal iny proces)", meno, pokus)
        return
