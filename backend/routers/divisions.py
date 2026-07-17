"""
Divisions Router
================
Mengelola CRUD Divisi, Grup, Bobot Kriteria, dan Batasan Pendidikan.
Telah diamankan dari injeksi payload relasional.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import require_role
from backend.models import (
    Division, DivisionConstraint, DivisionCriteriaWeight,
    DivisionGroup, EducationField, GroupCriteria, FactorType
)
from backend.schemas.division import (
    DivisionConstraintCreate, DivisionConstraintRead,
    DivisionCreate, DivisionGroupCreate, DivisionGroupRead, DivisionGroupUpdate,
    DivisionRead, DivisionUpdate,
    DivisionCriteriaWeightCreate, DivisionCriteriaWeightRead,
    EducationFieldCreate, EducationFieldRead,
    GroupCriteriaCreate, GroupCriteriaRead,
)

router = APIRouter(prefix="/api/divisions", tags=["divisions"])
_hrd = require_role("kepala_hrd", "kepala_cabang", "kepala_divisi")

# ---------------------------------------------------------------------------
# Division CRUD
# ---------------------------------------------------------------------------
@router.get("/", response_model=list[DivisionRead])
def list_divisions(group_id: int | None = None, db: Session = Depends(get_db), _=Depends(require_role("kepala_hrd", "kepala_cabang", "kepala_divisi"))):
    q = db.query(Division).filter(Division.is_active == True)
    if group_id is not None:
        q = q.filter(Division.group_id == group_id)
    return q.order_by(Division.name).all()

@router.post("/", response_model=DivisionRead, status_code=status.HTTP_201_CREATED)
def create_division(payload: DivisionCreate, db: Session = Depends(get_db), _=Depends(_hrd)):
    _assert_unique_name(db, payload.name)
    _assert_unique_code(db, payload.code)
    if payload.group_id:
        _assert_group_exists(db, payload.group_id)
    division = Division(**payload.model_dump())
    db.add(division)
    db.commit()
    db.refresh(division)
    return division

@router.patch("/{division_id}", response_model=DivisionRead)
def update_division(division_id: int, payload: DivisionUpdate, db: Session = Depends(get_db), _=Depends(_hrd)):
    div = _get_or_404(db, division_id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(div, field, value)
    db.commit()
    db.refresh(div)
    return div

@router.delete("/{division_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_division(division_id: int, db: Session = Depends(get_db), _=Depends(_hrd)):
    div = _get_or_404(db, division_id)
    div.is_active = False
    db.commit()

# ---------------------------------------------------------------------------
# Division Groups & Criteria
# ---------------------------------------------------------------------------
@router.get("/groups", response_model=list[DivisionGroupRead])
def list_groups(db: Session = Depends(get_db), _=Depends(require_role("kepala_hrd", "kepala_cabang", "kepala_divisi"))):
    return db.query(DivisionGroup).filter(DivisionGroup.is_active == True).order_by(DivisionGroup.name).all()

@router.post("/groups", response_model=DivisionGroupRead, status_code=status.HTTP_201_CREATED)
def create_group(payload: DivisionGroupCreate, db: Session = Depends(get_db), _=Depends(_hrd)):
    if db.query(DivisionGroup).filter(DivisionGroup.name == payload.name).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Group name already exists.")
    group = DivisionGroup(**payload.model_dump())
    db.add(group)
    db.commit()
    db.refresh(group)
    return group

@router.patch("/groups/{group_id}", response_model=DivisionGroupRead)
def update_group(
    group_id: int, 
    payload: DivisionGroupUpdate, 
    db: Session = Depends(get_db), 
    _=Depends(_hrd)
):
    """Memperbarui informasi nama atau deskripsi pada Grup Divisi."""
    group = _get_group_or_404(db, group_id)
    
    # Validasi jika nama grup diubah, pastikan tidak duplikat dengan yang lain
    if payload.name and payload.name != group.name:
        if db.query(DivisionGroup).filter(DivisionGroup.name == payload.name).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nama grup sudah digunakan.")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(group, field, value)
    
    db.commit()
    db.refresh(group)
    return group


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: int, 
    db: Session = Depends(get_db), 
    _=Depends(_hrd)
):
    """
    Menonaktifkan Grup Divisi. 
    Menerapkan validasi RESTRICT: Ditolak jika masih ada sub-divisi aktif di dalamnya.
    """
    group = _get_group_or_404(db, group_id)
    
    # Pencegahan pelanggaran integritas referensial (Foreign Key RESTRICT)
    has_active_divisions = db.query(Division).filter(
        Division.group_id == group_id, 
        Division.is_active == True
    ).first()
    
    if has_active_divisions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Grup tidak dapat dihapus karena masih menaungi sub-divisi aktif. Pindahkan atau hapus sub-divisi terlebih dahulu."
        )
        
    group.is_active = False
    db.commit()

@router.get("/groups/{group_id}/criteria", response_model=list[GroupCriteriaRead])
def list_group_criteria(group_id: int, db: Session = Depends(get_db), _=Depends(require_role("kepala_hrd", "kepala_cabang"))):
    _get_group_or_404(db, group_id)
    return db.query(GroupCriteria).filter(GroupCriteria.group_id == group_id, GroupCriteria.is_active == True).all()

@router.post("/groups/{group_id}/criteria", response_model=GroupCriteriaRead, status_code=status.HTTP_201_CREATED)
def create_group_criteria(group_id: int, payload: GroupCriteriaCreate, db: Session = Depends(get_db), _=Depends(_hrd)):
    _get_group_or_404(db, group_id)
    # INJEKSI AMAN: Memasukkan group_id dari URL secara paksa
    gc = GroupCriteria(**payload.model_dump(), group_id=group_id)
    db.add(gc)
    db.commit()
    db.refresh(gc)
    return gc

# ---------------------------------------------------------------------------
# Per-Sub-Division Weights (Mekanisme Pencegahan Injeksi Diterapkan)
# ---------------------------------------------------------------------------
@router.get("/{division_id}/weights", response_model=list[DivisionCriteriaWeightRead])
def get_division_weights(division_id: int, db: Session = Depends(get_db), _=Depends(require_role("kepala_hrd", "kepala_cabang"))):
    _get_or_404(db, division_id)
    return db.query(DivisionCriteriaWeight).filter(DivisionCriteriaWeight.division_id == division_id).all()

@router.put("/{division_id}/weights", response_model=list[DivisionCriteriaWeightRead])
def set_division_weights(division_id: int, weights: list[DivisionCriteriaWeightCreate], db: Session = Depends(get_db), _=Depends(_hrd)):
    _get_or_404(db, division_id)

    gc_ids = [w.group_criteria_id for w in weights]
    found_gc = {gc.id: gc for gc in db.query(GroupCriteria).filter(GroupCriteria.id.in_(gc_ids)).all()}
    
    missing = set(gc_ids) - set(found_gc.keys())
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Kriteria Grup tidak ditemukan: {sorted(missing)}")

    # Validasi total bobot wajib 1.0 (100%)
    core_total = sum(w.weight for w in weights if found_gc[w.group_criteria_id].factor_type == FactorType.core)
    secondary_total = sum(w.weight for w in weights if found_gc[w.group_criteria_id].factor_type == FactorType.secondary)
    _assert_weight_sum(core_total, "core")
    _assert_weight_sum(secondary_total, "secondary")

    db.query(DivisionCriteriaWeight).filter(DivisionCriteriaWeight.division_id == division_id).delete()
    
    # INJEKSI AMAN: Memasukkan division_id dari URL secara paksa ke setiap iterasi
    rows = [DivisionCriteriaWeight(division_id=division_id, **w.model_dump()) for w in weights]
    db.add_all(rows)
    db.commit()
    for r in rows: db.refresh(r)
    return rows

# ---------------------------------------------------------------------------
# Education & Constraints
# ---------------------------------------------------------------------------
@router.get("/education-fields", response_model=list[EducationFieldRead])
def list_education_fields(db: Session = Depends(get_db), _=Depends(require_role("kepala_hrd", "kepala_cabang", "kepala_divisi"))):
    return db.query(EducationField).filter(EducationField.is_active == True).order_by(EducationField.name).all()

@router.get("/{division_id}/constraints", response_model=list[DivisionConstraintRead])
def list_constraints(division_id: int, db: Session = Depends(get_db), _=Depends(require_role("kepala_hrd", "kepala_cabang"))):
    _get_or_404(db, division_id)
    return db.query(DivisionConstraint).filter(DivisionConstraint.division_id == division_id).all()

@router.post("/{division_id}/constraints", response_model=DivisionConstraintRead, status_code=status.HTTP_201_CREATED)
def create_constraint(division_id: int, payload: DivisionConstraintCreate, db: Session = Depends(get_db), _=Depends(_hrd)):
    _get_or_404(db, division_id)
    if not db.query(EducationField).filter(EducationField.id == payload.education_field_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jurusan pendidikan tidak ditemukan.")
    
    existing = db.query(DivisionConstraint).filter(
        DivisionConstraint.division_id == division_id,
        DivisionConstraint.education_field_id == payload.education_field_id,
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Aturan sudah ada. Gunakan PATCH untuk mengubah.")
        
    constraint = DivisionConstraint(**payload.model_dump(), division_id=division_id)
    db.add(constraint)
    db.commit()
    db.refresh(constraint)
    return constraint

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_or_404(db: Session, division_id: int) -> Division:
    div = db.query(Division).filter(Division.id == division_id).first()
    if not div: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Divisi tidak ditemukan.")
    return div

def _get_group_or_404(db: Session, group_id: int) -> DivisionGroup:
    g = db.query(DivisionGroup).filter(DivisionGroup.id == group_id).first()
    if not g: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grup Divisi tidak ditemukan.")
    return g

def _assert_group_exists(db: Session, group_id: int) -> None:
    _get_group_or_404(db, group_id)

def _assert_unique_name(db: Session, name: str) -> None:
    if db.query(Division).filter(Division.name == name).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Nama divisi '{name}' sudah ada.")

def _assert_unique_code(db: Session, code: str) -> None:
    if db.query(Division).filter(Division.code == code).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Kode divisi '{code}' sudah ada.")

def _assert_weight_sum(total: float, factor_name: str) -> None:
    if total > 0 and abs(total - 1.0) > 1e-6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Total bobot parameter {factor_name} harus 1.0 (100%), namun yang diterima adalah {total:.4f}.",
        )