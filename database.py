from supabase import create_client, Client
from datetime import datetime
from config import Config
import logging
from typing import Optional, Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        try:
            logger.info("🔄 Подключаемся к Supabase...")
            self.supabase: Client = create_client(
                Config.SUPABASE_URL,
                Config.SUPABASE_KEY
            )
            logger.info("✅ Подключение к Supabase успешно")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Supabase: {e}")
            raise
    
    # === ПОЛЬЗОВАТЕЛИ ===
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Получить пользователя по ID"""
        try:
            response = self.supabase.table("users")\
                .select("*")\
                .eq("user_id", user_id)\
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Ошибка получения пользователя {user_id}: {e}")
            return None
    
    def create_user(self, user_id: int, username: str, referrer_id: int = None) -> bool:
        """Создать нового пользователя"""
        try:
            user_data = {
                "user_id": user_id,
                "username": username or f"user_{user_id}",
                "referrer_id": referrer_id,
                "created_at": int(datetime.now().timestamp()),
                "balance": 0.0,
                "last_click": None
            }
            
            response = self.supabase.table("users")\
                .upsert(user_data, on_conflict="user_id")\
                .execute()
            
            return bool(response.data)
        except Exception as e:
            logger.error(f"Ошибка создания пользователя {user_id}: {e}")
            return False
    
    def update_balance(self, user_id: int, amount: float) -> bool:
        """Обновить баланс пользователя"""
        try:
            user = self.get_user(user_id)
            if not user:
                return False
            
            new_balance = user["balance"] + amount
            
            response = self.supabase.table("users")\
                .update({"balance": new_balance})\
                .eq("user_id", user_id)\
                .execute()
            
            return bool(response.data)
        except Exception as e:
            logger.error(f"Ошибка обновления баланса {user_id}: {e}")
            return False
    
    def update_last_click(self, user_id: int, timestamp: int) -> bool:
        """Обновить время последнего клика"""
        try:
            response = self.supabase.table("users")\
                .update({"last_click": timestamp})\
                .eq("user_id", user_id)\
                .execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Ошибка обновления last_click {user_id}: {e}")
            return False
    
    # === СПОНСОРЫ ===
    def get_sponsors(self) -> List[Dict]:
        """Получить всех спонсоров"""
        try:
            response = self.supabase.table("sponsors")\
                .select("*")\
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"Ошибка получения спонсоров: {e}")
            return []
    
    def update_user_sponsor_status(self, user_id: int, sponsor_id: int, is_subscribed: bool) -> bool:
        """Обновить статус подписки пользователя на спонсора"""
        try:
            response = self.supabase.table("user_sponsors")\
                .upsert({
                    "user_id": user_id,
                    "sponsor_id": sponsor_id,
                    "is_subscribed": is_subscribed,
                    "last_check": int(datetime.now().timestamp())
                }, on_conflict="user_id,sponsor_id")\
                .execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Ошибка обновления статуса подписки: {e}")
            return False
    
    def get_user_sponsors_status(self, user_id: int) -> List[Dict]:
        """Получить статус подписок пользователя"""
        try:
            response = self.supabase.rpc(
                'get_user_sponsors_status',
                {'p_user_id': user_id}
            ).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Ошибка получения статуса подписок {user_id}: {e}")
            return []
    
    # === РЕФЕРАЛЫ ===
    def get_user_referrals(self, user_id: int) -> tuple:
        """Получить статистику рефералов"""
        try:
            # Все рефералы
            response = self.supabase.table("users")\
                .select("user_id")\
                .eq("referrer_id", user_id)\
                .execute()
            total = len(response.data) if response.data else 0
            
            # Активные рефералы
            active_response = self.supabase.rpc(
                'get_active_referrals',
                {'p_user_id': user_id}
            ).execute()
            active = len(active_response.data) if active_response.data else 0
            
            return total, active
        except Exception as e:
            logger.error(f"Ошибка получения рефералов {user_id}: {e}")
            return 0, 0
    
    # === ТРАНЗАКЦИИ ===
    def add_transaction(self, user_id: int, amount: float, type: str, description: str = "") -> bool:
        """Добавить транзакцию"""
        try:
            response = self.supabase.table("transactions")\
                .insert({
                    "user_id": user_id,
                    "amount": amount,
                    "type": type,
                    "description": description,
                    "created_at": int(datetime.now().timestamp())
                })\
                .execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Ошибка добавления транзакции: {e}")
            return False
    
    # === ВЫВОД СРЕДСТВ ===
    def create_withdrawal(self, user_id: int, amount: float) -> Optional[Dict]:
        """Создать заявку на вывод"""
        try:
            response = self.supabase.table("withdrawals")\
                .insert({
                    "user_id": user_id,
                    "amount": amount,
                    "status": "pending",
                    "created_at": int(datetime.now().timestamp())
                })\
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Ошибка создания вывода: {e}")
            return None
    
    # === АДМИН ФУНКЦИИ ===
    def get_all_users(self) -> List[Dict]:
        """Получить всех пользователей (админ)"""
        try:
            response = self.supabase.table("users")\
                .select("*")\
                .order("created_at", desc=True)\
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"Ошибка получения всех пользователей: {e}")
            return []
    
    def get_stats(self) -> Dict:
        """Получить статистику (админ)"""
        try:
            # Количество пользователей
            users_resp = self.supabase.table("users")\
                .select("user_id", count="exact")\
                .execute()
            
            # Общий баланс
            balance_resp = self.supabase.table("users")\
                .select("balance")\
                .execute()
            total_balance = sum(user['balance'] for user in balance_resp.data) if balance_resp.data else 0
            
            # Заявки на вывод
            withdrawals_resp = self.supabase.table("withdrawals")\
                .select("id", count="exact")\
                .eq("status", "pending")\
                .execute()
            
            return {
                "total_users": users_resp.count or 0,
                "total_balance": total_balance,
                "pending_withdrawals": withdrawals_resp.count or 0
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {"total_users": 0, "total_balance": 0, "pending_withdrawals": 0}
