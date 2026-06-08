from backend.core.database import SessionLocal
from backend.models import User, UserRole
from backend.core.security import get_password_hash

def reset_test_accounts():
    db = SessionLocal()
    
    # Daftar akun pengujian standar untuk TA Anda.
    # Semua kata sandi akan diatur ulang menjadi: password123
    test_users = [
        {"username": "hrd", "password": "password123", "role": UserRole.kepala_hrd, "name": "Kepala HRD Pusat"},
        {"username": "divisi", "password": "password123", "role": UserRole.kepala_divisi, "name": "Kepala Divisi Lab"},
        {"username": "cabang", "password": "password123", "role": UserRole.kepala_cabang, "name": "Kepala Cabang Utama"},
    ]

    try:
        for data in test_users:
            user = db.query(User).filter(User.username == data["username"]).first()
            new_hash = get_password_hash(data["password"])
            
            if user:
                user.hashed_password = new_hash
                user.role = data["role"]
                user.is_active = True
                print(f"[UPDATE] Akun '{data['username']}' diperbarui. Sandi: {data['password']}")
            else:
                new_user = User(
                    username=data["username"],
                    hashed_password=new_hash,
                    full_name=data["name"],
                    role=data["role"],
                    division_id=1,  # Asumsi ID Divisi default
                    is_active=True
                )
                db.add(new_user)
                print(f"[BUAT BARU] Akun '{data['username']}' dibuat. Sandi: {data['password']}")

        db.commit()
        print("\nSelesai! Basis data berhasil disinkronisasi dengan algoritma enkripsi baru.")
    except Exception as e:
        db.rollback()
        print(f"Gagal memproses data: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_test_accounts()