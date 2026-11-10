# skills

A small skill library for coding agents. It works with any agent that reads skills: Claude Code, Cursor, Codex and others.

A skill is just a folder with a `SKILL.md` in it. There are seven:

- Six are unmodified copies from [davidondrej/skills](https://github.com/davidondrej/skills).
- One, `peer-review`, is mine.

## The skills

| Skill | What it does | When to use it |
| --- | --- | --- |
| [`4x4`](skills/4x4/SKILL.md) | Asks 4 sets of 4 open questions to get 16 fast decisions, then presents a plan. | Before a risky change, a large product decision, or a large refactor. |
| [`ask-then-build`](skills/ask-then-build/SKILL.md) | Clarifies a feature or change with questions, then writes a build prompt for another agent. | When you want the questions asked first and the building done by someone else. |
| [`decisions`](skills/decisions/SKILL.md) | Lists the choices the agent made during the work that it is not sure about. | After a piece of work, to see what to double-check. Ask for it by name. |
| [`handoff`](skills/handoff/SKILL.md) | Captures the session context for a fresh agent. | At a context limit, when switching focus, ending a session, or splitting work. |
| [`occams-razor`](skills/occams-razor/SKILL.md) | Answers with what is known for sure, how it is known, and a confidence %. | When the agent is overthinking, or you want to know if something is really true. |
| [`remind`](skills/remind/SKILL.md) | Rewrites the last response shorter and simpler, with a short TLDR of the conversation first. | When you lost the thread or the last answer was too long. Ask for it by name. |
| [`peer-review`](skills/peer-review/SKILL.md) | Reviews a teammate's pull request in my voice and drafts the comments for approval. | When reviewing someone else's PR. Never for your own code. |

## Install

Put the skills in `~/.agents/skills/`, then symlink each one for the agents that need it.

1. Clone the repo and copy the skills:

   ```sh
   git clone https://github.com/Michael-Ivlev/skills.git
   mkdir -p ~/.agents/skills
   cp -R skills/skills/* ~/.agents/skills/
   ```

2. Codex reads `~/.agents/skills` directly. Nothing more to do.

3. Claude Code reads `~/.claude/skills/<name>`:

   ```sh
   mkdir -p ~/.claude/skills
   for s in 4x4 ask-then-build decisions handoff occams-razor remind peer-review; do
     ln -s ~/.agents/skills/$s ~/.claude/skills/$s
   done
   ```

4. Cursor reads `~/.cursor/skills/<name>`:

   ```sh
   mkdir -p ~/.cursor/skills
   for s in 4x4 ask-then-build decisions handoff occams-razor remind peer-review; do
     ln -s ~/.agents/skills/$s ~/.cursor/skills/$s
   done
   ```

To install only some skills, copy and link only those folders.

## Credits

`4x4`, `ask-then-build`, `decisions`, `handoff`, `occams-razor` and `remind` come from [davidondrej/skills](https://github.com/davidondrej/skills) by David Ondrej, under the MIT license. They are unmodified copies. His license is in [`LICENSE-third-party/davidondrej-skills-LICENSE`](LICENSE-third-party/davidondrej-skills-LICENSE).

The version before this library, with the `flow` plugin, is kept at the `pre-refactor` tag.
