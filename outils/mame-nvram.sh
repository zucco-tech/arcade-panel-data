#!/bin/sh
# Reprise MAME des machines a NVRAM (17/09/2026) : NVRAM initialisee, puis releve acharne.
# Tourne a cote de « mame-lents » : ses parts a elle, dans parts-nvram.
J=/mnt/recalbox/journaux
BASE=/mnt/recalbox/donnees/credits-arcade.json
PARTS=/mnt/recalbox/donnees/parts-nvram
RAISONS="candidats non confirmes,MAME n a rien rendu (Configuration,MAME n a rien rendu (Loading"
H=$(date +%Y%m%d-%H%M)
mkdir -p $PARTS; rm -f $PARTS/*.json
python3 -u /mnt/recalbox/outils/preparer-nvram.py --base $BASE --raisons "$RAISONS" > $J/nvram-preparation-$H.log 2>&1
MAME_ACHARNE=1 python3 -u /mnt/recalbox/outils/releve-mame.py --acharne --raisons "$RAISONS" \
    --base $PARTS/part-1.json --reference $BASE --delai 900 > $J/nvram-mame-$H.log 2>&1
python3 /mnt/recalbox/outils/fusionner-parts.py --base $BASE --parts $PARTS >> $J/nvram-mame-$H.log 2>&1
echo "$(date '+%F %T') reprise nvram terminee" >> $J/nvram-mame-$H.log
