"""API endpoints для управления ограничениями (учёба, пожелания)."""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
import logging
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .database import (
    list_study_constraints,
    list_schedule_preferences,
    list_monthly_preferences,
    upsert_study_constraint,
    delete_study_constraint,
    upsert_schedule_preference,
    delete_schedule_preference,
    upsert_monthly_preference,
    delete_monthly_preference,
    list_operator_profiles,
    is_submission_window_open,
)
from .form_state import resolve_period
from .parsers import ParseError, parse_date, parse_time
from .templating import templates

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Auth helper
# =============================================================================

def _check_login(request: Request) -> HTMLResponse | None:
    """Returns error response or None if logged in."""
    if not request.session.get("logged_in_user"):
        return HTMLResponse(
            '<html><body>Необходима авторизация. <a href="/login">Войти</a></body></html>',
            status_code=401,
        )
    return None


def _check_write_access(request: Request, employee_name: str) -> HTMLResponse | None:
    """Returns 403 if user cannot write for employee_name."""
    current_user = request.session.get("logged_in_user")
    user_role = request.session.get("user_role")
    # Admin can write for anyone
    if user_role == "admin":
        return None
    # Employee can only modify own data
    if current_user != employee_name.strip():
        return HTMLResponse(
            '<html><body>Доступ только для своей учётной записи.</body></html>',
            status_code=403,
        )
    return None


def _check_submission_window(request: Request, employee_name: str) -> HTMLResponse | None:
    """Returns redirect with error if submission window is closed for employee."""
    user_role = request.session.get("user_role")
    # Admin不受 ограничений
    if user_role == "admin":
        return None
    if not is_submission_window_open():
        from fastapi.responses import RedirectResponse
        current_user = request.session.get("logged_in_user", "")
        request.session["flash_error"] = (
            "Редактирование расписания временно недоступно. "
            "Обратитесь к администратору для получения информации о сроках."
        )
        return RedirectResponse(f"/my-schedule?employee_name={employee_name or current_user}", status_code=303)
    return None


def _redirect_to_constraints(
    request: Request, year: int, month: int
) -> None:
    """Helper to reduce duplication for redirects."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/constraints?year={year}&month={month}", status_code=303)


# =============================================================================
# REDIRECTS - Старые URL на новый единый маршрут
# =============================================================================

@router.get("/constraints/study", response_class=HTMLResponse)
async def redirect_study_to_constraints(request: Request):
    """Перенаправляет со старого /constraints/study на /constraints."""
    err = _check_login(request)
    if err:
        return err
    from fastapi.responses import RedirectResponse
    year = request.query_params.get("year")
    month = request.query_params.get("month")
    params = []
    if year:
        params.append(f"year={year}")
    if month:
        params.append(f"month={month}")
    query = f"?{'&'.join(params)}" if params else ""
    return RedirectResponse(f"/constraints{query}", status_code=303)


@router.get("/constraints/preferences", response_class=HTMLResponse)
async def redirect_preferences_to_constraints(request: Request):
    """Перенаправляет со старого /constraints/preferences на /constraints."""
    err = _check_login(request)
    if err:
        return err
    from fastapi.responses import RedirectResponse
    year = request.query_params.get("year")
    month = request.query_params.get("month")
    params = []
    if year:
        params.append(f"year={year}")
    if month:
        params.append(f"month={month}")
    query = f"?{'&'.join(params)}" if params else ""
    return RedirectResponse(f"/constraints{query}", status_code=303)


# =============================================================================
# UNIFIED CONSTRAINTS PAGE (Все ограничения)
# =============================================================================

@router.get("/constraints", response_class=HTMLResponse)
async def get_constraints_page(
    request: Request,
    year: int | None = None,
    month: int | None = None,
) -> HTMLResponse:
    """Единая страница просмотра всех ограничений (учёба и пожелания)."""
    year, month = resolve_period(year, month)

    # Загружаем и учёбу, и пожелания
    study_list = list_study_constraints(year, month)
    pref_list = list_schedule_preferences(year, month)

    # Группируем по сотрудникам
    study_by_employee: dict[str, list] = {}
    for item in study_list:
        name = item["employee_name"]
        if name not in study_by_employee:
            study_by_employee[name] = []
        study_by_employee[name].append(item)

    pref_by_employee: dict[str, list] = {}
    for item in pref_list:
        name = item["employee_name"]
        if name not in pref_by_employee:
            pref_by_employee[name] = []
        pref_by_employee[name].append(item)

    return templates.TemplateResponse(
        "constraints_new.html",
        {
            "request": request,
            "year": year,
            "month": month,
            "month_label": f"{'Январь Февраль Март Апрель Май Июнь Июль Август Сентябрь Октябрь Ноябрь Декабрь'.split()[month-1]} {year}",
            "employees": list_operator_profiles(),
            "study_constraints_by_employee": study_by_employee,
            "preferences_by_employee": pref_by_employee,
            "form_values": {},
            "active_page": "constraints",
        },
    )


@router.post("/constraints/study/save", response_class=HTMLResponse)
async def save_study_constraint(
    request: Request,
    employee_name: str = Form(...),
    constraint_date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    note: str = Form(""),
    is_strict: int = Form(1),
    return_year: int | None = Form(None),
    return_month: int | None = Form(None),
) -> HTMLResponse:
    """Сохраняет ограничение по учёбе."""
    err = _check_login(request)
    if err:
        return err
    write_err = _check_write_access(request, employee_name)
    if write_err:
        return write_err
    window_err = _check_submission_window(request, employee_name)
    if window_err:
        return window_err
    year, month = resolve_period(return_year, return_month)

    try:
        if not employee_name.strip():
            raise ParseError("Укажите сотрудника.")

        constraint_date_parsed = parse_date(constraint_date, "constraint_date")

        # Проверка времени
        if not start_time or not end_time:
            raise ParseError("Укажите время начала и окончания учёбы.")

        start_time_parsed = parse_time(start_time)
        end_time_parsed = parse_time(end_time)

        if end_time_parsed <= start_time_parsed:
            raise ParseError("Время окончания должно быть позже времени начала.")

        upsert_study_constraint(
            employee_name=employee_name.strip(),
            date_value=constraint_date_parsed,
            start_time=start_time,
            end_time=end_time,
            note=note.strip(),
            is_strict=(is_strict == 1),
        )
        # Telegram notification: constraint add
        try:
            from .services.telegram_notifications import notify_constraint_add
            actor = request.session.get("logged_in_user", "unknown")
            notify_constraint_add(actor, employee_name.strip(), constraint_date, start_time, end_time, note.strip())
        except Exception:
            pass

    except (ParseError, ValueError) as error:
        logger.warning("constraints: save study constraint error: %s", error)
        request.session["flash_error"] = f"Ошибка сохранения: {error}"

    # Перенаправляем обратно на единую страницу ограничений
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/constraints?year={year}&month={month}", status_code=303)


@router.post("/constraints/study/delete", response_class=HTMLResponse)
async def delete_study_constraint_endpoint(
    request: Request,
    employee_name: str = Form(...),
    constraint_date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    return_year: int | None = Form(None),
    return_month: int | None = Form(None),
) -> HTMLResponse:
    """Удаляет ограничение по учёбе."""
    err = _check_login(request)
    if err:
        return err
    write_err = _check_write_access(request, employee_name)
    if write_err:
        return write_err
    window_err = _check_submission_window(request, employee_name)
    if window_err:
        return window_err
    year, month = resolve_period(return_year, return_month)

    try:
        constraint_date_parsed = parse_date(constraint_date, "constraint_date")
        delete_study_constraint(
            employee_name=employee_name,
            date_value=constraint_date_parsed,
            start_time=start_time,
            end_time=end_time,
        )
        # Telegram notification: constraint delete
        try:
            from .services.telegram_notifications import notify_constraint_delete
            actor = request.session.get("logged_in_user", "unknown")
            notify_constraint_delete(actor, employee_name, constraint_date, start_time, end_time)
        except Exception:
            pass
    except Exception as error:
        logger.warning("constraints: delete error: %s", error)

    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/constraints?year={year}&month={month}", status_code=303)


# =============================================================================
# SCHEDULE PREFERENCES (Пожелания)
# =============================================================================

@router.post("/constraints/preferences/save", response_class=HTMLResponse)
async def save_schedule_preference(
    request: Request,
    employee_name: str = Form(...),
    preference_date: str = Form(...),
    preference_type: str = Form(...),  # "prefer_off"
    note: str = Form(""),
    return_year: int | None = Form(None),
    return_month: int | None = Form(None),
) -> HTMLResponse:
    """Сохраняет пожелание по графику."""
    err = _check_login(request)
    if err:
        return err
    write_err = _check_write_access(request, employee_name)
    if write_err:
        return write_err
    window_err = _check_submission_window(request, employee_name)
    if window_err:
        return window_err
    year, month = resolve_period(return_year, return_month)

    try:
        if not employee_name.strip():
            raise ParseError("Укажите сотрудника.")

        preference_date_parsed = parse_date(preference_date, "preference_date")

        if preference_type != "prefer_off":
            raise ParseError("Неверный тип пожелания.")

        upsert_schedule_preference(
            employee_name=employee_name.strip(),
            date_value=preference_date_parsed,
            preference_type=preference_type,
            note=note.strip(),
        )
        # Telegram notification: preference add
        try:
            from .services.telegram_notifications import notify_preference_add
            actor = request.session.get("logged_in_user", "unknown")
            notify_preference_add(actor, employee_name.strip(), preference_date, preference_type, note.strip())
        except Exception:
            pass

    except (ParseError, ValueError) as error:
        logger.warning("constraints: preference error: %s", error)
        request.session["flash_error"] = f"Ошибка: {error}"

    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/constraints?year={year}&month={month}", status_code=303)


@router.post("/constraints/preferences/delete", response_class=HTMLResponse)
async def delete_schedule_preference_endpoint(
    request: Request,
    employee_name: str = Form(...),
    preference_date: str = Form(...),
    preference_type: str = Form(...),
    return_year: int | None = Form(None),
    return_month: int | None = Form(None),
) -> HTMLResponse:
    """Удаляет пожелание по графику."""
    err = _check_login(request)
    if err:
        return err
    write_err = _check_write_access(request, employee_name)
    if write_err:
        return write_err
    year, month = resolve_period(return_year, return_month)

    try:
        preference_date_parsed = parse_date(preference_date, "preference_date")
        delete_schedule_preference(
            employee_name=employee_name,
            date_value=preference_date_parsed,
            preference_type=preference_type,
        )
        # Telegram notification: preference delete
        try:
            from .services.telegram_notifications import notify_preference_delete
            actor = request.session.get("logged_in_user", "unknown")
            notify_preference_delete(actor, employee_name, preference_date, preference_type)
        except Exception:
            pass
    except Exception as error:
        logger.warning("constraints: delete error: %s", error)

    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/constraints?year={year}&month={month}", status_code=303)


# =============================================================================
# BULK IMPORT FROM TEXT (Массовый импорт из текста)
# =============================================================================

def parse_schedule_text(schedule_text: str, employee_name: str) -> tuple[list[dict], list[str]]:
    """
    Парсит текст расписания из личного кабинета студента.

    Формат входных данных:
    - Дни недели с датой (понедельник 6 апреля 2026 г.)
    - Пары с временем (08:30 - 10:00)
    - Названия предметов

    Возвращает:
    - Список ограничений (merged slots)
    - Список предупреждений/ошибок

    Правила слияния:
    - Если между парами окно < 3 часов (менее 2 пар подряд) - сливаем
    - Если окно >= 3 часа - разделяем на отдельные интервалы
    """
    warnings: list[str] = []
    constraints: list[dict] = []

    lines = schedule_text.strip().split('\n')

    # Паттерны для парсинга
    # Исправлено: поддерживаем формат "понедельник6 апреля 2026 г." и "понедельник 6 апреля 2026 г."
    # \s* после дня недели означает 0 или больше пробелов, затем \d+ ловит цифры даты
    day_date_pattern = re.compile(
        r'(понедельник|вторник|среда|четверг|пятница|суббота|воскресенье)\s*(\d{1,2})\s+(\w+)\s+(\d{4})\s*г\.?',
        re.IGNORECASE
    )
    # Время может быть в формате "08:30 - 10:00" или "08:30-10:00"
    time_slot_pattern = re.compile(r'(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})')

    current_date: date | None = None
    day_slots: list[tuple[time, time, str]] = []  # (start, end, subject)

    month_map = {
        'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
        'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
        'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
    }

    def process_day_slots():
        """Обрабатывает накопленные слоты за день и сливает их."""
        nonlocal current_date, day_slots

        if not current_date or not day_slots:
            return

        # Сортируем слоты по времени начала
        day_slots.sort(key=lambda x: x[0])

        # Сливаем соседние слоты с окном < 3 часов
        merged: list[tuple[time, time]] = []
        current_start, current_end, _ = day_slots[0]

        for i in range(1, len(day_slots)):
            next_start, next_end, _ = day_slots[i]

            # Вычисляем окно между текущим концом и следующим началом
            current_end_dt = datetime.combine(current_date, current_end)
            next_start_dt = datetime.combine(current_date, next_start)
            gap_minutes = (next_start_dt - current_end_dt).total_seconds() / 60

            # Если окно < 3 часов (180 минут) - сливаем
            if gap_minutes < 180:
                current_end = max(current_end, next_end)
            else:
                # Сохраняем текущий интервал и начинаем новый
                merged.append((current_start, current_end))
                current_start, current_end = next_start, next_end

        # Добавляем последний интервал
        merged.append((current_start, current_end))

        # Создаем ограничения
        for start_time, end_time in merged:
            # Вычисляем длительность в часах
            start_dt = datetime.combine(current_date, start_time)
            end_dt = datetime.combine(current_date, end_time)
            duration_hours = (end_dt - start_dt).total_seconds() / 3600

            # Пропускаем одиночные пары (1.5 часа)
            if duration_hours <= 1.5 and len(merged) == 1:
                warnings.append(f"Пропущено {current_date.strftime('%d.%m.%Y')}: одна пара ({duration_hours:.1f} ч.)")
                continue

            constraints.append({
                'employee_name': employee_name,
                'date': current_date,
                'start_time': start_time.strftime('%H:%M'),
                'end_time': end_time.strftime('%H:%M'),
                'note': 'Учебные занятия (импорт)',
                'is_strict': True,
            })

        day_slots = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Проверяем, является ли строка днем недели с датой
        day_match = day_date_pattern.match(line)
        if day_match:
            # Обрабатываем предыдущий день
            process_day_slots()

            # Извлекаем дату
            day_name = day_match.group(1)
            day_num = int(day_match.group(2))
            month_str = day_match.group(3).lower()
            year = int(day_match.group(4))
            month = month_map.get(month_str)

            if month:
                current_date = date(year, month, day_num)
            continue

        # Проверяем, является ли строка временным слотом
        time_match = time_slot_pattern.match(line)
        if time_match and current_date:
            start_str = time_match.group(1)
            end_str = time_match.group(2)

            try:
                start_time = parse_time(start_str)
                end_time = parse_time(end_str)

                # Извлекаем название предмета (следующая строка после времени)
                subject = ""

                day_slots.append((start_time, end_time, subject))
            except (ParseError, ValueError):
                warnings.append(f"Не распознано время: {line}")

    # Обрабатываем последний день
    process_day_slots()

    return constraints, warnings


@router.post("/constraints/bulk-import", response_class=JSONResponse)
async def bulk_import_study_constraints(
    request: Request,
    schedule_text: str = Form(...),
    employee_name: str = Form(...),
    year: int = Form(...),
    month: int = Form(...),
) -> JSONResponse:
    """
    Массовый импорт учебных занятий из текста расписания.
    """
    err = _check_login(request)
    if err:
        from fastapi.responses import HTMLResponse
        return err
    write_err = _check_write_access(request, employee_name)
    if write_err:
        return HTMLResponse(
            '<html><body>Доступ только для своей учётной записи.</body></html>',
            status_code=403,
        )
    try:
        if not schedule_text.strip():
            return JSONResponse({
                "success": False,
                "error": "Введите текст расписания",
            }, status_code=400)

        if not employee_name.strip():
            return JSONResponse({
                "success": False,
                "error": "Укажите сотрудника",
            }, status_code=400)

        # Парсим расписание
        constraints, warnings = parse_schedule_text(schedule_text, employee_name.strip())

        if not constraints:
            # Возвращаем больше информации для отладки
            return JSONResponse({
                "success": False,
                "error": "Не найдено занятий для импорта. Проверьте формат текста.",
                "warnings": warnings,
                "debug_lines": len(schedule_text.split('\n')),
                "debug_first_line": repr(schedule_text.split('\n')[0]) if schedule_text else "",
            }, status_code=400)

        # Фильтруем по месяцу
        constraints = [c for c in constraints if c['date'].year == year and c['date'].month == month]

        # Сохраняем в БД
        saved_count = 0
        for constraint in constraints:
            upsert_study_constraint(
                employee_name=constraint['employee_name'],
                date_value=constraint['date'],
                start_time=constraint['start_time'],
                end_time=constraint['end_time'],
                note=constraint['note'],
                is_strict=constraint['is_strict'],
            )
            saved_count += 1

        return JSONResponse({
            "success": True,
            "imported_count": saved_count,
            "warnings": warnings,
            "message": f"Импортировано {saved_count} занятий за {month} {year} г.",
        })

    except Exception as error:
        return JSONResponse({
            "success": False,
            "error": str(error),
        }, status_code=400)


# =============================================================================
# MONTHLY PREFERENCES (Месячные пожелания)
# =============================================================================

@router.post("/constraints/monthly/save", response_class=HTMLResponse)
async def save_monthly_preference(
    request: Request,
    employee_name: str = Form(...),
    preference_type: str = Form(...),  # "not_before", "not_after"
    time_value: str = Form(...),  # "08:00", "22:00"
    note: str = Form(""),
    return_year: int | None = Form(None),
    return_month: int | None = Form(None),
) -> HTMLResponse:
    """Сохраняет месячное пожелание сотрудника."""
    err = _check_login(request)
    if err:
        return err
    write_err = _check_write_access(request, employee_name)
    if write_err:
        return write_err
    window_err = _check_submission_window(request, employee_name)
    if window_err:
        return window_err
    year, month = resolve_period(return_year, return_month)

    try:
        if not employee_name.strip():
            raise ParseError("Укажите сотрудника.")

        if not preference_type or preference_type not in ("not_before", "not_after", "prefer_off"):
            raise ParseError("Неверный тип пожелания.")

        if not time_value:
            raise ParseError("Укажите время.")

        upsert_monthly_preference(
            employee_name=employee_name.strip(),
            year=year,
            month=month,
            preference_type=preference_type,
            time_value=time_value,
            note=note.strip(),
        )

    except (ParseError, ValueError) as error:
        logger.warning("constraints: preference error: %s", error)
        request.session["flash_error"] = f"Ошибка: {error}"

    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/constraints?year={year}&month={month}", status_code=303)


@router.post("/constraints/monthly/delete", response_class=HTMLResponse)
async def delete_monthly_preference_endpoint(
    request: Request,
    employee_name: str = Form(...),
    preference_type: str = Form(...),
    return_year: int | None = Form(None),
    return_month: int | None = Form(None),
) -> HTMLResponse:
    """Удаляет месячное пожелание сотрудника."""
    err = _check_login(request)
    if err:
        return err
    write_err = _check_write_access(request, employee_name)
    if write_err:
        return write_err
    year, month = resolve_period(return_year, return_month)

    try:
        delete_monthly_preference(
            employee_name=employee_name,
            year=year,
            month=month,
            preference_type=preference_type,
        )
    except Exception as error:
        logger.warning("constraints: monthly delete error: %s", error)

    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/constraints?year={year}&month={month}", status_code=303)


