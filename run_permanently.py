#!/usr/bin/env python
"""
Скрипт для одновременного запуска веб-приложения и Telegram бота
в режиме постоянной работы (always-on).
"""
import subprocess
import sys
import time
import signal
import os
import logging
import threading
from datetime import datetime

# Настройка логирования
os.makedirs('logs', exist_ok=True)
log_file = f'logs/permanently_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger("Permanent")

# Глобальные переменные для процессов
web_process = None
bot_process = None
should_exit = False

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения работы"""
    global should_exit
    should_exit = True
    logger.info(f"Получен сигнал {sig}, останавливаю процессы...")
    stop_processes()
    sys.exit(0)

def stop_processes():
    """Остановка запущенных процессов"""
    global web_process, bot_process
    
    if web_process:
        logger.info("Останавливаю веб-сервер...")
        try:
            web_process.terminate()
            web_process.wait(timeout=5)
        except Exception as e:
            logger.error(f"Ошибка при остановке веб-сервера: {e}")
            web_process.kill()
        web_process = None
    
    if bot_process:
        logger.info("Останавливаю Telegram бота...")
        try:
            bot_process.terminate()
            bot_process.wait(timeout=5)
        except Exception as e:
            logger.error(f"Ошибка при остановке Telegram бота: {e}")
            bot_process.kill()
        bot_process = None

def start_web_server():
    """Запуск веб-сервера Flask с Gunicorn"""
    global web_process
    
    try:
        logger.info("Запуск веб-сервера Flask...")
        port = os.environ.get("PORT", "5000")
        cmd = ["gunicorn", "--bind", f"0.0.0.0:{port}", "--workers", "2", "--timeout", "120", "main:app"]
        logger.info(f"Команда: {' '.join(cmd)}")
        
        web_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1  # Line buffered
        )
        logger.info(f"Веб-сервер запущен с PID: {web_process.pid}")
        
        # Мониторинг вывода в отдельном потоке
        threading.Thread(
            target=monitor_output,
            args=(web_process, "WEB"),
            daemon=True
        ).start()
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при запуске веб-сервера: {e}")
        return False

def start_telegram_bot():
    """Запуск Telegram бота"""
    global bot_process
    
    try:
        logger.info("Запуск Telegram бота...")
        cmd = ["python", "run_telegram_bot.py"]
        logger.info(f"Команда: {' '.join(cmd)}")
        
        bot_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1  # Line buffered
        )
        logger.info(f"Telegram бот запущен с PID: {bot_process.pid}")
        
        # Мониторинг вывода в отдельном потоке
        threading.Thread(
            target=monitor_output,
            args=(bot_process, "BOT"),
            daemon=True
        ).start()
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при запуске Telegram бота: {e}")
        return False

def monitor_output(process, prefix):
    """Мониторинг вывода процесса в реальном времени"""
    while True:
        line = process.stdout.readline()
        if not line:
            break
        logger.info(f"[{prefix}] {line.strip()}")
    
    while True:
        line = process.stderr.readline()
        if not line:
            break
        logger.error(f"[{prefix}] ERROR: {line.strip()}")

def check_and_restart_processes():
    """Проверяет статус процессов и перезапускает их при необходимости"""
    global web_process, bot_process, should_exit
    
    while not should_exit:
        try:
            # Проверка веб-сервера
            if web_process and web_process.poll() is not None:
                logger.warning("Веб-сервер остановился. Перезапуск...")
                start_web_server()
            
            # Проверка Telegram бота
            if bot_process and bot_process.poll() is not None:
                logger.warning("Telegram бот остановился. Перезапуск...")
                start_telegram_bot()
            
            # Пауза между проверками
            time.sleep(30)
            
        except Exception as e:
            logger.error(f"Ошибка при проверке процессов: {e}")
            time.sleep(60)  # Увеличиваем паузу в случае ошибки

def main():
    """Основная функция"""
    # Регистрация обработчиков сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("=" * 50)
    logger.info("ЗАПУСК ПРОЕКТА В РЕЖИМЕ ПОСТОЯННОЙ РАБОТЫ")
    logger.info("=" * 50)
    
    # Запуск веб-сервера
    if not start_web_server():
        logger.error("Не удалось запустить веб-сервер, выход...")
        return 1
    
    # Небольшая пауза для инициализации веб-сервера
    time.sleep(2)
    
    # Запуск Telegram бота
    if not start_telegram_bot():
        logger.error("Не удалось запустить Telegram бота, выход...")
        stop_processes()
        return 1
    
    logger.info("Все сервисы успешно запущены!")
    logger.info("Система работает в режиме постоянной работы")
    
    # Запуск мониторинга и перезапуска процессов
    try:
        check_and_restart_processes()
    except KeyboardInterrupt:
        logger.info("Получена команда остановки (Ctrl+C)")
    finally:
        stop_processes()
        logger.info("Работа завершена")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())