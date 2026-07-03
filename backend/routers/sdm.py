from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, status, Query, HTTPException
from pydantic import BaseModel
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

# Skema Pydantic khusus penambalan BUG-21
class SDMRequestStatusPatch(BaseModel):
    status: RequestStatus


# ---------------------------------------------------------------------------
# STATISTIK DASHBOARD
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


# ---------------------------------------------------------------------------
# Eksekusi Profile Matching & Simulasi Gate
# ---------------------------------------------------------------------------
# FIXED ISSUE-01: Memperluas perimeter hak akses ke kepala_hrd dan kepala_cabang
@router.post("/requests/{request_id}/run-matching", response_model=list[MatchingResultRead], status_code=status.HTTP_201_CREATED)
def run_matching(
    request_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("kepala_hrd", "kepala_cabang")),
):
    return sdm_service.run_matching(db, request_id)


@router.get("/requests/{request_id}/results", response_model=list[MatchingResultRead])
def get_results(
    request_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return sdm_service.get_matching_results(db, request_id)


# FIXED BUG-21: Menggunakan skema Pydantic SDMRequestStatusPatch demi keamanan tipe data
@router.patch("/requests/{request_id}/status")
def update_request_status(
    request_id: int,
    payload: SDMRequestStatusPatch,
    db: Session = Depends(get_db),
    _=Depends(require_role("kepala_hrd", "kepala_cabang"))
):
    """Digunakan oleh HRD untuk menyetujui atau menolak tiket pengajuan."""
    req = db.query(SDMRequest).filter(SDMRequest.id == request_id).first()
    if not req: 
        raise HTTPException(status_code=404, detail="Pengajuan tidak ditemukan")
    
    req.status = payload.status
    db.commit()
    return {"message": f"Status pengajuan berhasil diperbarui menjadi '{payload.status.value}'."}


# FIXED BUG-11 & Rute Ganda: Disatukan menjadi satu rute kanonikal di urutan PALING BAWAH
@router.get("/requests/{request_id}")
def get_canonical_request_detail(
    request_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_role("kepala_hrd", "kepala_cabang", "kepala_divisi"))
):
    """
    Menyuplai dictionary lengkap (termasuk properti ORM dan custom target_division_name)
    agar kompatibel dengan seluruh pemanggilan modal JS di frontend.
    """
    request_data = db.query(SDMRequest).filter(SDMRequest.id == request_id).first()
    
    if not request_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permintaan SDM dengan ID {request_id} tidak ditemukan dalam sistem."
        )
        
    return {
        "id": request_data.id,
        "target_division_id": request_data.target_division_id,
        "target_division_name": request_data.target_division.name if request_data.target_division else "Tidak Diketahui",
        "quantity": request_data.quantity,
        "reason": request_data.reason,
        "status": request_data.status.value,
        "created_at": request_data.created_at
    }


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