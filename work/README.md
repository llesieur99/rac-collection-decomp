# The private workspace

Everything that is game-derived, or that is a work in progress, stays here.
Nothing in this directory is committed: the `.gitignore` covers it, and the
repository guard checks it.

## What belongs here

| Path | Content |
|---|---|
| `work/pkg/` | the packages, when the target is a package rather than a disc |
| `work/elf/` | the PPU ELFs rebuilt from the SELF containers |
| `work/lots/` | the lot directory of each writer |
| `work/analysis/` | the analysis projects |
| `work/gate/` | the gate measurements |
| `work/manifest.tsv` | the manifest of the local copy |

## What must never come here

Nothing, except by accident. The console key material, the licence files and
the disc keys never enter the workspace of the repository either: they belong
to the machine and to the person who owns the console.

## The lot

A lot is the private directory of one writer, working on one wave:

```
work/lots/<wave>-<name>/
├── notes.md        the hypotheses, in the order they were tried
├── sources/        the attempts
└── report.md       what was verified, what is provisional, what is next
```

Only the root integrates. A lot is merged after its own functions pass the
gates.
