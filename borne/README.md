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
            manettes-consoles.json        les manettes d'origine là où Recalbox se trompe : couleurs, START, SELECT, nombre de boutons
            cablage.py                    qui est qui sur le panneau : rôles (es_input.cfg) × câblage (cablage.json) → LED de chaque bouton
            cablage.json                  quel bouton envoie quel code, LED par LED — mesuré par associer-boutons
            couleurs.py                   palette par défaut, teintes nommées, ordre des couleurs lu dans multi_index
            reglages.py                   les réglages allinone.* lus dans recalbox.conf
            relancer.sh                   sh relancer.sh credits|panneau|marquee
            processus.sh                  ce que relancer.sh et le garde-fou ont en commun
            sauvegardes/                  anciennes versions gardées sous la main (créé à la main)
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

- au survol d'un jeu d'arcade, seuls les boutons qu'il utilise s'allument,
  dans ses couleurs d'origine ;
- au survol d'un jeu de console, d'ordinateur ou de portable, c'est la
  **manette d'origine** qui s'allume : ses boutons, leurs couleurs, et son
  START et son SELECT s'il les a — pas de SELECT sur Master System, Game
  Gear ou N64, START rouge sur N64, bleu sur Game Gear. La table de
  couleurs de Recalbox le sait déjà presque partout ; `manettes-consoles.json`
  la corrige là où elle se trompe (Game Boy magenta, Master System rouge,
  Game Boy Advance et Virtual Boy à quatre boutons) ;
- le poste 2 reste noir pour un jeu à un joueur, en veille aussi ;
- quelqu'un est devant (un geste sur une manette, une navigation) :
  `PRESENT` (255, plein), START et PIÈCE allumés, le HK aussi ;
- personne depuis `VEILLE_APRES` secondes (30), la borne se raconte toute
  seule : `CLIP` (128, tamisé), le HK s'éteint. Sur un jeu d'arcade la
  PIÈCE s'éteint aussi — un monnayeur n'invite personne ; sur une console
  elle reste allumée, parce que ce bouton est le SELECT de la manette, un
  bouton de jeu comme les autres. Les clips vidéo ne réveillent pas le
  panneau, un joueur oui.

**Pendant la partie** — `credits(permanent).py` lit le compteur de crédits
dans la mémoire du jeu (adresse dans `credits/<système>.json`) : PIÈCE
clignote tant qu'il n'y a pas de crédit, START prend le relais dès qu'il y
en a un, puis tout reste fixe. Les boutons de jeu, eux, ne clignotent
jamais : chaque jeu a sa logique de touches et le panneau ne la devine pas.
Sur un jeu à deux, pendant que le joueur 1 joue, le poste 2 invite : son START clignote s'il reste du crédit, sa PIÈCE sinon.
Chaque mouvement du compteur est noté dans `journaux/credits.log`
(`credits 0 -> 1`) : la preuve, en jouant, que l'adresse est la bonne. Deux
minutes sans le moindre geste — stick compris — et la partie est tenue pour
finie. Le panneau du menu se tait ; au retour au menu il reprend, après
avoir rendu les couleurs. Un jeu absent de la base est appris la première
fois qu'on y joue.

Les réglages de tous les jours sont dans `recalbox.conf` (voir plus bas,
« Régler la borne »). Restent en tête de `panneau(permanent).py` :
`PORTABLES` (consoles portables : poste 2 toujours noir), et deux
particularités de la carte prototype : l'ordre des couleurs (les WS2812B
attendent vert, rouge, bleu — `couleurs.ordre_materiel()` le lit dans
`multi_index` et sait que le pilote d'origine y ment, voir
`pilote-allinone/`) et l'échange `start`/`select` du driver
(`LED_PIECE`, `LED_START`). Quelle LED porte quel bouton n'est **pas** un
réglage : `cablage.py` le déduit du mappage Recalbox (`es_input.cfg`, celui
de « Configurer une manette ») et du câblage mesuré (`cablage.json`). On
remappe dans Recalbox, les LED suivent ; on recâble, on relance
`outils/associer-boutons.sh` et elles suivent aussi. Les manettes d'origine se corrigent sans
toucher au programme, dans `manettes-consoles.json` : une couleur en vrai
RGB, `null` pour un bouton absent, `nombre` quand Recalbox en compte trop
peu.

**Où sont les boutons du jeu — la règle de Recalbox, et notre choix.** Sur
un panneau déclaré `arcade6` dans l'assistant (les boutons pressés dans
l'ordre du dessin, 1 à 6), Recalbox ne passe pas les rôles tels quels à
l'émulateur : son `configgen` **réordonne** les six boutons pour tous les
systèmes sauf MAME (`GamepadInfo.shouldReshuffle6Btn`, alpha-3.2) :

```
MAME, menu d'EmulationStation      FBNeo, Neo Geo, consoles (règle Recalbox)
  [1] [2] [3]                        [3] [4] [5]
  [4] [5] [6]                        [1] [2] [6]
```

Choix du propriétaire (16/09/2026) : **bouton 1 en haut à gauche partout**,
comme une vraie borne, comme MAME et comme le menu. FBNeo et Neo Geo y sont
remis par une surcharge officielle de Recalbox, un fichier `.retroarch.cfg`
dans leur dossier de roms, écrit par `outils/aligner-boutons.py` à partir de
`es_input.cfg`. Aucun fichier de Recalbox n'est modifié ; les consoles
gardent la règle de Recalbox. `cablage.py` lit cette surcharge, dans le menu
comme en jeu : les LED suivent. À relancer après chaque « Configurer une
manette » ; `--retirer` rend la règle de Recalbox. Limite : les jeux de
combat FBNeo à six boutons rangent poings et pieds comme une manette, ils
peuvent se mélanger dans l'ordre du dessin — à vérifier jeu par jeu.

Ne jamais « corriger » `es_input.cfg` à la main pour changer la place des
boutons (leçon du 14/09/2026).

## Régler la borne

Les réglages vivent dans `recalbox.conf`, à côté de ceux de Recalbox
(`\\RECALBOX\share\system\recalbox.conf` sur le réseau). Aucun n'est
obligatoire : sans ces lignes, la borne se comporte exactement comme avant.
Pour en changer un, copier le bloc à la fin du fichier et retirer le `;`
devant la ligne voulue :

```
## AllInOne — le panneau lumineux (panneau(permanent).py, credits(permanent).py)
## Retirer le ; pour activer une ligne. Pris en compte en quelques secondes.
## Luminosité quand quelqu'un est devant la borne, et en partie (1 à 255)
;allinone.brightness=255
## Luminosité en veille, pendant les clips (0 à 255, 0 = éteint)
;allinone.brightness.idle=128
## Secondes sans geste avant la veille
;allinone.idle.delay=30
## 0 : borne à un seul poste, le panneau 2 ne s'allume jamais pour un jeu
;allinone.player2.enabled=1
## Couleur de la PIÈCE qui clignote quand il faut payer (RRGGBB)
;allinone.coin.color=FF0000
## Demi-période du clignotement, en secondes
;allinone.blink.period=0.5
## Secondes sans geste ni crédit après lesquelles une partie est tenue pour finie
;allinone.game.idle=120
```

Un changement est pris en compte en quelques secondes, sans rien
redémarrer ; pendant une partie, au retour au menu. Une valeur illisible
est ignorée et notée dans `journaux/panneau.log` ou `credits.log`.
EmulationStation ne perd pas ces lignes quand il enregistre ses propres
réglages : il ne réécrit que les siennes (`IniFile.cpp`).

Le gestionnaire web de Recalbox **ne les montre pas** : ses pages sont
écrites pour une liste fixe de sections, et son serveur répond 404 à
`/api/configuration/allinone`. Les y faire entrer, c'est contribuer au
gestionnaire lui-même.

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
