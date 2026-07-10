from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.core.security import get_current_user, require_role
from backend.models import Employee, EmployeeScore, GroupCriteria, Division
from backend.schemas.employee import EmployeeCreate, EmployeeRead, EmployeeUpdate, EmployeeScoreCreate

router = APIRouter(prefix="/api/employees", tags=["employees"])


@router.get("/", response_model=list[EmployeeRead])
def list_employees(
    division_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(Employee).filter(Employee.is_active == True)
    if division_id is not None:
        q = q.filter(Employee.division_id == division_id)
    return q.order_by(Employee.full_name).all()


@router.get("/{employee_id}", response_model=EmployeeRead)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return _get_or_404(db, employee_id)


@router.post("/", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: EmployeeCreate,
    db: Session = Depends(get_db),
    _=Depends(require_role("kepala_hrd", "kepala_cabang")),
):
    existing = db.query(Employee).filter(Employee.employee_code == payload.employee_code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Employee code '{payload.employee_code}' already exists.",
        )

    emp = Employee(
        employee_code=payload.employee_code,
        full_name=payload.full_name,
        education_field_id=payload.education_field_id,
        division_id=payload.division_id,
        position=payload.position,
        has_sanction=payload.has_sanction,
        base_salary=payload.base_salary,
    )
    db.add(emp)
    db.flush()
    
    if payload.scores:
        _validate_and_persist_scores(db, emp.id, payload.division_id, payload.scores)

    db.commit()
    db.refresh(emp)
    return emp


@router.patch("/{employee_id}", response_model=EmployeeRead)
def update_employee(
    employee_id: int,
    payload: EmployeeUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_role("kepala_hrd", "kepala_cabang")),
):
    emp = _get_or_404(db, employee_id)
    update_data = payload.model_dump(exclude_none=True)
    
    # GANTI: Pisahkan field 'scores' agar tidak memicu error setattr pada relasi ORM
    new_scores = update_data.pop("scores", None)
    
    # Cek apakah terjadi perubahan divisi
    target_division_id = update_data.get("division_id", emp.division_id)
    division_changed = (target_division_id != emp.division_id)

    # Update field standar (nama, posisi, divisi, dll.)
    for field, value in update_data.items():
        setattr(emp, field, value)

    # Jika divisi berubah ATAU skor dikirim ulang, sinkronisasi skor menggunakan helper
    if division_changed or new_scores is not None:
        scores_to_persist = payload.scores if new_scores is not None else []
        _validate_and_persist_scores(db, emp.id, target_division_id, scores_to_persist)

    db.commit()
    db.refresh(emp)
    return emp


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_role("kepala_hrd")),
):
    emp = _get_or_404(db, employee_id)
    emp.is_active = False
    db.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_or_404(db: Session, employee_id: int) -> Employee:
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return emp

def _validate_and_persist_scores(
    db: Session, 
    emp_id: int, 
    division_id: int, 
    scores: list[EmployeeScoreCreate]
):
    """
    Validasi dan persistensi skor kriteria dengan menjaga integritas grup divisi.
    Strategi: Delete existing scores -> Validate criteria group ownership -> Bulk insert.
    """
    # 1. Hapus skor lama untuk menghindari stale data saat update/mutasi divisi
    db.query(EmployeeScore).filter(EmployeeScore.employee_id == emp_id).delete()
    
    if not scores:
        return

    # 2. Ambil group_id dari divisi karyawan saat ini
    division = db.query(Division).filter(Division.id == division_id).first()
    if not division:
        raise HTTPException(status_code=404, detail="Divisi tidak ditemukan.")
    
    requested_ids = {s.criteria_id for s in scores}
    
    # 3. Validasi O(1): Pastikan criteria_id eksis DAN milik grup divisi yang relevan
    valid_criteria = db.query(GroupCriteria.id).filter(
        GroupCriteria.id.in_(requested_ids),
        GroupCriteria.group_id == division.group_id,
        GroupCriteria.is_active == True
    ).all()
    
    valid_ids = {row.id for row in valid_criteria}
    missing_or_invalid = requested_ids - valid_ids
    
    if missing_or_invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Kriteria ID berikut tidak valid atau tidak milik grup divisi karyawan: {sorted(missing_or_invalid)}"
        )

    # 4. Bulk insert skor baru
    db.add_all(
        EmployeeScore(employee_id=emp_id, criteria_id=s.criteria_id, score=s.score)
        for s in scores
    )