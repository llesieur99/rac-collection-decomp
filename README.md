# Ratchet & Clank Collection — matching decompilation

A matching-decompilation workspace for **Ratchet & Clank Collection** on the
PlayStation 3 (USA release, `BCUS98282`).

The goal is to rebuild the retail programs in *C/C++ compiled*, with a proof:
the bytes the qualified toolchain produces must be **identical** to the retail
bytes, at every applicable placement, and the complete program must still hash
to the pinned retail hash.

This repository holds the **method, the rules, the templates and the tooling**,
and the first measured results. It publishes no game code, no assets and no
console keys.

## What is established

The pinned release has been read and measured:

| Fact | Value |
|---|---|
| Title | `Ratchet & Clank Collection` |
| Title id | `BCUS98282` |
| Release version | `02.00` (application version `01.00`) |
| Minimum system | `04.2100` |
| Volume | `PS3VOLUME` (hybrid disc), descriptor `PS3_DISC.SFB` |
| Descriptor size | 1,536 bytes |
| `PARAM.SFO` | 1,040 bytes, 12 entries |
| Executables | 4 — `EBOOT.BIN` plus one per title |
| Executable kind | retail SELF (`SCE\0`), key revision `0x001C`, local licence |
| PPU ELF | ELF64, big-endian, `EM_PPC`, 8 program headers, 35 section headers |
| Symbol table | **none** — the retail executables are stripped |
| Compiler | **GCC 4.1.1, as the PlayStation 3 SDK 400 ships it** — 124 objects, plus 5 from the SDK 360 |
| Functions bounded | 20,939 — 17,445 of them ending on a return |
| Functions with a string | 1,518 — the subject of the function, measured |
| Matching bodies | 6 — byte-exact, with two different toolchain builds |
| Correspondence between the builds | 99 % of the functions matched, function by function, across the builds and across the games |
| Disc files | 13,149 — 12,429,594,706 bytes |
| Working copy files | 13,148 — 12,161,159,250 bytes |
| Identical on both sides | 10 (the metadata); the other 13,138 are encrypted on the disc |

The release carries three titles plus a launcher:

| File | Title | Size | PPU ELF |
|---|---|---|---|
| `USRDIR/EBOOT.BIN` | collection launcher | 2,258,408 | 2,255,976 |
| `USRDIR/RC1.ppu.self` | Ratchet & Clank (2002) | 9,767,328 | 9,764,896 |
| `USRDIR/RC2.ppu.self` | Ratchet & Clank: Going Commando | 21,072,432 | 21,070,000 |
| `USRDIR/RC3.ppu.self` | Ratchet & Clank: Up Your Arsenal | 13,339,600 | 13,337,168 |

The exact hashes, the entry points and the segment tables are in
[config/target.json](config/target.json), which is **measured** by
[`tools/measure_target.py`](tools/measure_target.py), never typed by hand.

Three facts shape the whole project:

1. **The retail executables are stripped.** There is no `.symtab` and no
   readable section name — the string table of the sections is encrypted and
   lost with the container. Function boundaries and names have to be recovered
   by analysis, and every name in this project is a *hypothesis* until the
   code proves it.
2. **On the disc, the game data is encrypted.** The disc holds 13,138 game
   files encrypted with the disc key; the working copy holds the same files
   in the clear. Ten metadata files are in the clear on both sides. Both
   sides are pinned file by file, so a reader can always tell which one they
   are looking at: [docs/DISC-PROVENANCE.md](docs/DISC-PROVENANCE.md).
3. **The executables have a second layer, and it has been removed.** The
   metadata and the sections of a SELF container are encrypted; the removal
   needed only the constants of the revision of the container, and the
   result was validated against the sibling project.
   [docs/NPDRM.md](docs/NPDRM.md).

The compiler is named: **GCC 4.1.1 as the PlayStation 3 SDK 400 ships it**,
for 124 objects, plus 5 objects from the SDK 360. The sibling project's target
was built with the SDK 270, so the two trees are not interchangeable.
[docs/COMPILER.md](docs/COMPILER.md).

## Start here

| Document | What it gives you |
|---|---|
| [PROMPT.md](PROMPT.md) | the starter prompt — what an agent reads, and the prompt to launch a wave |
| [AGENTS.md](AGENTS.md) | the ten working rules, and what must never be committed |
| [docs/METHOD.md](docs/METHOD.md) | the wave protocol, from the foundation lot to the pull request |
| [docs/EVIDENCE.md](docs/EVIDENCE.md) | what counts as a proof, and what does not |
| [docs/GATES.md](docs/GATES.md) | the gates: the body gate, the placement gate, the complete-program gate |
| [docs/CATALOGUE.md](docs/CATALOGUE.md) | the function catalogue: how the boundaries are recovered, and on what evidence |
| [docs/STATE.md](docs/STATE.md) | the anchor: where the project stands, and what to do next |
| [docs/ROADMAP.md](docs/ROADMAP.md) | the ordered work, and what each step needs |
| [docs/DISC-FORMAT.md](docs/DISC-FORMAT.md) | the disc layout and the `PS3_DISC.SFB` descriptor |
| [docs/PARAM-SFO.md](docs/PARAM-SFO.md) | the metadata file and the measured table |
| [docs/SELF-FORMAT.md](docs/SELF-FORMAT.md) | the SELF container, the two variants, and the NPDRM control information |
| [docs/PPU-EXECUTABLE.md](docs/PPU-EXECUTABLE.md) | the PPU ELF, its segments and its section table |
| [docs/DISC-PROVENANCE.md](docs/DISC-PROVENANCE.md) | where the working copy comes from, and how it is verified |
| [docs/NPDRM.md](docs/NPDRM.md) | the encryption of the executables, and how it is removed |
| [docs/TOOLCHAIN.md](docs/TOOLCHAIN.md) | the compiler, its build, and the flags that reproduce the bytes |
| [docs/COMPILER.md](docs/COMPILER.md) | the compiler: the stamp, the link map, and the way forward |
| [docs/ENGINE.md](docs/ENGINE.md) | the engine: its build stamp, the originals it comes from |
| [docs/NAMING.md](docs/NAMING.md) | the naming: how a name is proved, and how it travels |
| [docs/CORRESPONDENCE.md](docs/CORRESPONDENCE.md) | the correspondence between the builds, function by function |
| [docs/RELATED-TITLES.md](docs/RELATED-TITLES.md) | the three titles as separate PlayStation Network titles |

## Layout

| Path | Role |
|---|---|
| `src/` | accepted authored C/C++ definitions, one per function |
| `nonmatching/` | useful but nonmatching attempts, indexed by function |
| `tools/` | reusable tools, with tests |
| `tests/` | the unit tests of the tools, on synthetic data only |
| `config/` | pinned metadata: target identity, measured tables |
| `docs/` | the method, the evidence standard, the anchor |
| `work/` | the private workspace: the disc tree, the rebuilt ELFs, analysis projects (git-ignored) |

## Using the tools

The readers need nothing but the Python standard library:

```sh
python tools/param_sfo.py info   "path/to/PS3_GAME/PARAM.SFO"
python tools/ps3disc.py info     "path/to/PS3_DISC.SFB"
python tools/self_header.py info "path/to/USRDIR/EBOOT.BIN"
python tools/self_header.py segments "path/to/USRDIR/EBOOT.BIN"
python tools/self_header.py extract "path/to/USRDIR/EBOOT.BIN" --out work/eboot.elf
python tools/ppu_elf.py info     work/eboot.elf
python tools/ppu_elf.py sections work/eboot.elf
```

The state of the payload, the compiler and the alignment of a rebuild:

```sh
python tools/payload_state.py  "path/to/USRDIR/EBOOT.BIN"
python tools/compiler_stamp.py "path/to/USRDIR/EBOOT.BIN" --modules
python tools/rebuild_check.py  "path/to/USRDIR/EBOOT.BIN"
```

The boundaries of the functions, and the code that backs them:

```sh
python tools/ppu_funcs.py catalogue work/eboot.elf --confirmed
python tools/ppu_funcs.py bounds   work/eboot.elf --confirmed
python tools/build_catalogue.py --work work/decrypted --out config/functions.tsv
python tools/ppu_disasm.py work/eboot.elf --start 0x10200 --count 11
```

The strings the code touches, and the evidence they carry:

```sh
python tools/strings_xref.py work/decrypted/RC2.elf \
    --catalogue config/functions.tsv --program RC2 --out work/strings-RC2.tsv
python tools/evidence.py --catalogue config/functions.tsv \
    --ghidra RC2=work/ghidra-project/rc2-evidence.tsv \
    --strings work/strings-RC2.tsv --out config/evidence.tsv
```

The correspondence between two builds, function by function, and the name
that travels on it:

```sh
python tools/build_correspondence.py \
    --build collection-RC2=work/decrypted/RC2.elf \
    --build NPUA80644=work/decrypted-standalone/gc.elf \
    --pair collection-RC2:NPUA80644 \
    --out config/correspondence.tsv --builds-out config/builds.tsv
python tools/propose_name.py --program collection-RC2 --address 0x00123456
```

`payload_state.py` measures the entropy of the segments and says whether the
program is readable. `compiler_stamp.py` looks for the identification of the
compiler and reports the link map. `rebuild_check.py` checks that a rebuilt
ELF is aligned, without reading the code. `ppu_funcs.py` recovers the
boundaries, `ppu_disasm.py` prints the code so that a boundary can be
checked by reading it. `build_correspondence.py` matches the functions of two
builds on the body, not on the address, and `propose_name.py` carries a name
over the match it found.

The removal of the encryption of the executables:

```sh
python tools/self_decrypt.py "path/to/USRDIR/EBOOT.BIN" --keys work/self-keys.json --out work/eboot.elf
```

The keys are read from a **local** file, which is not committed: they are
the SCE constants of the revision of the container, published by the RPCS3
sources, and the repository publishes no key material of any kind. See
[docs/NPDRM.md](docs/NPDRM.md).

The toolchain, and the comparison of a body with the retail bytes:

```sh
python tools/try_body.py work/gate/module_init.c 0x10200 \
    --elf work/decrypted/eboot.elf \
    --symbol sub_147B0=0x147B0 --symbol sub_14820=0x14820
python tools/compare_libgcc.py --elf work/decrypted/eboot.elf
```

`try_body.py` compiles a candidate in the container that holds the compiler,
links it at the retail address with the callees at their retail addresses,
and compares every byte. `compare_libgcc.py` checks the SDK's own runtime
against the retail text, which qualifies the compiler without writing a
single line of source. See [docs/TOOLCHAIN.md](docs/TOOLCHAIN.md).

The manifest pins the bytes of a tree, and checks one against it. The two
manifests of the release are in `config/`:

```sh
python tools/manifest.py build  "path/to/release" --out work/manifest.tsv
python tools/manifest.py verify "path/to/release" --manifest config/working-manifest.tsv
python tools/manifest.py diff   config/disc-manifest.tsv config/working-manifest.tsv
```

The package reader, for the digital manual the disc carries:

```sh
python tools/pkg.py inspect "path/to/PS3_GAME/PKGDIR/PKG00/INSTALL.PKG"
python tools/pkg.py list    "path/to/PS3_GAME/PKGDIR/PKG00/INSTALL.PKG"
```

The configuration of the target is regenerated from a local copy:

```sh
python tools/measure_target.py --root "path/to/extracted/release" --out config/target.json
```

## Public boundary

This repository publishes **written** source, reusable tools, research metadata
(names, addresses, hashes) and documentation. It never publishes disc images,
retail executables, extracted modules, instruction listings, disassembly,
assets, proprietary toolchains, console keys, SDK sources, or leaked or NDA
source. See [AGENTS.md](AGENTS.md) and [LEGAL.md](LEGAL.md).

Obtain your own lawful copy of the game; the project cannot supply one, and
the local tooling and receipts stay on your machine.

## Licence

The independently authored material here is GPL-3.0, like the sibling
projects; see [LICENSE](LICENSE). That licence does not cover the game, its
assets, any console key material or any proprietary toolchain. Contributions
should be original or compatible with that licence, with attribution where
required.

Ratchet & Clank is a trademark of Sony Interactive Entertainment; the game was
developed by Insomniac Games. This is an unofficial fan project, not
affiliated with or endorsed by either.
