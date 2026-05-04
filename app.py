"""
app.py — Entry point của DevNotes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Chạy:  python app.py
Mở:    http://localhost:5000
"""

from dotenv import load_dotenv
load_dotenv()

from datetime import timedelta
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_from_directory, abort, Response
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import settings
from db     import get_db
from utils.auth_utils import hash_password
from routes import auth_bp, notes_bp, topics_bp, data_bp
from routes.images import images_bp

# ── App setup ─────────────────────────────────────────────────────

app = Flask(__name__)
app.config["SECRET_KEY"]               = settings.SECRET_KEY
app.config["JWT_SECRET_KEY"]           = settings.JWT_SECRET_KEY
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=settings.JWT_EXPIRE_HOURS)
app.config["JWT_TOKEN_LOCATION"]       = ["headers", "cookies"]
app.config["JWT_COOKIE_SECURE"]        = False
app.config["JWT_COOKIE_CSRF_PROTECT"]  = False

jwt = JWTManager(app)

@jwt.unauthorized_loader
def unauthorized_callback(_reason):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Chưa đăng nhập"}), 401
    from flask import redirect
    return redirect("/login")

# ── Rate limiting ─────────────────────────────────────────────────

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
    storage_uri=settings.RATELIMIT_STORAGE_URI,
)
limiter.limit("10 per minute")(auth_bp)

# ── Register Blueprints ───────────────────────────────────────────

app.register_blueprint(auth_bp)
app.register_blueprint(notes_bp)
app.register_blueprint(topics_bp)
app.register_blueprint(data_bp)
app.register_blueprint(images_bp)

# ── Page routes ───────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/forgot-password")
def forgot_page():
    return render_template("forgot.html")

@app.route("/temp/<path:filename>")
def serve_temp_image(filename):
    """Phục vụ ảnh đang edit từ temp/ (cache filesystem). Sau Save, URL sẽ
    được rewrite sang /img/<id> nên route này chỉ phục vụ giai đoạn editing."""
    if "/" in filename or "\\" in filename or ".." in filename:
        abort(400)
    if Path(filename).suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
        abort(400)
    return send_from_directory(str(settings.TEMP_DIR), filename)


@app.route("/img/<string:image_id>")
def serve_db_image(image_id):
    """Phục vụ ảnh đã commit từ DB (bytes + mime). Slug = primary key của
    bảng images: integer cho SQL backend, ObjectId hex cho Mongo."""
    # Cắt extension nếu có (vd. /img/42.png) — lookup chỉ cần phần slug
    slug = image_id.split(".", 1)[0]
    if not slug:
        abort(400)
    db  = get_db()
    img = db.get_image_by_id(slug)
    if not img:
        abort(404)
    resp = Response(img["data"], content_type=img.get("mime") or "application/octet-stream")
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp

@app.route("/api/image-proxy")
def image_proxy():
    import requests as _req
    from flask import Response
    url = request.args.get("url", "").strip()
    if not url or not url.startswith(("http://", "https://")):
        abort(400)
    try:
        r  = _req.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
        ct = r.headers.get("Content-Type", "image/png")
        return Response(r.content, content_type=ct, headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e:
        print(f"[image-proxy] lỗi: {e}")
        abort(502)

# ── Startup helpers ───────────────────────────────────────────────

def ensure_admin():
    db = get_db()
    if not db.get_user(settings.ADMIN_USERNAME):
        db.create_user(
            settings.ADMIN_USERNAME,
            settings.ADMIN_EMAIL,
            hash_password(settings.ADMIN_PASSWORD),
            role="admin"
        )
        print(f"✅ Admin user tạo: {settings.ADMIN_USERNAME}")

def startup_cleanup():
    try:
        from services.image_cache import cleanup_expired_temp
        cleanup_expired_temp()
    except Exception as e:
        print(f"⚠️  Startup cleanup lỗi: {e}")


def migrate_legacy_temp_urls():
    """
    One-shot migration: các note đã lưu trước đây tham chiếu /temp/<filename>
    trong content. Đọc bytes từ temp/ → DB → rewrite content thành /img/<id>.
    File bị mất trên đĩa thì giữ nguyên URL (sẽ 404, không crash).
    """
    try:
        from services.image_cache import commit_images, _extract_temp_urls
        db = get_db()
        notes = db.get_notes()
        rewritten = 0
        for n in notes:
            content = n.get("content") or ""
            if not _extract_temp_urls(content):
                continue
            new_content = commit_images(
                old_content=None,
                new_content=content,
                note_id=n["id"],
            )
            if new_content != content:
                db.update_note(n["id"], content=new_content)
                rewritten += 1
        if rewritten:
            print(f"📦 Migrated {rewritten} note(s): /temp/* → /img/<id>")
    except Exception as e:
        print(f"⚠️  Legacy /temp migration lỗi: {e}")

# ── Main ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    ensure_admin()
    db = get_db()
    if not db.get_notes():
        from seed import seed_data
        seed_data()
    migrate_legacy_temp_urls()
    startup_cleanup()
    print(f"🚀 DevNotes chạy tại: http://localhost:{settings.PORT}")
    app.run(debug=settings.DEBUG, port=settings.PORT, host="0.0.0.0")
