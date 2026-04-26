-- ============================================================
-- migrations/001_init_schema.sql
-- Chạy file này trong Supabase SQL Editor để khởi tạo DB
-- ⚠️  Có thể chạy lại nhiều lần – an toàn (IF NOT EXISTS)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── 1. USERS ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name     TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'customer' CHECK (role IN ('customer', 'admin')),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ── Tài khoản admin mặc định ─────────────────────────────────
-- Email : admin@gmail.com
-- Pass  : admin
INSERT INTO users (email, password_hash, full_name, role)
VALUES (
    'admin@gmail.com',
    '$2b$12$MBQioTsXW47B20d8sjncGuScNUFBQG86aBrEVybAraueJMgp2BGHC',
    'Administrator',
    'admin'
)
ON CONFLICT (email) DO UPDATE
    SET password_hash = EXCLUDED.password_hash,
        role          = 'admin',
        full_name     = 'Administrator';

-- ── 2. CATEGORIES ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS categories (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name       TEXT NOT NULL,
    slug       TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO categories (name, slug) VALUES
    ('Nữ',       'women'),
    ('Nam',      'men'),
    ('Phụ kiện', 'accessories'),
    ('Sale',     'sale')
ON CONFLICT (slug) DO NOTHING;

-- ── 3. PRODUCTS ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS products (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name          TEXT NOT NULL,
    description   TEXT,
    price         NUMERIC(12, 0) NOT NULL DEFAULT 0,
    stock         INTEGER NOT NULL DEFAULT 0,
    category_id   UUID REFERENCES categories(id) ON DELETE SET NULL,
    thumbnail_url TEXT,
    is_featured   BOOLEAN DEFAULT FALSE,
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ── 4. PRODUCT IMAGES ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS product_images (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    url        TEXT NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE
);

-- ── 5. CART ITEMS ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cart_items (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    quantity   INTEGER NOT NULL DEFAULT 1,
    size       TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── 6. ORDERS ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          UUID REFERENCES users(id) ON DELETE SET NULL,
    total_amount     NUMERIC(14, 0) NOT NULL DEFAULT 0,
    shipping_address JSONB,
    status           TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','processing','shipped','delivered','cancelled')),
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ── 7. ORDER ITEMS ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS order_items (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id   UUID REFERENCES orders(id) ON DELETE CASCADE,
    product_id UUID REFERENCES products(id) ON DELETE SET NULL,
    quantity   INTEGER NOT NULL,
    unit_price NUMERIC(12, 0) NOT NULL,
    size       TEXT
);

-- ── Indexes ──────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_featured ON products(is_featured) WHERE is_featured = TRUE;
CREATE INDEX IF NOT EXISTS idx_cart_user         ON cart_items(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_user       ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);

-- ── Sample products (8 sản phẩm) ─────────────────────────────
INSERT INTO products (name, description, price, stock, thumbnail_url, is_featured)
SELECT name, description, price, stock, thumbnail_url, is_featured
FROM (VALUES
    ('Áo Blazer Linen Trắng',   'Chất liệu linen cao cấp, dáng regular fit thanh lịch',           890000,  20, 'https://images.unsplash.com/photo-1594938298603-c8148c4b4571?w=500', TRUE),
    ('Quần Culottes Đen',       'Vải crepe mềm mại, ống rộng thời thượng, cạp cao',               650000,  15, 'https://images.unsplash.com/photo-1506629082955-511b1aa562c8?w=500', TRUE),
    ('Váy Midi Floral',         'Họa tiết hoa nhẹ nhàng, phù hợp mọi dịp, chất liệu thoáng mát', 750000,  30, 'https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=500', TRUE),
    ('Áo Khoác Trench Coat',    'Phong cách cổ điển, màu camel thanh lịch, chống gió nhẹ',       1590000,  10, 'https://images.unsplash.com/photo-1539533018447-63fcce2678e4?w=500', TRUE),
    ('Áo Thun Oversize Trắng',  'Cotton 100%, form rộng thoải mái, basic nhưng đẳng cấp',         350000,  50, 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=500', TRUE),
    ('Chân Váy Mini Kẻ Caro',   'Họa tiết caro cổ điển, vải dày dặn, phù hợp đi làm đi chơi',   490000,  25, 'https://images.unsplash.com/photo-1583496661160-fb5218ees4b5?w=500', FALSE),
    ('Quần Jeans Straight',     'Denim cao cấp, dáng thẳng chuẩn, wash nhạt tinh tế',             780000,  18, 'https://images.unsplash.com/photo-1542272604-787c3835535d?w=500', TRUE),
    ('Áo Sơ Mi Lụa Trơn',      'Chất lụa mềm mượt, màu be sang trọng, phù hợp công sở',         680000,  22, 'https://images.unsplash.com/photo-1604695573706-53170668f6a6?w=500', FALSE)
) AS v(name, description, price, stock, thumbnail_url, is_featured)
WHERE NOT EXISTS (SELECT 1 FROM products LIMIT 1);

SELECT 
    '✅ Schema khởi tạo thành công!' AS status,
    (SELECT COUNT(*) FROM users)    AS total_users,
    (SELECT COUNT(*) FROM products) AS total_products,
    (SELECT email FROM users WHERE role = 'admin' LIMIT 1) AS admin_email;
