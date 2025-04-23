#!/bin/bash

# Скрипт-entrypoint для запуска в режиме постоянной работы
# Этот скрипт запускает и Flask-приложение, и Telegram-бота

# Создаем логи
mkdir -p logs
echo "$(date): Starting services in always-on mode" > logs/entrypoint.log

# Запускаем Telegram бота в фоновом режиме 
echo "Starting Telegram bot..." >> logs/entrypoint.log
python run_telegram_bot.py > logs/telegram_bot.log 2>&1 &
BOT_PID=$!
echo "Telegram bot started with PID: $BOT_PID" >> logs/entrypoint.log

# Записываем PID бота в файл для возможного управления позже
echo $BOT_PID > bot.pid

# Небольшая пауза для инициализации бота
sleep 2

# Запускаем веб-приложение Flask (Gunicorn в foreground режиме)
echo "Starting Flask web application..." >> logs/entrypoint.log
exec gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 main:app