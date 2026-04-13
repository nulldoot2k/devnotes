"""
routes/data.py — Blueprint /api/export và /api/import
"""

import os
from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity

from db   import get_db
from auth import jwt_required_api

data_bp = Blueprint("data", __name__, url_prefix="/api")


def _owner():
    if os.getenv("OWNER_MODE", "single") == "multi":
        return get_jwt_identity()
    return "__shared__"


@data_bp.route("/export", methods=["GET"])
@jwt_required_api
def export_data():
    return jsonify(get_db().export_all(owner_id=_owner()))


@data_bp.route("/import", methods=["POST"])
@jwt_required_api
def import_data():
    body = request.json
    if not body:
        return jsonify({"error": "Body rỗng"}), 400

    raw_notes  = []
    raw_topics = []

    if isinstance(body, list):
        raw_notes = body
    elif isinstance(body, dict):
        raw_notes  = body.get("notes",  [])
        raw_topics = body.get("topics", [])
    else:
        return jsonify({"error": "Format không hợp lệ"}), 400

    owner = _owner()
    db    = get_db()
    added = db.import_bulk(raw_topics, raw_notes, owner_id=owner)
    return jsonify({"added": added, "total": len(db.get_notes(owner_id=owner))})
