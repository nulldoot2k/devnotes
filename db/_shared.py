"""
db/_shared.py — CRUD helpers dùng chung cho SQLite / PostgreSQL / MySQL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P  = placeholder: '?' cho SQLite/MySQL-pymysql, '%s' cho PostgreSQL.
"""

import json
from datetime import datetime

from config import settings


def _now() -> str:
    return datetime.now().isoformat()


def build_sql_backend(get_conn, P: str = "?"):
    """
    Nhận get_conn (context manager kết nối DB) và placeholder P,
    trả về dict chứa tất cả hàm CRUD.
    """
    OWNER_MODE = settings.OWNER_MODE

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

    # ── Notes ──────────────────────────────────────────────────────

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

    # ── Topics ─────────────────────────────────────────────────────

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

    # ── Users ──────────────────────────────────────────────────────

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

    # ── OTP ────────────────────────────────────────────────────────

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

    # ── Images ─────────────────────────────────────────────────────

    def track_image(filename, folder="uploads", note_id=None):
        with get_conn() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO images (filename, folder, note_id, created_at)"
                f" VALUES ({P},{P},{P},{P})",
                (filename, folder, str(note_id) if note_id else None, _now())
            )

    def untrack_image(filename):
        with get_conn() as conn:
            conn.execute(f"DELETE FROM images WHERE filename = {P}", (filename,))

    def get_tracked_images(note_id=None):
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
