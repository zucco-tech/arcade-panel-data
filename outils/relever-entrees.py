#!/usr/bin/env python3
"""Ce que chaque jeu declare comme entrees, demande AU COEUR lui-meme.

Au chargement d une rom, un coeur libretro annonce a son frontend la liste
de ses entrees (RETRO_ENVIRONMENT_SET_INPUT_DESCRIPTORS) : « P1 Coin »,
« P2 Start », « Shot », « Jump »... C est ce que RetroArch montre dans
Menu rapide > Controles. Personne ne l ecrit sur disque : on charge donc le
coeur nous-memes, sans RetroArch ni ecran, on note ce qu il annonce, et on
passe au jeu suivant. Une seconde par jeu.

C est la source la plus sure pour le NOMBRE de joueurs et de boutons : elle
vient du pilote du jeu, celui-la meme qui tourne sur la borne. Les couleurs,
elles, restent celles d arcade-database — un emulateur ne les connait pas.

    sudo python3 relever-entrees.py --coeur /opt/coeurs/fbneo_rb.so \
        --roms /mnt/roms --systemes fbneo neogeo neogeocd \
        --sortie /mnt/recalbox/donnees/entrees-coeur.json

Chaque jeu est charge dans un processus a part, avec une limite de temps :
un pilote qui plante ou qui boucle n emporte pas le releve.
"""

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time

DIRECTIONS = {"Up", "Down", "Left", "Right"}
# Les identifiants RetroPad de libretro (RETRO_DEVICE_ID_JOYPAD_*), pour les
# boutons d action. C est ce qui dit OU le coeur range chaque fonction du jeu :
# « Weak Punch » sur y chez FBNeo pour Street Fighter, « Fire 1 » sur b pour
# 1942. outils/aligner-boutons.py s en sert pour placer le bouton N du jeu a
# la position N du panneau.
RETROPAD = {0: "b", 1: "y", 8: "a", 9: "x", 10: "l", 11: "r", 12: "l2", 13: "r2"}
SERVICE = {"Coin", "Start", "Service", "Test", "Diagnostic", "Reset", "Tilt",
           "Dip", "Dip A", "Dip B", "Dip C", "Dip D"}

# --- ce qui tourne dans le processus enfant ----------------------------------

ENV_GET_CAN_DUPE = 3
ENV_GET_SYSTEM_DIRECTORY = 9
ENV_SET_PIXEL_FORMAT = 10
ENV_SET_INPUT_DESCRIPTORS = 11
ENV_GET_SAVE_DIRECTORY = 31


class Descripteur(ctypes.Structure):
    _fields_ = [("port", ctypes.c_uint), ("device", ctypes.c_uint),
                ("index", ctypes.c_uint), ("id", ctypes.c_uint),
                ("description", ctypes.c_char_p)]


class InfoJeu(ctypes.Structure):
    _fields_ = [("path", ctypes.c_char_p), ("data", ctypes.c_void_p),
                ("size", ctypes.c_size_t), ("meta", ctypes.c_char_p)]


def enfant(coeur, rom, dossier_systeme):
    """Charge la rom, imprime les entrees en JSON sur stdout, sort."""
    declares = []
    dossier = ctypes.c_char_p(dossier_systeme.encode())

    def environnement(cmd, data):
        cmd &= 0xFFFF
        if cmd == ENV_SET_INPUT_DESCRIPTORS:
            p = ctypes.cast(data, ctypes.POINTER(Descripteur))
            i = 0
            while p[i].description:
                declares.append((p[i].port, p[i].device, p[i].id,
                                 p[i].description.decode("utf-8", "replace")))
                i += 1
            return True
        if cmd in (ENV_GET_SYSTEM_DIRECTORY, ENV_GET_SAVE_DIRECTORY):
            ctypes.cast(data, ctypes.POINTER(ctypes.c_char_p))[0] = dossier
            return True
        if cmd == ENV_GET_CAN_DUPE:
            ctypes.cast(data, ctypes.POINTER(ctypes.c_bool))[0] = True
            return True
        return cmd == ENV_SET_PIXEL_FORMAT

    types = [
        ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_uint, ctypes.c_void_p),
        ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_size_t),
        ctypes.CFUNCTYPE(None, ctypes.c_int16, ctypes.c_int16),
        ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t),
        ctypes.CFUNCTYPE(None),
        ctypes.CFUNCTYPE(ctypes.c_int16, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint),
    ]
    rappels = [types[0](environnement), types[1](lambda *a: None),
               types[2](lambda *a: None), types[3](lambda *a: 0),
               types[4](lambda: None), types[5](lambda *a: 0)]
    # Le coeur ecrit son journal sur stderr : on le fait taire.
    nul = os.open(os.devnull, os.O_WRONLY)
    os.dup2(nul, 2)
    c = ctypes.CDLL(coeur)
    c.retro_set_environment(rappels[0])
    c.retro_set_video_refresh(rappels[1])
    c.retro_set_audio_sample(rappels[2])
    c.retro_set_audio_sample_batch(rappels[3])
    c.retro_set_input_poll(rappels[4])
    c.retro_set_input_state(rappels[5])
    c.retro_init()
    c.retro_load_game.restype = ctypes.c_bool
    info = InfoJeu(rom.encode(), None, 0, None)
    charge = bool(c.retro_load_game(ctypes.byref(info)))
    if charge:
        # FBNeo n annonce ses entrees qu une fois les ports affectes et une
        # image calculee.
        c.retro_set_controller_port_device(0, 1)
        c.retro_set_controller_port_device(1, 1)
        for _ in range(2):
            c.retro_run()
    print(json.dumps({"charge": charge, "entrees": declares}))
    sys.stdout.flush()
    os._exit(0)          # pas de retro_deinit : certains pilotes y plantent


# --- ce que retient le releve --------------------------------------------------

def resumer(entrees):
    """Par joueur : ses boutons d action, dans l ordre annonce."""
    joueurs = {}
    retropad = []                  # joueur 1 : les boutons RetroPad, dans l ordre du jeu
    for port, appareil, ident, nom in entrees:
        nom = nom.strip()
        if "(Fake" in nom or nom in DIRECTIONS or nom in SERVICE:
            continue
        if appareil != 1:          # 1 = manette ; on ignore les analogiques
            continue
        joueurs.setdefault(port + 1, [])
        if nom not in joueurs[port + 1]:
            joueurs[port + 1].append(nom)
            if port == 0 and ident in RETROPAD and RETROPAD[ident] not in retropad:
                retropad.append(RETROPAD[ident])
    ports = sorted(p for p, _, _, _ in entrees) if entrees else []
    return {
        "joueurs": (max(ports) + 1) if ports else 0,
        "boutons": joueurs.get(1, []),
        "boutons_j2": joueurs.get(2, []),
        "retropad": retropad,
    }


def relever(coeur, rom, dossier_systeme, delai):
    try:
        sortie = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--enfant", coeur, rom, dossier_systeme],
            capture_output=True, timeout=delai)
    except subprocess.TimeoutExpired:
        return {"erreur": "delai depasse"}
    ligne = sortie.stdout.decode("utf-8", "replace").strip().splitlines()
    if not ligne:
        return {"erreur": "pilote plante (code %d)" % sortie.returncode}
    try:
        brut = json.loads(ligne[-1])
    except ValueError:
        return {"erreur": "reponse illisible"}
    if not brut.get("charge"):
        return {"erreur": "rom refusee"}
    fiche = resumer(brut["entrees"])
    if not fiche["joueurs"]:
        # FBNeo dit « charge » meme quand il manque un fichier du set ou le
        # BIOS Neo Geo ; il n annonce alors aucune entree.
        return {"erreur": "aucune entree annoncee (set incomplet ?)"}
    fiche["nombre"] = len(fiche["boutons"])
    return fiche


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--enfant":
        enfant(sys.argv[2], sys.argv[3], sys.argv[4])
        return
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--coeur", required=True)
    p.add_argument("--roms", default="/mnt/roms")
    p.add_argument("--systemes", nargs="+", default=["fbneo"])
    p.add_argument("--sortie", required=True)
    p.add_argument("--systeme-dir", default="/root/.config/retroarch/system")
    p.add_argument("--delai", type=float, default=60.0)
    p.add_argument("--limite", type=int, default=0)
    p.add_argument("--d-abord", metavar="BOUTONS_ARCADE",
                   help="boutons-arcade.json : les jeux qui ont le plus de boutons passent en premier")
    a = p.parse_args()

    base = {"coeur": os.path.basename(a.coeur), "jeux": {}}
    if os.path.exists(a.sortie):
        with open(a.sortie) as fh:
            base = json.load(fh)
    jeux = base["jeux"]
    liste = []
    for s in a.systemes:
        d = os.path.join(a.roms, s)
        if os.path.isdir(d):
            liste += [(s, f) for f in sorted(os.listdir(d)) if f.lower().endswith((".zip", ".7z"))]
    if a.d_abord:
        # Les jeux a beaucoup de boutons d abord : c est chez eux que le coeur
        # range parfois autrement (poings et pieds des jeux de combat).
        with open(a.d_abord) as fh:
            boutons = json.load(fh).get("jeux", {})
        liste.sort(key=lambda sf: -int((boutons.get(sf[1].rsplit(".", 1)[0]) or {}).get("nombre") or 0))
    if a.limite:
        liste = liste[:a.limite]
    debut = time.time()
    faits = 0
    for n, (systeme, fichier) in enumerate(liste, 1):
        jeu = fichier.rsplit(".", 1)[0]
        if jeu in jeux and "erreur" not in jeux[jeu]:
            continue
        fiche = relever(a.coeur, os.path.join(a.roms, systeme, fichier), a.systeme_dir, a.delai)
        fiche["systeme"] = systeme
        jeux[jeu] = fiche
        faits += 1
        if "erreur" in fiche:
            print("[%d/%d] %s : %s" % (n, len(liste), jeu, fiche["erreur"]), flush=True)
        else:
            print("[%d/%d] %s : %d joueur(s), %d bouton(s) %s" % (
                n, len(liste), jeu, fiche["joueurs"], fiche["nombre"], fiche["boutons"]), flush=True)
        if faits % 25 == 0:
            with open(a.sortie, "w") as fh:
                json.dump(base, fh, indent=1, ensure_ascii=False)
    with open(a.sortie, "w") as fh:
        json.dump(base, fh, indent=1, ensure_ascii=False)
    print("%d jeu(x) releve(s) en %d s" % (faits, time.time() - debut))


if __name__ == "__main__":
    main()
