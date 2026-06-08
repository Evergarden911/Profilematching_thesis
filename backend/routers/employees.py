from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import get_current_user, require_role
from backend.models import Employee, EmployeeScore, GroupCriteria
from backend.schemas.employee import EmployeeCreate, EmployeeRead, EmployeeUpdate

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
    db.flush()  # get emp.id before committing

    if payload.scores:
        requested_ids = {s.criteria_id for s in payload.scores}
        # Single query to validate all criteria IDs at once — O(1) instead of O(N).
        found_ids = {
            row.id
            for row in db.query(GroupCriteria.id).filter(GroupCriteria.id.in_(requested_ids)).all()
        }
        missing = requested_ids - found_ids
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Criteria ID(s) not found: {sorted(missing)}",
            )
        db.add_all(
            EmployeeScore(employee_id=emp.id, criteria_id=s.criteria_id, score=s.score)
            for s in payload.scores
        )

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
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(emp, field, value)
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