# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use. Right now the two
columns are identical: nothing in this repo used a competing vocabulary at setup time.

## Applying them

This repo's tracker is GitHub Issues, so labels are applied with
`gh issue edit <number> --add-label <label>` and removed with `--remove-label <label>`.
`gh issue create` also takes `--label a --label b`. See `docs/agents/issue-tracker.md`.

GitHub requires a label to exist in the repo before it can be applied. Create any
missing ones with `gh label create <name> --description "..."`; `gh label list`
shows what already exists.
