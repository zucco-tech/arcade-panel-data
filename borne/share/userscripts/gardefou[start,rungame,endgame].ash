#!/bin/sh
# Garde-fou des trois programmes permanents.
#
# Un script (permanent) n est lance par le frontend qu a son demarrage. Si
# le processus meurt en cours de route — c est arrive — plus rien ne le
# releve : le marquee se fige, ou le panneau reste eclaire comme il etait.
#
# Ce script n est appele que sur trois evenements rares : demarrage du
# frontend, lancement et fin de partie. Il ne fait qu un parcours de /proc,
# donc son cout est negligeable, contrairement a un script appele sur la
# navigation.
. /recalbox/share/system/panneau-allinone/processus.sh
JOURNAL=$N/journaux/gardefou.log

relever() {                     # $1 : programme (marquee, panneau ou credits)
    [ -f "$U/$1(permanent).py" ] || return 0     # une borne sans ce programme : rien a relancer
    [ -n "$(instances "$1")" ] && return 0
    lancer "$1"
    echo "$(date "+%Y-%m-%d %H:%M:%S") $1(permanent).py relance par le garde-fou" >> "$JOURNAL"
}

mkdir -p "$N/journaux" "$N/etat"
relever marquee
relever panneau
relever credits
exit 0
