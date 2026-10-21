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
| `RC1` — Tools of Destruction | `rt_udp 3.05.201103091800` |
| `RC2` — Going Commando | `rt_udp 3.05.201103091800` |
| `RC3` — Up Your Arsenal | `rt_udp 3.05.201103091800` |

The stamp dates the engine: **9 March 2011**. The launcher carries none, which
is what one expects of it: it is the graphics and menu module of the
collection, not a game.

The stamp is read by [`tools/engine_identity.py`](../tools/engine_identity.py),
and the result is in [config/engine.tsv](../config/engine.tsv).

## The stamp that is not there

The standalone PlayStation Network titles were measured the same way:

| Program | Stamp |
|---|---|
| Going Commando, `NPUA80644` | `rt_udp 3.05.201103091800` |
| Tools of Destruction, `NPUA80965` | **none** |

That is not a detail. The standalone Tools of Destruction was built with the
`CELL 4.1.2.7` toolchain, while the collection's copy of the same game was
built with the SDK 400 — and only the collection's copy carries the engine
stamp of 2011. **The collection ships a rebuilt Tools of Destruction**, and the
rebuild is newer than the standalone title.

It is the same conclusion the compiler measurement gave, from a completely
different direction: the collection's `rc1` and the standalone `NPUA80965`
are two builds of the same game, and the collection's one is the newer.

## The save paths, and the anchor of the naming

The programs keep the paths of their save data, and those paths name the
**original PlayStation 2 titles**:

| Program | Save path | The original |
|---|---|---|
| `RC2` — Going Commando | `/BESCES-51607RATCHET/save%d.bin` | **SCES-51607** |
| `RC3` — Up Your Arsenal | `/BESCES-50916RATCHET/save%d.bin` | **SCES-50916** |

`BESCES-51607` is the European PlayStation 2 Going Commando, and `BESCES-50916`
the European PlayStation 2 Up Your Arsenal. The PlayStation 3 builds of the
collection still save under the names of their PlayStation 2 originals — the
players' saves are compatible, and the engine says so in its own paths.

`RC2` also names `BESCES-50916RATCHET`: the two titles share the save
system, and each one can read the other's directory.

**This is the anchor of the naming.** The sibling projects have already
recovered a good part of this engine's vocabulary, on the PlayStation 2
originals:

| Our program | The original | The sibling project |
|---|---|---|
| `RC2` | `SCES-51607` — Going Commando | `rac2-gc-decomp` |
| `RC3` | `SCES-50916` — Up Your Arsenal | `rac3-uya-decomp` (PAL) |
| `RC1` | Tools of Destruction | `rac-sac-decomp` for the engine, `rac5-sm-decomp` for the tools |

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
3. **The build of each program is known.** The collection's `rc1` is a rebuild
   of Tools of Destruction; the standalone title is the older one. A name
   proved on one of them is a hypothesis on the other, and the two are not
   interchangeable.

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
