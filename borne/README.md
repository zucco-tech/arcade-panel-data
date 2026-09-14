# La borne

Ce dossier est **la copie exacte de ce qu'il y a sur la borne**, aux mêmes
emplacements. Rien à installer : on copie six fichiers, on redémarre.

```
borne/share/                          →  /recalbox/share/
    userscripts/
        credits(permanent).py             pendant une partie : les crédits, PIÈCE et START qui clignotent
        panneau(permanent).py             dans le menu : les boutons du jeu survolé, dans ses couleurs
        marquee(permanent).py             le nom du jeu sur le marquee (facultatif)
        gardefou[start,rungame,endgame].ash   relance un programme permanent qui serait mort
    system/
        custom.sh                         crochet de démarrage Recalbox (voir plus bas)
        panneau-allinone/
            credits/
                fbneo.json, mame.json…    où lire les crédits, un fichier par système
                pistes.json               les adresses de cheats, par nom de set
                appris.json               ce que la borne a appris elle-même (créé par elle)
            boutons-arcade.json           combien de boutons, combien de joueurs, couleurs
            relancer.sh                   sh relancer.sh credits|panneau|marquee
            journaux/                     ce que les programmes ont fait, jeu par jeu (créé par eux)
            etat/                         couleurs posées, signe de vie du panneau (créé par eux)
```

## Mettre en place sur une borne

Il faut une borne sous Recalbox avec une carte **AllInOne** (digipcb.tech) :
le dossier `/sys/class/leds/` y contient des `aio_p1_b1_1`, `aio_p1_start`…

Six fichiers à copier dans la share de la borne (`\\RECALBOX\share` sur le
réseau, ou la clé USB qui la porte), puis redémarrer :

| à copier | dans |
|---|---|
| `userscripts/credits(permanent).py` | `share\userscripts\` |
| `userscripts/panneau(permanent).py` | `share\userscripts\` |
| `userscripts/gardefou[start,rungame,endgame].ash` | `share\userscripts\` |
| `userscripts/marquee(permanent).py` | `share\userscripts\` — facultatif, seulement s'il y a un marquee |
| `system/custom.sh` | `share\system\` |
| `system/panneau-allinone/` (le dossier entier) | `share\system\` |

**Rien d'autre n'est touché.** On ajoute ces fichiers, on n'en remplace
aucun : les roms, les bios, les sauvegardes et tout le reste de la share
restent tels quels. Aucun fichier du système Recalbox n'est modifié.

Au redémarrage, `custom.sh` met hors service les deux scripts
`allinone[…].sh` d'origine (renommés `.off`, pas supprimés) et
EmulationStation lance les programmes `(permanent)`. Pour revenir en
arrière : supprimer ces six fichiers et remettre les `.off` à leur nom.

Pour vérifier que ça tourne : survoler un jeu dans le menu, ses boutons
s'allument. Les journaux disent ce que le panneau fait, jeu par jeu :
`system/panneau-allinone/journaux/panneau.log` (le menu) et `credits.log` (les parties).

## Ce que fait le panneau

**Dans le menu** — `panneau(permanent).py` lit l'état d'EmulationStation
(`/tmp/es_state.inf`) et écoute les manettes sans les accaparer :

- au survol d'un jeu, seuls les boutons qu'il utilise s'allument, dans ses
  couleurs d'origine ; pour une console, le nombre de boutons de la
  manette ; sans fiche, la table de couleurs de Recalbox pour ce système ;
- le poste 2 reste noir pour un jeu à un joueur ;
- quelqu'un est devant (un geste sur une manette, une navigation) :
  `PRESENT` (255, plein), les deux START et la PIÈCE allumés, le HK aussi ;
- personne depuis `VEILLE_APRES` secondes (30), la borne se raconte toute
  seule : `CLIP` (128, tamisé), les deux START allumés, PIÈCE et HK éteints.
  Les clips vidéo ne réveillent pas le panneau, un joueur oui.

**Pendant la partie** — `credits(permanent).py` lit le compteur de crédits
dans la mémoire du jeu (adresse dans `credits/<système>.json`) : PIÈCE
clignote tant qu'il n'y a pas de crédit, START prend le relais dès qu'il y
en a un, puis tout reste fixe. Le panneau du menu se tait ; au retour au
menu il reprend, après avoir rendu les couleurs. Un jeu absent de la base
est appris la première fois qu'on y joue.

Réglages, tous en tête de `panneau(permanent).py` : `PRESENT`, `CLIP`,
`VEILLE_APRES`, `PORTABLES` (consoles portables : poste 2 toujours noir),
et deux particularités de la carte prototype : `ORDRE_MATERIEL` (les WS2812B
attendent vert, rouge, bleu) et l'échange `start`/`select` du driver
(`LED_PIECE`, `LED_START`).

## Qui pilote les LED, et quand

Deux programmes écrivent dans les LED, jamais en même temps :

```
menu, jeu survolé      panneau(permanent).py
partie en cours        credits(permanent).py   (panneau se tait)
retour au menu         panneau reprend, après avoir rendu les couleurs
```

Tous deux n'écrivent que dans `brightness`, et dans `multi_intensity`
seulement pour poser la couleur d'origine d'un bouton. Le panneau publie
les couleurs qu'il a posées dans `panneau-allinone/etat/couleurs-carte.json` et le
démon des crédits les y lit : une seule mémoire, pas de couleur perdue.

## MAME

Le cœur MAME ne donne pas accès à sa mémoire par RetroArch. Sous MAME, le
démon des crédits **déduit** donc le compteur des boutons : une pièce
ajoute un crédit, un START en retire un. Le comportement est le même
(PIÈCE clignote, puis START), sans lecture exacte.

Le dépôt garde, côté PC, `outils/mame-rapport.lua` : il sait lire le vrai
compteur de l'intérieur de MAME (avec la liste que produit
`exporter-pour-borne.py --fiches-mame`), mais Recalbox 10 fixe le dossier
des `.ini` de MAME dans le système en lecture seule et il n'y a pas de
moyen propre de lui faire charger ce script. Il n'est pas sur la borne ;
il attend le jour où ce sera possible.

## Au démarrage

`custom.sh` (dans `share/system/`, crochet officiel appelé par `S99custom`)
fait deux choses à chaque allumage :

1. il remet hors service `allinone[systembrowsing].sh` et
   `allinone[startgameclip].sh`, que `/etc/init.d/S13allinone` **recrée à
   chaque démarrage** — ils repeignent les LED à chaque mouvement de menu et
   se battraient avec `panneau(permanent).py` ;
2. il allume le panneau en veilleuse tout de suite, sans attendre
   EmulationStation, qui met plusieurs minutes à charger ses listes.

`gardefou[…].ash` est appelé au démarrage du frontend, au lancement et à la
fin de chaque partie : il relance celui des programmes permanents qui
serait mort (journal dans `panneau-allinone/journaux/gardefou.log`). Une borne sans
marquee n'a rien à faire : il ne relance que ce qui est présent.

## Les données

Les crédits tiennent dans `system/panneau-allinone/credits/`, **un fichier par
système** : `fbneo.json`, `mame.json`, `neogeo.json`… Chacun contient les
fiches de ce système, indexées par nom de set, et ses jeux écartés. À côté,
`pistes.json` : les adresses de cheats « crédits infinis », par nom de set,
là où chercher en premier quand un jeu est inconnu.

Le démon ne lit que le fichier du système du jeu lancé, au moment du
lancement. Rien n'est gardé en mémoire pour des milliers de jeux, et un
fichier remplacé est pris en compte à la partie suivante : **rien à
redémarrer** quand on met les données à jour.

Ces fichiers viennent du PC de relevé (`outils/exporter-pour-borne.py`),
qui les pousse sur la borne toutes les 30 minutes par renommage, fichier
par fichier (`outils/deployer-vers-borne.sh`, qui met aussi à jour la copie
de ce dossier). La borne n'y écrit jamais.

Ce qu'elle apprend elle-même va dans `credits/appris.json`, qu'elle crée à
la première occasion et que le PC ne touche pas : l'adresse d'un jeu absent
des fichiers du PC, trouvée en jouant ; un jeu qui a accepté ou refusé le
joueur 2 ; un jeu où la recherche a échoué. Une fiche du PC prime sur une
fiche apprise ; le constat sur le joueur 2 prime toujours.

`boutons-arcade.json` reste un seul fichier : il est indexé par nom de set,
parce que `1942` a les mêmes boutons sous FBNeo, MAME ou Neo Geo.

Côté PC aussi, `outils/releve-poli.py` sait mesurer les crédits **sur la
borne elle-même**, jeu par jeu, en pilotant EmulationStation par UDP et
sans jamais déranger une partie. Il n'est pas sur la borne : le PC de
relevé va plus vite.
