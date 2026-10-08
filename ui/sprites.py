"""Display original JPEG pixels, with six viewports and exterior-only window masks.

No generated, recolored, resampled or rewritten artwork. Windows GDI+ decodes
the original JPEG once. White enclosed eyes remain inside the window region.
"""
import ctypes as c
from collections import deque
from pathlib import Path
import hashlib
import json
import struct
import sys


ASSETS = Path(__file__).resolve().parents[1] / 'assets' / 'sazabi'


def decode_jpeg(path):
    if sys.platform != 'win32':
        raise RuntimeError('O mascote usa GDI+ do Windows. Em outros sistemas, use --cli.')
    gdip = c.WinDLL('gdiplus')
    class Startup(c.Structure):
        _fields_ = [('version', c.c_uint), ('callback', c.c_void_p), ('thread', c.c_int), ('codecs', c.c_int)]
    class Rect(c.Structure):
        _fields_ = [('x', c.c_int), ('y', c.c_int), ('width', c.c_int), ('height', c.c_int)]
    class BitmapData(c.Structure):
        _fields_ = [('width', c.c_uint), ('height', c.c_uint), ('stride', c.c_int),
                    ('format', c.c_int), ('scan', c.c_void_p), ('reserved', c.c_size_t)]
    gdip.GdiplusStartup.argtypes = [c.POINTER(c.c_size_t), c.POINTER(Startup), c.c_void_p]
    gdip.GdipCreateBitmapFromFile.argtypes = [c.c_wchar_p, c.POINTER(c.c_void_p)]
    gdip.GdipGetImageWidth.argtypes = [c.c_void_p, c.POINTER(c.c_uint)]
    gdip.GdipGetImageHeight.argtypes = [c.c_void_p, c.POINTER(c.c_uint)]
    gdip.GdipBitmapLockBits.argtypes = [c.c_void_p, c.POINTER(Rect), c.c_uint, c.c_int, c.POINTER(BitmapData)]
    gdip.GdipBitmapUnlockBits.argtypes = [c.c_void_p, c.POINTER(BitmapData)]
    gdip.GdipDisposeImage.argtypes = [c.c_void_p]
    gdip.GdiplusShutdown.argtypes = [c.c_size_t]
    token, bitmap = c.c_size_t(), c.c_void_p()
    if gdip.GdiplusStartup(c.byref(token), c.byref(Startup(1, None, 0, 0)), None):
        raise RuntimeError('Falha ao iniciar o decodificador de imagem do Windows.')
    try:
        if gdip.GdipCreateBitmapFromFile(str(path), c.byref(bitmap)):
            raise RuntimeError('Não foi possível ler a arte original.')
        w, h = c.c_uint(), c.c_uint()
        gdip.GdipGetImageWidth(bitmap, c.byref(w))
        gdip.GdipGetImageHeight(bitmap, c.byref(h))
        if not 0 < w.value * h.value <= 4_000_000:
            raise RuntimeError('Dimensões da arte inválidas.')
        data = BitmapData()
        if gdip.GdipBitmapLockBits(bitmap, c.byref(Rect(0, 0, w.value, h.value)), 1, 0x26200A, c.byref(data)):
            raise RuntimeError('Não foi possível acessar os pixels da arte.')
        try:
            rgb = bytearray()
            for y in range(h.value):
                row = c.string_at(data.scan + y * data.stride, w.value * 4)
                for x in range(w.value):
                    b, g, r = row[x*4:x*4+3]
                    rgb.extend((r, g, b))
            return w.value, h.value, bytes(rgb)
        finally:
            gdip.GdipBitmapUnlockBits(bitmap, c.byref(data))
    finally:
        if bitmap:
            gdip.GdipDisposeImage(bitmap)
        gdip.GdiplusShutdown(token)


def foreground_mask(rgb, width, height, threshold=96):
    """Hide white-matted JPEG fringe connected to the exterior, never enclosed eyes.

    This artwork's silhouette is dark. Mixed white/blue edge pixels must be
    considered too, not only neutral near-white. Source RGB remains untouched.
    """
    exterior = bytearray(width * height)
    queue = deque()
    def visit(x, y):
        i = y*width+x
        if exterior[i]:
            return
        color = rgb[i*3:i*3+3]
        if min(color) >= threshold:
            exterior[i] = 1
            queue.append((x, y))
    for x in range(width):
        visit(x, 0)
        visit(x, height-1)
    for y in range(height):
        visit(0, y)
        visit(width-1, y)
    while queue:
        x, y = queue.popleft()
        for a, b in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
            if 0 <= a < width and 0 <= b < height:
                visit(a, b)
    return bytes(0 if value else 1 for value in exterior)


def region_data(mask, width, height):
    rects = []
    for y in range(height):
        x = 0
        while x < width:
            if not mask[y*width+x]:
                x += 1
                continue
            start = x
            while x < width and mask[y*width+x]:
                x += 1
            rects.append((start, y, x, y+1))
    header = struct.pack('<4I4i', 32, 1, len(rects), len(rects)*16, 0, 0, width, height)
    return header + b''.join(struct.pack('<4i', *rect) for rect in rects)


class SpriteAtlas:
    def __init__(self, root, directory=ASSETS):
        import tkinter as tk
        self.config = json.loads((directory / 'states.json').read_text(encoding='utf-8'))
        path = directory / self.config['image']
        if hashlib.sha256(path.read_bytes()).hexdigest() != self.config['sha256']:
            raise RuntimeError('A arte original foi alterada. Confira assets/sazabi/states.json.')
        width, height, pixels = decode_jpeg(path)
        self.width, self.height = self.config['canvas']
        self.images, self.regions, self.masks = {}, {}, {}
        for state, (left, top, right, bottom) in self.config['states'].items():
            if not (0 <= left < right <= width and 0 <= top < bottom <= height):
                raise RuntimeError('Recorte de exibição inválido: ' + state)
            w, h = right-left, bottom-top
            if w > self.width or h > self.height:
                raise RuntimeError('Recorte maior que a janela: ' + state)
            # Copy into a view; retain exactly the decoded RGB of every source pixel.
            crop = b''.join(pixels[(y*width+left)*3:(y*width+right)*3] for y in range(top, bottom))
            mask = foreground_mask(crop, w, h, self.config['background_threshold'])
            ox, oy = (self.width-w)//2, self.height-h
            display = bytearray(b'\xff' * (self.width*self.height*3))
            full_mask = bytearray(self.width*self.height)
            for y in range(h):
                index = (oy+y)*self.width+ox
                display[index*3:(index+w)*3] = crop[y*w*3:(y+1)*w*3]
                full_mask[index:index+w] = mask[y*w:(y+1)*w]
            ppm = f'P6\n{self.width} {self.height}\n255\n'.encode() + display
            self.images[state] = tk.PhotoImage(master=root, data=ppm, format='PPM')
            self.masks[state] = bytes(full_mask)
            self.regions[state] = region_data(full_mask, self.width, self.height)
