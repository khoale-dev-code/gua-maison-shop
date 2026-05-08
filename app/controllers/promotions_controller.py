"""
app/controllers/promotions_controller.py
Quản lý trang Khuyến mãi / Mã giảm giá dành cho Khách hàng (Storefront)
"""

import logging
from flask import Blueprint, render_template
from datetime import datetime
from app.utils.supabase_client import get_supabase

# Tạo Blueprint cho trang khuyến mãi
promotions_bp = Blueprint("promotions", __name__)
logger = logging.getLogger(__name__)


@promotions_bp.route("/promotions")
def index():
    """Hiển thị danh sách các mã giảm giá đang hoạt động cho khách hàng"""
    try:
        db = get_supabase()
        now_str = datetime.now().isoformat()
        
        # Truy vấn: Lấy mã is_active = True VÀ (không có ngày hết hạn HOẶC ngày hết hạn > hiện tại)
        res = db.table("coupons") \
                .select("*") \
                .eq("is_active", True) \
                .or_(f"expires_at.is.null,expires_at.gt.{now_str}") \
                .order("created_at", desc=True) \
                .execute()
        
        coupons = res.data or []
        
        # Render file template bạn vừa tạo
        return render_template("coupons/index.html", coupons=coupons)
        
    except Exception as e:
        logger.error(f"Lỗi tải danh sách khuyến mãi (Storefront): {e}")
        # Fallback an toàn: Trả về mảng rỗng nếu lỗi DB
        return render_template("coupons/index.html", coupons=[])
