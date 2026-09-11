#!/usr/bin/env python3
"""Le meme set sous deux systemes ne doit pas ecraser sa propre fiche."""
import os
import importlib.util, json, os, sys, threading, time, types
sys.path.insert(0, "/tmp/claude-1000/test")
from faux_retroarch import FauxRetroArch
# Les scripts sont dans le dossier parent de celui-ci : la suite doit
# tourner partout ou le projet est copie, pas seulement chez son auteur.
W = os.environ.get("ARCADE_CREDITS") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("cp", os.path.join(W, "credits(permanent).py"))
cp = importlib.util.module_from_spec(spec); spec.loader.exec_module(cp)

R = "/tmp/claude-1000/test/collision"; os.system("rm -rf " + R); os.makedirs(R)
PORT_RA, ORIG = 46100, "170 170 170"
ADR_FBNEO, ADR_MAME = 0x1234, 0x5678
def lampe(n):
    c = []
    for i in (1, 2):
        d = os.path.join(R, "%s_%d" % (n, i)); os.makedirs(d)
        open(os.path.join(d, "brightness"), "w").write("255")
        open(os.path.join(d, "multi_intensity"), "w").write(ORIG); c.append(d)
    return tuple(c)
P, S1, S2 = lampe("p"), lampe("s1"), lampe("s2")
lec, ecr = os.pipe()
ETAT, BASE = os.path.join(R, "es.inf"), os.path.join(R, "base.json")
json.dump({"format": "recalbox-arcade-credits", "version": 3, "jeux": {},
           "pistes": {}, "difficiles": {}}, open(BASE, "w"))
# Le faux RetroArch doit pouvoir changer de coeur.
_run = FauxRetroArch.run
def run(self):
    import socket, time as t
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", self.port)); s.settimeout(0.2)
    while not self.stop:
        try: d, src = s.recvfrom(4096)
        except socket.timeout: continue
        self.commandes += 1
        txt = d.decode(errors="replace").strip()
        if txt == "GET_STATUS":
            r = ("GET_STATUS PLAYING %s,%s,crc32=0" % (self.core, self.jeu)
                 if self.jeu else "GET_STATUS CONTENTLESS")
        elif txt.startswith("READ_CORE_RAM"):
            if not self.jeu: continue
            try: _, a, n = txt.split(); a, n = int(a, 16), int(n)
            except ValueError: continue
            r = ("READ_CORE_RAM %x -1" % a if a >= self.taille or n > 16384
                 or a + n > self.taille else
                 "READ_CORE_RAM %x %s" % (a, " ".join("%02X" % o for o in self.ram[a:a+n])))
        else: continue
        t.sleep(1/60); s.sendto(r.encode(), src)
    s.close()
FauxRetroArch.run = run

ra = FauxRetroArch(PORT_RA, adresse_credits=ADR_FBNEO, jeu="memerom")
ra.core = "FinalBurn Neo"
ra.start()
cp.BASE, cp.LEDS_PIECE, cp.LEDS_START, cp.LEDS_START_P2 = BASE, P, S1, S2
cp.RA_HOTE, cp.RA_PORT = "127.0.0.1", PORT_RA
cp.STATE_FILE, cp.JOURNAL = ETAT, os.path.join(R, "log")
cp.ouvrir_pads = lambda: {lec: "AllInOneP1"}
cp.signal = types.SimpleNamespace(signal=lambda *a: None, SIGTERM=15)
def appui(c): os.write(ecr, cp.EV.pack(0, 0, cp.EV_KEY, c, 1))
def etat(action, systeme):
    with open(ETAT, "w") as fh:
        fh.write("Action=%s\nSystemId=%s\nGame=Meme Rom\n" % (action, systeme))
echecs = []
def verifier(t, ok, d=""):
    print("%-56s %s %s" % (t, "OK" if ok else "ECHEC", d))
    if not ok: echecs.append(t)

def apprendre(systeme, adresse, core):
    ra.adresse = adresse; ra.ram[adresse] = 0; ra.jeu = "memerom"
    ra.core = core
    etat("rungame", systeme); time.sleep(2.5)
    for _ in range(5):
        ra.bruit(350); time.sleep(1.2)
        ra.credits(+1); appui(cp.CODE_PIECE); time.sleep(1.5)
        if ("%s/memerom" % systeme) in json.load(open(BASE))["jeux"]: return
        ra.credits(-1); appui(cp.CODE_START); time.sleep(1.2); ra.credits(+1)


threading.Thread(target=cp.main, daemon=True).start(); time.sleep(1.0)

print("--- meme rom, sous fbneo ---")
apprendre("fbneo", ADR_FBNEO, "FinalBurn Neo")
etat("endgame", "fbneo"); time.sleep(1.2)
print("--- puis sous mame, ou la RAM est ailleurs ---")
apprendre("mame", ADR_MAME, "MAME 2003-Plus")
etat("endgame", "mame"); time.sleep(1.5)

b = json.load(open(BASE))["jeux"]
verifier("deux fiches distinctes", len(b) == 2, str(sorted(b)))
verifier("fbneo garde son adresse",
         (b.get("fbneo/memerom") or {}).get("credits", {}).get("adresse") == ADR_FBNEO)
verifier("mame a la sienne",
         (b.get("mame/memerom") or {}).get("credits", {}).get("adresse") == ADR_MAME)
verifier("chaque fiche note son coeur",
         b["fbneo/memerom"]["core"] == "FinalBurn Neo"
         and b["mame/memerom"]["core"] == "MAME 2003-Plus")

print("\n--- et si le meme jeu revient sous un autre coeur ? ---")
base = json.load(open(BASE))
vue = cp.fiche_de(base, "fbneo", "memerom", "FinalBurn Neo")
verifier("le bon coeur : la fiche est rendue", vue is not None)
autre = cp.fiche_de(base, "fbneo", "memerom", "MAME 2003-Plus")
verifier("un autre coeur : refusee, on reapprend", autre is None)
ra.stop = True
print("\n%s" % ("TOUT EST BON" if not echecs else "ECHECS : " + ", ".join(echecs)))
