"""
WLA Service — Workload Analysis
================================
Implements the Workload Analysis formula used by Pramita Lab:

  WLA = Total Workload Hours / Total Capacity Hours

Normal band: 1.000 – 1.500
  < 1.000 → overstaffed  (division can afford to lose someone)
  > 1.500 → understaffed (division urgently needs more staff)

Key operations:
  1. Record WLA for a division and period
  2. Simulate post-rotation WLA before approving a transfer
  3. Validate a rotation does not push either division out of safe range
  4. (NEW) Auto-Generate SOS Requests if WLA becomes strictly critical.
"""

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.models import Division, WorkloadAnalysis

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HOURS_PER_PERSON_PER_MONTH: float = 160.0  
WLA_NORMAL_MIN = 1.0
WLA_NORMAL_MAX = 1.5


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WLASimulation:
    division_id: int
    division_name: str
    current_wla: float
    projected_wla: float
    current_headcount: int
    projected_headcount: int
    is_safe: bool           
    warning: str | None     


@dataclass(frozen=True)
class RotationWLACheck:
    source: WLASimulation
    target: WLASimulation
    rotation_approved: bool  


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------


def compute_wla(total_workload_hours: float, total_capacity_hours: float) -> float:
    if total_capacity_hours <= 0:
        raise ValueError("total_capacity_hours must be positive — check headcount data.")
    return round(total_workload_hours / total_capacity_hours, 4)


def classify_wla(wla: float) -> tuple[bool, bool]:
    return wla > WLA_NORMAL_MAX, wla < WLA_NORMAL_MIN


def _wla_warning(wla: float, division_name: str, change: str) -> str | None:
    if wla > WLA_NORMAL_MAX:
        return (
            f"Kritis: {division_name} akan OVERLOAD WLA setelah {change} "
            f"(WLA={wla:.3f}, max={WLA_NORMAL_MAX})."
        )
    if wla < WLA_NORMAL_MIN:
        return (
            f"Inefisiensi: {division_name} akan KEBANYAKAN ORANG setelah {change} "
            f"(WLA={wla:.3f}, min={WLA_NORMAL_MIN})."
        )
    return None


# ---------------------------------------------------------------------------
# CRUD & PROACTIVE AUTOMATION (Flow 2)
# ---------------------------------------------------------------------------


def record_wla(
    db: Session,
    division_id: int,
    period: str,
    total_workload_hours: float,
    headcount: int,
    notes: str | None = None,
) -> WorkloadAnalysis:
    
    _assert_division_exists(db, division_id)

    total_capacity_hours = headcount * HOURS_PER_PERSON_PER_MONTH
    wla_value = compute_wla(total_workload_hours, total_capacity_hours)
    is_understaffed, is_overstaffed = classify_wla(wla_value)

    existing = (
        db.query(WorkloadAnalysis)
        .filter(WorkloadAnalysis.division_id == division_id, WorkloadAnalysis.period == period)
        .first()
    )

    if existing:
        existing.total_workload_hours = total_workload_hours
        existing.total_capacity_hours = total_capacity_hours
        existing.headcount = headcount
        existing.wla_value = wla_value
        existing.is_understaffed = is_understaffed
        existing.is_overstaffed = is_overstaffed
        existing.notes = notes
        db.commit()
        db.refresh(existing)
        entry = existing
    else:
        entry = WorkloadAnalysis(
            division_id=division_id,
            period=period,
            total_workload_hours=total_workload_hours,
            total_capacity_hours=total_capacity_hours,
            headcount=headcount,
            wla_value=wla_value,
            is_understaffed=is_understaffed,
            is_overstaffed=is_overstaffed,
            notes=notes,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        
    # FLOW 2 TRIGGER: Jika divisi overload, sistem ciptakan pengajuan mutasi otomatis
    if is_understaffed:
        _trigger_auto_sdm_request(db, division_id, wla_value)

    return entry


def _trigger_auto_sdm_request(db: Session, division_id: int, wla_value: float):
    """Fungsi internal untuk menghasilkan SDM Request secara proaktif saat WLA meledak."""
    from backend.models import SDMRequest, RequestStatus, User, UserRole
    from backend.schemas.sdm import SDMRequestCreate
    from backend.services.sdm_service import create_sdm_request
    
    # 1. Cegah SPAM: Jangan buat tiket baru jika masih ada tiket dari sistem yang sedang diproses
    existing_req = db.query(SDMRequest).filter(
        SDMRequest.target_division_id == division_id,
        SDMRequest.status.in_([RequestStatus.pending, RequestStatus.forwarded, RequestStatus.under_review]),
        SDMRequest.is_auto_generated == True
    ).first()
    
    if existing_req:
        return
        
    # 2. Cari entitas HRD sebagai "Pelaku" (Requester) dari sistem ini
    system_user = db.query(User).filter(User.role == UserRole.kepala_hrd).first()
    if not system_user:
        return # Fallback jika tidak ada admin
        
    payload = SDMRequestCreate(
        target_division_id=division_id,
        quantity=1,
        reason=f"[AUTO-GENERATED] Peringatan Sistem: Workload Analysis divisi melampaui batas kritis (WLA = {wla_value:.3f}). Dibutuhkan tambahan SDM segera untuk mencegah kegagalan operasional.",
        is_auto_generated=True
    )
    
    try:
        # Panggil service utama. Validasi Gate 1 (Anggaran) akan otomatis berjalan.
        create_sdm_request(db, payload, system_user)
    except Exception:
        # Redam kegagalan trigger auto-gen agar tidak mengganggu transaksi pencatatan WLA
        pass


def get_latest_wla(db: Session, division_id: int) -> WorkloadAnalysis | None:
    return (
        db.query(WorkloadAnalysis)
        .filter(WorkloadAnalysis.division_id == division_id)
        .order_by(WorkloadAnalysis.period.desc())
        .first()
    )


def list_wla(db: Session, division_id: int | None = None) -> list[WorkloadAnalysis]:
    q = db.query(WorkloadAnalysis)
    if division_id:
        q = q.filter(WorkloadAnalysis.division_id == division_id)
    return q.order_by(WorkloadAnalysis.period.desc()).all()


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------


def simulate_rotation(
    db: Session,
    source_division_id: int,
    target_division_id: int,
    period: str,
) -> RotationWLACheck:
    
    source_div = _get_division_or_404(db, source_division_id)
    target_div = _get_division_or_404(db, target_division_id)

    source_wla_entry = get_latest_wla(db, source_division_id)
    target_wla_entry = get_latest_wla(db, target_division_id)

    if not source_wla_entry:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"WLA Divisi Asal '{source_div.name}' kosong.",
        )
    if not target_wla_entry:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"WLA Divisi Target '{target_div.name}' kosong.",
        )

    projected_source_headcount = source_wla_entry.headcount - 1
    if projected_source_headcount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Tidak bisa ditarik dari '{source_div.name}' — jumlah orang akan habis.",
        )
    projected_source_capacity = projected_source_headcount * HOURS_PER_PERSON_PER_MONTH
    projected_source_wla = compute_wla(source_wla_entry.total_workload_hours, projected_source_capacity)
    source_warning = _wla_warning(projected_source_wla, source_div.name, "ditarik")

    projected_target_headcount = target_wla_entry.headcount + 1
    projected_target_capacity = projected_target_headcount * HOURS_PER_PERSON_PER_MONTH
    projected_target_wla = compute_wla(target_wla_entry.total_workload_hours, projected_target_capacity)
    target_warning = _wla_warning(projected_target_wla, target_div.name, "ditambah")

    source_sim = WLASimulation(
        division_id=source_division_id,
        division_name=source_div.name,
        current_wla=source_wla_entry.wla_value,
        projected_wla=projected_source_wla,
        current_headcount=source_wla_entry.headcount,
        projected_headcount=projected_source_headcount,
        is_safe=source_warning is None,
        warning=source_warning,
    )

    target_sim = WLASimulation(
        division_id=target_division_id,
        division_name=target_div.name,
        current_wla=target_wla_entry.wla_value,
        projected_wla=projected_target_wla,
        current_headcount=target_wla_entry.headcount,
        projected_headcount=projected_target_headcount,
        is_safe=target_warning is None,
        warning=target_warning,
    )

    return RotationWLACheck(
        source=source_sim,
        target=target_sim,
        rotation_approved=source_sim.is_safe and target_sim.is_safe,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_division_exists(db: Session, division_id: int) -> None:
    if not db.query(Division).filter(Division.id == division_id).first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Division {division_id} not found.",
        )


def _get_division_or_404(db: Session, division_id: int) -> Division:
    div = db.query(Division).filter(Division.id == division_id).first()
    if not div:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Division {division_id} not found.",
        )
    return div