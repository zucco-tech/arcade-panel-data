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

# _IO('U', 1) et _IO('U', 2) ; _IOW('U', 100|101, int)
UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502
UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565

ABS_CNT = 64
EVENEMENT = struct.Struct("llHHi")      # struct input_event


class ClavierVirtuel:
    """A utiliser dans un with : le peripherique est detruit quoi qu'il arrive."""

    def __init__(self, nom="clavier-credits", touches=(KEY_ENTER, KEY_RIGHTSHIFT)):
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

    def appuyer(self, touche, duree=0.12):
        """Un appui franc : enfoncement, pause, relachement."""
        self._envoyer(EV_KEY, touche, 1)
        self._envoyer(EV_SYN, SYN_REPORT, 0)
        time.sleep(duree)
        self._envoyer(EV_KEY, touche, 0)
        self._envoyer(EV_SYN, SYN_REPORT, 0)

    def piece(self):
        self.appuyer(KEY_RIGHTSHIFT)

    def start(self):
        self.appuyer(KEY_ENTER)


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
