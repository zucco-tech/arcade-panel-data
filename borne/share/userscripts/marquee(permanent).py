#!/usr/bin/env python3
"""
Recalbox -> marquee LED : relais d'evenements.

A deposer dans /recalbox/share/userscripts/ sous le nom exact :

    marquee(permanent).py

Le "(permanent)" indique au frontend de le lancer une seule fois au
demarrage et de le laisser tourner, plutot que de relancer un interpreteur
Python a chaque evenement (ce qui ferait ramer la navigation).

Il surveille /tmp/es_state.inf, que le frontend reecrit a chaque evenement,
et envoie son contenu en JSON/UDP a la machine qui pilote le panneau LED.

Aucune dependance : uniquement la bibliotheque standard.
"""

import json
import os
import select
import socket
import struct
import time

# --- Configuration -------------------------------------------------------

TARGET_HOST = "192.168.1.111"   # conteneur lxc-marquee
TARGET_PORT = 5005

STATE_FILE = "/tmp/es_state.inf"

# Le fichier est sur un ramdisk : un stat() toutes les 400 ms ne coute rien.
POLL = 0.4

# Repetition de l'etat courant, meme sans changement.
#
# Indispensable : pendant une partie, EmulationStation n'ecrit plus rien. Un
# recepteur qui redemarre a ce moment-la n'aurait aucun moyen d'apprendre
# qu'un jeu tourne, et resterait fige jusqu'a la prochaine navigation. La
# repetition lui permet de se resynchroniser tout seul.
REPETITION = 30.0

# --- Compteur de pieces -------------------------------------------------
#
# Le bouton "piece" de la borne est un vrai bouton cable sur l'encodeur
# AllInOne. Sa pression passe par /dev/input AVANT d'atteindre l'emulateur,
# et l'emulateur ne verrouille pas l'acces exclusif : on peut donc l'ecouter
# en parallele sans le gener. Codes releves sur cette borne :
#   314 = BTN_SELECT -> piece
#   315 = BTN_START  -> demarrage, qui consomme un credit
#
# Les pieces ne comptent que pendant une partie, et le compteur repart de
# zero a chaque entree et sortie de jeu.
ENTREES = ("/dev/input/event1", "/dev/input/event2")
CODE_PIECE = 314
CODE_START = 315
EV_KEY = 0x01
EV_TAILLE = 24                      # struct input_event sur aarch64
EV_FORMAT = "llHHi"

# Cles utiles au marquee. On n'envoie que celles-la pour garder des
# datagrammes courts et eviter de balader des chemins inutiles.
KEEP = (
    "Action", "ActionData", "State",
    "System", "SystemId",
    "Game", "GamePath",
    "IsFolder",
    # Metadonnees du scraping, presentes depuis la version 2.0 du fichier
    # d'etat. Elles peuvent etre vides si le jeu n'a pas ete scrape.
    "Developer", "Publisher", "Players", "Genre", "Region", "Favorite",
)


def read_state(path):
    """Lit le fichier ini plat cle=valeur ecrit par EmulationStation."""
    state = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                if key in KEEP:
                    state[key] = value.strip()
    except (IOError, OSError):
        return None
    return state


def journal(msg):
    """Trace minimale : sans elle, une panne d'envoi est invisible."""
    try:
        with open("/tmp/marquee.log", "a") as fh:
            fh.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))
    except IOError:
        pass


def ouvrir_entrees():
    """Ouvre les manettes en lecture seule. Une absence n'est pas fatale."""
    fds = {}
    for chemin in ENTREES:
        try:
            fds[os.open(chemin, os.O_RDONLY | os.O_NONBLOCK)] = chemin
        except OSError as err:
            journal("entree %s indisponible : %s" % (chemin, err))
    return fds


def lire_boutons(fds):
    """Renvoie la liste des codes de touches enfoncees depuis le dernier tour."""
    codes = []
    if not fds:
        return codes
    prets, _, _ = select.select(list(fds), [], [], POLL)
    for fd in prets:
        try:
            donnees = os.read(fd, EV_TAILLE * 64)
        except OSError:
            continue
        for i in range(0, len(donnees) - EV_TAILLE + 1, EV_TAILLE):
            _, _, typ, code, val = struct.unpack(EV_FORMAT,
                                                 donnees[i:i + EV_TAILLE])
            if typ == EV_KEY and val == 1:        # appui, pas relachement
                codes.append(code)
    if not prets:
        time.sleep(0)                             # select a deja temporise
    return codes


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = (TARGET_HOST, TARGET_PORT)
    echecs = 0

    last_sig = None      # signature du dernier etat envoye
    last_mtime = None

    entrees = ouvrir_entrees()
    pieces = 0
    en_jeu = False
    pieces_envoyees = None
    derniere_repetition = 0.0

    while True:
        # select temporise a la place de sleep : les boutons sont pris en
        # compte sans attendre, le fichier d'etat reste sonde au meme rythme.
        for code in lire_boutons(entrees):
            if not en_jeu:
                continue                  # hors partie, les pieces ne comptent pas
            if code == CODE_PIECE:
                pieces += 1
            elif code == CODE_START and pieces > 0:
                pieces -= 1               # demarrer consomme un credit
        if not entrees:
            time.sleep(POLL)

        if pieces != pieces_envoyees:
            try:
                sock.sendto(json.dumps({"__credits": pieces}).encode("utf-8"),
                            target)
                pieces_envoyees = pieces
            except OSError:
                pass

        try:
            mtime = os.path.getmtime(STATE_FILE)
        except OSError:
            continue                      # pas encore ecrit par le frontend

        repeter = time.time() - derniere_repetition > REPETITION
        if mtime == last_mtime and not repeter:
            continue                      # rien de neuf, et pas l'heure de repeter
        last_mtime = mtime

        state = read_state(STATE_FILE)
        if not state:
            continue

        # Deux evenements tres rapproches peuvent produire le meme etat :
        # inutile de reveiller le BLE pour rien.
        # Entree ou sortie de jeu : le compteur de pieces repart de zero.
        action = (state.get("Action") or "").lower()
        if action in ("rungame", "rundemo"):
            en_jeu, pieces = True, 0
        elif action in ("endgame", "enddemo"):
            en_jeu, pieces = False, 0

        sig = json.dumps(state, sort_keys=True)
        if sig == last_sig and not repeter:
            continue
        last_sig = sig
        derniere_repetition = time.time()

        try:
            sock.sendto(sig.encode("utf-8"), target)
            if echecs:
                journal("envoi retabli apres %d echecs" % echecs)
                echecs = 0
        except OSError as err:
            # Une socket UDP peut rester durablement en erreur apres une
            # coupure reseau. La garder condamne le relais au silence, sans
            # que rien ne le signale : on en refait une.
            echecs += 1
            if echecs in (1, 10, 100) or echecs % 500 == 0:
                journal("echec d'envoi (%d) : %s" % (echecs, err))
            try:
                sock.close()
            except OSError:
                pass
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


if __name__ == "__main__":
    main()
