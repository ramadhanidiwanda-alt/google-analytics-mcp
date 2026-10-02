# AGENTS.md — google-analytics-mcp-cuan

These instructions apply to this Cuan-owned fork. Preserve upstream contribution and security requirements.

## Required context

- Read [README.md](./README.md) and [development workflow](./docs/operations/development-workflow.md).
- Read existing contribution/build/testing guidance for the touched area.
- Hosted mode is client-agnostic. Cuan Insight stores provider credentials and controls organization/account/tool permissions; Adstream owns public hub routing. Do not bypass permits/grant checks or expose credentials in output.
- Scope here: Google Analytics provider runtime. Cuan owns OAuth/entitlement; Adstream owns hub routing.
- Owned remote: `origin` → `ramadhanidiwanda-alt/google-analytics-mcp`. Vendor source: `upstream`. Never push Cuan changes to vendor upstream.
- Use feature branches prefixed `codex/`, preserve unrelated work and obtain explicit authorization for push/deploy/provider writes. Live Google mutations are separate from local build/tests.

## Todoist coordination (workflow v1.0.0)

Read [development workflow](./docs/operations/development-workflow.md) before implementation.
- Identify the Todoist task, read global focus (favorite **focus** label; **Fokus Coding** filter if available) and reconcile task claims with repository evidence.
- Link the task ID/URL from the plan and PR; document scope, acceptance, delivery boundary, validation and existing human approval.
- Ready alone is not approval. Respect authorization already granted in the session; do not expand scope or start the next task without permission.
- Keep at most one main focus across Cuan Insight, Adstream and Google Connectors. Respect another session's task/branch ownership.
- Update Todoist at Doing, Blocked, Review / QA, Release and completion with evidence appropriate to the agreed delivery.
- If Todoist is unavailable, record **Pending Todoist sync** in the phase/handoff document and report it. Do not claim synchronization or completion without evidence.
- Finish with owned changes committed, verified Git tracking/cleanliness, and this task's artifacts/merged branches cleaned up. Preserve unrelated work.
