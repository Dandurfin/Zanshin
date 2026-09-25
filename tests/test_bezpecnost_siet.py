# -*- coding: utf-8 -*-
"""Bezpečnosť voči hre a sieť (0.2, záverečná kontrola).

Čo tieto testy strážia - každé z toho bol sľub v SAFETY.md / PRIVACY.md,
ktorý kód nedodržal:
  * vypnutý auto-profil nečíta zoznam procesov vôbec (predtým sken bežal
    stále a vypínač len zahodil výsledok),
  * veta o štarte pri hre menuje presne hry z mapy; „bootstrapper.exe“
    (všeobecné meno spúšťača) v mape nie je,
  * zoznam Edge hlasov sa nesťahuje z Microsoftu (Edge je predvolený, takže
    predtým pri každom štarte),
  * texty hlášok sa na syntézu neposielajú, keď hláška nehovorí (štýl
    „zvuk“/„obrázok“, svet Práca), a počas počúvania vôbec - chýbajúca
    hláška sa dopripraví po hre,
  * nainštalovaná appka zvuky neťahá z GitHubu - skopíruje pribalené.
"""
import ast
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402
from _zdroj_appky import zdroj_appky, zdroj_metody  # noqa: E402

KOREN = os.path.join(os.path.dirname(__file__), "..")


def _read(meno):
    with open(os.path.join(KOREN, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _telo(subor, meno):
    """Zdrojak funkcie/metody `meno` zo suboru (cez ast, bez importu)."""
    # "app.py" = cela appka: app.py aj mixiny DandurfApp v app_*.py
    src = zdroj_appky() if subor == "app.py" else _read(subor)
    for uzol in ast.walk(ast.parse(src)):
        if isinstance(uzol, ast.FunctionDef) and uzol.name == meno:
            return ast.get_source_segment(src, uzol)
    raise AssertionError(meno)


def _app():
    import app as app_mod
    return app_mod


def _profily():
    """Modul, z ktoreho `_start_game_watcher` cita `GameProcessWatcher` a
    `PSUTIL_AVAILABLE`. Metoda byva v mixine app_profiles (ProfilesMixin),
    nie v app.py - falosny watcher treba podstrcit tam."""
    _app()
    import app_profiles
    return app_profiles


@pytest.fixture
def jazyk():
    povodny = i18n._lang["code"]
    yield i18n.set_lang
    i18n.set_lang(povodny)


# --------------------------------------------------------------------------
# Auto-profil: vypnutý = procesy sa nečítajú
# --------------------------------------------------------------------------

class _FalosnyWatcher:
    vsetky = []

    def __init__(self, on_found, on_gone, interval=4.0):
        self.bezi = False
        self.zastaveny = False
        _FalosnyWatcher.vsetky.append(self)

    def start(self):
        self.bezi = True

    def stop(self):
        self.zastaveny = True


def _atrapa_auto_profilu(app_mod, zapnute):
    a = types.SimpleNamespace(
        auto_profile_enabled=zapnute, game_watcher=None,
        _auto_started_listening=True, listening=True, kamae=None,
        auto_profile_var=types.SimpleNamespace(get=lambda: a.auto_profile_enabled),
        save_settings=lambda: None, log=lambda *_: None,
        on_game_process_found=lambda *_: None, on_game_process_gone=lambda: None)
    D = app_mod.DandurfApp
    a._start_game_watcher = types.MethodType(D._start_game_watcher, a)
    a._stop_game_watcher = types.MethodType(D._stop_game_watcher, a)
    return a


def test_vypnuty_auto_profil_zastavi_citanie_procesov(monkeypatch):
    app_mod = _app()
    monkeypatch.setattr(_profily(), "GameProcessWatcher", _FalosnyWatcher)
    monkeypatch.setattr(_profily(), "PSUTIL_AVAILABLE", True)
    _FalosnyWatcher.vsetky = []
    a = _atrapa_auto_profilu(app_mod, zapnute=True)

    app_mod.DandurfApp.on_auto_profile_toggle(a)
    assert len(_FalosnyWatcher.vsetky) == 1 and _FalosnyWatcher.vsetky[0].bezi
    prvy = a.game_watcher

    a.auto_profile_enabled = False
    app_mod.DandurfApp.on_auto_profile_toggle(a)
    assert prvy.zastaveny, "vypnutý auto-profil nesmie ďalej čítať procesy"
    assert a.game_watcher is None
    assert a._auto_started_listening is False, \
        "počúvanie, ktoré spustila hra, odteraz riadi hráč"

    a.auto_profile_enabled = True
    app_mod.DandurfApp.on_auto_profile_toggle(a)
    assert len(_FalosnyWatcher.vsetky) == 2, "vlákno sa nedá spustiť dvakrát - nové"
    assert a.game_watcher is _FalosnyWatcher.vsetky[1] and a.game_watcher.bezi


def test_zapnutie_dvakrat_nespusti_druhy_watcher(monkeypatch):
    app_mod = _app()
    monkeypatch.setattr(_profily(), "GameProcessWatcher", _FalosnyWatcher)
    monkeypatch.setattr(_profily(), "PSUTIL_AVAILABLE", True)
    _FalosnyWatcher.vsetky = []
    a = _atrapa_auto_profilu(app_mod, zapnute=True)
    a._start_game_watcher()
    a._start_game_watcher()
    assert len(_FalosnyWatcher.vsetky) == 1


def test_bez_psutil_sa_watcher_nespusti(monkeypatch):
    app_mod = _app()
    monkeypatch.setattr(_profily(), "GameProcessWatcher", _FalosnyWatcher)
    monkeypatch.setattr(_profily(), "PSUTIL_AVAILABLE", False)
    _FalosnyWatcher.vsetky = []
    a = _atrapa_auto_profilu(app_mod, zapnute=True)
    a._start_game_watcher()
    assert _FalosnyWatcher.vsetky == [] and a.game_watcher is None


def test_start_appky_spusti_watcher_len_pri_zapnutom_auto_profile():
    init = zdroj_metody("__init__")
    assert "GameProcessWatcher(" not in init, "štart ide len cez _start_game_watcher"
    assert ("if self.auto_profile_enabled:\n"
            "                self._start_game_watcher()") in init.replace("\r\n", "\n")


def test_mapa_hier_bez_vseobecneho_spustaca_a_veta_ich_meni(jazyk):
    import game_profiles
    assert "bootstrapper.exe" not in game_profiles.GAME_PROCESS_MAP
    hry = game_profiles.known_games()
    assert hry == sorted(set(game_profiles.GAME_PROCESS_MAP.values()), key=str.lower)
    D = _app().DandurfApp
    for kod in ("sk", "en"):
        jazyk(kod)
        a = types.SimpleNamespace(auto_profile_enabled=True, _zname_hry=D._zname_hry)
        titul, veta = D._kamae_zastavene(a)
        popis = i18n.tr("settings.auto_profile_sub", games=D._zname_hry())
        for hra in hry:
            assert hra in veta, (kod, hra)
            assert hra in popis, (kod, hra)
        assert "{games}" not in veta and "{games}" not in popis
    jazyk("sk")
    assert "sama" in i18n.tr("kamae.stopped_sub_auto", games="X")
    assert "nečítam" in i18n.tr("settings.auto_profile_sub", games="X"), \
        "popis má povedať, že vypnutý prepínač procesy nečíta"


def test_popis_auto_profilu_je_pod_prepinacom():
    telo = _telo("app.py", "_build_spustace_page")
    assert "settings.auto_profile_sub" in telo
    assert "games=self._zname_hry()" in telo


# --------------------------------------------------------------------------
# Edge: zoznam hlasov bez siete
# --------------------------------------------------------------------------

class _ZiadnaSiet:
    def __getattr__(self, meno):
        raise AssertionError(f"edge_tts.{meno} - zoznam hlasov nemá ísť na sieť")


def test_zoznam_edge_hlasov_je_lokalny_a_v_jazyku_rozhrania(monkeypatch, jazyk):
    import audio_engine
    from settings_model import DEFAULT_EDGE_VOICE, EDGE_FALLBACK_VOICES
    monkeypatch.setattr(audio_engine, "edge_tts", _ZiadnaSiet(), raising=False)
    monkeypatch.setattr(audio_engine, "EDGE_AVAILABLE", True)

    jazyk("sk")
    items = audio_engine.EdgeTTSCache.list_voices()
    assert [s for s, _ in items] == [v[0] for v in EDGE_FALLBACK_VOICES]
    assert items[0][0] == DEFAULT_EDGE_VOICE
    popis = dict(items)
    assert popis["sk-SK-ViktoriaNeural"] == "sk-SK · Viktória (žena)"
    assert popis["sk-SK-LukasNeural"] == "sk-SK · Lukáš (muž)"
    assert i18n.tr("voice.most_natural") in popis["en-US-AvaMultilingualNeural"]

    jazyk("en")
    popis = dict(audio_engine.EdgeTTSCache.list_voices())
    assert popis["en-GB-SoniaNeural"] == "en-GB · Sonia (female)"
    assert len(set(popis.values())) == len(popis), "popisy musia byť jedinečné (kľúč mapy)"


# --------------------------------------------------------------------------
# Edge: čo sa posiela na syntézu a kedy
# --------------------------------------------------------------------------

def _atrapa_hlasu(app_mod, styl="voice", svet="play"):
    from settings_model import MODE_COMBO, MODE_SFX, MODE_TTS
    D = app_mod.DandurfApp
    a = types.SimpleNamespace(
        cue_style=styl, world=svet, edge_voice_id="en-GB-SoniaNeural",
        slots=[types.SimpleNamespace(mode=MODE_COMBO, text_value="Breathe", voice_edge=""),
               types.SimpleNamespace(mode=MODE_TTS, text_value="Jaw", voice_edge="x-Y"),
               types.SimpleNamespace(mode=MODE_SFX, text_value="nic", voice_edge="")],
        engine=app_mod.ENGINE_EDGE, rate_value=0, _pregen_job=None, _pregen_seq=0,
        pal={"success": "g", "warn": "y", "danger": "r"}, stavy=[], posielane=[])
    a._hlasky_hovoria = types.MethodType(D._hlasky_hovoria, a)
    a.pregen_jobs = types.MethodType(D.pregen_jobs, a)
    a.set_edge_status = lambda text, color=None: a.stavy.append(text)
    a.edge_cache = types.SimpleNamespace(
        has=lambda *_: False, ensure=lambda *x, **_k: a.posielane.append(x))
    return a


def test_bez_hlasu_sa_texty_hlasok_neposielaju(monkeypatch):
    import audio_engine
    app_mod = _app()
    monkeypatch.setattr(audio_engine, "EDGE_AVAILABLE", True)
    vlakna = []
    monkeypatch.setattr(app_mod.threading, "Thread",
                        lambda *x, **k: vlakna.append(k) or types.SimpleNamespace(
                            start=lambda: None))
    for styl, svet in (("visual", "play"), ("sound", "play"), ("voice", "work")):
        a = _atrapa_hlasu(app_mod, styl, svet)
        assert a.pregen_jobs() == [], (styl, svet)
        app_mod.DandurfApp.pregenerate(a, force=True)
        assert a.stavy == [""] and a.posielane == [], (styl, svet)
    assert vlakna == [], "nič sa nemá ani začať generovať"

    a = _atrapa_hlasu(app_mod, "voice", "play")
    assert a.pregen_jobs() == [("Breathe", "en-GB-SoniaNeural"), ("Jaw", "x-Y")]


def test_chybajuca_hlaska_pocas_hry_nejde_na_siet(monkeypatch):
    import audio_engine
    app_mod = _app()
    monkeypatch.setattr(audio_engine, "EDGE_AVAILABLE", True)
    D = app_mod.DandurfApp

    def atrapa(pocuva, hovoria=True):
        a = types.SimpleNamespace(
            listening=pocuva, engine=app_mod.ENGINE_EDGE, edge_voice_id="v",
            rate_value=0, saved_voice_id="sapi", _pregen_po_hre=False,
            edge_cache=types.SimpleNamespace(has=lambda *_: False),
            logy=[], ui=[], hovorene=[], pripravy=[])
        a._hlasky_hovoria = lambda: hovoria
        a._slot_voice_clip = lambda slot: None
        a.log_threadsafe = a.logy.append
        a.ui_call = a.ui.append
        a.pregenerate = lambda *_: None
        a.audio = types.SimpleNamespace(speak=lambda *x: a.hovorene.append(x))
        a.schedule_pregenerate = lambda *x: a.pripravy.append(x)
        return a

    slot = types.SimpleNamespace(voice_edge="", voice_sapi="")
    a = atrapa(pocuva=True)
    D._speak_text(a, "Breathe", slot)
    assert a.ui == [], "počas hry sa na Microsoft nejde"
    assert a._pregen_po_hre is True
    assert a.logy == [i18n.tr("log.edge_not_cached_later")]
    assert a.hovorene, "hláška aj tak zaznie - hlasom z Windows"

    D._dopriprav_hlasky_po_hre(a)
    assert a.pripravy and a._pregen_po_hre is False
    D._dopriprav_hlasky_po_hre(a)
    assert len(a.pripravy) == 1, "bez chýbajúcej hlášky sa nič nepripravuje"

    a = atrapa(pocuva=False)
    D._speak_text(a, "Breathe", slot)
    assert a.ui == [a.pregenerate], "mimo hry sa chýbajúca hláška pripraví hneď"
    assert a._pregen_po_hre is False

    # Hlášky v hre nehovoria (len obrázok / zvuk / Práca): ukážka zaznie cez
    # SAPI, nič sa nepripravuje a denník nesľubuje prípravu, ktorá nepríde.
    for pocuva in (True, False):
        a = atrapa(pocuva=pocuva, hovoria=False)
        D._speak_text(a, "Breathe", slot)
        assert a.ui == [] and a.logy == [] and a._pregen_po_hre is False
        assert a.hovorene


def test_stop_pocuvania_dopripravi_hlasky():
    assert "self._dopriprav_hlasky_po_hre()" in _telo("app.py", "stop_listening")


# --------------------------------------------------------------------------
# Celá príprava hlasu (`pregenerate`) počas počúvania nejde na sieť
# --------------------------------------------------------------------------

def _atrapa_pripravy(app_mod, monkeypatch, pocuva):
    """Atrapa s ozajstným `pregenerate` / `schedule_pregenerate` /
    `_dopriprav_hlasky_po_hre`; vlákno sa nespúšťa, len zapíše."""
    import audio_engine
    monkeypatch.setattr(audio_engine, "EDGE_AVAILABLE", True)
    D = app_mod.DandurfApp
    a = _atrapa_hlasu(app_mod)
    a.listening = pocuva
    a._pregen_po_hre = False
    a.pal["text_dim"] = "d"
    a.vlakna, a.ui, a.prune = [], [], []
    a.ui_call = a.ui.append
    a._prune_cache = lambda *x: a.prune.append(x)
    a.root = types.SimpleNamespace(ulohy=[])
    a.root.after = lambda ms, fn: a.root.ulohy.append(fn) or len(a.root.ulohy)
    a.root.after_cancel = lambda job: None
    for meno in ("pregenerate", "schedule_pregenerate", "_dopriprav_hlasky_po_hre"):
        setattr(a, meno, types.MethodType(getattr(D, meno), a))
    monkeypatch.setattr(app_mod.threading, "Thread",
                        lambda *x, **k: a.vlakna.append(k) or types.SimpleNamespace(
                            start=lambda: None))
    return a


def test_priprava_pocas_pocuvania_sa_odlozi_na_po_hre(monkeypatch):
    app_mod = _app()
    a = _atrapa_pripravy(app_mod, monkeypatch, pocuva=True)
    for force in (False, True):
        a.pregenerate(force=force)
        assert a.vlakna == [] and a.posielane == [], "počas hry sa na Microsoft nejde"
        assert a._pregen_po_hre is True
        assert a.stavy[-1] == i18n.tr("edge.after_game")

    # Stop počúvania: príprava sa naplánuje a až potom beží naozaj.
    a.listening = False
    a._dopriprav_hlasky_po_hre()
    assert a._pregen_po_hre is False and len(a.root.ulohy) == 1
    a.root.ulohy[0]()
    assert len(a.vlakna) == 1, "po hre sa hlášky pripravia"
    assert a.stavy[-1] == i18n.tr("edge.generating")


def test_hotove_hlasky_pocas_pocuvania_su_len_hotove(monkeypatch):
    """Keď je všetko v cache, niet čo posielať - netreba nič odkladať."""
    app_mod = _app()
    a = _atrapa_pripravy(app_mod, monkeypatch, pocuva=True)
    a.edge_cache.has = lambda *_: True
    a.pregenerate()
    assert a.vlakna == [] and a._pregen_po_hre is False
    assert a.stavy == [i18n.tr("edge.ready")] and a.prune


def test_auto_profil_pri_starte_hry_nic_neposiela(monkeypatch):
    """Presne scenár zo zadania: známa hra sa spustí, auto-profil prepne
    profil (`switch_profile` -> `schedule_pregenerate`) a hneď zapne
    počúvanie. Keď príde na rad príprava, appka už počúva - odloží ju."""
    app_mod = _app()
    D = app_mod.DandurfApp
    a = _atrapa_pripravy(app_mod, monkeypatch, pocuva=False)
    a.auto_profile_enabled = True
    a._auto_started_listening = False
    a.profiles = [{"name": "Default", "slots": []}, {"name": "CS2", "slots": []}]
    a.active_profile_name = "Default"
    a._sync_active_profile_slots = lambda: None
    a.rebuild_slots = lambda slots: None
    a.refresh_profile_switch = lambda: None
    a.profile_var = types.SimpleNamespace(set=lambda v: None)
    a.save_settings = lambda: None
    a.log = lambda *x: None
    a.start_listening = lambda: setattr(a, "listening", True)
    a.switch_profile = types.MethodType(D.switch_profile, a)

    D._handle_game_found(a, "CS2")
    assert a.listening and a.active_profile_name == "CS2"
    assert len(a.root.ulohy) == 1, "príprava je naplánovaná"
    a.root.ulohy[0]()
    assert a.vlakna == [] and a.posielane == []
    assert a._pregen_po_hre is True

    # Rovnako ručné prepnutie profilu uprostred hry.
    a._pregen_po_hre = False
    a.switch_profile("Default")
    a.root.ulohy[-1]()
    assert a.vlakna == [] and a._pregen_po_hre is True


def test_rozbehnuta_priprava_prestane_ked_sa_zapne_pocuvanie(monkeypatch):
    """Príprava spustená pred hrou pošle najviac tú hlášku, ktorá už letí;
    ďalšiu už nie - zvyšok odovzdá `pregenerate`, ktorý ju odloží."""
    app_mod = _app()
    a = _atrapa_pripravy(app_mod, monkeypatch, pocuva=False)

    def posli(*x, **_k):
        a.posielane.append(x)
        a.listening = True          # hra sa rozbehla počas prvej hlášky
        return True

    a.edge_cache.ensure = posli
    a.log_threadsafe = lambda *x: None
    a.pregenerate()
    assert len(a.vlakna) == 1
    a.vlakna[0]["target"]()
    assert len(a.posielane) == 1, "druhá hláška už na sieť nešla"
    assert a.ui == [a.pregenerate]
    a.ui[0]()
    assert a._pregen_po_hre is True and len(a.vlakna) == 1


def _falosny_edge(monkeypatch, tmp_path, pri_odoslani=None):
    """Ozajstný `EdgeTTSCache` s ozajstným zámkom; namiesto Microsoftu
    atrapa `edge_tts.Communicate`, ktorá si zapíše každú požiadavku."""
    import asyncio
    import audio_engine
    odoslane = []

    class _Hovor:
        def __init__(self, text, voice, rate=None):
            odoslane.append((text, voice))

        async def save(self, cesta):
            if pri_odoslani is not None:
                pri_odoslani(len(odoslane))
            with open(cesta, "wb") as fh:
                fh.write(b"mp3")

    monkeypatch.setattr(audio_engine, "EDGE_AVAILABLE", True)
    monkeypatch.setattr(audio_engine, "asyncio", asyncio)
    monkeypatch.setattr(audio_engine, "edge_tts",
                        types.SimpleNamespace(Communicate=_Hovor))
    monkeypatch.setattr(audio_engine, "TTS_CACHE_DIR", str(tmp_path))
    return audio_engine.EdgeTTSCache(lambda *_: None), odoslane


class _ZamokSHlasenim:
    """Zámok, ktorý dá vedieť, keď naň niekto začne čakať."""

    def __init__(self):
        import threading
        self._zamok = threading.Lock()
        self.caka = threading.Event()

    def __enter__(self):
        self.caka.set()
        return self._zamok.__enter__()

    def __exit__(self, *x):
        return self._zamok.__exit__(*x)


def test_ensure_sa_po_cakani_na_zamku_vzda(monkeypatch, tmp_path):
    """`abort` sa pýta až po získaní zámku: kto čakal, kým iné vlákno
    dopošle svoju hlášku, a medzitým sa zaplo počúvanie, nepošle nič."""
    import threading
    cache, odoslane = _falosny_edge(monkeypatch, tmp_path)
    cache._lock = _ZamokSHlasenim()
    stav = {"pocuva": False}
    vysledok = []

    cache._lock._zamok.acquire()     # iné vlákno práve posiela svoju hlášku
    b = threading.Thread(target=lambda: vysledok.append(
        cache.ensure("Jaw", "v", 0, abort=lambda: stav["pocuva"])))
    b.start()
    assert cache._lock.caka.wait(5)
    stav["pocuva"] = True            # hra sa rozbehla, kým B čakal
    cache._lock._zamok.release()
    b.join(5)
    assert not b.is_alive()
    assert vysledok == [None] and odoslane == [], "nová požiadavka nezačala"

    # Bez počúvania sa pošle normálne; hotová hláška sa vráti aj počas neho.
    stav["pocuva"] = False
    cesta = cache.ensure("Jaw", "v", 0, abort=lambda: stav["pocuva"])
    assert cesta and odoslane == [("Jaw", "v")]
    stav["pocuva"] = True
    assert cache.ensure("Jaw", "v", 0, abort=lambda: True) == cesta
    assert len(odoslane) == 1


def test_druha_priprava_cakajuca_na_zamku_pocas_hry_nic_neposle(
        monkeypatch, tmp_path):
    """Scenár overovateľa: hráč zmení hlas (vlákno A posiela 1. hlášku),
    hneď znova (vlákno B čaká na zámku cache), potom sa spustí hra.
    Keď A dopošle, B nové požiadavky na Microsoft nezačne."""
    import threading
    realne_vlakno = threading.Thread
    app_mod = _app()
    a = _atrapa_pripravy(app_mod, monkeypatch, pocuva=False)
    a.log_threadsafe = lambda *x: None
    a_posiela, pusti_a = threading.Event(), threading.Event()

    def pri_odoslani(poradie):
        if poradie == 1:             # prvá hláška vlákna A "letí"
            a_posiela.set()
            assert pusti_a.wait(5)

    a.edge_cache, odoslane = _falosny_edge(monkeypatch, tmp_path, pri_odoslani)
    a.edge_cache._lock = _ZamokSHlasenim()

    a.pregenerate()                              # prvá zmena hlasu -> A
    vlakno_a = realne_vlakno(target=a.vlakna[0]["target"])
    vlakno_a.start()
    assert a_posiela.wait(5)

    a.edge_cache._lock.caka.clear()
    a.edge_voice_id = "en-US-AvaNeural"          # druhá zmena hlasu -> B
    a.pregenerate()
    assert len(a.vlakna) == 2
    vlakno_b = realne_vlakno(target=a.vlakna[1]["target"])
    vlakno_b.start()
    assert a.edge_cache._lock.caka.wait(5), "B čaká na zámku"

    a.listening = True                           # hra sa spustila
    pusti_a.set()
    vlakno_a.join(5)
    vlakno_b.join(5)
    assert not vlakno_a.is_alive() and not vlakno_b.is_alive()

    assert odoslane == [("Breathe", "en-GB-SoniaNeural")], \
        "počas počúvania nezačala žiadna nová požiadavka"
    assert a.ui == [a.pregenerate], "zvyšok odovzdá `pregenerate`"
    a.ui[0]()
    assert a._pregen_po_hre is True and len(a.vlakna) == 2


def test_posledna_hlaska_vzdana_na_zamku_nie_je_chyba(monkeypatch):
    """Keď sa na zámku vzdá až posledná hláška, zvyšok tiež odloží
    `pregenerate` - stav nehlási „pripravené len čiastočne“."""
    app_mod = _app()
    a = _atrapa_pripravy(app_mod, monkeypatch, pocuva=False)
    a.log_threadsafe = lambda *x: None
    volania = []

    def ensure(text, voice, rate, abort=None):
        volania.append(text)
        if len(volania) == 1:
            return "hotova.mp3"
        a.listening = True           # kým čakala na zámku, hra sa spustila
        assert abort is not None and abort()
        return None

    a.edge_cache.ensure = ensure
    a.pregenerate()
    a.vlakna[0]["target"]()
    assert volania == ["Breathe", "Jaw"]
    assert a.ui == [a.pregenerate]
    assert i18n.tr("edge.partial", ok=1, total=2) not in a.stavy


def test_rucna_zmena_mimo_pocuvania_je_hned(monkeypatch):
    app_mod = _app()
    a = _atrapa_pripravy(app_mod, monkeypatch, pocuva=False)
    a.pregenerate()
    assert len(a.vlakna) == 1 and a._pregen_po_hre is False


# --------------------------------------------------------------------------
# Zvuky: nainštalovaná appka ich kopíruje z balíka, nesťahuje
# --------------------------------------------------------------------------

def _vsetky_zvuky(sfx_assets):
    return [(pack, key, info) for pack, zvuky in sfx_assets.SOUND_LIBRARY.items()
            for key, info in zvuky.items()]


def test_nainstalovana_appka_kopiruje_pribalene_zvuky(tmp_path, monkeypatch):
    import sfx_assets
    balik = tmp_path / "meipass"
    data = tmp_path / "appdata" / "sounds"
    for pack, _key, info in _vsetky_zvuky(sfx_assets):
        ciel = balik / "assets" / "sounds" / pack / info["file"]
        ciel.parent.mkdir(parents=True, exist_ok=True)
        ciel.write_bytes(b"RIFF" + pack.encode() + info["file"].encode())
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(balik), raising=False)
    monkeypatch.setattr(sfx_assets, "SOUNDS_DIR", str(data))

    def siet(*_a, **_k):
        raise AssertionError("pribalený zvuk sa nemá sťahovať")
    monkeypatch.setattr(sfx_assets, "_try_download", siet)
    for _pack, _key, info in _vsetky_zvuky(sfx_assets):
        monkeypatch.setitem(info, "synth", siet)

    priebeh = []
    sfx_assets.ensure_assets(progress=lambda d, t: priebeh.append((d, t)))
    for pack, _key, info in _vsetky_zvuky(sfx_assets):
        cesta = data / pack / info["file"]
        assert cesta.read_bytes() == b"RIFF" + pack.encode() + info["file"].encode()
    celkom = len(_vsetky_zvuky(sfx_assets))
    assert priebeh[-1] == (celkom, celkom)
    assert sfx_assets.missing_count() == 0


def test_bez_pribaleneho_zvuku_ostava_stiahnutie_a_synteza(tmp_path, monkeypatch):
    import sfx_assets
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "prazdny"), raising=False)
    monkeypatch.setattr(sfx_assets, "SOUNDS_DIR", str(tmp_path / "data"))
    stiahnute, syntetizovane = [], []

    def stiahni(url, path, expected_sha256=None, timeout=4.0):
        stiahnute.append(url)
        raise OSError("offline")
    monkeypatch.setattr(sfx_assets, "_try_download", stiahni)
    for _pack, _key, info in _vsetky_zvuky(sfx_assets):
        monkeypatch.setitem(info, "synth", lambda path: syntetizovane.append(path))

    sfx_assets.ensure_assets()
    s_url = [i for _p, _k, i in _vsetky_zvuky(sfx_assets) if i.get("download_url")]
    assert len(stiahnute) == len(s_url)
    assert len(syntetizovane) == len(_vsetky_zvuky(sfx_assets))


def test_zo_zdrojakov_sa_nic_nekopiruje(monkeypatch):
    import sfx_assets
    monkeypatch.delattr(sys, "frozen", raising=False)
    _pack, _key, info = _vsetky_zvuky(sfx_assets)[0]
    assert sfx_assets._bundled_path(_pack, info) is None


def test_build_bali_zvuky():
    """Bez zvukov v balíku by nainštalovaná appka opäť sťahovala z GitHubu."""
    spec = _read("Dandurf.spec")
    assert "('assets', 'assets')" in spec or "sounds" in spec
