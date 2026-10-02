# Development workflow — google-analytics-mcp-cuan

**Version:** 1.0.0 · **Effective:** 2026-10-02 (Asia/Jakarta)

## Repository binding

- Owned repository: [ramadhanidiwanda-alt/google-analytics-mcp](https://github.com/ramadhanidiwanda-alt/google-analytics-mcp).
- Todoist: [Google Connectors](https://app.todoist.com/app/project/6hgJJRQP9q35Fj2p) (`6hgJJRQP9q35Fj2p`).
- Responsibility: Google Analytics provider runtime. Cuan owns OAuth/entitlement; Adstream owns hub routing.
- The owned fork is `origin`; vendor repositories, where present, are `upstream`. Never push workflow changes to vendor upstream.
- Read existing root/nested instructions and local architecture/contribution/testing documents alongside this workflow.

<!-- BEGIN SHARED WORKFLOW v1.0.0 -->
## Sources of truth

- Todoist owns priority, execution order, assignee and operational status.
- Versioned repository documents own scope, technical decisions, plans and validation evidence. Commits/PRs own implementation history.
- The ecosystem roadmap is maintained in Cuan Insight at `docs/roadmap/development-roadmap.md`. It describes outcomes and sequencing, not a second live task board.
- Every repository carries this shared workflow locally. Canonical source: [Cuan Insight workflow](https://github.com/ramadhanidiwanda-alt/cuan-insight/blob/main/docs/operations/development-workflow.md).
- Update the version and shared block in all six repositories together. Repository bindings outside the block may differ. A mismatch must be reported and reconciled within an authorized task.
- These documents complement existing repository security, approval and release rules. They do not grant permission to push, deploy, change provider data or perform destructive operations.

## Project ownership

| Todoist project | ID | Responsibility |
| --- | --- | --- |
| Cuan Insight Roadmap | `6gjV6q7hVQCW79F2` | UI, OAuth, credentials, organization/workspace access, billing, entitlement |
| Adstream MCP Roadmap | `6gv37Wg4qR6MHMpC` | MCP hub, transport, routing, gateway, execution admission |
| Google Connectors | `6hgJJRQP9q35Fj2p` | Ads, Analytics, Search Console and Drive/Workspace provider runtimes |

A project is an ownership boundary, not necessarily one Git repository. Do not create a project for every small repository. Marketing tasks already in Cuan may remain there, but must not receive the `engineering` label.

## Status and delivery

| Section | Entry / exit condition |
| --- | --- |
| Inbox | New report or idea; clarify reproduction, impact and desired outcome |
| Backlog | Understood candidate; not yet selected or approved for implementation |
| Ready | Scope, acceptance criteria, validation and human approval recorded; dependencies satisfied |
| Doing | Approved work is actively underway |
| Review / QA | Reviewable result and validation evidence available; acceptance still pending |
| Release | Required review/checks passed; agreed merge/deployment still pending |
| Blocked | Explicit blocker, dependency link, responsible party and next action recorded |

Complete a task only at its agreed delivery boundary. Record `Delivery: research`, `docs`, `merged` or `deployed` in its description. Code committed locally is not deployed. A code-preparation task can finish at merge if that was its approved scope; production acceptance then remains a separately linked task. Superseded/canceled tasks need an explicit disposition before completion.

If an otherwise-ready task needs review fixes, move it back to Doing. Removing a blocker returns the task to Backlog/Ready as appropriate; it never silently grants approval.

## Priority and order

- P1: demonstrated critical outage, security exposure or core flow failure requiring immediate attention.
- P2: important bug or high-impact near-term work.
- P3: planned normal work.
- P4: unprioritized or deferred idea.
- A priority is not authorization. A bug is not automatically P1.
- Use manual order within Ready for tasks with the same priority. For selection across projects, record the next sequence in the roadmap and apply `focus` only to the selected active task.
- Use dates for real commitments, not as a substitute for backlog rank.
- Review the backlog weekly when a session is requested. This rule does not create a scheduled automation.

## Labels and one active focus

- Every coding/workflow task: `engineering`.
- Type: `bug`, `feature`, `maintenance`, `docs` or `marketing`; preserve existing labels when updating.
- Area/provider only when useful: `ai-access`, `billing`, `ops`, `integration`, `google-ads`, `google-analytics`, `google-search-console`, `google-workspace`.
- `focus` identifies at most one main active task across the three projects. When account capacity allows, **Fokus Coding** uses `@engineering & @focus`, **Antrean Coding** uses `@engineering & /Ready` and **Coding Blocked** uses `@engineering & /Blocked`.
- Rollout limit (2026-10-02): Todoist rejected new saved filters with HTTP 403, maximum filters reached. Existing personal filters were preserved. Use the favorite **focus** label for active work and the Ready/Blocked board columns for queues. A future filter setup is optional; do not assume these saved filters exist.
- At session start, inspect the global focus, not just this repository's board. Respect another active session's ownership; do not remove its label or change task/branch state blindly.
- Parallel substeps may serve the same approved main task when local delegation rules allow them. Independent product work does not become a second focus without a human decision.
- Capture unrelated discoveries in Inbox. Do not change the active task or expand its scope without user authorization.

## Task contract and links

Before Ready, the task must contain:

1. Problem/outcome, affected repository/provider and evidence or reproduction.
2. Scope and exclusions, plus objective acceptance criteria.
3. Agreed delivery boundary, validation commands or manual checks and known limitations.
4. Links to the plan and prerequisite tasks where needed.
5. Human approval evidence: actor, session/date reference and approved scope. A Ready section or label alone is not approval.

Use the immutable Todoist task ID and URL as the join key. A plan/header should include:

```text
Todoist: https://app.todoist.com/app/task/<task-id>
Repositories: <owned repositories>
Delivery: <research|docs|merged|deployed>
Approval: <human/session reference and scope>
Dependencies: <task links, or none>
Validation: <commands/manual checks and acceptance evidence>
```

Small tasks keep their scoped plan/acceptance and final evidence in the versioned local handoff document or an existing plan/phase document; Todoist carries the summary and link. Substantial or cross-repo tasks link to existing versioned plan locations; do not create duplicate plan files in every repository. All affected repositories must still be named. Link the task from the PR body and the relevant phase log.

For cross-repo delivery, create a coordination task only when needed. Each child task owns a distinct result, not a duplicate report. Link prerequisites and dependent tasks in both directions. A parent's completion requires evidence from all required children.

## Session protocol

### Start

1. Read root/nested AGENTS instructions, this local workflow and task/plan documents.
2. Inspect Git status, tracking remote, recent commits and any rebase/merge state. Preserve unrelated changes. For Cuan schema/RPC work, inspect linked migration history before adding migrations.
3. Read the global focus and target Todoist task; compare their claims against actual repository/release evidence. Historical logs are not proof of current runtime health.
4. Confirm existing authorization covers the planned scope, files, validation and delivery. Do not ask again for the same scope already authorized in the session. Ask only for missing authorization or material scope changes.
5. Record session/branch ownership in the active task. Move to Doing only when starting/resuming approved implementation, after checking for another owner. Review-only or blocked sessions retain their existing status until evidence supports a transition. Apply focus only to the agreed main active task.

### During work

- Work from the approved plan. Keep provider tokens, Connection Keys and customer data out of task descriptions, comments, commits and logs.
- Update status at meaningful transitions, not at every micro-commit.
- Record blockers with an actionable next step. Provider writes and deployment need the permissions required by the affected repository.

### End a phase / session

1. Run checks appropriate to the scope; inspect results. Record uncovered cases honestly.
2. Commit only owned files. Use existing log conventions (including Cuan's phase-based LOG updates); local-only CONTEXT files are not the shared authority.
3. Put validation and commit/PR/release links in Todoist, then move to the evidenced status.
4. Complete only when the agreed acceptance/delivery criteria are met. Remove focus on completion; retain it on an active blocker or explicit pause only with a clear handoff.
5. Report Git branch, cleanliness and ahead/behind against the **owned** origin/main. Keep upstream vendor history separate. Remove this task's merged branches/scratch artifacts after verification; preserve unrelated work.
6. For Cuan handoff, freshly check linked migration drift. Record any debt; never infer zero drift from an old log.

## Sync failures and reconciliation

This is an agent-enforced protocol, not an automatic sync service.

Every repository has a versioned fallback at `docs/operations/session-handoff.md`. If Todoist is unavailable, continue already-authorized work that does not depend on missing scope/ownership information. Record the task ID, intended status/description update and evidence there under **Pending Todoist sync**, or link an equivalent entry in an existing phase document. The fallback also stores small-task plans and acceptance evidence. Report that sync is pending. Do not claim the board is updated, invent a task ID or overwrite unknown session ownership.

When access returns, inspect current task state before applying pending updates so a newer human change is not overwritten. Read back the updated task. Then mark the pending entry resolved. No task is marked complete merely because a remote update was attempted.

If repository evidence and Todoist disagree, reconcile the specific discrepancy before implementation. Preserve original requests and add a dated reconciliation note; do not silently change product policy or close a task based only on a deployment note.

## Initial rollout authorization

Ramadhani authorized the discussed project organization, six-repository documentation, backlog reconciliation, origin/local synchronization and cleanup on 2026-10-02. This authorization covers the workflow rollout only. Existing product bugs/features still need their own approved implementation plans.
<!-- END SHARED WORKFLOW v1.0.0 -->
