# Pramita Lab — SDM Decision Support System
## Project Context (Token-saving reference for future sessions)

---

## Stack
- **Backend**: FastAPI + SQLAlchemy + Jinja2 (SSR/MPA architecture)
- **Frontend**: Vanilla JS + Jinja2 templates (no React/Vue)
- **DB**: SQLite (dev), SQLAlchemy ORM
- **Auth**: JWT via cookie (`access_token`)
- **Server**: Uvicorn — `uvicorn backend.main:app`
- **Base URL**: `http://127.0.0.1:8000`

---

---

## Roles & Permissions
| Role | Value | Access |
|------|-------|--------|
| Kepala Divisi | `kepala_divisi` | Submit SDM requests only |
| Kepala HRD | `kepala_hrd` | Gate A/B, forward/reject requests, **trigger profile matching**, manage master data |
| Kepala Cabang | `kepala_cabang` | View matching results, approve/reject, issue transfer letter |

---

## Confirmed Workflow (Final)
```
Kepala Divisi
  → POST /api/sdm/requests
  → Budget check: ADVISORY ONLY (never blocks, shows warning to HRD)
  → status: pending

Kepala HRD
  → Views /requests (sees all pending)
  → POST /api/gates/evaluate-initial  (Gate A: education + sanction check per candidate)
  → If interview_pending → /gates page → POST /api/gates/interview-scores (Gate B)
  → POST /api/sdm/requests/{id}/forward  → status: forwarded
  → POST /api/sdm/requests/{id}/run-matching  ← HRD triggers this (not Kepala Cabang)
  → status: matched

Kepala Cabang
  → Views /results?request_id={id}
  → Approve or reject
  → POST /api/sdm/transfer-letters  → status: approved
```

---

## Key Bugs

### 1. 422 on POST /api/sdm/requests
- **Cause**: Frontend sent `notes`, backend schema expected `reason`
- **Thoughts/Plan**: Change JS payload key from `notes` to `reason` in `requests.html`

### 2. Empty table on /requests
- **Cause**: `main.py` passes `requests_data` to template but template iterates `requests`
- **Thoughts/Plan**: Change key in `view_requests()` from `requests_data` to `requests`

### 3. Budget hard-blocking requests (gate_rejected)
- **Cause**: `create_sdm_request` set `status = RequestStatus.gate_rejected` when budget exceeded
- **Thoughts/Plan**: Always set `status = RequestStatus.pending`; budget result only affects `budget_gate_status` field (advisory warning shown to HRD only)

### 4. Gates page unreachable
- **Cause**: No nav link in `base.html` for `/gates`
- **Thoughts/Plan**: Add nav link under `kepala_hrd` section in `base.html`

### 5. run_matching NameError crash
- **Cause**: References `ranked` and `persisted` variables that are never defined; `rank_employees()` imported but never called
- **Thoughts/Plan**: Call `rank_employees(match_results)`, build `persisted` list, then insert `MatchingResult` rows

### 6. Role comparison fragility
- **Cause**: Jinja2 templates used inconsistent role checks (`current_user.role.value`, `current_user.role | string`, etc.)
- **Thoughts/Plan**: Standardize to `{% set role_str = current_user.role.value if current_user.role.value is defined else current_user.role | string %}`

---

## Data Models (Key fields)

### SDMRequest
```python
id, requester_id, target_division_id, quantity, reason
status: RequestStatus          # pending, forwarded, under_review, matched, approved, rejected, gate_rejected
budget_gate_status: GateStatus # passed, failed (advisory only)
budget_notes: Text             # shown to HRD as warning
is_auto_generated: bool
hrd_notes: Text
created_at, updated_at
```

### RequestStatus enum
```python
pending, gate_check, interview_required, forwarded,
under_review, matched, approved, rejected, gate_rejected
```

### GateStatus enum
```python
pending, interview_pending, interview_passed, interview_failed, passed, failed
```

### RotationGate
```python
id, sdm_request_id, employee_id
education_gate_status: GateStatus
education_gate_notes: Text
interview_gate_status: GateStatus   # nullable
interview_gate_notes: Text
is_eligible_for_matching: bool
```

### MatchingResult
```python
id, sdm_request_id, employee_id
ncf_score, nsf_score, final_score: Float
rank: int
computed_at: DateTime
```

---

## API Endpoints

### SDM
| Method | Path | Role | Description |
|--------|------|------|-------------|
| POST | /api/sdm/requests | kepala_divisi | Create SDM request |
| GET | /api/sdm/requests | all | List requests (filtered by role in service) |
| POST | /api/sdm/requests/{id}/forward | kepala_hrd | Forward to Kepala Cabang |
| POST | /api/sdm/requests/{id}/reject | kepala_hrd | Reject with notes |
| POST | /api/sdm/requests/{id}/run-matching | kepala_hrd + kepala_cabang | Trigger profile matching |
| GET | /api/sdm/requests/{id}/results | all | Get matching results |
| POST | /api/sdm/transfer-letters | kepala_cabang | Issue transfer letter |

### Gates
| Method | Path | Role | Description |
|--------|------|------|-------------|
| POST | /api/gates/evaluate-initial | kepala_hrd | Gate A: education + sanction check |
| POST | /api/gates/interview-scores | kepala_hrd | Gate B: submit interview/assessment scores |
| POST | /api/gates/fail-interview | kepala_hrd, kepala_cabang | Manually fail a candidate |

### Web Views (SSR)
| Path | Template | Active For |
|------|----------|------------|
| /dashboard | dashboard.html | all |
| /requests | requests.html | all roles |
| /gates | gates.html | kepala_hrd |
| /results | results.html | kepala_cabang, kepala_hrd |
| /employees | employees.html | kepala_hrd |
| /criteria | criteria.html | kepala_hrd |
| /divisions | divisions.html | kepala_hrd |
| /wla | wla.html | kepala_hrd |

---

## Pending Changes To Implement

### routers/sdm.py
Change `run-matching` to allow both HRD and Kepala Cabang:
```python
# Before:
_: User = Depends(require_role("kepala_cabang"))

# After:
_: User = Depends(require_role("kepala_hrd", "kepala_cabang"))
```

### sdm_service.py — Thoughts/Plan run_matching
```python
# After match_results populated, replace broken ranked/persisted refs:
ranked = rank_employees(match_results)

db.query(MatchingResult).filter(
    MatchingResult.sdm_request_id == request_id
).delete()

persisted = []
for rank, result in enumerate(ranked, start=1):
    row = MatchingResult(
        sdm_request_id=request_id,
        employee_id=result.employee_id,
        ncf_score=result.ncf_score,
        nsf_score=result.nsf_score,
        final_score=result.final_score,
        rank=rank,
    )
    db.add(row)
    persisted.append(row)

sdm_request.status = RequestStatus.matched
db.commit()
for row in persisted:
    db.refresh(row)
return persisted
```

### sdm_service.py — Thoughts/Plan create_sdm_request (budget advisory)
```python
# Always pending, never gate_rejected:
request = SDMRequest(
    ...
    status=RequestStatus.pending,   # was: req_status (which could be gate_rejected)
    budget_gate_status=budget_gate,
    budget_notes=budget_notes,
    ...
)
```

### main.py — Thoughts/Plan template variable name
```python
# view_requests(): change requests_data → requests
return templates.TemplateResponse("requests.html", {
    ...
    "requests": reqs,   # was: "requests_data"
    ...
})
```

### base.html — add gates nav for HRD
```html
<a href="/gates" class="nav-item {% if active_page == 'gates' %}active{% endif %}">
  Asesmen Kandidat
</a>
```

### requests.html — role-based action buttons
- Kepala Divisi: read-only, shows status
- Kepala HRD: Forward + Reject buttons (pending), Run Matching button (forwarded), budget warning label
- Kepala Cabang: view results only

### requests.html — Thoughts/Plan form submission field name
```javascript
// Was: notes: notes
reason: notes
```

---

## Notes & Decisions
- `UserRole` inherits from `str` so `role == "kepala_divisi"` works in Python, but Jinja2 needs `.value`
- `budget_gate_status` column is `nullable=False` with `default=GateStatus.pending` — safe, no migration needed
- Gates page shows candidates across ALL requests (not per-request) so HRD sees the full queue
- `gate_rejected` status kept in enum as HRD-initiated rejection (budget grounds), not system-auto
- Modal loading uses `App.loadModal()` from `/static/js/app.js` — modals served from `/modals/` static mount
- FastAPI auto-redirects `/api/divisions` → `/api/divisions/` (307) — normal behavior, not a bug