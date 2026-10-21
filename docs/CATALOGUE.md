# The function catalogue

The catalogue is the index of the functions of the four programs: where they
are, how long they are, and what evidence backs the claim. It is the
reference that lets a contributor find the function they need without
re-deriving the whole program.

The catalogue is **not** a disassembly. It is a table of claims, each backed
by evidence, and it names a function only when the evidence is there.

## The columns

| Column | Meaning |
|---|---|
| `program` | which of the four executables the function belongs to |
| `address` | the virtual address of the first instruction |
| `size` | the length of the block the function occupies, in bytes |
| `instructions` | the number of instructions of the body |
| `name` | the proposed name, or the placeholder `func_<address>` |
| `state` | `unbounded`, `candidate`, `bounded`, `named`, `proposed`, `nonmatching` or `matching` |
| `evidence` | what proves the boundary and the name |

`config/functions.tsv` holds the machine-readable form, one row per
address, tab separated. It is **measured** by
[`tools/build_catalogue.py`](../tools/build_catalogue.py), never typed.

The `candidate` state marks the addresses that only one of the methods
sees. A candidate is published — the address is worth knowing — but it is
not a function, and the size the walk measures from it is **provisional**:
it is the block the walk covers, not a claim about the size of a function.

## Recovering a boundary

The retail programs are stripped: there is no symbol table and no readable
section name. A boundary has to be **proved** by the bytes.

### The start

Four independent signals, and only the addresses that **two** of them agree
on are functions:

* **the prologue** — the frame of the SDK: `stdu r1, -N(r1)`, with or
  without the save of the link register (`mflr r0`). The frame is not
  always the first instruction of the function: the compiler sometimes
  saves the link register first, and sometimes puts an instruction or two
  before the frame. The signal is recorded at the address where the
  prologue block **starts**, not at the address of the frame;
* **the call** — every `bl` (branch and link) names an address the program
  calls, and a called address is a function;
* **the entry** — the instruction that precedes the address does not fall
  through: it is a return, an unconditional branch or an indirect jump.
  The address then opens a new block, and a function opens with a new
  block;
* **the return** — the walk from the address ends on a `blr`. This is
  what confirms the prologue on its own: a frame in the middle of a
  function is not followed by the return of that function.

The signals are independent: one reads the shape of the code, one the
references of the code, one the control flow, one the end of the body. An
address that only one of them sees is a **candidate**, not a function, and
it is published as such.

The narrow method — the prologue of the SDK and the targets of the calls —
is still there, and it still reproduces the catalogue it produced before:
`tools/build_catalogue.py --narrow` writes it, row for row. It is the
baseline the extended method is measured against.

### The forms of the prologue

The prologue is not one shape. The measurement gives four, and the narrow
method misses three of them:

| Form | What it is | `EBOOT` | `RC1` | `RC2` | `RC3` |
|---|---|---|---|---|---|
| `frame+lr` | the frame, then the save of the link register | 3,286 | 7,338 | 16,904 | 14,411 |
| `frame` | the frame alone: the function has locals but calls nothing, so the link register is never saved | 167 | 401 | 811 | 535 |
| the link register first | the compiler saves the link register before the frame: the narrow method records the frame, one instruction after the entry | 348 | 949 | 949 | 964 |
| no frame at all | the leaf function: no locals, no call | 1,644 | 2,639 | 3,886 | 3,876 |

The first row is what the narrow method finds; the three others are what
it misses. The example of each is in the report of the measurement.

### The end

The function ends at the **return that no path falls through from**. The
walk follows the branches, stops at an indirect jump, and does not leave the
function: a branch that goes outside is a tail call, and the function ends
where the branch is.

Two bounds keep the walk honest, and both were needed:

* **the entry of the next function.** The walk stops as soon as it lands on
  the entry of another function: the flow has left the function, and the next
  one starts there. Without that bound the walk wanders into the code that
  follows — a branch that skips over a function lands in the middle of the
  next one — and reports an extent that covers half the program. It was
  measured: the extents of the catalogue summed to **78 gigabytes** before the
  bound, and to **6.7 megabytes** after it, for the same 20,939 functions.
* **the contiguous block.** The walk may reach further than the function —
  a jump table, or a block of data read as code. The extent of a function is
  the block of code that starts at its entry and that the walk covered: the
  `size` column is that block, and `instructions` counts the instructions in
  it.

The tool reports how the walk ended: `return`, `branch`, `entry`, `indirect`
or `limit`.

### The conditional branch that was never read

The walk followed **no conditional branch at all**, and the reason was a
single wrong constant. The test

```python
word & 0xFC000003 == 0x80000000
```

does not recognise a conditional branch: the opcode of `bc` is **16**, whose
top bits are `0x40000000`, and `0x80000000` is the opcode **32** — the
loads. The test matched 225,275 words of RC2, and **not one of them was a
conditional branch**.

The walk therefore followed the *target of a load* instead: an address read
out of an immediate, which lands in the **jump tables** of the text segment.
A word of a table, decoded as a call, named an address that no function
starts at, and the bound stopped the walk there. The extents of 368
functions were cut in two that way.

The fix reads the branch by its opcode, and the bound became sharper: a
target of a call stops the walk only when the flow **cannot fall into it** —
the same criterion as the *entry* signal, which gives **no false positive**
on the 3,299 targets that are not confirmed functions.

The coverage of RC2 went from 25,8 % of the text to **90,7 %**, the owned
code from 55,6 % to 92,1 %, the number of overlapping functions stayed at
**zero**, and the ends that are not proven went *down*, from 1,013 to 479.
The control outside the project held: 99,8 % of the matched functions still
have the same size in the two builds.

What the fix does **not** explain is the rest: 100 % of the returns that
are still not owned fall in a *hole* — a function that was never identified
— and not in a truncated extent.

## The population

The catalogue was measured, but the population was not. Every function ends
on a return, so the number of the returns of a program bounds the number of
its functions; and the functions the catalogue holds own on average **one**
return each, so the number of the returns is also a good estimate of the
number of the functions.

| Program | The text | `blr` | The conditional returns | The returns | The functions of the catalogue |
|---|---|---|---|---|---|
| `EBOOT` | 1,994,728 | 5,586 | 54 | 5,640 | 4,433 |
| `RC1` | 7,583,720 | 12,396 | 139 | 12,535 | 9,824 |
| `RC2` | 19,691,880 | 25,617 | 139 | 25,756 | 21,054 |
| `RC3` | 12,267,240 | 22,084 | 140 | 22,224 | 18,145 |
| **Total** | **41,537,568** | **75,683** | **472** | **76,155** | **53,456** |

The narrow catalogue held 21,054 functions for `RC2` against the 25,617
returns of the program: it knew **38 %** of the return sites. The extended
one holds 21,054 functions and owns 20,017 of the returns: **78 %**.

## The result

| Program | Functions | Of which the end is a return | Candidates |
|---|---|---|---|
| `EBOOT` — the collection launcher | 4,433 | 3,787 | 132 |
| `RC1` — Ratchet & Clank (2002) | 9,824 | 8,122 | 609 |
| `RC2` — Going Commando | 21,054 | 19,056 | 886 |
| `RC3` — Up Your Arsenal | 18,145 | 16,250 | 688 |
| **Total** | **53,456** | **47,215** | **3** |

The names are not known yet, so every function carries the placeholder of its
address. The state of every confirmed one is `bounded`: the extent is known
and the evidence is recorded, but the name is a hypothesis.

### The coverage

Two measures, both measured by
[`tools/ppu_census.py`](../tools/ppu_census.py): the **extent** is the sum of
the blocks the walk covers, and the **code owned** is the union of the
instructions the walk reaches — a function whose blocks are scattered owns
them all.

| Program | The extent, before | The extent, after | The code owned, before | The code owned, after |
|---|---|---|---|---|
| `EBOOT` | 245,056 (12.3 %) | 1,073,764 (53.8 %) | 141,081 (7.1 %) | 324,468 (16.3 %) |
| `RC1` | 923,776 (12.2 %) | 6,259,736 (82.5 %) | 531,237 (7.0 %) | 1,633,586 (21.5 %) |
| `RC2` | 3,258,292 (16.6 %) | 17,857,248 (90.7 %) | 2,345,425 (11.9 %) | 4,533,013 (23.0 %) |
| `RC3` | 2,626,700 (21.4 %) | 10,595,468 (86.4 %) | 1,355,267 (11.1 %) | 2,717,904 (22.2 %) |
| **Total** | **7,053,824 (17.0 %)** | **35,786,216 (86.2 %)** | **4,373,010 (10.5 %)** | **9,208,971 (22.2 %)** |

The "before" column is the narrow method; the "after" column is the wide
method **with the conditional branch read by its opcode** — the fix described
above is what took the extent of `RC2` from 25,8 % to 90,7 %.

The percentages are of the text segment of the program. It holds more than
code — the tables of the engine and of the game are in it — so they are a
lower bound of the share of the code that is covered.

### The false positives

Widening the detection raises the risk of false positives, and the risk is
measured, not asserted. Three counts:

* **the extent is eight bytes or less** — a function of one or two
  instructions. The narrow catalogue has none; the extended one has some,
  and the review of a sample shows the real ones are the stubs of the
  compiler (`li r3,0` then `blr`, one per `return 0;` of the source);
* **the extents overlap** — two functions that claim the same bytes. There
  are **none**, before and after;
* **the end is not proven** — the walk ended on the next entry or gave up,
  instead of on a return or a tail call.

| Program | Before: short, overlapped, unproven | After: short, overlapped, unproven |
|---|---|---|
| `EBOOT` | 0, 0, 58 (4.5 %) | 189, 0, 258 (6.1 %) |
| `RC1` | 0, 0, 100 (3.3 %) | 595, 0, 552 (6.0 %) |
| `RC2` | 0, 0, 428 (4.3 %) | 646, 0, 1,013 (5.0 %) |
| `RC3` | 0, 0, 209 (3.1 %) | 788, 0, 812 (4.7 %) |

The share of the rows whose end is not proven grows from 3 to 5 %: that is
the price of the wider detection, and it is the honest measure of it.

## Reading a boundary

The claim can be checked by reading the bytes.
[`tools/ppu_disasm.py`](../tools/ppu_disasm.py) prints them:

```sh
python tools/ppu_disasm.py work/eboot.elf --start 0x10200 --count 11
```

```
0x00010200:  F821FF91  stdu r1,-111(r1)     the frame of the SDK
0x00010204:  7C0802A6  mflr r0              the link register is saved
0x00010208:  F8010080  stw r0,128(r1)
0x0001020C:  480045A5  bl 0x000147B0        a call
0x00010210:  60000000  nop
0x00010214:  4800460D  bl 0x00014820        a call
0x00010218:  60000000  nop
0x0001021C:  E8010080  .long 0xE8010080     an extension of the SDK
0x00010220:  7C0803A6  mtlr r0              the epilogue
0x00010224:  38210070  addi r1,r1,112       the frame is torn down
0x00010228:  4E800020  blr                  the return
```

That is a textbook function of the SDK: a frame, two calls, an epilogue and a
return. The start at `0x10200` is confirmed by the prologue **and** by the
call that lands there; the end at `0x1022C` is confirmed by the `blr` that no
path falls through from.

## The limits

* **The names of the sections are lost.** The string table of the ELF is
  encrypted and is not covered by any encrypted section; only the names of the
  modules are readable. A function boundary can never be read off a section
  name here.
* **One instruction of the SDK is not decoded**: `0xE8010080`, which appears
  between the last call and the epilogue. It is most likely the far form of
  `bl`, and it is the reason the call method may miss some targets. The
  prologue method covers them.
* **A function that ends by an indirect jump** — a tail call through a
  register — cannot be bounded by the walk; the extent is then provisional.
  There are 66 such cases in the launcher.* **A boundary that is only "the next known boundary"** is provisional, and
  it is recorded as such.
* **A function that is only called through a pointer** is not seen by the
  call method. The prologue method sees it when it has a frame; a leaf
  function reached only through a pointer stays a candidate.
* **The correspondence table was re-measured on the wide catalogue.** The
  standalone copy of each game is another program, and the functions match
  it one by one, on the body and never on the address: 99 % of them, with
  the same size. See [CORRESPONDENCE.md](CORRESPONDENCE.md).

## The next step

The names. The engine is shared by the three titles, and the sibling
projects have already recovered a good part of its vocabulary: a name
recovered on one title is a hypothesis until the others confirm it.
