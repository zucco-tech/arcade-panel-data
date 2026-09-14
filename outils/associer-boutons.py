#!/usr/bin/env python3
"""Sur la borne : associe chaque LED d un poste au code que son bouton envoie.

On allume UNE LED, le joueur appuie sur le bouton allume, on note le code ;
six fois par poste. Le resultat va dans cablage.json, que le panneau du menu
et le demon des credits lisent pour savoir quelle LED porte quel bouton.
A refaire si l on recable, ou pour mesurer le poste 2.

    python3 associer-boutons.py 1            # le poste 1 (manette event1)
    python3 associer-boutons.py 2            # le poste 2 (event2)

Le panneau du menu est arrete pendant la mesure — il repeindrait les LED —
et relance a la fin quoi qu il arrive. Lance depuis le PC par
associer-boutons.sh, qui apporte ce fichier et rapatrie cablage.json."""

import json
import os
import select
import struct
import subprocess
import sys
import time

FMT = "llHHi"
TAILLE = struct.calcsize(FMT)
LEDS = "/sys/class/leds"
N = "/recalbox/share/system/panneau-allinone"
CABLAGE = os.path.join(N, "cablage.json")
MANETTE = {1: "/dev/input/event1", 2: "/dev/input/event2"}
FACADE = (314, 315, 316)               # piece, start, hotkey : pas des boutons de jeu


def ecrire(poste, nom, valeur):
    """La meme valeur sur les deux LED d un bouton."""
    for k in (1, 2):
        try:
            with open("%s/aio_p%d_%s_%d/brightness" % (LEDS, poste, nom, k), "w") as fh:
                fh.write(valeur)
        except OSError:
            pass


def lire(poste, nom):
    """La luminosite actuelle d une LED, pour la rendre telle quelle a la fin."""
    try:
        with open("%s/aio_p%d_%s_1/brightness" % (LEDS, poste, nom)) as fh:
            return fh.read().strip()
    except OSError:
        return None


def arreter_panneau():
    """Le panneau du menu repeindrait les LED pendant la mesure : on l arrete."""
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        try:
            with open("/proc/%s/cmdline" % p, "rb") as fh:
                if b"panneau(permanent)" in fh.read():
                    os.kill(int(p), 15)
        except OSError:
            pass


def attendre_appui(pad, delai=30.0):
    """Le premier code de bouton de jeu presse sur la manette, ou None."""
    fin = time.time() + delai
    while time.time() < fin:
        prets, _, _ = select.select([pad], [], [], 0.5)
        if not prets:
            continue
        d = pad.read(TAILLE)
        if len(d) < TAILLE:
            continue
        _, _, typ, code, val = struct.unpack(FMT, d)
        if typ == 1 and val == 1 and code not in FACADE:
            return code
    return None


def main():
    poste = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    noms = ["b%d" % i for i in range(1, 7)]
    sauve = {n: lire(poste, n) for n in noms}
    arreter_panneau()
    time.sleep(1.0)
    table = {}
    try:
        with open(MANETTE[poste], "rb", buffering=0) as pad:
            for n in noms:
                for autre in noms:
                    ecrire(poste, autre, "0")
                ecrire(poste, n, "255")
                code = attendre_appui(pad)
                print("LED %s -> %s" % (n, code if code is not None else "aucun appui en 30 s"), flush=True)
                if code is not None:
                    table[str(code)] = int(n[1:])
                ecrire(poste, n, "0")
                time.sleep(0.8)
    finally:
        for n in noms:
            ecrire(poste, n, sauve[n] or "255")
        subprocess.call(["sh", N + "/relancer.sh", "panneau"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if len(table) < 6:
        print("mesure incomplete : cablage.json n est pas modifie")
        return 1
    try:
        contenu = json.load(open(CABLAGE))
    except (OSError, ValueError):
        contenu = {"description": "code evdev -> numero de LED, par poste", "postes": {}}
    contenu["postes"][str(poste)] = table
    contenu["mesure_le"] = time.strftime("%Y-%m-%d")
    provisoire = CABLAGE + ".tmp"
    with open(provisoire, "w") as fh:
        json.dump(contenu, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(provisoire, CABLAGE)
    print("cablage.json : poste %d mis a jour" % poste)
    return 0


if __name__ == "__main__":
    sys.exit(main())
