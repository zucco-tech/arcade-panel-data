#!/usr/bin/env python3
"""Miroirs, format du fichier, et conversion d'une ancienne base."""
import os
import importlib.util, json, os, sys, threading, time, types
sys.path.insert(0, "/tmp/claude-1000/test")
from faux_retroarch import FauxRetroArch
# Les scripts sont dans le dossier parent de celui-ci : la suite doit
# tourner partout ou le projet est copie, pas seulement chez son auteur.
W = os.environ.get("ARCADE_CREDITS") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("cp", os.path.join(W, "credits(permanent).py"))
cp = importlib.util.module_from_spec(spec); spec.loader.exec_module(cp)

R = "/tmp/claude-1000/test/base"; os.system("rm -rf " + R); os.makedirs(R)
ADRESSE, MIROIR, PORT_RA, ORIG = 0x1234, 0x8080, 45800, "170 170 170"
def lampe(n):
    c = []
    for i in (1, 2):
        d = os.path.join(R, "%s_%d" % (n, i)); os.makedirs(d)
        open(os.path.join(d, "brightness"), "w").write("255")
        open(os.path.join(d, "multi_intensity"), "w").write(ORIG); c.append(d)
    return tuple(c)
PIECE, ST1, ST2 = lampe("p"), lampe("s1"), lampe("s2")
p1_l, p1_e = os.pipe()
ETAT, BASE = os.path.join(R, "es.inf"), os.path.join(R, "base.json")

# Une base a l'ancien format, comme celle qui est sur la borne aujourd'hui.
json.dump({"jeux": {"pzloop2": {"adresse": 1104, "adresse_hex": "0x0450",
                                "core": "FinalBurn Neo", "miroirs": ["0x80B1"],
                                "taille_ram": 65536, "verifie_insertion": True,
                                "verifie_consommation": True,
                                "releve_le": "2026-09-10"}},
           "pads": {}, "version": 1}, open(BASE, "w"), indent=2)

ra = FauxRetroArch(PORT_RA, adresse_credits=ADRESSE, jeu="miroirs",
                   miroirs=(MIROIR,)); ra.start()
cp.BASE, cp.LEDS_PIECE, cp.LEDS_START, cp.LEDS_START_P2 = BASE, PIECE, ST1, ST2
cp.RA_HOTE, cp.RA_PORT = "127.0.0.1", PORT_RA
cp.STATE_FILE, cp.JOURNAL = ETAT, os.path.join(R, "log")
cp.ouvrir_pads = lambda: {p1_l: "AllInOneP1"}
cp.signal = types.SimpleNamespace(signal=lambda *a: None, SIGTERM=15)
def appui(c): os.write(p1_e, cp.EV.pack(0, 0, cp.EV_KEY, c, 1))
with open(ETAT, "w") as fh:
    fh.write("Action=rungame\nSystemId=fbneo\nGame=Jeu Miroir\nPlayers=1-2\n")
echecs = []
def verifier(t, ok, det=""):
    print("%-56s %s %s" % (t, "OK" if ok else "ECHEC", det))
    if not ok: echecs.append(t)

ra.ram[ADRESSE] = 0; ra.ram[MIROIR] = 0
threading.Thread(target=cp.main, daemon=True).start(); time.sleep(3.0)

base = json.load(open(BASE))
print("--- conversion de l'ancienne base ---")
verifier("format annonce", base.get("format") == "recalbox-arcade-credits", base.get("format"))
verifier("version 3", base.get("version") == 3)
verifier("pzloop2 conserve (cle nue, faute de systeme connu)", "pzloop2" in base["jeux"])
verifier("son adresse est intacte",
         base["jeux"]["pzloop2"]["credits"]["adresse"] == 1104)
verifier("son miroir est conserve",
         base["jeux"]["pzloop2"]["credits"]["miroirs"] == ["0x80B1"])

print("\n--- apprentissage d'un jeu a compteur miroir ---")
for tour in range(6):
    ra.bruit(400); time.sleep(1.3)
    ra.credits(+1); appui(cp.CODE_PIECE); time.sleep(1.6)
    if "fbneo/miroirs" in json.load(open(BASE))["jeux"]: break
    ra.credits(-1); appui(cp.CODE_START); time.sleep(1.3); ra.credits(+1)

fiche = json.load(open(BASE))["jeux"].get("fbneo/miroirs")
verifier("le jeu a miroir est appris", fiche is not None)
if fiche:
    c = fiche["credits"]
    verifier("adresse = la plus petite", c["adresse"] == ADRESSE, c["adresse_hex"])
    verifier("miroir note", c["miroirs"] == ["0x%04X" % MIROIR], str(c["miroirs"]))
    verifier("nom du jeu present", fiche.get("nom") == "Jeu Miroir", str(fiche.get("nom")))
    verifier("systeme present", fiche.get("systeme") == "fbneo")
    verifier("core present", fiche.get("core") == "FinalBurn Neo", str(fiche.get("core")))
    verifier("taille RAM presente", fiche["ram"]["taille"] == 65536)
    verifier("date et methode de releve", bool(fiche["releve"]["le"]) and
             fiche["releve"]["methode"] == "apprentissage")
ra.stop = True
print("\n--- le fichier final ---")
print(json.dumps(json.load(open(BASE)), indent=2, ensure_ascii=False)[:1400])
print("\n%s" % ("TOUT EST BON" if not echecs else "ECHECS : " + ", ".join(echecs)))
