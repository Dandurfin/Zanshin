# -*- coding: utf-8 -*-
"""Meno stranky "V hre" v textoch podla sveta (0.2.2 davka 4b).

Vo svete Praca sa stranka v bocnom paneli vola "Obrazovka" (davka 4), no
dennik, prazdna Historia, uvod, okno parovania a vysvetlivka "Cas nad
hranicou" ju dalej menovali "V hre". Kazdy taky text ma teraz `{page}` a
appka don dosadi meno, ake ma stranka v aktualnom svete.

Vsetko na atrapach - bez okna, data vymyslene.
"""
import ast
import re
import types

import app as app_mod
import app_spolocne
import i18n
import theme as theme_mod
import ui_dialogs
from _zdroj_appky import zdroj_metody, zdroj_suboru

import test_022b_instance_port as port

S = i18n.STRINGS
D = app_mod.DandurfApp

# Texty, ktore posielaju na stranku "V hre" (hodinky, port, obrazky).
KLUCE_SO_STRANKOU = (
    "log.hr_port_busy", "log.hr_overlay_disabled", "log.vizualy_napravene",
    "ob.step2.body", "ob.step3.later_note", "history.empty", "metric.over.more",
    "hr.pair_status_gave_up", "kamae.port_busy_sub",
)


def _vzor_stranky(jazyk):
    """Meno stranky z Hry v uvodzovkach alebo pred sipkou (= odkaz na stranku,
    nie pridavne meno ako "In-game pictures" / 「ゲーム中の画像」)."""
    mena = {S["nav.vhre_short"][jazyk], S["nav.nastavenia_tabs.vhre"][jazyk]}
    kusy = []
    for meno in mena:
        m = re.escape(meno)
        kusy.append(r"[„“\"«「]\s*" + m + r"\s*[“”\"»」]")
        kusy.append(r"(?<![\w-])" + m + r"\s*[“”\"»」]?\s*→")
    return re.compile("|".join(kusy))


def test_texty_so_strankou_maju_page_vo_vsetkych_jazykoch():
    for kluc in KLUCE_SO_STRANKOU:
        for jazyk in i18n.LANGUAGES:
            assert "{page}" in S[kluc][jazyk], (kluc, jazyk)


def test_ziadny_text_nemenuje_stranku_v_hre_natvrdo():
    zle = []
    for jazyk in i18n.LANGUAGES:
        vzor = _vzor_stranky(jazyk)
        for kluc, zaznam in S.items():
            if kluc.startswith("nav."):
                continue
            if vzor.search(zaznam.get(jazyk, "")):
                zle.append((kluc, jazyk))
    assert not zle, zle


def test_v_praci_texty_menuju_obrazovku():
    for jazyk in i18n.LANGUAGES:
        praca = i18n.tr_lang(jazyk, "nav.vhre_work_short")
        hra = i18n.tr_lang(jazyk, "nav.vhre_short")
        for kluc in KLUCE_SO_STRANKOU:
            text = i18n.tr_lang(jazyk, kluc, page=praca, port=4455, card="X")
            assert praca in text, (kluc, jazyk)
            if kluc != "log.vizualy_napravene":     # "Obrazky v hre" je panel
                assert hra not in text, (kluc, jazyk, text)


def test_stranka_vhre_podla_sveta():
    for svet, kluc in (("play", "nav.vhre_short"), ("work", "nav.vhre_work_short")):
        a = types.SimpleNamespace(world=svet)
        a._nazov_vhre = types.MethodType(D._nazov_vhre, a)
        assert app_spolocne.stranka_vhre(a) == i18n.tr(kluc)
    # atrapa bez `_nazov_vhre` a pokazena metoda -> meno z Hry, ziadna vynimka
    assert app_spolocne.stranka_vhre(types.SimpleNamespace()) == i18n.tr("nav.vhre_short")

    def zle():
        raise RuntimeError("nie")
    assert (app_spolocne.stranka_vhre(types.SimpleNamespace(_nazov_vhre=zle))
            == i18n.tr("nav.vhre_short"))


def test_uvod_berie_svet_zo_zvolenej_temy():
    praca = theme_mod.WORLD_THEME["work"]
    hra = theme_mod.WORLD_THEME["play"]
    assert ui_dialogs._stranka_vhre(tema=praca) == i18n.tr("nav.vhre_work_short")
    assert ui_dialogs._stranka_vhre(tema=hra) == i18n.tr("nav.vhre_short")
    assert ui_dialogs._stranka_vhre() == i18n.tr("nav.vhre_short")
    strom = ast.parse(zdroj_suboru("ui_dialogs.py"))
    uvod = next(u for u in strom.body
                if isinstance(u, ast.ClassDef) and u.name == "OnboardingWizard")
    for krok in ("_step2", "_step3"):
        f = next(x for x in uvod.body if isinstance(x, ast.FunctionDef) and x.name == krok)
        assert "_stranka_vhre(tema=self.choice)" in ast.unparse(f), krok


def test_obsadeny_port_v_praci_posle_na_obrazovku():
    a = port._atrapa(_hr_bind_retries=3, world="work")
    a._nazov_vhre = types.MethodType(D._nazov_vhre, a)
    port._stav(a, "busy", 4455)
    assert a.denn[-1] == i18n.tr("log.hr_port_busy", port=4455,
                                 page=i18n.tr("nav.vhre_work_short"))


def test_okno_parovania_v_praci_posle_na_obrazovku():
    a = types.SimpleNamespace(world="work", hr_monitoring_enabled=False,
                              _hr_state="busy_gave_up", hr_port=4455,
                              _hr_last_bpm=None)
    a._nazov_vhre = types.MethodType(D._nazov_vhre, a)
    druh, text = ui_dialogs.stav_parovania(a)
    assert druh == "chyba"
    assert text == i18n.tr("hr.pair_status_gave_up", port=4455,
                           page=i18n.tr("nav.vhre_work_short"))


def test_volajuci_dosadzaju_meno_stranky():
    for metoda, kluc in (("_apply_hr_status", "log.hr_port_busy"),
                         ("_warn_hr_overlay_disabled_once", "log.hr_overlay_disabled"),
                         ("_refresh_history_page", "history.empty")):
        kod = zdroj_metody(metoda)
        assert 'tr("%s"' % kluc in kod, metoda
        assert "page=stranka_vhre(self)" in kod, metoda
    assert 'tr("log.vizualy_napravene", page=stranka_vhre(self))' in zdroj_metody("__init__")
    for metoda in ("_metric_info", "_rebuild_dashboard_stats_grid"):
        assert ".more\", page=stranka_vhre(self))" in zdroj_metody(metoda), metoda


# --------------------------------------------------------------------------
# Prepnutie sveta prepise aj texty postavene raz
# --------------------------------------------------------------------------

class _Stitok:
    def __init__(self, zije=True):
        self.text, self.zije = None, zije

    def winfo_exists(self):
        return self.zije

    def configure(self, text=None, **_k):
        self.text = text


def test_vysvetlivka_v_historii_sa_po_prepnuti_sveta_prepise():
    a = types.SimpleNamespace(world="play")
    a._nazov_vhre = types.MethodType(D._nazov_vhre, a)
    zivy, mrtvy, iny = _Stitok(), _Stitok(zije=False), _Stitok()
    app_spolocne.zapamataj_text_stranky(a, zivy, "metric.over.more")
    app_spolocne.zapamataj_text_stranky(a, mrtvy, "metric.over.more")
    # text bez {page} si appka nepamata (zoznam by rastol zbytocne)
    app_spolocne.zapamataj_text_stranky(a, iny, "metric.hrr.more")
    app_spolocne.zapamataj_text_stranky(a, None, "metric.over.more")
    assert len(a._texty_so_strankou) == 2
    a.world = "work"
    app_spolocne.obnov_texty_stranky(a)
    assert zivy.text == i18n.tr("metric.over.more", page=i18n.tr("nav.vhre_work_short"))
    assert iny.text is None
    assert a._texty_so_strankou == [(zivy, "metric.over.more")], "mrtvy stitok sa zahodi"


def test_prepnutie_sveta_prestavi_karty_na_dnes():
    volania = []
    a = types.SimpleNamespace(
        world="work", dashboard_grid=object(),
        _rebuild_dashboard_stats_grid=lambda: volania.append("karty"),
        _refresh_kamae_state_text=lambda: volania.append("stav"))
    a._nazov_vhre = types.MethodType(D._nazov_vhre, a)
    D._sync_world_nazvy(a)
    assert volania == ["karty", "stav"]
    # karty este nepostavene (start) -> nic sa nestavia
    volania.clear()
    a.dashboard_grid = None
    D._sync_world_nazvy(a)
    assert volania == ["stav"]
    kod = zdroj_metody("_metric_info")
    assert "zapamataj_text_stranky(self," in kod
