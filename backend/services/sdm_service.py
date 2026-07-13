from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, contains_eager

from backend.models import (
    GroupCriteria,
    DivisionCriteriaWeight,
    Division,
    Employee,
    EmployeeScore,
    MatchingResult,
    RequestStatus,
    SDMRequest,
    TransferLetter,
    User,
    UserRole,
    GateStatus,
    RotationGate
)
from backend.schemas.sdm import SDMRequestCreate, TransferLetterCreate
from backend.services.profile_matching import CriteriaInput, compute_match, rank_employees


# ---------------------------------------------------------------------------
# SDM Request CRUD (Injeksi Gate 1 - Biaya)
# ---------------------------------------------------------------------------


def create_sdm_request(db: Session, payload: SDMRequestCreate, requester: User) -> SDMRequest:
    target_div = db.query(Division).filter(Division.id == payload.target_division_id).first()
    if not target_div:
        raise HTTPException(status_code=404, detail="Divisi target tidak ditemukan.")

    # -----------------------------------------------------------------------
    # GATE 1: DINONAKTIFKAN (Intentional Auto-Pass)
    # Constraint finansial (base_salary/monthly_budget) sengaja di luar
    # cakupan skripsi. Fokus riset adalah Profile Matching pada kriteria
    # kompetensi karyawan (CF/SF), bukan constraint anggaran. Kolom biaya
    # tetap dipertahankan di skema DB untuk kompatibilitas seeder dan
    # kemungkinan pengembangan lanjutan, tapi sudah tidak lagi memengaruhi
    # keputusan alur SDM Request.
    # -----------------------------------------------------------------------
    request = SDMRequest(
        requester_id=requester.id,
        target_division_id=payload.target_division_id,
        quantity=payload.quantity,
        reason=payload.reason,
        status=RequestStatus.pending,
        budget_gate_status=GateStatus.passed,
        budget_notes="Gate anggaran dinonaktifkan.",
        is_auto_generated=payload.is_auto_generated
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def list_sdm_requests(db: Session, requester: User) -> list[SDMRequest]:
    q = db.query(SDMRequest)
    if requester.role == UserRole.kepala_divisi:
        q = q.filter(SDMRequest.requester_id == requester.id)
    elif requester.role == UserRole.kepala_cabang:
        q = q.filter(
            SDMRequest.status.in_(
                [RequestStatus.forwarded, RequestStatus.under_review, RequestStatus.matched]
            )
        )
    return q.order_by(SDMRequest.created_at.desc()).all()


def get_sdm_request_or_404(db: Session, request_id: int) -> SDMRequest:
    request = db.query(SDMRequest).filter(SDMRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SDM Request not found")
    return request


def hrd_forward_request(db: Session, request_id: int, hrd_notes: str | None) -> SDMRequest:
    request = get_sdm_request_or_404(db, request_id)
    if request.status != RequestStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request is in status '{request.status}', expected 'pending'.",
        )
    request.status = RequestStatus.forwarded
    request.hrd_notes = hrd_notes
    db.commit()
    db.refresh(request)
    return request


def hrd_reject_request(db: Session, request_id: int, hrd_notes: str) -> SDMRequest:
    request = get_sdm_request_or_404(db, request_id)
    if request.status != RequestStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request is in status '{request.status}', expected 'pending'.",
        )
    request.status = RequestStatus.rejected
    request.hrd_notes = hrd_notes
    db.commit()
    db.refresh(request)
    return request


# ---------------------------------------------------------------------------
# Profile Matching Execution (Injeksi Gate 2 - Simulasi WLA)
# ---------------------------------------------------------------------------


def run_matching(db: Session, request_id: int) -> list[MatchingResult]:
    sdm_request = get_sdm_request_or_404(db, request_id)

    if sdm_request.status not in (RequestStatus.forwarded, RequestStatus.under_review):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Matching tidak bisa dieksekusi pada status '{sdm_request.status}'.",
        )

    division_id = sdm_request.target_division_id

    # 1. PENGAMBILAN BOBOT DINAMIS SPESIFIK SUB-DIVISI
    division_weights = (
        db.query(DivisionCriteriaWeight)
        .join(GroupCriteria)
        .filter(
            DivisionCriteriaWeight.division_id == division_id,
            GroupCriteria.is_active == True
        )
        .options(contains_eager(DivisionCriteriaWeight.group_criteria))
        .all()
    )

    if not division_weights:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sub-divisi ini belum memiliki konfigurasi bobot kriteria. HRD harus menetapkan bobot 100% terlebih dahulu.",
        )

    valid_group_criteria_ids = [dw.group_criteria_id for dw in division_weights]

    # 2. PENGAMBILAN KANDIDAT YANG LOLOS GERBANG
    employees: list[Employee] = (
        db.query(Employee)
        .join(RotationGate, RotationGate.employee_id == Employee.id)
        .join(EmployeeScore, EmployeeScore.employee_id == Employee.id)
        .filter(
            Employee.is_active == True,
            Employee.has_sanction == False,
            RotationGate.sdm_request_id == request_id,
            RotationGate.is_eligible_for_matching == True,
            EmployeeScore.criteria_id.in_(valid_group_criteria_ids),
        )
        .options(contains_eager(Employee.scores))
        .all()
    )

    seen: set[int] = set()
    unique_employees: list[Employee] = []
    for emp in employees:
        if emp.id not in seen:
            seen.add(emp.id)
            unique_employees.append(emp)
    employees = unique_employees

    # -----------------------------------------------------------------------
    # DIAGNOSTIK: Kandidat yang terdaftar di RotationGate untuk request ini,
    # tapi TIDAK ikut proses matching di atas. Ini membedakan dua kondisi
    # yang secara query terlihat sama (hilang dari hasil) tapi maknanya beda:
    #   - masih interview_pending  -> belum dinilai, BUKAN ditolak, tinggal
    #     lengkapi Gate B (input nilai wawancara)
    #   - interview_failed / gagal Gate A -> memang tidak eligible
    # Tanpa ini, satu-satunya sinyal ke HRD adalah pesan generik "tidak ada
    # karyawan" yang terbaca seperti penolakan total, padahal bisa jadi
    # kandidat itu tinggal 1 langkah lagi (input nilai) sebelum eligible.
    # -----------------------------------------------------------------------
    all_gates_for_request = (
        db.query(RotationGate)
        .join(Employee)
        .filter(RotationGate.sdm_request_id == request_id)
        .options(contains_eager(RotationGate.employee))
        .all()
    )
    matched_employee_ids = {emp.id for emp in employees}
    pending_interview_candidates = [
        g.employee.full_name
        for g in all_gates_for_request
        if g.employee_id not in matched_employee_ids
        and g.interview_gate_status == GateStatus.interview_pending
    ]

    score_index: dict[int, dict[int, float]] = {}
    for emp in employees:
        score_index[emp.id] = {s.criteria_id: s.score for s in emp.scores}

    match_results = []
    
    # 3. PENYUSUNAN PARAMETER & KOMPUTASI ALGORITMA (Dipindah ke atas!)
    for emp in employees:
        emp_scores = score_index.get(emp.id, {})
        
        inputs = []
        for dw in division_weights:
            gc = dw.group_criteria
            actual_score = emp_scores.get(gc.id, 0.0) 
            
            inputs.append(
                CriteriaInput(
                    criteria_id=gc.id,
                    employee_score=actual_score,
                    target_value=gc.target_value,
                    weight=dw.weight,
                    factor_type=gc.factor_type.value,
                )
            )
            
        match_results.append(compute_match(emp.id, inputs))

    if not match_results:
        if pending_interview_candidates:
            names = ", ".join(pending_interview_candidates)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Belum bisa matching: kandidat berikut berasal dari grup divisi berbeda "
                    f"dan masih menunggu Gate B (input nilai wawancara/asesmen): {names}. "
                    "Selesaikan penilaian lewat halaman Rotation Gates terlebih dahulu."
                ),
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tidak ada karyawan yang memiliki nilai asesmen pada kriteria sub-divisi target ini."
        )

    # 4. PERANKINGAN & PENYIMPANAN KE DATABASE
    ranked = rank_employees(match_results)
    persisted = []
    
    # FIXED: Typo 'resulit' diganti menjadi 'result'
    for rank, result in ranked:
        row = MatchingResult(
            sdm_request_id=request_id,
            employee_id=result.employee_id,
            ncf_score=result.ncf_score,
            nsf_score=result.nsf_score,
            final_score=result.final_score,
            rank=rank
        )
        db.add(row)
        persisted.append(row)
    
    # Flush agar baris MatchingResult mendapat ID sementara di Session sebelum Gate 2 membaca DB
    db.flush()

    # -----------------------------------------------------------------------
    # GATE 2: Stress-Test WLA pada 3 Kandidat Teratas (Resource Optimization)
    # -----------------------------------------------------------------------
    import backend.services.wla_service as wla_service
    current_period = datetime.now().strftime("%Y-%m")

    for rank, result in ranked[:3]:
        emp_model = db.query(Employee).get(result.employee_id)
        
        # FIXED: Tarik record RotationGate yang sudah ada, jangan pakai db.add(RotationGate(...)) baru!
        gate = db.query(RotationGate).filter(
            RotationGate.sdm_request_id == request_id, 
            RotationGate.employee_id == result.employee_id
        ).first()
        
        if not gate:
            gate = RotationGate(sdm_request_id=request_id, employee_id=result.employee_id)
            db.add(gate)
        
        try:
            wla_check = wla_service.simulate_rotation(db, emp_model.division_id, division_id, current_period)
            
            if wla_check.rotation_approved:
                # FIXED: Menyesuaikan nama kolom ORM (wla_gate_status tidak eksis, di model namanya passed/failed atau masuk ke notes)
                # Catatan: Di models.py entitas RotationGate tidak punya kolom wla_gate_status terpisah.
                # Kita simpan hasil kelulusan WLA ini ke dalam is_eligible_for_matching dan notes wawancara/edukasi atau log.
                gate.is_eligible_for_matching = True
                gate.interview_gate_notes = f"[WLA Lulus]: Rotasi aman. {gate.interview_gate_notes or ''}"
            else:
                gate.is_eligible_for_matching = False
                gate.interview_gate_notes = f"[WLA Gagal]: Divisi asal overload. {gate.interview_gate_notes or ''}"
        except Exception as e:
            gate.is_eligible_for_matching = False
            gate.interview_gate_notes = f"[WLA Error]: Simulasi gagal ({str(e)}). {gate.interview_gate_notes or ''}"

    sdm_request.status = RequestStatus.matched
    db.commit()
    
    for row in persisted:
        db.refresh(row)

    return persisted


def get_matching_results(db: Session, request_id: int) -> list[MatchingResult]:
    get_sdm_request_or_404(db, request_id)
    return (
        db.query(MatchingResult)
        .join(MatchingResult.employee)
        .filter(MatchingResult.sdm_request_id == request_id)
        .options(contains_eager(MatchingResult.employee)) # Optimasi query
        .order_by(MatchingResult.rank)
        .all()
    )


# ---------------------------------------------------------------------------
# Transfer Letter
# ---------------------------------------------------------------------------


def create_transfer_letter(
    db: Session, payload: TransferLetterCreate, issuer: User
) -> TransferLetter:
    sdm_request = get_sdm_request_or_404(db, payload.sdm_request_id)

    if sdm_request.status != RequestStatus.matched:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transfer letter can only be issued after matching is complete.",
        )

    existing = (
        db.query(TransferLetter)
        .filter(TransferLetter.sdm_request_id == payload.sdm_request_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A transfer letter has already been issued for this request.",
        )

    letter = TransferLetter(
        sdm_request_id=payload.sdm_request_id,
        issued_by_id=issuer.id,
        letter_number=payload.letter_number,
        content=payload.content,
    )
    db.add(letter)
    sdm_request.status = RequestStatus.approved
    db.commit()
    db.refresh(letter)
    return letter