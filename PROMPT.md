# The starter prompt

This is what an agent reads before it touches the project, and the prompt to
launch a wave.

## The prompt

> You are working on **rac-collection-decomp**, a matching decompilation of
> Ratchet & Clank Collection (PS3, `BCUS98282`).
>
> Read `README.md`, `AGENTS.md`, `docs/METHOD.md`, `docs/EVIDENCE.md`,
> `docs/GATES.md` and `docs/STATE.md` first. Do not skip this.
>
> The retail programs are stripped PPU ELFs. Every function name is a
> hypothesis until the code, its callers or a string proves it. Do not present
> a guess as a fact.
>
> Work in your own lot directory under `work/`. Only the root integrates.
> Change one hypothesis at a time. After three attempts with the same
> mismatch class, stop, recover context, and park the best source with its
> first difference and a concrete reopening condition.
>
> Never commit game data, disc images, retail executables, instruction
> listings, disassembly, assets, console keys, disc keys, licence files, SDK
> sources or personal paths. Run `python tools/check_repository.py` and
> `python -m unittest discover -s tests -v` before you commit, and describe in
> your report what was verified and what remains provisional.
>
> The state of the project is in `docs/STATE.md`. If your work changes it,
> say so in your report; do not rewrite the anchor to make your work look
> finished.

## The checklist of a wave

Before starting:

- [ ] The lot directory is `work/lots/<wave>-<name>/`.
- [ ] The wave is scoped to **one** of the four programs.
- [ ] The functions of the wave are listed, with their current state.

While working:

- [ ] Every boundary claim records its evidence.
- [ ] Every name claim records its evidence.
- [ ] Every comparison is over the **complete** body.
- [ ] Every failure records its first difference and a reopening condition.

Before handing over:

- [ ] The checks pass.
- [ ] The report says what was measured, what is provisional, and what the
      next step needs.
- [ ] Nothing game-derived left the workspace.

## The current wave

**Wave 1 — the naming wave** is finished. The bounding stage is done: 53,456
functions of the four programs are confirmed, 3 addresses are still
candidates, and 319 have been measured and rejected. The naming evidence is
measured: 3,029 functions touch a string, 246 carry an assert that names
their source file and their line, 35,703 have a call graph, and 506 names
are proposed.

**Wave 2 — the frontier wave.** Eight lots, one writer each, all of them
private to their directory under `work/lots/wave2-*/`:

| Lot | Scope |
|---|---|
| `wave2-holes` | the functions the catalogue misses: the returns that fall in a hole |
| `wave2-prologues` | the prologue forms the catalogue does not know |
| `wave2-called` | the most called functions of the engine, which have no naming proof |
| `wave2-verify` | the verification of the 506 proposed names, at scale |
| `wave2-form` | the source form of the body the toolchain cannot reproduce |
| `wave2-toolchain` | the patched compiler, and the way to the revision that was never published |
| `wave2-launcher` | the names of the launcher's functions |
| `wave2-names` | the names of the engine's own symbols, applied to the engine's groups |

The lot directories are private to their writer, and only the root
integrates. A lot that produces names writes them in `config/proposals.tsv`
through the tool that measures them; a lot that produces boundaries writes
them in `config/functions.tsv` through the tool that measures them.
