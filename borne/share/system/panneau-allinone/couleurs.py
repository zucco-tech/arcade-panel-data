"""Les couleurs des boutons, partagees par le panneau et les credits.

Ces trois choses etaient ecrites a l identique dans les deux programmes :
la palette de secours quand une fiche ne donne pas de couleur, la table des
teintes nommees, et la regle qui choisit l une dans l autre. Deux copies,
c est deux endroits ou corriger — elles vivent ici maintenant.

A importer depuis userscripts/, comme cablage :
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "system", "panneau-allinone"))
    import couleurs
"""

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

def teinte_par_defaut(nombre, numero):
    """La couleur d un bouton quand la fiche n en donne pas : la palette par
    defaut pour ce nombre de boutons, blanc au-dela."""
    palette = PALETTE_DEFAUT.get(nombre) or PALETTE_DEFAUT[6]
    return palette[numero - 1] if numero - 1 < len(palette) else "white"
