"""Модуль аутентификации для ЕКЦ График."""
from __future__ import annotations

from functools import wraps

from fastapi import Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from .database import (
    get_user_credentials,
    create_user_credentials,
    update_user_password,
    hash_password,
    verify_password,
    init_credentials_for_all_employees,
    list_operator_profiles,
)

templates = Jinja2Templates(directory="app/templates")


def login_required(func):
    """Декоратор требует авторизации."""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        if not request.session.get("logged_in_user"):
            return RedirectResponse("/login", status_code=303)
        return await func(request, *args, **kwargs)
    return wrapper


def admin_required(func):
    """Декоратор требует прав администратора."""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        user_role = request.session.get("user_role")
        if user_role != "admin":
            return RedirectResponse("/my-schedule", status_code=303)
        return await func(request, *args, **kwargs)
    return wrapper


def is_employee(request: Request) -> bool:
    """Проверяет, авторизован ли пользователь как сотрудник."""
    return request.session.get("user_role") == "employee"


def is_admin(request: Request) -> bool:
    """Проверяет, авторизован ли пользователь как администратор."""
    return request.session.get("user_role") == "admin"


def get_current_user(request: Request) -> str | None:
    """Получает имя текущего пользователя."""
    return request.session.get("logged_in_user")


def init_auth() -> None:
    """Инициализирует учетные данные для всех сотрудников."""
    init_credentials_for_all_employees(hash_password)


async def process_login(request: Request, employee_name: str, password: str) -> tuple[bool, str]:
    """
    Обрабатывает вход в систему.
    Возвращает (success, message).
    """
    credentials = get_user_credentials(employee_name)

    if not credentials:
        return False, "Пользователь не найден"

    if verify_password(password, credentials["password_hash"]):
        request.session["logged_in_user"] = employee_name
        request.session["user_role"] = credentials["role"]
        return True, "Вход выполнен"

    return False, "Неверный пароль"


def process_logout(request: Request) -> None:
    """Обрабатывает выход из системы."""
    request.session.pop("logged_in_user", None)
    request.session.pop("user_role", None)


async def change_user_password(request: Request, current_password: str, new_password: str) -> tuple[bool, str]:
    """
    Меняет пароль текущего пользователя.
    Возвращает (success, message).
    """
    user = get_current_user(request)
    if not user:
        return False, "Пользователь не авторизован"

    credentials = get_user_credentials(user)
    if not credentials:
        return False, "Пользователь не найден"

    if not verify_password(current_password, credentials["password_hash"]):
        return False, "Неверный текущий пароль"

    if len(new_password) < 6:
        return False, "Пароль должен быть не менее 6 символов"

    update_user_password(user, new_password)
    return True, "Пароль изменен"
