"""
seed_scores.py — Seeder Nilai Kompetensi (EmployeeScore)
==========================================================
Terpisah dari seed.py secara sengaja: seed.py mengurus struktur data dasar
(divisi, kriteria, karyawan), script ini KHUSUS mengisi nilai kompetensi
untuk kebutuhan testing cepat / demo yang tidak melalui input manual via UI.

Idempotent: aman dijalankan berkali-kali. Karyawan yang sudah punya skor
untuk kriteria grupnya TIDAK ditimpa — hanya kombinasi (employee, criteria)
yang belum ada yang diisi.

Prasyarat: seed.py sudah dijalankan terlebih dahulu (butuh Employee &
GroupCriteria yang sudah ada).

Run:  python seed_scores.py
"""

import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.core.database import SessionLocal
from backend.models import Employee, GroupCriteria, EmployeeScore, Division

SCORE_MIN = 3.0
SCORE_MAX = 5.0


def seed_scores():
    db = SessionLocal()
    try:
        employees = db.query(Employee).filter_by(is_active=True).all()
        if not employees:
            print("Tidak ada Employee ditemukan. Jalankan seed.py terlebih dahulu.")
            return

        # Cache existing (employee_id, criteria_id) pairs agar tidak query berulang per baris
        existing_pairs = {
            (row.employee_id, row.criteria_id)
            for row in db.query(EmployeeScore.employee_id, EmployeeScore.criteria_id).all()
        }

        # Cache kriteria per group_id agar tidak query berulang per karyawan
        group_criteria_cache: dict[int, list[GroupCriteria]] = {}

        inserted = 0
        skipped = 0

        for emp in employees:
            div = db.query(Division).filter_by(id=emp.division_id).first()
            if not div:
                continue

            if div.group_id not in group_criteria_cache:
                group_criteria_cache[div.group_id] = (
                    db.query(GroupCriteria).filter_by(group_id=div.group_id).all()
                )
            criteria_list = group_criteria_cache[div.group_id]

            for crit in criteria_list:
                key = (emp.id, crit.id)
                if key in existing_pairs:
                    skipped += 1
                    continue

                score = round(random.uniform(SCORE_MIN, SCORE_MAX), 1)
                db.add(EmployeeScore(employee_id=emp.id, criteria_id=crit.id, score=score))
                existing_pairs.add(key)
                inserted += 1

        db.commit()
        print("=== SEED SCORES SELESAI ===")
        print(f" - {inserted} nilai baru ditambahkan")
        print(f" - {skipped} nilai sudah ada sebelumnya, dilewati (tidak ditimpa)")

    except Exception as e:
        db.rollback()
        print(f"\nGAGAL: Terjadi kesalahan fatal: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_scores()