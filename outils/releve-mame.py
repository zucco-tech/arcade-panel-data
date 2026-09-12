#!/usr/bin/env python3
"""Releve des credits des jeux MAME, mesure DANS MAME.

MAME ne publie pas sa memoire de travail au frontend libretro : sur dix
jeux tires au hasard, un seul rendait un pointeur, et fige. La mesure se
fait donc a l interieur de MAME, en Lua (outils/mame-credits.lua), ou l on
voit la carte memoire du pilote et les entrees NOMMEES du jeu — « Coin 1 »,
« 1 Player Start » — donc sans deviner quel bouton encaisse.

MAME accepte un fichier « .cmd » contenant sa ligne de commande : c est par
la qu on lui passe le nom de la machine, le dossier des roms et notre
script. Chaque jeu tourne dans un processus a part, avec une limite de
temps : MAME ne supporte pas de charger deux machines de suite.

    python3 releve-mame.py --roms /mnt/roms/mame/mame0278 \
        --base /mnt/recalbox/donnees/credits-mame.json

Compter environ une minute par jeu : MAME emule la machine entiere, la ou
FBNeo se contente de ce qu il faut. Les parts (--part 2/4) permettent de
faire tourner plusieurs releves en parallele.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

import importlib.machinery

RACINE = os.path.dirname(os.path.abspath(__file__))
LUA = os.path.join(RACINE, "mame-credits.lua")
COEUR = "/opt/coeurs/mame_libretro.so"
DOSSIER_SYSTEME = "/root/.config/retroarch/system"
# Le Lua attend environ trente secondes de jeu ; a la vitesse ou MAME tourne
# sans image ni son, cela demande quelques milliers d images.
IMAGES = 5400
IMAGES_PAS = 300
OPTIONS = {
    "mame_softlists_enable": "disabled",   # sinon le dossier devient la machine
    "mame_softlists_auto_media": "disabled",
    "mame_thread_mode": "disabled",        # on avance image par image
    "mame_throttle": "disabled",
    "mame_write_config": "disabled",
}


def charger_moteur():
    """Le chargeur de coeur ecrit pour le releve direct : meme code, meme
    isolement, on ne le duplique pas."""
    return importlib.machinery.SourceFileLoader(
        "releve_direct", os.path.join(RACINE, "releve-direct.py")).load_module()


# --- un jeu, dans son propre processus -----------------------------------------

def enfant():
    """Lance MAME sur un jeu et le fait tourner ; le Lua ecrit le resultat."""
    _, jeu, dossier_roms, sortie = sys.argv[1:5]
    rd = charger_moteur()
    os.dup2(os.open(os.devnull, os.O_WRONLY), 2)
    with tempfile.NamedTemporaryFile("w", suffix=".cmd", delete=False) as fh:
        fh.write("%s -rompath %s -autoboot_script %s -autoboot_delay 1\n"
                 % (jeu, dossier_roms, LUA))
        commande = fh.name
    os.environ["MAME_SORTIE"] = sortie
    coeur = rd.Coeur(COEUR, DOSSIER_SYSTEME, OPTIONS)
    coeur.charger(commande)          # MAME demarre meme quand il repond « faux »
    fait = 0
    while fait < IMAGES:
        coeur.images(IMAGES_PAS)
        fait += IMAGES_PAS
        if os.path.exists(sortie):   # le Lua a conclu : inutile d insister
            break
    try:
        os.unlink(commande)
    except OSError:
        pass
    os._exit(0)


def mesurer(jeu, dossier_roms, delai):
    """Renvoie la fiche du jeu, ou un dictionnaire d erreur."""
    sortie = tempfile.mktemp(suffix=".json", prefix="mame-")
    try:
        subprocess.run([sys.executable, os.path.abspath(__file__), "--enfant",
                        jeu, dossier_roms, sortie],
                       capture_output=True, timeout=delai)
    except subprocess.TimeoutExpired:
        return {"erreur": "delai depasse"}
    if not os.path.exists(sortie):
        return {"erreur": "MAME n a rien rendu (machine refusee ?)"}
    try:
        with open(sortie) as fh:
            brut = json.load(fh)
    except ValueError:
        return {"erreur": "reponse illisible"}
    finally:
        try:
            os.unlink(sortie)
        except OSError:
            pass
    return brut


# --- la base --------------------------------------------------------------------

def charger_base(chemin):
    if os.path.exists(chemin):
        with open(chemin) as fh:
            return json.load(fh)
    return {"jeux": {}, "difficiles": {}}


def ecrire_base(chemin, base):
    provisoire = chemin + ".tmp"
    with open(provisoire, "w") as fh:
        json.dump(base, fh, indent=1, ensure_ascii=False)
    os.replace(provisoire, chemin)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--enfant":
        enfant()
        return
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--roms", default="/mnt/roms/mame/mame0278")
    p.add_argument("--base", required=True)
    p.add_argument("--reference", default=None,
                   help="base a consulter pour savoir ce qui est deja mesure")
    p.add_argument("--part", default=None, help="« 2/4 » : une part sur quatre")
    p.add_argument("--jeux", nargs="*", default=None)
    p.add_argument("--priorite", default="/mnt/roms/fbneo",
                   help="dossier de roms deja couvert par un autre coeur : les jeux "
                        "qui n y sont PAS passent en premier, c est la que MAME sert")
    p.add_argument("--limite", type=int, default=0)
    p.add_argument("--delai", type=float, default=300.0)
    p.add_argument("--arret", default="/tmp/arret-nuit")
    a = p.parse_args()

    base = charger_base(a.base)
    connue = charger_base(a.reference) if a.reference else base
    noms = a.jeux or sorted(
        f.rsplit(".", 1)[0] for f in os.listdir(a.roms)
        if f.lower().endswith((".zip", ".7z")))
    reste = noms if a.jeux else [n for n in noms if "mame/%s" % n not in connue["jeux"]]
    # D abord ce que l autre coeur ne sait pas faire : c est la que MAME
    # apporte quelque chose. Le reste suivra, dans le meme ordre alphabetique.
    if a.priorite and os.path.isdir(a.priorite):
        couverts = {f.rsplit(".", 1)[0] for f in os.listdir(a.priorite)}
        reste = [n for n in reste if n not in couverts] + [n for n in reste if n in couverts]
    if a.part:
        rang, total = (int(x) for x in a.part.split("/"))
        reste = reste[rang - 1::total]
    if a.limite:
        reste = reste[:a.limite]
    print("mame : %d jeu(x) a mesurer (%d deja connus)"
          % (len(reste), len(noms) - len(reste)), flush=True)

    appris = ecartes = 0
    debut = time.time()
    for n, jeu in enumerate(reste, 1):
        if os.path.exists(a.arret):
            print("arret demande", flush=True)
            break
        parti = time.time()
        fiche = mesurer(jeu, a.roms, a.delai)
        duree = time.time() - parti
        print("[%d/%d] mame/%s" % (n, len(reste), jeu), flush=True)
        if "erreur" in fiche:
            ecartes += 1
            print("  difficile : %s (%.0f s)" % (fiche["erreur"], duree), flush=True)
            base["difficiles"]["mame/" + jeu] = {"jeu": jeu, "systeme": "mame",
                                                 "raison": fiche["erreur"],
                                                 "le": time.strftime("%Y-%m-%d")}
        else:
            appris += 1
            print("  APPRIS %s dans %s — %d -> %d au START, %d piece(s) (%.0f s)"
                  % (fiche.get("adresse_hex"), fiche.get("zone"),
                     fiche.get("avant_start", 0), fiche.get("apres_start", 0),
                     fiche.get("accords", 0), duree), flush=True)
            # La fiche prend la forme commune a toutes les bases, pour que le
            # repliage, l export et la borne la lisent comme les autres. Ce
            # qui est propre a MAME — l adresse est celle du processeur, pas
            # d une fenetre libretro, et il faudra la lire par Lua — est dit
            # dans « ram.commande » et « releve.methode ».
            base["jeux"]["mame/" + jeu] = {
                "jeu": jeu, "systeme": "mame", "core": "MAME",
                "ram": {"taille": fiche.get("ram"), "commande": "lua mame",
                        "zone": fiche.get("zone")},
                "credits": {
                    "adresse": fiche["adresse"], "adresse_hex": fiche["adresse_hex"],
                    "octets": 1, "miroirs": [],
                    "verifie_insertion": True, "verifie_consommation": True,
                    "pieces_observees": fiche.get("accords", 0),
                    "entree_piece": fiche.get("piece"), "entree_start": fiche.get("start"),
                    "compteur_commun": False, "adresse_j2": None, "adresse_j2_hex": None,
                    "j2_verifie_consommation": False,
                },
                "releve": {"le": time.strftime("%Y-%m-%d"), "methode": "lua dans mame"},
            }
            base["difficiles"].pop("mame/" + jeu, None)
        ecrire_base(a.base, base)
    duree = time.time() - debut
    print("%d appris, %d ecartes, en %d min (%.0f s par jeu)"
          % (appris, ecartes, duree / 60, duree / max(appris + ecartes, 1)), flush=True)


if __name__ == "__main__":
    main()
