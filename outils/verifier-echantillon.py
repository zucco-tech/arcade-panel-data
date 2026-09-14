#!/usr/bin/env python3
"""Un controle par echantillon : des fiches tirees au hasard, remesurees.

Le balayage a verifie chaque fiche une fois — le compteur monte a la piece
et redescend au START. Ce programme tire quelques fiches au sort et les
remesure avec les memes outils : chacune doit redonner LA MEME adresse. Une
mesure qui ne se repete pas est suspecte ; vingt sur vingt identiques, la
base est reproductible.

    python3 verifier-echantillon.py --tirer 20 --sortie .../echantillon.json
    python3 verifier-echantillon.py --remesurer .../echantillon.json

L echantillon est garde dans un fichier pour que la borne rejoue exactement
les memes fiches (voir verifier-sur-borne.sh). Le rapport va sur la sortie
et dans journaux/verification-pc-<date>.log ; la commande rend 1 au moindre
ecart.
"""

import argparse
import json
import os
import random
import subprocess
import sys
import tempfile
import time

BASE = "/mnt/recalbox/donnees/credits-arcade.json"
OUTILS = os.path.dirname(os.path.abspath(__file__))
JOURNAUX = "/mnt/recalbox/journaux"
# Ou sont les roms de chaque systeme, et comment on le remesure.
ROMS = {"fbneo": "/mnt/roms/fbneo", "mame": "/mnt/roms/mame/mame0278"}


def charger(chemin):
    with open(chemin) as fh:
        return json.load(fh)


def tirer(combien, systemes):
    """Autant de fiches par systeme, parmi celles dont la rom est bien la."""
    base = charger(BASE)
    par_systeme = {s: [] for s in systemes}
    for cle, fiche in base.get("jeux", {}).items():
        systeme = fiche.get("systeme")
        adresse = (fiche.get("credits") or {}).get("adresse")
        if systeme not in par_systeme or adresse is None:
            continue
        jeu = fiche.get("jeu") or cle.split("/", 1)[-1]
        # FBNeo range ses roms en .zip, MAME en .7z.
        if not any(os.path.exists(os.path.join(ROMS[systeme], jeu + ext)) for ext in (".zip", ".7z")):
            continue
        par_systeme[systeme].append({
            "systeme": systeme, "jeu": jeu, "cle": cle,
            "adresse": adresse, "adresse_hex": "0x%04X" % adresse,
            "octets": (fiche.get("credits") or {}).get("octets", 1),
            "entree_piece": fiche.get("entree_piece"),
            "core": fiche.get("core")})
    tires = []
    part = max(1, combien // max(1, len(systemes)))
    for systeme, fiches in par_systeme.items():
        tires.extend(random.sample(fiches, min(part, len(fiches))))
    return {"tire_le": time.strftime("%Y-%m-%d %H:%M"), "fiches": tires}


def remesurer(echantillon):
    """Relance les outils du balayage sur les seuls jeux de l echantillon,
    dans une base a part, et compare adresse par adresse."""
    dossier = tempfile.mkdtemp(prefix="verif-")
    arret = os.path.join(dossier, "arret")           # jamais cree : on va au bout
    verdicts = []
    for systeme in sorted({f["systeme"] for f in echantillon["fiches"]}):
        jeux = [f["jeu"] for f in echantillon["fiches"] if f["systeme"] == systeme]
        base = os.path.join(dossier, systeme + ".json")
        if systeme == "mame":
            commande = [sys.executable, os.path.join(OUTILS, "releve-mame.py"),
                        "--roms", ROMS["mame"], "--base", base, "--arret", arret,
                        "--jeux"] + jeux
        else:
            commande = [sys.executable, os.path.join(OUTILS, "releve-direct.py"),
                        "--systeme", systeme, "--roms", "/mnt/roms", "--base", base,
                        "--arret", arret, "--jeux"] + jeux
        with open(os.path.join(dossier, systeme + ".log"), "w") as journal:
            subprocess.run(commande, stdout=journal, stderr=subprocess.STDOUT)
        mesure = charger(base) if os.path.exists(base) else {}
        for fiche in [f for f in echantillon["fiches"] if f["systeme"] == systeme]:
            jeu = fiche["jeu"]
            trouvee = next((v for k, v in mesure.get("jeux", {}).items()
                            if k.endswith("/" + jeu)), None)
            ecartee = next((v for k, v in mesure.get("difficiles", {}).items()
                            if k.endswith("/" + jeu)), None)
            if trouvee is not None:
                adresse = (trouvee.get("credits") or {}).get("adresse")
                if adresse == fiche["adresse"]:
                    verdict = "OK        %s" % fiche["adresse_hex"]
                else:
                    verdict = "ECART     fiche %s, remesure %s" % (
                        fiche["adresse_hex"], "0x%04X" % adresse if adresse is not None else "?")
            elif ecartee is not None:
                verdict = "NON MESURE %s (fiche %s)" % (ecartee.get("raison", "?"), fiche["adresse_hex"])
            else:
                verdict = "ABSENT    rien dans la remesure (fiche %s)" % fiche["adresse_hex"]
            verdicts.append("%-6s %-12s %s" % (systeme, jeu, verdict))
    return verdicts, dossier


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--tirer", type=int, default=0, help="combien de fiches tirer au sort")
    p.add_argument("--systemes", nargs="*", default=["fbneo", "mame"])
    p.add_argument("--sortie", default="/mnt/recalbox/donnees/echantillon.json")
    p.add_argument("--remesurer", default=None, help="l echantillon a remesurer")
    a = p.parse_args()

    if a.tirer:
        echantillon = tirer(a.tirer, a.systemes)
        with open(a.sortie, "w") as fh:
            json.dump(echantillon, fh, indent=2, ensure_ascii=False)
        for f in echantillon["fiches"]:
            print("%-6s %-12s %s" % (f["systeme"], f["jeu"], f["adresse_hex"]))
        print("%d fiche(s) tiree(s) -> %s" % (len(echantillon["fiches"]), a.sortie))
        return 0

    if a.remesurer:
        echantillon = charger(a.remesurer)
        debut = time.time()
        verdicts, dossier = remesurer(echantillon)
        ecarts = sum(1 for v in verdicts if " ECART" in v or v.split()[2] == "ECART")
        non = sum(1 for v in verdicts if "NON MESURE" in v or "ABSENT" in v)
        ok = len(verdicts) - ecarts - non
        rapport = ["=== controle par echantillon sur le PC, %s (%d min) ===" % (
            time.strftime("%Y-%m-%d %H:%M"), int((time.time() - debut) / 60))]
        rapport += verdicts
        rapport.append("%d identique(s), %d ecart(s), %d non remesuree(s) sur %d ; detail dans %s"
                       % (ok, ecarts, non, len(verdicts), dossier))
        texte = "\n".join(rapport)
        print(texte)
        with open(os.path.join(JOURNAUX, "verification-pc-%s.log" % time.strftime("%Y%m%d")), "a") as fh:
            fh.write(texte + "\n")
        return 1 if ecarts else 0
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
