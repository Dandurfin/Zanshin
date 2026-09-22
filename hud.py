"""Zivy HUD panel v hre - tep, zataz a priebeh relacie.

Co to je
--------
Jedno male klikom-priechodne okno v rohu obrazovky, ktore ukazuje:

  * aktualny tep velkym cislom + srdce, ktore bije v REALNOM rytme
    (periferne videnie tak dostane informaciu aj bez citania cisla),
  * krivku tepu za poslednych ~3 minuty s vyznacenou kritickou hranicou
    a vlastnou pokojovou zakladnou,
  * pruh "Záťaž" (0-100) - zlozeninu z hr_stats.py, nie vymysleny "stres",
  * riadok relacie: dlzka, pocet spustenych pripomienok, cas nad hranicou.

Preco vlastne okno a nie sucast vizualov slotov
-----------------------------------------------
Vizualy slotov su UDALOSTI (stlacil si klavesu -> na 3 s sa nieco ukaze).
HUD je STAV - visi tam cely cas. Miesanie oboch do jedneho okna by
znamenalo, ze HUD zhasne vzdy, ked dobehne animacia slotu.

Vykon
-----
Prekresluje sa 8x za sekundu a len vtedy, ked je naozaj viditelny. Jeden
snimok je ~250x105 logickych pixelov (na 4K dvojnasobok), co je rad
velkosti nizsie nez dychovy kruh - v hre to nie je meratelne.

Anti-cheat: plati to iste co pre overlay.py - ziadna injekcia, ziadne
citanie hry, okno je klikom priechodne a v Alt+Tab nie je. Viz
layer_window.py.
"""

import time

import display
import hud_paint
from layer_window import LayeredSurface

REFRESH_MS = 125           # 8 fps - srdce staci, aby vyzeralo zivo
REPOSITION_EVERY_S = 2.0   # ako casto kontrolujeme, ci sa nezmenil monitor

# Predvolena poloha: lavy dolny roh, nad beznym miestom pre chat/killfeed.
DEFAULT_POS = (13.0, 90.0)

class StatsHud:
    """HUD panel so statistikou tepu.

    Vlastnik (DandurfApp) mu len nastavi konfiguraciu a poviе, odkial brat
    data (`stats`); o okno, prekreslovanie aj presun medzi monitormi sa
    stara sam.
    """

    def __init__(self, root, stats, style, monitor_target=display.TARGET_AUTO):
        self.root = root
        self.stats = stats
        self.style = style
        self.monitor_target = monitor_target

        self.enabled = False
        self.scale = 1.0
        self.pos = DEFAULT_POS
        self.opacity = 0.92
        self.critical_bpm = 110
        self.labels = {}
        self.connected = False
        self.session_text = ""

        self.surface = None
        self._job = None
        self._geometry = None          # (monitor_key, w, h, x, y)
        self._last_reposition = 0.0
        self._ss = 3

        # Riadok 4 ikoniek funkcii pod HUD panelom (nahrada za povodny
        # celoappkovy "Minimalisticky rezim" - teraz je to sucast tohoto
        # istého panela, ktory uz beh mal v hre BPM/zataz). Vypnute
        # predvolene, aby sa panel nezmenil pre nikoho, kto uz HUD pouziva.
        self.show_triggers = False
        self.trigger_icon_color = None   # None = farba temy (ako HUD)
        self._triggers = []              # [(visual_name, enabled)]
        self._on_trigger_click = None    # callback(index)

    # ---------- konfiguracia ----------

    def configure(self, enabled=None, scale=None, pos=None, opacity=None,
                  critical_bpm=None, monitor_target=None):
        rebuild = False
        if enabled is not None:
            self.enabled = bool(enabled)
        if scale is not None:
            new = max(0.6, min(2.0, float(scale)))
            rebuild = rebuild or new != self.scale
            self.scale = new
        if pos is not None:
            rebuild = rebuild or tuple(pos) != tuple(self.pos)
            self.pos = (float(pos[0]), float(pos[1]))
        if opacity is not None:
            self.opacity = max(0.25, min(1.0, float(opacity)))
            if self.surface is not None:
                self.surface.set_alpha(self.opacity)
        if critical_bpm is not None:
            self.critical_bpm = int(critical_bpm)
        if monitor_target is not None:
            rebuild = rebuild or monitor_target != self.monitor_target
            self.monitor_target = monitor_target

        if not self.enabled:
            self.stop()
            return
        if rebuild:
            self._teardown_window()
        self.start()

    def set_style(self, style):
        self.style = style

    def set_labels(self, labels):
        self.labels = labels or {}

    def set_connected(self, connected):
        self.connected = bool(connected)

    def set_session_text(self, text):
        self.session_text = text or ""

    def configure_triggers(self, show=None, icon_color=None, triggers=None,
                           on_click=None):
        """Riadok 4 ikoniek funkcii pod HUD panelom ("Ukazat panel v hre" v
        Nastaveniach -> V hre -> Vizualy). Nahradza povodny celoappkovy
        "Minimalisticky rezim" - to isté zobrazenie (BPM + 4 funkcie), ale
        teraz je to jedna cast HUD panela v hre, nie prepnutie celej appky.

        `triggers`: [(visual_name, enabled), ...] max 4 polozky.
        `on_click(index)`: zavola sa pri kliku na i-tu ikonku (hrac klikom
        na malej ikonke spusti tu istu pripomienku ako klavesou).
        """
        rebuild = False
        if show is not None:
            new_show = bool(show)
            rebuild = rebuild or new_show != self.show_triggers
            self.show_triggers = new_show
        if icon_color is not None:
            self.trigger_icon_color = icon_color or None
        if triggers is not None:
            self._triggers = list(triggers)[:4]
        if on_click is not None:
            self._on_trigger_click = on_click
        if rebuild and self.surface is not None:
            self._teardown_window()

    # ---------- zivotny cyklus ----------

    def start(self):
        if not self.enabled or self._job is not None:
            return
        self._tick()

    def stop(self):
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        self._teardown_window()

    def _teardown_window(self):
        if self.surface is not None:
            try:
                self.surface.destroy()
            except Exception:
                pass
        self.surface = None
        self._geometry = None

    # ---------- kreslenie ----------

    def _ensure_window(self):
        monitor = display.resolve_target(self.monitor_target, self.root)
        total = self.scale * monitor.scale
        w = max(140, int(round(hud_paint.HUD_WIDTH * total)))
        base_h = hud_paint.HUD_HEIGHT
        if self.show_triggers and self._triggers:
            base_h += 4 + hud_paint.TRIGGER_ROW_HEIGHT
        h = max(60, int(round(base_h * total)))
        x, y = display.place(monitor, w, h, self.pos[0], self.pos[1])
        key = (monitor.x, monitor.y, monitor.width, monitor.height, w, h, x, y)
        if self.surface is not None and self._geometry == key:
            return True
        if self.surface is not None and self._geometry is not None:
            # zmenil sa len monitor/poloha - staci okno presunut
            if self._geometry[4:6] == (w, h):
                self.surface.move(x, y)
                self._geometry = key
                return True
            self._teardown_window()
        self.surface = LayeredSurface(self.root)
        self.surface.create(x, y, w, h)
        self.surface.set_alpha(self.opacity)
        self._geometry = key
        self._ss = 2 if (w * h) > 90000 else 3
        return True

    def _tick(self):
        self._job = None
        if not self.enabled:
            return
        try:
            self._draw()
        except Exception:
            pass
        try:
            self._job = self.root.after(REFRESH_MS, self._tick)
        except Exception:
            self._job = None

    def _draw(self):
        now = time.time()
        if now - self._last_reposition > REPOSITION_EVERY_S or self.surface is None:
            self._last_reposition = now
            self._ensure_window()
        if self.surface is None:
            return

        stats = self.stats
        image = hud_paint.render_hud(
            self.style,
            bpm=stats.last_bpm if self.connected else None,
            stress=stats.stress,
            history=stats.series(90),
            threshold=self.critical_bpm,
            baseline=stats.baseline,
            labels=self.labels,
            pulse=stats.beat_phase(now) if self.connected else 0.0,
            session=self.session_text,
            connected=self.connected,
            ss=self._ss)
        if self.show_triggers and self._triggers:
            row = hud_paint.render_hud_trigger_row(
                hud_paint.HUD_WIDTH, self.style, self._triggers,
                icon_color=self.trigger_icon_color)
            image = hud_paint.render_hud_combined(image, row)
        self.surface.draw(image)
        self.surface.show()

    def handle_click(self, rel_x, rel_y):
        """Preklad klikneho bodu (0..1 v ramci okna) na index ikonky v
        riadku triggerov - POUZITELNE LEN v nahlade vnutri appky (napr.
        tlacidlo "Test" v Nastaveniach), NIE v realnej hre.

        Docela zamerne: HUD panel v hre ostava VZDY click-through
        (WS_EX_TRANSPARENT) - to je zakladny bezpecnostny/anti-cheat
        princip appky (viz layer_window.py hlavicka). Vypnutie
        click-through len kvoli klikatelnym ikonkam by znamenalo, ze
        appka v hre trvalo krade klik zo hry, co je presne to riziko,
        ktoremu sa ma vyhybat. Ikonky su preto v hre CISTO VIZUALNA
        pripomienka funkcie (piktogram), nie tlacidlo.
        """
        if not self.show_triggers or not self._triggers:
            return None
        total_h = hud_paint.HUD_HEIGHT + 4 + hud_paint.TRIGGER_ROW_HEIGHT
        row_top = (hud_paint.HUD_HEIGHT + 4) / total_h
        if rel_y < row_top:
            return None
        n = len(self._triggers)
        index = min(n - 1, max(0, int(rel_x * n)))
        if callable(self._on_trigger_click):
            self._on_trigger_click(index)
        return index
