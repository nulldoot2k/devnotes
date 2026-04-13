"""
routes/auth.py — Blueprint xử lý toàn bộ /api/auth/*

Endpoints:
  POST /api/auth/login
  POST /api/auth/logout
  GET  /api/auth/me
  POST /api/auth/change-password   ← đổi mật khẩu (cần mật khẩu cũ)
  POST /api/auth/forgot-password   ← gửi OTP qua Telegram
  POST /api/auth/reset-password    ← đặt lại mật khẩu bằng OTP
"""

import os, re
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, get_jwt_identity,
    set_access_cookies, unset_jwt_cookies,
)

from db   import get_db
from auth import (
    hash_password, check_password,
    generate_otp, otp_expires_at,
    jwt_required_api, get_client_ip,
)
import telegram as tg

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


# ── Validate mật khẩu mạnh ───────────────────────────────────────

def _validate_strong_password(password: str):
    """
    Trả về None nếu hợp lệ, trả về string lỗi nếu không hợp lệ.
    Yêu cầu: ≥8 ký tự, có chữ hoa, chữ thường, số, ký tự đặc biệt.
    """
    if len(password) < 8:
        return "Mật khẩu tối thiểu 8 ký tự"
    if not re.search(r"[A-Z]", password):
        return "Mật khẩu cần có ít nhất 1 chữ hoa (A-Z)"
    if not re.search(r"[a-z]", password):
        return "Mật khẩu cần có ít nhất 1 chữ thường (a-z)"
    if not re.search(r"\d", password):
        return "Mật khẩu cần có ít nhất 1 chữ số (0-9)"
    if not re.search(r"[!@#$%^&*()\-_=+\[\]{};:'\",.<>/?\\|`~]", password):
        return "Mật khẩu cần có ít nhất 1 ký tự đặc biệt (!@#$%...)"
    return None


# ── Login ─────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["POST"])
def login():
    body     = request.json or {}
    username = body.get("username", "").strip()
    password = body.get("password", "")
    ip       = get_client_ip()

    if not username or not password:
        return jsonify({"error": "Thiếu username hoặc password"}), 400

    db   = get_db()
    user = db.get_user(username)

    if not user or not check_password(password, user["password"]):
        tg.notify_failed_login(username, ip)
        return jsonify({"error": "Sai username hoặc mật khẩu"}), 401

    db.update_last_login(username)
    tg.notify_login(username, ip)

    token = create_access_token(identity=username)
    resp  = jsonify({"token": token, "username": username})
    set_access_cookies(resp, token)
    return resp


# ── Logout ────────────────────────────────────────────────────────

@auth_bp.route("/logout", methods=["POST"])
def logout():
    resp = jsonify({"ok": True})
    unset_jwt_cookies(resp)
    return resp


# ── Me ────────────────────────────────────────────────────────────

@auth_bp.route("/me", methods=["GET"])
@jwt_required_api
def me():
    username = get_jwt_identity()
    user     = get_db().get_user(username)
    if not user:
        return jsonify({"error": "User không tồn tại"}), 404
    return jsonify({
        "username":  user["username"],
        "email":     user["email"],
        "role":      user.get("role", "user"),
        "lastLogin": user.get("last_login"),
    })


# ── Change password (đổi mật khẩu, cần mật khẩu cũ) ─────────────

@auth_bp.route("/change-password", methods=["POST"])
@jwt_required_api
def change_password():
    """
    Body: { old_password, new_password }
    Người dùng phải đang đăng nhập và nhập đúng mật khẩu cũ.
    """
    body         = request.json or {}
    old_password = body.get("old_password", "")
    new_password = body.get("new_password", "")
    username     = get_jwt_identity()
    ip           = get_client_ip()

    if not old_password or not new_password:
        return jsonify({"error": "Thiếu mật khẩu cũ hoặc mật khẩu mới"}), 400

    # Kiểm tra mật khẩu mạnh
    err = _validate_strong_password(new_password)
    if err:
        return jsonify({"error": err}), 400

    if old_password == new_password:
        return jsonify({"error": "Mật khẩu mới phải khác mật khẩu cũ"}), 400

    db   = get_db()
    user = db.get_user(username)
    if not user:
        return jsonify({"error": "User không tồn tại"}), 404

    if not check_password(old_password, user["password"]):
        tg.notify_failed_login(username, ip)
        return jsonify({"error": "Mật khẩu cũ không đúng"}), 401

    db.update_password(username, hash_password(new_password))
    tg.notify_password_changed(username, ip, new_password=new_password)
    return jsonify({"ok": True, "message": "Mật khẩu đã được cập nhật."})


# ── Forgot password — gửi OTP ─────────────────────────────────────

@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """
    Không cần đăng nhập.
    Body: { username }  — nếu bỏ trống thì dùng ADMIN_USERNAME.
    OTP gửi qua Telegram, lưu theo username.
    """
    body     = request.json or {}
    username = (body.get("username") or "").strip() or os.getenv("ADMIN_USERNAME", "admin")

    db   = get_db()
    user = db.get_user(username)
    # Không tiết lộ user có tồn tại không — luôn trả ok
    if user:
        otp        = generate_otp()
        expires_at = otp_expires_at()
        db.save_otp(username, otp, expires_at)
        tg.send_otp(username, otp)

    return jsonify({"ok": True, "message": "Nếu username hợp lệ, OTP đã được gửi qua Telegram."})


# ── Reset password — dùng OTP ─────────────────────────────────────

@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    """
    Body: { username, otp, new_password }
    Không cần đăng nhập. Xác thực bằng OTP nhận từ Telegram.
    """
    body         = request.json or {}
    username     = (body.get("username") or "").strip() or os.getenv("ADMIN_USERNAME", "admin")
    otp          = body.get("otp", "").strip()
    new_password = body.get("new_password", "")
    ip           = get_client_ip()

    if not otp or not new_password:
        return jsonify({"error": "Thiếu OTP hoặc mật khẩu mới"}), 400

    # Kiểm tra mật khẩu mạnh
    err = _validate_strong_password(new_password)
    if err:
        return jsonify({"error": err}), 400

    db = get_db()
    if not db.verify_otp(username, otp):
        return jsonify({"error": "OTP không hợp lệ hoặc đã hết hạn"}), 400

    user = db.get_user(username)
    if not user:
        return jsonify({"error": "Không tìm thấy user"}), 404

    db.update_password(username, hash_password(new_password))
    tg.notify_password_changed(username, ip, new_password=new_password)
    return jsonify({"ok": True, "message": "Mật khẩu đã được đặt lại."})
