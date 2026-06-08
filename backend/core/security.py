"""
Pramita Lab — Security & Authorization Core
===========================================
Mengelola enkripsi kata sandi, pembuatan JSON Web Token (JWT), 
serta ekstraksi otentikasi hibrida (Header + Cookie) untuk mendukung MPA.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError, ExpiredSignatureError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.database import get_db
from backend.models import User

# Konfigurasi konteks enkripsi kata sandi menggunakan algoritma bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Skema OAuth2 bawaan tetap dipertahankan untuk dokumentasi Swagger UI (/docs)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Memverifikasi kesocokan antara kata sandi mentah dan hash database."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Mengonversi kata sandi mentah menjadi string hash yang aman."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Menerbitkan token JWT dengan klaim masa kedaluwarsa."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    Algoritma Ekstraksi Token Hibrida (Hybrid Token Resolution)
    -----------------------------------------------------------
    Mengekstrak token JWT dari Authorization Header atau HTTP-Only Cookie.
    Sangat krusial untuk mencegah galat 401/403 pada arsitektur gabungan MPA-CSR.
    """
    token: Optional[str] = None
    
    # Jalur Jalur 1: Memeriksa keberadaan token di dalam HTTP Headers (Standard API Fetch)
    authorization: str = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        
    # Jalur Jalur 2: Jika Header kosong, periksa kuki access_token peramban (MPA Form/Page Link)
    if not token:
        cookie_token = request.cookies.get("access_token")
        if cookie_token:
            # Mengantisipasi jika token di dalam kuki masih membawa awalan string Bearer
            if cookie_token.startswith("Bearer "):
                token = cookie_token.split(" ")[1]
            else:
                token = cookie_token

    # Jika kedua jalur tidak menghasilkan token, hentikan proses sejak awal
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesi otentikasi tidak ditemukan. Silakan masuk kembali ke sistem.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Melakukan dekode token menggunakan kunci rahasia sistem
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Klaim token tidak valid. Subjek pengguna tidak ditemukan.",
            )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesi Anda telah berakhir. Silakan lakukan login ulang.",
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gagal memproses tanda tangan keamanan token.",
        )

    # Validasi integritas data pengguna langsung ke basis data aktual
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kredensial akun tidak terdaftar dalam sistem.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hak akses ditangguhkan. Akun Anda berstatus tidak aktif.",
        )
        
    return user


def require_role(*allowed_roles: str):
    """
    Pemeriksa Otorisasi Berbasis Peran Adaptif (Adaptive RBAC Enforcement)
    -------------------------------------------------------------------
    Menerima parameter berupa peran-peran yang diizinkan untuk mengakses modul API.
    Mendukung pembacaan objek tipe data Enum maupun string murni.
    """
    def role_checker(current_user: User = Depends(get_current_user)):
        # Deteksi otomatis properti untuk mendukung objek SQLAlchemy Enum (.value)
        if current_user.role and hasattr(current_user.role, "value"):
            user_role = current_user.role.value
        else:
            user_role = str(current_user.role)
            
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Akses ditolak. Peran Anda tidak memiliki otoritas untuk memuat modul ini.",
            )
        return current_user
    return role_checker