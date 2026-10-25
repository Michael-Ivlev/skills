---
name: cleanup
description: End-of-run cleanup: removes or resets the lane worktrees, deletes merged ticket branches, puts the main checkout back on the target, checks the board, archives the run ledger; never touches unmerged or uncommitted work. Use at the end of flow:orchestrate-tickets or /flow:ship.
---

# cleanup (end of the run)

The run is over: every ticket is merged or blocked, the test plan is posted. You leave the machine tidy for the next run **without ever losing work**. The orchestrator gives you the ledger path, the lane folders, the main checkout, the merge target and the keep-or-remove answer.

## Safety first (check before touching anything)

For every lane, the main checkout included:

- `git status --porcelain`: uncommitted changes?
- `git log origin/<branch>..HEAD` (or `git status -sb`): commits not pushed?
- The branch's PR (`gh pr list --head <branch> --state all --json number,state,headRefOid`): is it MERGED, and is the local head the PR's head SHA?

A lane or branch with uncommitted changes, unpushed commits, or a PR that isn't merged (open, closed unmerged, blocked ticket) is **left exactly as it is** and listed in your report. Never use `--force`, `git reset --hard`, `git clean` or `git checkout -- .` on anything.

## Then

1. **Close tools left running in the lanes** (editors, dev servers, emulators) that the run started, only when nothing unsaved would be lost; otherwise leave them and report.
2. **Lanes** (not lane 1, the main checkout):
   - *Remove:* `git worktree remove <lane>` (it refuses a dirty lane; that's the point), then `git worktree prune`, then delete the empty `<repo>-lanes/laneN` folder if anything is left behind (ignored caches) only after the worktree is gone from `git worktree list`.
   - *Keep:* `git -C <lane> fetch origin && git -C <lane> switch --detach origin/<target>`, so the lane's caches stay warm and it holds no ticket branch.
3. **Branches.** `git fetch --prune`. Delete a local ticket branch only when its PR is MERGED and the local head equals the PR's head SHA: `git branch -D <branch>` (squash merges make `-d` refuse, so this check replaces it). Never delete a remote branch whose PR isn't merged.
4. **Main checkout:** back on the target branch and up to date (`git switch <target> && git pull --ff-only`), only if it is clean.
5. **Board:** every merged ticket's card is in Done; fix any that isn't. Don't touch human-only or blocked tickets.
6. **Ledger:** rename `<repo>-lanes/ledger.md` to `<repo>-lanes/ledger-<YYYY-MM-DD>.md` (add `-2`, `-3` if that name exists). Never delete a ledger. If lanes were kept, add a line at its top: which lanes remain and on which commit.
7. If lanes were removed and `<repo>-lanes/` now holds only archived ledgers, leave it: it keeps the run's history.

## Report

A table: each lane and branch with what you did (removed / reset / deleted / kept) and why anything was kept, tools closed, cards fixed, the archived ledger's path, and disk freed if you can measure it (folder size before and after).
