#!/bin/bash

# Скрипт для запуска мониторинга состояния сервисов в фоновом режиме

echo "Запуск мониторинга состояния сервисов..."

# Создаем директорию для логов, если она не существует
mkdir -p logs

# Определяем текущую дату и время для имен файлов логов
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
MONITOR_LOG="logs/monitor_${TIMESTAMP}.log"

# Запускаем мониторинг в фоновом режиме
echo "Запуск скрипта мониторинга health_check.py..."
python health_check.py > "$MONITOR_LOG" 2>&1 &
MONITOR_PID=$!

# Сохраняем PID процесса мониторинга
echo $MONITOR_PID > monitor.pid

echo "Мониторинг запущен с PID: $MONITOR_PID"
echo "Логи мониторинга записываются в файл: $MONITOR_LOG"
echo "Для просмотра логов используйте: tail -f $MONITOR_LOG"
echo "Для остановки мониторинга используйте: kill $(cat monitor.pid)"
echo ""
echo "Веб-эндпоинт для проверки состояния: http://localhost:5000/api/health"
echo ""