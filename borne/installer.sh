#!/bin/sh
# Installe le panneau lumineux sur une borne Recalbox equipee d une carte
# AllInOne (digipcb.tech). A lancer SUR la borne, en root, depuis le dossier
# ou l on a copie le depot (cle USB, ou la share par le reseau) :
#
#     sh borne/installer.sh
#
# Ce que ca fait, et rien d autre :
#   - copie 3 scripts dans /recalbox/share/userscripts/ (credits, panneau,
#     gardefou) — Recalbox les lance tout seul au demarrage du frontend
#   - cree /recalbox/share/system/panneau-arcade/ avec les donnees, les
#     outils et un dossier de sauvegardes
#   - pose /recalbox/share/system/custom.sh (crochet officiel de demarrage)
#   - met hors service les deux scripts allinone[...].sh d origine, qui
#     repeignent les LED a chaque mouvement de menu
#   - relance les programmes
# Tout reste dans /recalbox/share. Le systeme Recalbox n est pas touche.
# Pour tout retirer : sh borne/desinstaller.sh
set -e
ICI=$(cd "$(dirname "$0")" && pwd)
DEPOT=$(dirname "$ICI")
U=/recalbox/share/userscripts
N=/recalbox/share/system/panneau-arcade
DATE=$(date +%Y%m%d-%H%M)

[ -d /sys/class/leds/aio_p1_b1_1 ] || { echo "pas de carte AllInOne detectee (/sys/class/leds/aio_*) : abandon"; exit 1; }
[ -f "$DEPOT/donnees/pour-borne.json" ] || { echo "il manque donnees/pour-borne.json dans le depot : abandon"; exit 1; }

mkdir -p "$N/outils" "$N/sauvegardes" "$U"
echo "1. sauvegarde de ce qui existe deja"
for f in "credits(permanent).py" "panneau(permanent).py" "gardefou[start,rungame,endgame].ash"; do
    [ -f "$U/$f" ] && cp "$U/$f" "$N/sauvegardes/$f.$DATE"
done
[ -f /recalbox/share/system/custom.sh ] && cp /recalbox/share/system/custom.sh "$N/sauvegardes/custom.sh.$DATE"

echo "2. les programmes"
for f in "credits(permanent).py" "panneau(permanent).py" "gardefou[start,rungame,endgame].ash"; do
    cp "$ICI/$f" "$U/$f"; chmod 755 "$U/$f" 2>/dev/null || true
done
cp "$ICI/README.md" "$U/README.md"
cp "$ICI/relancer.sh" "$N/relancer.sh"
cp "$ICI/mame-rapport.lua" "$ICI/mame.ini" "$N/outils/" 2>/dev/null || true

echo "3. les donnees"
cp "$DEPOT/donnees/pour-borne.json" "$N/credits-arcade.json"
cp "$DEPOT/donnees/boutons-arcade.json" "$N/boutons-arcade.json"
[ -f "$DEPOT/donnees/mame-fiches.txt" ] && cp "$DEPOT/donnees/mame-fiches.txt" "$N/mame-fiches.txt"

echo "4. le crochet de demarrage"
cp "$ICI/custom.sh" /recalbox/share/system/custom.sh

echo "5. les scripts allinone d origine, hors service"
for f in "allinone[startgameclip].sh" "allinone[systembrowsing].sh"; do
    [ -f "$U/$f" ] && mv -f "$U/$f" "$U/$f.off"
done

echo "6. relance"
sh "$N/relancer.sh" panneau
sh "$N/relancer.sh" credits
echo
echo "Installe. Survole un jeu dans le menu : les boutons qu il utilise s allument."
echo "Journaux : $N/panneau.log et $N/credits.log"
