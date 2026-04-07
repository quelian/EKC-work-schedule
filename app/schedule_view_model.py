"""Представление результата расчёта для HTML/экспорта (виджеты, карточки, пайплайн)."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date

from .calendar_layout import merge_calendar_entries
from .ekc_constants import DAY_KIND_LABELS
from .form_state import translate_weekday
from .models import (
    Employee,
    ScheduleResult,
    employee_type_label,
)

def build_view_model(
    result: ScheduleResult,
    employees: list[Employee],
    *,
    year: int | None = None,
    month: int | None = None,
    holidays: set[date] | None = None,
) -> dict[str, object]:
    assignments_by_day: dict[str, list[dict[str, object]]] = defaultdict(list)
    employees_by_name = {employee.name: employee for employee in employees}
    export_rows = []
    total_slots = len(result.assignments)
    filled_slots = 0
    for assignment in result.assignments:
        row = {
            "date": assignment.slot.date.isoformat(),
            "day_kind": assignment.slot.day_kind,
            "shift_code": assignment.slot.template.code,
            "shift_label": assignment.slot.template.label,
            "position": assignment.slot.position + 1,
            "employee_name": assignment.employee_name or "",
            "duration_hours": assignment.slot.template.duration_hours,
            "start_time": assignment.slot.template.start_time.strftime("%H:%M"),
            "end_time": assignment.slot.template.end_time.strftime("%H:%M"),
        }
        export_rows.append(row)
        if assignment.employee_name:
            filled_slots += 1
        assignments_by_day[assignment.slot.date.isoformat()].append(
            {
                "date": assignment.slot.date.strftime("%d.%m.%Y"),
                "weekday_name": translate_weekday(assignment.slot.date),
                "day_kind": assignment.slot.day_kind,
                "day_kind_label": DAY_KIND_LABELS[assignment.slot.day_kind],
                "shift_label": assignment.slot.template.label,
                "shift_code": assignment.slot.template.code,
                "start_time": assignment.slot.template.start_time.strftime("%H:%M"),
                "end_time": assignment.slot.template.end_time.strftime("%H:%M"),
                "time_range": f"{assignment.slot.template.start_time.strftime('%H:%M')} - {assignment.slot.template.end_time.strftime('%H:%M')}",
                "position": assignment.slot.position + 1,
                "employee_name": assignment.employee_name or "Не закрыто",
                "filled": bool(assignment.employee_name),
                "is_manual": assignment.is_manual,
                "source": assignment.source,
                "source_label": assignment_source_label(assignment.source),
            }
        )

    for iso_key in list(assignments_by_day.keys()):
        assignments_by_day[iso_key] = merge_calendar_entries(assignments_by_day[iso_key])

    daily_rows = []
    for key in sorted(assignments_by_day):
        entries = assignments_by_day[key]
        daily_rows.append(
            {
                "date": entries[0]["date"],
                "weekday_name": entries[0]["weekday_name"],
                "day_kind": entries[0]["day_kind"],
                "day_kind_label": entries[0]["day_kind_label"],
                "entries": entries,
            }
        )

    employee_stats = []
    for stat in result.employee_stats:
        employee = employees_by_name.get(stat.employee_name)
        target_hours = employee.preferred_hours if employee else 0.0
        employee_stats.append(
            {
                "employee_name": stat.employee_name,
                "assigned_hours": stat.assigned_hours,
                "assigned_days": stat.assigned_days,
                "weekend_days": stat.weekend_days,
                "holiday_days": stat.holiday_days,
                "consecutive_days_peak": stat.consecutive_days_peak,
                "target_hours": target_hours,
                "delta_hours": target_hours - stat.assigned_hours,
                "delta_hours_abs": abs(target_hours - stat.assigned_hours),
                "max_hours": employee.max_hours if employee else 0.0,
                "rate": employee.rate if employee else 1.0,
                "employee_type": employee.employee_type if employee else "operator",
                "employee_type_label": employee_type_label(employee.employee_type if employee else "operator"),
                "max_consecutive_hours": employee.max_consecutive_hours if employee else 0.0,
                "norm_hours_per_workday": employee.norm_hours_per_workday if employee else 0.0,
            }
        )

    summary = {
        "total_slots": total_slots,
        "filled_slots": filled_slots,
        "open_slots": total_slots - filled_slots,
        "employee_count": len(result.employee_stats),
    }
    conflict_cards = build_conflict_cards(result.warnings, summary, employee_stats)

    eff_year = year
    eff_month = month
    if eff_year is None or eff_month is None:
        if result.assignments:
            eff_year = result.assignments[0].slot.date.year
            eff_month = result.assignments[0].slot.date.month
        else:
            today = date.today()
            eff_year = eff_year or today.year
            eff_month = eff_month or today.month
    holiday_iso = sorted(d.isoformat() for d in (holidays or set()))

    people_timesheet = []
    for stat in sorted(result.employee_stats, key=lambda s: s.employee_name.lower()):
        emp = employees_by_name.get(stat.employee_name)
        people_timesheet.append(
            {
                "name": stat.employee_name,
                "assigned_hours": stat.assigned_hours,
                "preferred_hours": float(emp.preferred_hours) if emp else 0.0,
                "rate": float(emp.rate) if emp else 1.0,
                "norm_hours_per_workday": float(emp.norm_hours_per_workday) if emp else 0.0,
                "position_label": employee_type_label(emp.employee_type) if emp else "",
            }
        )

    timesheet_export_payload = json.dumps(
        {
            "year": eff_year,
            "month": eff_month,
            "holidays": holiday_iso,
            "rows": export_rows,
            "people": people_timesheet,
        },
        ensure_ascii=False,
    )

    return {
        "daily_rows": daily_rows,
        "calendar_entries_by_date": dict(assignments_by_day),
        "employee_stats": employee_stats,
        "warnings": result.warnings,
        "conflict_cards": conflict_cards,
        "export_payload": json.dumps(export_rows, ensure_ascii=False),
        "timesheet_export_payload": timesheet_export_payload,
        "summary": summary,
    }


def build_conflict_cards(
    warnings: list[object],
    summary: dict[str, int],
    employee_stats: list[dict[str, object]],
) -> list[dict[str, object]]:
    warning_messages = [str(getattr(warning, "message", "")) for warning in warnings]
    cards: list[dict[str, object]] = []

    open_slot_messages = [message for message in warning_messages if "не удалось закрыть" in message]
    if summary.get("open_slots", 0) > 0 or open_slot_messages:
        cards.append(
            build_conflict_card(
                severity="critical",
                title="Есть незакрытые интервалы",
                description=f"Сейчас осталось пустыми {summary.get('open_slots', 0)} рабочих интервалов.",
                question="Как будем их закрывать?",
                examples=open_slot_messages[:3],
                actions=[
                    conflict_action("Добавить ручные смены", "section-manual-shifts", focus_id="manual-shift-form"),
                    conflict_action("Открыть список интервалов", "section-calendar", tab_group="results", tab="shifts"),
                    conflict_action("Проверить сотрудников", "section-people", focus_id="operator-form"),
                    conflict_action("Пока оставить как есть"),
                ],
            )
        )

    operator_gap_messages = [
        message
        for message in warning_messages
        if "нет ни одного сотрудника со статусом 'оператор'" in message or "оператор работает один" in message
    ]
    if operator_gap_messages:
        cards.append(
            build_conflict_card(
                severity="critical",
                title="Есть окна без нормального покрытия",
                description="Нашлись интервалы, где операторов не хватает или оператор остается один.",
                question="Что выбираете для исправления?",
                examples=operator_gap_messages[:3],
                actions=[
                    conflict_action("Добавить смену оператору", "section-manual-shifts", focus_id="manual-shift-form"),
                    conflict_action("Проверить сотрудников", "section-people", focus_id="operator-form"),
                    conflict_action("Открыть проблемные часы", "section-calendar", tab_group="results", tab="shifts"),
                    conflict_action("Пока оставить как есть"),
                ],
            )
        )

    underfilled_employees = [stat for stat in employee_stats if float(stat.get("delta_hours", 0.0)) > 0.01]
    underfilled_messages = [message for message in warning_messages if "не добрал(а)" in message]
    if underfilled_employees:
        cards.append(
            build_conflict_card(
                severity="warning",
                title="Есть недобор часов",
                description=f"{len(underfilled_employees)} сотрудник(ов) пока не добирают свою норму часов.",
                question="Как будем добирать часы?",
                examples=underfilled_messages[:3],
                actions=[
                    conflict_action("Добавить ручные смены", "section-manual-shifts", focus_id="manual-shift-form"),
                    conflict_action("Проверить ставки сотрудников", "section-people", focus_id="operator-form"),
                    conflict_action("Проверить календарь месяца", "section-graph"),
                    conflict_action("Пока оставить как есть"),
                ],
            )
        )

    capacity_messages = [message for message in warning_messages if "Не хватает минимум" in message]
    if capacity_messages:
        cards.append(
            build_conflict_card(
                severity="critical",
                title="Рабочих часов месяца не хватает",
                description="Даже идеальная расстановка сейчас не позволит закрыть все нормы часов.",
                question="Что меняем в первую очередь?",
                examples=capacity_messages[:2],
                actions=[
                    conflict_action("Проверить ставки сотрудников", "section-people", focus_id="operator-form"),
                    conflict_action("Проверить календарь месяца", "section-graph"),
                    conflict_action("Добавить ручные смены", "section-manual-shifts", focus_id="manual-shift-form"),
                    conflict_action("Пока оставить как есть"),
                ],
            )
        )

    chain_messages = [message for message in warning_messages if "пик подряд" in message]
    if chain_messages:
        cards.append(
            build_conflict_card(
                severity="warning",
                title="Есть слишком длинные цепочки дней",
                description="У некоторых сотрудников получаются слишком длинные серии подряд.",
                question="Как хотим это смягчить?",
                examples=chain_messages[:3],
                actions=[
                    conflict_action("Проверить отпуска", "section-vacations"),
                    conflict_action("Перераздать вручную", "section-manual-shifts", focus_id="manual-shift-form"),
                    conflict_action("Проверить сотрудников", "section-people", focus_id="operator-form"),
                    conflict_action("Пока оставить как есть"),
                ],
            )
        )

    overtime_messages = [message for message in warning_messages if "выше нормы" in message]
    if overtime_messages:
        cards.append(
            build_conflict_card(
                severity="warning",
                title="Есть переработка выше нормы",
                description="Некоторые сотрудники уже ушли выше своей нормы часов.",
                question="Что выбираете?",
                examples=overtime_messages[:3],
                actions=[
                    conflict_action("Открыть нагрузку", "section-calendar", tab_group="results", tab="load"),
                    conflict_action("Перераздать вручную", "section-manual-shifts", focus_id="manual-shift-form"),
                    conflict_action("Проверить ставки сотрудников", "section-people", focus_id="operator-form"),
                    conflict_action("Пока оставить как есть"),
                ],
            )
        )

    return cards


def build_conflict_card(
    severity: str,
    title: str,
    description: str,
    question: str,
    examples: list[str],
    actions: list[dict[str, str]],
) -> dict[str, object]:
    return {
        "severity": severity,
        "title": title,
        "description": description,
        "question": question,
        "examples": examples,
        "actions": actions,
    }


def conflict_action(
    label: str,
    target: str | None = None,
    *,
    tab_group: str | None = None,
    tab: str | None = None,
    open_details: str | None = None,
    focus_id: str | None = None,
) -> dict[str, str]:
    action = {
        "label": label,
        "target": target or "",
        "tab_group": tab_group or "",
        "tab": tab or "",
        "open_details": open_details or "",
        "focus_id": focus_id or "",
    }
    return action


def assignment_source_label(source: str) -> str:
    if source == "manual":
        return "вручную"
    if source == "system":
        return "авто-исправление"
    return ""

