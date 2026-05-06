import requests

# 1. Điền Mã Vận Đơn đang cần test vào đây
TRACKING_CODE = "MOCK-960301" 
WEBHOOK_URL = "http://127.0.0.1:5000/admin/webhook/ghn"


def test_thanh_cong_webhook():
    print(f"🚀 Bắt đầu giả lập Webhook GIAO HÀNG THÀNH CÔNG cho vận đơn: {TRACKING_CODE}")
    
    # 2. Thay đổi Payload thành kịch bản Giao thành công (Delivered)
    payload = {
        "OrderCode": TRACKING_CODE,
        "Status": "delivered",  # Mã trạng thái báo hiệu Đã giao hàng thành công
        "Description": "Giao hàng thành công: Người nhận đã nhận kiện hàng an toàn.",
        "Warehouse": "Bưu cục phát Quận 1"
    }

    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        print(f"📡 Status Code trả về: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ TEST GIAO THÀNH CÔNG HOÀN TẤT! Hãy ra F5 lại trang đơn hàng và báo cáo doanh thu để xem kết quả.")
        else:
            print("❌ CÓ LỖI XẢY RA!")
            print(f"Nội dung lỗi: {response.text[:200]}...")
            
    except requests.exceptions.ConnectionError:
        print("❌ KHÔNG THỂ KẾT NỐI! Đảm bảo server Flask đang chạy tại cổng 5000.")


if __name__ == "__main__":
    test_thanh_cong_webhook()
