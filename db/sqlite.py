"""
db/sqlite.py — SQLite backend
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dùng mặc định khi không khai báo DATABASE_URL hay MONGO_URI.
Lưu dữ liệu vào file data/devnotes.db.
"""

import sqlite3
from contextlib import contextmanager

from config import settings
from db._shared import build_sql_backend

DB_PATH = settings.DB_PATH


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


def _column_specs(conn, table):
    """Trả về dict[name] → (notnull: bool, dflt_value: any, type: str).
    Dùng để phát hiện legacy columns vướng NOT NULL không có default."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {
        row["name"]: (bool(row["notnull"]), row["dflt_value"], row["type"])
        for row in rows
    }


_EXPECTED_IMAGES_COLS = {
    "id", "filename", "folder", "note_id", "data", "mime", "created_at",
}


def _drop_legacy_notnull_images_columns(conn):
    """Phát hiện cột không thuộc schema chuẩn nhưng có NOT NULL không default.
    Mỗi cột như vậy sẽ block INSERT (vd. legacy `mime_type TEXT NOT NULL`).
    Cố gắng DROP chúng (SQLite ≥ 3.35). Nếu không drop được, rebuild bảng."""
    specs = _column_specs(conn, "images")
    legacy = [
        name for name, (notnull, dflt, _t) in specs.items()
        if name not in _EXPECTED_IMAGES_COLS and notnull and dflt is None
    ]
    if not legacy:
        return

    print(f"  ↳ Detected legacy NOT NULL columns in images: {legacy}")
    failed = []
    for col in legacy:
        try:
            conn.execute(f"ALTER TABLE images DROP COLUMN {col}")
            print(f"  ↳ Dropped legacy column images.{col}")
        except sqlite3.OperationalError as e:
            print(f"  ↳ DROP COLUMN images.{col} thất bại: {e}")
            failed.append(col)

    if not failed:
        return

    # Fallback: rebuild bảng. Giữ lại các cột chuẩn, bỏ legacy.
    print("  ↳ Rebuilding images table to drop legacy columns…")
    keep_cols = sorted(_EXPECTED_IMAGES_COLS & set(_column_specs(conn, "images").keys()))
    cols_csv = ", ".join(keep_cols)
    conn.executescript(f"""
        CREATE TABLE images_new (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            filename   TEXT,
            folder     TEXT NOT NULL DEFAULT 'uploads',
            note_id    TEXT,
            data       BLOB,
            mime       TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        INSERT INTO images_new ({cols_csv}) SELECT {cols_csv} FROM images;
        DROP TABLE images;
        ALTER TABLE images_new RENAME TO images;
    """)
    print("  ↳ images table rebuilt successfully")


def init():
    """Tạo bảng và chạy migration nếu cần."""
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
                data       BLOB,
                mime       TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)

        # Migration an toàn: thêm cột nếu thiếu.
        #
        # SQLite ALTER TABLE chỉ cho thêm cột nullable / không có UNIQUE
        # / PRIMARY KEY. Vì vậy cột `filename` thêm dạng nullable, sau đó
        # áp UNIQUE thông qua CREATE UNIQUE INDEX (xem dưới).
        migrations = [
            ("users",  "role",       "TEXT NOT NULL DEFAULT 'user'"),
            ("notes",  "owner_id",   "TEXT NOT NULL DEFAULT '__shared__'"),
            ("topics", "owner_id",   "TEXT NOT NULL DEFAULT '__shared__'"),
            # SQLite ALTER TABLE không cho non-constant default (datetime('now')).
            # Cột `created_at` thêm không default; row mới chỉ phụ thuộc vào
            # CREATE TABLE statement ở trên (đã có default datetime('now')).
            ("images", "filename",   "TEXT"),
            ("images", "folder",     "TEXT NOT NULL DEFAULT 'uploads'"),
            ("images", "note_id",    "TEXT"),
            ("images", "data",       "BLOB"),
            ("images", "mime",       "TEXT"),
            ("images", "created_at", "TEXT"),
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

        # Phát hiện & xử lý cột NOT NULL legacy không thuộc schema chuẩn
        # (vd. mime_type TEXT NOT NULL từ schema custom cũ) — block INSERT.
        _drop_legacy_notnull_images_columns(conn)

        # Migration otp_tokens: email → username
        otp_cols = _existing_columns(conn, "otp_tokens")
        if "username" not in otp_cols:
            if "email" in otp_cols:
                print("  ↳ Migrating otp_tokens: email → username")
                conn.executescript("""
                    ALTER TABLE otp_tokens RENAME TO otp_tokens_old;
                    CREATE TABLE otp_tokens (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
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

        conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_notes_owner  ON notes(owner_id);
            CREATE INDEX IF NOT EXISTS idx_notes_topic  ON notes(topic_id);
            CREATE INDEX IF NOT EXISTS idx_topics_owner ON topics(owner_id);
            CREATE INDEX IF NOT EXISTS idx_images_note  ON images(note_id);
        """)

        # Áp UNIQUE cho images.filename qua INDEX (vì ALTER TABLE không
        # cho thêm UNIQUE inline). Dùng partial index để không reject
        # các row legacy có filename = NULL.
        try:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_images_filename"
                " ON images(filename) WHERE filename IS NOT NULL"
            )
        except sqlite3.OperationalError as e:
            print(f"  ↳ Cảnh báo: không tạo được UNIQUE INDEX cho images.filename: {e}")

    print(f"✅ SQLite database ready: {DB_PATH}")


def create_backend():
    """Khởi tạo và trả về dict CRUD functions."""
    init()
    return build_sql_backend(get_conn, P="?")
