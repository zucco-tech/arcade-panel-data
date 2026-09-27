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
# Journal : /recalbox/share/system/panneau-allinone/journaux/demarrage.log

# Recalbox passe « start » ou « stop » : on n agit qu au demarrage.
case "$1" in
    stop|shutdown|reboot) exit 0 ;;
esac

N=/recalbox/share/system/panneau-allinone
U=/recalbox/share/userscripts
mkdir -p "$N/journaux" "$N/etat"
echo "$(date "+%Y-%m-%d %H:%M:%S") demarrage" >> "$N/journaux/demarrage.log"

for f in "allinone[startgameclip].sh" "allinone[systembrowsing].sh"; do
    if [ -f "$U/$f" ]; then
        mv -f "$U/$f" "$U/$f.off"
        echo "$(date "+%H:%M:%S") $f remis hors service" >> "$N/journaux/demarrage.log"
    fi
done

# Le panneau en veilleuse le temps que le frontend demarre : boutons et
# START a 77, monnayeur et touche hotkey eteints. On ne touche qu a la
# luminosite, jamais aux couleurs : elles restent celles de la carte. (Le
# START est la LED que le pilote appelle « select », voir panneau(permanent).py.)
regler() {                      # $1 : nom de la LED sans son suffixe, $2 : valeur
    for k in 1 2; do
        [ -d "/sys/class/leds/$1_$k" ] && echo "$2" > "/sys/class/leds/$1_$k/brightness"
    done
}
for j in 1 2; do
    for b in 1 2 3 4 5 6; do regler "aio_p${j}_b${b}" 77; done
    regler "aio_p${j}_select" 77
    regler "aio_p${j}_start" 0
done
regler aio_hotkey 0

# 3. Le releve poli des credits, s il etait en cours avant l extinction.
#    Il ne repartait pas tout seul : la borne rallumee le 27/09 l a laisse
#    mort jusqu a une relance a la main. Il attend cinq minutes de silence
#    avant de commencer et rend la main au premier bouton presse, donc le
#    remettre au demarrage ne gene jamais personne. Le drapeau
#    « releve-en-cours » dit qu on le veut ; il est pose par
#    lancer-releve-borne.sh et retire par --arreter.
# On teste la PRESENCE du script, pas son bit d execution : sur la carte de
# la borne, chmod +x ne prend pas, et « -x » etait toujours faux -- la relance
# ne s est jamais declenchee (constate le 27/09, dix heures perdues). « sh »
# n a pas besoin du bit d execution.
if [ -f "$N/releve-en-cours" ] && [ -f "$N/outils/lancer.sh" ]; then
    rm -f /tmp/arret-releve-poli /tmp/arret-nuit
    setsid nohup sh "$N/outils/lancer.sh" >/dev/null 2>&1 </dev/null &
    echo "$(date "+%Y-%m-%d %H:%M:%S") releve poli relance" >> "$N/journaux/demarrage.log"
fi

exit 0
