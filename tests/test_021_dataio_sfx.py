# -*- coding: utf-8 -*-
"""Downloading SFX from GitHub (0.2.1): reading with a cap.

`_try_download` read the whole response at once (`resp.read()`) and only
then checked SHA-256. Changed or forged content at that address could thus
push anything into the app's memory. Now it is read in chunks and stops
above `MAX_STIAHNUTIE_BAJTOV` - SHA-256 stays as a second safeguard.
"""
import hashlib
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import sfx_assets  # noqa: E402


class _Server:
    """Stub `urlopen` response. `data=None` = the server sends forever."""

    def __init__(self, data=None):
        self.data = data
        self.poslane = 0
        self.citania = []

    def read(self, amt=None):
        self.citania.append(amt)
        assert amt is not None, "read() bez stropu natiahne celu odpoved"
        if self.data is None:
            kus = b"RIFF" + b"\0" * (amt - 4) if self.poslane == 0 else b"\0" * amt
        else:
            kus = self.data[self.poslane:self.poslane + amt]
        self.poslane += len(kus)
        return kus

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def _stahovane():
    return [(pack, info) for pack, zvuky in sfx_assets.SOUND_LIBRARY.items()
            for info in zvuky.values() if info.get("download_url")]


def _pribaleny(pack, info):
    return os.path.join(ROOT, "assets", "sounds", pack, info["file"])


def test_nekonecna_odpoved_sa_zastavi_na_strope(tmp_path, monkeypatch):
    server = _Server()
    monkeypatch.setattr(sfx_assets.urllib.request, "urlopen",
                        lambda req, timeout=None: server)
    ciel = str(tmp_path / "zvuk.wav")
    with pytest.raises(ValueError):
        sfx_assets._try_download("https://example.invalid/x.wav", ciel,
                                 expected_sha256="0" * 64)
    assert server.poslane <= sfx_assets.MAX_STIAHNUTIE_BAJTOV + max(server.citania)
    assert not os.path.exists(ciel) and not os.path.exists(ciel + ".tmp")


def test_skutocny_zvuk_sa_stiahne_cely_a_overi(tmp_path, monkeypatch):
    """The cap must not cut off a real file - SHA-256 must match."""
    for pack, info in _stahovane():
        with open(_pribaleny(pack, info), "rb") as fh:
            obsah = fh.read()
        server = _Server(obsah)
        monkeypatch.setattr(sfx_assets.urllib.request, "urlopen",
                            lambda req, timeout=None, s=server: s)
        ciel = str(tmp_path / info["file"])
        sfx_assets._try_download(info["download_url"], ciel,
                                 expected_sha256=info["sha256"])
        with open(ciel, "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == info["sha256"]


def test_strop_je_nad_znamymi_subormi():
    """The cap is a bit above the real sizes (1,7 kB and 49,6 kB), not
    right on them - and not megabytes."""
    velkosti = [os.path.getsize(_pribaleny(p, i)) for p, i in _stahovane()]
    assert velkosti
    assert max(velkosti) * 2 < sfx_assets.MAX_STIAHNUTIE_BAJTOV <= 1024 * 1024
