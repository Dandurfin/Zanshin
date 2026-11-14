# -*- coding: utf-8 -*-
"""Úvod (sprievodca prvým spustením) a prehliadka appky - 0.2.2.

Čo tieto testy strážia (audit 0.2.2):
  * "Spárovať hodinky teraz" úvod NEukončí: kroky 4-5 (svet, štýl, jediná
    zmienka o Microsofte) prídu aj tak, párovanie sa otvorí po úvode a prvá
    prehliadka až po zatvorení párovania - nie nikdy,
  * "Preskočiť" na krokoch 1-2 vedie na krok s hodinkami, nie cez neho,
  * úvod sa dá zavrieť (✕, Esc, Alt+F4) - pri prvom štarte s pokojnou
    otázkou "Ukončiť Zanshin?"; Ukončiť nič neuloží a appka skončí,
  * krok 5 má ukážku podľa vybranej odpovede; hlas je VŽDY hlas z Windows,
    úvod nikam nič neposiela; pri Práci veta, že otázka platí pre Hru,
  * prehliadka: päť miest namiesto desiatich bublín, text o ensō tvrdí len
    to, čo kód naozaj robí, a koniec bez hodiniek povie, že appka mlčí.
"""
import ast
import os
import sys
import threading
import time
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import guided_tour  # noqa: E402
import i18n  # noqa: E402
import i18n_cs_bg  # noqa: E402
import rebrik  # noqa: E402
import theme as theme_mod  # noqa: E402
import ui_dialogs  # noqa: E402
from _zdroj_appky import zdroj_metody  # noqa: E402

KOREN = os.path.join(os.path.dirname(__file__), "..")
W = ui_dialogs.OnboardingWizard
tr = i18n.tr


def _read(meno):
    with open(os.path.join(KOREN, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _trieda(subor, meno):
    return next(u for u in ast.walk(ast.parse(_read(subor)))
                if isinstance(u, ast.ClassDef) and u.name == meno)


def _metoda(subor, trieda, meno):
    return next(f for f in _trieda(subor, trieda).body
                if isinstance(f, ast.FunctionDef) and f.name == meno)


@pytest.fixture(autouse=True)
def _slovencina():
    povodny = i18n._lang["code"]
    i18n.set_lang("sk")
    yield
    i18n.set_lang(povodny)


class _Zaznam:
    """Atrapa widgetu: zapisuje volania configure/pack/place."""

    def __init__(self):
        self.volania = []
        self.cfg = {}

    def configure(self, **kw):
        self.cfg.update(kw)
        self.volania.append(("configure", kw))

    def __getattr__(self, meno):
        if meno.startswith("_"):
            raise AttributeError(meno)
        return lambda *a, **k: self.volania.append((meno, a, k))


# --------------------------------------------------------------------------
# Úvod: hodinky a preskočenie
# --------------------------------------------------------------------------

def test_sparovat_teraz_uvod_neukonci_a_ide_dalej():
    kroky, zavrete = [], []
    wz = types.SimpleNamespace(
        wants_pairing=False, KROK_HODINKY=W.KROK_HODINKY,
        _pair_button_look=lambda: None,
        _show_step=kroky.append, _confirm=lambda: zavrete.append(True))
    W._pair_now(wz)
    assert wz.wants_pairing is True
    assert kroky == [W.KROK_HODINKY + 1], "po hodinkach ide krok 4 (svet)"
    assert not zavrete, "uvod sa nesmie hned skoncit - kroky 4 a 5 by vypadli"


def test_tlacidlo_parovania_ukaze_ze_volba_plati():
    pal = theme_mod.tokens(theme_mod.DEFAULT_THEME)
    btn = _Zaznam()
    wz = types.SimpleNamespace(wants_pairing=False, _pal=pal, pair_btn=btn)
    W._pair_button_look(wz)
    assert btn.cfg["text"].endswith(tr("ob.step3.pair_now"))
    wz.wants_pairing = True
    W._pair_button_look(wz)
    assert btn.cfg["text"] == "✓  " + tr("ob.step3.pair_queued")
    assert tr("ob.step3.pair_queued") == "Párovanie otvorím po úvode"


def test_preskocit_vedie_na_hodinky_a_od_nich_sa_skryje():
    assert W.KROK_HODINKY == 2 and not hasattr(W, "PRVA_VOLBA")
    paticka = ast.unparse(_metoda("ui_dialogs.py", "OnboardingWizard", "_build_footer"))
    assert "self._show_step(self.KROK_HODINKY)" in paticka
    krok = ast.unparse(_metoda("ui_dialogs.py", "OnboardingWizard", "_show_step"))
    assert "index >= self.KROK_HODINKY" in krok
    assert i18n.STRINGS["ob.skip"]["sk"] == "Preskočiť na hodinky"
    assert i18n.STRINGS["ob.skip"]["en"] == "Skip to the watch"


# --------------------------------------------------------------------------
# Úvod: zavretie
# --------------------------------------------------------------------------

def _wz_zavretie(prvy_start):
    stav = {"zatvorene": [], "otazka": 0, "skryta": 0}
    wz = types.SimpleNamespace(
        _prvy_start=prvy_start, _otazka=None, _otazka_od=0.0,
        OTAZKA_DUPLIKAT_S=W.OTAZKA_DUPLIKAT_S, quit_requested=False)
    wz._close = lambda confirmed: stav["zatvorene"].append(confirmed)

    def ukaz():
        stav["otazka"] += 1
        wz._otazka = object()
        wz._otazka_od = time.monotonic()

    def skry():
        stav["skryta"] += 1
        wz._otazka = None

    wz._show_quit_question = ukaz
    wz._hide_quit_question = skry
    return wz, stav


def test_z_palety_zavretie_uvod_len_zrusi():
    wz, stav = _wz_zavretie(prvy_start=False)
    W._on_close_request(wz)
    assert stav["zatvorene"] == [False] and stav["otazka"] == 0


def test_pri_prvom_starte_sa_zavretie_pyta():
    wz, stav = _wz_zavretie(prvy_start=True)
    W._on_close_request(wz)
    assert stav["otazka"] == 1 and not stav["zatvorene"], "nie do prazdna"
    # Alt+F4 pride ako klaves aj ako WM_DELETE_WINDOW - druhy signal hned
    # po prvom otazku nesmie zavriet
    W._on_close_request(wz)
    assert stav["skryta"] == 0 and wz._otazka is not None
    # neskorsie Esc / krizik = Pokracovat
    wz._otazka_od -= 1.0
    W._on_close_request(wz)
    assert stav["skryta"] == 1 and wz._otazka is None and not stav["zatvorene"]


def test_ukoncit_nic_neprevezme():
    wz, stav = _wz_zavretie(prvy_start=True)
    W._quit(wz)
    assert wz.quit_requested is True and stav["zatvorene"] == [False]


def test_zavretie_uvolni_okno():
    top = _Zaznam()
    wz = types.SimpleNamespace(top=top, confirmed=None,
                               _stop_picture_preview=lambda: None)
    W._close(wz, confirmed=True)
    assert wz.confirmed is True
    assert [v[0] for v in top.volania] == ["grab_release", "destroy"]


def test_okno_ide_cez_otazku_a_navrchu_len_pri_prvom_starte():
    init = _metoda("ui_dialogs.py", "OnboardingWizard", "__init__")
    assert [a.arg for a in init.args.kwonlyargs] == ["prvy_start"]
    src = ast.unparse(init)
    assert "self.top.protocol('WM_DELETE_WINDOW', self._on_close_request)" in src
    assert "on_close=self._on_close_request" in src and "closable=False" not in src
    assert "'<Alt-F4>'" in src
    topmost = [u for u in ast.walk(init) if isinstance(u, ast.If)
               and ast.unparse(u.test) == "self._prvy_start"]
    assert topmost and "'-topmost', True" in ast.unparse(topmost[0])
    assert src.count("-topmost") == 1, "navrchu len pri prvom starte"


def test_app_po_ukonceni_z_uvodu_nic_neulozi_a_skonci():
    init = zdroj_metody("__init__")
    blok = init[init.index("wizard = OnboardingWizard(self.root, prvy_start=True)"):]
    blok = blok[:blok.index("if wizard.confirmed:")]
    assert "quit_requested" in blok
    assert blok.index("self.root.destroy()") < blok.index("raise SystemExit(0)")
    assert "save_settings" not in blok


# --------------------------------------------------------------------------
# Krok 4 a 5: svet, ukážka, Práca
# --------------------------------------------------------------------------

def test_krok4_uz_nema_test_zvuku():
    krok = _metoda("ui_dialogs.py", "OnboardingWizard", "_step4")
    volania = {ast.unparse(u.func) for u in ast.walk(krok) if isinstance(u, ast.Call)}
    assert "ctk.CTkButton" not in volania and "ctk.CTkSlider" not in volania
    assert "test_sound" not in ast.unparse(krok)
    assert "onboarding.test_sound" not in i18n.STRINGS, "mrtvy kluc"
    sk = i18n.STRINGS["ob.step4.body"]
    assert sk["sk"].endswith("Vlastné hranice sa učím len z Hry.")
    assert sk["en"].endswith("I learn your own limits from Play only.")


def _wz_ukazka(volba, assets=True):
    btn, riadok, hlasitost = _Zaznam(), _Zaznam(), _Zaznam()
    styl = None if volba is None else (
        rebrik.STYL_HLAS if volba == W.NEVIEM else rebrik.normalize_cue_style(volba))
    wz = types.SimpleNamespace(preview_btn=btn, _preview_row=riadok,
                               _volume_box=hlasitost, _cue_volba=volba,
                               cue_style=styl, _assets_ready=assets)
    W._refresh_preview(wz)
    return btn, riadok, hlasitost


def test_bez_odpovede_ukazka_nie_je():
    btn, riadok, _h = _wz_ukazka(None)
    assert ("place_forget", (), {}) in riadok.volania and "text" not in btn.cfg


@pytest.mark.parametrize("volba, kluc, s_hlasitostou", [
    ("voice", "ob.preview.voice", True),
    (W.NEVIEM, "ob.preview.voice", True),          # neviem = hlas
    ("sound", "ob.preview.sound", True),
    ("visual", "ob.preview.visual", False),        # obrazok nema hlasitost
])
def test_ukazka_podla_odpovede(volba, kluc, s_hlasitostou):
    btn, riadok, hlasitost = _wz_ukazka(volba)
    assert btn.cfg["text"] == tr(kluc) and btn.cfg["state"] == "normal"
    assert any(v[0] == "place" for v in riadok.volania)
    assert any(v[0] == ("pack" if s_hlasitostou else "pack_forget")
               for v in hlasitost.volania)


def test_ukazka_zvuku_caka_na_zvuky():
    btn, _r, _h = _wz_ukazka("sound", assets=False)
    assert btn.cfg["text"] == tr("assets.preparing") and btn.cfg["state"] == "disabled"


def test_ukazka_hlasu_ma_povinny_popis():
    assert i18n.STRINGS["ob.preview.voice"]["sk"] == (
        "▶ Ukážka (hlas z Windows — prirodzený je jemnejší)")


@pytest.mark.parametrize("volba, cakane", [
    ("voice", "hlas"), (W.NEVIEM, "hlas"), ("sound", "zvuk"), ("visual", "obraz")])
def test_ukazka_hra_vybranu_odpoved(volba, cakane):
    zahrane = []
    styl = rebrik.STYL_HLAS if volba == W.NEVIEM else rebrik.normalize_cue_style(volba)
    wz = types.SimpleNamespace(
        cue_style=styl, _cue_volba=volba,
        _speak_preview=lambda: zahrane.append("hlas"),
        _play_sound_preview=lambda: zahrane.append("zvuk"),
        _show_picture_preview=lambda: zahrane.append("obraz"))
    W._play_preview(wz)
    assert zahrane == [cakane]


def test_ukazka_hlasu_je_hlas_z_windows(monkeypatch):
    povedane = []
    hotovo = threading.Event()

    def sapi(text, voice_id, rate, volume=100):
        povedane.append((text, voice_id, rate, volume))
        hotovo.set()

    monkeypatch.setattr(ui_dialogs, "speak_sapi_isolated", sapi)
    wz = types.SimpleNamespace(_hovori=False, volume_value=55)
    W._speak_preview(wz)
    assert hotovo.wait(5)
    for _ in range(100):
        if not wz._hovori:
            break
        time.sleep(0.01)
    assert povedane == [(tr("slot.default.breath"), None, 0, 55)]
    assert wz._hovori is False
    # kym znie, druhy klik nic nespusti
    wz._hovori = True
    W._speak_preview(wz)
    assert len(povedane) == 1


def test_uvod_nikam_nic_neposiela():
    """Žiadny Edge, žiadna príprava hlášok: o tom, čo posiela prirodzený
    hlas, sa hráč dozvie až v riadku pod otázkou."""
    trieda = _trieda("ui_dialogs.py", "OnboardingWizard")
    mena = set()
    for u in ast.walk(trieda):
        if isinstance(u, ast.Name):
            mena.add(u.id)
        elif isinstance(u, ast.Attribute):
            mena.add(u.attr)
    assert not [m for m in mena if "edge" in m.lower() or "pregen" in m.lower()], mena
    assert "speak_sapi_isolated" in mena


def test_pri_praci_krok5_povie_ze_otazka_plati_pre_hru():
    krok = ast.unparse(_metoda("ui_dialogs.py", "OnboardingWizard", "_step5"))
    assert "theme_mod.theme_world(self.choice) == 'work'" in krok
    assert "tr('ob.cue.work_note')" in krok
    assert krok.index("tr('ob.cue.title')") < krok.index("tr('ob.cue.work_note')")
    assert i18n.STRINGS["ob.cue.work_note"]["sk"] == (
        "V Práci sa ozývam len obrázkom — toto platí pre Hru.")
    assert "self._build_preview_row(parent)" in krok


# --------------------------------------------------------------------------
# Úvod naživo (Tk) - len Windows s displejom
# --------------------------------------------------------------------------

@pytest.mark.skipif(sys.platform != "win32", reason="len Windows")
def test_uvod_nazivo(monkeypatch):
    import ctypes
    import tkinter as tk
    import customtkinter as ctk
    import sfx_assets
    import ui_kit
    monkeypatch.setattr(sfx_assets, "ensure_assets", lambda **k: None)
    monkeypatch.setattr(sfx_assets, "missing_count", lambda: 0)
    try:
        root = ctk.CTk()
    except tk.TclError:
        pytest.skip("bez displeja")
    try:
        root.withdraw()

        def pump(wz):
            for _ in range(20):
                wz.top.update()
                time.sleep(0.01)

        wz = W(root, prvy_start=True)
        pump(wz)
        assert int(wz.top.attributes("-topmost")) == 1
        wz.skip_btn.invoke()
        assert wz._step == W.KROK_HODINKY
        assert not wz.skip_btn.winfo_ismapped()
        wz._pair_now()
        assert wz._step == 3 and wz.wants_pairing and wz.top.winfo_exists()
        # krizik OS (WM_CLOSE len nasmu oknu) -> otazka, nie zavretie
        u = ctypes.WinDLL("user32")
        u.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                   ctypes.c_void_p, ctypes.c_void_p]
        u.PostMessageW(ctypes.c_void_p(ui_kit._window_hwnd(wz.top)), 0x0010, None, None)
        pump(wz)
        assert wz._otazka is not None and wz.top.winfo_exists()
        wz._quit()
        assert wz.quit_requested and not wz.confirmed and not wz.top.winfo_exists()

        # z palety: zavretie len zrusi, bez otazky a bez topmost
        wz = W(root)
        pump(wz)
        assert int(wz.top.attributes("-topmost")) == 0
        wz._on_close_request()
        assert not wz.top.winfo_exists() and not wz.confirmed and not wz.quit_requested
    finally:
        root.destroy()


# --------------------------------------------------------------------------
# Prehliadka
# --------------------------------------------------------------------------

def test_prehliadka_ma_pat_miest():
    kluce = [k for k, *_ in guided_tour._STEPS]
    assert kluce == ["welcome", "dock", "sensor", "triggers", "history", "done"]
    assert guided_tour.GuidedTour.STEP_COUNT == 6
    # uvodna bublina + pat miest; kazde miesto na nieco ukazuje
    assert guided_tour._STEPS[0][2] is None
    assert all(spec is not None for _k, _p, spec, _s, _a in guided_tour._STEPS[1:])
    assert [k for k, *_r, akcia in guided_tour._STEPS if akcia] == ["sensor"]
    uvod = i18n.STRINGS["tour.welcome.body"]
    assert uvod["sk"] == "Ukážem ti päť miest v appke — asi minúta. Preskočiť môžeš kedykoľvek."
    assert "pár sekúnd" not in uvod["sk"] and "few seconds" not in uvod["en"]


def test_odstranene_kroky_nezanechali_kluce():
    for kluc in ("tour.kamae.title", "tour.kamae.body", "tour.sound.title",
                 "tour.sound.body", "tour.ingame.title", "tour.ingame.body",
                 "tour.today.title", "tour.today.body", "onboarding.test_sound"):
        assert kluc not in i18n.STRINGS, kluc
        assert kluc not in i18n_cs_bg.CS and kluc not in i18n_cs_bg.BG, kluc
        assert f"_tr7('{kluc}'" not in _read("i18n.py"), kluc


class _Root:
    def __init__(self):
        self.after_volania = []

    def after(self, ms, fn):
        self.after_volania.append((ms, fn))
        return f"job{len(self.after_volania)}"

    def after_cancel(self, _job):
        pass


def _app(tep=None, prijem=True):
    app = types.SimpleNamespace(
        pal=theme_mod.tokens(theme_mod.DEFAULT_THEME), root=_Root(),
        hr_monitoring_enabled=prijem,
        hr_stats=types.SimpleNamespace(last_bpm=tep),
        progres=[], parovanie=[], stranky=[])
    nastavenia = object()
    app.sidebar = types.SimpleNamespace(
        rows={"nastavenia": nastavenia}, pair_btn=object(),
        _select=app.stranky.append)
    app.nastavenia_row = nastavenia
    app.save_tour_progress = app.progres.append
    app.mark_tour_seen = lambda: None
    app.open_watch_pairing = lambda on_close=None: app.parovanie.append(on_close)
    return app


def test_koniec_bez_hodiniek_povie_ze_mlcim():
    app = _app(tep=None)
    tour = guided_tour.GuidedTour(app)
    koniec = tour.steps[-1]
    assert tour._body(koniec) == tr("tour.done.no_watch")
    assert tr("tour.done.no_watch") == (
        "Ešte jedno: bez hodiniek mlčím. Spáruj ich, keď budeš mať chvíľu.")
    assert koniec.target_fn() is app.sidebar.pair_btn, "ukaze na kontrolku hodiniek"
    # prijem vypnuty, hoci posledne BPM by tam este bolo
    app = _app(tep=72, prijem=False)
    assert guided_tour.GuidedTour(app)._body(koniec) == tr("tour.done.no_watch")


def test_koniec_s_tepom_ukaze_kde_prehliadku_spustit_znova():
    app = _app(tep=72)
    tour = guided_tour.GuidedTour(app)
    koniec = tour.steps[-1]
    assert tour._body(koniec) == tr("tour.done.body")
    assert koniec.target_fn() is app.nastavenia_row
    # ine kroky si text nevyberaju
    assert tour._body(tour.steps[1]) == tr("tour.dock.body")


def test_parovanie_z_prehliadky_pokracuje_dalsim_krokom():
    app = _app()
    tour = guided_tour.GuidedTour(app, start_index=2)
    app._tour = tour
    assert tour.steps[2].action == "pair"
    tour._pair()
    assert app.progres == [3], "pozicia uz za krokom o tepe"
    assert len(app.parovanie) == 1 and callable(app.parovanie[0])
    app.parovanie[0]()                       # navod sa zavrel
    assert tour._index == 3 and app.stranky[-1] == "spustace"
    assert app.root.after_volania, "dalsia bublina sa kresli"


def test_parovanie_nepokracuje_v_nahradenej_prehliadke():
    app = _app()
    tour = guided_tour.GuidedTour(app, start_index=2)
    app._tour = object()                     # medzitym nova z Nastaveni
    tour._pair()
    app.parovanie[0]()
    assert tour._index == 2 and not app.root.after_volania


def test_stara_pozicia_prehliadky_sa_zmesti():
    """Do 0.2.1 mala prehliadka 10 krokov - ulozene "8" by v Nastaveniach
    ukazalo "krok 9 z 6"."""
    init = zdroj_metody("__init__")
    riadok = init[init.index("self.tour_step = "):]
    riadok = riadok[:riadok.index("\n        #")]
    assert "GuidedTour.STEP_COUNT - 1" in riadok and "min(" in riadok
    tour = guided_tour.GuidedTour(_app(), start_index=8)
    assert tour._index == guided_tour.GuidedTour.STEP_COUNT - 1


# --------------------------------------------------------------------------
# Prehliadka po párovaní z úvodu
# --------------------------------------------------------------------------

def test_prehliadka_pride_po_parovani():
    import app as app_mod
    D = app_mod.DandurfApp
    for tour_seen, beziaca, cakane in ((False, None, True), (True, None, False),
                                       (False, object(), False)):
        root = _Root()
        a = types.SimpleNamespace(tour_seen=tour_seen, _tour=beziaca, root=root,
                                  start_tour=lambda: None)
        D._prehliadka_po_parovani(a)
        assert bool(root.after_volania) is cakane, (tour_seen, beziaca)
        if cakane:
            assert root.after_volania[0] == (300, a.start_tour)


def test_navod_na_parovanie_ma_on_close():
    assert "WatchPairingDialog(self, on_close=on_close)" in zdroj_metody("open_watch_pairing")
    init = _metoda("ui_dialogs.py", "WatchPairingDialog", "__init__")
    assert "on_close" in [a.arg for a in init.args.args]


# --------------------------------------------------------------------------
# Text o ensō hovorí pravdu
# --------------------------------------------------------------------------

def test_enso_v_prehliadke_bez_farieb_ktore_neexistuju():
    nazov = i18n.STRINGS["tour.dock.title"]
    assert nazov["sk"] == "Ensō — stav appky" and nazov["en"] == "The ensō — the app's state"
    telo = i18n.STRINGS["tour.dock.body"]
    assert telo["sk"] == (
        "Toto je ensō, značka appky. Keď sledujem, pomaly dýcha; keď stojím, je "
        "nehybné. Pomalý prstenec vnútri znamená, že čakám na vhodnú chvíľu. Klikom "
        "ma spustíš alebo zastavíš. Stav ukazuje aj bodka vľavo hore.")
    farby = {"sk": "zelen", "en": "green", "ja": "緑", "zh": "绿", "ru": "зелён",
             "es": "verde", "de": "grün", "fr": "vert", "pt": "verde", "cs": "zelen",
             "bg": "зелен"}
    for jazyk, slovo in farby.items():
        assert slovo not in telo[jazyk].lower(), jazyk
        assert telo[jazyk] != telo["en"] or jazyk == "en", ("nepreložené", jazyk)


def test_kazde_tvrdenie_o_enso_sedi_s_kodom():
    # farba je vzdy akcent temy, nie stav
    fn = next(u for u in ast.parse(_read("hud_paint.py")).body
              if isinstance(u, ast.FunctionDef) and u.name == "render_enso")
    enso = ast.unparse(ast.Module(body=fn.body[1:], type_ignores=[]))   # bez docstringu
    assert "base = color or style.accent" in enso
    assert "success" not in enso and "danger" not in enso
    # "pomaly dycha / zastavene stoji": zastavene ma jedinu snimku
    shell = _read("ui_shell.py")
    hero = shell[shell.index("class _EnsoHero"):shell.index("class _WatchPulse")]
    assert "bucket = 0        # zastavene enso stoji" in hero
    # "pomaly prstenec vnutri" = natiahnuty spustac, len pri sledovani
    assert "armed = self._armed and self._live" in hero
    assert "if armed and live:" in enso
    # "klikom ma spustis alebo zastavis"
    klik = zdroj_metody("_dnes_canvas_click")
    assert 'hit.get("enso")' in klik and "self.toggle_listening()" in klik
    # "bodka vlavo hore": bodka stavu je v bocnom paneli NAD navigaciou
    # (od 0.2.2 davka 4 je navigacia jedna skupina - vsetky PAGES naraz)
    sidebar = shell[shell.index("class Sidebar"):shell.index("class _NavRow")]
    assert sidebar.index("self.state_dot = _StateDot(") < sidebar.index(
        "for key, icon, default_label in self.PAGES:")


# --------------------------------------------------------------------------
# Texty: všetky jazyky, slovník 0.2.2
# --------------------------------------------------------------------------

NOVE_A_ZMENENE = ("ob.skip", "ob.quit.title", "ob.quit.body", "ob.quit.yes", "ob.quit.no",
                  "ob.step3.pair_queued", "ob.step4.body", "ob.cue.work_note",
                  "ob.preview.voice", "ob.preview.sound", "ob.preview.visual",
                  "tour.welcome.body", "tour.dock.title", "tour.dock.body",
                  "tour.sensor.pair", "tour.done.no_watch")


def test_texty_maju_vsetkych_jedenast_jazykov_a_vlastny_preklad():
    for kluc in NOVE_A_ZMENENE:
        zaznam = i18n.STRINGS[kluc]
        assert set(zaznam) == set(i18n.LANGUAGES), kluc
        for jazyk in i18n.LANGUAGES:
            if jazyk != "en":
                assert zaznam[jazyk] != zaznam["en"], ("nepreložené", kluc, jazyk)
        assert i18n.tr_lang("sk", kluc) == zaznam["sk"]
    assert i18n.STRINGS["ob.quit.title"]["sk"] == "Ukončiť Zanshin?"
    assert i18n.STRINGS["ob.quit.body"]["sk"] == "Úvod sa ukáže pri ďalšom spustení."
    assert (i18n.STRINGS["ob.quit.yes"]["sk"], i18n.STRINGS["ob.quit.no"]["sk"]) == (
        "Ukončiť", "Pokračovať")


def test_nove_texty_hovoria_novym_slovnikom():
    """Hlavný vypínač = sledovať (nie počúvať/odpočúvať), bez žargónu."""
    for kluc in NOVE_A_ZMENENE:
        sk = i18n.STRINGS[kluc]["sk"].lower()
        en = i18n.STRINGS[kluc]["en"].lower()
        assert "počúva" not in sk and "odpočúva" not in sk, kluc
        assert "listen" not in en, kluc
        for zargon in ("udp", "obs-websocket", "0.0.0.0", "websocket"):
            assert zargon not in sk and zargon not in en, (kluc, zargon)
