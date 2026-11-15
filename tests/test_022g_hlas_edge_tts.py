# -*- coding: utf-8 -*-
"""0.2.2: prirodzeny hlas po odmietnuti Microsoftom (HTTP 403, november 2026).

PRECO: Microsoft od novembra 2026 odmieta edge-tts starsi ako 7.3.1
(odmietnuty handshake WebSocketu, "Invalid response status"). Prirodzeny
hlas potom mlci a pripomienky hovori hlas z Windows. Novy build by to
neopravil: requirements.txt mal holy "edge-tts" a build_all.ps1 instaloval
zavislosti len ked nejaky modul CHYBAL - stara verzia v PC ostala navzdy.
A zlyhanie islo len do dennika v okne, nie do logs/app.log.

Rozhodnutie autora (2026-11-15): build stiahne najnovsi povoleny edge-tts
pri KAZDOM behu - ked Microsoft zmeni nieco znova, aj build po mesiaci bez
vydania dostane opravu. Strop <8 drzi mimo buildu neoverenu hlavnu verziu.

Co strazi tento test:
  * requirements.txt ma edge-tts s minimom a stropom (jediny zdroj) a
    ostatne riadky ostali,
  * build_all.ps1 celu poziadavku aj minimum cita z requirements.txt (tym
    istym vzorom ako check_before_run.py) a pri kazdom builde spusti
    `pip install --upgrade` LEN pre tuto poziadavku (s --retries/--timeout);
    bez internetu pokracuje, len ked nainstalovany edge-tts minimum splna,
    inak zastavi build (Fail),
  * skutocny blok z build_all.ps1 v powershell.exe s falosnym pip (uspech,
    bez internetu, zlyhanie) robi presne to - kazdy pripad zvlast,
  * ten isty blok so SKUTOCNYM Invoke-Py cez python.bat (cmd.exe, cesta s
    medzerou) doruci poziadavku do sys.argv celu a v priecinku buildu
    nevznikne ziadny subor (holy '<' a '>' by cmd zobral ako presmerovanie),
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
    """(podmienka, minimum, strop) z riadku edge-tts>=X,<N v requirements.txt.
    Vlastny prisny vzor - nezavisly od vzoru v builde."""
    zhody = re.findall(r"^\s*edge-tts\s*(>=\s*([0-9.]+)\s*,\s*<\s*([0-9]+))\s*$",
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


# --------------------------------------------------------------------------
# requirements.txt
# --------------------------------------------------------------------------

def test_requirements_ma_minimum_a_strop_edge_tts():
    podmienka, minimum, strop = _edge_riadok()
    assert _cisla(minimum) >= (7, 3, 1)
    # strop = dalsia hlavna verzia: neoverena (moze zmenit API) do buildu
    # nepride, kazda novsia 7.x ano
    assert int(strop) == _cisla(minimum)[0] + 1, podmienka
    riadky = [r.strip() for r in _read("requirements.txt").splitlines()
              if r.strip() and not r.lstrip().startswith("#")]
    assert "edge-tts" not in riadky, "holy edge-tts by nechal staru verziu"
    # ostatne zavislosti ostali, ako boli (bez verzii - build ich necha tak)
    assert [r for r in riadky if not r.startswith("edge-tts")] == [
        "pyttsx3", "comtypes", "pystray", "pillow", "customtkinter", "numpy",
        "pygame-ce", "psutil"]


# --------------------------------------------------------------------------
# build_all.ps1
# --------------------------------------------------------------------------

def _blok_z_buildu():
    """edge-tts blok z build_all.ps1: od $edgeMinVzor po PyInstaller."""
    skript = _read("build_all.ps1")
    return skript[skript.index("$edgeMinVzor = "):
                  skript.index("Invoke-Py '-m' 'PyInstaller' '--version'")]


def test_build_cita_poziadavku_z_requirements_tym_istym_vzorom():
    vzor = _vzor_z_buildu()
    podmienka, minimum, strop = _edge_riadok()
    # PowerShell -match je bez ohladu na velkost pismen; skupina 1 = cela
    # podmienka (ide do pip), skupina 2 = minimum (kontrola verzie)
    najdene = [(z.group(1).strip(), z.group(2))
               for r in _read("requirements.txt").splitlines()
               if (z := re.match(vzor, r, re.I))]
    assert najdene == [(podmienka, minimum)]
    assert podmienka == ">=%s,<%s" % (minimum, strop)
    for riadok, cakane in (
            ("edge-tts >= 7.3.1, <8  # komentar", (">= 7.3.1, <8", "7.3.1")),
            ("edge-tts>=7.10.0,<8", (">=7.10.0,<8", "7.10.0")),
            ("edge-tts>=7.3.1,<8; sys_platform == 'win32'", (">=7.3.1,<8", "7.3.1")),
            ("edge-tts>=7.3.1", (">=7.3.1", "7.3.1"))):
        z = re.match(vzor, riadok, re.I)
        assert (z.group(1).strip(), z.group(2)) == cakane, riadok
    for bez_minima in ("edge-tts", "edge-tts<8", "# edge-tts>=7.3.1"):
        assert not re.match(vzor, bez_minima, re.I), bez_minima
    # cely subor naraz (check_before_run.py): podmienka neprejde na dalsi riadok
    z = re.search(vzor, "edge-tts>=7.3.1,<8\ncustomtkinter\n", re.I | re.M)
    assert z.group(1) == ">=7.3.1,<8"
    skript = _read("build_all.ps1")
    assert "Get-Content 'requirements.txt'" in skript
    assert "$riadok -match $edgeMinVzor" in skript
    assert "$edgePoziadavka = 'edge-tts ' + $Matches[1].Trim()" in skript
    assert "$edgeMin = $Matches[2]" in skript
    # jediny zdroj: ziadne cislo verzie ani strop natvrdo v skripte
    assert minimum not in skript and "<%s" % strop not in skript
    # ta ista poziadavka v predbeznej kontrole, minimum je tam tiez skupina 2
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
    # pri kazdom builde: upgrade LEN poziadavky edge-tts z requirements.txt
    upgrade = ("Invoke-Py '-m' 'pip' 'install' '--upgrade' '--retries' '1' "
               "'--timeout' '15' $edgePoziadavka")
    riadky = [r.strip() for r in skript.splitlines()]
    assert [r for r in riadky if "'--upgrade'" in r] == [upgrade]
    # ani skratka, ani ina strategia (eager by zdvihol aj vsetky zavislosti)
    assert "'-U'" not in skript and "'--upgrade-strategy'" not in skript
    # -r requirements.txt len v cykle chybajucich modulov, bez --upgrade
    s_r = [r for r in riadky if "'-r'" in r]
    assert s_r == ["Invoke-Py '-m' 'pip' 'install' '-r' 'requirements.txt'"]
    assert skript.index(s_r[0]) < kontrola
    # pip OK aj bez internetu, ked nainstalovany vyhovuje - preto sonda indexu
    # (--dry-run nic neinstaluje), len po uspesnom pip
    sonda = ("Invoke-Py '-m' 'pip' 'install' '--dry-run' '--ignore-installed' "
             "'--no-deps' '--quiet' '--retries' '1' '--timeout' '15' "
             "$edgePoziadavka 2>&1 | Out-Null")
    assert blok.count(sonda) == 1
    assert blok.index(upgrade) < blok.index("if ($edgePip -eq 0) {") < blok.index(sonda)
    # potom kontrola verzie: pod minimum = Fail (s internetom aj bez)
    over = blok.index("$edgeVerzia = \"$(Invoke-Py '-c' $edgeKontrola $edgeMin)\".Trim()")
    assert blok.count("Invoke-Py '-c' $edgeKontrola $edgeMin") == 1
    assert blok.index(sonda) < over
    po = blok[over:]
    pod_minimom = po[po.index("if ($LASTEXITCODE -ne 0) {"):po.index("if ($edgePip -ne 0) {\n    Write-Host")]
    assert pod_minimom.count("Fail \"") == 2
    assert "skontroluj internet" in pod_minimom and "nefungoval" in pod_minimom
    # bez internetu (pip alebo sonda zlyhali) a minimum splnene: zlte, pokracuje
    zlte = po[po.index("if ($edgePip -ne 0) {\n    Write-Host"):]
    assert "nevedel overit (bez internetu?)" in zlte and "-ForegroundColor Yellow" in zlte
    assert "Fail" not in zlte
    # verzia, ktora ide do exe, je vzdy v logu buildu
    assert 'Write-Host "edge-tts $edgeVerzia ide do buildu' in zlte
    assert "Fail \"requirements.txt nema minimum pre edge-tts" in blok
    # ziadne 'packaging' (nemusi byt nainstalovany)
    assert "packaging" not in _kontrola_z_buildu()
    # PowerShell 5.1 skript bez BOM cita ako ANSI - ostava cisto ASCII
    assert skript.isascii()


# --------------------------------------------------------------------------
# Skutocny blok z build_all.ps1 v powershell.exe, pip je falosny
# --------------------------------------------------------------------------
#
# Bezi PRAVY kod bloku (citanie requirements.txt, rozhodovanie, hlasky);
# Fail a Write-Host su prepisane na zaznam, Invoke-Py na falosny pip.
# Kontrola verzie ('-c' $edgeKontrola) ide do skutocneho Pythonu s `-S`
# nad falosnym dist-info - ako test_kontrola_verzie_z_buildu_naozaj_porovna.
# Falosny pip: install vrati kod zo scenara a pri uspechu "nainstaluje"
# verziu `po`; sonda (--dry-run) vrati `sonda`. Pip bez internetu realne
# (overene 2026-11): s vyhovujucim edge-tts skonci 0, so starym 1.

_HARNESS = r"""
param([string]$Blok, [string]$Scenare, [string]$Vystup, [string]$Python, [string]$Site)
$kod = [IO.File]::ReadAllText($Blok)
function Fail($message) { throw "CHYBA: $message" }
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
    $global:LASTEXITCODE = 0
    try { & ([scriptblock]::Create($kod)); $koniec = 'presiel' }
    catch { $koniec = $_.Exception.Message }
    $script:riadky.Add("$($s.id)`tkoniec`t$koniec")
}
[IO.File]::WriteAllLines($Vystup, $script:riadky.ToArray())
"""

# id: (nainstalovany pred, kod pip install, verzia po uspesnom pip, kod sondy)
_SCENARE = {
    "online_stary": ("7.2.8", 0, "7.3.1", 0),
    "online_najnovsi": ("7.3.1", 0, None, 0),
    "offline_dost_novy": ("7.3.1", 0, None, 1),     # pip OK, sonda nie
    "offline_stary": ("7.2.8", 1, None, 1),
    "offline_ziadny": (None, 1, None, 1),
    "pip_zlyhal_dost_novy": ("7.10.0", 1, None, 0),  # ciselne: 7.10 > 7.3
    "pip_ok_stale_stary": ("7.2.8", 0, None, 0),
}


@pytest.fixture(scope="module")
def beh_bloku(tmp_path_factory):
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        pytest.skip("powershell.exe tu nie je")
    tmp = tmp_path_factory.mktemp("edge_blok")
    s_req, bez_req, site = tmp / "s_req", tmp / "bez_req", tmp / "site"
    for p in (s_req, bez_req, site):
        p.mkdir()
    (s_req / "requirements.txt").write_text(_read("requirements.txt"), encoding="utf-8")
    (bez_req / "requirements.txt").write_text("pyttsx3\nedge-tts\n", encoding="utf-8")
    scenare = [{"id": i, "pred": pred, "pip": pip, "po": po, "sonda": sonda,
                "priecinok": str(s_req)} for i, (pred, pip, po, sonda) in _SCENARE.items()]
    scenare.append({"id": "bez_minima", "pred": "7.3.1", "pip": 0, "po": None,
                    "sonda": 0, "priecinok": str(bez_req)})
    (tmp / "blok.ps1").write_text(_blok_z_buildu(), encoding="ascii")
    (tmp / "scenare.json").write_text(json.dumps(scenare), encoding="ascii")
    (tmp / "harness.ps1").write_text(_HARNESS, encoding="ascii")
    env = dict(os.environ, PYTHONPATH=str(site), PYTHONDONTWRITEBYTECODE="1")
    beh = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", str(tmp / "harness.ps1"), "-Blok", str(tmp / "blok.ps1"),
         "-Scenare", str(tmp / "scenare.json"), "-Vystup", str(tmp / "vystup.txt"),
         "-Python", sys.executable, "-Site", str(site)],
        cwd=str(tmp), env=env, capture_output=True, text=True, timeout=60)
    assert beh.returncode == 0, beh.stdout + beh.stderr
    vysledok = {}
    for riadok in (tmp / "vystup.txt").read_text(encoding="utf-8-sig").splitlines():
        sid, druh, *zvysok = riadok.split("\t")
        vysledok.setdefault(sid, []).append((druh, zvysok))
    return vysledok


def _hlasky(zaznam, farba):
    return [z[1] for d, z in zaznam if d == "host" and z[0] == farba]


def _pip_volania(zaznam):
    return [z[2:] for d, z in zaznam if d == "py" and z[:2] == ["-m", "pip"]]


def test_blok_v_powershelli_pip_dostane_len_edge_tts_z_requirements(beh_bloku):
    podmienka = _edge_riadok()[0]
    zaznam = beh_bloku["online_stary"]
    # medzera za menom: argument s medzerou da PowerShell 5.1 do uvodzoviek
    # a ani Python cez .bat neberie '<' a '>' ako presmerovanie
    poziadavka = "edge-tts " + podmienka
    assert _pip_volania(zaznam) == [
        ["install", "--upgrade", "--retries", "1", "--timeout", "15", poziadavka],
        ["install", "--dry-run", "--ignore-installed", "--no-deps", "--quiet",
         "--retries", "1", "--timeout", "15", poziadavka]]
    assert zaznam[-1] == ("koniec", ["presiel"])
    assert _hlasky(zaznam, "Green") == ["edge-tts 7.3.1 ide do buildu (treba aspon %s)"
                                        % _minimum_z_requirements()]
    assert _hlasky(zaznam, "Yellow") == []


@pytest.mark.parametrize("sid, verzia", [
    ("online_stary", "7.3.1"),
    ("online_najnovsi", "7.3.1"),
])
def test_blok_v_powershelli_s_internetom(beh_bloku, sid, verzia):
    zaznam = beh_bloku[sid]
    assert zaznam[-1] == ("koniec", ["presiel"])
    assert _hlasky(zaznam, "Yellow") == []
    assert _hlasky(zaznam, "Green") == ["edge-tts %s ide do buildu (treba aspon %s)"
                                        % (verzia, _minimum_z_requirements())]


@pytest.mark.parametrize("sid, verzia, sonda", [
    ("offline_dost_novy", "7.3.1", True),        # pip OK, az sonda zisti, ze siet nie je
    ("pip_zlyhal_dost_novy", "7.10.0", False),   # pip zlyhal - sonda netreba
])
def test_blok_v_powershelli_bez_internetu_pokracuje_s_dost_novym(beh_bloku, sid, verzia, sonda):
    zaznam = beh_bloku[sid]
    assert zaznam[-1] == ("koniec", ["presiel"])
    zlte = _hlasky(zaznam, "Yellow")
    assert len(zlte) == 1 and "nevedel overit" in zlte[0] and verzia in zlte[0]
    assert _hlasky(zaznam, "Green") == ["edge-tts %s ide do buildu (treba aspon %s)"
                                        % (verzia, _minimum_z_requirements())]
    assert any("--dry-run" in v for v in _pip_volania(zaznam)) == sonda


@pytest.mark.parametrize("sid, verzia, internet", [
    ("offline_stary", "7.2.8", True),
    ("offline_ziadny", "?", True),
    ("pip_ok_stale_stary", "7.2.8", False),
])
def test_blok_v_powershelli_pod_minimom_zastavi_build(beh_bloku, sid, verzia, internet):
    zaznam = beh_bloku[sid]
    druh, (koniec,) = zaznam[-1]
    assert druh == "koniec" and koniec.startswith("CHYBA: edge-tts je ")
    assert verzia in koniec and "prirodzeny hlas by v builde nefungoval" in koniec
    assert ("skontroluj internet" in koniec) == internet
    assert _hlasky(zaznam, "Green") == [] and _hlasky(zaznam, "Yellow") == []


def test_blok_v_powershelli_bez_minima_v_requirements(beh_bloku):
    zaznam = beh_bloku["bez_minima"]
    assert zaznam[-1] == ("koniec", ["CHYBA: requirements.txt nema minimum pre edge-tts "
                                     "(riadok edge-tts>=...)."])
    assert _pip_volania(zaznam) == []


# Falosny Python za python.bat: zapise sys.argv, pip nic nerobi (kod 0),
# kontrolu verzie ('-c') spusti skutocny Python s -S nad falosnym dist-info.
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
    """Python cez .bat (napr. pyenv-win) ide cez cmd.exe: holy argument
    edge-tts>=7.3.1,<8 by cmd vzal ako presmerovanie - pip by dostal zlomok
    a v priecinku buildu (koren repa) by vznikol subor '7.3.1'. Bezi
    skutocny Invoke-Py a Fail zo skriptu, nic sa neinstaluje."""
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
    for p in (site, shim, build, citlivost):
        p.mkdir()
    _dist_info(site, "7.3.1")
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
    zaznam = tmp_path / "zaznam.jsonl"
    env = dict(os.environ, ZAZNAM=str(zaznam), SITE=str(site), PYTHONDONTWRITEBYTECODE="1")
    beh = subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                          "Bypass", "-File", str(tmp_path / "beh.ps1")],
                         cwd=str(build), env=env, capture_output=True, text=True, timeout=60)
    assert beh.returncode == 0, beh.stdout + beh.stderr
    assert "edge-tts 7.3.1 ide do buildu" in beh.stdout, beh.stdout
    volania = [json.loads(r) for r in zaznam.read_text(encoding="utf-8").splitlines()]
    poziadavka = "edge-tts " + _edge_riadok()[0]
    pip = [v for v in volania if v[:2] == ["-m", "pip"]]
    assert pip[:2] == [
        ["-m", "pip", "install", "--upgrade", "--retries", "1", "--timeout", "15", poziadavka],
        ["-m", "pip", "install", "--dry-run", "--ignore-installed", "--no-deps", "--quiet",
         "--retries", "1", "--timeout", "15", poziadavka]]
    assert ["-c", _kontrola_z_buildu(), _minimum_z_requirements()] in volania
    # blok v priecinku buildu nic nevytvoril
    assert sorted(p.name for p in build.iterdir()) == ["requirements.txt"]
    # kontrola citlivosti: holy tvar ten isty .bat naozaj rozbije (cmd.exe) -
    # inak by test nedokazal, ze medzera za menom je potrebna
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
