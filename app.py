"""
DevNotes - Interview Knowledge Base
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Run:  python app.py
Open: http://localhost:5000

pip install flask flask-jwt-extended bcrypt python-dotenv requests flask-limiter
"""

import os
from datetime import timedelta

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, jsonify
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from db    import get_db
from auth  import hash_password
from routes import auth_bp, notes_bp, topics_bp, data_bp
from routes.images import images_bp

# ── App setup ─────────────────────────────────────────────────────

app = Flask(__name__)
app.config["SECRET_KEY"]               = os.getenv("FLASK_SECRET_KEY", "dev-secret")
app.config["JWT_SECRET_KEY"]           = os.getenv("JWT_SECRET_KEY",   "jwt-secret")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=12)
app.config["JWT_TOKEN_LOCATION"]       = ["headers", "cookies"]
app.config["JWT_COOKIE_SECURE"]        = False   # True khi production + HTTPS
app.config["JWT_COOKIE_CSRF_PROTECT"]  = False

jwt = JWTManager(app)

@jwt.unauthorized_loader
def unauthorized_callback(_reason):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Chưa đăng nhập"}), 401
    from flask import redirect
    return redirect("/login")

# ── Rate limiting ─────────────────────────────────────────────────
# Giới hạn brute-force login và OTP request
# Mặc định dùng memory storage (đủ cho single-process)
# Production: RATELIMIT_STORAGE_URI=redis://localhost:6379
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
    storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
)

# Áp rate limit cho auth endpoints quan trọng
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

@app.route("/api/image-proxy")
def image_proxy():
    """Proxy ảnh ngoài để tránh CORS khi export PDF."""
    import requests as _req
    from flask import Response, abort
    url = request.args.get("url", "").strip()
    if not url or not url.startswith(("http://", "https://")):
        abort(400)
    try:
        r = _req.get(url, timeout=10,
                     headers={"User-Agent": "Mozilla/5.0"},
                     stream=True)
        ct = r.headers.get("Content-Type", "image/png")
        return Response(r.content, content_type=ct,
                        headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e:
        print(f"[image-proxy] lỗi: {e}")
        abort(502)


# ── Ensure admin user exists ──────────────────────────────────────

def ensure_admin():
    db       = get_db()
    username = os.getenv("ADMIN_USERNAME", "admin")
    if not db.get_user(username):
        password = os.getenv("ADMIN_PASSWORD", "changeme123")
        email    = os.getenv("ADMIN_EMAIL",    "admin@devnotes.local")
        db.create_user(username, email, hash_password(password), role="admin")
        print(f"✅ Admin user tạo: {username}")


# ── Main ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    ensure_admin()

    db = get_db()
    if not db.get_notes():
        from seed import seed_data
        seed_data()

    print("🚀 DevNotes chạy tại: http://localhost:5000")
    app.run(debug=True, port=5000, host="0.0.0.0")
