# The roadmap

The ordered work, and what each step needs. A step that is not ready is not
started; a step that is started is finished before the next one begins.

## Step 0 — the release is measured *(done)*

The disc is read, the descriptor and the metadata file are parsed, the SELF
containers are read, the PPU ELF of each of the four executables is rebuilt,
and the hashes are pinned in `config/target.json`.

**Needs.** Nothing more.

## Step 1 — recover the compiler stamp

**Why.** The toolchain gate asks which compiler produced the retail bytes.
Without the stamp, the question cannot even be asked.

**What.** Search the rebuilt ELF for the `.comment` section or for any
compiler identification string; read the flags of the program headers for the
SCE code-generation bits; note the C++ library and the standard library
version from the strings the binary carries.

**Needs.** `tools/ppu_elf.py`, and a search over the rebuilt ELFs.

**Done when.** `config/compiler.json` names the compiler, or states that no
stamp could be found, with the evidence.

## Step 2 — build and qualify a PPU toolchain

**Why.** The PS2 projects qualified their compiler against the retail bytes
before writing a single function. The PS3 needs the same, with `ps3gcc` as
the starting point rather than the Sony compiler of the PS2 projects.

**What.** Build the toolchain; find the options that reproduce the retail
code generation; document them in `config/compiler.json` with a regression
control.

**Needs.** The `ps3gcc` sources, a host that can build them, and a body of
known extent to measure against — which means step 3 must be done first, at
least partially.

**Done when.** The toolchain gate passes: one complete body of known extent
is reproduced byte for byte.

## Step 3 — recover the first boundaries

**Why.** Everything else needs a body of known extent.

**What.** Work on the launcher, the smallest of the four programs. Recover
the start of a function from a `bl` that targets it, and the end from its
return, following the rules of [CATALOGUE.md](CATALOGUE.md).

**Needs.** A disassembler for the PPU (Ghidra has a PowerPC backend; the
machine has one), and the rebuilt ELF.

**Done when.** `config/functions.tsv` holds a first set of bounded functions,
each with its evidence.

## Step 4 — name the first functions

**What.** Recover the names from the sibling projects' vocabularies, from the
strings, and from the callers.

**Needs.** Step 3, and the sibling projects.

**Done when.** The first functions carry names with recorded evidence.

## Step 5 — author the first body

**What.** Write the function in C/C++ in the form the original author would
have used, and take it through the gates.

**Needs.** Steps 1 to 4.

**Done when.** One function passes the body gate, the placement gate, the
complete-program gate and the semantics gate, and moves to `src/`.

## Step 6 — the catalogue writer

**What.** A tool that turns the analysis into `config/functions.tsv`, so that
the catalogue stops being maintained by hand.

**Needs.** The entry convention, once it is settled by the first wave.

## Step 7 — the shared engine

**What.** The three titles share an engine. Once the engine's vocabulary is
recovered on one title, the other two become much cheaper: the same name, the
same layout, a different address.

**Needs.** Steps 3 to 5 on one title.

## Step 8 — the update package

**What.** Read `PS3_UPDATE/PS3UPDAT.PUP` from the disc, and check whether it
carries a newer build of the launcher than the disc does. If it does, decide
which one is the pinned target, and record the decision.

**Needs.** The disc, and the reader of the update container.

## Step 9 — the native port

**Why not earlier.** A port is not matching work; it earns no matching
credit, and it must not disturb the matching tree.

**What.** A PC build of the engine, with the matching work as its evidence.

**Needs.** Steps 5 to 7, and a separate branch.
