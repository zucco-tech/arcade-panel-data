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
  └─ ACHARNE=1 balayer.sh     la reprise acharnée : les écartés où le jeu tournait, avec plus de moyens
  └─ nuit-credits.py          reprise par RetroArch des rares roms que le cœur nu refuse
  └─ deployer-vers-borne.sh   toutes les 30 min : exporter-pour-borne.py, puis la borne
```

| | |
|---|---|
| `surveiller.sh` | **le point d'entrée** : enchaîne les systèmes, reprend les écartés en fin de cycle, déploie sur la borne toutes les 30 min |
| `balayer.sh` | balaye un système avec plusieurs relevés en parallèle, puis replie ; `ACHARNE=1` lance la reprise acharnée des écartés |
| `releve-direct.py` | le relevé lui-même : charge le cœur libretro directement, attend que la RAM vive, paie, START, cherche le compteur, vérifie les miroirs |
| `releve-mame.py`, `mame-credits.lua` | même chose pour MAME, dont la mémoire n'est pas lisible par libretro : le Lua cherche dans l'émulateur |
| `fusionner-parts.py` | replie les parts d'un balayage parallèle dans la base principale |
| `nuit-credits.py` | le relevé par RetroArch, en plein écran : réservé aux roms que le cœur nu refuse (`--reessayer`) |
| `clavier_virtuel.py`, `clavier_xtest.py` | les claviers virtuels de `nuit-credits.py` : `uinput`, ou XTEST sur un serveur X précis |
| `fenetre_x.py`, `capture_fenetre.py` | pour `nuit-credits.py` : plein écran sur un moniteur choisi, et photo du jeu quand il ne réagit pas |
| `exporter-pour-borne.py` | découpe la base en un fichier par système, la forme que lit la borne |
| `associer-boutons.sh` / `.py` | mesure sur la borne quel bouton porte quelle LED (une LED s'allume, on appuie dessus, six fois) et rapporte `cablage.json` ; à refaire si l'on recâble, une fois pour le poste 2 |
| `deployer-vers-borne.sh` | met les fichiers en place sur la borne, par renommage, sans rien redémarrer ; tient à jour la copie `borne/share/` du dépôt |
| `deployer-programmes.sh` | met les **programmes** du dépôt en place sur la borne (userscripts, `panneau-allinone/`, `custom.sh`) et relance ce qui doit l'être — le démon des crédits seulement hors partie |
| `importer-cheats.py` | tire des pistes des bases de cheats FBNeo et MAME |
| `importer-boutons.py`, `suivre-boutons.sh` | construit la base des boutons depuis arcade-database, et la tient à jour |
| `relever-entrees.py` | ce que chaque jeu déclare comme entrées, demandé au cœur lui-même |
| `complement-joueur2.py` | ajoute l'adresse du compteur du joueur 2 aux fiches déjà mesurées |
| `analyser-difficiles.py` | explique pourquoi des jeux ont résisté, et lesquels valent d'être repris |
| `releve-poli.py` | mesure sur la borne elle-même, jeu par jeu, sans déranger une partie — pas déployé, le PC va plus vite |
| `mame-rapport.lua` | lit le vrai compteur de l'intérieur de MAME sur la borne — pas déployé, Recalbox 10 ne laisse pas charger le script |

## La reprise acharnée

La mesure ordinaire est déterministe : refaire un écarté à l'identique ne
change rien. La reprise acharnée (`--acharne` des deux releveurs) ne change
pas les règles, elle donne plus de moyens, et seulement aux écartés où le
jeu tournait vraiment (délai dépassé, jeu inanimé, aucun candidat,
candidats non confirmés — jamais une rom refusée par le cœur) :

- cinq fois plus de temps par jeu, et une attente de vie trois fois plus
  longue, pendant laquelle on appuie sur START et le bouton 1 : des cartes
  attendent un appui pour sortir d'un écran d'erreur ou de calibrage ;
- plus de pièces, encaissées plus lentement, par les deux monnayeurs ;
  rien ne monte : on attend l'attract, puis on cherche sur deux octets ;
- d'autres façons de démarrer : START tenu une demi-seconde, START du
  joueur 2, bouton 1, double appui sur START ;
- sous MAME : d'autres zones de mémoire quand le pilote n'en déclare
  aucune « ram » (les zones servies par un délégué ou une banque), un crédit
  de service quand il n'y a pas de monnayeur nommé, et la raison exacte de
  MAME quand il refuse une machine ;
- si aucun START n'a jamais rien fait descendre mais qu'un octet, seul de
  sa classe, est monté à chaque pièce, la fiche est écrite **en le disant**
  (`verifie_consommation: false`, avec une note) : la borne clignotera à
  la pièce, et personne ne prendra une supposition pour une preuve ;
- une image de l'écran du jeu est gardée pour chaque échec, dans
  `journaux/images/<système>/<jeu>.png` : ce que le jeu affichait dit
  souvent pourquoi.

`surveiller.sh` l'enchaîne après les systèmes, à chaque tour.

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

## Vérifier

Quatre niveaux, du plus rapide au plus lourd. Chacun ne prouve qu'une chose,
et une seule commande les enchaîne :

```
sh outils/verifier-tout.sh                 # niveaux 1 et 2
sh outils/verifier-tout.sh --echantillon   # les quatre
```

| niveau | commande | ce que ça prouve | durée |
|---|---|---|---|
| 1. les bancs d'essai | `sh outils/tests/tout.sh` | la **logique** des programmes, contre un RetroArch simulé et un faux panneau — aucun matériel | ~3 min |
| 2. la santé de la borne | `sh outils/sante-borne.sh` | les trois programmes tournent, discrets (processeur, mémoire), sans erreur, et font leur travail ; chaque ligne `ALERTE` est un vrai souci | 10 s |
| 3. l'échantillon sur le PC | `python3 outils/verifier-echantillon.py --remesurer …` | vingt fiches tirées au sort se **remesurent à l'identique** | ~10 min |
| 4. l'échantillon sur la borne | `sh outils/verifier-sur-borne.sh` | les **mêmes** fiches rejouées par la borne elle-même : pièce +1, START −1, sur le vrai cœur et le fichier déployé | ~5 min, prend l'écran |

Le niveau 2 tourne seul chaque matin à 8 h (rapport dans
`journaux/sante.log`). Le niveau 4 arrête EmulationStation le temps du
contrôle : on ne le lance pas pendant qu'on joue. MAME n'y est pas
contrôlable — RetroArch ne livre pas sa mémoire — et l'est au niveau 3.
La preuve continue, elle, se fait toute seule : à chaque partie, le démon
note `credits 0 -> 1` dans `journaux/credits.log`.

## `tests/`

Contre un RetroArch simulé (`faux_retroarch.py`, à côté), **aucun matériel
nécessaire**, dans un dossier temporaire neuf à chaque banc. Les programmes
de la borne sont pris dans `borne/share/userscripts/`.

```
sh outils/tests/tout.sh                  # tous, un verdict
python3 outils/tests/test_partie.py      # un seul
```

| banc | ce qu'il vérifie |
|---|---|
| `test_partie` | une partie : pièce, START, plus rien ne clignote, le bouton 1 guide, la fin de partie |
| `test_j2` | le joueur 2 : invité par START ou par la pièce, accepté ou refusé, et retenu |
| `test_arcade` | les trois états d'une borne : pièce, start, partie en cours |
| `test_complet` | le démon apprend un jeu inconnu, puis le fait clignoter |
| `test_base` | miroirs, format d'`appris.json`, cohabitation avec les fichiers du PC |
| `test_piste` | une piste du pack de cheats se confirme dès la première pièce |
| `test_collision` | le même set sous deux systèmes ne s'écrase pas |
| `test_couleur` | jamais une couleur posée par la carte n'est écrasée |
| `test_panneau` | les règles d'éclairage du menu : manettes, START/SELECT, veille, arcade ≠ console |
| `test_nuit` | une nuit de relevé contre une fausse borne : ES, RetroArch, clavier |

Les commits ne partent que si `tout.sh` est vert.
