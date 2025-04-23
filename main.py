import os
import json
import glob
import time
import psutil
import zipfile
import logging
import subprocess
from datetime import datetime, timedelta, time as datetime_time
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Time
from sqlalchemy.sql import func

# Create database first
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "anapa-news-bot-secret")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1) # needed for url_for to generate with https

@app.context_processor
def inject_bot_username():
    """Inject bot username into all templates"""
    # Используем имя из токена API Telegram
    bot_username = "AnapaProBot"
    
    # Попытаемся получить имя из токена
    try:
        api_token = os.environ.get('TELEGRAM_API_TOKEN', '')
        if not api_token:
            from config import API_TOKEN
            api_token = API_TOKEN
    except Exception:
        # Если не удалось, используем стандартное имя
        pass
    
    # Add current datetime in Moscow time zone
    try:
        # Если pytz доступен, используем его для получения московского времени
        import pytz
        moscow_tz = pytz.timezone('Europe/Moscow')
        now = datetime.now(pytz.UTC).astimezone(moscow_tz)
    except ImportError:
        # Если pytz не доступен, используем смещение UTC+3
        moscow_offset = timedelta(hours=3)
        now = datetime.now() + moscow_offset
    
    # Utility function for template to format dates
    def format_date(dt, format_str='%Y-%m-%d'):
        if dt:
            return dt.strftime(format_str)
        return ''
    
    return {
        'bot_username': bot_username,
        'now': now,
        'format_date': format_date,
        'moscow_timezone': 'Europe/Moscow',
        'moscow_utc_offset': '+3'
    }

# Use file-based SQLite for persistence
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///anapa_news.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
    "connect_args": {
        "options": "-c timezone=Europe/Moscow"
    }
}

# Initialize the app with the extension
db.init_app(app)

# Define models here to avoid circular imports
class Subscriber(db.Model):
    """Model for bot subscribers"""
    __tablename__ = 'subscribers'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    notes = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Subscriber {self.user_id}>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'notes': self.notes,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'last_updated': self.last_updated.strftime('%Y-%m-%d %H:%M:%S') if self.last_updated else None
        }
        
class FeedSource(db.Model):
    """Model for RSS feed sources"""
    __tablename__ = 'feed_sources'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    url = Column(String(255), nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<FeedSource {self.name}>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'last_updated': self.last_updated.strftime('%Y-%m-%d %H:%M:%S') if self.last_updated else None
        }

class BotSettings(db.Model):
    """Model for bot settings"""
    __tablename__ = 'bot_settings'
    
    id = Column(Integer, primary_key=True)
    is_active = Column(Boolean, default=True)
    news_per_source = Column(Integer, default=3)
    daily_send_time = Column(Time, default=func.time(8, 0))  # 8:00 AM по Москве
    telegram_token = Column(String(255), nullable=True)
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<BotSettings {self.id}>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'is_active': self.is_active,
            'news_per_source': self.news_per_source,
            'daily_send_time': self.daily_send_time.strftime('%H:%M') if self.daily_send_time else '08:00',
            'telegram_token': self.telegram_token,
            'last_updated': self.last_updated.strftime('%Y-%m-%d %H:%M:%S') if self.last_updated else None
        }

class SendTime(db.Model):
    """Модель для дополнительных времен рассылки новостей"""
    __tablename__ = 'send_times'
    
    id = Column(Integer, primary_key=True)
    send_time = Column(Time, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<SendTime {self.send_time.strftime('%H:%M')}>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'send_time': self.send_time.strftime('%H:%M') if self.send_time else None,
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }
        
class NewsItem(db.Model):
    """Model for cached news items"""
    __tablename__ = 'news_items'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    link = Column(String(255), nullable=False)
    source = Column(String(100), nullable=True)
    summary = Column(String(1000), nullable=True)
    pub_date = Column(String(50), nullable=True)
    feed_id = Column(Integer, ForeignKey('feed_sources.id'), nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<NewsItem {self.title}>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'link': self.link,
            'source': self.source,
            'summary': self.summary,
            'pub_date': self.pub_date,
            'feed_id': self.feed_id,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

# Define routes
@app.route('/')
def home():
    """Main page of the application"""
    # Get latest news for the front page
    news_items = NewsItem.query.order_by(NewsItem.created_at.desc()).limit(10).all()
    # Get bot settings
    settings = BotSettings.query.first()
    if not settings:
        settings = BotSettings()
        db.session.add(settings)
        db.session.commit()
    
    # Get additional send times
    send_times = SendTime.query.filter_by(is_active=True).order_by(SendTime.send_time).all()
        
    return render_template('index.html', 
                          title="Новости Анапы - Телеграм бот",
                          news_items=news_items,
                          settings=settings,
                          send_times=send_times)

@app.route('/subscribers')
def subscribers():
    """Show all subscribers"""
    subscribers_list = Subscriber.query.all()
    return render_template('subscribers.html', 
                          subscribers=subscribers_list, 
                          title="Подписчики")

@app.route('/subscribers/add', methods=['POST'])
def add_subscriber():
    """Add a new subscriber"""
    try:
        user_id = int(request.form.get('user_id'))
        username = request.form.get('username')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        notes = request.form.get('notes')
        
        # Check if subscriber already exists
        existing = Subscriber.query.filter_by(user_id=user_id).first()
        if existing:
            existing.username = username
            existing.first_name = first_name
            existing.last_name = last_name
            existing.notes = notes
            existing.is_active = True
            db.session.commit()
            flash(f'Подписчик с ID {user_id} обновлен', 'success')
        else:
            new_subscriber = Subscriber(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                notes=notes,
                is_active=True
            )
            db.session.add(new_subscriber)
            db.session.commit()
            flash(f'Подписчик с ID {user_id} добавлен', 'success')
        
        return redirect(url_for('subscribers'))
    except Exception as e:
        flash(f'Ошибка: {str(e)}', 'danger')
        return redirect(url_for('subscribers'))

@app.route('/subscribers/toggle/<int:subscriber_id>', methods=['POST'])
def toggle_subscriber(subscriber_id):
    """Toggle subscriber active status"""
    subscriber = Subscriber.query.get_or_404(subscriber_id)
    subscriber.is_active = not subscriber.is_active
    db.session.commit()
    
    status = "активирован" if subscriber.is_active else "деактивирован"
    flash(f'Подписчик с ID {subscriber.user_id} {status}', 'success')
    return redirect(url_for('subscribers'))

@app.route('/subscribers/toggle_admin/<int:subscriber_id>', methods=['POST'])
def toggle_admin(subscriber_id):
    """Toggle subscriber admin status"""
    subscriber = Subscriber.query.get_or_404(subscriber_id)
    subscriber.is_admin = not subscriber.is_admin
    db.session.commit()
    
    status = "назначен администратором" if subscriber.is_admin else "лишен прав администратора"
    flash(f'Подписчик с ID {subscriber.user_id} {status}', 'success')
    return redirect(url_for('subscribers'))

@app.route('/subscribers/delete/<int:subscriber_id>', methods=['POST'])
def delete_subscriber(subscriber_id):
    """Delete a subscriber"""
    subscriber = Subscriber.query.get_or_404(subscriber_id)
    db.session.delete(subscriber)
    db.session.commit()
    
    flash(f'Подписчик с ID {subscriber.user_id} удален', 'success')
    return redirect(url_for('subscribers'))

@app.route('/feeds')
def feeds():
    """Show all feed sources"""
    feed_sources = FeedSource.query.all()
    return render_template('feeds.html', 
                          feeds=feed_sources, 
                          title="Источники новостей")

@app.route('/feeds/add', methods=['POST'])
def add_feed():
    """Add a new feed source"""
    try:
        name = request.form.get('name')
        url = request.form.get('url')
        
        # Check if feed already exists
        existing = FeedSource.query.filter_by(url=url).first()
        if existing:
            existing.name = name
            existing.is_active = True
            db.session.commit()
            flash(f'Источник новостей "{name}" обновлен', 'success')
        else:
            new_feed = FeedSource(
                name=name,
                url=url,
                is_active=True
            )
            db.session.add(new_feed)
            db.session.commit()
            flash(f'Источник новостей "{name}" добавлен', 'success')
        
        return redirect(url_for('feeds'))
    except Exception as e:
        flash(f'Ошибка: {str(e)}', 'danger')
        return redirect(url_for('feeds'))

@app.route('/feeds/toggle/<int:feed_id>', methods=['POST'])
def toggle_feed(feed_id):
    """Toggle feed source active status"""
    feed = FeedSource.query.get_or_404(feed_id)
    feed.is_active = not feed.is_active
    db.session.commit()
    
    status = "активирован" if feed.is_active else "деактивирован"
    flash(f'Источник новостей "{feed.name}" {status}', 'success')
    return redirect(url_for('feeds'))

@app.route('/feeds/delete/<int:feed_id>', methods=['POST'])
def delete_feed(feed_id):
    """Delete a feed source"""
    feed = FeedSource.query.get_or_404(feed_id)
    db.session.delete(feed)
    db.session.commit()
    
    flash(f'Источник новостей "{feed.name}" удален', 'success')
    return redirect(url_for('feeds'))

@app.route('/settings')
def settings():
    """Bot settings page"""
    bot_settings = BotSettings.query.first()
    if not bot_settings:
        bot_settings = BotSettings()
        db.session.add(bot_settings)
        db.session.commit()
    
    # Получаем дополнительные времена рассылки
    send_times = SendTime.query.order_by(SendTime.send_time).all()
    
    return render_template('settings.html', 
                          settings=bot_settings,
                          send_times=send_times,
                          title="Настройки бота")

@app.route('/settings/update', methods=['POST'])
def update_settings():
    """Update bot settings"""
    try:
        bot_settings = BotSettings.query.first()
        if not bot_settings:
            bot_settings = BotSettings()
            db.session.add(bot_settings)
        
        # Update settings
        bot_settings.is_active = 'is_active' in request.form
        
        # Get news per source
        news_per_source = request.form.get('news_per_source')
        if news_per_source and news_per_source.isdigit():
            bot_settings.news_per_source = int(news_per_source)
        
        # Get daily send time
        send_time_str = request.form.get('daily_send_time')
        if send_time_str:
            try:
                hours, minutes = map(int, send_time_str.split(':'))
                bot_settings.daily_send_time = datetime_time(hours, minutes)
            except:
                pass  # Ignore invalid time format
        
        # Get Telegram token
        telegram_token = request.form.get('telegram_token')
        if telegram_token:
            bot_settings.telegram_token = telegram_token
            
        db.session.commit()
        flash('Настройки бота обновлены', 'success')
        
        return redirect(url_for('settings'))
    except Exception as e:
        flash(f'Ошибка: {str(e)}', 'danger')
        return redirect(url_for('settings'))

@app.route('/settings/add_time', methods=['POST'])
def add_send_time():
    """Add a new send time"""
    try:
        send_time_str = request.form.get('send_time')
        if send_time_str:
            hours, minutes = map(int, send_time_str.split(':'))
            send_time = datetime_time(hours, minutes)
            
            # Check if time already exists
            existing = SendTime.query.filter(
                SendTime.send_time == send_time
            ).first()
            
            if existing:
                existing.is_active = True
                db.session.commit()
                flash(f'Время рассылки {send_time_str} активировано', 'success')
            else:
                new_time = SendTime(
                    send_time=send_time,
                    is_active=True
                )
                db.session.add(new_time)
                db.session.commit()
                flash(f'Время рассылки {send_time_str} добавлено', 'success')
        
        return redirect(url_for('settings'))
    except Exception as e:
        flash(f'Ошибка: {str(e)}', 'danger')
        return redirect(url_for('settings'))

@app.route('/settings/toggle_time/<int:time_id>', methods=['POST'])
def toggle_send_time(time_id):
    """Toggle send time active status"""
    send_time = SendTime.query.get_or_404(time_id)
    send_time.is_active = not send_time.is_active
    db.session.commit()
    
    time_str = send_time.send_time.strftime('%H:%M')
    status = "активировано" if send_time.is_active else "деактивировано"
    flash(f'Время рассылки {time_str} {status}', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/delete_time/<int:time_id>', methods=['POST'])
def delete_send_time(time_id):
    """Delete a send time"""
    send_time = SendTime.query.get_or_404(time_id)
    time_str = send_time.send_time.strftime('%H:%M')
    db.session.delete(send_time)
    db.session.commit()
    
    flash(f'Время рассылки {time_str} удалено', 'success')
    return redirect(url_for('settings'))

@app.route('/news')
def news():
    """Show all cached news items"""
    news_items = NewsItem.query.order_by(NewsItem.created_at.desc()).all()
    return render_template('news.html', 
                          news_items=news_items, 
                          title="Новости")

@app.route('/news/fetch', methods=['POST'])
def fetch_news():
    """Fetch latest news manually"""
    try:
        from utils import get_latest_news, get_news_limit
        
        # Get news per source from settings
        news_per_source = get_news_limit()
        
        # Fetch latest news
        news_items, has_errors = get_latest_news(news_per_source)
        
        # Save to database
        # Clear existing news
        NewsItem.query.delete()
        
        # Add new items
        for item in news_items:
            # Find the feed source
            feed_source = None
            if 'source' in item:
                feed_source = FeedSource.query.filter_by(name=item['source']).first()
            
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
        
        # Add status information if there were any errors
        if has_errors:
            flash('Новости обновлены, но некоторые источники недоступны', 'warning')
        else:
            flash(f'Успешно получено {len(news_items)} новостей', 'success')
        
        return redirect(url_for('news'))
    except Exception as e:
        flash(f'Ошибка при получении новостей: {str(e)}', 'danger')
        return redirect(url_for('news'))

@app.route('/api/feeds', methods=['GET'])
def api_feeds():
    """API to get feed sources as JSON"""
    try:
        feeds = FeedSource.query.filter_by(is_active=True).all()
        return jsonify({
            'success': True,
            'feeds': [feed.to_dict() for feed in feeds]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/subscribers', methods=['GET'])
def api_subscribers():
    """API to get subscribers as JSON"""
    try:
        subscribers = Subscriber.query.filter_by(is_active=True).all()
        return jsonify({
            'success': True,
            'subscribers': [sub.to_dict() for sub in subscribers]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/settings', methods=['GET'])
def api_settings():
    """API to get bot settings as JSON"""
    try:
        settings = BotSettings.query.first()
        if not settings:
            settings = BotSettings()
            db.session.add(settings)
            db.session.commit()
            
        return jsonify({
            'success': True,
            'settings': settings.to_dict()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/news', methods=['GET'])
def api_news():
    """API to get cached news items as JSON"""
    try:
        news_items = NewsItem.query.order_by(NewsItem.created_at.desc()).all()
        return jsonify({
            'success': True,
            'news': [item.to_dict() for item in news_items]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/health', methods=['GET'])
def api_health():
    """API для проверки состояния сервиса (heartbeat)"""
    import os
    import json
    import time
    from datetime import datetime
    
    # Проверка базы данных
    db_ok = True
    db_error = None
    try:
        db.session.execute(db.select(BotSettings).limit(1))
    except Exception as e:
        db_ok = False
        db_error = str(e)
    
    # Проверка настроек бота
    bot_settings = BotSettings.query.first()
    bot_active = bot_settings.is_active if bot_settings else False
    
    # Проверка наличия telegram_token
    token_exists = bool(bot_settings and bot_settings.telegram_token)
    
    # Сбор информации о системе с помощью psutil
    system_info = {}
    try:
        import psutil
        system_info = {
            "uptime": int(time.time() - psutil.boot_time()),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent
        }
    except ImportError:
        # Если psutil не доступен, используем старый метод
        try:
            with open('/proc/uptime', 'r') as f:
                system_info["uptime"] = float(f.readline().split()[0])
        except:
            system_info["uptime"] = None
    
    # Проверка heartbeat файла если он существует
    heartbeat_data = {}
    heartbeat_file = "heartbeat.json"
    if os.path.exists(heartbeat_file):
        try:
            with open(heartbeat_file, 'r') as f:
                heartbeat_data = json.load(f)
        except:
            pass
    
    # Получение информации о подписчиках
    subscribers_count = Subscriber.query.filter_by(is_active=True).count()
    
    # Получение информации о новостях
    news_count = NewsItem.query.count()
    latest_news = NewsItem.query.order_by(NewsItem.created_at.desc()).first()
    latest_news_time = latest_news.created_at.isoformat() if latest_news else None
    
    # Получение информации о источниках
    feeds_count = FeedSource.query.filter_by(is_active=True).count()
    
    # Отправка ответа
    response = {
        'status': 'ok' if db_ok else 'error',
        'timestamp': datetime.now().isoformat(),
        'components': {
            'database': {
                'status': 'healthy' if db_ok else 'error',
                'error': db_error
            },
            'bot': {
                'active': bot_active,
                'token_exists': token_exists
            },
            'system': system_info,
            'stats': {
                'subscribers': subscribers_count,
                'news_items': news_count,
                'latest_news_time': latest_news_time,
                'active_feeds': feeds_count
            }
        }
    }
    
    # Добавляем данные heartbeat, если они есть
    if heartbeat_data:
        response['heartbeat'] = heartbeat_data
    
    return jsonify(response)

# Функция для инициализации админов
def initialize_admins():
    """Initialize admin users with predefined IDs"""
    # List of admin user IDs
    admin_ids = [502783765, 957555131, 1148332858]
    
    for admin_id in admin_ids:
        # Проверяем существует ли пользователь
        admin = Subscriber.query.filter_by(user_id=admin_id).first()
        
        if admin:
            # Если пользователь существует, делаем его админом
            if not admin.is_admin:
                admin.is_admin = True
                print(f"Пользователь ID {admin_id} назначен администратором")
        else:
            # Если пользователя нет, создаем его как админа
            new_admin = Subscriber(
                user_id=admin_id,
                username=None,
                first_name=f"Admin {admin_id}",
                is_active=True,
                is_admin=True
            )
            db.session.add(new_admin)
            print(f"Создан новый администратор с ID {admin_id}")
    
    db.session.commit()

# Create DB tables on startup
with app.app_context():
    db.create_all()
    
    # Initialize default RSS feeds if there are none
    if FeedSource.query.count() == 0:
        from config import RSS_FEEDS
        for url in RSS_FEEDS:
            name = url.split('//')[-1].split('/')[0]
            feed = FeedSource(name=name, url=url)
            db.session.add(feed)
        db.session.commit()
    
    # Initialize bot settings if not present
    if BotSettings.query.count() == 0:
        from config import API_TOKEN, NEWS_PER_FEED
        settings = BotSettings(
            telegram_token=API_TOKEN,
            news_per_source=NEWS_PER_FEED
        )
        db.session.add(settings)
        db.session.commit()
    
    # Initialize admin users
    initialize_admins()

# Маршруты для мониторинга и просмотра логов
@app.route('/monitor')
def monitor():
    """Страница мониторинга состояния системы"""
    return render_template('monitor.html', title="Мониторинг системы")

@app.route('/logs')
def view_logs():
    """Просмотр логов системы"""
    log_type = request.args.get('log_type', 'all')
    log_file = request.args.get('log_file', 'latest')
    
    # Определяем директорию с логами
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Получаем список доступных лог-файлов
    log_files = []
    if log_type == 'all':
        log_files = glob.glob(os.path.join(logs_dir, '*.log'))
    elif log_type == 'web':
        log_files = glob.glob(os.path.join(logs_dir, 'web*.log'))
    elif log_type == 'bot':
        log_files = glob.glob(os.path.join(logs_dir, 'bot*.log')) + glob.glob(os.path.join(logs_dir, 'telegram*.log'))
    elif log_type == 'monitor':
        log_files = glob.glob(os.path.join(logs_dir, 'monitor*.log')) + glob.glob(os.path.join(logs_dir, 'health*.log'))
    
    # Сортируем файлы по дате модификации (новые вначале)
    log_files = sorted(log_files, key=os.path.getmtime, reverse=True)
    log_files = [os.path.basename(f) for f in log_files]
    
    # Выбираем файл для отображения
    if log_file == 'latest' and log_files:
        log_file = log_files[0]
    
    log_content = ''
    log_size = '0 bytes'
    log_update_time = 'неизвестно'
    can_clear = False
    
    if log_file and log_file in log_files:
        file_path = os.path.join(logs_dir, log_file)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                log_content = f.read()
            
            # Ограничиваем размер контента
            if len(log_content) > 500000:  # ~500KB
                log_content = "... [начало файла обрезано] ...\n\n" + log_content[-500000:]
            
            # Получаем информацию о файле
            file_stat = os.stat(file_path)
            log_size = f"{file_stat.st_size / 1024:.1f} KB"
            log_update_time = datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            
            # Файл можно очистить только если он не системный
            can_clear = not log_file.startswith(('system', 'gunicorn'))
            
        except Exception as e:
            log_content = f"Ошибка при чтении файла: {str(e)}"
    
    log_file_display = log_file if log_file else "Лог-файл не выбран"
    
    return render_template(
        'logs.html',
        title="Просмотр логов",
        log_type=log_type,
        log_file=log_file,
        log_file_display=log_file_display,
        log_files=log_files,
        log_content=log_content,
        log_size=log_size,
        log_update_time=log_update_time,
        can_clear=can_clear
    )

@app.route('/api/get_log_files')
def get_log_files():
    """API для получения списка лог-файлов определенного типа"""
    log_type = request.args.get('log_type', 'all')
    
    # Определяем директорию с логами
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Получаем список доступных лог-файлов
    log_files = []
    if log_type == 'all':
        log_files = glob.glob(os.path.join(logs_dir, '*.log'))
    elif log_type == 'web':
        log_files = glob.glob(os.path.join(logs_dir, 'web*.log'))
    elif log_type == 'bot':
        log_files = glob.glob(os.path.join(logs_dir, 'bot*.log')) + glob.glob(os.path.join(logs_dir, 'telegram*.log'))
    elif log_type == 'monitor':
        log_files = glob.glob(os.path.join(logs_dir, 'monitor*.log')) + glob.glob(os.path.join(logs_dir, 'health*.log'))
    
    # Сортируем файлы по дате модификации (новые вначале)
    log_files = sorted(log_files, key=os.path.getmtime, reverse=True)
    log_files = [os.path.basename(f) for f in log_files]
    
    return jsonify({
        'success': True,
        'files': log_files
    })

@app.route('/api/download_log')
def download_log():
    """API для скачивания лог-файла"""
    log_type = request.args.get('log_type', 'all')
    log_file = request.args.get('log_file', 'latest')
    
    # Определяем директорию с логами
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    
    # Получаем список доступных лог-файлов
    log_files = []
    if log_type == 'all':
        log_files = glob.glob(os.path.join(logs_dir, '*.log'))
    elif log_type == 'web':
        log_files = glob.glob(os.path.join(logs_dir, 'web*.log'))
    elif log_type == 'bot':
        log_files = glob.glob(os.path.join(logs_dir, 'bot*.log')) + glob.glob(os.path.join(logs_dir, 'telegram*.log'))
    elif log_type == 'monitor':
        log_files = glob.glob(os.path.join(logs_dir, 'monitor*.log')) + glob.glob(os.path.join(logs_dir, 'health*.log'))
    
    # Сортируем файлы по дате модификации (новые вначале)
    log_files = sorted(log_files, key=os.path.getmtime, reverse=True)
    
    # Выбираем файл для скачивания
    if log_file == 'latest' and log_files:
        file_path = log_files[0]
    else:
        file_path = os.path.join(logs_dir, log_file)
    
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return send_file(
            file_path,
            as_attachment=True,
            download_name=os.path.basename(file_path),
            mimetype='text/plain'
        )
    else:
        return jsonify({
            'success': False,
            'error': 'Файл не найден'
        }), 404

@app.route('/api/clear_log', methods=['POST'])
def clear_log():
    """API для очистки лог-файла"""
    log_type = request.args.get('log_type', 'all')
    log_file = request.args.get('log_file', 'latest')
    
    # Определяем директорию с логами
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    
    # Получаем список доступных лог-файлов
    log_files = []
    if log_type == 'all':
        log_files = glob.glob(os.path.join(logs_dir, '*.log'))
    elif log_type == 'web':
        log_files = glob.glob(os.path.join(logs_dir, 'web*.log'))
    elif log_type == 'bot':
        log_files = glob.glob(os.path.join(logs_dir, 'bot*.log')) + glob.glob(os.path.join(logs_dir, 'telegram*.log'))
    elif log_type == 'monitor':
        log_files = glob.glob(os.path.join(logs_dir, 'monitor*.log')) + glob.glob(os.path.join(logs_dir, 'health*.log'))
    
    # Сортируем файлы по дате модификации (новые вначале)
    log_files = sorted(log_files, key=os.path.getmtime, reverse=True)
    
    # Выбираем файл для очистки
    if log_file == 'latest' and log_files:
        file_path = log_files[0]
    else:
        file_path = os.path.join(logs_dir, log_file)
    
    # Проверяем, что это не системный файл
    if os.path.basename(file_path).startswith(('system', 'gunicorn')):
        return jsonify({
            'success': False,
            'error': 'Невозможно очистить системный лог-файл'
        }), 403
    
    try:
        if os.path.exists(file_path) and os.path.isfile(file_path):
            with open(file_path, 'w') as f:
                f.write(f"Лог-файл очищен {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            return jsonify({
                'success': True
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Файл не найден'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/archive_logs')
def archive_logs():
    """API для архивации всех лог-файлов"""
    # Определяем директорию с логами
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    
    # Получаем список всех лог-файлов
    log_files = glob.glob(os.path.join(logs_dir, '*.log'))
    
    if not log_files:
        return jsonify({
            'success': False,
            'error': 'Лог-файлы не найдены'
        }), 404
    
    # Создаем временный архив
    archive_path = os.path.join(logs_dir, f'logs_archive_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip')
    
    try:
        with zipfile.ZipFile(archive_path, 'w') as zipf:
            for file in log_files:
                zipf.write(file, os.path.basename(file))
        
        return send_file(
            archive_path,
            as_attachment=True,
            download_name=os.path.basename(archive_path),
            mimetype='application/zip'
        )
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        # Удаляем временный архив после отправки
        if os.path.exists(archive_path):
            try:
                os.remove(archive_path)
            except:
                pass

@app.route('/api/rotate_logs', methods=['POST'])
def rotate_logs():
    """API для ротации лог-файлов (удаление старых)"""
    try:
        data = request.get_json()
        days = data.get('days', 7)
        
        if not isinstance(days, int) or days < 1:
            return jsonify({
                'success': False,
                'error': 'Неверное количество дней'
            }), 400
        
        # Определяем директорию с логами
        logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
        
        # Получаем список всех лог-файлов
        log_files = glob.glob(os.path.join(logs_dir, '*.log'))
        
        deleted_count = 0
        cutoff_time = time.time() - (days * 86400)  # N дней в секундах
        
        for file in log_files:
            # Пропускаем системные файлы
            if os.path.basename(file).startswith(('system', 'gunicorn')):
                continue
                
            # Проверяем время модификации
            mtime = os.path.getmtime(file)
            if mtime < cutoff_time:
                os.remove(file)
                deleted_count += 1
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/restart/<service>', methods=['POST'])
def restart_service(service):
    """API для перезапуска сервисов"""
    if service not in ['web', 'bot']:
        return jsonify({
            'success': False,
            'error': 'Неизвестный сервис'
        }), 400
    
    try:
        if service == 'web':
            # Перезапуск веб-сервера
            cmd = ["pkill", "-f", "gunicorn"]
            subprocess.run(cmd, check=False)
            return jsonify({
                'success': True,
                'message': 'Команда на перезапуск веб-сервера отправлена'
            })
        elif service == 'bot':
            # Перезапуск Telegram бота
            cmd = ["pkill", "-f", "run_telegram_bot.py"]
            subprocess.run(cmd, check=False)
            # Запуск бота 
            import threading
            def restart_bot_thread():
                time.sleep(2)  # даем время на завершение
                os.system("python run_telegram_bot.py &")
            threading.Thread(target=restart_bot_thread).start()
            return jsonify({
                'success': True,
                'message': 'Команда на перезапуск Telegram бота отправлена'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/start/<service>', methods=['POST'])
def start_service(service):
    """API для запуска сервисов"""
    if service not in ['monitor']:
        return jsonify({
            'success': False,
            'error': 'Неизвестный сервис'
        }), 400
    
    try:
        if service == 'monitor':
            # Запуск мониторинга
            import threading
            def start_monitor_thread():
                os.system("python health_check.py &")
            threading.Thread(target=start_monitor_thread).start()
            return jsonify({
                'success': True,
                'message': 'Мониторинг запущен'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/stop/<service>', methods=['POST'])
def stop_service(service):
    """API для остановки сервисов"""
    if service not in ['monitor']:
        return jsonify({
            'success': False,
            'error': 'Неизвестный сервис'
        }), 400
    
    try:
        if service == 'monitor':
            # Остановка мониторинга
            cmd = ["pkill", "-f", "health_check.py"]
            subprocess.run(cmd, check=False)
            return jsonify({
                'success': True,
                'message': 'Мониторинг остановлен'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Импорт модуля для запуска бота
import bot_runner

if __name__ == '__main__':
    # Запускаем Telegram бота в отдельном потоке
    bot_runner.start_bot_thread()
    
    # Запуск Flask сервера
    app.run(host='0.0.0.0', port=5000, debug=True)
