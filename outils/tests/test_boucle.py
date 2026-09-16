#!/usr/bin/env python3
"""Le panneau se tait-il pendant la partie, et resiste-t-il a un etat coupe ?

Le cas signale le 14/09/2026 : les lumieres n etaient pas fluides, elles
avaient de la latence. EmulationStation reecrit /tmp/es_state.inf en place ;
le panneau tombait parfois au milieu, ne trouvait plus « Action », concluait
que la partie etait finie, repeignait tout — puis se ravisait au tour
suivant. Six bascules dans la meme seconde, pendant que le demon des credits
faisait clignoter les memes LED : cela saccadait.

On fait tourner la vraie boucle du panneau contre un faux panneau de LED et
un faux fichier d etat, et on regarde ce qui est ecrit.

    python3 outils/tests/test_boucle.py
"""

import os
import shutil
import sys
import tempfile
import threading
import time
import types

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROGRAMME = os.path.join(RACINE, "borne", "share", "userscripts", "panneau(permanent).py")
BOUTONS = ["aio_p%d_b%d" % (j, n) for j in (1, 2) for n in range(1, 7)]
ANNEXES = ["aio_p%d_%s" % (j, k) for j in (1, 2) for k in ("start", "select")] + ["aio_hotkey"]

echecs = []


def verifier(nom, ok):
    print("  %-64s %s" % (nom, "ok" if ok else "ECHEC"))
    if not ok:
        echecs.append(nom)


dossier = tempfile.mkdtemp(prefix="boucle-")
try:
    for nom in BOUTONS + ANNEXES:
        for k in (1, 2):
            c = os.path.join(dossier, "%s_%d" % (nom, k))
            os.makedirs(c)
            open(os.path.join(c, "brightness"), "w").write("255")
            open(os.path.join(c, "multi_intensity"), "w").write("0 0 0")
    etat_fichier = os.path.join(dossier, "es_state.inf")
    palette = os.path.join(dossier, "palette.sh")
    open(palette, "w").write(
        'declare -a fbneo=("0x00 0xFF 0x00" "0x00 0xFF 0x00" "0x00 0x00 0x00" "0x00 0x00 0x00" '
        '"0x00 0x00 0x00" "0x00 0x00 0x00" "0x00 0x00 0x00" "0x00 0x00 0x00" "0xAA 0xAA 0xAA" '
        '"0xAA 0xAA 0xAA" "0xFF 0xFF 0xFF")\n')

    def ecrire_etat(lignes):
        with open(etat_fichier, "w") as fh:
            fh.write(lignes)
        os.utime(etat_fichier, None)

    ecrire_etat("Action=rungame\nState=playing\nSystemId=fbneo\nGamePath=/x/64streetja.zip\n")

    # La palette est lue au chargement du programme : il faut donc la lui
    # designer AVANT, dans sa source, comme font les autres bancs.
    os.environ["PANNEAU_LEDS"] = dossier
    source = open(PROGRAMME).read().replace(
        'PALETTE_RECALBOX = "/recalbox/scripts/recalbox_allinone_rgb.sh"',
        'PALETTE_RECALBOX = %r' % palette)
    pp = types.ModuleType("pp")
    pp.__file__ = PROGRAMME          # pour qu il trouve cablage.py a cote
    exec(compile(source, PROGRAMME, "exec"), pp.__dict__)
    pp.ETAT = etat_fichier
    pp.JOURNAL = os.path.join(dossier, "journal.log")
    pp.BATTEMENT = os.path.join(dossier, "vivant")
    pp.BASE_BOUTONS = os.path.join(dossier, "absente.json")
    pp.ouvrir_manettes = lambda: []
    pp.publier_couleurs_carte = lambda carte: None

    threading.Thread(target=pp.main, daemon=True).start()
    time.sleep(2.0)

    def photo():
        """Tout ce qui est ecrit sur le panneau, en un instantane."""
        return {c: open(os.path.join(dossier, c, "brightness")).read()
                for c in os.listdir(dossier) if os.path.isdir(os.path.join(dossier, c))}

    print("--- pendant la partie, le panneau ne touche plus aux LED ---")
    avant = photo()
    time.sleep(2.5)
    verifier("rien n a bouge en 2,5 s de jeu", photo() == avant)

    print("--- l etat coupe en plein milieu ne fait pas basculer ---")
    for _ in range(6):
        # Ce qu on lit quand EmulationStation est en train de reecrire.
        ecrire_etat("Action")
        time.sleep(0.12)
        ecrire_etat("Action=rungame\nState=playing\nSystemId=fbneo\nGamePath=/x/64streetja.zip\n")
        time.sleep(0.12)
    time.sleep(0.5)
    verifier("apres six coupures, le panneau n a toujours rien ecrit", photo() == avant)
    lignes = open(pp.JOURNAL).read().count("bouton(s)")
    verifier("et rien n a ete note au journal", lignes == 0)

    print("--- a la sortie, il reprend la main ---")
    # Il repeint souvent les memes couleurs — la photo ne suffit donc pas a
    # le prouver. Ce qui le prouve, c est qu il a repris ses decisions : il
    # note le systeme au journal, ce qu il ne faisait plus pendant la partie.
    ecrire_etat("Action=endgame\nSystemId=fbneo\n")
    time.sleep(2.0)
    verifier("le panneau a repris la main en sortant",
             open(pp.JOURNAL).read().count("bouton(s)") == 1)

finally:
    shutil.rmtree(dossier, ignore_errors=True)

print("\n%s" % ("TOUT EST BON" if not echecs else "ECHECS : " + ", ".join(echecs)))
sys.exit(1 if echecs else 0)
