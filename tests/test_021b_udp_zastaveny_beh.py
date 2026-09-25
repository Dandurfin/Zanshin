# -*- coding: utf-8 -*-
"""Zastaveny beh UDP port neberie a nic nehlasi (0.2.1, BUG 3 - kontrola).

`_serve` spusta UDP vlakno az po `_notify("connecting")`, ktore v appke ide
cez `ui_call` - a to z cudzieho vlakna caka na GUI. Medzitym moze byt beh
zastaveny a novy uz otvara ten isty port. Keby stary beh port este chytil,
novy by dostal "UDP port drzi iny program" (hoci ho na chvilu drzal Zanshin
sam) a UDP/OSC by v novom behu ostalo mrtve bez opakovania. A keby naopak
stary beh na obsadeny port narazil, zapisal by do app.log varovanie za beh,
ktory uz neexistuje.
"""
import errno
import os
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import heart_rate  # noqa: E402

HOST = "127.0.0.1"


class _SpyLog:
    def __init__(self):
        self.varovania = []

    def warning(self, fmt, *args):
        self.varovania.append(fmt % args)

    def info(self, *_a, **_k):
        pass

    def exception(self, *_a, **_k):
        pass


def _monitor(monkeypatch):
    spy = _SpyLog()
    monkeypatch.setattr(heart_rate, "log", spy)   # `_udp_loop` byva tu
    stavy = []
    mon = heart_rate.HeartRateMonitor(
        on_bpm=lambda *_a: None,
        on_status=lambda stav, gen: stavy.append((stav, gen)))
    return mon, stavy, spy


def test_zastaveny_beh_udp_port_vobec_neotvara(monkeypatch):
    mon, stavy, spy = _monitor(monkeypatch)
    vazby = []

    def _bind(kind, host, port):
        vazby.append(kind)
        raise AssertionError("zastaveny beh nesmie port otvarat")

    mon._bind = _bind
    run = heart_rate._Run(1)
    run.shutdown()                  # beh zastaveny skor, nez sa vlakno rozbehlo
    mon._udp_loop(HOST, 4455, run)
    assert vazby == []
    assert stavy == [] and spy.varovania == []


def test_beh_zastaveny_pocas_vazby_nehlasi_nic(monkeypatch):
    """Zastavenie tesne pred zlyhanim vazby: port drzal uz novy beh, takze
    to nie je chyba, o ktorej treba komukolvek hovorit."""
    mon, stavy, spy = _monitor(monkeypatch)
    run = heart_rate._Run(1)

    def _bind(kind, host, port):
        run.shutdown()
        raise OSError(errno.EADDRINUSE, "port je obsadeny")

    mon._bind = _bind
    mon._udp_loop(HOST, 4455, run)
    assert stavy == [] and spy.varovania == []


def test_bezici_beh_obsadeny_port_stale_nahlasi(monkeypatch):
    """Poistka proti prilis sirokej podmienke vyssie: zivy beh sa nahlasi."""
    mon, stavy, spy = _monitor(monkeypatch)
    run = heart_rate._Run(3)

    def _bind(kind, host, port):
        raise OSError(errno.EADDRINUSE, "port je obsadeny")

    mon._bind = _bind
    mon._udp_loop(HOST, 4455, run)
    assert stavy == [(("udp_busy", 4455), 3)]
    assert len(spy.varovania) == 1 and "4455" in spy.varovania[0]
