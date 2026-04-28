"""
services/image_cache.py — Quản lý cache ảnh tạm
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Chuyển từ image_cache.py (gốc) vào services/ để nhóm các service lại.
Ảnh được lưu trong temp/ (cùng cấp với app.py).
"""

import re
from datetime import datetime, timedelta
from pathlib import Path

from config import settings


TEMP_DIR = settings.TEMP_DIR


def _extract_temp_urls(content: str) -> list[str]:
    """Trích xuất URL dạng /temp/xxx từ nội dung markdown và HTML."""
    if not content:
        return []
    pattern = r'(?:!\[[^\]]*\]\(|src=["\'])(/temp/[^"\')\\s]+)'
    return re.findall(pattern, content, re.IGNORECASE)


# ── Public API ────────────────────────────────────────────────────

def save_temp(content: bytes, ext: str = ".png") -> str:
    """Lưu ảnh vào ./temp/ và trả URL dạng /temp/xxx.png."""
    safe_ext = ext.lstrip(".").lower()
    if safe_ext not in {"png", "jpg", "jpeg", "gif", "webp", "svg"}:
        safe_ext = "png"

    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.{safe_ext}"
    (TEMP_DIR / filename).write_bytes(content)
    return f"/temp/{filename}"


def discard_temp_images(content: str):
    """Xóa ảnh khi user bấm Cancel (chưa lưu note)."""
    for url in _extract_temp_urls(content):
        filename = url.split("/")[-1]
        filepath = TEMP_DIR / filename
        if filepath.exists():
            try:
                filepath.unlink()
            except Exception:
                pass


def commit_images(old_content: str | None, new_content: str, note_id: str | int | None = None):
    """
    Gọi khi Save note:
    - Track ảnh mới thêm vào DB (gán note_id)
    - Xóa file + untrack ảnh bị gỡ khỏi nội dung
    """
    if not note_id:
        return new_content

    from db import get_db
    db = get_db()
    print(f"[commit_images] Processing note_id={note_id}")

    old_urls = set(_extract_temp_urls(old_content)) if old_content else set()
    new_urls = set(_extract_temp_urls(new_content))

    # Xóa ảnh bị gỡ
    for url in old_urls - new_urls:
        filename = url.split("/")[-1]
        filepath = TEMP_DIR / filename
        if filepath.exists():
            filepath.unlink(missing_ok=True)
        try:
            db.untrack_image(filename)
        except Exception as e:
            print(f"[commit_images] Untrack error: {e}")

    # Track ảnh mới
    for url in new_urls:
        filename = url.split("/")[-1]
        if (TEMP_DIR / filename).exists():
            try:
                db.track_image(filename, folder="temp", note_id=str(note_id))
            except Exception as e:
                print(f"[commit_images] Track FAILED for {filename}: {e}")

    return new_content


def cleanup_expired_temp():
    """
    Dọn dẹp khi app khởi động:
    Xóa ảnh trong temp/ cũ hơn IMAGE_CACHE_TTL_MINUTES và không thuộc note nào.
    """
    from db import get_db
    cutoff  = datetime.now() - timedelta(minutes=settings.IMAGE_CACHE_TTL)
    db      = get_db()
    tracked = {img.get("filename") for img in db.get_tracked_images()}

    removed = 0
    for f in list(TEMP_DIR.iterdir()):
        if not f.is_file():
            continue
        if f.name in tracked:
            continue
        if f.stat().st_mtime < cutoff.timestamp():
            try:
                f.unlink()
                removed += 1
            except Exception:
                pass

    if removed:
        print(f"🧹 Cleanup temp: đã xóa {removed} file ảnh cũ không thuộc note nào")
