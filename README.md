# Norn Governance

Norn is a small governance system for AI-assisted software development. It separates durable product meaning, current implementation reality, resumable work, and optional evidence so agents can continue reliably without treating chat history or document location as truth.

## Truth model

```text
main specification  → durable product semantics and accepted boundaries
code + tests         → current implementation reality
Git history          → implementation and decision evolution
active plans         → unfinished development state for session/device handoff
appendix             → optional non-authoritative evidence and explanation
```

Only the main specification authorizes durable product behavior. Plans and appendix material can help work continue or explain why, but they cannot override the specification or code facts.

## Skill

Use `$norn-governance` to:

- initialize the current governance structure;
- migrate a recognized legacy Norn structure;
- upgrade Norn-managed rules without overwriting project-owned specifications;
- audit project documents before consolidating them into Norn roles.

Every mutating governance operation begins with read-only analysis and a fingerprint-bound temporary governance transaction. The Skill explains the transaction, obtains confirmation, resolves explicit conflicts, applies it, and reports both what was verified and what remains a human semantic judgment.

## Project structure

```text
AGENTS.md
norn-governance/
  .norn.json
  AGENTS.md
  spec/
    AGENTS.md
    main-spec.md
  plans/                     # created only while unfinished work needs resumption
    YYYY-MM-DD-<task>.md
  appendix/
    README.md
```

`plans/` is not initialized empty and completed plans are not archived. `appendix/` is not required reading for ordinary development.

## Structural migration versus document consolidation

The deterministic engine migrates only recognized Norn governance paths and explicitly authorized legacy `docs/spec/**` or `docs/appendix/**` trees. It guarantees path safety, hashes, conflict handling, and source preservation.

It does not decide what arbitrary project prose means. When a user asks to move or remove all project documentation, the Skill must first classify content:

- durable normative semantics → main specification;
- unfinished development state → active plan;
- historical evidence or explanation → appendix;
- implementation mechanism → code, tests, or deletion of duplicated prose;
- independently useful project documentation → its most useful project location.

Therefore a structurally `current` result does not by itself prove semantic completeness.

## Repository layout

```text
norn-governance/spec/main-spec.md        # canonical product specification for Norn
template/                                # current governed-project template
skills/norn-governance/
  SKILL.md                               # orchestration and semantic decisions
  references/development-plans.md        # conditional plan lifecycle guidance
  scripts/                               # deterministic transaction engine
  assets/                                # current and legacy templates
  tests/
```

The repository copy under `skills/norn-governance/` is canonical. Install or update `~/.codex/skills/norn-governance/` only after repository tests, Skill validation, template comparison, and realistic migration checks pass.

Norn never commits, pushes, creates branches, or changes Git configuration unless the user explicitly requests those actions.
