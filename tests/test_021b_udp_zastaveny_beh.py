# -*- coding: utf-8 -*-
"""A stopped run takes no UDP port and reports nothing (0.2.1, BUG 3 - check).

`_serve` starts the UDP thread only after `_notify("connecting")`, which in
the app goes via `ui_call` - and that waits for the GUI from a foreign
thread. Meanwhile the run may be stopped and a new one may already be
opening the same port. If the old run still grabbed the port, the new one
would get "UDP port drzi iny program" (another program holds the UDP port),
although Zanshin itself held it briefly, and UDP/OSC would stay dead in the
new run with no retry. And conversely, if the old run hit a taken port, it
would write a warning to app.log for a run that no longer exists.
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
    monkeypatch.setattr(heart_rate, "log", spy)   # `_udp_loop` lives here
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
    run.shutdown()                  # run stopped before the thread got going
    mon._udp_loop(HOST, 4455, run)
    assert vazby == []
    assert stavy == [] and spy.varovania == []


def test_beh_zastaveny_pocas_vazby_nehlasi_nic(monkeypatch):
    """Stopped right before the bind fails: the new run already held the
    port, so it is not an error anybody needs to be told about."""
    mon, stavy, spy = _monitor(monkeypatch)
    run = heart_rate._Run(1)

    def _bind(kind, host, port):
        run.shutdown()
        raise OSError(errno.EADDRINUSE, "port je obsadeny")

    mon._bind = _bind
    mon._udp_loop(HOST, 4455, run)
    assert stavy == [] and spy.varovania == []


def test_bezici_beh_obsadeny_port_stale_nahlasi(monkeypatch):
    """Safeguard against a too broad condition above: a live run reports."""
    mon, stavy, spy = _monitor(monkeypatch)
    run = heart_rate._Run(3)

    def _bind(kind, host, port):
        raise OSError(errno.EADDRINUSE, "port je obsadeny")

    mon._bind = _bind
    mon._udp_loop(HOST, 4455, run)
    assert stavy == [(("udp_busy", 4455), 3)]
    assert len(spy.varovania) == 1 and "4455" in spy.varovania[0]
