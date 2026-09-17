#!/bin/sh
# Lance a distance un jeu par console et compare les LED allumees a ce que
# l EMULATEUR a vraiment recu comme boutons (sa configuration ecrite par
# configgen au lancement), pas a notre propre regle.
#
#   sudo sh /mnt/recalbox/outils/essai-consoles.sh [gba gb snes psx n64 ...]
#
# Refuse de demarrer si une partie est en cours. Chaque jeu tourne ~15 s.
BORNE=root@192.168.1.50
export SSH_ASKPASS=/mnt/recalbox/outils/.mdp-borne.sh SSH_ASKPASS_REQUIRE=force DISPLAY=${DISPLAY:-:0}
SYSTEMES="${*:-gb gba snes psx n64 megadrive}"
setsid -w ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $BORNE "SYSTEMES='$SYSTEMES' python3 -" <<'SUR_LA_BORNE'
import os, re, socket, subprocess, sys, time
import xml.etree.ElementTree as ET

R = "/recalbox/share/roms/"
RA = "/recalbox/share/system/configs/retroarch/retroarchcustom.cfg"
MUPEN = "/recalbox/share/system/configs/mupen64/mupen64plus.cfg"
CABLAGE = {304: 1, 305: 2, 307: 3, 313: 4, 311: 5, 310: 6}
# Ce que chaque coeur lit (code source lu le 17/09/2026), en noms RetroArch.
LUS = {"gb": "b a", "gbc": "b a", "nes": "b a", "gba": "b a l r", "snes": "b a y x l r",
       "psx": "b a y x l r", "megadrive": "b a y x l r", "mastersystem": "b a",
       "pcengine": "b a", "lynx": "b a l r", "virtualboy": "b a l r"}
# N64 (mupen) : les entrees de sa configuration qui sont des boutons du jeu.
N64 = ("A Button", "B Button", "Z Trig", "L Trig", "R Trig", "C Button U", "C Button D",
       "C Button L", "C Button R")
PROCESSUS = ("retroarch", "mupen64plus")

def ids_vers_codes():
    for conf in ET.parse("/recalbox/share/system/.emulationstation/es_input.cfg").getroot().iter("inputConfig"):
        if conf.get("deviceName") == "AllInOneP1":
            return {int(e.get("id")): int(e.get("code")) for e in conf.iter("input")
                    if e.get("type") == "button"}
    return {}

def en_jeu():
    return any(subprocess.call(["pidof", p], stdout=subprocess.DEVNULL) == 0 for p in PROCESSUS)

def attendre(cond, delai):
    fin = time.time() + delai
    while time.time() < fin:
        if cond():
            return True
        time.sleep(0.5)
    return False

def leds():
    etat = {}
    for n in range(1, 7):
        base = "/sys/class/leds/aio_p1_b%d_1/" % n
        br = open(base + "brightness").read().strip()
        mi = open(base + "multi_intensity").read().strip()
        etat[n] = (br != "0", mi)
    return etat

def attendues(systeme, ids):
    if systeme == "n64":
        texte = open(MUPEN).read()
        bloc = texte.split("[Input-SDL-Control1]", 1)[-1].split("\n[", 1)[0]
        leds = set()
        for nom in N64:
            m = re.search(r"^%s\s*=\s*\"?([^\"\n]*)" % re.escape(nom), bloc, re.M)
            for num in re.findall(r"button\((\d+)\)", m.group(1) if m else ""):
                code = ids.get(int(num))
                if code in CABLAGE:
                    leds.add(CABLAGE[code])
        return leds
    noms = LUS.get(systeme, "b a").split()
    config = {}
    for fichier in (RA, RA + ".overrides.cfg"):
        try:
            for nom, num in re.findall(r"^input_player1_(\w+?)_btn\s*=\s*\"?(\d+)", open(fichier).read(), re.M):
                config[nom] = int(num)
        except OSError:
            pass
    return {CABLAGE[ids[config[n]]] for n in noms if n in config and ids.get(config[n]) in CABLAGE}

if en_jeu():
    print("une partie est en cours : on ne touche a rien")
    sys.exit(2)
ids = ids_vers_codes()
bons = total = 0
for systeme in os.environ["SYSTEMES"].split():
    dossier = R + systeme
    # Un jeu qu EmulationStation connait : sa liste, pas le dossier (un .chd
    # d un jeu multi-disques ou une rom masquee est refuse).
    roms = []
    try:
        for g in ET.parse(os.path.join(dossier, "gamelist.xml")).getroot().iter("game"):
            chemin = os.path.normpath(os.path.join(dossier, g.findtext("path") or ""))
            if (g.findtext("hidden") or "false") != "true" and os.path.isfile(chemin):
                roms.append(chemin)
    except (OSError, ET.ParseError):
        pass
    if not roms:
        print("%-10s pas de jeu dans la liste" % systeme)
        continue
    rom = sorted(roms)[len(roms) // 2]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(("START|%s|%s" % (systeme, rom)).encode(), ("127.0.0.1", 1337))
    if not attendre(en_jeu, 60):
        print("%-10s %s : NE DEMARRE PAS" % (systeme, os.path.basename(rom)))
        continue
    time.sleep(10)
    total += 1
    etat = leds()
    allumees = {n for n, (on, _) in etat.items() if on}
    noires = [n for n, (on, mi) in etat.items() if on and set(mi.split()) == {"0"}]
    voulues = attendues(systeme, ids)
    ok = allumees == voulues and not noires
    bons += ok
    print("%-10s %-40s emulateur %-18s LED allumees %-18s %s" % (
        systeme, os.path.basename(rom)[:40], sorted(voulues), sorted(allumees),
        "OK" if ok else "ECART" + (" (noires : %s)" % noires if noires else "")))
    print("           couleurs : %s" % "  ".join("%d=%s" % (n, mi) for n, (on, mi) in etat.items() if on))
    s.sendto(b"QUIT", ("127.0.0.1", 55355))
    if not attendre(lambda: not en_jeu(), 15):
        subprocess.call(["killall", "retroarch", "mupen64plus"], stderr=subprocess.DEVNULL)
        attendre(lambda: not en_jeu(), 10)
    time.sleep(6)
print("\n%d console(s) sur %d : LED = boutons lus par l emulateur" % (bons, total))
sys.exit(0 if bons == total else 1)
SUR_LA_BORNE
