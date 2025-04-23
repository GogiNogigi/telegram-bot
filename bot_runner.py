"""
Модуль для автоматического запуска и остановки бота Telegram
с использованием контекста Flask приложения.
"""
import threading
import asyncio
import signal
import logging
import time
import os
from asyncio import AbstractEventLoop

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Флаг для контроля работы бота
bot_running = False
bot_thread = None
bot_loop = None

def start_bot_thread():
    """Запуск бота в отдельном потоке"""
    global bot_thread, bot_running, bot_loop
    
    if bot_running:
        logger.info("Бот уже запущен")
        return
    
    logger.info("Запуск Telegram бота в отдельном потоке...")
    bot_running = True
    
    # Создание потока для запуска бота
    bot_thread = threading.Thread(target=run_bot_async_with_loop)
    bot_thread.daemon = True  # Поток завершится вместе с основным приложением
    bot_thread.start()
    
    logger.info("Telegram бот запущен")

def run_bot_async_with_loop():
    """Запуск асинхронного бота в новом event loop"""
    global bot_loop
    
    try:
        # Необходимо импортировать внутри функции, чтобы избежать циклических импортов
        import bot
        from bot import main
        
        # Создание нового event loop для асинхронного бота
        bot_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(bot_loop)
        
        # Запуск функции main() бота
        logger.info("Запуск основной функции бота...")
        bot_loop.run_until_complete(main())
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        logger.info("Завершение работы бота")
        bot_running = False
        if bot_loop:
            bot_loop.close()

def stop_bot():
    """Остановка бота"""
    global bot_running, bot_loop
    
    if not bot_running:
        logger.info("Бот не запущен")
        return
    
    logger.info("Остановка Telegram бота...")
    bot_running = False
    
    # Отправка сигнала завершения в event loop бота
    if bot_loop:
        asyncio.run_coroutine_threadsafe(shutdown_bot(), bot_loop)
        time.sleep(2)  # Даем время на корректное завершение
    
    logger.info("Telegram бот остановлен")

async def shutdown_bot():
    """Корректное завершение работы бота"""
    try:
        # Импортируем объекты бота
        from bot import bot, dp
        
        # Останавливаем диспетчер и закрываем сессию бота
        await dp.stop_polling()
        await bot.session.close()
    except Exception as e:
        logger.error(f"Ошибка при завершении работы бота: {e}")

# Регистрация обработчиков сигналов для корректного завершения работы при остановке приложения
def register_signal_handlers():
    """Регистрация обработчиков сигналов для корректного завершения"""
    def signal_handler(sig, frame):
        logger.info(f"Получен сигнал {sig}, завершение работы...")
        stop_bot()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

# Автоматический запуск и регистрация при импорте модуля
register_signal_handlers()