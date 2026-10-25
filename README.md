# skills

Claude Code skills shared by the team, published as a plugin marketplace. Private: you need access to this repo to install it.

## Install

In Claude Code (any project):

```
/plugin marketplace add Michael-Ivlev/skills
/plugin install flow@michael-ivlev
```

Restart Claude Code if the skills don't show up. Get updates later with `/plugin marketplace update michael-ivlev`. If you also have `agent-skills` installed, uninstall it (`/plugin uninstall agent-skills@addy-agent-skills`): `flow` contains its own copy, and two copies trigger twice.

## The flow

```
DEFINE          PLAN           BUILD          VERIFY         REVIEW          SHIP
 Idea ───────▶  Spec/Tasks ──▶  Code   ─────▶  Test   ─────▶  PR review ──▶  Merge, test run, cleanup
 /flow:spec     /flow:plan      /flow:build    /flow:test     /flow:review   /flow:ship
```

**`/flow:go <anything>`** is the one entry point. It works out where the work starts:

| You give it | It does |
|---|---|
| **An idea** in words | Questions until it's clear, then `SPEC.md` (you approve), then `tasks/plan.md` + `tasks/todo.md` (you approve the task list), then builds every task non-stop: parallel worktrees, one PR per task reviewed on the PR until approved, merged, one final test run, a test plan for you, cleanup. All in the repo; no issues or board. |
| **One ticket** (`#12`, `T12`) | Plans, builds, tests, opens the PR, the reviewer agent reviews it on the PR and the developer fixes until it approves, merges, moves the card to Done, closes the issue. |
| **Many tickets** (`T04-T26`, a milestone, a label) | Asks its setup questions once, then runs up to N tickets in parallel (each in its own git worktree, never two on the same files), moves cards In Progress → In Review → Done, a reviewed PR per ticket, merges, one test run of everything at the end with a test plan for you, then cleans up the worktrees. Survives new sessions through its ledger (`<repo>-lanes/ledger.md`). |

Each phase also works alone:

| Command | Does |
|---|---|
| `/flow:spec` | Spec before code (`SPEC.md`): objective, commands, structure, style, tests, boundaries |
| `/flow:plan` | Small tasks with acceptance criteria, dependencies and the files each touches (`tasks/plan.md`, `tasks/todo.md`) |
| `/flow:build` / `/flow:build auto` | The next task here, test first / every task in parallel, one reviewed PR each |
| `/flow:test` | Test-driven: failing test first; for bugs, a test that reproduces it |
| `/flow:review [PR]` | Five-axis review; with a PR, the verdict goes on the PR and loops with fixes until approved |
| `/flow:ship` | Finishes a run (final test run, test plan, cleanup); for production, a parallel go/no-go with a rollback plan |
| `/flow:code-simplify`, `/flow:constraints`, `/flow:webperf` | Simplify without changing behaviour; write the project's quality bar; web performance audit |

Needs `gh` signed in; for the board, with the `project` scope (`gh auth refresh -s project`).

## Agents

| Agent | Job |
|---|---|
| `flow:developer` | Builds one ticket or task in its worktree, answers review findings by number |
| `flow:qa` | A test per acceptance item, runs the suites, writes end-to-end scenarios |
| `flow:pr-reviewer` | Reviews a PR and posts `Review round N: APPROVED / CHANGES REQUESTED` on it |
| `flow:tester` | Runs every end-to-end test once at the end of a run |
| `flow:cleanup` | Removes or resets the worktrees, deletes merged branches, archives the ledger |
| `flow:code-reviewer`, `flow:security-auditor`, `flow:test-engineer`, `flow:web-performance-auditor` | Specialist reviewers (used by `/flow:ship`) |

A project's own agent with the same name in `.claude/agents/` wins over these.

## Skills

- **Flow:** `orchestrate-tickets` (the engine behind `/flow:go`, `/flow:build auto` and `/flow:ship`), `interview-me`, `idea-refine`, `spec-driven-development`, `planning-and-task-breakdown`, `incremental-implementation`, `test-driven-development`, `debugging-and-error-recovery`, `code-review-and-quality`, `doubt-driven-development`, `git-workflow-and-versioning`.
- **Specialists (used when the work calls for them):** `api-and-interface-design`, `browser-testing-with-devtools`, `ci-cd-and-automation`, `code-simplification`, `constraint-driven-development`, `context-engineering`, `deprecation-and-migration`, `documentation-and-adrs`, `frontend-ui-engineering`, `observability-and-instrumentation`, `performance-optimization`, `security-and-hardening`, `shipping-and-launch`, `source-driven-development`. Checklists they share are in `plugins/flow/references/`.
- **3D models:** `meshy-3d` (Meshy: concept image then image-to-3D) and `tripo-3d` (Tripo v3: text-to-model, usually the best, ~$0.20 a model). Same job file format (`assets.example.json` in each), a credit budget and ledger, dry runs, never overwrite a good model, an AI-generation index. API keys never go in any repo: each tool reads its key from an environment variable or a git-ignored file and refuses a key file git would commit.

## Layout

```
.claude-plugin/marketplace.json            the marketplace
plugins/flow/.claude-plugin/plugin.json    the plugin
plugins/flow/commands/<name>.md            /flow:<name> slash commands (thin: each invokes a skill)
plugins/flow/skills/<name>/SKILL.md        skills, with their supporting files
plugins/flow/agents/<name>.md              agents (flow:<name>)
plugins/flow/references/                   shared checklists
plugins/flow/third_party/                  licences of adapted work
```

## Adding or changing a skill

1. Add `plugins/flow/skills/<name>/SKILL.md` (frontmatter `name` and `description`, then the instructions), and a thin `commands/<name>.md` if it deserves a slash command. Keep skills project-agnostic: project rules belong in each project's `CLAUDE.md`.
2. Bump `version` in `plugins/flow/.claude-plugin/plugin.json`.
3. Commit and push; teammates run `/plugin marketplace update michael-ivlev`.

## Credits

The engineering skills, the specialist agents, the references and the phase commands are adapted from [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) v0.6.13 by Addy Osmani, MIT licence (`plugins/flow/third_party/agent-skills-LICENSE`). Changed here: the commands are namespaced `flow:`, `/flow:build auto` hands the plan to the orchestrator (parallel worktrees, one reviewed PR per task), `/flow:review` reviews on the PR, `/flow:ship` first finishes the run, `/flow:go` is new, the planning skill feeds the orchestrator, and `using-agent-skills` is left out (Claude Code routes skills by their descriptions). Upstream changes are pulled in by hand.
