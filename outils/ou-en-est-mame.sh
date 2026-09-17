#!/bin/sh
# Ou en sont les reprises MAME : sudo sh /mnt/recalbox/outils/ou-en-est-mame.sh
J=/mnt/recalbox/journaux
for u in mame-lents mame-nvram; do
    echo "== $u : $(systemctl is-active $u), memoire $(( $(systemctl show $u -p MemoryCurrent --value 2>/dev/null || echo 0) / 1048576 )) Mo"
done
echo "-- lents (4 parts)"
for f in $(ls -t $J/acharne-mame-*part*.log 2>/dev/null | head -4); do
    printf "  %s : %s, appris %s, ecartes %s\n" "$(basename $f .log | sed 's/.*part/part/')" \
        "$(grep -o '^\[[0-9]*/[0-9]*\]' $f | tail -1)" "$(grep -c APPRIS $f)" "$(grep -c difficile $f)"
done
P=$(ls -t $J/nvram-preparation-*.log 2>/dev/null | head -1)
M=$(ls -t $J/nvram-mame-*.log 2>/dev/null | head -1)
echo "-- nvram : preparation $(grep -o '^\[[0-9]*/[0-9]*\]' $P | tail -1), ecrites $(grep -c 'NVRAM ecrite' $P)"
[ -n "$M" ] && echo "   releve $(grep -o '^\[[0-9]*/[0-9]*\]' $M | tail -1), appris $(grep -c APPRIS $M), ecartes $(grep -c difficile $M)"
python3 -c "import json; b=json.load(open('/mnt/recalbox/donnees/credits-arcade.json')); print('-- base :', len(b['jeux']), 'fiches,', sum(1 for k in b['difficiles'] if k.startswith('mame/')), 'MAME ecartes')"
