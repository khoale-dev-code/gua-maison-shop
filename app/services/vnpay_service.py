import hashlib
import hmac
import urllib.parse
from datetime import datetime


class VNPayService:

    @staticmethod
    def create_payment_url(order_id: str, amount: float, ip_address: str, order_desc: str=None) -> str:
        # HARDCODE KEY ĐỂ TRÁNH LỖI ENV
        vnp_TmnCode = "GQGO53PK"
        vnp_HashSecret = "8DOUH7Z99VJ220VXSUH1VGIXSN72QVZW"
        vnp_Url = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
        vnp_ReturnUrl = "http://127.0.0.1:5000/payment/vnpay_return"

        vnp_Amount = str(int(float(amount)) * 100)
        clean_order_id = str(order_id).replace("-", "")[:8]
        vnp_TxnRef = f"{clean_order_id}{datetime.now().strftime('%H%M%S')}"

        vnp_Params = {
            "vnp_Amount": vnp_Amount,
            "vnp_Command": "pay",
            "vnp_CreateDate": datetime.now().strftime('%Y%m%d%H%M%S'),
            "vnp_CurrCode": "VND",
            "vnp_IpAddr": "113.160.92.202",
            "vnp_Locale": "vn",
            "vnp_OrderInfo": "ThanhToanGUA",
            "vnp_OrderType": "other",
            "vnp_ReturnUrl": vnp_ReturnUrl,
            "vnp_TmnCode": vnp_TmnCode,
            "vnp_TxnRef": vnp_TxnRef,
            "vnp_Version": "2.1.0"
        }

        vnp_Params = {k: v for k, v in vnp_Params.items() if v is not None and str(v).strip() != ""}
        vnp_Params = dict(sorted(vnp_Params.items()))
        query_string = urllib.parse.urlencode(vnp_Params)

        hash_value = hmac.new(
            vnp_HashSecret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()

        return f"{vnp_Url}?{query_string}&vnp_SecureHash={hash_value}"

    @staticmethod
    def parse_response(request_args) -> dict:
        vnp_Params = request_args.to_dict()
        
        # Bóc chữ ký của VNPay ra để đối chiếu
        secure_hash = vnp_Params.pop('vnp_SecureHash', '')
        vnp_Params.pop('vnp_SecureHashType', None)

        # LỌC NGHIÊM NGẶT: Chỉ lấy các tham số hợp lệ của VNPay (Bắt đầu bằng vnp_)
        clean_params = {}
        for key, val in vnp_Params.items():
            if key.startswith('vnp_') and val is not None and str(val).strip() != "":
                clean_params[key] = val

        # Sắp xếp và nối chuỗi
        clean_params = dict(sorted(clean_params.items()))
        
        hash_data = []
        for key, val in clean_params.items():
            hash_data.append(key + "=" + urllib.parse.quote_plus(str(val)))
        
        query_string = "&".join(hash_data)
        
        # SỬ DỤNG LẠI CHÍNH XÁC KEY BẠN VỪA TẠO
        vnp_HashSecret = "8DOUH7Z99VJ220VXSUH1VGIXSN72QVZW"
        
        # Tự tính toán lại Hash
        my_hash = hmac.new(
            vnp_HashSecret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()

        # SO SÁNH (LƯU Ý: Phải ép về chữ thường (.lower()) để tránh lỗi phân biệt hoa/thường)
        is_valid = (my_hash.lower() == secure_hash.lower())

        # ---------------- IN LOG ĐỂ KIỂM TRA MÁY CHỦ ----------------
        print("\n" + "🌟" * 25)
        print("📥 BIÊN LAI TỪ VNPAY TRẢ VỀ:")
        for k, v in clean_params.items():
            print(f"  {k}: {v}")
        print("-" * 50)
        print(f"✅ Chuỗi tự nối:  {query_string}")
        print(f"✅ Hash tự tính:  {my_hash.lower()}")
        print(f"✅ Hash VNPay:    {secure_hash.lower()}")
        print(f"🎯 KẾT QUẢ KHỚP:  {is_valid}")
        print("🌟" * 25 + "\n")

        response_code = vnp_Params.get("vnp_ResponseCode", "")
        
        # Lấy lại order_id thật
        txn_ref = vnp_Params.get("vnp_TxnRef", "")
        order_id = txn_ref[:-6] if len(txn_ref) > 6 else txn_ref

        vn_pay_messages = {
            "00": "Giao dịch thành công",
            "24": "Khách hàng hủy giao dịch",
        }

        return {
            "is_valid": is_valid,
            "is_success": (response_code == "00"),
            "order_id": order_id,
            "transaction_id": vnp_Params.get("vnp_TransactionNo", txn_ref),
            "response_code": response_code,
            "message": vn_pay_messages.get(response_code, f"Lỗi VNPay: {response_code}")
        }
