# En cas de coupure — que relancer

Écrit le 21/09/2026. Tout est prévu pour tourner seul jusqu'au mercredi 23 au
soir. Ce fichier sert si quelque chose s'arrête quand même.

## D'abord : est-ce que ça tourne ?

Une seule commande donne l'état de tout :

    sh /mnt/recalbox/outils/ou-en-est.sh

S'il n'existe pas encore, les trois commandes équivalentes :

    systemctl is-active campagne-credits naomi-pc
    sudo tail -5 /mnt/recalbox/journaux/campagne.log
    sudo tail -3 /mnt/recalbox/journaux/deploiement.log

`active` partout = rien à faire.

## Les deux travaux en cours

| Service | Ce qu'il fait | Doit être |
|---|---|---|
| `campagne-credits` | FBNeo, Neo Geo, ST-V, MAME, tour après tour | `active` |
| `naomi-pc` | Naomi / Atomiswave / Naomi GD, 249 jeux écartés repris | `active` |

Les deux **redémarrent tout seuls** : plantage, session graphique relancée,
redémarrage de la machine. Il ne devrait donc normalement rien y avoir à faire.

## Si un service est arrêté

    sudo systemctl start campagne-credits
    sudo systemctl start naomi-pc

Si `naomi-pc` repart puis s'arrête aussitôt, regarder pourquoi :

    sudo journalctl -u naomi-pc -n 20 --no-pager

- **« l ecran ne repond pas : on ne demarre pas »** → la session graphique
  n'est pas ouverte. Se connecter à l'écran du PC (ou le rallumer). Le service
  réessaie tout seul toutes les 5 minutes, il repartira sans rien faire.
- **« ne demarre pas » sur tous les jeux** → ne devrait plus arriver, mais si
  ça revient, c'est le jeton d'écran. Le remettre :

        xauth -f /home/recaldev/.Xauthority merge \
          $(ps -eo args | grep -o "\-auth /run/user/1000/[^ ]*" | head -1 | cut -d' ' -f2)
        sudo systemctl restart naomi-pc

## Si la borne n'a pas reçu les nouvelles adresses

L'envoi est automatique après chaque système. Pour le forcer :

    sudo sh /mnt/recalbox/outils/deployer-vers-borne.sh
    tail -2 /mnt/recalbox/journaux/deploiement.log

La borne est en 192.168.1.50. Si « borne injoignable » : elle est éteinte,
l'envoi se refera tout seul plus tard.

## Si le NAS refuse l'accès (erreurs « Permission non accordée »)

C'est arrivé le 20/09. Cause : dans DSM, **Dossier partagé → recalbox →
Autorisations NFS**, une règle visant `192.168.1.82` (ce PC) avec
« Mappage de tous les utilisateurs ». Elle écrase la règle générale.
Correction : mettre son **Squash** sur **« Pas de mappage »**. Même chose sur
le dossier `roms`.

## Sauvegardes

- La base vit sur le NAS : `/mnt/recalbox/donnees/credits-arcade.json`
- Copie hors NAS : https://github.com/zucco-tech/arcade-panel-data
- Pour pousser à la main :

        sudo git -C /mnt/recalbox/depot add -A
        sudo git -C /mnt/recalbox/depot commit -m "sauvegarde"
        sudo git -C /mnt/recalbox/depot push origin main

## Pour arrêter proprement (sans rien abîmer)

    touch /tmp/arret-naomi        # Naomi s'arrête à la fin du jeu en cours
    sudo systemctl stop naomi-pc campagne-credits

Ne jamais tuer un relevé en pleine partie : la base est sauvée après chaque
jeu, mais le jeu en cours serait à refaire.
