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
# Formats d image que le coeur peut demander (RETRO_PIXEL_FORMAT_*).
FORMATS = {0: "0RGB1555", 1: "XRGB8888", 2: "RGB565"}
MANETTE = 1                      # RETRO_DEVICE_JOYPAD
PIECE = 2                        # RETRO_DEVICE_ID_JOYPAD_SELECT
START = 3                        # RETRO_DEVICE_ID_JOYPAD_START

# --- reglages du releve ------------------------------------------------------

# On n attend pas une duree fixe, on attend que la machine VIVE. Certaines
# cartes restent figees tres longtemps pendant leur test de memoire : 1944
# ne bouge pas une seule fois entre l image 300 et l image 2400, et met une
# piece a l image 900 revient a la glisser dans une borne eteinte. Mesure du
# 12/09/2026 : c est ce qui produisait la plupart des « aucun candidat ».
IMAGES_PAS = 300                 # on regarde la RAM tous les 300 images
IMAGES_MAX_DEMARRAGE = 9000      # ~2 min 30 de jeu, large pour un Neo Geo
OCTETS_VIVANT = 20               # au-dela, la machine travaille vraiment
IMAGES_APRES_VIVANT = 600        # on la laisse arriver a son ecran d attente
# Quand la premiere tentative echoue, on insiste : une piece toutes les 600
# images, sur plusieurs minutes de jeu emule. Aucun critere ne dit de facon
# fiable QUAND une carte est prete — Battle Garegga s agite sur 10 % de sa
# RAM pendant son test de memoire, 1944 sur 0,1 % une fois en attract — donc
# plutot que de deviner l instant, on paie regulierement jusqu a ce que ca
# prenne. Seuls les jeux recalcitrants coutent ce temps-la.
INSISTANCE_PIECES = 8
INSISTANCE_ECART = 600
IMAGES_APPUI = 6                 # une piece est une impulsion, pas un appui
IMAGES_APRES_PIECE = 120         # ~2 s : le jeu a le temps d encaisser
IMAGES_APRES_START = 240         # ~4 s : le temps de consommer le credit
PIECES_MAX = 5
ASSEZ = 4                        # en dessous de ce nombre de candidats, on tranche
ACCORDS_MIN = 2                  # un octet doit monter sur au moins deux pieces
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
        self.image = None            # derniere image calculee, pour la regarder
        self.format = 0              # format des pixels, annonce par le coeur
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
        if commande == ENV_SET_PIXEL_FORMAT:
            self.format = ctypes.cast(donnees, ctypes.POINTER(ctypes.c_int))[0]
            return self.format in FORMATS
        return False

    def _noter(self, niveau, texte):
        try:
            ligne = (texte or b"").decode("utf-8", "replace").strip()
        except AttributeError:
            return
        if ligne:
            self.dits.append(ligne)

    def _voir(self, donnees, largeur, hauteur, pas):
        """Garde la derniere image. Un jeu qui refuse nos pieces a presque
        toujours une raison ecrite a l ecran — « FREE PLAY », « COIN ERROR »,
        un test de memoire. La regarder vaut mieux que la deviner."""
        if not donnees or not largeur or not hauteur:
            return
        taille = pas * hauteur
        self.image = (bytes((ctypes.c_ubyte * taille).from_address(donnees)),
                      largeur, hauteur, pas, self.format)

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
                        types[1](self._voir),
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

def montes16(avant, apres):
    """Les compteurs sur DEUX octets qui valent un de plus.

    Certaines cartes comptent les credits sur seize bits — l octet bas
    seul ne monte alors pas de 1 quand il passe de 255 a 0, et un compteur
    parfaitement sain restait invisible. On regarde les deux sens
    d ecriture, petit-boutiste et gros-boutiste, et on renvoie l adresse du
    couple avec le sens qui convient."""
    trouves = set()
    for a in range(len(apres) - 1):
        for sens, vieux, neuf in (
                ("pb", avant[a] | (avant[a + 1] << 8), apres[a] | (apres[a + 1] << 8)),
                ("gb", (avant[a] << 8) | avant[a + 1], (apres[a] << 8) | apres[a + 1])):
            if neuf == vieux + 1 and vieux < 0x2710:      # 10000 credits, jamais plus
                trouves.add((a, sens))
    return trouves


def valeur16(photo, adresse, sens):
    bas, haut = photo[adresse], photo[adresse + 1]
    return bas | (haut << 8) if sens == "pb" else (bas << 8) | haut


def chercher_compteur16(coeur, journal):
    """Le meme travail que pour un octet, mais sur des couples d octets.

    N est appele qu en dernier recours : c est deux fois plus de comparaisons
    pour une minorite de cartes."""
    accords = {}
    avant = coeur.photo()
    for _ in range(3):
        coeur.appuyer(PIECE, 1)
        coeur.images(IMAGES_APRES_PIECE)
        apres = coeur.photo()
        for couple in montes16(avant, apres):
            accords[couple] = accords.get(couple, 0) + 1
        avant = apres
    solides = {c: n for c, n in accords.items() if n >= ACCORDS_MIN}
    if not solides:
        return None
    avant = coeur.photo()
    for _ in range(STARTS_MAX):
        coeur.appuyer(START, 1)
        coeur.images(IMAGES_APRES_START)
        apres = coeur.photo()
        for (adresse, sens), nombre in sorted(solides.items(), key=lambda x: -x[1]):
            if valeur16(apres, adresse, sens) < valeur16(avant, adresse, sens):
                journal("  compteur sur deux octets en 0x%04X (%s), %d -> %d"
                        % (adresse, "petit-boutiste" if sens == "pb" else "gros-boutiste",
                           valeur16(avant, adresse, sens), valeur16(apres, adresse, sens)))
                return adresse, sens, nombre
        avant = apres
    return None


def attendre_vivant(coeur, journal):
    """Fait tourner la machine jusqu a ce que sa memoire s anime.

    Renvoie le nombre d images calculees, ou None si elle est restee figee :
    un jeu qui ne vit pas n encaissera aucune piece, et le dire est plus
    utile que de chercher un compteur qui ne bougera pas."""
    avant = coeur.photo()
    total = 0
    while total < IMAGES_MAX_DEMARRAGE:
        coeur.images(IMAGES_PAS)
        total += IMAGES_PAS
        apres = coeur.photo()
        bouge = sum(1 for a in range(len(apres)) if apres[a] != avant[a])
        avant = apres
        if bouge > OCTETS_VIVANT and total >= 2 * IMAGES_PAS:
            coeur.images(IMAGES_APRES_VIVANT)
            journal("  vivant apres %d images" % total)
            return total
    return None


def enregistrer_image(coeur, chemin):
    """Ecrit la derniere image du jeu en PNG. Vrai si l image existe."""
    if not coeur.image:
        return False
    brut, largeur, hauteur, pas, format_ = coeur.image
    try:
        from PIL import Image
    except ImportError:
        return False
    pixels = bytearray(largeur * hauteur * 3)
    for y in range(hauteur):
        ligne = y * pas
        for x in range(largeur):
            if format_ == 1:                      # XRGB8888
                i = ligne + x * 4
                r, v, b = brut[i + 2], brut[i + 1], brut[i]
            else:
                i = ligne + x * 2
                mot = brut[i] | (brut[i + 1] << 8)
                if format_ == 2:                  # RGB565
                    r = (mot >> 11 & 0x1F) << 3
                    v = (mot >> 5 & 0x3F) << 2
                    b = (mot & 0x1F) << 3
                else:                             # 0RGB1555
                    r = (mot >> 10 & 0x1F) << 3
                    v = (mot >> 5 & 0x1F) << 3
                    b = (mot & 0x1F) << 3
            j = (y * largeur + x) * 3
            pixels[j], pixels[j + 1], pixels[j + 2] = r, v, b
    Image.frombytes("RGB", (largeur, hauteur), bytes(pixels)).save(chemin)
    return True


def montes_de_un(avant, apres):
    """Les octets qui valent exactement un de plus qu avant.

    Deux facons de valoir un de plus : en binaire (7 -> 8) et en BCD, ou
    chaque quartet compte jusqu a 9 (0x09 -> 0x10). Des cartes entieres
    comptent leurs credits en BCD parce qu elles les affichent directement.

    Le 0x99 ecarte les octets qui defilent : un compteur de credits ne
    depasse jamais cette valeur."""
    montes = set()
    for a in range(len(apres)):
        vieux, neuf = avant[a], apres[a]
        if vieux >= 0x99:
            continue
        if neuf == (vieux + 1) & 0xFF:
            montes.add(a)
        elif vieux & 0x0F == 9 and neuf == vieux + 7:      # 0x09 -> 0x10, BCD
            montes.add(a)
    return montes


def chercher_compteur(coeur, joueur, journal):
    """Les octets qui se comportent comme un compteur de credits.

    On ne demande pas qu un octet monte a CHAQUE piece : des cartes en
    avalent une puis ignorent les suivantes (1944 n en accepte qu une), et
    l exigence stricte jetait alors tout le travail. On compte donc les
    accords : un octet retenu doit etre monte sur au moins deux pieces. Le
    tri final, lui, ne pardonne pas — c est le START qui tranche."""
    accords = {}
    avant = coeur.photo()
    for numero in range(1, PIECES_MAX + 1):
        coeur.appuyer(PIECE, joueur)
        coeur.images(IMAGES_APRES_PIECE)
        apres = coeur.photo()
        for a in montes_de_un(avant, apres):
            accords[a] = accords.get(a, 0) + 1
        avant = apres
        retenus = {a for a, n in accords.items() if n >= ACCORDS_MIN}
        journal("  piece %d joueur %d : %d octet(s) d accord sur %d vus"
                % (numero, joueur, len(retenus), len(accords)))
        if retenus and len(retenus) <= ASSEZ and numero >= ACCORDS_MIN + 1:
            break
    # On rend TOUT ce qui est monte au moins une fois, avec son nombre
    # d accords. Ne garder que le plus fidele etait une erreur : sur Battle
    # Garegga, l octet le plus fidele est le compteur de pieces encaissees
    # (il monte encore au START), tandis que le vrai solde de credits etait
    # dans les dix autres, jetes. C est le START qui doit trancher, pas
    # nous — lui seul distingue un solde d un total.
    return accords


def verifier_miroirs(coeur, adresse, soupcons):
    """Garde les octets qui suivent VRAIMENT le compteur.

    Porter la meme valeur ne suffit pas : quand un compteur passe de 1 a 0,
    des dizaines d octets de jeu en font autant au meme instant. On met donc
    une piece de plus et on ne garde que ceux qui montent avec lui, et qui
    restent egaux a lui."""
    if not soupcons:
        return []
    avant = coeur.photo()
    coeur.appuyer(PIECE, 1)
    coeur.images(IMAGES_APRES_PIECE)
    apres = coeur.photo()
    if apres[adresse] <= avant[adresse]:
        return []                      # la piece n a pas ete prise : on ne tranche pas
    return [b for b in soupcons
            if apres[b] == apres[adresse] and avant[b] == avant[adresse]
            and apres[b] > avant[b]]


STARTS_MAX = 3                   # on insiste : le premier START ne consomme pas toujours


def confirmer_au_start(coeur, accords, journal):
    """Parmi les octets montes, ceux que le START fait DESCENDRE.

    C est la seule preuve qu on tient un solde de credits et non un total de
    pieces encaissees.

    Deux precautions apprises a la mesure :
      - le premier START ne consomme pas toujours (le jeu peut etre en train
        de finir une animation) ; on appuie donc jusqu a trois fois ;
      - on exige d abord un octet monte a CHAQUE piece. Sans cela, sur Air
        Gallet un octet de bruit monte une seule fois et descendu au premier
        START passait devant le vrai compteur, qui n avait pas encore ete
        consomme."""
    exigeant = max(accords.values()) if accords else 0
    faible = None
    for essai in range(1, STARTS_MAX + 1):
        avant = coeur.photo()
        coeur.appuyer(START, 1)
        coeur.images(IMAGES_APRES_START)
        apres = coeur.photo()
        descendus = sorted((a for a in accords if apres[a] < avant[a]),
                           key=lambda a: (-accords[a], a))
        forts = [a for a in descendus if accords[a] >= max(ACCORDS_MIN, exigeant)]
        if forts:
            journal("  START %d : %s descend (%d -> %d), monte a %d piece(s)"
                    % (essai, "0x%04X" % forts[0], avant[forts[0]], apres[forts[0]],
                       accords[forts[0]]))
            return forts + [a for a in descendus if a not in forts], avant, apres
        if descendus and faible is None:
            faible = (descendus, avant, apres)
    if faible:
        journal("  START : seul %s descend, monte a %d piece(s) seulement"
                % ("0x%04X" % faible[0][0], accords[faible[0][0]]))
        return faible
    return [], avant, apres


def insister(coeur, accords, journal):
    """Deuxieme chance : on paie regulierement pendant plusieurs minutes.

    Renvoie (descendus, avant, apres) comme confirmer_au_start, ou None."""
    journal("  rien de confirme : on insiste sur %d pieces"
            % INSISTANCE_PIECES)
    for numero in range(1, INSISTANCE_PIECES + 1):
        avant = coeur.photo()
        # On alterne les deux monnayeurs : des cartes n acceptent qu une
        # piece par fente avant un temps mort, et les deux alimentent le
        # meme compteur. Alterner double donc les chances d etre encaisse.
        coeur.appuyer(PIECE, 1 if numero % 2 else 2)
        coeur.images(INSISTANCE_ECART)
        for a in montes_de_un(avant, coeur.photo()):
            accords[a] = accords.get(a, 0) + 1
        if numero % 2:
            continue                       # on ne teste le START qu une fois sur deux
        descendus, avant, apres = confirmer_au_start(coeur, accords, journal)
        if descendus:
            journal("  confirme apres %d piece(s) d insistance" % numero)
            return descendus, avant, apres
    return None


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
    if attendre_vivant(coeur, journal) is None:
        return {"erreur": "jeu inanime"}, lignes

    accords = chercher_compteur(coeur, 1, journal)
    if not accords:
        return {"erreur": "aucun candidat"}, lignes

    # Le START doit FAIRE DESCENDRE le compteur : c est ce qui distingue un
    # solde de credits d un total de pieces encaissees.
    def solide(liste):
        """Un resultat est solide si son octet est monte a plusieurs pieces."""
        return liste and accords.get(liste[0], 0) >= ACCORDS_MIN

    descendus, avant, apres = confirmer_au_start(coeur, accords, journal)
    if not solide(descendus):
        # Rien, ou seulement un octet monte une seule fois : on insiste avant
        # de s en contenter. Sur Battle Garegga, se contenter du premier
        # octet venu donnait une adresse fausse alors que la bonne
        # apparaissait deux pieces plus tard.
        insiste = insister(coeur, accords, journal)
        if solide(insiste[0] if insiste else None):
            descendus, avant, apres = insiste
        elif not descendus and insiste:
            descendus, avant, apres = insiste
        elif not descendus:
            large = chercher_compteur16(coeur, journal)
            if large is None:
                return {"erreur": "candidats non confirmes", "candidats": len(accords)}, lignes
            adresse, sens, _ = large
            fiche = {
                "ram": {"taille": coeur.taille, "commande": "coeur direct"},
                "credits": {
                    "adresse": adresse, "adresse_hex": "0x%04X" % adresse, "octets": 2,
                    "sens": sens, "miroirs": [],
                    "verifie_insertion": True, "verifie_consommation": True,
                    "entree_piece": "select", "compteur_commun": False,
                    "adresse_j2": None, "adresse_j2_hex": None,
                    "j2_verifie_consommation": False,
                },
                "dip_imposes": imposes,
            }
            return fiche, lignes
    adresse = descendus[0]
    # Un miroir n est pas « un octet qui descend aussi » : c est le MEME
    # compteur vu a une autre adresse, donc il porte la meme valeur avant et
    # apres. Sans cette exigence, un jeu en attract donnait quatre-vingt-dix
    # « miroirs » qui n etaient que des octets de jeu en train de baisser.
    soupcons = [b for b in descendus[1:]
                if avant[b] == avant[adresse] and apres[b] == apres[adresse]]
    miroirs = verifier_miroirs(coeur, adresse, soupcons)
    journal("  APPRIS 0x%04X (%d -> %d)%s"
            % (adresse, avant[adresse], apres[adresse],
               "  miroirs : " + ", ".join("0x%04X" % m for m in miroirs) if miroirs else ""))

    # Le joueur 2 : sa piece a lui, et son compteur a lui — ou le meme.
    avant = coeur.photo()
    candidats_j2 = set(chercher_compteur(coeur, 2, journal))
    adresse_j2 = None
    commun = False
    if candidats_j2:
        if adresse in candidats_j2 or candidats_j2 & set(miroirs):
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
    p.add_argument("--part", default=None,
                   help="« 2/4 » : ne traiter que la deuxieme part sur quatre. "
                        "Les parts sont entrelacees, donc de difficulte egale.")
    p.add_argument("--reference", default=None,
                   help="base a consulter pour savoir ce qui est deja mesure, "
                        "quand on ecrit dans un fichier a part")
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
    connue = charger_base(a.reference) if a.reference else base
    prefixe = a.coeur_nomme.lower().replace(" ", "-")
    # Une liste de jeux donnee a la main est toujours mesuree : c est ce qui
    # permet de controler l outil contre des fiches deja connues.
    if a.jeux:
        reste = list(noms)
    else:
        reste = [n for n in noms if "%s/%s" % (prefixe, n) not in connue["jeux"]]
    if a.part:
        rang, total = (int(x) for x in a.part.split("/"))
        reste = reste[rang - 1::total]      # entrelacees : meme difficulte pour tous
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
