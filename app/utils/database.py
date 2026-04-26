# ===================================
# app/utils/database.py
# Kết nối Supabase - Singleton Pattern
# ===================================

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_supabase_client: Client = None


def get_db() -> Client:
    """
    Trả về Supabase client dùng Singleton pattern.
    Chỉ tạo kết nối 1 lần, tái sử dụng cho mọi request.
    """
    global _supabase_client

    if _supabase_client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")

        if not url or not key:
            raise ValueError(
                "❌ SUPABASE_URL và SUPABASE_KEY chưa được cấu hình trong .env"
            )

        _supabase_client = create_client(url, key)
        print("✅ Supabase connected!")

    return _supabase_client
