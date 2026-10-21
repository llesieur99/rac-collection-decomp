# The compiler

The first thing a matching decompilation needs is the compiler that produced
the retail bytes. This document records what was measured about it, and the
fact that **it could not be read out of the executables**.

## The question

Which compiler built the programs of the release, and with which options?

## The measurement

The stamp of a GCC-built object lives in the `.comment` section, once per
linked object. The tool is [`tools/compiler_stamp.py`](../tools/compiler_stamp.py),
and it reads a SELF container or a rebuilt PPU ELF.

| Executable | ELF size | GCC stamp | Toolchain string |
|---|---|---|---|
| `EBOOT.BIN` | 2,255,976 | **none** | **none** |
| `RC1.ppu.self` | 9,764,896 | **none** | **none** |
| `RC2.ppu.self` | 21,070,000 | **none** | **none** |
| `RC3.ppu.self` | 13,337,168 | **none** | **none** |

The search is wide: the four programs hold 3,591, 16,001, 34,455 and 21,594
printable strings of six characters or more, and **not one** of them names a
compiler, an SDK, a revision or a toolchain. The `GCC`, `gcc` and `GNU`
sequences that do appear are noise: they sit inside encrypted payloads and
carry no readable continuation.

The same result comes out of the standalone PlayStation Network titles, whose
executables are a different build of the same games (see
[RELATED-TITLES.md](RELATED-TITLES.md)).

**This is a negative result, and it is a real one.** The sibling project
`rac8-act-decomp` pins a target whose ELF carries 106 stamps of
`GCC: (GNU) 4.1.1 (SDK270, $Rev: 3019 $)`. The programs of this release
carry none, so the compiler cannot be read; it has to be *found*.

## What the executables do carry

The section string table of a retail executable holds the names of the SCE
modules the program is linked against. That is the link map of the program,
and it is measurable and publishable.

For `RC2.ppu.self` — 28 modules:

| Module | Times | What it is |
|---|---|---|
| `libc` | 122 | the C library |
| `libstdc++` | 8 | the C++ library |
| `crt1` | 1 | the C runtime start-up |
| `libsysutil_np_trophy_stub` | 11 | the trophy system |
| `libsysutil_np_tus_stub` | 4 | the PlayStation Store |
| `libsysutil_np_clans_stub` | 3 | the clans |
| `libsysutil_game_stub` | 9 | the game utility |
| `libsysutil_np_avconf_stub` | 2 | the user profile |
| `libsysutil_stub` | 19 | the system utility |
| `libgcm_sys_stub` | 19 | the content manager |
| `libgcm_cmd` | 5 | the content manager commands |
| `libvoice_stub` | 18 | the voice chat |
| `libnet_stub` | 23 | the network |
| `libnetctl_stub` | 7 | the network control |
| `libhttp_stub` | 3 | the HTTP client |
| `libssl_stub` | 4 | the TLS library |
| `libfios` | 15 | the file system |
| `libfs_stub` | 23 | the file system, stubbed |
| `libio_stub` | 7 | the input and output |
| `libaudio_stub` | 8 | the audio |
| `libspurs_stub` | 32 | the SPURS job system |
| `liblv2_stub` | 30 | the low level interface |
| `libl10n_stub` | 2 | the localisation |
| `librtc_stub` | 2 | the real time clock |
| `libm` | 13 | the maths library |
| `libcgb` | 1 | the cell games |
| `libsysutil_np_stub` | 33 | the system utility, stubbed |

What it says, in plain terms: the program is C and C++, it uses the trophy
system, the PlayStation Store, the clans, voice chat, HTTP over TLS, the
content manager, the SPURS job system and the localisation. The number of
times a name appears is the number of times the module is referenced, which
is a rough measure of how much of it the program uses.

`EBOOT.BIN` links 22 modules, `RC1.ppu.self` 26, `RC2.ppu.self` 28,
`RC3.ppu.self` 28, and the standalone `Tools of Destruction` only 15.

## The two variants of the container

The executables of the release and the executables of the standalone titles
use two different shapes of the SELF container. Both were measured.

| | The release | The standalone titles |
|---|---|---|
| Key revision | `0x001C` | `0x0019` (ToD: `0x001C`) |
| Header block | `0x980` | `0xA80` |
| Control information | `0x70` | `0x100` |
| Offset of the encrypted metadata | `0x410` | `0x4A0` |
| Trailer after the ELF | none | 48 bytes |

The rebuild rule is the same for both: the payload starts at the size of the
header block, and the ELF header and the program headers are copied over the
first bytes of the text segment. The payload is cut to the size the header
declares, because the older variant carries a short trailer after the ELF.

## The consequence

Without a stamp, the compiler has to be **found by experiment**: a candidate
is built, and its output is compared with the retail bytes. That is the
toolchain gate of [GATES.md](GATES.md), and it is the second step of
[ROADMAP.md](ROADMAP.md).

There is a second obstacle, and it comes first. The **code and the data of
the retail programs are still NPDRM-encrypted**: the text segment measures
7.99 bits per byte, the data segment 8.00, while the section table measures
1.61 and the module names are readable. The program can therefore be
*measured* — its layout, its sizes, its entry point, its modules — but it
cannot be *read* until the NPDRM layer is removed, and that needs the
console's key material.

The method is public and RPCS3 implements it; the keys are the console's.
See [SELF-FORMAT.md](SELF-FORMAT.md) and [LEGAL.md](../LEGAL.md).

## The tool

```sh
python tools/compiler_stamp.py "path/to/USRDIR/RC2.ppu.self" --modules
python tools/payload_state.py  "path/to/USRDIR/RC2.ppu.self"
```

`compiler_stamp.py` exits 1 when no stamp was found, so that the negative
result cannot be lost in a script. `payload_state.py` measures the entropy
of the segments and says whether the payload is in the clear.
