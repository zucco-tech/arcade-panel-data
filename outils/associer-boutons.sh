#!/bin/sh
# Mesure, sur la borne, quel bouton porte quelle LED — pour un poste — et
# rapporte le resultat dans le depot.
#
#   sh /mnt/recalbox/outils/associer-boutons.sh [1|2]
#
# Sur la borne, une LED s allume : le joueur appuie sur ce bouton ; six fois.
# A faire quand on recable, et une fois pour le poste 2. Le fichier obtenu,
# cablage.json, est lu par le panneau du menu et le demon des credits.
BORNE=root@192.168.1.50
OUTILS=/mnt/recalbox/outils
DEPOT=/mnt/recalbox/depot/borne/share/system/panneau-allinone
POSTE=${1:-1}
INVITE=$OUTILS/.mdp-borne.sh
[ -x "$INVITE" ] || { printf '#!/bin/sh\necho recalboxroot\n' > "$INVITE"; chmod 700 "$INVITE"; }
export SSH_ASKPASS="$INVITE" SSH_ASKPASS_REQUIRE=force DISPLAY=${DISPLAY:-:0}
SSH="setsid -w ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no"
SCP="setsid -w scp -q -o StrictHostKeyChecking=no"
$SCP "$OUTILS/associer-boutons.py" $BORNE:/tmp/associer-boutons.py 2>/dev/null || { echo "borne injoignable"; exit 1; }
echo "Sur le poste $POSTE : appuie sur le bouton qui s allume, six fois."
$SSH $BORNE "python3 /tmp/associer-boutons.py $POSTE; rm -f /tmp/associer-boutons.py" 2>/dev/null; code=$?
[ $code -eq 0 ] && $SCP $BORNE:/recalbox/share/system/panneau-allinone/cablage.json "$DEPOT/cablage.json" 2>/dev/null && echo "cablage.json rapporte dans le depot"
exit $code
