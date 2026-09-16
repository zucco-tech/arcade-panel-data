#!/bin/sh
# Essaie le pilote de LED corrige sur la borne, le temps d un allumage.
#
#   sh pilote-allinone/essayer-sur-borne.sh            # depuis le PC, dans le depot
#
# Rien n est installe : le module corrige est copie dans /tmp de la borne
# (la memoire vive), charge a la place de celui de Recalbox, et tout revient
# comme avant au prochain redemarrage. Aucun fichier du systeme n est touche.
#
# Garde-fous : on refuse de charger quoi que ce soit si le noyau n est pas
# celui pour lequel le module a ete prepare, ou si le module installe n est
# pas exactement celui qu on a corrige (une mise a jour de Recalbox l aurait
# change : il faudrait refaire la correction sur le nouveau).
#
# Ce qu on doit voir : multi_index dit « green red blue », et les couleurs du
# panneau ne changent pas — la correction ne change que les noms.
ICI=$(cd "$(dirname "$0")" && pwd)
BORNE=root@192.168.1.50
INVITE=/mnt/recalbox/outils/.mdp-borne.sh
[ -x "$INVITE" ] || { printf '#!/bin/sh\necho recalboxroot\n' > "$INVITE"; chmod 700 "$INVITE"; }
export SSH_ASKPASS="$INVITE" SSH_ASKPASS_REQUIRE=force DISPLAY=${DISPLAY:-:0}
SSH="setsid -w ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no"
SCP="setsid -w scp -o ConnectTimeout=10 -o StrictHostKeyChecking=no"

NOYAU=6.12.25-v8-16k
ORIGINE=3bbbd11b91113e2b78f63e977253bf9a253f7da7460be9ab79bf89457d40c11f
CORRIGE=8223c41f1c6d7ec8f86fb2581407a917cf42f7eccd2b38ab3ff053ed8be050eb

[ "$(sha256sum "$ICI/allinone_leds.ko" | cut -d' ' -f1)" = "$CORRIGE" ] \
    || { echo "allinone_leds.ko du depot abime : empreinte inattendue"; exit 1; }
$SCP "$ICI/allinone_leds.ko" $BORNE:/tmp/allinone_leds-corrige.ko || exit 1

$SSH $BORNE sh -s "$NOYAU" "$ORIGINE" "$CORRIGE" <<'SUR_LA_BORNE'
NOYAU=$1 ORIGINE=$2 CORRIGE=$3
INSTALLE=/lib/modules/$NOYAU/updates/allinone_leds.ko
N=/recalbox/share/system/panneau-allinone
[ "$(uname -r)" = "$NOYAU" ] || { echo "noyau $(uname -r), module prepare pour $NOYAU : on ne charge rien"; exit 1; }
[ "$(sha256sum "$INSTALLE" | cut -d' ' -f1)" = "$ORIGINE" ] \
    || { echo "le module installe a change (mise a jour ?) : correction a refaire, on ne charge rien"; exit 1; }
[ "$(sha256sum /tmp/allinone_leds-corrige.ko | cut -d' ' -f1)" = "$CORRIGE" ] \
    || { echo "copie abimee en route"; exit 1; }
echo "avant   : $(cat /sys/class/leds/aio_p1_b1_1/multi_index)"
rmmod allinone_leds || { echo "rmmod refuse : rien n a change"; exit 1; }
if ! insmod /tmp/allinone_leds-corrige.ko; then
    echo "insmod refuse : on remet le module d origine"
    modprobe allinone_leds
    exit 1
fi
sleep 1
echo "apres   : $(cat /sys/class/leds/aio_p1_b1_1/multi_index)"
echo "LED     : $(ls -d /sys/class/leds/aio_* | wc -l) (il y en avait autant avant)"
dmesg | tail -n 4
# Les LED viennent d etre recreees : nos programmes gardaient en memoire ce
# qu ils avaient pose. On les relance pour qu ils repeignent.
[ -f "$N/relancer.sh" ] && { sh "$N/relancer.sh" panneau; sh "$N/relancer.sh" credits; }
echo "au prochain redemarrage, le module de Recalbox revient tout seul"
SUR_LA_BORNE
