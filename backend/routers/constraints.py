from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import get_current_user, require_role
from backend.models import User, DivisionConstraint, EducationField
from backend.schemas.constraint import ConstraintCreate, ConstraintRead, EducationFieldCreate

router = APIRouter(prefix="/api/constraints", tags=["constraints"])

@router.get("/", response_model=list[ConstraintRead])
def list_constraints(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mengambil semua aturan matriks kualifikasi yang terdaftar di basis data.
    """
    # Mengamankan rute: Hanya Kepala HRD dan Kepala Cabang yang boleh memanggil API ini
    if current_user.role.value not in ["kepala_hrd", "kepala_cabang"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak memiliki hak akses untuk melihat aturan kualifikasi."
        )

    constraints = db.query(DivisionConstraint).all()
    
    # Merakit data agar nama divisi dan nama jurusan ikut terkirim ke frontend
    output = []
    for c in constraints:
        div_name = c.division.name if c.division else f"Divisi ID: {c.division_id}"
        edu_name = c.education_field.name if c.education_field else f"Jurusan ID: {c.education_field_id}"
        
        output.append(ConstraintRead(
            id=c.id,
            division_id=c.division_id,
            education_field_id=c.education_field_id,
            constraint_type=c.constraint_type,
            requires_interview_if_not_native=c.requires_interview_if_not_native,
            division_name=div_name,
            education_field_name=edu_name
        ))
    return output

@router.post("/", response_model=ConstraintRead, status_code=status.HTTP_201_CREATED)
def create_constraint(
    payload: ConstraintCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("kepala_hrd"))
):
    """
    Membuat aturan batasan kualifikasi baru (Hanya untuk Kepala HRD).
    """
    # Mencegah duplikasi aturan untuk kombinasi divisi dan jurusan yang sama
    existing = db.query(DivisionConstraint).filter(
        DivisionConstraint.division_id == payload.division_id,
        DivisionConstraint.education_field_id == payload.education_field_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aturan untuk kombinasi divisi dan jurusan ini sudah terdaftar."
        )
        
    new_const = DivisionConstraint(
        division_id=payload.division_id,
        education_field_id=payload.education_field_id,
        constraint_type=payload.constraint_type,
        requires_interview_if_not_native=payload.requires_interview_if_not_native
    )
    db.add(new_const)
    db.commit()
    db.refresh(new_const)
    return new_const

@router.delete("/{constraint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_constraint(
    constraint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("kepala_hrd"))
):
    """
    Menghapus aturan batasan kualifikasi (Hanya untuk Kepala HRD).
    """
    const = db.query(DivisionConstraint).filter(DivisionConstraint.id == constraint_id).first()
    if not const:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aturan kualifikasi tidak ditemukan."
        )
    db.delete(const)
    db.commit()
    return None

@router.post("/education-fields", status_code=status.HTTP_201_CREATED)
def create_dynamic_education(
    payload: EducationFieldCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("kepala_hrd"))
):
    """Memungkinkan HRD menambah data jurusan Master secara *on-the-fly*"""
    # Mencegah duplikasi data master
    exist = db.query(EducationField).filter(EducationField.name.ilike(payload.name)).first()
    if exist:
        raise HTTPException(status_code=400, detail=f"Jurusan {payload.name} sudah terdaftar.")
        
    new_edu = EducationField(
        name=payload.name, 
        code=payload.code, 
        category=payload.category
    )
    db.add(new_edu)
    db.commit()
    return {"message": "Jurusan berhasil ditambahkan"}