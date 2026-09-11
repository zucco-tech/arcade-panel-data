#!/usr/bin/env python3
"""Le cas signale : START consomme le credit, plus rien ne doit clignoter."""
import os
import importlib.util, json, os, sys, threading, time, types
sys.path.insert(0, "/tmp/claude-1000/test")
from faux_retroarch import FauxRetroArch
def _trouver(fichier):
    """Retrouve un script du projet, quelle que soit la disposition.

    Le depot separe le demon de la borne (borne/) des outils de releve
    (outils/), mais tout peut aussi vivre a plat. On cherche donc dans les
    endroits plausibles plutot que de figer un chemin.
    """
    ici = os.path.dirname(os.path.abspath(__file__))
    racines = [os.environ.get("ARCADE_CREDITS"),
               os.path.dirname(ici),                       # outils/
               os.path.join(os.path.dirname(ici), "..", "borne"),
               os.path.dirname(os.path.dirname(ici)),      # racine du depot
               ici]
    for racine in racines:
        if racine and os.path.exists(os.path.join(racine, fichier)):
            return os.path.join(racine, fichier)
    raise SystemExit("introuvable : %s" % fichier)
spec = importlib.util.spec_from_file_location("cp", _trouver("credits(permanent).py"))
cp = importlib.util.module_from_spec(spec); spec.loader.exec_module(cp)

RACINE = "/tmp/claude-1000/test/partie"; os.system("rm -rf " + RACINE); os.makedirs(RACINE)
ADRESSE, PORT_RA, ORIGINE = 0x1234, 45600, "170 170 170"
def lampe(nom):
    c = []
    for i in (1, 2):
        d = os.path.join(RACINE, "%s_%d" % (nom, i)); os.makedirs(d)
        open(os.path.join(d, "brightness"), "w").write("255")
        open(os.path.join(d, "multi_intensity"), "w").write(ORIGINE); c.append(d)
    return tuple(c)
L_PIECE, L_START = lampe("piece"), lampe("start")
lecture, ecriture = os.pipe()
ETAT, BASE = os.path.join(RACINE, "es.inf"), os.path.join(RACINE, "base.json")
json.dump({"version": 1, "jeux": {"testgame": {"adresse": ADRESSE}}}, open(BASE, "w"))
ra = FauxRetroArch(PORT_RA, adresse_credits=ADRESSE); ra.start()
cp.BASE, cp.LEDS_PIECE, cp.LEDS_START = BASE, L_PIECE, L_START
cp.RA_HOTE, cp.RA_PORT = "127.0.0.1", PORT_RA
cp.STATE_FILE, cp.JOURNAL = ETAT, os.path.join(RACINE, "log")
cp.ouvrir_pads = lambda: {lecture: "AllInOneP1"}
cp.signal = types.SimpleNamespace(signal=lambda *a: None, SIGTERM=15)
cp.INACTIVITE = 4.0                      # 45 s en vrai, 4 s pour le test
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
