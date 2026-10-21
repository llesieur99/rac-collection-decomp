# The related titles

The three titles of the collection also exist as **separate PlayStation
Network titles**, packaged as retail `.pkg` files. Each of them is a second,
independent reference for the same game: another build of the same program,
with another content id and another NPDRM key revision.

This document records what was measured on them and why they matter.

## The three titles

| Title | Content id | Package | Entries | Executable | Key revision |
|---|---|---|---|---|---|
| Ratchet & Clank: Going Commando | `UP9000-NPUA80644_00-RC2REMASTER00100` | 4,158,743,936 | 3,862 | 21,072,608 | `0x0019` |
| Ratchet & Clank: Up Your Arsenal | `UP9000-NPUA80645_00-RC3REMASTER00100` | 4,370,489,088 | 7,409 | 13,339,904 | `0x0019` |
| Ratchet & Clank: Tools of Destruction | `UP9000-NPUA80965_00-TOOLSOFDESTRUCT1` | 16,933,424,960 | 784 | 11,161,440 | `0x001C` |

All three are retail packages: revision `0x8000`, platform PS3, payload
encrypted with AES-128-CTR.

The machine-readable form is in
[config/related-titles.json](../config/related-titles.json), and it is
measured by [`tools/measure_package.py`](../tools/measure_package.py).

## The match with the collection

The trophy directories give the correspondence without ambiguity:

| Title | Content id | Trophy set | In the collection |
|---|---|---|---|
| Going Commando | `NPUA80644` | `NPWR02346` | `USRDIR/rc2` |
| Up Your Arsenal | `NPUA80645` | `NPWR02347` | `USRDIR/rc3` |
| Tools of Destruction | `NPUA80965` | — | `USRDIR/rc1` |

The collection's `TROPDIR` holds `NPWR02335`, `NPWR02346` and `NPWR02347`,
and the two standalone packages that carry trophies use `NPWR02346` and
`NPWR02347`. The layout of the packages matches the layout of the
collection: `USRDIR/rc2/ps3data/level0` … `levelN`, each with `audiowad` and
`scene[0]` … `scene[5]`.

## They are different builds

The executable of the collection and the executable of the standalone title
are **not** the same bytes. The comparison is structural, because the code
is encrypted on both sides — and now that the encryption is removed, it is
exact:

| | Collection | Standalone |
|---|---|---|
| `rc2` / Going Commando | text `0x12C7968`, data mem `0x1020F8` | text `0x12C76E8` (0x280 smaller) |
| `rc3` / Up Your Arsenal | text `0xBB2EE8` | text `0xBB2468` (0xA80 smaller) |
| Entry point | `0x12E38A8` | `0x12E38A8` — **the same** |
| Compiler | 124 × SDK 400, 5 × SDK 360 | 124 × SDK 400, 5 × SDK 360 — **the same** |

The entry point of the two Up Your Arsenal builds is identical while the
text segment is 2,688 bytes shorter, and both were built with the same
toolchain: they are two builds of the same program from the same source, made
with different settings.

**Tools of Destruction is the exception, and the exception is telling.**

| | Collection `rc1` | Standalone `NPUA80965` |
|---|---|---|
| Size of the ELF | 9,764,896 | 11,158,696 |
| Compiler | 124 × SDK 400, 5 × SDK 360 | 24 × **CELL 4.1.2.7** rev 1826, 8 × **CELL 4.1.2.7** rev 1830 |
| Modules | 26 | 15 |

The standalone Tools of Destruction was built with a **different toolchain
altogether** — the `CELL` branch of the SDK, which is an earlier
configuration — and it is 1.4 megabytes larger. The `rc1` of the collection
is a **rebuild** of the game with the SDK 400, not the program that the
standalone title carries.

That is worth knowing before anything is ported from one to the other: for
Tools of Destruction, the two are not the same program, and the collection
carries the newer one.

The NPDRM key revision tells the order for the other two: `0x0019` for the
standalone titles, `0x001C` for the collection, and `0x001C` again for the
standalone Tools of Destruction. The standalone Going Commando and Up Your
Arsenal are the **older** builds; the collection ships newer ones.

## Why they matter

1. **A second reference for the same code.** When a name, a layout or a
   behaviour is recovered from one build, the other build either confirms it
   or shows that it moved. That is a cheap, strong form of evidence.
2. **The content id convention.** The three ids show the shape of a PS3
   content id: `UP9000-<title id>_00-<name>`, the name being sixteen or
   seventeen characters with a four digit suffix. The release follows the
   same convention, and its own content id is therefore very likely
   `UP9000-BCUS98282_00-RATCHETCLANK0001`. That value is still a
   **derivation**: the real one is encrypted in the NPDRM metadata.
3. **The licence files.** Each package comes with a `.rap` file named after
   its content id. The method is public and RPCS3 implements it; the keys
   belong to the console.

## Reading them

```sh
python tools/pkg.py inspect "path/to/the.pkg"
python tools/pkg.py list    "path/to/the.pkg" --pattern TROPDIR
python tools/measure_package.py --pkg "path/to/the.pkg" --out work/pkg.json
python tools/self_decrypt.py "path/to/EBOOT.BIN" --keys work/self-keys.json --rap work/<content id>.rap --out work/gc.elf
```

Hashing a whole package is optional: they run from 4 to 17 gigabytes, and
reading one of them over a network takes hours. The hash of the executable
is always computed, because that is the part the project measures.

The three titles carry an NPDRM licence, so their decryption needs the
licence file of the title — the `.rap` of the PlayStation Network. See
[NPDRM.md](NPDRM.md).

## What is not published

No package, no extracted program, no licence file and no key material. The
repository keeps the content ids, the sizes, the hashes of the executables
and the module lists.
