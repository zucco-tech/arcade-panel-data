#!/usr/bin/env python3
"""Cycle complet, joueur 2 compris, avec apprentissage du nombre de joueurs."""
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

R = "/tmp/claude-1000/test/j2"; os.system("rm -rf " + R); os.makedirs(R)
ADRESSE, PORT_RA, ORIG = 0x1234, 45700, "170 170 170"
def lampe(n):
    c = []
    for i in (1, 2):
        d = os.path.join(R, "%s_%d" % (n, i)); os.makedirs(d)
        open(os.path.join(d, "brightness"), "w").write("255")
        open(os.path.join(d, "multi_intensity"), "w").write(ORIG); c.append(d)
    return tuple(c)
PIECE, ST1, ST2 = lampe("piece"), lampe("start1"), lampe("start2")
p1_l, p1_e = os.pipe(); p2_l, p2_e = os.pipe()
ETAT = os.path.join(R, "es.inf")
CREDITS = os.path.join(R, "credits"); os.makedirs(CREDITS)
APPRIS = os.path.join(CREDITS, "appris.json")     # ce que la borne apprend
json.dump({"jeux": {"deuxjoueurs": {"credits": {"adresse": ADRESSE}},
                    "solo": {"credits": {"adresse": ADRESSE}}}}, open(os.path.join(CREDITS, "fbneo.json"), "w"))
ra = FauxRetroArch(PORT_RA, adresse_credits=ADRESSE, jeu="deuxjoueurs"); ra.start()
cp.DOSSIER_CREDITS = CREDITS
cp.LEDS_PIECE, cp.LEDS_START, cp.LEDS_START_P2 = PIECE, ST1, ST2
cp.RA_HOTE, cp.RA_PORT = "127.0.0.1", PORT_RA
cp.STATE_FILE, cp.JOURNAL = ETAT, os.path.join(R, "log")
cp.ouvrir_pads = lambda: {p1_l: "AllInOneP1", p2_l: "AllInOneP2"}
cp.signal = types.SimpleNamespace(signal=lambda *a: None, SIGTERM=15)
cp.INACTIVITE = 6.0
def appui(t, c): os.write(t, cp.EV.pack(0, 0, cp.EV_KEY, c, 1))
def etat(a, joueurs="1-2"):
    with open(ETAT, "w") as fh:
        fh.write("Action=%s\nSystemId=fbneo\nPlayers=%s\n" % (a, joueurs))
def lu(c): return open(os.path.join(c[0], "brightness")).read().strip()
def coul(c): return open(os.path.join(c[0], "multi_intensity")).read().strip()
def observer(c, duree, jouer=False):
    v, fin = [], time.time() + duree
    while time.time() < fin:
        x = lu(c)
        if not v or v[-1] != x: v.append(x)
        if jouer: appui(p1_e, 304)
        time.sleep(0.05)
    return set(v)
echecs = []
def verifier(t, ok, det=""):
    print("%-58s %s %s" % (t, "OK" if ok else "ECHEC", det))
    if not ok: echecs.append(t)

etat("rungame"); ra.ram[ADRESSE] = 0
threading.Thread(target=cp.main, daemon=True).start(); time.sleep(1.5)

print("--- attract, puis une piece ---")
verifier("piece clignote rouge", len(observer(PIECE, 1.5)) > 1 and coul(PIECE) == cp.COULEUR_PIECE)
ra.credits(+1); appui(p1_e, cp.CODE_PIECE); time.sleep(1.0)
verifier("start J1 clignote", len(observer(ST1, 1.5)) > 1)

print("\n--- J1 lance : le J2 ne doit PAS clignoter dans la foulee ---")
appui(p1_e, cp.CODE_START); ra.credits(-1)
verifier("aucun clignotement fugace du J2", observer(ST2, cp.DELAI_J2, jouer=True) == {"255"})
verifier("ni du piece malgre 0 credit", observer(PIECE, 1.0, jouer=True) == {"255"})

print("\n--- une piece pendant la partie : on appelle le J2 ---")
ra.credits(+1); appui(p1_e, cp.CODE_PIECE); time.sleep(1.0)
verifier("start J2 clignote", len(observer(ST2, 2.0, jouer=True)) > 1)

print("\n--- le J2 appuie et le jeu consomme : 2 joueurs constate ---")
appui(p2_e, cp.CODE_START); time.sleep(0.4); ra.credits(-1); time.sleep(1.5)
verifier("start J2 s'arrete", observer(ST2, 1.5, jouer=True) == {"255"})
fiche = json.load(open(APPRIS))["jeux"]["fbneo/deuxjoueurs"]
verifier("la base note : joueur 2 accepte", (fiche.get("joueurs") or {}).get("joueur2_accepte") is True, str(fiche.get("joueurs")))

print("\n--- autre jeu, annonce 2 joueurs par le scrapeur, mais solo ---")
etat("endgame"); time.sleep(1.0)
ra.jeu = "solo"; ra.ram[ADRESSE] = 2
etat("rungame", joueurs="1-2"); time.sleep(1.5)
appui(p1_e, cp.CODE_START); ra.credits(-1); time.sleep(cp.DELAI_J2 + 1.0)
verifier("le J2 est appele (le scrapeur dit 2)", len(observer(ST2, 2.0, jouer=True)) > 1)
print("    le joueur 2 appuie... le jeu ne consomme rien")
appui(p2_e, cp.CODE_START); time.sleep(cp.VERDICT_J2 + 1.5)
fiche = json.load(open(APPRIS))["jeux"]["fbneo/solo"]
verifier("la base corrige : joueur 2 refuse", (fiche.get("joueurs") or {}).get("joueur2_accepte") is False, str(fiche.get("joueurs")))
verifier("le J2 n'est plus appele", observer(ST2, 2.0, jouer=True) == {"255"})

print("\n--- et ca tient d'une partie sur l'autre ---")
etat("endgame"); time.sleep(1.0)
etat("rungame", joueurs="1-2"); ra.ram[ADRESSE] = 3; time.sleep(1.5)
appui(p1_e, cp.CODE_START); ra.credits(-1); time.sleep(cp.DELAI_J2 + 1.0)
verifier("jeu marque solo : le J2 reste eteint", observer(ST2, 2.0, jouer=True) == {"255"})

etat("endgame"); time.sleep(1.2)
verifier("sortie : tout rendu",
         all(lu(c) == "255" for c in (PIECE, ST1, ST2))
         and all(coul(c) == ORIG for c in (PIECE, ST1, ST2)))
ra.stop = True
print("\njournal :\n" + open(cp.JOURNAL).read().strip())
print("\n%s" % ("TOUT EST BON" if not echecs else "ECHECS : " + ", ".join(echecs)))
