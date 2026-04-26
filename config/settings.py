"""
config/settings.py
==================
Cấu hình toàn bộ ứng dụng GUA Maison (2026 Industrial Edition).
Quản lý biến môi trường, kết nối Supabase và AI Microservices.
"""

import os
from dotenv import load_dotenv

# Tự động tải file .env nếu đang chạy ở môi trường Local
load_dotenv()


class BaseConfig:
    """Cấu hình chung cho mọi môi trường (Standard Node)"""

    # ── Flask Core ──────────────────────────────────────────────
    # Chìa khóa bảo mật cho Session và CSRF
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "gua-matrix-default-key-2026")

    # ── Supabase Infrastructure ──────────────────────────────────
    SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY", "")

    # ── AI Engine (Hugging Face Microservice) ────────────────────
    # URL dẫn đến bộ não AI (Matrix Vision & Analytics)
    AI_ENGINE_URL: str = os.environ.get("AI_ENGINE_URL", "")
    # Token xác thực nếu Space để chế độ Private
    HF_TOKEN: str = os.environ.get("HF_TOKEN", "")

    # ── Session Management (Chung) ───────────────────────────────
    SESSION_PERMANENT: bool = False
    SESSION_USE_SIGNER: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"

    # ── File & Upload Limits ─────────────────────────────────────
    MAX_CONTENT_LENGTH: int = 10 * 1024 * 1024  # Tối đa 10 MB cho ảnh Visual Search

    # ── UI & Pagination Constants ────────────────────────────────
    PRODUCTS_PER_PAGE: int = 12
    ADMIN_PRODUCTS_PER_PAGE: int = 15
    FEATURED_PRODUCTS_LIMIT: int = 8


class DevelopmentConfig(BaseConfig):
    """Cấu hình cho môi trường Lập trình (Localhost)"""
    DEBUG: bool = True
    SESSION_COOKIE_SECURE: bool = False  # Chạy được trên HTTP thường
    
    # Ở Local: Ổ cứng thoải mái, dùng filesystem để lưu session cho khỏe
    SESSION_TYPE: str = "filesystem"


class ProductionConfig(BaseConfig):
    """Cấu hình cho môi trường Vận hành (Vercel)"""
    DEBUG: bool = False
    # CỰC KỲ QUAN TRỌNG: Vercel chạy HTTPS nên phải để True để bảo mật Cookie
    SESSION_COOKIE_SECURE: bool = True 
    
    # CỰC KỲ QUAN TRỌNG 2: Vercel cấm ghi file ổ cứng (Read-only OS).
    # Đặt None để Flask tự động dùng cơ chế Signed Cookie mặc định, tránh lỗi 500
    SESSION_TYPE = None


# Map tên môi trường (FLASK_ENV) → class config tương ứng
config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}


def get_config():
    """Hàm Factory lấy cấu hình dựa trên biến môi trường FLASK_ENV"""
    env = os.environ.get("FLASK_ENV", "development").lower()
    return config_map.get(env, DevelopmentConfig)
