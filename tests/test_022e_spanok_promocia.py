# -*- coding: utf-8 -*-
"""Uspanie PC rozdeli relaciu (0.2.2 davka 4) - kontrola skeptika: relacia
uzavreta po spanku sa nesmie stat promociou.

Promocia ("plny Zanshin") sa spusti RAZ - trvaly priznak sa hned ulozi a jej
jedinu spravu nesie dotaznik (`summary["zen_graduation"]`). Po spanku sa
dotaznik neotvara (hrac pri tom nebol), takze by sprava prepadla navzdy.
Rovnake pravidlo uz plati pri vypinani Windows: promocia sa vyhodnoti az po
dalsej relacii. Vlozene hodiny, synteticky tep."""
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
