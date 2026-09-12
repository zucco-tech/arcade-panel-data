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
import re
import select
import struct
import time

ETAT = "/tmp/es_state.inf"
BASE_BOUTONS = "/recalbox/share/system/panneau-arcade/boutons-arcade.json"
JOURNAL = "/recalbox/share/system/panneau-arcade/panneau.log"
# La table de couleurs par systeme livree par Recalbox pour ce panneau. Elle
# servait aux scripts allinone[…].sh, appeles a chaque mouvement dans le
# menu ; ils sont desactives (un bash par evenement, et deux programmes qui
# ecrivent les memes LED). On lit leur table ici, une fois, pour rendre les
# memes couleurs qu a l origine sur les systemes que la table plus bas ne
# decrit pas.
PALETTE_RECALBOX = "/recalbox/scripts/recalbox_allinone_rgb.sh"
# Les couleurs que la carte AURAIT si les scripts d origine tournaient. On
# les publie ici pour que le demon des credits les reprenne telles quelles a
# la fin d une partie, au lieu de relire les LED — ce que nous avons pu
# repeindre entre-temps. Sans cette source unique, chacun memorisait les
# couleurs de l autre et le panneau revenait faux en sortant d un jeu.
COULEURS_CARTE = "/recalbox/share/system/panneau-arcade/couleurs-carte.json"

# Meme correspondance que credits(permanent).py, reprise de
# recalbox_allinone_rgb.sh : la LED n eclaire le bouton ORDRE[n].
#     rangee haute : LED 1 2 3  ->  boutons 3 4 5
#     rangee basse : LED 4 5 6  ->  boutons 1 2 6
ORDRE_BOUTONS = [3, 4, 5, 1, 2, 6]
PLEIN = "255"
# Dans le menu le panneau VEILLE : un tiers de la puissance suffit a lire
# quels boutons servent. Un geste sur une manette le reveille a fond, et il
# se rendort apres VEILLE_APRES secondes sans rien. Les clips video qui
# defilent tout seuls ne comptent pas comme un geste.
INTENSITE_MENU = "80"
VEILLE_APRES = 30.0
# En sortant d une partie, le demon des credits rend les couleurs de la
# carte — un instant APRES que nous ayons repeint celles du jeu survole. Il
# avait donc le dernier mot et le panneau revenait aux couleurs de la carte.
# On repeint pendant ces quelques secondes, jusqu a ce qu il ait fini.
INSISTER_APRES_JEU = 3.0
# On n attend pas la fin d un tour de boucle pour reagir : le programme dort
# SUR les manettes (select), donc un bouton presse le reveille aussitot.
# Sans cela, le rallumage arrivait avec jusqu a PERIODE de retard.
AUTOMATIQUES = {"startgameclip", "endgameclip"}
MANETTES = "AllInOne"        # nom des manettes de la carte dans /proc/bus/input
FORMAT_EVENEMENT = struct.Struct("llHHi")
PERIODE = 0.1                # cadence de lecture du fichier d etat : trois
                             # fois plus fine qu avant, pour que le survol
                             # suive la navigation sans retard visible

# Machines a UN joueur par construction : une console portable n a qu un
# ecran et une manette. Le poste 2 y reste noir quoi qu en dise la fiche.
PORTABLES = {"gb", "gbc", "gba", "gamegear", "lynx", "ngp", "ngpc", "wswan",
             "wswanc", "pokemini", "supervision", "megaduck", "nds", "psp",
             "3ds", "gw", "tic80"}

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


# Ce que chaque console utilise comme boutons, pour les systemes qui n ont
# pas de fiche arcade. Le nombre est celui des boutons d action de la manette
# d origine, dans la limite des six du panneau. Les couleurs ne sont donnees
# que quand elles sont emblematiques et certaines ; sinon la palette
# d origine par nombre de boutons s applique.
BOUTONS_PAR_SYSTEME = {
    "nes": (2, None),            "fds": (2, None),
    "snes": (6, ["red", "yellow", "blue", "green", "white", "white"]),
    "megadrive": (3, None),      "sg1000": (2, None),
    "mastersystem": (2, None),   "gamegear": (2, None),
    "pcengine": (2, None),       "supergrafx": (2, None),
    "neogeo": (4, ["red", "yellow", "green", "blue"]),
    "neogeocd": (4, ["red", "yellow", "green", "blue"]),
    "gb": (2, None),             "gbc": (2, None),
    "gba": (4, None),
    "n64": (6, None),            "psx": (6, None),
    "saturn": (6, None),         "dreamcast": (6, None),
    "atari2600": (1, None),      "atari7800": (2, None),
    "colecovision": (2, None),   "vectrex": (4, None),
    "amiga600": (2, None),       "amiga1200": (2, None),
    "c64": (1, None),            "amstradcpc": (2, None),
}


def charger_palette_recalbox():
    """Les tableaux « declare -a systeme=("R G B" ...) » du script Recalbox :
    11 entrees — boutons 1 a 8, puis select, start, hotkey — rendues en
    (r, v, b). On les garde toutes : les six premieres servent a eclairer,
    les trois dernieres a rendre la carte telle que Recalbox la peignait."""
    table = {}
    try:
        with open(PALETTE_RECALBOX) as fh:
            texte = fh.read()
    except (IOError, OSError):
        return table
    for nom, corps in re.findall(r'declare -a (\w+)=\((.*?)\)', texte):
        entrees = re.findall(r'"([^"]*)"', corps)
        boutons = []
        for e in entrees[:11]:
            try:
                boutons.append(tuple(int(x, 16) for x in e.split()))
            except ValueError:
                boutons.append((0, 0, 0))
        table[nom] = boutons
    return table


RECALBOX = charger_palette_recalbox()


def fiche_de_systeme(systeme):
    """Une fiche minimale pour un systeme sans fiche arcade, ou None.

    Les couleurs sont celles que Recalbox donne a ce systeme (la table du
    script d origine) : c est ce que le proprietaire a toujours vu. Notre
    table ne sert qu a borner le NOMBRE de boutons a ceux de la manette
    d origine. Un systeme que Recalbox ne connait pas prend sa couleur de
    secours (astrocity), comme le faisait le script d origine."""
    systeme = systeme or ""
    entree = BOUTONS_PAR_SYSTEME.get(systeme)
    boutons = (RECALBOX.get(systeme) or [])[:6] or None
    secours = None
    if not boutons:
        # Le systeme virtuel « arcade », ses sous-categories par
        # constructeur, et tout ce que Recalbox ne nomme pas : les couleurs
        # astrocity, un jeu de couleurs par poste, comme le script d origine.
        boutons = (RECALBOX.get("astrocityp1") or [])[:6] or None
        secours = (RECALBOX.get("astrocityp2") or [])[:6] or None
    if boutons:
        allumes = [i for i, rvb in enumerate(boutons, 1) if any(rvb)]
        nombre = entree[0] if entree else (max(allumes) if allumes else 0)
        if not nombre:
            return None

        def palette(table):
            return {"BUTTON%d" % i: {"rvb": table[i - 1]}
                    for i in range(1, nombre + 1)
                    if i - 1 < len(table) and any(table[i - 1])}
        fiche = {"nombre": nombre, "boutons": palette(boutons)}
        if secours:
            fiche["boutons_j2"] = palette(secours)
        return fiche
    if not entree:
        return None
    nombre, palette = entree
    couleurs = {}
    if palette:
        for i, teinte in enumerate(palette[:nombre], 1):
            couleurs["BUTTON%d" % i] = {"couleur": teinte}
    return {"nombre": nombre, "boutons": couleurs}


def joueurs_depuis(etat):
    """Le champ Players de EmulationStation : « 1 », « 2 », « 1-2 », « 1-4 »…
    Vrai si un second joueur peut jouer. None si le champ est absent."""
    texte = (etat or {}).get("Players") or ""
    nombres = [int(x) for x in re.findall(r"\d+", texte)]
    if not nombres:
        return None
    return max(nombres) >= 2


def teinte_par_defaut(nombre, numero):
    palette = PALETTE_DEFAUT.get(nombre) or PALETTE_DEFAUT[6]
    return palette[numero - 1] if numero - 1 < len(palette) else "white"


def lire_fichier(chemin):
    try:
        with open(chemin) as fh:
            return fh.read().strip()
    except (IOError, OSError):
        return None


# Le materiel MENT sur l ordre de ses composantes. multi_index annonce
# « red green blue », mais les WS2812B de cette carte sont cablees vert,
# rouge, bleu. Mesure faite le 12/09/2026 sur la borne : ecrire « 255 0 0 »
# sur le bouton 1 et « 0 255 0 » sur le bouton 2 allume le premier en VERT
# et le second en ROUGE (photo a l appui). C est le meme constat que celui
# deja inscrit dans credits(permanent).py, qui ecrit depuis toujours dans
# cet ordre : les deux programmes peignent enfin pareil.
ORDRE_MATERIEL = (1, 0, 2)          # vert, rouge, bleu


def couleur_pour(chemin_led, rvb):
    """La couleur telle que la carte l allume vraiment."""
    return " ".join(str(rvb[i]) for i in ORDRE_MATERIEL)


def couleurs_de_carte(systeme):
    """Ce que le script Recalbox aurait ecrit dans les LED pour ce systeme.

    On reproduit sa correspondance a l identique : les LED 1 a 8 recoivent
    les couleurs des boutons 3,4,5,1,2,6,7,8 ; la LED « select » recoit la
    9e entree, « start » la 10e, et la touche hotkey la 11e. Un systeme
    absent de sa table prend les couleurs astrocity, un jeu par poste, comme
    le faisait le script."""
    connue = RECALBOX.get(systeme or "")
    rendu = {}
    for joueur in (1, 2):
        table = connue or RECALBOX.get("astrocityp%d" % joueur) or []
        if not table:
            continue
        for place, numero in enumerate(ORDRE_BOUTONS + [7, 8], 1):
            if numero - 1 >= len(table):
                continue
            for chemin in _leds("aio_p%d_b%d" % (joueur, place)):
                rendu[chemin] = table[numero - 1]
        for decalage, nom in enumerate(("select", "start"), 8):
            if decalage < len(table):
                for chemin in _leds("aio_p%d_%s" % (joueur, nom)):
                    rendu[chemin] = table[decalage]
        if joueur == 1 and len(table) > 10:
            for chemin in _leds("aio_hotkey"):
                rendu[chemin] = table[10]
    return rendu


def publier_couleurs_carte(couleurs):
    """Ecrit ces couleurs la ou le demon des credits saura les lire."""
    try:
        with open(COULEURS_CARTE + ".tmp", "w") as fh:
            json.dump({c: list(rvb) for c, rvb in couleurs.items()}, fh)
        os.replace(COULEURS_CARTE + ".tmp", COULEURS_CARTE)
    except OSError:
        pass


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


def chemins_annexes(joueur):
    """Les LED du poste qui ne sont pas des boutons de jeu : pièce et start,
    plus la touche hotkey (elle n existe que sur le poste 1). Dans le menu
    elles suivent la meme intensite que les boutons, et le poste 2 les
    eteint avec lui."""
    noms = ["aio_p%d_start" % joueur, "aio_p%d_select" % joueur]
    return [c for nom in noms for c in _leds(nom)]


def _leds(nom):
    return [c for c in ("/sys/class/leds/%s_%d" % (nom, k) for k in (1, 2))
            if os.path.isdir(c)]


def ouvrir_manettes():
    """Les fichiers d evenements des manettes de la carte, ouverts sans
    blocage et sans exclusivite : EmulationStation continue de les lire."""
    fds = []
    try:
        with open("/proc/bus/input/devices") as fh:
            blocs = fh.read().split("\n\n")
    except (IOError, OSError):
        return fds
    for bloc in blocs:
        if 'Name="%s' % MANETTES not in bloc:
            continue
        for nom in re.findall(r"(event\d+)", bloc):
            try:
                fds.append(os.open("/dev/input/" + nom, os.O_RDONLY | os.O_NONBLOCK))
            except OSError:
                pass
    return fds


def geste(fds):
    """Vrai si une manette a bouge depuis le dernier passage. Vide la file
    des evenements ; un fichier mort est ferme et retire."""
    vu = False
    for fd in list(fds):
        while True:
            try:
                brut = os.read(fd, FORMAT_EVENEMENT.size * 64)
            except BlockingIOError:
                break
            except OSError:
                os.close(fd)
                fds.remove(fd)
                break
            if not brut:
                break
            for i in range(0, len(brut) - FORMAT_EVENEMENT.size + 1, FORMAT_EVENEMENT.size):
                typ = FORMAT_EVENEMENT.unpack_from(brut, i)[2]
                if typ in (1, 3):          # EV_KEY, EV_ABS : bouton ou stick
                    vu = True
    return vu


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
        self.annexes = chemins_annexes(joueur)
        # La touche hotkey n existe que sur le poste 1. Elle ne sert qu a
        # quelqu un qui est devant la borne : en veille elle s eteint.
        self.hotkey = _leds("aio_hotkey") if joueur == 1 else []
        self.dernier = None          # ce qu on a applique en dernier
        self.derniers_args = None    # pour re-appliquer a une autre intensite
        self.intensite = INTENSITE_MENU
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
        self.derniers_args = (nombre, couleurs, allume)
        voulu = (nombre, tuple(sorted(couleurs.items())), self.intensite) if allume else 0
        if voulu == self.dernier:
            return
        for position, chemins in enumerate(self.boutons):
            numero = ORDRE_BOUTONS[position] if position < len(ORDRE_BOUTONS) else position + 1
            utilise = allume and numero <= nombre
            entree = couleurs.get("BUTTON%d" % numero) or {}
            teinte = entree.get("couleur") or teinte_par_defaut(nombre, numero)
            rvb = entree.get("rvb") or TEINTES.get((teinte or "").strip().lower())
            for chemin in chemins:
                self._memoriser(chemin)
                if utilise and rvb:
                    ecrire(chemin, couleur_pour(chemin, rvb), "multi_intensity")
                else:
                    self._rendre_couleur(chemin)
                ecrire(chemin, self.intensite if utilise else "0")
        for chemin in self.annexes:
            ecrire(chemin, self.intensite if allume else "0")
        self._hotkey()
        self.dernier = voulu

    def _hotkey(self):
        for chemin in self.hotkey:
            ecrire(chemin, PLEIN if self.intensite == PLEIN else "0")

    def reveiller(self, intensite):
        """Change l intensite de ce qui est deja affiche.

        Chemin rapide : on ne touche qu a `brightness`, jamais aux couleurs
        — elles n ont pas change. Une vingtaine d ecritures, quelques
        millisecondes, et l oeil ne voit aucun delai."""
        if intensite == self.intensite:
            return
        ancienne, self.intensite = self.intensite, intensite
        if self.dernier is None:
            return
        for chemins in self.boutons:
            for chemin in chemins:
                if lire_fichier(os.path.join(chemin, "brightness")) not in ("0", None):
                    ecrire(chemin, intensite)
        for chemin in self.annexes:
            if lire_fichier(os.path.join(chemin, "brightness")) not in ("0", None):
                ecrire(chemin, intensite)
        self._hotkey()
        # `dernier` vaut 0 quand le poste est eteint, "repos" quand il est
        # rendu a la carte : seul un triplet porte une intensite.
        if isinstance(self.dernier, tuple):
            self.dernier = self.dernier[:2] + (intensite,)

    def poser_carte(self, couleurs):
        """Repeint le poste comme la carte — les COULEURS seulement.

        Appele juste avant qu une partie commence, pour que le demon des
        credits prenne la main sur des LED aux couleurs d origine et
        retrouve le meme etat en sortant du jeu.

        On ne touche pas a l allumage : le demon des credits decide dans la
        seconde quels boutons servent. Allumer tout ici faisait un eclair —
        tout le panneau s allumait au lancement du jeu avant de revenir aux
        bonnes couleurs."""
        for chemin, rvb in couleurs.items():
            if not chemin.startswith("/sys/class/leds/aio_p%d" % self.joueur) and not (
                    self.joueur == 1 and "hotkey" in chemin):
                continue
            self._memoriser(chemin)
            ecrire(chemin, couleur_pour(chemin, rvb), "multi_intensity")
        self.dernier = None

    def rendre(self):
        """Tout a 255 et couleurs d origine : l etat de repos de la carte."""
        if self.dernier == "repos":
            return
        for chemins in self.boutons:
            for chemin in chemins:
                self._rendre_couleur(chemin)
                ecrire(chemin, self.intensite)
        for chemin in self.annexes:
            ecrire(chemin, self.intensite)
        self._hotkey()
        self.dernier = "repos"


def main():
    boutons = charger_boutons()
    panneaux = {1: Panneau(1), 2: Panneau(2)}
    journal("demarrage — %d jeu(x) avec boutons, %d systeme(s) Recalbox"
            % (len(boutons), len(RECALBOX)))
    derniere_modif = None
    dernier_jeu = None
    base_vue = 0.0
    manettes = ouvrir_manettes()
    manettes_vues = time.time()
    dernier_geste = time.time()
    insister_jusqu = 0.0             # on repeint jusqu a cette heure-la
    intensite = None                 # fixee au premier tour
    journal("%d manette(s) ecoutee(s) pour la veille" % len(manettes))

    while True:
        # Dormir SUR les manettes : un geste rend la main tout de suite,
        # sinon on se reveille au bout de PERIODE pour relire l etat.
        if manettes:
            try:
                select.select(manettes, [], [], PERIODE)
            except (OSError, ValueError):
                manettes = []
        else:
            time.sleep(PERIODE)
        maintenant = time.time()
        # Veille : un geste rallume a fond, le silence tamise.
        if not manettes and maintenant - manettes_vues > 10:
            manettes = ouvrir_manettes()
            manettes_vues = maintenant
        if geste(manettes):
            dernier_geste = maintenant
        voulue = PLEIN if maintenant - dernier_geste < VEILLE_APRES else INTENSITE_MENU
        if voulue != intensite:
            intensite = voulue
            for p in panneaux.values():
                p.reveiller(intensite)
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
        if modif == derniere_modif and maintenant > insister_jusqu:
            continue
        derniere_modif = modif

        etat = lire_etat()
        if not etat:
            continue
        if etat.get("Action") not in AUTOMATIQUES:
            dernier_geste = maintenant       # on a navigue : c est un geste

        # Partie en cours : le demon des credits est maitre des LED.
        if etat.get("State") == "playing" or etat.get("Action") == "rungame":
            # On rend les couleurs d origine AVANT que le demon des credits
            # ne memorise les siennes : sinon il retiendrait nos couleurs
            # comme etant celles de la carte.
            insister_jusqu = maintenant + INSISTER_APRES_JEU
            if dernier_jeu is not None:
                carte = couleurs_de_carte(etat.get("SystemId") or "")
                publier_couleurs_carte(carte)
                for p in panneaux.values():
                    p.intensite = PLEIN
                    p.poser_carte(carte) if carte else p.rendre()
            dernier_jeu = None
            for p in panneaux.values():
                p.dernier = None       # on ne sait plus ce qu il y a dessus
            continue

        systeme = etat.get("SystemId") or ""
        chemin = etat.get("GamePath") or ""
        jeu = os.path.basename(chemin).rsplit(".", 1)[0] if chemin else ""
        if etat.get("IsFolder") == "1":
            jeu = ""

        # D abord la fiche arcade du jeu ; sinon ce que le systeme utilise ;
        # sinon on rend le panneau a la carte.
        fiche = boutons.get(jeu) if jeu else None
        origine = "fiche"
        if not fiche or not fiche.get("nombre"):
            fiche = fiche_de_systeme(systeme)
            origine = "systeme %s%s" % (systeme, "" if systeme in RECALBOX else ", couleur de secours")
        if not fiche:
            for p in panneaux.values():
                p.rendre()
            if (jeu or systeme) != dernier_jeu:
                journal("%s : rien de connu, panneau au repos" % (jeu or systeme))
            dernier_jeu = jeu or systeme
            continue

        nombre = int(fiche["nombre"])
        couleurs = fiche.get("boutons") or {}
        # Le second poste : la fiche arcade le sait ; pour une console,
        # EmulationStation dit combien de joueurs. Sans rien de sur, il
        # reste noir : sur console la plupart des jeux sont a un joueur, et
        # une portable n a jamais de second poste.
        # Sur la liste des systemes (aucun jeu survole), les deux postes
        # s allument aux couleurs du systeme : c est la vitrine de la borne.
        if origine == "fiche":
            deuxieme = int(fiche.get("joueurs") or 1) >= 2
        elif not jeu:
            deuxieme = True
        else:
            deuxieme = bool(joueurs_depuis(etat))
        if systeme in PORTABLES and jeu:
            deuxieme = False
        jeu = jeu or systeme
        if maintenant < insister_jusqu:
            # On sort d une partie : on repeint meme si rien n a change,
            # pour reprendre la main sur le demon des credits.
            for p in panneaux.values():
                p.dernier = None
        panneaux[1].appliquer(nombre, couleurs)
        panneaux[2].appliquer(nombre, fiche.get("boutons_j2") or couleurs, allume=deuxieme)
        if jeu != dernier_jeu:
            journal("%s : %d bouton(s), %d couleur(s), joueur 2 %s [%s]"
                    % (jeu, nombre, sum(1 for v in couleurs.values() if v.get("couleur") or v.get("rvb")),
                       "allume" if deuxieme else "eteint", origine))
        dernier_jeu = jeu


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
