"""
routes/notes.py — Blueprint /api/notes/*
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity

from db          import get_db
from utils.auth_utils import jwt_required_api
from services.image_cache import commit_images, _extract_temp_urls

notes_bp = Blueprint("notes", __name__, url_prefix="/api/notes")


def _lazy_migrate(db, notes):
    """Lazy migration: với mỗi note còn /temp/<f> ref, ingest bytes vào DB
    và rewrite content thành /img/<filename>. Idempotent — nếu file đã bị TTL
    xóa, URL giữ nguyên (không crash). Chạy in-line để bảo vệ trường hợp
    người dùng tạo note với code cũ rồi pull code mới mà chưa restart."""
    for n in notes:
        content = n.get("content") or ""
        if not _extract_temp_urls(content):
            continue
        try:
            new_content = commit_images(
                old_content=None,
                new_content=content,
                note_id=n["id"],
            )
        except Exception as e:
            print(f"[lazy-migrate] note {n.get('id')}: {e}")
            continue
        if new_content != content:
            try:
                db.update_note(n["id"], content=new_content)
                n["content"] = new_content
            except Exception as e:
                print(f"[lazy-migrate] update note {n.get('id')} failed: {e}")


def _owner():
    import os
    if os.getenv("OWNER_MODE", "single") == "multi":
        return get_jwt_identity()
    return "__shared__"


def _normalize_topic_id(topic_raw):
    if not topic_raw:
        return None
    try:
        if str(topic_raw).strip().isdigit():
            return int(topic_raw)
        return None
    except (ValueError, TypeError):
        return None


@notes_bp.route("", methods=["GET"])
@jwt_required_api
def get_notes():
    db       = get_db()
    q        = request.args.get("q", "").strip()
    topic_id = request.args.get("topic", "").strip()
    owner    = _owner()

    notes  = db.get_notes(q=q, topic_id=_normalize_topic_id(topic_id), owner_id=owner)
    _lazy_migrate(db, notes)
    topics = db.get_topics(owner_id=owner)
    return jsonify({"notes": notes, "topics": topics})


@notes_bp.route("", methods=["POST"])
@jwt_required_api
def create_note():
    body     = request.json or {}
    question = body.get("question", "").strip()
    content  = body.get("content",  "").strip()

    if not question or not content:
        return jsonify({"error": "question và content là bắt buộc"}), 400

    topic_id = _normalize_topic_id(body.get("topic"))
    tags     = body.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    db    = get_db()
    owner = _owner()

    # 1. Lưu note với content gốc (chứa /temp/<f>) để lấy note_id
    note = db.create_note(question, content, topic_id, tags, owner_id=owner)

    # 2. Ingest ảnh vào DB và rewrite /temp/<f> → /img/<filename>
    new_content = commit_images(
        old_content=None,
        new_content=content,
        note_id=note["id"],
    )

    # 3. Nếu URL được rewrite thì update lại note với content mới
    if new_content != content:
        updated = db.update_note(note["id"], content=new_content)
        if updated:
            note = updated

    return jsonify(note), 201


@notes_bp.route("/<string:note_id>", methods=["PUT"])
@jwt_required_api
def update_note(note_id):
    body     = request.json or {}
    question = body.get("question", "").strip() or None
    content  = body.get("content",  "").strip() or None
    topic_id = _normalize_topic_id(body.get("topic"))
    tags     = body.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    db       = get_db()
    old_note = db.get_note(note_id)
    if not old_note:
        return jsonify({"error": "Không tìm thấy note"}), 404

    effective_content = content if content is not None else old_note["content"]

    # 1. Update DB trước với content gốc
    note = db.update_note(
        note_id,
        question=question,
        content=content,
        topic_id=topic_id,
        tags=tags,
    )
    if note is None:
        return jsonify({"error": "Không tìm thấy note"}), 404

    # 2. Ingest /temp/<f> → DB, rewrite URL, dọn /img/<slug> đã bị remove
    new_content = commit_images(
        old_content=old_note["content"],
        new_content=effective_content,
        note_id=note_id,
    )

    # 3. Nếu content bị rewrite thì update lại
    if new_content != effective_content:
        updated = db.update_note(note_id, content=new_content)
        if updated:
            note = updated

    return jsonify(note)


@notes_bp.route("/<string:note_id>", methods=["DELETE"])
@jwt_required_api
def delete_note(note_id):
    db       = get_db()
    existing = db.get_note(note_id)
    if not existing:
        return jsonify({"error": "Không tìm thấy note"}), 404

    # Xóa file ảnh + untrack trước khi xóa note
    # new_content="" → toàn bộ ảnh cũ bị coi là "đã bị xóa"
    commit_images(
        old_content=existing["content"],
        new_content="",
        note_id=note_id,
    )

    db.delete_note(note_id)
    return jsonify({"ok": True})
