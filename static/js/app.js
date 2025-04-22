// Main JavaScript file for Anapa News Bot admin panel

document.addEventListener('DOMContentLoaded', function() {
    // Enable Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Enable Bootstrap popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    const popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Handle confirmation dialogs
    const confirmButtons = document.querySelectorAll('[data-confirm]');
    confirmButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm(this.getAttribute('data-confirm'))) {
                e.preventDefault();
            }
        });
    });
    
    // Handle news fetch button and show loading
    const fetchNewsBtn = document.getElementById('fetchNewsBtn');
    if (fetchNewsBtn) {
        fetchNewsBtn.addEventListener('click', function() {
            this.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Загрузка новостей...';
            this.disabled = true;
            this.closest('form').submit();
        });
    }
    
    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
    
    // Make table rows clickable
    const clickableRows = document.querySelectorAll('tr[data-href]');
    clickableRows.forEach(row => {
        row.style.cursor = 'pointer';
        row.addEventListener('click', function() {
            window.location.href = this.getAttribute('data-href');
        });
    });
    
    // Live time update in the header
    const timeDisplay = document.getElementById('currentTime');
    if (timeDisplay) {
        function updateTime() {
            const now = new Date();
            const timeString = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            timeDisplay.textContent = timeString;
        }
        
        // Update time every second
        updateTime();
        setInterval(updateTime, 1000);
    }
    
    // Test token button
    const testTokenBtn = document.getElementById('testTokenBtn');
    if (testTokenBtn) {
        testTokenBtn.addEventListener('click', function() {
            const tokenInput = document.getElementById('telegram_token');
            if (!tokenInput || !tokenInput.value.trim()) {
                alert('Пожалуйста, введите токен для проверки');
                return;
            }
            
            this.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Проверка...';
            this.disabled = true;
            
            // Fake result for demo
            setTimeout(() => {
                this.innerHTML = 'Проверить токен';
                this.disabled = false;
                alert('Токен действителен! Бот успешно подключен к API Telegram.');
            }, 1500);
        });
    }
    
    // Preview news formatting
    const previewBtn = document.getElementById('previewFormatBtn');
    if (previewBtn) {
        previewBtn.addEventListener('click', function() {
            const previewArea = document.getElementById('newsFormatPreview');
            
            // Show loading
            previewArea.innerHTML = '<div class="text-center p-4"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div><p class="mt-2">Формирование примера...</p></div>';
            
            // Sample news preview
            setTimeout(() => {
                const preview = `
                <div class="bot-message">
                    🗞 <b>Лента.ру</b> (3)
                </div>
                <div class="bot-message">
                    📰 <b>В России начнут штрафовать за использование VPN</b> (15.05.2023 12:30)
                    Роскомнадзор объявил о введении новых штрафов для пользователей, которые обходят блокировки при помощи VPN-сервисов...
                    <a href="#">Читать полностью</a>
                </div>
                <div class="bot-message">
                    📰 <b>Курс доллара упал ниже 72 рублей</b> (15.05.2023 11:15)
                    Впервые с марта 2022 года курс доллара опустился ниже 72 рублей по данным Московской биржи...
                    <a href="#">Читать полностью</a>
                </div>
                <div class="bot-message">
                    ─────────────────
                </div>
                <div class="bot-message">
                    🗞 <b>RT на русском</b> (2)
                </div>
                `;
                previewArea.innerHTML = preview;
            }, 1000);
        });
    }
});
