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

The release carries three titles plus a launcher:

| File | Title | Size | PPU ELF |
|---|---|---|---|
| `USRDIR/EBOOT.BIN` | collection launcher | 2,258,408 | 2,255,976 |
| `USRDIR/RC1.ppu.self` | Ratchet & Clank: Tools of Destruction | 9,767,328 | 9,764,896 |
| `USRDIR/RC2.ppu.self` | Ratchet & Clank: Going Commando | 21,072,432 | 21,070,000 |
| `USRDIR/RC3.ppu.self` | Ratchet & Clank: Up Your Arsenal | 13,339,600 | 13,337,168 |

The exact hashes, the entry points and the segment tables are in
[config/target.json](config/target.json), which is **measured** by
[`tools/measure_target.py`](tools/measure_target.py), never typed by hand.

Three facts shape the whole project:

1. **The retail executables are stripped.** There is no `.symtab` and no
   conventional section name; the section string table holds the SCE module
   names. Function boundaries and names have to be recovered by analysis, and
   every name in this project is a *hypothesis* until the code proves it.
2. **On the disc, the executables are encrypted.** The disc holds the NPDRM
   ciphertext; the working copy holds the same programs with the payload in
   the clear. Both sides are pinned by hash in
   [docs/DISC-PROVENANCE.md](docs/DISC-PROVENANCE.md).
3. **The PPU is a big-endian PowerPC.** The compiler is not the Sony compiler
   of the PS2 projects. Until a PPU compiler and its options are qualified, no
   byte-exact claim is possible and the gates stay closed.

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
| [docs/SELF-FORMAT.md](docs/SELF-FORMAT.md) | the SELF container and the NPDRM control information |
| [docs/PPU-EXECUTABLE.md](docs/PPU-EXECUTABLE.md) | the PPU ELF, its segments and its section table |
| [docs/DISC-PROVENANCE.md](docs/DISC-PROVENANCE.md) | where the working copy comes from, and how it is verified |

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

The manifest pins the bytes of a tree, and checks one against it:

```sh
python tools/manifest.py build  "path/to/PS3_GAME" --out work/manifest.tsv
python tools/manifest.py verify "path/to/PS3_GAME" --manifest work/manifest.tsv
python tools/manifest.py compare "path/to/PS3_GAME" "path/to/another/copy"
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
