from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, status, Query, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import extract
from sqlalchemy.orm import Session, contains_eager

from backend.core.database import get_db
from backend.core.security import get_current_user, require_role
from backend.models import User, SDMRequest, RequestStatus, MatchingResult, TransferLetter, SDMEvaluationHistory, Employee, Division
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

ROMAN_MONTHS = {
    1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI",
    7: "VII", 8: "VIII", 9: "IX", 10: "X", 11: "XI", 12: "XII"
}

# Skema Pydantic khusus penambalan BUG-21
class SDMRequestStatusPatch(BaseModel):
    status: RequestStatus

class RequestStatusUpdate(BaseModel):
    status: RequestStatus
    hrd_notes: Optional[str] = None

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
    # kepala_hrd diizinkan mengajukan closed-loop request dari WLA (sinkron dengan main.py can_request_sdm)
    current_user: User = Depends(require_role("kepala_divisi", "kepala_hrd", "super_admin")),
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
    current_user: User = Depends(require_role("kepala_hrd", "kepala_cabang", "eksekutif", "manajer_hrd"))
):
    """
    Mengesahkan rotasi secara paket berdasar kuota (quantity) yang diminta.
    Mengambil peringkat Top-N dari tabel MatchingResult, memindahkan divisi mereka,
    dan secara otomatis memperbarui Workload Analysis (WLA) divisi terkait.
    """
    # 1. Ambil data pengajuan
    req = db.query(SDMRequest).filter(SDMRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Pengajuan SDM tidak ditemukan.")

    # 2. Ambil kandidat peringkat 1 sampai N (Sesuai kuantitas diminta)
    top_candidates = (
        db.query(MatchingResult)
        .filter(MatchingResult.sdm_request_id == request_id)
        .order_by(MatchingResult.rank.asc())
        .limit(req.quantity)  # Memotong daftar otomatis berdasar kuota permintaan
        .all()
    )

    if not top_candidates:
        raise HTTPException(
            status_code=400, 
            detail="Belum ada hasil kalkulasi Profile Matching untuk pengajuan ini. Silakan jalankan matching terlebih dahulu."
        )

    # 3. SIAPKAN HIMPUNAN (SET) DIVISI TERDAMPAK
    # Masukkan Divisi Tujuan sejak awal
    affected_divisions = {req.target_division_id}

    # 4. Eksekusi perpindahan divisi & catat Divisi Asal
    for cand in top_candidates:
        emp = cand.employee
        if emp:
            # Catat divisi asal karyawan sebelum dipindahkan
            if emp.division_id:
                affected_divisions.add(emp.division_id)
            
            # Eksekusi rotasi ke divisi baru
            emp.division_id = req.target_division_id

    # 5. Kunci status pengajuan menjadi selesai / matched
    req.status = RequestStatus.matched
    req.updated_at = datetime.now()
    
    db.commit()

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

    return {
        "status": "success",
        "message": f"Berhasil mengesahkan rotasi untuk {len(top_candidates)} karyawan (Top-{req.quantity}). WLA pada {len(affected_divisions)} divisi terkait telah diperbarui!"
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

@router.patch("/requests/{request_id}/status", status_code=status.HTTP_200_OK)
def update_request_status(
    request_id: int,
    payload: RequestStatusUpdate,
    db: Session = Depends(get_db),
    # PENTING: Izinkan Kepala Cabang, Eksekutif, dan HRD untuk mengubah status
    current_user = Depends(require_role("kepala_hrd", "manajer_hrd", "kepala_cabang", "eksekutif", "super_admin"))
):
    """
    Memperbarui status pengajuan SDM (Digunakan untuk Sahkan SK dan Minta Revisi).
    """
    sdm_req = db.query(SDMRequest).filter(SDMRequest.id == request_id).first()
    if not sdm_req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Pengajuan dengan ID {request_id} tidak ditemukan."
        )

    old_status = sdm_req.status.value
    new_status_val = payload.status.value

    # Update atribut pengajuan
    sdm_req.status = payload.status
    if payload.hrd_notes:
        sdm_req.hrd_notes = payload.hrd_notes

    # Catat ke Audit Trail (SDMEvaluationHistory) agar terekam di riwayat
    history_entry = SDMEvaluationHistory(
        gate_id=request_id, # Atau hubungkan ke ID gate jika skemamu mensyaratkan
        from_status=old_status,
        to_status=new_status_val,
        actor_id=current_user.id,
        reason=payload.hrd_notes or f"Status diubah menjadi {new_status_val}",
        is_manual=True
    )
    db.add(history_entry)

    try:
        db.commit()
        db.refresh(sdm_req)
        return {
            "status": "success",
            "message": f"Status pengajuan berhasil diperbarui dari '{old_status}' menjadi '{new_status_val}'.",
            "data": {
                "id": sdm_req.id,
                "current_status": sdm_req.status.value
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal memperbarui status ke database: {str(e)}"
        )

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

@router.get("/requests/{request_id}/print-sk", response_class=HTMLResponse)
async def print_surat_tugas(
    request_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    # 1. Tarik Data Pengajuan
    sdm_req = db.query(SDMRequest).filter(SDMRequest.id == request_id).first()
    if not sdm_req:
        raise HTTPException(status_code=404, detail="Data pengajuan tidak ditemukan.")

    # 2. Tarik Kandidat Terpilih (Top-N Sesuai Kuota)
    top_results = (
        db.query(MatchingResult)
        .filter(MatchingResult.sdm_request_id == request_id)
        .options(contains_eager(MatchingResult.employee).contains_eager(Employee.division))
        .join(Employee)
        .join(Division)
        .order_by(MatchingResult.rank.asc())
        .limit(sdm_req.quantity)
        .all()
    )

    if not top_results:
        raise HTTPException(
            status_code=400, 
            detail="Belum ada kandidat yang dikalkulasi untuk pengajuan ini."
        )

    # 3. Rakit Data Dokumen per Karyawan
    now = datetime.now()
    roman_month = ROMAN_MONTHS.get(now.month, "VII")
    letter_year = now.year
    
    surat_list = []
    for index, res in enumerate(top_results, start=1):
        emp = res.employee
        # Penomoran surat berurutan, misal: 54A/Cab-1/P.18/VII/2026
        nomor_surat = f"{sdm_req.id:03d}{chr(64+index)}/Cab-1/P.18/{roman_month}/{letter_year}"
        
        surat_list.append({
            "nomor_surat": nomor_surat,
            "nama": emp.full_name,
            "nip": emp.employee_code,
            "bagian_asal": emp.division.name if emp.division else "Internal",
            "jabatan_asal": emp.position,
            "status_pegawai": "Pegawai Tetap", # Bisa ditarik dari kolom DB jika ada
            "divisi_tujuan": sdm_req.target_division.name,
            "tanggal_mulai": now.strftime("%d %B %Y"),
            "tanggal_selesai": (now.replace(year=now.year + 1)).strftime("%d %B %Y")
        })

    # 4. Ambil Jinja2 Templates dari konfigurasi aplikasi
    from backend.main import templates
    return templates.TemplateResponse("surat_tugas.html", {
        "request": request,
        "surat_list": surat_list,
        "tanggal_cetak": now.strftime("%d %B %Y"),
        "kota_cabang": "Bandung", # Atau disesuaikan dengan cabang aktif
        "pimpinan": "Yono Harsono",
        "jabatan_pimpinan": "Kepala Cabang"
    })