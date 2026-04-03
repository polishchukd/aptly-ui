# users_utils.py

import os
import json
import time
import bcrypt
import logging
from pathlib import Path
from typing import Dict, Optional
from flask_login import UserMixin, current_user
from dataclasses import dataclass, field
from functools import wraps
from flask import flash, redirect, url_for
from enum import Enum
from i18n import inject_i18n


class UserRoleEnum(Enum):
    """Роли пользователей в системе."""
    USER = 0      # Обычный пользователь - только просмотр
    ROOT = 1      # Администратор - полные права


# Простая модель пользователя
@dataclass
class User(UserMixin):
    id: int
    username: str
    password_hash: str = field(repr=False)
    root: UserRoleEnum = UserRoleEnum.USER  # По умолчанию обычный пользователь
    # Права доступа к вкладкам: словарь с ключами вкладок -> bool
    perms: dict = field(default_factory=dict, repr=False)

    def get_id(self) -> str:
        # Flask-Login ожидает строковый id
        return str(self.id)

    def is_root(self) -> bool:
        """Проверяет, является ли пользователь администратором с полными правами."""
        return self.root == UserRoleEnum.ROOT

    def has_tab_access(self, tab_name: str) -> bool:
        """Проверяет доступ к вкладке: у рута всегда доступ, иначе смотрим в perms."""
        try:
            if self.is_root():
                return True
            return bool(self.perms.get(tab_name, False))
        except Exception:
            return False


#######
def ensure_users_db(users_db: str) -> None:
    """Создаёт db пользователей с дефолтным admin/admin, если его нет."""
    p = Path(users_db)
    logger = logging.getLogger('app')

    # Если файл существует, проверим, валиден ли он как JSON — если да, ничего не делаем.
    if p.exists():
        try:
            with open(p, 'r', encoding='utf-8') as f:
                json.load(f)
            return
        except Exception:
            # Некорректный JSON — сохраняем бэкап и продолжим создание нового файла
            try:
                ts = int(time.time())
                backup = p.with_name(f"{p.name}.bak_{ts}")
                p.rename(backup)
                logger.exception('Users file %s is invalid JSON; backed up to %s', users_db, backup)
            except Exception:
                logger.exception('Users file %s is invalid JSON and backup failed', users_db)

    try:
        default_password = 'admin'
        hashed = bcrypt.hashpw(default_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        # Используем числовое значение Enum для сериализации в JSON
        # Права по-умолчанию: у рута все вкладки открыты
        default_perms = {
            'copy': True,
            'create': True,
            'delete': True,
            'delete_repo': True,
            'upload': True
        }
        data = {'admin': {'id': 1, 'password_hash': hashed, 'root': UserRoleEnum.ROOT.value, 'perms': default_perms}}
        # Записываем в временный файл и затем атомарно переименовываем
        tmp = p.with_name(p.name + '.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        try:
            os.replace(tmp, p)
        except Exception:
            # Падение replace — попытаемся простым открытием
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        try:
            os.chmod(p, 0o600)
        except Exception:
            logger.debug('Could not chmod users file %s', users_db, exc_info=True)
        logger.info('Created default users file %s with admin user', users_db)
    except Exception:
        logger.exception('Failed to create users file %s', users_db)


#######
def load_users(users_db: str) -> dict[str, User]:
    """Загружает пользователей."""
    logger = logging.getLogger('app')
    try:
        p = Path(users_db)
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
            users = {}
            for username, info in data.items():
                # Сохраняем совместимость со старым форматом — если 'perms' нет,
                # формируем его из уровня root: у root все права, у обычного — только delete
                root_level = UserRoleEnum(info.get('root', UserRoleEnum.USER.value))
                perms = info.get('perms')
                if perms is None:
                    if root_level == UserRoleEnum.ROOT:
                        perms = {k: True for k in ('copy', 'create', 'delete', 'delete_repo', 'upload')}
                    else:
                        perms = {'delete': True}
                user = User(
                    id=info['id'],
                    username=username,
                    password_hash=info['password_hash'],
                    root=root_level,
                    perms=perms
                )
                users[username] = user
            logger.debug('Loaded %d users from %s', len(users), users_db)
            return users
    except Exception:
        logger.exception('Failed to load users from %s', users_db)
        return {}


#######
def save_users_db(users_db: str, users_dict: dict) -> None:
    """
    Сохраняет пользователей в db
    (сопоставление имени пользователя -> {id, password_hash, root}) в файл.
    """
    logger = logging.getLogger('app')
    p = Path(users_db)
    try:
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(users_dict, f, ensure_ascii=False, indent=2)
        logger.debug('Saved %d users to %s', len(users_dict), users_db)
    except Exception:
        logger.exception('Failed to save users to %s', users_db)
        raise


#######
def add_user(users_db: str, username: str, password: str, root: UserRoleEnum = UserRoleEnum.USER, perms: dict[str, bool] | None = None) -> None:
    """
    Добавляет нового пользователя в users_db. Вызывает ValueError при ошибках валидации.
    Эта функция синхронная и минимальная; вызывающие должны обрабатывать исключения и
    представлять удобные для пользователя сообщения.
    """
    logger = logging.getLogger('app')
    username = (username or '').strip()
    if not username or not password:
        logger.warning('Attempt to add user with empty username or password')
        raise ValueError('username and password required')

    logger.info('Adding user %s with root=%s', username, root.name)
    # Загрузка существующих пользователей
    try:
        with open(users_db, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {}

    if username in data:
        logger.warning('User %s already exists', username)
        raise ValueError('user exists')

    existing_ids = [info.get('id', 0) for info in data.values()]
    new_id = max(existing_ids or [0]) + 1
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    # Если perms не переданы — по-умолчанию: у root все права, у user только copy
    if perms is None:
        if root == UserRoleEnum.ROOT:
            perms = {k: True for k in ('copy', 'create', 'delete', 'delete_repo', 'upload')}
        else:
            perms = {'copy': True}

    data[username] = {'id': new_id, 'password_hash': password_hash, 'root': root.value, 'perms': perms}
    save_users_db(users_db, data)
    logger.info('User %s added with id %d and root=%s', username, new_id, root.name)


#######
def delete_user(users_db: str, username: str) -> None:
    """Удаляет пользователя."""
    logger = logging.getLogger('app')
    username = (username or '').strip()
    if not username:
        logger.warning('delete_user called with empty username')
        raise ValueError('username required')
    logger.info('Deleting user %s', username)
    try:
        with open(users_db, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {}
    if username in data:
        del data[username]
        save_users_db(users_db, data)
        logger.info('User %s deleted', username)
    else:
        logger.warning('User %s not found for deletion', username)
        raise ValueError('user not found')


#######
def edit_user(users_db: str, username: str, password: Optional[str] = None, root: Optional[UserRoleEnum] = None, perms: dict[str, bool] | None = None) -> None:
    """Изменяет пользователя.
    Поддерживает смену пароля (если указан), уровня root (если указан), и прав perms (если указан).
    """
    logger = logging.getLogger('app')
    username = (username or '').strip()
    if not username:
        logger.warning('edit_user called with missing username')
        raise ValueError('username required')
    logger.info('Editing user %s', username)
    try:
        with open(users_db, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {}
    if username not in data:
        logger.warning('User %s not found for edit', username)
        raise ValueError('user not found')

    if password:
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        data[username]['password_hash'] = password_hash
        logger.info('Password updated for user %s', username)

    if root is not None:
        data[username]['root'] = root.value
        # если не было perms — при смене root нужно обеспечить правильность perms
        if 'perms' not in data[username] or data[username].get('perms') is None:
            data[username]['perms'] = {k: True for k in ('copy', 'create', 'delete', 'delete_repo', 'upload')} if root == UserRoleEnum.ROOT else {'delete': True}
        logger.info('Root flag updated for user %s -> %s', username, root.name)

    if perms is not None:
        data[username]['perms'] = perms
        logger.info('Permissions updated for user %s -> %s', username, perms)

    save_users_db(users_db, data)


#######
def find_user_by_id(users: Dict[str, User], user_id: int) -> Optional[User]:
    """Поиск пользователя по id."""
    for user in users.values():
        if str(user.id) == str(user_id):
            return user
    return None


#######
def root_required(f):
    """Декоратор для проверки прав администратора."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if not hasattr(current_user, 'is_root') or not current_user.is_root():
            _t = inject_i18n()['_t']
            flash(_t('flash.insufficient_permissions', 'Insufficient permissions to perform this action'), 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function
