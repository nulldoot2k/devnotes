"""
routes/images.py — Blueprint /api/images/*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Upload ảnh vào static/temp/ (cache tạm).
Ảnh chỉ được move sang static/uploads/ khi note được Save.

Endpoints:
  POST /api/images/upload   — nhận file, lưu temp, trả URL tạm
  POST /api/images/discard  — xóa danh sách URL temp (khi cancel)
"""

import os
from pathlib import Path

from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity

from auth         import jwt_required_api
from image_cache  import save_temp, discard_temp_images

images_bp = Blueprint("images", __name__, url_prefix="/api/images")

# Các mime type được phép upload
ALLOWED_MIME = {
    "image/png", "image/jpeg", "image/jpg",
    "image/gif", "image/webp", "image/svg+xml",
}

# Giới hạn kích thước (đọc từ env, mặc định 10MB)
MAX_SIZE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", str(10 * 1024 * 1024)))


@images_bp.route("/upload", methods=["POST"])
@jwt_required_api
def upload_image():
    """
    Nhận file ảnh từ multipart/form-data (field name: "file").
    Lưu vào static/temp/ (cache tạm).
    Trả về { "url": "/static/temp/<filename>", "temp": true }

    Ảnh chỉ thực sự được persist khi note được Save
    (xem image_cache.commit_images).
    """
    if "file" not in request.files:
        return jsonify({"error": "Không có file nào được gửi lên"}), 400

    file = request.files["file"]

    if not file.filename:
        return jsonify({"error": "Tên file rỗng"}), 400

    # Kiểm tra mime type
    mime = file.mimetype or ""
    if mime not in ALLOWED_MIME:
        return jsonify({"error": f"Loại file không được phép: {mime}"}), 415

    # Đọc content và kiểm tra kích thước
    content = file.read()
    if len(content) > MAX_SIZE_BYTES:
        return jsonify({"error": f"File quá lớn (tối đa {MAX_SIZE_BYTES // 1024 // 1024}MB)"}), 413

    # Lấy extension
    original_ext = Path(file.filename).suffix.lower() or ".png"
    safe_ext = original_ext if original_ext in {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"
    } else ".png"

    # Lưu vào temp/
    url = save_temp(content, safe_ext)

    return jsonify({
        "url":      url,
        "filename": url.split("/")[-1],
        "temp":     True,   # flag để frontend biết đây là URL tạm
    }), 201


@images_bp.route("/discard", methods=["POST"])
@jwt_required_api
def discard_images():
    """
    Nhận { "content": "<markdown content>" }
    Xóa tất cả ảnh temp được tham chiếu trong content.
    Gọi khi user Cancel / đóng modal mà không Save.
    """
    data    = request.get_json(silent=True) or {}
    content = data.get("content", "")
    if content:
        discard_temp_images(content)
    return jsonify({"ok": True}), 200
