#!/bin/sh
# L etat de tout, en une commande. Voir EN-CAS-DE-COUPURE.md si ca cloche.
echo "=== $(date '+%A %d %B, %H:%M') ==="
echo
for u in campagne-credits naomi-pc; do
    printf "%-20s %s\n" "$u" "$(systemctl is-active $u)"
done
echo
echo "--- la base ---"
python3 -c "
import json, collections
b = json.load(open('/mnt/recalbox/donnees/credits-arcade.json'))
c = collections.Counter(k.split('/')[0] for k in b['jeux'])
e = collections.Counter(k.split('/')[0] for k in b['difficiles'])
for k in sorted(set(c) | set(e), key=lambda x: -c[x]):
    print('  %-16s %6d trouves %6d ecartes' % (k, c[k], e[k]))
print('  %-16s %6d' % ('TOTAL', len(b['jeux'])))
" 2>/dev/null || echo "  base illisible"
echo
echo "--- la campagne ---"
tail -3 /mnt/recalbox/journaux/campagne.log 2>/dev/null | sed 's/^/  /'
echo
echo "--- Naomi ---"
journalctl -u naomi-pc --no-pager -o cat --since "-2h" 2>/dev/null \
    | grep -E "^\[|APPRIS" | tail -3 | sed 's/^/  /'
echo
echo "--- la borne ---"
tail -2 /mnt/recalbox/journaux/deploiement.log 2>/dev/null | sed 's/^/  /'
echo
echo "--- le disque ---"
df -h / | tail -1 | awk '{print "  "$4" libres ("$5" occupe)"}'
