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

from flask import Flask, render_template, request, jsonify, send_from_directory, abort
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
    if "/" in filename or "\\" in filename or ".." in filename:
        abort(400)
    if Path(filename).suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
        abort(400)
    return send_from_directory(str(settings.TEMP_DIR), filename)

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

# ── Main ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    ensure_admin()
    db = get_db()
    if not db.get_notes():
        from seed import seed_data
        seed_data()
    startup_cleanup()
    print(f"🚀 DevNotes chạy tại: http://localhost:{settings.PORT}")
    app.run(debug=settings.DEBUG, port=settings.PORT, host="0.0.0.0")
