#!/bin/sh
# Fait rejouer l echantillon par la borne elle-meme, et rapatrie le rapport.
#
#   sh /mnt/recalbox/outils/verifier-sur-borne.sh [/mnt/recalbox/donnees/echantillon.json]
#
# A ne lancer que quand personne ne joue : EmulationStation est arrete le
# temps du controle (une dizaine de minutes pour vingt fiches) et relance a
# la fin. Le programme et le clavier virtuel sont deposes dans /tmp de la
# borne, rien de permanent n y est ecrit. Le rapport va dans
# journaux/verification-borne-<date>.log ; la commande rend 1 au moindre ecart.
BORNE=root@192.168.1.50
OUTILS=/mnt/recalbox/outils
ECHANTILLON=${1:-/mnt/recalbox/donnees/echantillon.json}
JOURNAL=/mnt/recalbox/journaux/verification-borne-$(date +%Y%m%d).log
INVITE=$OUTILS/.mdp-borne.sh
[ -x "$INVITE" ] || { printf '#!/bin/sh\necho recalboxroot\n' > "$INVITE"; chmod 700 "$INVITE"; }
export SSH_ASKPASS="$INVITE" SSH_ASKPASS_REQUIRE=force DISPLAY=${DISPLAY:-:0}
SSH="setsid -w ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no"
SCP="setsid -w scp -q -o StrictHostKeyChecking=no"

$SSH $BORNE "mkdir -p /tmp/verification" 2>/dev/null || { echo "borne injoignable"; exit 1; }
$SCP "$OUTILS/verifier-sur-borne.py" "$OUTILS/clavier_virtuel.py" "$ECHANTILLON" $BORNE:/tmp/verification/ 2>/dev/null
echo "=== controle sur la borne, $(date '+%Y-%m-%d %H:%M') ===" | tee -a "$JOURNAL"
$SSH $BORNE "cd /tmp/verification && python3 verifier-sur-borne.py $(basename "$ECHANTILLON") rapport.json" 2>/dev/null | tee -a "$JOURNAL"
code=$?
$SSH $BORNE "rm -rf /tmp/verification" 2>/dev/null
exit $code
