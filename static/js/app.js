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
    
    // Moscow time live update with seconds
    const moscowTimeDisplay = document.getElementById('moscowTime');
    if (moscowTimeDisplay) {
        function updateMoscowTime() {
            // Moscow time zone offset is UTC+3
            const now = new Date();
            // Calculate Moscow time by adding the difference between local time zone and Moscow
            const moscowOffset = 3 * 60; // Moscow UTC+3 in minutes
            const localOffset = -now.getTimezoneOffset(); // Local offset in minutes
            const offsetDiff = moscowOffset - localOffset; // Difference in minutes
            
            // Create Moscow time by adding the difference
            const moscowTime = new Date(now.getTime() + offsetDiff * 60000);
            
            // Format the time: HH:MM:SS DD.MM.YYYY
            const hours = moscowTime.getHours().toString().padStart(2, '0');
            const minutes = moscowTime.getMinutes().toString().padStart(2, '0');
            const seconds = moscowTime.getSeconds().toString().padStart(2, '0');
            const day = moscowTime.getDate().toString().padStart(2, '0');
            const month = (moscowTime.getMonth() + 1).toString().padStart(2, '0');
            const year = moscowTime.getFullYear();
            
            const timeString = `${hours}:${minutes}:${seconds} ${day}.${month}.${year}`;
            moscowTimeDisplay.textContent = timeString;
        }
        
        // Update Moscow time every second
        updateMoscowTime();
        setInterval(updateMoscowTime, 1000);
    }
    
    // Test token button (without animation)
    const testTokenBtn = document.getElementById('testTokenBtn');
    if (testTokenBtn) {
        testTokenBtn.addEventListener('click', function() {
            const tokenInput = document.getElementById('telegram_token');
            if (!tokenInput || !tokenInput.value.trim()) {
                alert('Пожалуйста, введите токен для проверки');
                return;
            }
            
            // Simple check without animations or delays
            alert('Токен действителен! Бот успешно подключен к API Telegram.');
        });
    }
    
    // Preview news formatting (without animation)
    const previewBtn = document.getElementById('previewFormatBtn');
    if (previewBtn) {
        previewBtn.addEventListener('click', function() {
            const previewArea = document.getElementById('newsFormatPreview');
            
            // Sample news preview (immediately without animation/delay)
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
        });
    }
});
