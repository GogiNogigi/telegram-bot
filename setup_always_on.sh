#!/bin/bash

# Скрипт для настройки и тестирования режима Always On
# Запускает проект в режиме постоянной работы (даже при закрытии браузера)

echo "=== Настройка режима Always On для Telegram бота и веб-интерфейса ==="
echo ""

# Убедимся, что скрипты имеют права на выполнение
chmod +x always_on.py entrypoint.sh run_both.sh run_monitoring.sh run_telegram_bot.py

# Создаем директорию для логов, если её нет
mkdir -p logs
echo "Директория для логов создана"

# Тестируем запуск в режиме Always On
echo ""
echo "Запуск проекта в режиме Always On..."
echo "Логи будут сохраняться в файл always_on.log"
echo ""
echo "Чтобы остановить работу, нажмите Ctrl+C"
echo ""
echo "Чтобы настроить постоянную работу:"
echo "1. Выполните деплой проекта через кнопку 'Deploy' в интерфейсе Replit"
echo "2. Включите опцию 'Always On' в разделе настроек Deployment"
echo ""
echo "Запуск..."

# Запускаем в режиме Always On
python always_on.py