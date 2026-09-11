# Les données d'arcade : comment elles sont faites, comment on les lit

Ce document explique les deux fichiers produits par ce projet, ce qu'ils
contiennent, et comment Recalbox s'en sert pour éclairer les boutons d'une
borne AllInOne. Il est écrit pour quelqu'un qui découvre le projet.

---

## Le problème que ça résout

Sur une vraie borne d'arcade, les boutons s'allument pour dire quoi faire :

* pas de crédit → le bouton **PIÈCE** clignote, « mets une pièce »
* du crédit → le bouton **START** clignote, « appuie pour jouer »
* partie lancée, jeu à deux → le **START du joueur 2** clignote, « viens jouer »

Pour reproduire ça sous Recalbox, il faut savoir deux choses que ni Recalbox
ni RetroArch ne connaissent :

1. **combien de crédits sont insérés**, à chaque instant
2. **combien de boutons le jeu utilise**, et s'il se joue à deux

Le nombre de crédits n'existe nulle part : c'est un octet dans la mémoire du
jeu émulé, à une adresse différente pour chaque jeu. Ce projet mesure ces
adresses, jeu par jeu, et les range dans un fichier.

---

## Les deux fichiers

```
/recalbox/share/system/credits-arcade.json     ou sont les credits en memoire
/recalbox/share/system/boutons-arcade.json     combien de boutons, combien de joueurs
```

Sur la machine de mesure, ils vivent dans `/mnt/recalbox/donnees/`. On les
copie tels quels sur la borne.

---

## `credits-arcade.json` — où lire les crédits

Une fiche par jeu, rangée sous **`coeur/jeu`** :

```json
"finalburn-neo/1942": {
  "jeu": "1942",
  "systeme": "fbneo",
  "core": "FinalBurn Neo",
  "ram": { "taille": 12544, "commande": "READ_CORE_RAM" },
  "credits": {
    "adresse": 25,
    "adresse_hex": "0x0019",
    "octets": 1,
    "miroirs": ["0x16E4"],
    "entree_piece": "select",
    "adresse_j2": null,
    "adresse_j2_hex": null,
    "compteur_commun": false,
    "verifie_insertion": true,
    "verifie_consommation": true,
    "pieces_observees": 2
  }
}
```

### Pourquoi la clé contient le cœur

C'est le cœur d'émulation qui décide de la disposition mémoire, pas le
système ni la machine. Le même jeu sous FinalBurn Neo et sous MAME n'a pas
la même adresse de crédits. Les deux mesures doivent donc cohabiter :

```
finalburn-neo/1942    l'adresse pour qui joue avec FBNeo
mame/1942             l'adresse pour qui joue avec MAME
```

En revanche l'adresse ne dépend **pas** du processeur : vérifié, `pzloop2`
compte ses crédits en `0x0450` aussi bien sur un Raspberry Pi 5 que sur un
PC x86. Une mesure faite sur une machine vaut sur toutes les autres, tant
que le cœur est le même.

### Les champs, un par un

| champ | ce qu'il dit |
|---|---|
| `adresse` | l'octet à lire, en décimal |
| `adresse_hex` | le même, en hexadécimal, pour la lecture humaine |
| `octets` | combien d'octets lire (toujours 1 à ce jour) |
| `miroirs` | autres adresses qui reflètent la même valeur |
| `entree_piece` | quel bouton encaisse la pièce (voir plus bas) |
| `adresse_j2` | le compteur du joueur 2, quand il en a un à lui |
| `compteur_commun` | vrai si les deux monnayeurs alimentent le même octet |
| `verifie_insertion` | l'octet est bien monté quand on a mis une pièce |
| `verifie_consommation` | il est bien redescendu à l'appui sur START |
| `pieces_observees` | combien de pièces ont servi à le prouver |

**Rien n'est écrit sans preuve.** Un jeu dont on n'a pas vu le compteur
monter ne reçoit pas de fiche : il part dans `difficiles`, avec la raison,
et sera repris plus tard. Mieux vaut un jeu en attente qu'une adresse fausse
qui ferait clignoter n'importe quoi.

---

## `boutons-arcade.json` — combien de boutons allumer

```json
"1942": {
  "nom": "1942 (Japan set 1)",
  "nombre": 2,
  "joueurs": 2,
  "mode": "2P alt",
  "commandes": "joystick (8-way)",
  "boutons": {
    "BUTTON1": { "couleur": "Blue", "fonction": "Shoot" },
    "BUTTON2": { "couleur": "Blue", "fonction": "Loop" }
  }
}
```

Ces données ne sont pas mesurées : elles viennent des métadonnées MAME
publiées par arcade-database, récupérées par `importer-boutons.py`.

Les boutons sont nommés **logiquement** — `BUTTON1`, `BUTTON2` — jamais en
LED physiques. La correspondance vers une carte donnée appartient au
programme qui les allume, pas aux données : si tu changes de carte ou de
câblage, la base reste bonne.

Couverture : le **nombre de boutons** et le **nombre de joueurs** sont connus
pour 100 % des jeux. La couleur d'origine n'est connue que pour environ un
jeu sur huit — arcade-database ne la publie pas partout.

---

## Comment la borne s'en sert

Le programme qui allume les boutons est :

```
/recalbox/share/userscripts/credits(permanent).py
```

Le `(permanent)` fait que Recalbox le lance une seule fois au démarrage et
le laisse tourner. Il ne remplace ni ne modifie `marquee(permanent).py` :
les deux cohabitent.

### Ce qu'il fait, en boucle

1. il demande à RetroArch quel jeu tourne
2. il cherche sa fiche dans `credits-arcade.json`
3. il lit l'octet des crédits, trois fois par seconde, par
   `READ_CORE_RAM` sur le port UDP 55355
4. il allume ou éteint les LED selon la règle ci-dessous

### La règle d'éclairage

```
hors jeu, ou partie en cours      rien ne clignote
credits == 0                      PIECE clignote     « mets une piece »
credits > 0                       START clignote     « appuie sur start »

jeu multi, credit disponible,
joueur 2 pas encore entre         START J2 clignote  « viens jouer »
```

Et pour le second poste, trois cas que la fiche distingue :

```
adresse_j2 renseignee     deux compteurs separes : le START du joueur 2 ne
                          clignote que si LUI a paye

compteur_commun = true    une seule cagnotte alimentee par les deux
                          monnayeurs. On ne peut pas savoir qui a paye :
                          BOUTON DU JOUEUR 2 ETEINT

aucun des deux            un seul monnayeur : panneau 2 eteint
```

Le nombre de LED à allumer vient de `boutons-arcade.json` :

```
joueurs >= 2   memes boutons allumes sur les deux panneaux
joueurs == 1   panneau 1 seulement
```

### Côté LED, une seule chose est touchée

Le programme n'écrit que dans `brightness`. Les couleurs sont posées par
`recalbox_allinone_rgb.sh` à travers `multi_intensity`, auquel on ne touche
pas. Rien n'entre donc en conflit avec le code de la carte, et remettre
`brightness` à 255 rend la LED exactement telle que la carte l'avait
laissée.

---

## Le champ `entree_piece`, et pourquoi il existe

La plupart des jeux encaissent leur pièce sur le bouton **SELECT**. Mais pas
tous : des flippers, des jeux de tir, certains japonais utilisent un autre
bouton. Mesuré sur cette machine : `aof3bh` encaisse sur le bouton **a**.

Quand l'outil ne trouve rien sur SELECT, il essaie les six autres entrées du
panneau avant de déclarer forfait, et note laquelle a fonctionné. Le
programme des LED peut ainsi savoir quel bouton faire clignoter pour dire
« mets une pièce » — sur ces jeux-là, ce n'est pas le monnayeur habituel.

---

## Ce qui reste en attente

Les jeux non mesurés sont dans `difficiles`, avec leur cause :

| raison | récupérable ? |
|---|---|
| `aucun candidat` | oui, à reprendre avec plus de pièces |
| `candidats non confirmes` | oui, le START n'a pas tranché |
| `jeu inanime` | oui, souvent une question de démarrage |
| `ne demarre pas` | oui, parfois passager |
| `jeu non supporte par ce coeur` | **non**, FBNeo le marque lui-même injouable |
| `romset inconnu de ce coeur` | **non**, FBNeo ne connaît pas ce set |
| `romset incomplet pour cette version` | **non** avec ce cœur |

`analyser-difficiles.py` les trie par cause et donne la commande de reprise.

---

## Déployer sur la borne

```
scp /mnt/recalbox/donnees/credits-arcade.json  root@borne:/recalbox/share/system/
scp /mnt/recalbox/donnees/boutons-arcade.json  root@borne:/recalbox/share/system/
```

Les fichiers sont du JSON simple, sans dépendance. Le programme des LED les
relit au démarrage ; il suffit de redémarrer la borne, ou le script, pour
que les nouveaux jeux soient pris en compte.

Le dépôt : https://github.com/zucco-tech/arcade-panel-data
