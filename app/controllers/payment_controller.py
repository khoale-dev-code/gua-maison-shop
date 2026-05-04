"""
app/controllers/payment_controller.py
Xử lý callback từ cổng thanh toán (VNPay).
Đảm bảo cập nhật trạng thái "paid" để Dashboard ghi nhận Doanh thu thực tế.
"""
import logging
from flask import Blueprint, request, redirect, url_for, flash, session

from app.services.vnpay_service import VNPayService
from app.models.order_model import OrderModel
from app.models.cart_model import CartModel

payment_bp = Blueprint("payment", __name__, url_prefix="/payment")
logger = logging.getLogger(__name__)


@payment_bp.route("/vnpay_return", methods=["GET"])
def vnpay_return():
    """
    Endpoint nhận kết quả trả về từ VNPay (Return URL).
    VNPay sẽ redirect trình duyệt khách về đây sau khi họ quẹt thẻ xong.
    """
    try:
        # 1. Nhận và bóc tách dữ liệu từ URL do VNPay trả về
        vnp_args = request.args.to_dict()
        
        # Parse qua Service để kiểm tra chữ ký (Checksum)
        result = VNPayService.parse_response(vnp_args)

        # Trích xuất các tham số quan trọng
        order_id = result.get("order_id") or vnp_args.get("vnp_TxnRef")
        transaction_id = result.get("transaction_id") or vnp_args.get("vnp_TransactionNo")
        response_code = vnp_args.get("vnp_ResponseCode")  # Lấy trực tiếp mã lỗi ngân hàng
        
        if not order_id:
            logger.warning("[VNPay Return] Thiếu mã đơn hàng (vnp_TxnRef).")
            flash("Giao dịch không hợp lệ: Không tìm thấy mã đơn hàng.", "danger")
            return redirect(url_for("cart.index"))

        logger.info(f"[VNPay Return] Đơn hàng: {order_id} | Mã phản hồi: {response_code} | Mã GD: {transaction_id}")

        # (Tùy chọn) Kiểm tra chữ ký bảo mật ở đây nếu VNPayService của bạn có hỗ trợ
        if result.get("is_valid") is False:
            logger.error(f"[VNPay Return] Chữ ký không hợp lệ cho đơn {order_id}!")
            flash("Giao dịch bị từ chối do sai lệch chữ ký bảo mật.", "danger")
            return redirect(url_for("cart.checkout"))

        # 2. XỬ LÝ KẾ TOÁN (Chỉ mã '00' là thanh toán thành công)
        if response_code == "00":
            # Ghi nhận 'paid' để Dashboard nhảy số Doanh thu thực tế
            success = OrderModel.update_payment_status(
                order_id=order_id,
                payment_status="paid",
                transaction_id=transaction_id
            )
            
            if success:
                # Dọn sạch giỏ hàng của user sau khi đã thanh toán xong
                user_id = session.get("user_id")
                if user_id:
                    try:
                        CartModel.clear_cart(str(user_id))
                    except Exception as e:
                        logger.error(f"[VNPay Return] Lỗi clear_cart cho user {user_id}: {e}")
                
                flash(f"🎉 Thanh toán VNPay thành công! Mã Giao Dịch: {transaction_id}", "success")
                
                # Chuyển hướng tới trang "Đặt hàng thành công"
                return redirect(url_for("cart.order_success", order_id=order_id))
            
            else:
                logger.error(f"[VNPay Return] Lỗi Update DB sang 'paid' cho đơn {order_id}")
                flash("Thanh toán thành công nhưng có lỗi ghi nhận hệ thống. Vui lòng liên hệ Admin.", "warning")
                return redirect(url_for("home.index"))
        
        else:
            # 3. XỬ LÝ THẤT BẠI (Khách hủy, thẻ hết tiền, thẻ lỗi...)
            OrderModel.update_payment_status(
                order_id=order_id,
                payment_status="failed",
                transaction_id=transaction_id
            )
            flash(f"Thanh toán chưa hoàn tất hoặc bị hủy (Mã lỗi ngân hàng: {response_code}).", "warning")
            
            # Trả khách về lại trang Checkout để họ chọn COD hoặc quẹt thẻ lại
            return redirect(url_for("cart.checkout"))

    except Exception as e:
        logger.exception(f"[VNPay Return] Lỗi hệ thống nghiêm trọng: {e}")
        flash("Có lỗi xảy ra trong quá trình xác nhận thanh toán. Vui lòng kiểm tra lại đơn hàng.", "danger")
        return redirect(url_for("home.index"))
