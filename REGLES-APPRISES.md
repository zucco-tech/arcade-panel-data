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
