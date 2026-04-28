"""
utils/auth_utils.py — Auth helpers: hash mật khẩu, OTP, JWT decorator
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Đổi tên từ auth.py → utils/auth_utils.py để tránh nhầm với routes/auth.py
"""

import random
import string
from datetime import datetime, timedelta
from functools import wraps

import bcrypt
from flask import request, jsonify
from flask_jwt_extended import verify_jwt_in_request

from config import settings


# ── Password ──────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash mật khẩu bằng bcrypt."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def check_password(plain: str, hashed: str) -> bool:
    """Kiểm tra mật khẩu có khớp hash không."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ── OTP ───────────────────────────────────────────────────────────

def generate_otp(length: int = 6) -> str:
    """Tạo mã OTP gồm các chữ số ngẫu nhiên."""
    return "".join(random.choices(string.digits, k=length))


def otp_expires_at() -> str:
    """Trả về thời điểm hết hạn OTP dạng ISO string."""
    return (datetime.now() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)).isoformat()


# ── JWT decorator ─────────────────────────────────────────────────

def jwt_required_api(fn):
    """
    Decorator cho API routes.
    Trả JSON 401 thay vì redirect về trang login.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return jsonify({"error": "Chưa đăng nhập hoặc token hết hạn"}), 401
        return fn(*args, **kwargs)
    return wrapper


# ── Client IP ─────────────────────────────────────────────────────

def get_client_ip() -> str:
    """Lấy IP thực của client, hỗ trợ cả reverse proxy."""
    return (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.headers.get("X-Real-IP", "")
        or request.remote_addr
        or "unknown"
    )
