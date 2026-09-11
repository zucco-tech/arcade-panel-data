# arcade-panel-data

*[English version](README.en.md)*

Données mesurées à la machine pour piloter un panneau de commande lumineux :
**où chaque jeu range son compteur de crédits en mémoire**, et **quels
boutons chaque jeu utilise vraiment**, avec les couleurs d'origine de la
borne.

Deux jeux de données, un seul but — qu'une borne de salon se comporte comme
une vraie : le bouton pièce clignote quand il n'y a plus de crédit, le start
prend le relais dès qu'il y en a un, et seuls les boutons que le jeu utilise
s'allument, dans les couleurs du panneau d'époque.

---

## Pourquoi ça existe

Le nombre de crédits n'est connu ni de Recalbox, ni de RetroArch, ni d'aucun
frontend. C'est une variable en RAM de la machine émulée, à une adresse
différente pour chaque jeu, et **personne n'avait publié ces adresses**.

Les bases de cheats s'en approchent — un cheat « Infinite Credits » désigne
exactement cet octet — mais elles ne couvrent qu'une minorité de jeux, et les
grands titres n'y sont pas : ni Street Fighter II, ni Metal Slug, ni
Cadillacs & Dinosaurs.

Alors on les a mesurées. Sur une vraie borne, avec de vraies pièces.

## Les données

### `data/credits-arcade.json`

| | |
|---|---|
| jeux avec une adresse mesurée | **1692** |
| pistes importées des bases de cheats | 2646 |
| jeux récalcitrants | 287 |

Chaque fiche note ce qui a été **vérifié**, pas ce qui a été supposé :

```json
"fbneo/1942": {
  "jeu": "1942",
  "systeme": "fbneo",
  "core": "FinalBurn Neo",
  "ram": { "taille": 12544, "commande": "READ_CORE_RAM" },
  "credits": {
    "adresse": 17, "adresse_hex": "0x0011", "octets": 1,
    "miroirs": [],
    "verifie_insertion": true,      // l octet est monte quand une piece est entree
    "verifie_consommation": true,   // et descendu quand START a consomme un credit
    "pieces_observees": 2
  },
  "releve": { "le": "2026-09-11", "methode": "balayage nocturne" }
}
```

**Les fiches sont indexées `systeme/jeu`, jamais par le seul nom du jeu.** Le
même set tourne sous plusieurs cœurs — `fbneo/1942` et `mame/1942` — et
chacun range sa mémoire à sa façon. Indexer sur le nom seul ferait
silencieusement écraser l'une par l'autre. Chaque fiche note aussi son
`core` : si le jeu revient sous un autre, l'adresse est ignorée et
réapprise.

### `data/boutons-arcade.json`

Par jeu : combien de boutons il utilise, la couleur d'origine de chacun sur
la borne, et sa fonction.

```json
"1942": {
  "nom": "1942 (Revision B)",
  "nombre": 2,
  "boutons": {
    "BUTTON1": { "couleur": "Red",   "fonction": "Fire" },
    "BUTTON2": { "couleur": "White", "fonction": "Loop" }
  },
  "mode": "2P alt"
}
```

Les boutons sont nommés **logiquement** — `BUTTON1`, `BUTTON2` — jamais en
LED physiques. La correspondance vers le câblage d'une carte donnée
appartient à ce qui allume les lampes, pas aux données. Un autre panneau, une
autre carte : les données restent justes.

Source : métadonnées MAME publiées par [arcade-database](https://adb.arcadeitalia.net).

---

## Comment les adresses ont été mesurées

RetroArch expose la mémoire de la machine émulée par son interface réseau
(UDP 55355, `network_cmd_enable`). Un compteur de crédits a une signature
qu'aucun autre octet ne partage : il **monte de exactement un** quand une
pièce entre, et **descend** quand START en consomme un.

1. photographier toute la RAM
2. insérer une pièce
3. rephotographier, garder les octets montés de exactement 1
4. recommencer — deux ou trois pièces ne laissent qu'un candidat
5. appuyer sur START : l'octet survivant doit **descendre**

L'étape 5 est celle qui distingue un solde de crédits d'un total de pièces
encaissées, et c'est pourquoi les fiches portent `verifie_consommation`.
Quand la preuve est plus mince que ça, aucune fiche n'est écrite : le jeu
part dans `difficiles` et sera repris plus tard. **Un jeu non mesuré vaut
mieux qu'une adresse fausse.**

Les jeux ayant une piste issue d'une base de cheats sautent les photos : deux
adresses candidates, tranchées dès la première pièce.

### Ce qu'il fallait découvrir

Quatre mesures ont façonné tous les outils de ce dépôt :

- **`READ_CORE_MEMORY` ne fonctionne pas avec FBNeo** — il répond
  `no memory map defined`. Seul `READ_CORE_RAM`, qui lit la RAM système à
  plat depuis zéro, est utilisable.
- **RetroArch ne lit sa socket qu'une fois par image.** Une commande coûte
  une frame — 16,7 ms à 60 Hz — *quelle que soit sa taille*. Lire 1 octet
  coûte autant que lire 16 Ko : autant lire gros.
- **16 Ko est la plus grosse lecture possible.** Une photo complète de 64 Ko
  tient donc en 4 commandes, environ 68 ms.
- **Les adresses de cheats demandent une traduction.** Elles sont données
  dans l'espace du processeur émulé, où la RAM commence haut — `0xFF0000`
  sur une carte 68000 CPS, `0xE000` sur une carte Z80 — alors que
  `READ_CORE_RAM` lit depuis zéro. Masquer les bits bas retrouve le
  décalage, et les jeux 68000 demandent un `XOR 1` de plus, FBNeo rangeant
  la RAM gros-boutiste octets inversés sur un hôte petit-boutiste. Vérifié
  sur `pzloop2` : le cheat annonce `0xFF80B0`, le compteur est en `0x80B1`.

## Ce que valent ces données

Les sets arcade vont par familles — un parent et ses variantes régionales.
Tous exécutent le même code, donc **tous doivent donner la même adresse**.
D'où un audit gratuit, sans relancer un seul jeu :

```
394 familles de clones mesurees
326 s accordent exactement      (82,7 %)
 68 en desaccord
```

Les désaccords s'expliquent presque tous au lieu d'être des erreurs : des
bootlegs (`pacmanbl` contre 24 clones `puckman` cohérents), des révisions
matérielles successives (`cloak` et ses quatre versions `agentx`), ou la même
adresse dans une fenêtre de RAM de taille différente (`blandia` en
`0x100ABE`, `blandiap` en `0x0ABE`).

Une adresse a aussi été vérifiée à la main contre les bases de cheats
publiées, et **c'est la mesure qui a eu raison** : le cheat MAME de `1942`
désigne `0x0018`, qui ne bouge jamais. Le `0x0011` mesuré suit les crédits au
pas près.

## Les outils

| | |
|---|---|
| `tools/nuit-credits.py` | balayage d'une logithèque entière, sans surveillance |
| `tools/importer-cheats.py` | importe les pistes des cheats FBNeo et MAME |
| `tools/importer-boutons.py` | construit la base des boutons |
| `tools/capture-credits.py` | mesure un jeu à la main |
| `tools/verifier-borne.py` | contrôle avant un balayage |
| `tools/clavier_virtuel.py` | clavier virtuel (`uinput`) qui insère les pièces |

Python 3, bibliothèque standard uniquement. Aucune dépendance.

Le balayage pilote une vraie borne : EmulationStation lance chaque jeu
(`START|systeme|/chemin/complet/de/la/rom` en UDP 1337 — le chemin doit être
complet, pas seulement le nom du fichier), un clavier virtuel insère les
pièces, la mémoire est comparée, `QUIT` rend la main, jeu suivant. 1903 jeux
ont pris 9 h 15 sur un Raspberry Pi 5, sans un seul échec technique.

Un clavier plutôt qu'une manette virtuelle, délibérément : RetroArch attribue
les manettes aux ports dans l'ordre où il les découvre, donc une manette
virtuelle serait le joueur 3 et le jeu l'ignorerait. Le clavier, lui, est
câblé sur le joueur 1 par défaut — Entrée pour START, Shift droit pour
SELECT, c'est-à-dire la pièce — sans reconfigurer les manettes réelles.

### Les tests

```bash
cd tools/tests && python3 test_base.py
```

Huit suites, contre un RetroArch simulé — **aucun matériel nécessaire**.
Elles couvrent l'apprentissage de bout en bout, les compteurs en miroir, la
conversion de format, les trois états du panneau, le joueur 2, la collision
d'un même set entre deux cœurs, et la restitution des couleurs. Elles ont
attrapé de vrais défauts : une taille de RAM mesurée mais jamais conservée,
une fiche qui s'attribuait une méthode qu'elle n'avait pas employée, des jeux
condamnés sur une seule tentative malchanceuse.

## `cabinet/` — la seule partie liée à un matériel

`cabinet/credits(permanent).py` est un script permanent d'EmulationStation
qui pilote les LED d'une **carte AllInOne (digipcb.tech)** sous Recalbox. Il
lit les données et fait clignoter en conséquence ; il apprend aussi tout jeu
que le balayage aurait manqué, la première fois qu'on y joue.

Il n'écrit que dans `brightness`, et dans `multi_intensity` seulement le
temps d'un clignotement — en relisant d'abord la couleur posée par la carte
pour la remettre ensuite, et sans jamais écraser une couleur que la carte
aurait repeinte entre-temps. Les fichiers de Recalbox ne sont ni modifiés ni
remplacés.

Deux particularités de la carte prototype pour laquelle il a été écrit, toutes
deux réglables en tête de fichier et **absentes des données** :

- les LED `start` et `select` du driver sont croisées par rapport au panneau
- les WS2812B attendent l'ordre **vert, rouge, bleu** alors que le driver les
  déclare rouge, vert, bleu — écrire du rouge franc allume du vert

## Limites

- Arcade uniquement. Sur console, le nombre de boutons dépend de la manette,
  pas du jeu.
- Un cœur qui n'expose pas sa RAM ne peut pas être mesuré — 97 jeux ici.
- Certains compteurs sont en BCD ou sur deux octets et échappent à la méthode.
- Les métadonnées de boutons viennent de MAME : une poignée de jeux n'en ont
  pas.
