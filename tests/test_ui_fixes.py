"""Opravy UI z testovacej fazy:
  * vlastny (Zanshin) color picker + pipetka + "Predvolena" namiesto Windows dialogu,
  * potlacenie CTk alpha-preblkania pri presune okna medzi monitormi (DPI),
  * zjednotenie ikony Nastavenia v bocnom paneli (textovy ⚙, nie emoji),
  * ⓘ na karte statistiky ukazuje plavajuci popup (uz NEROZBALUJE kartu, cim
    predtym rastol aj stred/dojo - najma v rustine/nemcine).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read(name):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, name), encoding="utf-8-sig") as fh:
        return fh.read()


# ---- color picker -------------------------------------------------------

def test_color_hex_roundtrip_a_default():
    from color_picker import hex_to_rgb, rgb_to_hex, DEFAULT
    assert rgb_to_hex(hex_to_rgb("#7fdd8a")) == "#7fdd8a"
    assert DEFAULT == "__default__"
    # nezmyselny vstup nepadne, vrati bezpecny fallback
    assert hex_to_rgb("xyz") == (217, 184, 104)


def test_pick_color_pouziva_vlastny_picker_nie_windows():
    src = _read("app.py")
    for meno in ("def pick_overlay_color", "def pick_hud_trigger_color"):
        blok = src[src.index(meno):]
        blok = blok[:blok.index("\n    def ", 5)]
        assert "ask_color" in blok, f"{meno} nevola vlastny picker"
        assert "colorchooser" not in blok, f"{meno} stale pouziva Windows dialog"


def test_picker_ma_pipetku_a_predvolenu():
    src = _read("color_picker.py")
    assert "def pick_from_screen" in src, "chyba pipetka"
    assert "colorpick.reset_default" in src, "chyba tlacidlo Predvolena"
    assert "colorpick.eyedropper" in src


# ---- DPI alpha-preblik pri presune medzi monitormi ----------------------

def test_alpha_blik_sa_nenastavuje_oknu():
    import ui_kit

    class Fake:                           # bez winfo_id/after -> freeze je no-op
        def __init__(self):
            self.calls = []

        def wm_attributes(self, *a):
            self.calls.append(a)
            return a

    f = Fake()
    ui_kit.potlac_dpi_alpha_blik(f)
    f.wm_attributes("-alpha", 0.15)      # scaling "blik" -> zmrazi, alpha sa NEnastavi
    f.wm_attributes("-alpha", 1.0)       # koniec prepoctu -> odmrazi, alpha sa NEnastavi
    assert not any(c and str(c[0]) in ("-alpha", "alpha") for c in f.calls), \
        "alpha sa uz nema posielat oknu (ziadny priesvitny duch)"
    f.wm_attributes("-topmost", True)    # ine atributy prechadzaju bez zmeny
    assert f.calls[-1] == ("-topmost", True)


def test_app_potlaca_alpha_blik():
    src = _read("app.py")
    assert "potlac_dpi_alpha_blik(self.root)" in src


def test_zmena_jazyka_zmrazi_kreslenie():
    # Prestavba UI pri zmene jazyka (_build_ui) je obalena zmrazenim, aby sa
    # 1300+ widgetov neskladalo pred hracom po castiach.
    src = _read("app.py")
    blok = src[src.index("def on_lang_switch"):]
    blok = blok[:blok.index("\n    def ", 5)]
    assert "freeze_repaint(self.root, True)" in blok
    assert "freeze_repaint(self.root, False)" in blok
    assert "finally:" in blok, "odmrazenie musi byt vo finally (aj pri chybe)"


# ---- ikona Nastavenia zjednotena ----------------------------------------

def test_settings_ikona_ma_textovu_prezentaciu():
    src = _read("ui_shell.py")
    # Variacny selektor U+FE0E prinuti monochromaticke (tenke) vykreslenie
    # ⚙, aby nebol emoji-tucny vedla ◗ ◷ ◳. Overujeme, ze sedi za ⚙.
    assert "⚙︎" in src, "ikona Nastavenia nema textovy variant ⚙︎"


# ---- ⓘ na StatCard je popup, nie inline rozbalenie ----------------------

def test_statcard_info_je_plavajuci_popup():
    src = _read("ui_kit.py")
    card = src[src.index("class StatCard"):src.index("class QrReveal")]
    assert "info_label" not in card, \
        "info sa uz nesmie rozbalovat inline (rastie kartu -> stred/dojo)"
    assert "priprav_popup" in card, "info ma byt plavajuci popup"
    assert "_close_info" in card and "_info_pop" in card
    # popup sa zavrie aj pri strate zamerania / minimalizacii (nie len pri Leave)
    assert 'bind("<FocusOut>"' in card, "popup sa musi zavriet aj pri strate zamerania"


# ---- KamaeBar: znovupouzitie prvkov namiesto delete("all") kazdy tik ----

def test_kamaebar_znovupouziva_prvky():
    src = _read("ui_kit.py")
    kb = src[src.index("class KamaeBar"):src.index("class PalCanvas")]
    assert "def _build_items" in kb and "def _update_items" in kb
    # per-tik cesta (_update_items) NESMIE mazat a znovu vytvarat prvky
    upd = kb[kb.index("def _update_items"):]
    assert 'delete("all")' not in upd, "per-tik prekreslenie nesmie mazat vsetko"
    assert "itemconfigure" in upd and "coords" in upd


# ---- pipetka: poistka proti zaseknutiu appky ----

def test_eyedropper_ma_poistku():
    src = _read("color_picker.py")
    pf = src[src.index("def pick_from_screen"):src.index("def _use_default")]
    assert 'bind("<Escape>"' in pf, "Escape sa ma naviazat hned (pred stavbou obrazka)"
    assert "except Exception:" in pf and "finish()" in pf, \
        "pri zlyhani stavby prekrytia sa musi vratit dialog (nezaseknut appku)"
    assert "_grab_img = None" in pf, "plocha sa po zatvoreni ma uvolnit"


def test_hex_neplatny_nenahradi_farbu():
    src = _read("color_picker.py")
    sh = src[src.index("def _set_hex"):src.index("def _sync_from_hsv")]
    assert "_sync_from_hsv" in sh and "return" in sh, \
        "neplatny/rozpisany hex sa nema aplikovat (inak zahodi zvolenu farbu)"


# ---- import profilu: cerstve uid (proti zdielaniu nahravok) ----

def test_import_profilu_da_cerstve_uid():
    src = _read("app.py")
    imp = src[src.index("def import_profile_from_code"):]
    imp = imp[:imp.index("\n    def ", 5)]
    assert 's["uid"] = ""' in imp, "import musi dat cerstve uid (inak zdielane nahravky)"
    assert 's["voice_path"] = ""' in imp


# ---- logovanie tichych zlyhani (aby sme chytili viac bugov) ----

def test_tiche_zlyhania_teraz_loguju():
    assert "HR: spracovanie vzorky zlyhalo" in _read("heart_rate.py")
    assert "gamepad: spracovanie udalosti zlyhalo" in _read("gamepad.py")


# ---- Dnes: enso vycentrovane A klikatelne (obrazok sa nastavuje az v _paint) ----

def test_enso_ma_klikaciu_zonu_a_centruje_sa_podla_vysky():
    src = _read("app.py")
    lay = src[src.index("def _layout_dnes_items"):src.index("def _canvas_text")]
    # Klikacia zona ensa sa odvodi zo ZNAMEJ geometrie - bbox("enso") je None,
    # kym polozka nema obrazok (nastavuje sa az v _paint), inak enso NEKLIKATELNE.
    assert 'self._dnes_hit["enso"] = (' in lay
    # Centrovanie podla znamej vysky bloku [0, y], nie podla bbox("block")
    # (ktora enso bez obrazka nezahrna -> blok sedel privysoko).
    assert "h / 2 - y / 2" in lay


# ---- finalna previerka: migracia dat, ovladac, Edge privacy, KamaeBar DPI ----

def test_migracia_prenesie_aj_historiu_tepu(tmp_path):
    import paths
    old = tmp_path / "old"; old.mkdir()
    for f in ("dandurf_settings.json", "hr_sessions.json", "hr_windows.json",
              "hr_events.jsonl", "hr_insights.json"):
        (old / f).write_text("x", encoding="utf-8")
    (old / "hr_sessions.json.bak").write_text("x", encoding="utf-8")   # aj surodenci
    target = tmp_path / "new"
    paths._copy_data_dir(str(old), str(target))
    for f in ("dandurf_settings.json", "hr_sessions.json", "hr_windows.json",
              "hr_events.jsonl", "hr_insights.json", "hr_sessions.json.bak"):
        assert (target / f).exists(), f"migracia stratila {f} (strata dat)"


def test_gamepad_ma_mrtvu_zonu_a_reassert_aktivity():
    src = _read("gamepad.py")
    assert "STICK_DEADZONE" in src and "_STICK_AXES" in src
    assert "def _reassert_activity" in src and "_buttons_down" in src, \
        "drzane tlacidlo/pacicka sa musia ratat ako aktivita (inak cue padne v boji)"


def test_edge_hlasy_sa_netiahnu_z_ms_bez_edge():
    src = _read("app.py")
    i = src.index("_load_edge_voices, daemon=True).start()")   # prvy = startovy spawn
    assert "self.engine == ENGINE_EDGE" in src[max(0, i - 260):i], \
        "Edge zoznam hlasov sa tiahne z Microsoftu aj ked hrac pouziva offline SAPI"


def test_kamaebar_kresli_na_realnu_vysku_a_mierku():
    src = _read("ui_kit.py")
    kb = src[src.index("class KamaeBar"):src.index("class PalCanvas")]
    assert "winfo_height()" in kb, "KamaeBar musi brat REALNU vysku platna (DPI)"
    assert "get_widget_scaling" in kb and "self._last_mierka" in kb
    assert "self.BTN_SIZE * m" in kb, "spinac sa musi skalovat mierkou (150 %)"
