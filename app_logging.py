# app_logging.py

import logging
from pathlib import Path
from typing import Any
from logging.handlers import RotatingFileHandler
from datetime import datetime
from load_config import _load_config


# =============================
# Функция app_logging
# Параметры конфигурации:
#   LOG_LEVEL        – уровень (DEBUG, INFO, WARNING, ERROR, CRITICAL; по умолчанию INFO)
#   LOG_MAX_BYTES    – размер файла до ротации (байты). 0 или недопустимое значение -> без ротации.
#   LOG_BACKUP_COUNT – количество резервных файлов при ротации (по умолчанию 5)
# Логические каналы:
#   app       – технические события и ошибки
#   commands  – высокоуровневые пользовательские операции (create/copy/delete/publish)
# =============================
LOG_DIR = Path('logs')
LOG_DIR.mkdir(exist_ok=True)
LOG_FORMAT = '%(asctime)s | %(levelname)s | %(username)s | %(message)s'
DATEFMT = '%Y-%m-%d %H:%M:%S'

app_logger = logging.getLogger('app')
commands_logger = logging.getLogger('commands')
auth_logger = logging.getLogger('auth')


#########
def _create_log_handler(logger_name: str, config: dict[str, Any]) -> logging.Handler:
    """Создает обработчик логов на основе конфигурации."""
    def _parse_int(val, default):
        try:
            return int(val)
        except Exception:
            return default

    max_bytes = _parse_int(config.get('LOG_MAX_BYTES', '0'), 0)
    backup_count = _parse_int(config.get('LOG_BACKUP_COUNT', '5'), 5)

    if max_bytes > 0:
        handler = RotatingFileHandler(
            LOG_DIR / f'{logger_name}.log',
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
    else:
        handler = logging.FileHandler(
            LOG_DIR / f'{logger_name}.log',
            encoding='utf-8'
        )

    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATEFMT))
    return handler


#########
def startup_logging() -> None:
    cfg = _load_config()
    # Формируем строку с ключевыми параметрами. Можно расширить при появлении новых.
    fields = [
        f"APP_VERSION={cfg.get('APP_VERSION','')}\n",
        f"API_URL={cfg.get('API_URL','')}\n",
        f"PUBLISH_ARCH={cfg.get('PUBLISH_ARCH','')}\n",
        f"PUBLISH_ORIGIN={cfg.get('PUBLISH_ORIGIN','')}\n",
        f"PUBLISH_LABEL={cfg.get('PUBLISH_LABEL','')}\n",
        f"LOG_LEVEL={cfg.get('LOG_LEVEL','')}\n",
        f"LOG_MAX_BYTES={cfg.get('LOG_MAX_BYTES','')}\n",
        f"LOG_BACKUP_COUNT={cfg.get('LOG_BACKUP_COUNT','')}\n",
        f"---------------------------------------------------",
    ]
    app_logger.info('APP_START time=%s %s', datetime.utcnow().isoformat() + 'Z', ' '.join(fields), extra={'username': 'system'})


#########
def app_logging_conf() -> None:
    cfg = _load_config()
    level_name = cfg.get('LOG_LEVEL', 'INFO')
    level = getattr(logging, level_name, logging.INFO)

    for logger in (app_logger, commands_logger, auth_logger):
        # Устанавливаем уровень логирования
        logger.setLevel(level)
        # Удаляем старые хендлеры
        if logger.handlers:
            for h in list(logger.handlers):
                logger.removeHandler(h)

        # Создаем и добавляем новый обработчик
        handler = _create_log_handler(logger.name, cfg)
        logger.addHandler(handler)


#########
def command_logging(message: str | None = None, *, level: str = 'INFO', name: str | None = None, code: int | None = None, body: str | None = None, extra: dict | None = None, username: str | None = None) -> None:
    # Определяем уровень логирования
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Простой проход, когда передано только сообщение
    if message is not None and not any((name, code, body, extra, username)):
        commands_logger.log(log_level, message, extra={'username': username})
        return

    parts: list[str] = []
    if message:
        parts.append(str(message))
    if name:
        parts.append(f'{name}')
    if code is not None:
        parts.append(f'code={code}')
    if body is not None:
        compact = ' '.join(str(body).split())
        parts.append(f'body={compact}')
    if extra:
        parts.append(' '.join(f'{k}={v}' for k, v in extra.items()))

    msg = ' '.join(parts).strip()
    if msg:
        commands_logger.log(log_level, msg, extra={'username': username})


#########
def auth_logging(message: str | None = None, *, level: str = 'INFO', name: str | None = None, code: int | None = None, body: str | None = None, extra: dict | None = None, username: str | None = None) -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)

    if message is not None and not any((name, code, body, extra, username)):
        auth_logger.log(log_level, message, extra={'username': username})
        return

    parts: list[str] = []
    if message:
        parts.append(str(message))
    if name:
        parts.append(f'{name}')
    if code is not None:
        parts.append(f'code={code}')
    if body is not None:
        compact = ' '.join(str(body).split())
        parts.append(f'body={compact}')
    if extra:
        parts.append(' '.join(f'{k}={v}' for k, v in extra.items()))

    msg = ' '.join(parts).strip()
    if msg:
        auth_logger.log(log_level, msg, extra={'username': username})
