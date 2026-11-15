# -*- coding: utf-8 -*-
"""0.2.1c: gui_harness_auto.py keeps the heart rate history even when cut off.

The harness runs on the Zanshin data of the sources next to main.py. It
put the heart rate history (hr_sessions.json, hr_insights.json) aside only
in MEMORY and the last `finally` did not restore it - Ctrl+C, closing the
window or a crash between putting aside and restoring deleted it forever.
The settings backup, in turn, was overwritten by the next run with
settings that the interrupted run had changed.

Now all three files are copied to disk next to the original before the
first touch (`<subor>.pred-harnessom`), restored on every way out, and
after a hard kill the next run restores them right at the start - without
blindly overwriting a file that the app wrote in the meantime.

The harness cannot be started in tests (Tk window, real mouse). So the
tests pick only the backup functions out of its source (ast) and run them
over a temporary folder - they do not touch the project's real data.
"""
import ast
import fnmatch
import glob
import json
import os
import subprocess
import sys
import textwrap

import pytest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS = os.path.join(KOREN, "gui_harness_auto.py")
FUNKCIE = ("_zapis_kopiu", "obnov_po_prerusenom_behu", "zaloz_zalohy",
           "vrat_zalohy")
KONSTANTY = ("ZALOHA", "NEBOL")


def _zdroj():
    with open(HARNESS, encoding="utf-8-sig") as fh:
        return fh.read()


def _kod_zalohy():
    """Only the harness backup definitions - no Tk, app or folder change."""
    src = _zdroj()
    uzly = []
    for uzol in ast.parse(src).body:
        if isinstance(uzol, ast.FunctionDef) and uzol.name in FUNKCIE:
            uzly.append(uzol)
        elif (isinstance(uzol, ast.Assign) and len(uzol.targets) == 1
              and getattr(uzol.targets[0], "id", None) in KONSTANTY):
            uzly.append(uzol)
    assert len(uzly) == len(FUNKCIE) + len(KONSTANTY)
    return "import filecmp, os, shutil, time\n" + "\n\n".join(
        ast.get_source_segment(src, u) for u in uzly)


def _zaloha():
    ns = {}
    exec(compile(_kod_zalohy(), HARNESS, "exec"), ns)
    return ns


def _data(tmp_path):
    """Temp "player data": settings and history; no insights before the run."""
    nastavenia = tmp_path / "dandurf_settings.json"
    relacie = tmp_path / "hr_sessions.json"
    postrehy = tmp_path / "hr_insights.json"
    nastavenia.write_text('{"theme": "sumi", "tour_seen": false}', encoding="utf-8")
    relacie.write_text('[{"started": 1, "duration_s": 3600}]', encoding="utf-8")
    return nastavenia, relacie, postrehy


def _cesty(tmp_path):
    return [str(p) for p in _data(tmp_path)]


def _beh_harnessu_po_zalohe(nastavenia, relacie, postrehy):
    """What the harness does with the data: fills in theme/tour_seen, the empty
    history test deletes the files, then writes synthetic sessions and
    insights."""
    nastavenia.write_text('{"theme": "zen", "tour_seen": true}', encoding="utf-8")
    os.remove(relacie)
    relacie.write_text('[{"synteticka": true}]', encoding="utf-8")
    postrehy.write_text('[{"key": "resting_up"}]', encoding="utf-8")


def _zostatky(tmp_path):
    return sorted(os.path.basename(p) for p in glob.glob(str(tmp_path / "*.pred-*")))


# --------------------------------------------------------------------------
# The backup is on disk before the harness touches anything
# --------------------------------------------------------------------------

def test_zaloha_je_na_disku_a_normalny_koniec_ju_vrati(tmp_path):
    z = _zaloha()
    nastavenia, relacie, postrehy = _data(tmp_path)
    cesty = [str(nastavenia), str(relacie), str(postrehy)]
    povodne = {p: open(p, "rb").read() for p in cesty[:2]}

    z["zaloz_zalohy"](cesty)
    for p in cesty[:2]:
        assert open(p + ".pred-harnessom", "rb").read() == povodne[p]
    assert os.path.exists(str(postrehy) + ".pred-harnessom-nebol"), \
        "subor, ktory pred behom nebol, ma znacku"

    _beh_harnessu_po_zalohe(nastavenia, relacie, postrehy)
    z["vrat_zalohy"](cesty)
    for p in cesty[:2]:
        assert open(p, "rb").read() == povodne[p], p
    assert not postrehy.exists(), "co pred behom nebolo, beh po sebe zmaze"
    assert _zostatky(tmp_path) == [], "po normalnom konci nic neostane"
    assert not list(tmp_path.glob("*.tmp"))

    # `finish()`, `finally` and `atexit` may call it one after another.
    z["vrat_zalohy"](cesty)
    for p in cesty[:2]:
        assert open(p, "rb").read() == povodne[p], p


def test_vratenie_uprostred_behu_zalohu_necha(tmp_path):
    """After the history test (`_vrat_historiu_tepu`) the history is restored,
    but the backup stays - the app still writes to the files and the end of
    the run restores again."""
    z = _zaloha()
    nastavenia, relacie, postrehy = _data(tmp_path)
    cesty = [str(relacie), str(postrehy)]
    z["zaloz_zalohy"](cesty)
    _beh_harnessu_po_zalohe(nastavenia, relacie, postrehy)
    z["vrat_zalohy"](cesty, nechat_zalohy=True)
    assert relacie.read_text(encoding="utf-8") == '[{"started": 1, "duration_s": 3600}]'
    assert not postrehy.exists()
    assert os.path.exists(str(relacie) + ".pred-harnessom")
    assert os.path.exists(str(postrehy) + ".pred-harnessom-nebol")


# --------------------------------------------------------------------------
# Interrupted run: the data comes back
# --------------------------------------------------------------------------

def _spusti(skript, tmp_path):
    """Script in a separate process over a temporary folder."""
    subor = tmp_path / "beh.py"
    subor.write_text(skript, encoding="utf-8")
    return subprocess.run([sys.executable, str(subor)], cwd=str(tmp_path),
                          capture_output=True, text=True, timeout=60)


def test_tvrde_zabitie_medzi_odlozenim_a_vratenim_dalsi_beh_vrati(tmp_path):
    """The process ends with `os._exit` in the middle of the history test -
    neither `finally` nor `atexit` runs, exactly as with a kill from Task
    Manager. A history in memory would be gone; the backup on disk gives
    it back to the next run."""
    nastavenia, relacie, postrehy = _data(tmp_path)
    povodne_n = nastavenia.read_bytes()
    povodne_r = relacie.read_bytes()
    skript = _kod_zalohy() + textwrap.dedent("""

        import atexit
        cesty = %r
        zaloz_zalohy(cesty)
        atexit.register(vrat_zalohy, cesty)
        with open(cesty[0], "w") as fh:
            fh.write('{"theme": "zen", "tour_seen": true}')
        os.remove(cesty[1])                 # test prazdnej historie
        os._exit(1)                         # zabitie pred vratenim
    """) % ([str(nastavenia), str(relacie), str(postrehy)],)
    vysledok = _spusti(skript, tmp_path)
    assert vysledok.returncode == 1, vysledok.stderr
    assert not relacie.exists(), "zabitie naozaj preskocilo vratenie"
    assert os.path.exists(str(relacie) + ".pred-harnessom")

    # Next run: first it restores what was left.
    z = _zaloha()
    vratene = z["obnov_po_prerusenom_behu"](
        [str(nastavenia), str(relacie), str(postrehy)], znacka="T")
    assert relacie.read_bytes() == povodne_r
    assert nastavenia.read_bytes() == povodne_n
    assert not postrehy.exists()
    assert sorted(vratene) == sorted([str(nastavenia), str(relacie), str(postrehy)])
    # Settings changed by the interrupted run were not overwritten blindly -
    # they are set aside next to it.
    bokom = tmp_path / "dandurf_settings.json.pred-obnovou-T"
    assert json.loads(bokom.read_text(encoding="utf-8")) == {
        "theme": "zen", "tour_seen": True}
    assert _zostatky(tmp_path) == ["dandurf_settings.json.pred-obnovou-T"]

    # And the new run can make a fresh backup from the restored data.
    z["zaloz_zalohy"]([str(nastavenia), str(relacie), str(postrehy)])
    assert (tmp_path / "hr_sessions.json.pred-harnessom").read_bytes() == povodne_r


def test_ctrl_c_alebo_pad_pred_mainloop_vrati_cez_atexit(tmp_path):
    """An exception (KeyboardInterrupt, a crash while building the window)
    outside the `try` around mainloop: the interpreter ends normally and
    `atexit` restores the files right away."""
    nastavenia, relacie, postrehy = _data(tmp_path)
    povodne_r = relacie.read_bytes()
    skript = _kod_zalohy() + textwrap.dedent("""

        import atexit
        cesty = %r
        zaloz_zalohy(cesty)
        atexit.register(vrat_zalohy, cesty)
        os.remove(cesty[1])
        with open(cesty[2], "w") as fh:
            fh.write("[]")
        raise KeyboardInterrupt
    """) % ([str(nastavenia), str(relacie), str(postrehy)],)
    vysledok = _spusti(skript, tmp_path)
    assert vysledok.returncode != 0
    assert "KeyboardInterrupt" in vysledok.stderr
    assert relacie.read_bytes() == povodne_r
    assert not postrehy.exists()
    assert _zostatky(tmp_path) == []


def test_novsi_subor_z_appky_sa_naslepo_neprepise(tmp_path):
    """After an interrupted run the player starts the app before the harness
    and plays a session - it is written to hr_sessions.json. The next
    harness restores the history from before the harness, but does not
    overwrite the newer file: it leaves it next to it, nothing is lost."""
    z = _zaloha()
    nastavenia, relacie, postrehy = _data(tmp_path)
    cesty = [str(nastavenia), str(relacie), str(postrehy)]
    povodne_r = relacie.read_bytes()
    z["zaloz_zalohy"](cesty)
    _beh_harnessu_po_zalohe(nastavenia, relacie, postrehy)
    # ... kill; then the app writes a new real session:
    relacie.write_text('[{"synteticka": true}, {"started": 99, "nova": true}]',
                       encoding="utf-8")

    z["obnov_po_prerusenom_behu"](cesty, znacka="T")
    assert relacie.read_bytes() == povodne_r
    bokom = tmp_path / "hr_sessions.json.pred-obnovou-T"
    assert '"nova": true' in bokom.read_text(encoding="utf-8")
    # insights did not exist before the run - what is in their place
    # goes aside too
    assert (tmp_path / "hr_insights.json.pred-obnovou-T").exists()
    assert not postrehy.exists()


def test_zhodny_subor_sa_neodklada(tmp_path):
    """Run killed before it changed anything: nothing needs to be set aside."""
    z = _zaloha()
    _nastavenia, relacie, _postrehy = _data(tmp_path)
    z["zaloz_zalohy"]([str(relacie)])
    z["obnov_po_prerusenom_behu"]([str(relacie)], znacka="T")
    assert _zostatky(tmp_path) == []
    assert relacie.read_text(encoding="utf-8") == '[{"started": 1, "duration_s": 3600}]'


def test_nevratena_zaloha_sa_neprepise(tmp_path):
    """When the backup from an interrupted run cannot be restored (e.g. a
    locked file), a new run does not write a new one over it - that was
    how settings got lost."""
    z = _zaloha()
    _nastavenia, relacie, _postrehy = _data(tmp_path)
    (tmp_path / "hr_sessions.json.pred-harnessom").write_text("POVODNE", encoding="utf-8")
    with pytest.raises(SystemExit):
        z["zaloz_zalohy"]([str(relacie)])
    assert (tmp_path / "hr_sessions.json.pred-harnessom").read_text(
        encoding="utf-8") == "POVODNE"


# --------------------------------------------------------------------------
# The harness really uses this - and the backup names do not go to GitHub
# --------------------------------------------------------------------------

def test_harness_zalohuje_skor_nez_sa_dotkne_dat_a_vracia_na_kazdej_ceste():
    src = _zdroj()
    strom = ast.parse(src)
    # Only code that runs when the script is started (not function bodies -
    # those run only when someone calls them).
    hore = [u for s in strom.body
            if not isinstance(s, (ast.FunctionDef, ast.ClassDef))
            for u in ast.walk(s)]

    def riadok_volania(meno):
        riadky = [u.lineno for u in hore if isinstance(u, ast.Call)
                  and getattr(u.func, "id", None) == meno]
        assert riadky, meno
        return min(riadky)

    obnov = riadok_volania("obnov_po_prerusenom_behu")
    zaloz = riadok_volania("zaloz_zalohy")
    zapis_nastaveni = min(u.lineno for u in hore
                          if isinstance(u, ast.Call)
                          and getattr(u.func, "id", None) == "open"
                          and any(isinstance(a, ast.Constant) and a.value == "w"
                                  for a in u.args))
    import_appky = min(u.lineno for u in strom.body
                       if isinstance(u, ast.ImportFrom) and u.module == "app")
    assert obnov < zaloz < zapis_nastaveni < import_appky
    assert "atexit.register(vrat_zalohy, ODLOZENE)" in src
    # 0.3 batch 4: also sessions that failed to save (hr_session_pending.json)
    assert ("ODLOZENE = (SETTINGS, HR_SESSIONS, HR_INSIGHTS, HR_SESSION_OPEN, "
            "SETTINGS_BAK,\n            HR_SESSION_PENDING)") in src
    assert 'HR_SESSION_PENDING = os.path.join(PROJ, "hr_session_pending.json")' in src

    # the last `finally` and `finish()` (os._exit skips finally and atexit)
    posledny_try = [u for u in strom.body if isinstance(u, ast.Try)][-1]
    assert "vrat_zalohy(ODLOZENE)" in ast.get_source_segment(
        src, posledny_try.finalbody[0])
    finish = next(u for u in strom.body
                  if isinstance(u, ast.FunctionDef) and u.name == "finish")
    assert "vrat_zalohy(ODLOZENE)" in ast.get_source_segment(src, finish)

    # the history test deletes only a file that has a backup on disk;
    # nothing in memory
    assert "_hr_backups" not in src
    odloz = next(u for u in strom.body
                 if isinstance(u, ast.FunctionDef) and u.name == "_odloz_historiu_tepu")
    assert "p + ZALOHA" in ast.get_source_segment(src, odloz)


def test_mena_zaloh_pokryva_gitignore():
    with open(os.path.join(KOREN, ".gitignore"), encoding="utf-8") as fh:
        vzory = [r.strip() for r in fh
                 if r.strip() and not r.startswith("#") and "/" not in r.strip()]
    for meno in ("dandurf_settings.json", "hr_sessions.json", "hr_insights.json",
                 "hr_session_open.json", "dandurf_settings.json.bak"):
        for pripona in (".pred-harnessom", ".pred-harnessom-nebol",
                        ".pred-harnessom.tmp", ".pred-obnovou-20260925-120000",
                        ".pred-obnovou-20260925-120000-2"):
            subor = meno + pripona
            assert any(fnmatch.fnmatch(subor, v) for v in vzory), subor
