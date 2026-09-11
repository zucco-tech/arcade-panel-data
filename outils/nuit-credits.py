#!/usr/bin/env python3
"""
Releve l'adresse du compteur de credits de toute une logitheque, la nuit.

    python3 nuit-credits.py --essai                 # montre ce qu'il ferait
    python3 nuit-credits.py --pistes-seulement      # les jeux deja documentes
    python3 nuit-credits.py --limite 50             # une premiere fournee

A lancer SUR LA BORNE : il a besoin de /dev/uinput, qui est local.

Il enchaine, pour chaque jeu : EmulationStation le lance (commande reseau
START sur le port 1337), un clavier virtuel insere des pieces, on compare la
RAM avant et apres, puis RetroArch rend la main au menu (commande QUIT). Le
jeu suivant.

Prudence, parce que c'est une borne et pas un serveur :

  * il refuse de demarrer si une partie est deja en cours ;
  * il n'appuie JAMAIS sur une touche hors d'un jeu — sinon Entree validerait
    dans le menu et lancerait n'importe quoi ;
  * le clavier virtuel est detruit a la sortie, y compris sur Ctrl-C, sur un
    signal, ou sur une erreur imprevue ;
  * il n'ecrit jamais dans la RAM d'un jeu, seulement en lecture ;
  * la base est sauvee apres chaque jeu : une coupure ne perd rien et la
    reprise saute ce qui est deja fait ;
  * la presence du fichier d'arret (--arret) le fait s'arreter proprement ;
  * une serie d'echecs consecutifs l'arrete de lui-meme, plutot que de
    labourer la borne toute la nuit pour rien.

Aucune dependance : uniquement la bibliotheque standard.
"""

import argparse
import glob
import subprocess
import json
import os
import signal
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clavier_virtuel import ClavierVirtuel      # noqa: E402

PORT_RA = 55355          # commandes RetroArch
PORT_ES = 1337           # commandes EmulationStation

# Sur une machine dediee il n y a pas de frontend : le releveur lance
# RetroArch lui-meme. Deux details appris a la dure sur Ubuntu :
#
#   * sans bus D-Bus, RetroArch avorte des qu il cherche GameMode. Il faut
#     l envelopper dans dbus-run-session.
#   * la version 1.18 livree par Ubuntu n expose pas la RAM a READ_CORE_RAM.
#     Il faut la 1.22.2 officielle.
RETROARCH = "/opt/retroarch.AppImage"
DOSSIER_COEURS = "/opt/coeurs"
# Le nom que RetroArch annonce pour chaque coeur, pour savoir avant de
# lancer si un jeu a deja ete mesure. Il est reverifie a l execution.
COEURS_NOMMES = {
    "fbneo": "FinalBurn Neo", "fba": "FinalBurn Neo",
    "neogeo": "FinalBurn Neo", "neogeocd": "FinalBurn Neo",
    "naomi": "Flycast", "naomigd": "Flycast", "naomi2": "Flycast",
    "atomiswave": "Flycast",
    "mame0278": "MAME", "mame": "MAME",
}

COEURS = {
    "fbneo": "fbneo_libretro.so",
    "fba": "fbneo_libretro.so",
    "neogeo": "fbneo_libretro.so",
    "neogeocd": "fbneo_libretro.so",
    "naomi": "flycast_libretro.so",
    "naomigd": "flycast_libretro.so",
    "naomi2": "flycast_libretro.so",
    "atomiswave": "flycast_libretro.so",
    "mame0278": "mame_libretro.so",
    "mame": "mame_libretro.so",
}
MORCEAU = 16384          # maximum accepte par RetroArch en une commande

ATTENTE_LANCEMENT = 90.0  # un Neo Geo met du temps a demarrer
ATTENTE_RAM = 25.0
# Un jeu n'encaisse pas de piece tant qu'il n'a pas fini de demarrer :
# verification des ROM sur CPS2, ecran de garde, logo. Un delai fixe ne peut
# pas convenir a la fois a un jeu de 1984 et a un CPS2. On attend plutot que
# la RAM s'anime, signe que le jeu tourne pour de bon.
ATTENTE_VIVANT = 60.0
REMUE_MINIMUM = 16        # octets qui changent en une seconde
REPOS_APRES_VIVANT = 3.0
ATTENTE_ARRET = 25.0
PIECES_MAX = 4
ASSEZ = 4
# Sans confirmation par le START, on n'accepte qu'une preuve etroite : une ou
# deux adresses, pas davantage. Ecrire une fiche sur six candidats dont aucun
# n'a ete confirme, c'est inventer une reponse.
SANS_CONFIRMATION_MAX = 2
ECHECS_MAX = 8            # au-dela, quelque chose ne va pas : on s'arrete

# Un echec peut etre passager : le jeu n'avait pas fini de demarrer et la
# piece n'a pas ete encaissee. On ne condamne un jeu qu'apres deux tentatives,
# sauf quand la cause est sans appel (le core n'expose pas sa RAM).
ESSAIS_AVANT_ABANDON = 2
SANS_APPEL = ("RAM non lisible",)


class Interruption(Exception):
    """Demande d'arret propre."""


class Borne:
    def __init__(self, hote, rapide_voulue=False, direct=False):
        self.hote = hote
        self.direct = direct         # on lance RetroArch soi-meme
        self.processus = None
        self.taille = None
        self.rapide = False              # etat courant de l'avance rapide
        self.rapide_voulue = rapide_voulue

    def _udp(self, port, texte, attendre_reponse=True, timeout=0.6):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            sock.sendto(texte.encode(), (self.hote, port))
            if not attendre_reponse:
                return ""
            return sock.recv(65536).decode(errors="replace").strip()
        except OSError:
            return None
        finally:
            sock.close()

    # -- RetroArch

    def jeu(self):
        reponse = self._udp(PORT_RA, "GET_STATUS")
        if not reponse or "PLAYING" not in reponse:
            return None
        try:
            champs = reponse.split(None, 2)[2].split(",")
            return champs[1].strip(), champs[0].strip()
        except IndexError:
            return None

    def lire(self, adresse, n):
        reponse = self._udp(PORT_RA, "READ_CORE_RAM %x %d" % (adresse, n))
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

    def quitter(self):
        self._udp(PORT_RA, "QUIT", attendre_reponse=False)
        if self.direct:
            time.sleep(1.0)
            self.arreter_processus()

    def avance_rapide(self, actif):
        """Bascule l'avance rapide de RetroArch.

        RetroArch ne lit sa socket qu'une fois par image : accelerer les
        images accelere aussi les commandes. Sans effet sur une machine deja
        a sa limite (mesure : aucun gain sur le Raspberry), mais x5,8 sur un
        PC. La commande est une bascule, d'ou l'etat suivi ici.
        """
        if actif == self.rapide:
            return
        self._udp(PORT_RA, "FAST_FORWARD", attendre_reponse=False)
        self.rapide = actif
        time.sleep(0.3)

    def mesurer(self):
        if self.lire(0, 1) is None:
            return 0
        bas, haut = 0, 1
        while haut < (1 << 24) and self.lire(haut, 1) is not None:
            bas, haut = haut, haut << 1
        while haut - bas > 1:
            milieu = (bas + haut) // 2
            if self.lire(milieu, 1) is not None:
                bas = milieu
            else:
                haut = milieu
        return bas + 1

    def photo(self):
        if self.taille is None:
            self.taille = self.mesurer()
        if not self.taille:
            return None
        out = bytearray()
        for a in range(0, self.taille, MORCEAU):
            bloc = self.lire(a, min(MORCEAU, self.taille - a))
            if bloc is None:
                return None
            out += bloc
        return bytes(out)

    # -- EmulationStation

    def lancer(self, systeme, chemin_rom):
        """Demarre un jeu, par le frontend ou directement selon le mode."""
        if not self.direct:
            # EmulationStation compare le CHEMIN COMPLET de la rom, pas son
            # nom de fichier : verifie dans FolderData::LookupGame, et
            # constate sur la borne (un nom seul repond "Couldn't find game").
            self._udp(PORT_ES, "START|%s|%s" % (systeme, chemin_rom),
                      attendre_reponse=False)
            return
        coeur = COEURS.get(systeme)
        if coeur is None:
            return
        self.arreter_processus()
        env = dict(os.environ)
        env.update({"HOME": "/root", "XDG_RUNTIME_DIR": "/run/user/0"})
        self.processus = subprocess.Popen(
            ["dbus-run-session", "--", RETROARCH,
             "--config", "/root/.config/retroarch/retroarch.cfg",
             "-L", os.path.join(DOSSIER_COEURS, coeur), chemin_rom],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)

    def arreter_processus(self):
        """Coupe le RetroArch qu on a lance, s il en reste un."""
        if self.processus is None:
            return
        try:
            self.processus.terminate()
            self.processus.wait(timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            try:
                self.processus.kill()
            except OSError:
                pass
        self.processus = None


def attendre_vivant(borne, arret, delai=ATTENTE_VIVANT):
    """Attend que le jeu s'anime vraiment.

    Avant son ecran d'attente, la RAM est quasi figee et la piece tombe dans
    le vide — c'est ce qui faisait echouer les CPS2, longs a demarrer. Deux
    lectures a une seconde d'intervalle suffisent a le voir vivre.
    """
    fin = time.time() + delai
    precedent = None
    while time.time() < fin:
        arret()
        # On regarde TOUTE la RAM : sur certains jeux les premiers kilo-octets
        # restent figes alors que l'action se passe plus loin. Une photo coute
        # quatre commandes, c'est negligeable.
        bloc = borne.photo()
        if bloc is not None and precedent is not None:
            if sum(1 for a, b in zip(bloc, precedent) if a != b) >= REMUE_MINIMUM:
                time.sleep(REPOS_APRES_VIVANT)     # laisser l'ecran s'etablir
                return True
        precedent = bloc
        time.sleep(1.0)
    return False


def patienter(condition, delai, arret, pas=0.5):
    """Attend qu'une condition soit vraie. Vrai si elle l'est devenue."""
    fin = time.time() + delai
    while time.time() < fin:
        arret()
        valeur = condition()
        if valeur:
            return valeur
        time.sleep(pas)
    return None


def base_charger(chemin):
    with open(chemin) as fh:
        return json.load(fh)


def base_ecrire(chemin, base):
    # Un nom de fichier temporaire propre a ce processus. Deux ecrivains qui
    # partagent le meme ".tmp" melangent leurs contenus et laissent une base
    # tronquee — c'est arrive, et ca coute toutes les fiches relevees.
    provisoire = "%s.%d.tmp" % (chemin, os.getpid())
    with open(provisoire, "w") as fh:
        json.dump(base, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
    os.replace(provisoire, chemin)          # remplacement atomique


def normaliser_coeur(nom):
    """Un identifiant court et stable pour un coeur.

    RetroArch annonce le sien en toutes lettres — "FinalBurn Neo",
    "fb_alpha", "MAME 2003-Plus" — et l orthographe varie d une version a
    l autre. On en tire une cle lisible et constante.
    """
    propre = "".join(c if c.isalnum() else "-" for c in (nom or "inconnu").lower())
    while "--" in propre:
        propre = propre.replace("--", "-")
    return propre.strip("-") or "inconnu"


def cle(coeur, jeu):
    """Un jeu est identifie par son COEUR et son nom.

    C est le coeur qui decide de la disposition memoire : le meme set sous
    FinalBurn Neo et sous MAME n a pas la meme adresse de credits. Deux
    mesures faites sous deux coeurs doivent cohabiter, pas s ecraser.
    """
    return "%s/%s" % (normaliser_coeur(coeur), jeu)


def deja_fait(base, coeur, jeu, reessayer=False):
    """Vrai si ce jeu n'a plus rien a nous apprendre, pour ce coeur."""
    fiche = (base.get("jeux") or {}).get(cle(coeur, jeu)) or {}
    if (fiche.get("credits") or {}).get("adresse"):
        return True
    dur = (base.get("difficiles") or {}).get(cle(coeur, jeu))
    if not dur:
        return False
    if dur.get("raison") in SANS_APPEL:
        return True             # inutile d'insister, meme sur demande
    if reessayer:
        return False
    return dur.get("essais", 1) >= ESSAIS_AVANT_ABANDON


def noter_difficulte(base, jeu, systeme, raison, coeur=None):
    """Compte les tentatives : un jeu n'est ecarte qu'apres deux echecs."""
    durs = base.setdefault("difficiles", {})
    ancien = durs.get(cle(coeur, jeu)) or {}
    durs[cle(coeur, jeu)] = {
        "jeu": jeu,
        "systeme": systeme,
        "core": coeur,
        "raison": raison,
        "essais": ancien.get("essais", 0) + 1,
        "vu_le": time.strftime("%Y-%m-%d"),
        "par": "nuit-credits.py",
    }
    return durs[cle(coeur, jeu)]["essais"]


def candidats_piste(piste, taille):
    """Les adresses plausibles derriere une adresse de cheat.

    Le cheat vise l'espace du processeur emule, ou la RAM commence a une
    adresse haute qui depend du materiel : 0xFF0000 sur un 68000 CPS,
    0xE000 sur les cartes Z80 des annees 80. READ_CORE_RAM, lui, lit a plat
    depuis zero. On ne connait pas ce decalage, mais il est toujours rond :
    masquer les bits bas suffit a le retrouver.

        0xFF0D59 -> 0x0D59  (1941, 68000, masque de 16 bits)
        0x00E312 -> 0x0312  (1943, Z80,   masque de 12 bits)

    On y ajoute le XOR 1 des jeux gros-boutistes, dont FBNeo range la RAM
    octets inverses. La premiere piece tranche : un seul candidat monte.
    """
    candidats = set()
    for bits in (12, 13, 14, 15, 16, 17, 20):
        bas = piste & ((1 << bits) - 1)
        if bas < taille:
            candidats.add(bas)
            candidats.add(bas ^ 1)
    return {a for a in candidats if a < taille}


def traiter(borne, clavier, base, systeme, jeu, arret, journal):
    """Releve un jeu. Renvoie 'appris', 'difficile' ou 'echec'."""
    borne.taille = None
    piste = (base.get("pistes") or {}).get(jeu)
    adresse_piste = int(piste["cheat"], 16) if piste else None

    en_cours = patienter(lambda: borne.jeu(), ATTENTE_LANCEMENT, arret)
    if not en_cours or en_cours[0] != jeu:
        journal("  le jeu n'a pas demarre (%s)" % (en_cours[0] if en_cours else "rien"))
        return "echec"
    taille = patienter(lambda: borne.mesurer(), ATTENTE_RAM, arret)
    if not taille:
        journal("  ce core n'expose pas sa RAM")
        return "difficile", "RAM non lisible"
    borne.taille = taille          # mesuree une fois, reutilisee ensuite

    if not attendre_vivant(borne, arret):
        journal("  le jeu ne s'anime pas, il n'encaissera pas de piece")
        return "difficile", "jeu inanime"

    # Une fois le jeu vivant, on peut accelerer : plus rien n'attend d'horloge
    # reelle, et les commandes suivent le rythme des images.
    if borne.rapide_voulue:
        borne.avance_rapide(True)

    candidats = None
    par_piste = False        # la piste a-t-elle reellement fonctionne ?
    valeurs = {}
    avant = None
    if adresse_piste is not None:
        cibles = candidats_piste(adresse_piste, borne.taille)
        for a in cibles:
            octet = borne.lire(a, 1)
            if octet is None:
                return "echec"
            valeurs[a] = octet[0]
    else:
        avant = borne.photo()
        if avant is None:
            return "echec"

    pieces = 0
    for _ in range(PIECES_MAX):
        arret()
        clavier.piece()
        time.sleep(1.0)
        pieces += 1

        if adresse_piste is not None:
            montes = set()
            for a in sorted(valeurs):
                octet = borne.lire(a, 1)
                if octet is None:
                    return "echec"
                if octet[0] == (valeurs[a] + 1) & 0xFF:
                    montes.add(a)
                valeurs[a] = octet[0]
            if montes:
                candidats, par_piste = montes, True
                break
            if pieces >= 2:
                journal("  piste sans effet, recherche complete")
                adresse_piste = None
                avant = borne.photo()
                if avant is None:
                    return "echec"
                pieces = 0
            continue

        apres = borne.photo()
        if apres is None or len(apres) != len(avant):
            return "echec"
        trouves = {a for a in range(len(apres))
                   if apres[a] == (avant[a] + 1) & 0xFF and avant[a] < 0x99}
        candidats = trouves if candidats is None else candidats & trouves
        avant = apres
        journal("  piece %d : %d candidat(s)" % (pieces, len(candidats)))
        if not candidats:
            return "difficile", "aucun candidat"
        if len(candidats) <= ASSEZ:
            break

    if not candidats:
        return "difficile", "compteur introuvable"

    # START consomme un credit : le solde baisse, un total de pieces non.
    avant_start = {}
    for a in sorted(candidats):
        octet = borne.lire(a, 1)
        if octet is not None:
            avant_start[a] = octet[0]
    arret()
    clavier.start()
    time.sleep(1.5)
    baissiers = set()
    for a in sorted(candidats):
        octet = borne.lire(a, 1)
        if octet is not None and a in avant_start and octet[0] < avant_start[a]:
            baissiers.add(a)

    surs = candidats & baissiers
    if not surs:
        if len(candidats) > SANS_CONFIRMATION_MAX:
            journal("  %d candidats, aucun confirme par le START : trop mince"
                    % len(candidats))
            return "difficile", "candidats non confirmes"
        surs = candidats        # une ou deux adresses, insertion verifiee
    retenues = sorted(surs)
    adresse = retenues[0]
    base.setdefault("jeux", {})[cle(en_cours[1], jeu)] = {
        "jeu": jeu,
        "nom": jeu,
        "systeme": systeme,
        "core": en_cours[1],
        "ram": {"taille": borne.taille, "commande": "READ_CORE_RAM"},
        "credits": {
            "adresse": adresse,
            "adresse_hex": "0x%04X" % adresse,
            "octets": 1,
            "miroirs": ["0x%04X" % a for a in retenues[1:]],
            "verifie_insertion": True,
            "verifie_consommation": adresse in baissiers,
            "pieces_observees": pieces,
        },
        "releve": {"le": time.strftime("%Y-%m-%d"),
                   "methode": "piste confirmee" if par_piste else "balayage nocturne",
                   "par": "nuit-credits.py"},
    }
    journal("  APPRIS 0x%04X%s%s" % (
        adresse,
        " (+%d miroir)" % len(retenues[1:]) if len(retenues) > 1 else "",
        "" if adresse in baissiers else "  [consommation non confirmee]"))
    return "appris"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--borne", default="127.0.0.1")
    parser.add_argument("--base", default="/recalbox/share/system/credits-arcade.json")
    parser.add_argument("--roms", default="/recalbox/share/roms")
    parser.add_argument("--systeme", default="fbneo",
                        help="un ou plusieurs, separes par des virgules "
                             "(fbneo,neogeo,mame)")
    parser.add_argument("--limite", type=int, default=0, help="0 = pas de limite")
    parser.add_argument("--pistes-seulement", action="store_true",
                        help="ne traiter que les jeux deja documentes (rapide et sur)")
    parser.add_argument("--essai", action="store_true",
                        help="montrer la liste sans rien lancer")
    parser.add_argument("--direct", action="store_true",
                        help="lancer RetroArch soi-meme, sans EmulationStation "
                             "(machine dediee)")
    parser.add_argument("--rapide", action="store_true",
                        help="avance rapide pendant le releve : inutile sur un "
                             "Raspberry deja a sa limite, x5,8 sur un PC")
    parser.add_argument("--reessayer", action="store_true",
                        help="reprendre aussi les jeux classes difficiles")
    parser.add_argument("--arret", default="/tmp/arret-nuit",
                        help="creer ce fichier arrete proprement")
    args = parser.parse_args()

    base = base_charger(args.base)
    pistes = base.get("pistes", {})

    systemes = [s.strip() for s in args.systeme.split(",") if s.strip()]
    liste = []
    for systeme in systemes:
        dossier = os.path.join(args.roms, systeme)
        if not os.path.isdir(dossier):
            print("%s : dossier absent, ignore" % systeme)
            continue
        roms = sorted(os.path.basename(f) for f in glob.glob(
            os.path.join(dossier, "*")) if f.lower().endswith((".zip", ".7z")))
        retenus = 0
        for rom in roms:
            jeu = rom.rsplit(".", 1)[0]
            if deja_fait(base, COEURS_NOMMES.get(systeme), jeu, args.reessayer):
                continue
            if args.pistes_seulement and jeu not in pistes:
                continue
            liste.append((systeme, jeu, os.path.join(dossier, rom)))
            retenus += 1
        print("%-12s %5d roms, %5d a traiter" % (systeme, len(roms), retenus))
    if args.limite:
        liste = liste[:args.limite]

    print("%d jeu(x) au total" % len(liste))
    if args.essai:
        for systeme, jeu, _ in liste[:40]:
            print("   %-8s %-14s %s" % (systeme, jeu,
                                        "piste" if jeu in pistes else "recherche complete"))
        if len(liste) > 40:
            print("   ... et %d autres" % (len(liste) - 40))
        print("\nessai : rien n'a ete lance.")
        return
    if not liste:
        return

    borne = Borne(args.borne, args.rapide, args.direct)
    if borne.jeu():
        raise SystemExit("Une partie est en cours — je ne demarre pas. "
                         "Reviens quand la borne est libre.")

    stop = {"demande": False}

    def demander_arret(*_):
        stop["demande"] = True
    signal.signal(signal.SIGINT, demander_arret)
    signal.signal(signal.SIGTERM, demander_arret)

    def arret():
        if stop["demande"] or os.path.exists(args.arret):
            raise Interruption()

    debut = time.time()
    comptes = {"appris": 0, "difficile": 0, "echec": 0}
    echecs_daffilee = 0

    def journal(msg):
        print(msg, flush=True)

    try:
        with ClavierVirtuel("clavier-credits") as clavier:
            for n, (systeme, jeu, chemin) in enumerate(liste, 1):
                arret()
                print("[%d/%d] %s/%s" % (n, len(liste), systeme, jeu), flush=True)
                borne.lancer(systeme, chemin)
                try:
                    resultat = traiter(borne, clavier, base, systeme, jeu,
                                       arret, journal)
                except Interruption:
                    raise
                except OSError as err:
                    journal("  erreur reseau : %s" % err)
                    resultat = "echec"

                if isinstance(resultat, tuple):
                    resultat, raison = resultat
                    essais = noter_difficulte(base, jeu, systeme, raison,
                                              COEURS_NOMMES.get(systeme))
                    definitif = (raison in SANS_APPEL
                                 or essais >= ESSAIS_AVANT_ABANDON)
                    journal("  difficile : %s (essai %d%s)"
                            % (raison, essais,
                               "" if definitif else ", on reessaiera"))
                comptes[resultat] = comptes.get(resultat, 0) + 1
                echecs_daffilee = echecs_daffilee + 1 if resultat == "echec" else 0

                base_ecrire(args.base, base)

                borne.avance_rapide(False)   # on rend la main a vitesse normale
                borne.quitter()
                borne.rapide = False         # le jeu suivant repart a neuf
                if not patienter(lambda: borne.jeu() is None, ATTENTE_ARRET, arret):
                    journal("  le jeu ne veut pas se fermer, seconde tentative")
                    borne.quitter()
                    if not patienter(lambda: borne.jeu() is None, ATTENTE_ARRET, arret):
                        raise SystemExit("Impossible de rendre la main au menu — "
                                         "j'arrete la pour ne rien casser.")
                if echecs_daffilee >= ECHECS_MAX:
                    raise SystemExit("%d echecs d'affilee — quelque chose ne va "
                                     "pas, j'arrete." % echecs_daffilee)
                time.sleep(1.0)
    except Interruption:
        print("\narret demande, tout est sauve.", flush=True)
    finally:
        base_ecrire(args.base, base)
        try:
            borne.avance_rapide(False)   # ne pas laisser la borne en accelere
            borne.quitter()
            borne.arreter_processus()
        except OSError:
            pass

    duree = time.time() - debut
    print("\n%d appris, %d difficiles, %d echecs, en %d min"
          % (comptes["appris"], comptes["difficile"], comptes["echec"], duree / 60))


if __name__ == "__main__":
    main()
