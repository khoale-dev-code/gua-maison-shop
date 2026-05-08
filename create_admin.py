"""
create_admin.py
===============
Script chạy MỘT LẦN để tạo tài khoản admin cố định.
Chạy từ thư mục gốc dự án:
    python create_admin.py

Xóa file này sau khi chạy xong.
"""

import sys
import os

# Thêm thư mục gốc dự án vào sys.path để import được app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Cấu hình tài khoản admin ──────────────────────────────────
ADMIN_EMAIL = "admin123@gmail.com"
ADMIN_PASSWORD = "admin@123"
ADMIN_NAME = "Super Admin"
# ─────────────────────────────────────────────────────────────


def main():
    print("=" * 55)
    print("  GUA MAISON — Tạo tài khoản Admin")
    print("=" * 55)

    try:
        from app.utils.supabase_client import get_supabase
        from app.utils.security import hash_password
    except ImportError as e:
        print(f"\n[LỖI] Không import được module: {e}")
        print("→ Hãy chắc chắn chạy script từ thư mục gốc dự án.")
        sys.exit(1)

    db = get_supabase()

    # ── 1. Kiểm tra email đã tồn tại chưa ────────────────────
    print(f"\n[1/4] Kiểm tra email '{ADMIN_EMAIL}'...")
    existing = db.table("users").select("id, email").eq("email", ADMIN_EMAIL).limit(1).execute()

    if existing.data:
        user_id = existing.data[0]["id"]
        print(f"      → Email đã tồn tại (id={user_id})")
        print(f"        Bỏ qua bước tạo user, tiếp tục gán quyền...")
    else:
        # ── 2. Tạo user mới ───────────────────────────────────
        print(f"[2/4] Tạo user mới...")
        hashed = hash_password(ADMIN_PASSWORD)
        user_res = db.table("users").insert({
            "email": ADMIN_EMAIL,
            "password_hash": hashed,
            "full_name": ADMIN_NAME,
        }).execute()

        if not user_res.data:
            print("[LỖI] Không tạo được user. Kiểm tra lại Supabase.")
            sys.exit(1)

        user_id = user_res.data[0]["id"]
        print(f"      → Đã tạo user: id={user_id}")

    # ── 3. Tìm role_id của 'admin' ────────────────────────────
    print(f"[3/4] Tìm role 'admin' trong bảng roles...")
    role_res = db.table("roles").select("id, name").eq("name", "admin").limit(1).execute()

    if not role_res.data:
        print("\n[LỖI] Không tìm thấy role 'admin' trong bảng roles!")
        print("→ Hãy chạy SQL sau trong Supabase SQL Editor trước:\n")
        print("   INSERT INTO roles (name, description, is_active)")
        print("   VALUES ('admin', 'Quản trị viên hệ thống', true);")
        print("\nSau đó chạy lại script này.")
        sys.exit(1)

    role_id = role_res.data[0]["id"]
    print(f"      → Tìm thấy role 'admin' với id={role_id}")

    # ── 4. Gán quyền admin cho user ───────────────────────────
    print(f"[4/4] Gán quyền admin cho user...")

    # Kiểm tra đã có bản ghi user_roles chưa (tránh lỗi duplicate key)
    ur_existing = (
        db.table("user_roles")
        .select("user_id, role_id")
        .eq("user_id", user_id)
        .eq("role_id", role_id)
        .execute()
    )

    if ur_existing.data:
        print(f"      → Quyền admin đã được gán trước đó, bỏ qua.")
    else:
        db.table("user_roles").insert({
            "user_id": user_id,
            "role_id": role_id,
        }).execute()
        print(f"      → Đã gán quyền admin thành công!")

    # ── Kết quả ───────────────────────────────────────────────
    print("\n" + "=" * 55)
    print("  ✅ HOÀN TẤT")
    print("=" * 55)
    print(f"  Email    : {ADMIN_EMAIL}")
    print(f"  Mật khẩu : {ADMIN_PASSWORD}")
    print(f"  Role     : admin (id={role_id})")
    print(f"  User ID  : {user_id}")
    print("=" * 55)
    print("\n⚠️  Hãy XÓA file create_admin.py sau khi dùng xong!\n")


if __name__ == "__main__":
    main()
