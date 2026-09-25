# -*- coding: utf-8 -*-
"""0.2.1c: gui_harness_auto.py neprida o historiu tepu ani po preruseni.

Harness bezi nad datami Zanshinu zo zdrojakov vedla main.py. Historiu tepu
(hr_sessions.json, hr_insights.json) odkladal len v PAMATI a posledny
`finally` ju nevracal - Ctrl+C, zavretie okna ci pad medzi odlozenim a
vratenim ju zmazali navzdy. Zalohu nastaveni zas dalsi beh prepisal
nastaveniami, ktore zmenil preruseny beh.

Teraz sa vsetky tri subory pred prvym dotykom kopiruju na disk vedla
originalu (`<subor>.pred-harnessom`), vracaju sa na kazdej ceste von a po
tvrdom zabiti ich vrati dalsi beh hned na zaciatku - bez toho, aby naslepo
prepisal subor, ktory medzitym zapisala appka.

Harness sa v testoch spustit neda (Tk okno, realna mys). Testy preto z
jeho zdrojaku vyberu len funkcie zalohy (ast) a spustia ich nad docasnym
priecinkom - ozajstnych dat projektu sa nedotknu.
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
    """Len definicie zalohy z harnessu - bez Tk, appky a zmeny priecinka."""
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
    """Docasne "data hraca": nastavenia a historia, insights pred behom nie su."""
    nastavenia = tmp_path / "dandurf_settings.json"
    relacie = tmp_path / "hr_sessions.json"
    postrehy = tmp_path / "hr_insights.json"
    nastavenia.write_text('{"theme": "sumi", "tour_seen": false}', encoding="utf-8")
    relacie.write_text('[{"started": 1, "duration_s": 3600}]', encoding="utf-8")
    return nastavenia, relacie, postrehy


def _cesty(tmp_path):
    return [str(p) for p in _data(tmp_path)]


def _beh_harnessu_po_zalohe(nastavenia, relacie, postrehy):
    """To, co harness robi s datami: doplni temu/tour_seen, test prazdnej
    historie subory zmaze, potom zapise synteticke relacie a postrehy."""
    nastavenia.write_text('{"theme": "zen", "tour_seen": true}', encoding="utf-8")
    os.remove(relacie)
    relacie.write_text('[{"synteticka": true}]', encoding="utf-8")
    postrehy.write_text('[{"key": "resting_up"}]', encoding="utf-8")


def _zostatky(tmp_path):
    return sorted(os.path.basename(p) for p in glob.glob(str(tmp_path / "*.pred-*")))


# --------------------------------------------------------------------------
# Zaloha je na disku skor, nez sa harness cohokolvek dotkne
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

    # `finish()`, `finally` aj `atexit` ho mozu zavolat po sebe.
    z["vrat_zalohy"](cesty)
    for p in cesty[:2]:
        assert open(p, "rb").read() == povodne[p], p


def test_vratenie_uprostred_behu_zalohu_necha(tmp_path):
    """Po teste historie (`_vrat_historiu_tepu`) sa historia vrati, ale
    zaloha ostava - appka do suborov este pise a koniec behu vracia znova."""
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
# Preruseny beh: data sa vratia
# --------------------------------------------------------------------------

def _spusti(skript, tmp_path):
    """Skript v samostatnom procese nad docasnym priecinkom."""
    subor = tmp_path / "beh.py"
    subor.write_text(skript, encoding="utf-8")
    return subprocess.run([sys.executable, str(subor)], cwd=str(tmp_path),
                          capture_output=True, text=True, timeout=60)


def test_tvrde_zabitie_medzi_odlozenim_a_vratenim_dalsi_beh_vrati(tmp_path):
    """Proces skonci `os._exit` uprostred testu historie - nebezi `finally`
    ani `atexit`, presne ako pri zabiti z Task Managera. Historia v pamati
    by bola prec; zaloha na disku ju dalsiemu behu vrati."""
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

    # Dalsi beh: najprv vrati, co ostalo.
    z = _zaloha()
    vratene = z["obnov_po_prerusenom_behu"](
        [str(nastavenia), str(relacie), str(postrehy)], znacka="T")
    assert relacie.read_bytes() == povodne_r
    assert nastavenia.read_bytes() == povodne_n
    assert not postrehy.exists()
    assert sorted(vratene) == sorted([str(nastavenia), str(relacie), str(postrehy)])
    # Nastavenia zmenene prerusenym behom sa neprepisali naslepo - su vedla.
    bokom = tmp_path / "dandurf_settings.json.pred-obnovou-T"
    assert json.loads(bokom.read_text(encoding="utf-8")) == {
        "theme": "zen", "tour_seen": True}
    assert _zostatky(tmp_path) == ["dandurf_settings.json.pred-obnovou-T"]

    # A novy beh si moze zalozit cerstvu zalohu z vratenych dat.
    z["zaloz_zalohy"]([str(nastavenia), str(relacie), str(postrehy)])
    assert (tmp_path / "hr_sessions.json.pred-harnessom").read_bytes() == povodne_r


def test_ctrl_c_alebo_pad_pred_mainloop_vrati_cez_atexit(tmp_path):
    """Vynimka (KeyboardInterrupt, pad pri stavbe okna) mimo `try` okolo
    mainloop: interpreter konci normalne a `atexit` subory vrati hned."""
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
    """Po prerusenom behu hrac spusti appku skor nez harness a odohra
    relaciu - zapise sa do hr_sessions.json. Dalsi harness vrati historiu
    spred harnessu, ale novsi subor neprepise: necha ho vedla, nic sa
    nestrati."""
    z = _zaloha()
    nastavenia, relacie, postrehy = _data(tmp_path)
    cesty = [str(nastavenia), str(relacie), str(postrehy)]
    povodne_r = relacie.read_bytes()
    z["zaloz_zalohy"](cesty)
    _beh_harnessu_po_zalohe(nastavenia, relacie, postrehy)
    # ... zabitie; potom appka zapise novu ozajstnu relaciu:
    relacie.write_text('[{"synteticka": true}, {"started": 99, "nova": true}]',
                       encoding="utf-8")

    z["obnov_po_prerusenom_behu"](cesty, znacka="T")
    assert relacie.read_bytes() == povodne_r
    bokom = tmp_path / "hr_sessions.json.pred-obnovou-T"
    assert '"nova": true' in bokom.read_text(encoding="utf-8")
    # insights pred behom neboli - to, co je na ich mieste, tiez ide vedla
    assert (tmp_path / "hr_insights.json.pred-obnovou-T").exists()
    assert not postrehy.exists()


def test_zhodny_subor_sa_neodklada(tmp_path):
    """Beh zabity skor, nez nieco zmenil: vratenie netreba drzat vedla."""
    z = _zaloha()
    _nastavenia, relacie, _postrehy = _data(tmp_path)
    z["zaloz_zalohy"]([str(relacie)])
    z["obnov_po_prerusenom_behu"]([str(relacie)], znacka="T")
    assert _zostatky(tmp_path) == []
    assert relacie.read_text(encoding="utf-8") == '[{"started": 1, "duration_s": 3600}]'


def test_nevratena_zaloha_sa_neprepise(tmp_path):
    """Ked sa zaloha z preruseneho behu vratit nepodari (napr. zamknuty
    subor), novy beh cez nu nezapise novu - to bola strata nastaveni."""
    z = _zaloha()
    _nastavenia, relacie, _postrehy = _data(tmp_path)
    (tmp_path / "hr_sessions.json.pred-harnessom").write_text("POVODNE", encoding="utf-8")
    with pytest.raises(SystemExit):
        z["zaloz_zalohy"]([str(relacie)])
    assert (tmp_path / "hr_sessions.json.pred-harnessom").read_text(
        encoding="utf-8") == "POVODNE"


# --------------------------------------------------------------------------
# Harness to naozaj pouziva - a mena zaloh nejdu na GitHub
# --------------------------------------------------------------------------

def test_harness_zalohuje_skor_nez_sa_dotkne_dat_a_vracia_na_kazdej_ceste():
    src = _zdroj()
    strom = ast.parse(src)
    # Len kod, ktory bezi pri spusteni skriptu (nie tela funkcii - tie bezia
    # az ked ich niekto zavola).
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
    assert "ODLOZENE = (SETTINGS, HR_SESSIONS, HR_INSIGHTS)" in src

    # posledny `finally` aj `finish()` (os._exit preskoci finally aj atexit)
    posledny_try = [u for u in strom.body if isinstance(u, ast.Try)][-1]
    assert "vrat_zalohy(ODLOZENE)" in ast.get_source_segment(
        src, posledny_try.finalbody[0])
    finish = next(u for u in strom.body
                  if isinstance(u, ast.FunctionDef) and u.name == "finish")
    assert "vrat_zalohy(ODLOZENE)" in ast.get_source_segment(src, finish)

    # test historie maze len subor so zalohou na disku; nic v pamati
    assert "_hr_backups" not in src
    odloz = next(u for u in strom.body
                 if isinstance(u, ast.FunctionDef) and u.name == "_odloz_historiu_tepu")
    assert "p + ZALOHA" in ast.get_source_segment(src, odloz)


def test_mena_zaloh_pokryva_gitignore():
    with open(os.path.join(KOREN, ".gitignore"), encoding="utf-8") as fh:
        vzory = [r.strip() for r in fh
                 if r.strip() and not r.startswith("#") and "/" not in r.strip()]
    for meno in ("dandurf_settings.json", "hr_sessions.json", "hr_insights.json"):
        for pripona in (".pred-harnessom", ".pred-harnessom-nebol",
                        ".pred-harnessom.tmp", ".pred-obnovou-20260925-120000",
                        ".pred-obnovou-20260925-120000-2"):
            subor = meno + pripona
            assert any(fnmatch.fnmatch(subor, v) for v in vzory), subor
