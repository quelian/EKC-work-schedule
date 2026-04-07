"""Сервис вычисления зон доступности сотрудников по диапазону дат."""
from __future__ import annotations

import calendar
from datetime import date, timedelta

from ..database import (
    list_operator_profiles,
    list_holiday_entries,
    list_calendar_day_overrides,
    list_vacation_entries_range,
    list_schedule_assignments_range,
    list_study_constraints_range,
    list_schedule_preferences_range,
    list_monthly_preferences,
    get_employee_month_adjustments_batch,
)
from ..calendar_layout import resolve_non_working_dates
from ..employee_hydration import _get_vacation_days_for_employee
from ..models import monthly_norm_hours


def _time_to_minutes(t: str) -> int:
    """'HH:MM' → минуты от полуночи."""
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _minutes_to_time(m: int) -> str:
    """Минуты от полуночи → 'HH:MM'."""
    return f"{m // 60:02d}:{m % 60:02d}"


def _subtract_interval(
    intervals: list[tuple[int, int]],
    cut_start: int,
    cut_end: int,
) -> list[tuple[int, int]]:
    """Вычитает [cut_start, cut_end) из списка интервалов [start, end)."""
    result: list[tuple[int, int]] = []
    for start, end in intervals:
        if cut_end <= start or cut_start >= end:
            result.append((start, end))
        else:
            if start < cut_start:
                result.append((start, cut_start))
            if cut_end < end:
                result.append((cut_end, end))
    return result


def compute_availability_range(
    start_date: date,
    end_date: date,
) -> dict:
    """
    Вычисляет зоны доступности для каждого сотрудника на каждую дату в диапазоне.

    Возвращает:
    {
        "2026-04-07": {
            "Иванов И.И.": {
                "zones": [{"start": "08:00", "end": "14:00", "type": "available"}, ...],
                "blocks": [{"start": "14:00", "end": "18:00", "type": "study", "note": "Пары"}, ...]
            },
            ...
        },
        ...
    }
    """
    employees = list_operator_profiles(active_only=True)
    holidays = list_holiday_entries()
    overrides = list_calendar_day_overrides()
    vacations = list_vacation_entries_range(start_date, end_date)
    study = list_study_constraints_range(start_date, end_date)
    preferences = list_schedule_preferences_range(start_date, end_date)

    months_covered: set[tuple[int, int]] = set()
    cursor_month = date(start_date.year, start_date.month, 1)
    while cursor_month <= end_date:
        months_covered.add((cursor_month.year, cursor_month.month))
        next_month = cursor_month.month + 1
        next_year = cursor_month.year + (1 if next_month == 13 else 0)
        next_month = 1 if next_month == 13 else next_month
        cursor_month = date(next_year, next_month, 1)

    monthly_preferences_by_emp_month: dict[tuple[str, int, int], list[dict]] = {}
    for y, m in months_covered:
        for pref in list_monthly_preferences(y, m):
            monthly_preferences_by_emp_month.setdefault((pref["employee_name"], y, m), []).append(pref)

    # Собираем множества нерабочих дат для каждого месяца в диапазоне
    non_working_cache: dict[tuple[int, int], set[date]] = {}

    def is_non_working(d: date) -> bool:
        key = (d.year, d.month)
        if key not in non_working_cache:
            non_working_cache[key] = resolve_non_working_dates(
                d.year, d.month, holidays, overrides
            )
        return d in non_working_cache[key]

    # Группируем constraints/preferences по (employee, date)
    study_by_emp_date: dict[tuple[str, str], list[dict]] = {}
    for c in study:
        key = (c["employee_name"], c["date"])
        study_by_emp_date.setdefault(key, []).append(c)

    pref_by_emp_date: dict[tuple[str, str], list[dict]] = {}
    for p in preferences:
        key = (p["employee_name"], p["date"])
        pref_by_emp_date.setdefault(key, []).append(p)

    # Вычисляем для каждой даты
    result: dict[str, dict] = {}
    cursor = start_date
    while cursor <= end_date:
        date_str = cursor.isoformat()
        is_nw = is_non_working(cursor)
        op_start = 9 * 60 if is_nw else 8 * 60   # 09:00 или 08:00
        op_end = 21 * 60 if is_nw else 22 * 60    # 21:00 или 22:00

        day_data: dict[str, dict] = {}

        for emp in employees:
            zones: list[dict] = []
            blocks: list[dict] = []

            emp_name = emp.name
            emp_type = emp.employee_type

            # Проверяем отпуск
            on_vacation = False
            for v in vacations:
                if v.employee_name == emp_name and v.start_date <= cursor <= v.end_date:
                    on_vacation = True
                    blocks.append({
                        "start": _minutes_to_time(op_start),
                        "end": _minutes_to_time(op_end),
                        "type": "vacation",
                        "note": v.note or "Отпуск",
                    })
                    break

            if on_vacation:
                day_data[emp_name] = {"zones": [], "blocks": blocks}
                continue

            # applications_only: не работает в выходные, только 09:00-18:00 в будни
            avail_start = op_start
            avail_end = op_end

            if emp_type == "applications_only":
                if is_nw:
                    blocks.append({
                        "start": _minutes_to_time(op_start),
                        "end": _minutes_to_time(op_end),
                        "type": "outside_hours",
                        "note": "Не работает в выходные",
                    })
                    day_data[emp_name] = {"zones": [], "blocks": blocks}
                    continue
                else:
                    apps_start = 9 * 60
                    apps_end = 18 * 60
                    if op_start < apps_start:
                        blocks.append({
                            "start": _minutes_to_time(op_start),
                            "end": _minutes_to_time(apps_start),
                            "type": "outside_hours",
                            "note": "",
                        })
                    if op_end > apps_end:
                        blocks.append({
                            "start": _minutes_to_time(apps_end),
                            "end": _minutes_to_time(op_end),
                            "type": "outside_hours",
                            "note": "",
                        })
                    avail_start = apps_start
                    avail_end = apps_end

            # Строим доступные интервалы вычитанием study constraints
            intervals: list[tuple[int, int]] = [(avail_start, avail_end)]
            day_study = study_by_emp_date.get((emp_name, date_str), [])
            for c in day_study:
                c_start = _time_to_minutes(c["start_time"])
                c_end = _time_to_minutes(c["end_time"])
                blocks.append({
                    "start": c["start_time"],
                    "end": c["end_time"],
                    "type": "study",
                    "note": (c.get("note", "") or "").strip(),
                })
                if c.get("is_strict", True):
                    intervals = _subtract_interval(intervals, c_start, c_end)

            # Формируем зоны из оставшихся интервалов
            for s, e in intervals:
                if e > s:
                    zones.append({
                        "start": _minutes_to_time(s),
                        "end": _minutes_to_time(e),
                        "type": "available",
                    })

            # Preferences (мягкие, для отображения)
            day_prefs = pref_by_emp_date.get((emp_name, date_str), [])
            for p in day_prefs:
                pref_type = p["preference_type"]
                if pref_type == "prefer_off":
                    blocks.append({
                        "start": p.get("start_time") or _minutes_to_time(op_start),
                        "end": p.get("end_time") or _minutes_to_time(op_end),
                        "type": "preference_off",
                        "note": p.get("note", "") or "Не ставить",
                    })
                elif pref_type == "not_before":
                    pref_end = p.get("end_time") or p.get("start_time") or _minutes_to_time(op_start)
                    blocks.append({
                        "start": _minutes_to_time(op_start),
                        "end": pref_end,
                        "type": "preference_not_before",
                        "note": p.get("note", "") or f"Не ставить до {pref_end}",
                    })
                elif pref_type == "not_after":
                    pref_start = p.get("start_time") or _minutes_to_time(op_end)
                    blocks.append({
                        "start": pref_start,
                        "end": _minutes_to_time(op_end),
                        "type": "preference_not_after",
                        "note": p.get("note", "") or f"Не ставить после {pref_start}",
                    })
                else:
                    blocks.append({
                        "start": p.get("start_time") or _minutes_to_time(op_start),
                        "end": p.get("end_time") or _minutes_to_time(op_end),
                        "type": "preference_other",
                        "note": p.get("note", "") or "Другое пожелание",
                    })

            day_month_prefs = monthly_preferences_by_emp_month.get((emp_name, cursor.year, cursor.month), [])
            for p in day_month_prefs:
                pref_type = p["preference_type"]
                if pref_type == "prefer_off":
                    blocks.append({
                        "start": _minutes_to_time(op_start),
                        "end": _minutes_to_time(op_end),
                        "type": "preference_off",
                        "note": p.get("note", "") or "Не ставить",
                    })
                elif pref_type == "not_before":
                    pref_end = p.get("time_value") or p.get("end_time") or p.get("start_time") or _minutes_to_time(op_start)
                    blocks.append({
                        "start": _minutes_to_time(op_start),
                        "end": pref_end,
                        "type": "preference_not_before",
                        "note": p.get("note", "") or f"Не ставить до {pref_end}",
                    })
                elif pref_type == "not_after":
                    pref_start = p.get("time_value") or p.get("start_time") or p.get("end_time") or _minutes_to_time(op_end)
                    blocks.append({
                        "start": pref_start,
                        "end": _minutes_to_time(op_end),
                        "type": "preference_not_after",
                        "note": p.get("note", "") or f"Не ставить после {pref_start}",
                    })
                else:
                    blocks.append({
                        "start": p.get("start_time") or _minutes_to_time(op_start),
                        "end": p.get("end_time") or _minutes_to_time(op_end),
                        "type": "preference_other",
                        "note": p.get("note", "") or "Другое пожелание",
                    })

            day_data[emp_name] = {"zones": zones, "blocks": blocks}


        result[date_str] = day_data
        cursor += timedelta(days=1)

    return result


def compute_employee_target_hours(
    year: int,
    month: int,
) -> dict[str, float]:
    """Вычисляет целевые часы для каждого активного сотрудника в месяце."""
    employees = list_operator_profiles(active_only=True)
    holidays = list_holiday_entries()
    overrides = list_calendar_day_overrides()
    month_start = date(year, month, 1)
    import calendar as _cal
    month_end = date(year, month, _cal.monthrange(year, month)[1])
    vacations = list_vacation_entries_range(month_start, month_end)
    non_working = resolve_non_working_dates(year, month, holidays, overrides)
    holiday_dates = {h.holiday_date for h in holidays if h.holiday_date.year == year and h.holiday_date.month == month}

    adjustments_batch = get_employee_month_adjustments_batch(year, month)
    # non_working = weekends(Сб/Вс) + holidays + overrides (calendar_overrides)
    # Это и есть база для расчёта нормы рабочих дней
    target_hours: dict[str, float] = {}
    for emp in employees:
        vacation_days = _get_vacation_days_for_employee(emp.name, year, month, vacations)
        base_norm = monthly_norm_hours(emp.rate, year, month, non_working, vacation_days)
        adjustment = adjustments_batch.get(emp.name, 0.0)
        target_hours[emp.name] = round(base_norm + adjustment, 1)

    return target_hours


def get_non_working_dates_range(
    start_date: date,
    end_date: date,
) -> list[str]:
    """Возвращает список ISO-дат нерабочих дней в диапазоне."""
    holidays = list_holiday_entries()
    overrides = list_calendar_day_overrides()

    non_working_cache: dict[tuple[int, int], set[date]] = {}
    result: list[str] = []
    cursor = start_date
    while cursor <= end_date:
        key = (cursor.year, cursor.month)
        if key not in non_working_cache:
            non_working_cache[key] = resolve_non_working_dates(
                cursor.year, cursor.month, holidays, overrides
            )
        if cursor in non_working_cache[key]:
            result.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return result
