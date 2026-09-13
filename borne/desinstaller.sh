#!/bin/sh
# Retire le panneau lumineux et remet la borne comme avant.
#     sh borne/desinstaller.sh
U=/recalbox/share/userscripts
N=/recalbox/share/system/panneau-arcade
for p in /proc/[0-9]*; do
    comm=$(cat "$p/comm" 2>/dev/null)
    case "$comm" in python3|python) ;; *) continue ;; esac
    tr '\0' ' ' < "$p/cmdline" 2>/dev/null | grep -q -E "userscripts/(credits|panneau)\(permanent\)" && kill "${p#/proc/}" 2>/dev/null
done
rm -f "$U/credits(permanent).py" "$U/panneau(permanent).py" "$U/gardefou[start,rungame,endgame].ash" "$U/README.md"
for f in "allinone[startgameclip].sh" "allinone[systembrowsing].sh"; do
    [ -f "$U/$f.off" ] && mv -f "$U/$f.off" "$U/$f"
done
rm -f /recalbox/share/system/custom.sh
echo "Programmes retires, scripts d origine remis. Les donnees et sauvegardes restent dans $N ;"
echo "supprime ce dossier a la main si tu n en veux plus. Redemarre la borne pour que tout reparte propre."
