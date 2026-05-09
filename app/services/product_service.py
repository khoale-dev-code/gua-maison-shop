from app.models.product_model import ProductModel


class ProductService:

    @staticmethod
    def get_catalog(page, per_page, keyword=None, category=None):
        """Logic tập trung để lấy danh sách sản phẩm."""
        if keyword:
            search_method = getattr(ProductModel, "search", None)
            if callable(search_method):
                return search_method(keyword, page=page, per_page=per_page)

            return ProductModel.get_all(keyword=keyword, page=page, category=category, per_page=per_page)
        
        return ProductModel.get_all(page=page, category=category, per_page=per_page)

    @staticmethod
    def get_product_detail(product_id):
        """Lấy chi tiết sản phẩm."""
        return ProductModel.get_by_id(product_id)
