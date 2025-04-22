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

# Create keyboards for bot
def get_main_keyboard():
    """Create main keyboard with commands"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📰 Последние новости")],
            [KeyboardButton(text="✅ Подписаться"), KeyboardButton(text="❌ Отписаться")],
            [KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

# Initialize bot and dispatcher with token from settings
token = get_telegram_token()
bot = Bot(token=token)
dp = Dispatcher()

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
    
    await message.reply(
        "👋 Добро пожаловать в бот «Новости Анапа Pro»!\n\n"
        "Я буду держать вас в курсе последних новостей Анапы и Краснодарского края.\n\n"
        "📋 <b>Доступные команды:</b>\n"
        "/новости - получить свежие новости\n"
        "/подписаться - подписаться на ежедневную рассылку\n"
        "/отписаться - отписаться от рассылки\n"
        "/помощь - показать список команд\n\n"
        "Вы также можете использовать кнопки меню для удобства.",
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
    
    await message.reply(
        formatted_news, 
        parse_mode="HTML", 
        disable_web_page_preview=True,
        reply_markup=get_main_keyboard()
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
    
    if add_subscriber(user_id, username, first_name, last_name):
        # Get daily send time
        send_time = get_daily_send_time()
        time_str = send_time.strftime("%H:%M")
        
        await message.reply(
            f"✅ Вы успешно подписались на ежедневную рассылку новостей!\n"
            f"Вы будете получать свежие новости каждый день в {time_str}.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.reply(
            "ℹ️ Вы уже подписаны на рассылку новостей.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
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
    
    if remove_subscriber(user_id):
        await message.reply(
            "✅ Вы успешно отписались от рассылки новостей.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.reply(
            "ℹ️ Вы не были подписаны на рассылку новостей.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )

@dp.message(Command('помощь', 'help'))
@dp.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: types.Message):
    """Handle /помощь command"""
    if not is_bot_active():
        await message.reply(
            "⚠️ Бот временно отключен администратором. Пожалуйста, попробуйте позже.",
            parse_mode="HTML"
        )
        return
    
    # Get sources from the database
    sources_text = ""
    if use_db:
        with app.app_context():
            sources = FeedSource.query.filter_by(is_active=True).all()
            if sources:
                sources_text = "\n".join([f"- {s.name}" for s in sources])
            else:
                sources_text = "- Источники новостей не настроены"
    else:
        sources_text = "- Официальный сайт Анапы\n- Кубань 24"
    
    # Получаем время рассылки
    send_time_info = ""
    if use_db:
        with app.app_context():
            # Основное время
            settings = BotSettings.query.first()
            if settings and settings.daily_send_time:
                main_time = settings.daily_send_time.strftime("%H:%M")
                send_time_info = f"Основное время рассылки: <b>{main_time}</b> (МСК)\n"
            
            # Дополнительные времена
            additional_times = SendTime.query.filter_by(is_active=True).order_by(SendTime.send_time).all()
            if additional_times:
                times_str = ", ".join([time.send_time.strftime("%H:%M") for time in additional_times])
                send_time_info += f"Дополнительные времена: <b>{times_str}</b> (МСК)"
            else:
                send_time_info += "Дополнительные времена рассылки не настроены"
    else:
        send_time_info = "Время рассылки: <b>08:00</b> (МСК)"
    
    await message.reply(
        f"📋 <b>Доступные команды:</b>\n"
        f"/новости - получить свежие новости\n"
        f"/подписаться - подписаться на ежедневную рассылку\n"
        f"/отписаться - отписаться от рассылки\n"
        f"/помощь - показать список команд\n\n"
        f"<b>Расписание рассылки:</b>\n{send_time_info}\n\n"
        f"<b>Источники новостей:</b>\n{sources_text}",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

# Background tasks
async def send_news_to_user(user_id: int, news_message: str) -> bool:
    """Send news to a specific user with error handling
    
    Args:
        user_id: Telegram user ID
        news_message: Formatted HTML message with news
        
    Returns:
        bool: True if message was sent successfully, False otherwise
    """
    try:
        await bot.send_message(
            user_id, 
            news_message, 
            parse_mode="HTML", 
            disable_web_page_preview=True
        )
        logger.info(f"News sent to user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send news to user {user_id}: {e}")
        return False

async def scheduled_news():
    """Send news to all subscribers periodically according to Moscow time"""
    # Словарь для отслеживания времени последней отправки для каждого временного слота
    last_sent_times = {}
    time_checked = datetime.now()
    
    # Константа для московского часового пояса (UTC+3)
    MOSCOW_UTC_OFFSET = 3
    
    # Функция для получения текущего московского времени
    def get_moscow_time():
        # Получаем текущее UTC время
        utc_now = datetime.utcnow()
        # Добавляем смещение для московского времени
        moscow_time = utc_now.replace(tzinfo=None) + timedelta(hours=MOSCOW_UTC_OFFSET)
        return moscow_time
    
    while True:
        try:
            # Проверяем, активен ли бот
            if not is_bot_active():
                logger.info("Bot is disabled, skipping scheduled news")
                await asyncio.sleep(60)  # Проверяем снова через минуту
                continue
            
            # Получаем текущее время по Москве
            now = get_moscow_time()
            
            # Если прошло менее 30 секунд с последней проверки, пропускаем
            if (now - time_checked).total_seconds() < 30:
                await asyncio.sleep(10)
                continue
                
            time_checked = now
            
            # Получаем все активные времена рассылки
            send_times = get_all_send_times()
            
            # Текущий день и время
            current_day = now.date()
            current_hour = now.hour
            current_minute = now.minute
            
            # Форматирование для логов
            moscow_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"Current Moscow time: {moscow_time_str}")
            
            # Проверяем каждое время отправки
            should_send = False
            target_time = None
            
            for send_time in send_times:
                time_key = f"{send_time.hour}:{send_time.minute}"
                target_hour = send_time.hour
                target_minute = send_time.minute
                
                # Если это время еще не отправлялось сегодня
                if time_key not in last_sent_times or last_sent_times[time_key].date() != current_day:
                    # Если текущее время совпадает с целевым временем отправки (± 5 минут)
                    if (current_hour == target_hour and abs(current_minute - target_minute) <= 5):
                        should_send = True
                        target_time = send_time
                        logger.info(f"Found matching send time: {target_hour}:{target_minute}")
                        break
            
            # Если не время отправки, ждем и проверяем снова
            if not should_send:
                # Находим ближайшее время рассылки для определения оптимального интервала проверки
                wait_time = 60  # По умолчанию проверяем каждую минуту
                
                # Если есть время рассылки в течение ближайших 10 минут, проверяем чаще
                for send_time in send_times:
                    minutes_until = ((send_time.hour - current_hour) * 60 + 
                                    (send_time.minute - current_minute)) % (24 * 60)
                    if 0 < minutes_until <= 10:
                        wait_time = 30  # Проверяем чаще ближе к целевому времени
                        break
                
                logger.info(f"Not time to send yet. Next check in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
                continue
            
            # Время отправлять новости!
            logger.info(f"It's time to send daily news (Moscow time: {target_time.hour}:{target_time.minute})")
            
            # Отмечаем, что данное время рассылки использовано сегодня
            time_key = f"{target_time.hour}:{target_time.minute}"
            last_sent_times[time_key] = now
            
            # Получаем всех подписчиков
            subscribers = get_all_subscribers()
            
            if subscribers:
                # Получаем настройку количества новостей для источника
                news_per_source = get_news_per_source()
                
                # Получаем и форматируем новости
                news_items, has_errors = get_latest_news(news_per_source)
                
                # Сохраняем элементы новостей в базу данных, если используется БД
                if use_db:
                    save_news_items(news_items)
                
                if news_items:
                    current_time = now.strftime("%d.%m.%Y %H:%M")
                    header = f"🗞 <b>Ежедневная рассылка новостей на {current_time} (МСК):</b>\n\n"
                    
                    formatted_news = format_news_message(news_items)
                    
                    # Добавляем информацию о статусе, если были ошибки
                    if has_errors:
                        formatted_news += "\n\n⚠️ <i>Некоторые источники новостей временно недоступны</i>"
                    
                    full_message = header + formatted_news
                    
                    # Отправляем всем подписчикам
                    success_count = 0
                    for user_id in subscribers:
                        if await send_news_to_user(user_id, full_message):
                            success_count += 1
                    
                    logger.info(f"Daily news sent to {success_count}/{len(subscribers)} subscribers")
                
                else:
                    logger.warning("No news to send in scheduled update")
            
            else:
                logger.info("No subscribers for news delivery")
            
            # Ждем некоторое время и проверяем снова
            # После отправки новостей делаем паузу, чтобы избежать повторной отправки
            await asyncio.sleep(600)  # 10 минут
            
        except Exception as e:
            logger.error(f"Error in scheduled news task: {e}")
            logger.exception("Full exception details:")
            await asyncio.sleep(60)  # Ждем минуту и пробуем снова

async def send_news_to_subscribers():
    """Send news to all subscribers manually"""
    try:
        # Check if bot is active
        if not is_bot_active():
            logger.info("Bot is disabled, cannot send news")
            return False
        
        # Get all subscribers
        subscribers = get_all_subscribers()
        
        if not subscribers:
            logger.info("No subscribers for news delivery")
            return False
        
        # Get news per source setting
        news_per_source = get_news_per_source()
        
        # Get and format news
        news_items, has_errors = get_latest_news(news_per_source)
        
        # Save news items to database if using DB
        if use_db:
            save_news_items(news_items)
        
        if not news_items:
            logger.warning("No news to send in manual update")
            return False
        
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
        header = f"🗞 <b>Свежие новости на {current_time}:</b>\n\n"
        
        formatted_news = format_news_message(news_items)
        
        # Add status information if there were any errors
        if has_errors:
            formatted_news += "\n\n⚠️ <i>Некоторые источники новостей временно недоступны</i>"
        
        full_message = header + formatted_news
        
        # Send to all subscribers
        success_count = 0
        for user_id in subscribers:
            if await send_news_to_user(user_id, full_message):
                success_count += 1
        
        logger.info(f"Manual news sent to {success_count}/{len(subscribers)} subscribers")
        return True
    
    except Exception as e:
        logger.error(f"Error sending news manually: {e}")
        return False

async def on_startup():
    """Startup actions when bot begins"""
    logger.info("Starting up the Anapa News Bot")
    asyncio.create_task(scheduled_news())

if __name__ == '__main__':
    # Start the bot
    dp.startup.register(on_startup)
    # Register the bot with the dispatcher
    dp.bot = bot
    asyncio.run(dp.start_polling(bot, skip_updates=True))
