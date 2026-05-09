import os
import subprocess
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime, timedelta
import logging
import shutil

# 1. CẤU HÌNH KẾT NỐI DATABASE
DB_USER = "postgres"
DB_PASS = "%2uf%rQSS_S8^T#"
DB_HOST = "db.eshbhcxlwxmlgbkgjlmu.supabase.co"
DB_PORT = "5432"
DB_NAME = "postgres"

# ĐƯỜNG DẪN PG_DUMP
PG_DUMP_BIN = r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
DB_URI = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# 2. PHÂN NHÓM BẢNG DỮ LIỆU ĐỂ XUẤT EXCEL (Dựa trên Schema thực tế)
# Lưu ý: Bỏ qua các bảng log quá nặng (audit_logs, webhook_logs) để tránh tràn RAM khi xuất Excel
DATA_GROUPS = {
    "1. DOANH THU & ĐƠN HÀNG": [
        "orders", "order_items", "payments", "return_requests", "cart_items"
    ],
    "2. SẢN PHẨM & KHO": [
        "products", "product_variants", "categories", "brands", "product_images",
        "inventory_logs", "product_reviews", "product_analytics"
    ],
    "3. KHUYẾN MÃI": [
        "coupons", "coupon_usages", "flash_sales", "flash_sale_items"
    ],
    "4. KHÁCH HÀNG (CRM)": [
        "users", "user_addresses", "favorites"
    ],
    "5. VẬN HÀNH (LOGISTICS)": [
        "shipments", "shipment_events", "shipping_providers", "shipping_configs"
    ]
}


def setup_logger(backup_dir):
    logger = logging.getLogger("GUABackup")
    logger.setLevel(logging.INFO)
    # Xóa handlers cũ nếu chạy nhiều lần trong 1 session
    if logger.hasHandlers():
        logger.handlers.clear()
        
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Ghi log ra màn hình
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger.addHandler(sh)
    
    # Ghi log ra file
    fh = logging.FileHandler(f"{backup_dir}/backup_process.log", encoding='utf-8')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    return logger


def run_ultimate_backup():
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = "backups"
    current_dir = f"{backup_root}/{now_str}"
    os.makedirs(current_dir, exist_ok=True)
    
    logger = setup_logger(current_dir)
    logger.info("🚀 KHỞI ĐỘNG HỆ THỐNG BACKUP GUA MAISON ARCHIVE...")

    # =========================================================================
    # PHẦN 1: PG_DUMP (BACKUP CẤU TRÚC & DỮ LIỆU SQL NGUYÊN BẢN)
    # =========================================================================
    sql_file = f"{current_dir}/database_full_dump.sql"
    os.environ['PGPASSWORD'] = DB_PASS
    
    if os.path.exists(PG_DUMP_BIN):
        logger.info("⏳ Đang tiến hành trích xuất cơ sở dữ liệu (SQL Dump)...")
        dump_cmd = [
            PG_DUMP_BIN, "-h", DB_HOST, "-p", DB_PORT, "-U", DB_USER,
            "-d", DB_NAME, "-f", sql_file, "--clean", "--if-exists", "--no-owner"
        ]
        try:
            subprocess.run(dump_cmd, check=True)
            logger.info(f"✅ Backup SQL thành công: {sql_file}")
        except Exception as e:
            logger.error(f"❌ Lỗi khi chạy PG_DUMP: {e}")
    else:
        logger.warning(f"⚠️ Không tìm thấy pg_dump tại {PG_DUMP_BIN}. Bỏ qua backup SQL.")

    # =========================================================================
    # PHẦN 2: PANDAS EXCEL (TRÍCH XUẤT BÁO CÁO KINH DOANH)
    # =========================================================================
    excel_file = f"{current_dir}/GUA_Business_Report_{now_str}.xlsx"
    engine = create_engine(DB_URI)
    
    logger.info("⏳ Đang biên dịch dữ liệu ra báo cáo Excel...")
    try:
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            for group_name, tables in DATA_GROUPS.items():
                for table in tables:
                    try:
                        # Đọc dữ liệu từ Database
                        df = pd.read_sql_query(f'SELECT * FROM public."{table}"', engine)
                        
                        if df.empty:
                            logger.info(f"  - Bảng {table}: Trống (Bỏ qua)")
                            continue

                        # 1. BẢO MẬT & TỐI ƯU DUNG LƯỢNG (Xóa cột nhạy cảm/cột JSON quá dài)
                        sensitive_cols = ["password_hash", "raw_response", "payload", "old_values", "new_values"]
                        cols_to_drop = [c for c in sensitive_cols if c in df.columns]
                        if cols_to_drop:
                            df = df.drop(columns=cols_to_drop)

                        # 2. XỬ LÝ TIMEZONE (Để Excel không bị lỗi)
                        for col in df.select_dtypes(include=['datetimetz', 'datetime']).columns:
                            df[col] = df[col].dt.tz_localize(None)

                        # 3. GHI VÀO SHEET (Cắt tên sheet <= 31 ký tự theo chuẩn Excel)
                        sheet_name = table[:31]
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        logger.info(f"  - Đã xuất bảng [{table}] ({len(df)} dòng)")

                    except Exception as tbl_err:
                        logger.warning(f"  - Lỗi khi đọc bảng {table}: {tbl_err}")
                        
        logger.info(f"✅ Hoàn tất xuất báo cáo Excel: {excel_file}")
    except Exception as e:
        logger.error(f"❌ Lỗi hệ thống Pandas/Excel: {e}")

    # =========================================================================
    # PHẦN 3: TỰ ĐỘNG DỌN DẸP (XÓA BACKUP CŨ > 15 NGÀY ĐỂ TRÁNH ĐẦY Ổ CỨNG)
    # =========================================================================
    logger.info("🧹 Đang kiểm tra và dọn dẹp các bản backup cũ...")
    retention_days = 15
    try:
        for folder in os.listdir(backup_root):
            folder_path = os.path.join(backup_root, folder)
            if os.path.isdir(folder_path):
                try:
                    folder_date = datetime.strptime(folder, "%Y%m%d_%H%M%S")
                    if datetime.now() - folder_date > timedelta(days=retention_days):
                        shutil.rmtree(folder_path)
                        logger.info(f"  - Đã xóa bản backup cũ: {folder}")
                except ValueError:
                    # Bỏ qua các thư mục không đúng định dạng ngày tháng
                    pass
    except Exception as e:
        logger.warning(f"⚠️ Có lỗi khi dọn dẹp thư mục: {e}")

    logger.info(f"✨ TẤT CẢ CHIẾN DỊCH ĐÃ XONG! Dữ liệu được bảo vệ tại: {current_dir}")


if __name__ == "__main__":
    run_ultimate_backup()
