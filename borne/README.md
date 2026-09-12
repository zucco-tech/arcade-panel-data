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
| `gardefou[…].ash` | garde-fou du frontend |

Le jour, le panneau reste a pleine puissance : la piece est claire, il ne
gene personne. La nuit, il se tamise au repos. Le lever et le coucher du
soleil sont **calcules pour le jour meme** a partir de l'horloge de la borne
et des coordonnees en tete de `panneau(permanent).py` (`LATITUDE`,
`LONGITUDE`) — juste en decembre comme en juin, sans horaire fige a
entretenir.

Dans le menu le panneau **veille** : un geste sur une manette (bouton,
stick) ou une navigation le rallume à fond, et il se tamise à `INTENSITE_MENU`
(80 sur 255) après `VEILLE_APRES` secondes (30) sans rien. Les clips vidéo qui
défilent seuls ne le réveillent pas. Les manettes sont lues sans exclusivité
(`/dev/input/event*` de la carte) : EmulationStation les voit toujours.
Autre réglage : `PORTABLES` (consoles portables : le poste 2 y reste noir). Sur console, le poste 2 ne s'allume que
si EmulationStation annonce plusieurs joueurs ; dans le doute il reste noir.

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

## Les sauvegardes

Chaque modification d'un script d'origine est précédée d'une copie datée
dans `/recalbox/share/system/panneau-arcade/sauvegardes/`. Pour revenir en arrière : copier
la sauvegarde à la place du script, et redémarrer la borne.

Le dépôt de référence : https://github.com/zucco-tech/arcade-panel-data — le
dossier `borne/` y contient exactement ces scripts.
