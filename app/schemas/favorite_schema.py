from pydantic import BaseModel, Field


class FavoriteToggleRequest(BaseModel):
    # Ràng buộc product_id phải là chuỗi hợp lệ, không được rỗng
    product_id: str = Field(..., min_length=10, description="Mã ID của sản phẩm")


class FavoriteDTO(BaseModel):
    id: str
    user_id: str
    product_id: str
    # Có thể mở rộng thêm product_details ở đây
