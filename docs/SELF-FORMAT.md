# The SELF container of the retail executables

The four executables of the release are **SELF** containers (`SCE\0`), not
plain ELF files. This document describes what was measured on the four of them
and how the PPU ELF is recovered.

**The decryption is not published here.** On the disc the payload is
NPDRM-encrypted and reading it needs console key material, which has no place
in a public repository. The method is public though, and RPCS3 implements it:
see `rpcs3/Crypto/unself.cpp`, `rpcs3/Crypto/key_vault.cpp` and
`rpcs3/Crypto/unedat.cpp` in the RPCS3 sources.

**What the working copy holds, and what it does not.** The working copy is
the disc decrypted with the disc key, so the *assets* are in the clear. The
executables keep their **second layer**: the header of the container, the ELF
header, the program headers, the section table and the module names are
readable, but the **code and the data are still NPDRM-encrypted** — the text
segment measures 7.99 bits per byte and the data segment 8.00, while the
section table measures 1.61. See [COMPILER.md](COMPILER.md) and
[RELATED-TITLES.md](RELATED-TITLES.md).

## The header

Every multi-byte field of the header is big-endian. The layout below was
measured on all four executables and is identical on each of them.

| Offset | Size | Field | Value on the target |
|---|---|---|---|
| `0x00` | 4 | magic `SCE\0` | ✓ |
| `0x04` | 4 | version | 2 |
| `0x08` | 2 | revision of the container | `0x001C` |
| `0x0A` | 2 | type | 1 (SELF) |
| `0x0C` | 4 | offset of the metadata | `0x410` |
| `0x10` | 8 | size of the header block | `0x980` |
| `0x18` | 8 | size of the ELF the container holds | see below |
| `0x20` | 8 | version of the extension | 3 |
| `0x28` | 8 | offset of the program identification header | `0x70` |
| `0x30` | 8 | offset of the ELF header | `0x90` |
| `0x38` | 8 | offset of the program header table | `0xD0` |
| `0x40` | 8 | offset of the section header table | per file |
| `0x48` | 8 | offset of the segment table | `0x290` |
| `0x50` | 8 | offset of the version header | `0x390` |
| `0x58` | 8 | offset of the control information | `0x3C0` |
| `0x60` | 8 | size of the control information | `0x70` |
| `0x68` | 8 | padding | 0 |

The revision at `0x08` is the field that names the constants the metadata is
encrypted with: `0x001C` for the release of this project, `0x0019` for the
standalone titles. Bit `0x8000` of it marks a debug container, whose
payload is not encrypted.

The ELF header at `0x90` is a normal ELF64 big-endian header; its
`e_phoff` and `e_shoff` describe the **rebuilt** ELF, not the SELF's own
layout.

## The program identification header

At `0x70`, four fields and a padding:

| Offset | Size | Field | Value on the target |
|---|---|---|---|
| `0x00` | 8 | authority | `0x1010000001000003` |
| `0x08` | 4 | vendor | `0x01000002` |
| `0x0C` | 4 | type of the program | 4 (`APP`) |
| `0x10` | 8 | version of the program | `0x1000000000000` |

The type is what selects the constants of the decryption: the SCE key tables
are indexed by it. See [NPDRM.md](NPDRM.md).

## The control information

A chain of supplemental headers, each with a type, a size and a pointer to
the next one:

| Type | What it holds | Size |
|---|---|---|
| 1 | the plaintext capability header | `0x30` |
| 2 | the digest of the ELF | `0x40` |
| 3 | the NPDRM licence: the content id and the licence type | `0x90` |

The executables of the release carry a type 1 and a type 2; they have **no
NPDRM header**. The standalone titles carry the three. See
[NPDRM.md](NPDRM.md).

## The four executables

| File | Container size | ELF size | Entry | Program headers | Section headers |
|---|---|---|---|---|---|
| `EBOOT.BIN` | 2,258,408 | 2,255,976 | `0x202450` | 8 | 35 |
| `RC1.ppu.self` | 9,767,328 | 9,764,896 | `0x753798` | 8 | 35 |
| `RC2.ppu.self` | 21,072,432 | 21,070,000 | `0x12E38A8` | 8 | 35 |
| `RC3.ppu.self` | 13,339,600 | 13,337,168 | `0xBD3DA0` | 8 | 35 |

The container size is the ELF size plus `0x980`, on all four. That constant is
the whole of the header block.

## The segment table

At `0x290`, eight entries of 32 bytes, one per program header. Each entry is
eight big-endian 32-bit words:

| Word | Meaning |
|---|---|
| 0 | encryption state |
| 1 | offset of the payload in the container |
| 2 | reserved |
| 3 | size of the payload |
| 4 | compression method (1 = none) |
| 5, 6 | reserved |
| 7 | flags |

For `EBOOT.BIN`:

| # | Payload offset | Size | Role |
|---|---|---|---|
| 0 | `0x980` | `0x1E6FE8` | text |
| 1 | `0x1F0980` | `0x34A80` | data |
| 2 | `0x225400` | 0 | empty |
| 3 | `0x225400` | 0 | empty |
| 4 | `0x225400` | 0 | empty |
| 5 | `0x1FE70C` | `0x114` | TLS |
| 6 | `0x1E7900` | `0x28` | SCE dynamic section |
| 7 | `0x1E7928` | `0x40` | SCE segment symbols |

Every payload offset is the matching program header offset plus `0x980`.

## The NPDRM control information

At `0x3C0`, `0x70` bytes:

| Offset | Size | Field | Value |
|---|---|---|---|
| `0x00` | 4 | | `1` |
| `0x04` | 4 | | `0x30` |
| `0x08` | 4 | | 0 |
| `0x0C` | 4 | | `1` |
| `0x10` | `0x20` | | zero |
| `0x30` | 4 | licence type | `2` (local licence) |
| `0x34` | 4 | size of the encrypted metadata | `0x40` |
| `0x38` | 8 | | zero |
| `0x40` | `0x40` | encrypted metadata | ciphertext |

**That table describes the NPDRM header, and the executables of this release
do not have one.** Their control information holds a type 1 and a type 2, and
nothing else. The NPDRM header above is what the standalone titles carry.

The encrypted metadata of an NPDRM header holds the content id and the key
material. The chain is the one RPCS3 implements:

```
licence file --(rap2rifkey)--> rif key --(NP_KLIC_KEY)--> NPDRM key
metadata_info --(AES-128-CBC, npdrm_key, iv=0)--> metadata_info
metadata_info --(AES-256-CBC, erk, riv)--> metadata_info
metadata_headers --(AES-128-CTR, meta key/iv)--> the section table
each encrypted section --(AES-128-CTR, data key/iv)--> plaintext
```

The `erk`/`riv` pair depends on the revision of the container, `0x001C` here.
A wrong licence file shows up as a metadata info block whose padding is not
zero: that is the check the tooling does before going further.

The removal of the encryption, and what it does and does not recover, is the
subject of [NPDRM.md](NPDRM.md).

## Rebuilding the ELF

The rebuild is mechanical once the container is read:

1. the payload area starts at `header_size`, that is `0x980`;
2. the rebuilt ELF is that area, cut to the size the header declares, so its
   size is the `ELF size` field of the header;
3. the ELF header and the program header table are **not** in the payload
   area: they sit at `0x90` and `0xD0` of the container, and they are copied
   over the first bytes of the rebuilt image.

In other words:

```python
rebuilt = bytearray(container[0x980:0x980 + elf_size])
rebuilt[0:0x200] = container[0x90:0x290]
```

The result is a normal ELF64 big-endian file whose `e_phoff` is `0x40` and
whose `e_shoff` is the tail of the image. Its hash is pinned in
`config/target.json`.

**The rebuilt image is a container, not a program.** The header, the program
headers and the section table are in the clear; the segments are not. The
reader measures that, and says so: `tools/payload_state.py`.

```sh
python tools/self_header.py extract "path/to/USRDIR/EBOOT.BIN" --out work/eboot.elf
```

The reader is [`tools/self_header.py`](../tools/self_header.py):

```sh
python tools/self_header.py info     "path/to/USRDIR/EBOOT.BIN"
python tools/self_header.py segments "path/to/USRDIR/EBOOT.BIN"
python tools/self_header.py control  "path/to/USRDIR/EBOOT.BIN"
```

## The two variants

The release and the standalone PlayStation Network titles use two different
shapes of the container. Both were measured.

| | The release | The standalone titles |
|---|---|---|
| Key revision | `0x001C` | `0x0019` (Tools of Destruction: `0x001C`) |
| Header block | `0x980` | `0xA80` |
| Control information | `0x70` | `0x100` |
| Offset of the encrypted metadata | `0x410` | `0x4A0` |
| Trailer after the ELF | none | 48 bytes |

The rebuild rule is the same for both. The payload is cut to the size the
header declares, because the older variant carries a short trailer after the
ELF that is not part of the program.

## The validation of the rebuild

The reader is checked against an independent reference: the sibling project
`rac8-act-decomp` pins the container of A Crack in Time, and the copy on this
machine is **byte for byte the same file**:

| | Hash |
|---|---|
| The container, as published by the sibling | `e69f2b5a053454ef90144d31c3cbb5b6ccfc5399745e9bbb73fca1680b25c81a` |
| The container on this machine | `e69f2b5a053454ef90144d31c3cbb5b6ccfc5399745e9bbb73fca1680b25c81a` |

The rebuild gives exactly the size the sibling publishes, 14,515,416 bytes,
and the structure agrees in every particular: the entry point, the eight
program headers, the thirty sections, the segment offsets.

The **bytes** differ, and they have to: the sibling's hash is the hash of an
ELF rebuilt from a *decrypted* container, and this one is rebuilt from the
encrypted container. The difference is exactly the encrypted payload, the
text and the data; the headers, the program headers and the section header
table are in the clear in both and are identical.

`tools/rebuild_check.py` checks the alignment of a rebuild, without reading
the code: the size of the image, the end of the section header table, the
placement of every allocated section inside a segment, and the readability of
the module names.

```sh
python tools/rebuild_check.py "path/to/USRDIR/EBOOT.BIN"
```

All ten executables this project has measured — the four of the release, the
four standalone titles and A Crack in Time — are consistent.

## The section names

The section header table is present and has 35 entries, but the string table
it points at holds the SCE module names (`p410001libc`, `p410001libstdc++`,
`p410001liblv2`, …) rather than conventional names such as `.text`. The
retail build is stripped: there is no symbol table, and no section name may be
used as evidence of what a section holds. See
[PPU-EXECUTABLE.md](PPU-EXECUTABLE.md).
