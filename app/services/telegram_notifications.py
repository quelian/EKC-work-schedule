"""Централизованный модуль Telegram-уведомлений для всех событий системы ЕКЦ График."""
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_settings():
    """Читает настройки Telegram из БД."""
    try:
        from ..database import get_app_settings
        return get_app_settings([
            "telegram_bot_token",
            "telegram_chat_id",
            "telegram_backup_enabled",
        ])
    except Exception as e:
        logger.error(f"Telegram notifications: failed to read settings: {e}")
        return {}


def _is_enabled() -> bool:
    """Проверяет, включены ли Telegram-уведомления."""
    settings = _get_settings()
    return settings.get("telegram_backup_enabled", "false") == "true"


def _get_token_and_chat():
    """Возвращает (token, chat_id) или None, если не настроены."""
    settings = _get_settings()
    token = settings.get("telegram_bot_token", "").strip()
    chat_id = settings.get("telegram_chat_id", "").strip()
    if not token or not chat_id:
        return None, None
    return token, chat_id


def _send(text: str) -> bool:
    """Отправляет сообщение в Telegram, если уведомления включены."""
    if not _is_enabled():
        return False
    token, chat_id = _get_token_and_chat()
    if not token or not chat_id:
        return False
    try:
        from .telegram_bot import send_text_message
        return send_text_message(token, chat_id, text)
    except Exception as e:
        logger.error(f"Telegram notification send error: {e}")
        return False


def _now() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M")


def _emoji(event_type: str) -> str:
    """Возвращает эмодзи для типа события (используем HTML-safe символы)."""
    icons = {
        "login": "🔑",
        "logout": "🚪",
        "schedule_save": "📅",
        "schedule_delete": "🗑️",
        "employee_update": "👤",
        "employee_adjust": "⚖️",
        "employee_deactivate": "🔇",
        "vacation_save": "🏖️",
        "vacation_delete": "❌",
        "constraint_add": "🚫",
        "constraint_delete": "✅",
        "preference_add": "💭",
        "preference_delete": "💨",
        "monthly_pref_add": "📋",
        "monthly_pref_edit": "✏️",
        "monthly_pref_delete": "📋",
        "user_create": "🆕",
        "user_delete": "👋",
        "user_promote": "⬆️",
        "user_demote": "⬇️",
        "user_password_reset": "🔐",
        "password_change": "🔑",
        "settings_change": "⚙️",
        "server_start": "🚀",
        "server_stop": "🛑",
        "backup_success": "💾",
        "backup_failed": "⚠️",
        "bulk_add": "📦",
    }
    return icons.get(event_type, "📢")


# ---------------------------------------------------------------------------
# Public notification functions — call these from endpoints
# ---------------------------------------------------------------------------

def notify_login(username: str, user_role: str, ip: str) -> bool:
    """Уведомление об успешном входе в систему."""
    text = (
        f"{_emoji('login')} <b>Вход в систему</b>\n"
        f"├ Пользователь: <b>{username}</b>\n"
        f"├ Роль: {user_role}\n"
        f"├ IP: {ip}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_logout(username: str, user_role: str) -> bool:
    """Уведомление о выходе из системы."""
    text = (
        f"{_emoji('logout')} <b>Выход из системы</b>\n"
        f"├ Пользователь: <b>{username}</b>\n"
        f"├ Роль: {user_role}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_schedule_save(
    actor: str,
    employee_name: str,
    date: str,
    start_time: str,
    end_time: str,
    shift_type: str,
) -> bool:
    """Уведомление о сохранении смены."""
    text = (
        f"{_emoji('schedule_save')} <b>Смена сохранена</b>\n"
        f"├ Администратор: <b>{actor}</b>\n"
        f"├ Сотрудник: <b>{employee_name}</b>\n"
        f"├ Дата: {date}\n"
        f"├ Время: {start_time} — {end_time}\n"
        f"├ Тип: {shift_type}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_schedule_delete(actor: str, employee_name: str, date: str) -> bool:
    """Уведомление об удалении смены."""
    text = (
        f"{_emoji('schedule_delete')} <b>Смена удалена</b>\n"
        f"├ Администратор: <b>{actor}</b>\n"
        f"├ Сотрудник: <b>{employee_name}</b>\n"
        f"├ Дата: {date}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_employee_update(
    actor: str,
    name: str,
    original_name: Optional[str] = None,
    rate: Optional[float] = None,
    employee_type: Optional[str] = None,
) -> bool:
    """Уведомление об обновлении данных сотрудника."""
    changes = []
    if original_name and original_name != name:
        changes.append(f"Имя: {original_name} → <b>{name}</b>")
    if rate is not None:
        changes.append(f"Ставка: <b>{rate}</b>")
    if employee_type:
        changes.append(f"Тип: {employee_type}")

    changes_str = "\n├ ".join(changes) if changes else "данные обновлены"

    text = (
        f"{_emoji('employee_update')} <b>Сотрудник обновлён</b>\n"
        f"├ Администратор: <b>{actor}</b>\n"
        f"├ Сотрудник: <b>{name}</b>\n"
        f"├ Изменения: {changes_str}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_employee_adjustment(
    actor: str,
    employee_name: str,
    delta: float,
    new_adjustment: float,
    year: int,
    month: int,
) -> bool:
    """Уведомление о корректировке нормы часов сотрудника."""
    sign = "+" if delta > 0 else ""
    text = (
        f"{_emoji('employee_adjust')} <b>Корректировка часов</b>\n"
        f"├ Администратор: <b>{actor}</b>\n"
        f"├ Сотрудник: <b>{employee_name}</b>\n"
        f"├ Период: {month:02d}.{year}\n"
        f"├ Изменение: {sign}{delta} ч\n"
        f"├ Итого корректировка: {new_adjustment} ч\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_employee_deactivate(actor: str, employee_name: str) -> bool:
    """Уведомление о деактивации сотрудника."""
    text = (
        f"{_emoji('employee_deactivate')} <b>Сотрудник деактивирован</b>\n"
        f"├ Администратор: <b>{actor}</b>\n"
        f"├ Сотрудник: <b>{employee_name}</b>\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_vacation_save(
    actor: str,
    employee_name: str,
    start_date: str,
    end_date: str,
    note: str = "",
) -> bool:
    """Уведомление о сохранении отпуска."""
    note_line = f"\n├ Примечание: {note}" if note else ""
    text = (
        f"{_emoji('vacation_save')} <b>Отпуск сохранён</b>\n"
        f"├ Администратор: <b>{actor}</b>\n"
        f"├ Сотрудник: <b>{employee_name}</b>\n"
        f"├ Период: {start_date} — {end_date}{note_line}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_vacation_delete(actor: str, employee_name: str, vacation_id: int) -> bool:
    """Уведомление об удалении отпуска."""
    text = (
        f"{_emoji('vacation_delete')} <b>Отпуск удалён</b>\n"
        f"├ Администратор: <b>{actor}</b>\n"
        f"├ Сотрудник: <b>{employee_name}</b>\n"
        f"├ ID записи: {vacation_id}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_constraint_add(
    actor: str,
    employee_name: str,
    date: str,
    start_time: str,
    end_time: str,
    note: str = "",
) -> bool:
    """Уведомление о добавлении ограничения (учёба/недоступность)."""
    note_line = f"\n├ Примечание: {note}" if note else ""
    time_str = f" {start_time}—{end_time}" if start_time and end_time else ""
    text = (
        f"{_emoji('constraint_add')} <b>Ограничение добавлено</b>\n"
        f"├ Пользователь: <b>{actor}</b>\n"
        f"├ Сотрудник: <b>{employee_name}</b>\n"
        f"├ Дата: {date}{time_str}{note_line}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_constraint_delete(
    actor: str,
    employee_name: str,
    date: str,
    start_time: str,
    end_time: str,
) -> bool:
    """Уведомление об удалении ограничения."""
    text = (
        f"{_emoji('constraint_delete')} <b>Ограничение удалено</b>\n"
        f"├ Пользователь: <b>{actor}</b>\n"
        f"├ Сотрудник: <b>{employee_name}</b>\n"
        f"├ Дата: {date} {start_time}—{end_time}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_preference_add(
    actor: str,
    employee_name: str,
    date: str,
    preference_type: str,
    note: str = "",
) -> bool:
    """Уведомление о добавлении пожелания."""
    note_line = f"\n├ Примечание: {note}" if note else ""
    type_labels = {
        "not_before": "Не раньше",
        "not_after": "Не позже",
        "full_day": "Весь день",
        "other": "Другое",
    }
    type_label = type_labels.get(preference_type, preference_type)
    text = (
        f"{_emoji('preference_add')} <b>Пожелание добавлено</b>\n"
        f"├ Пользователь: <b>{actor}</b>\n"
        f"├ Сотрудник: <b>{employee_name}</b>\n"
        f"├ Дата: {date}\n"
        f"├ Тип: {type_label}{note_line}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_preference_delete(
    actor: str,
    employee_name: str,
    date: str,
    preference_type: str,
) -> bool:
    """Уведомление об удалении пожелания."""
    text = (
        f"{_emoji('preference_delete')} <b>Пожелание удалено</b>\n"
        f"├ Пользователь: <b>{actor}</b>\n"
        f"├ Сотрудник: <b>{employee_name}</b>\n"
        f"├ Дата: {date}\n"
        f"├ Тип: {preference_type}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_monthly_preference_add(
    actor: str,
    employee_name: str,
    year: int,
    month: int,
    preference_type: str,
    time_value: str = "",
    note: str = "",
) -> bool:
    """Уведомление о добавлении месячного пожелания."""
    type_labels = {
        "not_before": "Не раньше",
        "not_after": "Не позже",
        "other": "Другое",
    }
    type_label = type_labels.get(preference_type, preference_type)
    time_str = f" {time_value}" if time_value else ""
    note_line = f" | {note}" if note else ""
    text = (
        f"{_emoji('monthly_pref_add')} <b>Месячное пожелание</b>\n"
        f"├ Пользователь: <b>{actor}</b>\n"
        f"├ Сотрудник: <b>{employee_name}</b>\n"
        f"├ Период: {month:02d}.{year}\n"
        f"├ Тип: {type_label}{time_str}{note_line}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_monthly_preference_edit(
    actor: str,
    employee_name: str,
    year: int,
    month: int,
    old_type: str,
    new_type: str,
) -> bool:
    """Уведомление о редактировании месячного пожелания."""
    text = (
        f"{_emoji('monthly_pref_edit')} <b>Месячное пожелание изменено</b>\n"
        f"├ Пользователь: <b>{actor}</b>\n"
        f"├ Сотрудник: <b>{employee_name}</b>\n"
        f"├ Период: {month:02d}.{year}\n"
        f"├ Было: {old_type} → Стало: {new_type}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_monthly_preference_delete(
    actor: str,
    employee_name: str,
    year: int,
    month: int,
    preference_type: str,
) -> bool:
    """Уведомление об удалении месячного пожелания."""
    text = (
        f"{_emoji('monthly_pref_delete')} <b>Месячное пожелание удалено</b>\n"
        f"├ Пользователь: <b>{actor}</b>\n"
        f"├ Сотрудник: <b>{employee_name}</b>\n"
        f"├ Период: {month:02d}.{year}\n"
        f"├ Тип: {preference_type}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_bulk_add(
    actor: str,
    employee_name: str,
    item_type: str,
    success_count: int,
    error_count: int,
) -> bool:
    """Уведомление о массовом добавлении."""
    type_labels = {
        "study": "учебных ограничений",
        "preference": "пожеланий",
    }
    label = type_labels.get(item_type, item_type)
    error_str = f", ошибок: {error_count}" if error_count > 0 else ""
    text = (
        f"{_emoji('bulk_add')} <b>Массовое добавление</b>\n"
        f"├ Пользователь: <b>{actor}</b>\n"
        f"├ Сотрудник: <b>{employee_name}</b>\n"
        f"├ Добавлено {label}: {success_count}{error_str}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_user_create(actor: str, new_user: str, role: str) -> bool:
    """Уведомление о создании нового пользователя."""
    text = (
        f"{_emoji('user_create')} <b>Пользователь создан</b>\n"
        f"├ Администратор: <b>{actor}</b>\n"
        f"├ Новый пользователь: <b>{new_user}</b>\n"
        f"├ Роль: {role}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_user_delete(actor: str, deleted_user: str) -> bool:
    """Уведомление об удалении пользователя."""
    text = (
        f"{_emoji('user_delete')} <b>Пользователь удалён</b>\n"
        f"├ Администратор: <b>{actor}</b>\n"
        f"├ Удалён: <b>{deleted_user}</b>\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_user_promote(actor: str, promoted_user: str) -> bool:
    """Уведомление о повышении до админа."""
    text = (
        f"{_emoji('user_promote')} <b>Пользователь повышен</b>\n"
        f"├ Администратор: <b>{actor}</b>\n"
        f"├ Пользователь: <b>{promoted_user}</b>\n"
        f"├ Новая роль: администратор\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_user_demote(actor: str, demoted_user: str) -> bool:
    """Уведомление о понижении до сотрудника."""
    text = (
        f"{_emoji('user_demote')} <b>Пользователь понижен</b>\n"
        f"├ Администратор: <b>{actor}</b>\n"
        f"├ Пользователь: <b>{demoted_user}</b>\n"
        f"├ Новая роль: сотрудник\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_user_password_reset(actor: str, target_user: str) -> bool:
    """Уведомление о сбросе пароля администратором."""
    text = (
        f"{_emoji('user_password_reset')} <b>Сброс пароля</b>\n"
        f"├ Администратор: <b>{actor}</b>\n"
        f"├ Пользователь: <b>{target_user}</b>\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_password_change(username: str) -> bool:
    """Уведомление об изменении пароля пользователем."""
    text = (
        f"{_emoji('password_change')} <b>Пароль изменён</b>\n"
        f"├ Пользователь: <b>{username}</b>\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_settings_change(actor: str, setting_name: str, old_value: str, new_value: str) -> bool:
    """Уведомление об изменении настройки."""
    text = (
        f"{_emoji('settings_change')} <b>Настройка изменена</b>\n"
        f"├ Администратор: <b>{actor}</b>\n"
        f"├ Параметр: {setting_name}\n"
        f"├ Было: {old_value} → Стало: {new_value}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_telegram_settings_change(actor: str, changed_fields: list[str]) -> bool:
    """Уведомление об изменении настроек Telegram."""
    fields = ", ".join(changed_fields)
    text = (
        f"{_emoji('settings_change')} <b>Настройки Telegram изменены</b>\n"
        f"├ Администратор: <b>{actor}</b>\n"
        f"├ Изменены поля: {fields}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_server_start(ip: str = "unknown", port: int = 8001) -> bool:
    """Уведомление о запуске сервера."""
    text = (
        f"{_emoji('server_start')} <b>Сервер запущен</b>\n"
        f"├ IP: {ip}\n"
        f"├ Порт: {port}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_server_stop() -> bool:
    """Уведомление об остановке сервера."""
    text = (
        f"{_emoji('server_stop')} <b>Сервер остановлен</b>\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_backup_success() -> bool:
    """Уведомление об успешном бэкапе."""
    text = (
        f"{_emoji('backup_success')} <b>Бэкап выполнен успешно</b>\n"
        f"├ Архив отправлен в Telegram\n"
        f"└ Время: {_now()}"
    )
    return _send(text)


def notify_backup_failed(error: str = "Неизвестная ошибка") -> bool:
    """Уведомление о неудачном бэкапе."""
    text = (
        f"{_emoji('backup_failed')} <b>Бэкап не выполнен</b>\n"
        f"├ Ошибка: {error}\n"
        f"└ Время: {_now()}"
    )
    return _send(text)
