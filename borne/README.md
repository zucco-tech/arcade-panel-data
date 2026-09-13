# Les scripts de la borne

Ce dossier est lu par Recalbox au démarrage. Un script dont le nom contient
`(permanent)` est lancé une fois et laissé tourner ; un nom entre crochets
`[evenement]` est appelé à chaque événement du frontend.

| script | rôle |
|---|---|
| `credits(permanent).py` | pendant une partie : lit le compteur de crédits en mémoire, fait clignoter PIÈCE ou START, éclaire les boutons utiles, éteint le poste 2 s'il ne sert pas |
| `panneau(permanent).py` | dans le menu : éclaire les boutons du jeu **survolé**, avec ses couleurs d'origine, avant même de le lancer |
| `marquee(permanent).py` | affiche le nom du jeu sur le marquee |
| `allinone[…].sh.off` | scripts d'origine Recalbox, **désactivés** : ils lançaient un bash à chaque mouvement du menu et écrivaient les mêmes LED que le panneau. Leur table de couleurs par système est reprise par `panneau(permanent).py`, qui lit `/recalbox/scripts/recalbox_allinone_rgb.sh` au démarrage |
| `gardefou[…].ash` | garde-fou : au demarrage du frontend, au lancement et a la fin de chaque partie, relance celui des trois programmes permanents qui serait mort. Journal dans `panneau-arcade/gardefou.log` |
| `custom.sh` (dans `share/system/`) | crochet de demarrage : neutralise les scripts allinone que Recalbox recree, et allume le panneau en veilleuse avant EmulationStation |

Deux niveaux seulement — le proprietaire eteint la borne le soir, le
jour/nuit n avait pas lieu d etre : `PRESENT` (255) des que quelqu un est
devant, `CLIP` (128) quand la borne se raconte toute seule.

Dans le menu le panneau **veille** : un geste sur une manette (bouton,
stick) ou une navigation le rallume à fond, et il se tamise à `INTENSITE_MENU`
(80 sur 255) après `VEILLE_APRES` secondes (30) sans rien. Les clips vidéo qui
défilent seuls ne le réveillent pas. Les manettes sont lues sans exclusivité
(`/dev/input/event*` de la carte) : EmulationStation les voit toujours.
Autre réglage : `PORTABLES` (consoles portables : le poste 2 y reste noir). Sur console, le poste 2 ne s'allume que
si EmulationStation annonce plusieurs joueurs ; dans le doute il reste noir.

## Installer sur une autre borne

Il faut : une borne sous Recalbox avec une carte **AllInOne** (le module
`allinone` charge, `/sys/class/leds/aio_*` present), et ce depot copie sur
la borne — sur une cle USB, ou dans la share par le reseau. Puis, en root
sur la borne :

```
sh borne/installer.sh
```

Une commande. Il copie trois programmes dans `userscripts/`, cree
`system/panneau-arcade/` avec les donnees, pose le crochet de demarrage,
met hors service les scripts allinone d origine et relance. Tout reste
dans `/recalbox/share` ; le systeme Recalbox n est pas touche. Pour revenir
en arriere : `sh borne/desinstaller.sh`.

Les donnees pretes a l emploi sont dans `donnees/` : `pour-borne.json`
(les credits, indexes par systeme) et `boutons-arcade.json`. Elles viennent
du PC de releve ; on peut les remplacer par une version plus recente sans
rien reinstaller, le demon des credits relit sa base a son redemarrage et
le panneau recharge les boutons tout seul.

## Qui pilote les LED, et quand

Deux scripts écrivent dans les LED, jamais en même temps :

```
menu, jeu survole      panneau(permanent).py
partie en cours        credits(permanent).py   (panneau se tait)
retour au menu         panneau reprend, apres avoir rendu les couleurs
```

Les deux suivent la même règle : on n'écrit que dans `brightness`, et dans
`multi_intensity` seulement pour poser la couleur d'origine d'un bouton — la
couleur posée par la carte est mémorisée avant, et rendue en partant. Rien
ne reste modifié derrière eux.

## Les données

Tout ce qui appartient au panneau est dans **un seul dossier** :

```
/recalbox/share/system/panneau-arcade/
    credits-arcade.json     ou lire les credits, par jeu
    boutons-arcade.json     combien de boutons, combien de joueurs, couleurs
    credits.log             ce que le demon des credits a decide, jeu par jeu
    panneau.log             ce que le panneau a eclaire au survol
    credits-erreurs.log     sortie brute du demon (vide si tout va bien)
    sauvegardes/            copies datees des scripts avant modification
```

Elles sont fabriquées sur le PC de relevé et poussées ici toutes les
30 minutes, hors partie. Le démon des crédits ne relit sa base qu'au
démarrage : le déploiement le redémarre, uniquement quand personne ne joue.

## Les journaux

Voir le dossier ci-dessus : `credits.log`, `panneau.log`, `credits-erreurs.log`.

## MAME : les credits lus de l interieur

MAME ne sert pas `READ_CORE_RAM`. Pour lui, `mame-rapport.lua` (dans
`panneau-arcade/outils/`) tourne **dans** l emulateur, lance par
`/recalbox/share/bios/mame/ini/mame.ini` (`autoboot_script`, que le coeur
lit grace a l option `mame_read_config`). Il cherche la machine dans
`panneau-arcade/mame-fiches.txt` — une ligne par jeu, produite par le PC de
releve — et ecrit le nombre de credits dans `/tmp/mame-credits` cinq fois
par seconde. `credits(permanent).py` lit ce fichier au lieu de la memoire
quand le coeur est MAME. Sans fiche, le Lua ecrit « inconnu » et le demon
garde son comportement par defaut.

## Au demarrage

`custom.sh` (dans `share/system/`, crochet officiel appele par `S99custom`)
fait deux choses a chaque allumage :

1. il remet hors service `allinone[systembrowsing].sh` et
   `allinone[startgameclip].sh`, que `/etc/init.d/S13allinone` **recree a
   chaque demarrage** — ils repeignent les LED a chaque mouvement de menu et
   se battraient avec `panneau(permanent).py` ;
2. il allume le panneau en veilleuse tout de suite, sans attendre
   EmulationStation, qui met plusieurs minutes a charger ses listes.

## Les sauvegardes

Chaque modification d'un script d'origine est précédée d'une copie datée
dans `/recalbox/share/system/panneau-arcade/sauvegardes/`. Pour revenir en arrière : copier
la sauvegarde à la place du script, et redémarrer la borne.

Le dépôt de référence : https://github.com/zucco-tech/arcade-panel-data — le
dossier `borne/` y contient exactement ces scripts.
