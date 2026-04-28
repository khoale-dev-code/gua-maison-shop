import os
import requests
import uuid
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))


def seed_data():
    print("Đang lấy dữ liệu từ API...")
    response = requests.get("https://dummyjson.com/products?limit=50")  # Lấy 50 sản phẩm
    
    if response.status_code != 200:
        print("Lỗi gọi API")
        return
        
    products = response.json().get('products', [])
    
    # 1. Lấy danh sách category hiện có từ DB của bạn (hoặc tạo mới)
    # Giả sử bạn đã có Categories, ta lấy ra ID của chúng.
    # Trong thực tế, bạn có thể map category từ API sang DB của bạn.
    try:
        cat_res = supabase.table('categories').select('id').execute()
        category_ids = [cat['id'] for cat in cat_res.data]
    except Exception as e:
        print("Không thể lấy Categories:", e)
        return
        
    if not category_ids:
        print("Bạn chưa có Category nào trong CSDL! Hãy thêm Category trước.")
        return

    print("Bắt đầu Insert vào Supabase...")
    for p in products:
        # Chọn ngẫu nhiên 1 category_id
        import random
        cat_id = random.choice(category_ids)
        
        # Tạo UUID cho sản phẩm
        product_id = str(uuid.uuid4())
        
        # INSERT Product
        product_data = {
            "id": product_id,
            "name": p.get('title'),
            "description": p.get('description'),
            "price": p.get('price') * 25000,  # Giả lập đổi ra VNĐ
            "stock": p.get('stock'),
            "category_id": cat_id,
            "thumbnail_url": p.get('thumbnail'),
            "is_featured": random.choice([True, False])
        }
        
        try:
            supabase.table('products').insert(product_data).execute()
            
            # INSERT Product Images
            images = p.get('images', [])
            for idx, img_url in enumerate(images):
                img_data = {
                    "product_id": product_id,
                    "url": img_url,
                    "is_primary": True if idx == 0 else False,
                    "sort_order": idx
                }
                supabase.table('product_images').insert(img_data).execute()
                
            print(f" Đã thêm: {product_data['name']}")
        except Exception as e:
            print(f"Lỗi khi insert {product_data['name']}: {e}")
            
    print("Hoàn tất!")


if __name__ == "__main__":
    seed_data()
