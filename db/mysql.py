"""
db/mysql.py — MySQL backend
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Kích hoạt khi DATABASE_URL bắt đầu bằng mysql:// hoặc mysql+pymysql://
Cài thêm: pip install pymysql
"""

from contextlib import contextmanager
from urllib.parse import urlparse

from config import settings
from db._shared import build_sql_backend

_parsed = urlparse(settings.DATABASE_URL.replace("mysql+pymysql://", "mysql://"))


@contextmanager
def get_conn():
    import pymysql
    import pymysql.cursors

    conn = pymysql.connect(
        host=_parsed.hostname,
        port=_parsed.port or 3306,
        user=_parsed.username,
        password=_parsed.password,
        database=_parsed.path.lstrip("/"),
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
    """Tạo bảng và migration cho MySQL."""
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
                data       LONGBLOB,
                mime       VARCHAR(100),
                created_at TEXT,
                INDEX idx_images_note (note_id)
            )""",
        ]:
            conn.execute(ddl)

    # Migration: thêm các cột nếu chưa có (handle DB cũ có schema khác)
    for col, definition in [
        ("filename",   "VARCHAR(300)"),
        ("folder",     "VARCHAR(50) NOT NULL DEFAULT 'uploads'"),
        ("note_id",    "VARCHAR(100)"),
        ("data",       "LONGBLOB"),
        ("mime",       "VARCHAR(100)"),
        ("created_at", "TEXT"),
    ]:
        try:
            with get_conn() as conn:
                conn.execute(f"ALTER TABLE images ADD COLUMN IF NOT EXISTS {col} {definition}")
                print(f"  ↳ Migrated: images.{col} added (MySQL)")
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                print(f"  ↳ MySQL migration skipped ({col}): {e}")
    # UNIQUE INDEX trên filename (MySQL không hỗ trợ partial index, nên
    # chỉ tạo nếu chưa có. Nếu DB legacy có row filename NULL thì OK,
    # NULL không bị unique constraint reject).
    try:
        with get_conn() as conn:
            conn.execute("CREATE UNIQUE INDEX idx_images_filename ON images(filename)")
            print("  ↳ Migrated: UNIQUE idx_images_filename (MySQL)")
    except Exception as e:
        # MySQL không có IF NOT EXISTS cho CREATE INDEX trước 8.0.
        # Nếu đã tồn tại / duplicate key, bỏ qua êm.
        msg = str(e).lower()
        if "duplicate" not in msg and "exists" not in msg:
            print(f"  ↳ MySQL UNIQUE index trên images.filename skipped: {e}")

    print(f"✅ MySQL: {_parsed.hostname}/{_parsed.path.lstrip('/')}")


def create_backend():
    """Khởi tạo và trả về dict CRUD functions."""
    init()
    return build_sql_backend(get_conn, P="%s")
