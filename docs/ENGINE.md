# The engine

The three titles of the release are the PlayStation 3 versions of the older
PlayStation 2 games, and the engine says so in its own data. This document
records what the programs say about the engine that built them, and why that
is the anchor of the naming.

## The build stamp

The engine leaves a stamp in the data of each program:

| Program | Stamp |
|---|---|
| `EBOOT` — the collection launcher | none |
| `RC1` — Ratchet & Clank (2002) | `rt_udp 3.05.201103091800` |
| `RC2` — Ratchet & Clank 2: Going Commando | `rt_udp 3.05.201103091800` |
| `RC3` — Ratchet & Clank 3: Up Your Arsenal | `rt_udp 3.05.201103091800` |

The stamp dates the engine: **9 March 2011**. The launcher carries none, which
is what one expects of it: it is the graphics and menu module of the
collection, not a game.

The stamp is read by [`tools/engine_identity.py`](../tools/engine_identity.py),
and the result is in [config/engine.tsv](../config/engine.tsv).

**The names of the collection are not the numbers of the series.** The
collection numbers its own titles `rc1`, `rc2` and `rc3`, and `rc1` is the
*first* game of the series — Ratchet & Clank of 2002 — not the sixth. That was
measured, not assumed: the standalone title whose content id is
`UP9000-NPUA80643_00-RC1REMASTER00100` carries the name `Ratchet & Clank™` in
its `PARAM.SFO`, the trophy set `NPWR02335`, and an executable of exactly the
size of the collection's `rc1`. See [RELATED-TITLES.md](RELATED-TITLES.md).

## The stamp that is not there

The standalone PlayStation Network titles were measured the same way:

| Program | Stamp |
|---|---|
| Ratchet & Clank, `NPUA80643` | `rt_udp 3.05.201103091800` |
| Going Commando, `NPUA80644` | `rt_udp 3.05.201103091800` |
| Up Your Arsenal, `NPUA80645` | `rt_udp 3.05.201103091800` |
| Ratchet: Deadlocked, `NPUA80646` | `rt_udp 3.05.201103091800` |
| **Tools of Destruction, `NPUA80965`** | **none** |

The four remasters carry the stamp of 2011, like the collection does.
**Tools of Destruction does not, and it is not one of the collection's
titles**: it is a separate PlayStation 3 game, built with the `CELL 4.1.2.7`
toolchain, and it shares nothing with the collection but the engine.

The two builds of the same game differ in the size of their text — 640 bytes
for Ratchet & Clank, 640 for Going Commando — and in the addresses they
carry, which is what one expects of two builds of one source.

## The save paths, and what they do not say

The programs keep the paths of their save data, and those paths carry a
PlayStation 2 title id:

| Program | Save path |
|---|---|
| `RC2` — Going Commando | `/BESCES-51607RATCHET/save%d.bin` |
| `RC3` — Up Your Arsenal | `/BESCES-50916RATCHET/save%d.bin` |

`51607` is the PlayStation 2 id of **Going Commando**, and the path proves it:
`rc2` carries the trophy set of the title whose `PARAM.SFO` says
`Ratchet & Clank™: Going Commando`.

But `50916` is **not** the id of Up Your Arsenal alone: the standalone
`Ratchet: Deadlocked` uses the same directory. The remasters share the save
system, and the path names the *directory*, not the game. So a save path
identifies a game only when it is used by one game alone — which is the
exception, not the rule, and it has to be measured each time.

**This is the anchor of the naming**, and it is a narrow one:

| Our program | The original | The sibling project |
|---|---|---|
| `RC2` — Going Commando | `SCES-51607` | `rac2-gc-decomp` |
| `RC3` — Up Your Arsenal | the shared `SCES-50916` | `rac3-uya-decomp` (PAL) |
| `RC1` — Ratchet & Clank | the 2002 original | `rac1-decomp`, `Lombyte` |

The names of the sibling projects are a **hypothesis source**: they say what
to look for, and they make a proposal cheap. They are never the proof — see
[NAMING.md](NAMING.md) for why an address does not carry a name from one
build to another.

## The engine's own symbols

One engine symbol is readable in the data of the three games:

```
rt_mempool_check_integrity_
```

The `rt_` prefix is the engine's own namespace, and it is what a name of the
engine looks like. The rest of the engine's names are in the assets, not in
the code: the game's text, the weapon names and the level names live in the
banks and the dialogue files of the disc.

## What the engine identity gives the naming

1. **The vocabulary source is known.** The three programs are the PlayStation 3
   versions of games the sibling projects have already worked on, and the save
   paths prove which original each one is.
2. **The date is known.** An engine of the 9th of March 2011 tells which
   branch of the engine the sibling's PlayStation 2 work corresponds to.
3. **The build of each program is known.** The collection and the standalone
   titles are two builds of the same game, and their texts differ by hundreds
   of bytes. A name proved on one of them is a hypothesis on the other, and the
   two are not interchangeable.

## How to read a name

The naming of this project is a chain, and every link of it is measured:

```
the engine's strings  ->  the code that touches them  ->  the name
                                                     ->  the source
                                                     ->  the bytes
```

The last link is the one that decides: a name is a fact when the source
reproduces the retail bytes. Everything before it is a hypothesis written
down, and the hypotheses are published so that the next person does not have
to make them again.
