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
| `0x08` | 2 | key revision | `0x001C` |
| `0x0A` | 2 | header type | `0x0001` (SELF) |
| `0x0C` | 4 | offset of the encrypted metadata | `0x410` |
| `0x10` | 8 | size of the header block | `0x980` |
| `0x18` | 8 | size of the ELF the container holds | see below |
| `0x20` | 8 | extension header version | 3 |
| `0x28` | 8 | offset of the program information | `0x70` |
| `0x30` | 8 | offset of the ELF header | `0x90` |
| `0x38` | 8 | offset of the program header table | `0xD0` |
| `0x40` | 8 | offset of the section header table | per file |
| `0x48` | 8 | offset of the segment table | `0x290` |
| `0x50` | 8 | offset of the version header | `0x390` |
| `0x58` | 8 | offset of the control information | `0x3C0` |
| `0x60` | 8 | size of the control information | `0x70` |

## The four executables

| File | Container size | ELF size | Entry | Program headers | Section headers |
|---|---|---|---|---|---|
| `EBOOT.BIN` | 2,258,408 | 2,255,976 | `0x202450` | 8 | 35 |
| `RC1.ppu.self` | 9,767,328 | 9,764,896 | `0x753798` | 8 | 35 |
| `RC2.ppu.self` | 21,072,432 | 21,070,000 | `0x12E38A8` | 8 | 35 |
| `RC3.ppu.self` | 13,339,600 | 13,337,168 | `0xBD3DA0` | 8 | 35 |

The container size is the ELF size plus `0x980`, on all four. That constant is
the whole of the header block.

## The program information

Four 32-bit words at `0x70`. On all four executables they read:

```
0x10100000  0x01000003  0x01000002  0x00000004
```

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

The encrypted metadata holds the content id and the key material. It stays
encrypted on the disc; reading it needs the licence file of the console. The
chain is the one RPCS3 implements:

```
rap --(AES-128-CBC, RAP_KEY)--> rif --(rap2rifkey)--> rifkey
rifkey --(AES-128-ECB, NP_KLIC_KEY)--> npdrm_key
metadata_info --(AES-128-CBC, npdrm_key, iv=0)--> metadata_info
metadata_info --(AES-256-CBC, erk, riv)--> metadata_info
metadata_headers --(AES-128-CTR, meta key/iv)--> the section table
each encrypted section --(AES-128-CTR, data key/iv)--> plaintext
```

The `erk`/`riv` pair depends on the key revision, `0x001C` here. A wrong
licence file shows up as a metadata info block whose padding is not zero:
that is the check the tooling does before going further.

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

## The section names

The section header table is present and has 35 entries, but the string table
it points at holds the SCE module names (`p410001libc`, `p410001libstdc++`,
`p410001liblv2`, …) rather than conventional names such as `.text`. The
retail build is stripped: there is no symbol table, and no section name may be
used as evidence of what a section holds. See
[PPU-EXECUTABLE.md](PPU-EXECUTABLE.md).
