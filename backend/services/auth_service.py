from sqlalchemy.orm import Session

from backend.core.security import verify_password
from backend.models import User


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """Return User if credentials are valid, else None."""
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user