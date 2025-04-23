#!/usr/bin/env python
"""
Скрипт для проверки состояния работы сервисов проекта.
Выполняет мониторинг веб-интерфейса и Telegram бота.
Может запускаться как отдельный процесс или по расписанию.
"""
import os
import sys
import logging
import time
import json
import traceback
import subprocess
import requests
from datetime import datetime, timedelta
import signal
import asyncio

# Настройка логирования
os.makedirs('logs', exist_ok=True)
log_file = f'logs/health_check_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger("HealthCheck")

# Глобальные настройки
CHECK_INTERVAL = 300  # Интервал проверки в секундах (по умолчанию 5 минут)
WEB_URL = "http://localhost:5000"  # URL веб-интерфейса для проверки
HEARTBEAT_FILE = "heartbeat.json"  # Файл для хранения информации о состоянии сервисов
MAX_RESTART_ATTEMPTS = 3  # Максимальное число попыток перезапуска
RESTART_COOLDOWN = 600  # Период охлаждения между перезапусками (10 минут)
TELEGRAM_TOKEN = None  # Токен Telegram бота (будет получен из базы)

# Времена последних перезапусков
last_web_restart = datetime.min
last_bot_restart = datetime.min
web_restart_attempts = 0
bot_restart_attempts = 0

# Флаг для завершения работы
should_exit = False

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения"""
    global should_exit
    should_exit = True
    logger.info(f"Получен сигнал {sig}, завершаю работу...")
    sys.exit(0)

def get_telegram_token():
    """Получить токен Telegram бота из базы данных"""
    try:
        import psycopg2
        import os
        
        # Определяем URL подключения к базе данных из переменной окружения
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.warning("Переменная DATABASE_URL не найдена, проверка Telegram бота будет пропущена")
            return None
        
        # Создаем подключение к базе данных
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        # Получаем токен из таблицы настроек
        cur.execute("SELECT telegram_token FROM bot_settings LIMIT 1")
        result = cur.fetchone()
        
        # Закрываем соединение
        cur.close()
        conn.close()
        
        if result and result[0]:
            return result[0]
        
        logger.warning("Токен Telegram бота не найден в базе данных")
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении токена Telegram бота: {e}")
        return None

def update_heartbeat(service_name, status, details=None):
    """Обновить информацию о состоянии сервиса в heartbeat файле"""
    try:
        heartbeat_data = {}
        if os.path.exists(HEARTBEAT_FILE):
            with open(HEARTBEAT_FILE, 'r') as f:
                heartbeat_data = json.load(f)
        
        # Обновляем данные
        if service_name not in heartbeat_data:
            heartbeat_data[service_name] = {}
        
        heartbeat_data[service_name].update({
            'status': status,
            'last_check': datetime.now().isoformat(),
            'details': details or {}
        })
        
        # Сохраняем обновленный heartbeat
        with open(HEARTBEAT_FILE, 'w') as f:
            json.dump(heartbeat_data, f, indent=2)
        
        logger.info(f"Обновлен heartbeat для сервиса {service_name}: {status}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении heartbeat: {e}")

def check_web_service():
    """Проверить состояние веб-интерфейса"""
    global last_web_restart, web_restart_attempts
    
    try:
        # Отправляем GET-запрос на эндпоинт проверки здоровья
        health_url = f"{WEB_URL}/api/health"
        response = requests.get(health_url, timeout=10)
        
        # Проверяем статус ответа
        if response.status_code == 200:
            try:
                # Анализируем ответ API
                health_data = response.json()
                
                # Получаем статус компонентов
                db_status = health_data.get('components', {}).get('database', {}).get('status', 'unknown')
                bot_status = 'healthy' if health_data.get('components', {}).get('bot', {}).get('active', False) else 'warning'
                stats = health_data.get('components', {}).get('stats', {})
                
                # Проверяем общий статус
                overall_status = 'healthy'
                components_status = {}
                
                if db_status != 'healthy':
                    overall_status = 'warning'
                    components_status['database'] = db_status
                
                if bot_status != 'healthy':
                    overall_status = 'warning'
                    components_status['bot'] = bot_status
                
                # Обновляем heartbeat с детальной информацией
                update_heartbeat('web', overall_status, {
                    'status_code': response.status_code,
                    'response_time': response.elapsed.total_seconds(),
                    'components': components_status,
                    'stats': stats
                })
                
                logger.info(f"Веб-интерфейс доступен, статус: {overall_status}")
                
                if overall_status == 'healthy':
                    # Сбрасываем счетчик попыток перезапуска при успешной проверке
                    web_restart_attempts = 0
                
                return overall_status == 'healthy'
            except ValueError as e:
                # Ошибка при разборе JSON
                logger.warning(f"Ошибка при разборе ответа API: {e}")
                update_heartbeat('web', 'warning', {
                    'status_code': response.status_code,
                    'error': f"Ошибка JSON: {str(e)}",
                    'response_time': response.elapsed.total_seconds()
                })
                return False
        else:
            logger.warning(f"Веб-интерфейс вернул неожиданный статус: {response.status_code}")
            update_heartbeat('web', 'warning', {
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            })
            return False
    except requests.RequestException as e:
        logger.error(f"Ошибка при проверке веб-интерфейса: {e}")
        update_heartbeat('web', 'error', {
            'error': str(e),
            'traceback': traceback.format_exc()
        })
        
        # Проверяем, можно ли выполнить перезапуск
        current_time = datetime.now()
        if (current_time - last_web_restart > timedelta(seconds=RESTART_COOLDOWN) and 
            web_restart_attempts < MAX_RESTART_ATTEMPTS):
            logger.info("Пытаюсь перезапустить веб-сервер...")
            if restart_web_service():
                last_web_restart = current_time
                web_restart_attempts += 1
        
        return False

def restart_web_service():
    """Перезапустить веб-сервер"""
    try:
        # Находим процесс gunicorn
        cmd = ["pkill", "-f", "gunicorn"]
        subprocess.run(cmd, check=False)
        
        # Даем процессу время на завершение
        time.sleep(2)
        
        # Запускаем новый процесс
        cmd = ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "main:app"]
        subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        logger.info("Веб-сервер успешно перезапущен")
        update_heartbeat('web', 'restarted')
        return True
    except Exception as e:
        logger.error(f"Ошибка при перезапуске веб-сервера: {e}")
        update_heartbeat('web', 'restart_failed', {'error': str(e)})
        return False

async def check_telegram_bot():
    """Проверить состояние Telegram бота"""
    global TELEGRAM_TOKEN, last_bot_restart, bot_restart_attempts
    
    if not TELEGRAM_TOKEN:
        # Попробуем получить токен из базы данных
        TELEGRAM_TOKEN = get_telegram_token()
        if not TELEGRAM_TOKEN:
            logger.error("Не удалось получить токен Telegram бота, проверка пропущена")
            update_heartbeat('telegram_bot', 'unknown', {
                'error': 'Токен не найден'
            })
            return False
    
    try:
        # URL для получения информации о боте
        bot_info_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe"
        
        # Отправляем запрос
        response = requests.get(bot_info_url, timeout=10)
        
        # Проверяем результат
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                logger.info(f"Telegram бот доступен: {data['result']['username']}")
                update_heartbeat('telegram_bot', 'healthy', {
                    'username': data['result']['username'],
                    'response_time': response.elapsed.total_seconds()
                })
                # Сбрасываем счетчик попыток перезапуска при успешной проверке
                bot_restart_attempts = 0
                return True
            else:
                logger.warning(f"Telegram API вернул ошибку: {data.get('description', 'Неизвестная ошибка')}")
                update_heartbeat('telegram_bot', 'warning', {
                    'error': data.get('description', 'Неизвестная ошибка')
                })
        else:
            logger.warning(f"Telegram API вернул неожиданный статус: {response.status_code}")
            update_heartbeat('telegram_bot', 'warning', {
                'status_code': response.status_code
            })
        
        # Проверяем, нужен ли перезапуск
        current_time = datetime.now()
        if (current_time - last_bot_restart > timedelta(seconds=RESTART_COOLDOWN) and 
            bot_restart_attempts < MAX_RESTART_ATTEMPTS):
            logger.info("Пытаюсь перезапустить Telegram бота...")
            if await restart_telegram_bot():
                last_bot_restart = current_time
                bot_restart_attempts += 1
        
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке Telegram бота: {e}")
        update_heartbeat('telegram_bot', 'error', {
            'error': str(e),
            'traceback': traceback.format_exc()
        })
        return False

async def restart_telegram_bot():
    """Перезапустить Telegram бота"""
    try:
        # Находим процесс бота
        cmd = ["pkill", "-f", "run_telegram_bot.py"]
        subprocess.run(cmd, check=False)
        
        # Даем процессу время на завершение
        await asyncio.sleep(2)
        
        # Запускаем новый процесс
        cmd = ["python", "run_telegram_bot.py"]
        subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        logger.info("Telegram бот успешно перезапущен")
        update_heartbeat('telegram_bot', 'restarted')
        return True
    except Exception as e:
        logger.error(f"Ошибка при перезапуске Telegram бота: {e}")
        update_heartbeat('telegram_bot', 'restart_failed', {'error': str(e)})
        return False

def check_processes():
    """Проверить, запущены ли необходимые процессы"""
    try:
        # Проверяем веб-сервер (gunicorn)
        web_process = subprocess.run(
            ["pgrep", "-f", "gunicorn"],
            capture_output=True, text=True
        )
        web_running = web_process.returncode == 0
        
        # Проверяем Telegram бота
        bot_process = subprocess.run(
            ["pgrep", "-f", "run_telegram_bot.py"],
            capture_output=True, text=True
        )
        bot_running = bot_process.returncode == 0
        
        logger.info(f"Статус процессов: веб-сервер: {'запущен' if web_running else 'не запущен'}, "
                   f"Telegram бот: {'запущен' if bot_running else 'не запущен'}")
        
        # Обновляем heartbeat
        update_heartbeat('processes', 'healthy' if (web_running and bot_running) else 'warning', {
            'web_running': web_running,
            'bot_running': bot_running
        })
        
        return web_running, bot_running
    except Exception as e:
        logger.error(f"Ошибка при проверке процессов: {e}")
        update_heartbeat('processes', 'error', {'error': str(e)})
        return False, False

async def main_loop():
    """Основной цикл проверки состояния сервисов"""
    global should_exit
    
    logger.info("=" * 60)
    logger.info("ЗАПУСК СИСТЕМЫ МОНИТОРИНГА СОСТОЯНИЯ СЕРВИСОВ")
    logger.info("=" * 60)
    
    # Создаем или обновляем heartbeat файл
    update_heartbeat('system', 'starting', {
        'start_time': datetime.now().isoformat(),
        'check_interval': CHECK_INTERVAL
    })
    
    try:
        # Бесконечный цикл проверок
        while not should_exit:
            logger.info("-" * 40)
            logger.info(f"Выполняется проверка сервисов: {datetime.now().isoformat()}")
            
            # Проверяем процессы
            web_running, bot_running = check_processes()
            
            # Проверяем веб-интерфейс
            web_ok = check_web_service()
            
            # Проверяем Telegram бота
            bot_ok = await check_telegram_bot()
            
            # Обновляем общий статус
            overall_status = 'healthy'
            if not (web_ok and bot_ok):
                overall_status = 'warning'
            
            update_heartbeat('system', overall_status, {
                'web_status': 'healthy' if web_ok else 'error',
                'bot_status': 'healthy' if bot_ok else 'error',
                'last_check': datetime.now().isoformat()
            })
            
            # Ожидаем до следующей проверки
            logger.info(f"Проверка завершена. Следующая проверка через {CHECK_INTERVAL} секунд")
            
            # Проверяем условие выхода каждую секунду
            for _ in range(CHECK_INTERVAL):
                if should_exit:
                    break
                await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Получена команда остановки (Ctrl+C)")
    except Exception as e:
        logger.error(f"Критическая ошибка в основном цикле: {e}", exc_info=True)
    finally:
        update_heartbeat('system', 'stopped', {
            'stop_time': datetime.now().isoformat(),
            'reason': 'manual' if should_exit else 'error'
        })
        logger.info("Мониторинг остановлен")

async def main():
    """Основная функция"""
    # Регистрация обработчиков сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Запуск основного цикла
    await main_loop()

if __name__ == "__main__":
    # Запуск скрипта
    asyncio.run(main())