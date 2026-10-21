# The toolchain

A matching decompilation is only possible with the compiler that produced
the retail bytes. This document records which one that is, how it was built
here, and what it has already reproduced.

## The answer

The retail executable names its compiler itself, once per linked object, in
the `.comment` section:

| Stamps | Compiler |
|---|---|
| 124 | `GCC: (GNU) 4.1.1 (SDK400, $Rev: 3538 $)` |
| 5 | `GCC: (GNU) 4.1.1 (SDK360, $Rev: 3455 $)` |

So the release was built with **Sony's PPC GCC 4.1.1**, from the PlayStation 3
SDK, revision `SDK400` (the SDK's own revision `3538`). Five objects are
older, from the SDK 3.6.0.

The stamp is read with the published tool, so the answer is reproducible:

```sh
python tools/compiler_stamp.py work/decrypted/eboot.elf --libraries
```

## The build

The Cell OS Lv-2 toolchain is GCC 4.1.1 with the Cell target. Its sources
are published by [sagemono/ps3gcc](https://github.com/sagemono/ps3gcc), at
the tag `toolchain-src-2.7.0-GCC411`. It builds on an ordinary Linux
system, with a host compiler old enough to build GCC 4.1.1 — a Debian jessie
container is a good middle ground.

The build needs the usual workarounds of an old package: the `makeinfo` of
today refuses the Texinfo files of the old binutils, the SDK's thread support
needs the SDK's own C library headers, and the old binutils cannot do a
separate-directory build. The script that does all of this lives in the
contributor's workspace, not here.

The result reports itself as:

```
ppu-lv2-gcc (GCC) 4.1.1 (SDK270, $Rev: 3019 $)
```

The stamp of the build is the SDK 2.7.0 one, while the retail program was
built with the SDK 4.0. The compiler is the same GCC 4.1.1, and the
difference of the stamp does not show in the code: the flag set below
reproduces the retail bytes exactly.

**The toolchain is a tool.** It is built by the contributor, it stays in the
workspace, and the repository never ships it, an SDK header or an SDK
library. What the repository holds is the written result.

## The flags

| Flag | Why |
|---|---|
| `-O1` | the optimisation level of the retail build |
| `-mno-save-restore-tocbase` | **the one that matters**: without it the compiler keeps a TOC base and a back chain in the frame, which the retail code does not have |

At `-O2` the same function differs by two instructions: the compiler restores
the stack pointer before the link register, where the retail code does the
opposite.

## What it has already reproduced

### One body, byte-exact

`src/text/module_init.c` — the first function of the launcher, at `0x10200`,
44 bytes:

```sh
python tools/try_body.py work/gate/module_init.c 0x10200 \
    --elf work/decrypted/eboot.elf \
    --symbol sub_147B0=0x147B0 --symbol sub_14820=0x14820
match: 44 bytes at 0x10200
```

### Four functions of the SDK's runtime, byte-identical

The retail executable links libgcc statically, so the SDK's own runtime is in
the text segment. Every function of our build of the runtime that is found
in the retail text is byte-identical to the one the game runs — and no
source has to be written for that check:

| Function | Bytes | At retail |
|---|---|---|
| `_Unwind_DeleteException` | 80 | `0x000C9734` |
| `fde_unencoded_compare` | 40 | `0x000CCBAC` |
| `read_sleb128` | 88 | `0x000C96A4` |
| `read_uleb128` | 56 | `0x000C966C` |

```sh
python tools/compare_libgcc.py --elf work/decrypted/eboot.elf
```

The other functions of the library are simply not linked into the program:
the linker only pulls what the program needs, so their absence from the retail
executable is not a difference.

## The state of the qualification

**Provisional.** One body is not enough to qualify a build: the profile
holds on one function and on the runtime's four, and it has to hold on more
of the game's own code before it can be called qualified.

The toolchain gate of [GATES.md](GATES.md) stays open until then.

## The two routes

| Route | What it gives |
|---|---|
| **A — the byte-exact route** | this toolchain: the bytes can be compared, and a match is a proof |
| **B — the open route** | `ps3dev/ps3toolchain` (GCC 9 or 13 with the PPU patches) and `rpcs3/PS3DK`: legal, and they build a *semantic* reconstruction, but GCC 9 lays the code out differently from GCC 4.1.1, so the body gate cannot be closed with them |

The two are not exclusive: the sources written for route B are the same
sources route A has to match, and the project's rules — authored form, no
assembly, original behaviour — are the same in both.
