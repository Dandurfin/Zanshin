# -*- coding: utf-8 -*-
"""Dialog musi patrit hlavnemu oknu, inak ho hlavne okno prekryje (24. 9.:
dotaznik po relacii zostal schovany za appkou, hrac ho nevedel vyplnit)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ui_kit  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src(name):
    with open(os.path.join(ROOT, name), encoding="utf-8-sig") as fh:
        return fh.read()


def test_dialog_chrome_pripina_dialog_k_hlavnemu_oknu():
    src = _src("ui_kit.py")
    chrome = src[src.index("class DialogChrome"):]
    chrome = chrome[:chrome.index("def _begin")]
    assert "pripni_k_vlastnikovi(top)" in chrome
    assert chrome.count("pripni_k_vlastnikovi(top)") >= 2   # <Map> aj _take_focus


@pytest.mark.skipif(sys.platform != "win32", reason="len Windows")
def test_bezramovy_dialog_dostane_vlastnika_a_prebije_topmost_hlavne_okno():
    import ctypes
    import tkinter as tk
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("bez displeja")
    try:
        root.geometry("300x200+40+40")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.update()
        dlg = tk.Toplevel(root)
        dlg.transient(root)
        dlg.overrideredirect(True)
        dlg.geometry("120x60+60+60")
        dlg.update()
        u = ctypes.WinDLL("user32")
        u.GetWindow.restype = ctypes.c_void_p
        u.GetWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        h_dlg, h_root = ui_kit._window_hwnd(dlg), ui_kit._window_hwnd(root)
        # bez opravy Tk vlastnika zahodi (to je ten bug)
        assert not u.GetWindow(ctypes.c_void_p(h_dlg), 4)
        assert ui_kit.pripni_k_vlastnikovi(dlg) is True
        dlg.update()
        assert int(u.GetWindow(ctypes.c_void_p(h_dlg), 4) or 0) == int(h_root)   # GW_OWNER
        assert bool(dlg.attributes("-topmost"))
    finally:
        root.destroy()


def test_pripni_nikdy_nevyhodi_vynimku():
    class Falosne:
        master = None
    assert ui_kit.pripni_k_vlastnikovi(Falosne()) is False
