# Vos demandes — cahier de référence

Relevé le 17/09/2026 à partir de **tous vos messages depuis le 11/09**
(7 conversations, 360 messages). Chaque demande est notée avec vos mots
quand c'est utile, et avec son état **vérifié**, pas supposé.

Légende : ✅ validé par vous à la borne · 🟢 en place et testé (banc d'essai
ou lecture sur la borne) · 🟡 en place, pas encore validé par vous ·
🔴 pas fait / en cours · ⏸ mis de côté par vous

---

## 1. Comment je dois travailler

| Demande | Vos mots |
|---|---|
| **Toujours suivre la configuration de Recalbox, et adapter les lumières simplement** (17/09) | « toujours suivre les config recalbox et adapter les lumières simplement » |
| Faire ce qui est demandé, **rien de plus**, et le faire bien | « fais les choses bien », « arrête de supposer ! » |
| **Lire le code de Recalbox** (configgen, ES) avant toute supposition | « depuis le début je te demande de regarder le code recalbox » |
| **Suivre les règles de Recalbox**, sans modifier ses fichiers d'origine | « suis les règles de recalbox », « tu touches pas au fichier d'origine » |
| Ne rien casser en voulant améliorer : **pas de régression**, tout revérifier | « quand tu fais des évolutions ne fais pas de régression » |
| Vérifier **en vrai** avant de dire « c'est bon » | « donc t sûr que ça marche », « sûr de sûr » |
| Réponses **claires et simples**, pas d'usine à gaz | « pourquoi c compliqué je veux juste que ça marche » |
| Faire le **point régulièrement**, sur le travail et sur l'état du PC | « fais-moi le point régulier » |
| Être **autonome** : le PC d'en bas tourne seul, vous êtes souvent à la borne (en haut) | « tu peux pas être autonome » |
| **Heure française** ; ne pas parler de « nuit » : le PC tourne 24 h/24 jusqu'à la fin | « arrête de me parler de nuit » |
| Ne pas voler **clavier / souris** du PC | « rends-moi la souris » |

## 2. Code et dépôt

| Demande | État |
|---|---|
| Code **propre, commenté**, sans doublon, optimisé — lisible par d'autres (« je serai pas forcément le seul ») | 🟢 revu à chaque modification |
| Même hygiène que les développeurs de la carte (Digi) | 🟢 |
| **Économiser RAM et CPU du Raspberry** : navigation fluide, LED sans latence | 🟢 3 programmes à 0 % CPU, 10-23 Mo chacun (santé du 17/09) |
| Tests / diagnostics pour **tout** ce qui doit l'être | 🟢 14 bancs d'essai + essai-boutons, essai-partie, essai-consoles (borne réelle) |
| GitHub `zucco-tech/arcade-panel-data` **propre et bien renseigné** | 🟢 poussé le 17/09 03:50 |
| **Aucune mention de Claude** dans commits, PR, fichiers | 🟢 vérifié avant chaque envoi |
| Jeton `/mnt/recalbox/git.txt` : **le garder** | 🟢 |
| Données **par système** (un JSON par système), dossiers bien rangés, un seul dossier `panneau-allinone` | 🟢 |
| Installation simple pour un copain : **seulement les fichiers nécessaires**, jamais tout le share (roms locales) | 🟢 `mettre-en-service.sh` |
| Scripts partagés rangés dans `userscripts/panneau-allinone/` | ✅ 16/09 |

## 3. Les LED du panneau

| Demande | État |
|---|---|
| **N'allumer que les boutons utiles** au jeu | 🟢 bancs |
| Jeu **1 joueur** : poste 2 éteint, y compris sa pièce et son start | 🟢 bancs |
| Jeu **2 joueurs** : mêmes boutons des deux côtés | 🟢 bancs |
| Couleurs **fidèles** aux bornes et manettes d'origine (« fais comme les arcades d'origine »), **aussi en jeu** (17/09) | 🟢 consoles vérifiées en vrai le 17/09 (PSX, Saturn, Dreamcast, N64, GB, GBA, SNES, Megadrive) ; N64 et Neo Geo CD corrigées ; arcade : 3 429 jeux sur 7 024 avec vraies couleurs (868 + 2 548 variantes + 13 Neo Geo), provenance dans chaque fiche de `boutons-arcade.json` |
| **Survol** dans les listes : bonnes touches et bonnes couleurs, sans latence | 🟡 |
| Au **lancement** : pas d'éclair (tout qui s'allume), pas de clignotement d'intensité | 🟢 |
| Menu, quelqu'un devant : **100 %** ; personne depuis 30 s (**clip**) : **50 %** ; pas de mode jour/nuit | 🟢 `brightness=255`, `idle=128`, `idle.delay=30` |
| Toucher le joystick ou un bouton : **tout se rallume** à 100 % | 🟢 |
| En clip : **les deux START allumés**, **pièce et HK éteints** | 🟢 bancs |
| Portables (Game Boy…) : jamais de poste 2 | 🟢 bancs |
| Liste des systèmes / arcade : J1 et J2 allumés aux couleurs du système | 🟢 bancs |
| **Pièce = SELECT** ; START = bonhomme ; manettes Nintendo ont les deux, Sega souvent pas de SELECT | 🟢 bancs |
| LED qui **suivent le mappage de Recalbox** (Configurer une manette) et le câblage mesuré | 🟢 `cablage.py` relit `es_input.cfg` |
| **Toutes machines : les LED sur les boutons que l'émulateur utilise vraiment** (17-18/09) | 🟢 vérifiés en vrai : GB, GBA, SNES, Megadrive, PSX, Saturn, Dreamcast, N64, Neo Geo (17-18/09). 33 machines sans fiche relevées en chargeant leur émulateur sur la borne (`boutons-systemes.json`) : PV-1000 2 boutons, Channel F 4, Intellivision 3, V.Smile 4 vérifiés ; 12 machines à clavier (Alice, PC-98…) n'allument plus rien au lieu de 6 |

## 4. Les boutons

| Demande | État |
|---|---|
| **Toujours suivre la configuration de Recalbox**, arcade comprise ; ne jamais déplacer un bouton ; les LED s'adaptent (17/09, remplace le « bouton 1 en haut à gauche » du 16/09) | ✅ validé par vous à la borne le 17/09 : 1942 FBNeo, SF2 FBNeo, 1942 MAME, Metroid II (GB), Mega Man BN4 (GBA) |
| Les LED prennent la couleur du bouton qu'elles portent, même quand l'émulateur range les boutons autrement (SF2 FBNeo) | ✅ SF2 FBNeo validé le 17/09 |
| La touche qui **clignote** doit être celle qui agit (« je suis obligé de faire bouton 4 ») | 🟢 les LED suivent maintenant les vrais boutons ; à revoir si un cas réapparaît |
| Validation par un bouton (certains jeux) : guider seulement quand c'est utile | 🟡 |

## 5. Crédits (pièce / START qui clignotent)

| Demande | État |
|---|---|
| Comportement d'arcade : **sans crédit, PIÈCE clignote ; avec crédit, START clignote** — aussi sous MAME | 🟢 essai-partie.sh (LED lues sur la carte) le 16/09 |
| **Deux joueurs** : compteurs séparés ou cagnotte commune ; si commune, pas de faux « joueur 2 » ; inviter le joueur 2 à rejoindre | 🟢 |
| Adresse des crédits pour **tous les jeux**, « à la perfection », « tu cherches… et trouve » | 🟢 13 066 fiches sur la borne (17/09 06:40) |
| **Les ~600 MAME restants** : « à la fin des fins » | 🔴 en cours depuis le 17/09 : 348 jeux lents (1-2 jours) + 168 Williams/Midway (mémoire sauvegardée initialisée : Joust trouvé en 16 s) ; 156 cartes Sega à discuter (le cœur MAME plante) |
| Envoyer les nouvelles adresses sur la borne | 🟢 17/09 06:40 ; à refaire à la fin de MAME |

## 6. Contraintes

- Ne rien modifier dans **le système Recalbox** de la borne ; seulement `/recalbox/share`, et demander avant de changer un réglage.
- Sur le PC : ne rien écrire hors de `/mnt/recalbox` (outils, données, journaux).
- Ne pas relancer le démon des crédits **pendant une partie**.
- La carte **AllInOne est un prototype** que vous testez chez vous : **rien à proposer à Recalbox** pour l'instant.
- Mot de passe de la borne : celui, public, de Recalbox.

## 7. Mis de côté ou traités ailleurs

| Sujet | État |
|---|---|
| **Bandeau d'aide** en bas du menu qui ne correspond pas aux boutons | ⏸ « ce qui va rester un problème c'est le bandeau, mais ça on verra » |
| Intégrer AllInOne dans le gestionnaire de manettes / merge request | ⏸ « pour le moment on n'en parle plus » |
| Correctif du pilote G,R,B sur la borne | ⏸ déconseillé (ne change que des noms) |
| Dev Recalbox (Docker, NAS `/mnt/recalbox-dev`) | ailleurs : conversation « Dev recalbox » |
| Noms des meilleurs scores FBNeo perdus au redémarrage | ⏸ « je vais en parler au dev recalbox » |

## 8. Après l'arcade : les consoles

| Demande | État |
|---|---|
| Faire clignoter **START** (ou SELECT, ou un bouton) sur les jeux **console** qui attendent un appui à l'écran-titre, comme le fait une borne d'arcade. Méthode différente : pas de compteur de crédits sur console, il faut détecter que le jeu *attend* un appui. À faire **quand tous les jeux d'arcade seront passés** (demandé le 24/09) | ⏳ après l'arcade |
