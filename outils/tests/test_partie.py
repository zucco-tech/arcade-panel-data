#!/usr/bin/env python3
"""Le cas signale : START consomme le credit, plus rien ne doit clignoter."""
import os, tempfile
import importlib.util, json, os, sys, threading, time, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # faux_retroarch.py est a cote
from faux_retroarch import FauxRetroArch
# Les programmes de la borne sont dans borne/share/userscripts/ : la suite doit
# tourner partout ou le depot est copie, pas seulement chez son auteur.
W = os.environ.get("ARCADE_CREDITS") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "borne", "share", "userscripts")
spec = importlib.util.spec_from_file_location("cp", os.path.join(W, "credits(permanent).py"))
cp = importlib.util.module_from_spec(spec); spec.loader.exec_module(cp)

RACINE = tempfile.mkdtemp(prefix="partie-")            # un dossier neuf, nettoye par le systeme
ADRESSE, PORT_RA, ORIGINE = 0x1234, 45600, "170 170 170"
def lampe(nom):
    c = []
    for i in (1, 2):
        d = os.path.join(RACINE, "%s_%d" % (nom, i)); os.makedirs(d)
        open(os.path.join(d, "brightness"), "w").write("255")
        open(os.path.join(d, "multi_intensity"), "w").write(ORIGINE); c.append(d)
    return tuple(c)
L_PIECE, L_START, L_B1 = lampe("piece"), lampe("start"), lampe("b1")
lecture, ecriture = os.pipe()
ETAT = os.path.join(RACINE, "es.inf")
CREDITS = os.path.join(RACINE, "credits"); os.makedirs(CREDITS)
APPRIS = os.path.join(CREDITS, "appris.json")     # ce que la borne apprend
json.dump({"jeux": {"testgame": {"credits": {"adresse": ADRESSE}}}}, open(os.path.join(CREDITS, "fbneo.json"), "w"))
ra = FauxRetroArch(PORT_RA, adresse_credits=ADRESSE); ra.start()
cp.DOSSIER_CREDITS, cp.LEDS_PIECE, cp.LEDS_START = CREDITS, L_PIECE, L_START
# Le bouton 1 est a la 4e place physique (ORDRE_BOUTONS) ; le poste 2 n a rien ici.
cp.LEDS_JEU = {1: [(), (), (), L_B1, (), (), (), ()], 2: []}
cp.RA_HOTE, cp.RA_PORT = "127.0.0.1", PORT_RA
cp.STATE_FILE, cp.JOURNAL = ETAT, os.path.join(RACINE, "log")
cp.ouvrir_pads = lambda: {lecture: "AllInOneP1"}
cp.signal = types.SimpleNamespace(signal=lambda *a: None, SIGTERM=15)
cp.INACTIVITE = 4.0                      # 120 s en vrai, 4 s pour le test
cp.DELAI_GUIDE = 0.8                     # 2 s en vrai : le temps de voir si le joueur hesite
def appui(code): os.write(ecriture, cp.EV.pack(0, 0, cp.EV_KEY, code, 1))
def etat(a):
    with open(ETAT, "w") as fh: fh.write("Action=%s\nSystemId=fbneo\n" % a)
def lu(c): return open(os.path.join(c[0], "brightness")).read().strip()
def observer(c, d, jouer=False):
    """jouer=True simule un joueur qui appuie : la borne sait qu'on joue."""
    v, fin = [], time.time() + d
    while time.time() < fin:
        x = lu(c)
        if not v or v[-1] != x: v.append(x)
        if jouer: appui(304)
        time.sleep(0.05)
    return set(v)
echecs = []
def verifier(t, ok, det=""):
    print("%-54s %s %s" % (t, "OK" if ok else "ECHEC", det)); (echecs.append(t) if not ok else None)

etat("rungame"); ra.ram[ADRESSE] = 0
threading.Thread(target=cp.main, daemon=True).start(); time.sleep(1.5)
verifier("0 credit : le bouton piece clignote", len(observer(L_PIECE, 2.0)) > 1)

ra.credits(+1); appui(cp.CODE_PIECE); time.sleep(1.2)
verifier("piece mise : c'est le start qui clignote", len(observer(L_START, 2.0)) > 1)
verifier("le bouton piece se calme", observer(L_PIECE, 1.0) == {"255"})

print("\n--- le cas signale : on appuie sur START ---")
appui(cp.CODE_START); ra.credits(-1); time.sleep(1.5)
verifier("le joueur hesite : le bouton 1 pulse, c'est lui qui valide", len(observer(L_B1, 1.5)) > 1)
appui(304)                                 # le joueur appuie sur un bouton de jeu : il a trouve
time.sleep(0.4)
verifier("des qu'on joue, il se stabilise, allume", observer(L_B1, 1.0, jouer=True) == {"255"})
verifier("credit retombe a 0 : LE PIECE NE CLIGNOTE PAS", observer(L_PIECE, 2.5, jouer=True) == {"255"})
verifier("le start non plus", observer(L_START, 1.5, jouer=True) == {"255"})
verifier("les couleurs sont d'origine",
         open(os.path.join(L_PIECE[0], "multi_intensity")).read().strip() == ORIGINE)

print("\n--- on continue de jouer : toujours rien ---")
for _ in range(6):
    appui(304); time.sleep(0.5)          # un bouton de jeu quelconque
verifier("pendant la partie : rien ne clignote", observer(L_PIECE, 2.0, jouer=True) == {"255"})

print("\n--- game over : le panneau se tait ---")
time.sleep(cp.INACTIVITE + 1.5)
verifier("apres le silence : le piece reclignote", len(observer(L_PIECE, 2.5)) > 1)

etat("endgame"); time.sleep(1.2)
verifier("sortie : tout est rendu", lu(L_PIECE) == "255" and lu(L_START) == "255")
ra.stop = True
print("\n%s" % ("TOUT EST BON" if not echecs else "ECHECS : " + ", ".join(echecs)))
