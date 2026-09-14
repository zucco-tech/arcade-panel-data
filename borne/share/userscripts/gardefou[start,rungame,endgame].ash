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
U=/recalbox/share/userscripts
N=/recalbox/share/system/panneau-allinone
JOURNAL=$N/journaux/gardefou.log

vivant() {                      # $1 : morceau de nom cherche dans /proc
    for p in /proc/[0-9]*; do
        comm=$(cat "$p/comm" 2>/dev/null)
        case "$comm" in python3|python) ;; *) continue ;; esac
        if tr "\0" " " < "$p/cmdline" 2>/dev/null | grep -q "$1"; then
            return 0
        fi
    done
    return 1
}

relever() {                     # $1 : morceau de nom, $2 : fichier a lancer
    [ -f "$U/$2" ] || return 0     # une borne sans ce programme : rien a relancer
    vivant "$1" && return 0
    setsid nohup python3 "$U/$2" >> "$N/journaux/$1-erreurs.log" 2>&1 &
    echo "$(date "+%Y-%m-%d %H:%M:%S") $2 relance par le garde-fou" >> "$JOURNAL"
}

mkdir -p "$N/journaux" "$N/etat"
relever "marquee" "marquee(permanent).py"
relever "panneau" "panneau(permanent).py"
relever "credits" "credits(permanent).py"
exit 0
