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
entrant en partie. Cette correction vaut pour ce qui est ecrit en vrai RGB :
nos fiches d arcade et manettes-consoles.json. La table de Recalbox est un
cas a part, voir ci-dessous.

## La table de couleurs de Recalbox est DEJA dans l ordre du materiel
Le script d origine `recalbox_allinone_rgb.sh` ecrit ses triplets tels quels
dans les LED. Ses valeurs sont donc dans l ordre reel de la carte (vert,
rouge, bleu), pas en RGB : « 00 FF 00 » y veut dire ROUGE. Lui appliquer
notre correction la retournait — la NES et la Game Boy sortaient vertes,
alors que leurs boutons sont rouges. Constate le 14/09/2026 en lisant les
LED sur la borne. La preuve par la SNES : sa table, envoyee telle quelle,
donne jaune, rouge, vert, bleu — les boutons B, A, Y, X ; corrigee, elle
donnait jaune, vert, rouge, bleu, faux. Regle : ce qui vient de la table
Recalbox est marque « brut » et part sans correction ; le reste est corrige.
Et cette table est fidele presque partout — NES rouge, PSX bleu/rouge/rose/
vert, Neo Geo jaune/bleu/rouge/vert, START rouge de la N64, bleu de la Game
Gear. Ses 9e et 10e entrees disent meme si la manette a un SELECT et un
START : noires sur Master System, Game Gear, Saturn, Dreamcast, GameCube.
manettes-consoles.json ne corrige que ses rares erreurs.

## Sur une borne, PIECE est un monnayeur ; sur une console, c est SELECT
Le meme bouton du panneau change de nature avec le jeu. Sur un jeu d arcade
c est le monnayeur : il ne sert a rien tant que personne n est devant, il
reste noir pendant les clips. Sur une console, un ordinateur ou une
portable, c est le SELECT de la manette, un bouton de jeu comme les autres :
il s allume avec eux, clips compris. Sans cette distinction, on a eu les
deux defauts a la suite : le SELECT de la Game Boy noir en veille, puis —
en le traitant comme un bouton de manette pour tout le monde — le panneau
entierement noir sur un clip mame, parce que mame n est pas dans la table
Recalbox et que « pas de manette » avait ete lu comme « pas de boutons ».
Regle : un systeme absent de la table Recalbox n est pas une console, il
garde la regle de la borne.

## Quel bouton envoie quel code, LED par LED
Mesure le 14/09/2026 en allumant chaque LED du poste 1 a son tour et en
notant le code evdev recu (associer-boutons) :

    LED b1 -> 304   b2 -> 305   b3 -> 307   b4 -> 313   b5 -> 311   b6 -> 310
    PIECE (select) -> 314   START -> 315   hotkey -> 316

Le poste 2 envoie les memes codes sur sa manette. Cette mesure vit dans
cablage.json ; le role de chaque code (b, a, y, x, l1, r1, select, start,
hotkey) vient d es_input.cfg, le mappage de Recalbox ; et cablage.py croise
les deux : bouton 1 du jeu = role b = code 313 = LED 4. Plus rien n est en
dur : si un joueur remappe sa manette dans Recalbox, ou cable ses boutons
autrement et relance associer-boutons, les LED suivent au lieu de se
decaler.

## Le joystick est une activite, et 45 secondes ne font pas une fin de partie
Le demon des credits ne sait pas si l on joue ou si le jeu est revenu en
attract : apres START le compteur est a zero dans les deux cas. Il tranche
au silence des manettes. Deux erreurs corrigees le 14/09/2026 : seules les
touches comptaient, pas le joystick — un jeu mene au stick passait pour
abandonne — et 45 s suffisaient, alors qu un joueur qui lit l ecran ou
reflechit les depasse sans peine ; son START se mettait a clignoter en
pleine partie. Desormais tout geste compte, stick compris, et il faut deux
minutes de silence complet.

## Un script shell en cours d execution ne se recharge pas
`surveiller.sh` tournait depuis le 12/09 21 h 36. Le 13/09 a 13 h 30 on y a
ajoute la reprise acharnee. Le 13/09 a 21 h 07, a la fin du balayage MAME,
il est passe directement a la reprise par RetroArch : l instance en cours
suivait toujours l ancien plan, elle n a jamais vu la modification. Un
shell lit son script au fil de l eau, mais ne le relit pas ; et modifier le
fichier sous lui peut meme lui faire executer n importe quoi, puisqu il
avance par position dans le fichier. Regle : on ne modifie jamais un script
qui tourne ; on l arrete (`touch /tmp/arret-nuit`), on modifie, on relance.

## Deux programmes ne peuvent pas memoriser « la couleur d origine » chacun de son cote
Chacun relisait `multi_intensity` au moment ou il touchait une LED. Celui qui
lisait en second memorisait donc les couleurs du PREMIER, et les restituait
en sortant de partie : le panneau revenait avec les couleurs du jeu
precedent. Il n y a desormais qu une source : `panneau(permanent).py` publie
les couleurs de la carte (la table Recalbox du systeme) dans
`panneau-allinone/couleurs-carte.json` juste avant que la partie commence, et
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

## Quels systemes arcade sont mesurables, et lesquels ne le sont pas
| systeme | roms | comment |
|---|---|---|
| fbneo | 7772 | coeur FBNeo, le gros du travail |
| neogeo / neogeocd | 124 / 232 | meme coeur |
| stv | 114 | coeur mednafen_stv ; il lui faut `stvbios.zip` dans le dossier systeme de RetroArch, sinon il refuse tout. Verifie sur cotton2 (compteur 0x0741) |
| fba | 223 | vieux sets FB Alpha : FBNeo n en accepte qu un sur six, les autres manquent de fichiers et ne se lancent pas davantage sur la borne |
| mame | 20601 (dossier `mame0278`) | mesurable **par Lua a l interieur de MAME**, voir ci-dessous. Environ 25 s par jeu. Masque sur la borne (`mame.ignore=1`) tant que le proprietaire ne l active pas |
| naomi, naomigd, naomi2, atomiswave | 457 | flycast force le FREE PLAY : aucun compteur a mesurer |
| model2, model3 | 118 | Recalbox les emule avec des programmes a part, hors libretro : leur memoire n est pas lisible, c est sans issue |

## MAME : la porte s ouvre, mais la piece est vide
Deux choses distinctes, mesurees le 12/09/2026.

**Comment lui parler.** Le coeur MAME prend le dossier parent du fichier
pour un nom de machine : une rom dans `roms/mame/` lui fait chercher une
machine appelee « mame ». Il accepte en revanche un fichier `.cmd`
contenant une ligne de commande — c est dans ses extensions declarees
(`cmd|zip|7z`) :

    echo "10yard -rompath /mnt/roms/mame/mame0278" > 10yard.cmd

Ainsi la machine demarre pour de bon ; son propre journal dit « Starting
10-Yard Fight » et la capture montre le jeu.

**Pourquoi c est sans issue quand meme.** Le coeur n expose pas la memoire
de travail. Sur cinq jeux essayes : pacman (1008 octets) et dkong (3072)
rendent un pointeur nul, galaga aussi (64) ; sf2ce et mslug rendent 2048
octets qui ne changent jamais — c est leur sauvegarde, pas leur RAM. Sans
memoire lisible, aucun compteur de credits n est mesurable. Les memes jeux
se mesurent tres bien sous FBNeo, qui, lui, expose tout.

Corollaire pour tout nouveau coeur : demander la memoire APRES quelques
images. MAME rend un pointeur nul juste apres le chargement, ce qui faisait
passer pour « refusees » des roms qui tournaient.

## MAME se mesure de l interieur, en Lua
L API memoire de libretro est inutilisable avec MAME : sur dix jeux tires au
hasard, neuf demarrent mais un seul rend un pointeur, et il est fige.

La solution est ailleurs. MAME embarque un interpreteur Lua, et comme on lui
donne sa ligne de commande (fichier `.cmd`), on peut lui faire executer notre
script : `-autoboot_script outils/mame-credits.lua`. Depuis ce script on a

  - **la carte memoire du pilote** : `space.map.entries` donne le type de
    chaque zone (`rom`, `ram`, `port`...). On ne photographie que la `ram`.
    Les « shares » ne suffisent pas : chez Pac-Man ils ne couvrent que la
    memoire video, et le releve trouvait le chiffre AFFICHE au lieu du
    compteur ;
  - **les entrees nommees** : `Coin 1`, `1 Player Start`, et jusqu aux
    interrupteurs de reglage. Plus besoin de deviner quel bouton encaisse —
    MAME le dit. Sur Neo Geo c est `:AUDIO_COIN/Coin 1`, ailleurs `:IN0/Coin 1`.

Resultats verifies : pacman 0x4E6E, dkong 0x6001, galaga 0x99B5,
mslug 0xD00034, sf2ce 0xFF82DA, 1942 0xE011, bublbobl 0xE366 — tous montes a
chaque piece et redescendus au START.

**La preuve que les deux methodes disent vrai** : pour 1942, MAME rend
0xE011 et FBNeo 0x0011. C est le meme octet — la fenetre de RAM exposee par
FBNeo commence a 0xE000. Deux emulateurs, deux methodes, une seule adresse.

## Les scripts allinone reviennent a chaque demarrage
`/etc/init.d/S13allinone` les REECRIT au boot quand le module de la carte
est charge :

    echo 'bash /recalbox/scripts/recalbox_allinone_rgb.sh $6' > "allinone[systembrowsing].sh"

Les renommer une fois ne suffit donc pas : ils reviennent. La parade est le
crochet officiel `share/system/custom.sh`, appele par `S99custom` — donc
APRES S13 — qui les remet hors service a chaque allumage. Il en profite pour
poser les couleurs en veilleuse : EmulationStation met plusieurs minutes a
charger ses listes, et le panneau restait noir pendant ce temps.

La share est en exFAT : le bit executable n existe pas. Sans importance,
S99custom appelle le fichier par `bash custom.sh start`. Le script ne doit
donc rien faire quand on lui passe « stop ».

## MAME : ne mesurer que les jeux d arcade
Sur 20601 machines, 6995 sont des jeux d arcade — ce sont celles que la
base des boutons connait. Les 13351 autres sont des machines a sous, des
ordinateurs, du mahjong : pas de monnayeur, pas de compteur, et chacune
coutait 150 s pour conclure a rien. Le releve MAME se limite donc a la base
des boutons, et commence par les 310 jeux d arcade que FBNeo ne sait pas
faire — les seuls ou MAME apporte une fiche que rien d autre ne donne.

## MAME : ce que les rates ont appris (nuit du 12 au 13/09)
Un quart de rates au premier passage, dont de vrais jeux. Quatre causes,
toutes de notre cote, verifiees une a une en regardant l ecran :

1. **Le mapper memoire.** Sur le System 16 (Altered Beast, Alien
   Syndrome), tout l espace d adressage passe par un delegue ; lire les
   zones « ram » a travers lui ne rend pas la RAM reelle. L ecran affichait
   CREDITS 9 sans qu un octet monte. Les **shares** sont la memoire brute :
   on les photographie aussi.
2. **Le plafond de la photo.** Pris dans l ordre du hasard, les shares de
   tuiles (des centaines de Ko) remplissaient le plafond avant la RAM de
   travail (quelques Ko). Les petits d abord, plafond a 2 Mo.
3. **Pas de START.** The Three Stooges n en declare pas : on demarre avec
   un bouton de jeu. Sans START trouve, on appuie sur le bouton 1 du
   joueur 1 — ce qu un joueur ferait.
4. **Le delai fixe avant la premiere piece**, comme sous FBNeo : remplace
   par l attente que la RAM vive, puis l insistance.
