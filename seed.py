# import os
# import random
# import uuid
# from faker import Faker
# from supabase import create_client, Client
# from dotenv import load_dotenv

# load_dotenv()
# supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
# fake = Faker('vi_VN')  # Hỗ trợ sinh Tiếng Việt

# # Từ vựng tạo tên sản phẩm thời trang
# PREFIXES = ["GUA Matrix", "GUA Core", "GUA Heritage", "GUA Techwear", "GUA Essential"]
# ITEMS = ["Áo thun Oversize", "Quần Cargo", "Áo Hoodie", "Áo Khoác Bomber", "Túi Crossbody", "Quần Jogger", "Áo Len", "Giày Sneaker"]
# COLORS = ["Đen", "Trắng", "Xám Khói", "Xanh Rêu", "Be", "Navy"]

# # Bộ ảnh thời trang Unsplash (Chất lượng cao)
# FASHION_IMAGES = [
#     "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=800",
#     "https://images.unsplash.com/photo-1488161628813-04466f872be2?w=800",
#     "https://images.unsplash.com/photo-1608248543803-ba4f8c70ae0b?w=800",
#     "https://images.unsplash.com/photo-1556821840-3a63f95609a7?w=800",
#     "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=800",
#     "https://images.unsplash.com/photo-1503341455253-b2e723bb3dbb?w=800"
# ]

# def seed_fashion_data(num=50):
#     print(f"Bắt đầu sinh {num} sản phẩm thời trang ảo...")
    
#     try:
#         cat_res = supabase.table('categories').select('id').execute()
#         category_ids = [cat['id'] for cat in cat_res.data]
#     except Exception as e:
#         print("Lỗi lấy Categories:", e)
#         return
        
#     if not category_ids:
#         print("Bạn chưa có Category nào! Hãy tạo ít nhất 1 Category trước.")
#         return

#     for i in range(num):
#         cat_id = random.choice(category_ids)
#         product_id = str(uuid.uuid4())
        
#         # Sinh tên: VD "GUA Core Áo Hoodie Đen"
#         name = f"{random.choice(PREFIXES)} {random.choice(ITEMS)} {random.choice(COLORS)}"
        
#         # Giá từ 350k đến 2tr5
#         price = random.randint(35, 250) * 10000 
        
#         # Chọn ngẫu nhiên 1 ảnh chính
#         thumbnail = random.choice(FASHION_IMAGES)
        
#         product_data = {
#             "id": product_id,
#             "name": name,
#             "description": fake.paragraph(nb_sentences=3) + " Chất liệu thoáng khí, chống nước nhẹ, định hình form dáng kiến trúc.",
#             "price": price,
#             "stock": random.randint(0, 100),
#             "category_id": cat_id,
#             "thumbnail_url": thumbnail,
#             "is_featured": random.choice([True, False, False])  # Tỉ lệ 1/3 là nổi bật
#         }
        
#         try:
#             supabase.table('products').insert(product_data).execute()
            
#             # Thêm 2 ảnh phụ
#             for sort_order in range(1, 3):
#                 img_data = {
#                     "product_id": product_id,
#                     "url": random.choice(FASHION_IMAGES),
#                     "is_primary": False,
#                     "sort_order": sort_order
#                 }
#                 supabase.table('product_images').insert(img_data).execute()
                
#             print(f" Đã seed: {name}")
#         except Exception as e:
#             print(f" Lỗi seed {name}: {e}")

# if __name__ == "__main__":
#     seed_fashion_data(50)
