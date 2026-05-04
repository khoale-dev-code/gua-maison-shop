import os
import subprocess
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime
import sys

# 1. CẤU HÌNH KẾT NỐI
DB_USER = "postgres"
DB_PASS = "%2uf%rQSS_S8^T#"
DB_HOST = "db.eshbhcxlwxmlgbkgjlmu.supabase.co"
DB_PORT = "5432"
DB_NAME = "postgres"

# ĐƯỜNG DẪN PG_DUMP (Khoa đã có bản 18, mình trỏ thẳng vào đây)
PG_DUMP_BIN = r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"

DB_URI = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
TABLES = ["users", "products", "orders", "order_items", "shipments"]


def run_ultimate_backup():
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"backups/{now}"
    os.makedirs(backup_dir, exist_ok=True)
    
    print(f"🚀 Bắt đầu tiến hành Backup chiến dịch GUA Maison...")

    # --- PHẦN 1: DÙNG PG_DUMP (Backup cấu trúc SQL) ---
    sql_file = f"{backup_dir}/structure_and_data.sql"
    os.environ['PGPASSWORD'] = DB_PASS
    
    # Kiểm tra xem file pg_dump có tồn tại không trước khi chạy
    if not os.path.exists(PG_DUMP_BIN):
        print(f"⚠️ Cảnh báo: Không tìm thấy pg_dump tại {PG_DUMP_BIN}")
        print("💡 Bạn cần kiểm tra lại đường dẫn cài đặt PostgreSQL.")
    else:
        dump_cmd = [
            PG_DUMP_BIN, "-h", DB_HOST, "-p", DB_PORT, "-U", DB_USER,
            "-d", DB_NAME, "-f", sql_file, "--clean", "--if-exists"
        ]
        try:
            subprocess.run(dump_cmd, check=True)
            print(f"✅ Đã trích xuất xong file SQL: {sql_file}")
        except Exception as e:
            print(f"❌ Lỗi pg_dump: {e}")

    # --- PHẦN 2: DÙNG PANDAS (Xuất Excel báo cáo) ---
    excel_file = f"{backup_dir}/business_report_{now}.xlsx"
    engine = create_engine(DB_URI)
    
    try:
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            for table in TABLES:
                print(f"📊 Đang đọc bảng {table}...")
                df = pd.read_sql_table(table, engine)
                
                # BẢO MẬT: Xóa mật khẩu
                if "password_hash" in df.columns:
                    df = df.drop(columns=["password_hash"])

                # 🔥 FIX LỖI TIMEZONE: Chuyển tất cả cột thời gian về dạng không múi giờ
                for col in df.select_dtypes(include=['datetimetz', 'datetime']).columns:
                    df[col] = df[col].dt.tz_localize(None)
                
                df.to_excel(writer, sheet_name=table, index=False)
        print(f"✅ Đã tạo xong báo cáo Excel: {excel_file}")
    except Exception as e:
        print(f"❌ Lỗi Pandas: {e}")

    print(f"\n✨ TẤT CẢ ĐÃ XONG! Dữ liệu nằm trong: {backup_dir}")


if __name__ == "__main__":
    run_ultimate_backup()
