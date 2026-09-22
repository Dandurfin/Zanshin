# -*- coding: utf-8 -*-
"""Fotka na pozadí — mechanizmus, nie vzhľad.

Zmysel týchto testov je jediný: aby sa fotka dala vymeniť za inú bez toho,
aby sa čokoľvek rozbilo, a aby jej neprítomnosť nikdy nezhodila okno.
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
# Jedno miesto na zmenu
# --------------------------------------------------------------------------

def test_nazov_suboru_je_len_na_jednom_mieste():
    """Kto mení fotku, mení `IMAGE_NAME` a nič iné. Keby sa názov objavil
    aj inde, raz sa zmení len na jednom mieste a appka bude hľadať súbor,
    ktorý tam nie je."""
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
    """Fotka je ozdoba, nie súčasť funkcie. Chýbajúci súbor nesmie zhodiť
    okno — `load` len vráti None a volajúci nekreslí nič."""
    monkeypatch.setattr(background.paths, "images_dir", lambda: str(tmp_path))
    spravy = []
    assert background.image_path() is None
    assert background.available() is False
    assert background.load(800, 600, 0.1, log=spravy.append) is None
    assert len(spravy) == 1, "má sa to zalogovať raz"
    # druhé volanie už log nezaplavuje
    assert background.load(800, 600, 0.1, log=spravy.append) is None
    assert len(spravy) == 1


def test_zaloha_ked_nova_fotka_chyba(monkeypatch, tmp_path):
    """Kým nová fotka nie je na disku, použije sa starý pás z verzie 2.0 —
    je to tá istá miestnosť, len užší výrez."""
    from PIL import Image
    monkeypatch.setattr(background.paths, "images_dir", lambda: str(tmp_path))
    Image.new("RGB", (1100, 190), "#203040").save(
        tmp_path / background.FALLBACK_NAME)
    assert os.path.basename(background.image_path()) == background.FALLBACK_NAME
    # a keď pribudne nová, má prednosť
    Image.new("RGB", (1024, 574), "#203040").save(
        tmp_path / (background.IMAGE_NAME + ".jpg"))
    assert os.path.basename(background.image_path()) == background.IMAGE_NAME + ".jpg"


# --------------------------------------------------------------------------
# Jemnosť
# --------------------------------------------------------------------------

def test_jemnost_ma_strop():
    """Nad stropom prestáva byť čitateľný malý text v paneloch — a tých je
    deväť jazykov vrátane japončiny."""
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
    """Celý návrh stojí na tom, že prstenec „natiahnuté" zachytíš kútikom
    oka. Výrazná fotka za všetkým je najúčinnejší spôsob, ako to zabiť."""
    assert background.DEFAULT_OPACITY <= 0.15


# --------------------------------------------------------------------------
# Samotné kreslenie
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
    """Cez alfu sa fotka zlúči s pozadím témy, takže v Sumi ostane teplá a
    v Aizome chladná. Stmavenie jasu by ju v oboch spravilo len sivou."""
    _priprav(monkeypatch, tmp_path)
    img = background.load(200, 150, 0.2)
    r, g, b, a = img.split()
    assert max(a.getextrema()) <= int(255 * 0.2) + 1, "alfa sa nestlmila"
    # farba samotná ostala
    assert g.getextrema()[1] > 80


def test_orez_zachova_pomer_a_nerozťahuje(monkeypatch, tmp_path):
    """Fotka je 16:9, plocha je užšia. Roztiahnuť ju na výšku by z nej
    spravilo kašu, tak sa orezáva stredom."""
    _priprav(monkeypatch, tmp_path, size=(1600, 900))
    from PIL import Image
    zdroj = Image.open(tmp_path / (background.IMAGE_NAME + ".jpg"))
    orez = background._orez_na_pomer(zdroj, 800, 800)
    assert orez.size == (900, 900), orez.size          # orezané po stranách
    orez2 = background._orez_na_pomer(zdroj, 1600, 400)
    assert orez2.size == (1600, 400), orez2.size       # orezané hore/dole


def test_cache_nerastie_donekonecna(monkeypatch, tmp_path):
    """Prekresľuje sa pri každej zmene veľkosti a témy."""
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
    """Stiahnutá fotka nemá vždy príponu, ktorú čakáš. Prvá, ktorú sme sem
    dali, prišla ako `.webp` a appka ju proste nenašla — bez chyby, bez
    hlášky, len staré pozadie. Hľadať presne jeden názov je pasca.
    """
    from PIL import Image
    monkeypatch.setattr(background.paths, "images_dir", lambda: str(tmp_path))
    Image.new("RGB", (800, 450), "#30506F").save(
        tmp_path / (background.IMAGE_NAME + pripona))
    assert os.path.basename(background.image_path()) == background.IMAGE_NAME + pripona
    assert background.load(400, 300, 0.2) is not None


def test_nova_fotka_ma_prednost_pred_zalohou(monkeypatch, tmp_path):
    from PIL import Image
    monkeypatch.setattr(background.paths, "images_dir", lambda: str(tmp_path))
    Image.new("RGB", (1100, 190), "#203040").save(tmp_path / background.FALLBACK_NAME)
    Image.new("RGB", (1024, 572), "#203040").save(
        tmp_path / (background.IMAGE_NAME + ".webp"))
    assert os.path.basename(background.image_path()).startswith(background.IMAGE_NAME)
