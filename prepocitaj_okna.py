# -*- coding: utf-8 -*-
"""Recomputes the VALIDITY of saved measurement windows by today's rules.

WHY THIS EXISTS
A window carries `valid` and `reasons` from the moment it was created.
When a rule changes, old records do not know about it - and the
effectiveness graph keeps counting windows that would not pass today.
That is exactly what happened on 19. 9., when the reason
`nebol_pri_klavesnici` was added: of the six valid windows, four were
ones in which the player was not at the computer at all, and three of
them were the biggest "the cue worked" results in the whole file.

WHAT IT DOES AND WHAT IT DOES NOT
It only fills in reasons that can be derived from the window's ALREADY
SAVED fields - i.e. from `pre_activity` and `post_activity`. It does not
touch `skratene_pred`, `skratene_po`, `diera_v_datach`,
`refraktern_zona` or `kruh_pri_vysokom_tepe`: those were computed from raw
heart-rate samples and from when the ring at high heart rate was on
screen, which are not in the file, and guessing them after the fact would
mean making up numbers nobody measured.

RECORDS ARE NOT DELETED. The window stays, numbers and all; it just
stops being valid and gets a reason. Raw data can always be filtered
again; it can be deleted only once.
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
    """Reasons that follow from activity at the keyboard. The same rule as
    `measure.build_window` - when it changes there, it changes here too."""
    pre = okno.get("pre_activity")
    post = okno.get("post_activity")
    # `None` means "we do not know", not "was away" - old sessions did not
    # record activity, and not knowing must not invalidate a window.
    if ((pre is not None and pre < measure.MIN_AKTIVITA)
            or (post is not None and post < measure.MIN_AKTIVITA)):
        return [measure.R_NEAKTIVNY]
    return []


def prepocitaj(cesta, zapisat=True):
    """Returns (n_windows, changed, backup_path). `zapisat=False` = preview."""
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
        # Atomic write - the same pattern as `save_settings`: a crash in the
        # middle of writing would otherwise leave a truncated file, and with
        # it the loss of the whole measurement history.
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
