"""
services/image_cache.py — Quản lý ảnh: temp/ là cache khi đang edit, DB là persist
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Lifecycle:
  1. Upload (đang edit): bytes → temp/<filename>; URL trả cho FE = /temp/<filename>.
  2. Save note (commit_images): đọc bytes từ temp/ → upsert vào DB
     (bytes + mime + note_id), URL trong content rewrite từ /temp/<f> → /img/<filename>.
  3. Edit + xóa ảnh: /img/<filename> biến mất khỏi content → row trong DB bị delete.
  4. Background: file trong temp/ quá TTL bị xóa (bytes vẫn an toàn trong DB).

Sau Save, content KHÔNG còn /temp/<f> nào nữa, mọi ảnh đều phục vụ qua /img/<filename>.
URL legacy `/img/<numeric_id>` vẫn được route resolve cho note cũ (backward compat).
"""

import re
from datetime import datetime, timedelta
from pathlib import Path

from config import settings


TEMP_DIR = settings.TEMP_DIR

# /temp/<filename>  — cache filesystem trong khi đang edit
_TEMP_URL_RE = re.compile(
    r'(?:!\[[^\]]*\]\(|src=["\'])(/temp/[^"\')\s]+)',
    re.IGNORECASE,
)
# /img/<id>  — URL persistent trỏ vào DB
_IMG_URL_RE = re.compile(
    r'(?:!\[[^\]]*\]\(|src=["\'])(/img/[^"\')\s]+)',
    re.IGNORECASE,
)

_MIME_BY_EXT = {
    "png":  "image/png",
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
    "gif":  "image/gif",
    "webp": "image/webp",
    "svg":  "image/svg+xml",
}


def _extract_temp_urls(content: str) -> list[str]:
    if not content:
        return []
    return _TEMP_URL_RE.findall(content)


def _extract_img_slugs(content: str) -> list[str]:
    """Extract slugs từ /img/<slug> (filename hoặc numeric id legacy)."""
    if not content:
        return []
    slugs = []
    for url in _IMG_URL_RE.findall(content):
        slug = url[len("/img/"):].split("?", 1)[0].split("#", 1)[0]
        if slug:
            slugs.append(slug)
    return slugs


def _looks_like_filename(slug: str) -> bool:
    """True nếu slug nhìn như filename (có extension ảnh đã biết)."""
    return Path(slug).suffix.lstrip(".").lower() in _MIME_BY_EXT


def _mime_from_filename(filename: str) -> str:
    ext = Path(filename).suffix.lstrip(".").lower()
    return _MIME_BY_EXT.get(ext, "application/octet-stream")


# ── Public API ────────────────────────────────────────────────────

def save_temp(content: bytes, ext: str = ".png") -> str:
    """Lưu ảnh vào temp/ (cache khi đang edit) và trả URL /temp/<filename>."""
    safe_ext = ext.lstrip(".").lower()
    if safe_ext not in _MIME_BY_EXT:
        safe_ext = "png"

    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.{safe_ext}"
    (TEMP_DIR / filename).write_bytes(content)
    return f"/temp/{filename}"


def discard_temp_images(content: str):
    """Xóa file trong temp/ ứng với /temp/<f> được tham chiếu (khi user Cancel)."""
    for url in _extract_temp_urls(content):
        filename = url.split("/")[-1]
        filepath = TEMP_DIR / filename
        if filepath.exists():
            try:
                filepath.unlink()
            except Exception:
                pass


def commit_images(old_content: str | None, new_content: str, note_id) -> str:
    """
    Gọi khi Save / Update / Delete note.
    1. Với mỗi /temp/<f> trong new_content: đọc bytes từ temp/, upsert vào DB,
       rewrite URL → /img/<id> trong content.
    2. Với mỗi /img/<id> có trong old_content nhưng không có trong new_content:
       xóa row trong DB (ảnh đã bị remove khỏi note).
    3. Trả về content đã rewrite (caller chịu trách nhiệm save lại nếu khác).

    File trong temp/ KHÔNG bị xóa ngay — để cleanup_expired_temp dọn theo TTL.
    """
    if not note_id:
        return new_content

    from db import get_db
    db = get_db()

    # ── 1. Ingest /temp/<f> → DB và rewrite URL → /img/<filename>
    rewrites: dict[str, str] = {}
    for url in _extract_temp_urls(new_content):
        filename = url.split("/")[-1]
        filepath = TEMP_DIR / filename

        # File còn trên đĩa → đọc bytes và upsert vào DB.
        if filepath.exists():
            try:
                data = filepath.read_bytes()
            except Exception as e:
                print(f"[commit_images] Read FAILED for {filename}: {e}")
                continue

            mime = _mime_from_filename(filename)
            try:
                db.upsert_image_bytes(filename, data, mime, note_id=note_id)
            except Exception as e:
                print(f"[commit_images] DB upsert FAILED for {filename}: {e}")
                continue
            rewrites[url] = f"/img/{filename}"
            continue

        # File đã mất khỏi temp/ — nhưng nếu DB đã có row cho filename này
        # (vd. commit trước đó thành công, sau đó TTL xóa file), vẫn rewrite
        # URL → /img/<filename> để FE không stuck ở /temp/<f> 404 mãi mãi.
        try:
            existing_id = db.get_image_id_by_filename(filename)
        except Exception as e:
            print(f"[commit_images] DB lookup FAILED for {filename}: {e}")
            existing_id = None
        if existing_id is not None:
            rewrites[url] = f"/img/{filename}"
        # else: file mất + DB chưa có → ảnh đã mất hẳn, để URL gốc (FE 404)

    rewritten = new_content
    for old_url, new_url in rewrites.items():
        rewritten = rewritten.replace(old_url, new_url)

    # ── 2. Xóa các /img/<slug> không còn được tham chiếu trong note này
    #     VÀ không được note khác tham chiếu. Slug có thể là filename (URL
    #     mới) hoặc numeric id legacy — phân biệt theo extension để gọi đúng
    #     delete method.
    old_slugs = set(_extract_img_slugs(old_content)) if old_content else set()
    new_slugs = set(_extract_img_slugs(rewritten))
    for slug in old_slugs - new_slugs:
        if _image_still_referenced(db, slug, exclude_note_id=note_id):
            # Note khác vẫn dùng ảnh này → không xóa, tránh broken refs.
            continue
        try:
            if _looks_like_filename(slug):
                db.delete_image_by_filename(slug)
            else:
                db.delete_image_by_id(slug)
        except Exception as e:
            print(f"[commit_images] DB delete FAILED for /img/{slug}: {e}")

    return rewritten


def _image_still_referenced(db, slug: str, exclude_note_id) -> bool:
    """True nếu /img/<slug> còn xuất hiện trong content của bất kỳ note nào
    khác (loại trừ note đang được update). Dùng để tránh xóa row trong DB
    khi nhiều note cùng share 1 ảnh."""
    eid = str(exclude_note_id) if exclude_note_id is not None else None
    try:
        notes = db.get_notes()
    except Exception as e:
        # Lookup fail → không an toàn để xóa, giữ row.
        print(f"[commit_images] _image_still_referenced lookup failed: {e}")
        return True
    for n in notes:
        if eid and str(n.get("id")) == eid:
            continue
        if slug in _extract_img_slugs(n.get("content") or ""):
            return True
    return False


def cleanup_expired_temp():
    """
    Khởi động app: xóa file trong temp/ quá TTL.
    Bytes của các ảnh đã commit nằm an toàn trong DB → temp/ chỉ còn vai trò cache.
    """
    cutoff = datetime.now() - timedelta(minutes=settings.IMAGE_CACHE_TTL)
    removed = 0
    for f in list(TEMP_DIR.iterdir()):
        if not f.is_file():
            continue
        try:
            if f.stat().st_mtime < cutoff.timestamp():
                f.unlink()
                removed += 1
        except Exception:
            pass

    if removed:
        print(f"🧹 Cleanup temp: đã xóa {removed} file ảnh quá TTL")
