# The accepted source

One authored C/C++ definition per function, in the form the original author
would have used.

A function lives here only when it has passed the body gate, the placement
gate, the complete-program gate and the semantics gate. See
[docs/GATES.md](../docs/GATES.md).

The layout follows the sibling projects: one file per function, named after
the function, with the address of the retail body in the name when the
function has no proven name yet.

```
src/
├── core/
├── game/
└── levels/
```

Nothing game-derived goes here: no retail code, no disassembly, no extracted
module. The source is written, not recovered.
