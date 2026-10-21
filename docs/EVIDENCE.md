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
| `candidate` | one method sees the address and the others do not: it may be a function, and it is not counted as one |
| `bounded` | the extent is known, and the evidence is recorded |
| `named` | the extent and the name are both backed by evidence |
| `nonmatching` | authored, but the bytes do not match |
| `matching` | all five points of the proof hold |

Only `matching` functions live in `src/`. A `nonmatching` attempt that is
worth keeping lives in `nonmatching/`, indexed by function.

The `candidate` state is the one the catalogue uses for the addresses the
boundary methods do not agree on.  A candidate is published — the address
is worth knowing — but it is not a function, and the extent that the walk
covers from it is **provisional**: it is the block the walk reaches, not a
claim about the size of a function.

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

The result is in [config/evidence.tsv](../config/evidence.tsv): **3,020
functions** of the release touch a string, out of the 51,463 functions of the
catalogue.

Two details of the reading, both measured:

* **the text of a string starts at the address the code points at**, not at
  the beginning of the printable run. The game keeps its messages in records
  whose first byte is a tag, and returning the whole run put a stray
  character at the head of 16 % of the references.
* **the tables are written by the csv module**, and not by a join: a message
  of the game may hold a double quote, and a table that a quote breaks is a
  table that lies — 2,042 lines were read as 760.

| Program | Functions with a string |
|---|---|
| `EBOOT` — the collection launcher | 500 |
| `RC1` — Ratchet & Clank (2002) | 340 |
| `RC2` — Going Commando | 635 |
| `RC3` — Up Your Arsenal | 1,204 |

The strings are the engine's and the game's own: `CS_INIT`, `map level 0`,
`sky texs`, `rc2/ps3data/level%d/audiowad/speech[%d].xvag`, `WARNING, CAN
ONLY HAVE 20 CONNECTORS IN ONE ELECTROLYZER PUZZLE`.

### The call graph

The role of a function is also read from the code: the functions it calls
and the functions that call it. The tool is
[`tools/callgraph.py`](../tools/callgraph.py), and the graph is in
[config/evidence.tsv](../config/evidence.tsv): **35,703** functions of the
release have a call graph, **27,856** of them are called.

The owner of a call is the function whose **control flow** reaches it, not
the function whose extent covers it: the same rule as the strings.

### The condition of an assert

A retail assert is not one call but **three**: the first carries the file
and the line, the second the condition, the third the free text. The tool
that reads them is [`tools/assert_cond.py`](../tools/assert_cond.py), and it
is what turns an assert into a name: the condition of an assert of the lobby
names the class, the member and the method — `LobbyNet::RoomMgr::
RefreshPlayerList() Error (MEDIUS: %d)` is a name and an address at once.

**What is not reached.** The engine's *assert* messages carry the source file
and the line — `j:/Ratchet/Source/PS3/cell/samples/common/gcmutil/old/
texture.cpp:91 p != NULL` — and they are the best naming evidence there is.
They are in the data, in a table of the SDK, and the table is not reached by
the addresses the tool reads: the table is filled by the module's start-up,
and the game refers to the assertions by their number. Recovering them is
the next piece of work.

### The assert messages

The assert messages are the strongest naming evidence the program carries: a
message names the **source file** and the **line** inside it, so a function
that asserts says where it comes from.

The mechanism was measured, and it is not a table: the code calls a logging
function with the **triplet (file, line, condition)**, or with a single
message that already carries the file and the line.

```
0x010D4358:  3C600124  addis r3,r0,0x0124
0x010D435C:  3C800124  addis r4,r0,0x0124
0x010D4360:  306394AC  addic r3,r3,0x94AC   ; the condition
0x010D4364:  38A00167  li    r5,359         ; the line
0x010D4368:  308494F4  addic r4,r4,0x94F4   ; "j:/Ratchet/.../IMSeqMem.cpp"
0x010D436C:  48000EC5  bl    0x010D5230    ; the logger
```

Two details of the addressing of the PPU are worth writing down, because
they are what makes the measurement possible:

* the low half of an address is added **with its sign**: when the offset has
  its top bit set, the compiler takes the high half one greater and codes the
  low half negative;
* `r0` reads as **zero** in the idiom, even where the code has just put the
  link register there: the compiler uses `r0` as the null base. The control
  is statistical — on RC2, 366 of the addresses built that way land exactly
  on the first byte of a string, against 24 when `r0` is read as the link
  register.

The tool is [`tools/assert_xref.py`](../tools/assert_xref.py), and the table
is in [config/asserts.tsv](../config/asserts.tsv): **707 asserts, 246
functions, 56 source files**. The criterion that keeps the false positives
out is the **line**: a call that names a source file but no line is a log
call that happens to carry a file name.

| Program | Asserts | Functions | Source files |
|---|---|---|---|
| `EBOOT` — the collection launcher | 17 | 9 | 6 |
| `RC1` — Ratchet & Clank (2002) | 3 | 3 | 2 |
| `RC2` — Going Commando | 5 | 4 | 3 |
| `RC3` — Up Your Arsenal | 682 | 230 | 47 |

**RC3 is the richest source of naming evidence in the release**: it carries
the code of the lobby — the multiplayer — and 47 source files, among them
`lobby_net/src/lobby_net_main.cpp` and `lobby_gui/src/lobby_gui_manager.cpp`.

**The strings that look better than they are.** The six strings of the
`cell/samples/common/gcmutil/old/` library — `texture.cpp:91 p != NULL` and
its neighbours — are **dead data**: no instruction of RC1, RC2 or RC3 builds
their address, and the table of pointers that holds them is never read. They
are the `.data` of a statically linked library whose code was not called;
the linker kept them all the same. A string that no code reaches can name no
function, and the tool reports those separately.

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
