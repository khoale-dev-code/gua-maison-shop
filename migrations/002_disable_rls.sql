-- ============================================================
-- migrations/002_disable_rls.sql
-- ⚡ CHẠY FILE NÀY SAU 001_init_schema.sql
-- Tắt Row Level Security cho tất cả bảng
-- (cần thiết khi dùng publishable/anon key từ Flask backend)
-- ============================================================

-- Tắt RLS
ALTER TABLE users         DISABLE ROW LEVEL SECURITY;
ALTER TABLE categories    DISABLE ROW LEVEL SECURITY;
ALTER TABLE products      DISABLE ROW LEVEL SECURITY;
ALTER TABLE product_images DISABLE ROW LEVEL SECURITY;
ALTER TABLE cart_items    DISABLE ROW LEVEL SECURITY;
ALTER TABLE orders        DISABLE ROW LEVEL SECURITY;
ALTER TABLE order_items   DISABLE ROW LEVEL SECURITY;

-- Cấp quyền đọc/ghi cho anon và authenticated role
GRANT ALL ON ALL TABLES    IN SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated;
GRANT USAGE ON SCHEMA public TO anon, authenticated;

-- Xác nhận
SELECT
    tablename,
    rowsecurity AS rls_enabled
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
