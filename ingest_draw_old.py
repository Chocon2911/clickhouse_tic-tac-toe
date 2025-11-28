import os
import requests

# --- Thông tin kết nối ClickHouse ---
CLICKHOUSE_HTTP = "http://localhost:8123"
CLICKHOUSE_USER = "default"
CLICKHOUSE_PASS = "admin"
DATABASE = "tictactoe"

def create_database():
    """
    Tạo database nếu chưa tồn tại
    """
    create_db_query = f"CREATE DATABASE IF NOT EXISTS {DATABASE}"
    
    response = requests.post(
        CLICKHOUSE_HTTP,
        auth=(CLICKHOUSE_USER, CLICKHOUSE_PASS),
        data=create_db_query
    )
    
    if response.status_code == 200:
        print(f"✅ Database '{DATABASE}' created or already exists")
    else:
        print(f"❌ Failed to create database: {response.text}")
        return False
    
    return True


def create_table_from_sql_file(sql_file: str):
    """
    Tạo table từ file SQL
    
    Args:
        sql_file: Đường dẫn đến file SQL (ví dụ: "ttt_5_draw.sql")
    """
    if not os.path.exists(sql_file):
        print(f"❌ SQL file not found: {sql_file}")
        return False
    
    # Đọc nội dung file SQL
    with open(sql_file, 'r') as f:
        sql_schema = f.read()
    
    # Convert \n literals thành newlines thật
    create_table_query = sql_schema.replace('\\n', '\n')
    
    print(f"🔹 Creating table from: {sql_file}")
    
    response = requests.post(
        CLICKHOUSE_HTTP,
        auth=(CLICKHOUSE_USER, CLICKHOUSE_PASS),
        data=create_table_query
    )
    
    if response.status_code == 200:
        print(f"✅ Table created successfully from {sql_file}")
    else:
        print(f"❌ Failed to create table: {response.text}")
        return False
    
    return True


def check_table_exists(table_name: str) -> bool:
    """
    Kiểm tra xem table có tồn tại không
    
    Args:
        table_name: Tên table (ví dụ: "ttt_5_draw")
    
    Returns:
        True nếu table tồn tại, False nếu không
    """
    query = f"EXISTS TABLE {DATABASE}.{table_name}"
    
    response = requests.post(
        CLICKHOUSE_HTTP,
        auth=(CLICKHOUSE_USER, CLICKHOUSE_PASS),
        data=query
    )
    
    if response.status_code == 200:
        return response.text.strip() == "1"
    
    return False


def get_table_info(table_name: str):
    """
    Lấy thông tin về table (schema, số dòng)
    
    Args:
        table_name: Tên table (ví dụ: "ttt_5_draw")
    """
    # Get schema
    schema_query = f"DESCRIBE TABLE {DATABASE}.{table_name}"
    response = requests.post(
        CLICKHOUSE_HTTP,
        auth=(CLICKHOUSE_USER, CLICKHOUSE_PASS),
        data=schema_query
    )
    
    print(f"\n📊 Table: {DATABASE}.{table_name}")
    print("=" * 60)
    
    if response.status_code == 200:
        print("Schema:")
        print(response.text)
    
    # Get row count
    count_query = f"SELECT count() FROM {DATABASE}.{table_name}"
    response = requests.post(
        CLICKHOUSE_HTTP,
        auth=(CLICKHOUSE_USER, CLICKHOUSE_PASS),
        data=count_query
    )
    
    if response.status_code == 200:
        print(f"\nRow count: {response.text.strip()}")


def drop_table(table_name: str):
    """
    Xóa table (nếu cần)
    
    Args:
        table_name: Tên table (ví dụ: "ttt_5_draw")
    """
    drop_query = f"DROP TABLE IF EXISTS {DATABASE}.{table_name}"
    
    response = requests.post(
        CLICKHOUSE_HTTP,
        auth=(CLICKHOUSE_USER, CLICKHOUSE_PASS),
        data=drop_query
    )
    
    if response.status_code == 200:
        print(f"✅ Table '{DATABASE}.{table_name}' dropped successfully")
    else:
        print(f"❌ Failed to drop table: {response.text}")


#============================================Main============================================
if __name__ == "__main__":
    print("=" * 60)
    print("Creating ttt_5_draw table from SQL file")
    print("=" * 60)
    
    # Tạo database
    if not create_database():
        exit(1)
    
    # Tạo table từ file SQL
    sql_file = "schema/ttt_5_draw.sql"
    if create_table_from_sql_file(sql_file):
        # Kiểm tra table đã tạo thành công
        if check_table_exists("ttt_5_draw"):
            print("\n✅ Table 'ttt_5_draw' exists in database")
            get_table_info("ttt_5_draw")
        else:
            print("\n⚠️  Table 'ttt_5_draw' not found")
    
    print("\n" + "=" * 60)