import os
import requests
from tqdm import tqdm

# --- Thông tin kết nối ClickHouse ---
CLICKHOUSE_HTTP = "http://localhost:8123"
CLICKHOUSE_USER = "default"
CLICKHOUSE_PASS = "admin"
DATABASE = "tictactoe"

# --- Import dữ liệu ---
for i in range(9, 26):
    table = f"ttt_5_l{i}"
    csv_file = f"data/{table}.csv"
    if not os.path.exists(csv_file):
        print(f"⚠️  Bỏ qua {table}: không có file {csv_file}")
        continue

    print(f"\n📂 Bắt đầu import {csv_file} → {table}")

    # Dùng streaming upload + progress bar
    file_size = os.path.getsize(csv_file)
    with open(csv_file, "rb") as f, tqdm(
        total=file_size, unit="B", unit_scale=True, desc=table
    ) as pbar:
        def read_in_chunks(file_object, chunk_size=1024 * 1024):
            while chunk := file_object.read(chunk_size):
                pbar.update(len(chunk))
                yield chunk

        r = requests.post(
            CLICKHOUSE_HTTP,
            params={
                "user": CLICKHOUSE_USER,
                "password": CLICKHOUSE_PASS,
                "database": DATABASE,
                "query": f"INSERT INTO {table} FORMAT CSV",
            },
            data=read_in_chunks(f),
        )

    if r.status_code == 200:
        print(f"✅ Import thành công: {table}")
    else:
        print(f"❌ Lỗi import {table}: {r.text}")

