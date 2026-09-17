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
import sys
import time

# Le code partage avec le demon des credits vit a cote, dans le sous-dossier
# userscripts/panneau-allinone/ (les donnees, elles, restent dans
# system/panneau-allinone/) :
#   cablage.py   quelle LED porte quel bouton du jeu, deduit du mappage
#                Recalbox (es_input.cfg), du cablage mesure (cablage.json) et
#                des surcharges .retroarch.cfg des dossiers de roms
#   couleurs.py  palette de secours, teintes nommees, ordre des couleurs
#   reglages.py  les reglages allinone.* de recalbox.conf
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "panneau-allinone"))
import cablage
import couleurs
import reglages
PALETTE_DEFAUT = couleurs.PALETTE_DEFAUT
TEINTES = couleurs.TEINTES
teinte_par_defaut = couleurs.teinte_par_defaut
TABLE = cablage.Cablage()
# Les reglages de recalbox.conf. main() les relie au journal ; en attendant
# (banc d essai qui appelle une fonction seule), aucun reglage n est lu.
REGLAGES = reglages.Reglages(chemin=os.devnull)

ETAT = "/tmp/es_state.inf"
BASE_BOUTONS = "/recalbox/share/system/panneau-allinone/boutons-arcade.json"
# Les corrections apportees a la table de Recalbox d apres les manettes
# d origine : la Game Boy est magenta, la Master System rouge, la N64 n a
# pas de SELECT. Recalbox est juste presque partout ; ce fichier ne dit que
# les exceptions, et il peut ne pas exister.
FICHIER_MANETTES = "/recalbox/share/system/panneau-allinone/manettes-consoles.json"
JOURNAL = "/recalbox/share/system/panneau-allinone/journaux/panneau.log"
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
COULEURS_CARTE = "/recalbox/share/system/panneau-allinone/etat/couleurs-carte.json"
# Notre signe de vie. Tant qu il est frais, le demon des credits sait que le
# menu va repeindre lui-meme et ne rend PAS les couleurs de la carte en
# sortant d une partie : sans cela les deux repeignaient l un apres l autre
# et le joueur voyait un clignotement.
BATTEMENT = "/recalbox/share/system/panneau-allinone/etat/panneau-vivant"
PERIODE_BATTEMENT = 2.0

# La racine des LED. Reglable pour que le banc d essai fabrique un faux
# panneau dans un dossier temporaire et verifie ce qu on y ecrit.
RACINE_LEDS = os.environ.get("PANNEAU_LEDS", "/sys/class/leds")
PLEIN = "255"
# Dans le menu le panneau VEILLE : un geste sur une manette le ranime, et il
# se rendort apres VEILLE_APRES secondes sans rien. Les clips video qui
# defilent tout seuls ne comptent pas comme un geste.
# Deux niveaux, et pas un de plus — choix du proprietaire, qui eteint la
# borne le soir : plein pot des que quelqu un est devant, la moitie quand
# elle se raconte toute seule. L oeil est logarithmique : a 160 sur 255 la
# difference ne se voyait pas, a 128 elle se voit.
# Ce sont les valeurs d origine : allinone.brightness, allinone.brightness.idle
# et allinone.idle.delay, dans recalbox.conf, les remplacent (voir reglages.py).
PRESENT = "255"          # quelqu un navigue
CLIP = "128"             # personne devant depuis VEILLE_APRES secondes
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


# Palette « comme les arcades d origine », pour les jeux dont la base ne
# connait pas les couleurs (1522 sur 1735). Elle n est pas inventee : c est,
# pour chaque nombre de boutons, la palette la plus frequente parmi les 213
# jeux dont arcade-database publie les vraies couleurs d epoque.
#   4 boutons : Rouge Jaune Vert Bleu — le Neo Geo MVS, 8 jeux sur 16
#   6 boutons : Bleu Jaune Rouge x2 — les jeux de combat Capcom, deux rangees
#   3 boutons : egalite Capcom (bleu) / Sega (rouge) — bleu retenu


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


# Les boutons que l EMULATEUR lit vraiment, en noms RetroPad, quand ce ne sont
# pas simplement les N premiers de b, a, y, x, l1, r1. Lu dans le code source
# de chaque coeur le 17/09/2026 (et dans configgen pour les emulateurs hors
# RetroArch). Sans cette table, la GBA allumait Y et X — deux turbos — a la
# place de ses gachettes L et R, et la N64 un bouton qui ne fait rien.
# Les gachettes L2/R2 n existent pas sur le panneau : on ne les compte pas.
BOUTONS_UTILISES = {
    "gba": ("b", "a", "l1", "r1"),          # mgba : X, Y, L2, R2 sont des turbos
    "virtualboy": ("b", "a", "l1", "r1"),   # mednafen_vb : la croix droite est sur L2/R2/L3/R3
    "lynx": ("b", "a", "l1", "r1"),         # handy : L et R = Option 1 et Option 2
    # mupen64plus (configgen/generators/mupen, input.xml) sur un panneau sans
    # stick analogique : A = b, B = y, Z = x, L = l1, R = r1 ; a ne sert a rien.
    "n64": ("b", "y", "x", "l1", "r1"),
    "dreamcast": ("b", "a", "y", "x"),      # flycast : L et R sont C et Z, absents du pad
    "gamecube": ("b", "a", "y", "x", "r1"), # dolphin : R = Z ; L = test Triforce
    "pokemini": ("b", "a", "r1"),           # pokemini : R = C ; X est un turbo
    "jaguar": ("b", "a", "y"),              # virtualjaguar : A, B, C ; le reste est le pave
}


def numeros_utilises(systeme):
    """Les numeros de boutons (1 = b, 2 = a, 3 = y...) que ce systeme lit, ou
    None s il lit simplement les premiers."""
    roles = BOUTONS_UTILISES.get(systeme or "")
    if not roles:
        return None
    numero = {r: n for n, r in cablage.ROLE_DU_BOUTON.items()}
    return [numero[r] for r in roles]


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


def charger_manettes():
    """Les corrections manuelles, en vrai RGB. Absent = rien a corriger."""
    try:
        with open(FICHIER_MANETTES) as fh:
            return (json.load(fh) or {}).get("systemes") or {}
    except (IOError, OSError, ValueError):
        return {}


MANETTES_CONSOLES = charger_manettes()


def teinte_hexa(valeur):
    """« #RRGGBB » vers (r, v, b). None reste None."""
    if not valeur:
        return None
    v = valeur.lstrip("#")
    try:
        return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return None


def facade_de_systeme(systeme, correction):
    """Le START et le SELECT de la manette d origine.

    Recalbox le dit deja : sa table donne onze entrees par systeme, dont la
    neuvieme pour SELECT et la dixieme pour START. Une entree noire veut dire
    que la manette n a pas ce bouton — la Master System et la Game Gear n ont
    pas de SELECT, la Saturn, la Dreamcast et la GameCube non plus.
    manettes-consoles.json peut corriger l un ou l autre : « null » retire le
    bouton, une couleur le repeint.

    Renvoie {"start": ..., "piece": ...} ou chaque valeur vaut None si le
    bouton n existe pas, sinon le triplet a ecrire. « piece » est le nom du
    bouton SELECT sur cette borne : c est le monnayeur.

    Renvoie None pour tout ce qui n est PAS une console : l arcade, mame, les
    systemes que Recalbox ne nomme pas. Sur une borne, le START et le
    monnayeur existent toujours — ce n est pas une manette qui decide. Sans
    cette distinction, un jeu mame eteignait les deux (constate le
    14/09/2026 : panneau entierement noir sur un clip mame)."""
    table = RECALBOX.get(systeme) or []
    if not table:
        return None
    rendu = {}
    # « piece » est notre nom pour le bouton SELECT : sur cette borne, c est le
    # monnayeur. Le fichier de corrections, lui, parle la langue des manettes.
    for nom, cle, rang in (("piece", "select", 8), ("start", "start", 9)):
        rvb = table[rang] if rang < len(table) else None
        garde = rvb if (rvb and any(rvb)) else None
        brut = True
        if cle in correction:
            # « null » explicite : la manette n a pas ce bouton.
            mieux = teinte_hexa(correction.get(cle))
            garde, brut = mieux, False
        rendu[nom] = {"rvb": garde, "brut": brut} if garde else None
    return rendu


def fiche_de_systeme(systeme):
    """Une fiche minimale pour un systeme sans fiche arcade, ou None.

    Les couleurs sont celles que Recalbox donne a ce systeme (la table du
    script d origine) : c est ce que le proprietaire a toujours vu. Notre
    table ne sert qu a borner le NOMBRE de boutons a ceux de la manette
    d origine. Un systeme que Recalbox ne connait pas prend sa couleur de
    secours (astrocity), comme le faisait le script d origine."""
    systeme = systeme or ""
    if not systeme:
        # Aucun systeme : on ne devine pas. Le script Recalbox d origine fait
        # de meme — « if test -z $1; then exit 0 ». Un systeme inconnu, lui,
        # a droit aux couleurs de secours.
        return None
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
        correction = MANETTES_CONSOLES.get(systeme) or {}
        remplace = correction.get("boutons") or []
        allumes = [i for i, rvb in enumerate(boutons, 1) if any(rvb)]
        # Recalbox compte parfois moins de boutons que la manette n en a — la
        # Virtual Boy en a quatre, sa table n en colore que deux. Le fichier
        # de corrections peut donc fixer le nombre, sinon on garde le notre,
        # sinon celui de Recalbox.
        nombre = (correction.get("nombre") or (entree[0] if entree else 0)
                  or (max(allumes) if allumes else 0))
        numeros = numeros_utilises(systeme)
        if numeros:
            nombre = len(numeros)
        if not nombre:
            return None
        utilises = numeros or list(range(1, nombre + 1))

        def palette(table):
            # « brut » : ces triplets viennent du script Recalbox, qui les
            # ecrit tels quels dans les LED. Ils sont donc DEJA dans l ordre
            # du materiel (vert, rouge, bleu) — leur appliquer notre
            # correction les retournerait. Verifie le 14/09/2026 : la nes et
            # la gb valent « 00 FF 00 », ce qui allume du ROUGE sur cette
            # carte, la couleur de leurs vrais boutons ; et la table snes
            # rend alors jaune, rouge, vert, bleu — les boutons B, A, Y, X.
            # Une couleur venue de manettes-consoles.json, elle, est ecrite
            # en vrai RGB : elle passe par la correction, donc pas « brut ».
            """La palette des boutons, en dictionnaire BUTTONn -> couleur."""
            rendu = {}
            # La k-ieme couleur corrigee va au k-ieme bouton utilise : pour la
            # GBA, « A B L R » et non « A B Y X ».
            for k, i in enumerate(utilises):
                mieux = teinte_hexa(remplace[k]) if k < len(remplace) else None
                if mieux:
                    rendu["BUTTON%d" % i] = {"rvb": mieux}
                elif i - 1 < len(table) and any(table[i - 1]):
                    rendu["BUTTON%d" % i] = {"rvb": table[i - 1], "brut": True}
            return rendu
        fiche = {"nombre": nombre, "boutons": palette(boutons), "numeros": numeros}
        if secours:
            fiche["boutons_j2"] = palette(secours)
        fiche["facade"] = facade_de_systeme(systeme, correction)
        return fiche
    if not entree:
        return None
    nombre, palette = entree
    couleurs = {}
    if palette:
        for i, teinte in enumerate(palette[:nombre], 1):
            couleurs["BUTTON%d" % i] = {"couleur": teinte}
    return {"nombre": nombre, "boutons": couleurs, "numeros": numeros_utilises(systeme)}


def joueurs_depuis(etat):
    """Le champ Players de EmulationStation : « 1 », « 2 », « 1-2 », « 1-4 »…
    Vrai si un second joueur peut jouer. None si le champ est absent."""
    texte = (etat or {}).get("Players") or ""
    nombres = [int(x) for x in re.findall(r"\d+", texte)]
    if not nombres:
        return None
    return max(nombres) >= 2


def lire_fichier(chemin):
    """Le contenu d un fichier sans ses espaces autour, ou None s il n est pas
    lisible. C est ainsi qu on lit une LED ou l etat d EmulationStation."""
    try:
        with open(chemin) as fh:
            return fh.read().strip()
    except (IOError, OSError):
        return None


# Le pilote d origine MENT sur l ordre de ses composantes. multi_index
# annonce « red green blue », mais les WS2812B de cette carte sont cablees
# vert, rouge, bleu. Mesure faite le 12/09/2026 sur la borne : ecrire
# « 255 0 0 » sur le bouton 1 et « 0 255 0 » sur le bouton 2 allume le
# premier en VERT et le second en ROUGE (photo a l appui). couleurs.py
# connait ce mensonge et croit un pilote corrige (« green red blue ») : le
# demon des credits lit le meme ordre, les deux programmes peignent pareil.
ORDRE_MATERIEL = couleurs.ordre_materiel(os.path.join(RACINE_LEDS, "aio_p1_b1_1"))


def couleur_pour(chemin_led, rvb, brut=False):
    """La couleur telle que la carte l allume vraiment.

    `brut` : le triplet est DEJA dans l ordre du materiel. C est le cas de
    tout ce qui vient de la table de Recalbox, que son propre script ecrit
    tel quel dans les LED ; y appliquer la correction le retournerait. Nos
    fiches d arcade et manettes-consoles.json, eux, sont en vrai RGB."""
    if brut:
        return " ".join(str(x) for x in rvb)
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
    # L ordre est celui du script Recalbox lui-meme, pas de notre cablage :
    # ses LED 1 a 8 recoivent les entrees 3,4,5,1,2,6,7,8 de sa table — la
    # couleur du bouton 1 va la ou Recalbox met le bouton 1, en bas a gauche.
    # Un systeme aligne par aligner-boutons.py a son bouton N a la position N :
    # sa couleur aussi. Sans cela, sur la Game Boy alignee (17/09/2026), les
    # LED 1 et 2 s allumaient avec la couleur de la position 3 : du noir.
    ordre = [3, 4, 5, 1, 2, 6, 7, 8]
    if TABLE.surcharge_systeme(systeme or ""):
        ordre = [1, 2, 3, 4, 5, 6, 7, 8]
    for joueur in (1, 2):
        table = connue or RECALBOX.get("astrocityp%d" % joueur) or []
        if not table:
            continue
        for place, numero in enumerate(ordre, 1):
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


def battre(derniere):
    """Touche le fichier de presence, au plus une fois toutes les deux
    secondes. Renvoie l heure du dernier battement."""
    maintenant = time.time()
    if maintenant - derniere < PERIODE_BATTEMENT:
        return derniere
    try:
        with open(BATTEMENT, "w") as fh:
            fh.write("%d\n" % os.getpid())
    except OSError:
        pass
    return maintenant


def preparer_dossiers():
    """Les sous-dossiers ou l'on ecrit, s'ils manquent (premiere installation)."""
    for chemin in (JOURNAL, COULEURS_CARTE):
        try:
            os.makedirs(os.path.dirname(chemin), exist_ok=True)
        except OSError:
            pass


def journal(msg):
    """Une ligne datee dans le journal du panneau ; un journal illisible n arrete
    jamais le programme."""
    try:
        with open(JOURNAL, "a") as fh:
            fh.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def decider(etat, boutons):
    """Ce que le panneau doit montrer pour cet etat du frontend.

    Toutes les regles d eclairage sont ici, en un seul endroit, pour qu on
    puisse les verifier sans carte ni borne : voir outils/tests/test_panneau.py.

    Renvoie le jeu et le systeme reconnus, la fiche retenue, d ou elle
    vient, le nombre de boutons, leurs couleurs (et celles du poste 2), et
    si le second poste doit s allumer."""
    vide = {"nombre": 0, "couleurs": {}, "couleurs_j2": {}, "deuxieme": False}
    systeme = (etat or {}).get("SystemId") or ""
    chemin = (etat or {}).get("GamePath") or ""
    jeu = os.path.basename(chemin).rsplit(".", 1)[0] if chemin else ""
    if (etat or {}).get("IsFolder") == "1":
        jeu = ""

    # D abord la fiche arcade du jeu ; sinon ce que le systeme utilise.
    fiche = boutons.get(jeu) if jeu else None
    origine = "fiche"
    if not fiche or not fiche.get("nombre"):
        fiche = fiche_de_systeme(systeme)
        origine = "systeme %s%s" % (systeme, "" if systeme in RECALBOX else ", couleur de secours")
    if not fiche:
        vide.update({"systeme": systeme, "jeu": jeu, "fiche": None, "origine": origine})
        return vide

    # Le second poste. La fiche arcade sait combien de joueurs ; pour une
    # console, EmulationStation le dit, et sans rien de sur il reste noir.
    # Sur la liste des systemes, les deux postes s allument : c est la
    # vitrine de la borne. Une portable n a jamais de second poste.
    if origine == "fiche":
        deuxieme = int(fiche.get("joueurs") or 1) >= 2
    elif not jeu:
        deuxieme = True
    else:
        deuxieme = bool(joueurs_depuis(etat))
    if systeme in PORTABLES and jeu:
        deuxieme = False
    return {"systeme": systeme, "jeu": jeu, "fiche": fiche, "origine": origine,
            "nombre": int(fiche["nombre"]), "couleurs": fiche.get("boutons") or {},
            "couleurs_j2": fiche.get("boutons_j2") or fiche.get("boutons") or {},
            "facade": fiche.get("facade"), "numeros": fiche.get("numeros"),
            "deuxieme": deuxieme}


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
    """La base des boutons d arcade (boutons-arcade.json), indexee par nom de set
    ; vide si elle manque ou est illisible."""
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
            chemin = os.path.join(RACINE_LEDS, "aio_p%d_b%d_%d" % (joueur, n, k))
            if os.path.isdir(chemin):
                paire.append(chemin)
        paires.append(paire)
    return paires


# Le nom que le pilote donne aux LED et le cablage du panneau ne concordent
# pas sur cette borne : les LED appelees « start » eclairent le bouton
# PIECE, et inversement. C est le meme constat que dans
# credits(permanent).py ; si un jour la carte change, ces deux lignes sont
# le seul endroit a echanger.
LED_PIECE = "aio_p%d_start"
LED_START = "aio_p%d_select"


def chemins_annexes(joueur):
    """Les LED de piece et de start du poste, dans cet ordre."""
    return _leds(LED_PIECE % joueur), _leds(LED_START % joueur)


def _leds(nom):
    """Les chemins des deux LED d un bouton (« _1 » et « _2 ») qui existent
    vraiment dans /sys/class/leds."""
    return [c for c in (os.path.join(RACINE_LEDS, "%s_%d" % (nom, k)) for k in (1, 2))
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
    """Ecrit une valeur dans un fichier d une LED, brightness par defaut. Une LED
    absente ou en erreur est ignoree : le panneau ne doit jamais s arreter
    pour une LED."""
    try:
        with open(os.path.join(chemin, fichier), "w") as fh:
            fh.write(valeur)
    except (IOError, OSError):
        pass


class Panneau:
    """Un poste de jeu : ses boutons, son START, sa PIECE et, pour le poste 1, la
    touche hotkey. Il retient ce qu il a applique en dernier pour ne rien
    reecrire sans raison, et la couleur que la carte avait posee sur chaque
    LED pour la lui rendre."""
    def __init__(self, joueur):
        self.joueur = joueur
        self.boutons = chemins_led(joueur)
        self.piece, self.start = chemins_annexes(joueur)
        # La touche hotkey n existe que sur le poste 1. Elle ne sert qu a
        # quelqu un qui est devant la borne : en veille elle s eteint.
        self.hotkey = _leds("aio_hotkey") if joueur == 1 else []
        self.present = True          # quelqu un est-il devant la borne ?
        self.dernier = None          # ce qu on a applique en dernier
        self.facade = None           # START/SELECT de la manette d origine
        self.systeme = ""            # le systeme montre : la place des boutons en depend
        self.en_jeu = False          # en partie, RetroArch dit ou sont les boutons
        self.intensite = PRESENT
        self.origine = {}            # couleur posee par la carte, par led

    def _memoriser(self, chemin):
        """Retient la couleur que la LED avait avant qu on y touche, une seule
        fois par LED."""
        if chemin not in self.origine:
            valeur = lire_fichier(os.path.join(chemin, "multi_intensity"))
            if valeur:
                self.origine[chemin] = valeur

    def _rendre_couleur(self, chemin):
        """Remet a la LED la couleur memorisee, si on en a une."""
        if chemin in self.origine:
            ecrire(chemin, self.origine[chemin], "multi_intensity")

    def appliquer(self, nombre, couleurs, allume=True, facade=None, systeme="", en_jeu=False,
                  numeros=None):
        """Allume les `nombre` premiers boutons logiques, eteint le reste,
        et pose la couleur d origine de chacun quand la base la connait.

        `facade` dit ce que la manette d origine possede comme START et
        SELECT ; None (un jeu d arcade) garde la regle de la borne.
        `systeme` et `en_jeu` disent OU sont les boutons : Recalbox ne les
        place pas pareil sous MAME et sous FBNeo (voir cablage.py)."""
        self.facade, self.systeme, self.en_jeu = facade, systeme, en_jeu
        voulu = (nombre, tuple(sorted(couleurs.items())), self.intensite,
                 tuple(sorted((facade or {}).items())), systeme, en_jeu,
                 tuple(numeros or ())) if allume else 0
        if voulu == self.dernier:
            return
        for position, chemins in enumerate(self.boutons):
            numero = TABLE.bouton_de_led(self.joueur, position + 1, self.systeme, self.en_jeu)
            # `numeros` : les boutons que l emulateur lit vraiment (voir
            # BOUTONS_UTILISES) ; sinon les `nombre` premiers.
            utilise = allume and numero is not None and (
                numero in numeros if numeros else numero <= nombre)
            entree = couleurs.get("BUTTON%d" % numero) or {}
            teinte = entree.get("couleur") or teinte_par_defaut(nombre, numero)
            rvb = entree.get("rvb") or TEINTES.get((teinte or "").strip().lower())
            for chemin in chemins:
                self._memoriser(chemin)
                if utilise and rvb:
                    ecrire(chemin, couleur_pour(chemin, rvb, entree.get("brut")),
                           "multi_intensity")
                else:
                    self._rendre_couleur(chemin)
                ecrire(chemin, self.intensite if utilise else "0")
        self._annexes(allume)
        self.dernier = voulu

    def _annexes(self, allume):
        """Les boutons de facade : piece, start et hotkey.

        Choix du proprietaire de la borne : en mode clip, le START ne
        s allume que sur les postes qui servent au jeu montre — un jeu a un
        seul joueur laisse donc le poste 2 noir. Sur un jeu d arcade, la
        PIECE et la touche hotkey restent eteintes tant que personne n est
        devant : elles ne servent a rien pendant les clips. Sur une console,
        ce bouton est le SELECT de la manette : il s allume avec les autres.
        Un geste rallume tout."""
        # Le START suit la regle du jeu, en clip comme devant quelqu un : un
        # jeu solo n allume que le poste 1, un jeu a deux allume les deux.
        # Le second bouton, lui, change de nature avec le jeu : monnayeur sur
        # une borne — inutile tant que personne n est devant — mais SELECT de
        # la manette sur une console, et alors bouton de jeu comme les autres.
        facade = self.facade
        arcade = facade is None
        self._un_annexe(self.start, None if arcade else facade.get("start"), allume)
        self._un_annexe(self.piece, None if arcade else facade.get("piece"),
                        allume and (self.present or not arcade))
        self._hotkey()

    def _un_annexe(self, chemins, bouton, allumee):
        """Un bouton de facade — START ou PIECE — sur les deux LED du poste.

        Jeu d arcade (`self.facade` a None) : la borne decide, la couleur ne
        bouge pas. Console : `bouton` a None veut dire que la manette
        d origine n a pas ce bouton, et la LED reste noire meme devant
        quelqu un."""
        for chemin in chemins:
            if self.facade is not None and not bouton:
                ecrire(chemin, "0")
                continue
            if bouton and bouton.get("rvb"):
                self._memoriser(chemin)
                ecrire(chemin, couleur_pour(chemin, bouton["rvb"], bouton.get("brut")),
                       "multi_intensity")
            ecrire(chemin, self.intensite if allumee else "0")

    def _hotkey(self):
        """La touche hotkey ne sert qu a quelqu un qui joue : elle reste
        noire tant que personne n a touche la borne, meme en plein jour ou
        pendant les clips video, ou elle n eclairerait rien d utile."""
        for chemin in self.hotkey:
            ecrire(chemin, self.intensite if self.present else "0")

    def presence(self, quelqu_un):
        """Dit au poste si quelqu un est devant la borne : le start et la
        touche hotkey s allument avec lui, la piece reste."""
        if quelqu_un != self.present:
            self.present = quelqu_un
            if self.dernier is not None:
                self._annexes(self.dernier != 0)
            else:
                self._hotkey()

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
        for chemin in self.piece + self.start:
            if lire_fichier(os.path.join(chemin, "brightness")) not in ("0", None):
                ecrire(chemin, intensite)
        self._hotkey()
        # `dernier` vaut 0 quand le poste est eteint, "repos" quand il est
        # rendu a la carte : seul un triplet porte une intensite.
        if isinstance(self.dernier, tuple):
            self.dernier = self.dernier[:2] + (intensite,) + self.dernier[3:]

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
            if not os.path.basename(chemin).startswith("aio_p%d" % self.joueur) and not (
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
        self._annexes(True)
        self.dernier = "repos"


def luminosite(present):
    """L intensite du panneau, devant quelqu un ou en veille, telle que
    recalbox.conf la regle."""
    if present:
        return str(REGLAGES.get("allinone.brightness", int(PRESENT)))
    return str(REGLAGES.get("allinone.brightness.idle", int(CLIP)))


def main():
    global REGLAGES
    preparer_dossiers()
    REGLAGES = reglages.Reglages(journal)
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
    # Pendant une partie, ce programme se TAIT completement. Il ne suffit
    # pas de ne plus choisir les couleurs : tant qu il ajustait encore
    # l intensite ou la touche hotkey, ses ecritures se melaient aux
    # clignotements du demon des credits et cela se voyait a l ecran.
    en_partie = False
    battement = 0.0
    intensite = None                 # fixee au premier tour
    journal("tables du panneau : %s" % TABLE.source)
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
        battement = battre(battement)
        # Veille : un geste rallume a fond, le silence tamise.
        if not manettes and maintenant - manettes_vues > 10:
            manettes = ouvrir_manettes()
            manettes_vues = maintenant
        if geste(manettes):
            dernier_geste = maintenant
        # Au repos : pleine puissance tant qu il fait jour, tamise la nuit.
        if not en_partie:
            if REGLAGES.rafraichir():
                # Le poste 2 a pu etre active ou coupe : on repeint.
                for p in panneaux.values():
                    p.dernier = None
            if TABLE.rafraichir():
                # Une manette vient d etre reconfiguree : on repeint tout de
                # suite avec les nouveaux roles, sans attendre un changement
                # de jeu.
                journal("tables relues : %s" % TABLE.source)
                for p in panneaux.values():
                    p.dernier = None
            present = (maintenant - dernier_geste
                       < REGLAGES.get("allinone.idle.delay", VEILLE_APRES))
            for p in panneaux.values():
                p.presence(present)
            voulue = luminosite(present)
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
        # EmulationStation reecrit ce fichier en place : on tombe parfois au
        # milieu et il manque des lignes. Un etat sans « Action » ne prouve
        # rien — surtout pas qu on a quitte la partie. Constate le
        # 14/09/2026 : six bascules dans la meme seconde, le panneau et le
        # demon des credits se disputaient les LED, et cela se voyait.
        if not etat or "Action" not in etat:
            continue
        if etat.get("Action") not in AUTOMATIQUES:
            dernier_geste = maintenant       # on a navigue : c est un geste

        # Partie en cours : le demon des credits est seul maitre des LED.
        # On n y touche plus du tout tant qu elle dure — deux programmes qui
        # ecrivent les memes LED dix fois par seconde, cela saccade.
        etait_en_partie = en_partie
        en_partie = (etat.get("State") == "playing"
                     or etat.get("Action") == "rungame")
        if en_partie:
            if not etait_en_partie:
                # On entre : on rend les couleurs d origine AVANT que le
                # demon des credits ne memorise les siennes, sinon il
                # retiendrait les notres comme etant celles de la carte.
                carte = couleurs_de_carte(etat.get("SystemId") or "")
                publier_couleurs_carte(carte)
                # Une console : le demon des credits ne s en occupe pas, et la
                # table de Recalbox ne connait que ses propres couleurs — elle
                # repeignait en noir les gachettes L et R de la GBA. On garde
                # donc ce que le menu montrait pour ce jeu : les boutons que
                # l emulateur lit, dans leurs couleurs, a pleine intensite.
                console = decider(etat, boutons)
                console = console if str(console.get("origine", "")).startswith("systeme") \
                    and console.get("fiche") else None
                for p in panneaux.values():
                    p.intensite = str(REGLAGES.get("allinone.brightness", int(PLEIN)))
                    p.present = True   # pour ne pas toucher HK en revenant
                    if console:
                        deux = console["deuxieme"] and REGLAGES.get("allinone.player2.enabled", True)
                        p.appliquer(console["nombre"],
                                    console["couleurs"] if p.joueur == 1 else console["couleurs_j2"],
                                    allume=(p.joueur == 1 or deux), facade=console.get("facade"),
                                    systeme=console["systeme"], numeros=console.get("numeros"))
                    else:
                        p.poser_carte(carte) if carte else p.rendre()
                    p.dernier = None   # on ne sait plus ce qu il y a dessus
                dernier_jeu = None
            continue
        if etait_en_partie:
            # On vient de sortir : on repeint quelques secondes meme si rien
            # ne change, le temps de reprendre la main sur les credits.
            insister_jusqu = maintenant + INSISTER_APRES_JEU

        decision = decider(etat, boutons)
        systeme, jeu = decision["systeme"], decision["jeu"]
        origine = decision["origine"]
        if not decision["fiche"]:
            for p in panneaux.values():
                p.rendre()
            if (jeu or systeme) != dernier_jeu:
                journal("%s : rien de connu, panneau au repos" % (jeu or systeme))
            dernier_jeu = jeu or systeme
            continue

        nombre, couleurs = decision["nombre"], decision["couleurs"]
        # Une borne a un seul poste le dit dans recalbox.conf.
        deuxieme = decision["deuxieme"] and REGLAGES.get("allinone.player2.enabled", True)
        jeu = jeu or systeme
        if maintenant < insister_jusqu:
            # On sort d une partie : on repeint meme si rien n a change,
            # pour reprendre la main sur le demon des credits.
            for p in panneaux.values():
                p.dernier = None
        facade = decision.get("facade")
        en_jeu = etat.get("Action") == "rungame"
        numeros = decision.get("numeros")
        panneaux[1].appliquer(nombre, couleurs, facade=facade, systeme=systeme, en_jeu=en_jeu,
                              numeros=numeros)
        panneaux[2].appliquer(nombre, decision["couleurs_j2"], allume=deuxieme, numeros=numeros,
                              facade=facade, systeme=systeme, en_jeu=en_jeu)
        if jeu != dernier_jeu:
            journal("%s : %d bouton(s), %d couleur(s), joueur 2 %s [%s]"
                    % (jeu, nombre, sum(1 for v in couleurs.values() if v.get("couleur") or v.get("rvb")),
                       "allume" if deuxieme else "eteint", origine))
            # En partie, RetroArch a le dernier mot : si Recalbox a place les
            # boutons autrement que sa regle, on le note — c est le signe
            # d un remap par jeu, ou d une regle qui a change.
            ecart = TABLE.ecart_retroarch(1, systeme) if en_jeu else []
            if ecart:
                journal("%s : RetroArch place les boutons autrement que la regle (%s)" % (jeu, "; ".join(ecart)))
        dernier_jeu = jeu


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
