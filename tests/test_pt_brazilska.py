# -*- coding: utf-8 -*-
"""Portugalcina v appke je brazilska (0.2, faza jazykov).

Prepinac ju vola „Português (Brasil)“ a hlasy su pt-BR, no do 0.2 sa v nej
miesali dve varianty: na konci relacie „Jogaste {time}.“ (europska, „tu“)
vedla „Você trabalhou por {time}.“ (brazilska, „você“), v navode na
parovanie „telemóvel“ v krokoch 1 a 3 a „celular“ v kroku 2. Starsie texty
su prepisane do brazilskej portugalciny; tento test drzi slova a tvary,
ktore v Brazilii nikto nepovie.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402

# Kazdy vzor je jednoznacne europsky (brazilsky ekvivalent v komentari).
# Porovnava sa bez ohladu na velkost pismen.
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
    r"\best(á|ou|ão|ava) a \w+r\b",   # está ouvindo, nie „está a ouvir“
)
# „a app“ (brazilsky „o app“) - s ohladom na velkost pismen: velke A je
# obchod („na App Store“), nie appka.
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
