#!/bin/sh
# La campagne des credits : elle tourne tant qu il reste des jeux a trouver.
#
#   sudo sh /mnt/recalbox/outils/campagne-credits.sh          # un tour, a la main
#   sudo systemctl start campagne-credits                     # en service
#   sudo touch /tmp/arret-campagne                            # arret propre
#
# Elle enchaine, sans jamais rien perdre :
#   1. FBNeo (coeur de 2026) : les jeux inconnus et ceux qui ont resiste
#   2. MAME : idem, avec la NVRAM initialisee d abord
#   3. le repliage des parts dans la base, apres CHAQUE systeme
#   4. un compte rendu dans journaux/campagne.txt
#
# Elle ne touche JAMAIS a la borne : l envoi des fiches reste une decision du
# proprietaire (outils/deployer-vers-borne.sh).
#
# Pourquoi un tour apres l autre, sans fin : une passe apprend des adresses,
# ce qui reduit la liste ; la passe suivante reprend ce qui reste avec plus de
# moyens. Quand un tour entier n apprend plus rien, la campagne s arrete
# d elle-meme et le dit dans le compte rendu.
OUTILS=/mnt/recalbox/outils
DONNEES=/mnt/recalbox/donnees
JOURNAUX=/mnt/recalbox/journaux
BASE=$DONNEES/credits-arcade.json
RAPPORT=$JOURNAUX/campagne.txt
ARRET=/tmp/arret-campagne
RAISONS_TOUT="rom refusee,romset inconnu,jeu non supporte,aucun candidat,candidats non confirmes,jeu inanime,delai depasse,pilote plante,reponse illisible"

note() { echo "$(date '+%F %T')  $1" >> $JOURNAUX/campagne.log; }
compter() { python3 -c "
import json; b = json.load(open('$BASE'))
print(len(b['jeux']), len(b['difficiles']))"; }

# Un seul balayage a la fois sur ce PC : quatre releves occupent deja les
# quatre coeurs. Si un autre tourne (lance a la main, ou reste d un
# redemarrage), on attend qu il finisse plutot que de tout ralentir.
attendre_la_place() {
    while ps -eo args | grep -q "[r]eleve-\(direct\|mame\).py --systeme\|[r]eleve-mame.py --acharne"; do
        [ -f $ARRET ] && return 1
        sleep 60
    done
    return 0
}

tour=0
while [ ! -f $ARRET ]; do
    attendre_la_place || break
    tour=$((tour + 1))
    set -- $(compter); avant_jeux=$1; avant_durs=$2
    note "tour $tour : depart, $avant_jeux fiches, $avant_durs ecartes"

    for systeme in fbneo neogeo neogeocd fba stv; do
        [ -f $ARRET ] && break
        [ -d /mnt/roms/$systeme ] || continue
        note "tour $tour : $systeme"
        PARTS=$DONNEES/parts-campagne ACHARNE=1 RAISONS="$RAISONS_TOUT" \
            sh $OUTILS/balayer.sh $systeme 4 \
            > $JOURNAUX/campagne-$systeme-$(date +%Y%m%d-%H%M).log 2>&1
    done

    if [ ! -f $ARRET ]; then
        note "tour $tour : mame (NVRAM d abord)"
        python3 -u $OUTILS/preparer-nvram.py --base $BASE \
            --raisons "candidats non confirmes,MAME n a rien rendu,jeu inanime,aucun candidat" \
            >> $JOURNAUX/campagne-nvram.log 2>&1
        PARTS=$DONNEES/parts-campagne ACHARNE=1 DELAI_MAME_ACHARNE=1800 MAME_IMAGES=45000 \
            sh $OUTILS/balayer.sh mame 4 \
            > $JOURNAUX/campagne-mame-$(date +%Y%m%d-%H%M).log 2>&1
    fi

    set -- $(compter); apres_jeux=$1; apres_durs=$2
    gagne=$((apres_jeux - avant_jeux))
    note "tour $tour : fini, $apres_jeux fiches (+$gagne), $apres_durs ecartes"
    {
        echo "CAMPAGNE DES CREDITS — $(date '+%A %d/%m/%Y %H:%M')"
        echo
        echo "Tour $tour termine : $apres_jeux adresses connues (+$gagne pendant ce tour),"
        echo "$apres_durs jeux encore sans adresse."
        echo
        echo "Derniers tours :"; tail -12 $JOURNAUX/campagne.log
        echo
        echo "Rien n a ete envoye sur la borne. Pour le faire :"
        echo "  sudo sh /mnt/recalbox/outils/deployer-vers-borne.sh"
    } > $RAPPORT

    if [ "$gagne" -le 0 ]; then
        note "tour $tour : plus rien a apprendre, la campagne s arrete"
        break
    fi
done
note "campagne terminee"
