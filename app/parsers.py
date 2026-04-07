from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from datetime import date, datetime, time

from .models import Employee, ShiftTemplate, TimeConstraint, WeekendChoice, daily_hours_for_rate, normalize_employee_type, normalize_rate

DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y")
TIME_FORMATS = ("%H:%M", "%H:%M:%S")


class ParseError(ValueError):
    """Raised when incoming CSV or text data is invalid."""


def decode_upload(raw: bytes | None) -> str:
    if not raw:
        return ""
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ParseError("Не удалось определить кодировку файла. Используйте UTF-8 или CP1251.")


def parse_csv_rows(raw_text: str) -> list[dict[str, str]]:
    if not raw_text.strip():
        return []
    reader = csv.DictReader(io.StringIO(raw_text.strip()))
    if not reader.fieldnames:
        raise ParseError("CSV-файл пустой или в нем нет заголовков.")
    rows = []
    for row in reader:
        rows.append({(key or "").strip(): (value or "").strip() for key, value in row.items()})
    return rows


def parse_date(value: str, field_name: str = "date") -> date:
    value = value.strip()
    if not value:
        raise ParseError(f"Поле {field_name} не заполнено.")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ParseError(f"Не удалось распознать дату '{value}' в поле {field_name}. Используйте YYYY-MM-DD.")


def parse_time(value: str | None, field_name: str = "time") -> time | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    raise ParseError(f"Не удалось распознать время '{value}' в поле {field_name}. Используйте HH:MM.")


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "да", "д"}


def parse_float(value: str | None, default: float) -> float:
    if value is None or not value.strip():
        return default
    normalized = value.replace(",", ".").strip()
    try:
        return float(normalized)
    except ValueError as error:
        raise ParseError(f"Ожидалось число, получено '{value}'.") from error


def parse_int(value: str | None, default: int) -> int:
    if value is None or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError as error:
        raise ParseError(f"Ожидалось целое число, получено '{value}'.") from error


def parse_employees(rows: Iterable[dict[str, str]]) -> list[Employee]:
    employees: list[Employee] = []
    for index, row in enumerate(rows, start=2):
        name = row.get("name", "")
        if not name:
            raise ParseError(f"В employees.csv строка {index}: поле name обязательно.")
        employee_id = row.get("employee_id") or slugify_name(name)
        max_hours = parse_float(row.get("max_hours"), 168.0)
        preferred_hours = parse_float(row.get("preferred_hours") or row.get("norm_hours"), min(max_hours, 160.0))
        rate = normalize_rate(parse_float(row.get("rate"), 1.0))
        daily_hours_for_rate(rate)
        employee_type = normalize_employee_type(row.get("employee_type") or "operator")
        employees.append(
            Employee(
                employee_id=employee_id,
                name=name,
                max_hours=max_hours,
                preferred_hours=preferred_hours,
                max_consecutive_days=parse_int(row.get("max_consecutive_days"), 5),
                rate=rate,
                employee_type=employee_type,
            )
        )
    if not employees:
        raise ParseError("Список сотрудников пуст. Загрузите employees.csv.")
    return employees


def parse_shift_templates(rows: Iterable[dict[str, str]]) -> list[ShiftTemplate]:
    shifts: list[ShiftTemplate] = []
    for index, row in enumerate(rows, start=2):
        code = row.get("code", "")
        label = row.get("label", "")
        if not code or not label:
            raise ParseError(f"В shifts.csv строка {index}: поля code и label обязательны.")
        applies_to = (row.get("applies_to") or "weekday").strip().lower()
        if applies_to not in {"weekday", "weekend", "holiday", "weekend_or_holiday", "everyday"}:
            raise ParseError(
                f"В shifts.csv строка {index}: applies_to должен быть weekday, weekend, holiday, weekend_or_holiday или everyday."
            )
        shifts.append(
            ShiftTemplate(
                code=code,
                label=label,
                start_time=parse_time(row.get("start_time"), "start_time") or time(9, 0),
                end_time=parse_time(row.get("end_time"), "end_time") or time(18, 0),
                duration_hours=parse_float(row.get("duration_hours"), 8.0),
                applies_to=applies_to,
                required_staff=parse_int(row.get("required_staff"), 1),
            )
        )
    if not shifts:
        raise ParseError("Список смен пуст. Добавьте хотя бы одну смену.")
    return shifts


def parse_constraints(rows: Iterable[dict[str, str]], default_kind: str) -> list[TimeConstraint]:
    constraints: list[TimeConstraint] = []
    for index, row in enumerate(rows, start=2):
        employee_name = row.get("employee_name", "")
        if not employee_name:
            raise ParseError(f"В constraints CSV строка {index}: поле employee_name обязательно.")
        kind = (row.get("kind") or default_kind).strip().lower()
        if kind not in {"study", "unavailable", "prefer_off"}:
            raise ParseError(f"В constraints CSV строка {index}: неизвестный kind '{kind}'.")
        constraints.append(
            TimeConstraint(
                employee_name=employee_name,
                date=parse_date(row.get("date", ""), "date"),
                kind=kind,
                start_time=parse_time(row.get("start_time"), "start_time"),
                end_time=parse_time(row.get("end_time"), "end_time"),
                strict=parse_bool(row.get("strict"), default=kind in {"study", "unavailable"}),
                note=row.get("note", ""),
            )
        )
    return constraints


def parse_weekend_choices(rows: Iterable[dict[str, str]]) -> list[WeekendChoice]:
    choices: list[WeekendChoice] = []
    for index, row in enumerate(rows, start=2):
        employee_name = row.get("employee_name", "")
        if not employee_name:
            raise ParseError(f"В weekend_choices.csv строка {index}: поле employee_name обязательно.")
        choices.append(
            WeekendChoice(
                employee_name=employee_name,
                date=parse_date(row.get("date", ""), "date"),
                shift_code=(row.get("shift_code") or "").strip() or None,
                note=row.get("note", ""),
            )
        )
    return choices


def parse_holiday_dates(raw_text: str) -> set[date]:
    holiday_dates: set[date] = set()
    separators = [",", "\n", ";"]
    normalized = raw_text
    for separator in separators[1:]:
        normalized = normalized.replace(separator, separators[0])
    for chunk in normalized.split(separators[0]):
        chunk = chunk.strip()
        if chunk:
            holiday_dates.add(parse_date(chunk, "holiday_dates"))
    return holiday_dates


def slugify_name(name: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in name).strip("_")
