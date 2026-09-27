#!/usr/bin/env python3
"""La liste des jeux dont on n a pas trouve le compteur de credits.

    python3 liste-jeux-restants.py > /mnt/recalbox/jeux-restants.md

Ecrite pour etre lue par quelqu un qui connait les bornes, pas par un
programme : les jeux sont groupes par RAISON, avec en clair ce que la
machine a fait, pour qu on puisse dire « celui-la je sais pourquoi » ou
« celui-la devrait marcher, regarde encore ».

Les familles (un jeu et ses variantes : 1944, 1944ad, 1944d...) sont
rassemblees sur une ligne : sinon la liste fait trois mille lignes dont
les neuf dixiemes sont des clones du meme jeu.
"""
import collections
import json
import re
import sys

BASE = "/mnt/recalbox/donnees/credits-arcade.json"

# Ce qu il faut comprendre de chaque raison, en francais.
EXPLICATIONS = {
    "le coeur refuse la rom":
        "L emulateur affiche « This romset is known but marked as not working ». "
        "Il ne sait pas faire tourner cette carte : il n y a pas de partie, donc "
        "pas de credit a trouver. **Rien a esperer sans une nouvelle version de "
        "l emulateur.**",
    "romset inconnu de ce coeur":
        "L emulateur ne connait pas ce nom de set. Souvent un romset d une autre "
        "version que celle qu il attend.",
    "candidats non confirmes":
        "Le jeu tourne, la piece est comptee, mais **rien ne redescend quand on "
        "appuie sur START**. Soit le credit se consomme autrement, soit il est "
        "range d une facon qu on ne sait pas lire. **C est ici qu il y a le plus "
        "a gagner si tu reconnais un jeu.**",
    "aucun candidat":
        "Le jeu tourne mais **aucun octet ne bouge quand on met une piece**. "
        "Le monnayeur n est peut-etre pas sur SELECT, ou la carte attend "
        "autre chose (choix de langue, ecran de service).",
    "delai depasse":
        "La machine est trop lente a demarrer pour qu on puisse la mesurer "
        "(souvent du materiel 3D emule au ralenti).",
    "jeu inanime":
        "Rien ne bouge a l ecran : la machine ne demarre pas vraiment.",
    "ne demarre pas":
        "L emulateur n a pas reussi a lancer le jeu.",
    "pas de monnayeur declare":
        "La machine n a **pas de fente a pieces** : un BIOS, un prototype, une "
        "borne de service. Il n y a pas de credit, c est normal.",
    "aucune RAM declaree":
        "L emulateur n expose aucune memoire pour cette machine.",
    "chargee, ni memoire publiee ni sauvegarde d etat":
        "Le jeu se charge, mais l emulateur **ne montre ni sa memoire ni une "
        "sauvegarde d etat**. Aucune porte pour lire le credit. Beaucoup sont "
        "des BIOS ou des cartes de service (`gg-bios`, `naomigd`, `uni-bios`) "
        "qui n ont pas de credits du tout.",
    "chargee, mais le coeur ne publie pas sa memoire":
        "Le jeu se charge mais l emulateur garde sa memoire pour lui. "
        "On sait contourner par les sauvegardes d etat quand il les accepte.",
}

SYSTEMES = {"finalburn-neo": "FBNeo", "mame": "MAME", "flycast": "Naomi / Atomiswave",
            "mednafen-st-v": "ST-V"}


def famille(nom):
    """« 1944ad » -> « 1944 » : le jeu d origine, sans son suffixe de variante."""
    return re.sub(r"(?<=[a-z0-9])(?:[a-z]{1,3}\d?|\d)$", "", nom) or nom


def raison_courte(texte):
    """La raison, sans le detail technique entre parentheses."""
    return re.sub(r"\s*\(.*", "", str(texte or "inconnue")).strip()


def main():
    with open(BASE) as fh:
        base = json.load(fh)
    trouves, durs = base.get("jeux") or {}, base.get("difficiles") or {}

    par_raison = collections.defaultdict(lambda: collections.defaultdict(list))
    for cle, fiche in durs.items():
        coeur = cle.split("/", 1)[0]
        jeu = cle.split("/", 1)[1]
        # Un jeu couvert par un AUTRE emulateur n est pas un probleme.
        if any(("%s/%s" % (autre, jeu)) in trouves
               for autre in SYSTEMES if autre != coeur):
            continue
        par_raison[raison_courte(fiche.get("raison"))][SYSTEMES.get(coeur, coeur)].append(jeu)

    restants = sum(len(j) for s in par_raison.values() for j in s.values())
    print("# Les jeux dont on n a pas trouve le compteur de credits")
    print()
    print("%d jeux trouves, %d sans solution a ce jour." % (len(trouves), restants))
    print()
    print("Les jeux couverts par un autre emulateur (FBNeo refuse, MAME le joue)")
    print("ne sont pas listes : sur la borne, ils marchent.")
    print()
    print("Les variantes d un meme jeu sont regroupees : « 1944 (+4) » veut dire")
    print("1944 et quatre de ses versions.")
    print()

    for raison in sorted(par_raison, key=lambda r: -sum(len(j) for j in par_raison[r].values())):
        total = sum(len(j) for j in par_raison[raison].values())
        print("---")
        print()
        print("## %s — %d jeux" % (raison, total))
        print()
        print(EXPLICATIONS.get(raison, "") or "_Pas d explication enregistree._")
        print()
        for systeme in sorted(par_raison[raison]):
            jeux = par_raison[raison][systeme]
            groupes = collections.defaultdict(list)
            for j in jeux:
                groupes[famille(j)].append(j)
            morceaux = []
            for tete in sorted(groupes):
                n = len(groupes[tete]) - 1
                morceaux.append("`%s`%s" % (sorted(groupes[tete])[0],
                                            " (+%d)" % n if n else ""))
            print("**%s** — %d jeux, %d familles" % (systeme, len(jeux), len(groupes)))
            print()
            print(", ".join(morceaux))
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
