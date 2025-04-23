#!/bin/bash

# Запуск Telegram бота в фоновом режиме
python run_telegram_bot.py > telegram_bot.log 2>&1 &
TELEGRAM_PID=$!
echo "Telegram bot started with PID: $TELEGRAM_PID"

# Запуск веб-приложения
echo "Starting web application..."
gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app

# При завершении веб-приложения, остановить и Telegram бота
kill $TELEGRAM_PID