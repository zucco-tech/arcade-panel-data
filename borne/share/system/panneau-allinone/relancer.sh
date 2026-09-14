#!/bin/sh
# Relance proprement un des programmes permanents de la borne.
#
#   sh relancer.sh credits      (ou panneau, ou marquee)
#
# Tue toutes les instances du programme — il n en faut jamais qu une, deux
# se disputent les LED — puis en lance une seule.
. /recalbox/share/system/panneau-allinone/processus.sh
NOM=$1
[ -f "$U/$NOM(permanent).py" ] || { echo "inconnu : $NOM"; exit 1; }
for pid in $(instances "$NOM"); do kill "$pid" 2>/dev/null; done
sleep 2
lancer "$NOM"
sleep 3
echo "$NOM : $(instances "$NOM" | wc -l) instance(s)"
