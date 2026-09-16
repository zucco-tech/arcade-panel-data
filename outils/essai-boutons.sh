#!/bin/sh
# Verifie a distance, sans monter a la borne, ou tombent les boutons en jeu.
#
#   sudo sh /mnt/recalbox/depot/outils/essai-boutons.sh
#
# Pour chaque jeu d essai, la borne le lance PAR EMULATIONSTATION (commande
# START sur le port 1337, comme si on le choisissait dans le menu : configgen
# et les surcharges .retroarch.cfg s appliquent), attend que RetroArch
# tourne, lit ce que RetroArch a VRAIMENT charge (retroarchcustom.cfg puis
# retroarchcustom.cfg.overrides.cfg), en deduit la LED de chaque bouton du
# jeu avec cablage.py, puis quitte le jeu (QUIT sur le port 55355).
#
# Attendu, choix du 16/09/2026 : bouton N du jeu sous la LED N, sur FBNeo,
# Neo Geo et MAME — 1 2 3 en haut, 4 5 6 en bas.
#
# Ce que ca ne prouve pas : que le jeu donne a ses boutons le sens attendu
# (poings et pieds d un Street Fighter FBNeo). Ca, il faut le voir.
#
# Refuse si une partie est en cours. Rien n est ecrit sur la borne.
BORNE=root@192.168.1.50
INVITE=/mnt/recalbox/outils/.mdp-borne.sh
[ -x "$INVITE" ] || { printf '#!/bin/sh\necho recalboxroot\n' > "$INVITE"; chmod 700 "$INVITE"; }
export SSH_ASKPASS="$INVITE" SSH_ASKPASS_REQUIRE=force DISPLAY=${DISPLAY:-:0}
JOURNAL=/mnt/recalbox/journaux/essai-boutons-$(date +%Y%m%d-%H%M).log

setsid -w ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $BORNE python3 - <<'SUR_LA_BORNE' 2>&1 | tee "$JOURNAL"
import os, socket, subprocess, sys, time
sys.path.insert(0, "/recalbox/share/userscripts/panneau-allinone")
import cablage

R = "/recalbox/share/roms/"
JEUX = [
    ("fbneo",  R + "fbneo/1942.zip",           "2 boutons, tir"),
    ("fbneo",  R + "fbneo/sf2ce.zip",          "6 boutons, combat"),
    ("mame",   R + "mame/mame0278/1942.7z",    "reference MAME"),
    ("mame",   R + "mame/mame0278/sf2ce.7z",   "reference MAME, combat"),
]
SURCHARGE = "/recalbox/share/system/configs/retroarch/retroarchcustom.cfg.overrides.cfg"
CONFIG = "/recalbox/share/system/configs/retroarch/retroarchcustom.cfg"
# Ce que le coeur met sous chaque nom RetroPad, pour dire en clair ce qui est
# en haut a gauche. FBNeo : releve par relever-entrees.py le 16/09/2026.
# MAME : bouton 1 du jeu sur b, toujours.
FONCTIONS = {
    ("fbneo", "1942"):  {"b": "Fire 1", "a": "Fire 2"},
    ("fbneo", "sf2ce"): {"y": "Weak Punch", "x": "Medium Punch", "l": "Strong Punch",
                         "b": "Weak Kick", "a": "Medium Kick", "r": "Strong Kick"},
    ("mame", "1942"):   {"b": "Fire 1 (bouton 1)", "a": "Fire 2 (bouton 2)"},
    ("mame", "sf2ce"):  {"b": "Weak Punch (bouton 1)", "a": "Medium Punch", "y": "Strong Punch",
                         "x": "Weak Kick", "l": "Medium Kick", "r": "Strong Kick"},
}

def en_haut_a_gauche():
    """Le nom RetroPad que RetroArch a mis sur le bouton en haut a gauche :
    dans l ordre de chargement, le dernier nom qui recoit le numero du role
    south d es_input.cfg."""
    import xml.etree.ElementTree as ET
    south = None
    for conf in ET.parse("/recalbox/share/system/.emulationstation/es_input.cfg").getroot().iter("inputConfig"):
        if conf.get("deviceName") == "AllInOneP1":
            for e in conf.iter("input"):
                if e.get("name") in ("south", "b") and e.get("type") == "button":
                    south = e.get("id")
    noms = {}
    for fichier in (CONFIG, SURCHARGE):
        try:
            for ligne in open(fichier):
                if ligne.startswith("input_player1_") and "_btn" in ligne and "=" in ligne:
                    cle, val = ligne.split("=", 1)
                    noms[cle.strip()[len("input_player1_"):-len("_btn")]] = val.strip().strip('"')
        except OSError:
            pass
    return [n for n, v in noms.items() if v == south and n in ("b", "a", "y", "x", "l", "r")]

def en_jeu():
    return subprocess.call(["pidof", "retroarch"], stdout=subprocess.DEVNULL) == 0

def udp(port, texte):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(texte.encode(), ("127.0.0.1", port))
    s.close()

def attendre(condition, delai):
    fin = time.time() + delai
    while time.time() < fin:
        if condition():
            return True
        time.sleep(0.5)
    return False

if en_jeu():
    print("une partie est en cours : on ne touche a rien")
    sys.exit(2)

bons = 0
print("%-7s %-12s %-22s %-20s %s" % ("systeme", "jeu", "", "LED des boutons 1-6", "verdict"))
for systeme, rom, quoi in JEUX:
    jeu = os.path.basename(rom).rsplit(".", 1)[0]
    if not os.path.exists(rom):
        print("%-7s %-12s %-22s %-20s %s" % (systeme, jeu, quoi, "-", "rom absente"))
        continue
    udp(1337, "START|%s|%s" % (systeme, rom))
    if not attendre(en_jeu, 60):
        print("%-7s %-12s %-22s %-20s %s" % (systeme, jeu, quoi, "-", "NE DEMARRE PAS"))
        continue
    time.sleep(5)                       # configgen a fini d ecrire, le coeur tourne
    c = cablage.Cablage()
    leds = [c.led_du_bouton(1, n, systeme, True) for n in range(1, 7)]
    leds2 = [c.led_du_bouton(2, n, systeme, True) for n in range(1, 7)]
    # configgen recopie la surcharge sans ses commentaires : on la reconnait
    # a ce qu elle definit, pas a notre marque.
    try:
        surcharge = "input_player1_b_btn" in open(SURCHARGE).read()
    except OSError:
        surcharge = False
    ok = leds == [1, 2, 3, 4, 5, 6] and leds2 == leds
    bons += ok
    haut = en_haut_a_gauche()
    fonction = ", ".join(FONCTIONS.get((systeme, jeu), {}).get(n, n) for n in haut)
    print("%-7s %-12s %-22s %-20s %s%s" % (systeme, jeu, quoi, leds,
          "OK" if ok else "ECART (poste 2 : %s)" % leds2, "  [surcharge chargee]" if surcharge else ""))
    print("        en haut a gauche : %s" % (fonction or "?"))
    udp(55355, "QUIT")
    if not attendre(lambda: not en_jeu(), 20):
        udp(55355, "QUIT")
        attendre(lambda: not en_jeu(), 10)
    time.sleep(6)                       # EmulationStation reprend la main

print("\n%d jeu(x) sur %d avec le bouton 1 en haut a gauche" % (bons, len(JEUX)))
sys.exit(0 if bons == len(JEUX) else 1)
SUR_LA_BORNE
