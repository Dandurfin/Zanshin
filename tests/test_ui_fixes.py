"""UI fixes from the testing phase:
  * our own (Zanshin) colour picker + "Default" instead of the Windows
    dialog (no eyedropper - it took a picture of the whole screen, see
    SAFETY.md),
  * suppressing the CTk alpha flicker when moving the window between
    monitors (DPI),
  * unifying the Settings icon in the side panel (a text ⚙, not an emoji),
  * ⓘ on a stats card shows a floating popup (it NO LONGER EXPANDS the
    card, which used to make the centre/dojo grow too - especially in
    Russian/German).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _zdroj_appky import zdroj_appky, zdroj_metody  # noqa: E402


def _read(name):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, name), encoding="utf-8-sig") as fh:
        return fh.read()


# ---- color picker -------------------------------------------------------

def test_color_hex_roundtrip_a_default():
    from color_picker import hex_to_rgb, rgb_to_hex, DEFAULT
    assert rgb_to_hex(hex_to_rgb("#7fdd8a")) == "#7fdd8a"
    assert DEFAULT == "__default__"
    # nonsense input does not crash, it returns a safe fallback
    assert hex_to_rgb("xyz") == (217, 184, 104)


def test_pick_color_pouziva_vlastny_picker_nie_windows():
    for meno in ("pick_overlay_color", "pick_hud_trigger_color"):
        blok = zdroj_metody(meno)
        assert "ask_color" in blok, f"{meno} nevola vlastny picker"
        assert "colorchooser" not in blok, f"{meno} stale pouziva Windows dialog"


def test_picker_ma_predvolenu_a_ziadnu_pipetku():
    """The eyedropper took a screenshot of the whole desktop (ImageGrab) - game
    included. Yet SAFETY.md promises that the app does not read the screen
    content, and the colour picker has the area, hex and swatches. So it is
    gone and is not to come back."""
    import i18n
    src = _read("color_picker.py")
    assert "colorpick.reset_default" in src, "chyba tlacidlo Predvolena"
    assert "pick_from_screen" not in src, "pipetka sa vratila"
    assert "ImageGrab" not in src, "vyber farby nesmie fotit obrazovku"
    assert "colorpick.eyedropper" not in src
    assert "colorpick.eyedropper" not in i18n.STRINGS, "mrtvy text pipetky"


# ---- DPI alpha flicker when moving between monitors ---------------------

def test_alpha_blik_sa_nenastavuje_oknu():
    import ui_kit

    class Fake:                           # no winfo_id/after -> freeze is a no-op
        def __init__(self):
            self.calls = []

        def wm_attributes(self, *a):
            self.calls.append(a)
            return a

    f = Fake()
    ui_kit.potlac_dpi_alpha_blik(f)
    f.wm_attributes("-alpha", 0.15)      # scaling "blink" -> freezes, alpha is NOT set
    f.wm_attributes("-alpha", 1.0)       # end of rescaling -> unfreezes, alpha is NOT set
    assert not any(c and str(c[0]) in ("-alpha", "alpha") for c in f.calls), \
        "alpha sa uz nema posielat oknu (ziadny priesvitny duch)"
    f.wm_attributes("-topmost", True)    # other attributes pass through unchanged
    assert f.calls[-1] == ("-topmost", True)


def test_app_potlaca_alpha_blik():
    src = zdroj_appky()
    assert "potlac_dpi_alpha_blik(self.root)" in src


def test_zmena_jazyka_zmrazi_kreslenie():
    # The UI rebuild on a language change (_build_ui) is wrapped in a freeze
    # so that 1300+ widgets are not assembled piece by piece in front of the
    # player.
    blok = zdroj_metody("on_lang_switch")
    assert "freeze_repaint(self.root, True)" in blok
    assert "freeze_repaint(self.root, False)" in blok
    assert "finally:" in blok, "odmrazenie musi byt vo finally (aj pri chybe)"


# ---- Settings icon unified ----------------------------------------------

def test_settings_ikona_ma_textovu_prezentaciu():
    src = _read("ui_shell.py")
    # The variation selector U+FE0E forces a monochrome (thin) rendering of
    # ⚙ so it is not emoji-bold next to ◗ ◷ ◳. We check it sits right after ⚙.
    assert "⚙︎" in src, "ikona Nastavenia nema textovy variant ⚙︎"


# ---- ⓘ on StatCard is a popup, not an inline expansion ------------------

def test_statcard_info_je_plavajuci_popup():
    src = _read("ui_kit.py")
    card = src[src.index("class StatCard"):src.index("class QrReveal")]
    assert "info_label" not in card, \
        "info sa uz nesmie rozbalovat inline (rastie kartu -> stred/dojo)"
    assert "priprav_popup" in card, "info ma byt plavajuci popup"
    assert "_close_info" in card and "_info_pop" in card
    # the popup also closes on focus loss / minimising (not only on Leave)
    assert 'bind("<FocusOut>"' in card, "popup sa musi zavriet aj pri strate zamerania"


# ---- KamaeBar: reusing items instead of delete("all") every tick ----

def test_kamaebar_znovupouziva_prvky():
    src = _read("ui_kit.py")
    kb = src[src.index("class KamaeBar"):src.index("class PalCanvas")]
    assert "def _build_items" in kb and "def _update_items" in kb
    # the per-tick path (_update_items) MUST NOT delete and re-create items
    upd = kb[kb.index("def _update_items"):]
    assert 'delete("all")' not in upd, "per-tik prekreslenie nesmie mazat vsetko"
    assert "itemconfigure" in upd and "coords" in upd


def test_hex_neplatny_nenahradi_farbu():
    src = _read("color_picker.py")
    sh = src[src.index("def _set_hex"):src.index("def _sync_from_hsv")]
    assert "_sync_from_hsv" in sh and "return" in sh, \
        "neplatny/rozpisany hex sa nema aplikovat (inak zahodi zvolenu farbu)"


# ---- profile import: fresh uid (against sharing recordings) ----

def test_import_profilu_da_cerstve_uid():
    # The behaviour is in settings_model.slot_zo_zdielania (see also
    # tests/test_ip_skryta.py - sharing a profile by code).
    from settings_model import slot_zo_zdielania
    imp = zdroj_metody("import_profile_from_code")
    assert "slot_zo_zdielania" in imp, "import musi ist cez slot_zo_zdielania"
    cudzi = {"text": "x", "uid": "abc123abc123", "voice_path": "C:/a/voice.wav",
             "audio_path": "C:/a/rec.wav", "sfx_key": ""}
    slot = slot_zo_zdielania(cudzi)
    assert slot["uid"] and slot["uid"] != "abc123abc123", \
        "import musi dat cerstve uid (inak zdielane nahravky)"
    assert slot["voice_path"] == "" and slot["audio_path"] == ""


# ---- logging silent failures (so we catch more bugs) ----

def test_tiche_zlyhania_teraz_loguju():
    assert "HR: spracovanie vzorky zlyhalo" in _read("heart_rate.py")
    assert "gamepad: spracovanie udalosti zlyhalo" in _read("gamepad.py")


# ---- Today: enso centred AND clickable (the image is only set in _paint) ----

def test_enso_ma_klikaciu_zonu_a_centruje_sa_podla_vysky():
    lay = zdroj_metody("_layout_dnes_items")
    # The enso's click zone is derived from the KNOWN geometry - bbox("enso") is
    # None until the item has an image (it is only set in _paint), otherwise the
    # enso is NOT CLICKABLE.
    assert 'self._dnes_hit["enso"] = (' in lay
    # Centring by the known block height [0, y], not by bbox("block") (which
    # does not include the enso without an image -> the block sat too high).
    assert "h / 2 - y / 2" in lay


# ---- final check: data migration, controller, Edge privacy, KamaeBar DPI ----

def test_migracia_prenesie_aj_historiu_tepu(tmp_path):
    import paths
    old = tmp_path / "old"; old.mkdir()
    for f in ("dandurf_settings.json", "hr_sessions.json", "hr_windows.json",
              "hr_events.jsonl", "hr_insights.json"):
        (old / f).write_text("x", encoding="utf-8")
    (old / "hr_sessions.json.bak").write_text("x", encoding="utf-8")   # siblings too
    target = tmp_path / "new"
    paths._copy_data_dir(str(old), str(target))
    for f in ("dandurf_settings.json", "hr_sessions.json", "hr_windows.json",
              "hr_events.jsonl", "hr_insights.json", "hr_sessions.json.bak"):
        assert (target / f).exists(), f"migracia stratila {f} (strata dat)"


def test_gamepad_ma_mrtvu_zonu_a_reassert_aktivity():
    src = _read("gamepad.py")
    # The behaviour (JOY and CONTROLLER events, dead zones, trigger at rest) is
    # guarded by tests/test_gamepad.py; here only that it stayed in the module.
    assert "LEFT_STICK_DEADZONE" in src and "TRIGGER_DEADZONE" in src
    assert "def _reassert_activity" in src and "self._held" in src, \
        "drzane tlacidlo/pacicka sa musia ratat ako aktivita (inak cue padne v boji)"


def test_edge_zoznam_hlasov_sa_netiahne_zo_siete():
    """The Edge voice list is no longer downloaded at all - neither at start
    nor when switching engines. Edge is the default, so before, the app
    pinged Microsoft on every start just to trim the catalogue down to a
    fixed list."""
    assert "edge_tts.list_voices" not in _read("audio_engine.py")
    src = zdroj_appky()
    assert "_load_edge_voices, daemon=True" not in src, \
        "zoznam hlasov je lokalny - netreba vlakno ani siet"


def test_kamaebar_kresli_na_realnu_vysku_a_mierku():
    src = _read("ui_kit.py")
    kb = src[src.index("class KamaeBar"):src.index("class PalCanvas")]
    assert "winfo_height()" in kb, "KamaeBar musi brat REALNU vysku platna (DPI)"
    assert "get_widget_scaling" in kb and "self._last_mierka" in kb
    assert "self.BTN_SIZE * m" in kb, "spinac sa musi skalovat mierkou (150 %)"


# ---- start without flicker: the window shows only once drawn (DWM cloak) ----

import re
import types

import pytest


def test_zahal_okno_na_atrape_nic_nespravi_a_nepadne():
    import ui_kit

    class BezOkna:
        def winfo_id(self):
            raise RuntimeError("okno uz neexistuje")

    for okno in (object(), BezOkna()):
        assert ui_kit.zahal_okno(okno, True) is False
        assert ui_kit.zahal_okno(okno, False) is False
        assert ui_kit.je_zahalene(okno) is False


@pytest.mark.skipif(sys.platform != "win32", reason="DWM je len na Windows")
def test_dwm_ma_vlastny_handle_nie_zdielany_windll():
    # CTk calls windll.dwmapi.DwmSetWindowAttribute (dark title bar) without
    # argtypes - our argtypes must not change the library's call path.
    import ctypes
    import ui_kit
    assert ui_kit._dwm() is not ctypes.windll.dwmapi
    assert ctypes.windll.dwmapi.DwmSetWindowAttribute.argtypes is None


class _KorenAtrapa:
    """As much of the Tk root as `_odhal_hotove_okno` needs."""

    def __init__(self, stav="withdrawn", update_hodi=False):
        self.stav = stav
        self.update_hodi = update_hodi
        self.naplanovane = []          # (ms, callback), in order like Tk
        self.updaty = 0

    def state(self):
        return self.stav

    def after(self, ms, fn):
        self.naplanovane.append((ms, fn))
        return f"after#{len(self.naplanovane)}"

    def update(self):
        self.updaty += 1
        if self.update_hodi:
            raise RuntimeError("update zlyhal")

    def update_idletasks(self):
        pass


def _odhalovanie(monkeypatch, root, vysledky=None):
    """The real DandurfApp methods on an object without __init__ (without the
    whole app). `zahal_okno` only records what it would send to Windows;
    `app_log` collects errors."""
    import app as app_mod
    volania, chyby = [], []
    vysledky = iter(vysledky) if vysledky is not None else None

    def zahal(okno, zahalit):
        volania.append(zahalit)
        return next(vysledky) if vysledky is not None else True

    monkeypatch.setattr(app_mod.ui_kit, "zahal_okno", zahal)
    monkeypatch.setattr(app_mod, "app_log", types.SimpleNamespace(
        exception=lambda *a, **k: chyby.append(a)))
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.root = root
    a._zahalene = True
    a._refresh_dnes_backdrop = lambda: None
    return a, volania, chyby


def _dobehni(root, limit=1000):
    """Runs scheduled callbacks like the Tk loop, as long as there are any."""
    n = 0
    while root.naplanovane and n < limit:
        _, fn = root.naplanovane.pop(0)
        fn()
        n += 1
    return n


def test_odhalenie_pocka_kym_ctk_okno_znova_ukaze(monkeypatch):
    # after(0) fires in the CTk mainloop while the window is currently hidden.
    root = _KorenAtrapa("withdrawn")
    a, volania, _ = _odhalovanie(monkeypatch, root)
    a._odhal_hotove_okno()
    assert [ms for ms, _ in root.naplanovane] == [10], "schovane okno -> znova o 10 ms"
    assert volania == [] and root.updaty == 0, "schovane okno sa este nesmie odhalit"
    assert a._zahalene is True
    root.stav = "normal"               # CTk showed the window again
    _dobehni(root)
    assert root.updaty == 1, "pred odhalenim sa okno cele dokresli"
    assert volania == [False], "odhali sa presne raz"
    assert a._zahalene is False


def test_po_limite_pokusov_sa_okno_odhali_aj_tak(monkeypatch):
    root = _KorenAtrapa("withdrawn")   # e.g. start straight into the tray
    a, volania, _ = _odhalovanie(monkeypatch, root)
    a._odhal_hotove_okno()
    assert _dobehni(root) == a.ODHAL_MAX_POKUSOV
    assert volania == [False], "po limite sa okno odhali, nikdy neostane neviditelne"
    assert a._zahalene is False


def test_ked_kreslenie_spadne_okno_sa_aj_tak_odhali(monkeypatch):
    root = _KorenAtrapa("normal", update_hodi=True)
    a, volania, chyby = _odhalovanie(monkeypatch, root)
    a._odhal_hotove_okno()
    assert volania == [False], "odhalenie je vo finally"
    assert a._zahalene is False
    assert root.naplanovane == []
    assert len(chyby) == 1, "zlyhanie kreslenia sa zapise do logu, nie potichu"


def test_ked_sa_odklad_neda_naplanovat_okno_sa_odhali_hned(monkeypatch):
    root = _KorenAtrapa("withdrawn")

    def after(ms, fn):
        raise RuntimeError("root sa prave rusi")

    root.after = after
    a, volania, chyby = _odhalovanie(monkeypatch, root)
    a._odhal_hotove_okno()
    assert volania == [False] and a._zahalene is False
    assert len(chyby) == 1


def test_poistka_odhali_hned_a_potom_uz_nic_nerobi(monkeypatch):
    root = _KorenAtrapa("withdrawn")
    a, volania, _ = _odhalovanie(monkeypatch, root)
    a._odhal_hotove_okno(pokus=a.ODHAL_MAX_POKUSOV)     # safety net after 10 s
    assert volania == [False] and root.naplanovane == []
    a._odhal_hotove_okno(pokus=a.ODHAL_MAX_POKUSOV)     # already revealed -> nothing
    a._odhal_hotove_okno()
    assert volania == [False] and root.updaty == 1


def test_ked_odhalenie_zlyha_poistka_to_skusi_znova(monkeypatch):
    root = _KorenAtrapa("normal")
    a, volania, _ = _odhalovanie(monkeypatch, root, vysledky=[False, True])
    a._odhal_hotove_okno()
    assert a._zahalene is True, "Windows odhalenie neprijal -> poistka ma co robit"
    a._odhal_hotove_okno(pokus=a.ODHAL_MAX_POKUSOV)
    assert a._zahalene is False and volania == [False, False]


def test_zahalenie_sa_neopakuje_a_bez_dwm_bezi_start_ako_doteraz(monkeypatch):
    import app as app_mod
    volania, vysledok = [], [True]
    monkeypatch.setattr(app_mod.ui_kit, "zahal_okno",
                        lambda okno, z: volania.append(z) or vysledok[0])
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.root, a._zahalene = object(), False
    a._zahal_do_dokreslenia()
    a._zahal_do_dokreslenia()          # the second place it is shown (first start)
    assert volania == [True] and a._zahalene is True
    vysledok[0] = False                # Windows did not accept it (older system)
    b = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    b.root, b._zahalene = object(), False
    b._zahal_do_dokreslenia()
    assert b._zahalene is False, "bez zahalenia sa nic neplanuje - start ako doteraz"


def test_obe_prve_zobrazenia_su_zahalene_a_odhalenie_naplanovane():
    init = zdroj_metody("__init__")
    zobrazenia = re.findall(
        r"self\._zahal_do_dokreslenia\(\)\n\s*self\.root\.deiconify\(\)", init)
    assert len(zobrazenia) == 2, "prvy start (po sprievodcovi) aj bezny start"
    assert init.index("self._zahal_do_dokreslenia()") < init.index("self.root.deiconify()")
    assert "self.root.after(0, self._odhal_hotove_okno)" in init
    assert "self.root.after(self.ODHAL_POISTKA_MS" in init, "chyba poistka"


def test_harnessy_nefotia_zahalene_okno():
    # A cloaked window has winfo_viewable() True; a screenshot would capture
    # the desktop.
    for meno, fotiace in (("gui_harness_onboarding.py", "def shot"),
                          ("gui_harness_auto.py", "def grab")):
        src = _read(meno)
        assert src.count("ImageGrab.grab(") == 1, f"{meno}: grab len cez strazenu funkciu"
        telo = src[src.index(fotiace):]
        telo = telo[:telo.index("\ndef ")]
        assert telo.index("app_zahalena()") < telo.index("ImageGrab.grab("), meno
        assert "if app_zahalena():" in src[src.index("def run_steps"):], \
            f"{meno}: krok musi pockat, kym sa okno ukaze"
        assert "not ui_kit.je_zahalene(root)" in src, f"{meno}: kontrola viditelnosti"
    foto = _read("gui_screenshots.py")
    foto = foto[foto.index("def foto(meno)"):foto.index("def foto_okna")]
    assert foto.index("je_zahalene(root)") < foto.index("ImageGrab.grab(")


# ---- window icon: the enso, not the CustomTkinter logo ----

def test_bez_ensa_ostane_aspon_ikona_ctk():
    import app as app_mod
    root = types.SimpleNamespace(_iconbitmap_method_called=False,
                                 iconphoto=lambda *a: None)

    def zlyha():
        raise RuntimeError("kreslenie zlyhalo")

    app_mod.DandurfApp._apply_window_icon(types.SimpleNamespace(root=root, make_tray_image=zlyha))
    assert root._iconbitmap_method_called is False


@pytest.mark.skipif(sys.platform != "win32", reason="ikona v liste je vec Windows")
def test_enso_ikonu_customtkinter_neprepise():
    import customtkinter as ctk
    from PIL import Image
    import app as app_mod
    if app_mod._ImageTk is None:
        pytest.skip("chyba PIL.ImageTk")
    try:
        root = ctk.CTk()               # CTk hides the window itself right away - nothing shows
    except Exception as exc:
        pytest.skip(f"Tk sa neda vytvorit: {exc}")
    try:
        volania, fotky = [], []
        root.iconbitmap = lambda *a, **k: volania.append(a)
        povodne_iconphoto = root.iconphoto
        root.iconphoto = lambda default, *img: (fotky.append(bool(default)),
                                                povodne_iconphoto(default, *img))
        # Precondition: without the fix, CTk really does set its icon. This is
        # exactly the callback CTk schedules 200 ms after the window appears.
        root._windows_set_titlebar_icon()
        assert volania, "CTk uz ikonu neprepisuje - vlajka v _apply_window_icon je zbytocna"
        volania.clear()
        a = types.SimpleNamespace(root=root, make_tray_image=lambda: Image.new(
            "RGBA", (64, 64), (212, 175, 55, 255)))
        app_mod.DandurfApp._apply_window_icon(a)
        assert a._window_icon_ref is not None, "enso sa nenastavilo"
        # First start: CTk has already put its icon on the window (the timer
        # fired during onboarding). The default icon (True) would not override
        # it - the window itself must get the enso too (False).
        assert False in fotky, "enso len ako predvolena ikona - vlastnu ikonu CTk neprebije"
        # Normal start: the CTk timer fires only after us and must not
        # overwrite anything.
        root._windows_set_titlebar_icon()
        assert volania == [], "CTk by enso v liste a v Alt-Tab prepisal svojim logom"
    finally:
        root.destroy()
