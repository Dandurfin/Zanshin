"""Sprievodca netvrdi mechanizmy ako fakt bez zdroja (KNOWN_ISSUES.md, bod 4).

Kontroluje VSETKY jazyky: stary text by inak prezil v ja..bg, kde ho
make_translation_todo.py nenajde (hlada len retazce rovne anglictine), a
neskorsi `_tr7` riadok by ho tam potichu vratil. Nadpisy Sprievodcu a panela
v Historii zas nesmu slubovat vedu ani ucinok.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import i18n

_KARTY = ("guide.grounding.science", "guide.jaw.science", "guide.periphery.science",
          "guide.periphery.physiology", "guide.breath.tech1.why", "guide.breath.tech2.why",
          # 0.2: „aktivacia hlbokeho stabilizacneho systemu“ bola fakt bez zdroja
          "guide.grounding.physiology")

# Stare tvrdenia vo vsetkych pismach; porovnava sa na malych pismenach.
# 中心視 / 中央视觉 tu zamerne NIE SU: po japonsky a cinsky je to obycajne
# „centralne videnie“, ktore nova veta vo fyziologii legitimne hovori. Stary
# ja/zh text aj tak chyti 交感 (副交感) a アドレナリン / 肾上腺.
_ZAKAZANE = (
    # amygdala
    "amygdal", "amígdal", "миндалев", "扁桃体", "杏仁核",
    # sympatikus / parasympatikus ("sympat" chyti aj "parasympat")
    "sympat", "simpát", "симпат", "交感",
    # „foveálny režim“
    "fove", "фовеал",
    # adrenalin
    "adrenal", "adrénal", "адренал", "アドレナリン", "肾上腺",
    # „primárny evolučný prejav“
    "evolut", "évolut", "evoluč", "эволюц", "進化", "进化",
    # CO2 v alveolách
    "alveol", "alvéol", "альвеол", "肺胞", "肺泡", "lungenbläschen",
    # „najrýchlejší biologický mechanizmus“ (es/pt „más/mais rápido“ je aj
    # obycajny komparativ - stary es/pt text chyti „alvéol“)
    "fastest", "najrýchlejš", "schnellste", "le plus rapide", "самый быстр",
    "最も速い", "最快",
    # „stabilizuje parasympatikus“
    "stabiliz",
)

_NADPISY = ("guide.block.science", "guide.block.why_title", "guide.panel_title",
            "guide.window_title", "dnes.why_link", "settings.guide_sub",
            "origin.title",
            # 0.2: graf v Historii bol „Ktora hlaska zabera“ / „Which cue works“
            "history.effect_title")

# „veda“ ako cele slovo (aj tvary) - obycajny podretazec by chytil „povedal“.
_VEDA = re.compile(r"\b(veda|vedy|vede|vedu|vedou|vedeck\w*)\b", re.I)
# Veda v ostatnych jazykoch; \b, aby „conscience“ / „conciencia“ neprekazali.
_VEDA_INDE = re.compile(r"\bscien|\bcienc|\bciênc|wissenschaft|наук|науч|科学", re.I)
_UCINOK = re.compile(r"\b(works|funguje)\b", re.I)


def test_karty_netvrdia_neoverene_mechanizmy():
    zle = [f"{k}[{jazyk}]: {z}" for k in _KARTY
           for jazyk, text in i18n.STRINGS[k].items()
           for z in _ZAKAZANE if z in text.lower()]
    assert not zle, "vratil sa neovereny mechanizmus:\n  " + "\n  ".join(zle)


def test_nadpisy_nesluboju_vedu():
    kluce = _NADPISY + ("origin.text", "origin.examples")
    zle = [f"{k}[{jazyk}]" for k in kluce
           for jazyk, text in i18n.STRINGS[k].items()
           if _VEDA.search(text) or _VEDA_INDE.search(text)]
    assert not zle, "nadpis stale slubuje vedu: " + ", ".join(zle)


def test_nadpisy_nesluboju_ucinok():
    zle = [f"{k}[{jazyk}]" for k in _NADPISY for jazyk in ("sk", "en")
           if _UCINOK.search(i18n.STRINGS[k][jazyk])]
    assert not zle, "nadpis stale slubuje, ze to funguje: " + ", ".join(zle)


def test_kontrola_naozaj_nieco_chyta():
    """Poistka: blocklist aj regexy musia na starom znení naozaj zabrat."""
    stare = ("Tunnel vision while aiming switches the brain into a narrow foveal mode",
             "Смягчение фокуса задействует парасимпатическую систему",
             "视线放柔能激活副交感神经系统",
             "rééquilibrer le CO₂ dans les alvéoles pulmonaires")
    for veta in stare:
        assert any(z in veta.lower() for z in _ZAKAZANE), veta
    assert _VEDA.search("Čo na to veda") and not _VEDA.search("povedal")
    assert _VEDA_INDE.search("Qué dice la ciencia")
    assert not _VEDA_INDE.search("la conscience du corps")
