"""Heart-rate receiving over the OSC protocol (apps for VRChat).

Why the app can do it: on iPhone/Apple Watch there is no app that would
speak obs-websocket - everything else (Pulsoid, Stromno, HypeRate) sends
the heart rate to the cloud and never connects to this PC. OSC is the
only way to send the heart rate from an iPhone to a LOCAL address without
a cloud.

The tests build OSC packets exactly the way those apps send them.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import heart_rate


def _osc_str(text):
    """OSC string: null-terminated, padded to a multiple of four bytes."""
    raw = text.encode() + b"\0"
    return raw + b"\0" * (-len(raw) % 4)


def _msg(address, tag, value):
    payload = (struct.pack(">i", value) if tag == "i"
               else struct.pack(">f", value))
    return _osc_str(address) + _osc_str("," + tag) + payload


def _bundle(*messages):
    out = _osc_str("#bundle") + struct.pack(">Q", 1)
    for m in messages:
        out += struct.pack(">i", len(m)) + m
    return out


# --------------------------------------------------------------------------
# message
# --------------------------------------------------------------------------

def test_int_je_tep():
    assert heart_rate._parse_bpm(_msg("/avatar/parameters/HR", "i", 72)) == 72


def test_float_je_tep_ked_vyzera_ako_tep():
    assert heart_rate._parse_bpm(_msg("/avatar/parameters/HR", "f", 118.0)) == 118


def test_normalizovana_hodnota_nie_je_tep():
    """The same apps also send, next to BPM, a 0..1 value (a percentage of
    the 1-200 range). 0.36 is not a heart rate and must not get onto the
    indicator."""
    assert heart_rate._parse_bpm(_msg("/avatar/parameters/HRPercent", "f", 0.36)) is None


def test_nezmyselne_cislo_neprejde():
    assert heart_rate._parse_bpm(_msg("/avatar/parameters/HR", "i", 9999)) is None
    assert heart_rate._parse_bpm(_msg("/avatar/parameters/HR", "i", 0)) is None


def test_na_nazve_adresy_nezalezi():
    """Every app names the address differently and the player can change it -
    so the app goes by the value, not the name."""
    for adresa in ("/hr", "/avatar/parameters/Heartrate", "/zanshin/bpm"):
        assert heart_rate._parse_bpm(_msg(adresa, "i", 64)) == 64


def test_adresa_bez_zarovnania_nezhodi_parser():
    assert heart_rate._parse_bpm(b"/HR") is None
    assert heart_rate._parse_bpm(b"") is None
    assert heart_rate._parse_bpm(b"/HR\0\0\0\0,i\0") is None


# --------------------------------------------------------------------------
# bundle
# --------------------------------------------------------------------------

def test_balik_najde_tep_medzi_inymi_spravami():
    paket = _bundle(_msg("/avatar/parameters/HRPercent", "f", 0.36),
                    _msg("/avatar/parameters/HRConnected", "i", 1),
                    _msg("/avatar/parameters/HR", "i", 95))
    assert heart_rate._parse_bpm(paket) == 95


def test_prazdny_balik():
    assert heart_rate._parse_bpm(_osc_str("#bundle") + struct.pack(">Q", 1)) is None


# --------------------------------------------------------------------------
# regression: OSC must not break the original two formats
# --------------------------------------------------------------------------

def test_holy_text_a_json_stale_funguju():
    assert heart_rate._parse_bpm(b"72") == 72
    assert heart_rate._parse_bpm(b'{"bpm": 88}') == 88
    assert heart_rate._parse_bpm(b'{"heartRate": 101}') == 101


def test_text_zacinajuci_lomkou_padne_do_textovej_vetvy():
    """A message that is not OSC must not get lost on the first branch."""
    assert heart_rate._parse_bpm(b"/status 77") == 77


def test_obsadeny_port_neuklada_vypnutie():
    """A busy port is a temporary state, not the player's decision.

    On `busy` the app fell into the same branch as on `error`: it turned
    `hr_monitoring_enabled` off and saved it to disk right away. A
    collision lasting a few seconds (a second running copy of the app)
    thus became a permanent setting — the sensor stayed off even after the
    port was freed, and the only signal was a line in the journal, which
    is collapsed by default.
    """
    import inspect
    import app as app_mod
    telo = inspect.getsource(app_mod.DandurfApp._apply_hr_status)
    busy = telo[telo.index('elif kind == "busy":'):telo.index('elif kind == "error":')]
    assert "_retry_hr_bind" in busy, "vazba sa neskusa znova"
    assert "HR_BIND_RETRIES" in busy, "chyba strop pokusov"

    # While it is still retrying, NOTHING may be saved. And since 0.3 not
    # even after giving up: even then it is not the player's decision - a
    # second running copy of the app was thereby permanently turning off the
    # first one's heart-rate receiving. It is off only in memory
    # (`_senzor_vypla_chyba`), the next start tries again
    # (tests/test_022b_instance_port.py).
    pokusy = busy[busy.index("if self._hr_bind_retries <="):]
    pokusy = pokusy[:pokusy.index("else:")]
    assert "save_settings" not in pokusy,         "vypnutie sa uklada uz pocas opakovania"
    assert "save_settings" not in busy,         "vzdanie sa nie je volba hraca - neuklada sa"
    assert "_senzor_vypla_chyba(self)" in busy, "po vzdani ma byt senzor vypnuty len v pamati"


def test_obsadeny_port_je_vidno_pri_prepinaci():
    """Must not pass for an ordinary "Disconnected"."""
    import inspect
    import app as app_mod
    telo = inspect.getsource(app_mod.DandurfApp._hr_status_display)
    assert 'self._hr_state == "busy"' in telo, "stav nema vlastny popis"


def test_tep_sa_najde_aj_ked_hodinky_posielaju_kroky_a_rychlost():
    """A premium app on the watch can also send steps and speed.

    The parser took "the first number in the text", so with
    "Steps: 1832  HR: 73" it read the steps. `_plausible` rejected them and
    returned None — in the app it would look like a watch dropout, not
    like misread text.
    """
    import heart_rate
    for text in ("73",
                 '{"bpm": 73}',
                 '{"bpm": 73, "steps": 1832, "speed": 0.0}',
                 "73 bpm",
                 "1832 krokov | 73 bpm | 0.0 km/h",
                 "Steps: 1832  HR: 73  Speed: 0.0",
                 "HR 73 | 1832 steps",
                 "73 bpm, 1832 steps, 4.2 km/h",
                 "Tep: 73  Kroky: 1832",
                 "0.0 km/h  73 bpm"):
        assert heart_rate._parse_bpm(text.encode()) == 73, text


def test_slovo_tep_je_vnutri_slova_steps():
    """The trap that caused it — so it does not come back.

    The Slovak "tep" (heart rate) is a substring of the English "S-tep-s".
    Without word boundaries the pattern caught on "Steps" and took the
    first three digits of "1832".
    """
    import heart_rate
    assert heart_rate._parse_bpm(b"Steps: 1832") is None, \
        "kroky sa citaju ako tep"
    assert heart_rate._parse_bpm(b"1832") is None, "nezmyselna hodnota prejde"


def test_kroky_a_rychlost_sa_vytiahnu_z_roznych_formatov():
    """A premium app on the watch also sends steps and speed.

    They are the only DIRECT movement signal we have — without it walking
    cannot be told apart from gaming load; in both cases only the heart
    rate rises.
    """
    import heart_rate
    for text in ('{"bpm": 73, "steps": 1832, "speed": 4.2}',
                 "73 bpm | 1832 steps | 4.2 km/h",
                 "Steps: 1832  HR: 73  Speed: 4.2",
                 "HR 73 | 1832 steps | 4.2 kmh",
                 "HR=73 Steps=1832 Speed=4.2"):
        m = heart_rate.parse_metrics(text.encode())
        assert m["bpm"] == 73, text
        assert m["steps"] == 1832, text
        assert abs(m["speed"] - 4.2) < 0.001, text


def test_chybajuca_metrika_je_none_nie_nula():
    """The "we don't know" and "zero steps" cases are two different things.

    Mixing them up would mean claiming the player is sitting whenever the
    watch does not send steps — and movement detection would then rest on
    exactly that.
    """
    import heart_rate
    m = heart_rate.parse_metrics(b"73 bpm")
    assert m["bpm"] == 73
    assert m["steps"] is None and m["speed"] is None


def test_menovka_sa_nespoji_s_cislom_za_oddelovacom():
    """The traps that caused it — so they do not come back.

    1) "1832 steps | 4.2 km/h" joined the label "steps" with the number
       only AFTER the "|" and read the steps as 4.
    2) "Tep: 73  Kroky: 1832" caught on "73  Kroky" and read the heart
       rate as the step count — `re.search` returns the leftmost match,
       not the first alternative.
    """
    import heart_rate
    m = heart_rate.parse_metrics(b"1832 steps | 4.2 km/h")
    assert m["steps"] == 1832
    m = heart_rate.parse_metrics("Tep: 73  Kroky: 1832".encode())
    assert m["bpm"] == 73 and m["steps"] == 1832
