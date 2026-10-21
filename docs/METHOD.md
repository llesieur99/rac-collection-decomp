# The method

This project rebuilds the retail programs of the **Ratchet & Clank Collection**
in C/C++ and proves the rebuild by comparing the compiled bytes with the
retail bytes.

The method is the one of the sibling projects (rac1-decomp, rac2-gc-decomp,
rac5-sm-decomp, rac-sac-decomp, rac8-act-decomp), adapted to the PS3.

## The shape of the work

```
  measure  ->  bound  ->  name  ->  author  ->  compare  ->  promote
```

1. **Measure.** Read the container, rebuild the PPU ELF, pin the hashes.
2. **Bound.** Find where a function starts and where it ends, and record the
   evidence.
3. **Name.** Propose a name, and justify it from the code, its callers or a
   string it references.
4. **Author.** Write the function in C/C++, in the form the original author
   would have used.
5. **Compare.** Compile it with the qualified toolchain and compare the bytes.
6. **Promote.** Only when the gates pass does the function move to `src/`.

A step may send you back. That is the point: the loop is the work.

## The waves

The work is organised in **waves**. A wave is a lot of functions of the same
kind, taken from the same program, worked by one writer in one lot
directory.

A wave has:

* a **lot directory** under `work/lots/`, private to its writer;
* a **foundation lot**: the first lot of a wave, which establishes the
  compiler profile, the baseline and the conventions the other lots follow;
* a **catalogue entry** per function, in `config/`, naming the program, the
  address, the size, the evidence and the state of the function.

A lot is merged into `src/` by the root integrator only, after its own
functions pass the gates.

## Where the work stands now

The measurement stage is done for the container formats. The bounding stage
has not started: the four executables are stripped, so no function boundary
is known yet.

The next step is therefore the **toolchain qualification**: without a PPU
compiler that reproduces retail bytes, no comparison can be made, and the
gates stay closed. See [ROADMAP.md](ROADMAP.md).

## The comparison

A comparison is only meaningful against a **complete** retail body at a
**known** placement. Comparing a prefix, comparing masked bytes, or comparing
against a boundary that was guessed is not evidence. The rules are in
[EVIDENCE.md](EVIDENCE.md) and the measurements are in [GATES.md](GATES.md).

## The four programs

The release carries four programs. A wave belongs to one of them, and a
function belongs to exactly one:

| Program | Role |
|---|---|
| `EBOOT.BIN` | the collection launcher |
| `RC1.ppu.self` | Ratchet & Clank (2002) |
| `RC2.ppu.self` | Ratchet & Clank 2: Going Commando |
| `RC3.ppu.self` | Ratchet & Clank 3: Up Your Arsenal |

The three titles share an engine, and the engine is where the interesting
matching work is. A name recovered on one program is a **hypothesis** until the
same name is confirmed on the others, which is itself evidence.

## What is not matching work

* A **port**: making the game run on a PC is a separate goal with separate
  rules. It earns no matching credit, and it must live in a separate tree.
* A **fix**: the retail behaviour, including its bugs, is preserved. A fix
  belongs to an explicitly separate change.
* A **tool**: the readers and the comparators are welcome, but they are not
  evidence of a match.
