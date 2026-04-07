from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Optional


DAY_KIND_WEEKDAY = "weekday"
DAY_KIND_WEEKEND = "weekend"
DAY_KIND_HOLIDAY = "holiday"

EMPLOYEE_TYPE_OPERATOR = "operator"
EMPLOYEE_TYPE_APPLICATIONS_ONLY = "applications_only"


APPLICATIONS_ONLY_START = time(9, 0)
APPLICATIONS_ONLY_END = time(18, 0)
APPLICATIONS_ONLY_MIN_HOURS = 4.0

# «Учёба/пары» считаются с буфером на дорогу.
STUDY_TRANSIT_BUFFER_MINUTES = 30


MANUAL_OPERATING_BOUNDS_WEEKDAY = (time(8, 0), time(22, 0))
MANUAL_OPERATING_BOUNDS_NON_WORKING = (time(9, 0), time(21, 0))


# Длительности одной непрерывной смены (в часах) — одно место истины.
MIN_SHIFT_HOURS_DEFAULT = 2.0
MIN_SHIFT_HOURS_OPERATOR_HALFTIME = 3.0  # ставка 0.5 и 0.75
MIN_SHIFT_HOURS_APPLICATIONS_ONLY = 4.0


# --- Мягкие приоритеты (scoring/ранжирование) ---
# Эти числа используются при выборе кандидатов.
SCORE_DEFICIT_HOURS_MULTIPLIER = 25.0
SPREAD_PENALTY_THRESHOLD = 1.25
SPREAD_PENALTY_SLOPE = 14.0
SPREAD_PENALTY_CAP = 45.0
SLACK_BONUS_SLOPE = 0.45
SLACK_BONUS_CAP = 14.0

OPERATOR_WEEKDAY_BASE_BONUS = 8.0
OPERATOR_MONDAY_PEAK_SLOT_BONUS = 4.0
APPLICATIONS_ONLY_OPERATOR_SUFFICIENCY_PENALTY = -3.0

WEEKEND_BOOKED_DAYS_PENALTY_PER_DAY = 6.0
HOLIDAY_BOOKED_DAYS_PENALTY_PER_DAY = 6.0

CHAIN_LENGTH_PENALTY_BASE = 20.0
CHAIN_LENGTH_PENALTY_PER_EXTRA_DAY = 5.0

PREFERENCE_ADJUSTMENT_PREFER_OFF = -12.0

# --- Весовые коэффициенты для приоритета покрытия (gap-aware ranking) ---
COVERAGE_VIOLATION_WEIGHT_WEEKDAY_08_09 = 2.0
COVERAGE_VIOLATION_WEIGHT_WEEKDAY_09_18_OPERATOR_DEFICIT = 3.0
COVERAGE_VIOLATION_WEIGHT_WEEKDAY_09_18_APPS_DEFICIT = 3.0
COVERAGE_VIOLATION_WEIGHT_WEEKDAY_18_21_OPERATOR_DEFICIT = 2.0
COVERAGE_VIOLATION_WEIGHT_WEEKDAY_18_21_OPERATOR_EXCESS = 1.2
COVERAGE_VIOLATION_WEIGHT_WEEKDAY_21_22_EXACT_ONE = 2.5
COVERAGE_VIOLATION_WEIGHT_WEEKEND_09_21_EXACT_ONE = 2.0

# Масштаб перевода "баллов нарушений покрытия" в score кандидата.
COVERAGE_GAP_PRIORITY_WEIGHT = 60.0

# Отдельный сверхштраф за лишнего оператора в 21:00-22:00 (чтобы не жертвовать серединой дня).
LATE_WINDOW_OVERSTAFF_PENALTY_PER_POINT = 220.0


def normalize_rate(rate: float) -> float:
    return round(float(rate), 2)


def min_shift_duration_hours(employee_type: str, rate: float) -> float:
    """
    Минимальная длительность одной непрерывной смены для допустимого назначения.
    Логика должна совпадать с проверками планировщика и с фильтрацией safe_options.
    """
    if employee_type == EMPLOYEE_TYPE_APPLICATIONS_ONLY:
        return max(MIN_SHIFT_HOURS_DEFAULT, MIN_SHIFT_HOURS_APPLICATIONS_ONLY)
    if normalize_rate(rate) in (0.5, 0.75):
        return max(MIN_SHIFT_HOURS_DEFAULT, MIN_SHIFT_HOURS_OPERATOR_HALFTIME)
    return MIN_SHIFT_HOURS_DEFAULT


def manual_interval_bounds(day_is_non_working: bool) -> tuple[time, time]:
    """
    Операционные границы ручных смен.
    day_is_non_working: True = weekend/holiday, False = weekday.
    """
    return MANUAL_OPERATING_BOUNDS_NON_WORKING if day_is_non_working else MANUAL_OPERATING_BOUNDS_WEEKDAY


@dataclass(frozen=True)
class OperatorWindowRule:
    label: str
    start: time
    end: time
    operator_min: int
    operator_max: Optional[int] = None


@dataclass(frozen=True)
class ApplicationsOnlySupportRule:
    label: str
    start: time
    end: time
    operator_min: int
    applications_only_min: int


WEEKDAY_08_09 = OperatorWindowRule(label="08:00-09:00", start=time(8, 0), end=time(9, 0), operator_min=1, operator_max=1)
WEEKDAY_09_18_SUPPORT = ApplicationsOnlySupportRule(
    label="09:00-18:00",
    start=time(9, 0),
    end=time(18, 0),
    operator_min=2,
    applications_only_min=1,
)
WEEKDAY_18_21 = OperatorWindowRule(label="18:00-21:00", start=time(18, 0), end=time(21, 0), operator_min=1, operator_max=2)
WEEKDAY_21_22 = OperatorWindowRule(label="21:00-22:00", start=time(21, 0), end=time(22, 0), operator_min=1, operator_max=1)

WEEKEND_OR_HOLIDAY_09_21 = OperatorWindowRule(
    label="09:00-21:00",
    start=time(9, 0),
    end=time(21, 0),
    operator_min=1,
    operator_max=1,
)


def coverage_rules_ru_dict() -> dict[str, str]:
    """
    Текст для LLM (в summarize_for_ai и/или в аудитах).
    Важно: это именно человекочитаемые правила, а не код проверки.
    """
    return {
        "single_shift_per_day": "у каждого сотрудника не более одной непрерывной смены в календарный день (без перерыва и второго выхода на линию)",
        "weekday_08_09": "должен работать ровно 1 оператор",
        "weekday_09_18": "минимум 2 оператора и минимум 1 сотрудник 'только заявки'; оператор не должен оставаться один — рядом второй оператор или 'только заявки'",
        "weekday_18_21": "может работать 1 или 2 оператора",
        "weekday_21_22": "должен работать 1 оператор",
        "weekend_or_holiday_09_21": "обязательно должен работать ровно 1 оператор",
        "applications_only_shift_window": "09:00-18:00 только по будням",
        "applications_only_min_duration": f"минимум {int(APPLICATIONS_ONLY_MIN_HOURS)} часа",
        "applications_only_must_not_work_alone": "сотрудник 'только заявки' никогда не должен оставаться без оператора рядом и не работает по выходным и праздникам",
        "operator_halftime_min_duration": "для операторов ставок 0,5 и 0,75 минимум 3 часа",
        "operator_min_duration": "для всех операторов минимум 2 часа",
    }


def coverage_rules_en_for_prompts() -> str:
    """
    English фрагмент, который удобно вставлять в system prompts.
    """
    return (
        "Hard rules (do not violate): "
        "one continuous shift per employee per calendar day; "
        "weekday 08:00-09:00 exactly 1 operator; "
        "weekday 09:00-18:00 at least 2 operators and at least 1 applications_only, operator must not be alone; "
        "weekday 18:00-21:00 1-2 operators; "
        "weekday 21:00-22:00 exactly 1 operator; "
        "weekend/holiday 09:00-21:00 exactly 1 operator; "
        "applications_only only weekdays 09:00-18:00; "
        "applications_only min duration 4 hours and must not be alone without an operator nearby; "
        "min shift duration: operators >=2 hours, operators with rate 0.5/0.75 >=3 hours."
    )


def coverage_priority_bonus_for_slot_ru(
    *,
    slot_day_kind: str,
    required_employee_type: str | None,
    slot_start: time,
    slot_end: time,
    is_monday: bool,
) -> tuple[float, list[str]]:
    """
    Мягкие приоритеты (scoring) для выбора кандидатов.
    Сейчас используется в покрытии при ранжировании, но это не часть hard-валидатора.
    """
    reasons: list[str] = []
    score = 0.0
    if slot_day_kind in {"weekend", "holiday"}:
        if required_employee_type == EMPLOYEE_TYPE_OPERATOR:
            score += 120.0
            reasons.append("Weekend/holiday: обязательный оператор на 09:00-21:00 (+120)")
        return score, reasons

    if required_employee_type == EMPLOYEE_TYPE_OPERATOR:
        if slot_start == time(8, 0) and slot_end == time(9, 0):
            score += 140.0
            reasons.append("Operator morning mandatory 08:00-09:00 (+140)")
        elif not (slot_end <= time(9, 0) or slot_start >= time(18, 0)):
            score += 100.0
            reasons.append("Operator daytime mandatory window 09:00-18:00 (+100)")
            if is_monday:
                score += 25.0
                reasons.append("Monday peak for operators (+25)")
        elif not (slot_end <= time(18, 0) or slot_start >= time(21, 0)):
            score += 75.0
            reasons.append("Operator evening mandatory 18:00-21:00 (+75)")
        elif not (slot_end <= time(21, 0) or slot_start >= time(22, 0)):
            score += 95.0
            reasons.append("Operator late mandatory 21:00-22:00 (+95)")
    elif required_employee_type == EMPLOYEE_TYPE_APPLICATIONS_ONLY:
        # Интервальная проверка «пересекает 09:00-18:00»
        if not (slot_end <= APPLICATIONS_ONLY_START or slot_start >= APPLICATIONS_ONLY_END):
            score += 95.0
            reasons.append("applications_only mandatory window 09:00-18:00 (+95)")
            if is_monday:
                score += 20.0
                reasons.append("Monday peak for applications_only (+20)")
    return score, reasons


def monday_peak_operator_density_bonus_ru(operator_segments: int) -> tuple[float, str | None]:
    if operator_segments <= 1:
        return 22.0, "Monday bonus: daily operator core (<=1 segment) (+22)"
    if operator_segments == 2:
        return 10.0, "Monday bonus: daily operator core (=2 segments) (+10)"
    return 0.0, None


def _format_hours_ru(hours: float) -> str:
    # Показываем "2" вместо "2.0" для читаемости в UI.
    as_int = int(round(float(hours)))
    if abs(float(hours) - as_int) < 1e-9:
        return str(as_int)
    return str(hours).replace(".", ",")


def ui_coverage_rules_ru_lines() -> list[str]:
    """
    Строки для UI (в `index.html`) — один источник истины для отображаемых правил.
    """
    weekday_08_09 = WEEKDAY_08_09.label
    weekday_09_18 = WEEKDAY_09_18_SUPPORT.label
    weekday_18_21 = WEEKDAY_18_21.label
    weekday_21_22 = WEEKDAY_21_22.label
    weekend_09_21 = WEEKEND_OR_HOLIDAY_09_21.label

    min_default = _format_hours_ru(MIN_SHIFT_HOURS_DEFAULT)
    min_half = _format_hours_ru(MIN_SHIFT_HOURS_OPERATOR_HALFTIME)
    min_apps_only = _format_hours_ru(MIN_SHIFT_HOURS_APPLICATIONS_ONLY)

    apps_from = APPLICATIONS_ONLY_START.strftime("%H:%M")
    apps_to = APPLICATIONS_ONLY_END.strftime("%H:%M")

    return [
        f"Будни: {weekday_08_09} нужен 1 оператор",
        f"Будни: {weekday_09_18} нужны минимум {WEEKDAY_09_18_SUPPORT.operator_min} оператора и минимум 1 сотрудник «только заявки»",
        f"Будни: {weekday_18_21} нужен 1-{WEEKDAY_18_21.operator_max} оператора",
        f"Будни: {weekday_21_22} нужен 1 оператор",
        f"Выходные и праздники: с {WEEKEND_OR_HOLIDAY_09_21.start.strftime('%H:%M')} до {WEEKEND_OR_HOLIDAY_09_21.end.strftime('%H:%M')} работает ровно 1 оператор",
        f"Сотрудники «только заявки» работают только по будням с {apps_from} до {apps_to}",
        "Программа сама раскладывает день на рабочие интервалы",
        f"(не короче {min_default} ч; для ставок 0,5 и 0,75 — не короче {min_half} ч; для «только заявки» — не короче {min_apps_only} ч.).",
        "Ничего руками настраивать не нужно.",
    ]

