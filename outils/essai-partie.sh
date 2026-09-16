#!/bin/sh
# Une partie simulee de bout en bout, sur la vraie borne, sans personne devant.
#
#   sudo sh /mnt/recalbox/depot/outils/essai-partie.sh
#
# La borne lance 1942 (FBNeo) par EmulationStation, comme un joueur. Puis on
# joue le role du monnayeur en ecrivant dans la memoire du jeu (WRITE_CORE_RAM
# sur le port 55355, a l adresse des credits de la fiche : 0x0011) :
#
#   credits a 0   la PIECE doit clignoter, START rester fixe
#   credits a 1   START doit clignoter, la PIECE s arreter
#
# et on LIT les LED de la carte (/sys/class/leds, dix fois par seconde) : ce
# n est pas ce que le programme croit faire, c est ce que la carte affiche.
# On verifie aussi les boutons : 1942 en utilise 2 et se joue chacun son
# tour, donc boutons 1 et 2 allumes, 3 a 6 eteints, poste 2 eteint.
#
# Refuse si une partie est en cours. Le compteur est remis a sa valeur, le
# jeu est quitte. Rien n est ecrit sur la borne.
BORNE=root@192.168.1.50
INVITE=/mnt/recalbox/outils/.mdp-borne.sh
[ -x "$INVITE" ] || { printf '#!/bin/sh\necho recalboxroot\n' > "$INVITE"; chmod 700 "$INVITE"; }
export SSH_ASKPASS="$INVITE" SSH_ASKPASS_REQUIRE=force DISPLAY=${DISPLAY:-:0}
JOURNAL=/mnt/recalbox/journaux/essai-partie-$(date +%Y%m%d-%H%M).log

setsid -w ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $BORNE python3 - <<'SUR_LA_BORNE' 2>&1 | tee "$JOURNAL"
import socket, subprocess, sys, time

ROM = "/recalbox/share/roms/fbneo/1942.zip"
ADRESSE = 0x0011
LED = "/sys/class/leds/%s/brightness"
PIECE, START = "aio_p1_start_1", "aio_p1_select_1"     # le pilote croise les noms

def en_jeu():
    return subprocess.call(["pidof", "retroarch"], stdout=subprocess.DEVNULL) == 0

def udp(port, texte, reponse=False):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(1.0)
    s.sendto(texte.encode(), ("127.0.0.1", port))
    try:
        return s.recv(4096).decode() if reponse else None
    except socket.timeout:
        return None
    finally:
        s.close()

def credits():
    r = udp(55355, "READ_CORE_RAM %x 1" % ADRESSE, True)
    try:
        return int(r.split()[2], 16)
    except (AttributeError, IndexError, ValueError):
        return None

def lire(nom):
    try:
        return int(open(LED % nom).read())
    except (OSError, ValueError):
        return None

def observer(secondes):
    """{led: ensemble des luminosites vues} sur la duree."""
    vues = {PIECE: set(), START: set()}
    fin = time.time() + secondes
    while time.time() < fin:
        for nom in vues:
            vues[nom].add(lire(nom))
        time.sleep(0.1)
    return vues

def clignote(valeurs):
    return 0 in valeurs and any(v for v in valeurs if v)

echecs = []
def verifier(texte, ok, detail=""):
    print("  %-52s %s %s" % (texte, "OK" if ok else "ECHEC", detail), flush=True)
    if not ok:
        echecs.append(texte)

if en_jeu():
    print("une partie est en cours : on ne touche a rien")
    sys.exit(2)

print("lancement de 1942 (FBNeo) par EmulationStation", flush=True)
udp(1337, "START|fbneo|%s" % ROM)
fin = time.time() + 60
while not en_jeu() and time.time() < fin:
    time.sleep(0.5)
if not en_jeu():
    print("le jeu ne demarre pas"); sys.exit(1)
time.sleep(15)                      # le demon a trouve le jeu et sa fiche
avant = credits()
print("compteur de credits lu : %s" % avant, flush=True)

try:
    print("\nboutons", flush=True)
    p1 = [lire("aio_p1_b%d_1" % n) for n in range(1, 7)]
    p2 = [lire("aio_p2_b%d_1" % n) for n in range(1, 7)]
    verifier("poste 1 : boutons 1 et 2 allumes", all(p1[:2]), p1)
    verifier("poste 1 : boutons 3 a 6 eteints", not any(p1[2:]), p1)
    verifier("poste 2 eteint (jeu chacun son tour)", not any(p2), p2)

    print("\npas de credit", flush=True)
    udp(55355, "WRITE_CORE_RAM %x 00" % ADRESSE)
    time.sleep(1.5)
    vues = observer(3)
    verifier("compteur a 0", credits() == 0, credits())
    verifier("PIECE clignote", clignote(vues[PIECE]), sorted(vues[PIECE], key=str))
    verifier("START ne clignote pas", not clignote(vues[START]), sorted(vues[START], key=str))

    print("\nune piece", flush=True)
    udp(55355, "WRITE_CORE_RAM %x 01" % ADRESSE)
    time.sleep(1.5)
    vues = observer(3)
    verifier("compteur a 1", credits() == 1, credits())
    verifier("START clignote", clignote(vues[START]), sorted(vues[START], key=str))
    verifier("PIECE ne clignote plus", not clignote(vues[PIECE]), sorted(vues[PIECE], key=str))
finally:
    if avant is not None:
        udp(55355, "WRITE_CORE_RAM %x %02x" % (ADRESSE, avant))
    udp(55355, "QUIT")
    fin = time.time() + 20
    while en_jeu() and time.time() < fin:
        time.sleep(0.5)

print("\n%s" % ("TOUT EST BON" if not echecs else "ECHECS : " + ", ".join(echecs)))
sys.exit(1 if echecs else 0)
SUR_LA_BORNE
