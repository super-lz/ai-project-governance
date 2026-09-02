# Resumable development plans

`norn-governance/plans/` saves the current state of unfinished development so the same branch can be continued in another session or on another device. A plan is temporary navigation, never product authority, implementation truth, Git history, or a machine governance transaction.

## When to create one

Create a plan when at least one condition is true:

- the task is expected to remain unfinished when the current work session ends;
- the user intends to continue the same branch on another device;
- several dependent checkpoints, migrations, external approvals, or expensive verification steps make reconstruction materially risky.

Do not create a plan for work that can be completed and verified in the current session with low reconstruction cost.

## Investigate before writing

Before saving a plan:

1. verify the repository identity, branch or worktree, Git status, and stable base reference;
2. read the governing `AGENTS.md` files and the complete main specification;
3. inspect the relevant entry points, code paths, symbols, tests, configuration, dependencies, and current failures;
4. separate verified facts from assumptions and decisions that still need an owner;
5. translate the accepted outcome into explicit requirements and observable acceptance evidence.

Do not produce a plan by expanding the user's wording into generic phases. If the implementation location is not yet known, add a bounded discovery step that names what will be searched, where, and what decision or artifact ends the discovery. Never invent a path or symbol to make the plan look complete.

## File and required content

Use `norn-governance/plans/YYYY-MM-DD-<task>.md` and keep one file per active task. Adapt the number of requirements and steps to the work; do not preserve empty placeholders.

```markdown
# <Task>

- Status: active | blocked
- Branch: <branch or worktree>
- Base: <stable branch or revision>

## Outcome and boundaries

- Outcome: <observable completed result>
- Done when: <user-visible or system-visible acceptance evidence>
- Non-goals: <scope intentionally excluded>

## Verified baseline

- `<spec section or path#symbol>`: <verified current fact and evidence>
- Assumptions: <assumptions that do not yet qualify as facts>
- Unknowns: <unresolved facts and how they affect the plan>

## Requirements

### R1 — <explicit behavior or constraint>

- Source: <main-spec section, confirmed requirement, or code/test invariant to preserve>
- Acceptance: <testable or reviewable evidence>
- Specification writeback: none | <required spec section and step>

## Implementation steps

### S1 [pending] — <concrete intermediate outcome>

- Requirements: R1
- Targets: `<repository-relative path#stable-symbol>`
- Change: <specific behavior or contract change>
- Depends on: none | S<n> | <external condition>
- Risks or edge cases: <material cases only>
- Verify: `<command, test, or inspection>` → <expected evidence>

## Resume checkpoint

- Completed: <completed step IDs and verified result>
- In progress: none | <exactly one step ID and current state>
- Next: <one exact action naming a path, symbol, command, or decision>
- Blockers or decisions: <owner, condition, and resume trigger>
- Verification completed: <commands or evidence and result>
- Verification pending: <remaining evidence tied to requirements or steps>
```

## Step quality rules

- Use only `pending`, `in_progress`, and `completed`; at most one step may be `in_progress`.
- Every implementation step links to at least one requirement and identifies repository-relative targets or stable symbols.
- `Change` describes the behavior or contract delta, not the act of editing.
- `Verify` names the command, test, inspection, or observable result that can disprove completion.
- A discovery step names its search scope and the concrete decision or evidence it must produce. It does not pretend the implementation target is already known.
- Requirements that change durable product semantics must be written back to the main specification in the same change. The plan references that work; it does not become the authority.
- Keep only details that make execution, review, or resumption cheaper. Do not turn the plan into a design essay or transcript.

These are invalid on their own:

```markdown
- Implement the feature.
- Add tests.
- Update documentation.
- Continue processing the remaining work.
```

A useful step instead identifies the requirement, target, intended behavior, dependency, and verification. For example:

```markdown
### S2 [pending] — Reject an invalid destination parent during analysis

- Requirements: R2
- Targets: `skills/norn-governance/scripts/norn_governance/analyzer.py#_transaction_output`
- Change: report a blocking conflict before apply when a destination parent is a regular file
- Depends on: S1 path enumeration
- Risks or edge cases: nested destinations and a parent replaced after analysis
- Verify: `python3 -m unittest discover -s skills/norn-governance/tests -p 'test_analyzer.py' -v` → the focused collision case passes without repository writes
```

## Checkpoints and resumption

- Update the plan after a meaningful implementation or verification checkpoint, before an expected interruption, and when a blocker changes.
- On resume, first verify repository identity, branch, Git status, main specification, relevant code, and external state. Then compare the plan with current facts.
- If facts changed, update or discard stale plan content. Never use a plan to overwrite the main specification or current code.
- Existing decisions in a plan are context, not fresh authorization for destructive, external, or scope-expanding actions.
- Update step states and the resume checkpoint together. Do not claim a step is completed without its stated evidence.

## Git and cleanup

A plan may travel with its development branch so another device can continue it, but commit and push only when the user authorizes those Git actions. Do not create plan indexes, completed-plan archives, a global current plan, README files, or placeholders.

When the task completes or is cancelled, first place durable outcomes in the main specification, code, tests, or Git history, then delete the plan. A blocked plan may remain only when it states the unblock condition and exact first resume action.
