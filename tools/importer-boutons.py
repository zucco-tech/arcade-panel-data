#!/usr/bin/env python3
"""
Construit la base des boutons : combien un jeu en utilise, leur couleur
d'origine sur la vraie borne, et la fonction de chacun.

    python3 importer-boutons.py --jeux credits-arcade.json --base boutons-arcade.json

Rien a mesurer ici, contrairement aux credits : ce sont des metadonnees,
issues de la base MAME publiee par arcade-database. Elles donnent, par jeu :

    input_buttons   : 2
    buttons_colors  : P1_BUTTON1:Blue:Attack;P1_BUTTON2:Black:Jump;...
    nplayers        : "2P sim"

C'est ce qu'il faut pour n'allumer que les boutons utiles, dans les couleurs
du panneau d'epoque, et pour savoir si le joueur 2 a sa place.

Les boutons sont decrits en termes LOGIQUES — BUTTON1, BUTTON2 — jamais en
LED physiques. La correspondance vers une carte donnee appartient au demon,
pas aux donnees : une autre carte, un autre cablage, la base reste bonne.

On interroge un service exterieur : un appel par jeu, espaces, avec reprise
si on relance. Aucune dependance hors bibliotheque standard.
"""

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

SERVICE = "https://adb.arcadeitalia.net/service_scraper.php"
PAUSE = 0.35              # on ne martele pas un service gratuit
TIMEOUT = 12.0
ESSAIS = 2


def interroger(jeu):
    url = "%s?%s" % (SERVICE, urllib.parse.urlencode(
        {"ajax": "query_mame", "game_name": jeu}))
    for essai in range(ESSAIS):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as reponse:
                donnees = json.load(reponse)
            resultats = donnees.get("result") or []
            return resultats[0] if resultats else None
        except (urllib.error.URLError, ValueError, OSError):
            if essai + 1 < ESSAIS:
                time.sleep(1.5)
    return None


def decouper_boutons(brut):
    """'P1_BUTTON1:Blue:Attack;...' -> {'BUTTON1': {couleur, fonction}}"""
    boutons = {}
    for entree in (brut or "").split(";"):
        morceaux = entree.split(":")
        if len(morceaux) < 2 or not morceaux[0].startswith("P1_BUTTON"):
            continue
        nom = morceaux[0][3:]                      # on retire le "P1_"
        couleur = morceaux[1].strip()
        fonction = morceaux[2].strip() if len(morceaux) > 2 else ""
        boutons[nom] = {"couleur": couleur or None, "fonction": fonction or None}
    return boutons


def base_neuve():
    return {
        "format": "recalbox-arcade-boutons",
        "version": 1,
        "description": (
            "Pour chaque jeu arcade : combien de boutons il utilise, la "
            "couleur d'origine de chacun sur la borne, et sa fonction. "
            "Les boutons sont nommes logiquement (BUTTON1, BUTTON2...) : la "
            "correspondance vers les LED d'une carte donnee appartient au "
            "programme qui les allume, pas a ces donnees."),
        "source": {
            "quoi": "metadonnees MAME publiees par arcade-database",
            "ou": "https://adb.arcadeitalia.net",
        },
        "jeux": {},
        "absents": {},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--jeux", required=True,
                        help="base de credits, ou fichier texte d'un nom par ligne")
    parser.add_argument("--base", required=True, help="fichier a ecrire")
    parser.add_argument("--limite", type=int, default=0)
    args = parser.parse_args()

    # La liste des jeux : soit une base de credits, soit une liste brute.
    if args.jeux.endswith(".json"):
        credits = json.load(open(args.jeux))
        noms = sorted({cle.split("/", 1)[-1] for cle in credits.get("jeux", {})})
    else:
        noms = [l.strip() for l in open(args.jeux) if l.strip()]

    try:
        base = json.load(open(args.base))
    except (IOError, OSError, ValueError):
        base = base_neuve()

    deja = set(base["jeux"]) | set(base["absents"])
    restants = [n for n in noms if n not in deja]
    if args.limite:
        restants = restants[:args.limite]
    print("%d jeu(x) a interroger (%d deja connus)" % (len(restants), len(deja)))

    ajoutes = absents = 0
    for i, jeu in enumerate(restants, 1):
        fiche = interroger(jeu)
        if fiche is None or not fiche.get("input_buttons"):
            base["absents"][jeu] = "sans donnees"
            absents += 1
        else:
            base["jeux"][jeu] = {
                "nom": fiche.get("title"),
                "nombre": int(fiche["input_buttons"]),
                "boutons": decouper_boutons(fiche.get("buttons_colors")),
                "commandes": fiche.get("input_controls"),
                "joueurs": fiche.get("players"),
                "mode": fiche.get("nplayers"),
            }
            ajoutes += 1
        if i % 50 == 0 or i == len(restants):
            with open(args.base + ".tmp", "w") as fh:
                json.dump(base, fh, indent=2, sort_keys=True, ensure_ascii=False)
                fh.write("\n")
            os.replace(args.base + ".tmp", args.base)
            print("  %d/%d — %d releves, %d sans donnees"
                  % (i, len(restants), ajoutes, absents), flush=True)
        time.sleep(PAUSE)

    print("\ntermine : %d jeux avec boutons, %d sans" % (len(base["jeux"]), len(base["absents"])))


if __name__ == "__main__":
    main()
