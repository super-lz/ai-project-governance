# Norn Governance main specification

- Decision status: **Accepted**
- Current delivery scope: **Governance model version 4**
- Implementation status: **Implemented in this repository**

This file is Norn's semantic authority. Code and tests describe the current implementation, Git records evolution, active plans preserve unfinished development state, and appendix material—when present—provides non-authoritative evidence only.

## Product purpose and user outcome

Norn enables a developer and coding agents to continue real software work across conversations and devices without making chat history, temporary plans, or scattered documentation authoritative.

The completed user outcome is a repository where:

- one discoverable main specification preserves the product's durable purpose and accepted semantic boundaries;
- current code and tests expose implementation reality;
- Git preserves the evolution of both specification and implementation;
- unfinished work can travel with its development branch through a concise active plan;
- optional historical evidence cannot silently authorize current behavior;
- governance initialization, migration, and upgrades are safe, reviewable, and repeatable.

## Durable authority model

### Main specification: product soul

`norn-governance/spec/main-spec.md` is the semantic authority. It records the real user outcome, accepted scope, invariants, flows, states, contracts, failures, safety boundaries, and acceptance criteria that must survive changes in language, framework, host, or code organization.

The main specification may index subordinate specifications only after stable independent system boundaries make a single file materially harder to understand. It remains the authoritative entry point.

### Code, tests, and Git: implementation reality and evolution

Current reachable code and tests show how the accepted specification is implemented. Git history records when and why specification and implementation changed. Neither chat nor a plan replaces source inspection or version history.

When stable code behavior is ahead of the specification, the same change must reconcile the specification. When the intended behavior is ambiguous, a product decision is required rather than choosing whichever source is convenient.

### Main specification synchronization notices

Norn makes consequential specification actions visible without emitting a status banner on ordinary replies:

- When a new or changed durable requirement still needs developer confirmation, the notice begins with `🚨`, enumerates the exact semantic changes proposed for the main specification, and explicitly asks whether to confirm or adjust them. An explicit confirmation already present in the current context satisfies this boundary and is not requested again merely for presentation.
- When reachable code and tests prove an omitted stable behavior and the specification edit is within the developer-authorized change scope, Norn updates the main specification in the same change. Only after the file is actually edited does the notice begin with `⚠️` and enumerate only the semantic writebacks completed.
- When there is no proposed or completed specification writeback, Norn emits no synchronization notice. It never uses `🔵`, “no writeback”, “no changes found”, or another placeholder status, and it never claims synchronization without an actual main-specification content change.

These notices do not alter the authority model, confirmation boundary, automatic omission-repair conditions, or governance transaction authorization.

### Active plans: resumable unfinished development

`norn-governance/plans/` contains one concise file per active development task when work is expected to continue across a session or device, or when dependent checkpoints make reconstruction materially risky.

A plan is written only after inspecting the relevant specification, code, tests, and Git state. It records an observable outcome, explicit acceptance-bound requirements and non-goals, a verified baseline, ordered target-specific implementation steps, validation state, blockers, and one exact next action. It is temporary navigation, not product authority, implementation truth, history, or reusable execution permission.

Plans may travel with a development branch when the user authorizes commit and push. They are updated at meaningful checkpoints and deleted on completion or cancellation after durable outcomes are captured in the specification, code, tests, and Git history. Blocked plans may remain only with an explicit unblock condition and resume action. Empty plan directories, indexes, and completed-plan archives are forbidden.

### Appendix: optional evidence

`norn-governance/appendix/` contains only non-normative evidence or explanatory aids needed to trace why an accepted boundary exists. Normal development must not require reading it.

Any current rule found only in appendix means the main specification is incomplete. Promote the rule into the specification, retain only useful historical evidence, and delete duplicated or misleading prose.

## Governed project structure

```text
AGENTS.md
norn-governance/
  .norn.json
  AGENTS.md
  spec/
    AGENTS.md
    main-spec.md
  plans/                     # optional while tasks are active
    YYYY-MM-DD-<task>.md
  appendix/
    README.md
```

The fixed initialization set excludes `plans/`. The appendix README exists to state its non-authoritative contract; project evidence files are optional.

## User workflows

### Initialize

For a project without Norn or a recognizable legacy Norn structure:

1. inspect existing repository rules and content;
2. establish or confirm the product purpose, current delivery boundary, and acceptance criteria;
3. generate a fingerprint-bound governance transaction;
4. semantically merge a custom root `AGENTS.md` when necessary;
5. apply only after confirmation;
6. verify the governed structure and disclose the limits of machine verification.

Initialization must not populate a project-owned main specification with guessed business content.

### Migrate a legacy Norn structure

The deterministic engine recognizes only this fixed legacy mapping by default:

```text
docs/AGENTS.md                 → norn-governance/AGENTS.md
docs/spec/AGENTS.md            → norn-governance/spec/AGENTS.md
docs/spec/main-spec.md         → norn-governance/spec/main-spec.md
docs/appendix/README.md        → norn-governance/appendix/README.md
```

Legacy ownership requires a known template hash or a complete governance evidence chain; matching path names alone are insufficient.

The user may explicitly authorize recursive processing of legacy `docs/spec/**`, `docs/appendix/**`, or both after the Skill lists every affected file. Ordinary files move byte-for-byte; target collisions, abnormal parents, symbolic links, and special files block execution. Other project documentation remains outside the machine transaction.

### Consolidate project documentation

Adopting Norn does not mean moving every Markdown file under `norn-governance/`. When the user requests a full documentation migration or removal of a legacy documentation tree, the Skill must read the affected files and present a content-disposition review before editing:

| Content role | Destination |
|---|---|
| Current durable product or architecture semantics | Merge into `spec/main-spec.md` or an indexed subordinate specification |
| Active unfinished development state | `plans/YYYY-MM-DD-<task>.md` |
| Historical rationale or necessary explanatory evidence | `appendix/` |
| Current implementation mechanism | Code, tests, necessary comments, or deletion of duplicate prose |
| Independent user-facing or operational documentation | Its most useful project location |

Classification follows content, not filename or source directory. Mixed-role documents must be split or consolidated. The developer confirms semantic writeback, retained evidence, active plans, deletions, and any remaining independent documents before changes apply.

### Upgrade

Norn owns stable managed blocks in four Markdown entry files and the manifest. Project-specific rules live outside those blocks. `main-spec.md`, active plans, appendix evidence, and project extensions are project-owned.

When an installed managed block matches its recorded baseline, it may upgrade automatically. A modified block requires an explicit `keep-current`, `adopt-template`, or hash-bound `semantic-merge` choice. Upgrades never overwrite the project-owned main specification.

## Skill and deterministic engine boundaries

### Skill orchestration

The Skill owns intent interpretation, repository and document reading, content-role classification, semantic merge judgment, user-facing action summaries, confirmation, and final semantic audit.

### Deterministic governance transaction

The engine owns fixed governed-path discovery, path fingerprints, SHA-256 binding, structural state classification, rendered artifacts, conflict binding, safe writes, source deletion after target verification, manifest generation, and structural verification.

Its temporary `transaction.json` lives outside the target repository and must never be confused with `norn-governance/plans/`.

The engine must report both its guarantees and exclusions. A result of `current` means only that the Norn-managed structure and template version are current. It does not prove:

- completeness or correctness of product semantics;
- correct content classification of arbitrary documents;
- agreement between specification and implementation;
- code correctness or test success;
- validity of an active development plan.

## Structural states

- `uninitialized`: no current or recognizable legacy Norn structure exists.
- `current`: manifest, managed paths, and template version are structurally current.
- `upgradeable`: valid Norn metadata exists at an older template version.
- `legacy`: recognized legacy Norn structure has not migrated.
- `mixed`: current and legacy governance paths coexist.
- `ambiguous`: ownership evidence is insufficient.
- `conflict`: target paths, file types, managed blocks, or content cannot be safely resolved automatically.

These are structural states, never product maturity or semantic-quality states.

## Governance transaction contract

Every mutating governance operation follows:

1. read-only analysis;
2. a per-path transaction containing fingerprints, ownership evidence, output hashes, actions, risks, and verification conditions;
3. a natural-language explanation and explicit confirmation;
4. conflict resolution bound to the same transaction and rendered artifact hashes;
5. complete precondition revalidation immediately before apply;
6. staged and atomic writes;
7. target-byte verification before source deletion;
8. manifest written last;
9. structural verification plus disclosure of semantic exclusions.

Actions are `create`, `move`, `merge`, `delete`, `keep`, or `conflict`. A changed path, target, rendered artifact, or transaction digest invalidates the whole transaction; partial reuse of an old confirmation is forbidden.

## Development plan contract

Development plans are ordinary project-owned Markdown files, not inputs to `resolve` or `apply`. On resume, the agent verifies repository identity, branch, Git status, specification, relevant code, tests, and external state before trusting the plan. Changed facts require updating or discarding it.

Before creating a plan, the agent investigates enough of the current system to distinguish verified facts from assumptions and unresolved decisions. A plan must contain:

- an observable completed outcome and explicit non-goals;
- numbered requirements whose authority or confirmation source and acceptance evidence are explicit;
- a verified baseline referencing relevant specification sections, repository-relative code paths, stable symbols, tests, and branch or base context;
- ordered steps with `pending`, `in_progress`, or `completed` state, with at most one step in progress;
- for each implementation step, the requirements satisfied, target files or stable symbols, intended behavior change, dependencies or material risks, and concrete verification;
- for an unknown target, a bounded discovery step that names the search or inspection and the decision it must produce instead of inventing a path;
- completed and pending verification, blockers or decisions with their resume condition, and one exact next action.

Generic steps such as “implement the feature”, “add tests”, “update documentation”, or “continue processing” are invalid unless they also identify the target, behavior, and verification. Durable requirements belong in the main specification; a plan may reference a newly confirmed requirement only while its specification writeback remains an explicit implementation step.

Plans use repository-relative paths and stable identifiers. They must not contain file bodies, transcripts, raw logs, secrets, personal data, temporary absolute paths, machine transaction artifacts, hashes used as reusable approval, or hidden authorization. Norn defines the plan-quality contract and agent instructions; deterministic governance transactions do not generate or approve development plans.

## Safety and recovery

- A source file is deleted only after its target exists with the transaction output bytes.
- Legacy directories are deleted only when empty.
- Repository paths cannot escape the canonical target or traverse symbolic links.
- Unsupported filesystem types and collisions block before mutation.
- Interrupted work re-enters through fresh analysis; previous machine transactions and approvals are never reused.
- File modes are preserved through APIs supported by the repository's declared Python baseline.
- Norn never commits, pushes, creates branches, or modifies Git configuration without explicit user authorization.

## Verification and acceptance

Automated verification must cover:

- initialization, legacy migration, mixed-state recovery, and idempotence;
- custom root-rule semantic resolution;
- template upgrades with unchanged and modified managed blocks;
- transaction and rendered-artifact tamper rejection;
- source preservation across write failures and changed preconditions;
- explicit legacy tree handling, collisions, symbolic links, and special files;
- mode preservation on supported Python versions;
- disclosure of structural verification scope and semantic exclusions;
- absence of an initialized empty `plans/` directory;
- development-plan guidance that requires code-informed baselines, explicit acceptance-bound requirements, target-specific steps, concrete verification, and one active next action;
- equality of repository templates, Skill assets, and the installed Skill after release;
- realistic document-consolidation instructions that classify content instead of dumping all documents into appendix.
- main-specification notices that distinguish confirmation from completed writeback, remain silent when no writeback exists, and upgrade deterministically from the immediately previous managed template while preserving project text outside managed blocks and retaining the existing conflict policy for modified blocks.

The release acceptance sequence is:

1. all unit and CLI tests pass on the supported Python baseline;
2. Skill structure validation passes;
3. template and asset copies match byte-for-byte;
4. fresh initialization and legacy migration fixtures finish structurally current;
5. a realistic documentation-consolidation review proves that current normative content is promoted to the main specification;
6. a realistic development-plan review proves that requirements, implementation targets, step states, verification, and resume state are actionable rather than generic;
7. Git diff contains only the approved scope;
8. the installed Skill is synchronized only after repository validation.

## Non-goals

- Treating plans or appendix files as a fourth authority.
- Deterministically generating, approving, or executing development plans as governance transactions.
- Automatically interpreting arbitrary Markdown with the deterministic engine.
- Moving every project document into Norn merely because governance is adopted.
- Maintaining completed-plan archives, indexes, or placeholders.
- Overwriting project-owned specifications or silently resolving managed-block conflicts.
- Claiming semantic correctness from a structural `current` result.
- Automatic Git mutation.
