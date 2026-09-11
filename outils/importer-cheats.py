#!/usr/bin/env python3
"""
Pre-remplit la base a partir du pack de cheats officiel FBNeo.

    python3 importer-cheats.py --cheats /chemin/vers/cheats --base credits-arcade.json

Un cheat "Infinite Credits" designe exactement l'octet qu'on cherche : c'est
le compteur de credits du jeu. Le pack en documente plus d'un millier.

Une adresse de cheat n'est pas directement utilisable : elle est donnee dans
l'espace d'adressage du processeur emule (0xFF80B0 pour un 68000 CPS), alors
que READ_CORE_RAM lit la RAM systeme a plat depuis 0. Deux corrections :

  * on ne garde que le bas de l'adresse, la taille de la RAM etant une
    puissance de deux : flat = adresse & (taille - 1) ;
  * sur un jeu 68000, FBNeo range la RAM gros-boutiste octets inverses sur un
    hote petit-boutiste : il faut un XOR 1.

Verifie sur pzloop2 : le cheat dit 0xFF80B0, le compteur est bien a 0x80B1.

Comme on ne sait pas d'avance si un jeu est 68000 ou Z80, on garde les deux
candidats. La borne tranche a la premiere piece inseree : un seul des deux
montera de 1. C'est une piste, pas une certitude — mais une piste a deux
entrees plutot qu'a soixante-cinq mille.

Aucune dependance : uniquement la bibliotheque standard.
"""

import argparse
import glob
import re
import json
import os
import re
import time

# On ne retient que le compteur principal. Les variantes par joueur
# ("Infinite Credits PL1") designent des compteurs separes, moins universels.
TITRES = ("infinite credits", "infinite credit", "infinite credits (common)")

# 1 "Enabled", 0, 0xFF80B0, 0x09
LIGNE = re.compile(r'^\s*\d+\s+"[^"]*"\s*,\s*(\d+)\s*,\s*(0x[0-9A-Fa-f]+)\s*,')


def lire_cheat(chemin):
    """Adresse du cheat de credits d'un jeu, ou None."""
    dedans = False
    try:
        with open(chemin, "r", encoding="utf-8", errors="replace") as fh:
            for ligne in fh:
                depouillee = ligne.strip()
                if depouillee.startswith('cheat "'):
                    titre = depouillee[7:].rstrip('"').strip().lower()
                    dedans = titre in TITRES
                    continue
                if not dedans:
                    continue
                trouvee = LIGNE.match(ligne)
                if trouvee:
                    # Un cheat a plusieurs adresses vise autre chose qu'un
                    # simple compteur : on ne le retient pas.
                    if ligne.count("0x") > 2:
                        return None
                    return int(trouvee.group(2), 16)
    except (IOError, OSError):
        return None
    return None


# MAME documente ses cheats en XML, avec l'adresse dans l'espace du
# processeur principal : maincpu.pb@FF80B0. La collection couvre nettement
# plus de jeux que le pack FBNeo, avec la meme convention d'adresse — verifie
# sur pzloop2, ou les deux annoncent 0xFF80B0.
BLOC_MAME = re.compile(r'<cheat desc="([^"]+)">(.*?)</cheat>', re.S)
ADR_MAME = re.compile(r'maincpu\.pb@([0-9A-Fa-f]+)')


def lire_mame(archive):
    """{jeu: adresse} depuis une collection de cheats MAME (cheat.zip)."""
    import zipfile
    trouves = {}
    with zipfile.ZipFile(archive) as zf:
        for nom in zf.namelist():
            if not nom.endswith(".xml"):
                continue
            try:
                texte = zf.read(nom).decode("utf-8", "replace")
            except (KeyError, OSError):
                continue
            if "redit" not in texte:
                continue
            for desc, corps in BLOC_MAME.findall(texte):
                if desc.strip().lower() not in TITRES:
                    continue
                adresses = ADR_MAME.findall(corps)
                # Plusieurs adresses : le cheat vise autre chose qu'un
                # simple compteur, on ne le retient pas.
                if len(adresses) == 1:
                    trouves[nom[:-4]] = int(adresses[0], 16)
                break
    return trouves


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--cheats", help="dossier des .ini FBNeo")
    parser.add_argument("--mame", help="archive cheat.zip de la collection MAME")
    parser.add_argument("--base", required=True, help="fichier de la base")
    parser.add_argument("--source", help="nom de la source (sinon deduit)")
    args = parser.parse_args()
    if not args.cheats and not args.mame:
        raise SystemExit("donne au moins --cheats ou --mame")

    try:
        with open(args.base) as fh:
            base = json.load(fh)
    except (IOError, OSError):
        raise SystemExit("base %s introuvable" % args.base)

    if args.cheats:
        source = args.source or "FBNeo-cheats"
        ou = "https://github.com/finalburnneo/FBNeo-cheats"
        quoi = "cheats \"Infinite Credits\" du pack officiel FinalBurn Neo"
        fichiers = sorted(glob.glob(os.path.join(args.cheats, "*.ini")))
        if not fichiers:
            raise SystemExit("aucun .ini dans %s" % args.cheats)
        releve = {}
        for chemin in fichiers:
            adresse = lire_cheat(chemin)
            if adresse is not None:
                releve[os.path.basename(chemin)[:-4]] = adresse
        lus = len(fichiers)
    else:
        source = args.source or "MAME-cheats"
        ou = "collection de cheats MAME (cheat.zip)"
        quoi = "cheats \"Infinite Credits\" sur un seul octet, adresse maincpu"
        releve = lire_mame(args.mame)
        lus = len(releve)

    pistes = base.setdefault("pistes", {})
    ajoutees = ignorees = doublons = 0
    for jeu, adresse in sorted(releve.items()):
        # Une piste deja posee par une source plus sure n'est pas remplacee.
        if jeu in pistes:
            doublons += 1
            continue
        # Un jeu deja releve sur la borne n'a pas besoin de piste.
        if ((base.get("jeux", {}).get(jeu) or {}).get("credits") or {}).get("adresse"):
            ignorees += 1
            continue
        pistes[jeu] = {"cheat": "0x%06X" % adresse, "source": source}
        ajoutees += 1

    base.setdefault("sources", {})[source] = {
        "quoi": quoi,
        "ou": ou,
        "importe_le": time.strftime("%Y-%m-%d"),
        "pistes_posees": ajoutees,
    }

    provisoire = args.base + ".tmp"
    with open(provisoire, "w") as fh:
        json.dump(base, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
    os.replace(provisoire, args.base)

    print("source : %s" % source)
    print("%d entree(s) lue(s), %d piste(s) ajoutee(s)" % (lus, ajoutees))
    if doublons:
        print("%d deja pourvu(s) par une autre source" % doublons)
    if ignorees:
        print("%d deja releve(s) sur la borne" % ignorees)
    print("total des pistes : %d" % len(pistes))


if __name__ == "__main__":
    main()
