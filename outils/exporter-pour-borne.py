#!/usr/bin/env python3
"""
Ecrit la base des credits dans la forme que lit la borne : un fichier par
systeme.

Le releveur indexe ses fiches par COEUR — « finalburn-neo/1942 » — parce que
c est le coeur qui decide de la disposition memoire. Le demon des LED, lui,
cherche par SYSTEME, celui qu EmulationStation annonce : « fbneo », puis
« 1942 ». Il ne charge que le fichier du systeme du jeu lance.

    dossier/
        fbneo.json      les fiches fbneo, indexees par nom de set
        mame.json       ...
        pistes.json     les adresses de cheats, indexees par set (tous systemes)

Chaque fiche sait sous quel systeme elle a ete relevee. Quand deux coeurs ont
mesure le meme jeu, on garde celui qui a une consommation confirmee. Le
fichier appris.json du dossier, ecrit par la borne, n est jamais touche ici.

    python3 exporter-pour-borne.py --base .../credits-arcade.json --dossier .../credits
"""

import argparse
import json
import os


def ecrire_json(chemin, contenu):
    """Ecriture atomique : la borne ne verra jamais un fichier a moitie ecrit."""
    provisoire = chemin + ".tmp"
    with open(provisoire, "w") as fh:
        json.dump(contenu, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
    os.replace(provisoire, chemin)


def par_systeme(entrees):
    """Regroupe des fiches « cle -> fiche » par systeme, indexees par nom de set.

    Deux coeurs ayant mesure le meme jeu : on garde la mesure la mieux prouvee.
    Renvoie (groupes, doublons).
    """
    groupes, doublons = {}, 0
    for cle, fiche in entrees.items():
        jeu = fiche.get("jeu") or cle.split("/", 1)[-1]
        systeme = fiche.get("systeme")
        if not systeme:
            continue
        # Une fiche lue dans une sauvegarde d etat porte une POSITION dans cet
        # etat, valable pour le seul coeur qui l a ecrite (assault : 0x20026
        # sur le PC, 0x20036 sur la borne). Le demon de la borne sait la
        # relire depuis le 26/09 -- mais seulement si c est la borne elle-meme
        # qui a mesure. Ce que le PC a lu ainsi reste ici.
        ram = fiche.get("ram") or {}
        if ram.get("commande") == "sauvegarde d etat" and ram.get("hote") != "BORNEARCADE":
            continue
        jeux = groupes.setdefault(systeme, {})
        ancienne = jeux.get(jeu)
        if ancienne is not None:
            doublons += 1
            a = (ancienne.get("credits") or {}).get("verifie_consommation")
            b = (fiche.get("credits") or {}).get("verifie_consommation")
            if a and not b:
                continue
        jeux[jeu] = fiche
    return groupes, doublons


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("--base", required=True)
    p.add_argument("--dossier", required=True,
                   help="dossier de sortie : un <systeme>.json par systeme, plus pistes.json")
    p.add_argument("--fiches-mame", default=None,
                   help="ecrit aussi la liste que lit mame-rapport.lua sur la borne : "
                        "une ligne par jeu MAME, « nom adresse zone »")
    args = p.parse_args()

    source = json.load(open(args.base))
    jeux, doublons = par_systeme(source.get("jeux") or {})
    difficiles, _ = par_systeme(source.get("difficiles") or {})
    os.makedirs(args.dossier, exist_ok=True)

    entete = {
        "format": "recalbox-arcade-credits (un fichier par systeme, pour la borne)",
        "version": source.get("version"),
        "description": ("Adresse RAM du compteur de credits de chaque jeu de "
                        "ce systeme, indexee par nom de set. Se lit par "
                        "l'interface reseau de RetroArch : READ_CORE_RAM "
                        "<adresse> 1 en UDP sur le port 55355."),
    }
    for systeme in sorted(set(jeux) | set(difficiles)):
        contenu = dict(entete, systeme=systeme,
                       jeux=jeux.get(systeme, {}),
                       difficiles=difficiles.get(systeme, {}))
        ecrire_json(os.path.join(args.dossier, systeme + ".json"), contenu)
        print("%-10s %5d fiche(s), %5d difficile(s)"
              % (systeme, len(contenu["jeux"]), len(contenu["difficiles"])))

    # Les pistes visent le processeur emule, pas un coeur : un seul fichier.
    ecrire_json(os.path.join(args.dossier, "pistes.json"), {
        "format": "recalbox-arcade-credits (pistes, pour la borne)",
        "description": ("Adresse d'un cheat « credits infinis », par nom de "
                        "set : la ou chercher en premier quand un jeu est "
                        "inconnu. A verifier a la piece, jamais a croire."),
        "sources": source.get("sources", {}),
        "pistes": source.get("pistes", {}),
    })

    if args.fiches_mame:
        # Le Lua de la borne n a pas de lecteur JSON : une ligne par jeu,
        # « nom adresse zone ». L adresse est un decalage dans le share
        # quand la zone commence par « : », une adresse du processeur sinon.
        lignes = []
        for jeu, fiche in sorted(jeux.get("mame", {}).items()):
            credits = fiche.get("credits") or {}
            zone = (fiche.get("ram") or {}).get("zone") or "?"
            if credits.get("adresse") is None or " " in str(zone):
                continue
            lignes.append("%s %d %s" % (jeu, credits["adresse"], zone))
        with open(args.fiches_mame, "w") as liste:
            liste.write("\n".join(lignes) + "\n")
        print("%d fiche(s) MAME ecrites pour le Lua de la borne" % len(lignes))
    print("%d fiches ecrites (%d doublons de coeur fusionnes), %d pistes"
          % (sum(len(j) for j in jeux.values()), doublons,
             len(source.get("pistes") or {})))


if __name__ == "__main__":
    main()
