#!/usr/bin/env python3
"""
Fait tourner le releve en continu, systeme apres systeme, sans surveillance.

    python3 balayage-continu.py

Pense pour une machine dediee qui tourne jour et nuit. Il enchaine les
systemes dans l ordre, reprend les jeux ecartes une fois le systeme fini,
puis passe au suivant. Quand tout est fait il se rendort et reverifie plus
tard : une base de cheats mise a jour, des roms ajoutees, et il reprend.

Il s arrete proprement si le fichier d arret existe, et il ne demarre jamais
sans avoir verifie le jeu temoin — relever six mille adresses avec un coeur
qui range sa memoire autrement serait du temps perdu deux fois.

Aucune dependance : uniquement la bibliotheque standard.
"""

import json
import os
import socket
import subprocess
import sys
import time

RACINE = "/mnt/recalbox"
OUTILS = os.path.join(RACINE, "outils")
BASE = os.path.join(RACINE, "donnees", "credits-arcade.json")
JOURNAUX = os.path.join(RACINE, "journaux")
ARRET = "/tmp/arret-nuit"

# L ordre compte : on commence par ce qu on maitrise, on garde pour la fin
# les coeurs dont on ignore s ils exposent leur memoire.
SYSTEMES = ["fbneo", "fba", "neogeo", "neogeocd",
            "naomi", "naomigd", "naomi2", "atomiswave"]

# Le jeu temoin et son adresse, mesures a la main sur la borne avec de
# vraies pieces. Si le coeur d ici ne donne pas la meme chose, sa disposition
# memoire differe et rien de ce qu on releverait ne vaudrait ailleurs.
TEMOIN = ("fbneo", "pzloop2", 0x0450)

REPOS_ENTRE_TOURS = 900.0     # quand tout est fait, on repasse dans un quart d heure


def journal(msg):
    horodate = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(horodate, flush=True)
    try:
        os.makedirs(JOURNAUX, exist_ok=True)
        with open(os.path.join(JOURNAUX, "continu.log"), "a") as fh:
            fh.write(horodate + "\n")
    except OSError:
        pass


def arret_demande():
    return os.path.exists(ARRET)


def ra(commande, timeout=2.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(commande.encode(), ("127.0.0.1", 55355))
        return sock.recv(65536).decode(errors="replace").strip()
    except OSError:
        return None
    finally:
        sock.close()


def verifier_temoin():
    """Le coeur d ici range-t-il sa memoire comme celui de la borne ?"""
    systeme, jeu, adresse = TEMOIN
    base = json.load(open(BASE))
    fiche = (base.get("jeux") or {}).get("%s/%s" % (systeme, jeu))
    if not fiche:
        journal("temoin %s absent de la base : controle impossible" % jeu)
        return False

    journal("controle du temoin %s, adresse attendue 0x%04X" % (jeu, adresse))
    processus = subprocess.Popen(
        [sys.executable, os.path.join(OUTILS, "nuit-credits.py"),
         "--direct", "--essai", "--systeme", systeme, "--base", BASE],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    processus.wait()

    # On relit simplement l adresse pendant que le jeu tourne : si le coeur
    # differe, elle ne designera pas un compteur de credits plausible.
    valeur = None
    for _ in range(20):
        reponse = ra("READ_CORE_RAM %x 1" % adresse)
        if reponse and reponse.split()[-1] != "-1":
            valeur = int(reponse.split()[-1], 16)
            break
        time.sleep(2)
    if valeur is None:
        journal("temoin : adresse illisible — le coeur n expose pas la memoire "
                "au meme endroit. ARRET.")
        return False
    if valeur > 99:
        journal("temoin : 0x%04X vaut %d, ce n est pas un nombre de credits "
                "plausible. ARRET." % (adresse, valeur))
        return False
    journal("temoin : 0x%04X vaut %d — coherent, on peut y aller"
            % (adresse, valeur))
    return True


def restant(systeme):
    """Combien de jeux restent a traiter sur ce systeme."""
    sortie = subprocess.run(
        [sys.executable, os.path.join(OUTILS, "nuit-credits.py"),
         "--direct", "--essai", "--systeme", systeme, "--base", BASE,
         "--roms", "/mnt/roms"],
        capture_output=True, text=True).stdout
    for ligne in sortie.splitlines():
        if "jeu(x) au total" in ligne:
            try:
                return int(ligne.split()[0])
            except ValueError:
                pass
    return 0


def balayer(systeme, reessayer=False):
    """Un passage complet sur un systeme. Renvoie le code de sortie."""
    commande = [sys.executable, "-u", os.path.join(OUTILS, "nuit-credits.py"),
                "--direct", "--rapide", "--roms", "/mnt/roms",
                "--systeme", systeme, "--base", BASE, "--arret", ARRET]
    if reessayer:
        commande.append("--reessayer")
    chemin = os.path.join(JOURNAUX, "%s-%s.log" % (systeme, time.strftime("%Y%m%d-%H%M")))
    os.makedirs(JOURNAUX, exist_ok=True)
    with open(chemin, "w") as sortie:
        return subprocess.run(commande, stdout=sortie, stderr=subprocess.STDOUT).returncode


def main():
    journal("=== balayage continu : demarrage ===")
    if not verifier_temoin():
        journal("le controle du temoin a echoue : on ne balaye pas.")
        return 1

    while not arret_demande():
        travail = False
        for systeme in SYSTEMES:
            if arret_demande():
                break
            if not os.path.isdir(os.path.join("/mnt/roms", systeme)):
                continue
            n = restant(systeme)
            if n:
                journal("%s : %d jeu(x) a traiter" % (systeme, n))
                balayer(systeme)
                travail = True
                continue
            # Systeme fini : on tente une fois les ecartes recuperables.
            journal("%s : termine, reprise des ecartes" % systeme)
            if balayer(systeme, reessayer=True) == 0:
                travail = True

        if arret_demande():
            break
        if not travail:
            journal("plus rien a faire — nouvelle passe dans %d min"
                    % (REPOS_ENTRE_TOURS / 60))
        temps = 0.0
        while temps < REPOS_ENTRE_TOURS and not arret_demande():
            time.sleep(10.0)
            temps += 10.0

    journal("=== arret demande, tout est sauve ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
