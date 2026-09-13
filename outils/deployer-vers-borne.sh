#!/bin/sh
# Envoie les bases a jour sur la borne, sans jamais deranger une partie.
#
#   1. la base des credits est exportee dans la forme que le demon lit
#      (index par systeme, voir exporter-pour-borne.py)
#   2. les deux fichiers sont copies sur la borne
#   3. le demon des credits ne relit sa base qu au demarrage : on le
#      redemarre — mais SEULEMENT si EmulationStation dit qu aucune partie
#      n est en cours. Sinon on laisse, la prochaine passe s en chargera.
#      Le script du menu, lui, recharge les boutons tout seul.
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
EXPORT=/mnt/recalbox/donnees/pour-borne.json
FICHES_MAME=/mnt/recalbox/donnees/mame-fiches.txt
BORNE_MAME=/recalbox/share/system/panneau-arcade
JOURNAL=/mnt/recalbox/journaux/deploiement.log
SSH="setsid -w ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=no"
note() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $1" >> "$JOURNAL"; }

python3 /mnt/recalbox/outils/exporter-pour-borne.py --base "$DONNEES/credits-arcade.json" --sortie "$EXPORT" --fiches-mame "$FICHES_MAME" >/dev/null 2>&1 || { note "export impossible"; exit 1; }
$SSH $BORNE true 2>/dev/null || { note "borne injoignable"; exit 1; }
setsid -w scp -q -o StrictHostKeyChecking=no "$EXPORT" $BORNE:/recalbox/share/system/panneau-arcade/credits-arcade.json 2>/dev/null || { note "copie credits echouee"; exit 1; }
setsid -w scp -q -o StrictHostKeyChecking=no "$DONNEES/boutons-arcade.json" $BORNE:/recalbox/share/system/panneau-arcade/boutons-arcade.json 2>/dev/null
# MAME : la liste des adresses que lit le Lua pendant la partie.
setsid -w scp -q -o StrictHostKeyChecking=no "$FICHES_MAME" $BORNE:$BORNE_MAME/mame-fiches.txt 2>/dev/null
N=$(python3 -c "import json;print(len(json.load(open('$EXPORT'))['jeux']))")
ETAT=$($SSH $BORNE "grep -E '^State=' /tmp/es_state.inf 2>/dev/null | cut -d= -f2")
if [ "$ETAT" = "playing" ]; then
    note "$N fiches copiees, partie en cours : le demon relira au prochain passage"
    exit 0
fi
$SSH $BORNE "for p in \$(ps -o pid,args | grep 'credits(permanent)' | grep -v grep | awk '{print \$1}'); do kill \$p; done; sleep 2; cd /recalbox/share/userscripts && nohup /usr/bin/python -u '/recalbox/share/userscripts/credits(permanent).py' >> /recalbox/share/system/panneau-arcade/credits-erreurs.log 2>&1 &" 2>/dev/null
note "$N fiches copiees, demon redemarre"
