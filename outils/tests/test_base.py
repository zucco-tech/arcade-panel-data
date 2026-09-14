#!/usr/bin/env python3
"""Miroirs, format du fichier appris, et cohabitation avec les fichiers du PC."""
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

R = tempfile.mkdtemp(prefix="base-")            # un dossier neuf, nettoye par le systeme
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
ETAT = os.path.join(R, "es.inf")
CREDITS = os.path.join(R, "credits"); os.makedirs(CREDITS)
APPRIS = os.path.join(CREDITS, "appris.json")
# Un fichier depose par le PC, avec une fiche ; la borne n y ecrit jamais.
DU_PC = os.path.join(CREDITS, "fbneo.json")
json.dump({"systeme": "fbneo", "jeux": {"pzloop2": {"jeu": "pzloop2", "core": "FinalBurn Neo",
           "credits": {"adresse": 1104, "adresse_hex": "0x0450", "miroirs": ["0x80B1"]}}},
           "difficiles": {}}, open(DU_PC, "w"), indent=2)
EMPREINTE = open(DU_PC).read()

ra = FauxRetroArch(PORT_RA, adresse_credits=ADRESSE, jeu="miroirs",
                   miroirs=(MIROIR,)); ra.start()
cp.DOSSIER_CREDITS, cp.LEDS_PIECE, cp.LEDS_START, cp.LEDS_START_P2 = CREDITS, PIECE, ST1, ST2
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

print("--- les fichiers du PC ---")
base = cp.Base(CREDITS)
verifier("le systeme du PC est vu", base.systemes() == ["fbneo"], str(base.systemes()))
verifier("sa fiche est lue par nom de set",
         cp.adresse_de(base.fiche("fbneo", "pzloop2")) == 1104)
verifier("un jeu inconnu : rien", base.fiche("fbneo", "inconnu") is None)
verifier("rien n'est encore appris", not os.path.exists(APPRIS))

print("\n--- apprentissage d'un jeu a compteur miroir ---")
for tour in range(6):
    ra.bruit(400); time.sleep(1.3)
    ra.credits(+1); appui(cp.CODE_PIECE); time.sleep(1.6)
    if os.path.exists(APPRIS) and "fbneo/miroirs" in json.load(open(APPRIS))["jeux"]: break
    ra.credits(-1); appui(cp.CODE_START); time.sleep(1.3); ra.credits(+1)

appris = json.load(open(APPRIS)) if os.path.exists(APPRIS) else {"jeux": {}}
fiche = appris["jeux"].get("fbneo/miroirs")
verifier("le jeu a miroir est appris", fiche is not None)
verifier("format du fichier appris annonce", "appris" in str(appris.get("format")), str(appris.get("format")))
verifier("version 3", appris.get("version") == 3)
verifier("le fichier du PC n'a pas ete touche", open(DU_PC).read() == EMPREINTE)
verifier("la fiche apprise est vue par la base", cp.adresse_de(cp.Base(CREDITS).fiche("fbneo", "miroirs")) == ADRESSE)
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
print(json.dumps(appris, indent=2, ensure_ascii=False)[:1400])
print("\n%s" % ("TOUT EST BON" if not echecs else "ECHECS : " + ", ".join(echecs)))
