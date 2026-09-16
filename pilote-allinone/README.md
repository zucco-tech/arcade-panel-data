# Le pilote de LED AllInOne : l'ordre des couleurs corrigé

Le pilote `allinone_leds` de Recalbox (`projects/recalbox-allinone/allinone_leds.c`)
déclare les trois composantes de chaque LED dans l'ordre **rouge, vert, bleu**.
Les WS2812B de la carte les reçoivent dans l'ordre **vert, rouge, bleu**. Du
coup, `multi_index` annonce `red green blue` et écrire `255 0 0` allume du
vert (mesuré le 12/09/2026, bouton par bouton).

## La correction, et pourquoi elle ne casse rien

```c
static u32 color_idx[WS2812B_NUM_COLORS] = {
  LED_COLOR_ID_GREEN,   /* était RED   */
  LED_COLOR_ID_RED,     /* était GREEN */
  LED_COLOR_ID_BLUE,
};
```

Seuls les **noms** changent. `multi_intensity` est positionnel : la première
valeur écrite part toujours la première sur le fil. Donc :

| qui | ce qu'il fait | après la correction |
|---|---|---|
| `recalbox_allinone_rgb.sh` | écrit ses triplets tels quels | identique, au bit près |
| `panneau(permanent).py`, `credits(permanent).py` | lisent `multi_index` par `couleurs.ordre_materiel()` | identique : ils connaissent le mensonge du pilote d'origine et croient le pilote corrigé |
| tout programme qui lit `multi_index` pour savoir où mettre le rouge | se trompait | juste |

Vérifié sur la borne le 16/09/2026 : rien d'autre ne lit `multi_index` (ni
EmulationStation, ni les scripts de `/recalbox/scripts`, ni configgen).

Le renommage croisé `start`/`select` des LED de façade (autre défaut du même
fichier) n'est **pas** corrigé ici : changer ces noms casserait
`recalbox_allinone_rgb.sh` et tous les programmes existants. Il demande un
plan de transition à discuter avec le mainteneur.

## Les fichiers

| fichier | quoi |
|---|---|
| `fix-allinone-leds-grb.patch` | la correction du source, à appliquer à la racine du dépôt `recalbox/recalbox` |
| `allinone_leds.ko` | le module de la borne (Recalbox 11.0-patron-1-alpha-3.2, noyau `6.12.25-v8-16k`) avec la même correction |
| `essayer-sur-borne.sh` | le charge sur la borne jusqu'au prochain redémarrage, rien d'installé |
| `MERGE-REQUEST.md` | le texte prêt pour GitLab, dans les règles de contribution de Recalbox |

### Comment `allinone_leds.ko` a été fait

Ni la borne ni le PC n'ont de chaîne de compilation, et un module recompilé
à partir d'une configuration du noyau approximative risque d'être refusé
(`modversions`). Le module a donc été **pris sur la borne et corrigé en
place** : le compilateur avait intégré le tableau `color_idx` directement
dans `ws2812b_prepare_led`, sous forme de trois instructions ARM64 :

```
0xf8   mov w11, #1   -> #2      subled[0].color_index   RED   -> GREEN
0x100  mov w10, #2   -> #1      subled[1].color_index   GREEN -> RED
       mov w9,  #3              subled[2].color_index   BLUE (inchangé, sert aussi à num_colors)
```

Deux octets changés, aucune relocalisation ne les touche, le module n'est
pas signé. Même `vermagic`, mêmes symboles : le noyau le charge comme
l'original.

| | sha256 |
|---|---|
| module d'origine (`/lib/modules/6.12.25-v8-16k/updates/allinone_leds.ko`) | `3bbbd11b91113e2b78f63e977253bf9a253f7da7460be9ab79bf89457d40c11f` |
| module corrigé | `8223c41f1c6d7ec8f86fb2581407a917cf42f7eccd2b38ab3ff053ed8be050eb` |

Il ne vaut que pour **ce** noyau et **ce** module : le script d'essai
refuse de charger quoi que ce soit si l'un des deux a changé. La correction
durable est celle du source, dans Recalbox.

## Essayer sur la borne

```
sh pilote-allinone/essayer-sur-borne.sh
```

Il copie le module dans `/tmp` de la borne, décharge celui de Recalbox,
charge le corrigé, relance `panneau` et `credits`, et affiche
`multi_index` avant et après. Attendu : `red green blue` puis
`green red blue`, **et aucune couleur ne change sur le panneau**. Un
redémarrage remet le module de Recalbox.
