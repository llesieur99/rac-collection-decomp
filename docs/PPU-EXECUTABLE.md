# The PPU executable

The PPU ELF is the program the SELF container holds. It is an ELF64,
big-endian file for the Cell BEAT PowerPC core.

## The header

| Field | Value on the target |
|---|---|
| Class | `ELF64` |
| Data | big-endian (`ELFDATA2MSB`) |
| Version | 1 (`EV_CURRENT`) |
| Machine | `EM_PPC` (102) |
| Entry | `0x202450` on `EBOOT.BIN` |
| Program header offset | `0x40` |
| Section header offset | `0x2263A8` on `EBOOT.BIN` |
| Program headers | 8 |
| Section headers | 35 |

## The program headers

Each program header carries the SCE flag bits next to the usual permission
bits. The reader names them `SPU_X`, `SPU_W`, `SPU_R`, `RSX_X`, `RSX_W` and
`RSX_R`.

For `EBOOT.BIN`:

| # | Type | Flags | File offset | Vaddr | File size | Mem size |
|---|---|---|---|---|---|---|
| 0 | `PT_LOAD` | `SPU_R` (`0x400005`) | `0x0` | `0x10000` | `0x1E6FE8` | `0x1E6FE8` |
| 1 | `PT_LOAD` | `SPU_W`, `SPU_R` | `0x1F0000` | `0x200000` | `0x34A80` | `0x1020F8` |
| 2 | `PT_LOAD` | — | `0x224A80` | `0x0` | 0 | 0 |
| 3 | `PT_LOAD` | — | `0x224A80` | `0x0` | 0 | 0 |
| 4 | `PT_LOAD` | `SPU_W`, `SPU_R`, `RSX_W`, `RSX_R` | `0x224A80` | `0x0` | 0 | 0 |
| 5 | `PT_TLS` | — | `0x1FDD8C` | `0x20DD8C` | `0x114` | `0x114` |
| 6 | `0x60000001` | — | `0x1E6F80` | `0x1F6F80` | `0x28` | `0x28` |
| 7 | `0x60000002` | — | `0x1E6FA8` | `0x1F6FA8` | `0x40` | `0x40` |

The last two types are SCE-specific. The reader reports them by their raw
value, because the two projects of this family that read PS3 executables do
not agree on their names, and a name that is not certain is not used. What is
certain is their extent and their role: they hold the relocation records and
the segment symbols of the program, and they sit at the end of the text
segment.

Two things are worth noting:

* **The text segment starts at file offset 0.** The ELF header and the
  program header table live inside the first segment's file range. A file
  offset is therefore not a virtual address, and the two must never be
  confused when a boundary is recorded.
* **Segments 2, 3 and 4 are empty** but still carry a file offset. They are
  the RSX graphics segments: the collection links the graphics side of the
  engine but leaves the payload to the RSX side.

## The section table

35 entries of 64 bytes, at the tail of the image.

The string table they point at does **not** hold conventional section names.
It holds the SCE module names: `p410001libc`, `p410001libstdc++`,
`p410001liblv2`, `p410001libnet_stub`, `p410001libnetctl_stub`,
`p410001libfs_stub`, `p410001libspurs_stub` and so on.

So the retail build is stripped in the strongest sense:

* there is **no symbol table** — no `.symtab`, no `.dynsym` with names;
* there is **no conventional section name** — the name of a section says which
  module it came from, not what it holds.

Every function name in this project is therefore a *hypothesis* until the code
proves it, and every section boundary is provisional until the bytes say so.

## Reading it

```sh
python tools/ppu_elf.py info     work/eboot.elf
python tools/ppu_elf.py sections work/eboot.elf
python tools/ppu_elf.py symbols  work/eboot.elf
python tools/ppu_elf.py catalogue work/eboot.elf --out work/catalogue.tsv
```

`tools/ppu_elf.py` reads a *decrypted* ELF; obtain it with
`tools/self_header.py extract`. The reader is shared with the sibling
projects, so the output columns and the vocabulary are the same.

## What the reader cannot do

It cannot name a function, because there is nothing to read. It reports
addresses, sizes, flags and offsets; it does not guess. Naming is the work of
[CATALOGUE.md](CATALOGUE.md), and it is a separate, slower step.
