#!/usr/bin/env python3
"""Ecrit ordre-fbneo.json : l ordre des boutons des jeux FBNeo que le coeur ne
range pas dans l ordre b, a, y, x, l, r.

    python3 exporter-ordre-fbneo.py --entrees .../entrees-retropad.json --sortie .../ordre-fbneo.json

Sur la borne, les boutons suivent la configuration de Recalbox et ne sont
jamais deplaces (choix du 17/09/2026). Les LED, elles, doivent savoir quel
bouton du jeu chaque position porte : sur Street Fighter II, le bouton 1 du
jeu (poing faible) est sur y, pas sur b. Ce fichier le leur dit.

Seuls les jeux hors de l ordre habituel y sont (808 sur 7760) : le reste se
deduit, et le fichier reste petit a lire pour le Raspberry.
"""

import argparse
import json
import os

HABITUEL = ["b", "a", "y", "x", "l", "r"]


def ordre(retropad):
    """Les six noms RetroPad dans l ordre du jeu : ceux que le coeur annonce
    d abord, puis les autres dans l ordre habituel (meme regle que
    aligner-boutons.py, pour que les deux disent la meme chose)."""
    vus = [n for n in (retropad or []) if n in HABITUEL]
    return vus + [n for n in HABITUEL if n not in vus]


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--entrees", default="/mnt/recalbox/donnees/entrees-retropad.json")
    p.add_argument("--sortie", required=True)
    a = p.parse_args()
    with open(a.entrees) as fh:
        jeux = json.load(fh).get("jeux") or {}
    autres = {}
    for jeu, fiche in sorted(jeux.items()):
        o = ordre(fiche.get("retropad"))
        if fiche.get("retropad") and o != HABITUEL:
            autres[jeu] = o
    contenu = {
        "format": "panneau-allinone (ordre des boutons FBNeo)",
        "description": ("Pour chaque jeu FBNeo dont le coeur ne range pas les boutons "
                        "dans l ordre b, a, y, x, l, r : le nom RetroPad du bouton 1, 2, "
                        "3... du jeu. Lu par cablage.py pour colorer les LED."),
        "jeux": autres,
    }
    provisoire = a.sortie + ".tmp"
    with open(provisoire, "w") as fh:
        json.dump(contenu, fh, separators=(",", ":"), sort_keys=True)
    os.replace(provisoire, a.sortie)
    print("%d jeu(x) hors de l ordre habituel sur %d" % (len(autres), len(jeux)))


if __name__ == "__main__":
    main()
