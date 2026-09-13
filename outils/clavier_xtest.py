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

# Joueur 2, cable dans retroarch.cfg : start = « 2 », piece = « 6 ».
KEY_2 = 11
KEY_6 = 15

# Les six boutons de chaque poste. Memes touches que le clavier uinput, en
# codes X (codes evdev + 8) :
#   joueur 1 : a=x  b=z  x=s  y=a  l=q  r=w
#   joueur 2 : a=g  b=f  x=t  y=r  l=e  r=y
BOUTONS_J1 = {"a": 53, "b": 52, "x": 39, "y": 38, "l": 24, "r": 25}
BOUTONS_J2 = {"a": 42, "b": 41, "x": 28, "y": 27, "l": 26, "r": 29}


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

    def appuyer(self, touche, duree=0.25):
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

    def piece_j2(self):
        self.appuyer(KEY_6)

    def start_j2(self):
        self.appuyer(KEY_2)

    def bouton(self, nom, joueur=1):
        """Un bouton du panneau, par son nom RetroPad : a, b, x, y, l, r."""
        code = (BOUTONS_J1 if joueur == 1 else BOUTONS_J2).get(nom)
        if code is not None:
            self.appuyer(code)

    def entrees_possibles(self, joueur=1):
        """Tout ce qui peut encaisser une piece, du plus probable au reste."""
        # Seulement les boutons d ACTION. « l » et « r » sont ecartes : dans
        # FBNeo, beaucoup de pilotes y placent Service et Test/Diagnostic, et
        # les essayer fait entrer le jeu en mode service — ou le compteur de
        # credits ne se comporte pas normalement et l adresse relevee serait
        # fausse.
        table = {n: c for n, c in (BOUTONS_J1 if joueur == 1 else BOUTONS_J2).items()
                 if n in ("a", "b", "x", "y")}
        depart = [("select", KEY_SHIFT_DROIT if joueur == 1 else KEY_6)]
        return depart + [(n, c) for n, c in sorted(table.items())]


if __name__ == "__main__":
    import sys
    affichage = sys.argv[1] if len(sys.argv) > 1 else ":10"
    with ClavierXTest(affichage) as clavier:
        clavier.piece()
        clavier.start()
        print("deux appuis envoyes sur %s, sans clavier systeme" % affichage)
