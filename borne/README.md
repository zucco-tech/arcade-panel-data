# La borne

**La seule partie de ce dépôt liée à un matériel particulier.** Tout le reste
vaut pour n'importe quelle installation.

`credits(permanent).py` est un script permanent d'EmulationStation qui pilote
les LED d'une carte **AllInOne (digipcb.tech)** sous Recalbox.

## Ce qu'il fait

| | bouton pièce | start J1 | start J2 |
|---|---|---|---|
| plus de crédit | **clignote rouge** | — | — |
| du crédit, partie pas lancée | — | **clignote** | — |
| partie en cours | — | — | — |
| crédit disponible, jeu à deux | — | — | **clignote** |

Il lit `donnees/credits-arcade.json`, et apprend tout seul les jeux qui n'y
sont pas, la première fois qu'on y joue.

## Ce qu'il ne fait pas

Il ne modifie **aucun fichier de Recalbox ni de digi**. Côté LED il n'écrit
que dans `brightness`, et dans `multi_intensity` seulement le temps d'un
clignotement — en relisant d'abord la couleur posée par la carte pour la
remettre après, et sans jamais écraser une couleur repeinte entre-temps.

## Deux particularités de la carte prototype

Réglables en tête de fichier, et **absentes des données** :

- les LED `start` et `select` du driver sont croisées par rapport au panneau
- les WS2812B attendent l'ordre **vert, rouge, bleu** alors que le driver les
  déclare rouge, vert, bleu — écrire du rouge franc allume du vert
