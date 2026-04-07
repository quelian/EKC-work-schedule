from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, time
from typing import Collection, Literal

from .roster_requirements import (
    MIN_SHIFT_HOURS_APPLICATIONS_ONLY,
    MIN_SHIFT_HOURS_DEFAULT,
    MIN_SHIFT_HOURS_OPERATOR_HALFTIME,
    min_shift_duration_hours,
)
DayKind = Literal["weekday", "weekend", "holiday"]
ShiftAppliesTo = Literal["weekday", "weekend", "holiday", "weekend_or_holiday", "everyday"]
PreferenceKind = Literal["study", "unavailable", "prefer_off"]
EmployeeType = Literal["operator", "applications_only"]
AssignmentSource = Literal["auto", "manual", "system"]
PipelineStageStatus = Literal["done", "warning", "critical", "skipped"]
ALLOWED_RATES = (0.25, 0.5, 0.75, 1.0)
ALLOWED_EMPLOYEE_TYPES = ("operator", "applications_only")
EMPLOYEE_TYPE_LABELS = {
    "operator": "оператор",
    "applications_only": "только заявки",
}
RATE_DAILY_LIMITS = {
    0.25: 2.0,
    0.5: 4.0,
    0.75: 6.0,
    1.0: 8.0,
}
RATE_MAX_CONSECUTIVE_HOURS = {
    0.25: 4.0,
    0.5: 6.0,
    0.75: 8.0,
    1.0: 8.0,
}

@dataclass(slots=True)
class Employee:
    employee_id: str
    name: str
    max_hours: float = 168.0
    preferred_hours: float = 160.0
    max_consecutive_days: int = 5
    rate: float = 1.0
    employee_type: EmployeeType = "operator"

    @property
    def daily_hours_limit(self) -> float:
        return max_consecutive_hours_for_rate(self.rate)

    @property
    def max_consecutive_hours(self) -> float:
        return max_consecutive_hours_for_rate(self.rate)

    @property
    def norm_hours_per_workday(self) -> float:
        return daily_hours_for_rate(self.rate)


def min_shift_duration_hours_for_employee(employee: Employee) -> float:
    # Вся бизнес-логика “минимальной длительности” хранится в `app/roster_requirements.py`.
    return min_shift_duration_hours(employee.employee_type, employee.rate)


@dataclass(slots=True)
class ShiftTemplate:
    code: str
    label: str
    start_time: time
    end_time: time
    duration_hours: float
    applies_to: ShiftAppliesTo
    required_staff: int
    required_employee_type: EmployeeType | None = None
    optional: bool = False


@dataclass(slots=True)
class TimeConstraint:
    employee_name: str
    date: date
    kind: PreferenceKind
    start_time: time | None = None
    end_time: time | None = None
    strict: bool = True
    note: str = ""


@dataclass(slots=True)
class WeekendChoice:
    employee_name: str
    date: date
    shift_code: str | None = None
    note: str = ""


@dataclass(slots=True)
class ManualShiftEntry:
    employee_name: str
    shift_date: date
    shift_code: str
    note: str = ""
    source: AssignmentSource = "manual"
    updated_at: str = ""


@dataclass(slots=True)
class ShiftSlot:
    date: date
    day_kind: DayKind
    template: ShiftTemplate
    position: int

    @property
    def slot_id(self) -> str:
        return f"{self.date.isoformat()}::{self.template.code}::{self.position}"


@dataclass(slots=True)
class Assignment:
    slot: ShiftSlot
    employee_name: str | None = None
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    is_manual: bool = False
    source: AssignmentSource = "auto"


@dataclass(slots=True)
class EmployeeStats:
    employee_name: str
    assigned_hours: float = 0.0
    assigned_days: int = 0
    weekend_days: int = 0
    holiday_days: int = 0
    consecutive_days_peak: int = 0


@dataclass(slots=True)
class ScheduleWarning:
    severity: Literal["info", "warning", "critical"]
    message: str


@dataclass(slots=True)
class ImportedOperatorDoc:
    employee_name: str
    source_path: str
    extracted_text: str
    constraints: list[TimeConstraint] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(slots=True)
class OperatorProfile:
    name: str
    employee_id: str
    norm_hours: float = 160.0
    max_hours: float = 168.0
    rate: float = 1.0
    employee_type: EmployeeType = "operator"
    max_consecutive_days: int = 5
    is_active: bool = True
    hour_adjustment: float = 0.0
    updated_at: str = ""

    @property
    def daily_hours_limit(self) -> float:
        return max_consecutive_hours_for_rate(self.rate)

    @property
    def max_consecutive_hours(self) -> float:
        return max_consecutive_hours_for_rate(self.rate)

    @property
    def norm_hours_per_workday(self) -> float:
        return daily_hours_for_rate(self.rate)


@dataclass(slots=True)
class VacationEntry:
    employee_name: str
    start_date: date
    end_date: date
    note: str = ""
    id: int = 0
    updated_at: str = ""


@dataclass(slots=True)
class HolidayEntry:
    holiday_date: date
    name: str = ""
    updated_at: str = ""


@dataclass(slots=True)
class CalendarDayOverride:
    calendar_date: date
    is_non_working: bool
    updated_at: str = ""


@dataclass(slots=True)
class ScheduleResult:
    assignments: list[Assignment]
    employee_stats: list[EmployeeStats]
    warnings: list[ScheduleWarning]


def normalize_rate(rate: float) -> float:
    return round(float(rate), 2)


def daily_hours_for_rate(rate: float) -> float:
    normalized = normalize_rate(rate)
    if normalized not in RATE_DAILY_LIMITS:
        allowed = ", ".join(str(value).replace(".", ",") for value in ALLOWED_RATES)
        raise ValueError(f"Недопустимая ставка {rate}. Разрешены: {allowed}.")
    return RATE_DAILY_LIMITS[normalized]


def max_consecutive_hours_for_rate(rate: float) -> float:
    normalized = normalize_rate(rate)
    if normalized not in RATE_MAX_CONSECUTIVE_HOURS:
        allowed = ", ".join(str(value).replace(".", ",") for value in ALLOWED_RATES)
        raise ValueError(f"Недопустимая ставка {rate}. Разрешены: {allowed}.")
    return RATE_MAX_CONSECUTIVE_HOURS[normalized]


def normalize_employee_type(employee_type: str | None) -> EmployeeType:
    normalized = (employee_type or "").strip().lower().replace("-", "_")
    aliases = {
        "operator": "operator",
        "оператор": "operator",
        "applications_only": "applications_only",
        "only_applications": "applications_only",
        "only_requests": "applications_only",
        "requests_only": "applications_only",
        "только_заявки": "applications_only",
        "только заявки": "applications_only",
    }
    if normalized in aliases:
        return aliases[normalized]
    allowed = ", ".join(EMPLOYEE_TYPE_LABELS[value] for value in ALLOWED_EMPLOYEE_TYPES)
    raise ValueError(f"Недопустимый тип сотрудника '{employee_type}'. Разрешены: {allowed}.")


def employee_type_label(employee_type: str) -> str:
    normalized = normalize_employee_type(employee_type)
    return EMPLOYEE_TYPE_LABELS[normalized]


def working_days_in_month(year: int, month: int, holidays: Collection[date] | None = None) -> int:
    holiday_set = {
        holiday_date
        for holiday_date in (holidays or [])
        if holiday_date.year == year and holiday_date.month == month
    }
    total_days = calendar.monthrange(year, month)[1]
    working_days = 0
    for day_number in range(1, total_days + 1):
        current_day = date(year, month, day_number)
        if current_day.weekday() >= 5 or current_day in holiday_set:
            continue
        working_days += 1
    return working_days


def monthly_norm_hours(
    rate: float,
    year: int,
    month: int,
    holidays: Collection[date] | None = None,
    vacation_days: int = 0,
) -> float:
    """
    Рассчитывает норму часов для сотрудника в месяце.

    :param vacation_days: Количество дней отпуска в месяце (вычитается из рабочих дней)
    """
    return (working_days_in_month(year, month, holidays) - vacation_days) * daily_hours_for_rate(rate)
