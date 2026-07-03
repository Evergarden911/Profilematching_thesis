"""
Criteria Router (Refactored)
============================
Fokus pada penyajian data kriteria yang telah dikalkulasi dengan bobot 
spesifik sub-divisi. Pembuatan dan modifikasi kriteria sekarang dikelola 
sepenuhnya melalui domain `divisions.py` untuk menjaga integritas hierarki.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, contains_eager

from backend.core.database import get_db
from backend.core.security import require_role
from backend.models import Division, DivisionCriteriaWeight, GroupCriteria

router = APIRouter(prefix="/api/criteria", tags=["criteria"])

@router.get("/")
@router.get("/division/{division_id}")
def get_criteria_for_division(
    division_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: object = Depends(require_role("kepala_hrd", "kepala_cabang", "kepala_divisi")),
):
    if not division_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Parameter 'division_id' wajib disertakan."
        )

    div = db.query(Division).filter(Division.id == division_id).first()
    if not div:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Divisi dengan ID {division_id} tidak ditemukan."
        )

    weights = (
        db.query(DivisionCriteriaWeight)
        .filter(DivisionCriteriaWeight.division_id == division_id)
        .join(GroupCriteria)
        .options(contains_eager(DivisionCriteriaWeight.group_criteria))
        .all()
    )

    results = []
    for w in weights:
        gc = w.group_criteria
        if gc.is_active:
            results.append({
                "id": gc.id,
                "name": gc.name,
                "description": gc.description,
                "target_value": gc.target_value,
                "factor_type": gc.factor_type.value,
                "weight": w.weight
            })
            
    return results