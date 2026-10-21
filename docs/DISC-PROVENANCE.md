# Provenance: the disc, the working copy and the hashes

A matching project is only as good as the bytes it measures. This document
records where the working copy comes from, how it relates to the disc, and how
any contributor can check that they are looking at the same thing.

## The finding

**The disc holds the game data encrypted; the working copy holds the same
files in the clear.** The file names are the same, the file sizes are the same,
and the contents differ.

This is not a modification and not a different revision. It is the PS3 disc
encryption: a PS3 disc stores its game files encrypted with a key that belongs
to the disc, and the console decrypts them on the fly. A copy taken with a
tool that knows the disc key holds the plaintext.

**One layer is removed, not two.** The *assets* of the game — the textures,
the movies, the audio, the trophies, the licence data — are in the clear in
the working copy. The *executables* keep their second layer, the NPDRM: their
header, their program headers, their section table and their module names are
readable, but their code and their data are still encrypted. See
[COMPILER.md](COMPILER.md).

The evidence, in the order it was measured:

| | |
|---|---|
| File names | **identical** — 13,148 files on both sides |
| File sizes | **identical** — not one file differs in size |
| The 10 metadata files | **byte for byte identical** (see below) |
| The other 13,138 files | **different content, same size** |
| The content of the copy | **plaintext**: `BIKi` on the Bink movies, `<?xml …` on the credits, `PS3LICDA` on the licence data, `\0PSF` on the metadata |
| The content of the disc | **high entropy**: 7.97 to 7.98 bits per byte on the same files, against 3.02 to 7.25 in the clear |
| The XOR of the two | **no repeating period**, so the cipher is a block or stream cipher and not a simple mask |

A stream cipher preserves the length exactly; that is why every size matches.

## The numbers

| | Disc | Working copy |
|---|---|---|
| Files | 13,149 | 13,148 |
| Total size | 12,429,594,706 | 12,161,159,250 |
| Identical to the other side | 10 | 10 |
| Different content, same size | 13,138 | 13,138 |
| Present only on this side | 1 (`PS3_UPDATE/PS3UPDAT.PUP`) | 0 |

The ten files that are in the clear on the disc are the ones the console has
to read before it can decrypt anything else:

```
PS3_DISC.SFB
PS3_GAME/ICON0.PNG
PS3_GAME/PARAM.SFO
PS3_GAME/PIC1.PNG
PS3_GAME/PS3LOGO.DAT
PS3_GAME/PKGDIR/ICON0.PNG
PS3_GAME/PKGDIR/PARAM.SFO
PS3_GAME/PKGDIR/PKG00/ICON0.PNG
PS3_GAME/PKGDIR/PKG00/INSTALL.PKG
PS3_GAME/PKGDIR/PKG00/PARAM.SFO
```

The package is in the clear too: a `.pkg` carries its own encryption layer,
so the disc does not encrypt it again.

## The two manifests

Both sides are pinned, file by file, in the repository:

| File | What it is |
|---|---|
| [config/disc-manifest.tsv](../config/disc-manifest.tsv) | the retail disc: 13,149 files, the encrypted bytes |
| [config/working-manifest.tsv](../config/working-manifest.tsv) | the analysis target: 13,148 files, the decrypted bytes |

Each line is `sha256`, `size`, `relative path`, tab separated.

The disc manifest is the **retail identity** of the release: a reader who
hashes their own disc must obtain exactly these values, and that is how they
know they have the same disc. The working manifest is the **analysis
identity**: a reader who decrypted their disc must obtain exactly these
values, and that is how they know they are working from the same bytes.

## Checking a copy

```sh
python tools/manifest.py build  "path/to/release" --out work/manifest.tsv
python tools/manifest.py verify "path/to/release" --manifest config/working-manifest.tsv
python tools/manifest.py diff   config/disc-manifest.tsv config/working-manifest.tsv
```

`verify` checks a tree against a manifest. `diff` compares two manifests
without touching a single file, and is how the table above was produced.

## Reading the disc directly

The optical drive of a machine that holds the disc can be hashed without
copying anything: read the files over a remote session, hash them there, and
keep only the manifest. A ready-made script lives in
`tools/disc_manifest.ps1`.

```powershell
powershell -File tools/disc_manifest.ps1 -Root E:\ -Out C:\rac-disc-manifest.tsv
```

The script writes plain UTF-8 with Unix line endings and no byte order mark,
so that the manifest can be read as it is by the tools of the repository.

## The update file

`PS3_UPDATE/PS3UPDAT.PUP` is on the disc and is not in the working copy. It
is 268,435,456 bytes and hashes to
`d03c83dcf22575e220f455eea03a8bbdc33e0c71074b609c719bcb83a7d03042`. It is
the system's own update container; it is not part of this project and must
never be published.

## The keys

Two different keys are involved, and neither belongs here:

* the **disc key** decrypts the game files. It is the key the console knows
  for this disc, and it is what a disc ripper needs;
* the **NPDRM key** protects the metadata of the executables. The working
  copy still carries that layer: the control information of each SELF is
  readable, but the metadata block is still ciphertext.

The method is public in both cases and RPCS3 implements it. The keys belong
to the console and to the person who owns it, and the repository publishes
neither. See [SELF-FORMAT.md](SELF-FORMAT.md) for the NPDRM chain.

## The rules that follow from this

* The working copy is a **reference**, not a deliverable. It stays in the
  workspace, and the repository keeps only hashes and structure.
* No disc key, no licence file and no key material is ever published, here or
  in a pull request.
* A number that is not measured is labelled as derived. The content id in
  `config/target.json` is derived from the title, because the real one is
  encrypted.
* The pinned hashes of the four executables, on both sides, are in
  [config/target.json](../config/target.json) and in
  [SELF-FORMAT.md](SELF-FORMAT.md).
