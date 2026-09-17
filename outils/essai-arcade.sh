#!/bin/sh
# Lance a distance des jeux d arcade et verifie, sur la carte, que chaque LED
# allumee porte un bouton du jeu, dans la couleur de ce bouton. La verite est
# ce que RetroArch a recu (retroarchcustom.cfg), pas notre propre regle.
#
#   sudo sh /mnt/recalbox/outils/essai-arcade.sh
#
# Refuse de demarrer si une partie est en cours. Chaque jeu tourne ~20 s.
BORNE=root@192.168.1.50
export SSH_ASKPASS=/mnt/recalbox/outils/.mdp-borne.sh SSH_ASKPASS_REQUIRE=force DISPLAY=${DISPLAY:-:0}
setsid -w ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $BORNE python3 - <<'SUR_LA_BORNE'
import json, os, re, socket, subprocess, sys, time
import xml.etree.ElementTree as ET
sys.path.insert(0, "/recalbox/share/userscripts/panneau-allinone")
import couleurs

R = "/recalbox/share/roms/"
P = "/recalbox/share/system/panneau-allinone/"
RA = "/recalbox/share/system/configs/retroarch/retroarchcustom.cfg"
JEUX = [("fbneo", R + "fbneo/1942.zip"), ("fbneo", R + "fbneo/sf2ce.zip"),
        ("mame", R + "mame/mame0278/1942.7z"), ("mame", R + "mame/mame0278/sf2ce.7z"),
        ("neogeo", R + "neogeo/mslug.zip")]
HABITUEL = ["b", "a", "y", "x", "l", "r"]
ORDRE = couleurs.ordre_materiel()

def charger(chemin, cle):
    try:
        return json.load(open(chemin)).get(cle) or {}
    except (OSError, ValueError):
        return {}

fiches = charger(P + "boutons-arcade.json", "jeux")
ordres = charger(P + "ordre-fbneo.json", "jeux")
cablage = {int(c): int(l) for c, l in (charger(P + "cablage.json", "postes").get("1") or
           {"304": 1, "305": 2, "307": 3, "313": 4, "311": 5, "310": 6}).items()}
ids = {}
for conf in ET.parse("/recalbox/share/system/.emulationstation/es_input.cfg").getroot().iter("inputConfig"):
    if conf.get("deviceName") == "AllInOneP1":
        ids = {int(e.get("id")): int(e.get("code")) for e in conf.iter("input") if e.get("type") == "button"}

def en_jeu():
    return subprocess.call(["pidof", "retroarch"], stdout=subprocess.DEVNULL) == 0

def attendre(cond, delai):
    fin = time.time() + delai
    while time.time() < fin:
        if cond():
            return True
        time.sleep(0.5)
    return False

def retroarch():
    noms = {}
    for f in (RA, RA + ".overrides.cfg"):
        try:
            for nom, num in re.findall(r"^input_player1_(\w+?)_btn\s*=\s*\"?(\d+)", open(f).read(), re.M):
                noms[nom] = int(num)
        except OSError:
            pass
    return noms

if en_jeu():
    print("une partie est en cours : on ne touche a rien")
    sys.exit(2)
bons = total = 0
for systeme, rom in JEUX:
    jeu = os.path.basename(rom).rsplit(".", 1)[0]
    fiche = fiches.get(jeu)
    if not os.path.exists(rom) or not fiche:
        print("%-7s %-8s rom ou fiche absente" % (systeme, jeu))
        continue
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(("START|%s|%s" % (systeme, rom)).encode(), ("127.0.0.1", 1337))
    if not attendre(en_jeu, 60):
        print("%-7s %-8s NE DEMARRE PAS" % (systeme, jeu))
        continue
    time.sleep(15)
    total += 1
    nombre = min(int(fiche.get("nombre") or 0), 6)
    ordre = ordres.get(jeu) if systeme in ("fbneo", "neogeo") else None
    ordre = ordre or HABITUEL
    ra = retroarch()
    attendu = {}
    for k in range(1, nombre + 1):
        code = ids.get(ra.get(ordre[k - 1]))
        led = cablage.get(code)
        if led:
            b = (fiche.get("boutons") or {}).get("BUTTON%d" % k) or {}
            teinte = b.get("couleur") or couleurs.teinte_par_defaut(nombre, k)
            rvb = couleurs.TEINTES.get((teinte or "").strip().lower())
            attendu[led] = (b.get("fonction") or "bouton %d" % k,
                            [rvb[i] for i in ORDRE] if rvb else None)
    ecarts = []
    for n in range(1, 7):
        base = "/sys/class/leds/aio_p1_b%d_1/" % n
        allume = open(base + "brightness").read().strip() != "0"
        vu = [int(x, 0) for x in open(base + "multi_intensity").read().split()]
        if allume != (n in attendu):
            ecarts.append("LED %d %s" % (n, "allumee sans bouton" if allume else "eteinte alors qu elle sert"))
        elif allume and attendu[n][1] and vu != attendu[n][1]:
            ecarts.append("LED %d couleur %s au lieu de %s" % (n, vu, attendu[n][1]))
    ok = not ecarts
    bons += ok
    print("%-7s %-8s %s" % (systeme, jeu, "OK" if ok else "ECART : " + " ; ".join(ecarts)))
    print("        " + "  ".join("LED%d=%s" % (n, attendu[n][0]) for n in sorted(attendu)))
    s.sendto(b"QUIT", ("127.0.0.1", 55355))
    if not attendre(lambda: not en_jeu(), 20):
        subprocess.call(["killall", "retroarch"], stderr=subprocess.DEVNULL)
        attendre(lambda: not en_jeu(), 10)
    time.sleep(6)
print("\n%d jeu(x) d arcade sur %d : LED = boutons du jeu, bonnes couleurs" % (bons, total))
sys.exit(0 if bons == total else 1)
SUR_LA_BORNE
