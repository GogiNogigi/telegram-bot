#!/bin/bash

# Скрипт для одновременного запуска веб-интерфейса и Telegram бота
# Удобен для локального запуска/отладки

echo "Запуск веб-интерфейса и Telegram бота..."

# Создаем директорию для логов, если она не существует
mkdir -p logs

# Определяем текущую дату и время для имен файлов логов
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
WEB_LOG="logs/web_${TIMESTAMP}.log"
BOT_LOG="logs/bot_${TIMESTAMP}.log"

# Запускаем веб-сервер в фоновом режиме
echo "Запуск веб-сервера на порту 5000..."
gunicorn --bind 0.0.0.0:5000 --workers 2 main:app > "$WEB_LOG" 2>&1 &
WEB_PID=$!

# Небольшая пауза для запуска веб-сервера
sleep 2

# Запускаем Telegram бота в фоновом режиме
echo "Запуск Telegram бота..."
python run_telegram_bot.py > "$BOT_LOG" 2>&1 &
BOT_PID=$!

echo "Процессы запущены:"
echo "Веб-сервер (PID: $WEB_PID) - лог: $WEB_LOG"
echo "Telegram бот (PID: $BOT_PID) - лог: $BOT_LOG"

# Сохраняем PIDs в файлы для возможного управления
echo $WEB_PID > web.pid
echo $BOT_PID > bot.pid

echo "Для мониторинга логов используйте:"
echo "Web: tail -f $WEB_LOG"
echo "Bot: tail -f $BOT_LOG"

echo "Нажмите Ctrl+C для завершения работы всех процессов"

# Функция для корректной остановки процессов при завершении
cleanup() {
    echo "Завершение работы процессов..."
    
    if [ -f web.pid ]; then
        WEB_PID=$(cat web.pid)
        if ps -p $WEB_PID > /dev/null; then
            echo "Останавливаю веб-сервер (PID: $WEB_PID)..."
            kill $WEB_PID
        fi
        rm web.pid
    fi
    
    if [ -f bot.pid ]; then
        BOT_PID=$(cat bot.pid)
        if ps -p $BOT_PID > /dev/null; then
            echo "Останавливаю Telegram бота (PID: $BOT_PID)..."
            kill $BOT_PID
        fi
        rm bot.pid
    fi
    
    echo "Все процессы остановлены"
    exit 0
}

# Регистрируем обработчик сигналов для корректного завершения
trap cleanup SIGINT SIGTERM

# Просто ждем бесконечно, пока пользователь не нажмет Ctrl+C
while true; do
    sleep 1
done