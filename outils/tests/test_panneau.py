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

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROGRAMME = os.path.join(RACINE, "depot", "borne", "panneau(permanent).py")
if not os.path.exists(PROGRAMME):
    PROGRAMME = os.path.join(RACINE, "outils", "panneau(permanent).py")

BOUTONS = ["aio_p%d_b%d" % (j, n) for j in (1, 2) for n in range(1, 7)]
ANNEXES = ["aio_p%d_%s" % (j, k) for j in (1, 2) for k in ("start", "select")] + ["aio_hotkey"]

essais = []


def essai(nom):
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
    espace = {"__name__": "panneau_essai"}
    exec(compile(source, PROGRAMME, "exec"), espace)
    return espace


def palette_factice(chemin):
    """Deux systemes et le secours, dans la forme du script Recalbox."""
    with open(chemin, "w") as fh:
        fh.write('declare -a nes=("0x00 0xFF 0x00" "0x00 0xFF 0x00" "0x00 0x00 0x00" '
                 '"0x00 0x00 0x00" "0x00 0x00 0x00" "0x00 0x00 0x00" "0x00 0x00 0x00" '
                 '"0x00 0x00 0x00" "0xAA 0xAA 0xAA" "0xAA 0xAA 0xAA" "0xFF 0xFF 0xFF")\n')
        fh.write('declare -a gb=("0x00 0xFF 0x00" "0x00 0xFF 0x00" "0x00 0x00 0x00" '
                 '"0x00 0x00 0x00" "0x00 0x00 0x00" "0x00 0x00 0x00" "0x00 0x00 0x00" '
                 '"0x00 0x00 0x00" "0xAA 0xAA 0xAA" "0xAA 0xAA 0xAA" "0xFF 0xFF 0xFF")\n')
        fh.write('declare -a astrocityp1=("0xFF 0x00 0x00" "0xFF 0x00 0x00" "0xFF 0x00 0x00" '
                 '"0xFF 0x00 0x00" "0xFF 0x00 0x00" "0xFF 0x00 0x00" "0x00 0x00 0x00" '
                 '"0x00 0x00 0x00" "0xFF 0xFF 0x00" "0xFF 0xFF 0x00" "0x00 0x00 0xFF")\n')
        fh.write('declare -a astrocityp2=("0x00 0x80 0x80" "0x00 0x80 0x80" "0x00 0x80 0x80" '
                 '"0x00 0x80 0x80" "0x00 0x80 0x80" "0x00 0x80 0x80" "0x00 0x00 0x00" '
                 '"0x00 0x00 0x00" "0xFF 0xFF 0x00" "0xFF 0xFF 0x00" "0x00 0x80 0x80")\n')


def lire(dossier, nom, fichier="brightness"):
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


@essai("une console prend les couleurs de Recalbox (NES = vert)")
def _(dossier, espace):
    etat = {"SystemId": "nes", "GamePath": "/roms/nes/mario.nes", "Players": "1-2"}
    d = espace["decider"](etat, {})
    assert d["nombre"] == 2, d["nombre"]
    espace["Panneau"](1).appliquer(d["nombre"], d["couleurs"])
    # la carte est cablee vert-rouge-bleu : du vert s ecrit « 255 0 0 »
    assert lire(dossier, "aio_p1_b4", "multi_intensity") == "255 0 0"


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


@essai("poser la carte ne touche QUE les couleurs, jamais l allumage")
def _(dossier, espace):
    for j in (1, 2):
        for n in range(1, 7):
            with open(os.path.join(dossier, "aio_p%d_b%d_1" % (j, n), "brightness"), "w") as fh:
                fh.write("7")
    p = espace["Panneau"](1)
    p.poser_carte(espace["couleurs_de_carte"]("nes"))
    assert lire(dossier, "aio_p1_b1") == "7", "l allumage a ete touche"


@essai("la touche hotkey s eteint des que personne n est devant")
def _(dossier, espace):
    p = espace["Panneau"](1)
    p.presence(True)
    assert lire(dossier, "aio_hotkey") != "0"
    p.presence(False)
    assert lire(dossier, "aio_hotkey") == "0"


@essai("le jour eclaire plus fort que la nuit, present ou non")
def _(dossier, espace):
    jour_present = int(espace["JOUR_PRESENT"])
    nuit_present = int(espace["NUIT_PRESENT"])
    nuit_repos = int(espace["NUIT_REPOS"])
    jour_repos = int(espace["JOUR_REPOS"])
    assert nuit_present < jour_present, "la nuit devrait etre plus douce que le jour"
    assert jour_repos < jour_present, "le clip devrait etre plus doux que la presence"
    assert nuit_repos <= nuit_present, "la nuit au repos ne doit pas depasser la presence"
    assert nuit_repos < jour_repos, "la nuit devrait rester plus douce que le jour"


@essai("le soleil se leve et se couche a des heures credibles")
def _(dossier, espace):
    ete = espace["heures_du_soleil"](time.mktime((2026, 6, 21, 12, 0, 0, 0, 0, -1)))
    hiver = espace["heures_du_soleil"](time.mktime((2026, 12, 21, 12, 0, 0, 0, 0, -1)))
    assert 4 < ete[0] < 7 and 21 < ete[1] < 23, ete
    assert 7 < hiver[0] < 10 and 16 < hiver[1] < 18, hiver
    assert espace["il_fait_jour"](time.mktime((2026, 6, 21, 14, 0, 0, 0, 0, -1)))
    assert not espace["il_fait_jour"](time.mktime((2026, 12, 21, 23, 0, 0, 0, 0, -1)))


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
