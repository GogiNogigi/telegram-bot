#!/usr/bin/env python
"""
Специальный сервер для поддержания работы в режиме Always On
Это запасной метод для гарантированной работы
"""
from flask import Flask, jsonify
import threading
import os
import time
import subprocess
import logging
import sys
from datetime import datetime

# Настройка логирования
os.makedirs('logs', exist_ok=True)
log_file = os.path.join('logs', f'server_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ServerAlwaysOn")

app = Flask(__name__)

# Глобальные переменные для процессов
keep_alive_process = None

@app.route('/')
def home():
    """Домашняя страница для проверки работоспособности"""
    return jsonify({
        "status": "ok",
        "message": "Replit Always On Server работает",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/health')
def health():
    """Endpoint для проверки работоспособности"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "process_running": keep_alive_process is not None and keep_alive_process.poll() is None
    })

def start_keep_alive():
    """Запустить keep_alive.py в отдельном процессе"""
    global keep_alive_process
    
    try:
        logger.info("Запуск процесса keep_alive.py...")
        
        # Закрываем предыдущий процесс, если он существует
        if keep_alive_process is not None:
            try:
                keep_alive_process.terminate()
                keep_alive_process.wait(timeout=5)
            except:
                pass
        
        # Открываем файл для логов
        keep_alive_log = os.path.join('logs', f'keep_alive_proc_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        log_file = open(keep_alive_log, 'w')
        
        # Запускаем процесс
        keep_alive_process = subprocess.Popen(
            ["python", "-u", "keep_alive.py"],
            stdout=log_file,
            stderr=log_file,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )
        
        logger.info(f"Процесс keep_alive запущен с PID: {keep_alive_process.pid}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при запуске keep_alive: {e}")
        return False

def monitor_keep_alive():
    """Мониторинг процесса keep_alive.py и его перезапуск при необходимости"""
    global keep_alive_process
    
    logger.info("Запуск мониторинга процесса keep_alive...")
    
    while True:
        try:
            # Если процесс не запущен или завершился, перезапускаем его
            if keep_alive_process is None or keep_alive_process.poll() is not None:
                logger.warning("Процесс keep_alive не работает, перезапуск...")
                start_keep_alive()
            
            # Пауза между проверками
            time.sleep(300)  # Проверка каждые 5 минут
            
        except Exception as e:
            logger.error(f"Ошибка в мониторинге keep_alive: {e}")
            time.sleep(60)

if __name__ == "__main__":
    # Запускаем процесс keep_alive.py
    start_keep_alive()
    
    # Запускаем мониторинг в отдельном потоке
    monitor_thread = threading.Thread(target=monitor_keep_alive, daemon=True)
    monitor_thread.start()
    
    # Запускаем Flask-сервер
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)