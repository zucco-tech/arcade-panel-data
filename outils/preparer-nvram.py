#!/usr/bin/env python3
"""Donne aux machines MAME une NVRAM deja initialisee avant de les mesurer.

Le releve ferme MAME brutalement : la NVRAM n est jamais ecrite, et chaque
lancement repart d une memoire vierge. Les Williams et les Midway (Joust,
Defender, Mortal Kombat 3) passent alors leur temps sur l ecran « reglages
usine » et n encaissent aucune piece : « candidats non confirmes », ou rien
du tout. Ici on demarre chaque machine une fois, on la laisse s initialiser,
puis on la ferme PROPREMENT (retro_unload_game) pour que MAME ecrive sa NVRAM
dans system/mame/nvram/<jeu>/. Le releve suivant la retrouve.

Essai du 17/09/2026 : Joust, « candidats non confirmes » depuis le 12/09,
appris en 16 s une fois la NVRAM posee (0xA0F2, 5 pieces, START 5 -> 4).

    python3 preparer-nvram.py --base .../credits-arcade.json \
        --raisons "candidats non confirmes,MAME n a rien rendu (Configuration"
    python3 preparer-nvram.py --jeux joust defender
"""

import argparse
import importlib.machinery
import json
import os
import subprocess
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
NVRAM = "/root/.config/retroarch/system/mame/nvram"
ROMS = "/mnt/roms/mame/mame0278"


def enfant(jeu, images):
    rm = importlib.machinery.SourceFileLoader(
        "releve_mame", os.path.join(ICI, "releve-mame.py")).load_module()
    rd = rm.charger_moteur()
    os.dup2(os.open(os.devnull, os.O_WRONLY), 2)
    with tempfile.NamedTemporaryFile("w", suffix=".cmd", delete=False) as fh:
        fh.write("%s -rompath %s\n" % (jeu, ROMS))
        commande = fh.name
    coeur = rd.Coeur(rm.COEUR, rm.DOSSIER_SYSTEME, rm.OPTIONS)
    coeur.charger(commande)
    coeur.images(images)
    coeur.lib.retro_unload_game()        # c est ici que MAME ecrit la NVRAM
    coeur.lib.retro_deinit()
    os.unlink(commande)
    os._exit(0)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--enfant":
        enfant(sys.argv[2], int(sys.argv[3]))
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--base", default="/mnt/recalbox/donnees/credits-arcade.json")
    p.add_argument("--raisons", default="candidats non confirmes")
    p.add_argument("--jeux", nargs="*", default=None)
    p.add_argument("--images", type=int, default=3600,
                   help="images de demarrage avant la fermeture (60 s de jeu)")
    p.add_argument("--delai", type=float, default=600)
    p.add_argument("--refaire", action="store_true", help="meme si la NVRAM existe")
    a = p.parse_args()
    if a.jeux:
        jeux = a.jeux
    else:
        motifs = tuple(m.strip() for m in a.raisons.split(",") if m.strip())
        with open(a.base) as fh:
            durs = json.load(fh).get("difficiles", {})
        jeux = sorted(d["jeu"] for c, d in durs.items()
                      if c.startswith("mame/") and str(d.get("raison", "")).startswith(motifs))
    print("nvram : %d machine(s)" % len(jeux), flush=True)
    for n, jeu in enumerate(jeux, 1):
        dossier = os.path.join(NVRAM, jeu)
        if os.path.isdir(dossier) and os.listdir(dossier) and not a.refaire:
            print("[%d/%d] %s : deja en place" % (n, len(jeux), jeu), flush=True)
            continue
        try:
            subprocess.run([sys.executable, os.path.abspath(__file__), "--enfant",
                            jeu, str(a.images)], capture_output=True, timeout=a.delai)
        except subprocess.TimeoutExpired:
            print("[%d/%d] %s : delai depasse" % (n, len(jeux), jeu), flush=True)
            continue
        ecrit = os.path.isdir(dossier) and os.listdir(dossier)
        print("[%d/%d] %s : %s" % (n, len(jeux), jeu,
              "NVRAM ecrite (%s)" % ", ".join(sorted(os.listdir(dossier))) if ecrit
              else "pas de NVRAM (la machine n en a pas)"), flush=True)


if __name__ == "__main__":
    main()
