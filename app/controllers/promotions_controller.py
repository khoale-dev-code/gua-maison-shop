"""
app/controllers/promotions_controller.py
Quản lý trang Khuyến mãi / Mã giảm giá dành cho Khách hàng (Storefront)
"""

import logging
import io
import segno
from flask import Blueprint, render_template, send_file
from datetime import datetime
from app.utils.supabase_client import get_supabase

# Khởi tạo Blueprint và Logger
promotions_bp = Blueprint("promotions", __name__)
logger = logging.getLogger(__name__)


@promotions_bp.route("/promotions")
def index():
    """
    Hiển thị danh sách các mã giảm giá đang hoạt động cho khách hàng.
    Bao gồm cả hình ảnh (image_url) để hiển thị trên UI Editorial.
    """
    try:
        db = get_supabase()
        now_str = datetime.now().isoformat()
        
        # Lấy danh sách voucher: is_active = True VÀ (chưa hết hạn HOẶC không có hạn)
        res = db.table("coupons") \
                .select("*") \
                .eq("is_active", True) \
                .or_(f"expires_at.is.null,expires_at.gt.{now_str}") \
                .order("created_at", desc=True) \
                .execute()
        
        coupons = res.data or []
        
        return render_template("coupons/index.html", coupons=coupons)
        
    except Exception as e:
        logger.error(f"Lỗi tải danh sách khuyến mãi (Storefront): {e}")
        # Fallback an toàn: Trả về danh sách rỗng để UI không bị crash
        return render_template("coupons/index.html", coupons=[])


@promotions_bp.route("/api/coupons/qr/<code>")
def generate_qr(code):
    """
    Tạo và trả về hình ảnh QR Code dạng PNG từ mã khuyến mãi.
    Tạo trực tiếp trên RAM (In-memory buffer) để không chiếm dụng Storage.
    """
    try:
        if not code:
            return "Mã không hợp lệ", 400

        # Tạo QR với Segno, set error_correction mức cao (H) giúp quét dễ hơn
        qr = segno.make_qr(code.upper(), error='h')
        
        # Lưu vào buffer với màu sắc chuẩn Editorial (mực đen '#0e0e0e', nền kem '#faf8f5')
        img_io = io.BytesIO()
        qr.save(
            img_io,
            kind='png',
            scale=10,
            dark="#0e0e0e",
            light="#faf8f5",
            border=2
        )
        img_io.seek(0)
        
        return send_file(img_io, mimetype='image/png', as_attachment=False)
        
    except Exception as e:
        logger.error(f"Lỗi tạo QR code cho mã {code}: {e}")
        return "Lỗi tạo mã QR", 500


@promotions_bp.route("/promotions/<code>")
def detail(code):
    """
    Hiển thị trang chi tiết của một mã khuyến mãi cụ thể.
    """
    try:
        db = get_supabase()
        # Tìm mã khuyến mãi dựa trên code
        res = db.table("coupons") \
                .select("*") \
                .eq("code", code.upper()) \
                .single() \
                .execute()
        
        coupon = res.data
        if not coupon:
            return render_template("404.html"), 404  # Hoặc redirect về trang /promotions
            
        return render_template("coupons/detail.html", coupon=coupon)
        
    except Exception as e:
        logger.error(f"Lỗi tải chi tiết khuyến mãi {code}: {e}")
        return "Không tìm thấy đặc quyền này.", 404
