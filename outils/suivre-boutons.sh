#!/bin/sh
# Tient la base des boutons a jour pendant que le balayage des credits tourne.
#
# Aucun conflit possible : cet outil n interroge qu un service web et ecrit
# dans son propre fichier. Il ne touche ni a RetroArch, ni au clavier, ni a
# l ecran, ni a la base des credits — qu il se contente de LIRE pour savoir
# quels jeux sont nouveaux.
#
# S arrete avec le meme drapeau que le balayage.
BASE=/mnt/recalbox/donnees
while [ ! -f /tmp/arret-nuit ]; do
    python3 -u /mnt/recalbox/outils/importer-boutons.py \
        --jeux "$BASE/credits-arcade.json" \
        --base "$BASE/boutons-arcade.json"
    n=0
    while [ $n -lt 1200 ] && [ ! -f /tmp/arret-nuit ]; do
        sleep 10
        n=$((n + 10))
    done
done
echo "suivi des boutons : arret demande"
