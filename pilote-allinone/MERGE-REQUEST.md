# Merge request pour gitlab.com/recalbox/recalbox

Préparée selon `CONTRIBUTE.md` (lu le 14/09/2026) : une branche, commit
conventionnel, entrée dans `RELEASE-NOTES.md`, ligne dans `TESTING.md`
section `[NEXT]`. Le numéro `#…` est celui de la MR, connu une fois ouverte.

## Branche

```
fix/allinone-leds-grb-order
```

## Commit

```
fix(allinone): declare the WS2812B subleds in green, red, blue order
```

Corps :

```
The AllInOne LED driver registered each WS2812B with color_idx
{RED, GREEN, BLUE}, but WS2812B receive their bits in green, red,
blue order and subled[0] goes first on the wire. multi_index therefore
reported "red green blue" and writing "255 0 0" lit the button green.

Only the labels change: multi_intensity stays positional, so
recalbox_allinone_rgb.sh, which writes raw triplets, is unaffected.
```

Fichier : `projects/recalbox-allinone/allinone_leds.c` — voir
`fix-allinone-leds-grb.patch`.

## RELEASE-NOTES.md

```
- AllInOne: LED colors are now declared in the order the WS2812B expect (green, red, blue)
```

## TESTING.md, section [NEXT]

```
- [ ] AllInOne: check that /sys/class/leds/aio_p1_b1_1/multi_index reads "green red blue" (#…)
- [ ] AllInOne: check that system colors in the menu are unchanged (NES buttons stay red) (#…)
- [ ] AllInOne: check that writing "0 255 0" to aio_p1_b1_1/multi_intensity lights the button red (#…)
```

## Description de la MR

```
## What

The AllInOne LED driver declares its subleds as red, green, blue. The
WS2812B on the board take green, red, blue: multi_index lies, and any
program trusting it paints the wrong color ("255 0 0" lights green).

## How

Swap RED and GREEN in color_idx. Nothing else.

## Why it is safe

multi_intensity is positional; the bytes sent on the wire are identical
before and after. recalbox_allinone_rgb.sh writes raw triplets and does not
read multi_index — nothing in the image reads it (checked on
11.0-patron-1-alpha-3.2). Only the reported labels become correct.

## Tested

Raspberry Pi 5, AllInOne prototype v3.0, two 6-button panels,
11.0-patron-1-alpha-3.2 (kernel 6.12.25-v8-16k): multi_index reads
"green red blue", menu colors unchanged, "0 255 0" lights red.

## Not in this MR

allinone_leds.c also registers the LED wired at the SELECT position as
aio_p*_start and vice versa. Renaming would break recalbox_allinone_rgb.sh
and user scripts, so it needs a transition plan — happy to discuss it
separately.
```

> La ligne « Tested » n'est vraie qu'une fois `essayer-sur-borne.sh` passé
> et les deux vérifications visuelles faites. À ne pas envoyer avant.
