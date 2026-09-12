# Ce que la machine nous a appris — 11 septembre 2026

Ce fichier existe pour qu'on ne repasse pas par les mêmes impasses. Chaque
règle vient d'une mesure faite sur cette machine, pas d'une supposition.

## Sur RetroArch et les cœurs

**`GET_STATUS` fait planter RetroArch avec FBNeo.** Deux morts sur deux
essais, en une seconde, toujours au même endroit (segfault, lecture d'un
pointeur nul). `READ_CORE_RAM` et `VERSION` répondent douze fois sur douze.
C'était la cause du blocage attribué à SSH depuis le début. Ne jamais
utiliser `GET_STATUS` : pour savoir si un jeu tourne, lire sa RAM.

**Le cœur doit correspondre au set de ROMs, pas à la machine.** FBNeo change
la définition des romsets entre versions. Les compilations libretro d'août
et septembre 2026 refusent des sets de mars 2025 qui marchent très bien
ailleurs. Le bon cœur ici est celui extrait de l'image **Recalbox x86_64**,
installé en `/opt/coeurs/fbneo_rb.so`.

**Un binaire de la borne ne tourne pas sur le PC.** Le Pi 5 est en ARM, le PC
en x86-64. Copier `fbneo_libretro.so` depuis la borne ne sert à rien.

**Les adresses sont portables entre Pi et PC.** Vérifié : `pzloop2` compte
ses crédits en `0x0450` des deux côtés, mesuré à la pièce réelle, et 14
adresses sur 20 prises au hasard dans les relevés de la borne se confirment
sur le PC. L'adresse dépend du cœur, jamais du processeur.

## Sur la façon de mesurer

**Les deux joueurs paient AVANT qu'on appuie sur START.** C'est l'ordre d'une
vraie borne. Chercher le compteur du joueur 2 après avoir lancé la partie ne
donne rien — zéro trouvé sur trois jeux. Dans le bon ordre, ça marche.

**Une seule pièce ne suffit jamais à isoler un compteur.** Un jeu qui tourne
fait bouger des dizaines d'octets : 288 sur `pzloop2`, 181 sur `bloodwar`.
Il faut deux ou trois pièces et ne garder que ce qui monte de 1 à chaque
fois. Pareil pour le joueur 2 : on ne devine pas son compteur « à côté » de
celui du joueur 1.

**Tous les jeux n'encaissent pas sur SELECT.** Flippers, jeux de tir,
certains japonais ont le monnayeur ailleurs. Quand SELECT ne donne rien, il
faut essayer les autres boutons du panneau avant de condamner le jeu.

**Certains compteurs sont en ASCII.** `avengrgs` range ses crédits en
caractères : 49 puis 50, c'est-à-dire « 1 » puis « 2 ». Chercher une hausse
de 1 le trouve quand même ; en déduire autre chose serait faux.

## Sur les pièges du système

**Xlib tue le programme quand une fenêtre disparaît.** Une capture prise
pendant que RetroArch se ferme a arrêté le balayage au seizième jeu. Il faut
poser un gestionnaire d'erreurs X qui les ignore.

**Ne jamais déduire un refus d'un silence.** Conclure « romset inconnu »
parce que le journal ne contenait pas encore « Romset name » a produit 23
faux positifs sur 20 jeux : le journal est écrit sur le NAS et arrive en
retard. Ne se fier qu'aux messages explicites.

**Tuer un processus, c'est tuer son groupe.** `terminate()` sur le fils
direct visait `dbus-run-session` et laissait RetroArch vivant, réadopté par
systemd. Un orphelin suffit à faire échouer tous les lancements suivants.

**Ne jamais jeter la sortie de RetroArch.** Elle était envoyée dans
`/dev/null` : sans elle, plusieurs heures de diagnostic à l'aveugle. Elle
est maintenant conservée dans `journaux/retroarch.log`.

**Une capture d'écran vaut mieux qu'une déduction.** C'est une image qui a
montré `Romset is unknown`, message qui n'apparaît nulle part dans les
journaux. Quand un jeu ne réagit pas : photographier et regarder.

## Sur la conduite du travail

**Ne pas annoncer une cause avant de l'avoir reproduite.** Trois diagnostics
faux ont été annoncés dans la journée — plein écran, crash aléatoire,
processus orphelins — chacun sur un seul essai qui ne s'est pas reproduit.

**Ne pas changer un réglage qui marche sur une hypothèse.** Basculer le cœur
sans vérifier a cassé le chargement des ROMs pendant une heure.

**Le balayage vole le clavier.** Les pièces et les START sont des touches
injectées dans la fenêtre active : si l'utilisateur prend le focus, elles
arrivent chez lui. Mettre en pause quand il a besoin de sa machine.

## Règle d'éclairage du panneau 2

Trois cas, et la fiche de chaque jeu dit lequel :

```
adresse_j2 renseignee    deux compteurs separes
                         chaque poste a son solde : le START du joueur 2 ne
                         clignote que si LUI a paye

compteur_commun = true   une seule cagnotte alimentee par les deux monnayeurs
                         on ne peut pas savoir qui a paye :
                         BOUTON DU JOUEUR 2 ETEINT

ni l'un ni l'autre       un seul monnayeur, jeu a un poste
                         panneau 2 eteint
```

Sans cette distinction, le panneau clignoterait faux une fois sur deux : il
inviterait le joueur 2 à payer dans un pot commun alors que rien ne lui
garantit sa place.

## Naomi / Atomiswave : FREE PLAY, donc rien a mesurer
Flycast force le free play (`reicast_force_freeplay = enabled`, defaut du
coeur, identique sur la borne). L ecran affiche « FREE PLAY », la piece ne
change aucun compteur utile, le START ne consomme rien : chaque jeu finit
« candidats non confirmes » apres 7 minutes. Ces systemes sont hors balayage.
Le jour ou la borne sortira du free play, il faudra d abord passer l option
a `disabled` sur le PC de releve, puis les remettre dans SYSTEMES.
Les couleurs et le nombre de boutons, eux, ne dependent pas des credits :
boutons-arcade.json couvre aussi ces jeux, le panneau les eclaire normalement.

## Jamais d avance rapide pendant le releve
Les attentes du releve sont en temps reel : l accelere ne fait rien gagner.
En revanche chaque appui de touche, tenu un quart de seconde reel, devient
plusieurs secondes de jeu. Battle Garegga restait fige sur son test de RAM,
World Heroes ne comptait que 2 pieces sur 5, et tout finissait « aucun
candidat ». Sans accelere, les deux donnent leur adresse du premier coup.

## Une piece est une impulsion, pas un appui
Armed Police Batrider (Raizing) affiche « COIN ERROR » des qu on tient le
monnayeur 0,25 s, et refuse toutes les pieces suivantes : la carte guette le
monnayeur bloque. A 0,05-0,15 s la piece passe et le compteur monte. La
duree de la piece est 0,10 s (`ClavierVirtuel.DUREE_PIECE`) ; le START garde
son quart de seconde. Verifie sur pzloop2 (0x0450), 64street (0xB6AC),
batrider (0x2401), wh1 (0xFE8B) le 12/09.

## La carte ment sur l ordre de ses couleurs
`multi_index` annonce « red green blue ». C est faux : les WS2812B de cette
carte sont cablees **vert, rouge, bleu**. Mesure du 12/09/2026 : ecrire
« 255 0 0 » sur le bouton 1 et « 0 255 0 » sur le bouton 2 allume le premier
en VERT et le second en ROUGE. Les deux programmes ecrivent donc dans
l ordre (vert, rouge, bleu) — constante `ORDRE_MATERIEL = (1, 0, 2)`.
Avant cette correction, le panneau du menu peignait a l envers tandis que le
demon des credits peignait juste : un meme jeu changeait de couleur en
entrant en partie, et la NES sortait rouge au lieu de verte.

## Deux programmes ne peuvent pas memoriser « la couleur d origine » chacun de son cote
Chacun relisait `multi_intensity` au moment ou il touchait une LED. Celui qui
lisait en second memorisait donc les couleurs du PREMIER, et les restituait
en sortant de partie : le panneau revenait avec les couleurs du jeu
precedent. Il n y a desormais qu une source : `panneau(permanent).py` publie
les couleurs de la carte (la table Recalbox du systeme) dans
`panneau-arcade/couleurs-carte.json` juste avant que la partie commence, et
`credits(permanent).py` les lit de la. Aucune course possible.

## Chercher un compteur de credits : cinq pieges, tous mesures
1. **Payer avant que la machine soit vivante.** 1944 reste fige de l image
   300 a l image 2400 (test de RAM) : une piece glissee la n existe pas.
   On attend que la memoire s anime, puis on paie.
2. **Exiger que TOUTES les pieces fassent monter le meme octet.** Des cartes
   en avalent une puis ignorent les suivantes ; l exigence stricte jetait
   alors tout. On compte les accords, et le START tranche.
3. **Ignorer le BCD.** Des cartes comptent en decimal code binaire, ou
   « un de plus » s ecrit 0x09 -> 0x10. Elles etaient invisibles.
4. **Conclure sur le premier START.** Il ne consomme pas toujours (animation
   en cours). Sur Air Gallet, un octet de bruit monte une fois et descendu
   au premier START passait devant le vrai compteur, qui n avait pas encore
   ete consomme. On appuie jusqu a trois fois, et on prefere l octet monte
   a chaque piece.
5. **Appeler « miroir » tout octet qui descend aussi.** Quand un compteur
   passe de 1 a 0, des dizaines d octets de jeu en font autant : Battle
   Garegga rendait quatre-vingt-dix faux miroirs. Un miroir doit le prouver
   en montant avec le compteur a une piece de verification.

Aucun critere d « ecran pret » ne marche pour tous : Battle Garegga agite
10 % de sa RAM pendant son test de memoire, 1944 seulement 0,1 % une fois en
attract. D ou le choix de ne plus deviner l instant, mais de payer
regulierement jusqu a ce que ca prenne.

## Regarder l ecran sans RetroArch
Le coeur fournit ses images au frontend : le releve direct les garde et sait
les ecrire en PNG (`enregistrer_image`). C est ainsi qu on a vu Battle
Garegga afficher encore « ROM RAM CHECK » au moment ou on le payait. Un
echec se regarde, il ne se devine pas.
