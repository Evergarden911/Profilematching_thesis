"""
seed_org_and_criteria.py — Seeder Master Terintegrasi Pramita Lab
=================================================================
Menyuntikkan data:
1. Rumpun Divisi Besar (DivisionGroup) beserta bobot standar CF/SF
2. Sub-Divisi Aktual / Stasiun Kerja (Division) beserta kode unik & budget awal
3. Kriteria Penilaian (GroupCriteria) sesuai 5 Rumpun Divisi dari Excel
4. Bobot Kriteria per Sub-Divisi (DivisionCriteriaWeight)
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
    # Format: "NAMA GRUP": {"code": "KODE_GRUP", "divisions": [ ("Nama Sub-Divisi", "KODE_SUB"), ... ]}
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
    # 2. DATA MASTER: KRITERIA (FROM EXCEL)
    # ==========================================
    criteria_data = {
        "LABORATORIUM": [
            ("Index Kepuasan Pelanggan", 5.0, FactorType.core, 0.05),
            ("Turn Around Time proses Lab IVD", 5.0, FactorType.core, 0.05),
            ("OTP Hasil Pemeriksaan Lab IVD", 5.0, FactorType.core, 0.10),
            ("Kuantitas pekerjaan analisa", 5.0, FactorType.core, 0.10),
            ("Kesesuaian penyimpanan spesimen", 5.0, FactorType.core, 0.05),
            ("Kepatuhan pelaporan hasil kritis", 5.0, FactorType.core, 0.05),
            ("Kepatuhan Identifikasi pasien/spesimen", 5.0, FactorType.core, 0.05),
            ("Tingkat ketidaksesuaian spesimen", 1.0, FactorType.core, 0.05),
            ("Kejadian sample/spesimen hilang atau rusak", 1.0, FactorType.core, 0.05),
            ("Pengulangan pemeriksaan bahan kontrol", 3.0, FactorType.core, 0.05),
            ("Tingkat Ketidaksesuaian hasil pemeriksaan", 1.0, FactorType.core, 0.10),
            ("Tingkat realisasi program maintenance alat", 5.0, FactorType.core, 0.05),
            ("Pengulangan pemeriksaan", 4.0, FactorType.core, 0.05),
            ("Pencapaian waktu pembelajaran", 1.0, FactorType.secondary, 0.05),
            ("Realisasi kegiatan control lingkungan", 5.0, FactorType.secondary, 0.02),
            ("Kepatuhan kebersihan tangan", 5.0, FactorType.secondary, 0.03),
            ("Kepatuhan penggunaan APD", 5.0, FactorType.secondary, 0.04),
            ("Tingkat ketidaksesuaian proses administratif", 1.0, FactorType.secondary, 0.03),
            ("Kesesuaian pemilahan limbah padat", 5.0, FactorType.secondary, 0.03),
        ],
        "ELEKTRODIAGNOSTIK": [
            ("TTR Hasil pemeriksaan Elektrodiagnostik", 5.0, FactorType.core, 0.05),
            ("Pencapaian target waktu tunggu walk-in", 5.0, FactorType.core, 0.05),
            ("Waktu tunggu pelayanan elektrodiagnostik walk-in", 5.0, FactorType.core, 0.05),
            ("OTP Hasil Elektrodiagnostik", 5.0, FactorType.core, 0.05),
            ("Performance layanan pelanggan individual", 5.0, FactorType.core, 0.04),
            ("TTR pengambilan spesimen", 5.0, FactorType.core, 0.04),
            ("Tingkat kesesuaian output verifikasi spesimen", 5.0, FactorType.core, 0.04),
            ("TTR verifikasi spesimen", 5.0, FactorType.core, 0.04),
            ("TAT waktu tunggu Pemeriksaan ECG", 5.0, FactorType.core, 0.04),
            ("TAT waktu tunggu Pemeriksaan Audiogram", 5.0, FactorType.core, 0.04),
            ("TAT waktu tunggu Pemeriksaan Spirometri", 5.0, FactorType.core, 0.04),
            ("Kuantitas pemeriksaan ECG", 5.0, FactorType.core, 0.04),
            ("Kuantitas pemeriksaan Audiogram", 5.0, FactorType.core, 0.04),
            ("Kuantitas pemeriksaan Spirometri", 5.0, FactorType.core, 0.04),
            ("TAT proses elektrodiagnostik", 5.0, FactorType.core, 0.04),
            ("Tingkat ketidaksesuaian imaging/rekaman", 1.0, FactorType.core, 0.04),
            ("Pengulangan pemeriksaan", 1.0, FactorType.core, 0.04),
            ("Rata-rata tingkat utilitas alat Elektrodiagnostik", 5.0, FactorType.core, 0.04),
            ("Pencapaian waktu pembelajaran", 1.0, FactorType.secondary, 0.02),
            ("Realisasi kegiatan pemeliharaan alat", 5.0, FactorType.secondary, 0.04),
            ("Realisasi kegiatan control lingkungan", 5.0, FactorType.secondary, 0.04),
            ("Kuantitas pendampingan treadmill", 5.0, FactorType.secondary, 0.04),
            ("Kuantitas pendampingan Echocardiografi", 5.0, FactorType.secondary, 0.04),
            ("Kepatuhan kebersihan tangan", 5.0, FactorType.secondary, 0.02),
            ("Kepatuhan penggunaan APD", 5.0, FactorType.secondary, 0.02),
            ("Kesesuaian pemilahan limbah padat", 5.0, FactorType.secondary, 0.02),
        ],
        "CUSTOMER SERVICE": [
            ("Index Kepuasan Pelanggan", 5.0, FactorType.core, 0.05),
            ("Turn Around Time proses Lab IVD", 5.0, FactorType.core, 0.05),
            ("OTP Hasil Pemeriksaan Lab IVD", 5.0, FactorType.core, 0.10),
            ("Kuantitas pekerjaan analisa", 5.0, FactorType.core, 0.10),
            ("Kesesuaian penyimpanan spesimen", 5.0, FactorType.core, 0.05),
            ("Kepatuhan pelaporan hasil kritis", 5.0, FactorType.core, 0.05),
            ("Kepatuhan Identifikasi pasien/spesimen", 5.0, FactorType.core, 0.05),
            ("Tingkat ketidaksesuaian spesimen", 1.0, FactorType.core, 0.05),
            ("Kejadian sample/spesimen hilang atau rusak", 1.0, FactorType.core, 0.05),
            ("Pengulangan pemeriksaan bahan kontrol", 3.0, FactorType.core, 0.05),
            ("Tingkat Ketidaksesuaian hasil pemeriksaan", 1.0, FactorType.core, 0.10),
            ("Tingkat realisasi program maintenance alat", 5.0, FactorType.core, 0.05),
            ("Pengulangan pemeriksaan", 4.0, FactorType.core, 0.05),
            ("Pencapaian waktu pembelajaran", 1.0, FactorType.secondary, 0.05),
            ("Realisasi kegiatan control lingkungan", 5.0, FactorType.secondary, 0.02),
            ("Kepatuhan kebersihan tangan", 5.0, FactorType.secondary, 0.03),
            ("Kepatuhan penggunaan APD", 5.0, FactorType.secondary, 0.04),
            ("Tingkat ketidaksesuaian proses administratif", 1.0, FactorType.secondary, 0.03),
            ("Kesesuaian pemilahan limbah padat", 5.0, FactorType.secondary, 0.03),
        ],
        "KEUANGAN": [
            ("Cash Count (frekuensi)", 4.0, FactorType.core, 0.15),
            ("Penyajian Laporan Harian Kasir", 5.0, FactorType.core, 0.10),
            ("Kebenaran Laporan Harian Kasir & Posisi Kas", 5.0, FactorType.core, 0.15),
            ("Ketepatan penyajian laporan mutasi Bank", 5.0, FactorType.core, 0.10),
            ("Kebenaran laporan mutasi Bank", 5.0, FactorType.core, 0.10),
            ("Pencapaian waktu pembelajaran", 1.0, FactorType.secondary, 0.10),
            ("Penyajian Laporan Harian Tunai Kantor Pusat", 5.0, FactorType.secondary, 0.10),
            ("Ketepatan pembayaran installment Kantor Pusat", 5.0, FactorType.secondary, 0.10),
            ("Penyajian laporan progress instalment Kantor Pusat", 5.0, FactorType.secondary, 0.10),
        ],
        "SDM & UMUM": [
            ("Ketertiban Administrasi dan Laporan", 5.0, FactorType.core, 0.15),
            ("Tingkat kesesuaian administrasi barang fix asset", 5.0, FactorType.core, 0.15),
            ("Tingkat Kesesuaian stock opname Fix Asset", 5.0, FactorType.core, 0.15),
            ("Tingkat Kesesuaian administrasi kepegawaian (ACK)", 5.0, FactorType.core, 0.20),
            ("Tingkat ketepatan laporan BPJS/DPLK", 5.0, FactorType.core, 0.15),
            ("Pencapaian waktu pembelajaran", 1.0, FactorType.secondary, 0.10),
            ("Kesesuaian Pengelolaan Surat Masuk dan Keluar", 5.0, FactorType.secondary, 0.10),
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
        for crit_name, target, ftype, weight in criteria_list:
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
                    description=f"Parameter {ftype.value} untuk {grp_name}"
                )
                db.add(gc)
                db.flush()
            else:
                gc.target_value = target
                gc.factor_type = ftype

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