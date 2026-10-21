# The nonmatching attempts

A useful attempt that does not match belongs here, indexed by the function it
tries to rebuild.

Each attempt is named after the function it targets and carries, in a comment
at the top:

* the **program** it belongs to (`EBOOT.BIN`, `RC1.ppu.self`, `RC2.ppu.self`,
  `RC3.ppu.self`);
* the **address** of the retail body;
* the **first difference** — the address, and both byte values;
* the **reopening condition**: what has to change for the attempt to be tried
  again.

An attempt without a first difference and a reopening condition is not kept;
it is a dead end, and it teaches nobody anything.

These attempts earn no matching credit. They are kept because the next
person should not have to make the same mistake.
