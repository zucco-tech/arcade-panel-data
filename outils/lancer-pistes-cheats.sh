#!/bin/sh
# Reprend des jeux MAME en donnant au Lua l adresse de credits DOCUMENTEE par
# le pack de cheats (« Infinite Credits »), deja importee dans la base par
# importer-cheats.py sous la clef "pistes".
#
# Pourquoi ca valait le detour : cette methode a trouve 1157 fiches sous FBNeo
# — c est la plus productive du projet — mais elle n avait jamais servi sous
# MAME, parce que releve-mame.py ne savait pas recevoir de piste avant le
# 28/09. Les adresses etaient la, personne ne les lisait.
#
#   sh lancer-pistes-cheats.sh [combien]
#
# Les fiches gagnees ne sont PAS repliees automatiquement : elles attendent
# une relecture, puis
#   python3 fusionner-parts.py --base <base> --parts <parts>
set -e
OUTILS=/mnt/recalbox/outils
DONNEES=/mnt/recalbox/donnees
JOURNAUX=/mnt/recalbox/journaux
BASE=$DONNEES/credits-arcade.json
JEUX_FICHIER=${JEUX_FICHIER:-$DONNEES/jeux-cheats-mame.txt}
PARTS=$DONNEES/parts-piste-cheats
COMBIEN=${1:-4}
export MAME_IMAGES=45000
mkdir -p "$PARTS"
rm -f "$PARTS"/*.json

n=1
while [ $n -le "$COMBIEN" ]; do
    JEUX=$(python3 -c "
import sys
noms = [l.strip() for l in open('$JEUX_FICHIER') if l.strip()]
print(' '.join(noms[$n - 1::$COMBIEN]))")
    [ -n "$JEUX" ] || { n=$((n + 1)); continue; }
    echo '{"jeux":{},"difficiles":{}}' > "$PARTS/part-$n.json"
    # La base sert de fichier de pistes : ses 2646 adresses de cheats y sont.
    # shellcheck disable=SC2086
    nice -n 10 python3 -u "$OUTILS/releve-mame.py" \
        --roms /mnt/roms/mame/mame0278 --acharne --delai 900 \
        --pistes "$BASE" --jeux $JEUX \
        --base "$PARTS/part-$n.json" --reference "$BASE" \
        > "$JOURNAUX/piste-cheats-mame-part$n.log" 2>&1 &
    n=$((n + 1))
done
wait
echo "les parts sont finies"
