# settings.py

from flask import flash, redirect, url_for, render_template, request, Flask
from flask_login import login_required, current_user
from load_config import _load_config
from users_utils import root_required
import configparser
from i18n import inject_i18n
from typing import Callable


def init_settings_routes(app: Flask, users: dict, users_db: str, load_users: Callable[[str], dict]) -> None:


#######
    @app.route('/settings', methods=['GET', 'POST'])
    @login_required
    @root_required
    def settings():
        config_path = 'aptly-ui.conf'
        # Группировать ключи по секциям
        app_keys = ['API_URL', 'APP_VERSION', 'PUBLISH_ARCH', 'PUBLISH_ORIGIN', 'PUBLISH_LABEL', 'ALLOWED_CODENAME']
        logging_keys = ['LOG_LEVEL', 'LOG_MAX_BYTES', 'LOG_BACKUP_COUNT']
        cfg = _load_config()
        tab = request.args.get('tab', '')
        if request.method == 'POST':
            parser = configparser.ConfigParser()
            # Прочитать существующий файл, если он присутствует, чтобы сохранить неизвестные секции/ключи
            try:
                parser.read(config_path)
            except Exception as e:
                # Если чтение не удалось, начать с пустого парсера
                # и записать ошибку в лог
                try:
                    app.logger.exception('Failed to read config file, starting with empty parser')
                except Exception:
                    # Если логгер недоступен — игнорируем, но не прерываем работу
                    pass
                parser = configparser.ConfigParser()

            if 'APP' not in parser:
                parser['APP'] = {}
            if 'LOGGING' not in parser:
                parser['LOGGING'] = {}

            # Обновлять только ключи, управляемые через интерфейс; остальные ключи/секции не трогать
            for key in app_keys:
                # Обновлять только те ключи, которые присутствуют в отправленной форме; остальные не изменять
                if key not in request.form:
                    continue
                val = request.form.get(key, '').strip()
                if key == 'ALLOWED_CODENAME':
                    parts = [s.strip().lower() for s in val.split(',') if s.strip()]
                    seen = set()
                    normalized = []
                    for p in parts:
                        if p not in seen:
                            seen.add(p)
                            normalized.append(p)
                    parser['APP'][key] = ','.join(normalized)
                else:
                    parser['APP'][key] = val

            for key in logging_keys:
                if key not in request.form:
                    continue
                parser['LOGGING'][key] = request.form.get(key, '').strip()

            try:
                with open(config_path, 'w') as f:
                    parser.write(f)
                _t = inject_i18n()['_t']
                flash(_t('flash.settings_saved'), 'success')
                cfg = _load_config()
            except Exception as e:
                # Записать стек ошибки в лог и показать flash-предупреждение
                try:
                    app.logger.exception('Failed to save settings')
                except Exception:
                    pass
                _t = inject_i18n()['_t']
                flash(_t('flash.save_error') + f': {e}', 'danger')
        try:
            current_users = load_users(users_db)
        except Exception as e:
            # Если не удалось загрузить файл пользователей — логируем и используем переданный словарь
            try:
                app.logger.exception('Failed to load users file, using fallback users dict')
            except Exception:
                pass
            current_users = users

        users_list = list(current_users.keys())
        return render_template('settings.html', config=cfg, users=current_users, users_list=users_list, tab=tab)
