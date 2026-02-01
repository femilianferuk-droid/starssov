import os

class Config:
    # Обязательные настройки из переменных окружения
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # Опциональные настройки с значениями по умолчанию
    ADMIN_ID = int(os.getenv("ADMIN_ID", "7973988177"))
    
    # Supabase - прямо в коде
    SUPABASE_URL = "https://lzmvkp5wrkoms.hv.qb2usq.supabase.co"
    SUPABASE_KEY = "sb_publishable_lZmVKp5wrkoOMsHvQB2UsQ_jkmn1gul"
    
    # Настройки игры - прямо в коде
    CLICK_REWARD = 0.2
    CLICK_COOLDOWN = 3600  # 1 час в секундах
    REFERRAL_REWARD_REFERRER = 3.0
    REFERRAL_REWARD_REFEREE = 2.0
    CLICK_REFERRAL_PERCENT = 10  # 10% от клика реферала
    
    # Суммы для вывода
    WITHDRAWAL_AMOUNTS = [15, 25, 50, 100]
    
    # Проверка обязательных настроек
    @classmethod
    def validate(cls):
        if not cls.BOT_TOKEN:
            raise ValueError(
                "❌ BOT_TOKEN не найден!\n"
                "Установите переменную окружения:\n"
                "1. Создайте файл .env с BOT_TOKEN=ваш_токен\n"
                "2. Или установите в системе: export BOT_TOKEN=ваш_токен\n"
                "3. Получите токен у @BotFather"
            )
        return True
