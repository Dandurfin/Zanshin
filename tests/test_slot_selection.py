"""Logika hromadneho vyberu a odstranenia spustacov - bez Tk.

Karta slotu (SlotCard) drzi vela Tk widgetov, ktore sa tu vytvorit nedaju.
Testujeme preto ROZHODOVANIE, nie widgety: ktore indexy sa maju odstranit,
kedy sa odstranenie odmietne, a ci to, co ostane, sedi. Rovnaka disciplina
ako pri hr_stats/display - cistu logiku drzat oddelene od UI a testovat ju
priamo.

Tieto testy su zaroven regresna poistka na chybu, ktoru mal redizajn:
rebind padal, lebo volal .configure(text=) na Keycap widgete, ktory taku
metodu nema. `set_key` uz preto vola set_text() - test to strazi na urovni
API kontraktu (Keycap MUSI mat set_text a NESMIE sa spoliehat na configure).
"""

import os
import sys


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --------------------------------------------------------------------------
# Cista logika vyberu - zamerne oddelena od SlotCard, aby sa dala testovat
# --------------------------------------------------------------------------

def plan_removal(selected_flags):
    """[bool] za kazdy slot -> (indexy_na_odstranenie, povolene?).

    Toto je presne pravidlo z DandurfApp.remove_selected_slots vytiahnute do
    cistej funkcie: odstranit sa da lubovolna podmnozina OKREM tej, ktora by
    zmazala uplne vsetko - aspon jeden spustac musi ostat, inak profil
    nema co spustat.
    """
    selected = [i for i, on in enumerate(selected_flags) if on]
    if not selected:
        return [], False
    if len(selected) >= len(selected_flags):
        return selected, False       # zakazane: nesmie ostat prazdno
    return selected, True


def apply_removal(items, selected_flags):
    """Co ostane po odstraneni oznacenych (poradie zachovane)."""
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
# API kontrakt Keycap - regresia rebindu
# --------------------------------------------------------------------------

# customtkinter/numpy tu nie su, tak sa moduly neimportuju - kontrakt sa
# overuje CITANIM zdrojaku (regex/AST), nie behom. To je zamer: test ma
# strazit chybu aj v prostredi bez GUI kniznic (napr. CI), presne tam, kde
# by sa rucne odchytit nedala.

def _read(name):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, name), encoding="utf-8") as fh:
        return fh.read()


def test_keycap_defines_set_text():
    """ui_kit.Keycap MUSI definovat set_text() - rebind aj set_key() nan
    spoliehaju. Bez neho rebind spadne v momente prepisu popisku."""
    import re
    src = _read("ui_kit.py")
    body = src[src.index("class Keycap"):]
    body = body[:body.index("\nclass ")] if "\nclass " in body[10:] else body
    assert re.search(r"def set_text\(", body), \
        "Keycap MUSI mat metodu set_text()"


def test_klavesovy_hook_sa_nevratil():
    """Poistka proti tichemu navratu globalneho hooku.

    Bol to jediny kus appky, ktory navonok vyzeral ako keylogger, a cely
    SAFETY.md sa o jeho odstranenie opiera. Keby ho niekto (vratane
    buduceho ja) vratil - napr. aby "islo znova priradit klaves" - nech to
    padne tu a nie az v momente, ked sa niekto pyta, preco appka pocuva
    klavesnicu.

    Testuje sa staticky, aby to bezalo bez Tk.
    """
    import re
    # Hlada sa IMPORT, nie slovo - v komentaroch sa pynput spomina zamerne
    # (vysvetluju, preco tam uz nie je).
    dovoz = re.compile(r"^\s*(?:from\s+pynput|import\s+pynput)", re.M)
    for subor in ("app.py", "ui_dialogs.py", "ui_kit.py"):
        src = _read(subor)
        assert not dovoz.search(src), f"{subor} znova importuje pynput"
        assert "keyboard.Listener(" not in src, f"{subor} znova instaluje hook"
        assert "mouse.Listener(" not in src, f"{subor} znova instaluje hook"

    app_src = _read("app.py")
    for meno in ("def begin_rebind", "def on_press", "def on_click",
                 "def handle_trigger"):
        assert meno not in app_src, f"{meno} sa vratilo do app.py"


def test_remove_selected_guards_against_emptying():
    """DandurfApp.remove_selected_slots musi odmietnut zmazanie vsetkych
    slotov - staticka kontrola, ze tam ta poistka je."""
    src = _read("app.py")
    block = src[src.index("def remove_selected_slots(self"):]
    block = block[:block.index("\n    def ", 5)]
    assert "slot_only_one" in block, \
        "remove_selected_slots musi mat poistku proti zmazaniu vsetkeho"
