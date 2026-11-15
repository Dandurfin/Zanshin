# -*- coding: utf-8 -*-
"""Heart-rate measurement session regressions — no Tk, by reading the source.

`_retry_hr_bind` spins real sockets and threads, so an integration test
would be brittle. These invariants are therefore guarded statically via
AST: „function X calls function Y". That is exactly the core of bug A1 — a
restored socket without a restored session.
"""
import ast

from _zdroj_appky import zdroj_metody


def _telo_metody(trieda, metoda):
    # DandurfApp is split into mixins (app_*.py) - the method is looked for in
    # it and in all the mixins (the same as what Python finds via the MRO).
    assert trieda == "DandurfApp", trieda
    return zdroj_metody(metoda)


def _volania(telo):
    """Names of the called `self.<...>` methods in a function body."""
    mena = set()
    for uzol in ast.walk(ast.parse(telo.strip())):
        if (isinstance(uzol, ast.Call)
                and isinstance(uzol.func, ast.Attribute)
                and isinstance(uzol.func.value, ast.Name)
                and uzol.func.value.id == "self"):
            mena.add(uzol.func.attr)
    return mena


def test_retry_po_obsadenom_porte_znovu_otvori_relaciu():
    """A1: after a successful socket restore the session MUST open again.

    Without that the app shows a live heart rate after the restored port,
    but `_hr_session_open` stays False — `_tick_cue_trigger` returns right
    away when the session is closed, so it never speaks up and saves
    nothing at the end. A whole evening of measurement vanishes silently.
    The `busy` branch closed the session; the retry has to bring it back.
    """
    telo = _telo_metody("DandurfApp", "_retry_hr_bind")
    assert "heart_rate_monitor.start" in telo, "_retry_hr_bind musí obnoviť socket"
    assert "_open_hr_session" in _volania(telo), (
        "_retry_hr_bind musí po úspešnom start() znova otvoriť reláciu — "
        "inak beží tep, ale nič sa nemeria ani neuloží (A1)")


def test_busy_vetva_relaciu_zavrie_a_ulozi():
    """The `busy` branch must close the session through `_close_hr_session`
    (that one saves), not just throw it away — the data from before the
    dropout must not be lost."""
    telo = _telo_metody("DandurfApp", "_apply_hr_status")
    assert "_close_hr_session" in _volania(telo)


def test_open_hr_session_sa_nedotyka_siete():
    """The retry calls `_open_hr_session(prepoj=False)` after `start()` has
    already restored the socket — so `_open_hr_session` MUST NOT restart the
    network, otherwise it would disconnect the watch twice."""
    telo = _telo_metody("DandurfApp", "_open_hr_session")
    assert "heart_rate_monitor.start" not in telo, (
        "_open_hr_session sa nesmie dotýkať siete")


# ---------------------------------------------------------------------------
# A2 — the breathing bar must not claim "Sledujem tep" when no heart rate comes
# ---------------------------------------------------------------------------

def test_pas_vychadza_zo_stavu_spojenia_nie_z_prepinaca():
    """A2: `_kamae_state_text` must tell "listening and the heart rate is
    coming" from "listening, but nothing is coming". Until then it reported
    "Sledujem tep" (Watching your heart rate) based on the switch alone —
    even during a dropout, with a busy port or before the first connection."""
    telo = _telo_metody("DandurfApp", "_kamae_state_text")
    assert "_hr_state" in telo and "_hr_last_bpm" in telo, (
        "pás sa musí pýtať na skutočný stav spojenia, nie len na prepínač")
    assert "kamae.no_hr" in telo, "musí existovať pravdivá vetva 'čakám na tep'"


def test_pas_sa_prekresli_pri_zmene_spojenia():
    """A truthful branch is useless if the bar is not redrawn on state change.

    `_apply_hr_status` (dropout/busy/connecting) and `_apply_hr_bpm` (the
    heart rate came back) must both call `_refresh_kamae_state_text`.
    """
    for metoda in ("_apply_hr_status", "_apply_hr_bpm"):
        assert "_refresh_kamae_state_text" in _volania(_telo_metody("DandurfApp", metoda)), \
            "%s musí prekresliť pás" % metoda


def test_no_hr_sa_lisi_od_no_watch():
    """Sensor off and "listening, no heart rate" are two states — two texts."""
    import i18n
    assert i18n.tr_lang("sk", "kamae.no_hr") != i18n.tr_lang("sk", "kamae.no_watch")
    for jazyk in ("sk", "en"):
        assert i18n.tr_lang(jazyk, "kamae.no_hr_sub").strip()


# ---------------------------------------------------------------------------
# A3 — the exclusive-fullscreen warning must run when the GAME is in front
# ---------------------------------------------------------------------------

def test_fullscreen_varovanie_sa_kontroluje_pocas_relacie_nie_pri_starte():
    """A3: the check in `start_heart_rate_monitor` was dead — at that point
    Zanshin is in the foreground, not the game, so
    `is_fullscreen_foreground` is always False. It must run from
    `_tick_session` (then the game is usually in the foreground)."""
    start = _telo_metody("DandurfApp", "start_heart_rate_monitor")
    tick = _telo_metody("DandurfApp", "_tick_session")
    assert "_warn_exclusive_fullscreen_once" not in _volania(start), (
        "kontrola pri štarte je mŕtva — popredím je Zanshin, nie hra")
    assert "_warn_exclusive_fullscreen_once" in _volania(tick), (
        "kontrola musí bežať z _tick_session, keď je popredím hra")


# ---------------------------------------------------------------------------
# B17/B19 — an undelivered cue is not measured or counted in the questionnaire
# ---------------------------------------------------------------------------

def test_fire_somatic_cue_prenasa_ci_sa_vykreslilo():
    """B17: `_fire_somatic_cue` must return whether the visual was really
    drawn, and pass it on to `note_trigger(delivered=...)`, so that `measure`
    can exclude the undelivered window."""
    telo = _telo_metody("DandurfApp", "_fire_somatic_cue")
    assert "overlay_manager.trigger" in telo
    assert "delivered=" in telo, "note_trigger musí dostať delivered"
    assert "return" in telo, "_fire_somatic_cue musí vrátiť výsledok doručenia"


def test_on_cue_event_zaznamena_dorucenie():
    """`_on_cue_event` must write into the record whether `_fire_somatic_cue`
    really delivered — otherwise the questionnaire also counts undelivered
    ones (B19)."""
    telo = _telo_metody("DandurfApp", "_on_cue_event")
    assert "delivered" in telo
    assert "_fire_somatic_cue" in _volania(telo)


def test_dotaznik_rata_len_dorucene_hlasky():
    """B19: the questionnaire reported 'Ozvala som sa 3×' (I spoke up 3×) even
    when all cues were switched off (E_DELIVER was written before the
    decision). It must filter on `delivered`."""
    telo = _telo_metody("DandurfApp", "_ask_session_context")
    assert "delivered" in telo, "počet hlášok v dotazníku musí filtrovať doručené"


# ---------------------------------------------------------------------------
# B2/B3 — truthfulness of the sensor state
# ---------------------------------------------------------------------------

def test_busy_po_vzdani_sa_meni_stav():
    """B3: after the attempts run out the state MUST change from 'busy' —
    otherwise the label claims 'skúšam znova' (trying again) forever,
    although nobody is trying any more."""
    telo = _telo_metody("DandurfApp", "_apply_hr_status")
    assert '"busy_gave_up"' in telo, "po vzdaní sa musí nastaviť iný stav"
    disp = _telo_metody("DandurfApp", "_hr_status_display")
    assert "busy_gave_up" in disp and "no_client" in disp


def test_no_client_po_case_bez_pripojenia():
    """B2: when nobody connects, the state differs from 'connecting'."""
    telo = _telo_metody("DandurfApp", "_hr_no_client")
    assert '"no_client"' in telo
    # and it is started at start-up, cancelled when a client arrives
    assert "_schedule_no_client_check" in _volania(
        _telo_metody("DandurfApp", "start_heart_rate_monitor"))
    assert "_cancel_no_client_check" in _volania(
        _telo_metody("DandurfApp", "_apply_hr_status"))


def test_trouble_a_stavy_maju_texty():
    import i18n
    # 0.3: the firewall tip moved from "connects, but no heart rate comes"
    # (trouble_body) to the "does not connect at all" box - that cause belongs
    # there.
    assert "firewall" in i18n.tr_lang("sk", "hr.noconnect_body").lower()
    assert "firewall" not in i18n.tr_lang("sk", "hr.trouble_body").lower()
    for kluc in ("settings.hr_status_no_client", "settings.hr_status_busy_gave_up"):
        assert i18n.tr_lang("sk", kluc).strip()
        assert i18n.tr_lang("en", kluc).strip()
