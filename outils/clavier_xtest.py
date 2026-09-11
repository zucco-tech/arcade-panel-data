#!/usr/bin/env python3
"""
Clavier par XTEST, adresse a UN serveur X precis.

Pourquoi celui-ci plutot que clavier_virtuel.py : le clavier uinput est un
peripherique du NOYAU. Ses touches partent dans la fenetre active, quelle
qu elle soit — le terminal de l utilisateur compris, ou un Entree valide une
commande a moitie tapee. Et avec plusieurs RetroArch ouverts, la piece tombe
dans celui qui a le focus, pas dans celui qu on mesure.

XTEST, lui, injecte dans un serveur X donne. En placant chaque RetroArch dans
son propre serveur imbrique (Xephyr), ou il est la seule fenetre et a donc
toujours le focus, chaque instance recoit exactement ses touches et rien
d autre. Le bureau de l utilisateur n en voit aucune.

A la difference des evenements XSendEvent — essayes, et ignores par
RetroArch — les evenements XTEST sont indiscernables d un vrai clavier.

    with ClavierXTest(":10") as clavier:
        clavier.piece()
        clavier.start()

Aucune dependance : ctypes sur les bibliotheques X deja presentes.
"""

import ctypes
import ctypes.util
import time

# Codes X = codes evdev + 8. Memes touches que le clavier uinput, pour que
# la configuration de RetroArch reste valable :
#   Entree      -> START joueur 1
#   Shift droit -> SELECT joueur 1, c est-a-dire la piece
KEY_ENTREE = 36
KEY_SHIFT_DROIT = 62


class ClavierXTest:
    """A utiliser dans un with : la connexion est fermee quoi qu il arrive."""

    def __init__(self, affichage):
        self.affichage = affichage
        self.x = None
        self.xtest = None
        self.d = None

    def __enter__(self):
        self.x = ctypes.CDLL(ctypes.util.find_library("X11"))
        self.xtest = ctypes.CDLL(ctypes.util.find_library("Xtst"))
        self.x.XOpenDisplay.restype = ctypes.c_void_p
        self.x.XFlush.argtypes = [ctypes.c_void_p]
        self.xtest.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                                 ctypes.c_int, ctypes.c_ulong]
        self.d = self.x.XOpenDisplay(self.affichage.encode())
        if not self.d:
            raise OSError("affichage %s inaccessible" % self.affichage)
        return self

    def __exit__(self, *_):
        if self.d:
            self.x.XCloseDisplay.argtypes = [ctypes.c_void_p]
            try:
                self.x.XCloseDisplay(self.d)
            except OSError:
                pass
            self.d = None

    def appuyer(self, touche, duree=0.12):
        """Un appui franc : enfoncement, pause, relachement."""
        self.xtest.XTestFakeKeyEvent(self.d, touche, 1, 0)
        self.x.XFlush(self.d)
        time.sleep(duree)
        self.xtest.XTestFakeKeyEvent(self.d, touche, 0, 0)
        self.x.XFlush(self.d)

    def piece(self):
        self.appuyer(KEY_SHIFT_DROIT)

    def start(self):
        self.appuyer(KEY_ENTREE)


if __name__ == "__main__":
    import sys
    affichage = sys.argv[1] if len(sys.argv) > 1 else ":10"
    with ClavierXTest(affichage) as clavier:
        clavier.piece()
        clavier.start()
        print("deux appuis envoyes sur %s, sans clavier systeme" % affichage)
