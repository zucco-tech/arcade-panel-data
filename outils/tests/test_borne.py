#!/usr/bin/env python3
"""Teste credits(permanent).py : LED, envoi d'evenements, reception de fiche."""
import os
import importlib.util, json, os, socket, struct, sys, threading, time, types
sys.path.insert(0, "/tmp/claude-1000/test")
from faux_retroarch import FauxRetroArch

# Les scripts sont dans le dossier parent de celui-ci : la suite doit
# tourner partout ou le projet est copie, pas seulement chez son auteur.
W = os.environ.get("ARCADE_CREDITS") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("cp", os.path.join(W, "credits(permanent).py"))
cp = importlib.util.module_from_spec(spec); spec.loader.exec_module(cp)

RACINE = "/tmp/claude-1000/test/borne"
os.makedirs(RACINE, exist_ok=True)
ADRESSE, PORT_RA, PORT_LXC, PORT_ECOUTE = 0x1234, 45356, 45106, 45107

# --- fausses LED
leds = []
for nom in ("aio_p1_select_1", "aio_p1_select_2"):
    d = os.path.join(RACINE, nom); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "brightness"), "w").write("255")
    leds.append(d)

# --- fausses manettes : un tube fait tres bien l'affaire
lecture, ecriture = os.pipe()
def envoyer_appui(code):
    os.write(ecriture, cp.EV.pack(0, 0, cp.EV_KEY, code, 1))

# --- faux frontend
ETAT = os.path.join(RACINE, "es_state.inf")
def poser_etat(action, systeme="fbneo"):
    with open(ETAT, "w") as fh:
        fh.write("Action=%s\nSystemId=%s\nGame=Test\n" % (action, systeme))

BASE = os.path.join(RACINE, "credits-arcade.json")
json.dump({"version": 1, "jeux": {"testgame": {"adresse": ADRESSE}}, "pads": {}},
          open(BASE, "w"))

# --- branchements
ra = FauxRetroArch(PORT_RA, adresse_credits=ADRESSE); ra.start()
cp.BASE, cp.LEDS_COIN = BASE, tuple(leds)
cp.RA_HOTE, cp.RA_PORT = "127.0.0.1", PORT_RA
cp.LXC_HOTE, cp.LXC_PORT, cp.ECOUTE_PORT = "127.0.0.1", PORT_LXC, PORT_ECOUTE
cp.STATE_FILE, cp.JOURNAL = ETAT, os.path.join(RACINE, "credits.log")
cp.ouvrir_pads = lambda: {lecture: "AllInOneP1"}
cp.signal = types.SimpleNamespace(signal=lambda *a: None, SIGTERM=15)

recus = []
def lxc_ecoute():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", PORT_LXC)); s.settimeout(20)
    while True:
        try: recus.append(json.loads(s.recvfrom(4096)[0].decode()))
        except socket.timeout: return
threading.Thread(target=lxc_ecoute, daemon=True).start()

def brightness():
    return [open(os.path.join(d, "brightness")).read().strip() for d in leds]

def observer(duree):
    """Suit la LED et renvoie les valeurs distinctes vues."""
    vues, fin = [], time.time() + duree
    while time.time() < fin:
        v = brightness()[0]
        if not vues or vues[-1] != v: vues.append(v)
        time.sleep(0.05)
    return vues

echecs = []
def verifier(titre, condition, detail=""):
    print("%-46s %s %s" % (titre, "OK" if condition else "ECHEC", detail))
    if not condition: echecs.append(titre)

poser_etat("rungame")
ra.ram[ADRESSE] = 0
threading.Thread(target=cp.main, daemon=True).start()
time.sleep(2.0)

vues = observer(2.5)
verifier("0 credit : la LED clignote", len(set(vues)) > 1, "vu %s" % vues)

ra.ram[ADRESSE] = 3
time.sleep(1.5)
vues = observer(2.0)
verifier("3 credits : la LED reste allumee", set(vues) == {"255"}, "vu %s" % vues)

ra.ram[ADRESSE] = 0
time.sleep(1.2)
vues = observer(2.5)
verifier("retour a 0 : elle reclignote", len(set(vues)) > 1, "vu %s" % vues)

envoyer_appui(cp.CODE_PIECE); time.sleep(0.8)
envoyer_appui(cp.CODE_START); time.sleep(0.8)
evs = [r.get("ev") for r in recus]
verifier("l'appui piece part vers le LXC", "piece" in evs, str(evs))
verifier("l'appui start part vers le LXC", "start" in evs, str(evs))

# fiche apprise, envoyee par le LXC
env = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
env.sendto(json.dumps({"jeu": "autrejeu", "fiche": {"adresse": 0x4321,
           "adresse_hex": "0x4321"}}).encode(), ("127.0.0.1", PORT_ECOUTE))
time.sleep(1.0)
jeux = json.load(open(BASE)).get("jeux", {})
verifier("la fiche recue est rangee dans la base", jeux.get("autrejeu", {}).get("adresse") == 0x4321)
verifier("l'ancienne fiche est preservee", "testgame" in jeux)

poser_etat("endgame"); time.sleep(1.5)
verifier("fin de partie : LED rendue allumee", brightness() == ["255", "255"], str(brightness()))

ra.stop = True
print("\ncommandes RetroArch en %d s de test : %d" % (14, ra.commandes))
print("journal :"); print(open(cp.JOURNAL).read().strip())
print("\n%s" % ("TOUT EST BON" if not echecs else "ECHECS : " + ", ".join(echecs)))
