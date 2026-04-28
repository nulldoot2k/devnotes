"""
db.py — Database layer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ưu tiên detect backend từ env:
  1. MONGO_URI       → MongoDB (nếu connect được)
  2. DATABASE_URL    → PostgreSQL hoặc MySQL
  3. (không khai báo) → SQLite (mặc định, lưu file)

Multi-user ready:
  - notes, topics đều có owner_id (= username)
  - OWNER_MODE=single (default) → tất cả dùng chung 1 pool
  - OWNER_MODE=multi  → mỗi user chỉ thấy data của mình

Image tracking:
  - Bảng images lưu metadata từng file ảnh (filename, folder, note_id)
  - track_image / untrack_image được gọi từ image_cache.py
"""

import os
import json
from pathlib import Path
from datetime import datetime

# ── Config ───────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
DATA_DIR     = BASE_DIR / "data"
DB_PATH      = DATA_DIR / "devnotes.db"
JSON_PATH    = DATA_DIR / "notes.json"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
MONGO_URI    = os.getenv("MONGO_URI",    "").strip()
MONGO_DB     = os.getenv("MONGO_DB",     "devnotes")
OWNER_MODE   = os.getenv("OWNER_MODE",   "single")   # "single" | "multi"

USE_MONGO    = bool(MONGO_URI)
USE_POSTGRES = not USE_MONGO and DATABASE_URL.startswith(("postgresql://", "postgres://"))
USE_MYSQL    = not USE_MONGO and DATABASE_URL.startswith(("mysql://", "mysql+pymysql://"))
USE_SQLITE   = not (USE_MONGO or USE_POSTGRES or USE_MYSQL)


def _now() -> str:
    return datetime.now().isoformat()


# ════════════════════════════════════════════════════════════════
#  SQLite backend
# ════════════════════════════════════════════════════════════════

def _sqlite_backend():
    import sqlite3
    from contextlib import contextmanager

    @contextmanager
    def get_conn():
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _existing_columns(conn, table):
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {row["name"] for row in rows}

    def init():
        with get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    username   TEXT UNIQUE NOT NULL,
                    email      TEXT UNIQUE NOT NULL,
                    password   TEXT NOT NULL,
                    role       TEXT NOT NULL DEFAULT 'user',
                    created_at TEXT DEFAULT (datetime('now')),
                    last_login TEXT
                );
                CREATE TABLE IF NOT EXISTS topics (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id   TEXT NOT NULL DEFAULT '__shared__',
                    name       TEXT NOT NULL,
                    color      TEXT NOT NULL DEFAULT '#4fffb0',
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS notes (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id   TEXT NOT NULL DEFAULT '__shared__',
                    question   TEXT NOT NULL,
                    content    TEXT NOT NULL,
                    topic_id   INTEGER REFERENCES topics(id) ON DELETE SET NULL,
                    tags       TEXT DEFAULT '[]',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS otp_tokens (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    username   TEXT NOT NULL,
                    token      TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used       INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS images (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename   TEXT UNIQUE NOT NULL,
                    folder     TEXT NOT NULL DEFAULT 'uploads',
                    note_id    TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
            """)

            # === MIGRATION AN TOÀN ===
            migrations = [
                ("users",  "role",     "TEXT NOT NULL DEFAULT 'user'"),
                ("notes",  "owner_id", "TEXT NOT NULL DEFAULT '__shared__'"),
                ("topics", "owner_id", "TEXT NOT NULL DEFAULT '__shared__'"),
                ("images", "note_id",  "TEXT"),                    # ← Đây là cột gây lỗi
            ]
            for table, col, definition in migrations:
                cols = _existing_columns(conn, table)
                if col not in cols:
                    try:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
                        print(f"  ↳ Migrated: Added {table}.{col}")
                    except sqlite3.OperationalError as e:
                        if "duplicate column" not in str(e).lower():
                            raise
                        print(f"  ↳ {table}.{col} already exists (skipped)")

            # Migration otp_tokens (nếu cần)
            otp_cols = _existing_columns(conn, "otp_tokens")
            if "username" not in otp_cols:
                if "email" in otp_cols:
                    print("  ↳ Migrating otp_tokens: email → username")
                    conn.executescript("""
                        ALTER TABLE otp_tokens RENAME TO otp_tokens_old;
                        CREATE TABLE otp_tokens (
                            id         INTEGER PRIMARY KEY AUTOINCREMENT,
                            username   TEXT NOT NULL,
                            token      TEXT NOT NULL,
                            expires_at TEXT NOT NULL,
                            used       INTEGER DEFAULT 0
                        );
                        INSERT INTO otp_tokens (id, username, token, expires_at, used)
                            SELECT id, email, token, expires_at, used FROM otp_tokens_old;
                        DROP TABLE otp_tokens_old;
                    """)
                else:
                    conn.execute("ALTER TABLE otp_tokens ADD COLUMN username TEXT NOT NULL DEFAULT ''")

            # Index
            conn.executescript("""
                CREATE INDEX IF NOT EXISTS idx_notes_owner  ON notes(owner_id);
                CREATE INDEX IF NOT EXISTS idx_notes_topic  ON notes(topic_id);
                CREATE INDEX IF NOT EXISTS idx_topics_owner ON topics(owner_id);
                CREATE INDEX IF NOT EXISTS idx_images_note  ON images(note_id);
            """)

        print(f"✅ SQLite database ready: {DB_PATH}")

    return get_conn, init


# ════════════════════════════════════════════════════════════════
#  SQL CRUD helpers — dùng chung cho SQLite / PostgreSQL / MySQL
# ════════════════════════════════════════════════════════════════

def _sql_backend(get_conn, P: str = "?"):
    """P = placeholder: '?' SQLite/MySQL-pymysql, '%s' PostgreSQL."""

    def _note(row) -> dict:
        r = dict(row)
        return {
            "id":        r["id"],
            "question":  r["question"],
            "content":   r["content"],
            "topic":     r.get("topic_id"),
            "tags":      json.loads(r.get("tags") or "[]"),
            "createdAt": r.get("created_at"),
            "updatedAt": r.get("updated_at"),
        }

    def _topic(row) -> dict:
        r = dict(row)
        return {"id": r["id"], "name": r["name"], "color": r["color"]}

    def _owner_clause(owner_id, alias=""):
        tbl = f"{alias}." if alias else ""
        if OWNER_MODE == "multi" and owner_id:
            return f" AND {tbl}owner_id = {P}", [owner_id]
        return "", []

    # ── Notes ──────────────────────────────────────────────────
    def get_notes(q="", topic_id=None, owner_id=None):
        own_sql, own_p = _owner_clause(owner_id)
        sql    = f"SELECT * FROM notes WHERE 1=1{own_sql}"
        params = list(own_p)
        if topic_id is not None:
            sql += f" AND topic_id = {P}"; params.append(topic_id)
        if q:
            like = f"%{q.lower()}%"
            sql += (f" AND (LOWER(question) LIKE {P}"
                    f" OR LOWER(content) LIKE {P}"
                    f" OR LOWER(tags) LIKE {P})")
            params += [like, like, like]
        sql += " ORDER BY updated_at DESC"
        with get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_note(r) for r in rows]

    def get_note(note_id):
        with get_conn() as conn:
            row = conn.execute(
                f"SELECT * FROM notes WHERE id = {P}", (note_id,)
            ).fetchone()
        return _note(row) if row else None

    def create_note(question, content, topic_id=None, tags=None, owner_id="__shared__"):
        now = _now()
        with get_conn() as conn:
            cur = conn.execute(
                f"INSERT INTO notes (owner_id,question,content,topic_id,tags,created_at,updated_at)"
                f" VALUES ({P},{P},{P},{P},{P},{P},{P})",
                (owner_id, question, content, topic_id,
                 json.dumps(tags or [], ensure_ascii=False), now, now)
            )
            row = conn.execute(
                f"SELECT * FROM notes WHERE id = {P}", (cur.lastrowid,)
            ).fetchone()
        return _note(row)

    def update_note(note_id, **fields):
        note = get_note(note_id)
        if not note:
            return None
        now = _now()
        with get_conn() as conn:
            conn.execute(
                f"UPDATE notes SET question={P},content={P},topic_id={P},"
                f"tags={P},updated_at={P} WHERE id={P}",
                (fields.get("question", note["question"]),
                 fields.get("content",  note["content"]),
                 fields.get("topic_id", note["topic"]),
                 json.dumps(fields.get("tags", note["tags"]), ensure_ascii=False),
                 now, note_id)
            )
            row = conn.execute(
                f"SELECT * FROM notes WHERE id = {P}", (note_id,)
            ).fetchone()
        return _note(row)

    def delete_note(note_id):
        with get_conn() as conn:
            cur = conn.execute(f"DELETE FROM notes WHERE id = {P}", (note_id,))
        return cur.rowcount > 0

    # ── Topics ─────────────────────────────────────────────────
    def get_topics(owner_id=None):
        own_sql, own_p = _owner_clause(owner_id)
        sql = f"SELECT * FROM topics WHERE 1=1{own_sql} ORDER BY name"
        with get_conn() as conn:
            rows = conn.execute(sql, own_p).fetchall()
        return [_topic(r) for r in rows]

    def get_topic_by_name(name, owner_id=None):
        own_sql, own_p = _owner_clause(owner_id)
        with get_conn() as conn:
            row = conn.execute(
                f"SELECT * FROM topics WHERE LOWER(name)=LOWER({P}){own_sql}",
                [name] + list(own_p)
            ).fetchone()
        return _topic(row) if row else None

    def create_topic(name, color="#4fffb0", owner_id="__shared__"):
        with get_conn() as conn:
            cur = conn.execute(
                f"INSERT INTO topics (owner_id,name,color) VALUES ({P},{P},{P})",
                (owner_id, name, color)
            )
            row = conn.execute(
                f"SELECT * FROM topics WHERE id = {P}", (cur.lastrowid,)
            ).fetchone()
        return _topic(row)

    def delete_topic(topic_id):
        with get_conn() as conn:
            cur = conn.execute(f"DELETE FROM topics WHERE id = {P}", (topic_id,))
        return cur.rowcount > 0

    # ── Users ──────────────────────────────────────────────────
    def get_user(username):
        with get_conn() as conn:
            row = conn.execute(
                f"SELECT * FROM users WHERE username = {P}", (username,)
            ).fetchone()
        return dict(row) if row else None

    def get_user_by_email(email):
        with get_conn() as conn:
            row = conn.execute(
                f"SELECT * FROM users WHERE LOWER(email) = LOWER({P})", (email,)
            ).fetchone()
        return dict(row) if row else None

    def create_user(username, email, hashed_pw, role="user"):
        with get_conn() as conn:
            cur = conn.execute(
                f"INSERT INTO users (username,email,password,role) VALUES ({P},{P},{P},{P})",
                (username, email, hashed_pw, role)
            )
            row = conn.execute(
                f"SELECT * FROM users WHERE id = {P}", (cur.lastrowid,)
            ).fetchone()
        return dict(row)

    def update_password(username, hashed_pw):
        with get_conn() as conn:
            conn.execute(
                f"UPDATE users SET password = {P} WHERE username = {P}",
                (hashed_pw, username)
            )

    def update_last_login(username):
        with get_conn() as conn:
            conn.execute(
                f"UPDATE users SET last_login = {P} WHERE username = {P}",
                (_now(), username)
            )

    # ── OTP ────────────────────────────────────────────────────
    def save_otp(username, token, expires_at):
        with get_conn() as conn:
            conn.execute(f"DELETE FROM otp_tokens WHERE username = {P}", (username,))
            conn.execute(
                f"INSERT INTO otp_tokens (username,token,expires_at) VALUES ({P},{P},{P})",
                (username, token, expires_at)
            )

    def verify_otp(username, token):
        now = _now()
        with get_conn() as conn:
            row = conn.execute(
                f"SELECT * FROM otp_tokens"
                f" WHERE username={P} AND token={P} AND used=0 AND expires_at>{P}",
                (username, token, now)
            ).fetchone()
            if row:
                conn.execute(
                    f"UPDATE otp_tokens SET used=1 WHERE id={P}", (row["id"],)
                )
                return True
        return False

    # ── Images ─────────────────────────────────────────────────
    def track_image(filename, folder="uploads", note_id=None):
        """Ghi nhận ảnh đã được persist vào DB."""
        with get_conn() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO images (filename, folder, note_id, created_at)"
                f" VALUES ({P},{P},{P},{P})",
                (filename, folder, str(note_id) if note_id else None, _now())
            )

    def untrack_image(filename):
        """Xóa record ảnh khỏi DB."""
        with get_conn() as conn:
            conn.execute(f"DELETE FROM images WHERE filename = {P}", (filename,))

    def get_tracked_images(note_id=None):
        """Lấy danh sách ảnh đã được track. Nếu note_id thì lọc theo note."""
        with get_conn() as conn:
            if note_id:
                rows = conn.execute(
                    f"SELECT * FROM images WHERE note_id = {P}", (str(note_id),)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM images").fetchall()
        return [dict(r) for r in rows]

    return dict(
        get_notes=get_notes, get_note=get_note,
        create_note=create_note, update_note=update_note, delete_note=delete_note,
        get_topics=get_topics, get_topic_by_name=get_topic_by_name,
        create_topic=create_topic, delete_topic=delete_topic,
        get_user=get_user, get_user_by_email=get_user_by_email,
        create_user=create_user, update_password=update_password,
        update_last_login=update_last_login,
        save_otp=save_otp, verify_otp=verify_otp,
        track_image=track_image, untrack_image=untrack_image,
        get_tracked_images=get_tracked_images,
    )


# ════════════════════════════════════════════════════════════════
#  PostgreSQL backend
# ════════════════════════════════════════════════════════════════

def _postgres_backend():
    import psycopg2
    import psycopg2.extras
    from contextlib import contextmanager

    @contextmanager
    def get_conn():
        conn = psycopg2.connect(
            DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor
        )
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init():
        with get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id         SERIAL PRIMARY KEY,
                    username   TEXT UNIQUE NOT NULL,
                    email      TEXT UNIQUE NOT NULL,
                    password   TEXT NOT NULL,
                    role       TEXT NOT NULL DEFAULT 'user',
                    created_at TEXT,
                    last_login TEXT
                );
                CREATE TABLE IF NOT EXISTS topics (
                    id         SERIAL PRIMARY KEY,
                    owner_id   TEXT NOT NULL DEFAULT '__shared__',
                    name       TEXT NOT NULL,
                    color      TEXT NOT NULL DEFAULT '#4fffb0',
                    created_at TEXT,
                    UNIQUE(owner_id, name)
                );
                CREATE TABLE IF NOT EXISTS notes (
                    id         SERIAL PRIMARY KEY,
                    owner_id   TEXT NOT NULL DEFAULT '__shared__',
                    question   TEXT NOT NULL,
                    content    TEXT NOT NULL,
                    topic_id   INTEGER REFERENCES topics(id) ON DELETE SET NULL,
                    tags       TEXT DEFAULT '[]',
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_notes_owner  ON notes(owner_id);
                CREATE INDEX IF NOT EXISTS idx_notes_topic  ON notes(topic_id);
                CREATE INDEX IF NOT EXISTS idx_topics_owner ON topics(owner_id);
                CREATE TABLE IF NOT EXISTS otp_tokens (
                    id         SERIAL PRIMARY KEY,
                    username   TEXT NOT NULL,
                    token      TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used       INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS images (
                    id         SERIAL PRIMARY KEY,
                    filename   TEXT UNIQUE NOT NULL,
                    folder     TEXT NOT NULL DEFAULT 'uploads',
                    note_id    TEXT,
                    created_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_images_note ON images(note_id);
            """)

        # === MIGRATION: Thêm cột note_id nếu chưa có ===
        try:
            with get_conn() as conn:
                conn.execute("ALTER TABLE images ADD COLUMN IF NOT EXISTS note_id TEXT")
                print("  ↳ Migrated: images.note_id added (PostgreSQL)")
        except Exception as e:
            if "already exists" not in str(e).lower():
                print(f"  ↳ PostgreSQL migration note_id skipped: {e}")

        print(f"✅ PostgreSQL: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")

    return get_conn, init


# ════════════════════════════════════════════════════════════════
#  MySQL backend
# ════════════════════════════════════════════════════════════════

def _mysql_backend():
    import pymysql
    import pymysql.cursors
    from contextlib import contextmanager
    from urllib.parse import urlparse

    parsed = urlparse(DATABASE_URL.replace("mysql+pymysql://", "mysql://"))

    @contextmanager
    def get_conn():
        conn = pymysql.connect(
            host=parsed.hostname,
            port=parsed.port or 3306,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path.lstrip("/"),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init():
        with get_conn() as conn:
            for ddl in [
                """CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username   VARCHAR(100) UNIQUE NOT NULL,
                    email      VARCHAR(200) UNIQUE NOT NULL,
                    password   TEXT NOT NULL,
                    role       VARCHAR(20) NOT NULL DEFAULT 'user',
                    created_at TEXT,
                    last_login TEXT
                )""",
                """CREATE TABLE IF NOT EXISTS topics (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    owner_id   VARCHAR(100) NOT NULL DEFAULT '__shared__',
                    name       VARCHAR(200) NOT NULL,
                    color      VARCHAR(20)  NOT NULL DEFAULT '#4fffb0',
                    created_at TEXT,
                    UNIQUE KEY uq_owner_topic (owner_id, name)
                )""",
                """CREATE TABLE IF NOT EXISTS notes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    owner_id   VARCHAR(100) NOT NULL DEFAULT '__shared__',
                    question   TEXT NOT NULL,
                    content    LONGTEXT NOT NULL,
                    topic_id   INT,
                    tags       TEXT DEFAULT '[]',
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE SET NULL
                )""",
                """CREATE TABLE IF NOT EXISTS otp_tokens (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username   VARCHAR(100) NOT NULL,
                    token      VARCHAR(20)  NOT NULL,
                    expires_at TEXT NOT NULL,
                    used       TINYINT DEFAULT 0
                )""",
                """CREATE TABLE IF NOT EXISTS images (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    filename   VARCHAR(300) UNIQUE NOT NULL,
                    folder     VARCHAR(50)  NOT NULL DEFAULT 'uploads',
                    note_id    VARCHAR(100),
                    created_at TEXT,
                    INDEX idx_images_note (note_id)
                )""",
            ]:
                conn.execute(ddl)

        # === MIGRATION: Thêm cột note_id nếu chưa có ===
        try:
            with get_conn() as conn:
                conn.execute("ALTER TABLE images ADD COLUMN IF NOT EXISTS note_id VARCHAR(100)")
                print("  ↳ Migrated: images.note_id added (MySQL)")
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                print(f"  ↳ MySQL migration note_id skipped: {e}")

        print(f"✅ MySQL: {parsed.hostname}/{parsed.path.lstrip('/')}")

    return get_conn, init


# ════════════════════════════════════════════════════════════════
#  MongoDB backend
# ════════════════════════════════════════════════════════════════

def _mongo_backend():
    from pymongo import MongoClient, ASCENDING, DESCENDING
    from bson import ObjectId

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    # Ping để kiểm tra connection ngay lập tức
    client.admin.command("ping")

    mdb    = client[MONGO_DB]
    users  = mdb["users"]
    topics = mdb["topics"]
    notes  = mdb["notes"]
    otps   = mdb["otp_tokens"]
    images = mdb["images"]

    def init():
        users.create_index("username",  unique=True)
        users.create_index("email",     unique=True)
        topics.create_index([("owner_id", ASCENDING), ("name", ASCENDING)], unique=True)
        notes.create_index("owner_id")
        notes.create_index("topic_id")
        notes.create_index([("updated_at", DESCENDING)])
        otps.create_index("username")
        images.create_index("filename", unique=True)
        images.create_index("note_id")
        print(f"✅ MongoDB: {MONGO_URI.split('@')[-1] if '@' in MONGO_URI else MONGO_URI} / {MONGO_DB}")

    def _note(doc):
        if not doc:
            return None
        return {
            "id":        str(doc["_id"]),
            "question":  doc["question"],
            "content":   doc["content"],
            "topic":     doc.get("topic_id"),
            "tags":      doc.get("tags", []),
            "createdAt": doc.get("created_at"),
            "updatedAt": doc.get("updated_at"),
        }

    def _topic(doc):
        if not doc:
            return None
        return {"id": str(doc["_id"]), "name": doc["name"], "color": doc.get("color", "#4fffb0")}

    def _user(doc):
        if not doc:
            return None
        d = dict(doc)
        d["id"] = str(d.pop("_id"))
        return d

    def _owner_filter(owner_id):
        if OWNER_MODE == "multi" and owner_id:
            return {"owner_id": owner_id}
        return {}

    def get_notes(q="", topic_id=None, owner_id=None):
        filt = _owner_filter(owner_id)
        if topic_id:
            filt["topic_id"] = str(topic_id)
        if q:
            regex = {"$regex": q, "$options": "i"}
            filt["$or"] = [
                {"question": regex},
                {"content":  regex},
                {"tags":     regex},
            ]
        return [_note(d) for d in notes.find(filt).sort([("updated_at", DESCENDING)])]

    def get_note(note_id):
        try:
            return _note(notes.find_one({"_id": ObjectId(note_id)}))
        except Exception:
            return None

    def create_note(question, content, topic_id=None, tags=None, owner_id="__shared__"):
        now = _now()
        doc = {
            "owner_id": owner_id,
            "question": question, "content": content,
            "topic_id": str(topic_id) if topic_id else None,
            "tags": tags or [], "created_at": now, "updated_at": now,
        }
        doc["_id"] = notes.insert_one(doc).inserted_id
        return _note(doc)

    def update_note(note_id, **fields):
        n = get_note(note_id)
        if not n:
            return None
        upd = {
            "question":   fields.get("question", n["question"]),
            "content":    fields.get("content",  n["content"]),
            "topic_id":   str(fields["topic_id"]) if fields.get("topic_id") else None,
            "tags":       fields.get("tags", n["tags"]),
            "updated_at": _now(),
        }
        try:
            notes.update_one({"_id": ObjectId(note_id)}, {"$set": upd})
        except Exception:
            return None
        return get_note(note_id)

    def delete_note(note_id):
        try:
            return notes.delete_one({"_id": ObjectId(note_id)}).deleted_count > 0
        except Exception:
            return False

    def get_topics(owner_id=None):
        filt = _owner_filter(owner_id)
        return [_topic(d) for d in topics.find(filt).sort([("name", ASCENDING)])]

    def get_topic_by_name(name, owner_id=None):
        filt = _owner_filter(owner_id)
        filt["name"] = {"$regex": f"^{name}$", "$options": "i"}
        return _topic(topics.find_one(filt))

    def create_topic(name, color="#4fffb0", owner_id="__shared__"):
        doc = {"owner_id": owner_id, "name": name, "color": color, "created_at": _now()}
        doc["_id"] = topics.insert_one(doc).inserted_id
        return _topic(doc)

    def delete_topic(topic_id):
        try:
            notes.update_many({"topic_id": str(topic_id)}, {"$set": {"topic_id": None}})
            return topics.delete_one({"_id": ObjectId(topic_id)}).deleted_count > 0
        except Exception:
            return False

    def get_user(username):
        return _user(users.find_one({"username": username}))

    def get_user_by_email(email):
        return _user(users.find_one({"email": {"$regex": f"^{email}$", "$options": "i"}}))

    def create_user(username, email, hashed_pw, role="user"):
        doc = {
            "username": username, "email": email, "password": hashed_pw,
            "role": role, "created_at": _now(), "last_login": None,
        }
        doc["_id"] = users.insert_one(doc).inserted_id
        return _user(doc)

    def update_password(username, hashed_pw):
        users.update_one({"username": username}, {"$set": {"password": hashed_pw}})

    def update_last_login(username):
        users.update_one({"username": username}, {"$set": {"last_login": _now()}})

    def save_otp(username, token, expires_at):
        otps.delete_many({"username": username})
        otps.insert_one({"username": username, "token": token,
                         "expires_at": expires_at, "used": False})

    def verify_otp(username, token):
        doc = otps.find_one({
            "username": username, "token": token,
            "used": False, "expires_at": {"$gt": _now()},
        })
        if doc:
            otps.update_one({"_id": doc["_id"]}, {"$set": {"used": True}})
            return True
        return False

    # ── Images (MongoDB) ───────────────────────────────────────
    def track_image(filename, folder="uploads", note_id=None):
        images.update_one(
            {"filename": filename},
            {"$set": {
                "filename":   filename,
                "folder":     folder,
                "note_id":    str(note_id) if note_id else None,
                "created_at": _now(),
            }},
            upsert=True,
        )

    def untrack_image(filename):
        images.delete_one({"filename": filename})

    def get_tracked_images(note_id=None):
        filt = {"note_id": str(note_id)} if note_id else {}
        return list(images.find(filt, {"_id": 0}))

    return init, dict(
        get_notes=get_notes, get_note=get_note,
        create_note=create_note, update_note=update_note, delete_note=delete_note,
        get_topics=get_topics, get_topic_by_name=get_topic_by_name,
        create_topic=create_topic, delete_topic=delete_topic,
        get_user=get_user, get_user_by_email=get_user_by_email,
        create_user=create_user, update_password=update_password,
        update_last_login=update_last_login,
        save_otp=save_otp, verify_otp=verify_otp,
        track_image=track_image, untrack_image=untrack_image,
        get_tracked_images=get_tracked_images,
    )


# ════════════════════════════════════════════════════════════════
#  Database facade
# ════════════════════════════════════════════════════════════════

class Database:
    def __init__(self):
        # ── MongoDB: thử connect, nếu fail thì fallback SQLite ──
        if USE_MONGO:
            try:
                init_fn, self._fns = _mongo_backend()
                init_fn()
                self._backend = "mongodb"
                # Đồng bộ dữ liệu từ SQLite/JSON nếu Mongo đang rỗng
                self._sync_from_sql_if_empty()
            except Exception as e:
                print(f"⚠️  MongoDB connect thất bại ({e}), fallback → SQLite")
                get_conn, init_fn = _sqlite_backend()
                init_fn()
                self._fns    = _sql_backend(get_conn, P="?")
                self._backend = "sqlite"
                self._migrate_json_if_needed(get_conn, "?")

        elif USE_POSTGRES:
            get_conn, init_fn = _postgres_backend()
            init_fn()
            self._fns    = _sql_backend(get_conn, P="%s")
            self._backend = "postgresql"
            self._migrate_json_if_needed(get_conn, "%s")

        elif USE_MYSQL:
            get_conn, init_fn = _mysql_backend()
            init_fn()
            self._fns    = _sql_backend(get_conn, P="%s")
            self._backend = "mysql"
            self._migrate_json_if_needed(get_conn, "%s")

        else:
            get_conn, init_fn = _sqlite_backend()
            init_fn()
            self._fns    = _sql_backend(get_conn, P="?")
            self._backend = "sqlite"
            self._migrate_json_if_needed(get_conn, "?")

    # ── Sync SQLite → MongoDB khi Mongo rỗng ─────────────────────
    def _sync_from_sql_if_empty(self):
        """
        Nếu MongoDB đang rỗng (0 notes) nhưng SQLite có dữ liệu,
        đổ toàn bộ dữ liệu từ SQLite sang MongoDB.
        Gọi 1 lần duy nhất lúc khởi động khi dùng MongoDB.
        """
        mongo_notes = self._fns["get_notes"]()
        if mongo_notes:
            return  # Mongo đã có data → không cần sync

        # Kiểm tra SQLite có data không
        if not DB_PATH.exists():
            # Thử đọc từ JSON
            self._sync_from_json_if_empty()
            return

        try:
            import sqlite3
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            count = conn.execute("SELECT COUNT(*) as c FROM notes").fetchone()["c"]
            if count == 0:
                conn.close()
                self._sync_from_json_if_empty()
                return

            print(f"📦 Syncing SQLite ({count} notes) → MongoDB…")

            # Đọc topics
            sql_topics = [dict(r) for r in conn.execute("SELECT * FROM topics").fetchall()]
            # Đọc notes
            sql_notes  = [dict(r) for r in conn.execute("SELECT * FROM notes").fetchall()]
            # Đọc users (ngoại trừ password không sync nếu đã có trong Mongo)
            sql_users  = [dict(r) for r in conn.execute("SELECT * FROM users").fetchall()]
            conn.close()

            # Map topic id cũ → id mới trong Mongo
            topic_id_map = {}
            create_topic = self._fns["create_topic"]
            get_topic_by_name = self._fns["get_topic_by_name"]

            for t in sql_topics:
                existing = get_topic_by_name(t["name"], owner_id=t.get("owner_id"))
                if existing:
                    topic_id_map[str(t["id"])] = existing["id"]
                else:
                    new_t = create_topic(
                        t["name"],
                        t.get("color", "#4fffb0"),
                        t.get("owner_id", "__shared__"),
                    )
                    topic_id_map[str(t["id"])] = new_t["id"]

            # Sync notes
            create_note = self._fns["create_note"]
            for n in sql_notes:
                old_topic_id = str(n["topic_id"]) if n.get("topic_id") else None
                new_topic_id = topic_id_map.get(old_topic_id) if old_topic_id else None
                create_note(
                    n["question"], n["content"],
                    new_topic_id,
                    json.loads(n.get("tags") or "[]"),
                    n.get("owner_id", "__shared__"),
                )

            # Sync users
            get_user    = self._fns["get_user"]
            create_user = self._fns["create_user"]
            for u in sql_users:
                if not get_user(u["username"]):
                    create_user(u["username"], u["email"], u["password"], u.get("role", "user"))

            print(f"✅ Sync hoàn tất: {len(sql_notes)} notes, {len(sql_topics)} topics → MongoDB")

        except Exception as e:
            print(f"⚠️  Sync SQLite → MongoDB thất bại: {e}")

    def _sync_from_json_if_empty(self):
        """Đổ dữ liệu từ notes.json vào MongoDB nếu Mongo đang rỗng."""
        if not JSON_PATH.exists():
            return
        try:
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            notes_data  = data.get("notes", [])
            topics_data = data.get("topics", [])
            if not notes_data:
                return
            print(f"📦 Syncing JSON ({len(notes_data)} notes) → MongoDB…")
            added = self.import_bulk(topics_data, notes_data)
            print(f"✅ Sync JSON → MongoDB: {added} notes")
        except Exception as e:
            print(f"⚠️  Sync JSON → MongoDB thất bại: {e}")

    # ── Migrate JSON → SQL (cho SQLite/PG/MySQL) ──────────────────
    def _migrate_json_if_needed(self, get_conn, P):
        if not JSON_PATH.exists():
            return
        with get_conn() as conn:
            row   = conn.execute("SELECT COUNT(*) as c FROM notes").fetchone()
            count = row["c"] if isinstance(row, dict) else row[0]
            if count > 0:
                return

        print("📦 Migrating JSON → DB…")
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        with get_conn() as conn:
            for t in data.get("topics", []):
                try:
                    conn.execute(
                        f"INSERT INTO topics (name,color) VALUES ({P},{P})",
                        (t["name"], t.get("color", "#4fffb0"))
                    )
                except Exception:
                    pass
            rows = conn.execute("SELECT id, name FROM topics").fetchall()
            tmap = {
                (r["name"] if isinstance(r, dict) else r[1]):
                (r["id"]   if isinstance(r, dict) else r[0])
                for r in rows
            }
            old_id_map = {t["id"]: tmap.get(t["name"]) for t in data.get("topics", [])}
            for n in data.get("notes", []):
                now = _now()
                conn.execute(
                    f"INSERT INTO notes (question,content,topic_id,tags,created_at,updated_at)"
                    f" VALUES ({P},{P},{P},{P},{P},{P})",
                    (n["question"], n["content"],
                     old_id_map.get(n.get("topic")),
                     json.dumps(n.get("tags", []), ensure_ascii=False),
                     n.get("createdAt", now), n.get("updatedAt", now))
                )

        JSON_PATH.rename(JSON_PATH.with_suffix(".json.migrated"))
        print(f"✅ Migrated {len(data.get('notes', []))} notes")

    def __getattr__(self, name):
        try:
            return self._fns[name]
        except KeyError:
            raise AttributeError(f"Database has no method '{name}'")

    def export_all(self, owner_id=None) -> dict:
        return {
            "topics": self.get_topics(owner_id=owner_id),
            "notes":  self.get_notes(owner_id=owner_id),
        }

    def import_bulk(self, raw_topics: list, raw_notes: list,
                    owner_id="__shared__") -> int:
        for t in raw_topics:
            if not self.get_topic_by_name(t["name"], owner_id=owner_id):
                self.create_topic(t["name"], t.get("color", "#4fffb0"), owner_id=owner_id)
        added = 0
        for item in raw_notes:
            if not item.get("question") or not item.get("content"):
                continue
            topic_id = None
            rt = item.get("topic")
            if isinstance(rt, str):
                t = (self.get_topic_by_name(rt, owner_id=owner_id)
                     or self.create_topic(rt, owner_id=owner_id))
                topic_id = t["id"]
            elif isinstance(rt, int):
                topic_id = rt
            self.create_note(
                item["question"].strip(), item["content"].strip(),
                topic_id,
                item.get("tags", []) if isinstance(item.get("tags"), list) else [],
                owner_id=owner_id,
            )
            added += 1
        return added


# ── Singleton ────────────────────────────────────────────────────
_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db
