FROM python:3.11-slim

WORKDIR /app

# Cài dependencies trước (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ source
COPY . .

# Tạo thư mục data (SQLite + static files)
RUN mkdir -p data static/css static/js templates

EXPOSE 5000

CMD ["python", "app.py"]
