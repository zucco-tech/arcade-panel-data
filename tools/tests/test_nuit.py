#!/usr/bin/env python3
"""Deroule une nuit complete contre une fausse borne : ES, RetroArch, clavier."""
import os
import importlib.util, json, os, socket, sys, threading, time
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
spec = importlib.util.spec_from_file_location("nuit", _trouver("nuit-credits.py"))
nuit = importlib.util.module_from_spec(spec); spec.loader.exec_module(nuit)

R = "/tmp/claude-1000/test/nuit"; os.system("rm -rf " + R); os.makedirs(R + "/roms/fbneo")
PORT_RA, PORT_ES = 46000, 46001
# Trois jeux : un avec piste juste, un avec piste fausse, un sans piste.
JEUX = {"avecpiste": 0x80B1, "piste_fausse": 0x2222, "sanspiste": 0x3333}
for j in JEUX: open(os.path.join(R, "roms/fbneo", j + ".zip"), "w").close()
BASE = os.path.join(R, "base.json")
json.dump({"format": "recalbox-arcade-credits", "version": 2, "jeux": {},
           "pistes": {"avecpiste": {"cheat": "0xFF80B0", "source": "test"},
                      "piste_fausse": {"cheat": "0xFF1000", "source": "test"}},
           "difficiles": {}}, open(BASE, "w"))

ra = FauxRetroArch(PORT_RA, jeu=None); ra.jeu = None; ra.start()

def faux_es():
    """Repond a START comme EmulationStation : il lance le jeu demande."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", PORT_ES)); s.settimeout(0.3)
    while not ra.stop:
        try: d, _ = s.recvfrom(4096)
        except socket.timeout: continue
        p = d.decode().split("|")
        if len(p) >= 3 and p[0] == "START":
            jeu = os.path.basename(p[2]).rsplit(".", 1)[0]   # ES recoit le chemin complet
            time.sleep(1.0)                        # temps de demarrage
            ra.adresse = JEUX.get(jeu, 0x1000)
            ra.ram[ra.adresse] = 0
            ra.jeu = jeu
    s.close()
threading.Thread(target=faux_es, daemon=True).start()

# QUIT : le faux RetroArch doit rendre la main
_udp = nuit.Borne._udp
def udp(self, port, texte, attendre_reponse=True, timeout=0.6):
    if port == nuit.PORT_RA and texte == "QUIT":
        ra.jeu = None; return ""
    return _udp(self, port, texte, attendre_reponse, timeout)
nuit.Borne._udp = udp

# Le clavier : une piece incremente vraiment le compteur du jeu en cours.
class FauxClavier:
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def piece(self):
        ra.bruit(80); ra.ram[ra.adresse] = (ra.ram[ra.adresse] + 1) & 0xFF
    def start(self):
        if ra.ram[ra.adresse] > 0: ra.ram[ra.adresse] -= 1
nuit.ClavierVirtuel = lambda *a, **k: FauxClavier()

nuit.PORT_RA, nuit.PORT_ES = PORT_RA, PORT_ES
nuit.REPOS_APRES_BOOT, nuit.ATTENTE_LANCEMENT = 0.5, 20.0

sys.argv = ["nuit", "--base", BASE, "--roms", os.path.join(R, "roms"),
            "--systeme", "fbneo", "--arret", os.path.join(R, "stop")]
t0 = time.time()
nuit.main()
ra.stop = True

print("\n--- verification ---")
b = json.load(open(BASE))
echecs = []
for jeu, adresse in JEUX.items():
    f = b["jeux"].get("fbneo/" + jeu)
    ok = f and f["credits"]["adresse"] == adresse
    print("%-14s %s %s" % (jeu, "OK  " if ok else "ECHEC",
                           f["credits"]["adresse_hex"] if f else "absent"))
    if not ok: echecs.append(jeu)
print("methodes :", {j: b["jeux"][j]["releve"]["methode"] for j in b["jeux"]})
print("\n%s (%.0f s)" % ("TOUT EST BON" if not echecs else "ECHECS : %s" % echecs,
                         time.time() - t0))
