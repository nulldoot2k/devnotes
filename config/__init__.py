"""
config/__init__.py — Cấu hình tập trung toàn bộ app
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tất cả biến môi trường đọc từ .env đều tập trung ở đây.
Các module khác chỉ cần: from config import settings
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


class Settings:
    # ── Flask ──────────────────────────────────────────────────
    SECRET_KEY: str       = os.getenv("FLASK_SECRET_KEY", "dev-secret")
    JWT_SECRET_KEY: str   = os.getenv("JWT_SECRET_KEY",   "jwt-secret")
    JWT_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "12"))
    DEBUG: bool           = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    PORT: int             = int(os.getenv("PORT", "5000"))

    # ── Admin ──────────────────────────────────────────────────
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "changeme123")
    ADMIN_EMAIL: str    = os.getenv("ADMIN_EMAIL",    "admin@devnotes.local")

    # ── Database ───────────────────────────────────────────────
    DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()
    MONGO_URI: str    = os.getenv("MONGO_URI",    "").strip()
    MONGO_DB: str     = os.getenv("MONGO_DB",     "devnotes")
    OWNER_MODE: str   = os.getenv("OWNER_MODE",   "single")  # "single" | "multi"

    # Đường dẫn file SQLite
    DATA_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path  = DATA_DIR / "devnotes.db"
    JSON_PATH: Path = DATA_DIR / "notes.json"

    # ── Telegram ───────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str   = os.getenv("TELEGRAM_CHAT_ID",   "")
    TELEGRAM_THREAD_ID: str = os.getenv("TELEGRAM_THREAD_ID", "")
    APP_NAME: str           = os.getenv("APP_NAME", "DevNotes")

    # ── OTP ────────────────────────────────────────────────────
    OTP_EXPIRE_MINUTES: int = int(os.getenv("OTP_EXPIRE_MINUTES", "10"))

    # ── Images ─────────────────────────────────────────────────
    TEMP_DIR: Path          = BASE_DIR / "temp"
    MAX_IMAGE_BYTES: int    = int(os.getenv("MAX_IMAGE_BYTES", str(10 * 1024 * 1024)))
    IMAGE_CACHE_TTL: int    = int(os.getenv("IMAGE_CACHE_TTL_MINUTES", "120"))

    # ── Rate limiting ──────────────────────────────────────────
    RATELIMIT_STORAGE_URI: str = os.getenv("RATELIMIT_STORAGE_URI", "memory://")

    # ── Tự động detect loại DB ─────────────────────────────────
    @property
    def USE_MONGO(self) -> bool:
        return bool(self.MONGO_URI)

    @property
    def USE_POSTGRES(self) -> bool:
        return not self.USE_MONGO and self.DATABASE_URL.startswith(("postgresql://", "postgres://"))

    @property
    def USE_MYSQL(self) -> bool:
        return not self.USE_MONGO and self.DATABASE_URL.startswith(("mysql://", "mysql+pymysql://"))

    @property
    def USE_SQLITE(self) -> bool:
        return not (self.USE_MONGO or self.USE_POSTGRES or self.USE_MYSQL)


settings = Settings()

# Đảm bảo thư mục data/ và temp/ tồn tại
settings.DATA_DIR.mkdir(exist_ok=True)
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
