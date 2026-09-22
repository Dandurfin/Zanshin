"""Priehladne okno s per-pixel alfou - podklad pre vsetky in-game vizualy.

Preco nie tk.Canvas
-------------------
Tk vie priehladnost len cez `-transparentcolor`: jedna JEDINA farba sa
vystrihne a vsetko ostatne ostane nepriehladne. Antialiasovana hrana (ktora
je zmesou farby tvaru a farby pozadia) sa nevystrihne a okolo kazdeho tvaru
ostane tmavy lem. Ziara sa takto neda urobit vobec.

`UpdateLayeredWindow` naopak berie 32-bit BGRA bitmapu s PREDNASOBENOU
alfou a Windows ju slozi nad plochu pixel po pixeli. To je ten isty
mechanizmus, aky pouzivaju systemove tooltipy a Windows Ink.

Bezpecnost voci anti-cheatu
---------------------------
Toto je bezne okno tejto appky. NEinjektujeme sa do procesu hry, nehookujeme
Direct3D/Present, necitame pamat hry a ani nevieme, co je na obrazovke.
Okno ma navyse:

  WS_EX_TRANSPARENT  - klik prejde nasquoz do hry (nikdy jej neukradne vstup)
  WS_EX_NOACTIVATE   - okno sa nikdy nestane aktivnym (hra nestrati focus)
  WS_EX_TOOLWINDOW   - nie je v Alt+Tab ani na paneli uloh

Zamerne NEpouzivame `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)`.
Skrylo by to overlay pred screenshotmi a OBS - co je presne to spravanie,
podla ktoreho sa hladaju podvodne prekrytia. Nas overlay ma byt na
kazdom zazname a screenshote vidno; to je jeho najlepsia obhajoba.

Ak sa vrstveny rezim z akehokolvek dovodu nepodari (stary Windows, iny OS,
ovladac), trieda ticho spadne na `-transparentcolor` + PhotoImage. Vizual
vtedy stratí ziaru, ale appka bezi dalej.
"""

import base64
import ctypes
import io
import tkinter as tk

from paths import IS_WINDOWS

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except Exception:  # pragma: no cover
    NUMPY_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:  # pragma: no cover
    PIL_AVAILABLE = False


GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080

ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01

TRANSPARENT_KEY = "#010203"   # pre fallback vetvu


if IS_WINDOWS:

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class _SIZE(ctypes.Structure):
        _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]

    class _BLENDFUNCTION(ctypes.Structure):
        _fields_ = [("BlendOp", ctypes.c_byte),
                    ("BlendFlags", ctypes.c_byte),
                    ("SourceConstantAlpha", ctypes.c_byte),
                    ("AlphaFormat", ctypes.c_byte)]

    class _BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                    ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                    ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                    ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
                    ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                    ("biClrImportant", ctypes.c_uint32)]

    class _BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", _BITMAPINFOHEADER),
                    ("bmiColors", ctypes.c_uint32 * 3)]

    _user32 = ctypes.windll.user32
    _gdi32 = ctypes.windll.gdi32

    _user32.GetDC.restype = ctypes.c_void_p
    _user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _user32.UpdateLayeredWindow.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(_POINT),
        ctypes.POINTER(_SIZE), ctypes.c_void_p, ctypes.POINTER(_POINT),
        ctypes.c_uint32, ctypes.POINTER(_BLENDFUNCTION), ctypes.c_uint32]
    _user32.UpdateLayeredWindow.restype = ctypes.c_int
    _gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    _gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
    _gdi32.CreateDIBSection.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(_BITMAPINFO), ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_uint32]
    _gdi32.CreateDIBSection.restype = ctypes.c_void_p
    _gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _gdi32.SelectObject.restype = ctypes.c_void_p
    _gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    _gdi32.DeleteDC.argtypes = [ctypes.c_void_p]


def to_premultiplied_bgra(image):
    """RGBA PIL obrazok -> bajty BGRA s prednasobenou alfou.

    Prednasobenie je poziadavka AC_SRC_ALPHA: Windows uz alfou nenasobi,
    ocakava, ze je zapocitana vo farbe. Bez toho by kazdy poloprieh}adny
    pixel svietil prilis jasno a hrany by mali biely lem.
    """
    if NUMPY_AVAILABLE:
        arr = np.asarray(image.convert("RGBA"), dtype=np.uint16)
        alpha = arr[..., 3:4]
        rgb = (arr[..., :3] * alpha + 127) // 255
        out = np.empty(arr.shape, dtype=np.uint8)
        out[..., 0] = rgb[..., 2]      # B
        out[..., 1] = rgb[..., 1]      # G
        out[..., 2] = rgb[..., 0]      # R
        out[..., 3] = arr[..., 3]      # A
        return out.tobytes()
    # numpy nie je povinny - pomalsia, ale funkcna zaloha
    src = image.convert("RGBA")
    out = bytearray(src.width * src.height * 4)
    i = 0
    for r, g, b, a in src.getdata():
        out[i] = (b * a + 127) // 255
        out[i + 1] = (g * a + 127) // 255
        out[i + 2] = (r * a + 127) // 255
        out[i + 3] = a
        i += 4
    return bytes(out)


class LayeredSurface:
    """Jedno priehladne, klikom-priechodne okno, do ktoreho sa posiela
    hotovy RGBA obrazok.

    Zivotny cyklus riadi Tk (Toplevel + `after()`), obsah kresli PIL a
    skladanie robi Windows. Fade sa robi cez konstantnu alfu vrstveneho
    okna - NEPREKRESLUJE sa pri nom obrazok, takze fade stoji nula.
    """

    def __init__(self, root):
        self.root = root
        self.top = None
        self.width = self.height = 0
        self.mode = "none"          # layered | canvas | none
        self._hwnd = None
        self._hdc = None
        self._dib = None
        self._old_bmp = None
        self._bits = None
        self._canvas = None
        self._photo = None
        self._image_ref = None
        self._alpha = 1.0

    # ---------- zivotny cyklus ----------

    def create(self, x, y, width, height):
        self.destroy()
        self.width, self.height = int(width), int(height)
        top = tk.Toplevel(self.root)
        top.withdraw()
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.configure(bg=TRANSPARENT_KEY)
        top.geometry(f"{self.width}x{self.height}+{int(x)}+{int(y)}")
        self.top = top
        top.update_idletasks()

        if IS_WINDOWS and PIL_AVAILABLE and self._setup_layered():
            self.mode = "layered"
        else:
            self._setup_canvas()
            self.mode = "canvas"
        return self.mode

    def move(self, x, y):
        if self.top is None:
            return
        try:
            self.top.geometry(f"{self.width}x{self.height}+{int(x)}+{int(y)}")
        except Exception:
            pass

    def set_click_through(self, click_through):
        """Zapne/vypne prechod kliku (WS_EX_TRANSPARENT).

        Overlay je pocas hry klik-through, aby nekradol vstup. Ale v rezime
        "Test vizualu" ho hrac potrebuje chytit mysou a potiahnut - vtedy
        klik-through docasne VYPNEME. Po skonceni testu sa zase zapne, aby
        okno v hre neprekazalo.

        Robime to na urovni WS_EX_TRANSPARENT bitu; ostatne styly (LAYERED,
        NOACTIVATE, TOOLWINDOW) ostavaju.
        """
        if not IS_WINDOWS or self.top is None:
            return
        try:
            hwnd = _user32.GetParent(self.top.winfo_id()) or self.top.winfo_id()
            hwnd = ctypes.c_void_p(hwnd)
            style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if click_through:
                style |= WS_EX_TRANSPARENT
            else:
                style &= ~WS_EX_TRANSPARENT
            _user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            pass

    def destroy(self):
        self._release_gdi()
        self._canvas = None
        self._photo = None
        self._image_ref = None
        if self.top is not None:
            try:
                self.top.destroy()
            except Exception:
                pass
        self.top = None
        self.mode = "none"

    # ---------- vykreslenie ----------

    def show(self):
        if self.top is None:
            return
        try:
            self.top.deiconify()
        except Exception:
            pass

    def draw(self, image, alpha=None):
        """Posle novy snimok. `image` musi mat presne rozmery okna."""
        if self.top is None or image is None:
            return
        if alpha is not None:
            self._alpha = max(0.0, min(1.0, float(alpha)))
        if self.mode == "layered":
            self._draw_layered(image)
        else:
            self._draw_canvas(image)

    def set_alpha(self, alpha):
        """Zmeni len priehladnost - bez prekreslovania obsahu."""
        self._alpha = max(0.0, min(1.0, float(alpha)))
        if self.top is None:
            return
        if self.mode == "layered":
            self._blit()
        else:
            try:
                self.top.attributes("-alpha", self._alpha)
            except Exception:
                pass

    # ---------- vrstvene okno ----------

    def _setup_layered(self):
        try:
            hwnd = _user32.GetParent(self.top.winfo_id()) or self.top.winfo_id()
            if not hwnd:
                return False
            hwnd = ctypes.c_void_p(hwnd)
            style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            _user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE,
                style | WS_EX_LAYERED | WS_EX_TRANSPARENT
                | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)

            screen_dc = _user32.GetDC(None)
            hdc = _gdi32.CreateCompatibleDC(screen_dc)
            info = _BITMAPINFO()
            info.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
            info.bmiHeader.biWidth = self.width
            info.bmiHeader.biHeight = -self.height   # zaporne = top-down riadky
            info.bmiHeader.biPlanes = 1
            info.bmiHeader.biBitCount = 32
            info.bmiHeader.biCompression = 0         # BI_RGB
            bits = ctypes.c_void_p()
            dib = _gdi32.CreateDIBSection(hdc, ctypes.byref(info), 0,
                                          ctypes.byref(bits), None, 0)
            _user32.ReleaseDC(None, screen_dc)
            if not dib or not bits:
                if hdc:
                    _gdi32.DeleteDC(hdc)
                return False
            self._hwnd = hwnd
            self._hdc = hdc
            self._dib = dib
            self._bits = bits
            self._old_bmp = _gdi32.SelectObject(hdc, dib)
            return True
        except Exception:
            self._release_gdi()
            return False

    def _draw_layered(self, image):
        try:
            if image.size != (self.width, self.height):
                image = image.resize((self.width, self.height), Image.LANCZOS)
            buf = to_premultiplied_bgra(image)
            ctypes.memmove(self._bits, buf, len(buf))
            self._blit()
        except Exception:
            pass

    def _blit(self):
        if self._hwnd is None:
            return
        try:
            rect_x = self.top.winfo_x()
            rect_y = self.top.winfo_y()
            pt_dst = _POINT(int(rect_x), int(rect_y))
            pt_src = _POINT(0, 0)
            size = _SIZE(self.width, self.height)
            blend = _BLENDFUNCTION(AC_SRC_OVER, 0,
                                   int(round(self._alpha * 255)), AC_SRC_ALPHA)
            screen_dc = _user32.GetDC(None)
            _user32.UpdateLayeredWindow(
                self._hwnd, screen_dc, ctypes.byref(pt_dst), ctypes.byref(size),
                self._hdc, ctypes.byref(pt_src), 0, ctypes.byref(blend), ULW_ALPHA)
            _user32.ReleaseDC(None, screen_dc)
        except Exception:
            pass

    def _release_gdi(self):
        try:
            if self._hdc and self._old_bmp:
                _gdi32.SelectObject(self._hdc, self._old_bmp)
            if self._dib:
                _gdi32.DeleteObject(self._dib)
            if self._hdc:
                _gdi32.DeleteDC(self._hdc)
        except Exception:
            pass
        self._hwnd = self._hdc = self._dib = self._old_bmp = self._bits = None

    # ---------- zaloha: transparentcolor + PhotoImage ----------

    def _setup_canvas(self):
        try:
            self.top.attributes("-transparentcolor", TRANSPARENT_KEY)
        except Exception:
            pass
        self._canvas = tk.Canvas(self.top, width=self.width, height=self.height,
                                 bg=TRANSPARENT_KEY, highlightthickness=0, bd=0)
        self._canvas.pack(fill="both", expand=True)
        if IS_WINDOWS:
            try:
                hwnd = _user32.GetParent(self.top.winfo_id()) or self.top.winfo_id()
                hwnd = ctypes.c_void_p(hwnd)
                style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                _user32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE,
                    style | WS_EX_LAYERED | WS_EX_TRANSPARENT
                    | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
            except Exception:
                pass

    def _draw_canvas(self, image):
        if not PIL_AVAILABLE or self._canvas is None:
            return
        try:
            flat = Image.new("RGB", image.size, TRANSPARENT_KEY)
            flat.paste(image, mask=image.getchannel("A"))
            buf = io.BytesIO()
            flat.save(buf, format="PNG")
            self._photo = tk.PhotoImage(
                master=self.top, data=base64.b64encode(buf.getvalue()))
            self._canvas.delete("all")
            self._canvas.create_image(0, 0, image=self._photo, anchor="nw")
            self.top.attributes("-alpha", self._alpha)
        except Exception:
            pass
