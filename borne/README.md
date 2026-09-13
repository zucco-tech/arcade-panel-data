# La borne

Ce dossier est **la copie exacte de ce qu'il y a sur la borne**. Rien à
installer : on copie, on redémarre.

```
borne/share/                          →  /recalbox/share/
    userscripts/
        credits(permanent).py             pendant une partie : les crédits, PIÈCE et START qui clignotent
        panneau(permanent).py             dans le menu : les boutons du jeu survolé, dans ses couleurs
        marquee(permanent).py             le nom du jeu sur le marquee (facultatif)
        gardefou[start,rungame,endgame].ash   relance un programme permanent qui serait mort
    system/
        custom.sh                         crochet de démarrage Recalbox (voir plus bas)
        panneau-arcade/
            credits-arcade.json           où lire les crédits, par système et par jeu
            boutons-arcade.json           combien de boutons, combien de joueurs, couleurs
            mame-fiches.txt               les adresses MAME, une ligne par jeu
            relancer.sh                   sh relancer.sh credits|panneau|marquee
            outils/                       mame-rapport.lua, releve-poli.py : facultatifs, voir plus bas
```

## Mettre en place sur une borne

Il faut une borne sous Recalbox avec une carte **AllInOne** (digipcb.tech) :
le dossier `/sys/class/leds/` y contient des `aio_p1_b1_1`, `aio_p1_start`…

1. Copier le **contenu** de `borne/share/` dans la share de la borne
   (`\\RECALBOX\share` depuis Windows, ou une clé USB) : les dossiers
   `userscripts` et `system` se fondent dans ceux qui existent déjà.
2. Redémarrer la borne.

C'est tout. Au démarrage, `custom.sh` met hors service les deux scripts
`allinone[…].sh` d'origine (renommés `.off`) et EmulationStation lance les
programmes `(permanent)`. Le système Recalbox n'est pas touché : tout est
dans la share, et pour revenir en arrière on supprime ces fichiers et on
remet les `.off` à leur nom.

Les journaux disent ce que le panneau fait, jeu par jeu :
`system/panneau-arcade/panneau.log` (le menu) et `credits.log` (les parties).

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
dans la mémoire du jeu (adresse dans `credits-arcade.json`) : PIÈCE
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
les couleurs qu'il a posées dans `panneau-arcade/couleurs-carte.json` et le
démon des crédits les y lit : une seule mémoire, pas de couleur perdue.

## MAME

Le cœur MAME ne donne pas accès à sa mémoire par RetroArch. Sous MAME, le
démon des crédits **déduit** donc le compteur des boutons : une pièce
ajoute un crédit, un START en retire un. Le comportement est le même
(PIÈCE clignote, puis START), sans lecture exacte.

`outils/mame-rapport.lua` sait lire le vrai compteur de l'intérieur de MAME
(il cherche la machine dans `mame-fiches.txt` et écrit le nombre dans
`/tmp/mame-credits`), mais Recalbox 10 fixe le dossier des `.ini` de MAME
dans le système en lecture seule : il n'y a pas de moyen propre de lui
faire charger ce script. Il est là pour le jour où ce sera possible.

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
serait mort (journal dans `panneau-arcade/gardefou.log`). Une borne sans
marquee n'a rien à faire : il ne relance que ce qui est présent.

## Les données viennent du PC

`credits-arcade.json`, `boutons-arcade.json` et `mame-fiches.txt` sont
fabriqués sur le PC de relevé (`outils/exporter-pour-borne.py`) et poussés
sur la borne toutes les 30 minutes, jamais pendant une partie
(`outils/deployer-vers-borne.sh`, qui met aussi à jour la copie de ce
dossier). Le démon des crédits ne relit sa base qu'à son démarrage :
`sh system/panneau-arcade/relancer.sh credits` après avoir remplacé le
fichier. Le panneau, lui, recharge les boutons tout seul.

`outils/releve-poli.py` mesure les crédits **sur la borne elle-même**, jeu
par jeu, en pilotant EmulationStation par UDP et sans jamais déranger une
partie. Il n'est pas lancé : le PC va plus vite.
