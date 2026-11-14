"""Zanshin (predtym Zanshin DojoSync a Dandurf) - mindfulness/biofeedback asistent
pre hranie hier.

Toto je len vstupny bod - overi zavislosti a spusti hlavnu appku
(DandurfApp v app.py). Cela architektura je rozdelena na moduly:

  paths.py           - cesty k datam (%APPDATA%), migracia zo starsich verzii
  theme.py           - farebne tokeny vzhladov Sumi (hra) / Aizome (praca)
  i18n.py            - preklady rozhrania (11 jazykov; cs/bg v i18n_cs_bg.py)
  settings_model.py  - datovy model slotov/nastaveni (predvolene hodnoty,
                        normalizacia, popisky)
  sfx_assets.py       - zabudovana SFX kniznica (syntéza aj stiahnutie)
  audio_engine.py     - TTS (Edge Natural + SAPI5) a prehravanie SFX/nahravok
  gamepad.py          - ovladace cez pygame/SDL2; UZ NIE SPUSTAC, len druhy
                        zdroj informacie o tom, ci je hrac aktivny
  game_profiles.py    - Auto-Profile Engine (rozpoznanie beziacej hry)
  activity.py         - ci hrac prave nieco robi (GetLastInputInfo, ZIADNY
                        hook) a z coho hra (ovladac / klavesnica)
  trigger.py          - stavovy automat hlasky: natiahnutie po 90 s zataze,
                        odklad na prestavku, tiche kontrolne rameno
  measure.py          - meracie okna okolo hlasky a ich platnost
  data_io.py          - export/import/mazanie dat (prisny parser, bez pickle)
  overlay.py          - in-game somaticke vizualy (click-through okna)
  guide_content.py,
  guide_panel.py       - panel "Sprievodca / Čo je za tým"
  ui_dialogs.py        - dialogy a karty hlavneho okna (vratane Onboardingu)
  app.py              - DandurfApp: hlavne okno, prepojenie vsetkeho
  app_audio.py        - AudioMixin (cast DandurfApp): SFX kniznica, hlasitost,
                        hlasy, priprava Edge hlasok, prehratie slotu
  app_controls.py     - ControlsMixin (cast DandurfApp): paleta prikazov,
                        "teraz nie", dennik, ovladac a rucna hlaska (Test)
  app_cues.py         - CuesMixin (cast DandurfApp): stav spustaca hlasky,
                        stupen rebrika pre relaciu, styl hlasky
  app_data.py         - DataMixin (cast DandurfApp): export/import/mazanie
                        dat, ulozenie relacie, zdielanie profilov kodom
  app_history.py      - HistoryMixin (cast DandurfApp): stranka Historia
                        (trend, tabulka, detail relacie, export do CSV) a
                        analyza historie na pozadi
  app_hud.py          - HudMixin (cast DandurfApp): HUD v hre a riadok ikon,
                        jazyk hry, monitor, kontrolka tepu, in-game vizualy
  app_prefs.py        - PrefsMixin (cast DandurfApp): prepinanie jazyka,
                        sveta a temy, nacitanie/ulozenie nastaveni
  app_profiles.py     - ProfilesMixin (cast DandurfApp): sloty, profily hier
                        a auto-profil (rozpoznanie beziacej hry)
  app_session.py      - SessionMixin (cast DandurfApp): senzor tepu, prijem
                        tepu a stavu spojenia, otvorenie meracej relacie
  app_spolocne.py     - mena spolocne pre app.py a jej mixiny (app_log,
                        nazvy jazykov, skratka "Teraz nie", ImageTk)
  app_today.py        - TodayMixin (cast DandurfApp): stred (kreslenie) a
                        zivy blok stranky Dnes, dorucenie hlasky,
                        "Moje statistiky"

Dva TTS motory:
  * "edge"  - Microsoft Edge Natural (neuronove hlasy). Hlasky sa
              generuju DOPREDU do cache v audio/tts_cache/ a ked sa hlaska
              doruci, uz sa len prehra hotovy MP3 subor - ziadna sietova
              komunikacia ani latencia pocas hrania.
  * "sapi"  - klasicke offline Windows SAPI5 hlasy.

Rozhranie ma dva vzhlady a idu so svetom: Sumi pre hru, Aizome pre pracu
(kluce `zen` / `modern`, viz `theme.WORLD_THEME`). Prepnutie sveta ich
prefarbi kedykolvek bez restartu - farebne tokeny su v theme.py. Zabudovana SFX
kniznica (stiahnuta alebo lokalne vygenerovana) je v sfx_assets.py.
"""

import os
import sys
import threading
import tkinter as tk
import types
from tkinter import messagebox

# DPI-awareness MUSI byt nastavena EST PRED importom customtkinter
# (ten si pri svojom importe nastavuje vlastny, slabsi rezim) a
# pred vznikom prveho Tk okna - potom uz Windows rezim procesu
# nemeni. Bez toho appka na 4K monitore so skalovanim dostava
# klamlive rozmery obrazovky a Windows ju navyse rozmaze
# bitmapovym zvacsenim. Viz display.py.
import display
display.enable_dpi_awareness()

try:
    import customtkinter as ctk
except Exception as exc:  # pragma: no cover - sanity guard pre chybajucu zavislost
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Zanshin",
        "Chýba knižnica 'customtkinter', bez ktorej appka nevie zobraziť "
        "rozhranie. / Missing the 'customtkinter' library - the app can't "
        f"display its interface without it.\n\nChyba / Error: {exc}\n\n"
        "Nainštaluj ju príkazom / Install it with:\n"
        "    pip install customtkinter",
    )
    sys.exit(1)


def _install_crash_hooks():
    """Nastavi zapis neosetrenych vynimok do crash.log (hlavne vlakno aj
    vlastne vlakna) a vrati `log_crash` pre Tk callbacky.

    logging_setup je lahky (len stdlib + paths), takze ho mozeme natiahnut
    skor nez app bez spomalenia startu. Import paths pri tom urci DATA_DIR
    (v builde %APPDATA%\\Zanshin) a spravi migraciu starych dat - presne to,
    co by inak spravil az import app. Priecinok logs/ vznikne az pri prvom
    zapise do logu, teda az PO migracii - ta sa riadi tym, ci cielovy
    priecinok uz existuje, takze logs/ ju nesmie predbehnut.
    """
    from logging_setup import log_crash

    # Vynimky MIMO Tk na HLAVNOM vlakne (napr. import app, este pred
    # vytvorenim root-u) zachyti sys.excepthook.
    def _sys_excepthook(exc_type, exc_value, exc_tb):
        log_crash(exc_type, exc_value, exc_tb)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _sys_excepthook

    # Vynimky vo VLASTNYCH VLAKNACH. Od Pythonu 3.8 uz NEidu cez
    # sys.excepthook (comment vyssie to kedysi tvrdil - bola to nepravda),
    # ale sem. Appka ma ~20 vlakien (siet, audio, TTS, analyza); bez tohto
    # by pad ktorehokolvek z nich nezanechal v crash.log ani bajt a v
    # zabalenom builde (console=False) ide stderr nikam - chyba by zmizla
    # uplne bez stopy.
    def _thread_excepthook(args):
        if args.exc_type is SystemExit:
            return
        log_crash(args.exc_type, args.exc_value, args.exc_traceback)

    threading.excepthook = _thread_excepthook
    return log_crash


# --- JEDNA KOPIA APPKY (0.2.2) ---------------------------------------------
#
# × appku len schova do listy a na Windowse 11 je ikona v liste predvolene
# skryta pod sipkou ^. Kto ju tam nenasiel, spustil Zanshin.exe znova - a
# druha kopia zlyhala na skratke Ctrl+Alt+Z ("drzi ju ina appka") aj na porte
# tepu, ktory drzi prva. Do 0.2.2 navyse po ~24 s ULOZILA vypnuty senzor do
# spolocnych nastaveni, takze tep sa neprijimal ani pri dalsom starte. Preto
# pomenovany mutex: druha kopia len povie prvej "ukaz okno" (pomenovana
# udalost) a ticho skonci. "Local\\" = v ramci prihlasenia jedneho hraca.
_MUTEX_MENO = "Local\\Zanshin-single"
_UDALOST_MENO = "Local\\Zanshin-show"
# Obchadzka pre vyvoj a testy, ktore naozaj potrebuju dve kopie naraz. Pod
# pytestom sa straz preskakuje sama (`PYTEST_CURRENT_TEST` dedia aj procesy,
# ktore test spusti) - inak by test so spustenym main.py zlyhal len preto,
# ze na tom istom PC prave bezi Zanshin.
POVOL_VIAC_KOPII = "ZANSHIN_ALLOW_MULTI"
_ERROR_ACCESS_DENIED = 5
_ERROR_ALREADY_EXISTS = 183
_EVENT_MODIFY_STATE = 0x0002
_WAIT_OBJECT_0 = 0x0
_WAIT_TIMEOUT = 0x102
_ASFW_ANY = 0xFFFFFFFF
_MB_ICONINFORMATION = 0x40
_MB_SETFOREGROUND = 0x10000
# Kym proces zije, drzi sa tu handle mutexu (a udalosti). Handle v ctypes je
# len cislo, ktore nic samo nezatvori - mutex zanikne az s procesom, presne
# vtedy, ked sa druha kopia uz smie spustit.
_JEDNA_KOPIA = None
# Len ked by zlyhal aj import i18n - normalne ide text z `tray.already_running`.
_UZ_BEZI_ZALOHA = (
    "Zanshin is already running — you'll find it in the tray by the clock "
    "(if you don't see the icon, click the ^ arrow).\n\n"
    "Zanshin už beží — nájdeš ho v lište pri hodinách (ak ikonu nevidíš, "
    "klikni na šípku ^).")


def _win32():
    """kernel32 a user32 s presnymi typmi - vlastne WinDLL, nie
    `ctypes.windll`, aby `argtypes` nezmenili volania v inych moduloch."""
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    u32 = ctypes.WinDLL("user32", use_last_error=True)
    for fn, args, res in (
            (k32.CreateMutexW, (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR),
             wintypes.HANDLE),
            (k32.CreateEventW, (wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL,
                                wintypes.LPCWSTR), wintypes.HANDLE),
            (k32.OpenEventW, (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR),
             wintypes.HANDLE),
            (k32.SetEvent, (wintypes.HANDLE,), wintypes.BOOL),
            (k32.CloseHandle, (wintypes.HANDLE,), wintypes.BOOL),
            (k32.WaitForSingleObject, (wintypes.HANDLE, wintypes.DWORD),
             wintypes.DWORD),
            (u32.MessageBoxW, (wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
                               wintypes.UINT), ctypes.c_int),
            (u32.AllowSetForegroundWindow, (wintypes.DWORD,), wintypes.BOOL)):
        fn.argtypes, fn.restype = args, res
    return types.SimpleNamespace(k32=k32, u32=u32,
                                 posledna_chyba=ctypes.get_last_error)


def _straz_jednej_kopie(api=None, environ=None, platforma=None):
    """Prva kopia: vrati {api, mutex, udalost} - drzat do konca procesu.
    Uz bezi ina kopia: da jej znamenie "ukaz okno" a skonci (SystemExit 0).
    None: straz sa preskakuje (iny OS, obchadzka, chyba Windows API).

    Straz NIKDY nesmie zabranit startu - ked jej nieco zlyha, appka sa spusti
    ako do 0.2.2. Zle zachytena druha kopia je mensia skoda nez appka, ktora
    sa neda spustit vobec.
    """
    environ = os.environ if environ is None else environ
    platforma = sys.platform if platforma is None else platforma
    if environ.get(POVOL_VIAC_KOPII) == "1" or "PYTEST_CURRENT_TEST" in environ:
        return None
    if not platforma.startswith("win"):
        return None
    try:
        api = api or _win32()
        mutex = api.k32.CreateMutexW(None, False, _MUTEX_MENO)
        chyba = api.posledna_chyba()
    except Exception:
        return None
    # ACCESS_DENIED bez handle: mutex existuje, len ho vytvoril proces s
    # vyssimi pravami (Zanshin spusteny ako spravca). Tiez uz bezi.
    if chyba == _ERROR_ALREADY_EXISTS or (not mutex and chyba == _ERROR_ACCESS_DENIED):
        if not _daj_znamenie_prvej_kopii(api):
            _ukaz_uz_bezi(api)
        sys.exit(0)
    if not mutex:
        return None
    # Udalost hned za mutexom, este pred dlhym importom app: druha kopia
    # spustena pocas nacitania tak najde udalost a znamenie sa nestrati -
    # auto-reset udalost ostane nastavena, kym si ju vlakno prvej kopie
    # nevyzdvihne (`_cakaj_na_dalsi_start`).
    try:
        udalost = api.k32.CreateEventW(None, False, False, _UDALOST_MENO)
    except Exception:
        udalost = None
    return types.SimpleNamespace(api=api, mutex=mutex, udalost=udalost or None)


def _daj_znamenie_prvej_kopii(api):
    """Povie beziacej kopii "ukaz okno". True, ked sa znamenie podarilo."""
    try:
        # Do popredia smie okno dat len proces, ktory hrac prave spustil -
        # teda tento. Bez povolenia by okno prvej kopie len blikalo v liste
        # uloh za tym, co je prave navrchu.
        api.u32.AllowSetForegroundWindow(_ASFW_ANY)
    except Exception:
        pass
    try:
        handle = api.k32.OpenEventW(_EVENT_MODIFY_STATE, False, _UDALOST_MENO)
    except Exception:
        return False
    if not handle:
        return False
    try:
        return bool(api.k32.SetEvent(handle))
    except Exception:
        return False
    finally:
        try:
            api.k32.CloseHandle(handle)
        except Exception:
            pass


def _ulozeny_jazyk():
    """Jazyk z ulozenych nastaveni, None ked sa neda bezpecne precitat.

    Len `json` - appka sa tu este nenacitala a kvoli jednej vete sa ani
    nema. Pokazeny ci chybajuci subor znamena "nevieme", nie pad."""
    try:
        import json
        from paths import SETTINGS_PATH
        with open(SETTINGS_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        lang = data.get("lang") if isinstance(data, dict) else None
        return lang if isinstance(lang, str) else None
    except Exception:
        return None


def _text_uz_bezi(lang=None):
    """Veta pre okienko: v jazyku hraca, inak anglicky a slovensky."""
    try:
        import i18n
        if lang in i18n.LANGUAGES:
            return i18n.tr_lang(lang, "tray.already_running")
        return "%s\n\n%s" % (i18n.tr_lang(i18n.LANG_EN, "tray.already_running"),
                             i18n.tr_lang(i18n.LANG_SK, "tray.already_running"))
    except Exception:
        return _UZ_BEZI_ZALOHA


def _ukaz_uz_bezi(api):
    """Znamenie neprislo (prva kopia sa prave zatvara alebo bezi pod inymi
    pravami) - aspon povedat, kde appku hladat. Nativne okienko, nie Tk:
    druha kopia nema kvoli jednej vete nacitavat cele GUI."""
    try:
        api.u32.MessageBoxW(None, _text_uz_bezi(_ulozeny_jazyk()), "Zanshin",
                            _MB_ICONINFORMATION | _MB_SETFOREGROUND)
    except Exception:
        pass


def _cakaj_na_dalsi_start(kopia, ukaz, stop, krok_ms=500):
    """Vlakno prvej kopie: kym nie je `stop`, caka na znamenie druheho startu
    a pri nom zavola `ukaz` (DandurfApp.show_window - sama ide cez ui_call).

    Caka po kuskoch `krok_ms`, aby sa pri ukonceni zastavilo samo a nevisi
    v nekonecnom cakani. Pri chybe handle (WAIT_FAILED) skonci - tocit sa
    naprazdno nema zmysel."""
    k32 = kopia.api.k32
    while not stop.is_set():
        try:
            vysledok = k32.WaitForSingleObject(kopia.udalost, krok_ms)
        except Exception:
            return
        if vysledok == _WAIT_OBJECT_0:
            if stop.is_set():
                return
            try:
                ukaz()
            except Exception:
                from logging_setup import get_logger
                get_logger("main").exception("druhy start: okno sa neukazalo")
        elif vysledok != _WAIT_TIMEOUT:
            return


def _spusti_cakanie_na_dalsi_start(kopia, ukaz, stop):
    """Vrati vlakno (alebo None, ked nie je na co cakat)."""
    if kopia is None or not getattr(kopia, "udalost", None):
        return None
    vlakno = threading.Thread(target=_cakaj_na_dalsi_start,
                              args=(kopia, ukaz, stop),
                              name="zanshin-druhy-start", daemon=True)
    vlakno.start()
    return vlakno


def main():
    # Hooky PRED importom app. Import app nataha desiatky modulov (audio,
    # siet, ovladac, TTS...) a chyba v ktoromkolvek z nich - chybajuca
    # zavislost, preklep - je presne ta, ktoru appka bez konzoly nikde
    # neulozi: pythonw ju zahodi, zabaleny .exe (console=False) ju ukaze
    # len v okne PyInstalleru, ktore po zatvoreni zmizne. Kym bol import
    # app prvy riadok main(), takyto pad nezanechal ani crash.log.
    log_crash = _install_crash_hooks()
    # Jedna kopia PRED importom app: druha kopia nema co nacitavat - povie
    # prvej "ukaz okno" a skonci skor, nez by siahla na port, skratku ci
    # nastavenia. Az za hookmi, aby aj pad v nej skoncil v crash.log.
    global _JEDNA_KOPIA
    _JEDNA_KOPIA = _straz_jednej_kopie()
    from app import DandurfApp

    # Neosetrene vynimky VNUTRI Tk callbackov (napr. command= na tlacidle)
    # nezastavia mainloop a nepropaguju sa hore ako normalna Python
    # vynimka - Tk ich len vypise na stderr cez report_callback_exception.
    # Prepiseme ho, aby sa zapisali aj do crash.log.
    def _tk_callback_exception(exc_type, exc_value, exc_tb):
        log_crash(exc_type, exc_value, exc_tb)

    root = ctk.CTk()
    root.report_callback_exception = _tk_callback_exception
    # Pad v konstruktore ci v mainloop-e zapise do crash.log sys.excepthook
    # (nastaveny vyssie, pred importom app; volaju ho Python aj bootloader
    # PyInstalleru). Do 0.2.1 tu bol este try/except s vlastnym log_crash,
    # takze jeden pad bol v crash.log dvakrat - ako keby appka spadla dva
    # razy.
    app = DandurfApp(root)
    # Druhy start ukaze okno tejto kopie - ta ista cesta ako "Zobrazit" v
    # liste. Vlakno sa pusta az teraz, ked appka stoji: znamenie z druheho
    # startu pocas nacitania pocka v udalosti.
    stop = threading.Event()
    _spusti_cakanie_na_dalsi_start(_JEDNA_KOPIA, app.show_window, stop)
    try:
        root.mainloop()
    finally:
        stop.set()


if __name__ == "__main__":
    main()
