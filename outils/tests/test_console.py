#!/usr/bin/env python3
"""Les jeux console : START clignote jusqu au premier appui, puis plus rien.

Demande du 24/09/2026 : « faire clignoter START sur les jeux console qui
attendent un appui a l ecran-titre, comme le fait une borne d arcade ». Il n y
a pas de credit a compter sur console : l invitation s arrete des que le joueur
repond. Ce banc verifie aussi qu un jeu d ARCADE ne tombe pas dans cette regle.
"""
import os, tempfile
import importlib.util, json, sys, threading, time, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
W = os.environ.get("ARCADE_CREDITS") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "borne", "share", "userscripts")
spec = importlib.util.spec_from_file_location("cp", os.path.join(W, "credits(permanent).py"))
cp = importlib.util.module_from_spec(spec); spec.loader.exec_module(cp)

RACINE = tempfile.mkdtemp(prefix="console-")
ORIGINE = "170 170 170"
def lampe(nom):
    c = []
    for i in (1, 2):
        d = os.path.join(RACINE, "%s_%d" % (nom, i)); os.makedirs(d)
        open(os.path.join(d, "brightness"), "w").write("255")
        open(os.path.join(d, "multi_intensity"), "w").write(ORIGINE); c.append(d)
    return tuple(c)
L_PIECE, L_START = lampe("piece"), lampe("start")
lecture, ecriture = os.pipe()
ETAT = os.path.join(RACINE, "es.inf")
CREDITS = os.path.join(RACINE, "credits"); os.makedirs(CREDITS)
json.dump({"jeux": {}}, open(os.path.join(CREDITS, "fbneo.json"), "w"))
cp.DOSSIER_CREDITS, cp.LEDS_PIECE, cp.LEDS_START = CREDITS, L_PIECE, L_START
cp.STATE_FILE, cp.JOURNAL = ETAT, os.path.join(RACINE, "log")
cp.ouvrir_pads = lambda: {lecture: "AllInOneP1"}
cp.signal = types.SimpleNamespace(signal=lambda *a: None, SIGTERM=15)

def appui(code): os.write(ecriture, cp.EV.pack(0, 0, cp.EV_KEY, code, 1))
def etat(action, systeme):
    with open(ETAT, "w") as fh: fh.write("Action=%s\nSystemId=%s\n" % (action, systeme))
def lu(c): return open(os.path.join(c[0], "brightness")).read().strip()
def observer(c, d):
    v, fin = [], time.time() + d
    while time.time() < fin:
        x = lu(c)
        if not v or v[-1] != x: v.append(x)
        time.sleep(0.05)
    return set(v)
echecs = []
def verifier(t, ok, det=""):
    print("%-54s %s %s" % (t, "OK" if ok else "ECHEC", det)); (echecs.append(t) if not ok else None)

# Le delai laisse passer le logo de la machine. On compte le temps a partir du
# moment ou le demon LIT l etat, pas du lancement du fil : sous charge il met
# une seconde ou deux a demarrer, et un banc qui compte depuis le fil devient
# faux des que la machine travaille (constate le 30/09 : vert seul, rouge dans
# la serie). On demarre donc le demon hors jeu, puis on lance le jeu.
cp.DELAI_CONSOLE = 2.5

etat("endgame", "snes")
threading.Thread(target=cp.main, daemon=True).start(); time.sleep(1.5)
print("--- un jeu SNES vient de se lancer : le logo passe d abord ---")
etat("rungame", "snes"); time.sleep(0.4)     # le demon a lu l etat
verifier("rien ne clignote pendant le delai", observer(L_START, 1.5) == {"255"})
time.sleep(1.2)                              # le delai est ecoule
print("\n--- l ecran-titre attend un appui ---")
verifier("START clignote", len(observer(L_START, 2.0)) > 1)
verifier("PIECE ne clignote pas (pas de monnayeur)", observer(L_PIECE, 1.0) == {"255"})

print("\n--- le joueur appuie ---")
appui(cp.CODE_START); time.sleep(1.0)
verifier("START se calme et reste allume", observer(L_START, 2.0) == {"255"})
verifier("sa couleur d origine est rendue",
         open(os.path.join(L_START[0], "multi_intensity")).read().strip() == ORIGINE)

print("\n--- on sort du jeu ---")
etat("endgame", "snes"); time.sleep(1.2)
verifier("rien ne clignote hors jeu", observer(L_START, 1.5) == {"255"})

print("\n--- un jeu d ARCADE sans fiche : la regle console ne s applique pas ---")
etat("rungame", "fbneo"); time.sleep(1.5)
verifier("START ne clignote pas sur un jeu arcade inconnu", observer(L_START, 2.0) == {"255"})

print()
if echecs:
    print("ECHECS : %s" % echecs); sys.exit(1)
print("TOUT EST BON")          # la formule que tout.sh attend
