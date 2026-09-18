#!/bin/sh
# Fait chercher les adresses de credits PAR LA BORNE, poliment.
#
#   sudo sh /mnt/recalbox/outils/lancer-releve-borne.sh [fbneo neogeo ...]
#   sudo sh /mnt/recalbox/outils/lancer-releve-borne.sh --arreter
#   sudo sh /mnt/recalbox/outils/lancer-releve-borne.sh --ou-en-est
#
# Pourquoi la borne et pas le PC. Le coeur FBNeo du PC (Recalbox 10.1, x86)
# n expose pas la memoire de travail des cartes CPS2 : la zone qu il rend
# reste a zero pendant que le jeu tourne et compte les credits a l ecran
# (verifie sur 1944 le 18/09/2026, image a l appui). Aucune recherche ne peut
# aboutir la. La borne, elle, lit la memoire par RetroArch (READ_CORE_RAM) et
# repond bien sur les memes jeux : c est donc elle qui doit les mesurer.
#
# Poliment : releve-poli.py ne demarre qu apres 3 minutes sans un geste, rend
# la main au premier bouton presse, et ne relance rien tant que quelqu un
# joue. La borne reste a son proprietaire.
#
# Ce qui est repris : seulement les jeux ou la recherche a VRAIMENT echoue
# (aucun candidat, candidats non confirmes, jeu inanime, delai depasse). Les
# roms que le coeur refuse (romset inconnu, jeu non supporte) sont laissees
# de cote : la borne les refusera pareil, c est le romset qu il faut completer.
BORNE=root@192.168.1.50
INVITE=/mnt/recalbox/outils/.mdp-borne.sh
[ -x "$INVITE" ] || { printf '#!/bin/sh\necho recalboxroot\n' > "$INVITE"; chmod 700 "$INVITE"; }
export SSH_ASKPASS="$INVITE" SSH_ASKPASS_REQUIRE=force DISPLAY=${DISPLAY:-:0}
SSH="setsid -w ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no"
SCP="setsid -w scp -q -o ConnectTimeout=10 -o StrictHostKeyChecking=no"
OUTILS=$(cd "$(dirname "$0")" && pwd)
SUR_BORNE=/recalbox/share/system/panneau-allinone
BASE=/mnt/recalbox/donnees/credits-arcade.json
RAISONS_A_REPRENDRE="aucun candidat|candidats non confirmes|jeu inanime|delai depasse"

case "$1" in
    --arreter)
        $SSH $BORNE "touch /tmp/arret-releve-poli; sleep 2; pkill -f releve-poli.py; pkill -f nuit-credits.py; echo arrete"
        exit $?
        ;;
    --ou-en-est)
        $SSH $BORNE "tail -6 $SUR_BORNE/releve.log 2>/dev/null; echo ---; python3 -c \"
import json
b = json.load(open('$SUR_BORNE/releve-borne.json'))
print(len(b.get('jeux') or {}), 'fiches,', len(b.get('difficiles') or {}), 'ecartes')\" 2>/dev/null"
        exit $?
        ;;
esac

SYSTEMES="${*:-fbneo neogeo neogeocd}"
echo "=== 1. la base de depart : ce que le PC sait deja"
python3 - "$BASE" "$RAISONS_A_REPRENDRE" <<'PYTHON' > /tmp/releve-borne-depart.json
import json, re, sys
base = json.load(open(sys.argv[1]))
motifs = re.compile(sys.argv[2])
durs = {c: d for c, d in (base.get("difficiles") or {}).items()
        if not motifs.match(str(d.get("raison") or ""))}
repris = len(base.get("difficiles") or {}) - len(durs)
json.dump({"jeux": base.get("jeux") or {}, "difficiles": durs}, sys.stdout, indent=1)
print("%d fiche(s) connues, %d ecarte(s) laisses de cote, %d a reprendre par la borne"
      % (len(base.get("jeux") or {}), len(durs), repris), file=sys.stderr)
PYTHON

echo "=== 2. les programmes et la base sur la borne"
$SSH $BORNE "mkdir -p $SUR_BORNE/outils" || exit 1
$SCP "$OUTILS/releve-poli.py" "$OUTILS/nuit-credits.py" $BORNE:$SUR_BORNE/outils/ || exit 1
$SCP /tmp/releve-borne-depart.json $BORNE:$SUR_BORNE/releve-borne.json.tmp || exit 1
$SSH $BORNE "mv -f $SUR_BORNE/releve-borne.json.tmp $SUR_BORNE/releve-borne.json" || exit 1

echo "=== 3. en route (il attend le silence avant de commencer)"
$SSH $BORNE "rm -f /tmp/arret-releve-poli /tmp/arret-nuit
pkill -f releve-poli.py 2>/dev/null
cd $SUR_BORNE/outils && setsid nohup python3 -u releve-poli.py --systemes $SYSTEMES \
    > $SUR_BORNE/releve-poli.log 2>&1 < /dev/null &
sleep 2; pgrep -f releve-poli.py >/dev/null && echo 'releve poli en route' || echo 'ECHEC du lancement'"

echo
echo "Suivre :  sudo sh $0 --ou-en-est"
echo "Arreter : sudo sh $0 --arreter"
