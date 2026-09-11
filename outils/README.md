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
| `clavier_virtuel.py` | le clavier `uinput` qui insère les pièces |

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

## `tests/`

Huit suites contre un RetroArch simulé — **aucun matériel nécessaire**.

```bash
cd tests && python3 test_base.py
```

Elles ont attrapé de vrais défauts : une taille de RAM mesurée mais jamais
conservée, une fiche qui s'attribuait une méthode qu'elle n'avait pas
employée, des jeux condamnés sur une seule tentative malchanceuse.
