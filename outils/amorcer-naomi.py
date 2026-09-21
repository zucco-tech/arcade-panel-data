#!/usr/bin/env python3
"""Prepare le fichier de travail de la recherche Naomi avant chaque depart.

La campagne replie ce fichier dans la base commune puis l efface. Sans cette
amorce, un redemarrage du service repartirait de zero et remesurerait des
centaines de jeux deja faits. On le reconstruit donc depuis la base, qui est
la seule memoire durable.
"""
import json
import os

BASE = "/mnt/recalbox/donnees/credits-arcade.json"
PART = "/mnt/recalbox/donnees/parts-naomi/part-1.json"
COEUR = "flycast/"

def main():
    try:
        with open(BASE) as fh:
            base = json.load(fh)
    except (IOError, OSError, ValueError):
        return 0                      # pas de base : on laisse faire
    part = {"jeux": {}, "difficiles": {}}
    if os.path.exists(PART):
        try:
            with open(PART) as fh:
                part = json.load(fh)   # ce qui a ete trouve depuis le repli
        except (IOError, OSError, ValueError):
            part = {"jeux": {}, "difficiles": {}}
    for section in ("jeux", "difficiles"):
        for cle, fiche in (base.get(section) or {}).items():
            if cle.startswith(COEUR):
                part.setdefault(section, {}).setdefault(cle, fiche)
    os.makedirs(os.path.dirname(PART), exist_ok=True)
    provisoire = PART + ".tmp"
    with open(provisoire, "w") as fh:
        json.dump(part, fh, indent=1, ensure_ascii=False)
    os.replace(provisoire, PART)
    print("amorce : %d trouves, %d ecartes"
          % (len(part["jeux"]), len(part["difficiles"])))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
