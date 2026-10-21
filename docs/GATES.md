# The gates

A gate is a measurement that decides whether a claim may be promoted. The
gates are ordered: each one is cheaper than the next, and a claim must pass
them in order.

All of them need the private workspace. None of them may be simulated, and a
gate that was not run does not count as passed.

## The toolchain gate

**Question.** Does the qualified toolchain produce bytes the retail compiler
produced?

**What is measured.** The compiler stamp of the rebuilt ELF, the options, the
linker script and the produced bytes, on a body of known extent.

**What passes.** The profile is documented in `config/compiler.json`, the
stamp is identified, and the same profile reproduces at least one complete
body of known extent, byte for byte.

**Where it stands.** The compiler is identified — **SCEI PPC GCC 4.1.1**, the
SDK 4.0 revision — and the profile `-O1 -mno-save-restore-tocbase` already
reproduces one body exactly and four functions of the SDK's runtime
byte for byte. That is a *provisional* qualification: one function is not
enough. See [TOOLCHAIN.md](TOOLCHAIN.md).

## The body gate

**Question.** Does the authored source compile to the retail body, byte for
byte?

**What is measured.** The compiled body and the retail body, over the whole
extent of the retail body:

* the compiled bytes cover the extent exactly: same length, no hole, no
  overlap;
* every byte is equal;
* the first difference, if any, is reported with its address and both byte
  values.

**What passes.** The two byte ranges are equal over the whole extent.

**What does not pass.** A prefix that matches, a masked comparison, or a
comparison against a boundary that was not established.

## The placement gate

**Question.** Does the body land where the retail body lands?

**What is measured.** The link of the program that contains the body, and:

* the address of the body in the linked image;
* the alignment of the body;
* the segment it belongs to;
* the displacement of everything that follows it.

**What passes.** The body is at the retail address, with the retail alignment,
in the retail segment, and the rest of the program is unchanged by its
presence.

**The subtlety.** The text segment of a PS3 PPU ELF starts at file offset
`0x0`: the ELF header itself lives inside the first segment. A file offset is
therefore not an address, and a placement mistake can hide in that confusion.
See [PPU-EXECUTABLE.md](PPU-EXECUTABLE.md).

## The complete-program gate

**Question.** Does the whole program still match once the new body replaces
the old one?

**What is measured.** The complete linked program, compared with the pinned
retail program:

* the program is linked with the authored body in place of the retail body;
* every other byte of the program is unchanged;
* the SHA-256 of the complete program equals the pinned hash.

**What passes.** The hash is the pinned one.

**Why it is the last gate.** It is the only one that cannot be satisfied by a
lucky body. A body that matches on its own but shifts the rest of the
program fails here, and it should.

## The semantics gate

**Question.** Does the source express the retail behaviour?

**What is reviewed.** The source, by a reader who did not write it:

* the values live where the retail code keeps them;
* the order of the operations is the retail order;
* no construct exists only to steer the code generation;
* the bugs of the retail code are preserved.

**What passes.** The review finds nothing that the retail program would not
have contained.

## The counting rule

Credit is counted in **compiled body bytes**, after the boundary and the
semantics have been reviewed. A body that passes the body gate but not the
placement gate does not count. A body that passes the placement gate but not
the semantics gate does not count. One proven zero word of linker alignment
may follow a complete body; it is counted separately.
