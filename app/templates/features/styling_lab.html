<div align="center">

<br/>

# 👗 GUA Maison

### Nền tảng thương mại điện tử thời trang cao cấp tích hợp AI

<br/>

![Python](https://img.shields.io/badge/Python_3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask_3.x-000000?style=for-the-badge&logo=flask&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/Tailwind_v4-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)
![HuggingFace](https://img.shields.io/badge/HuggingFace-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black)
![Vercel](https://img.shields.io/badge/Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)

<br/>

</div>

---

## Tổng quan

**GUA Maison** là nền tảng mua sắm thời trang được xây dựng theo kiến trúc **MVC** với Flask, tích hợp pipeline AI hoàn chỉnh gồm phân tích hình thể người dùng, gợi ý trang phục cá nhân hoá và tìm kiếm bằng hình ảnh. Dữ liệu vận hành theo thời gian thực trên Supabase, AI microservice chạy độc lập trên Hugging Face Spaces.

---

## Tính năng

**Mua sắm & Trải nghiệm**
- Trang sản phẩm, tìm kiếm, lọc theo danh mục và giá
- Giỏ hàng theo session, quy trình thanh toán đa bước
- Trang chi tiết sản phẩm với gợi ý sản phẩm liên quan theo ngữ nghĩa

**AI — Styling Lab**
- Tải ảnh toàn thân → AI phân tích hình thể (dáng người, chiều cao, vóc dáng)
- Gợi ý phong cách phù hợp: Streetwear · Minimalist · Techwear · Smart Casual
- Tìm kiếm sản phẩm bằng hình ảnh (visual search) sử dụng CLIP + FAISS
- Điểm độ phù hợp trang phục từ 0–100% dựa trên body affinity

**Quản trị**
- Dashboard thống kê doanh thu, đơn hàng, sản phẩm bán chạy
- CRUD sản phẩm với upload ảnh và quản lý danh mục
- Quản lý đơn hàng và tài khoản người dùng

**Bảo mật**
- Mật khẩu mã hoá bcrypt, không lưu plain-text
- Server-side session với Flask-Session
- Kiểm soát truy cập theo vai trò (user / admin)
- Cookie `HttpOnly`, `SameSite=Lax`

---

## Thư viện Python

| Thư viện | Vai trò |
|---|---|
| **Flask** | Web framework chính, routing, Jinja2 template engine |
| **Flask-CORS** | Xử lý Cross-Origin request giữa Vercel và HF Spaces |
| **Flask-Session** | Lưu session phía server (filesystem), thay thế client-side cookie |
| **sentence-transformers** | Chạy mô hình CLIP (clip-ViT-B-32) để encode ảnh và text thành vector |
| **faiss-cpu** | Vector database tốc độ cao — tìm kiếm cosine similarity trên embedding |
| **scikit-learn** | TF-IDF vectorizer cho content-based recommendation, cosine similarity |
| **Pillow** | Decode và xử lý ảnh người dùng upload trước khi đưa vào model |
| **Pandas** | Xây dựng DataFrame cho recommendation engine và báo cáo doanh thu |
| **Requests** | Gọi HTTP đến Supabase Storage và AI microservice trên HF Spaces |
| **bcrypt** | Hash và verify mật khẩu người dùng |
| **python-dotenv** | Load biến môi trường từ file `.env` |
| **numpy** | Tính toán ma trận vector, softmax, cosine similarity trong AI pipeline |

---

## Kiến trúc hệ thống

```
Trình duyệt
    │
    ▼
Vercel (Flask App)
    ├── Controllers  →  Auth / Product / Cart / Admin / AI
    ├── Models       →  Supabase (PostgreSQL)
    └── Templates    →  Jinja2 + TailwindCSS v4
         │
         ▼ (khi có ảnh người dùng)
Hugging Face Spaces (AI Microservice - Flask)
    ├── /analyze-style   →  CLIP encode + body heuristic → vibe suggestion
    ├── /search          →  FAISS visual search
    ├── /recommend       →  TF-IDF content-based filtering
    └── /analyze-sales   →  Pandas reporting engine
```

---

## Cấu trúc dự án

```
gua-fashion-store/
│
├── run.py                          # Entry point
├── requirements.txt
├── vercel.json
├── .env.example
│
├── config/
│   └── settings.py                 # Cấu hình theo môi trường dev / prod
│
├── migrations/
│   └── 001_init_schema.sql         # Schema Supabase
│
└── app/
    ├── __init__.py                 # Application Factory
    │
    ├── controllers/
    │   ├── auth_controller.py
    │   ├── product_controller.py
    │   ├── cart_controller.py
    │   ├── admin_controller.py
    │   └── ai_controller.py        # Styling Lab + /api/recommend_outfit
    │
    ├── models/
    │   ├── user_model.py
    │   ├── product_model.py
    │   ├── cart_model.py
    │   └── order_model.py
    │
    ├── templates/
    │   ├── base.html
    │   ├── features/
    │   │   └── styling_lab.html    # AI Styling Lab UI
    │   ├── auth/ · products/ · cart/ · admin/
    │
    ├── middleware/
    │   └── auth_required.py        # @login_required · @admin_required
    │
    └── utils/
        ├── supabase_client.py      # Singleton Supabase client
        └── security.py             # bcrypt helpers
```

---

## Khởi động nhanh

**Yêu cầu:** Python 3.10+, tài khoản Supabase, tài khoản Vercel

```bash
# 1. Clone & vào thư mục
git clone https://github.com/your-username/gua-fashion-store.git
cd gua-fashion-store

# 2. Tạo môi trường ảo
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Cài dependencies
pip install -r requirements.txt

# 4. Cấu hình môi trường
cp .env.example .env
# → Điền SUPABASE_URL, SUPABASE_KEY, SECRET_KEY, AI_ENGINE_URL

# 5. Khởi tạo database
# Mở Supabase Dashboard → SQL Editor → chạy migrations/001_init_schema.sql

# 6. Chạy server
python run.py
# → http://localhost:5000
```

> **Lưu ý:** Lần đầu khởi động, model CLIP (~600MB) sẽ được tải tự động bởi HF Spaces. Cần kết nối internet.

---

## Deploy

```bash
npm i -g vercel
vercel login
vercel --prod
```

Thêm biến môi trường tại **Vercel Dashboard → Settings → Environment Variables**.

AI microservice được host riêng trên **Hugging Face Spaces** (Docker, port 7860) để tách biệt tài nguyên RAM/GPU khỏi Vercel.

---

## License

[MIT](./LICENSE) © 2026 **Khoa** — GUA Maison