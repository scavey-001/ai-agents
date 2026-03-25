# Agent Workflow Preferences

These instructions apply to the entire repository.

## Commit Confirmation Gate

Before running any `git commit`, the agent must:

1. Show a concise summary of the staged changes.
2. Propose the exact commit message.
3. Wait for explicit user approval before committing.

Do not commit unless the user explicitly approves.

## Session Handoff Habit

At the start of new sessions, the agent should read `README.md` and `memory.md` before making implementation decisions.

## Session Close Ritual

Before ending an implementation session, the agent must provide:

1. A concise summary of what changed (files + intent).
2. What was tested and what was not tested.
3. Exact next-step instructions for the laptop workflow.
4. Confirmation that `memory.md` was updated when relevant.
5. A final commit approval checkpoint before committing if new commits are still pending.

## Speed vs. Cleanliness Default

Default policy is **Balanced**:

- Fast iteration is acceptable during exploration.
- Before committing, quality and handoff hygiene are required (docs/deps/tests status captured).
