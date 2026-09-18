#!/usr/bin/env python3
"""Transforme le releve des coeurs en table « quels boutons ce systeme utilise ».

    python3 exporter-boutons-systemes.py --releve boutons-systemes.json \
        --sortie /mnt/recalbox/donnees/boutons-systemes.json

Le releve (outils/relever-boutons-systemes.py, execute sur la borne) donne,
pour chaque systeme, ce que son coeur libretro annonce bouton par bouton.
Tout n en est pas un bouton de la machine : on ecarte

  - les axes et les cadrans (« Paddle », « Analog », « Cursor ») ;
  - le clavier et la souris emules (« Key », « Mouse », « Touchscreen ») ;
  - les fonctions de service du coeur (« Turbo », « Pause », « Show Keypad »,
    « Change drive », « Restart », « Mode »...).

Un systeme dont le coeur a bien charge le jeu et n annonce aucun bouton (le
Matra Alice, le PC-98 : ils se jouent au clavier) est note « aucun bouton » :
le panneau n en allumera aucun, au lieu des six par defaut. Un coeur qui a
plante ou qui n a pas charge le jeu ne conclut rien : le systeme garde le
comportement d avant.
"""

import argparse
import json
import re
import time

PAS_UN_BOUTON = re.compile(
    r"mouse|touchscreen|keyboard|on-screen|key sel|turbo|menu|shift|virtual|pointer|"
    r"stylus|mic |swap|lid|save|load|reset|fast forward|screen|paddle|analog|cursor|"
    r"keypad|show |hide |change drive|aux|sound|pause|mode|rewind|forward|help|abc|"
    r"^on$|^off$|restart|dollar|^key|key$", re.I)
ROLES = ("b", "a", "y", "x", "l", "r")


def retenus(boutons):
    """Les roles RetroPad qui portent un vrai bouton de la machine, sans doublon."""
    rendu = []
    for role, nom in boutons:
        if role in ROLES and role not in [r for r, _ in rendu] and not PAS_UN_BOUTON.search(nom):
            rendu.append((role, nom.strip()))
    return rendu


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--releve", required=True)
    p.add_argument("--sortie", required=True)
    a = p.parse_args()
    with open(a.releve) as fh:
        releve = json.load(fh)

    systemes, aucun, ignores = {}, [], []
    for nom, fiche in sorted(releve.items()):
        if fiche.get("erreur"):
            ignores.append(nom)
            continue
        gardes = retenus(fiche.get("boutons") or [])
        if gardes:
            systemes[nom] = {
                "coeur": fiche.get("coeur"),
                "roles": [r for r, _ in gardes],
                "fonctions": [n for _, n in gardes],
            }
        elif fiche.get("charge"):
            systemes[nom] = {"coeur": fiche.get("coeur"), "roles": [], "fonctions": [],
                             "note": "aucun bouton : cette machine se joue au clavier"}
            aucun.append(nom)
        else:
            ignores.append(nom)

    contenu = {
        "format": "panneau-allinone (boutons par systeme)",
        "description": ("Les boutons que le coeur de chaque systeme lit vraiment, en noms "
                        "RetroPad, releves en chargeant le coeur sur la borne "
                        "(outils/relever-boutons-systemes.py). Le panneau n allume que "
                        "ceux-la. « roles » vide = machine sans bouton (clavier)."),
        "releve_le": time.strftime("%Y-%m-%d"),
        "systemes": systemes,
    }
    provisoire = a.sortie + ".tmp"
    with open(provisoire, "w") as fh:
        json.dump(contenu, fh, indent=1, ensure_ascii=False, sort_keys=True)
    import os
    os.replace(provisoire, a.sortie)
    print("%d systeme(s) releves, dont %d sans aucun bouton ; %d sans conclusion (%s)"
          % (len(systemes), len(aucun), len(ignores), " ".join(ignores)))


if __name__ == "__main__":
    main()
