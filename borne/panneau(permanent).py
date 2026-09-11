#!/usr/bin/env python3
"""
Eclaire le panneau selon le jeu SURVOLE dans le menu, avant meme de le lancer.

A deposer dans /recalbox/share/userscripts/ sous le nom exact :

    panneau(permanent).py

Recalbox fait tout le travail d observation : EmulationStation reecrit
/tmp/es_state.inf a chaque mouvement dans le menu, avec le jeu survole,
son systeme et son etat. C est le meme fichier que lit le marquee. On le
surveille, on cherche le jeu dans boutons-arcade.json, et on allume le
nombre de boutons qu il utilise.

Partage des roles, pour que deux programmes ne se disputent jamais les LED :

    dans le menu        ce script eclaire le panneau selon le jeu survole
    partie en cours     credits(permanent).py prend la main, ce script se tait
    aucun jeu survole   on rend le panneau tel que la carte l a laisse

Regle du second panneau, decidee avec le proprietaire de la borne : des
qu un second joueur peut rejoindre, les MEMES boutons s allument des deux
cotes. Un jeu a un seul joueur laisse le panneau 2 eteint.

Cote LED, on n ecrit QUE dans brightness, jamais dans multi_intensity : les
couleurs restent celles que la carte a posees. Meme regle que le demon des
credits, pour la meme raison — rien n entre en conflit avec le code de la
carte, et une remise a 255 rend la LED exactement telle qu elle etait.

Aucune dependance : uniquement la bibliotheque standard.
"""

import json
import os
import time

ETAT = "/tmp/es_state.inf"
BASE_BOUTONS = "/recalbox/share/system/boutons-arcade.json"
JOURNAL = "/recalbox/share/system/panneau.log"

# Meme correspondance que credits(permanent).py, reprise de
# recalbox_allinone_rgb.sh : la LED n eclaire le bouton ORDRE[n].
#     rangee haute : LED 1 2 3  ->  boutons 3 4 5
#     rangee basse : LED 4 5 6  ->  boutons 1 2 6
ORDRE_BOUTONS = [3, 4, 5, 1, 2, 6]
PLEIN = "255"
PERIODE = 0.3                # cadence de lecture du fichier d etat


def journal(msg):
    try:
        with open(JOURNAL, "a") as fh:
            fh.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def lire_etat():
    """Le fichier ini plat de EmulationStation, cle=valeur."""
    etat = {}
    try:
        with open(ETAT, "r", encoding="utf-8", errors="replace") as fh:
            for ligne in fh:
                ligne = ligne.strip()
                if "=" in ligne and not ligne.startswith("#"):
                    cle, _, valeur = ligne.partition("=")
                    etat[cle.strip()] = valeur.strip()
    except (IOError, OSError):
        return None
    return etat


def charger_boutons():
    try:
        with open(BASE_BOUTONS) as fh:
            return json.load(fh).get("jeux", {})
    except (IOError, OSError, ValueError):
        return {}


def chemins_led(joueur):
    """Les six boutons du poste, chacun avec ses deux LED."""
    paires = []
    for n in range(1, 7):
        paire = []
        for k in (1, 2):
            chemin = "/sys/class/leds/aio_p%d_b%d_%d" % (joueur, n, k)
            if os.path.isdir(chemin):
                paire.append(chemin)
        paires.append(paire)
    return paires


def ecrire(chemin, valeur):
    try:
        with open(os.path.join(chemin, "brightness"), "w") as fh:
            fh.write(valeur)
    except (IOError, OSError):
        pass


class Panneau:
    def __init__(self, joueur):
        self.joueur = joueur
        self.boutons = chemins_led(joueur)
        self.dernier = None          # ce qu on a applique en dernier

    def appliquer(self, nombre, allume=True):
        """Allume les `nombre` premiers boutons logiques, eteint le reste."""
        voulu = (nombre if allume else 0)
        if voulu == self.dernier:
            return
        for position, chemins in enumerate(self.boutons):
            numero = ORDRE_BOUTONS[position] if position < len(ORDRE_BOUTONS) else position + 1
            valeur = PLEIN if (allume and numero <= nombre) else "0"
            for chemin in chemins:
                ecrire(chemin, valeur)
        self.dernier = voulu

    def rendre(self):
        """Tout a 255 : l etat de repos de la carte."""
        if self.dernier == "repos":
            return
        for chemins in self.boutons:
            for chemin in chemins:
                ecrire(chemin, PLEIN)
        self.dernier = "repos"


def main():
    boutons = charger_boutons()
    panneaux = {1: Panneau(1), 2: Panneau(2)}
    journal("demarrage — %d jeu(x) avec boutons" % len(boutons))
    derniere_modif = None
    dernier_jeu = None
    base_vue = 0.0

    while True:
        time.sleep(PERIODE)
        # La base peut etre mise a jour pendant que la borne tourne.
        try:
            m = os.path.getmtime(BASE_BOUTONS)
            if m != base_vue:
                boutons = charger_boutons()
                base_vue = m
        except OSError:
            pass
        try:
            modif = os.path.getmtime(ETAT)
        except OSError:
            continue
        if modif == derniere_modif:
            continue
        derniere_modif = modif

        etat = lire_etat()
        if not etat:
            continue

        # Partie en cours : le demon des credits est maitre des LED.
        if etat.get("State") == "playing" or etat.get("Action") == "rungame":
            dernier_jeu = None
            for p in panneaux.values():
                p.dernier = None       # on ne sait plus ce qu il y a dessus
            continue

        chemin = etat.get("GamePath") or ""
        jeu = os.path.basename(chemin).rsplit(".", 1)[0] if chemin else ""
        if not jeu or etat.get("IsFolder") == "1":
            for p in panneaux.values():
                p.rendre()
            dernier_jeu = None
            continue

        fiche = boutons.get(jeu)
        if not fiche or not fiche.get("nombre"):
            for p in panneaux.values():
                p.rendre()
            if jeu != dernier_jeu:
                journal("%s : pas de fiche, panneau au repos" % jeu)
            dernier_jeu = jeu
            continue

        nombre = int(fiche["nombre"])
        deuxieme = int(fiche.get("joueurs") or 1) >= 2
        panneaux[1].appliquer(nombre)
        panneaux[2].appliquer(nombre, allume=deuxieme)
        if jeu != dernier_jeu:
            journal("%s : %d bouton(s), joueur 2 %s"
                    % (jeu, nombre, "allume" if deuxieme else "eteint"))
        dernier_jeu = jeu


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
