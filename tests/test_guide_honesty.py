"""Guide states no unsourced mechanism as fact (KNOWN_ISSUES.md, item 4).

Checks ALL languages: otherwise the old text would survive in ja..bg, where
make_translation_todo.py does not find it (it looks only for strings equal
to the English), and a later `_tr7` line would quietly bring it back there.
The headings of the Guide and of the panel in History must not promise
science or effect either.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import i18n

_KARTY = ("guide.grounding.science", "guide.jaw.science", "guide.periphery.science",
          "guide.periphery.physiology", "guide.breath.tech1.why", "guide.breath.tech2.why",
          # 0.2: "aktivacia hlbokeho stabilizacneho systemu" (activation of the
          # deep stabilising system) was a fact without a source
          "guide.grounding.physiology")

# Old claims in all scripts; compared in lower case.
# 中心視 / 中央视觉 are deliberately NOT here: in Japanese and Chinese it is
# ordinary "central vision", which the new sentence in the physiology part
# legitimately says. The old ja/zh text is caught anyway by 交感 (副交感) and
# アドレナリン / 肾上腺.
_ZAKAZANE = (
    # amygdala
    "amygdal", "amígdal", "миндалев", "扁桃体", "杏仁核",
    # sympathetic / parasympathetic ("sympat" also catches "parasympat")
    "sympat", "simpát", "симпат", "交感",
    # "foveal mode"
    "fove", "фовеал",
    # adrenaline
    "adrenal", "adrénal", "адренал", "アドレナリン", "肾上腺",
    # "primary evolutionary response"
    "evolut", "évolut", "evoluč", "эволюц", "進化", "进化",
    # CO2 in the alveoli
    "alveol", "alvéol", "альвеол", "肺胞", "肺泡", "lungenbläschen",
    # "the fastest biological mechanism" (es/pt "más/mais rápido" is also an
    # ordinary comparative - the old es/pt text is caught by "alvéol")
    "fastest", "najrýchlejš", "schnellste", "le plus rapide", "самый быстр",
    "最も速い", "最快",
    # "stabilises the parasympathetic"
    "stabiliz",
)

_NADPISY = ("guide.block.science", "guide.block.why_title", "guide.panel_title",
            "guide.window_title", "dnes.why_link", "settings.guide_sub",
            "origin.title",
            # 0.2: the chart in History was "Ktora hlaska zabera" /
            # "Which cue works"
            "history.effect_title")

# "veda" (science) as a whole word (also its forms) - a plain substring
# would catch "povedal".
_VEDA = re.compile(r"\b(veda|vedy|vede|vedu|vedou|vedeck\w*)\b", re.I)
# Science in the other languages; \b so that "conscience" / "conciencia"
# do not get in the way.
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
    """Safeguard: the blocklist and regexes must really hit the old text."""
    stare = ("Tunnel vision while aiming switches the brain into a narrow foveal mode",
             "Смягчение фокуса задействует парасимпатическую систему",
             "视线放柔能激活副交感神经系统",
             "rééquilibrer le CO₂ dans les alvéoles pulmonaires")
    for veta in stare:
        assert any(z in veta.lower() for z in _ZAKAZANE), veta
    assert _VEDA.search("Čo na to veda") and not _VEDA.search("povedal")
    assert _VEDA_INDE.search("Qué dice la ciencia")
    assert not _VEDA_INDE.search("la conscience du corps")
