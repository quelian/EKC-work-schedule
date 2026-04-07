"""JSON API роутер для Gantt-редактора графика v2."""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..database import (
    list_operator_profiles,
    list_holiday_entries,
    list_vacation_entries_range,
    list_monthly_preferences,
    list_schedule_assignments_range,
    list_study_constraints_range,
    list_schedule_preferences_range,
    list_calendar_day_overrides,
    replace_calendar_overrides_for_month,
    find_schedule_assignment_by_id,
    create_schedule_assignment_returning,
    update_schedule_assignment_by_id,
    delete_schedule_assignment_by_id,
)
from ..services.availability_service import (
    compute_availability_range,
    compute_employee_target_hours,
    get_non_working_dates_range,
)
from ..calendar_layout import base_non_working_dates as calc_base_non_working

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/schedule/editor", tags=["schedule-editor-v2"])

# =============================================================================
# Debounce — in-memory механизм для предотвращения дублей запросов
# =============================================================================

class ShiftDebounce:
    """Отклоняет повторные запросы к той же смене в течение 500 ms."""

    def __init__(self, window_ms: int = 500) -> None:
        self.window_ms = window_ms
        self._timestamps: dict[str, float] = {}
        self._cleanup_count: int = 0

    def check(self, key: str) -> bool:
        """Возвращает False если запрос заблокирован (дубликат в окне debounce)."""
        now = time.monotonic() * 1000
        last = self._timestamps.get(key, 0)
        if now - last < self.window_ms:
            return False
        self._timestamps[key] = now
        # Периодическая очистка старых записей
        self._cleanup_count += 1
        if self._cleanup_count > 100:
            self._cleanup()
        return True

    def _cleanup(self, max_age_ms: int = 10_000) -> None:
        now = time.monotonic() * 1000
        self._timestamps = {
            k: v for k, v in self._timestamps.items()
            if now - v < max_age_ms
        }
        self._cleanup_count = 0


_debounce = ShiftDebounce()

# =============================================================================
# Pydantic-модели
# =============================================================================

class ShiftCreate(BaseModel):
    employee_name: str
    date: str           # "YYYY-MM-DD"
    start_time: str     # "HH:MM"
    end_time: str       # "HH:MM"
    shift_type: str = "operator"
    note: str = ""


class ShiftUpdate(BaseModel):
    shift_id: int
    employee_name: Optional[str] = None
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    shift_type: Optional[str] = None
    note: Optional[str] = None


class ShiftDelete(BaseModel):
    shift_id: int


# =============================================================================
# Хелпер авторизации
# =============================================================================

def _check_admin(request: Request) -> JSONResponse | None:
    """Проверяет что пользователь — админ. Возвращает ошибку или None."""
    if not request.session.get("logged_in_user"):
        return JSONResponse({"error": "Необходима авторизация"}, status_code=401)
    if request.session.get("user_role") != "admin":
        return JSONResponse({"error": "Доступ только для администраторов"}, status_code=403)
    return None


# =============================================================================
# GET /api/v1/schedule/editor/data — Все данные для Gantt-редактора
# =============================================================================

@router.get("/data")
async def get_editor_data(
    request: Request,
    start_date: str = Query(..., description="Начало диапазона (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конец диапазона (YYYY-MM-DD)"),
    year: int | None = Query(None, description="Базовый год для норм часов"),
    month: int | None = Query(None, description="Базовый месяц для норм часов"),
):
    """
    Возвращает все данные для Gantt-редактора за диапазон дат:
    shifts, availability, employees, target_hours, holidays, non_working_dates.
    """
    auth_error = _check_admin(request)
    if auth_error:
        return auth_error

    try:
        sd = date.fromisoformat(start_date)
        ed = date.fromisoformat(end_date)
    except ValueError:
        return JSONResponse({"error": "Неверный формат даты"}, status_code=400)

    # Загружаем данные
    shifts = list_schedule_assignments_range(sd, ed)
    availability = compute_availability_range(sd, ed)
    study_constraints = list_study_constraints_range(sd, ed)
    preferences = list_schedule_preferences_range(sd, ed)
    non_working = get_non_working_dates_range(sd, ed)

    # Employees (все активные)
    operators = list_operator_profiles(active_only=True)
    employees = [
        {
            "name": emp.name,
            "employee_id": emp.employee_id,
            "employee_type": emp.employee_type,
            "rate": emp.rate,
            "max_consecutive_days": emp.max_consecutive_days,
        }
        for emp in operators
    ]

    # Holidays
    holidays_raw = list_holiday_entries()
    holidays = [
        {"date": h.holiday_date.isoformat(), "name": h.name}
        for h in holidays_raw
        if sd <= h.holiday_date <= ed
    ]

    # Vacations (пересекающиеся с диапазоном)
    vacations_raw = list_vacation_entries_range(sd, ed)
    vacations = [
        {
            "id": v.id,
            "employee_name": v.employee_name,
            "start_date": v.start_date.isoformat(),
            "end_date": v.end_date.isoformat(),
            "note": v.note,
        }
        for v in vacations_raw
    ]

    # Target hours for the editor should be based on the visible month,
    # with a safe fallback to the date range if the caller does not provide it.
    if year is not None and month is not None:
        months_covered: set[tuple[int, int]] = {(year, month)}
    else:
        months_covered = {(sd.year, sd.month), (ed.year, ed.month)}
        if sd.year == ed.year and sd.month == ed.month:
            months_covered = {(sd.year, sd.month)}
        elif (ed - sd).days > 31:
            cursor = sd.replace(day=1)
            while cursor <= ed:
                months_covered.add((cursor.year, cursor.month))
                next_month = cursor.month + 1
                next_year = cursor.year + (1 if next_month == 13 else 0)
                next_month = 1 if next_month == 13 else next_month
                cursor = date(next_year, next_month, 1)
        if not months_covered:
            months_covered = {(sd.year, sd.month)}

    # Monthly preferences returned below are used by the editor footer section.

    target_hours: dict[str, float] = {}
    for y, m in months_covered:
        th = compute_employee_target_hours(y, m)
        for name, hours in th.items():
            # Если несколько месяцев, суммируем (хотя обычно 1 месяц)
            target_hours[name] = target_hours.get(name, 0) + hours

    # Monthly preferences
    monthly_prefs_all: list[dict] = []
    for y, m in months_covered:
        mp = list_monthly_preferences(y, m)
        monthly_prefs_all.extend(mp)

    return JSONResponse({
        "shifts": shifts,
        "availability": availability,
        "employees": employees,
        "employee_target_hours": target_hours,
        "holidays": holidays,
        "non_working_dates": non_working,
        "vacations": vacations,
        "study_constraints": study_constraints,
        "schedule_preferences": preferences,
        "monthly_preferences": monthly_prefs_all,
    })


# =============================================================================
# POST /api/v1/schedule/editor/shifts — Создать смену
# =============================================================================

@router.post("/shifts")
async def create_shift(request: Request, payload: ShiftCreate):
    """Создаёт смену. Возвращает созданный объект с ID."""
    auth_error = _check_admin(request)
    if auth_error:
        return auth_error

    # Валидация
    if not payload.employee_name.strip():
        return JSONResponse({"error": "Имя сотрудника не указано"}, status_code=400)
    if not payload.start_time or not payload.end_time:
        return JSONResponse({"error": "Время начала и окончания обязательны"}, status_code=400)
    if payload.start_time >= payload.end_time:
        return JSONResponse({"error": "Время начала должно быть раньше окончания"}, status_code=400)

    # Debounce check
    debounce_key = f"create:{payload.employee_name}:{payload.date}:{payload.start_time}:{payload.end_time}"
    if not _debounce.check(debounce_key):
        return JSONResponse({"error": "Повторный запрос. Подождите немного."}, status_code=429)

    try:
        shift = create_schedule_assignment_returning(
            employee_name=payload.employee_name.strip(),
            date_value=payload.date,
            start_time=payload.start_time,
            end_time=payload.end_time,
            shift_type=payload.shift_type,
            note=payload.note,
        )
        return JSONResponse({"status": "ok", "shift": shift})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error("Failed to create shift: %s", e, exc_info=True)
        return JSONResponse({"error": "Не удалось создать смену. Попробуйте ещё раз."}, status_code=500)


# =============================================================================
# PUT /api/v1/schedule/editor/shifts — Обновить смену
# =============================================================================

@router.put("/shifts")
async def update_shift(request: Request, payload: ShiftUpdate):
    """Обновляет смену по ID. Для drag-to-move/resize."""
    auth_error = _check_admin(request)
    if auth_error:
        return auth_error

    if payload.start_time and payload.end_time and payload.start_time >= payload.end_time:
        return JSONResponse({"error": "Время начала должно быть раньше окончания"}, status_code=400)

    # Debounce check
    debounce_key = f"update:{payload.shift_id}"
    if not _debounce.check(debounce_key):
        return JSONResponse({"error": "Повторный запрос. Подождите немного."}, status_code=429)

    # Check for concurrent modifications
    try:
        current = find_schedule_assignment_by_id(payload.shift_id)
        if current is None:
            return JSONResponse({"error": "Смена не найдена"}, status_code=404)

        updated_at_str = current.get("updated_at")
        if updated_at_str:
            try:
                from datetime import datetime
                stored_ts = datetime.fromisoformat(updated_at_str)
            except (ValueError, TypeError):
                pass  # Игнорируем если формат даты нечитаем

        shift = update_schedule_assignment_by_id(
            payload.shift_id,
            employee_name=payload.employee_name,
            date_value=payload.date,
            start_time=payload.start_time,
            end_time=payload.end_time,
            shift_type=payload.shift_type,
            note=payload.note,
        )
        if shift is None:
            return JSONResponse({"error": "Смена не найдена"}, status_code=404)

        return JSONResponse({"status": "ok", "shift": shift})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error("Failed to update shift: %s", e, exc_info=True)
        return JSONResponse({"error": "Не удалось обновить смену. Попробуйте ещё раз."}, status_code=500)


# =============================================================================
# DELETE /api/v1/schedule/editor/shifts — Удалить смену
# =============================================================================

@router.delete("/shifts")
async def delete_shift(request: Request, payload: ShiftDelete):
    """Удаляет смену по ID."""
    auth_error = _check_admin(request)
    if auth_error:
        return auth_error

    # Debounce check
    debounce_key = f"delete:{payload.shift_id}"
    if not _debounce.check(debounce_key):
        return JSONResponse({"error": "Повторный запрос. Подождите немного."}, status_code=429)

    try:
        success = delete_schedule_assignment_by_id(payload.shift_id)
        if not success:
            return JSONResponse({"error": "Смена не найдена"}, status_code=404)

        return JSONResponse({"status": "ok"})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error("Failed to delete shift: %s", e, exc_info=True)
        return JSONResponse({"error": "Не удалось удалить смену. Попробуйте ещё раз."}, status_code=500)


# =============================================================================
# PATCH /api/v1/schedule/editor/set-non-working — Установить выходной день
# =============================================================================


@router.patch("/set-non-working")
async def set_non_working(request: Request):
    """
    Переключает статус одной даты — выходной/рабочий.
    Загружает текущие overrides, применяет изменение,
    сохраняет через replace_calendar_overrides_for_month,
    возвращает обновлённый non_working_dates для текущего диапазона.
    """
    auth_error = _check_admin(request)
    if auth_error:
        return auth_error

    try:
        body = await request.json()
        target_str = body["date"]
        is_non_working = bool(body["is_non_working"])
    except (ValueError, KeyError, TypeError):
        return JSONResponse({"error": "Ожидается JSON с полями date и is_non_working"}, status_code=400)

    try:
        target = date.fromisoformat(target_str)
    except ValueError:
        return JSONResponse({"error": "Неверный формат даты"}, status_code=400)

    holidays = list_holiday_entries()
    base_nw = calc_base_non_working(target.year, target.month, holidays)
    existing_overrides = list_calendar_day_overrides()

    # Build the full selected set for this month
    selected = set(base_nw)
    for ov in existing_overrides:
        if ov.calendar_date.year == target.year and ov.calendar_date.month == target.month:
            if ov.is_non_working:
                selected.add(ov.calendar_date)
            else:
                selected.discard(ov.calendar_date)

    # Set the target date
    if is_non_working:
        selected.add(target)
    else:
        selected.discard(target)

    save_calendar_overrides_for_month(target.year, target.month, selected)

    # Determine view range from the request or default to the current month
    qs = request.query_params
    start_param = qs.get("start_date")
    end_param = qs.get("end_date")
    if start_param and end_param:
        try:
            view_start = date.fromisoformat(start_param)
            view_end = date.fromisoformat(end_param)
        except ValueError:
            view_start = date(target.year, target.month, 1)
            from calendar import monthrange as mr
            _, last = mr(target.year, target.month)
            view_end = date(target.year, target.month, last)
    else:
        from calendar import monthrange as mr
        view_start = date(target.year, target.month, 1)
        _, last = mr(target.year, target.month)
        view_end = date(target.year, target.month, last)

    non_working_dates = get_non_working_dates_range(view_start, view_end)

    return JSONResponse({
        "status": "ok",
        "date": target_str,
        "is_non_working": is_non_working,
        "non_working_dates": non_working_dates,
    })


def save_calendar_overrides_for_month(year: int, month: int, selected_dates: set[date]) -> None:
    """Сохраняет выбранные нерабочие дни, записывая дельты от базовых выходных."""
    holidays = list_holiday_entries()
    base_nw = calc_base_non_working(year, month, holidays)
    replace_calendar_overrides_for_month(year, month, selected_dates, base_nw)
