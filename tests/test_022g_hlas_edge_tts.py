# -*- coding: utf-8 -*-
"""0.2.2: prirodzeny hlas po odmietnuti Microsoftom (HTTP 403, november 2026).

PRECO: Microsoft od novembra 2026 odmieta edge-tts starsi ako 7.3.1
(odmietnuty handshake WebSocketu, "Invalid response status"). Prirodzeny
hlas potom mlci a pripomienky hovori hlas z Windows. Novy build by to
neopravil: requirements.txt mal holy "edge-tts" a build_all.ps1 instaloval
zavislosti len ked nejaky modul CHYBAL - stara verzia v PC ostala navzdy.
A zlyhanie islo len do dennika v okne, nie do logs/app.log.

Co strazi tento test:
  * requirements.txt ma minimum edge-tts (jediny zdroj) a ostatne riadky
    ostali,
  * build_all.ps1 minimum cita z requirements.txt (tym istym vzorom ako
    check_before_run.py), porovna ho s nainstalovanou verziou ciselne a pri
    starej verzii spusti `pip install -r requirements.txt`; zlyhanie
    zastavi build (Fail),
  * kontrola verzie z build_all.ps1 naozaj funguje (falosne dist-info v
    tmp_path, bez siete a bez instalacie),
  * zlyhana priprava hlasu zapise raz za druh chyby jeden riadok do app.log
    - druh, kratku chybu bez ciest a verziu edge-tts,
  * skutocna aiohttp.WSServerHandshakeError (403) cez skutocny edge-tts a
    `EdgeTTSCache.ensure` je "refused" (bez siete) a URL sluzby v kratkej
    chybe ostane URL - orezavanie ciest z "wss://" nerobi "wsv1?...",
  * veta o odmietnuti (stav aj dennik) vo vsetkych 11 jazykoch povie, ze
    pri trvalom odmietnuti treba novu verziu z oficialneho GitHubu
    (Releases), bez URL, s nezmenenymi {placeholdermi}.

Synteticke data: cesta C:\\Users\\Hrac, verzie 7.2.8 / 7.3.1 - nic z PC.
"""
import os
import re
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app_audio  # noqa: E402
import i18n  # noqa: E402
from audio_engine import EDGE_CHYBA_ODMIETNUTE, EDGE_CHYBA_OFFLINE  # noqa: E402

import test_022e_hlas_chyby as chyby  # noqa: E402

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = i18n.STRINGS


def _read(meno):
    with open(os.path.join(KOREN, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _cisla(verzia):
    return tuple(int(c) for c in re.findall(r"\d+", verzia))


def _minimum_z_requirements():
    zhody = re.findall(r"^\s*edge-tts\s*>=\s*([0-9.]+)\s*$", _read("requirements.txt"), re.M)
    assert len(zhody) == 1, zhody
    return zhody[0]


def _vzor_z_buildu():
    zhoda = re.search(r"^\$edgeMinVzor = '([^']+)'$", _read("build_all.ps1"), re.M)
    assert zhoda, "build_all.ps1 nema $edgeMinVzor"
    return zhoda.group(1)


def _kontrola_z_buildu():
    zhoda = re.search(r'^\$edgeKontrola = "([^"]+)"$', _read("build_all.ps1"), re.M)
    assert zhoda, "build_all.ps1 nema $edgeKontrola"
    return zhoda.group(1)


# --------------------------------------------------------------------------
# requirements.txt
# --------------------------------------------------------------------------

def test_requirements_ma_minimum_edge_tts():
    assert _cisla(_minimum_z_requirements()) >= (7, 3, 1)
    riadky = [r.strip() for r in _read("requirements.txt").splitlines()
              if r.strip() and not r.lstrip().startswith("#")]
    assert "edge-tts" not in riadky, "holy edge-tts by nechal staru verziu"
    # ostatne zavislosti ostali, ako boli
    assert [r for r in riadky if not r.startswith("edge-tts")] == [
        "pyttsx3", "comtypes", "pystray", "pillow", "customtkinter", "numpy",
        "pygame-ce", "psutil"]


# --------------------------------------------------------------------------
# build_all.ps1
# --------------------------------------------------------------------------

def test_build_cita_minimum_z_requirements_tym_istym_vzorom():
    vzor = _vzor_z_buildu()
    # PowerShell -match je bez ohladu na velkost pismen
    najdene = [z.group(1) for r in _read("requirements.txt").splitlines()
               if (z := re.match(vzor, r, re.I))]
    assert najdene == [_minimum_z_requirements()]
    assert re.match(vzor, "edge-tts >= 7.3.1  # komentar", re.I).group(1) == "7.3.1"
    assert not re.match(vzor, "edge-tts", re.I)
    skript = _read("build_all.ps1")
    assert "Get-Content 'requirements.txt'" in skript
    assert "$riadok -match $edgeMinVzor" in skript
    # jediny zdroj: ziadne cislo verzie natvrdo v skripte
    assert _minimum_z_requirements() not in skript
    # ta ista poziadavka v predbeznej kontrole
    assert vzor in _read("check_before_run.py")


def test_build_pri_starej_verzii_spusti_pip_a_chybu_zastavi():
    skript = _read("build_all.ps1")
    cyklus = skript.index("foreach ($module in @('edge_tts'")
    kontrola = skript.index("$edgeMinVzor = ")
    pyinstaller = skript.index("Invoke-Py '-m' 'PyInstaller' '--version'")
    assert cyklus < kontrola < pyinstaller, "kontrola ide po cykle, pred PyInstallerom"
    blok = skript[kontrola:pyinstaller]
    assert "Invoke-Py '-c' $edgeKontrola $edgeMin" in blok
    stara = blok.index("if ($LASTEXITCODE -ne 0) {")
    po_starej = blok[stara:]
    assert po_starej.index("Invoke-Py '-m' 'pip' 'install' '-r' 'requirements.txt'") \
        < po_starej.index("Fail \"pip install zlyhal")
    # po instalacii sa verzia overi znova - stale stara = Fail
    assert po_starej.count("Invoke-Py '-c' $edgeKontrola $edgeMin") == 1
    assert "Fail \"edge-tts je stale" in po_starej
    assert "Fail \"requirements.txt nema minimum pre edge-tts" in blok
    # ziadne 'packaging' (nemusi byt nainstalovany), ziadny upgrade vsetkeho
    assert "packaging" not in _kontrola_z_buildu()
    assert "'--upgrade'" not in skript and "'-U'" not in skript
    # PowerShell 5.1 skript bez BOM cita ako ANSI - ostava cisto ASCII
    assert skript.isascii()


def _dist_info(koren, verzia):
    priecinok = koren / ("edge_tts-%s.dist-info" % verzia)
    priecinok.mkdir(parents=True)
    (priecinok / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: edge-tts\nVersion: %s\n" % verzia, encoding="ascii")


@pytest.mark.parametrize("nainstalovana, minimum, kod", [
    ("7.2.8", "7.3.1", 1),
    ("7.3.1", "7.3.1", 0),
    ("7.10.0", "7.3.1", 0),          # ciselne, nie ako text ("7.10" < "7.3")
    ("8.0", "7.3.1", 0),
    ("7.3", "7.3.1", 1),
    (None, "7.3.1", 1),              # nenainstalovany = treba pip
])
def test_kontrola_verzie_z_buildu_naozaj_porovna(tmp_path, nainstalovana, minimum, kod):
    """Ten isty kod, ktory spusti build_all.ps1 (`py -c`). `-S` vypne
    site-packages - vidno len falosne dist-info z tmp_path."""
    site = tmp_path / "site"
    site.mkdir()
    if nainstalovana:
        _dist_info(site, nainstalovana)
    env = dict(os.environ, PYTHONPATH=str(site), PYTHONDONTWRITEBYTECODE="1")
    beh = subprocess.run([sys.executable, "-S", "-c", _kontrola_z_buildu(), minimum],
                         cwd=str(tmp_path), env=env, capture_output=True, text=True,
                         timeout=60)
    assert beh.returncode == kod, beh.stderr
    assert beh.stdout.strip() == (nainstalovana or "?")


# --------------------------------------------------------------------------
# app.log
# --------------------------------------------------------------------------

class _Log:
    def __init__(self):
        self.riadky = []

    def warning(self, fmt, *args):
        self.riadky.append(fmt % args)


def test_zlyhana_priprava_zapise_do_app_log_raz_za_druh(monkeypatch):
    log = _Log()
    monkeypatch.setattr(app_audio, "app_log", log)
    monkeypatch.setattr(app_audio, "_verzia_edge_tts", lambda: "7.2.8")
    a = chyby._atrapa(monkeypatch)
    chyby._zlyha(a, (EDGE_CHYBA_ODMIETNUTE, chyby.WSServerHandshakeError(403)))
    assert len(log.riadky) == 1 and len(a.denn) == 1
    riadok = log.riadky[0]
    assert "(refused)" in riadok and "0/3" in riadok
    assert "edge-tts 7.2.8" in riadok and "Invalid response status 403" in riadok
    assert riadok.isascii(), "app.log po slovensky bez diakritiky"
    # ta ista chyba znova: ani dennik, ani app.log
    a.ui.clear()
    chyby._zlyha(a, (EDGE_CHYBA_ODMIETNUTE, chyby.WSServerHandshakeError(403)))
    assert len(log.riadky) == 1 and len(a.denn) == 1
    # iny druh = novy riadok
    a.ui.clear()
    chyby._zlyha(a, (EDGE_CHYBA_OFFLINE, TimeoutError("vyprsal cas")))
    assert len(log.riadky) == 2 and "(offline)" in log.riadky[1]
    assert "vyprsal cas" in log.riadky[1]


def test_riadok_v_app_log_je_bez_cesty(monkeypatch):
    log = _Log()
    monkeypatch.setattr(app_audio, "app_log", log)
    a = chyby._atrapa(monkeypatch)
    chyby._zlyha(a, ("other", OSError(
        "zapis zlyhal: 'C:\\Users\\Hrac\\AppData\\Roaming\\Zanshin\\audio\\x.mp3'")))
    assert len(log.riadky) == 1
    assert "Hrac" not in log.riadky[0] and "AppData" not in log.riadky[0]
    assert "x.mp3" in log.riadky[0]


def test_app_log_ide_cez_spolocny_logger():
    import app_spolocne
    assert app_audio.app_log is app_spolocne.app_log
    from _zdroj_appky import zdroj_metody
    telo = zdroj_metody("_edge_priprava_zlyhala")
    # riadok do app.log az za poistkou "raz za druh"
    assert telo.index("self._edge_chyba_v_denniku = druh") < telo.index("app_log.warning(")


# --------------------------------------------------------------------------
# Skutocne odmietnutie: aiohttp + edge-tts, bez siete
# --------------------------------------------------------------------------
#
# Atrapy vyssie (test_022e_hlas_chyby) maju vlastne triedy. Tu ide SKUTOCNA
# aiohttp.WSServerHandshakeError, postavena ako v aiohttp/client.py, cez
# SKUTOCNY edge-tts (jeho druhy pokus po 403 s upravou hodin podla hlavicky
# Date) a `EdgeTTSCache.ensure`. `ws_connect` je podstrceny - na siet sa
# nejde. Overene 2026-11: edge-tts 7.2.8 dostava od Microsoftu presne toto.

def _skutocne_odmietnutie(aiohttp, status=403, date=True):
    from multidict import CIMultiDict, CIMultiDictProxy
    from yarl import URL
    url = URL("wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/"
              "edge/v1?TrustedClientToken=X")
    hlavicky = CIMultiDict({"Date": "Sun, 15 Nov 2026 10:00:00 GMT"} if date else {})
    info = aiohttp.RequestInfo(url, "GET", CIMultiDictProxy(CIMultiDict()), url)
    return aiohttp.WSServerHandshakeError(info, (), message="Invalid response status",
                                          status=status, headers=CIMultiDictProxy(hlavicky))


@pytest.mark.parametrize("date, spojeni, trieda", [
    (True, 2, "WSServerHandshakeError"),   # druhy pokus po uprave hodin tiez 403
    (False, 1, "SkewAdjustmentError"),     # bez Date: edge-tts vlastna chyba "from" 403
])
def test_skutocny_403_cez_edge_tts_je_odmietnutie(tmp_path, monkeypatch, date, spojeni, trieda):
    aiohttp = pytest.importorskip("aiohttp")
    edge_tts = pytest.importorskip("edge_tts")
    import asyncio

    import audio_engine
    from edge_tts import drm

    volania = []

    class _Odmietnute:
        def __init__(self, exc):
            self.exc = exc

        async def __aenter__(self):
            raise self.exc

        async def __aexit__(self, *_a):
            return False

    def _ws_connect(_session, url, *_a, **_k):
        volania.append(url)
        return _Odmietnute(_skutocne_odmietnutie(aiohttp, 403, date))

    monkeypatch.setattr(aiohttp.ClientSession, "ws_connect", _ws_connect)
    monkeypatch.setattr(drm.DRM, "clock_skew_seconds", drm.DRM.clock_skew_seconds)
    monkeypatch.setattr(audio_engine, "TTS_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(audio_engine, "EDGE_AVAILABLE", True)
    monkeypatch.setattr(audio_engine, "edge_tts", edge_tts, raising=False)
    monkeypatch.setattr(audio_engine, "asyncio", asyncio, raising=False)

    cache = audio_engine.EdgeTTSCache(log=lambda *_a: None)
    assert cache.ensure("Grounded", "en-GB-SoniaNeural", 0) is None
    druh, exc = cache.posledna_chyba()
    assert druh == EDGE_CHYBA_ODMIETNUTE, (type(exc), exc)
    assert type(exc).__name__ == trieda
    assert len(volania) == spojeni and all(u.startswith("wss://") for u in volania)
    assert os.listdir(tmp_path) == [], ".part po odmietnuti nesmie ostat"

    # ta ista chyba az po stav, dennik a app.log
    log = _Log()
    monkeypatch.setattr(app_audio, "app_log", log)
    a = chyby._atrapa(monkeypatch)
    chyby._zlyha(a, (druh, exc))
    assert a.stavy[-1] == i18n.tr("edge.partial_refused", ok=0, total=3)
    assert len(a.denn) == 1 and len(log.riadky) == 1
    assert "(refused)" in log.riadky[0]
    if date:
        assert "403, message='Invalid response status'" in log.riadky[0]
        # URL sluzby ostane URL - nie "wsv1?..." z orezavania ciest
        assert "url='wss://speech.platform.bing.com/" in log.riadky[0]


@pytest.mark.parametrize("text, cakane", [
    ("403, message='Invalid response status', url='wss://speech.platform.bing.com/edge/v1?T=X'",
     "403, message='Invalid response status', url='wss://speech.platform.bing.com/edge/v1?T=X'"),
    ("Cannot connect to host speech.platform.bing.com:443 ssl:default [getaddrinfo failed]",
     "Cannot connect to host speech.platform.bing.com:443 ssl:default [getaddrinfo failed]"),
    ("zapis zlyhal: 'C:\\Users\\Hrac\\AppData\\Roaming\\Zanshin\\audio\\x.mp3'",
     "zapis zlyhal: 'x.mp3'"),
    ("[Errno 2] No such file: 'C:\\\\Users\\\\Hrac\\\\audio\\\\x.mp3'",
     "[Errno 2] No such file: 'x.mp3'"),
    ("[Errno 2] No such file: '\\\\\\\\server\\\\share\\\\Hrac\\\\x.mp3'",
     "[Errno 2] No such file: 'x.mp3'"),
    ("file:///C:/Users/Hrac/x.mp3", "file:///x.mp3"),
    ("cesta \\\\?\\C:\\Users\\Hrac\\x.mp3", "cesta \\\\?\\x.mp3"),
])
def test_kratka_chyba_necha_url_sluzby_a_oreze_cesty(text, cakane):
    assert app_audio._kratka_chyba(RuntimeError(text)) == cakane


def test_verzia_edge_tts_nikdy_nevyhodi(monkeypatch):
    from importlib import metadata

    def _chyba(_meno):
        raise metadata.PackageNotFoundError("edge-tts")
    monkeypatch.setattr(metadata, "version", _chyba)
    assert app_audio._verzia_edge_tts() == "?"
    monkeypatch.setattr(metadata, "version", lambda _meno: "7.3.1")
    assert app_audio._verzia_edge_tts() == "7.3.1"


# --------------------------------------------------------------------------
# Texty o odmietnuti
# --------------------------------------------------------------------------

PRIPOMIENKA = {"sk": "pripomien", "cs": "připomín", "en": "cue", "ja": "合図", "zh": "提示",
               "ru": "подсказ", "bg": "подсказ", "es": "aviso", "pt": "aviso",
               "de": "Hinweis", "fr": "rappel"}
OFICIALNY = {"sk": "oficiáln", "cs": "oficiáln", "en": "official", "ja": "公式", "zh": "官方",
             "ru": "официальн", "bg": "официалн", "es": "oficial", "pt": "oficial",
             "de": "offiziell", "fr": "officiel"}
KLUCE = ("edge.partial_refused", "log.edge_failed_refused")


def _placeholdery(text):
    return sorted(re.findall(r"\{[a-z_]+\}", text))


@pytest.mark.parametrize("kluc", KLUCE)
def test_odmietnutie_posle_po_novu_verziu_vo_vsetkych_jazykoch(kluc):
    en = S[kluc]["en"]
    assert "outdated" in en and "official GitHub (Releases)" in en
    assert set(S[kluc]) == set(i18n.LANGUAGES)
    for jazyk in i18n.LANGUAGES:
        text = S[kluc][jazyk]
        assert _placeholdery(text) == _placeholdery(en), (kluc, jazyk)
        assert "GitHub" in text and "Releases" in text, (kluc, jazyk)
        assert OFICIALNY[jazyk] in text, (kluc, jazyk)
        assert "Zanshin" in text, (kluc, jazyk)
        # bez URL - ziadna veta o hlase ju doteraz nemala
        assert not re.search(r"https?:|github\.com|www\.", text), (kluc, jazyk)
        # stale aj rada "skus neskor / prepni Zdroj hlasu na Windows"
        assert "Windows" in text, (kluc, jazyk)
        zdroj = i18n.tr_lang(jazyk, "settings.engine")
        assert zdroj.lower() in text.lower(), (kluc, jazyk)
        assert "\\u" not in text, (kluc, jazyk)


def test_dennik_hovori_slovnikom_a_povie_kto_hovori_dovtedy():
    for jazyk in i18n.LANGUAGES:
        text = S["log.edge_failed_refused"][jazyk]
        assert PRIPOMIENKA[jazyk] in text, jazyk
        # odmietnuta veta v dennikoch: zvysok povie hlas z Windows (ako offline)
        assert text.count("Windows") >= 2, jazyk
    assert S["edge.partial_refused"]["sk"].startswith("! hlas má len {ok}/{total} pripomienok")
    assert "dovtedy zvyšok povie hlas z Windows" in S["log.edge_failed_refused"]["sk"]
    assert "until then the Windows voice covers the rest" in S["log.edge_failed_refused"]["en"]


def test_texty_sa_skladaju_bez_chyby():
    for jazyk in i18n.LANGUAGES:
        stav = i18n.tr_lang(jazyk, "edge.partial_refused", ok=2, total=4)
        assert "2/4" in stav and "{" not in stav, jazyk
        riadok = i18n.tr_lang(jazyk, "log.edge_failed_refused", retry="R", page="P",
                              cmd="C", err="E")
        assert "{" not in riadok, jazyk
