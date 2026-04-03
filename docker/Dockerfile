FROM python:3.11-slim

LABEL author="Dmitriy Polishchuk"
LABEL description="Aptly-UI"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN \
    apt-get update && \
    apt-get install -y --no-install-recommends \
       openssh-client ca-certificates && \
    apt-get autoremove --quiet --yes --purge && \
    rm -rf /var/lib/apt/lists/*

## Настройка Python окружения
ENV \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    USER=aptly \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

COPY requirements.txt ./

RUN \
    pip install --no-cache-dir -r requirements.txt

## Копируем код приложения
COPY app.py ./
COPY gunicorn_conf.py ./
COPY aptly-ui.conf ./
COPY users_utils.py ./
COPY app_logging.py ./
COPY app_utils.py ./
COPY i18n.py ./
COPY load_config.py ./
COPY users.json ./
COPY routes ./routes
COPY templates ./templates
COPY static ./static
COPY i18n ./i18n

## Используем не-root пользователя для безопасности
RUN useradd -m ${USER} && chown -R ${USER}:${USER} /app
USER ${USER}

## Открываем порт Flask
EXPOSE 5000

## Примечание: примонтируйте aptly-ui.conf в /app/aptly-ui.conf при запуске контейнера
## Например: -v $(pwd)/aptly-ui.conf:/app/aptly-ui.conf

## Запуск через gunicorn для продакшена
CMD ["gunicorn", "-c", "gunicorn_conf.py", "app:app"]
