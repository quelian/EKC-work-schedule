"""Сборка списка сотрудников для расчёта: БД + импорт, нормы по месяцу."""
from __future__ import annotations

from datetime import date

from .database import get_employee_month_adjustment
from .ekc_constants import MONTH_NAMES
from .models import (
    ALLOWED_EMPLOYEE_TYPES,
    ALLOWED_RATES,
    Employee,
    OperatorProfile,
    daily_hours_for_rate,
    employee_type_label,
    max_consecutive_hours_for_rate,
    monthly_norm_hours,
)


def _get_vacation_days_for_employee(
    employee_name: str,
    year: int,
    month: int,
    vacation_entries: list | None = None,
) -> int:
    """
    Возвращает количество дней отпуска у сотрудника в указанном месяце.
    Считает только рабочие дни (пн-пт).
    """
    from datetime import timedelta
    import calendar

    if vacation_entries is None:
        return 0

    vacation_days = 0
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])

    for entry in vacation_entries:
        if entry.employee_name != employee_name:
            continue

        # Проверяем пересечение отпуска с месяцем
        if entry.end_date < month_start or entry.start_date > month_end:
            continue

        # Считаем дни отпуска в этом месяце
        cursor = max(entry.start_date, month_start)
        end_cursor = min(entry.end_date, month_end)

        while cursor <= end_cursor:
            # Считаем только рабочие дни (пн-пт)
            if cursor.weekday() < 5:
                vacation_days += 1
            cursor += timedelta(days=1)

    return vacation_days

def hydrate_employees(
    employees: list[Employee],
    operator_profiles: list[OperatorProfile],
    year: int,
    month: int,
    holidays: set[date],
    vacation_entries: list | None = None,
) -> list[Employee]:
    profiles_by_name = {profile.name: profile for profile in operator_profiles}
    hydrated: list[Employee] = []
    seen: set[str] = set()
    for employee in employees:
        if employee.name in seen:
            continue
        profile = profiles_by_name.get(employee.name)
        if profile is None:
            vacation_days = _get_vacation_days_for_employee(employee.name, year, month, vacation_entries)
            target_hours = monthly_norm_hours(employee.rate, year, month, holidays, vacation_days)
            employee.preferred_hours = target_hours
            employee.max_hours = target_hours
            hydrated.append(employee)
        elif profile.is_active:
            vacation_days = _get_vacation_days_for_employee(profile.name, year, month, vacation_entries)
            base_target = monthly_norm_hours(profile.rate, year, month, holidays, vacation_days)
            # Добавляем ручную корректировку из БД (employee_month_adjustments)
            month_adjustment = get_employee_month_adjustment(profile.name, year, month)
            max_hours = base_target + month_adjustment
            hydrated.append(
                Employee(
                    employee_id=profile.employee_id or employee.employee_id,
                    name=employee.name,
                    max_hours=max_hours,
                    preferred_hours=max_hours,
                    max_consecutive_days=profile.max_consecutive_days,
                    rate=profile.rate,
                    employee_type=profile.employee_type,
                )
            )
        seen.add(employee.name)
    for profile in operator_profiles:
        if not profile.is_active or profile.name in seen:
            continue
        vacation_days = _get_vacation_days_for_employee(profile.name, year, month, vacation_entries)
        base_target = monthly_norm_hours(profile.rate, year, month, holidays, vacation_days)
        # Добавляем ручную корректировку из БД (employee_month_adjustments)
        month_adjustment = get_employee_month_adjustment(profile.name, year, month)
        max_hours = base_target + month_adjustment
        hydrated.append(
            Employee(
                employee_id=profile.employee_id,
                name=profile.name,
                max_hours=max_hours,
                preferred_hours=max_hours,
                max_consecutive_days=profile.max_consecutive_days,
                rate=profile.rate,
                employee_type=profile.employee_type,
            )
        )
    return sorted(hydrated, key=lambda item: item.name.lower())


def employees_from_profiles(
    operator_profiles: list[OperatorProfile],
    year: int,
    month: int,
    holidays: set[date],
    vacation_entries: list | None = None,
) -> list[Employee]:
    employees = []
    for profile in operator_profiles:
        if not profile.is_active:
            continue
        vacation_days = _get_vacation_days_for_employee(profile.name, year, month, vacation_entries)
        base_target = monthly_norm_hours(profile.rate, year, month, holidays, vacation_days)
        # Добавляем ручную корректировку из БД (employee_month_adjustments)
        month_adjustment = get_employee_month_adjustment(profile.name, year, month)
        max_hours = base_target + month_adjustment
        employees.append(
            Employee(
                employee_id=profile.employee_id,
                name=profile.name,
                max_hours=max_hours,
                preferred_hours=max_hours,
                max_consecutive_days=profile.max_consecutive_days,
                rate=profile.rate,
                employee_type=profile.employee_type,
            )
        )
    return sorted(employees, key=lambda item: item.name.lower())


def rate_options() -> list[dict[str, str]]:
    options = []
    for rate in ALLOWED_RATES:
        options.append(
            {
                "value": str(rate),
                "label": (
                    f"{str(rate).replace('.', ',')} ставки - "
                    f"норма {int(daily_hours_for_rate(rate))} ч/раб. день, "
                    f"подряд до {int(max_consecutive_hours_for_rate(rate))} ч"
                ),
            }
        )
    return options


def employee_type_options() -> list[dict[str, str]]:
    return [
        {
            "value": employee_type,
            "label": employee_type_label(employee_type),
        }
        for employee_type in ALLOWED_EMPLOYEE_TYPES
    ]


def month_options(selected_month: int) -> list[dict[str, object]]:
    return [
        {
            "value": month_value,
            "label": month_name,
            "selected": month_value == selected_month,
        }
        for month_value, month_name in MONTH_NAMES.items()
    ]

