#!/usr/bin/env python
"""
Скрипт для одновременного запуска веб-приложения и Telegram бота
в режиме постоянной работы (always-on).
"""
import os
import sys
import logging
import subprocess
import signal
import time
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

# Глобальные переменные для хранения процессов
web_process = None
bot_process = None
should_exit = False

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения работы"""
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
        web_process = subprocess.Popen(
            ["gunicorn", "--bind", "0.0.0.0:5000", "--reuse-port", "--workers", "2", "main:app"],
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
        bot_process = subprocess.Popen(
            ["python", "run_telegram_bot.py"],
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

def check_and_restart_processes():
    """Проверяет статус процессов и перезапускает их при необходимости"""
    global web_process, bot_process, should_exit
    
    while not should_exit:
        # Проверка веб-сервера
        if web_process and web_process.poll() is not None:
            logger.warning("Веб-сервер остановлен. Перезапуск...")
            start_web_server()
        
        # Проверка Telegram бота
        if bot_process and bot_process.poll() is not None:
            logger.warning("Telegram бот остановлен. Перезапуск...")
            start_telegram_bot()
        
        # Пауза между проверками
        time.sleep(10)

def main():
    """Основная функция"""
    logger.info("=== ЗАПУСК СИСТЕМЫ В РЕЖИМЕ ПОСТОЯННОЙ РАБОТЫ ===")
    
    # Регистрация обработчика сигналов для корректного завершения
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Запуск компонентов
    if not start_web_server():
        logger.error("Не удалось запустить веб-сервер, выход...")
        return
    
    if not start_telegram_bot():
        logger.error("Не удалось запустить Telegram бота, выход...")
        stop_processes()
        return
    
    # Запуск мониторинга процессов в отдельном потоке
    monitor_thread = threading.Thread(target=check_and_restart_processes, daemon=True)
    monitor_thread.start()
    
    logger.info("Система запущена и работает в режиме постоянной работы!")
    
    try:
        # Бесконечный цикл, чтобы держать программу запущенной
        while not should_exit:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)
    finally:
        stop_processes()

if __name__ == "__main__":
    main()