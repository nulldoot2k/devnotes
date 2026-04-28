"""
routes/notes.py — Blueprint /api/notes/*
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity

from db          import get_db
from auth        import jwt_required_api
from image_cache import commit_images

notes_bp = Blueprint("notes", __name__, url_prefix="/api/notes")


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

    # 1. Lưu note trước để có note_id
    note = db.create_note(question, content, topic_id, tags, owner_id=owner)

    # 2. Sau khi có note_id: track ảnh vào DB (ảnh vẫn nằm trong temp/)
    #    old_content=None vì note mới, không có ảnh cũ nào cần xóa
    commit_images(
        old_content=None,
        new_content=content,
        note_id=note["id"],
    )

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

    # 1. Update DB trước
    note = db.update_note(
        note_id,
        question=question,
        content=content,
        topic_id=topic_id,
        tags=tags,
    )
    if note is None:
        return jsonify({"error": "Không tìm thấy note"}), 404

    # 2. commit_images:
    #    - Track ảnh mới thêm vào (gán note_id)
    #    - Xóa file temp + untrack ảnh bị remove khỏi content
    commit_images(
        old_content=old_note["content"],
        new_content=content if content is not None else old_note["content"],
        note_id=note_id,
    )

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
