"""
DevNotes - Interview Knowledge Base
────────────────────────────────────
Run:  python app.py
Open: http://localhost:5000

Yêu cầu: pip install flask flask-jwt-extended bcrypt python-dotenv requests
"""

import os
from pathlib import Path
from datetime import timedelta

from dotenv import load_dotenv
load_dotenv()  # load .env trước mọi thứ

from flask import Flask, render_template, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity

from db      import get_db
from auth    import (hash_password, check_password,
                     generate_otp, otp_expires_at,
                     jwt_required_api, get_client_ip)
import telegram as tg

# ── App setup ────────────────────────────────────────────────────

app = Flask(__name__)
app.config["SECRET_KEY"]              = os.getenv("FLASK_SECRET_KEY", "dev-secret")
app.config["JWT_SECRET_KEY"]          = os.getenv("JWT_SECRET_KEY",   "jwt-secret")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=12)
app.config["JWT_TOKEN_LOCATION"]      = ["headers", "cookies"]
app.config["JWT_COOKIE_SECURE"]       = False  # True khi production + HTTPS
app.config["JWT_COOKIE_CSRF_PROTECT"] = False

jwt = JWTManager(app)

@jwt.unauthorized_loader
def unauthorized_callback(_reason):
    # API calls nhận JSON; page calls nhận redirect
    if request.path.startswith("/api/"):
        return jsonify({"error": "Chưa đăng nhập"}), 401
    from flask import redirect, url_for
    return redirect("/login")


# ── Ensure admin user exists ─────────────────────────────────────

def ensure_admin():
    db = get_db()
    username = os.getenv("ADMIN_USERNAME", "admin")
    if not db.get_user(username):
        password = os.getenv("ADMIN_PASSWORD", "changeme123")
        email    = os.getenv("ADMIN_EMAIL",    "admin@devnotes.local")
        db.create_user(username, email, hash_password(password))
        print(f"✅ Admin user tạo: {username}")


# ════════════════════════════════════════════════════════════════
#  PAGE ROUTES
# ════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/forgot-password")
def forgot_page():
    return render_template("forgot.html")


# ════════════════════════════════════════════════════════════════
#  AUTH API
# ════════════════════════════════════════════════════════════════

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    body     = request.json or {}
    username = body.get("username", "").strip()
    password = body.get("password", "")
    ip       = get_client_ip()

    if not username or not password:
        return jsonify({"error": "Thiếu username hoặc password"}), 400

    db   = get_db()
    user = db.get_user(username)

    if not user or not check_password(password, user["password"]):
        tg.notify_failed_login(username, ip)
        return jsonify({"error": "Sai username hoặc mật khẩu"}), 401

    db.update_last_login(username)
    tg.notify_login(username, ip)

    token = create_access_token(identity=username)
    resp  = jsonify({"token": token, "username": username})
    # Lưu vào cookie để page tự dùng
    from flask_jwt_extended import set_access_cookies
    set_access_cookies(resp, token)
    return resp


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    from flask_jwt_extended import unset_jwt_cookies
    resp = jsonify({"ok": True})
    unset_jwt_cookies(resp)
    return resp


@app.route("/api/auth/me", methods=["GET"])
@jwt_required_api
def api_me():
    username = get_jwt_identity()
    db   = get_db()
    user = db.get_user(username)
    if not user:
        return jsonify({"error": "User không tồn tại"}), 404
    return jsonify({
        "username":  user["username"],
        "email":     user["email"],
        "lastLogin": user.get("last_login"),
    })


@app.route("/api/auth/forgot-password", methods=["POST"])
def api_forgot_password():
    """
    Không cần email — gửi OTP thẳng vào Telegram.
    OTP được lưu tạm với key cố định "_admin_reset_".
    """
    db         = get_db()
    otp        = generate_otp()
    expires_at = otp_expires_at()
    # Dùng key cố định thay vì email
    db.save_otp("_admin_reset_", otp, expires_at)
    tg.send_otp_no_email(otp)
    return jsonify({"ok": True, "message": "OTP đã được gửi qua Telegram."})


@app.route("/api/auth/reset-password", methods=["POST"])
def api_reset_password():
    body     = request.json or {}
    otp      = body.get("otp", "").strip()
    new_pass = body.get("new_password", "")
    username = os.getenv("ADMIN_USERNAME", "admin")
    ip       = get_client_ip()

    if not otp or not new_pass:
        return jsonify({"error": "Thiếu OTP hoặc mật khẩu mới"}), 400

    if len(new_pass) < 8:
        return jsonify({"error": "Mật khẩu tối thiểu 8 ký tự"}), 400

    db = get_db()
    if not db.verify_otp("_admin_reset_", otp):
        return jsonify({"error": "OTP không hợp lệ hoặc đã hết hạn"}), 400

    # Cập nhật password của admin
    user = db.get_user(username)
    if not user:
        return jsonify({"error": "Không tìm thấy user"}), 404

    db.update_password(user["email"], hash_password(new_pass))
    tg.notify_password_changed(username, ip)
    return jsonify({"ok": True, "message": "Mật khẩu đã được cập nhật."})


# ════════════════════════════════════════════════════════════════
#  NOTES API
# ════════════════════════════════════════════════════════════════

@app.route("/api/notes", methods=["GET"])
@jwt_required_api
def api_get_notes():
    db       = get_db()
    q        = request.args.get("q", "").strip()
    topic_id = request.args.get("topic", "")

    notes  = db.get_notes(
        q=q,
        topic_id=int(topic_id) if topic_id.isdigit() else None,
    )
    topics = db.get_topics()
    return jsonify({"notes": notes, "topics": topics})


@app.route("/api/notes", methods=["POST"])
@jwt_required_api
def api_create_note():
    body     = request.json or {}
    question = body.get("question", "").strip()
    content  = body.get("content",  "").strip()

    if not question or not content:
        return jsonify({"error": "question và content là bắt buộc"}), 400

    topic_raw = body.get("topic")
    topic_id  = int(topic_raw) if str(topic_raw).isdigit() else None
    tags      = body.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    note = get_db().create_note(question, content, topic_id, tags)
    return jsonify(note), 201


@app.route("/api/notes/<int:note_id>", methods=["PUT"])
@jwt_required_api
def api_update_note(note_id):
    body     = request.json or {}
    topic_raw = body.get("topic")
    topic_id  = int(topic_raw) if str(topic_raw or "").isdigit() else None
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


@app.route("/api/notes/<int:note_id>", methods=["DELETE"])
@jwt_required_api
def api_delete_note(note_id):
    if not get_db().delete_note(note_id):
        return jsonify({"error": "Không tìm thấy note"}), 404
    return jsonify({"ok": True})


# ════════════════════════════════════════════════════════════════
#  TOPICS API
# ════════════════════════════════════════════════════════════════

@app.route("/api/topics", methods=["GET"])
@jwt_required_api
def api_get_topics():
    return jsonify(get_db().get_topics())


@app.route("/api/topics", methods=["POST"])
@jwt_required_api
def api_create_topic():
    body  = request.json or {}
    name  = body.get("name", "").strip()
    color = body.get("color", "#4fffb0")
    if not name:
        return jsonify({"error": "Tên chủ đề là bắt buộc"}), 400

    db = get_db()
    if db.get_topic_by_name(name):
        return jsonify({"error": "Chủ đề đã tồn tại"}), 409

    return jsonify(db.create_topic(name, color)), 201


@app.route("/api/topics/<int:topic_id>", methods=["DELETE"])
@jwt_required_api
def api_delete_topic(topic_id):
    if not get_db().delete_topic(topic_id):
        return jsonify({"error": "Không tìm thấy topic"}), 404
    return jsonify({"ok": True})


# ════════════════════════════════════════════════════════════════
#  IMPORT / EXPORT
# ════════════════════════════════════════════════════════════════

@app.route("/api/export", methods=["GET"])
@jwt_required_api
def api_export():
    return jsonify(get_db().export_all())


@app.route("/api/import", methods=["POST"])
@jwt_required_api
def api_import():
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

    db    = get_db()
    added = db.import_bulk(raw_topics, raw_notes)
    return jsonify({"added": added, "total": len(db.get_notes())})


# ════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    ensure_admin()

    # Seed nếu DB trống
    db = get_db()
    if not db.get_notes():
        from seed import seed_data
        seed_data()

    print("🚀 DevNotes chạy tại: http://localhost:5000")
    app.run(debug=True, port=5000)
