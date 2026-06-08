from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# 1. Resolve the absolute path to the project root.
# __file__ is config.py. .parents[2] traverses up: core -> backend -> root
ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE_PATH = ROOT_DIR / ".env"

class Settings(BaseSettings):
    # No defaults — app crashes at startup with a clear ValidationError if missing.
    DATABASE_URL: str
    SECRET_KEY: str

    # Safe to default: non-secret, well-known algorithm identifier.
    ALGORITHM: str = "HS256"
    # Safe to default: controls token expiry, not a credential.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    # When True, runs create_all on startup. Keep False until DB is ready for tables.
    DB_INIT_ON_STARTUP: bool = False
    
    # 2. Use Pydantic V2 syntax and bind explicitly to the absolute path
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()