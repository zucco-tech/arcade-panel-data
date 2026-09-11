#!/bin/sh
# Demarre le relevé pour la nuit : les credits, et le suivi des boutons.
#
# A lancer quand PERSONNE ne se sert de la machine : le balayage ouvre une
# fenetre RetroArch par jeu, une toutes les quinze secondes environ, et
# chacune prend le focus. Impossible de travailler sur le bureau pendant ce
# temps — ce n est pas un reglage a trouver, c est la nature de la chose.
#
#   sudo sh /mnt/recalbox/outils/demarrer.sh
#
# Pour arreter proprement, a tout moment :   touch /tmp/arret-nuit
# La base est ecrite apres chaque jeu : rien ne se perd, et une relance
# reprend exactement ou on en etait.

rm -f /tmp/arret-nuit

# Il ne doit rester aucun RetroArch d une session precedente.
for p in $(pgrep -f "/opt/retroarch.AppImage" 2>/dev/null); do
    kill -9 "$p" 2>/dev/null
done

DISPLAY=:0 nohup python3 -u /mnt/recalbox/outils/balayage-continu.py \
    > /mnt/recalbox/journaux/sortie-balayage.log 2>&1 &
echo "balayage des credits lance (pid $!)"

nohup sh /mnt/recalbox/outils/suivre-boutons.sh \
    > /mnt/recalbox/journaux/boutons.log 2>&1 &
echo "suivi des boutons lance (pid $!)"

echo
echo "suivre l avancement :"
echo "    tail -f /mnt/recalbox/journaux/continu.log"
echo "    ls -t /mnt/recalbox/journaux/fbneo-*.log | head -1"
echo "arreter :"
echo "    touch /tmp/arret-nuit"
