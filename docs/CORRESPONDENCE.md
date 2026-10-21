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

1. **The boundaries** are recovered in each build on its own, with the four
   independent signals of [CATALOGUE.md](CATALOGUE.md): the prologue of the
   SDK, the targets of the calls, the entries of the control flow and the
   returns of the walk. Two of them have to agree.
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
| `rc1` ↔ `NPUA80643` | 9,596 | **9,567** (99 %) | 9,567 | 53 % | **100 %** |
| `rc2` ↔ `NPUA80644` | 20,561 | **20,517** (99 %) | 20,517 | 28 % | 94 % |
| `rc3` ↔ `NPUA80645` | 17,860 | **17,785** (99 %) | 17,785 | 35 % | 95 % |

The two builds of one game hold **the same number of functions** — 9,596 and
9,592, 20,561 and 20,560, 17,860 and 17,858 — and the tool matches 99 % of
them, every matched pair having **exactly the same size**.

The addresses, on the other hand, are not the same: the shift is constant
inside a block of code and changes from block to block — 385 blocks for `rc1`,
719 for `rc2`, 558 for `rc3`. That is the linker of the other SDK placing the
pieces of the program elsewhere, and it is why an address is not a name.

### The same engine, three games

| Pair | Matched | Same size | Same bytes | Median identity |
|---|---|---|---|---|
| `rc1` ↔ `rc2` | 5,504 of `rc1`'s 9,596 (57 %) | 5,504 | 56 % | **100 %** |
| `rc2` ↔ `rc3` | 7,933 of `rc2`'s 20,561 (38 %) | 7,933 | 42 % | 97 % |
| `rc1` ↔ `rc3` | 5,508 of `rc1`'s 9,596 (57 %) | 5,508 | 55 % | **100 %** |

**5,454 functions of `rc1` have a counterpart in the three other builds at
once**: the standalone title, `rc2` and `rc3`. They are the engine's own code,
and more than half of those pairs are **literally the same bytes**.

That is the important number. A name proved on the engine's code of one game
is not a guess on the engine's code of another: the body is the same body,
and the body gate would reproduce the same bytes at the other address.

## The relation with the PlayStation 2

The PlayStation 2 versions of the three games are the **originals** the
PlayStation 3 builds are ports of, and the sibling project has already
recovered a good part of their vocabulary: 3,888 functions of the PlayStation
2 games, 773 of them with the name of the source file they come from.

The two versions cannot be matched by the instructions — one is a MIPS
PowerPC-like processor, the other a PowerPC — but they can be matched by
**what they say**: the same literal in the same function.

The key is a **distinctive message**: a string long enough, and rare enough,
to name one function and one only. The control is measured: a pair of
functions picked at random shares a message 0,18 % of the time.

| Program | Functions of the PS3 | Verified pairs | Named |
|---|---|---|---|
| `RC1` | 10,160 | **27** | 10 |
| `RC2` | 21,387 | **10** | 5 |
| `RC3` | 18,572 | **9** | 3 |
| `EBOOT` | 4,985 | **2** | 0 |

**48 functions of the PlayStation 3 builds are matched with confidence with
a function of the PlayStation 2**, and 18 of them carry a name of source that
can be used (`gameplay/state/do_space_transition`, `ui/menus/draw_prompt_box`,
`rendering/draw_ties_2`, `storage/memory_card/memcard_get_data_size`…). The
table is in [config/proposals.tsv](../config/proposals.tsv).

**The ceiling is measured, not conjectured.** There are 380 messages common
to the two versions, 88 of them are read by the code of both, and they give
16 distinct pairs. The PlayStation 3 build reads two and a half times more
messages — the SDK is newer — and the PlayStation 2 decompilation names only
773 of its 3,888 functions.

### The exact key, and why it is thin

The PlayStation 2 builds carry the **same triplet** as the PlayStation 3 one:
the name of the source file and the line, passed at the site of the call.
The tool that reads it on the MIPS side is
[`tools/mips_assert_xref.py`](../tools/mips_assert_xref.py), and it measures
**1,141 triplets** across the three PlayStation 2 games.

The join on the triplet is exact where it exists — **no collision at all**
on the 1,141 triplets of the PlayStation 2, against 27 on the PlayStation 3
side, where the assertions live in headers — and it is verifiable: the
control on the PlayStation 2 alone (the core against the overlays) gives 76
pairs and **76 of them agree** with the sibling project's catalogue.

**And it gives almost nothing.** The exact join on (file, line) gives
**zero** pairs: the retail PlayStation 2 build compiles out nearly all of
its assertions, and where it kept them, **the port moved the line by six** —
the same shift in both ported games, and the only one that pairs the whole
block. With that shift, five pairs.

The negative control says the same thing: of the 230 assertions of the
PlayStation 3 build, **none** matches a PlayStation 2 triplet on the line,
and three match on the file name alone — and those three are the function
this repository had already named, on its own evidence,
`hud_print_moby_debug_info`.

So the triplet is the more precise key and the less productive one. It is
published because it is exact, and because it is the measure of how much the
PlayStation 2 build can still say.

Two keys were measured and rejected, and they are worth naming: the **order**
of the functions (the drift between two anchors is as large as the drift
between the two builds) and the **graph of the calls** (38 pairs proposed, at
least six of them demonstrably wrong).

## What a name is worth across a correspondence

| | The name travels | What it is worth |
|---|---|---|
| the same game, two builds | the address, the code, the subject | a proposal on the other build, to be proved there |
| the same engine, two games, **same bytes** | the body itself | the body gate reproduces the same bytes at the other address: the name is proved twice |
| the same engine, two games, different bytes | the subject, the role | a proposal, to be proved on the second game |
| the PlayStation 2, same message | the name of the source | a proposal, with the message as the proof that it is the same function |

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
  `?` — 1,195 pairs for `rc1`, 8,490 for `rc2`, 2,331 for `rc3`. They are
  proposals like the others, but weaker ones, and the table says so.
* **The functions of the launcher are not in the table.** The `EBOOT` is the
  collection's own module; the standalone titles have no counterpart for it.
* **A function that the rebuild changed a lot may not be found at all.** 32
  functions of `rc1`, 48 of `rc2` and 100 of `rc3` have no counterpart in the
  standalone title. They are the functions the rebuild touched the most.
* **The PlayStation 2 relation is thin, and that is the measure.** 48
  functions out of 55,104: 0,09 %. The engine is shared, but the *messages*
  that name its functions were compiled out of the retail builds, and the
  strings that remain are the ones the game prints.
