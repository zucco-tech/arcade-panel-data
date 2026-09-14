#!/usr/bin/env python3
"""Sur la borne : rejoue un echantillon de fiches sur le vrai materiel.

Pour chaque fiche, la borne lance le jeu elle-meme avec le coeur qu utilise
Recalbox, attend qu il tourne, lit le compteur a l adresse de la fiche, met
une piece par un clavier virtuel, relit — il doit avoir monte de un —,
appuie sur START, relit — il doit etre redescendu. C est la preuve de bout
en bout : le fichier deploye, le coeur de la borne, la vraie machine.

EmulationStation est arrete le temps du controle (il faut l ecran) et
relance a la fin, quoi qu il arrive. Seuls les systemes lus par RetroArch
sont controlables ici : MAME ne livre pas sa memoire par ce chemin.

    python3 verifier-sur-borne.py echantillon.json rapport.json

Lance depuis le PC par verifier-sur-borne.sh, qui apporte ce fichier et le
clavier virtuel dans /tmp et rapatrie le rapport."""

import json
import os
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clavier_virtuel import ClavierVirtuel   # le meme que celui du balayage

RETROARCH = "/usr/bin/retroarch"
CONFIG = "/recalbox/share/system/configs/retroarch/retroarchcustom.cfg"
ROMS = "/recalbox/share/roms"
COEURS = {"fbneo": "fbneo_libretro.so", "neogeo": "fbneo_libretro.so",
          "neogeocd": "fbneo_libretro.so", "fba": "fbneo_libretro.so"}
PORT = 55355
FRONTEND = "/etc/init.d/S31emulationstation"
# Les attentes, en secondes. Le balayage du PC laisse bien plus de temps a
# un jeu pour demarrer ; ici on veut aller vite, mais un jeu lent a se
# reveiller (Pinball Action) rendrait un faux ecart. On peut donc les
# allonger en argument : verifier-sur-borne.py echantillon rapport [boot] [start].
ATTENTE_BOOT = 6.0                    # apres que le coeur repond, avant la piece
ATTENTE_PIECE = 1.5                   # entre la piece et la lecture
ATTENTE_START = 2.5                   # entre le START et la lecture


def udp(texte, attendre=True, timeout=0.6):
    """Une commande au port reseau de RetroArch (le meme dialogue que le
    demon des credits) ; None s il ne repond pas."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(texte.encode(), ("127.0.0.1", PORT))
        if not attendre:
            return ""
        return sock.recv(65536).decode(errors="replace").strip()
    except OSError:
        return None
    finally:
        sock.close()


def lire(adresse, octets):
    """Le compteur, ou None si le coeur ne repond pas."""
    reponse = udp("READ_CORE_RAM %x %d" % (adresse, octets))
    if not reponse:
        return None
    parties = reponse.split()
    if len(parties) < 3 or parties[2] == "-1":
        return None
    try:
        valeurs = [int(x, 16) for x in parties[2:2 + octets]]
    except ValueError:
        return None
    return sum(v << (8 * i) for i, v in enumerate(valeurs))   # petit-boutiste


def attendre_le_jeu(adresse, octets, delai=30.0):
    fin = time.time() + delai
    while time.time() < fin:
        etat = udp("GET_STATUS") or ""
        if "PLAYING" in etat and lire(adresse, octets) is not None:
            return True
        time.sleep(0.5)
    return False


def controler(fiche, clavier, journal):
    systeme, jeu = fiche["systeme"], fiche["jeu"]
    coeur = COEURS.get(systeme)
    rom = os.path.join(ROMS, systeme, jeu + ".zip")
    if not coeur:
        return "HORS CHAMP  %s ne se lit pas par RetroArch sur la borne" % systeme
    if not os.path.exists(rom):
        return "ABSENT      pas de rom %s" % rom
    adresse, octets = fiche["adresse"], fiche.get("octets") or 1
    processus = subprocess.Popen(
        [RETROARCH, "-L", "/usr/lib/libretro/" + coeur, "--config", CONFIG,
         "--appendconfig", CONFIG + ".overrides.cfg", rom],
        stdout=journal, stderr=subprocess.STDOUT)
    try:
        if not attendre_le_jeu(adresse, octets):
            return "NON LANCE   le jeu n a pas demarre en 30 s"
        time.sleep(ATTENTE_BOOT)              # le temps d arriver en attract
        avant = lire(adresse, octets)
        if fiche.get("entree_piece") and fiche["entree_piece"] != "select":
            clavier.bouton(fiche["entree_piece"])
        else:
            clavier.piece()
        time.sleep(ATTENTE_PIECE)
        apres_piece = lire(adresse, octets)
        clavier.start()
        time.sleep(ATTENTE_START)
        apres_start = lire(adresse, octets)
        suite = "%s -> %s -> %s" % (avant, apres_piece, apres_start)
        if None in (avant, apres_piece, apres_start):
            return "ILLISIBLE   %s" % suite
        if apres_piece == avant + 1 and apres_start == avant:
            return "OK          %s" % suite
        if apres_piece == avant + 1 and apres_start < apres_piece:
            # Il descend, mais pas de un : le demon s en contente (il ne
            # regarde que le sens), mais ce n est pas un compteur de credits
            # ordinaire — a noter, pas a valider les yeux fermes.
            return "DESCEND     %s (pas de -1 franc)" % suite
        if apres_piece == avant + 1:
            return "PIECE SEULE %s (le START n a pas consomme)" % suite
        return "ECART       %s (la piece n a pas monte le compteur)" % suite
    finally:
        udp("QUIT", attendre=False)
        for _ in range(20):
            if processus.poll() is not None:
                break
            time.sleep(0.5)
        else:
            processus.kill()
        time.sleep(1.5)


def main():
    global ATTENTE_BOOT, ATTENTE_START
    echantillon = json.load(open(sys.argv[1]))
    sortie = sys.argv[2]
    if len(sys.argv) > 3:
        ATTENTE_BOOT = float(sys.argv[3])
    if len(sys.argv) > 4:
        ATTENTE_START = float(sys.argv[4])
    if subprocess.call(["pidof", "retroarch"], stdout=subprocess.DEVNULL) == 0:
        print("une partie est en cours : on ne touche pas a la borne")
        return 2
    resultats = []
    subprocess.call([FRONTEND, "stop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3.0)
    try:
        with ClavierVirtuel("clavier-verification") as clavier, \
                open("/tmp/verification-retroarch.log", "w") as journal:
            for fiche in echantillon["fiches"]:
                verdict = controler(fiche, clavier, journal)
                ligne = "%-6s %-12s %s" % (fiche["systeme"], fiche["jeu"], verdict)
                print(ligne, flush=True)
                resultats.append(ligne)
    finally:
        subprocess.call([FRONTEND, "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    json.dump({"le": time.strftime("%Y-%m-%d %H:%M"), "lignes": resultats}, open(sortie, "w"), indent=1)
    return 1 if any(" ECART" in l for l in resultats) else 0


if __name__ == "__main__":
    sys.exit(main())
