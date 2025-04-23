import feedparser
import logging
import os
import sys
from typing import List, Dict, Any, Tuple
from datetime import datetime
import time
import re

from config import RSS_FEEDS, NEWS_PER_FEED

# Add the parent directory to path so we can import Flask models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import Flask models
try:
    from main import app, FeedSource, BotSettings
    use_db = True
    
    def get_feed_urls() -> List[str]:
        """Get feed URLs from the Flask database"""
        with app.app_context():
            feeds = FeedSource.query.filter_by(is_active=True).all()
            return [feed.url for feed in feeds]
            
    def get_news_limit() -> int:
        """Get number of news per source from settings"""
        with app.app_context():
            settings = BotSettings.query.first()
            if settings:
                return settings.news_per_source
            return NEWS_PER_FEED
except ImportError:
    # If Flask app is not available, use config directly
    use_db = False
    
    def get_feed_urls() -> List[str]:
        """Get feed URLs from config"""
        return RSS_FEEDS
        
    def get_news_limit() -> int:
        """Get number of news per source from config"""
        return NEWS_PER_FEED

def sanitize_html(text: str) -> str:
    """Remove unwanted HTML tags but keep basic formatting"""
    # Remove all HTML tags except allowed ones
    allowed_tags = ['b', 'i', 'u', 'a', 'code', 'pre']
    for tag in allowed_tags:
        text = text.replace(f"<{tag}>", f"[{tag}]").replace(f"</{tag}>", f"[/{tag}]")
    
    # Remove all other HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Restore allowed tags
    for tag in allowed_tags:
        text = text.replace(f"[{tag}]", f"<{tag}>").replace(f"[/{tag}]", f"</{tag}>")
    
    return text

def get_feed_entries(feed_url: str, max_entries: int = 3) -> List[Dict[str, Any]]:
    """Get entries from a specific RSS feed"""
    try:
        # Добавляем User-Agent в запрос, чтобы избежать блокировки
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'}
        feed = feedparser.parse(feed_url, request_headers=headers)
        
        if not feed or not hasattr(feed, 'entries') or not feed.entries:
            logger.warning(f"No entries found in feed {feed_url}")
            return []
            
        if hasattr(feed, 'bozo_exception') and feed.bozo:
            logger.warning(f"Partial error parsing feed {feed_url}: {feed.bozo_exception}")
            # Продолжаем, если есть хоть какие-то entries
            if not feed.entries:
                return []
        
        entries = []
        
        # Определяем имя источника (из feed или из URL)
        source_name = None
        if hasattr(feed, 'feed') and hasattr(feed.feed, 'title'):
            source_name = feed.feed.title
        if not source_name:
            try:
                # Извлекаем имя источника из URL
                if "lenta.ru" in feed_url:
                    source_name = "Лента.ру"
                elif "news.mail.ru" in feed_url:
                    source_name = "Новости Mail.ru"
                elif "russian.rt.com" in feed_url:
                    source_name = "RT на русском"
                else:
                    # Берём домен из URL
                    domain = feed_url.split('//')[-1].split('/')[0]
                    source_name = domain
            except:
                source_name = "Новости"
        
        for i, entry in enumerate(feed.entries):
            if i >= max_entries:
                break
                
            # Extract required fields with fallbacks
            title = getattr(entry, 'title', 'Без заголовка')
            
            # Получаем URL новости
            link = getattr(entry, 'link', '#')
            if not link or link == '#':
                link = getattr(entry, 'id', '#')
            
            # Ищем дату публикации в разных полях
            pub_date = None
            date_fields = ['published', 'pubDate', 'updated', 'date']
            for field in date_fields:
                if hasattr(entry, field) and getattr(entry, field):
                    try:
                        # Пытаемся использовать parsed-варианты полей для даты
                        parsed_field = f"{field}_parsed"
                        if hasattr(entry, parsed_field) and getattr(entry, parsed_field):
                            time_struct = getattr(entry, parsed_field)
                            pub_date = time.strftime("%d.%m.%Y %H:%M", time_struct)
                            break
                        # Если нет parsed-поля, пытаемся распарсить строку
                        date_str = getattr(entry, field)
                        if date_str:
                            # Преобразуем для локализованного отображения
                            dt = datetime.strptime(date_str[:25], "%a, %d %b %Y %H:%M:%S")
                            pub_date = dt.strftime("%d.%m.%Y %H:%M")
                            break
                    except Exception as e:
                        logger.debug(f"Couldn't parse date: {e}")
                        continue
            
            # Ищем описание новости в разных полях
            summary = None
            summary_fields = ['summary', 'description', 'content']
            for field in summary_fields:
                if hasattr(entry, field) and getattr(entry, field):
                    content = getattr(entry, field)
                    # Проверка для различных форматов полей в RSS-фидах
                    if isinstance(content, list) and content:
                        # Некоторые фиды (например, Atom) хранят контент в списке словарей
                        for item in content:
                            if isinstance(item, dict) and 'value' in item:
                                summary = item['value']
                                break
                    elif isinstance(content, str):
                        summary = content
                    
                    if summary:
                        break
            
            # Если описание не найдено - используем заголовок
            if not summary:
                summary = title
                
            # Очистка HTML и ограничение длины
            summary = sanitize_html(summary)
            if len(summary) > 300:
                summary = summary[:297] + "..."
            
            entries.append({
                'title': title,
                'link': link,
                'pub_date': pub_date,
                'summary': summary,
                'source': source_name
            })
            
        return entries
        
    except Exception as e:
        logger.error(f"Error fetching feed {feed_url}: {e}")
        return []

def get_latest_news(max_per_feed: int = 3) -> Tuple[List[Dict[str, Any]], bool]:
    """Get latest news from all configured RSS feeds"""
    all_news = []
    has_errors = False
    
    try:
        # Get feed URLs either from database or from config
        feed_urls = get_feed_urls()
        
        if not feed_urls:
            logger.warning("No feed URLs configured")
            return [], True
        
        for feed_url in feed_urls:
            entries = get_feed_entries(feed_url, max_per_feed)
            if not entries:
                has_errors = True
            all_news.extend(entries)
        
        # Sort by publication date (if available)
        all_news.sort(key=lambda x: x.get('pub_date', ''), reverse=True)
        
        return all_news, has_errors
        
    except Exception as e:
        logger.error(f"Error getting latest news: {e}")
        return [], True

def format_news_message(news_items: List[Dict[str, Any]]) -> str:
    """Format news items into a Telegram message"""
    if not news_items:
        return "🔍 К сожалению, новостей не найдено."
    
    # Группируем новости по источникам
    news_by_source = {}
    for item in news_items:
        source = item.get('source', 'Неизвестный источник')
        if source not in news_by_source:
            news_by_source[source] = []
        news_by_source[source].append(item)
    
    all_parts = []
    
    # Добавляем заголовок с текущим временем по Москве
    try:
        # Если доступен pytz, используем его для получения московского времени
        import pytz
        from datetime import timedelta
        moscow_tz = pytz.timezone('Europe/Moscow')
        now = datetime.now(pytz.UTC).astimezone(moscow_tz)
        time_string = f"{now.strftime('%d.%m.%Y %H:%M')} (MSK)"
    except ImportError:
        # Иначе считаем вручную UTC+3
        from datetime import timedelta
        now = datetime.now() + timedelta(hours=3)
        time_string = f"{now.strftime('%d.%m.%Y %H:%M')} (по Москве)"
    
    all_parts.append(f"📰 <b>НОВОСТИ НА {time_string}</b>")
    
    # Форматируем каждую группу новостей
    for source, items in news_by_source.items():
        # Заголовок источника
        source_header = f"🗞 <b>{source}</b> ({len(items)})"
        all_parts.append(source_header)
        
        # Новости из этого источника
        for item in items:
            title = item['title'].replace('<', '&lt;').replace('>', '&gt;')
            link = item['link']
            pub_date = f" ({item['pub_date']})" if item.get('pub_date') else ""
            
            # Упрощаем описание для избежания проблем с HTML
            summary = item.get('summary', '')
            # Избегаем проблем с HTML разметкой путем очистки тегов
            summary = re.sub(r'<[^>]+>', '', summary)
            # Ограничиваем длину описания
            if len(summary) > 150:
                summary = summary[:147] + "..."
            
            # Форматируем новость
            news_item = (
                f"📰 <b>{title}</b>{pub_date}\n"
                f"{summary}\n"
                f"🔗 <a href='{link}'>Читать полностью</a>"
            )
            all_parts.append(news_item)
        
        # Добавляем разделитель между группами
        all_parts.append("─────────────────")
    
    # Удаляем последний разделитель
    if all_parts and all_parts[-1] == "─────────────────":
        all_parts.pop()
    
    return "\n\n".join(all_parts)
