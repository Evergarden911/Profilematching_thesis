"""
Constraint Service — Rotation Gate Evaluation
==============================================
Implements the two-gate eligibility pipeline that all candidates
must pass before entering Profile Matching.

Gate A — Education Check
  Rules loaded from DivisionConstraint:
    - constraint_type = "blocked"  → candidate's education field is explicitly denied → FAIL
    - constraint_type = "allowed"  → candidate's education field is permitted → PASS Gate A
    - No constraint row for this field → default PASS (open policy)
  After Gate A pass, check whether Gate B is needed.

Gate B — Interview + Test (conditional)
  Required when:
    candidate's current division is OUTSIDE the target division's group
    AND the matching DivisionConstraint has requires_interview_if_not_native = True
  Process:
    1. HRD records raw scores (0–100) per criteria via Frontend.
    2. System converts to 1–5 scale: converted = raw / 100 * 4 + 1
    3. Converted scores are directly written to EmployeeScore.
    4. Candidate is flagged is_eligible_for_matching = True
    5. Profile Matching runs using these updated converted scores.

Score conversion:
  Linear map: 0 → 1.0, 50 → 3.0, 100 → 5.0
  Formula: converted = (raw / 100) * 4 + 1
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.models import (
    ConstraintType,
    GroupCriteria,
    Division,
    DivisionConstraint,
    Employee,
    EmployeeScore,
    GateStatus,
    RotationGate,
    SDMRequest,
    User,
)

# ---------------------------------------------------------------------------
# Score conversion
# ---------------------------------------------------------------------------

RAW_SCORE_MIN: float = 0.0
RAW_SCORE_MAX: float = 100.0
CONVERTED_MIN: float = 1.0
CONVERTED_MAX: float = 5.0


def convert_interview_score(raw_score: float) -> float:
    """
    Linear conversion from 0–100 interview scale to 1–5 profile-matching scale.
    Formula: converted = (raw / 100) * 4 + 1
    """
    if not (RAW_SCORE_MIN <= raw_score <= RAW_SCORE_MAX):
        raise ValueError(f"raw_score must be between {RAW_SCORE_MIN} and {RAW_SCORE_MAX}, got {raw_score}")
    return round((raw_score / 100.0) * 4.0 + 1.0, 4)


# ---------------------------------------------------------------------------
# Gate A — Education eligibility
# ---------------------------------------------------------------------------

def evaluate_education_gate(
    db: Session,
    sdm_request_id: int,
    employee_id: int,
) -> RotationGate:
    """
    Evaluate Gate A for a single candidate against the target division's
    education constraints.
    """
    request = _get_request_or_404(db, sdm_request_id)
    employee = _get_employee_or_404(db, employee_id)
    target_division = _get_division_or_404(db, request.target_division_id)

    gate = _get_or_create_gate(db, sdm_request_id, employee_id)

    if employee.has_sanction:
        gate.education_gate_status = GateStatus.failed
        gate.education_gate_notes = "Employee is currently under sanction."
        gate.education_checked_at = datetime.now(timezone.utc)
        gate.is_eligible_for_matching = False
        db.commit()
        db.refresh(gate)
        return gate

    if employee.education_field_id is None:
        gate.education_gate_status = GateStatus.failed
        gate.education_gate_notes = "Employee has no education field recorded. Update employee profile first."
        gate.education_checked_at = datetime.now(timezone.utc)
        gate.is_eligible_for_matching = False
        db.commit()
        db.refresh(gate)
        return gate

    constraint: DivisionConstraint | None = (
        db.query(DivisionConstraint)
        .filter(
            DivisionConstraint.division_id == request.target_division_id,
            DivisionConstraint.education_field_id == employee.education_field_id,
        )
        .first()
    )

    if constraint is None:
        gate.education_gate_status = GateStatus.passed
        gate.education_gate_notes = "No restriction configured for this education field. Open policy."
        gate.education_checked_at = datetime.now(timezone.utc)
        _decide_interview_requirement(db, gate, employee, target_division, requires_interview=False)
        db.commit()
        db.refresh(gate)
        return gate

    if constraint.constraint_type == ConstraintType.blocked:
        gate.education_gate_status = GateStatus.failed
        gate.education_gate_notes = (
            f"Education field '{employee.education_field.name}' is not permitted "
            f"for rotation into '{target_division.name}'."
            + (f" Note: {constraint.notes}" if constraint.notes else "")
        )
        gate.education_checked_at = datetime.now(timezone.utc)
        gate.is_eligible_for_matching = False
        db.commit()
        db.refresh(gate)
        return gate

    gate.education_gate_status = GateStatus.passed
    gate.education_gate_notes = (
        f"Education field '{employee.education_field.name}' is permitted for '{target_division.name}'."
    )
    gate.education_checked_at = datetime.now(timezone.utc)
    _decide_interview_requirement(
        db, gate, employee, target_division,
        requires_interview=constraint.requires_interview_if_not_native,
    )
    db.commit()
    db.refresh(gate)
    return gate


def _decide_interview_requirement(
    db: Session,
    gate: RotationGate,
    employee: Employee,
    target_division: Division,
    requires_interview: bool,
) -> None:
    if not requires_interview:
        gate.is_eligible_for_matching = True
        return

    employee_division = db.query(Division).filter(Division.id == employee.division_id).first()

    same_group = (
        target_division.group_id is not None
        and employee_division is not None
        and employee_division.group_id == target_division.group_id
    )

    if same_group:
        gate.is_eligible_for_matching = True
        gate.interview_gate_notes = "Employee is within the same division group. Interview not required."
    else:
        gate.interview_gate_status = GateStatus.interview_pending
        gate.interview_gate_notes = (
            f"Employee is from '{employee_division.name if employee_division else 'unknown'}', "
            f"which is outside the '{target_division.group.name if target_division.group else target_division.name}' group. "
            "Interview + test required before Profile Matching."
        )
        gate.is_eligible_for_matching = False


# ---------------------------------------------------------------------------
# Gate B — Record and process interview scores
# ---------------------------------------------------------------------------

def record_interview_scores(
    db: Session,
    gate_id: int,
    scores: list[dict],  
    scored_by: User,
) -> list[dict]:
    """
    Mengonversi skor mentah (0-100) dan langsung menyuntikkannya ke EmployeeScore.
    Menghapus ketergantungan pada tabel InterviewScore yang telah usang.
    """
    gate = _get_gate_or_404(db, gate_id)
    employee = gate.employee

    if gate.interview_gate_status != GateStatus.interview_pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Gate is in status '{gate.interview_gate_status}', expected 'interview_pending'.",
        )

    criteria_ids = [s["criteria_id"] for s in scores]
    found_criteria = {
        c.id: c
        for c in db.query(GroupCriteria).filter(GroupCriteria.id.in_(criteria_ids)).all()
    }
    
    missing = set(criteria_ids) - set(found_criteria.keys())
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group Criteria ID(s) not found: {sorted(missing)}",
        )

    results = []
    for entry in scores:
        cid = entry["criteria_id"]
        raw = entry["raw_score"]

        try:
            converted = convert_interview_score(raw)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

        # Upsert: Timpa nilai lama jika sudah ada, buat baru jika belum ada
        existing_es = (
            db.query(EmployeeScore)
            .filter(EmployeeScore.employee_id == employee.id, EmployeeScore.criteria_id == cid)
            .first()
        )
        
        if existing_es:
            existing_es.score = converted
        else:
            db.add(EmployeeScore(employee_id=employee.id, criteria_id=cid, score=converted))
            
        # Mengembalikan format kamus agar sesuai dengan skema InterviewScoreRead di frontend
        results.append({
            "criteria_id": cid,
            "raw_score": raw,
            "score": converted
        })

    # Loloskan Gerbang
    gate.interview_gate_status = GateStatus.interview_passed
    gate.interview_checked_at = datetime.now(timezone.utc)
    gate.is_eligible_for_matching = True

    db.commit()
    return results


def fail_interview_gate(db: Session, gate_id: int, notes: str) -> RotationGate:
    gate = _get_gate_or_404(db, gate_id)
    gate.interview_gate_status = GateStatus.interview_failed
    gate.interview_gate_notes = notes
    gate.interview_checked_at = datetime.now(timezone.utc)
    gate.is_eligible_for_matching = False
    db.commit()
    db.refresh(gate)
    return gate


def get_eligible_employee_ids(db: Session, sdm_request_id: int) -> list[int]:
    gates = (
        db.query(RotationGate)
        .filter(
            RotationGate.sdm_request_id == sdm_request_id,
            RotationGate.is_eligible_for_matching == True,
        )
        .all()
    )
    return [g.employee_id for g in gates]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_gate(db: Session, sdm_request_id: int, employee_id: int) -> RotationGate:
    gate = (
        db.query(RotationGate)
        .filter(RotationGate.sdm_request_id == sdm_request_id, RotationGate.employee_id == employee_id)
        .first()
    )
    if not gate:
        gate = RotationGate(sdm_request_id=sdm_request_id, employee_id=employee_id)
        db.add(gate)
        db.flush()
    return gate


def _get_gate_or_404(db: Session, gate_id: int) -> RotationGate:
    gate = db.query(RotationGate).filter(RotationGate.id == gate_id).first()
    if not gate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rotation gate not found.")
    return gate


def _get_request_or_404(db: Session, request_id: int) -> SDMRequest:
    req = db.query(SDMRequest).filter(SDMRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SDM Request not found.")
    return req


def _get_employee_or_404(db: Session, employee_id: int) -> Employee:
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")
    return emp


def _get_division_or_404(db: Session, division_id: int) -> Division:
    div = db.query(Division).filter(Division.id == division_id).first()
    if not div:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Division not found.")
    return div

def evaluate_initial_constraints(db: Session, sdm_request_id: int, employee_id: int):
    request = _get_request_or_404(db, sdm_request_id)
    emp = _get_employee_or_404(db, employee_id)
    gate = _get_or_create_gate(db, sdm_request_id, employee_id)
    
    # 1. ATURAN SANKSI
    if emp.has_sanction:
        gate.education_gate_status = "failed"
        gate.education_gate_notes = "Ditolak di Gate A: Karyawan sedang dalam masa sanksi."
        db.commit()
        return gate

    # 2. ATURAN MATRIKS PENDIDIKAN
    from backend.models import DivisionConstraint
    constraint = db.query(DivisionConstraint).filter(
        DivisionConstraint.division_id == request.target_division_id,
        DivisionConstraint.education_field_id == emp.education_field_id
    ).first()

    if constraint:
        if constraint.constraint_type == "blocked":
            gate.education_gate_status = "failed"
            gate.education_gate_notes = "Ditolak di Gate A: Kualifikasi pendidikan diblokir untuk divisi ini."
        elif constraint.constraint_type == "allowed":
            is_native = (emp.division_id == request.target_division_id)
            if not is_native and getattr(constraint, 'requires_interview_if_not_native', False):
                gate.education_gate_status = "interview_pending"
                gate.education_gate_notes = "Lolos Gate A: Wajib mengikuti asesmen lintas fungsi."
            else:
                gate.education_gate_status = "passed"
                gate.education_gate_notes = "Lulus Gate A: Kualifikasi pendidikan sesuai."
    else:
        # OPEN POLICY
        is_native = (emp.division_id == request.target_division_id)
        if not is_native:
            gate.education_gate_status = "interview_pending"
            gate.education_gate_notes = "Lolos Gate A: Menerapkan Open Policy (Wajib Asesmen)."
        else:
            gate.education_gate_status = "passed"
            gate.education_gate_notes = "Lulus Gate A: Menerapkan Open Policy (Internal)."

    db.commit()
    return gate