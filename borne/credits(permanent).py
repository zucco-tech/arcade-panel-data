#!/usr/bin/env python3
"""
Bouton coin clignotant quand le jeu arcade n'a plus de credit — et qui
apprend tout seul l'adresse du compteur, jeu par jeu, pendant que tu joues.

A deposer dans /recalbox/share/userscripts/ sous le nom exact :

    credits(permanent).py

Le "(permanent)" fait lancer le script une seule fois par le frontend, qui le
laisse ensuite tourner. Il ne remplace ni ne modifie marquee(permanent).py :
les deux cohabitent, ils ne touchent pas aux memes choses.

Le nombre de credits n'existe ni dans Recalbox ni dans RetroArch : c'est une
variable en RAM du jeu emule, a une adresse propre a chaque jeu. RetroArch
sait la lire par son interface reseau (READ_CORE_RAM, UDP 55355, activee par
network_cmd_enable dans retroarchcustom.cfg).

Pour trouver cette adresse, on regarde la RAM avant et apres une piece : le
compteur est l'octet qui monte de exactement 1. Deux ou trois pieces et il ne
reste qu'un candidat ; un appui sur START tranche la derniere ambiguite,
puisque le solde redescend quand on le consomme alors qu'un total de pieces
encaissees, non. La fiche est alors ecrite dans BASE et le jeu est connu
pour toujours.

Ce que ca coute a la borne :

  * jeu deja connu   : un octet lu trois fois par seconde, rien d'autre ;
  * jeu en cours d'apprentissage : une photo de la RAM toutes les 5 s et une
    a chaque piece — 4 commandes RetroArch, soit 4 images de jeu ;
  * jeu appris       : plus une seule photo, definitivement.

Cote LED, on n'ecrit QUE dans "brightness". Les couleurs sont posees par
recalbox_allinone_rgb.sh via "multi_intensity" : on n'y touche pas, donc rien
n'entre en conflit avec le code de la carte, et une remise a 255 rend la LED
exactement telle que la carte l'avait laissee.

Aucune dependance : uniquement la bibliotheque standard.
"""

import glob
import json
import os
import re
import select
import signal
import socket
import struct
import sys
import time

# --- Configuration -------------------------------------------------------

BASE = "/recalbox/share/system/credits-arcade.json"
BASE_BOUTONS = "/recalbox/share/system/boutons-arcade.json"

# Version du format de la base. Une base plus ancienne est convertie a la
# volee au demarrage : aucun releve n'est perdu.
SCHEMA = 3
OUTIL = "credits(permanent).py"

# Le journal est sur le partage, et non dans /tmp, pour rester lisible depuis
# le reseau sans ouvrir un shell sur la borne. Il est plafonne : sur une carte
# SD, un fichier qui grossit sans fin finit toujours par poser probleme.
JOURNAL = "/recalbox/share/system/credits.log"
JOURNAL_MAX = 200 * 1024
STATE_FILE = "/tmp/es_state.inf"

RA_HOTE = "127.0.0.1"
RA_PORT = 55355
RA_TIMEOUT = 0.5

# Quelles LED eclairent quel bouton reel.
#
# Le nom que le driver donne aux LED et le cablage du panneau ne concordent
# pas sur cette borne : les LED que le module appelle "start" eclairent le
# bouton piece, et inversement. Si tu vois le contraire, echange ces deux
# lignes — c'est le seul endroit a changer.
LEDS_PIECE = ("/sys/class/leds/aio_p1_start_1",
              "/sys/class/leds/aio_p1_start_2")
LEDS_START = ("/sys/class/leds/aio_p1_select_1",
              "/sys/class/leds/aio_p1_select_2")
LEDS_START_P2 = ("/sys/class/leds/aio_p2_select_1",
                 "/sys/class/leds/aio_p2_select_2")
# Meme inversion que pour le joueur 1 : les LED nommees "start" eclairent
# le bouton PIECE.
LEDS_PIECE_P2 = ("/sys/class/leds/aio_p2_start_1",
                 "/sys/class/leds/aio_p2_start_2")

# Les huit boutons de jeu de chaque joueur, dans l ordre ou le module les
# nomme. On n allume que ceux dont le jeu se sert.
LEDS_JEU = {
    1: [("/sys/class/leds/aio_p1_b%d_1" % n, "/sys/class/leds/aio_p1_b%d_2" % n)
        for n in range(1, 9)],
    2: [("/sys/class/leds/aio_p2_b%d_1" % n, "/sys/class/leds/aio_p2_b%d_2" % n)
        for n in range(1, 9)],
}

# Correspondance entre le bouton logique du jeu (BUTTON1, BUTTON2...) et la
# LED physique. Reprise de recalbox_allinone_rgb.sh, qui range le panneau
# ainsi :
#
#     rangee haute : LED 1 2 3   ->  boutons 3 4 5
#     rangee basse : LED 4 5 6   ->  boutons 1 2 6
#
# Si l ordre ne correspond pas a ton panneau, c est la seule ligne a changer.
ORDRE_BOUTONS = [3, 4, 5, 1, 2, 6, 7, 8]

# Couleurs nommees par la base des boutons, telles qu elles sont ecrites sur
# les vraies bornes. Le materiel attend du G R B, la fonction couleur() s en
# charge.
TEINTES = {
    "red": (0xFF, 0x00, 0x00), "blue": (0x00, 0x00, 0xFF),
    "green": (0x00, 0xFF, 0x00), "yellow": (0xFF, 0xFF, 0x00),
    "white": (0xFF, 0xFF, 0xFF), "black": (0x20, 0x20, 0x20),
    "orange": (0xFF, 0x60, 0x00), "purple": (0x80, 0x00, 0xFF),
    "pink": (0xFF, 0x40, 0x80), "cyan": (0x00, 0xFF, 0xFF),
    "grey": (0x60, 0x60, 0x60), "gray": (0x60, 0x60, 0x60),
}

# Ordre des composantes attendu par le materiel.
#
# Les WS2812B recoivent leurs couleurs dans l'ordre vert, rouge, bleu, alors
# que le module les declare dans l'ordre rouge, vert, bleu. Ecrire du rouge
# franc allume donc du vert — constate sur la borne. On ecrit les couleurs de
# facon lisible et cette fonction les remet dans l'ordre du fil.
ORDRE_MATERIEL = (1, 0, 2)              # G R B

def couleur(rouge, vert, bleu):
    """Une couleur lisible, ecrite dans l'ordre que le materiel attend."""
    composantes = (rouge, vert, bleu)
    return " ".join("0x%02X" % composantes[i] for i in ORDRE_MATERIEL)


# None garde la couleur que recalbox_allinone_rgb.sh a posee pour le systeme.
# La couleur d'origine est relue avant, et remise des que le clignotement
# s'arrete : rien n'est perdu.
COULEUR_PIECE = couleur(0xFF, 0x00, 0x00)   # rouge : mets une piece
COULEUR_START = None                        # sa couleur d'origine

CODE_PIECE = 314                # BTN_SELECT
CODE_START = 315                # BTN_START

# Appuyer sur START consomme le credit : le compteur retombe a zero alors
# qu'on est en train de jouer. C'est le silence du panneau qui dit qu'une
# partie est finie, pas le compteur. Sans appui pendant ce delai, on
# considere que la borne est revenue en attract et on rappelle qu'il faut
# une piece.
INACTIVITE = 45.0

# On n'appelle pas le joueur 2 dans la seconde ou la partie demarre : la
# derniere lecture du credit date d'un tiers de seconde et annonce encore
# l'ancienne valeur. Sans ce delai, son bouton clignote une seconde pour rien.
DELAI_J2 = 2.5

# Un appui sur le start du joueur 2 suivi d'un credit consomme prouve que le
# jeu accepte deux joueurs ; sans consommation, il l'a refuse. C'est ainsi
# qu'on apprend le vrai nombre de joueurs, sans croire le scrapeur.
VERDICT_J2 = 2.0

PLEIN = 255                     # brightness au repos, valeur posee par le driver
PERIODE = 0.5                   # demi-periode du clignotement
SONDAGE = 0.3                   # relecture des credits pendant une partie
BOUCLE = 0.1                    # granularite de la boucle principale

# Une photo trop vieille rend la comparaison bruyante : entre deux pieces, le
# jeu a fait bouger des centaines d'octets. On en reprend une regulierement
# tant qu'on apprend, jamais une fois le jeu connu.
RAFRAICHI = 5.0
MAX_PIECES = 15                 # au-dela, ce jeu est declare recalcitrant
ESSAIS_AVANT_ABANDON = 2        # un echec peut etre passager
ASSEZ = 4                       # on tente la confirmation START sous ce seuil

# RetroArch ne lit sa socket qu'une fois par image : une commande coute une
# frame, quelle que soit sa taille. On lit donc le plus gros possible.
MORCEAUX = (16384, 4096, 1024)

EV = struct.Struct("llHHi")     # struct input_event
EV_KEY = 0x01

SYSTEMES = ("fbneo", "neogeo", "neogeocd", "mame", "naomi", "naomigd",
            "atomiswave", "arcade")


def journal(msg):
    """Trace minimale : sans elle, une panne est parfaitement invisible.

    Une ecriture impossible — partage demonte, disque plein — ne doit jamais
    empecher la borne de fonctionner : on avale l'erreur en silence.
    """
    try:
        if os.path.exists(JOURNAL) and os.path.getsize(JOURNAL) > JOURNAL_MAX:
            os.replace(JOURNAL, JOURNAL + ".1")   # on ne garde qu'une archive
        with open(JOURNAL, "a") as fh:
            fh.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


# --- RetroArch -----------------------------------------------------------

def ra(commande, timeout=RA_TIMEOUT):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(commande.encode(), (RA_HOTE, RA_PORT))
        return sock.recv(262144).decode(errors="replace").strip()
    except OSError:
        return None
    finally:
        sock.close()


def jeu_en_cours():
    """Nom du set tel que le core le rapporte, ou None."""
    reponse = ra("GET_STATUS")
    if not reponse or "PLAYING" not in reponse:
        return None
    try:
        return reponse.split(None, 2)[2].split(",")[1].strip()
    except IndexError:
        return None


def core_en_cours():
    reponse = ra("GET_STATUS")
    if not reponse or "PLAYING" not in reponse:
        return ""
    try:
        return reponse.split(None, 2)[2].split(",")[0].strip()
    except IndexError:
        return ""


def lire(adresse, n):
    """n octets de RAM du jeu, ou None si la zone n'est pas lisible."""
    # FBNeo ne publie pas de memory map : READ_CORE_MEMORY repond toujours
    # "no memory map defined". READ_CORE_RAM, lui, lit la RAM systeme a plat.
    reponse = ra("READ_CORE_RAM %x %d" % (adresse, n))
    if not reponse:
        return None
    parties = reponse.split()
    if len(parties) < 3 or parties[2] == "-1":
        return None
    try:
        octets = bytes(int(x, 16) for x in parties[2:])
    except ValueError:
        return None
    return octets if len(octets) == n else None


# --- LED -----------------------------------------------------------------

class Lampe:
    """Un bouton lumineux : deux LED, et la couleur que la carte avait posee.

    On n'ecrit dans multi_intensity qu'au moment de clignoter, et on rend la
    couleur d'origine des qu'on s'arrete. Entre-temps, seule brightness bouge
    — c'est ce qui evite tout conflit avec recalbox_allinone_rgb.sh.
    """

    def __init__(self, nom, chemins, couleur):
        self.nom = nom
        self.chemins = [c for c in chemins if os.path.isdir(c)]
        self.couleur = couleur
        self.origine = {}
        self.active = False
        self.eteinte = False
        self.prochain = 0.0
        if not self.chemins:
            journal("LED %s introuvables : module allinone charge ?" % nom)

    def _ecrire(self, fichier, valeur):
        for chemin in self.chemins:
            try:
                with open(os.path.join(chemin, fichier), "w") as fh:
                    fh.write(valeur)
            except IOError as err:
                journal("%s/%s : %s" % (chemin, fichier, err))

    def _memoriser(self):
        for chemin in self.chemins:
            if chemin in self.origine:
                continue
            try:
                with open(os.path.join(chemin, "multi_intensity")) as fh:
                    self.origine[chemin] = fh.read().strip()
            except IOError:
                pass

    def _lire_couleur(self, chemin):
        try:
            with open(os.path.join(chemin, "multi_intensity")) as fh:
                return fh.read().strip()
        except IOError:
            return None

    @staticmethod
    def _meme_couleur(a, b):
        """Compare deux couleurs ecrites differemment : le driver rend des
        decimales la ou recalbox_allinone_rgb.sh ecrit de l'hexadecimal."""
        if a is None or b is None:
            return False
        try:
            return ([int(x, 0) for x in a.split()] == [int(x, 0) for x in b.split()])
        except ValueError:
            return a.strip() == b.strip()

    def _rendre_couleur(self):
        for chemin, valeur in self.origine.items():
            # recalbox_allinone_rgb.sh repeint les boutons a chaque
            # navigation, et cela peut tomber juste apres notre sortie de
            # jeu. Si la LED n'est plus du rouge que nous avons pose, c'est
            # que la carte est repassee derriere : sa couleur est plus
            # recente que la notre, on la laisse.
            if not self._meme_couleur(self._lire_couleur(chemin), self.couleur):
                continue
            try:
                with open(os.path.join(chemin, "multi_intensity"), "w") as fh:
                    fh.write(valeur)
            except IOError as err:
                journal("%s : couleur non rendue (%s)" % (chemin, err))
        self.origine.clear()

    def clignoter(self, maintenant, periode=PERIODE):
        if not self.active:
            self.active = True
            if self.couleur is not None:
                self._memoriser()
                self._ecrire("multi_intensity", self.couleur)
        if maintenant >= self.prochain:
            self.prochain = maintenant + periode
            self.eteinte = not self.eteinte
            self._ecrire("brightness", "0" if self.eteinte else str(PLEIN))

    def eteindre(self):
        """Noir : ce poste ne sert pas sur ce jeu.

        Sur un jeu a un seul joueur, laisser START et PIECE du joueur 2
        allumes invite a payer pour un poste qui ne jouera pas. On les
        eteint, et repos() les rendra a la sortie du jeu.
        """
        self.active = True
        self.eteinte = True
        self._ecrire("brightness", "0")

    def repos(self):
        """Rend le bouton exactement tel que la carte l'avait laisse."""
        if not self.active:
            return
        self.active = False
        self.eteinte = False
        self._ecrire("brightness", str(PLEIN))
        self._rendre_couleur()


class Panneau:
    """Les huit boutons de jeu d un joueur.

    A l entree d un jeu on n allume que ceux dont il se sert, dans leur
    couleur d origine quand on la connait, et on eteint les autres. A la
    sortie, tout est rendu tel que la carte l avait laisse.
    """

    def __init__(self, joueur):
        self.joueur = joueur
        self.boutons = []
        for paire in LEDS_JEU.get(joueur, []):
            chemins = [c for c in paire if os.path.isdir(c)]
            self.boutons.append(chemins)
        self.origine = {}          # chemin -> couleur posee par la carte
        self.actif = False
        presents = sum(1 for b in self.boutons if b)
        if not presents:
            journal("boutons du joueur %d introuvables" % joueur)

    def _ecrire(self, chemin, fichier, valeur):
        try:
            with open(os.path.join(chemin, fichier), "w") as fh:
                fh.write(valeur)
        except IOError as err:
            journal("%s/%s : %s" % (chemin, fichier, err))

    def _memoriser(self, chemin):
        if chemin in self.origine:
            return
        try:
            with open(os.path.join(chemin, "multi_intensity")) as fh:
                self.origine[chemin] = fh.read().strip()
        except IOError:
            pass

    def appliquer(self, fiche, allume=True):
        """Eclaire le panneau selon la fiche du jeu.

        allume=False eteint tout : c est ce qu on fait au panneau du joueur 2
        quand le jeu est solo.
        """
        nombre = (fiche or {}).get("nombre")
        couleurs = (fiche or {}).get("boutons") or {}
        self.actif = True
        for position, chemins in enumerate(self.boutons):
            if not chemins:
                continue
            numero = ORDRE_BOUTONS[position] if position < len(ORDRE_BOUTONS) else position + 1
            utilise = allume and nombre is not None and numero <= nombre
            for chemin in chemins:
                self._memoriser(chemin)
                if not utilise:
                    self._ecrire(chemin, "brightness", "0")
                    continue
                self._ecrire(chemin, "brightness", str(PLEIN))
                teinte = ((couleurs.get("BUTTON%d" % numero) or {}).get("couleur")
                          or teinte_par_defaut(nombre, numero))
                rvb = TEINTES.get((teinte or "").strip().lower())
                if rvb:
                    self._ecrire(chemin, "multi_intensity", couleur(*rvb))

    def rendre(self):
        """Remet le panneau tel que la carte l avait laisse."""
        if not self.actif:
            return
        self.actif = False
        for chemins in self.boutons:
            for chemin in chemins:
                self._ecrire(chemin, "brightness", str(PLEIN))
                if chemin in self.origine:
                    self._ecrire(chemin, "multi_intensity", self.origine[chemin])
        self.origine.clear()


# Palette « comme les arcades d origine », pour les jeux dont la base ne
# connait pas les couleurs (1522 sur 1735). Elle n est pas inventee : c est,
# pour chaque nombre de boutons, la palette la plus frequente parmi les 213
# jeux dont arcade-database publie les vraies couleurs d epoque.
#   4 boutons : Rouge Jaune Vert Bleu — le Neo Geo MVS, 8 jeux sur 16
#   6 boutons : Bleu Jaune Rouge x2 — les jeux de combat Capcom, deux rangees
#   3 boutons : egalite Capcom (bleu) / Sega (rouge) — bleu retenu
PALETTE_DEFAUT = {
    1: ["red"],
    2: ["red", "blue"],
    3: ["blue", "blue", "blue"],
    4: ["red", "yellow", "green", "blue"],
    5: ["blue", "yellow", "red", "blue", "yellow"],
    6: ["blue", "yellow", "red", "blue", "yellow", "red"],
}


def teinte_par_defaut(nombre, numero):
    palette = PALETTE_DEFAUT.get(nombre) or PALETTE_DEFAUT[6]
    return palette[numero - 1] if numero - 1 < len(palette) else "white"


def joueurs_simultanes(fiche_boutons):
    """Le second panneau doit-il s allumer ?

    La base des boutons distingue "2P sim" de "2P alt" : simultane ou a tour
    de role. Sur un jeu en alterne, un seul joueur agit a la fois — allumer
    les deux panneaux donnerait a croire qu on peut jouer ensemble.
    """
    mode = ((fiche_boutons or {}).get("mode") or "").lower()
    if "alt" in mode:
        return False
    if "sim" in mode:
        return True
    return None            # pas d avis : on s en remet au constat sur la borne


def charger_boutons():
    """La base des boutons. Absente : on n eclaire simplement rien."""
    try:
        with open(BASE_BOUTONS) as fh:
            return json.load(fh).get("jeux", {})
    except (IOError, OSError):
        return {}
    except ValueError as err:
        journal("base des boutons illisible : %s" % err)
        return {}


# --- Manettes ------------------------------------------------------------

def ouvrir_pads():
    """Les pads AllInOne, par leur nom : les numeros d'event bougent."""
    fds = {}
    for base in sorted(glob.glob("/sys/class/input/event*")):
        try:
            with open(os.path.join(base, "device", "name")) as fh:
                nom = fh.read().strip()
        except OSError:
            continue
        if not nom.startswith("AllInOne"):
            continue
        chemin = "/dev/input/" + os.path.basename(base)
        try:
            fds[os.open(chemin, os.O_RDONLY | os.O_NONBLOCK)] = nom
        except OSError as err:
            journal("%s illisible : %s" % (chemin, err))
    if not fds:
        journal("aucun pad AllInOne : pas d'apprentissage possible")
    return fds


def appuis(fd):
    """Codes des touches enfoncees, lus sans bloquer."""
    codes = []
    try:
        donnees = os.read(fd, EV.size * 64)
    except OSError:
        return codes
    entiers = len(donnees) // EV.size * EV.size
    for _, _, typ, code, val in EV.iter_unpack(donnees[:entiers]):
        if typ == EV_KEY and val == 1:      # appui, pas relachement
            codes.append(code)
    return codes


# --- Frontend et base ----------------------------------------------------

def jeu_multijoueur(base, systeme, nom):
    """Le jeu accepte-t-il un deuxieme joueur ?

    C'est la seule chose observable : on ne compte pas les joueurs, on
    constate si le joueur 2 a pu rejoindre. Un jeu a quatre joueurs est donc
    note comme un jeu a deux — la borne n'a de toute facon que deux panneaux.

    Ce constat prime sur le scrapeur, dont la metadonnee est souvent fausse.
    """
    fiche = (base.get("jeux") or {}).get(cle(systeme, nom)) or {}
    connu = (fiche.get("joueurs") or {}).get("joueur2_accepte")
    if connu is not None:
        return connu
    nombres = [int(n) for n in re.findall(r"\d+", champ_etat("Players"))]
    return bool(nombres) and max(nombres) >= 2


def noter_joueurs(base, systeme, nom, accepte):
    """Retient ce qu'on vient de constater, sans toucher au reste de la fiche."""
    fiche = base.setdefault("jeux", {}).setdefault(cle(systeme, nom), {})
    if (fiche.get("joueurs") or {}).get("joueur2_accepte") == accepte:
        return
    fiche["joueurs"] = {
        "joueur2_accepte": accepte,
        "constate": ("le joueur 2 a appuye sur START et un credit a ete "
                     "consomme" if accepte else
                     "le joueur 2 a appuye sur START sans qu'aucun credit "
                     "soit consomme"),
        "source": "borne",              # constate, pas lu chez le scrapeur
        "constate_le": time.strftime("%Y-%m-%d"),
    }
    ecrire_base(base)
    journal("%s : joueur 2 %s" % (nom, "accepte" if accepte else "refuse"))


def champ_etat(cle):
    try:
        with open(STATE_FILE, "r", errors="replace") as fh:
            for ligne in fh:
                if ligne.startswith(cle + "="):
                    return ligne.partition("=")[2].strip()
    except (IOError, OSError):
        pass
    return ""


def base_neuve():
    """Squelette documente : le fichier doit se comprendre sans ce script."""
    return {
        "format": "recalbox-arcade-credits",
        "version": SCHEMA,
        "description": (
            "Adresse RAM du compteur de credits de chaque jeu arcade, relevee "
            "sur la borne. Se lit par l'interface reseau de RetroArch : "
            "READ_CORE_RAM <adresse> 1 en UDP sur le port 55355. "
            "READ_CORE_MEMORY ne fonctionne pas avec FBNeo, qui ne publie "
            "aucune memory map."),
        "borne": {
            "carte": "AllInOne — digipcb.tech",
            "boutons": {"piece": CODE_PIECE, "start": CODE_START},
            "pads": ["AllInOneP1", "AllInOneP2"],
        },
        "jeux": {},
        "difficiles": {},
        "cles_lisez_moi": ("Les fiches sont indexees \"systeme/jeu\" : le meme "
                           "set peut tourner sous plusieurs coeurs, qui ne "
                           "rangent pas leur RAM de la meme facon. Les pistes, "
                           "elles, sont indexees par le seul nom du set : une "
                           "adresse de cheat vise le processeur emule et ne "
                           "depend pas du coeur."),
    }


def cle(systeme, jeu):
    """Un jeu est identifie par son systeme ET son nom.

    Le meme set existe sous plusieurs systemes — fbneo et mame par exemple —
    et chaque coeur range sa RAM a sa facon. Indexer sur le seul nom ferait
    silencieusement ecraser une fiche par l'autre, et le clignotement
    deviendrait faux sans que rien ne le signale.
    """
    return "%s/%s" % (systeme or "?", jeu)


def fiche_de(base, systeme, jeu, core=None):
    """La fiche d'un jeu, si elle correspond bien au coeur qui tourne."""
    jeux = base.get("jeux") or {}
    # Une base ancienne peut avoir garde une cle nue, faute de systeme connu
    # au moment de la conversion : on l'accepte encore.
    fiche = jeux.get(cle(systeme, jeu)) or jeux.get(jeu)
    if not fiche:
        return None
    # Un jeu relance sous un autre coeur n'a plus la meme disposition
    # memoire : mieux vaut reapprendre que clignoter faux.
    if core and fiche.get("core") and fiche["core"] != core:
        journal("%s : releve sous %s, or %s tourne — je reapprends"
                % (jeu, fiche["core"], core))
        return None
    return fiche


def convertir(base):
    """Amene une base d'un ancien format au format courant."""
    if base.get("version") == SCHEMA:
        return base
    neuve = base_neuve()
    neuve["pistes"] = base.get("pistes", {})
    neuve["sources"] = base.get("sources", {})
    if "pistes_lisez_moi" in base:
        neuve["pistes_lisez_moi"] = base["pistes_lisez_moi"]
    # Les difficultes suivent la meme cle que les fiches.
    for nom, dur in (base.get("difficiles") or {}).items():
        neuve["difficiles"][cle(dur.get("systeme"), nom) if "/" not in nom
                            else nom] = dur
    for nom, ancienne in (base.get("jeux") or {}).items():
        if "credits" in ancienne:                  # deja au bon format interne
            ancienne.setdefault("jeu", nom.split("/")[-1])
            systeme = ancienne.get("systeme")
            neuve["jeux"][nom if "/" in nom or not systeme
                          else cle(systeme, nom)] = ancienne
            continue
        fiche = {}
        if "adresse" in ancienne:
            fiche["credits"] = {
                "adresse": ancienne["adresse"],
                "adresse_hex": ancienne.get("adresse_hex",
                                            "0x%04X" % ancienne["adresse"]),
                "octets": 1,
                "miroirs": ancienne.get("miroirs", []),
                "verifie_insertion": ancienne.get("verifie_insertion"),
                "verifie_consommation": ancienne.get("verifie_consommation"),
                "pieces_observees": ancienne.get("pieces_observees"),
            }
        if ancienne.get("core"):
            fiche["core"] = ancienne["core"]
        if ancienne.get("taille_ram"):
            fiche["ram"] = {"taille": ancienne["taille_ram"],
                            "commande": "READ_CORE_RAM"}
        if "joueurs" in ancienne:
            fiche["joueurs"] = {
                "joueur2_accepte": ancienne["joueurs"] >= 2,
                "source": "borne",
                "constate_le": ancienne.get("joueurs_constate_le")}
        fiche["releve"] = {"le": ancienne.get("appris_le") or ancienne.get("releve_le"),
                           "methode": "apprentissage", "par": OUTIL}
        fiche.setdefault("jeu", nom.split("/")[-1])
        systeme = ancienne.get("systeme") or fiche.get("systeme")
        neuve["jeux"][nom if "/" in nom or not systeme
                      else cle(systeme, nom)] = fiche
    journal("base convertie au format %d (%d jeu(x))" % (SCHEMA, len(neuve["jeux"])))
    return neuve


def charger_base():
    try:
        with open(BASE) as fh:
            base = json.load(fh)
    except (IOError, OSError):
        return base_neuve()
    except ValueError as err:
        journal("base illisible (%s) : je n'y touche pas" % err)
        return None                      # None = on n'ecrira rien
    if base.get("version") != SCHEMA:
        base = convertir(base)
        ecrire_base(base)
    return base


def adresse_de(fiche):
    """L'adresse du compteur dans une fiche, ou None."""
    return ((fiche or {}).get("credits") or {}).get("adresse")


def ecrire_base(base):
    if base is None:
        return
    # Un nom de fichier temporaire propre a ce processus. Deux ecrivains qui
    # partagent le meme ".tmp" melangent leurs contenus et laissent une base
    # tronquee — c'est arrive, et ca coute toutes les fiches relevees.
    provisoire = "%s.%d.tmp" % (BASE, os.getpid())
    try:
        with open(provisoire, "w") as fh:
            json.dump(base, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(provisoire, BASE)     # remplacement atomique
    except (IOError, OSError) as err:
        journal("ecriture base impossible : %s" % err)


# --- Apprentissage -------------------------------------------------------

class Apprenti:
    """Cherche l'adresse du compteur du jeu en cours, s'il est inconnu."""

    def __init__(self, base):
        self.base = base
        self.oublier()

    def oublier(self):
        self.jeu = None
        self.systeme = None
        self.core = None
        self.piste = None            # adresse suggeree par le pack de cheats
        self.taille = None
        self.photo = None
        self.derniere_photo = 0.0
        self.candidats = None            # None = aucune piece encore vue
        self.valeurs = {}
        self.baissiers = set()
        self.pieces = 0

    # -- acces a la RAM

    def mesurer(self):
        """Taille lisible, par dichotomie. Une fois par jeu."""
        if lire(0, 1) is None:
            return 0
        bas, haut = 0, 1
        while haut < (1 << 24) and lire(haut, 1) is not None:
            bas, haut = haut, haut << 1
        while haut - bas > 1:
            milieu = (bas + haut) // 2
            if lire(milieu, 1) is not None:
                bas = milieu
            else:
                haut = milieu
        return bas + 1

    def prendre_photo(self):
        """Copie complete de la RAM : 4 commandes pour 64 Ko."""
        if self.taille is None:
            self.taille = self.mesurer()
            journal("%s : %d octets lisibles" % (self.jeu, self.taille))
        if not self.taille:
            return None
        for morceau in MORCEAUX:          # repli si un gros bloc passe mal
            out = bytearray()
            a = 0
            while a < self.taille:
                bloc = lire(a, min(morceau, self.taille - a))
                if bloc is None:
                    break
                out += bloc
                a += len(bloc)
            if a >= self.taille:
                return bytes(out)
        return None

    # -- evenements

    def nouveau_jeu(self, nom, systeme, core):
        self.oublier()
        self.jeu = nom
        self.systeme = systeme
        self.core = core
        # Les pistes sont indexees par le seul nom du set : une adresse de
        # cheat vise le processeur emule, pas un coeur en particulier.
        piste = (self.base.get("pistes") or {}).get(nom)
        if piste:
            try:
                self.piste = int(piste["cheat"], 16)
            except (KeyError, ValueError):
                self.piste = None
            if self.piste is not None:
                journal("%s : piste %s (%s)"
                        % (nom, piste["cheat"], piste.get("source", "?")))

    def candidats_de_la_piste(self):
        """Les adresses plausibles derriere une adresse de cheat.

        Le cheat vise l'espace du processeur emule, ou la RAM commence a une
        adresse haute propre au materiel : 0xFF0000 sur un 68000 CPS, 0xE000
        sur les cartes Z80. READ_CORE_RAM lit a plat depuis zero. Ce decalage
        est toujours rond, donc masquer les bits bas suffit a le retrouver.

            0xFF0D59 -> 0x0D59  (1941, 68000)
            0x00E312 -> 0x0312  (1943, Z80)

        Plus le XOR 1 des jeux gros-boutistes, dont FBNeo range la RAM octets
        inverses. La premiere piece tranche : un seul candidat monte.
        """
        if self.taille is None:
            self.taille = self.mesurer()
        if not self.taille:
            return set()
        candidats = set()
        for bits in (12, 13, 14, 15, 16, 17, 20):
            bas = self.piste & ((1 << bits) - 1)
            if bas < self.taille:
                candidats.add(bas)
                candidats.add(bas ^ 1)
        return {a for a in candidats if a < self.taille}

    @property
    def cle(self):
        return cle(self.systeme, self.jeu)

    def a_apprendre(self):
        return (self.jeu is not None
                and adresse_de(fiche_de(self.base, self.systeme, self.jeu,
                                        self.core)) is None
                and ((self.base.get("difficiles") or {}).get(self.cle) or {}
                     ).get("essais", 0) < ESSAIS_AVANT_ABANDON
                and self.pieces < MAX_PIECES)

    def rafraichir(self):
        """Garde de quoi comparer quand la piece arrivera.

        Avec une piste, deux octets suffisent et coutent deux commandes. Sans
        piste, il faut toute la RAM : quatre commandes et 64 Ko en memoire.
        """
        if not self.a_apprendre():
            return
        if time.time() - self.derniere_photo < RAFRAICHI:
            return
        if self.piste is not None:
            valeurs = {}
            for a in self.candidats_de_la_piste():
                octet = lire(a, 1)
                if octet is None:
                    return           # jeu pas encore pret : on reessaiera
                valeurs[a] = octet[0]
            self.valeurs = valeurs
            self.derniere_photo = time.time()
            return
        photo = self.prendre_photo()
        if photo is not None:
            self.photo = photo
            self.derniere_photo = time.time()

    def piece(self):
        """Une piece vient d'entrer : ce qu'on avait avant est notre reference."""
        if not self.a_apprendre():
            return None
        if self.piste is not None:
            return self.piece_sur_piste()
        avant = self.photo
        apres = self.prendre_photo()
        if apres is None:
            return None
        self.photo = apres
        self.derniere_photo = time.time()
        if avant is None or len(avant) != len(apres):
            return None                   # premiere photo : rien a comparer

        self.pieces += 1
        # Le masque 0xFF gere le repli a zero ; la borne 0x99 ecarte les
        # octets qui comptent tout autre chose (timers, animations).
        trouves = {a for a in range(len(apres))
                   if apres[a] == (avant[a] + 1) & 0xFF and avant[a] < 0x99}
        self.candidats = (trouves if self.candidats is None
                          else self.candidats & trouves)
        self.valeurs = {a: apres[a] for a in self.candidats}
        journal("%s : piece %d -> %d candidat(s)"
                % (self.jeu, self.pieces, len(self.candidats)))

        if not self.candidats:
            journal("%s : plus aucun candidat (BCD, deux octets, ou hors "
                    "zone) — j'abandonne" % self.jeu)
            self.abandonner("aucun candidat")
            return None
        return self.conclure_si_sur()

    def piece_sur_piste(self):
        """Verifie les deux candidats issus du cheat, sans photographier."""
        avant = dict(self.valeurs)
        montes = set()
        for a in self.candidats_de_la_piste():
            octet = lire(a, 1)
            if octet is None:
                return None
            if a in avant and octet[0] == (avant[a] + 1) & 0xFF:
                montes.add(a)
            self.valeurs[a] = octet[0]
        if not avant:
            return None              # premiere lecture : rien a comparer
        self.pieces += 1
        if montes:
            self.candidats = montes
            journal("%s : piste confirmee, %s"
                    % (self.jeu, " ".join("0x%04X" % a for a in sorted(montes))))
            return self.conclure()
        if self.pieces >= 2:
            # Deux pieces sans reaction : la piste est fausse pour ce jeu, on
            # repart sur la recherche complete plutot que d'y renoncer.
            journal("%s : piste sans effet, retour a la recherche complete"
                    % self.jeu)
            self.piste = None
            self.pieces = 0
            self.valeurs = {}
            self.derniere_photo = 0.0
        return None

    def start(self):
        """START consomme un credit : le solde baisse, un total de pieces non."""
        if not self.a_apprendre() or not self.candidats:
            return None
        if len(self.candidats) > ASSEZ:
            return None
        for a in sorted(self.candidats):
            octet = lire(a, 1)
            if octet is None:
                continue
            if a in self.valeurs and octet[0] < self.valeurs[a]:
                self.baissiers.add(a)
            self.valeurs[a] = octet[0]
        journal("%s : start -> %d candidat(s) confirme(s)"
                % (self.jeu, len(self.candidats & self.baissiers)))
        return self.conclure_si_sur()

    def conclure_si_sur(self):
        """Conclut des que tous les candidats restants sont confirmes.

        Un jeu range souvent son compteur a plusieurs endroits a la fois :
        les miroirs montent et descendent ensemble, l'intersection ne
        tombera donc jamais a un seul candidat. Attendre ce candidat unique
        reviendrait a ne jamais rien apprendre sur ces jeux-la — on garde
        la plus petite adresse et on note les autres comme miroirs.
        """
        surs = self.candidats & self.baissiers
        if not surs or len(surs) > ASSEZ:
            return None
        self.candidats = surs
        return self.conclure()

    # -- fin

    def conclure(self):
        retenues = sorted(self.candidats)
        adresse = retenues[0]
        fiche = self.base.setdefault("jeux", {}).setdefault(self.cle, {})
        fiche.update({
            "jeu": self.jeu,
            "nom": champ_etat("Game") or self.jeu,
            "systeme": self.systeme,
            "core": self.core or core_en_cours(),
            "ram": {"taille": self.taille or 0, "commande": "READ_CORE_RAM"},
            "credits": {
                "adresse": adresse,
                "adresse_hex": "0x%04X" % adresse,
                "octets": 1,
                # Un jeu range souvent son compteur a plusieurs endroits :
                # les autres adresses confirmees sont notees comme miroirs.
                "miroirs": ["0x%04X" % a for a in retenues[1:]],
                "verifie_insertion": True,
                "verifie_consommation": adresse in self.baissiers,
                "pieces_observees": self.pieces,
            },
            "releve": {"le": time.strftime("%Y-%m-%d"),
                       "methode": ("piste confirmee" if self.piste is not None
                                   else "apprentissage"),
                       "par": OUTIL},
        })
        ecrire_base(self.base)
        journal("%s : APPRIS 0x%04X%s apres %d piece(s)"
                % (self.jeu, adresse,
                   " (+%d miroir(s))" % len(retenues[1:]) if len(retenues) > 1 else "",
                   self.pieces))
        self.photo = None                 # plus besoin de garder 64 Ko
        return adresse

    def abandonner(self, raison):
        # Un echec peut etre passager. On compte les tentatives plutot que de
        # condamner un jeu sur une seule partie malchanceuse.
        durs = self.base.setdefault("difficiles", {})
        ancien = durs.get(self.cle) or {}
        durs[self.cle] = {
            "jeu": self.jeu,
            "nom": champ_etat("Game") or self.jeu,
            "systeme": self.systeme,
            "core": self.core or core_en_cours(),
            "raison": raison,
            "essais": ancien.get("essais", 0) + 1,
            "pieces_observees": self.pieces,
            "vu_le": time.strftime("%Y-%m-%d"),
        }
        ecrire_base(self.base)
        self.photo = None


# --- Boucle principale ---------------------------------------------------

def main():
    base = charger_base()
    if base is None:                       # base corrompue : on ne clignote
        base = {"version": 1, "jeux": {}}   # pas au hasard, et on n'ecrit rien
    piece = Lampe("piece", LEDS_PIECE, COULEUR_PIECE)
    start = Lampe("start", LEDS_START, COULEUR_START)
    start2 = Lampe("start J2", LEDS_START_P2, COULEUR_START)
    piece2 = Lampe("piece J2", LEDS_PIECE_P2, COULEUR_PIECE)
    deuxieme = True                # tant qu on ne sait pas, on n eteint rien
    panneaux = {1: Panneau(1), 2: Panneau(2)}
    boutons = charger_boutons()
    pads = ouvrir_pads()
    apprenti = Apprenti(base)

    journal("demarrage — %d jeu(x) connu(s), %d avec boutons, %d+%d+%d LED, "
            "%d pad(s)"
            % (len(base.get("jeux", {})), len(boutons), len(piece.chemins),
               len(start.chemins), len(start2.chemins), len(pads)))

    def rendre(*_):
        """Les boutons doivent repartir allumes et de leur couleur."""
        piece.repos()
        start.repos()
        start2.repos()
        for p in panneaux.values():
            p.rendre()
        sys.exit(0)

    signal.signal(signal.SIGTERM, rendre)

    en_jeu = False
    resolu = False
    adresse = None
    credits = None
    lance = False              # START a ete presse avec du credit : on joue
    multi = False              # le jeu accepte au moins deux joueurs
    p2_engage = False          # le joueur 2 a pris sa place
    depuis_lance = 0.0         # quand la partie a demarre
    essai_j2 = None            # (instant, credits) d'un appui start du J2
    derniere_activite = 0.0
    dernier_mtime = None
    prochain_sondage = 0.0
    fds = list(pads)

    try:
        while True:
            # Un select plutot qu'un sleep : les boutons sont pris tout de
            # suite, et la boucle ne tourne pas a vide entre deux appuis.
            if fds:
                prets, _, _ = select.select(fds, [], [], BOUCLE)
            else:
                prets = []
                time.sleep(BOUCLE)
            maintenant = time.time()

            for fd in prets:
                for code in appuis(fd):
                    if not en_jeu:
                        continue
                    derniere_activite = maintenant
                    if code not in (CODE_PIECE, CODE_START):
                        continue          # une touche de jeu : juste un signe de vie
                    if code == CODE_START and pads[fd].endswith("P2"):
                        p2_engage = True    # il a rejoint, on cesse de l'appeler
                        if credits:
                            # On regarde si le jeu accepte vraiment : s'il
                            # consomme le credit, il est bien a deux.
                            essai_j2 = (maintenant, credits)
                    if code == CODE_START and credits and not lance:
                        # La partie demarre : plus rien ne clignote, comme
                        # sur une vraie borne. Le cas ou le compteur n'est
                        # pas encore connu est rattrape plus bas, en voyant
                        # le credit se faire consommer.
                        lance, depuis_lance = True, maintenant
                    trouvee = (apprenti.piece() if code == CODE_PIECE
                               else apprenti.start())
                    if trouvee is not None:
                        adresse = trouvee

            # Entree et sortie de partie, vues par le frontend.
            try:
                mtime = os.path.getmtime(STATE_FILE)
            except OSError:
                mtime = None
            if mtime is not None and mtime != dernier_mtime:
                dernier_mtime = mtime
                action = champ_etat("Action").lower()
                if action in ("rungame", "rundemo"):
                    en_jeu = champ_etat("SystemId").lower() in SYSTEMES
                    resolu, adresse, credits, lance = False, None, None, False
                    p2_engage, essai_j2 = False, None
                    derniere_activite = maintenant
                    apprenti.oublier()
                elif action in ("endgame", "enddemo", "stop", "shutdown", "reboot"):
                    en_jeu = False
                    resolu, adresse, credits, lance = False, None, None, False
                    for panneau in panneaux.values():
                        panneau.rendre()
                    apprenti.oublier()

            # Nom du jeu, cherche une seule fois par partie.
            if en_jeu and not resolu and maintenant >= prochain_sondage:
                prochain_sondage = maintenant + SONDAGE
                nom = jeu_en_cours()
                if nom is not None:
                    resolu = True
                    systeme = champ_etat("SystemId").lower()
                    core = core_en_cours()
                    apprenti.nouveau_jeu(nom, systeme, core)
                    multi = jeu_multijoueur(base, systeme, nom)
                    adresse = adresse_de(fiche_de(base, systeme, nom, core))
                    journal("%s/%s : %s" % (systeme, nom,
                                            "0x%04X" % adresse if adresse
                                            else "inconnu, j'apprends"))
                    # Le panneau : seuls les boutons utiles, dans leurs
                    # couleurs. Le joueur 2 reste noir sur un jeu solo.
                    fiche_boutons = boutons.get(nom)
                    if fiche_boutons:
                        # Le mode du jeu prime : en alterne, le panneau du
                        # joueur 2 reste noir meme si le jeu est "a deux".
                        simultane = joueurs_simultanes(fiche_boutons)
                        deuxieme = multi if simultane is None else simultane
                        panneaux[1].appliquer(fiche_boutons)
                        panneaux[2].appliquer(fiche_boutons, allume=deuxieme)
                        journal("%s : %s bouton(s), %s%s" % (
                            nom, fiche_boutons.get("nombre"),
                            fiche_boutons.get("mode") or "mode inconnu",
                            "" if deuxieme else " — joueur 2 eteint"))

            # Jeu connu : un octet, trois fois par seconde.
            elif en_jeu and adresse is not None and maintenant >= prochain_sondage:
                prochain_sondage = maintenant + SONDAGE
                octet = lire(adresse, 1)
                nouveau = octet[0] if octet else None
                # Un credit qui descend, c'est quelqu'un qui vient de lancer
                # une partie ou de rejoindre : rien d'autre ne le consomme.
                # C'est le signal le plus sur dont on dispose.
                if (nouveau is not None and credits is not None
                        and nouveau < credits):
                    if not lance:
                        lance, depuis_lance = True, maintenant

                # Verdict sur le joueur 2 : le credit a-t-il ete consomme
                # apres son appui ?
                if essai_j2 is not None and nouveau is not None:
                    instant, avant = essai_j2
                    if nouveau < avant:
                        multi = True
                        noter_joueurs(base, apprenti.systeme, apprenti.jeu, True)
                        essai_j2 = None
                    elif maintenant - instant > VERDICT_J2:
                        multi = False        # le jeu a refuse le joueur 2
                        noter_joueurs(base, apprenti.systeme, apprenti.jeu, False)
                        essai_j2 = None
                credits = nouveau

            # Jeu inconnu : on entretient la photo de reference.
            elif en_jeu and adresse is None:
                apprenti.rafraichir()

            # Les trois etats d'une borne d'arcade. Une lecture ratee
            # (credits vaut None) laisse les boutons tranquilles plutot que
            # de raconter n'importe quoi.
            # Le panneau silencieux depuis un moment : la partie est finie,
            # la borne peut recommencer a reclamer une piece.
            if lance and maintenant - derniere_activite > INACTIVITE:
                lance, p2_engage = False, False

            if not en_jeu or credits is None or lance:
                piece.repos()                # hors jeu, ou en train de jouer :
                start.repos()                # rien ne clignote
            elif credits == 0:
                start.repos()
                piece.clignoter(maintenant)  # "mets une piece"
            else:
                piece.repos()
                start.clignoter(maintenant)  # "appuie sur start"

            # Joueur 2 : sur un jeu multi, tant qu'il reste du credit et
            # qu'il n'a pas pris sa place, son bouton start l'appelle.
            if en_jeu and not deuxieme:
                # Poste 2 inutile sur ce jeu : START et PIECE noirs, comme
                # ses boutons de jeu.
                start2.eteindre()
                piece2.eteindre()
            elif (en_jeu and lance and multi and not p2_engage and credits
                    and maintenant - depuis_lance > DELAI_J2):
                piece2.repos()
                start2.clignoter(maintenant)
            else:
                start2.repos()
                piece2.repos()
    finally:
        piece.repos()
        start.repos()
        start2.repos()
        piece2.repos()
        for panneau in panneaux.values():
            panneau.rendre()


if __name__ == "__main__":
    main()
