#!/usr/bin/env python3
"""Remet les boutons d un systeme dans l ordre du dessin : bouton 1 en haut a gauche.

Sur un panneau declare « arcade6 », Recalbox REORDONNE les six boutons pour
tous les systemes sauf MAME (configgen, GamepadInfo.shouldReshuffle6Btn,
Recalbox 11.0-patron-1-alpha-3.2, lu le 16/09/2026) :

    MAME                         FBNeo, Neo Geo, consoles
    [1] [2] [3]                  [3] [4] [5]
    [4] [5] [6]                  [1] [2] [6]

Le menu d EmulationStation, lui, garde l ordre du dessin (A et B en haut).
Choix du proprietaire, 16/09/2026 : le bouton 1 en haut a gauche PARTOUT,
comme une vraie borne et comme MAME.

Sans toucher a Recalbox : configgen charge un fichier .retroarch.cfg pose
dans un dossier de roms par-dessus sa propre configuration, pour tous les
jeux du dossier (settings/configOverriding.py, --appendconfig). Ce programme
ecrit ce fichier, avec les numeros de boutons lus dans es_input.cfg — la
configuration faite dans « Configurer une manette ». Si le joueur refait sa
configuration, il suffit de relancer ce programme.

    python3 aligner-boutons.py --es-input es_input.cfg --roms /mnt/roms fbneo neogeo
    python3 aligner-boutons.py --es-input es_input.cfg --roms /mnt/roms --voir fbneo
    python3 aligner-boutons.py --roms /mnt/roms --retirer fbneo neogeo

Un fichier .retroarch.cfg qui ne vient pas de ce programme n est jamais
ecrase ni retire.

Limite connue : les jeux de combat FBNeo a six boutons (Street Fighter...)
rangent poings et pieds a la maniere d une manette ; dans l ordre du dessin
ils peuvent se melanger. A verifier jeu par jeu ; un fichier
<rom>.retroarch.cfg vide ne suffit pas a revenir en arriere, il faut y
reecrire la regle de Recalbox.
"""

import argparse
import os
import sys
import xml.etree.ElementTree as ET

MARQUE = "# aligner-boutons.py : bouton 1 en haut a gauche (panneau-allinone)"
MANETTES = {1: "AllInOneP1", 2: "AllInOneP2"}
# L ordre du dessin de l assistant arcade6, et le nom RetroArch que chaque
# position doit porter pour que le bouton N du jeu tombe a la position N
# (bouton 1 = b, 2 = a, 3 = y, 4 = x, 5 = l, 6 = r : convention RetroPad des
# coeurs d arcade, la meme que MAME).
ORDRE = [("south", "b"), ("east", "a"), ("west", "y"),
         ("north", "x"), ("l1", "l"), ("r1", "r")]
# Recalbox ecrit parfois les lettres au lieu des points cardinaux.
AUTRE_NOM = {"south": "b", "east": "a", "west": "y", "north": "x"}


def lire_ids(es_input):
    """{joueur: {role: numero SDL}} pour les deux postes AllInOne."""
    racine = ET.parse(es_input).getroot()
    postes = {}
    for config in racine.iter("inputConfig"):
        for joueur, nom in MANETTES.items():
            if config.get("deviceName") != nom:
                continue
            if (config.get("gamepadtype") or "") not in ("arcade6", "arcade8"):
                raise SystemExit("%s n est pas declare arcade6/arcade8 : Recalbox ne le "
                                 "reordonne pas, rien a aligner" % nom)
            ids = {}
            for entree in config.iter("input"):
                if entree.get("type") == "button":
                    ids[entree.get("name")] = int(entree.get("id"))
            postes[joueur] = ids
    return postes


def contenu(postes):
    lignes = [MARQUE,
              "# Genere a partir de es_input.cfg. Relancer apres « Configurer une manette ».",
              "# Positions : 1 2 3 en haut, 4 5 6 en bas, comme dans l assistant."]
    for joueur in sorted(postes):
        ids = postes[joueur]
        for role, retroarch in ORDRE:
            numero = ids.get(role, ids.get(AUTRE_NOM.get(role, "")))
            if numero is None:
                raise SystemExit("poste %d : le role %s manque dans es_input.cfg" % (joueur, role))
            lignes.append('input_player%d_%s_btn = "%d"' % (joueur, retroarch, numero))
    return "\n".join(lignes) + "\n"


def est_a_nous(chemin):
    try:
        with open(chemin) as fh:
            return fh.readline().rstrip("\n") == MARQUE
    except OSError:
        return False


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("systemes", nargs="+")
    p.add_argument("--es-input", default="/recalbox/share/system/.emulationstation/es_input.cfg")
    p.add_argument("--roms", default="/recalbox/share/roms")
    p.add_argument("--voir", action="store_true", help="affiche sans rien ecrire")
    p.add_argument("--retirer", action="store_true", help="retire nos fichiers")
    a = p.parse_args()

    texte = None if a.retirer else contenu(lire_ids(a.es_input))
    for systeme in a.systemes:
        dossier = os.path.join(a.roms, systeme)
        chemin = os.path.join(dossier, ".retroarch.cfg")
        if not os.path.isdir(dossier):
            print("%s : pas de dossier de roms, ignore" % systeme)
            continue
        existe = os.path.exists(chemin)
        if existe and not est_a_nous(chemin):
            print("%s : %s existe et n est pas a nous, on n y touche pas" % (systeme, chemin))
            continue
        if a.retirer:
            if existe:
                os.remove(chemin)
                print("%s : retire, la regle de Recalbox revient" % systeme)
            continue
        if a.voir:
            print("--- %s (%s)\n%s" % (systeme, chemin, texte))
            continue
        provisoire = chemin + ".tmp"
        with open(provisoire, "w") as fh:
            fh.write(texte)
        os.replace(provisoire, chemin)
        print("%s : %s ecrit" % (systeme, chemin))
    return 0


if __name__ == "__main__":
    sys.exit(main())
