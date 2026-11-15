"""Logic of bulk selection and removal of triggers - without Tk.

The slot card (SlotCard) holds many Tk widgets that cannot be created
here. So we test the DECISION, not the widgets: which indexes are to be
removed, when the removal is refused, and whether what remains is right.
The same discipline as with hr_stats/display - keep pure logic separate
from the UI and test it directly.

These tests are also a regression safeguard against a bug the redesign
had: rebind crashed because it called .configure(text=) on a Keycap
widget that has no such method. `set_key` therefore now calls
set_text() - the test guards it at the level of the API contract (Keycap
MUST have set_text and MUST NOT rely on configure).
"""

import os
import sys


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _zdroj_appky import subory_appky, zdroj_appky, zdroj_metody  # noqa: E402


# --------------------------------------------------------------------------
# Pure selection logic - kept apart from SlotCard on purpose, to be testable
# --------------------------------------------------------------------------

def plan_removal(selected_flags):
    """[bool] per slot -> (indexes_to_remove, allowed?).

    This is exactly the rule from DandurfApp.remove_selected_slots pulled
    out into a pure function: any subset can be removed EXCEPT one that
    would delete absolutely everything - at least one trigger must remain,
    otherwise the profile has nothing to trigger.
    """
    selected = [i for i, on in enumerate(selected_flags) if on]
    if not selected:
        return [], False
    if len(selected) >= len(selected_flags):
        return selected, False       # forbidden: it must not be left empty
    return selected, True


def apply_removal(items, selected_flags):
    """What remains after removing the marked ones (order kept)."""
    drop = set(i for i, on in enumerate(selected_flags) if on)
    return [x for i, x in enumerate(items) if i not in drop]


def test_nothing_selected_is_noop():
    idx, ok = plan_removal([False, False, False])
    assert idx == [] and ok is False


def test_subset_is_allowed():
    idx, ok = plan_removal([True, False, True, False])
    assert idx == [0, 2] and ok is True


def test_removing_all_is_blocked():
    idx, ok = plan_removal([True, True, True])
    assert ok is False, "musi ostat aspon jeden spustac"


def test_removing_all_but_one_is_allowed():
    idx, ok = plan_removal([True, True, False, True])
    assert ok is True and idx == [0, 1, 3]


def test_apply_keeps_order_and_unselected():
    items = ["C", "R", "PravaMys", "F"]
    keep = apply_removal(items, [True, False, True, False])
    assert keep == ["R", "F"]


def test_apply_removes_single():
    items = ["a", "b", "c"]
    assert apply_removal(items, [False, True, False]) == ["a", "c"]


# --------------------------------------------------------------------------
# Keycap API contract - rebind regression
# --------------------------------------------------------------------------

# customtkinter/numpy are not here, so the modules are not imported - the
# contract is checked by READING the source (regex/AST), not by running.
# That is intentional: the test should guard the bug even in an
# environment without GUI libraries (e.g. CI), exactly where it could not
# be caught by hand.

def _read(name):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, name), encoding="utf-8") as fh:
        return fh.read()


def test_keycap_defines_set_text():
    """ui_kit.Keycap MUST define set_text() - rebind and set_key() rely on
    it. Without it rebind crashes the moment the label is rewritten."""
    import re
    src = _read("ui_kit.py")
    body = src[src.index("class Keycap"):]
    body = body[:body.index("\nclass ")] if "\nclass " in body[10:] else body
    assert re.search(r"def set_text\(", body), \
        "Keycap MUSI mat metodu set_text()"


def test_klavesovy_hook_sa_nevratil():
    """Safeguard against a silent return of the global hook.

    It was the only piece of the app that from the outside looked like a
    keylogger, and the whole SAFETY.md rests on its removal. If someone
    (including future me) brought it back - e.g. so that "reassigning a
    key works again" - let it fail here and not only at the moment
    someone asks why the app is listening to the keyboard.

    Tested statically, so that it runs without Tk.
    """
    import re
    # It looks for the IMPORT, not the word - pynput is mentioned in comments
    # on purpose (they explain why it is no longer there).
    dovoz = re.compile(r"^\s*(?:from\s+pynput|import\s+pynput)", re.M)
    # the app = app.py and the DandurfApp mixins in app_*.py
    for subor in (*subory_appky(), "ui_dialogs.py", "ui_kit.py"):
        src = _read(subor)
        assert not dovoz.search(src), f"{subor} znova importuje pynput"
        assert "keyboard.Listener(" not in src, f"{subor} znova instaluje hook"
        assert "mouse.Listener(" not in src, f"{subor} znova instaluje hook"

    app_src = zdroj_appky()
    for meno in ("def begin_rebind", "def on_press", "def on_click",
                 "def handle_trigger"):
        assert meno not in app_src, f"{meno} sa vratilo do app.py"


def test_remove_selected_guards_against_emptying():
    """DandurfApp.remove_selected_slots must refuse deleting all slots - a
    static check that the safeguard is there."""
    block = zdroj_metody("remove_selected_slots")
    assert "slot_only_one" in block, \
        "remove_selected_slots musi mat poistku proti zmazaniu vsetkeho"
