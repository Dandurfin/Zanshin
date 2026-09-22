"""Prijem tepu protokolom OSC (appky pre VRChat).

Preco to appka vie: na iPhone/Apple Watch neexistuje appka, ktora by
hovorila obs-websocket - vsetko ostatne (Pulsoid, Stromno, HypeRate)
posiela tep do cloudu a k tomuto PC sa nikdy nepripoji. OSC je jediny
sposob, akym sa z iPhonu da tep poslat na LOKALNU adresu bez cloudu.

Testy stavaju OSC pakety presne tak, ako ich tie appky posielaju.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import heart_rate


def _osc_str(text):
    """OSC retazec: null-ukonceny, doplneny na nasobok styroch bajtov."""
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
# sprava
# --------------------------------------------------------------------------

def test_int_je_tep():
    assert heart_rate._parse_bpm(_msg("/avatar/parameters/HR", "i", 72)) == 72


def test_float_je_tep_ked_vyzera_ako_tep():
    assert heart_rate._parse_bpm(_msg("/avatar/parameters/HR", "f", 118.0)) == 118


def test_normalizovana_hodnota_nie_je_tep():
    """Tie iste appky posielaju vedla BPM aj hodnotu 0..1 (percento z
    rozsahu 1-200). 0.36 nie je tep a na indikator sa dostat nesmie."""
    assert heart_rate._parse_bpm(_msg("/avatar/parameters/HRPercent", "f", 0.36)) is None


def test_nezmyselne_cislo_neprejde():
    assert heart_rate._parse_bpm(_msg("/avatar/parameters/HR", "i", 9999)) is None
    assert heart_rate._parse_bpm(_msg("/avatar/parameters/HR", "i", 0)) is None


def test_na_nazve_adresy_nezalezi():
    """Kazda appka si adresu pomenuje inak a hrac si ju vie prepisat -
    appka sa preto riadi hodnotou, nie nazvom."""
    for adresa in ("/hr", "/avatar/parameters/Heartrate", "/zanshin/bpm"):
        assert heart_rate._parse_bpm(_msg(adresa, "i", 64)) == 64


def test_adresa_bez_zarovnania_nezhodi_parser():
    assert heart_rate._parse_bpm(b"/HR") is None
    assert heart_rate._parse_bpm(b"") is None
    assert heart_rate._parse_bpm(b"/HR\0\0\0\0,i\0") is None


# --------------------------------------------------------------------------
# balik
# --------------------------------------------------------------------------

def test_balik_najde_tep_medzi_inymi_spravami():
    paket = _bundle(_msg("/avatar/parameters/HRPercent", "f", 0.36),
                    _msg("/avatar/parameters/HRConnected", "i", 1),
                    _msg("/avatar/parameters/HR", "i", 95))
    assert heart_rate._parse_bpm(paket) == 95


def test_prazdny_balik():
    assert heart_rate._parse_bpm(_osc_str("#bundle") + struct.pack(">Q", 1)) is None


# --------------------------------------------------------------------------
# regresia: OSC nesmie rozbit povodne dva formaty
# --------------------------------------------------------------------------

def test_holy_text_a_json_stale_funguju():
    assert heart_rate._parse_bpm(b"72") == 72
    assert heart_rate._parse_bpm(b'{"bpm": 88}') == 88
    assert heart_rate._parse_bpm(b'{"heartRate": 101}') == 101


def test_text_zacinajuci_lomkou_padne_do_textovej_vetvy():
    """Sprava, ktora OSC nie je, sa nesmie na prvej vetve stratit."""
    assert heart_rate._parse_bpm(b"/status 77") == 77


def test_obsadeny_port_neuklada_vypnutie():
    """Obsadený port je dočasný stav, nie rozhodnutie hráča.

    Appka padala pri `busy` do tej istej vetvy ako pri `error`: vypla
    `hr_monitoring_enabled` a hneď to uložila na disk. Z kolízie, ktorá trvá
    pár sekúnd (druhá spustená kópia appky), sa tak stalo trvalé nastavenie —
    senzor ostal vypnutý aj po uvoľnení portu a jediný signál bol riadok
    v denníku, ktorý je predvolene zabalený.
    """
    import inspect
    import app as app_mod
    telo = inspect.getsource(app_mod.DandurfApp._apply_hr_status)
    busy = telo[telo.index('elif kind == "busy":'):telo.index('elif kind == "error":')]
    assert "_retry_hr_bind" in busy, "vazba sa neskusa znova"
    assert "HR_BIND_RETRIES" in busy, "chyba strop pokusov"

    # Kym sa este skusa, NESMIE sa nic ukladat. Vzdat sa a zapisat vypnutie
    # sa smie az potom, co strop pokusov dobehol - vtedy uz to nie je
    # docasna kolizia.
    pokusy = busy[busy.index("if self._hr_bind_retries <="):]
    pokusy = pokusy[:pokusy.index("else:")]
    assert "save_settings" not in pokusy,         "vypnutie sa uklada uz pocas opakovania"
    assert "save_settings" in busy,         "po vycerpani pokusov sa vypnutie ulozit MA"


def test_obsadeny_port_je_vidno_pri_prepinaci():
    """Nesmie sa tváriť ako obyčajné „Odpojené"."""
    import inspect
    import app as app_mod
    telo = inspect.getsource(app_mod.DandurfApp._hr_status_display)
    assert 'self._hr_state == "busy"' in telo, "stav nema vlastny popis"


def test_tep_sa_najde_aj_ked_hodinky_posielaju_kroky_a_rychlost():
    """Prémiová appka na hodinkách vie posielať aj kroky a rýchlosť.

    Parser bral „prvé číslo v texte", takže pri „Steps: 1832  HR: 73" čítal
    kroky. `_plausible` ich odmietol a vrátil None — v appke by to vyzeralo
    ako výpadok hodiniek, nie ako zle prečítaný text.
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
    """Pasca, ktorá to spôsobila — nech sa nevráti.

    Slovenské „tep" je podreťazec anglického „S-tep-s". Bez hraníc slov sa
    vzor chytil na „Steps" a z „1832" vzal prvé tri číslice.
    """
    import heart_rate
    assert heart_rate._parse_bpm(b"Steps: 1832") is None, \
        "kroky sa citaju ako tep"
    assert heart_rate._parse_bpm(b"1832") is None, "nezmyselna hodnota prejde"


def test_kroky_a_rychlost_sa_vytiahnu_z_roznych_formatov():
    """Prémiová appka na hodinkách posiela aj kroky a rýchlosť.

    Sú to jediný PRIAMY signál pohybu, ktorý máme — bez neho sa chôdza od
    hernej záťaže odlíšiť nedá, v oboch prípadoch len stúpne tep.
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
    """„Nevieme" a „nula krokov" sú dve rôzne veci.

    Zameniť ich by znamenalo tvrdiť, že hráč sedí, vždy keď hodinky kroky
    neposielajú — a práve na tom by potom stála detekcia pohybu.
    """
    import heart_rate
    m = heart_rate.parse_metrics(b"73 bpm")
    assert m["bpm"] == 73
    assert m["steps"] is None and m["speed"] is None


def test_menovka_sa_nespoji_s_cislom_za_oddelovacom():
    """Pasce, ktoré to spôsobili — nech sa nevrátia.

    1) „1832 steps | 4.2 km/h" spájalo menovku „steps" s číslom AŽ ZA „|"
       a čítalo kroky ako 4.
    2) „Tep: 73  Kroky: 1832" sa chytilo na „73  Kroky" a čítalo tep ako
       počet krokov — `re.search` vracia najľavejší výskyt, nie prvú vetvu.
    """
    import heart_rate
    m = heart_rate.parse_metrics(b"1832 steps | 4.2 km/h")
    assert m["steps"] == 1832
    m = heart_rate.parse_metrics("Tep: 73  Kroky: 1832".encode())
    assert m["bpm"] == 73 and m["steps"] == 1832
