# The correspondence between the builds

An address is not a portable name, and the project has measured why: two
builds of the same program lay their code out differently. But a *function* is
portable — and the relation between two builds can be **measured** instead of
guessed.

This document records that relation. The table is in
[config/correspondence.tsv](../config/correspondence.tsv), one row per matched
pair of functions, and the summary is in
[config/builds.tsv](../config/builds.tsv).

## The two relations

The release and the series give two different relations, and both are needed.

| Relation | Between | What it is |
|---|---|---|
| **the same game, two builds** | the collection's copy ↔ the standalone PlayStation Network title | two builds of one program: the same source, the same compiler, a different link |
| **the same engine, three games** | `rc1` ↔ `rc2` ↔ `rc3` | three games that share the engine: the engine's own code is the same in the three |

The first relation is what carries a name from the collection to the
standalone title. The second is what carries a name from one game to the
others — and it is the one that pays.

## How the relation is measured

An address says nothing, so the relation is measured on the **body** of the
functions.

1. **The boundaries** are recovered in each build on its own, with the two
   independent methods of [CATALOGUE.md](CATALOGUE.md): the SDK's prologue and
   the calls that land on an address.
2. **Every function gets a signature**: the sequence of its instructions, with
   the opcodes, the registers and — in the strictest form — the immediates.
   The immediates are the offsets of the data, and the data of two builds does
   not sit at the same place, so the strictest signature fails on the data.
3. **The signature is matched** against the signatures of the other build.
   When several functions share a signature, two independent facts break the
   tie: the **size** of the body, which does not change when the program is
   rebuilt, and the **order** of the addresses, which the linker keeps almost
   everywhere.
4. **The match is checked by the bytes**: the share of the instructions that
   are literally the same in the two builds. It is the measure of how much of
   the function the rebuild left untouched, and it is published in the table.

The tool is [`tools/build_correspondence.py`](../tools/build_correspondence.py).

## The result

### The same game, two builds

| Pair | Functions | Matched | Same size | Same bytes | Median identity |
|---|---|---|---|---|---|
| `rc1` ↔ `NPUA80643` | 3,054 | **3,047** (99 %) | 3,047 | 37 % | 95.2 % |
| `rc2` ↔ `NPUA80644` | 9,884 | **9,873** (99 %) | 9,873 | 13 % | 93.0 % |
| `rc3` ↔ `NPUA80645` | 6,711 | **6,691** (99 %) | 6,691 | 24 % | 93.7 % |

The two builds of one game hold **the same number of functions** — 3,054,
9,884 and 6,711, to the unit — and the tool matches 99 % of them, every
matched pair having **exactly the same size**.

The addresses, on the other hand, are not the same: the shift is constant
inside a block of code and changes from block to block — 77 blocks for
`rc1`, 227 for `rc2`, 140 for `rc3`. That is the linker of the other SDK
placing the pieces of the program elsewhere, and it is why an address is not
a name.

### The same engine, three games

| Pair | Matched | Same size | Same bytes | Median identity |
|---|---|---|---|---|
| `rc1` ↔ `rc2` | 1,242 of `rc1`'s 3,054 (40 %) | 1,242 | **56 %** | **100 %** |
| `rc2` ↔ `rc3` | 2,182 of `rc2`'s 9,884 (22 %) | 2,182 | 33 % | 95.7 % |
| `rc1` ↔ `rc3` | 1,264 of `rc1`'s 3,054 (41 %) | 1,264 | **54 %** | **100 %** |

**1,226 functions of `rc1` have a counterpart in all three other builds** at
once: the standalone title, `rc2` and `rc3`. They are the engine's own code,
and the instructions of more than half of them are **literally the same bytes**
in the three games.

That is the important number. A name proved on the engine's code of one game
is not a guess on the engine's code of another: the body is the same body,
and the body gate would reproduce the same bytes at the other address.

## What a name is worth across a correspondence

| | The name travels | What it is worth |
|---|---|---|
| the same game, two builds | the address, the code, the subject | a proposal on the other build, to be proved there |
| the same engine, two games, **same bytes** | the body itself | the body gate reproduces the same bytes at the other address: the name is proved twice |
| the same engine, two games, different bytes | the subject, the role | a proposal, to be proved on the second game |

The tool that carries the name over is
[`tools/propose_name.py`](../tools/propose_name.py):

```sh
python tools/propose_name.py --program collection-RC1 --address 0x000128B8
```

```
collection-RC1 0x000128B8
  -> NPUA80643            0x000128B8 size    644   96.3% of the instructions are the same  (ops+size)
  -> collection-RC2       0x00010408 size    644   86.3% of the instructions are the same  (ops+size)
  -> collection-RC3       0x00010718 size    644   86.3% of the instructions are the same  (ops+size)
```

The share of the instructions that are the same is the confidence of the
proposal: 96 % means the two bodies are the same function with a different
address and a different data layout; 100 % means the same bytes, and the
proof on one build is the proof on the other.

With `--name` and `--write`, the proposal is written in the catalogue with the
state `proposed` and the evidence that says where it comes from. A proposal
is not a fact: only the body gate makes a name a fact.

## The limits

* **A correspondence is not a proof.** It says that two functions are the same
  function. It does not say what the function is called.
* **The ambiguous pairs are marked.** When several candidates share the
  signature and the size and the bytes do not decide, the method ends with a
  `?` — 106 pairs for `rc1`, 4,893 for `rc2`, 411 for `rc3`. They are
  proposals like the others, but weaker ones, and the table says so.* **The functions of the launcher are not in the table.** The `EBOOT` is the
  collection's own module; the standalone titles have no counterpart for it.
* **A function that the rebuild changed a lot may not be found at all.** 7
  functions of `rc1`, 11 of `rc2` and 20 of `rc3` have no counterpart in the
  standalone title. They are the functions the rebuild touched the most.
