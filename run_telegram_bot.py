#!/usr/bin/env python
"""
Скрипт для запуска Telegram бота в отдельном процессе.
Используется для запуска бота через Replit workflow.
"""
import asyncio
import logging
import time
import sys
import os
from datetime import datetime, timedelta

# Проверим и создадим директорию для логов если ее нет
logs_dir = "logs"
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

# Имя файла лога с датой и временем
log_filename = os.path.join(logs_dir, f"telegram_bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Настройка расширенного логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_filename)
    ]
)
logger = logging.getLogger(__name__)

# Добавим диагностику московского времени
async def check_moscow_time():
    """Логирует московское время каждую минуту"""
    try:
        from bot import get_moscow_time
        
        while True:
            # Получаем разные варианты времени для сравнения
            utc_now = datetime.utcnow()
            moscow_calc = utc_now + timedelta(hours=3)
            
            try:
                moscow_time = get_moscow_time()
                logger.info(f"Московское время (из функции): {moscow_time.strftime('%Y-%m-%d %H:%M:%S')}")
            except Exception as e:
                logger.error(f"Ошибка при получении московского времени: {e}")
                moscow_time = moscow_calc
            
            logger.info(f"UTC: {utc_now.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"Москва (расчет): {moscow_calc.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Проверяем активные времена рассылки из базы данных
            try:
                from bot import get_all_send_times
                send_times = get_all_send_times()
                time_strings = [t.strftime('%H:%M') for t in send_times]
                logger.info(f"Настроенные времена рассылки: {', '.join(time_strings)}")
                
                # Проверяем близость ко времени отправки
                current_time = moscow_time.time()
                for send_time in send_times:
                    current_minutes = current_time.hour * 60 + current_time.minute
                    target_minutes = send_time.hour * 60 + send_time.minute
                    diff = abs(current_minutes - target_minutes)
                    
                    if diff <= 5:  # Если до отправки меньше 5 минут
                        logger.info(f"ВНИМАНИЕ: Приближается время отправки {send_time.strftime('%H:%M')}, осталось {diff} мин.")
            except Exception as e:
                logger.error(f"Ошибка при проверке времен отправки: {e}")
            
            # Проверяем каждую минуту
            await asyncio.sleep(60)
    except Exception as e:
        logger.error(f"Ошибка в мониторинге времени: {e}")

async def main():
    """Основная функция для запуска бота"""
    try:
        logger.info("=== ЗАПУСК TELEGRAM БОТА ===")
        logger.info(f"Логи сохраняются в файл: {log_filename}")
        logger.info(f"Текущее системное время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Запускаем проверку московского времени в отдельной задаче
        time_task = asyncio.create_task(check_moscow_time())
        
        # Импортируем запуск бота
        from bot import main as bot_main
        
        # Запускаем бота
        logger.info("Запуск основной функции Telegram бота...")
        bot_task = asyncio.create_task(bot_main())
        
        # Ждем завершения обеих задач
        await asyncio.gather(time_task, bot_task)
        
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
        # В случае ошибки ждем и пробуем перезапустить
        time.sleep(5)
        logger.info("Перезапуск бота...")
        await main()

if __name__ == "__main__":
    # Запускаем бота
    asyncio.run(main())