# -*- coding: utf-8 -*-
"""Putting the PC to sleep splits the session (0.3 batch 4) - skeptic's
check: a session closed after sleep must not become a graduation.

The graduation ("full Zanshin") fires ONCE - a permanent flag is saved right
away and its only message is carried by the questionnaire
(`summary["zen_graduation"]`). After sleep the questionnaire does not open
(the player was not there), so the message would be lost forever. The same
rule already applies when Windows shuts down: the graduation is evaluated
only after the next session. Injected clock, synthetic heart rate."""
import test_022b_data_vypnutie as vypnutie


def _appka(tmp_path):
    a = vypnutie._appka(tmp_path, minut=15)

    def otvor(**k):
        a.otvorene.append(k)
        a._hr_session_open = True
    a._open_hr_session = otvor
    return a


def test_po_spanku_bez_promocie_aj_bez_dotaznika(tmp_path):
    a = _appka(tmp_path)
    posledny = a.hr_stats.session_start + 10 * 60.0
    a._posledny_tik_relacie = posledny
    assert a._hlidaj_medzeru_relacie(teraz=posledny + 8 * 3600.0) is True
    assert len(vypnutie._historia(a)) == 1, "relacia sa ulozila"
    assert a.dotazniky == []
    assert a.promocie == [], "jednorazova sprava by sa bez dotaznika stratila"


def test_bezne_zatvorenie_promociu_dalej_vyhodnoti(tmp_path):
    a = _appka(tmp_path)
    a._close_hr_session()
    assert len(a.promocie) == 1 and len(a.dotazniky) == 1
