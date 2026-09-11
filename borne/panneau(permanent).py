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

Cote LED : brightness pour allumer ou eteindre, et multi_intensity pour la
couleur d origine du bouton quand la base la connait — bleu pour un coup de
poing, rouge pour un saut, comme sur la vraie borne. La couleur posee par la
carte est memorisee AVANT d etre changee, et rendue des qu on quitte le jeu
ou qu on survole un jeu sans couleurs. C est la meme discipline que le demon
des credits : rien ne reste modifie derriere nous.

L ordre des composantes est lu dans multi_index, que le materiel publie
lui-meme (« red green blue » ici) : on ne le suppose pas.

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

# Couleurs nommees par la base, telles qu elles sont ecrites sur les bornes.
TEINTES = {
    "red": (0xFF, 0x00, 0x00), "blue": (0x00, 0x00, 0xFF),
    "green": (0x00, 0xFF, 0x00), "yellow": (0xFF, 0xFF, 0x00),
    "white": (0xFF, 0xFF, 0xFF), "black": (0x20, 0x20, 0x20),
    "orange": (0xFF, 0x60, 0x00), "purple": (0x80, 0x00, 0xFF),
    "pink": (0xFF, 0x40, 0x80), "cyan": (0x00, 0xFF, 0xFF),
    "grey": (0x60, 0x60, 0x60), "gray": (0x60, 0x60, 0x60),
}


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


def lire_fichier(chemin):
    try:
        with open(chemin) as fh:
            return fh.read().strip()
    except (IOError, OSError):
        return None


def couleur_pour(chemin_led, rvb):
    """La couleur dans l ordre que CETTE led annonce dans multi_index."""
    index = (lire_fichier(os.path.join(chemin_led, "multi_index")) or "red green blue").split()
    par_nom = {"red": rvb[0], "green": rvb[1], "blue": rvb[2]}
    return " ".join(str(par_nom.get(nom, 0)) for nom in index)


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


def ecrire(chemin, valeur, fichier="brightness"):
    try:
        with open(os.path.join(chemin, fichier), "w") as fh:
            fh.write(valeur)
    except (IOError, OSError):
        pass


class Panneau:
    def __init__(self, joueur):
        self.joueur = joueur
        self.boutons = chemins_led(joueur)
        self.dernier = None          # ce qu on a applique en dernier
        self.origine = {}            # couleur posee par la carte, par led

    def _memoriser(self, chemin):
        if chemin not in self.origine:
            valeur = lire_fichier(os.path.join(chemin, "multi_intensity"))
            if valeur:
                self.origine[chemin] = valeur

    def _rendre_couleur(self, chemin):
        if chemin in self.origine:
            ecrire(chemin, self.origine[chemin], "multi_intensity")

    def appliquer(self, nombre, couleurs, allume=True):
        """Allume les `nombre` premiers boutons logiques, eteint le reste,
        et pose la couleur d origine de chacun quand la base la connait."""
        voulu = (nombre, tuple(sorted(couleurs.items()))) if allume else 0
        if voulu == self.dernier:
            return
        for position, chemins in enumerate(self.boutons):
            numero = ORDRE_BOUTONS[position] if position < len(ORDRE_BOUTONS) else position + 1
            utilise = allume and numero <= nombre
            teinte = ((couleurs.get("BUTTON%d" % numero) or {}).get("couleur")
                      or teinte_par_defaut(nombre, numero))
            rvb = TEINTES.get((teinte or "").strip().lower())
            for chemin in chemins:
                self._memoriser(chemin)
                if utilise and rvb:
                    ecrire(chemin, couleur_pour(chemin, rvb), "multi_intensity")
                else:
                    self._rendre_couleur(chemin)
                ecrire(chemin, PLEIN if utilise else "0")
        self.dernier = voulu

    def rendre(self):
        """Tout a 255 et couleurs d origine : l etat de repos de la carte."""
        if self.dernier == "repos":
            return
        for chemins in self.boutons:
            for chemin in chemins:
                self._rendre_couleur(chemin)
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
            # On rend les couleurs d origine AVANT que le demon des credits
            # ne memorise les siennes : sinon il retiendrait nos couleurs
            # comme etant celles de la carte.
            if dernier_jeu is not None:
                for p in panneaux.values():
                    p.rendre()
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
        couleurs = fiche.get("boutons") or {}
        deuxieme = int(fiche.get("joueurs") or 1) >= 2
        panneaux[1].appliquer(nombre, couleurs)
        panneaux[2].appliquer(nombre, couleurs, allume=deuxieme)
        if jeu != dernier_jeu:
            journal("%s : %d bouton(s), %d couleur(s), joueur 2 %s"
                    % (jeu, nombre, sum(1 for v in couleurs.values() if v.get("couleur")),
                       "allume" if deuxieme else "eteint"))
        dernier_jeu = jeu


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
