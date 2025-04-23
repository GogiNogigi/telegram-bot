#!/usr/bin/env python
"""
Скрипт для запуска Telegram бота в отдельном процессе.
Используется для запуска бота через Replit workflow.
"""
import asyncio
import logging
import time
import sys

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def main():
    """Основная функция для запуска бота"""
    try:
        # Импортируем запуск бота
        from bot import main as bot_main
        
        # Запускаем бота
        logger.info("Запуск Telegram бота...")
        await bot_main()
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        # В случае ошибки ждем и пробуем перезапустить
        time.sleep(5)
        logger.info("Перезапуск бота...")
        await main()

if __name__ == "__main__":
    # Запускаем бота
    asyncio.run(main())