---
name: SDM Profile Matching Project Planning
description: >
  Established decisions, architecture context, and execution order for the Employee Modal
  and Division Page restructuring features in the SDM Profile Matching thesis project.
  Covers backend schema changes, frontend modal/form changes, Gate 1 budget auto-pass,
  salary/budget field hiding, division grouping, employee assignment boxes, and WLA aggregation.
  Reference this skill when working on employees.html, divisions.html, employee schemas/routers,
  sdm_service.py, or any feature related to employee editing, division restructuring, criteria scores,
  or the SDM mutation flow.
---

# SDM Profile Matching — Project Planning Context

> **Source**: [planning.md](file:///d:/Kuliah/Porto/FastAPI/planning.md)
>
> Always re-read `planning.md` if you need the full original context. This skill
> summarises the **confirmed decisions and guardrails** so you don't have to re-derive them.

---

## Key File Mapping

| Concept | Files |
|---|---|
| Employee edit modal | `frontend/templates/employees.html` |
| Division page | `frontend/templates/divisions.html` |
| Employee schemas | `backend/schemas/employee.py` |
| Employee router | `backend/routers/employees.py` |
| SDM service (Gate 1) | `backend/services/sdm_service.py` |
| Division modal (possibly dead) | `frontend/modals/modal-division.html` |
| Seed data | `seed.py` |

---

## Confirmed Decisions (✅)

1. **PATCH vs PUT bug**: The frontend `employees.html` uses `method: 'PUT'` but the backend only defines `@router.patch`. Fix by changing the frontend fetch to `PATCH` (consistent with `EmployeeUpdate` partial-update semantics).

2. **Gaji Pokok (base_salary)**: **Option B** — hide from UI only, do NOT drop the DB column (no migration). The column becomes dead data. Add a comment in the model noting it is unused.

3. **Gate 1 Budget Check → auto-pass**: Remove all financial calculations (`current_expenses`, `company_avg_salary`, `projected_additional_cost`, `total_projected_expense`) from `create_sdm_request` in `sdm_service.py`. Set `budget_gate = GateStatus.passed` unconditionally with clear notes stating this is by design, not a bug. Keep the `budget_gate_status` / `budget_notes` schema fields for historical data compatibility.

4. **Division monthly_budget**: Also hidden from UI (`divisions.html` — remove from add/edit modal and from the table column "ANGGARAN BULANAN"). Column stays in model, same rationale as `base_salary`. Already verified no hidden dependencies beyond `divisions.html`, `sdm_service.py`, `seed.py`, and model/schema.

5. **Employee assignment box (divisions.html bottom section)**: For **initial placement only** (new employees / never-mutated). Official mutations still go through `SDMRequest → TransferLetter` (Gate A/B, WLA check in `simulate_rotation` untouched). Show warning text in UI: "Gunakan hanya untuk penempatan awal — mutasi resmi lewat menu Pengajuan Mutasi SDM".

6. **Total WLA per Group Divisi**: Sum of `total_workload_hours` and `headcount` across sub-divisions in the group (NOT average of `wla_value`). Fetch per-division via `GET /api/wla/division/{id}/latest`, aggregate client-side (scale is small). **WLA per individual sub-divisi: PENDING** (awaiting stakeholder clarity).

---

## Execution Order

Follow this order strictly — each step depends on the previous:

1. **Fix PATCH/PUT bug** (blocker, ~5 min)
2. **Gate 1 auto-pass + hide `emp_salary`** from `employees.html`
3. **Hide `div_budget`** from `divisions.html` (add/edit modal + table column)
4. **Nested schema** — add `division_name`, `group_id`, `group_name` to `EmployeeRead`
5. **Feature 1**: Employee edit modal with dynamic criteria scores
   - Dynamic criteria section populated via `GET /api/criteria/division/{division_id}`
   - Refreshes when Sub Divisi dropdown changes
   - Score inputs 0–5, prefilled from `EmployeeRead.scores` in edit mode
   - Group Divisi displayed as read-only text
   - Backend: upsert scores logic in `update_employee` (delete-all + re-insert strategy)
   - Extract `_validate_and_persist_scores()` helper to avoid duplication with `create_employee`
6. **Feature 2 top**: Group name fix (replace raw `ID: {group_id}`), restructure divisions into grouped cards, total WLA per group
7. **Feature 2 bottom**: Employee assignment boxes per sub-division with warning text

---

## Backend Change Checklist

### `backend/schemas/employee.py`
- `EmployeeRead`: Add `division_name`, `group_id`, `group_name` (computed/nested)
- `EmployeeUpdate`: Add `scores: Optional[list[EmployeeScoreCreate]] = None`

### `backend/routers/employees.py`
- `update_employee`: Add upsert-scores logic (delete existing + insert from payload)
- When `division_id` changes: validate that submitted `criteria_id`s belong to the new division's group
- Extract `_validate_and_persist_scores(db, emp_id, scores)` shared helper

### `backend/services/sdm_service.py`
- `create_sdm_request`: Replace Gate 1 block → `budget_gate = GateStatus.passed`, clear explanatory `budget_notes`

---

## Frontend Change Checklist

### `frontend/templates/employees.html`
- Change fetch method from `PUT` to `PATCH`
- Remove `emp_salary` input from form and payload
- Add dynamic "Penilaian Kriteria" section in edit modal
- Show Group Divisi as read-only text
- Criteria inputs: number 0–5, prefilled from employee scores

### `frontend/templates/divisions.html`
- Remove `div_budget` input from add/edit modal
- Remove "ANGGARAN BULANAN" column from table
- Fix group name display (replace raw ID span with name from `Map(id → name)`)
- Restructure: group-by `group_id`, render cards per group containing sub-divisions
- Add bottom section: per sub-division box with employee list + assign functionality
- Warning text for assignment box

---

## Guardrails & Gotchas

- **Do NOT drop `base_salary` or `monthly_budget` columns** — hide from UI only, no migrations.
- **Do NOT touch the mutation flow** (`SDMRequest`, `TransferLetter`, Gate A/B, `simulate_rotation`) — these remain intact.
- **`frontend/modals/modal-division.html`** may be dead code — audit before modifying. Check if any other page references it.
- **Seed data** (`seed.py`): Can keep generating `base_salary` values (harmless), cleanup is optional.
- **Concurrency**: No row-level locking on score upsert. Acceptable for current single-admin usage; revisit if multi-admin editing becomes a requirement.
