"""
db/__init__.py — Database facade
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tự động chọn backend theo .env:
  MONGO_URI      → db/mongo.py
  DATABASE_URL   → db/postgres.py hoặc db/mysql.py
  (không có gì)  → db/sqlite.py  ← mặc định

Các module khác chỉ cần: from db import get_db
"""

import json
from config import settings


class Database:
    def __init__(self):
        # ── MongoDB ────────────────────────────────────────────
        if settings.USE_MONGO:
            try:
                from db.mongo import create_backend
                self._fns    = create_backend()
                self._backend = "mongodb"
                self._sync_from_sql_if_empty()
            except Exception as e:
                print(f"⚠️  MongoDB connect thất bại ({e}), fallback → SQLite")
                from db.sqlite import create_backend, get_conn
                self._fns     = create_backend()
                self._backend = "sqlite"
                self._migrate_json_if_needed(get_conn, "?")

        # ── PostgreSQL ─────────────────────────────────────────
        elif settings.USE_POSTGRES:
            from db.postgres import create_backend, get_conn
            self._fns     = create_backend()
            self._backend = "postgresql"
            self._migrate_json_if_needed(get_conn, "%s")

        # ── MySQL ──────────────────────────────────────────────
        elif settings.USE_MYSQL:
            from db.mysql import create_backend, get_conn
            self._fns     = create_backend()
            self._backend = "mysql"
            self._migrate_json_if_needed(get_conn, "%s")

        # ── SQLite (mặc định) ──────────────────────────────────
        else:
            from db.sqlite import create_backend, get_conn
            self._fns     = create_backend()
            self._backend = "sqlite"
            self._migrate_json_if_needed(get_conn, "?")

    # ── Sync SQLite → MongoDB khi Mongo rỗng ──────────────────────

    def _sync_from_sql_if_empty(self):
        if self._fns["get_notes"]():
            return  # Mongo đã có data

        DB_PATH = settings.DB_PATH
        if not DB_PATH.exists():
            self._sync_from_json_if_empty()
            return

        try:
            import sqlite3
            conn  = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            count = conn.execute("SELECT COUNT(*) as c FROM notes").fetchone()["c"]
            if count == 0:
                conn.close()
                self._sync_from_json_if_empty()
                return

            print(f"📦 Syncing SQLite ({count} notes) → MongoDB…")
            sql_topics = [dict(r) for r in conn.execute("SELECT * FROM topics").fetchall()]
            sql_notes  = [dict(r) for r in conn.execute("SELECT * FROM notes").fetchall()]
            sql_users  = [dict(r) for r in conn.execute("SELECT * FROM users").fetchall()]
            conn.close()

            topic_id_map = {}
            for t in sql_topics:
                existing = self._fns["get_topic_by_name"](t["name"], owner_id=t.get("owner_id"))
                if existing:
                    topic_id_map[str(t["id"])] = existing["id"]
                else:
                    new_t = self._fns["create_topic"](t["name"], t.get("color", "#4fffb0"), t.get("owner_id", "__shared__"))
                    topic_id_map[str(t["id"])] = new_t["id"]

            for n in sql_notes:
                old_tid = str(n["topic_id"]) if n.get("topic_id") else None
                self._fns["create_note"](
                    n["question"], n["content"],
                    topic_id_map.get(old_tid) if old_tid else None,
                    json.loads(n.get("tags") or "[]"),
                    n.get("owner_id", "__shared__"),
                )

            for u in sql_users:
                if not self._fns["get_user"](u["username"]):
                    self._fns["create_user"](u["username"], u["email"], u["password"], u.get("role", "user"))

            print(f"✅ Sync hoàn tất: {len(sql_notes)} notes → MongoDB")
        except Exception as e:
            print(f"⚠️  Sync SQLite → MongoDB thất bại: {e}")

    def _sync_from_json_if_empty(self):
        JSON_PATH = settings.JSON_PATH
        if not JSON_PATH.exists():
            return
        try:
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            notes_data = data.get("notes", [])
            if not notes_data:
                return
            print(f"📦 Syncing JSON ({len(notes_data)} notes) → MongoDB…")
            added = self.import_bulk(data.get("topics", []), notes_data)
            print(f"✅ Sync JSON → MongoDB: {added} notes")
        except Exception as e:
            print(f"⚠️  Sync JSON → MongoDB thất bại: {e}")

    # ── Migrate JSON → SQL (SQLite / Postgres / MySQL) ─────────────

    def _migrate_json_if_needed(self, get_conn, P):
        JSON_PATH = settings.JSON_PATH
        if not JSON_PATH.exists():
            return
        with get_conn() as conn:
            row   = conn.execute("SELECT COUNT(*) as c FROM notes").fetchone()
            count = row["c"] if isinstance(row, dict) else row[0]
            if count > 0:
                return

        print("📦 Migrating JSON → DB…")
        from datetime import datetime
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        now = datetime.now().isoformat()
        with get_conn() as conn:
            for t in data.get("topics", []):
                try:
                    conn.execute(f"INSERT INTO topics (name,color) VALUES ({P},{P})",
                                 (t["name"], t.get("color", "#4fffb0")))
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

    def import_bulk(self, raw_topics: list, raw_notes: list, owner_id="__shared__") -> int:
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


# ── Singleton ─────────────────────────────────────────────────────

_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db
