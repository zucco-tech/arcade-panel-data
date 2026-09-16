#!/usr/bin/env python3
"""Les reglages allinone.* de recalbox.conf, et l ordre des couleurs lu dans multi_index.

Aucun materiel : un faux recalbox.conf et de fausses LED dans un dossier
temporaire. On verifie qu un fichier sans section allinone rend la borne
d avant, qu un reglage ecrit est pris, qu une valeur fausse est ignoree, et
que les deux programmes s en servent.
"""
import importlib.util, os, sys, tempfile, time

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
W = os.environ.get("ARCADE_CREDITS") or os.path.join(RACINE, "borne", "share", "userscripts")
sys.path.insert(0, os.path.join(W, "..", "system", "panneau-allinone"))
import couleurs, reglages

def charger(nom, fichier):
    spec = importlib.util.spec_from_file_location(nom, os.path.join(W, fichier))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

R = tempfile.mkdtemp(prefix="reglages-")
CONF = os.path.join(R, "recalbox.conf")
echecs = []
def verifier(t, ok, det=""):
    print("%-62s %s %s" % (t, "OK" if ok else "ECHEC", det))
    if not ok: echecs.append(t)
def ecrire_conf(texte):
    with open(CONF, "w") as fh: fh.write(texte)
    # la date doit changer, meme dans la meme seconde
    t = time.time() + ecrire_conf.n; ecrire_conf.n += 5
    os.utime(CONF, (t, t))
ecrire_conf.n = 5
notes = []

print("--- le fichier, lu comme EmulationStation le lit ---")
ecrire_conf("# System Variable\nsystem.fbcp.enabled=0\n")
r = reglages.Reglages(notes.append, CONF)
verifier("sans section allinone : les valeurs du programme", r.get("allinone.brightness", 255) == 255
         and r.get("allinone.player2.enabled", True) is True)
verifier("et rien au journal", notes == [], notes)

ecrire_conf(";allinone.brightness=10\n#allinone.brightness.idle=5\n"
            "allinone.brightness = 180 \nallinone.coin.color=#00ff80\n"
            "allinone.player2.enabled=0\nallinone.idle.delay=45\n")
verifier("un changement de fichier est vu", r.rafraichir(forcer=True))
verifier("« ; » desactive la cle, « # » est un commentaire",
         r.get("allinone.brightness.idle", 128) == 128)
verifier("espaces autour de la cle et de la valeur retires", r.get("allinone.brightness", 255) == 180)
verifier("couleur avec ou sans #", r.get("allinone.coin.color", None) == (0x00, 0xFF, 0x80))
verifier("poste 2 coupe", r.get("allinone.player2.enabled", True) is False)
verifier("duree en secondes", r.get("allinone.idle.delay", 30.0) == 45.0)
verifier("fichier inchange : pas de relecture", not r.rafraichir(forcer=True))

notes.clear()
ecrire_conf("allinone.brightness=999\nallinone.coin.color=rouge\nallinone.blink.period=0.25\n")
r.rafraichir(forcer=True)
verifier("valeur hors bornes : ignoree", r.get("allinone.brightness", 255) == 255)
verifier("couleur illisible : ignoree", r.get("allinone.coin.color", None) is None)
verifier("les autres cles restent prises", r.get("allinone.blink.period", 0.5) == 0.25)
verifier("chaque erreur notee au journal", sum("ignore" in n for n in notes) == 2, notes)
notes.clear()
os.utime(CONF, (time.time() + 99, time.time() + 99))
r.rafraichir(forcer=True)
verifier("une erreur n est pas repetee a chaque relecture", not any("ignore" in n for n in notes), notes)
verifier("sans le fichier : rien ne casse",
         reglages.Reglages(chemin=os.path.join(R, "absent")).get("allinone.brightness", 255) == 255)

print("\n--- l ordre des couleurs, lu dans multi_index ---")
def led(nom, index):
    d = os.path.join(R, nom); os.makedirs(d)
    if index is not None:
        with open(os.path.join(d, "multi_index"), "w") as fh: fh.write(index + "\n")
    return d
verifier("pilote d origine (« red green blue », faux) : correction mesuree",
         couleurs.ordre_materiel(led("origine", "red green blue")) == (1, 0, 2))
verifier("pilote corrige (« green red blue ») : meme resultat",
         couleurs.ordre_materiel(led("corrige", "green red blue")) == (1, 0, 2))
verifier("un autre ordre annonce est suivi",
         couleurs.ordre_materiel(led("autre", "blue red green")) == (2, 0, 1))
verifier("LED absente : correction mesuree", couleurs.ordre_materiel(led("vide", None)) == (1, 0, 2))
verifier("texte inattendu : correction mesuree", couleurs.ordre_materiel(led("bizarre", "white")) == (1, 0, 2))

print("\n--- le demon des credits ---")
cp = charger("cp", "credits(permanent).py")
cp.JOURNAL = os.path.join(R, "credits.log")
verifier("sans reglage : luminosite et piece d origine",
         cp.plein() == "255" and cp.couleur_piece() == cp.COULEUR_PIECE)
ecrire_conf("allinone.brightness=200\nallinone.coin.color=0000FF\nallinone.blink.period=1.5\n")
cp.REGLAGES = reglages.Reglages(chemin=CONF)
verifier("allinone.brightness", cp.plein() == "200")
verifier("allinone.coin.color, dans l ordre du materiel", cp.couleur_piece() == cp.couleur(0, 0, 0xFF))
d = led("piece", None)
for f, v in (("brightness", "255"), ("multi_intensity", "0xAA 0xAA 0xAA")):
    with open(os.path.join(d, f), "w") as fh: fh.write(v)
lampe = cp.Lampe("piece", (d,), cp.couleur_piece())
lampe.clignoter(100.0)
verifier("le clignotement suit allinone.blink.period", abs(lampe.prochain - 101.5) < 1e-6, lampe.prochain)
lampe.clignoter(101.6)
verifier("rallumee a la luminosite reglee", open(os.path.join(d, "brightness")).read().strip() in ("0", "200"))
lampe.repos()
verifier("au repos : luminosite reglee et couleur rendue",
         open(os.path.join(d, "brightness")).read().strip() == "200"
         and open(os.path.join(d, "multi_intensity")).read().strip() == "0xAA 0xAA 0xAA")

print("\n--- le panneau du menu ---")
os.environ["PANNEAU_LEDS"] = os.path.join(R, "leds")
pm = charger("pm", "panneau(permanent).py")
verifier("sans reglage : 255 devant, 128 en veille", pm.luminosite(True) == "255" and pm.luminosite(False) == "128")
ecrire_conf("allinone.brightness=90\nallinone.brightness.idle=0\n")
pm.REGLAGES = reglages.Reglages(chemin=CONF)
verifier("allinone.brightness et allinone.brightness.idle", pm.luminosite(True) == "90" and pm.luminosite(False) == "0")

print("\n%s" % ("TOUT EST BON" if not echecs else "ECHECS : " + ", ".join(echecs)))
sys.exit(1 if echecs else 0)
