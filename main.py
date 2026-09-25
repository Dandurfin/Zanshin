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

import sys
import threading
import tkinter as tk
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


def main():
    # Hooky PRED importom app. Import app nataha desiatky modulov (audio,
    # siet, ovladac, TTS...) a chyba v ktoromkolvek z nich - chybajuca
    # zavislost, preklep - je presne ta, ktoru appka bez konzoly nikde
    # neulozi: pythonw ju zahodi, zabaleny .exe (console=False) ju ukaze
    # len v okne PyInstalleru, ktore po zatvoreni zmizne. Kym bol import
    # app prvy riadok main(), takyto pad nezanechal ani crash.log.
    log_crash = _install_crash_hooks()
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
    DandurfApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
