#!/bin/sh
# Tout ce qui se verifie, dans l ordre, en une commande.
#
#   sh /mnt/recalbox/outils/verifier-tout.sh                 # la logique et la borne
#   sh /mnt/recalbox/outils/verifier-tout.sh --echantillon   # plus les fiches, sur le PC et sur la borne
#
# Quatre niveaux, du plus rapide au plus lourd, et chacun ne prouve qu une
# chose :
#   1. les bancs d essai      la logique des programmes, sans materiel      ~3 min
#   2. la sante de la borne   les programmes tournent, discrets, sans erreur  10 s
#   3. l echantillon sur le PC    les fiches se remesurent a l identique      ~10 min
#   4. l echantillon sur la borne les memes fiches sur le vrai materiel     ~5 min, prend l ecran
# Les niveaux 3 et 4 ne se lancent qu avec --echantillon : le 4 arrete
# EmulationStation le temps du controle, on ne le fait pas pendant qu on joue.
# La commande s arrete au premier niveau rouge et rend 1.
OUTILS=$(cd "$(dirname "$0")" && pwd)
ECHANTILLON=/mnt/recalbox/donnees/echantillon.json
# Les bancs d essai vivent dans le depot, a cote des programmes de la borne
# qu ils chargent (borne/share/userscripts/). Lance depuis la copie de
# travail du NAS (/mnt/recalbox/outils), on va les chercher dans le depot.
if [ -d "$OUTILS/../borne" ]; then BANCS="$OUTILS/tests"; else BANCS=/mnt/recalbox/depot/outils/tests; fi

etape() { printf "\n=== %s ===\n" "$1"; }

etape "1. les bancs d essai"
sh "$BANCS/tout.sh" || exit 1

etape "2. la sante de la borne"
sh "$OUTILS/sante-borne.sh" || exit 1

[ "$1" = "--echantillon" ] || { echo; echo "logique et borne : tout est vert (ajouter --echantillon pour les fiches)"; exit 0; }

etape "3. l echantillon, remesure sur le PC"
[ -f "$ECHANTILLON" ] || python3 "$OUTILS/verifier-echantillon.py" --tirer 20 --sortie "$ECHANTILLON"
python3 "$OUTILS/verifier-echantillon.py" --remesurer "$ECHANTILLON" || exit 1

etape "4. le meme echantillon, rejoue par la borne"
sh "$OUTILS/verifier-sur-borne.sh" "$ECHANTILLON" 15 5 || exit 1

echo; echo "tout est vert, du banc d essai a la borne"
