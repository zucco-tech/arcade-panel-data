#!/usr/bin/env python3
"""
Explique pourquoi des jeux ont resiste au releve, et dit lesquels valent
d'etre repris.

    python3 analyser-difficiles.py --base donnees/credits-arcade.json

Un balayage laisse toujours des jeux de cote. La question utile n'est pas
combien, mais **pourquoi** — et surtout lesquels sont recuperables. Ce
programme trie les echecs par cause, croise avec ce qu'on sait par ailleurs
(un parent deja mesure, une piste de cheat), et propose une conduite a tenir
pour chaque groupe.

Aucune mesure, aucun jeu lance : il ne fait que lire la base.
"""

import argparse
import collections
import json
import os
import re

# Ce que chaque cause veut dire, et ce qu'on peut en faire.
CAUSES = {
    "RAM non lisible": (
        "le coeur n expose pas sa memoire",
        "sans appel — aucun releve n est possible sur ce coeur"),
    "aucun candidat": (
        "la piece n a rien fait monter",
        "souvent recuperable : jeu pas encore pret, ou compteur en BCD"),
    "candidats non confirmes": (
        "des octets ont bouge mais le START n a rien confirme",
        "a reprendre avec plus de pieces et un START mieux place"),
    "jeu inanime": (
        "la RAM ne bouge pas du tout",
        "le jeu est bloque au demarrage — verification de ROM, cle manquante"),
    "compteur introuvable": (
        "trop de candidats, jamais reduits",
        "a reprendre avec davantage de pieces"),
}


def parents_du_dat(chemin):
    """{jeu: parent} depuis un DAT ClrMamePro, s il est fourni."""
    if not chemin or not os.path.exists(chemin):
        return {}
    texte = open(chemin, encoding="utf-8", errors="replace").read()
    return {n: (c or None) for n, c in
            re.findall(r'<game name="([^"]+)"(?:\s+cloneof="([^"]+)")?', texte)}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--base", required=True)
    parser.add_argument("--dat", help="DAT ClrMamePro, pour les liens parent/clone")
    parser.add_argument("--systeme", help="n analyser qu un systeme")
    args = parser.parse_args()

    base = json.load(open(args.base))
    durs = base.get("difficiles") or {}
    jeux = base.get("jeux") or {}
    pistes = base.get("pistes") or {}
    parents = parents_du_dat(args.dat)

    if args.systeme:
        durs = {c: d for c, d in durs.items()
                if (d.get("systeme") or c.split("/")[0]) == args.systeme}

    if not durs:
        print("Aucun jeu difficile : tout est passe.")
        return

    mesures = {c.split("/", 1)[-1] for c in jeux}
    par_cause = collections.defaultdict(list)
    for cle, fiche in durs.items():
        par_cause[fiche.get("raison", "?")].append((cle, fiche))

    total = len(durs)
    print("%d jeu(x) ecarte(s)%s\n" % (total, " sur " + args.systeme if args.systeme else ""))

    recuperables = []
    for cause, membres in sorted(par_cause.items(), key=lambda x: -len(x[1])):
        quoi, conduite = CAUSES.get(cause, (cause, "cause inconnue"))
        print("%d — %s" % (len(membres), quoi))
        print("     %s" % conduite)

        # Un clone dont le parent est mesure herite d une piste solide.
        avec_parent = [c for c, _ in membres
                       if parents.get(c.split("/")[-1]) in mesures]
        avec_piste = [c for c, _ in membres if c.split("/")[-1] in pistes]
        premier_essai = [c for c, f in membres if f.get("essais", 1) < 2]

        if avec_parent:
            print("     dont %d sont des clones d un jeu deja mesure — "
                  "l adresse du parent leur sert de piste sure" % len(avec_parent))
            recuperables += avec_parent
        if avec_piste:
            print("     dont %d ont une piste de cheat inexploitee" % len(avec_piste))
        if premier_essai and cause not in ("RAM non lisible",):
            print("     dont %d n ont ete essayes qu une fois" % len(premier_essai))
            recuperables += premier_essai
        print("     exemples : %s" % ", ".join(c.split("/")[-1] for c, _ in membres[:6]))
        print()

    recuperables = sorted(set(recuperables))
    print("-" * 64)
    print("%d jeu(x) valent d etre repris, soit %.0f %% des ecartes"
          % (len(recuperables), 100.0 * len(recuperables) / total))
    definitifs = total - len(recuperables)
    print("%d sont sans appel — le coeur ne montre pas sa memoire" % definitifs)
    if recuperables:
        print("\nPour les reprendre :")
        print("    python3 nuit-credits.py --direct --rapide --reessayer \\")
        print("      --systeme %s --base %s" % (args.systeme or "fbneo", args.base))


if __name__ == "__main__":
    main()
