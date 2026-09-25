#!/usr/bin/env python3
"""
Clavier virtuel par /dev/uinput, sans dependance.

Pourquoi un clavier et pas une manette : RetroArch attribue les manettes aux
ports dans l'ordre ou il les voit. Les deux AllInOne occupent deja les ports
1 et 2 ; une manette virtuelle serait le joueur 3, et le jeu ignorerait tout
ce qu'elle envoie. Il faudrait modifier retroarchcustom.cfg pour la forcer,
ce qu'on ne veut pas faire.

Le clavier echappe a ce probleme : RetroArch le traite a part et le cable sur
le joueur 1 par defaut, sans rien reconfigurer :

    Entree       -> START joueur 1
    Shift droit  -> SELECT joueur 1, c'est-a-dire la piece

Les manettes physiques ne sont ni touchees ni reconfigurees : ce clavier est
un peripherique de plus, qui disparait des qu'on ferme.
"""

import ctypes
import fcntl
import os
import struct
import time

UINPUT = "/dev/uinput"

EV_SYN, EV_KEY = 0x00, 0x01
SYN_REPORT = 0

KEY_ENTER = 28          # START joueur 1
KEY_RIGHTSHIFT = 54     # SELECT joueur 1 = piece

# Le joueur 2 a ses propres touches, cablees dans retroarch.cfg :
#   input_player2_start = "2"   input_player2_select = "6"
# Sans elles, impossible de savoir si un jeu tient DEUX compteurs de credits
# separes — ce qui est le cas des jeux a deux postes, ou chacun alimente le
# sien tant que personne n a appuye sur START.
KEY_2 = 3               # START joueur 2
KEY_6 = 7               # SELECT joueur 2 = piece joueur 2

# Les huit entrees de chaque poste, cablees dans retroarch.cfg. Elles servent
# quand un jeu n encaisse PAS sa piece sur SELECT : flippers, jeux de tir,
# certains japonais. Sans elles, ces jeux restent introuvables.
#
#   joueur 1 : a=x  b=z  x=s  y=a  l=q  r=w
#   joueur 2 : a=g  b=f  x=t  y=r  l=e  r=y
BOUTONS_J1 = {"a": 45, "b": 44, "x": 31, "y": 30, "l": 16, "r": 17}
BOUTONS_J2 = {"a": 34, "b": 33, "x": 20, "y": 19, "l": 18, "r": 21}

# _IO('U', 1) et _IO('U', 2) ; _IOW('U', 100|101, int)
UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502
UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565

ABS_CNT = 64
EVENEMENT = struct.Struct("llHHi")      # struct input_event


class ClavierVirtuel:
    """A utiliser dans un with : le peripherique est detruit quoi qu'il arrive."""

    def __init__(self, nom="clavier-credits", touches=None):
        if touches is None:
            # Seulement la piece et le start de chaque joueur. Les boutons
            # d action servaient au repli, desactive : les declarer ouvrait
            # des menus de diagnostic sans rien apporter.
            touches = (KEY_ENTER, KEY_RIGHTSHIFT, KEY_2, KEY_6)
        self.nom = nom
        self.touches = touches
        self.fd = None

    def __enter__(self):
        self.fd = os.open(UINPUT, os.O_WRONLY | os.O_NONBLOCK)
        fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
        for touche in self.touches:
            fcntl.ioctl(self.fd, UI_SET_KEYBIT, touche)

        # struct uinput_user_dev : nom, identifiants, puis les bornes des axes
        # analogiques, inutiles ici mais attendues par le noyau.
        descriptif = (self.nom.encode()[:79].ljust(80, b"\0")
                      + struct.pack("HHHH", 0x03, 0x1234, 0x5678, 1)  # USB, ids libres
                      + struct.pack("I", 0)                           # pas de retour de force
                      + b"\0" * (ctypes.sizeof(ctypes.c_int) * ABS_CNT * 4))
        os.write(self.fd, descriptif)
        fcntl.ioctl(self.fd, UI_DEV_CREATE)
        # Le noyau doit publier le peripherique et les applications le voir.
        time.sleep(0.4)
        return self

    def __exit__(self, *_):
        if self.fd is None:
            return
        try:
            fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        except OSError:
            pass
        os.close(self.fd)
        self.fd = None

    def _envoyer(self, typ, code, valeur):
        os.write(self.fd, EVENEMENT.pack(0, 0, typ, code, valeur))

    def appuyer(self, touche, duree=0.25):
        """Un appui franc : enfoncement, pause, relachement."""
        self._envoyer(EV_KEY, touche, 1)
        self._envoyer(EV_SYN, SYN_REPORT, 0)
        time.sleep(duree)
        self._envoyer(EV_KEY, touche, 0)
        self._envoyer(EV_SYN, SYN_REPORT, 0)

    # Une piece est une IMPULSION, pas un appui. Tenue 0,25 s (15 images),
    # Armed Police Batrider affiche « COIN ERROR » des la premiere et refuse
    # les suivantes : les cartes Raizing guettent le monnayeur bloque. A
    # 0,05-0,15 s la meme piece passe et le compteur monte (banc du 12/09).
    DUREE_PIECE = 0.10

    def piece(self):
        self.appuyer(KEY_RIGHTSHIFT, self.DUREE_PIECE)

    def start(self, duree=None):
        self.appuyer(KEY_ENTER, duree or 0.25)

    def piece_j2(self):
        self.appuyer(KEY_6, self.DUREE_PIECE)

    def start_j2(self):
        self.appuyer(KEY_2)

    def bouton(self, nom, joueur=1):
        """Un bouton du panneau, par son nom RetroPad : a, b, x, y, l, r."""
        table = BOUTONS_J1 if joueur == 1 else BOUTONS_J2
        code = table.get(nom)
        if code is not None:
            self.appuyer(code)

    def entrees_possibles(self, joueur=1):
        """Tout ce qui peut encaisser une piece, dans l ordre du plus probable."""
        # Seulement les boutons d ACTION. « l » et « r » sont ecartes : dans
        # FBNeo, beaucoup de pilotes y placent Service et Test/Diagnostic, et
        # les essayer fait entrer le jeu en mode service — ou le compteur de
        # credits ne se comporte pas normalement et l adresse relevee serait
        # fausse.
        table = {n: c for n, c in (BOUTONS_J1 if joueur == 1 else BOUTONS_J2).items()
                 if n in ("a", "b", "x", "y")}
        depart = [("select", KEY_RIGHTSHIFT if joueur == 1 else KEY_6)]
        return depart + [(n, c) for n, c in sorted(table.items())]


if __name__ == "__main__":
    # Verification : le peripherique apparait-il vraiment au noyau ?
    with ClavierVirtuel("clavier-credits-essai") as clavier:
        with open("/proc/bus/input/devices") as fh:
            contenu = fh.read()
        vu = "clavier-credits-essai" in contenu
        print("peripherique visible par le noyau :", "OUI" if vu else "NON")
        for bloc in contenu.split("\n\n"):
            if "clavier-credits-essai" in bloc:
                for ligne in bloc.splitlines():
                    if ligne[:1] in ("I", "N", "H"):
                        print("   ", ligne)
        clavier.piece()
        clavier.start()
        print("deux appuis envoyes sans erreur")
    with open("/proc/bus/input/devices") as fh:
        print("apres fermeture, encore present :",
              "OUI" if "clavier-credits-essai" in fh.read() else "NON")
