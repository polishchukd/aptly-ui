# Makefile

#!make
.PHONY: help install venv run build start up stop down logs cli clean print-%

help:
	@echo "Available targets:"
	@echo "  install/venv  Create virtualenv and install dependencies"
	@echo "  run           Run Flask app locally (uses venv if present)"
	@echo "  build         Build Docker image ($(IMAGE))"
	@echo "  start/up      Run Docker container, bind :$(PORT) and mount ./$(UI_CONF)"
	@echo "  stop/down     Stop running container ($(APP_NAME))"
	@echo "  logs          Tail logs from running container"
	@echo "  cli           Open an interactive shell in the running container"
	@echo "  clean         Remove caches and temporary files"

# Базовые переменные
DOCKER = $(shell command -v docker)
USE_TTY = -ti

VENV ?= .venv

# Переменные проекта
DOCKERFILE = docker/Dockerfile
APP_NAME = aptly-ui
IMAGE = $(APP_NAME):latest
PORT = 5000
UI_CONF = aptly-ui.conf

# Параметры для запуска контейнеров
PARAMS = --volume "${PWD}":/app \
		-p $(PORT):5000 \
		--volume=$(PWD)/$(UI_CONF):/app/$(UI_CONF) \
		--volume=$(PWD)/users.json:/app/users.json \
		--volume=$(PWD)/logs:/app/logs \
		--rm ${USE_TTY}

# Цель для вывода значений переменных (debugging)
# Использование: make print-VARIABLE_NAME
print-%:
	@echo '$* = $($*)'

# Подготовка окружения для запуска приложения
install venv:
	@test -d $(VENV) || python3 -m venv $(VENV)
	@. $(VENV)/bin/activate; pip install --upgrade pip
	@. $(VENV)/bin/activate; pip install -r requirements.txt

# Запуск приложения в режиме debug
run: install
	@echo "Starting app on http://127.0.0.1:5000"
	@. $(VENV)/bin/activate; FLASK_RUN_PORT=5000 python app.py

# Сборка Docker образа
build:
	@$(info "Build ${IMAGE}")
	@${DOCKER} build --tag=${IMAGE} -f ${DOCKERFILE} ./

# Запуск контейнера
start up:
	@$(info "Run ${IMAGE}")
	@${DOCKER} run ${PARAMS} --detach --name ${APP_NAME} ${IMAGE}

# Остановка контейнера
stop down:
	@$(info "Stop ${APP_NAME}")
	@${DOCKER} stop ${APP_NAME} || true
	@${DOCKER} rm ${APP_NAME} || true

# Логи контейнера
logs:
	@${DOCKER} logs -f ${APP_NAME}

# Интерактивная сессия в контейнере
cli:
	@${DOCKER} exec -it ${APP_NAME} bash

# Очистка
clean:
	@$(info "Cleaning...")
	@rm -rf $(VENV)
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name ".DS_Store" -delete
