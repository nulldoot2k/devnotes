# 📝 DevNotes — Interview Knowledge Base

Ứng dụng quản lý notes phỏng vấn, chạy local bằng Python + Flask.
Dữ liệu lưu vào file `data/notes.json`.

---

## 🚀 Cài đặt & Chạy

```bash
# 1. Cài dependencies
pip install -r requirements.txt

# 2. Chạy server
python app.py

# 3. Mở browser
http://localhost:5000
```

Lần đầu chạy sẽ tự seed dữ liệu mẫu K8s vào `data/notes.json`.

---

## 📁 Cấu trúc thư mục

```
devnotes/
├── app.py               # Flask server + REST API
├── seed.py              # Script tạo dữ liệu mẫu
├── requirements.txt
├── data/
│   └── notes.json       # Toàn bộ dữ liệu (tự tạo)
├── templates/
│   └── index.html       # HTML layout
└── static/
    ├── css/
    │   └── style.css    # Giao diện
    └── js/
        ├── api.js       # Gọi Flask API
        ├── ui.js        # Render helpers
        └── app.js       # Logic chính
```

---

## 🔌 REST API

| Method | Endpoint             | Mô tả                   |
|--------|----------------------|-------------------------|
| GET    | `/api/notes`         | Lấy notes (hỗ trợ `?q=` và `?topic=`) |
| POST   | `/api/notes`         | Tạo note mới            |
| PUT    | `/api/notes/<id>`    | Cập nhật note           |
| DELETE | `/api/notes/<id>`    | Xóa note                |
| GET    | `/api/topics`        | Lấy danh sách chủ đề   |
| POST   | `/api/topics`        | Tạo chủ đề mới          |
| DELETE | `/api/topics/<id>`   | Xóa chủ đề              |
| GET    | `/api/export`        | Export toàn bộ JSON     |
| POST   | `/api/import`        | Import JSON             |

---

## 📥 Format Import JSON

```json
[
  {
    "question": "VM và k8s khác nhau như nào?",
    "topic": "Kubernetes & DevOps",
    "tags": ["k8s", "vm", "devops"],
    "content": "Nội dung trả lời..."
  }
]
```

---

## ⌨️ Phím tắt

| Phím | Chức năng |
|------|-----------|
| `Ctrl+K` | Focus ô tìm kiếm |
| `Ctrl+N` | Thêm note mới |
| `Esc`    | Đóng modal |

---

## 💾 Backup dữ liệu

Chỉ cần copy file `data/notes.json` là xong.
Hoặc dùng nút **Export JSON** trong app để tải về.
