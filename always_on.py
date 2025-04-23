#!/usr/bin/env python
"""
Скрипт для запуска в режиме always-on
Запускает и Flask-приложение, и Telegram-бота в режиме постоянной работы
"""
import subprocess
import sys
import time
import signal
import os
import logging
import threading

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("always_on.log")
    ]
)
logger = logging.getLogger("AlwaysOn")

# Глобальные переменные
web_process = None
bot_process = None
should_exit = False

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения"""
    global should_exit
    should_exit = True
    logger.info("Получен сигнал завершения, останавливаю процессы...")
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
        except:
            web_process.kill()
        web_process = None
    
    if bot_process:
        logger.info("Останавливаю Telegram бота...")
        try:
            bot_process.terminate()
            bot_process.wait(timeout=5)
        except:
            bot_process.kill()
        bot_process = None

def start_web_server():
    """Запуск веб-сервера Flask с Gunicorn"""
    global web_process
    
    try:
        logger.info("Запуск веб-сервера Flask...")
        cmd = ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "main:app"]
        logger.info(f"Команда: {' '.join(cmd)}")
        
        web_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logger.info(f"Веб-сервер запущен с PID: {web_process.pid}")
        
        # Мониторинг вывода в отдельном потоке
        threading.Thread(target=monitor_output, args=(web_process, "WEB"), daemon=True).start()
        
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
            text=True
        )
        logger.info(f"Telegram бот запущен с PID: {bot_process.pid}")
        
        # Мониторинг вывода в отдельном потоке
        threading.Thread(target=monitor_output, args=(bot_process, "BOT"), daemon=True).start()
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при запуске Telegram бота: {e}")
        return False

def monitor_output(process, prefix):
    """Мониторинг вывода процесса в реальном времени"""
    for line in iter(process.stdout.readline, ''):
        if line:
            logger.info(f"[{prefix}] {line.strip()}")
    
    for line in iter(process.stderr.readline, ''):
        if line:
            logger.error(f"[{prefix}] ERROR: {line.strip()}")

def monitor_processes():
    """Мониторинг состояния процессов и их перезапуск при необходимости"""
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
            
            # Выводим информацию о состоянии каждые 5 минут
            if int(time.time()) % 300 < 10:  # Примерно каждые 5 минут
                web_status = "Работает" if web_process and web_process.poll() is None else "Остановлен"
                bot_status = "Работает" if bot_process and bot_process.poll() is None else "Остановлен"
                logger.info(f"СТАТУС: Веб-сервер: {web_status}, Telegram бот: {bot_status}")
            
            # Пауза между проверками
            time.sleep(10)
        except Exception as e:
            logger.error(f"Ошибка при мониторинге процессов: {e}")
            time.sleep(30)  # Увеличиваем паузу в случае ошибки

def main():
    """Основная функция"""
    logger.info("=" * 80)
    logger.info("ЗАПУСК В РЕЖИМЕ ALWAYS-ON")
    logger.info("=" * 80)
    
    # Регистрация обработчиков сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Запуск компонентов
    web_ok = start_web_server()
    if not web_ok:
        logger.error("Не удалось запустить веб-сервер, выход...")
        return 1
    
    bot_ok = start_telegram_bot()
    if not bot_ok:
        logger.error("Не удалось запустить Telegram бота, выход...")
        stop_processes()
        return 1
    
    # Запуск мониторинга в отдельном потоке
    monitor_thread = threading.Thread(target=monitor_processes, daemon=True)
    monitor_thread.start()
    
    logger.info("Система успешно запущена в режиме Always-On!")
    logger.info("Для работы в режиме постоянной работы (даже при закрытии браузера):")
    logger.info("1. Выполните деплой проекта через кнопку 'Deploy' в интерфейсе Replit")
    logger.info("2. Настройте 'Always On' в разделе 'Deployment' настроек проекта")
    
    try:
        # Бесконечный цикл для поддержания программы в рабочем состоянии
        while not should_exit:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Получена команда остановки (Ctrl+C)")
    finally:
        stop_processes()
        logger.info("Работа завершена")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())