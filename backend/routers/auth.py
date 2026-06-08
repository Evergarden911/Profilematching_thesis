"""
Authentication Router
=====================
Mengelola penerbitan JWT dan pembersihan sesi pengguna.
Mendukung arsitektur Multi-Page Application (MPA) Server-Side Rendering.
"""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm 
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.security import create_access_token, get_password_hash
from backend.models import User
from backend.schemas.token import Token
from backend.schemas.user import UserCreate, UserRead
from backend.services.auth_service import authenticate_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/token", response_model=Token)
def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Autentikasi kredensial pengguna.
    Jika valid, sistem menerbitkan JWT dan menyuntikkannya ke HTTP Cookie
    serta mengembalikan respons JSON resmi.
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kredensial username atau password salah.",
        )
        
    token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(data={"sub": user.username}, expires_delta=token_expires)
    
    # Menyuntikkan token ke dalam HTTP-Only Cookie untuk mengamankan sesi MPA
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,  # Proteksi mutlak dari pembajakan skrip JavaScript (XSS)
        samesite="lax",   # Mitigasi celah keamanan Cross-Site Request Forgery (CSRF)
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=False    # Setel ke True ketika peladen sudah mengimplementasikan sertifikat HTTPS
    )
    
    return Token(access_token=token, token_type="bearer")


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Mendaftarkan akun pengguna baru ke dalam basis data sistem."""
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username telah digunakan oleh staf lain.",
        )
        
    user = User(
        username=payload.username,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        division_id=payload.division_id,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/logout")
def logout(response: Response):
    """
    Menghapus sesi pengguna secara fisik dari memori peramban.
    Mengirimkan instruksi penghapusan cookie akses otentikasi.
    """
    response.delete_cookie(
        key="access_token",
        httponly=True,
        samesite="lax",
        secure=False  # Wajib bernilai sama dengan konfigurasi set_cookie saat login
    )
    return {"status": "success", "message": "Sesi pengguna berhasil dimusnahkan secara aman."}