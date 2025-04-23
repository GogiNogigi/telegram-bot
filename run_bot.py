#!/usr/bin/env python
import subprocess
import os
import sys
import time
import signal
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='bot_launcher.log'
)
logger = logging.getLogger("BotLauncher")

# Путь к файлу бота
BOT_SCRIPT = "bot.py"

def run_bot():
    """Запуск Telegram бота"""
    try:
        logger.info("Запуск Telegram бота...")
        # Запуск процесса бота и перенаправление вывода в файл
        process = subprocess.Popen(
            [sys.executable, BOT_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # Логирование PID процесса
        logger.info(f"Бот запущен с PID: {process.pid}")
        
        # Бесконечный цикл для мониторинга процесса
        while True:
            # Проверка статуса процесса
            if process.poll() is not None:
                logger.error(f"Процесс бота завершился с кодом: {process.returncode}")
                logger.info("Перезапуск бота через 5 секунд...")
                time.sleep(5)
                # Перезапуск бота
                process = subprocess.Popen(
                    [sys.executable, BOT_SCRIPT],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                logger.info(f"Бот перезапущен с PID: {process.pid}")
            
            # Чтение вывода из процесса
            output = process.stdout.readline()
            if output:
                # Запись вывода в файл логов
                logger.info(f"BOT: {output.strip()}")
            
            # Пауза между проверками
            time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("Получен сигнал завершения. Остановка бота...")
        if process.poll() is None:
            process.terminate()
            process.wait()
        logger.info("Бот остановлен")
    
    except Exception as e:
        logger.error(f"Ошибка в работе лаунчера: {e}")
        if 'process' in locals() and process.poll() is None:
            process.terminate()
            process.wait()
        logger.info("Бот остановлен из-за ошибки")

if __name__ == "__main__":
    run_bot()