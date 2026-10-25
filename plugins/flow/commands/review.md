---
description: Five-axis code review — correctness, readability, architecture, security, performance. With a PR, the reviewer agent posts its verdict on the PR and loops with fixes until it approves
---

Invoke the flow:code-review-and-quality skill.

**With a pull request** (`/flow:review 123`, a PR URL, or "the PR" for the current branch's): spawn the `flow:pr-reviewer` agent on it. It reviews on these five axes plus the ticket and posts its verdict **on the PR** (`## Review round N: APPROVED` or `CHANGES REQUESTED`, numbered findings, the reviewed SHA). When it asks for changes, fix every blocker and should-fix (or hand them to `flow:developer`), reply on the PR to each finding by number, rerun the tests, and review again until it approves. Report the verdict and the review's URL.

**Without one**, review the local changes as below and report in the session.

Review the current changes (staged or recent commits) across all five axes:

1. **Correctness** — Does it match the spec? Edge cases handled? Tests adequate?
2. **Readability** — Clear names? Straightforward logic? Well-organized?
3. **Architecture** — Follows existing patterns? Clean boundaries? Right abstraction level?
4. **Security** — Input validated? Secrets safe? Auth checked? (Use security-and-hardening skill)
5. **Performance** — No N+1 queries? No unbounded ops? (Use performance-optimization skill)

Categorize findings as Critical, Required, Optional, or Nit.
Output a structured review with specific file:line references and fix recommendations.
