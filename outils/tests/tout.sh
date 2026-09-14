#!/bin/sh
# Tous les bancs d essai, l un apres l autre, et un verdict.
#
#   sh outils/tests/tout.sh            # depuis n importe ou
#
# Aucun materiel : chaque banc parle a un RetroArch simule et a un faux
# panneau de LED dans un dossier temporaire. Un banc = une ligne, avec sa
# duree ; a la fin, le compte. La commande rend 1 des qu un banc est rouge —
# c est elle que les commits doivent regarder.
ICI=$(cd "$(dirname "$0")" && pwd)
rouges=0; total=0
for banc in "$ICI"/test_*.py; do
    nom=$(basename "$banc" .py); total=$((total + 1))
    debut=$(date +%s)
    sortie=$(timeout 600 python3 "$banc" 2>&1); code=$?
    duree=$(( $(date +%s) - debut ))
    # Chaque banc conclut par « TOUT EST BON » ou « N essai(s), 0 rate(s) ».
    if [ $code -eq 0 ] && echo "$sortie" | grep -q "TOUT EST BON\|, 0 rate(s)"; then
        printf "  ok    %-16s %3d s\n" "$nom" "$duree"
    else
        rouges=$((rouges + 1))
        printf "  ROUGE %-16s %3d s\n" "$nom" "$duree"
        echo "$sortie" | grep -E "ECHEC|RATE|Error|Traceback|ECHECS" | head -n 5 | sed 's/^/        /'
    fi
done
if [ $rouges -eq 0 ]; then echo "$total banc(s), tous verts"; exit 0; fi
echo "$total banc(s), $rouges rouge(s)"; exit 1
