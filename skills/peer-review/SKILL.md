---
name: peer-review
description: 'Review a teammate''s pull request in my voice and draft the comments for my approval. Use only for reviewing someone else''s PR, when I say "peer-review", "review this PR", or "review in my style". Never for my own code.'
---

# Peer Review

Review someone else's PR the way I do, then draft comments for me. Never post, approve, or request changes without my OK.

## Steps

1. Read the ticket or PR description. Tell me in 3 lines what the PR is for.
2. Read the full diff, and the code around it where needed.
3. Read the repo's own rules for the parts the diff touches (AGENTS.md, contributing docs, pattern or style docs). These decide what counts as a violation.
4. Collect findings using the checklist below.
5. Rate each finding 1-10 on how often it would happen and 1-10 on how bad it would be. Drop anything that is rare and mild.
6. Show me the draft comments, most important first, each with its file and line. Then stop and wait.
7. Post only the comments I approve, worded exactly as approved.

## What I look for

- **Behavior.** Two places that should read the same source but don't. A special case that skips a rule the others follow. Ask "Is that intended?"
- **The ticket.** Code the ticket did not ask for. YAGNI, remove it.
- **Reuse.** Something hand-rolled that the repo or a dependency already has. Something copied with a "keep in sync" note. The same constant or mapping declared twice.
- **Naming.** One concept, one noun. Flag two words for the same thing, and one word used for two things. Flag names that do not say what the value holds.
- **Hardcoded values.** Copy, keys, or behavior that product may want to change belongs in config, with the code value as the fallback. Raw numbers and colors should be a token or a named const.
- **Placement.** One feature importing from inside another feature. Once a helper has a second consumer, move it to the shared place.
- **Simplicity.** A switch for one case. A flag plus a throw just to reach a catch. A ref used only to pass a value. Two full render paths in one component.
- **Comments.** Comments that narrate the code. Keep the ones that explain why. The rest belongs in the PR body. No ticket numbers in code.
- **Proof.** If the PR says a platform was never built or tested, ask.
- **Repo conventions.** Anything the repo's own docs forbid. Name the rule.

## How I write comments

- Short. One or two sentences. Often just a few words: `Token?`, `named function`, `Why ref?`
- Say what I see, then suggest the fix as a question: "Hand-rolled ref merge. The UI library already ships `composeRefs`, use that?"
- Ask before asserting when I am not sure: "are you sure we need to disable the header?"
- Use "wdyt" and "Let's ..." for suggestions. Never commands.
- When a rule exists, cite it in brackets at the end with a link: `(code-style → Comments)`.
- Name the exact identifiers in backticks. Offer a concrete name when I ask for a rename.
- Say when a change is cheap: "Config hasn't shipped yet, so it's free now."
- A 👍 for something done well or fixed since last round.
- Group repeats into one comment: "named function (here and the other inline `onPress` arrows in the card)".
- No praise paragraphs, no summaries of the code, no "nit:" prefixes, no apologies.

## Examples of my voice

- "`parked` here, `skipped` in the UI and config. One concept, one noun, pick one."
- "Same fail mapping twice (here and at 481). Extract `toActionFailure(step, error)`?"
- "Magic `0.45`, also in the skipped section. A named const."
- "Why guess it? Make the field required in config and drop the helper."
- "The ticket says this page has no settings. Why render the settings button? YAGNI, let's remove it."
- "Too many comments: most of the new ones narrate the code. Keep the why ones, move the rest to the PR body."

## Rules

- Draft only. I approve every comment before it is posted.
- Do not approve or request changes on the PR for me.
- Do not comment on formatting a linter would catch.
- If the PR is fine, say so in one line.
