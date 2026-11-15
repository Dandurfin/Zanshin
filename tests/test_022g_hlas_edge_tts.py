# -*- coding: utf-8 -*-
"""0.3: natural voice after Microsoft's rejection (HTTP 403, November 2026).

WHY: since November 2026 Microsoft rejects edge-tts older than 7.3.1
(rejected WebSocket handshake, "Invalid response status"). The natural
voice then goes silent and the cues are spoken by the Windows voice. A new
build would not fix it: requirements.txt had a bare "edge-tts" and
build_all.ps1 installed dependencies only when some module was MISSING -
the old version stayed on the PC forever. And the failure went only to the
journal in the window, not to logs/app.log.

The author's decision (2026-11-15): the build downloads the newest edge-tts
on EVERY run - when Microsoft changes something again, even a build made
after a month with no release gets the fix. A version cap (it was <8) is
deliberately absent - both reviewers of the previous change showed it can
block exactly that fix. Compatibility is therefore checked functionally:
after the upgrade the build tries the API (no network) and one test word,
and the app (the Update voice button, hlas_kniznica.py) does the same with
every downloaded version.

What this test guards:
  * requirements.txt has edge-tts with a minimum and WITHOUT a cap (the
    single source) and the other lines stayed,
  * build_all.ps1 reads the whole requirement and the minimum from
    requirements.txt (with the same pattern as check_before_run.py) and on
    every build runs `pip install --upgrade` ONLY for this requirement (with
    --retries/--timeout); without internet it continues only when the
    installed edge-tts meets the minimum, otherwise it stops the build
    (Fail),
  * after the upgrade the build tries the edge-tts API without network
    (`py -c`: import, Communicate('Zanshin', hlas, rate='+0%'), async save)
    - a failure stops the build (Fail) with the exact pip command back to
    the last working one; then (only with internet) a test word into %TEMP%
    - a failure is a loud YELLOW warning, not Fail (the exe also works with
    the Windows voice and the app fixes the voice itself); without internet
    the word is skipped,
  * the real block from build_all.ps1 in powershell.exe with a fake pip and
    a fake edge_tts (success, no internet, failure, changed API, rejected
    word) does exactly that - each case separately,
  * the same block with the REAL Invoke-Py via python.bat (cmd.exe, a path
    with a space) delivers the requirement and both `py -c` lines into
    sys.argv whole, and no file appears in the build folder (a bare '<' and
    '>' would be taken by cmd as redirection, '%' as a variable),
  * the version check from build_all.ps1 really works (fake dist-info in
    tmp_path, no network and no install), the API test passes with the real
    installed edge-tts (no network - sockets are forbidden),
  * a failed voice preparation writes one line to app.log once per error
    kind - the kind, a short error without paths and the edge-tts version,
  * a real aiohttp.WSServerHandshakeError (403) through the real edge-tts and
    `EdgeTTSCache.ensure` is "refused" (no network), and the service URL in
    the short error stays a URL - trimming paths from "wss://" does not make
    "wsv1?...",
  * the rejection sentence (status and journal) in all 11 languages says
    that on a permanent rejection a new version from the official GitHub
    (Releases) is needed, without a URL, with unchanged {placeholders}.

Synthetic data: path C:\\Users\\Hrac, versions 7.2.8 / 7.3.1 - nothing
from the PC.
"""
import json
import os
import re
import shutil
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


def _edge_riadok():
    """(condition, minimum) from the edge-tts>=X line in requirements.txt -
    without a cap. Its own strict pattern - independent of the build's."""
    zhody = re.findall(r"^\s*edge-tts\s*(>=\s*([0-9]+(?:\.[0-9]+)*))\s*$",
                       _read("requirements.txt"), re.M)
    assert len(zhody) == 1, zhody
    return zhody[0]


def _minimum_z_requirements():
    return _edge_riadok()[1]


def _vzor_z_buildu():
    zhoda = re.search(r"^\$edgeMinVzor = '([^']+)'$", _read("build_all.ps1"), re.M)
    assert zhoda, "build_all.ps1 nema $edgeMinVzor"
    return zhoda.group(1)


def _kontrola_z_buildu():
    zhoda = re.search(r'^\$edgeKontrola = "([^"]+)"$', _read("build_all.ps1"), re.M)
    assert zhoda, "build_all.ps1 nema $edgeKontrola"
    return zhoda.group(1)


def _py_c_z_buildu(meno):
    """Python for `py -c` from the `$meno = "..."` line in build_all.ps1."""
    zhody = re.findall(r'^\s*\$%s = "([^"]+)"$' % meno, _read("build_all.ps1"), re.M)
    assert len(zhody) == 1, "build_all.ps1 nema prave jeden $%s" % meno
    return zhody[0]


def _api_z_buildu():
    return _py_c_z_buildu("edgeApi")


def _slovo_z_buildu():
    return _py_c_z_buildu("edgeSlovo")


# --------------------------------------------------------------------------
# requirements.txt
# --------------------------------------------------------------------------

def test_requirements_ma_minimum_edge_tts_bez_stropu():
    podmienka, minimum = _edge_riadok()
    assert _cisla(minimum) >= (7, 3, 1)
    req = _read("requirements.txt")
    riadky = [r.strip() for r in req.splitlines()
              if r.strip() and not r.lstrip().startswith("#")]
    edge = [r for r in riadky if r.startswith("edge-tts")]
    # without a cap: a fix from a new major version must reach the build
    assert edge == ["edge-tts" + podmienka] and "<" not in edge[0] and "," not in edge[0]
    assert "edge-tts" not in riadky, "holy edge-tts by nechal staru verziu"
    # the comment says why and who checks compatibility instead of a cap
    komentar = " ".join(r.lstrip("# ").strip() for r in req.splitlines()
                        if r.lstrip().startswith("#"))
    assert "There is deliberately no cap" in komentar
    assert "tries its API" in komentar and "test word" in komentar
    assert "Update voice" in komentar and "keeps it only if it works" in komentar
    # other dependencies stayed as they were (no versions - build leaves them)
    assert [r for r in riadky if not r.startswith("edge-tts")] == [
        "pyttsx3", "comtypes", "pystray", "pillow", "customtkinter", "numpy",
        "pygame-ce", "psutil"]


# --------------------------------------------------------------------------
# build_all.ps1
# --------------------------------------------------------------------------

def _blok_z_buildu():
    """edge-tts block of build_all.ps1: from $edgeMinVzor to PyInstaller."""
    skript = _read("build_all.ps1")
    return skript[skript.index("$edgeMinVzor = "):
                  skript.index("Invoke-Py '-m' 'PyInstaller' '--version'")]


def test_build_cita_poziadavku_z_requirements_tym_istym_vzorom():
    vzor = _vzor_z_buildu()
    podmienka, minimum = _edge_riadok()
    # PowerShell -match is case-insensitive; group 1 = the whole condition
    # (goes to pip), group 2 = the minimum (version check)
    najdene = [(z.group(1).strip(), z.group(2))
               for r in _read("requirements.txt").splitlines()
               if (z := re.match(vzor, r, re.I))]
    assert najdene == [(podmienka, minimum)]
    assert podmienka == ">=%s" % minimum
    # the pattern still reads a temporary cap (build advice, changed API) whole
    for riadok, cakane in (
            ("edge-tts >= 7.3.1, <8  # komentar", (">= 7.3.1, <8", "7.3.1")),
            ("edge-tts>=7.10.0,<8", (">=7.10.0,<8", "7.10.0")),
            ("edge-tts>=7.3.1,<8; sys_platform == 'win32'", (">=7.3.1,<8", "7.3.1")),
            ("edge-tts>=7.3.1", (">=7.3.1", "7.3.1"))):
        z = re.match(vzor, riadok, re.I)
        assert (z.group(1).strip(), z.group(2)) == cakane, riadok
    for bez_minima in ("edge-tts", "edge-tts<8", "# edge-tts>=7.3.1"):
        assert not re.match(vzor, bez_minima, re.I), bez_minima
    # the whole file at once (check_before_run.py): no spill to the next line
    z = re.search(vzor, "edge-tts>=7.3.1,<8\ncustomtkinter\n", re.I | re.M)
    assert z.group(1) == ">=7.3.1,<8"
    skript = _read("build_all.ps1")
    assert "Get-Content 'requirements.txt'" in skript
    assert "$riadok -match $edgeMinVzor" in skript
    assert "$edgePoziadavka = 'edge-tts ' + $Matches[1].Trim()" in skript
    assert "$edgeMin = $Matches[2]" in skript
    # single source: no version number or cap hard-coded in the script (the
    # advice "back to the last working one" is built from variables)
    assert minimum not in skript
    assert not re.search(r"edge-tts\s*(?:[<>=!~]=?|,)\s*\d", skript)
    # the same requirement in the pre-check, the minimum is group 2 there too
    kontrola = _read("check_before_run.py")
    assert vzor in kontrola
    assert "_treba = _minimum.group(2)" in kontrola


def test_build_vzdy_zdvihne_len_edge_tts_a_bez_internetu_rozhodne_minimum():
    skript = _read("build_all.ps1")
    cyklus = skript.index("foreach ($module in @('edge_tts'")
    kontrola = skript.index("$edgeMinVzor = ")
    pyinstaller = skript.index("Invoke-Py '-m' 'PyInstaller' '--version'")
    assert cyklus < kontrola < pyinstaller, "kontrola ide po cykle, pred PyInstallerom"
    blok = _blok_z_buildu()
    # every build: upgrade ONLY the edge-tts requirement from requirements.txt
    upgrade = ("Invoke-Py '-m' 'pip' 'install' '--upgrade' '--retries' '1' "
               "'--timeout' '15' $edgePoziadavka")
    riadky = [r.strip() for r in skript.splitlines()]
    assert [r for r in riadky if "'--upgrade'" in r] == [upgrade]
    # no short flag, no other strategy (eager would upgrade all dependencies)
    assert "'-U'" not in skript and "'--upgrade-strategy'" not in skript
    # -r requirements.txt only in the missing-modules loop, without --upgrade
    s_r = [r for r in riadky if "'-r'" in r]
    assert s_r == ["Invoke-Py '-m' 'pip' 'install' '-r' 'requirements.txt'"]
    assert skript.index(s_r[0]) < kontrola
    # pip is OK even without internet when the installed one satisfies - hence
    # the index probe (--dry-run installs nothing), only after a successful pip
    sonda = ("Invoke-Py '-m' 'pip' 'install' '--dry-run' '--ignore-installed' "
             "'--no-deps' '--quiet' '--retries' '1' '--timeout' '15' "
             "$edgePoziadavka 2>&1 | Out-Null")
    assert blok.count(sonda) == 1
    assert blok.index(upgrade) < blok.index("if ($edgePip -eq 0) {") < blok.index(sonda)
    # then the version check: below minimum = Fail (with or without internet)
    over = blok.index("$edgeVerzia = \"$(Invoke-Py '-c' $edgeKontrola $edgeMin)\".Trim()")
    assert blok.count("Invoke-Py '-c' $edgeKontrola $edgeMin") == 1
    assert blok.index(sonda) < over
    po = blok[over:]
    bez_netu = po.index("if ($edgePip -ne 0) {\n    Write-Host \"Couldn't")
    pod_minimom = po[po.index("if ($LASTEXITCODE -ne 0) {"):bez_netu]
    assert pod_minimom.count("Fail \"") == 2
    assert "check your internet connection" in pod_minimom and "wouldn't work" in pod_minimom
    # without internet (pip or probe failed) and minimum met: yellow, continues
    api = po.index("$edgeApi = ")
    zlte = po[bez_netu:api]
    assert "Couldn't check for the newest edge-tts (no internet?)" in zlte and "-ForegroundColor Yellow" in zlte
    assert "Fail" not in zlte
    # the exe's version is always in the build log - only after the API test
    assert po.index('Write-Host "edge-tts $edgeVerzia goes into the build') > api
    assert "Fail \"requirements.txt has no minimum for edge-tts" in blok
    # no 'packaging' (it may not be installed)
    assert "packaging" not in _kontrola_z_buildu()
    # PowerShell 5.1 reads a script without BOM as ANSI - it stays pure ASCII
    assert skript.isascii()


def test_py_c_riadky_prezyju_powershell_aj_cmd():
    """Both new `py -c` lines: no quotes (PowerShell 5.1 breaks them for a
    native program), no '%' (cmd.exe with Python via .bat), no '$' and no
    backtick (PowerShell would expand them in "..."), one line."""
    for kod in (_api_z_buildu(), _slovo_z_buildu(), _kontrola_z_buildu()):
        for zly in ('"', "%", "$", "`", "\n", "\t", "!"):
            assert zly not in kod, (zly, kod)
        compile(kod, "<py -c>", "exec")
    # '+0%' is built from chr(37) - just like edge_rate_str(0) in audio_engine
    from audio_engine import edge_rate_str
    assert "+0" + chr(37) == edge_rate_str(0)
    for kod in (_api_z_buildu(), _slovo_z_buildu()):
        assert "Communicate('Zanshin', 'en-GB-SoniaNeural', rate='+0' + chr(37))" in kod
        # short reason (Class: message), not a traceback, goes into the notice
        assert "sys.excepthook = lambda t, e, b: print(t.__name__ + ': ' + str(e)[:160])" in kod
    # API test makes no network call: save is only checked (async), not called
    assert ".save(" not in _api_z_buildu()
    assert "inspect.iscoroutinefunction(getattr(k, 'save', None))" in _api_z_buildu()
    # test word: file from the argument, time limit, empty sound = failure
    slovo = _slovo_z_buildu()
    assert "p = sys.argv[1]" in slovo and ".save(p), 30)" in slovo
    assert "asyncio.run(asyncio.wait_for(" in slovo and "print('empty audio')" in slovo


def test_build_vyskusa_api_a_skusobne_slovo():
    blok = _blok_z_buildu()
    riadky = [r.strip() for r in blok.splitlines()]
    # order: version check -> API (always, even without internet) -> "goes
    # into the build" -> test word (only with internet)
    over = blok.index("$edgeVerzia = \"$(Invoke-Py '-c' $edgeKontrola $edgeMin)\".Trim()")
    api = blok.index("$edgeApiDovod = \"$(Invoke-Py '-c' $edgeApi)\".Trim()")
    ide = blok.index('Write-Host "edge-tts $edgeVerzia goes into the build')
    offline = blok.index("if ($edgePip -ne 0) {\n    Write-Host \"Skipping the test word")
    slovo = blok.index("$edgeSlovoDovod = \"$(Invoke-Py '-c' $edgeSlovo $edgeSubor)\".Trim()")
    assert over < api < ide < offline < slovo
    assert blok.count("Invoke-Py '-c' $edgeApi") == 1
    assert blok.count("Invoke-Py '-c' $edgeSlovo") == 1
    # API fails = Fail (both cases), with the exact pip command back
    zlyhane_api = blok[api:ide]
    assert zlyhane_api.count("Fail (") == 2
    assert "has changed so that Zanshin can't use it ($edgeApiDovod)" in zlyhane_api
    assert ("$pyPrikaz -m pip install `\"$edgeSpat`\"" in zlyhane_api
            and "in requirements.txt change the edge-tts line to $edgeSpat" in zlyhane_api)
    assert "$pyPrikaz = (@($PY.Exe) + $PY.Pre) -join ' '" in riadky
    # test word: skipped without internet (yellow), otherwise a file in %TEMP%,
    # which is always deleted; a failure is a yellow warning, NOT Fail
    cast = blok[offline:]
    assert "Fail" not in cast
    assert ("$edgeSubor = Join-Path $env:TEMP ('zanshin-edge-tts-' + "
            "[guid]::NewGuid().ToString('N') + '.mp3')") in riadky
    zmaz = "Remove-Item -LiteralPath $edgeSubor -Force -ErrorAction SilentlyContinue"
    assert riadky.count(zmaz) == 1
    assert cast.index("$edgeSlovoKod = $LASTEXITCODE") < cast.index(zmaz) < cast.index(
        "if ($edgeSlovoKod -eq 0) {")
    assert 'Write-Host "natural voice verified (edge-tts $edgeVerzia)" -ForegroundColor Green' in riadky
    varovanie = cast[cast.index("} else {\n        Write-Host \"\""):]
    assert varovanie.count("-ForegroundColor Yellow") == 3
    assert "Microsoft refuses even edge-tts $edgeVerzia" in varovanie
    assert "Windows voice" in varovanie and "Update voice" in varovanie
    # with internet = the same condition as the yellow "Couldn't check" message
    assert blok.count("if ($edgePip -ne 0) {") == 3


def test_predbezna_kontrola_upozorni_na_strop():
    """A cap in requirements.txt (temporary build advice on a changed API) is
    only a warning in check_before_run.py - so it is not forgotten."""
    kontrola = _read("check_before_run.py")
    z = re.search(r'_strop = re\.search\(r"([^"]+)", _minimum\.group\(1\)\)', kontrola)
    assert z, "check_before_run.py nehlada strop v podmienke edge-tts"
    vzor_stropu, vzor = z.group(1), _vzor_z_buildu()
    for riadok, ma_strop in (("edge-tts>=7.3.1", False),
                             ("edge-tts>=7.3.1,<8", True),
                             ("edge-tts >= 7.3.1, <= 7.9", True),
                             ("edge-tts>=7.3.1,<7.4.0", True),
                             ("edge-tts>=7.3.1  # <8 neskor", False)):
        podmienka = re.match(vzor, riadok, re.I).group(1)
        assert bool(re.search(vzor_stropu, podmienka)) == ma_strop, riadok
    assert not re.search(vzor_stropu, _edge_riadok()[0]), "dnes strop nie je"
    blok = kontrola[kontrola.index("_strop = re.search"):
                    kontrola.index("_verzia = _metadata.version")]
    assert "notes.append(" in blok and "problems.append(" not in blok
    assert blok.isascii()


# --------------------------------------------------------------------------
# The real block from build_all.ps1 in powershell.exe, pip is fake
# --------------------------------------------------------------------------
#
# The REAL code of the block runs (reading requirements.txt, decisions,
# messages); Fail and Write-Host are overridden to record, Invoke-Py to a
# fake pip. All '-c' (version check, API test, test word) go to the real
# Python with `-S` over a fake dist-info and a FAKE edge_tts in tmp_path -
# like test_kontrola_verzie_z_buildu_naozaj_porovna. Nothing goes to the
# network: the real edge-tts is not even visible with -S.
# Fake pip: install returns the code from the scenario and on success
# "installs" version `po`; the probe (--dry-run) returns `sonda`. Real pip
# without internet (verified 2026-11): with a satisfying edge-tts it ends 0,
# with an old one 1.
# The fake edge_tts behaves according to FALOSNY_EDGE = "api,slovo":
#   api:   ok | konstruktor (TypeError - changed signature) | sync (save is
#          not async) | import (ImportError on import)
#   slovo: ok | 403 (writes part of the file and refuses) | prazdne (empty
#          file)
# It writes the file path for the test word to FALOSNY_ZAZNAM.

_FALOSNY_EDGE_TTS = r'''
import os

_API, _SLOVO = (os.environ.get("FALOSNY_EDGE") or "ok,ok").split(",")
if _API == "import":
    raise ImportError("falosny edge_tts: chyba zavislost aiohttp")


class Communicate:
    def __init__(self, text, voice, **kw):
        if _API == "konstruktor":
            raise TypeError("Communicate.__init__() got an unexpected keyword argument 'rate'")
        # presne volanie z buildu - aj '%' poskladane z chr(37)
        if (text, voice, kw) != ("Zanshin", "en-GB-SoniaNeural", {"rate": "+0%"}):
            raise ValueError("necakane volanie %r" % ((text, voice, kw),))

    if _API == "sync":
        def save(self, cesta):
            raise AssertionError("synchronny save sa nesmie volat")
    else:
        async def save(self, cesta):
            with open(os.environ["FALOSNY_ZAZNAM"], "a", encoding="utf-8") as fh:
                fh.write(cesta + "\n")
            with open(cesta, "wb") as fh:
                fh.write(b"" if _SLOVO == "prazdne" else b"ID3")
            if _SLOVO == "403":
                raise ConnectionError("403, message='Invalid response status'")
'''


def _falosny_edge_tts(site):
    balik = site / "edge_tts"
    balik.mkdir()
    (balik / "__init__.py").write_text(_FALOSNY_EDGE_TTS, encoding="ascii")


_HARNESS = r"""
param([string]$Blok, [string]$Scenare, [string]$Vystup, [string]$Python, [string]$Site,
      [string]$Zaznamy)
$kod = [IO.File]::ReadAllText($Blok)
$PY = @{ Exe = 'py'; Pre = @('-3') }
function Fail($message) { throw "ERROR: $message" }
function Write-Host {
    param([Parameter(Position = 0)] $Object = '', $ForegroundColor = '')
    $script:riadky.Add("$($script:s.id)`thost`t$ForegroundColor`t$Object")
}
function Nastav-Verziu($verzia) {
    Get-ChildItem $Site -Filter 'edge_tts-*.dist-info' | Remove-Item -Recurse -Force
    if ($verzia) {
        $d = New-Item -ItemType Directory -Path (Join-Path $Site "edge_tts-$verzia.dist-info")
        [IO.File]::WriteAllText((Join-Path $d.FullName 'METADATA'),
            "Metadata-Version: 2.1`nName: edge-tts`nVersion: $verzia`n")
    }
}
function Invoke-Py {
    $script:riadky.Add("$($script:s.id)`tpy`t" + ($args -join "`t"))
    if ($args[0] -eq '-c') { & $Python -S @args; return }
    if ($args -contains '--dry-run') { $global:LASTEXITCODE = $script:s.sonda; return }
    if ($script:s.pip -eq 0 -and $script:s.po) { Nastav-Verziu $script:s.po }
    $global:LASTEXITCODE = $script:s.pip
}
$script:riadky = New-Object System.Collections.Generic.List[string]
foreach ($s in (Get-Content $Scenare -Raw | ConvertFrom-Json)) {
    $script:s = $s
    Nastav-Verziu $s.pred
    Set-Location $s.priecinok
    $env:FALOSNY_EDGE = $s.edge
    $env:FALOSNY_ZAZNAM = Join-Path $Zaznamy "$($s.id).txt"
    $global:LASTEXITCODE = 0
    try { & ([scriptblock]::Create($kod)); $koniec = 'presiel' }
    catch { $koniec = $_.Exception.Message }
    $script:riadky.Add("$($s.id)`tkoniec`t$koniec")
}
[IO.File]::WriteAllLines($Vystup, $script:riadky.ToArray())
"""

# id: (installed before, pip install code, version after a successful pip,
#      probe code, fake edge_tts "api,slovo")
_SCENARE = {
    "online_stary": ("7.2.8", 0, "7.3.1", 0, "ok,ok"),
    "online_najnovsi": ("7.3.1", 0, None, 0, "ok,ok"),
    # without internet: the word would fail (403) - it must not even be tried
    "offline_dost_novy": ("7.3.1", 0, None, 1, "ok,403"),     # pip OK, probe not
    "offline_stary": ("7.2.8", 1, None, 1, "ok,ok"),
    "offline_ziadny": (None, 1, None, 1, "ok,ok"),
    "pip_zlyhal_dost_novy": ("7.10.0", 1, None, 0, "ok,403"),  # numerically: 7.10 > 7.3
    "pip_ok_stale_stary": ("7.2.8", 0, None, 0, "ok,ok"),
    # the upgrade brought an edge-tts with a changed API
    "api_nova_hlavna": ("7.3.1", 0, "8.0.0", 0, "konstruktor,ok"),
    "api_ta_ista_hlavna": ("7.3.1", 0, "7.4.0", 0, "sync,ok"),
    "api_import_offline": ("8.1.0", 1, None, 1, "import,ok"),   # API test even without network
    "api_minimum": ("7.3.1", 0, None, 0, "konstruktor,ok"),
    # API fine, but the test word is not
    "slovo_odmietnute": ("7.3.1", 0, None, 0, "ok,403"),
    "slovo_prazdne": ("7.3.1", 0, None, 0, "ok,prazdne"),
}


@pytest.fixture(scope="module")
def beh_bloku(tmp_path_factory):
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        pytest.skip("powershell.exe tu nie je")
    tmp = tmp_path_factory.mktemp("edge_blok")
    s_req, bez_req, site = tmp / "s_req", tmp / "bez_req", tmp / "site"
    zaznamy, temp = tmp / "zaznamy", tmp / "temp s medzerou"
    for p in (s_req, bez_req, site, zaznamy, temp):
        p.mkdir()
    _falosny_edge_tts(site)
    (s_req / "requirements.txt").write_text(_read("requirements.txt"), encoding="utf-8")
    (bez_req / "requirements.txt").write_text("pyttsx3\nedge-tts\n", encoding="utf-8")
    scenare = [{"id": i, "pred": pred, "pip": pip, "po": po, "sonda": sonda, "edge": edge,
                "priecinok": str(s_req)}
               for i, (pred, pip, po, sonda, edge) in _SCENARE.items()]
    scenare.append({"id": "bez_minima", "pred": "7.3.1", "pip": 0, "po": None,
                    "sonda": 0, "edge": "ok,ok", "priecinok": str(bez_req)})
    (tmp / "blok.ps1").write_text(_blok_z_buildu(), encoding="ascii")
    (tmp / "scenare.json").write_text(json.dumps(scenare), encoding="ascii")
    (tmp / "harness.ps1").write_text(_HARNESS, encoding="ascii")
    env = dict(os.environ, PYTHONPATH=str(site), PYTHONDONTWRITEBYTECODE="1",
               TEMP=str(temp), TMP=str(temp))
    beh = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", str(tmp / "harness.ps1"), "-Blok", str(tmp / "blok.ps1"),
         "-Scenare", str(tmp / "scenare.json"), "-Vystup", str(tmp / "vystup.txt"),
         "-Python", sys.executable, "-Site", str(site), "-Zaznamy", str(zaznamy)],
        cwd=str(tmp), env=env, capture_output=True, text=True, timeout=180)
    assert beh.returncode == 0, beh.stdout + beh.stderr
    vysledok = {}
    for riadok in (tmp / "vystup.txt").read_text(encoding="utf-8-sig").splitlines():
        sid, druh, *zvysok = riadok.split("\t")
        vysledok.setdefault(sid, []).append((druh, zvysok))
    # test words: which scenario said it and where (file deleted after the run)
    for sid in vysledok:
        subor = zaznamy / ("%s.txt" % sid)
        slova = subor.read_text(encoding="utf-8").splitlines() if subor.exists() else []
        vysledok[sid].append(("slova", slova))
    vysledok["_temp"] = temp
    return vysledok


def _hlasky(zaznam, farba):
    return [z[1] for d, z in zaznam if d == "host" and z[0] == farba]


def _pip_volania(zaznam):
    return [z[2:] for d, z in zaznam if d == "py" and z[:2] == ["-m", "pip"]]


def _py_c_volania(zaznam):
    return [z[1:] for d, z in zaznam if d == "py" and z[:1] == ["-c"]]


def _koniec(zaznam):
    return [z for d, z in zaznam if d == "koniec"][0][0]


def _slova(zaznam):
    return [z for d, z in zaznam if d == "slova"][0]


def test_blok_v_powershelli_pip_dostane_len_edge_tts_z_requirements(beh_bloku):
    podmienka = _edge_riadok()[0]
    zaznam = beh_bloku["online_stary"]
    # a space after the name: PowerShell 5.1 puts an argument with a space
    # in quotes, and then even Python via .bat does not take '<' and '>' as
    # redirection
    poziadavka = "edge-tts " + podmienka
    assert _pip_volania(zaznam) == [
        ["install", "--upgrade", "--retries", "1", "--timeout", "15", poziadavka],
        ["install", "--dry-run", "--ignore-installed", "--no-deps", "--quiet",
         "--retries", "1", "--timeout", "15", poziadavka]]
    assert _koniec(zaznam) == "presiel"
    assert _hlasky(zaznam, "Green") == [
        "edge-tts 7.3.1 goes into the build (minimum %s)" % _minimum_z_requirements(),
        "natural voice verified (edge-tts 7.3.1)"]
    assert _hlasky(zaznam, "Yellow") == []


@pytest.mark.parametrize("sid, verzia", [
    ("online_stary", "7.3.1"),
    ("online_najnovsi", "7.3.1"),
])
def test_blok_v_powershelli_s_internetom(beh_bloku, sid, verzia):
    zaznam = beh_bloku[sid]
    assert _koniec(zaznam) == "presiel"
    assert _hlasky(zaznam, "Yellow") == []
    assert _hlasky(zaznam, "Green") == [
        "edge-tts %s goes into the build (minimum %s)" % (verzia, _minimum_z_requirements()),
        "natural voice verified (edge-tts %s)" % verzia]
    # version check, API test, test word - each once, in this order
    volania = _py_c_volania(zaznam)
    assert [v[0] for v in volania] == [_kontrola_z_buildu(), _api_z_buildu(), _slovo_z_buildu()]
    # test word: one file in %TEMP% with a random name, deleted after the run
    (subor,) = _slova(zaznam)
    assert volania[2][1:] == [subor]
    temp = beh_bloku["_temp"]
    assert os.path.dirname(subor) == str(temp)
    assert re.fullmatch(r"zanshin-edge-tts-[0-9a-f]{32}\.mp3", os.path.basename(subor))
    assert not os.path.exists(subor)


@pytest.mark.parametrize("sid, verzia, sonda", [
    ("offline_dost_novy", "7.3.1", True),        # pip OK, only the probe finds there is no network
    ("pip_zlyhal_dost_novy", "7.10.0", False),   # pip failed - no probe needed
])
def test_blok_v_powershelli_bez_internetu_pokracuje_s_dost_novym(beh_bloku, sid, verzia, sonda):
    zaznam = beh_bloku[sid]
    assert _koniec(zaznam) == "presiel"
    zlte = _hlasky(zaznam, "Yellow")
    assert len(zlte) == 2 and "Couldn't check" in zlte[0] and verzia in zlte[0]
    # without internet the test word is skipped - it says so, does not stop
    assert zlte[1] == ("Skipping the test word (no internet) - the natural voice "
                       "with edge-tts %s is not verified." % verzia)
    assert _hlasky(zaznam, "Green") == ["edge-tts %s goes into the build (minimum %s)"
                                        % (verzia, _minimum_z_requirements())]
    assert any("--dry-run" in v for v in _pip_volania(zaznam)) == sonda
    # offline API test ran, the word (fake edge_tts would give 403) did not
    assert [v[0] for v in _py_c_volania(zaznam)] == [_kontrola_z_buildu(), _api_z_buildu()]
    assert _slova(zaznam) == []


@pytest.mark.parametrize("sid, verzia, internet", [
    ("offline_stary", "7.2.8", True),
    ("offline_ziadny", "?", True),
    ("pip_ok_stale_stary", "7.2.8", False),
])
def test_blok_v_powershelli_pod_minimom_zastavi_build(beh_bloku, sid, verzia, internet):
    zaznam = beh_bloku[sid]
    koniec = _koniec(zaznam)
    assert koniec.startswith("ERROR: edge-tts is ")
    assert verzia in koniec and "the natural voice wouldn't work in the build" in koniec
    assert ("check your internet connection" in koniec) == internet
    assert _hlasky(zaznam, "Green") == [] and _hlasky(zaznam, "Yellow") == []
    # below the minimum neither the API nor the word is tried
    assert [v[0] for v in _py_c_volania(zaznam)] == [_kontrola_z_buildu()]


def test_blok_v_powershelli_bez_minima_v_requirements(beh_bloku):
    zaznam = beh_bloku["bez_minima"]
    assert _koniec(zaznam) == ("ERROR: requirements.txt has no minimum for edge-tts "
                               "(line edge-tts>=...).")
    assert _pip_volania(zaznam) == [] and _py_c_volania(zaznam) == []


@pytest.mark.parametrize("sid, verzia, dovod, spat", [
    # a new major version: back to the newest previous one (<8)
    ("api_nova_hlavna", "8.0.0",
     "TypeError: Communicate.__init__() got an unexpected keyword argument 'rate'",
     "edge-tts>=7.3.1,<8"),
    # the same major version: back to the newest before the broken one
    ("api_ta_ista_hlavna", "7.4.0", "Communicate.save is not async", "edge-tts>=7.3.1,<7.4.0"),
    # even without internet - the API test needs no network
    ("api_import_offline", "8.1.0",
     "ImportError: falosny edge_tts: chyba zavislost aiohttp", "edge-tts>=7.3.1,<8"),
])
def test_blok_v_powershelli_zmenene_api_zastavi_build(beh_bloku, sid, verzia, dovod, spat):
    zaznam = beh_bloku[sid]
    assert _koniec(zaznam) == (
        "ERROR: edge-tts %s has changed so that Zanshin can't use it (%s). "
        "Go back to the last version that worked: in requirements.txt change the edge-tts "
        "line to %s and run the build again (from source, by hand: py -3 -m pip install "
        "\"%s\"). Only a newer Zanshin fixes this for good." % (verzia, dovod, spat, spat))
    # the "spat" advice has a form that both the build and the pre-check
    # read from requirements.txt
    z = re.match(_vzor_z_buildu(), spat, re.I)
    assert z and z.group(2) == _minimum_z_requirements()
    assert _hlasky(zaznam, "Green") == []
    # the test word is not tried after a failed API
    assert [v[0] for v in _py_c_volania(zaznam)] == [_kontrola_z_buildu(), _api_z_buildu()]
    assert _slova(zaznam) == []


def test_blok_v_powershelli_zlyhane_minimum_radi_preinstalovat(beh_bloku):
    """The API fails even on the minimum itself - edge-tts did not change, the
    "spat" advice (>=7.3.1,<7.3.1) would make no sense."""
    koniec = _koniec(beh_bloku["api_minimum"])
    minimum = _minimum_z_requirements()
    assert koniec == (
        "ERROR: edge-tts %s can't be used (TypeError: Communicate.__init__() got an "
        "unexpected keyword argument 'rate') - the problem is probably in one of its "
        "dependencies. Reinstall it: py -3 -m pip install --force-reinstall "
        "\"edge-tts==%s\" and run the build again." % (minimum, minimum))


@pytest.mark.parametrize("sid, dovod", [
    ("slovo_odmietnute", "ConnectionError: 403, message='Invalid response status'"),
    ("slovo_prazdne", "empty audio"),
])
def test_blok_v_powershelli_odmietnute_slovo_je_hlasne_varovanie(beh_bloku, sid, dovod):
    zaznam = beh_bloku[sid]
    # build goes on - exe works with the Windows voice too, app fixes the voice
    assert _koniec(zaznam) == "presiel"
    assert _hlasky(zaznam, "Green") == ["edge-tts 7.3.1 goes into the build (minimum %s)"
                                        % _minimum_z_requirements()]
    zlte = _hlasky(zaznam, "Yellow")
    assert zlte == [
        "!!! WARNING: Microsoft refuses even edge-tts 7.3.1, or its voice service isn't "
        "answering right now (%s)." % dovod,
        "!!! The build goes on, but the natural voice doesn't work in it right now - the "
        "Windows voice covers the cues.",
        "!!! To fix it: the Update voice button in the app (once a newer edge-tts is out) "
        "or a later build."]
    # loud: an empty line before and after
    farby = [z[0] for d, z in zaznam if d == "host"]
    i = farby.index("Yellow")
    assert farby[i - 1:i + 4] == ["", "Yellow", "Yellow", "Yellow", ""]
    # file deleted even after a failure (fake edge_tts had begun writing it)
    (subor,) = _slova(zaznam)
    assert not os.path.exists(subor)


def test_blok_v_powershelli_nenecha_v_temp_nic(beh_bloku):
    assert list(beh_bloku["_temp"].glob("zanshin-edge-tts-*")) == []


# Fake Python behind python.bat: writes sys.argv, pip does nothing (code 0),
# every '-c' (version check, API test, test word) runs the real Python with
# -S over a fake dist-info and a fake edge_tts.
_FALOSNY_PY = r"""
import json, os, subprocess, sys
with open(os.environ["ZAZNAM"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\n")
if sys.argv[1] == "-c":
    env = dict(os.environ, PYTHONPATH=os.environ["SITE"])
    sys.exit(subprocess.run([sys.executable, "-S"] + sys.argv[1:], env=env).returncode)
sys.exit(0)
"""


def test_blok_cez_bat_doruci_poziadavku_celu_a_nic_nepresmeruje(tmp_path):
    """Python via .bat (e.g. pyenv-win) goes through cmd.exe: a bare argument
    edge-tts>=7.3.1,<8 would be taken by cmd as redirection - pip would get
    a fragment and a file '7.3.1' would appear in the build folder (repo
    root); cmd would take '%' in the code as a variable. The real Invoke-Py
    and Fail from the script run, nothing is installed and nothing goes to
    the network (fake edge_tts)."""
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        pytest.skip("powershell.exe tu nie je")
    if not (sys.executable + str(tmp_path)).isascii():
        pytest.skip("cesta s diakritikou - .bat by ju v inej kodovej stranke pokazil")
    skript = _read("build_all.ps1")
    fail = skript[skript.index("function Fail($message) {"):skript.index("# ----")]
    invoke = skript[skript.index("function Invoke-Py {"):skript.index("$version = ")]
    site, shim = tmp_path / "site", tmp_path / "python v kosi"
    build, citlivost = tmp_path / "build", tmp_path / "citlivost"
    temp = tmp_path / "temp s medzerou"
    for p in (site, shim, build, citlivost, temp):
        p.mkdir()
    _dist_info(site, "7.3.1")
    _falosny_edge_tts(site)
    (tmp_path / "falosny.py").write_text(_FALOSNY_PY, encoding="ascii")
    bat = shim / "python.bat"
    bat.write_text('@"%s" "%s" %%*\r\n' % (sys.executable, tmp_path / "falosny.py"),
                   encoding="ascii", newline="")
    (build / "requirements.txt").write_text(_read("requirements.txt"), encoding="utf-8")
    beh_ps = (fail + "$PY = @{ Exe = '%s'; Pre = @() }\n" % str(bat).replace("'", "''") +
              invoke + _blok_z_buildu() +
              "Set-Location '%s'\n" % str(citlivost).replace("'", "''") +
              "Invoke-Py '-m' 'pip' 'install' 'edge-tts>=7.3.1,<8'\nexit 0\n")
    (tmp_path / "beh.ps1").write_text(beh_ps, encoding="ascii")
    zaznam, slova = tmp_path / "zaznam.jsonl", tmp_path / "slova.txt"
    env = dict(os.environ, ZAZNAM=str(zaznam), SITE=str(site), PYTHONDONTWRITEBYTECODE="1",
               FALOSNY_EDGE="ok,ok", FALOSNY_ZAZNAM=str(slova), TEMP=str(temp), TMP=str(temp))
    beh = subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                          "Bypass", "-File", str(tmp_path / "beh.ps1")],
                         cwd=str(build), env=env, capture_output=True, text=True, timeout=90)
    assert beh.returncode == 0, beh.stdout + beh.stderr
    assert "edge-tts 7.3.1 goes into the build" in beh.stdout, beh.stdout
    # both new '-c' lines arrived whole (otherwise the fake edge_tts would
    # throw ValueError) - API and word passed
    assert "natural voice verified (edge-tts 7.3.1)" in beh.stdout, beh.stdout
    volania = [json.loads(r) for r in zaznam.read_text(encoding="utf-8").splitlines()]
    poziadavka = "edge-tts " + _edge_riadok()[0]
    pip = [v for v in volania if v[:2] == ["-m", "pip"]]
    assert pip[:2] == [
        ["-m", "pip", "install", "--upgrade", "--retries", "1", "--timeout", "15", poziadavka],
        ["-m", "pip", "install", "--dry-run", "--ignore-installed", "--no-deps", "--quiet",
         "--retries", "1", "--timeout", "15", poziadavka]]
    assert ["-c", _kontrola_z_buildu(), _minimum_z_requirements()] in volania
    assert ["-c", _api_z_buildu()] in volania
    (subor,) = slova.read_text(encoding="utf-8").splitlines()
    assert ["-c", _slovo_z_buildu(), subor] in volania
    # the %TEMP% path with a space arrived whole, file deleted after the run
    assert os.path.dirname(subor) == str(temp) and not os.path.exists(subor)
    assert list(temp.glob("zanshin-edge-tts-*")) == []
    # the block created nothing in the build folder
    assert sorted(p.name for p in build.iterdir()) == ["requirements.txt"]
    # sensitivity check: the bare form really breaks the same .bat (cmd.exe) -
    # otherwise the test would not prove the space after the name is needed
    assert pip[2:] != [["-m", "pip", "install", "edge-tts>=7.3.1,<8"]]
    assert "7.3.1" in [p.name for p in citlivost.iterdir()]


def _dist_info(koren, verzia):
    priecinok = koren / ("edge_tts-%s.dist-info" % verzia)
    priecinok.mkdir(parents=True)
    (priecinok / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: edge-tts\nVersion: %s\n" % verzia, encoding="ascii")


@pytest.mark.parametrize("nainstalovana, minimum, kod", [
    ("7.2.8", "7.3.1", 1),
    ("7.3.1", "7.3.1", 0),
    ("7.10.0", "7.3.1", 0),          # numerically, not as text ("7.10" < "7.3")
    ("8.0", "7.3.1", 0),
    ("7.3", "7.3.1", 1),
    (None, "7.3.1", 1),              # not installed = pip needed
])
def test_kontrola_verzie_z_buildu_naozaj_porovna(tmp_path, nainstalovana, minimum, kod):
    """The same code that build_all.ps1 runs (`py -c`). `-S` switches off
    site-packages - only the fake dist-info from tmp_path is visible."""
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


def _spusti_py_c(tmp_path, kod, *argumenty, edge="ok,ok"):
    """Build `py -c` over a fake edge_tts (`-S`: the real one is hidden)."""
    site = tmp_path / "site"
    if not site.exists():
        site.mkdir()
        _falosny_edge_tts(site)
    env = dict(os.environ, PYTHONPATH=str(site), PYTHONDONTWRITEBYTECODE="1",
               FALOSNY_EDGE=edge, FALOSNY_ZAZNAM=str(tmp_path / "slova.txt"))
    return subprocess.run([sys.executable, "-S", "-c", kod] + list(argumenty),
                          cwd=str(tmp_path), env=env, capture_output=True, text=True,
                          timeout=60)


@pytest.mark.parametrize("edge, kod, vystup", [
    ("ok,ok", 0, ""),
    ("konstruktor,ok", 1,
     "TypeError: Communicate.__init__() got an unexpected keyword argument 'rate'"),
    ("sync,ok", 1, "Communicate.save is not async"),
    ("import,ok", 1, "ImportError: falosny edge_tts: chyba zavislost aiohttp"),
])
def test_api_skuska_z_buildu(tmp_path, edge, kod, vystup):
    beh = _spusti_py_c(tmp_path, _api_z_buildu(), edge=edge)
    assert beh.returncode == kod, beh.stderr
    # one short line, no traceback
    assert beh.stdout.strip() == vystup and "Traceback" not in beh.stderr
    # the API test says nothing (save is not called)
    assert not (tmp_path / "slova.txt").exists()


@pytest.mark.parametrize("edge, kod, vystup, obsah", [
    ("ok,ok", 0, "", b"ID3"),
    ("ok,403", 1, "ConnectionError: 403, message='Invalid response status'", b"ID3"),
    ("ok,prazdne", 1, "empty audio", b""),
])
def test_skusobne_slovo_z_buildu(tmp_path, edge, kod, vystup, obsah):
    subor = tmp_path / "temp s medzerou" / "zanshin-edge-tts-x.mp3"
    subor.parent.mkdir()
    beh = _spusti_py_c(tmp_path, _slovo_z_buildu(), str(subor), edge=edge)
    assert beh.returncode == kod, beh.stderr
    assert beh.stdout.strip() == vystup and "Traceback" not in beh.stderr
    assert (tmp_path / "slova.txt").read_text(encoding="utf-8").splitlines() == [str(subor)]
    # build deletes it (Remove-Item); Python leaves it as edge-tts wrote it
    assert subor.read_bytes() == obsah


def test_api_skuska_prejde_so_skutocnym_edge_tts(tmp_path):
    """The same line the build runs, against the installed edge-tts -
    confirms that the test fits the real API (Communicate with rate=...,
    async save). It does not go to the network: the constructor is not a
    network one, and to be safe sockets are forbidden (every attempt would
    end with an error and code 1)."""
    pytest.importorskip("edge_tts")
    bez_siete = ("import socket\n"
                 "def _zakazane(*_a, **_k):\n"
                 "    raise OSError('siet je v teste zakazana')\n"
                 "socket.socket.connect = socket.socket.connect_ex = _zakazane\n"
                 "socket.create_connection = socket.getaddrinfo = _zakazane\n")
    beh = subprocess.run([sys.executable, "-I", "-c", bez_siete + _api_z_buildu()],
                         cwd=str(tmp_path), capture_output=True, text=True, timeout=60,
                         env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    assert beh.returncode == 0, beh.stdout + beh.stderr
    assert beh.stdout.strip() == ""


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
    # the same error again: neither the journal nor app.log
    a.ui.clear()
    chyby._zlyha(a, (EDGE_CHYBA_ODMIETNUTE, chyby.WSServerHandshakeError(403)))
    assert len(log.riadky) == 1 and len(a.denn) == 1
    # another kind = a new line
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
    # the app.log line only after the "once per kind" guard
    assert telo.index("self._edge_chyba_v_denniku = druh") < telo.index("app_log.warning(")


# --------------------------------------------------------------------------
# Real rejection: aiohttp + edge-tts, no network
# --------------------------------------------------------------------------
#
# The dummies above (test_022e_hlas_chyby) have their own classes. Here a
# REAL aiohttp.WSServerHandshakeError, built as in aiohttp/client.py, goes
# through the REAL edge-tts (its second attempt after 403 with the clock
# adjusted by the Date header) and `EdgeTTSCache.ensure`. `ws_connect` is
# patched - nothing goes to the network. Verified 2026-11: edge-tts 7.2.8
# gets exactly this from Microsoft.

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
    (True, 2, "WSServerHandshakeError"),   # second attempt after clock adjustment also 403
    (False, 1, "SkewAdjustmentError"),     # no Date: edge-tts' own error "from" 403
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

    # the same error all the way to the status, journal and app.log
    log = _Log()
    monkeypatch.setattr(app_audio, "app_log", log)
    a = chyby._atrapa(monkeypatch)
    chyby._zlyha(a, (druh, exc))
    assert a.stavy[-1] == i18n.tr("edge.partial_refused", ok=0, total=3)
    assert len(a.denn) == 1 and len(log.riadky) == 1
    assert "(refused)" in log.riadky[0]
    if date:
        assert "403, message='Invalid response status'" in log.riadky[0]
        # the service URL stays a URL - not "wsv1?..." from path trimming
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
# Rejection texts
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
        # no URL - no voice sentence had one so far
        assert not re.search(r"https?:|github\.com|www\.", text), (kluc, jazyk)
        # still also the "try later / switch Voice source to Windows" advice
        assert "Windows" in text, (kluc, jazyk)
        zdroj = i18n.tr_lang(jazyk, "settings.engine")
        assert zdroj.lower() in text.lower(), (kluc, jazyk)
        assert "\\u" not in text, (kluc, jazyk)


def test_dennik_hovori_slovnikom_a_povie_kto_hovori_dovtedy():
    for jazyk in i18n.LANGUAGES:
        text = S["log.edge_failed_refused"][jazyk]
        assert PRIPOMIENKA[jazyk] in text, jazyk
        # rejection line in journals: Windows voice says the rest (like offline)
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
