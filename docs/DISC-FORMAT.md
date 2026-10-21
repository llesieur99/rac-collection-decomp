# The disc and its volume descriptor

The target is a retail PlayStation 3 disc. This document describes what was
measured on it and how the working copy relates to it.

## The disc

| Fact | Value |
|---|---|
| Volume label | `PS3VOLUME` |
| Media | CD/DVD/Blu-ray hybrid, 12,477,331,456 bytes |
| Root | `PS3_DISC.SFB`, `PS3_GAME/`, `PS3_UPDATE/` |

The root of the disc holds three entries:

```
PS3_DISC.SFB      1536 bytes
PS3_GAME/         the game tree
PS3_UPDATE/       PS3UPDAT.PUP, 268,435,456 bytes
```

`PS3_GAME` holds 13,147 files for 12,161,157,714 bytes:

```
PS3_GAME/
├── ICON0.PNG      95,118
├── PIC1.PNG     3,387,458
├── PS3LOGO.DAT       5,120
├── PARAM.SFO        1,040
├── LICDIR/
├── PKGDIR/
├── TROPDIR/
└── USRDIR/
    ├── Common/
    ├── PS3Data/
    ├── rc1/
    ├── rc2/
    ├── rc3/
    ├── EBOOT.BIN          2,258,408
    ├── RC1.ppu.self       9,767,328
    ├── RC2.ppu.self      21,072,432
    └── RC3.ppu.self      13,339,600
```

The three `rcN` directories hold the assets of one title each: `rc1` is
Tools of Destruction, `rc2` is Going Commando, `rc3` is Up Your Arsenal.
`EBOOT.BIN` is the collection launcher.

## The volume descriptor

`PS3_DISC.SFB` is **not** a container of the game data. It is a small
descriptor, 1,536 bytes on this disc, that names the title and describes the
volume.

| Offset | Size | Field | Value |
|---|---|---|---|
| `0x00` | 4 | magic | `.SFB` |
| `0x04` | 4 | version | `0x00010000` |
| `0x08` | 24 | reserved | zero |
| `0x20` | 16 | entry name | `HYBRID_FLAG` |
| `0x30` | 4 | payload offset | `0x200` |
| `0x34` | 4 | payload length | `0x20` |
| `0x38` | 8 | reserved | zero |
| `0x40` | 16 | entry name | `TITLE_ID` |
| `0x50` | 4 | payload offset | `0x220` |
| `0x54` | 4 | payload length | `0x10` |
| `0x58` | 8 | reserved | zero |
| `0x60` | … | rest of the file | zero |

Each entry is 32 bytes: a 16-byte name, then four big-endian 32-bit words.
The table ends at the first entry whose name is empty.

The `TITLE_ID` payload, at `0x220`, is the string `BCUS-98282`. Note the dash:
the descriptor writes the title id as `BCUS-98282`, while `PARAM.SFO` writes
it as `BCUS98282`.

The reader is [`tools/ps3disc.py`](../tools/ps3disc.py):

```sh
python tools/ps3disc.py info    "path/to/PS3_DISC.SFB"
python tools/ps3disc.py entries "path/to/PS3_DISC.SFB"
```

## The disc is not a folder

Two things about this disc decide the whole workflow:

1. **The executables are encrypted on the disc.** Reading `E:\PS3_GAME\USRDIR\EBOOT.BIN`
   through the drive gives the NPDRM ciphertext; the first bytes are noise.
   The working copy holds the same program with the payload in the clear, and
   its first bytes are the `SCE\0` header.
2. **The update is not in the working copy.** The disc holds `PS3_UPDATE/PS3UPDAT.PUP`;
   the extracted game tree does not.

Both differences are pinned by hash in [DISC-PROVENANCE.md](DISC-PROVENANCE.md),
so a reader can always tell which side they are looking at.

## What this repository does not hold

No disc image, no ISO, no extracted game tree, no retail executable and no
disc key. The tools read these files where the contributor keeps them; the
repository keeps only the hashes, the sizes and the structure.
