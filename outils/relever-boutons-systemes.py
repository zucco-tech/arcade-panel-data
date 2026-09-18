#!/usr/bin/env python3
"""Demande a l emulateur de chaque systeme quels boutons il utilise.

A executer SUR LA BORNE (les coeurs sont compiles pour elle) :

    python3 relever-boutons-systemes.py --systemes alice dragon msx ...
    python3 relever-boutons-systemes.py            # tous ceux qui ont des roms

Un coeur libretro annonce ses entrees au frontend : pour chaque bouton de la
manette virtuelle (b, a, y, x, l, r...), le nom de ce qu il commande sur la
machine d origine (« Fire », « Button 1 », « Turbo A »...). C est la seule
source sure : ni la table de couleurs de Recalbox, ni arcade-database ne le
disent pour ces machines.

Chaque coeur est charge dans un PROCESSUS SEPARE, avec un jeu de la liste
d EmulationStation : un coeur qui plante ou qui attend un BIOS ne fait donc
perdre que son propre releve. Le resultat, en JSON sur la sortie standard :

    {"alice": {"coeur": "xroar", "boutons": [["b", "Fire"]], "nombre": 1}, ...}

Les turbos et les fonctions qui ne sont pas des boutons de la machine (« Turbo »,
« Mouse », « Keyboard ») sont signales : le panneau ne les allume pas.
"""

import argparse
import ctypes
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

ROMS = "/recalbox/share/roms"
COEURS = "/usr/lib/libretro"
SYSTEMLIST = "/recalbox/share_init/system/.emulationstation/systemlist.xml"
DOSSIER_SYSTEME = "/recalbox/share/bios"
ROLES = {0: "b", 1: "y", 2: "select", 3: "start", 8: "a", 9: "x", 10: "l", 11: "r",
         12: "l2", 13: "r2", 14: "l3", 15: "r3"}
ENV_SET_INPUT_DESCRIPTORS = 11
ENV_GET_SYSTEM_DIRECTORY = 9
ENV_GET_SAVE_DIRECTORY = 31
ENV_SET_PIXEL_FORMAT = 10
ENV_GET_CAN_DUPE = 13
ENV_GET_VARIABLE = 15
ENV_GET_VARIABLE_UPDATE = 17
ENV_GET_LOG_INTERFACE = 27
EXTENSIONS = (".zip", ".7z", ".chd", ".cue", ".iso", ".bin", ".rom", ".cas", ".k7",
              ".dsk", ".d64", ".tap", ".wav", ".cdt", ".sna", ".nib", ".img", ".mgt")


class Descripteur(ctypes.Structure):
    _fields_ = [("port", ctypes.c_uint), ("device", ctypes.c_uint),
                ("index", ctypes.c_uint), ("id", ctypes.c_uint),
                ("description", ctypes.c_char_p)]


class InfoJeu(ctypes.Structure):
    _fields_ = [("path", ctypes.c_char_p), ("data", ctypes.c_void_p),
                ("size", ctypes.c_size_t), ("meta", ctypes.c_char_p)]


def coeur_du_systeme(systeme):
    """Le coeur de plus haute priorite que Recalbox donne a ce systeme."""
    try:
        racine = ET.parse(SYSTEMLIST).getroot()
    except (OSError, ET.ParseError):
        return None
    for s in racine.iter("system"):
        if s.get("name") != systeme:
            continue
        meilleur = None
        for c in s.iter("core"):
            rang = int(c.get("priority") or 99)
            if meilleur is None or rang < meilleur[0]:
                meilleur = (rang, c.get("name"))
        return meilleur[1] if meilleur else None
    return None


def un_jeu(systeme):
    """Un jeu de la liste d EmulationStation, ou None."""
    dossier = os.path.join(ROMS, systeme)
    try:
        racine = ET.parse(os.path.join(dossier, "gamelist.xml")).getroot()
    except (OSError, ET.ParseError):
        racine = None
    if racine is not None:
        for g in racine.iter("game"):
            chemin = os.path.normpath(os.path.join(dossier, g.findtext("path") or ""))
            if os.path.isfile(chemin):
                return chemin
    try:
        for f in sorted(os.listdir(dossier)):
            if f.lower().endswith(EXTENSIONS):
                return os.path.join(dossier, f)
    except OSError:
        pass
    return None


def enfant(systeme, sortie=None):
    """Charge le coeur du systeme avec un jeu et ecrit ses entrees en JSON.

    Le resultat est ecrit DES que le coeur annonce ses entrees, et non a la
    fin : plusieurs coeurs plantent apres (o2em, 3do le 18/09/2026), et leur
    releve serait perdu."""
    def rendre(contenu):
        texte = json.dumps(contenu, ensure_ascii=False)
        if sortie:
            try:
                with open(sortie, "w") as fh:
                    fh.write(texte + "\n")
            except OSError:
                pass
        print(texte)
        sys.stdout.flush()

    coeur = coeur_du_systeme(systeme)
    chemin = os.path.join(COEURS, "%s_libretro.so" % coeur) if coeur else None
    jeu = un_jeu(systeme)
    if not coeur or not chemin or not os.path.exists(chemin) or not jeu:
        rendre({"erreur": "coeur libretro ou jeu introuvable", "coeur": coeur})
        return
    entrees = []
    dossier = ctypes.c_char_p(DOSSIER_SYSTEME.encode())

    def noter(charge):
        boutons = []
        for port, ident, texte in entrees:
            if port != 0 or ident not in ROLES:
                continue
            role = ROLES[ident]
            if role in ("select", "start") or (role, texte) in boutons:
                continue
            boutons.append((role, texte))
        rendre({"coeur": coeur, "jeu": os.path.basename(jeu), "charge": charge,
                "boutons": boutons})

    def environnement(commande, donnees):
        commande &= 0xFFFF
        if commande == ENV_SET_INPUT_DESCRIPTORS:
            p = ctypes.cast(donnees, ctypes.POINTER(Descripteur))
            i = 0
            while p[i].description:
                entrees.append((p[i].port, p[i].id,
                                p[i].description.decode("utf-8", "replace")))
                i += 1
            noter(None)                # ecrit tout de suite : le coeur peut planter apres
            return True
        if commande in (ENV_GET_SYSTEM_DIRECTORY, ENV_GET_SAVE_DIRECTORY):
            ctypes.cast(donnees, ctypes.POINTER(ctypes.c_char_p))[0] = dossier
            return True
        if commande == ENV_GET_CAN_DUPE:
            ctypes.cast(donnees, ctypes.POINTER(ctypes.c_bool))[0] = True
            return True
        if commande == ENV_SET_PIXEL_FORMAT:
            return True
        if commande == ENV_GET_VARIABLE_UPDATE:
            ctypes.cast(donnees, ctypes.POINTER(ctypes.c_bool))[0] = False
            return True
        return False

    os.dup2(os.open(os.devnull, os.O_WRONLY), 2)      # les coeurs bavardent
    lib = ctypes.CDLL(chemin)
    garder = [ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_uint, ctypes.c_void_p)(environnement),
              ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint,
                               ctypes.c_size_t)(lambda *a: None),
              ctypes.CFUNCTYPE(None, ctypes.c_int16, ctypes.c_int16)(lambda *a: None),
              ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t)(lambda *a: 0),
              ctypes.CFUNCTYPE(None)(lambda: None),
              ctypes.CFUNCTYPE(ctypes.c_int16, ctypes.c_uint, ctypes.c_uint,
                               ctypes.c_uint, ctypes.c_uint)(lambda *a: 0)]
    lib.retro_set_environment(garder[0])
    lib.retro_set_video_refresh(garder[1])
    lib.retro_set_audio_sample(garder[2])
    lib.retro_set_audio_sample_batch(garder[3])
    lib.retro_set_input_poll(garder[4])
    lib.retro_set_input_state(garder[5])
    lib.retro_init()
    lib.retro_load_game.restype = ctypes.c_bool
    info = InfoJeu(jeu.encode(), None, 0, None)
    charge = bool(lib.retro_load_game(ctypes.byref(info)))
    noter(charge)
    for _ in range(2):                                # certains coeurs les posent en jeu
        try:
            lib.retro_run()
        except Exception:
            break
    noter(charge)
    os._exit(0)


def tous_les_systemes():
    rendu = []
    for nom in sorted(os.listdir(ROMS)):
        if not os.path.isdir(os.path.join(ROMS, nom)):
            continue
        if un_jeu(nom):
            rendu.append(nom)
    return rendu


def main():
    if len(sys.argv) > 3 and sys.argv[1] == "--enfant":
        enfant(sys.argv[2], sys.argv[3])
        return
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--systemes", nargs="*", default=None)
    p.add_argument("--delai", type=float, default=60.0)
    a = p.parse_args()
    rendu = {}
    for systeme in (a.systemes or tous_les_systemes()):
        fichier = "/tmp/boutons-%s.json" % systeme
        code = None
        try:
            os.path.exists(fichier) and os.unlink(fichier)
            code = subprocess.run([sys.executable, os.path.abspath(__file__),
                                   "--enfant", systeme, fichier],
                                  capture_output=True, timeout=a.delai).returncode
        except subprocess.TimeoutExpired:
            code = "delai depasse"
        try:
            with open(fichier) as fh:
                rendu[systeme] = json.load(fh)
            rendu[systeme]["fin"] = code
            os.unlink(fichier)
        except (OSError, ValueError):
            rendu[systeme] = {"erreur": "le coeur n a rien rendu (%s)" % code}
        print("%-14s %s" % (systeme, json.dumps(rendu[systeme], ensure_ascii=False)[:160]),
              file=sys.stderr, flush=True)
    print(json.dumps(rendu, ensure_ascii=False, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
