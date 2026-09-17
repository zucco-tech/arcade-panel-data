#!/usr/bin/env python3
"""Donne de vraies couleurs de boutons a plus de jeux d arcade, sans en inventer.

    python3 heriter-couleurs.py --base .../boutons-arcade.json --liste mame0278lx.zip

arcade-database ne connait les couleurs du panneau que pour une minorite de
jeux (868 sur 7024 le 17/09/2026). Deux sources sures completent :

  1. Les VARIANTES d un meme jeu (1942a, 1942b... de 1942) ont le meme panneau :
     une variante sans couleurs prend celles de son jeu d origine, ou d une
     autre variante de la famille, si le nombre de boutons est le meme. La
     famille vient de la liste officielle de MAME (-listxml, champ cloneof).
  2. Les jeux NEO GEO MVS (sourcefile neogeo.cpp) : panneau standard,
     A rouge, B jaune, C vert, D bleu.

Chaque couleur ajoutee le dit dans la fiche (« couleurs_reprises_de » ou
« couleurs_standard ») : on sait toujours d ou elle vient. Une fiche qui a
deja ses couleurs n est jamais touchee.
"""

import argparse
import collections
import json
import os
import zipfile
import xml.etree.ElementTree as ET

NEO_GEO = ["Red", "Yellow", "Green", "Blue"]


def familles(liste):
    """{machine: (jeu d origine ou None, fichier source)} depuis le -listxml zippe."""
    rendu = {}
    with zipfile.ZipFile(liste) as z:
        nom = next(n for n in z.namelist() if n.endswith(".xml"))
        with z.open(nom) as fh:
            for _, el in ET.iterparse(fh, events=("end",)):
                if el.tag == "machine":
                    rendu[el.get("name")] = (el.get("cloneof"), el.get("sourcefile") or "")
                    el.clear()
    return rendu


def colore(fiche):
    return any((b or {}).get("couleur") for b in (fiche.get("boutons") or {}).values())


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--base", default="/mnt/recalbox/donnees/boutons-arcade.json")
    p.add_argument("--liste", required=True, help="mameXXXXlx.zip, la liste officielle de MAME")
    p.add_argument("--sec", action="store_true", help="compter sans ecrire")
    a = p.parse_args()

    base = json.load(open(a.base))
    jeux = base["jeux"]
    info = familles(a.liste)
    origine = {n: (info.get(n, (None, ""))[0] or n) for n in jeux}
    membres = collections.defaultdict(list)
    for n in sorted(jeux):
        membres[origine[n]].append(n)
    colores = {n for n, f in jeux.items() if colore(f)}

    reprises = standards = 0
    for n, fiche in sorted(jeux.items()):
        if n in colores:
            continue
        tete = origine[n]
        donneurs = [m for m in [tete] + membres[tete]
                    if m in colores and jeux[m].get("nombre") == fiche.get("nombre")]
        if donneurs:
            modele = jeux[donneurs[0]]["boutons"]
            fiche["boutons"] = {k: dict(v) for k, v in modele.items()}
            fiche["couleurs_reprises_de"] = donneurs[0]
            reprises += 1
        elif info.get(n, (None, ""))[1].endswith("neogeo.cpp") and 0 < (fiche.get("nombre") or 0) <= 4:
            fiche["boutons"] = {"BUTTON%d" % (i + 1): {"couleur": c}
                                for i, c in enumerate(NEO_GEO[:fiche["nombre"]])}
            fiche["couleurs_standard"] = "Neo Geo MVS : A rouge, B jaune, C vert, D bleu"
            standards += 1

    couverture = base.setdefault("couverture", {})
    couverture["jeux_avec_couleurs_reprises_d_une_variante"] = reprises
    couverture["jeux_avec_couleurs_standard_neo_geo"] = standards
    couverture["jeux_avec_couleurs"] = sum(1 for f in jeux.values() if colore(f))
    print("%d reprises d une variante, %d standard Neo Geo : %d jeux sur %d ont leurs couleurs"
          % (reprises, standards, couverture["jeux_avec_couleurs"], len(jeux)))
    if not a.sec:
        provisoire = a.base + ".tmp"
        with open(provisoire, "w") as fh:
            json.dump(base, fh, indent=1, ensure_ascii=False, sort_keys=True)
        os.replace(provisoire, a.base)


if __name__ == "__main__":
    main()
