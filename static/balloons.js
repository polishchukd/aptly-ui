// Глобальный обработчик плавающих уведомлений (balloons)
(function () {
    var TIMEOUT_MS = 6000;

    function ensureContainer() {
        var container = document.getElementById('balloonContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'balloonContainer';
            container.className = 'balloon-container';
            document.body.appendChild(container);
        }
        return container;
    }

    function setupBalloon(b) {
        // добавить класс отображения
        requestAnimationFrame(function () {
            b.classList.add('show');
        });
        var close = b.querySelector('.balloon-close');
        var timeout = setTimeout(function () {
            b.classList.remove('show');
            setTimeout(function () {
                if (b.parentNode) b.parentNode.removeChild(b);
            }, 300);
        }, TIMEOUT_MS);
        if (close)
            close.addEventListener('click', function () {
                clearTimeout(timeout);
                b.classList.remove('show');
                setTimeout(function () {
                    if (b.parentNode) b.parentNode.removeChild(b);
                }, 220);
            });
    }

    function createBalloon(text, cls) {
        var c = ensureContainer();
        var b = document.createElement('div');
        b.className = 'balloon ' + (cls || 'info');
        b.setAttribute('role', 'status');
        var icon = document.createElement('div');
        icon.className = 'balloon-icon';
        var txt = document.createElement('div');
        txt.className = 'balloon-text';
        txt.textContent = text;
        var close = document.createElement('button');
        close.className = 'balloon-close';
        close.setAttribute('aria-label', 'close');
        close.innerHTML = '\u00d7';
        b.appendChild(icon);
        b.appendChild(txt);
        b.appendChild(close);
        // вставлять в начало контейнера, чтобы новые появились внизу при column-reverse
        if (c.firstChild) c.insertBefore(b, c.firstChild);
        else c.appendChild(b);
        setupBalloon(b);
        return b;
    }

    // Публичный API: показать balloon программно. cls — одна из 'info','success','danger' и т.д.
    window.showBalloon = function (text, cls) {
        return createBalloon(text, cls);
    };

    function init() {
        var container = ensureContainer();
        // обработать уже вставленные сервером balloons (статические в шаблоне)
        var existing = Array.prototype.slice.call(container.querySelectorAll('.balloon'));
        existing.forEach(function (b) {
            setupBalloon(b);
        });

        // обработать контейнеры локального/страницы входа (например, loginBalloonContainer)
        var loginC = document.getElementById('loginBalloonContainer');
        if (loginC) {
            var bs = Array.prototype.slice.call(loginC.querySelectorAll('.balloon'));
            bs.forEach(function (b) {
                setupBalloon(b);
            });
        }

        // обработать плейсхолдер server-message, если он есть
        var server = document.getElementById('server-message');
        if (server) {
            var msg = server.dataset && server.dataset.message ? server.dataset.message : '';
            var cat = server.dataset && server.dataset.category ? server.dataset.category : 'info';
            if (msg) {
                var container2 = ensureContainer();
                // избегать дубликатов: если balloon с тем же текстом уже есть, пропустить создание
                var existingTexts = Array.prototype.slice
                    .call(container2.querySelectorAll('.balloon .balloon-text'))
                    .map(function (t) {
                        return (t.textContent || '').trim();
                    });
                if (existingTexts.indexOf((msg || '').trim()) === -1) {
                    createBalloon(msg, cat);
                }
            }
        }
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
