"""
Main FastAPI Application (MPA / SSR Architecture)
=================================================
Menghubungkan seluruh router API dan bertindak sebagai mesin 
Server-Side Rendering (SSR) menggunakan Jinja2.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, Depends, HTTPException, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text, extract
from sqlalchemy.orm import Session, contains_eager

from backend.core.config import settings
from backend.core.database import Base, engine, get_db
from backend.models import User, SDMRequest, RequestStatus, Employee, Division, GroupCriteria, DivisionCriteriaWeight, MatchingResult, WorkloadAnalysis, RotationGate, GateStatus
from backend.core.security import get_current_user

# Import API Routers
from backend.routers import auth, calculation, criteria, divisions, employees, gates, sdm, wla, constraints

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

@asynccontextmanager
async def lifespan(app: FastAPI):
    with engine.begin() as conn:
        conn.execute(text("SELECT 1"))
    logger.info("Database connection OK")
    if settings.DB_INIT_ON_STARTUP:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized (create_all)")
    yield

app = FastAPI(title="Pramita Lab DSS", lifespan=lifespan)

# ---------------------------------------------------------------------------
# KONFIGURASI ASET STATIS & JINJA2 TEMPLATES
# ---------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")

modals_path = FRONTEND_DIR / "modals"
if modals_path.exists():
    app.mount("/modals", StaticFiles(directory=str(modals_path)), name="modals")

templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))

# ---------------------------------------------------------------------------
# API ROUTERS (Digunakan oleh fetch() untuk eksekusi aksi spesifik/modal)
# ---------------------------------------------------------------------------
app.include_router(auth.router)
app.include_router(employees.router)
app.include_router(criteria.router)
app.include_router(sdm.router)
app.include_router(calculation.router)
app.include_router(divisions.router)
app.include_router(gates.router)
app.include_router(wla.router)
app.include_router(constraints.router)


# ---------------------------------------------------------------------------
# WEB VIEW ROUTES (Mesin Pembuat Halaman HTML Jinja2)
# ---------------------------------------------------------------------------

def get_current_user_from_cookie(request: Request, db: Session):
    """
    Mengekstrak token JWT secara langsung dari Cookie menggunakan fungsi keamanan utama.
    """
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None

@app.get("/", response_class=HTMLResponse)
async def view_login_root(request: Request):  # <-- FIXED name
    if request.cookies.get("access_token"):
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login")
async def view_login_page(request: Request):  # <-- FIXED name
    if request.cookies.get("access_token"):
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/logout")
async def logout(response: Response):
    # Menghapus cookie otentikasi
    response.delete_cookie(key="access_token")
    return RedirectResponse(url="/", status_code=302)

@app.get("/dashboard", response_class=HTMLResponse)
async def view_dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user: return RedirectResponse(url="/", status_code=302)

    now = datetime.now()
    
    # Deteksi WLA Kritis untuk notifikasi proaktif
    critical_wla_count = db.query(WorkloadAnalysis).filter(
        WorkloadAnalysis.is_understaffed == True,
        WorkloadAnalysis.period == now.strftime("%Y-%m")
    ).count()

    stats = {
        "total_requests": db.query(SDMRequest).count(),
        "pending_requests": db.query(SDMRequest).filter(SDMRequest.status == RequestStatus.pending).count(),
        "completed_requests": db.query(SDMRequest).filter(SDMRequest.status == RequestStatus.matched).count(),
        "active_employees": db.query(Employee).filter(Employee.is_active == True).count(),
        "critical_wla_divisions": critical_wla_count,
        "monthly_delta": db.query(SDMRequest).filter(
            extract('month', SDMRequest.created_at) == now.month,
            extract('year', SDMRequest.created_at) == now.year
        ).count()
    }
    
    recent_reqs = db.query(SDMRequest).order_by(SDMRequest.created_at.desc()).limit(5).all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_user": user,
        "active_page": "dashboard",
        "stats": stats,
        "recent_requests": recent_reqs,
        "current_date": now.strftime("%A, %d %B %Y")
    })

@app.get("/employees", response_class=HTMLResponse)
async def view_employees(
    request: Request, 
    search: Optional[str] = None,
    division: Optional[str] = None,
    role: Optional[str] = None,
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(request, db)
    if not user: return RedirectResponse(url="/", status_code=302)

    query = db.query(Employee).options(contains_eager(Employee.division)).join(Division)
    if search:
        query = query.filter(Employee.full_name.ilike(f"%{search}%"))
    if division:
        query = query.filter(Division.code == division)
    if role:
        query = query.filter(Employee.position == role)
        
    emps = query.all()
    divs = db.query(Division).all()

    return templates.TemplateResponse("employees.html", {
        "request": request,
        "current_user": user,
        "active_page": "employees",
        "employees_data": emps,
        "divisions_list": divs,
        "search_query": search,
        "current_division": division,
        "current_role": role
    })

@app.get("/requests", response_class=HTMLResponse)
async def view_requests(
    request: Request, 
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(request, db)
    if not user: return RedirectResponse(url="/", status_code=302)

    query = db.query(SDMRequest)
    if status and status != 'all':
        query = query.filter(SDMRequest.status == status)
        
    reqs = query.order_by(SDMRequest.created_at.desc()).all()

    return templates.TemplateResponse("requests.html", {
        "request": request,
        "current_user": user,
        "active_page": "requests",
        "requests": reqs,
        "current_filter": status,
        "search_query": search
    })

@app.get("/results/{request_id}", response_class=HTMLResponse)
async def view_results_detail(
    request_id: int,
    request: Request, 
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(request, db)
    if not user: return RedirectResponse(url="/", status_code=302)
    
    req_data = db.query(SDMRequest).filter(SDMRequest.id == request_id).first()
    if not req_data:
        raise HTTPException(status_code=404, detail="Request tidak ditemukan")

    # 1. TARIK KRITERIA STANDAR DIVISI TARGET (Untuk render dinamis Tabel Gap)
    target_criteria_weights = (
        db.query(DivisionCriteriaWeight)
        .join(GroupCriteria)
        .filter(
            DivisionCriteriaWeight.division_id == req_data.target_division_id,
            GroupCriteria.is_active == True
        )
        .options(contains_eager(DivisionCriteriaWeight.group_criteria))
        .all()
    )

    candidates = (
        db.query(MatchingResult)
        .filter(MatchingResult.sdm_request_id == request_id)
        .options(contains_eager(MatchingResult.employee).contains_eager(Employee.division))
        .join(Employee)
        .join(Division)
        .order_by(MatchingResult.rank)
        .all()
    )

    # 2. TRANSFORMATION & INJEKSI GAP DETAIL
    from backend.services.profile_matching import compute_match, CriteriaInput
    formatted_candidates = []
    
    for cand in candidates:
        emp = cand.employee
        # Ekstrak skor kompetensi aktual karyawan dari database
        emp_scores = {es.criteria_id: es.score for es in emp.scores}
        
        inputs = []
        for dw in target_criteria_weights:
            gc = dw.group_criteria
            inputs.append(CriteriaInput(
                criteria_id=gc.id,
                employee_score=emp_scores.get(gc.id, 1.0), # Safety fallback ke 1.0 jika belum dinilai
                target_value=gc.target_value,
                weight=dw.weight,
                factor_type=gc.factor_type.value
            ))
        
        # Panggil compute_match murni untuk mendapatkan struktur gap_detail
        pm_calc = compute_match(emp.id, inputs)

        formatted_candidates.append({
            "id": emp.id,
            "employee_name": emp.full_name,
            "employee_code": emp.employee_code,
            "employee_role": emp.position,
            "origin_division": emp.division.name if emp.division else "Internal",
            "origin_division_code": emp.division.code if emp.division else "-",
            "ncf_score": cand.ncf_score,
            "nsf_score": cand.nsf_score,
            "final_score": cand.final_score,
            "gap_detail": pm_calc.gap_detail  # <-- MEMUTUS BLIND SPOT: INJEKSI GAP
        })

    return templates.TemplateResponse("results.html", {
        "request": request,
        "current_user": user,
        "active_page": "results",
        "request_data": {
            "id": req_data.id,
            "code": f"REQ-{req_data.id:04d}",
            "target_division_name": req_data.target_division.name if req_data.target_division else "Unknown",
            "quantity": req_data.quantity,  # <-- PATCH BUG #1: KUOTA ASLI DISALURKAN KE UI
            "status": req_data.status.value if hasattr(req_data.status, 'value') else str(req_data.status)
        },
        "candidates": formatted_candidates,
        "target_criteria": target_criteria_weights,  # <-- INJEKSI KRITERIA STANDAR KE UI
        "calculated_at": candidates[0].computed_at.strftime('%d %b %Y, %H:%M') if candidates else "Belum dikalkulasi",
        "ncf_weight": 60,
        "nsf_weight": 40,
        "total_criteria": len(target_criteria_weights)
    })

@app.get("/criteria", response_class=HTMLResponse)
async def view_criteria(
    request: Request, 
    division: Optional[str] = None,
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(request, db)
    if not user: return RedirectResponse(url="/", status_code=302)

    divs = db.query(Division).all()
    criteria_list = []
    ncf_total = 0.0
    nsf_total = 0.0

    if division:
        # Melakukan query ke arsitektur Sub-Divisi yang baru
        division_weights = (
            db.query(DivisionCriteriaWeight)
            .join(Division)
            .join(GroupCriteria)
            .filter(Division.code == division)
            .options(contains_eager(DivisionCriteriaWeight.group_criteria))
            .all()
        )

        for dw in division_weights:
            gc = dw.group_criteria
            # Memformat data untuk Template Jinja2
            criteria_list.append({
                "name": gc.name,
                "factor_type": gc.factor_type,
                "weight": dw.weight
            })
            
            if gc.factor_type.value == 'core': 
                ncf_total += dw.weight
            else: 
                nsf_total += dw.weight

    return templates.TemplateResponse("criteria.html", {
        "request": request,
        "current_user": user,
        "active_page": "criteria",
        "divisions_list": divs,
        "criteria_data": criteria_list,
        "current_division": division,
        "ncf_total_weight": round(ncf_total * 100),
        "nsf_total_weight": round(nsf_total * 100)
    })

@app.get("/health")
def health():
    try:
        with engine.begin() as conn: conn.execute(text("SELECT 1"))
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "detail": str(e)}
    
    
@app.get("/gates", response_class=HTMLResponse)
async def view_gates(
    request: Request,
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(request, db)
    if not user: return RedirectResponse(url="/", status_code=302)

    # Menarik daftar kandidat yang tertahan karena mutasi lintas fungsi
    pending_gates = (
        db.query(RotationGate)
        .join(Employee)
        .join(SDMRequest)
        .filter(RotationGate.interview_gate_status == GateStatus.interview_pending)
        .options(contains_eager(RotationGate.employee), contains_eager(RotationGate.sdm_request))
        .order_by(RotationGate.updated_at.desc())
        .all()
    )

    return templates.TemplateResponse("gates.html", {
        "request": request,
        "current_user": user,
        "active_page": "gates", # Untuk indikator menu aktif di sidebar
        "pending_gates": pending_gates
    })
    
@app.get("/divisions", response_class=HTMLResponse)
async def view_divisions(request: Request, db: Session = Depends(get_db)):
    # Asumsi Anda menggunakan fungsi get_current_user_from_cookie seperti pada rute lain
    user = get_current_user_from_cookie(request, db)
    if not user: return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("divisions.html", {
        "request": request, 
        "current_user": user, 
        "active_page": "divisions"
    })

@app.get("/wla", response_class=HTMLResponse)
async def view_wla(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user: 
        return RedirectResponse(url="/login", status_code=302)

    user_role_str = str(user.role.value if hasattr(user.role, 'value') else user.role).lower()
    
    # Daftar izin
    read_roles = ["kepala_hrd", "manajer_hrd", "admin_hrd", "hrd", "kepala_cabang", "eksekutif", "kacab", "kepala_divisi", "kepala_bagian", "bagian"]
    write_roles = ["kepala_hrd", "manajer_hrd", "admin_hrd", "hrd", "kepala_divisi", "kepala_bagian", "bagian"]

    # Gatekeeper halaman: Jika bukan termasuk ketiga rumpun tersebut, tendang ke dashboard
    if user_role_str not in read_roles:
        return RedirectResponse(url="/dashboard", status_code=303)

    # Tentukan apakah user aktif boleh melakukan input/edit
    can_edit = user_role_str in write_roles

    return templates.TemplateResponse("wla.html", {
        "request": request, 
        "current_user": user, 
        "active_page": "wla",
        "can_edit_wla": can_edit  # <-- INJEKSI FLAG KE UI
    })

@app.get("/results", response_class=HTMLResponse)
async def view_results_list(  # <-- FIXED BUG-02 (Nama diubah)
    request: Request, 
    request_id: Optional[int] = None, 
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(request, db)
    if not user: return RedirectResponse(url="/", status_code=302)

    request_data = {}
    candidates = []

    if request_id:
        # Menarik data pengajuan
        sdm_req = db.query(SDMRequest).filter(SDMRequest.id == request_id).first()
        if sdm_req:
            request_data = {
                "code": str(sdm_req.id),
                "target_division_name": sdm_req.target_division.name if sdm_req.target_division else "Tidak Diketahui"
            }

            # Menarik hasil Profile Matching yang sudah diurutkan berdasarkan peringkat (Rank)
            results_db = (
                db.query(MatchingResult)
                .filter(MatchingResult.sdm_request_id == request_id)
                .order_by(MatchingResult.rank.asc())
                .all()
            )

            # Memformat data untuk dikonsumsi oleh Jinja2 HTML
            for r in results_db:
                candidates.append({
                    "id": r.employee.id,
                    "employee_name": r.employee.full_name,  # <--- FIXED BUG-14 & BUG-22: Ganti 'name' ke 'employee_name'
                    "employee_code": r.employee.employee_code,
                    "ncf_score": round(r.ncf_score, 2),
                    "nsf_score": round(r.nsf_score, 2),
                    "final_score": round(r.final_score, 2),
                    "rank": r.rank
                })

    return templates.TemplateResponse("results.html", {
        "request": request, 
        "current_user": user, 
        "active_page": "results",
        "request_data": request_data,
        "candidates": candidates
    })
    
@app.get("/constraints", response_class=HTMLResponse)
async def get_constraints_page(request: Request, db: Session = Depends(get_db)):
    """
    Menampilkan halaman web antarmuka Matriks Kualifikasi Mutasi.
    """
    # Ekstraksi token atau user dari cookies/session untuk keamanan halaman
    # Kode ini mengasumsikan Anda menggunakan get_current_user untuk otentikasi halaman web
    try:
        from backend.core.security import get_current_user
        # Tergantung arsitektur otentikasi halaman Anda, sesuaikan dependensi user di bawah ini:
        current_user = get_current_user(request, db) 
        
        if current_user.role.value not in ["kepala_hrd", "kepala_cabang"]:
            raise HTTPException(status_code=403, detail="Hak akses ditolak.")
            
        # Merender berkas constraints.html ke peramban
        return templates.TemplateResponse(
            "constraints.html", 
            {"request": request, "current_user": current_user}
        )
    except Exception:
        # Jika belum login atau token kedaluwarsa, arahkan kembali ke halaman login utama
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login", status_code=303)
    
@app.get("/admin", response_class=HTMLResponse)
async def view_admin_system(request: Request, db: Session = Depends(get_db)):
    """
    Menampilkan halaman web Administrasi Sistem & RBAC.
    Hanya dapat diakses oleh akun dengan hak akses Manajer HRD atau Super Admin.
    """
    # 1. Otentikasi: Ambil user aktif dari cookie sesi
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # 2. Otorisasi (RBAC): Pastikan hanya role HRD dan Super Admin yang bisa masuk
    #    Kita cek lowercase & uppercase untuk menghindari kendala case-sensitive enum/string
    user_role_str = str(user.role.value if hasattr(user.role, 'value') else user.role).lower()
    allowed_roles = ["kepala_hrd", "super_admin", "hrd"]
    
    if user_role_str not in allowed_roles:
        logger.warning(f"Akses ilegal ke halaman /admin oleh user ID {user.id} dengan role '{user_role_str}'")
        # Alihkan kembali ke dashboard jika mencoba memodifikasi URL secara manual
        return RedirectResponse(url="/dashboard", status_code=303)

    # 3. Render template admin.html jika lolos otentikasi & otorisasi
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "current_user": user,
        "active_page": "admin"  # Memicu sorotan menu aktif di sidebar
    })
    
   
@app.get("/history", response_class=HTMLResponse)
async def view_history_log(
    request: Request,
    division: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Menampilkan Laporan Historis & Audit Log Rotasi SDM.
    Hanya dapat diakses oleh Kepala HRD, Kepala Cabang, dan Manajemen Eksekutif.
    """
    # 1. Otentikasi Pengguna dari Cookie
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    # 2. Otorisasi RBAC (Gatekeeper Eksekutif)
    allowed_roles = ["kepala_hrd", "kepala_cabang", "manajer_hrd", "eksekutif", "super_admin"]
    user_role_str = str(user.role.value if hasattr(user.role, 'value') else user.role).lower()
    
    if user_role_str not in allowed_roles:
        logger.warning(f"Akses ilegal ke /history oleh user ID {user.id} dengan role '{user_role_str}'")
        return RedirectResponse(url="/dashboard", status_code=303)

    # 3. Query Pengajuan yang Sudah Final (Selesai / Matched / Ditolak)
    query = db.query(SDMRequest).filter(
        SDMRequest.status.in_([
            RequestStatus.matched, 
            RequestStatus.approved, 
            RequestStatus.rejected
        ])
    )
    
    # Filter Opsional berdasarkan Divisi dan Status
    if division and division != 'all':
        query = query.join(Division, SDMRequest.target_division_id == Division.id).filter(Division.code == division)
    if status_filter and status_filter != 'all':
        query = query.filter(SDMRequest.status == status_filter)
        
    # Urutkan dari keputusan paling baru (Kronologis terbalik)
    history_records = query.order_by(SDMRequest.updated_at.desc()).all()

    # 4. Transformasi Data untuk Konsumsi Jinja2
    formatted_history = []
    for req in history_records:
        # Tarik data kandidat Top-N yang resmi dimutasi/disahkan
        top_candidates = (
            db.query(MatchingResult)
            .filter(MatchingResult.sdm_request_id == req.id)
            .order_by(MatchingResult.rank.asc())
            .limit(req.quantity)
            .all()
        )
        
        # Hitung total seluruh kandidat yang pernah dikomputasi (termasuk cadangan)
        total_assessed = db.query(MatchingResult).filter(MatchingResult.sdm_request_id == req.id).count()
        
        formatted_history.append({
            "id": req.id,
            "code": f"REQ-{req.id:04d}",
            "target_division_name": req.target_division.name if req.target_division else "Tidak Diketahui",
            "quantity": req.quantity,
            "status": req.status.value if hasattr(req.status, 'value') else str(req.status),
            "created_at": req.created_at.strftime('%d %b %Y'),
            "completed_at": req.updated_at.strftime('%d %b %Y, %H:%M') if req.updated_at else "-",
            "selected_employees": [c.employee.full_name for c in top_candidates if c.employee],
            "total_assessed": total_assessed,
            "talent_pool_count": max(0, total_assessed - req.quantity)
        })

    divs = db.query(Division).all()

    return templates.TemplateResponse("history.html", {
        "request": request,
        "current_user": user,
        "active_page": "history",  # Memicu nyala menu aktif di sidebar
        "history_data": formatted_history,
        "divisions_list": divs,
        "current_division": division,
        "current_status": status_filter
    })    