#!/bin/sh
# Fait tourner le releve jour et nuit, et le surveille.
#
# Le lanceur isole ne traite qu un systeme puis s arrete : c est ce script qui
# enchaine les systemes et le relance quand il a fini. Il recommence ensuite
# au debut, pour reprendre les jeux ecartes et ceux ajoutes entre-temps.
#
# Il verifie aussi, toutes les deux minutes, que FBNeo n est pas revenu en
# mode diagnostic : RetroArch remet « Hold Start » en quittant, et un START
# maintenu ouvre alors le menu de service, ou le compteur de credits ne veut
# plus rien dire. Le fichier est fige, mais on ne s en remet pas a ca seul.
#
# Arret :  touch /tmp/arret-nuit

OPT="/root/.config/retroarch/config/FinalBurn Neo/FinalBurn Neo.opt"
JOURNAL=/mnt/recalbox/journaux/surveillance.log
VIGNETTES=/mnt/recalbox/journaux/veille
SYSTEMES="fbneo fba neogeo neogeocd naomi naomigd naomi2 atomiswave"
mkdir -p "$VIGNETTES"

note() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $1" >> "$JOURNAL"; }

verifier_diagnostic() {
    if ! grep -q 'fbneo-diagnostic-input = "Disabled"' "$OPT" 2>/dev/null; then
        chattr -i "$OPT" 2>/dev/null; chmod 644 "$OPT" 2>/dev/null
        sed -i 's/^fbneo-diagnostic-input = .*/fbneo-diagnostic-input = "Disabled"/' "$OPT"
        chmod 444 "$OPT" 2>/dev/null; chattr +i "$OPT" 2>/dev/null
        note "ALERTE : diagnostic revenu a Hold Start, corrige"
    fi
}

note "=== surveillance demarree ==="
n=0
while [ ! -f /tmp/arret-nuit ]; do
    for sys in $SYSTEMES; do
        [ -f /tmp/arret-nuit ] && break
        [ -d "/mnt/roms/$sys" ] || continue
        verifier_diagnostic
        if ! pgrep -f "nuit-credits" >/dev/null 2>&1; then
            note "lancement du systeme $sys"
            DISPLAY=:0 nohup python3 -u /mnt/recalbox/outils/nuit-credits.py \
                --direct --rapide --roms /mnt/roms --systeme "$sys" \
                --base /mnt/recalbox/donnees/credits-arcade.json \
                --arret /tmp/arret-nuit --coeur-nomme "FinalBurn Neo" \
                > /mnt/recalbox/journaux/$sys-$(date +%Y%m%d-%H%M).log 2>&1 &
            sleep 30
        fi
        # on attend que ce systeme soit fini, en surveillant pendant ce temps
        while pgrep -f "nuit-credits" >/dev/null 2>&1; do
            [ -f /tmp/arret-nuit ] && break
            verifier_diagnostic
            n=$((n + 1))
            if [ $((n % 5)) -eq 0 ]; then
                DISPLAY=:0 python3 -c "
import sys; sys.path.insert(0,'/mnt/recalbox/outils')
from capture_fenetre import photographier
photographier('$VIGNETTES/$(date +%H%M%S).png', titre='releve credits')
" >/dev/null 2>&1
                ls -t "$VIGNETTES"/*.png 2>/dev/null | tail -n +61 | xargs -r rm -f
            fi
            i=0
            while [ $i -lt 120 ] && [ ! -f /tmp/arret-nuit ]; do sleep 10; i=$((i + 10)); done
        done
        note "systeme $sys termine"
    done
    [ -f /tmp/arret-nuit ] && break
    note "tous les systemes faits, nouvelle passe dans 15 min"
    i=0
    while [ $i -lt 900 ] && [ ! -f /tmp/arret-nuit ]; do sleep 10; i=$((i + 10)); done
done
note "=== surveillance arretee ==="
