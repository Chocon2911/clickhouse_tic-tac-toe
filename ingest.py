import os
import requests
from tqdm import tqdm

# --- Thông tin kết nối ClickHouse ---
CLICKHOUSE_HTTP = "http://localhost:8123"
CLICKHOUSE_USER = "default"
CLICKHOUSE_PASS = "admin"
DATABASE = "tictactoe"
SCHEMA_FOLDER = "schema"

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
        sql_file: Đường dẫn đến file SQL
    
    Returns:
        True nếu thành công, False nếu thất bại
    """
    if not os.path.exists(sql_file):
        print(f"❌ SQL file not found: {sql_file}")
        return False
    
    # Đọc nội dung file SQL
    with open(sql_file, 'r') as f:
        sql_schema = f.read()
    
    # Convert \n literals thành newlines thật
    create_table_query = sql_schema.replace('\\n', '\n')
    
    response = requests.post(
        CLICKHOUSE_HTTP,
        auth=(CLICKHOUSE_USER, CLICKHOUSE_PASS),
        data=create_table_query
    )
    
    if response.status_code == 200:
        return True
    else:
        print(f"❌ Failed to create table from {sql_file}: {response.text}")
        return False


def check_table_exists(table_name: str) -> bool:
    """
    Kiểm tra xem table có tồn tại không
    
    Args:
        table_name: Tên table
    
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


def get_table_count(table_name: str) -> int:
    """
    Lấy số lượng rows trong table
    
    Args:
        table_name: Tên table
    
    Returns:
        Số lượng rows
    """
    count_query = f"SELECT count() FROM {DATABASE}.{table_name}"
    
    response = requests.post(
        CLICKHOUSE_HTTP,
        auth=(CLICKHOUSE_USER, CLICKHOUSE_PASS),
        data=count_query
    )
    
    if response.status_code == 200:
        return int(response.text.strip())
    
    return 0


def drop_table(table_name: str):
    """
    Xóa table
    
    Args:
        table_name: Tên table
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


def create_all_tables(recreate: bool = False):
    """
    Tạo tất cả tables từ schema files
    
    Args:
        recreate: Nếu True, xóa và tạo lại tables đã tồn tại
    
    Returns:
        Tuple (success_count, fail_count)
    """
    print("=" * 70)
    print("🚀 Creating All Tables from Schema Files")
    print("=" * 70)
    
    # Tạo database
    if not create_database():
        return (0, 0)
    
    print()
    
    # Danh sách tất cả các schema files cần tạo
    schema_files = []
    
    # 1. Draw table
    schema_files.append(("ttt_5_draw", os.path.join(SCHEMA_FOLDER, "ttt_5_draw.sql")))
    
    # 2. Win tables (layer 9-25)
    for layer in range(9, 26):
        table_name = f"ttt_5_l{layer}"
        sql_file = os.path.join(SCHEMA_FOLDER, f"{table_name}.sql")
        schema_files.append((table_name, sql_file))
    
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    # Tạo từng table
    for table_name, sql_file in tqdm(schema_files, desc="Creating tables"):
        # Kiểm tra file có tồn tại không
        if not os.path.exists(sql_file):
            print(f"⚠️  Schema file not found: {sql_file}")
            fail_count += 1
            continue
        
        # Kiểm tra table đã tồn tại chưa
        if check_table_exists(table_name):
            if recreate:
                print(f"🔄 Recreating table: {table_name}")
                drop_table(table_name)
            else:
                print(f"⏭️  Table '{table_name}' already exists, skipping...")
                skip_count += 1
                continue
        
        # Tạo table
        if create_table_from_sql_file(sql_file):
            success_count += 1
            print(f"✅ Created: {table_name}")
        else:
            fail_count += 1
    
    print("\n" + "=" * 70)
    print("📊 Summary:")
    print(f"   ✅ Successfully created: {success_count} tables")
    print(f"   ⏭️  Skipped (already exists): {skip_count} tables")
    print(f"   ❌ Failed: {fail_count} tables")
    print("=" * 70)
    
    return (success_count, fail_count)


def verify_all_tables():
    """
    Kiểm tra tất cả tables đã được tạo chưa và hiển thị thông tin
    """
    print("\n" + "=" * 70)
    print("🔍 Verifying All Tables")
    print("=" * 70)
    
    tables_to_check = ["ttt_5_draw"] + [f"ttt_5_l{layer}" for layer in range(9, 26)]
    
    results = []
    
    for table_name in tables_to_check:
        exists = check_table_exists(table_name)
        if exists:
            count = get_table_count(table_name)
            results.append((table_name, True, count))
        else:
            results.append((table_name, False, 0))
    
    # Hiển thị kết quả
    print(f"\n{'Table Name':<20} {'Status':<10} {'Row Count':<15}")
    print("-" * 50)
    
    for table_name, exists, count in results:
        status = "✅ EXISTS" if exists else "❌ MISSING"
        count_str = f"{count:,}" if exists else "N/A"
        print(f"{table_name:<20} {status:<10} {count_str:<15}")
    
    # Tổng kết
    total_tables = len(results)
    existing_tables = sum(1 for _, exists, _ in results if exists)
    total_rows = sum(count for _, exists, count in results if exists)
    
    print("-" * 50)
    print(f"{'Total':<20} {existing_tables}/{total_tables:<10} {total_rows:,}")
    print("=" * 70)


def show_all_tables():
    """
    Hiển thị tất cả tables trong database
    """
    query = f"SHOW TABLES FROM {DATABASE}"
    
    response = requests.post(
        CLICKHOUSE_HTTP,
        auth=(CLICKHOUSE_USER, CLICKHOUSE_PASS),
        data=query
    )
    
    if response.status_code == 200:
        tables = response.text.strip().split('\n')
        print(f"\n📋 All tables in database '{DATABASE}':")
        for table in tables:
            print(f"   - {table}")
    else:
        print(f"❌ Failed to show tables: {response.text}")


#============================================Main============================================
if __name__ == "__main__":
    import sys
    
    # Parse command line arguments
    recreate = "--recreate" in sys.argv
    verify_only = "--verify" in sys.argv
    
    if verify_only:
        # Chỉ verify, không tạo table mới
        verify_all_tables()
    else:
        # Tạo tất cả tables
        success, fail = create_all_tables(recreate=recreate)
        
        # Verify sau khi tạo
        if success > 0 or fail > 0:
            verify_all_tables()
        
        # Hiển thị danh sách tables
        show_all_tables()
    
    print("\n💡 Usage:")
    print("   python create_all_tables.py              # Tạo tables mới (skip nếu đã tồn tại)")
    print("   python create_all_tables.py --recreate   # Xóa và tạo lại tất cả tables")
    print("   python create_all_tables.py --verify     # Chỉ kiểm tra tables đã tồn tại")