# auth.py

import bcrypt
import json
from flask import request, redirect, url_for, flash, render_template, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app_logging import auth_logging
from users_utils import add_user as uu_add_user, delete_user as uu_delete_user, edit_user as uu_edit_user, root_required, UserRoleEnum
from flask import Flask
from typing import Callable
from i18n import inject_i18n


def init_auth_routes(app: Flask, users: dict, users_db: str, load_users: Callable[[str], dict]) -> None:


#######
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        _t = inject_i18n()['_t']
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            user = users.get(username)
            if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
                login_user(user)
                try:
                    uid = user.get_id() if hasattr(user, 'get_id') else getattr(user, 'id', '')
                except Exception:
                    uid = getattr(user, 'id', '')
                auth_logging(
                    level='INFO',
                    name='LOGIN_SUCCESS',
                    username=getattr(user, 'username', ''),
                    extra={'ip': request.remote_addr}
                )
                return redirect(url_for('index'))
            else:
                # Зафиксировать неудачную попытку входа
                auth_logging(
                    level='ERROR',
                    name='LOGIN_FAILED',
                    username=username or '<empty>',
                    extra={'ip': request.remote_addr}
                )
                flash(_t('flash.invalid_credentials'), 'danger')
                return render_template('login.html')
        return render_template('login.html')


#######
    @app.route('/logout')
    @login_required
    def logout():
        # Выйти из системы, если current_user доступен
        try:
            username = getattr(current_user, 'username', '') or ''
        except Exception:
            username = ''
        auth_logging(
            level='INFO',
            name='LOGOUT',
            username=username,
            extra={'ip': request.remote_addr}
        )
        logout_user()
        return redirect(url_for('login'))


#######
    @app.route('/api/users', methods=['GET'])
    @login_required
    def api_users():
        users = load_users(users_db)
        # Отдаём базовую информацию о пользователях (без password_hash)
        result = {}
        for username, user in users.items():
            result[username] = {
                'id': getattr(user, 'id', None),
                'root': getattr(user, 'root').value if hasattr(user, 'root') else 0,
                'perms': getattr(user, 'perms', {})
            }
        return jsonify(result)


#######
    @app.route('/add_user', methods=['POST'])
    @login_required
    @root_required
    def add_user():
        _t = inject_i18n()['_t']
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('confirm_password', '')
        is_root = request.form.get('is_root') == 'on'  # Проверяем переключатель
        # Считываем переключатели прав по вкладкам (если присутствуют)
        perms = {
            'copy': request.form.get('perm_copy') == 'on',
            'create': request.form.get('perm_create') == 'on',
            'delete': request.form.get('perm_delete') == 'on',
            'delete_repo': request.form.get('perm_delete_repo') == 'on',
            'upload': request.form.get('perm_upload') == 'on'
        }
        # Если установлен флаг полных прав — не полагаться на пришедшие чекбоксы (они могут быть disabled)
        if is_root:
            perms = None

        # Пароль может быть пустым — тогда меняются только права/root
        if not username:
            flash(_t('flash.missing_username'), 'danger')
            return redirect('/settings#users')
        if password or password_confirm:
            if not password or not password_confirm:
                flash(_t('flash.required_login_password'), 'danger')
                return redirect('/settings#users')
            if password != password_confirm:
                flash(_t('flash.password_mismatch'), 'danger')
                return redirect('/settings#users')

        try:
            root_level = UserRoleEnum.ROOT if is_root else UserRoleEnum.USER
            uu_add_user(users_db, username, password, root_level, perms)
        except ValueError as ve:
            flash(_t('flash.data_error') + ': ' + str(ve), 'danger')
            return redirect('/settings#users')
        except Exception as e:
            flash(_t('flash.save_error') + f': {e}', 'danger')
            return redirect('/settings#users')

        try:
            new_users = load_users(users_db)
            users.clear()
            users.update(new_users)
        except Exception:
            pass
        flash(_t('flash.user_created'), 'success')
        return redirect('/settings#users')


#######
    @app.route('/delete_user', methods=['POST'])
    @login_required
    @root_required
    def delete_user():
        _t = inject_i18n()['_t']
        username = request.form.get('username', '').strip()
        if not username:
            flash(_t('flash.missing_username'), 'danger')
            return redirect('/settings#users')

        if username == 'admin':
            flash(_t('flash.cannot_delete_admin', 'Нельзя удалить пользователя admin'), 'danger')
            return redirect('/settings#users')

        try:
            uu_delete_user(users_db, username)
        except ValueError as ve:
            flash(_t('flash.user_not_found'), 'danger')
            return redirect('/settings#users')
        except Exception as e:
            flash(_t('flash.delete_error') + f': {e}', 'danger')
            return redirect('/settings#users')

        try:
            new_users = load_users(users_db)
            users.clear()
            users.update(new_users)
        except Exception:
            pass
        flash(_t('flash.user_deleted'), 'success')
        return redirect('/settings#users')


#######
    @app.route('/edit_user', methods=['POST'])
    @login_required
    @root_required
    def edit_user():
        _t = inject_i18n()['_t']
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('confirm_password', '')
        is_root = request.form.get('is_root') == 'on'
        # Также ожидаем переключатели прав, если админ их передал
        perms = {
            'copy': request.form.get('perm_copy') == 'on',
            'create': request.form.get('perm_create') == 'on',
            'delete': request.form.get('perm_delete') == 'on',
            'delete_repo': request.form.get('perm_delete_repo') == 'on',
            'upload': request.form.get('perm_upload') == 'on'
        }
        # if is_root:
        #     perms = None
        # if not username or not password or not password_confirm:
        #     flash(_t('flash.required_login_password'), 'danger')
        #     return redirect('/settings#users')
        if password != password_confirm:
            flash(_t('flash.password_mismatch'), 'danger')
            return redirect('/settings#users')

        try:
            # Обновляем пароль и, если нужно, root и perms
            root_level = UserRoleEnum.ROOT if is_root else UserRoleEnum.USER
            # Если пароль не указан — передаём None чтобы поменять только права/root
            pwd = password if password else None
            uu_edit_user(users_db, username, pwd, root_level, perms)
        except ValueError as ve:
            flash(_t('flash.user_not_found'), 'danger')
            return redirect('/settings#users')
        except Exception as e:
            flash(_t('flash.save_error') + f': {e}', 'danger')
            return redirect('/settings#users')

        try:
            new_users = load_users(users_db)
            users.clear()
            users.update(new_users)
        except Exception:
            pass
        if password:
            flash(_t('flash.user_password_updated'), 'success')
        else:
            flash(_t('flash.user_updated'), 'success')
        return redirect('/settings#users')
