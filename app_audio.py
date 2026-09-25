"""Zvuk a hlasy - cast hlavnej appky (DandurfApp z app.py).

AudioMixin je mixin DandurfApp: app.py ho dedi a cely stav (motor TTS,
hlasy, rychlost, hlasitost, cache Edge hlasok, sloty, prehravac) zije na
DandurfApp. Tu su len metody, ktore s nim pracuju cez `self` - mixin nema
__init__ ani vlastne atributy.

Pat sekcii presunutych z app.py bez zmeny:
  * SFX kniznica - priprava zabudovanych zvukov a pas s priebehom,
  * hlasitost (master + vyvazenie SFX/hlas) - efektivna hlasitost SFX a
    hlasu; sekcia nesie aj `_apply_diagnostics` (ktore sloty zapnut podla
    diagnostiky z onboardingu), ktora v nej bola uz v app.py,
  * hlasy - zoznamy hlasov SAPI / Edge, vyber motora, hlasu a rychlosti,
  * predgenerovanie Edge hlasok - priprava hlasok do cache dopredu (len
    tych, ktore v hre naozaj povie prirodzeny hlas; pocas pocuvania sa
    odklada na po hre),
  * rozhodovanie o SFX subore - ktory zvuk slot zahra a samotne prehratie
    slotu (`_emit`, `_speak_text`, vlastna nahravka hlasu).

Pozor v testoch: `pregenerate`, `_prune_cache`, `_play_concurrent`,
`_play_voice_file` a `_speak_text` citaju `threading` z tohto modulu -
nahrada celeho modulu `threading` na module app ich nezasiahne (treba
`app_audio.threading`). Zmena atributu zdielaneho modulu
(`app.threading.Thread`, `audio_engine.EDGE_AVAILABLE`) plati aj tu.
"""

import os
import threading
from tkinter import messagebox

import customtkinter as ctk

import audio_engine
import rebrik
import sfx_assets
import theme as theme_mod
from audio_engine import EdgeTTSCache, speak_sapi_isolated
from i18n import tr
from paths import APP_NAME
from settings_model import (DEFAULT_EDGE_VOICE, ENGINE_EDGE, ENGINE_SAPI,
                            MODE_COMBO, MODE_SFX, MODE_TTS,
                            engine_labels, je_kategoria, label_to_engine)


class AudioMixin:
    """Zvuky, hlasy, priprava Edge hlasok a prehratie slotu (mixin DandurfApp)."""

    # ---------- SFX kniznica ----------

    def _ensure_sfx_assets(self):
        def progress(done, total):
            self.ui_call(lambda: self._update_assets_progress(done, total))
        sfx_assets.ensure_assets(log=self.log_threadsafe, progress=progress)

    def show_assets_progress(self):
        """Maly nenapadny prúžok v hornej casti okna - len ked naozaj
        chybaju SFX subory (napr. po precistení %APPDATA%)."""
        if self._assets_progress_frame is not None:
            return
        pal = self.pal
        frame = ctk.CTkFrame(self.main, fg_color=pal["surface_alt"], corner_radius=10)
        frame.pack(fill="x", padx=20, pady=(0, 8), before=self.main_grid)
        ctk.CTkLabel(frame, text=tr("assets.preparing"), text_color=pal["text"],
                    font=("Segoe UI", 11)).pack(side="left", padx=14, pady=10)
        bar = ctk.CTkProgressBar(frame, width=160, progress_color=pal["accent"])
        bar.set(0.0)
        bar.pack(side="right", padx=14, pady=10)
        self._assets_progress_frame = frame
        self._assets_progress_bar = bar

    def _update_assets_progress(self, done, total):
        if total <= 0:
            return
        if self._assets_progress_bar is not None:
            try:
                self._assets_progress_bar.set(done / total)
            except Exception:
                pass
        if done >= total and self._assets_progress_frame is not None:
            self.root.after(600, self._hide_assets_progress)

    def _hide_assets_progress(self):
        if self._assets_progress_frame is not None:
            try:
                self._assets_progress_frame.destroy()
            except Exception:
                pass
            self._assets_progress_frame = None
            self._assets_progress_bar = None

    # ---------- hlasitost (master + vyvazenie SFX/hlas) ----------

    def _recompute_volumes(self):
        """Master hlasitost + posuvnik Vyvazenie -> samostatna efektivna
        hlasitost pre SFX a pre hlas (TTS), obe v rozsahu 0-100.

        balance 50 = obe na plnej masterovej hlasitosti; 0 = len SFX
        (hlas stiseny), 100 = len hlas (SFX stiseny)."""
        master = self.volume_value
        balance = self.balance_value
        sfx_mult = min(1.0, (100 - balance) / 50.0)
        tts_mult = min(1.0, balance / 50.0)
        self.sfx_volume = round(master * sfx_mult)
        self.tts_volume = round(master * tts_mult)

    def _apply_diagnostics(self, settings, diagnostics):
        """Diagnostika herneho tiena (Onboarding krok 2) rozhoduje, ktore
        zo 4 uz pripravenych zakladnych slotov (data/klavesy/hlasky/zvuky
        su vzdy rovnake) su po onboardingu ZAPNUTE. Zaskrtnuty symptom ->
        prislusny slot ostava enabled=True (predvolene z DEFAULT_SLOT);
        nezaskrtnuty -> slot sa vypne (enabled=False), ale zostava v
        zozname pripraveny - pouzivatel si ho kedykolvek sam zapne."""
        if not diagnostics:
            return
        try:
            slots = settings["profiles"][0]["slots"]
        except (KeyError, IndexError):
            return
        # diagnostika 0 = zovreta ruka/trasenie pri mierení -> slot 2
        # (Release), 1 = zatate zuby/celust -> slot 1 (Jaw), 2 =
        # predklananie/nestabilita -> slot 0 (Grounded), 3 = zadrziavanie
        # dychu/panika -> slot 3 (Breathe).
        mapping = {0: 2, 1: 1, 2: 0, 3: 3}
        for diag_index, slot_index in mapping.items():
            if slot_index < len(slots):
                slots[slot_index]["enabled"] = bool(diagnostics.get(diag_index, True))

    # ---------- hlasy ----------

    def on_voices_ready(self, items):
        self.ui_call(lambda: self._apply_sapi_voices(items))

    def _apply_sapi_voices(self, items):
        self.voice_map = {name: vid for vid, name in items}
        if not self.saved_voice_id and items:
            self.saved_voice_id = items[0][0]
        if self.saved_voice_id:
            self.worker.set_voice(self.saved_voice_id)
        if self.engine == ENGINE_SAPI:
            self.refresh_voice_box()
        self.refresh_slot_summaries()

    def _load_edge_voices(self, pregen=True):
        """Naplni vyber Edge hlasov z pevneho zoznamu - bez siete, takze
        priamo na Tk vlakne (predtym vlakno + stiahnutie katalogu)."""
        self._apply_edge_voices(EdgeTTSCache.list_voices(), pregen=pregen)

    def _apply_edge_voices(self, items, pregen=True):
        self.edge_voice_map = {name: short for short, name in items}
        known = set(self.edge_voice_map.values())
        if self.edge_voice_id not in known:
            self.edge_voice_id = (DEFAULT_EDGE_VOICE if DEFAULT_EDGE_VOICE in known
                                  else (items[0][0] if items else DEFAULT_EDGE_VOICE))
        if self.engine == ENGINE_EDGE:
            self.refresh_voice_box()
            if pregen:
                self.pregenerate()
        self.refresh_slot_summaries()

    def current_voice_map(self):
        return (self.edge_voice_map if self.engine == ENGINE_EDGE
                else self.voice_map)

    def current_voice_names(self):
        return list(self.current_voice_map().keys())

    def voice_id_for_label(self, label):
        return self.current_voice_map().get(label, "")

    def slot_voice_label(self, slot):
        vid = slot.voice_edge if self.engine == ENGINE_EDGE else slot.voice_sapi
        if not vid:
            return ""
        for label, candidate in self.current_voice_map().items():
            if candidate == vid:
                return label
        return vid

    def set_slot_voice(self, slot, voice_id):
        if self.engine == ENGINE_EDGE:
            slot.voice_edge = voice_id
        else:
            slot.voice_sapi = voice_id

    def refresh_slot_summaries(self):
        for slot in self.slots:
            slot.refresh_summary()

    def refresh_voice_box(self):
        mapping = self.current_voice_map()
        current = (self.edge_voice_id if self.engine == ENGINE_EDGE
                   else self.saved_voice_id)
        names = list(mapping.keys())
        self.voice_box.configure(values=names or [tr("voice.none")])
        label = next((n for n, vid in mapping.items() if vid == current), None)
        if label is None and names:
            label = names[0]
        if label:
            self.voice_var.set(label)
            if self.engine == ENGINE_EDGE:
                self.edge_voice_id = mapping[label]
            else:
                self.saved_voice_id = mapping[label]
                self.worker.set_voice(self.saved_voice_id)
        elif not names:
            self.voice_var.set(tr("voice.loading"))

    def on_engine_change(self):
        engine = label_to_engine().get(self.engine_var.get(), ENGINE_SAPI)
        if engine == ENGINE_EDGE and not audio_engine.EDGE_AVAILABLE:
            self.engine_pref = ENGINE_EDGE
            self.engine_var.set(engine_labels()[ENGINE_SAPI])
            self.save_settings()
            self.refresh_edge_banner()
            messagebox.showwarning(APP_NAME, tr("msgbox.edge_missing_body"))
            return
        if engine == self.engine:
            return
        self.engine = self.engine_pref = engine
        self.refresh_edge_banner()
        self.refresh_voice_box()
        self.refresh_slot_summaries()
        self.save_settings()
        self.log(tr("log.engine_switched", engine=engine_labels()[engine]))
        if engine == ENGINE_EDGE:
            # Poistka: vyber Edge hlasov sa plni pri starte (bez siete); keby
            # bol prazdny, naplni sa teraz - inak by bol combobox prazdny.
            if not getattr(self, "edge_voice_map", None):
                self._load_edge_voices(pregen=False)
            self.pregenerate()
        else:
            # Kto prepol na hlas z Windows, nechce nic posielat Microsoftu -
            # ani zvysok pripravy, ktora prave bezi. Doteraz dobehla cela.
            self._zrus_rozbehnutu_pripravu()
            self.set_edge_status("")

    def on_voice_change(self):
        label = self.voice_var.get()
        vid = self.current_voice_map().get(label)
        if not vid:
            return
        if self.engine == ENGINE_EDGE:
            self.edge_voice_id = vid
            self.save_settings()
            self.pregenerate()
        else:
            self.saved_voice_id = vid
            self.worker.set_voice(vid)
            self.save_settings()

    def on_rate_change(self):
        self.rate_value = int(self.rate_var.get())
        self.audio.rate = self.rate_value
        self.worker.set_rate(self.rate_value)
        label = getattr(self, "rate_value_label", None)
        if label is not None:
            try:
                label.configure(text=self._rate_label_text())
            except Exception:
                pass
        self.save_settings()
        if self.engine == ENGINE_EDGE:
            self.schedule_pregenerate()

    # ---------- predgenerovanie Edge hlasok ----------

    def set_edge_status(self, text, color=None):
        if self.edge_status_label is not None:
            try:
                self.edge_status_label.configure(text=text,
                                                 text_color=color or self.pal["text_dim"])
            except Exception:
                pass

    def _hlasky_hovoria(self):
        """Povie hlaska v hre vobec nieco hlasom (TTS)? Len v style "hlas"
        a mimo sveta Praca - tam ide len obrazom (`rebrik.vrchol`). Styl
        "zvuk" hra zvuk slotu bez slov a "obraz" len obrazok."""
        styl = rebrik.normalize_cue_style(getattr(self, "cue_style", None))
        return (styl == rebrik.STYL_HLAS
                and rebrik.vrchol(getattr(self, "world", None), styl) == rebrik.HLAS)

    def _slot_na_pripravu(self, slot):
        """Moze text tejto hlasky v hre naozaj povedat prirodzeny hlas?

        Len vtedy sa smie poslat Microsoftu na pripravu. Doteraz sa posielali
        texty vsetkych slotov s hlasom, aj tych, ktore Edge nikdy nevyslovi:
          * vypnutej hlasky - `_dalsi_cue_slot` ju v hre preskakuje,
          * hlasky s vypnutym obrazkom v hre - `_dalsi_cue_slot` ju
            preskakuje tiez (ta ista podmienka, `_ma_obrazok_v_hre`); jej
            text isiel Microsoftu, hoci ho v hre nikdy nepovie,
          * hlasky s vlastnou nahravkou - `_speak_text` prehra nahravku,
            nie TTS (ta ista podmienka ako tam, `_slot_voice_clip`),
          * slotu navyse z 0.1 (index 4+, "+ Pridat spustac") - nema
            kategoriu ani obrazok a appka ho sama nespusta
            (`settings_model.je_kategoria`).
        Ked sa hlaska alebo jej obrazok neskor zapne, alebo sa jej zmaze
        nahravka, pripravu znova spusti ta zmena (`schedule_pregenerate`).
        """
        return bool(
            je_kategoria(slot.index)
            and slot.enabled_value
            and self._ma_obrazok_v_hre(slot)
            and slot.mode in (MODE_TTS, MODE_COMBO)
            and slot.text_value.strip()
            and not self._slot_voice_clip(slot))

    def pregen_jobs(self):
        """[(text, hlas)] pre hlasky, ktore v hre povie prirodzeny hlas
        (`_slot_na_pripravu`) - respektuje hlas kazdeho slotu.

        Prazdne, ked hlasky v hre nehovoria (`_hlasky_hovoria`): hracovi,
        ktory zvolil len obrazok alebo zvuk bez slov, alebo je vo svete
        Praca, by sa inak texty hlasok posielali do Microsoftu zbytocne.
        """
        if not self._hlasky_hovoria():
            return []
        jobs = []
        for slot in self.slots:
            if not self._slot_na_pripravu(slot):
                continue
            voice = slot.voice_edge or self.edge_voice_id
            pair = (slot.text_value, voice)
            if pair not in jobs:
                jobs.append(pair)
        return jobs

    def _zrus_rozbehnutu_pripravu(self):
        """Zvysok rozbehnutej pripravy uz na siet nepojde.

        Vlakno pripravy (`work` v `pregenerate`) sa na svoje `seq` pyta pred
        kazdou dalsou hlaskou aj tesne pred odoslanim (`abort` po ziskani
        zamku cache). Hlaska, ktora uz leti, dobehne - dalsia sa nezacne.
        Rovnako ako ked sa zapne pocuvanie.
        """
        self._pregen_seq += 1

    def schedule_pregenerate(self, delay_ms=700):
        # Kazda zmena, ktora pripravu planuje (hlaska vypnuta, styl bez slov,
        # svet Praca, iny text/hlas/rychlost...), meni aj to, co sa smie
        # poslat. Stara priprava preto konci HNED, nie az po `delay_ms` -
        # za ten cas by mohla zacat posielat hlasku, ktora uz nezaznie.
        # Nova priprava si po odklade zisti, co este chyba (hotove hlasky
        # su v cache a na siet nejdu).
        self._zrus_rozbehnutu_pripravu()
        if self.engine != ENGINE_EDGE:
            return
        if self._pregen_job is not None:
            try:
                self.root.after_cancel(self._pregen_job)
            except Exception:
                pass
        self._pregen_job = self.root.after(delay_ms, self.pregenerate)

    def pregenerate(self, force=False):
        self._pregen_job = None
        # Kazde volanie zacina odznova - aj ked vyjde, ze netreba nic (iny
        # motor, styl bez slov, Praca, vsetky hlasky vypnute). Doteraz sa
        # `seq` zvysoval az pri neprazdnom zozname, takze priprava rozbehnuta
        # predtym dobehla cela, hoci jej hlasky uz nemali zazniet.
        self._zrus_rozbehnutu_pripravu()
        seq = self._pregen_seq
        if self.engine != ENGINE_EDGE or not audio_engine.EDGE_AVAILABLE:
            return
        rate = self.rate_value
        jobs = self.pregen_jobs()
        if not jobs:
            self.set_edge_status("")
            return

        if not force and all(self.edge_cache.has(t, v, rate) for t, v in jobs):
            self.set_edge_status(tr("edge.ready"), self.pal["success"])
            self._prune_cache(jobs, rate)
            return

        if getattr(self, "listening", False):
            # POCAS POCUVANIA SA NA MICROSOFT NECHODI - ani kvoli priprave.
            # Auto-profil prepne profil hry pri jej starte (`_handle_game_found`
            # -> `switch_profile` -> `schedule_pregenerate`) a pocuvanie sa
            # zapne hned za tym, takze priprava by inak isla na siet presne
            # vtedy, ked sa hra nacitava. Rovnako rucne prepnutie profilu alebo
            # zmena hlasu uprostred hry. Priprava sa odlozi a spusti ju az
            # `stop_listening` (`_dopriprav_hlasky_po_hre`) - ten isty
            # mechanizmus ako pre hlasku, ktora v hre chybala (`_speak_text`).
            # `_pregen_seq` vyssie uz zastavil pripadnu rozbehnutu pripravu.
            self._pregen_po_hre = True
            self.set_edge_status(tr("edge.after_game"), self.pal["text_dim"])
            return

        self.set_edge_status(tr("edge.generating"), self.pal["warn"])

        def work():
            ok = 0
            for text, voice in jobs:
                if seq != self._pregen_seq:
                    return
                if getattr(self, "listening", False):
                    # Pocuvanie sa zaplo uprostred pripravy: dalsia hlaska uz
                    # na siet nejde. O zvysku rozhodne `pregenerate` na
                    # GUI vlakne - pocas pocuvania ho odlozi na po hre.
                    self.ui_call(self.pregenerate)
                    return
                # Kontrola vyssie nestaci: `ensure` moze cakat na zamku cache,
                # kym ine (starsie) vlakno pripravy dokonci svoju hlasku - a
                # medzitym sa moze zapnut pocuvanie. `abort` sa preto pyta
                # znova az po ziskani zamku, tesne pred odoslanim.
                if self.edge_cache.ensure(
                        text, voice, rate,
                        abort=lambda: (seq != self._pregen_seq
                                       or getattr(self, "listening", False))):
                    ok += 1
            if seq != self._pregen_seq:
                return
            total = len(jobs)
            if ok < total and getattr(self, "listening", False):
                # Posledna hlaska sa vzdala na zamku, lebo sa zaplo pocuvanie
                # (alebo zlyhala a hra uz bezi) - nie je to chyba pripravy,
                # zvysok odlozi `pregenerate` na po hre.
                self.ui_call(self.pregenerate)
                return
            if ok == total:
                self.ui_call(lambda: self.set_edge_status(
                    tr("edge.ready"), self.pal["success"]))
                self.log_threadsafe(tr("log.edge_cache_ready", n=ok))
                self.ui_call(lambda: self._prune_cache(jobs, rate))
            else:
                self.ui_call(lambda: self.set_edge_status(
                    tr("edge.partial", ok=ok, total=total), self.pal["danger"]))

        threading.Thread(target=work, daemon=True).start()

    def _prune_cache(self, jobs, rate):
        keep = [self.edge_cache.path_for(t, v, rate) for t, v in jobs]
        threading.Thread(target=lambda: EdgeTTSCache.prune(keep),
                         daemon=True).start()

    # ---------- rozhodovanie o SFX subore ----------

    def resolve_sfx_path(self, slot):
        key = slot.sfx_key
        if key == "__custom__":
            return slot.audio_path if slot.audio_path and os.path.exists(slot.audio_path) \
                else None
        if key and ":" in key:
            pack, sound_key = key.split(":", 1)
            return sfx_assets.sound_path(pack, sound_key)
        if not key and slot.audio_path:
            return slot.audio_path if os.path.exists(slot.audio_path) else None
        # Predvolena sada ide za vzhladom - ale pocas relacie za SVETOM
        # RELACIE (B3-worlds): kto si uprostred hry len pozrie Pracu, nema
        # od dalsej hlasky pocut zvuky druheho sveta.
        pack = self.theme_key
        if getattr(self, "_hr_session_open", False):
            pack = theme_mod.WORLD_THEME.get(
                getattr(self, "_session_world", None), pack)
        default_key = sfx_assets.default_sound_for_slot_index(pack, slot.index)
        if not default_key:
            items = sfx_assets.library_items(pack)
            default_key = items[0][0] if items else None
        return sfx_assets.sound_path(pack, default_key) if default_key else None

    def _play_concurrent(self, path, volume):
        threading.Thread(target=self._play_now_safe, args=(path, volume), daemon=True).start()

    def _play_now_safe(self, path, volume):
        try:
            audio_engine.play_audio_file(path, volume)
        except Exception as exc:
            self.log_threadsafe(tr("log.sfx_playback_error", err=exc))

    def _play_voice_file(self, path):
        """Prehra VLASTNU nahravku hlasu - hlasitostou TTS a bez notch filtra
        (2-4 kHz), aby znela cela a zrozumitelna ako vlastny hlas. Vzdy vo
        vlastnom vlakne (subezne), rovnako ako SFX v kombinacii."""
        threading.Thread(target=self._voice_now_safe, args=(path,), daemon=True).start()

    def _voice_now_safe(self, path):
        try:
            audio_engine.play_audio_file(path, self.tts_volume, notch=False)
        except Exception as exc:
            self.log_threadsafe(tr("log.sfx_playback_error", err=exc))

    def _slot_voice_clip(self, slot):
        """Cesta k platnej vlastnej nahravke hlasu slotu, alebo None."""
        vp = getattr(slot, "voice_path", "")
        return vp if vp and os.path.exists(vp) else None

    def _slot_has_voice(self, slot):
        """Ma slot co povedat hlasom? Bud napisany text, alebo nahravka.
        Vdaka tomu sa nahravka prehra aj ked je textove pole prazdne."""
        return bool(slot.text_value.strip() or self._slot_voice_clip(slot))

    def _speak_text(self, text, slot, concurrent=False):
        # Vlastna nahravka hlasu ma prednost pred TTS: ak si clovek nahral
        # svoj hlas, prehra sa on - nie strojovy prevod textu.
        clip = self._slot_voice_clip(slot)
        if clip:
            self._play_voice_file(clip)
            return
        if self.engine == ENGINE_EDGE and audio_engine.EDGE_AVAILABLE:
            voice = slot.voice_edge or self.edge_voice_id
            if self.edge_cache.has(text, voice, self.rate_value):
                path = self.edge_cache.path_for(text, voice, self.rate_value)
                if concurrent:
                    self._play_concurrent(path, self.tts_volume)
                else:
                    self.audio.play_tts(path)
                return
            if not self._hlasky_hovoria() or not self._slot_na_pripravu(slot):
                # Styl bez slov / svet Praca, alebo hlaska, ktoru v hre Edge
                # nepovie (vypnuta, s vypnutym obrazkom v hre, slot navyse
                # z 0.1): nic sa pre nu
                # nepripravuje (`pregen_jobs`) - Test/ukazka zaznie cez SAPI
                # a dennik neslubuje pripravu, ktora nepride.
                pass
            elif getattr(self, "listening", False):
                # Pocas hry sa na Microsoft nechodi: hlaska zaznie hlasom
                # z Windows a dopripravi sa po `stop_listening`.
                self._pregen_po_hre = True
                self.log_threadsafe(tr("log.edge_not_cached_later"))
            else:
                self.log_threadsafe(tr("log.edge_not_cached"))
                self.ui_call(self.pregenerate)

        voice_id = slot.voice_sapi or self.saved_voice_id
        if concurrent:
            threading.Thread(target=speak_sapi_isolated,
                             args=(text, voice_id, self.rate_value, self.tts_volume),
                             daemon=True).start()
        else:
            self.audio.speak(text, voice_id)

    def _slot_zaznie(self, slot, bez_slov=False):
        """Zaznie z `_emit(slot, bez_slov)` vobec nieco? Rovnake vetvy ako
        `_emit`, len bez prehravania - pre `audible` v zazname hlasky (graf
        ucinnosti rata len hlasky, ktore naozaj zazneli)."""
        mode = slot.mode
        sfx_path = self.resolve_sfx_path(slot) if mode in (MODE_SFX, MODE_COMBO) else None
        zvuk = bool(sfx_path and os.path.exists(sfx_path))
        if bez_slov or mode == MODE_SFX:
            # V rezime SFX `_emit` text nema (`text` je len pre TTS/COMBO),
            # takze bez suboru nezaznie nic.
            return zvuk
        if mode == MODE_COMBO:
            return zvuk or self._slot_has_voice(slot)
        return self._slot_has_voice(slot)

    def _emit(self, slot, bez_slov=False):
        """Prehra slot. `bez_slov=True` (styl hlasky "zvuk", `rebrik.py`)
        zahra LEN zvuk slotu - ziadne TTS, ziadnu vlastnu nahravku, ani ako
        zalohu za chybajuci zvuk. Slot bez zvuku potom mlci."""
        mode = slot.mode
        sfx_path = self.resolve_sfx_path(slot) if mode in (MODE_SFX, MODE_COMBO) else None
        text = slot.text_value if mode in (MODE_TTS, MODE_COMBO) else ""

        if bez_slov:
            if sfx_path and os.path.exists(sfx_path):
                self.audio.play(sfx_path)
            elif sfx_path:
                self.log_threadsafe(tr("log.slot_sfx_missing_plain", n=slot.index + 1))
            return

        if mode == MODE_COMBO:
            played_sfx = False
            if sfx_path and os.path.exists(sfx_path):
                self._play_concurrent(sfx_path, self.sfx_volume)
                played_sfx = True
            elif sfx_path:
                self.log_threadsafe(tr("log.slot_sfx_missing", n=slot.index + 1,
                                       name=os.path.basename(sfx_path)))
            if self._slot_has_voice(slot):
                # Kombinacia hraje vzdy subezne (naraz) - bez ohladu na globalny
                # prepinac "cez seba", inak by SFX+TTS zneli za sebou. `_speak_text`
                # sam rozhodne, ci povie text (TTS) alebo prehra vlastnu nahravku.
                self._speak_text(text, slot, concurrent=played_sfx)
            return

        if mode == MODE_SFX:
            if sfx_path and os.path.exists(sfx_path):
                self.audio.play(sfx_path)
                return
            if sfx_path:
                key = "log.slot_sfx_missing_fallback" if text.strip() \
                    else "log.slot_sfx_missing_plain"
                self.log_threadsafe(tr(key, n=slot.index + 1))
            if text.strip():
                self._speak_text(text, slot)
            return

        if self._slot_has_voice(slot):
            self._speak_text(text, slot)
