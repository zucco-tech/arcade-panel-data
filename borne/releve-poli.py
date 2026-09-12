#!/usr/bin/env python3
"""Releve des credits SUR la borne, sans jamais gener celui qui joue.

La borne appartient au joueur, pas au releve. D ou une regle unique, tenue
par ce programme :

    le releve ne demarre qu apres SILENCE secondes sans un geste,
    il rend la main au PREMIER bouton presse,
    et il ne repart qu apres un nouveau silence.

Il n y a donc jamais deux choses en concurrence : soit quelqu un se sert de
la borne, soit le releve travaille. La navigation ne peut pas ramer a cause
de nous, puisque nous ne tournons pas pendant qu on navigue.

Ce que ca coute quand le releve tourne : un RetroArch, celui qu
EmulationStation lance de toute facon pour jouer — pas un de plus, jamais
deux en meme temps. Environ 300 Mo sur les 4 Go de la borne, qui n a pas de
swap : on ne lance rien d autre, et on n ecrit la base que par petits bouts.

    python3 releve-poli.py --systemes fbneo neogeo neogeocd

Pour l arreter proprement, a tout moment :  touch /tmp/arret-releve-poli
Le releve reprend toujours ou il en etait : la base est ecrite apres chaque
jeu, et un jeu deja mesure n est pas remesure.

Aucune dependance : bibliotheque standard seulement.
"""

import argparse
import os
import select
import signal
import socket
import struct
import subprocess
import sys
import time

DOSSIER = "/recalbox/share/system/panneau-arcade"
OUTILS = os.path.join(DOSSIER, "outils")
BASE = os.path.join(DOSSIER, "releve-borne.json")
JOURNAL = os.path.join(DOSSIER, "releve.log")
SORTIE = os.path.join(DOSSIER, "releve-sortie.log")
ETAT = "/tmp/es_state.inf"
ARRET_MOI = "/tmp/arret-releve-poli"     # pose par l utilisateur : on s arrete
ARRET_FILS = "/tmp/arret-nuit"           # pose par nous : le releve s arrete

PORT_RA = 55355                          # commandes RetroArch
MANETTES = "AllInOne"                    # nom des manettes dans /proc/bus/input
EVENEMENT = struct.Struct("llHHi")

SILENCE = 300.0          # temps sans geste avant de (re)commencer
GRACE = 20.0             # temps laisse au releve pour s arreter tout seul
TOUR = 0.5               # cadence de surveillance quand on ne fait rien


def journal(message):
    ligne = "%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), message)
    try:
        with open(JOURNAL, "a") as fh:
            fh.write(ligne)
    except OSError:
        pass
    sys.stdout.write(ligne)
    sys.stdout.flush()


def ouvrir_manettes():
    """Les manettes de la carte, ouvertes sans exclusivite.

    Sans exclusivite : EmulationStation continue de les lire normalement. On
    ne fait que regarder passer les evenements pour savoir si quelqu un est
    devant la borne."""
    fds = []
    try:
        with open("/proc/bus/input/devices") as fh:
            blocs = fh.read().split("\n\n")
    except OSError:
        return fds
    for bloc in blocs:
        if 'Name="%s' % MANETTES not in bloc:
            continue
        for mot in bloc.split():
            if mot.startswith("event"):
                try:
                    fds.append(os.open("/dev/input/" + mot, os.O_RDONLY | os.O_NONBLOCK))
                except OSError:
                    pass
    return fds


def geste(fds):
    """Vrai si une manette a bouge depuis le dernier appel."""
    vu = False
    for fd in list(fds):
        while True:
            try:
                brut = os.read(fd, EVENEMENT.size * 64)
            except BlockingIOError:
                break
            except OSError:
                os.close(fd)
                fds.remove(fd)
                break
            if not brut:
                break
            for i in range(0, len(brut) - EVENEMENT.size + 1, EVENEMENT.size):
                if EVENEMENT.unpack_from(brut, i)[2] in (1, 3):   # touche ou stick
                    vu = True
    return vu


def etat_frontend():
    """Ce que EmulationStation dit faire en ce moment."""
    try:
        with open(ETAT) as fh:
            return dict(l.strip().split("=", 1) for l in fh if "=" in l)
    except (OSError, ValueError):
        return {}


def quitter_le_jeu():
    """Rend la main au menu : RetroArch ferme le jeu et EmulationStation
    revient. C est la meme commande que celle utilisee par le releve."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(b"QUIT", ("127.0.0.1", PORT_RA))
        s.close()
    except OSError:
        pass


class Releve:
    """Le programme de mesure, lance en fils et surveille."""

    def __init__(self, systemes, limite):
        self.systemes = systemes
        self.limite = limite
        self.processus = None
        self.systeme_en_cours = None

    def tourne(self):
        return self.processus is not None and self.processus.poll() is None

    def demarrer(self, systeme):
        """Lance le releve d un systeme, a la priorite la plus basse.

        « nice 19 » : si quoi que ce soit d autre reclame le processeur, il
        passe devant nous. Le jeu, lui, est lance par EmulationStation et
        garde sa priorite normale — sinon la memoire serait lue au ralenti."""
        for fichier in (ARRET_FILS,):
            try:
                os.unlink(fichier)
            except OSError:
                pass
        commande = ["nice", "-n", "19", "python3", "-u",
                    os.path.join(OUTILS, "nuit-credits.py"),
                    "--roms", "/recalbox/share/roms",
                    "--systeme", systeme,
                    "--base", BASE,
                    "--arret", ARRET_FILS,
                    "--coeur-nomme", "FinalBurn Neo"]
        if self.limite:
            commande += ["--limite", str(self.limite)]
        self.systeme_en_cours = systeme
        self.processus = subprocess.Popen(
            commande, stdout=open(SORTIE, "a"), stderr=subprocess.STDOUT,
            start_new_session=True)
        journal("releve demarre : %s (pid %d)" % (systeme, self.processus.pid))

    def rendre_la_main(self, raison):
        """Quelqu un est arrive : on s efface, dans cet ordre precis.

        1. le fichier d arret, pour que le releve ne demarre plus rien
        2. QUIT, pour que le jeu en cours se ferme et rende l ecran
        3. on laisse GRACE secondes au releve pour finir proprement
        4. passe ce delai, on coupe le groupe entier — rien ne doit survivre
        """
        if not self.tourne():
            return
        journal("on rend la main (%s)" % raison)
        open(ARRET_FILS, "w").close()
        quitter_le_jeu()
        fin = time.time() + GRACE
        while time.time() < fin and self.tourne():
            time.sleep(0.5)
        if self.tourne():
            try:
                os.killpg(os.getpgid(self.processus.pid), signal.SIGKILL)
            except OSError:
                pass
            journal("le releve ne s arretait pas : coupe")
        quitter_le_jeu()          # au cas ou un jeu serait reste ouvert
        self.processus = None


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--systemes", nargs="+", default=["fbneo", "neogeo", "neogeocd"])
    p.add_argument("--silence", type=float, default=SILENCE,
                   help="secondes sans geste avant de (re)commencer")
    p.add_argument("--limite", type=int, default=0,
                   help="ne mesurer que les N premiers jeux (essai)")
    a = p.parse_args()

    os.makedirs(DOSSIER, exist_ok=True)
    manettes = ouvrir_manettes()
    journal("=== surveillance polie demarree : %d manette(s), silence %d s ==="
            % (len(manettes), a.silence))
    releve = Releve(a.systemes, a.limite)
    restants = list(a.systemes)
    dernier_geste = time.time()
    manettes_vues = time.time()

    while not os.path.exists(ARRET_MOI):
        # Dormir SUR les manettes : un geste nous reveille aussitot.
        if manettes:
            try:
                select.select(manettes, [], [], TOUR)
            except (OSError, ValueError):
                manettes = []
        else:
            time.sleep(TOUR)
            if time.time() - manettes_vues > 30:       # une manette rebranchee
                manettes = ouvrir_manettes()
                manettes_vues = time.time()

        occupe = geste(manettes)
        if occupe:
            dernier_geste = time.time()
            releve.rendre_la_main("quelqu un se sert de la borne")

        if releve.tourne():
            continue

        # Le releve vient-il de finir son systeme ?
        if releve.processus is not None:
            journal("systeme %s termine" % releve.systeme_en_cours)
            if releve.systeme_en_cours in restants:
                restants.remove(releve.systeme_en_cours)
            releve.processus = None
            if not restants:
                restants = list(a.systemes)
                journal("tous les systemes faits, on recommence")

        # Rien ne tourne : peut-on demarrer ?
        if time.time() - dernier_geste < a.silence:
            continue
        frontend = etat_frontend()
        if frontend.get("State") == "playing":
            dernier_geste = time.time()     # une partie est en cours : on attend
            continue
        releve.demarrer(restants[0])

    releve.rendre_la_main("arret demande")
    journal("=== surveillance polie arretee ===")


if __name__ == "__main__":
    main()
