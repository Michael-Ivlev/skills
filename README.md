# skills

Claude Code skills shared by the team, published as a plugin marketplace. Private: you need access to this repo to install it.

## Install

In Claude Code (any project):

```
/plugin marketplace add Michael-Ivlev/skills
/plugin install workflows@michael-ivlev
```

Restart Claude Code if the skills don't show up. Get updates later with `/plugin marketplace update michael-ivlev`.

## Skills

| Skill | Command | What it does |
|---|---|---|
| orchestrate-tickets | `/workflows:orchestrate-tickets <scope>` | Finishes a set of GitHub issues (a range, milestone, label or roadmap step) as the orchestrator of an AI team: tickets run in parallel in their own git worktrees without touching the same files, cards move across the GitHub project board (In Progress, In Review, Done), a reviewer agent reviews every PR on the PR itself until it approves, approved PRs merge and their issues close, slow end-to-end tests run once at the end with a test plan for humans, and a cleanup agent then removes or resets the worktrees and archives the run's ledger. Needs `gh` signed in with the `project` scope (`gh auth refresh -s project`). |
| meshy-3d | `/workflows:meshy-3d` | Generates textured `.glb` models for a list of assets with the Meshy API: a concept image from the asset's prompt plus a shared style block, then image-to-3D, in parallel batches. Credit budget and spend ledger, dry runs, never overwrites a good model, an AI-generation index and a contact sheet. Needs a Meshy API key (`msy_...`). |
| tripo-3d | `/workflows:tripo-3d` | The same with the Tripo API v3: text-to-model (usually the best, ~$0.20 a model) or concept then image-to-model. Real money (1 credit = $0.01), so a hard budget and a ledger. Needs a Tripo secret key (`tsk_...`). |

The two 3D skills read the same job file format (`assets.example.json` in each skill's folder). API keys never go in this repo or any repo: each tool reads its key from an environment variable or a git-ignored file, and refuses a key file git would commit.

## Layout

```
.claude-plugin/marketplace.json          the marketplace (lists the plugins)
plugins/workflows/.claude-plugin/plugin.json
plugins/workflows/skills/<skill>/SKILL.md one folder per skill, with its supporting files
```

## Adding a skill

1. Add `plugins/workflows/skills/<name>/SKILL.md` (frontmatter `name` and `description`, then the instructions). Keep skills project-agnostic: project rules belong in each project's `CLAUDE.md`.
2. Bump `version` in `plugins/workflows/.claude-plugin/plugin.json`.
3. Commit and push; teammates run `/plugin marketplace update michael-ivlev`.
