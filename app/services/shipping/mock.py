from .base import BaseShippingProvider
import random


class MockShippingProvider(BaseShippingProvider):

    def calculate_fee(self, payload: dict) -> dict:
        fee = random.choice([25000, 30000, 35000])
        return {
            "success": True,
            "fee": fee,
            "estimated_days": 2,
            "raw_response": {
                "message": "Mock Provider calculated successfully",
                "data": {"calculated_fee": fee, "service_type": "standard"}
            }
        }

    def create_order(self, order_data: dict) -> dict:
        tracking = f"MOCK-{random.randint(100000, 999999)}"
        return {
            "success": True,
            "tracking_code": tracking,
            "raw_response": {
                "message": "Mock Order Created",
                "tracking_number": tracking,
                "status": "Ready to pick"
            }
        }
