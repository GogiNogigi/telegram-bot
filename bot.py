import asyncio
import logging
import os
import sys
from datetime import datetime, time, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Add the parent directory to path so we can import Flask models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from utils import get_latest_news, format_news_message

# Initialize Flask app context to access models
try:
    from main import app, db, Subscriber, FeedSource, BotSettings, NewsItem, SendTime
    use_db = True
    
    # Function to get bot settings
    def get_bot_settings():
        """Get bot settings from database"""
        with app.app_context():
            settings = BotSettings.query.first()
            if not settings:
                settings = BotSettings()
                db.session.add(settings)
                db.session.commit()
            return settings
    
    # Function to check if bot is active
    def is_bot_active():
        """Check if bot is active based on settings"""
        with app.app_context():
            settings = BotSettings.query.first()
            if not settings:
                return True  # Default to active if no settings
            return settings.is_active
    
    # Function to get Telegram token
    def get_telegram_token():
        """Get Telegram token from database settings"""
        with app.app_context():
            settings = BotSettings.query.first()
            if settings and settings.telegram_token:
                return settings.telegram_token
            return config.API_TOKEN
    
    # Function to get news per source
    def get_news_per_source():
        """Get news per source setting"""
        with app.app_context():
            settings = BotSettings.query.first()
            if settings:
                return settings.news_per_source
            return config.NEWS_PER_FEED
    
    # Function to get daily send time
    def get_daily_send_time():
        """Get daily send time setting"""
        with app.app_context():
            settings = BotSettings.query.first()
            if settings and settings.daily_send_time:
                return settings.daily_send_time
            return time(8, 0)  # Default to 8:00 AM
            
    # Function to get all active send times
    def get_all_send_times():
        """Get all active send times from the database"""
        with app.app_context():
            # Get main send time
            settings = BotSettings.query.first()
            main_time = time(8, 0)  # Default
            if settings and settings.daily_send_time:
                main_time = settings.daily_send_time
                
            # Get additional send times
            additional_times = [st.send_time for st in SendTime.query.filter_by(is_active=True).all()]
            
            # Combine all times
            all_times = [main_time] + additional_times
            return all_times
    
    # Function to add subscriber using Flask models
    def add_subscriber(user_id, username=None, first_name=None, last_name=None):
        """Add a new subscriber using Flask SQLAlchemy model"""
        with app.app_context():
            # Check if subscriber exists
            existing = Subscriber.query.filter_by(user_id=user_id).first()
            if existing:
                if not existing.is_active:
                    existing.is_active = True
                    existing.username = username if username else existing.username
                    existing.first_name = first_name if first_name else existing.first_name
                    existing.last_name = last_name if last_name else existing.last_name
                    db.session.commit()
                    return True
                return False
            
            # Create new subscriber
            new_subscriber = Subscriber(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                is_active=True
            )
            db.session.add(new_subscriber)
            db.session.commit()
            return True
    
    # Function to remove subscriber
    def remove_subscriber(user_id):
        """Remove a subscriber using Flask SQLAlchemy model"""
        with app.app_context():
            subscriber = Subscriber.query.filter_by(user_id=user_id).first()
            if not subscriber:
                return False
            
            # Instead of deleting, mark as inactive
            subscriber.is_active = False
            db.session.commit()
            return True
    
    # Function to get all subscribers
    def get_all_subscribers():
        """Get all active subscribers using Flask SQLAlchemy model"""
        with app.app_context():
            subscribers = Subscriber.query.filter_by(is_active=True).all()
            return [s.user_id for s in subscribers]
    
    # Function to save news items to database
    def save_news_items(news_items):
        """Save news items to database"""
        with app.app_context():
            # Clear existing news
            NewsItem.query.delete()
            
            # Save new items
            for item in news_items:
                # Find the feed source
                feed_source = FeedSource.query.filter_by(name=item.get('source', '')).first()
                feed_id = feed_source.id if feed_source else None
                
                news_item = NewsItem(
                    title=item['title'],
                    link=item['link'],
                    source=item.get('source', ''),
                    summary=item.get('summary', ''),
                    pub_date=item.get('pub_date', ''),
                    feed_id=feed_id
                )
                db.session.add(news_item)
            
            db.session.commit()

except ImportError:
    # If Flask app is not available, use the simple JSON db
    use_db = False
    from db import add_subscriber, remove_subscriber, get_all_subscribers
    
    def get_bot_settings():
        return None
    
    def is_bot_active():
        return True
    
    def get_telegram_token():
        return config.API_TOKEN
    
    def get_news_per_source():
        return config.NEWS_PER_FEED
        
    def get_daily_send_time():
        return time(8, 0)  # Default to 8:00 AM by Moscow time
        
    def get_all_send_times():
        return [time(8, 0)]  # Default only main time
    
    def save_news_items(news_items):
        pass  # No database to save to
    
    logging.warning("Could not import Flask models, using JSON database instead")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Проверка является ли пользователь администратором
async def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    # Предопределенный список администраторов для аварийного режима
    admin_ids = [502783765, 957555131, 1148332858]
    
    # Если БД недоступна, используем запасной список
    if not use_db:
        return user_id in admin_ids
    
    try:
        with app.app_context():
            subscriber = Subscriber.query.filter_by(user_id=user_id, is_admin=True).first()
            return subscriber is not None
    except Exception as e:
        logger.error(f"Ошибка при проверке статуса администратора: {e}")
        # Если произошла ошибка, используем запасной список
        return user_id in admin_ids

# Create keyboards for bot
def get_main_keyboard():
    """Create main keyboard with commands"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📰 Последние новости")],
            [KeyboardButton(text="✅ Подписаться"), KeyboardButton(text="❌ Отписаться")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="ℹ️ Информация")],
            [KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

# Создаем клавиатуру для администраторов
def get_admin_keyboard():
    """Create keyboard with admin commands"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📰 Последние новости")],
            [KeyboardButton(text="✅ Подписаться"), KeyboardButton(text="❌ Отписаться")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="ℹ️ Информация")],
            [KeyboardButton(text="🔄 Обновить новости"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

# Initialize bot and dispatcher with token from settings
token = get_telegram_token()
bot = Bot(token=token)
dp = Dispatcher()

# Регистрация команд бота
async def set_bot_commands():
    """Зарегистрировать команды бота для удобства пользователей"""
    await bot.set_my_commands([
        BotCommand(command="start", description="Старт - начать работу с ботом"),
        BotCommand(command="новости", description="Запрос новостей - получить свежие новости"),
        BotCommand(command="подписаться", description="Начало подписки - подписаться на рассылку"),
        BotCommand(command="отписаться", description="Отмена подписки - отписаться от рассылки"),
        BotCommand(command="настройки", description="Настройки - посмотреть настройки"),
        BotCommand(command="информация", description="Информация - сведения о боте"),
        BotCommand(command="помощь", description="Помощь - список команд")
    ])

# Command handlers
@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    """Handle /start command"""
    if not is_bot_active():
        await message.reply(
            "⚠️ Бот временно отключен администратором. Пожалуйста, попробуйте позже.",
            parse_mode="HTML"
        )
        return
    
    keyboard = get_main_keyboard()
    
    # Проверяем является ли пользователь администратором
    is_user_admin = await is_admin(message.from_user.id)
    keyboard = get_admin_keyboard() if is_user_admin else get_main_keyboard()
    
    commands_list = (
        "📋 <b>Доступные команды:</b>\n"
        "/новости - получить свежие новости\n"
        "/подписаться - подписаться на ежедневную рассылку\n"
        "/отписаться - отписаться от рассылки\n"
        "/настройки - настройки уведомлений\n"
        "/информация - информация о боте\n"
        "/помощь - показать список команд\n"
    )
    
    if is_user_admin:
        admin_commands = (
            "\n<b>Команды администратора:</b>\n"
            "/статистика - просмотр статистики бота\n"
            "/обновить - обновить новости вручную\n"
        )
        commands_list += admin_commands
    
    await message.reply(
        f"👋 Добро пожаловать в бот «Новости Анапа Pro»!\n\n"
        f"Я буду держать вас в курсе последних новостей Анапы и Краснодарского края.\n\n"
        f"{commands_list}\n"
        f"Вы также можете использовать кнопки меню для удобства.",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.message(Command('новости', 'news'))
@dp.message(F.text == "📰 Последние новости")
async def cmd_news(message: types.Message):
    """Handle /новости command"""
    if not is_bot_active():
        await message.reply(
            "⚠️ Бот временно отключен администратором. Пожалуйста, попробуйте позже.",
            parse_mode="HTML"
        )
        return
    
    await message.reply("🔍 <i>Ищу свежие новости...</i>", parse_mode="HTML")
    
    # Get news per source setting
    news_per_source = get_news_per_source()
    
    news_items, has_errors = get_latest_news(news_per_source)
    formatted_news = format_news_message(news_items)
    
    # Save news items to database if using DB
    if use_db:
        save_news_items(news_items)
    
    # Add status information if there were any errors
    if has_errors:
        formatted_news += "\n\n⚠️ <i>Некоторые источники новостей временно недоступны</i>"
    
    # Проверяем является ли пользователь администратором
    is_user_admin = await is_admin(message.from_user.id)
    keyboard = get_admin_keyboard() if is_user_admin else get_main_keyboard()
    
    await message.reply(
        formatted_news, 
        parse_mode="HTML", 
        disable_web_page_preview=True,
        reply_markup=keyboard
    )

@dp.message(Command('подписаться', 'subscribe'))
@dp.message(F.text == "✅ Подписаться")
async def cmd_subscribe(message: types.Message):
    """Handle /подписаться command"""
    if not is_bot_active():
        await message.reply(
            "⚠️ Бот временно отключен администратором. Пожалуйста, попробуйте позже.",
            parse_mode="HTML"
        )
        return
    
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    # Проверяем является ли пользователь администратором
    is_user_admin = await is_admin(message.from_user.id)
    keyboard = get_admin_keyboard() if is_user_admin else get_main_keyboard()
    
    if add_subscriber(user_id, username, first_name, last_name):
        # Get daily send time
        send_time = get_daily_send_time()
        time_str = send_time.strftime("%H:%M")
        
        await message.reply(
            f"✅ Вы успешно подписались на ежедневную рассылку новостей!\n"
            f"Вы будете получать свежие новости каждый день в {time_str}.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await message.reply(
            "ℹ️ Вы уже подписаны на рассылку новостей.",
            parse_mode="HTML",
            reply_markup=keyboard
        )

@dp.message(Command('отписаться', 'unsubscribe'))
@dp.message(F.text == "❌ Отписаться")
async def cmd_unsubscribe(message: types.Message):
    """Handle /отписаться command"""
    if not is_bot_active():
        await message.reply(
            "⚠️ Бот временно отключен администратором. Пожалуйста, попробуйте позже.",
            parse_mode="HTML"
        )
        return
    
    user_id = message.from_user.id
    
    # Проверяем является ли пользователь администратором
    is_user_admin = await is_admin(message.from_user.id)
    keyboard = get_admin_keyboard() if is_user_admin else get_main_keyboard()
    
    if remove_subscriber(user_id):
        await message.reply(
            "✅ Вы успешно отписались от рассылки новостей.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await message.reply(
            "ℹ️ Вы не были подписаны на рассылку новостей.",
            parse_mode="HTML",
            reply_markup=keyboard
        )

@dp.message(Command('помощь', 'help'))
@dp.message(F.text == "❓ Помощь")
async def cmd_help(message: types.Message):
    """Handle /помощь command"""
    if not is_bot_active():
        await message.reply(
            "⚠️ Бот временно отключен администратором. Пожалуйста, попробуйте позже.",
            parse_mode="HTML"
        )
        return
    
    # Проверяем является ли пользователь администратором
    is_user_admin = await is_admin(message.from_user.id)
    keyboard = get_admin_keyboard() if is_user_admin else get_main_keyboard()
    
    commands_text = (
        "📋 <b>Доступные команды:</b>\n"
        "/start - Начать работу с ботом\n"
        "/новости - Получить свежие новости\n"
        "/подписаться - Подписаться на ежедневную рассылку\n"
        "/отписаться - Отписаться от рассылки\n"
        "/настройки - Настройки уведомлений\n"
        "/информация - Информация о боте\n"
        "/помощь - Показать список команд\n\n"
    )
    
    if is_user_admin:
        commands_text += (
            "<b>Команды администратора:</b>\n"
            "/статистика - Просмотр статистики бота\n"
            "/обновить - Обновить новости вручную\n\n"
        )
    
    commands_text += (
        "Вы также можете использовать кнопки меню для удобства.\n\n"
        "Бот «Новости Анапа Pro» автоматически рассылает новости из различных источников."
    )
    
    await message.reply(
        commands_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.message(Command('информация', 'info'))
@dp.message(F.text == "ℹ️ Информация")
async def cmd_info(message: types.Message):
    """Обработчик команды /информация"""
    if not is_bot_active():
        await message.reply(
            "⚠️ Бот временно отключен администратором. Пожалуйста, попробуйте позже.",
            parse_mode="HTML"
        )
        return
    
    # Проверяем является ли пользователь администратором
    is_user_admin = await is_admin(message.from_user.id)
    keyboard = get_admin_keyboard() if is_user_admin else get_main_keyboard()
    
    # Получаем информацию о боте
    try:
        with app.app_context():
            # Статус бота
            settings = BotSettings.query.first()
            status = "Активен ✅" if (settings and settings.is_active) else "Неактивен ❌"
            
            # Источники новостей
            feed_sources = FeedSource.query.filter_by(is_active=True).all()
            feeds_list = "\n".join([f"• {feed.name}" for feed in feed_sources]) if feed_sources else "Нет активных источников"
            
            # Подписчики
            active_subscribers = Subscriber.query.filter_by(is_active=True).count()
            total_subscribers = Subscriber.query.count()
            
            # Время рассылки
            main_time = settings.daily_send_time.strftime('%H:%M') if settings and settings.daily_send_time else "08:00"
            additional_times = SendTime.query.filter_by(is_active=True).all()
            times_list = [main_time]
            times_list.extend([time.send_time.strftime('%H:%M') for time in additional_times])
            times_formatted = ", ".join(times_list)
            
            # Новости
            news_count = NewsItem.query.count()
            latest_news = NewsItem.query.order_by(NewsItem.created_at.desc()).first()
            latest_update = latest_news.created_at.strftime('%Y-%m-%d %H:%M') if latest_news else "Нет данных"
            
            # Собираем текст сообщения
            info_text = (
                "<b>📊 Информация о боте</b>\n\n"
                f"<b>Статус:</b> {status}\n"
                f"<b>Подписчиков:</b> {active_subscribers} активных из {total_subscribers} всего\n"
                f"<b>Количество новостей в базе:</b> {news_count}\n"
                f"<b>Последнее обновление:</b> {latest_update}\n"
                f"<b>Рассылка в:</b> {times_formatted}\n\n"
                "<b>📰 Источники новостей:</b>\n"
                f"{feeds_list}\n\n"
            )
            
            # Добавляем админскую информацию если пользователь админ
            if is_user_admin:
                admins = Subscriber.query.filter_by(is_admin=True).all()
                admins_list = "\n".join([f"• {admin.first_name or ''} {admin.last_name or ''} (@{admin.username or 'нет username'}) - ID: {admin.user_id}" 
                                        for admin in admins]) if admins else "Нет администраторов"
                
                info_text += (
                    "<b>👑 Администраторы бота:</b>\n"
                    f"{admins_list}\n\n"
                )
            
            info_text += "Для управления подпиской используйте соответствующие команды в меню."
                
    except Exception as e:
        logger.error(f"Error getting bot info: {e}")
        info_text = "⚠️ Не удалось получить информацию о боте. Пожалуйста, попробуйте позже."
    
    await message.reply(
        info_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.message(Command('настройки', 'settings'))
@dp.message(F.text == "⚙️ Настройки")
async def cmd_settings(message: types.Message):
    """Обработчик команды /настройки"""
    if not is_bot_active():
        await message.reply(
            "⚠️ Бот временно отключен администратором. Пожалуйста, попробуйте позже.",
            parse_mode="HTML"
        )
        return
    
    # Проверяем является ли пользователь администратором
    is_user_admin = await is_admin(message.from_user.id)
    keyboard = get_admin_keyboard() if is_user_admin else get_main_keyboard()
    
    # Получаем информацию о подписке пользователя
    user_id = message.from_user.id
    try:
        with app.app_context():
            subscriber = Subscriber.query.filter_by(user_id=user_id).first()
            is_subscribed = subscriber and subscriber.is_active
            
            # Основное время рассылки
            settings = BotSettings.query.first()
            main_time = settings.daily_send_time.strftime('%H:%M') if settings and settings.daily_send_time else "08:00"
            
            # Дополнительные времена
            additional_times = SendTime.query.filter_by(is_active=True).all()
            if additional_times:
                times_list = [time.send_time.strftime('%H:%M') for time in additional_times]
                times_text = ", ".join(times_list)
            else:
                times_text = "Не настроены"
            
            # Формируем текст настроек
            settings_text = (
                "<b>⚙️ Настройки</b>\n\n"
                f"<b>Статус подписки:</b> {'Активна ✅' if is_subscribed else 'Неактивна ❌'}\n"
                f"<b>Основное время рассылки:</b> {main_time}\n"
                f"<b>Дополнительные рассылки:</b> {times_text}\n\n"
            )
            
            if is_user_admin:
                settings_text += (
                    "<b>👑 Права администратора:</b> Есть\n\n"
                    "Используйте веб-интерфейс администратора для настройки бота:\n"
                    "• Управление источниками\n"
                    "• Управление временем рассылки\n"
                    "• Настройка токена и параметров бота"
                )
            else:
                settings_text += (
                    "Для управления подпиской используйте команды /подписаться и /отписаться.\n\n"
                    "Вы будете получать новости по расписанию, настроенному администратором бота."
                )
    
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        settings_text = "⚠️ Не удалось получить настройки. Пожалуйста, попробуйте позже."
    
    await message.reply(
        settings_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.message(Command('статистика', 'stats'))
@dp.message(F.text == "📊 Статистика")
async def cmd_stats(message: types.Message):
    """Обработчик команды /статистика (только для администраторов)"""
    if not is_bot_active():
        await message.reply(
            "⚠️ Бот временно отключен администратором. Пожалуйста, попробуйте позже.",
            parse_mode="HTML"
        )
        return
    
    # Проверяем является ли пользователь администратором
    is_user_admin = await is_admin(message.from_user.id)
    if not is_user_admin:
        await message.reply(
            "⚠️ Эта команда доступна только администраторам бота.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Собираем статистику
    try:
        with app.app_context():
            # Подписчики
            total_subscribers = Subscriber.query.count()
            active_subscribers = Subscriber.query.filter_by(is_active=True).count()
            inactive_subscribers = total_subscribers - active_subscribers
            admins_count = Subscriber.query.filter_by(is_admin=True).count()
            
            # Источники новостей
            total_feeds = FeedSource.query.count()
            active_feeds = FeedSource.query.filter_by(is_active=True).count()
            inactive_feeds = total_feeds - active_feeds
            
            # Новости
            news_count = NewsItem.query.count()
            
            # Статистика по дням
            # Тут можно добавить более детальную статистику в будущем
            
            stats_text = (
                "<b>📊 Статистика бота</b>\n\n"
                f"<b>Подписчики:</b>\n"
                f"• Всего: {total_subscribers}\n"
                f"• Активных: {active_subscribers}\n"
                f"• Неактивных: {inactive_subscribers}\n"
                f"• Администраторов: {admins_count}\n\n"
                f"<b>Источники новостей:</b>\n"
                f"• Всего: {total_feeds}\n"
                f"• Активных: {active_feeds}\n"
                f"• Неактивных: {inactive_feeds}\n\n"
                f"<b>Новости:</b>\n"
                f"• Всего записей: {news_count}\n\n"
                "Используйте веб-интерфейс для просмотра подробной статистики и управления ботом."
            )
    
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        stats_text = "⚠️ Не удалось получить статистику. Пожалуйста, попробуйте позже."
        
    await message.reply(
        stats_text,
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )

@dp.message(Command('обновить', 'refresh'))
@dp.message(F.text == "🔄 Обновить новости")
async def cmd_refresh(message: types.Message):
    """Обработчик команды /обновить (только для администраторов)"""
    if not is_bot_active():
        await message.reply(
            "⚠️ Бот временно отключен администратором. Пожалуйста, попробуйте позже.",
            parse_mode="HTML"
        )
        return
    
    # Проверяем является ли пользователь администратором
    is_user_admin = await is_admin(message.from_user.id)
    if not is_user_admin:
        await message.reply(
            "⚠️ Эта команда доступна только администраторам бота.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
        return
    
    await message.reply(
        "🔄 <i>Запущено обновление новостей...</i>", 
        parse_mode="HTML"
    )
    
    try:
        # Получаем лимит новостей из настроек
        news_per_source = get_news_per_source()
        
        # Получаем новости
        news_items, has_errors = get_latest_news(news_per_source)
        
        # Сохраняем в базу данных
        if use_db:
            save_news_items(news_items)
        
        # Формируем ответ
        if news_items:
            result_text = f"✅ Успешно обновлено {len(news_items)} новостей."
            if has_errors:
                result_text += "\n⚠️ Некоторые источники были недоступны."
        else:
            result_text = "⚠️ Не удалось получить новости. Проверьте настройки источников."
            
    except Exception as e:
        logger.error(f"Error refreshing news: {e}")
        result_text = f"❌ Ошибка при обновлении новостей: {str(e)}"
    
    await message.reply(
        result_text,
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )

@dp.message()
async def unknown_message(message: types.Message):
    """Handle unknown messages"""
    if not is_bot_active():
        return
    
    # Проверяем является ли пользователь администратором
    is_user_admin = await is_admin(message.from_user.id)
    keyboard = get_admin_keyboard() if is_user_admin else get_main_keyboard()
    
    # If it's not a command or a recognized button, offer help
    await message.reply(
        "Я не понимаю эту команду. Воспользуйтесь меню или введите /помощь для списка доступных команд.",
        reply_markup=keyboard
    )

async def send_news_to_subscribers():
    """Send news to all subscribers"""
    try:
        # Check if bot is active
        if not is_bot_active():
            logger.info("Bot is inactive, skipping news delivery")
            return
        
        # Get all active subscribers
        subscribers = get_all_subscribers()
        if not subscribers:
            logger.info("No active subscribers found")
            return
        
        # Get news per source setting
        news_per_source = get_news_per_source()
        
        # Fetch latest news
        logger.info("Fetching news for scheduled delivery")
        news_items, has_errors = get_latest_news(news_per_source)
        
        if not news_items:
            logger.warning("No news items fetched for delivery")
            return
            
        # Save news items to database if using DB
        if use_db:
            save_news_items(news_items)
            
        # Format news message
        formatted_news = format_news_message(news_items)
        
        # Add status information if there were any errors
        if has_errors:
            formatted_news += "\n\n⚠️ <i>Некоторые источники новостей временно недоступны</i>"
        
        # Add footer
        formatted_news += "\n\n<i>Это автоматическая рассылка новостей. Чтобы отписаться, используйте команду /отписаться</i>"
        
        # Send to all subscribers
        logger.info(f"Sending news to {len(subscribers)} subscribers")
        for user_id in subscribers:
            try:
                await bot.send_message(
                    user_id,
                    formatted_news,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                # Add a small delay between messages to avoid flood limits
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error sending news to user {user_id}: {e}")
        
        logger.info("Scheduled news delivery completed")
        
    except Exception as e:
        logger.error(f"Error in scheduled news delivery: {e}")

async def scheduler():
    """Run scheduled tasks"""
    while True:
        try:
            # Get current time
            now = datetime.now().time()
            
            # Get all send times
            send_times = get_all_send_times()
            
            # Check if it's time to send news
            for send_time in send_times:
                # Check if current time is within 1 minute of the send time
                current_minutes = now.hour * 60 + now.minute
                target_minutes = send_time.hour * 60 + send_time.minute
                
                if abs(current_minutes - target_minutes) <= 1:
                    logger.info(f"Scheduled news delivery triggered at {now.strftime('%H:%M')}")
                    await send_news_to_subscribers()
                    # Wait a bit more than a minute to avoid sending twice
                    await asyncio.sleep(70)
                    break
            
            # Check every minute
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Error in scheduler: {e}")
            await asyncio.sleep(60)

async def main():
    """Main function"""
    # Start scheduler task
    asyncio.create_task(scheduler())
    
    # Start the bot
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
