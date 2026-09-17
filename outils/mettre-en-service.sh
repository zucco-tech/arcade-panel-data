#!/bin/sh
# Met en service sur la borne tout ce qui est pret dans le depot, dans le bon
# ordre, et verifie. Une commande :
#
#   sudo sh /mnt/recalbox/depot/outils/mettre-en-service.sh
#
#   1. refuse si une partie est en cours (la famille joue)
#   2. programmes des LED (deployer-programmes.sh) : reglages recalbox.conf,
#      couleurs lues dans multi_index, cablage qui connait les surcharges
#   3. boutons dans l ordre du dessin pour fbneo et neogeo
#      (aligner-boutons.py, a partir du es_input.cfg de la borne)
#   4. controle de sante de la borne
#
# Les etapes 2 et 3 vont ensemble : sans le nouveau cablage.py, la borne
# remettrait les boutons a leur place mais les LED seraient inversees.
# Retour en arriere des boutons :
#   python3 /mnt/recalbox/depot/outils/aligner-boutons.py --roms /mnt/roms --retirer fbneo neogeo
OUTILS=$(cd "$(dirname "$0")" && pwd)
BORNE=root@192.168.1.50
INVITE=/mnt/recalbox/outils/.mdp-borne.sh
[ -x "$INVITE" ] || { printf '#!/bin/sh\necho recalboxroot\n' > "$INVITE"; chmod 700 "$INVITE"; }
export SSH_ASKPASS="$INVITE" SSH_ASKPASS_REQUIRE=force DISPLAY=${DISPLAY:-:0}
SSH="setsid -w ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no"
SCP="setsid -w scp -q -o ConnectTimeout=10 -o StrictHostKeyChecking=no"
SYSTEMES="fbneo neogeo"
# Consoles a deux boutons (17/09/2026) : sans surcharge, B et A tombaient en
# bas (4 et 5) et les boutons 1 et 2 etaient les TURBO de Gambatte (X et Y).
# Les consoles a six boutons (snes, psx...) gardent la regle de Recalbox.
CONSOLES="nes fds sg1000 mastersystem gamegear pcengine supergrafx gb gbc atari2600 atari7800 colecovision"
etape() { printf "\n=== %s ===\n" "$1"; }

etape "1. personne ne joue ?"
en_jeu=$($SSH $BORNE "pidof retroarch mame 2>/dev/null" 2>/dev/null)
[ $? -le 1 ] || { echo "borne injoignable"; exit 1; }
if [ -n "$en_jeu" ]; then echo "une partie est en cours : on ne touche a rien, relancer plus tard"; exit 1; fi
echo "non, on y va"

etape "2. les programmes des LED"
sh "$OUTILS/deployer-programmes.sh" || exit 1

etape "3. bouton 1 en haut a gauche ($SYSTEMES)"
ES=$(mktemp)
$SCP $BORNE:/recalbox/share/system/.emulationstation/es_input.cfg "$ES" || { echo "es_input.cfg illisible"; exit 1; }
# Par jeu, quand le releve des entrees du coeur existe (relever-entrees.py) :
# les jeux que FBNeo range autrement (Street Fighter...) ont leur fichier.
ENTREES=/mnt/recalbox/donnees/entrees-retropad.json
if [ -f "$ENTREES" ]; then
    python3 "$OUTILS/aligner-boutons.py" --es-input "$ES" --roms /mnt/roms --entrees "$ENTREES" fbneo || exit 1
    python3 "$OUTILS/aligner-boutons.py" --es-input "$ES" --roms /mnt/roms neogeo || exit 1
    python3 "$OUTILS/aligner-boutons.py" --es-input "$ES" --roms /mnt/roms $CONSOLES || exit 1
else
    python3 "$OUTILS/aligner-boutons.py" --es-input "$ES" --roms /mnt/roms $SYSTEMES $CONSOLES || exit 1
    echo "ATTENTION : pas de $ENTREES, les jeux de combat FBNeo auront poings et pieds melanges"
fi
rm -f "$ES"

etape "4. sante de la borne"
sh "$OUTILS/sante-borne.sh"
echo
echo "En service. A essayer : un jeu FBNeo a 2 ou 3 boutons (1942), le tir doit etre en haut a gauche,"
echo "et un Street Fighter FBNeo, pour voir si poings et pieds tombent juste."
