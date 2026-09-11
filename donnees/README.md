# Les données

Le cœur du dépôt. Deux fichiers, deux natures différentes.

## `credits-arcade.json` — mesuré

L'adresse mémoire où chaque jeu range son compteur de crédits. **Ces adresses
n'existent nulle part ailleurs** : elles ont été relevées une par une sur une
vraie borne, en insérant de vraies pièces et en regardant quel octet montait.

```
1692 jeux mesures
2646 pistes issues des bases de cheats FBNeo et MAME
 287 jeux ecartes faute de preuve suffisante
```

Chaque fiche dit **ce qui a été vérifié** : `verifie_insertion` (l'octet est
monté quand une pièce est entrée) et `verifie_consommation` (il est descendu
quand START en a consommé une). Sans ces deux preuves, rien n'est écrit.

Les fiches sont indexées `systeme/jeu` — le même set sous un autre cœur n'a
pas la même adresse.

## `boutons-arcade.json` — compilé

Combien de boutons chaque jeu utilise, et pour une partie d'entre eux la
couleur d'origine de chacun sur le panneau et sa fonction.

```
1623 jeux avec le nombre de boutons
 266 avec couleur et fonction detaillees
  69 sans donnees
```

Rien de mesuré ici : ce sont des métadonnées MAME publiées par
[arcade-database](https://adb.arcadeitalia.net), rassemblées pour cet usage.

Les boutons sont nommés **logiquement** (`BUTTON1`, `BUTTON2`), jamais en LED
physiques : la correspondance vers un câblage donné appartient au programme
qui allume les lampes, pas aux données.
