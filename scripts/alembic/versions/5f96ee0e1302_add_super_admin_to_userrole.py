"""add_super_admin_to_userrole

Revision ID: 5f96ee0e1302
Revises: 1600876603de
Create Date: 2026-07-12 19:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision: str = '5f96ee0e1302'
# Kita hubungkan down_revision ke ID file initial schema milikmu
down_revision: Union[str, None] = '1600876603de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Menambahkan nilai 'super_admin' ke dalam tipe Enum 'userrole' di PostgreSQL.
    
    Logika & Algoritma:
    1. Perintah ALTER TYPE ... ADD VALUE di PostgreSQL menolak dijalankan di dalam 
       blok transaksi standar (BEGIN/COMMIT).
    2. Oleh karena itu, kita harus mengeluarkan eksekusi ini menggunakan 
       op.get_context().autocommit_block().
    3. Klausul IF NOT EXISTS menjamin sifat Idempotent, sehingga tidak error 
       jika dijalankan berulang (Reliability & Safety).
    """
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'super_admin'")


def downgrade() -> None:
    """
    Logika Downgrade:
    Sengaja dibiarkan no-op (pass). PostgreSQL tidak memiliki sintaks 'DROP VALUE' 
    untuk ENUM. Melakukan re-create type dan table lock berisiko tinggi terhadap 
    availability sistem dan integritas data (Disaster Recovery & Availability).
    """
    pass