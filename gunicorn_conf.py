import multiprocessing
import os
import json

# Чтение настроек из окружения (Dockerfile задаёт значения по умолчанию)
def getenv_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default

def getenv_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.lower() in ('1','true','yes','on')

worker_class = os.getenv('GUNICORN_WORKER_CLASS', 'gthread')
threads = getenv_int('GUNICORN_THREADS', 1)
workers = getenv_int('GUNICORN_WORKERS', max(2, multiprocessing.cpu_count() // 2))
timeout = getenv_int('GUNICORN_TIMEOUT', 150)
graceful_timeout = getenv_int('GUNICORN_GRACEFUL_TIMEOUT', 30)
keepalive = getenv_int('GUNICORN_KEEPALIVE', 30)
preload_app = getenv_bool('GUNICORN_PRELOAD', True)
max_requests = getenv_int('GUNICORN_MAX_REQUESTS', 1000)
max_requests_jitter = getenv_int('GUNICORN_MAX_REQUESTS_JITTER', 100)
loglevel = os.getenv('GUNICORN_LOGLEVEL', 'info')

bind = '0.0.0.0:5000'
accesslog = '-'  # stdout
errorlog = '-'   # stderr

# Базовые разумные значения по умолчанию для gthread
if worker_class == 'gthread':
    threads = max(threads, 1)  # обеспечить минимально разумное число потоков

# Опционально: ограничение длины строки запроса / заголовков (безопасность)
limit_request_line = 4094
limit_request_fields = 200
limit_request_field_size = 8190

# Хук: логирование после форка воркера
def post_fork(server, worker):  # noqa: D401
    server.log.info(f"Запущен воркер (pid: {worker.pid})")

def on_starting(server):  # Вызывается непосредственно перед инициализацией мастера
    config_snapshot = {
        'worker_class': worker_class,
        'workers': workers,
        'threads': threads,
        'timeout': timeout,
        'graceful_timeout': graceful_timeout,
        'keepalive': keepalive,
        'preload_app': preload_app,
        'max_requests': max_requests,
        'max_requests_jitter': max_requests_jitter,
        'loglevel': loglevel,
        'limit_request_line': limit_request_line,
        'limit_request_fields': limit_request_fields,
        'limit_request_field_size': limit_request_field_size,
    }
    server.log.info('Effective Gunicorn configuration: ' + json.dumps(config_snapshot, ensure_ascii=False, indent=4))
