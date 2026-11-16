# -*- coding: utf-8 -*-
"""Every cue comes with an exhale - the visual side (overlay.py, settings).

  * grounding / jaw / release (trigger(0|1|2)) bring the breath ring along
    in an exhale-only mode: one exhale of the player's exhale length, full ->
    empty, the exhale caption, then the fade-out,
  * only when the breath visual is enabled and not in its own drag test; a
    running ring is restarted,
  * trigger() still returns the CATEGORY visual's own result (measurement,
    bug B17),
  * the breath cue on its own breathes exhale -> inhale -> exhale and ends
    breathed out; the drag test loops, exhale first,
  * test(index) shows only that slot's visual,
  * grounding moved to the left middle; an untouched old position (exactly
    the old default) is moved ONCE, a dragged one stays.

No Tk window is created: `LayeredSurface`, the monitor, the clock and the
drawing are fakes, the Tk `.after()` queue is driven by hand.
"""
import json
import types

import pytest

import display
import hud_paint
import i18n
import overlay
import settings_model as sm

OUT, IN = "VYDYCH", "NADYCH"


# --------------------------------------------------------------------------
# fakes
# --------------------------------------------------------------------------

class _Hodiny:
    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t


class _Fronta:
    """Tk `.after()` queue on a fake clock."""

    def __init__(self, hodiny):
        self.hodiny = hodiny
        self.ulohy = {}
        self._dalsie_id = 0

    def after(self, ms, fn):
        self._dalsie_id += 1
        self.ulohy[self._dalsie_id] = (self.hodiny.t + ms / 1000.0,
                                       self._dalsie_id, fn)
        return self._dalsie_id

    def cancel(self, job):
        self.ulohy.pop(job, None)

    def bez(self, sekundy):
        """Runs everything that is due within `sekundy` from now."""
        koniec = self.hodiny.t + sekundy
        while self.ulohy:
            kedy, job, fn = min(self.ulohy.values())
            if kedy > koniec + 1e-9:
                break
            del self.ulohy[job]
            self.hodiny.t = max(self.hodiny.t, kedy)
            fn()
        self.hodiny.t = koniec


class _Top:
    def __init__(self, fronta, x, y):
        self.fronta = fronta
        self.x, self.y = x, y

    def after(self, ms, fn):
        return self.fronta.after(ms, fn)

    def after_cancel(self, job):
        self.fronta.cancel(job)

    def winfo_x(self):
        return self.x

    def winfo_y(self):
        return self.y

    def winfo_children(self):
        return ()

    def bind(self, *_a, **_k):
        pass

    def configure(self, **_k):
        pass

    def geometry(self, *_a):
        pass


class _Plocha:
    """Stands in for `layer_window.LayeredSurface`."""

    def __init__(self, root):
        self.root = root
        self.top = None
        self.zavrete = False
        self.snimky = 0
        self.alfa = None
        self.rect = None
        self.click_through = True
        root.plochy.append(self)

    def create(self, x, y, w, h):
        if self.root.pokazit_vytvorenie:
            raise RuntimeError("okno sa nepostavilo")
        self.rect = (x, y, w, h)
        self.top = _Top(self.root.fronta, x, y)
        return "layered"

    def set_alpha(self, a):
        self.alfa = a

    def show(self):
        pass

    def draw(self, _image):
        self.snimky += 1

    def destroy(self):
        self.top = None
        self.zavrete = True

    def set_click_through(self, value):
        self.click_through = value


@pytest.fixture
def svet(monkeypatch):
    hodiny = _Hodiny()
    root = types.SimpleNamespace(fronta=_Fronta(hodiny), plochy=[],
                                 pokazit_vytvorenie=False)
    kresba = []

    def _breath(w, h, style, phase=0.0, inhale=True, cycle_text=None, ss=2):
        kresba.append(("breath", inhale, phase, cycle_text, hodiny.t))
        return object()

    def _visual(name, w, h, style, t=1.0, label=None, ss=2):
        kresba.append((name, None, t, label, hodiny.t))
        return object()

    monkeypatch.setattr(overlay, "LayeredSurface", _Plocha)
    monkeypatch.setattr(overlay, "time", hodiny)
    monkeypatch.setattr(hud_paint, "render_breath", _breath)
    monkeypatch.setattr(hud_paint, "render_visual", _visual)
    monkeypatch.setattr(display, "resolve_target",
                        lambda *_a, **_k: display.Monitor(0, 0, 1920, 1080))

    m = overlay.SomaticOverlayManager(root)
    m.set_labels({0: "G", 1: "J", 2: "R"}, breath_inhale=IN, breath_exhale=OUT)
    for i in range(4):
        m.configure(i, enabled=True)
    return types.SimpleNamespace(m=m, root=root, fronta=root.fronta,
                                 hodiny=hodiny, kresba=kresba)


def _kruh(svet):
    return svet.m._slots[svet.m.BREATH_INDEX]


def _dych(svet):
    """Breath ring frames as (inhale, phase, caption, time)."""
    return [k[1:] for k in svet.kresba if k[0] == "breath"]


def _behy(snimky):
    """[inhale, inhale, exhale ...] -> runs of the same phase, in order."""
    behy = []
    for inhale, *_ in snimky:
        if not behy or behy[-1] != inhale:
            behy.append(inhale)
    return behy


# --------------------------------------------------------------------------
# the companion exhale
# --------------------------------------------------------------------------

@pytest.mark.parametrize("index", [0, 1, 2])
def test_kategoria_prinesie_vydych(svet, index):
    assert svet.m.trigger(index) is True
    assert svet.m.is_active(index)
    assert svet.m.is_active(3), "k hlaske 0-2 patri aj kruh s vydychom"
    assert _kruh(svet)._breath_mode == _kruh(svet).BREATH_EXHALE
    # the ring is slot 3's own visual: its own position and size
    kruh = _kruh(svet).surface
    assert kruh.rect == (875, 714, 170, 170), "kruh nie je na mieste slotu 3"
    prvy = _dych(svet)[0]
    assert prvy[:3] == (False, 0.0, OUT), "kruh zacina plny, vo vydychu"


def test_vydych_respektuje_poziciu_a_farbu_kruhu(svet):
    svet.m.configure(3, pos=(30.0, 30.0), scale=1.5, color="#ff8800")
    svet.m.trigger(1)
    x, y, w, h = _kruh(svet).surface.rect
    assert (w, h) == (255, 255)
    assert (x + w / 2.0, y + h / 2.0) == pytest.approx((576, 324), abs=1)
    assert _kruh(svet).color == "#ff8800"


def test_dychova_hlaska_nema_druhy_kruh(svet):
    assert svet.m.trigger(3) is True
    assert len(svet.root.plochy) == 1, "dych sam sebe sprievod nerobi"
    assert not any(svet.m.is_active(i) for i in range(3))
    assert _kruh(svet)._breath_mode == _kruh(svet).BREATH_FULL


def test_bez_vydychu_ked_je_kruh_vypnuty(svet):
    svet.m.configure(3, enabled=False)
    assert svet.m.trigger(0) is True, "vypnuty kruh nemeni vysledok hlasky"
    assert not svet.m.is_active(3)
    assert len(svet.root.plochy) == 1
    assert not _dych(svet)


def test_vysledok_je_vlastny_vizual_kategorie(svet, monkeypatch):
    # category visual off -> no cue, so no exhale either
    svet.m.configure(2, enabled=False)
    assert svet.m.trigger(2) is False
    assert not svet.m.is_active(3), "bez hlasky ani vydych"

    # the ring fails -> the category's own result stays True
    def _zlyhaj():
        raise RuntimeError("kruh zlyhal")
    monkeypatch.setattr(_kruh(svet), "trigger_exhale", _zlyhaj)
    assert svet.m.trigger(0) is True
    assert svet.m.is_active(0)


def test_zlyhany_vizual_kategorie_nema_vydych(svet):
    svet.root.pokazit_vytvorenie = True
    assert svet.m.trigger(1) is False
    svet.root.pokazit_vytvorenie = False
    assert not svet.m.is_active(3), "nedoruceny vizual nema mat sprievod"


def test_neplatny_index(svet):
    for index in (-1, 4, 99):
        assert svet.m.trigger(index) is False
    assert not svet.root.plochy


def test_vydych_ma_jednu_fazu_s_popisom_vydychu(svet):
    svet.m.set_breath_seconds(4.0, 8.0)
    kruh = _kruh(svet)
    svet.m.trigger(0)
    assert kruh.breath_phases() == ((False, 8.0),)
    assert kruh.breath_duration() == 8.0
    start = svet.hodiny.t
    svet.fronta.bez(20.0)

    snimky = _dych(svet)
    assert _behy(snimky) == [False], "vydych bez nadychu"
    assert {s[2] for s in snimky} == {OUT}
    fazy = [s[1] for s in snimky]
    assert fazy == sorted(fazy), "kruh ide len od plneho k prazdnemu"
    assert fazy[0] == 0.0 and fazy[-1] == 1.0, "konci presne vydychnuty"
    # one exhale after the fade-in: the last frame at FADE + 8 s
    fade = kruh.FADE_MS / 1000.0
    assert snimky[-1][3] - start == pytest.approx(fade + 8.0, abs=0.1)
    assert not kruh.is_active, "po vydychu zmizne"
    assert svet.root.plochy[-1].zavrete


def test_vydych_trva_dlzku_vydychu_hraca(svet):
    """Default 6 s; on screen fade-in + 6 s + fade-out, then gone."""
    kruh = _kruh(svet)
    start = svet.hodiny.t
    svet.m.trigger(2)
    while kruh.is_active and svet.hodiny.t - start < 30.0:
        svet.fronta.bez(0.02)
    fade = (kruh.FADE_MS // kruh.TICK_MS) * kruh.TICK_MS / 1000.0
    assert svet.hodiny.t - start == pytest.approx(fade + 6.0 + fade, abs=0.08)


def test_kruh_kategorie_zmizne_skor_ako_vydych(svet):
    svet.m.trigger(0)
    svet.fronta.bez(4.0)
    assert not svet.m.is_active(0), "kategoria drzi svoje 3 s"
    assert svet.m.is_active(3), "vydych dobieha"


def test_beziaci_kruh_sa_restartuje(svet):
    kruh = _kruh(svet)
    svet.m.trigger(3)
    svet.fronta.bez(5.0)
    stara = kruh.surface
    svet.kresba.clear()
    svet.m.trigger(1)
    assert stara.zavrete and kruh.surface is not stara
    assert kruh._breath_mode == kruh.BREATH_EXHALE
    svet.fronta.bez(30.0)
    snimky = _dych(svet)
    assert _behy(snimky) == [False] and snimky[0][1] == 0.0
    assert not kruh.is_active


def test_druhy_vydych_restartuje_prvy(svet):
    kruh = _kruh(svet)
    svet.m.trigger(0)
    svet.fronta.bez(4.0)
    stara = kruh.surface
    svet.kresba.clear()
    svet.m.trigger(2)
    assert stara.zavrete and kruh.surface is not stara
    assert _dych(svet)[0][:2] == (False, 0.0), "novy vydych zacina od plneho kruhu"
    # the first exhale would have ended at ~6.5 s - the new one runs a full 6 s
    svet.fronta.bez(5.5)
    assert kruh.is_active


def test_stop_all_zastavi_aj_vydych(svet):
    svet.m.trigger(0)
    svet.fronta.bez(1.0)
    svet.m.stop_all()
    assert not any(svet.m.is_active(i) for i in range(4))
    pocet = len(svet.kresba)
    svet.fronta.bez(10.0)
    assert len(svet.kresba) == pocet, "po stop_all sa uz nic nekresli"


def test_vypnutie_kruhu_zastavi_vydych(svet):
    svet.m.trigger(1)
    svet.m.configure(3, enabled=False)
    assert not svet.m.is_active(3)
    assert svet.m.is_active(1)


def test_zlyhany_vydych_neostane_visiet(svet):
    """The ring fails AFTER its window was built (here the fade's start).
    `play()` cleans up only a failed build or first frame - an open window
    with no animation would count as a running visual for good and
    `_cue_can_fire` would hold back every later cue of the session."""
    kruh = _kruh(svet)

    def _zlyhaj(*_a, **_k):
        raise RuntimeError("after() zlyhal")
    kruh._fade = _zlyhaj                      # only this ring's instance
    assert svet.m.trigger(0) is True, "vysledok je vizual kategorie"
    assert not svet.m.is_active(3), "polovicny kruh nesmie ostat otvoreny"
    assert all(p.zavrete for p in svet.root.plochy if p is not svet.m._slots[0].surface)
    svet.fronta.bez(30.0)
    assert not any(svet.m.is_active(i) for i in range(4)), "dalsia hlaska moze prist"

    # once the ring works again, the next cue brings it as usual
    del kruh._fade
    assert svet.m.trigger(1) is True
    assert svet.m.is_active(3)


def test_nic_nezostane_po_rychlych_hlaskach(svet):
    """Restart while the ring fades out, cue after cue, stop_all, a theme
    and a monitor change mid-exhale: in the end no window is open and no
    `.after()` job is left in the queue."""
    kruh = _kruh(svet)
    svet.m.trigger(0)
    fade = kruh.FADE_MS / 1000.0
    svet.fronta.bez(fade + 6.0 + 0.1)          # the ring is fading out now
    assert kruh.is_active
    svet.kresba.clear()
    svet.m.trigger(1)                          # another cue mid-fade
    assert _dych(svet)[0][:2] == (False, 0.0), "zacina znova od plneho kruhu"
    svet.m.set_palette({"accent": "#123456", "danger": "#ff0000"})
    svet.m.set_monitor_target("primary")
    svet.fronta.bez(2.0)
    assert kruh.is_active, "zmena temy ani monitora vydych nezastavi"
    for index in (2, 0, 1, 2, 3, 0):          # clicks on Test in a row
        svet.m.trigger(index)
        svet.fronta.bez(0.05)
    svet.fronta.bez(40.0)
    assert not any(svet.m.is_active(i) for i in range(4))
    assert all(p.zavrete for p in svet.root.plochy), "otvorene okno ostalo"
    assert not svet.fronta.ulohy, "after() uloha ostala"

    svet.m.trigger(2)
    svet.fronta.bez(1.0)
    svet.m.stop_all()
    assert all(p.zavrete for p in svet.root.plochy)
    svet.fronta.bez(10.0)
    assert not svet.fronta.ulohy


# --------------------------------------------------------------------------
# the breath cue on its own and the drag test
# --------------------------------------------------------------------------

def test_dych_zacina_aj_konci_vydychom(svet):
    kruh = _kruh(svet)
    assert kruh.breath_phases() == ((False, 6.0), (True, 4.0), (False, 6.0))
    assert kruh.breath_duration() == 16.0
    start = svet.hodiny.t
    svet.m.trigger(3)
    svet.fronta.bez(40.0)

    snimky = _dych(svet)
    assert _behy(snimky) == [False, True, False], "vydych -> nadych -> vydych"
    for inhale, _faza, popis, _t in snimky:
        assert popis == (IN if inhale else OUT), "popis ide podla fazy"
    assert snimky[0][1] == 0.0 and snimky[-1][:2] == (False, 1.0)
    fade = kruh.FADE_MS / 1000.0
    assert snimky[-1][3] - start == pytest.approx(fade + 16.0, abs=0.1)
    assert not kruh.is_active


def test_dych_podla_dlzok_hraca(svet):
    svet.m.set_breath_seconds(3.0, 7.5)
    kruh = _kruh(svet)
    kruh._breath_mode = kruh.BREATH_FULL
    assert kruh.breath_phases() == ((False, 7.5), (True, 3.0), (False, 7.5))
    assert kruh.breath_duration() == 18.0
    assert kruh.breath_state(0.0) == (False, 0.0)
    assert kruh.breath_state(7.5) == (True, 0.0)
    assert kruh.breath_state(9.0) == (True, 0.5)
    assert kruh.breath_state(10.5) == (False, 0.0)
    assert kruh.breath_state(18.0) == (False, 1.0)
    assert kruh.breath_state(99.0) == (False, 1.0), "po konci ostava vydychnuty"


def test_test_rezim_bez_vydychu(svet):
    for index in (0, 1, 2):
        assert svet.m.test(index) is True
        assert not svet.m.is_active(3), "test ukaze len svoj vizual"
    assert svet.m.test(2) is False


def test_test_kruhu_dycha_dokola_od_vydychu(svet):
    kruh = _kruh(svet)
    assert svet.m.test(3) is True
    svet.fronta.bez(60.0)
    assert kruh.is_active, "test sam neskonci"
    snimky = _dych(svet)
    behy = _behy(snimky)
    assert behy[0] is False and len(behy) >= 6
    assert all(a != b for a, b in zip(behy, behy[1:]))
    assert kruh.breath_state(6.0) == (True, 0.0)
    assert kruh.breath_state(10.0) == (False, 0.0)
    svet.m.stop_test(3)
    assert not kruh.is_active


def test_hlaska_neprerusi_test_kruhu(svet):
    kruh = _kruh(svet)
    svet.m.test(3)
    plocha = kruh.surface
    assert svet.m.trigger(0) is True
    assert kruh.surface is plocha, "hrac prave kruh umiestnuje"
    assert kruh._test_mode and kruh._breath_mode == kruh.BREATH_FULL


def test_hlaska_v_teste_kategorie_nema_vydych(svet):
    svet.m.test(1)
    svet.m.trigger(1)
    assert not svet.m.is_active(3)


def test_skutocne_kreslenie_vydychu():
    """One real frame (PIL) at the start, middle and end of the exhale."""
    kruh = overlay._SlotOverlay(None, "breath", (170, 170),
                                types.SimpleNamespace(
                                    style=hud_paint.Style({"accent": "#00d2ff",
                                                           "danger": "#ff5c73"}),
                                    breath_text=lambda inhale: IN if inhale else OUT))
    kruh.w = kruh.h = 170
    obrazky = []
    kruh.surface = types.SimpleNamespace(draw=obrazky.append)
    kruh._breath_mode = kruh.BREATH_EXHALE
    for t in (0.0, 3.0, 6.0):
        kruh._render(t)
    assert len(obrazky) == 3
    for obr in obrazky:
        assert obr.size == (170, 170) and obr.mode == "RGBA"
        assert obr.getchannel("A").getbbox() is not None


# --------------------------------------------------------------------------
# grounding position
# --------------------------------------------------------------------------

def test_predvolene_pozicie():
    assert sm.OVERLAY_DEFAULT_POS == {0: (14.0, 50.0), 1: (50.0, 12.0),
                                      2: (86.0, 50.0), 3: (50.0, 74.0)}
    # left middle mirrors release
    assert sm.OVERLAY_DEFAULT_POS[0][0] == 100.0 - sm.OVERLAY_DEFAULT_POS[2][0]
    assert sm.OVERLAY_DEFAULT_POS[0][1] == sm.OVERLAY_DEFAULT_POS[2][1]
    cfg = sm.default_overlay_configs()[0]
    assert (cfg["pos_x"], cfg["pos_y"]) == (14.0, 50.0)
    assert sm.normalize_overlay_config({}, 0)["pos_x"] == 14.0
    m = overlay.SomaticOverlayManager(None)
    assert m._slots[0].pos == (14.0, 50.0)


def _cfgs(pos0=(50.0, 88.0)):
    out = sm.default_overlay_configs()
    out[0].update(pos_x=pos0[0], pos_y=pos0[1], scale=1.3, color="#112233",
                  enabled=False)
    return out


def test_presun_len_presne_starej_predvolby():
    cfgs = _cfgs()
    assert sm.move_old_grounding_position(cfgs) is True
    assert (cfgs[0]["pos_x"], cfgs[0]["pos_y"]) == (14.0, 50.0)
    assert (cfgs[0]["scale"], cfgs[0]["color"], cfgs[0]["enabled"]) == \
        (1.3, "#112233", False), "presuva sa len pozicia"
    assert cfgs[1:] == sm.default_overlay_configs()[1:]

    for posunuta in ((50.0, 87.9), (50.1, 88.0), (14.0, 50.0), (30.0, 70.0)):
        cfgs = _cfgs(posunuta)
        assert sm.move_old_grounding_position(cfgs) is False
        assert (cfgs[0]["pos_x"], cfgs[0]["pos_y"]) == posunuta

    # another slot at the old grounding spot is not grounding
    cfgs = sm.default_overlay_configs()
    cfgs[3].update(pos_x=50.0, pos_y=88.0)
    sm.move_old_grounding_position(cfgs)
    assert (cfgs[3]["pos_x"], cfgs[3]["pos_y"]) == (50.0, 88.0)

    for zle in ([], None, [{}], [{"pos_x": "x", "pos_y": 1}]):
        assert sm.move_old_grounding_position(zle) is False


@pytest.fixture
def nastavenia(tmp_path, monkeypatch):
    import app as app_mod
    import app_prefs
    cesta = str(tmp_path / "dandurf_settings.json")
    monkeypatch.setattr(app_prefs, "SETTINGS_PATH", cesta)
    povodny = i18n._lang["code"]

    def zapis(obsah):
        with open(cesta, "w", encoding="utf-8") as fh:
            json.dump(obsah, fh)

    def nacitaj():
        return app_mod.DandurfApp.load_settings(types.SimpleNamespace())

    def uloz(data):
        a = types.SimpleNamespace(
            _ready=True, slots=[object()], _sync_active_profile_slots=lambda: None,
            profiles=data["profiles"], active_profile_name=data["active_profile"],
            saved_voice_id=data["voice_id"], rate_value=data["rate"],
            volume_value=data["volume"], balance_value=data["balance"],
            engine_pref=data["engine_pref"], edge_voice_id=data["edge_voice"],
            theme_key=data["theme"], world=data["world"], cue_style=data["cue_style"],
            lang=data["lang"], start_minimized=data["start_minimized"],
            tray_close_explained=data["tray_close_explained"],
            auto_profile_enabled=data["auto_profile_enabled"],
            overlay_configs=data["overlay_configs"], hr_ip=data["hr_ip"],
            hr_port=data["hr_port"], hr_monitoring_enabled=data["hr_monitoring_enabled"],
            zanshin_graduated=data["zanshin_graduated"],
            zanshin_graduated_at=data["zanshin_graduated_at"],
            snooze_hotkey=data["snooze_hotkey"],
            background_opacity=data["background_opacity"],
            monitor_target=data["monitor_target"], hud_config=data["hud_config"],
            dashboard_stats=data["dashboard_stats"],
            breath_inhale_s=data["breath_inhale_s"],
            breath_exhale_s=data["breath_exhale_s"],
            old_installer_warned=data["old_installer_warned"],
            log=lambda _m: None)
        app_mod.DandurfApp.save_settings(a)

    def citaj():
        with open(cesta, encoding="utf-8") as fh:
            return json.load(fh)

    yield types.SimpleNamespace(zapis=zapis, nacitaj=nacitaj, uloz=uloz,
                                citaj=citaj)
    i18n.set_lang(povodny)


def _subor(pos0, **navyse):
    cfgs = sm.default_overlay_configs()
    cfgs[0].update(pos_x=pos0[0], pos_y=pos0[1])
    return dict({"lang": "sk", "theme": "zen", "overlay_configs": cfgs,
                 "visuals_repaired": True}, **navyse)


def test_nacitanie_presunie_nedotknute_ukotvenie_raz(nastavenia):
    nastavenia.zapis(_subor((50.0, 88.0)))
    d = nastavenia.nacitaj()
    assert (d["overlay_configs"][0]["pos_x"], d["overlay_configs"][0]["pos_y"]) == (14.0, 50.0)
    for i in (1, 2, 3):
        assert (d["overlay_configs"][i]["pos_x"], d["overlay_configs"][i]["pos_y"]) == \
            sm.OVERLAY_DEFAULT_POS[i]

    # saved -> the flag is in the file, the new position too
    nastavenia.uloz(d)
    ulozene = nastavenia.citaj()
    assert ulozene["grounding_moved"] is True
    assert (ulozene["overlay_configs"][0]["pos_x"],
            ulozene["overlay_configs"][0]["pos_y"]) == (14.0, 50.0)

    # the player puts it back at the bottom centre - it stays there
    ulozene["overlay_configs"][0].update(pos_x=50.0, pos_y=88.0)
    nastavenia.zapis(ulozene)
    d = nastavenia.nacitaj()
    assert (d["overlay_configs"][0]["pos_x"], d["overlay_configs"][0]["pos_y"]) == (50.0, 88.0)


def test_nacitanie_necha_posunute_ukotvenie(nastavenia):
    nastavenia.zapis(_subor((22.5, 61.0)))
    d = nastavenia.nacitaj()
    assert (d["overlay_configs"][0]["pos_x"], d["overlay_configs"][0]["pos_y"]) == (22.5, 61.0)


def test_nacitanie_s_priznakom_nepresuva(nastavenia):
    nastavenia.zapis(_subor((50.0, 88.0), grounding_moved=True))
    d = nastavenia.nacitaj()
    assert (d["overlay_configs"][0]["pos_x"], d["overlay_configs"][0]["pos_y"]) == (50.0, 88.0)


def test_cele_cisla_v_subore_sa_tiez_rataju(nastavenia):
    """A hand-edited file with 50 / 88 is the same position as 50.0 / 88.0."""
    nastavenia.zapis(_subor((50, 88)))
    d = nastavenia.nacitaj()
    assert (d["overlay_configs"][0]["pos_x"], d["overlay_configs"][0]["pos_y"]) == (14.0, 50.0)


def test_nova_instalacia_ma_nove_ukotvenie(nastavenia):
    d = nastavenia.nacitaj()           # no file yet
    assert (d["overlay_configs"][0]["pos_x"], d["overlay_configs"][0]["pos_y"]) == (14.0, 50.0)


def test_nahlad_v_uvode_ukazuje_ukotvenie_kde_naozaj_je():
    """Onboarding step 2 shows the player WHERE the picture sits. It drew
    grounding at a fixed bottom centre, the old default - after the move it
    has to follow `OVERLAY_DEFAULT_POS`."""
    import inspect

    import ui_dialogs
    W, H, w, h = 520, 292, 150, 100
    gx, gy = ui_dialogs.stred_v_nahlade(W, H, w, h, sm.OVERLAY_DEFAULT_POS[0])
    assert gx < W / 3, "ukotvenie je vlavo"
    assert gy == pytest.approx(H / 2, abs=1), "v strede vysky"
    assert gx - w / 2 >= 0 and gy + h / 2 <= H, "cely obrazok je v nahlade"
    # the clamp works on every side, the middle stays as it is
    assert ui_dialogs.stred_v_nahlade(W, H, w, h, (0.0, 0.0)) == (8 + 75, 8 + 50)
    assert ui_dialogs.stred_v_nahlade(W, H, w, h, (100.0, 100.0)) == (W - 8 - 75, H - 8 - 50)
    assert ui_dialogs.stred_v_nahlade(W, H, w, h, (50.0, 50.0)) == (260, 146)

    zdroj = inspect.getsource(ui_dialogs.OnboardingWizard._build_screen_preview)
    assert "stred_v_nahlade(" in zdroj and "OVERLAY_DEFAULT_POS[0]" in zdroj
    assert "H - 20" not in zdroj, "pevne miesto dole v strede"
