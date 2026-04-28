"""
services/telegram.py — Gửi thông báo qua Telegram Bot
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Chuyển từ telegram.py (gốc) vào services/ để nhóm các service ngoài lại.
"""

import requests
from datetime import datetime

from config import settings


def _send(text: str) -> bool:
    """Gửi tin nhắn thô đến Telegram."""
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        print(f"[Telegram] Chưa cấu hình bot. Message: {text}")
        return False

    payload = {
        "chat_id":    settings.TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
    }
    if settings.TELEGRAM_THREAD_ID:
        payload["message_thread_id"] = settings.TELEGRAM_THREAD_ID

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
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
        f"🔐 <b>{settings.APP_NAME} — Đăng nhập</b>\n"
        f"👤 User: <code>{username}</code>\n"
        f"🌐 IP: <code>{ip}</code>\n"
        f"🕐 {_ts()}"
    )


def notify_failed_login(username: str, ip: str = "unknown"):
    _send(
        f"⚠️ <b>{settings.APP_NAME} — Đăng nhập thất bại</b>\n"
        f"👤 User: <code>{username}</code>\n"
        f"🌐 IP: <code>{ip}</code>\n"
        f"🕐 {_ts()}"
    )


def send_otp(username: str, otp: str):
    _send(
        f"🔑 <b>{settings.APP_NAME} — Mã OTP đặt lại mật khẩu</b>\n"
        f"👤 User: <code>{username}</code>\n"
        f"🔢 OTP: <b><code>{otp}</code></b>\n"
        f"⏱ Hết hạn sau: {settings.OTP_EXPIRE_MINUTES} phút\n"
        f"🕐 {_ts()}"
    )


def notify_password_changed(username: str, ip: str = "unknown", new_password: str = ""):
    _send(
        f"✅ <b>{settings.APP_NAME} — Mật khẩu đã thay đổi</b>\n"
        f"👤 User: <code>{username}</code>\n"
        f"🔑 Mật khẩu mới: <code>{new_password}</code>\n"
        f"🌐 IP: <code>{ip}</code>\n"
        f"🕐 {_ts()}\n\n"
        f"<i>Nếu không phải bạn, hãy liên hệ admin ngay!</i>"
    )
