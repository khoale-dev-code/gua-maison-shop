# 👗 GUA Fashion Store

<div align="center">

**E-commerce thời trang cao cấp tích hợp AI gợi ý sản phẩm thông minh**

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS_v4-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)
![HuggingFace](https://img.shields.io/badge/HuggingFace-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black)

</div>

---

## 📌 Tổng quan

**GUA Fashion Store** là nền tảng thương mại điện tử thời trang kết hợp AI để đem lại trải nghiệm mua sắm thông minh. Hệ thống tích hợp mô hình **Sentence Transformers** (Hugging Face) và **FAISS** để gợi ý sản phẩm tương tự dựa trên ngữ nghĩa, cùng với **Vercell** làm nền tảng triển khai và **Supabase** quản lý dữ liệu theo thời gian thực.

### ✨ Tính năng nổi bật

| Tính năng | Mô tả |
|-----------|-------|
| 🤖 AI Gợi ý sản phẩm | Sentence Transformers + FAISS vector search |
| 🔍 Tìm kiếm ngữ nghĩa | Tìm theo mô tả, không cần đúng từ khóa |
| 🖼️ Xử lý ảnh sản phẩm | Pillow – resize, optimize, thumbnail |
| 🛒 Giỏ hàng & Thanh toán | Session-based, real-time với Supabase |
| 🔐 Xác thực bảo mật | bcrypt + Flask-Session server-side |
| 📊 Admin Dashboard | Quản lý sản phẩm, đơn hàng, người dùng |
| 🌐 CORS hỗ trợ | Flask-CORS cho tích hợp frontend linh hoạt |

---

## 🛠️ Tech Stack

```
Backend       →  Flask + Flask-CORS
Database      →  Supabase (PostgreSQL)
AI / ML       →  Sentence Transformers (HuggingFace) + FAISS + scikit-learn
Image         →  Pillow
Data          →  Pandas + Requests
Frontend      →  Jinja2 + TailwindCSS v4
Deploy        →  Vercel
```

---

## 🚀 Khởi động nhanh

### Yêu cầu hệ thống

- Python **3.10+**
- Tài khoản [Supabase](https://supabase.com) (free tier đủ dùng)
- Tài khoản [Vercel](https://vercel.com) (để deploy)

### 1. Clone repository

```bash
git clone https://github.com/your-username/gua-fashion-store.git
cd gua-fashion-store
```

### 2. Tạo môi trường ảo

```bash
python -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

> ⚠️ Lần đầu chạy, model Sentence Transformers sẽ tự động tải về (~90MB). Cần kết nối internet.

### 4. Cấu hình biến môi trường

```bash
cp .env.example .env
```

Mở file `.env` và điền đầy đủ thông tin:

```env
# Flask
SECRET_KEY=your-very-secret-key-here
FLASK_ENV=development

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-public-key

# AI Model (tùy chọn, mặc định dùng all-MiniLM-L6-v2)
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### 5. Khởi tạo Database

Mở **Supabase Dashboard** → **SQL Editor** → chạy file:

```
migrations/001_init_schema.sql
```

### 6. Khởi chạy server

```bash
python run.py
```

Truy cập: **http://localhost:5000** 🎉

---

## 📁 Cấu trúc dự án

```
gua-fashion-store/
│
├── run.py                          # 🚪 Entry point
├── requirements.txt                # 📦 Dependencies
├── .env                            # 🔒 Biến môi trường (KHÔNG commit)
├── .env.example                    # 📋 Template cấu hình
├── vercel.json                     # ☁️  Cấu hình deploy Vercel
│
├── config/
│   └── settings.py                 # ⚙️  Config theo môi trường (dev/prod)
│
├── migrations/
│   └── 001_init_schema.sql         # 🗄️  Schema khởi tạo Supabase
│
└── app/
    ├── __init__.py                 # 🏭 Application Factory
    │
    ├── controllers/                # 🎮 (C) Route handlers
    │   ├── auth_controller.py      #    Đăng ký / Đăng nhập / Đăng xuất
    │   ├── product_controller.py   #    Danh sách, chi tiết, tìm kiếm AI
    │   ├── cart_controller.py      #    Giỏ hàng & Checkout
    │   └── admin_controller.py     #    Quản trị viên
    │
    ├── models/                     # 🗃️  (M) Database operations
    │   ├── user_model.py
    │   ├── product_model.py
    │   ├── cart_model.py
    │   └── order_model.py
    │
    ├── templates/                  # 🎨 (V) Jinja2 HTML Templates
    │   ├── base.html
    │   ├── partials/
    │   ├── auth/
    │   ├── products/
    │   ├── cart/
    │   └── admin/
    │
    ├── middleware/
    │   └── auth_required.py        # 🛡️  Decorator: login_required, admin_required
    │
    └── utils/
        ├── supabase_client.py      # 🔌 Singleton Supabase client
        ├── ai_recommender.py       # 🤖 FAISS + Sentence Transformers engine
        └── security.py             # 🔐 bcrypt hash / verify
```

---

## 🤖 AI Recommendation Engine

Hệ thống gợi ý sản phẩm hoạt động theo pipeline:

```
Mô tả sản phẩm
      │
      ▼
Sentence Transformers (HuggingFace)
      │  → Vector embedding (384 chiều)
      ▼
FAISS Index (vector database)
      │  → cosine similarity search
      ▼
Top-K sản phẩm tương tự
      │
      ▼
scikit-learn (re-ranking / filtering)
      │
      ▼
Kết quả gợi ý cho người dùng
```

**Model mặc định:** `sentence-transformers/all-MiniLM-L6-v2`
- Nhẹ (~90MB), tốc độ nhanh, phù hợp production
- Hỗ trợ đa ngôn ngữ (bao gồm Tiếng Việt)

---

## 🗺️ API Routes

### 👤 Authentication

| Route | Method | Mô tả |
|-------|--------|-------|
| `/auth/register` | GET / POST | Đăng ký tài khoản |
| `/auth/login` | GET / POST | Đăng nhập |
| `/auth/logout` | GET | Đăng xuất |

### 🛍️ Products

| Route | Method | Mô tả |
|-------|--------|-------|
| `/` | GET | Trang chủ |
| `/shop` | GET | Danh sách sản phẩm |
| `/product/<id>` | GET | Chi tiết sản phẩm |
| `/product/<id>/similar` | GET | Gợi ý sản phẩm tương tự (AI) |

### 🛒 Cart & Checkout

| Route | Method | Mô tả |
|-------|--------|-------|
| `/cart/` | GET | Xem giỏ hàng |
| `/cart/add` | POST | Thêm sản phẩm vào giỏ |
| `/cart/remove` | POST | Xoá sản phẩm khỏi giỏ |
| `/cart/checkout` | GET / POST | Thanh toán đơn hàng |

### 🔧 Admin

| Route | Method | Mô tả |
|-------|--------|-------|
| `/admin/` | GET | Dashboard tổng quan |
| `/admin/products` | GET | Danh sách sản phẩm |
| `/admin/products/create` | GET / POST | Thêm sản phẩm mới |
| `/admin/orders` | GET | Quản lý đơn hàng |

---

## 🔐 Bảo mật

- 🔑 **Password hashing** – bcrypt với cost factor 12, không lưu plain-text
- 🍪 **Server-side session** – Flask-Session lưu trên filesystem
- 🛡️ **Access control** – Decorator `@login_required` / `@admin_required`
- 🌐 **Cookie flags** – `HttpOnly=True`, `SameSite=Lax`
- 🔒 **Secret key** – Cấu hình qua biến môi trường, không hardcode

---

## 📦 Dependencies chính

```
flask                    # Web framework
flask-cors               # Cross-Origin Resource Sharing
sentence-transformers    # HuggingFace embedding models
faiss-cpu                # Vector similarity search
Pillow                   # Image processing
requests                 # HTTP client
pandas                   # Data manipulation
scikit-learn             # ML utilities (re-ranking, preprocessing)
```

Xem đầy đủ: [`requirements.txt`](./requirements.txt)

---

## ☁️ Deploy lên Vercel

```bash
# Cài Vercel CLI
npm i -g vercel

# Login
vercel login

# Deploy
vercel --prod
```

Đảm bảo đã thêm các biến môi trường trong **Vercel Dashboard → Settings → Environment Variables**.

> ⚠️ FAISS và Sentence Transformers tốn RAM. Nên dùng Vercel Pro hoặc tách AI service thành microservice riêng khi production.

---

## 🤝 Đóng góp

1. Fork repository
2. Tạo branch mới: `git checkout -b feature/ten-tinh-nang`
3. Commit changes: `git commit -m 'feat: thêm tính năng X'`
4. Push lên branch: `git push origin feature/ten-tinh-nang`
5. Mở Pull Request

---

## 📄 License

Dự án này được phát hành dưới giấy phép [MIT](./LICENSE).

---

<div align="center">

Made with ❤️ by **Khoa** · GUA Fashion Store © 2026

</div>