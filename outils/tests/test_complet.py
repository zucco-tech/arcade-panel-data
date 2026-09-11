#!/usr/bin/env python3
"""Un seul script sur le Pi : il doit apprendre, PUIS faire clignoter."""
import os
import importlib.util, json, os, socket, sys, threading, time, types
sys.path.insert(0, "/tmp/claude-1000/test")
from faux_retroarch import FauxRetroArch

# Les scripts sont dans le dossier parent de celui-ci : la suite doit
# tourner partout ou le projet est copie, pas seulement chez son auteur.
W = os.environ.get("ARCADE_CREDITS") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("cp", os.path.join(W, "credits(permanent).py"))
cp = importlib.util.module_from_spec(spec); spec.loader.exec_module(cp)

RACINE = "/tmp/claude-1000/test/pi"; os.system("rm -rf " + RACINE); os.makedirs(RACINE)
ADRESSE, PORT_RA = 0x1234, 45400

leds = []
for nom in ("aio_p1_select_1", "aio_p1_select_2"):
    d = os.path.join(RACINE, nom); os.makedirs(d)
    open(os.path.join(d, "brightness"), "w").write("255")
    open(os.path.join(d, "multi_intensity"), "w").write("170 170 170"); leds.append(d)
leds2 = []
for nom in ("aio_p1_x_1", "aio_p1_x_2"):
    d = os.path.join(RACINE, nom); os.makedirs(d)
    open(os.path.join(d, "brightness"), "w").write("255")
    open(os.path.join(d, "multi_intensity"), "w").write("170 170 170"); leds2.append(d)

lecture, ecriture = os.pipe()
ETAT = os.path.join(RACINE, "es_state.inf")
BASE = os.path.join(RACINE, "credits-arcade.json")     # volontairement absent

ra = FauxRetroArch(PORT_RA, adresse_credits=ADRESSE); ra.start()
cp.BASE = BASE
cp.LEDS_PIECE, cp.LEDS_START = tuple(leds), tuple(leds2)
cp.RA_HOTE, cp.RA_PORT = "127.0.0.1", PORT_RA
cp.STATE_FILE, cp.JOURNAL = ETAT, os.path.join(RACINE, "credits.log")
cp.ouvrir_pads = lambda: {lecture: "AllInOneP1"}
cp.signal = types.SimpleNamespace(signal=lambda *a: None, SIGTERM=15)
cp.INACTIVITE = 4.0

def appui(code): os.write(ecriture, cp.EV.pack(0, 0, cp.EV_KEY, code, 1))
def etat(action):
    with open(ETAT, "w") as fh: fh.write("Action=%s\nSystemId=fbneo\n" % action)
def brightness(): return open(os.path.join(leds[0], "brightness")).read().strip()
def observer(duree):
    vues, fin = [], time.time() + duree
    while time.time() < fin:
        v = brightness()
        if not vues or vues[-1] != v: vues.append(v)
        time.sleep(0.05)
    return vues

echecs = []
def verifier(titre, ok, detail=""):
    print("%-48s %s %s" % (titre, "OK" if ok else "ECHEC", detail))
    if not ok: echecs.append(titre)

print("--- partie 1 : le jeu est inconnu, le script doit apprendre ---")
etat("rungame"); ra.ram[ADRESSE] = 0
threading.Thread(target=cp.main, daemon=True).start()
time.sleep(3.0)                      # resolution du jeu + photo de reference
verifier("base absente au depart : rien n'est invente", not os.path.exists(BASE))
verifier("jeu inconnu : la LED ne clignote pas", set(observer(1.5)) == {"255"})

t0 = time.time()
for tour in range(8):
    ra.bruit(400); time.sleep(1.3)
    ra.credits(+1); appui(cp.CODE_PIECE); time.sleep(1.6)
    base = json.load(open(BASE)) if os.path.exists(BASE) else {"jeux": {}}
    if "fbneo/testgame" in base.get("jeux", {}): break
    ra.credits(-1); appui(cp.CODE_START); time.sleep(1.2)
    ra.credits(+1)                    # on remet le credit consomme pour la suite
duree = time.time() - t0

base = json.load(open(BASE)) if os.path.exists(BASE) else {"jeux": {}}
fiche = base.get("jeux", {}).get("fbneo/testgame")
verifier("le jeu a ete appris", fiche is not None, "en %.0f s" % duree)
if fiche:
    verifier("adresse correcte", fiche["credits"]["adresse"] == ADRESSE, fiche["credits"]["adresse_hex"])
    verifier("consommation START verifiee", fiche["credits"].get("verifie_consommation") is True)

print("\n--- partie 2 : le jeu est connu, la LED doit suivre ---")
ra.ram[ADRESSE] = 0
time.sleep(cp.INACTIVITE + 1.5)      # game over : le panneau se tait
verifier("0 credit + panneau silencieux : ca clignote", len(set(observer(2.5))) > 1)
ra.ram[ADRESSE] = 5; time.sleep(1.2)
verifier("5 credits : la LED reste allumee", set(observer(2.0)) == {"255"})

print("\n--- partie 3 : sortie de jeu ---")
etat("endgame"); time.sleep(1.5)
verifier("LED rendue allumee", brightness() == "255")

ra.stop = True
print("\ncommandes RetroArch pour tout le test : %d" % ra.commandes)
print("\njournal de la borne :\n" + open(cp.JOURNAL).read().strip())
print("\n%s" % ("TOUT EST BON" if not echecs else "ECHECS : " + ", ".join(echecs)))
