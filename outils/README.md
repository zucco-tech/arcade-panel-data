# Les outils

Tout ce qui a servi à fabriquer les données. Python 3, bibliothèque standard
uniquement, aucune dépendance.

| | |
|---|---|
| `nuit-credits.py` | le releveur : enchaîne une logithèque entière sans surveillance |
| `importer-cheats.py` | tire des pistes des bases de cheats FBNeo et MAME |
| `importer-boutons.py` | construit la base des boutons |
| `capture-credits.py` | mesure un seul jeu, à la main |
| `verifier-borne.py` | contrôle les trois inconnues avant un balayage |
| `releve-poli.py` | mesure les crédits sur la borne elle-même, jeu par jeu, sans déranger une partie — pas déployé, le PC va plus vite |
| `mame-rapport.lua` | lit le vrai compteur de l'intérieur de MAME (avec `exporter-pour-borne.py --fiches-mame`) — pas déployé, Recalbox 10 ne laisse pas charger le script |
| `clavier_virtuel.py` | le clavier `uinput` qui insère les pièces, pour les deux joueurs |
| `clavier_xtest.py` | variante XTEST, qui n'existe que dans un serveur X donné |
| `balayage-continu.py` | enchaîne les systèmes, jour et nuit, sans surveillance |
| `complement-joueur2.py` | ajoute l'adresse du joueur 2 aux fiches déjà mesurées |
| `capture_fenetre.py` | photographie l'écran du jeu quand il ne réagit pas |
| `fenetre_x.py` | place une fenêtre sur un moniteur choisi |
| `suivre-boutons.sh` | tient la base des boutons à jour pendant le relevé |
| `demarrer.sh` | lance tout en une commande |

## Comment le releveur travaille

Il lance un jeu, attend que sa RAM s'anime — signe qu'il tourne vraiment et
qu'il acceptera une pièce —, insère des pièces par le clavier virtuel,
compare la mémoire avant et après, puis passe au suivant.

Deux modes : par **EmulationStation** (`START|systeme|chemin` en UDP 1337) sur
une borne Recalbox, ou **directement** (`--direct`) sur une machine dédiée qui
n'a pas de frontend.

## Les garde-fous

Ils viennent tous d'un vrai problème rencontré :

- refus de démarrer si une partie est déjà en cours
- jamais d'appui clavier hors d'un jeu, sinon `Entrée` validerait dans le menu
- clavier virtuel détruit à la sortie, y compris sur Ctrl-C
- base sauvée après **chaque** jeu — une coupure ne perd rien
- rien n'est écrit quand la preuve est trop mince : le jeu est réessayé
- arrêt automatique après 8 échecs d'affilée
- jamais de `GET_STATUS` : cette commande fait segfauter RetroArch avec FBNeo
  (mesuré : deux morts sur deux, quand `READ_CORE_RAM` répond douze fois sur
  douze). Pour savoir si un jeu tourne, on lit sa RAM.
- un refus de ROM est reconnu en quelques secondes au lieu d'attendre six
  minutes : FBNeo dit lui-même « marked as not working » ou réclame des
  fichiers manquants
- un jeu figé est d'abord sorti de pause avant d'être déclaré inanimé — un
  RetroArch en pause fige sa RAM et ferait condamner un jeu parfaitement sain
- tout le groupe de processus est tué à la fermeture : viser le fils direct
  laissait RetroArch orphelin, et un seul orphelin fait échouer tous les
  lancements suivants

## `tests/`

Huit suites contre un RetroArch simulé — **aucun matériel nécessaire**.

```bash
cd tests && python3 test_base.py
```

Elles ont attrapé de vrais défauts : une taille de RAM mesurée mais jamais
conservée, une fiche qui s'attribuait une méthode qu'elle n'avait pas
employée, des jeux condamnés sur une seule tentative malchanceuse.
