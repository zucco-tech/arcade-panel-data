# Fonctions communes a relancer.sh et au garde-fou : trouver et lancer un
# programme permanent. A sourcer :
#     . /recalbox/share/system/panneau-allinone/processus.sh
U=/recalbox/share/userscripts
N=/recalbox/share/system/panneau-allinone

# Les numeros des instances du programme $1 (credits, panneau ou marquee),
# sauf le shell qui appelle. On lit /proc, jamais « ps | grep » : un grep
# attraperait le shell lui-meme, et se tuerait.
instances() {
    for p in /proc/[0-9]*; do
        pid=${p#/proc/}
        [ "$pid" = "$$" ] && continue
        case "$(cat "$p/comm" 2>/dev/null)" in python3|python) ;; *) continue ;; esac
        tr '\0' ' ' < "$p/cmdline" 2>/dev/null | grep -q "userscripts/$1(permanent)" && echo "$pid"
    done
}

# Lance une instance du programme $1, detachee, ses erreurs dans un journal
# a part. « -u » : sans lui, python garde ses lignes en memoire et le journal
# arrive avec des minutes de retard.
lancer() {
    mkdir -p "$N/journaux" "$N/etat"
    cd "$U" && setsid nohup /usr/bin/python -u "$U/$1(permanent).py" >> "$N/journaux/$1-erreurs.log" 2>&1 &
}
