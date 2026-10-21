# Third party notices

This repository is authored material under GPL-3.0. It carries no vendored
third-party source code today; this file records the tools and the formats
whose knowledge it builds on, so that the origin of what is used here stays
visible.

## Formats and specifications

The readers in `tools/` implement formats that are described in public
documentation and in other people's tools. This repository documents what it
measured on its own target; the formats themselves are not the property of
this project.

| Format | Where it is read | Public description |
|---|---|---|
| `PARAM.SFO` | `tools/param_sfo.py` | the PS3 metadata file, described by the homebrew community |
| `PS3_DISC.SFB` | `tools/ps3disc.py` | the PS3 volume descriptor, described by the homebrew community |
| `SCE\0` (SELF) | `tools/self_header.py` | the PS3 executable container; the decryption method is the one RPCS3 implements |
| PPU ELF | `tools/ppu_elf.py` | ELF64 big-endian for the Cell BEAT PowerPC core |

## RPCS3

The NPDRM decryption scheme and the SELF container are implemented by the
RPCS3 emulator, under its own licence. This repository **links no RPCS3
code**. It documents the scheme and points at the RPCS3 sources, the way the
sibling projects do.

* RPCS3 — https://github.com/RPCS3/rpcs3 — free software, licensed under
  GPL-2.0-or-later.

## The sibling projects

The evidence standard, the source layout and the vocabulary of this project
come from the sibling Ratchet & Clank decompilation projects, all under
GPL-3.0 and all authored by the same contributor:

* `rac1-decomp` — Ratchet & Clank (2002)
* `rac2-gc-decomp` — Ratchet & Clank: Going Commando (PS2)
* `rac3-uya-decomp` — Ratchet & Clank: Up Your Arsenal (PS2)
* `rac5-sm-decomp` — Ratchet & Clank: Size Matters (PS2)
* `rac-sac-decomp` — Ratchet & Clank: Secret Agent Clank (PS2)
* `rac8-act-decomp` — Ratchet & Clank: A Crack in Time (PS3)

`tools/ppu_elf.py` is shared with `rac8-act-decomp` and carries its origin
here; it is covered by the same GPL-3.0 licence.

## The game

Ratchet & Clank Collection is a trademark of Sony Interactive Entertainment and
was developed by Insomniac Games. This project is an unofficial fan project,
not affiliated with or endorsed by either. No part of the game is
redistributed here; see [LEGAL.md](LEGAL.md).
