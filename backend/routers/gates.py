from fastapi import APIRouter, Depends, status, HTTPException 
from sqlalchemy.orm import Session 

from backend.core.database import get_db 
from backend.core.security import get_current_user, require_role 
from backend.models import User, RequestStatus 
from backend.schemas.division import (
    GateEvaluateRequest, 
    GateFailRequest, 
    InterviewScoreRead, 
    InterviewScoreSubmit, 
    RotationGateRead, 
)
from backend.services import constraint_service, sdm_service 
from backend.schemas.constraint import BatchEvaluateCreate  # <--- Skema dari langkah 1
from backend.services import constraint_service

router = APIRouter(prefix="/api/gates", tags=["rotation-gates"]) 


@router.post(
    "/evaluate-initial",
    response_model=RotationGateRead,
    status_code=status.HTTP_201_CREATED,
)
def evaluate_initial_gate(
    payload: GateEvaluateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("kepala_hrd")),
):
    """
    Gate A: Filtrasi Tahap Pertama (Pendidikan & Sanksi SP).
    
    Sistem mengekstrak data karyawan untuk memvalidasi:
      1. Kebijakan Sanksi: Jika karyawan memiliki status SP aktif, otomatis GAGAL.
      2. Kesesuaian Jurusan: Memeriksa apakah ijazah diizinkan di divisi target.
      3. Korelasi Keilmuan: Jika jurusan cocok tapi fungsi asal melompat jauh 
         (contoh: CS ke LAB), sistem memaksa status ke 'interview_pending'.
    """
    return constraint_service.evaluate_education_gate(db, payload.sdm_request_id, payload.employee_id)


@router.post(
    "/interview-scores",
    response_model=list[InterviewScoreRead],
    status_code=status.HTTP_201_CREATED,
)
def submit_interview_scores(
    payload: InterviewScoreSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("kepala_hrd")),
):
    """
    Gate B: Input Kompetensi Lintas Fungsi (Halaman Terpisah HRD).
    
    Digunakan khusus untuk kasus tidak ada korelasi keilmuan langsung.
    Nilai asesmen kompetensi diinput oleh HRD, dikonversi ke skala 1-5,
    dan setelah disimpan, status diubah agar kandidat bisa diteruskan ke 
    proses algoritma Profile Matching.
    """
    return constraint_service.record_interview_scores(
        db=db, 
        gate_id=payload.gate_id, 
        scores=[{"criteria_id": s.criteria_id, "raw_score": s.raw_score} for s in payload.scores], 
        scored_by=current_user
    )


@router.post("/fail-interview", response_model=RotationGateRead)
def fail_interview_gate(
    payload: GateFailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("kepala_hrd", "kepala_cabang")),
):
    """Menggagalkan kandidat secara manual pada tahap asesmen kompetensi."""
    return constraint_service.fail_interview_gate(db, payload.gate_id, payload.notes)

@router.get(
    "/{gate_id}/assessment-criteria",
    status_code=status.HTTP_200_OK,
)
def get_criteria_for_gate_assessment(
    gate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("kepala_hrd")),
):
    """
    API untuk Frontend: Mengambil daftar kriteria dan bobot yang sah dari divisi 
    tujuan sebelum memunculkan modal penilaian Gate B kepada HRD.
    """
    return constraint_service.get_target_assessment_criteria(db, gate_id)

@router.post("/evaluate-batch", status_code=status.HTTP_201_CREATED)
def evaluate_batch_candidates(
    payload: BatchEvaluateCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_role("kepala_hrd", "manajer_hrd"))
):
    """
    Endpoint untuk mendaftarkan dan mengevaluasi kandidat rotasi secara massal (Batch Selection).
    Hanya dapat diakses oleh Kepala HRD dan Manajer HRD.
    """
    return constraint_service.evaluate_batch(
        db=db,
        request_id=payload.sdm_request_id,
        employee_ids=payload.employee_ids
    )