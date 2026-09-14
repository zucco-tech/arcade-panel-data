#!/usr/bin/env python3
"""Le tour du panneau : chaque LED s allume seule, on appuie dessus, on note.

Une LED s allume, dans une couleur qui lui est propre ; le joueur appuie sur
le bouton eclaire ; on lit le code recu et on dit tout de suite si c est le
bon — celui que le cablage et le mappage Recalbox annoncent pour cette LED.
Poste 1 puis poste 2, boutons de jeu puis facade (PIECE, START, HOTKEY).

    python3 verifier-cablage.py [1|2|12]

Le panneau du menu est arrete pendant le tour et relance a la fin, quoi
qu il arrive. Rien n est ecrit : c est une verification, pas une mesure.
Pour MESURER un cablage inconnu, c est associer-boutons.py."""

import os
import select
import struct
import subprocess
import sys
import time

FMT = "llHHi"
TAILLE = struct.calcsize(FMT)
LEDS = "/sys/class/leds"
N = "/recalbox/share/system/panneau-allinone"
MANETTE = {1: "/dev/input/event1", 2: "/dev/input/event2"}
ATTENTE = 25.0                       # secondes par bouton

# Une couleur par bouton, pour qu on voie d un coup d oeil lequel est allume.
# Ecrites dans l ordre du materiel (vert, rouge, bleu) : ce sont des reperes,
# pas des couleurs de jeu.
COULEURS = {
    "b1": "0 255 0",     # rouge
    "b2": "255 0 0",     # vert
    "b3": "0 0 255",     # bleu
    "b4": "255 255 0",   # jaune
    "b5": "0 255 255",   # magenta
    "b6": "255 0 255",   # cyan
    "select": "255 255 255",
    "start": "255 255 255",
    "hotkey": "255 255 255",
}
# Le nom que le pilote donne aux LED de facade est croise : la LED appelee
# « start » eclaire le bouton PIECE, et inversement (voir panneau(permanent)).
FACADE = [("start", "PIECE"), ("select", "START"), ("hotkey", "HOTKEY")]


def ecrire(poste, nom, fichier, valeur):
    """Ecrit la meme valeur dans les deux LED d un bouton ; le hotkey n existe
    que sur le poste 1."""
    cible = "aio_hotkey" if nom == "hotkey" else "aio_p%d_%s" % (poste, nom)
    for k in (1, 2):
        try:
            with open("%s/%s_%d/%s" % (LEDS, cible, k, fichier), "w") as fh:
                fh.write(valeur)
        except OSError:
            pass


def eteindre_tout(poste):
    """Eteint tous les boutons du poste, pour qu un seul soit allume a la fois."""
    for nom in list(COULEURS):
        if nom == "hotkey" and poste != 1:
            continue
        ecrire(poste, nom, "brightness", "0")


def arreter_panneau():
    """Arrete le programme du menu : il repeindrait les LED pendant le tour."""
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        try:
            with open("/proc/%s/cmdline" % p, "rb") as fh:
                if b"panneau(permanent)" in fh.read():
                    os.kill(int(p), 15)
        except OSError:
            pass


def attendre(pad, delai=ATTENTE):
    """Le premier code presse, ou None au bout du delai."""
    fin = time.time() + delai
    while time.time() < fin:
        prets, _, _ = select.select([pad], [], [], 0.5)
        if not prets:
            continue
        d = pad.read(TAILLE)
        if len(d) < TAILLE:
            continue
        _, _, typ, code, val = struct.unpack(FMT, d)
        if typ == 1 and val == 1:
            return code
    return None


def tour(poste, table):
    """Un poste, LED par LED. Renvoie le nombre d ecarts."""
    ecarts = 0
    attendus = []
    for n in range(1, 7):
        code = next((c for c, l in table._led_du_code[poste].items() if l == n), None)
        attendus.append(("b%d" % n, code, "bouton %s FBNeo / %s MAME" % (
            table.bouton_de_led(poste, n, "fbneo") or "?", table.bouton_de_led(poste, n, "mame") or "?")))
    for nom_led, role in FACADE:
        if nom_led == "hotkey" and poste != 1:
            continue
        attendus.append((nom_led, table.code(poste, "hotkey" if nom_led == "hotkey"
                                             else ("select" if nom_led == "start" else "start")), role))
    print("\n--- poste %d (bouton du jeu : sous FBNeo et les consoles Recalbox met 1 et 2 en bas ; MAME suit le dessin) ---" % poste, flush=True)
    with open(MANETTE[poste], "rb", buffering=0) as pad:
        while select.select([pad], [], [], 0)[0]:      # on vide ce qui traine
            pad.read(TAILLE)
        for nom, attendu, quoi in attendus:
            eteindre_tout(poste)
            ecrire(poste, nom, "multi_intensity", COULEURS[nom])
            ecrire(poste, nom, "brightness", "255")
            recu = attendre(pad)
            if recu is None:
                verdict, ecarts = "RIEN       aucun appui en %d s" % ATTENTE, ecarts + 1
            elif attendu is None:
                verdict = "code %d (aucun attendu pour cette LED)" % recu
            elif recu == attendu:
                verdict = "OK         code %d" % recu
            else:
                verdict, ecarts = "ECART      attendu %s, recu %s" % (attendu, recu), ecarts + 1
            print("  %-7s %-18s %s" % (nom, quoi, verdict), flush=True)
    eteindre_tout(poste)
    return ecarts


def main():
    quels = sys.argv[1] if len(sys.argv) > 1 else "12"
    sys.path.insert(0, N)
    import cablage
    table = cablage.Cablage()
    print("tables : %s" % table.source, flush=True)
    arreter_panneau()
    time.sleep(1.0)
    ecarts = 0
    try:
        for poste in (1, 2):
            if str(poste) in quels:
                ecarts += tour(poste, table)
    finally:
        subprocess.call(["sh", N + "/relancer.sh", "panneau"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("\n%s" % ("tout concorde : le cablage et le mappage disent la meme chose"
                    if ecarts == 0 else "%d ecart(s) — voir ci-dessus" % ecarts), flush=True)
    return 1 if ecarts else 0


if __name__ == "__main__":
    sys.exit(main())
