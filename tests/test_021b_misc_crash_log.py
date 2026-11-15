# -*- coding: utf-8 -*-
"""A crash during the app import ends up in crash.log (review 0.2.1, bug 5).

main() used to import app first and only then set sys.excepthook and
threading.excepthook. Importing app pulls in dozens of modules; an error
in any of them (a missing dependency, a typo) left no crash.log in an app
without a console: pythonw threw it away, the packaged .exe
(console=False) showed it only in a PyInstaller window, which disappears
once closed.

Second test: a crash in the DandurfApp constructor is in crash.log once,
not twice (main() wrote it itself and then sys.excepthook did as well).

The test runs main.py in a separate process like a packaged build
(sys.frozen, %APPDATA% redirected to tmp), with a fake app.py that
crashes on import. It does not touch the project's real logs/ or the real
%APPDATA%.
"""
import ast
import os
import subprocess
import sys
import textwrap

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Launcher: behaves like a packaged build and replaces the GUI modules
# with empty ones, so the test does not change the process's DPI mode or
# open a window.
_SPUSTAC = textwrap.dedent("""
    import os, runpy, sys, types
    sys.dont_write_bytecode = True
    ROOT, FALOSNE = sys.argv[1], sys.argv[2]
    sys.path[:0] = [FALOSNE, ROOT]
    sys.frozen = True
    displej = types.ModuleType("display")
    displej.enable_dpi_awareness = lambda: None
    sys.modules["display"] = displej
    ctk = types.ModuleType("customtkinter")
    ctk.CTk = lambda: types.SimpleNamespace()   # "okno" bez Tk
    sys.modules["customtkinter"] = ctk
    runpy.run_path(os.path.join(ROOT, "main.py"), run_name="__main__")
""")

# Fake app.py: a crash in a thread (threading.excepthook) and then a
# missing dependency (sys.excepthook) - both during the app import.
_FALOSNA_APP = textwrap.dedent("""
    import threading

    def _pad():
        raise RuntimeError("simulovany pad vlakna pocas importu app")

    vlakno = threading.Thread(target=_pad)
    vlakno.start()
    vlakno.join()

    import zanshin_test_chybajuca_zavislost  # noqa: F401
""")


def _stav(cesta):
    try:
        st = os.stat(cesta)
        return st.st_size, st.st_mtime_ns
    except OSError:
        return None


def test_chyba_pri_importe_app_zapise_crash_log(tmp_path):
    appdata = tmp_path / "appdata"
    falosne = tmp_path / "falosne"
    falosne.mkdir()
    (falosne / "app.py").write_text(_FALOSNA_APP, encoding="utf-8")
    spustac = tmp_path / "spustac.py"
    spustac.write_text(_SPUSTAC, encoding="utf-8")
    # An old installation under the previous name: the migration must run
    # now too, when logging_setup (and paths with it) goes before app.
    stara = appdata / "Zanshin DojoSync"
    stara.mkdir(parents=True)
    (stara / "dandurf_settings.json").write_text("{}", encoding="utf-8")

    projekt_logy = [os.path.join(ROOT, "logs", m) for m in ("crash.log", "app.log")]
    pred = [_stav(c) for c in projekt_logy]

    env = dict(os.environ, APPDATA=str(appdata), PYTHONDONTWRITEBYTECODE="1",
               PYTHONIOENCODING="utf-8")
    vysledok = subprocess.run(
        [sys.executable, "-B", str(spustac), ROOT, str(falosne)],
        cwd=str(tmp_path), env=env, capture_output=True, text=True,
        encoding="utf-8", timeout=120)

    assert vysledok.returncode != 0, vysledok.stdout + vysledok.stderr
    data = appdata / "Zanshin"
    crash = data / "logs" / "crash.log"
    assert crash.is_file(), vysledok.stderr
    text = crash.read_text(encoding="utf-8")
    # main thread: sys.excepthook was set before the app import
    assert "ModuleNotFoundError" in text
    assert "zanshin_test_chybajuca_zavislost" in text
    # a thread started during the app import: threading.excepthook too
    assert "simulovany pad vlakna pocas importu app" in text
    # the console (development from source) gets the traceback as before
    assert "zanshin_test_chybajuca_zavislost" in vysledok.stderr
    # the migration of old data ran (the logs/ folder did not get ahead of it)
    assert (data / "dandurf_settings.json").is_file()
    # the project's real logs stayed untouched
    assert [_stav(c) for c in projekt_logy] == pred


def test_pad_v_konstruktore_je_v_crash_logu_raz(tmp_path):
    """main() had its own try/except with log_crash around DandurfApp(root)
    and then let the exception through to sys.excepthook, which wrote it
    again. A tester sending crash.log would have seen two crashes instead
    of one."""
    appdata = tmp_path / "appdata"
    falosne = tmp_path / "falosne"
    falosne.mkdir()
    (falosne / "app.py").write_text(textwrap.dedent("""
        class DandurfApp:
            def __init__(self, root):
                raise RuntimeError("simulovany pad v konstruktore")
    """), encoding="utf-8")
    spustac = tmp_path / "spustac.py"
    spustac.write_text(_SPUSTAC, encoding="utf-8")

    env = dict(os.environ, APPDATA=str(appdata), PYTHONDONTWRITEBYTECODE="1",
               PYTHONIOENCODING="utf-8")
    vysledok = subprocess.run(
        [sys.executable, "-B", str(spustac), ROOT, str(falosne)],
        cwd=str(tmp_path), env=env, capture_output=True, text=True,
        encoding="utf-8", timeout=120)

    assert vysledok.returncode != 0, vysledok.stdout + vysledok.stderr
    crash = appdata / "Zanshin" / "logs" / "crash.log"
    assert crash.is_file(), vysledok.stderr
    text = crash.read_text(encoding="utf-8")
    # each record starts with "==== <time> ====" (logging_setup.log_crash)
    assert text.count("\n==== ") == 1, text
    assert text.count("RuntimeError: simulovany pad v konstruktore") == 1, text
    assert "simulovany pad v konstruktore" in vysledok.stderr


def _main_py_strom():
    with open(os.path.join(ROOT, "main.py"), encoding="utf-8") as fh:
        return ast.parse(fh.read())


def _funkcia(strom, meno):
    for uzol in strom.body:
        if isinstance(uzol, ast.FunctionDef) and uzol.name == meno:
            return uzol
    raise AssertionError(f"main.py nema funkciu {meno}")


def test_hooky_su_pred_importom_app():
    """Order in main(): hooks first, then `from app import ...`."""
    telo = _funkcia(_main_py_strom(), "main").body
    hooky = next(i for i, u in enumerate(telo)
                 if "_install_crash_hooks" in ast.dump(u))
    app = next(i for i, u in enumerate(telo)
               if isinstance(u, ast.ImportFrom) and u.module == "app")
    assert hooky < app


def test_install_crash_hooks_nastavi_oba_hooky():
    fn = _funkcia(_main_py_strom(), "_install_crash_hooks")
    nastavene = {ciel.value.id
                 for uzol in ast.walk(fn) if isinstance(uzol, ast.Assign)
                 for ciel in uzol.targets
                 if isinstance(ciel, ast.Attribute) and ciel.attr == "excepthook"
                 and isinstance(ciel.value, ast.Name)}
    assert nastavene == {"sys", "threading"}


def test_app_sa_neimportuje_na_urovni_modulu():
    """Heavy modules must not be loaded earlier than needed: app stays a
    lazy import inside main(), not at module level."""
    for uzol in _main_py_strom().body:
        if isinstance(uzol, ast.Import):
            assert "app" not in [a.name for a in uzol.names]
        if isinstance(uzol, ast.ImportFrom):
            assert uzol.module != "app"


def test_logging_setup_je_lahky():
    """logging_setup now goes before app - it must not drag in the GUI or
    other heavy dependencies (otherwise we would just have moved the slow
    import)."""
    kod = ("import sys; sys.dont_write_bytecode = True; "
           "sys.path.insert(0, sys.argv[1]); import logging_setup; "
           "tazke = ('tkinter', 'customtkinter', 'app', 'pygame', 'edge_tts', "
           "'PIL', 'psutil', 'pyttsx3', 'numpy'); "
           "print(','.join(m for m in tazke if m in sys.modules))")
    vysledok = subprocess.run(
        [sys.executable, "-B", "-c", kod, ROOT],
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        capture_output=True, text=True, timeout=60)
    assert vysledok.returncode == 0, vysledok.stderr
    assert vysledok.stdout.strip() == ""
