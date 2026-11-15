# -*- coding: utf-8 -*-
"""Telling metrics apart by the OBS source name.

On 19. 9. 2026 the watch app got separate sources for steps and speed. Each
of them sends a **bare number** without a label, so `86` and `1045` were
alternating on the wire. The only thing that turned this into usable data
was luck: 1045 is outside the plausible heart-rate range, so the parser
dropped it.

In the morning, at 140 steps walked, that luck would have run out and the
app would have recorded 140 BPM. This is exactly how the corrupted session
at 13:07 came about (average 124, maximum 235). That is why the source name
is carried all the way to the parser, and why this file guards it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import heart_rate  # noqa: E402
import obs_websocket  # noqa: E402


# ---------------------------------------------------------------------------
# the source name must make it out of the request
# ---------------------------------------------------------------------------

def test_zapis_nesie_meno_aj_text():
    meno, text = obs_websocket._extract_write(
        {"inputName": "Kroky", "inputSettings": {"text": "1045"}})
    assert (meno, text) == ("Kroky", "1045")


def test_zapis_bez_mena_je_stale_platny():
    """The basic app version sends no name — it must not stop working."""
    meno, text = obs_websocket._extract_write(
        {"inputSettings": {"text": "86"}})
    assert meno is None and text == "86"


def test_pokazena_poziadavka_nic_nevrati():
    for zle in (None, {}, {"inputSettings": None},
                {"inputSettings": {"text": 86}}):
        assert obs_websocket._extract_write(zle) == (None, None)


# ---------------------------------------------------------------------------
# classifying the name
# ---------------------------------------------------------------------------

def test_nase_vlastne_zdroje_sa_zaradia():
    z = heart_rate.metrika_zdroja
    assert z("Tep") == "bpm"
    assert z("Kroky") == "steps"
    assert z("Rychlost") == "speed"


def test_zaradenie_je_odolne_voci_tomu_ako_si_to_hrac_pomenuje():
    z = heart_rate.metrika_zdroja
    assert z("steps") == "steps"
    assert z("Step Count") == "steps"
    assert z("speed") == "speed"
    assert z("  BPM  ") == "bpm"
    assert z("heart rate") == "bpm"


def test_kroky_sa_nezaradia_ako_tep():
    """The Slovak "tep" is inside the English "s-tep-s".

    The same trap as with labels in the text — there word boundaries solve
    it, here the order: steps are tried before heart rate.
    """
    assert heart_rate.metrika_zdroja("Steps") == "steps"


def test_nezname_meno_znamena_neviem_a_nie_tep():
    assert heart_rate.metrika_zdroja("Text 1") is None
    assert heart_rate.metrika_zdroja("") is None
    assert heart_rate.metrika_zdroja(None) is None


# ---------------------------------------------------------------------------
# the routing of values itself — the heart of the matter
# ---------------------------------------------------------------------------

def test_kroky_v_rozsahu_tepu_sa_uz_nedaju_precitat_ako_tep():
    """This is the test this file exists for."""
    m = heart_rate.parse_metrics(b"140", "Kroky")
    assert m["bpm"] is None
    assert m["steps"] == 140


def test_rychlost_sa_nikdy_nestane_tepom():
    m = heart_rate.parse_metrics(b"42", "Rychlost")
    assert m["bpm"] is None
    assert m["speed"] == 42.0


def test_tep_zo_zdroja_tepu_prejde():
    assert heart_rate.parse_metrics(b"86", "Tep")["bpm"] == 86


def test_nepravdepodobny_tep_neprejde_ani_zo_spravneho_zdroja():
    """The source name says WHAT it is — not that it is true."""
    assert heart_rate.parse_metrics(b"400", "Tep")["bpm"] is None


def test_desatinna_ciarka_v_rychlosti():
    assert heart_rate.parse_metrics(b"4,2", "Rychlost")["speed"] == 4.2


def test_nezmyselny_pocet_krokov_neprejde():
    assert heart_rate.parse_metrics(b"999999999", "Kroky")["steps"] is None


def test_len_ciste_cislo_je_hodnota():
    """The first number is not taken from arbitrary text.

    Otherwise we would be back at the bug that read heart rate from the
    step count — just from the other side.
    """
    m = heart_rate.parse_metrics(b"chyba senzora 3x", "Tep")
    assert m["bpm"] is None


def test_menovky_v_texte_maju_prednost_pred_menom_zdroja():
    """The premium version can send everything into one source."""
    m = heart_rate.parse_metrics(b"Tep: 73 Kroky: 1832", "Tep")
    assert m["bpm"] == 73 and m["steps"] == 1832


def test_bez_mena_zdroja_ostava_povodne_spravanie():
    """UDP has no source name — the old path must keep working."""
    assert heart_rate.parse_metrics(b"140")["bpm"] == 140
    assert heart_rate.parse_metrics(b"Tep 73 Kroky 1832") == {
        "bpm": 73, "steps": 1832, "speed": None}


# ---------------------------------------------------------------------------
# the pretend OBS must also offer those sources
# ---------------------------------------------------------------------------

def test_hrac_si_ma_v_telefone_z_coho_vybrat():
    mena = [i["inputName"]
            for i in obs_websocket._response_data("GetInputList")["inputs"]]
    assert mena == ["Tep", "Kroky", "Rychlost"]


def test_kazdy_ponukany_zdroj_vie_appka_zaradit():
    """The OBS layer list and the parser recognition must not drift apart."""
    for meno, _uuid in obs_websocket.ZDROJE:
        assert heart_rate.metrika_zdroja(meno) is not None, meno


def test_zdroj_vyrobeny_klientom_sa_v_zozname_objavi():
    mena = [i["inputName"] for i in obs_websocket._response_data(
        "GetInputList", {"speed"})["inputs"]]
    assert "speed" in mena


def test_scena_vyda_polozku_pre_kazdy_zdroj():
    polozky = obs_websocket._response_data("GetSceneItemList")["sceneItems"]
    assert len(polozky) == len(obs_websocket.ZDROJE)
    assert len(set(p["sceneItemId"] for p in polozky)) == len(polozky)


def test_vyroba_zdroja_dostane_odpoved_nie_prazdno():
    """An empty reply is a reason for the client to wait until the timeout."""
    d = obs_websocket._response_data("CreateInput", (), {"inputName": "speed"})
    assert d.get("inputUuid") and d.get("sceneItemId")


def test_uuid_odvodene_od_mena_je_stale():
    assert obs_websocket._uuid_pre("speed") == obs_websocket._uuid_pre("speed")
    assert obs_websocket._uuid_pre("speed") != obs_websocket._uuid_pre("steps")


# ---------------------------------------------------------------------------
# two step sources at once — a mine that was waiting for the first walk
# ---------------------------------------------------------------------------

def _kroky(hodnoty, zdroje=None, krok=0.25, start=1000.0):
    """Feeds the stats a sequence of step counts and returns steps/min."""
    import hr_stats
    s = hr_stats.HeartStats()
    t = start
    for i, v in enumerate(hodnoty):
        z = zdroje[i % len(zdroje)] if zdroje else None
        s.note_metrics(steps=v, ts=t, zdroj=z)
        t += krok
    return s.steps_per_min(now=t)


def test_dva_zdroje_krokov_nevyrobia_kroky_ktore_sa_nestali():
    """This is the test the fix was made for.

    The watch writes the same step count into two sources ("Steps" and
    "steps"). As long as the counters differ only by their mutual delay,
    the player has not moved. Before the fix this came out as 595 steps
    per minute against a threshold of 15 — the app would think they were
    sprinting and would stop speaking.
    """
    assert _kroky([1085, 1080] * 120, ["Steps", "steps"]) == 0.0


def test_dva_zdroje_s_rovnakou_hodnotou_su_ticho():
    assert _kroky([1085] * 240, ["Steps", "steps"]) == 0.0


def test_skutocna_chodza_sa_z_dvoch_zdrojov_stale_zmeria():
    """The fix must not silence steps — only the made-up ones."""
    hodnoty, v = [], 1000
    for _ in range(120):
        hodnoty += [v, v - 4]        # the second source lags 4 steps behind
        v += 2                       # the real increment: 2 per message
    za_minutu = _kroky(hodnoty, ["Steps", "steps"])
    assert 220.0 <= za_minutu <= 240.0, za_minutu


def test_restart_pocitadla_o_polnoci_nevyrobi_kroky():
    assert _kroky([8000, 8000, 0, 5, 10, 15], ["Steps"], krok=1.0) == 15.0


def test_bez_mena_zdroja_ostava_pocitanie_krokov_nezmenene():
    """UDP has no source name — the behaviour must be exactly as before."""
    assert _kroky(list(range(1000, 1240))) == 239.0


def test_ticho_vybraneho_zdroja_prepusti_iny():
    """Otherwise a switched-off source would silence steps forever."""
    import hr_stats
    s = hr_stats.HeartStats()
    s.note_metrics(steps=1000, ts=1000.0, zdroj="Steps")
    # meanwhile the second source must not take over
    s.note_metrics(steps=5000, ts=1001.0, zdroj="iny")
    assert s.steps_per_min(now=1001.0) == 0.0
    # ...but after the original goes quiet, yes - and without a fake increment
    t = 1000.0 + hr_stats.PRELADENIE_ZDROJA_S + 1.0
    s.note_metrics(steps=5000, ts=t, zdroj="iny")
    assert s.steps_per_min(now=t) == 0.0
    s.note_metrics(steps=5010, ts=t + 1.0, zdroj="iny")
    assert s.steps_per_min(now=t + 1.0) == 10.0


def test_neviem_sa_nikdy_nestane_nulou():
    """Two things: "the watch sends no steps" and "the player is sitting"."""
    import hr_stats
    s = hr_stats.HeartStats()
    assert s.steps_per_min() is None


# ---------------------------------------------------------------------------
# an unknown source name — the original bug was only half closed
# ---------------------------------------------------------------------------

def test_neznamy_zdroj_medzi_viacerymi_nevyda_tep():
    """We can only classify names we know — and the player picks them.

    `Cadence`, `Calories`, `Aktivita` or the Japanese 歩数 are unknown to
    us, and while heart rate was guessed from their bare number, the
    original bug was closed only for names we happen to have on the list.
    Anyone else got exactly that corrupted session from 13:07.
    """
    for meno in ("Cadence", "Calories", "Distance", "Aktivita", "歩数x",
                 "Text 1"):
        m = heart_rate.parse_metrics(b"140", meno, False)
        assert m["bpm"] is None, meno


def test_jediny_zdroj_ostava_tepom_nech_sa_vola_akokolvek():
    """OBS's default source name is "Text 1", and many people never rename it.

    While a single source is writing, there is nothing to mix up — it is
    heart rate.
    """
    assert heart_rate.parse_metrics(b"140", "Text 1", True)["bpm"] == 140
    assert heart_rate.parse_metrics(b"140", None, True)["bpm"] == 140


def test_menovka_v_texte_prejde_aj_z_nezname_zdroja():
    """What gets suppressed is a BARE number, not an explicit label."""
    assert heart_rate.parse_metrics(b"Tep: 86", "Cadence", False)["bpm"] == 86
    assert heart_rate.parse_metrics(b'{"bpm": 86}', "Cadence", False)["bpm"] == 86


def test_beh_si_pamata_ktore_zdroje_uz_pisali():
    r = heart_rate._Run(1)
    assert r.note_source("Tep") is True          # the first
    assert r.note_source("Tep") is True          # still the only one
    assert r.note_source("Kroky") is False       # now there are two


# ---------------------------------------------------------------------------
# word boundaries — the same trap a third time
# ---------------------------------------------------------------------------

def test_hrv_a_threshold_nie_su_tep():
    """`hr` has two characters, and as a plain substring it caught on
    "T-hr-eshold" and on "HRV". On top of that, premium apps really do
    send HRV."""
    assert heart_rate.metrika_zdroja("HRV") is None
    assert heart_rate.metrika_zdroja("Threshold") is None
    assert heart_rate.metrika_zdroja("HR") == "bpm"


def test_zaradenie_zvlada_aj_cudzie_jazyky():
    z = heart_rate.metrika_zdroja
    assert z("Herzfrequenz") == "bpm"
    assert z("Schrittzähler") == "steps"
    assert z("心拍") == "bpm"
    assert z("歩数") == "steps"
    assert z("Rýchlosť") == "speed"


# ---------------------------------------------------------------------------
# thousands separator
# ---------------------------------------------------------------------------

def test_pocet_krokov_znesie_oddelovac_tisicov():
    """The watch formats the number for the overlay by locale.

    It cannot be told apart at the string level — "4,2" is a valid speed.
    At the metric level it can: a step count is always a whole number.
    """
    for text in (b"1,085", b"1 085", b"1.085", b"1085"):
        assert heart_rate.parse_metrics(text, "Kroky")["steps"] == 1085, text
    assert heart_rate.parse_metrics(b"12,345", "Kroky")["steps"] == 12345


def test_desatinne_cislo_nie_je_pocet_krokov():
    assert heart_rate.parse_metrics(b"4,2", "Kroky")["steps"] is None
    assert heart_rate.parse_metrics(b"4,2", "Rychlost")["speed"] == 4.2


# ---------------------------------------------------------------------------
# a batch of requests — this was that "timeout waiting 10000 ms"
# ---------------------------------------------------------------------------

def test_davka_ide_rovnakou_cestou_ako_samostatna_poziadavka():
    """`op 8` fell through the whole if/elif chain without any response.

    A watch app that sends several metrics tends to send them at once as a
    batch. The client then waited ten seconds and reported that the
    receiver does not exist. Not even the log entry about an unknown
    request caught it — that one is inside the `op == 6` branch, which the
    batch never reached.
    """
    zapisy = []
    vlastne, nepoznane = set(), set()
    d = obs_websocket._odbav(
        {"requestType": "SetInputSettings", "requestId": "a",
         "requestData": {"inputName": "Kroky",
                         "inputSettings": {"text": "1085"}}},
        lambda t, z: zapisy.append((z, t)), vlastne, nepoznane)
    assert zapisy == [("Kroky", "1085")]
    assert d["requestId"] == "a" and d["requestStatus"]["result"] is True


def test_opkody_bez_odpovede_su_vymenovane():
    """So the silence around the next `op` cannot be overlooked — anything
    outside this list is written to the journal."""
    assert 8 not in obs_websocket._TICHE_OP      # the batch MUST be handled
    assert 6 not in obs_websocket._TICHE_OP
    assert 0 in obs_websocket._TICHE_OP          # Hello is our own output


# ---------------------------------------------------------------------------
# writing heart rate only after Identify (B6)
# ---------------------------------------------------------------------------

def test_zapis_tepu_sa_odmietne_pred_identify():
    """B6: anything on the LAN that completes the WS handshake could send
    an arbitrary "BPM" and it was written as a real heart rate. A write
    (SetInputSettings) may be accepted only once the client has
    identified itself (op 1)."""
    zapisane = []
    req = {"requestType": "SetInputSettings", "requestId": "a",
           "requestData": {"inputName": "Tep", "inputSettings": {"text": "200"}}}
    # before Identify: the write MUST be ignored
    obs_websocket._odbav(req, lambda t, z: zapisane.append(t),
                         set(), set(), zapis_ok=False)
    assert zapisane == [], "tep sa zapísal bez identifikácie (B6)"
    # after Identify: the write goes through
    obs_websocket._odbav(req, lambda t, z: zapisane.append(t),
                         set(), set(), zapis_ok=True)
    assert zapisane == ["200"]


def test_citania_prejdu_aj_pred_identify():
    """Only a WRITE is refused — reads (GetInputList and co.) are harmless
    and the client may get them, so the protocol does not get stuck."""
    d = obs_websocket._odbav(
        {"requestType": "GetInputList", "requestId": "x"},
        lambda t, z: None, set(), set(), zapis_ok=False)
    assert d["requestStatus"]["result"] is True


def test_serve_connection_strazi_identify():
    """The connection loop must tie a write to Identify (op 1)."""
    import inspect
    telo = inspect.getsource(obs_websocket.serve_connection)
    assert "identified" in telo
    assert "zapis_ok=identified" in telo


# ---------------------------------------------------------------------------
# addressing a source via inputUuid (B7)
# ---------------------------------------------------------------------------

def test_zapis_cez_uuid_dohlada_meno_zdroja():
    """B7: obs-websocket v5 allows addressing a source via inputUuid
    instead of the name. We handed out the UUIDs ourselves → we can map
    them back. Without this, steps addressed via UUID would have no name
    and would be read as heart rate."""
    uuid_kroky = dict(obs_websocket.ZDROJE)["Kroky"]
    meno, text = obs_websocket._extract_write(
        {"inputUuid": uuid_kroky, "inputSettings": {"text": "1045"}})
    assert (meno, text) == ("Kroky", "1045")


def test_zapis_cez_uuid_klientom_vyrobeneho_zdroja():
    """A source the client created itself (e.g. "steps") is found via UUID
    if the app has already seen its name in the connection."""
    u = obs_websocket._uuid_pre("steps")
    meno, _ = obs_websocket._extract_write(
        {"inputUuid": u, "inputSettings": {"text": "1200"}}, {"steps"})
    assert meno == "steps"


def test_neznamy_uuid_nechyti_tep():
    """Unknown UUID → no name → a bare number is NOT heart rate (the
    multi-source logic in parse_metrics protects this)."""
    meno, _ = obs_websocket._extract_write(
        {"inputUuid": "ffffffff-0000-4000-8000-000000000000",
         "inputSettings": {"text": "140"}})
    assert meno is None
    # and with several sources it does not become heart rate
    assert heart_rate.parse_metrics(b"140", meno, False)["bpm"] is None


def test_steps_per_min_je_none_ked_kroky_prestali_chodit():
    """B32: when the watch stops sending steps, that is WE DON'T KNOW, not
    0. While messages keep coming (even with a zero increment), zero is
    valid."""
    import hr_stats
    s = hr_stats.HeartStats()
    assert s.steps_per_min(now=1000.0) is None          # nothing ever arrived
    s.note_metrics(steps=1000, ts=1000.0, zdroj="Kroky")
    s.note_metrics(steps=1000, ts=1001.0, zdroj="Kroky")   # zero increment
    assert s.steps_per_min(now=1001.0) == 0.0            # coming in → zero
    # after two minutes of silence → we don't know, not zero
    assert s.steps_per_min(now=1001.0 + 120.0) is None


# ---------------------------------------------------------------------------
# the guide in every language names the source exactly as the phone will see it
# ---------------------------------------------------------------------------

def test_navod_menuje_zdroj_doslova_vo_vsetkych_jazykoch():
    """The phone will see the scene "Zanshin" and the source "Tep"
    (SCENE_NAME, INPUT_NAME). The English guide and its ja..pt
    translations advised picking a "Heart rate" source, which does not
    exist. Names in OBS are not translated."""
    import i18n
    for kluc in ("hr.step4_body", "hr.trouble_body", "log.hr_client_connected"):
        for jazyk in i18n.LANGUAGES:
            text = i18n.STRINGS[kluc][jazyk]
            assert obs_websocket.SCENE_NAME in text, (kluc, jazyk)
            assert obs_websocket.INPUT_NAME in text, (kluc, jazyk)
            assert "Heart rate" not in text, (kluc, jazyk)
