"""
app/controllers/payment_controller.py
Xử lý kết quả thanh toán từ VNPay.
"""
import logging
from datetime import datetime
from flask import Blueprint, request, redirect, flash, session

from app.services.vnpay_service import VNPayService
from app.models.order_model import OrderModel
from app.models.cart_model import CartModel
from app.utils.supabase_client import get_supabase

payment_bp = Blueprint("payment", __name__, url_prefix="/payment")
logger = logging.getLogger(__name__)


@payment_bp.route("/vnpay_return", methods=["GET"])
def vnpay_return():
    """
    Endpoint nhận kết quả trả về từ VNPay sau khi khách thanh toán.
    """
    try:
        # 1. Chuyển đổi MultiDict của Flask sang Dict chuẩn Python
        vnp_args = request.args.to_dict()
        
        # 2. Gọi Service để kiểm tra chữ ký và bóc tách dữ liệu
        result = VNPayService.parse_response(vnp_args)
        
        # Lấy các thông tin định danh
        order_id = result.get("order_id") 
        transaction_id = result.get("transaction_id")
        response_code = result.get("response_code")
        is_valid = result.get("is_valid")

        logger.info(f"[VNPay Return] Nhận phản hồi cho đơn: {order_id} | Mã: {response_code}")

        # 3. Kiểm tra tính hợp lệ của chữ ký (Checksum)
        if not is_valid:
            logger.error(f"[VNPay Return] Chữ ký không hợp lệ cho đơn {order_id}!")
            flash("Dữ liệu thanh toán bị sai lệch (Checksum failed).", "danger")
            return redirect("/") 

        if not order_id:
            flash("Không tìm thấy thông tin đơn hàng.", "danger")
            return redirect("/")

        # ─── THÊM MỚI: GHI LOG VÀO BẢNG PAYMENTS (Lịch sử giao dịch) ───
        try:
            db = get_supabase()
            # VNPay trả về số tiền nhân 100, nên ta chia lại để lấy số tiền thực
            amount = float(vnp_args.get("vnp_Amount", 0)) / 100.0
            
            # Phân loại trạng thái giao dịch
            payment_status_db = "success" if response_code == "00" else "failed"
            paid_at = datetime.now().isoformat() if response_code == "00" else None
            
            db.table("payments").insert({
                "order_id": order_id,
                "provider": "vnpay",
                "transaction_id": transaction_id,
                "amount": amount,
                "status": payment_status_db,
                "raw_response": vnp_args,  # Lưu toàn bộ chuỗi JSON trả về để đối soát
                "paid_at": paid_at
            }).execute()
            
            logger.info(f"[VNPay Return] Đã lưu log giao dịch vào bảng payments.")
        except Exception as e:
            # Dùng try-except bọc lại để nếu lỗi ghi log cũng không làm sập luồng mua hàng của khách
            logger.error(f"[VNPay Return] Lỗi ghi log bảng payments cho đơn {order_id}: {e}")
        # ───────────────────────────────────────────────────────────────

        # 4. XỬ LÝ THEO MÃ PHẢN HỒI (00 = THÀNH CÔNG)
        if response_code == "00":
            # Cập nhật trạng thái 'paid' cho đơn hàng
            update_success = OrderModel.update_payment_status(
                order_id=order_id,
                payment_status="paid",
                transaction_id=transaction_id
            )
            
            if update_success:
                # Xóa giỏ hàng sau khi mua thành công
                user_id = session.get("user_id")
                if user_id:
                    try:
                        CartModel.clear_cart(str(user_id))
                    except Exception as e:
                        logger.error(f"[VNPay Return] Lỗi dọn giỏ hàng: {e}")

                flash("🎉 Thanh toán thành công! Cảm ơn bạn đã ủng hộ GUA Maison.", "success")
                return redirect(f"/cart/order-success/{order_id}")
            else:
                logger.error(f"[VNPay Return] Database từ chối cập nhật UUID: {order_id}")
                flash("Thanh toán thành công nhưng hệ thống chưa cập nhật kịp. Vui lòng liên hệ hỗ trợ.", "warning")
                return redirect("/")
        
        else:
            # 5. XỬ LÝ KHI GIAO DỊCH THẤT BẠI (Khách hủy, lỗi thẻ...)
            OrderModel.update_payment_status(
                order_id=order_id,
                payment_status="failed",
                transaction_id=transaction_id
            )
            flash(f"Giao dịch không thành công (Mã lỗi: {response_code}). Vui lòng thử lại.", "warning")
            return redirect("/cart/checkout")

    except Exception as e:
        logger.error(f"[VNPay Return] Lỗi hệ thống: {str(e)}", exc_info=True)
        flash("Có lỗi kỹ thuật xảy ra khi xử lý thanh toán.", "danger")
        return redirect("/")
