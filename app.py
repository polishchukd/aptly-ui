
import os
import secrets
from flask import Flask, render_template
from flask_login import LoginManager, login_required
from users_utils import ensure_users_db, load_users, find_user_by_id, User
from load_config import _load_config
from app_logging import app_logging_conf, startup_logging
from i18n import inject_i18n
from app_utils import get_api_url
from routes import init_routes


app = Flask(__name__)


# Всегда генерируем случайный секрет при старте.
# Для разлогинивания пользователей при перезапуске.
app.secret_key = secrets.token_urlsafe(32)


# Настройка Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# Имя файла хранения пользователей (JSON).
USERS_DB = 'users.json'


# Обеспечение наличия файла пользователей
ensure_users_db(USERS_DB)
users: dict[str, "User"] = load_users(USERS_DB)


# Настройка логгера приложения
@login_manager.user_loader
def load_user(user_id: int) -> User | None:
    return find_user_by_id(users, user_id)


# Инициализация логов при импорте
app_logging_conf()


# Логирование старта приложения
startup_logging()


# Инъекция переводов в контекст шаблонов
app.context_processor(inject_i18n)


# Фавикон
@app.route('/favicon.ico')
def favicon() -> object:
    from flask import send_from_directory
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')


# =====================================================================================================
# Вьюха index
# Назначение: корневая страница UI. Собирает конфигурацию для фронтенда (API URL,
# архитектуры публикации, Origin, Label) и передаёт их в шаблон aptly-ui.html. Выполняет
# раннюю валидацию наличия API_URL (через get_api_url) — при отсутствии выбрасывается исключение,
# которое может быть перехвачено глобальными обработчиками Flask (в отладочном режиме отдаст трейсбек).
# =====================================================================================================
@app.route('/')
@login_required
def index() -> str:
    cfg = _load_config()
    api_url = get_api_url()
    publish_arch = cfg['PUBLISH_ARCH'] or 'amd64,i386'
    return render_template(
        'aptly-ui.html',
        api_url=api_url,
        publish_arch=publish_arch,
        publish_origin=cfg.get('PUBLISH_ORIGIN',''),
        publish_label=cfg.get('PUBLISH_LABEL',''),
        app_version=cfg.get('APP_VERSION','')
    )


# Инициализация всех роутов
init_routes(app, users, get_api_url, USERS_DB, load_users)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
