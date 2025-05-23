# Новостной Telegram Бот для Анапы и Краснодарского края

Этот проект представляет собой систему доставки новостей через Telegram бота с веб-интерфейсом администрирования. Бот собирает новости из различных RSS-источников и отправляет их подписчикам в указанное время по московскому часовому поясу (UTC+3).

## Возможности системы

- **Доставка новостей**: Автоматический сбор и отправка новостей в определенное время
- **Управление подписчиками**: Добавление и удаление подписчиков через Telegram и веб-интерфейс
- **Управление источниками**: Добавление, редактирование и отключение источников новостей
- **Гибкое расписание**: Настройка нескольких времен отправки новостей в течение дня
- **Работа с часовыми поясами**: Корректная работа с московским временем (UTC+3)
- **Непрерывная работа**: Режим Always-On для бесперебойной работы
- **Разделение прав**: Разделение пользователей на обычных и администраторов

## Структура проекта

- `main.py` - Основной файл Flask-приложения с моделями данных
- `bot.py` - Реализация Telegram бота на базе aiogram
- `utils.py` - Вспомогательные функции для работы с новостями
- `run_telegram_bot.py` - Скрипт для запуска Telegram бота в отдельном процессе
- `run_permanently.py` - Скрипт для запуска обоих сервисов в режиме постоянной работы
- `run_both.sh` - Bash-скрипт для удобного запуска и отладки обоих сервисов
- `templates/` - HTML-шаблоны для веб-интерфейса
- `static/` - Статические файлы (CSS, JavaScript)
- `logs/` - Директория с логами

## Инструкции по настройке

1. **Настройка Workflow для Telegram бота**:
   - Следуйте инструкциям в файле [SETUP_TELEGRAM_BOT_WORKFLOW.md](SETUP_TELEGRAM_BOT_WORKFLOW.md)

2. **Настройка режима Always-On**:
   - Следуйте инструкциям в файле [SETUP_ALWAYS_ON.md](SETUP_ALWAYS_ON.md)

## Запуск проекта для разработки

Есть несколько способов запуска проекта:

### 1. Запуск через Replit Workflows (рекомендуется)

- Используйте кнопку ▶️ (Run) для запуска основного workflow
- Для запуска только Telegram бота используйте workflow "Start Telegram Bot"

### 2. Запуск через Bash-скрипт

```bash
./run_both.sh
```

Этот скрипт запустит веб-сервер и Telegram бота одновременно с логированием в отдельные файлы.

### 3. Запуск в режиме постоянной работы

```bash
python run_permanently.py
```

Этот скрипт запустит все сервисы и будет следить за их работой, автоматически перезапуская в случае сбоев.

## Работа с проектом

### Веб-интерфейс администратора

Веб-интерфейс доступен по URL проекта Replit и предоставляет следующие возможности:

- **Главная страница**: Обзор состояния системы
- **Подписчики**: Управление подписчиками Telegram бота
- **Источники**: Управление RSS-источниками новостей
- **Настройки**: Настройка расписания отправки и параметров бота
- **Новости**: Просмотр кэшированных новостей и ручное обновление

### Команды Telegram бота

- `/start` - Начало работы с ботом
- `/новости` - Получить последние новости
- `/подписаться` - Подписаться на рассылку новостей
- `/отписаться` - Отписаться от рассылки
- `/помощь` - Получить справку по командам
- `/информация` - Получить информацию о боте
- `/настройки` - Настройки бота (для администраторов)
- `/статистика` - Получить статистику по подписчикам (для администраторов)
- `/обновить` - Принудительно обновить новости (для администраторов)

## Мониторинг и отладка

### Логи

Все логи сохраняются в директории `logs/`:
- Логи веб-сервера: `logs/web_*.log`
- Логи Telegram бота: `logs/telegram_bot_*.log` и `logs/bot_*.log`
- Логи скрипта постоянной работы: `logs/permanently_*.log`

### Мониторинг процессов

Во время работы скрипта постоянной работы информация о статусе процессов выводится в лог и в консоль каждые 5 минут.

## Разработка и расширение

Проект имеет модульную структуру, что позволяет легко расширять его функциональность:

1. **Добавление новых источников новостей**: Просто добавьте новые URL в веб-интерфейсе
2. **Изменение формата сообщений**: Отредактируйте функцию `format_news_message` в `utils.py`
3. **Добавление новых команд**: Добавьте новые обработчики в `bot.py`

## Создатели

Проект разработан с использованием:
- Flask и Flask-SQLAlchemy для веб-интерфейса
- aiogram для Telegram бота
- feedparser и trafilatura для обработки новостей