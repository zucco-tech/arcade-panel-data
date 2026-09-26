#!/bin/sh
# Ramene sur le PC ce que la borne a mesure elle-meme (releve-borne.json),
# le replie dans la base commune, puis renvoie les fichiers a la borne.
#
# Regles de repli, dans cet ordre :
#   - un jeu inconnu de la base : on le prend ;
#   - un jeu que le PC avait lu dans une sauvegarde d etat : la mesure de la
#     borne REMPLACE celle du PC (une position dans l etat ne vaut que pour le
#     coeur qui l a ecrite : assault, 0x20026 sur le PC, 0x20036 sur la borne) ;
#   - sinon, la base garde ce qu elle a ;
#   - un ecarte n est ajoute que si la base ne connait pas le jeu du tout.
BORNE=root@192.168.1.50
INVITE=${INVITE_BORNE:-/mnt/recalbox/outils/.mdp-borne.sh}
[ -x "$INVITE" ] || INVITE=/var/tmp/.mdp-borne-$(id -u).sh
[ -x "$INVITE" ] || { printf '#!/bin/sh\necho recalboxroot\n' > "$INVITE"; chmod 700 "$INVITE"; }
export SSH_ASKPASS="$INVITE" SSH_ASKPASS_REQUIRE=force DISPLAY=${DISPLAY:-:0}
SCP="setsid -w scp -q -o ConnectTimeout=10 -o StrictHostKeyChecking=no"
BASE=/mnt/recalbox/donnees/credits-arcade.json
SUR_BORNE=/recalbox/share/system/panneau-allinone/releve-borne.json
JOURNAL=/mnt/recalbox/journaux/rapatriement.log
note() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $1" | tee -a "$JOURNAL"; }
T=$(mktemp)
$SCP $BORNE:$SUR_BORNE "$T" 2>/dev/null || { note "borne injoignable, rien rapatrie"; rm -f "$T"; exit 1; }
RESUME=$(python3 - "$BASE" "$T" <<'PYTHON'

import json, os, sys
base = json.load(open(sys.argv[1]))
borne = json.load(open(sys.argv[2]))
def par_etat(f): return ((f or {}).get("ram") or {}).get("commande") == "sauvegarde d etat"
def de_la_borne(f): return ((f or {}).get("ram") or {}).get("hote") == "BORNEARCADE"
pris = remplaces = ecartes = 0
for cle, fiche in (borne.get("jeux") or {}).items():
    ancienne = base["jeux"].get(cle)
    if ancienne is None:
        base["jeux"][cle] = fiche; base["difficiles"].pop(cle, None); pris += 1
    elif par_etat(ancienne) and not de_la_borne(ancienne) and de_la_borne(fiche):
        base["jeux"][cle] = fiche; remplaces += 1
for cle, ecart in (borne.get("difficiles") or {}).items():
    if cle not in base["jeux"] and cle not in base["difficiles"]:
        base["difficiles"][cle] = ecart; ecartes += 1
prov = sys.argv[1] + ".tmp"
json.dump(base, open(prov, "w"), indent=1, ensure_ascii=False)
os.replace(prov, sys.argv[1])
print("%d fiche(s) nouvelles, %d mesure(s) du PC remplacees par celles de la borne, %d ecarte(s) ; base : %d fiches, %d ecartes"
      % (pris, remplaces, ecartes, len(base["jeux"]), len(base["difficiles"])))
PYTHON
) || { rm -f "$T"; note "repli impossible"; exit 1; }
rm -f "$T"
note "rapatrie : $RESUME"
sh /mnt/recalbox/outils/deployer-vers-borne.sh >/dev/null 2>&1 && note "renvoye sur la borne" || note "renvoi vers la borne a refaire"
