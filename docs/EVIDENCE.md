# The evidence standard

This project accepts a claim only when it is backed by a measurement that
someone else can repeat. What follows is what counts as evidence, what does
not, and how a claim is written down.

## What counts as a proof

A function matches when **all** of the following hold:

1. the **body** is complete: the compiled bytes cover the whole retail body,
   from its first byte to its last, with no gap and no overlap;
2. the **placement** is right: the compiled body lands at the retail address,
   at the retail alignment, in the retail segment;
3. the **bytes** are identical: every byte of the compiled body equals the
   corresponding retail byte;
4. the **program** still matches: the complete program, assembled with the
   new body in place of the old one, hashes to the pinned retail hash;
5. the **semantics** are the retail semantics: the source expresses what the
   retail code does, bugs included.

Point 5 is not decoration. A function that compiles to the right bytes by
accident, or by a trick that has no counterpart in the original source, is not
a match; it is a coincidence, and it does not survive the next function.

## What does not count

* **Compiling.** A successful build proves nothing about the bytes.
* **Matching a few instructions.** A prefix that matches says that the
  beginning is right. It says nothing about the end.
* **Comparing masked bytes.** Ignoring a byte that differs is the opposite of
  a proof.
* **A guessed boundary.** A "function" that starts at the next symbol, or at
  the next alignment, is an interval, not a function.
* **An assembly fallback.** Hand-written assembly that reproduces the bytes
  keeps the baseline intact but earns no credit in C.
* **A single compiler sample.** One match does not qualify a compiler
  profile; the profile must hold across the functions that use it.
* **A name that sounds right.** A name is a hypothesis until the code, its
  callers or a string it references proves it.

## The states of a function

| State | Meaning |
|---|---|
| `unbounded` | nothing is known about where it starts or ends |
| `bounded` | the extent is known, and the evidence is recorded |
| `named` | the extent and the name are both backed by evidence |
| `nonmatching` | authored, but the bytes do not match |
| `matching` | all five points of the proof hold |

Only `matching` functions live in `src/`. A `nonmatching` attempt that is
worth keeping lives in `nonmatching/`, indexed by function.

## The evidence the code carries

The naming evidence of a function is what the analysis of the code finds:

| Evidence | What it gives |
|---|---|
| the strings it touches | the *subject* of the function: a name, a format string, a file name, a message |
| the functions it calls | its *role*: a getter, a setter, a parser, a dispatcher |
| the functions that call it | its *role* seen from the other side |
| the data it reads and writes | the *state* it works on |

The evidence is measured, and it is published: it is research metadata, and it
carries no game bytes.

### The strings

The strings of the program are in the data, and the code points at them. The
tool that reads the references is
[`tools/strings_xref.py`](../tools/strings_xref.py), and what it measures is
worth stating, because the addressing of the PPU is not the addressing of a
classic 32-bit PowerPC:

* **the address of a string is built in two instructions** — `lis r3, hi` and
  `addi r3, r3, lo`, or `addic`, or a load with an immediate offset — and the
  two halves are often more than a dozen instructions apart, because the
  compiler reuses the registers. The tool therefore follows the value of the
  registers, not a window of instructions: a register keeps its value until
  an instruction writes it.
* **a string of C is terminated by a NUL**, and that is what tells it from a
  sequence of bytes that only looks like text. The sections that are
  allocated but **not** executable hold the data; the code is excluded.
* **the game keeps some of its messages in a table of pointers**, and the
  code points at the table. The tool follows one level of pointer.
* **the owner of a reference is the function whose control flow reaches
  it**, not the function whose extent covers it: a function whose blocks are
  scattered — a jump table, a cold block the compiler moved — owns the
  instructions of those blocks too.

The result is in [config/evidence.tsv](../config/evidence.tsv): **1,518
functions** of the release touch a string, out of 20,939.

| Program | Functions with a string |
|---|---|
| `EBOOT` — the collection launcher | 181 |
| `RC1` — Ratchet & Clank (2002) | 146 |
| `RC2` — Going Commando | 477 |
| `RC3` — Up Your Arsenal | 714 |

The strings are the engine's and the game's own: `CS_INIT`, `map level 0`,
`sky texs`, `rc2/ps3data/level%d/audiowad/speech[%d].xvag`, `WARNING, CAN
ONLY HAVE 20 CONNECTORS IN ONE ELECTROLYZER PUZZLE`.

**What is not reached.** The engine's *assert* messages carry the source file
and the line — `j:/Ratchet/Source/PS3/cell/samples/common/gcmutil/old/
texture.cpp:91 p != NULL` — and they are the best naming evidence there is.
They are in the data, in a table of the SDK, and the table is not reached by
the addresses the tool reads: the table is filled by the module's start-up,
and the game refers to the assertions by their number. Recovering them is
the next piece of work.

## Writing a claim down

Every claim records:

* the **program** it belongs to (`EBOOT.BIN`, `RC1.ppu.self`, …);
* the **address** and the **size** of the body;
* the **evidence** for the boundary: which instruction proves the start, which
  one proves the end;
* the **evidence** for the name: a symbol, a caller, a string, a reference;
* the **placement** the claim was measured at;
* the **first difference**, when the claim does not match;
* the **reopening condition**: what has to change for the claim to be tried
  again.

A claim without a reopening condition is a dead end, not a result.

## Recording the measurements

The hashes in `config/target.json` are **measured** by
`tools/measure_target.py`, and the manifest of a tree is produced by
`tools/manifest.py`. Both are reproducible: run them again, get the same
numbers, or find out that the copy is not the one that was measured.

A number that cannot be measured — the content id, for instance, which is
encrypted — is labelled as derived. It is never presented as measured.
