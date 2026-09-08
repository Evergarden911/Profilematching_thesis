"""
seed_org_and_criteria.py — Seeder Master Terintegrasi Pramita Lab (REVISI)
==========================================================================
Menyuntikkan data:
1. Rumpun Divisi Besar (DivisionGroup) beserta bobot standar CF/SF
2. Sub-Divisi Aktual / Stasiun Kerja (Division) beserta kode unik & budget awal
3. Kriteria Penilaian (GroupCriteria) sesuai 5 Rumpun Divisi dari Excel
4. Bobot Kriteria per Sub-Divisi (DivisionCriteriaWeight)

PERBAIKAN:
- Menambahkan parameter `container_type` ("individual" atau "additional").
- Normalisasi bobot matematis: Total Kinerja Individu = 1.0, Total Kinerja Tambahan = 1.0.
- Kriteria spesifik divisi disesuaikan dengan konteks operasional nyata (bukan sekadar copy-paste).
"""

import sys
import os
from sqlalchemy.orm import Session

# Uncomment line di bawah jika perlu penyesuaian root path
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.database import SessionLocal
from backend.models import (
    DivisionGroup, 
    Division, 
    GroupCriteria, 
    DivisionCriteriaWeight, 
    FactorType
)

def seed_master(db: Session):
    print("🌱 Memulai Seeder Terintegrasi Pramita Lab (ORM Models Terbaru)...")

    # ==========================================
    # 1. DATA MASTER: STRUKTUR ORGANISASI
    # ==========================================
    org_data = {
        "LABORATORIUM": {
            "code": "LAB",
            "cf_weight": 0.60,
            "sf_weight": 0.40,
            "divisions": [
                ("Penanggung Jawab Laboratorium", "LAB-PJ"),
                ("Supervisor Teknis Laboratorium", "LAB-SPV"),
                ("Pelaksana Administrasi Laboratorium", "LAB-ADM"),
                ("Pelaksana Analis Hematologi", "LAB-HEM"),
                ("Pelaksana Analis Immunologi", "LAB-IMM"),
                ("Pelaksana Analis Kimia Klinik", "LAB-KIM"),
                ("Pelaksana Analis Kimia Rutin", "LAB-RUT"),
                ("Pelaksana Pencatatan Sampel", "LAB-CAT"),
                ("Pelaksana Sampling", "LAB-SMP"),
            ]
        },
        "ELEKTRODIAGNOSTIK": {
            "code": "EDG",
            "cf_weight": 0.60,
            "sf_weight": 0.40,
            "divisions": [
                ("Supervisor Elektrodiagnostik", "EDG-SPV"),
                ("Pelaksana Pemeriksaan ECG & Treadmill", "EDG-ECG"),
                ("Pelaksana Pemeriksaan Audiogram & Spirometri", "EDG-AUD"),
                ("Pelaksana Pendampingan Echocardiografi", "EDG-ECHO"),
                ("Pelaksana Verifikasi & Imaging Elektrodiagnostik", "EDG-IMG"),
            ]
        },
        "CUSTOMER SERVICE": {
            "code": "MKT-CS",
            "cf_weight": 0.60,
            "sf_weight": 0.40,
            "divisions": [
                ("Manajer / Wakil Manajer Pemasaran", "MKT-MGR"),
                ("Supervisor Customer Service", "CS-SPV"),
                ("Supervisor Pemasaran", "MKT-SPV"),
                ("Pelaksana Customer Service", "CS-PEL"),
                ("Pelaksana Customer Care", "CS-CARE"),
                ("Pelaksana Pemasaran Medis", "MKT-MED"),
                ("Pelaksana Pemasaran Instansi", "MKT-INS"),
                ("Pelaksana Pemasaran Rujukan", "MKT-RUJ"),
                ("Pelaksana Markom", "MKT-KOM"),
                ("Pelaksana Admin Pemasaran", "MKT-ADM"),
            ]
        },
        "KEUANGAN": {
            "code": "KEU",
            "cf_weight": 0.60,
            "sf_weight": 0.40,
            "divisions": [
                ("Manajer Keuangan", "KEU-MGR"),
                ("Pelaksana Kasir Utama", "KEU-KSR"),
                ("Pelaksana Administrasi Keuangan & Bank", "KEU-ADM"),
            ]
        },
        "SDM & UMUM": {
            "code": "SDM-GA",
            "cf_weight": 0.60,
            "sf_weight": 0.40,
            "divisions": [
                ("Manajer SDM dan Umum", "SDM-MGR"),
                ("Manajer Mutu", "QA-MGR"),
                ("Pelaksana Admin SDM dan Umum", "SDM-ADM"),
                ("Pelaksana Pengendali Dokumen", "QA-DOK"),
                ("Pelaksana Logistik", "GA-LOG"),
                ("Pelaksana Supir", "GA-SPR"),
                ("Pelaksana Pembantu Umum", "GA-PBU"),
                ("Pelaksana Keamanan", "GA-SEC"),
            ]
        }
    }

    # ==========================================
    # 2. DATA MASTER: KRITERIA (DIPERBAIKI)
    # ==========================================
    # Format Baru: ("Nama", Target, FactorType, Bobot, "container_type")
    # Syarat Mutlak: Total Bobot Kinerja Individu = 1.0, Total Kinerja Tambahan = 1.0
    criteria_data = {
        "LABORATORIUM": [
            # KINERJA INDIVIDU (Total = 1.0)
            ("Index Kepuasan Pelanggan", 5.0, FactorType.core, 0.15, "individual"),
            ("Turn Around Time proses Lab IVD", 5.0, FactorType.core, 0.15, "individual"),
            ("OTP Hasil Pemeriksaan Lab IVD", 5.0, FactorType.core, 0.20, "individual"),
            ("Kuantitas pekerjaan analisa", 5.0, FactorType.core, 0.10, "individual"),
            ("Kesesuaian penyimpanan spesimen", 5.0, FactorType.core, 0.10, "individual"),
            ("Tingkat Ketidaksesuaian hasil pemeriksaan", 1.0, FactorType.core, 0.10, "individual"),
            ("Pencapaian waktu pembelajaran", 1.0, FactorType.secondary, 0.10, "individual"),
            ("Kepatuhan penggunaan APD", 5.0, FactorType.secondary, 0.10, "individual"),
            
            # KINERJA TAMBAHAN / TIM (Total = 1.0)
            ("Realisasi kegiatan control lingkungan", 5.0, FactorType.core, 0.40, "additional"),
            ("Kesesuaian pemilahan limbah padat", 5.0, FactorType.core, 0.30, "additional"),
            ("Inisiatif Pemeliharaan Alat Lab", 5.0, FactorType.secondary, 0.30, "additional"),
        ],
        "ELEKTRODIAGNOSTIK": [
            # KINERJA INDIVIDU (Total = 1.0)
            ("TTR Hasil pemeriksaan Elektrodiagnostik", 5.0, FactorType.core, 0.20, "individual"),
            ("Pencapaian target waktu tunggu walk-in", 5.0, FactorType.core, 0.20, "individual"),
            ("Kuantitas pemeriksaan terpadu", 5.0, FactorType.core, 0.20, "individual"),
            ("Tingkat ketidaksesuaian imaging/rekaman", 1.0, FactorType.core, 0.15, "individual"),
            ("Pengulangan pemeriksaan", 1.0, FactorType.core, 0.15, "individual"),
            ("Pencapaian waktu pembelajaran", 1.0, FactorType.secondary, 0.10, "individual"),
            
            # KINERJA TAMBAHAN / TIM (Total = 1.0)
            ("Realisasi kegiatan pemeliharaan alat", 5.0, FactorType.core, 0.40, "additional"),
            ("Kuantitas pendampingan medis", 5.0, FactorType.core, 0.40, "additional"),
            ("Kepatuhan kebersihan & APD", 5.0, FactorType.secondary, 0.20, "additional"),
        ],
        "CUSTOMER SERVICE": [
            # KINERJA INDIVIDU (Total = 1.0)
            ("Index Kepuasan Pelanggan", 5.0, FactorType.core, 0.30, "individual"),
            ("Tingkat Resolusi Komplain Pertama", 5.0, FactorType.core, 0.30, "individual"),
            ("Kecepatan Respon Pelayanan (SLA)", 5.0, FactorType.core, 0.20, "individual"),
            ("Tingkat Kesalahan Edukasi Layanan", 1.0, FactorType.secondary, 0.10, "individual"),
            ("Pencapaian waktu pembelajaran", 1.0, FactorType.secondary, 0.10, "individual"),
            
            # KINERJA TAMBAHAN / TIM (Total = 1.0)
            ("Pencapaian Target Cross-Selling", 5.0, FactorType.core, 0.50, "additional"),
            ("Akuisisi Pelanggan Baru / Instansi", 5.0, FactorType.core, 0.30, "additional"),
            ("Inisiatif Kolaborasi Antar Divisi", 5.0, FactorType.secondary, 0.20, "additional"),
        ],
        "KEUANGAN": [
            # KINERJA INDIVIDU (Total = 1.0)
            ("Kebenaran Laporan Harian Kasir & Posisi Kas", 5.0, FactorType.core, 0.30, "individual"),
            ("Kebenaran laporan mutasi Bank", 5.0, FactorType.core, 0.30, "individual"),
            ("Ketepatan waktu penyajian laporan", 5.0, FactorType.core, 0.20, "individual"),
            ("Akurasi Cash Count Harian", 4.0, FactorType.secondary, 0.10, "individual"),
            ("Pencapaian waktu pembelajaran", 1.0, FactorType.secondary, 0.10, "individual"),
            
            # KINERJA TAMBAHAN / TIM (Total = 1.0)
            ("Efisiensi Biaya Operasional Cabang", 5.0, FactorType.core, 0.50, "additional"),
            ("Ketepatan pembayaran installment Pusat", 5.0, FactorType.core, 0.30, "additional"),
            ("Dukungan Audit Internal/Eksternal", 5.0, FactorType.secondary, 0.20, "additional"),
        ],
        "SDM & UMUM": [
            # KINERJA INDIVIDU (Total = 1.0)
            ("Ketertiban Administrasi dan Laporan", 5.0, FactorType.core, 0.25, "individual"),
            ("Tingkat Kesesuaian administrasi kepegawaian", 5.0, FactorType.core, 0.25, "individual"),
            ("Tingkat kesesuaian administrasi fix asset", 5.0, FactorType.core, 0.20, "individual"),
            ("Tingkat ketepatan laporan BPJS/DPLK", 5.0, FactorType.core, 0.20, "individual"),
            ("Pencapaian waktu pembelajaran", 1.0, FactorType.secondary, 0.10, "individual"),
            
            # KINERJA TAMBAHAN / TIM (Total = 1.0)
            ("Kecepatan Pemenuhan Kebutuhan SDM", 5.0, FactorType.core, 0.40, "additional"),
            ("Tingkat Turn-Over Karyawan (Retensi)", 1.0, FactorType.core, 0.40, "additional"),
            ("Inisiatif Program Employee Engagement", 5.0, FactorType.secondary, 0.20, "additional"),
        ]
    }

    # ==========================================
    # 3. PROSES INJEKSI KE DATABASE
    # ==========================================
    for grp_name, grp_info in org_data.items():
        print(f"\n📁 Memproses DivisionGroup: {grp_name} ({grp_info['code']})")
        
        # A. Upsert DivisionGroup
        div_group = db.query(DivisionGroup).filter_by(code=grp_info['code']).first()
        if not div_group:
            div_group = DivisionGroup(
                name=grp_name,
                code=grp_info['code'],
                cf_weight=grp_info['cf_weight'],
                sf_weight=grp_info['sf_weight'],
                description=f"Rumpun Divisi {grp_name} Pramita Lab"
            )
            db.add(div_group)
            db.flush()
            print(f"  [+] Insert Rumpun Divisi: {grp_name}")
        else:
            div_group.name = grp_name
            div_group.cf_weight = grp_info['cf_weight']
            div_group.sf_weight = grp_info['sf_weight']
            print(f"  [*] Update Rumpun Divisi: {grp_name}")

        # B. Upsert Sub-Divisions (Divisions)
        active_divisions = []
        for div_name, div_code in grp_info['divisions']:
            division = db.query(Division).filter_by(code=div_code).first()
            if not division:
                division = Division(
                    name=div_name,
                    code=div_code,
                    group_id=div_group.id,
                    monthly_budget=5000000.0  # Default budget operasional bulanan
                )
                db.add(division)
                db.flush()
                print(f"    ├── [+] Insert Sub-Divisi: {div_name} ({div_code})")
            else:
                division.name = div_name
                division.group_id = div_group.id
                print(f"    ├── [*] Update Sub-Divisi: {div_name} ({div_code})")
            
            active_divisions.append(division)

        # C. Upsert GroupCriteria & DivisionCriteriaWeight
        criteria_list = criteria_data.get(grp_name, [])
        for crit_name, target, ftype, weight, ctype in criteria_list:
            # Upsert GroupCriteria
            gc = db.query(GroupCriteria).filter_by(
                group_id=div_group.id, 
                name=crit_name
            ).first()

            if not gc:
                gc = GroupCriteria(
                    group_id=div_group.id,
                    name=crit_name,
                    target_value=target,
                    factor_type=ftype,
                    container_type=ctype, # <-- INJEKSI CONTAINER TYPE BARU
                    description=f"Parameter {ftype.value} untuk {grp_name}"
                )
                db.add(gc)
                db.flush()
            else:
                gc.target_value = target
                gc.factor_type = ftype
                gc.container_type = ctype # <-- UPDATE JIKA SUDAH ADA
                db.flush()

            # Bind bobot (DivisionCriteriaWeight) ke setiap Sub-Divisi di bawah rumpun ini
            for div_obj in active_divisions:
                div_weight = db.query(DivisionCriteriaWeight).filter_by(
                    division_id=div_obj.id,
                    group_criteria_id=gc.id
                ).first()

                if not div_weight:
                    div_weight = DivisionCriteriaWeight(
                        division_id=div_obj.id,
                        group_criteria_id=gc.id,
                        weight=weight
                    )
                    db.add(div_weight)
                else:
                    div_weight.weight = weight

    db.commit()
    print("\n✅ Seeder Master Terintegrasi Selesai Dijalankan!")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_master(db)
    except Exception as e:
        db.rollback()
        print(f"❌ Terjadi kesalahan: {e}")
    finally:
        db.close()
