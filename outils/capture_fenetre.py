#!/usr/bin/env python3
"""
Photographie la fenetre de RetroArch, pour voir ce que le jeu affiche.

Sert quand un jeu ne reagit pas : l image dit souvent ce que la memoire ne
dit pas — un ecran « insert coin » qui n arrive jamais, un message d erreur,
un jeu bloque sur un test de RAM, un monnayeur qui attend autre chose.

On photographie la FENETRE et non l ecran : sous Wayland la fenetre racine
est vide, XGetImage y echoue avec BadMatch.

Aucune dependance hors PIL, deja present.
"""

import ctypes
import ctypes.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class XImage(ctypes.Structure):
    _fields_ = [("width", ctypes.c_int), ("height", ctypes.c_int),
                ("xoffset", ctypes.c_int), ("format", ctypes.c_int),
                ("data", ctypes.POINTER(ctypes.c_char)),
                ("byte_order", ctypes.c_int), ("bitmap_unit", ctypes.c_int),
                ("bitmap_bit_order", ctypes.c_int), ("bitmap_pad", ctypes.c_int),
                ("depth", ctypes.c_int), ("bytes_per_line", ctypes.c_int),
                ("bits_per_pixel", ctypes.c_int),
                ("red_mask", ctypes.c_ulong), ("green_mask", ctypes.c_ulong),
                ("blue_mask", ctypes.c_ulong)]


def photographier(chemin, titre="RetroArch", affichage=":0"):
    """Vrai si l image a ete ecrite."""
    try:
        from PIL import Image
        from fenetre_x import _X
    except ImportError:
        return False
    try:
        X = _X(affichage)
    except OSError:
        return False
    fen = X.chercher(titre)
    if not fen:
        return False
    r = ctypes.c_ulong(); x = ctypes.c_int(); y = ctypes.c_int()
    w = ctypes.c_uint(); h = ctypes.c_uint(); b = ctypes.c_uint(); p = ctypes.c_uint()
    X.x.XGetGeometry.argtypes = [
        ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint),
        ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint)]
    X.x.XGetGeometry(X.d, fen, ctypes.byref(r), ctypes.byref(x), ctypes.byref(y),
                     ctypes.byref(w), ctypes.byref(h), ctypes.byref(b), ctypes.byref(p))
    X.x.XGetImage.restype = ctypes.POINTER(XImage)
    X.x.XGetImage.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int,
                              ctypes.c_int, ctypes.c_uint, ctypes.c_uint,
                              ctypes.c_ulong, ctypes.c_int]
    img = X.x.XGetImage(X.d, fen, 0, 0, w.value, h.value, 0xFFFFFFFF, 2)
    if not img:
        return False
    im = img.contents
    brut = ctypes.string_at(im.data, im.bytes_per_line * im.height)
    try:
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        photo = Image.frombytes("RGB", (im.width, im.height), brut, "raw", "BGRX")
        # Une image reduite suffit a voir un ecran de jeu, et pese dix fois moins.
        photo.thumbnail((960, 720))
        photo.save(chemin)
        os.chmod(chemin, 0o644)
    except (OSError, ValueError):
        return False
    return True


if __name__ == "__main__":
    ok = photographier(sys.argv[1] if len(sys.argv) > 1 else "/tmp/fenetre.png")
    print("capture ecrite" if ok else "aucune fenetre RetroArch")
