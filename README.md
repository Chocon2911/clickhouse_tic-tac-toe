## ClickHouse CSV Ingestion (Streaming, Low Memory)

This tool streams large CSV files from `data/` into ClickHouse using matching table schemas from `schema/`. It is optimized for speed and low memory usage on Windows.

### Prerequisites
- Python 3.9+
- A running ClickHouse server with HTTP interface enabled (default port 8123)

### Install
```bash
pip install -r requirements.txt
```

### Directory Layout
- `data/ttt_5_l9.csv` — data files
- `schema/ttt_5_l9.sql` — matching schema files (table creation)

Files are paired by filename stem (e.g., `ttt_5_l9`).

### Configure
Create a `.env` file (optional) at project root:
```
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DATABASE=default
```

### Usage
Run with environment and auto-discovery:
```bash
python ingest.py run --cwd .
```

Or pass parameters explicitly:
```bash
python ingest.py ingest --host localhost --port 8123 --username default --password "" --database default --cwd .
```

Dry run (show plan only):
```bash
python ingest.py ingest --host localhost --port 8123 --username default --database default --cwd . --dry-run
```

### Performance Notes
- Uses HTTP compression and ClickHouse parallel CSV parsing.
- Inserts stream directly from file to server (no full-file memory load).
- `async_insert=1` enabled; server ingests in background for throughput.
- Adjust server settings if needed (e.g., `max_insert_block_size`).

### Troubleshooting
- Verify ClickHouse is reachable at `host:port`.
- Ensure each CSV has a corresponding SQL schema in `schema/`.
- If table names differ inside `.sql`, the tool auto-detects table name from `CREATE TABLE`.


