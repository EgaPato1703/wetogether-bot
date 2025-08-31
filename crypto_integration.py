import aiohttp
import asyncio
import json
from typing import Optional, Dict, Any
from database import get_db

class CryptoBotIntegration:
    def __init__(self, crypto_bot_token: str):
        self.token = crypto_bot_token
        self.base_url = "https://pay.crypt.bot/api"
        
    async def create_invoice(self, amount: float, user_id: int, description: str = "Payment") -> Optional[Dict[str, Any]]:
        """Создает счет в CryptoBot"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "amount": str(amount),
                    "currency": "USD",
                    "asset": "USDT",
                    "description": description,
                    "paid_btn_name": "callback",
                    "paid_btn_url": f"https://t.me/WetogetherBot?start=paid_{user_id}_{amount}",
                    "payload": f"user_{user_id}_amount_{amount}"
                }
                
                headers = {
                    "Crypto-Pay-API-Token": self.token,
                    "Content-Type": "application/json"
                }
                
                async with session.post(f"{self.base_url}/createInvoice", json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("ok"):
                            return data.get("result")
                    return None
        except Exception as e:
            print(f"Ошибка создания счета: {e}")
            return None
    
    async def check_invoice_status(self, invoice_id: str) -> Optional[str]:
        """Проверяет статус счета"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Crypto-Pay-API-Token": self.token
                }
                
                async with session.get(f"{self.base_url}/getInvoices?invoice_ids={invoice_id}", headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"Ответ от API проверки статуса: {data}")
                        
                        if data.get("ok") and data.get("result"):
                            # Проверяем разные форматы ответа
                            result = data["result"]
                            
                            # Формат 1: result.items (как в тесте)
                            if "items" in result and len(result["items"]) > 0:
                                invoice = result["items"][0]
                                status = invoice.get("status")
                                print(f"Статус счета {invoice_id}: {status}")
                                return status
                            
                            # Формат 2: result как массив
                            elif isinstance(result, list) and len(result) > 0:
                                invoice = result[0]
                                status = invoice.get("status")
                                print(f"Статус счета {invoice_id}: {status}")
                                return status
                            
                            # Формат 3: result как объект
                            elif isinstance(result, dict) and "status" in result:
                                status = result.get("status")
                                print(f"Статус счета {invoice_id}: {status}")
                                return status
                            
                            else:
                                print(f"Неизвестный формат ответа для счета {invoice_id}")
                                return None
                        else:
                            print(f"Нет данных о счете {invoice_id}")
                            return None
                    else:
                        print(f"HTTP ошибка при проверке статуса: {response.status}")
                        return None
        except Exception as e:
            print(f"Ошибка проверки статуса: {e}")
            return None
    
    async def get_invoice_url(self, invoice_id: str) -> str:
        """Возвращает URL для оплаты счета"""
        return f"https://t.me/CryptoBot?start=invoice_{invoice_id}"

# Создаем экземпляр интеграции
crypto_integration = CryptoBotIntegration("447765:AAASEFBfCAs2IZLVxfIDYoxHhGS0ZFZ1Ql3")
