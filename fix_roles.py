from backend.core.database import SessionLocal
from backend.models import User, UserRole

def assign_roles():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        if not users:
            print("Tidak ada pengguna di database.")
            return

        print(f"Ditemukan {len(users)} pengguna. Mulai memperbarui hak akses...")
        
        # Asumsi: Kita membagi role berdasarkan ID atau urutan untuk testing
        for i, user in enumerate(users):
            if i == 0:
                user.role = UserRole.kepala_hrd
                print(f"User {user.username} -> KEPALA HRD")
            elif i == 1:
                user.role = UserRole.kepala_cabang
                print(f"User {user.username} -> KEPALA CABANG")
            else:
                user.role = UserRole.kepala_divisi
                print(f"User {user.username} -> KEPALA DIVISI")
        
        db.commit()
        print("Pembaruan Role Berhasil!")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    assign_roles()