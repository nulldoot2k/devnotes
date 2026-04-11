"""
auth.py — Auth helpers: password hash, OTP, JWT wrapper
"""

import os
import random
import string
from datetime import datetime, timedelta
from functools import wraps

import bcrypt
from flask import request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", "10"))


# ── Password ─────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def check_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ── OTP ──────────────────────────────────────────────────────────

def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def otp_expires_at() -> str:
    return (datetime.now() + timedelta(minutes=OTP_EXPIRE_MINUTES)).isoformat()


# ── JWT decorator ────────────────────────────────────────────────

def jwt_required_api(fn):
    """
    Decorator cho API routes — trả JSON 401 thay vì redirect.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return jsonify({"error": "Chưa đăng nhập hoặc token hết hạn"}), 401
        return fn(*args, **kwargs)
    return wrapper


def get_client_ip() -> str:
    """Lấy IP thực của client (qua proxy)."""
    return (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.headers.get("X-Real-IP", "")
        or request.remote_addr
        or "unknown"
    )
