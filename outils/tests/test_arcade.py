#!/usr/bin/env python3
"""Les trois etats d'une borne : piece, start, partie en cours."""
import os
import importlib.util, json, os, sys, threading, time, types
sys.path.insert(0, "/tmp/claude-1000/test")
from faux_retroarch import FauxRetroArch

# Les programmes de la borne sont dans borne/share/userscripts/ : la suite doit
# tourner partout ou le depot est copie, pas seulement chez son auteur.
W = os.environ.get("ARCADE_CREDITS") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "borne", "share", "userscripts")
spec = importlib.util.spec_from_file_location("cp", os.path.join(W, "credits(permanent).py"))
cp = importlib.util.module_from_spec(spec); spec.loader.exec_module(cp)

RACINE = "/tmp/claude-1000/test/arcade"; os.system("rm -rf " + RACINE); os.makedirs(RACINE)
ADRESSE, PORT_RA = 0x1234, 45500
ORIGINE = "170 170 170"          # la couleur posee par la carte pour le systeme

def lampe(nom):
    chemins = []
    for i in (1, 2):
        d = os.path.join(RACINE, "%s_%d" % (nom, i)); os.makedirs(d)
        open(os.path.join(d, "brightness"), "w").write("255")
        open(os.path.join(d, "multi_intensity"), "w").write(ORIGINE)
        chemins.append(d)
    return tuple(chemins)

L_PIECE, L_START = lampe("piece"), lampe("start")
lecture, ecriture = os.pipe()
ETAT = os.path.join(RACINE, "es_state.inf")
CREDITS = os.path.join(RACINE, "credits"); os.makedirs(CREDITS)
APPRIS = os.path.join(CREDITS, "appris.json")     # ce que la borne apprend
json.dump({"jeux": {"testgame": {"credits": {"adresse": ADRESSE}}}}, open(os.path.join(CREDITS, "fbneo.json"), "w"))

ra = FauxRetroArch(PORT_RA, adresse_credits=ADRESSE); ra.start()
cp.DOSSIER_CREDITS = CREDITS
cp.INACTIVITE = 6.0                      # 45 s en vrai ; assez long pour que
                                         # les observations de l etat 3 tiennent dedans
cp.LEDS_PIECE, cp.LEDS_START = L_PIECE, L_START
cp.RA_HOTE, cp.RA_PORT = "127.0.0.1", PORT_RA
cp.STATE_FILE, cp.JOURNAL = ETAT, os.path.join(RACINE, "credits.log")
cp.ouvrir_pads = lambda: {lecture: "AllInOneP1"}
cp.signal = types.SimpleNamespace(signal=lambda *a: None, SIGTERM=15)

def appui(code): os.write(ecriture, cp.EV.pack(0, 0, cp.EV_KEY, code, 1))
def etat(action):
    with open(ETAT, "w") as fh: fh.write("Action=%s\nSystemId=fbneo\n" % action)
def lu(chemins, fichier):
    return open(os.path.join(chemins[0], fichier)).read().strip()
def observer(chemins, duree):
    vues, fin = [], time.time() + duree
    while time.time() < fin:
        v = lu(chemins, "brightness")
        if not vues or vues[-1] != v: vues.append(v)
        time.sleep(0.05)
    return set(vues)

echecs = []
def verifier(titre, ok, detail=""):
    print("%-52s %s %s" % (titre, "OK" if ok else "ECHEC", detail))
    if not ok: echecs.append(titre)

etat("rungame"); ra.ram[ADRESSE] = 0
threading.Thread(target=cp.main, daemon=True).start()
time.sleep(1.5)

print("--- etat 1 : plus de credit ---")
verifier("le bouton piece clignote", len(observer(L_PIECE, 2.5)) > 1)
verifier("il est rouge", lu(L_PIECE, "multi_intensity") == cp.COULEUR_PIECE,
         lu(L_PIECE, "multi_intensity"))
verifier("le bouton start reste allume", observer(L_START, 1.0) == {"255"})
verifier("start garde sa couleur d'origine", lu(L_START, "multi_intensity") == ORIGINE)

print("\n--- etat 2 : du credit, partie pas lancee ---")
ra.ram[ADRESSE] = 2; time.sleep(1.2)
verifier("le bouton start clignote", len(observer(L_START, 2.5)) > 1)
verifier("start clignote dans sa couleur", lu(L_START, "multi_intensity") == ORIGINE)
verifier("le bouton piece est rendu allume", observer(L_PIECE, 1.0) == {"255"})
verifier("piece a retrouve sa couleur", lu(L_PIECE, "multi_intensity") == ORIGINE,
         lu(L_PIECE, "multi_intensity"))

print("\n--- etat 3 : on appuie sur start, la partie demarre ---")
appui(cp.CODE_START); ra.credits(-1); time.sleep(1.5)
verifier("plus rien ne clignote (piece)", observer(L_PIECE, 1.5) == {"255"})
verifier("plus rien ne clignote (start)", observer(L_START, 1.5) == {"255"})
verifier("les deux couleurs sont d'origine",
         lu(L_PIECE, "multi_intensity") == ORIGINE and lu(L_START, "multi_intensity") == ORIGINE)

print("\n--- retour a zero : la borne rappelle qu'il faut une piece ---")
# La partie est lancee : la borne ne reclame une piece qu apres INACTIVITE
# secondes sans un appui — comme une vraie borne en attract.
ra.ram[ADRESSE] = 0; time.sleep(cp.INACTIVITE + 1.0)
verifier("le bouton piece reclignote en rouge",
         len(observer(L_PIECE, 2.5)) > 1 and lu(L_PIECE, "multi_intensity") == cp.COULEUR_PIECE)

print("\n--- sortie du jeu ---")
etat("endgame"); time.sleep(1.5)
verifier("tout est rendu : allume et couleur d'origine",
         lu(L_PIECE, "brightness") == "255" and lu(L_START, "brightness") == "255"
         and lu(L_PIECE, "multi_intensity") == ORIGINE
         and lu(L_START, "multi_intensity") == ORIGINE)

ra.stop = True
print("\n%s" % ("TOUT EST BON" if not echecs else "ECHECS : " + ", ".join(echecs)))
