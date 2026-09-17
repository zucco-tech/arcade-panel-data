#!/bin/sh
# Balaye un systeme avec plusieurs releves en parallele.
#
#   sh balayer.sh fbneo 4
#   ACHARNE=1 sh balayer.sh fbneo 4     reprise acharnee des ecartes (voir plus bas)
#
# Chaque releve prend une part entrelacee des jeux (1 sur 4, 2 sur 4...) et
# ecrit dans SON fichier : deux programmes qui ecrivent la meme base
# s ecraseraient. A la fin, les parts sont repliees dans la base principale.
#
# Ils tournent en « nice 10 » : s ils sont quatre sur quatre coeurs, le
# bureau garderait la main de toute facon, mais autant etre poli.
SYSTEME=${1:-fbneo}
COMBIEN=${2:-4}
# ACHARNE=1 : on ne mesure que les jeux deja ecartes ou le jeu tournait
# vraiment (delai depasse, inanime, aucun candidat, non confirmes), avec le
# mode acharne des releveurs — plus de temps, plus de pieces, d autres facons
# de demarrer — et un delai par jeu a la hauteur. Deux a cinq fois plus lent
# par jeu, mais il n y a que les ecartes a reprendre.
ACHARNE=${ACHARNE:-0}
SUPPLEMENT=""
PREFIXE=direct

# Chaque systeme a son coeur. Le nom compte autant que le fichier : c est lui
# qui indexe les fiches, et une meme rom sous deux coeurs n a pas la meme
# memoire (voir README).
# Le delai par jeu et le nombre de releves dependent aussi du coeur : la
# Saturn de Mednafen est lourde — a quatre en parallele sur deux coeurs
# physiques, un jeu depassait les trois minutes sans avoir fini de
# demarrer. Deux releves et un quart d heure de marge lui conviennent.
DELAI=180
DELAI_MAME=150
case "$SYSTEME" in
    stv)  COEUR=/opt/coeurs/mednafen_stv_libretro.so ; NOM="Mednafen ST-V" ; COMBIEN=2 ; DELAI=900 ;;
    *)    COEUR=/opt/coeurs/fbneo_rb.so              ; NOM="FinalBurn Neo" ;;
esac
if [ "$ACHARNE" = "1" ]; then
    SUPPLEMENT="--acharne"
    PREFIXE=acharne
    DELAI=900
    DELAI_MAME=${DELAI_MAME_ACHARNE:-600}
    [ "$SYSTEME" = "stv" ] && DELAI=1800
fi
BASE=/mnt/recalbox/donnees/credits-arcade.json
PARTS=/mnt/recalbox/donnees/parts
JOURNAUX=/mnt/recalbox/journaux
ARRET=/tmp/arret-nuit
HORODATE=$(date +%Y%m%d-%H%M)

mkdir -p "$PARTS"
rm -f "$PARTS"/*.json

n=1
while [ $n -le $COMBIEN ]; do
    if [ "$SYSTEME" = "mame" ]; then
        # MAME ne se mesure pas par libretro mais par un script Lua execute
        # dans l emulateur (voir releve-mame.py). Meme decoupage en parts,
        # meme repliage.
        # 150 s par machine : un jeu conclut en 10 a 50 s, et la moitie de
        # MAME n est pas de l arcade (machines a sous, mahjong, bornes de
        # test) — celles-la ne concluent jamais, inutile de les attendre
        # cinq minutes chacune.
        nice -n 10 python3 -u /mnt/recalbox/outils/releve-mame.py \
            --roms /mnt/roms/mame/mame0278 --delai "$DELAI_MAME" $SUPPLEMENT \
            --base "$PARTS/part-$n.json" --reference "$BASE" \
            --part "$n/$COMBIEN" --arret "$ARRET" ${RAISONS:+--raisons "$RAISONS"} \
            > "$JOURNAUX/$PREFIXE-mame-$HORODATE-part$n.log" 2>&1 &
    else
        nice -n 10 python3 -u /mnt/recalbox/outils/releve-direct.py \
            --systeme "$SYSTEME" --roms /mnt/roms \
            --coeur "$COEUR" --coeur-nomme "$NOM" \
            --base "$PARTS/part-$n.json" --reference "$BASE" \
            --part "$n/$COMBIEN" --arret "$ARRET" --delai "$DELAI" $SUPPLEMENT \
            > "$JOURNAUX/$PREFIXE-$SYSTEME-$HORODATE-part$n.log" 2>&1 &
    fi
    n=$((n + 1))
done
wait
python3 /mnt/recalbox/outils/fusionner-parts.py --base "$BASE" --parts "$PARTS"
