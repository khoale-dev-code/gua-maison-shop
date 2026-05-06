"""
app/services/vnpay_service.py
Dịch vụ tích hợp cổng thanh toán VNPay Version 2.1.0.
"""
import hashlib
import hmac
import urllib.parse
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class VNPayService:
    TMN_CODE = "GQGO53PK"
    HASH_SECRET = "8DOUH7Z99VJ220VXSUH1VGIXSN72QVZW"
    PAYMENT_URL = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
    RETURN_URL = "http://127.0.0.1:5000/payment/vnpay_return"

    @classmethod
    def create_payment_url(cls, order_id: str, amount: float, ip_address: str, order_desc: str=None) -> str:
        """Tạo URL thanh toán gửi sang VNPay"""
        
        # 1. Định dạng số tiền (VNPay yêu cầu nhân 100)
        vnp_Amount = str(int(float(amount)) * 100)
        
        # Giữ nguyên mã UUID đầy đủ
        vnp_TxnRef = str(order_id)

        vnp_Params = {
            "vnp_Version": "2.1.0",
            "vnp_Command": "pay",
            "vnp_TmnCode": cls.TMN_CODE,
            "vnp_Amount": vnp_Amount,
            "vnp_CurrCode": "VND",
            "vnp_TxnRef": vnp_TxnRef,
            # Bổ sung lại order_desc từ Controller truyền sang
            "vnp_OrderInfo": order_desc or f"ThanhToanGUA_{vnp_TxnRef[:8]}",
            "vnp_OrderType": "other",
            "vnp_Locale": "vn",
            "vnp_ReturnUrl": cls.RETURN_URL,
            "vnp_IpAddr": ip_address or "127.0.0.1",
            "vnp_CreateDate": datetime.now().strftime('%Y%m%d%H%M%S'),
        }

        # 2. Sắp xếp tham số theo alphabet
        vnp_Params = dict(sorted(vnp_Params.items()))
        
        # 3. Tạo chuỗi Hash (Query String)
        query_string = urllib.parse.urlencode(vnp_Params)

        # 4. Tính toán chữ ký bảo mật HMAC-SHA512
        hash_value = hmac.new(
            cls.HASH_SECRET.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()

        return f"{cls.PAYMENT_URL}?{query_string}&vnp_SecureHash={hash_value}"

    @classmethod
    def parse_response(cls, request_args) -> dict:
        """Xác thực và phân tích phản hồi từ VNPay gửi về"""
        
        # Chống lỗi AttributeError to_dict()
        if hasattr(request_args, 'to_dict'):
            vnp_Params = request_args.to_dict()
        else:
            vnp_Params = dict(request_args)
            
        # Lấy chữ ký từ VNPay trả về
        vnp_SecureHash = vnp_Params.pop('vnp_SecureHash', None)
        vnp_Params.pop('vnp_SecureHashType', None)

        # 1. Sắp xếp lại tham số còn lại để tính Hash đối chiếu
        vnp_Params = dict(sorted(vnp_Params.items()))
        
        # 2. Tạo chuỗi dữ liệu để băm
        hash_data = []
        for key, val in vnp_Params.items():
            if key.startswith('vnp_') and val:
                hash_data.append(f"{key}={urllib.parse.quote_plus(str(val))}")
        
        hash_string = "&".join(hash_data)
        
        # 3. Tính toán Hash đối ứng
        calculated_hash = hmac.new(
            cls.HASH_SECRET.encode('utf-8'),
            hash_string.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()

        # 4. Kiểm tra tính hợp lệ
        is_valid = (calculated_hash.lower() == str(vnp_SecureHash).lower())
        
        response_code = vnp_Params.get("vnp_ResponseCode", "")
        # Lấy lại order_id nguyên bản (UUID) từ vnp_TxnRef
        order_id = vnp_Params.get("vnp_TxnRef") 

        error_messages = {
            "00": "Giao dịch thành công",
            "07": "Trừ tiền thành công. Giao dịch bị nghi ngờ (liên quan tới lừa đảo).",
            "09": "Thẻ/Tài khoản chưa đăng ký Internet Banking.",
            "10": "Xác thực thông tin thẻ/tài khoản không đúng quá 3 lần.",
            "11": "Hết hạn chờ thanh toán.",
            "24": "Khách hàng hủy giao dịch",
            "51": "Tài khoản không đủ số dư.",
            "75": "Ngân hàng đang bảo trì.",
        }

        return {
            "is_valid": is_valid,
            "order_id": order_id,
            "transaction_id": vnp_Params.get("vnp_TransactionNo"),
            "response_code": response_code,
            "message": error_messages.get(response_code, f"Lỗi không xác định: {response_code}")
        }
