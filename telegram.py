"""
telegram.py — Gửi thông báo qua Telegram Bot
"""

import os
import requests
from datetime import datetime

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
THREAD_ID   = os.getenv("TELEGRAM_THREAD_ID", "")
APP_NAME  = os.getenv("APP_NAME", "DevNotes")


def _send(text: str) -> bool:
    """Gửi message đến Telegram. Return True nếu thành công."""
    if not BOT_TOKEN or not CHAT_ID:
        print(f"[Telegram] Chưa cấu hình bot. Message: {text}")
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id":    CHAT_ID,
                "message_thread_id":    THREAD_ID,
                "text":       text,
                "parse_mode": "HTML",
            },
            timeout=5,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[Telegram] Lỗi gửi: {e}")
        return False


def notify_login(username: str, ip: str = "unknown"):
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    _send(
        f"🔐 <b>{APP_NAME} — Đăng nhập</b>\n"
        f"👤 User: <code>{username}</code>\n"
        f"🌐 IP: <code>{ip}</code>\n"
        f"🕐 Thời gian: {now}"
    )


def notify_failed_login(username: str, ip: str = "unknown"):
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    _send(
        f"⚠️ <b>{APP_NAME} — Đăng nhập thất bại</b>\n"
        f"👤 User: <code>{username}</code>\n"
        f"🌐 IP: <code>{ip}</code>\n"
        f"🕐 Thời gian: {now}"
    )


def send_otp(email: str, otp: str, expire_minutes: int = 10):
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    _send(
        f"🔑 <b>{APP_NAME} — Mã OTP đặt lại mật khẩu</b>\n"
        f"📧 Email: <code>{email}</code>\n"
        f"🔢 OTP: <b><code>{otp}</code></b>\n"
        f"⏱ Hết hạn sau: {expire_minutes} phút\n"
        f"🕐 Lúc: {now}\n\n"
        f"<i>Nếu bạn không yêu cầu, hãy bỏ qua tin nhắn này.</i>"
    )


def notify_password_changed(email: str, ip: str = "unknown"):
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    _send(
        f"✅ <b>{APP_NAME} — Mật khẩu đã thay đổi</b>\n"
        f"📧 Email: <code>{email}</code>\n"
        f"🌐 IP: <code>{ip}</code>\n"
        f"🕐 Thời gian: {now}\n\n"
        f"<i>Nếu không phải bạn, hãy liên hệ admin ngay!</i>"
    )


def send_otp_no_email(otp: str, expire_minutes: int = 10):
    """Gửi OTP không kèm email — dùng cho flow reset password đơn giản."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    _send(
        f"🔑 <b>{APP_NAME} — Mã OTP đặt lại mật khẩu</b>\n"
        f"🔢 OTP: <b><code>{otp}</code></b>\n"
        f"⏱ Hết hạn sau: {expire_minutes} phút\n"
        f"🕐 Lúc: {now}"
    )
