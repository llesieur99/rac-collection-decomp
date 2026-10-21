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

There is no wave in progress. The work has not started: the compiler has not
been qualified, so no boundary is known yet. See `docs/ROADMAP.md` for the
ordered steps and what each of them needs.

When the first wave starts, this section is where its scope is announced.
