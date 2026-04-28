"""
image_cache.py — Chỉ dùng 1 thư mục temp/ (cùng cấp với app.py)
Ảnh được lưu vĩnh viễn trong temp/, chỉ track vào DB khi Save note.
"""

import re
import os
from datetime import datetime, timedelta
from pathlib import Path

from db import get_db

# Thư mục temp cùng cấp với app.py
BASE_DIR = Path(__file__).parent
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

_TTL_MINUTES = int(os.getenv("IMAGE_CACHE_TTL_MINUTES", "120"))  # 2 giờ


def _extract_temp_urls(content: str) -> list[str]:
    """Trích xuất URL dạng /temp/xxx từ markdown và HTML"""
    if not content:
        return []
    pattern = r'(?:!\[[^\]]*\]\(|src=["\'])(/temp/[^"\')\s]+)'
    return re.findall(pattern, content, re.IGNORECASE)


# ════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ════════════════════════════════════════════════════════════════════

def save_temp(content: bytes, ext: str = ".png") -> str:
    """Lưu ảnh vào ./temp/ và trả URL dạng /temp/xxx.png"""
    safe_ext = ext.lstrip(".").lower()
    if safe_ext not in {"png", "jpg", "jpeg", "gif", "webp", "svg"}:
        safe_ext = "png"

    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.{safe_ext}"
    (TEMP_DIR / filename).write_bytes(content)
    return f"/temp/{filename}"


def discard_temp_images(content: str):
    """Xóa ảnh khi user Cancel (Trường hợp 1)"""
    for url in _extract_temp_urls(content):
        filename = url.split('/')[-1]
        filepath = TEMP_DIR / filename
        if filepath.exists():
            try:
                filepath.unlink()
            except:
                pass


def commit_images(old_content: str | None, new_content: str, note_id: str | int | None = None):
    if not note_id:
        return new_content

    db = get_db()
    print(f"[commit_images] Processing note_id={note_id}")

    old_urls = set(_extract_temp_urls(old_content)) if old_content else set()
    new_urls = set(_extract_temp_urls(new_content))

    print(f"[commit_images] Old URLs: {len(old_urls)}, New URLs: {len(new_urls)}")

    # Xóa ảnh bị gỡ
    for url in old_urls - new_urls:
        filename = url.split('/')[-1]
        filepath = TEMP_DIR / filename
        if filepath.exists():
            filepath.unlink(missing_ok=True)
        try:
            db.untrack_image(filename)
            print(f"[commit_images] Untracked (deleted): {filename}")
        except Exception as e:
            print(f"[commit_images] Untrack error: {e}")

    # Track ảnh mới
    for url in new_urls:
        filename = url.split('/')[-1]
        if (TEMP_DIR / filename).exists():
            try:
                db.track_image(filename, folder="temp", note_id=str(note_id))
                print(f"[commit_images] Tracked successfully: {filename} → note {note_id}")
            except Exception as e:
                print(f"[commit_images] Track FAILED for {filename}: {e}")

    return new_content


def cleanup_expired_temp(hours: int = 2):
    """Cleanup an toàn: chỉ xóa file temp cũ và không thuộc note nào"""
    cutoff = datetime.now() - timedelta(hours=hours)
    db = get_db()
    tracked = {img.get('filename') for img in db.get_tracked_images()}

    removed = 0
    for f in list(TEMP_DIR.iterdir()):
        if not f.is_file():
            continue
        if f.name in tracked:
            continue  # thuộc note → giữ lại
        if f.stat().st_mtime < cutoff.timestamp():
            try:
                f.unlink()
                removed += 1
            except:
                pass

    if removed:
        print(f"🧹 Cleanup temp: đã xóa {removed} file ảnh cũ không thuộc note nào")
