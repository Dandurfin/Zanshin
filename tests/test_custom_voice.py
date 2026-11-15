"""Custom voice (recording) instead of TTS + recording-saving fixes (B1-B3).

Without Tk/pygame - just like test_overlay_features.py, the API contract
and the source are checked. The data part (DEFAULT_SLOT, normalize_slot)
is also checked directly in test_settings_model.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import settings_model as sm  # noqa: E402
from _zdroj_appky import zdroj_metody  # noqa: E402


def _read(name):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, name), encoding="utf-8-sig") as fh:
        return fh.read()


# ---- data model ----------------------------------------------------------

def test_default_slot_ma_voice_path_a_uid():
    assert "voice_path" in sm.DEFAULT_SLOT
    assert "uid" in sm.DEFAULT_SLOT


# ---- playback: the recording goes before TTS and plays clean ------------

def test_speak_text_skusa_nahravku_pred_tts():
    # playback (`_speak_text`) and its mirror for the record (`_slot_zaznie`)
    telo = zdroj_metody("_speak_text") + "\n" + zdroj_metody("_slot_zaznie")
    assert "_slot_voice_clip" in telo, "nahravka sa nekontroluje"
    # the recording must be resolved before TTS (the Edge/SAPI branch)
    assert telo.index("_play_voice_file") < telo.index("EDGE_AVAILABLE"), \
        "vlastna nahravka ma mat prednost pred TTS"


def test_vlastny_hlas_hraje_bez_footstep_notch():
    vn = zdroj_metody("_voice_now_safe")
    assert "notch=False" in vn, "vlastny hlas ma hrat cisto (notch=False)"


def test_play_audio_file_ma_prepinac_notch():
    audio = _read("audio_engine.py")
    assert "def play_audio_file(path, volume=100, notch=True)" in audio
    hlava = audio[audio.index("def play_audio_file"):]
    hlava = hlava[:hlava.index("\n\n\n")]
    assert "if notch:" in hlava, "notch sa ma dat vypnut, nie aplikovat vzdy"


def test_emit_pusti_hlas_aj_bez_textu_ak_je_nahravka():
    emit = zdroj_metody("_emit")
    # COMBO and the pure TTS branch ask _slot_has_voice, not just text.strip()
    assert emit.count("_slot_has_voice(slot)") >= 2, \
        "nahravka s prazdnym textom by sa inak neprehrala"


# ---- B1: recording names by a stable uid, not by order -------------------

def test_b1_nahravka_ma_meno_podla_uid():
    dialogs = _read("ui_dialogs.py")
    assert "slot{self.index + 1}.wav" not in dialogs, \
        "meno podla poradia sa krizilo medzi profilmi (B1)"
    assert "rec_{self.uid}.wav" in dialogs
    assert "voice_{self.slot.uid}.wav" in dialogs


# ---- B2: the chosen file is copied into the audio/ folder ----------------

def test_b2_vybrany_subor_sa_kopiruje_do_ulozne():
    dialogs = _read("ui_dialogs.py")
    assert "def _import_into_store" in dialogs
    assert "shutil.copy2" in dialogs
    cf = dialogs[dialogs.index("    def choose_file(self"):dialogs.index("    def record_audio")]
    assert "self._import_into_store" in cf, \
        "choose_file uz nesmie drzat cudziu cestu tak ako je (B2)"


# ---- B3: saving a recording is atomic ------------------------------------

def test_b3_stop_and_save_je_atomicke():
    audio = _read("audio_engine.py")
    sas = audio[audio.index("    def stop_and_save(self"):audio.index("    def cancel(self")]
    # `nahrad_subor` = os.replace with a retry on a short lock (paths.py)
    assert ".part" in sas and "nahrad_subor(" in sas, \
        "nahravka sa ma ulozit najprv do .part a atomicky presunut (B3)"


# ---- serialisation -------------------------------------------------------

def test_to_dict_ma_voice_path_a_uid():
    dialogs = _read("ui_dialogs.py")
    td = dialogs[dialogs.index("    def to_dict(self"):dialogs.index("class RecordDialog")]
    assert '"voice_path": self.voice_path' in td
    assert '"uid": self.uid' in td


# ---- UI: the voice dialog has custom voice recording ---------------------

def test_dialog_hlasu_ma_vlastnu_nahravku():
    dialogs = _read("ui_dialogs.py")
    dialog = dialogs[dialogs.index("class SlotSettingsDialog:"):]
    dialog = dialog[:dialog.index("\nclass ", 5)]
    for metoda in ("def record_voice", "def choose_voice", "def clear_voice"):
        assert metoda in dialog, f"dialog hlasu nema {metoda}"
    assert "dialog.voice_rec_label" in dialog


# ---- i18n: all new keys have all languages ---------------------------------

def test_nove_i18n_kluce_maju_vsetky_jazyky():
    import i18n
    nove = [
        "dialog.voice_rec_label", "dialog.voice_rec_none", "dialog.voice_rec_set",
        "dialog.voice_rec_record", "dialog.voice_rec_file", "dialog.voice_rec_clear",
        "dialog.voice_rec_note", "dialog.choose_voice_title",
        "log.slot_voice_recorded", "log.slot_voice_set", "log.slot_voice_cleared",
    ]
    for kluc in nove:
        assert kluc in i18n.STRINGS, f"chyba i18n kluc {kluc}"
        for lang in i18n.LANGUAGES:
            assert i18n.STRINGS[kluc].get(lang), f"{kluc} nema preklad pre {lang}"
