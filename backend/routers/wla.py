from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import require_role
from backend.schemas.division import (
    RotationWLACheckRead, WLACreate, WLARead, WLASimulationRead,
)
from backend.services import wla_service

router = APIRouter(prefix="/api/wla", tags=["workload-analysis"])

@router.get("/", response_model=list[WLARead])
def list_wla(
    division_id: int | None = None,
    db: Session = Depends(get_db),
    # PERLUASAN RBAC: Menambahkan manajer_hrd, eksekutif, & super_admin agar tidak 403 Forbidden
    _=Depends(require_role("kepala_hrd", "kepala_cabang", "manajer_hrd", "eksekutif", "super_admin")),
):
    """
    Mengambil daftar riwayat Analisis Beban Kerja (WLA).
    Dapat difilter berdasarkan divisi tertentu.
    """
    return wla_service.list_wla(db, division_id=division_id)

@router.post("/", response_model=WLARead, status_code=status.HTTP_201_CREATED)
def record_wla(
    payload: WLACreate,
    db: Session = Depends(get_db),
    # Kepala Divisi diizinkan menginput data operasional divisinya
    _=Depends(require_role("kepala_hrd", "kepala_cabang", "manajer_hrd", "kepala_divisi", "super_admin")),
):
    """
    Mencatat atau memperbarui analisis beban kerja divisi bulanan.
    Memicu kalkulasi indeks WLA dan status over/understaffed secara otomatis di layer servis.
    """
    return wla_service.record_wla(
        db=db,
        division_id=payload.division_id,
        period=payload.period,
        total_workload_hours=payload.total_workload_hours,
        headcount=payload.headcount,
        notes=payload.notes,
    )

@router.get("/division/{division_id}/latest", response_model=WLARead)
def latest_wla(
    division_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_role("kepala_hrd", "kepala_cabang", "manajer_hrd", "kepala_divisi", "super_admin")),
):
    """
    Mengambil data WLA terbaru untuk divisi tertentu (berguna untuk auto-fill di form pengajuan mutasi).
    """
    entry = wla_service.get_latest_wla(db, division_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Belum ada rekam data WLA untuk divisi ID {division_id}."
        )
    return entry

@router.get("/simulate", response_model=RotationWLACheckRead)
def simulate_rotation(
    source_division_id: int,
    target_division_id: int,
    period: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("kepala_hrd", "kepala_cabang", "manajer_hrd", "eksekutif", "super_admin")),
):
    """
    Mensimulasikan dampak perpindahan staf terhadap rasio WLA divisi asal dan divisi tujuan sebelum SK diterbitkan.
    """
    return wla_service.simulate_rotation(db, source_division_id, target_division_id, period)

# =====================================================================
# PENAMBAHAN ENDPOINT BARU: DELETE (Penyebab utama error CRUD di UI)
# =====================================================================
@router.delete("/{wla_id}", status_code=status.HTTP_200_OK)
def delete_wla(
    wla_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_role("kepala_hrd", "manajer_hrd", "super_admin")),
):
    """
    Menghapus rekam historis WLA berdasarkan ID.
    Hanya dapat dilakukan oleh HRD dan Super Admin.
    """
    success = wla_service.delete_wla(db, wla_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Data WLA dengan ID {wla_id} tidak ditemukan."
        )
    return {"status": "success", "message": f"Rekam WLA ID {wla_id} berhasil dihapus dari sistem."}