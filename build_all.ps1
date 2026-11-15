# Builds Zanshin.exe and from it the installer Zanshin-<version>-setup.exe
# (version = MyAppVersion in Dandurf.iss)
#
# How to run (works from any folder):
#     powershell -ExecutionPolicy Bypass -File ".\build_all.ps1"
#
# You need:
#   Python 3   ->  https://www.python.org/downloads/
#   Inno Setup 6  ->  https://jrsoftware.org/isdl.php   (for step 3/3)
#
# Note: we deliberately DON'T set $ErrorActionPreference = "Stop" - in PowerShell
# 5.1 an external program that writes to stderr can throw an exception even
# when it finished fine. So we check exit codes by hand.

Set-Location -Path $PSScriptRoot
Write-Host "Folder: $PSScriptRoot" -ForegroundColor DarkGray

function Fail($message) {
    Write-Host ""
    Write-Host "ERROR: $message" -ForegroundColor Red
    exit 1
}

# --------------------------------------------------------------------------
# 1/3  Python and dependencies
# --------------------------------------------------------------------------
Write-Host ""
Write-Host "=== 1/3  Checking dependencies ===" -ForegroundColor Cyan

# On Windows, Python is sometimes called 'python', sometimes only 'py'. We try both.
# Careful: a bare 'python' is often an alias to the Microsoft Store that runs
# nothing - so we really test each candidate.
$pythonCandidates = @(
    @{ Exe = 'py';      Pre = @('-3') },
    @{ Exe = 'python';  Pre = @() },
    @{ Exe = 'python3'; Pre = @() }
)
$PY = $null
foreach ($candidate in $pythonCandidates) {
    if (-not (Get-Command $candidate.Exe -ErrorAction SilentlyContinue)) { continue }
    $probeArgs = $candidate.Pre + @('-c', 'import sys')
    & $candidate.Exe @probeArgs 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $PY = $candidate; break }
}
if (-not $PY) {
    # The Python install manager (today mainly the button on python.org) has no
    # PATH checkbox - 'py' goes through an alias in WindowsApps, and Python
    # downloads itself on the first 'py -3'. If even that fails, it's usually no internet.
    Fail ("Python not found (or it couldn't be downloaded - check your internet connection). " +
          "Install 'Python install manager' from https://www.python.org/downloads/ " +
          "and run build.bat again. The classic installer from python.org works too.")
}

function Invoke-Py {
    $callArgs = $PY.Pre + $args
    & $PY.Exe @callArgs
}

$version = Invoke-Py '-c' 'import sys; print(sys.version.split()[0])'
Write-Host "Python $version  ($($PY.Exe) $($PY.Pre))" -ForegroundColor Green

# pyttsx3 (the Windows voice fallback) and psutil (automatic profiles) used to be
# missing here - the build passed without them, but the app then quietly lost these features.
foreach ($module in @('edge_tts', 'comtypes', 'pystray', 'PIL',
                     'customtkinter', 'numpy', 'pygame', 'pyttsx3', 'psutil')) {
    Invoke-Py '-c' "import $module" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Module $module is missing - installing dependencies..." -ForegroundColor Yellow
        Invoke-Py '-m' 'pip' 'install' '-r' 'requirements.txt'
        if ($LASTEXITCODE -ne 0) { Fail "pip install failed." }
        break
    }
}

# The build fetches edge-tts (the natural voice) in its newest version on EVERY
# run: since November 2026 Microsoft refuses older versions (HTTP 403), and when
# it changes something again, the fix usually comes in a new edge-tts - even for
# a build made a month after a release. The loop above installs only a MISSING module.
# There is deliberately no version cap (it could block exactly that fix) - so
# after the upgrade the build tries the new version: the API without the network
# and one test word (below).
# The requirement (minimum) is only in requirements.txt. ONLY edge-tts gets
# the upgrade: by default (--upgrade-strategy only-if-needed) pip raises one of
# its dependencies only if edge-tts needs a newer version of it; it leaves the other packages alone.
# The space after the name is deliberate: PowerShell 5.1 puts an argument with a
# space in quotes, so not even Python through a .bat (e.g. pyenv-win) takes '<' and '>'
# as redirection. The versions are compared numerically via importlib.metadata -
# without 'packaging', which may not be installed.
$edgeMinVzor = '^\s*edge-tts\s*(>=\s*([0-9]+(?:\.[0-9]+)*)[^#;\r\n]*)'
$edgeMin = $null
foreach ($riadok in Get-Content 'requirements.txt') {
    if ($riadok -match $edgeMinVzor) {
        $edgePoziadavka = 'edge-tts ' + $Matches[1].Trim()
        $edgeMin = $Matches[2]
        break
    }
}
if (-not $edgeMin) { Fail "requirements.txt has no minimum for edge-tts (line edge-tts>=...)." }
$edgeKontrola = "import re, sys, importlib.metadata as m; d = next(iter(m.distributions(name='edge-tts')), None); v = d.version if d else '?'; t = lambda s: tuple(int(c) for c in re.findall(r'\d+', s)); print(v); sys.exit(0 if t(v) >= t(sys.argv[1]) else 1)"
Write-Host "Looking for the newest edge-tts ($edgePoziadavka)..." -ForegroundColor DarkGray
Invoke-Py '-m' 'pip' 'install' '--upgrade' '--retries' '1' '--timeout' '15' $edgePoziadavka
$edgePip = $LASTEXITCODE
if ($edgePip -eq 0) {
    # Offline, pip ends OK when the installed edge-tts meets the requirement
    # (it only prints WARNING Retrying). So we ask the index once more,
    # regardless of what's installed: --dry-run installs nothing and fails offline.
    Invoke-Py '-m' 'pip' 'install' '--dry-run' '--ignore-installed' '--no-deps' '--quiet' '--retries' '1' '--timeout' '15' $edgePoziadavka 2>&1 | Out-Null
    $edgePip = $LASTEXITCODE
}
$edgeVerzia = "$(Invoke-Py '-c' $edgeKontrola $edgeMin)".Trim()
if ($LASTEXITCODE -ne 0) {
    if ($edgePip -ne 0) {
        Fail "edge-tts is $edgeVerzia, but the minimum is $edgeMin, and a newer one couldn't be downloaded (check your internet connection) - the natural voice wouldn't work in the build."
    }
    Fail "edge-tts is still $edgeVerzia, but the minimum is $edgeMin - the natural voice wouldn't work in the build."
}
if ($edgePip -ne 0) {
    Write-Host "Couldn't check for the newest edge-tts (no internet?) - the build goes on with the installed $edgeVerzia." -ForegroundColor Yellow
}

# Strings for 'py -c' below: no double quotes (PowerShell 5.1 breaks them for a
# native program, see $edgeKontrola) and no percent sign - Python through a .bat
# goes through cmd.exe, which would take %...% as a variable; hence rate='+0' + chr(37)
# (= '+0%', like edge_rate_str in audio_engine). Instead of a traceback,
# sys.excepthook prints one line "Class: message" - the build quotes it in its message.
# (a) API without the network: the exact call from audio_engine (EdgeTTSCache.ensure) -
# Communicate(text, voice, rate=...) and an async save. If it fails, the new edge-tts
# changed its API: the natural voice in the exe would be dead, so the build stops and
# says how to go back to the last version that worked.
$edgeApi = "import inspect, sys; sys.excepthook = lambda t, e, b: print(t.__name__ + ': ' + str(e)[:160]); import edge_tts; k = edge_tts.Communicate('Zanshin', 'en-GB-SoniaNeural', rate='+0' + chr(37)); ok = inspect.iscoroutinefunction(getattr(k, 'save', None)); ok or print('Communicate.save is not async'); sys.exit(0 if ok else 1)"
$edgeApiDovod = "$(Invoke-Py '-c' $edgeApi)".Trim()
if ($LASTEXITCODE -ne 0) {
    $pyPrikaz = (@($PY.Exe) + $PY.Pre) -join ' '
    if ($edgeVerzia -eq $edgeMin) {
        # even the minimum itself failed - edge-tts didn't change, the problem is around it
        Fail ("edge-tts $edgeVerzia can't be used ($edgeApiDovod) - the problem is probably in one of its dependencies. " +
              "Reinstall it: $pyPrikaz -m pip install --force-reinstall `"edge-tts==$edgeVerzia`" and run the build again.")
    }
    # Last version that worked: one major version lower (8.0 -> <8, the newest 7.x);
    # within the same major version, the newest one before the broken one.
    $edgeHlavna = 0
    if ($edgeVerzia -match '^(\d+)') { $edgeHlavna = [int]$Matches[1] }
    $edgeMinHlavna = 0
    if ($edgeMin -match '^(\d+)') { $edgeMinHlavna = [int]$Matches[1] }
    if ($edgeHlavna -gt $edgeMinHlavna) { $edgeSpat = "edge-tts>=$edgeMin,<$edgeHlavna" }
    else { $edgeSpat = "edge-tts>=$edgeMin,<$edgeVerzia" }
    Fail ("edge-tts $edgeVerzia has changed so that Zanshin can't use it ($edgeApiDovod). " +
          "Go back to the last version that worked: in requirements.txt change the edge-tts line to $edgeSpat and run the build again " +
          "(from source, by hand: $pyPrikaz -m pip install `"$edgeSpat`"). Only a newer Zanshin fixes this for good.")
}
Write-Host "edge-tts $edgeVerzia goes into the build (minimum $edgeMin)" -ForegroundColor Green

# (b) Test word, only with internet (the index probe above): "Zanshin" through
# Microsoft into a temporary file in %TEMP%, which is deleted right away. If it
# fails, the build does NOT stop - the exe also works with the Windows voice, and
# the Update voice button in the app (or the next build with a newer edge-tts)
# fixes the natural voice later. But the message is loud, so it gets seen.
if ($edgePip -ne 0) {
    Write-Host "Skipping the test word (no internet) - the natural voice with edge-tts $edgeVerzia is not verified." -ForegroundColor Yellow
} else {
    $edgeSlovo = "import asyncio, os, sys; sys.excepthook = lambda t, e, b: print(t.__name__ + ': ' + str(e)[:160]); import edge_tts; p = sys.argv[1]; asyncio.run(asyncio.wait_for(edge_tts.Communicate('Zanshin', 'en-GB-SoniaNeural', rate='+0' + chr(37)).save(p), 30)); n = os.path.getsize(p); n or print('empty audio'); sys.exit(0 if n else 1)"
    $edgeSubor = Join-Path $env:TEMP ('zanshin-edge-tts-' + [guid]::NewGuid().ToString('N') + '.mp3')
    $edgeSlovoDovod = "$(Invoke-Py '-c' $edgeSlovo $edgeSubor)".Trim()
    $edgeSlovoKod = $LASTEXITCODE
    Remove-Item -LiteralPath $edgeSubor -Force -ErrorAction SilentlyContinue
    if ($edgeSlovoKod -eq 0) {
        Write-Host "natural voice verified (edge-tts $edgeVerzia)" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "!!! WARNING: Microsoft refuses even edge-tts $edgeVerzia, or its voice service isn't answering right now ($edgeSlovoDovod)." -ForegroundColor Yellow
        Write-Host "!!! The build goes on, but the natural voice doesn't work in it right now - the Windows voice covers the cues." -ForegroundColor Yellow
        Write-Host "!!! To fix it: the Update voice button in the app (once a newer edge-tts is out) or a later build." -ForegroundColor Yellow
        Write-Host ""
    }
}

Invoke-Py '-m' 'PyInstaller' '--version' 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller is missing - installing it..." -ForegroundColor Yellow
    Invoke-Py '-m' 'pip' 'install' 'pyinstaller'
    if ($LASTEXITCODE -ne 0) { Fail "Installing PyInstaller failed." }
}

if (-not (Test-Path "Dandurf.ico")) {
    Write-Host "Dandurf.ico is missing - generating it..." -ForegroundColor Yellow
    Invoke-Py 'make_icon.py'
    if ($LASTEXITCODE -ne 0) { Fail "make_icon.py failed." }
}

# Pre-build check (translations, calls, no keyboard hook, no Steam
# layer). Until now only the Steam build ran it - the public installer didn't.
Write-Host "Pre-build check (check_before_run.py)..." -ForegroundColor DarkGray
$env:PYTHONIOENCODING = 'utf-8'
Invoke-Py 'check_before_run.py'
if ($LASTEXITCODE -ne 0) { Fail "check_before_run.py found a problem - the build was not started." }

# --------------------------------------------------------------------------
# 2/3  Packaging the .exe
# --------------------------------------------------------------------------
Write-Host ""
Write-Host "=== 2/3  Packaging Zanshin.exe ===" -ForegroundColor Cyan

# Windows holds a lock on every running .exe. If the app is running right now
# (typically minimised to the system tray), PyInstaller can't overwrite it and fails
# with "Access is denied". So we close it ourselves.
$running = Get-Process -Name 'Zanshin' -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "The app is running - closing it, otherwise the new build can't be written." -ForegroundColor Yellow
    $running | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# Onedir build (Dandurf.spec) - the result is the folder dist\Zanshin\,
# not a single .exe. We delete all of it first, so no old libraries from
# older versions of the dependencies are left behind.
if (Test-Path "dist\Zanshin") {
    try {
        Remove-Item "dist\Zanshin" -Recurse -Force -ErrorAction Stop
    } catch {
        Fail ("The old dist\Zanshin\ can't be deleted. Close the running app " +
              "(right-click its icon in the system tray -> Quit). " +
              "If it isn't running, an antivirus or an open File Explorer window may be holding a file.")
    }
}

Write-Host "This usually takes 1-3 minutes..." -ForegroundColor DarkGray

Invoke-Py '-m' 'PyInstaller' '--noconfirm' '--clean' 'Dandurf.spec'
if ($LASTEXITCODE -ne 0) { Fail "PyInstaller exited with code $LASTEXITCODE." }
if (-not (Test-Path "dist\Zanshin\Zanshin.exe")) {
    Fail "PyInstaller did not produce dist\Zanshin\Zanshin.exe"
}

$distMb = [math]::Round((Get-ChildItem "dist\Zanshin" -Recurse |
    Measure-Object -Property Length -Sum).Sum / 1MB, 1)
Write-Host "dist\Zanshin\ done ($distMb MB)" -ForegroundColor Green

# --------------------------------------------------------------------------
# 3/3  Installer
# --------------------------------------------------------------------------
Write-Host ""
Write-Host "=== 3/3  Assembling the installer ===" -ForegroundColor Cyan

$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    $found = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($found) { $iscc = $found.Source }
}

if (-not $iscc) {
    Write-Host ""
    # The installer isn't published (no signing certificate) - players don't need it,
    # so we don't send them off to download Inno Setup here. A developer who wants it
    # knows from DEVELOPMENT.md that installing Inno Setup 6 and running the script again is enough.
    Write-Host "Inno Setup not found - installer not built (it isn't needed)." -ForegroundColor Yellow
    Write-Host "DONE: the app is dist\Zanshin\Zanshin.exe - just run it." -ForegroundColor Green
    exit 0
}

# The installer speaks all 11 languages of the app. Inno Setup doesn't ship Chinese,
# the translation is in the project (installer_lang\ChineseSimplified.isl) and MUST be
# UTF-8 with a BOM - without the BOM the compiler would read the characters as ANSI and
# the dialog would show garbage. Better to check it than to ship a broken build.
$zhIsl = "installer_lang\ChineseSimplified.isl"
if (-not (Test-Path $zhIsl)) { Fail "$zhIsl is missing (the installer's Chinese translation)." }
$bom = [IO.File]::ReadAllBytes($zhIsl)[0..2]
if (-not ($bom[0] -eq 0xEF -and $bom[1] -eq 0xBB -and $bom[2] -eq 0xBF)) {
    Fail "$zhIsl is not saved as UTF-8 with BOM - save it that way (e.g. in Notepad: Save as -> UTF-8 with BOM)."
}

& $iscc "Dandurf.iss"
if ($LASTEXITCODE -ne 0) { Fail "Inno Setup exited with code $LASTEXITCODE." }

$setup = Get-ChildItem "installer\*setup.exe" -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $setup) { Fail "Inno Setup did not produce any setup.exe in the installer\ folder." }

$setupMb = [math]::Round($setup.Length / 1MB, 1)
Write-Host ""
Write-Host "DONE: $($setup.FullName) ($setupMb MB)" -ForegroundColor Green
Write-Host "The installer has 11 languages (en, sk, ja, zh, ru, es, de, fr, pt, cs, bg), English is the default."
Write-Host "It installs into %LOCALAPPDATA%\Programs\Zanshin (no UAC)."
Write-Host "User data (settings, recordings, TTS cache) goes to %APPDATA%\Zanshin."
Write-Host "On the first start SmartScreen may warn you - 'More info' -> 'Run anyway'." -ForegroundColor DarkGray
