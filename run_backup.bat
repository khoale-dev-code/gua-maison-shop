@echo off
:: Di chuyển vào thư mục dự án của bạn
cd /d "D:\freetime\fashion_store_2026\fashion_store"

:: Kích hoạt môi trường ảo (nếu bạn có dùng venv)
:: call venv\Scripts\activate

:: Chạy script backup
python automated_backup.py

pause