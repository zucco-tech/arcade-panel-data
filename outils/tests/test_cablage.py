#!/usr/bin/env python3
"""La table des roles applique-t-elle la regle de Recalbox ?

On ecrit un es_input.cfg comme l assistant de Recalbox le produit sur cette
borne (panneau arcade6, boutons presses dans l ordre du dessin), un
cablage.json mesure, et un retroarchcustom.cfg comme configgen l ecrit au
lancement d un jeu FBNeo (releve du 14/09/2026, 64th Street). Puis on
verifie ce que chaque programme en deduit : quel bouton du jeu porte
chaque LED, systeme par systeme, et que RetroArch et la regle concordent."""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                                "borne", "share", "userscripts", "panneau-allinone"))
import cablage

ES = """<?xml version="1.0"?>
<inputList>
	<inputConfig type="joystick" deviceName="AllInOneP1" deviceGUID="x" gamepadtype="arcade6" version="2">
		<input name="r1" type="button" id="4" value="1" code="310" />
		<input name="l1" type="button" id="5" value="1" code="311" />
		<input name="west" type="button" id="2" value="1" code="307" />
		<input name="north" type="button" id="7" value="1" code="313" />
		<input name="south" type="button" id="0" value="1" code="304" />
		<input name="east" type="button" id="1" value="1" code="305" />
		<input name="hotkey" type="button" id="10" value="1" code="316" />
		<input name="select" type="button" id="8" value="1" code="314" />
		<input name="start" type="button" id="9" value="1" code="315" />
	</inputConfig>
	<inputConfig type="joystick" deviceName="AllInOneP2" deviceGUID="y" gamepadtype="arcade6" version="2">
		<input name="r1" type="button" id="4" value="1" code="310" />
		<input name="l1" type="button" id="5" value="1" code="311" />
		<input name="west" type="button" id="2" value="1" code="307" />
		<input name="north" type="button" id="7" value="1" code="313" />
		<input name="south" type="button" id="0" value="1" code="304" />
		<input name="east" type="button" id="1" value="1" code="305" />
		<input name="select" type="button" id="8" value="1" code="314" />
		<input name="start" type="button" id="9" value="1" code="315" />
	</inputConfig>
</inputList>
"""
CABLAGE = '{"postes": {"1": {"304": 1, "305": 2, "307": 3, "313": 4, "311": 5, "310": 6}}}'
# Ce que configgen a ecrit pour 64th Street (fbneo) : b <- north, a <- l1...
RETROARCH = """input_player1_a_btn = 5
input_player1_b_btn = 7
input_player1_l_btn = 2
input_player1_r_btn = 4
input_player1_select_btn = 8
input_player1_start_btn = 9
input_player1_x_btn = 1
input_player1_y_btn = 0
input_player2_a_btn = 5
input_player2_b_btn = 7
"""

echecs = []
def verifier(nom, ok):
    print("  %-62s %s" % (nom, "ok" if ok else "ECHEC"))
    if not ok:
        echecs.append(nom)

with tempfile.TemporaryDirectory() as d:
    es, cab, ra = (os.path.join(d, n) for n in ("es_input.cfg", "cablage.json", "retroarchcustom.cfg"))
    open(es, "w").write(ES); open(cab, "w").write(CABLAGE); open(ra, "w").write(RETROARCH)
    t = cablage.Cablage(es, cab, ra)

    print("--- ce que Recalbox a enregistre ---")
    verifier("source : es_input.cfg et cablage.json", t.source == "es_input.cfg, cablage.json")
    verifier("select = 314, start = 315, hotkey = 316", (t.code(1, "select"), t.code(1, "start"), t.code(1, "hotkey")) == (314, 315, 316))
    verifier("le role de 313 est x (north), en lettres", t.role(1, 313) == "x")
    verifier("le code 313 est sur la LED 4", t.led_du_code(1, 313) == 4)

    print("--- FBNeo : la rangee du bas porte les boutons 1 et 2 ---")
    leds = [t.led_du_bouton(1, n, "fbneo") for n in range(1, 7)]
    verifier("boutons 1..6 -> LED 4 5 1 2 3 6", leds == [4, 5, 1, 2, 3, 6])
    verifier("la LED 4 porte le bouton 1, la LED 1 le bouton 3",
             (t.bouton_de_led(1, 4, "fbneo"), t.bouton_de_led(1, 1, "fbneo")) == (1, 3))
    verifier("les consoles suivent la meme regle (snes)", [t.led_du_bouton(1, n, "snes") for n in (1, 2)] == [4, 5])
    verifier("le poste 2 est identique", [t.led_du_bouton(2, n, "fbneo") for n in range(1, 7)] == leds)

    print("--- MAME : dans l ordre du dessin ---")
    verifier("boutons 1..6 -> LED 1 2 3 4 5 6", [t.led_du_bouton(1, n, "mame") for n in range(1, 7)] == [1, 2, 3, 4, 5, 6])

    print("--- Naomi : L1 et R1 echanges apres le reordre ---")
    verifier("bouton 5 (l1) -> LED 6, bouton 6 (r1) -> LED 3",
             (t.led_du_bouton(1, 5, "naomi"), t.led_du_bouton(1, 6, "naomi")) == (6, 3))

    print("--- Megadrive : ses tables a six boutons ---")
    # apres reordre : a<-l1(311) b<-x(313) x<-a(305) y<-b(304) l1<-y(307) r1(310)
    # table MD6 : RA b <- a, y <- b, x <- x, l1 <- y, r1 <- l1, a <- r1
    verifier("b <- 311 (LED 5), y <- 313 (LED 4), a <- 310 (LED 6)",
             (t.led_du_bouton(1, 1, "megadrive"), t.led_du_bouton(1, 3, "megadrive"), t.led_du_bouton(1, 2, "megadrive")) == (5, 4, 6))

    print("--- en jeu : retroarchcustom.cfg a le dernier mot ---")
    verifier("le code de b en jeu est 313 (id 7)", t.code_en_jeu(1, "b") == 313)
    verifier("la regle et RetroArch concordent sur fbneo", t.ecart_retroarch(1, "fbneo") == [])
    verifier("...et pas sur mame : la regle y differe, et on le dirait", len(t.ecart_retroarch(1, "mame")) == 5)
    verifier("en jeu, bouton 1 -> LED 4 meme si on croit etre sous mame", t.led_du_bouton(1, 1, "mame", en_jeu=True) == 4)
    verifier("un role absent du fichier retombe sur la regle", t.led_du_bouton(2, 3, "fbneo", en_jeu=True) == 1)

    print("--- relecture ---")
    verifier("rien n a change : pas de relecture", t.rafraichir() is False)
    time.sleep(0.05)
    open(ra, "w").write(RETROARCH.replace("input_player1_b_btn = 7", "input_player1_b_btn = 0"))
    os.utime(ra, None)
    verifier("retroarchcustom.cfg reecrit : relecture", t.rafraichir() is True)
    verifier("...et le nouveau mappage est pris : b -> LED 1", t.led_du_bouton(1, 1, "fbneo", en_jeu=True) == 1)
    verifier("l ecart est signale", t.ecart_retroarch(1, "fbneo") == ["b : regle 313, retroarch 304"])

    print("--- sans fichiers : les valeurs de reference ---")
    t2 = cablage.Cablage(os.path.join(d, "absent"), os.path.join(d, "absent"), os.path.join(d, "absent"))
    verifier("source par defaut", t2.source == "roles par defaut, cablage par defaut")
    verifier("fbneo : bouton 1 -> LED 4 comme sur la borne", t2.led_du_bouton(1, 1, "fbneo") == 4)
    verifier("rien en jeu sans retroarchcustom.cfg", t2.code_en_jeu(1, "b") is None and t2.ecart_retroarch(1) == [])

print("\n%s" % ("TOUT EST BON" if not echecs else "ECHECS : " + ", ".join(echecs)))
sys.exit(1 if echecs else 0)
