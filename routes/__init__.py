# __init__.py

from .auth import init_auth_routes
from .health import init_health_routes
from .settings import init_settings_routes
from .lang import init_lang_routes
from .create_repo import init_create_repo_routes
from .copy_package import init_copy_package_routes
from .delete_package import init_delete_package_routes
from .delete_repo import init_delete_repo_routes
from .upload_package import init_upload_package_routes
from .api_requests import init_api_requests_routes
from flask import Flask
from typing import Callable


def init_routes(app: Flask, users: dict, get_api_url: Callable[[], str], users_db: str, load_users: Callable[[str], dict]) -> None:
    init_auth_routes(app, users, users_db, load_users)
    init_health_routes(app, get_api_url)
    init_settings_routes(app, users, users_db, load_users)
    init_lang_routes(app, users)
    init_create_repo_routes(app, get_api_url)
    init_copy_package_routes(app, get_api_url)
    init_delete_package_routes(app, get_api_url)
    init_delete_repo_routes(app, get_api_url)
    init_upload_package_routes(app, get_api_url)
    init_api_requests_routes(app, get_api_url)
