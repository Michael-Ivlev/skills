---
description: One entry point for the whole flow (define, plan, build, verify, review, ship). Give it an idea in words, one ticket, or many tickets; it starts at the right phase and runs to merged, reviewed PRs.
---

`$ARGUMENTS` says where the work starts. Decide which of the three it is, say it in one line, then follow that row. Don't redo a phase whose output already exists and is approved.

```
DEFINE          PLAN           BUILD          VERIFY         REVIEW          SHIP
 Idea ───────▶  Spec/Tasks ──▶  Code   ─────▶  Test   ─────▶  PR review ──▶  Merge, test run, cleanup
 /flow:spec     /flow:plan      /flow:build    /flow:test     /flow:review   /flow:ship
```

| `$ARGUMENTS` looks like | Mode | What happens |
|---|---|---|
| An idea, a feature, a problem in words (no issue number) | **Idea** | 1. **Define:** if it is vague, run flow:interview-me (one question at a time) or flow:idea-refine first; then flow:spec-driven-development writes `SPEC.md`. **Stop: the human approves the spec.** 2. **Plan:** flow:planning-and-task-breakdown writes `tasks/plan.md` and `tasks/todo.md` (every task with dependencies and the files it touches). **Stop: the human approves the task list.** 3. From there **non-stop**: `/flow:build auto`, i.e. flow:orchestrate-tickets with scope `plan` (parallel lanes, one PR per task, reviewed on the PR until approved, merged), ending with the final test run, the test plan and cleanup. No GitHub issues or board in this mode. |
| One issue: `#12`, `12`, `T12`, an issue URL | **Single ticket** | flow:orchestrate-tickets with that one issue: one lane (the main checkout), card to In Progress, plan, build, test, PR, review on the PR until approved, merge, card to Done, issue closed. Slow end-to-end tests: run them for this ticket before the PR unless the setup says otherwise. |
| Several issues: a range (`T04-T26`, `#4-#26`), a list, a milestone, a label, a roadmap step | **Many tickets** | flow:orchestrate-tickets with that scope, non-stop: setup questions once, parallel lanes, never two tickets on the same files, board moves, a reviewed PR per ticket, merges, one test run of everything at the end, a test plan for the human, cleanup. |

Rules for every mode:

- An earlier run's ledger (`<repo>-lanes/ledger.md`) means work is in flight: continue it rather than starting over, unless the human says otherwise.
- An approval is a clear yes ("approve", "go", "yes"). "Looks fine I guess" is not one.
- If the request is a one-line fix with an obvious scope, skip the ceremony: do it, test it, and offer a PR.
- The phase commands still work alone: `/flow:spec`, `/flow:plan`, `/flow:build` (one task here) or `/flow:build auto`, `/flow:test`, `/flow:review [PR]`, `/flow:ship`.
