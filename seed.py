"""
seed.py — Master Seeder Data Pramita Lab
========================================
Menghasilkan lingkungan data yang siap untuk demonstrasi Sidang Skripsi:
  - Standardisasi Grouping Divisi (Lab, Penunjang Medis, Manajemen)
  - Parameter Finansial (Anggaran Divisi & Gaji Karyawan)
  - Data Demografi Karyawan Fiktif & Nilai Profile Matching
  - Simulasi Beban Kerja (WLA)
"""

import sys
import os
import random
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.core.database import SessionLocal, engine, Base
from backend.core.security import get_password_hash
from backend.models import (
    ConstraintType,
    Division,
    DivisionConstraint,
    DivisionGroup,
    EducationField,
    FactorType,
    GroupCriteria,
    DivisionCriteriaWeight,
    User,
    UserRole,
    Employee,
    EmployeeScore,
    WorkloadAnalysis
)

# ─────────────────────────────────────────────────────────────
# 1. Konfigurasi Grup Divisi Terpusat
# ─────────────────────────────────────────────────────────────
DIVISION_GROUPS = [
    {"code": "LAB", "name": "Laboratorium", "desc": "Grup divisi laboratorium klinik utama"},
    {"code": "MED", "name": "Penunjang Medis", "desc": "Grup radiologi dan diagnostik"},
    {"code": "MGT", "name": "Manajemen & Umum", "desc": "Grup operasional dan pendukung bisnis"},
]

# ─────────────────────────────────────────────────────────────
# 2. Struktur Divisi & Anggaran Bulanan
# ─────────────────────────────────────────────────────────────
DIVISIONS = [
    # Laboratorium
    {"code": "HEM", "name": "Hematologi", "group": "LAB", "budget": 60_000_000},
    {"code": "KLR", "name": "Klinik Rutin", "group": "LAB", "budget": 45_000_000},
    {"code": "KIA", "name": "Kimia Klinik & Immun Abbott", "group": "LAB", "budget": 75_000_000},
    {"code": "PCR", "name": "PCR", "group": "LAB", "budget": 80_000_000},
    
    # Penunjang Medis
    {"code": "RAD", "name": "Radiologi", "group": "MED", "budget": 50_000_000},
    {"code": "ELD", "name": "Elektrodiagnostik", "group": "MED", "budget": 40_000_000},
    
    # Manajemen
    {"code": "CS", "name": "Customer Service", "group": "MGT", "budget": 30_000_000},
    {"code": "SDM", "name": "SDM & HRD", "group": "MGT", "budget": 35_000_000},
    {"code": "KEU", "name": "Keuangan", "group": "MGT", "budget": 40_000_000},
]

# ─────────────────────────────────────────────────────────────
# 3. Kriteria & Bobot (Standardisasi Group Criteria)
# ─────────────────────────────────────────────────────────────
GROUP_CRITERIA_SCHEMA = {
    "LAB": [
        ("Kompetensi Teknis Lab", 5.0, FactorType.core, 0.50),
        ("Kepatuhan Prosedur", 5.0, FactorType.core, 0.50),
        ("Kemampuan Komunikasi", 4.0, FactorType.secondary, 0.50),
        ("Adaptabilitas", 4.0, FactorType.secondary, 0.50),
    ],
    "MED": [
        ("Operasi Alat Medis", 5.0, FactorType.core, 0.60),
        ("Akurasi Diagnostik", 5.0, FactorType.core, 0.40),
        ("Empati Pasien", 4.0, FactorType.secondary, 1.00),
    ],
    "MGT": [
        ("Kompetensi Manajerial", 4.0, FactorType.core, 0.60),
        ("Problem Solving", 4.0, FactorType.core, 0.40),
        ("Komunikasi Lintas Divisi", 5.0, FactorType.secondary, 1.00),
    ]
}

# ─────────────────────────────────────────────────────────────
# Eksekusi Seeder Utama
# ─────────────────────────────────────────────────────────────

def seed():
    db = SessionLocal()
    print(" -> Memeriksa dan memaksa pembuatan tabel fisik di PostgreSQL...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("Membangun ulang ekosistem data Pramita Lab...")

        # 1. GENERATE PENDIDIKAN (Education Fields)
        print(" -> Menyuntikkan Jurusan Pendidikan...")
        edu_list = [
            ("Analis Kesehatan / ATLM", "ATLM", "Kesehatan"),
            ("Keperawatan", "KPRW", "Kesehatan"),
            ("Kedokteran", "DOK", "Kesehatan"),
            ("Manajemen", "MNJ", "Bisnis"),
            ("Teknik Informatika", "TI", "Teknik")
        ]
        edu_map = {}
        for name, code, cat in edu_list:
            ef = db.query(EducationField).filter_by(code=code).first()
            if not ef:
                ef = EducationField(name=name, code=code, category=cat)
                db.add(ef)
                db.flush()
            edu_map[code] = ef

        # 2. GENERATE GRUP DIVISI
        print(" -> Menyuntikkan Grup Divisi Utama...")
        group_map = {}
        for g in DIVISION_GROUPS:
            grp = db.query(DivisionGroup).filter_by(code=g["code"]).first()
            if not grp:
                grp = DivisionGroup(name=g["name"], code=g["code"], description=g["desc"])
                db.add(grp)
                db.flush()
            group_map[g["code"]] = grp

        # 3. GENERATE KRITERIA GRUP & DIVISI
        print(" -> Menyuntikkan Kriteria & Divisi (Tanpa Dualisme)...")
        div_map = {}
        for d in DIVISIONS:
            grp = group_map[d["group"]]
            
            # Buat Divisinya dengan Anggaran Finansial
            div = db.query(Division).filter_by(code=d["code"]).first()
            if not div:
                div = Division(name=d["name"], code=d["code"], group_id=grp.id, monthly_budget=d["budget"])
                db.add(div)
                db.flush()
            div_map[d["code"]] = div

            # Buat Kriteria dan Bobot Spesifik
            for c_name, target, ftype, weight in GROUP_CRITERIA_SCHEMA[d["group"]]:
                gc = db.query(GroupCriteria).filter_by(group_id=grp.id, name=c_name).first()
                if not gc:
                    gc = GroupCriteria(group_id=grp.id, name=c_name, target_value=target, factor_type=ftype)
                    db.add(gc)
                    db.flush()
                
                # Ikat bobot kriteria ke Sub-Divisi
                exists_weight = db.query(DivisionCriteriaWeight).filter_by(division_id=div.id, group_criteria_id=gc.id).first()
                if not exists_weight:
                    db.add(DivisionCriteriaWeight(division_id=div.id, group_criteria_id=gc.id, weight=weight))
        db.flush()

        # 4. GENERATE ATURAN KENDALA (Constraint)
        print(" -> Menyuntikkan Aturan Mutasi & Lompat Lintas Fungsi...")
        lab_divs = [d for d in div_map.values() if d.group_id == group_map["LAB"].id]
        for div in lab_divs:
            # ATLM bebas masuk Lab
            db.add(DivisionConstraint(division_id=div.id, education_field_id=edu_map["ATLM"].id, constraint_type=ConstraintType.allowed, requires_interview_if_not_native=False))
            # Manajemen Diblokir dari Lab
            db.add(DivisionConstraint(division_id=div.id, education_field_id=edu_map["MNJ"].id, constraint_type=ConstraintType.blocked))
        db.flush()

        # 5. GENERATE KARYAWAN FIKTIF & NILAI KOMPETENSI (SDM Dummy)
        print(" -> Merekrut Karyawan Fiktif & Simulasi Gaji...")
        employees_data = []
        for i in range(1, 16):
            div = random.choice(list(div_map.values()))
            edu = random.choice(list(edu_map.values()))
            emp = Employee(
                employee_code=f"EMP-2026-{i:03d}",
                full_name=f"Karyawan Simulasi {i}",
                division_id=div.id,
                education_field_id=edu.id,
                position="Staf Operasional",
                base_salary=random.choice([4500000, 5200000, 6000000, 7100000]),
                is_active=True,
                has_sanction=False
            )
            db.add(emp)
            db.flush()
            employees_data.append(emp)

            # Suntik Nilai Kompetensi untuk Profile Matching
            criteria_list = db.query(GroupCriteria).filter_by(group_id=div.group_id).all()
            for crit in criteria_list:
                # Random skor 3.0 hingga 5.0
                score = round(random.uniform(3.0, 5.0), 1)
                db.add(EmployeeScore(employee_id=emp.id, criteria_id=crit.id, score=score))
        db.flush()

        # 6. GENERATE SIMULASI BEBAN KERJA (WLA)
        print(" -> Mensimulasikan Kondisi Beban Kerja (WLA) Bulan Ini...")
        current_period = datetime.now().strftime("%Y-%m")
        
        # Skenario 1: Divisi CS Overload (WLA Kritis > 1.5) - Akan memicu peringatan otomatis!
        cs_div = div_map["CS"]
        db.add(WorkloadAnalysis(
            division_id=cs_div.id, period=current_period, 
            total_workload_hours=850.0, total_capacity_hours=480.0, headcount=3,
            wla_value=1.77, is_understaffed=True, is_overstaffed=False, notes="Kekurangan staf CS akibat lonjakan pasien akhir tahun."
        ))

        # Skenario 2: Divisi KLR Optimal (WLA Normal 1.0 - 1.5)
        klr_div = div_map["KLR"]
        db.add(WorkloadAnalysis(
            division_id=klr_div.id, period=current_period, 
            total_workload_hours=600.0, total_capacity_hours=480.0, headcount=3,
            wla_value=1.25, is_understaffed=False, is_overstaffed=False, notes="Kapasitas pemeriksaan lab rutin stabil."
        ))

        # 7. GENERATE PENGGUNA SISTEM (Akun Login)
        print(" -> Membuat Otoritas Akun Login...")
        default_users = [
            ("admin_hrd", "Admin HRD", "hrd123", UserRole.kepala_hrd, None),
            ("admin_cabang", "Kepala Cabang", "cabang123", UserRole.kepala_cabang, None),
            ("admin_divisi", "Kepala Divisi Lab", "divisi123", UserRole.kepala_divisi, div_map["HEM"].id),
        ]
        for uname, fname, pwd, role, div_id in default_users:
            if not db.query(User).filter_by(username=uname).first():
                db.add(User(username=uname, full_name=fname, hashed_password=get_password_hash(pwd), role=role, division_id=div_id))
            user = db.query(User).filter_by(username=uname).first()
            hashed_pwd = get_password_hash(pwd)
            if not user:
                db.add(User(username=uname, full_name=fname, hashed_password=hashed_pwd, role=role, division_id=div_id))
            else:
                # Sinkronisasi ulang password hash agar menggunakan format SHA256+Bcrypt yang baru
                user.hashed_password = hashed_pwd
                user.role = role

        db.commit()
        print("\n=== GENERASI DATABASE BERHASIL ===")
        print("Aplikasi Anda sekarang terisi dengan:")
        print(f" - {len(DIVISIONS)} Divisi Terstruktur")
        print(f" - 15 Karyawan Aktif dengan Riwayat Gaji & Kompetensi")
        print(f" - Skenario WLA Kritis pada Divisi Customer Service")
        print("\nSilakan jalankan aplikasi FastAPI Anda untuk melihat Dasbor yang hidup.")

    except Exception as e:
        db.rollback()
        print(f"\nGAGAL: Terjadi kesalahan fatal: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed()