# The compiler

The first thing a matching decompilation needs is the compiler that produced
the retail bytes. This document records what was measured about it.

## The question

Which compiler built the programs of the release, and with which options?

## The measurement

The stamp of a GCC-built object lives in the `.comment` section, once per
linked object. The tool is
[`tools/compiler_stamp.py`](../tools/compiler_stamp.py), and it reads a SELF
container or a PPU ELF.

| Program | Objects | Stamp |
|---|---|---|
| `EBOOT.BIN` | 124 | `GCC: (GNU) 4.1.1 (SDK400, $Rev: 3538 $)` |
| | 5 | `GCC: (GNU) 4.1.1 (SDK360, $Rev: 3455 $)` |
| `RC1.ppu.self` | 124 | `GCC: (GNU) 4.1.1 (SDK400, $Rev: 3538 $)` |
| | 5 | `GCC: (GNU) 4.1.1 (SDK360, $Rev: 3455 $)` |
| `RC2.ppu.self` | 124 | `GCC: (GNU) 4.1.1 (SDK400, $Rev: 3538 $)` |
| | 5 | `GCC: (GNU) 4.1.1 (SDK360, $Rev: 3455 $)` |
| `RC3.ppu.self` | 124 | `GCC: (GNU) 4.1.1 (SDK400, $Rev: 3538 $)` |
| | 5 | `GCC: (GNU) 4.1.1 (SDK360, $Rev: 3455 $)` |

**The same compiler built the four programs of the release**: the collection
launcher and the three titles come out of the same tree, with the same
toolchain, the same 129 objects and the same two stamps.

The two stamps tell the story of the tree: 124 objects come from the **SDK
400**, and 5 are older, from the **SDK 360**. Those five are the objects that
did not change since the previous revision of the engine — a library, or a
module that was not rebuilt.

The libraries are the ones of the SDK: the Dinkumware C++ library.

## The contrast with the sibling project

The sibling project `rac8-act-decomp` pins a target whose stamps are:

| | Count | Stamp |
|---|---|---|
| A Crack in Time | 106 | `GCC: (GNU) 4.1.1 (SDK270, $Rev: 3019 $)` |
| | 1 | `GCC: (GNU) 4.1.1 (SDK250, $Rev: 2824 $)` |
| **This release** | 124 | `GCC: (GNU) 4.1.1 (SDK400, $Rev: 3538 $)` |
| | 5 | `GCC: (GNU) 4.1.1 (SDK360, $Rev: 3455 $)` |

A Crack in Time is a native PlayStation 3 game, built with the SDK 270. The
release of this project is built with the **SDK 400**, a good deal later. The
two trees are not interchangeable, and neither are their toolchains.

## The lesson of the first pass

The first pass of this search found **nothing**. The four executables of the
release carry no stamp, and neither do the executables of the standalone
titles: a search of every printable string of six characters or more turned
up no compiler, no SDK and no revision.

That result was **an artefact of the encryption**. The `.comment` section is
in the payload, and the payload was still encrypted; a search for a string
inside a ciphertext finds noise. The negative result was correct about the
file it was run on, and wrong about the program.

The rule to keep: *a negative result is only about what was searched*. When
the search cannot reach the data, it says nothing about the data. That is why
`tools/compiler_stamp.py` now exits 1 on a negative result, and why
`tools/payload_state.py` exists: the two together say *the payload was
encrypted* rather than *the program has no stamp*.

## The link map

The section string table of a retail executable is encrypted, but the names of
the modules the program is linked against are not. They lie in the tail of the
image, just before the string table, and they are what the program was built
with. For `RC2.ppu.self` — 28 modules:

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

## The consequence

The compiler is known, so the toolchain gate can finally be attempted. The
profile to qualify is **GCC 4.1.1 for the PowerPC, as the SDK 400 ships
it** — not the SDK 270 of the sibling project, and not the compiler of the
PlayStation 2 titles.

The open-source candidates are the `ps3gcc` sources; the question is which
of them reproduces the code generation of the SDK 400. That is the work of
step 3 of the [roadmap](ROADMAP.md), and it needs a body of known extent to
measure against — which step 4 provides.

## The tools

```sh
python tools/compiler_stamp.py "path/to/USRDIR/RC2.ppu.self" --modules
python tools/payload_state.py  "path/to/USRDIR/RC2.ppu.self"
python tools/self_decrypt.py   "path/to/USRDIR/RC2.ppu.self" --keys work/self-keys.json --out work/rc2.elf
```

`compiler_stamp.py` exits 1 when no stamp was found, so that the negative
result cannot be lost in a script. `payload_state.py` measures the entropy of
the segments and says whether the program can be read at all. Run the
decryption first, or the stamp search will look at a ciphertext.
