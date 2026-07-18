"""
seed_users.py — Seeder Pengguna Sistem & RBAC Pramita Lab
=========================================================
Membentuk akun standar untuk seluruh hierarki peran:
1. Super Admin (Akses penuh sistem IT)
2. Kepala HRD (Manajemen evaluasi SDM & rotasi)
3. Kepala Cabang (Persetujuan akhir / Executive View)
4. Kepala Divisi / Supervisor (Penilai kinerja sub-divisi masing-masing)
"""

import sys
import os
from sqlalchemy.orm import Session

# Pastikan library passlib sudah terinstal (pip install passlib[bcrypt])
# Jika proyek kamu menggunakan modul keamanan internal, sesuaikan impor di bawah ini
from passlib.context import CryptContext

from backend.core.database import SessionLocal
from backend.models import User, UserRole, Division

# Konfigurasi Hashing Password standar industri (Bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def seed_users(db: Session):
    print("Memulai injeksi data pengguna (Users & RBAC)...")

    # 1. Pemetaan Kode Divisi untuk Peran Kepala Divisi / Supervisor
    # Mengambil referensi dari kode divisi yang diinject pada seeder organisasi
    division_map = {}
    div_codes = ["LAB-PJ", "EDG-SPV", "MKT-MGR", "KEU-MGR", "SDM-MGR", "QA-MGR"]
    
    for code in div_codes:
        div_obj = db.query(Division).filter_by(code=code).first()
        if div_obj:
            division_map[code] = div_obj.id
        else:
            print(f"[Peringatan] Divisi dengan kode '{code}' tidak ditemukan di database.")

    # 2. Definisi Master Pengguna (Username, Password Raw, Full Name, Role, Division Code)
    # Password default set seragam untuk kemudahan testing awal: "Pramita2026!"
    default_password = "Pramita2026!"
    
    users_schema = [
        # --- ROLES TANPA KETERIKATAN DIVISI SPESIFIK ---
        (
            "admin",
            default_password,
            "Administrator Sistem",
            UserRole.super_admin,
            None
        ),
        (
            "head_hrd",
            default_password,
            "Manajer SDM & Kepegawaian",
            UserRole.kepala_hrd,
            None
        ),
        (
            "kacab_kdr",
            default_password,
            "Kepala Cabang Kelapa Dua Raya",
            UserRole.kepala_cabang,
            None
        ),

        # --- ROLES KEPALA DIVISI (TERIKAT PADA SUB-DIVISI / STASIUN KERJA) ---
        (
            "pj_lab",
            default_password,
            "dr. Penanggung Jawab Laboratorium",
            UserRole.kepala_divisi,
            "LAB-PJ"
        ),
        (
            "spv_edg",
            default_password,
            "Supervisor Elektrodiagnostik",
            UserRole.kepala_divisi,
            "EDG-SPV"
        ),
        (
            "mgr_mkt",
            default_password,
            "Manajer Pemasaran & CS",
            UserRole.kepala_divisi,
            "MKT-MGR"
        ),
        (
            "mgr_keu",
            default_password,
            "Manajer Keuangan Cabang",
            UserRole.kepala_divisi,
            "KEU-MGR"
        ),
        (
            "mgr_sdm_ga",
            default_password,
            "Manajer SDM dan Umum Cabang",
            UserRole.kepala_divisi,
            "SDM-MGR"
        ),
        (
            "mgr_qa",
            default_password,
            "Manajer Manajemen Mutu",
            UserRole.kepala_divisi,
            "QA-MGR"
        ),
    ]

    total_inserted = 0
    total_updated = 0

    # 3. Proses Eksekusi Upsert (Insert / Update)
    for username, raw_pwd, full_name, role, div_code in users_schema:
        # Resolusi ID divisi jika user adalah kepala divisi
        target_div_id = division_map.get(div_code) if div_code else None

        # Pengecekan Idempotensi berdasarkan username (Unique Constraint)
        user = db.query(User).filter_by(username=username).first()

        if not user:
            # Hash password hanya saat pembuatan user baru demi efisiensi CPU
            hashed_pwd = get_password_hash(raw_pwd)
            
            new_user = User(
                username=username,
                hashed_password=hashed_pwd,
                full_name=full_name,
                role=role,
                division_id=target_div_id,
                is_active=True
            )
            db.add(new_user)
            total_inserted += 1
            print(f"  [+] Insert User: {username:12} | Role: {role.value:15} | Div ID: {str(target_div_id)}")
        else:
            # Update data metadata (kecuali password agar tidak merubah password yang sudah diganti user)
            user.full_name = full_name
            user.role = role
            user.division_id = target_div_id
            user.is_active = True
            total_updated += 1
            print(f"  [*] Update User: {username:12} | Role: {role.value:15} | Div ID: {str(target_div_id)}")

    db.commit()
    print(f"\nInjeksi data pengguna selesai. Ditambahkan: {total_inserted}, Diperbarui: {total_updated}.")
    print(f"Kredensial default untuk testing -> Password: {default_password}")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_users(db)
    except Exception as e:
        db.rollback()
        print(f"Terjadi kesalahan saat regenerasi users: {e}")
    finally:
        db.close()