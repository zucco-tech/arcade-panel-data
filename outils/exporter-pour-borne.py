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
    p.add_argument("--fiches-mame", default=None,
                   help="ecrit aussi la liste que lit mame-rapport.lua sur la borne : "
                        "une ligne par jeu MAME, « nom adresse zone »")
    args = p.parse_args()

    source = json.load(open(args.base))
    sortie = dict(source)
    jeux = {}
    doublons = 0
    for cle, fiche in (source.get("jeux") or {}).items():
        jeu = fiche.get("jeu") or cle.split("/", 1)[-1]
        systeme = fiche.get("systeme")
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
    if args.fiches_mame:
        # Le Lua de la borne n a pas de lecteur JSON : une ligne par jeu,
        # « nom adresse zone ». L adresse est un decalage dans le share
        # quand la zone commence par « : », une adresse du processeur sinon.
        lignes = []
        for cle, fiche in sorted(jeux.items()):
            if fiche.get("systeme") != "mame":
                continue
            credits = fiche.get("credits") or {}
            zone = (fiche.get("ram") or {}).get("zone") or "?"
            if credits.get("adresse") is None or " " in str(zone):
                continue
            lignes.append("%s %d %s" % (fiche["jeu"], credits["adresse"], zone))
        with open(args.fiches_mame, "w") as liste:
            liste.write("\n".join(lignes) + "\n")
        print("%d fiche(s) MAME ecrites pour le Lua de la borne" % len(lignes))
    os.replace(provisoire, args.sortie)
    print("%d fiches ecrites (%d doublons de coeur fusionnes)" % (len(jeux), doublons))


if __name__ == "__main__":
    main()
