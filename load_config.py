# load_config.py

import os
import configparser


# ===================================================================================================
# Функция _load_config
# Назначение: однократно при вызове прочитать файл конфигурации aptly-ui.conf (секцию DEFAULT)
# и сформировать словарь с ключами, используемыми приложением (API_URL, PUBLISH_ARCH,
# PUBLISH_ORIGIN, PUBLISH_LABEL). Для каждого параметра предусмотрен резервный источник
# (переменные окружения или значения по умолчанию). Отсутствие файла aptly-ui.conf не считается
# критической ошибкой – возвращаются безопасные значения. Не кэшируем результат умышленно,
# чтобы изменения в файле могли применяться без рестарта (при последующих запросах).
# Возвращает: dict.
# Побочных эффектов (логирование, исключения наружу) — нет; любые ошибки чтения игнорируются.
# Ограничения: файл читается целиком через configparser; отсутствует поддержка секций кроме DEFAULT.
# ===================================================================================================
def _load_config() -> dict[str, str]:
    cfg = configparser.ConfigParser()
    try:
        cfg.read('aptly-ui.conf')
    except Exception:
        pass
    app_section = cfg['APP'] if 'APP' in cfg else (cfg['DEFAULT'] if 'DEFAULT' in cfg else {})
    log_section = cfg['LOGGING'] if 'LOGGING' in cfg else (cfg['DEFAULT'] if 'DEFAULT' in cfg else {})

    def _get(section, key, env_default=''):
        return section.get(key, os.environ.get(key, env_default)).strip()

    return {
        'API_URL': _get(app_section, 'API_URL', ''),
        'PUBLISH_ARCH': _get(app_section, 'PUBLISH_ARCH', 'amd64'),
        'PUBLISH_ORIGIN': _get(app_section, 'PUBLISH_ORIGIN', ''),
        'ALLOWED_CODENAME': _get(app_section, 'ALLOWED_CODENAME', ''),
        'PUBLISH_LABEL': _get(app_section, 'PUBLISH_LABEL', ''),
        'APP_VERSION': _get(app_section, 'APP_VERSION', os.environ.get('APP_VERSION', '')),
        'LOG_LEVEL': _get(log_section, 'LOG_LEVEL', os.environ.get('LOG_LEVEL', 'INFO')).upper(),
        'LOG_MAX_BYTES': _get(log_section, 'LOG_MAX_BYTES', os.environ.get('LOG_MAX_BYTES', '0')),
        'LOG_BACKUP_COUNT': _get(log_section, 'LOG_BACKUP_COUNT', os.environ.get('LOG_BACKUP_COUNT', '5')),
    }
