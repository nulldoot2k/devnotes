"""
routes/notes.py — Blueprint /api/notes/*
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity

from db   import get_db
from auth import jwt_required_api

notes_bp = Blueprint("notes", __name__, url_prefix="/api/notes")


def _owner(db_mode="single"):
    """
    Trả owner_id cho note/topic.
    single mode → '__shared__' (tất cả cùng xem)
    multi  mode → username hiện tại
    """
    import os
    if os.getenv("OWNER_MODE", "single") == "multi":
        return get_jwt_identity()
    return "__shared__"


@notes_bp.route("", methods=["GET"])
@jwt_required_api
def get_notes():
    db       = get_db()
    q        = request.args.get("q", "").strip()
    topic_id = request.args.get("topic", "")
    owner    = _owner()

    notes  = db.get_notes(
        q=q,
        topic_id=int(topic_id) if topic_id.isdigit() else None,
        owner_id=owner,
    )
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

    topic_raw = body.get("topic")
    if topic_raw:
        topic_id = int(topic_raw) if str(topic_raw).isdigit() else str(topic_raw)
    else:
        topic_id = None
    tags      = body.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    note = get_db().create_note(
        question, content, topic_id, tags, owner_id=_owner()
    )
    return jsonify(note), 201


@notes_bp.route("/<string:note_id>", methods=["PUT"])
@jwt_required_api
def update_note(note_id):
    body      = request.json or {}
    topic_raw = body.get("topic")
    if topic_raw:
        topic_id = int(topic_raw) if str(topic_raw).isdigit() else str(topic_raw)
    else:
        topic_id = None
    tags      = body.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    note = get_db().update_note(
        note_id,
        question=body.get("question", "").strip() or None,
        content=body.get("content",   "").strip() or None,
        topic_id=topic_id,
        tags=tags,
    )
    if note is None:
        return jsonify({"error": "Không tìm thấy note"}), 404
    return jsonify(note)


@notes_bp.route("/<string:note_id>", methods=["DELETE"])
@jwt_required_api
def delete_note(note_id):
    if not get_db().delete_note(note_id):
        return jsonify({"error": "Không tìm thấy note"}), 404
    return jsonify({"ok": True})
