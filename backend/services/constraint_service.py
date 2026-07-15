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
from sqlalchemy.orm import Session, contains_eager
from typing import List, Dict, Any

from backend.models import (
    ConstraintType,
    GroupCriteria,
    Division,
    DivisionConstraint,
    DivisionCriteriaWeight,
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

    # PERBAIKAN 1: Menggunakan employee.education.name (bukan employee.education_field.name)
    # PERBAIKAN 2: Menghapus pengecekan constraint.notes karena kolom tersebut tidak ada di skema ORM
    if constraint.constraint_type == ConstraintType.blocked:
        gate.education_gate_status = GateStatus.failed
        gate.education_gate_notes = (
            f"Education field '{employee.education.name}' is not permitted "
            f"for rotation into '{target_division.name}'."
        )
        gate.education_checked_at = datetime.now(timezone.utc)
        gate.is_eligible_for_matching = False
        db.commit()
        db.refresh(gate)
        return gate

    gate.education_gate_status = GateStatus.passed
    gate.education_gate_notes = (
        f"Education field '{employee.education.name}' is permitted for '{target_division.name}'."
    )
    gate.education_checked_at = datetime.now(timezone.utc)
    _decide_interview_requirement(
        db, gate, employee, target_division,
        requires_interview=constraint.requires_interview_if_not_native,
    )
    db.commit()
    db.refresh(gate)
    return gate

def get_target_assessment_criteria(db: Session, gate_id: int) -> list[dict]:
    """
    Mengambil daftar kriteria wajib dari Sub-Divisi Target untuk form Gate B.
    Mencegah sistem menarik kriteria divisi asal yang tidak relevan.
    """
    gate = _get_gate_or_404(db, gate_id)
    target_div_id = gate.sdm_request.target_division_id 

    div_weights = (
        db.query(DivisionCriteriaWeight)
        .join(GroupCriteria)
        .filter(
            DivisionCriteriaWeight.division_id == target_div_id,
            GroupCriteria.is_active == True
        )
        .options(contains_eager(DivisionCriteriaWeight.group_criteria))
        .all()
    )

    if not div_weights:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sub-divisi target belum memiliki konfigurasi bobot kriteria yang aktif."
        )

    output = []
    for dw in div_weights:
        gc = dw.group_criteria
        output.append({
            "criteria_id": gc.id,
            "name": gc.name,
            "target_value": gc.target_value,
            "factor_type": gc.factor_type.value,
            "weight": dw.weight
        })
    return output

def _decide_interview_requirement(
    db: Session,
    gate: RotationGate,
    employee: Employee,
    target_division: Division,
    requires_interview: bool,
) -> None:
    # 1. Ambil data divisi asal karyawan
    employee_division = db.query(Division).filter(Division.id == employee.division_id).first()

    # 2. Cek apakah divisi asal dan divisi target berada dalam SATU RUMPUN GRUP
    same_group = (
        target_division.group_id is not None
        and employee_division is not None
        and employee_division.group_id == target_division.group_id
    )

    # 3. ATURAN GERBANG B (Wawancara & Asesmen Kompetensi):
    # Gate B WAJIB dipicu jika:
    #   a) Rotasi LINTAS GRUP (not same_group) -> Wajib karena belum punya skor di grup baru
    #   b) ATAU aturan matriks (DivisionConstraint) secara eksplisit mewajibkan interview (requires_interview == True)
    if not same_group or requires_interview:
        gate.interview_gate_status = GateStatus.interview_pending
        gate.is_eligible_for_matching = False
        
        if not same_group:
            gate.interview_gate_notes = (
                f"Rotasi Lintas Grup: Dari '{employee_division.name if employee_division else 'unknown'}' "
                f"ke '{target_division.name}'. Wajib mengikuti asesmen kompetensi Gate B sebelum Profile Matching."
            )
        else:
            gate.interview_gate_notes = "Aturan matriks kualifikasi mewajibkan asesmen wawancara Gate B."
    else:
        # Rotasi internal satu grup & tidak ada kewajiban interview dari constraint -> Lolos Otomatis
        gate.interview_gate_status = GateStatus.passed
        gate.is_eligible_for_matching = True
        gate.interview_gate_notes = "Rotasi Satu Rumpun Grup: Gate B dilewati (Lolos Otomatis)."

def evaluate_batch(db: Session, request_id: int, employee_ids: List[int]) -> Dict[str, Any]:
    """
    Mengevaluasi dan mendaftarkan daftar karyawan ke dalam tahapan asesmen (Gates) secara massal.
    Menerapkan pencegahan N+1 Query dan transaksi atomik.
    """
    # 1. Validasi eksistensi pengajuan SDM
    sdm_request = db.query(SDMRequest).filter(SDMRequest.id == request_id).first()
    if not sdm_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="ID Pengajuan SDM tidak ditemukan di dalam sistem."
        )

    # 2. Bulk Fetch: Ambil seluruh data karyawan sekaligus (Mencegah N+1 Query)
    employees = db.query(Employee).filter(Employee.id.in_(employee_ids)).all()
    if not employees:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Daftar kandidat karyawan tidak valid atau tidak ditemukan."
        )

    # 3. Bulk Check: Ambil data gate yang sudah ada untuk pengajuan ini (Mencegah duplikasi)
    existing_gates = db.query(RotationGate).filter(
        RotationGate.sdm_request_id == request_id,
        RotationGate.employee_id.in_(employee_ids)
    ).all()
    existing_emp_ids = {gate.employee_id for gate in existing_gates}

    new_gates = []
    processed_count = 0
    skipped_duplicates = 0
    rejected_sanctions = 0

    for emp in employees:
        # Lewati jika karyawan sudah pernah didaftarkan pada pengajuan ini
        if emp.id in existing_emp_ids:
            skipped_duplicates += 1
            continue

        # Evaluasi Gate A: Pengecekan Sanksi Aktif
        # Jika karyawan memiliki sanksi, kita catat kegagalannya atau lewati sesuai aturan bisnis
        if getattr(emp, "has_sanction", False):
            rejected_sanctions += 1
            # Catatan: Jika aturan bisnismu tetap ingin menyimpan data yang gagal Gate A ke DB
            # dengan status 'rejected', kamu bisa mengubah logika di sini.
            continue

        # Evaluasi Gate A: Logika penentuan status awal (Sesuaikan dengan aturan sistemmu)
        # Contoh: Jika rumpun ilmunya berbeda, wajib masuk wawancara (Gate B)
        is_same_division = (emp.division_id == sdm_request.target_division_id)
        
        gate_a_status = "passed"
        gate_b_status = "pending" if not is_same_division else "waived"

        # Pembuatan objek baris database baru
        new_gate = RotationGate(
            sdm_request_id=request_id,
            employee_id=emp.id,
            gate_a_status=gate_a_status,
            gate_b_status=gate_b_status,
            # Tambahkan atribut lain jika tabel RotationGate kamu memilikinya (misal: education_gate_status)
        )
        new_gates.append(new_gate)
        processed_count += 1

    # 4. Bulk Insert & Single Commit (Atomic Transaction)
    if new_gates:
        db.add_all(new_gates)
        db.commit()

    return {
        "status": "success",
        "message": f"Berhasil mendaftarkan {processed_count} kandidat ke dalam tahapan asesmen.",
        "details": {
            "total_requested": len(employee_ids),
            "processed_successfully": processed_count,
            "skipped_duplicates": skipped_duplicates,
            "rejected_due_to_sanctions": rejected_sanctions
        }
    }


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
    Mengonversi skor mentah (0–100), memvalidasi kesesuaian kriteria dengan 
    divisi target, dan menyuntikkannya ke tabel EmployeeScore.
    """
    gate = _get_gate_or_404(db, gate_id) 
    employee = gate.employee 
    target_div_id = gate.sdm_request.target_division_id 

    if gate.interview_gate_status != GateStatus.interview_pending: 
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Status Gate saat ini adalah '{gate.interview_gate_status}', diharapkan 'interview_pending'." 
        )

    # 1. VALIDASI KETAT: Ambil daftar ID Kriteria sah dari divisi target
    valid_target_criteria = db.query(DivisionCriteriaWeight.group_criteria_id).filter(
        DivisionCriteriaWeight.division_id == target_div_id
    ).all()
    valid_ids = {item[0] for item in valid_target_criteria}

    submitted_ids = {s["criteria_id"] for s in scores} 
    
    # Mencegah masuknya ID Kriteria asing (misal dari divisi asal karyawan)
    invalid_ids = submitted_ids - valid_ids
    if invalid_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Inkonsistensi data: Kriteria ID {sorted(invalid_ids)} bukan parameter penilai pada divisi target."
        )

    # Pastikan seluruh kriteria wajib milik divisi target dinilai lengkap
    missing_ids = valid_ids - submitted_ids
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Penilaian tidak lengkap. Kriteria target ID {sorted(missing_ids)} belum diberikan skor."
        )

    # 2. EKSEKUSI KONVERSI & UPSERT SKOR
    results = [] 
    for entry in scores: 
        cid = entry["criteria_id"] 
        raw = entry["raw_score"] 

        try:
            converted = convert_interview_score(raw) 
        except ValueError as e: 
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) 

        # Upsert: Timpa nilai lama jika ada, buat baru jika belum
        existing_es = (
            db.query(EmployeeScore)
            .filter(EmployeeScore.employee_id == employee.id, EmployeeScore.criteria_id == cid)
            .first()
        ) 
        
        if existing_es: 
            existing_es.score = converted 
        else: 
            db.add(EmployeeScore(employee_id=employee.id, criteria_id=cid, score=converted)) 
            
        results.append({ 
            "criteria_id": cid, 
            "raw_score": raw, 
            "score": converted 
        }) 

    # 3. TRANSISI STATUS GATE
    gate.interview_gate_status = GateStatus.interview_passed 
    gate.interview_checked_at = datetime.now(timezone.utc) 
    gate.interview_gate_notes = f"Asesmen lintas fungsi selesai dirating oleh {scored_by.full_name}."
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
