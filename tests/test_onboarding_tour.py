"""Tests of the reworked onboarding and guided tour - static, no Tk."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _zdroj_appky import zdroj_appky, zdroj_metody

def _read(name):
    here=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here,name),encoding="utf-8-sig") as fh: return fh.read()

def test_onboarding_newline_bug_is_fixed():
    """World descriptions (and the themes under them) must wrap via a real \\n,
    not a multiply escaped \\\\n (that was a visual bug - the text
    '\\nPre nocne...'). The old `onboarding.zen/modern.*` were read by
    nobody and were deleted; their place in onboarding is taken by
    `ob.world.*.desc`."""
    import i18n
    for k in ("ob.world.play.desc","ob.world.work.desc"):
        v=i18n.STRINGS[k]["sk"]
        assert "\n" in v, f"{k} ma mat zalomenie"
        assert "\\n" not in v.replace("\n",""), f"{k} ma pokazeny escape"

def test_onboarding_is_five_steps():
    """Since 0.2 a fifth step: how the app should speak up (cue style)."""
    ud=_read("ui_dialogs.py")
    w=ud[ud.index("class OnboardingWizard"):]
    assert "STEP_COUNT = 5" in w
    for step in ("_step1","_step2","_step3","_step4","_step5"):
        assert f"def {step}(" in w, f"chyba {step}"
    # every step's kicker says "z 5" (of 5); the old "zo 4" survived in no
    # language (its _tr7 lines are deleted, the new translation is from the
    # language phase)
    import i18n
    for n in range(1, 6):
        kicker = i18n.STRINGS[f"ob.step{n}.kicker"]
        assert f"{n} z 5" in kicker["sk"] and f"{n} of 5" in kicker["en"]
        assert all("5" in v for v in kicker.values()), (n, kicker)

def test_onboarding_keeps_app_interface():
    """app.py reads .confirmed/.choice/.volume_value/.diagnostics - must stay."""
    ud=_read("ui_dialogs.py")
    w=ud[ud.index("class OnboardingWizard"):]
    for attr in ("self.confirmed","self.choice","self.volume_value","self.diagnostics","self.wants_pairing",
                 "self.cue_style"):
        assert attr in w, f"chyba {attr}"

def test_onboarding_has_watch_step():
    """The watch step with pairing must exist (the key point)."""
    import i18n
    assert "ob.step3.pair_now" in i18n.STRINGS
    assert "ob.step3.later" in i18n.STRINGS
    ud=_read("ui_dialogs.py")
    assert "wants_pairing = True" in ud, "pair_now musi nastavit wants_pairing"

def test_tour_steps_have_translations():
    """Every tour step has a title and a text - the keys are built at runtime
    (tr(f"tour.{key}.title")), so test_i18n_keys does not see them."""
    import i18n
    import guided_tour
    for key, *_ in guided_tour._STEPS:
        for cast in ("title", "body"):
            assert f"tour.{key}.{cast}" in i18n.STRINGS, f"chyba tour.{key}.{cast}"
    for k in ("tour.step_of", "tour.done.no_watch", "tour.sensor.pair"):
        assert k in i18n.STRINGS, f"chyba {k}"

def test_tour_marks_seen_and_is_replayable():
    """Finished tour sets tour_seen; it can be started from Settings."""
    gt=_read("guided_tour.py")
    assert "mark_tour_seen" in gt
    app=zdroj_appky()
    assert "def start_tour" in app
    assert "def mark_tour_seen" in app
    assert '"tour_seen"' in app, "tour_seen sa musi ukladat do settings"
    assert "settings.tour_btn" in app, "tlacidlo na replay v Nastaveniach"

def test_onboarding_imports_everything_it_uses():
    """Onboarding crashed on NameError ('hud_paint' is not defined) - it used
    a module that ui_dialogs did not import. Compiling does not catch it."""
    import ui_dialogs
    for name in ("hud_paint", "ImageTk", "threading", "sfx_assets", "theme_mod"):
        assert hasattr(ui_dialogs, name), f"ui_dialogs nema import {name}"


def test_first_run_window_reappears_after_wizard():
    """A frameless window after withdraw() + one deiconify() stays withdrawn
    on Windows -> the player did not see the app after onboarding. There
    must be update() + a second deiconify()."""
    app=zdroj_metody("__init__")
    block=app[app.index("wizard = OnboardingWizard(self.root"):]
    block=block[:block.index("self.monitor_target = settings")]
    assert block.count("self.root.deiconify()") >= 2 and "self.root.update()" in block


def test_tour_cancels_pending_place_on_next_and_finish():
    """The delayed _place() (after 60 ms) must be cancelled on the next step
    and on finish(), otherwise after a quick Next/Skip a bubble is left
    hanging."""
    gt=_read("guided_tour.py")
    assert "after_cancel" in gt and "_place_job" in gt
    place=gt[gt.index("    def _place(self"):]
    place=place[:place.index("\n    def ", 5)]
    assert "_finished" in place and "_gen" in place


def test_tour_bubble_clamped_to_app_monitor():
    """The bubble stays on the app's monitor (display.monitors), not just on
    the primary one (winfo_screenwidth)."""
    gt=_read("guided_tour.py")
    pos=gt[gt.index("    def _bubble_position(self"):]
    assert "display.monitors" in pos


def test_onboarding_uses_dialog_chrome_and_closes_through_question():
    """Onboarding has the same custom title bar as the other dialogs
    (DialogChrome). Since 0.3 it can be closed - the cross, Esc and the OS
    cross all go through one question (`_on_close_request`), not "into the
    void" and not nowhere (before: nothing)."""
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
    """First start with "Pair a watch now": pairing first, the tour only after
    it is closed (on_close) - before, the elif skipped it completely.
    Without pairing the tour starts right away as before."""
    init=zdroj_metody("__init__")
    blok=init[init.index('prehliadka = settings["first_run"] and not self.tour_seen'):]
    assert "self._prehliadka_po_parovani if prehliadka else None" in blok
    assert "self.open_watch_pairing(on_close=po_parovani)" in blok
    assert "elif prehliadka:" in blok and "self.start_tour" in blok
    po=zdroj_metody("_prehliadka_po_parovani")
    assert "self.tour_seen" in po and "self.start_tour" in po
    assert "on_close" in zdroj_metody("open_watch_pairing")
