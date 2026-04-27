from flask import Blueprint, request, jsonify, render_template

# Khởi tạo Blueprint
ai_bp = Blueprint('ai_bp', __name__)


# 1. Route hiển thị giao diện Web
@ai_bp.route('/styling-lab', methods=['GET'])
def styling_lab_page():
    return render_template('features/styling_lab.html')


# 2. API xử lý logic AI (Backend)
@ai_bp.route('/api/recommend_outfit', methods=['POST'])
def recommend_outfit():
    try:
        # SỬA LỖI LINTER: Dùng request.get_json() an toàn hơn request.json
        data = request.get_json()
        
        # Lấy product_id an toàn
        product_id = data.get('product_id') if data else None
        
        # SỬA CẢNH BÁO "Unused variable": Tạm thời in ra màn hình terminal
        # Sau này bạn dùng nó để Query Database thì có thể xóa dòng print này
        if product_id:
            print(f"[GUA AI ENGINE] Đang khởi chạy phân tích cho sản phẩm ID: {product_id}")

        # [TODO: Xử lý logic AI / Query DB bằng Supabase tại đây]

        # Trả về Mock Data (Dữ liệu giả) để test UI
        mock_results = [
            {"id": "p1", "name": "Túi Crossbody Đen", "price": 1250000, "match_score": 98, "image": "https://images.unsplash.com/photo-1608248543803-ba4f8c70ae0b?w=400"},
            {"id": "p2", "name": "Quần Cargo Túi hộp", "price": 850000, "match_score": 92, "image": "https://images.unsplash.com/photo-1556821840-3a63f95609a7?w=400"},
            {"id": "p3", "name": "Mũ Cap GUA Thể thao", "price": 450000, "match_score": 85, "image": "https://images.unsplash.com/photo-1511556532299-8f662fc26c06?w=400"}
        ]

        return jsonify({
            "status": "success",
            "data": mock_results
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
