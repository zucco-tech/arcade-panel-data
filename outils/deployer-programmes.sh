#!/bin/sh
# Met en place sur la borne les PROGRAMMES du depot — pas les donnees, c est
# l affaire de deployer-vers-borne.sh — et relance ce qui doit l etre.
#
#   sh /mnt/recalbox/outils/deployer-programmes.sh
#
# Copies : les scripts de userscripts/ (panneau, credits, marquee, garde-fou),
# le code partage de userscripts/panneau-allinone/ (cablage.py, couleurs.py,
# reglages.py), et dans system/panneau-allinone/ (relancer.sh, processus.sh,
# manettes-consoles.json, cablage.json si le depot en a un plus recent que
# la borne n en a mesure) et custom.sh. Puis le panneau du menu est relance
# tout de suite ; le demon des credits seulement si aucune partie n est en
# cours — sinon a la fin de la partie, depuis la borne elle-meme.
BORNE=root@192.168.1.50
DEPOT=/mnt/recalbox/depot/borne/share
INVITE=/mnt/recalbox/outils/.mdp-borne.sh
JOURNAL=/mnt/recalbox/journaux/deploiement.log
[ -x "$INVITE" ] || { printf '#!/bin/sh\necho recalboxroot\n' > "$INVITE"; chmod 700 "$INVITE"; }
export SSH_ASKPASS="$INVITE" SSH_ASKPASS_REQUIRE=force DISPLAY=${DISPLAY:-:0}
SSH="setsid -w ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=no"
SCP="setsid -w scp -q -o StrictHostKeyChecking=no"
note() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $1" >> "$JOURNAL"; echo "$1"; }

$SSH $BORNE true 2>/dev/null || { note "programmes : borne injoignable"; exit 1; }
N=/recalbox/share/system/panneau-allinone
$SSH $BORNE "mkdir -p $N /tmp/programmes" 2>/dev/null
# tout passe par un dossier de passage, puis se met en place par renommage
$SCP "$DEPOT/userscripts/panneau(permanent).py" "$DEPOT/userscripts/credits(permanent).py" \
     "$DEPOT/userscripts/marquee(permanent).py" "$DEPOT/userscripts/gardefou[start,rungame,endgame].ash" \
     "$DEPOT/system/panneau-allinone/relancer.sh" "$DEPOT/system/panneau-allinone/processus.sh" \
     "$DEPOT/userscripts/panneau-allinone/cablage.py" "$DEPOT/userscripts/panneau-allinone/couleurs.py" \
     "$DEPOT/userscripts/panneau-allinone/reglages.py" "$DEPOT/system/panneau-allinone/manettes-consoles.json" \
     "$DEPOT/system/custom.sh" $BORNE:/tmp/programmes/ 2>/dev/null || { note "programmes : copie echouee"; exit 1; }
[ -f "$DEPOT/system/panneau-allinone/cablage.json" ] && $SCP "$DEPOT/system/panneau-allinone/cablage.json" $BORNE:/tmp/programmes/ 2>/dev/null
$SSH $BORNE "cd /tmp/programmes || exit 1
for f in 'panneau(permanent).py' 'credits(permanent).py' 'marquee(permanent).py' 'gardefou[start,rungame,endgame].ash'; do [ -f \"\$f\" ] && mv -f \"\$f\" \"/recalbox/share/userscripts/\$f\"; done
for f in relancer.sh processus.sh manettes-consoles.json; do [ -f \$f ] && mv -f \$f $N/\$f; done
# Le code partage vit dans un SOUS-dossier de userscripts : EmulationStation
# n y regarde pas, alors qu il executerait a chaque evenement un .py pose
# directement dans userscripts. Les anciennes copies de system/ sont retirees.
mkdir -p /recalbox/share/userscripts/panneau-allinone
for f in cablage.py couleurs.py reglages.py; do [ -f \$f ] && mv -f \$f /recalbox/share/userscripts/panneau-allinone/\$f && rm -f $N/\$f; done
rm -rf $N/__pycache__
# le cablage mesure sur la borne prime sur celui du depot s il est plus recent
if [ -f cablage.json ]; then [ $N/cablage.json -nt cablage.json ] 2>/dev/null || mv -f cablage.json $N/cablage.json; fi
mv -f custom.sh /recalbox/share/system/custom.sh
cd / && rm -rf /tmp/programmes
sh $N/relancer.sh panneau >/dev/null 2>&1
if pidof retroarch >/dev/null; then
    . $N/processus.sh; for pid in \$(attentes); do kill \$pid 2>/dev/null; done
    setsid nohup sh -c 'while pidof retroarch >/dev/null; do sleep 15; done; sleep 5; sh $N/relancer.sh credits >/dev/null 2>&1' >/dev/null 2>&1 &
    echo 'partie en cours : le demon des credits sera relance a sa fin'
else
    sh $N/relancer.sh credits >/dev/null 2>&1; echo 'demons relances'
fi" 2>/dev/null || { note "programmes : mise en place echouee"; exit 1; }
note "programmes en place sur la borne (depuis le depot $(cd /mnt/recalbox/depot && git log --oneline -1 2>/dev/null | cut -c1-7))"
