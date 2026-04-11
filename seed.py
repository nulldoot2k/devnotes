"""
seed.py - Tạo dữ liệu mẫu cho DevNotes
Chạy thủ công: python seed.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from db import get_db


def seed_data():
    db = get_db()

    # Create topics
    topics_def = [
        ("Kubernetes & DevOps", "#4fffb0"),
        ("System Design",       "#00c8ff"),
        ("Networking",          "#ffd166"),
        ("Database",            "#f472b6"),
    ]

    topic_map = {}
    for name, color in topics_def:
        existing = db.get_topic_by_name(name)
        if existing:
            topic_map[name] = existing["id"]
        else:
            t = db.create_topic(name, color)
            topic_map[name] = t["id"]

    k8s = topic_map["Kubernetes & DevOps"]
    sd  = topic_map["System Design"]
    net = topic_map["Networking"]
    dbt = topic_map["Database"]

    notes = [
        {
            "question": "VM và k8s khác nhau như nào? Triển khai ứng dụng với k8s hay VM?",
            "topic_id": k8s,
            "tags": ["k8s", "vm", "devops"],
            "content": (
                "## Khác nhau\n"
                "- **VM** ảo hóa phần cứng, mỗi VM có OS riêng, nặng và chậm.\n"
                "- **Container** dùng chung kernel, nhẹ hơn, boot vài giây.\n"
                "- **K8s** là lớp orchestrate container: tự restart, scale, deploy.\n\n"
                "## Tại sao K8s hơn VM — Ví dụ App e-commerce\n"
                "- Black Friday traffic tăng 10x → VM tạo thêm thủ công mất vài phút, K8s tự scale vài giây.\n"
                "- App crash 3AM → VM phải SSH restart tay, K8s tự heal.\n"
                "- Deploy version mới → VM có downtime, K8s rolling update không downtime.\n\n"
                "## Khi nào vẫn dùng VM\n"
                "Cần isolation cao như banking, hoặc legacy app không containerize được."
            ),
        },
        {
            "question": "Kernel là gì?",
            "topic_id": k8s,
            "tags": ["os", "kernel"],
            "content": (
                "Kernel là **lõi của OS** — quản lý CPU, RAM, disk, network.\n\n"
                "- **VM**: mỗi cái có kernel riêng.\n"
                "- **Container**: dùng chung kernel của host, chỉ đóng gói app + thư viện cần thiết.\n\n"
                "> Nhẹ hơn vì không mang theo cả OS."
            ),
        },
        {
            "question": "Orchestrate trong K8s có mấy lớp?",
            "topic_id": k8s,
            "tags": ["k8s", "architecture"],
            "content": (
                "## Có 2 lớp chính\n\n"
                "### 1. Control Plane (não — đưa ra quyết định)\n"
                "- **API Server**: nhận lệnh từ người dùng (kubectl)\n"
                "- **Scheduler**: quyết định Pod chạy ở node nào\n"
                "- **etcd**: lưu toàn bộ trạng thái cluster\n"
                "- **Controller Manager**: đảm bảo trạng thái thực = khai báo\n\n"
                "### 2. Worker Node (tay — chạy thực tế)\n"
                "- **kubelet**: nhận lệnh từ Control Plane, quản lý Pod\n"
                "- **kube-proxy**: quản lý network rules\n"
                "- **Container Runtime**: chạy container (containerd, docker)"
            ),
        },
        {
            "question": "K8s tự restart, scale, deploy như nào?",
            "topic_id": k8s,
            "tags": ["k8s", "restart", "scale", "deploy"],
            "content": (
                "## Restart\n"
                "K8s dựa vào `restartPolicy` trong Pod spec: `Always`, `OnFailure`, `Never`.\n\n"
                "## Scale\n"
                "**HPA** (Horizontal Pod Autoscaler) — thu thập metrics (mặc định 15s/lần).\n"
                "Khi vượt ngưỡng CPU/MEM đã khai báo → tăng replicas, xuống dưới → giảm.\n\n"
                "## Deploy\n"
                "**Rolling Update** là strategy mặc định: tạo Pod mới healthy rồi mới xóa Pod cũ.\n"
                "> Không bị downtime, có thể rollback bất cứ lúc nào."
            ),
        },
        {
            "question": "Blue-Green deployment là gì? Khác gì Rolling Update?",
            "topic_id": k8s,
            "tags": ["k8s", "deployment", "blue-green"],
            "content": (
                "## Blue-Green\n"
                "Chạy 2 môi trường song song — **Blue** (version cũ), **Green** (version mới).\n"
                "Deploy xong → chuyển toàn bộ traffic từ Blue sang Green ngay lập tức.\n"
                "Lỗi → rollback về Blue tức thì.\n\n"
                "## Rolling Update\n"
                "Thay thế Pod cũ dần dần từng cái, có cả Pod version cũ và mới cùng nhận traffic.\n\n"
                "> **Lưu ý:** K8s không hỗ trợ Blue-Green sẵn. Phải tự quản lý bằng 2 Deployment + đổi Service, hoặc dùng Argo Rollouts / Istio."
            ),
        },
        {
            "question": "HPA là gì? Khác gì VPA?",
            "topic_id": k8s,
            "tags": ["k8s", "hpa", "vpa", "autoscaling"],
            "content": (
                "## HPA (Horizontal Pod Autoscaler)\n"
                "- Tăng/giảm **số lượng Pod** (scale ngang).\n"
                "- Dựa vào Metrics Server thu thập CPU/MEM, mặc định 15s/lần.\n"
                "- Khai báo ngưỡng → vượt → tăng replicas, xuống → giảm.\n"
                "- Không cần restart Pod.\n\n"
                "## VPA (Vertical Pod Autoscaler)\n"
                "- Tăng **CPU/Memory** của Pod hiện tại (scale dọc).\n"
                "- Khi điều chỉnh thường phải restart Pod để apply resource mới.\n\n"
                "> **Tóm lại:** HPA = thêm Pod, VPA = Pod to hơn."
            ),
        },
        {
            "question": "CAP Theorem là gì?",
            "topic_id": sd,
            "tags": ["system-design", "distributed", "cap"],
            "content": (
                "## CAP Theorem\n"
                "Hệ thống phân tán chỉ đảm bảo tối đa **2/3**:\n\n"
                "| Chữ | Tên | Ý nghĩa |\n"
                "|-----|-----|---------|\n"
                "| **C** | Consistency | Mọi node thấy cùng data tại cùng thời điểm |\n"
                "| **A** | Availability | Mọi request đều nhận được response |\n"
                "| **P** | Partition Tolerance | Hệ thống vẫn hoạt động khi network bị split |\n\n"
                "Trong thực tế **P gần như bắt buộc** → chọn giữa CP hoặc AP:\n"
                "- **CP**: Zookeeper, HBase, MongoDB (strong consistency)\n"
                "- **AP**: Cassandra, DynamoDB, CouchDB (eventual consistency)"
            ),
        },
        {
            "question": "TCP vs UDP khác nhau như nào? Khi nào dùng cái nào?",
            "topic_id": net,
            "tags": ["networking", "tcp", "udp"],
            "content": (
                "## TCP (Transmission Control Protocol)\n"
                "- **Connection-oriented**: bắt tay 3 bước trước khi truyền.\n"
                "- Đảm bảo delivery, ordering, error checking.\n"
                "- Chậm hơn vì có overhead.\n"
                "- Dùng: HTTP/HTTPS, SSH, email, file transfer.\n\n"
                "## UDP (User Datagram Protocol)\n"
                "- **Connectionless**: bắn packet đi không cần xác nhận.\n"
                "- Không đảm bảo delivery hay ordering.\n"
                "- Nhanh, ít overhead.\n"
                "- Dùng: video streaming, gaming, DNS, VoIP.\n\n"
                "> **Rule of thumb:** cần chính xác → TCP, cần tốc độ → UDP."
            ),
        },
        {
            "question": "Index trong database là gì? Khi nào nên dùng?",
            "topic_id": dbt,
            "tags": ["database", "index", "performance"],
            "content": (
                "Index là cấu trúc dữ liệu phụ giúp tìm kiếm nhanh hơn.\n"
                "Thay vì scan toàn bộ table `O(n)` → dùng index `O(log n)`.\n\n"
                "## Các loại index\n"
                "- **B-Tree**: phổ biến nhất, tốt cho range query (`>`, `<`, `BETWEEN`).\n"
                "- **Hash**: chỉ tốt cho equality (`=`), không hỗ trợ range.\n"
                "- **Full-text**: tìm kiếm text.\n"
                "- **Composite**: nhiều cột, thứ tự cột quan trọng.\n\n"
                "## Khi nào dùng ✓\n"
                "- Cột thường xuất hiện trong `WHERE`, `JOIN`, `ORDER BY`.\n"
                "- Cột có cardinality cao (nhiều giá trị distinct).\n\n"
                "## Khi nào không dùng ✗\n"
                "- Table nhỏ — full scan còn nhanh hơn.\n"
                "- Cột hay bị `UPDATE` — index phải rebuild liên tục.\n"
                "- Quá nhiều index — làm chậm `INSERT`/`UPDATE`/`DELETE`."
            ),
        },
    ]

    count = 0
    for n in notes:
        db.create_note(
            question=n["question"],
            content=n["content"],
            topic_id=n["topic_id"],
            tags=n["tags"],
        )
        count += 1

    print(f"✅ Seeded {count} notes, {len(topics_def)} topics")


if __name__ == "__main__":
    seed_data()
