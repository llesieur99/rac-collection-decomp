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
| `size` | the length of the body, in bytes |
| `name` | the proposed name, or the placeholder `func_<address>` |
| `state` | `unbounded`, `bounded`, `named`, `nonmatching` or `matching` |
| `evidence` | what proves the boundary and the name |

`config/functions.tsv` holds the machine-readable form, one row per
function, tab separated. It is **measured** by
[`tools/build_catalogue.py`](../tools/build_catalogue.py), never typed.

## Recovering a boundary

The retail programs are stripped: there is no symbol table and no readable
section name. A boundary has to be **proved** by the bytes.

### The start

Two independent methods, and only the addresses that **both** agree on are
kept:

* **the prologue** — the PS3 SDK's functions open with a fixed pattern: the
  stack pointer is moved down with `stdu r1, -N(r1)`, and the link register
  is saved with `mflr r0` and `stw r0, 0x10(r1)`;
* **the call** — every `bl` (branch and link) names an address the program
  calls, and a called address is a function.

The two methods are independent: one reads the shape of the code, the other
the references of the code. An address that only one of them sees is a
**candidate**, not a function, and it is not counted.

### The end

The function ends at the **return that no path falls through from**. The
walk follows the branches, stops at an indirect jump, and does not leave the
function: a branch that goes outside is a tail call, and the function ends
where the branch is.

The tool reports how it ended: `return`, `branch`, `indirect` or `limit`.

## The result

| Program | Functions | Of which the end is a return |
|---|---|---|
| `EBOOT` — the collection launcher | 1,290 | 1,077 |
| `RC1` — Ratchet & Clank (2002) | 3,054 | 2,591 |
| `RC2` — Going Commando | 9,884 | 8,383 |
| `RC3` — Up Your Arsenal | 6,711 | 5,677 |
| **Total** | **20,939** | **17,728** |

The names are not known yet, so every function carries the placeholder of its
address. The state of every one of them is `bounded`: the extent is known and
the evidence is recorded, but the name is a hypothesis.

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
0x00010220:  7C0803A6  mflr r1              the epilogue
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
  There are 66 such cases in the launcher.* **A boundary that is only "the next known boundary"** is provisional, and it
  is recorded as such.

## The next step

The names. The engine is shared by the three titles, and the sibling
projects have already recovered a good part of its vocabulary: a name
recovered on one title is a hypothesis until the others confirm it.
