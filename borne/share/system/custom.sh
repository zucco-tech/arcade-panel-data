#!/bin/bash
# Lance au demarrage par Recalbox (crochet officiel : share/system/custom.sh).
#
# Deux choses a tenir a chaque demarrage :
#
#   1. Les deux scripts allinone[...].sh d origine reviennent tout seuls
#      apres certains redemarrages. Ils repeignent les LED a chaque
#      mouvement dans les menus et se battent alors avec
#      panneau(permanent).py. On les remet hors service.
#
#   2. EmulationStation met plusieurs minutes a charger ses listes ; tant
#      qu il n a rien ecrit, le panneau ne sait pas quoi eclairer et reste
#      comme la carte l a laisse. On pose donc tout de suite les couleurs
#      du panneau d arcade, en veilleuse : la borne a l air vivante des
#      l allumage, et le programme prendra le relais.
#
# Journal : /recalbox/share/system/panneau-arcade/journaux/demarrage.log

# Recalbox passe « start » ou « stop » : on n agit qu au demarrage.
case "$1" in
    stop|shutdown|reboot) exit 0 ;;
esac

N=/recalbox/share/system/panneau-arcade
U=/recalbox/share/userscripts
mkdir -p "$N/journaux" "$N/etat"
echo "$(date "+%Y-%m-%d %H:%M:%S") demarrage" >> "$N/journaux/demarrage.log"

for f in "allinone[startgameclip].sh" "allinone[systembrowsing].sh"; do
    if [ -f "$U/$f" ]; then
        mv -f "$U/$f" "$U/$f.off"
        echo "$(date "+%H:%M:%S") $f remis hors service" >> "$N/journaux/demarrage.log"
    fi
done

# Couleurs astrocity, en veilleuse, le temps que le frontend demarre.
for j in 1 2; do
    for b in 1 2 3 4 5 6; do
        for k in 1 2; do
            [ -d "/sys/class/leds/aio_p${j}_b${b}_${k}" ] || continue
            echo "77" > "/sys/class/leds/aio_p${j}_b${b}_${k}/brightness"
        done
    done
    for x in select; do
        for k in 1 2; do
            [ -d "/sys/class/leds/aio_p${j}_${x}_${k}" ] || continue
            echo "77" > "/sys/class/leds/aio_p${j}_${x}_${k}/brightness"
        done
    done
    for x in start; do
        for k in 1 2; do
            [ -d "/sys/class/leds/aio_p${j}_${x}_${k}" ] || continue
            echo "0" > "/sys/class/leds/aio_p${j}_${x}_${k}/brightness"
        done
    done
done
for k in 1 2; do
    [ -d "/sys/class/leds/aio_hotkey_${k}" ] && echo "0" > "/sys/class/leds/aio_hotkey_${k}/brightness"
done
exit 0
