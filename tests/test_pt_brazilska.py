# -*- coding: utf-8 -*-
"""Portuguese in the app is Brazilian (0.2, language phase).

The switch calls it „Português (Brasil)“ and the voices are pt-BR, but
until 0.2 two variants were mixed in it: at the end of a session „Jogaste
{time}.“ (European, „tu“) next to „Você trabalhou por {time}.“
(Brazilian, „você“), and in the pairing guide „telemóvel“ in steps 1 and
3 and „celular“ in step 2. The older texts have been rewritten into
Brazilian Portuguese; this test keeps out the words and forms that nobody
in Brazil would say.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402

# Each pattern is unambiguously European (Brazilian equivalent in the
# comment). Compared ignoring letter case.
EUROPSKE = (
    r"\btelemóve(l|is)\b",            # celular
    r"\bficheiros?\b",                # arquivo
    r"\bregistos?\b",                 # registro
    r"\becrãs?\b",                    # tela
    r"\bpalavra-passe\b",             # senha
    r"\bfolhas? de cálculo\b",        # planilha
    r"\b(teu|tua|teus|tuas)\b",       # seu / sua
    r"\btu\b",                        # você
    r"\b(estás|podes|queres|tens|vês|jogaste|sentiste|quiseres)\b",
    r"\best(á|ou|ão|ava) a \w+r\b",   # está ouvindo, not „está a ouvir“
)
# „a app“ (Brazilian „o app“) - case-sensitive: a capital A is the
# store („na App Store“), not the app.
EUROPSKA_APP = r"\b(a|à|da|na|pela) app\b"


def _europske(text):
    najdene = [vzor for vzor in EUROPSKE if re.search(vzor, text, re.IGNORECASE)]
    if re.search(EUROPSKA_APP, text):
        najdene.append(EUROPSKA_APP)
    return najdene


def test_kontrola_nieco_kontroluje():
    for europske in ("Jogaste {time}.", "no telemóvel", "o teu pulso",
                     "a app está a ouvir", "Como te sentiste"):
        assert _europske(europske), europske
    for brazilske in ("Você jogou por {time}.", "no celular", "o seu pulso",
                      "o app está ouvindo", "na App Store",
                      "começo a ouvir sozinha"):
        assert not _europske(brazilske), brazilske


def test_portugalcina_je_brazilska():
    zle = {kluc: _europske(zaznam["pt"]) for kluc, zaznam in i18n.STRINGS.items()
           if _europske(zaznam["pt"])}
    assert not zle, "europska portugalcina:\n  " + "\n  ".join(
        f"{k}: {v}" for k, v in sorted(zle.items()))
