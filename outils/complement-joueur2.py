#!/usr/bin/env python3
"""
Ajoute l adresse du compteur de credits du JOUEUR 2 aux fiches deja mesurees.

    python3 complement-joueur2.py --base /mnt/recalbox/donnees/credits-arcade.json

Pourquoi une passe a part : sur une borne a deux postes, chaque joueur
alimente SON compteur tant que personne n a appuye sur START. Le demon des
LED a donc besoin des deux adresses pour eclairer juste — sinon le joueur 2
qui vient de payer ne voit pas son bouton START clignoter.

Pourquoi on ne devine pas l adresse a cote de celle du joueur 1 : essaye et
mesure. Une seule piece joueur 2 fait monter 288 octets sur pzloop2, 181 sur
bloodwar — un jeu qui tourne fait bouger des dizaines de compteurs internes.
Il faut la meme methode que pour le joueur 1 : plusieurs pieces, et on ne
garde que les octets qui montent de 1 a chaque fois.

Les touches, cablees dans retroarch.cfg et dans le clavier virtuel :

    joueur 1 : piece = Shift droit, start = Entree     (defauts RetroArch)
    joueur 2 : piece = 6,           start = 2

Verifie : la piece du joueur 2 ne touche jamais le compteur du joueur 1.

Aucune dependance hors bibliotheque standard.
"""

import argparse
import importlib.util
import json
import os
import sys
import time

OUTILS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, OUTILS)

spec = importlib.util.spec_from_file_location(
    "nuit_credits", os.path.join(OUTILS, "nuit-credits.py"))
nuit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nuit)

from clavier_virtuel import ClavierVirtuel     # noqa: E402

PIECES_J2 = 3               # autant que pour le joueur 1
ASSEZ = 2                   # on s arrete des qu il ne reste presque plus rien


def chercher_j2(borne, clavier, arret, journal):
    """L adresse du compteur du joueur 2, ou None.

    Meme principe que pour le joueur 1 : on photographie la RAM, on insere
    une piece, on ne garde que les octets montes de 1, et on recommence. Deux
    ou trois pieces suffisent a ne laisser qu un candidat.
    """
    candidats = None
    avant = borne.photo()
    if avant is None:
        return None
    for n in range(1, PIECES_J2 + 1):
        arret()
        clavier.piece_j2()
        time.sleep(1.5)
        apres = borne.photo()
        if apres is None or len(apres) != len(avant):
            return None
        montes = {a for a in range(len(apres))
                  if apres[a] == (avant[a] + 1) & 0xFF and avant[a] < 0x99}
        candidats = montes if candidats is None else candidats & montes
        avant = apres
        journal("    piece J2 %d : %d candidat(s)" % (n, len(candidats)))
        if not candidats:
            return None
        if len(candidats) <= ASSEZ:
            break

    # START joueur 2 doit faire redescendre SON solde, pas celui du joueur 1.
    avant_start = {}
    for a in sorted(candidats):
        o = borne.lire(a, 1)
        if o is not None:
            avant_start[a] = o[0]
    arret()
    clavier.start_j2()
    time.sleep(2.0)
    baissiers = set()
    for a, v in avant_start.items():
        o = borne.lire(a, 1)
        if o is not None and o[0] < v:
            baissiers.add(a)
    if baissiers:
        return sorted(baissiers)[0]
    if len(candidats) == 1:
        return sorted(candidats)[0]      # un seul candidat, sans confirmation
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("--base", required=True)
    p.add_argument("--roms", default="/mnt/roms")
    p.add_argument("--systeme", default="fbneo")
    p.add_argument("--limite", type=int, default=0)
    p.add_argument("--arret", default="/tmp/arret-nuit")
    p.add_argument("--coeur-nomme", default="FinalBurn Neo")
    args = p.parse_args()

    base = nuit.base_charger(args.base)
    boutons = {}
    chemin_boutons = os.path.join(os.path.dirname(args.base), "boutons-arcade.json")
    try:
        boutons = (json.load(open(chemin_boutons)).get("jeux") or {})
    except (IOError, OSError, ValueError):
        pass

    # Seuls les jeux MULTI ont un second poste ; inutile d essayer les autres.
    a_faire = []
    for cle, fiche in (base.get("jeux") or {}).items():
        credits = fiche.get("credits") or {}
        if not credits.get("adresse") or credits.get("adresse_j2") is not None:
            continue
        jeu = cle.split("/", 1)[-1]
        info = boutons.get(jeu) or {}
        if (info.get("joueurs") or 1) < 2:
            continue
        for ext in (".zip", ".7z"):
            rom = os.path.join(args.roms, args.systeme, jeu + ext)
            if os.path.exists(rom):
                a_faire.append((cle, jeu, rom))
                break
    if args.limite:
        a_faire = a_faire[:args.limite]
    print("%d jeu(x) multi a completer" % len(a_faire), flush=True)

    def arret():
        if os.path.exists(args.arret):
            raise SystemExit("arret demande, tout est sauve.")

    def journal(m):
        print(m, flush=True)

    borne = nuit.Borne("127.0.0.1", True, True)
    borne.coeur_nomme = args.coeur_nomme
    trouves = 0
    try:
        with ClavierVirtuel("clavier-credits") as clavier:
            for n, (cle, jeu, rom) in enumerate(a_faire, 1):
                arret()
                print("[%d/%d] %s" % (n, len(a_faire), cle), flush=True)
                vu = nuit.lancer_avec_reprises(borne, args.systeme, jeu, rom,
                                               arret, journal)
                if not vu or isinstance(vu, str):
                    continue
                taille = nuit.patienter(borne.mesurer, nuit.ATTENTE_RAM, arret)
                if not taille:
                    continue
                borne.taille = taille
                if not nuit.attendre_vivant(borne, arret):
                    continue
                if borne.rapide_voulue:
                    borne.avance_rapide(True)
                adresse = chercher_j2(borne, clavier, arret, journal)
                if adresse is not None:
                    fiche = base["jeux"][cle]["credits"]
                    fiche["adresse_j2"] = adresse
                    fiche["adresse_j2_hex"] = "0x%04X" % adresse
                    trouves += 1
                    journal("  JOUEUR 2 en 0x%04X" % adresse)
                else:
                    journal("  pas de second compteur trouve")
                nuit.base_ecrire(args.base, base)
                borne.avance_rapide(False)
                borne.quitter()
                borne.rapide = False
                nuit.patienter(lambda: borne.jeu() is None, nuit.ATTENTE_ARRET, arret)
                time.sleep(1.0)
    except SystemExit as fin:
        print(fin, flush=True)
    finally:
        nuit.base_ecrire(args.base, base)
        borne.quitter()
        borne.arreter_processus()
    print("\n%d adresse(s) joueur 2 ajoutee(s)" % trouves, flush=True)


if __name__ == "__main__":
    main()
