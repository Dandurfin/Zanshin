"""In-game somaticke vizualy (Overlay) - jeden nezavisly vizual na kazdy
zo 4 slotov (tazisko / celust / uvolnenie / dych).

Co sa oproti alpha 0.4 zmenilo a preco
--------------------------------------
1. ROZLISENIE. Rozmery vizualov su zadane v "1080p pixeloch" a nasobia sa
   `Monitor.scale` (vyska monitora / 1080). Na 4K je teda vsetko 2x vacsie
   a zabera rovnaku CAST obrazovky - predtym bol vizual na 4K stvrtinovy.

2. VIAC MONITOROV. Poloha sa rata voci konkretnemu monitoru zo
   `display.resolve_target()`, nie voci `winfo_screenwidth()` (co je vzdy
   len primarna obrazovka). Kto ma hru na druhom monitore, vizual tam
   konecne uvidi. Predvolba "auto" berie monitor, na ktorom je aktivne
   okno - cize hru.

3. VZHLAD. Kreslenie preslo z tk.Canvas (tvrde hrany, emoji) na PIL +
   UpdateLayeredWindow (per-pixel alfa, ziara, antialiasing) - viz
   hud_paint.py a layer_window.py.

Anti-cheat
----------
Bez zmeny oproti povodnemu navrhu, len prisnejsie: okno je klikom
priechodne (WS_EX_TRANSPARENT), nikdy sa neaktivuje (WS_EX_NOACTIVATE),
nie je v Alt+Tab (WS_EX_TOOLWINDOW), nic neinjektuje a o hre nevie nic
okrem toho, ktory monitor ma prave aktivne okno. Detaily v layer_window.py.
"""

import time

try:
    from PIL import ImageDraw
except Exception:  # pragma: no cover
    ImageDraw = None

import display
import hud_paint
import logging_setup
from hud_paint import Style
from settings_model import OVERLAY_DEFAULT_POS
from layer_window import LayeredSurface

log = logging_setup.get_logger("overlay")


class _SlotOverlay:
    """Jeden konkretny in-game vizual (pre 1 slot).

    Kostra je spolocna pre vsetky 4:
      * vlastne klikom-priechodne okno (LayeredSurface),
      * fade-in -> animacia -> fade-out, vsetko cez Tk `.after()` (ziadny
        time.sleep - to iste vlakno obsluhuje aj poll aktivity a spustac
        hlasky, takze spanok v nom by zastavil oboje),
      * novy trigger pocas bezania starej animacie ju okamzite zrusi
        (`play() -> self.stop()`) a zacne od nuly.

    Fade nestoji nic navyse: meni sa len konstantna alfa vrstveneho okna,
    snimok sa neprekresluje.
    """

    TICK_MS = 40                 # 25 fps - na dychanie a dopad viac netreba
    FADE_MS = 260
    HOLD_S = 3.0

    # dychovy cyklus - predvolba 4 s nadych / 6 s vydych, hrac si ich vie
    # zmenit v Nastaveniach (viz SomaticOverlayManager.set_breath_seconds)
    INHALE_S_DEFAULT = 4.0
    EXHALE_S_DEFAULT = 6.0
    CYCLES = 2                   # 2 cykly na jedno spustenie slotu

    # Ako dlho bezi "vstupna" animacia jednotlivych vizualov. Po jej konci
    # sa snimok uz NEPREKRESLUJE (obraz je staticky), takze drzanie
    # vizualu na obrazovke nestoji ziadny vykon.
    INTRO_S = {"grounding": 1.35, "jaw": 0.95, "release": 1.15}

    def __init__(self, root, visual, base_size, manager):
        self.root = root
        self.visual = visual
        self.base_w, self.base_h = base_size
        self.manager = manager

        self.enabled = False
        self.scale = 1.0
        self.pos = (50.0, 50.0)     # % sirky/vysky CIELOVEHO monitora
        self.color = None           # None = akcent temy; inak #rrggbb
        self.inhale_s = self.INHALE_S_DEFAULT
        self.exhale_s = self.EXHALE_S_DEFAULT

        self.surface = None
        self.w = self.h = 0
        self._job = None
        self._gen = 0
        self._start_time = None
        self._ss = 2
        self._static_done = False
        self._label = None
        # Rezim "Test vizualu" (drag & drop). Ked je zapnuty, vizual sa
        # NEskryva po HOLD_S a da sa chytit mysou; po ukonceni sa cez
        # on_test_moved ulozi nova pozicia a vrati sa klik-through.
        self._test_mode = False
        self._drag_origin = None
        self.on_test_moved = None    # callback(index_pos_x, index_pos_y) - nastavi manager

    # ---------- konfiguracia ----------

    def configure(self, enabled=None, scale=None, pos=None, color=None):
        if enabled is not None:
            self.enabled = bool(enabled)
            if not self.enabled:
                self.stop()
        if scale is not None:
            self.scale = max(0.5, min(2.0, float(scale)))
        if pos is not None:
            self.pos = pos
        if color is not None:
            # "" (prazdny retazec) znamena "vrat sa na farbu temy"
            self.color = color or None

    def set_label(self, label):
        self._label = label

    def set_breath_seconds(self, inhale_s, exhale_s):
        self.inhale_s = max(0.5, float(inhale_s))
        self.exhale_s = max(0.5, float(exhale_s))

    # ---------- spustenie ----------

    def trigger(self):
        """Vráti True, ak sa vizuál naozaj začal kresliť.

        Tichá vetva má vizuál ako JEDINÝ podnet — keď zlyhá, meranie by
        porovnávalo hlášku proti ničomu a označilo okno `valid:True` bez
        potvrdeného doručenia (bug B17). Návratka to volajúcemu prezradí.
        Vypnutý vizuál (`not enabled`) nie je zlyhanie — vtedy sa cue vôbec
        nemal doručovať; vráti False, aby sa nemeral.
        """
        if self.enabled:
            return self.play()
        return False

    @property
    def is_active(self):
        return self.surface is not None

    def test(self):
        """Tlacidlo "Test vizualu" - NOVE spravanie (drag & drop).

        Vizual sa zobrazi NASTALO (kym hrac test nevypne) a da sa chytit
        mysou a potiahnut kamkolvek. Predtym to bola len 3-sekundova ukazka
        na fixnej pozicii, takze sa poloha nedala doladit vizualne.

        Druhe volanie test() (alebo stop_test) rezim ukonci a ulozi poziciu.
        """
        if self._test_mode:
            self.stop_test()
            return
        self._test_mode = True
        self.play()

    def stop_test(self):
        """Ukonci drag rezim, ulozi poziciu a vrati klik-through."""
        if not self._test_mode:
            return
        self._save_test_position()
        self._test_mode = False
        self.stop()

    def _save_test_position(self):
        """Prepocita polohu okna spat na percenta monitora a ohlasi ju."""
        if self.surface is None or self.surface.top is None:
            return
        try:
            monitor = self.manager.target_monitor()
            x = self.surface.top.winfo_x()
            y = self.surface.top.winfo_y()
            # stred okna v percentach plochy monitora (rovnaka konvencia ako display.place)
            cx = x + self.w / 2.0
            cy = y + self.h / 2.0
            px = max(0.0, min(100.0, (cx - monitor.x) / monitor.width * 100.0))
            py = max(0.0, min(100.0, (cy - monitor.y) / monitor.height * 100.0))
            self.pos = (px, py)
            if callable(self.on_test_moved):
                self.on_test_moved(px, py)
        except Exception:
            pass

    def play(self):
        """Vykreslí vizuál. Vráti True pri úspechu, False pri zlyhaní.

        Chybové vetvy sa LOGUJÚ — doteraz ticho `_destroy(); return`, takže
        keď sa vizuál nevykreslil, nezostala po tom stopa a meranie ho aj tak
        rátalo ako platné (bug B17).
        """
        self.stop()
        self._gen += 1
        gen = self._gen
        try:
            self._build_window()
        except Exception:
            log.exception("in-game vizuál sa nepodarilo postaviť (slot %s)",
                          getattr(self, "index", "?"))
            self._destroy()
            return False
        self._static_done = False
        self._start_time = time.time()
        try:
            self._render(0.0)
        except Exception:
            log.exception("in-game vizuál sa nepodarilo vykresliť (slot %s)",
                          getattr(self, "index", "?"))
            self._destroy()
            return False
        self.surface.set_alpha(0.0)
        self.surface.show()
        if self._test_mode:
            self._enable_drag()
        self._fade(0.0, 1.0, self.FADE_MS, lambda: self._start_main(gen), gen)
        return True

    def _enable_drag(self):
        """V test rezime: vypni klik-through a nechaj okno tahat mysou."""
        if self.surface is None or self.surface.top is None:
            return
        self.surface.set_click_through(False)
        top = self.surface.top

        def _press(event):
            self._drag_origin = (event.x_root, event.y_root,
                                 top.winfo_x(), top.winfo_y())

        def _motion(event):
            if not self._drag_origin:
                return
            sx, sy, wx, wy = self._drag_origin
            top.geometry(f"+{wx + event.x_root - sx}+{wy + event.y_root - sy}")

        def _release(_event):
            self._drag_origin = None

        # bind na okno aj na jeho canvas/label (podla toho, cim LayeredSurface kresli)
        for target in (top,) + tuple(top.winfo_children()):
            try:
                target.bind("<ButtonPress-1>", _press, add="+")
                target.bind("<B1-Motion>", _motion, add="+")
                target.bind("<ButtonRelease-1>", _release, add="+")
                target.configure(cursor="fleur")
            except Exception:
                pass

    def stop(self):
        self._gen += 1
        if self._job is not None and self.surface is not None and self.surface.top:
            try:
                self.surface.top.after_cancel(self._job)
            except Exception:
                pass
        self._job = None
        self._destroy()

    # ---------- okno ----------

    def _build_window(self):
        monitor = self.manager.target_monitor()
        total = self.scale * monitor.scale
        self.w = max(48, int(round(self.base_w * total)))
        self.h = max(48, int(round(self.base_h * total)))
        x, y = display.place(monitor, self.w, self.h, self.pos[0], self.pos[1])
        self.surface = LayeredSurface(self.root)
        self.surface.create(x, y, self.w, self.h)
        # Na 4K su plochy 4x vacsie nez na 1080p; supersampling 3 by na
        # dychovom kruhu (prekresluje sa 25x za sekundu) uz zral vykon,
        # tak ho na velkych plochach znizime.
        self._ss = 2 if (self.w * self.h) > 240000 else 3

    def _destroy(self):
        if self.surface is not None:
            try:
                self.surface.destroy()
            except Exception:
                pass
        self.surface = None

    def _after(self, ms, fn):
        if self.surface is None or self.surface.top is None:
            return
        self._job = self.surface.top.after(ms, fn)

    def _fade(self, start, end, duration_ms, on_done, gen):
        steps = max(1, duration_ms // self.TICK_MS)

        def step(i):
            if gen != self._gen or self.surface is None:
                return
            self.surface.set_alpha(start + (end - start) * (i / steps))
            if i >= steps:
                on_done()
            else:
                self._after(self.TICK_MS, lambda: step(i + 1))

        step(0)

    def _start_main(self, gen):
        if gen != self._gen or self.surface is None:
            return
        self._start_time = time.time()
        self._tick(gen)

    def _tick(self, gen):
        if gen != self._gen or self.surface is None:
            return
        elapsed = time.time() - self._start_time
        try:
            finished = self._step(elapsed)
        except Exception:
            self._destroy()
            return
        if finished:
            self._fade(1.0, 0.0, self.FADE_MS,
                       lambda: self._on_fade_out_done(gen), gen)
            return
        self._after(self.TICK_MS, lambda: self._tick(gen))

    def _on_fade_out_done(self, gen):
        if gen == self._gen:
            self._destroy()

    # ---------- kreslenie ----------

    def _render(self, elapsed):
        style = self.manager.style
        if self.color:
            style = style.tinted(self.color)
        if self.visual == "breath":
            cycle = self.inhale_s + self.exhale_s
            t_in_cycle = elapsed % cycle
            inhale = t_in_cycle < self.inhale_s
            phase = (t_in_cycle / self.inhale_s if inhale
                     else (t_in_cycle - self.inhale_s) / self.exhale_s)
            image = hud_paint.render_breath(self.w, self.h, style, phase=phase,
                                            inhale=inhale,
                                            cycle_text=self.manager.breath_text(inhale),
                                            ss=self._ss)
        else:
            intro = self.INTRO_S.get(self.visual, 1.0)
            t = min(1.0, elapsed / intro) if intro else 1.0
            image = hud_paint.render_visual(self.visual, self.w, self.h, style,
                                            t=t, label=self._label, ss=self._ss)
        if self._test_mode:
            image = self._decorate_test(image, style)
        self.surface.draw(image)

    # Ram v test rezime: dlzka ciarky / medzery / odsadenie od hrany (px)
    TEST_DASH = 8
    TEST_GAP = 5
    TEST_INSET = 2

    def _decorate_test(self, image, style):
        """Upravi snimok pre drag rezim tak, aby sa dal CHYTIT KDEKOLVEK.

        Windows pusta mys cez pixely vrstveneho okna s alfou 0 (hit-test je
        per-pixel). Piktogram je vacsinou prazdny priestor - nazivo sa dalo
        okno chytit len na 3-10 % plochy, presne na nakreslenej ciare. Preto:

          1. kazdy pixel dostane alfu aspon 1 (opticky neviditelne, ale
             pre hit-test "plne"), takze drzi cela plocha okna;
          2. jemny prerusovany ram ukaze, kde ma okno hranu a co hrac drzi.

        Mimo test rezimu sa nic z toho nekresli - v hre ostava okno presne
        take, ake bolo (a klik-through).
        """
        if image is None or ImageDraw is None:
            return image
        try:
            img = image if image.mode == "RGBA" else image.convert("RGBA")
            alpha = img.getchannel("A").point(lambda v: 1 if v < 1 else v)
            img.putalpha(alpha)
            w, h = img.size
            d = ImageDraw.Draw(img)
            color = tuple(style.accent) + (96,)
            i = self.TEST_INSET
            self._dashed_rect(d, i, i, w - 1 - i, h - 1 - i, color)
            return img
        except Exception:
            return image

    def _dashed_rect(self, d, x0, y0, x1, y1, color):
        dash, gap = self.TEST_DASH, self.TEST_GAP
        for (ax, ay, bx, by) in ((x0, y0, x1, y0), (x0, y1, x1, y1),
                                 (x0, y0, x0, y1), (x1, y0, x1, y1)):
            horizontal = ay == by
            length = (bx - ax) if horizontal else (by - ay)
            pos = 0
            while pos < length:
                end = min(pos + dash, length)
                if horizontal:
                    d.line([(ax + pos, ay), (ax + end, ay)], fill=color, width=1)
                else:
                    d.line([(ax, ay + pos), (ax, ay + end)], fill=color, width=1)
                pos = end + gap

    def _step(self, elapsed):
        if self.visual == "breath":
            # v test rezime dycha dookola (hrac si polohu doladuje),
            # inak 2 cykly a koniec
            if not self._test_mode and elapsed >= self.CYCLES * (self.inhale_s + self.exhale_s):
                return True
            self._render(elapsed)
            return False

        intro = self.INTRO_S.get(self.visual, 1.0)
        if elapsed <= intro + 0.05:
            self._render(elapsed)
        elif not self._static_done:
            # animacia dobehla - dokreslime koncovy stav raz a dalej uz
            # okno len visi na obrazovke bez jedineho prekreslenia
            self._render(intro)
            self._static_done = True
        # v test rezime NIKDY nekonci sam - visi kym hrac test nevypne
        if self._test_mode:
            return False
        return elapsed >= self.HOLD_S


class SomaticOverlayManager:
    """Spravca 4 nezavislych in-game vizualov.

    Drzi spolocny farebny styl (podla temy appky), cielovy monitor a
    popisky - jednotlive `_SlotOverlay` si od neho beru vsetko spolocne,
    aby sa pri zmene temy/jazyka/monitora nemuselo prechadzat styri
    objekty.
    """

    VISUALS = ("grounding", "jaw", "release", "breath")

    # Rozmery su v 1080p pixeloch - nasobia sa Monitor.scale.
    BASE_SIZES = {
        "grounding": (240, 160),
        "jaw": (170, 175),
        "release": (170, 155),
        "breath": (170, 170),
    }

    def __init__(self, root, color="#00d2ff", danger_color="#ff5c73", pal=None):
        self.root = root
        self.style = Style(pal or {"accent": color, "danger": danger_color})
        self.monitor_target = display.TARGET_AUTO
        self._labels = {}
        self._breath_labels = ("", "")
        self._monitor_cache = (0.0, None)
        self._slots = [_SlotOverlay(root, visual, self.BASE_SIZES[visual], self)
                       for visual in self.VISUALS]
        for i, overlay in enumerate(self._slots):
            overlay.pos = OVERLAY_DEFAULT_POS.get(i, (50.0, 50.0))

    # ---------- spolocny stav ----------

    def set_palette(self, pal):
        self.style = Style(pal)

    def set_colors(self, color, danger_color):
        """Zachovane kvoli spatnej kompatibilite s app.py."""
        self.style = Style({"accent": color, "danger": danger_color})

    def set_labels(self, labels, breath_inhale="", breath_exhale=""):
        """`labels` je {index: text} - popisok pod vizualom."""
        self._labels = labels or {}
        self._breath_labels = (breath_inhale, breath_exhale)
        for i, overlay in enumerate(self._slots):
            overlay.set_label(self._labels.get(i))

    def breath_text(self, inhale):
        return self._breath_labels[0] if inhale else self._breath_labels[1]

    def set_breath_seconds(self, inhale_s, exhale_s):
        """Dlzka nadychu/vydychu (v sekundach) pre dychovy kruh - hrac ju
        meni v Nastaveniach (viz app.py on_breath_seconds_change)."""
        for overlay in self._slots:
            if overlay.visual == "breath":
                overlay.set_breath_seconds(inhale_s, exhale_s)

    def set_monitor_target(self, target):
        self.monitor_target = target or display.TARGET_AUTO
        self._monitor_cache = (0.0, None)

    def target_monitor(self):
        """Cielovy monitor s kratkou cache.

        Enumeracia monitorov je lacna, ale nie zadarmo, a pri spusteni
        vizualu je to na GUI vlakne. Sekundova cache staci - monitory sa
        pocas jednej sekundy neprepajaju.
        """
        now = time.time()
        if self._monitor_cache[1] is not None and now - self._monitor_cache[0] < 1.0:
            return self._monitor_cache[1]
        monitor = display.resolve_target(self.monitor_target, self.root)
        self._monitor_cache = (now, monitor)
        return monitor

    # ---------- ovladanie slotov ----------

    def configure(self, index, enabled=None, scale=None, pos=None, color=None):
        if 0 <= index < len(self._slots):
            self._slots[index].configure(enabled=enabled, scale=scale, pos=pos,
                                         color=color)

    def trigger(self, index):
        """Vráti True, ak sa vizuál slotu naozaj začal kresliť (viz
        `_SlotOverlay.trigger`). Neplatný index = nič sa nevykreslilo."""
        if 0 <= index < len(self._slots):
            return bool(self._slots[index].trigger())
        return False

    def is_active(self, index):
        if 0 <= index < len(self._slots):
            return self._slots[index].is_active
        return False

    def test(self, index):
        """Prepne drag-test rezim slotu. Vrati True ak je PO volani zapnuty
        (vizual je na obrazovke a da sa tahat), False ak sa prave vypol."""
        if 0 <= index < len(self._slots):
            # ak bezi test ineho slotu, najprv ho vypni - dva perzistentne
            # test-vizualy naraz by sa prekryvali a mietli
            for i, ov in enumerate(self._slots):
                if i != index and ov._test_mode:
                    ov.stop_test()
            self._slots[index].test()
            return self._slots[index]._test_mode
        return False

    def stop_test(self, index):
        if 0 <= index < len(self._slots):
            self._slots[index].stop_test()

    def is_testing(self, index):
        if 0 <= index < len(self._slots):
            return self._slots[index]._test_mode
        return False

    def set_test_moved_callback(self, index, callback):
        """Nastavi callback(px, py), ktory sa zavola pri ukonceni testu s
        novou polohou vizualu (v percentach monitora) - app si ju ulozi."""
        if 0 <= index < len(self._slots):
            self._slots[index].on_test_moved = callback

    def stop_all(self):
        for overlay in self._slots:
            overlay.stop_test()
            overlay.stop()

    def stop_all_tests(self):
        """Ukonci VSETKY drag-testy a vrati klik-through.

        PRECO TO MA VLASTNU METODU: test rezim vypina klik-through
        (`_enable_drag` -> `set_click_through(False)`), takze vizual nad hrou
        pohlcuje kliky mysou - a sam od seba nikdy neskonci (`_step` v test
        rezime vracia False navzdy). Kto klikol Test a zabudol, mal uprostred
        obrazovky nekliknutelnu plochu a nemal ako zistit preco.

        Vracia pocet ukoncenych testov, aby volajuci vedel, ci ma o tom
        povedat hracovi.
        """
        ukoncene = 0
        for overlay in self._slots:
            if overlay._test_mode:
                overlay.stop_test()
                ukoncene += 1
        return ukoncene
