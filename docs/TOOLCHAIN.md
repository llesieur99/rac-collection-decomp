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
the tags `toolchain-src-2.7.0-GCC411` and `toolchain-src-4.2.0-GCC411`. It
builds on an ordinary Linux system, with a host compiler old enough to build
GCC 4.1.1 — a Debian jessie container is a good middle ground.

The build needs the usual workarounds of an old package: the `makeinfo` of
today refuses the Texinfo files of the old binutils, the SDK's thread support
needs the SDK's own C library headers, and the old binutils cannot do a
separate-directory build. The script that does all of this lives in the
contributor's workspace, not here.

Two builds were made here, and both work:

| Build | Stamp | Note |
|---|---|---|
| SDK 2.7.0 | `GCC 4.1.1 (SDK270, $Rev: 3019 $)` | the build of the sibling project |
| SDK 4.2.0 | `GCC 4.1.1 (SDK420, $Rev: 3547 $)` | built here, the closest to the target |

The stamp of a build is the SDK's own revision, while the retail program was
built with the SDK 4.0, revision `3538`. The compiler is the same GCC 4.1.1,
and the difference of the stamp does not show in the code: both builds
reproduce the retail bytes exactly.

**The toolchain is a tool.** It is built by the contributor, it stays in the
workspace, and the repository never ships it, an SDK header or an SDK
library. What the repository holds is the written result.

## The flags

| Flag | Why |
|---|---|
| `-O1` | the optimisation level of the retail build |
| `-mno-save-restore-tocbase` | **the one that matters**: without it the compiler keeps a TOC base and a back chain in the frame, which the retail code does not have |
| `-mno-nop-after-bl` | **the second one**, and it is not used everywhere |

At `-O2` the same function differs by two instructions: the compiler restores
the stack pointer before the link register, where the retail code does the
opposite.

### The two shapes of a call

The SCE backend emits a call as the branch **and a second word that restores
the TOC** — eight bytes in all. The option `-mno-nop-after-bl` drops that
second word, and the call is four bytes long:

```
 eight bytes                        four bytes
 4803824D   bl 0x8954C               4BFFFF61   bl 0x2CE90
 60000000   nop                      E8010080   ld  r0,0x80(r1)
 E8010080   ld  r0,0x80(r1)
```

The launcher holds **both** shapes: the eight byte call in `0x512F4` and
`0x143158`, the four byte one in `0x2CF24`, `0x4EB7C` and `0x68088`. The game
was therefore built with the option **on some files and off on others**, and
which one a file uses is visible in its code.

That is the whole difference between the two profiles:

| Profile | Bodies |
|---|---|
| `-O1 -mno-save-restore-tocbase` | `0x10200`, `0x512F4`, `0x143158` |
| `-O1 -mno-save-restore-tocbase -mno-nop-after-bl` | `0x2CF24`, `0x4EB7C`, `0x68088` |

## What it has already reproduced

### Six bodies, byte-exact

| Function | Address | Bytes | Profile |
|---|---|---|---|
| `module_init` | `0x10200` | 44 | the eight byte call |
| `func_512F4` | `0x512F4` | 36 | the eight byte call |
| `func_143158` | `0x143158` | 36 | the eight byte call |
| `func_2CF24` | `0x2CF24` | 32 | the four byte call |
| `func_4EB7C` | `0x4EB7C` | 32 | the four byte call |
| `func_68088` | `0x68088` | 32 | the four byte call |

The sources are in `src/text/`, and each one carries the command that proves
it.

```sh
python tools/try_body.py work/gate/func_2CF24.c 0x2CF24 \
    --elf work/decrypted/eboot.elf --symbol sub_2CE90=0x2CE90
match: 32 bytes at 0x2CF24
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

**Provisional, but no longer thin.** Six bodies of the launcher and four
functions of the SDK's runtime are byte-exact, and the profiles hold on both
shapes of the call.

The strongest evidence is the **cross-check between two toolchains**. The
bodies are reproduced by the SDK 2.7.0 compiler *and* by the SDK 4.2.0 one,
which are two different builds of the same GCC:

| Toolchain | Stamp | Bodies reproduced |
|---|---|---|
| SDK 2.7.0 | `GCC 4.1.1 (SDK270, $Rev: 3019 $)` | 6 of 6 |
| SDK 4.2.0 | `GCC 4.1.1 (SDK420, $Rev: 3547 $)` | 6 of 6 |

Two independent builds of the compiler producing the same bytes is a much
stronger statement than one build producing them once. The target itself was
built with the SDK 4.0, whose revision `3538` sits between the two.

What is still missing: the bodies are all of the same shape — a frame, a
call, an epilogue. The gate stays open until the profile holds on bodies
with arguments, with branches and with arithmetic, and until the
complete-program gate can be attempted.

The toolchain gate of [GATES.md](GATES.md) stays open until then.

## The two routes

| Route | What it gives |
|---|---|
| **A — the byte-exact route** | this toolchain: the bytes can be compared, and a match is a proof |
| **B — the open route** | `ps3dev/ps3toolchain` (GCC 9 or 13 with the PPU patches) and `rpcs3/PS3DK`: legal, and they build a *semantic* reconstruction, but GCC 9 lays the code out differently from GCC 4.1.1, so the body gate cannot be closed with them |

The two are not exclusive: the sources written for route B are the same
sources route A has to match, and the project's rules — authored form, no
assembly, original behaviour — are the same in both.
