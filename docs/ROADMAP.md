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

## Step 3 — build and qualify a PPU toolchain *(provisionally qualified)*

**Why.** The toolchain gate asks which options reproduce the code generation
of the compiler. The compiler is now named — GCC 4.1.1 as the SDK 400 ships
it — so the question is precise, and step 4 gave the bodies of known extent
to measure against.

**What was done.** Two builds of the Cell OS Lv-2 toolchain were made from
their sources, in a container, with a host compiler old enough to build
GCC 4.1.1. The profiles `-O1 -mno-save-restore-tocbase` and
`-O1 -mno-save-restore-tocbase -mno-nop-after-bl` reproduce six bodies
exactly, and four functions of the SDK's runtime are byte-identical in the
retail executable.

**What was found.** The game was built with `-mno-nop-after-bl` on some
files and without it on others: the SCE backend emits a call as the branch
and a second word that restores the TOC, and the option drops that second
word. Which one a file uses is visible in its code.

**What is left.** The six bodies are all of the same shape — a frame, a
call, an epilogue. The profile has to hold on bodies with arguments, with
branches and with arithmetic.

**Needs.** More bodies.

**Done when.** The toolchain gate passes: the profile holds on a set of
bodies of different shapes, and the complete-program gate can be attempted.

## Step 4 — recover the function boundaries *(done)*

**What.** Four independent signals — the prologue of the SDK, the targets of
the calls, the entries of the control flow and the returns of the walk — and
only the addresses that two of them agree on. The end of a function is the
return that no path falls through from.

**The result.** 53,456 functions, of which 47,215 end on a return, and 3
addresses that are still candidates:

| Program | Functions | Ending on a return |
|---|---|---|
| `EBOOT` - the collection launcher | 4,433 | 3,787 |
| `RC1` - Ratchet & Clank (2002) | 9,824 | 8,122 |
| `RC2` - Going Commando | 21,054 | 19,056 |
| `RC3` - Up Your Arsenal | 18,145 | 16,250 |

The names are not known yet: every function carries the placeholder of its
address, and its state is `bounded`. See [CATALOGUE.md](CATALOGUE.md).

**Needs.** Nothing more.

## Step 4b — match the builds to each other *(done)*

**What.** The collection's copy of a game and the standalone PlayStation
Network title of the same game are two builds of one program; the three
games of the series share an engine. The relation between them is measured
on the body of the functions, never on the address.

**The result.** 99 % of the functions of a game are matched with their
counterpart in the other build, every matched pair having exactly the same
size; and the engine's own code is matched across the three games, more than
half of those pairs being literally the same bytes. The table is in
`config/correspondence.tsv`. See [CORRESPONDENCE.md](CORRESPONDENCE.md).

**Needs.** Nothing more.

## Step 5 — name the first functions

**What.** Recover the names from the sibling projects' vocabularies, from the
strings, and from the callers.

**Needs.** Step 4, and the sibling projects.

**Done when.** The first functions carry names with recorded evidence.

## Step 6 — author the first body *(done, once)*

**What.** Write the function in C/C++ in the form the original author would
have used, and take it through the gates.

**The result.** Six bodies of the launcher, in `src/text/`. Each candidate is
compiled with the qualified profile, linked at the measured address with the
callees at their retail addresses, and compared with the retail bytes:
**match**.

| Function | Address | Bytes | Profile |
|---|---|---|---|
| `module_init` | `0x10200` | 44 | the eight byte call |
| `func_512F4` | `0x512F4` | 36 | the eight byte call |
| `func_143158` | `0x143158` | 36 | the eight byte call |
| `func_2CF24` | `0x2CF24` | 32 | the four byte call |
| `func_4EB7C` | `0x4EB7C` | 32 | the four byte call |
| `func_68088` | `0x68088` | 32 | the four byte call |

```sh
python tools/try_body.py work/gate/func_2CF24.c 0x2CF24 \
    --elf work/decrypted/eboot.elf --symbol sub_2CE90=0x2CE90
match: 32 bytes at 0x2CF24
```

**Needs.** Nothing more for these. The next bodies need the same work: read
the code, write the source, compile, compare.

## Step 7 — the catalogue writer

**What.** A tool that turns the analysis into `config/functions.tsv`, so that
the catalogue stops being maintained by hand.

**Needs.** The entry convention, once it is settled by the first wave.

## Step 8 — the shared engine *(the relation is measured; the names are not)*

**What.** The three titles share an engine. Once the engine's vocabulary is
recovered on one title, the other two become much cheaper: the same name, the
same layout, a different address.

**What is done.** The relation itself is measured: 1,226 functions of `rc1`
have a counterpart in the three other builds at once, and more than half of
those pairs are the same bytes — so a name proved on the engine's code of one
game is proved on the other games by the same body, at another address. See
[CORRESPONDENCE.md](CORRESPONDENCE.md).

**What is left.** The vocabulary: the names of the engine's functions, which
is step 5.

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
