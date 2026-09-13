# Les outils

Tout ce qui fabrique les données, sur le PC de relevé. Python 3,
bibliothèque standard uniquement, aucune dépendance.

## La chaîne, du balayage à la borne

```
surveiller.sh                 le point d'entrée : enchaîne les systèmes, jour et nuit
  └─ balayer.sh               un système, en quatre relevés parallèles
       ├─ releve-direct.py    charge le cœur libretro tout seul, sans RetroArch ni écran
       ├─ releve-mame.py      pour MAME : mesure DANS l'émulateur, par mame-credits.lua
       └─ fusionner-parts.py  replie les quatre parts dans la base
  └─ nuit-credits.py          reprise par RetroArch des rares roms que le cœur nu refuse
  └─ deployer-vers-borne.sh   toutes les 30 min : exporter-pour-borne.py, puis la borne
```

| | |
|---|---|
| `surveiller.sh` | **le point d'entrée** : enchaîne les systèmes, reprend les écartés en fin de cycle, déploie sur la borne toutes les 30 min |
| `balayer.sh` | balaye un système avec plusieurs relevés en parallèle, puis replie |
| `releve-direct.py` | le relevé lui-même : charge le cœur libretro directement, attend que la RAM vive, paie, START, cherche le compteur, vérifie les miroirs |
| `releve-mame.py`, `mame-credits.lua` | même chose pour MAME, dont la mémoire n'est pas lisible par libretro : le Lua cherche dans l'émulateur |
| `fusionner-parts.py` | replie les parts d'un balayage parallèle dans la base principale |
| `nuit-credits.py` | le relevé par RetroArch, en plein écran : réservé aux roms que le cœur nu refuse (`--reessayer`) |
| `clavier_virtuel.py`, `clavier_xtest.py` | les claviers virtuels de `nuit-credits.py` : `uinput`, ou XTEST sur un serveur X précis |
| `fenetre_x.py`, `capture_fenetre.py` | pour `nuit-credits.py` : plein écran sur un moniteur choisi, et photo du jeu quand il ne réagit pas |
| `exporter-pour-borne.py` | découpe la base en un fichier par système, la forme que lit la borne |
| `deployer-vers-borne.sh` | met les fichiers en place sur la borne, par renommage, sans rien redémarrer ; tient à jour la copie `borne/share/` du dépôt |
| `importer-cheats.py` | tire des pistes des bases de cheats FBNeo et MAME |
| `importer-boutons.py`, `suivre-boutons.sh` | construit la base des boutons depuis arcade-database, et la tient à jour |
| `relever-entrees.py` | ce que chaque jeu déclare comme entrées, demandé au cœur lui-même |
| `complement-joueur2.py` | ajoute l'adresse du compteur du joueur 2 aux fiches déjà mesurées |
| `analyser-difficiles.py` | explique pourquoi des jeux ont résisté, et lesquels valent d'être repris |
| `releve-poli.py` | mesure sur la borne elle-même, jeu par jeu, sans déranger une partie — pas déployé, le PC va plus vite |
| `mame-rapport.lua` | lit le vrai compteur de l'intérieur de MAME sur la borne — pas déployé, Recalbox 10 ne laisse pas charger le script |

## Comment le relevé travaille

Il charge le cœur, attend que la RAM s'anime — signe que le jeu tourne
vraiment et acceptera une pièce —, insère des pièces, compare la mémoire
avant et après, fait consommer un crédit par START pour trancher, vérifie
les miroirs avec une pièce de plus, puis passe au suivant. Sans preuve
suffisante, rien n'est écrit : le jeu est réessayé au tour suivant.

## Les garde-fous

Ils viennent tous d'un vrai problème rencontré :

- l'attente que la RAM vive, plutôt qu'un délai fixe : un jeu lent n'est
  plus condamné, un jeu rapide ne fait plus attendre
- un octet ne compte que s'il est monté à **chaque** pièce, en binaire ou en
  BCD (`0x09` → `0x10`)
- START doit faire redescendre le compteur, jusqu'à trois appuis : un total
  de pièces encaissées monte sans jamais redescendre
- les miroirs sont vérifiés avec une pièce de plus, pas supposés
- DIP forcés : pas de free play, pas de service, une pièce un crédit
- jamais d'accéléré ni de pièce trop brève : certaines cartes refusent
  (`COIN ERROR` sur Batrider)
- pas de `GET_STATUS` par RetroArch : cette commande fait segfauter FBNeo
- tout le groupe de processus est tué à la fermeture : un orphelin fait
  échouer tous les lancements suivants

## `tests/`

Contre un RetroArch simulé, **aucun matériel nécessaire**. Les programmes
de la borne sont pris dans `borne/share/userscripts/`.

```bash
cd tests && python3 test_partie.py       # une partie : pièce, START, plus rien ne clignote
python3 test_panneau.py                  # les règles d'éclairage du menu
```

`test_partie`, `test_j2`, `test_base`, `test_piste`, `test_complet`,
`test_collision`, `test_arcade`, `test_borne`, `test_couleur` visent le démon
des crédits ; `test_panneau` le panneau du menu ; `test_nuit` le relevé par
RetroArch.
