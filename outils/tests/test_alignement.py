#!/usr/bin/env python3
"""Bouton 1 en haut a gauche : aligner-boutons.py et le panneau qui le suit.

Un faux es_input.cfg (celui de la borne, 16/09/2026), de faux dossiers de
roms. On verifie que la surcharge ecrite remet FBNeo dans l ordre du dessin,
que les LED la suivent des le menu et en jeu, que MAME et les consoles ne
bougent pas, et qu un .retroarch.cfg etranger n est jamais touche.
"""
import os, subprocess, sys, tempfile
ICI = os.path.dirname(os.path.abspath(__file__))
DEPOT = os.path.dirname(os.path.dirname(ICI))
sys.path.insert(0, os.path.join(DEPOT, "borne", "share", "userscripts", "panneau-allinone"))
import cablage

R = tempfile.mkdtemp(prefix="alignement-")
ES = os.path.join(R, "es_input.cfg")
def poste(nom, hotkey):
    boutons = [("r1", 4, 310), ("l1", 5, 311), ("west", 2, 307), ("north", 7, 313),
               ("south", 0, 304), ("east", 1, 305), ("hotkey", hotkey, 314 + (hotkey == 10) * 2),
               ("select", 8, 314), ("start", 9, 315)]
    return ('<inputConfig type="joystick" deviceName="%s" gamepadtype="arcade6" version="2">' % nom
            + "".join('<input name="%s" type="button" id="%d" value="1" code="%d" />' % b for b in boutons)
            + "</inputConfig>")
with open(ES, "w") as fh:
    fh.write("<inputList>%s%s</inputList>" % (poste("AllInOneP2", 8), poste("AllInOneP1", 10)))
ROMS = os.path.join(R, "roms")
for s in ("fbneo", "neogeo", "mame", "nes", "etranger"):
    os.makedirs(os.path.join(ROMS, s))
ETRANGER = os.path.join(ROMS, "etranger", ".retroarch.cfg")
with open(ETRANGER, "w") as fh:
    fh.write("video_smooth = true\n")

echecs = []
def verifier(t, ok, det=""):
    print("%-62s %s %s" % (t, "OK" if ok else "ECHEC", det))
    if not ok: echecs.append(t)
def outil(*args):
    return subprocess.run([sys.executable, os.path.join(DEPOT, "outils", "aligner-boutons.py"),
                           "--es-input", ES, "--roms", ROMS] + list(args),
                          capture_output=True, text=True)
def leds(c, systeme, en_jeu=False):
    return [c.led_du_bouton(1, n, systeme, en_jeu) for n in range(1, 7)]

def panneau(retroarch="absent.cfg"):
    return cablage.Cablage(es_input=ES, fichier_cablage=os.path.join(R, "pas-de-cablage.json"),
                           retroarch=os.path.join(R, retroarch),
                           surcharge_systeme=os.path.join(ROMS, "%s", ".retroarch.cfg"))

print("--- avant : la regle de Recalbox ---")
c = panneau()
verifier("FBNeo : bouton 1 en bas a gauche (LED 4)", leds(c, "fbneo") == [4, 5, 1, 2, 3, 6], leds(c, "fbneo"))
verifier("MAME : dans l ordre du dessin", leds(c, "mame") == [1, 2, 3, 4, 5, 6])

print("\n--- l outil ---")
r = outil("fbneo", "neogeo", "etranger", "absent")
verifier("il s execute", r.returncode == 0, r.stderr[-300:])
texte = open(os.path.join(ROMS, "fbneo", ".retroarch.cfg")).read()
verifier("numeros lus dans es_input.cfg, poste 1", 'input_player1_b_btn = "0"' in texte
         and 'input_player1_x_btn = "7"' in texte and 'input_player1_l_btn = "5"' in texte)
verifier("et poste 2", 'input_player2_r_btn = "4"' in texte)
verifier("un .retroarch.cfg etranger n est pas touche",
         open(ETRANGER).read() == "video_smooth = true\n" and "pas a nous" in r.stdout)
verifier("un systeme sans dossier est ignore", "absent : pas de dossier" in r.stdout)

print("\n--- apres : le panneau suit ---")
c = panneau()
verifier("menu FBNeo : bouton N sous la LED N", leds(c, "fbneo") == [1, 2, 3, 4, 5, 6], leds(c, "fbneo"))
verifier("menu Neo Geo : pareil", leds(c, "neogeo") == [1, 2, 3, 4, 5, 6])
verifier("MAME ne bouge pas", leds(c, "mame") == [1, 2, 3, 4, 5, 6])
verifier("NES garde la regle de Recalbox", leds(c, "nes") == [4, 5, 1, 2, 3, 6])

# En jeu : RetroArch a charge retroarchcustom.cfg (regle) PUIS la surcharge.
with open(os.path.join(R, "retroarchcustom.cfg"), "w") as fh:
    fh.write("".join("input_player1_%s_btn = %d\n" % kv for kv in
                     (("b", 7), ("a", 5), ("y", 0), ("x", 1), ("l", 2), ("r", 4))))
with open(os.path.join(R, "retroarchcustom.cfg.overrides.cfg"), "w") as fh:
    fh.write(texte)
c = panneau("retroarchcustom.cfg")
verifier("en jeu : la surcharge l emporte sur retroarchcustom.cfg",
         leds(c, "fbneo", True) == [1, 2, 3, 4, 5, 6], leds(c, "fbneo", True))
verifier("et RetroArch concorde avec la regle : aucun ecart note", c.ecart_retroarch(1, "fbneo") == [],
         c.ecart_retroarch(1, "fbneo"))

print("\n--- par jeu : le coeur range Street Fighter autrement ---")
import json
for rom in ("1942.zip", "sf2ce.zip", "garou.zip"):
    open(os.path.join(ROMS, "fbneo", rom), "w").close()
ETRANGER_JEU = os.path.join(ROMS, "fbneo", "garou.zip.retroarch.cfg")
with open(ETRANGER_JEU, "w") as fh:
    fh.write("input_player1_b_btn = 3\n")
ENTREES = os.path.join(R, "entrees.json")
with open(ENTREES, "w") as fh:
    json.dump({"jeux": {"1942": {"systeme": "fbneo", "retropad": ["b", "a"]},
                        "sf2ce": {"systeme": "fbneo", "retropad": ["y", "x", "l", "b", "a", "r", "l2", "r2"]},
                        "garou": {"systeme": "fbneo", "retropad": ["a", "b"]}}}, fh)
r = outil("--entrees", ENTREES, "fbneo")
verifier("il s execute", r.returncode == 0, r.stderr[-300:])
SF2 = os.path.join(ROMS, "fbneo", "sf2ce.zip.retroarch.cfg")
verifier("1942, deja dans l ordre habituel : pas de fichier par jeu",
         not os.path.exists(os.path.join(ROMS, "fbneo", "1942.zip.retroarch.cfg")))
jeu = open(SF2).read() if os.path.exists(SF2) else ""
# poings (y x l) en haut sur les positions 1 2 3, pieds (b a r) en bas.
verifier("sf2ce : poings en haut", all(l in jeu for l in
         ('input_player1_y_btn = "0"', 'input_player1_x_btn = "1"', 'input_player1_l_btn = "2"')), jeu)
verifier("sf2ce : pieds en bas", all(l in jeu for l in
         ('input_player1_b_btn = "7"', 'input_player1_a_btn = "5"', 'input_player1_r_btn = "4"')))
verifier("un fichier par jeu etranger n est pas touche", open(ETRANGER_JEU).read() == "input_player1_b_btn = 3\n")
# En jeu, RetroArch charge : regle, dossier, puis fichier du jeu.
with open(os.path.join(R, "retroarchcustom.cfg.overrides.cfg"), "w") as fh:
    fh.write(texte + jeu)
c = panneau("retroarchcustom.cfg")
verifier("en jeu sf2ce : bouton N (poing faible = 1) sous la LED N",
         leds(c, "fbneo", True) == [1, 2, 3, 4, 5, 6], leds(c, "fbneo", True))
r = outil("--entrees", ENTREES, "fbneo")
verifier("relance : rien a reecrire", "0 fichier(s) ecrit(s), 0 retire(s)" in r.stdout, r.stdout)
with open(ENTREES, "w") as fh:
    json.dump({"jeux": {"sf2ce": {"systeme": "fbneo", "retropad": ["b", "a", "y"]}}}, fh)
r = outil("--entrees", ENTREES, "fbneo")
verifier("un jeu redevenu habituel perd son fichier", not os.path.exists(SF2), r.stdout)

print("\n--- retour en arriere ---")
r = outil("--retirer", "fbneo", "neogeo", "etranger")
verifier("nos fichiers retires", not os.path.exists(os.path.join(ROMS, "fbneo", ".retroarch.cfg")))
verifier("l etranger reste", os.path.exists(ETRANGER) and os.path.exists(ETRANGER_JEU))
verifier("la regle de Recalbox revient", leds(panneau(), "fbneo") == [4, 5, 1, 2, 3, 6])

print("\n%s" % ("TOUT EST BON" if not echecs else "ECHECS : " + ", ".join(echecs)))
sys.exit(1 if echecs else 0)
