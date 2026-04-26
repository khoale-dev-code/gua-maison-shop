"""
app/utils/supabase_client.py
============================
Singleton Supabase client – import ở bất kỳ đâu cũng dùng chung 1 instance.
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_client: Client | None = None


def get_supabase() -> Client:
    """Trả về Supabase client (khởi tạo 1 lần duy nhất)."""
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            raise EnvironmentError("❌ Thiếu SUPABASE_URL hoặc SUPABASE_KEY trong .env")
        _client = create_client(url, key)
    return _client
