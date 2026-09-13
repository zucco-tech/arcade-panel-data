#!/usr/bin/env python3
"""Deroule un apprentissage complet contre le faux RetroArch."""
import os
import importlib.util, json, os, socket, sys, threading, time
sys.path.insert(0, "/tmp/claude-1000/test")
from faux_retroarch import FauxRetroArch

# Les programmes de la borne sont dans borne/share/userscripts/ : la suite doit
# tourner partout ou le depot est copie, pas seulement chez son auteur.
W = os.environ.get("ARCADE_CREDITS") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "borne", "share", "userscripts")
spec = importlib.util.spec_from_file_location("ap", os.path.join(W, "apprenti-credits.py"))
ap = importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)

ADRESSE = 0x1234
PORT_RA, PORT_EV, PORT_RETOUR = 45355, 45006, 45007
BASE = "/tmp/claude-1000/test/base.json"
if os.path.exists(BASE): os.remove(BASE)

ra = FauxRetroArch(PORT_RA, adresse_credits=ADRESSE); ra.start()
ap.PORT_RA = PORT_RA          # le module parle au faux
time.sleep(0.2)

# La borne : recoit les fiches apprises
recu = []
def borne_ecoute():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", PORT_RETOUR)); s.settimeout(30)
    try: recu.append(json.loads(s.recvfrom(4096)[0].decode()))
    except socket.timeout: pass
    finally: s.close()
threading.Thread(target=borne_ecoute, daemon=True).start()

# L'apprenti, dans son thread
base = ap.charger(BASE)
borne = ap.Borne("127.0.0.1")
apprenti = ap.Apprenti(borne, base, BASE, ("127.0.0.1", PORT_RETOUR))
ecoute = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
ecoute.bind(("127.0.0.1", PORT_EV)); ecoute.settimeout(0.5)
fini = threading.Event()
def boucle():
    while not fini.is_set():
        try:
            d, _ = ecoute.recvfrom(4096)
            apprenti.evenement(json.loads(d.decode()))
        except socket.timeout:
            pass
        apprenti.rafraichir()
threading.Thread(target=boucle, daemon=True).start()

env = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
def evenement(ev):
    env.sendto(json.dumps({"ev": ev, "pad": "AllInOneP1", "jeu": "testgame"}).encode(),
               ("127.0.0.1", PORT_EV))

print("--- le joueur joue, met des pieces, appuie sur start ---")
t0 = time.time()
for tour in range(6):
    ra.bruit(400)                      # le jeu vit entre deux pieces
    time.sleep(1.2)                    # laisse l'apprenti rafraichir sa photo
    ra.credits(+1); evenement("piece")
    time.sleep(1.5)
    if apprenti.candidats is not None and len(apprenti.candidats) <= ap.ASSEZ:
        ra.credits(-1); evenement("start")
        time.sleep(1.5)
    if os.path.exists(BASE) and "testgame" in ap.charger(BASE).get("jeux", {}):
        break

fini.set(); time.sleep(0.6); ra.stop = True
duree = time.time() - t0

fiches = ap.charger(BASE).get("jeux", {})
print("\n--- resultat ---")
print("commandes RetroArch consommees : %d (~%.1f s d'images)" % (ra.commandes, ra.commandes/60))
ok = True
if "testgame" not in fiches:
    print("ECHEC : rien appris. candidats restants : %s" % (apprenti.candidats and len(apprenti.candidats)))
    ok = False
else:
    f = fiches["testgame"]
    print("fiche : %s" % json.dumps(f, sort_keys=True))
    if f["adresse"] != ADRESSE:
        print("ECHEC : adresse %s attendue 0x%04X" % (f["adresse_hex"], ADRESSE)); ok = False
    else:
        print("OK  adresse correcte : %s" % f["adresse_hex"])
    if not f["verifie_consommation"]:
        print("ATTENTION : consommation non verifiee"); 
if not recu:
    print("ECHEC : la borne n'a pas recu la fiche"); ok = False
else:
    print("OK  la borne a recu la fiche : %s" % recu[0]["fiche"]["adresse_hex"])
print("\n%s en %.0f s" % ("TOUT EST BON" if ok else "IL Y A UN PROBLEME", duree))
