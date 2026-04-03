# create_repo.py

import requests
from flask import request, redirect, flash, jsonify, Flask
from flask_login import login_required, current_user
from load_config import _load_config
from app_logging import command_logging
from typing import Callable
from i18n import inject_i18n


def init_create_repo_routes(app: Flask, get_api_url: Callable[[], str]) -> None:


# =============================
# Endpoint create_repo
# Назначение: создать локальный репозиторий в Aptly и сразу (при успехе) выполнить его
# публикацию (publish) с заданными Distribution и Prefix. Формирует два запроса:
# 1) POST /repos
# 2) POST /publish/<prefix>
# Добавляет метаданные Origin/Label если указаны в конфиге. Возвращает конкатенированный
# текст обоих ответов и статус второго запроса (publish) при успешном создании.
# Обработка ошибок: при отсутствии обязательных полей (name, component) делает redirect с flash;
# при сетевых ошибках возвращает 500. Требует явного prefix — без него возвращает 400.
# =============================
    def validate_codename(name: str, component: str, allowed: list[str]) -> tuple[bool, str]:
        """
        Проверить, разрешено ли кодовое имя для создания репозитория.
        Возвращает (разрешено, base_codename).
        """
        name_l = name.strip().lower() if name else ''
        comp = (component or '').strip()
        base = ''
        allowed_match = False

        if not name_l or not allowed:
            return True, ''

        # 1) разделение по маркеру компонента
        if comp and f'-{comp}-' in name_l:
            base = name_l.split(f'-{comp}-', 1)[0].strip()
            allowed_match = base in allowed
        else:
            # 2) искать разрешённый префикс
            for a in allowed:
                if name_l == a or name_l.startswith(a + '-') or name_l.startswith(a + '_'):
                    base = a
                    allowed_match = True
                    break
            # 3) fallback — первый токен до дефиса
            if not allowed_match:
                parts = name_l.split('-')
                base = parts[0].strip().lower() if parts else ''
                allowed_match = base in allowed

        return allowed_match, base or name_l


#######
    def require_prefix(prefix: str, message: str):
        """Проверить наличие префикса, вернуть JSON/redirect при ошибке."""
        if prefix:
            return None
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'balloon': message}), 400
        flash(message, 'danger')
        return redirect('/')


#######
    def create_repo_in_api(api_url: str, payload: dict) -> requests.Response:
        """Создать репозиторий в Aptly API."""
        return requests.post(f"{api_url}/repos", json=payload)


#######
    def publish_repo(api_url: str, cfg: dict, name: str, prefix: str, distribution: str) -> requests.Response:
        """Опубликовать репозиторий через Aptly API."""
        encoded_prefix = prefix.replace('_', '__').replace('/', '_')
        url = f"{api_url}/publish/{encoded_prefix}"
        publish_payload = {
            "SourceKind": "local",
            "Sources": [{"Name": name}],
            "Architectures": (cfg.get('PUBLISH_ARCH') or 'amd64').split(','),
            "Distribution": distribution or ''
        }
        if cfg.get('PUBLISH_ORIGIN'):
            publish_payload['Origin'] = cfg['PUBLISH_ORIGIN']
        if cfg.get('PUBLISH_LABEL'):
            publish_payload['Label'] = cfg['PUBLISH_LABEL']
        return requests.post(url, json=publish_payload)


#######
    @app.route('/create_repo', methods=['POST'])
    @login_required
    def create_repo():
        _t = inject_i18n()['_t']
        name = request.form.get('name')
        comment = request.form.get('comment')
        distribution = request.form.get('distribution')
        component = request.form.get('component')
        prefix = request.form.get('prefix')

        if not name or not component:
            flash(_t('flash.create_repo_missing_fields'))
            return redirect('/')

        # Получаем имя текущего пользователя
        username = getattr(current_user, 'username', None)

        cfg = _load_config()

        # Проверка разрешённых кодовых имён
        allowed_raw = (cfg.get('ALLOWED_CODENAME', '') or '').strip().lower()
        allowed = [s for s in (allowed_raw.split(',') if allowed_raw else []) if s]
        ok, base = validate_codename(name, component, allowed)
        if not ok:
            display_name = base
            msg = _t('flash.create_repo_codename_forbidden').format(display_name=display_name)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'balloon': msg}), 400
            flash(msg, 'danger')
            return redirect('/')

        # Проверка префикса
        prefix_check = require_prefix(prefix, _t('flash.publish_prefix_required'))
        if prefix_check:
            return prefix_check

        # Создание репозитория
        payload = {
            'Name': name,
            'Comment': comment or '',
            'DefaultDistribution': distribution or '',
            'DefaultComponent': component or ''
        }
        api_url = get_api_url()

        try:
            resp = create_repo_in_api(api_url, payload)
            result = resp.text

            # Если создание репозитория не успешно, вернуть ошибку и не логировать как успешную команду
            if resp.status_code not in (200, 201, 202, 204):
                # Краткая запись причины в командный журнал для аудита
                command_logging(
                    level='ERROR',
                    name='CREATE_REPO_FAIL',
                    code=resp.status_code,
                    body=(result or '')[:400],
                    username=username
                )
                # Подробный стек/диагностика не пишем из роутов — только краткая причина в commands.log
                # вернуть тело ответа как текст ошибки (фронтенд показывает сообщение)
                return result, resp.status_code

            # Публикация
            publish_resp = publish_repo(api_url, cfg, name, prefix, distribution or '')
            meta_note = []
            if cfg.get('PUBLISH_ORIGIN'):
                meta_note.append(f"Origin={cfg['PUBLISH_ORIGIN']}")
            if cfg.get('PUBLISH_LABEL'):
                meta_note.append(f"Label={cfg['PUBLISH_LABEL']}")
            meta_str = (" (" + ", ".join(meta_note) + ")") if meta_note else ''

            # Логировать только если publish тоже успешен; при неуспехе — краткая причина в commands.log
            if publish_resp.status_code in (200, 201, 202, 204):
                command_logging(
                    level='INFO',
                    name='CREATE_REPO',
                    extra={'name': name, 'prefix': prefix, 'distribution': distribution or ''},
                    username=username
                )
            else:
                command_logging(
                    level='ERROR',
                    name='CREATE_REPO_PUBLISH_FAIL',
                    code=publish_resp.status_code,
                    body=(publish_resp.text or '')[:400],
                    extra={'name': name, 'prefix': prefix, 'distribution': distribution or ''},
                    username=username
                )
                # Не пишем подробности в app.log из роутов
            result += f"\n---\n(Publish to {prefix} distribution {distribution or ''}{meta_str})\n" + publish_resp.text
            return result, publish_resp.status_code

        except Exception as e:
            # Записать исключение в журнал команд для аудита
            command_logging(
                level='ERROR',
                name='CREATE_REPO_EXCEPTION',
                body=str(e),
                extra={'name': name},
                username=username
            )
            msg = _t('flash.connection_error')
            flash(msg, 'danger')
            return f'{msg} {e}', 500
