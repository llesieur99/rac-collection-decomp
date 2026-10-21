# The encryption of the executables

The retail executables of a PlayStation 3 disc are protected twice, by two
different keys, and the two layers have to be taken apart in the right order.
This document describes what was measured, how the removal works, and what it
does not recover.

## The two layers

| Layer | What it protects | Which key |
|---|---|---|
| **The disc key** | the files of the disc, assets included | the key of the disc |
| **The SELF encryption** | the metadata and the sections of an executable | the constants of the revision of the container |

The working copy of this project has the first layer removed and the second
one still there. Removing the second one is what this document is about.

## The chain

A retail SELF container protects itself in two steps.

1. The **metadata** — the block that names the sections and the data keys — is
   encrypted with **AES-256-CBC**, under the `erk` and the `riv` of the
   revision of the container. The revision is the `flags` field of the SCE
   header, `0x001C` for the release of this project.
2. The **sections** are encrypted with **AES-128-CTR**, under the data keys
   that the metadata carries. Each section names its key and its counter.

There is a third step for the containers that carry an **NPDRM licence** — a
control information of type 3. The metadata of those containers is encrypted
once more, with **AES-128-CBC**, under a key that comes from the licence file
of the title:

```
licence file --(rap2rifkey)--> rif key --(NP_KLIC_KEY)--> NPDRM key
```

## What was measured

| | The release | A Crack in Time | The standalone titles |
|---|---|---|---|
| Revision of the container | `0x001C` | `0x001C` | `0x0019` |
| Type of the program | `APP` | `NPDRM` | `APP` |
| NPDRM licence header | **none** | yes, local | yes, local |
| Control information | type 1, type 2 | type 1, 2, **3** | type 1, 2, **3** |

The executables of the release carry **no NPDRM licence header**: the two
programs of the collection need only the constants of their revision. The
standalone titles carry one, and their licence file is needed.

## The tool

```sh
python tools/self_decrypt.py <file.self> --keys <keys.json> --out <file.elf>
python tools/self_decrypt.py <file.self> --keys <keys.json> --rap <file.rap> --out <file.elf>
```

`--info` reports the container and stops. The tool prints the section table
it finds, the size of the rebuilt ELF and its hash.

The cipher operations live in `tools/self_crypto.py`: AES-128 and AES-256, the
inverse cipher, CBC and CTR. They are checked against the FIPS-197 vectors
and they fall back on the standard library when the `cryptography` package is
not installed.

## The keys

The tool reads its keys from a **local key file**, which is not committed.
The file holds:

* the `erk` and the `riv` of each revision, keyed by the type of the program
  and the revision: `{"APP:0x001C": {"erk": "...", "riv": "..."}}`;
* the constants of the NPDRM chain, under the `npdrm` key.

Those constants are the ones of `rpcs3/Crypto/key_vault.cpp` and
`rpcs3/Crypto/key_vault.h` in the RPCS3 sources, which are public. They are
**not** key material of a console: the same values are on every PlayStation 3
of that SDK. They are kept out of the repository all the same, because the
repository publishes no key material of any kind — not even the public
constants, and not even in a test.

What is *not* in the key file, and never will be, is the key that is unique
to a console. A container that carries an NPDRM licence needs the licence
file of the title — the `.rap` of the PlayStation Network — and the tool
takes it with `--rap`. The derivation of the NPDRM key from a licence file is
the one RPCS3 implements, and it uses only the public constants.

## The validation

The decryption is checked against the sibling project `rac8-act-decomp`,
whose target is A Crack in Time and whose analysis is public.

The container of A Crack in Time on this machine is byte for byte the file
the sibling publishes: `e69f2b5a053454ef90144d31c3cbb5b6ccfc5399745e9bbb73fca1680b25c81a`.

Decrypting it and rebuilding the ELF gives:

| | The sibling publishes | This project measures |
|---|---|---|
| Size of the rebuilt ELF | 14,515,416 | 14,515,416 |
| Stamps `GCC: (GNU) 4.1.1 (SDK270, $Rev: 3019 $)` | 106 | **106** |
| Stamps `GCC: (GNU) 4.1.1 (SDK250, $Rev: 2824 $)` | 1 | **1** |
| Libraries | Dinkumware, Lua 5.1.2, zlib 1.2.3 | **the same three** |

The analysis of the two projects therefore agrees on every point that can be
compared.

The rebuilt image is not *byte for byte* the one the sibling publishes, and
it cannot be: the parts of the ELF that no encrypted section covers cannot be
recovered from the container. See below.

## What is lost

The **string table of the sections** is not covered by any encrypted section.
It sits in the tail of the container, between the last data section and the
section header table, and no metadata section reaches it: the string table
measures 7.25 to 7.49 bits per byte after the decryption, while the SCE
module names next to it are entirely readable.

So the **names of the sections are lost** in a SELF container. A retail
executable of a PlayStation 3 has no readable section name, and a
decompilation cannot rely on one. The names of the modules — `libc`,
`libstdc++`, `libspurs_stub` and the others — are in the clear, in the region
just before the string table, and they are what `tools/compiler_stamp.py
--modules` reads.

## The result for this project

With the payload in the clear, the programs of the release can finally be
*read*:

* the compiler that produced them is named, with the exact SDK revision;
* the libraries they are built against are named;
* the code is plain PowerPC, and the entry point is a function.

That closes step 2 of the [roadmap](ROADMAP.md) and turns step 1 from a
negative result into a positive one. See [COMPILER.md](COMPILER.md).
