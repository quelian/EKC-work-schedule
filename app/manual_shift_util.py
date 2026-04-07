"""Парсинг и проверки произвольных ручных интервалов смен."""
from __future__ import annotations

import re
from datetime import date, time

from .ekc_constants import LEGACY_MANUAL_SHIFT_CODES
from .models import Employee, ManualShiftEntry, OperatorProfile, min_shift_duration_hours_for_employee
from .parsers import ParseError, parse_time
from .roster_requirements import manual_interval_bounds

def normalize_manual_interval(start_time_value: str, end_time_value: str) -> str:
    start_text = start_time_value.strip()
    end_text = end_time_value.strip()
    if not start_text or not end_text:
        raise ParseError("Для ручной смены укажите и время начала, и время окончания.")
    return f"{start_text}-{end_text}"


def manual_interval_within_operating_hours(
    shift_date: date,
    start_time_value: time,
    end_time_value: time,
    non_working_dates: set[date],
) -> bool:
    start_bound, end_bound = manual_interval_bounds(shift_date in non_working_dates)
    return start_bound <= start_time_value < end_time_value <= end_bound


def manual_shift_label(shift_code: str) -> str:
    normalized = shift_code.strip()
    legacy = LEGACY_MANUAL_SHIFT_CODES.get(normalized)
    if legacy:
        return str(legacy["label"])
    if re.fullmatch(r"\d{2}:\d{2}-\d{2}:\d{2}", normalized):
        start_text, end_text = normalized.split("-", 1)
        return f"{start_text} - {end_text}"
    return normalized


def manual_shift_sort_time(shift_code: str) -> str:
    normalized = shift_code.strip()
    legacy = LEGACY_MANUAL_SHIFT_CODES.get(normalized)
    if legacy:
        return str(legacy["start_time"])
    if re.fullmatch(r"\d{2}:\d{2}-\d{2}:\d{2}", normalized):
        return normalized.split("-", 1)[0]
    return "99:99"


def manual_shift_end_time(shift_code: str) -> str:
    normalized = shift_code.strip()
    legacy = LEGACY_MANUAL_SHIFT_CODES.get(normalized)
    if legacy and re.fullmatch(r"\d{2}:\d{2} - \d{2}:\d{2}", str(legacy["label"])):
        return str(legacy["label"]).split(" - ", 1)[1]
    if re.fullmatch(r"\d{2}:\d{2}-\d{2}:\d{2}", normalized):
        return normalized.split("-", 1)[1]
    label = manual_shift_label(normalized)
    if re.fullmatch(r"\d{2}:\d{2} - \d{2}:\d{2}", label):
        return label.split(" - ", 1)[1]
    return ""


def normalize_legacy_manual_shift_code(shift_code: str) -> str:
    normalized = shift_code.strip()
    legacy = LEGACY_MANUAL_SHIFT_CODES.get(normalized)
    if legacy:
        return str(legacy["normalized_code"])
    return normalized


def parse_manual_shift_code(shift_code: str) -> tuple[time, time] | None:
    normalized = normalize_legacy_manual_shift_code(shift_code)
    if not re.fullmatch(r"\d{2}:\d{2}-\d{2}:\d{2}", normalized):
        return None
    start_text, end_text = normalized.split("-", 1)
    return (
        parse_time(start_text, "manual_shift_start_time"),
        parse_time(end_text, "manual_shift_end_time"),
    )


def manual_intervals_overlap(
    start_time_value: time,
    end_time_value: time,
    other_start_time: time,
    other_end_time: time,
) -> bool:
    return start_time_value < other_end_time and other_start_time < end_time_value


def validate_manual_shift_rules(
    *,
    employee_name: str,
    shift_date_value: date,
    start_time_value: time,
    end_time_value: time,
    shift_code: str,
    non_working_dates: set[date],
    operator_profiles: list[OperatorProfile],
    existing_entries: list[ManualShiftEntry],
) -> None:
    employee_types = {profile.name: profile.employee_type for profile in operator_profiles}
    employee_type = employee_types.get(employee_name, "operator")
    is_non_working_day = shift_date_value in non_working_dates
    normalized_shift_code = normalize_legacy_manual_shift_code(shift_code)

    if is_non_working_day and employee_type == "applications_only":
        raise ParseError(
            f"Сотрудник '{employee_name}' имеет тип 'только заявки' и не может работать в выходные или праздники."
        )

    if not is_non_working_day:
        return

    for entry in existing_entries:
        if entry.shift_date != shift_date_value:
            continue
        if entry.employee_name == employee_name and normalize_legacy_manual_shift_code(entry.shift_code) == normalized_shift_code:
            continue
        if employee_types.get(entry.employee_name, "operator") != "operator":
            continue
        parsed_interval = parse_manual_shift_code(entry.shift_code)
        if parsed_interval is None:
            continue
        existing_start_time, existing_end_time = parsed_interval
        if manual_intervals_overlap(start_time_value, end_time_value, existing_start_time, existing_end_time):
            raise ParseError(
                "В выходной или праздничный день одновременно может работать только 1 оператор. "
                f"Интервал пересекается с уже сохраненной ручной сменой '{entry.employee_name}'."
            )


def assert_manual_shift_minimum_duration(
    *,
    employee_name: str,
    start_time_value: time,
    end_time_value: time,
    operator_profiles: list[OperatorProfile],
) -> None:
    span_h = (end_time_value.hour * 60 + end_time_value.minute - start_time_value.hour * 60 - start_time_value.minute) / 60.0
    profile = next((p for p in operator_profiles if p.name == employee_name), None)
    proxy = Employee(
        employee_id=profile.employee_id if profile else "",
        name=employee_name,
        rate=profile.rate if profile else 1.0,
        employee_type=profile.employee_type if profile else "operator",
    )
    need = min_shift_duration_hours_for_employee(proxy)
    if span_h + 1e-6 < need:
        raise ParseError(
            f"Слишком короткая смена ({span_h:g} ч.): минимум {need:g} ч. "
            "(для операторов на ставках 0,5 и 0,75 — не короче 3 ч.; для «только заявки» — не короче 4 ч.)."
        )

