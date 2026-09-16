"""Les couleurs des boutons, partagees par le panneau et les credits.

Ces trois choses etaient ecrites a l identique dans les deux programmes :
la palette de secours quand une fiche ne donne pas de couleur, la table des
teintes nommees, et la regle qui choisit l une dans l autre. Deux copies,
c est deux endroits ou corriger — elles vivent ici maintenant.

Ou il vit, et pourquoi la. Le code partage par les programmes du panneau
est range dans userscripts/panneau-allinone/, a cote de ceux qui s en
servent ; les donnees (credits, cablage.json, journaux) restent dans
system/panneau-allinone/. Un SOUS-DOSSIER, pas userscripts/ lui-meme :
EmulationStation execute tout .py ou .sh pose directement dans userscripts
et dont le nom ne porte pas d evenements entre crochets — a CHAQUE evenement,
chaque mouvement dans le menu (NotificationManager.cpp, LoadScriptList et
ExtractNotificationsFromPath, lu le 16/09/2026). Les sous-dossiers, il ne
les regarde pas.

A importer depuis userscripts/ :
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "panneau-allinone"))
    import couleurs
"""

import os

# Quelle couleur donner au bouton N quand on ne sait rien du jeu, selon le
# nombre de boutons qu il utilise. Lue sur les bornes d origine.
PALETTE_DEFAUT = {
    1: ["red"],
    2: ["red", "blue"],
    3: ["blue", "blue", "blue"],
    4: ["red", "yellow", "green", "blue"],
    5: ["blue", "yellow", "red", "blue", "yellow"],
    6: ["blue", "yellow", "red", "blue", "yellow", "red"],
}

# Les teintes nommees par la base des boutons, en rouge/vert/bleu vrais.
TEINTES = {
    "red": (0xFF, 0x00, 0x00), "blue": (0x00, 0x00, 0xFF),
    "green": (0x00, 0xFF, 0x00), "yellow": (0xFF, 0xFF, 0x00),
    "white": (0xFF, 0xFF, 0xFF), "black": (0x20, 0x20, 0x20),
    "orange": (0xFF, 0x60, 0x00), "purple": (0x80, 0x00, 0xFF),
    "pink": (0xFF, 0x40, 0x80), "cyan": (0x00, 0xFF, 0xFF),
    "grey": (0x60, 0x60, 0x60), "gray": (0x60, 0x60, 0x60),
}

COMPOSANTES = ("red", "green", "blue")


def ordre_materiel(chemin_led="/sys/class/leds/aio_p1_b1_1"):
    """Dans quel ordre ecrire (rouge, vert, bleu) dans multi_intensity.

    Chaque LED publie dans multi_index le nom de ses composantes, dans
    l ordre ou multi_intensity les attend. Le pilote AllInOne d origine
    annonce « red green blue » alors que ses WS2812B sont cablees vert,
    rouge, bleu (mesure du 12/09/2026) : ce texte-la est connu pour mentir,
    on applique la correction mesuree. Un pilote corrige annonce « green
    red blue » : on le croit, et le resultat est le meme. Sans LED lisible
    (banc d essai, carte absente), on garde la correction mesuree.

    Renvoie les indices a prendre dans (rouge, vert, bleu), position par
    position : (1, 0, 2) pour vert, rouge, bleu."""
    try:
        with open(os.path.join(chemin_led, "multi_index")) as fh:
            noms = fh.read().split()
    except (IOError, OSError):
        noms = []
    if sorted(noms) != sorted(COMPOSANTES) or tuple(noms) == COMPOSANTES:
        return (1, 0, 2)
    return tuple(COMPOSANTES.index(n) for n in noms)


def teinte_par_defaut(nombre, numero):
    """La couleur d un bouton quand la fiche n en donne pas : la palette par
    defaut pour ce nombre de boutons, blanc au-dela."""
    palette = PALETTE_DEFAUT.get(nombre) or PALETTE_DEFAUT[6]
    return palette[numero - 1] if numero - 1 < len(palette) else "white"
