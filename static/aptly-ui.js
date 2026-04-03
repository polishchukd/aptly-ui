// aptly-ui.js

// =============================
// Разбор переводов, встроенных в страницу как JSON (безопасно для линтеров)
// =============================
try {
    const el = document.getElementById('i18n-data');
    if (el && el.textContent) {
        try { window.I18N = JSON.parse(el.textContent); }
        catch (e) { window.I18N = window.I18N || {}; }
    }
}
catch (e) {}

// =============================
// Функция checkHealth
// Назначение: выполнить ping сервера (бэкенд /health), отобразить текущий
// статус доступности Aptly API в badge (OK / ERROR / проверка…). При ошибке сети
// или отличном от ожидаемого ответе выводит ERROR. Используется при загрузке
// страницы и далее периодически каждые 10 секунд.
// Побочные эффекты: изменяет DOM (текст и класс бейджа #health_api).
// Ошибки: сетевые исключения перехватываются и отображаются как ERROR.
// =============================

function checkHealth() {
    const badge = document.getElementById('health_api');
    badge.textContent = t('msg.api_checking');
    badge.className = 'badge bg-secondary';
    fetch('/health')
        .then((resp) => resp.json())
        .then((data) => {
            if (data.status === 'ok') {
                badge.textContent = t('msg.api_ok');
                badge.className = 'badge bg-success';
            } else {
                badge.textContent = t('msg.api_error');
                badge.className = 'badge bg-danger';
            }
        })
        .catch(() => {
            badge.textContent = t('msg.api_error');
            badge.className = 'badge bg-danger';
        });
}

// Универсальный помощник: объединяет несколько команд единой разделительной строкой
function joinCommands(cmds) {
    if (!cmds || !Array.isArray(cmds)) return '';
    return cmds.filter(Boolean).join('\n-----------------------------\n');
}

// Простой JS-хелпер переводов. Ожидает, что сервер внедрит объект `window.I18N`.
function t(key, def) {
    try { if (window && window.I18N && Object.prototype.hasOwnProperty.call(window.I18N, key)) return window.I18N[key]; }
    catch (e) {}
    return def || key;
}

// =============================
// Основной инициализирующий блок (DOMContentLoaded)
// Назначение: запуск периодического health-check, восстановление активной вкладки,
// настройка обработчиков форм (копирование пакета, удаление, создание),
// инициализация кастомных выпадающих списков, а также логика автоформирования
// curl команд. Содержит вложенные вспомогательные функции.
// =============================
window.addEventListener('DOMContentLoaded', () => {
    // selected repo for delete-repo tab (set by clicking left list)
    let selectedRepoRepo = null;
    // --- Загрузка .deb ---
    const uploadForm = document.getElementById('upload_package_form');
    if (uploadForm) {
    // Хелпер для обновления превью команды загрузки
        function updateUploadCmd() {
            const fileInput = document.getElementById('deb_file');
            const repoInput = document.getElementById('upload_repo');
            const box = document.getElementById('upload_package_api');
            if (!box) return;
            const file = fileInput && fileInput.files && fileInput.files[0];
            const repo = repoInput ? repoInput.value.trim() : '';
            if (!file || !repo) {
                box.textContent = '';
                return;
            }
            const apiBaseRaw = window.API_URL || 'http://localhost:8080';
            const apiBase = String(apiBaseRaw).replace(/\/$/, '');
            const apiPrefix = apiBase.endsWith('/api') ? apiBase : apiBase + '/api';
            // Показываем две команды: загрузка в директорию (используя имя репозитория как плейсхолдер) и импорт из этой директории
            // Нельзя заранее узнать точную timestamp-папку, создаваемую сервером, показываем вероятные команды
            const dirPlaceholder = repo.replace(/[^A-Za-z0-9._-]+/g, '_');
            const uploadCmd = `curl -X POST -F file=@${file.name} ${apiPrefix}/files/${dirPlaceholder}`;
            const importCmd = `curl -X POST ${apiPrefix}/repos/${repo}/file/${dirPlaceholder}`;
            box.textContent = joinCommands([uploadCmd, importCmd]);
        }

    // Привязать поля формы для обновления превью команды и состояния кнопки
    const debFileInput = document.getElementById('deb_file');
    const uploadRepoInput = document.getElementById('upload_repo');
    const uploadSubmitBtn = document.getElementById('upload_package_submit');

    function updateUploadBtnState() {
        if (!uploadSubmitBtn) return;
        const hasFile = debFileInput && debFileInput.files && debFileInput.files.length > 0;
        const hasRepo = uploadRepoInput && uploadRepoInput.value && uploadRepoInput.value.trim() !== '';
        uploadSubmitBtn.disabled = !(hasFile && hasRepo);
    }

    if (debFileInput) debFileInput.addEventListener('change', function () { updateUploadCmd(); updateUploadBtnState(); });
    if (uploadRepoInput) uploadRepoInput.addEventListener('input', function () { updateUploadCmd(); updateUploadBtnState(); });
    // Установить начальное состояние при загрузке
    try { updateUploadBtnState(); }
    catch (e) {}
        uploadForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const fileInput = document.getElementById('deb_file');
            const repoInput = document.getElementById('upload_repo');
            const resultBox = document.getElementById('upload_package_result');
            if (!fileInput || !repoInput || !resultBox) return;
            const file = fileInput.files[0];
            const repo = repoInput.value.trim();
            if (!file || !repo) {
                resultBox.textContent = t('msg.choose_deb_and_repo');
                return;
            }
            // немедленно обновить превью команды
            try { updateUploadCmd(); }
            catch (e) {}
            resultBox.textContent = t('msg.uploading');
            const formData = new FormData();
            formData.append('file', file);
            formData.append('repo', repo);
            fetch('/upload_package', {
                method: 'POST',
                body: formData
            })
            .then(resp => resp.json().then(j => ({ status: resp.status, body: j })))
            .then(({ status, body }) => {
                if (status >= 200 && status < 300 && body && body.status === 'ok') {
                    resultBox.textContent = t('msg.upload_ok');
                    if (body.details) {
                        resultBox.textContent += '\n' + JSON.stringify(body.details, null, 2);
                    }
                    try { if (window.showBalloon) window.showBalloon(t('msg.upload_done'), 'success'); }
                    catch (e) {}
                } else {
                    var errMsg = (body && body.error) ? body.error : t('msg.upload_error');
                    resultBox.textContent = errMsg;
                    try { if (window.showBalloon) window.showBalloon(errMsg, 'danger'); }
                    catch (e) {}
                }
            })
            .catch(err => {
                resultBox.textContent = t('msg.error_prefix') + err;
                try { if (window.showBalloon) window.showBalloon(t('msg.upload_error'), 'danger'); }
                catch (e) {}
            });
        });
    }
    // Гарантировать отображение команд при загрузке страницы
    setTimeout(() => {
        if (typeof updateDeleteRepoCmd === 'function') updateDeleteRepoCmd();
    }, 0);
    checkHealth();
    setInterval(checkHealth, 10000); // каждые 10 секунд

    // Иконка помощи: клик — переключить тултип (для элементов .help-icon с data-help)
    (function setupHelpIcons() {
        function removeTooltip() {
            const existing = document.querySelectorAll('.help-tooltip');
            existing.forEach(e => e.parentNode && e.parentNode.removeChild(e));
        }
        document.addEventListener('click', function (ev) {
            const target = ev.target;
            const icon = target.closest && target.closest('.help-icon');
            if (!icon) {
                // клик вне элемента — удалить любой показанный тултип
                removeTooltip();
                return;
            }
            // Предотвратить активацию <label> (клик по нему откроет связанный контрол, напр. диалог выбора файлов).
            // Остановить действие и распространение при клике по иконке помощи.
            try { ev.preventDefault(); }
            catch (e) {}
            ev.stopPropagation();
            removeTooltip();
            const helpText = icon.getAttribute('data-help') || '';
            if (!helpText) return;
            const tooltip = document.createElement('div');
            tooltip.className = 'help-tooltip';
            tooltip.textContent = helpText;
            document.body.appendChild(tooltip);
            // позиционировать тултип под иконкой
            const r = icon.getBoundingClientRect();
            tooltip.style.left = (r.left + window.scrollX) + 'px';
            tooltip.style.top = (r.bottom + window.scrollY + 8) + 'px';
        });
    })();

    // ===== Сохранение и восстановление активной вкладки =====
    const TAB_STORAGE_KEY = 'aptlyActiveTab';
    // Перед предполагаемой "жёсткой" перезагрузкой (Ctrl+F5 / Ctrl+Shift+R / Cmd+Shift+R / Cmd+R) очищаем сохранённую вкладку
    window.addEventListener('keydown', (e) => {
        const key = e.key.toLowerCase();
        const isHardReloadCombo =
            // Windows/Linux: Ctrl+F5
            (e.ctrlKey && e.key === 'F5') ||
            // Windows/Linux: Ctrl+Shift+R
            (e.ctrlKey && e.shiftKey && key === 'r') ||
            // macOS: Cmd+Shift+R (жёсткое обновление)
            (e.metaKey && e.shiftKey && key === 'r') ||
            // macOS: обычное Cmd+R тоже учитываем
            (e.metaKey && !e.shiftKey && key === 'r');
        if (isHardReloadCombo) {
            try { localStorage.removeItem(TAB_STORAGE_KEY); }
            catch (_) {}
        }
    });
    try {
        const savedTabId = localStorage.getItem(TAB_STORAGE_KEY);
        if (savedTabId) {
            // Если сохраненная вкладка существует – показываем её
            const savedBtn = document.getElementById(savedTabId);
            if (savedBtn && !savedBtn.classList.contains('active')) {
                try { new bootstrap.Tab(savedBtn).show(); }
                catch (e) { savedBtn.click(); }
            }
        }
    }
    catch (e) {
        /* localStorage может быть недоступен (privacy mode) */
    }
    // Подписка на смену вкладок для сохранения
    document.querySelectorAll('#aptlyTab button[data-bs-toggle="tab"]').forEach((btn) => {
        btn.addEventListener('shown.bs.tab', (ev) => {
            try { localStorage.setItem(TAB_STORAGE_KEY, ev.target.id); }
            catch (e) {}
        });
    });
    // =========================================================

    // Обработчик формы копирования пакета
    // Вспомогательная функция fillRepoList вынесена в область DOMContentLoaded
    function fillRepoList(inputId, listId) {
        fetch('/api/repos')
            .then((r) => r.json())
            .then((repos) => {
                const list = document.getElementById(listId);
                if (list) {
                    list.innerHTML = '';
                    (repos || []).forEach((repo) => {
                        const opt = document.createElement('option');
                        opt.value = repo.Name || repo;
                        list.appendChild(opt);
                    });
                    // Если это список для удаления репозитория — вызвать updateDeleteRepoCmd
                    if (listId === 'delete_repo_list' && typeof updateDeleteRepoCmd === 'function') {
                        setTimeout(updateDeleteRepoCmd, 0);
                    }
                }
            })
            .catch(() => {
                /* ignore */
            });
    }
    // Заполнить datalist, если они присутствуют
    fillRepoList('source_repo', 'source_repo_list');
    fillRepoList('target_repo', 'target_repo_list');
    fillRepoList('upload_repo', 'upload_repo_list');

    // Функция формирования команд для удаления репозитория
    function updateDeleteRepoCmd() {
        const forceInput = document.getElementById('delete_repo_force');
        const apiBox = document.getElementById('delete_repo_api');
        const submitBtn = document.getElementById('delete_repo_submit');
        if (!apiBox) return;
        const repoName = selectedRepoRepo || '';
        if (!repoName) {
            apiBox.textContent = '';
            if (submitBtn) submitBtn.disabled = true;
            return;
        }
    const apiBaseRaw = window.API_URL || 'http://localhost:8080';
    const apiBase = String(apiBaseRaw).replace(/\/$/, '');
    const apiPrefix = apiBase.endsWith('/api') ? apiBase : apiBase + '/api';
    console.debug('[delete-repo] updateDeleteRepoCmd repo=', repoName, 'force=', !!(forceInput && forceInput.checked));

        // Попробуем получить publish info (совместимо с логикой targetRepo)
        fetch(`/api/repo_publish_info?repo=${encodeURIComponent(repoName)}`)
            .then((r) => r.json())
            .then((arr) => {
                let publishCmd = '';
                    if (Array.isArray(arr) && arr.length) {
                    const info = arr[0];
                    const prefix = info.Prefix || '';
                    const distribution = info.Distribution || '';
                    if (prefix && distribution) {
                        // Кодирование префикса по правилам Aptly: '_' -> '__' и '/' -> '_'; distribution кодируется для URL
                        const encPrefix = String(prefix).replace(/_/g, '__').replace(/\//g, '_');
                        const encDist = encodeURIComponent(String(distribution || ''));
                        publishCmd = `curl -X DELETE "${apiPrefix}/publish/${encPrefix}/${encDist}`;
                        if (forceInput && forceInput.checked) publishCmd += '?force=1';
                        publishCmd += '"';
                    }
                }
                // Команда удаления репозитория
                const repoCmd = `curl -X DELETE "${apiPrefix}/repos/${repoName}"`;
                apiBox.textContent = publishCmd ? joinCommands([publishCmd, repoCmd]) : repoCmd;
                console.debug('[delete-repo] publishCmd=', publishCmd, 'repoCmd=', repoCmd);
                if (submitBtn) submitBtn.disabled = false;
            })
            .catch(() => {
                // запасной вариант: показать только команду удаления репозитория
                apiBox.textContent = `curl -X DELETE "${apiPrefix}/repos/${repoName}"`;
                console.debug('[delete-repo] fallback repoCmd=', apiBox.textContent);
                if (submitBtn) submitBtn.disabled = false;
            });
    }

    // Подключаем слушатели к полям выбора репозитория и переключателю force
    (function wireDeleteRepoInputs() {
        const force = document.getElementById('delete_repo_force');
        if (force) {
            force.addEventListener('change', updateDeleteRepoCmd);
            force.addEventListener('click', function(){ console.debug('[delete-repo] force clicked, checked=', force.checked); });
        }
    })();

    // Обработка submit формы удаления репозитория: показываем модальное подтверждение
    const deleteRepoForm = document.getElementById('delete_repo_form');
    if (deleteRepoForm) {
        deleteRepoForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const repoName = selectedRepoRepo || '';
            if (!repoName) return;
            const forceInput = document.getElementById('delete_repo_force');
            const body = document.getElementById('delete_modal_body');
            if (body) {
                body.textContent = t('msg.delete_repo_confirm_template').replace('{repo}', repoName);
                if (forceInput && forceInput.checked) {
                    body.textContent += '\n' + t('msg.delete_repo_force_notice');
                }
            }
            const modalEl = document.getElementById('deleteConfirmModal');
            if (modalEl) {
                const pkgBtn = document.getElementById('confirm_delete_pack_btn');
                const repoBtn = document.getElementById('confirm_delete_repo_btn');
                if (pkgBtn) pkgBtn.style.display = 'none';
                if (repoBtn) { repoBtn.style.display = ''; repoBtn.disabled = false; }
                const modal = new bootstrap.Modal(modalEl);
                modal.show();
            }
        });
    }

    // Обработчик подтверждения удаления репозитория (кнопка в модальном окне)
    const confirmRepoBtn = document.getElementById('confirm_delete_repo_btn');
    if (confirmRepoBtn) {
        confirmRepoBtn.addEventListener('click', function () {
            const repoName = selectedRepoRepo || '';
            if (!repoName) return;
            const forceInput = document.getElementById('delete_repo_force');
            const resultBox = document.getElementById('delete_repo_result');
            const submitBtn = document.getElementById('delete_repo_submit');
            if (submitBtn) { submitBtn.disabled = true; submitBtn.style.backgroundColor = '#ffd600'; submitBtn.style.color = '#333'; }
            if (resultBox) resultBox.textContent = t('msg.deleting');

            var progressBalloon = null;
            try { if (window.showBalloon) progressBalloon = window.showBalloon(t('msg.in_progress'), 'info'); }
            catch (e) {}

            fetch('/delete_repo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repo: repoName, force: !!(forceInput && forceInput.checked) })
            })
                .then((resp) => {
                    if (!resp.ok) {
                        return resp.text().then((t) => { throw new Error(`Server error ${resp.status}: ${t}`); });
                    }
                    return resp.json();
                })
                .then((json) => {
                    let out = '';
                    if (json.publish) {
                        out += t('msg.delete_publish_status_prefix') + String(json.publish.status) + '\n' + t('msg.response_prefix') + (typeof json.publish.body === 'object' ? JSON.stringify(json.publish.body, null, 2) : String(json.publish.body)) + '\n\n';
                    }
                    if (json.repo) {
                        out += t('msg.delete_repo_status_prefix') + String(json.repo.status) + '\n' + t('msg.response_prefix') + (typeof json.repo.body === 'object' ? JSON.stringify(json.repo.body, null, 2) : String(json.repo.body)) + '\n';
                    }
                    if (!json.publish && !json.repo && json.error) {
                        out = t('msg.error_prefix') + String(json.error);
                    }
                    if (resultBox) resultBox.textContent = out || t('msg.ready');

                    const opStatus = (obj) => { try { const s = Number(obj && obj.status); return s >= 200 && s < 300; } catch (e) { return false; } };
                    const publishOk = !json.publish || opStatus(json.publish);
                    const repoOk = !json.repo || opStatus(json.repo);

                    if (publishOk && repoOk) {
                        try { if (window.showBalloon) window.showBalloon(t('msg.delete_done'), 'success'); }
                        catch (e) {}
                        try {
                            // Обновить все представления списков репозиториев: datalist'ы и видимые списки
                            fillRepoList('source_repo', 'source_repo_list');
                            fillRepoList('target_repo', 'target_repo_list');
                            fillRepoList('upload_repo', 'upload_repo_list');
                            // Обновить три-колоночный интерфейс и список на вкладке удаления репозитория
                            try { if (typeof refreshRepos === 'function') refreshRepos(); } catch (e) {}
                            try { if (typeof refreshReposForDeleteRepo === 'function') refreshReposForDeleteRepo(); } catch (e) {}
                            selectedRepoRepo = null;
                            if (submitBtn) submitBtn.disabled = true;
                        }
                        catch (e) { console.debug('[delete-repo] refresh lists failed', e); }
                    } else {
                        let brief = t('msg.delete_error_brief');
                        try {
                            const parts = [];
                            if (json.publish && !publishOk) {
                                const body = typeof json.publish.body === 'object' ? JSON.stringify(json.publish.body) : String(json.publish.body);
                                parts.push(`publish ${json.publish.status}: ${body}`);
                            }
                            if (json.repo && !repoOk) {
                                const body = typeof json.repo.body === 'object' ? JSON.stringify(json.repo.body) : String(json.repo.body);
                                parts.push(`repo ${json.repo.status}: ${body}`);
                            }
                            if (parts.length) brief += ': ' + parts.join('; ');
                        }
                        catch (e) { /* ignore */ }
                        try { if (window.showBalloon) window.showBalloon(brief, 'danger'); }
                        catch (e) {}
                    }
                })
                .catch((err) => {
                    if (resultBox) resultBox.textContent = t('msg.delete_repo_error_prefix') + String(err);
                    try { if (window.showBalloon) window.showBalloon(t('msg.delete_error'), 'danger'); }
                    catch (e) {}
                })
                .finally(() => {
                    // убрать прогресс-балун
                    try {
                        if (progressBalloon) { progressBalloon.classList.remove('show'); setTimeout(function () { if (progressBalloon.parentNode) progressBalloon.parentNode.removeChild(progressBalloon); }, 300); }
                    } catch (e) {}

                    // скрыть modal и восстановить кнопки модалки
                    const modalEl = document.getElementById('deleteConfirmModal');
                    if (modalEl) {
                        try { bootstrap.Modal.getInstance(modalEl)?.hide(); } catch (e) {}
                    }
                    const pkgBtn = document.getElementById('confirm_delete_pack_btn');
                    const repoBtn = document.getElementById('confirm_delete_repo_btn');
                    if (pkgBtn) pkgBtn.style.display = '';
                    if (repoBtn) repoBtn.style.display = 'none';

                    // Восстановить состояние кнопки удаления репозитория: включена только если есть выбранный репозиторий
                    try {
                        if (submitBtn) {
                            const shouldEnable = !!selectedRepoRepo;
                            submitBtn.disabled = !shouldEnable;
                            if (!shouldEnable) {
                                // убрать пользовательские inline-стили, чтобы кнопка выглядела серой
                                submitBtn.style.backgroundColor = '';
                                submitBtn.style.color = '';
                            } else {
                                // очистить возможные inline-стили и позволить CSS управлять видом
                                submitBtn.style.backgroundColor = '';
                                submitBtn.style.color = '';
                            }
                        }
                    } catch (e) {}
                });
        });
    }

    const copyForm = document.getElementById('copy_package_form');
    if (copyForm) {
        // Списки дистрибуций по умолчанию пустые до выбора репозитория
        ['source_distribution_list', 'target_distribution_list'].forEach((id) => {
            const list = document.getElementById(id);
            if (list) list.innerHTML = '';
        });

        // --- Автозаполнение пакетов ---
        const sourceRepoEl = document.getElementById('source_repo');
        if (sourceRepoEl) {
            sourceRepoEl.addEventListener('input', function () {
                const repo = sourceRepoEl.value.trim();
                // Очищаем поля "Имя пакета" и "Версия" при смене исходного репозитория
                const pkgEl = document.getElementById('package_name');
                if (pkgEl) {
                    pkgEl.value = '';
                    pkgEl.dispatchEvent(new Event('input'));
                }
                const verEl = document.getElementById('version');
                if (verEl) {
                    verEl.value = '';
                    verEl.dispatchEvent(new Event('input'));
                }
                if (!repo) return;
                // Получить доступные distribution именно для этого репо (publish entries)
                fetch(`/api/repo_distributions?repo=${encodeURIComponent(repo)}`)
                    .then((r) => r.json())
                    .then((dists) => {
                        const list = document.getElementById('source_distribution_list');
                        if (list) {
                            list.innerHTML = '';
                            (dists || []).forEach((d) => {
                                const opt = document.createElement('option');
                                opt.value = d;
                                list.appendChild(opt);
                            });
                        }
                        const sourceDistEl = document.getElementById('source_distribution');
                        if (dists && dists.length === 1 && sourceDistEl) {
                            sourceDistEl.value = dists[0];
                        }
                    })
                    .catch(() => {});
                fetch(`/api/packages?repo=${encodeURIComponent(repo)}`)
                    .then((r) => r.json())
                    .then((pkgs) => {
                        const list = document.getElementById('package_name_list');
                        if (list) {
                            list.innerHTML = '';
                            (pkgs || []).forEach((pkg) => {
                                const opt = document.createElement('option');
                                opt.value = pkg;
                                list.appendChild(opt);
                            });
                            // Если только один пакет, выбрать его автоматически
                            if (pkgs && pkgs.length === 1) {
                                const pkgEl = document.getElementById('package_name');
                                if (pkgEl) {
                                    pkgEl.value = pkgs[0];
                                    pkgEl.dispatchEvent(new Event('input'));
                                }
                            }
                        }
                    })
                    .catch(() => {});
            });
        }
        // Аналогично для целевого репозитория — получить доступные distribution
        const targetRepoEl = document.getElementById('target_repo');
        if (targetRepoEl) {
            targetRepoEl.addEventListener('input', function () {
                const repo = targetRepoEl.value.trim();
                if (!repo) {
                    const list = document.getElementById('target_distribution_list');
                    if (list) list.innerHTML = '';
                    const tp = document.getElementById('target_prefix');
                    if (tp) tp.value = '';
                    return;
                }
                fetch(`/api/repo_distributions?repo=${encodeURIComponent(repo)}`)
                    .then((r) => r.json())
                    .then((dists) => {
                        const list = document.getElementById('target_distribution_list');
                        if (list) {
                            list.innerHTML = '';
                            (dists || []).forEach((d) => {
                                const opt = document.createElement('option');
                                opt.value = d;
                                list.appendChild(opt);
                            });
                        }
                        const targetDistEl = document.getElementById('target_distribution');
                        if (dists && dists.length === 1 && targetDistEl) {
                            targetDistEl.value = dists[0];
                            targetDistEl.dispatchEvent(new Event('input'));
                        }
                    })
                    .catch(() => {});
                // Получить publish info (Prefix + Distribution) для автозаполнения префикса
                fetch(`/api/repo_publish_info?repo=${encodeURIComponent(repo)}`)
                    .then((r) => r.json())
                    .then((arr) => {
                        // Удалить предыдущий блок выбора публикации, если он был
                        const prev = document.getElementById('publish_choice_container');
                        if (prev && prev.parentNode) prev.parentNode.removeChild(prev);

                        let applied = false;
                        const tp = document.getElementById('target_prefix');
                        const targetDistEl = document.getElementById('target_distribution');

                        if (Array.isArray(arr) && arr.length) {
                            // Если есть одна или несколько записей публикации — по умолчанию
                            // применяем первую (Prefix + Distribution). Пользователь всё ещё
                            // может вручную поменять поля target_prefix/target_distribution.
                            const info = arr[0];
                            if (tp) tp.value = info.Prefix || '';
                            if (targetDistEl && info.Distribution) targetDistEl.value = info.Distribution;
                            applied = true;
                        }

                        if (!applied) {
                            const parts = repo.split('-');
                            if (parts.length >= 4 && /\d/.test(parts[2])) {
                                const prefix = parts[0] + '/' + parts[2];
                                if (tp) tp.value = prefix;
                                if (targetDistEl) targetDistEl.value = parts[parts.length - 1];
                            } else {
                                if (tp) tp.value = repo;
                            }
                        }
                        updateCopyCmd();
                    })
                    .catch(() => {
                        updateCopyCmd();
                    });
            });
        }

        // --- Автозаполнение версий ---
        const packageNameEl = document.getElementById('package_name');
        if (packageNameEl) {
            packageNameEl.addEventListener('input', function () {
                const repoEl = document.getElementById('source_repo');
                const repo = repoEl ? repoEl.value.trim() : '';
                const pkg = packageNameEl.value.trim();
                if (!repo || !pkg) return;
                fetch(
                    `/api/versions?repo=${encodeURIComponent(repo)}&package=${encodeURIComponent(pkg)}`
                )
                    .then((r) => r.json())
                    .then((versions) => {
                        const list = document.getElementById('version_list');
                        if (list) {
                            list.innerHTML = '';
                            (versions || []).forEach((ver) => {
                                const opt = document.createElement('option');
                                opt.value = ver;
                                list.appendChild(opt);
                            });
                            if (versions && versions.length === 1) {
                                const vEl = document.getElementById('version');
                                if (vEl) vEl.value = versions[0];
                            }
                            updateCopyCmd();
                        }
                    })
                    .catch(() => {
                        updateCopyCmd();
                    });
            });
        }

    // =============================
    // Функция updateCopyCmd
    // Назначение: динамически построить curl команду для копирования пакета
    // (POST /repos/<target>/packages) и при наличии publish-настроек — команду
    // обновления публикации (PUT /publish/<prefix>/<distribution>). Использует
    // ключ пакета, полученный через /api/package_key. Применяет только явные overrides
    // из полей target_distribution / target_prefix; эвристики не используются.
    // Вывод: текст помещается в #copy_package_api. При неполных данных очищает бокс.
    // Особенности: запрос ключа выполняется асинхронно; при неудаче выводится
    // диагностическое сообщение.
    // =============================
        function updateCopyCmd() {
            const srcEl = document.getElementById('source_repo');
            const tgtEl = document.getElementById('target_repo');
            const pkgEl = document.getElementById('package_name');
            const verEl = document.getElementById('version');
            const src = srcEl ? srcEl.value.trim() : '';
            const tgt = tgtEl ? tgtEl.value.trim() : '';
            const pkg = pkgEl ? pkgEl.value.trim() : '';
            const ver = verEl ? verEl.value.trim() : '';
            const tgtDistOverride = document.getElementById('target_distribution')
                ? document.getElementById('target_distribution').value.trim()
                : '';
            const tgtPrefixOverride = document.getElementById('target_prefix')
                ? document.getElementById('target_prefix').value.trim()
                : '';
            const arch = (window.PUBLISH_ARCH || '').split(',')[0] || '';
            const box = document.getElementById('copy_package_api');
            if (!box) return;
            if (!(src && tgt && pkg && ver)) {
                box.textContent = '';
                return;
            }
            box.textContent = t('msg.forming_command');
            // 1. Получаем ключ пакета через наш вспом. endpoint
            fetch(
                `/api/package_key?repo=${encodeURIComponent(src)}&package=${encodeURIComponent(pkg)}&version=${encodeURIComponent(ver)}${arch ? `&arch=${encodeURIComponent(arch)}` : ''}`
            )
                .then((r) => r.json())
                .then((data) => {
                    if (!data.key) {
                        box.textContent = t('msg.no_package_key');
                        return;
                    }
                    const key = data.key;
                    const apiBase = window.API_URL || '/api';
                    // Официальный copy: POST /api/repos/<target>/packages  {"PackageRefs":["<key>"]}
                    const copyUrl = `${apiBase}/repos/${tgt}/packages`;
                    const payload = { PackageRefs: [key] };
                    let json = JSON.stringify(payload).replace(/'/g, "'\\''");
                    // (Опционально) показать команду получения списка
                    const copyCmd = `curl -X POST -H 'Content-Type: application/json' -d '${json}' ${copyUrl}`;
                    // Использовать только явные переопределения: требовать явные target_prefix и target_distribution
                    const prefixToUse = tgtPrefixOverride || '';
                    const distFinal = tgtDistOverride || '';
                    if (distFinal && prefixToUse) {
                        // Обновление публикации (PUT /publish/<encodedPrefix>/<distribution>)
                        // Кодирование префикса по правилам Aptly: '_' -> '__' и '/' -> '_'
                        const encDist = encodeURIComponent(distFinal);
                        const encPrefix = prefixToUse.replace(/_/g, '__').replace(/\//g, '_');
                        const publishUrl = `${apiBase}/publish/${encPrefix}/${encDist}`;
                        const publishCmd = `curl -X PUT ${publishUrl}`;
                        box.textContent = joinCommands([copyCmd, publishCmd]);
                    } else {
                        box.textContent = copyCmd;
                    }
                })
                .catch((err) => {
                    box.textContent = t('msg.error_forming') + err;
                });
        }
        [
            'source_repo',
            'target_repo',
            'package_name',
            'version',
            'target_distribution',
            'target_prefix',
        ].forEach((id) => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('input', updateCopyCmd);
                el.addEventListener('change', updateCopyCmd);
            }
        });
        // =============================
        // Функция validateCopy
        // Назначение: включить / отключить кнопку копирования по наличию обязательных полей.
        // Логика: кнопка активна только если заполнены source_repo, target_repo,
        // Поля package_name и version.
        // =============================
        function validateCopy() {
            const btn = document.getElementById('copy_submit');
            if (!btn) return;
            const src = document.getElementById('source_repo');
            const tgt = document.getElementById('target_repo');
            const pkg = document.getElementById('package_name');
            const ver = document.getElementById('version');
            btn.disabled = !(
                src &&
                tgt &&
                pkg &&
                ver &&
                src.value.trim() &&
                tgt.value.trim() &&
                pkg.value.trim() &&
                ver.value.trim()
            );
        }
        [
            'source_repo',
            'target_repo',
            'package_name',
            'version',
            'target_distribution',
            'target_prefix',
        ].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('input', validateCopy);
        });
        validateCopy();
        // Инициализация
        updateCopyCmd();
        // =============================
        // Обработчик submit формы копирования
        // Назначение: отправить JSON на /copy_package. Визуально подсвечивает кнопку
        // прогресса (желтый), успеха (зелёный), ошибки (красный). После завершения
        // переформатирует команду copy/publish для актуального состояния.
        // =============================
        copyForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const btn = document.getElementById('copy_submit');
            const resultBox = document.getElementById('copy_package_result');
            const data = (function () {
                const get = (id) => {
                    const el = document.getElementById(id);
                    return el ? el.value.trim() : '';
                };
                return {
                    source_repo: get('source_repo'),
                    target_repo: get('target_repo'),
                    package_name: get('package_name'),
                    version: get('version'),
                    source_distribution: get('source_distribution'),
                    target_distribution: get('target_distribution'),
                    target_prefix: get('target_prefix'),
                    arch: (window.PUBLISH_ARCH || '').split(',')[0] || '',
                };
            })();
            btn.disabled = true;
            btn.style.backgroundColor = '#ffd600';
            btn.style.color = '#333';
            // показать прогресс как balloon; результат запроса помещаем в resultBox
            var progressBalloon = null;
            try { if (window.showBalloon) progressBalloon = window.showBalloon(t('msg.in_progress'), 'info'); }
            catch (e) {}

            fetch('/copy_package', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            })
                .then((resp) => resp.json().then((j) => ({ status: resp.status, body: j })))
                .then(({ status, body }) => {
                    // вне зависимости от результата помещаем ответ сервера в окно результата
                    try { resultBox.textContent = typeof body === 'string' ? body : JSON.stringify(body, null, 2); }
                    catch (e) { resultBox.textContent = String(body); }

                    if (status >= 200 && status < 300 && body && body.status === 'ok') {
                        try { if (window.showBalloon) window.showBalloon(t('msg.copy_ok'), 'success'); }
                        catch (e) {}
                        btn.style.backgroundColor = '#28a745';
                        btn.style.color = '#fff';
                    } else {
                        var errMsg = (body && body.error) ? body.error : t('msg.copy_error');
                        try { if (window.showBalloon) window.showBalloon(errMsg, 'danger'); }
                        catch (e) {}
                        btn.style.backgroundColor = '#dc3545';
                        btn.style.color = '#fff';
                    }

                    // убрать прогресс-балун
                    if (progressBalloon) {
                        try {
                            progressBalloon.classList.remove('show');
                            setTimeout(function () {
                                if (progressBalloon.parentNode) progressBalloon.parentNode.removeChild(progressBalloon);
                            }, 300);
                        }
                        catch (e) {}
                    }

                    btn.disabled = false;
                    updateCopyCmd();
                })
                .catch((err) => {
                    // показать ошибку как balloon и поместить текст ошибки в окно результата
                    try { if (window.showBalloon) window.showBalloon(t('msg.copy_error'), 'danger'); }
                    catch (e) {}
                    resultBox.textContent = String(err);
                    btn.style.backgroundColor = '#dc3545';
                    btn.style.color = '#fff';
                    // убрать прогресс-балун
                    if (progressBalloon) {
                        try {
                            progressBalloon.classList.remove('show');
                            setTimeout(function () {
                                if (progressBalloon.parentNode) progressBalloon.parentNode.removeChild(progressBalloon);
                            }, 300);
                        }
                        catch (e) {}
                    }
                    btn.disabled = false;
                    updateCopyCmd();
                });
        });
    }

    // =============================
    // Блок интерфейса удаления пакета (3-колоночный список)
    // Назначение: пошаговый выбор репозитория -> пакета -> версии и формирование
    // команды curl для удаления (DELETE /repos/<repo>/packages). Использует локальный
    // кеш и фильтры для быстрого поиска. Отдельные функции управляют каждым этапом.
    // =============================
    const reposListEl = document.getElementById('del_repos_list');
    if (reposListEl) {
        const packagesListEl = document.getElementById('del_packages_list');
        const versionsListEl = document.getElementById('del_versions_list');
        const deleteBtn = document.getElementById('delete_submit');
        const reposFilter = document.getElementById('del_repos_filter');
        const packagesFilter = document.getElementById('del_packages_filter');
        const versionsFilter = document.getElementById('del_versions_filter');
        const resultBox = document.getElementById('delete_result_box');
        let selectedRepo = null;
        let selectedPackage = null;
        let selectedVersion = null;

        function clear(el) {
            if (el) el.innerHTML = '';
        }
        function setActive(list, value) {
            if (!list) return;
            Array.from(list.querySelectorAll('li')).forEach((li) => {
                if (li.dataset.value === value) {
                    li.classList.add('active');
                } else li.classList.remove('active');
            });
        }
        // --- updateDeleteCmdPreview ---
        // Назначение: построить curl-команду удаления выбранного пакета.
        // Условия: выбраны repo, package и version. Иначе очищает превью.
        function updateDeleteCmdPreview() {
            const box = document.getElementById('delete_command_box');
            if (!box) {
                return;
            }

            // Проверяем права доступа - не показываем команды для пользователей без root прав
            if (deleteBtn && deleteBtn.hasAttribute('data-readonly')) {
                box.textContent = '';
                return;
            }

            if (!(selectedRepo && selectedPackage && selectedVersion)) {
                box.textContent = '';
                return;
            }
            // Получение key пакета для формирования curl-команды
            const arch = (window.PUBLISH_ARCH || '').split(',')[0] || '';
            box.textContent = t('msg.forming_command');
            fetch(
                `/api/package_key?repo=${encodeURIComponent(selectedRepo)}&package=${encodeURIComponent(selectedPackage)}&version=${encodeURIComponent(selectedVersion)}${arch ? `&arch=${encodeURIComponent(arch)}` : ''}`
            )
                .then((r) => r.json())
                .then((data) => {
                    if (!data.key) {
                        box.textContent = t('msg.no_package_key');
                        return;
                    }
                    const apiBase = window.API_URL || '/api';
                    const url = `${apiBase}/repos/${selectedRepo}/packages`;
                    const payload = { PackageRefs: [data.key] };
                    let json = JSON.stringify(payload).replace(/'/g, "'\\''");
                    box.textContent = `curl -X DELETE -H 'Content-Type: application/json' -d '${json}' ${url}`;
                })
                .catch((err) => {
                    box.textContent = t('msg.error_forming') + err;
                });
        }
        let cachedRepos = [];
        let cachedPackages = [];
        let cachedVersions = [];

        // --- applyFilter ---
        // Назначение: скрыть элементы списка, не соответствующие подстроке фильтра.
        function applyFilter(listEl, filterValue) {
            const fv = (filterValue || '').toLowerCase();
            Array.from(listEl.querySelectorAll('li')).forEach((li) => {
                if (!fv || li.dataset.value.toLowerCase().includes(fv)) li.style.display = '';
                else li.style.display = 'none';
            });
        }

        // --- buildList ---
        // Назначение: перерисовать список <li> и навесить обработчик выбора.
        function buildList(listEl, items, clickHandler) {
            clear(listEl);
            items.forEach((name) => {
                const li = document.createElement('li');
                li.textContent = name;
                li.dataset.value = name;
                li.className = 'list-group-item list-group-item-action';
                li.addEventListener('click', () => clickHandler(name));
                listEl.appendChild(li);
            });
        }

        // --- refreshRepos ---
        // Назначение: запросить /api/repos, обновить список репозиториев и применить фильтр.
        function refreshRepos() {
            fetch('/api/repos')
                .then((r) => r.json())
                .then((repos) => {
                    cachedRepos = (repos || []).map((r) => r.Name || r);
                    buildList(reposListEl, cachedRepos, handleRepoClick);
                    applyFilter(reposListEl, reposFilter.value);
                });
        }

        // --- handleRepoClick ---
        // Назначение: выбрать/снять выбор репозитория, загрузить пакеты при выборе.
        function handleRepoClick(name) {
            if (selectedRepo === name) {
                selectedRepo = null;
                selectedPackage = null;
                selectedVersion = null;
                setActive(reposListEl, null);
                clear(packagesListEl);
                clear(versionsListEl);
                packagesFilter.value = '';
                packagesFilter.disabled = true;
                versionsFilter.value = '';
                versionsFilter.disabled = true;
                cachedPackages = [];
                cachedVersions = [];
                updateDeleteButton();
                updateDeleteCmdPreview();
                return;
            }
            selectedRepo = name;
            selectedPackage = null;
            selectedVersion = null;
            setActive(reposListEl, name);
            loadPackages(name);
            clear(versionsListEl);
            versionsFilter.value = '';
            versionsFilter.disabled = true;
            cachedVersions = [];
            updateDeleteButton();
            updateDeleteCmdPreview();
        }

        // --- loadPackages ---
        // Назначение: получить список пакетов репозитория и построить колонку.
        function loadPackages(repo) {
            fetch(`/api/packages?repo=${encodeURIComponent(repo)}`)
                .then((r) => r.json())
                .then((pkgs) => {
                    cachedPackages = pkgs || [];
                    buildList(packagesListEl, cachedPackages, handlePackageClick);
                    packagesFilter.disabled = false;
                    applyFilter(packagesListEl, packagesFilter.value);
                    // Автовыбор если единственный пакет
                    if (cachedPackages.length === 1) {
                        handlePackageClick(cachedPackages[0]);
                    }
                });
        }

        // --- handlePackageClick ---
        // Назначение: выбрать/снять выбор пакета и инициировать загрузку версий.
        function handlePackageClick(p) {
            if (selectedPackage === p) {
                selectedPackage = null;
                selectedVersion = null;
                setActive(packagesListEl, null);
                clear(versionsListEl);
                versionsFilter.value = '';
                versionsFilter.disabled = true;
                cachedVersions = [];
                updateDeleteButton();
                updateDeleteCmdPreview();
                return;
            }
            selectedPackage = p;
            selectedVersion = null;
            setActive(packagesListEl, p);
            loadVersions(selectedRepo, p);
            updateDeleteButton();
            updateDeleteCmdPreview();
        }

        // --- loadVersions ---
        // Назначение: запросить версии выбранного пакета и обновить список.
        function loadVersions(repo, pkg) {
            fetch(
                `/api/versions?repo=${encodeURIComponent(repo)}&package=${encodeURIComponent(pkg)}`
            )
                .then((r) => r.json())
                .then((vers) => {
                    cachedVersions = vers || [];
                    buildList(versionsListEl, cachedVersions, handleVersionClick);
                    versionsFilter.disabled = false;
                    applyFilter(versionsListEl, versionsFilter.value);
                    // Автовыбор если единственная версия
                    if (cachedVersions.length === 1) {
                        handleVersionClick(cachedVersions[0]);
                    } else if (cachedVersions.length === 0) {
                        // Нет версий — сброс выбранной
                        selectedVersion = null;
                        // Если у пакета больше нет версий, убрать пакет из списка пакетов
                        try {
                            const idx = cachedPackages.indexOf(pkg);
                            if (idx !== -1) {
                                cachedPackages.splice(idx, 1);
                                buildList(packagesListEl, cachedPackages, handlePackageClick);
                                // Если текущий выбранный пакет совпадает с удалённым — сбросить выбор
                                if (selectedPackage === pkg) {
                                    selectedPackage = null;
                                    setActive(packagesListEl, null);
                                }
                            }
                        } catch (e) {
                            console.debug('[loadVersions] failed to remove empty package', e);
                        }
                        versionsFilter.disabled = true;
                        updateDeleteButton();
                        updateDeleteCmdPreview();
                    }
                });
        }

        // --- handleVersionClick ---
        // Назначение: выбрать/снять конкретную версию и обновить кнопку/превью.
        function handleVersionClick(v) {
            if (selectedVersion === v) {
                selectedVersion = null;
                setActive(versionsListEl, null);
            } else {
                selectedVersion = v;
                setActive(versionsListEl, v);
            }
            updateDeleteButton();
            updateDeleteCmdPreview();
        }

        // --- updateDeleteButton ---
        // Назначение: активировать кнопку удаления при выборе репозитория, пакета и версии.
        function updateDeleteButton() {
            if (deleteBtn) {
                // Проверяем права доступа
                if (deleteBtn.hasAttribute('data-readonly')) {
                    // Для пользователей без root прав кнопка всегда заблокирована
                    deleteBtn.disabled = true;
                    return;
                }

                const enabled = selectedRepo && selectedPackage && selectedVersion;
                deleteBtn.disabled = !enabled;
                if (enabled) {
                    deleteBtn.style.background = '#dc3545';
                    deleteBtn.style.color = '#fff';
                } else {
                    deleteBtn.style.background = ''; // На стиль применится CSS :disabled
                    deleteBtn.style.color = '';
                }
            }
        }
        // Кнопка удаления с модальным подтверждением
        if (deleteBtn) {
            deleteBtn.addEventListener('click', () => {
                // Проверка прав доступа
                if (deleteBtn.hasAttribute('data-readonly')) {
                    return; // Блокируем выполнение для пользователей без root прав
                }
                if (!(selectedRepo && selectedPackage && selectedVersion)) return;
                const body = document.getElementById('delete_modal_body');
                if (body) {
                    body.textContent = t('msg.delete_confirm_template')
                        .replace('{pkg}', selectedPackage).replace('{ver}', selectedVersion).replace('{repo}', selectedRepo);
                }
                const modalEl = document.getElementById('deleteConfirmModal');
                if (modalEl) {
                    const modal = new bootstrap.Modal(modalEl);
                    modal.show();
                }
            });
        }
        const confirmBtn = document.getElementById('confirm_delete_pack_btn');
        if (confirmBtn) {
            // =============================
            // Обработчик подтверждения удаления
            // Назначение: отправить POST /delete_package с выбранными параметрами.
            // Управляет визуальными состояниями кнопки и закрывает модал по завершению.
            // =============================
            confirmBtn.addEventListener('click', () => {
                if (!(selectedRepo && selectedPackage && selectedVersion)) return;
                const modalEl = document.getElementById('deleteConfirmModal');
                const arch = (window.PUBLISH_ARCH || '').split(',')[0] || '';
                const btn = deleteBtn;
                btn.disabled = true;
                btn.style.backgroundColor = '#ffd600';
                btn.style.color = '#333';
                resultBox.textContent = t('msg.deleting');

                var progressBalloon = null;
                try { if (window.showBalloon) progressBalloon = window.showBalloon(t('msg.in_progress'), 'info'); }
                catch (e) {}

                fetch('/delete_package', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        repo: selectedRepo,
                        package_name: selectedPackage,
                        version: selectedVersion,
                        arch,
                    }),
                })
                    .then((resp) => resp.json().then((j) => ({ status: resp.status, body: j })))
                    .then(({ status, body }) => {
                        // Положить полный ответ сервера в окно результата (pretty JSON если возможно)
                        try { resultBox.textContent = typeof body === 'string' ? body : JSON.stringify(body, null, 2); }
                        catch (e) { resultBox.textContent = String(body); }

                        if (status >= 200 && status < 300 && body && body.status === 'ok') {
                            try { if (window.showBalloon) window.showBalloon(t('msg.package_deleted'), 'success'); }
                            catch (e) {}
                            btn.style.backgroundColor = '#28a745';
                            btn.style.color = '#fff';
                            // После удаления сбрасываем выбранную версию и обновляем список версий
                            selectedVersion = null;
                            updateDeleteButton();
                            loadVersions(selectedRepo, selectedPackage);
                            updateDeleteCmdPreview();
                        } else {
                            var errMsg = (body && body.error) ? body.error : t('msg.could_not_delete_package');
                            try { if (window.showBalloon) window.showBalloon(errMsg, 'danger'); }
                            catch (e) {}
                            btn.style.backgroundColor = '#dc3545';
                            btn.style.color = '#fff';
                        }

                        // убрать прогресс-балун
                        if (progressBalloon) {
                            try {
                                progressBalloon.classList.remove('show');
                                setTimeout(function () {
                                    if (progressBalloon.parentNode) progressBalloon.parentNode.removeChild(progressBalloon);
                                }, 300);
                            }
                            catch (e) {}
                        }

                        btn.disabled = false;
                        updateDeleteCmdPreview();
                    })
                    .catch((err) => {
                        try { if (window.showBalloon) window.showBalloon(t('msg.could_not_delete_package'), 'danger'); }
                        catch (e) {}
                        resultBox.textContent = String(err);
                        btn.style.backgroundColor = '#dc3545';
                        btn.style.color = '#fff';
                        btn.disabled = false;
                        // убрать прогресс-балун
                        if (progressBalloon) {
                            try {
                                progressBalloon.classList.remove('show');
                                setTimeout(function () {
                                    if (progressBalloon.parentNode) progressBalloon.parentNode.removeChild(progressBalloon);
                                }, 300);
                            }
                            catch (e) {}
                        }
                    })
                    .finally(() => {
                        if (modalEl) {
                            try { bootstrap.Modal.getInstance(modalEl)?.hide(); }
                            catch (e) {}
                        }
                    });
            });
        }
        // Фильтры
        if (reposFilter) {
            reposFilter.addEventListener('input', () =>
                applyFilter(reposListEl, reposFilter.value)
            );
        }
        if (packagesFilter) {
            packagesFilter.addEventListener('input', () =>
                applyFilter(packagesListEl, packagesFilter.value)
            );
        }
        if (versionsFilter) {
            versionsFilter.addEventListener('input', () =>
                applyFilter(versionsListEl, versionsFilter.value)
            );
        }

        // Первичная загрузка репозиториев
        refreshRepos();
    // Обновить состояние кнопки удаления после начальной загрузки списков
    try { updateDeleteButton(); }
    catch (e) {}
    }

    // ===== Поддержка видимого списка репозиториев на вкладке "Удалить репозиторий" =====
    const delReposRepoEl = document.getElementById('del_repos_list_repo');
    if (delReposRepoEl) {
        const delReposFilterRepo = document.getElementById('del_repos_filter_repo');
        const deleteRepoInput = document.getElementById('delete_repo_select');
        const deleteRepoSubmit = document.getElementById('delete_repo_submit');

        function clearRepoList(el) { if (el) el.innerHTML = ''; }
        function applyFilterRepo(listEl, filterValue) {
            const fv = (filterValue || '').toLowerCase();
            Array.from(listEl.querySelectorAll('li')).forEach((li) => {
                if (!fv || li.dataset.value.toLowerCase().includes(fv)) li.style.display = '';
                else li.style.display = 'none';
            });
        }
        function setActiveRepo(listEl, value) {
            if (!listEl) return;
            Array.from(listEl.querySelectorAll('li')).forEach((li) => {
                if (li.dataset.value === value) li.classList.add('active');
                else li.classList.remove('active');
            });
        }

        function buildRepoList(listEl, items) {
            clearRepoList(listEl);
            items.forEach((name) => {
                const li = document.createElement('li');
                li.textContent = name;
                li.dataset.value = name;
                li.className = 'list-group-item list-group-item-action';
                li.addEventListener('click', () => {
                    // Toggle selection similar to delete-package.handleRepoClick
                    const submitBtn = document.getElementById('delete_repo_submit');
                    if (selectedRepoRepo === name) {
                        // deselect
                        selectedRepoRepo = null;
                        setActiveRepo(listEl, null);
                        if (submitBtn) submitBtn.disabled = true;
                        if (typeof updateDeleteRepoCmd === 'function') setTimeout(updateDeleteRepoCmd, 0);
                        return;
                    }
                    // select
                    selectedRepoRepo = name;
                    setActiveRepo(listEl, name);
                    if (submitBtn) submitBtn.disabled = false;
                    if (typeof updateDeleteRepoCmd === 'function') setTimeout(updateDeleteRepoCmd, 0);
                });
                listEl.appendChild(li);
            });
            // reflect currently selectedRepoRepo (if any)
            if (selectedRepoRepo) setActiveRepo(listEl, selectedRepoRepo);
        }

        function refreshReposForDeleteRepo() {
            fetch('/api/repos')
                .then((r) => r.json())
                .then((repos) => {
                    const items = (repos || []).map((r) => r.Name || r);
                    buildRepoList(delReposRepoEl, items, function (name) {
                        // Сохранить выбор в переменной (отображение не требуется)
                        selectedRepoRepo = name;
                        if (typeof updateDeleteRepoCmd === 'function') setTimeout(updateDeleteRepoCmd, 0);
                        if (deleteRepoSubmit) deleteRepoSubmit.disabled = false;
                    });
                    if (delReposFilterRepo) applyFilterRepo(delReposRepoEl, delReposFilterRepo.value);
                })
                .catch(() => {});
        }

        if (delReposFilterRepo) {
            delReposFilterRepo.addEventListener('input', () => applyFilterRepo(delReposRepoEl, delReposFilterRepo.value));
        }

        // Заполнить сразу при загрузке страницы (как в удалении пакета)
        try { refreshReposForDeleteRepo(); } catch (e) {}
        // Повторно обновлять при переключении вкладок handled elsewhere via shown.bs.tab
    }

    // Переключение вкладок: очистка результатов при смене
    const aptlyTab = document.getElementById('aptlyTab');
    if (aptlyTab) {
        aptlyTab.addEventListener('click', function (e) {
            const target = e.target;
            if (target && target.classList.contains('nav-link')) {
                const idsToClear = {
                    'copy-package-tab': 'copy_package_result',
                    'create-repo-tab': 'create_repo_result',
                    'delete-package-tab': 'delete_result_box',
                };
                const boxId = idsToClear[target.id];
                if (boxId) {
                    const el = document.getElementById(boxId);
                    if (el) el.textContent = '';
                }
                // Очистка всех форм при переключении
                function clearForm(formId) {
                    const f = document.getElementById(formId);
                    if (!f) return;
                    Array.from(f.querySelectorAll('input, textarea')).forEach((inp) => {
                        // Не трогаем скрытые / кнопки
                        if (inp.type === 'button' || inp.type === 'submit') return;
                        inp.value = '';
                    });
                }
                clearForm('copy_package_form');
                clearForm('create_repo_form');
                clearForm('delete_package_form');
                // Очистить выбранный репозиторий на вкладке удаления репозитория
                // try {
                //     selectedRepoRepo = null;
                // } catch (e) {}
                // Специально очистим зоны команд при полной очистке
                const copyCmdBox = document.getElementById('copy_package_api');
                if (copyCmdBox) copyCmdBox.textContent = '';
                const createCmdBox = document.getElementById('create_repo_api');
                if (createCmdBox) createCmdBox.textContent = '';
                const deleteCmdBox = document.getElementById('delete_command_box');
                if (deleteCmdBox) deleteCmdBox.textContent = '';
                // Обновление списков репозиториев при переключении на любую вкладку
                if (typeof fillRepoList === 'function') {
                    fillRepoList('source_repo', 'source_repo_list');
                    fillRepoList('target_repo', 'target_repo_list');
                }
                if (typeof refreshRepos === 'function') {
                    // для интерфейса удаления (3 колонки)
                    refreshRepos();
                }
                if (typeof refreshReposForDeleteRepo === 'function') {
                    // обновить видимый список репозиториев на вкладке удаления репозитория
                    refreshReposForDeleteRepo();
                }
                if (typeof updateCopyCmd === 'function') {
                    setTimeout(updateCopyCmd, 0);
                }
            }
        });
    }

    // Также реагируем на событие Bootstrap 'shown.bs.tab' — покрывает переключение через
    // клавиатуру или программный вызов таба. Повторяем ту же логику обновления списков.
    document.querySelectorAll('#aptlyTab button[data-bs-toggle="tab"]').forEach((btn) => {
        btn.addEventListener('shown.bs.tab', function (e) {
            if (typeof fillRepoList === 'function') {
                fillRepoList('source_repo', 'source_repo_list');
                fillRepoList('target_repo', 'target_repo_list');
                fillRepoList('upload_repo', 'upload_repo_list');
            }
            if (typeof refreshRepos === 'function') {
                refreshRepos();
            }
            if (typeof refreshReposForDeleteRepo === 'function') {
                refreshReposForDeleteRepo();
            }
            if (typeof updateCopyCmd === 'function') setTimeout(updateCopyCmd, 0);
        });
    });

    // =============================
    // Самовызывающийся модуль initFilterable
    // Назначение: превратить input[data-filterable][list] в кастомный виджет с
    // собственным выпадающим списком и строкой фильтра, поддержкой закрытия по клику вне
    // и клавише Escape. Данные берутся из связанного datalist и пересобираются при открытии.
    // =============================
    (function initFilterable() {
        const inputs = Array.from(document.querySelectorAll('input[data-filterable][list]'));
        if (!inputs.length) return;
        function closeAll(except) {
            document.querySelectorAll('.filter-dropdown-panel.open').forEach((p) => {
                if (p !== except) p.classList.remove('open');
            });
        }
        const globalClick = (ev) => {
            const panel = ev.target.closest('.filter-dropdown-panel');
            if (panel) {
                // Клик внутри открытой панели – не закрываем её
                return;
            }
            const filterInput =
                ev.target.matches && ev.target.matches('input[data-filterable]') ? ev.target : null;
            if (filterInput) {
                // Клик по другому фильтру: закрыть остальные
                const ownPanel = filterInput.parentNode.querySelector('.filter-dropdown-panel');
                closeAll(ownPanel);
                return; // открытие произойдёт в обработчике focus/click конкретного инпута
            }
            // Клик вне панели и не по фильтру – закрыть все
            closeAll();
        };
        document.addEventListener('click', globalClick);
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closeAll();
            }
        });
        inputs.forEach((inp) => {
            // Обернём
            const wrap = document.createElement('div');
            wrap.className = 'filter-dropdown-wrapper';
            inp.parentNode.insertBefore(wrap, inp);
            wrap.appendChild(inp);
            // Панель
            const panel = document.createElement('div');
            panel.className = 'filter-dropdown-panel';
            const search = document.createElement('input');
            search.type = 'text';
            search.className = 'form-control filter-dropdown-search';
            search.placeholder = t('msg.filter_placeholder');
            const ul = document.createElement('ul');
            ul.className = 'filter-dropdown-list';
            const empty = document.createElement('div');
            empty.className = 'filter-dropdown-empty';
            empty.textContent = t('msg.no_matches');
            panel.appendChild(search);
            panel.appendChild(ul);
            panel.appendChild(empty);
            wrap.appendChild(panel);
            empty.style.display = 'none';
            function collectOptions() {
                const listId = inp.getAttribute('list');
                const dl = listId && document.getElementById(listId);
                if (!dl) return [];
                return Array.from(dl.querySelectorAll('option'))
                    .map((o) => o.value)
                    .filter(Boolean);
            }
            function render(list) {
                ul.innerHTML = '';
                let visibleCount = 0;
                const current = inp.value;
                list.forEach((val) => {
                    if (search.value && !val.toLowerCase().includes(search.value.toLowerCase()))
                        return;
                    visibleCount++;
                    const li = document.createElement('li');
                    li.textContent = val;
                    if (val === current) li.classList.add('active');
                    li.addEventListener('mousedown', (e) => {
                        // Используем mousedown, чтобы сработало до blur
                        e.preventDefault();
                        inp.value = val;
                        inp.dispatchEvent(new Event('input'));
                        // Если это поле выбора репозитория для удаления — вызвать updateDeleteRepoCmd
                        if (inp.id === 'delete_repo_select' && typeof updateDeleteRepoCmd === 'function') {
                            setTimeout(updateDeleteRepoCmd, 0);
                        }
                        panel.classList.remove('open');
                    });
                    ul.appendChild(li);
                });
                empty.style.display = visibleCount ? 'none' : 'block';
            }
            function open() {
                closeAll(panel);
                // Перестраиваем список при каждом открытии (опции могли обновиться через fetch)
                render(collectOptions());
                panel.classList.add('open');
                search.value = '';
                setTimeout(() => search.focus(), 0);
            }
            inp.addEventListener('focus', open);
            inp.addEventListener('click', open);
            search.addEventListener('input', () => render(collectOptions()));
            // Обработка ESC внутри поля фильтра или исходного инпута
            [inp, search].forEach((el) =>
                el.addEventListener('keydown', (e) => {
                    if (e.key === 'Escape') {
                        panel.classList.remove('open');
                        inp.blur();
                    }
                })
            );
            inp.addEventListener('keydown', (e) => {
                if (e.key === 'ArrowDown') {
                    if (!panel.classList.contains('open')) open();
                    const first = ul.querySelector('li');
                    if (first) {
                        first.focus?.();
                    }
                }
            });
        });
    })();
});

// =============================
// Функция updateApiCmd
// Назначение: построить curl команду создания репозитория (POST /repos) и при
// наличии prefix+distribution — команду публикации (POST /publish/<prefix>). Использует
// значения полей формы создания. Результат выводит в #create_repo_api.
// =============================
function updateApiCmd() {
    const nameEl = document.getElementById('name');
    const componentEl = document.getElementById('component');
    const distributionEl = document.getElementById('distribution');
    const prefixEl = document.getElementById('prefix');
    const commentEl = document.getElementById('comment');
    if (!nameEl && !componentEl && !distributionEl && !prefixEl && !commentEl) {
        const createApiBox = document.getElementById('create_repo_api');
        if (createApiBox) createApiBox.textContent = '';
        return;
    }
    const name = nameEl ? nameEl.value.trim() : '';
    const component = componentEl ? componentEl.value.trim() : '';
    const distribution = distributionEl ? distributionEl.value.trim() : '';
    const prefix = prefixEl ? prefixEl.value.trim() : '';
    const comment = commentEl ? commentEl.value.trim() : '';
    let api_cmd = '';
    if (name) {
        const url = (window.API_URL || '/api') + '/repos';
        const data = {
            Name: name,
            Comment: comment,
            DefaultDistribution: distribution,
            DefaultComponent: component,
        };
        const json = JSON.stringify(data);
        api_cmd = `curl -X POST -H 'Content-Type: application/json' --data '${json}' ${url}`;
    if (prefix && distribution) {
            const encodedPrefix = prefix.replace(/_/g, '__').replace(/\//g, '_');
            const publish_url = (window.API_URL || '/api') + '/publish/' + encodedPrefix;
            const archList = (window.PUBLISH_ARCH || 'amd64')
                .split(',')
                .map((a) => a.trim())
                .filter(Boolean);
            const publish_data = {
                SourceKind: 'local',
                Sources: [{ Name: name, Component: component }],
                Architectures: archList,
                Distribution: distribution,
            };
            if (window.PUBLISH_ORIGIN) publish_data.Origin = window.PUBLISH_ORIGIN;
            if (window.PUBLISH_LABEL) publish_data.Label = window.PUBLISH_LABEL;
            const publish_json = JSON.stringify(publish_data);
            const publishCmd = `curl -X POST -H 'Content-Type: application/json' --data '${publish_json}' ${publish_url}`;
            api_cmd = joinCommands([api_cmd, publishCmd]);
        }
    }
    const createApiBox = document.getElementById('create_repo_api');
    if (createApiBox) createApiBox.textContent = api_cmd;
}
['name', 'component', 'distribution', 'comment', 'prefix'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', updateApiCmd);
});

// =============================
// Функция validateCreateForm
// Назначение: включить кнопку создания репозитория только если заполнены
// обязательные поля (name, component, distribution, prefix).
// =============================
function validateCreateForm() {
    const nameEl = document.getElementById('name');
    const componentEl = document.getElementById('component');
    const distributionEl = document.getElementById('distribution');
    const prefixEl = document.getElementById('prefix');
    const btn = document.getElementById('create_repo_submit');
    if (btn) {
        const name = nameEl ? nameEl.value.trim() : '';
        const component = componentEl ? componentEl.value.trim() : '';
        const distribution = distributionEl ? distributionEl.value.trim() : '';
        const prefix = prefixEl ? prefixEl.value.trim() : '';
        btn.disabled = !(name && component && distribution && prefix);
    }
}
['name', 'component', 'distribution', 'prefix'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', validateCreateForm);
});
validateCreateForm();
updateApiCmd();

// =============================
// Обработчик submit формы создания репозитория
// Назначение: выполнить последовательность: POST /create_repo (бэкенд обрабатывает и
// сам инициирует publish). Визуально меняет цвет кнопки по статусу ответа.
// =============================
const createRepoForm = document.getElementById('create_repo_form');
if (createRepoForm) {
    createRepoForm.addEventListener('submit', function (e) {
        e.preventDefault();
        const form = e.target;
        const btn = form.querySelector('button[type="submit"]');
        const resultEl = document.getElementById('create_repo_result');
        const data = {
            name: form.name.value,
            component: form.component.value,
            distribution: form.distribution.value,
            prefix: form.prefix.value,
            comment: form.comment.value,
        };

        // В процессе выполнения — желтый
        if (btn) {
            btn.style.backgroundColor = '#ffd600';
            btn.style.color = '#333';
            btn.disabled = true;
        }

        var progressBalloon = null;
        try { if (window.showBalloon) progressBalloon = window.showBalloon(t('msg.in_progress'), 'info'); }
        catch (e) {}

        fetch('/create_repo', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest' },
            body: new URLSearchParams(data),
        })
            .then((resp) =>
                resp.text().then((t) => {
                    let parsed = null;
                    try { parsed = JSON.parse(t); }
                    catch (e) { parsed = null; }
                    return { status: resp.status, text: t, json: parsed };
                })
            )
            .then((res) => {
                // Положить полный ответ сервера в окно результата (pretty JSON если возможно)
                if (resultEl) {
                    if (res.json) resultEl.textContent = JSON.stringify(res.json, null, 2);
                    else resultEl.textContent = res.text;
                }

                // Логика balloon / цвет кнопки
                if (res.status >= 200 && res.status < 300) {
                    // Если сервер вернул structured balloon, показать его; иначе показать стандартный success
                    if (res.json && res.json.balloon) {
                        try { if (window.showBalloon) window.showBalloon(res.json.balloon, res.json.category || 'info'); }
                        catch (e) {}
                    } else {
                        try { if (window.showBalloon) window.showBalloon(t('msg.repo_created'), 'success'); }
                        catch (e) {}
                    }
                    if (btn) {
                        btn.style.backgroundColor = '#28a745';
                        btn.style.color = '#fff';
                    }
                } else {
                    // Prefer structured fields: error or balloon. Fall back to raw text.
                    var errMsg = t('msg.could_not_create_repo');
                    if (res.json) {
                        if (res.json.error) errMsg = res.json.error;
                        else if (res.json.balloon) errMsg = res.json.balloon;
                    } else if (res.text) {
                        // If server returned raw JSON text with escaped unicode and parsing failed,
                        // try to parse it now to extract balloon field.
                        try {
                            var parsedFallback = JSON.parse(res.text);
                            if (parsedFallback && parsedFallback.balloon) errMsg = parsedFallback.balloon;
                        } catch (e) {
                            errMsg = res.text || errMsg;
                        }
                    }
                    try { if (window.showBalloon) window.showBalloon(errMsg, 'danger'); }
                    catch (e) {}
                    if (btn) {
                        btn.style.backgroundColor = '#dc3545';
                        btn.style.color = '#fff';
                    }
                }

                // убрать прогресс-балун
                if (progressBalloon) {
                    try {
                        progressBalloon.classList.remove('show');
                        setTimeout(function () {
                            if (progressBalloon.parentNode) progressBalloon.parentNode.removeChild(progressBalloon);
                        }, 300);
                    }
                    catch (e) {}
                }

                if (btn) btn.disabled = false;
                updateApiCmd();
            })
            .catch((err) => {
                if (resultEl) resultEl.textContent = String(err);
                try { if (window.showBalloon) window.showBalloon(t('msg.could_not_create_repo'), 'danger'); }
                catch (e) {}
                if (btn) {
                    btn.style.backgroundColor = '#dc3545';
                    btn.style.color = '#fff';
                    btn.disabled = false;
                }
                if (progressBalloon) {
                    try {
                        progressBalloon.classList.remove('show');
                        setTimeout(function () {
                            if (progressBalloon.parentNode) progressBalloon.parentNode.removeChild(progressBalloon);
                        }, 300);
                    }
                    catch (e) {}
                }
                updateApiCmd();
            });
    });
}
