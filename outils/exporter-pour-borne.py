#!/usr/bin/env python3
"""
Ecrit la base des credits dans la forme attendue par la borne.

Le releveur indexe ses fiches par COEUR — « finalburn-neo/1942 » — parce que
c est le coeur qui decide de la disposition memoire. Mais le demon des LED,
lui, cherche par SYSTEME : « fbneo/1942 ». Deployer la base telle quelle le
laisse sans rien trouver, et il reapprend tout depuis zero.

Ce script traduit, sans rien perdre : chaque fiche sait sous quel systeme
elle a ete relevee. Quand deux coeurs ont mesure le meme jeu, on garde celui
qui a une consommation confirmee.

    python3 exporter-pour-borne.py --base .../credits-arcade.json --sortie .../pour-borne.json
"""

import argparse
import json
import os


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("--base", required=True)
    p.add_argument("--sortie", required=True)
    args = p.parse_args()

    source = json.load(open(args.base))
    sortie = dict(source)
    jeux = {}
    doublons = 0
    for cle, fiche in (source.get("jeux") or {}).items():
        jeu = fiche.get("jeu") or cle.split("/", 1)[-1]
        systeme = fiche.get("systeme")
        # Les fiches MAME donnent une adresse dans l espace du processeur,
        # que le demon de la borne ne sait pas encore lire (il passe par
        # READ_CORE_RAM, que MAME ne sert pas). On les garde dans la base,
        # on ne les exporte pas tant que la lecture par Lua n existe pas
        # cote borne — sinon le demon tenterait des lectures qui echouent.
        if (fiche.get("releve") or {}).get("methode") == "lua dans mame":
            continue
        if not systeme:
            continue
        neuve = "%s/%s" % (systeme, jeu)
        ancienne = jeux.get(neuve)
        if ancienne is not None:
            doublons += 1
            # On garde la mesure la mieux prouvee.
            a = (ancienne.get("credits") or {}).get("verifie_consommation")
            b = (fiche.get("credits") or {}).get("verifie_consommation")
            if a and not b:
                continue
        jeux[neuve] = fiche
    sortie["jeux"] = jeux

    durs = {}
    for cle, fiche in (source.get("difficiles") or {}).items():
        jeu = fiche.get("jeu") or cle.split("/", 1)[-1]
        systeme = fiche.get("systeme")
        if systeme:
            durs["%s/%s" % (systeme, jeu)] = fiche
    sortie["difficiles"] = durs
    sortie["format"] = "recalbox-arcade-credits (index par systeme, pour la borne)"

    provisoire = args.sortie + ".tmp"
    with open(provisoire, "w") as fh:
        json.dump(sortie, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
    os.replace(provisoire, args.sortie)
    print("%d fiches ecrites (%d doublons de coeur fusionnes)" % (len(jeux), doublons))


if __name__ == "__main__":
    main()
