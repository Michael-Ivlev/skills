# claude-skills

Claude Code skills shared by the team, published as a plugin marketplace. Private: you need access to this repo to install it.

## Install

In Claude Code (any project):

```
/plugin marketplace add Michael-Ivlev/claude-skills
/plugin install workflows@michael-ivlev
```

Restart Claude Code if the skills don't show up. Get updates later with `/plugin marketplace update michael-ivlev`.

## Skills

| Skill | Command | What it does |
|---|---|---|
| orchestrate-tickets | `/workflows:orchestrate-tickets <scope>` | Finishes a set of GitHub issues (a range, milestone, label or roadmap step) as the orchestrator of an AI team: tickets run in parallel in their own git worktrees without touching the same files, cards move across the GitHub project board (In Progress, In Review, Done), a reviewer agent reviews every PR on the PR itself until it approves, approved PRs merge and their issues close, and slow end-to-end tests run once at the end with a test plan for humans. Needs `gh` signed in with the `project` scope (`gh auth refresh -s project`). |

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
