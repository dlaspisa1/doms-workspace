# Governance

> **Precedence:** Where anything here conflicts with `CLAUDE.md`, **CLAUDE.md wins** — including its autonomy rules (act without asking, commit and push without asking). The only stops for user approval are the Compliance Gates below, anything tagged "don't change X", and destructive ops.

This is a personal automation hub, not a business entity — no legal/marketing/compliance surface, so there are only 3 agent personas.

## Agents

| Agent | Role | Domain | Approval Authority |
|-------|------|--------|--------------------|
| **cfo** | Chief Financial Officer | Personal QuickBooks, bank reconciliation, bitcoin dashboard | Any payment/transfer/transaction >$5,000 requires explicit approval |
| **csp** | Chief Software Programmer | `execution/` scripts, Modal webhook system, `rep-pwa/` | Credential/API-key/OAuth changes require explicit approval before applying |
| **auditor** | Chief Audit Officer | Post-task quality review, `tasks/lessons.md` | Read-only reviewer; flags compliance gates it finds skipped |

Spawn any of these by name via the Agent tool. `auditor` can run in parallel with either of the other two.

## Compliance Gates (require explicit user approval)

- **Large transaction** — any payment, transfer, or transaction over $5,000.
- **Credential change** — API keys, OAuth tokens, `.env`/`credentials.json`/token file changes.
- **Deletion** — any delete operation.

Full machine-readable gate definitions: `agents/registry.json`.

## Lessons

`tasks/lessons.md` is the single institutional-memory file — non-obvious root causes, corrections, and API quirks. Grep it at the start of a task per CLAUDE.md.
