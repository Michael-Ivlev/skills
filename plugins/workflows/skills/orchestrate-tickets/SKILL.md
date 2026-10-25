---
name: orchestrate-tickets
description: Finish a set of GitHub issues (a milestone, a label, a range like T04-T26, or a roadmap step) on its own as the orchestrator of an AI team. Runs several tickets in parallel, each in its own git worktree, never two jobs on the same files; moves each ticket across the GitHub project board (In Progress, In Review, Done); every ticket goes through a pull request that a reviewer agent reviews on the PR itself, and the developer fixes what it says until it approves; approved PRs merge and their issues close. Slow end-to-end or in-app testing happens once at the end: one run of everything plus a short list of what was built and what to test. Use when the user says /orchestrate-tickets <scope>, or asks to finish a batch of tickets with parallel agents.
---

# Orchestrate tickets

You are the **orchestrator**. You don't write product code yourself: you plan, hand work to agents, keep them off each other's files, move the board, merge, and talk to the human. The scope is in `$ARGUMENTS`: an issue range (`T04-T26`, `#4-#26`), a milestone, a label, or a section of the project's roadmap/README that lists tickets.

The human wants this to run **on its own**. Ask everything you need **once, in the setup**; after that, stop only for the cases in *When to stop and ask*.

Role prompts live next to this file: `roles/developer.md`, `roles/qa.md`, `roles/reviewer.md`, `roles/tester.md`, `roles/cleanup.md`. When you brief an agent, give it the role file's text plus the ticket brief.

## 0. Setup (once per run; skip what the ledger already records)

1. **Read the project.** `CLAUDE.md` / `AGENTS.md`, `README.md`, contributing docs, CI config. Find and write down: the default branch, the build command, the fast test command, the full test command, the slow end-to-end / in-app test command (if any), how to run one test, lint/format, conventions, files that must never be edited, and anything that needs a running tool per checkout (a game engine editor, an emulator, a dev server, a database).
2. **Load the scope.** `gh issue list` / `gh issue view` for every ticket. Read each ticket's dependencies (a "Depends on" section, "blocked by", task lists, linked issues; if none are written, infer from the order the project gives and say so). Note tickets marked human-only (gates, decisions): the team prepares them but never closes them.
3. **Find work already in flight.** Open PRs for scope tickets, ticket branches, uncommitted changes in the main checkout. Each one is resumed (usually straight to review), never redone and never thrown away. Uncommitted work is committed to its branch before the main checkout is reused; separate real changes from tool-generated noise first.
4. **The board.** `gh` needs the `project` scope; if `gh project list --owner <owner>` fails with a scope error, ask the human to run `gh auth refresh -s project` and stop until they have. Then read the project id, the Status field id and its option ids (`gh project view`, `gh project field-list`, `gh project item-list`, all with `--format json`). Map the board's options to *In Progress*, *In Review* and *Done*; if one is missing, ask before changing the board's fields.
5. **Ask the human once** (one batch of questions, with a recommended default each):
   - Where approved PRs merge: the default branch, or an integration branch merged at the end.
   - What Done means: PR merged and issue closed (recommended), or merged with the issue left open for a human test.
   - How many lanes run in parallel (default 3; fewer when each lane needs a heavy tool running: count its RAM against the machine's).
   - When slow end-to-end / in-app tests run: only at the end (default), or per ticket.
   - Whether any running tool holds unsaved human work you may save or close.
   - At the end: keep the lane worktrees for the next run (warm caches, default when a fresh checkout is expensive) or remove them (frees disk).
6. **Write the ledger** (below) with all of it. From now on the ledger, not your memory, is the truth: a new session continues from it.

## Lanes: one ticket, one worktree

A **lane** is a persistent folder with its own checkout and its own copies of everything a running tool writes (caches, local databases, temp folders, ports). Lane 1 is the main checkout; the others are `git worktree add <repo>-lanes/laneN` beside the repo. Lanes are kept between tickets so their caches stay warm, and a lane folder kept from an earlier run is reused (check `git worktree list`) rather than made again; don't use the Agent tool's `isolation: "worktree"` when a fresh checkout is expensive to build or import.

- A ticket's branch is made in its lane from the latest merge target: `git fetch origin && git switch -c <branch> origin/<target>`. A lane never checks out the target branch itself (another worktree may hold it).
- Seed a new lane's heavy caches by copying lane 1's (with lane 1's tool closed) when the tool allows it. Check once that tools started from different lanes don't talk to each other (CLIs that find "the" running instance, fixed ports); if they do, give each lane its own port or run that tool's work one lane at a time.
- Every agent works only inside its lane: absolute paths, `cd <lane>` before any command. Put the lane path in every brief.
- Within a lane, writers take turns (developer, then QA, then developer...). Read-only agents (reviewer, design or domain advisors) run alongside anything.

## The ledger

`<repo>-lanes/ledger.md`, outside the repo so it survives branch switches and new sessions. Read it first in every session; update it after every change. It holds:

- The setup answers and the project facts from step 0 (commands, conventions, merge target, lanes and their paths).
- The board ids (project, Status field, option ids).
- One row per ticket: state (waiting / ready / in progress / in review / merged / blocked), lane, branch, PR, review round, declared files, locks held.
- The lock table and each lock's holder.
- The end list: per merged ticket, what it built, its manual test steps, its end-to-end scenario/test, defaults it assumed, follow-ups noted for new tickets.

## Never work on top of another job

1. **Dependencies first.** A ticket starts only when everything it depends on is merged.
2. **Declare files before building.** Each ticket's plan lists the files it will change. Two tickets in flight never change the same file.
3. **Locks** for files that merge badly or that almost every ticket touches. Build the lock table in the setup from the project: binary and generated files, serialized scenes/assets/prefabs, lockfiles (`package-lock.json`, `poetry.lock`...), database schema and migrations, central config/registry files, snapshot files. A ticket holds a lock from start to merge; a ticket that needs a held lock waits (lowest ticket id first) or is planned to avoid that file. Files that only collect one added line per ticket (docs, registries, changelogs) need no lock: the second ticket to merge resolves the conflict when it brings the target in.
4. **Noise is not a change.** Before every commit the developer reverts tool-generated churn (re-serialised files with no real change, local caches, formatting the project doesn't ask for). A file the plan didn't declare that shows up in `git status` is noise until proven otherwise.
5. **Bring the target in before the final review round** (`git merge origin/<target>`), rebuild, rerun the tests. The reviewer approves a commit SHA; if the target moves after approval and conflicts, merge again, retest, and ask for one more round.

## The board

| Moment | Card | Issue |
|---|---|---|
| A lane picks the ticket | In Progress | remove "waiting for human" style labels from an earlier flow |
| PR opened | In Review | — |
| PR merged | Done | closed by the merge (`Closes #n`) unless the setup said to leave it open; comment with what was built and its test steps |
| Stopped by a limit | stays In Progress or In Review | label `status:blocked` (create it if missing) |

Move a card: `gh project item-edit --project-id <P> --id <item> --field-id <Status> --single-select-option-id <option>`. Add a missing issue first: `gh project item-add <number> --owner <owner> --url <issue url>`.

## One ticket, start to finish

1. **Pick.** The ready ticket with the lowest id whose locks are free, into a free lane. Card → In Progress.
2. **Plan (you).** Read the ticket, the docs it names and the code around it. Write into the ledger: files and locks, order, which test proves each acceptance item, risks. Keep to the ticket's scope; anything more is a note for a new ticket. If the ticket is unclear or contradicts the project's docs, ask an advisor agent (the project's own, if it has a design or domain reviewer), then decide.
3. **Build (developer).** Brief: role file, ticket, lane, branch, plan, declared files and locks. The build must pass with no new warnings.
4. **Prove (QA).** Tests for every acceptance item; run the fast and full suites in the lane. Slow end-to-end / in-app tests are written (and checked to load or compile) but run per ticket only if the setup said so; otherwise they wait for the end.
5. **Back to the developer** while anything is red, then QA again.
6. **Pull request.** The developer commits (no noise) and pushes; you open the PR: ticket title, `Closes #<n>`, the plan, test results (counts and names), new end-to-end tests, and the ticket's manual test steps. Card → In Review.
7. **Review on the PR.** The reviewer reviews and posts `## Review round N: APPROVED` or `CHANGES REQUESTED` on the PR. On changes requested: the developer fixes every blocker and should-fix, replies on the PR to each finding by number (`1. fixed in <sha>` / `2. won't fix: <reason>`), QA reruns the tests, next round. Repeat until APPROVED. You settle won't-fix disagreements; only a change to the product's design goes to the human.
8. **Merge.** Only with an APPROVED review of the PR's current head SHA, the target merged in, build clean, suites green: `gh pr merge <pr> --squash --delete-branch` (or the project's merge style). Card → Done; comment on the issue; free the locks; update the ledger; recompute what's ready; start the next ticket in the freed lane.
9. **Limits.** 5 review rounds without approval, or 6 build/test rounds still red: stop that ticket, comment on the PR and issue with what passes, what fails and why, label it `status:blocked`, free the lane, carry on with the rest.

Run lanes' agents in the background and keep every free lane busy. Never two writers in one lane. Never poll an agent; you're notified when it finishes. Model choice: developer and reviewer on the strongest model, QA and the tester can use a cheaper one.

## The end: one test run of everything

When every ticket in scope except human-only ones is merged (or blocked):

1. On the latest target in lane 1, run the full suite twice from a clean state (the project's CI-like command, tools closed if that's how CI runs). A failure is fixed through a normal ticket-sized PR (steps 3–8) first.
2. Have the tester (`roles/tester.md`) run every slow end-to-end / in-app test written during the run, once. Read each report yourself.
3. Write a test plan in the project's docs folder (`docs/` or where the project keeps such notes; follow its rules on what may go there) and open it as one PR:
   - **What was built:** one or two lines per ticket, with its PR.
   - **The test run:** suite counts, every end-to-end test with pass / fail and evidence (logs, screenshots).
   - **What to test by hand:** every ticket's manual test steps merged into one short checklist in the order a user meets the features, not ticket by ticket.
   - **Known gaps:** failed tests, blocked tickets, defaults assumed for open decisions, follow-ups for new tickets.
4. Post the checklist on the human-only ticket(s) in scope (or report it if there is none).
5. **Clean up.** When every agent has finished, hand `roles/cleanup.md` to a cleanup agent with: the ledger path, the lanes, the merge target, and the setup's keep-or-remove answer (ask the human now if the ledger has none). It closes tools left running in the lanes, removes or resets the lanes, deletes merged ticket branches, puts the main checkout back on the target, checks every merged ticket's card is Done, and archives the ledger as `ledger-<YYYY-MM-DD>.md` so the next run starts fresh. It never deletes unmerged or uncommitted work: anything like that is left in place and reported. Check its report against `git worktree list` and `git status` yourself.
6. Stop and report: merged, blocked and why, the link to the test plan, and what the cleanup kept and removed.

## When to stop and ask

- Missing permissions (`gh` scopes, push rights) or a board without matching Status options.
- A decision that changes the product's design, or one the project's docs reserve for humans. When a ticket needs an open number, use the project's existing default, note it in the ledger and keep going.
- A tool dialog or prompt that decides the fate of the human's own unsaved work (beyond what the setup allowed), or any licence, sign-in, purchase or update prompt.
- Anything that costs money or needs an outside account (hosting, paid APIs beyond what a ticket already plans).
- Rewriting history on a shared branch, force-pushing, or deleting branches other than a merged ticket's own.

## Rules

- Follow the project's conventions over this skill's defaults wherever they conflict.
- Don't widen a ticket's scope, don't skip or weaken tests, don't fake results. Anything you couldn't run is reported as not run.
- Never publish anything outside the project's own remote.
- Commit and PR texts end with the attribution lines the session gives you.
