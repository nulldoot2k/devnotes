"""
db/postgres.py — PostgreSQL backend
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Kích hoạt khi DATABASE_URL bắt đầu bằng postgresql:// hoặc postgres://
Cài thêm: pip install psycopg2-binary
"""

from contextlib import contextmanager

from config import settings
from db._shared import build_sql_backend


@contextmanager
def get_conn():
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(
        settings.DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor
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
    """Tạo bảng và migration cho PostgreSQL."""
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
                data       BYTEA,
                mime       TEXT,
                created_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_images_note ON images(note_id);
        """)

    # Migration: thêm các cột nếu chưa có
    for col, definition in [
        ("note_id", "TEXT"),
        ("data",    "BYTEA"),
        ("mime",    "TEXT"),
    ]:
        try:
            with get_conn() as conn:
                conn.execute(f"ALTER TABLE images ADD COLUMN IF NOT EXISTS {col} {definition}")
                print(f"  ↳ Migrated: images.{col} added (PostgreSQL)")
        except Exception as e:
            if "already exists" not in str(e).lower():
                print(f"  ↳ PostgreSQL migration skipped ({col}): {e}")

    db_host = settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else settings.DATABASE_URL
    print(f"✅ PostgreSQL: {db_host}")


def create_backend():
    """Khởi tạo và trả về dict CRUD functions."""
    init()
    return build_sql_backend(get_conn, P="%s")
