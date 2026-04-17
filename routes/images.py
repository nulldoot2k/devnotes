"""
routes/images.py — Blueprint /api/images/*
Xử lý upload ảnh từ paste/clipboard trong editor.
"""

import os
import uuid
from pathlib import Path

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import get_jwt_identity

from auth import jwt_required_api

images_bp = Blueprint("images", __name__, url_prefix="/api/images")

# Các mime type được phép upload
ALLOWED_MIME = {
    "image/png", "image/jpeg", "image/jpg",
    "image/gif", "image/webp", "image/svg+xml",
}

# Giới hạn 10MB mỗi file
MAX_SIZE_BYTES = 10 * 1024 * 1024


def _upload_dir() -> Path:
    """Thư mục lưu ảnh: static/uploads/ (tự tạo nếu chưa có)."""
    base = Path(current_app.root_path) / "static" / "uploads"
    base.mkdir(parents=True, exist_ok=True)
    return base


@images_bp.route("/upload", methods=["POST"])
@jwt_required_api
def upload_image():
    """
    Nhận file ảnh từ multipart/form-data (field name: "file").
    Trả về { "url": "/static/uploads/<filename>" }
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
        return jsonify({"error": "File quá lớn (tối đa 10MB)"}), 413

    # Tạo tên file unique: <uuid>.<ext>
    original_ext = Path(file.filename).suffix.lower() or ".png"
    # Đảm bảo ext hợp lệ
    safe_ext = original_ext if original_ext in {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"
    } else ".png"

    filename = f"{uuid.uuid4().hex}{safe_ext}"
    dest     = _upload_dir() / filename

    dest.write_bytes(content)

    url = f"/static/uploads/{filename}"
    return jsonify({"url": url, "filename": filename}), 201
