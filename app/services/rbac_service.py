import json
import logging
# import redis (Khuyến nghị dùng Redis cho Production)
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# Giả lập Redis Cache (Trong thực tế hãy dùng Redis)
_pseudo_redis_cache = {}


class RBACService:
    CACHE_PREFIX = "user_perms:"
    CACHE_TTL = 3600  # Cache sống 1 tiếng

    @staticmethod
    def get_user_permissions(user_id: str, tenant_id: str) -> set:
        """
        Lấy danh sách quyền của User. CÓ SỬ DỤNG CACHE LAYER.
        Bao gồm: Quyền từ Role + Quyền cấp trực tiếp (Direct) - Quyền bị cấm (Blacklist)
        """
        cache_key = f"{RBACService.CACHE_PREFIX}{tenant_id}:{user_id}"
        
        # 1. Đọc từ Cache (Performance Fix)
        if cache_key in _pseudo_redis_cache:
            return _pseudo_redis_cache[cache_key]

        db = get_supabase()
        permissions = set()

        try:
            # 2. Lấy quyền từ Roles (Bỏ qua các Role bị Soft Delete/Inactive)
            # Truy vấn này yêu cầu viết RPC (Hàm SQL) trên Supabase hoặc join nhiều bảng
            roles_res = db.table("user_roles").select("role_id, roles!inner(is_active, deleted_at, role_permissions(permissions(code)))").eq("user_id", user_id).eq("tenant_id", tenant_id).execute()
            
            for ur in roles_res.data:
                role = ur.get("roles", {})
                if role.get("is_active") and not role.get("deleted_at"):
                    for rp in role.get("role_permissions", []):
                        permissions.add(rp["permissions"]["code"])

            # 3. Xử lý Direct Permissions (Ngoại lệ)
            direct_res = db.table("user_permissions").select("is_granted, permissions(code)").eq("user_id", user_id).execute()
            
            for dp in direct_res.data:
                perm_code = dp["permissions"]["code"]
                if dp["is_granted"]:
                    permissions.add(perm_code)  # Cấp thêm
                else:
                    permissions.discard(perm_code)  # Blacklist (Cấm quyền này dù Role có)

            # 4. Lưu vào Cache
            _pseudo_redis_cache[cache_key] = permissions
            return permissions

        except Exception as e:
            logger.error(f"Lỗi lấy quyền user {user_id}: {e}")
            return set()

    @staticmethod
    def invalidate_cache(user_id: str, tenant_id: str):
        """Gọi hàm này khi Admin thay đổi quyền của User trên UI"""
        cache_key = f"{RBACService.CACHE_PREFIX}{tenant_id}:{user_id}"
        _pseudo_redis_cache.pop(cache_key, None)
