# API Contract Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the DevOps run APIs use one explicit camelCase JSON contract with fixed pagination and consistent exit-code fields.

**Architecture:** Django serializers define explicit public DTO fields and translate model fields at the API boundary. Vue API types consume only camelCase DTOs; pagination always returns `{list,total,page,size}`. Legacy `after_id` handling is removed from production event logic.

**Tech Stack:** Django REST Framework, Django models, Vue 3, TypeScript, Vite, pytest, vue-tsc.

**Spec:** `backend/docs/2026-09-07-devops-refactor.md` sections 11–14.

## Global Constraints

- Database model fields remain snake_case; public JSON fields are camelCase.
- No compatibility response aliases or dual protocol.
- Existing databases are not cleared; tests use isolated databases only.
- No production asset, queue, Redis, or MySQL connection from this workspace.
- Keep soybean-admin component and route conventions.

---

### Task 1: Define explicit run DTO serializers

**Files:**
- Modify: `backend/apps/jobs/serializers.py`
- Test: `backend/apps/jobs/test_api_contract.py`

**Interfaces:**
- Produces explicit `WorkflowRunSerializer`, `NodeRunSerializer`, `HostRunResultSerializer`, and `JobEventLogSerializer` camelCase output.
- `NodeRun` and `HostRunResult` expose `exitCode`.

- [ ] Add serializer contract tests asserting exact public keys and absence of snake_case aliases.
- [ ] Replace `fields = "__all__"` with explicit fields and `source=` mappings.
- [x] Map node `exit_code` and host `rc` to `exitCode`.
- [x] Run the jobs API tests.

### Task 2: Make pagination invariant

**Files:**
- Modify: `backend/common/pagination.py`
- Modify: `backend/common/api/viewsets.py`
- Test: `backend/apps/jobs/test_api_contract.py`

**Interfaces:**
- Every paginated list returns `{list,total,page,size}` regardless of query parameters.

- [ ] Add tests for empty, one-row, and page-sized lists without query-parameter variation.
- [ ] Update list handling to always use `StandardResultSetPagination` for configured model viewsets.
- [ ] Remove `result`, `count`, and `num_pages` from the public contract where these are not required.
- [ ] Run pagination and permission regressions.

### Task 3: Remove the legacy event parameter

**Files:**
- Modify: `backend/apps/jobs/views.py`
- Modify: `frontend/src/service/api/jobs.ts`
- Test: `backend/apps/jobs/test_event_api.py`

**Interfaces:**
- Events accept only `cursor` and `limit`; unknown `after_id` is rejected by normal parameter validation.

- [ ] Add a negative test asserting `after_id` is rejected without a compatibility branch.
- [x] Remove the explicit `after_id` production branch and keep only cursor validation.
- [x] Keep frontend event calls cursor-only.
- [x] Run event API tests.

### Task 4: Synchronize frontend DTOs and pages

**Files:**
- Modify: `frontend/src/typings/api/jobs.d.ts`
- Modify: `frontend/src/views/task/run/index.vue`
- Modify: `frontend/src/views/task/run-detail/index.vue`
- Modify: `frontend/src/service/api/jobs.ts`

**Interfaces:**
- Frontend consumes only camelCase run, node, host-result, and event fields.
- `fetchRunLogFile(id, domain, signal?)` supports cancellation.

- [x] Change frontend DTO fields to camelCase and remove snake_case aliases.
- [x] Update list/detail/node/host/event templates to camelCase fields.
- [x] Add `AbortSignal` to log download and cancel it on scope disposal.
- [ ] Run vue-tsc, ESLint, event stream tests, and Vite build.

### Task 5: Contract cleanup and delivery record

**Files:**
- Modify: `backend/docs/refactor-progress.md`
- Modify: `backend/docs/acceptance.md`
- Test: repository scans and full backend/frontend checks.

- [ ] Scan for old public field names, `after_id` callers, and static demo headers.
- [ ] Record changed/deleted fields and tests with exact counts.
- [ ] Run `git diff --check`, Django checks, migration diff check, backend regression, frontend typecheck, lint, and build.
- [ ] Leave real Redis/MySQL, multi-instance, Runner, and performance results as the separately reported internal acceptance evidence.
