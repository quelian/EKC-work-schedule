"""Календарная сетка месяца, merge интервалов, типы дней."""
from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, timedelta

from .database import holidays_to_dates
from .ekc_constants import DAY_KIND_LABELS, MONTH_NAMES, WEEKDAY_SHORT_LABELS
from .form_state import translate_weekday
from .models import CalendarDayOverride, HolidayEntry, VacationEntry

def base_non_working_dates(year: int, month: int, holiday_entries: list[HolidayEntry]) -> set[date]:
    selected = {
        date(year, month, day_number)
        for day_number in range(1, calendar.monthrange(year, month)[1] + 1)
        if date(year, month, day_number).weekday() >= 5
    }
    selected |= holidays_to_dates(holiday_entries, year, month)
    return selected


def resolve_non_working_dates(
    year: int,
    month: int,
    holiday_entries: list[HolidayEntry],
    calendar_overrides: list[CalendarDayOverride],
) -> set[date]:
    selected = base_non_working_dates(year, month, holiday_entries)
    for item in calendar_overrides:
        if item.calendar_date.year != year or item.calendar_date.month != month:
            continue
        if item.is_non_working:
            selected.add(item.calendar_date)
        else:
            selected.discard(item.calendar_date)
    return selected


def serialize_dates(dates: set[date]) -> str:
    return ", ".join(sorted(target_date.isoformat() for target_date in dates))


def build_calendar_view(
    year: int,
    month: int,
    result: dict[str, object] | None,
    vacation_entries: list[VacationEntry],
    holiday_entries: list[HolidayEntry],
    non_working_dates: set[date],
) -> dict[str, object]:
    month_calendar = calendar.Calendar(firstweekday=0)
    holiday_names = build_holiday_names(year, month, holiday_entries, non_working_dates)
    vacations_by_day = build_vacations_by_day(year, month, vacation_entries)
    calendar_entries_by_date = result.get("calendar_entries_by_date", {}) if result else {}
    weeks = []

    for week in month_calendar.monthdatescalendar(year, month):
        week_cells = []
        for day_value in week:
            iso_value = day_value.isoformat()
            holiday_name = holiday_names.get(iso_value, "")
            day_entries = calendar_entries_by_date.get(iso_value, [])
            merged_entries = merge_calendar_entries(day_entries)
            day_kind = resolve_day_kind(day_value, non_working_dates, day_entries)
            filled_slots = sum(1 for entry in day_entries if entry["filled"])
            open_slots = sum(1 for entry in day_entries if not entry["filled"])
            week_cells.append(
                {
                    "in_month": day_value.month == month,
                    "iso_date": iso_value,
                    "day_number": day_value.day,
                    "weekday_name": translate_weekday(day_value),
                    "day_kind": day_kind,
                    "day_kind_label": DAY_KIND_LABELS[day_kind],
                    "holiday_name": holiday_name,
                    "vacation_names": vacations_by_day.get(iso_value, []),
                    "entries": merged_entries,
                    "filled_slots": filled_slots,
                    "open_slots": open_slots,
                    "has_schedule": bool(day_entries),
                }
            )
        weeks.append(week_cells)

    return {
        "month_label": f"{MONTH_NAMES[month]} {year}",
        "weekdays": WEEKDAY_SHORT_LABELS,
        "weeks": weeks,
    }


def merge_calendar_entries(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    """Склеивает подряд идущие интервалы одного сотрудника (08-09 + 09-10 → 08-10) для отображения."""
    if not entries:
        return []

    filled: list[dict[str, object]] = []
    unfilled: list[dict[str, object]] = []
    for raw in entries:
        item = dict(raw)
        if item.get("filled"):
            filled.append(item)
        else:
            unfilled.append(item)

    by_employee: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in filled:
        by_employee[str(item.get("employee_name", ""))].append(item)

    merged_filled: list[dict[str, object]] = []
    for employee_name in sorted(by_employee.keys(), key=lambda name: name.lower()):
        chain = sorted(by_employee[employee_name], key=lambda item: str(item.get("start_time", "")))
        merged_filled.extend(_merge_adjacent_intervals_one_employee(chain))

    unfilled.sort(key=lambda item: str(item.get("start_time", "")))
    combined = merged_filled + unfilled
    combined.sort(
        key=lambda item: (
            str(item.get("start_time", "")),
            str(item.get("employee_name", "")).lower(),
        ),
    )
    return combined


def _merge_adjacent_intervals_one_employee(chain: list[dict[str, object]]) -> list[dict[str, object]]:
    if not chain:
        return []
    result: list[dict[str, object]] = []
    current = dict(chain[0])
    for nxt in chain[1:]:
        if str(current.get("end_time", "")) == str(nxt.get("start_time", "")):
            current["end_time"] = nxt.get("end_time", current.get("end_time", ""))
            start_t = str(current.get("start_time", ""))
            end_t = str(current.get("end_time", ""))
            current["time_range"] = f"{start_t} - {end_t}"
            current["shift_label"] = f"{start_t}-{end_t}"
            pos_cur = int(current.get("position") or 999)
            pos_n = int(nxt.get("position") or 999)
            current["position"] = min(pos_cur, pos_n)
        else:
            _finalize_merged_interval_labels(current)
            result.append(current)
            current = dict(nxt)
    _finalize_merged_interval_labels(current)
    result.append(current)
    return result


def _finalize_merged_interval_labels(block: dict[str, object]) -> None:
    start_t = str(block.get("start_time", ""))
    end_t = str(block.get("end_time", ""))
    block["time_range"] = f"{start_t} - {end_t}"
    block["shift_label"] = f"{start_t}-{end_t}"


def build_holiday_names(
    year: int,
    month: int,
    holiday_entries: list[HolidayEntry],
    non_working_dates: set[date],
) -> dict[str, str]:
    holiday_names: dict[str, str] = {}
    for holiday in holiday_entries:
        if (
            holiday.holiday_date.year == year
            and holiday.holiday_date.month == month
            and holiday.holiday_date in non_working_dates
        ):
            holiday_names[holiday.holiday_date.isoformat()] = holiday.name or "Праздник"
    for holiday_date in non_working_dates:
        if holiday_date.year != year or holiday_date.month != month:
            continue
        if holiday_date.weekday() < 5:
            holiday_names.setdefault(holiday_date.isoformat(), "Праздник")
    return holiday_names


def build_vacations_by_day(year: int, month: int, vacation_entries: list[VacationEntry]) -> dict[str, list[str]]:
    vacations_by_day: dict[str, list[str]] = defaultdict(list)
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])

    for vacation in vacation_entries:
        start = max(vacation.start_date, month_start)
        end = min(vacation.end_date, month_end)
        if end < start:
            continue
        current_day = start
        while current_day <= end:
            vacations_by_day[current_day.isoformat()].append(vacation.employee_name)
            current_day += timedelta(days=1)

    return dict(vacations_by_day)


def resolve_day_kind(day_value: date, non_working_dates: set[date], day_entries: list[dict[str, object]]) -> str:
    if day_entries:
        return str(day_entries[0]["day_kind"])
    if day_value in non_working_dates:
        return "weekend" if day_value.weekday() >= 5 else "holiday"
    return "weekday"
