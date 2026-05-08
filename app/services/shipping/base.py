from abc import ABC, abstractmethod

class BaseShippingProvider(ABC):
    """Unified Interface cho tất cả các hãng vận chuyển"""
    
    @abstractmethod
    def calculate_fee(self, payload: dict) -> dict:
        """Trả về: {'success': bool, 'fee': int, 'raw_response': dict}"""
        pass

    @abstractmethod
    def create_order(self, order_data: dict) -> dict:
        """Trả về: {'success': bool, 'tracking_code': str, 'raw_response': dict}"""
        pass