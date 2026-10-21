# Contributing

Thank you for helping. This project follows the evidence standard of the
sibling Ratchet & Clank decompilation projects; the short version is below.

## The one rule that matters

**A claim is a measurement or it is a hypothesis.** Say which one it is, and
back it with something another person can repeat.

## What to send

* **Authored source** for a function, in `src/`, when it passes the gates.
* **A useful attempt** that does not match, in `nonmatching/`, indexed by the
  function it belongs to.
* **A tool** in `tools/`, with its tests in `tests/`.
* **A measurement** in `config/`, produced by a tool rather than typed.
* **A document** in `docs/`, in English.

## What not to send

Disc images, packages, retail executables, extracted modules, instruction
listings, disassembly, assets, proprietary tools, build output, console keys
or licence files, disc keys, SDK sources or headers, leaked or NDA source,
and personal paths.

The guard is structural, and it is not a substitute for reading your own
diff. Run it before you commit:

```
python tools/check_repository.py
python -m unittest discover -s tests -v
```

## The style of the source

* One authored definition per function, in `src/`.
* No inline or global assembly, no fixed-register bindings, no raw
  instruction words, no artificial assembly barriers, and no edit to the
  compiler output.
* The retail behaviour is preserved, bugs included. A fix is a separate
  change and earns no matching credit.
* The code is written in the form the original author would have used: the
  values live where the retail code keeps them, and the operations happen in
  the retail order.

## The style of the text

Public text is English. A function name is stable once it is proven; a
descriptive alias needs evidence like any other name.

## The pull request

Describe:

1. **what** was done, program by program;
2. **what was measured** — the hashes, the gates, the checks;
3. **what remains provisional** — the boundaries, the names, the claims that
   are still hypotheses;
4. **what the next step needs**.

A pull request that claims a match without naming the gates it passed is not
ready.

## The licence

The independently authored material here is GPL-3.0. Contributions should be
original or compatible with that licence, with attribution where required.
Do not contribute game code, assets or anything derived from them; see
[LEGAL.md](LEGAL.md).
