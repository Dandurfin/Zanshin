# -*- coding: utf-8 -*-
"""Stavový automat hlášky — natiahnutie, odklad na pauzu, tiché rameno.

Hodiny sú podstrčené, takže testy nič nečakajú v reálnom čase a 90-sekundové
zotrvanie sa odsimuluje okamžite.

Väčšina testov nižšie existuje preto, že práve tie prípady označila
adversariálna kontrola návrhu za miesta, kde by sa meranie ticho pokazilo:
zlúčenie `arm` a `delivery`, chýbajúci návrat z cooldownu, tolerancia
prepadu, ktorá by z „súvisle nad 55" spravila „ani raz pod 45".
"""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trigger  # noqa: E402


class Hodiny:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def posun(self, o):
        self.t += o


def spusti(silent_share=0.0, rng_seed=1, **params):
    """Automat s pevným generátorom, takže rameno je predvídateľné."""
    h = Hodiny()
    t = trigger.CueTrigger(params=params, rng=random.Random(rng_seed), clock=h)
    t.open_session(silent_share=silent_share)
    return t, h


def natiahni(t, h, stress=80.0, krok=1.0):
    """Drž záťaž nad prahom, kým sa nenatiahne. Vráti udalosť natiahnutia."""
    for _ in range(200):
        ev = t.note_load(stress, h.t)
        if ev:
            return ev
        h.posun(krok)
    raise AssertionError("nenatiahlo sa")


# --------------------------------------------------------------------------
# Natiahnutie
# --------------------------------------------------------------------------

def test_spicka_nenatiahne():
    """Skok po headshote nie je stres. Dve minúty na 120 áno."""
    t, h = spusti()
    for _ in range(10):                 # 10 s vysokej záťaže
        assert t.note_load(95.0, h.t) is None
        h.posun(1.0)
    assert t.state == trigger.RISING
    assert not t.is_armed


def test_zotrvanie_nad_prahom_natiahne():
    t, h = spusti()
    ev = natiahni(t, h)
    assert ev["typ"] == trigger.E_ARMED
    assert t.is_armed


def test_kratky_prepad_natiahnutie_nezrusi():
    """`stress` je vyhladený exponenciálnym priemerom a na hranici kmitá.
    Tri sekundy pod prahom ho nesmú zhodiť."""
    t, h = spusti()
    for _ in range(40):
        t.note_load(80.0, h.t)
        h.posun(1.0)
    for _ in range(3):                  # krátky prepad
        t.note_load(40.0, h.t)
        h.posun(1.0)
    for _ in range(60):
        ev = t.note_load(80.0, h.t)
        if ev:
            break
        h.posun(1.0)
    assert t.is_armed


def test_dlhy_prepad_natiahnutie_zrusi():
    # Tolerancia sa tu určuje výslovne. Predtým sa test spoliehal na
    # predvolenú hodnotu a spadol vo chvíli, keď sa zmenila z 5 s na 20 s —
    # hoci na správaní, ktoré overuje, sa nezmenilo nič.
    t, h = spusti(dip_grace_s=5.0)
    for _ in range(40):
        t.note_load(80.0, h.t)
        h.posun(1.0)
    for _ in range(10):                 # dlhší prepad než tolerancia
        t.note_load(40.0, h.t)
        h.posun(1.0)
    assert t.state == trigger.IDLE
    assert t._above_since is None


def test_cas_pod_prahom_sa_do_zotrvania_nepocita():
    """Poistka proti chybe, ktorú našla kontrola návrhu: „súvisle nad 55"
    sa nesmie zvrhnúť na „ani raz pod 45".

    Záťaž kmitajúca tesne pod prahom nesmie natiahnuť, nech beží akokoľvek
    dlho.
    """
    t, h = spusti()
    for _ in range(300):
        assert t.note_load(50.0, h.t) is None    # pod prahom 55
        h.posun(1.0)
    assert not t.is_armed


# --------------------------------------------------------------------------
# Odklad na pauzu
# --------------------------------------------------------------------------

def test_pauza_dorucí_hlasku():
    t, h = spusti()
    natiahni(t, h)
    assert t.tick(pause_s=0.0, now=h.t) is None      # hrá, nedoručuje sa
    h.posun(5.0)
    ev = t.tick(pause_s=3.0, now=h.t)
    assert ev["typ"] == trigger.E_DELIVER
    assert ev["delivery"] == trigger.D_PAUSE
    assert ev["hlas"] is True


def test_ked_pauza_nepride_ide_tichy_vizual():
    t, h = spusti()
    natiahni(t, h)
    h.posun(91.0)                                    # prešiel max_wait_s
    ev = t.tick(pause_s=0.0, now=h.t)
    assert ev["delivery"] == trigger.D_TIMEOUT
    assert ev["hlas"] is False                       # bez hlasu
    assert ev["arm"] == trigger.ARM_VOICE            # ale rameno je hlasné!


def test_timeout_nie_je_tiche_rameno():
    """Najdôležitejší test v súbore.

    Keď pauza nepríde, hláška ide ticho — ale NIE JE to kontrolné rameno.
    Keby sa oboje zapísalo ako arm="silent", measure.summarize() by
    porovnával dve rôzne veci: jedna skupina mala pauzu, druhá nie, a
    rozdiel medzi ramenami by meral práve toto.
    """
    t, h = spusti(silent_share=0.0)                  # nikdy nelosuj ticho
    natiahni(t, h)
    h.posun(91.0)
    ev = t.tick(pause_s=0.0, now=h.t)
    assert ev["hlas"] is False                       # nezaznelo
    assert ev["arm"] == trigger.ARM_VOICE            # ale patrí do hlasného
    assert ev["delivery"] == trigger.D_TIMEOUT       # a dôvod je zapísaný


def test_odchod_od_pc_nie_je_pauza():
    t, h = spusti()
    natiahni(t, h)
    ev = t.tick(pause_s=200.0, now=h.t)
    assert ev["typ"] == trigger.E_ABORT
    assert ev["reason"] == trigger.A_ODISIEL


def test_neznama_pauza_nedoruci_hned_ale_ani_necaka_navzdy():
    """pause_s() vracia None, keď systém idle nehlási.

    Nesmie sa to tváriť ani ako „pauza je" (doručilo by sa hneď), ani ako
    „pauza nie je navždy". Nechá sa dobehnúť max_wait_s a doručí sa ticho.
    """
    t, h = spusti()
    natiahni(t, h)
    assert t.tick(pause_s=None, now=h.t) is None
    h.posun(91.0)
    ev = t.tick(pause_s=None, now=h.t)
    assert ev["delivery"] == trigger.D_TIMEOUT


def test_ked_sa_nesmie_natiahnutie_sa_nespali():
    """can_fire=False (cooldown, vypnutý vizuál) natiahnutie nezruší —
    čaká sa ďalej."""
    t, h = spusti()
    natiahni(t, h)
    h.posun(5.0)
    assert t.tick(pause_s=5.0, now=h.t, can_fire=False) is None
    assert t.is_armed
    ev = t.tick(pause_s=5.0, now=h.t, can_fire=True)
    assert ev["typ"] == trigger.E_DELIVER


# --------------------------------------------------------------------------
# Cooldown
# --------------------------------------------------------------------------

def test_po_hlaske_sa_da_natiahnut_znova():
    """Kontrola návrhu našla verziu, v ktorej prechod z cooldownu späť
    neexistoval — po prvej hláške by relácia už nikdy nič nespustila."""
    t, h = spusti()
    natiahni(t, h)
    h.posun(5.0)
    assert t.tick(pause_s=3.0, now=h.t)["typ"] == trigger.E_DELIVER
    assert t.state == trigger.COOLDOWN

    h.posun(300.0)                                   # viac než min_gap_s
    t.tick(pause_s=0.0, now=h.t)
    assert t.state == trigger.IDLE
    natiahni(t, h)
    assert t.is_armed


def test_odstup_je_dlhsi_nez_refrakterna_zona():
    """min_gap_s musí byť väčší než measure.REFRACTORY_AFTER_S (180 s).

    Inak si dve hlášky navzájom zneplatnia meracie okná a mesiac merania
    je na nič.
    """
    import measure
    assert trigger.default_params()["min_gap_s"] > measure.REFRACTORY_AFTER_S


# --------------------------------------------------------------------------
# Tiché rameno
# --------------------------------------------------------------------------

def test_rameno_sa_losuje_uz_pri_natiahnuti():
    """Aby sa dalo zapísať aj vtedy, keď sa hláška nakoniec nedoručí."""
    t, h = spusti(silent_share=1.0)
    ev = natiahni(t, h)
    assert ev["arm"] == trigger.ARM_SILENT


def test_tiche_rameno_nezaznie_ale_dorucí_sa():
    t, h = spusti(silent_share=1.0)
    natiahni(t, h)
    h.posun(5.0)
    ev = t.tick(pause_s=3.0, now=h.t)
    assert ev["typ"] == trigger.E_DELIVER            # okno sa zapíše
    assert ev["delivery"] == trigger.D_PAUSE         # pauza naozaj prišla
    assert ev["hlas"] is False                       # len nezaznie


def test_podiel_ticha_klesne_po_kalibracii():
    assert trigger.silent_share_for(0) == 0.25
    assert trigger.silent_share_for(14) == 0.25
    assert trigger.silent_share_for(15) == 0.10
    assert trigger.silent_share_for(400) == 0.10


def test_podiel_ticha_nikdy_nie_je_nula():
    """Bez kontrolného ramena vyjde „funguje" vždy, aj keby appka mlčala —
    tep sa vracia dole aj sám."""
    for n in (0, 15, 100, 10000):
        assert trigger.silent_share_for(n) > 0


def test_losovanie_nezavisi_od_modulového_random():
    """`app.fire_slot` používa random.uniform na jitter. Keby automat bral
    z modulového generátora, akýkoľvek random.seed() inde v appke by
    posunul aj rameno a kontrolná skupina by prestala byť náhodná."""
    vysledky = []
    for _ in range(2):
        random.seed(12345)
        t, h = spusti(silent_share=0.5, rng_seed=7)
        vysledky.append(natiahni(t, h)["arm"])
    assert vysledky[0] == vysledky[1]


# --------------------------------------------------------------------------
# Prerušenia
# --------------------------------------------------------------------------

def test_snooze_zrusi_natiahnutie():
    t, h = spusti()
    natiahni(t, h)
    ev = t.suspend(trigger.A_SNOOZE, now=h.t)
    assert ev["reason"] == trigger.A_SNOOZE
    assert t.state == trigger.DORMANT
    assert t.tick(pause_s=5.0, now=h.t) is None      # počas snooze ani vizuál


def test_vypadok_tepu_zrusi_natiahnutie_a_pocita_sa_odznova():
    t, h = spusti()
    natiahni(t, h)
    t.suspend(trigger.A_TEP_VYPADOL, now=h.t)
    t.resume(now=h.t)
    assert t.state == trigger.IDLE
    for _ in range(10):                              # 10 s nestačí
        t.note_load(80.0, h.t)
        h.posun(1.0)
    assert not t.is_armed                            # 90 s sa počíta odznova


def test_koniec_relacie_v_stave_cakania_sa_zapise():
    """Podľa toho, ako často sa to stáva, sa dá ladiť max_wait_s."""
    t, h = spusti()
    natiahni(t, h)
    h.posun(30.0)
    ev = t.close_session(now=h.t)
    assert ev["reason"] == trigger.A_KONIEC_RELACIE
    assert ev["waited_s"] == 30.0


# --------------------------------------------------------------------------
# Vývojárska vrstva — parametre len medzi reláciami (§3.3)
# --------------------------------------------------------------------------

def _zdroj(meno):
    # utf-8-sig, nie utf-8: app.py ma na zaciatku BOM a `ast.parse` na nom
    # padne s "invalid non-printable character U+FEFF".
    cesta = os.path.join(os.path.dirname(__file__), "..", meno)
    return open(cesta, encoding="utf-8-sig").read()


def _telo(meno_suboru, meno_funkcie):
    """Telo funkcie ako kód, BEZ docstringu a komentárov.

    Hľadať podreťazec v surovom zdrojáku je pasca: docstring často
    vysvetľuje, prečo sa niečo NEPOUŽÍVA, a test na tom spadne. Preto sa
    číta AST a docstring sa zahodí.
    """
    import ast
    strom = ast.parse(_zdroj(meno_suboru))
    for uzol in ast.walk(strom):
        if isinstance(uzol, ast.FunctionDef) and uzol.name == meno_funkcie:
            telo = uzol.body
            if (telo and isinstance(telo[0], ast.Expr)
                    and isinstance(telo[0].value, ast.Constant)
                    and isinstance(telo[0].value.value, str)):
                telo = telo[1:]
            return "\n".join(ast.unparse(p) for p in telo)
    raise AssertionError(f"{meno_funkcie} sa v {meno_suboru} nenašla")


def _telo_metody(meno_suboru, trieda, metoda):
    """Telo metódy KONKRÉTNEJ triedy.

    `_telo` berie prvú funkciu daného mena v súbore — a to je pasca: keď
    v `ui_shell.py` pribudol `_StateDot.set_live`, test o ense začal čítať
    cudziu metódu a padol. Meno samo o sebe nestačí.
    """
    import ast
    strom = ast.parse(_zdroj(meno_suboru))
    for uzol in ast.walk(strom):
        if not (isinstance(uzol, ast.ClassDef) and uzol.name == trieda):
            continue
        for pod in uzol.body:
            if isinstance(pod, ast.FunctionDef) and pod.name == metoda:
                telo = pod.body
                if (telo and isinstance(telo[0], ast.Expr)
                        and isinstance(telo[0].value, ast.Constant)
                        and isinstance(telo[0].value.value, str)):
                    telo = telo[1:]
                return chr(10).join(ast.unparse(x) for x in telo)
        raise AssertionError(f"{trieda}.{metoda} sa nenašla")
    raise AssertionError(f"trieda {trieda} sa v {meno_suboru} nenašla")


def test_nove_prahy_sa_beru_az_pri_novej_relacii():
    """Meniť prahy uprostred relácie znamená merať pohyblivý cieľ.

    Okná z prvej polovice večera a z druhej by sa nedali porovnať a nikto
    by už spätne nezistil, ktoré bolo ktoré. Preto sa `_dev_params` čítajú
    v `start_heart_rate_monitor`, nie pri uložení v dialógu.
    """
    # Logika sedi v `_open_hr_session`; `start_heart_rate_monitor` je uz
    # len "otvor relaciu + nastartuj socket". Strazia sa OBE polovice
    # retaze, inak by sa delegovanie dalo ticho zrusit.
    assert "_open_hr_session" in _telo("app.py", "start_heart_rate_monitor")
    assert "_dev_params" in _telo("app.py", "_open_hr_session"), \
        "start_heart_rate_monitor musí brať prahy z vývojárskej vrstvy"


def test_dialog_ladenia_zamkne_polia_pocas_relacie():
    """Nie je to odporúčanie v texte — polia sa naozaj zamknú."""
    src = _zdroj("ui_dialogs.py")
    blok = src[src.index("class DevLayerDialog"):]
    blok = blok[:blok.index("\nclass ", 5)]
    assert "_hr_session_open" in blok, "dialóg sa musí pýtať, či relácia beží"
    assert 'state="disabled"' in blok, "polia sa počas relácie musia zamknúť"


def test_vynutena_hlaska_nejde_do_merania():
    """`dev_force_cue` obchádza automat zámerne.

    Vynútená hláška nie je meranie — keby sa zapísala do okien, spálila by
    refraktérnu zónu okolo skutočnej hlášky a znečistila by dáta práve pri
    ladení, teda vtedy, keď sa s ňou klikne najčastejšie.
    """
    telo = _telo("app.py", "dev_force_cue")
    assert "note_trigger" not in telo, "vynútená hláška sa nesmie zapísať do relácie"
    assert "cue_trigger" not in telo, "vynútená hláška nesmie ísť cez automat"


def test_pocitadla_sedia():
    t, h = spusti()
    natiahni(t, h)
    h.posun(5.0)
    t.tick(pause_s=3.0, now=h.t)
    s = t.snapshot()
    assert s["armed_count"] == 1 and s["delivered_count"] == 1


# --------------------------------------------------------------------------
# Hodinový strop (zadanie §2)
# --------------------------------------------------------------------------

def _doruc(t, h):
    """Prejde celý cyklus až po doručenie. Vráti udalosť alebo None."""
    for _ in range(400):
        ev = t.note_load(80.0, h.t)
        h.posun(1.0)
        if ev and ev["typ"] == trigger.E_ARMED:
            h.posun(5.0)
            return t.tick(pause_s=3.0, now=h.t)
    return None


def test_strop_zastavi_po_piatich_za_hodinu():
    """`min_gap_s` sám nestačí — 240 s odstup dovolí až 15 hlášok za hodinu.

    Simulácia namerala pri vypätom večeri 6,9 za hodinu, teda nad zadaním.
    """
    t, h = spusti()
    for i in range(5):
        ev = _doruc(t, h)
        assert ev is not None and ev["typ"] == trigger.E_DELIVER, f"{i + 1}. hláška"
    # šiesta sa už nesmie ani natiahnuť
    for _ in range(600):
        assert t.note_load(80.0, h.t) is None, "šiesta hláška prekročila strop"
        h.posun(1.0)
    assert t.delivered_count == 5


def test_strop_pusti_dalsiu_ked_najstarsia_vyprsi():
    """Okno je kĺzavé — po hodine od prvej hlášky sa miesto uvoľní."""
    t, h = spusti()
    for _ in range(5):
        assert _doruc(t, h) is not None
    prva = t._delivered_at[0]
    # presuň sa tesne za hodinu od prvej
    h.t = prva + trigger.HOUR_S + 1.0
    ev = _doruc(t, h)
    assert ev is not None and ev["typ"] == trigger.E_DELIVER
    assert t.delivered_count == 6


def test_strop_sa_neda_obist_restartom_relacie():
    """Vypnúť a zapnúť senzor nesmie strop vynulovať.

    „Päť za hodinu" je o hráčovi, nie o relácii — a reštart by hráč urobil
    presne vtedy, keď ho appka štve, čiže by dostal viac, nie menej.
    """
    t, h = spusti()
    for _ in range(5):
        assert _doruc(t, h) is not None
    t.close_session(now=h.t)
    t.open_session(silent_share=0.0)
    for _ in range(600):
        assert t.note_load(80.0, h.t) is None, "reštart relácie obišiel strop"
        h.posun(1.0)


def test_strop_sa_da_vypnut_nulou():
    """Vývojárska vrstva musí vedieť strop odstaviť — bez toho sa nedá
    odladiť nič, čo si vyžaduje veľa hlášok za krátky čas."""
    t, h = spusti(max_per_hour=0)
    for i in range(8):
        ev = _doruc(t, h)
        assert ev is not None, f"{i + 1}. hláška pri vypnutom strope"
    assert t.delivered_count == 8


def test_vycerpany_strop_nenatiahne_prstenec():
    """Natiahnuť a nedoručiť by znamenalo, že prstenec na ense svieti a nič
    nepríde. Pri vyčerpanom strope sa preto nenatiahne vôbec."""
    t, h = spusti()
    for _ in range(5):
        assert _doruc(t, h) is not None
    for _ in range(600):
        t.note_load(80.0, h.t)
        h.posun(1.0)
    assert t.is_armed is False
    assert t.armed_count == 5, "natiahlo sa viackrát, než sa doručilo"


# --------------------------------------------------------------------------
# Prstenec "natiahnute" na ense
# --------------------------------------------------------------------------

def test_prstenec_sa_zhadzuje_na_kazdej_ceste_von_z_natiahnutia():
    """Zabudnuta cesta = prstenec, ktory svieti navzdy.

    Je to najtichsie mozne zlyhanie: automat je v poriadku, meranie je v
    poriadku, len znacka klame. Nic v appke to nechyti - `CueTrigger` o UI
    nevie a UI nema ako zistit, ze sa niekde stratila udalost.

    Von zo stavu ARMED vedu styri cesty a kazda musi prstenec zhodit.
    """
    cesty = {
        "_on_cue_event": "dorucenie aj zrusenie",
        "_suspend_cue_trigger": "snooze a vypadok tepu",
        "_close_hr_session": "koniec relacie",
    }
    for meno, preco in cesty.items():
        telo = _telo("app.py", meno)
        assert "_set_enso_armed" in telo, f"{meno} ({preco}) nezhadzuje prstenec"

    # Stvrta cesta je vo widgete: ked sa prestane pocuvat, natiahnutie uz
    # neplati a `set_live(False)` ho musi zahodit samo. Keby to robila len
    # appka, po vypnuti a zapnuti pocuvania by prstenec svietil hned.
    telo = _telo_metody("ui_shell.py", "_EnsoButton", "set_live")
    assert "_armed" in telo, "set_live(False) musí zahodiť natiahnutie"


def test_ikona_hodiniek_zapina_a_nikdy_nevypina():
    """Zadanie §1.10. Predtým ikona len otvorila dialóg — nad vypnutým
    senzorom, takže hráč postupoval podľa panelu a appka nič neprijala.

    A hlavne: nesmie vypínať. Ikona, ktorá raz zapne a inokedy vypne, je
    pri jednom piktograme bez popisku nečitateľná.
    """
    telo = _telo("app.py", "open_watch_pairing")
    assert "_enable_hr_monitoring" in telo, "ikona hodiniek nezapína senzor"

    zapnutie = _telo("app.py", "_enable_hr_monitoring")
    assert "hr_monitoring_enabled = True" in zapnutie
    assert "= False" not in zapnutie, "cez ikonu sa nesmie dať vypnúť"
    assert "stop_heart_rate_monitor" not in zapnutie


def test_zapnutie_senzora_nezahodi_beziacu_relaciu():
    """`start_heart_rate_monitor` volá `hr_stats.reset_session()`. Zavolať ho
    na bežiacej relácii by zahodilo celý večer nazbieraných dát len preto,
    že hráč otvoril párovací panel."""
    telo = _telo("app.py", "_enable_hr_monitoring")
    assert "if self.hr_monitoring_enabled:" in telo and "return False" in telo, \
        "_enable_hr_monitoring sa musí vrátiť skôr, keď senzor už beží"


def test_enso_sleduje_temu_nie_stav():
    """PREMIUM REDIZAJN (2026-09, rozhodnutie "podla temy"): enso ma farbu
    podla TEMY (style.accent - zlate v Sumi, modre v Aizome), NIE podla stavu.
    Stav (pocuva/nie) nesie POHYB dychajuceho pasu + bodka v paneli
    (_StateDot). render_enso preto NESMIE siahat na stavove farby
    (success/danger) - tie patria bodke a pasu - a MUSI pouzit accent.
    """
    import ast
    strom = ast.parse(_zdroj("hud_paint.py"))
    telo = None
    for uzol in ast.walk(strom):
        if isinstance(uzol, ast.FunctionDef) and uzol.name == "render_enso":
            telo = ast.unparse(uzol)
            break
    assert telo is not None, "render_enso sa nenasla"
    najdene = {f"style.{u.attr}" for u in ast.walk(ast.parse(telo))
               if isinstance(u, ast.Attribute)
               and isinstance(u.value, ast.Name) and u.value.id == "style"}
    stavove = {"style.success", "style.danger"}
    assert not (najdene & stavove), (
        "render_enso siaha na STAVOVE farby (patria bodke/pasu): "
        + repr(sorted(najdene & stavove)))
    assert "style.accent" in najdene, "enso ma mat farbu TEMY (style.accent)"

# --------------------------------------------------------------------------
# Hlavička Dnes — stav namiesto čísel
# --------------------------------------------------------------------------

def test_pas_a_prstenec_citaju_ten_isty_priznak():
    """Jeden zdroj pravdy, nie dva.

    Prvá verzia mala prstenec z argumentu `_set_enso_armed` a text pásu si
    stav odvodzoval znova z `cue_trigger.is_armed`. V appke to náhodou
    sedelo, v ukážke už nie — pás hlásil „Počúvam", kým prstenec svietil.
    Rozídu sa vždy, len nie hneď.
    """
    zapis = _telo("app.py", "_set_enso_armed")
    assert "_cue_armed = armed" in zapis, \
        "_set_enso_armed musí byť jediné miesto, kde sa príznak zapisuje"
    assert "_refresh_kamae_state_text" in zapis, \
        "text pásu sa musí meniť spolu s prstencom"

    citanie = _telo("app.py", "_kamae_state_text")
    assert "_cue_armed" in citanie
    assert "is_armed" not in citanie, \
        "text pásu si stav nesmie odvodzovať znova z automatu"


def test_pas_ma_tri_stavy():
    """Zastavené / počúvam / natiahnuté. To tretie je celý zmysel zmeny:
    „natiahnuté" sa doteraz dalo prečítať len z prstenca, a ten má 68 px.

    „Zastavené" má odvtedy dve znenia — appka sa vie spustiť sama pri štarte
    hry, ale len pri zapnutom automatickom prepínaní profilov. Voľba medzi
    nimi býva v `_kamae_zastavene`, preto sa čítajú obe telá: stav musí
    existovať, nie nutne na jednom riadku.
    """
    telo = _telo("app.py", "_kamae_state_text") + _telo("app.py", "_kamae_zastavene")
    for kluc in ("kamae.stopped", "kamae.running", "kamae.armed"):
        assert kluc in telo, f"chýba stav {kluc}"


def test_veta_o_starte_pri_hre_plati_len_ked_je_zapnuty():
    """Appka sa sama spustí iba pri `auto_profile_enabled`.

    Jedna veta pre oba stavy by v tom druhom klamala — a komentár v `app.py`
    o štvrtom stave pásu hovorí presne to, čo taká veta narobí: hráč ide
    hrať s tým, že appka beží, a celý večer čaká na hlášku, ktorá nemá
    odkiaľ prísť.
    """
    telo = _telo("app.py", "_kamae_zastavene")
    assert "auto_profile_enabled" in telo
    assert "kamae.stopped_sub_auto" in telo and "kamae.stopped_sub" in telo
    # a ten sľub musí byť naozaj krytý kódom, ktorý štart robí
    assert "start_listening" in _telo("app.py", "_handle_game_found")


def test_pas_neukazuje_odpocet():
    """Merať hráčovi vlastný stav pred očami je presne to, čo appka nemá
    robiť. Veta hovorí, že sa čaká — číslo tam nepatrí."""
    telo = _telo("app.py", "_kamae_state_text")
    for zakazane in ("max_wait_s", "_armed_at", "time.time()", "waited"):
        assert zakazane not in telo, f"do textu pásu sa dostal odpočet: {zakazane}"


def test_riadok_o_poslednej_hlaske_sa_skryva():
    """Kým v relácii nič nebolo, riadok sa nezobrazí. Prázdny riadok s nulou
    by bol počítadlo a appka má ukazovať stav, nie skóre."""
    telo = _telo("app.py", "_refresh_last_cue")
    # Od prestavby stredu na Canvas nie je riadok widget — schová sa tak, že
    # `_dnes_lastcue_text` je prázdny (`_paint_dnes_canvas` ho potom nekreslí).
    assert "_dnes_lastcue_text" in telo, "bez hlášky sa riadok musí schovať"
    assert "if not cues" in telo or "not cues" in telo


def test_riadok_o_hlaske_sa_nepakuje_do_scrollable_frame():
    """`CTkScrollableFrame` je zložený widget — `dnes_body` je vnútorný rámec
    na plátne, ale do `wrap` sa zabalí jeho obal, takže `pack(before=...)`
    naň padne na TclError „isn't packed" — a padalo to ticho.

    Po prestavbe riadok sedí v strednom stĺpci a kotvu nepotrebuje. Test
    ostáva ako poistka, aby sa tá cesta nevrátila."""
    telo = _telo("app.py", "_refresh_last_cue")
    assert "before=self.dnes_body" not in telo
    assert "dnes_body" not in telo


# --------------------------------------------------------------------------
# Pozastavenie: čo smie zdvihnúť tep a čo nie
# --------------------------------------------------------------------------

def test_tep_nezdvihne_snooze():
    """Najhoršia chyba, akú našla revízia.

    `resume()` sa volá z `_apply_hr_bpm`, teda KAŽDÚ SEKUNDU. Kým nevedel,
    prečo bol automat pozastavený, zrušil „teraz nie" prvý úder srdca
    o sekundu neskôr. Odmerané: pri 30-minútovom snooze sa natiahlo 10-krát
    a do každého meracieho okna relácie sa zapísal nafúknutý `natiahnuti`.
    """
    t, h = spusti()
    t.suspend(trigger.A_SNOOZE, now=h.t)
    for _ in range(1800):                       # pol hodiny vzoriek tepu
        t.resume(h.t)                           # presne ako _apply_hr_bpm
        assert t.note_load(80.0, h.t) is None, "tep zdvihol snooze"
        h.posun(1.0)
    assert t.state == trigger.DORMANT
    assert t.armed_count == 0, f"natiahlo sa {t.armed_count}x počas snooze"


def test_vedome_zdvihnutie_snooze_funguje():
    t, h = spusti()
    t.suspend(trigger.A_SNOOZE, now=h.t)
    t.resume(h.t, force=True)
    assert t.state == trigger.IDLE
    natiahni(t, h)
    assert t.is_armed


def test_vypadok_tepu_zdvihne_prva_vzorka():
    """Toto `resume()` bez `force` zdvihnúť MUSÍ — je to presne ten prípad,
    na ktorý bol napísaný."""
    t, h = spusti()
    t.suspend(trigger.A_TEP_VYPADOL, now=h.t)
    t.resume(h.t)
    assert t.state == trigger.IDLE


def test_pozastavenie_nezmaze_odstup_medzi_hlaskami():
    """Druhá polovica tej istej chyby.

    `_cooldown_until` sa číta LEN v stave COOLDOWN. Keď šlo pozastavenie
    rovno na IDLE, jeden výpadok tepu zmazal štyri minúty odstupu — a ten
    odstup musí byť väčší než `measure.REFRACTORY_AFTER_S`, inak si dve
    hlášky navzájom zneplatnia meracie okná.
    """
    t, h = spusti()
    natiahni(t, h)
    h.posun(5.0)
    assert t.tick(pause_s=3.0, now=h.t)["typ"] == trigger.E_DELIVER
    assert t.state == trigger.COOLDOWN

    h.posun(10.0)                                # ešte hlboko v odstupe
    t.suspend(trigger.A_TEP_VYPADOL, now=h.t)
    t.resume(h.t)
    assert t.state == trigger.COOLDOWN, "odstup sa stratil pri výpadku tepu"

    # a po uplynutí odstupu sa normálne pokračuje
    h.posun(trigger.default_params()["min_gap_s"] + 1.0)
    t.tick(pause_s=0.0, now=h.t)
    assert t.state == trigger.IDLE


def test_appka_zdvihne_spustac_na_vsetkych_troch_cestach():
    """Von zo snooze vedú tri cesty a `start_listening` sa volá len
    podmienene — pri snooze spustenom v nepočúvajúcom stave by spúšťač
    ostal pozastavený navždy."""
    for meno in ("_cancel_snooze", "start_listening"):
        assert "_resume_cue_trigger" in _telo("app.py", meno), meno
    # vypršanie snooze je vnorená funkcia v _start_snooze
    assert "_resume_cue_trigger" in _telo("app.py", "_start_snooze")


def test_zmena_ip_uprostred_relacie_nezahodi_vecer():
    """`start_heart_rate_monitor` volá `hr_stats.reset_session()`, ktorý zmaže
    `cues` aj `_all`. Bez korektného zatvorenia by sa meracie okná už nemali
    z čoho zostaviť — a jediná cesta sem s otvorenou reláciou je zmena
    IP/portu uprostred večera."""
    assert "_open_hr_session" in _telo("app.py", "start_heart_rate_monitor")
    telo = _telo("app.py", "_open_hr_session")
    assert "_close_hr_session" in telo
    assert telo.index("_close_hr_session") < telo.index("reset_session"), \
        "zatvoriť sa musí PRED vynulovaním"


def test_tiche_rameno_sa_neda_vypnut_nedopatrenim():
    """Dialóg ladenia sa predvypĺňal zo `cue_trigger.silent_share`, čo je
    pred prvou reláciou 0.0. Kto ho otvoril a dal Uložiť bez toho, aby na to
    pole siahol, vypol kontrolné rameno na celý beh appky — ticho."""
    telo = _telo("app.py", "_silent_share_for_next_session")
    assert "if not podiel" in telo, "nula sa musí brať ako nedopatrenie"
    assert "silent_share_for" in telo


def test_riadok_o_hlaske_sa_obnovuje_aj_bez_tepu():
    """Všetky ostatné cesty k `_refresh_dnes_stats` visia na prichádzajúcom
    tepe. Po výpadku hodiniek by číslo „pred X min" zamrzlo a klamalo
    donekonečna."""
    assert "_refresh_last_cue" in _telo("app.py", "_tick_session")


def test_prestavba_okna_zosuladi_prstenec():
    """Prestavba (zmena jazyka) postaví ensō nanovo s `_armed=False`, kým
    `self._cue_armed` si stav drží ďalej. `set_live` to nezachráni — ten
    príznak zhadzuje len pri prechode True → False."""
    telo = _telo("app.py", "_apply_listening_visuals")
    assert "set_armed" in telo and "_cue_armed" in telo


# --------------------------------------------------------------------------
# Prestavba okna: značka do stredu, spínač do pásu
# --------------------------------------------------------------------------

def test_znacka_sa_stavia_na_stranke_nie_v_paneli():
    """Od 2.1 sedí v strede stránky. V paneli mala 68 px a prstenec
    „natiahnuté" pri tej veľkosti 1,4 px. Od prestavby stredu na Canvas je to
    `_EnsoHero` (kresba, nie widget) - aby enso plávalo na dojo bez boxu."""
    telo = _telo("app.py", "_build_dnes_page")
    assert "_EnsoHero" in telo, "značka sa musí stavať na stránke Dnes"
    assert "ENSO_SIZE" in telo

    import app as app_mod
    assert app_mod.DandurfApp.ENSO_SIZE >= 120


def test_stred_dnes_je_canvas_bez_boxu():
    """Enso + text musia plávať na dojo, nie sedieť na tmavom štvorci.

    CTk widget nevie byť priehľadný nad fotkou (`fg_color="transparent"` zdedí
    plnú farbu rodiča), takže akýkoľvek rámec/label nad dojom ostal ako box.
    Stred sa preto kreslí na `tk.Canvas` (`create_image` pre priehľadné enso,
    `create_text` pre text). Test stráži, že sa box nevráti."""
    telo = _telo("app.py", "_build_dnes_page")
    assert "tk.Canvas" in telo and "dnes_canvas" in telo, \
        "stred Dnes sa má kresliť na Canvas"
    # Do stredu sa už NESMIE vrátiť nepriehľadný rámec vo farbe pozadia -
    # to bol práve ten „štvorec".
    assert 'ctk.CTkFrame(stred, fg_color=pal["bg"])' not in telo, \
        "nepriehľadný box v strede je späť"
    # enso aj dojo sú OBRÁZKY na Canvase (create_image v layoute); v paint
    # slučke sa už len vymieňajú cez itemconfigure (bez blikania).
    layout = _telo("app.py", "_layout_dnes_items")
    assert "create_image" in layout, "enso aj dojo sú obrázky na Canvase"
    paint = _telo("app.py", "_paint_dnes_canvas")
    assert "itemconfigure" in paint, "snímky sa vymieňajú v mieste (proti blikaniu)"
    text = _telo("app.py", "_canvas_text")
    assert "create_text" in text, "text sa kreslí bez pozadia (create_text)"


def test_sidebar_uz_znacku_nestavia():
    src = _zdroj("ui_shell.py")
    i = src.index("class Sidebar")
    telo = src[i:src.index("\nclass ", i + 1)]
    assert "_EnsoButton(" not in telo, "Sidebar už značku nestavia"


def test_alias_sidebar_enso_ostava():
    """`guided_tour.py` aj oba harnessy hľadajú značku ako `app.sidebar.enso`
    a hľadajú ju MENOM — pri premenovaní by zlyhali TICHO (bublina sprievodcu
    by sa len prestala na niečo ukazovať)."""
    telo = _telo("app.py", "_build_ui")
    assert "self.sidebar.enso = self.enso" in telo


def test_spinac_je_v_pase_a_nie_na_znacke():
    """Značka prestala byť skryté tlačidlo. Ovládanie má vlastný viditeľný
    prvok a prepína UŽ LEN on — klik inam do pásu nerobí nič."""
    src = _zdroj("ui_kit.py")
    i = src.index("class KamaeBar")
    telo = src[i:src.index("\nclass ", i + 1)]
    assert "BTN_X" in telo and "_v_spinaci" in telo
    assert "def _clicked" in telo
    # klik mimo spínača nesmie prepínať
    j = telo.index("def _clicked")
    klik = telo[j:telo.index("def ", j + 10)]
    assert "_v_spinaci" in klik, "prepína aj klik mimo spínača"


def test_znacka_sa_dokresluje_na_pozadi():
    """Pri 150 px stojí celá sada 283 ms — a platilo by sa za ňu pri každom
    štarte aj pri každej zmene témy, proti rozpočtu ~673 ms na tému."""
    src = _zdroj("ui_shell.py")
    i = src.index("class _EnsoButton")
    telo = src[i:src.index("\nclass ", i + 1)]
    assert "_build_step" in telo and "_build_queue" in telo
    assert "BIG_PX" in telo, "veľká značka sa má kresliť s nižším prevzorkovaním"
    # oba reťazce sa musia rušiť
    j = telo.index("def destroy")
    znic = telo[j:telo.index("def ", j + 10)]
    assert "_cancel_build" in znic and "_after_id" in znic


def test_pozadie_ma_vsetko_v_jednom_module():
    """Kto mení fotku, mení `background.py` a nič iné. Fotku stredu stavia
    `_build_dojo_photo` (dojo/tlmená → PIL → ImageTk pre Canvas)."""
    telo = _telo("app.py", "_build_dojo_photo")
    assert "background.load" in telo
    assert ".jpg" not in telo and ".png" not in telo


def test_stav_sa_da_precitat_aj_mimo_stranky_dnes():
    """Značka aj dýchajúci pás sú deti stránky Dnes. Bez kontrolky v bočnom
    paneli by na Histórii, V hre, Zvuku a Nastaveniach nebolo v okne nič,
    čo povie, či appka počúva — to je strata schopnosti, nie zmena vzhľadu.
    """
    src = _zdroj("ui_shell.py")
    assert "class _StateDot" in src
    i = src.index("class Sidebar")
    telo = src[i:src.index("\nclass ", i + 1)]
    assert "_StateDot(" in telo, "kontrolka musí byť v bočnom paneli"

    # a musí sa prepínať spolu so stavom
    assert "state_dot" in _telo("app.py", "_apply_listening_visuals")


def test_kontrolka_nie_je_druhe_tlacidlo():
    """Spínač je jeden a je v dýchajúcom páse. Dve miesta, kde sa dá appka
    spustiť, je presne to, čomu sa prestavba vyhýbala."""
    telo = _telo_metody("ui_shell.py", "_StateDot", "__init__")
    assert "on_toggle" not in telo and "Button-1" not in telo


def test_stav_je_vyplneny_uz_pri_stavbe():
    """Text sa inak píše len z `_apply_listening_visuals` a `_set_enso_armed`
    a ani jedno pri stavbe okna nebeží — po čerstvom štarte stála značka nad
    prázdnym miestom. Vidno to v logs/gui_screenshots/01_dnes.png."""
    telo = _telo("app.py", "_build_dnes_page")
    assert "_refresh_dnes_state_text" in telo


def test_pozadie_sa_nekresli_1_5x_vacsie():
    """DPI: `winfo_*` na Canvase sú už FYZICKÉ pixely. Dojo sa preto stavia 1:1
    na (w, h) a enso aj fonty sa škálujú `get_widget_scaling` (logické × mierka
    = fyzické), aby pri 150 % neboli malé. Predtým sa fotka cez `CTkImage(size=)`
    kreslila 1,5× väčšia a orezala sa."""
    telo = _telo("app.py", "_paint_dnes_canvas")
    assert "get_widget_scaling" in telo
    assert "mierka" in telo


# --------------------------------------------------------------------------
# Prečo sa večer skončil nulou hlášok
#
# Prvý skutočný večer (The Finals, 36 min) skončil s nulou hlášok, hoci
# špička záťaže bola 87 pri prahu 55. Zo súhrnu relácie sa nedalo rozlíšiť,
# či bolo pravidlo „súvisle 90 s" pritvrdé, alebo či počítadlo súvislosti
# rozbíjali výpadky tepu. Tieto štyri čísla to rozlíšia bez ukladania krivky.
# --------------------------------------------------------------------------

def test_najdlhsi_usek_nad_prahom_sa_meria():
    """Keď sa nenatiahne, musí byť vidieť, ako blízko k tomu bolo."""
    t, h = spusti(stress_hold_s=90.0, dip_grace_s=5.0)
    for _ in range(40):                      # 40 s nad prahom, potom dole
        t.note_load(80.0, h.t)
        h.posun(1.0)
    for _ in range(20):                      # dlhý prepad úsek zruší
        t.note_load(10.0, h.t)
        h.posun(1.0)
    assert t.armed_count == 0
    assert 38.0 <= t.najdlhsi_nad_s <= 40.0, t.najdlhsi_nad_s
    assert t.behov_nad == 1
    assert t.zrusenych_prepadom == 1
    assert t.zrusenych_vypadkom == 0


def test_vypadok_tepu_sa_odlisi_od_prepadu():
    """Tá istá nula hlášok, úplne iná príčina — a iné riešenie."""
    t, h = spusti(stress_hold_s=90.0)
    for _ in range(30):
        t.note_load(80.0, h.t)
        h.posun(1.0)
    t.suspend(trigger.A_TEP_VYPADOL, h.t)
    assert t.zrusenych_vypadkom == 1
    assert t.zrusenych_prepadom == 0
    assert 28.0 <= t.najdlhsi_nad_s <= 30.0, t.najdlhsi_nad_s


def test_kratky_prepad_beh_nerozbije():
    """Tolerancia `dip_grace_s` nesmie počítať nový beh - inak by čísla
    tvrdili roztrieštenosť, ktorá sa nestala."""
    t, h = spusti(stress_hold_s=90.0, dip_grace_s=5.0)
    for _ in range(30):
        t.note_load(80.0, h.t)
        h.posun(1.0)
    for _ in range(3):                       # krátky prepad, v tolerancii
        t.note_load(10.0, h.t)
        h.posun(1.0)
    for _ in range(30):
        t.note_load(80.0, h.t)
        h.posun(1.0)
    assert t.behov_nad == 1, t.behov_nad
    assert t.zrusenych_prepadom == 0
    assert t.najdlhsi_nad_s >= 60.0, t.najdlhsi_nad_s


def test_pocitadla_sa_novou_relaciou_vynuluju():
    t, h = spusti(stress_hold_s=90.0)
    for _ in range(20):
        t.note_load(80.0, h.t)
        h.posun(1.0)
    assert t.behov_nad == 1
    t.open_session(silent_share=0.0)
    assert t.najdlhsi_nad_s == 0.0
    assert t.behov_nad == 0
    assert t.zrusenych_prepadom == 0
    assert t.zrusenych_vypadkom == 0


def test_uspesne_natiahnutie_najdlhsi_usek_zaznamena():
    """Aj keď hláška padne, dĺžka úseku sa musí zapísať - inak by vyšlo, že
    najdlhší úsek bol nula práve vo večeroch, keď appka fungovala."""
    t, h = spusti(stress_hold_s=90.0)
    natiahni(t, h, stress=80.0)
    assert t.armed_count == 1
    assert t.najdlhsi_nad_s >= 89.0, t.najdlhsi_nad_s


# --------------------------------------------------------------------------
# Veta „prečo som sa neozvala" musí trafiť správnu príčinu
#
# Tri veľmi rôzne veci vyzerajú z pohľadu hráča rovnako (ticho) a majú
# veľmi rôzne riešenia. Zámena by ho poslala opravovať niečo iné.
# --------------------------------------------------------------------------

def _preco(**summary):
    import ui_dialogs
    return ui_dialogs.SessionEndDialog._preco_ticho(summary)


def test_preco_ticho_stare_relacie_nic_netvrdia():
    """Relácia uložená pred touto zmenou tie čísla nemá - radšej mlčať."""
    assert _preco(duration_s=1800) == ""


def test_preco_ticho_telo_nebolo_hore():
    veta = _preco(above_runs=0, runs_cancelled_gap=0, runs_cancelled_dip=0)
    assert veta and "hranic" in veta.lower(), veta


def test_preco_ticho_bolo_hore_ale_kratko():
    veta = _preco(above_runs=6, runs_cancelled_gap=0, runs_cancelled_dip=6,
                  longest_above_s=42.0, stress_hold_s=90.0)
    assert "42" in veta and "90" in veta, veta


def test_preco_ticho_vypadky_maju_prednost():
    """Pri výpadkoch je „najdlhší úsek" nedôveryhodný - je rozsekaný dierami
    v dátach, nie fyziológiou. Preto sa pýtajú ako prvé."""
    veta = _preco(above_runs=9, runs_cancelled_gap=7, runs_cancelled_dip=2,
                  longest_above_s=11.0, stress_hold_s=90.0)
    assert "7" in veta, veta
    assert "11" not in veta, "pri vypadkoch sa dlzka useku tvrdit nema: " + veta


def test_kolova_hra_sa_natiahne_az_po_uprave():
    """Prečo sa `stress_hold_s` zmenil z 90 na 45 a tolerancia z 5 na 20.

    Vzorec z kolovej strieľačky: telo ide hore, umrieš, respawn, telo na
    chvíľu klesne, ďalšie kolo. Presne toto sa dialo vo večeri, ktorý
    skončil nulou hlášok — a presne toto musí appka po úprave zachytiť.
    """
    def odohraj(**params):
        t, h = spusti(**params)
        for _ in range(3):                   # tri kolá
            for _ in range(50):              # 50 s v boji
                if t.note_load(80.0, h.t):
                    return True
                h.posun(1.0)
            for _ in range(12):              # 12 s respawn a pokoj
                if t.note_load(20.0, h.t):
                    return True
                h.posun(1.0)
        return False

    # Od 19. 9. sa nepočíta SÚVISLÝ úsek, ale koľko času bolo nad prahom
    # za posledných `OKNO_NASOBOK * stress_hold_s` sekúnd. Tento vzorec sa
    # preto natiahne aj so starými parametrami — a to je celý zmysel zmeny:
    # večer, ktorý skončil nulou hlášok, mal 13 behov nad prahom a najdlhší
    # 44,1 s pri požadovaných 45,0. Chýbala jedna sekunda z jedného behu,
    # pritom času nad prahom bolo dosť.
    assert odohraj(stress_hold_s=90.0, dip_grace_s=5.0), (
        "kumulatívne okno musí zachytiť aj kolový vzorec s krátkou toleranciou")
    assert odohraj(stress_hold_s=45.0, dip_grace_s=20.0), (
        "s dnešnými parametrami tobôž")


def test_pokojny_vecer_sa_nenatiahne_ani_kumulativne():
    """Poistka k predošlému: kumulatívne okno nesmie naťahovať na čomkoľvek.

    Keby stačilo pár sekúnd nad prahom za dlhý čas, appka by sa ozývala aj
    pri pokojnom hraní — to je presne ten opak, ktorý ju robí otravnou.
    """
    t, h = spusti(stress_threshold=55.0, stress_hold_s=45.0)
    for _ in range(40):
        for _ in range(5):                   # 5 s krátky špic nad prahom
            assert not t.note_load(60.0, h.t)
            h.posun(1.0)
        for _ in range(55):                  # 55 s pokoja
            assert not t.note_load(20.0, h.t)
            h.posun(1.0)


def test_vypadok_spojenia_sa_nerata_ako_cas_nad_prahom():
    """Diera v dátach nie je záťaž.

    Bez stropu na krok by jeden 20-minútový výpadok spojenia pripísal do
    okna 20 minút „nad prahom" a appka by sa ozvala hneď po návrate — na
    základe času, ktorý nikto nemeral.
    """
    t, h = spusti(stress_threshold=55.0, stress_hold_s=45.0)
    assert not t.note_load(80.0, h.t)
    h.posun(1200.0)                          # 20 minút ticha zo senzora
    assert not t.note_load(80.0, h.t), "výpadok sa nesmie počítať ako držanie"


def test_zapnutie_pocuvania_otvori_novu_relaciu():
    """Bod 1 zadania z 18. 9.

    Relácia bola naviazaná na SENZOR, nie na počúvanie — otvárala sa jedine
    v `start_heart_rate_monitor`. Odkedy ju `stop_listening` korektne
    zatvára, po prvom cykle stop/štart nebola otvorená žiadna relácia a
    nemeralo sa nič. V CSV z 18. 9. to vidno ako štyri krátke relácie
    namiesto jednej — vznikli len reštartom appky.
    """
    telo = _telo("app.py", "start_listening")
    assert "_hr_session_open" in telo, "start_listening sa musí pýtať na reláciu"
    assert "_open_hr_session" in telo, "a otvoriť novú, keď žiadna nebeží"


def test_zapnutie_pocuvania_nerestartuje_siet_zbytocne():
    """Reštart socketu = krátke odpojenie hodiniek, a práve krátke výpadky
    rozbíjajú počítanie súvislosti (body 2 a 5). Keď príjem už beží, smie sa
    otvoriť len relácia."""
    telo = _telo("app.py", "start_listening")
    assert "heart_rate_monitor.running" in telo, \
        "start_listening sa musí spýtať, či príjem už beží"
    assert "prepoj=False" in telo, \
        "pri bežiacom príjme sa stav pripojenia nesmie zhodiť na 'connecting'"


# ---------------------------------------------------------------------------
# "Ako casto sa ozvem" - jeden ovladac, ktory hybe styrmi prahmi naraz
# ---------------------------------------------------------------------------

def test_citlivost_bezne_je_presne_vychodiskove_nastavenie():
    """"Bezne" nesmie byt vlastna tabulka cisel.

    Keby si viedlo svoje hodnoty, `default_params()` a "bezne" by sa raz
    rozisli a nikto by nevedel, ktore z nich su cisla zo zadania.
    """
    assert trigger.params_for(trigger.CITLIVOST_BEZNE) == trigger.default_params()


def test_citlivost_vracia_cely_slovnik_nie_len_rozdiel():
    """Prepnutie spat na "bezne" musi vratit VSETKY cisla.

    Keby `params_for` vracalo len rozdiel a volajuci ho `update`-oval do
    beziacich parametrov, po ceste "viac" -> "bezne" by v nich ostal
    stary prah 48 a volba by klamala.
    """
    for citlivost in trigger.CITLIVOSTI:
        assert set(trigger.params_for(citlivost)) == set(trigger.default_params())


def test_citlivost_naozaj_meni_frekvenciu_spravnym_smerom():
    menej = trigger.params_for(trigger.CITLIVOST_MENEJ)
    bezne = trigger.params_for(trigger.CITLIVOST_BEZNE)
    viac = trigger.params_for(trigger.CITLIVOST_VIAC)
    # nizsi prah a kratsie drzanie = ozve sa skor
    assert menej["stress_threshold"] > bezne["stress_threshold"] > viac["stress_threshold"]
    assert menej["stress_hold_s"] > bezne["stress_hold_s"] > viac["stress_hold_s"]
    # kratsi odstup a vyssi strop = ozve sa castejsie
    assert menej["min_gap_s"] > bezne["min_gap_s"] > viac["min_gap_s"]
    assert menej["max_per_hour"] < bezne["max_per_hour"] < viac["max_per_hour"]


def test_ziadna_citlivost_nepodlezie_refrakternu_zonu():
    """TVRDA HRANICA. Odstup musi ostat nad `measure.REFRACTORY_AFTER_S`.

    Keby klesol pod nu, druha hlaska by pristala do meracieho okna prvej,
    obe okna by sa zneplatnili a z vecera by neostalo nic na vyhodnotenie.
    Je to jediny dovod, preco "viac" nejde este vyssie.
    """
    import measure
    for citlivost in trigger.CITLIVOSTI:
        odstup = trigger.params_for(citlivost)["min_gap_s"]
        assert odstup > measure.REFRACTORY_AFTER_S, citlivost
    assert trigger.MIN_GAP_FLOOR_S > measure.REFRACTORY_AFTER_S


def test_nezmyselna_citlivost_padne_na_bezne():
    """Rozbity/stary settings.json nesmie appku nechat bez prahov."""
    for nezmysel in ("stredne", "", None, 3):
        assert trigger.params_for(nezmysel) == trigger.default_params()


def test_vyvojarska_vrstva_nepodlezie_refrakternu_zonu():
    """Tvrdá poistka platí aj pre vývojársku vrstvu.

    Je to nástroj na ladenie prahov, nie na obchádzanie hranice, ktorá
    chráni meranie. Preklep v políčku (24 namiesto 240) by nepokazil jeden
    večer, ale celý týždeň dát — a v dátach by to vyzeralo ako „hláška
    nezabrala", nie ako chyba nastavenia.
    """
    import inspect
    import app as app_mod
    telo = inspect.getsource(app_mod.DandurfApp.apply_dev_params)
    telo = telo[telo.index('"""', telo.index('"""') + 3):]
    assert "MIN_GAP_FLOOR_S" in telo, "vyvojarska vrstva poistku obchadza"


def test_vypnutie_vsetkych_hlasok_appku_umlci():
    """Kto vypol všetky štyri, chcel ticho — a dostal dychanie.

    `_dalsi_cue_slot` vracal ako zálohu `CUE_SLOT_INDEX` (dychový kruh),
    takže vypnutie všetkých prepínačov appku neumlčalo. Vypnutie je
    rozhodnutie hráča a automat ho obchádzať nesmie.
    """
    import inspect
    import app as app_mod
    telo = inspect.getsource(app_mod.DandurfApp._dalsi_cue_slot)
    telo = telo[telo.index('"""', telo.index('"""') + 3):]
    assert "return self.CUE_SLOT_INDEX" not in telo, "zaloha sa vratila"
    assert "return None" in telo

    doruc = inspect.getsource(app_mod.DandurfApp._fire_somatic_cue)
    assert "if index is None:" in doruc, "dorucenie None neoseruje"


# --------------------------------------------------------------------------
# Výpadok tepu zahodí nazbieraný čas nad prahom (B4)
# --------------------------------------------------------------------------

def test_vypadok_tepu_zahodi_nazbierany_cas_nad_prahom():
    """B4: `suspend` vynuloval `_above_since`, ale nechal `_nad_okno`.

    Poistka proti diere v `note_load` sa spustí len keď `_above_since` nie je
    None — a to práve suspend vynuloval. Bez vyčistenia okna by po výpadku
    12–40 s stará nazbieraná záťaž prežila a prvá vzorka po návrate by
    natiahla hlášku na čase, ktorý nikto nemeral.
    """
    t, h = spusti(stress_threshold=50.0, stress_hold_s=30.0)
    # ~29 s tesne pod hold=30 → ešte sa nenatiahne, ale okno je plné
    for _ in range(29):
        assert t.note_load(80.0, h.t) is None
        h.posun(1.0)

    t.suspend(trigger.A_TEP_VYPADOL, now=h.t)   # appka to volá pri výpadku
    h.posun(15.0)                               # 15 s bez tepu
    t.resume(now=h.t)                           # návrat tepu

    ev = t.note_load(80.0, h.t)                 # prvá vzorka po návrate
    assert ev is None, "natiahlo sa z času spred výpadku (B4)"


def test_po_vypadku_sa_da_natiahnut_odznova():
    """Poistka nesmie appku umlčať — po návrate sa dá natiahnuť normálne,
    len odznova (od nuly), nie zo starého času."""
    t, h = spusti(stress_threshold=50.0, stress_hold_s=30.0)
    for _ in range(10):
        t.note_load(80.0, h.t)
        h.posun(1.0)
    t.suspend(trigger.A_TEP_VYPADOL, now=h.t)
    h.posun(20.0)
    t.resume(now=h.t)
    ev = natiahni(t, h, stress=80.0)            # drž záťaž → musí sa natiahnuť
    assert ev is not None
