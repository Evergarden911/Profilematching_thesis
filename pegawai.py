"""
seed_employees_and_scores.py — Seeder Karyawan & Matriks Nilai Kompetensi Pramita Lab
====================================================================================
Menyuntikkan 39 data pegawai riil dari Excel beserta 17 rincian bidang pendidikan,
serta menggenerasi nilai evaluasi (EmployeeScore) adaptif sesuai parameter target divisi.
"""

import sys
import os
import random
from datetime import datetime, timezone
from sqlalchemy.orm import Session

# Uncomment line di bawah jika perlu penyesuaian root path
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.database import SessionLocal
from backend.models import (
    Employee, 
    EmployeeScore, 
    Division, 
    DivisionGroup,
    GroupCriteria, 
    EducationField
)

def seed_employees_and_scores(db: Session):
    print("🌱 Memulai Injeksi Data Karyawan & Generasi Nilai Kompetensi...")

    # =========================================================================
    # 1. DATA MASTER: BIDANG PENDIDIKAN (17 Kategori dari Excel)
    # =========================================================================
    education_fields_data = [
        ("D4 - ANALIS KESEHATAN", "D4-ANAKAT", "Kesehatan"),
        ("D3 - ANALIS KESEHATAN", "D3-ANAKAT", "Kesehatan"),
        ("D3 - KEPERAWATAN", "D3-PERAWAT", "Kesehatan"),
        ("S1 - ILMU HUBUNGAN INTERNASIONAL", "S1-HI", "Sosial & Humaniora"),
        ("D3 - TEKNOLOGI LABORATORIUM MEDIS", "D3-TLM", "Kesehatan"),
        ("SMK - BISNIS DAN MANAJEMEN", "SMK-BM", "Ekonomi & Bisnis"),
        ("S1 - AKUNTANSI", "S1-AKUN", "Ekonomi & Bisnis"),
        ("SMK - TEKNIK PEMESINAN", "SMK-MESIN", "Teknik"),
        ("SMA - IPA", "SMA-IPA", "Umum"),
        ("S1 - KEDOKTERAN", "S1-DOKTER", "Kesehatan"),
        ("D3 - RADIODIAGNOSTIK DAN RADIOTERAPI", "D3-RAD", "Kesehatan"),
        ("SMK - PERHOTELAN", "SMK-HOTEL", "Umum & Pariwisata"),
        ("S1 - KEPERAWATAN / NERS", "S1-NERS", "Kesehatan"),
        ("S1 - KESEHATAN MASYARAKAT", "S1-KESMAS", "Kesehatan"),
        ("SMK - SEKRETARIS", "SMK-SEKRE", "Ekonomi & Bisnis"),
        ("SMK - AKUNTANSI & KEUANGAN LEMBAGA", "SMK-AKUN", "Ekonomi & Bisnis"),
        ("S1 - EKONOMI", "S1-EKONOMI", "Ekonomi & Bisnis"),
    ]

    edu_map = {}
    for name, code, category in education_fields_data:
        edu_obj = db.query(EducationField).filter_by(code=code).first()
        if not edu_obj:
            edu_obj = EducationField(name=name, code=code, category=category, is_active=True)
            db.add(edu_obj)
            db.flush()
            print(f"  [+] Insert Pendidikan: {name} ({code})")
        edu_map[name] = edu_obj.id

    # =========================================================================
    # 2. DATA MASTER: PEGAWAI PRAMITA LAB (39 Pegawai dari Excel)
    # =========================================================================
    # Format: (NIP, NAMA, DIVISI_CODE, POSISI, PENDIDIKAN_TERAKHIR, BASE_SALARY)
    employees_data = [
        ("04.9911.0070", "YONO HARSONO", "SDM-MGR", "Kepala Cabang", "D4 - ANALIS KESEHATAN", 12500000.0),
        ("06.1309.1451", "DEBI DWI PUTRI HENDRIANY", "LAB-PJ", "Manager Pelayanan Medis", "D3 - ANALIS KESEHATAN", 9500000.0),
        ("04.1109.1081", "SAMUEL KRISTIANTO WIBOWO", "EDG-SPV", "Spv. Pelayanan Medis", "D3 - KEPERAWATAN", 7500000.0),
        ("04.0204.0130", "SUTIYONO BIN SARJONO", "LAB-PJ", "Manager Laboratorium", "D4 - ANALIS KESEHATAN", 9500000.0),
        ("04.0307.0168", "BEN MUSTIKA FIRDAUS", "SDM-MGR", "Manager SDM & Umum", "S1 - ILMU HUBUNGAN INTERNASIONAL", 9000000.0),
        ("06.1912.2889", "NISA NURFAIDAH SYA'ADAH", "LAB-SPV", "Spv. Laboratorium", "D3 - TEKNOLOGI LABORATORIUM MEDIS", 7000000.0),
        ("06.1402.1611", "ABDURRAHIM", "GA-SEC", "STAFF (Pramita)", "SMK - BISNIS DAN MANAJEMEN", 4500000.0),
        ("06.2301.3665", "AGIF DWI PANGESTU", "KEU-KSR", "STAFF (Pramita)", "S1 - AKUNTANSI", 4800000.0),
        ("06.1111.1381", "AGUS YUNIOKO", "GA-SEC", "STAFF (Pramita)", "SMK - TEKNIK PEMESINAN", 4500000.0),
        ("06.1408.1694", "ASFIAH NURYATI", "EDG-ECG", "STAFF (Pramita)", "D3 - KEPERAWATAN", 5200000.0),
        ("06.2107.3333", "AYU SHINTA PERMANA", "LAB-ADM", "STAFF (Pramita)", "D3 - TEKNOLOGI LABORATORIUM MEDIS", 4900000.0),
        ("04.0502.0231", "BUDIONO", "GA-SEC", "STAFF (Pramita)", "SMA - IPA", 4500000.0),
        ("06.1310.1452", "DENI ARIANI", "LAB-PJ", "STAFF (Pramita)", "S1 - KEDOKTERAN", 11000000.0),
        ("06.1408.1690", "DWI INDAH LESTARI", "EDG-IMG", "STAFF (Pramita)", "D3 - RADIODIAGNOSTIK DAN RADIOTERAPI", 5300000.0),
        ("06.2112.3461", "ELI FITRIANI", "LAB-HEM", "STAFF (Pramita)", "D3 - ANALIS KESEHATAN", 5000000.0),
        ("06.2110.3407", "FRANSISKA FRIDOLIN WEA", "EDG-IMG", "STAFF (Pramita)", "D3 - RADIODIAGNOSTIK DAN RADIOTERAPI", 5300000.0),
        ("06.2211.3649", "IDCHAM NAUFAL HAVIDZ", "LAB-KIM", "STAFF (Pramita)", "D3 - TEKNOLOGI LABORATORIUM MEDIS", 5000000.0),
        ("06.1405.1695", "ILHAM SEPTIAN", "GA-PBU", "STAFF (Pramita)", "SMK - PERHOTELAN", 4300000.0),
        ("06.1707.2417", "IVAN JATI PRASETYO", "GA-LOG", "STAFF (Pramita)", "SMK - BISNIS DAN MANAJEMEN", 4600000.0),
        ("06.1707.2297", "JENNY ROHMAWATI", "CS-PEL", "STAFF (Pramita)", "D3 - KEPERAWATAN", 4900000.0),
        ("06.2009.2994", "LAILATUL FITRI", "EDG-AUD", "STAFF (Pramita)", "S1 - KEPERAWATAN / NERS", 5400000.0),
        ("06.1509.1982", "M.FADILAH", "GA-PBU", "STAFF (Pramita)", "SMK - BISNIS DAN MANAJEMEN", 4300000.0),
        ("06.1910.2834", "NURUL FITRI GUSTIANAWATI", "LAB-IMM", "STAFF (Pramita)", "D3 - TEKNOLOGI LABORATORIUM MEDIS", 5000000.0),
        ("06.2208.3620", "OKTA NOVANDA VILANO", "EDG-ECHO", "STAFF (Pramita)", "D3 - KEPERAWATAN", 5200000.0),
        ("06.2107.3309", "QUEENTA HEHANUSSA", "CS-PEL", "STAFF (Pramita)", "S1 - KESEHATAN MASYARAKAT", 5000000.0),
        ("06.2107.3335", "RAVINA SEFTIYANINGRUM", "LAB-ADM", "STAFF (Pramita)", "D3 - TEKNOLOGI LABORATORIUM MEDIS", 4900000.0),
        ("06.1611.2220", "RUKMINI", "CS-PEL", "STAFF (Pramita)", "S1 - KEPERAWATAN / NERS", 5100000.0),
        ("06.1210.1382", "RUSLY", "GA-SPR", "STAFF (Pramita)", "SMK - SEKRETARIS", 4500000.0),
        ("06.2506.3923", "SAGIANSYAH RIZKY ZULKARNAIN", "EDG-ECG", "STAFF (Pramita)", "D3 - KEPERAWATAN", 5100000.0),
        ("06.1609.2416", "SANDY", "GA-PBU", "STAFF (Pramita)", "SMK - BISNIS DAN MANAJEMEN", 4300000.0),
        ("06.0707.0427", "SITI MAESAROH", "EDG-AUD", "STAFF (Pramita)", "D3 - KEPERAWATAN", 5300000.0),
        ("06.2011.3049", "SITI NURJANAH", "LAB-RUT", "STAFF (Pramita)", "D3 - TEKNOLOGI LABORATORIUM MEDIS", 5000000.0),
        ("06.0711.0694", "SITI SOLEHA", "GA-PBU", "STAFF (Pramita)", "SMK - AKUNTANSI & KEUANGAN LEMBAGA", 4400000.0),
        ("06.1508.1917", "SUPRIADI", "EDG-IMG", "STAFF (Pramita)", "D3 - RADIODIAGNOSTIK DAN RADIOTERAPI", 5400000.0),
        ("06.1808.2523", "SYARAH MAULIDIYA", "CS-PEL", "STAFF (Pramita)", "S1 - EKONOMI", 4900000.0),
        ("06.1404.1610", "TRIS KIYANAH", "CS-CARE", "STAFF (Pramita)", "S1 - KEPERAWATAN / NERS", 5200000.0),
        ("06.1109.1015", "WILLY DANA KUSUMA", "EDG-IMG", "STAFF (Pramita)", "D3 - RADIODIAGNOSTIK DAN RADIOTERAPI", 5400000.0),
        ("09.0505.0492", "WINDRIAH DIAH WARDANI", "SDM-ADM", "STAFF (Pramita)", "S1 - AKUNTANSI", 4800000.0),
        ("06.1003.1136", "YUNUS", "GA-PBU", "STAFF (Pramita)", "SMK - TEKNIK PEMESINAN", 4300000.0),
    ]

    # Pre-fetch seluruh divisi untuk efisiensi
    divisions_db = {d.code: d for d in db.query(Division).all()}

    total_emp_inserted = 0
    total_emp_updated = 0
    total_scores_upserted = 0

    # =========================================================================
    # 3. PROSES INJEKSI PEGAWAI & GENERASI NILAI
    # =========================================================================
    for nip, name, div_code, position, edu_name, salary in employees_data:
        div_obj = divisions_db.get(div_code)
        if not div_obj:
            print(f"  [!] Peringatan: Divisi kode '{div_code}' untuk pegawai {name} tidak ditemukan. Dilewati.")
            continue

        edu_id = edu_map.get(edu_name)
        if not edu_id:
            print(f"  [!] Peringatan: Pendidikan '{edu_name}' tidak terdaftar.")
            continue

        # A. Upsert Employee
        emp = db.query(Employee).filter_by(employee_code=nip).first()
        if not emp:
            emp = Employee(
                employee_code=nip,
                full_name=name,
                division_id=div_obj.id,
                education_field_id=edu_id,
                position=position,
                base_salary=salary,
                has_sanction=False,
                is_active=True
            )
            db.add(emp)
            db.flush()  # Flush agar emp.id tersedia untuk EmployeeScore
            total_emp_inserted += 1
            print(f"  [+] Insert Karyawan: {name:28} | Divisi: {div_code:8} | NIP: {nip}")
        else:
            emp.full_name = name
            emp.division_id = div_obj.id
            emp.education_field_id = edu_id
            emp.position = position
            emp.base_salary = salary
            emp.is_active = True
            total_emp_updated += 1
            print(f"  [*] Update Karyawan: {name:28} | Divisi: {div_code:8} | NIP: {nip}")

        # B. Generasi Nilai Kompetensi Karyawan (EmployeeScore)
        # Menarik kriteria yang berlaku untuk Rumpun Divisi karyawan ini
        group_criteria_list = db.query(GroupCriteria).filter_by(
            group_id=div_obj.group_id, 
            is_active=True
        ).all()

        for gc in group_criteria_list:
            # Algoritma Generasi Nilai Adaptif berdasarkan Target Value
            if gc.target_value == 5.0:
                # Kriteria positif normal: Nilai acak realistis tinggi (3.8 - 5.0)
                simulated_score = round(random.uniform(3.8, 5.0), 1)
            elif gc.target_value == 1.0:
                # Kriteria negatif / error minimal: Nilai acak mendekati sempurna (1.0 - 1.5)
                simulated_score = round(random.choice([1.0, 1.0, 1.0, 1.2, 1.5]), 1)
            elif gc.target_value == 3.0:
                # Kriteria tengah (misal pengulangan kontrol): Rentang stabil (2.8 - 3.2)
                simulated_score = round(random.uniform(2.8, 3.2), 1)
            elif gc.target_value == 4.0:
                # Kriteria frekuensi harian: Rentang baik (3.8 - 4.5)
                simulated_score = round(random.uniform(3.8, 4.5), 1)
            else:
                simulated_score = gc.target_value

            # Upsert EmployeeScore
            score_record = db.query(EmployeeScore).filter_by(
                employee_id=emp.id,
                criteria_id=gc.id
            ).first()

            if not score_record:
                score_record = EmployeeScore(
                    employee_id=emp.id,
                    criteria_id=gc.id,
                    score=simulated_score
                )
                db.add(score_record)
            else:
                score_record.score = simulated_score
            
            total_scores_upserted += 1

    db.commit()
    print("\n✅ Injeksi Karyawan & Generasi Nilai Selesai!")
    print(f"   - Karyawan baru ditambahkan : {total_emp_inserted}")
    print(f"   - Karyawan diperbarui       : {total_emp_updated}")
    print(f"   - Total rekam nilai (Scores): {total_scores_upserted}")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_employees_and_scores(db)
    except Exception as e:
        db.rollback()
        print(f"❌ Terjadi kesalahan saat seeding: {e}")
    finally:
        db.close()