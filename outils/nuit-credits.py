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
import re
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
# RETROARCH=... : la version 1.18 livree par Ubuntu n expose pas la RAM a
# READ_CORE_RAM, et les coeurs 3D (Flycast) ont besoin d un RetroArch recent.
# Celle du 19/09/2026 vit dans nos outils, sans rien installer sur le systeme.
RETROARCH = os.environ.get("RETROARCH", "/mnt/recalbox/outils/retroarch-1.22.AppImage")
# BIOS=... : le dossier « system » de RetroArch (les BIOS Naomi sont dans dc/).
BIOS = os.environ.get("BIOS", "/mnt/recalbox/bios")
DOSSIER_COEURS = "/opt/coeurs"
JOURNAUX_RA = "/mnt/recalbox/journaux"
# Le nom que RetroArch annonce pour chaque coeur, pour savoir avant de
# lancer si un jeu a deja ete mesure. Il est reverifie a l execution.
COEURS_NOMMES = {
    "fbneo": "FinalBurn Neo", "fba": "FinalBurn Neo",
    "neogeo": "FinalBurn Neo", "neogeocd": "FinalBurn Neo",
    "naomi": "Flycast", "naomigd": "Flycast", "naomi2": "Flycast",
    "atomiswave": "Flycast",
    "mame0278": "MAME", "mame": "MAME",
}

# fbneo_rb.so est le coeur EXTRAIT DE L IMAGE RECALBOX x86_64, donc le meme
# FBNeo que celui du Pi de la borne, compile pour ce processeur.
#
# C est le seul qui convienne, pour deux raisons mesurees :
#   * il accepte les romsets d ici, la ou les compilations libretro recentes
#     les refusent (aburner : CHARGE contre « romset refuse ») — FBNeo a
#     change ses definitions de sets entre-temps, et les roms datent de 2025 ;
#   * il donne les memes adresses que la borne : pzloop2 compte ses credits
#     en 0x0450, valeur mesuree a la main sur le Pi avec de vraies pieces.
COEURS = {
    "fbneo": "fbneo_rb.so",
    "fba": "fbneo_rb.so",
    "neogeo": "fbneo_rb.so",
    "neogeocd": "fbneo_rb.so",
    "naomi": "flycast_libretro.so",
    "naomigd": "flycast_libretro.so",
    "naomi2": "flycast_libretro.so",
    "atomiswave": "flycast_libretro.so",
    "mame0278": "mame_libretro.so",
    "mame": "mame_libretro.so",
}
# Recalbox declare flycast-next en priorite 1 pour naomi, atomiswave et
# naomigd, et comme SEUL coeur pour naomi2 (systemlist.xml de la borne, relu
# le 24/09). On doit donc pouvoir changer de coeur sans retoucher au fichier :
#   COEUR_NAOMI=flycast-next_libretro.so
for _systeme in list(COEURS):
    _autre = os.environ.get("COEUR_%s" % _systeme.upper())
    if _autre:
        COEURS[_systeme] = _autre

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
# Cinq pieces plutot que quatre : « aucun candidat » est de loin la premiere
# cause d echec (87 sur 376 jeux), et une piece de plus coute deux secondes
# alors qu un jeu perdu coute tout.
PIECES_MAX = 5
ASSEZ = 4
# Sans confirmation par le START, on n'accepte qu'une preuve etroite : une ou
# deux adresses, pas davantage. Ecrire une fiche sur six candidats dont aucun
# n'a ete confirme, c'est inventer une reponse.
SANS_CONFIRMATION_MAX = 2
# Apres le START, on ne prenait qu un instantane a 1,5 s. Trop tot pour les
# jeux qui chargent : sur Naomi, 211 jeux sur 253 ont ete ecartes pour
# « candidats non confirmes ». On surveille maintenant sans relache pendant
# ATTENTE_START secondes : toute adresse qui descend, a n importe quel
# moment, est retenue. Reglable par l environnement pour pouvoir mesurer.
ATTENTE_START = float(os.environ.get("ATTENTE_START", "8.0"))
# 1,5 s entre deux lectures, pas 0,4 : lire, c est faire repondre RetroArch,
# et le marteler empeche le jeu d avancer jusqu a consommer le credit.
# Mesure du 21/09 : a 0,4 s, 0 confirmation sur 29 jeux ; l ancien code,
# qui laissait 1,5 s de calme avant sa lecture unique, en confirmait 21.
PAS_SURVEILLANCE = 1.5
ECHECS_MAX = 8            # au-dela, quelque chose ne va pas : on s'arrete

# Un echec peut etre passager : le jeu n'avait pas fini de demarrer et la
# piece n'a pas ete encaissee. On ne condamne un jeu qu'apres deux tentatives,
# sauf quand la cause est sans appel (le core n'expose pas sa RAM).
ESSAIS_AVANT_ABANDON = 2
# RetroArch rate parfois son demarrage : il meurt dans la seconde, toujours au
# meme endroit (segfault a la lecture d un pointeur nul). Mesure sur cette
# machine : environ un lancement sur cinq. Rien en aval ne peut le rattraper,
# mais relancer suffit — et sur six mille jeux sans surveillance, il le faut.
ESSAIS_LANCEMENT = 4
# Un RetroArch vivant qui n expose toujours pas de RAM apres ce delai affiche
# un ecran d erreur. On ne l attend pas plus longtemps, mais on ne le
# condamne pas non plus : il sera simplement reessaye.
ATTENTE_ECRAN_ERREUR = 35.0
# Au-dela de ce delai, un journal sans « Romset name: » ne peut plus etre un
# retard d ecriture : le set est vraiment inconnu de ce coeur.
DELAI_ROMSET_INCONNU = 25.0
SANS_APPEL = ("le coeur refuse la rom",
              "RAM non lisible",
              "jeu non supporte par ce coeur",
              "romset incomplet pour cette version",
              "romset inconnu de ce coeur")


class Interruption(Exception):
    """Demande d'arret propre."""


class Borne:
    """RetroArch vu d ici : on lui parle par son port reseau — lire la RAM, la
    photographier, quitter — et, en mode direct, on le lance et on l arrete
    soi-meme."""
    def __init__(self, hote, rapide_voulue=False, direct=False):
        self.hote = hote
        self.direct = direct         # on lance RetroArch soi-meme
        self.processus = None
        self.taille = None
        self.rapide = False              # etat courant de l'avance rapide
        self.rapide_voulue = rapide_voulue
        self.port = PORT_RA              # propre a cette instance
        self.affichage = None            # serveur X ou lancer RetroArch
        self.jeu_lance = None            # ce qu on a demande a RetroArch
        self.systeme_lance = None        # et sous quel systeme (chemin des etats)
        self.identite_prouvee = False    # sur la borne : le fichier d etat porte le bon nom
        self.coeur_lance = None
        self.coeur_nomme = None          # nom observe, quand l appelant le sait

    def _udp(self, port, texte, attendre_reponse=True, timeout=0.6):
        """Envoie un texte a RetroArch en UDP et renvoie sa reponse : une chaine
        vide si on n en attend pas, None s il ne repond pas."""
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
        """Le jeu en cours, et sous quel coeur.

        Surtout PAS par GET_STATUS : cette commande fait segfauter
        RetroArch 1.22.2 avec fbneo_recalbox.so, a tous les coups et en une
        seconde (mesure : deux morts sur deux, pendant que READ_CORE_RAM et
        VERSION repondent six fois sur six). Comme l outil l appelait toutes
        les demi-secondes pour savoir si le jeu avait demarre, il tuait
        systematiquement le jeu qu il venait de lancer.

        On se rabat sur ce qui repond : si la RAM du coeur se lit, c est que
        le jeu tourne. Et ce jeu, on sait lequel c est — c est nous qui
        l avons lance.
        """
        ram_lisible = self.lire(0, 1) is not None
        if not ram_lisible:
            # La RAM ne se lit pas : ou bien RetroArch n est pas la, ou bien
            # le coeur ne la publie pas (494 jeux FBNeo). VERSION repond des
            # que RetroArch tourne ; on demande alors une sauvegarde d etat,
            # et si elle arrive, le jeu tourne — et on lira dedans.
            if self.par_etat or not self._udp(self.port, "VERSION"):
                return None
        if not (self.jeu_lance and self.systeme_lance):
            return None
        # Sur la borne, c est EmulationStation qui lance : s il ignore notre
        # START parce que RetroArch est encore ouvert, c est le jeu d AVANT
        # qui repond -- et il etait mesure sous le nom du nouveau (arkatour2
        # « trouve » a l adresse d arkanoidpe, le 26/09). Le fichier d etat
        # que RetroArch ecrit porte le nom du contenu charge : c est la
        # preuve. Une fois par lancement.
        if not self.direct and not self.identite_prouvee:
            etat = self.etat()
            if etat is None:
                return None
            self.identite_prouvee = True
            if not ram_lisible:
                self.par_etat = True
                self._etat_cache = (time.monotonic(), etat)
        elif not ram_lisible and not self.par_etat:
            etat = self.etat()
            if etat is None:
                return None
            self.par_etat = True
            self._etat_cache = (time.monotonic(), etat)
        return (self.jeu_lance or "inconnu"), self.coeur_lance

    def lire(self, adresse, n):
        """Lit n octets de la RAM du coeur a une adresse, par READ_CORE_RAM ;
        None si le coeur ne les expose pas. En mode etat, on decoupe dans la
        derniere sauvegarde, rafraichie au plus toutes les 0,3 s : les
        lectures groupees (candidats, joueur 2) n en declenchent qu une."""
        if self.par_etat:
            quand, etat = self._etat_cache
            if etat is None or time.monotonic() - quand > 0.3:
                etat = self.etat()
                if etat is None:
                    return None
                self._etat_cache = (time.monotonic(), etat)
            bloc = etat[adresse:adresse + n]
            return bloc if len(bloc) == n else None
        reponse = self._udp(self.port, "READ_CORE_RAM %x %d" % (adresse, n))
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
        """Demande a RetroArch de quitter et, en mode direct, s assure qu il est
        bien mort."""
        self._udp(self.port, "QUIT", attendre_reponse=False)
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
        self._udp(self.port, "FAST_FORWARD", attendre_reponse=False)
        self.rapide = actif
        time.sleep(0.3)

    # --- sauvegarde d etat : quand le coeur ne publie pas sa RAM ----------
    # FBNeo ne publie la RAM que d une partie de ses pilotes (494 jeux sans,
    # le 24/09) ; et le FBNeo de la borne pas davantage (verifie le 26/09).
    # Mais il sait sauvegarder l etat complet de la machine, RAM comprise :
    # SAVE_STATE ecrit un fichier (RZIP, 15 ms sur le Raspberry), qu on lit
    # et decompresse. Les offsets y sont stables d une sauvegarde a l autre.
    # Une adresse ainsi trouvee est une POSITION DANS L ETAT, pas une adresse
    # machine : la fiche le dit (ram.commande), et le demon lit pareil.
    DOSSIER_ETATS = os.environ.get("DOSSIER_ETATS", "/recalbox/share/saves/%s")
    par_etat = False
    _etat_cache = (0.0, None)

    def _etat_le_plus_frais(self):
        """Le fichier d etat de ce jeu le plus recemment ecrit, et sa date.

        RetroArch ecrit dans le SLOT COURANT, dont on ne sait rien (mesure du
        26/09 : il etait a 2). On ne devine donc pas un nom de fichier.
        """
        motif = os.path.join(self.DOSSIER_ETATS % (self.systeme_lance or ""),
                             "%s.state*" % (self.jeu_lance or ""))
        recent, quand = None, 0.0
        for chemin in glob.glob(motif):
            if chemin.endswith(".png"):
                continue                      # la vignette, pas l etat
            try:
                date = os.path.getmtime(chemin)
            except OSError:
                continue
            if date > quand:
                recent, quand = chemin, date
        return recent, quand

    def etat(self):
        """L etat complet de la machine, par SAVE_STATE puis lecture du
        fichier ; None si RetroArch n a rien ecrit."""
        import rzip
        _, avant = self._etat_le_plus_frais()
        self._udp(self.port, "SAVE_STATE", attendre_reponse=False)
        # RetroArch ecrit le fichier en plusieurs fois, et sur le NAS ca dure :
        # on attend qu il soit la, que sa taille ne bouge plus, et que le
        # decodage aboutisse (un RZIP tronque leve une erreur, on reessaie).
        fin = time.monotonic() + 3.0
        taille_vue = -1
        while time.monotonic() < fin:
            chemin, date = self._etat_le_plus_frais()
            try:
                if chemin and date > avant:
                    taille = os.path.getsize(chemin)
                    if taille > 64 and taille == taille_vue:
                        return rzip.lire_etat(chemin)
                    taille_vue = taille
            except (OSError, ValueError):
                taille_vue = -1
            time.sleep(0.05)
        return None

    def mesurer(self):
        """La taille de la RAM que le coeur expose, par dichotomie : on double l
        adresse jusqu a ce que la lecture echoue, puis on resserre."""
        if self.lire(0, 1) is None:
            etat = self.etat()
            if etat:
                self.par_etat = True
                self._etat_cache = (time.monotonic(), etat)
                return len(etat)
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
        """Toute la RAM exposee, d un bloc ; None si une lecture a echoue en
        route, une photo partielle fausserait la comparaison."""
        if self.taille is None:
            self.taille = self.mesurer()
        if not self.taille:
            return None
        if self.par_etat:
            etat = self.etat()
            if etat is not None:
                self._etat_cache = (time.monotonic(), etat)
            return etat
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
            self.jeu_lance = os.path.basename(chemin_rom).rsplit(".", 1)[0]
            self.systeme_lance = systeme
            self.par_etat, self._etat_cache = False, (0.0, None)
            self.identite_prouvee = False
            self.coeur_lance = self.coeur_nomme or COEURS_NOMMES.get(systeme)
            return
        coeur = COEURS.get(systeme)
        if coeur is None:
            return
        self.jeu_lance = os.path.basename(chemin_rom).rsplit(".", 1)[0]
        self.systeme_lance = systeme
        self.par_etat, self._etat_cache = False, (0.0, None)
        self.identite_prouvee = False
        self.coeur_lance = self.coeur_nomme or COEURS_NOMMES.get(systeme)
        self.arreter_processus()
        self.oublier_les_restes()      # aucun rescape ne doit trainer
        imposer_options_coeur(self.coeur_lance)
        env = dict(os.environ)
        env.update({"HOME": "/root", "XDG_RUNTIME_DIR": "/run/user/0"})
        if self.affichage:
            env["DISPLAY"] = self.affichage
            env.pop("WAYLAND_DISPLAY", None)
        self.processus = subprocess.Popen(
            ["dbus-run-session", "--", RETROARCH, "--verbose",
             "--config", "/root/.config/retroarch/retroarch.cfg"]
            + self._surcharge() + [
             "-L", os.path.join(DOSSIER_COEURS, coeur), chemin_rom],
            env=env, stdout=self._journal_retroarch(),
            stderr=subprocess.STDOUT, start_new_session=True)

    def _surcharge(self):
        """Les reglages propres a cette instance, dans un fichier a part.

        Le port de commande d abord : RetroArch le lit dans sa config, pas
        sur la ligne de commande, et deux instances ne peuvent pas ecouter
        au meme endroit.

        Puis, quand on tourne dans un serveur X imbrique, le plein ecran est
        desactive : il reclame l extension XFree86-VidMode, absente de
        Xephyr, qui tombe alors avec le serveur. Inutile de toute facon, la
        fenetre occupe deja tout le serveur imbrique.
        """
        chemin = os.path.join(JOURNAUX_RA, "retroarch-%d.cfg" % self.port)
        try:
            os.makedirs(JOURNAUX_RA, exist_ok=True)
            with open(chemin, "w") as fh:
                fh.write('network_cmd_enable = "true"\n')
                fh.write('network_cmd_port = "%d"\n' % self.port)
                # Les BIOS (Naomi, Atomiswave, Dreamcast) vivent avec nos
                # outils, pas dans le systeme : on le dit a chaque lancement.
                fh.write('system_directory = "%s"\n' % BIOS)
                fh.write('menu_driver = "null"\n')
                if self.affichage:
                    fh.write('video_fullscreen = "false"\n')
                    fh.write('video_windowed_fullscreen = "false"\n')
                    fh.write('video_window_save_positions = "false"\n')
        except OSError:
            return []
        return ["--appendconfig", chemin]

    @staticmethod
    def _journal_retroarch():
        """Ou ecrire ce que RetroArch raconte.

        Jeter sa sortie dans /dev/null rendait tout diagnostic impossible :
        quand il refuse de demarrer, la raison est la et nulle part ailleurs.
        On garde le dernier lancement, ecrase a chaque fois — ce qui compte
        c est celui qui vient d echouer.
        """
        try:
            os.makedirs(JOURNAUX_RA, exist_ok=True)
            return open(os.path.join(JOURNAUX_RA, "retroarch.log"), "w")
        except OSError:
            return subprocess.DEVNULL

    def arreter_processus(self):
        """Coupe le RetroArch qu on a lance, s il en reste un.

        On tue tout le GROUPE, pas le fils direct : celui-ci est
        dbus-run-session, et le terminer laissait RetroArch vivant, reattache
        a systemd. Or un seul RetroArch orphelin fait segfauter le lancement
        suivant — les deux se disputent le contexte graphique et le port 55355.
        Un raté suffisait alors a bloquer tout le reste du balayage.
        """
        if self.processus is None:
            # Pas de processus a nous : sur la borne, c est EmulationStation
            # qui a lance RetroArch. On lui demande de quitter, et on ATTEND
            # qu il soit parti -- sinon le START suivant est ignore par
            # EmulationStation, et c est le jeu d avant qui se fait mesurer.
            if self.direct or not self._udp(self.port, "VERSION"):
                return
            fin = time.monotonic() + ATTENTE_ARRET
            while time.monotonic() < fin:
                self._udp(self.port, "QUIT", attendre_reponse=False)
                time.sleep(1.5)
                if not self._udp(self.port, "VERSION"):
                    time.sleep(2.0)          # EmulationStation reprend la main
                    return
            return
        try:
            groupe = os.getpgid(self.processus.pid)
        except OSError:
            groupe = None
        for coup in (signal.SIGTERM, signal.SIGKILL):
            if groupe is None:
                break
            try:
                os.killpg(groupe, coup)
            except OSError:
                break
            try:
                self.processus.wait(timeout=8)
                break
            except subprocess.TimeoutExpired:
                continue
        try:
            self.processus.kill()
        except OSError:
            pass
        self.processus = None
        self.oublier_les_restes()

    @staticmethod
    def oublier_les_restes():
        """Tue les RetroArch qui ne sont plus a personne.

        Ceinture et bretelles : un processus reattache a systemd n est plus
        dans notre groupe et survivrait au nettoyage ci-dessus. Sur une
        machine dediee au releve, aucun RetroArch ne doit tourner en dehors
        de celui qu on pilote.
        """
        try:
            sortie = subprocess.run(["pgrep", "-f", RETROARCH],
                                    capture_output=True, text=True).stdout
        except OSError:
            return
        for ligne in sortie.split():
            try:
                pid = int(ligne)
            except ValueError:
                continue
            if pid == os.getpid():
                continue
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass


def attendre_vivant(borne, arret, delai=ATTENTE_VIVANT, clavier=None):
    """Attend que le jeu s'anime vraiment.

    Avant son ecran d'attente, la RAM est quasi figee et la piece tombe dans
    le vide — c'est ce qui faisait echouer les CPS2, longs a demarrer. Deux
    lectures a une seconde d'intervalle suffisent a le voir vivre.

    Une machine qui ne bouge pas attend peut-etre un appui — ecran « press
    start », calibrage (constate a la borne le 26/09). Un START toutes les
    douze secondes, jamais de piece : une piece hors d un jeu pret est perdue.
    """
    fin = time.time() + delai
    precedent = None
    dernier_start = time.time()
    while time.time() < fin:
        arret()
        if clavier is not None and time.time() - dernier_start > 12.0:
            clavier.start()
            dernier_start = time.time()
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

    # Rien n a bouge. Avant de condamner le jeu, verifier qu il n est pas
    # simplement EN PAUSE : constate a l ecran, RetroArch affiche « En
    # pause » et la RAM se fige. Un jeu classe « inanime » sur une pause est
    # un jeu perdu pour rien.
    borne._udp(borne.port, "PAUSE_TOGGLE", attendre_reponse=False)
    time.sleep(1.5)
    precedent = borne.photo()
    time.sleep(1.5)
    bloc = borne.photo()
    if bloc is not None and precedent is not None:
        if sum(1 for a, b in zip(bloc, precedent) if a != b) >= REMUE_MINIMUM:
            time.sleep(REPOS_APRES_VIVANT)
            return True
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


OPTIONS_COEUR = "/root/.config/retroarch/config/%s/%s.opt"
# Flycast force le mode gratuit par defaut : le jeu n a alors jamais besoin de
# credit, la piece monte bien un compteur mais START ne decompte rien. C est
# la cause des 211 « candidats non confirmes » sur Naomi (trouve le 21/09).
# RetroArch reecrit ce fichier en quittant : on le remet avant chaque lancement.
OPTIONS_IMPOSEES = {"Flycast": {"reicast_force_freeplay": "disabled"}}


def imposer_options_coeur(coeur):
    """Remet les options du coeur que RetroArch pourrait avoir changees."""
    voulues = OPTIONS_IMPOSEES.get(coeur)
    if not voulues:
        return
    chemin = OPTIONS_COEUR % (coeur, coeur)
    try:
        with open(chemin) as fh:
            lignes = fh.readlines()
    except (IOError, OSError):
        return
    change = False
    for i, ligne in enumerate(lignes):
        cle = ligne.split("=")[0].strip()
        if cle in voulues:
            neuve = '%s = "%s"\n' % (cle, voulues[cle])
            if lignes[i] != neuve:
                lignes[i] = neuve
                change = True
    if not change:
        return
    try:
        provisoire = chemin + ".tmp"
        with open(provisoire, "w") as fh:
            fh.writelines(lignes)
        os.replace(provisoire, chemin)
    except (IOError, OSError):
        pass


def _ecran_repond(affichage, jeton=None):
    """Vrai si un client X arrive a ouvrir cet ecran."""
    env = dict(os.environ)
    if affichage:
        env["DISPLAY"] = affichage
    if jeton:
        env["XAUTHORITY"] = jeton
    try:
        return subprocess.run(["xdpyinfo"], env=env,
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL,
                              timeout=15).returncode == 0
    except FileNotFoundError:
        return True          # xdpyinfo absent : on ne bloque pas pour si peu
    except (OSError, subprocess.SubprocessError):
        return False


def ecran_utilisable(affichage=None):
    """S assure qu on a un ecran, en retrouvant le jeton au besoin.

    La session graphique change de jeton d acces a chaque redemarrage. Le
    fichier passe au service au lancement devient alors muet : RetroArch
    charge bien le jeu, puis meurt faute d ecran. Sans ce controle, chaque
    jeu est note « ne demarre pas » et finit ecarte pour de bon — c est ce
    qui est arrive le 20 septembre, apres un redemarrage de session a 8 h 23.

    On relit donc le jeton sur la ligne de commande du serveur X lui-meme.
    Renvoie vrai si l ecran repond, apres correction eventuelle.
    """
    if _ecran_repond(affichage):
        return True
    try:
        sortie = subprocess.run(["ps", "-eo", "args"], stdout=subprocess.PIPE,
                                text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    for jeton in re.findall(r"-auth (\S+)", sortie):
        if os.path.exists(jeton) and _ecran_repond(affichage, jeton):
            os.environ["XAUTHORITY"] = jeton
            return True
    return False


def ouvrir_clavier(affichage):
    """Le clavier qui convient au mode de fonctionnement.

    Avec un serveur X a soi (--affichage), on injecte par XTEST : les touches
    n existent que dans ce serveur, donc ni le bureau de l utilisateur ni les
    autres instances ne les voient. C est ce qui rend le travail en parallele
    possible, et ce qui empeche un Entree d atterrir dans un terminal.

    Sans affichage dedie, on garde le clavier uinput historique.
    """
    if affichage:
        from clavier_xtest import ClavierXTest
        return ClavierXTest(affichage)
    return ClavierVirtuel("clavier-credits")



def journal_retroarch():
    """Le journal de RetroArch tel quel, ou None s il n est pas lisible.

    Il est ecrit sur le NAS et arrive en retard : a lire apres un delai
    confortable, jamais dans la seconde qui suit un lancement."""
    try:
        with open(os.path.join(JOURNAUX_RA, "retroarch.log"), "rb") as fh:
            return fh.read().decode("utf-8", "replace")
    except OSError:
        return None

def romset_inconnu():
    """Vrai si FBNeo ne connait pas du tout ce set.

    Son message « Romset is unknown » ne s ecrit QUE sur l ecran, jamais dans
    le journal. Mais un set inconnu ne produit qu une seule ligne FBNeo — le
    reglage de frequence — et n annonce jamais de « Romset name: », qu un jeu
    normal ecrit dans les deux premieres secondes.

    A n appeler qu apres un delai confortable : le journal est sur le NAS et
    arrive en retard. Interroge a huit secondes, ce controle avait produit 23
    faux positifs sur 20 jeux. A vingt-cinq secondes, le doute n existe plus.
    """
    texte = journal_retroarch()
    if texte is None:
        return False
    return "[FBNeo]" in texte and "Romset name" not in texte


def refus_fbneo():
    """Ce que FBNeo vient de dire, quand il refuse une rom.

    Sans ca, un jeu refuse coute six minutes : FBNeo affiche son ecran
    d erreur et RESTE OUVERT, alors l outil attend quatre-vingt-dix secondes
    qu il demarre, quatre fois de suite. Le message est dans le journal des
    la premiere seconde ; il suffit de le lire.

    Renvoie la raison, ou None si la rom n a pas ete refusee.
    """
    texte = journal_retroarch()
    if texte is None:
        return None
    # On ne se fie qu a des messages EXPLICITES. Deduire un refus de
    # l ABSENCE de « Romset name: » a produit 23 faux positifs sur 20 jeux :
    # le journal est ecrit sur le NAS et arrive en retard, donc un jeu
    # parfaitement sain paraissait inconnu. Un silence ne prouve rien.
    if "marked as not working" in texte:
        return "jeu non supporte par ce coeur"
    # Attention : l ecran d erreur dit « is missing », mais le JOURNAL, lui,
    # ecrit « ROM at index N with name X and CRC Y is required ». Chercher le
    # texte de l ecran ne detectait donc jamais rien.
    if "is required" in texte or "missing files for THIS VERSION" in texte:
        return "romset incomplet pour cette version"
    return None


def lancer_avec_reprises(borne, systeme, jeu, chemin, arret, journal):
    """Lance le jeu et attend qu il tourne vraiment, en reessayant.

    On ne se contente pas d attendre : si le processus est deja mort, inutile
    de patienter quatre-vingt-dix secondes pour rien, on relance tout de
    suite. Renvoie le couple (jeu, coeur) annonce par RetroArch, ou None.
    """
    ecran_erreur = False
    for essai in range(1, ESSAIS_LANCEMENT + 1):
        arret()
        borne.lancer(systeme, chemin)
        fin = time.time() + ATTENTE_LANCEMENT
        depart = time.time()
        en_cours = None
        while time.time() < fin:
            arret()
            en_cours = borne.jeu()
            if en_cours and en_cours[0] == jeu:
                return en_cours
            mort = (borne.direct and borne.processus is not None
                    and borne.processus.poll() is not None)
            if mort:
                break          # inutile d attendre un processus disparu
            # FBNeo qui refuse une rom affiche son erreur et RESTE ouvert :
            # sans ce controle, on l attendrait quatre-vingt-dix secondes,
            # quatre fois de suite, pour un jeu qui ne demarrera jamais.
            if time.time() - depart > 12.0:
                refus = refus_fbneo()
                if refus:
                    borne.arreter_processus()
                    return refus
            if time.time() - depart > DELAI_ROMSET_INCONNU and romset_inconnu():
                borne.arreter_processus()
                return "romset inconnu de ce coeur"
            # RetroArch vivant mais muet au-dela de ce delai : c est un ecran
            # d erreur. Inutile d attendre les quatre-vingt-dix secondes.
            if time.time() - depart > ATTENTE_ECRAN_ERREUR:
                ecran_erreur = True
                break
            time.sleep(0.5)
        refus = refus_fbneo()
        if refus:
            journal("  %s — inutile d insister" % refus)
            borne.arreter_processus()
            return refus                 # une chaine : refus net, pas un jeu
        # RetroArch ouvert mais muet : c est un ecran d erreur, pas un
        # demarrage lent. Deux essais suffisent — quatre font deux minutes
        # de fenetres qui clignotent pour rien.
        if ecran_erreur and essai >= 2:
            # RetroArch repond, mais aucun contenu n est charge : ni RAM, ni
            # sauvegarde d etat possible. C est l ecran d erreur de FBNeo, qui
            # refuse le romset (mesure sur la borne le 26/09 : chopper, chqflag).
            # Un jeu que l emulateur refuse n est pas jouable sur la borne non
            # plus : inutile d y revenir a chaque tour.
            borne.arreter_processus()
            return "le coeur refuse la rom"
        if essai < ESSAIS_LANCEMENT:
            journal("  demarrage rate (%s), tentative %d sur %d"
                    % (en_cours[0] if en_cours else "rien mesure",
                       essai + 1, ESSAIS_LANCEMENT))
            borne.arreter_processus()
            time.sleep(2.0)
    return None


def base_charger(chemin):
    """Charge la base des credits, et la convertit au passage si elle est encore
    indexee par systeme et non par coeur."""
    with open(chemin) as fh:
        base = json.load(fh)
    if migrer_par_coeur(base):
        base_ecrire(chemin, base)
    return base


def base_ecrire(chemin, base):
    # Un nom de fichier temporaire propre a ce processus. Deux ecrivains qui
    # partagent le meme ".tmp" melangent leurs contenus et laissent une base
    # tronquee — c'est arrive, et ca coute toutes les fiches relevees.
    """Ecrit la base de facon atomique."""
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


def migrer_par_coeur(base):
    """Reindexe une base ecrite par systeme vers un index par coeur.

    Les premieres fiches portaient `fbneo/1942`. C est le coeur qui decide de
    la disposition memoire, d ou `finalburn-neo/1942`. Chaque fiche sait sous
    quel coeur elle a ete mesuree ; les ecartes ne notent que leur systeme,
    dont le coeur se deduit.

    Sans cette conversion, `deja_fait` cherche `finalburn-neo/1942` dans une
    base qui ne contient que `fbneo/1942` : les releves deviennent invisibles
    et seraient tous refaits.

    Renvoie vrai si quelque chose a bouge ; a l appelant d ecrire la base.
    """
    change = False
    for section in ("jeux", "difficiles"):
        anciennes = base.get(section)
        if not anciennes:
            continue
        nouvelles = {}
        for ancienne, fiche in sorted(anciennes.items()):
            prefixe, _, jeu = ancienne.partition("/")
            coeur = (fiche.get("core")
                     or COEURS_NOMMES.get(fiche.get("systeme") or prefixe))
            if not jeu or not coeur:
                # Coeur indeterminable : mieux vaut laisser la cle en place
                # que de ranger la fiche sous "inconnu".
                nouvelles[ancienne] = fiche
                continue
            fiche.setdefault("core", coeur)
            neuve = cle(coeur, jeu)
            if neuve != ancienne:
                change = True
            # Deux systemes qui partagent un coeur — fbneo et neogeo — se
            # rejoignent ici. On garde celle qui porte une adresse.
            gardee = nouvelles.get(neuve)
            if (gardee is not None
                    and (gardee.get("credits") or {}).get("adresse")
                    and not (fiche.get("credits") or {}).get("adresse")):
                continue
            nouvelles[neuve] = fiche
        base[section] = nouvelles
    return change


def surveiller_baisse(borne, avant, duree, arret):
    """Les adresses qui descendent sous leur valeur d avant, a tout moment.

    Un seul relevé differe attrape le decompte seulement s il tombe pile
    dans la fenetre. On relit donc en boucle pendant toute la duree : des
    qu une adresse passe sous sa valeur de depart, elle est acquise, meme
    si le jeu la remonte ensuite (ecran de selection, remise a zero).
    """
    baissiers = set()
    fin = time.monotonic() + duree
    while True:
        # Le calme d abord : le jeu doit pouvoir tourner sans etre lu.
        arret()
        time.sleep(PAS_SURVEILLANCE)
        for a in sorted(avant):
            if a in baissiers:
                continue
            octet = borne.lire(a, 1)
            if octet is not None and octet[0] < avant[a]:
                baissiers.add(a)
        if len(baissiers) == len(avant) or time.monotonic() >= fin:
            return baissiers


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


def photographier_echec(jeu, raison):
    """Garde une image du jeu qui vient d echouer, pour comprendre apres.

    On ne garde qu une image par jeu et par raison, et rien si le dossier
    devient trop gros : six mille jeux feraient vite des giga-octets.
    """
    dossier = os.path.join(JOURNAUX_RA, "echecs")
    try:
        os.makedirs(dossier, exist_ok=True)
        if len(os.listdir(dossier)) > 300:
            return
    except OSError:
        return
    propre = "".join(c if c.isalnum() else "-" for c in raison)[:28]
    chemin = os.path.join(dossier, "%s_%s.png" % (jeu, propre))
    if os.path.exists(chemin):
        return
    try:
        from capture_fenetre import photographier
        photographier(chemin)
    except Exception:
        pass



def montees_depuis(borne, avant, candidats):
    """Une photo de plus, et les adresses qui ont monte d exactement un.

    Renvoie (candidats, photo) : les adresses encore en lice, croisees avec
    les precedentes, et la photo qui servira de base au prochain tour. (None,
    None) quand la photo est inutilisable ou qu il ne reste plus personne.
    Un compteur de credits ne depasse pas 99 : au-dela, ce n en est pas un."""
    apres = borne.photo()
    if apres is None or len(apres) != len(avant):
        return None, None
    montes = {a for a in range(len(apres))
              if monte_de_un(avant[a], apres[a])}
    candidats = montes if candidats is None else candidats & montes
    return (candidats or None), apres

def monte_de_un(vieux, neuf):
    """Un credit de plus, que la carte compte en binaire ou en BCD.

    Beaucoup de cartes d arcade comptent en decimal code binaire : apres 9
    vient 0x10, pas 0x0A. On ne cherchait que « +1 » : une piece sur dix
    passait inapercue, et tout compteur deja au-dela de neuf devenait
    invisible. Le filtre « < 0x99 » qui etait la disait deja que ces
    compteurs sont en BCD — on ne s en servait pas.

    Un compteur de credits ne depasse pas 99, dans les deux ecritures.
    """
    if vieux >= 0x99:
        return False
    if neuf == vieux + 1:                       # binaire, et BCD hors retenue
        return True
    bas = vieux & 0x0F
    return bas == 9 and neuf == (vieux & 0xF0) + 0x10      # BCD : 9 -> 10


def chercher_avec(borne, appuyer, arret, essais=3, assez=4):
    """Cherche l octet qui monte de 1 a chaque appui sur UNE entree donnee.

    Le meme principe que pour la piece, mais applicable a n importe quel
    bouton du panneau. Sert au repli : tous les jeux n encaissent pas leur
    piece sur SELECT — les flippers, des jeux de tir, certains japonais ont
    le monnayeur ailleurs. Tant qu on n essaie que SELECT, ces jeux-la sont
    perdus alors qu ils marchent tres bien.

    Renvoie l ensemble des candidats, vide si cette entree ne fait rien.
    """
    candidats = None
    avant = borne.photo()
    if avant is None:
        return set()
    for _ in range(essais):
        arret()
        appuyer()
        time.sleep(1.2)
        candidats, avant = montees_depuis(borne, avant, candidats)
        if candidats is None:
            return set()
        if len(candidats) <= assez:
            break
    return candidats or set()


def est_neogeo():
    """Vrai si le jeu en cours est un Neo Geo.

    Un jeu Neo Geo charge toujours son BIOS depuis neogeo.zip ; le journal de
    RetroArch le montre. C est la seule facon fiable de le savoir depuis ici.
    """
    texte = journal_retroarch()
    if texte is None:
        return False
    return "neogeo" in texte.lower()


def repli_autres_entrees(borne, clavier, joueur, arret, journal):
    """Quand SELECT ne donne rien, on essaie les autres boutons du poste.

    Renvoie (nom de l entree, candidats) ou (None, set()).
    """
    # DESACTIVE. Essayer les autres boutons ouvrait des menus de service sur
    # plusieurs systemes — constate a l ecran sur Neo Geo (« NEO-GEO MVS
    # SYSTEM : HARDWARE TEST / SOFT DIP / BOOK KEEPING ») et signale
    # ailleurs. Dans ces menus le compteur de credits ne veut plus rien dire,
    # et l adresse relevee serait fausse.
    #
    # Le repli trouvait le monnayeur sur environ un jeu sur dix. Ce n est pas
    # assez pour risquer d ecrire de fausses adresses sur les autres. Les
    # jeux dont le monnayeur n est pas sur SELECT partent en « difficile » et
    # seront traites autrement.
    if True:
        return None, set()

    # JAMAIS sur Neo Geo. Le monnayeur y est toujours sur SELECT — c est un
    # systeme standardise — et appuyer sur les autres boutons ouvre le menu
    # « NEO-GEO MVS SYSTEM : HARDWARE TEST / SOFT DIP / BOOK KEEPING ».
    # Dans ce menu le compteur de credits ne se comporte plus normalement, et
    # l adresse relevee serait fausse. Constate a l ecran.
    if est_neogeo():
        journal("  Neo Geo : pas de repli, le monnayeur est sur SELECT")
        return None, set()
    for nom, code in clavier.entrees_possibles(joueur):
        if nom == "select":
            continue                    # deja essaye, c est pour ca qu on est la
        arret()
        trouves = chercher_avec(borne, lambda c=code: clavier.appuyer(c), arret,
                                essais=2, assez=4)
        if trouves:
            journal("  la piece passe par « %s » (joueur %d) : %d candidat(s)"
                    % (nom, joueur, len(trouves)))
            return nom, trouves
    return None, set()


PIECES_J2 = 3               # autant que pour le joueur 1
ASSEZ_J2 = 2


def chercher_joueur2(borne, clavier, arret, journal):
    """L adresse du compteur de credits du JOUEUR 2, ou None.

    Sur une borne a deux postes, chacun alimente SON compteur tant que
    personne n a appuye sur START. Sans cette seconde adresse, le demon des
    LED ne peut pas savoir que le joueur 2 a paye, et son bouton START ne
    clignote pas — il reste devant une borne muette alors qu il a mis sa
    piece.

    On ne devine pas cette adresse a cote de celle du joueur 1 : mesure
    faite, une seule piece joueur 2 fait monter 288 octets sur pzloop2 et 181
    sur bloodwar. Un jeu qui tourne remue des dizaines de compteurs internes.
    Il faut donc la meme methode que pour le joueur 1 — plusieurs pieces, et
    on ne garde que ce qui monte de 1 a chaque fois — puis START joueur 2
    pour confirmer que c est bien un solde et non un total encaisse.
    """
    candidats = None
    avant = borne.photo()
    if avant is None:
        return set()
    for n in range(1, PIECES_J2 + 1):
        arret()
        clavier.piece_j2()
        time.sleep(1.5)
        candidats, avant = montees_depuis(borne, avant, candidats)
        if candidats is None:
            return set()
        if len(candidats) <= ASSEZ_J2:
            break

    return candidats


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
    if borne.par_etat:
        journal("  RAM non publiee : lecture par sauvegarde d etat (%d octets)" % taille)

    if not attendre_vivant(borne, arret, clavier=clavier):
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
    ecran_franchi = False      # a-t-on deja tente de passer un menu ?
    candidats2 = None          # ce qui monte toutes les DEUX pieces
    avant2 = avant             # la photo d il y a deux pieces
    entree_piece = "select"
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
                   if monte_de_un(avant[a], apres[a])}
        candidats = trouves if candidats is None else candidats & trouves
        # Des cartes demandent DEUX pieces pour un credit : le compteur ne
        # monte alors qu une fois sur deux, et la regle ci-dessus ne retient
        # que le compteur de pieces cumulees — qui ne redescend jamais au
        # START. C est le symptome des jeux « candidats non confirmes ». On
        # suit donc en parallele ce qui monte de un toutes les deux pieces.
        if avant2 is not None and pieces % 2 == 0:
            deux = {a for a in range(len(apres))
                    if monte_de_un(avant2[a], apres[a])}
            candidats2 = deux if candidats2 is None else candidats2 & deux
        if pieces % 2 == 0:
            avant2 = apres
        avant = apres
        journal("  piece %d : %d candidat(s)" % (pieces, len(candidats)))
        if not candidats and not ecran_franchi:
            # Rien de compte : le jeu attend peut-etre un appui — choix de
            # langue, « press start » — et la piece est tombee dans le vide
            # (constate a la borne le 26/09). On fait ce qu un joueur ferait,
            # puis on reessaie une piece, en repartant de zero.
            ecran_franchi = True
            journal("  piece non comptee : START, A, B, puis on reessaie")
            for agir in (clavier.start, lambda: clavier.bouton("a"),
                         lambda: clavier.bouton("b")):
                arret()
                agir()
                time.sleep(1.0)
            time.sleep(2.0)
            avant = borne.photo()
            if avant is None:
                return "echec"
            candidats, candidats2, avant2 = None, None, avant
            continue
        if not candidats:
            # SELECT n encaisse pas : ce jeu a peut-etre son monnayeur sur un
            # autre bouton. On les essaie tous avant de le condamner.
            entree, trouves = repli_autres_entrees(borne, clavier, 1, arret, journal)
            if trouves:
                candidats, par_piste = trouves, False
                entree_piece = entree
                break
            return "difficile", "aucun candidat"
        if len(candidats) <= ASSEZ:
            break

    if not candidats:
        return "difficile", "compteur introuvable"

    # Les pieces du JOUEUR 2 avant tout START : sur une vraie borne, les deux
    # joueurs alimentent leur compteur pendant l ecran d attente, et c est
    # seulement ensuite que l un appuie sur START. Chercher le second
    # compteur une fois la partie lancee ne marche pas — mesure faite, zero
    # trouve sur trois jeux.
    candidats_j2 = chercher_joueur2(borne, clavier, arret, journal)
    avant_start_j2 = {}
    for a in sorted(candidats_j2):
        o = borne.lire(a, 1)
        if o is not None:
            avant_start_j2[a] = o[0]

    # START consomme un credit : le solde baisse, un total de pieces non.
    # On soumet au START les deux familles : ce qui monte a chaque piece, et
    # ce qui ne monte qu une fois sur deux. Seul ce qui redescend sera retenu,
    # donc elargir ici ne peut pas faire entrer de fausse adresse.
    a_tester = candidats | (candidats2 or set())
    avant_start = {}
    for a in sorted(a_tester):
        octet = borne.lire(a, 1)
        if octet is not None:
            avant_start[a] = octet[0]
    arret()
    clavier.start()
    baissiers = surveiller_baisse(borne, avant_start, ATTENTE_START, arret)

    surs = a_tester & baissiers
    if surs and not (candidats & baissiers):
        journal("  confirme par le START a raison de DEUX pieces par credit")

    # Le START n a rien consomme. Sur bien des cartes ce n est pas lui qui
    # lance la partie : certaines veulent un appui plus franc, d autres un
    # bouton de jeu (MAME a ce repli depuis longtemps, pas nous). Un joueur
    # devant la borne essaierait la meme chose. Constat du 25/09 : a l ecran,
    # le jeu reclame START et ne demarre pas.
    if not surs:
        for nom, agir in (("START tenu 1 s", lambda: clavier.start(1.0)),
                          ("bouton A", lambda: clavier.bouton("a")),
                          ("bouton B", lambda: clavier.bouton("b")),
                          ("bouton X", lambda: clavier.bouton("x"))):
            arret()
            avant_bis = {}
            for a in sorted(a_tester):
                octet = borne.lire(a, 1)
                if octet is not None:
                    avant_bis[a] = octet[0]
            agir()
            encore = surveiller_baisse(borne, avant_bis, ATTENTE_START, arret)
            if encore:
                journal("  consomme par %s, pas par le START" % nom)
                surs, baissiers = a_tester & encore, encore
                break

    if not surs:
        if len(candidats) > SANS_CONFIRMATION_MAX:
            journal("  %d candidats, aucun confirme par le START : trop mince"
                    % len(candidats))
            return "difficile", "candidats non confirmes"
        surs = candidats        # une ou deux adresses, insertion verifiee
    retenues = sorted(surs)
    adresse = retenues[0]

    # START joueur 2 : son compteur a lui doit redescendre.
    adresse_j2, j2_confirme = None, False
    # START joueur 2 TOUJOURS, meme sans candidat : sur beaucoup de jeux
    # c est cet appui qui fait entrer le second joueur, et sans lui son
    # credit n est jamais consomme — donc jamais confirmable.
    arret()
    clavier.start_j2()
    time.sleep(2.0)
    if candidats_j2:
        baissiers_j2 = [a for a, v in avant_start_j2.items()
                        if (borne.lire(a, 1) or [v])[0] < v]
        if baissiers_j2:
            adresse_j2, j2_confirme = sorted(baissiers_j2)[0], True
        elif len(candidats_j2) == 1:
            adresse_j2 = sorted(candidats_j2)[0]

    # Meme octet pour les deux joueurs : ce n est pas un second compteur,
    # c est une cagnotte COMMUNE, ou les deux monnayeurs alimentent le meme
    # solde. Le noter comme « adresse du joueur 2 » ferait croire au demon
    # que chaque poste a son credit, et il eclairerait faux.
    compteur_commun = adresse_j2 is not None and adresse_j2 == adresse
    if compteur_commun:
        adresse_j2, j2_confirme = None, False

    base.setdefault("jeux", {})[cle(en_cours[1], jeu)] = {
        "jeu": jeu,
        "nom": jeu,
        "systeme": systeme,
        "core": en_cours[1],
        "ram": {"taille": borne.taille, "commande": ("sauvegarde d etat" if borne.par_etat else "READ_CORE_RAM"),
                    # Une position dans l etat ne vaut que pour le coeur qui l a ecrite :
                    # on note qui a mesure, l export s en sert.
                    "hote": socket.gethostname()},
        "credits": {
            "adresse": adresse,
            "adresse_hex": "0x%04X" % adresse,
            "octets": 1,
            "miroirs": ["0x%04X" % a for a in retenues[1:]],
            "verifie_insertion": True,
            "verifie_consommation": adresse in baissiers,
            "pieces_observees": pieces,
            "entree_piece": entree_piece,
            "compteur_commun": compteur_commun,
            "adresse_j2": adresse_j2,
            "adresse_j2_hex": None if adresse_j2 is None else "0x%04X" % adresse_j2,
            "j2_verifie_consommation": j2_confirme,
        },
        "releve": {"le": time.strftime("%Y-%m-%d"),
                   "methode": "piste confirmee" if par_piste else "balayage nocturne",
                   "par": "nuit-credits.py"},
    }
    journal("  APPRIS 0x%04X%s%s%s" % (
        adresse,
        " (+%d miroir)" % len(retenues[1:]) if len(retenues) > 1 else "",
        "" if adresse in baissiers else "  [consommation non confirmee]",
        ("  J2 en 0x%04X" % adresse_j2) if adresse_j2 is not None
        else ("  [cagnotte commune aux deux joueurs]" if compteur_commun
              else "  [pas de second compteur]")))
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
    parser.add_argument("--jeux", nargs="*", default=None,
                        help="ne mesurer que ces jeux (noms de sets), meme deja connus")
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
    parser.add_argument("--port", type=int, default=PORT_RA,
                        help="port de commande de CETTE instance "
                             "(55355 par defaut ; un par instance)")
    parser.add_argument("--affichage", default=None,
                        help="serveur X ou lancer RetroArch, par exemple :10 "
                             "(un Xephyr par instance). Active du meme coup "
                             "le clavier XTEST, qui n existe que pour lui.")
    parser.add_argument("--part", default=None,
                        help="N/M : ne traiter que la part N sur M de la "
                             "liste, pour repartir le travail sans doublon")
    parser.add_argument("--coeur-nomme", default=None,
                        help="le nom que ce coeur annonce reellement ici, "
                             "quand l appelant l a observe")
    args = parser.parse_args()

    def nom_coeur(systeme):
        """Le nom que le coeur de ce systeme annonce sur cette machine.

        COEURS_NOMMES dit ce qu on attend. Mais le meme fbneo_libretro.so
        s annonce « FinalBurn Neo » sur la borne et « fb_alpha » ici, et ce
        sont deux dispositions memoire distinctes : filtrer sur le nom
        attendu ferait sauter des jeux jamais mesures sous le coeur d ici.
        Quand l appelant a vu le vrai nom, il le passe.
        """
        return args.coeur_nomme or COEURS_NOMMES.get(systeme)

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
            if deja_fait(base, nom_coeur(systeme), jeu, args.reessayer):
                continue
            if args.pistes_seulement and jeu not in pistes:
                continue
            liste.append((systeme, jeu, os.path.join(dossier, rom)))
            retenus += 1
        print("%-12s %5d roms, %5d a traiter" % (systeme, len(roms), retenus))
    if args.jeux:
        # Des jeux nommes : on les prend meme s ils sont deja connus ou
        # ecartes — c est fait pour verifier ou reprendre a la main.
        voulus = set(args.jeux)
        liste = []
        for systeme in systemes:
            dossier = os.path.join(args.roms, systeme)
            for rom in sorted(glob.glob(os.path.join(dossier, "*"))):
                jeu = os.path.basename(rom).rsplit(".", 1)[0]
                if jeu in voulus and rom.lower().endswith((".zip", ".7z")):
                    liste.append((systeme, jeu, rom))
        print("jeux demandes : %d trouve(s) sur %d" % (len(liste), len(voulus)))
    if args.part:
        # « 2/3 » : un jeu sur trois, en commencant par le deuxieme. Les
        # parts sont disjointes et couvrent tout, sans se concerter.
        n_part, _, m_part = args.part.partition("/")
        n_part, m_part = int(n_part), int(m_part)
        if not 1 <= n_part <= m_part:
            raise SystemExit("--part attend N/M avec 1 <= N <= M")
        liste = liste[n_part - 1::m_part]
        print("part %d sur %d : %d jeu(x)" % (n_part, m_part, len(liste)))
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
    borne.coeur_nomme = args.coeur_nomme
    borne.port = args.port
    borne.affichage = args.affichage
    if borne.jeu():
        raise SystemExit("Une partie est en cours — je ne demarre pas. "
                         "Reviens quand la borne est libre.")

    stop = {"demande": False}

    def demander_arret(*_):
        """Un signal d arret (SIGTERM, Ctrl-C) : on note la demande, le releve s
        arretera proprement au prochain point sur."""
        stop["demande"] = True
    signal.signal(signal.SIGINT, demander_arret)
    signal.signal(signal.SIGTERM, demander_arret)

    def arret():
        """Leve Interruption si un arret a ete demande, par signal ou par le
        fichier drapeau."""
        if stop["demande"] or os.path.exists(args.arret):
            raise Interruption()

    debut = time.time()
    comptes = {"appris": 0, "difficile": 0, "echec": 0}
    echecs_daffilee = 0

    def journal(msg):
        """Une ligne de journal, ecrite tout de suite : le journal est suivi en
        direct."""
        print(msg, flush=True)

    if not ecran_utilisable(args.affichage):
        print("l ecran ne repond pas : on ne demarre pas (sinon chaque jeu "
              "serait note « ne demarre pas » et finirait ecarte a tort)",
              flush=True)
        return 2

    try:
        with ouvrir_clavier(args.affichage) as clavier:
            for n, (systeme, jeu, chemin) in enumerate(liste, 1):
                arret()
                print("[%d/%d] %s/%s" % (n, len(liste), systeme, jeu), flush=True)
                try:
                    demarrage = lancer_avec_reprises(borne, systeme, jeu,
                                                     chemin, arret, journal)
                    if isinstance(demarrage, str):
                        resultat = ("difficile", demarrage)
                    elif demarrage is None:
                        # On l ENREGISTRE, sinon le meme jeu bloque repasse en
                        # premier a chaque relance et mange une minute a
                        # chaque fois. Un echec non note est un echec repete.
                        if not ecran_utilisable(args.affichage):
                            journal("  l ecran ne repond plus : on s arrete, "
                                    "plutot que d ecarter des jeux a tort")
                            raise Interruption()
                        journal("  RetroArch n a pas demarre, on le note")
                        resultat = ("difficile", "ne demarre pas")
                    else:
                        resultat = traiter(borne, clavier, base, systeme, jeu,
                                           arret, journal)
                except Interruption:
                    raise
                except OSError as err:
                    journal("  erreur reseau : %s" % err)
                    resultat = "echec"

                if isinstance(resultat, tuple):
                    resultat, raison = resultat
                    # Une image du jeu au moment de l echec : elle dit souvent
                    # ce que la memoire ne dit pas — un ecran d attente qui ne
                    # vient jamais, un message d erreur, un monnayeur qui
                    # reclame autre chose.
                    photographier_echec(jeu, raison)
                    essais = noter_difficulte(base, jeu, systeme, raison,
                                              nom_coeur(systeme))
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
