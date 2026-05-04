"""
db/mongo.py — MongoDB backend
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Kích hoạt khi MONGO_URI được khai báo trong .env
Cài thêm: pip install pymongo
"""

import json
from datetime import datetime

from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId

from config import settings

OWNER_MODE = settings.OWNER_MODE


def _now() -> str:
    return datetime.now().isoformat()


def create_backend():
    """Kết nối MongoDB, tạo index, trả về dict CRUD functions."""
    client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")  # Kiểm tra connection ngay

    mdb    = client[settings.MONGO_DB]
    users  = mdb["users"]
    topics = mdb["topics"]
    notes  = mdb["notes"]
    otps   = mdb["otp_tokens"]
    images = mdb["images"]

    # Tạo index
    users.create_index("username",  unique=True)
    users.create_index("email",     unique=True)
    topics.create_index([("owner_id", ASCENDING), ("name", ASCENDING)], unique=True)
    notes.create_index("owner_id")
    notes.create_index("topic_id")
    notes.create_index([("updated_at", DESCENDING)])
    otps.create_index("username")
    images.create_index("filename", unique=True)
    images.create_index("note_id")

    host = settings.MONGO_URI.split("@")[-1] if "@" in settings.MONGO_URI else settings.MONGO_URI
    print(f"✅ MongoDB: {host} / {settings.MONGO_DB}")

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

    # ── Notes ──────────────────────────────────────────────────────

    def get_notes(q="", topic_id=None, owner_id=None):
        filt = _owner_filter(owner_id)
        if topic_id:
            filt["topic_id"] = str(topic_id)
        if q:
            regex = {"$regex": q, "$options": "i"}
            filt["$or"] = [{"question": regex}, {"content": regex}, {"tags": regex}]
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

    # ── Topics ─────────────────────────────────────────────────────

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

    # ── Users ──────────────────────────────────────────────────────

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

    # ── OTP ────────────────────────────────────────────────────────

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

    # ── Images ─────────────────────────────────────────────────────
    # URL ngoài: /img/<24-char-ObjectId-hex>

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
        return [
            {
                "id":         str(d["_id"]),
                "filename":   d.get("filename"),
                "folder":     d.get("folder"),
                "note_id":    d.get("note_id"),
                "mime":       d.get("mime"),
                "created_at": d.get("created_at"),
            }
            for d in images.find(filt)
        ]

    def upsert_image_bytes(filename, data: bytes, mime: str, note_id=None) -> str:
        from bson.binary import Binary
        nid = str(note_id) if note_id else None
        existing = images.find_one({"filename": filename})
        if existing:
            images.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "data":    Binary(data),
                    "mime":    mime,
                    "note_id": nid,
                }},
            )
            return str(existing["_id"])
        doc = {
            "filename":   filename,
            "folder":     "db",
            "note_id":    nid,
            "data":       Binary(data),
            "mime":       mime,
            "created_at": _now(),
        }
        return str(images.insert_one(doc).inserted_id)

    def get_image_by_id(image_id):
        try:
            oid = ObjectId(str(image_id))
        except Exception:
            return None
        d = images.find_one({"_id": oid})
        if not d or d.get("data") is None:
            return None
        return {
            "data":     bytes(d["data"]),
            "mime":     d.get("mime") or "application/octet-stream",
            "filename": d.get("filename"),
        }

    def delete_image_by_id(image_id):
        try:
            oid = ObjectId(str(image_id))
        except Exception:
            return False
        return images.delete_one({"_id": oid}).deleted_count > 0

    def get_image_id_by_filename(filename):
        if not filename:
            return None
        d = images.find_one({"filename": filename}, {"_id": 1})
        if not d:
            return None
        return str(d["_id"])

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
        upsert_image_bytes=upsert_image_bytes,
        get_image_by_id=get_image_by_id,
        get_image_id_by_filename=get_image_id_by_filename,
        delete_image_by_id=delete_image_by_id,
    )
