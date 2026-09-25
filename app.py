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
import threading
import time
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

# DOLEZITE poradie: `gamepad` MUSI byt naimportovany skor nez `audio_engine`
# (gamepad pri importe nastavi SDL_AUDIODRIVER=dummy pre bezokenny joystick;
# audio_engine tento env var pri svojom importe odstrani tesne pred
# pygame.mixer.init() - ak by sa poradie obratilo, mixer by ostal nemy).
import gamepad
import activity
import audio_engine
import sfx_assets
import hr_insights
import hr_stats
import rebrik
import trigger
import guide_content
from heart_rate import HeartRateMonitor
from hud import StatsHud
import theme as theme_mod
import ui_kit
from audio_engine import AudioDispatcher, EdgeTTSCache, SpeechWorker
from game_profiles import PSUTIL_AVAILABLE
from guide_panel import GuidePanel, build_guide_into
from guided_tour import GuidedTour
from i18n import LANG_EN, tr
from overlay import SomaticOverlayManager
from paths import APP_NAME, AUDIO_DIR, DATA_DIR, TTS_CACHE_DIR

# Licencia tak, ako ju vidno v titulnej liste. NIE je to prekladany retazec:
# "GPLv3" je nazov licencie, rovnako ako "Zanshin" je nazov appky - prelozit
# ho by znamenalo tvrdit, ze ide o inu licenciu.
LICENCIA = "GPLv3"
from settings_model import (DEFAULT_AUDIO,
                            DASHBOARD_MAX_CARDS,
                            DEFAULT_COOLDOWN,
                            ENGINE_EDGE,
                            ENGINE_SAPI,
                            engine_labels)
from ui_dialogs import (watch_app_qr,
                        DevLayerDialog,
                        OnboardingWizard)
import ui_shell
from ui_shell import (PageContainer, Sidebar,
                      TitleBar, enable_frameless)
from collections import deque

import hotkey
import hud_paint

# Mixiny DandurfApp (app_*.py) sa importuju az tu, za vsetkymi modulmi
# vyssie: co potrebuju, je uz nacitane, takze nemenia poradie importov
# (gamepad pred audio_engine). Vynimky su `background` a `data_io` - app.py
# ich uz sam nepouziva a nacita ich az mixin (pri importe `background` len
# nacita PIL a `data_io` len definuje konstanty). Mena spolocne pre app.py
# aj mixiny (app_log, nazvy jazykov, skratka "Teraz nie", ImageTk) su v
# app_spolocne.py - mixin nesmie importovat app (kruhovy import).
from app_spolocne import (LANG_NATIVE_LABELS, SNOOZE_HOTKEY_MINUTES,
                          _ImageTk, app_log)
# Tieto dve mena app.py sam nepouziva: DEFAULT_SNOOZE_HOTKEY cita
# `load_settings` v app_prefs, LABEL_TO_LANG prepinace jazyka v app_prefs
# a app_hud. Importuju sa, aby `app.DEFAULT_SNOOZE_HOTKEY` a
# `app.LABEL_TO_LANG` (do 0.2.1 konstanty app.py) ostali platne.
from app_spolocne import DEFAULT_SNOOZE_HOTKEY, LABEL_TO_LANG  # noqa: F401
from app_data import DataMixin
from app_prefs import PrefsMixin
from app_controls import ControlsMixin
from app_audio import AudioMixin
from app_hud import HudMixin
from app_today import TodayMixin
from app_profiles import ProfilesMixin
from app_session import SessionMixin
from app_cues import CuesMixin
from app_history import HistoryMixin

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


class DandurfApp(DataMixin, PrefsMixin, ControlsMixin, AudioMixin, HudMixin,
                 TodayMixin, ProfilesMixin, SessionMixin, CuesMixin,
                 HistoryMixin):
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

    # Kontrolka tepu v bocnom paneli (`_watch_pulse_state` v app_hud.py).
    # hysterezia pasma: nove pasmo musi vydrzat, inak by kontrolka na
    # hranici (napr. stres kolisajuci okolo 25) blikala medzi dvoma
    # farbami pri kazdom tepe
    WATCH_ZONE_HOLD_S = 1.5

    # Hero prazdneho stavu na Dnes (zive dojo v app_today.py).
    HERO_PERIOD_S = 10.0        # 5 s nádych + 5 s výdych — tempo pásu aj kruhu

    # Presun karty na Dnes potiahnutim (`_dashboard_drag` v app_today.py).
    DASHBOARD_DRAG_PX = 8

    # Senzor tepu bez klienta (`_schedule_no_client_check` v app_session.py).
    # Ak sa do tolkoto ms po zapnuti nepripoji ani jeden klient, stav sa
    # zmeni z "connecting" na "no_client" - iny problem, iny text (B2).
    HR_NO_CLIENT_AFTER_MS = 20000

    # Stred Dnes po zmene rozmeru (`_naplanuj_backdrop` v app_today.py).
    # Kolko sa caka, kym sa rozmer ustali. Pri presune okna medzi monitormi
    # vystreli Windows `<Configure>` viackrat rychlo za sebou a KAZDY z nich
    # ma iny rozmer, takze straz na `_backdrop_size` ich nezachyti. Kedze
    # `background.load()` skaluje fotku cez LANCZOS priamo v Tk vlakne,
    # niekolko prepoctov tesne po sebe okno viditelne zasekne.
    BACKDROP_DEBOUNCE_MS = 150

    # Stranka Historia: tabulka, trend a detail relacie (app_history.py).
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

    # ---------- stranky Nastaveni a V hre ----------

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
