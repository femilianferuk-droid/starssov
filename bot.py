import asyncio
import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, ReplyKeyboardRemove
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import Config
from database import Database

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Проверяем настройки
Config.validate()

# Инициализация бота и БД
bot = Bot(token=Config.BOT_TOKEN)
dp = Dispatcher()
db = Database()

# Состояния для FSM
class WithdrawState(StatesGroup):
    choosing_amount = State()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def format_balance(balance: float) -> str:
    """Форматирование баланса"""
    return f"{balance:.2f}"

def format_time(seconds: int) -> str:
    """Форматирование времени"""
    if seconds < 60:
        return f"{seconds} сек"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes} мин {secs} сек"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours} ч {minutes} мин"

async def check_subscriptions(user_id: int) -> bool:
    """Проверить подписки пользователя на спонсоров"""
    try:
        sponsors_status = db.get_user_sponsors_status(user_id)
        if not sponsors_status:  # Если нет спонсоров
            return True
        
        for sponsor in sponsors_status:
            if not sponsor.get('is_subscribed', False):
                return False
        return True
    except Exception as e:
        logger.error(f"Error checking subscriptions for {user_id}: {e}")
        return False

def create_main_menu() -> InlineKeyboardMarkup:
    """Создать главное меню"""
    keyboard = [
        [InlineKeyboardButton(text="🐵 Заработать звезды", callback_data="earn")],
        [InlineKeyboardButton(text="📊 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="👥 Реферальная система", callback_data="referral")],
        [InlineKeyboardButton(text="🎮 Игры (Перейти на сайт)", url="https://ваш-сайт.vercel.app")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ========== ОБРАБОТЧИКИ КОМАНД ==========

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    logger.info(f"User {user_id} ({username}) started bot")
    
    # Обработка реферальной ссылки
    referrer_id = None
    if len(message.text.split()) > 1:
        try:
            referrer_id = int(message.text.split()[1])
            if referrer_id == user_id:  # Нельзя самому себя пригласить
                referrer_id = None
        except ValueError:
            referrer_id = None
    
    # Создаем/обновляем пользователя
    db.create_user(user_id, username, referrer_id)
    
    # Проверяем подписки
    if not await check_subscriptions(user_id):
        await show_sponsors_message(message, user_id)
        return
    
    # Показываем главное меню
    await show_main_menu(message)

async def show_sponsors_message(message: Message, user_id: int):
    """Показать сообщение о необходимости подписки"""
    sponsors = db.get_sponsors()
    
    if not sponsors:
        await show_main_menu(message)
        return
    
    keyboard = []
    for sponsor in sponsors:
        keyboard.append([
            InlineKeyboardButton(
                text=f"📢 {sponsor.get('channel_username', 'Канал')}",
                url=sponsor.get('channel_url', 'https://t.me')
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(
            text="✅ Я подписался",
            callback_data="check_subscriptions"
        )
    ])
    
    await message.answer(
        "📢 *Чтобы начать, подпишитесь на наших спонсоров!*\n\n"
        "После подписки нажмите кнопку ниже:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

async def show_main_menu(message: Message, text: str = None):
    """Показать главное меню"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    balance = user['balance'] if user else 0.0
    
    welcome_text = text or (
        "🐵 *Monkey Stars*\n\n"
        f"💰 Баланс: *{format_balance(balance)} STAR*\n\n"
        "Выберите действие:"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=create_main_menu(),
        parse_mode="Markdown"
    )

# ========== CALLBACK ОБРАБОТЧИКИ ==========

@dp.callback_query(F.data == "check_subscriptions")
async def handle_check_subscriptions(callback: CallbackQuery):
    """Проверка подписок после нажатия кнопки"""
    user_id = callback.from_user.id
    
    # Здесь должна быть реальная проверка через getChatMember
    # Пока что имитируем успешную подписку
    sponsors = db.get_sponsors()
    for sponsor in sponsors:
        db.update_user_sponsor_status(user_id, sponsor['id'], True)
    
    await callback.answer("✅ Отлично! Доступ открыт!")
    await callback.message.delete()
    await show_main_menu(callback.message)

@dp.callback_query(F.data == "earn")
async def handle_earn(callback: CallbackQuery):
    """Меню заработка"""
    user_id = callback.from_user.id
    
    if not await check_subscriptions(user_id):
        await callback.answer("❌ Сначала подпишитесь на спонсоров!", show_alert=True)
        await show_sponsors_message(callback.message, user_id)
        return
    
    keyboard = [
        [InlineKeyboardButton(text="🎯 Кликнуть (+0.2 STAR)", callback_data="click")],
        [InlineKeyboardButton(text="💸 Вывод средств", callback_data="withdraw_menu")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ]
    
    await callback.message.edit_text(
        "🐵 *Заработать звезды*\n\n"
        "Выберите способ заработка:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "click")
async def handle_click(callback: CallbackQuery):
    """Обработка кликера"""
    user_id = callback.from_user.id
    
    if not await check_subscriptions(user_id):
        await callback.answer("❌ Сначала подпишитесь на спонсоров!", show_alert=True)
        return
    
    user = db.get_user(user_id)
    if not user:
        await callback.answer("❌ Ошибка, попробуйте /start")
        return
    
    current_time = int(datetime.now().timestamp())
    last_click = user.get('last_click')
    
    # Проверка кулдауна
    if last_click and (current_time - last_click) < Config.CLICK_COOLDOWN:
        remaining = Config.CLICK_COOLDOWN - (current_time - last_click)
        await callback.answer(f"⏳ Подождите {format_time(remaining)}")
        return
    
    # Начисление клика
    reward = Config.CLICK_REWARD
    db.update_balance(user_id, reward)
    db.update_last_click(user_id, current_time)
    db.add_transaction(user_id, reward, "click", "Кликер")
    
    # Реферальный бонус (10%)
    referrer_id = user.get('referrer_id')
    if referrer_id:
        referral_bonus = reward * (Config.CLICK_REFERRAL_PERCENT / 100)
        db.update_balance(referrer_id, referral_bonus)
        db.add_transaction(
            referrer_id,
            referral_bonus,
            "referral_income",
            f"10% от клика пользователя {callback.from_user.username or user_id}"
        )
    
    # Обновляем сообщение
    user = db.get_user(user_id)
    await callback.message.edit_text(
        f"✅ *Вы получили {reward} STAR!*\n\n"
        f"💰 Баланс: *{format_balance(user['balance'])} STAR*\n\n"
        f"⏰ Следующий клик через 1 час",
        parse_mode="Markdown",
        reply_markup=callback.message.reply_markup
    )
    
    await callback.answer(f"+{reward} STAR")

@dp.callback_query(F.data == "withdraw_menu")
async def handle_withdraw_menu(callback: CallbackQuery, state: FSMContext):
    """Меню вывода средств"""
    user_id = callback.from_user.id
    
    if not await check_subscriptions(user_id):
        await callback.answer("❌ Сначала подпишитесь на спонсоров!", show_alert=True)
        return
    
    keyboard = []
    for amount in Config.WITHDRAWAL_AMOUNTS:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{amount} STAR",
                callback_data=f"withdraw_{amount}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="earn")])
    
    await callback.message.edit_text(
        "💸 *Вывод средств*\n\n"
        "Выберите сумму для вывода:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("withdraw_"))
async def handle_withdraw(callback: CallbackQuery, state: FSMContext):
    """Обработка вывода"""
    user_id = callback.from_user.id
    
    try:
        amount = float(callback.data.split("_")[1])
    except:
        await callback.answer("❌ Ошибка суммы")
        return
    
    user = db.get_user(user_id)
    if not user:
        await callback.answer("❌ Ошибка, попробуйте /start")
        return
    
    # Проверка баланса
    if user['balance'] < amount:
        await callback.answer(f"❌ Недостаточно STAR. Ваш баланс: {format_balance(user['balance'])}")
        return
    
    # Проверка активных рефералов
    total_ref, active_ref = db.get_user_referrals(user_id)
    if active_ref < 3:
        await callback.answer(f"❌ Нужно 3 активных реферала. У вас: {active_ref}")
        return
    
    # Создание заявки на вывод
    withdrawal = db.create_withdrawal(user_id, amount)
    if not withdrawal:
        await callback.answer("❌ Ошибка при создании заявки")
        return
    
    # Списание баланса
    db.update_balance(user_id, -amount)
    db.add_transaction(user_id, -amount, "withdrawal", f"Вывод #{withdrawal['id']}")
    
    # Отправляем сообщение об успехе
    await callback.message.edit_text(
        f"✅ *Заявка на вывод одобрена!*\n\n"
        f"💰 Сумма: *{amount} STAR*\n"
        f"📝 ID заявки: *#{withdrawal['id']}*\n\n"
        f"Для получения средств свяжитесь с поддержкой: @MonkeyStarsov\n"
        f"Укажите ваш ID: `{user_id}` и сумму: `{amount} STAR`",
        parse_mode="Markdown"
    )
    
    # Уведомляем админа
    try:
        await bot.send_message(
            Config.ADMIN_ID,
            f"📥 Новая заявка на вывод!\n"
            f"👤 Пользователь: @{callback.from_user.username or user_id}\n"
            f"💰 Сумма: {amount} STAR\n"
            f"📝 ID: {withdrawal['id']}\n"
            f"🆔 User ID: {user_id}"
        )
    except:
        pass

@dp.callback_query(F.data == "profile")
async def handle_profile(callback: CallbackQuery):
    """Профиль пользователя"""
    user_id = callback.from_user.id
    
    if not await check_subscriptions(user_id):
        await callback.answer("❌ Сначала подпишитесь на спонсоров!", show_alert=True)
        return
    
    user = db.get_user(user_id)
    if not user:
        await callback.answer("❌ Ошибка, попробуйте /start")
        return
    
    total_ref, active_ref = db.get_user_referrals(user_id)
    
    # Время до следующего клика
    last_click = user.get('last_click')
    current_time = int(datetime.now().timestamp())
    
    if last_click:
        time_passed = current_time - last_click
        if time_passed < Config.CLICK_COOLDOWN:
            remaining = Config.CLICK_COOLDOWN - time_passed
            next_click = f"через {format_time(remaining)}"
        else:
            next_click = "сейчас"
    else:
        next_click = "сейчас"
    
    text = (
        f"📊 *Профиль*\n\n"
        f"👤 ID: `{user_id}`\n"
        f"👤 Имя: {callback.from_user.full_name}\n"
        f"💰 Баланс: *{format_balance(user['balance'])} STAR*\n"
        f"👥 Рефералов: *{active_ref}* / {total_ref}\n"
        f"⏰ Кликер доступен: {next_click}"
    )
    
    keyboard = [[InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]]
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "referral")
async def handle_referral(callback: CallbackQuery):
    """Реферальная система"""
    user_id = callback.from_user.id
    
    if not await check_subscriptions(user_id):
        await callback.answer("❌ Сначала подпишитесь на спонсоров!", show_alert=True)
        return
    
    total_ref, active_ref = db.get_user_referrals(user_id)
    
    text = (
        f"👥 *Реферальная система*\n\n"
        f"🔗 Ваша реферальная ссылка:\n"
        f"`https://t.me/MonkeyStarsBot?start={user_id}`\n\n"
        f"📊 Статистика:\n"
        f"• Приглашено: *{total_ref}*\n"
        f"• Активных: *{active_ref}*\n\n"
        f"🎁 *Правила:*\n"
        f"• Вы получаете *3 STAR*, а друг *2 STAR* после подписки на спонсоров\n"
        f"• Вы получаете *10%* от всех кликов реферала\n"
        f"• Для вывода нужно *3 активных реферала*"
    )
    
    keyboard = [[InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]]
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "main_menu")
async def handle_back_to_main(callback: CallbackQuery):
    """Возврат в главное меню"""
    await callback.message.delete()
    await show_main_menu(callback.message)

# ========== АДМИН КОМАНДЫ ==========

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    """Админ панель"""
    if message.from_user.id != Config.ADMIN_ID:
        await message.answer("❌ Доступ запрещен")
        return
    
    stats = db.get_stats()
    
    text = (
        f"👑 *Админ панель*\n\n"
        f"📊 Статистика:\n"
        f"• Пользователей: {stats['total_users']}\n"
        f"• Общий баланс: {format_balance(stats['total_balance'])} STAR\n"
        f"• Заявок на вывод: {stats['pending_withdrawals']}\n\n"
        f"Доступные команды:\n"
        f"/stats - Полная статистика\n"
        f"/users - Список пользователей\n"
        f"/sponsors - Управление спонсорами\n"
        f"/broadcast - Рассылка сообщений"
    )
    
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    """Детальная статистика"""
    if message.from_user.id != Config.ADMIN_ID:
        return
    
    stats = db.get_stats()
    
    # Дополнительная статистика
    users = db.get_all_users()
    top_users = sorted(users, key=lambda x: x['balance'], reverse=True)[:10]
    
    top_text = "🏆 Топ-10 по балансу:\n"
    for i, user in enumerate(top_users, 1):
        top_text += f"{i}. @{user['username']}: {format_balance(user['balance'])} STAR\n"
    
    text = (
        f"📈 *Детальная статистика*\n\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"💰 Общий баланс: {format_balance(stats['total_balance'])} STAR\n"
        f"📥 Заявок на вывод: {stats['pending_withdrawals']}\n\n"
        f"{top_text}"
    )
    
    await message.answer(text, parse_mode="Markdown")

# ========== ЗАПУСК БОТА ==========

async def main():
    """Основная функция запуска"""
    logger.info("🚀 Запуск бота Monkey Stars...")
    
    try:
        # Проверяем подключение к БД
        stats = db.get_stats()
        logger.info(f"✅ База данных подключена. Пользователей: {stats['total_users']}")
        
        # Запускаем бота
        logger.info("✅ Бот успешно запущен!")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
