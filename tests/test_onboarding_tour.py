"""Testy prepracovaneho onboardingu a guided tour - staticke, bez Tk."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    import i18n
    for k in ("tour.welcome.title","tour.kamae.body","tour.done.body","tour.step_of"):
        assert k in i18n.STRINGS, f"chyba {k}"

def test_tour_marks_seen_and_is_replayable():
    """Tour po dobehnuti nastavi tour_seen; da sa spustit z Nastaveni."""
    gt=_read("guided_tour.py")
    assert "mark_tour_seen" in gt
    app=_read("app.py")
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
    app=_read("app.py")
    block=app[app.index("wizard = OnboardingWizard(self.root)"):]
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


def test_onboarding_uses_dialog_chrome_without_close():
    """Onboarding ma rovnaku vlastnu listu ako ostatne dialogy (DialogChrome)
    a NESMIE mat krizik/Escape - nesmie sa dat zavriet do prazdna."""
    ud=_read("ui_dialogs.py")
    w=ud[ud.index("class OnboardingWizard"):]
    init=w[w.index("def __init__"):w.index("\n    def ", w.index("def __init__")+5)]
    assert "ui_kit.DialogChrome(" in init and "closable=False" in init
    assert "chrome.body" in init, "obsah musi ist do chrome.body, nie do top"
    assert 'protocol("WM_DELETE_WINDOW", lambda: None)' in init
    kit=_read("ui_kit.py")
    assert "closable=True" in kit and "if self.closable:" in kit


def test_tour_does_not_clash_with_pairing():
    """Tour sa nespusti, ak hrac isiel rovno parovat (aby sa neprekryvali)."""
    app=_read("app.py")
    assert "elif settings[\"first_run\"] and not self.tour_seen" in app
