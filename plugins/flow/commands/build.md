---
description: Implement tasks incrementally — build, test, verify, commit. Add "auto" to build the whole plan in one approved pass, in parallel, one reviewed PR per task.
---

Invoke the flow:incremental-implementation skill alongside flow:test-driven-development.

## Modes

- **`/build`** — implement the *next* pending task, then stop (careful, one slice at a time).
- **`/build auto`** — generate the plan if needed, get a single approval, then implement *every* task without stopping between them.

`$ARGUMENTS` selects the mode. Treat `auto` (canonical) or `all` as autonomous mode; anything else (or empty) is the default single-task mode. Note: autonomous mode is not faster *per task* — it runs the same test-driven loop — it only removes the human stepping *between* tasks.

## Default: one task

Pick the next pending task from the plan. Then:

1. Read the task's acceptance criteria
2. Load relevant context (existing code, patterns, types)
3. Write a failing test for the expected behavior (RED)
4. Implement the minimum code to pass the test (GREEN)
5. Run the full test suite to check for regressions
6. Run the build to verify compilation
7. Commit with a descriptive message
8. Mark the task complete and stop

## Autonomous: the whole plan (`/build auto`)

Use this once a spec exists and you want the whole plan built without stepping through it. It removes the manual stepping between tasks — **not** the verification. Every task still earns a passing test, its own pull request and an approved review.

1. **Require a spec.** Look only for a spec at a known path: `SPEC.md` at the repo root, `docs/SPEC.md`, or a file under `spec/`. A README or arbitrary doc does **not** count. If none exists, stop and tell the user to run `/flow:spec` first — do not invent requirements.
2. **Establish a clean baseline.** Run `git status --porcelain`. If there are uncommitted changes outside the expected planning artifacts (`SPEC.md`, `docs/SPEC.md`, `spec/*`, `tasks/plan.md`, `tasks/todo.md`), stop and ask the user to commit, stash, or confirm how to handle them.
3. **Plan if needed.** If there is no `tasks/plan.md`, invoke flow:planning-and-task-breakdown to generate one. Every task needs its **Dependencies** and **Files likely touched**: the orchestrator uses them to run tasks in parallel without two of them touching the same files.
4. **Single checkpoint.** Present the full task list and wait for an unambiguous affirmative (e.g. "approve", "go", "yes"). Treat hedged responses ("looks reasonable", "I guess") as **not** approved. This is the only human gate — after approval, run autonomously.
5. **Land the spec and plan.** Commit `SPEC.md`, `tasks/plan.md` and `tasks/todo.md` alone and get them onto the merge target (a PR merged at once, since the human just approved them, or a direct push where the project allows it), so every task branch starts from them.
6. **Hand the plan to flow:orchestrate-tickets with scope `plan`.** Each task gets its own lane (git worktree) and branch, `flow:developer` builds it, `flow:qa` proves it, a PR opens, `flow:pr-reviewer` reviews it on the PR until it approves, it merges and its checkbox is ticked. Independent tasks run in parallel; tasks never share files in flight. The run ends with one full test run, a test plan for the human, and cleanup (the orchestrator's *End* section).
7. **Stop and ask the user** (do not push through) when:
   - the spec is ambiguous, or a task needs a decision the spec doesn't cover
   - a task is high-risk or irreversible — auth/permission changes, destructive data migrations, payments, deletions, deploys, anything touching secrets, **or anything you can't undo with `git revert`** → follow flow:doubt-driven-development and get explicit sign-off before continuing
   - anything else in the orchestrator's *When to stop and ask*

   A task that can't be made green or approved within the orchestrator's limits is marked blocked (with flow:debugging-and-error-recovery's findings on its PR) and the rest carry on. After the user resolves a blocker, they re-invoke `/build auto`: it resumes from the orchestrator's ledger.
8. **Summarize at the end:** tasks merged (with PRs), tests added, anything blocked, skipped or left for the user, and the link to the test plan.

If any step fails, follow the flow:debugging-and-error-recovery skill.
