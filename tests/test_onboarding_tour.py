"""Testy prepracovaneho onboardingu a guided tour - staticke, bez Tk."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _zdroj_appky import zdroj_appky, zdroj_metody

def _read(name):
    here=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here,name),encoding="utf-8-sig") as fh: return fh.read()

def test_onboarding_newline_bug_is_fixed():
    """Popisy svetov (a tem pod nimi) sa musia zalamovat cez skutocny \\n,
    nie viacnasobne escapovany \\\\n (to bola vizualna chyba - text
    '\\nPre nocne...'). Stare `onboarding.zen/modern.*` nikto necital a
    zmazali sa; ich miesto v onboardingu maju `ob.world.*.desc`."""
    import i18n
    for k in ("ob.world.play.desc","ob.world.work.desc"):
        v=i18n.STRINGS[k]["sk"]
        assert "\n" in v, f"{k} ma mat zalomenie"
        assert "\\n" not in v.replace("\n",""), f"{k} ma pokazeny escape"

def test_onboarding_is_five_steps():
    """Od 0.2 piaty krok: ako sa ma appka ozvat (styl hlasky)."""
    ud=_read("ui_dialogs.py")
    w=ud[ud.index("class OnboardingWizard"):]
    assert "STEP_COUNT = 5" in w
    for step in ("_step1","_step2","_step3","_step4","_step5"):
        assert f"def {step}(" in w, f"chyba {step}"
    # kicker kazdeho kroku hovori "z 5"; stare "zo 4" neprezilo v ziadnom
    # jazyku (jeho _tr7 riadky su zmazane, novy preklad je z fazy jazykov)
    import i18n
    for n in range(1, 6):
        kicker = i18n.STRINGS[f"ob.step{n}.kicker"]
        assert f"{n} z 5" in kicker["sk"] and f"{n} of 5" in kicker["en"]
        assert all("5" in v for v in kicker.values()), (n, kicker)

def test_onboarding_keeps_app_interface():
    """app.py cita .confirmed/.choice/.volume_value/.diagnostics - musia zostat."""
    ud=_read("ui_dialogs.py")
    w=ud[ud.index("class OnboardingWizard"):]
    for attr in ("self.confirmed","self.choice","self.volume_value","self.diagnostics","self.wants_pairing",
                 "self.cue_style"):
        assert attr in w, f"chyba {attr}"

def test_onboarding_has_watch_step():
    """Krok o hodinkach s parovanim musi existovat (kluc pointa)."""
    import i18n
    assert "ob.step3.pair_now" in i18n.STRINGS
    assert "ob.step3.later" in i18n.STRINGS
    ud=_read("ui_dialogs.py")
    assert "wants_pairing = True" in ud, "pair_now musi nastavit wants_pairing"

def test_tour_steps_have_translations():
    """Kazdy krok prehliadky ma nadpis aj text - kluce sa skladaju za behu
    (tr(f"tour.{key}.title")), takze test_i18n_keys ich nevidi."""
    import i18n
    import guided_tour
    for key, *_ in guided_tour._STEPS:
        for cast in ("title", "body"):
            assert f"tour.{key}.{cast}" in i18n.STRINGS, f"chyba tour.{key}.{cast}"
    for k in ("tour.step_of", "tour.done.no_watch", "tour.sensor.pair"):
        assert k in i18n.STRINGS, f"chyba {k}"

def test_tour_marks_seen_and_is_replayable():
    """Tour po dobehnuti nastavi tour_seen; da sa spustit z Nastaveni."""
    gt=_read("guided_tour.py")
    assert "mark_tour_seen" in gt
    app=zdroj_appky()
    assert "def start_tour" in app
    assert "def mark_tour_seen" in app
    assert '"tour_seen"' in app, "tour_seen sa musi ukladat do settings"
    assert "settings.tour_btn" in app, "tlacidlo na replay v Nastaveniach"

def test_onboarding_imports_everything_it_uses():
    """Onboarding padal na NameError ('hud_paint' is not defined) - pouzival
    modul, ktory ui_dialogs neimportoval. Kompilacia to neodchyti."""
    import ui_dialogs
    for name in ("hud_paint", "ImageTk", "threading", "sfx_assets", "theme_mod"):
        assert hasattr(ui_dialogs, name), f"ui_dialogs nema import {name}"


def test_first_run_window_reappears_after_wizard():
    """Bezramove okno po withdraw() + jednom deiconify() ostava na Windows
    withdrawn -> hrac po onboardingu nevidel appku. Musi byt update() +
    druhy deiconify()."""
    app=zdroj_metody("__init__")
    block=app[app.index("wizard = OnboardingWizard(self.root"):]
    block=block[:block.index("self.monitor_target = settings")]
    assert block.count("self.root.deiconify()") >= 2 and "self.root.update()" in block


def test_tour_cancels_pending_place_on_next_and_finish():
    """Odlozeny _place() (after 60 ms) sa musi zrusit pri dalsom kroku aj pri
    finish(), inak po rychlom Dalej/Preskocit ostane visiet bublina."""
    gt=_read("guided_tour.py")
    assert "after_cancel" in gt and "_place_job" in gt
    place=gt[gt.index("    def _place(self"):]
    place=place[:place.index("\n    def ", 5)]
    assert "_finished" in place and "_gen" in place


def test_tour_bubble_clamped_to_app_monitor():
    """Bublina sa drzi na monitore appky (display.monitors), nie len na
    primarnom (winfo_screenwidth)."""
    gt=_read("guided_tour.py")
    pos=gt[gt.index("    def _bubble_position(self"):]
    assert "display.monitors" in pos


def test_onboarding_uses_dialog_chrome_and_closes_through_question():
    """Onboarding ma rovnaku vlastnu listu ako ostatne dialogy (DialogChrome).
    Od 0.2.2 sa da zavriet - krizik, Esc aj krizik OS idu cez jednu otazku
    (`_on_close_request`), nie "do prazdna" a nie nikam (predtym nic)."""
    ud=_read("ui_dialogs.py")
    w=ud[ud.index("class OnboardingWizard"):]
    init=w[w.index("def __init__"):w.index("\n    def ", w.index("def __init__")+5)]
    assert "ui_kit.DialogChrome(" in init and "closable=False" not in init
    assert "on_close=self._on_close_request" in init
    assert "chrome.body" in init, "obsah musi ist do chrome.body, nie do top"
    assert 'protocol("WM_DELETE_WINDOW", self._on_close_request)' in init
    assert "lambda: None" not in init, "zavretie sa nesmie prehltnut"
    kit=_read("ui_kit.py")
    assert "closable=True" in kit and "if self.closable:" in kit


def test_tour_runs_after_pairing_not_instead_of_it():
    """Prvy start s "Sparovat hodinky teraz": najprv parovanie, prehliadka
    az po jeho zavreti (on_close) - predtym ju elif vynechal uplne. Bez
    parovania ide prehliadka hned ako doteraz."""
    init=zdroj_metody("__init__")
    blok=init[init.index('prehliadka = settings["first_run"] and not self.tour_seen'):]
    assert "self._prehliadka_po_parovani if prehliadka else None" in blok
    assert "self.open_watch_pairing(on_close=po_parovani)" in blok
    assert "elif prehliadka:" in blok and "self.start_tour" in blok
    po=zdroj_metody("_prehliadka_po_parovani")
    assert "self.tour_seen" in po and "self.start_tour" in po
    assert "on_close" in zdroj_metody("open_watch_pairing")
