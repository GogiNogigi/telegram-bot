#!/bin/bash

# Скрипт-entrypoint для запуска в режиме постоянной работы
# Использует специальный контроллер Always On для управления всеми процессами

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

# Выдаем права на выполнение всем необходимым скриптам
echo "Setting executable permissions on scripts..." >> logs/entrypoint.log
chmod +x run_telegram_bot.py always_on.py run_always_on.sh health_check.py replit_always_on_controller.py

# Создаем необходимые директории
mkdir -p logs tmp
echo "Created necessary directories" >> logs/entrypoint.log

# Запускаем специальный контроллер для Always On
echo "Starting Replit Always On Controller..." >> logs/entrypoint.log
exec python replit_always_on_controller.py