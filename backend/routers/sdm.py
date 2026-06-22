from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, status, Query, HTTPException
from sqlalchemy import extract
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import get_current_user, require_role
from backend.models import User, SDMRequest, RequestStatus
from backend.schemas.sdm import (
    MatchingResultRead,
    SDMRequestCreate,
    SDMRequestRead,
    SDMRequestUpdate,
    TransferLetterCreate,
    TransferLetterRead,
)
from backend.services import sdm_service

router = APIRouter(prefix="/api/sdm", tags=["sdm"])

# ---------------------------------------------------------------------------
# STATISTIK DASHBOARD (Dipertahankan untuk kompatibilitas API JSON)
# ---------------------------------------------------------------------------
@router.get("/dashboard-stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base_query = db.query(SDMRequest)
    
    total = base_query.count()
    pending = base_query.filter(SDMRequest.status == RequestStatus.pending).count()
    completed = base_query.filter(
        SDMRequest.status.in_([RequestStatus.matched, RequestStatus.approved])
    ).count()
    
    now = datetime.now()
    this_month = base_query.filter(
        extract('year', SDMRequest.created_at) == now.year,
        extract('month', SDMRequest.created_at) == now.month
    ).count()
    
    return {
        "total_requests": total,
        "pending_requests": pending,
        "completed_requests": completed,
        "monthly_delta": this_month
    }

# ---------------------------------------------------------------------------
# SDM Requests & Siklus Hidup Approval
# ---------------------------------------------------------------------------
@router.post("/requests", response_model=SDMRequestRead, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: SDMRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("kepala_divisi")),
):
    return sdm_service.create_sdm_request(db, payload, current_user)

@router.get("/requests", response_model=list[SDMRequestRead])
def list_requests(
    limit: Optional[int] = Query(None, description="Batasi jumlah data yang dirender"),
    status_filter: Optional[str] = Query(alias="status", default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    requests = sdm_service.list_sdm_requests(db, current_user)
    
    if status_filter:
        status_map = {
            "Menunggu": RequestStatus.pending.value,
            "Diproses": RequestStatus.under_review.value,
            "Selesai": RequestStatus.matched.value
        }
        db_status = status_map.get(status_filter, status_filter)
        requests = [req for req in requests if req.status.value == db_status]
        
    if limit:
        requests = requests[:limit]
        
    return requests

@router.post("/requests/{request_id}/forward", response_model=SDMRequestRead)
def forward_request(
    request_id: int,
    payload: SDMRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("kepala_hrd")),
):
    return sdm_service.hrd_forward_request(db, request_id, payload.hrd_notes)

@router.post("/requests/{request_id}/reject", response_model=SDMRequestRead)
def reject_request(
    request_id: int,
    payload: SDMRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("kepala_hrd")),
):
    return sdm_service.hrd_reject_request(db, request_id, payload.hrd_notes or "Ditolak sistem")

@router.get("/{request_id}")
def get_request_detail(
    request_id: int,
    db: Session = Depends(get_db),
    # Memastikan hanya peran yang sah yang bisa melihat detail
    _=Depends(require_role("kepala_hrd", "kepala_cabang", "kepala_divisi"))
):
    """Menarik satu data pengajuan spesifik untuk ditampilkan di Modal UI."""
    request_data = db.query(SDMRequest).filter(SDMRequest.id == request_id).first()
    
    if not request_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Data pengajuan dengan ID {request_id} tidak ditemukan."
        )
        
    return request_data

# ---------------------------------------------------------------------------
# Eksekusi Profile Matching & Simulasi Gate
# ---------------------------------------------------------------------------
@router.post("/requests/{request_id}/run-matching", response_model=list[MatchingResultRead], status_code=status.HTTP_201_CREATED)
def run_matching(
    request_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("kepala_hrd")),
):
    return sdm_service.run_matching(db, request_id)

@router.get("/requests/{request_id}/results", response_model=list[MatchingResultRead])
def get_results(
    request_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return sdm_service.get_matching_results(db, request_id)

# Hapus response_model dari dalam kurung @router.get agar lebih fleksibel
@router.get("/requests/{request_id}")
def get_single_request_detail(
    request_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_role("kepala_hrd", "kepala_cabang", "kepala_divisi"))
):
    """
    Menyuplai data JSON murni untuk satu pengajuan spesifik berdasarkan ID.
    """
    request_data = db.query(SDMRequest).filter(SDMRequest.id == request_id).first()
    
    if not request_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permintaan SDM dengan ID {request_id} tidak ditemukan dalam sistem."
        )
        
    # Mengonversi objek ke dalam kamus (dictionary) kustom agar relasi nama divisi ikut terkirim
    return {
        "id": request_data.id,
        "target_division_id": request_data.target_division_id,
        "target_division_name": request_data.target_division.name if request_data.target_division else "Tidak Diketahui",
        "quantity": request_data.quantity,
        "reason": request_data.reason
    }
    
@router.patch("/requests/{request_id}/status")
def update_request_status(
    request_id: int,
    payload: dict, # Menerima JSON seperti {"status": "under_review"}
    db: Session = Depends(get_db),
    _=Depends(require_role("kepala_hrd"))
):
    """Digunakan oleh HRD untuk menyetujui atau menolak tiket pengajuan."""
    req = db.query(SDMRequest).filter(SDMRequest.id == request_id).first()
    if not req: 
        raise HTTPException(status_code=404, detail="Pengajuan tidak ditemukan")
    
    req.status = payload.get("status")
    db.commit()
    return {"message": "Status pengajuan berhasil diperbarui."}

# ---------------------------------------------------------------------------
# Eksekusi Surat Tugas
# ---------------------------------------------------------------------------
@router.post("/transfer-letters", response_model=TransferLetterRead, status_code=status.HTTP_201_CREATED)
def issue_transfer_letter(
    payload: TransferLetterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("kepala_cabang")),
):
    return sdm_service.create_transfer_letter(db, payload, current_user)