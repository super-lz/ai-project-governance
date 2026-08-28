# Resumable development plans

`norn-governance/plans/` saves the current state of unfinished development so the same branch can be continued in another session or on another device. A plan is temporary navigation, never product authority, implementation truth, Git history, or a machine governance transaction.

## When to create one

Create a plan when at least one condition is true:

- the task is expected to remain unfinished when the current work session ends;
- the user intends to continue the same branch on another device;
- several dependent checkpoints, migrations, external approvals, or expensive verification steps make reconstruction materially risky.

Do not create a plan for work that can be completed and verified in the current session with low reconstruction cost.

## File and content

Use `norn-governance/plans/YYYY-MM-DD-<task>.md` and keep one file per active task.

```markdown
# <Task>

- Goal: <observable completed outcome>
- Non-goals: <scope intentionally excluded>
- Authority: <main-spec sections and relevant code paths>
- Branch context: <branch/worktree and stable base reference>
- Completed: <verified checkpoints only>
- Remaining: <unfinished work>
- Next: <one exact first action>
- Verification: <commands/evidence already run and still pending>
- Blockers or decisions: <condition, owner, and resume trigger>
```

Use repository-relative paths and stable identifiers. Do not copy file bodies, chat transcripts, raw command logs, secrets, credentials, personal data, absolute temporary paths, generated artifacts, transaction hashes, or reusable execution approvals.

## Checkpoints and resumption

- Update the plan after a meaningful implementation or verification checkpoint, before an expected interruption, and when a blocker changes.
- On resume, first verify repository identity, branch, Git status, main specification, relevant code, and external state. Then compare the plan with current facts.
- If facts changed, update or discard stale plan content. Never use a plan to overwrite the main specification or current code.
- Existing decisions in a plan are context, not fresh authorization for destructive, external, or scope-expanding actions.

## Git and cleanup

A plan may travel with its development branch so another device can continue it, but commit and push only when the user authorizes those Git actions. Do not create plan indexes, completed-plan archives, a global current plan, README files, or placeholders.

When the task completes or is cancelled, first place durable outcomes in the main specification, code, tests, or Git history, then delete the plan. A blocked plan may remain only when it states the unblock condition and exact first resume action.
