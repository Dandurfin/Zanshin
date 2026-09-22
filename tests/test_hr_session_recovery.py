# -*- coding: utf-8 -*-
"""Regresie okolo meracej relácie tepu — bez Tk, čítaním zdrojáku.

`_retry_hr_bind` točí skutočné sockety a vlákna, takže integračný test by bol
krehký. Tieto invarianty sa preto strážia staticky cez AST: „funkcia X volá
funkciu Y". Presne to je jadro chyby A1 — obnovený socket bez obnovenej
relácie.
"""
import ast
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _telo_metody(trieda, metoda):
    src = open(os.path.join(ROOT, "app.py"), encoding="utf-8-sig").read()
    strom = ast.parse(src)
    for uzol in ast.walk(strom):
        if isinstance(uzol, ast.ClassDef) and uzol.name == trieda:
            for pod in uzol.body:
                if isinstance(pod, ast.FunctionDef) and pod.name == metoda:
                    return ast.get_source_segment(src, pod)
    raise AssertionError("nenašla sa %s.%s" % (trieda, metoda))


def _volania(telo):
    """Mená volaných metód `self.<...>` v tele funkcie."""
    mena = set()
    for uzol in ast.walk(ast.parse(telo.strip())):
        if (isinstance(uzol, ast.Call)
                and isinstance(uzol.func, ast.Attribute)
                and isinstance(uzol.func.value, ast.Name)
                and uzol.func.value.id == "self"):
            mena.add(uzol.func.attr)
    return mena


def test_retry_po_obsadenom_porte_znovu_otvori_relaciu():
    """A1: po úspešnom obnovení socketu sa MUSÍ znova otvoriť relácia.

    Bez toho appka po obnovenom porte ukazuje živý tep, ale `_hr_session_open`
    ostáva False — `_tick_cue_trigger` sa pri zatvorenej relácii hneď vracia,
    takže sa nikdy neozve a na konci neuloží nič. Celý večer merania zmizne
    ticho. `busy` vetva reláciu zavrela; retry ju musí vrátiť.
    """
    telo = _telo_metody("DandurfApp", "_retry_hr_bind")
    assert "heart_rate_monitor.start" in telo, "_retry_hr_bind musí obnoviť socket"
    assert "_open_hr_session" in _volania(telo), (
        "_retry_hr_bind musí po úspešnom start() znova otvoriť reláciu — "
        "inak beží tep, ale nič sa nemeria ani neuloží (A1)")


def test_busy_vetva_relaciu_zavrie_a_ulozi():
    """`busy` vetva musí reláciu zavrieť cez `_close_hr_session` (ten ukladá),
    nie ju len zahodiť — dáta spred výpadku sa nesmú stratiť."""
    telo = _telo_metody("DandurfApp", "_apply_hr_status")
    assert "_close_hr_session" in _volania(telo)


def test_open_hr_session_sa_nedotyka_siete():
    """Retry volá `_open_hr_session(prepoj=False)` po tom, čo `start()` už
    socket obnovil — `_open_hr_session` teda NESMIE reštartovať sieť, inak by
    hodinky odpojil dvakrát."""
    telo = _telo_metody("DandurfApp", "_open_hr_session")
    assert "heart_rate_monitor.start" not in telo, (
        "_open_hr_session sa nesmie dotýkať siete")


# ---------------------------------------------------------------------------
# A2 — dýchajúci pás nesmie tvrdiť "Sledujem tep", keď tep nechodí
# ---------------------------------------------------------------------------

def test_pas_vychadza_zo_stavu_spojenia_nie_z_prepinaca():
    """A2: `_kamae_state_text` musí rozlíšiť "počúvam a tep chodí" od
    "počúvam, ale nič nechodí". Dovtedy hlásil "Sledujem tep" len podľa
    prepínača — aj pri výpadku, obsadenom porte či pred prvým pripojením."""
    telo = _telo_metody("DandurfApp", "_kamae_state_text")
    assert "_hr_state" in telo and "_hr_last_bpm" in telo, (
        "pás sa musí pýtať na skutočný stav spojenia, nie len na prepínač")
    assert "kamae.no_hr" in telo, "musí existovať pravdivá vetva 'čakám na tep'"


def test_pas_sa_prekresli_pri_zmene_spojenia():
    """Pravdivá vetva je zbytočná, ak sa pás pri zmene stavu neprekreslí.

    `_apply_hr_status` (výpadok/busy/connecting) aj `_apply_hr_bpm` (tep sa
    vrátil) musia zavolať `_refresh_kamae_state_text`.
    """
    for metoda in ("_apply_hr_status", "_apply_hr_bpm"):
        assert "_refresh_kamae_state_text" in _volania(_telo_metody("DandurfApp", metoda)), \
            "%s musí prekresliť pás" % metoda


def test_no_hr_sa_lisi_od_no_watch():
    """Vypnutý senzor a "počúvam bez tepu" sú dva rôzne stavy — dva texty."""
    import i18n
    assert i18n.tr_lang("sk", "kamae.no_hr") != i18n.tr_lang("sk", "kamae.no_watch")
    for jazyk in ("sk", "en"):
        assert i18n.tr_lang(jazyk, "kamae.no_hr_sub").strip()


# ---------------------------------------------------------------------------
# A3 — varovanie o exkluzívnom fullscreene musí bežať, keď je popredím HRA
# ---------------------------------------------------------------------------

def test_fullscreen_varovanie_sa_kontroluje_pocas_relacie_nie_pri_starte():
    """A3: kontrola v `start_heart_rate_monitor` bola mŕtva — vtedy je
    popredím Zanshin, nie hra, takže `is_fullscreen_foreground` vždy False.
    Musí bežať z `_tick_session` (vtedy býva popredím hra)."""
    start = _telo_metody("DandurfApp", "start_heart_rate_monitor")
    tick = _telo_metody("DandurfApp", "_tick_session")
    assert "_warn_exclusive_fullscreen_once" not in _volania(start), (
        "kontrola pri štarte je mŕtva — popredím je Zanshin, nie hra")
    assert "_warn_exclusive_fullscreen_once" in _volania(tick), (
        "kontrola musí bežať z _tick_session, keď je popredím hra")


# ---------------------------------------------------------------------------
# B17/B19 — nedoručená hláška sa nemeria ani neráta v dotazníku
# ---------------------------------------------------------------------------

def test_fire_somatic_cue_prenasa_ci_sa_vykreslilo():
    """B17: `_fire_somatic_cue` musí vrátiť, či sa vizuál naozaj vykreslil,
    a odovzdať to do `note_trigger(delivered=...)`, nech `measure` vie
    nedoručené okno vylúčiť."""
    telo = _telo_metody("DandurfApp", "_fire_somatic_cue")
    assert "overlay_manager.trigger" in telo
    assert "delivered=" in telo, "note_trigger musí dostať delivered"
    assert "return" in telo, "_fire_somatic_cue musí vrátiť výsledok doručenia"


def test_on_cue_event_zaznamena_dorucenie():
    """`_on_cue_event` musí do záznamu zapísať, či `_fire_somatic_cue`
    naozaj doručil — inak dotazník ráta aj nedoručené (B19)."""
    telo = _telo_metody("DandurfApp", "_on_cue_event")
    assert "delivered" in telo
    assert "_fire_somatic_cue" in _volania(telo)


def test_dotaznik_rata_len_dorucene_hlasky():
    """B19: dotazník hlásil 'Ozvala som sa 3×' aj keď boli všetky hlášky
    vypnuté (E_DELIVER sa zapísal pred rozhodnutím). Musí filtrovať na
    `delivered`."""
    telo = _telo_metody("DandurfApp", "_ask_session_context")
    assert "delivered" in telo, "počet hlášok v dotazníku musí filtrovať doručené"


# ---------------------------------------------------------------------------
# B2/B3 — pravdivosť stavu senzora
# ---------------------------------------------------------------------------

def test_busy_po_vzdani_sa_meni_stav():
    """B3: po vyčerpaní pokusov sa stav MUSÍ zmeniť z 'busy' — inak štítok
    navždy tvrdí 'skúšam znova', hoci to už nikto neskúša."""
    telo = _telo_metody("DandurfApp", "_apply_hr_status")
    assert '"busy_gave_up"' in telo, "po vzdaní sa musí nastaviť iný stav"
    disp = _telo_metody("DandurfApp", "_hr_status_display")
    assert "busy_gave_up" in disp and "no_client" in disp


def test_no_client_po_case_bez_pripojenia():
    """B2: keď sa nikto nepripojí, stav sa odlíši od 'connecting'."""
    telo = _telo_metody("DandurfApp", "_hr_no_client")
    assert '"no_client"' in telo
    # a spúšťa sa pri štarte, ruší pri príchode klienta
    assert "_schedule_no_client_check" in _volania(
        _telo_metody("DandurfApp", "start_heart_rate_monitor"))
    assert "_cancel_no_client_check" in _volania(
        _telo_metody("DandurfApp", "_apply_hr_status"))


def test_trouble_a_stavy_maju_texty():
    import i18n
    assert "firewall" in i18n.tr_lang("sk", "hr.trouble_body").lower()
    for kluc in ("settings.hr_status_no_client", "settings.hr_status_busy_gave_up"):
        assert i18n.tr_lang("sk", kluc).strip()
        assert i18n.tr_lang("en", kluc).strip()
