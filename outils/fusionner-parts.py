#!/usr/bin/env python3
"""Replie les parts du balayage parallele dans la base principale.

Quatre releves tournent en meme temps, chacun dans son fichier : sans cela
ils s ecraseraient l un l autre a chaque ecriture. Ce programme rassemble
leur travail, puis vide les parts.

    python3 fusionner-parts.py --base .../credits-arcade.json --parts .../parts

Une fiche mesuree l emporte toujours sur un ecart : un jeu peut avoir ete
ecarte hier et mesure aujourd hui.
"""

import argparse
import json
import os


def charger(chemin):
    try:
        with open(chemin) as fh:
            return json.load(fh)
    except (IOError, OSError, ValueError):
        return {"jeux": {}, "difficiles": {}}


def ecrire(chemin, base):
    provisoire = chemin + ".tmp"
    with open(provisoire, "w") as fh:
        json.dump(base, fh, indent=1, ensure_ascii=False)
    os.replace(provisoire, chemin)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--base", required=True)
    p.add_argument("--parts", required=True)
    a = p.parse_args()

    base = charger(a.base)
    appris = ecartes = 0
    if not os.path.isdir(a.parts):
        print("aucune part a replier")
        return
    for nom in sorted(os.listdir(a.parts)):
        if not nom.endswith(".json"):
            continue
        chemin = os.path.join(a.parts, nom)
        part = charger(chemin)
        for cle, fiche in part.get("jeux", {}).items():
            base["jeux"][cle] = fiche
            base["difficiles"].pop(cle, None)
            appris += 1
        for cle, ecart in part.get("difficiles", {}).items():
            if cle not in base["jeux"]:
                base["difficiles"][cle] = ecart
                ecartes += 1
        os.remove(chemin)
    ecrire(a.base, base)
    print("%d fiche(s) et %d ecart(s) replies ; la base en compte %d et %d"
          % (appris, ecartes, len(base["jeux"]), len(base["difficiles"])))


if __name__ == "__main__":
    main()
