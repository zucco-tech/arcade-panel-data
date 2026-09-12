#!/bin/sh
# Le balayage des credits, jour et nuit, sans surveillance.
#
# Deux methodes, dans cet ordre, parce qu elles ne coutent pas la meme chose :
#
#   1. releve-direct.py  charge le coeur libretro tout seul, sans RetroArch
#      ni fenetre : environ 8 s par jeu, et le bureau reste utilisable. C est
#      elle qui fait le gros du travail.
#   2. nuit-credits.py   lance vraiment le jeu dans RetroArch, en plein
#      ecran : environ 30 s par jeu, et l ecran est pris. Reservee aux rares
#      roms que le coeur nu refuse de charger (1,7 % sur 60 jeux mesures).
#
# A chaque passe, on verifie que l option de diagnostic de FBNeo est toujours
# desactivee : RetroArch reecrit son fichier d options en quittant, et
# « Hold Start » ferait ouvrir le menu de service par notre appui sur START.
#
#   sudo sh /mnt/recalbox/outils/surveiller.sh &
# Arret propre :  touch /tmp/arret-nuit

OPT="/root/.config/retroarch/config/FinalBurn Neo/FinalBurn Neo.opt"
BASE=/mnt/recalbox/donnees/credits-arcade.json
JOURNAUX=/mnt/recalbox/journaux
JOURNAL=$JOURNAUX/surveillance.log
ARRET=/tmp/arret-nuit

# Pas de « fba » : ce systeme n existe pas sur la borne.
# Pas de naomi ni atomiswave : flycast les met en FREE PLAY, il n y a aucun
# compteur a mesurer (voir REGLES-APPRISES.md).
SYSTEMES="fbneo neogeo neogeocd"

note() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $1" >> "$JOURNAL"; }

verifier_diagnostic() {
    if ! grep -q 'fbneo-diagnostic-input = "Disabled"' "$OPT" 2>/dev/null; then
        chattr -i "$OPT" 2>/dev/null; chmod 644 "$OPT" 2>/dev/null
        sed -i 's/^fbneo-diagnostic-input = .*/fbneo-diagnostic-input = "Disabled"/' "$OPT"
        chmod 444 "$OPT" 2>/dev/null; chattr +i "$OPT" 2>/dev/null
        note "ALERTE : diagnostic revenu a Hold Start, corrige"
    fi
}

# Attend la fin du programme dont le numero est donne, en rendant la main
# tout de suite si l arret est demande. Renvoie faux si on s arrete.
attendre() {
    while kill -0 "$1" 2>/dev/null; do
        if [ -f "$ARRET" ]; then kill "$1" 2>/dev/null; return 1; fi
        sleep 5
    done
    return 0
}

note "=== surveillance demarree ==="
n=0
while [ ! -f "$ARRET" ]; do
    for sys in $SYSTEMES; do
        [ -f "$ARRET" ] && break
        [ -d "/mnt/roms/$sys" ] || continue
        verifier_diagnostic
        note "coeur direct : $sys"
        python3 -u /mnt/recalbox/outils/releve-direct.py \
            --systeme "$sys" --roms /mnt/roms --base "$BASE" --arret "$ARRET" \
            > "$JOURNAUX/direct-$sys-$(date +%Y%m%d-%H%M).log" 2>&1 &
        attendre $! || break
        note "coeur direct : $sys termine"
        n=$((n + 1))
        [ $((n % 2)) -eq 0 ] && sh /mnt/recalbox/outils/deployer-vers-borne.sh
    done
    [ -f "$ARRET" ] && break

    # Les roms que le coeur nu refuse : RetroArch, lui, sait les charger.
    # Cette passe prend l ecran, mais seulement pour celles-la.
    for sys in $SYSTEMES; do
        [ -f "$ARRET" ] && break
        verifier_diagnostic
        note "reprise par RetroArch : $sys"
        DISPLAY=:0 python3 -u /mnt/recalbox/outils/nuit-credits.py \
            --direct --reessayer --systeme "$sys" --roms /mnt/roms --base "$BASE" \
            --arret "$ARRET" --coeur-nomme "FinalBurn Neo" \
            > "$JOURNAUX/reprise-$sys-$(date +%Y%m%d-%H%M).log" 2>&1 &
        attendre $! || break
        note "reprise par RetroArch : $sys termine"
    done

    sh /mnt/recalbox/outils/deployer-vers-borne.sh
    note "tour complet termine, nouveau tour dans 15 min"
    i=0
    while [ $i -lt 900 ] && [ ! -f "$ARRET" ]; do sleep 10; i=$((i + 10)); done
done
note "=== surveillance arretee ==="
