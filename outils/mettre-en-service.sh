#!/bin/sh
# Met en service sur la borne tout ce qui est pret dans le depot, dans le bon
# ordre, et verifie. Une commande :
#
#   sudo sh /mnt/recalbox/depot/outils/mettre-en-service.sh
#
#   1. refuse si une partie est en cours (la famille joue)
#   2. programmes des LED (deployer-programmes.sh)
#   3. boutons : ceux de Recalbox, jamais deplaces (choix du 17/09/2026) ;
#      retire les surcharges .retroarch.cfg d avant et envoie les donnees
#      (credits, boutons-arcade.json, ordre-fbneo.json pour les couleurs)
#   4. controle de sante de la borne
#
# A relancer apres « Configurer une manette » : rien a faire pour les
# boutons, les LED relisent es_input.cfg toutes seules.
OUTILS=$(cd "$(dirname "$0")" && pwd)
BORNE=root@192.168.1.50
INVITE=/mnt/recalbox/outils/.mdp-borne.sh
[ -x "$INVITE" ] || { printf '#!/bin/sh\necho recalboxroot\n' > "$INVITE"; chmod 700 "$INVITE"; }
export SSH_ASKPASS="$INVITE" SSH_ASKPASS_REQUIRE=force DISPLAY=${DISPLAY:-:0}
SSH="setsid -w ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no"
SCP="setsid -w scp -q -o ConnectTimeout=10 -o StrictHostKeyChecking=no"
SYSTEMES="fbneo neogeo"
etape() { printf "\n=== %s ===\n" "$1"; }

etape "1. personne ne joue ?"
en_jeu=$($SSH $BORNE "pidof retroarch mame 2>/dev/null" 2>/dev/null)
[ $? -le 1 ] || { echo "borne injoignable"; exit 1; }
if [ -n "$en_jeu" ]; then echo "une partie est en cours : on ne touche a rien, relancer plus tard"; exit 1; fi
echo "non, on y va"

etape "2. les programmes des LED"
sh "$OUTILS/deployer-programmes.sh" || exit 1

etape "3. les boutons : ceux de Recalbox"
# Choix du 17/09/2026 : toujours suivre la configuration de Recalbox, jamais
# deplacer un bouton ; les LED s adaptent (cablage.py, ordre-fbneo.json).
# On retire donc les surcharges que les versions du 16/09 avaient posees.
python3 "$OUTILS/aligner-boutons.py" --roms /mnt/roms --retirer fbneo neogeo || exit 1
sh "$OUTILS/deployer-vers-borne.sh" || { echo "donnees non envoyees (voir journaux/deploiement.log)"; exit 1; }

etape "4. sante de la borne"
sh "$OUTILS/sante-borne.sh"
echo
echo "En service. A essayer : 1942 FBNeo (le tir est la ou Recalbox le met, et c est lui qui s allume)"
echo "et Street Fighter II FBNeo (chaque bouton allume dans la couleur de son coup)."
