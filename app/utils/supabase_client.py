"""
app/utils/supabase_client.py

Hai client:
- get_supabase()       → anon key, dùng cho user-facing queries (bị RLS giới hạn)
- get_supabase_admin() → service_role key, bypass RLS hoàn toàn
                         CHỈ dùng ở server-side (fan-out, lazy-sync, admin CRUD)
                         KHÔNG bao giờ expose key này ra client/frontend
"""
import os
from supabase import create_client, Client

_client: Client | None = None
_admin_client: Client | None = None


def get_supabase() -> Client:
    """Anon client – dùng cho các query thông thường."""
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]  # anon / public key
        _client = create_client(url, key)
    return _client


def get_supabase_admin() -> Client:
    """
    Service role client – bypass RLS.
    Biến môi trường: SUPABASE_SERVICE_ROLE_KEY
    Lấy tại: Supabase Dashboard > Settings > API > service_role (secret)
    """
    global _admin_client
    if _admin_client is None:
        url = os.environ["SUPABASE_URL"]
        service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or \
                      os.environ.get("SUPABASE_SERVICE_KEY")
        if not service_key:
            raise RuntimeError(
                "Thiếu biến môi trường SUPABASE_SERVICE_ROLE_KEY. "
                "Vào Supabase Dashboard > Settings > API > service_role để lấy key."
            )
        _admin_client = create_client(url, service_key)
    return _admin_client
