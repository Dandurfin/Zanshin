"""Hlavna appka (DandurfApp) - hlavne okno, prepojenie sfx/TTS pipeline,
profily, tray ikona.

Toto je kompozicny koren appky: vytvara a prepaja AudioDispatcher/
SpeechWorker (audio_engine.py), GamepadListener (gamepad.py),
GameProcessWatcher (game_profiles.py), SomaticOverlayManager (overlay.py)
a vsetky dialogy/karty (ui_dialogs.py).

Cast metod DandurfApp byva v mixinoch app_*.py (napr. app_data.DataMixin),
ktore DandurfApp dedi. Mixiny nesu len metody - cely stav ostava tu.

OD VERZIE 2.1 TU NIE JE ZIADNY KLAVESOVY HOOK. Hlasku nespusta stlacenie,
ale telo: `trigger.CueTrigger` sleduje zataz z hodiniek a `activity.py`
zistuje cez `GetLastInputInfo`, ci je hrac aktivny - to vracia jedine
pocet milisekund od posledneho vstupu, nie to, co sa stlacilo. Rozhodnutie
o doruceni ostava tu, lebo je tesne prepojene s UI (ui_call/log_threadsafe)
a s overlay vrstvou.
"""

import os
import math
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox
from tkinter import font as tkfont

# Stred stranky Dnes je tk.Canvas: enso je priehladne PNG (`create_image`),
# preto tu treba `ImageTk`. PIL nie je tvrda zavislost - bez neho appka bezi
# dalej (canvas ostane v jednofarebnom pozadi temy).
try:
    from PIL import ImageTk as _ImageTk
except Exception:               # pragma: no cover - PIL je bezne pritomny
    _ImageTk = None

import customtkinter as ctk

# DOLEZITE poradie: `gamepad` MUSI byt naimportovany skor nez `audio_engine`
# (gamepad pri importe nastavi SDL_AUDIODRIVER=dummy pre bezokenny joystick;
# audio_engine tento env var pri svojom importe odstrani tesne pred
# pygame.mixer.init() - ak by sa poradie obratilo, mixer by ostal nemy).
import gamepad
import activity
import audio_engine
import sfx_assets
import display
import hr_insights
import data_io
import hr_stats
import measure
import netinfo
import rebrik
import trigger
import guide_content
from guide_content import origin_sources
from heart_rate import ANY_INTERFACE, HeartRateMonitor
from hud import StatsHud
import theme as theme_mod
import ui_kit
from audio_engine import AudioDispatcher, EdgeTTSCache, SpeechWorker, speak_sapi_isolated
from game_profiles import PSUTIL_AVAILABLE, GameProcessWatcher, known_games
from guide_panel import GuidePanel, build_guide_into
from guided_tour import GuidedTour
from i18n import LANGUAGES, LANG_EN, LANG_SAME_AS_APP, tr, tr_lang
from overlay import SomaticOverlayManager
from paths import APP_NAME, AUDIO_DIR, DATA_DIR, TTS_CACHE_DIR

# Licencia tak, ako ju vidno v titulnej liste. NIE je to prekladany retazec:
# "GPLv3" je nazov licencie, rovnako ako "Zanshin" je nazov appky - prelozit
# ho by znamenalo tvrdit, ze ide o inu licenciu.
LICENCIA = "GPLv3"
from settings_model import (DEFAULT_AUDIO,
                            DASHBOARD_MAX_CARDS,
                            DEFAULT_COOLDOWN,
                            DEFAULT_EDGE_VOICE,
                            ENGINE_EDGE,
                            ENGINE_SAPI, MODE_COMBO, MODE_SFX, MODE_TTS,
                            clamp_float, clamp_int,
                            default_slots, normalize_breath_seconds,
                            engine_labels, label_to_engine,
                            dashboard_stat_clickable,
                            normalize_hud_config, normalize_monitor_target,
                            normalize_overlay_config, normalize_slot,
                            swap_dashboard_stats, toggle_dashboard_stat)
from ui_dialogs import (watch_app_qr, CUE_STYLE_LABELS,
                        DevLayerDialog,
                        NewProfileDialog,
                        OnboardingWizard, OverlaySettingsDialog,
                        SlotCard, WatchPairingDialog)
import ui_shell
from ui_shell import (PageContainer, Sidebar,
                      TitleBar, enable_frameless)
from collections import deque

import background

import hotkey
import hud_paint

# Mixiny DandurfApp (app_*.py) sa importuju az tu, za vsetkymi modulmi
# vyssie: co potrebuju, je uz nacitane, takze nemenia poradie importov
# (gamepad pred audio_engine). Mena spolocne pre app.py aj mixiny (app_log,
# nazvy jazykov, skratka "Teraz nie") su v app_spolocne.py - mixin nesmie
# importovat app (kruhovy import).
from app_spolocne import (LABEL_TO_LANG, LANG_NATIVE_LABELS, SNOOZE_HOTKEY_MINUTES,
                          app_log)
# DEFAULT_SNOOZE_HOTKEY app.py sam nepouziva (cita ho `load_settings` v
# app_prefs) - importuje sa, aby `app.DEFAULT_SNOOZE_HOTKEY` ostalo platne.
from app_spolocne import DEFAULT_SNOOZE_HOTKEY  # noqa: F401
from app_data import DataMixin
from app_prefs import PrefsMixin
from app_controls import ControlsMixin

try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

try:
    import pystray
    TRAY_AVAILABLE = PIL_AVAILABLE
except Exception:
    TRAY_AVAILABLE = False


class DandurfApp(DataMixin, PrefsMixin, ControlsMixin):
    # ZALOZNY slot, ked nie je zapnuty ani jeden. 3 = dychovy kruh.
    #
    # Do 18. 9. to bol JEDINY slot, ktory automaticka hlaska pouzivala.
    # Bolo to spravne rozhodnutie pre meranie (vsetky okna z jednej
    # kategorie) a zle pre appku: rovnaka veta stokrat za vecer prestane
    # fungovat. Teraz sa kategorie striedaju kolo-dokola
    # (`measure.next_slot`) a kategoria sa zapisuje do kazdeho okna, takze
    # faza 8 zbiera data od dnes.
    #
    # Vyber kategorie podla toho, co komu ZABERA, je stale faza 8 - to
    # potrebuje data. Striedanie je rovnomerne, nie personalizovane.
    CUE_SLOT_INDEX = 3

    # Klavesove sloty vo faze 2 nespustaju nic. Kod sa zatial NEMAZE
    # (to je faza 3) - toto je jediny vypinac a da sa v dev vrstve otocit.
    KEY_SLOTS_ENABLED = False

    # Obsadeny UDP port: kolkokrat a po akom case sa skusi vazba znova.
    # Tri pokusy po 8 s prekleni beznu pricinu - druha instancia appky, ktora
    # sa prave zatvara. Dlhsie uz nie je docasne.
    HR_BIND_RETRIES = 3
    HR_BIND_RETRY_MS = 8000

    # POHYB: od kolkych krokov za minutu sa appka neozve.
    #
    # PRECO VOBEC: tep od pohybu odlisit NEJDE. Uendes a kol. (2026, JMIR,
    # N=127) ukazali, ze model s 55 EKG priznakmi ma pri strednej fyzickej
    # aktivite specificitu 0,418 - takmer sest z desiatich okien chodze
    # oznaci ako stres. Jeden BPM kazdych ~1 az 3 s (kadencia hodiniek, viz
    # `trigger.MAX_KROK_S`) to nezvladne tobozu. Brana
    # na kroky teda nie je opatrnost, je to jedina cesta.
    #
    # PRECO NIE 100 (etablovana hranica strednej intenzity, 3 METy):
    # pomala chodza po byte ma 60-90 krokov/min a tep zdvihne o 10-20 bpm -
    # presne nas artefakt, ktory by stoerka prepustila.
    #
    # PRECO NIE NULA: literatura pocita s pasom na hrudi. Krokomer na
    # ZAPASTI pocita pohyb ruky a hranie je samy pohyb ruky, takze nula by
    # pravdepodobne zahodila vsetko.
    #
    # 15 je PREDBEZNE cislo od zadavatela, nie namerane. Prvych 10 sprav s
    # krokmi kazdej relacie sa zapisuje do denniku (`_metrics_log_left`)
    # prave preto, aby sa dalo nahradit hodnotou z vlastnych dat.
    KROKY_PRAH_ZA_MIN = 15.0

    # Z akeho sveta sa rata kriticky tep a prah zataze. Rozhodnutie
    # zadavatela (B3-worlds): LEN z hry - oba su definovane ako percentily
    # HRANIA (`hr_stats.dynamicky_kriticky`, `dynamicky_prah_zataze`). Na
    # testovacich datach jedina pracovna relacia v spolocnom pool-e stiahla
    # cas hrania nad prahom z ~23 % na ~9 % (ciel je ~20 %). Pokojova
    # zakladna ostava zo vsetkeho: telo je jedno.
    ALGORITMUS_SVET = "play"

    # Bocne menu ma 4 hlavne polozky + enso (Dnes, Historia, V hre,
    # Nastavenia); "vhre" je od redizajnu "Sumi noc" samostatna stranka,
    # nie karta - SETTINGS_TABS su len karty VNUTRI Nastaveni. Kluce su
    # zaroven kluce stranok, takze sidebar._select(kluc) / _navigate(kluc)
    # fungujú pre vsetky (paleta, onboarding "Sparovat teraz" -> vhre,
    # guided tour).
    # "guide" tu bol do 18. 9. ako samostatna karta. Vysvetlivky a teoria
    # patria k HLASKAM - clovek ich hlada prave vtedy, ked cita, co ktora
    # hlaska hovori, nie o dve karty dalej. Kluc ale ZIJE DALEJ: odkazuje
    # sa nan sprievodca, prikazova paleta aj `Sidebar.GROUPS`, a `_navigate`
    # ho presmeruje na "spustace" (viz nizsie).
    SETTINGS_TABS = ("spustace", "zvuk", "vseobecne")

    # Stare kluce -> kam sa dnes chodí. Bez toho by `_navigate("guide")`
    # prepadlo na `pages.show("guide")`, teda na stranku, ktora neexistuje,
    # a okno by ostalo prazdne - ticho, bez vynimky.
    TAB_ALIAS = {"guide": "spustace"}
    # Appka je dashboard s viacerymi pevne rozmiestnenymi panelmi (HUD,
    # paleta prikazov, mriezka statistik), nie textovy editor - volne
    # roztahovanie okna rozbijalo layouty (najma CommandPalette). Namiesto
    # opravovania kazdeho panela pre kazdu moznu velkost okno drzi jeden
    # pevny rozmer, nastaveny programovo cez geometry() - ziadne rucne
    # tahanie za hrany (viz enable_frameless() a minsize==maxsize nizsie).
    WINDOW_W, WINDOW_H = 1180, 760
    # Znacka v strede stranky Dnes. Pri 68 px (povodne miesto v bocnom
    # paneli) mal prstenec "natiahnute" 1,4 px a strácal sa. 168 px je
    # velkost z makety - pri nej ma prstenec okolo 4 px a v periferii sa
    # naozaj zachyti. Nad 100 px sa sada kresli s dvojnasobnym (nie
    # trojnasobnym) prevzorkovanim, viz `ui_shell._EnsoButton`.
    ENSO_SIZE = 168
    # Krytie mäkkeho stredoveho zavoja za ensom a textom. < 255, aby dojo
    # PRESVITALO (priehladne) - nie tmavy box, len tolko stmavenia, kolko
    # text potrebuje na citatelnost (zvysok nesie tienik pod textom).
    DNES_SCRIM_PEAK = 120
    # Tempo prekreslovania stredu (enso + dych dojo). 120 ms ~ 8/s = plynuly
    # obeh svetla po ense, rovnako ako mal widget.
    DNES_TICK_MS = 120

    def __init__(self, root):
        self.root = root
        # Bez preblikavania pri presune medzi monitormi s roznou mierkou:
        # potlaci CTk pokles na alpha 0.15 pocas prepoctu DPI (viz ui_kit).
        ui_kit.potlac_dpi_alpha_blik(self.root)
        self.root.title(APP_NAME)
        # Pevny rozmer (viz komentar pri WINDOW_W vyssie) - appka nema
        # rucny resize za hrany, minsize/maxsize su rovnake ako geometry.
        self.root.geometry(f"{self.WINDOW_W}x{self.WINDOW_H}")
        self.root.minsize(self.WINDOW_W, self.WINDOW_H)
        self.root.maxsize(self.WINDOW_W, self.WINDOW_H)
        # Vlastna titulkova lista (FAZA 2 redesignu) - odstrani OS ram;
        # samotna TitleBar (v _build_ui) uz len kresli nahradu. Vola sa
        # raz tu, nie v _build_ui, lebo ten len nici DETI root-u, nie
        # samotny root a jeho bindingy.
        enable_frameless(self.root)

        self.listening = False
        self.rebind_index = None
        # POZN: tu boli `keyboard_listener`, `mouse_listener`,
        # `rebind_kb_listener`, `rebind_mouse_listener` - zvyšky po pynput
        # hookoch, ktoré fáza 3 zrušila. Nastavovali sa na None a už ich nikto
        # nečítal (B28). Vstup sa dnes zisťuje cez `GetLastInputInfo`.
        self.gamepad = gamepad.GamepadListener(self.on_gamepad_button,
                                               self.on_gamepad_status)
        self._rebind_gamepad_temp = False
        self.tray_icon = None
        self.typing = False
        self._ready = False
        # Okno je zahalene (DWM cloak), kym sa pri starte cele nenakresli -
        # viz `_zahal_do_dokreslenia` / `_odhal_hotove_okno`.
        self._zahalene = False
        self._listen_started = None
        self.log_collapsed = True
        self._last_log_line = None
        self._guide_panel = None
        self._assets_progress_frame = None
        self._assets_progress_bar = None
        self.session_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        self.session_label = None
        self._auto_started_listening = False
        self.game_watcher = None

        ctk.set_appearance_mode("dark")

        settings = self.load_settings()
        self.lang = settings["lang"]
        # DVA SVETY, JEDNO TELO (0.2, B3-worlds). Svet (hra/praca) urcuje
        # vzhlad (`theme.WORLD_THEME`), ktoru historiu a postrehy appka
        # ukazuje a ci hlaska smie zaznit. `load_settings` uz zarucil, ze
        # tema sedi so svetom.
        self.world = settings["world"]
        # Svet BEZIACEJ relacie - pecati sa pri jej otvoreni a prepinac ho
        # uz nezmeni (viz `_open_hr_session`).
        self._session_world = self.world
        # Styl hlasky, ktory si hrac vybral, a stupen rebrika beziacej
        # relacie (0.2, `rebrik.py`). Stupen sa urci pri otvoreni relacie.
        self.cue_style = settings["cue_style"]
        self._cue_style_rel = self.cue_style
        self._cue_rung = rebrik.vrchol(self.world, self.cue_style)
        self._snooze_po_hlaske = None
        self.theme_key = settings["theme"]
        self.pal = theme_mod.tokens(self.theme_key)

        self.start_minimized = bool(settings["start_minimized"])
        # Uz raz povedane, ze × appku neukonci, len schova do listy (`on_close`).
        self.tray_close_explained = bool(settings["tray_close_explained"])
        self.auto_profile_enabled = bool(settings["auto_profile_enabled"]) and PSUTIL_AVAILABLE
        self.overlay_configs = settings["overlay_configs"]
        self._vizualy_napravene = bool(settings.get("_vizualy_napravene"))

        if settings["first_run"]:
            self.root.withdraw()
            wizard = OnboardingWizard(self.root)
            self.root.wait_window(wizard.top)
            if wizard.confirmed:
                # Krok 4 vybera HLAVNY SVET; `choice` je jeho tema.
                self.world = theme_mod.theme_world(wizard.choice)
                self._session_world = self.world
                self.theme_key = theme_mod.WORLD_THEME[self.world]
                self.pal = theme_mod.tokens(self.theme_key)
                self._apply_diagnostics(settings, wizard.diagnostics)
                settings["volume"] = wizard.volume_value
                # Krok 5: ako sa ma appka ozvat (styl hlasky). None = hrac
                # nevybral nic a ostava predvoleny hlas (ako "neviem").
                self._prevezmi_styl_z_onboardingu(wizard)
                # ak hrac v onboardingu klikol "Sparovat hodinky teraz",
                # otvorime parovaci dialog az PO dostaveni okna (viz koniec
                # __init__) - teraz appka este nie je hotova
                self._pending_pairing = bool(getattr(wizard, "wants_pairing", False))
            # Prvy start sa NIKDY neschovava do lišty - okno musi ostat
            # viditelne, aktivne a v popredi bez ohladu na `start_minimized`.
            #
            # POZOR (Tk na Windows): bezramove okno (overrideredirect), ktore
            # sa withdraw()-lo este PRED prvym zobrazenim, sa jednym
            # deiconify() NEUKAZE - ostane v stave "withdrawn" a hrac po
            # onboardingu vidi len plochu (guided tour potom plaval nad
            # prazdnou obrazovkou). Pomaha spracovat cakajuce udalosti a
            # zavolat deiconify znova; overene nazivo (gui_harness_onboarding).
            #
            # Zahalit az TU, za sprievodcom: ten je `transient(root)`, takze
            # pocas neho root zahaleny byt nesmie. Hrac potom stavbu stranok
            # (vratane preblikajucich Nastaveni) nevidi - okno sa ukaze
            # naraz a hotove az po __init__, ked sa rozbehne slucka Tk
            # (viz `_odhal_hotove_okno`).
            self._zahal_do_dokreslenia()
            self.root.deiconify()
            self.root.update()
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()

        self.monitor_target = settings["monitor_target"]
        self.hud_config = settings["hud_config"]
        # Na Dnes najviac DASHBOARD_MAX_CARDS kariet (mriezka 2x2). Dlhsi
        # zoznam sa dal dostat len rucnou upravou JSON - vybrat sa neda.
        self.dashboard_stats = list(settings["dashboard_stats"])[:DASHBOARD_MAX_CARDS]
        self.breath_inhale_s = float(settings["breath_inhale_s"])
        self.breath_exhale_s = float(settings["breath_exhale_s"])
        # Prah zataze si appka rata sama pri kazdej relacii z vlastnych dat
        # (`hr_stats.dynamicky_prah_zataze`). None = este nie je z coho.
        self._prah_z_dat = None
        self._prah_z_relacii = 0
        self.overlay_manager = SomaticOverlayManager(self.root, pal=self.pal)
        self.overlay_manager.set_monitor_target(self.monitor_target)
        self.overlay_manager.set_breath_seconds(self.breath_inhale_s, self.breath_exhale_s)
        self._apply_overlay_labels()
        for i, cfg in enumerate(self.overlay_configs):
            self.overlay_manager.configure(i, enabled=cfg["enabled"], scale=cfg["scale"],
                                           pos=(cfg["pos_x"], cfg["pos_y"]),
                                           color=cfg.get("color") or "")

        # Plain-python zrkadla - listener vlakna nesmu citat Tk premenne.
        # Odstup pri RUCNOM spusteni (Test, HUD nahlad). Konstanta - viz
        # POZN pri zrusenom paneli "Casovanie" na stranke Zvuk.
        self.cooldown_value = DEFAULT_COOLDOWN
        self.rate_value = int(settings["rate"])
        self.volume_value = int(settings["volume"])
        self.tour_seen = bool(settings.get("tour_seen", False))
        self.tour_step = max(0, int(settings.get("tour_step", 0) or 0))
        # Jazyk toho, co appka kresli DO HRY - viz `_game_text`.
        self.game_lang = settings.get("game_lang", LANG_EN)
        self.balance_value = int(settings["balance"])
        # Konstanty pre RUCNE spustenie (tlacidlo Test, HUD nahlad).
        # Nastavit sa nedaju - ako casto sa appka ozve, riadi volba
        # "Ako casto sa ozvem" na stranke Hlasky, a to je jedine miesto.
        self.overlap_value = False
        self.last_global_trigger_time = 0.0

        # --- Senzor Tepu (Wi-Fi / UDP biofeedback) ---
        self.hr_ip = str(settings["hr_ip"])
        # SKRYTA IP (0.2): adresa PC sa na obrazovke neukaze sama - okno
        # appky byva na streame aj na screenshote pre testera. Odkryje ju
        # az "Ukazat IP" (parovanie, Nastavenia) a len do restartu: ZAMERNE
        # len v pamati, do nastaveni sa nezapisuje (viz netinfo.mask_ip).
        self.show_ip = False
        self.show_ip_var = None
        self.hr_ip_entry = None
        self.hr_port = int(settings["hr_port"])
        # Vypocitana hodnota, nie nastavenie. Realne cislo pride pri prvom
        # otvoreni relacie z `hr_stats.dynamicky_kriticky`; dovtedy zaloha.
        self.hr_critical_bpm = int(hr_stats.KRITICKY_ZALOHA)
        self.hr_monitoring_enabled = bool(settings["hr_monitoring_enabled"])
        self.zanshin_graduated = bool(settings["zanshin_graduated"])
        self.zanshin_graduated_at = settings.get("zanshin_graduated_at")
        self._hr_state = "disconnected"   # disconnected | connecting | connected
        self._hr_last_bpm = None
        # Tep, ktory appka v tomto behu pocula, prestal chodit ("vypadol") -
        # na rozdiel od "este nic neprislo". Len zobrazenie a zaznam; spustac
        # ma vlastne pozastavenie (`_suspend_cue_trigger`). `_hr_lost_od` je
        # cas poslednej vzorky pred vypadkom (pre riadok v denniku).
        self._hr_lost = False
        self._hr_lost_od = None
        self._hr_over_since = None
        self._hr_overlay_warned = False
        self._hr_client_linked = False
        # Generacia bezuceho prijimacieho vlakna (0 = ziadne). Aktualizacie
        # so starou generaciou zahadzujeme - inak by indikator zamrzol na
        # poslednom BPM aj po vypnuti senzora.
        self._hr_generation = 0
        self.hr_status_label = None
        self.hr_enabled_var = None
        self.heart_rate_monitor = HeartRateMonitor(
            self.on_hr_bpm, self.on_hr_status, on_metrics=self.on_hr_metrics)
        # Kolko sprav s krokmi este zapisat do denniku. Nastavuje sa pri
        # otvoreni relacie - potrebujeme vediet, CO hodinky naozaj posielaju,
        # aby sa prah pohybu dal nastavit z dat a nie od oka.
        self._metrics_log_left = 0
        # Statistika tepu (zakladna, zataz, suhrn relacie) + zivy HUD panel.
        # `HeartStats` je cisto datova a vola sa vyhradne z GUI vlakna cez
        # `_apply_hr_bpm`, takze nepotrebuje zamok.
        self.hr_stats = hr_stats.HeartStats(self.hr_critical_bpm)
        self.hr_sessions_path = os.path.join(DATA_DIR, "hr_sessions.json")
        # Priebeh vecera po udalostiach (bod 6 zadania z 18. 9.). Doteraz
        # sa `_cue_log` len spocital do dialogu a zahodil - spatne sa
        # nedalo precitat, kedy sa co stalo a preco appka mlcala.
        self.hr_events_path = os.path.join(DATA_DIR, "hr_events.jsonl")
        # Meracie okna okolo hlasok. Vlastny subor, nie sucast suhrnu
        # relacie: `hr_sessions.json` drzi poslednych MAX_SESSIONS relacii
        # a starsie ticho zahadzuje, takze okna by mizli prave vtedy, ked
        # ich zacne byt dost na to, aby sa z nich dalo nieco precitat.
        self.hr_windows_path = os.path.join(DATA_DIR, "hr_windows.json")
        # Ci hrac prave nieco robi - GetLastInputInfo, ziadny hook.
        # Zaznam sluzi ako treti kanal v meracom okne (popri tepe a zatazi)
        # a vo faze 2 z neho bude aj rozpoznanie pauzy.
        self.activity = activity.ActivityTracker()
        self._activity_job = None
        # Uz 20 minut ani kratka pauza vo vstupe (gyro ovladaca, pacicka bez
        # mrtvej zony)? Tichy riadok na Dnes, raz za relaciu - viz
        # `_tick_nonstop_input`.
        self._nonstop_input = activity.NonstopInputWatch()
        self._dnes_nonstop_text = ""
        # Stavovy automat hlasky: zataz nad prahom 90 s -> natiahnute ->
        # caka na pauzu -> hlaska. Cisty modul, testovany bez Tk.
        self.cue_trigger = trigger.CueTrigger()
        self._cue_log = []           # natiahnutia aj zrusenia, do suhrnu relacie
        # Kolkokrat zlyhalo obnovenie stranky Dnes. Viz `_refresh_dnes_stats`:
        # jeho telo je v jednom `except`, takze rozbita stranka sa inak
        # neprejavi nicim - ani chybou, ani v gui_screenshots.
        self._dnes_refresh_fails = 0
        # Je spustac natiahnuty? JEDINY zdroj pravdy pre UI. Prstenec na ense
        # aj text v dychajucom pase cítaju odtialto - keby si kazdy odvodzoval
        # stav sam (napr. z `cue_trigger.is_armed`), raz sa rozidu a nikto si
        # toho nevsimne. Zapisuje sa vyhradne v `_set_enso_armed`.
        self._cue_armed = False
        # Volania z vlakien, ktore prisli pred `mainloop()`. Strop je
        # poistka: keby sa slucka nikdy nerozbehla, fronta nesmie rast.
        self._ui_pending = deque(maxlen=200)
        self.snooze_hotkey = settings["snooze_hotkey"]
        # Fotka na pozadi. Vymena obrazku aj vypnutie su v
        # `background.py` - tu sa drzi uz len zvolena jemnost.
        self.background_opacity = settings["background_opacity"]
        self._hotkey = None
        # postrehy z analyzy historie (hr_insights) - posledny ulozeny
        # vysledok sa ukaze hned, cerstvy sa dopocita v pozadi po starte
        self.hr_insights_path = os.path.join(DATA_DIR, "hr_insights.json")
        _stored = hr_insights.load_insights(self.hr_insights_path)
        # Postrehy su za JEDEN svet (B3-worlds). Ulozene za iny svet - alebo
        # zo starsej verzie, ktora ich ratala zo vsetkeho spolu - sa neukazu;
        # cerstve sa dopocitaju chvilu po starte (`run_hr_analysis`).
        if _stored.get("world") != self.world:
            _stored = {}
        self._hr_insights = list(_stored.get("insights") or [])
        self._hr_insights_at = _stored.get("computed_at")
        self._hr_analysis_thread = None
        # Analyza odmietnuta, lebo este bezala predosla (napr. hned po
        # prepnuti sveta) - dobehne znova, ked ta skonci. Viz `run_hr_analysis`.
        self._hr_analysis_rerun = False
        self._hr_rerun_job = None
        self._hr_session_open = False
        # Kolko sekund relacie bol HUD viditelny (biofeedback: videny tep sa
        # podvedome reguluje). Snima sa v `_tick_cue_trigger`, aby chytilo aj
        # prepnutie uprostred hrania; do suhrnu ide ako podiel z AKTIVNEHO casu.
        # `_hud_active_s` je ten isty cas, len bez podmienky viditelnosti -
        # delime nim (nie hrubym trvanim), lebo tik zahadzuje medzery >=5 s
        # (uspanie PC), takze inak by podiel po uspani umelo klesol.
        self._hud_vis_s = 0.0
        self._hud_active_s = 0.0
        self._hud_tick_t = None
        self.hud = StatsHud(self.root, self.hr_stats,
                            self.overlay_manager.style,
                            monitor_target=self.monitor_target)
        self._apply_hud_config()
        self.sfx_volume = self.volume_value
        self.tts_volume = self.volume_value
        self._recompute_volumes()

        self.log_text = None
        self.slots = []
        self.profiles = settings["profiles"]
        self.active_profile_name = settings["active_profile"]
        self.voice_map = {}          # popis -> SAPI voice id
        self.saved_voice_id = settings["voice_id"]
        self.rate_var = None

        # --- Edge Natural TTS ---
        self.engine_pref = settings["engine_pref"]
        self.engine = (ENGINE_SAPI
                       if self.engine_pref == ENGINE_EDGE and not audio_engine.EDGE_AVAILABLE
                       else self.engine_pref)
        self.edge_voice_id = settings["edge_voice"]
        self.edge_voice_map = {}     # popis -> ShortName
        self.edge_cache = EdgeTTSCache(self.log_threadsafe)
        self.edge_status_label = None
        self._pregen_job = None
        self._pregen_seq = 0
        # Hlaska, ktora pocas pocuvania chybala v cache (`_speak_text`) -
        # dogeneruje sa az po `stop_listening`, nie uprostred hry.
        self._pregen_po_hre = False

        self.worker = SpeechWorker(self.log_threadsafe, on_voices=self.on_voices_ready)
        self.worker.pending_voice = self.saved_voice_id or None
        self.worker.pending_rate = self.rate_value
        self.worker.pending_volume = self.tts_volume
        self.worker.start()

        self.audio = AudioDispatcher(self.worker, self.log_threadsafe)
        self.audio.overlap = self.overlap_value
        self.audio.rate = self.rate_value
        self.audio.sfx_volume = self.sfx_volume
        self.audio.tts_volume = self.tts_volume

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind_all("<Control-k>", lambda e: self.open_command_palette())
        if TRAY_AVAILABLE:
            self.setup_tray()
        self._apply_window_icon()

        os.makedirs(AUDIO_DIR, exist_ok=True)
        os.makedirs(TTS_CACHE_DIR, exist_ok=True)
        self._ready = True
        self.save_settings()
        self.log(tr("log.ready"))
        self.log(tr("log.safe_mode"))
        if self._vizualy_napravene:
            # Appka si prave sama zapla vizualy, ktore ju umlcovali. Nema to
            # spravit potichu - hrac ma vediet, ze sa mu nieco v nastaveniach
            # zmenilo, a ma to vediet vratit.
            self.log(tr("log.vizualy_napravene"))

        if PSUTIL_AVAILABLE:
            # Zoznam procesov sa cita LEN pri zapnutom auto-profile. Predtym
            # sken bezal vzdy a vypnuty prepinac len zahodil vysledok - appka
            # tak kazde 4 s citala mena procesov aj hracovi, ktory to vypol.
            if self.auto_profile_enabled:
                self._start_game_watcher()
        else:
            self.log(tr("log.auto_profile_unavailable"))

        if self.hr_monitoring_enabled:
            self.start_heart_rate_monitor()
        # POZN: tu sa zapinala volitelna Steamworks vrstva. Zanshin nema
        # ziadnu integraciu so Steamom (0.2) - vrstva bez SDK aj tak nerobila
        # nic, takze appka bezi presne ako doteraz.
        self._tick_session()
        self._tick_activity()
        # analyza historie tepu v pozadi (nie na GUI vlakne), az ked okno stoji
        self.root.after(1500, self.run_hr_analysis)

        # Okno musi po spustani ostat viditelne a v popredi - do systemovej
        # listy sa appka schova len na vyslovnu ziadost pouzivatela (tlacidlo
        # "Minimalizovat do lišty" alebo zavretie okna, ak je to tak
        # nastavene), nikdy automaticky.
        #
        # Ukazat ho ale az NAKRESLENE: Windows kresli len zobrazene okno, takze
        # bez zahalenia by hrac videl najprv priesvitny ram a potom skladanie
        # po kusoch (lista, pas, prazdna stranka, statistiky, dojo).
        self._zahal_do_dokreslenia()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        if self._zahalene:
            self.root.after(0, self._odhal_hotove_okno)
            # Poistka: okno nesmie nikdy ostat neviditelne, nech sa stane
            # cokolvek (odhalenie sa nespusti, CTk zmeni poradie krokov...).
            self.root.after(self.ODHAL_POISTKA_MS, lambda: self._odhal_hotove_okno(
                pokus=self.ODHAL_MAX_POKUSOV))
        if self.start_minimized and not settings["first_run"] and TRAY_AVAILABLE:
            self.root.after(150, self.minimize_to_tray)

        self.refresh_edge_banner()
        if sfx_assets.missing_count() > 0:
            self.show_assets_progress()
        threading.Thread(target=self._ensure_sfx_assets, daemon=True).start()
        if audio_engine.EDGE_AVAILABLE:
            # Zoznam Edge hlasov je pevny (`EDGE_FALLBACK_VOICES`) a NESTAHUJE
            # sa. Predtym sa pri kazdom starte s Edge - a ten je predvoleny -
            # tahal katalog z Microsoftu, len aby sa orezal presne na tento
            # zoznam. Na Microsoft ide appka az pri priprave hlasok
            # (`pregenerate`), a to len ked hlasky v hre naozaj hovoria.
            self._load_edge_voices()
        else:
            self.log(tr("log.edge_tts_missing"))

        # Po onboardingu appka ZACNE POCUVAT sama.
        #
        # Predtym hrac preklikal styri kroky o tom, co appka robi, a
        # pristal na stranke s hlaskou "Zastavené. Spúšťače nereagujú." -
        # za cely uvod ani raz nepocul, na co si to instaloval. Tlacidlo na
        # poslednom kroku sa vola "spustit", tak nech to naozaj spusti;
        # zastavit sa da jednym klikom na ten isty pas.
        # Az teraz, ked uz su vlakna spustene: doruci to, co stihli
        # zalogovat pred rozbehnutim slucky.
        self.root.after(0, self._flush_ui_pending)

        self.start_snooze_hotkey()

        if settings["first_run"]:
            self.root.after(250, self.start_listening)

        # Ak hrac v onboardingu klikol "Sparovat hodinky teraz", otvorime
        # parovaci dialog az teraz - okno appky uz je hotove a viditelne.
        if getattr(self, "_pending_pairing", False):
            self._pending_pairing = False
            self.sidebar._select("vhre")
            self.root.after(400, self.open_watch_pairing)
        elif settings["first_run"] and not self.tour_seen:
            # Prva prehliadka appky - az po onboardingu a len ak hrac neisiel
            # rovno parovat hodinky (aby sa dva sprievodcovia neprekryvali).
            self.root.after(600, self.start_tour)

    # ---------- start bez preblikania ----------
    #
    # Pri starte bolo okno na obrazovke skor, nez bolo nakreslene: prvy obraz
    # takmer cely priesvitny (presvitala plocha), potom 4-8 medzikrokov. Pri
    # prvom spusteni po onboardingu bolo vidno skladat sa vsetky stranky.
    # Nebolo to mnozstvom dat (pri dnesnej velkosti historie) - Windows
    # posiela kreslenie len ZOBRAZENEMU oknu a Tk kresli lenivo. DWM cloak
    # (`ui_kit.zahal_okno`) okno zobrazi a necha nakreslit, len ho neukaze.

    # Kolkokrat po 10 ms pockat, kym CTk v `mainloop()` okno schova a znova
    # ukaze (spolu zhruba 1-2 s, casovace Tk na Windows su hrubsie). Potom
    # sa okno odhali aj tak. Bezne to CTk stihne za menej nez 0,1 s.
    ODHAL_MAX_POKUSOV = 100
    # Posledna poistka: najneskor po 10 s je okno viditelne vzdy.
    ODHAL_POISTKA_MS = 10000

    def _zahal_do_dokreslenia(self):
        """Zahali okno tesne pred prvym zobrazenim. Ked to Windows neprijme
        (starsi system, chyba), `_zahalene` ostane False a start bezi ako
        doteraz - len s preblikanim."""
        if not getattr(self, "_zahalene", False):
            self._zahalene = ui_kit.zahal_okno(self.root, True)

    def _okno_este_schovane(self):
        try:
            return self.root.state() != "normal"
        except Exception:
            return False

    def _odhal_hotove_okno(self, pokus=0):
        """Ukaze okno az ked je cele nakreslene - naraz, nie po kusoch.

        CTk v `mainloop()` okno este raz schova, prepocita a ukaze (tmava
        lista, `_windows_set_titlebar_color`); `after(0)` pribehne prave v
        tom schovanom useku. Kym okno nie je "normal", skusi to znova o
        10 ms - najviac `ODHAL_MAX_POKUSOV`-krat, potom odhali aj tak.

        Cakanie je ZAMERNE mimo try/finally: `return` zvnutra by cez
        `finally` odhalil okno predcasne, este nenakreslene. Samotne
        odhalenie je vo `finally`, takze prebehne aj ked kreslenie spadne.
        Ked by zlyhalo aj odhalenie, `_zahalene` ostane True a poistka
        (`ODHAL_POISTKA_MS`) to skusi znova."""
        if not getattr(self, "_zahalene", False):
            return
        if pokus < self.ODHAL_MAX_POKUSOV and self._okno_este_schovane():
            try:
                self.root.after(10, lambda: self._odhal_hotove_okno(pokus + 1))
                return
            except Exception:
                app_log.exception("start: odklad odhalenia zlyhal - odhalim hned")
        try:
            self.root.update()               # rozlozenie + WM_PAINT + prekreslenie
            self._refresh_dnes_backdrop()    # dojo nech je uz v prvom obraze
            self.root.update_idletasks()
        except Exception:
            app_log.exception("start: dokreslenie pred odhalenim zlyhalo")
        finally:
            self._zahalene = not ui_kit.zahal_okno(self.root, False)

    # ---------- SFX kniznica ----------

    def _ensure_sfx_assets(self):
        def progress(done, total):
            self.ui_call(lambda: self._update_assets_progress(done, total))
        sfx_assets.ensure_assets(log=self.log_threadsafe, progress=progress)

    def show_assets_progress(self):
        """Maly nenapadny prúžok v hornej casti okna - len ked naozaj
        chybaju SFX subory (napr. po precistení %APPDATA%)."""
        if self._assets_progress_frame is not None:
            return
        pal = self.pal
        frame = ctk.CTkFrame(self.main, fg_color=pal["surface_alt"], corner_radius=10)
        frame.pack(fill="x", padx=20, pady=(0, 8), before=self.main_grid)
        ctk.CTkLabel(frame, text=tr("assets.preparing"), text_color=pal["text"],
                    font=("Segoe UI", 11)).pack(side="left", padx=14, pady=10)
        bar = ctk.CTkProgressBar(frame, width=160, progress_color=pal["accent"])
        bar.set(0.0)
        bar.pack(side="right", padx=14, pady=10)
        self._assets_progress_frame = frame
        self._assets_progress_bar = bar

    def _update_assets_progress(self, done, total):
        if total <= 0:
            return
        if self._assets_progress_bar is not None:
            try:
                self._assets_progress_bar.set(done / total)
            except Exception:
                pass
        if done >= total and self._assets_progress_frame is not None:
            self.root.after(600, self._hide_assets_progress)

    def _hide_assets_progress(self):
        if self._assets_progress_frame is not None:
            try:
                self._assets_progress_frame.destroy()
            except Exception:
                pass
            self._assets_progress_frame = None
            self._assets_progress_bar = None

    # ---------- hlasitost (master + vyvazenie SFX/hlas) ----------

    def _recompute_volumes(self):
        """Master hlasitost + posuvnik Vyvazenie -> samostatna efektivna
        hlasitost pre SFX a pre hlas (TTS), obe v rozsahu 0-100.

        balance 50 = obe na plnej masterovej hlasitosti; 0 = len SFX
        (hlas stiseny), 100 = len hlas (SFX stiseny)."""
        master = self.volume_value
        balance = self.balance_value
        sfx_mult = min(1.0, (100 - balance) / 50.0)
        tts_mult = min(1.0, balance / 50.0)
        self.sfx_volume = round(master * sfx_mult)
        self.tts_volume = round(master * tts_mult)

    def _apply_diagnostics(self, settings, diagnostics):
        """Diagnostika herneho tiena (Onboarding krok 2) rozhoduje, ktore
        zo 4 uz pripravenych zakladnych slotov (data/klavesy/hlasky/zvuky
        su vzdy rovnake) su po onboardingu ZAPNUTE. Zaskrtnuty symptom ->
        prislusny slot ostava enabled=True (predvolene z DEFAULT_SLOT);
        nezaskrtnuty -> slot sa vypne (enabled=False), ale zostava v
        zozname pripraveny - pouzivatel si ho kedykolvek sam zapne."""
        if not diagnostics:
            return
        try:
            slots = settings["profiles"][0]["slots"]
        except (KeyError, IndexError):
            return
        # diagnostika 0 = zovreta ruka/trasenie pri mierení -> slot 2
        # (Release), 1 = zatate zuby/celust -> slot 1 (Jaw), 2 =
        # predklananie/nestabilita -> slot 0 (Grounded), 3 = zadrziavanie
        # dychu/panika -> slot 3 (Breathe).
        mapping = {0: 2, 1: 1, 2: 0, 3: 3}
        for diag_index, slot_index in mapping.items():
            if slot_index < len(slots):
                slots[slot_index]["enabled"] = bool(diagnostics.get(diag_index, True))

    # ---------- UI ----------

    def _build_ui(self):
        pal = self.pal
        # Prvky, ktore si vlastnu kopiu palety nedrzia (bubliny s popiskami),
        # si ju vezmu odtialto - inak by kreslili starym `ui_shell.PAL`.
        ui_shell.set_theme_pal(pal)
        self.root.configure(fg_color=pal["bg"])
        # rekreacia okna (prepnutie temy/jazyka) znici aj rozostavany
        # priebeh prípravy SFX - referencie zresetujeme, aby sme sa
        # nepokusali aktualizovat uz zniceny widget.
        self._assets_progress_frame = None
        self._assets_progress_bar = None
        # POZOR: HUD aj in-game vizualy su samostatne Toplevel okna, a tie su
        # tiez detmi root-u. Slepe zmazanie vsetkych deti ich znicilo pri
        # kazdom prepnuti temy/jazyka - StatsHud si ich uz nikdy nepostavil
        # a HUD ostal navzdy prazdny. Rusime len obsah hlavneho okna.
        for child in self.root.winfo_children():
            if isinstance(child, tk.Toplevel):
                continue
            child.destroy()

        # --- vonkajsi obal: vlastna titulkova lista hore, telo (sidebar +
        # stranky) pod nou. `enable_frameless()` sa vola len raz v __init__,
        # nie tu - odstranenie OS ramu netreba opakovat pri kazdom rebuilde. ---
        # Obal aj telo brali `fg_color` z moduloveho `ui_shell.PAL` - zo
        # starej zelenkavej palety, ktoru redizajn nahradil. Farba sa tym
        # navyse vyradila z prefarbovania tem (`theme_recolor` meni len to,
        # co v palete temy naozaj je), takze pri prepnuti Aizome/Sumi
        # ostavalo pozadie okna rovnake. Teraz je to `pal["bg"]`.
        appwrap = ctk.CTkFrame(self.root, fg_color=pal["bg"], corner_radius=0)
        appwrap.pack(fill="both", expand=True)
        self.appwrap = appwrap

        # POZN: nad titulkovou listou tu bol `DojoBand` - fotopas pevnej
        # vysky 130 px (ui_shell.DojoBand + hud_paint.render_dojo_band /
        # render_lamp_glow). Odstraneny: titulkova lista patri na samy vrch
        # okna, a pas nad nou bol 130 px mrtveho miesta, ktore len uberalo
        # z fixnej vysky okna (WINDOW_H). S nim odisiel aj posuvnik
        # "Pozadie dojo" v Nastaveniach a hodnota `dojo_intensity` - bez
        # pasu uz nemali co ovladat.
        # Prepinac sveta (Hra | Praca) sedi v liste vlavo od ⓘ - viz
        # `set_world` a `ui_shell.TitleBar`.
        titlebar = TitleBar(appwrap, root_window=self.root, app_name=APP_NAME,
                            on_close=self.on_close, version=tr("app.version_short"),
                            pal=pal, on_about=self.show_about,
                            about_tip=tr("about.title"), licence=LICENCIA,
                            world_values=self._world_labels(),
                            world_value=self._world_label(self.world),
                            on_world=self._on_world_label,
                            world_tip=tr("world.tip"))
        titlebar.pack(fill="x", side="top")
        self.titlebar = titlebar
        # Patnast klikov na cislo verzie otvori ladenie (§3.2). Lokalna Tk
        # vazba na jeden widget, nie globalny hook.
        titlebar.on_dev_layer = self.open_dev_layer

        body = ctk.CTkFrame(appwrap, fg_color=pal["bg"], corner_radius=0)
        body.pack(fill="both", expand=True, side="top")
        self.body = body

        self.pages = PageContainer(body)
        self.page_frames = {}          # kluc -> ramec stranky (hlavne aj karty)

        def _navigate(_key):
            self._navigate(_key)

        self.sidebar = Sidebar(body, on_navigate=_navigate, pal=pal,
                               version=tr("app.version_short"),
                               on_palette=self.open_command_palette,
                               on_enso_toggle=self.toggle_listening,
                               on_pair_watch=self.open_watch_pairing, labels={
            "pair_tip": tr("dnes.empty_btn"),
            "pair_live_tip": tr("dock.pulse_live_tip"),
            "dnes": tr("nav.dnes"),
            "historia": tr("nav.historia"),
            "vhre": tr("nav.vhre_short"),
            "nastavenia": tr("nav.nastavenia"),
            "cmdk": tr("nav.cmdk_hint"),
            "enso_start_tip": tr("dock.start_tip"),
            "enso_stop_tip": tr("dock.stop_tip"),
            "state_tip": tr("sidebar.state_tip"),
        })
        # Kontrolka tepu si stav pyta sama pri kazdom tiku - tak bije
        # plynule bez ohladu na to, ako casto chodia data z hodiniek.
        if getattr(self.sidebar, "pair_btn", None) is not None:
            try:
                self.sidebar.pair_btn.set_state_source(self._watch_pulse_state)
            except Exception:
                pass
        self.sidebar.pack(side="left", fill="y")
        self.pages.pack(side="left", fill="both", expand=True)

        built = {}
        for key, builder in (("dnes", self._build_dnes_page),
                             ("historia", self._build_historia_page),
                             ("vhre", self._build_vhre_page),
                             ("nastavenia", self._build_settings_group)):
            frame = ctk.CTkFrame(self.pages, fg_color=pal["bg"])
            self.pages.add_page(key, frame)
            built[key] = frame
            self.page_frames[key] = frame
            builder(frame, pal)

        self.pages.show("dnes")

        self._refresh_nav_badges()

        # command palette (Ctrl+K) - obsah sa generuje nanovo pri kazdom
        # otvoreni (viz open_command_palette), aby nikdy nezastaral po
        # pridani/zmazani slotu ci profilu mimo plneho _build_ui. Tlacidlo
        # v bocnom paneli ju vola priamo cez `on_palette` (viz Sidebar).

        # POZN: tu sa stavil `QuickDock` - tri ikony dole v bocnom paneli
        # (🔊 stisit, 😴 odlozit, ⌘ rychly profil). Odstranene vedome, nie
        # kvoli miestu:
        #
        #   STISENIE jednym klikom do tejto appky nepatri. Cela jej hodnota
        #   stoji na tom, ze vyrusi vtedy, ked je telo hore - a to je presne
        #   chvila, kedy je hrac na nu najviac nastvany. Jednoklikove
        #   stisenie sa preto pouzije systematicky prave vtedy, ked je
        #   hlaska najopravnenejsia. Hlasitost sa da stiahnut na nulu v
        #   Nastaveniach -> Zvuk; ze to trva tri kliky namiesto jedneho, je
        #   VLASTNOST: vypnut to nadobro ma byt rozhodnutie, nie reflex.
        #
        #   ODLOZENIE ostalo, len uz nema tlacidlo - ma globalnu skratku
        #   (Ctrl+Alt+Z, `start_snooze_hotkey`), ktora funguje aj v hre, a
        #   tam ju hrac potrebuje. Je casovo ohranicene a samo vyprsi, cize
        #   to nie je vypinac. Ze prave bezi, ukazuje bodka stavu v rade
        #   (`_refresh_snooze_indicator`). Od 0.2.1 je aj v ponuke ikony v
        #   liste (`setup_tray`) - skratku moze drzat ina appka.
        #
        #   PROFIL je dosiahnutelny cez ozubene koliesko (Nastavenia ->
        #   Spustace) a cez paletu Ctrl+K.

        # spatna kompatibilita pre show_assets_progress()/_update_assets_progress()/
        # refresh_edge_banner(), ktore ocakavaju self.main (rodic pre banner)
        # a self.main_grid (kotva "pred ktorou" sa banner/progress vlozia).
        self.main = built["dnes"]
        self.main_grid = self._dashboard_anchor_frame
        # ALIAS, nie druha znacka. Znacka od 2.1 zije v strede stranky Dnes,
        # ale `guided_tour.py`, `gui_harness_auto.py` aj
        # `gui_harness_onboarding.py` ju hladaju ako `app.sidebar.enso` -
        # a hladaju ju MENOM, takze pri premenovani by zlyhali TICHO
        # (bublina sprievodcu by sa len prestala na nieco ukazovat).
        # Cez tento alias ju najdu a `Sidebar.set_pal` ju aj dalej prefarbi.
        if getattr(self, "sidebar", None) is not None:
            self.sidebar.enso = self.enso
        # Prestavba okna (jazyk, zachrana pri teme) postavi bodku stavu nanovo
        # a ta zacina neodlozena. Pocas "teraz nie", ktore od 24. 9. pocuva
        # dalej, by potom svietila zelenou "appka pocuva" namiesto jantarovej.
        if getattr(self, "_snooze_job", None) is not None:
            self._refresh_snooze_indicator()

    def _build_dnes_page(self, page, pal):
        """Dnes: dychajuci pas (spustit/zastavit), tep so zatazou, suhrn
        relacie a dennik.

        Povodny "Prehlad" mal hore siroke tlacidlo, ktore blikalo dvoma
        farbami. Tu je namiesto neho `KamaeBar` - jediny pohyblivy prvok v
        okne, ktory dycha v rovnakom rytme ako dychovy kruh v hre a po
        zastaveni stoji. Stav sa teda necita z farby, ale z toho, ci sa
        rozhranie hybe.
        """
        wrap = ctk.CTkFrame(page, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=24, pady=(20, 20))

        # --- banner o chybajucom edge-tts (skryty, kym ho refresh_edge_banner nezapne) ---
        self.banner = ctk.CTkFrame(wrap, fg_color=pal["danger"], corner_radius=ui_kit.RADIUS_CONTROL)
        self.banner_label = ctk.CTkLabel(self.banner, text="", justify="left",
                                         anchor="w", text_color=pal["bg"],
                                         font=ui_kit.ui(11))
        self.banner_label.pack(side="left", padx=14, pady=10, fill="x", expand=True)
        ctk.CTkButton(self.banner, text=tr("common.retry"), fg_color=pal["bg"],
                      text_color=pal["text"], hover_color=pal["surface_alt"],
                      command=self.retry_edge_import).pack(side="right", padx=14, pady=10)

        anchor = ctk.CTkFrame(wrap, fg_color="transparent")
        self._dashboard_anchor_frame = anchor
        anchor.pack(fill="x")

        self.kamae = ui_kit.KamaeBar(anchor, pal, on_toggle=self.toggle_listening)
        # Znacka (enso) dycha PRESNE s dychovou linkou tejto hlavicky -
        # jedno okno, jeden rytmus. Viz `KamaeBar.phase()`.
        self.kamae.pack(fill="x")
        self.kamae.set_texts(tr("kamae.bar_title"), tr("kamae.bar_sub"))

        # Kedy sa appka naposledy ozvala. Zamerne tlmene: je to kontext k
        # stavu, nie vykon. Ked este nic nebolo, riadok sa vobec nezobrazi -
        # prazdne "0x" by bolo pocitadlo. Od 2.1 to nie je widget, ale text
        # kresleny na stred (`_paint_dnes_canvas`); `_refresh_last_cue` len
        # meni tento retazec a vyziada prekreslenie.
        self._dnes_lastcue_text = ""

        # Okno ma pevnych 1180x760 (viz WINDOW_W/H) a pod dychajucim pasom
        # ostava asi 600 px. Kym tam boli len dve karty, vyslo to; s tretim
        # panelom uz nie a dennik by z okna vypadol. Pas ostava PEVNE hore
        # (jeho rytmus je stav appky a nesmie odrolovat), vsetko pod nim sa
        # posuva - rovnako ako na Historii.
        body = ctk.CTkScrollableFrame(
            wrap, fg_color="transparent", scrollbar_button_color=pal["surface_alt"],
            scrollbar_button_hover_color=pal["accent"])
        body.pack(fill="both", expand=True)
        self.dnes_body = body

        # --- stav | statistiky ---
        # Tazisko stranky je STAV, nie cisla. Vlavo znacka, ktora stav nesie,
        # vpravo cisla. Panel s tepom a krivkou sa presunul POD tuto dvojicu
        # - je to podrobnost, nie to prve, co ma hrac vidiet.
        cols = ctk.CTkFrame(body, fg_color="transparent")
        cols.pack(fill="x", pady=(14, 0))
        cols.grid_columnconfigure(0, weight=1)
        # 300 px pevne: v nemcine a japoncine su popisky kariet dlhsie a pri
        # pruznej sirke by sa zalamovali inak v kazdom jazyku.
        cols.grid_columnconfigure(1, weight=0, minsize=300)
        cols.grid_rowconfigure(0, weight=1)

        stred = ctk.CTkFrame(cols, fg_color="transparent")
        stred.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.dnes_stred = stred

        # STRED = tk.Canvas, nie ramcek s labelmi.
        #
        # PRECO: CTk/tk widget nevie byt priehladny nad fotkou -
        # `fg_color="transparent"` zdedi PLNU farbu rodica, takze enso aj text
        # nad dojom vzdy sedeli na tmavom STVORCI (a ziaden scrim ho nezakryl,
        # lebo box je nepriehladny obdlznik). Canvas kresli dojo, enso
        # (PRIEHLADNE PNG cez `create_image`) aj text (`create_text` = bez
        # pozadia) na jednu plochu - box zmizne, dojo vidno cele, enso aj text
        # plavaju. Kresli sa v `_paint_dnes_canvas`, riadi `_refresh_dnes_backdrop`.
        self.dnes_canvas = tk.Canvas(stred, highlightthickness=0, bd=0,
                                     bg=pal["bg"], takefocus=0)
        self.dnes_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.dnes_canvas.bind("<Button-1>", self._dnes_canvas_click)
        self.dnes_canvas.bind("<Motion>", self._dnes_canvas_motion)
        self.dnes_canvas.bind("<Leave>",
                              lambda _e: self._dnes_set_cursor(""))
        self._dnes_tk_imgs = {}      # drzi ImageTk referencie (Tk ich inak zahodi)
        self._dnes_hit = {}          # klikacie zony: "enso"/"credit" -> (x0,y0,x1,y1)
        self._dnes_cursor = ""
        self._dnes_fonts = {}
        # Trvale polozky canvasu (dojo, enso) a podpisy proti zbytocnemu
        # prekresleniu - nova stranka zacina nacisto (stary canvas je zniceny).
        self._dnes_items = None
        self._dnes_frame_sig = None
        self._dnes_text_sig = None
        self._dnes_cur_dojo = None
        self._dnes_cur_pil = None
        self._dnes_titul = ""
        self._dnes_veta = ""
        self._dnes_lastcue_text = ""
        # Twitch odkaz pre kredit (klik na "Dandurfin" v strede).
        self._dnes_twitch = next(
            (u for n, u in guide_content.COMMUNITY_LINKS if n == "Twitch"), None)

        # ZNACKA (残 v ense) + spinac stavu. Uz to NIE JE widget, ale kresba na
        # Canvase (`ui_shell._EnsoHero`). API ostava rovnake, takze alias
        # `sidebar.enso`, `_apply_listening_visuals`, `_set_enso_armed` aj
        # harness (`enso._live`/`_armed`) fungujú nezmenene. Spinac zije v pase
        # (`ui_kit.KamaeBar`); enso je to, co sa cita, a klik naň prepina.
        self.enso = ui_shell._EnsoHero(pal, size=self.ENSO_SIZE,
                                       on_change=self._on_enso_change)
        try:
            if getattr(self, "zanshin_graduated", False):
                self.enso.graduate()   # uz promovany - enso ostava zlaty mesiac
        except Exception:
            app_log.exception("promocia: obnova mesiaca pri starte zlyhala")
        # Enso dycha PRESNE s dychovou linkou v hlavicke - jedno okno, jeden
        # rytmus. Viz `KamaeBar.phase()`.
        try:
            self.enso.set_phase_source(self.kamae.phase)
        except Exception:
            app_log.exception("enso: napojenie na dych zlyhalo")

        self._build_dnes_backdrop(stred, pal)   # scrim + <Configure>
        # NAPLNIT HNED. Text sa inak pise len z `_apply_listening_visuals` a
        # `_set_enso_armed`, a ani jedno pri stavbe okna nebezi - po cerstvom
        # starte by stala znacka nad prazdnym miestom.
        self._refresh_dnes_state_text()
        self._refresh_dnes_backdrop(force=True)

        # --- tep a zataz (podrobnosti, pod stavom) ---
        hr_panel = ui_kit.Panel(body, pal, title=tr("dnes.hr_title"))
        hr_panel.pack(fill="x", pady=(16, 0))
        self.hr_panel = hr_panel

        bpm_row = ctk.CTkFrame(hr_panel.body, fg_color="transparent")
        bpm_row.pack(fill="x")
        self.dnes_bpm = ctk.CTkLabel(bpm_row, text="--", font=ui_kit.display(40),
                                     text_color=pal["text"])
        self.dnes_bpm.pack(side="left")
        ctk.CTkLabel(bpm_row, text=tr("dnes.bpm_unit"), font=ui_kit.ui(11),
                     text_color=pal["text_faint"]).pack(side="left", padx=(9, 0),
                                                        pady=(14, 0))
        # "aby pouzivatel vedel": veta pri cisle + rozbalitelne co to znamena
        self.dnes_info_bpm = self._metric_info(hr_panel.body, pal, "bpm")
        self.dnes_info_bpm.pack(fill="x", pady=(2, 0))

        # "zive" prvky (krivka, zataz) su v jednom ramci, ktory sa bez hodiniek
        # schova a namiesto neho sa ukaze prazdny stav (dnes_empty) - inak by
        # sa v kompaktnom okne nezmestili oba a prazdna krivka nic nehovori
        live = ctk.CTkFrame(hr_panel.body, fg_color="transparent")
        self.dnes_live = live
        self.dnes_spark = ui_kit.Sparkline(live, pal, height=62)
        self.dnes_spark.pack(fill="x", pady=(10, 0))

        load_row = ctk.CTkFrame(live, fg_color="transparent")
        load_row.pack(fill="x", pady=(16, 5))
        ctk.CTkLabel(load_row, text=tr("hud.load"), font=ui_kit.ui(12),
                     text_color=pal["text_dim"]).pack(side="left")
        self.dnes_zone = ctk.CTkLabel(load_row, text="—", font=ui_kit.ui(12),
                                      text_color=pal["text_faint"])
        self.dnes_zone.pack(side="right")
        self.dnes_load = ui_kit.SegmentBar(live, pal)
        self.dnes_load.pack(fill="x")
        self.dnes_info_load = self._metric_info(live, pal, "load", wrap=360)
        self.dnes_info_load.pack(fill="x", pady=(9, 0))

        # --- stopa relacie ---
        # Krivka nad tymto je zive okno poslednych troch minut. Toto je
        # cely vecer: kde tep vyskocil, ako dlho tam ostal a kedy appka
        # spustila dychanie. Dovtedy sa dala relacia precitat az v
        # Historii, a aj tam len ako riadok cisel.
        ctk.CTkFrame(live, fg_color=pal["line_soft"], height=1,
                     corner_radius=0).pack(fill="x", pady=(14, 0))
        trace_head = ctk.CTkFrame(live, fg_color="transparent")
        trace_head.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(trace_head, text=tr("dnes.trace_title"), font=ui_kit.ui(12),
                     text_color=pal["text_dim"]).pack(side="left")
        self.dnes_trace_meta = ctk.CTkLabel(trace_head, text="", font=ui_kit.mono(10),
                                            text_color=pal["text_faint"])
        self.dnes_trace_meta.pack(side="right")
        self.dnes_trace = ui_kit.SessionTrace(live, pal, height=88)
        self.dnes_trace.pack(fill="x", pady=(4, 0))
        live.pack(fill="x")

        # Prazdny stav (feedback: "Dnes posobi holo"): kym nie su hodinky,
        # ukazeme tlmeny nahlad HUD-u, jednu vetu a tlacidlo na parovanie.
        # Po pripojeni sa schova (_refresh_dnes_stats).
        self.dnes_empty = ctk.CTkFrame(hr_panel.body, fg_color="transparent")
        try:
            style = hud_paint.Style(pal)
            img = hud_paint.render_hud(
                style, bpm=72, stress=18,
                history=[64 + ((i * 5) % 14) for i in range(90)],
                threshold=self.hr_critical_bpm, baseline=64,
                labels={"load": tr("hud.load")}, pulse=0.0, session="", ss=2)
            img = img.resize((int(img.width * 0.62), int(img.height * 0.62)))
            img.putalpha(img.getchannel("A").point(lambda v: int(v * 0.45)))
            photo = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            preview = ctk.CTkLabel(self.dnes_empty, image=photo, text="")
            preview.image = photo
            preview.pack(pady=(10, 6))
            # referencia pre `_redraw_dnes_preview` - obrazok ma farby
            # zapecene, pri zmene temy sa musi nakreslit znova
            self.dnes_preview_label = preview
        except Exception:
            app_log.exception("nahlad HUD na Dnes sa nepodarilo vykreslit")
        ctk.CTkLabel(self.dnes_empty, text=tr("dnes.empty_title"), font=ui_kit.ui(13, "bold"),
                     text_color=pal["text_dim"]).pack()
        ctk.CTkLabel(self.dnes_empty, text=tr("dnes.empty_body"), font=ui_kit.ui(11),
                     text_color=pal["text_faint"], wraplength=380,
                     justify="center").pack(pady=(4, 10))
        ui_kit.chip(self.dnes_empty, pal, tr("dnes.empty_btn"), self.open_watch_pairing,
                    width=170).pack()
        # ktory z dvojice (live / empty) je vidno, riesi _refresh_dnes_stats

        # "Moje štatistiky" - volitelna mriezka 2x2 (nahradza povodny pevny
        # 7-riadkovy StatList). "✎ upraviť" otvori popup so vsetkymi
        # metrikami, zvolit sa daju najviac 4 (DASHBOARD_MAX_CARDS); vyber aj
        # poradie sa uklada do settings (self.dashboard_stats).
        stats_wrap = ctk.CTkFrame(cols, fg_color="transparent")
        stats_wrap.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        # --- rychly prepinac HUD (tep v hre) ---
        # Vpravo hore, hned po ruke: zapnut/vypnut widget tepu bez chodenia do
        # Nastaveni. Ci ho hrac ma zapnuty, ovplyvnuje vysledok (biofeedback -
        # videny tep sa podvedome reguluje), preto sa oplati mat to na ocaich.
        # ⚙ vedla presmeruje do plnych HUD nastaveni ("V hre").
        hud_row = ctk.CTkFrame(stats_wrap, fg_color="transparent")
        hud_row.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(hud_row, text=tr("hud.quick_label").upper(), font=ui_kit.ui(11, "bold"),
                     text_color=pal["text_faint"], anchor="w").pack(side="left")
        ctk.CTkButton(
            hud_row, text="⚙︎", width=26, height=26, corner_radius=ui_kit.RADIUS_CONTROL,
            fg_color="transparent", hover_color=pal["surface_alt"],
            text_color=pal["text_dim"], font=ui_kit.ui(13),
            command=lambda: self._navigate("vhre")).pack(side="right")
        self.hud_quick_var = tk.BooleanVar(value=self.hud_config["enabled"])
        ctk.CTkSwitch(
            hud_row, text="", variable=self.hud_quick_var, width=40,
            switch_width=36, switch_height=18,
            progress_color=pal["accent2"], fg_color=pal["switch_off"],
            button_hover_color=pal["accent_hover"],
            command=lambda: self.on_hud_config_change(
                enabled=self.hud_quick_var.get())).pack(side="right", padx=(0, 8))

        stats_head = ctk.CTkFrame(stats_wrap, fg_color="transparent")
        stats_head.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(stats_head, text=tr("dashboard.stats_title").upper(),
                     font=ui_kit.ui(11, "bold"), text_color=pal["text_faint"],
                     anchor="w").pack(side="left")
        self.dashboard_edit_btn = ctk.CTkButton(
            stats_head, text=tr("dashboard.edit_stats"), height=22, corner_radius=ui_kit.RADIUS_CONTROL,
            fg_color="transparent", hover_color=pal["surface_alt"],
            text_color=pal["accent_hover"], font=ui_kit.ui(11),
            command=self._open_dashboard_picker)
        self.dashboard_edit_btn.pack(side="right")
        self.dashboard_grid = ctk.CTkFrame(stats_wrap, fg_color="transparent")
        self.dashboard_grid.pack(fill="x")
        self.dashboard_grid.grid_columnconfigure(0, weight=1, uniform="dstat")
        self.dashboard_grid.grid_columnconfigure(1, weight=1, uniform="dstat")
        self.dashboard_cards = {}
        self._rebuild_dashboard_stats_grid()

        # --- kde si dnes bol ---
        # Pod mriezkou kariet ostavala prazdna polovica stlpca. `zone_seconds`
        # pritom appka pocita od zaciatku a nikde ich neukazovala - styri
        # cisla, ktore z relacie povedia viac nez ktorekolvek jedno.
        zone_panel = ui_kit.Panel(stats_wrap, pal, title=tr("dnes.zones_title"))
        zone_panel.pack(fill="both", expand=True, pady=(12, 0))
        self.dnes_zone_panel = zone_panel
        self.dnes_zone_bar = ui_kit.ZoneBar(zone_panel.body, pal)
        self.dnes_zone_bar.pack(fill="x", pady=(0, 10))
        self.dnes_zone_rows = {}
        # Nazov vlavo, PODIEL vpravo - a nic medzi tym. Do 2.1 tu bola aj
        # farebna bodka a cas ("0:00   65 %"). Bodka opakovala farbu pruhu,
        # ktory je priamo nad riadkami a v tom istom poradi, a cas hovoril
        # to iste, co podiel, len inak. Styri riadky po troch udajoch robili
        # z panelu tabulku; ma to byt jeden pohlad.
        for zone in ui_kit.ZoneBar.ORDER:
            row = ctk.CTkFrame(zone_panel.body, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=tr(f"metric.zones.{zone}"), font=ui_kit.ui(11),
                         text_color=pal["text_dim"], anchor="w").pack(side="left")
            value = ctk.CTkLabel(row, text="0 %", font=ui_kit.mono(11),
                                 text_color=pal["text_faint"], anchor="e")
            value.pack(side="right")
            self.dnes_zone_rows[zone] = value
        self.dnes_zone_note = ctk.CTkLabel(
            zone_panel.body, text=tr("dnes.zones_hint"), font=ui_kit.ui(10),
            text_color=pal["text_faint"], anchor="w", justify="left", wraplength=280)
        self.dnes_zone_note.pack(fill="x", pady=(10, 0))

        # --- dennik ---
        log_panel = ui_kit.Panel(body, pal)
        log_panel.pack(fill="x", pady=(16, 0))
        log_head = ctk.CTkFrame(log_panel.body, fg_color="transparent")
        log_head.pack(fill="x")
        self.session_label = ctk.CTkLabel(log_head, text=self._session_text(),
                                          text_color=pal["text_faint"],
                                          font=ui_kit.mono(10))
        self.session_label.pack(side="right", padx=(8, 0))
        self.log_toggle_btn = ctk.CTkButton(
            log_head, text=self._log_toggle_text(), fg_color="transparent",
            hover_color=pal["surface_alt"], text_color=pal["text_dim"], anchor="w",
            height=26, corner_radius=ui_kit.RADIUS_CONTROL, font=ui_kit.ui(12), command=self.toggle_log)
        self.log_toggle_btn.pack(side="left", fill="x", expand=True)

        self.log_body = ctk.CTkFrame(log_panel.body, fg_color="transparent")
        self.log_text = ctk.CTkTextbox(self.log_body, height=110, corner_radius=ui_kit.RADIUS_CONTROL,
                                       fg_color=pal["entry_bg"],
                                       text_color=pal["text_dim"],
                                       font=ui_kit.mono(10))
        self.log_text.pack(fill="both", expand=True, pady=(8, 0))
        self.log_text.configure(state="disabled")
        if not self.log_collapsed:
            self.log_body.pack(fill="x")

        # "Preco to funguje" - jedna veta pod vsetkym, s odkazom do
        # Sprievodcu. Zamerne nenapadne: kto to vie, necita to; kto si nie
        # je isty, ci appka nie je len placebo, ma jeden klik k vede za nou.
        why = ctk.CTkFrame(body, fg_color="transparent")
        why.pack(fill="x", pady=(14, 0))
        ctk.CTkLabel(why, text=tr("dnes.why_line"), font=ui_kit.ui(11),
                     text_color=pal["text_faint"], anchor="w",
                     justify="left", wraplength=560).pack(side="left")
        ctk.CTkButton(why, text=tr("dnes.why_link"), height=24, corner_radius=ui_kit.RADIUS_CONTROL,
                      fg_color="transparent", hover_color=pal["surface_alt"],
                      text_color=pal["accent_hover"], font=ui_kit.ui(11),
                      command=self.open_guide_panel).pack(side="left", padx=(6, 0))

        self._refresh_dnes_stats()

    def _icon_image(self, name, size):
        """Piktogram z `hud_paint` ako CTkImage do tlacidla.

        Referencie sa drzia v zozname - CTkImage bez referencie zmaze
        zberac odpadu a tlacidlo ostane bez ikony.
        """
        try:
            img = hud_paint.render_slot_icon(name, size, hud_paint.Style(self.pal))
            photo = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
        except Exception:
            return None
        if not hasattr(self, "_button_icons"):
            self._button_icons = []
        self._button_icons.append(photo)
        return photo

    # ---------- info k metrikam ("aby pouzivatel vedel") ----------

    def _metric_info(self, parent, pal, metric, wrap=420):
        """Veta pri cisle + rozbalitelne 'co to znamena' (ui_kit.InfoRow).
        Texty su v i18n pod metric.<id>.short / .more - presne znenie zo
        zadania, pre hraca, nie pre lekara."""
        return ui_kit.InfoRow(parent, pal, tr(f"metric.{metric}.short"),
                              tr(f"metric.{metric}.more"), tr("history.info_more"),
                              tr("history.info_less"), wrap=wrap)

    # ---------- stranka Historia ----------

    HISTORY_ROWS = 30          # najnovsich relacii v tabulke

    # (id, i18n kluc nazvu, theme token farby) - poradie chipov aj vo vybere
    HISTORY_METRICS = (
        # farby z radu pasiem (theme.ZONE_TOKENS), nie success/warn - graf
        # a pas pasiem vedla neho musia hovorit tou istou farebnou recou
        ("baseline", "metric.baseline.title", "zone_calm"),
        ("hrr", "metric.hrr.title", "blue"),
        ("over", "metric.over.title", "zone_high"),
        ("peak", "metric.peak.title", "accent"),
        # 0.2 - Historia ma ukazat cely obraz, nielen tep: ako dlho sa
        # hralo, kolko z toho v pokoji, ako dobre appka pocula a kolko
        # hlasok poslala. Id a farby su tie iste ako karty na Dnes.
        ("session_len", "metric.session_len.title", "text_dim"),
        ("calm_time", "metric.calm_time.title", "zone_calm"),
        ("signal", "metric.signal.title", "blue"),
        ("breath", "metric.breath.title", "murasaki"),
    )
    _METRIC_BUCKET_KEY = {"baseline": "baseline", "hrr": "hrr", "over": "over_s", "peak": "peak",
                          "session_len": "duration_s", "calm_time": "calm_s",
                          "signal": "coverage", "breath": "cues"}
    _METRIC_INFO_KEY = {"baseline": "baseline", "hrr": "hrr", "over": "zones", "peak": "peak",
                        "session_len": "session_len", "calm_time": "calm_time",
                        "signal": "signal", "breath": "breath"}
    # Co sa kresli stlpcami: veliciny, ktorych prirodzena nula nieco
    # znamena (nula minut nad hranicou je vypoved). Zakladna a zotavenie
    # su ciara - stlpec od nuly by na usek 60-70 BPM nechal par pixelov.
    # Signal tiez: zije okolo 95-100 % a stlpec od nuly by kazdy vypadok
    # schoval do par pixelov na vrchu.
    _METRIC_BARS = frozenset({"over", "peak", "session_len", "calm_time", "breath"})
    # Bucket drzi sekundy a pokrytie 0..1; graf ukazuje minuty a percenta.
    _METRIC_SCALE = {"over": 1 / 60.0, "session_len": 1 / 60.0,
                     "calm_time": 1 / 60.0, "signal": 100.0}
    # Desatinne miesta na osi a v "prvy -> posledny". Hlasky su priemer na
    # relaciu (1,5 je poctivejsie nez zaokruhlenych 2).
    _METRIC_DECIMALS = {"over": 1, "breath": 1}
    HISTORY_METRIC_CHIPS_PER_ROW = 4

    # Detail jednej relacie: (kluc bunky, i18n kluc popisku, token farby).
    # Popisky su tie iste slova ako v tabulke a na kartach - nove len tam,
    # kde take slovo este nebolo.
    HISTORY_DETAIL_COLS = 4
    HISTORY_DETAIL_CELLS = (
        ("duration", "history.col_duration", "text_dim"),
        ("avg", "history.col_avg", "text"),
        ("max", "history.detail_peak", "danger"),
        ("calm", "history.detail_calm", "zone_calm"),
        ("over", "history.col_over", "zone_high"),
        ("breath", "history.detail_breath", "murasaki"),
        ("peak", "history.col_peak", "accent"),
        ("hrr", "history.detail_hrr", "blue"),
        ("hrpi", "history.detail_hrpi", "accent"),
        ("signal", "history.detail_signal", "blue"),
        ("felt", "history.detail_felt", "text"),
    )

    def _build_historia_page(self, page, pal):
        """Historia relacii tepu: postrehy z analyzy na pozadi, trend
        pokojovej zakladne napriec relaciami, tabulka relacii s metrikami
        z cisteho BPM a panel 'Preco to funguje' so studiami.

        Data: hr_sessions.json (hr_stats.save_session) + hr_insights.json
        (hr_insights.analyze v pozadi). Stranka sa prekresli pri postaveni,
        po ulozeni relacie a po dobehnuti analyzy (_refresh_history_page).
        """
        scroll = ctk.CTkScrollableFrame(
            page, fg_color="transparent", scrollbar_button_color=pal["surface_alt"],
            scrollbar_button_hover_color=pal["accent"])
        scroll.pack(fill="both", expand=True, padx=24, pady=(20, 20))
        self.history_scroll = scroll

        ctk.CTkLabel(scroll, text=tr("history.title"), font=ui_kit.ui(17, "bold"),
                     text_color=pal["text"], anchor="w").pack(fill="x", padx=6)
        ctk.CTkLabel(scroll, text=tr("history.subtitle"), font=ui_kit.ui(11),
                     text_color=pal["text_dim"], wraplength=680, anchor="w",
                     justify="left").pack(fill="x", padx=6, pady=(4, 2))
        # Ktory svet stranka ukazuje (B3-worlds). Bez tejto vety by prazdna
        # Praca vyzerala ako stratena historia. Text doplna
        # `_refresh_history_page`, lebo svet sa meni bez prestavby stranky.
        self.history_world_note = ctk.CTkLabel(
            scroll, text="", font=ui_kit.ui(10), text_color=pal["text_faint"],
            wraplength=680, anchor="w", justify="left")
        self.history_world_note.pack(fill="x", padx=6, pady=(0, 10))

        # --- postrehy (analyza na pozadi) ---
        ins = ui_kit.Panel(scroll, pal, title=tr("history.insights_title"), right="")
        ins.pack(fill="x")
        self.history_insights_panel = ins
        self.history_insights_box = ctk.CTkFrame(ins.body, fg_color="transparent")
        self.history_insights_box.pack(fill="x")
        foot = ctk.CTkFrame(ins.body, fg_color="transparent")
        foot.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(foot, text=tr("history.insights_note"), font=ui_kit.ui(10),
                     text_color=pal["text_faint"], anchor="w", justify="left",
                     wraplength=520).pack(side="left", fill="x", expand=True)
        self.history_recompute_btn = ui_kit.chip(foot, pal, tr("history.recompute"),
                                                 self.run_hr_analysis, width=110)
        self.history_recompute_btn.pack(side="right")

        # --- trend napriec relaciami: metrika + casove obdobie sa daju
        # prepnut (chips), graf aj text sa prekreslia (_refresh_history_trend) ---
        tp = ui_kit.Panel(scroll, pal, title=tr("history.trend_title"))
        tp.pack(fill="x", pady=(14, 0))

        # Dva rady chipov pod sebou vyzerali ako jedna mriezka osmich
        # tlacidiel - z obrazovky sa nedalo precitat, ze horny rad meni CO
        # a dolny ZA AKE OBDOBIE. Popisok vlavo to povie jednym slovom.
        self.history_metric = getattr(self, "history_metric", "baseline")
        metric_row = ctk.CTkFrame(tp.body, fg_color="transparent")
        metric_row.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(metric_row, text=tr("history.pick_metric").upper(), width=74,
                     font=ui_kit.ui(9, "bold"), text_color=pal["text_faint"],
                     anchor="w").pack(side="left", anchor="n")
        # Osem metrik sa do jedneho radu nezmesti - chipy idu do mriezky
        # po styroch vpravo od popisku, ktory tak ostava jeden pre vsetky.
        chips = ctk.CTkFrame(metric_row, fg_color="transparent")
        chips.pack(side="left", fill="x", expand=True)
        self.history_metric_chips = {}
        for i, (key, title_key, _color) in enumerate(self.HISTORY_METRICS):
            btn = ui_kit.chip(chips, pal, tr(title_key),
                              lambda k=key: self._set_history_metric(k),
                              pressed=(key == self.history_metric))
            row, col = divmod(i, self.HISTORY_METRIC_CHIPS_PER_ROW)
            btn.grid(row=row, column=col, sticky="w", padx=(0, 6),
                     pady=(4, 0) if row else (0, 0))
            self.history_metric_chips[key] = btn

        self.history_period = getattr(self, "history_period", hr_stats.PERIOD_WEEK)
        period_row = ctk.CTkFrame(tp.body, fg_color="transparent")
        period_row.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(period_row, text=tr("history.pick_period").upper(), width=74,
                     font=ui_kit.ui(9, "bold"), text_color=pal["text_faint"],
                     anchor="w").pack(side="left")
        self.history_period_chips = {}
        for key in hr_stats.PERIODS:
            btn = ui_kit.chip(period_row, pal, tr(f"history.period.{key}"),
                              lambda k=key: self._set_history_period(k),
                              pressed=(key == self.history_period))
            btn.pack(side="left", padx=(0, 6))
            self.history_period_chips[key] = btn

        self.history_trend_caption = ctk.CTkLabel(tp.body, text="", font=ui_kit.ui(11),
                                                  text_color=pal["text_dim"], anchor="w")
        self.history_trend_caption.pack(fill="x")
        self.history_trend = ui_kit.TrendChart(tp.body, pal, height=158)
        self.history_trend.pack(fill="x", pady=(6, 0))
        self.history_trend_delta = ctk.CTkLabel(tp.body, text="", font=ui_kit.mono(11),
                                                text_color=pal["text"], anchor="w")
        self.history_trend_delta.pack(fill="x", pady=(4, 0))
        self.history_info_wrap = ctk.CTkFrame(tp.body, fg_color="transparent")
        self.history_info_wrap.pack(fill="x", pady=(6, 0))
        self._render_history_metric_info()

        # --- ktora hlaska zabera ---
        # Da sa pytat az odkedy sa kategorie striedaju (`measure.next_slot`).
        # Do 18. 9. hrala appka vzdy jednu, takze porovnavat nebolo co.
        ep = ui_kit.Panel(scroll, pal, title=tr("history.effect_title"), right="")
        ep.pack(fill="x", pady=(14, 0))
        self.history_effect_panel = ep
        self.history_effect = ui_kit.CueEffectChart(ep.body, pal)
        self.history_effect.pack(fill="x")
        self.history_effect_hint = ctk.CTkLabel(
            ep.body, text=tr("history.effect_hint"), font=ui_kit.ui(10),
            text_color=pal["text_faint"], anchor="w", justify="left",
            wraplength=560)
        self.history_effect_hint.pack(fill="x", pady=(8, 0))
        # REBRIK HLASKY (0.2): jedna ticha veta, len ked sa appka sama
        # stisila pod vrchol - s dovodom. Na vrchole sa nezobrazi vobec
        # (`_refresh_rebrik_note`).
        self.history_rebrik_note = ctk.CTkLabel(
            ep.body, text="", font=ui_kit.ui(10),
            text_color=pal["text_faint"], anchor="w", justify="left",
            wraplength=560)

        # --- pravidelnost: mriezka dni + serie ---
        # Jedina vec na tejto stranke, ktora nehovori o jednej relacii, ale
        # o vzore: vikendy, serie vecerov, tyzden, ked appka lezala vypnuta.
        gp = ui_kit.Panel(scroll, pal, title=tr("history.rhythm_title"), right="")
        gp.pack(fill="x", pady=(14, 0))
        self.history_rhythm_panel = gp
        grid_row = ctk.CTkFrame(gp.body, fg_color="transparent")
        grid_row.pack(fill="x")
        self.history_daygrid = ui_kit.DayGrid(grid_row, pal)
        self.history_daygrid.pack(side="left", fill="x", expand=True)
        # height treba zadat: CTkFrame ma predvolenu ziadanu vysku 200 px a
        # s pack_propagate(False) by si ju panel nechal aj s tromi riadkami
        # textu - pod mriezkou by ostala prazdna tretina panela.
        days_box = ctk.CTkFrame(grid_row, fg_color="transparent", width=150, height=118)
        days_box.pack(side="right", padx=(18, 0))
        days_box.pack_propagate(False)
        ctk.CTkLabel(days_box, text=tr("history.days_played").upper(),
                     font=ui_kit.ui(9, "bold"), text_color=pal["text_faint"],
                     anchor="w").pack(fill="x")
        # Farba je `text`, nie `success`: zelena bola z cias, ked to bola
        # seria a dala sa "drzat". Pocet dni nie je uspech ani neuspech.
        self.history_days_value = ctk.CTkLabel(days_box, text="—",
                                               font=ui_kit.display(22),
                                               text_color=pal["text"], anchor="w")
        self.history_days_value.pack(fill="x")

        # --- detail jednej relacie ---
        # Tabulka nizsie je hustá a presna, ale relacia sa z nej da uz len
        # PRECITAT. Tu sa da POZRIET - z krivky ulozenej v suhrne.
        dp = ui_kit.Panel(scroll, pal, title=tr("history.detail_title"), right="")
        dp.pack(fill="x", pady=(14, 0))
        self.history_detail_panel = dp
        self.history_detail_index = None      # None = najnovsia relacia
        self.history_detail_trace = ui_kit.SessionTrace(dp.body, pal, height=96)
        self.history_detail_trace.pack(fill="x")
        # Ten isty popis ako pod grafom v dotazniku po relacii - nie novy
        # text. Pruh "kde sa hralo" treba vysvetlit raz a rovnako; dva
        # vlastne popisy toho isteho obrazka by sa casom rozisli.
        self.history_detail_legend = ctk.CTkLabel(
            dp.body, text=tr("session.end.trace_hint"), font=ui_kit.ui(10),
            text_color=pal["text_faint"], anchor="w", justify="left",
            wraplength=640)
        self.history_detail_legend.pack(fill="x", pady=(6, 0))
        # VSETKY hodnoty vybranej relacie (0.2: "Historia = cely obraz"),
        # v mriezke po styroch - v jednom rade by sa jedenast buniek
        # nezmestilo. Poradie a popisky v `HISTORY_DETAIL_CELLS`.
        detail_grid = ctk.CTkFrame(dp.body, fg_color="transparent")
        detail_grid.pack(fill="x", pady=(10, 0))
        for col in range(self.HISTORY_DETAIL_COLS):
            detail_grid.grid_columnconfigure(col, weight=1, uniform="detail")
        self.history_detail_cells = {}
        for i, (key, label_key, token) in enumerate(self.HISTORY_DETAIL_CELLS):
            row, col = divmod(i, self.HISTORY_DETAIL_COLS)
            cell = ctk.CTkFrame(detail_grid, fg_color="transparent")
            cell.grid(row=row, column=col, sticky="w", padx=(0, 12),
                      pady=(10, 0) if row else (0, 0))
            ctk.CTkLabel(cell, text=tr(label_key).upper(),
                         font=ui_kit.ui(9, "bold"), text_color=pal["text_faint"],
                         anchor="w").pack(fill="x")
            value = ctk.CTkLabel(cell, text="—", font=ui_kit.display(18),
                                 text_color=pal[token], anchor="w")
            value.pack(fill="x")
            self.history_detail_cells[key] = value
        self.history_detail_hint = ctk.CTkLabel(
            dp.body, text=tr("history.detail_hint"), font=ui_kit.ui(10),
            text_color=pal["text_faint"], anchor="w", justify="left", wraplength=640)
        self.history_detail_hint.pack(fill="x", pady=(10, 0))

        # --- tabulka relacii ---
        sp = ui_kit.Panel(scroll, pal, title=tr("history.sessions_title"), right="")
        sp.pack(fill="x", pady=(14, 0))
        self.history_sessions_panel = sp
        self.history_sessions_box = ctk.CTkFrame(sp.body, fg_color="transparent")
        self.history_sessions_box.pack(fill="x")
        # --- export do tabulky ---
        # Data su hracove, takze si ich musi vediet zobrat. A hned pri
        # tlacidle aj veta o tom, ze appka ich nikam neposiela - to je
        # otazka, ktoru si pri appke merajucej tep polozi kazdy.
        export_row = ctk.CTkFrame(sp.body, fg_color="transparent")
        export_row.pack(fill="x", pady=(12, 0))
        self.history_export_btn = ctk.CTkButton(
            export_row, text="  " + tr("history.export_btn"),
            image=self._icon_image("table", 26), compound="left",
            width=210, height=34, corner_radius=ui_kit.RADIUS_CONTROL,
            border_width=1, border_color=pal["border"], fg_color="transparent",
            hover_color=pal["surface_alt"], text_color=pal["text_dim"],
            font=ui_kit.ui(12), command=self.export_sessions_csv)
        self.history_export_btn.pack(side="left")
        self.history_export_note = ctk.CTkLabel(
            export_row, text=tr("history.export_local"), font=ui_kit.ui(10),
            text_color=pal["text_faint"], anchor="w", justify="left", wraplength=470)
        self.history_export_note.pack(side="left", padx=(12, 0))

        infos = ctk.CTkFrame(sp.body, fg_color="transparent")
        infos.pack(fill="x", pady=(10, 0))
        self.history_info_hrr = self._metric_info(infos, pal, "hrr", wrap=640)
        self.history_info_hrr.pack(fill="x")
        self.history_info_zones = self._metric_info(infos, pal, "zones", wrap=640)
        self.history_info_zones.pack(fill="x", pady=(6, 0))
        self.history_info_hrpi = self._metric_info(infos, pal, "hrpi", wrap=640)
        self.history_info_hrpi.pack(fill="x", pady=(6, 0))
        # "Cítené · merané" v detaile su dve cisla bez sipky a bez verdiktu -
        # bez vety o tom, co je co, by sa "6 · 8" citalo ako "appka tvrdi,
        # ze sa mylis". Graf tuto metriku nema, tak vysvetlenie stoji tu.
        self.history_info_felt = self._metric_info(infos, pal, "felt_vs_measured", wrap=640)
        self.history_info_felt.pack(fill="x", pady=(6, 0))

        # --- Ako to vzniklo: rozbalitelny panel, text autora + tri priklady ---
        # (0.2) Namiesto dlheho zoznamu studii - cely je v ZDROJE.md.
        sc = ui_kit.Panel(scroll, pal)
        sc.pack(fill="x", pady=(14, 0))
        self.history_science_btn = ctk.CTkButton(
            sc.body, text=f"▸   {tr('origin.title')}", anchor="w",
            fg_color="transparent", hover_color=pal["surface_alt"], text_color=pal["text"],
            font=ui_kit.ui(13, "bold"), command=self._toggle_history_science)
        self.history_science_btn.pack(fill="x")
        self.history_science_body = ctk.CTkFrame(sc.body, fg_color="transparent")
        ctk.CTkLabel(self.history_science_body, text=tr("origin.text"),
                     font=ui_kit.ui(11), text_color=pal["text_dim"], wraplength=640,
                     anchor="w", justify="left").pack(fill="x", pady=(6, 4))
        ctk.CTkLabel(self.history_science_body, text=tr("origin.examples"),
                     font=ui_kit.ui(11), text_color=pal["text_dim"], wraplength=640,
                     anchor="w", justify="left").pack(fill="x", pady=(4, 0))
        # rovnaky mechanizmus ako Sprievodca: "↗ zdroj" -> webbrowser.open,
        # zoznam je ten isty (guide_content.PHILOSOPHY_SOURCES)
        self.history_source_links = []
        for label, url in origin_sources():
            link = ctk.CTkLabel(self.history_science_body, text=f"↗ {label}",
                                font=ui_kit.ui(10, "underline"), text_color=pal["accent"],
                                anchor="w", justify="left", cursor="hand2", wraplength=640)
            link.pack(fill="x", pady=(2, 0))
            link.bind("<Button-1>", lambda _e, u=url: webbrowser.open(u))
            self.history_source_links.append((link, url))
        ctk.CTkLabel(self.history_science_body, text=tr("origin.full_list"),
                     font=ui_kit.ui(10), text_color=pal["text_faint"], wraplength=640,
                     anchor="w", justify="left").pack(fill="x", pady=(8, 0))

        self._refresh_history_page()

    def _toggle_history_science(self):
        body = self.history_science_body
        if body.winfo_ismapped():
            body.pack_forget()
            self.history_science_btn.configure(text=f"▸   {tr('origin.title')}")
        else:
            body.pack(fill="x", pady=(4, 0))
            self.history_science_btn.configure(text=f"▾   {tr('origin.title')}")

    def _history_sessions(self):
        # `log` odovzdaný zámerne: nečitateľná história sa nesmie tváriť ako
        # "žiadne relácie" bez stopy (bug B15).
        return [s for s in hr_stats.load_sessions(self.hr_sessions_path,
                                                  log=self.log_threadsafe)
                if isinstance(s, dict)]

    def _world_sessions(self):
        """Relacie AKTUALNEHO sveta - len pre POHLADY (B3-worlds).

        Historia, trend a jeho pasmo, tabulka, rytmus, detail, karty na Dnes
        a postrehy ukazuju len svoj svet. Algoritmus sa na toto NEPYTA:
        pokojova zakladna ide zo vsetkych relacii (telo je jedno), kriticky
        tep a prah zataze len z hernych (viz `_open_hr_session`). Export
        berie vzdy vsetko."""
        return hr_stats.sessions_in_world(self._history_sessions(), self.world)

    @staticmethod
    def _fmt_minutes(seconds):
        try:
            total = int(float(seconds or 0))
        except (TypeError, ValueError):
            total = 0
        return f"{total // 60}:{total % 60:02d}"

    # ---------- trend: metrika + casove obdobie (chips) ----------

    def _render_history_metric_info(self):
        """ⓘ vysvetlenie pod grafom - preto samostatny wrap, ktory sa pri
        prepnuti metriky zbura a postavi znova (InfoRow nema setter)."""
        wrap = getattr(self, "history_info_wrap", None)
        if wrap is None or not wrap.winfo_exists():
            return
        for child in wrap.winfo_children():
            child.destroy()
        metric_key = self._METRIC_INFO_KEY.get(self.history_metric, "baseline")
        info = self._metric_info(wrap, self.pal, metric_key, wrap=640)
        info.pack(fill="x")

    def _set_history_metric(self, metric):
        self.history_metric = metric
        pal = self.pal
        for key, btn in self.history_metric_chips.items():
            btn.configure(
                fg_color=pal["accent2"] if key == metric else "transparent",
                border_color=pal["accent"] if key == metric else pal["border"],
                text_color=pal["text"] if key == metric else pal["text_dim"])
        self._render_history_metric_info()
        self._refresh_history_trend()

    def _set_history_period(self, period):
        self.history_period = period
        pal = self.pal
        for key, btn in self.history_period_chips.items():
            btn.configure(
                fg_color=pal["accent2"] if key == period else "transparent",
                border_color=pal["accent"] if key == period else pal["border"],
                text_color=pal["text"] if key == period else pal["text_dim"])
        self._refresh_history_trend()

    def _refresh_history_trend(self):
        """Prekresli graf + text trendu podla zvolenej metriky a obdobia.

        Obdobie urcuje, ktore relacie sa poctaju (napr. "Tyzden" = od
        pondelka) a do akych bucketov sa zoskupia pre graf (mesiac -> denne
        priemery, rok -> mesacne - presne ako v zadani); metrika urcuje,
        ktora hodnota bucketu sa vykresli.
        """
        caption = getattr(self, "history_trend_caption", None)
        if caption is None or not caption.winfo_exists():
            return
        pal = self.pal
        metric = self.history_metric
        period = self.history_period
        # Len aktualny svet - aj pasmo "bezne rozpatie" nizsie (B3-worlds).
        sessions = self._world_sessions()
        # Posuvne okno, nie kalendarne obdobie - viz hr_stats.rolling_start_ts
        since = hr_stats.rolling_start_ts(period)
        period_sessions = [s for s in sessions if isinstance(s, dict)
                          and isinstance(s.get("started"), (int, float))
                          and s["started"] >= since]
        bucket_period = hr_stats.CHART_BUCKET_FOR_PERIOD.get(period, period)
        # `bucket_axis` doplni dni bez relacie - bez neho by sa os zmrstila
        # a pauza by z grafu zmizla (viz hr_stats.bucket_axis)
        buckets = hr_stats.bucket_axis(
            hr_stats.aggregate_by_period(period_sessions, bucket_period),
            bucket_period, since)
        bucket_key = self._METRIC_BUCKET_KEY[metric]
        # casy su v sekundach - na grafe citatelnejsie v minutach; pokrytie
        # signalu je 0..1 - na grafe percenta (viz _METRIC_SCALE)
        scale = self._METRIC_SCALE.get(metric, 1.0)
        decimals = self._METRIC_DECIMALS.get(metric, 0)
        # Bucket BEZ dat sa posiela ako None, nie ako vynechany bod: inak
        # by sa stredajsia pauza na grafe nezobrazila a utorok by sa
        # posunul na jej miesto. Popisky osi x su uz spocitane v buckete.
        chart_values = [None if b[bucket_key] is None else b[bucket_key] * scale
                        for b in buckets]
        labels = [b["label"] for b in buckets]
        raw_values = [b[bucket_key] for b in buckets if b[bucket_key] is not None]
        title_key = {k: t for k, t, _c in self.HISTORY_METRICS}[metric]
        color_token = {k: c for k, _t, c in self.HISTORY_METRICS}[metric]
        bars = metric in self._METRIC_BARS

        # "Tvoje bezne rozpatie" (p25-p75) sa rata z CELEJ historie SVETA v
        # tom istom rozliseni bucketov - aby sa porovnavali rovnake veliciny.
        # Bez neho je kazdy bod len cislo; s nim je jasne, ktory z nich je
        # naozaj mimo.
        vsetky = hr_stats.aggregate_by_period(sessions, bucket_period)
        band = hr_stats.usual_range([b[bucket_key] * scale for b in vsetky
                                     if b[bucket_key] is not None])

        caption.configure(text=f"{tr(title_key)}  ·  {tr(f'history.unit.{metric}')}")
        self.history_trend.set_series(chart_values, labels=labels,
                                      color=pal[color_token], band=band,
                                      band_label=tr("history.band_label"), bars=bars,
                                      decimals=decimals)

        if len(raw_values) >= 2:
            first_v, last_v = raw_values[0], raw_values[-1]
            if metric == "baseline":
                trend = hr_stats.baseline_trend(period_sessions)
                if not trend["insufficient_span"]:
                    delta_text = tr("history.trend_delta", first=int(round(first_v)),
                                    last=int(round(last_v)), slope=trend["slope_per_week"])
                else:
                    delta_text = tr("history.trend_need_more")
            elif metric == "over":
                delta_text = tr("history.trend_simple_delta",
                                first=f"{first_v / 60.0:.1f}", last=f"{last_v / 60.0:.1f}")
            elif scale != 1.0 or decimals:
                # nove metriky 0.2: v tych istych jednotkach ako graf
                delta_text = tr("history.trend_simple_delta",
                                first=f"{first_v * scale:.{decimals}f}",
                                last=f"{last_v * scale:.{decimals}f}")
            else:
                delta_text = tr("history.trend_simple_delta",
                                first=int(round(first_v)), last=int(round(last_v)))
        elif raw_values:
            delta_text = tr("history.sessions_count", n=len(period_sessions))
        else:
            delta_text = tr("history.empty_period")
        self.history_trend_delta.configure(text=delta_text)

    def _refresh_history_page(self):
        """Prekresli trend, tabulku a postrehy z aktualnych suborov. Ked
        stranka este nie je postavena (prepnutie temy), nerobi nic."""
        box = getattr(self, "history_sessions_box", None)
        if box is None or not box.winfo_exists():
            return
        pal = self.pal
        # Len relacie aktualneho sveta (B3-worlds); detail je index do
        # PRAVE tohto zoznamu, preto ho `set_world` nuluje.
        sessions = self._world_sessions()
        note = getattr(self, "history_world_note", None)
        if note is not None:
            # Graf "ktora hlaska zabera" rata len herne hlasky, ktore
            # zazneli (viz `_refresh_cue_effect`) - veta to musi povedat,
            # inak by stranka s napisom "Svet: Praca" ukazovala herne hlasky
            # bez slova.
            note.configure(text=tr("history.world_note",
                                   world=self._world_label(self.world),
                                   chart=tr("history.effect_title")))
        self._refresh_history_trend()

        # tabulka
        for child in box.winfo_children():
            child.destroy()
        self.history_sessions_panel.set_right(tr("history.sessions_count", n=len(sessions)))
        if not sessions:
            ctk.CTkLabel(box, text=tr("history.empty"), font=ui_kit.ui(11),
                         text_color=pal["text_faint"], wraplength=620, anchor="w",
                         justify="left").pack(fill="x")
        else:
            cols = (("col_date", 118), ("col_duration", 62), ("col_avg", 66),
                    ("col_minmax", 84), ("col_over", 86), ("col_triggers", 70),
                    ("col_peak", 92), ("col_hrr", 52), ("col_hrpi", 52))
            head = ctk.CTkFrame(box, fg_color="transparent")
            head.pack(fill="x")
            for key, width in cols:
                ctk.CTkLabel(head, text=tr(f"history.{key}"), width=width, anchor="w",
                             font=ui_kit.ui(10, "bold"), text_color=pal["text_faint"]).pack(
                    side="left")
            ctk.CTkFrame(box, fg_color=pal["line_soft"], height=1, corner_radius=0).pack(fill="x")
            for poradie, s in enumerate(reversed(sessions)):
                if poradie >= self.HISTORY_ROWS:
                    break
                index = len(sessions) - 1 - poradie      # index do `sessions`
                vybrana = index == self._history_detail_index(sessions)
                row = ctk.CTkFrame(box, fg_color=pal["surface_alt"] if vybrana
                                   else "transparent")
                row.pack(fill="x")
                started = float(s.get("started") or 0)
                date = time.strftime("%d.%m.%Y %H:%M", time.localtime(started)) if started else "-"
                hrr = s.get("hrr_bpm")
                # Hlasky = to iste cislo ako detail, graf aj CSV: len tie,
                # ktore appka poslala sama (`hlasky_relacie`). Stare
                # `triggers` ratalo aj klavesu a tlacidlo "Test".
                hlasky = hr_stats.hlasky_relacie(s)
                cells = (date, self._fmt_minutes(s.get("duration_s")),
                         str(s.get("avg_bpm") or "-"),
                         f"{s.get('min_bpm') or '-'} / {s.get('max_bpm') or '-'}",
                         self._fmt_minutes(s.get("time_over_s")),
                         str(hlasky) if hlasky is not None else "-",
                         f"{s.get('peak_stress', 0)} %",
                         f"{int(hrr):+d}" if hrr is not None else "-",
                         str(s.get("hrpi") if s.get("hrpi") is not None else "-"))
                bunky = [row]
                for (key, width), text in zip(cols, cells):
                    label = ctk.CTkLabel(row, text=text, width=width, anchor="w",
                                         font=ui_kit.mono(10), text_color=pal["text"])
                    label.pack(side="left")
                    bunky.append(label)
                # Riadok je klikatelny: otvori tu istu relaciu v detaile
                # nad tabulkou. Bindovat treba aj kazdu bunku - klik na
                # popisok sa na ramec nepropaguje.
                for w in bunky:
                    try:
                        w.configure(cursor="hand2")
                    except Exception:
                        pass
                    # `_e=None`, nie `_e`: zhruba v kazdom druhom behu
                    # `gui_screenshots.py` sa tento handler zavolal BEZ
                    # udalosti a Tk to zapisalo ako chybu
                    # ("missing 1 required positional argument: '_e'").
                    # Kto ho takto vola, som NEODHALIL - viem len, ze sa to
                    # deje po scrollovani Historie, teda okolo prestavby
                    # riadkov v CTkScrollableFrame. Handler tu udalost
                    # nepouziva (potrebuje len `index`), takze nema dovod ju
                    # vyzadovat; tym chyba zmizne, ale PRICINA je stale
                    # neznama a nerobim, ze nie je.
                    w.bind("<Button-1>",
                           lambda _e=None, i=index: self._pick_history_session(i))
                ctk.CTkFrame(box, fg_color=pal["line_soft"], height=1,
                             corner_radius=0).pack(fill="x")

        self._refresh_history_rhythm(sessions)
        self._refresh_history_detail(sessions)
        self._refresh_cue_effect()
        self._refresh_rebrik_note(sessions)
        self._render_hr_insights()

    def _refresh_rebrik_note(self, sessions):
        """Jedna ticha veta pod grafom ucinnosti, ked je rebrik hlasky
        (`rebrik.py`) v zobrazenom svete POD vrcholom: co appka teraz robi,
        preco a kolko relacii chyba do dalsieho pokusu. Na vrchole nic -
        appka nema co vysvetlovat. `sessions` su relacie zobrazeneho sveta.
        """
        label = getattr(self, "history_rebrik_note", None)
        if label is None or not label.winfo_exists():
            return
        text = ""
        try:
            stav = rebrik.stupen(sessions, svet=self.world,
                                 styl=getattr(self, "cue_style", None))
            text = self._rebrik_veta(stav)
        except Exception:
            app_log.exception("historia: veta rebrika zlyhala")
        try:
            if text:
                label.configure(text=text)
                label.pack(fill="x", pady=(6, 0))
            else:
                label.pack_forget()
        except Exception:
            pass

    @staticmethod
    def _rebrik_veta(stav):
        """Veta pre stav rebrika, alebo "" na vrchole."""
        if not stav or stav.get("stupen") == stav.get("vrchol"):
            return ""
        dovod = stav.get("dovod")
        preco = (tr(f"history.rebrik.why.{dovod}")
                 if dovod in rebrik.DOVODY_POD_VRCHOLOM else "")
        kluc = ("history.rebrik.pause" if stav["stupen"] == rebrik.PAUZA
                else "history.rebrik.visual")
        # Bez dovodu (peciatka po orezani historie) by ostali dve medzery.
        return " ".join(tr(kluc, dovod=preco, n=stav.get("zostava", 0)).split())

    def _refresh_cue_effect(self):
        """Naplni graf "ktora hlaska zabera".

        Pocita sa LEN z hlasneho ramena (viz `measure.by_category`) - tiche
        okna su referencia pre to, ci hlaska funguje vobec, nie pre
        porovnanie kategorii medzi sebou.

        Od 0.2 (rebrik + brana) len hlasky, ktore naozaj zazneli, dorucene
        na pauze a z HRY - v praci je hlaska len obrazom. Ked uz su okna s
        branou, len tie (`measure.by_category`); veta pod grafom hovori, ze
        pokles po hlaske nie je dokaz.
        """
        graf = getattr(self, "history_effect", None)
        if graf is None or not graf.winfo_exists():
            return
        try:
            okna = measure.load_windows(self.hr_windows_path)
        except Exception:
            app_log.exception("graf ucinnosti: okna sa nepodarilo nacitat")
            okna = []
        podla = measure.by_category(okna)
        riadky = []
        # Poradie podla `measure.CATEGORIES`, nie podla toho, ktora ma
        # najviac okien - inak by sa riadky pri kazdom otvoreni presuvali.
        for kat in measure.CATEGORIES:
            udaj = podla.get(kat)
            if udaj is None:
                continue
            riadky.append((tr("cue.category.%s" % kat), udaj["n"],
                           udaj["delta_bpm"], udaj["ci95"], udaj["dost_dat"]))
        graf.set_data(riadky, malo_textu=tr("history.effect_few"))
        try:
            self.history_effect_hint.configure(
                text=tr("history.effect_hint") if riadky
                else tr("history.effect_empty"))
        except Exception:
            pass

    def export_sessions_csv(self):
        """Ulozi historiu relacii ako tabulku pre Excel.

        Data su hracove - appka mu ich nesmie drzat v JSON-e, ktory bezny
        clovek neotvori. CSV Excel otvori dvojklikom a appka na to
        nepotrebuje ziadnu kniznicu navyse (viz hr_stats.export_sessions_csv).

        Vzdy VSETKY relacie, z oboch svetov (B3-worlds) - su to jeho data.
        """
        sessions = self._history_sessions()
        if not sessions:
            messagebox.showinfo(APP_NAME, tr("history.export_empty"))
            return
        default = time.strftime("zanshin-relacie-%Y-%m-%d.csv")
        path = filedialog.asksaveasfilename(
            parent=self.root, title=tr("history.export_btn"),
            defaultextension=".csv", initialfile=default,
            filetypes=[(tr("history.export_filetype"), "*.csv")])
        if not path:
            return
        try:
            count = hr_stats.export_sessions_csv(
                sessions, path,
                headers=[tr(f"history.export_col.{key}")
                         for key in hr_stats.CSV_COLUMNS])
            dalsie = self._export_podrobnosti(path)
        except Exception as exc:
            app_log.exception("export relacii zlyhal")
            messagebox.showerror(APP_NAME, tr("history.export_failed", err=exc))
            return
        self.log(tr("log.sessions_exported", n=count))
        sprava = tr("history.export_done", n=count, path=os.path.basename(path))
        if dalsie:
            sprava += "\n\n" + tr("history.export_extra",
                                   files="\n".join(dalsie))
        messagebox.showinfo(APP_NAME, sprava)

    def _export_podrobnosti(self, path):
        """Vedla relacii ulozi aj meracie okna a udalosti. Vrati nazvy.

        PRECO TRI SUBORY A NIE JEDEN ZOSIT
        ----------------------------------
        Tri roviny dat maju rozne stlpce aj rozny pocet riadkov - do jednej
        tabulky sa nedaju. Excel s viacerymi harkami by znamenal `openpyxl`,
        teda dalsiu zavislost v builde; CSV appka zapise sama a Excel ho
        otvori dvojklikom. To bol dovod uz pri povodnom exporte relacii.

        Nazvy sa odvodia od suboru, ktory si hrac vybral, takze vsetky tri
        skoncia vedla seba a s rovnakym datumom.
        """
        zaklad, _pripona = os.path.splitext(path)
        # "zanshin-relacie-2026-09-18" -> "zanshin-okna-2026-09-18"
        okna_cesta = zaklad.replace("relacie", "okna") + ".csv"
        udal_cesta = zaklad.replace("relacie", "udalosti") + ".csv"
        if okna_cesta == path:
            okna_cesta = zaklad + "-okna.csv"
        if udal_cesta == path:
            udal_cesta = zaklad + "-udalosti.csv"

        von = []
        try:
            okna = measure.load_windows(self.hr_windows_path)
        except Exception:
            okna = []
        if okna and data_io.export_rows_csv(data_io.s_casom(okna), okna_cesta):
            von.append(os.path.basename(okna_cesta))

        udalosti = data_io.read_events(self.hr_events_path)
        if udalosti and data_io.export_rows_csv(data_io.s_casom(udalosti), udal_cesta):
            von.append(os.path.basename(udal_cesta))
        return von

    # ---------- pravidelnost a detail jednej relacie ----------

    def _history_detail_index(self, sessions):
        """Index relacie v detaile: vybrana, inak najnovsia, inak None."""
        if not sessions:
            return None
        index = self.history_detail_index
        if index is None or not 0 <= index < len(sessions):
            return len(sessions) - 1
        return index

    def _pick_history_session(self, index):
        self.history_detail_index = index
        self._refresh_history_page()

    def _refresh_history_rhythm(self, sessions):
        """Mriezka dni + pocet dni, v ktorych nejaka relacia bola."""
        grid = getattr(self, "history_daygrid", None)
        if grid is None or not grid.winfo_exists():
            return
        # Cely rok: mriezka si sama oreze zaciatok na to, co sa do jej sirky
        # zmesti (viz ui_kit.DayGrid), takze na sirsom paneli vidno viac.
        dni = hr_stats.day_activity(sessions, days=371)
        grid.set_days(dni, legend=(tr("history.grid_less"), tr("history.grid_more")))
        # Cislo samo, jednotka je v popisku nad nim ("Dní s reláciou · rok").
        # Slovencina sklonuje "deň/dni/dní" podla poctu a appka ma vela
        # jazykov - cislo bez podstatneho mena je spravne v kazdom z nich.
        aktivne = sum(1 for den in dni if den.get("count"))
        self.history_days_value.configure(text=str(aktivne) if aktivne else "—")

    def _refresh_history_detail(self, sessions):
        """Krivka a cisla jednej relacie - z `curve` ulozenej v suhrne.

        Relacie z predoslych verzii krivku nemaju (pole pribudlo neskor);
        vtedy sa panel neschova, len ukaze, ze tvar tejto relacie sa uz
        dopocitat neda - zahodene surove vzorky sa spatne nevytvoria.
        """
        trace = getattr(self, "history_detail_trace", None)
        if trace is None or not trace.winfo_exists():
            return
        index = self._history_detail_index(sessions)
        session = sessions[index] if index is not None else None
        if not session:
            trace.set_trace([])
            self.history_detail_panel.set_right("")
            for cell in self.history_detail_cells.values():
                cell.configure(text="—")
            self.history_detail_hint.configure(text=tr("history.detail_empty"))
            return
        started = float(session.get("started") or 0)
        self.history_detail_panel.set_right(
            time.strftime("%d.%m.%Y %H:%M", time.localtime(started)) if started else "")
        curve = session.get("curve") or []
        # `activity_curve` pribudla neskor - starsie relacie ju nemaju a
        # vtedy sa pruh proste nekresli (viz `SessionTrace._draw_activity`).
        trace.set_trace(curve, baseline=session.get("baseline_bpm"),
                        threshold=session.get("critical_bpm"),
                        duration_s=session.get("duration_s") or 0,
                        triggers=session.get("trigger_offsets_s") or [],
                        activity=session.get("activity_curve") or ())
        hodnoty = self._history_detail_values(session)
        for key, cell in self.history_detail_cells.items():
            cell.configure(text=hodnoty.get(key, "—"))
        self.history_detail_hint.configure(
            text=tr("history.detail_hint") if curve else tr("history.detail_no_curve"))

    def _history_detail_values(self, session):
        """{kluc bunky: text} pre VSETKY bunky detailu jednej relacie.

        Co relacia nema (stara verzia, import, preskoceny dotaznik), je "—",
        nie nula - "nevieme" a "nic" su dve rozne vypovede.
        """
        def cislo(key):
            v = session.get(key)
            return str(v) if v not in (None, "") else "—"

        hrr = session.get("hrr_bpm")
        try:
            hrr_text = f"{int(hrr):+d}" if hrr is not None else "—"
        except (TypeError, ValueError):
            hrr_text = "—"
        calm = hr_stats.cas_v_pokoji_s(session)
        hlasky = hr_stats.hlasky_relacie(session)
        pokrytie = hr_stats.pokrytie_signalu(session)
        par = hr_stats.citene_a_merane(session)
        duration = session.get("duration_s")
        over = session.get("time_over_s")
        return {
            "duration": self._fmt_dlzka(duration) if duration else "—",
            "avg": cislo("avg_bpm"),
            "max": cislo("max_bpm"),
            "calm": ("—" if calm is None
                     else tr("dashboard.fmt.min", n=int(calm // 60))),
            "over": self._fmt_minutes(over) if over is not None else "—",
            "breath": str(hlasky) if hlasky is not None else "—",
            "peak": cislo("peak_stress"),
            "hrr": hrr_text,
            "hrpi": cislo("hrpi"),
            "signal": self._fmt_pokrytie(pokrytie),
            "felt": self._fmt_citene_merane(par),
        }

    @staticmethod
    def _fmt_dlzka(seconds):
        """Dlzka "45 min" alebo "1 h 05 min" - karta "Dĺžka relácie" aj
        detail relacie v Historii. Pokazena hodnota -> "—"."""
        try:
            total_min = int(max(0.0, float(seconds or 0.0)) // 60)
        except (TypeError, ValueError, OverflowError):
            return "—"
        hodiny, minuty = divmod(total_min, 60)
        if hodiny:
            return tr("dashboard.fmt.h_min", h=hodiny, m=f"{minuty:02d}")
        return tr("dashboard.fmt.min", n=minuty)

    @staticmethod
    def _fmt_pokrytie(pokrytie):
        """Pokrytie signalu 0..1 -> "97 %", None -> "—"."""
        if pokrytie is None:
            return "—"
        return tr("dashboard.fmt.pct", n=int(round(float(pokrytie) * 100)))

    @staticmethod
    def _fmt_citene_merane(par):
        """(citene, merane) -> "6 · 8"; bez dotaznika "—". Dve cisla vedla
        seba, ziadny rozdiel ani sipka - ktore je "spravne", appka nevie."""
        if par is None:
            return "—"
        citene, merane = par
        return f"{citene} · {'—' if merane is None else merane}"

    def _render_hr_insights(self):
        box = getattr(self, "history_insights_box", None)
        if box is None or not box.winfo_exists():
            return
        pal = self.pal
        for child in box.winfo_children():
            child.destroy()
        running = getattr(self, "_hr_analysis_thread", None) is not None \
            and self._hr_analysis_thread.is_alive()
        if running and not self._hr_insights:
            ctk.CTkLabel(box, text=tr("history.analysis_running"), font=ui_kit.ui(11),
                         text_color=pal["text_faint"], anchor="w").pack(fill="x")
        tone_color = {"good": pal["success"], "watch": pal["warn"], "info": pal["accent"]}
        for item in self._hr_insights:
            params = item.get("params") or {}
            try:
                text = tr(f"insight.{item.get('key')}", **params)
            except Exception:
                text = str(item.get("key"))
            farba = tone_color.get(item.get("tone"), pal["accent"])
            row = ctk.CTkFrame(box, fg_color="transparent")
            row.pack(fill="x", pady=2)
            # height=8: CTkFrame ma predvolenu ziadanu vysku 200 px a riadok
            # by sa natiahol na nu; takto prúžok len vyplni vysku textu
            ctk.CTkFrame(row, fg_color=farba, width=3, height=8,
                         corner_radius=0).pack(side="left", fill="y", padx=(0, 10))
            ctk.CTkLabel(row, text=text, font=ui_kit.ui(11), text_color=pal["text"],
                         wraplength=600, anchor="w", justify="left").pack(side="left", fill="x",
                                                                          expand=True)
            # "0 z 3 relácií" je stav postupu, nie postreh - bodky ho
            # povedia skor, nez sa veta docita.
            if item.get("key") == "need_more":
                dots = ctk.CTkFrame(row, fg_color="transparent")
                dots.pack(side="right", padx=(10, 0))
                hotovo = int(params.get("n", 0) or 0)
                treba = int(params.get("need", 0) or 0)
                for i in range(treba):
                    ctk.CTkFrame(dots, width=8, height=8, corner_radius=4,
                                 fg_color=farba if i < hotovo else pal["switch_off"]
                                 ).pack(side="left", padx=2)
            elif params.get("delta") is not None:
                # Rozdiel, o ktorom postreh hovori, ako cislo - veta
                # povie preco, cislo povie kolko.
                ctk.CTkLabel(row, text=f"{int(params['delta']):+d}",
                             font=ui_kit.mono(12), text_color=farba,
                             anchor="e").pack(side="right", padx=(10, 0))
        stamp = self._hr_insights_at
        if stamp:
            self.history_insights_panel.set_right(tr(
                "history.analysis_stamp",
                when=time.strftime("%d.%m. %H:%M", time.localtime(stamp))))
        else:
            # Po prepnuti sveta sa postrehy zahodia - cas analyzy druheho
            # sveta by pri nich klamal.
            self.history_insights_panel.set_right("")

    # ---------- analyza historie na pozadi ----------

    def run_hr_analysis(self, *_):
        """Spusti hr_insights.analyze() v samostatnom vlakne - nie na GUI
        vlakne (historia moze mat desiatky relacii a analyza nesmie
        zaseknut okno). Vysledok sa zapise do hr_insights.json a do UI sa
        dostane cez ui_call. Bezi po starte, po kazdej ulozenej relacii,
        po prepnuti sveta a na tlacidlo 'Prepocitat'.

        Postrehy su za JEDEN svet - ten, ktory platil pri spusteni
        (B3-worlds). Ked uz analyza bezi, nova sa neodmietne potichu:
        zapise sa `_hr_analysis_rerun` a po dobehnuti bezucej sa spusti
        znova (viz `_po_analyze`). Inak by po rychlom prepnuti sveta
        ostali na obrazovke postrehy druheho sveta."""
        existing = getattr(self, "_hr_analysis_thread", None)
        if existing is not None and existing.is_alive():
            self._hr_analysis_rerun = True
            return
        self._hr_analysis_rerun = False
        world = self.world
        sessions_path, insights_path = self.hr_sessions_path, self.hr_insights_path

        def work():
            try:
                sessions = hr_stats.sessions_in_world(
                    hr_stats.load_sessions(sessions_path), world)
                insights = hr_insights.analyze(sessions)
                hr_insights.save_insights(insights_path, insights,
                                          log=self.log_threadsafe, world=world)
            except Exception as exc:
                app_log.exception("HR analyza zlyhala")
                self.log_threadsafe(f"HR analysis failed: {exc}")
                self.ui_call(lambda: self._po_analyze(world))
                return
            self.ui_call(lambda: self._apply_hr_insights(insights, world))

        self._hr_analysis_thread = threading.Thread(target=work, daemon=True,
                                                    name="hr-analysis")
        self._hr_analysis_thread.start()
        self._render_hr_insights()

    def _apply_hr_insights(self, insights, world=None):
        """Vysledok analyzy do UI - len ked je za AKTUALNY svet.

        Vysledok za iny svet (prepnuty pocas analyzy) sa zahodi a analyza
        sa spusti znova. `world=None` = volajuci svet nepozna, berie sa."""
        if world is None or world == self.world:
            self._hr_insights = list(insights or [])
            self._hr_insights_at = time.time()
        self._po_analyze(world)
        self._render_hr_insights()

    def _po_analyze(self, world):
        """Dobehla analyza (aj neuspesna). Treba ju zopakovat?

        Ano, ked medzitym niekto poziadal o novu (`_hr_analysis_rerun`) alebo
        ked bola za iny svet, nez aky plati teraz."""
        if self._hr_analysis_rerun or (world is not None and world != self.world):
            self._hr_analysis_rerun = False
            self._naplanuj_analyzu()

    def _naplanuj_analyzu(self):
        """Spusti analyzu, AZ KED dobehne bezuce vlakno.

        `_apply_hr_insights` prichadza cez `ui_call` zvnutra vlakna, takze
        vlakno moze byt v tej chvili este nazive - priame `run_hr_analysis`
        by sa odmietlo a poziadavka by sa stratila. Caka sa preto po 100 ms;
        naplanovane je najviac jedno cakanie naraz."""
        if getattr(self, "_hr_rerun_job", None) is not None:
            return
        vlakno = getattr(self, "_hr_analysis_thread", None)
        if vlakno is not None and vlakno.is_alive():
            def znova():
                self._hr_rerun_job = None
                self._naplanuj_analyzu()
            try:
                self._hr_rerun_job = self.root.after(100, znova)
            except Exception:
                self._hr_rerun_job = None
            return
        self.run_hr_analysis()

    def _build_spustace_page(self, page, pal):
        """Spustace: profil, jeho zdielanie, a mapa spustacov.

        Stranka sa uz nevola "Profily" - profil je mechanizmus, spustac je
        to, co pouzivatel naozaj nastavuje. Profil ostava, len prestal byt
        nazvom celej stranky.
        """
        # JEDEN SCROLL NA CELU STRANKU.
        #
        # Do 18. 9. scrolloval len zoznam slotov (vnoreny CTkScrollableFrame)
        # a zvysok stranky stal. Malo to dve nevyhody: pod sloty sa nedalo
        # nic dat (vysvetlivky, teoria), a `before=self.slots_container`
        # padalo na TclError, lebo zlozeny widget nie je spravovany packom -
        # tichá chyba, ktorá sa len zapísala do crash.log.
        #
        # Teraz scrolluje celok a `slots_container` je obycajny ramec, ktory
        # `rebuild_slots` bez problemu vyprazdni.
        wrap = ctk.CTkScrollableFrame(
            page, fg_color="transparent",
            scrollbar_button_color=pal["surface_alt"],
            scrollbar_button_hover_color=pal["accent"])
        wrap.pack(fill="both", expand=True, padx=24, pady=(20, 20))
        self.spustace_scroll = wrap

        ctk.CTkLabel(wrap, text=tr("slots.title"), font=ui_kit.ui(17, "bold"),
                     text_color=pal["text"], anchor="w").pack(fill="x")
        ctk.CTkLabel(wrap, text=tr("slots.hint"), font=ui_kit.ui(11),
                     text_color=pal["text_faint"], wraplength=680, anchor="w",
                     justify="left").pack(fill="x", pady=(3, 0))

        self._build_citlivost_card(wrap, pal)

        # --- lista profilu ---
        bar = ctk.CTkFrame(wrap, fg_color=pal["surface"], corner_radius=ui_kit.RADIUS_CONTROL,
                           border_width=1, border_color=pal["line_soft"])
        bar.pack(fill="x", pady=(16, 14))
        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=11)

        self.profile_var = tk.StringVar(value=self.active_profile_name)
        self.profile_switch = ctk.CTkOptionMenu(
            inner, values=[p["name"] for p in self.profiles],
            variable=self.profile_var, width=168, height=28, corner_radius=ui_kit.RADIUS_CONTROL,
            fg_color=pal["surface_alt"], button_color=pal["accent2"],
            button_hover_color=pal["accent2_hover"], text_color=pal["text"],
            dropdown_fg_color=pal["surface"], dropdown_text_color=pal["text"],
            font=ui_kit.ui(12), command=self.on_profile_switch)
        self.profile_switch.pack(side="left", padx=(0, 6))

        for text, command in ((tr("profile.new"), self.new_profile_dialog),
                              (tr("profile.delete"), self.delete_current_profile),
                              (tr("profile.export"), self.export_profile_code),
                              (tr("profile.import"), self.import_profile_dialog)):
            ui_kit.chip(inner, pal, text, command).pack(side="left", padx=3)

        self.auto_profile_var = tk.BooleanVar(value=self.auto_profile_enabled)
        auto_text = tr("settings.auto_profile") if PSUTIL_AVAILABLE \
            else tr("settings.auto_profile_unavailable")
        # Vlastny riadok pod profilmi: veta pod prepinacom povie, ktore hry
        # appka pozna, ze sama spusti aj zastavi pocuvanie a ze vypnuta
        # procesy necita - vedla styroch tlacidiel profilu by sa nezmestila.
        auto_row = ctk.CTkFrame(bar, fg_color="transparent")
        auto_row.pack(fill="x", padx=14, pady=(0, 11))
        auto_switch = ctk.CTkSwitch(auto_row, text=auto_text, variable=self.auto_profile_var,
                                    progress_color=pal["accent2"],
                                    fg_color=pal["switch_off"],
                                    button_hover_color=pal["accent_hover"],
                                    text_color=pal["text_dim"], font=ui_kit.ui(11),
                                    command=self.on_auto_profile_toggle)
        auto_switch.pack(anchor="w")
        if not PSUTIL_AVAILABLE:
            auto_switch.configure(state="disabled")
        else:
            ctk.CTkLabel(auto_row, text=tr("settings.auto_profile_sub",
                                           games=self._zname_hry()),
                         font=ui_kit.ui(10), text_color=pal["text_faint"],
                         wraplength=640, anchor="w", justify="left").pack(
                fill="x", pady=(4, 0))

        # --- mapa spustacov ---
        # FAZA 3: legenda tlacidiel gamepadu (A=X, B=O, ...) tu bola preto,
        # ze sa tlacidlom dala spustit hlaska. Uz sa neda - ovladac len
        # hlasi, ze je hrac aktivny. Kluc `slots.gamepad_hint` v i18n
        # ostava, kym sa stranka vo faze 5 neprekresli.
        #
        # TLACIDLO "+ Pridat spustac" TU UZ NIE JE (0.2). Hlasky maju pevne
        # styri kategorie (Tazisko, Celust, Uvolnenie, Dych) - kazda so svojim
        # vizualom v hre. Piaty a dalsi slot nemal vizual ani kategoriu, takze
        # `_dalsi_cue_slot` ho preskakoval a sam od seba nezaznel nikdy; log
        # pritom hracovi slubil, ze "kedy sa ozve, rozhoduje appka sama".
        # Stare nastavenia s viac nez styrmi slotmi sa nacitaju dalej (nic sa
        # nemaze) - navyse sloty zaznia len cez tlacidlo Test.

        # --- lista hromadneho vyberu (skryta, kym nie je nic oznacene) ---
        # Objavi sa az ked hrac zaskrtne aspon jeden slot - inak by nad
        # zoznamom trvalo visel prazdny pruh. Odstranenie viacerych slotov
        # naraz je jedna akcia s jednym potvrdenim, nie klikanie po jednom.
        self.bulk_bar = ctk.CTkFrame(wrap, fg_color=pal["surface_alt"],
                                     corner_radius=ui_kit.RADIUS_CONTROL, border_width=1,
                                     border_color=pal["line_soft"], height=44)
        self.bulk_bar.pack_propagate(False)
        bulk_inner = ctk.CTkFrame(self.bulk_bar, fg_color="transparent")
        bulk_inner.pack(fill="both", expand=True, padx=14, pady=6)
        self.bulk_label = ctk.CTkLabel(bulk_inner, text="", font=ui_kit.ui(12),
                                       text_color=pal["text"], anchor="w")
        self.bulk_label.pack(side="left")
        ctk.CTkButton(bulk_inner, text=tr("slots.remove_selected"), height=28,
                      corner_radius=ui_kit.RADIUS_CONTROL, fg_color="transparent", border_width=1,
                      border_color=pal["danger"], hover_color=pal["danger"],
                      text_color=pal["text"], font=ui_kit.ui(11),
                      command=self.remove_selected_slots).pack(side="right")
        ctk.CTkButton(bulk_inner, text=tr("slots.clear_selection"), height=28,
                      corner_radius=ui_kit.RADIUS_CONTROL, fg_color="transparent", border_width=1,
                      border_color=pal["line_soft"], hover_color=pal["surface"],
                      text_color=pal["text_dim"], font=ui_kit.ui(11),
                      command=self.clear_slot_selection).pack(side="right", padx=(0, 8))
        # zabalene NEbude - pack az v _on_slot_selection_change

        # Kotva, pred ktoru sa lista vklada. `before=` musi ukazovat na
        # widget, ktory JE spravovany packom - a CTkScrollableFrame nim nie
        # je: navonok je to zlozeny widget a packnuty je az jeho vnutorny
        # ramec. `before=self.slots_container` preto vyhodilo TclError a
        # lista sa nezobrazila nikdy (chyba sa len ticho zapisala do
        # crash.log, appka bezala dalej).
        self._bulk_anchor = ctk.CTkFrame(wrap, fg_color="transparent", height=0)
        self._bulk_anchor.pack(fill="x")

        self.slots_container = ctk.CTkFrame(wrap, fg_color="transparent")
        self.slots_container.pack(fill="x", pady=(10, 0))
        active_profile = next(
            (p for p in self.profiles if p["name"] == self.active_profile_name),
            self.profiles[0])
        self.rebuild_slots(active_profile["slots"])

        # VYSVETLIVKY A TEORIA PATRIA SEM, nie o dve karty dalej.
        # Clovek ich hlada prave vtedy, ked cita, co ktora hlaska hovori -
        # "preco zrovna celust" sa pyta pri celusti.
        ctk.CTkFrame(wrap, fg_color=pal["line_soft"], height=1,
                     corner_radius=0).pack(fill="x", pady=(22, 0))
        self._build_guide_into(wrap, pal)

    def _build_zvuk_page(self, page, pal):
        """Zvuk: hlas (kto hovori, akym hlasom, ako rychlo), hlasitost
        (+ pomer zvuk/hlas) a casovanie (pauza, prekryvanie).

        Toto bola jedina stranka nastaveni, ktora redizajn prezila
        nezmenena: hola mriezka `CTkLabel` + slider, bez jedineho
        vysvetlenia a bez rozdelenia do skupin. Pritom prave tu su volby,
        ktorym nazov nestaci - "Pomer zvuk ↔ hlas" ani "Hlášky sa môžu
        prekrývať" sa z dvoch slov pochopit nedaju. Teraz je z nej
        `ui_kit.SettingRow` ako zo zvysku appky (nazov, veta pod nim,
        ovladac vpravo) v troch panelocch, a na konci tlacidlo, ktore to
        da naozaj pocut - hlas sa podla nazvu vybrat neda.
        """
        wrap = ctk.CTkScrollableFrame(
            page, fg_color="transparent", scrollbar_button_color=pal["surface_alt"],
            scrollbar_button_hover_color=pal["accent"])
        wrap.pack(fill="both", expand=True, padx=24, pady=(20, 20))
        self.zvuk_scroll = wrap

        # Vysvetlenia maju na tejto stranke vela miesta (ovladace su uzke),
        # takze sirsi zlom nez predvolenych 430 - inak by kazda veta bola
        # na tri riadky a stranka dvojnasobne dlha.
        WRAP = 560

        def _slider(parent, **kw):
            """Slider + popisok hodnoty vpravo od neho. Koliesko je zamerne
            zablokovane: stranka sa posuva a bez toho by rolovanie menilo
            hodnotu, nad ktorou prave stoji kurzor."""
            box = ctk.CTkFrame(parent, fg_color="transparent")
            slider = ui_kit.block_slider_wheel(ctk.CTkSlider(
                box, width=150, progress_color=pal["accent"], button_color=pal["accent"],
                button_hover_color=pal["accent_hover"], **kw))
            slider.pack(side="left")
            return box

        def _hodnota(box, text):
            """Popisok hodnoty. Sirsi, nez by cislo potrebovalo - je v nom
            aj slovo ("vyvazene", "pomaly"), lebo holé "5.0 s" nepovie,
            ci je to vela alebo malo."""
            label = ctk.CTkLabel(box, text=text, text_color=pal["text_dim"], width=132,
                                 font=ui_kit.ui(11), anchor="w")
            label.pack(side="left", padx=(10, 0))
            return label

        # --- ako sa ozyvam (styl hlasky, 0.2) ---
        # Ta ista otazka ako v 5. kroku onboardingu, s tymi istymi vetami.
        # Je navrchu: rozhoduje, ci zo vsetkeho pod nou v hre vobec nieco
        # zaznie. "Neviem" tu nie je - v onboardingu znamena hlas.
        styl_panel = ui_kit.Panel(wrap, pal)
        styl_panel.pack(fill="x")
        row = ui_kit.SettingRow(styl_panel.body, pal, tr("settings.cue_style"),
                                tr("settings.cue_style_sub"), wrap=WRAP)
        self.cue_style_var = tk.StringVar(
            value=self._cue_style_label(getattr(self, "cue_style", None)))
        ctk.CTkOptionMenu(
            row.control, values=self._cue_style_labels(),
            variable=self.cue_style_var, width=250, height=28,
            corner_radius=ui_kit.RADIUS_CONTROL, fg_color=pal["surface_alt"],
            button_color=pal["accent2"], button_hover_color=pal["accent2_hover"],
            text_color=pal["text"], dropdown_fg_color=pal["surface"],
            dropdown_text_color=pal["text"], font=ui_kit.ui(12),
            command=self._on_cue_style_label).pack()

        # --- hlas ---
        voice_panel = ui_kit.Panel(wrap, pal, title=tr("settings.audio_voice_title"))
        voice_panel.pack(fill="x", pady=(14, 0))

        row = ui_kit.SettingRow(voice_panel.body, pal, tr("settings.engine"),
                                tr("settings.engine_sub"), wrap=WRAP)
        self.engine_var = tk.StringVar(value=engine_labels()[self.engine])
        self.engine_box = ctk.CTkOptionMenu(
            row.control, values=[engine_labels()[ENGINE_EDGE], engine_labels()[ENGINE_SAPI]],
            variable=self.engine_var, width=250, height=28,
            corner_radius=ui_kit.RADIUS_CONTROL, fg_color=pal["surface_alt"],
            button_color=pal["accent2"], button_hover_color=pal["accent2_hover"],
            text_color=pal["text"], dropdown_fg_color=pal["surface"],
            dropdown_text_color=pal["text"], font=ui_kit.ui(12),
            command=lambda _v: self.on_engine_change())
        self.engine_box.pack()
        # Stav pripravy Edge hlasok - patri pod prepinac motora, nie vedla
        # neho: je to hlaska o priebehu, nie dalsie nastavenie.
        self.edge_status_label = ctk.CTkLabel(
            voice_panel.body, text="", font=ui_kit.ui(10), text_color=pal["text_dim"],
            anchor="w", justify="left", wraplength=520)
        self.edge_status_label.pack(fill="x", pady=(6, 0))

        row = ui_kit.SettingRow(voice_panel.body, pal, tr("settings.voice"),
                                tr("settings.voice_sub"), wrap=WRAP)
        self.voice_var = tk.StringVar()
        self.voice_box = ctk.CTkOptionMenu(
            row.control, values=[tr("voice.loading")], variable=self.voice_var,
            width=250, height=28, corner_radius=ui_kit.RADIUS_CONTROL,
            fg_color=pal["surface_alt"], button_color=pal["accent2"],
            button_hover_color=pal["accent2_hover"], text_color=pal["text"],
            dropdown_fg_color=pal["surface"], dropdown_text_color=pal["text"],
            font=ui_kit.ui(12), command=lambda _v: self.on_voice_change())
        self.voice_box.pack()

        row = ui_kit.SettingRow(voice_panel.body, pal, tr("settings.rate"),
                                tr("settings.rate_sub"), wrap=WRAP)
        self.rate_var = tk.IntVar(value=self.rate_value)
        box = _slider(row.control, from_=-10, to=10, number_of_steps=20,
                      variable=self.rate_var, command=lambda _v: self.on_rate_change())
        self.rate_value_label = _hodnota(box, self._rate_label_text())
        box.pack()

        # --- hlasitost ---
        loud_panel = ui_kit.Panel(wrap, pal, title=tr("settings.audio_volume_title"))
        loud_panel.pack(fill="x", pady=(14, 0))

        row = ui_kit.SettingRow(loud_panel.body, pal, tr("settings.volume"),
                                tr("settings.volume_sub"), wrap=WRAP)
        self.volume_var = tk.IntVar(value=self.volume_value)
        box = _slider(row.control, from_=0, to=100, number_of_steps=100,
                      variable=self.volume_var, command=lambda _v: self.on_volume_change())
        self.volume_value_label = _hodnota(box, f"{self.volume_value} %")
        box.pack()

        row = ui_kit.SettingRow(loud_panel.body, pal, tr("settings.balance"),
                                tr("settings.balance_sub"), wrap=WRAP)
        self.balance_var = tk.IntVar(value=self.balance_value)
        box = _slider(row.control, from_=0, to=100, number_of_steps=100,
                      variable=self.balance_var, command=lambda _v: self.on_balance_change())
        self.balance_value_label = _hodnota(box, self._balance_label_text())
        box.pack()

        # Veta pod ukazkou ide za stylom hlasky - prepisuje ju aj volba
        # "Ako sa ozyvam" vyssie (`_nastav_styl_hlasky`).
        row = ui_kit.SettingRow(loud_panel.body, pal, tr("settings.preview"),
                                self._preview_sub_text(), wrap=WRAP)
        self.preview_sub_label = row.sub_label
        ui_kit.chip(row.control, pal, tr("settings.preview_btn"),
                    self.preview_sound, width=130).pack()

        # POZN: tu bol panel "Casovanie" s posuvnikom "Pauza medzi
        # pripomienkami" (0,2-30 s) a prepinacom "Hlasky sa mozu prekryvat".
        #
        # Boli to najvacsie ovladace v sekcii a slubovali presne to, co hrac
        # hlada - "kratka pauza pripomina casto, dlha ta necha hrat". Na
        # automaticku hlasku pritom nemali ziadny vplyv: odstup medzi
        # hlaskami riesi `trigger.params["min_gap_s"]`, ktory ma tvrdu
        # podlahu 210 s, cize sedemnasobok maxima toho posuvnika. Hrac si
        # myslel, ze appku vyladil, a nezmenil nic - a este si aj protirecil
        # s volbou "Ako casto sa ozvem", ktora to robi naozaj.
        #
        # Obe hodnoty ostavaju ako konstanty pre RUCNE spustenie (tlacidlo
        # Test, klik v HUD nahlade), kde davaju zmysel a nikto ich nemusi
        # nastavovat.

        # --- vratit odporucane ---
        # Posuvniky sa daju zakrutit do stavu, z ktoreho sa clovek sam
        # nedostane (hlasitost 3 %, pauza 30 s) a nevie, co bolo povodne.
        # Jedno tlacidlo, ziadne "naozaj?" - vsetkych pat hodnot je vidno
        # hned nad nim a spat sa daju posunut rukou.
        reset_panel = ui_kit.Panel(wrap, pal)
        reset_panel.pack(fill="x", pady=(14, 0))
        row = ui_kit.SettingRow(reset_panel.body, pal, tr("settings.audio_reset"),
                                tr("settings.audio_reset_sub"), wrap=WRAP)
        ui_kit.chip(row.control, pal, tr("settings.audio_reset_btn"),
                    self.reset_audio_settings, width=130).pack()

    def _rate_label_text(self):
        """Rychlost reci ako "+3 · rýchlo". Holé číslo -10..10 nepovie ani
        smer, ani co znamena - znamienko a slovo áno."""
        value = self.rate_value
        if value <= -3:
            slovo = tr("settings.speed_slow")
        elif value >= 3:
            slovo = tr("settings.speed_fast")
        else:
            slovo = tr("settings.speed_normal")
        return f"{value:+d} · {slovo}" if value else f"0 · {slovo}"


    def reset_audio_settings(self):
        """Vrati hlasitost, pomer, rychlost, pauzu a prekryvanie na
        odporucane hodnoty (`settings_model.DEFAULT_AUDIO`).

        Hlas ani motor sa nemenia - to nie je pokazene nastavenie, ale
        volba, a prepisat ju pod rukou by bolo prekvapenie, nie pomoc.
        """
        self.volume_var.set(DEFAULT_AUDIO["volume"])
        self.on_volume_change()
        self.balance_var.set(DEFAULT_AUDIO["balance"])
        self.on_balance_change()
        self.rate_var.set(DEFAULT_AUDIO["rate"])
        self.on_rate_change()
        self.log(tr("log.audio_reset"))

    # Veta pod "Ako to znie" podla stylu hlasky (rozhodnutie 24. 9.).
    PREVIEW_SUB = {rebrik.STYL_HLAS: "settings.preview_sub",
                   rebrik.STYL_ZVUK: "settings.preview_sub_sound",
                   rebrik.STYL_OBRAZ: "settings.preview_sub_visual"}

    def _preview_sub_text(self):
        """Co ukazka naozaj urobi - podla stylu, ktory si hrac vybral."""
        styl = rebrik.normalize_cue_style(getattr(self, "cue_style", None))
        return tr(self.PREVIEW_SUB[styl])

    def preview_sound(self):
        """Prehra prvu zapnutu pripomienku tak, ako sa v hre ozve vo
        zvolenom STYLE hlasky (`cue_style`, rozhodnutie 24. 9.):

          * hlas   - `_emit` so zvukom aj slovami, bez vizualu (ako doteraz);
          * zvuk   - zvuk slotu a jeho obrazok, ziadne slova (`bez_slov`);
          * obraz  - nic nezaznie, len obrazok.
        Predtym zaznel hlas vzdy - aj hracovi, ktory si vybral "len obrazok,
        nic nehovor", a veta pod tlacidlom mu slubovala, ze presne tak to
        znie v hre.

        Hlas sa podla nazvu vybrat neda: "Prirodzený hlas (Edge)" a "Hlas
        z Windows" su dve vety, ktore o vysledku nepovedia nic, a to iste
        plati pre hlasitost aj pomer zvuk/hlas. Pusta sa `_emit` s
        realnym slotom (nie `fire_slot`), takze sa ukazka NEpocita do
        relacie.
        """
        styl = rebrik.normalize_cue_style(getattr(self, "cue_style", None))
        if styl == rebrik.STYL_HLAS:
            slot = next((s for s in self.slots if s.enabled_value), None)
            if slot is None and self.slots:
                slot = self.slots[0]
            if slot is None:
                return
            threading.Thread(target=self._emit, args=(slot,), daemon=True).start()
            return
        # Zvuk aj obraz: obrazok je v tychto styloch cela hlaska (alebo jej
        # polovica), tak ho ukazka ukaze. Bezi to na Tk vlakne (klik).
        # Slot sa berie ako v hre (`_dalsi_cue_slot`): zapnuty A so zapnutym
        # obrazkom v hre. Prvy zapnuty slot bez obrazka by po kliku neukazal
        # nic a v "len obrazok" ani nic neprehral - tlacidlo by mlcalo a veta
        # pod nim by slubovala obrazok.
        slot = next((s for s in self.slots
                     if s.enabled_value and self._ma_obrazok_v_hre(s)), None)
        if slot is None:
            # V hre by sa v tomto style neozvala vobec (`_dalsi_cue_slot`
            # vrati None) - povie sa to narovinu, nie tichym klikom.
            self.log(tr("log.preview_no_picture"))
            return
        try:
            self.overlay_manager.trigger(slot.index)
        except Exception:
            app_log.exception("ukazka: obrazok sa nepodarilo ukazat")
        if styl == rebrik.STYL_ZVUK:
            threading.Thread(target=self._emit, args=(slot,),
                             kwargs={"bez_slov": True}, daemon=True).start()

    def _ma_obrazok_v_hre(self, slot):
        """Ma slot zapnuty obrazok v hre? Ta ista podmienka ako v
        `_dalsi_cue_slot` - bez nej sa hlaska v hre vobec nedoruci."""
        try:
            return bool(self.overlay_configs[int(slot.index)]["enabled"])
        except (AttributeError, IndexError, KeyError, TypeError, ValueError):
            return False

    def _build_vhre_page(self, page, pal):
        """Hodinky: sparovat a vidiet, co z toho appka kresli do hry.

        Do 18. 9. tu bolo VSETKO, co appka pocas hrania robi - ikonky
        funkcii, vyber obrazovky, jazyk v hre, panel s tepom aj vysvetlenie
        anti-cheatu. Bolo to sest sekcii pod sebou a karta, kvoli ktorej sem
        clovek chodi - sparovanie hodiniek - sa v nich stratila.

        Ostali dve veci, a obe su o tom istom: senzor a to, co z neho vidno
        na obrazovke. Zvysok si sadol do Vseobecnych nastaveni zabaleny
        (`_build_ingame_sections_into`) - su to veci, ktore clovek nastavi
        raz a uz sa k nim nevracia.
        """
        scroll = ctk.CTkScrollableFrame(
            page, fg_color="transparent", scrollbar_button_color=pal["surface_alt"],
            scrollbar_button_hover_color=pal["accent"])
        scroll.pack(fill="both", expand=True, padx=24, pady=(20, 20))
        self.vhre_scroll = scroll

        # Sparovanie je prve: bez hodiniek nema widget co kreslit.
        self._build_heart_rate_card(scroll, pal, pady=(0, 0))

        # --- vizualy slotov ---
        vis_panel = ui_kit.Panel(scroll, pal, title=tr("overlay.dialog_title"))
        vis_panel.pack(fill="x", pady=(14, 0))
        ctk.CTkLabel(vis_panel.body, text=tr("overlay.drag_hint"), font=ui_kit.ui(10),
                     text_color=pal["text_faint"], wraplength=440, anchor="w",
                     justify="left").pack(fill="x", pady=(0, 8))
        self.vhre_vis_switches = []
        self.vhre_test_buttons = {}
        for index in range(4):
            cfg = self.overlay_configs[index]
            # emoji ide do stlpca pevnej sirky, inak nazvy zacinaju kazdy
            # inde (emoji maju rozne sirky) a prepinace vyzeraju "mimo"
            raw = tr(f"overlay.slot.{index}")
            icon, _, title = raw.partition(" ")
            if not title:
                icon, title = "", raw
            row = ui_kit.SettingRow(vis_panel.body, pal, title, icon=icon)
            if index == 0:
                self.vhre_slot_rows = []
            self.vhre_slot_rows.append(row)
            test_btn = ctk.CTkButton(
                row.control, text=tr("overlay.test"), width=78, height=26,
                corner_radius=ui_kit.RADIUS_CONTROL, fg_color="transparent", border_width=1,
                border_color=pal["line_soft"], hover_color=pal["surface_alt"],
                text_color=pal["text_dim"], font=ui_kit.ui(10),
                command=lambda i=index: self.toggle_overlay_test(i))
            test_btn.pack(side="left", padx=(0, 6))
            self.vhre_test_buttons[index] = test_btn
            # farba piktogramu tohto vizualu (color picker)
            swatch = ctk.CTkButton(
                row.control, text="", width=26, height=26, corner_radius=ui_kit.RADIUS_CONTROL,
                fg_color=self._overlay_color(index), border_width=1,
                border_color=pal["border"], hover_color=self._overlay_color(index),
                command=lambda i=index: self.pick_overlay_color(i))
            swatch.pack(side="left", padx=(0, 8))
            self.vhre_color_swatches = getattr(self, "vhre_color_swatches", {})
            self.vhre_color_swatches[index] = swatch
            var = tk.BooleanVar(value=cfg["enabled"])
            ctk.CTkSwitch(row.control, text="", variable=var, width=40,
                          switch_width=36, switch_height=18,
                          progress_color=pal["accent2"], fg_color=pal["switch_off"],
                          button_hover_color=pal["accent_hover"],
                          command=lambda i=index, v=var: self.on_overlay_config_change(
                              i, enabled=v.get())).pack(side="left")
            self.vhre_vis_switches.append(var)

        ctk.CTkButton(vis_panel.body, text=tr("overlay.fine_tune"), height=32,
                      corner_radius=ui_kit.RADIUS_CONTROL, fg_color="transparent", border_width=1,
                      border_color=pal["border"], hover_color=pal["surface_alt"],
                      text_color=pal["text"], font=ui_kit.ui(12),
                      command=self.open_overlay_settings).pack(fill="x", pady=(12, 0))

    def _build_ingame_sections_into(self, parent, pal):
        """Styri sekcie stiahnute zo stranky hodiniek do Vseobecnych.

        Su ZABALENE zamerne. Ikonky v hre, obrazovka, jazyk v hre a panel s
        tepom sa nastavia raz pri prvom spusteni; anti-cheat sa precita raz.
        Rozbalene by z Vseobecnych spravili najdlhsiu stranku appky, po
        ktorej sa scrolluje za temou a jazykom.
        """
        # --- monitor ---
        mon_panel = ui_kit.Collapsible(parent, pal,
                                       title=tr("overlay.monitor.label"))
        mon_panel.pack(fill="x", pady=(10, 0))
        # --- jazyk toho, co vidno V HRE ---
        # Samostatny od jazyka okna zamerne: HUD vlavo dole a popisky pod
        # vizualmi koncia na streame a na screenshotoch v obchode, kde ich
        # citaju aj ludia, co jazyk rozhrania nevedia. Preto anglictina
        # predvolene, aj ked appka bezi po slovensky.
        row = ui_kit.SettingRow(mon_panel.body, pal, tr("settings.game_lang"),
                                tr("settings.game_lang_sub"), wrap=520)
        self.game_lang_var = tk.StringVar(value=self._game_lang_label(self.game_lang))
        ctk.CTkOptionMenu(
            row.control, values=[tr("settings.game_lang_same")]
            + list(LANG_NATIVE_LABELS.values()),
            variable=self.game_lang_var, width=210, height=28,
            corner_radius=ui_kit.RADIUS_CONTROL, fg_color=pal["surface_alt"],
            button_color=pal["accent2"], button_hover_color=pal["accent2_hover"],
            text_color=pal["text"], dropdown_fg_color=pal["surface"],
            dropdown_text_color=pal["text"], font=ui_kit.ui(12),
            command=self.on_game_lang_change).pack()

        row = ui_kit.SettingRow(mon_panel.body, pal, tr("overlay.monitor.pick"),
                                tr("overlay.monitor.hint"))
        options = self.monitor_choices()
        self._monitor_labels = {label: value for label, value in options}
        current = next((label for label, value in options
                        if value == self.monitor_target), options[0][0])
        self.monitor_box = ctk.CTkOptionMenu(
            row.control, values=[label for label, _ in options], width=230, height=28,
            corner_radius=ui_kit.RADIUS_CONTROL, fg_color=pal["surface_alt"], button_color=pal["accent2"],
            button_hover_color=pal["accent2_hover"], text_color=pal["text"],
            dropdown_fg_color=pal["surface"], dropdown_text_color=pal["text"],
            font=ui_kit.ui(12), command=self._on_monitor_pick)
        self.monitor_box.set(current)
        self.monitor_box.pack()

        # --- HUD ---
        hud_panel = ui_kit.Collapsible(parent, pal,
                                       title=tr("hud.section_title"))
        hud_panel.pack(fill="x", pady=(10, 0))
        row = ui_kit.SettingRow(hud_panel.body, pal, tr("hud.enable"), tr("hud.hint"))
        ctk.CTkButton(row.control, text=tr("hud.test"), width=104, height=26,
                      corner_radius=ui_kit.RADIUS_CONTROL, fg_color="transparent", border_width=1,
                      border_color=pal["line_soft"], hover_color=pal["surface_alt"],
                      text_color=pal["text_dim"], font=ui_kit.ui(10),
                      command=self.test_hud).pack(side="left", padx=(0, 8))
        self.hud_enabled_var = tk.BooleanVar(value=self.hud_config["enabled"])
        ctk.CTkSwitch(row.control, text="", variable=self.hud_enabled_var, width=40,
                      switch_width=36, switch_height=18,
                      progress_color=pal["accent2"], fg_color=pal["switch_off"],
                      button_hover_color=pal["accent_hover"],
                      command=lambda: self.on_hud_config_change(
                          enabled=self.hud_enabled_var.get())).pack(side="left")

        # --- IKONKY FUNKCII: podriadena volba, nie samostatna sekcia ---
        #
        # Do 19. 9. mali vlastny zabaleny panel, a to NAD panelom s tepom.
        # Lenze `hud.StatsHud` ich kresli dovnutra panela s tepom: kym je
        # panel vypnuty, prepinac ikoniek nespravi vobec nic. Hrac zapol
        # vrchny prepinac, nic sa nestalo a nemal ziadnu indiciu, ze mu
        # chyba druhy o dva panely nizsie. Vyzeralo to ako pokazeny prepinac.
        #
        # Teraz sedia pod svojim rodicom a kym je panel vypnuty, su
        # zosedivene - vtedy je hned vidno, co treba zapnut najprv.
        ctk.CTkFrame(hud_panel.body, fg_color=pal["line_soft"], height=1,
                     corner_radius=0).pack(fill="x", pady=(12, 0))
        ctk.CTkLabel(hud_panel.body, text=tr("hud.trigger_row.sub"),
                     font=ui_kit.ui(10), text_color=pal["text_faint"],
                     wraplength=440, anchor="w", justify="left").pack(
            fill="x", pady=(10, 0))

        row = ui_kit.SettingRow(hud_panel.body, pal, tr("hud.trigger_row.toggle"))
        self.hud_trigger_var = tk.BooleanVar(value=self.hud_config["show_triggers"])
        self.hud_trigger_switch = ctk.CTkSwitch(
            row.control, text="", variable=self.hud_trigger_var, width=40,
            switch_width=36, switch_height=18,
            progress_color=pal["accent2"], fg_color=pal["switch_off"],
            button_hover_color=pal["accent_hover"],
            command=lambda: self.on_hud_config_change(
                show_triggers=self.hud_trigger_var.get()))
        self.hud_trigger_switch.pack(side="left")

        color_row = ui_kit.SettingRow(hud_panel.body, pal, tr("hud.trigger_row.color"))
        self.hud_trigger_swatch = ctk.CTkButton(
            color_row.control, text="", width=26, height=26,
            corner_radius=ui_kit.RADIUS_CONTROL,
            fg_color=self._hud_trigger_color_display(), border_width=1,
            border_color=pal["border"], hover_color=self._hud_trigger_color_display(),
            command=self.pick_hud_trigger_color)
        self.hud_trigger_swatch.pack(side="left")
        self._sync_hud_trigger_state()

        for key, label, low, high, fmt in (
                ("scale", tr("overlay.scale"), 0.6, 2.0, "{:.2f}×"),
                ("opacity", tr("hud.opacity"), 0.25, 1.0, "{:.0%}")):
            row = ui_kit.SettingRow(hud_panel.body, pal, label)
            value_label = ctk.CTkLabel(row.control, text=fmt.format(self.hud_config[key]),
                                       width=52, font=ui_kit.mono(11),
                                       text_color=pal["text_dim"])
            value_label.pack(side="right", padx=(8, 0))
            var = tk.DoubleVar(value=self.hud_config[key])
            ui_kit.block_slider_wheel(ctk.CTkSlider(row.control, from_=low, to=high, variable=var, width=180,
                          number_of_steps=28, progress_color=pal["accent"],
                          button_color=pal["accent"], fg_color=pal["switch_off"],
                          button_hover_color=pal["accent_hover"],
                          command=lambda _v, k=key, v=var, lbl=value_label, f=fmt:
                              self._on_hud_slider(k, v, lbl, f))).pack(side="right")

        # --- anti-cheat ---
        #
        # Je to CISTY TEXT, ziadne nastavenie: co appka voci hre robi a co
        # nerobi. Clovek si to precita raz, ked sa rozhoduje, ci si ju vobec
        # pusti - preto zabalene, aby to nezabralo pol stranky navzdy.
        safety = ui_kit.Collapsible(parent, pal, title=tr("safety.title"))
        safety.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(safety.body, text=tr("safety.body"), font=ui_kit.ui(11),
                     text_color=pal["text_dim"], wraplength=620, anchor="w",
                     justify="left").pack(fill="x")

    def _on_monitor_pick(self, label):
        self.on_monitor_target_change(self._monitor_labels.get(label, "auto"))

    def _on_hud_slider(self, key, var, label, fmt):
        value = round(float(var.get()), 3)
        try:
            label.configure(text=fmt.format(value))
        except Exception:
            pass
        self.on_hud_config_change(**{key: value})

    # POZN: `_on_dojo_slider` a `_update_dojo_readout` tu boli - obsluha
    # posuvnika "Pozadie dojo" a jeho ziva spatna vazba (pasma vypnute/
    # jemne/stredne/vyrazne/plne). Zmizli spolu s fotopasom nad titulkovou
    # listou, ktory jediny ovladali (viz POZN v `_build_ui`).

    def _build_citlivost_card(self, parent, pal):
        """Co si appka o mne spocitala. Uz ziadny prepinac.

        PRECO PREPINAC ZMIZOL: mal tri polohy (menej / bezne / viac) a hrac
        nemal ako vediet, co ktora urobi PRAVE JEMU. Zataz je skalovana voci
        jeho vlastnej zakladne, takze to iste cislo znamena u kazdeho nieco
        ine - a odmerane na realnych datach vyslo, ze rozdiel medzi polohami
        je mensi nez rozdiel medzi dvoma vecermi.

        Prah si appka rata z vlastnych relacii (80. percentil zataze), tak
        ako uz ratala zakladnu a hranicu vysokeho tepu. Tu sa to len UKAZE.
        """
        panel = ui_kit.Panel(parent, pal, title=tr("cue_rate.title"))
        panel.pack(fill="x", pady=(16, 0))
        self.citlivost_detail = ctk.CTkLabel(
            panel.body, text=self._citlivost_detail_text(), font=ui_kit.ui(11),
            text_color=pal["text_dim"], anchor="w", justify="left",
            wraplength=640)
        self.citlivost_detail.pack(fill="x")
        return panel

    def _citlivost_detail_text(self):
        """Veta sa cita Z PARAMETROV, nie z prekladu - inak by sa po prvej
        zmene rozisla s tym, co appka naozaj robi."""
        p = self.cue_trigger.params
        if getattr(self, "_prah_z_dat", None) is None:
            return tr("cue_rate.learning",
                      prah=f"{p['stress_threshold']:g}",
                      hold=f"{p['stress_hold_s']:g}")
        return tr("cue_rate.computed",
                  prah=f"{p['stress_threshold']:g}",
                  hold=f"{p['stress_hold_s']:g}",
                  strop=f"{p['max_per_hour']:g}",
                  odstup=f"{p['min_gap_s'] / 60.0:g}",
                  n=self._prah_z_relacii)

    def _refresh_citlivost_detail(self):
        popis = getattr(self, "citlivost_detail", None)
        if popis is None:
            return
        try:
            popis.configure(text=self._citlivost_detail_text())
        except Exception:
            pass

    def _build_guide_into(self, parent, pal):
        """Vysvetlivky a teoria, vlozene pod obsah hlasok.

        Referencia `self.guide_content` ostava, lebo `gui_screenshots.py`
        cez nu karty rozbaluje (inak sa rozbalit nedaju nez klikom).
        """
        self.guide_content = build_guide_into(parent, pal)

    def _navigate(self, key):
        key = self.TAB_ALIAS.get(key, key)
        """Prepne stranku. Karty Nastaveni (SETTINGS_TABS) su vnorene: ukaze
        skupinu Nastavenia a v nej danu kartu; "nastavenia" samo otvori
        naposledy pouzitu kartu (prvykrat Spustace).

        POZN: na zaciatku tu bolo `dojo_band.suspend_briefly()`, ktore na
        180 ms zastavilo prekreslovanie lampionov vo fotopase - rychle
        preklikavanie v sidebari inak spadalo do stredu toho prekreslenia
        a vyzeralo to, ze "sa prenastavuje cela appka". Fotopas bol
        odstraneny (viz POZN v `_build_ui`), takze s nim zmizol aj zdroj
        toho mihnutia - nie je uz co pozastavovat.
        """
        if key in self.SETTINGS_TABS:
            self.pages.show("nastavenia")
            self.settings_pages.show(key)
            self.settings_nav.set_active(key)
            self._settings_last_tab = key
        elif key == "nastavenia":
            self.pages.show("nastavenia")
            tab = getattr(self, "_settings_last_tab", "spustace")
            self.settings_pages.show(tab)
            self.settings_nav.set_active(tab)
        else:
            self.pages.show(key)

    def _build_settings_group(self, page, pal):
        """Skupina Nastavenia: rad kariet hore (Spustace | Zvuk | Sprievodca |
        Vseobecne) a pod nim vnoreny PageContainer.

        "V hre" uz nie je karta - je to samostatna polozka v bocnom menu
        (redizajn "Sumi noc"), pretoze je to najvacsia cast appky.
        """
        head = ctk.CTkFrame(page, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=(16, 0))
        self.settings_nav = ui_kit.SubNav(
            head, pal, [(k, tr(f"nav.nastavenia_tabs.{k}")) for k in self.SETTINGS_TABS],
            on_select=self.sidebar._select)
        self.settings_nav.pack(anchor="w")
        self.settings_pages = PageContainer(page)
        self.settings_pages.configure(fg_color=pal["bg"])
        self.settings_pages.pack(fill="both", expand=True, pady=(8, 0))
        for key, builder in (("spustace", self._build_spustace_page),
                             ("zvuk", self._build_zvuk_page),
                             ("vseobecne", self._build_nastavenia_page)):
            frame = ctk.CTkFrame(self.settings_pages, fg_color=pal["bg"])
            self.settings_pages.add_page(key, frame)
            self.page_frames[key] = frame
            builder(frame, pal)
        tab = getattr(self, "_settings_last_tab", "spustace")
        self.settings_pages.show(tab)
        self.settings_nav.set_active(tab)

    def _build_nastavenia_page(self, page, pal):
        """Vseobecne nastavenia (karta v skupine Nastavenia): uz len veci,
        ktore sa nastavia raz - vzhlad, jazyk, spravanie, sprievodca.

        Scrollovatelny ramec (nie len CTkFrame): pri pevnom rozmere okna
        (viz DandurfApp.WINDOW_H) sa vsetky panely (Vzhlad/Spravanie/
        Sprievodca) nemusia zmestit na vysku - bez scrollu by spodne panely
        boli nedosiahnutelne.

        POZN: povodne tu boli vymenovane aj panely "Pozadie dojo" a
        "Minimalisticky rezim" - oba boli medzitym odstranene, takze uz
        nie su dovodom pre scroll.
        """
        wrap = ctk.CTkScrollableFrame(
            page, fg_color="transparent", scrollbar_button_color=pal["surface_alt"],
            scrollbar_button_hover_color=pal["accent"])
        wrap.pack(fill="both", expand=True, padx=24, pady=(20, 20))

        # POZN: prvym panelom tu bolo "Pozadie dojo" - posuvnik intenzity
        # fotopasu nad titulkovou listou, so zivou spatnou vazbou o
        # citatelnosti. Pas bol odstraneny (viz POZN v `_build_ui`), takze
        # posuvnik uz nemal co ovladat. Vzhlad je teraz prvy panel.
        # FAZA 4: data ako PRVY panel, nie zahrabane dole. Sub "vsetko
        # ostava u teba" je na store page a je to skutocny rozdiel oproti
        # konkurencii - ma sa dat overit, nie hladat.
        # Referencia na scrollovaci ram: `show_about` podla nej posunie
        # stranku na sekciu O appke. Bez nej by tlacidlo v liste otvorilo
        # spravnu stranku, ale hrac by na nej ostal hore a sekciu by musel
        # najst sam - cize by tlacidlo splnilo polovicu svojej ulohy.
        self.vseobecne_wrap = wrap

        self._build_data_panel(wrap, pal)

        # "O appke" HNED POD DATAMI. Su to dve strany tej istej otazky:
        # co appka robi s mojimi datami a kto za nou stoji. Clovek, ktory
        # hlada jedno, obvykle hlada aj druhe.
        self._build_about_panel(wrap, pal)

        # Veci, ktore appka kresli do hry. Prisli sem zo stranky hodiniek,
        # kde prekryvali jedinu vec, kvoli ktorej tam clovek chodi.
        self._build_ingame_sections_into(wrap, pal)

        look = ui_kit.Panel(wrap, pal, title=tr("settings.look_title"))
        look.pack(fill="x", pady=(14, 0))

        # SVET namiesto farebnej temy (0.2, B3-worlds). Vzhlad patri svetu -
        # Hra je Sumi, Praca Aizome - takze samostatny vyber temy by len
        # rozbil to, co ma jeden pohlad na okno povedat. Je to ten isty
        # prepinac ako v liste hore (`set_world`); veta pod nim hovori
        # poctivo, co vsetko sa s nim meni. (Do 0.2 tu bola "Farebna tema"
        # s vetou "skus obe" - to by teraz prestitkovalo relacie.)
        row = ui_kit.SettingRow(look.body, pal, tr("settings.world"),
                                tr("settings.world_sub"))
        self.world_switch = ctk.CTkSegmentedButton(
            row.control, values=self._world_labels(),
            selected_color=pal["accent2"], selected_hover_color=pal["accent2_hover"],
            unselected_color=pal["surface_alt"], unselected_hover_color=pal["border"],
            text_color=pal["text"], fg_color=pal["surface_alt"],
            font=ui_kit.ui(12), command=self._on_world_label)
        self.world_switch.set(self._world_label(self.world))
        self.world_switch.pack()

        # Veta pod vyberom jazyka hovori poctivo, co je zdroj a co preklad:
        # appka je pisana po slovensky, ostatne jazyky su preklady s AI,
        # ktore este necital rodeny hovoriaci. Ukazuje sa vo vsetkych
        # jazykoch (sama sa preklada ako ostatne texty).
        row = ui_kit.SettingRow(look.body, pal, tr("settings.language"),
                                tr("settings.language_sub"),
                                note=tr("settings.language_note"))
        self.lang_var = tk.StringVar(value=self._lang_switch_value(self.lang))
        self.lang_switch = ctk.CTkOptionMenu(
            row.control, values=list(LANG_NATIVE_LABELS.values()), variable=self.lang_var,
            width=170, height=28, corner_radius=ui_kit.RADIUS_CONTROL, fg_color=pal["surface_alt"],
            button_color=pal["accent2"], button_hover_color=pal["accent2_hover"],
            text_color=pal["text"], dropdown_fg_color=pal["surface"],
            dropdown_text_color=pal["text"], font=ui_kit.ui(12),
            command=self.on_lang_switch)
        self.lang_switch.pack()

        # POZN: tu bol panel "Spravanie" s jedinym prepinacom "Naraz len
        # jedna pripomienka". Bol to jediny prepinac v celom paneli, takze
        # posobil ako dolezite nastavenie - a pritom ho automat necital
        # vobec: dve hlasky naraz nespusti ani nemoze (`min_gap_s` je 210 s
        # a vyssie). Cital ho jedine `fire_slot`, teda tlacidlo Test.
        # Tam ochrana zmysel ma, tak tam ostala - natvrdo, bez prepinaca.

        # POZN: prepinac "Minimalisticky rezim" tu bol (zmensoval cele okno
        # appky na 320x160) - odstraneny. Rovnaka funkcia (BPM + 4 ikonky)
        # je teraz sucastou HUD panela v hre, viz "Ukazat panel v hre" v
        # _build_vhre_page - je to spravne miesto, lebo ide o IN-GAME
        # vizual, nie o rezim samotnej appky.

        guide = ui_kit.Panel(wrap, pal, title=tr("settings.guide_title"))
        guide.pack(fill="x", pady=(14, 0))
        row = ui_kit.SettingRow(guide.body, pal, tr("settings.guide_row"),
                                tr("settings.guide_sub"))
        ui_kit.chip(row.control, pal, tr("common.open"),
                    self.open_guide_panel, width=104).pack()
        self.tour_row = ui_kit.SettingRow(guide.body, pal, tr("settings.tour_row"),
                                          tr("settings.tour_sub"))
        self.tour_btn = ui_kit.chip(self.tour_row.control, pal,
                                    tr("settings.tour_btn"), self.start_tour,
                                    width=140)
        self.tour_btn.pack()
        self._refresh_tour_row()      # rozpracovana prehliadka ponuka Pokracovat

    def _build_heart_rate_card(self, page, pal, pady=(14, 0)):
        """Senzor Tepu (Wi-Fi / UDP) - prijem BPM z hodiniek (napr.
        HeartRateOnStream for OBS) a automaticky biofeedback trigger
        dychoveho kruhu (Slot 4) pri dlhodobo zvysenom tepe.

        `pady` je odsadenie panela zhora - prvy panel na stranke ho ma
        nulove, ostatne 14 px (rovnaka konvencia ako zvysok stranky)."""
        # POZN: karta si tu predtym stavala vlastny CTkFrame s
        # `pack(padx=20)` a vlastnym nadpisom v mriezke, kym VSETKY ostatne
        # panely na stranke idu cez `ui_kit.Panel` a pakuju sa bez padx.
        # Karta tak bola oproti nim odsadena o 20 px a mala iny nadpis aj
        # okraj - hlasene ako "nesedi so zarovnanim ostatnych". Teraz je to
        # rovnaky Panel ako zvysok, takze zarovnanie drzi samo od seba.
        panel = ui_kit.Panel(page, pal, title=tr("settings.hr_section_title"))
        panel.pack(fill="x", pady=pady)
        self.hr_card = panel          # ciel kroku prehliadky o senzore tepu
        inner = ctk.CTkFrame(panel.body, fg_color="transparent")
        inner.pack(fill="x")
        inner.grid_columnconfigure(1, weight=1)

        self.hr_ip_var = tk.StringVar(value=self.hr_ip)
        # Pole IP je skryte ako heslo, kym si ho hrac neodkryje prepinacom
        # vedla neho (skryta IP, viz `set_show_ip`). Ukladanie hodnoty sa
        # tym nemeni - maska je len to, ako pole kresli.
        self.show_ip_var = tk.BooleanVar(value=self.show_ip)

        def _prepinac_ip(bunka):
            ctk.CTkSwitch(bunka, text=tr("hr.ip_show"), variable=self.show_ip_var,
                          progress_color=pal["accent"], text_color=pal["text_dim"],
                          font=ui_kit.ui(11),
                          command=lambda: self.set_show_ip(self.show_ip_var.get())
                          ).pack(side="left", padx=(12, 0))

        self.hr_ip_entry = self._hr_entry(inner, pal, 1, tr("settings.hr_ip_label"),
                                          self.hr_ip_var, extra=_prepinac_ip)
        self.hr_ip_var.trace_add("write", lambda *_a: self._apply_hr_ip_mask())
        self._apply_hr_ip_mask()
        self._hr_hint(inner, pal, 2, tr("settings.hr_ip_hint"))

        self.hr_port_var = tk.StringVar(value=str(self.hr_port))
        self.hr_port_entry = self._hr_entry(inner, pal, 3, tr("settings.hr_port_label"),
                                            self.hr_port_var)
        self._hr_hint(inner, pal, 4, tr("settings.hr_port_hint"))

        # KRITICKY TEP UZ NIE JE POLICKO.
        #
        # Nedal sa nastavit dobre. Vstupuje do vzorca zataze ako
        # `headroom = max(12, kriticky - zakladna)`, takze pri zakladni 77
        # davalo hocico do 89 ten isty vysledok - hrac posuval cislo a nic
        # sa nemenilo. A zaroven urcuje pasmo "kriticka", takze prilis nizka
        # hodnota spravila z pokojneho vecera 52 % casu v cervenom.
        #
        # Appka si ho rata z vlastnych relacii (`hr_stats.dynamicky_kriticky`,
        # 90. percentil hrania). Tu sa uz len UKAZUJE, aby bolo vidno, s cim
        # appka pracuje a ako sa to casom meni.
        self.hr_critical_label = ctk.CTkLabel(
            inner, text=self._kriticky_popis(), font=ui_kit.ui(11),
            text_color=pal["text_dim"], anchor="w", justify="left",
            wraplength=430)
        self.hr_critical_label.grid(row=5, column=0, columnspan=2, sticky="w",
                                    pady=(10, 0))

        self.hr_enabled_var = tk.BooleanVar(value=self.hr_monitoring_enabled)
        ctk.CTkSwitch(inner, text=tr("settings.hr_enable_switch"),
                     variable=self.hr_enabled_var,
                     progress_color=pal["accent"], text_color=pal["text"],
                     command=self.on_hr_toggle).grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(10, 10))

        self.hr_status_label = ctk.CTkLabel(inner, text="", font=("Segoe UI", 13, "bold"))
        self.hr_status_label.grid(row=8, column=0, columnspan=2, sticky="w")
        self.refresh_hr_status_label()

        # Parovanie hodiniek je najmenej intuitivna cast celej appky - hrac
        # musi vediet, ze appka predstiera OBS a ze si v telefone nastavuje
        # OBS spojenie. Preto samostatny krokovy navod, nie len hint pod
        # polickom (viz WatchPairingDialog).
        ctk.CTkButton(inner, text=tr("hr.pair_button"), height=32,
                      corner_radius=ui_kit.RADIUS_CONTROL, fg_color="transparent", border_width=1,
                      border_color=pal["accent"], hover_color=pal["surface_alt"],
                      text_color=pal["accent_hover"], font=ui_kit.ui(12),
                      command=self.open_watch_pairing).grid(
            row=9, column=0, columnspan=2, sticky="ew", pady=(14, 0))

        # QR na appku do telefonu aj tu, nielen v krokovom navode - kto uz
        # vie, co robi, si ju chce stiahnut bez otvarania sprievodcu.
        # Navonok je to len znacka, biely kod sa rozbali az na klik
        # (viz ui_kit.QrReveal).
        qr_row = ctk.CTkFrame(inner, fg_color="transparent")
        qr_row.grid(row=10, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.hr_qr = watch_app_qr(qr_row, pal, pady=0)

    def _hr_entry(self, inner, pal, row, label, variable, extra=None):
        """Jeden riadok "popisok + policko" karty Senzor Tepu.

        set_typing() je tu rovnako dolezity ako v slotoch (viz SlotCard):
        globalny odchytavac klavesnice bezi aj ked hrac prave pise do
        nastaveni, takze bez tejto poistky by mu pisanie "110" spustilo
        slot, ktory ma nabindovany na klavesu "1".

        `extra(bunka)` prida vedla policka dalsi ovladac (prepinac
        "Ukazat IP") - policko ostava na tom istom mieste v osi."""
        # pevna sirka popisku + rovnaka sirka policka: vsetky tri riadky
        # (IP, port, tep) sedia v jednej osi (feedback: "nie su v jednej osi")
        ctk.CTkLabel(inner, text=label, text_color=pal["text"], width=190,
                     anchor="w", justify="left").grid(
            row=row, column=0, sticky="w", pady=6)
        bunka = inner
        if extra is not None:
            bunka = ctk.CTkFrame(inner, fg_color="transparent")
            bunka.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=6)
        entry = ctk.CTkEntry(bunka, textvariable=variable, width=150, height=30,
                             corner_radius=ui_kit.RADIUS_CONTROL,
                             fg_color=pal["entry_bg"], border_color=pal["border"],
                             text_color=pal["text"])
        if extra is not None:
            entry.pack(side="left")
            extra(bunka)
        else:
            entry.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=6)
        entry.bind("<FocusIn>", lambda _e: self.set_typing(True))
        entry.bind("<FocusOut>", lambda _e: (self.set_typing(False),
                                             self.on_hr_config_change()))
        entry.bind("<Return>", lambda _e: self.on_hr_config_change())
        return entry

    def _kriticky_popis(self):
        """Veta pod polickami senzora - co si appka spocitala a z coho.

        Z coho = z HERNYCH relacii (B3-worlds), rovnako ako samotny vypocet
        v `_open_hr_session`; pracovne vecery sa do `n` nerataju.

        KRATKE RELACIE SA NERATAJU (0.2.1) - `dynamicky_kriticky` sa uci len
        z relacii dlhych aspon 5 minut (`hr_stats.je_dost_dlha`). Bez toho
        by po troch kratkych relaciach veta tvrdila "spocitane z 3 relacii",
        kym v skutocnosti plati zaloha 110."""
        n = len([r for r in hr_stats.ciste_relacie(hr_stats.sessions_in_world(
            self._history_sessions(), self.ALGORITMUS_SVET))
            if hr_stats.je_dost_dlha(r)])
        if n < hr_stats.KRITICKY_MIN_RELACII:
            return tr("settings.hr_critical_learning",
                      bpm=int(self.hr_critical_bpm),
                      treba=hr_stats.KRITICKY_MIN_RELACII - n)
        return tr("settings.hr_critical_computed",
                  bpm=int(self.hr_critical_bpm), n=n)

    def _refresh_kriticky_popis(self):
        popis = getattr(self, "hr_critical_label", None)
        if popis is None:
            return
        try:
            popis.configure(text=self._kriticky_popis())
        except Exception:
            pass

    def _hr_hint(self, inner, pal, row, text):
        """Vysvetlivka pod jedným policom karty Senzor Tepu.

        Samostatna metoda (namiesto opakovania grid() na kazdom mieste),
        aby vsetky tri riadky (IP/Port/Tep) mali zarucene rovnake lave
        zarovnanie aj rovnaky vertikalny odstup - feedback z testu ("rozne
        odsadenie") ukazal, ze kopirovanie tych istych grid() argumentov na
        3 miestach sa casom rozide."""
        ctk.CTkLabel(inner, text=text, text_color=pal["text_dim"],
                    font=ui_kit.ui(10), wraplength=320, justify="left",
                    anchor="w").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 4))

    # ---------- Somatic Session Tracker ----------

    def _session_text(self):
        c = self.session_counts
        return tr("session.summary", g=c.get(0, 0), j=c.get(1, 0),
                 r=c.get(2, 0), b=c.get(3, 0))

    def update_session_label(self):
        if self.session_label is not None:
            try:
                self.session_label.configure(text=self._session_text())
            except Exception:
                pass

    # ---------- sprievodca ----------

    def open_guide_panel(self):
        if self._guide_panel is not None and self._guide_panel.top.winfo_exists():
            self._guide_panel.top.lift()
            self._guide_panel.top.focus_force()
            return
        self._guide_panel = GuidePanel(self)

    def start_tour(self, from_start=False):
        """Spusti sprievodnu prehliadku appky (kde co je).

        Vola sa raz po prvom onboardingu a kedykolvek z Nastaveni. Drzime si
        jednu instanciu, aby sa dve prehliadky neprekryvali.

        `from_start=True` zacne od zaciatku; inak nadviaze tam, kde ju hrac
        naposledy opustil (`tour_step`) - jedenast krokov nikto nepreklika
        naraz a zacinat vzdy odznova znamena, ze druhykrat uz nepozrie nic.
        """
        existing = getattr(self, "_tour", None)
        if existing is not None:
            existing.finish()
        self._tour = GuidedTour(self, start_index=0 if from_start else self.tour_step)
        self._tour.start()

    def save_tour_progress(self, index):
        """Kde prehliadka skoncila (0 = dobehla cela)."""
        self.tour_step = max(0, int(index or 0))
        self._refresh_tour_row()
        self.save_settings()

    def _refresh_tour_row(self):
        """Riadok prehliadky v Nastaveniach - rozpracovana prehliadka ponuka
        Pokracovat a ukaze, kde clovek skoncil."""
        row = getattr(self, "tour_row", None)
        button = getattr(self, "tour_btn", None)
        if row is None or button is None:
            return
        try:
            rozpracovana = self.tour_step > 0
            row.title_label.configure(
                text=tr("settings.tour_row_at", n=self.tour_step + 1,
                        total=GuidedTour.STEP_COUNT) if rozpracovana
                else tr("settings.tour_row"))
            button.configure(text=tr("settings.tour_resume") if rozpracovana
                             else tr("settings.tour_btn"))
        except Exception:
            pass

    def mark_tour_seen(self):
        """Prehliadka dobehla alebo bola preskocena - uz ju sami nespustime."""
        self.tour_seen = True
        self._tour = None
        self.save_settings()

    def _refresh_guide_panel_theme(self):
        if self._guide_panel is not None and self._guide_panel.top.winfo_exists():
            self._guide_panel.top.destroy()
            self._guide_panel = GuidePanel(self)

    # ---------- sloty ----------

    def rebuild_slots(self, data_list):
        """Prestava sloty aktivneho profilu, zosuladi odznak v navigacii aj
        listu hromadneho vyberu (po prestavbe uz nic nie je oznacene)."""
        for child in self.slots_container.winfo_children():
            child.destroy()
        self.slots = [SlotCard(self, i, data) for i, data in enumerate(data_list)]
        self._on_slot_selection_change()
        self._refresh_nav_badges()

    def slot_dicts(self):
        return [s.to_dict() for s in self.slots]

    # ---------- profily hier ----------

    def _sync_active_profile_slots(self):
        profile = next((p for p in self.profiles if p["name"] == self.active_profile_name),
                       None)
        if profile is not None:
            profile["slots"] = self.slot_dicts()

    def refresh_profile_switch(self):
        names = [p["name"] for p in self.profiles]
        self.profile_switch.configure(values=names)
        self.profile_var.set(self.active_profile_name)

    def on_profile_switch(self, name):
        self.switch_profile(name)

    def switch_profile(self, name):
        if name == self.active_profile_name:
            return
        profile = next((p for p in self.profiles if p["name"] == name), None)
        if profile is None:
            return
        self._sync_active_profile_slots()
        self.active_profile_name = name
        self.rebuild_slots(profile["slots"])
        self.profile_var.set(name)
        self.save_settings()
        self.schedule_pregenerate(200)
        self.log(tr("log.profile_switched", name=name))

    def new_profile_dialog(self):
        NewProfileDialog(self)

    def create_profile(self, name):
        name = name.strip()
        if not name:
            return
        if any(p["name"] == name for p in self.profiles):
            messagebox.showinfo(APP_NAME, tr("profile.duplicate_name"))
            return
        self._sync_active_profile_slots()
        # Novy profil dostane VSETKY STYRI kategorie, rovnako ako profil
        # zalozeny automaticky pre hru (`_handle_game_found`). Doteraz mal
        # jeden slot a zvysne si hrac "pridal" tlacidlom - to je prec, takze
        # by profil ostal navzdy len s Taziskom.
        new_slots = [normalize_slot(s) for s in default_slots()]
        self.profiles.append({"name": name, "slots": new_slots})
        self.active_profile_name = name
        self.rebuild_slots(new_slots)
        self.refresh_profile_switch()
        self.save_settings()
        self.log(tr("log.profile_created", name=name))

    def delete_current_profile(self):
        if len(self.profiles) <= 1:
            messagebox.showinfo(APP_NAME, tr("profile.cannot_delete_last"))
            return
        if not messagebox.askyesno(APP_NAME,
                                   tr("profile.confirm_delete", name=self.active_profile_name)):
            return
        self.profiles = [p for p in self.profiles if p["name"] != self.active_profile_name]
        new_active = self.profiles[0]
        self.active_profile_name = new_active["name"]
        self.rebuild_slots(new_active["slots"])
        self.refresh_profile_switch()
        self.save_settings()
        self.schedule_pregenerate(200)
        self.log(tr("log.profile_deleted"))

    # ---------- Auto-Profile Engine (rozpoznanie beziacej hry) ----------

    def on_game_process_found(self, profile_name):
        self.ui_call(lambda: self._handle_game_found(profile_name))

    def on_game_process_gone(self):
        self.ui_call(self._handle_game_gone)

    def _handle_game_found(self, profile_name):
        if not self.auto_profile_enabled:
            return
        if not any(p["name"] == profile_name for p in self.profiles):
            self._sync_active_profile_slots()
            new_slots = [normalize_slot(s) for s in default_slots()]
            self.profiles.append({"name": profile_name, "slots": new_slots})
            self.refresh_profile_switch()
            self.log(tr("log.auto_profile_created", name=profile_name))
        if profile_name != self.active_profile_name:
            self.switch_profile(profile_name)
        self.log(tr("log.auto_profile_detected", name=profile_name))
        if not self.listening:
            self._auto_started_listening = True
            self.start_listening()

    def _handle_game_gone(self):
        if not self.auto_profile_enabled:
            return
        # "Odpocuvanie pozastavene" sa pise LEN ked sa naozaj zastavilo.
        # Doteraz sa zapisalo vzdy - aj ked pocuvanie spustil hrac sam a
        # bezalo dalej (port aj meranie), takze dennik tvrdil opak.
        if self.listening and self._auto_started_listening:
            self.stop_listening()
            self.log(tr("log.auto_profile_ended"))
        self._auto_started_listening = False

    @staticmethod
    def _zname_hry():
        """Hry, ktore auto-profil pozna, do viet v appke. Z mapy
        (`game_profiles.GAME_PROCESS_MAP`), aby veta nemohla slubovat start
        pri hre, ktoru appka nepozna."""
        return " / ".join(known_games())

    def _start_game_watcher(self):
        """Spusti citanie mien procesov (auto-profil). Vlakno sa neda
        spustit dvakrat, preto pri kazdom zapnuti nove."""
        if not PSUTIL_AVAILABLE or getattr(self, "game_watcher", None) is not None:
            return
        self.game_watcher = GameProcessWatcher(self.on_game_process_found,
                                               self.on_game_process_gone)
        self.game_watcher.start()

    def _stop_game_watcher(self):
        """Zastavi citanie procesov - vypnuty auto-profil necita nic."""
        watcher, self.game_watcher = getattr(self, "game_watcher", None), None
        if watcher is not None:
            watcher.stop()

    def _kamae_zastavene(self):
        """Dvojica textov pre stav "Zastavene".

        Appka sa vie spustit sama, ked najde beziacu hru - lenze len pri
        zapnutom automatickom prepinani profilov (`_handle_game_found`), a
        to sa da vypnut. Preto sa veta pyta na skutocny stav namiesto toho,
        aby slubovala nieco, co pri vypnutom prepinani nepride.
        """
        kluc = ("kamae.stopped_sub_auto" if self.auto_profile_enabled
                else "kamae.stopped_sub")
        return tr("kamae.stopped"), tr(kluc, games=self._zname_hry())

    def on_auto_profile_toggle(self):
        self.auto_profile_enabled = bool(self.auto_profile_var.get())
        if self.auto_profile_enabled:
            self._start_game_watcher()
        else:
            # Vypnute = mena procesov sa necitaju vobec. Pocuvanie, ktore
            # spustila hra, bezi dalej - odteraz ho riadi hrac, nie detekcia.
            self._stop_game_watcher()
            self._auto_started_listening = False
        self.save_settings()
        # Veta v pase hovori o tomto nastaveni, takze sa musi prepisat hned -
        # inak by po vypnuti este stale slubovala start pri hre.
        if not self.listening and getattr(self, "kamae", None) is not None:
            self.kamae.set_texts(tr("kamae.bar_title"), tr("kamae.bar_sub"))
        self.log(tr("log.auto_profile_on") if self.auto_profile_enabled
                else tr("log.auto_profile_off"))


    def on_hr_config_change(self):
        # prazdne policko = "pocuvaj na vsetkych sietach", nie "vrat povodnu
        # hodnotu" - hrac musi mat sposob, ako sa k tomu bezpecnemu stavu
        # dostat aj ked si tam raz napisal nefunkcnu adresu
        ip = self.hr_ip_var.get().strip() or ANY_INTERFACE
        port = clamp_int(self.hr_port_var.get(), 1, 65535, self.hr_port)
        critical = int(self.hr_critical_bpm)      # rata sa, nenastavuje
        network_changed = (ip != self.hr_ip) or (port != self.hr_port)
        self.hr_ip, self.hr_port, self.hr_critical_bpm = ip, port, critical
        self.hr_stats.critical_bpm = critical
        self.hud.configure(critical_bpm=critical)
        self.hr_ip_var.set(ip)
        self.hr_port_var.set(str(port))
        self.refresh_hr_status_label()
        self.save_settings()
        if network_changed and self.hr_monitoring_enabled:
            self.start_heart_rate_monitor()

    def on_hr_toggle(self):
        self.hr_monitoring_enabled = bool(self.hr_enabled_var.get())
        self.save_settings()
        if self.hr_monitoring_enabled:
            self.start_heart_rate_monitor()
        else:
            self.stop_heart_rate_monitor()

    def start_heart_rate_monitor(self):
        """Otvori novu meraciu relaciu A naštartuje sietovy prijem.

        Ked treba len novu relaciu (zapnutie pocuvania, ked uz hodinky
        posielaju), vola sa `_open_hr_session` priamo - restart socketu by
        hodinky na chvilu odpojil.
        """
        self._open_hr_session(meria=self.listening)
        self._hr_generation = self.heart_rate_monitor.start(self.hr_ip, self.hr_port)
        self.log(tr("log.hr_enabled", ip=self._hr_ip_display(), port=self.hr_port))
        # Ak sa do N sekúnd nepripojí ani jeden klient, povedz to inak než
        # "Pripája sa…" - "bound, ale nikto sa nepripojil" je iný problém
        # (najčastejšie firewall) a hráč to má vedieť (B2).
        self._schedule_no_client_check()
        # Varovanie o exkluzívnom fullscreene sa TU nekontroluje: v tejto
        # chvíli je popredím Zanshin (hráč práve klikol), takže hru by nikdy
        # nezachytilo (bug A3). Rieši to `_tick_session`, keď je popredím hra.

    def _open_hr_session(self, prepoj=True, meria=True):
        """Zacne novu meraciu relaciu. Siete sa NEDOTYKA.

        `prepoj=False` znamena "prijem uz bezi a hodinky posielaju" - vtedy
        sa stav pripojenia nesmie zhodit na "connecting", lebo by okno
        tvrdilo, ze sa prave pripaja, hoci data chodia.
        """
        # Predosla relacia sa musi KOREKTNE ZATVORIT, nie len prepisat.
        # `hr_stats.reset_session()` nizsie zmaze `cues` aj `_all`, takze bez
        # tohto by sa meracie okna uz nemali z coho zostavit - a jedina
        # cesta, ktora sem vedie s otvorenou relaciou, je zmena IP/portu
        # uprostred vecera (`apply_hr_settings`). Odmerane: cely vecer dat
        # zmizol bez jedineho riadku v logu.
        if getattr(self, "_hr_session_open", False):
            self._close_hr_session()
        if prepoj:
            self._hr_state = "connecting"
        self._hr_last_bpm = None
        # Vypadok patri do predoslej relacie, aj ked sa otvara bez prepojenia
        # (`start_listening` pocas vypadku). Inak by sa priznak preniesol do
        # novej relacie a riadok "tep je spat" by ratal od casu, ktory
        # `reset_session` nizsie prepise.
        self._hr_lost = False
        self._hr_lost_od = None
        self._hr_over_since = None
        self._hr_overlay_warned = False
        self._hr_retry_job = None
        self._hr_bind_retries = 0
        self._hr_client_linked = False
        self.hr_stats.critical_bpm = self.hr_critical_bpm
        # SVET RELACIE SA PECATI TU (B3-worlds), pri otvoreni - nie pri
        # zatvoreni. Kto si uprostred hry len prepne na Pracu, aby videl
        # pracovne statistiky, a zabudne prepnut spat, nema mat hru
        # zapisanu ako pracu. Ide do suhrnu ako `world` (`_close_hr_session`)
        # a urcuje, ci hlaska smie mat hlas (nizsie, `open_session`).
        self._session_world = self.world
        # Pokojovy tep z predchadzajucich vecerov. Bez neho appka v suvislom
        # strese nevidi ziadnu zataz - zakladna sa jej dotiahne za stresom a
        # pocita voci nemu (viz `hr_stats.dlhodoba_zakladna`).
        try:
            historia = self._history_sessions()
            # Zakladna zo VSETKYCH relacii - telo je jedno (B3-worlds).
            self.hr_stats.long_baseline = hr_stats.dlhodoba_zakladna(historia)
            # Kriticky tep a prah zataze len z HERNYCH relacii (B3-worlds,
            # viz `ALGORITMUS_SVET`). Plati aj pre pracovnu relaciu - tam
            # sa hlaska aj tak ukaze len obrazom.
            herna = hr_stats.sessions_in_world(historia, self.ALGORITMUS_SVET)
            # Kriticky tep sa prepocita RAZ ZA RELACIU, nie priebezne.
            # Menit skalu zataze uprostred vecera by znamenalo, ze okna z
            # prvej polovice a z druhej sa nedaju porovnat - to iste
            # pravidlo, ake plati pre prahy spustaca (zadanie §3.3).
            self.hr_critical_bpm = int(hr_stats.dynamicky_kriticky(
                herna, baseline=self.hr_stats.long_baseline))
            # Prah zataze z vlastnych relacii. None = este nie je z coho,
            # vtedy ostavaju cisla pre priemerneho hraca.
            self._prah_z_dat = hr_stats.dynamicky_prah_zataze(
                herna, baseline=self.hr_stats.long_baseline,
                critical=self.hr_critical_bpm)
            # To iste pravidlo ako vypocet (`je_dost_dlha`): pokazene
            # `duration_s` tu nesmie vyhodit vynimku, inak by `except` nizsie
            # zahodil aj dlhodobu zakladnu.
            self._prah_z_relacii = len([
                r for r in hr_stats.ciste_relacie(herna)
                if hr_stats.je_dost_dlha(r)])
        except Exception:
            self.hr_stats.long_baseline = None
            app_log.exception("dlhodoba zakladna / kriticky tep zlyhali")
        self.hr_stats.critical_bpm = self.hr_critical_bpm
        self.hud.configure(critical_bpm=self.hr_critical_bpm)
        self._refresh_kriticky_popis()
        self._refresh_citlivost_detail()
        self.hr_stats.reset_session()
        # Prvych par sprav s krokmi zapis do denniku - z nich sa nastavi prah.
        self._metrics_log_left = 10
        # Zaznam aktivity sa vynuluje spolu s relaciou, aby meracie okna
        # nevideli nic spred zapnutia senzora.
        self.activity.reset_session()
        # Riadok "ziadna pauza vo vstupe" je raz za relaciu.
        self._nonstop_input.reset()
        # Podiel tichych hlasok klesne po kalibracii (25 % -> 10 %), ale
        # nikdy nie na nulu. Pocet relacii sa berie z historie.
        self._cue_log = []
        # Prahy sa beru AZ TU, cize az pri novej relacii (§3.3): menit ich
        # uprostred vecera znamena merat pohyblivy ciel.
        #
        # Poradie je zamerne. Najprv volba "ako casto sa ozvem" (cely
        # slovnik, takze prepnutie spat na "bezne" naozaj vrati vychodiskove
        # cisla a nenecha visiet stare), az potom vyvojarska vrstva, ktora
        # je jemnejsi nastroj a smie prekryt hocico.
        # Cisla pre priemerneho hraca z literatury; prvá relácia bezi na nich.
        self.cue_trigger.params.update(trigger.default_params())
        if getattr(self, "_prah_z_dat", None) is not None:
            self.cue_trigger.params["stress_threshold"] = float(self._prah_z_dat)
        if getattr(self, "_dev_params", None):
            self.cue_trigger.params.update(self._dev_params)
        podiel = self._silent_share_for_next_session()
        # REBRIK HLASKY (0.2): na akom stupni bezi tato relacia. Pauza =
        # automat sa vobec nenatiahne (diagnostika bezi dalej).
        self._urci_stupen_hlasky()
        if self._cue_rung == rebrik.PAUZA:
            self.cue_trigger.params["cues_enabled"] = False
        self._snooze_po_hlaske = None
        self._snooze_rel_s = 0.0
        self._snooze_rel_od = None
        # PRACA = LEN OBRAZ (B3-worlds, rozhodnutie zadavatela). Kto sa v
        # praci sustredi, nema mu do toho nic hovorit ani cinkat - vizual v
        # rohu oka staci. Plati pre celu relaciu podla sveta, v ktorom zacala.
        # Pod stupnom hlasu (rebrik) tiez len obraz - `hlas` v udalosti tak
        # hovori pravdu o tom, co mohlo zaznet.
        self.cue_trigger.open_session(silent_share=podiel,
                                      voice=self._session_world != "work"
                                      and self._cue_rung == rebrik.HLAS)
        # "TERAZ NIE" PLATI AJ CEZ NOVU RELACIU. `open_session` automat
        # zdvihne - a nova relacia sa da otvorit aj pocas stisenia (stop a
        # start, zapnutie senzora, zmena IP), odkedy snooze pocuvanie
        # nezastavuje (24. 9.).
        if getattr(self, "_snooze_job", None) is not None:
            self._suspend_cue_trigger(trigger.A_SNOOZE)
            # Aj do `snoozed_s` novej relacie - od jej zaciatku.
            if meria:
                self._snooze_rel_od = time.time()
        # MERIA SA LEN, KED SVIETI ZELENA.
        #
        # `hr_stats.add()` bezi pri kazdej vzorke bez ohladu na to, ci appka
        # pocuva - takze relacia otvorena SAMOTNYM ZAPNUTIM SENZORA by
        # zbierala trvanie, pasma aj zakladnu z casu, v ktorom hlaska nemohla
        # padnut. V exporte by z toho bola "relacia", v ktorej sa nemeralo
        # nic, a v pocte vecerov do zaveru by sa ratala ako plnohodnotna.
        #
        # `meria=False` teda nechá senzor bezat (aby bolo vidiet tep pri
        # parovani), ale relaciu NEOTVORI. Otvori ju az `start_listening`.
        self._hr_session_open = bool(meria)
        if meria:
            # Nova relacia: vynuluj sledovac viditelnosti HUD-u.
            self._hud_vis_s = 0.0
            self._hud_active_s = 0.0
            self._hud_tick_t = time.time()
        if prepoj:
            self.hud.set_connected(False)
        self.hud.configure(critical_bpm=self.hr_critical_bpm)
        self.refresh_hr_status_label()

    def stop_heart_rate_monitor(self):
        self.heart_rate_monitor.stop()
        self._cancel_no_client_check()
        # generacia 0 = ziadne bezuce vlakno, takze uz odoslane (a este
        # nedorucene) aktualizacie z prave zastaveneho vlakna sa zahodia
        self._hr_generation = 0
        self._hr_state = "disconnected"
        self._hr_last_bpm = None
        self._hr_over_since = None
        self._hr_client_linked = False
        # Senzor vypol hrac - to uz nie je vypadok. Relacia sa zatvara az
        # nizsie, takze vypadok, ktory prave trval, sa do suhrnu este zarata.
        self._hr_lost = False
        self._hr_lost_od = None
        self._close_hr_session()
        self.hud.set_connected(False)
        self.hr_stats.clear_live()
        self.refresh_hr_status_label()
        self.log(tr("log.hr_disabled"))

    # Ak sa do tolkoto ms po zapnuti nepripoji ani jeden klient, stav sa
    # zmeni z "connecting" na "no_client" - iny problem, iny text (B2).
    HR_NO_CLIENT_AFTER_MS = 20000

    def _schedule_no_client_check(self):
        self._cancel_no_client_check()
        try:
            self._hr_no_client_job = self.root.after(
                self.HR_NO_CLIENT_AFTER_MS, self._hr_no_client)
        except Exception:
            self._hr_no_client_job = None

    def _cancel_no_client_check(self):
        job = getattr(self, "_hr_no_client_job", None)
        if job is not None:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
            self._hr_no_client_job = None

    def _hr_no_client(self):
        self._hr_no_client_job = None
        # Stále "connecting" a nikto sa nepripojil → povedz to narovinu.
        if self._hr_state == "connecting" and self.hr_monitoring_enabled:
            self._hr_state = "no_client"
            self.refresh_hr_status_label()
            self._refresh_kamae_state_text()

    def _hr_ip_display(self):
        """IP pre riadok v denniku appky - skryta, kym ju hrac neodkryje
        (0.0.0.0 sa neskryva, nie je to adresa PC)."""
        ip = self.hr_ip if self.hr_ip.strip() else ANY_INTERFACE
        return netinfo.ip_for_screen(ip, self.show_ip)

    def set_show_ip(self, show):
        """Ukazat / Skryt IP pre celu appku (okno parovania aj pole IP v
        Nastaveniach). Len v pamati - po restarte je IP znova skryta, preto
        to `save_settings` ZAMERNE nezapisuje."""
        self.show_ip = bool(show)
        var = getattr(self, "show_ip_var", None)
        if var is not None:
            try:
                if bool(var.get()) != self.show_ip:
                    var.set(self.show_ip)
            except Exception:
                pass
        self._apply_hr_ip_mask()

    def _apply_hr_ip_mask(self):
        """Pole IP v Nastaveniach kresli skutocnu adresu bodkami, kym nie je
        `show_ip`. Prazdne pole a 0.0.0.0 ostavaju citatelne."""
        entry = getattr(self, "hr_ip_entry", None)
        var = getattr(self, "hr_ip_var", None)
        if entry is None or var is None:
            return
        try:
            maska = netinfo.entry_mask(var.get(), self.show_ip)
            if str(entry.cget("show")) != maska:
                entry.configure(show=maska)
        except Exception:
            pass            # pole uz neexistuje (prestavba UI)

    def on_hr_bpm(self, bpm, generation):
        self.ui_call(lambda: self._apply_hr_bpm(bpm, generation))

    def _apply_hr_bpm(self, bpm, generation=None):
        if generation is not None and generation != self._hr_generation:
            return                      # sprava od uz zastaveneho vlakna
        self._hr_state = "connected"
        self._hr_bind_retries = 0       # port sa uvolnil, pocitadlo odznova
        self._hr_last_bpm = bpm
        self.hr_stats.add(bpm)
        # Vypadok konci az PLATNOU vzorkou - tou istou, ktora v `hr_stats`
        # uzavrie slepy cas, aby riadok v denniku a suhrn nehovorili ine.
        if self._hr_lost and self.hr_stats.last_bpm is not None:
            self._tep_je_spat()
        self.hud.set_connected(True)
        self._refresh_hud_session_text()
        self._refresh_dnes_stats()
        self.refresh_hr_status_label()
        # Pás flipne z "Čakám na tep" na "Sledujem tep", len čo dáta chodia
        # (bug A2 - pás sa dovtedy prekresľoval len z `_set_enso_armed`).
        self._refresh_kamae_state_text()
        now = time.time()
        # Faza 2: spusta ZATAZ drziaca nad prahom, nie surove BPM prekracujuce
        # kriticku hranicu. Zataz uz v sebe nesie `sustained` - podiel
        # poslednych dvoch minut nad zakladnou - takze "spicka po headshote
        # nie je stres" je zabudovane v samotnom cisle, nie dolepene.
        # ZATAZ SA PODAVA AUTOMATU LEN POCAS RELACIE.
        #
        # Volalo sa to pri kazdej vzorke, aj ked relacia nebezala (senzor
        # zapnuty, pocuvanie vypnute). Automat sa teda natiahol, prstenec na
        # ense sa rozsvietil - a `_tick_cue_trigger` sa kvoli
        # `_hr_session_open` hned vracal, takze uz ho nemal co zhodit.
        # Prstenec "natiahnute" potom svietil donekonecna a tvrdil stav,
        # ktory neexistoval.
        if not self._hr_session_open:
            return
        self.cue_trigger.resume(now)
        # Pocas kalibracie (prvych ~30 vzoriek relacie) sa nic nenatiahne -
        # viz `trigger.CueTrigger.note_load`.
        # `zona` je pre BRANU hlasky (0.2): pasmo TEPU (`zone_of_bpm`, to
        # iste slovo ako na HUD-e), None ked ho appka nepozna. Nikdy nie
        # pasma zataze - nad hranicou vysokeho tepu hlas nezaznie.
        udalost = self.cue_trigger.note_load(
            self.hr_stats.stress, now,
            calibrating=self.hr_stats.is_calibrating,
            zona=self.hr_stats.known_zone)
        if udalost is not None:
            self._on_cue_event(udalost)

    def on_hr_metrics(self, metrics, generation):
        self.ui_call(lambda: self._apply_hr_metrics(metrics, generation))

    def _apply_hr_metrics(self, metrics, generation=None):
        """Kroky a rychlost z hodiniek. Bezi na Tk vlakne ako `_apply_hr_bpm`."""
        if generation is not None and generation != self._hr_generation:
            return
        try:
            self.hr_stats.note_metrics(steps=metrics.get("steps"),
                                       speed=metrics.get("speed"),
                                       zdroj=metrics.get("zdroj"))
        except Exception:
            app_log.exception("kroky z hodiniek sa nepodarilo zapisat")
            return
        if self._metrics_log_left > 0:
            self._metrics_log_left -= 1
            app_log.info("hodinky posielaju [%s]: kroky=%s rychlost=%s "
                         "(za minutu %s)", metrics.get("zdroj") or "bez mena",
                         metrics.get("steps"), metrics.get("speed"),
                         self.hr_stats.steps_per_min())

    def on_hr_status(self, status, generation):
        self.ui_call(lambda: self._apply_hr_status(status, generation))

    def _apply_hr_status(self, status, generation=None):
        if generation is not None and generation != self._hr_generation:
            return                      # sprava od uz zastaveneho vlakna
        kind, payload = status
        if kind == "bound_any":
            # zadanu IP toto PC nema - pocuvame na vsetkych sietach, nech
            # hracovi funkcia nezomrie kvoli jednemu zlemu cislu
            self.log(tr("log.hr_bind_fallback",
                        ip=netinfo.ip_for_screen(payload, self.show_ip)))
            return
        if kind == "client":
            # hodinky drzia spojenie - to este NEznamena, ze posielaju tep
            self._cancel_no_client_check()      # klient prisiel (B2)
            self._hr_client_linked = True
            self._hr_state = "linked"
            self.log(tr("log.hr_client_connected"))
        elif kind == "client_gone":
            self._zaznamenaj_vypadok(kind)      # PRED clear_live
            self.hud.set_connected(False)
            self.hr_stats.clear_live()
            self._hr_client_linked = False
            self._hr_state = "connecting"
            self._hr_last_bpm = None
            self._hr_over_since = None
            self._suspend_cue_trigger(trigger.A_TEP_VYPADOL)
            self.log(tr("log.hr_client_gone"))
        elif kind == "connecting":
            self._hr_state = "connecting"
            self._hr_last_bpm = None
        elif kind == "disconnected":
            # tep prestal chodit; ak hodinky spojenie stale drzia, je to
            # "pripojene, ale bez dat", nie "odpojene" - iny problem, iny text
            self._zaznamenaj_vypadok(kind)      # PRED clear_live
            self.hud.set_connected(False)
            self.hr_stats.clear_live()
            self._hr_state = "linked" if self._hr_client_linked else "disconnected"
            self._hr_last_bpm = None
            self._hr_over_since = None
            self._suspend_cue_trigger(trigger.A_TEP_VYPADOL)
        elif kind == "busy":
            # OBSADENY PORT JE DOCASNY STAV, NIE ROZHODNUTIE HRACA.
            #
            # Doteraz sa sem padalo spolu s "error": appka vypla
            # `hr_monitoring_enabled` a hned to ULOZILA na disk. Z kolizie,
            # ktora trva par sekund (druha instancia appky sa prave zatvara,
            # alebo ju niekto omylom spustil dvakrat), sa tak stalo trvale
            # nastavenie - senzor ostal vypnuty aj potom, co sa port uvolnil,
            # a hrac nemal ako zistit preco. Jediny signal bol riadok v
            # DENNIKU, ktory je predvolene zabaleny.
            #
            # Teraz sa prepinac nechava zapnuty, do nastaveni sa neuklada nic
            # a vazba sa par krat zopakuje. Az ked port drzi niekto natrvalo,
            # sa senzor vzda - a vtedy to uz naozaj je stav, o ktorom ma
            # zmysel hraca informovat.
            self._hr_state = "busy"
            self._hr_last_bpm = None
            self._hr_over_since = None
            self._hr_client_linked = False
            self._hr_lost = False           # port, nie vypadok tepu
            self._hr_lost_od = None
            self._hr_generation = 0
            self._close_hr_session()
            self._hr_bind_retries = getattr(self, "_hr_bind_retries", 0) + 1
            if self._hr_bind_retries <= self.HR_BIND_RETRIES:
                self.log(tr("log.hr_port_busy_retry", port=payload,
                            n=self._hr_bind_retries, z=self.HR_BIND_RETRIES))
                self._hr_retry_job = self.root.after(
                    self.HR_BIND_RETRY_MS, self._retry_hr_bind)
            else:
                self.hr_monitoring_enabled = False
                if self.hr_enabled_var is not None:
                    self.hr_enabled_var.set(False)
                self.save_settings()
                # Stav sa MUSÍ zmeniť z "busy" - inak štítok navždy tvrdí
                # "skúšam znova", hoci sme to vzdali (B3).
                self._hr_state = "busy_gave_up"
                self.log(tr("log.hr_port_busy", port=payload))
            self.refresh_hr_status_label()
            self._refresh_dnes_stats()
            self._refresh_kamae_state_text()   # pás nesmie tvrdiť "sledujem"
            return
        elif kind == "error":
            self._hr_state = "disconnected"
            self._hr_last_bpm = None
            self._hr_over_since = None
            self._hr_client_linked = False
            self._hr_lost = False           # senzor je vypnuty, nie slepy
            self._hr_lost_od = None
            self.hr_monitoring_enabled = False
            if self.hr_enabled_var is not None:
                self.hr_enabled_var.set(False)
            self.save_settings()
            # Prepinac sa prave vypol, ale relacia zostavala OTVORENA: uz
            # sa nedala vypnut cez `stop_heart_rate_monitor` (ten vola len
            # `on_hr_toggle`, a prepinac je uz v polohe vypnute), takze sa
            # ulozila az pri ukonceni appky - a `summary()` medzitym ratal
            # `duration_s` z `time.time()`, cize relacia narastla o cely
            # zvysok vecera. Zatvarame ju tu, kym su cisla este pravdive.
            # Generacia 0 zaroven zahodi spravy z uz mrtveho vlakna.
            self._hr_generation = 0
            self._close_hr_session()
            self.log(tr("log.hr_socket_error", err=payload))
        self.refresh_hr_status_label()
        self._refresh_dnes_stats()
        # Pás aj text pod ensom musia sledovať SKUTOČNÝ stav spojenia
        # (connecting / disconnected / client_gone), nie len prepínač — inak
        # tvrdia "Sledujem tep" aj keď hodinky vypadli (bug A2).
        self._refresh_kamae_state_text()

    def _zaznamenaj_vypadok(self, kind):
        """Tep, ktory appka pocula, prestal chodit - zapamataj si to.

        Vola sa z vetiev `disconnected` a `client_gone` PRED `clear_live`
        (potom uz `hr_stats` nevie, kedy prisla posledna vzorka). Len ked
        appka tep naozaj pocula: vypadok pred prvou vzorkou je "este nic
        neprislo" a ma vlastny text. Obe udalosti mozu prist za sebou (TCP
        spojenie padne az po 12 s ticha, alebo naopak) - druha uz `_hr_last_bpm`
        nema, takze sa ten isty vypadok nerata dvakrat.

        ZIADNY NOVY CASOVAC, ZVUK ANI OKNO. Hranica 12 s je ta ista ako doteraz
        (`heart_rate.STALE_AFTER_S`); tu sa len prestane tvarit, ze hodinky
        ani neboli sparovane (Dnes necha zivy blok a stopu relacie).
        """
        if self._hr_last_bpm is None:
            return
        self._hr_lost = True
        self._hr_lost_od = self.hr_stats.last_beat_ts
        try:
            self.hr_stats.note_dropout(od=self._hr_lost_od)
        except Exception:
            app_log.exception("vypadok tepu sa nepodarilo zapisat")
        app_log.info("tep vypadol (%s)", kind)

    def _tep_je_spat(self):
        """Prva platna vzorka po vypadku: jeden riadok do dennika, nic viac."""
        od = self._hr_lost_od
        self._hr_lost = False
        self._hr_lost_od = None
        if od is None:
            return
        sekund = max(0, int(round(self.hr_stats.last_beat_ts - od)))
        self.log(tr("log.hr_back", s=sekund))
        app_log.info("tep je spat po %d s", sekund)

    # POZN: tu bol `_maybe_trigger_hr_breathing` - starý automatický spúšťač
    # z fázy 1 (tep nad kritickou 5 s → dýchací kruh). Už ho nič nevolalo,
    # nahradil ho `trigger.CueTrigger` (záťaž nad prahom 90 s, odklad na
    # pauzu). Zmazaný aj s konštantami HR_TRIGGER_* (B28). Pomocníci
    # `_hr_overlay_available` / `_warn_hr_overlay_disabled_once` ostávajú -
    # používa ich živá cesta hlášok.

    def _hr_overlay_available(self):
        """True, ak ma aspon JEDEN slot zapnuty in-game vizual.

        Do 19. 9. sa pytala vylucne na slot 3 (dychaci kruh). To bolo spravne,
        kym vsetky hlasky chodili na ten jeden slot - lenze od zavedenia
        striedania kategorii (`_dalsi_cue_slot`) sa hlaska moze dorucit na
        hociktory zo styroch. Brana teda povolila hlasku, ked bezal dychaci
        kruh, a poslala ju na slot, ktory kreslit nemal - alebo naopak
        umlcala appku, ktora mala tri vizualy zapnute a len ten stvrty nie.

        Samotny vyber uz zapnutost vizualu zohladnuje, takze tu staci, ze
        existuje aspon jeden pouzitelny.
        """
        try:
            return any(bool(cfg["enabled"]) for cfg in self.overlay_configs)
        except (KeyError, TypeError):
            return False

    def _warn_hr_overlay_disabled_once(self):
        if self._hr_overlay_warned:
            return
        self._hr_overlay_warned = True
        self.log(tr("log.hr_overlay_disabled"))

    def _retry_hr_bind(self):
        """Skusi znova otvorit UDP prijem po obsadenom porte.

        Nevola `on_hr_toggle` - prepinac je stale zapnuty a nesmie sa hybat.
        Otvara priamo novy socket, rovnako ako `_open_hr_session` pri starte.
        """
        self._hr_retry_job = None
        if not self.hr_monitoring_enabled:
            return                      # hrac medzitym vypol sam
        try:
            self._hr_state = "connecting"
            self.refresh_hr_status_label()
            self._hr_generation = self.heart_rate_monitor.start(self.hr_ip,
                                                                self.hr_port)
            # SOCKET JE SPÄŤ - ALE RELÁCIA SA V "busy" VETVE ZAVRELA.
            #
            # Bez tohto by appka po obnovenom porte ukazovala živý tep, no
            # `_hr_session_open` by ostalo False - `_tick_cue_trigger` sa pri
            # zatvorenej relácii hneď vracia, takže by sa NIKDY neozvala a na
            # konci by neuložila NIČ. Pás pritom sľubuje "sledujem". Otvárame
            # ju nanovo (siete sa to nedotýka; `start()` ju už obnovil),
            # rovnako ako pri štarte. Dáta spred výpadku sú už uložené
            # (`busy` vetva volá `_close_hr_session`, ktorý ukladá).
            self._open_hr_session(prepoj=False, meria=self.listening)
            self._schedule_no_client_check()   # čerstvých 20 s na klienta (B2)
        except Exception:
            app_log.exception("opakovana vazba na UDP port zlyhala")

    def _hr_status_display(self):
        pal = self.pal
        if self._hr_state == "connected" and self._hr_last_bpm is not None:
            # farby pasiem, nie success/danger - inak by stav tepu svietil
            # inou zelenou, nez akou appka kresli pokoj (viz theme.ZONE_TOKENS)
            zone = "critical" if self._hr_last_bpm > self.hr_critical_bpm else "calm"
            return f"❤️ {self._hr_last_bpm} BPM", theme_mod.zone_color(pal, zone)
        if self._hr_state == "linked":
            return tr("settings.hr_status_waiting"), pal["warn"]
        if self._hr_state == "busy":
            # Vlastny stav, nie "Odpojene": hrac vidi presne to, co sa deje,
            # priamo pri prepinaci a nemusi rozbalovat dennik.
            return tr("settings.hr_status_busy"), pal["warn"]
        if self._hr_state == "busy_gave_up":
            # Pokusy vycerpane - uz to neskusa, tak to ani netvrdi (B3).
            return tr("settings.hr_status_busy_gave_up"), pal["danger"]
        if self._hr_state == "connecting":
            return tr("settings.hr_status_connecting"), pal["text_dim"]
        if self._hr_state == "no_client":
            # Počúvame, ale za N s sa nikto nepripojil - iný problém než
            # "pripája sa" (najčastejšie firewall / iná Wi-Fi) (B2).
            return tr("settings.hr_status_no_client"), pal["warn"]
        return tr("settings.hr_status_disconnected"), pal["text_dim"]

    def refresh_hr_status_label(self):
        if self.hr_status_label is None:
            return
        text, color = self._hr_status_display()
        try:
            self.hr_status_label.configure(text=text, text_color=color)
        except Exception:
            pass

    def _tick_session(self):
        """Raz za sekundu obnovi "naposledy sa ozvala pred X min" a pri
        otvorenej relacii skontroluje exkluzivny fullscreen.

        Popri nom bezi este `_tick_activity` (4x za sekundu); vsetko ostatne
        sa prekresluje az na zaklade prichadzajucich dat.

        POZN: bol tu aj `_refresh_kamae_metrics()` - tri cisla vpravo v
        pase. S ich odstranenim (viz `ui_kit.KamaeBar`) uz pas nema co
        posuvat po sekundach.
        """
        try:
            # "Naposledy sa ozvala pred X min" sa pocita z `time.time()` az
            # pri prekresleni. Vsetky ostatne cesty k `_refresh_dnes_stats`
            # visia na prichadzajucom tepe, takze bez tohto riadku sa cislo
            # zastavilo na hodnote spred poslednej vzorky a uz sa nepohlo -
            # a po vypadku hodiniek klamalo donekonecna.
            self._refresh_last_cue()
        except Exception:
            pass
        # Exkluzívny fullscreen: Windows v ňom naše overlay okná nevykreslí,
        # takže vizuál (jadro appky) ticho zmizne. Kontrola má zmysel LEN keď
        # je popredím hra — čo počas relácie väčšinou je, a nikdy to nie je
        # počas `start_heart_rate_monitor`, kde kontrola pôvodne bola a bola
        # preto mŕtva (bug A3). Raz za spustenie appky (flag
        # `_fullscreen_warned` sa nenuluje) - a len ako odhad: rovnako veľké
        # je aj okno bez okrajov, preto text hovorí „ak vizuály nevidíš“.
        if getattr(self, "_hr_session_open", False):
            try:
                self._warn_exclusive_fullscreen_once()
            except Exception:
                pass
        try:
            self.root.after(1000, self._tick_session)
        except Exception:
            pass

    def _tick_activity(self):
        """4x za sekundu sa spyta Windowsu, ako dlho je hrac necinny.

        Je to jedno `GetLastInputInfo` - ziadny hook, ziadna informacia o
        tom, co hrac stlacil. Beha aj mimo relacie, aby `pause_s()` malo
        zmysel hned, ked sa senzor zapne; zaznam do meracich okien sa pri
        zapnuti senzora aj tak vynuluje.

        `after` id sa drzi, aby sa dalo pri ukonceni zrusit - inak by sa
        4x za sekundu zvysovala sanca, ze jeden callback dobehne az nad
        rozobratym oknom.
        """
        try:
            idle = self.activity.poll()
        except Exception:
            idle = None
        # Krivka aktivity do relacie - z nej sa neskor spocita, kedy sa
        # naozaj hralo a kedy sa sedelo v menu. Zapisuje sa LEN pocas
        # relacie, rovnako ako vsetko ostatne: mimo nej by to len riedilo
        # priemer casom, ked hrac appku ani nepouziva.
        if idle is not None and getattr(self, "_hr_session_open", False):
            try:
                self.hr_stats.note_activity(idle <= measure.ACTIVE_IDLE_MS)
            except Exception:
                pass
        try:
            self._tick_nonstop_input()
        except Exception:
            app_log.exception("vstup bez pauzy: tick zlyhal")
        try:
            self._tick_cue_trigger()
        except Exception:
            app_log.exception("spustac hlasky: tick zlyhal")
        try:
            self._activity_job = self.root.after(
                int(activity.POLL_S * 1000), self._tick_activity)
        except Exception:
            self._activity_job = None

    def _tick_nonstop_input(self, now=None):
        """Tichy riadok na Dnes, ked appka uz dlho nevidela ani kratku pauzu
        vo vstupe (`activity.NonstopInputWatch`).

        Stalo sa to zadavatelovi: gyroskop ovladaca hlasil Windowsu vstup
        kazdych ~16 ms a appka nemala kedy najst pauzu. Rata sa, len ked
        appka pocuva a tep chodi (hrac je pri PC). LEN na Dnes - nie v hre,
        nie v HUD-e; hrac to uvidi, ked sa na appku sam pozrie.
        """
        now = time.time() if now is None else now
        watching = bool(self.listening
                        and getattr(self, "_hr_session_open", False)
                        and self._hr_state == "connected"
                        and self._hr_last_bpm is not None
                        and not getattr(self, "_hr_lost", False))
        try:
            potrebna = float(self.cue_trigger.params.get("pause_s", 2.5))
        except Exception:
            potrebna = 2.5
        ukaz = self._nonstop_input.update(
            now, self.activity.pause_s(now), watching, pause_needed_s=potrebna)
        text = ""
        if ukaz and self.listening:
            text = tr("dnes.nonstop_input",
                      min=int(self._nonstop_input.after_s // 60))
        if text != getattr(self, "_dnes_nonstop_text", ""):
            if text:
                app_log.info("vstup: %d min bez jedinej pauzy - riadok na Dnes",
                             int(self._nonstop_input.after_s // 60))
            self._dnes_nonstop_text = text
            self._refresh_dnes_backdrop(force=False)

    # ---------- automaticky spustac hlasky (faza 2) ----------

    def _suspend_cue_trigger(self, reason):
        """Zrusi natiahnutie. Volat pri vypadku tepu aj pri snooze -
        polovicne natiahnuty stav neexistuje, 90 s sa pocita odznova."""
        try:
            udalost = self.cue_trigger.suspend(reason)
        except Exception:
            app_log.exception("spustac hlasky: suspend zlyhal")
            return
        if udalost is not None:
            self._on_cue_event(udalost)
        # `suspend` vrati udalost LEN ked bol automat natiahnuty; ked nebol,
        # vrati None a `_on_cue_event` sa nezavola. Prstenec sa preto zhadzuje
        # tu, nie tam - inak by po snooze v nenatiahnutom stave ostal svietit.
        self._set_enso_armed(False)

    def _kamae_state_text(self):
        """(nadpis, podtitulok) pre dychajuci pas - TRI stavy, nie dva.

        Zadanie posuva tazisko stranky Dnes z cisel na stav, a "natiahnute"
        je stav, ktory sa doteraz nedal precitat nikde inak nez z prstenca na
        ense - a ten ma 68 px. Pas je najvacsi prvok okna, takze vetu, ktora
        povie PRECO sa nic nedeje, unesie prave on.

        Zamerne bez odpoctu ("zostava 47 s"). Merat hracovi vlastny stav pred
        ocami je presne to, co ma appka nerobit; veta hovori, ze sa caka, a
        to staci.
        """
        if not self.listening:
            return self._kamae_zastavene()
        # STVRTY STAV: pocuvam, ale nemam z coho.
        #
        # Bez zdroja tepu `start_listening` prijem vobec nespusti a
        # `_tick_cue_trigger` sa hned vracia - appka teda naozaj nesleduje
        # nic. Pas pritom hlasil "Sledujem tep a cakam na spravnu chvilu",
        # cize vetu, ktora nebola pravdiva. Hrac isiel hrat s tym, ze appka
        # bezi, a cely vecer cakal na hlasku, ktora nemala odkial prist.
        if not self.hr_monitoring_enabled:
            return tr("kamae.no_watch"), tr("kamae.no_watch_sub")
        # POCUVAM, ALE TEP NECHODI.
        #
        # Doteraz sa tu vratilo "Sledujem tep a cakam..." len na zaklade
        # prepinaca - aj ked hodinky vypadli, port bol obsadeny alebo sa este
        # nic nepripojilo. Pas je najvacsi prvok okna; tvrdit na nom
        # "sledujem", ked appka nema z coho, je presne ten bug, co sa uz raz
        # opravoval pre vypnuty senzor. Pravda podla STAVU SPOJENIA, nie
        # prepinaca: naozaj sledujeme, len ked chodi tep.
        if self._hr_state != "connected" or self._hr_last_bpm is None:
            # Nadpis "Cakam na tep" plati aj pri vypadku. Veta pod nim nie:
            # "z hodiniek zatial nic nechodi" patri pred prvu vzorku, nie
            # doprostred vecera, ked tep chodil a prestal.
            if getattr(self, "_hr_lost", False):
                return tr("kamae.no_hr"), tr("kamae.lost_sub")
            return tr("kamae.no_hr"), tr("kamae.no_hr_sub")
        # "TERAZ NIE" (24. 9.): pocuva a meria sa dalej, ale hlaska neprijde.
        # "Cakam na spravnu chvilu" by slubovalo presne to, co hrac vypol.
        if getattr(self, "_snooze_job", None) is not None:
            return tr("kamae.snoozed"), tr("kamae.snoozed_sub",
                                           until=self._snooze_do())
        if self._cue_armed:
            return tr("kamae.armed"), tr("kamae.armed_sub")
        # Rebrik hlasky je na pauze (`rebrik.py`): "cakam na spravnu chvilu"
        # by slubovalo hlasku, ktora v tejto relacii neprijde.
        if (getattr(self, "_hr_session_open", False)
                and getattr(self, "_cue_rung", None) == rebrik.PAUZA):
            return tr("kamae.running"), tr("kamae.paused_sub")
        return tr("kamae.running"), tr("kamae.running_sub")

    def _refresh_kamae_state_text(self):
        """Prepise pas, ked sa stav zmenil. Vola sa zo `_set_enso_armed`,
        cize z tej istej cesty ako prstenec - aby sa text a znacka nemohli
        rozist."""
        bar = getattr(self, "kamae", None)
        if bar is None:
            return
        try:
            # Pas nesie stav POHYBOM (dycha/stoji), nie textom - preto staticka
            # napoveda o vypinaci; samotny stav (Zastavene/Pocuvam/...) je v strede
            # stranky (hero), aby sa neduplikoval. Viz KamaeBar docstring.
            bar.set_texts(tr("kamae.bar_title"), tr("kamae.bar_sub"))
        except Exception:
            app_log.exception("dychajuci pas: prepis textu zlyhal")
        self._refresh_dnes_state_text()

    def _refresh_last_cue(self):
        """Riadok "naposledy sa ozvala pred X min".

        Kym v relacii nic nebolo, riadok sa NEZOBRAZI. Prazdny riadok s
        nulou by bol pocitadlo a appka ma ukazovat stav, nie skore.
        """
        if not hasattr(self, "dnes_canvas"):
            return
        cues = getattr(self.hr_stats, "cues", None) or []
        if not cues or not self.listening:
            if getattr(self, "_dnes_lastcue_text", ""):
                self._dnes_lastcue_text = ""
                self._refresh_dnes_backdrop(force=False)
            return
        posledna = cues[-1]
        # Popisok berieme z toho isteho slotu, z akeho ho berie
        # `_fire_somatic_cue` - podla atributu, nie podla poradia v zozname.
        slot = next((sl for sl in self.slots if sl.index == self.CUE_SLOT_INDEX), None)
        label = ((slot.text_value if slot is not None else "") or "").strip()
        minut = int(max(0.0, time.time() - float(posledna["ts"])) // 60)
        text = (tr("dnes.lastcue_now", label=label) if minut < 1
                else tr("dnes.lastcue", min=minut, label=label))
        if text != getattr(self, "_dnes_lastcue_text", ""):
            self._dnes_lastcue_text = text
            self._refresh_dnes_backdrop(force=False)

    def _silent_share_for_next_session(self):
        """Podiel tichych hlasok pre najblizsiu relaciu.

        Tiche rameno je JEDINY pevny bod merania - bez neho vyjde "funguje"
        vzdy, aj keby appka mlcala, lebo tep sa vracia dole aj sam. Preto sa
        nula neberie ako hodnota, ale ako nedopatrenie, a prepise sa.

        Presne to sa aj dialo: dialog ladenia sa predvyplnal zo
        `cue_trigger.silent_share`, co je pred prvou relaciou 0.0. Kto ho
        otvoril a dal Ulozit bez toho, aby na to pole siahol, vypol tiche
        rameno na cely beh appky a nikde o tom nebolo ani slovo.

        Kto ho naozaj chce vypnut, ma na to vyvojarsku vrstvu a uvidi tam
        varovanie - ale musi to urobit vedome.
        """
        podiel = getattr(self, "_dev_silent_share", None)
        try:
            podiel = float(podiel) if podiel is not None else None
        except (TypeError, ValueError):
            podiel = None
        if not podiel:                  # None aj 0.0
            # Len VLASTNE relacie: importovane (cudzie telo) by inak posunuli
            # pocitadlo - import 15 relacii by ukoncil fazu, v ktorej tiche
            # rameno mlci castejsie (1/4), skor nez sa tvoje telo porovnalo.
            podiel = trigger.silent_share_for(
                len(data_io.vlastne(self._history_sessions())))
        return podiel

    def _urci_stupen_hlasky(self):
        """REBRIK HLASKY (0.2, `rebrik.py`): stupen pre relaciu, ktora sa
        prave otvara. Vola ju `_open_hr_session`, az ked je svet opecateny.

        Vrchol dava svet (praca = len obraz, B3-worlds - svet sa tu nepocita
        znova, berie sa opecateny `_session_world`) a styl, ktory si hrac
        vybral (`cue_style`); rebrik ide len pod neho. Styl aj stupen platia
        pre celu relaciu, rovnako ako svet.

        Ked vyhodnotenie zlyha, relacia ide len obrazom: radsej tichsie nez
        hlas, ktory mal byt stiseny.
        """
        self._cue_style_rel = rebrik.normalize_cue_style(
            getattr(self, "cue_style", None))
        svet = getattr(self, "_session_world", hr_stats.WORLD_DEFAULT)
        try:
            stav = rebrik.stupen(
                hr_stats.sessions_in_world(self._history_sessions(), svet),
                svet=svet, styl=self._cue_style_rel)
        except Exception:
            app_log.exception("rebrik hlasky: vyhodnotenie zlyhalo")
            stav = {"stupen": rebrik.OBRAZ, "dovod": None}
        self._cue_rung = stav["stupen"]
        app_log.info("rebrik hlasky: %s (styl %s, dovod %s)",
                     self._cue_rung, self._cue_style_rel, stav.get("dovod"))
        return stav

    # ---------- styl hlasky (onboarding krok 5, Nastavenia -> Zvuk) ----------

    @staticmethod
    def _cue_style_label(styl):
        """'voice'/'sound'/'visual' -> veta z onboardingu v jazyku rozhrania."""
        return tr(dict(CUE_STYLE_LABELS)[rebrik.normalize_cue_style(styl)])

    def _cue_style_labels(self):
        return [tr(kluc) for _styl, kluc in CUE_STYLE_LABELS]

    def _on_cue_style_label(self, label):
        """Vyber v riadku "Ako sa ozyvam" (Nastavenia -> Zvuk)."""
        styl = next((s for s, kluc in CUE_STYLE_LABELS if tr(kluc) == label), None)
        if styl is None:
            return
        self._nastav_styl_hlasky(styl)
        self.save_settings()
        # Styl rozhoduje, ci sa texty hlasok posielaju na syntezu
        # (`_hlasky_hovoria`) - hlas sa pripravi hned, ked ho hrac zapne.
        self.schedule_pregenerate(200)

    def _prevezmi_styl_z_onboardingu(self, wizard):
        """Styl z 5. kroku onboardingu. None = hrac nevybral nic a ostava
        mu, co mal (novemu hracovi hlas - to iste ako odpoved "neviem")."""
        styl = getattr(wizard, "cue_style", None)
        if styl is not None:
            self._nastav_styl_hlasky(styl)

    def _nastav_styl_hlasky(self, styl):
        """Hrac vybral styl hlasky (onboarding alebo Nastavenia -> Zvuk).

        Novy styl je vrchol rebrika od dalsej relacie (`_urci_stupen_hlasky`).
        TICHSI styl navyse plati HNED, aj v beziacej relacii: veta pri volbe
        slubuje "nikdy nie hlasnejsie, nez tu vyberies", a hlas, ktory by
        dohral vecer po tom, co si hrac vybral len obrazok, by ju porusil.
        Hlasnejsi styl pocka na dalsiu relaciu - stupen sa uprostred relacie
        neprepocitava (ako svet) a byt tichsie, nez hrac dovolil, smie.
        Relacia si do suhrnu zapise styl a stupen, s ktorymi naozaj dobehla.
        """
        styl = rebrik.normalize_cue_style(styl)
        self.cue_style = styl
        app_log.info("styl hlasky: %s", styl)
        # Veta pod ukazkou v Nastaveniach -> Zvuk ide za stylom HNED - aj
        # hlasnejsim, lebo ukazka hra styl, nie stupen beziacej relacie.
        veta = getattr(self, "preview_sub_label", None)
        if veta is not None:
            try:
                veta.configure(text=self._preview_sub_text())
            except Exception:
                app_log.exception("ukazka: vetu sa nepodarilo prepisat")
        if not rebrik.je_tichsi(styl, getattr(self, "_cue_style_rel", None)):
            return
        self._cue_style_rel = styl
        svet = getattr(self, "_session_world", hr_stats.WORLD_DEFAULT)
        if (rebrik.vrchol(svet, styl) == rebrik.OBRAZ
                and getattr(self, "_cue_rung", rebrik.HLAS) == rebrik.HLAS):
            # Len obrazok: automat uz hlas neohlasi (`hlas` v udalosti hovori
            # pravdu) a `_fire_somatic_cue` pod stupnom hlasu nic neprehra.
            self._cue_rung = rebrik.OBRAZ
            automat = getattr(self, "cue_trigger", None)
            if automat is not None:
                automat.voice = False

    def _build_dnes_backdrop(self, parent, pal):
        """Zavesi prekreslenie stredu na zmenu velkosti.

        Uz nestavia widget - dojo, enso aj text kresli `_paint_dnes_canvas` na
        `self.dnes_canvas` (postaveny v `_build_dnes_page`). Tu sa len ulozi
        farba zavoja a zavesi `<Configure>`. Fotka je v `background.py`; ked nie
        je, `background.hero/load` vrati None a ostane pozadie temy.
        """
        self._backdrop_size = (0, 0)
        self._dnes_dojo_tk = None
        parent.bind("<Configure>", self._naplanuj_backdrop, add="+")

    # Kolko sa caka, kym sa rozmer ustali. Pri presune okna medzi monitormi
    # vystreli Windows `<Configure>` viackrat rychlo za sebou a KAZDY z nich
    # ma iny rozmer, takze straz na `_backdrop_size` ich nezachyti. Kedze
    # `background.load()` skaluje fotku cez LANCZOS priamo v Tk vlakne,
    # niekolko prepoctov tesne po sebe okno viditelne zasekne.
    BACKDROP_DEBOUNCE_MS = 150

    def _naplanuj_backdrop(self, _event=None):
        """Prepocita pozadie az ked sa rozmer na chvilu ustali.

        Nie je to kozmetika: pri plynulom tahani okna medzi obrazovkami by
        sa inak fotka preskalovala pri kazdom medzikroku, a z tych sa
        pouzije jediny - ten posledny.
        """
        job = getattr(self, "_backdrop_job", None)
        if job is not None:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
        try:
            self._backdrop_job = self.root.after(
                self.BACKDROP_DEBOUNCE_MS, self._refresh_dnes_backdrop)
        except Exception:
            # Okno sa zatvara - prekreslovat uz nie je co.
            self._backdrop_job = None

    def _refresh_dnes_backdrop(self, _event=None, force=False):
        """Prekresli stred stranky Dnes (dojo + enso + text) na `dnes_canvas`.

        Dva rezimy dojo: v ZASTAVENOM stave DOJO HERO, ktore dycha (lampiony,
        mesiac, odlesk stupaju a klesaju v tempe nadychu, viz `_tick_dnes`).
        Ked appka pocuva, tlmena fotka. Drahy LANCZOS sa robi len ked sa zmeni
        rozmer/dych/tema (kluc `_backdrop_size`); enso a text sa prekreslia
        vzdy (su lacne). Volaju sem: `<Configure>` (debounced), animacny tik,
        zmena stavu, `_EnsoHero._emit()` (set_live/armed/graduate/set_pal)."""
        canvas = getattr(self, "dnes_canvas", None)
        stred = getattr(self, "dnes_stred", None)
        if canvas is None or stred is None:
            return
        try:
            w, h = stred.winfo_width(), stred.winfo_height()
        except Exception:
            return
        if w < 40 or h < 40:
            return
        # --- 1) DOJO obrazok (drahy LANCZOS) - cachovany podla rozmeru/dychu/temy ---
        hero_on = bool(getattr(self, "_dnes_hero_on", False))
        faza = getattr(self, "_dnes_breath_phase", 0.0)
        breath = round(((1.0 - math.cos(2.0 * math.pi * faza)) / 2.0) * 8) / 8.0
        scrim = self.pal["bg"]
        kluc = (w, h, hero_on, breath if hero_on else 0, scrim)
        if force or _ImageTk is None or kluc != getattr(self, "_backdrop_size", None):
            self._backdrop_size = kluc
            self._dnes_dojo_tk = self._build_dojo_photo(w, h, hero_on, breath, scrim)
        # --- 2) prekresli canvas: dojo + enso + text (lacne) ---
        # POZOR: tu sa NESMIE volat `_ensure_dnes_tick()`. Prekreslenie bezi aj
        # zvnutra `_tick_dnes`, a ked `_tick_dnes` na zaciatku vynuluje job,
        # `_ensure_dnes_tick` by ho videl ako "nebezi" a rozbehol dalsi retazec
        # (alebo priamo zarekurzoval). Tik rozbieha len zmena stavu (nizsie).
        try:
            self._paint_dnes_canvas(canvas, w, h, getattr(self, "_dnes_dojo_tk", None))
        except Exception:
            app_log.exception("Dnes canvas: prekreslenie zlyhalo")

    def _build_dojo_photo(self, w, h, hero_on, breath, scrim):
        """PIL -> ImageTk dojo pre Canvas. Canvas pouziva FYZICKE pixely 1:1
        (na rozdiel od `CTkImage`, ktory si logicke sam nasobi), takze stavame
        rovno na (w, h) z `winfo_*` a kreslime bez prepoctu mierky."""
        if _ImageTk is None:
            return None
        try:
            peak = self.DNES_SCRIM_PEAK
            if hero_on:
                img = background.hero(w, h, breath=breath, scrim=scrim,
                                      scrim_peak=peak, blur=True,
                                      log=self.log_threadsafe)
            else:
                img = background.load(w, h, self.background_opacity,
                                      log=self.log_threadsafe)
                if img is not None and scrim:
                    try:
                        img = background._pridaj_scrim(img.convert("RGBA"),
                                                       scrim, peak)
                    except Exception:
                        pass
            if img is None:
                return None
            return _ImageTk.PhotoImage(img)
        except Exception:
            app_log.exception("Dnes dojo: obrazok zlyhal")
            return None

    def _cvfont(self, size, weight="normal", underline=False):
        """Tk font pre kreslenie na Canvas vo FYZICKYCH pixeloch.

        `create_text` nie je CTk widget, takze si mierku DPI musime dorobit
        sami: logicka velkost * mierka = fyzicke px (zaporny size = px, ktore
        `tk scaling` uz nenasobi). Fonty cachujeme - stavat ich 8x/s netreba."""
        mierka = getattr(self, "_dnes_mierka", 1.0)
        kluc = (size, weight, underline, round(mierka, 2))
        f = self._dnes_fonts.get(kluc)
        if f is None:
            f = tkfont.Font(family="Segoe UI", size=-max(1, int(round(size * mierka))),
                            weight=weight, underline=underline)
            self._dnes_fonts[kluc] = f
        return f

    def _paint_dnes_canvas(self, canvas, w, h, dojo):
        """Zlozi dojo + enso + text na jednu plochu - bez boxu a BEZ BLIKANIA.

        Proti blikaniu su dva kluce:
          (1) ak sa vizualne NIC nezmenilo, prekreslenie sa cele PRESKOCI -
              inak sa zastaveny stav prekresloval 8x/s (kazdy tik novy
              `PhotoImage`, aj ked je snimka rovnaka) a okno blikalo;
          (2) obrazkove polozky (dojo, enso) su TRVALE - meni sa im len obsah
              cez `itemconfigure`, nikdy sa nemazu (`delete`), takze ani
              animacia ensa neblikne. Textovy blok sa prestavia len pri zmene
              textu/rozmeru/temy (`_layout_dnes_items`).
        `render()` vracia cachovanu snimku (rovnaky objekt = rovnaka snimka),
        takze na porovnanie staci `id()`."""
        pal = self.pal
        try:
            mierka = (ctk.ScalingTracker.get_widget_scaling(self.dnes_stred)
                      or 1.0)
        except Exception:
            mierka = 1.0
        self._dnes_mierka = mierka
        enso = getattr(self, "enso", None)
        enso_px = max(48, int(self.ENSO_SIZE * mierka))
        pil = None
        if enso is not None:
            try:
                pil = enso.render(enso_px)
            except Exception:
                pil = None
        titul = getattr(self, "_dnes_titul", "") or ""
        veta = getattr(self, "_dnes_veta", "") or ""
        last = getattr(self, "_dnes_lastcue_text", "") or ""
        # Tichy riadok "ziadna pauza vo vstupe" ide pod neho, rovnako tlmeny.
        nonstop = getattr(self, "_dnes_nonstop_text", "") or ""
        if nonstop:
            last = f"{last}\n{nonstop}" if last else nonstop

        # (1) PRESKOC identicke prekreslenie.
        frame_sig = (w, h, round(mierka, 2), id(dojo), id(pil),
                     titul, veta, last, pal["bg"])
        if frame_sig == getattr(self, "_dnes_frame_sig", None):
            return
        self._dnes_frame_sig = frame_sig

        try:
            canvas.configure(bg=pal["bg"])
        except Exception:
            pass

        # (2) textovy blok + polohy prestavame len pri zmene textu/rozmeru/temy.
        text_sig = (w, h, round(mierka, 2), titul, veta, last, enso_px,
                    pal["text"], pal["text_dim"], pal["text_faint"])
        if (getattr(self, "_dnes_items", None) is None
                or text_sig != getattr(self, "_dnes_text_sig", None)):
            self._layout_dnes_items(canvas, w, h, mierka, enso_px,
                                    titul, veta, last, pal)
            self._dnes_text_sig = text_sig

        items = self._dnes_items or {}
        # dojo (trvala polozka vzadu) - vymen obrazok LEN ked sa naozaj zmenil.
        di = items.get("dojo")
        if di is not None:
            if dojo is not None:
                if dojo is not getattr(self, "_dnes_cur_dojo", None):
                    try:
                        canvas.itemconfigure(di, image=dojo, state="normal")
                        canvas.coords(di, w // 2, h // 2)
                    except Exception:
                        pass
                    self._dnes_tk_imgs["dojo"] = dojo
                    self._dnes_cur_dojo = dojo
            else:
                try:
                    canvas.itemconfigure(di, state="hidden")
                except Exception:
                    pass
                self._dnes_cur_dojo = None
        # enso (trvala polozka) - novy PhotoImage a vymena LEN ked sa snimka
        # naozaj zmenila (`render()` vracia cachovany objekt; rovnake id =
        # rovnaka snimka). Bez tejto strazy sa enso prehadzovalo pri KAZDOM
        # prekresleni (aj ked stalo) a okno blikalo.
        ei = items.get("enso")
        if (ei is not None and pil is not None and _ImageTk is not None
                and pil is not getattr(self, "_dnes_cur_pil", None)):
            try:
                tkimg = _ImageTk.PhotoImage(pil)
                self._dnes_tk_imgs["enso"] = tkimg
                canvas.itemconfigure(ei, image=tkimg)
            except Exception:
                pass
            self._dnes_cur_pil = pil

    def _layout_dnes_items(self, canvas, w, h, mierka, enso_px, titul, veta,
                           last, pal):
        """(Pre)stavia trvale obrazkove polozky (dojo, enso) + textovy blok a
        vycentruje cely blok zvisle. Vola sa LEN pri zmene textu/rozmeru/temy,
        nie kazdy tik - preto si moze dovolit merat a posuvat. Enso ma tag
        "block" (centruje sa s textom), ale NIE "dtext" (prestavba textu ho
        nesmie zmazat, je to trvala polozka menena cez `itemconfigure`)."""
        self._dnes_hit = {}
        # Polozky sa mohli prave vytvorit - vynuluj "co je na canvase", nech
        # `_paint` znova aplikuje dojo aj enso obrazok.
        self._dnes_cur_dojo = None
        self._dnes_cur_pil = None
        items = getattr(self, "_dnes_items", None)
        if items is None:
            items = self._dnes_items = {}
        # dojo - trvala polozka celkom vzadu
        if items.get("dojo") is None:
            items["dojo"] = canvas.create_image(w // 2, h // 2, anchor="center")
        try:
            canvas.tag_lower(items["dojo"])
        except Exception:
            pass
        # enso - trvala polozka
        if items.get("enso") is None:
            items["enso"] = canvas.create_image(w // 2, 0, anchor="n",
                                                tags=("block", "enso"))
        canvas.coords(items["enso"], w // 2, 0)

        canvas.delete("dtext")          # len textovy blok; obrazky ostavaju
        cx = w // 2
        gap = max(4, int(10 * mierka))
        wrap = min(int(360 * mierka), max(140, w - int(48 * mierka)))
        y = enso_px + gap
        if titul:
            y = self._canvas_text(canvas, cx, y, titul, self._cvfont(19, "bold"),
                                  pal["text"], wrap=wrap, shadow=True) + gap
        if veta:
            y = self._canvas_text(canvas, cx, y, veta, self._cvfont(12),
                                  pal["text_dim"], wrap=wrap, shadow=True) + int(gap * 1.4)
        y = self._canvas_credit(canvas, cx, y, pal) + gap
        if last:
            y = self._canvas_text(canvas, cx, y, last, self._cvfont(10),
                                  pal["text_faint"], wrap=wrap) + gap

        # Blok = enso (hore, vyska enso_px) + text pod nim (spodok `y`).
        # POZOR: bbox("block") NEZAHRNA enso, lebo jeho obrazok sa nastavuje az
        # v `_paint_dnes_canvas` (tu je polozka este bez obrazka -> bbox ~ bod).
        # Preto centrujeme podla ZNAMEJ vysky bloku [0, y], nie podla bbox -
        # inak enso "vypadlo" z merania a cely blok sedel privysoko.
        dy = int(h / 2 - y / 2)
        if dy:
            canvas.move("block", 0, dy)
        # Klikacia zona ensa - tiez zo znamej geometrie (bbox("enso") je None,
        # kym polozka nema obrazok), inak by enso bolo NEKLIKATELNE.
        ex0 = w // 2 - enso_px // 2
        ey0 = dy
        self._dnes_hit["enso"] = (ex0, ey0, ex0 + enso_px, ey0 + enso_px)
        self._record_dnes_hits(canvas)   # kredit cez bbox (ma text); enso ostane

    def _canvas_text(self, canvas, cx, y_top, text, font, fill, wrap=0, shadow=False):
        """Vycentrovany (viacriadkovy) text od `y_top` nadol; vrati spodok.
        `shadow` prida tmavy tienik +1px pre citatelnost bez boxu."""
        kw = dict(anchor="n", justify="center", font=font)
        if wrap:
            kw["width"] = wrap
        if shadow:
            canvas.create_text(cx + 1, y_top + 1, text=text, fill="#0b0b0f",
                               tags=("block", "dtext"), **kw)
        item = canvas.create_text(cx, y_top, text=text, fill=fill,
                                  tags=("block", "dtext"), **kw)
        bb = canvas.bbox(item)
        return bb[3] if bb else y_top

    def _canvas_credit(self, canvas, cx, y_top, pal):
        """Riadok "© 2026 Dandurfin · GPLv3" vycentrovany; meno podciarknute a
        klikatelne (Twitch). Kresli sa po castiach vedla seba."""
        f = self._cvfont(10)
        fu = self._cvfont(10, underline=True)
        pre, meno, post = "© 2026 ", "Dandurfin", "  ·  GPLv3"
        try:
            wpre, wmeno, wpost = f.measure(pre), fu.measure(meno), f.measure(post)
        except Exception:
            wpre = wmeno = wpost = 0
        x = cx - (wpre + wmeno + wpost) / 2
        canvas.create_text(x + 1, y_top + 1, text=pre, anchor="nw", font=f,
                           fill="#0b0b0f", tags=("block", "dtext"))
        canvas.create_text(x, y_top, text=pre, anchor="nw", font=f,
                           fill=pal["text_faint"], tags=("block", "dtext"))
        x += wpre
        canvas.create_text(x, y_top, text=meno, anchor="nw", font=fu,
                           fill=pal["text_dim"], tags=("block", "dtext", "credit"))
        x += wmeno
        canvas.create_text(x, y_top, text=post, anchor="nw", font=f,
                           fill=pal["text_faint"], tags=("block", "dtext"))
        bb = canvas.bbox("credit")
        return bb[3] if bb else y_top

    def _record_dnes_hits(self, canvas):
        """Zapamata bboxy klikacich zon (enso, kredit) PO vycentrovani."""
        for tag in ("enso", "credit"):
            try:
                bb = canvas.bbox(tag)
            except Exception:
                bb = None
            if bb:
                self._dnes_hit[tag] = bb

    def _dnes_set_cursor(self, cur):
        if cur == getattr(self, "_dnes_cursor", ""):
            return
        self._dnes_cursor = cur
        try:
            self.dnes_canvas.configure(cursor=cur)
        except Exception:
            pass

    @staticmethod
    def _in_bbox(x, y, bb):
        return bb is not None and bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3]

    def _dnes_canvas_motion(self, event):
        hit = getattr(self, "_dnes_hit", {})
        over = (self._in_bbox(event.x, event.y, hit.get("enso"))
                or self._in_bbox(event.x, event.y, hit.get("credit")))
        self._dnes_set_cursor("hand2" if over else "")

    def _dnes_canvas_click(self, event):
        hit = getattr(self, "_dnes_hit", {})
        if self._in_bbox(event.x, event.y, hit.get("credit")):
            tw = getattr(self, "_dnes_twitch", None)
            if tw:
                try:
                    webbrowser.open(tw)
                except Exception:
                    app_log.exception("kredit: otvorenie Twitchu zlyhalo")
            return
        if self._in_bbox(event.x, event.y, hit.get("enso")):
            # Klik na znacku = spinac pocuvania (rovnako, ako mal widget).
            try:
                self.toggle_listening()
            except Exception:
                app_log.exception("enso klik: prepnutie zlyhalo")

    # ---------- živé dojo (hero prázdneho stavu) ----------

    HERO_PERIOD_S = 10.0        # 5 s nádych + 5 s výdych — tempo pásu aj kruhu

    def _dnes_anim_active(self):
        """Kresli sa este nieco POHYBLIVE? Uz len ked enso zije alebo je mesiac
        (pocuvanie / promocia). ZASTAVENY stav STOJI - dojo sa uz NEDYCHA, lebo
        prekreslovanie (skoro) identickeho obsahu 8x/s okno preblikavalo. Pas to
        cita rovnako: "inak stoji"."""
        enso = getattr(self, "enso", None)
        return bool(enso is not None and (enso._live or enso._moon))

    def _ensure_dnes_tick(self):
        """Rozbehne animacny tik stredu, ak nebezi a enso sa hybe. Jedine
        miesto (spolu s koncom `_tick_dnes`), kde `_dnes_tick_job` vznika.

        Planuje cez `after` a job nastavi HNED - nie priamym volanim
        `_tick_dnes` (to by cez prekreslenie a spatne `_ensure_dnes_tick`
        zarekurzovalo, kym `_tick_dnes` job na zaciatku drzi vynulovany)."""
        if getattr(self, "_dnes_tick_job", None) is not None:
            return
        if not self._dnes_anim_active():
            return
        try:
            self._dnes_tick_job = self.root.after(self.DNES_TICK_MS, self._tick_dnes)
        except Exception:
            self._dnes_tick_job = None

    def _on_enso_change(self):
        """`_EnsoHero._emit()` sem hlasi zmenu stavu (set_live/armed/graduate/
        set_pal). Prekresli stred a rozbehne tik, ak enso zacalo zit."""
        self._refresh_dnes_backdrop(force=False)
        self._ensure_dnes_tick()

    def _tick_dnes(self):
        """Jeden krok animacie stredu - uz len pre enso (pocuva / mesiac). Dojo
        je staticke, takze sa nehybe; prekreslime canvas a enso vymeni snimku v
        mieste (`itemconfigure`, bez blikania)."""
        self._dnes_tick_job = None
        if not self._dnes_anim_active():
            return
        try:
            viditelne = bool(self.root.winfo_viewable())
        except Exception:
            viditelne = True
        if viditelne:
            self._refresh_dnes_backdrop(force=False)
        interval = self.DNES_TICK_MS if viditelne else self.DNES_TICK_MS * 4
        try:
            self._dnes_tick_job = self.root.after(interval, self._tick_dnes)
        except Exception:
            self._dnes_tick_job = None

    def _start_dnes_hero(self):
        """Zapne JASNE dojo za ensom (zastaveny stav). Dojo je STATICKE - uz sa
        NEDYCHA (to blikanie preblo). Enso aj text stoja; stred sa prekresli raz
        a potom sa nehybe nic - presne ako to hlasi pas: "inak stoji"."""
        self._dnes_hero_on = True
        # Staticke, ale s prijemnou ziarou (nie na minime) - fixna faza dychu.
        self._dnes_breath_phase = 0.25
        self._refresh_dnes_backdrop(force=True)
        self._ensure_dnes_tick()

    def _stop_dnes_hero(self):
        """Prepne dojo na tlmenu fotku (pocuvanie). Enso môže žiť ďalej (počúva /
        mesiac) - animacny tik sa sam zastavi, ked sa nehybe uz nic."""
        self._dnes_hero_on = False
        self._refresh_dnes_backdrop(force=True)
        self._ensure_dnes_tick()

    def _refresh_dnes_state_text(self):
        """Nadpis a veta pod znackou. Ten isty text ako v dychajucom pase -
        `_kamae_state_text` je jediny zdroj, aby sa nemohli rozist. Text sa
        ulozi a stred sa prekresli (kresli ho `_paint_dnes_canvas`)."""
        if not hasattr(self, "dnes_canvas"):
            return
        try:
            titul, veta = self._kamae_state_text()
            self._dnes_titul = titul
            self._dnes_veta = veta
            self._refresh_dnes_backdrop(force=False)
        except Exception:
            app_log.exception("stav na Dnes: prepis textu zlyhal")

    def _resume_cue_trigger(self):
        """Vedome zdvihne pozastavenie spustaca.

        `resume(force=True)`, lebo bezny `resume()` z `_apply_hr_bpm` zdvihne
        UZ LEN vypadok tepu - snooze ani zastavene pocuvanie zdvihnut nesmie.
        Volat treba VZDY, aj ked sa `start_listening` nezavola: pri snooze
        spustenom v nepocuvajucom stave by inak spustac ostal pozastaveny
        navzdy.

        KYM PLATI "TERAZ NIE", NEZDVIHNE NIC. Od 24. 9. snooze pocuvanie
        nezastavuje, takze `start_listening` (hrac dal stop a start pocas
        stisenia) by ho inak ticho zrusil. Koniec a zrusenie snooze nulu
        `_snooze_job` PRED volanim.
        """
        if getattr(self, "_snooze_job", None) is not None:
            return
        try:
            self.cue_trigger.resume(force=True)
        except Exception:
            app_log.exception("spustac hlasky: resume zlyhal")

    def _set_enso_armed(self, armed):
        """Prenesie "natiahnute" do znacky v bocnom paneli.

        Vnutorny prstenec, nie tretia farba - farba ensa ma podla `theme.py`
        v celom rozhrani jedinu ulohu a tou je povedat, ci appka pocuva.

        Cez `getattr` a `try`, lebo sem sa da dostat aj skor, nez je sidebar
        postaveny (spustac tika z `_tick_activity`, ten bezi od startu).
        """
        armed = bool(armed)
        self._cue_armed = armed
        sidebar = getattr(self, "sidebar", None)
        if sidebar is not None:
            try:
                sidebar.enso.set_armed(armed)
            except Exception:
                pass
        # Znacka a pas nesu ten isty stav - musia sa menit na jednom mieste,
        # inak sa raz rozidu a nikto si toho nevsimne.
        self._refresh_kamae_state_text()

    def _cue_can_fire(self, now):
        """Smie sa prave teraz hlaska dorucit?

        Natiahnutie sa tym NEZRUSI - ked sa nesmie, caka sa dalej. Zrusi sa
        az ked uplynie `max_wait_s`.
        """
        if not self.listening:
            # Enso je jediny nositel stavu. Kym svieti `danger`, appka
            # nesmie povedat nic - inak by ta farba klamala.
            return False
        if getattr(self, "_snooze_job", None) is not None:
            return False            # "teraz nie" plati aj na telo, nie len na klavesy
        if not self._hr_overlay_available():
            self._warn_hr_overlay_disabled_once()
            return False
        # Bezi uz NIEKTORY vizual? Pytat sa len na slot 3 nestacilo: od
        # zavedenia striedania kategorii moze bezat hociktory zo styroch a
        # dva prekryte piktogramy naraz su presne ten vizualny sum, ktoremu
        # sa appka vyhyba.
        if any(self.overlay_manager.is_active(i) for i in range(4)):
            return False
        # Kym chodia kroky, appka mlci. `None` znamena, ze hodinky kroky
        # neposielaju - vtedy sa nema na co odvolavat a nebrani nicomu.
        kroky = self.hr_stats.steps_per_min()
        if kroky is not None and kroky >= self.KROKY_PRAH_ZA_MIN:
            return False
        if now - self.last_global_trigger_time < self.cooldown_value:
            return False
        return True

    def _tick_cue_trigger(self):
        """4x za sekundu. Jediny volajuci je `_tick_activity`, cize Tk vlakno -
        a to je nutne: dotyka sa `hr_stats` aj `overlay_manager`."""
        if not self._hr_session_open:
            return
        now = time.time()
        # Viditelnost HUD-u za tento tik. dt < 5 s je poistka proti uspaniu PC
        # (po prebudeni by jeden "tik" pridal hodiny) - kratke medzery su beh.
        # Aktivny cas rastie vzdy, viditelny len ked je HUD zapnuty - podiel
        # sa potom rata z rovnakej zakladne (viz `_close_hr_session`).
        if self._hud_tick_t is not None:
            dt = now - self._hud_tick_t
            if 0.0 < dt < 5.0:
                self._hud_active_s += dt
                if self._hud_is_visible():
                    self._hud_vis_s += dt
        self._hud_tick_t = now
        udalost = self.cue_trigger.tick(
            pause_s=self.activity.pause_s(now),
            now=now,
            can_fire=self._cue_can_fire(now))
        if udalost is not None:
            self._on_cue_event(udalost)

    def _hud_is_visible(self):
        """Ci hrac prave vidi svoj tep - t.j. HUD panel je zapnuty. Berie sa
        ulozeny stav (`hud_config['enabled']`), takze prepnutie ho hned zmeni;
        docasny 'test_hud' sa nepocita (nie je to hranie)."""
        try:
            return bool(self.hud_config.get("enabled"))
        except Exception:
            return False

    def _on_cue_event(self, ev):
        """Jedna udalost z automatu. Vsetko sa zapise - aj zrusene
        natiahnutia, lebo podla ich pomeru sa ladia prahy.

        Je to zaroven jediné miesto, kde sa prstenec na ense zapina. Zhasina
        sa na troch dalsich (dorucenie, zrusenie, `_suspend_cue_trigger`) -
        automat ma stavov viac nez UI, ale von z ARMED vedie kazda cesta cez
        niektoru z nich.
        """
        zaznam = dict(ev)
        self._cue_log.append(zaznam)
        if ev["typ"] == trigger.E_DELIVER:
            self._set_enso_armed(False)
            # Ci sa hlaska NAOZAJ dorucila (nie vypnute vsetky sloty, nie
            # zlyhany vizual). Bez toho dotaznik ratal aj nedorucene a hlasil
            # "Ozvala som sa 3x", ked appka mlcala (bug B19).
            zaznam["delivered"] = bool(self._fire_somatic_cue(ev))
        elif ev["typ"] == trigger.E_ARMED:
            self._set_enso_armed(True)
            app_log.info("hlaska natiahnuta (rameno %s)", ev.get("arm"))
        else:
            self._set_enso_armed(False)
            app_log.info("natiahnutie zrusene: %s", ev.get("reason"))

    def _dalsi_cue_slot(self):
        """Ktora kategoria zaznie teraz. Striedaju sa kolo-dokola.

        Berie do uvahy len sloty, ktore su ZAPNUTE a maju zapnuty aj
        in-game vizual. Ked taky nie je ani jeden, vracia None a hlaska sa
        NEDORUCI - vypnutie je rozhodnutie hraca a appka ho obchadzat nesmie.

        Poradie sa pamata v ramci behu appky, nie medzi spusteniami: po
        restarte sa zacina od prvej zapnutej kategorie. Pri strope pat
        hlasok za hodinu je to rozdiel, ktory sa v datach stratí.
        """
        zapnute = []
        for slot in getattr(self, "slots", ()):
            try:
                index = int(slot.index)
            except (TypeError, ValueError):
                continue
            if not getattr(slot, "enabled_value", True):
                continue
            # A MUSI mat aj zapnuty in-game vizual.
            #
            # `_fire_somatic_cue` kresli `overlay_manager.trigger(index)` v
            # OBOCH ramenach - to je jedina vec, ktoru dostane tiche rameno.
            # Slot s vypnutym vizualom by v tichom rameni nedorucil nic a
            # okno by sa zapisalo ako platne meranie hlasky, ktora sa nikdy
            # nestala. Preto sa taky slot preskakuje.
            try:
                if not self.overlay_configs[index]["enabled"]:
                    continue
            except (IndexError, KeyError, TypeError):
                continue
            zapnute.append(index)
        dalsi = measure.next_slot(zapnute, getattr(self, "_posledny_cue_slot", None))
        if dalsi is None:
            # Ziadna kategoria nie je pouzitelna. `CUE_SLOT_INDEX` (3) bola
            # zaloha natvrdo, lenze prave ten slot moze mat vypnuty vizual -
            # a potom by sa hlaska "dorucila" bez toho, aby sa cokolvek
            # nakreslilo. Berieme prvy slot, ktory naozaj ma co ukazat.
            # ZIADNA ZALOHA. Do 19. 9. sa tu vracal `CUE_SLOT_INDEX` (3),
            # teda dychovy kruh - "radsej nech appka povie nieco nez nic".
            # Lenze vypnutie hlasky je rozhodnutie hraca a appka ho obchadzat
            # nesmie: kto vypol vsetky styri, chcel ticho a dostal dychanie.
            return None
        self._posledny_cue_slot = dalsi
        return dalsi

    def _fire_somatic_cue(self, ev):
        """Doruci hlasku. VIZUAL IDE V OBOCH RAMENACH, zvuk len v hlasnom.

        Keby sa tichemu ramenu nezobrazil ani vizual, ramena by sa nedali
        porovnat - meral by sa rozdiel medzi "nieco sa stalo" a "nestalo sa
        nic", nie medzi hlaskou a tichom.

        Do logu appky ide ROVNAKY riadok v oboch ramenach. Hrac aj tak pocuje,
        ci nieco zaznelo, takze zaslepit sa to neda - ale log nema byt dalsim
        miestom, kde sa ramena rozchadzaju.
        """
        index = self._dalsi_cue_slot()
        if index is None:
            # Vsetky hlasky vypnute (alebo ziadna nema vizual). Doteraz sa v
            # tomto stave dorucila zaloha - dychovy kruh - takze vypnutie
            # vsetkych styroch prepinacov appku NEUMLCALO. Hrac vypol vsetko,
            # co sa vypnut dalo, a appka sa ozvala dalej.
            self.log(tr("log.cue_skipped_all_off"))
            return False
        self.last_global_trigger_time = ev["ts"]
        # VIZUAL JE SPOLOCNY PODNET OBOCH RAMIEN. Ked sa nevykresli, tiche
        # rameno nedostane NIC a meranie by porovnavalo hlasku proti nicomu.
        # `note_trigger(delivered=...)` to prenesie do okna, ktore `measure`
        # v takom pripade zneplatni (bug B17).
        vykreslene = bool(self.overlay_manager.trigger(index))
        if not vykreslene:
            self.log(tr("log.cue_visual_failed"))

        # Podla atributu, nie podla poradia v zozname: `handle_trigger` tiez
        # hlada cez `slot.index`, takze poradie v `self.slots` nemusi sediet.
        slot = next((s for s in self.slots if s.index == index), None)
        label = (slot.text_value if slot is not None else "") or ""
        # `hlas` je v pracovnom svete vzdy False (B3-worlds) - rozhoduje
        # automat (`CueTrigger.open_session(voice=...)`), nie tato vetva,
        # aby aj zaznam udalosti hovoril pravdu o tom, co zaznelo.
        #
        # REBRIK (0.2): zvuk LEN na stupni hlasu. Pod nim ide hlaska len
        # obrazom v oboch ramenach - automat to uz vie (`voice` pri
        # otvoreni), tu je to druha poistka. Styl "zvuk" = stupen hlasu so
        # stlmenymi slovami: slot zahra svoj zvuk, TTS ani nahravka nie.
        stupen = getattr(self, "_cue_rung", rebrik.HLAS)
        bez_slov = (getattr(self, "_cue_style_rel", rebrik.STYL_HLAS)
                    == rebrik.STYL_ZVUK)
        zaznie = False
        if ev.get("hlas") and slot is not None and stupen == rebrik.HLAS:
            zaznie = self._slot_zaznie(slot, bez_slov)
            # `_emit` prehrava a blokuje - v Tk vlakne by zamrazilo okno.
            threading.Thread(target=self._emit, args=(slot,),
                             kwargs={"bez_slov": bez_slov}, daemon=True).start()

        # Zaznam o doruceni ide do okna (`measure.build_window`): stupen,
        # ci naozaj nieco zaznelo, zataz a jej vrchol, pasmo tepu.
        self.hr_stats.note_trigger(
            ts=ev["ts"], auto=True,
            category=measure.category_for_slot(index),
            cue_id=f"slot{index}", arm=ev["arm"], source="auto",
            delivery=ev.get("delivery"), delivered=vykreslene,
            rung=stupen, audible=zaznie, load_at=ev.get("load"),
            load_peak=ev.get("load_peak"), zone_at=ev.get("zone_at"))
        self.log(tr("log.cue_delivered", label=label))
        # Pocitadlo v hlavicke dennika (`session.summary`, "Ťažisko 2× | ...").
        # Doteraz ho zvysoval len `_deliver` pri source=="trigger" - lenze
        # tadial automaticka hlaska nikdy nechodi, takze riadok ukazoval 0×
        # pri vsetkych styroch, kym karta na Dnes hlasila tri hlasky.
        # Rata sa len hlaska, ktora sa naozaj ukazala, a nie tiche kontrolne
        # rameno (to je meranie, nie hlaska pre hraca).
        if vykreslene and ev.get("arm") != trigger.ARM_SILENT:
            pocty = getattr(self, "session_counts", None)
            if isinstance(pocty, dict):
                pocty[index] = pocty.get(index, 0) + 1
                obnov = getattr(self, "update_session_label", None)
                if callable(obnov):
                    obnov()
        self._refresh_hud_session_text()
        self._refresh_dnes_stats()
        return vykreslene

    def _refresh_nav_badges(self):
        """Pocet spustacov na karte Spustace, bodka pri "V hre" (teraz
        samostatna polozka sidebaru, nie karta), ked senzor tepu bezi."""
        sidebar = getattr(self, "sidebar", None)
        if sidebar is None or not hasattr(sidebar, "set_badge"):
            return
        try:
            # POCET HLASOK pri karte "Spustace" uz NIE JE.
            #
            # Cislo malo zmysel, kym si hrac sloty priradoval ku klavesom a
            # potreboval vidiet, kolko ich je aktivnych. Dnes su styri, appka
            # si ich strieda sama a hrac ich nepridava - tak to bola len
            # cifra, ktora nic nehlasila a tahala oko k nesprávnej veci.
            nav = getattr(self, "settings_nav", None)
            if nav is not None:
                nav.set_badge("spustace", "")
            sidebar.set_badge("vhre", "●" if self.hr_monitoring_enabled else "")
        except Exception:
            pass

    def _refresh_dnes_stats(self):
        """Prepise tep, zataz a suhrn relacie na stranke Dnes.

        Vola sa pri kazdej vzorke tepu a raz za sekundu z `_tick_session`,
        aby bezal aj cas relacie. Ked stranka este nie je postavena (deje sa
        pri prepnuti temy/jazyka), ticho sa nerobi nic.

        PRECO SA TU CHYBA POCITA
        Cele telo je v jednom `except`, a to zamerne: bezi to 1-4x za
        sekundu a vynimka z prekreslenia nesmie zhodit ani meranie, ani
        relaciu. Lenze `pass` znamenal, ze rozbita stranka sa neprejavila
        NICIM. gui_screenshots hlasi "0 chyb v Tk", lebo to chyta len
        vynimky, ktore z Tk callbacku UNIKNU - a tato neunikne. Appka teda
        mohla mat uplne zamrznutu stranku Dnes a cely test prejst nazeleno.

        Prvy vyskyt sa preto zaloguje cely a dalsie sa uz len pocitaju
        (`app_log.exception` pri kazdom volani by log zaplavil). Na
        `_dnes_refresh_fails` sa pyta gui_screenshots.
        """
        if getattr(self, "dnes_bpm", None) is None:
            return
        stats = self.hr_stats
        connected = self._hr_state == "connected" and stats.last_bpm is not None
        # VYPADOK NIE JE "ESTE SOM TA NEPOCULA". Pocas vypadku ostava zivy
        # blok aj stopa relacie (ziadne "Sparuj hodinky" uprostred vecera),
        # ale cislo je "--" a pasmo "—" - to riesi `connected` nizsie, takze
        # ziadny falosny pokoj.
        lost = bool(getattr(self, "_hr_lost", False)) and not connected
        ukaz = connected or lost
        pal = self.pal
        try:
            self.dnes_bpm.configure(
                text=str(int(stats.last_bpm)) if connected else "--",
                text_color=pal["text"] if connected else pal["text_faint"])
            self.dnes_spark.set_series(stats.series(120) if connected else [],
                                       threshold=self.hr_critical_bpm,
                                       baseline=stats.baseline)
            # Kym sa relacia kalibruje, pruh ostane prazdny a namiesto pasma
            # je tiche "kalibrujem…" - rovnako ako HUD v hre. Hned po navrate
            # tepu (`is_settling`) to iste, len namiesto slova "…": zataz sa
            # rozbieha od nuly a inak by par sekund tvrdila "Pokoj".
            kalibruje = connected and stats.is_calibrating
            usadza = connected and not kalibruje and stats.is_settling
            tlmene = kalibruje or usadza
            # Slovo aj farba plnych dielikov su `stats.zone` (tep voci
            # pokoju) - to iste ako na HUD-e a na kontrolke tepu. Dlzka
            # pruhu je zataz.
            zone = stats.zone if connected and not tlmene else None
            self.dnes_load.set_value(stats.stress if connected and not tlmene else 0,
                                     zone=zone)
            if kalibruje:
                zone_text = tr("hud.calibrating")
            elif usadza:
                zone_text = "…"
            else:
                zone_text = tr(f"hud.zone.{zone}") if zone else "—"
            self.dnes_zone.configure(
                text=zone_text,
                text_color=theme_mod.zone_color(pal, zone) if zone else pal["text_faint"])
            self._refresh_session_trace(ukaz)
            self._refresh_zone_panel()
            self._refresh_dashboard_stats()
            if getattr(self, "hr_panel", None) is not None:
                if connected:
                    vpravo = tr("dnes.hr_connected")
                elif lost:
                    vpravo = tr("dnes.hr_lost")
                else:
                    vpravo = tr("dnes.hr_waiting")
                self.hr_panel.set_right(vpravo)
            empty, live = getattr(self, "dnes_empty", None), getattr(self, "dnes_live", None)
            if empty is not None and live is not None:
                if ukaz and not live.winfo_ismapped():
                    empty.pack_forget()
                    live.pack(fill="x")
                    self._stop_dnes_hero()       # dýcha už len pás
                elif not ukaz and not empty.winfo_ismapped():
                    live.pack_forget()
                    empty.pack(fill="x", pady=(6, 0))
                    self._start_dnes_hero()      # rozdýchaj dojo za ensom
        except Exception:
            self._dnes_refresh_fails = getattr(self, "_dnes_refresh_fails", 0) + 1
            if self._dnes_refresh_fails == 1:
                app_log.exception(
                    "Dnes: obnovenie zlyhalo (dalsie vyskyty sa uz nevypisu)")
        self._refresh_last_cue()

    def _refresh_session_trace(self, connected):
        """Stopa relacie na Dnes.

        Kresli sa z `HeartStats.trace()`, cize z CELEJ relacie preriedenej
        na 120 bodov - nie z posledneho okna. Bez senzora ostava prazdna,
        ale panel nezmizne: prazdny obrys je informacia ("este som nic
        nezmeral"), zatial co chybajuci panel je diera v stranke.
        """
        trace = getattr(self, "dnes_trace", None)
        if trace is None or not trace.winfo_exists():
            return
        stats = self.hr_stats
        elapsed = max(0.0, time.time() - stats.session_start)
        if connected and stats.session_count >= 2:
            # Bez popisku: Dnes je stranka, na ktoru sa hrac pozera POCAS
            # hrania a kazda veta navyse ho z hry vytrhne. Co pruh znamena,
            # vysvetluje dotaznik po relacii a detail v Historii.
            trace.set_trace(stats.trace(), baseline=stats.session_baseline,
                            threshold=self.hr_critical_bpm, duration_s=elapsed,
                            triggers=stats.trigger_offsets,
                            activity=stats.activity_trace())
            meta = tr("dnes.trace_meta", time=self._fmt_minutes(elapsed),
                      n=stats.auto_triggers)
        else:
            trace.set_trace([])
            meta = ""
        self.dnes_trace_meta.configure(text=meta)

    def _refresh_zone_panel(self):
        """Rozdelenie casu relacie do pasiem (pruh + styri riadky)."""
        bar = getattr(self, "dnes_zone_bar", None)
        if bar is None or not bar.winfo_exists():
            return
        zones = self.hr_stats.zone_seconds
        bar.set_zones(zones)
        celkom = sum(max(0.0, float(v or 0.0)) for v in zones.values())
        for zone, label in self.dnes_zone_rows.items():
            sekundy = max(0.0, float(zones.get(zone, 0.0) or 0.0))
            podiel = (100.0 * sekundy / celkom) if celkom > 0 else 0.0
            label.configure(text=f"{podiel:.0f} %")

    # ---------- volitelne statistiky na Dnes ("Moje štatistiky") ----------

    def _dashboard_stat_catalog(self):
        """(id, nazov, TOKEN farby) pre vsetky volitelne statistiky, v poradi
        vo vybere. V mriezke je poradie hracovo (self.dashboard_stats) -
        meni sa potiahnutim karty na inu.

        Token, nie hodnota: kartu aj bodku vo vybere treba po zmene temy
        prefarbit, a token si novu farbu najde sam."""
        return [
            # tep patri do radu pasiem, nie do success/warn/danger - inak by
            # karta "pokojová základňa" svietila inou zelenou, nez akou je
            # pokoj v pruhu vedla nej (viz theme.ZONE_TOKENS)
            ("baseline", tr("metric.baseline.title"), "zone_calm"),
            ("hrr", tr("metric.hrr.title"), "blue"),
            ("over", tr("metric.over.title"), "zone_high"),
            ("breath", tr("metric.breath.title"), "murasaki"),
            ("avg", tr("metric.avg.title"), "zone_calm"),
            ("max", tr("metric.max.title"), "zone_critical"),
            ("peak", tr("metric.peak.title"), "accent"),
            ("week", tr("metric.week.title"), "blue"),
            # 0.2: ta ista farba ako ciara tej istej metriky v Historii
            # (HISTORY_METRICS) - karta a graf su jedna vec
            ("session_len", tr("metric.session_len.title"), "text_dim"),
            ("last_cue", tr("metric.last_cue.title"), "murasaki"),
            ("calm_time", tr("metric.calm_time.title"), "zone_calm"),
            ("signal", tr("metric.signal.title"), "blue"),
            # neutralna farba: ani jedno z dvoch cisel nie je "to spravne"
            ("felt_vs_measured", tr("metric.felt_vs_measured.title"), "text"),
        ]

    # POZN: tu boli `_STAT_HISTORY` (ktore pole ulozeneho suhrnu zodpoveda
    # ktorej karte) a `_STAT_LOWER_IS_BETTER` (kde je "menej" dobra sprava).
    # Oboje existovalo VYLUCNE pre mikrograf a vetu o odchylke na karte;
    # s nimi odisli aj `_dashboard_stat_live` a `ui_kit.MicroChart`.
    # Dovod je nizsie pri `_dashboard_stat_value`.

    def _history_cached(self, max_age=20.0):
        """Historia relacii z disku, najviac raz za `max_age` sekund.

        Karty sa prekresluju pri KAZDEJ vzorke tepu (a raz za sekundu aj
        bez nej). Karta "Relácie tento týždeň" pritom citala JSON zakazdym
        - niekolko otvoreni suboru za sekundu za nic. Cache sa zahodi po
        ulozeni relacie (`_close_hr_session`), cize novy zaznam sa objavi
        hned, nie o 20 sekund.
        """
        now = time.time()
        stamp, data = getattr(self, "_history_cache", (0.0, None))
        if data is None or now - stamp > max_age:
            data = self._history_sessions()
            self._history_cache = (now, data)
        return data

    # POZN: tu boli `_dashboard_stat_live(stat_id)` (aktualna hodnota karty
    # ako CISLO, na porovnanie s historiou) a `_dashboard_stat_trend(stat_id)`
    # (seria poslednych relacii, odchylka dneska od ich priemeru a farba
    # podla toho, ci je to zlepsenie). Kreslilo sa to na karte ako mikrograf
    # plus veta pod cislom.
    #
    # Odislo spolu s prestavbou karty (viz `ui_kit.StatCard`): karta ma byt
    # JEDEN pokojny udaj, a mikrograf s vetou z nej robili tri. Myslienka
    # sama bola spravna - "62 BPM" nehovori nic, kym clovek nevie, co je
    # uneho bezne - a zije dalej v Historii, kde je na trend cely graf.
    #
    # Odstranene s tym aj: `_STAT_HISTORY`, `_STAT_LOWER_IS_BETTER`,
    # `ui_kit.MicroChart` a jazykove kluce `dashboard.delta_*`.

    def _dashboard_stat_value(self, stat_id):
        """(hodnota, popisok) pre jednu kartu - zo ziveho self.hr_stats,
        "week" a "felt_vs_measured" z ulozenej historie relacii
        (hr_sessions.json, cez `_history_cached`)."""
        stats = self.hr_stats
        if stat_id == "baseline":
            base = stats.session_baseline
            return (str(int(round(base))) if base else "-", tr("dashboard.unit.baseline"))
        if stat_id == "hrr":
            hrr = stats.hrr if stats.session_count else None
            return (f"{hrr:+d}" if hrr is not None else "-", tr("dashboard.unit.hrr"))
        if stat_id == "over":
            over = int(stats.time_over)
            return (f"{over // 60}:{over % 60:02d}", tr("dashboard.unit.over"))
        if stat_id == "breath":
            return (str(stats.auto_triggers), tr("dashboard.unit.breath"))
        if stat_id == "avg":
            return (str(int(round(stats.average))) if stats.average else "-",
                    tr("dashboard.unit.avg"))
        if stat_id == "max":
            return (str(int(stats.session_max)) if stats.session_max else "-",
                    tr("dashboard.unit.max"))
        if stat_id == "peak":
            return (str(int(round(stats.peak_stress))), tr("dashboard.unit.peak"))
        if stat_id == "week":
            try:
                since = hr_stats.period_start_ts(hr_stats.PERIOD_WEEK)
                # Len aktualny svet (B3-worlds). Filtruje sa ulozeny zoznam,
                # takze prepnutie sveta sa prejavi hned, bez citania disku.
                count, duration = hr_stats.count_sessions_since(
                    hr_stats.sessions_in_world(self._history_cached(), self.world),
                    since)
            except Exception:
                count, duration = 0, 0.0
            hours, rem = divmod(int(duration), 3600)
            minutes = rem // 60
            sub = f"{hours}h {minutes}m" if hours else f"{minutes}m"
            return (str(count), sub)
        # --- 0.2 (widgets-history). Co sa nevie, je "—", nie nula. ---
        # Dlzka, posledna hlaska a signal sa pytaju len OTVORENEJ relacie:
        # po jej zatvoreni by hodiny bezali dalej od zaciatku uz skoncenej
        # relacie a pokrytie by ticho klesalo k nule.
        otvorena = getattr(self, "_hr_session_open", False)
        if stat_id == "session_len":
            unit = tr("dashboard.unit.session_len")
            if not otvorena:
                return ("—", unit)
            return (self._fmt_dlzka(time.time() - stats.session_start), unit)
        if stat_id == "last_cue":
            unit = tr("dashboard.unit.last_cue")
            ts = stats.last_auto_cue_ts() if otvorena else None
            if ts is None:
                return ("—", unit)
            return (tr("dashboard.fmt.min", n=int(max(0.0, time.time() - ts) // 60)), unit)
        if stat_id == "calm_time":
            # Ako "nad hranicou": suhrn relacie, ostava aj po jej zatvoreni.
            calm = stats.calm_seconds()
            return ("—" if calm is None else tr("dashboard.fmt.min", n=int(calm // 60)),
                    tr("dashboard.unit.calm_time"))
        if stat_id == "signal":
            unit = tr("dashboard.unit.signal")
            pokrytie = stats.signal_coverage if otvorena else None
            if pokrytie is None:
                return ("—", unit)
            text = self._fmt_pokrytie(pokrytie)
            if stats.dropouts:
                text = f"{text} · {stats.dropouts}×"
            return (text, unit)
        if stat_id == "felt_vs_measured":
            try:
                # Posledna relacia AKTUALNEHO sveta (B3-worlds).
                par = hr_stats.citene_a_merane(hr_stats.posledna_relacia(
                    hr_stats.sessions_in_world(self._history_cached(), self.world)))
            except Exception:
                par = None
            return (self._fmt_citene_merane(par), tr("dashboard.unit.felt_vs_measured"))
        return ("-", "")

    def _rebuild_dashboard_stats_grid(self):
        grid = getattr(self, "dashboard_grid", None)
        if grid is None:
            return
        pal = self.pal
        for child in grid.winfo_children():
            child.destroy()
        self.dashboard_cards = {}
        self._dashboard_drag_state = None     # stare karty su prec
        catalog = {s[0]: s for s in self._dashboard_stat_catalog()}
        # Posledna karta nema ✕ - jedna ostava vzdy (toggle_dashboard_stat).
        removable = len(self.dashboard_stats) > 1
        for i, stat_id in enumerate(self.dashboard_stats):
            meta = catalog.get(stat_id)
            if meta is None:
                continue
            _id, _title, color_token = meta
            value, _sub = self._dashboard_stat_value(stat_id)
            row, col = divmod(i, 2)
            # `metric.*.tag`, nie `title`: karta ukazuje velke cislo a pod
            # nim JEDNO SLOVO. `title` je cela veta a v nemcine, francuzstine
            # a rustine rozsiruje cely pravy stlpec na ukor stredu.
            card = ui_kit.StatCard(
                grid, pal, color_token, tr(f"metric.{stat_id}.tag"), value,
                tr(f"metric.{stat_id}.more"),
                on_remove=((lambda k=stat_id: self._toggle_dashboard_stat(k))
                           if removable else None),
                on_drag=lambda phase, e, k=stat_id: self._dashboard_drag(k, phase, e))
            card.grid(row=row, column=col, sticky="nsew",
                     padx=(0, 7) if col == 0 else (7, 0),
                     pady=(7, 0) if row > 0 else (0, 0))
            self.dashboard_cards[stat_id] = card
        self._refresh_dashboard_stats()

    def _refresh_dashboard_stats(self):
        # POZN: bol tu aj `card.set_trend(...)` z `_dashboard_stat_trend` -
        # mikrograf poslednych relacii a veta o odchylke. Karta je teraz
        # jeden udaj, nie tri; trend patri do Historie, kde je na to graf.
        for stat_id, card in getattr(self, "dashboard_cards", {}).items():
            value, _sub = self._dashboard_stat_value(stat_id)
            card.set_value(value)

    def _open_dashboard_picker(self):
        existing = getattr(self, "_dashboard_picker", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.destroy()
                    self._dashboard_picker = None
                    return
            except Exception:
                pass
        pal = self.pal
        btn = self.dashboard_edit_btn
        btn.update_idletasks()
        top = ui_kit.priprav_popup(tk.Toplevel(self.root))
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.configure(bg=pal["border"])
        self._dashboard_picker = top

        # Vysku berie ramec z obsahu. Kedysi tu bolo `pack_propagate(False)`
        # bez vysky, takze ramec ostal na predvolenych 200 px CTkFrame: vidno
        # boli 3 riadky, stvrty napoly a zvysok sa vybrat vobec nedal. Sirku
        # (230) drzi nulovo vysoka rozpera.
        frame = ctk.CTkFrame(top, fg_color=pal["surface"], corner_radius=ui_kit.RADIUS_PANEL,
                             border_width=1, border_color=pal["border"], width=230)
        frame.pack(padx=1, pady=1)
        ctk.CTkFrame(frame, width=228, height=0, fg_color="transparent").pack()
        ctk.CTkLabel(frame, text=tr("dashboard.picker_title").upper(), font=ui_kit.ui(9, "bold"),
                     text_color=pal["text_faint"], anchor="w").pack(fill="x", padx=12, pady=(10, 4))
        self._dashboard_picker_rows = ctk.CTkFrame(frame, fg_color="transparent")
        self._dashboard_picker_rows.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        self._render_dashboard_picker_rows()
        # jeden tichy riadok: strop 4 kariet a ze sa daju presuvat
        ctk.CTkLabel(frame, text=tr("dashboard.picker_hint"), font=ui_kit.ui(10),
                     text_color=pal["text_faint"], anchor="w", justify="left",
                     wraplength=200).pack(fill="x", padx=12, pady=(0, 10))

        # pravy okraj popupu = pravy okraj tlacidla (rovnake ako makety
        # `position:absolute; top:100%; right:0`) - az PO postaveni obsahu,
        # inak by sirka este nebola znama. Ked sa pod tlacidlo nezmesti
        # (nizka obrazovka, okno dole), vysunie sa nad neho.
        top.update_idletasks()
        w, h = top.winfo_reqwidth(), top.winfo_reqheight()
        x = btn.winfo_rootx() + btn.winfo_width() - w
        y = btn.winfo_rooty() + btn.winfo_height() + 4
        x, y = ui_kit.fit_popup(x, y, w, h, ui_kit.work_area(btn), btn.winfo_rooty())
        top.geometry(f"+{x}+{y}")

        top.bind("<FocusOut>", lambda _e: self._close_dashboard_picker())
        top.bind("<Escape>", lambda _e: self._close_dashboard_picker())
        top.after(60, top.focus_force)

    def _close_dashboard_picker(self):
        top = getattr(self, "_dashboard_picker", None)
        if top is not None:
            try:
                top.destroy()
            except Exception:
                pass
        self._dashboard_picker = None

    def _render_dashboard_picker_rows(self):
        container = getattr(self, "_dashboard_picker_rows", None)
        if container is None:
            return
        try:
            if not container.winfo_exists():
                return
        except Exception:
            return
        for child in container.winfo_children():
            child.destroy()
        pal = self.pal
        for stat_id, title, color_token in self._dashboard_stat_catalog():
            on = stat_id in self.dashboard_stats
            # Riadok, na ktorom klik nic neurobi, nema ruku na kurzore:
            #  - nezvolena metrika, ked su 4 karty plne -> aj bledy text
            #    (uvolni sa, ked jednu kartu odoberies)
            #  - posledna zvolena metrika (jedna karta ostava vzdy) -> vyzera
            #    ako zvolena, len nereaguje
            clickable = dashboard_stat_clickable(self.dashboard_stats, stat_id)
            if on:
                text_color = pal["text"]
            elif clickable:
                text_color = pal["text_dim"]
            else:
                text_color = pal["text_faint"]
            row = ctk.CTkFrame(container, fg_color=pal["surface_alt"] if on else "transparent",
                               corner_radius=6)
            row.pack(fill="x", pady=1)
            inner = ctk.CTkFrame(row, fg_color="transparent")
            # Nizsie riadky (popisok 20 px namiesto predvolenych 28 CTkLabel,
            # okraj 4 namiesto 6): od 0.2 je v katalogu 13 metrik a vyber musi
            # ostat na obrazovke cely. Odmerane pri 150 %: riadok 60 -> 42 px,
            # cely vyber s 13 riadkami 719 px (predtym s 8 riadkami 643).
            inner.pack(fill="x", padx=8, pady=4)
            ctk.CTkFrame(inner, width=8, height=8, corner_radius=4,
                        fg_color=pal[color_token] if (on or clickable) else pal["text_faint"]
                        ).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(inner, text=title, font=ui_kit.ui(12), height=20,
                         text_color=text_color,
                         anchor="w").pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(inner, text="✓" if on else "", font=ui_kit.ui(11, "bold"),
                         text_color=pal["accent"], width=16, height=20).pack(side="right")
            if not clickable:
                continue
            for w in (row, inner) + tuple(inner.winfo_children()):
                try:
                    w.configure(cursor="hand2")
                except Exception:
                    pass
                w.bind("<Button-1>", lambda _e, k=stat_id: self._toggle_dashboard_stat(k))

    def _toggle_dashboard_stat(self, stat_id):
        """Klik na riadok vo vybere alebo ✕ na karte. Strop kariet aj
        "posledna ostava" rata `toggle_dashboard_stat`; ked sa nic nezmeni,
        nic sa neuklada ani neprestavuje."""
        new = toggle_dashboard_stat(self.dashboard_stats, stat_id)
        if new == self.dashboard_stats:
            return
        self.dashboard_stats = new
        self.save_settings()
        self._rebuild_dashboard_stats_grid()
        self._render_dashboard_picker_rows()

    # ---- presun karty potiahnutim (vymena miest) ----
    #
    # Chytis kartu (cislo, popisok, okraj - nie ⓘ/✕), potiahnes aspon
    # DASHBOARD_DRAG_PX a pustis ju na inu kartu: vymenia si miesto. Pri
    # mriezke 2x2 je vymena presne predvidatelna - zvyraznena karta je
    # presne tam, kam tvoja dopadne. Ziadne "duchove" okno, animacia ani
    # posuvanie ostatnych kariet.
    #
    # ROZHODUJE PUSTENIE, nie pohyb: vzdialenost stlacenie->pustenie a
    # karta pod bodom pustenia. Pohyb len kresli zvyraznenie a kurzor.
    # Pri skutocnej mysi totiz niekedy do Tk nepride ani jeden B1-Motion
    # (rychly svih, touchpad) - drop, ktory by na nom zavisel, by sa ticho
    # stratil.

    DASHBOARD_DRAG_PX = 8

    def _dashboard_card_at(self, x_root, y_root):
        """stat_id karty pod bodom obrazovky, alebo None (medzera, mimo)."""
        for stat_id, card in getattr(self, "dashboard_cards", {}).items():
            try:
                x0, y0 = card.winfo_rootx(), card.winfo_rooty()
                if (x0 <= x_root < x0 + card.winfo_width()
                        and y0 <= y_root < y0 + card.winfo_height()):
                    return stat_id
            except Exception:
                continue
        return None

    def _dashboard_drag_reset(self):
        """Zhodi zvyraznenie aj kurzor. Vola sa pri KAZDOM stlaceni: ked sa
        pustenie stratilo (alt-tab uprostred tahu), nic neostane visiet."""
        st, self._dashboard_drag_state = getattr(self, "_dashboard_drag_state", None), None
        for card in getattr(self, "dashboard_cards", {}).values():
            try:
                card.set_drag_look(None)
            except Exception:
                pass
        if st and st.get("widget") is not None:
            try:
                st["widget"].configure(cursor="")
            except Exception:
                pass

    def _dashboard_drag(self, stat_id, phase, event):
        if phase == "press":
            self._dashboard_drag_reset()
            self._dashboard_drag_state = {
                "id": stat_id, "x": event.x_root, "y": event.y_root,
                "widget": event.widget, "active": False, "target": None}
            return
        st = getattr(self, "_dashboard_drag_state", None)
        if not st or st["id"] != stat_id:
            return
        moved = (abs(event.x_root - st["x"]) + abs(event.y_root - st["y"])
                 >= self.DASHBOARD_DRAG_PX)
        cards = getattr(self, "dashboard_cards", {})
        if phase == "move":
            if not st["active"]:
                if not moved:
                    return
                st["active"] = True
                if stat_id in cards:
                    cards[stat_id].set_drag_look("source")
                try:
                    st["widget"].configure(cursor="fleur")
                except Exception:
                    pass
            target = self._dashboard_card_at(event.x_root, event.y_root)
            if target == stat_id:
                target = None
            if target != st["target"]:
                if st["target"] in cards:
                    cards[st["target"]].set_drag_look(None)
                if target in cards:
                    cards[target].set_drag_look("target")
                st["target"] = target
            return
        if phase != "release":
            return
        self._dashboard_drag_reset()
        if not moved:
            return                              # obycajny klik
        target = self._dashboard_card_at(event.x_root, event.y_root)
        new = swap_dashboard_stats(self.dashboard_stats, stat_id, target)
        if new == self.dashboard_stats:
            return                              # medzera, mimo, sama na seba
        self.dashboard_stats = new
        self.save_settings()
        # after_idle: prestavba znici aj widget, ktory prave vybavuje event
        self.root.after_idle(self._rebuild_dashboard_stats_grid)

    # POZN: tu bolo `_refresh_kamae_metrics()` - dlzka relacie, pocet
    # pripomienok a tep, kreslene vpravo v dychajucom pase. Odstranene:
    # dlzka aj pocet su o kusok vedla v pravom paneli tejto istej stranky,
    # takze pas ich len opakoval, a pas ma niest stav, nie skore.
    # `self._listen_started` sa pouziva dalej (dlzka relacie v paneli).

    # ---------- Panel v hre so 4 zakladnymi funkciami (HUD trigger row) ----------
    #
    # POZNAMKA K HISTORII: toto boli povodne dve metody pre celoappkovy
    # "Minimalisticky rezim" (zmensoval cele okno appky na 320x160 -
    # `set_minimal_mode`/`_apply_minimal_mode`, teraz odstranene). Rovnaky
    # zoznam 4 funkcii sa ale hodi aj tu - je to ten isty udaj (nazov
    # vizualu + popisok + kombinacia klaves pre sloty 0..3), len teraz
    # kresleny ako riadok pod HUD panelom v hre (`hud_paint.render_hud_
    # trigger_row`), nie ako samostatne okno appky.

    def _sync_hud_trigger_state(self):
        """Zosedivi ikonky, kym je panel s tepom vypnuty.

        Bez toho je to prepinac, ktory sa da zapnut a nic nespravi - a to je
        horsie nez prepinac, ktory sa zapnut neda.
        """
        stav = "normal" if self.hud_config.get("enabled") else "disabled"
        for widget in (getattr(self, "hud_trigger_switch", None),
                       getattr(self, "hud_trigger_swatch", None)):
            try:
                if widget is not None:
                    widget.configure(state=stav)
            except Exception:
                pass

    def _hud_trigger_info(self):
        """[(nazov vizualu, enabled)] pre riadok 4 zakladnych funkcii pod HUD
        panelom - poziciou zodpovedaju self.slots[0..3].

        POPISOK POD IKONKOU TU UZ NIE JE.
        Do 19. 9. sa pod kazdu ikonku kreslil `slot.display_key()`, cize
        'C', 'R', 'Mys: right', 'F'. Boli to klavesy z `DEFAULT_SLOT`, ktore
        od fazy 3 nespustaju nic - appka klavesy vobec necita. Hrac teda
        priamo v hre cital navod, ktory neplatil, a stlacanim tych klaves
        nedosiahol nic.

        Nahradzat ich popiskom nema zmysel: riadok je vysoky par pixelov a
        ma byt periferny. Ikonka je ta ista grafika, ktoru hrac uvidi, ked
        hlaska pride - to staci.
        """
        visuals = ("grounding", "jaw", "release", "breath")
        out = []
        # getattr, nie self.slots priamo: _apply_hud_config() sa vola z
        # __init__ este PRED self.slots = [] (riadok nizsie v __init__),
        # takze pri prvom zavolani atribut este neexistuje vobec.
        slots = getattr(self, "slots", [])
        for i, visual_name in enumerate(visuals):
            enabled = True
            if i < len(slots):
                enabled = bool(getattr(slots[i], "enabled_value", True))
            out.append((visual_name, enabled))
        return out

    def _on_hud_trigger_click(self, index):
        """Klik na ikonu v HUD riadku (len v nahlade v appke, v hre je
        panel click-through - viz hud.StatsHud.handle_click) spusti tu
        istu funkciu, ako keby hrac stlacil priradeny kláves."""
        if 0 <= index < len(self.slots):
            self.fire_slot(self.slots[index], source="hud_panel")

    def _refresh_hud_trigger_row(self):
        """Prekresli zoznam 4 funkcii v HUD paneli - vola sa pri zmene
        slotov (rebind klavesy, zapnutie/vypnutie) aj pri zmene jazyka."""
        hud = getattr(self, "hud", None)
        if hud is None:
            return
        try:
            hud.configure_triggers(triggers=self._hud_trigger_info())
        except Exception:
            pass

    # ---------- HUD (zivy panel so statistikou tepu) ----------

    def _apply_overlay_labels(self):
        """Popisky pod in-game vizualmi + slova dychoveho cyklu.

        Kreslia sa do obrazka, takze pri zmene jazyka ich treba manageru
        podat znova - preto je to samostatna metoda a nie parameter
        konstruktora.
        """
        g = self._game_text
        self.overlay_manager.set_labels(
            {0: g("overlay.caption.grounding"),
             1: g("overlay.caption.jaw"),
             2: g("overlay.caption.release")},
            breath_inhale=g("overlay.caption.inhale"),
            breath_exhale=g("overlay.caption.exhale"))

    @staticmethod
    def _game_lang_label(code):
        return (LANG_NATIVE_LABELS.get(code) if code in LANGUAGES
                else tr("settings.game_lang_same"))

    def on_game_lang_change(self, label):
        """Prepne jazyk toho, co appka kresli do hry. Prekresli sa hned -
        HUD aj vizualy si popisky drzia ako hotovy obrazok."""
        self.game_lang = LABEL_TO_LANG.get(label, LANG_SAME_AS_APP)
        self.save_settings()
        self._apply_overlay_labels()
        self._apply_hud_labels()
        self.log(tr("log.game_lang", lang=self._game_lang_label(self.game_lang)))

    def _game_text(self, key, **kwargs):
        """Text, ktory appka kresli DO HRY - vlastny jazyk, nie jazyk okna.

        HUD sedi vlavo dole na hernej obrazovke a popisky su pod vizualmi;
        oboje konci na streame a na screenshotoch v obchode, kde to citaju
        aj ludia, ktori jazyk rozhrania nevedia. Predvolena je preto
        anglictina, aj ked appka bezi po slovensky.
        """
        return tr_lang(getattr(self, "game_lang", LANG_EN), key, **kwargs)

    def _hud_labels(self):
        g = self._game_text
        return {
            "load": g("hud.load"),
            "calm": g("hud.zone.calm"),
            "raised": g("hud.zone.raised"),
            "high": g("hud.zone.high"),
            "critical": g("hud.zone.critical"),
            "waiting": g("hud.waiting"),
            "calibrating": g("hud.calibrating"),
        }

    def _apply_hud_labels(self):
        self.hud.set_labels(self._hud_labels())

    def _apply_hud_config(self):
        """Prenesie ulozenu konfiguraciu HUD-u do bezuceho okna."""
        cfg = self.hud_config
        self.hud.set_style(self.overlay_manager.style)
        self._apply_hud_labels()
        self.hud.configure(enabled=cfg["enabled"], scale=cfg["scale"],
                           opacity=cfg["opacity"],
                           pos=(cfg["pos_x"], cfg["pos_y"]),
                           critical_bpm=self.hr_critical_bpm,
                           monitor_target=self.monitor_target)
        self.hud.configure_triggers(
            show=cfg["show_triggers"], icon_color=cfg["trigger_color"],
            triggers=self._hud_trigger_info(),
            on_click=self._on_hud_trigger_click)

    def on_hud_config_change(self, **kwargs):
        cfg = self.hud_config
        if "enabled" in kwargs:
            cfg["enabled"] = bool(kwargs["enabled"])
        if "scale" in kwargs:
            cfg["scale"] = clamp_float(kwargs["scale"], 0.6, 2.0, cfg["scale"])
        if "opacity" in kwargs:
            cfg["opacity"] = clamp_float(kwargs["opacity"], 0.25, 1.0, cfg["opacity"])
        if "pos" in kwargs:
            cfg["pos_x"] = clamp_float(kwargs["pos"][0], 0.0, 100.0, cfg["pos_x"])
            cfg["pos_y"] = clamp_float(kwargs["pos"][1], 0.0, 100.0, cfg["pos_y"])
        if "show_triggers" in kwargs:
            cfg["show_triggers"] = bool(kwargs["show_triggers"])
        if "trigger_color" in kwargs:
            # "" (prazdny retazec) znamena "vrat sa na farbu temy", rovnaka
            # konvencia ako pri farbe piktogramov vizualov (on_overlay_config_change)
            value = kwargs["trigger_color"]
            cfg["trigger_color"] = normalize_hud_config(
                {"trigger_color": value})["trigger_color"] if value else None
        self._apply_hud_config()
        # Zapnutie/vypnutie panela meni, ci maju podriadene ikonky co robit.
        self._sync_hud_trigger_state()
        # Dva prepinace na to iste (v Nastaveniach aj rychly na Dnes) drzime v
        # zhode. `.set()` nezavola command CTkSwitch-a, takze to nerekurzuje.
        if "enabled" in kwargs:
            for meno in ("hud_enabled_var", "hud_quick_var"):
                var = getattr(self, meno, None)
                if var is not None:
                    try:
                        var.set(bool(kwargs["enabled"]))
                    except Exception:
                        pass
        self.save_settings()

    def _hud_trigger_color_display(self):
        """Farba vzorky pri "Ukazat panel v hre" - vlastna, alebo akcent
        temy (rovnaka konvencia ako _overlay_color pre 4 vizualy)."""
        return self.hud_config.get("trigger_color") or self.pal["accent"]

    def pick_hud_trigger_color(self):
        """Vyber farby ikoniek v riadku 4 zakladnych funkcii pod HUD
        panelom - rovnaky system-native color picker ako pri vizualoch
        (pick_overlay_color), len ulozeny do hud_config namiesto
        overlay_configs."""
        from color_picker import ask_color, DEFAULT
        current = self._hud_trigger_color_display()
        res = ask_color(self, current, title=tr("overlay.color_title"))
        if res is None:
            return
        self.on_hud_config_change(trigger_color=(None if res == DEFAULT else res))
        swatch = getattr(self, "hud_trigger_swatch", None)
        if swatch is not None:
            try:
                display = self._hud_trigger_color_display()   # None -> akcent temy
                swatch.configure(fg_color=display, hover_color=display)
            except Exception:
                pass

    def _toggle_snooze_menu(self):
        """Rozbali/zabali male menu s vyberom dlzky stisenia (5/20/40/60
        min) pri tlacidle 😴 v doku bocneho panela.

        POZOR - TOTO MENU NEMA V 2.1 SPUSTAC. Tlacidlo 😴 odislo s rychlym
        dokom (viz `_build_ui`) a odlozenie sa zapina globalnou skratkou na
        pevnych `SNOOZE_HOTKEY_MINUTES` minut. Volba dlzky tak nie je
        dostupna nikde.

        Kod je NECHANY zamerne, nie prehliadnutim: volba dlzky je prirodzeny
        kandidat na jeden z piatich jednoduchych ovladacov zo zadania §3.1,
        o ktorych sa este nerozhodlo. Ked padne rozhodnutie, staci to
        zavolat odtial; ak sa rozhodne inak, patri to prec.

        Anchor si berie z `quick_dock`, ktory uz neexistuje, takze metoda
        skonci hned na `anchor is None` - nespadne, len nic neurobi.

        Kreslene ako CTkToplevel bez OS ramu (rovnaky vzor ako ostatne
        docasne popup-y v appke), zatvara sa klikom mimo neho alebo
        opakovanym klikom na 😴.

        POZN: menu predtym viselo pod ozubenym kolieskom na stranke V hre.
        Kotvi sa preto teraz VPRAVO od tlacidla, nie pod nim - dok sedi pri
        dolnom okraji okna, takze pod nim uz nie je miesto a menu by
        vyliezlo mimo obrazovky."""
        existing = getattr(self, "_snooze_menu", None)
        if existing is not None and existing.winfo_exists():
            existing.destroy()
            self._snooze_menu = None
            return

        dock = getattr(self, "quick_dock", None)
        anchor = getattr(dock, "snooze_btn", None) if dock is not None else None
        if anchor is None or not anchor.winfo_exists():
            return
        pal = self.pal
        menu = ctk.CTkToplevel(self.root)
        menu.overrideredirect(True)
        menu.attributes("-topmost", True)
        card = ctk.CTkFrame(menu, fg_color=pal["surface"], corner_radius=ui_kit.RADIUS_CONTROL,
                            border_width=1, border_color=pal["border"])
        card.pack(fill="both", expand=True)

        def pick(minutes):
            self._start_snooze(minutes)
            menu.destroy()
            self._snooze_menu = None

        for minutes, key in ((5, "hud.snooze.5min"), (20, "hud.snooze.20min"),
                             (40, "hud.snooze.40min"), (60, "hud.snooze.60min")):
            ctk.CTkButton(card, text=tr(key), anchor="w", height=30, width=130,
                         fg_color="transparent", hover_color=pal["surface_alt"],
                         text_color=pal["text"], font=ui_kit.ui(11),
                         command=lambda m=minutes: pick(m)).pack(fill="x", padx=4, pady=2)
        if getattr(self, "_snooze_job", None) is not None:
            ctk.CTkButton(card, text=tr("hud.snooze.cancel"), anchor="w", height=30, width=130,
                         fg_color="transparent", hover_color=pal["danger"],
                         text_color=pal["text"], font=ui_kit.ui(11),
                         command=lambda: (self._cancel_snooze(), menu.destroy(),
                                          setattr(self, "_snooze_menu", None))
                         ).pack(fill="x", padx=4, pady=(2, 4))

        # Poloha az TERAZ, ked je menu naplnene: pred zabalenim poloziek je
        # winfo_reqheight() rovne 1 a menu by sa zarovnalo uplne mimo.
        menu.update_idletasks()
        x = anchor.winfo_rootx() + anchor.winfo_width() + 6
        y = anchor.winfo_rooty() + anchor.winfo_height() - menu.winfo_reqheight()
        menu.geometry(f"+{x}+{max(0, y)}")

        menu.bind("<FocusOut>", lambda _e: self.root.after(120, self._close_snooze_menu))
        # Klik inam v hlavnom okne menu zavrie. Viazeme raz za beh appky
        # (nie pri kazdom otvoreni), obsluha sama nic nerobi, ked menu nie
        # je otvorene - tak netreba nic odviazovat a nehromadia sa vazby.
        if not getattr(self, "_snooze_click_bound", False):
            self.root.bind("<ButtonRelease-1>", self._on_click_outside_snooze, add="+")
            self._snooze_click_bound = True
        menu.focus_force()
        self._snooze_menu = menu

    def _close_snooze_menu(self):
        """Zavrie snooze menu, ked hrac prepol na INU APPKU (FocusOut).

        Podmienka `focus_get() is None` znamena "ziadny prvok TEJTO appky
        nema fokus". Vyzera prilis volne, ale prisnejsie kriterium ("fokus
        nie je v menu") tu NEFUNGUJE: menu je overrideredirect Toplevel a
        jeho `focus_force()` na Windows fokus neudrzi - FocusOut priletí
        hned po otvoreni a menu by zmizlo skor, nez by si ho hrac vobec
        vsimol (overene naživo, zavrelo sa do 150 ms).

        Klik inam VO VNUTRI okna appky preto rieši `_on_click_outside_snooze`,
        nie tato metoda."""
        menu = getattr(self, "_snooze_menu", None)
        if menu is not None and menu.winfo_exists():
            try:
                if self.root.focus_get() is None:
                    menu.destroy()
                    self._snooze_menu = None
            except Exception:
                pass

    def _on_click_outside_snooze(self, _event=None):
        """Klik kamkolvek v hlavnom okne zavrie otvorene snooze menu.

        Menu je samostatny Toplevel, takze kliky V NOM sa sem vobec
        nedostanu - tato obsluha vidi len kliky do hlavneho okna, teda
        presne tie "mimo menu".

        Viazane na <ButtonRelease-1>, NIE <Button-1>, a je to podstatne:
        CTkButton spusta svoj command az na release a vazba widgetu bezi
        PRED vazbou okna. Klik na 😴 teda najprv prejde cez
        `_toggle_snooze_menu` (ktore menu zavrie) a sem uz dojde None.
        Keby to viselo na <Button-1>, press by menu zavrel a nasledny
        release na tlacidle by ho hned znova otvoril - druhy klik na 😴
        by menu nikdy nezavrel."""
        menu = getattr(self, "_snooze_menu", None)
        if menu is None or not menu.winfo_exists():
            return
        try:
            menu.destroy()
        except Exception:
            pass
        self._snooze_menu = None

    def test_hud(self):
        """Ukaze HUD aj ked je vypnuty, aby si hrac overil polohu voci
        HUD-u svojej hry. Po 4 sekundach ho zase schova."""
        was_enabled = self.hud_config["enabled"]
        self.hud.configure(enabled=True)
        if not was_enabled:
            self.root.after(4000, lambda: self.hud.configure(
                enabled=self.hud_config["enabled"]))

    def on_monitor_target_change(self, target):
        """Prepnutie cieloveho monitora pre vizualy aj HUD."""
        self.monitor_target = normalize_monitor_target(target)
        self.overlay_manager.set_monitor_target(self.monitor_target)
        self.hud.configure(monitor_target=self.monitor_target)
        self.save_settings()
        self.log(tr("log.monitor_target", target=self._monitor_label(self.monitor_target)))

    def _monitor_label(self, target):
        if target == "auto":
            return tr("overlay.monitor.auto")
        if target == "cursor":
            return tr("overlay.monitor.cursor")
        if target == "primary":
            return tr("overlay.monitor.primary")
        found = display.monitors(self.root)
        idx = int(target) if str(target).isdigit() else 0
        if 0 <= idx < len(found):
            return found[idx].label(idx)
        return tr("overlay.monitor.auto")

    def monitor_choices(self):
        """[(popisok, hodnota)] pre dropdown vyberu monitora."""
        options = [(tr("overlay.monitor.auto"), "auto"),
                   (tr("overlay.monitor.cursor"), "cursor"),
                   (tr("overlay.monitor.primary"), "primary")]
        for i, mon in enumerate(display.monitors(self.root)):
            options.append((mon.label(i), str(i)))
        return options

    def _refresh_hud_session_text(self):
        stats = self.hr_stats
        elapsed = int(max(0.0, time.time() - stats.session_start))
        parts = [f"{elapsed // 60:02d}:{elapsed % 60:02d}",
                 self._game_text("hud.session.triggers", n=stats.triggers)]
        if stats.time_over >= 1.0:
            over = int(stats.time_over)
            parts.append(self._game_text("hud.session.over",
                                         time=f"{over // 60}:{over % 60:02d}"))
        self.hud.set_session_text("  ·  ".join(parts))

    # ---------- vyvojarska vrstva (faza 5, §3.2) ----------

    def open_dev_layer(self):
        """Otvori ladenie. Volane z patnasteho kliku na cislo verzie."""
        try:
            DevLayerDialog(self)
        except Exception:
            app_log.exception("vyvojarska vrstva sa nepodarila otvorit")

    def apply_dev_params(self, params, silent_share):
        """Ulozi nove prahy. Platia AZ OD DALSEJ relacie.

        Zadanie §3.3: parametre sa menia len medzi relaciami. Dialog to uz
        vynutil tym, ze pri beziacej relacii polia zamkol; tu sa hodnoty
        len odlozia a `start_heart_rate_monitor` ich vezme.
        """
        params = dict(params)
        # TVRDA POISTKA PLATI AJ TU.
        #
        # Vyvojarska vrstva je na ladenie prahov, nie na obchadzanie hranice,
        # ktora chrani meranie: pri odstupe pod `measure.REFRACTORY_AFTER_S`
        # (180 s) pristane druha hlaska do meracieho okna prvej a obe okna sa
        # zneplatnia. Preklep v policku by tak nepokazil jeden vecer, ale
        # cely tyzden dat - a v datach by to vyzeralo ako "hlaska nezabrala".
        odstup = params.get("min_gap_s")
        if odstup is not None and float(odstup) < trigger.MIN_GAP_FLOOR_S:
            params["min_gap_s"] = trigger.MIN_GAP_FLOOR_S
            self.log(tr("dev.min_gap_clamped", s=f"{trigger.MIN_GAP_FLOOR_S:g}"))
        self._dev_params = params
        self._dev_silent_share = silent_share
        self.cue_trigger.params.update(params)
        self.cue_trigger.silent_share = silent_share
        self.log(tr("dev.applied"))

    def dev_force_cue(self):
        """Vystreli hlasku hned, bez cakania na telo aj na pauzu.

        Zamerne NEPOUZIVA `cue_trigger` - vynutena hlaska nie je meranie a
        nesmie sa dostat do okien ani spalit refrakternu zonu. Je to len
        na to, aby sa dal pocut zvuk a vidiet vizual.
        """
        index = self.CUE_SLOT_INDEX
        try:
            self.overlay_manager.trigger(index)
            slot = next((s for s in self.slots if s.index == index), None)
            if slot is not None:
                threading.Thread(target=self._emit, args=(slot,), daemon=True).start()
        except Exception:
            app_log.exception("vynutena hlaska zlyhala")

    # ---------- In-Game Vizualy (Overlay) ----------

    # hysterezia pasma: nove pasmo musi vydrzat, inak by kontrolka na
    # hranici (napr. stres kolisajuci okolo 25) blikala medzi dvoma
    # farbami pri kazdom tepe
    WATCH_ZONE_HOLD_S = 1.5

    def _watch_pulse_state(self):
        """Stav kontrolky tepu v bocnom paneli:
        (spojene, caka_na_tep, pasmo, faza_tepu).

        Faza ide z `HeartStats.beat_phase()` - z toho isteho zdroja ako
        srdce na HUD-e v hre, takze oba bijú naraz. Pevna animacia (napr.
        raz za sekundu) je bezna chyba: kontrolka by potom ukazovala iny
        tep, nez aky hodinky naozaj hlasia.
        """
        if not self.hr_monitoring_enabled:
            # Senzor je vypnuty - zahod aj drzane pasmo, inak by kontrolka
            # po opatovnom zapnuti bliskala 1,5 s STARYM pasmom z predoslej
            # relacie (hysterezia by drzala napr. cervenu, hoci hrac medzitym
            # vychladol).
            self._watch_zone = None
            self._watch_zone_cakajuce = None
            return False, False, None, 0.0
        stats = self.hr_stats
        bpm = getattr(stats, "last_bpm", None)
        if not bpm:
            # Senzor bezi, ale data nechodia (este neprisli, alebo hodinky
            # vypadli). Pasmo zahadzujeme z rovnakeho dovodu ako vyssie.
            self._watch_zone = None
            self._watch_zone_cakajuce = None
            return True, True, None, 0.0

        # Pocas kalibracie HUD aj Dnes pisu "kalibrujem…" - kontrolka nesmie
        # popri tom svietit pasmom. Neutralna farba, tep bije dalej. To iste
        # par vzoriek po navrate tepu (`is_settling`): zataz sa rozbieha od
        # nuly a zelena by tvrdila pokoj, ktory appka nevie.
        if (getattr(stats, "is_calibrating", False)
                or getattr(stats, "is_settling", False)):
            nove = "neutral"
        else:
            # To iste pasmo ako HUD a Dnes - pocita sa len v `HeartStats.zone`.
            nove = stats.zone
        teraz = time.monotonic()
        drzane = getattr(self, "_watch_zone", None)
        if nove != getattr(self, "_watch_zone_cakajuce", None):
            self._watch_zone_cakajuce = nove
            self._watch_zone_od = teraz
        if drzane is None:
            # prve pasmo po pripojeni sa berie HNED, nie az po hysterezii -
            # inak by kontrolka zacala v nahodnom pasme
            self._watch_zone = nove
        elif (nove != drzane
              and teraz - getattr(self, "_watch_zone_od", teraz) >= self.WATCH_ZONE_HOLD_S):
            self._watch_zone = nove
        return True, False, self._watch_zone, stats.beat_phase()

    def open_watch_pairing(self):
        """Ikona hodiniek ZAPINA a otvara panel. Vypnut sa nou neda (§1.10).

        Predtym len otvarala dialog. Ked bol senzor vypnuty, hrac tak dostal
        parovaci panel nad vypnutym senzorom: postupoval podla neho, appka
        nic neprijala a nikde nestalo preco. Teraz klik znamena "chcem to",
        cize sa senzor rovno zapne.

        Vypinanie zostava tam, kde bolo - prepinac v nastaveniach. Ikona,
        ktora raz zapne a inokedy vypne, je pri jednom piktograme bez
        popisku necitatelna: hrac nevie, ci klikom zapina alebo vypina, kym
        neklikne.

        Vsetkych pat volajucich je za klikom hraca - dve z nich az po tom,
        co si v onboardingu vybral "Sparovat hodinky teraz" (app.py:406,
        2336). Appka teda senzor nezapne nikdy sama od seba.
        """
        self._enable_hr_monitoring()
        WatchPairingDialog(self)

    def _enable_hr_monitoring(self):
        """Zapne senzor tepu, ak este nebezi. Vrati True, ak sa naozaj zapol.

        Ked uz bezi, NEROBI NIC - `start_heart_rate_monitor` vynuluje
        relaciu (`hr_stats.reset_session`), takze zavolat ho na beziacej
        relacii by zahodilo vecer nazbieranych dat len preto, ze hrac
        otvoril parovaci panel.
        """
        if self.hr_monitoring_enabled:
            return False
        self.hr_monitoring_enabled = True
        # Prepinac v nastaveniach existuje az po postaveni tej stranky.
        if self.hr_enabled_var is not None:
            try:
                self.hr_enabled_var.set(True)
            except Exception:
                pass
        self.save_settings()
        self.start_heart_rate_monitor()
        self._refresh_nav_badges()
        return True

    def open_overlay_settings(self):
        OverlaySettingsDialog(self)

    def on_overlay_config_change(self, index, **kwargs):
        if not (0 <= index < len(self.overlay_configs)):
            return
        cfg = self.overlay_configs[index]
        if "enabled" in kwargs:
            cfg["enabled"] = bool(kwargs["enabled"])
            if index == 3 and cfg["enabled"]:
                # dychaci kruh je zas zapnuty - radu o vypnutom vizuali
                # smieme hracovi pripomenut, ak si ho znova vypne
                self._hr_overlay_warned = False
        if "scale" in kwargs:
            cfg["scale"] = clamp_float(kwargs["scale"], 0.5, 2.0, cfg["scale"])
        if "pos" in kwargs:
            pos_x, pos_y = kwargs["pos"]
            cfg["pos_x"] = clamp_float(pos_x, 0.0, 100.0, cfg["pos_x"])
            cfg["pos_y"] = clamp_float(pos_y, 0.0, 100.0, cfg["pos_y"])
        if "color" in kwargs:
            # None / "" = farba temy; inak overeny #rrggbb
            cfg["color"] = normalize_overlay_config({"color": kwargs["color"]},
                                                    index)["color"]
        self.overlay_manager.configure(index, enabled=cfg["enabled"], scale=cfg["scale"],
                                       pos=(cfg["pos_x"], cfg["pos_y"]),
                                       color=cfg["color"] or "")
        self.save_settings()

    def on_breath_seconds_change(self, inhale=None, exhale=None):
        """Dlzka nadychu/vydychu dychoveho kruhu (v sekundach) - slider v
        "In-Game Vizuály" pri slote Dych."""
        new_inhale = self.breath_inhale_s if inhale is None else inhale
        new_exhale = self.breath_exhale_s if exhale is None else exhale
        self.breath_inhale_s, self.breath_exhale_s = normalize_breath_seconds(
            new_inhale, new_exhale)
        self.overlay_manager.set_breath_seconds(self.breath_inhale_s, self.breath_exhale_s)
        self.save_settings()

    def _overlay_color(self, index):
        """Farba piktogramu slotu pre UI - vlastna, alebo akcent temy."""
        cfg = self.overlay_configs[index]
        return cfg.get("color") or self.pal["accent"]

    def toggle_overlay_test(self, index):
        """Prepne drag-test rezim vizualu.

        Prve kliknutie zobrazi vizual NASTALO a da sa tahat mysou; tlacidlo
        sa zmeni na "Hotovo". Druhe kliknutie test ukonci a ULOZI polohu,
        na ktoru ho hrac potiahol. Poloha sa vrati cez callback
        set_test_moved_callback -> _on_overlay_test_moved.
        """
        # nauc manager, kam ulozit novu polohu po skonceni tohto testu
        self.overlay_manager.set_test_moved_callback(
            index, lambda px, py, i=index: self._on_overlay_test_moved(i, px, py))
        testing = self.overlay_manager.test(index)
        self._refresh_test_button(index, testing)
        # ak sa zaplo testovanie ineho slotu, jeho tlacidlo treba vratit
        for i in range(4):
            if i != index:
                self._refresh_test_button(i, self.overlay_manager.is_testing(i))

    def _refresh_all_test_buttons(self):
        """Zosuladi vsetky styri tlacidla Test so skutocnym stavom.

        Volat po hromadnom ukonceni testov - inak by tlacidlo dalej hlasilo
        "Hotovo" pri vizuale, ktory uz nebezi.
        """
        for index in range(4):
            try:
                self._refresh_test_button(
                    index, self.overlay_manager.is_testing(index))
            except Exception:
                pass

    def _refresh_test_button(self, index, testing):
        btn = getattr(self, "vhre_test_buttons", {}).get(index)
        if btn is None:
            return
        try:
            btn.configure(
                text=tr("overlay.test_done") if testing else tr("overlay.test"),
                fg_color=self.pal["accent2"] if testing else "transparent",
                text_color=self.pal["text"] if testing else self.pal["text_dim"])
        except Exception:
            pass

    def _on_overlay_test_moved(self, index, px, py):
        """Vizual bol potiahnuty na novu polohu - uloz ju do konfiguracie."""
        cfg = self.overlay_configs[index]
        cfg["pos_x"], cfg["pos_y"] = round(px, 1), round(py, 1)
        self.overlay_manager.configure(index, pos=(cfg["pos_x"], cfg["pos_y"]))
        self.save_settings()
        self._refresh_test_button(index, False)

    def pick_overlay_color(self, index):
        """Otvori vlastny (Zanshin) vyber farby piktogramu pre dany vizual.

        Vrati hex farbu, DEFAULT (vrat farbu temy = color=None), alebo None
        pri zruseni (vtedy sa nic nemeni).
        """
        from color_picker import ask_color, DEFAULT
        current = self._overlay_color(index)
        res = ask_color(self, current, title=tr("overlay.color_title"))
        if res is None:
            return
        self.on_overlay_config_change(index, color=(None if res == DEFAULT else res))
        swatch = getattr(self, "vhre_color_swatches", {}).get(index)
        if swatch is not None:
            try:
                display = self._overlay_color(index)   # None -> akcent temy
                swatch.configure(fg_color=display, hover_color=display)
            except Exception:
                pass

    def test_overlay(self, index):
        # zachovane pre spatnu kompatibilitu (paleta prikazov, onboarding)
        self.toggle_overlay_test(index)

    # ---------- log ----------

    def log(self, message):
        stamp = time.strftime("%H:%M:%S")
        self._last_log_line = f"[{stamp}] {message}"
        if self.log_text is None:
            print(self._last_log_line)
            return
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{self._last_log_line}\n")
        self.log_text.see("end")
        if int(self.log_text.index("end-1c").split(".")[0]) > 200:
            self.log_text.delete("1.0", "50.0")
        self.log_text.configure(state="disabled")
        try:
            self.log_toggle_btn.configure(text=self._log_toggle_text())
        except Exception:
            pass

    def ui_call(self, func):
        """Naplanuje volanie v GUI vlakne. Bezpecne z lubovolneho vlakna aj
        pocas ukoncovania aplikacie (vtedy Tk uz volanie odmietne).

        PRVE ZLYHANIE SA ZALOGUJE. Predtym tu bolo holé `pass` a to skryva
        celu triedu chyb: `root.after` z cudzieho vlakna vyhodi
        RuntimeError("main thread is not in main loop") vzdy, ked Tk nebezi
        na `mainloop()`, a volajuci sa o tom nedozvie nic - callback proste
        nepride. Stalo sa to pri ladeni hotkey: stlacenie dorazilo az do
        `_on_snooze_hotkey`, `ui_call` ho zhltol a snooze sa nezapol.

        Dalsie vyskyty sa uz len pocitaju: ked sa appka ukoncuje, odmietnutych
        volani moze prist vela naraz a log by sa zaplavil.
        """
        try:
            self.root.after(0, func)
            return
        except RuntimeError:
            # Tk este nie je v `mainloop()`. Deje sa to pri KAZDOM starte:
            # `_ensure_sfx_assets` aj priprava Edge hlasok bezia na vlastnom
            # vlakne uz z `__init__` a logovat zacnu skor,
            # nez sa slucka rozbehne. Predtym sa tie riadky ticho zahadzovali.
            #
            # Odlozime a dorucime, ked sa slucka rozbehne - `_flush_ui_pending`
            # je naplanovany z hlavneho vlakna, takze na nom `after` funguje.
            try:
                self._ui_pending.append(func)
            except Exception:
                pass
            return
        except Exception:
            pass
        self._ui_call_fails = getattr(self, "_ui_call_fails", 0) + 1
        if self._ui_call_fails == 1:
            app_log.exception(
                "ui_call: volanie sa nepodarilo naplanovat "
                "(dalsie vyskyty sa uz nevypisu)")

    def _flush_ui_pending(self):
        """Doruci volania, ktore prisli z vlakien skor, nez sa rozbehol
        `mainloop()`. Vola sa raz, hned ako sa slucka rozbehne."""
        fronta, self._ui_pending = list(self._ui_pending), deque(maxlen=200)
        for func in fronta:
            try:
                func()
            except Exception:
                app_log.exception("ui_call: odlozene volanie zlyhalo")

    def log_threadsafe(self, message):
        self.ui_call(lambda: self.log(message))

    def set_typing(self, value):
        self.typing = bool(value)

    # ---------- hlasy ----------

    def on_voices_ready(self, items):
        self.ui_call(lambda: self._apply_sapi_voices(items))

    def _apply_sapi_voices(self, items):
        self.voice_map = {name: vid for vid, name in items}
        if not self.saved_voice_id and items:
            self.saved_voice_id = items[0][0]
        if self.saved_voice_id:
            self.worker.set_voice(self.saved_voice_id)
        if self.engine == ENGINE_SAPI:
            self.refresh_voice_box()
        self.refresh_slot_summaries()

    def _load_edge_voices(self, pregen=True):
        """Naplni vyber Edge hlasov z pevneho zoznamu - bez siete, takze
        priamo na Tk vlakne (predtym vlakno + stiahnutie katalogu)."""
        self._apply_edge_voices(EdgeTTSCache.list_voices(), pregen=pregen)

    def _apply_edge_voices(self, items, pregen=True):
        self.edge_voice_map = {name: short for short, name in items}
        known = set(self.edge_voice_map.values())
        if self.edge_voice_id not in known:
            self.edge_voice_id = (DEFAULT_EDGE_VOICE if DEFAULT_EDGE_VOICE in known
                                  else (items[0][0] if items else DEFAULT_EDGE_VOICE))
        if self.engine == ENGINE_EDGE:
            self.refresh_voice_box()
            if pregen:
                self.pregenerate()
        self.refresh_slot_summaries()

    def current_voice_map(self):
        return (self.edge_voice_map if self.engine == ENGINE_EDGE
                else self.voice_map)

    def current_voice_names(self):
        return list(self.current_voice_map().keys())

    def voice_id_for_label(self, label):
        return self.current_voice_map().get(label, "")

    def slot_voice_label(self, slot):
        vid = slot.voice_edge if self.engine == ENGINE_EDGE else slot.voice_sapi
        if not vid:
            return ""
        for label, candidate in self.current_voice_map().items():
            if candidate == vid:
                return label
        return vid

    def set_slot_voice(self, slot, voice_id):
        if self.engine == ENGINE_EDGE:
            slot.voice_edge = voice_id
        else:
            slot.voice_sapi = voice_id

    def refresh_slot_summaries(self):
        for slot in self.slots:
            slot.refresh_summary()

    def refresh_voice_box(self):
        mapping = self.current_voice_map()
        current = (self.edge_voice_id if self.engine == ENGINE_EDGE
                   else self.saved_voice_id)
        names = list(mapping.keys())
        self.voice_box.configure(values=names or [tr("voice.none")])
        label = next((n for n, vid in mapping.items() if vid == current), None)
        if label is None and names:
            label = names[0]
        if label:
            self.voice_var.set(label)
            if self.engine == ENGINE_EDGE:
                self.edge_voice_id = mapping[label]
            else:
                self.saved_voice_id = mapping[label]
                self.worker.set_voice(self.saved_voice_id)
        elif not names:
            self.voice_var.set(tr("voice.loading"))

    def on_engine_change(self):
        engine = label_to_engine().get(self.engine_var.get(), ENGINE_SAPI)
        if engine == ENGINE_EDGE and not audio_engine.EDGE_AVAILABLE:
            self.engine_pref = ENGINE_EDGE
            self.engine_var.set(engine_labels()[ENGINE_SAPI])
            self.save_settings()
            self.refresh_edge_banner()
            messagebox.showwarning(APP_NAME, tr("msgbox.edge_missing_body"))
            return
        if engine == self.engine:
            return
        self.engine = self.engine_pref = engine
        self.refresh_edge_banner()
        self.refresh_voice_box()
        self.refresh_slot_summaries()
        self.save_settings()
        self.log(tr("log.engine_switched", engine=engine_labels()[engine]))
        if engine == ENGINE_EDGE:
            # Poistka: vyber Edge hlasov sa plni pri starte (bez siete); keby
            # bol prazdny, naplni sa teraz - inak by bol combobox prazdny.
            if not getattr(self, "edge_voice_map", None):
                self._load_edge_voices(pregen=False)
            self.pregenerate()
        else:
            self.set_edge_status("")

    def on_voice_change(self):
        label = self.voice_var.get()
        vid = self.current_voice_map().get(label)
        if not vid:
            return
        if self.engine == ENGINE_EDGE:
            self.edge_voice_id = vid
            self.save_settings()
            self.pregenerate()
        else:
            self.saved_voice_id = vid
            self.worker.set_voice(vid)
            self.save_settings()

    def on_rate_change(self):
        self.rate_value = int(self.rate_var.get())
        self.audio.rate = self.rate_value
        self.worker.set_rate(self.rate_value)
        label = getattr(self, "rate_value_label", None)
        if label is not None:
            try:
                label.configure(text=self._rate_label_text())
            except Exception:
                pass
        self.save_settings()
        if self.engine == ENGINE_EDGE:
            self.schedule_pregenerate()

    # ---------- predgenerovanie Edge hlasok ----------

    def set_edge_status(self, text, color=None):
        if self.edge_status_label is not None:
            try:
                self.edge_status_label.configure(text=text,
                                                 text_color=color or self.pal["text_dim"])
            except Exception:
                pass

    def _hlasky_hovoria(self):
        """Povie hlaska v hre vobec nieco hlasom (TTS)? Len v style "hlas"
        a mimo sveta Praca - tam ide len obrazom (`rebrik.vrchol`). Styl
        "zvuk" hra zvuk slotu bez slov a "obraz" len obrazok."""
        styl = rebrik.normalize_cue_style(getattr(self, "cue_style", None))
        return (styl == rebrik.STYL_HLAS
                and rebrik.vrchol(getattr(self, "world", None), styl) == rebrik.HLAS)

    def pregen_jobs(self):
        """[(text, hlas)] pre vsetky TTS/kombinovane sloty - respektuje hlas kazdeho slotu.

        Prazdne, ked hlasky v hre nehovoria (`_hlasky_hovoria`): hracovi,
        ktory zvolil len obrazok alebo zvuk bez slov, alebo je vo svete
        Praca, by sa inak texty hlasok posielali do Microsoftu zbytocne.
        """
        if not self._hlasky_hovoria():
            return []
        jobs = []
        for slot in self.slots:
            if slot.mode not in (MODE_TTS, MODE_COMBO) or not slot.text_value.strip():
                continue
            voice = slot.voice_edge or self.edge_voice_id
            pair = (slot.text_value, voice)
            if pair not in jobs:
                jobs.append(pair)
        return jobs

    def schedule_pregenerate(self, delay_ms=700):
        if self.engine != ENGINE_EDGE:
            return
        if self._pregen_job is not None:
            try:
                self.root.after_cancel(self._pregen_job)
            except Exception:
                pass
        self._pregen_job = self.root.after(delay_ms, self.pregenerate)

    def pregenerate(self, force=False):
        self._pregen_job = None
        if self.engine != ENGINE_EDGE or not audio_engine.EDGE_AVAILABLE:
            return
        rate = self.rate_value
        jobs = self.pregen_jobs()
        if not jobs:
            self.set_edge_status("")
            return

        self._pregen_seq += 1
        seq = self._pregen_seq
        if not force and all(self.edge_cache.has(t, v, rate) for t, v in jobs):
            self.set_edge_status(tr("edge.ready"), self.pal["success"])
            self._prune_cache(jobs, rate)
            return

        if getattr(self, "listening", False):
            # POCAS POCUVANIA SA NA MICROSOFT NECHODI - ani kvoli priprave.
            # Auto-profil prepne profil hry pri jej starte (`_handle_game_found`
            # -> `switch_profile` -> `schedule_pregenerate`) a pocuvanie sa
            # zapne hned za tym, takze priprava by inak isla na siet presne
            # vtedy, ked sa hra nacitava. Rovnako rucne prepnutie profilu alebo
            # zmena hlasu uprostred hry. Priprava sa odlozi a spusti ju az
            # `stop_listening` (`_dopriprav_hlasky_po_hre`) - ten isty
            # mechanizmus ako pre hlasku, ktora v hre chybala (`_speak_text`).
            # `_pregen_seq` vyssie uz zastavil pripadnu rozbehnutu pripravu.
            self._pregen_po_hre = True
            self.set_edge_status(tr("edge.after_game"), self.pal["text_dim"])
            return

        self.set_edge_status(tr("edge.generating"), self.pal["warn"])

        def work():
            ok = 0
            for text, voice in jobs:
                if seq != self._pregen_seq:
                    return
                if getattr(self, "listening", False):
                    # Pocuvanie sa zaplo uprostred pripravy: dalsia hlaska uz
                    # na siet nejde. O zvysku rozhodne `pregenerate` na
                    # GUI vlakne - pocas pocuvania ho odlozi na po hre.
                    self.ui_call(self.pregenerate)
                    return
                # Kontrola vyssie nestaci: `ensure` moze cakat na zamku cache,
                # kym ine (starsie) vlakno pripravy dokonci svoju hlasku - a
                # medzitym sa moze zapnut pocuvanie. `abort` sa preto pyta
                # znova az po ziskani zamku, tesne pred odoslanim.
                if self.edge_cache.ensure(
                        text, voice, rate,
                        abort=lambda: (seq != self._pregen_seq
                                       or getattr(self, "listening", False))):
                    ok += 1
            if seq != self._pregen_seq:
                return
            total = len(jobs)
            if ok < total and getattr(self, "listening", False):
                # Posledna hlaska sa vzdala na zamku, lebo sa zaplo pocuvanie
                # (alebo zlyhala a hra uz bezi) - nie je to chyba pripravy,
                # zvysok odlozi `pregenerate` na po hre.
                self.ui_call(self.pregenerate)
                return
            if ok == total:
                self.ui_call(lambda: self.set_edge_status(
                    tr("edge.ready"), self.pal["success"]))
                self.log_threadsafe(tr("log.edge_cache_ready", n=ok))
                self.ui_call(lambda: self._prune_cache(jobs, rate))
            else:
                self.ui_call(lambda: self.set_edge_status(
                    tr("edge.partial", ok=ok, total=total), self.pal["danger"]))

        threading.Thread(target=work, daemon=True).start()

    def _prune_cache(self, jobs, rate):
        keep = [self.edge_cache.path_for(t, v, rate) for t, v in jobs]
        threading.Thread(target=lambda: EdgeTTSCache.prune(keep),
                         daemon=True).start()

    # ---------- rozhodovanie o SFX subore ----------

    def resolve_sfx_path(self, slot):
        key = slot.sfx_key
        if key == "__custom__":
            return slot.audio_path if slot.audio_path and os.path.exists(slot.audio_path) \
                else None
        if key and ":" in key:
            pack, sound_key = key.split(":", 1)
            return sfx_assets.sound_path(pack, sound_key)
        if not key and slot.audio_path:
            return slot.audio_path if os.path.exists(slot.audio_path) else None
        # Predvolena sada ide za vzhladom - ale pocas relacie za SVETOM
        # RELACIE (B3-worlds): kto si uprostred hry len pozrie Pracu, nema
        # od dalsej hlasky pocut zvuky druheho sveta.
        pack = self.theme_key
        if getattr(self, "_hr_session_open", False):
            pack = theme_mod.WORLD_THEME.get(
                getattr(self, "_session_world", None), pack)
        default_key = sfx_assets.default_sound_for_slot_index(pack, slot.index)
        if not default_key:
            items = sfx_assets.library_items(pack)
            default_key = items[0][0] if items else None
        return sfx_assets.sound_path(pack, default_key) if default_key else None

    def _play_concurrent(self, path, volume):
        threading.Thread(target=self._play_now_safe, args=(path, volume), daemon=True).start()

    def _play_now_safe(self, path, volume):
        try:
            audio_engine.play_audio_file(path, volume)
        except Exception as exc:
            self.log_threadsafe(tr("log.sfx_playback_error", err=exc))

    def _play_voice_file(self, path):
        """Prehra VLASTNU nahravku hlasu - hlasitostou TTS a bez notch filtra
        (2-4 kHz), aby znela cela a zrozumitelna ako vlastny hlas. Vzdy vo
        vlastnom vlakne (subezne), rovnako ako SFX v kombinacii."""
        threading.Thread(target=self._voice_now_safe, args=(path,), daemon=True).start()

    def _voice_now_safe(self, path):
        try:
            audio_engine.play_audio_file(path, self.tts_volume, notch=False)
        except Exception as exc:
            self.log_threadsafe(tr("log.sfx_playback_error", err=exc))

    def _slot_voice_clip(self, slot):
        """Cesta k platnej vlastnej nahravke hlasu slotu, alebo None."""
        vp = getattr(slot, "voice_path", "")
        return vp if vp and os.path.exists(vp) else None

    def _slot_has_voice(self, slot):
        """Ma slot co povedat hlasom? Bud napisany text, alebo nahravka.
        Vdaka tomu sa nahravka prehra aj ked je textove pole prazdne."""
        return bool(slot.text_value.strip() or self._slot_voice_clip(slot))

    def _speak_text(self, text, slot, concurrent=False):
        # Vlastna nahravka hlasu ma prednost pred TTS: ak si clovek nahral
        # svoj hlas, prehra sa on - nie strojovy prevod textu.
        clip = self._slot_voice_clip(slot)
        if clip:
            self._play_voice_file(clip)
            return
        if self.engine == ENGINE_EDGE and audio_engine.EDGE_AVAILABLE:
            voice = slot.voice_edge or self.edge_voice_id
            if self.edge_cache.has(text, voice, self.rate_value):
                path = self.edge_cache.path_for(text, voice, self.rate_value)
                if concurrent:
                    self._play_concurrent(path, self.tts_volume)
                else:
                    self.audio.play_tts(path)
                return
            if not self._hlasky_hovoria():
                # Styl bez slov / svet Praca: hlasky v hre nehovoria, takze sa
                # nic nepripravuje (`pregen_jobs`) - ukazka zaznie cez SAPI.
                pass
            elif getattr(self, "listening", False):
                # Pocas hry sa na Microsoft nechodi: hlaska zaznie hlasom
                # z Windows a dopripravi sa po `stop_listening`.
                self._pregen_po_hre = True
                self.log_threadsafe(tr("log.edge_not_cached_later"))
            else:
                self.log_threadsafe(tr("log.edge_not_cached"))
                self.ui_call(self.pregenerate)

        voice_id = slot.voice_sapi or self.saved_voice_id
        if concurrent:
            threading.Thread(target=speak_sapi_isolated,
                             args=(text, voice_id, self.rate_value, self.tts_volume),
                             daemon=True).start()
        else:
            self.audio.speak(text, voice_id)

    def _slot_zaznie(self, slot, bez_slov=False):
        """Zaznie z `_emit(slot, bez_slov)` vobec nieco? Rovnake vetvy ako
        `_emit`, len bez prehravania - pre `audible` v zazname hlasky (graf
        ucinnosti rata len hlasky, ktore naozaj zazneli)."""
        mode = slot.mode
        sfx_path = self.resolve_sfx_path(slot) if mode in (MODE_SFX, MODE_COMBO) else None
        zvuk = bool(sfx_path and os.path.exists(sfx_path))
        if bez_slov or mode == MODE_SFX:
            # V rezime SFX `_emit` text nema (`text` je len pre TTS/COMBO),
            # takze bez suboru nezaznie nic.
            return zvuk
        if mode == MODE_COMBO:
            return zvuk or self._slot_has_voice(slot)
        return self._slot_has_voice(slot)

    def _emit(self, slot, bez_slov=False):
        """Prehra slot. `bez_slov=True` (styl hlasky "zvuk", `rebrik.py`)
        zahra LEN zvuk slotu - ziadne TTS, ziadnu vlastnu nahravku, ani ako
        zalohu za chybajuci zvuk. Slot bez zvuku potom mlci."""
        mode = slot.mode
        sfx_path = self.resolve_sfx_path(slot) if mode in (MODE_SFX, MODE_COMBO) else None
        text = slot.text_value if mode in (MODE_TTS, MODE_COMBO) else ""

        if bez_slov:
            if sfx_path and os.path.exists(sfx_path):
                self.audio.play(sfx_path)
            elif sfx_path:
                self.log_threadsafe(tr("log.slot_sfx_missing_plain", n=slot.index + 1))
            return

        if mode == MODE_COMBO:
            played_sfx = False
            if sfx_path and os.path.exists(sfx_path):
                self._play_concurrent(sfx_path, self.sfx_volume)
                played_sfx = True
            elif sfx_path:
                self.log_threadsafe(tr("log.slot_sfx_missing", n=slot.index + 1,
                                       name=os.path.basename(sfx_path)))
            if self._slot_has_voice(slot):
                # Kombinacia hraje vzdy subezne (naraz) - bez ohladu na globalny
                # prepinac "cez seba", inak by SFX+TTS zneli za sebou. `_speak_text`
                # sam rozhodne, ci povie text (TTS) alebo prehra vlastnu nahravku.
                self._speak_text(text, slot, concurrent=played_sfx)
            return

        if mode == MODE_SFX:
            if sfx_path and os.path.exists(sfx_path):
                self.audio.play(sfx_path)
                return
            if sfx_path:
                key = "log.slot_sfx_missing_fallback" if text.strip() \
                    else "log.slot_sfx_missing_plain"
                self.log_threadsafe(tr(key, n=slot.index + 1))
            if text.strip():
                self._speak_text(text, slot)
            return

        if self._slot_has_voice(slot):
            self._speak_text(text, slot)

    # ---------- start / stop ----------

    def toggle_listening(self):
        if self.listening:
            self.stop_listening()
        else:
            self.start_listening()

    def start_listening(self):
        """Zapne pocuvanie. Enso od tejto chvile svieti `success`.

        FAZA 3 zmenila, co "pocuvanie" znamena. Doteraz to bolo "bezia
        klavesove hooky"; teraz je to "appka sleduje telo a smie sa ozvat".
        Ziadny hook sa uz neinstaluje - aktivita sa zistuje cez
        `GetLastInputInfo`, co vracia jedine pocet milisekund od posledneho
        vstupu.

        Enso je jediny nositel stavu v celom rozhrani, takze toto NIE JE len
        kozmetika: `_cue_can_fire` sa pyta na `self.listening`, cize kym
        enso svieti `danger`, appka naozaj mlci.
        """
        if self.listening:
            return
        # Drag-test nesmie prezit spustenie pocuvania.
        #
        # Testovaci vizual ma vypnuty klik-through, cize nad hrou pohlcuje
        # kliky. Hrac, ktory si doladil polohu a potom zapol pocuvanie, ide
        # vzapati hrat - a mal by uprostred obrazovky nekliknutelnu plochu.
        try:
            if self.overlay_manager.stop_all_tests():
                self.log(tr("log.overlay_test_ukonceny"))
                self._refresh_all_test_buttons()
        except Exception:
            app_log.exception("ukoncenie drag-testu zlyhalo")
        if self.gamepad.available:
            # Uz nie ako spustac - len ako druhy zdroj informacie o tom, ci
            # je hrac aktivny, a ako jedina cesta, ako rozoznat ovladac od
            # klavesnice (`GetLastInputInfo` vidi oboje, ale nepovie co).
            self.gamepad.start()
        self.activity.set_gamepad_watched(self.gamepad.available)
        # NOVA MERACIA RELACIA PRI KAZDOM ZAPNUTI POCUVANIA.
        #
        # Relacia bola naviazana na SENZOR, nie na pocuvanie: otvarala sa
        # jedine v `start_heart_rate_monitor`. Odkedy ju `stop_listening`
        # korektne zatvara, vzniklo z toho tiche zlyhanie - po prvom cykle
        # stop/start nebola otvorena ZIADNA relacia a nemeralo sa nic.
        # (V CSV z 18. 9. to vidno ako styri kratke relacie namiesto jednej:
        # 17:03, 18:01, 18:04, 18:07 - vznikli len restartom appky, lebo
        # inak sa nova relacia otvorit nedala.)
        #
        # Siete sa pritom NEDOTYKAME: ked prijem uz bezi, restart socketu by
        # hodinky na chvilu odpojil - a prave kratke vypadky rozbijaju
        # pocitanie suvislosti (viz body 2 a 5 zadania).
        if self.hr_monitoring_enabled and not getattr(self, "_hr_session_open", False):
            if self.heart_rate_monitor.running:
                self._open_hr_session(prepoj=False, meria=True)
            else:
                # `self.listening` este nie je True, tak sa to povie priamo.
                self._open_hr_session(meria=True)
                self._hr_generation = self.heart_rate_monitor.start(
                    self.hr_ip, self.hr_port)
        # `stop_listening` spustac pozastavi; bez tohto by ho zdvihla az
        # nejaka ina cesta a do vtedy by appka mlcala. Kym plati "teraz nie",
        # nezdvihne nic (`_resume_cue_trigger`) - stisenie plati dalej.
        self._resume_cue_trigger()
        self.listening = True
        self.session_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        self.update_session_label()
        self._apply_listening_visuals()
        self.log(tr("log.listening_on"))
        self.update_tray_icon()

    def stop_listening(self):
        self.gamepad.stop()
        self.activity.set_gamepad_watched(False)
        self.listening = False
        self._suspend_cue_trigger(trigger.A_SNOOZE)
        # RELACIA KONCI TU, nie az pri zatvoreni appky.
        # `_close_hr_session` visel len na vypnuti SENZORA a na `_quit`.
        # Kto dal stop a nechal appku otvorenu, mal reláciu stale otvorenu -
        # neulozila sa, nespytalo sa na kontext, a keby proces skoncil inak
        # nez cez `_quit`, cely vecer merania sa stratil. Stalo sa to.
        #
        # Ked sa nepocuva, nemoze padnut hlaska, takze uz sa nic nemeria -
        # relacia nema preco zostat otvorena. `_hr_session_open` strazi, aby
        # to druhy volajuci (vypnutie senzora, `_quit`) nezopakoval.
        self._close_hr_session()
        self._apply_listening_visuals()
        self.log(tr("log.listening_off"))
        self.update_tray_icon()
        self._dopriprav_hlasky_po_hre()

    def _dopriprav_hlasky_po_hre(self):
        """Hlasky, ktore pocas hry chybali v cache (`_speak_text`), sa
        pripravia az teraz - pocas pocuvania appka na Microsoft nechodi."""
        if getattr(self, "_pregen_po_hre", False):
            self._pregen_po_hre = False
            self.schedule_pregenerate(200)

    def _apply_listening_visuals(self):
        """Prenesie stav do dychajuceho pasu a do rychleho docku.

        Ziadne blikanie uz netreba - `KamaeBar` si rytmus riadi sam a v
        zastavenom stave stoji, takze sa tu nespusta ziadny `after()`
        retazec (povodny `_pulse_status` bezal 2x za sekundu cely cas, co
        appka bezala).
        """
        if self.listening and getattr(self, "_listen_started", None) is None:
            self._listen_started = time.time()
        elif not self.listening:
            self._listen_started = None
        if getattr(self, "kamae", None) is not None:
            self.kamae.set_texts(tr("kamae.bar_title"), tr("kamae.bar_sub"))
            self.kamae.set_live(self.listening)
        self._refresh_dnes_state_text()
        if getattr(self, "sidebar", None) is not None:
            try:
                # Kontrolka v paneli je jedina informacia o stave na piatich
                # zo siestich stranok - znacka aj pas zijú na stranke Dnes.
                bodka = getattr(self.sidebar, "state_dot", None)
                if bodka is not None:
                    bodka.set_live(self.listening)
                self.sidebar.enso.set_live(self.listening)
                # Prestavba okna (zmena jazyka, zachrana pri teme) postavi
                # ENSO NANOVO a to zacina s `_armed = False`, kym
                # `self._cue_armed` si stav drzi dalej. Pas by potom hlasil
                # "Natiahnute" nad znackou bez prstenca az do najblizsej
                # udalosti automatu. `set_live` to nezachrani - ten priznak
                # zhadzuje len pri prechode True -> False.
                self.sidebar.enso.set_armed(self._cue_armed and self.listening)
            except Exception:
                pass
        # HUD trigger row ("Ukazat panel v hre") si zoznam funkcii
        # neprekresluje sam - staci raz pri kazdej zmene stavu pocuvania,
        # aby ikonky odrazali aktualne enabled/disabled sloty.
        self._refresh_hud_trigger_row()
        self._refresh_nav_badges()


    def make_tray_image(self):
        """Ikona v systemovej liste - rovnaka znacka ako ikona appky.

        Prstenec nesie stav (bezi / zastavene), znak 残 nesie identitu.
        Povodne to bola len zelena alebo cervena bodka, ktora sa medzi
        ostatnymi ikonami v liste nedala rozoznat.

        `make_icon` je bezny modul bez kodu na urovni modulu, takze sa da
        importovat aj za behu; ak by kreslenie z akehokolvek dovodu zlyhalo
        (chybajuce pismo so znakmi CJK), spadne to na povodnu bodku - appka
        bez ikony v liste by sa nedala vyvolat spat z minimalizacie.
        """
        size = 64
        pal = self.pal
        ring = pal["success"] if self.listening else pal["danger"]
        try:
            import make_icon
            rgb = tuple(int(ring.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
            return make_icon.tray_mark(size, rgb)
        except Exception:
            app_log.exception("make_tray_image: kreslenie znacky zlyhalo")
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            color = (60, 160, 60, 255) if self.listening else (160, 60, 60, 255)
            ImageDraw.Draw(img).ellipse((4, 4, size - 4, size - 4), fill=color)
            return img

    def setup_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem(lambda _item: tr("tray.show"), self.show_window, default=True),
            pystray.MenuItem(lambda _item: tr("tray.toggle"), lambda *_: self.ui_call(
                self.toggle_listening)),
            # "TERAZ NIE" AJ BEZ SKRATKY (0.2.1). Ked Ctrl+Alt+Z drzi ina
            # appka, `RegisterHotKey` zlyha - a hlasky sa potom dali stisit
            # jedine zastavenim pocuvania, co zastavi aj meranie. Polozka
            # robi presne to, co skratka: prepinac na `SNOOZE_HOTKEY_MINUTES`
            # minut, fajka hovori, ci prave plati. Klik prichadza na vlakne
            # listy, takze ide cez `ui_call` rovnako ako stlacenie skratky.
            pystray.MenuItem(
                lambda _item: tr("tray.snooze", minutes=SNOOZE_HOTKEY_MINUTES),
                lambda *_: self.ui_call(self._toggle_snooze_from_hotkey),
                checked=lambda _item: getattr(self, "_snooze_job", None) is not None),
            pystray.MenuItem(lambda _item: tr("tray.quit"), self.quit_app),
        )
        self.tray_icon = pystray.Icon(APP_NAME, self.make_tray_image(), APP_NAME, menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def update_tray_icon(self):
        if self.tray_icon:
            try:
                self.tray_icon.icon = self.make_tray_image()
            except Exception:
                pass
        self._apply_window_icon()

    def _apply_window_icon(self):
        """Ikona okna (taskbar / alt-tab) = to iste zlate enso vo farbe stavu
        (zelena pocuvam / cervena nie) ako znacka v listi. Najlepsia snaha:
        pri bezramovom okne sa nemusi vsade zobrazit, preto je cela v
        try/except a bez nej appka bezi dalej. Referenciu na obrazok si drzime,
        inak ju Tk zahodi a ikona zbelie.

        CustomTkinter si 200 ms po vzniku okna nastavi VLASTNU ikonu priamo
        na okno (`CTk._windows_set_titlebar_icon`), ak appka dovtedy nevolala
        `iconbitmap()`. O `iconphoto()` nevie, takze v liste a v Alt-Tab
        ostavalo logo CustomTkinter namiesto ensa. Dve cesty:
          * bezny start - casovac CTk pribehne az v `mainloop()`, teda PO
            tejto metode. Vlajku, ktorou si CTk pamata "appka ma vlastnu
            ikonu", preto nastavime sami (len ked sa enso naozaj nastavilo;
            inak radsej ikona CTk nez ziadna);
          * prvy start - casovac pribehne uz pocas sprievodcu, PRED touto
            metodou. `iconphoto(True, ...)` meni len predvolenu ikonu a tu
            vlastna ikona okna prebije - preto enso dostane aj hlavne okno
            priamo (`iconphoto(False, ...)`).
        Ze CTk vlajku stale cita, strazi test v tests/test_ui_fixes.py."""
        try:
            photo = _ImageTk.PhotoImage(self.make_tray_image())
            self.root.iconphoto(True, photo)     # predvolena pre okna appky
            self.root.iconphoto(False, photo)    # vlastna ikona hlavneho okna
            self._window_icon_ref = photo
        except Exception:
            return
        if hasattr(self.root, "_iconbitmap_method_called"):
            self.root._iconbitmap_method_called = True

    def minimize_to_tray(self):
        if TRAY_AVAILABLE:
            self.root.withdraw()
        else:
            self.root.iconify()

    def show_window(self, *_):
        self.ui_call(self._show_window)

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def on_close(self):
        if not TRAY_AVAILABLE:
            self.quit_app()
            return
        # PRVY KRIZIK: povedat, ze appka nekonci. Doteraz × okno potichu
        # schovalo do listy - port pre telefon ostal otvoreny a tep sa dalej
        # meral a ukladal, hoci si hrac myslel, ze appku zavrel. Raz to
        # povie a da na vyber (Nie = ukoncit hned); dalej × len schovava.
        if not getattr(self, "tray_close_explained", True):
            self.tray_close_explained = True
            self.save_settings()
            if not messagebox.askyesno(
                    APP_NAME, tr("tray.close_first", port=self.hr_port)):
                self.quit_app()
                return
        self.minimize_to_tray()

    def quit_app(self, *_):
        self.ui_call(self._quit)

    def _quit(self):
        # Kym je toto True, `_ask_session_context` na dotaznik pocka.
        self._zatvara_sa = True
        self.stop_listening()
        for attr in ("_pregen_job", "_snooze_job", "_activity_job",
                     "_hr_retry_job"):
            job = getattr(self, attr, None)
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except Exception:
                    pass
                setattr(self, attr, None)
        self._close_hr_session()
        self.hud.stop()
        self.overlay_manager.stop_all()
        self.gamepad.stop()
        # Hotkey drzi vlastne vlakno s `GetMessageW` slucku - bez tohto by
        # viselo az do konca procesu a kombinacia by ostala zabrata.
        # Zamerne az TU, nie v `stop_listening` ani `on_close`: "teraz nie"
        # ma fungovat aj ked appka nepocuva aj ked je minimalizovana v liste.
        self.stop_snooze_hotkey()
        self.heart_rate_monitor.stop()
        if self.game_watcher is not None:
            self.game_watcher.stop()
        self.worker.stop()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.root.destroy()

    # Registracia globalnej skratky "teraz nie" (zo sekcie rychly dock).
    # Zvysok "teraz nie" (prepinac, odlozenie hlasok, bodka stavu) je v
    # app_controls.ControlsMixin. Tieto dve metody ostali v app.py pri
    # liste: `start_snooze_hotkey` cita TRAY_AVAILABLE, ktore sa pocita
    # tu spolu s importom pystray/PIL (a testy ho menia na module app).
    def start_snooze_hotkey(self):
        """Zaregistruje globalny klaves pre "teraz nie" (zadanie §1.9).

        NIE JE to navrat hooku, ktory faza 3 zrusila - viz hlavicka
        `hotkey.py`. Appka Windowsu ohlasi JEDINU kombinaciu a o ziadnom
        inom klavese sa nedozvie.

        Ked je kombinacia obsadena inou appkou, registracia zlyha a appka
        bezi dalej bez nej - `hotkey.GlobalHotkey` to zaloguje. Tlacidlo v
        doku uz nie je; od 0.2.1 je "teraz nie" aj v ponuke ikony v liste
        (`setup_tray`) a riadok v denniku (`log.hotkey_failed_tray`) hraca
        posle tam. Bez listy (chyba pystray/PIL) zostava len zastavit
        pocuvanie, co zastavi aj meranie - to hovori `log.hotkey_failed`.
        """
        self.stop_snooze_hotkey()
        if not self.snooze_hotkey:
            return False
        try:
            self._hotkey = hotkey.GlobalHotkey(
                self.snooze_hotkey, self._on_snooze_hotkey,
                # NIE `log_threadsafe`: hotkey sa registruje na vlastnom
                # vlakne uz pocas `__init__`, teda PRED `root.mainloop()`.
                # `ui_call` vtedy este planovat nevie ("main thread is not
                # in main loop") a sprava by sa ticho stratila - presne to
                # sa aj dialo. `app_log` je vlaknovo bezpecny a do suboru
                # zapise vzdy. Vysledok registracie zaloguje do okna az
                # `start_snooze_hotkey` nizsie, z hlavneho vlakna.
                log=app_log.info)
            ok = self._hotkey.start()
        except Exception:
            app_log.exception("hotkey: registracia zlyhala")
            self._hotkey = None
            return False
        if ok:
            self.log(tr("log.hotkey_on",
                        combo=hotkey.format_combo(self.snooze_hotkey)))
        elif TRAY_AVAILABLE:
            # Zlyhanie sa hlasi RAZ - `start_snooze_hotkey` sa vola raz pri
            # starte - a veta ukaze na polozku v liste, nie na zastavenie.
            self.log(tr("log.hotkey_failed_tray",
                        combo=hotkey.format_combo(self.snooze_hotkey)))
        else:
            self.log(tr("log.hotkey_failed",
                        combo=hotkey.format_combo(self.snooze_hotkey)))
        return ok

    def stop_snooze_hotkey(self):
        if self._hotkey is None:
            return
        try:
            self._hotkey.stop()
        except Exception:
            app_log.exception("hotkey: zastavenie zlyhalo")
        self._hotkey = None
