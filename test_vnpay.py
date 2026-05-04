import hashlib
import hmac
import urllib.parse
from datetime import datetime


def debug_vnpay():
    print("="*60)
    print("🔬 VNPAY DEEP DEBUGGER - KIỂM TRA TỪNG KÝ TỰ")
    print("="*60)

    # 1. Hardcode Data tĩnh 100% để loại bỏ lỗi do biến môi trường
    vnp_TmnCode = "GQGO53PK"
    vnp_HashSecret = "8DOUH7Z99VJ220VXSUH1VGIXSN72QVZW"
    vnp_Url = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
    vnp_ReturnUrl = "http://127.0.0.1:5000/payment/vnpay_return"
    
    # Tạo mã đơn hàng cố định cho dễ test
    txn_ref = f"DEBUG{datetime.now().strftime('%H%M%S')}"

    # 2. Tham số chuẩn
    vnp_Params = {
        "vnp_Amount": "10000000",  # 100,000 VND
        "vnp_Command": "pay",
        "vnp_CreateDate": datetime.now().strftime('%Y%m%d%H%M%S'),
        "vnp_CurrCode": "VND",
        "vnp_IpAddr": "113.160.92.202",
        "vnp_Locale": "vn",
        "vnp_OrderInfo": "ThanhToanGUA",
        "vnp_OrderType": "other",
        "vnp_ReturnUrl": vnp_ReturnUrl,
        "vnp_TmnCode": vnp_TmnCode,
        "vnp_TxnRef": txn_ref,
        "vnp_Version": "2.1.0"
    }

    # 3. Sắp xếp key
    vnp_Params = dict(sorted(vnp_Params.items()))

    # 4. Build Query String (Dùng quote_plus chuẩn)
    qs_list = []
    for k, v in vnp_Params.items():
        qs_list.append(f"{k}={urllib.parse.quote_plus(str(v))}")
    query_string = "&".join(qs_list)

    # 5. Hash
    hash_value = hmac.new(
        vnp_HashSecret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha512
    ).hexdigest()

    payment_url = f"{vnp_Url}?{query_string}&vnp_SecureHash={hash_value}"

    # ─── BẮT ĐẦU SOI KÝ TỰ TỪNG CHÚT MỘT ───
    
    print("\n[1] KIỂM TRA SECRET KEY (Bắt lỗi khoảng trắng, dấu enter ẩn):")
    print(f"Độ dài lý thuyết: 32 | Độ dài thực tế: {len(vnp_HashSecret)}")
    for i, char in enumerate(vnp_HashSecret):
        # Ký tự hợp lệ thường nằm trong khoảng ASCII 48-57 (số) và 65-90 (chữ in hoa)
        is_weird = ord(char) < 33 or ord(char) > 126
        warning = " <--- ⚠️ KÝ TỰ LẠ!" if is_weird else ""
        print(f"  Vị trí [{i:02d}]: '{char}' (ASCII: {ord(char)}){warning}")

    print("\n[2] KIỂM TRA QUERY STRING:")
    print("Chuỗi mang đi Hash:")
    print(query_string)

    print("\n[3] CHỮ KÝ SHA-512 TẠO RA:")
    print(hash_value)

    print("\n[4] 🚀 URL THANH TOÁN TEST CỦA BẠN:")
    print("-" * 60)
    print(payment_url)
    print("-" * 60)
    print("\n👉 HƯỚNG DẪN: Hãy COPY đoạn URL ở mục [4], dán thẳng vào Google Chrome/Safari và ấn Enter.")


if __name__ == "__main__":
    debug_vnpay()
