#!/bin/sh
# Envoie les bases a jour sur la borne, sans jamais deranger une partie.
#
#   1. la base des credits est exportee dans la forme que le demon lit :
#      un fichier par systeme, plus les pistes (voir exporter-pour-borne.py)
#   2. ces fichiers et les boutons sont copies sur la borne,
#      d abord dans un dossier de passage, puis mis en place un par un
#      (un renommage est atomique : le demon ne lit jamais un fichier a
#      moitie ecrit)
#   3. rien a redemarrer : le demon lit le fichier du systeme au lancement
#      de chaque jeu, la partie suivante voit les nouvelles fiches
#
# La copie de la share dans le depot suit : ce que voit GitHub est ce que la
# borne a.
#
# Authentification : le systeme de la borne est en lecture seule, on ne peut
# pas y poser de cle SSH. On passe par le mot de passe par defaut de Recalbox,
# qui est public (documentation Recalbox). Il est fourni a ssh par un petit
# programme d invite, ce que ssh exige quand il n y a pas de terminal.
BORNE=root@192.168.1.50
INVITE=/mnt/recalbox/outils/.mdp-borne.sh
[ -x "$INVITE" ] || { printf '#!/bin/sh\necho recalboxroot\n' > "$INVITE"; chmod 700 "$INVITE"; }
export SSH_ASKPASS="$INVITE" SSH_ASKPASS_REQUIRE=force DISPLAY=${DISPLAY:-:0}
DONNEES=/mnt/recalbox/donnees
EXPORT=/mnt/recalbox/donnees/pour-borne          # un <systeme>.json par systeme + pistes.json
DEPOT_BORNE=/mnt/recalbox/depot/borne/share/system/panneau-allinone
SUR_BORNE=/recalbox/share/system/panneau-allinone
JOURNAL=/mnt/recalbox/journaux/deploiement.log
SSH="setsid -w ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=no"
SCP="setsid -w scp -q -o StrictHostKeyChecking=no"
note() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $1" >> "$JOURNAL"; }

python3 /mnt/recalbox/outils/exporter-pour-borne.py --base "$DONNEES/credits-arcade.json" --dossier "$EXPORT" >/dev/null 2>&1 || { note "export impossible"; exit 1; }
if [ -d "$DEPOT_BORNE" ]; then
    mkdir -p "$DEPOT_BORNE/credits"
    cp "$EXPORT"/*.json "$DEPOT_BORNE/credits/"
    cp "$DONNEES/boutons-arcade.json" "$DEPOT_BORNE/boutons-arcade.json"
fi
$SSH $BORNE true 2>/dev/null || { note "borne injoignable"; exit 1; }
$SSH $BORNE "rm -rf $SUR_BORNE/credits.tmp && mkdir -p $SUR_BORNE/credits.tmp $SUR_BORNE/credits" 2>/dev/null
$SCP "$EXPORT"/*.json $BORNE:$SUR_BORNE/credits.tmp/ 2>/dev/null || { note "copie credits echouee"; exit 1; }
$SCP "$DONNEES/boutons-arcade.json" $BORNE:$SUR_BORNE/credits.tmp/boutons-arcade.json 2>/dev/null
# Mise en place fichier par fichier, par renommage. appris.json, que seule la
# borne ecrit, n est pas dans le lot et reste intact.
$SSH $BORNE "cd $SUR_BORNE/credits.tmp || exit 1
for f in *.json; do case \$f in boutons-arcade.json) mv -f \$f ../boutons-arcade.json;; *) mv -f \$f ../credits/\$f;; esac; done
cd .. && rmdir credits.tmp" 2>/dev/null || { note "mise en place echouee"; exit 1; }
N=$(python3 -c "
import json, glob
print(sum(len(json.load(open(f)).get('jeux', {})) for f in glob.glob('$EXPORT/*.json') if not f.endswith('pistes.json')))")
note "$N fiches en place sur la borne (un fichier par systeme)"
