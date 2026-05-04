# 📝 DevNotes — Interview Knowledge Base

Ứng dụng quản lý notes phỏng vấn / kiến thức kỹ thuật, viết bằng Python + Flask.
Hỗ trợ nhiều backend lưu trữ: **SQLite** (mặc định), **PostgreSQL**, **MySQL**, **MongoDB** — chọn DB qua biến môi trường.

---

## 🚀 Quick Start (Local)

```bash
# 1. Tạo virtualenv & cài dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Tạo file cấu hình từ template
cp .env.example .env

# 3. Chạy server
python app.py

# 4. Mở browser
http://localhost:5000
```

Lần đầu chạy sẽ tự seed dữ liệu mẫu vào DB và tạo tài khoản admin.

---

## 🐳 Quick Start (Docker)

```bash
# 1. Tạo file cấu hình từ template
cp .env.example .env

# 2. (Tuỳ chọn) Bỏ comment service DB cần dùng trong docker-compose.yml

# 3. Khởi chạy stack
docker-compose up -d

# 4. Mở browser
http://localhost:5000
```

---

## 👤 Tài khoản admin mặc định

Tài khoản admin được tạo tự động lần đầu chạy, dựa trên biến môi trường trong `.env`:

| Biến             | Mặc định                |
|------------------|-------------------------|
| `ADMIN_USERNAME` | `admin`                 |
| `ADMIN_PASSWORD` | `changeme123`           |
| `ADMIN_EMAIL`    | `admin@devnotes.local`  |

> ⚠️ Đổi mật khẩu mặc định trước khi deploy production.

---

## 🗄️ Chọn Database

Cấu hình trong file `.env`:

| Backend                 | Cách bật                                                                 |
|-------------------------|--------------------------------------------------------------------------|
| **SQLite** (mặc định)   | Để trống `DATABASE_URL` và `MONGO_URI` — DB tự tạo tại `data/devnotes.db` |
| **PostgreSQL**          | `DATABASE_URL=postgresql://user:pass@host:5432/devnotes`                 |
| **MySQL**               | `DATABASE_URL=mysql://user:pass@host:3306/devnotes`                      |
| **MongoDB**             | `MONGO_URI=mongodb://user:pass@host:27017` và `MONGO_DB=devnotes`        |

Sau khi đổi backend, chạy `python seed.py` để khởi tạo schema + dữ liệu mẫu cho DB mới.

---

## 📁 Cấu trúc thư mục

```
devnotes/
├── app.py                 # Flask entrypoint, đăng ký blueprint
├── seed.py                # Khởi tạo schema + dữ liệu mẫu cho DB
├── requirements.txt       # Python dependencies
├── Dockerfile             # Image cho service devnotes
├── docker-compose.yml     # Compose stack (app + DB + traefik)
├── .env.example           # Template biến môi trường
├── templates/             # Single-page HTML
├── static/                # JS / CSS / image assets
├── traefik/               # Cấu hình Traefik + cert local
├── data/                  # SQLite DB + dữ liệu runtime (gitignored)
├── config/
│   └── __init__.py        # Load config từ env
├── db/                    # Multi-backend database layer
│   ├── __init__.py        # Factory chọn backend theo env
│   ├── _shared.py         # Helper dùng chung (constants, utils)
│   ├── sqlite.py          # Backend SQLite (mặc định)
│   ├── postgres.py        # Backend PostgreSQL
│   ├── mysql.py           # Backend MySQL
│   └── mongo.py           # Backend MongoDB
├── routes/                # Flask blueprints (REST API)
│   ├── auth.py            # Login / register / OTP
│   ├── notes.py           # CRUD notes
│   ├── topics.py          # CRUD topics (categories)
│   ├── images.py          # Upload / proxy image
│   └── data.py            # Export / import JSON
├── services/
│   ├── telegram.py        # Gửi OTP qua Telegram bot
│   └── image_cache.py     # Cache ảnh external (proxy)
└── utils/
    └── auth_utils.py      # JWT helpers, hash password
```

---

## 🏗️ Architecture

![art](static/image/fe_be_architecture_devnotes.svg)

---

## ⌨️ Phím tắt

| Phím      | Chức năng         |
|-----------|-------------------|
| `Ctrl+K`  | Focus ô tìm kiếm  |
| `Ctrl+N`  | Thêm note mới     |
| `Esc`     | Đóng modal        |

---

## 💾 Backup dữ liệu

- Dùng nút **Export JSON** trong app để tải toàn bộ notes về máy.
- Hoặc backup nguyên thư mục `data/` (chứa `devnotes.db` khi dùng SQLite).
- Với PostgreSQL / MySQL / MongoDB, dùng tool gốc của DB (`pg_dump`, `mysqldump`, `mongodump`).

---

## 🧹 Gỡ cài đặt

```bash
deactivate
rm -rf venv
```
