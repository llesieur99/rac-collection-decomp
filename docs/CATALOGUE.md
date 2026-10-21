# The function catalogue

The catalogue is the index of the functions of the four programs: where they
are, what they are called, and how that is known. It is the reference that
lets a contributor find the function they need without re-deriving the whole
program.

The catalogue is **not** a disassembly. It is a table of claims, each backed
by evidence, and it names a function only when the evidence is there.

## The columns

| Column | Meaning |
|---|---|
| `program` | which of the four executables the function belongs to |
| `address` | the virtual address of the first instruction |
| `size` | the length of the body, in bytes |
| `name` | the proposed name, or the placeholder `func_<address>` |
| `state` | `unbounded`, `bounded`, `named`, `nonmatching` or `matching` |
| `evidence` | what proves the boundary and the name |

`config/functions.tsv` holds the machine-readable form, one row per
function, tab separated.

## Recovering a boundary

The retail programs are stripped: there is no symbol table and no
conventional section name. A boundary therefore has to be **proved** by the
bytes.

A **start** is proved by one of:

* a `bl` (branch and link) instruction that targets the address;
* a reference from the SCE dynamic table;
* a reference from a data word that is known to hold a function pointer;
* the entry of a table of function pointers whose other entries are already
  bounded.

A **end** is proved by one of:

* a `blr` (branch and link register) that returns to the caller, followed by
  the padding that the linker inserted;
* a branch to a known address;
* a trap or a return that no path can fall through from.

A boundary that is only "the next known boundary" is **provisional**. It is
recorded as such, and it is not counted.

## Recovering a name

A name is a hypothesis until one of these proves it:

* a symbol or a string literal that the function references;
* a caller that names its callee;
* a sibling program that carries a name for the same code;
* a matching decompilation of the same engine in another title of the series.

The fourth one is the strongest lead this project has: the collection is
built on the same engine as the other Ratchet & Clank titles, and the sibling
projects have already recovered a good part of that engine's vocabulary.

A name that is only plausible is kept with a marker that says so. It is never
presented as proven.

## The state of the catalogue

**Empty, and that is honest.** No boundary has been recovered yet, because the
toolchain has not been qualified and the work has not started. The table
exists so that the first wave has somewhere to write.

The order of the work is in [ROADMAP.md](ROADMAP.md).

## The tools

`tools/ppu_elf.py` gives the raw material:

```sh
python tools/ppu_elf.py sections work/eboot.elf
python tools/ppu_elf.py catalogue work/eboot.elf --out work/catalogue.tsv
```

The catalogue writer itself belongs to the first wave: it needs the entry
convention and the naming rules of this project, which are still being
qualified. Until then, the catalogue is maintained by hand in
`config/functions.tsv`, and the tool is a later step of the roadmap.
