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
    _=Depends(require_role("kepala_hrd", "kepala_cabang")),
):
    return wla_service.list_wla(db, division_id=division_id)

@router.post("/", response_model=WLARead, status_code=status.HTTP_201_CREATED)
def record_wla(
    payload: WLACreate,
    db: Session = Depends(get_db),
    _=Depends(require_role("kepala_hrd", "kepala_cabang", "kepala_divisi")),
):
    # Parameter diekstrak eksplisit untuk memastikan pemicu pengajuan otomatis berjalan presisi
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
    _=Depends(require_role("kepala_hrd", "kepala_cabang", "kepala_divisi")),
):
    entry = wla_service.get_latest_wla(db, division_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"No WLA data found for division {division_id}.")
    return entry

@router.get("/simulate", response_model=RotationWLACheckRead)
def simulate_rotation(
    source_division_id: int,
    target_division_id: int,
    period: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("kepala_hrd", "kepala_cabang")),
):
    return wla_service.simulate_rotation(db, source_division_id, target_division_id, period)