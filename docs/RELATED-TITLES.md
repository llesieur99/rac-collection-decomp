# The related titles

The three titles of the collection also exist as **separate PlayStation
Network titles**, packaged as retail `.pkg` files. Each of them is a second,
independent reference for the same game: another build of the same program,
with another content id and another NPDRM key revision.

This document records what was measured on them, and the one thing that was
got wrong before it was measured.

## The five titles

| Content id | Title | Trophy set | In the collection |
|---|---|---|---|
| `UP9000-NPUA80643_00-RC1REMASTER00100` | **Ratchet & Clank™** (2002) | `NPWR02335` | **`rc1`** |
| `UP9000-NPUA80644_00-RC2REMASTER00100` | Ratchet & Clank™: Going Commando | `NPWR02346` | **`rc2`** |
| `UP9000-NPUA80645_00-RC3REMASTER00100` | Ratchet & Clank™: Up Your Arsenal | `NPWR02347` | **`rc3`** |
| `UP9000-NPUA80646_00-RC4REMASTER00101` | Ratchet: Deadlocked™ | `NPWR02348` | — |
| `UP9000-NPUA80965_00-TOOLSOFDESTRUCT1` | Ratchet and Clank® **Future: Tools of Destruction™** | — | — |

The collection is the **trilogy**: the first game, Going Commando and Up Your
Arsenal. Ratchet: Deadlocked and Tools of Destruction are **not** in it, and
neither is A Crack in Time.

**The names of the collection are not the numbers of the series.** The
collection numbers its own titles `rc1`, `rc2` and `rc3`, and its `rc1` is the
*first* game of the series, not the sixth. That was measured: the standalone
title whose content id is `UP9000-NPUA80643_00-RC1REMASTER00100` carries the
name `Ratchet & Clank™` in its `PARAM.SFO`, the trophy set `NPWR02335`, and an
executable of exactly the size of the collection's `rc1` — 9,764,896 bytes.

The trophy sets are the proof that needs no interpretation: the collection's
`TROPDIR` holds `NPWR02335`, `NPWR02346` and `NPWR02347`, and those are
exactly the three sets of the three remasters.

## What was measured

| | The collection | The standalone title |
|---|---|---|
| `rc1` / `NPUA80643` | 9,764,896 bytes | 9,764,896 bytes |
| `rc2` / `NPUA80644` | 21,070,000 | 21,069,872 |
| `rc3` / `NPUA80645` | 13,337,168 | 13,337,168 |

The two builds of one game have the same size to the byte for `rc1` and
`rc3`, and differ by 128 bytes for `rc2`. The *text* differs by 640 bytes in
each case: the programs are the same source, built with slightly different
settings.

The toolchain differs too, and it is the clearest sign of a different build:

| Program | Compiler |
|---|---|
| the collection's three titles | `GCC: (GNU) 4.1.1 (SDK400, $Rev: 3538 $)` |
| `NPUA80644`, `NPUA80645` | `GCC: (GNU) 4.1.1 (SDK270, $Rev: 3019 $)` |
| `NPUA80965`, Tools of Destruction | `GCC: (GNU) 4.1.1 (CELL 4.1.2.7, RTTI, $Rev: 1826 $)` |

The collection's copies are the **newer** builds, and the standalone
Going Commando and Up Your Arsenal are the older ones. The Tools of
Destruction is a different game on an older toolchain still.

## Why the correction matters

The first reading of this project called the collection's `rc1` *Tools of
Destruction*, from the numbering of the series. The measurement says otherwise:
`rc1` is the first game, and Tools of Destruction is not in the collection at
all.

That is the rule of the project in one case: **a name is a hypothesis until
the code proves it**, and the same goes for the *program* a name belongs to.
Here the evidence was a `PARAM.SFO`, a trophy set and a file size, and it
overturned a name that had been written down from memory.

## Reading them

```sh
python tools/pkg.py inspect "path/to/the.pkg"
python tools/pkg.py list    "path/to/the.pkg" --pattern TROPDIR
python tools/measure_package.py --pkg "path/to/the.pkg" --out work/pkg.json
python tools/self_decrypt.py "path/to/EBOOT.BIN" --keys work/self-keys.json --rap work/<content id>.rap --out work/gc.elf
```

Hashing a whole package is optional: they run from 4 to 17 gigabytes, and
reading one of them over a network takes hours. The hash of the executable
is always computed, because that is the part the project measures.

## What is not published

No package, no extracted program, no licence file and no key material. The
repository keeps the content ids, the sizes, the hashes of the executables
and the module lists.
