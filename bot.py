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
    
    keyboard = get_main_keyboard()
    
    await message.reply(
        "📋 <b>Доступные команды:</b>\n"
        "/новости - получить свежие новости\n"
        "/подписаться - подписаться на ежедневную рассылку\n"
        "/отписаться - отписаться от рассылки\n"
        "/помощь - показать список команд\n\n"
        "Вы также можете использовать кнопки меню для удобства.\n\n"
        "Бот «Новости Анапа Pro» автоматически рассылает новости из различных источников.",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.message()
async def unknown_message(message: types.Message):
    """Handle unknown messages"""
    if not is_bot_active():
        return
    
    # If it's not a command or a recognized button, offer help
    await message.reply(
        "Я не понимаю эту команду. Воспользуйтесь меню или введите /помощь для списка доступных команд.",
        reply_markup=get_main_keyboard()
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
