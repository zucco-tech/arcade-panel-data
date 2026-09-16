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

Par jeu. Le fichier du dossier suppose que le coeur range les boutons du
jeu dans l ordre b, a, y, x, l, r — vrai pour 1942 (Fire 1 sur b). Pas pour
les jeux de combat Capcom : FBNeo met les poings sur y, x, l et les pieds sur
b, a, r (demande au coeur le 16/09/2026). Avec --entrees (le releve de
relever-entrees.py, champ « retropad » : les boutons RetroPad dans l ordre
du jeu), on ecrit pour chacun de ces jeux un <rom>.retroarch.cfg qui met
le bouton N du jeu a la position N : poings en haut, pieds en bas.

    python3 aligner-boutons.py --es-input es_input.cfg --roms /mnt/roms \
        --entrees /mnt/recalbox/donnees/entrees-retropad.json fbneo
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


NOMS = [retroarch for _, retroarch in ORDRE]          # b a y x l r


def ordre_du_jeu(retropad):
    """Les six noms RetroPad dans l ordre ou le jeu numerote ses boutons :
    ceux que le coeur annonce d abord, puis les autres dans l ordre habituel."""
    vus = [n for n in (retropad or []) if n in NOMS]
    return vus + [n for n in NOMS if n not in vus]


def contenu(postes, ordre=None, jeu=None):
    """Le fichier : le nom RetroPad numero k de l ordre a la position k."""
    ordre = ordre or NOMS
    lignes = [MARQUE,
              "# Genere a partir de es_input.cfg. Relancer apres « Configurer une manette ».",
              "# Positions : 1 2 3 en haut, 4 5 6 en bas, comme dans l assistant."]
    if jeu:
        lignes.append("# %s : le coeur range ses boutons %s" % (jeu, " ".join(ordre)))
    for joueur in sorted(postes):
        ids = postes[joueur]
        for position, (role, _) in enumerate(ORDRE):
            numero = ids.get(role, ids.get(AUTRE_NOM.get(role, "")))
            if numero is None:
                raise SystemExit("poste %d : le role %s manque dans es_input.cfg" % (joueur, role))
            lignes.append('input_player%d_%s_btn = "%d"' % (joueur, ordre[position], numero))
    return "\n".join(lignes) + "\n"


def ecrire(chemin, texte):
    provisoire = chemin + ".tmp"
    with open(provisoire, "w") as fh:
        fh.write(texte)
    os.replace(provisoire, chemin)


def par_jeu(dossier, postes, entrees, systeme, retirer, voir):
    """Un <rom>.retroarch.cfg pour chaque jeu que le coeur ne range pas dans
    l ordre habituel ; les notres devenus inutiles sont retires. Un fichier
    par jeu qui n est pas a nous n est jamais touche. Renvoie (ecrits, retires)."""
    ecrits = retires = 0
    roms = {f.rsplit(".", 1)[0]: f for f in os.listdir(dossier) if f.lower().endswith((".zip", ".7z"))}
    for jeu, fichier in sorted(roms.items()):
        chemin = os.path.join(dossier, fichier + ".retroarch.cfg")
        existe = os.path.exists(chemin)
        if existe and not est_a_nous(chemin):
            continue
        fiche = (entrees or {}).get(jeu) or {}
        ordre = ordre_du_jeu(fiche.get("retropad"))
        if not retirer and ordre != NOMS:
            texte = contenu(postes, ordre, jeu)
            if voir:
                print("--- %s\n%s" % (chemin, texte))
            elif not existe or open(chemin).read() != texte:
                ecrire(chemin, texte)
                ecrits += 1
        elif existe and not voir:
            os.remove(chemin)
            retires += 1
    return ecrits, retires


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
    p.add_argument("--entrees", help="releve de relever-entrees.py : un fichier par jeu range autrement")
    a = p.parse_args()

    postes = None if a.retirer else lire_ids(a.es_input)
    texte = None if a.retirer else contenu(postes)
    entrees = None
    if a.entrees:
        import json
        with open(a.entrees) as fh:
            entrees = json.load(fh).get("jeux", {})
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
            _, retires = par_jeu(dossier, None, None, systeme, True, False)
            if retires:
                print("%s : %d fichier(s) par jeu retire(s)" % (systeme, retires))
            continue
        if entrees is not None:
            ecrits, retires = par_jeu(dossier, postes, entrees, systeme, False, a.voir)
            print("%s : par jeu, %d fichier(s) ecrit(s), %d retire(s)" % (systeme, ecrits, retires))
        if a.voir:
            print("--- %s (%s)\n%s" % (systeme, chemin, texte))
            continue
        ecrire(chemin, texte)
        print("%s : %s ecrit" % (systeme, chemin))
    return 0


if __name__ == "__main__":
    sys.exit(main())
