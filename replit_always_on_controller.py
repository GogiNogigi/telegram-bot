#!/usr/bin/env python3
"""
Специальный контроллер Always On для Replit
Этот скрипт гарантирует, что и Telegram бот, и веб-приложение 
будут работать постоянно, даже при закрытии браузера.
"""
import os
import sys
import time
import signal
import logging
import subprocess
import threading
import atexit

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/always_on_controller.log")
    ]
)
logger = logging.getLogger("AlwaysOnController")

# Глобальные переменные для процессов
WEB_PROCESS = None
BOT_PROCESS = None
MONITOR_PROCESS = None
SHOULD_EXIT = False

def ensure_directory(path):
    """Убедиться, что директория существует"""
    if not os.path.exists(path):
        os.makedirs(path)
        logger.info(f"Создана директория: {path}")

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения"""
    global SHOULD_EXIT
    SHOULD_EXIT = True
    logger.info("Получен сигнал завершения, останавливаю процессы...")
    stop_all_processes()
    sys.exit(0)

def stop_process(process, name):
    """Остановить отдельный процесс"""
    if process:
        logger.info(f"Останавливаю {name}...")
        try:
            process.terminate()
            process.wait(timeout=5)
            logger.info(f"{name} успешно остановлен")
        except Exception as e:
            logger.error(f"Ошибка при остановке {name}: {e}")
            try:
                process.kill()
                logger.info(f"{name} принудительно остановлен (kill)")
            except Exception as e2:
                logger.error(f"Не удалось принудительно остановить {name}: {e2}")
    return None

def stop_all_processes():
    """Остановка всех запущенных процессов"""
    global WEB_PROCESS, BOT_PROCESS, MONITOR_PROCESS
    
    # Сначала останавливаем мониторинг
    MONITOR_PROCESS = stop_process(MONITOR_PROCESS, "процесс мониторинга")
    
    # Затем останавливаем бота
    BOT_PROCESS = stop_process(BOT_PROCESS, "Telegram бот")
    
    # В последнюю очередь останавливаем веб-сервер
    WEB_PROCESS = stop_process(WEB_PROCESS, "веб-сервер")
    
    logger.info("Все процессы остановлены")

def start_telegram_bot():
    """Запуск Telegram бота"""
    global BOT_PROCESS
    
    try:
        logger.info("Запуск Telegram бота...")
        cmd = ["python", "-u", "run_telegram_bot.py"]
        logger.info(f"Команда: {' '.join(cmd)}")
        
        bot_log_file = open("logs/telegram_bot.log", "a")
        
        BOT_PROCESS = subprocess.Popen(
            cmd,
            stdout=bot_log_file,
            stderr=subprocess.STDOUT,
            text=True
        )
        logger.info(f"Telegram бот запущен с PID: {BOT_PROCESS.pid}")
        
        # Записываем PID в файл
        with open("tmp/bot.pid", "w") as pid_file:
            pid_file.write(str(BOT_PROCESS.pid))
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при запуске Telegram бота: {e}")
        return False

def start_web_server():
    """Запуск веб-сервера Flask"""
    global WEB_PROCESS
    
    try:
        logger.info("Запуск веб-сервера Flask...")
        port = os.environ.get("PORT", "5000")
        cmd = ["gunicorn", "--bind", f"0.0.0.0:{port}", "--workers", "2", "main:app"]
        logger.info(f"Команда: {' '.join(cmd)}")
        
        web_log_file = open("logs/web_server.log", "a")
        
        WEB_PROCESS = subprocess.Popen(
            cmd,
            stdout=web_log_file,
            stderr=subprocess.STDOUT,
            text=True
        )
        logger.info(f"Веб-сервер запущен с PID: {WEB_PROCESS.pid}")
        
        # Записываем PID в файл
        with open("tmp/web.pid", "w") as pid_file:
            pid_file.write(str(WEB_PROCESS.pid))
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при запуске веб-сервера: {e}")
        return False

def start_monitoring():
    """Запуск процесса мониторинга"""
    global MONITOR_PROCESS
    
    try:
        logger.info("Запуск процесса мониторинга...")
        cmd = ["python", "-u", "health_check.py"]
        logger.info(f"Команда: {' '.join(cmd)}")
        
        monitor_log_file = open("logs/monitor.log", "a")
        
        MONITOR_PROCESS = subprocess.Popen(
            cmd,
            stdout=monitor_log_file,
            stderr=subprocess.STDOUT,
            text=True
        )
        logger.info(f"Процесс мониторинга запущен с PID: {MONITOR_PROCESS.pid}")
        
        # Записываем PID в файл
        with open("tmp/monitor.pid", "w") as pid_file:
            pid_file.write(str(MONITOR_PROCESS.pid))
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при запуске процесса мониторинга: {e}")
        return False

def check_process_status(process, name):
    """Проверка статуса процесса"""
    if not process:
        return False
    
    # Проверяем статус процесса
    status = process.poll()
    
    if status is None:
        # Процесс всё ещё выполняется
        return True
    else:
        logger.warning(f"{name} остановился с кодом {status}")
        return False

def process_watchdog():
    """Мониторинг процессов и их перезапуск при необходимости"""
    global WEB_PROCESS, BOT_PROCESS, MONITOR_PROCESS, SHOULD_EXIT
    
    while not SHOULD_EXIT:
        try:
            # Проверяем статус мониторинга
            if not check_process_status(MONITOR_PROCESS, "Процесс мониторинга"):
                logger.warning("Перезапуск процесса мониторинга...")
                start_monitoring()
            
            # Проверяем статус бота
            if not check_process_status(BOT_PROCESS, "Telegram бот"):
                logger.warning("Перезапуск Telegram бота...")
                start_telegram_bot()
            
            # Проверяем статус веб-сервера
            if not check_process_status(WEB_PROCESS, "Веб-сервер"):
                logger.warning("Перезапуск веб-сервера...")
                start_web_server()
            
            # Логирование статуса каждые 5 минут
            current_time = int(time.time())
            if current_time % 300 < 5:  # каждые 5 минут
                web_status = "Работает" if check_process_status(WEB_PROCESS, "Веб-сервер") else "Остановлен"
                bot_status = "Работает" if check_process_status(BOT_PROCESS, "Telegram бот") else "Остановлен"
                monitor_status = "Работает" if check_process_status(MONITOR_PROCESS, "Процесс мониторинга") else "Остановлен"
                
                logger.info(f"Статус процессов: Веб-сервер: {web_status}, Telegram бот: {bot_status}, Мониторинг: {monitor_status}")
                
            # Пауза перед следующей проверкой
            time.sleep(30)
            
        except Exception as e:
            logger.error(f"Ошибка в watchdog: {e}")
            time.sleep(60)  # Увеличиваем паузу в случае ошибки

def main():
    """Основная функция"""
    global SHOULD_EXIT
    
    # Создаем необходимые директории
    ensure_directory("logs")
    ensure_directory("tmp")
    
    # Выводим информацию о запуске
    logger.info("=" * 80)
    logger.info("ЗАПУСК КОНТРОЛЛЕРА ALWAYS ON ДЛЯ REPLIT")
    logger.info("=" * 80)
    
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Регистрируем функцию очистки при выходе
    atexit.register(stop_all_processes)
    
    # Запускаем компоненты
    bot_ok = start_telegram_bot()
    if not bot_ok:
        logger.error("Не удалось запустить Telegram бота. Попробуем ещё раз...")
        time.sleep(5)
        bot_ok = start_telegram_bot()
        if not bot_ok:
            logger.error("Повторная попытка запуска Telegram бота не удалась.")
    
    web_ok = start_web_server()
    if not web_ok:
        logger.error("Не удалось запустить веб-сервер. Попробуем ещё раз...")
        time.sleep(5)
        web_ok = start_web_server()
        if not web_ok:
            logger.error("Повторная попытка запуска веб-сервера не удалась.")
    
    monitor_ok = start_monitoring()
    if not monitor_ok:
        logger.error("Не удалось запустить процесс мониторинга. Попробуем ещё раз...")
        time.sleep(5)
        monitor_ok = start_monitoring()
        if not monitor_ok:
            logger.error("Повторная попытка запуска процесса мониторинга не удалась.")
    
    # Запускаем мониторинг процессов в отдельном потоке
    watchdog_thread = threading.Thread(target=process_watchdog, daemon=True)
    watchdog_thread.start()
    
    logger.info("Контроллер Always On успешно запущен!")
    logger.info("Система настроена для постоянной работы, даже при закрытии браузера.")
    
    try:
        # Основной цикл
        while not SHOULD_EXIT:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Получена команда остановки (Ctrl+C).")
    finally:
        stop_all_processes()
        logger.info("Контроллер Always On завершил работу.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())