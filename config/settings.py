"""
config/settings.py
==================
Cấu hình toàn bộ ứng dụng GUA Maison (2026 Industrial Edition).
Quản lý biến môi trường, kết nối Supabase và AI Microservices.
"""

import os
import logging
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logger = logging.getLogger(__name__)

# ── Singleton Supabase Client ────────────────────────────────────────────────
# FIX: Tạo 1 lần duy nhất, tái sử dụng — tránh tạo connection mới mỗi request
_supabase_client: Client | None = None


def get_supabase_client() -> Client:
    """
    Trả về Supabase client dùng chung (Singleton pattern).
    Thread-safe với Flask vì mỗi worker process có 1 instance riêng.
    """
    global _supabase_client
    if _supabase_client is None:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            raise ValueError(
                "❌ Không tìm thấy SUPABASE_URL hoặc SUPABASE_KEY trong file .env"
            )
        _supabase_client = create_client(url, key)
    return _supabase_client

# ── Base Config ──────────────────────────────────────────────────────────────


class BaseConfig:
    """Cấu hình chung cho mọi môi trường."""

    # ── Flask Core ───────────────────────────────────────────────
    # FIX: Không có fallback mặc định — buộc dev phải set SECRET_KEY trong .env
    # Nếu thiếu, validate_config() sẽ báo lỗi rõ ràng khi khởi động
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")

    # ── Supabase ─────────────────────────────────────────────────
    SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY", "")

    # ── AI Engine (Hugging Face) ─────────────────────────────────
    AI_ENGINE_URL: str = os.environ.get("AI_ENGINE_URL", "")
    HF_TOKEN: str = os.environ.get("HF_TOKEN", "")

    # ── Session ──────────────────────────────────────────────────
    SESSION_PERMANENT: bool = False
    SESSION_USE_SIGNER: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"

    # ── Upload ───────────────────────────────────────────────────
    MAX_CONTENT_LENGTH: int = 10 * 1024 * 1024  # 10 MB

    # ── Pagination ───────────────────────────────────────────────
    PRODUCTS_PER_PAGE: int = 12
    ADMIN_PRODUCTS_PER_PAGE: int = 15
    FEATURED_PRODUCTS_LIMIT: int = 8

# ── Environment Configs ──────────────────────────────────────────────────────


class DevelopmentConfig(BaseConfig):
    """Môi trường Local — HTTP, filesystem session, debug on."""
    DEBUG: bool = True
    SESSION_COOKIE_SECURE: bool = False
    SESSION_TYPE: str = "filesystem"


class ProductionConfig(BaseConfig):
    """Môi trường Vercel — HTTPS only, signed cookie session."""
    DEBUG: bool = False
    SESSION_COOKIE_SECURE: bool = True
    # FIX: Không set SESSION_TYPE=None (gây lỗi nếu flask-session đã import)
    # Bỏ hẳn key này → Flask dùng built-in signed cookie mặc định

# ── Config Map ───────────────────────────────────────────────────────────────


config_map: dict[str, type[BaseConfig]] = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}


def get_config() -> type[BaseConfig]:
    """Factory: trả về config class dựa trên FLASK_ENV."""
    env = os.environ.get("FLASK_ENV", "development").lower()
    cfg = config_map.get(env, DevelopmentConfig)
    if env not in config_map:
        logger.warning("⚠️  FLASK_ENV='%s' không hợp lệ, fallback về DevelopmentConfig.", env)
    return cfg

# ── Startup Validator ────────────────────────────────────────────────────────


# Các biến BẮT BUỘC phải có — app không thể chạy nếu thiếu
_REQUIRED_VARS = ["SECRET_KEY", "SUPABASE_URL", "SUPABASE_KEY"]

# Các biến tùy chọn — chỉ warn, không crash
_OPTIONAL_VARS = ["AI_ENGINE_URL", "HF_TOKEN"]


def validate_config() -> None:
    """
    Kiểm tra biến môi trường khi khởi động app.
    Gọi hàm này trong create_app() để lỗi config xuất hiện sớm,
    thay vì âm thầm crash lúc runtime.

    Raises:
        EnvironmentError: Nếu thiếu bất kỳ biến bắt buộc nào.
    """
    missing = [var for var in _REQUIRED_VARS if not os.environ.get(var)]
    if missing:
        raise EnvironmentError(
            f"❌ Thiếu biến môi trường bắt buộc: {', '.join(missing)}\n"
            f"   Kiểm tra lại file .env hoặc Vercel Environment Variables."
        )

    for var in _OPTIONAL_VARS:
        if not os.environ.get(var):
            logger.warning("⚠️  Biến tuỳ chọn '%s' chưa được cấu hình — một số tính năng AI sẽ bị tắt.", var)
