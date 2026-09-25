# -*- coding: utf-8 -*-
"""Pad pri importe app konci v crash.log (review 0.2.1, bug 5).

main() predtym najprv importoval app a az potom nastavil sys.excepthook a
threading.excepthook. Import app nataha desiatky modulov; chyba v ktoromkolvek
z nich (chybajuca zavislost, preklep) v appke bez konzoly nezanechala crash.log:
pythonw ju zahodil, zabaleny .exe (console=False) ju ukazal len v okne
PyInstalleru, ktore po zatvoreni zmizne.

Druhy test: pad v konstruktore DandurfApp je v crash.log raz, nie dvakrat
(main() ho zapisoval sam a potom este sys.excepthook).

Test spusti main.py v samostatnom procese ako zabaleny build (sys.frozen,
%APPDATA% presmerovane do tmp), s falosnym app.py, ktory pri importe spadne.
Skutocne logs/ projektu ani skutocny %APPDATA% sa nedotkne.
"""
import ast
import os
import subprocess
import sys
import textwrap

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Spustac: sprava sa ako zabaleny build a GUI moduly nahradi prazdnymi, aby
# test nemenil DPI rezim procesu ani neotvaral okno.
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

# Falosny app.py: pad vo vlakne (threading.excepthook) a potom chybajuca
# zavislost (sys.excepthook) - obe pocas importu app.
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
    # Stara instalacia pod predoslym menom: migracia musi prebehnut aj teraz,
    # ked logging_setup (a s nim paths) ide pred app.
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
    # hlavne vlakno: sys.excepthook bol nastaveny pred importom app
    assert "ModuleNotFoundError" in text
    assert "zanshin_test_chybajuca_zavislost" in text
    # vlakno spustene pocas importu app: threading.excepthook tiez
    assert "simulovany pad vlakna pocas importu app" in text
    # konzola (vyvoj zo zdrojakov) dostane traceback ako predtym
    assert "zanshin_test_chybajuca_zavislost" in vysledok.stderr
    # migracia starych dat prebehla (priecinok logs/ ju nepredbehol)
    assert (data / "dandurf_settings.json").is_file()
    # skutocne logy projektu ostali netknute
    assert [_stav(c) for c in projekt_logy] == pred


def test_pad_v_konstruktore_je_v_crash_logu_raz(tmp_path):
    """main() mal okolo DandurfApp(root) vlastny try/except s log_crash a
    vynimku potom pustil dalej do sys.excepthook, ktory ju zapisal znova.
    Tester, co posle crash.log, by videl dva pady namiesto jedneho."""
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
    # kazdy zaznam zacina riadkom "==== <cas> ====" (logging_setup.log_crash)
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
    """Poradie v main(): najprv hooky, potom `from app import ...`."""
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
    """Tazke moduly sa nesmu natiahnut skor nez treba: app ostava lenivy
    import vnutri main(), na urovni modulu nie."""
    for uzol in _main_py_strom().body:
        if isinstance(uzol, ast.Import):
            assert "app" not in [a.name for a in uzol.names]
        if isinstance(uzol, ast.ImportFrom):
            assert uzol.module != "app"


def test_logging_setup_je_lahky():
    """logging_setup ide teraz pred app - nesmie so sebou tahat GUI ani
    ine tazke zavislosti (inak by sme len presunuli pomaly import)."""
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
