import requests

# 1. Điền Mã Vận Đơn MỚI của bạn vào đây
TRACKING_CODE = "MOCK-285934" 
WEBHOOK_URL = "http://127.0.0.1:5000/admin/webhook/ghn"


def test_boom_hang_webhook():
    print(f"🚀 Bắt đầu giả lập Webhook KHÁCH BOOM HÀNG cho vận đơn: {TRACKING_CODE}")
    
    # 2. Thay đổi Payload thành kịch bản Giao thất bại / Hoàn hàng
    payload = {
        "OrderCode": TRACKING_CODE,
        "Status": "return",  # Mã trạng thái của GHN báo hiệu Chuyển Hoàn
        "Description": "Giao hàng thất bại: Khách hàng từ chối nhận hàng. Đang chuyển hoàn về kho GUA.",
        "Warehouse": "Bưu cục phát Quận 1"
    }

    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        print(f"📡 Status Code trả về: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ TEST BOOM HÀNG THÀNH CÔNG! Hãy ra F5 lại trang đơn hàng để xem kết quả.")
        else:
            print("❌ CÓ LỖI XẢY RA!")
            print(f"Nội dung lỗi: {response.text[:200]}...")
            
    except requests.exceptions.ConnectionError:
        print("❌ KHÔNG THỂ KẾT NỐI! Đảm bảo server Flask đang chạy.")


if __name__ == "__main__":
    test_boom_hang_webhook()
