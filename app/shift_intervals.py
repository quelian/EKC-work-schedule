"""Фабрика стандартных рабочих интервалов для планировщика."""
from __future__ import annotations

from datetime import time

from .models import ShiftTemplate

def generated_work_intervals() -> list[ShiftTemplate]:
    """Рабочие интервалы без «часовых» нарезок: минимум 3 ч в основной сетке (≥2 ч для всех, ≥3 ч для 0,5/0,75)."""
    intervals: list[ShiftTemplate] = []

    def add_interval(
        *,
        code: str,
        label: str,
        start: time,
        end: time,
        applies_to: str,
        employee_type: str,
        optional: bool = False,
    ) -> None:
        sm = start.hour * 60 + start.minute
        em = end.hour * 60 + end.minute
        intervals.append(
            ShiftTemplate(
                code=code,
                label=label,
                start_time=start,
                end_time=end,
                duration_hours=(em - sm) / 60.0,
                applies_to=applies_to,
                required_staff=1,
                required_employee_type=employee_type,
                optional=optional,
            )
        )

    # Будни: утренний якорь + три блока по 3 ч (09–18, два обязательных оператора + два опциональных линии)
    add_interval(
        code="WD-OP-08:00-11:00",
        label="08:00-11:00",
        start=time(8, 0),
        end=time(11, 0),
        applies_to="weekday",
        employee_type="operator",
    )
    for sh, eh in ((9, 12), (12, 15), (15, 18)):
        span_lbl = f"{sh:02d}:00-{eh:02d}:00"
        add_interval(
            code=f"WD-OP1-{span_lbl}",
            label=span_lbl,
            start=time(sh, 0),
            end=time(eh, 0),
            applies_to="weekday",
            employee_type="operator",
        )
        add_interval(
            code=f"WD-OP2-{span_lbl}",
            label=span_lbl,
            start=time(sh, 0),
            end=time(eh, 0),
            applies_to="weekday",
            employee_type="operator",
        )
        add_interval(
            code=f"WD-OP3-{span_lbl}",
            label=span_lbl,
            start=time(sh, 0),
            end=time(eh, 0),
            applies_to="weekday",
            employee_type="operator",
            optional=True,
        )
        add_interval(
            code=f"WD-OP4-{span_lbl}",
            label=span_lbl,
            start=time(sh, 0),
            end=time(eh, 0),
            applies_to="weekday",
            employee_type="operator",
            optional=True,
        )

    add_interval(
        code="WD-APP-09:00-13:00",
        label="09:00-13:00",
        start=time(9, 0),
        end=time(13, 0),
        applies_to="weekday",
        employee_type="applications_only",
    )
    add_interval(
        code="WD-APP-13:00-18:00",
        label="13:00-18:00",
        start=time(13, 0),
        end=time(18, 0),
        applies_to="weekday",
        employee_type="applications_only",
    )
    add_interval(
        code="WD-APP2-09:00-13:00",
        label="09:00-13:00",
        start=time(9, 0),
        end=time(13, 0),
        applies_to="weekday",
        employee_type="applications_only",
        optional=True,
    )
    add_interval(
        code="WD-APP2-13:00-18:00",
        label="13:00-18:00",
        start=time(13, 0),
        end=time(18, 0),
        applies_to="weekday",
        employee_type="applications_only",
        optional=True,
    )

    # Вечер и закрытие дня одним блоком 18:00–22:00 (4 ч, без отдельного «одного часа»)
    add_interval(
        code="WD-OP-18:00-22:00",
        label="18:00-22:00",
        start=time(18, 0),
        end=time(22, 0),
        applies_to="weekday",
        employee_type="operator",
    )
    add_interval(
        code="WD-OP2-18:00-22:00",
        label="18:00-22:00",
        start=time(18, 0),
        end=time(22, 0),
        applies_to="weekday",
        employee_type="operator",
        optional=True,
    )

    for sh, eh in ((9, 12), (12, 15), (15, 18), (18, 21)):
        span_lbl = f"{sh:02d}:00-{eh:02d}:00"
        add_interval(
            code=f"WE-OP-{span_lbl}",
            label=span_lbl,
            start=time(sh, 0),
            end=time(eh, 0),
            applies_to="weekend_or_holiday",
            employee_type="operator",
        )
        add_interval(
            code=f"WE-OP2-{span_lbl}",
            label=span_lbl,
            start=time(sh, 0),
            end=time(eh, 0),
            applies_to="weekend_or_holiday",
            employee_type="operator",
            optional=True,
        )

    return intervals


def generated_work_interval_options() -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    options: list[dict[str, str]] = []
    for interval in generated_work_intervals():
        unique_key = (
            interval.label,
            interval.start_time.strftime("%H:%M"),
            interval.end_time.strftime("%H:%M"),
        )
        if unique_key in seen:
            continue
        seen.add(unique_key)
        options.append(
            {
                "code": interval.label,
                "label": interval.label,
                "start_time": interval.start_time.strftime("%H:%M"),
                "end_time": interval.end_time.strftime("%H:%M"),
            }
        )
    return options
