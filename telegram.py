"""
telegram.py — Gửi thông báo qua Telegram Bot
"""

import os
import requests
from datetime import datetime

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID",   "")
THREAD_ID = os.getenv("TELEGRAM_THREAD_ID", "")
APP_NAME  = os.getenv("APP_NAME", "DevNotes")


def _send(text: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print(f"[Telegram] Chưa cấu hình bot. Message: {text}")
        return False
    payload = {
        "chat_id":    CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
    }
    if THREAD_ID:
        payload["message_thread_id"] = THREAD_ID
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json=payload,
            timeout=5,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[Telegram] Lỗi gửi: {e}")
        return False


def _ts() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def notify_login(username: str, ip: str = "unknown"):
    _send(
        f"🔐 <b>{APP_NAME} — Đăng nhập</b>\n"
        f"👤 User: <code>{username}</code>\n"
        f"🌐 IP: <code>{ip}</code>\n"
        f"🕐 {_ts()}"
    )


def notify_failed_login(username: str, ip: str = "unknown"):
    _send(
        f"⚠️ <b>{APP_NAME} — Đăng nhập thất bại</b>\n"
        f"👤 User: <code>{username}</code>\n"
        f"🌐 IP: <code>{ip}</code>\n"
        f"🕐 {_ts()}"
    )


def send_otp(username: str, otp: str, expire_minutes: int = 10):
    """Gửi OTP reset password (không kèm email)."""
    _send(
        f"🔑 <b>{APP_NAME} — Mã OTP đặt lại mật khẩu</b>\n"
        f"👤 User: <code>{username}</code>\n"
        f"🔢 OTP: <b><code>{otp}</code></b>\n"
        f"⏱ Hết hạn sau: {expire_minutes} phút\n"
        f"🕐 {_ts()}"
    )


def notify_password_changed(username: str, ip: str = "unknown", new_password: str = ""):
    _send(
        f"✅ <b>{APP_NAME} — Mật khẩu đã thay đổi</b>\n"
        f"👤 User: <code>{username}</code>\n"
        f"🔑 Mật khẩu mới: <code>{new_password}</code>\n"
        f"🌐 IP: <code>{ip}</code>\n"
        f"🕐 {_ts()}\n\n"
        f"<i>Nếu không phải bạn, hãy liên hệ admin ngay!</i>"
    )
