#!/bin/sh
# Le controle de sante de la borne, en une commande et une dizaine de lignes.
#
#   sh /mnt/recalbox/outils/sante-borne.sh
#
# Repond a quatre questions : la borne tient-elle la charge (processeur,
# memoire, temperature, bridage), nos trois programmes permanents sont-ils
# vivants et discrets, ont-ils note des erreurs ou ete relances par le
# garde-fou, et font-ils leur travail (dernier jeu vu par le panneau,
# derniere lecture de credits). Chaque ligne ALERTE est un vrai souci ;
# sans alerte, la borne va bien. Le rapport est aussi ajoute au journal
# journaux/sante.log, et la commande rend 1 s il y a au moins une alerte —
# pour qu un appel automatique puisse le savoir.
#
# Tout est mesure sur la borne, par ssh, sans rien y ecrire.
BORNE=root@192.168.1.50
INVITE=/mnt/recalbox/outils/.mdp-borne.sh
JOURNAL=/mnt/recalbox/journaux/sante.log
[ -x "$INVITE" ] || { printf '#!/bin/sh\necho recalboxroot\n' > "$INVITE"; chmod 700 "$INVITE"; }
export SSH_ASKPASS="$INVITE" SSH_ASKPASS_REQUIRE=force DISPLAY=${DISPLAY:-:0}

rapport=$(setsid -w ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$BORNE" sh 2>/dev/null <<'SUR_LA_BORNE'
N=/recalbox/share/system/panneau-allinone
tics=$(getconf CLK_TCK 2>/dev/null || echo 100)
maintenant=$(date +%s)

# --- la machine ---
charge=$(cut -d' ' -f1 /proc/loadavg)
libre=$(awk '/MemAvailable/{printf "%d", $2/1024}' /proc/meminfo)
temp=$(awk '{printf "%d", $1/1000}' /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
bride=$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)
echo "machine    charge $charge, $libre Mo libres, $temp C, bridage ${bride:-inconnu}, allumee depuis $(uptime | sed 's/.*up //; s/,  *load.*//; s/, *[0-9]* user.*//')"
[ "$temp" -ge 75 ] 2>/dev/null && echo "ALERTE     temperature $temp C : le boitier chauffe"
[ -n "$bride" ] && [ "$bride" != "0x0" ] && echo "ALERTE     le Raspberry se bride ($bride) : alimentation ou chaleur"

# --- nos programmes : vivants, et ce qu ils coutent sur 5 secondes ---
for nom in panneau credits marquee; do
  pid=""
  for p in /proc/[0-9]*; do tr '\0' ' ' < $p/cmdline 2>/dev/null | grep -q "userscripts/$nom(permanent)" && pid=${p#/proc/} && break; done
  if [ -z "$pid" ]; then echo "ALERTE     $nom(permanent).py n est pas en marche"; continue; fi
  a=$(awk '{print $14+$15}' /proc/$pid/stat); eval a_$nom=$a; eval pid_$nom=$pid
done
sleep 5
for nom in panneau credits marquee; do
  eval pid=\$pid_$nom; [ -z "$pid" ] && continue
  eval a=\$a_$nom; b=$(awk '{print $14+$15}' /proc/$pid/stat)
  cpu=$(( (b - a) * 100 / tics / 5 ))
  ram=$(awk '/VmRSS/{printf "%d", $2/1024}' /proc/$pid/status)
  printf "%-10s vivant, processeur %d %%, memoire %d Mo\n" "$nom" "$cpu" "$ram"
  [ "$cpu" -ge 5 ] && echo "ALERTE     $nom consomme $cpu % de processeur : il devrait dormir"
  [ "$ram" -ge 150 ] && echo "ALERTE     $nom occupe $ram Mo : fuite de memoire probable"
done

# --- erreurs et relances ---
erreurs=$(cat $N/journaux/*-erreurs.log 2>/dev/null | wc -l)
relances=$(grep -c "relance" $N/journaux/gardefou.log 2>/dev/null)
derniere=$(tail -n 1 $N/journaux/gardefou.log 2>/dev/null | cut -c1-16)
echo "erreurs    $erreurs ligne(s) dans les journaux d erreurs ; $relances relance(s) par le garde-fou${derniere:+, derniere le $derniere}"
[ "$erreurs" -gt 0 ] && echo "ALERTE     $erreurs erreur(s) : lire $N/journaux/*-erreurs.log"

# --- font-ils leur travail ---
if [ -f $N/journaux/panneau.log ]; then
  age=$(( maintenant - $(date -r $N/journaux/panneau.log +%s) ))
  echo "panneau    dernier jeu vu il y a $(( age / 60 )) min : $(tail -n 1 $N/journaux/panneau.log | cut -c21-90)"
  pidof emulationstation >/dev/null && [ "$age" -gt 1800 ] && echo "ALERTE     le panneau n a rien vu depuis $(( age / 60 )) min alors que le frontend tourne"
fi
if [ -f $N/journaux/credits.log ]; then
  echo "credits    derniere lecture il y a $(( (maintenant - $(date -r $N/journaux/credits.log +%s)) / 60 )) min : $(tail -n 1 $N/journaux/credits.log | cut -c21-90)"
fi
total=0; for f in $N/credits/*.json; do case $f in *pistes.json|*appris.json) continue;; esac; n=$(python -c "import json;print(len(json.load(open('$f')).get('jeux',{})))" 2>/dev/null || echo 0); total=$((total + n)); done
echo "fiches     $total en place, $(python -c "import json;print(len(json.load(open('$N/credits/appris.json')).get('jeux',{})))" 2>/dev/null || echo 0) apprises par la borne elle-meme"

# --- qui consomme vraiment, pour ne pas accuser a tort ---
echo "gourmands  $(ps -o pcpu,comm 2>/dev/null | sort -rn | head -n 3 | awk '{printf "%s %s%%  ", $2, $1}' )"
SUR_LA_BORNE
)
if [ -z "$rapport" ]; then
    rapport="ALERTE     borne injoignable"
fi
echo "$rapport"
{ echo "=== $(date '+%Y-%m-%d %H:%M:%S')"; echo "$rapport"; } >> "$JOURNAL"
echo "$rapport" | grep -q "^ALERTE" && exit 1
exit 0
