# The naming

A name is a hypothesis until the code proves it. This document records how
the names of this project are obtained, and why the obvious shortcuts do not
work.

## The rule

The sibling project puts it plainly: *the name is never the evidence*. A
function is named when **what the code at its address must do** agrees with
the name. A name that merely sounds right is a hypothesis, and a hypothesis
stays in the catalogue as such.

For this project the chain is short and it closes:

1. **The evidence.** The code says what the function touches: the strings, the
   functions it calls, the functions that call it, the data it reads.
2. **The proposal.** The evidence suggests a name. A function that touches the
   string `Ratchet` is a candidate for a name about Ratchet.
3. **The source.** The function is written in the form the original author
   would have used.
4. **The proof.** The source is compiled with the qualified profile, linked at
   the measured address, and compared with the retail bytes. **Only a body
   that reproduces the retail bytes carries a name.**

Step 4 is what makes the name a fact. Everything before it is a guess that
happens to be written down.

## Why the shortcuts do not work

The sibling project measured the obvious shortcut and it failed. A prototype
of the engine binds eleven engine symbols to fixed addresses in its linker
script; those addresses were tested against the retail build, and **one name
transfers and ten do not**.

The reason is measurable and not mysterious: the two builds **share a shape,
not a layout**.

| Section | The prototype | The retail build |
|---|---|---|
| CORE `.text` | `0x00115200`-`0x00133a50` | `0x00115200`-`0x00133b4f` |
| CORE `.data` | `0x00133a80`-`0x00139ec0` | `0x00133b80`-`0x0013a1bf` |
| FRONTEND `.text` | `0x001faf80`-`0x00260e10` | `0x0026ea00`-`0x00351fbf` |

The section *names* and the section *order* are the same; the addresses are
not. An address is therefore not a portable name, and a name cannot be
transferred by address — neither from a prototype to a retail build, nor from
the PlayStation 2 originals to the PlayStation 3 builds, nor from one retail
build to another.

The same measurement was made here, on the three titles of the release: the
standalone PlayStation Network titles and the collection's copies are **two
builds of the same programs**, with the same entry points, and their code
sizes differ by hundreds of bytes. The names still have to be proved on each
build.

## The evidence the code carries

The naming evidence of a function is what the analysis of the code finds:

| Evidence | What it gives |
|---|---|
| the strings it touches | the *subject* of the function: a name, a format string, a file name, a message |
| the functions it calls | its *role*: a getter, a setter, a parser, a dispatcher |
| the functions that call it | its *role* seen from the other side |
| the data it reads and writes | the *state* it works on |

The evidence is measured, and it is published: it is research metadata, and it
carries no game bytes.

## The vocabulary of the series

The three titles of the release share the engine with the other games of the
series, and the sibling projects have recovered a good part of that engine's
vocabulary. That vocabulary is a **hypothesis source**: it says what to look
for, and it makes a proposal cheap.

It is never the proof. A name that comes from another project has to be
proved here, on this build, by the body gate. A function that the sibling
project calls `weapon_get_name` and that this project's code also calls
`weapon_get_name` is one name with two pieces of evidence — the string, and
the bytes.

## The state of the names

| | Count |
|---|---|
| functions bounded | 20,939 |
| functions with a proved name | 6 — and those six carry the placeholder of their address, because nothing yet says what they do |
| functions with a proposed name | 0 |

The six proved bodies are the first ones, and they are deliberately the
simplest: a frame, a call, an epilogue. They prove the toolchain and the
method, not the vocabulary.

The next names come from the evidence: a function that touches a string is
named after what the string says, written, and measured.

## What a name is worth

A name is worth what it saves. The engine's vocabulary is large and shared
across the three titles: a name recovered once on one title is a hypothesis
for the other two, and the same *shape* of code appears in all three. A name
that is proved on one title and merely proposed on the other two is already
worth a lot of work.

That is the reason the names are worth the effort, and the reason they are
not transferred by address.
