"""Общие подписи и legacy-коды ручных смен для UI и парсинга."""

WEEKDAY_LABELS = {
    "Monday": "понедельник",
    "Tuesday": "вторник",
    "Wednesday": "среда",
    "Thursday": "четверг",
    "Friday": "пятница",
    "Saturday": "суббота",
    "Sunday": "воскресенье",
}

DAY_KIND_LABELS = {
    "weekday": "будний",
    "weekend": "выходной",
    "holiday": "праздничный",
}

WEEKDAY_SHORT_LABELS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")

MONTH_NAMES = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}

LEGACY_MANUAL_SHIFT_CODES = {
    "WD_OPEN": {"label": "08:00 - 13:00", "start_time": "08:00", "normalized_code": "08:00-13:00"},
    "WD_DAY_ONE": {"label": "09:00 - 14:00", "start_time": "09:00", "normalized_code": "09:00-14:00"},
    "WD_DAY_TWO": {"label": "10:00 - 18:00", "start_time": "10:00", "normalized_code": "10:00-18:00"},
    "WD_LATE": {"label": "14:00 - 22:00", "start_time": "14:00", "normalized_code": "14:00-22:00"},
    "WE_MORNING": {"label": "09:00 - 15:00", "start_time": "09:00", "normalized_code": "09:00-15:00"},
    "WE_EVENING": {"label": "15:00 - 21:00", "start_time": "15:00", "normalized_code": "15:00-21:00"},
}

