## Chạy toàn bộ bằng Docker + PowerShell (Windows)

File này giúp bạn dựng ClickHouse bằng Docker và tự động insert dữ liệu CSV từ `data/` theo schema trong `schema/`.

### Yêu cầu
- Docker Desktop đã cài và đang chạy
- Python 3.9+ (để chạy script ingestion)

### 1) Khởi động ClickHouse bằng Docker Compose
```powershell
docker compose up -d
```
- HTTP: `localhost:8123`
- User: `default`
- Password: `admin` (đặt trong `docker-compose.yml`)

Kiểm tra:
```powershell
curl http://localhost:8123/ping
# Kỳ vọng: Ok.
```

### 2) Chạy ingestion tự động (1 lệnh)
```powershell
.\run.ps1
```
Script sẽ:
- Khởi động (hoặc đảm bảo) ClickHouse bằng `docker compose up -d`
- Đợi `/ping` trả `Ok`
- Cài dependencies Python
- Chạy `python ingest.py ingest --cwd . --host localhost --port 8123 --username default --password "admin" --database default`

### 3) Kiểm tra dữ liệu
```powershell
curl "http://localhost:8123/?query=SELECT%20version()"
curl "http://localhost:8123/?query=SHOW%20TABLES"
curl "http://localhost:8123/?query=SELECT%20count()%20FROM%20<ten_bang>"
```

### Ghi chú hiệu năng
- Ingestion stream trực tiếp file → server (không load toàn bộ vào RAM).
- Bật `async_insert` và `input_format_parallel_parsing` để tối ưu tốc độ.
- Có thể điều chỉnh thêm trong `ingest.py` nếu cần.

