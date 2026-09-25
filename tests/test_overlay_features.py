"""Testy nových funkcií vizualov: farba piktogramu, drag-test rezim,
blokovanie kolieska na slideroch. Bez Tk - testuje sa logika a API kontrakt.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import settings_model as sm
from _zdroj_appky import subory_appky, zdroj_appky, zdroj_metody


def test_overlay_config_has_color():
    """Kazdy vizual ma v konfiguracii pole color (None = farba temy)."""
    for cfg in sm.default_overlay_configs():
        assert "color" in cfg and cfg["color"] is None


def test_color_validation():
    """Farba sa uklada len ako platny #rrggbb, inak None."""
    assert sm.normalize_overlay_config({"color": "#AABBCC"}, 0)["color"] == "#aabbcc"
    assert sm.normalize_overlay_config({"color": "#f80"}, 0)["color"] is None      # kratke
    assert sm.normalize_overlay_config({"color": "red"}, 0)["color"] is None       # nazov
    assert sm.normalize_overlay_config({"color": "#GGGGGG"}, 0)["color"] is None   # nehex
    assert sm.normalize_overlay_config({"color": None}, 0)["color"] is None


def _read(name):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, name), encoding="utf-8-sig") as fh:
        return fh.read()


def test_slider_wheel_is_blocked_everywhere():
    """Kazdy CTkSlider musi byt obaleny block_slider_wheel - inak sa da
    hodnota omylom menit kolieskom pri scrollovani stranky."""
    # appka = app.py aj mixiny DandurfApp v app_*.py
    for f in (*subory_appky(), "ui_dialogs.py"):
        src = _read(f)
        raw_sliders = len(re.findall(r"ctk\.CTkSlider\(", src))
        wrapped = len(re.findall(r"block_slider_wheel\(ctk\.CTkSlider\(", src))
        assert raw_sliders == wrapped, \
            f"{f}: {raw_sliders} sliderov, {wrapped} obalenych - vsetky musia byt obalene"


def test_block_slider_wheel_returns_slider():
    """Helper musi vratit slider, aby .pack()/.grid() retazec fungoval."""
    src = _read("ui_kit.py")
    body = src[src.index("def block_slider_wheel"):]
    body = body[:body.index("\ndef ", 5)] if "\ndef " in body[5:] else body
    assert "return slider" in body


def test_block_slider_wheel_replaces_internal_handler():
    """Helper musi viazat priamo na slider._canvas (tkinter bind bez add),
    inak interny handler CTkSlider zbehne prvy a hodnotu zmeni - CTkSlider.bind()
    vzdy pridava (add=True), takze 'break' by prisiel neskoro."""
    src = _read("ui_kit.py")
    body = src[src.index("def block_slider_wheel"):]
    body = body[:body.index("\ndef ", 5)] if "\ndef " in body[5:] else body
    assert '"_canvas"' in body and "canvas.bind(seq, _redirect)" in body


def test_overlay_test_button_text_is_not_timed():
    """Tlacidlo Test uz nesmie slubovat '3 s' - test je drag rezim bez casu."""
    import i18n
    for lang, text in i18n.STRINGS["overlay.test"].items():
        assert "3 s" not in text and "3秒" not in text and "3 秒" not in text and "3 с" not in text, (lang, text)
    for lang, text in i18n.STRINGS["overlay.dialog_hint"].items():
        assert "3 s" not in text and "3 se" not in text and "3秒" not in text and "3 с" not in text, (lang, text)


def test_overlay_test_mode_decorates_frame_for_hit_testing():
    """V test rezime musi _render prehnat snimok cez _decorate_test (alfa >= 1
    na celej ploche = okno drzi mys kdekolvek, nie len na ciare)."""
    src = _read("overlay.py")
    block = src[src.index("    def _render(self, elapsed):"):]
    block = block[:block.index("\n    def ", 5)]
    assert "_decorate_test" in block
    assert "def _decorate_test" in src


def test_overlay_test_is_drag_mode_not_timed():
    """test() slotu musi spustat perzistentny drag rezim (_test_mode),
    nie 3-sekundovu ukazku."""
    src = _read("overlay.py")
    block = src[src.index("    def test(self):"):]
    block = block[:block.index("\n    def ", 5)]
    assert "_test_mode" in block, "test() musi prepinat drag rezim"


def test_layered_surface_can_toggle_click_through():
    """Pre drag musi ist docasne vypnut klik-through okna."""
    src = _read("layer_window.py")
    assert "def set_click_through" in src
    assert "WS_EX_TRANSPARENT" in src


def test_overlay_windows_keep_steam_overlay_flags():
    """Kazde overlay okno musi mat vsetky STYRI rozsirene styly naraz.

    Doteraz sa testoval len WS_EX_TRANSPARENT, ale ostatne tri su rovnako
    podstatne a lahko sa pri uprave okna stratia:

      WS_EX_LAYERED      - vobec umozni priehladne kreslenie
      WS_EX_TRANSPARENT  - klik prejde nasquoz do hry (anti-cheat princip)
      WS_EX_NOACTIVATE   - okno nikdy neprevezme fokus, hra ho nestrati
      WS_EX_TOOLWINDOW   - nie je v Alt+Tab ani na paneli uloh

    NOACTIVATE + TOOLWINDOW su zaroven to, co drzi appku bokom od Steam
    overlayu (Shift+Tab): okno, ktore si nepyta fokus a netvari sa ako
    bezna appka, sa so Steam overlayom nebije o aktivne okno.
    """
    src = _read("layer_window.py")
    flags = ("WS_EX_LAYERED", "WS_EX_TRANSPARENT",
             "WS_EX_NOACTIVATE", "WS_EX_TOOLWINDOW")

    for flag in flags:
        assert f"{flag} = 0x" in src, f"{flag} nie je definovany"

    # Miesta, kde sa okno ZAKLADA, musia nasadit vsetky styri naraz. Pozname
    # ich podla toho, ze pridavaju WS_EX_LAYERED - `set_click_through()`
    # naopak zamerne prepina len jediny bit (TRANSPARENT) a ostatne nechava
    # tak, takze ju sem nezaratavame.
    setups = src.split("WS_EX_LAYERED")[1:]
    # prva polozka je samotna definicia konstanty (`WS_EX_LAYERED = 0x...`)
    setups = [s for s in setups if not s.lstrip().startswith("=")]
    assert len(setups) >= 2, (
        f"cakali sa aspon 2 miesta, kde sa overlay oknu nasadzuju styly, "
        f"najdene: {len(setups)}")
    for i, seg in enumerate(setups, 1):
        head = seg[:200]
        for flag in ("WS_EX_TRANSPARENT", "WS_EX_NOACTIVATE", "WS_EX_TOOLWINDOW"):
            assert flag in head, (
                f"{i}. zakladanie overlay okna nenasadzuje {flag} - overlay "
                f"by prestal byt click-through alebo by sa bil o fokus "
                f"(aj so Steam overlayom)")


def test_guide_je_pod_hlaskami_a_stara_cesta_nezmizla():
    """Od 18. 9. Sprievodca NIE JE samostatna karta - vysvetlivky a teoria
    sedia pod hlaskami, lebo clovek ich hlada prave tam.

    Kluc "guide" sa ale nesmie stratit: odkazuje sa nan `Sidebar.GROUPS`,
    prikazova paleta aj sprievodca sam. Keby `_navigate("guide")` prepadlo
    na `pages.show("guide")`, okno by ostalo PRAZDNE - ticho, bez vynimky.
    Preto `TAB_ALIAS`.
    """
    shell = _read("ui_shell.py")
    assert '"guide": "nastavenia"' in shell, "guide musi zostat v GROUPS sidebaru"

    app_src = zdroj_appky()
    riadok = app_src[app_src.index("SETTINGS_TABS = ("):].split("\n")[0]
    assert '"guide"' not in riadok, "guide uz nema byt samostatna karta"

    assert 'TAB_ALIAS = {"guide": "spustace"}' in app_src, \
        "stara cesta na guide musi niekam viest"
    nav = zdroj_metody("_navigate")
    assert "TAB_ALIAS" in nav, "_navigate musi alias naozaj pouzit"

    # a obsah sa naozaj vklada pod hlasky
    assert "_build_guide_into" in app_src
    spustace = zdroj_metody("_build_spustace_page")
    assert "_build_guide_into" in spustace, "vysvetlivky nie su na stranke hlasok"

    guide = _read("guide_panel.py")
    assert "def build_guide_into" in guide
    assert "class _GuideContent" in guide
    # Vlozeny sprievodca NESMIE mat vlastny scroll - sedi uz v scrollujucej
    # stranke a druhy posuvnik by obsah zovrel do uzkeho pasu.
    vkladanie = guide[guide.index("def build_guide_into"):]
    vkladanie = vkladanie[:vkladanie.index(chr(10) * 3)]
    # az KOD pod docstringom - v poznamke je slovo spomenute zamerne
    vkladanie = vkladanie[vkladanie.index('"""', vkladanie.index('"""') + 3):]
    assert "CTkScrollableFrame" not in vkladanie, "dvojity scroll sa vratil"

    # A stara stranka sprievodcu sa uz NESTAVIA. Kym sa stavala, bezala az
    # po stranke Hlasky a prepisovala `self.guide_content` - rozbalovanie
    # kariet potom siahalo na neviditelnu stranku.
    assert "_build_guide_page" not in app_src, "mrtva stranka sprievodcu sa vratila"


def test_guide_uses_real_overlay_icons():
    """Sprievodca musi kreslit realne piktogramy z overlay (render_slot_icon),
    nie len ilustracne nacrty."""
    src = _read("guide_panel.py")
    block = src[src.index("def sketch_or_image"):]
    block = block[:block.index("\nclass ", 5)]
    assert "render_slot_icon" in block, \
        "sketch_or_image musi pouzit realny piktogram z hud_paint"


def test_karta_hlasky_uz_nenastavuje_casovanie():
    """Sest casovacich poli z karty hlasky zmizlo.

    Vlastny cooldown, oneskorenie, "kazde N-te", opakovanie, pauza medzi
    opakovaniami a rozptyl sa citali JEDINE vo `fire_slot`, teda pri
    tlacidle Test a pri kliku v HUD nahlade. Automaticku hlasku spusta
    `_fire_somatic_cue` cez `_emit`. Boli to teda ovladace, ktore pri hrani
    nerobili nic - a pritom vyzerali ako hlavne nastavenie appky.
    """
    dialogs = _read("ui_dialogs.py")
    # Len telo SlotCard - `HoverTooltip` ma svoje vlastne `self.delay`
    # (oneskorenie bublinky) a s casovanim hlasky nema nic spolocne.
    karta = dialogs[dialogs.index("class SlotCard:"):]
    karta = karta[:karta.index('\nclass ', 5)]
    for mrtve in ("self.every_n", "self.repeat_gap", "self.jitter",
                  "self.cooldown", "self.delay", "self.repeat",
                  "_cooldown_text", "press_count"):
        assert mrtve not in karta, f"{mrtve} sa vratilo na kartu hlasky"
    assert "class NumberStepper" not in dialogs, "stepper uz nema co ovladat"
    dialog = dialogs[dialogs.index("class SlotSettingsDialog:"):]
    dialog = dialog[:dialog.index('\nclass ', 5)]
    assert "NumberStepper" not in dialog and "timing" not in dialog,         "dialog hlasky ma nastavovat uz len hlas"

    # dorucenie = `fire_slot` + `_note_cue` + `_deliver`
    dorucenie = "\n".join(zdroj_metody(m) for m in ("fire_slot", "_note_cue", "_deliver"))
    for mrtve in ("slot.every_n", "slot.jitter", "slot.repeat", "slot.delay",
                  "slot.cooldown", "press_count"):
        assert mrtve not in dorucenie, f"{mrtve} sa vratilo do dorucenia"


def test_ako_casto_sa_ozvem_riadi_algoritmus_nie_prepinac():
    """Volba „ako casto sa ozvem" zanikla — prah si appka rata z dat.

    Mala tri polohy (menej / bezne / viac) a hrac nemal ako vediet, co ktora
    urobi PRAVE JEMU: zataz je skalovana voci jeho vlastnej zakladne, takze
    to iste cislo znamena u kazdeho nieco ine.

    Prvá relacia bezi na cislach pre priemerneho hraca
    (`trigger.default_params()`); vlastny prah pride, az ked je z coho ratat.
    """
    app_src = zdroj_appky()
    assert "cue_sensitivity" not in app_src, "nastavenie sa vratilo"
    assert "self.citlivost_var" not in app_src, "prepinac sa vratil"

    assert "hr_stats.dynamicky_prah_zataze(" in app_src, "prah sa nikde nepocita"
    assert "trigger.default_params()" in app_src,         "chybaju cisla pre priemerneho hraca"

    # Poradie: priemerny hrac, nad nim vlastny prah, nad nim vyvojarska vrstva.
    # Vsetky tri vrstvy su v `_open_hr_session` - poradie sa meria v nej.
    otvor = zdroj_metody("_open_hr_session")
    zaklad = otvor.index("self.cue_trigger.params.update(trigger.default_params())")
    vlastny = otvor.index('self.cue_trigger.params["stress_threshold"] = float(')
    dev = otvor.index("self.cue_trigger.params.update(self._dev_params)")
    assert zaklad < vlastny < dev, "vrstvy sa prekryvaju v zlom poradi"


def test_prah_zataze_sa_rata_z_vlastnych_relacii():
    """80. percentil vlastnej zataze — nie cislo z tabulky.

    Odmerane na realnych datach: prah 73 dava 3,7 dorucenych hlasok za
    hodinu, teda pod strop 5 zo zadania. Prah neurcuje, KOLKO hlasok pride
    (to robi `max_per_hour` a `min_gap_s`), ale KTORE momenty sa kvalifikuju.
    """
    import hr_stats

    # Krivka musi vyzerat ako telo: plynula, bez skokov nad 30 bpm medzi
    # susednymi bodmi - inak ju `je_podozriva` (spravne) oznaci za pokazenu
    # a z vypoctu vypadne.
    def relacie(bpm_hore):
        vlna = []
        for i in range(60):
            for b in range(70, bpm_hore, 5):       # plynule hore
                vlna.append(b)
            for b in range(bpm_hore, 70, -5):      # a spat dole
                vlna.append(b)
        return [{"curve": vlna, "duration_s": 1800.0, "baseline_bpm": 70}
                for _ in range(4)]

    nizky = hr_stats.dynamicky_prah_zataze(relacie(85), baseline=70, critical=110)
    vysoky = hr_stats.dynamicky_prah_zataze(relacie(130), baseline=70, critical=110)
    assert nizky is not None and vysoky is not None
    assert vysoky > nizky, "vyhrotenejsie relacie musia dat vyssi prah"
    lo, hi = hr_stats.PRAH_ROZSAH
    assert lo <= nizky <= hi and lo <= vysoky <= hi

    # bez dat sa nic netvrdi
    assert hr_stats.dynamicky_prah_zataze([]) is None
    assert hr_stats.dynamicky_prah_zataze(
        [{"curve": [80] * 600, "duration_s": 1800.0}]) is None

def test_vysvetlivka_sedi_v_karte_hlasky_ku_ktorej_patri():
    """Kazda zo styroch hlasok nesie svoju vlastnu vysvetlivku.

    Poradie NIE JE nahodne: `guide_content.GUIDE_CARD_IDS` musi sediet na
    sloty 0-3 v tom istom poradi ako `measure.CATEGORIES`, lebo to su tie
    iste styri somaticke vizualy. Keby sa jedno z tych poli preusporiadalo,
    karta "Zuby" by ticho ukazovala vysvetlivku k dychaniu - bez vynimky,
    bez chyby, len s nespravnym textom.
    """
    import guide_panel
    import measure
    from guide_content import GUIDE_CARD_IDS

    assert len(GUIDE_CARD_IDS) == len(measure.CATEGORIES) + 1
    assert GUIDE_CARD_IDS[-1] == guide_panel.PHILOSOPHY_ID
    for index in range(len(measure.CATEGORIES)):
        karta = guide_panel.card_for_slot(index)
        assert karta is not None and karta["id"] == GUIDE_CARD_IDS[index]

    # Vlastny slot hraca vysvetlivku nema a filozofia nepatri ziadnej hlaske.
    for mimo in (len(measure.CATEGORIES), 99, -1, None, "x"):
        assert guide_panel.card_for_slot(mimo) is None


def test_obsah_vysvetlivky_ma_jeden_zdroj():
    """Karta hlasky a Sprievodca kreslia TEN ISTY obsah.

    Keby si kazde miesto skladalo bloky samo, prva zmena textu by ich
    rozislo - a nikto by si nevsimol ktore z nich je zastarale.
    """
    guide = _read("guide_panel.py")
    assert "def populate_card_body" in guide
    assert guide.count("populate_card_body(") >= 2
    dialogs = _read("ui_dialogs.py")
    assert "guide_panel.populate_card_body(" in dialogs

    karta = dialogs[dialogs.index("class SlotCard:"):]
    karta = karta[:karta.index(chr(10) + "class ", 5)]
    assert "def toggle_detail" in karta
    # Telo sa stavia az pri prvom rozbaleni - styri karty naraz by bolo
    # pri kazdom prekresleni stranky vidno ako seknutie.
    assert "_detail_built" in karta


def test_spodny_blok_je_uz_len_filozofia():
    guide = _read("guide_panel.py")
    vkladanie = guide[guide.index("def build_guide_into"):]
    vkladanie = vkladanie[:vkladanie.index(chr(10) * 3)]
    assert "card_ids=[PHILOSOPHY_ID]" in vkladanie, \
        "styri vysvetlivky uz patria do kariet hlasok, nie sem"
    assert "expand_first=False" in vkladanie, \
        "desat odkazov na studie nema visiet rozbalenych pod hlaskami"
