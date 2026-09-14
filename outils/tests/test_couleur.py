#!/usr/bin/env python3
"""Le script ne doit jamais ecraser une couleur posee par la carte AllInOne."""
import importlib.util, os, sys, tempfile
# Les programmes de la borne sont dans borne/share/userscripts/ : la suite doit
# tourner partout ou le depot est copie, pas seulement chez son auteur.
W = os.environ.get("ARCADE_CREDITS") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "borne", "share", "userscripts")
spec = importlib.util.spec_from_file_location("cp", os.path.join(W, "credits(permanent).py"))
cp = importlib.util.module_from_spec(spec); spec.loader.exec_module(cp)

R = tempfile.mkdtemp(prefix="couleur-")            # un dossier neuf, nettoye par le systeme
cp.JOURNAL = os.path.join(R, "log")
SYSTEME = "0xAA 0xAA 0xAA"
# Une couleur qui n'est surtout pas la notre, quel que soit l'ordre materiel.
NOUVELLE = cp.couleur(0x00, 0x00, 0xFF)
# Le meme rouge que le notre, mais ecrit en decimal comme le rend le driver.
NOTRE_ROUGE_DECIMAL = " ".join(str(int(x, 0)) for x in cp.COULEUR_PIECE.split())
def lampe(nom, couleur):
    d = os.path.join(R, nom); os.makedirs(d)
    open(os.path.join(d, "brightness"), "w").write("255")
    open(os.path.join(d, "multi_intensity"), "w").write(couleur)
    return d
def lu(d, f): return open(os.path.join(d, f)).read().strip()
def poser(d, c): open(os.path.join(d, "multi_intensity"), "w").write(c)
echecs = []
def verifier(t, ok, det=""):
    print("%-58s %s %s" % (t, "OK" if ok else "ECHEC", det))
    if not ok: echecs.append(t)

print("--- cas normal : personne d'autre n'a touche a la LED ---")
d = lampe("a", SYSTEME)
l = cp.Lampe("piece", (d,), cp.COULEUR_PIECE)
l.clignoter(0.0)
verifier("la LED est passee au rouge", lu(d, "multi_intensity") == cp.COULEUR_PIECE)
l.repos()
verifier("la couleur du systeme est rendue", lu(d, "multi_intensity") == SYSTEME,
         lu(d, "multi_intensity"))

print("\n--- la carte repeint pendant qu'on clignote ---")
d2 = lampe("b", SYSTEME)
l2 = cp.Lampe("piece", (d2,), cp.COULEUR_PIECE)
l2.clignoter(0.0)
poser(d2, NOUVELLE)                      # recalbox_allinone_rgb.sh passe par la
l2.repos()
verifier("sa couleur est respectee, pas ecrasee", lu(d2, "multi_intensity") == NOUVELLE,
         lu(d2, "multi_intensity"))
verifier("la luminosite est quand meme rendue", lu(d2, "brightness") == "255")

print("\n--- le driver rend des decimales, la carte ecrit en hexa ---")
d3 = lampe("c", SYSTEME)
l3 = cp.Lampe("piece", (d3,), cp.COULEUR_PIECE)
l3.clignoter(0.0)
poser(d3, NOTRE_ROUGE_DECIMAL)           # meme rouge, autre ecriture
l3.repos()
verifier("reconnu comme notre rouge, donc restaure",
         lu(d3, "multi_intensity") == SYSTEME, lu(d3, "multi_intensity"))
print("\n%s" % ("TOUT EST BON" if not echecs else "ECHECS : " + ", ".join(echecs)))
