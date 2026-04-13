"""
routes/topics.py — Blueprint /api/topics/*
"""

from flask import Blueprint, request, jsonify

from db   import get_db
from auth import jwt_required_api

topics_bp = Blueprint("topics", __name__, url_prefix="/api/topics")


def _owner():
    import os
    from flask_jwt_extended import get_jwt_identity
    if os.getenv("OWNER_MODE", "single") == "multi":
        return get_jwt_identity()
    return "__shared__"


@topics_bp.route("", methods=["GET"])
@jwt_required_api
def get_topics():
    return jsonify(get_db().get_topics(owner_id=_owner()))


@topics_bp.route("", methods=["POST"])
@jwt_required_api
def create_topic():
    body  = request.json or {}
    name  = body.get("name", "").strip()
    color = body.get("color", "#4fffb0")
    owner = _owner()

    if not name:
        return jsonify({"error": "Tên chủ đề là bắt buộc"}), 400

    db = get_db()
    if db.get_topic_by_name(name, owner_id=owner):
        return jsonify({"error": "Chủ đề đã tồn tại"}), 409

    return jsonify(db.create_topic(name, color, owner_id=owner)), 201


@topics_bp.route("/<string:topic_id>", methods=["DELETE"])
@jwt_required_api
def delete_topic(topic_id):
    if not get_db().delete_topic(topic_id):
        return jsonify({"error": "Không tìm thấy topic"}), 404
    return jsonify({"ok": True})
