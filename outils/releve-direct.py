#!/usr/bin/env python3
"""Releve des credits DANS le coeur, sans RetroArch ni ecran.

Un coeur libretro (`fbneo_libretro.so`) est un simple fichier programme : on
peut le charger soi-meme, lui demander de calculer des images, appuyer sur
ses boutons et lire sa memoire — sans fenetre, sans son, sans voler le
clavier de personne. C est exactement le meme emulateur que celui de la
borne, donc les adresses trouvees sont celles de la borne.

Ce que ca change, par rapport au releve qui passe par RetroArch :

    600 images calculees en 3 s        au lieu de 10 s de temps reel
    la memoire lue par un pointeur     au lieu d une commande par image
    aucune fenetre, aucun focus vole   le PC reste utilisable
    les DIP du jeu sont visibles       on peut sortir un jeu du free play

Verifie avant d etre ecrit : pzloop2 rend 0x80B1 (le miroir connu de son
0x0450) et 64street rend 0xB6AC, comme le releve par RetroArch.

    python3 releve-direct.py --coeur /opt/coeurs/fbneo_rb.so \
        --roms /mnt/roms --systeme fbneo \
        --base /mnt/recalbox/donnees/credits-arcade.json

Chaque jeu est mesure dans un processus a part, avec une limite de temps :
un pilote qui plante ou qui boucle n emporte pas le releve. La base est
ecrite apres chaque jeu ; une relance reprend ou on en etait.
"""

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time

# --- libretro : les quelques constantes dont on se sert ---------------------

ENV_GET_CAN_DUPE = 3
ENV_GET_SYSTEM_DIRECTORY = 9
ENV_SET_PIXEL_FORMAT = 10
ENV_SET_INPUT_DESCRIPTORS = 11
ENV_GET_VARIABLE = 15
ENV_SET_VARIABLES = 16
ENV_GET_VARIABLE_UPDATE = 17
ENV_GET_LOG_INTERFACE = 27
ENV_GET_SAVE_DIRECTORY = 31

MEMOIRE_SYSTEME = 2              # RETRO_MEMORY_SYSTEM_RAM
MANETTE = 1                      # RETRO_DEVICE_JOYPAD
PIECE = 2                        # RETRO_DEVICE_ID_JOYPAD_SELECT
START = 3                        # RETRO_DEVICE_ID_JOYPAD_START

# --- reglages du releve ------------------------------------------------------

IMAGES_DEMARRAGE = 900           # ~15 s de jeu : le temps de passer les logos
IMAGES_APPUI = 6                 # une piece est une impulsion, pas un appui
IMAGES_APRES_PIECE = 120         # ~2 s : le jeu a le temps d encaisser
IMAGES_APRES_START = 240         # ~4 s : le temps de consommer le credit
PIECES_MAX = 5
ASSEZ = 4                        # en dessous de ce nombre de candidats, on tranche
DELAI_JEU = 180.0                # secondes reelles accordees a un jeu

# Les reglages de carte qu on impose quand le jeu les expose. Un jeu en free
# play n encaisse rien : sans ca, il n y a aucun compteur a trouver.
DIP_IMPOSES = [
    ("free_play", "Off"),
    ("free play", "Off"),
    ("freeplay", "Off"),
    ("service_mode", "Off"),
    ("service mode", "Off"),
    ("test_mode", "Off"),
    ("coin_a", "1 Coin  1 Credits"),
    ("coin_b", "1 Coin  1 Credits"),
]


def options_de_retroarch(chemin):
    """Les options que RetroArch garde pour ce coeur, telles quelles.

    Un coeur charge nu n a aucune option : il prend ses valeurs par defaut,
    qui ne sont pas forcement celles sous lesquelles la borne tourne. On lui
    rend donc exactement ce que RetroArch lui rendrait — c est la seule
    facon d obtenir le meme comportement, et donc les memes adresses."""
    valeurs = {}
    try:
        with open(chemin) as fh:
            for ligne in fh:
                if "=" not in ligne or ligne.lstrip().startswith("#"):
                    continue
                cle, _, valeur = ligne.partition("=")
                valeurs[cle.strip()] = valeur.strip().strip('"')
    except (IOError, OSError):
        pass
    return valeurs


class Descripteur(ctypes.Structure):
    _fields_ = [("port", ctypes.c_uint), ("device", ctypes.c_uint),
                ("index", ctypes.c_uint), ("id", ctypes.c_uint),
                ("description", ctypes.c_char_p)]


class Variable(ctypes.Structure):
    _fields_ = [("key", ctypes.c_char_p), ("value", ctypes.c_char_p)]


class InfoJeu(ctypes.Structure):
    _fields_ = [("path", ctypes.c_char_p), ("data", ctypes.c_void_p),
                ("size", ctypes.c_size_t), ("meta", ctypes.c_char_p)]


class Coeur:
    """Un coeur libretro charge en memoire, avec un jeu dedans."""

    def __init__(self, chemin_coeur, dossier_systeme, options_frontend=None):
        self.dits = []               # ce que le coeur raconte (son journal)
        self.entrees = []            # ce que le jeu declare comme boutons
        self.options = {}            # cle -> libelle;choix|choix|...
        self.imposees = dict(options_frontend or {})   # ce que RetroArch dirait
        self.appuis = {}             # (port, bouton) -> images restantes
        self._dossier = ctypes.c_char_p(dossier_systeme.encode())
        self._valeurs = {}           # garde les c_char_p en vie
        self._garder = []            # idem pour les rappels
        self.lib = ctypes.CDLL(chemin_coeur)
        self._brancher()
        self.lib.retro_init()

    # -- dialogue avec le coeur

    def _environnement(self, commande, donnees):
        commande &= 0xFFFF
        if commande == ENV_SET_INPUT_DESCRIPTORS:
            p = ctypes.cast(donnees, ctypes.POINTER(Descripteur))
            i = 0
            while p[i].description:
                self.entrees.append((p[i].port, p[i].device, p[i].id,
                                     p[i].description.decode("utf-8", "replace")))
                i += 1
            return True
        if commande == ENV_SET_VARIABLES:
            p = ctypes.cast(donnees, ctypes.POINTER(Variable))
            i = 0
            while p[i].key:
                self.options[p[i].key.decode()] = p[i].value.decode("utf-8", "replace")
                i += 1
            return True
        if commande == ENV_GET_VARIABLE:
            v = ctypes.cast(donnees, ctypes.POINTER(Variable))[0]
            choisie = self.imposees.get(v.key.decode())
            if choisie is None:
                return False
            self._valeurs[v.key] = ctypes.c_char_p(choisie.encode())
            v.value = self._valeurs[v.key]
            return True
        if commande == ENV_GET_VARIABLE_UPDATE:
            ctypes.cast(donnees, ctypes.POINTER(ctypes.c_bool))[0] = False
            return True
        if commande == ENV_GET_LOG_INTERFACE:
            # Le coeur veut un endroit ou ecrire son journal. Sans ca il se
            # tait, et l on ne sait pas POURQUOI il refuse une rom. La
            # fonction C est variadique ; on ne recupere que le format, ce
            # qui suffit a lire « romset is unknown » ou « missing file ».
            ctypes.cast(donnees, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.cast(
                self._journal_coeur, ctypes.c_void_p).value
            return True
        if commande in (ENV_GET_SYSTEM_DIRECTORY, ENV_GET_SAVE_DIRECTORY):
            ctypes.cast(donnees, ctypes.POINTER(ctypes.c_char_p))[0] = self._dossier
            return True
        if commande == ENV_GET_CAN_DUPE:
            ctypes.cast(donnees, ctypes.POINTER(ctypes.c_bool))[0] = True
            return True
        return commande == ENV_SET_PIXEL_FORMAT

    def _noter(self, niveau, texte):
        try:
            ligne = (texte or b"").decode("utf-8", "replace").strip()
        except AttributeError:
            return
        if ligne:
            self.dits.append(ligne)

    def _etat_bouton(self, port, appareil, index, bouton):
        return 1 if self.appuis.get((port, bouton), 0) > 0 else 0

    def _brancher(self):
        """Les six rappels que tout frontend doit fournir. L image et le son
        sont jetes : on ne veut que la memoire."""
        types = [
            ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_uint, ctypes.c_void_p),
            ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_size_t),
            ctypes.CFUNCTYPE(None, ctypes.c_int16, ctypes.c_int16),
            ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t),
            ctypes.CFUNCTYPE(None),
            ctypes.CFUNCTYPE(ctypes.c_int16, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint),
        ]
        self._journal_coeur = ctypes.CFUNCTYPE(
            None, ctypes.c_int, ctypes.c_char_p)(self._noter)
        self._garder = [types[0](self._environnement),
                        types[1](lambda *a: None),
                        types[2](lambda *a: None),
                        types[3](lambda *a: 0),
                        types[4](lambda: None),
                        types[5](self._etat_bouton)]
        self.lib.retro_set_environment(self._garder[0])
        self.lib.retro_set_video_refresh(self._garder[1])
        self.lib.retro_set_audio_sample(self._garder[2])
        self.lib.retro_set_audio_sample_batch(self._garder[3])
        self.lib.retro_set_input_poll(self._garder[4])
        self.lib.retro_set_input_state(self._garder[5])

    # -- le jeu

    def choisir_les_dip(self):
        """Impose les reglages de carte qui nous interessent, quand le jeu
        les expose : pas de free play, pas de mode service, une piece pour
        un credit. Ce que le jeu ne propose pas est simplement ignore."""
        choisis = {}
        for cle, valeur in self.options.items():
            bas = cle.lower()
            for motif, voulue in DIP_IMPOSES:
                if motif in bas:
                    choix = self.options[cle].split(";")[-1].split("|")
                    choix = [c.strip() for c in choix]
                    if voulue in choix:
                        choisis[cle] = voulue
                    elif motif.startswith("coin") and choix:
                        choisis[cle] = choix[0]
                    break
        self.imposees.update(choisis)
        return choisis

    def charger(self, chemin_rom):
        self.lib.retro_load_game.restype = ctypes.c_bool
        info = InfoJeu(chemin_rom.encode(), None, 0, None)
        if not self.lib.retro_load_game(ctypes.byref(info)):
            return False
        self.lib.retro_set_controller_port_device(0, MANETTE)
        self.lib.retro_set_controller_port_device(1, MANETTE)
        self.lib.retro_get_memory_data.restype = ctypes.c_void_p
        self.lib.retro_get_memory_size.restype = ctypes.c_size_t
        self.taille = self.lib.retro_get_memory_size(MEMOIRE_SYSTEME)
        self.adresse = self.lib.retro_get_memory_data(MEMOIRE_SYSTEME)
        return bool(self.taille and self.adresse)

    def images(self, combien):
        """Calcule `combien` images, en decomptant les appuis en cours."""
        for _ in range(combien):
            self.lib.retro_run()
            for touche in list(self.appuis):
                self.appuis[touche] -= 1

    def appuyer(self, bouton, joueur=1, images=IMAGES_APPUI):
        self.appuis[(joueur - 1, bouton)] = images

    def photo(self):
        return bytes((ctypes.c_ubyte * self.taille).from_address(self.adresse))


# --- la mesure elle-meme -------------------------------------------------------

def montes_de_un(avant, apres):
    """Les octets qui valent exactement un de plus qu avant.

    Le 0x99 ecarte les compteurs BCD satures et les octets qui defilent :
    un compteur de credits ne depasse jamais cette valeur."""
    return {a for a in range(len(apres))
            if apres[a] == (avant[a] + 1) & 0xFF and avant[a] < 0x99}


def chercher_compteur(coeur, joueur, journal):
    """L octet qui monte de 1 a chaque piece de ce joueur, ou None."""
    candidats = None
    avant = coeur.photo()
    for numero in range(1, PIECES_MAX + 1):
        coeur.appuyer(PIECE, joueur)
        coeur.images(IMAGES_APRES_PIECE)
        apres = coeur.photo()
        montes = montes_de_un(avant, apres)
        candidats = montes if candidats is None else candidats & montes
        avant = apres
        journal("  piece %d joueur %d : %d candidat(s)" % (numero, joueur, len(candidats)))
        if not candidats:
            return set()
        if len(candidats) <= ASSEZ:
            break
    return candidats


def mesurer(chemin_coeur, chemin_rom, dossier_systeme, bavard, options=None):
    """Mesure un jeu. Renvoie la fiche, ou un dictionnaire d erreur."""
    lignes = []

    def journal(message):
        lignes.append(message)
        if bavard:
            print(message, flush=True)

    coeur = Coeur(chemin_coeur, dossier_systeme, options)
    if not coeur.charger(chemin_rom):
        # On rapporte ce que le coeur a dit : « romset is unknown », un
        # fichier manquant... C est la difference entre « ca ne marche pas »
        # et une raison sur laquelle on peut agir.
        dit = " | ".join(coeur.dits[-3:]) if coeur.dits else "sans explication"
        return {"erreur": "rom refusee (%s)" % dit[:160]}, lignes
    imposes = coeur.choisir_les_dip()
    if imposes:
        journal("  reglages imposes : %s" % ", ".join(sorted(imposes.values())))
    coeur.images(IMAGES_DEMARRAGE)

    candidats = chercher_compteur(coeur, 1, journal)
    if not candidats:
        return {"erreur": "aucun candidat"}, lignes

    # Le START doit FAIRE DESCENDRE le compteur : c est ce qui distingue un
    # solde de credits d un total de pieces encaissees.
    avant = coeur.photo()
    coeur.appuyer(START, 1)
    coeur.images(IMAGES_APRES_START)
    apres = coeur.photo()
    descendus = [a for a in sorted(candidats) if apres[a] < avant[a]]
    if not descendus:
        return {"erreur": "candidats non confirmes", "candidats": len(candidats)}, lignes
    adresse = descendus[0]
    miroirs = [a for a in descendus[1:]]
    journal("  APPRIS 0x%04X (%d -> %d)%s"
            % (adresse, avant[adresse], apres[adresse],
               "  miroirs : " + ", ".join("0x%04X" % m for m in miroirs) if miroirs else ""))

    # Le joueur 2 : sa piece a lui, et son compteur a lui — ou le meme.
    avant = coeur.photo()
    candidats_j2 = chercher_compteur(coeur, 2, journal)
    adresse_j2 = None
    commun = False
    if candidats_j2:
        if adresse in candidats_j2:
            commun = True
            journal("  le joueur 2 alimente le MEME compteur")
        else:
            adresse_j2 = sorted(candidats_j2)[0]
            journal("  joueur 2 en 0x%04X" % adresse_j2)

    fiche = {
        "ram": {"taille": coeur.taille, "commande": "coeur direct"},
        "credits": {
            "adresse": adresse, "adresse_hex": "0x%04X" % adresse, "octets": 1,
            "miroirs": ["0x%04X" % m for m in miroirs],
            "verifie_insertion": True, "verifie_consommation": True,
            "entree_piece": "select",
            "compteur_commun": commun,
            "adresse_j2": adresse_j2,
            "adresse_j2_hex": ("0x%04X" % adresse_j2) if adresse_j2 is not None else None,
            "j2_verifie_consommation": False,
        },
        "dip_imposes": imposes,
    }
    return fiche, lignes


# --- un jeu par processus ------------------------------------------------------

def enfant():
    """Mesure un jeu et imprime la fiche en JSON. Le processus est jete
    ensuite : aucun pilote ne peut polluer le suivant."""
    _, coeur, rom, dossier, options_ra = sys.argv[1:6]
    os.dup2(os.open(os.devnull, os.O_WRONLY), 2)      # le coeur bavarde sur stderr
    try:
        fiche, lignes = mesurer(coeur, rom, dossier, False,
                                options_de_retroarch(options_ra))
    except Exception as souci:                         # un pilote peut planter
        fiche, lignes = {"erreur": "pilote en echec (%s)" % souci}, []
    sys.stdout.write(json.dumps({"fiche": fiche, "lignes": lignes}) + "\n")
    sys.stdout.flush()
    os._exit(0)


def mesurer_isole(chemin_coeur, chemin_rom, dossier_systeme, delai, options_ra):
    try:
        sortie = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--enfant",
             chemin_coeur, chemin_rom, dossier_systeme, options_ra],
            capture_output=True, timeout=delai)
    except subprocess.TimeoutExpired:
        return {"erreur": "delai depasse"}, []
    lignes = sortie.stdout.decode("utf-8", "replace").strip().splitlines()
    if not lignes:
        return {"erreur": "pilote plante (code %d)" % sortie.returncode}, []
    try:
        brut = json.loads(lignes[-1])
    except ValueError:
        return {"erreur": "reponse illisible"}, []
    return brut["fiche"], brut["lignes"]


# --- la base ------------------------------------------------------------------

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
    p.add_argument("--coeur", default="/opt/coeurs/fbneo_rb.so")
    p.add_argument("--coeur-nomme", default="FinalBurn Neo")
    p.add_argument("--roms", default="/mnt/roms")
    p.add_argument("--systeme", default="fbneo")
    p.add_argument("--base", required=True)
    p.add_argument("--systeme-dir", default="/root/.config/retroarch/system")
    p.add_argument("--options", default="/root/.config/retroarch/config/FinalBurn Neo/FinalBurn Neo.opt",
                   help="les options que RetroArch garde pour ce coeur")
    p.add_argument("--delai", type=float, default=DELAI_JEU)
    p.add_argument("--limite", type=int, default=0)
    p.add_argument("--jeux", nargs="*", default=None,
                   help="ne mesurer que ces jeux (essai)")
    p.add_argument("--arret", default="/tmp/arret-nuit")
    p.add_argument("--sec", action="store_true",
                   help="ne rien ecrire : afficher seulement ce qu on trouverait")
    a = p.parse_args()

    dossier = os.path.join(a.roms, a.systeme)
    noms = a.jeux or sorted(f.rsplit(".", 1)[0] for f in os.listdir(dossier)
                            if f.lower().endswith((".zip", ".7z")))
    base = charger_base(a.base)
    prefixe = a.coeur_nomme.lower().replace(" ", "-")
    # Une liste de jeux donnee a la main est toujours mesuree : c est ce qui
    # permet de controler l outil contre des fiches deja connues.
    if a.jeux:
        reste = list(noms)
    else:
        reste = [n for n in noms if "%s/%s" % (prefixe, n) not in base["jeux"]]
    if a.limite:
        reste = reste[:a.limite]
    print("%s : %d jeu(x) a mesurer (%d deja connus)"
          % (a.systeme, len(reste), len(noms) - len(reste)), flush=True)

    appris = ecartes = 0
    debut = time.time()
    for n, jeu in enumerate(reste, 1):
        if os.path.exists(a.arret):
            print("arret demande", flush=True)
            break
        chemin = None
        for extension in (".zip", ".7z"):
            candidat = os.path.join(dossier, jeu + extension)
            if os.path.exists(candidat):
                chemin = candidat
                break
        if chemin is None:
            continue
        print("[%d/%d] %s/%s" % (n, len(reste), a.systeme, jeu), flush=True)
        parti = time.time()
        fiche, lignes = mesurer_isole(a.coeur, chemin, a.systeme_dir, a.delai, a.options)
        for ligne in lignes:
            print(ligne, flush=True)
        cle = "%s/%s" % (prefixe, jeu)
        if "erreur" in fiche:
            ecartes += 1
            print("  difficile : %s (%.0f s)" % (fiche["erreur"], time.time() - parti), flush=True)
            if not a.sec:
                base["difficiles"][cle] = {"jeu": jeu, "systeme": a.systeme,
                                           "raison": fiche["erreur"],
                                           "le": time.strftime("%Y-%m-%d")}
        else:
            appris += 1
            print("  en %.0f s" % (time.time() - parti), flush=True)
            if not a.sec:
                fiche.update({"jeu": jeu, "systeme": a.systeme, "core": a.coeur_nomme,
                              "releve": {"le": time.strftime("%Y-%m-%d"),
                                         "methode": "coeur direct"}})
                base["jeux"][cle] = fiche
                base["difficiles"].pop(cle, None)
        if not a.sec:
            ecrire_base(a.base, base)
    duree = time.time() - debut
    print("%d appris, %d ecartes, en %d min (%.1f s par jeu)"
          % (appris, ecartes, duree / 60, duree / max(appris + ecartes, 1)), flush=True)


if __name__ == "__main__":
    main()
