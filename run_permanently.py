#!/usr/bin/env python
"""
Скрипт для одновременного запуска веб-приложения и Telegram бота
в режиме постоянной работы (always-on). Специальная версия для Replit Deployment.
"""
import subprocess
import sys
import time
import signal
import os
import logging
import threading
import atexit
from datetime import datetime
import traceback

# Создаем директории для логов и временных файлов
os.makedirs('logs', exist_ok=True)
os.makedirs('tmp', exist_ok=True)

# Настройка логирования
log_file = f'logs/permanently_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger("ReplotDeployment")

# Глобальные переменные для процессов
WEB_PROCESS = None
BOT_PROCESS = None
MONITOR_PROCESS = None
SHOULD_EXIT = False

# Запись диагностической информации
logger.info("=" * 70)
logger.info(f"Запуск контроллера Always On: {datetime.now()}")
logger.info(f"Python версия: {sys.version}")
logger.info(f"Текущая директория: {os.getcwd()}")
logger.info(f"Переменные окружения: PORT={os.environ.get('PORT', 'не установлен')}")
logger.info("=" * 70)

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения работы"""
    global SHOULD_EXIT
    SHOULD_EXIT = True
    logger.info(f"Получен сигнал {sig}, останавливаю процессы...")
    stop_all_processes()
    sys.exit(0)

def on_exit():
    """Функция, выполняемая при завершении работы скрипта"""
    logger.info("Завершение работы скрипта, очистка...")
    stop_all_processes()

def stop_process(process, name):
    """Остановка отдельного процесса"""
    if not process:
        return None
        
    logger.info(f"Останавливаю {name}...")
    try:
        process.terminate()
        try:
            process.wait(timeout=10)
            logger.info(f"{name} остановлен")
        except subprocess.TimeoutExpired:
            logger.warning(f"{name} не остановился после terminate, используем kill")
            process.kill()
            process.wait(timeout=5)
            logger.info(f"{name} принудительно остановлен")
    except Exception as e:
        logger.error(f"Ошибка при остановке {name}: {e}")
        try:
            process.kill()
            logger.info(f"{name} принудительно остановлен после ошибки")
        except:
            logger.error(f"Не удалось остановить {name} даже с kill")
            
    return None

def stop_all_processes():
    """Остановка всех запущенных процессов"""
    global WEB_PROCESS, BOT_PROCESS, MONITOR_PROCESS
    
    logger.info("Останавливаю все процессы...")
    
    # Останавливаем в порядке: мониторинг, бот, веб-сервер
    MONITOR_PROCESS = stop_process(MONITOR_PROCESS, "процесс мониторинга")
    BOT_PROCESS = stop_process(BOT_PROCESS, "Telegram бот")
    WEB_PROCESS = stop_process(WEB_PROCESS, "веб-сервер")
    
    logger.info("Все процессы остановлены")

def start_web_server():
    """Запуск веб-сервера Flask с Gunicorn"""
    global WEB_PROCESS
    
    try:
        logger.info("Запуск веб-сервера Flask...")
        port = os.environ.get("PORT", "5000")
        logger.info(f"Используемый порт: {port}")
        
        # Создаем файл для логов
        web_log_path = os.path.join('logs', f'web_server_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        web_log_file = open(web_log_path, 'w')
        
        # Команда запуска с увеличенным timeout
        cmd = ["gunicorn", "--bind", f"0.0.0.0:{port}", "--workers", "2", "--timeout", "600", "main:app"]
        logger.info(f"Команда запуска: {' '.join(cmd)}")
        
        # Запускаем процесс без захвата вывода - это важно для Replit
        WEB_PROCESS = subprocess.Popen(
            cmd,
            stdout=web_log_file,
            stderr=web_log_file,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )
        
        logger.info(f"Веб-сервер запущен с PID: {WEB_PROCESS.pid}")
        
        # Записываем PID в файл
        with open("tmp/web.pid", "w") as pid_file:
            pid_file.write(str(WEB_PROCESS.pid))
        
        # Пауза для инициализации
        time.sleep(3)
        
        # Проверка статуса
        if WEB_PROCESS.poll() is None:
            logger.info("Веб-сервер успешно запущен и работает")
            return True
        else:
            logger.error(f"Веб-сервер завершился сразу после запуска с кодом {WEB_PROCESS.poll()}")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при запуске веб-сервера: {e}")
        logger.error(traceback.format_exc())
        return False

def start_telegram_bot():
    """Запуск Telegram бота"""
    global BOT_PROCESS
    
    try:
        logger.info("Запуск Telegram бота...")
        
        # Создаем файл для логов
        bot_log_path = os.path.join('logs', f'telegram_bot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        bot_log_file = open(bot_log_path, 'w')
        
        # Команда запуска с флагом -u для unbuffered output
        cmd = ["python", "-u", "run_telegram_bot.py"]
        logger.info(f"Команда запуска: {' '.join(cmd)}")
        
        # Запускаем процесс с использованием preexec_fn для создания новой группы процессов
        BOT_PROCESS = subprocess.Popen(
            cmd,
            stdout=bot_log_file,
            stderr=bot_log_file,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )
        
        logger.info(f"Telegram бот запущен с PID: {BOT_PROCESS.pid}")
        
        # Записываем PID в файл
        with open("tmp/bot.pid", "w") as pid_file:
            pid_file.write(str(BOT_PROCESS.pid))
        
        # Пауза для инициализации
        time.sleep(3)
        
        # Проверка статуса
        if BOT_PROCESS.poll() is None:
            logger.info("Telegram бот успешно запущен и работает")
            return True
        else:
            logger.error(f"Telegram бот завершился сразу после запуска с кодом {BOT_PROCESS.poll()}")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при запуске Telegram бота: {e}")
        logger.error(traceback.format_exc())
        return False

def start_monitoring():
    """Запуск процесса мониторинга"""
    global MONITOR_PROCESS
    
    try:
        logger.info("Запуск процесса мониторинга...")
        
        # Создаем файл для логов
        monitor_log_path = os.path.join('logs', f'monitor_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        monitor_log_file = open(monitor_log_path, 'w')
        
        # Команда запуска
        cmd = ["python", "-u", "health_check.py"]
        logger.info(f"Команда запуска: {' '.join(cmd)}")
        
        # Запускаем процесс
        MONITOR_PROCESS = subprocess.Popen(
            cmd,
            stdout=monitor_log_file,
            stderr=monitor_log_file,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )
        
        logger.info(f"Процесс мониторинга запущен с PID: {MONITOR_PROCESS.pid}")
        
        # Записываем PID в файл
        with open("tmp/monitor.pid", "w") as pid_file:
            pid_file.write(str(MONITOR_PROCESS.pid))
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при запуске процесса мониторинга: {e}")
        logger.error(traceback.format_exc())
        return False

def check_process_status(process, name):
    """Проверка статуса процесса"""
    if not process:
        logger.warning(f"Процесс {name} не существует")
        return False
    
    # Проверяем статус процесса
    status = process.poll()
    
    if status is None:
        # Процесс всё ещё выполняется
        return True
    else:
        logger.warning(f"Процесс {name} остановился с кодом {status}")
        return False

def process_watchdog():
    """Мониторинг процессов и их перезапуск при необходимости"""
    global WEB_PROCESS, BOT_PROCESS, MONITOR_PROCESS, SHOULD_EXIT
    
    logger.info("Запуск системы мониторинга процессов")
    
    last_status_time = 0
    
    while not SHOULD_EXIT:
        try:
            # Проверяем статус мониторинга
            if not check_process_status(MONITOR_PROCESS, "Процесс мониторинга"):
                logger.warning("Перезапуск процесса мониторинга...")
                start_monitoring()
            
            # Проверяем статус бота
            if not check_process_status(BOT_PROCESS, "Telegram бот"):
                logger.warning("Перезапуск Telegram бота...")
                BOT_PROCESS = stop_process(BOT_PROCESS, "Telegram бот (перед перезапуском)")
                start_telegram_bot()
            
            # Проверяем статус веб-сервера
            if not check_process_status(WEB_PROCESS, "Веб-сервер"):
                logger.warning("Перезапуск веб-сервера...")
                WEB_PROCESS = stop_process(WEB_PROCESS, "Веб-сервер (перед перезапуском)")
                start_web_server()
            
            # Логирование статуса каждые 5 минут
            current_time = int(time.time())
            if current_time - last_status_time >= 300:  # каждые 5 минут
                web_status = "Работает" if check_process_status(WEB_PROCESS, "Веб-сервер") else "Остановлен"
                bot_status = "Работает" if check_process_status(BOT_PROCESS, "Telegram бот") else "Остановлен"
                monitor_status = "Работает" if check_process_status(MONITOR_PROCESS, "Процесс мониторинга") else "Остановлен"
                
                logger.info(f"Статус: Веб-сервер: {web_status}, Telegram бот: {bot_status}, Мониторинг: {monitor_status}")
                last_status_time = current_time
                
            # Проверка каждые 30 секунд
            time.sleep(30)
            
        except Exception as e:
            logger.error(f"Ошибка в системе мониторинга: {e}")
            logger.error(traceback.format_exc())
            time.sleep(60)  # Увеличиваем паузу в случае ошибки

def main():
    """Основная функция"""
    global SHOULD_EXIT
    
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Регистрируем функцию, которая будет выполнена при выходе
    atexit.register(on_exit)
    
    logger.info("=" * 70)
    logger.info("ЗАПУСК ПРОЕКТА В РЕЖИМЕ ПОСТОЯННОЙ РАБОТЫ ДЛЯ REPLIT DEPLOYMENT")
    logger.info("=" * 70)
    
    # Даем права на выполнение скриптам
    try:
        os.system("chmod +x run_telegram_bot.py health_check.py")
        logger.info("Выданы права на выполнение скриптам")
    except Exception as e:
        logger.error(f"Ошибка при выдаче прав: {e}")
    
    # Запуск всех компонентов
    
    # 1. Запуск веб-сервера
    logger.info("Шаг 1: Запуск веб-сервера")
    web_ok = start_web_server()
    if not web_ok:
        logger.error("Не удалось запустить веб-сервер, повторная попытка через 5 секунд...")
        time.sleep(5)
        web_ok = start_web_server()
        if not web_ok:
            logger.error("Вторая попытка запуска веб-сервера также не удалась!")
            # Не выходим, пробуем продолжить запуск других компонентов
    
    # 2. Запуск Telegram бота
    logger.info("Шаг 2: Запуск Telegram бота")
    bot_ok = start_telegram_bot()
    if not bot_ok:
        logger.error("Не удалось запустить Telegram бота, повторная попытка через 5 секунд...")
        time.sleep(5)
        bot_ok = start_telegram_bot()
        if not bot_ok:
            logger.error("Вторая попытка запуска Telegram бота также не удалась!")
            # Не выходим, пробуем продолжить запуск других компонентов
    
    # 3. Запуск мониторинга
    logger.info("Шаг 3: Запуск системы мониторинга")
    monitor_ok = start_monitoring()
    if not monitor_ok:
        logger.error("Не удалось запустить мониторинг, повторная попытка через 5 секунд...")
        time.sleep(5)
        monitor_ok = start_monitoring()
        if not monitor_ok:
            logger.error("Вторая попытка запуска мониторинга также не удалась!")
            # Не выходим, продолжаем работу
    
    # Запуск мониторинга процессов в отдельном потоке
    logger.info("Запуск watchdog-процесса для мониторинга всех компонентов")
    watchdog_thread = threading.Thread(target=process_watchdog, daemon=True)
    watchdog_thread.start()
    
    # Готово! Выводим информацию о запущенных сервисах
    logger.info("=" * 70)
    logger.info("СИСТЕМА УСПЕШНО ЗАПУЩЕНА!")
    logger.info(f"Веб-сервер: {'запущен' if web_ok else 'ОШИБКА ЗАПУСКА'}")
    logger.info(f"Telegram бот: {'запущен' if bot_ok else 'ОШИБКА ЗАПУСКА'}")
    logger.info(f"Мониторинг: {'запущен' if monitor_ok else 'ОШИБКА ЗАПУСКА'}")
    logger.info("=" * 70)
    logger.info("Система будет работать постоянно, даже при закрытии браузера.")
    logger.info("Для остановки сервисов нажмите Ctrl+C или отключите Always On в настройках Replit.")
    
    try:
        # Бесконечный цикл для поддержания работы программы
        while not SHOULD_EXIT:
            time.sleep(10)  # Проверка каждые 10 секунд
            
            # Запись информации о работе в лог-файл раз в час (для контроля непрерывности работы)
            current_hour = datetime.now().hour
            current_minute = datetime.now().minute
            
            if current_minute == 0:  # В начале каждого часа
                logger.info(f"Контрольная точка: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - система работает")
                
    except KeyboardInterrupt:
        logger.info("Получена команда остановки (Ctrl+C)")
    except Exception as e:
        logger.error(f"Неожиданная ошибка в основном цикле: {e}")
        logger.error(traceback.format_exc())
    finally:
        # Остановка всех процессов при выходе
        logger.info("Завершение работы скрипта")
        stop_all_processes()
        logger.info("Работа завершена")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())