# -*- coding: utf-8 -*-
"""Prepocita PLATNOST uz ulozenych meracich okien podla dnesnych pravidiel.

PRECO TO EXISTUJE
Okno si nesie `valid` a `reasons` z chvile, kedy vzniklo. Ked sa pravidlo
zmeni, stare zaznamy o tom nevedia - a graf ucinnosti dalej rata okna, ktore
by dnes neobstali. Presne to sa stalo 19. 9., ked pribudol dovod
`nebol_pri_klavesnici`: zo siestich platnych okien boli styri take, v ktorych
hrac pri pocitaci vobec nebol, a tri z nich boli najvacsie "hlaska zabrala"
vysledky v celom subore.

CO ROBI A CO NEROBI
Dopocitava len dovody, ktore sa daju odvodit z UZ ULOZENYCH poli okna -
teda z `pre_activity` a `post_activity`. Nesiaha na `skratene_pred`,
`skratene_po`, `diera_v_datach` ani `refraktern_zona`: tie sa ratali zo
surovych vzoriek tepu, ktore v subore nie su, a hadat ich spatne by
znamenalo vyrobit cisla, ktore nikto nenameral.

ZAZNAMY SA NEMAZU. Okno ostava aj s cislami, len prestane platit a dostane
dovod. Surove data sa daju vzdy prefiltrovat znova; zmazat sa daju raz.
"""

import io
import json
import os
import shutil
import sys
from datetime import datetime

import measure
from paths import data_dir


def _dovody_z_aktivity(okno):
    """Dovody, ktore plynu z aktivity pri klavesnici. Rovnake pravidlo ako
    `measure.build_window` - ked sa zmeni tam, zmeni sa aj tu."""
    pre = okno.get("pre_activity")
    post = okno.get("post_activity")
    # `None` znamena "nevieme", nie "bol prec" - stare relacie aktivitu
    # nezapisovali a neznalost nesmie zneplatnit okno.
    if ((pre is not None and pre < measure.MIN_AKTIVITA)
            or (post is not None and post < measure.MIN_AKTIVITA)):
        return [measure.R_NEAKTIVNY]
    return []


def prepocitaj(cesta, zapisat=True):
    """Vrati (pocet_okien, zmenene, cesta_zalohy). `zapisat=False` = nahlad."""
    with io.open(cesta, encoding="utf-8") as f:
        data = json.load(f)
    okna = data["windows"] if isinstance(data, dict) and "windows" in data else data

    zmenene = []
    for okno in okna:
        stare_valid = okno.get("valid")
        dovody = list(okno.get("reasons") or [])
        for d in _dovody_z_aktivity(okno):
            if d not in dovody:
                dovody.append(d)
        novy_valid = not dovody
        if novy_valid != stare_valid or dovody != (okno.get("reasons") or []):
            zmenene.append((okno, stare_valid, novy_valid, dovody))
        okno["reasons"] = dovody
        okno["valid"] = novy_valid

    zaloha = None
    if zapisat and zmenene:
        znacka = datetime.now().strftime("%Y%m%d-%H%M%S")
        zaloha = "%s.pred-prepoctom-%s" % (cesta, znacka)
        shutil.copy2(cesta, zaloha)
        # Atomicky zapis - rovnaky vzor ako `save_settings`: pri pade
        # uprostred zapisu by inak ostal orezany subor a s nim aj strata
        # celej historie merania.
        tmp = cesta + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, cesta)
    return len(okna), zmenene, zaloha


def main(argv):
    nahlad = "--nahlad" in argv
    cesta = os.path.join(data_dir(), "hr_windows.json")
    if not os.path.exists(cesta):
        print("subor s oknami neexistuje:", cesta)
        return 1

    spolu, zmenene, zaloha = prepocitaj(cesta, zapisat=not nahlad)
    print("okien v subore: %d" % spolu)
    if not zmenene:
        print("nic sa nemeni - vsetky okna uz sedia s dnesnymi pravidlami")
        return 0

    print("zmenenych: %d\n" % len(zmenene))
    for okno, stare, nove, dovody in zmenene:
        kedy = datetime.fromtimestamp(okno.get("ts", 0)).strftime("%d.%m. %H:%M")
        pre, post = okno.get("pre_bpm"), okno.get("post_bpm")
        delta = ("%+.1f" % (post - pre)) if (pre is not None and post is not None) else "-"
        print("  %s  %-10s aktivita %s/%s  tep %s -> %s (%s)" % (
            kedy, okno.get("category"), okno.get("pre_activity"),
            okno.get("post_activity"), pre, post, delta))
        print("      platne: %s -> %s   dovody: %s" % (
            stare, nove, ", ".join(dovody) or "-"))

    if nahlad:
        print("\n(nahlad - nic sa nezapisalo)")
    else:
        print("\nzaloha: %s" % zaloha)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
