# arcade-panel-data

*[Version française : LISEZ-MOI.md](LISEZ-MOI.md)*

Machine-measured data for driving an illuminated arcade control panel:
**where each game keeps its credit counter in memory**, and **which buttons
each game actually uses**, with their original cabinet colours.

Two datasets, one purpose — making a home cabinet behave like a real one:
the coin button blinks when credits run out, the start button takes over
when a credit is available, and only the buttons the game actually uses
light up, in the colours of the original panel.

---

## Why this exists

A credit counter is not something Recalbox, RetroArch or any frontend knows
about. It lives in the emulated machine's RAM, at an address that differs
for every game, and **nobody had published those addresses**.

The cheat databases come close — an "Infinite Credits" cheat points at
exactly that byte — but they cover a minority of games, and many popular
titles (Street Fighter II, Metal Slug, Cadillacs & Dinosaurs) have no credit
cheat at all.

So we measured them. On a real cabinet, by inserting real coins.

## Datasets

### `data/credits-arcade.json`

| | |
|---|---|
| games with a measured address | **1692** |
| leads imported from cheat databases | 2646 |
| games that resisted | 287 |

Each entry records what was verified, not what was assumed:

```json
"fbneo/1942": {
  "jeu": "1942",
  "systeme": "fbneo",
  "core": "FinalBurn Neo",
  "ram": { "taille": 12544, "commande": "READ_CORE_RAM" },
  "credits": {
    "adresse": 17, "adresse_hex": "0x0011", "octets": 1,
    "miroirs": [],
    "verifie_insertion": true,      // the byte went up when a coin went in
    "verifie_consommation": true,   // and down when START consumed a credit
    "pieces_observees": 2
  },
  "releve": { "le": "2026-09-11", "methode": "balayage nocturne" }
}
```

**Entries are keyed `system/game`, never by game name alone.** The same ROM
set runs under different cores — `fbneo/1942` and `mame/1942` — and each core
lays out memory its own way. Keying on the name alone would silently
overwrite one with the other. Each entry also records its `core`; if a game
later runs under a different one, the address is ignored and re-learned.

### `data/boutons-arcade.json`

Per game: how many buttons it uses, each button's original colour on the
cabinet, and what it does.

```json
"1942": {
  "nom": "1942 (Revision B)",
  "nombre": 2,
  "boutons": {
    "BUTTON1": { "couleur": "Red",   "fonction": "Fire" },
    "BUTTON2": { "couleur": "White", "fonction": "Loop" }
  },
  "mode": "2P alt"
}
```

Buttons are named **logically** — `BUTTON1`, `BUTTON2` — never as physical
LEDs. Mapping them to a particular board's wiring belongs to whatever drives
the lights, not to the data. A different panel, a different board: the data
stays correct.

Source: MAME metadata published by [arcade-database](https://adb.arcadeitalia.net).

---

## How the addresses were measured

RetroArch exposes the emulated machine's memory over its network command
interface (UDP 55355, `network_cmd_enable`). A credit counter has a
signature no other byte shares: it goes **up by exactly one** when a coin is
inserted, and **down** when START consumes one.

1. photograph the whole RAM
2. insert a coin
3. photograph again, keep the bytes that went up by exactly 1
4. repeat — two or three coins leave a single candidate
5. press START: the surviving byte must go **down**

Step 5 is what separates a credit balance from a total-coins counter, and it
is why entries carry `verifie_consommation`. When the evidence is thinner
than that, no entry is written at all — the game goes to `difficiles` and is
retried later. **An unmeasured game is better than a wrong address.**

Games with a lead from a cheat database skip the photographs entirely: two
candidate addresses, settled by the first coin.

### Findings worth knowing

Four measurements shaped every tool here:

- **`READ_CORE_MEMORY` does not work with FBNeo** — it answers
  `no memory map defined`. Only `READ_CORE_RAM`, which reads system RAM flat
  from zero, is usable.
- **RetroArch polls its command socket once per frame.** A command costs one
  frame — 16.7 ms at 60 Hz — *regardless of its size*. Reading 1 byte costs
  as much as reading 16 KB, so read big.
- **16 KB is the largest single read.** A full 64 KB RAM snapshot is
  therefore 4 commands, about 68 ms.
- **Cheat addresses need translating.** They are given in the emulated CPU's
  address space, where RAM starts high — `0xFF0000` on a 68000 CPS board,
  `0xE000` on a Z80 board — while `READ_CORE_RAM` reads from zero. Masking
  the low bits recovers the offset, and 68000 games need an extra `XOR 1`
  because FBNeo stores big-endian RAM byte-swapped on a little-endian host.
  Verified on `pzloop2`: the cheat says `0xFF80B0`, the counter is at
  `0x80B1`.

## How good is the data

Arcade ROM sets come in families — a parent and its regional variants. Every
member of a family runs the same code, so **every member must report the same
address**. That gives a free audit, with no game to re-run:

```
394 clone families measured
326 agree exactly          (82.7 %)
 68 disagree
```

The disagreements are almost all explainable rather than wrong: bootlegs
(`pacmanbl` against 24 consistent `puckman` clones), successive hardware
revisions (`cloak` and its four `agentx` versions), or the same address in a
differently sized RAM window (`blandia` at `0x100ABE`, `blandiap` at
`0x0ABE`).

One address was also verified by hand against the published cheat databases,
and **the measurement won**: MAME's cheat for `1942` points at `0x0018`,
which never moves. The measured `0x0011` tracks credits exactly.

## Tools

| | |
|---|---|
| `tools/nuit-credits.py` | unattended sweep of a whole library |
| `tools/importer-cheats.py` | import leads from FBNeo and MAME cheat sets |
| `tools/importer-boutons.py` | build the button dataset |
| `tools/capture-credits.py` | measure one game by hand |
| `tools/verifier-borne.py` | pre-flight check before a sweep |
| `tools/clavier_virtuel.py` | virtual keyboard (`uinput`) used to insert coins |

Python 3, standard library only. No dependencies.

The sweep drives a real cabinet: EmulationStation launches each game
(`START|system|/full/rom/path` over UDP 1337 — the path must be complete,
not just the filename), a virtual keyboard inserts coins, memory is compared,
`QUIT` hands control back, next game. 1903 games took 9 h 15 on a Raspberry
Pi 5, with no failures.

A keyboard rather than a virtual gamepad, deliberately: RetroArch assigns
gamepads to ports in discovery order, so a virtual pad would land on player 3
and be ignored. The keyboard is bound to player 1 by default — Enter for
START, Right Shift for SELECT, which is the coin — and needs no
reconfiguration of the real controllers.

### Tests

```bash
cd tools/tests && python3 test_base.py
```

Eight suites, run against a simulated RetroArch — **no hardware needed**.
They cover learning end to end, mirrored counters, schema migration, the
three panel states, player 2, clone collisions across cores, and colour
restoration. They have caught real defects: a RAM size measured but never
stored, an entry claiming a discovery method it had not used, games condemned
on a single unlucky attempt.

## `cabinet/` — the only hardware-specific part

`cabinet/credits(permanent).py` is an EmulationStation permanent script that
drives the LEDs of an **AllInOne board (digipcb.tech)** on Recalbox. It reads
the datasets and blinks accordingly; it also learns any game the sweep
missed, the first time you play it.

It writes only to `brightness`, and to `multi_intensity` solely for the
duration of a blink — reading the board's own colour first and restoring it
after, and never overwriting a colour the board has repainted in the
meantime. Recalbox's own files are neither modified nor replaced.

Two quirks of the prototype board it was written against, both configurable
at the top of the file and **not encoded in the datasets**:

- the driver's `start` and `select` LEDs are crossed relative to the panel
- WS2812B LEDs expect **green, red, blue** order, while the driver declares
  red, green, blue — writing pure red lights green

## Limitations

- Arcade only. On a console, the button count is a property of the pad, not
  the game.
- A core that does not expose its RAM cannot be measured — 97 games here.
- Some counters are BCD or two bytes wide and escape the method.
- Button metadata is MAME-derived: a handful of games have none.
