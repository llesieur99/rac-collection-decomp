# Legal

## What this repository is

An unofficial fan project that studies the executable structure of a game the
contributors own, in order to document it and to preserve the knowledge of
its engine.

## What this repository is not

It is **not** affiliated with, endorsed by, or supported by Sony Interactive
Entertainment, Insomniac Games, or any of the other projects of this series.
It is not a product, and it is not a service.

## What this repository contains

Only material that the contributors authored or that they are allowed to
redistribute:

* written C/C++ source of the contributors, under GPL-3.0;
* reusable tools, under GPL-3.0;
* research metadata: identifiers, offsets, sizes, hashes, and the description
  of a file format;
* documentation.

## What this repository does not contain, and never will

* disc images, ISO images, packages, or extracted game trees;
* retail executables, in any form, encrypted or not;
* instruction listings, disassemblies, decompilations of the retail code, or
  extracted modules;
* game assets: models, textures, audio, video, scripts, fonts;
* console key material, licence files, disc keys, or the key vault;
* proprietary toolchains, SDK sources, or SDK headers;
* leaked or NDA source.

`tools/check_repository.py` enforces this structurally, and it runs in the
continuous integration. It is a guard, not a guarantee: read your own diff.

## Where the game comes from

You need your own lawful copy. This project cannot supply one, and it will
not. The tooling and the receipts of the operations stay on the machine of
the contributor.

## Reading the executables

The decryption of the retail executables is described in
[docs/SELF-FORMAT.md](docs/SELF-FORMAT.md), and the method is public: it is
the one RPCS3 implements. What the project does not publish is the key
material, which belongs to the console and to the person who owns it. A
contributor with their own console follows the RPCS3 path and keeps the
result in their own workspace.

## Trade marks

Ratchet & Clank is a trademark of Sony Interactive Entertainment. The game was
developed by Insomniac Games. Other names mentioned in the documentation
remain the property of their owners. This project is not affiliated with, or
endorsed by, any of them.

## The licence of this repository

GPL-3.0, like the sibling projects. See [LICENSE](LICENSE). That licence
covers the independently authored material only. It does **not** cover the
game, its assets, any console key material or any proprietary toolchain, and
it grants no right to redistribute them.

## Reporting a problem

If you believe this repository holds something it should not, open an issue
without quoting the material itself. It will be removed.
