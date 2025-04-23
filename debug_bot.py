#!/usr/bin/env python3
"""
Скрипт для запуска Telegram бота в отладочном режиме.
Имитирует отправку новостей по московскому времени.
"""
import asyncio
import logging
import sys
import time
from datetime import datetime, timedelta

# Настройка расширенного логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("debug_telegram_bot.log")
    ]
)
logger = logging.getLogger("debug_bot")

# Импортируем get_moscow_time из бота для диагностики
from bot import get_moscow_time

async def check_moscow_time():
    """Проверяет и логирует разницу между локальным и московским временем"""
    while True:
        try:
            # Локальное время
            local_time = datetime.now()
            
            # Московское время через нашу функцию
            moscow_time = get_moscow_time()
            
            # Расчетное московское время (простое смещение +3 часа)
            utc_time = datetime.utcnow()
            calculated_moscow = utc_time + timedelta(hours=3)
            
            # Логируем сравнение времен
            logger.info("----- Диагностика московского времени -----")
            logger.info(f"Локальное время: {local_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"UTC время: {utc_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"Расчетное московское время (UTC+3): {calculated_moscow.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"Московское время (через функцию): {moscow_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Разница в секундах между нашей функцией и прямым расчетом
            diff_seconds = abs((moscow_time - calculated_moscow).total_seconds())
            logger.info(f"Разница между расчетом и функцией: {diff_seconds} сек.")
            logger.info("-------------------------------------------")
            
            # Ждем 1 минуту перед следующей проверкой
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Ошибка при проверке времени: {e}", exc_info=True)
            await asyncio.sleep(10)

async def main():
    """Основная функция для отладки бота"""
    try:
        logger.info("Запуск отладки московского времени...")
        
        # Запускаем параллельные задачи
        time_task = asyncio.create_task(check_moscow_time())
        
        # Импортируем запуск бота
        from bot import main as bot_main
        
        # Запускаем бот в отдельной задаче
        logger.info("Запуск Telegram бота...")
        bot_task = asyncio.create_task(bot_main())
        
        # Ждем завершения задач
        await asyncio.gather(time_task, bot_task)
        
    except Exception as e:
        logger.error(f"Критическая ошибка при отладке: {e}", exc_info=True)

if __name__ == "__main__":
    # Запускаем отладку
    asyncio.run(main())