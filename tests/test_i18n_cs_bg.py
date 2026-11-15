# -*- coding: utf-8 -*-
"""Czech and Bulgarian (0.2) - eleven languages in the app and the installer.

What these tests guard:
  * cs and bg have their OWN translation for every key - except texts the
    author deliberately wrote the same in Slovak and English (names,
    abbreviations, units, symbols: "BPM", "HRPI", "Sumi", "🗑") and a few
    words that really are the same in Czech as in English,
  * the translation does not break {placeholders} or lines, and `tr()` for
    cs/bg never crashes, even when an entry is incomplete (English is used, not
    Slovak),
  * Czech and Bulgarian Windows get their language on the first start,
  * PyInstaller picks up the `i18n_cs_bg.py` module too, and the installer has
    Czech and Bulgarian with all its own messages,
  * the Bulgarian load label ("НАТОВАРВАНЕ") fits on the HUD next to the zone
    word - the HUD neither measures nor clips texts, it draws them at fixed
    places.
"""
import os
import re
import string
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402
import i18n_cs_bg  # noqa: E402
from _zdroj_appky import zdroj_appky  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
NOVE = {"cs": i18n_cs_bg.CS, "bg": i18n_cs_bg.BG}

# Words that really are the same in Czech as in English, although Slovak has
# different ones (valencia / Štart). Everything else equal to EN is a
# translation error.
ZHODA_S_ANGLICTINOU = {
    # (0.3 batch 4: dead "tray.toggle" - Start / Stop - removed from dictionary)
    "cs": {"history.export_col.valence"},  # valence
    "bg": set(),
}


def _read(nazov):
    with open(os.path.join(ROOT, nazov), "rb") as fh:
        return fh.read()


def _placeholdery(text):
    return sorted(meno for _, meno, _, _ in string.Formatter().parse(text) if meno)


class _Hocico:
    """A value for any {placeholder}, even with a format ({slope:+.1f})."""

    def __format__(self, spec):
        return "x"


# --------------------------------------------------------------------------
# Languages
# --------------------------------------------------------------------------

def test_cestina_a_bulharcina_su_medzi_jazykmi():
    assert i18n.LANG_CS == "cs" and i18n.LANG_BG == "bg"
    assert i18n.LANGUAGES[-2:] == ("cs", "bg")
    assert len(i18n.LANGUAGES) == 11


def test_prepinac_ukazuje_nativne_nazvy():
    """Language switch shows each language by its own name (static, no Tk)."""
    src = zdroj_appky()
    blok = src[src.index("LANG_NATIVE_LABELS = {"):]
    blok = blok[:blok.index("}")]
    assert 'LANG_CS: "Čeština"' in blok
    assert 'LANG_BG: "Български"' in blok


def test_kazdy_jazyk_ma_svoj_nazov():
    """The log after a language switch reads `lang.{kod}` (app.on_lang_switch).
    The key is dynamic, so test_i18n_keys does not see it - for Czech and
    Bulgarian it was missing and the raw key went into the log
    ("…prepnuty na: lang.cs")."""
    for kod in i18n.LANGUAGES:
        kluc = f"lang.{kod}"
        assert kluc in i18n.STRINGS, kluc
        for jazyk in i18n.LANGUAGES:
            assert i18n.tr_lang(jazyk, kluc) != kluc, (kluc, jazyk)
    assert i18n.STRINGS["lang.cs"]["cs"] == "Čeština"
    assert i18n.STRINGS["lang.bg"]["bg"] == "Български"


@pytest.mark.parametrize("locale, cakany", [
    ("cs-CZ", "cs"), ("bg-BG", "bg"), ("cs_CZ", "cs"), ("sk-SK", "sk"),
    ("de-AT", "de"), ("pt-BR", "pt"), ("zh-CN", "zh"), ("pl-PL", "en"),
    ("", "en"),
])
def test_jazyk_windowsu(monkeypatch, locale, cakany):
    """Czech Windows got Slovak until 0.2 - now its own Czech."""
    monkeypatch.setattr(i18n, "_win_locale", lambda: locale)
    assert i18n.system_lang() == cakany


# --------------------------------------------------------------------------
# Translations
# --------------------------------------------------------------------------

def test_modul_prekladu_pokryva_presne_vsetky_kluce():
    """Every app key has a Czech and a Bulgarian text and the module carries
    no dead keys (e.g. `slots.add`, which the app no longer has)."""
    for jazyk, preklady in NOVE.items():
        chyba = sorted(set(i18n.STRINGS) - set(preklady))
        navyse = sorted(set(preklady) - set(i18n.STRINGS))
        assert not chyba, f"{jazyk}: chyba preklad pre {chyba[:10]}"
        assert not navyse, f"{jazyk}: kluce, ktore appka nema: {navyse[:10]}"
        for kluc, text in preklady.items():
            assert i18n.STRINGS[kluc][jazyk] == text, (jazyk, kluc)


def test_cs_bg_maju_vlastny_preklad():
    """Where Slovak and English differ, the text is language-specific - cs and
    bg must have their own translation there, not an English substitute.
    Where the author wrote SK and EN the same (names, abbreviations, units,
    symbols), the match is deliberate."""
    for jazyk in NOVE:
        zle = [kluc for kluc, zaznam in i18n.STRINGS.items()
               if zaznam["sk"] != zaznam["en"]
               and zaznam[jazyk] == zaznam["en"]
               and kluc not in ZHODA_S_ANGLICTINOU[jazyk]]
        assert not zle, f"{jazyk}: anglicky text namiesto prekladu: {zle[:15]}"


def test_vynimky_su_naozaj_rovnake():
    """The exception list must not go stale - each must still be a match."""
    for jazyk, kluce in ZHODA_S_ANGLICTINOU.items():
        for kluc in kluce:
            zaznam = i18n.STRINGS[kluc]
            assert zaznam[jazyk] == zaznam["en"] != zaznam["sk"], (jazyk, kluc)


def test_cestina_nie_je_slovencina():
    """Letters Czech lacks - an untranslated Slovak text would have them."""
    for kluc, text in i18n_cs_bg.CS.items():
        assert not set(text) & set("äÄľĽĺĹŕŔôÔ"), kluc


def test_bulharcina_je_v_cyrilike():
    for kluc, text in i18n_cs_bg.BG.items():
        zaznam = i18n.STRINGS[kluc]
        if zaznam["sk"] == zaznam["en"]:
            continue
        slova = re.sub(r"\{\w+(:[^}]*)?\}", "", zaznam["sk"])
        if re.search(r"[^\W\d_]", slova):
            assert re.search("[Ѐ-ӿ]", text), kluc


def test_placeholdery_riadky_a_okraje_sedia():
    for jazyk, preklady in NOVE.items():
        for kluc, text in preklady.items():
            sk = i18n.STRINGS[kluc]["sk"]
            assert text.strip(), (jazyk, kluc)
            assert _placeholdery(text) == _placeholdery(sk), (jazyk, kluc)
            assert text.count("\n") == sk.count("\n"), (jazyk, kluc)
            assert "\\n" not in text, (jazyk, kluc)       # literal backslash+n


@pytest.mark.parametrize("jazyk", ["cs", "bg"])
def test_tr_pre_cs_bg_nikdy_nespadne(jazyk):
    """Every key can be formatted (even with a format like {slope:+.1f})."""
    povodny = i18n._lang["code"]
    try:
        i18n.set_lang(jazyk)
        for kluc, zaznam in i18n.STRINGS.items():
            mena = _placeholdery(zaznam[jazyk])
            text = i18n.tr(kluc, **{m: _Hocico() for m in mena})
            assert isinstance(text, str) and text, kluc
    finally:
        i18n.set_lang(povodny)


def test_neuplny_zaznam_ide_anglicky_a_zly_preklad_nezhodi_okno():
    povodny = i18n._lang["code"]
    i18n.STRINGS["__test.len_sk_en"] = {"sk": "ahoj {meno}", "en": "hi {meno}"}
    i18n.STRINGS["__test.zly_preklad"] = {"sk": "a {n}", "en": "b {n}",
                                          "cs": "c {pocet}", "bg": "d {n"}
    try:
        for jazyk in ("cs", "bg"):
            i18n.set_lang(jazyk)
            assert i18n.tr("__test.len_sk_en", meno="X") == "hi X"
            assert i18n.tr_lang(jazyk, "__test.len_sk_en") == "hi {meno}"
            assert i18n.tr("__test.zly_preklad", n=3) == "b 3"
        i18n.set_lang("en")
        with pytest.raises(KeyError):       # a call error is not hidden
            i18n.tr("__test.zly_preklad", zle=3)
    finally:
        del i18n.STRINGS["__test.len_sk_en"]
        del i18n.STRINGS["__test.zly_preklad"]
        i18n.set_lang(povodny)


def test_sk_en_plni_vsetkych_jedenast_jazykov():
    zaznam = i18n._sk_en("a", "b")
    assert set(zaznam) == set(i18n.LANGUAGES)
    assert zaznam["cs"] == zaznam["bg"] == "b"


# --------------------------------------------------------------------------
# Build and installer
# --------------------------------------------------------------------------

def test_pyinstaller_zoberie_modul_prekladov():
    """Static import in i18n.py (PyInstaller sees it), safeguard in .spec."""
    assert "from i18n_cs_bg import " in _read("i18n.py").decode("utf-8")
    spec = _read("Dandurf.spec").decode("utf-8")
    assert "'i18n_cs_bg'," in spec[spec.index("hiddenimports=["):]


def test_instalator_hovori_jedenastimi_jazykmi():
    raw = _read("Dandurf.iss")
    assert raw.startswith(b"\xef\xbb\xbf") and b"\r\n" not in raw   # BOM + LF
    text = raw.decode("utf-8-sig")
    jazyky = text[text.index("[Languages]"):text.index("[CustomMessages]")]
    mena = re.findall(r'^Name: "(\w+)"', jazyky, re.M)
    assert len(mena) == 11, mena
    assert 'Name: "czech"; MessagesFile: "compiler:Languages\\Czech.isl"' in jazyky
    assert 'Name: "bulgarian"; MessagesFile: "compiler:Languages\\Bulgarian.isl"' in jazyky
    vlastne = text[text.index("[CustomMessages]"):text.index("[Tasks]")]
    hlasky = {}
    for riadok in vlastne.splitlines():
        m = re.match(r"(\w+)\.(\w+)=(.+)$", riadok)
        if m:
            hlasky.setdefault(m.group(2), {})[m.group(1)] = m.group(3)
    assert set(hlasky) >= {"KeepDataQuestion", "KeepDataHint"}
    for sprava, preklady in hlasky.items():
        assert set(preklady) == set(mena), (sprava, sorted(set(mena) - set(preklady)))
        for jazyk, veta in preklady.items():
            if sprava == "KeepDataHint":
                assert "%1" in veta, (jazyk, veta)
    # MsgBox buttons are the system's Ano/Nie - the text must call them that
    assert "Ano" in hlasky["KeepDataHint"]["czech"]
    assert "„Да“" in hlasky["KeepDataHint"]["bulgarian"]


# --------------------------------------------------------------------------
# HUD
# --------------------------------------------------------------------------

def test_stitok_zataze_sa_na_hud_zmesti_vo_vsetkych_jazykoch():
    """Load strip: label on the left, the zone word (or "calibrating...") on
    the right, 9 pt with letter spacing 1,8 - exactly like
    `hud_paint.render_hud`. Nothing is clipped, so free space must remain
    between them."""
    hud_paint = pytest.importorskip("hud_paint")
    if not hud_paint.PIL_AVAILABLE:
        pytest.skip("bez Pillow sa HUD nekresli")
    p = hud_paint.Painter(hud_paint.HUD_WIDTH, hud_paint.HUD_HEIGHT, ss=2)
    sirka_pruhu = hud_paint.HUD_WIDTH - 28.0

    def sirka(text):
        return p.measure(text, 9, kind="label", tracking=1.8)

    for jazyk in i18n.LANGUAGES:
        vlavo = sirka(i18n.tr_lang(jazyk, "hud.load"))
        vpravo = max(
            [sirka(i18n.tr_lang(jazyk, f"hud.zone.{z}").upper())
             for z in ("calm", "raised", "high", "critical")]
            + [sirka(i18n.tr_lang(jazyk, "hud.calibrating").upper().replace("…", "..."))])
        assert vlavo + vpravo + 12 <= sirka_pruhu, (jazyk, vlavo, vpravo)
