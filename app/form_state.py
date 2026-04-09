"""Значения полей форм по умолчанию и вспомогательные мелочи."""
from __future__ import annotations

from datetime import date

from .database import get_app_settings
from .ekc_constants import WEEKDAY_LABELS
from .models import Employee

def translate_weekday(value: date) -> str:
    return WEEKDAY_LABELS[value.strftime("%A")]


def merge_employee_lists(primary: list[Employee], secondary: list[Employee]) -> list[Employee]:
    merged = {employee.name: employee for employee in primary}
    for employee in secondary:
        merged.setdefault(employee.name, employee)
    return sorted(merged.values(), key=lambda item: item.name.lower())


def default_form_values() -> dict[str, str]:
    return {
        "holiday_dates": "",
    }


def default_operator_form_values() -> dict[str, object]:
    return {
        "original_name": "",
        "name": "",
        "rate": "1.0",
        "employee_type": "operator",
        "max_consecutive_days": "5",
        "is_active": True,
    }


def default_manual_shift_form_values() -> dict[str, str]:
    return {
        "employee_name": "",
        "shift_date": "",
        "start_time": "",
        "end_time": "",
        "note": "",
    }


def default_vacation_form_values() -> dict[str, str]:
    return {
        "employee_name": "",
        "start_date": "",
        "end_date": "",
        "note": "",
    }


def default_holiday_form_values() -> dict[str, str]:
    return {
        "holiday_date": "",
        "holiday_name": "",
    }


def resolve_period(year: int | None, month: int | None) -> tuple[int, int]:
    today = date.today()
    safe_year = year if year and 2024 <= year <= 2100 else today.year
    safe_month = month if month and 1 <= month <= 12 else today.month
    return safe_year, safe_month

