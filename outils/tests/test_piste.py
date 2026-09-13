#!/usr/bin/env python3
"""Une piste issue du pack de cheats doit se confirmer des la 1re piece."""
import os
import importlib.util, json, os, sys, threading, time, types
sys.path.insert(0, "/tmp/claude-1000/test")
from faux_retroarch import FauxRetroArch
# Les scripts sont dans le dossier parent de celui-ci : la suite doit
# tourner partout ou le projet est copie, pas seulement chez son auteur.
W = os.environ.get("ARCADE_CREDITS") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("cp", os.path.join(W, "credits(permanent).py"))
cp = importlib.util.module_from_spec(spec); spec.loader.exec_module(cp)

R = "/tmp/claude-1000/test/piste"; os.system("rm -rf " + R); os.makedirs(R)
PORT_RA, ORIG = 45900, "170 170 170"
# Le compteur est en 0x80B1 ; le cheat, lui, annonce 0xFF80B0 (XOR 1).
ADRESSE, CHEAT = 0x80B1, "0xFF80B0"
def lampe(n):
    c = []
    for i in (1, 2):
        d = os.path.join(R, "%s_%d" % (n, i)); os.makedirs(d)
        open(os.path.join(d, "brightness"), "w").write("255")
        open(os.path.join(d, "multi_intensity"), "w").write(ORIG); c.append(d)
    return tuple(c)
P, S1, S2 = lampe("p"), lampe("s1"), lampe("s2")
lec, ecr = os.pipe()
ETAT = os.path.join(R, "es.inf")
CREDITS = os.path.join(R, "credits"); os.makedirs(CREDITS)
APPRIS = os.path.join(CREDITS, "appris.json")
# Les pistes viennent du PC, dans leur propre fichier.
json.dump({"pistes": {"jeupiste": {"cheat": CHEAT, "source": "FBNeo-cheats"},
                      "jeufausse": {"cheat": "0xFF1000", "source": "FBNeo-cheats"}}},
          open(os.path.join(CREDITS, "pistes.json"), "w"))
ra = FauxRetroArch(PORT_RA, adresse_credits=ADRESSE, jeu="jeupiste"); ra.start()
cp.DOSSIER_CREDITS, cp.LEDS_PIECE, cp.LEDS_START, cp.LEDS_START_P2 = CREDITS, P, S1, S2
cp.RA_HOTE, cp.RA_PORT = "127.0.0.1", PORT_RA
cp.STATE_FILE, cp.JOURNAL = ETAT, os.path.join(R, "log")
cp.ouvrir_pads = lambda: {lec: "AllInOneP1"}
cp.signal = types.SimpleNamespace(signal=lambda *a: None, SIGTERM=15)
def appui(c): os.write(ecr, cp.EV.pack(0, 0, cp.EV_KEY, c, 1))
with open(ETAT, "w") as fh: fh.write("Action=rungame\nSystemId=fbneo\nGame=Jeu Piste\n")
echecs = []
def verifier(t, ok, d=""):
    print("%-54s %s %s" % (t, "OK" if ok else "ECHEC", d))
    if not ok: echecs.append(t)

ra.ram[ADRESSE] = 0
threading.Thread(target=cp.main, daemon=True).start(); time.sleep(3.0)
avant = ra.commandes
ra.credits(+1); appui(cp.CODE_PIECE); time.sleep(2.0)
cout = ra.commandes - avant

fiche = json.load(open(APPRIS))["jeux"].get("fbneo/jeupiste")
verifier("appris des la 1re piece", fiche is not None)
if fiche:
    verifier("bonne adresse", fiche["credits"]["adresse"] == ADRESSE,
             fiche["credits"]["adresse_hex"])
    verifier("methode notee", fiche["releve"]["methode"] == "piste confirmee",
             fiche["releve"]["methode"])
journal = open(cp.JOURNAL).read()
verifier("aucune photo prise pour ce jeu",
         "jeupiste : piece 1 ->" not in journal and "jeupiste : 65536 octets" not in journal,
         "%d commandes en tout" % cout)

print("\n--- une piste fausse doit basculer sur la recherche complete ---")
ra.jeu = "jeufausse"; ra.adresse = 0x2222; ra.ram[0x2222] = 0
with open(ETAT, "w") as fh: fh.write("Action=endgame\nSystemId=fbneo\n")
time.sleep(1.0)
with open(ETAT, "w") as fh: fh.write("Action=rungame\nSystemId=fbneo\nGame=Fausse\n")
time.sleep(2.5)
for tour in range(6):
    ra.bruit(300); time.sleep(1.2)
    ra.credits(+1); appui(cp.CODE_PIECE); time.sleep(1.6)
    if "fbneo/jeufausse" in json.load(open(APPRIS))["jeux"]: break
    ra.credits(-1); appui(cp.CODE_START); time.sleep(1.2); ra.credits(+1)
f2 = json.load(open(APPRIS))["jeux"].get("fbneo/jeufausse")
verifier("le jeu est quand meme appris", f2 is not None)
if f2:
    verifier("adresse reelle trouvee", f2["credits"]["adresse"] == 0x2222,
             f2["credits"]["adresse_hex"])
ra.stop = True
print("\njournal :\n" + open(cp.JOURNAL).read().strip())
print("\n%s" % ("TOUT EST BON" if not echecs else "ECHECS : " + ", ".join(echecs)))
