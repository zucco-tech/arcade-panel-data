#!/bin/sh
# Relance proprement un des programmes permanents de la borne.
#
#   sh relancer.sh credits      (ou panneau, ou marquee)
#
# Tue toutes les instances du programme — il n en faut jamais qu une, deux
# se disputent les LED — puis en lance une seule. On cherche les processus
# par leur ligne de commande dans /proc, jamais par un « grep » sur « ps »
# qui attraperait aussi le shell qui l execute (et se tuerait lui-meme).
NOM=$1
U=/recalbox/share/userscripts
N=/recalbox/share/system/panneau-allinone
PROGRAMME="$U/$NOM(permanent).py"
mkdir -p "$N/journaux" "$N/etat"
[ -f "$PROGRAMME" ] || { echo "inconnu : $NOM"; exit 1; }

# Les numeros des instances de ce programme, sauf ce shell lui-meme.
instances() {
    for p in /proc/[0-9]*; do
        pid=${p#/proc/}
        [ "$pid" = "$$" ] && continue
        case "$(cat "$p/comm" 2>/dev/null)" in python3|python) ;; *) continue ;; esac
        tr '\0' ' ' < "$p/cmdline" 2>/dev/null | grep -q "userscripts/$NOM(permanent)" && echo "$pid"
    done
}

for pid in $(instances); do kill "$pid" 2>/dev/null; done
sleep 2
cd "$U" && setsid nohup /usr/bin/python -u "$PROGRAMME" >> "$N/journaux/$NOM-erreurs.log" 2>&1 &
sleep 3
echo "$NOM : $(instances | wc -l) instance(s)"
