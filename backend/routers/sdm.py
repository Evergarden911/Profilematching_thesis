from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, status, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import extract
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import get_current_user, require_role
from backend.models import User, SDMRequest, RequestStatus, MatchingResult, TransferLetter
from backend.schemas.sdm import (
    MatchingResultRead,
    SDMRequestCreate,
    SDMRequestRead,
    SDMRequestUpdate,
    TransferLetterCreate,
    TransferLetterRead,
)
from backend.services import sdm_service, wla_service

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

@router.post("/requests/{request_id}/approve-package")
def approve_rotation_package(
    request_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(require_role("kepala_hrd", "kepala_cabang", "eksekutif", "manajer_hrd"))[cite: 25]
):
    """
    Mengesahkan rotasi secara paket berdasar kuota (quantity) yang diminta.[cite: 25]
    Mengambil peringkat Top-N dari tabel MatchingResult, memindahkan divisi mereka,[cite: 25]
    dan secara otomatis memperbarui Workload Analysis (WLA) divisi terkait.
    """
    # 1. Ambil data pengajuan[cite: 25]
    req = db.query(SDMRequest).filter(SDMRequest.id == request_id).first()[cite: 25]
    if not req:[cite: 25]
        raise HTTPException(status_code=404, detail="Pengajuan SDM tidak ditemukan.")[cite: 25]

    # 2. Ambil kandidat peringkat 1 sampai N (Sesuai kuantitas diminta)[cite: 25]
    top_candidates = (
        db.query(MatchingResult)[cite: 25]
        .filter(MatchingResult.sdm_request_id == request_id)[cite: 25]
        .order_by(MatchingResult.rank.asc())[cite: 25]
        .limit(req.quantity)  # Memotong daftar otomatis berdasar kuota permintaan[cite: 25]
        .all()[cite: 25]
    )

    if not top_candidates:[cite: 25]
        raise HTTPException(
            status_code=400, [cite: 25]
            detail="Belum ada hasil kalkulasi Profile Matching untuk pengajuan ini. Silakan jalankan matching terlebih dahulu."[cite: 25]
        )

    # 3. SIAPKAN HIMPUNAN (SET) DIVISI TERDAMPAK
    # Masukkan Divisi Tujuan sejak awal
    affected_divisions = {req.target_division_id}

    # 4. Eksekusi perpindahan divisi & catat Divisi Asal
    for cand in top_candidates:[cite: 25]
        emp = cand.employee[cite: 25]
        if emp:[cite: 25]
            # Catat divisi asal karyawan sebelum dipindahkan
            if emp.division_id:
                affected_divisions.add(emp.division_id)
            
            # Eksekusi rotasi ke divisi baru
            emp.division_id = req.target_division_id[cite: 25]

    # 5. Kunci status pengajuan menjadi selesai / matched[cite: 25]
    req.status = RequestStatus.matched[cite: 25]
    req.updated_at = datetime.now()[cite: 25]
    
    db.commit()[cite: 25]

    # 6. REKALKULASI WLA DIVISI TERDAMPAK
    # Memastikan indikator beban kerja di Dashboard langsung akurat
    try:
        for div_id in affected_divisions:
            # Mengambil entri WLA terakhir untuk divisi tersebut
            latest_entry = wla_service.get_latest_wla(db, div_id)
            if latest_entry:
                # Rekalkulasi ulang dengan jumlah headcount pegawai yang baru
                wla_service.record_wla(
                    db=db,
                    division_id=div_id,
                    period=latest_entry.period,
                    total_workload_hours=latest_entry.total_workload_hours,
                    headcount=len(latest_entry.division.employees), # Hitung aktual pegawai baru
                    notes="Automated WLA recalculation post-mutation approval."
                )
    except Exception as e:
        # Prevent secondary WLA errors from failing the already committed transaction
        print(f"Warning: Automated WLA update failed: {e}")

    return {[cite: 25]
        "status": "success",[cite: 25]
        "message": f"Berhasil mengesahkan rotasi untuk {len(top_candidates)} karyawan (Top-{req.quantity}). WLA pada {len(affected_divisions)} divisi terkait telah diperbarui!"[cite: 25]
    }


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