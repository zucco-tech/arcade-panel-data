#!/usr/bin/env python3
"""Seuls les boutons utiles s allument, dans leurs couleurs, et le joueur 2
reste noir sur un jeu solo."""
import importlib.util, os, sys, threading, time, types, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from faux_retroarch import FauxRetroArch


def _trouver(fichier):
    ici = os.path.dirname(os.path.abspath(__file__))
    for racine in (os.environ.get("ARCADE_CREDITS"), os.path.dirname(ici),
                   os.path.join(os.path.dirname(ici), "..", "borne"),
                   os.path.dirname(os.path.dirname(ici)), ici):
        if racine and os.path.exists(os.path.join(racine, fichier)):
            return os.path.join(racine, fichier)
    raise SystemExit("introuvable : %s" % fichier)


spec = importlib.util.spec_from_file_location("cp", _trouver("credits(permanent).py"))
cp = importlib.util.module_from_spec(spec); spec.loader.exec_module(cp)

R = "/tmp/claude-test-panneau"; os.system("rm -rf " + R); os.makedirs(R)
PORT_RA, ADRESSE, ORIG = 46300, 0x1234, "170 170 170"

def paires(prefixe):
    paires_ = []
    for n in range(1, 9):
        chemins = []
        for i in (1, 2):
            d = os.path.join(R, "%s_b%d_%d" % (prefixe, n, i)); os.makedirs(d)
            open(os.path.join(d, "brightness"), "w").write("255")
            open(os.path.join(d, "multi_intensity"), "w").write(ORIG)
            chemins.append(d)
        paires_.append(tuple(chemins))
    return paires_

def lampe(nom):
    c = []
    for i in (1, 2):
        d = os.path.join(R, "%s_%d" % (nom, i)); os.makedirs(d)
        open(os.path.join(d, "brightness"), "w").write("255")
        open(os.path.join(d, "multi_intensity"), "w").write(ORIG); c.append(d)
    return tuple(c)

cp.LEDS_JEU = {1: paires("p1"), 2: paires("p2")}
cp.LEDS_PIECE, cp.LEDS_START, cp.LEDS_START_P2 = lampe("pc"), lampe("s1"), lampe("s2")
lec, ecr = os.pipe()
ETAT = os.path.join(R, "es.inf"); BASE = os.path.join(R, "base.json")
BOUTONS = os.path.join(R, "boutons.json")
json.dump({"version": 3, "jeux": {"finalburn-neo/duo": {"jeu": "duo", "systeme": "fbneo",
           "core": "FinalBurn Neo", "credits": {"adresse": ADRESSE}}},
           "pistes": {}, "difficiles": {}}, open(BASE, "w"))
json.dump({"jeux": {
    "duo":  {"nombre": 2, "mode": "2P sim",
             "boutons": {"BUTTON1": {"couleur": "Blue", "fonction": "Attack"},
                         "BUTTON2": {"couleur": "Black", "fonction": "Jump"}}},
    "alterne": {"nombre": 2, "mode": "2P alt", "boutons": {}},
    "solo": {"nombre": 3, "mode": "1P", "boutons": {}}}}, open(BOUTONS, "w"))

ra = FauxRetroArch(PORT_RA, adresse_credits=ADRESSE, jeu="duo"); ra.start()
cp.BASE, cp.BASE_BOUTONS = BASE, BOUTONS
cp.RA_HOTE, cp.RA_PORT = "127.0.0.1", PORT_RA
cp.STATE_FILE, cp.JOURNAL = ETAT, os.path.join(R, "log")
cp.ouvrir_pads = lambda: {lec: "AllInOneP1"}
cp.signal = types.SimpleNamespace(signal=lambda *a: None, SIGTERM=15)

def etat(action, joueurs="1-2"):
    with open(ETAT, "w") as fh:
        fh.write("Action=%s\nSystemId=fbneo\nGame=Duo\nPlayers=%s\n" % (action, joueurs))
def lu(d, f): return open(os.path.join(d, f)).read().strip()
def etat_boutons(joueur):
    return [lu(cp.LEDS_JEU[joueur][n][0], "brightness") for n in range(8)]

echecs = []
def verifier(t, ok, det=""):
    print("%-54s %s %s" % (t, "OK" if ok else "ECHEC", det))
    if not ok: echecs.append(t)

etat("rungame"); ra.ram[ADRESSE] = 0
threading.Thread(target=cp.main, daemon=True).start(); time.sleep(3.0)

print("--- jeu a 2 boutons, jouable a deux ---")
allumes = etat_boutons(1)
# ORDRE_BOUTONS = [3,4,5,1,2,6,7,8] : les boutons 1 et 2 sont en position 4 et 5
attendu = ["0", "0", "0", "255", "255", "0", "0", "0"]
verifier("seuls les 2 boutons utiles sont allumes", allumes == attendu, str(allumes))
couleur_b1 = lu(cp.LEDS_JEU[1][3][0], "multi_intensity")
verifier("le bouton 1 est bleu", couleur_b1 == cp.couleur(0x00, 0x00, 0xFF), couleur_b1)
verifier("le panneau du joueur 2 est allume aussi",
         etat_boutons(2) == attendu, str(etat_boutons(2)))

print("\n--- jeu a deux mais en alterne ---")
etat("endgame"); time.sleep(1.2)
ra.jeu = "alterne"; ra.ram[ADRESSE] = 0
json.dump({"version": 3, "jeux": {"finalburn-neo/alterne": {"jeu": "alterne", "systeme": "fbneo",
           "core": "FinalBurn Neo", "credits": {"adresse": ADRESSE}}},
           "pistes": {}, "difficiles": {}}, open(BASE, "w"))
etat("rungame", joueurs="1-2"); time.sleep(3.0)
verifier("joueur 2 eteint malgre un jeu a deux",
         set(etat_boutons(2)) == {"0"}, str(etat_boutons(2)))

print("\n--- meme jeu declare solo ---")
etat("endgame"); time.sleep(1.2)
ra.jeu = "solo"; ra.ram[ADRESSE] = 0
json.dump({"version": 3, "jeux": {"finalburn-neo/solo": {"jeu": "solo", "systeme": "fbneo",
           "core": "FinalBurn Neo", "credits": {"adresse": ADRESSE}}},
           "pistes": {}, "difficiles": {}}, open(BASE, "w"))
etat("rungame", joueurs="1"); time.sleep(3.0)
verifier("le joueur 2 est entierement eteint",
         set(etat_boutons(2)) == {"0"}, str(etat_boutons(2)))
verifier("le joueur 1 a bien ses 3 boutons",
         etat_boutons(1).count("255") == 3, str(etat_boutons(1)))

print("\n--- sortie du jeu ---")
etat("endgame"); time.sleep(1.5)
verifier("tout est rendu allume", set(etat_boutons(1)) == {"255"} and set(etat_boutons(2)) == {"255"})
verifier("et les couleurs d origine aussi",
         lu(cp.LEDS_JEU[1][3][0], "multi_intensity") == ORIG)
ra.stop = True
print("\n%s" % ("TOUT EST BON" if not echecs else "ECHECS : " + ", ".join(echecs)))
