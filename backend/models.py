"""
ORM Models — Single Source of Truth for the Database Schema
==========================================================
Sistem Relasi Basis Data Terintegrasi Pramita Lab.
Menghilangkan dualisme kriteria lama dan menyatukan seluruh sub-divisi
ke bawah arsitektur GroupCriteria dan EmployeeScore yang baru.
"""

import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey, 
    Integer, String, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship
from backend.core.database import Base


def _now():
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────
# ENUMS (Definisi Tipe Data Kontekstual)
# ─────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    """
    Standarisasi role pengguna menggunakan format lowercase legacy.
    Menghilangkan duplikasi uppercase untuk menjaga efisiensi dan konsistensi RBAC.
    """
    super_admin = "super_admin"
    kepala_hrd = "kepala_hrd"
    kepala_cabang = "kepala_cabang"
    kepala_divisi = "kepala_divisi"


class RequestStatus(str, enum.Enum):
    pending = "pending"
    gate_check = "gate_check"
    interview_required = "interview_required"
    forwarded = "forwarded"
    under_review = "under_review"
    matched = "matched"
    approved = "approved"
    rejected = "rejected"
    gate_rejected = "gate_rejected"


class FactorType(str, enum.Enum):
    core = "core"
    secondary = "secondary"


class GateStatus(str, enum.Enum):
    pending = "pending"
    interview_pending = "interview_pending"
    interview_passed = "interview_passed"
    interview_failed = "interview_failed"
    passed = "passed"
    failed = "failed"


class ConstraintType(str, enum.Enum):
    allowed = "allowed"
    blocked = "blocked"


class KPIDirection(str, enum.Enum):
    higher_is_better = "higher_is_better"
    lower_is_better = "lower_is_better"


class KPIType(str, enum.Enum):
    individual = "individual"
    operational = "operational"


# ─────────────────────────────────────────────────────────────
# ENTITAS AUTENTIKASI DAN PENGGUNA
# ─────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name       = Column(String(200), nullable=False)
    role            = Column(Enum(UserRole), nullable=False)
    division_id     = Column(Integer, ForeignKey("divisions.id", ondelete="SET NULL"), nullable=True)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=_now)

    division        = relationship("Division")


# ─────────────────────────────────────────────────────────────
# STRUCTURAL & ORGANIZATIONAL MODELS (Hierarki Sub-Divisi)
# ─────────────────────────────────────────────────────────────

class DivisionGroup(Base):
    """
    Payung Rumpun Kerja Besar. Contoh: LAB untuk Laboratorium Klinik.
    Menjadi jangkar utama pewarisan kriteria standardisasi dan bobot CF/SF.
    """
    __tablename__ = "division_groups"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(200), unique=True, nullable=False)
    code        = Column(String(20), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # IMPROVEMENT: Bobot Dinamis CF & SF per Rumpun Divisi
    cf_weight   = Column(Float, default=0.60, nullable=False)
    sf_weight   = Column(Float, default=0.40, nullable=False)

    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=_now)

    divisions   = relationship("Division", back_populates="group")
    criteria    = relationship("GroupCriteria", back_populates="group", cascade="all, delete-orphan")


class Division(Base):
    """
    Sub-Divisi Aktual atau Stasiun Kerja Riil di Pramita Lab.
    Memiliki alokasi anggaran finansial operasional bulanan mandiri.
    """
    __tablename__ = "divisions"

    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String(200), unique=True, nullable=False)
    code           = Column(String(20), unique=True, nullable=False, index=True)
    group_id       = Column(Integer, ForeignKey("division_groups.id", ondelete="RESTRICT"), nullable=False)
    monthly_budget = Column(Float, default=0.0, nullable=False)
    is_active      = Column(Boolean, default=True)
    created_at     = Column(DateTime, default=_now)

    group          = relationship("DivisionGroup", back_populates="divisions")
    employees      = relationship("Employee", back_populates="division")
    criteria_weights = relationship("DivisionCriteriaWeight", back_populates="division", cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────────────
# LOGIKA FILTRASI & PEMBATAS ADMINISTRATIF (Gates)
# ─────────────────────────────────────────────────────────────

class EducationField(Base):
    __tablename__ = "education_fields"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String(200), unique=True, nullable=False)
    code       = Column(String(20), unique=True, nullable=False, index=True)
    category   = Column(String(100), nullable=False)
    is_active  = Column(Boolean, default=True)


class DivisionConstraint(Base):
    __tablename__ = "division_constraints"
    __table_args__ = (UniqueConstraint("division_id", "education_field_id", name="uq_div_edu_constraint"),)

    id                               = Column(Integer, primary_key=True, index=True)
    division_id                      = Column(Integer, ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False)
    education_field_id               = Column(Integer, ForeignKey("education_fields.id", ondelete="CASCADE"), nullable=False)
    constraint_type                  = Column(Enum(ConstraintType), nullable=False)
    requires_interview_if_not_native = Column(Boolean, default=False, nullable=False)
    
    division = relationship("Division")
    education_field = relationship("EducationField")


# ─────────────────────────────────────────────────────────────
# CORE PROFILE MATCHING SYSTEM (Pembersihan Dualisme)
# ─────────────────────────────────────────────────────────────

class GroupCriteria(Base):
    """
    Kamus Utama Parameter Penilaian yang diwariskan ke Sub-Divisi.
    Menyimpan Target Nilas Ideal dan Klasifikasi Faktor Evaluasi.
    """
    __tablename__ = "group_criteria"
    __table_args__ = (UniqueConstraint("group_id", "name", name="uq_group_criteria_name"),)

    id           = Column(Integer, primary_key=True, index=True)
    group_id     = Column(Integer, ForeignKey("division_groups.id", ondelete="CASCADE"), nullable=False)
    name         = Column(String(200), nullable=False)
    description  = Column(Text, nullable=True)
    target_value = Column(Float, nullable=False)
    factor_type  = Column(Enum(FactorType), nullable=False)
    is_active    = Column(Boolean, default=True)

    group            = relationship("DivisionGroup", back_populates="criteria")
    weights          = relationship("DivisionCriteriaWeight", back_populates="group_criteria", cascade="all, delete-orphan")
    employee_scores  = relationship("EmployeeScore", back_populates="group_criteria", cascade="all, delete-orphan")


class DivisionCriteriaWeight(Base):
    """
    Bobot Dinamis Spesifik per Sub-Divisi.
    Menjamin total akumulasi bobot wajib 100% di level rute API.
    """
    __tablename__ = "division_criteria_weights"
    __table_args__ = (UniqueConstraint("division_id", "group_criteria_id", name="uq_div_crit_weight"),)

    id                = Column(Integer, primary_key=True, index=True)
    division_id       = Column(Integer, ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False)
    group_criteria_id = Column(Integer, ForeignKey("group_criteria.id", ondelete="CASCADE"), nullable=False)
    weight            = Column(Float, nullable=False)

    division       = relationship("Division", back_populates="criteria_weights")
    group_criteria = relationship("GroupCriteria", back_populates="weights")


# ─────────────────────────────────────────────────────────────
# DATA DEMOGRAFI & MATRIKS NILAI KARYAWAN
# ─────────────────────────────────────────────────────────────

class Employee(Base):
    __tablename__ = "employees"

    id                 = Column(Integer, primary_key=True, index=True)
    employee_code      = Column(String(50), unique=True, nullable=False, index=True)
    full_name          = Column(String(200), nullable=False)
    division_id        = Column(Integer, ForeignKey("divisions.id", ondelete="RESTRICT"), nullable=False)
    education_field_id = Column(Integer, ForeignKey("education_fields.id", ondelete="RESTRICT"), nullable=False)
    position           = Column(String(150), nullable=False)
    base_salary        = Column(Float, default=0.0, nullable=False)
    has_sanction       = Column(Boolean, default=False, nullable=False)
    is_active          = Column(Boolean, default=True)
    created_at         = Column(DateTime, default=_now)

    division   = relationship("Division", back_populates="employees")
    education  = relationship("EducationField")
    scores     = relationship("EmployeeScore", back_populates="employee", cascade="all, delete-orphan")


class EmployeeScore(Base):
    """
    Nilai Kompetensi Aktual Karyawan.
    Telah diikat mutlak ke GroupCriteria untuk melayani komputasi sub-divisi.
    """
    __tablename__ = "employee_scores"
    __table_args__ = (UniqueConstraint("employee_id", "criteria_id", name="uq_emp_score"),)

    id          = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    criteria_id = Column(Integer, ForeignKey("group_criteria.id", ondelete="CASCADE"), nullable=False)
    score       = Column(Float, nullable=False)

    employee       = relationship("Employee", back_populates="scores")
    group_criteria = relationship("GroupCriteria", back_populates="employee_scores")


# ─────────────────────────────────────────────────────────────
# TRANSAKSI ALUR KERJA MUTASI SDM (FSM & Audit Trail)
# ─────────────────────────────────────────────────────────────

class SDMRequest(Base):
    __tablename__ = "sdm_requests"

    id                 = Column(Integer, primary_key=True, index=True)
    requester_id       = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    target_division_id = Column(Integer, ForeignKey("divisions.id", ondelete="RESTRICT"), nullable=False)
    quantity           = Column(Integer, default=1, nullable=False)
    reason             = Column(Text, nullable=False)
    status             = Column(Enum(RequestStatus), default=RequestStatus.pending, nullable=False)
    
    # DEPRECATED / BYPASSED: Integrasi Keuangan Gerbang Anggaran (Dipertahankan di DB demi kompatibilitas seeder)
    budget_gate_status = Column(Enum(GateStatus), default=GateStatus.pending, nullable=False)
    budget_notes       = Column(Text, nullable=True)
    
    is_auto_generated  = Column(Boolean, default=False, nullable=False)
    hrd_notes          = Column(Text, nullable=True)
    created_at         = Column(DateTime, default=_now)
    updated_at         = Column(DateTime, default=_now, onupdate=_now)

    requester       = relationship("User")
    target_division = relationship("Division")


class RotationGate(Base):
    """
    Entitas Utama Evaluasi Kandidat (Gate A & Gate B).
    Bertindak sebagai stateful entity yang melacak eligibility sebelum Profile Matching.
    """
    __tablename__ = "rotation_gates"
    __table_args__ = (UniqueConstraint("sdm_request_id", "employee_id", name="uq_rotation_gate_flow"),)

    id                       = Column(Integer, primary_key=True, index=True)
    sdm_request_id           = Column(Integer, ForeignKey("sdm_requests.id", ondelete="CASCADE"), nullable=False)
    employee_id              = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    
    education_gate_status    = Column(Enum(GateStatus), default=GateStatus.pending, nullable=False)
    education_gate_notes     = Column(Text, nullable=True)
    education_checked_at     = Column(DateTime, nullable=True)
    
    interview_gate_status    = Column(Enum(GateStatus), nullable=True)
    interview_gate_notes     = Column(Text, nullable=True)
    interview_checked_at     = Column(DateTime, nullable=True)
    
    is_eligible_for_matching = Column(Boolean, default=False, nullable=False)
    created_at               = Column(DateTime, default=_now)
    updated_at               = Column(DateTime, default=_now, onupdate=_now)

    sdm_request = relationship("SDMRequest")
    employee    = relationship("Employee")
    history     = relationship("SDMEvaluationHistory", back_populates="gate", cascade="all, delete-orphan")


class SDMEvaluationHistory(Base):
    """
    NEW AUDIT TRAIL TABLE:
    Mencatat seluruh riwayat transisi status evaluasi (Otomatis & Manual Action HRD).
    Menjadi sumber data utama untuk halaman Riwayat Rotasi & fitur ekspor Excel.
    """
    __tablename__ = "sdm_evaluation_history"

    id          = Column(Integer, primary_key=True, index=True)
    gate_id     = Column(Integer, ForeignKey("rotation_gates.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status = Column(String(50), nullable=False)
    to_status   = Column(String(50), nullable=False)
    actor_id    = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reason      = Column(Text, nullable=True)
    is_manual   = Column(Boolean, default=False, nullable=False)
    created_at  = Column(DateTime, default=_now, nullable=False)

    gate  = relationship("RotationGate", back_populates="history")
    actor = relationship("User")


class MatchingResult(Base):
    __tablename__ = "matching_results"
    __table_args__ = (UniqueConstraint("sdm_request_id", "employee_id", name="uq_matching_res_node"),)

    id             = Column(Integer, primary_key=True, index=True)
    sdm_request_id = Column(Integer, ForeignKey("sdm_requests.id", ondelete="CASCADE"), nullable=False)
    employee_id    = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    ncf_score      = Column(Float, nullable=False)
    nsf_score      = Column(Float, nullable=False)
    final_score    = Column(Float, nullable=False)
    rank           = Column(Integer, nullable=False)
    computed_at    = Column(DateTime, default=_now)

    sdm_request = relationship("SDMRequest")
    employee    = relationship("Employee")


class TransferLetter(Base):
    __tablename__ = "transfer_letters"

    id             = Column(Integer, primary_key=True, index=True)
    sdm_request_id = Column(Integer, ForeignKey("sdm_requests.id", ondelete="RESTRICT"), unique=True, nullable=False)
    issued_by_id   = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    letter_number  = Column(String(100), unique=True, nullable=False)
    content        = Column(Text, nullable=False)
    created_at     = Column(DateTime, default=_now)

    sdm_request = relationship("SDMRequest")
    issuer      = relationship("User")


# ─────────────────────────────────────────────────────────────
# MONITORING OPERASIONAL BEBAN KERJA (WLA)
# ─────────────────────────────────────────────────────────────

class WorkloadAnalysis(Base):
    __tablename__ = "workload_analyses"
    __table_args__ = (UniqueConstraint("division_id", "period", name="uq_wla_period_node"),)

    id                   = Column(Integer, primary_key=True, index=True)
    division_id          = Column(Integer, ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False)
    period               = Column(String(7), nullable=False)
    total_workload_hours = Column(Float, nullable=False)
    total_capacity_hours = Column(Float, nullable=False)
    headcount            = Column(Integer, nullable=False)
    wla_value            = Column(Float, nullable=False)
    is_understaffed      = Column(Boolean, default=False, nullable=False)
    is_overstaffed       = Column(Boolean, default=False, nullable=False)
    notes                = Column(Text, nullable=True)
    recorded_at          = Column(DateTime, default=_now)

    division = relationship("Division")


# ─────────────────────────────────────────────────────────────
# KPI SUB-SYSTEM (Dipertahankan untuk Kebutuhan Rekam Penilaian)
# ─────────────────────────────────────────────────────────────

class KPIIndicator(Base):
    __tablename__ = "kpi_indicators"

    id          = Column(Integer, primary_key=True, index=True)
    division_id = Column(Integer, ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False)
    name        = Column(String(200), nullable=False)
    weight      = Column(Float, nullable=False)
    direction   = Column(Enum(KPIDirection), default=KPIDirection.higher_is_better, nullable=False)
    kpi_type    = Column(Enum(KPIType), default=KPIType.individual, nullable=False)
    is_active   = Column(Boolean, default=True)
    
    division    = relationship("Division")
    records     = relationship("KPIRecord", back_populates="indicator", cascade="all, delete-orphan")


class KPIPeriod(Base):
    __tablename__ = "kpi_periods"

    id          = Column(Integer, primary_key=True, index=True)
    period_name = Column(String(7), unique=True, nullable=False)
    is_active   = Column(Boolean, default=True)


class KPIRecord(Base):
    __tablename__ = "kpi_records"
    __table_args__ = (UniqueConstraint("employee_id", "indicator_id", "period_id", name="uq_kpi_record"),)

    id           = Column(Integer, primary_key=True, index=True)
    employee_id  = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    indicator_id = Column(Integer, ForeignKey("kpi_indicators.id", ondelete="CASCADE"), nullable=False)
    period_id    = Column(Integer, ForeignKey("kpi_periods.id", ondelete="RESTRICT"), nullable=False)
    raw_value    = Column(Float, nullable=False)
    kpi_score    = Column(Float, nullable=False)
    recorded_at  = Column(DateTime, default=_now)

    indicator = relationship("KPIIndicator", back_populates="records")