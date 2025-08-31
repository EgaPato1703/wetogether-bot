import json
import random
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, List

class CouponSystem:
    def __init__(self, coupons_file: str = "data/coupons.json"):
        self.coupons_file = coupons_file
        self.coupons = self.load_coupons()
    
    def load_coupons(self) -> Dict:
        """Загружает купоны из файла"""
        try:
            with open(self.coupons_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def save_coupons(self):
        """Сохраняет купоны в файл"""
        import os
        os.makedirs(os.path.dirname(self.coupons_file), exist_ok=True)
        with open(self.coupons_file, 'w', encoding='utf-8') as f:
            json.dump(self.coupons, f, ensure_ascii=False, indent=2)
    
    def generate_coupon_code(self, length: int = 8) -> str:
        """Генерирует уникальный код купона"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
            if code not in self.coupons:
                return code
    
    def create_coupon(self, amount: float, days_valid: int, created_by: str) -> Dict:
        """Создает новый купон"""
        coupon_code = self.generate_coupon_code()
        expiry_date = datetime.now() + timedelta(days=days_valid)
        
        coupon = {
            "code": coupon_code,
            "amount": amount,
            "days_valid": days_valid,
            "created_at": datetime.now().isoformat(),
            "expires_at": expiry_date.isoformat(),
            "created_by": created_by,
            "is_used": False,
            "used_by": None,
            "used_at": None
        }
        
        self.coupons[coupon_code] = coupon
        self.save_coupons()
        return coupon
    
    def get_coupon(self, code: str) -> Optional[Dict]:
        """Получает купон по коду"""
        return self.coupons.get(code)
    
    def use_coupon(self, code: str, user_id: str) -> bool:
        """Использует купон"""
        if code not in self.coupons:
            return False
        
        coupon = self.coupons[code]
        
        # Проверяем срок действия
        expiry_date = datetime.fromisoformat(coupon["expires_at"])
        if datetime.now() > expiry_date:
            return False
        
        # Проверяем, не использован ли уже
        if coupon["is_used"]:
            return False
        
        # Помечаем как использованный
        coupon["is_used"] = True
        coupon["used_by"] = user_id
        coupon["used_at"] = datetime.now().isoformat()
        
        self.save_coupons()
        return True
    
    def get_active_coupons(self) -> List[Dict]:
        """Получает все активные купоны"""
        active = []
        for coupon in self.coupons.values():
            if not coupon["is_used"]:
                expiry_date = datetime.fromisoformat(coupon["expires_at"])
                if datetime.now() <= expiry_date:
                    active.append(coupon)
        return active
    
    def get_expired_coupons(self) -> List[Dict]:
        """Получает все истекшие купоны"""
        expired = []
        for coupon in self.coupons.values():
            expiry_date = datetime.fromisoformat(coupon["expires_at"])
            if datetime.now() > expiry_date:
                expired.append(coupon)
        return expired
    
    def get_user_coupons(self, user_id: str) -> List[Dict]:
        """Получает купоны, созданные пользователем"""
        user_coupons = []
        for coupon in self.coupons.values():
            if coupon["created_by"] == user_id:
                user_coupons.append(coupon)
        return user_coupons
    
    def delete_coupon(self, code: str, user_id: str) -> bool:
        """Удаляет купон (только создатель или админ)"""
        if code not in self.coupons:
            return False
        
        coupon = self.coupons[code]
        
        # Проверяем права на удаление
        if coupon["created_by"] != user_id:
            return False
        
        # Удаляем купон
        del self.coupons[code]
        self.save_coupons()
        return True




