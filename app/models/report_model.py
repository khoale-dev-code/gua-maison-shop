"""
app/models/report_model.py
Xử lý dữ liệu Báo cáo & Thống kê Omnichannel bằng Pandas.
"""
import pandas as pd
import logging
from app.utils.supabase_client import get_supabase

logger = logging.getLogger(__name__)


class ReportModel:

    @staticmethod
    def get_dashboard_reports() -> dict:
        db = get_supabase()
        try:
            # ── Kéo dữ liệu từ các bảng cần thiết ──
            analytics_res = (
                db.table("product_analytics")
                .select("*, products(name)")
                .execute()
            )
            orders_res = (
                db.table("orders")
                .select("id, total_amount, sales_channel, created_at, status, payment_status")
                .execute()
            )
            # Kéo order_items để tính số lượng bán thực tế theo sản phẩm
            order_items_res = (
                db.table("order_items")
                .select("order_id, product_id, quantity, unit_price, products(name)")
                .execute()
            )

            df_ana = pd.DataFrame(analytics_res.data or [])
            df_ord = pd.DataFrame(orders_res.data or [])
            df_items = pd.DataFrame(order_items_res.data or [])

            if df_ana.empty and df_ord.empty:
                return ReportModel._get_fallback_data()

            channel_revenue = {}
            monthly_stats = []
            funnel_data = []
            best_production = []
            most_liked = []

            # ── BƯỚC 1: Lọc đơn hợp lệ (completed/delivered + paid) ──
            valid_order_ids = set()
            if not df_ord.empty:
                is_delivered = df_ord["status"].isin(["delivered", "completed"])
                is_paid = df_ord["payment_status"] == "paid"
                df_valid = df_ord[is_delivered | is_paid].copy()

                if not df_valid.empty:
                    valid_order_ids = set(df_valid["id"].tolist())

                    df_valid["sales_channel"] = df_valid["sales_channel"].fillna("web")

                    # Doanh thu theo kênh
                    channel_revenue = (
                        df_valid.groupby("sales_channel")["total_amount"]
                        .sum()
                        .to_dict()
                    )

                    # Doanh thu theo tháng (12 tháng gần nhất)
                    if "created_at" in df_valid.columns:
                        df_valid["created_at"] = pd.to_datetime(df_valid["created_at"])
                        df_valid["month"] = df_valid["created_at"].dt.strftime("%m/%Y")
                        monthly = (
                            df_valid.groupby("month")["total_amount"]
                            .sum()
                            .reset_index()
                        )
                        monthly = monthly.sort_values("month").tail(12)
                        monthly.rename(columns={"total_amount": "revenue"}, inplace=True)
                        monthly_stats = monthly.to_dict("records")

            # ── BƯỚC 2: Tính số lượng bán thực tế từ order_items (chỉ đơn hợp lệ) ──
            # Đây là nguồn sự thật cho "sold" — đặc biệt quan trọng với kênh POS
            sold_by_product = {}
            if not df_items.empty and valid_order_ids:
                df_valid_items = df_items[df_items["order_id"].isin(valid_order_ids)].copy()
                if not df_valid_items.empty:
                    sold_by_product = (
                        df_valid_items.groupby("product_id")["quantity"]
                        .sum()
                        .to_dict()
                    )

            # ── BƯỚC 3: Funnel & AI Score từ product_analytics ──
            if not df_ana.empty:
                df_ana["product_name"] = df_ana["products"].apply(
                    lambda x: x.get("name") if isinstance(x, dict) else "Unknown"
                )

                # Ghi đè cột "sold" trong analytics bằng số liệu thực từ order_items
                # để đảm bảo dữ liệu nhất quán giữa POS và các kênh online
                if sold_by_product:
                    df_ana["sold_actual"] = df_ana["product_id"].map(sold_by_product).fillna(0)
                    # Lấy MAX giữa sold trong analytics (tracking online) và sold_actual (đơn thực)
                    # vì một số kênh (shopee, tiktok) tự tracking, không qua order_items
                    df_ana["sold"] = df_ana[["sold", "sold_actual"]].max(axis=1)

                # Phễu chuyển đổi theo kênh
                funnel_df = (
                    df_ana.groupby("channel")[["views", "add_to_carts", "sold"]]
                    .sum()
                    .reset_index()
                )
                funnel_df["cr_view_to_cart"] = (
                    funnel_df["add_to_carts"] / funnel_df["views"].replace(0, 1) * 100
                ).round(1)
                funnel_df["cr_cart_to_order"] = (
                    funnel_df["sold"] / funnel_df["add_to_carts"].replace(0, 1) * 100
                ).round(1)
                funnel_df["cr_total"] = (
                    funnel_df["sold"] / funnel_df["views"].replace(0, 1) * 100
                ).round(1)
                funnel_data = funnel_df.to_dict("records")

                # AI Score = (sold x 0.5) + (wishlist x 0.3) + (views x 0.2)
                df_ana["ai_score"] = (
                    df_ana["sold"] * 0.5
                    +df_ana["wishlist_count"] * 0.3
                    +df_ana["views"] * 0.2
                )
                idx = df_ana.groupby("channel")["ai_score"].idxmax()
                best_production = (
                    df_ana.loc[idx, ["channel", "product_name", "ai_score", "sold", "views"]]
                    .to_dict("records")
                )

                top_liked_df = (
                    df_ana.groupby("product_name")["wishlist_count"]
                    .sum()
                    .nlargest(5)
                    .reset_index()
                )
                top_liked_df.columns = ["product_name", "likes"]
                most_liked = top_liked_df[top_liked_df["likes"] > 0].to_dict("records")

            # ── BƯỚC 4: Nếu analytics rỗng nhưng có order_items, tổng hợp sold từ đó ──
            elif sold_by_product and not df_items.empty and valid_order_ids:
                df_valid_items = df_items[df_items["order_id"].isin(valid_order_ids)].copy()
                df_valid_items["product_name"] = df_valid_items["products"].apply(
                    lambda x: x.get("name") if isinstance(x, dict) else "Unknown"
                )
                # Merge với channel từ orders
                df_ord_channel = df_ord[["id", "sales_channel"]].rename(columns={"id": "order_id"})
                df_valid_items = df_valid_items.merge(df_ord_channel, on="order_id", how="left")
                df_valid_items["sales_channel"] = df_valid_items["sales_channel"].fillna("pos")

                funnel_df = (
                    df_valid_items.groupby("sales_channel")
                    .agg(sold=("quantity", "sum"), views=("quantity", "count"), add_to_carts=("quantity", "sum"))
                    .reset_index()
                    .rename(columns={"sales_channel": "channel"})
                )
                funnel_df["cr_view_to_cart"] = 100.0
                funnel_df["cr_cart_to_order"] = 100.0
                funnel_df["cr_total"] = 100.0
                funnel_data = funnel_df.to_dict("records")

            return {
                "channel_revenue": channel_revenue,
                "monthly_stats": monthly_stats,
                "funnel": funnel_data,
                "production_suggestions": best_production,
                "most_liked": most_liked,
            }

        except Exception as e:
            logger.error(f"[ReportModel] Lỗi xử lý Pandas: {e}", exc_info=True)
            return ReportModel._get_fallback_data()

    @staticmethod
    def _get_fallback_data():
        return {
            "channel_revenue": {"web": 0, "pos": 0, "tiktok": 0},
            "monthly_stats": [],
            "funnel": [],
            "production_suggestions": [],
            "most_liked": [],
        }
