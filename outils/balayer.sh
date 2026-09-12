#!/bin/sh
# Balaye un systeme avec plusieurs releves en parallele.
#
#   sh balayer.sh fbneo 4
#
# Chaque releve prend une part entrelacee des jeux (1 sur 4, 2 sur 4...) et
# ecrit dans SON fichier : deux programmes qui ecrivent la meme base
# s ecraseraient. A la fin, les parts sont repliees dans la base principale.
#
# Ils tournent en « nice 10 » : s ils sont quatre sur quatre coeurs, le
# bureau garderait la main de toute facon, mais autant etre poli.
SYSTEME=${1:-fbneo}
COMBIEN=${2:-4}

# Chaque systeme a son coeur. Le nom compte autant que le fichier : c est lui
# qui indexe les fiches, et une meme rom sous deux coeurs n a pas la meme
# memoire (voir README).
case "$SYSTEME" in
    stv)  COEUR=/opt/coeurs/mednafen_stv_libretro.so ; NOM="Mednafen ST-V" ;;
    *)    COEUR=/opt/coeurs/fbneo_rb.so              ; NOM="FinalBurn Neo" ;;
esac
BASE=/mnt/recalbox/donnees/credits-arcade.json
PARTS=/mnt/recalbox/donnees/parts
JOURNAUX=/mnt/recalbox/journaux
ARRET=/tmp/arret-nuit
HORODATE=$(date +%Y%m%d-%H%M)

mkdir -p "$PARTS"
rm -f "$PARTS"/*.json

n=1
while [ $n -le $COMBIEN ]; do
    nice -n 10 python3 -u /mnt/recalbox/outils/releve-direct.py \
        --systeme "$SYSTEME" --roms /mnt/roms \
        --coeur "$COEUR" --coeur-nomme "$NOM" \
        --base "$PARTS/part-$n.json" --reference "$BASE" \
        --part "$n/$COMBIEN" --arret "$ARRET" \
        > "$JOURNAUX/direct-$SYSTEME-$HORODATE-part$n.log" 2>&1 &
    n=$((n + 1))
done
wait
python3 /mnt/recalbox/outils/fusionner-parts.py --base "$BASE" --parts "$PARTS"
