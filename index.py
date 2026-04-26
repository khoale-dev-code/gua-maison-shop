 

import os
from app import create_app

# Khởi tạo ứng dụng Flask. 
# CỰC KỲ QUAN TRỌNG: Vercel sẽ tìm kiếm chính xác biến tên là `app` này để khởi chạy.
app = create_app()

if __name__ == "__main__":
    # Linh hoạt lấy Port từ biến môi trường, nếu không có thì mặc định là 5000
    port = int(os.environ.get("PORT", 5000))
    
    # Kích hoạt máy chủ phát triển (Dev Server). 
    # Lưu ý: Đoạn code trong block này sẽ KHÔNG chạy trên Vercel.
    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )