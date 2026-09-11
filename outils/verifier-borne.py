#!/usr/bin/env python3
"""
Test de deux minutes : verifie les trois inconnues avant toute nuit de releve.

    python3 verifier-borne.py            # sur la borne
    python3 verifier-borne.py --borne 192.168.1.50 --sans-clavier

Il ne lance aucun jeu, n'ecrit rien, ne modifie rien. Il verifie seulement :

  1. /dev/uinput est utilisable ;
  2. un clavier virtuel apparait bien au noyau ;
  3. RetroArch voit ses appuis — c'est le seul test qui compte vraiment :
     on regarde le compteur de credits d'un jeu deja connu monter tout seul.

A lancer avec un jeu deja releve en cours (pzloop2 par exemple), sur son
ecran d'attente.
"""

import argparse
import json
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PORT_RA = 55355


def ra(hote, texte, timeout=0.8):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(texte.encode(), (hote, PORT_RA))
        return s.recv(65536).decode(errors="replace").strip()
    except OSError:
        return None
    finally:
        s.close()


def lire(hote, adresse):
    r = ra(hote, "READ_CORE_RAM %x 1" % adresse)
    if not r:
        return None
    p = r.split()
    if len(p) < 3 or p[2] == "-1":
        return None
    try:
        return int(p[2], 16)
    except ValueError:
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--borne", default="127.0.0.1")
    parser.add_argument("--base", default="/recalbox/share/system/credits-arcade.json")
    parser.add_argument("--sans-clavier", action="store_true",
                        help="sauter les tests uinput (depuis un PC distant)")
    args = parser.parse_args()
    soucis = []

    print("1. jeu en cours")
    statut = ra(args.borne, "GET_STATUS")
    if not statut or "PLAYING" not in statut:
        raise SystemExit("   aucun jeu en cours — lance un jeu deja releve d'abord.")
    jeu = statut.split(None, 2)[2].split(",")[1].strip()
    print("   %s" % jeu)

    print("2. adresse connue pour ce jeu")
    try:
        base = json.load(open(args.base))
    except (IOError, OSError, ValueError) as err:
        raise SystemExit("   base illisible : %s" % err)
    # Les fiches sont indexees "systeme/jeu" ; on accepte encore la cle nue
    # des bases anciennes.
    jeux = base.get("jeux") or {}
    fiche = jeux.get(jeu)
    if fiche is None:
        for cle, valeur in jeux.items():
            if cle.rsplit("/", 1)[-1] == jeu:
                fiche = valeur
                break
    fiche = (fiche or {}).get("credits") or {}
    adresse = fiche.get("adresse")
    if adresse is None:
        raise SystemExit("   %s n'est pas encore releve — choisis un jeu connu "
                         "(pzloop2)." % jeu)
    depart = lire(args.borne, adresse)
    print("   %s : %d credit(s)" % (fiche["adresse_hex"], depart))

    if args.sans_clavier:
        print("\ntests clavier sautes (--sans-clavier).")
        return

    print("3. /dev/uinput")
    if not os.path.exists("/dev/uinput"):
        soucis.append("/dev/uinput absent : le releve automatique est impossible")
        print("   ABSENT")
    else:
        try:
            fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
            os.close(fd)
            print("   utilisable")
        except OSError as err:
            soucis.append("/dev/uinput refuse l'ecriture : %s" % err)
            print("   refuse : %s" % err)

    if not soucis:
        from clavier_virtuel import ClavierVirtuel
        print("4. clavier virtuel visible par le noyau")
        with ClavierVirtuel("clavier-credits-essai") as clavier:
            try:
                with open("/proc/bus/input/devices") as fh:
                    vu = "clavier-credits-essai" in fh.read()
            except IOError:
                vu = None
            print("   %s" % {True: "oui", False: "NON", None: "indeterminable"}[vu])
            if vu is False:
                soucis.append("le clavier virtuel n'apparait pas")

            print("5. RetroArch recoit les appuis  (le test decisif)")
            print("   trois pieces envoyees...")
            for _ in range(3):
                clavier.piece()
                time.sleep(0.8)
            time.sleep(1.0)
            arrivee = lire(args.borne, adresse)
            print("   credits : %d -> %s" % (depart, arrivee))
            if arrivee is None:
                soucis.append("lecture impossible apres les appuis")
            elif arrivee > depart:
                print("   LE JEU A VU LES PIECES — tout fonctionne.")
            else:
                soucis.append("le compteur n'a pas bouge : RetroArch ignore le "
                              "clavier, ou le jeu n'est pas sur son ecran d'attente")

    print()
    if soucis:
        print("PROBLEMES :")
        for s in soucis:
            print("  - %s" % s)
    else:
        print("TOUT EST BON — la nuit de releve peut tourner.")


if __name__ == "__main__":
    main()
