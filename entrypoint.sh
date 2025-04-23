#!/bin/bash

# Скрипт-entrypoint для запуска в режиме постоянной работы
# Этот скрипт запускает и Flask-приложение, и Telegram-бота

# Создаем логи
mkdir -p logs
echo "$(date): Starting services in always-on mode" > logs/entrypoint.log

# Устанавливаем переменные среды для порта
if [ -z "$PORT" ]; then
  # Если переменная PORT не установлена (локальный запуск), используем 5000
  export PORT="5000"
  echo "PORT not set, using default port 5000" >> logs/entrypoint.log
else
  echo "Using provided PORT: $PORT" >> logs/entrypoint.log
fi

# Проверяем, есть ли executable права
if [ ! -x "run_telegram_bot.py" ]; then
  echo "Adding executable permissions to scripts..." >> logs/entrypoint.log
  chmod +x run_telegram_bot.py always_on.py run_always_on.sh
fi

# Создаем директорию для хранения PID
mkdir -p tmp
echo "$(date): Setting up process management" >> logs/entrypoint.log

# Отдельное логирование для Telegram бота
BOT_LOG="logs/telegram_bot_$(date +%Y%m%d_%H%M%S).log"
echo "Bot logs will be saved to: $BOT_LOG" >> logs/entrypoint.log

# Запускаем Telegram бота в фоновом режиме с nohup для обеспечения продолжения работы
echo "Starting Telegram bot..." >> logs/entrypoint.log
nohup python run_telegram_bot.py > "$BOT_LOG" 2>&1 &
BOT_PID=$!
echo "Telegram bot started with PID: $BOT_PID" >> logs/entrypoint.log

# Записываем PID бота в файл для возможного управления позже
echo $BOT_PID > tmp/bot.pid

# Небольшая пауза для инициализации бота
sleep 3

# Проверяем, что бот запустился
if ps -p $BOT_PID > /dev/null; then
  echo "Telegram bot is running with PID: $BOT_PID" >> logs/entrypoint.log
else
  echo "ERROR: Telegram bot failed to start! Trying alternative method..." >> logs/entrypoint.log
  # Альтернативный запуск через python -u для буферизации вывода
  nohup python -u run_telegram_bot.py > "$BOT_LOG" 2>&1 &
  BOT_PID=$!
  echo $BOT_PID > tmp/bot.pid
  echo "Telegram bot started with alternate method, PID: $BOT_PID" >> logs/entrypoint.log
fi

# Пишем информацию о режиме работы
echo "System running in Always-On mode!" >> logs/entrypoint.log
echo "Bot will continue to work even when browser is closed." >> logs/entrypoint.log

# Запуск мониторинга в фоновом режиме
echo "Starting monitoring process..." >> logs/entrypoint.log
nohup python -u health_check.py > logs/monitor.log 2>&1 &
MONITOR_PID=$!
echo $MONITOR_PID > tmp/monitor.pid
echo "Monitoring process started with PID: $MONITOR_PID" >> logs/entrypoint.log

# Запускаем веб-приложение Flask (Gunicorn в foreground режиме)
echo "Starting Flask web application..." >> logs/entrypoint.log
echo "Binding to: 0.0.0.0:$PORT" >> logs/entrypoint.log
exec gunicorn --bind "0.0.0.0:$PORT" --workers 2 --timeout 600 main:app