# The roadmap

The ordered work, and what each step needs. A step that is not ready is not
started; a step that is started is finished before the next one begins.

## Step 0 — the release is measured *(done)*

The disc is read, the descriptor and the metadata file are parsed, the SELF
containers are read, the PPU ELF of each of the four executables is rebuilt,
and the hashes are pinned in `config/target.json`.

Both sides of the release are pinned file by file, in
`config/disc-manifest.tsv` and `config/working-manifest.tsv`.

**Needs.** Nothing more.

## Step 1 — recover the compiler stamp *(done)*

The executables were searched for the identification of the compiler: the
`.comment` section, every printable string of six characters or more, and the
strings that would name an SDK or a revision.

**The first pass found nothing**, because the payload was still encrypted: a
search for a string inside a ciphertext finds noise. The encryption was
removed in step 2, and the stamp was then found immediately.

**The answer**: 124 objects with `GCC: (GNU) 4.1.1 (SDK400, $Rev: 3538 $)`
and 5 with `GCC: (GNU) 4.1.1 (SDK360, $Rev: 3455 $)`, the same for the four
programs of the release.

**Needs.** Nothing more; the question is answered.

## Step 2 — remove the NPDRM layer *(done)*

The metadata and the sections of the executables are encrypted. The removal
needed only the constants of the revision of the container, and the tool that
does it is `tools/self_decrypt.py`.

**What was done.** The chain was implemented and the result was validated
against the sibling project: decrypting A Crack in Time reproduces its
published analysis exactly — the same 106 stamps, the same libraries, the
same size of the rebuilt ELF.

**Needs.** Nothing more.

**Done when.** The programs are in the clear: `tools/payload_state.py` reports
*IN THE CLEAR* for the four executables of the release, and the stamps are
readable.

## Step 3 — build and qualify a PPU toolchain

**Why.** The toolchain gate asks which options reproduce the code generation
of the compiler. The compiler is now named — GCC 4.1.1 as the SDK 400 ships
it — so the question is precise, and step 4 has given the bodies of known
extent to measure against.

**What.** Build a candidate toolchain — the `ps3gcc` sources are the obvious
one, as the homebrew scene's PowerPC cross compiler for the PS3 — and
qualify it against the retail bytes, the way the PS2 projects qualified
theirs. The qualification is the work, not the build.

**Needs.** The `ps3gcc` sources, a host that can build them, and the bodies
of step 4.

**Done when.** The toolchain gate passes: one complete body of known extent
is reproduced byte for byte.

## Step 4 — recover the function boundaries *(done)*

**What.** Two independent methods, and only the addresses that both agree on:
the prologue of the SDK, and the targets of the calls. The end of a function
is the return that no path falls through from.

**The result.** 20,939 functions, of which 17,728 end on a return:

| Program | Functions | Ending on a return |
|---|---|---|
| `EBOOT` — the collection launcher | 1,290 | 1,077 |
| `RC1` — Tools of Destruction | 3,054 | 2,591 |
| `RC2` — Going Commando | 9,884 | 8,383 |
| `RC3` — Up Your Arsenal | 6,711 | 5,677 |

The names are not known yet: every function carries the placeholder of its
address, and its state is `bounded`. See [CATALOGUE.md](CATALOGUE.md).

**Needs.** Nothing more.

## Step 5 — name the first functions

**What.** Recover the names from the sibling projects' vocabularies, from the
strings, and from the callers.

**Needs.** Step 4, and the sibling projects.

**Done when.** The first functions carry names with recorded evidence.

## Step 6 — author the first body

**What.** Write the function in C/C++ in the form the original author would
have used, and take it through the gates.

**Needs.** Steps 3 to 5.

**Done when.** One function passes the body gate, the placement gate, the
complete-program gate and the semantics gate, and moves to `src/`.

## Step 7 — the catalogue writer

**What.** A tool that turns the analysis into `config/functions.tsv`, so that
the catalogue stops being maintained by hand.

**Needs.** The entry convention, once it is settled by the first wave.

## Step 8 — the shared engine

**What.** The three titles share an engine. Once the engine's vocabulary is
recovered on one title, the other two become much cheaper: the same name, the
same layout, a different address.

**Needs.** Steps 4 to 6 on one title.

## Step 9 — the update package

**What.** Read `PS3_UPDATE/PS3UPDAT.PUP` from the disc, and check whether it
carries a newer build of the launcher than the disc does. If it does, decide
which one is the pinned target, and record the decision.

**Needs.** The disc, and the reader of the update container.

## Step 10 — the native port

**Why not earlier.** A port is not matching work; it earns no matching
credit, and it must not disturb the matching tree.

**What.** A PC build of the engine, with the matching work as its evidence.

**Needs.** Steps 5 to 8, and a separate branch.
