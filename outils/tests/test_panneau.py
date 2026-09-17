#!/usr/bin/env python3
"""Banc d essai du panneau lumineux — sans carte, sans borne, sans ecran.

Chaque demande du proprietaire de la borne est verifiee ici, une par une.
On fabrique un faux panneau de LED dans un dossier temporaire, on donne au
programme l etat qu EmulationStation ecrirait, et on lit ce qui a ete
ecrit dans les fichiers.

    python3 outils/tests/test_panneau.py

Aucune dependance : bibliotheque standard uniquement.
"""

import importlib.machinery
import os
import shutil
import sys
import tempfile
import time

# Le programme est dans borne/share/userscripts/, la copie exacte de la borne.
RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROGRAMME = os.path.join(RACINE, "borne", "share", "userscripts", "panneau(permanent).py")

BOUTONS = ["aio_p%d_b%d" % (j, n) for j in (1, 2) for n in range(1, 7)]
ANNEXES = ["aio_p%d_%s" % (j, k) for j in (1, 2) for k in ("start", "select")] + ["aio_hotkey"]

essais = []


def essai(nom):
    """Decorateur qui inscrit une fonction au banc d essai sous un nom lisible."""
    def decorateur(fonction):
        essais.append((nom, fonction))
        return fonction
    return decorateur


def faux_panneau(dossier):
    """Un panneau de LED en dossiers et fichiers, comme le noyau l expose."""
    for nom in BOUTONS + ANNEXES:
        for k in (1, 2):
            chemin = os.path.join(dossier, "%s_%d" % (nom, k))
            os.makedirs(chemin, exist_ok=True)
            with open(os.path.join(chemin, "brightness"), "w") as fh:
                fh.write("255")
            with open(os.path.join(chemin, "multi_intensity"), "w") as fh:
                fh.write("0 0 0")
            with open(os.path.join(chemin, "multi_index"), "w") as fh:
                fh.write("red green blue")


def charger(dossier, palette):
    """Charge le programme avec un faux panneau et une fausse palette."""
    os.environ["PANNEAU_LEDS"] = dossier
    source = open(PROGRAMME).read().split("def main():")[0]
    source = source.replace('PALETTE_RECALBOX = "/recalbox/scripts/recalbox_allinone_rgb.sh"',
                            'PALETTE_RECALBOX = %r' % palette)
    espace = {"__name__": "panneau_essai", "__file__": PROGRAMME}   # pour trouver cablage.py a cote
    exec(compile(source, PROGRAMME, "exec"), espace)
    return espace


def palette_factice(chemin):
    """Quelques systemes et le secours, dans la forme du script Recalbox."""
    with open(chemin, "w") as fh:
        fh.write('declare -a nes=("0x00 0xFF 0x00" "0x00 0xFF 0x00" "0x00 0x00 0x00" '
                 '"0x00 0x00 0x00" "0x00 0x00 0x00" "0x00 0x00 0x00" "0x00 0x00 0x00" '
                 '"0x00 0x00 0x00" "0xAA 0xAA 0xAA" "0xAA 0xAA 0xAA" "0xFF 0xFF 0xFF")\n')
        fh.write('declare -a gb=("0x00 0xFF 0x00" "0x00 0xFF 0x00" "0x00 0x00 0x00" '
                 '"0x00 0x00 0x00" "0x00 0x00 0x00" "0x00 0x00 0x00" "0x00 0x00 0x00" '
                 '"0x00 0x00 0x00" "0xAA 0xAA 0xAA" "0xAA 0xAA 0xAA" "0xFF 0xFF 0xFF")\n')
        # La Master System : deux boutons, un START, et PAS de SELECT — sa 9e
        # entree est noire. C est ce qui permet d essayer la regle de facade.
        fh.write('declare -a mastersystem=("0xAA 0xAA 0xAA" "0xAA 0xAA 0xAA" "0x00 0x00 0x00" '
                 '"0x00 0x00 0x00" "0x00 0x00 0x00" "0x00 0x00 0x00" "0x00 0x00 0x00" '
                 '"0x00 0x00 0x00" "0x00 0x00 0x00" "0xAA 0xAA 0xAA" "0xFF 0xFF 0xFF")\n')
        # La Super Nintendo : quatre boutons colores, deux gachettes, et les
        # deux boutons de facade.
        fh.write('declare -a snes=("0xFF 0xFF 0x00" "0x00 0xFF 0x00" "0x80 0x00 0x00" '
                 '"0x00 0x00 0xFF" "0xAA 0xAA 0xAA" "0xAA 0xAA 0xAA" "0x00 0x00 0x00" '
                 '"0x00 0x00 0x00" "0xAA 0xAA 0xAA" "0xAA 0xAA 0xAA" "0xFF 0xFF 0xFF")\n')
        fh.write('declare -a astrocityp1=("0xFF 0x00 0x00" "0xFF 0x00 0x00" "0xFF 0x00 0x00" '
                 '"0xFF 0x00 0x00" "0xFF 0x00 0x00" "0xFF 0x00 0x00" "0x00 0x00 0x00" '
                 '"0x00 0x00 0x00" "0xFF 0xFF 0x00" "0xFF 0xFF 0x00" "0x00 0x00 0xFF")\n')
        fh.write('declare -a astrocityp2=("0x00 0x80 0x80" "0x00 0x80 0x80" "0x00 0x80 0x80" '
                 '"0x00 0x80 0x80" "0x00 0x80 0x80" "0x00 0x80 0x80" "0x00 0x00 0x00" '
                 '"0x00 0x00 0x00" "0xFF 0xFF 0x00" "0xFF 0xFF 0x00" "0x00 0x80 0x80")\n')


def lire(dossier, nom, fichier="brightness"):
    """La valeur d un fichier d une LED du faux panneau ; « _1 » suffit, les deux
    LED d un bouton recoivent la meme chose."""
    with open(os.path.join(dossier, nom + "_1", fichier)) as fh:
        return fh.read().strip()


def allumes(dossier, joueur):
    """Les numeros LOGIQUES des boutons allumes sur ce poste."""
    espace_ordre = [3, 4, 5, 1, 2, 6]
    vus = []
    for place in range(1, 7):
        if lire(dossier, "aio_p%d_b%d" % (joueur, place)) != "0":
            vus.append(espace_ordre[place - 1])
    return sorted(vus)


# --- les essais ---------------------------------------------------------------

@essai("un jeu a un joueur n allume que ses boutons, poste 2 eteint")
def _(dossier, espace):
    boutons = {"dkong": {"nombre": 1, "joueurs": 1, "boutons": {"BUTTON1": {"couleur": "red"}}}}
    etat = {"SystemId": "fbneo", "GamePath": "/roms/fbneo/dkong.zip", "Players": "1"}
    d = espace["decider"](etat, boutons)
    assert d["nombre"] == 1, d
    assert d["deuxieme"] is False, d
    p1, p2 = espace["Panneau"](1), espace["Panneau"](2)
    p1.appliquer(d["nombre"], d["couleurs"])
    p2.appliquer(d["nombre"], d["couleurs_j2"], allume=d["deuxieme"])
    assert allumes(dossier, 1) == [1], allumes(dossier, 1)
    assert allumes(dossier, 2) == [], allumes(dossier, 2)


@essai("un jeu a un joueur eteint aussi la piece et le start du poste 2")
def _(dossier, espace):
    boutons = {"dkong": {"nombre": 1, "joueurs": 1, "boutons": {}}}
    etat = {"SystemId": "fbneo", "GamePath": "/roms/fbneo/dkong.zip"}
    d = espace["decider"](etat, boutons)
    espace["Panneau"](2).appliquer(d["nombre"], d["couleurs_j2"], allume=d["deuxieme"])
    assert lire(dossier, "aio_p2_start") == "0"
    assert lire(dossier, "aio_p2_select") == "0"


@essai("un jeu a deux joueurs allume les MEMES boutons des deux cotes")
def _(dossier, espace):
    boutons = {"sf2": {"nombre": 6, "joueurs": 2, "boutons": {}}}
    etat = {"SystemId": "fbneo", "GamePath": "/roms/fbneo/sf2.zip"}
    d = espace["decider"](etat, boutons)
    assert d["deuxieme"] is True
    espace["Panneau"](1).appliquer(d["nombre"], d["couleurs"])
    espace["Panneau"](2).appliquer(d["nombre"], d["couleurs_j2"], allume=True)
    assert allumes(dossier, 1) == allumes(dossier, 2) == [1, 2, 3, 4, 5, 6]


@essai("une console garde la table de Recalbox telle quelle (NES = rouge)")
def _(dossier, espace):
    etat = {"SystemId": "nes", "GamePath": "/roms/nes/mario.nes", "Players": "1-2"}
    d = espace["decider"](etat, {})
    assert d["nombre"] == 2, d["nombre"]
    espace["Panneau"](1).appliquer(d["nombre"], d["couleurs"], facade=d["facade"])
    # La table de Recalbox est DEJA dans l ordre du materiel : son « 00 FF 00 »
    # part tel quel et allume du ROUGE, la couleur des boutons d une NES. Lui
    # appliquer notre correction vert/rouge donnerait du vert : c est le defaut
    # corrige le 14/09/2026.
    assert lire(dossier, "aio_p1_b4", "multi_intensity") == "0 255 0"


@essai("une portable laisse le poste 2 eteint meme a deux joueurs annonces")
def _(dossier, espace):
    etat = {"SystemId": "gb", "GamePath": "/roms/gb/tetris.gb", "Players": "1-2"}
    d = espace["decider"](etat, {})
    assert d["deuxieme"] is False, d


@essai("sur la liste des systemes, les deux postes s allument")
def _(dossier, espace):
    etat = {"SystemId": "nes", "GamePath": "", "Players": ""}
    d = espace["decider"](etat, {})
    assert d["deuxieme"] is True, d


@essai("un systeme inconnu de Recalbox prend la couleur de secours, pas le repos")
def _(dossier, espace):
    etat = {"SystemId": "arcade-capcom", "GamePath": ""}
    d = espace["decider"](etat, {})
    assert d["fiche"] is not None, d
    assert d["nombre"] == 6, d["nombre"]


@essai("les couleurs de la carte sont publiees pour le demon des credits")
def _(dossier, espace):
    couleurs = espace["couleurs_de_carte"]("nes")
    assert couleurs, "aucune couleur de carte"
    espace["publier_couleurs_carte"](couleurs)
    assert os.path.exists(espace["COULEURS_CARTE"])


@essai("systeme aligne (gb) : la couleur du bouton N va sur la LED N, pas sur l ordre Recalbox")
def _(dossier, espace):
    import tempfile
    roms = tempfile.mkdtemp()
    os.makedirs(os.path.join(roms, "gb"))
    with open(os.path.join(roms, "gb", ".retroarch.cfg"), "w") as fh:
        fh.write('input_player1_b_btn = "0"\ninput_player1_a_btn = "1"\n')
    table = espace["TABLE"]
    ancien = table._surcharge_systeme
    table._surcharge_systeme = os.path.join(roms, "%s", ".retroarch.cfg")
    try:
        gb = espace["couleurs_de_carte"]("gb")
        nes = espace["couleurs_de_carte"]("nes")      # pas de surcharge : ordre Recalbox
    finally:
        table._surcharge_systeme = ancien
    led = lambda couleurs, n: couleurs[os.path.join(dossier, "aio_p1_b%d_1" % n)]
    assert led(gb, 1) == (0, 255, 0) and led(gb, 2) == (0, 255, 0), "gb : LED 1 et 2 noires"
    assert led(gb, 4) == (0, 0, 0), "gb : la LED 4 garde une couleur de bouton"
    assert led(nes, 4) == (0, 255, 0) and led(nes, 1) == (0, 0, 0), "nes : ordre Recalbox perdu"


@essai("GBA : les LED des boutons que mgba lit (B A L R), pas Y et X qui sont des turbos")
def _(dossier, espace):
    d = espace["decider"]({"SystemId": "gba", "GamePath": "/r/gba/Metroid.zip"}, {})
    assert d["numeros"] == [1, 2, 5, 6], d["numeros"]
    p = espace["Panneau"](1)
    p.appliquer(d["nombre"], d["couleurs"], facade=d["facade"], systeme="gba", numeros=d["numeros"])
    allumees = [n for n in range(1, 7) if lire(dossier, "aio_p1_b%d" % n) != "0"]
    # arcade6 : Recalbox met b sur la LED 4, a sur la 5, l1 sur la 3, r1 sur la 6
    assert allumees == [3, 4, 5, 6], allumees


@essai("N64 : le bouton que mupen ne lit pas (a) reste eteint")
def _(dossier, espace):
    d = espace["decider"]({"SystemId": "n64", "GamePath": "/r/n64/Mario.z64"}, {})
    p = espace["Panneau"](1)
    p.appliquer(d["nombre"], d["couleurs"], facade=d["facade"], systeme="n64", numeros=d["numeros"])
    allumees = [n for n in range(1, 7) if lire(dossier, "aio_p1_b%d" % n) != "0"]
    assert allumees == [1, 2, 3, 4, 6], allumees


@essai("une console sans liste particuliere garde ses N premiers boutons (snes : 6)")
def _(dossier, espace):
    d = espace["decider"]({"SystemId": "snes", "GamePath": "/r/snes/Mario.zip"}, {})
    assert d["numeros"] is None and d["nombre"] == 6


@essai("poser la carte ne touche QUE les couleurs, jamais l allumage")
def _(dossier, espace):
    for j in (1, 2):
        for n in range(1, 7):
            with open(os.path.join(dossier, "aio_p%d_b%d_1" % (j, n), "brightness"), "w") as fh:
                fh.write("7")
    p = espace["Panneau"](1)
    p.poser_carte(espace["couleurs_de_carte"]("nes"))
    assert lire(dossier, "aio_p1_b1") == "7", "l allumage a ete touche"


@essai("en mode clip, le start reste allume, la piece et HK s eteignent")
def _(dossier, espace):
    p = espace["Panneau"](1)
    p.presence(True)
    p.appliquer(2, {})
    assert lire(dossier, "aio_p1_select") != "0", "le start devrait etre allume"
    assert lire(dossier, "aio_p1_start") != "0", "la piece devrait etre allumee"
    assert lire(dossier, "aio_hotkey") != "0", "HK devrait etre allume"
    p.presence(False)
    assert lire(dossier, "aio_p1_select") != "0", "le start doit rester en mode clip"
    assert lire(dossier, "aio_p1_start") == "0", "la piece doit s eteindre en mode clip"
    assert lire(dossier, "aio_hotkey") == "0", "HK doit s eteindre en mode clip"
    assert lire(dossier, "aio_p1_b4") != "0", "les boutons de jeu doivent rester"


@essai("un poste eteint eteint aussi sa piece et son start, quand on est devant")
def _(dossier, espace):
    p = espace["Panneau"](2)
    p.presence(True)
    p.appliquer(2, {}, allume=False)
    assert lire(dossier, "aio_p2_start") == "0"
    assert lire(dossier, "aio_p2_select") == "0"


@essai("en mode clip, le poste 2 reste noir sur un jeu solo")
def _(dossier, espace):
    p = espace["Panneau"](2)
    p.presence(True)
    p.appliquer(1, {}, allume=False)       # jeu a un joueur : poste 2 eteint
    assert lire(dossier, "aio_p2_select") == "0"
    p.presence(False)                      # personne devant : mode clip
    assert lire(dossier, "aio_p2_select") == "0", "un jeu solo laisse le poste 2 noir"
    assert lire(dossier, "aio_p2_start") == "0", "la piece reste eteinte"


@essai("une manette sans SELECT laisse la piece eteinte, meme devant quelqu un")
def _(dossier, espace):
    # La Master System n a pas de bouton SELECT : la pause est sur la console.
    # Recalbox le dit deja, sa 9e entree est noire.
    etat = {"SystemId": "mastersystem", "GamePath": "/roms/mastersystem/alexkidd.sms",
            "Players": "1"}
    d = espace["decider"](etat, {})
    assert d["facade"]["piece"] is None, d["facade"]
    p = espace["Panneau"](1)
    p.presence(True)
    p.appliquer(d["nombre"], d["couleurs"], facade=d["facade"])
    assert lire(dossier, "aio_p1_start") == "0", "la Master System n a pas de SELECT"
    assert lire(dossier, "aio_p1_select") != "0", "mais elle a bien un START"


@essai("une manette Nintendo a les deux : START et SELECT s allument")
def _(dossier, espace):
    etat = {"SystemId": "snes", "GamePath": "/roms/snes/mario.sfc", "Players": "1"}
    d = espace["decider"](etat, {})
    assert d["facade"]["piece"], d["facade"]
    assert d["facade"]["start"], d["facade"]
    p = espace["Panneau"](1)
    p.presence(True)
    p.appliquer(d["nombre"], d["couleurs"], facade=d["facade"])
    assert lire(dossier, "aio_p1_start") != "0", "la Super Nintendo a un SELECT"
    assert lire(dossier, "aio_p1_select") != "0", "et un START"


@essai("un jeu d arcade garde la regle de la borne, pas celle d une manette")
def _(dossier, espace):
    p = espace["Panneau"](1)
    p.presence(True)
    p.appliquer(6, {}, facade=None)        # aucune facade : jeu d arcade
    assert lire(dossier, "aio_p1_select") != "0", "le start d une borne s allume"
    assert lire(dossier, "aio_p1_start") != "0", "et le monnayeur aussi"


@essai("un systeme inconnu de Recalbox garde la regle de la borne")
def _(dossier, espace):
    # mame, l arcade, tout ce que Recalbox ne nomme pas : ce n est pas une
    # manette, le START et le monnayeur existent toujours.
    d = espace["decider"]({"SystemId": "mame", "GamePath": "/roms/mame/pacman.zip",
                           "Players": "1-2"}, {})
    assert d["facade"] is None, d["facade"]
    p = espace["Panneau"](1)
    p.presence(True)
    p.appliquer(d["nombre"], d["couleurs"], facade=d["facade"])
    assert lire(dossier, "aio_p1_select") != "0", "le start d une borne s allume"
    assert lire(dossier, "aio_p1_start") != "0", "et le monnayeur aussi"


@essai("sur une console, le SELECT s allume meme en clip ; sur une borne, non")
def _(dossier, espace):
    # Game Boy : SELECT est un bouton de jeu, il reste eclaire en veille.
    d = espace["decider"]({"SystemId": "gb", "GamePath": "/roms/gb/tetris.gb",
                           "Players": "1"}, {})
    p = espace["Panneau"](1)
    p.presence(False)
    p.appliquer(d["nombre"], d["couleurs"], facade=d["facade"])
    assert lire(dossier, "aio_p1_start") != "0", "le SELECT d une console est un bouton"
    # mame : le meme bouton est un monnayeur, il attend quelqu un.
    d = espace["decider"]({"SystemId": "mame", "GamePath": "/roms/mame/pacman.zip",
                           "Players": "1"}, {})
    p2 = espace["Panneau"](2)
    p2.presence(False)
    p2.appliquer(d["nombre"], d["couleurs"], facade=d["facade"])
    assert lire(dossier, "aio_p2_start") == "0", "un monnayeur ne sert a personne en clip"


@essai("la touche hotkey s eteint des que personne n est devant")
def _(dossier, espace):
    p = espace["Panneau"](1)
    p.presence(True)
    assert lire(dossier, "aio_hotkey") != "0"
    p.presence(False)
    assert lire(dossier, "aio_hotkey") == "0"


@essai("le clip est plus doux que la presence, et les deux sont lisibles")
def _(dossier, espace):
    present, clip = int(espace["PRESENT"]), int(espace["CLIP"])
    assert clip < present, "le clip devrait etre plus doux que la presence"
    assert clip >= 64, "en dessous du quart, on ne lit plus les boutons"


@essai("changer d intensite ne reecrit pas les couleurs")
def _(dossier, espace):
    p = espace["Panneau"](1)
    p.appliquer(2, {"BUTTON1": {"couleur": "blue"}})
    avant = lire(dossier, "aio_p1_b4", "multi_intensity")
    p.reveiller("60")
    assert lire(dossier, "aio_p1_b4", "multi_intensity") == avant, "la couleur a bouge"
    assert lire(dossier, "aio_p1_b4") == "60", lire(dossier, "aio_p1_b4")


@essai("le reveil supporte les trois etats memorises")
def _(dossier, espace):
    p = espace["Panneau"](1)
    for etat in (None, 0, "repos", (2, (), "255")):
        p.dernier = etat
        p.intensite = "255"
        p.reveiller("80")        # ne doit pas lever d exception


@essai("un jeu sans fiche ni systeme connu laisse le panneau au repos")
def _(dossier, espace):
    d = espace["decider"]({"SystemId": "", "GamePath": ""}, {})
    assert d["fiche"] is None and d["nombre"] == 0, d


def principal():
    """Fait tourner tous les essais dans un dossier temporaire, un faux panneau
    neuf pour chacun, et compte les rates."""
    dossier = tempfile.mkdtemp(prefix="panneau-essai-")
    palette = os.path.join(dossier, "rgb.sh")
    palette_factice(palette)
    rates = 0
    try:
        for nom, fonction in essais:
            faux_panneau(dossier)
            espace = charger(dossier, palette)
            espace["COULEURS_CARTE"] = os.path.join(dossier, "couleurs.json")
            espace["JOURNAL"] = os.path.join(dossier, "panneau.log")
            espace["BATTEMENT"] = os.path.join(dossier, "vivant")
            try:
                fonction(dossier, espace)
                print("  ok   %s" % nom)
            except AssertionError as souci:
                rates += 1
                print("  RATE %s\n       %s" % (nom, souci))
            except Exception as souci:            # une erreur de programme
                rates += 1
                print("  ERR  %s\n       %s: %s" % (nom, type(souci).__name__, souci))
    finally:
        shutil.rmtree(dossier, ignore_errors=True)
    print("\n%d essai(s), %d rate(s)" % (len(essais), rates))
    return 1 if rates else 0


if __name__ == "__main__":
    sys.exit(principal())
