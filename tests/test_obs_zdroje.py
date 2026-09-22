# -*- coding: utf-8 -*-
"""Rozlíšenie metrík podľa mena OBS zdroja.

19. 9. 2026 pribudli v appke na hodinkách samostatné zdroje pre kroky a
rýchlosť. Každý z nich posiela **holé číslo** bez menovky, takže na drôte
chodilo striedavo `86` a `1045`. Jediné, čo z toho spravilo použiteľné dáta,
bola náhoda: 1045 je mimo vierohodného rozsahu tepu, tak ho parser zahodil.

Ráno, pri 140 nachodených krokoch, by tá náhoda prestala platiť a appka by
si zapísala 140 BPM. Presne takto vznikla poškodená relácia o 13:07
(priemer 124, maximum 235). Preto sa meno zdroja prenáša až do parsera a
preto to drží tento súbor.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import heart_rate  # noqa: E402
import obs_websocket  # noqa: E402


# ---------------------------------------------------------------------------
# meno zdroja sa musí dostať z požiadavky von
# ---------------------------------------------------------------------------

def test_zapis_nesie_meno_aj_text():
    meno, text = obs_websocket._extract_write(
        {"inputName": "Kroky", "inputSettings": {"text": "1045"}})
    assert (meno, text) == ("Kroky", "1045")


def test_zapis_bez_mena_je_stale_platny():
    """Základná verzia appky meno neposiela — nesmie prestať fungovať."""
    meno, text = obs_websocket._extract_write(
        {"inputSettings": {"text": "86"}})
    assert meno is None and text == "86"


def test_pokazena_poziadavka_nic_nevrati():
    for zle in (None, {}, {"inputSettings": None},
                {"inputSettings": {"text": 86}}):
        assert obs_websocket._extract_write(zle) == (None, None)


# ---------------------------------------------------------------------------
# zaradenie mena
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
    """Slovenské „tep“ je vnútri anglického „s-tep-s“.

    Rovnaká pasca ako pri menovkách v texte — tam ju riešia hranice slov,
    tu poradie: kroky sa skúšajú skôr než tep.
    """
    assert heart_rate.metrika_zdroja("Steps") == "steps"


def test_nezname_meno_znamena_neviem_a_nie_tep():
    assert heart_rate.metrika_zdroja("Text 1") is None
    assert heart_rate.metrika_zdroja("") is None
    assert heart_rate.metrika_zdroja(None) is None


# ---------------------------------------------------------------------------
# samotné smerovanie hodnôt — jadro veci
# ---------------------------------------------------------------------------

def test_kroky_v_rozsahu_tepu_sa_uz_nedaju_precitat_ako_tep():
    """Toto je ten test, kvôli ktorému súbor existuje."""
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
    """Meno zdroja hovorí, ČO to je — nie že je to pravda."""
    assert heart_rate.parse_metrics(b"400", "Tep")["bpm"] is None


def test_desatinna_ciarka_v_rychlosti():
    assert heart_rate.parse_metrics(b"4,2", "Rychlost")["speed"] == 4.2


def test_nezmyselny_pocet_krokov_neprejde():
    assert heart_rate.parse_metrics(b"999999999", "Kroky")["steps"] is None


def test_len_ciste_cislo_je_hodnota():
    """Z ľubovoľného textu sa prvé číslo neberie.

    Inak by sme boli späť pri chybe, ktorá čítala tep z počtu krokov —
    len z druhej strany.
    """
    m = heart_rate.parse_metrics(b"chyba senzora 3x", "Tep")
    assert m["bpm"] is None


def test_menovky_v_texte_maju_prednost_pred_menom_zdroja():
    """Prémiová verzia vie poslať všetko do jedného zdroja."""
    m = heart_rate.parse_metrics(b"Tep: 73 Kroky: 1832", "Tep")
    assert m["bpm"] == 73 and m["steps"] == 1832


def test_bez_mena_zdroja_ostava_povodne_spravanie():
    """UDP meno zdroja nemá — stará cesta musí platiť ďalej."""
    assert heart_rate.parse_metrics(b"140")["bpm"] == 140
    assert heart_rate.parse_metrics(b"Tep 73 Kroky 1832") == {
        "bpm": 73, "steps": 1832, "speed": None}


# ---------------------------------------------------------------------------
# predstieraný OBS musí tie zdroje aj ponúknuť
# ---------------------------------------------------------------------------

def test_hrac_si_ma_v_telefone_z_coho_vybrat():
    mena = [i["inputName"]
            for i in obs_websocket._response_data("GetInputList")["inputs"]]
    assert mena == ["Tep", "Kroky", "Rychlost"]


def test_kazdy_ponukany_zdroj_vie_appka_zaradit():
    """Zoznam v OBS vrstve a rozpoznávanie v parseri sa nesmú rozísť."""
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
    """Prázdna odpoveď je pre klienta dôvod čakať do vypršania limitu."""
    d = obs_websocket._response_data("CreateInput", (), {"inputName": "speed"})
    assert d.get("inputUuid") and d.get("sceneItemId")


def test_uuid_odvodene_od_mena_je_stale():
    assert obs_websocket._uuid_pre("speed") == obs_websocket._uuid_pre("speed")
    assert obs_websocket._uuid_pre("speed") != obs_websocket._uuid_pre("steps")


# ---------------------------------------------------------------------------
# dva zdroje krokov naraz — mína, ktorá čakala na prvú prechádzku
# ---------------------------------------------------------------------------

def _kroky(hodnoty, zdroje=None, krok=0.25, start=1000.0):
    """Nakŕmi štatistiku postupnosťou počtov krokov a vráti kroky/min."""
    import hr_stats
    s = hr_stats.HeartStats()
    t = start
    for i, v in enumerate(hodnoty):
        z = zdroje[i % len(zdroje)] if zdroje else None
        s.note_metrics(steps=v, ts=t, zdroj=z)
        t += krok
    return s.steps_per_min(now=t)


def test_dva_zdroje_krokov_nevyrobia_kroky_ktore_sa_nestali():
    """Toto je ten test, kvôli ktorému oprava vznikla.

    Hodinky píšu ten istý počet krokov do dvoch zdrojov („Steps“ aj „steps“).
    Kým sa počítadlá líšia len vzájomným oneskorením, hráč sa nepohol.
    Pred opravou z toho vychádzalo 595 krokov za minútu pri prahu 15 —
    appka by si myslela, že šprintuje, a prestala by hovoriť.
    """
    assert _kroky([1085, 1080] * 120, ["Steps", "steps"]) == 0.0


def test_dva_zdroje_s_rovnakou_hodnotou_su_ticho():
    assert _kroky([1085] * 240, ["Steps", "steps"]) == 0.0


def test_skutocna_chodza_sa_z_dvoch_zdrojov_stale_zmeria():
    """Oprava nesmie kroky umlčať — len tie vymyslené."""
    hodnoty, v = [], 1000
    for _ in range(120):
        hodnoty += [v, v - 4]        # druhý zdroj zaostáva o 4 kroky
        v += 2                       # skutočný prírastok: 2 na správu
    za_minutu = _kroky(hodnoty, ["Steps", "steps"])
    assert 220.0 <= za_minutu <= 240.0, za_minutu


def test_restart_pocitadla_o_polnoci_nevyrobi_kroky():
    assert _kroky([8000, 8000, 0, 5, 10, 15], ["Steps"], krok=1.0) == 15.0


def test_bez_mena_zdroja_ostava_pocitanie_krokov_nezmenene():
    """UDP meno zdroja nemá — správanie musí byť presne ako predtým."""
    assert _kroky(list(range(1000, 1240))) == 239.0


def test_ticho_vybraneho_zdroja_prepusti_iny():
    """Keby nie, vypnutý zdroj by umlčal kroky navždy."""
    import hr_stats
    s = hr_stats.HeartStats()
    s.note_metrics(steps=1000, ts=1000.0, zdroj="Steps")
    # druhý zdroj sa medzitým nesmie presadiť
    s.note_metrics(steps=5000, ts=1001.0, zdroj="iny")
    assert s.steps_per_min(now=1001.0) == 0.0
    # ...ale po tichu pôvodného áno, a bez fiktívneho prírastku
    t = 1000.0 + hr_stats.PRELADENIE_ZDROJA_S + 1.0
    s.note_metrics(steps=5000, ts=t, zdroj="iny")
    assert s.steps_per_min(now=t) == 0.0
    s.note_metrics(steps=5010, ts=t + 1.0, zdroj="iny")
    assert s.steps_per_min(now=t + 1.0) == 10.0


def test_neviem_sa_nikdy_nestane_nulou():
    """„Hodinky kroky neposielajú“ a „hráč sedí“ sú dve rôzne veci."""
    import hr_stats
    s = hr_stats.HeartStats()
    assert s.steps_per_min() is None


# ---------------------------------------------------------------------------
# neznáme meno zdroja — pôvodná chyba bola zavretá len spolovice
# ---------------------------------------------------------------------------

def test_neznamy_zdroj_medzi_viacerymi_nevyda_tep():
    """Zaradiť vieme len mená, ktoré poznáme — a hráč si ich volí sám.

    `Cadence`, `Calories`, `Aktivita` či japonské 歩数 sú pre nás neznáma, a
    kým sa z ich holého čísla hádal tep, bola pôvodná chyba zavretá len pre
    mená, ktoré máme náhodou v zozname. Ktokoľvek iný dostal presne tú
    poškodenú reláciu z 13:07.
    """
    for meno in ("Cadence", "Calories", "Distance", "Aktivita", "歩数x",
                 "Text 1"):
        m = heart_rate.parse_metrics(b"140", meno, False)
        assert m["bpm"] is None, meno


def test_jediny_zdroj_ostava_tepom_nech_sa_vola_akokolvek():
    """„Text 1“ je predvolené meno zdroja v OBS a veľa ľudí ho nepremenuje.

    Kým píše jediný zdroj, niet čo si pomýliť — je to tep.
    """
    assert heart_rate.parse_metrics(b"140", "Text 1", True)["bpm"] == 140
    assert heart_rate.parse_metrics(b"140", None, True)["bpm"] == 140


def test_menovka_v_texte_prejde_aj_z_nezname_zdroja():
    """Potláča sa HOLÉ číslo, nie explicitná menovka."""
    assert heart_rate.parse_metrics(b"Tep: 86", "Cadence", False)["bpm"] == 86
    assert heart_rate.parse_metrics(b'{"bpm": 86}', "Cadence", False)["bpm"] == 86


def test_beh_si_pamata_ktore_zdroje_uz_pisali():
    r = heart_rate._Run(1)
    assert r.note_source("Tep") is True          # prvý
    assert r.note_source("Tep") is True          # stále jediný
    assert r.note_source("Kroky") is False       # už sú dva


# ---------------------------------------------------------------------------
# hranice slov — tá istá pasca tretíkrát
# ---------------------------------------------------------------------------

def test_hrv_a_threshold_nie_su_tep():
    """`hr` má dva znaky a ako obyčajný podreťazec sa chytil na „T-hr-eshold“
    aj na „HRV“. HRV navyše prémiové appky naozaj posielajú."""
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
# oddeľovač tisícov
# ---------------------------------------------------------------------------

def test_pocet_krokov_znesie_oddelovac_tisicov():
    """Hodinky formátujú číslo pre overlay podľa locale.

    Rozlíšiť to na úrovni reťazca sa nedá — „4,2“ je platná rýchlosť. Na
    úrovni metriky áno: krok je vždy celé číslo.
    """
    for text in (b"1,085", b"1 085", b"1.085", b"1085"):
        assert heart_rate.parse_metrics(text, "Kroky")["steps"] == 1085, text
    assert heart_rate.parse_metrics(b"12,345", "Kroky")["steps"] == 12345


def test_desatinne_cislo_nie_je_pocet_krokov():
    assert heart_rate.parse_metrics(b"4,2", "Kroky")["steps"] is None
    assert heart_rate.parse_metrics(b"4,2", "Rychlost")["speed"] == 4.2


# ---------------------------------------------------------------------------
# dávka požiadaviek — toto bol ten „timeout waiting 10000 ms“
# ---------------------------------------------------------------------------

def test_davka_ide_rovnakou_cestou_ako_samostatna_poziadavka():
    """`op 8` prepadával cez celý if/elif reťazec bez akejkoľvek odpovede.

    Appka na hodinkách, ktorá posiela viac metrík, ich zvykne poslať naraz
    ako dávku. Klient potom čakal desať sekúnd a hlásil, že prijímač
    neexistuje. Ani zápis o neznámej požiadavke to nechytil — ten je vnútri
    vetvy `op == 6`, kam sa dávka nikdy nedostala.
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
    """Nech sa ticho okolo ďalšieho `op` nedá prehliadnuť — čokoľvek mimo
    tohto zoznamu sa zapíše do denníka."""
    assert 8 not in obs_websocket._TICHE_OP      # dávka sa MUSÍ odbaviť
    assert 6 not in obs_websocket._TICHE_OP
    assert 0 in obs_websocket._TICHE_OP          # Hello je náš vlastný výstup


# ---------------------------------------------------------------------------
# zápis tepu až po Identify (B6)
# ---------------------------------------------------------------------------

def test_zapis_tepu_sa_odmietne_pred_identify():
    """B6: čokoľvek v LAN, čo dokončí WS handshake, mohlo poslať ľubovoľné
    „BPM" a zapísalo sa ako reálny tep. Zápis (SetInputSettings) sa smie
    prijať až keď sa klient identifikoval (op 1)."""
    zapisane = []
    req = {"requestType": "SetInputSettings", "requestId": "a",
           "requestData": {"inputName": "Tep", "inputSettings": {"text": "200"}}}
    # pred Identify: zápis sa MUSÍ ignorovať
    obs_websocket._odbav(req, lambda t, z: zapisane.append(t),
                         set(), set(), zapis_ok=False)
    assert zapisane == [], "tep sa zapísal bez identifikácie (B6)"
    # po Identify: zápis prejde
    obs_websocket._odbav(req, lambda t, z: zapisane.append(t),
                         set(), set(), zapis_ok=True)
    assert zapisane == ["200"]


def test_citania_prejdu_aj_pred_identify():
    """Odmieta sa len ZÁPIS — čítania (GetInputList a spol.) sú neškodné a
    klient ich smie dostať, nech sa protokol nezasekne."""
    d = obs_websocket._odbav(
        {"requestType": "GetInputList", "requestId": "x"},
        lambda t, z: None, set(), set(), zapis_ok=False)
    assert d["requestStatus"]["result"] is True


def test_serve_connection_strazi_identify():
    """Slučka spojenia musí zápis viazať na Identify (op 1)."""
    import inspect
    telo = inspect.getsource(obs_websocket.serve_connection)
    assert "identified" in telo
    assert "zapis_ok=identified" in telo


# ---------------------------------------------------------------------------
# adresovanie zdroja cez inputUuid (B7)
# ---------------------------------------------------------------------------

def test_zapis_cez_uuid_dohlada_meno_zdroja():
    """B7: obs-websocket v5 dovoľuje adresovať zdroj cez inputUuid namiesto
    mena. UUID sme rozdávali sami → vieme ho zmapovať späť. Bez toho by kroky
    adresované cez UUID nemali meno a čítali sa ako tep."""
    uuid_kroky = dict(obs_websocket.ZDROJE)["Kroky"]
    meno, text = obs_websocket._extract_write(
        {"inputUuid": uuid_kroky, "inputSettings": {"text": "1045"}})
    assert (meno, text) == ("Kroky", "1045")


def test_zapis_cez_uuid_klientom_vyrobeneho_zdroja():
    """Zdroj, ktorý si klient vyrobil (napr. „steps"), sa cez UUID nájde,
    ak jeho meno appka v spojení už videla."""
    u = obs_websocket._uuid_pre("steps")
    meno, _ = obs_websocket._extract_write(
        {"inputUuid": u, "inputSettings": {"text": "1200"}}, {"steps"})
    assert meno == "steps"


def test_neznamy_uuid_nechyti_tep():
    """Neznámy UUID → žiadne meno → holé číslo NIE je tep (chráni to
    viaczdrojová logika v parse_metrics)."""
    meno, _ = obs_websocket._extract_write(
        {"inputUuid": "ffffffff-0000-4000-8000-000000000000",
         "inputSettings": {"text": "140"}})
    assert meno is None
    # a s viacerými zdrojmi sa z toho tep nestane
    assert heart_rate.parse_metrics(b"140", meno, False)["bpm"] is None


def test_steps_per_min_je_none_ked_kroky_prestali_chodit():
    """B32: keď hodinky prestanú posielať kroky, je to NEVIEME, nie 0.
    Kým správy chodia (aj nulový prírastok), je platná nula."""
    import hr_stats
    s = hr_stats.HeartStats()
    assert s.steps_per_min(now=1000.0) is None          # nikdy nič neprišlo
    s.note_metrics(steps=1000, ts=1000.0, zdroj="Kroky")
    s.note_metrics(steps=1000, ts=1001.0, zdroj="Kroky")   # nulový prírastok
    assert s.steps_per_min(now=1001.0) == 0.0            # chodí → nula
    # o dve minúty ticha → nevieme, nie nula
    assert s.steps_per_min(now=1001.0 + 120.0) is None
