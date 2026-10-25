---
description: Break work into small verifiable tasks with acceptance criteria and dependency ordering
---

Invoke the flow:planning-and-task-breakdown skill.

Read the existing spec (SPEC.md or equivalent) and the relevant codebase sections. Then:

1. Enter plan mode — read only, no code changes
2. Identify the dependency graph between components
3. Slice work vertically (one complete path per task, not horizontal layers)
4. Write tasks with acceptance criteria and verification steps
5. Add checkpoints between phases
6. Present the plan for human review

Save the plan to tasks/plan.md and task list to tasks/todo.md. Give every task its **Dependencies** and **Files likely touched**: `/flow:build auto` runs independent tasks in parallel from them, and never two tasks on the same files at once.

Presenting the task list is a human gate: wait for a clear yes. Then offer `/flow:build` (the next task, here) or `/flow:build auto` (every task, in parallel, one reviewed PR each, non-stop).

If tasks/plan.md or tasks/todo.md already exists with unchecked tasks for different work, stop and ask before writing — never silently overwrite an incomplete plan.
