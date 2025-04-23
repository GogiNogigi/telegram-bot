#!/usr/bin/env python
"""
Специальный скрипт для поддержания Always On режима в Replit
Этот скрипт использует подход UptimeRobot для поддержания работы приложения
"""
import threading
import time
import logging
import os
import signal
import sys
import subprocess
import traceback
from datetime import datetime
import atexit

# Создаем директории
os.makedirs('logs', exist_ok=True)
os.makedirs('tmp', exist_ok=True)

# Настройка логирования
log_file = os.path.join('logs', f'keep_alive_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("KeepAlive")

# Глобальные переменные для процессов
WEB_PROCESS = None
BOT_PROCESS = None
SHOULD_EXIT = False

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения работы"""
    global SHOULD_EXIT
    SHOULD_EXIT = True
    logger.info(f"Получен сигнал {sig}, останавливаю процессы...")
    stop_processes()
    sys.exit(0)

def on_exit():
    """Функция, выполняемая при завершении работы скрипта"""
    logger.info("Завершение работы скрипта, останавливаю процессы...")
    stop_processes()

def stop_processes():
    """Остановка запущенных процессов"""
    global WEB_PROCESS, BOT_PROCESS
    
    if WEB_PROCESS:
        logger.info("Останавливаю веб-сервер...")
        try:
            WEB_PROCESS.terminate()
            WEB_PROCESS.wait(timeout=5)
        except Exception as e:
            logger.error(f"Ошибка при остановке веб-сервера: {e}")
            try:
                WEB_PROCESS.kill()
            except:
                pass
        WEB_PROCESS = None
    
    if BOT_PROCESS:
        logger.info("Останавливаю Telegram бота...")
        try:
            BOT_PROCESS.terminate()
            BOT_PROCESS.wait(timeout=5)
        except Exception as e:
            logger.error(f"Ошибка при остановке Telegram бота: {e}")
            try:
                BOT_PROCESS.kill()
            except:
                pass
        BOT_PROCESS = None

def start_web_server():
    """Запуск веб-сервера Flask с Gunicorn"""
    global WEB_PROCESS
    
    try:
        logger.info("Запуск веб-сервера Flask...")
        port = os.environ.get("PORT", "5000")
        logger.info(f"Используемый порт: {port}")
        
        # Команда запуска
        cmd = ["gunicorn", "--bind", f"0.0.0.0:{port}", "--workers", "2", "--timeout", "120", "main:app"]
        logger.info(f"Команда запуска: {' '.join(cmd)}")
        
        # Открываем лог-файл
        web_log_path = os.path.join('logs', f'web_server_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        web_log_file = open(web_log_path, 'w')
        
        # Запускаем процесс
        WEB_PROCESS = subprocess.Popen(
            cmd,
            stdout=web_log_file,
            stderr=web_log_file,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )
        
        logger.info(f"Веб-сервер запущен с PID: {WEB_PROCESS.pid}")
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при запуске веб-сервера: {e}")
        logger.error(traceback.format_exc())
        return False

def start_telegram_bot():
    """Запуск Telegram бота"""
    global BOT_PROCESS
    
    try:
        logger.info("Запуск Telegram бота...")
        
        # Открываем лог-файл
        bot_log_path = os.path.join('logs', f'telegram_bot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        bot_log_file = open(bot_log_path, 'w')
        
        # Команда запуска
        cmd = ["python", "-u", "run_telegram_bot.py"]
        logger.info(f"Команда запуска: {' '.join(cmd)}")
        
        # Запускаем процесс
        BOT_PROCESS = subprocess.Popen(
            cmd,
            stdout=bot_log_file,
            stderr=bot_log_file,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )
        
        logger.info(f"Telegram бот запущен с PID: {BOT_PROCESS.pid}")
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при запуске Telegram бота: {e}")
        logger.error(traceback.format_exc())
        return False

def keep_alive_task():
    """Функция для поддержания процессов работающими"""
    global WEB_PROCESS, BOT_PROCESS, SHOULD_EXIT
    
    logger.info("Запуск системы поддержания работы...")
    
    while not SHOULD_EXIT:
        try:
            # Проверяем веб-сервер
            if WEB_PROCESS and WEB_PROCESS.poll() is not None:
                logger.warning(f"Веб-сервер остановился с кодом {WEB_PROCESS.poll()}, перезапуск...")
                WEB_PROCESS = None
                start_web_server()
            
            # Проверяем Telegram бота
            if BOT_PROCESS and BOT_PROCESS.poll() is not None:
                logger.warning(f"Telegram бот остановился с кодом {BOT_PROCESS.poll()}, перезапуск...")
                BOT_PROCESS = None
                start_telegram_bot()
            
            # Пауза между проверками
            time.sleep(60)
            
        except Exception as e:
            logger.error(f"Ошибка в системе поддержания работы: {e}")
            logger.error(traceback.format_exc())
            time.sleep(120)  # Увеличиваем паузу в случае ошибки

def main():
    """Основная функция"""
    # Регистрация обработчиков сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Регистрация функции, выполняемой при выходе
    atexit.register(on_exit)
    
    logger.info("=" * 50)
    logger.info("ЗАПУСК СИСТЕМЫ ПОДДЕРЖАНИЯ РАБОТЫ")
    logger.info("=" * 50)
    
    # Выдаем права на выполнение
    os.system("chmod +x run_telegram_bot.py health_check.py run_permanently.py")
    
    # Запуск веб-сервера
    web_ok = start_web_server()
    if not web_ok:
        logger.error("Не удалось запустить веб-сервер!")
        sys.exit(1)
    
    # Пауза для инициализации веб-сервера
    time.sleep(3)
    
    # Запуск Telegram бота
    bot_ok = start_telegram_bot()
    if not bot_ok:
        logger.error("Не удалось запустить Telegram бота!")
        stop_processes()
        sys.exit(1)
    
    logger.info("Все сервисы запущены успешно!")
    
    # Создаем и запускаем поток для поддержания работы
    keep_alive_thread = threading.Thread(target=keep_alive_task, daemon=True)
    keep_alive_thread.start()
    
    # Бесконечный цикл для поддержания работы основного потока
    try:
        while not SHOULD_EXIT:
            # Записываем периодические сообщения для контроля
            logger.info("KeepAlive проверка - система работает")
            time.sleep(3600)  # Проверка каждый час
    except KeyboardInterrupt:
        logger.info("Получена команда остановки (Ctrl+C)")
    finally:
        stop_processes()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())