# -*- coding: utf-8 -*-
"""Background photo — the mechanism, not the look.

These tests have one purpose only: that the photo can be swapped for
another without anything breaking, and that its absence never brings the
window down.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import background  # noqa: E402

pytestmark = pytest.mark.skipif(not background.PIL_AVAILABLE,
                                reason="pillow nie je nainštalovaný")


@pytest.fixture(autouse=True)
def cista_cache():
    background.forget()
    background._warned = False
    yield
    background.forget()
    background._warned = False


# --------------------------------------------------------------------------
# One place to change
# --------------------------------------------------------------------------

def test_nazov_suboru_je_len_na_jednom_mieste():
    """Whoever changes the photo changes `IMAGE_NAME` and nothing else. If the
    name appeared elsewhere too, one day it would get changed in one place
    only and the app would look for a file that is not there."""
    koren = os.path.join(os.path.dirname(__file__), "..")
    najdene = []
    for meno in sorted(os.listdir(koren)):
        if not meno.endswith(".py") or meno == "background.py":
            continue
        with open(os.path.join(koren, meno), encoding="utf-8-sig") as fh:
            if background.IMAGE_NAME in fh.read():
                najdene.append(meno)
    assert not najdene, f"názov fotky je natvrdo aj v {najdene}"


def test_ked_fotka_nie_je_appka_kresli_dalej(monkeypatch, tmp_path):
    """The photo is decoration, not part of the function. A missing file must
    not bring the window down — `load` just returns None and the caller
    draws nothing."""
    monkeypatch.setattr(background.paths, "images_dir", lambda: str(tmp_path))
    spravy = []
    assert background.image_path() is None
    assert background.available() is False
    assert background.load(800, 600, 0.1, log=spravy.append) is None
    assert len(spravy) == 1, "má sa to zalogovať raz"
    # the second call no longer floods the log
    assert background.load(800, 600, 0.1, log=spravy.append) is None
    assert len(spravy) == 1


def test_stary_pas_uz_nie_je_zaloha(monkeypatch, tmp_path):
    """The old band `dojo_band.jpg` from version 2.0 is in _archiv (0.2) - it
    was never loaded at runtime. If it stayed on disk, the app does not
    look for it and draws on without a photo."""
    from PIL import Image
    monkeypatch.setattr(background.paths, "images_dir", lambda: str(tmp_path))
    assert not hasattr(background, "FALLBACK_NAME")
    Image.new("RGB", (1100, 190), "#203040").save(tmp_path / "dojo_band.jpg")
    assert background.image_path() is None
    assert background.load(800, 600, 0.1) is None
    # and when the new photo is in place, it is found
    Image.new("RGB", (1024, 574), "#203040").save(
        tmp_path / (background.IMAGE_NAME + ".jpg"))
    assert os.path.basename(background.image_path()) == background.IMAGE_NAME + ".jpg"


# --------------------------------------------------------------------------
# Subtlety
# --------------------------------------------------------------------------

def test_jemnost_ma_strop():
    """Above the cap, small text in the panels stops being readable — and
    there are nine languages of it, including Japanese."""
    assert background.clamp_opacity(0.9) == background.MAX_OPACITY
    assert background.clamp_opacity(-1) == 0.0
    assert background.clamp_opacity(0.1) == pytest.approx(0.1)


@pytest.mark.parametrize("nezmysel", ["", None, "veľa", float("nan"), []])
def test_nezmyselna_jemnost_padne_na_predvolenu(nezmysel):
    assert background.clamp_opacity(nezmysel) == background.DEFAULT_OPACITY


def test_nulova_jemnost_znamena_nekreslit(monkeypatch, tmp_path):
    from PIL import Image
    monkeypatch.setattr(background.paths, "images_dir", lambda: str(tmp_path))
    Image.new("RGB", (1024, 574), "#203040").save(tmp_path / (background.IMAGE_NAME + ".jpg"))
    assert background.load(400, 300, 0.0) is None


def test_predvolena_jemnost_je_nizka():
    """The whole design rests on catching the „natiahnuté" (Armed) ring out of
    the corner of your eye. A striking photo behind everything is the most
    effective way to kill that."""
    assert background.DEFAULT_OPACITY <= 0.15


# --------------------------------------------------------------------------
# The drawing itself
# --------------------------------------------------------------------------

def _priprav(monkeypatch, tmp_path, size=(1024, 574)):
    from PIL import Image
    monkeypatch.setattr(background.paths, "images_dir", lambda: str(tmp_path))
    Image.new("RGB", size, "#40607F").save(tmp_path / (background.IMAGE_NAME + ".jpg"))


def test_vrati_presne_ziadany_rozmer(monkeypatch, tmp_path):
    _priprav(monkeypatch, tmp_path)
    img = background.load(804, 665, 0.2)
    assert img is not None and img.size == (804, 665)
    assert img.mode == "RGBA"


def test_stlmenie_ide_do_alfy_nie_do_jasu(monkeypatch, tmp_path):
    """Through alpha the photo blends with the theme background, so in Sumi it
    stays warm and in Aizome cool. Darkening the brightness would just make
    it grey in both."""
    _priprav(monkeypatch, tmp_path)
    img = background.load(200, 150, 0.2)
    r, g, b, a = img.split()
    assert max(a.getextrema()) <= int(255 * 0.2) + 1, "alfa sa nestlmila"
    # the colour itself stayed
    assert g.getextrema()[1] > 80


def test_orez_zachova_pomer_a_nerozťahuje(monkeypatch, tmp_path):
    """The photo is 16:9, the area is narrower. Stretching it to the height
    would turn it into mush, so it is cropped from the centre."""
    _priprav(monkeypatch, tmp_path, size=(1600, 900))
    from PIL import Image
    zdroj = Image.open(tmp_path / (background.IMAGE_NAME + ".jpg"))
    orez = background._orez_na_pomer(zdroj, 800, 800)
    assert orez.size == (900, 900), orez.size          # cropped at the sides
    orez2 = background._orez_na_pomer(zdroj, 1600, 400)
    assert orez2.size == (1600, 400), orez2.size       # cropped top/bottom


def test_cache_nerastie_donekonecna(monkeypatch, tmp_path):
    """It is redrawn on every change of size and theme."""
    _priprav(monkeypatch, tmp_path)
    for i in range(14):
        assert background.load(300 + i, 200, 0.2) is not None
    assert len(background._cache) <= 9


def test_forget_zahodi_cache(monkeypatch, tmp_path):
    _priprav(monkeypatch, tmp_path)
    background.load(300, 200, 0.2)
    assert background._cache
    background.forget()
    assert not background._cache


def test_poskodena_fotka_nezhodi_appku(monkeypatch, tmp_path):
    monkeypatch.setattr(background.paths, "images_dir", lambda: str(tmp_path))
    (tmp_path / (background.IMAGE_NAME + ".jpg")).write_bytes(b"toto nie je obrazok")
    spravy = []
    assert background.load(400, 300, 0.2, log=spravy.append) is None
    assert spravy, "poškodený súbor sa má zalogovať"


@pytest.mark.parametrize("pripona", [".jpg", ".png", ".webp"])
def test_pripona_nerozhoduje(monkeypatch, tmp_path, pripona):
    """A downloaded photo does not always have the extension you expect. The
    first one we put here came as `.webp` and the app simply did not find
    it — no error, no message, just the old background. Looking for exactly
    one name is a trap.
    """
    from PIL import Image
    monkeypatch.setattr(background.paths, "images_dir", lambda: str(tmp_path))
    Image.new("RGB", (800, 450), "#30506F").save(
        tmp_path / (background.IMAGE_NAME + pripona))
    assert os.path.basename(background.image_path()) == background.IMAGE_NAME + pripona
    assert background.load(400, 300, 0.2) is not None
