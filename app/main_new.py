"""Новый главный файл с обновлённым дизайном."""
import logging
from fastapi import FastAPI, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path
from datetime import date, timedelta
import calendar
import json
import os
import secrets

logger = logging.getLogger(__name__)

from .database import (
    init_db,
    list_operator_profiles,
    list_vacation_entries,
    list_holiday_entries,
    list_study_constraints,
    list_schedule_preferences,
    list_monthly_preferences,
    list_schedule_assignments,
    list_vacations_for_employee_in_month,
    upsert_study_constraint,
    delete_study_constraint,
    upsert_schedule_preference,
    delete_schedule_preference,
    upsert_monthly_preference,
    delete_monthly_preference,
    list_calendar_day_overrides,
    list_all_credentials,
    update_user_role,
    update_user_password,
    create_user_with_password,
    get_user_with_password,
    list_all_users_with_passwords,
    delete_user_credentials,
    generate_password,
    upsert_holiday_entry,
    delete_holiday_entry,
    HolidayEntry,
    upsert_operator_profile,
    OperatorProfile,
    get_vacation_days_in_month,
    get_employee_month_adjustments_batch,
)
from .models import working_days_in_month
from .form_state import resolve_period
from .auth import (
    get_current_user,
    init_auth,
    process_login,
    process_logout,
    change_user_password,
)


# ---------------------------------------------------------------------------
# Rate limiter for login endpoint
# ---------------------------------------------------------------------------
class LoginRateLimiter:
    """Простой in-memory ограничитель попыток входа."""
    def __init__(self):
        self.attempts: dict[str, list[float]] = {}
        self.max_attempts = 10
        self.window_seconds = 60

    def is_allowed(self, identifier: str) -> bool:
        import time
        now = time.time()
        if identifier not in self.attempts:
            self.attempts[identifier] = []
        self.attempts[identifier] = [
            t for t in self.attempts[identifier]
            if now - t < self.window_seconds
        ]
        if len(self.attempts[identifier]) >= self.max_attempts:
            return False
        self.attempts[identifier].append(now)
        return True


login_rate_limiter = LoginRateLimiter()


BASE_DIR = Path(__file__).parent.parent
app = FastAPI(title="ЕКЦ График")
_session_secret = os.environ.get("EKC_SESSION_SECRET") or secrets.token_hex(32)
app.add_middleware(SessionMiddleware, secret_key=_session_secret)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Подключаем роутер ограничений
from .constraints_api import router as constraints_router
app.include_router(constraints_router)

# Подключаем JSON API роутер для Gantt-редактора v2
from .api.schedule_editor_api import router as editor_api_router
app.include_router(editor_api_router)

# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Добавляет заголовки безопасности ко всем ответам."""
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' cdn.tailwindcss.com; "
        "style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
        "font-src fonts.gstatic.com; "
        "connect-src 'self';"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.autoescape = True  # Enable XSS protection for all templates

init_db()
init_auth()


def merge_adjacent_shifts(shifts: list[dict]) -> list[dict]:
    """
    Объединяет смежные смены в одну.
    Например: 09:00-15:00 + 15:00-21:00 = 09:00-21:00
    """
    if not shifts:
        return []

    # Сортируем по времени начала
    sorted_shifts = sorted(shifts, key=lambda s: s['start_time'])

    merged = []
    current_start = sorted_shifts[0]['start_time']
    current_end = sorted_shifts[0]['end_time']
    current_note = sorted_shifts[0].get('note', '')

    for i in range(1, len(sorted_shifts)):
        shift = sorted_shifts[i]
        # Если следующая смена начинается когда заканчивается текущая - объединяем
        if shift['start_time'] == current_end:
            current_end = shift['end_time']
        else:
            # Сохраняем текущую объединённую смену
            merged.append({
                'start_time': current_start,
                'end_time': current_end,
                'note': current_note,
            })
            current_start = shift['start_time']
            current_end = shift['end_time']
            current_note = shift.get('note', '')

    # Добавляем последнюю смену
    merged.append({
        'start_time': current_start,
        'end_time': current_end,
        'note': current_note,
    })

    return merged


def get_period_from_session_or_default(request: Request, year: int = None, month: int = None):
    """Получает год и месяц из session, cookies или формы."""
    # 1. Проверяем явные параметры
    if year is not None and month is not None:
        # Сохраняем в session
        request.session['selected_year'] = year
        request.session['selected_month'] = month
        return year, month
    
    # 2. Проверяем session
    if request.session.get('selected_year') and request.session.get('selected_month'):
        return request.session['selected_year'], request.session['selected_month']
    
    # 3. Проверяем cookies
    year_cookie = request.cookies.get('ekc_year')
    month_cookie = request.cookies.get('ekc_month')
    if year_cookie and month_cookie:
        try:
            year = int(year_cookie)
            month = int(month_cookie)
            request.session['selected_year'] = year
            request.session['selected_month'] = month
            return year, month
        except ValueError:
            pass
    
    # 4. Возвращаем текущий месяц
    today = date.today()
    return today.year, today.month


def create_period_response(content, status_code=200):
    """Создаёт response с cookies для сохранения периода."""
    response = Response(content=content, status_code=status_code, media_type="text/html")
    # Устанавливаем cookies на 1 год
    response.set_cookie('ekc_year', str(date.today().year), max_age=365*24*60*60, httponly=False)
    response.set_cookie('ekc_month', str(date.today().month), max_age=365*24*60*60, httponly=False)
    return response


@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    year: int = None,
    month: int = None,
) -> HTMLResponse:
    """Главная страница - дашборд (только для админов)."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    # Сотрудники перенаправляются на свою страницу
    if request.session.get("user_role") != "admin":
        return RedirectResponse("/my-schedule", status_code=303)

    year, month = get_period_from_session_or_default(request, year, month)

    from .database import list_schedule_assignments, list_holiday_entries

    operator_profiles = list_operator_profiles()

    # Загружаем реальные данные из БД
    shifts = list_schedule_assignments(year, month)
    shifts_count = len(shifts)

    # Считаем рабочие дни с учетом выходных и календарных overrides
    holidays = list_holiday_entries()
    holiday_dates = {h.holiday_date for h in holidays if h.holiday_date.year == year and h.holiday_date.month == month}
    cal_ovrs = list_calendar_day_overrides()
    overrides_map = {}
    for o in cal_ovrs:
        if o.calendar_date.year == year and o.calendar_date.month == month:
            overrides_map[o.calendar_date] = o.is_non_working

    total_days = calendar.monthrange(year, month)[1]
    monthly_working_days = 0
    for day in range(1, total_days + 1):
        d = date(year, month, day)
        if d in overrides_map:
            if overrides_map[d]:
                continue
            else:
                monthly_working_days += 1
        elif d.weekday() >= 5 or d in holiday_dates:
            continue
        else:
            monthly_working_days += 1

    # Считаем предупреждения (конфликты смен)
    warnings_count = 0
    employee_shifts: dict[str, list] = {}
    for shift in shifts:
        key = f"{shift['employee_name']}_{shift['date']}"
        if key not in employee_shifts:
            employee_shifts[key] = []
        employee_shifts[key].append(shift)

    for key, day_shifts in employee_shifts.items():
        if len(day_shifts) > 1:
            # Проверяем наложение времени
            for i, s1 in enumerate(day_shifts):
                for s2 in day_shifts[i+1:]:
                    if not (s1['end_time'] <= s2['start_time'] or s2['end_time'] <= s1['start_time']):
                        warnings_count += 1

    today_shifts = []
    today = date.today()
    for s in shifts:
        s_day, s_month_val, s_year = s['date'].day, s['date'].month, s['date'].year
        if s_day == today.day and s_month_val == today.month and s_year == today.year:
            today_shifts.append({
                'employee_name': s['employee_name'],
                'start_time': s['start_time'],
                'end_time': s['end_time'],
            })

    context = {
        "request": request,
        "year": year,
        "month": month,
        "month_label": f"{'Январь Февраль Март Апрель Май Июнь Июль Август Сентябрь Октябрь Ноябрь Декабрь'.split()[month-1]} {year}",
        "employees": operator_profiles,
        "monthly_working_days": monthly_working_days,
        "shifts_count": shifts_count,
        "warnings_count": warnings_count,
        "todays_date": today,
        "today_shifts": sorted(today_shifts, key=lambda s: s['start_time']),
        "result": None,
        "errors": [],
        "notices": [],
        "active_page": "home",
        "operator_norms_by_name": {},
    }

    response = templates.TemplateResponse("home_new.html", context)
    response.set_cookie('ekc_year', str(year), max_age=365*24*60*60)
    response.set_cookie('ekc_month', str(month), max_age=365*24*60*60)
    return response


@app.get("/employees", response_class=HTMLResponse)
async def employees_page(
    request: Request,
    year: int = None,
    month: int = None,
) -> HTMLResponse:
    """Страница сотрудников (только для админов)."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    # Сотрудники не имеют доступа
    if request.session.get("user_role") != "admin":
        return RedirectResponse("/my-schedule", status_code=303)

    year, month = get_period_from_session_or_default(request, year, month)

    operator_profiles = list_operator_profiles()

    # Рассчитываем рабочие дни с учётом выходных и календарных overrides
    holidays = list_holiday_entries()
    holiday_dates = {h.holiday_date for h in holidays if h.holiday_date.year == year and h.holiday_date.month == month}
    cal_ovrs = list_calendar_day_overrides()
    overrides_map = {}
    for o in cal_ovrs:
        if o.calendar_date.year == year and o.calendar_date.month == month:
            overrides_map[o.calendar_date] = o.is_non_working

    total_days = calendar.monthrange(year, month)[1]
    monthly_working_days = 0
    for day in range(1, total_days + 1):
        d = date(year, month, day)
        if d in overrides_map:
            if overrides_map[d]:
                continue  # явно помечен как выходной
            else:
                monthly_working_days += 1  # явно помечен как рабочий
        elif d.weekday() >= 5 or d in holiday_dates:
            continue  # Сб/Вс или праздник
        else:
            monthly_working_days += 1

    # Загружаем отпуска для отображения в карточках и считаем дни
    vacation_entries = list_vacation_entries()
    vacations_by_employee: dict[str, list] = {}
    vacation_days_by_employee: dict[str, int] = {}
    vacation_hours_by_employee: dict[str, float] = {}
    vacation_total_days_by_employee: dict[str, int] = {}
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])

    for entry in vacation_entries:
        # Проверяем пересечение с месяцем
        if entry.end_date < month_start or entry.start_date > month_end:
            continue

        if entry.employee_name not in vacations_by_employee:
            vacations_by_employee[entry.employee_name] = []
            vacation_days_by_employee[entry.employee_name] = 0
            vacation_total_days_by_employee[entry.employee_name] = 0
        vacations_by_employee[entry.employee_name].append(entry)

        # Считаем дни отпуска в пределах месяца
        cursor = max(entry.start_date, month_start)
        end_cursor = min(entry.end_date, month_end)
        total_days = 0
        while cursor <= end_cursor:
            total_days += 1
            if cursor.weekday() < 5:
                vacation_days_by_employee[entry.employee_name] += 1
            cursor += timedelta(days=1)
        vacation_total_days_by_employee[entry.employee_name] += total_days

    # Считаем часы отпуска для каждого сотрудника
    for emp in operator_profiles:
        vac_days = vacation_days_by_employee.get(emp.name, 0)
        vacation_hours_by_employee[emp.name] = round(emp.rate * 8 * vac_days, 1)

    # Загружаем месячные корректировки из БД и считаем итоговые часы с учётом отпуска
    adjustments_batch = get_employee_month_adjustments_batch(year, month)
    # operator_adjustments хранит ИТОГОВУЮ норму: база - отпуск + ручная корректировка
    operator_adjustments = {}
    operator_base_norms = {}
    operator_manual_adjustments = {}
    for emp in operator_profiles:
        # Базовая норма = ставка × 8 часов × рабочие дни
        base_norm = emp.rate * 8 * monthly_working_days
        operator_base_norms[emp.name] = round(base_norm, 1)
        # Ручная корректировка из БД для текущего месяца
        manual_adjustment = adjustments_batch.get(emp.name, 0.0)
        operator_manual_adjustments[emp.name] = round(manual_adjustment, 1)
        # Часы отпуска для этого сотрудника
        vac_hours = vacation_hours_by_employee.get(emp.name, 0)
        # Итоговая норма с учётом отпуска
        operator_adjustments[emp.name] = round(base_norm - vac_hours + manual_adjustment, 1)
    
    context = {
        "request": request,
        "year": year,
        "month": month,
        "month_label": f"{'Январь Февраль Март Апрель Май Июнь Июль Август Сентябрь Октябрь Ноябрь Декабрь'.split()[month-1]} {year}",
        "operator_profiles": operator_profiles,
        "operator_form_values": {},
        "operator_adjustments": operator_adjustments,
        "operator_base_norms": operator_base_norms,
        "operator_manual_adjustments": operator_manual_adjustments,
        "monthly_working_days": monthly_working_days,
        "vacations_by_employee": vacations_by_employee,
        "vacation_days_by_employee": vacation_days_by_employee,
        "vacation_hours_by_employee": vacation_hours_by_employee,
        "vacation_total_days_by_employee": vacation_total_days_by_employee,
        "active_page": "employees",
        "errors": [],
        "notices": [],
    }
    
    response = templates.TemplateResponse("employees_new.html", context)
    response.set_cookie('ekc_year', str(year), max_age=365*24*60*60)
    response.set_cookie('ekc_month', str(month), max_age=365*24*60*60)
    return response


@app.get("/schedule", response_class=HTMLResponse)
async def schedule_page(
    request: Request,
    year: int = None,
    month: int = None,
) -> HTMLResponse:
    """Страница просмотра графика."""
    from datetime import timedelta
    from collections import OrderedDict

    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    user_role = request.session.get("user_role")
    current_user = get_current_user(request)
    year, month = get_period_from_session_or_default(request, year, month)
    month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
    genitive_names = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
    weekday_names = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье']
    day_num_days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

    # Для сотрудников - показываем только их смены
    if user_role != "admin":
        from .database import list_schedule_assignments, list_operator_profiles, list_holiday_entries

        # Находим профиль сотрудника
        operators = list_operator_profiles()
        employee = next((e for e in operators if e.name == current_user), None)

        # Загружаем выходные из БД для расчёта нормы часов
        holidays = list_holiday_entries()
        holiday_dates = {h.holiday_date for h in holidays if h.holiday_date.year == year and h.holiday_date.month == month}
        # Считаем дни отпуска
        vacation_days = get_vacation_days_in_month(current_user, year, month) if employee else 0
        # Базовая норма = ставка × 8 часов × (рабочие дни - отпуск)
        base_norm = employee.rate * 8 * (working_days_in_month(year, month, holiday_dates) - vacation_days) if employee else 160
        # Добавляем корректировку из БД для текущего месяца
        adjustments_batch = get_employee_month_adjustments_batch(year, month)
        month_adjustment = adjustments_batch.get(current_user, 0.0) if employee else 0
        norm_hours = base_norm + month_adjustment

        # Получаем все смены за месяц
        all_assignments = list_schedule_assignments(year, month)

        # Фильтруем только смены текущего сотрудника
        shifts = []
        total_hours = 0
        for a in all_assignments:
            if a['employee_name'] == current_user:
                shift_date = a['date']
                is_weekend = shift_date.weekday() >= 5

                # Считаем часы смены
                start_parts = a['start_time'].split(':')
                end_parts = a['end_time'].split(':')
                start_minutes = int(start_parts[0]) * 60 + int(start_parts[1])
                end_minutes = int(end_parts[0]) * 60 + int(end_parts[1])
                if end_minutes < start_minutes:
                    end_minutes += 24 * 60  # Переход через полночь
                shift_hours = (end_minutes - start_minutes) / 60

                shifts.append({
                    'date': shift_date.strftime('%d.%m.%Y'),
                    'is_weekend': is_weekend,
                    'start_time': a['start_time'],
                    'end_time': a['end_time'],
                    'shift_type': a['shift_type'],
                    'hours': shift_hours,
                })
                total_hours += shift_hours

        remaining_hours = norm_hours - total_hours

        context = {
            "request": request,
            "year": year,
            "month": month,
            "month_label": f"{month_names[month-1]} {year}",
            "active_page": "schedule",
            "shifts": shifts,
            "shifts_count": len(shifts),
            "total_hours": round(total_hours, 1),
            "norm_hours": round(norm_hours, 1),
            "remaining_hours": round(remaining_hours, 1),
            "errors": [],
            "notices": [],
        }
    else:
        from .database import list_schedule_assignments, list_operator_profiles

        all_assignments = list_schedule_assignments(year, month)
        operators = list_operator_profiles(active_only=True)

        # Color palette for employees (consistent coloring)
        employee_colors = {}
        color_palette = [
            '--blue-600', '--green-600', '--orange-500', '--purple-600',
            '--pink-500', '--blue-800', '--green-700', '--red-500',
        ]
        for idx, op in enumerate(operators):
            employee_colors[op.name] = color_palette[idx % len(color_palette)]

        # Group by date
        schedule_by_date = {}  # date -> list of assignments
        for a in all_assignments:
            date_key = a['date']
            if date_key not in schedule_by_date:
                schedule_by_date[date_key] = []
            schedule_by_date[date_key].append(a)

        # Sort assignments per date by start_time
        for date_key in schedule_by_date:
            schedule_by_date[date_key].sort(key=lambda x: x['start_time'])

        # Build ordered list of day info (all days in month)
        days_in_month = calendar.monthrange(year, month)[1]
        all_days = []
        total_shifts_count = 0
        total_coverage_hours = 0.0

        for day in range(1, days_in_month + 1):
            d = date(year, month, day)
            is_weekend = d.weekday() >= 5
            shifts_for_day = schedule_by_date.get(d, [])
            total_shifts_count += len(shifts_for_day)

            # Compute coverage hours
            day_coverage = 0.0
            if shifts_for_day:
                for s in shifts_for_day:
                    start_parts = s['start_time'].split(':')
                    end_parts = s['end_time'].split(':')
                    start_minutes = int(start_parts[0]) * 60 + int(start_parts[1])
                    end_minutes = int(end_parts[0]) * 60 + int(end_parts[1])
                    if end_minutes < start_minutes:
                        end_minutes += 24 * 60
                    day_coverage += (end_minutes - start_minutes) / 60
                total_coverage_hours += day_coverage

            # Enriched assignments
            enriched = []
            for s in shifts_for_day:
                start_parts = s['start_time'].split(':')
                end_parts = s['end_time'].split(':')
                start_minutes = int(start_parts[0]) * 60 + int(start_parts[1])
                end_minutes = int(end_parts[0]) * 60 + int(end_parts[1])
                if end_minutes < start_minutes:
                    end_minutes += 24 * 60
                shift_hours = (end_minutes - start_minutes) / 60

                # Compute relative positions for timeline bar (0-1)
                day_start = min(int(s2['start_time'].split(':')[0]) * 60 + int(s2['start_time'].split(':')[1])
                               for s2 in shifts_for_day)
                day_end = max(int(s2['end_time'].split(':')[0]) * 60 + int(s2['end_time'].split(':')[1])
                             for s2 in shifts_for_day)
                span = day_end - day_start or 1

                bar_left = (start_minutes - day_start) / span * 100
                bar_width = (end_minutes - start_minutes) / span * 100

                enriched.append({
                    'employee_name': s['employee_name'],
                    'start_time': s['start_time'],
                    'end_time': s['end_time'],
                    'shift_type': s['shift_type'],
                    'hours': round(shift_hours, 1),
                    'color': employee_colors.get(s['employee_name'], '--gray-600'),
                    'bar_left': bar_left,
                    'bar_width': bar_width,
                })

            # Day coverage range
            coverage_label = ''
            if shifts_for_day:
                earliest = min(int(s['start_time'].split(':')[0]) * 60 + int(s['start_time'].split(':')[1]) for s in shifts_for_day)
                latest = max(int(s['end_time'].split(':')[0]) * 60 + int(s['end_time'].split(':')[1]) for s in shifts_for_day)
                e_h = earliest // 60
                e_m = earliest % 60
                l_h = latest // 60
                l_m = latest % 60
                coverage_hours_total = (latest - earliest) / 60
                coverage_label = f"{e_h:02d}:{e_m:02d} — {l_h:02d}:{l_m:02d} ({coverage_hours_total:.0f}ч)"

            all_days.append({
                'date': d,
                'day_num': day,
                'weekday_name': weekday_names[d.weekday()],
                'day_short': day_num_days[d.weekday()],
                'is_weekend': is_weekend,
                'shifts': enriched,
                'coverage_label': coverage_label,
                'coverage_hours': round(day_coverage, 1),
            })

        context = {
            "request": request,
            "year": year,
            "month": month,
            "month_label": f"{month_names[month-1]} {year}",
            "active_page": "schedule",
            "all_days": all_days,
            "working_days_count": sum(1 for d in all_days if not d['is_weekend'] and d['shifts']),
            "total_shifts_count": total_shifts_count,
            "total_coverage_hours": round(total_coverage_hours, 1),
            "errors": [],
            "notices": [],
        }

    response = templates.TemplateResponse("schedule_new.html", context)
    response.set_cookie('ekc_year', str(year), max_age=365*24*60*60)
    response.set_cookie('ekc_month', str(month), max_age=365*24*60*60)
    return response


@app.get("/schedule/editor", response_class=HTMLResponse)
async def schedule_editor_page(
    request: Request,
    year: int = None,
    month: int = None,
    view: str = None,
) -> HTMLResponse:
    """Gantt-редактор графика v2 (только для админов)."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)
    if request.session.get("user_role") != "admin":
        return RedirectResponse("/my-schedule", status_code=303)

    year, month = get_period_from_session_or_default(request, year, month)

    from .database import list_operator_profiles, list_holiday_entries, list_monthly_preferences

    operators = list_operator_profiles(active_only=True)
    holidays = list_holiday_entries()
    monthly_preferences = list_monthly_preferences(year, month)

    monthly_preferences_data = [
        {
            "id": pref["id"],
            "employee_name": pref["employee_name"],
            "year": pref["year"],
            "month": pref["month"],
            "preference_type": pref["preference_type"],
            "time_value": pref["time_value"],
            "note": pref["note"],
        }
        for pref in monthly_preferences
    ]

    employees_data = [
        {
            "name": emp.name,
            "employee_id": emp.employee_id,
            "employee_type": emp.employee_type,
            "rate": emp.rate,
        }
        for emp in operators
    ]

    holidays_data = [
        {"date": h.holiday_date.isoformat(), "name": h.name}
        for h in holidays
    ]

    month_names = 'Январь Февраль Март Апрель Май Июнь Июль Август Сентябрь Октябрь Ноябрь Декабрь'.split()

    context = {
        "request": request,
        "year": year,
        "month": month,
        "month_label": f"{month_names[month-1]} {year}",
        "employees_json": json.dumps(employees_data, ensure_ascii=False),
        "holidays_json": json.dumps(holidays_data, ensure_ascii=False),
        "monthly_preferences_json": json.dumps(monthly_preferences_data, ensure_ascii=False),
        "monthly_preferences_data": monthly_preferences_data,
        "active_page": "schedule-editor",
        "errors": [],
        "notices": [],
    }

    response = templates.TemplateResponse("schedule_gantt_v2.html", context)
    response.set_cookie('ekc_year', str(year), max_age=365*24*60*60)
    response.set_cookie('ekc_month', str(month), max_age=365*24*60*60)
    return response




@app.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    year: int = None,
    month: int = None,
) -> HTMLResponse:
    """Страница настроек (только для админов)."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    # Сотрудники не имеют доступа
    if request.session.get("user_role") != "admin":
        return RedirectResponse("/my-schedule", status_code=303)

    year, month = get_period_from_session_or_default(request, year, month)

    from .database import get_app_settings

    # Загружаем настройки из БД
    settings = get_app_settings(['autosave_enabled'])

    context = {
        "request": request,
        "year": year,
        "month": month,
        "month_label": f"{'Январь Февраль Март Апрель Май Июнь Июль Август Сентябрь Октябрь Ноябрь Декабрь'.split()[month-1]} {year}",
        "active_page": "settings",
        "autosave_enabled": settings.get('autosave_enabled', 'true').lower() == 'true',
        "errors": [],
        "notices": [],
    }

    response = templates.TemplateResponse("settings_new.html", context)
    response.set_cookie('ekc_year', str(year), max_age=365*24*60*60)
    response.set_cookie('ekc_month', str(month), max_age=365*24*60*60)
    return response


@app.post("/settings", response_class=HTMLResponse)
async def settings_save_page(
    request: Request,
    autosave_enabled: str = Form("off"),
) -> HTMLResponse:
    """Сохраняет настройки в БД."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    if request.session.get("user_role") != "admin":
        return RedirectResponse("/my-schedule", status_code=303)

    from .database import set_app_settings

    settings = {}
    settings['autosave_enabled'] = 'true' if autosave_enabled == 'on' else 'false'

    set_app_settings(settings)

    return RedirectResponse("/settings", status_code=303)


@app.get("/settings/download-db")
async def settings_download_db(request: Request):
    """Скачивает архив с базой данных и всеми вспомогательными файлами (только для админов)."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)
    if request.session.get("user_role") != "admin":
        return RedirectResponse("/my-schedule", status_code=303)

    from .database import get_db_path
    import zipfile
    import io
    import time

    db_path = get_db_path()
    data_dir = db_path.parent

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Основной файл БД
        if db_path.exists():
            zf.write(db_path, db_path.name)
        # WAL и SHM файлы (могут отсутствовать)
        for ext in ("-shm", "-wal"):
            sibling = db_path.with_name(db_path.stem + ".db" + ext)
            if sibling.exists():
                zf.write(sibling, sibling.name)
        # Любые другие файлы в data/
        for f in data_dir.iterdir():
            if f.name not in (db_path.name, db_path.stem + ".db-shm", db_path.stem + ".db-wal"):
                zf.write(f, f.name)

    zip_buffer.seek(0)

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"ekc_backup_{timestamp}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


# =============================================================================
# MY SCHEDULE - Личная страница сотрудника
# =============================================================================

@app.get("/my-schedule", response_class=HTMLResponse)
async def my_schedule_page(
    request: Request,
    employee_name: str = "",
    year: int = None,
    month: int = None,
) -> HTMLResponse:
    """Личная страница сотрудника для управления пожеланиями."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    current_user = get_current_user(request)
    user_role = request.session.get("user_role")

    year, month = get_period_from_session_or_default(request, year, month)

    # Сотрудники могут видеть только свои данные
    if user_role != "admin":
        employee_name = current_user

    # Если сотрудник не выбран, показываем список всех (только для админов)
    if not employee_name:
        # Сотрудники перенаправляются на свою страницу
        if user_role != "admin":
            return RedirectResponse(f"/my-schedule?employee_name={current_user}", status_code=303)

        operators = list_operator_profiles()

        # Рассчитываем рабочие дни с учётом выходных и календарных overrides
        holidays = list_holiday_entries()
        holiday_dates = {h.holiday_date for h in holidays if h.holiday_date.year == year and h.holiday_date.month == month}
        cal_ovrs = list_calendar_day_overrides()
        overrides_map = {}
        for o in cal_ovrs:
            if o.calendar_date.year == year and o.calendar_date.month == month:
                overrides_map[o.calendar_date] = o.is_non_working

        total_days = calendar.monthrange(year, month)[1]
        monthly_working_days = 0
        for day in range(1, total_days + 1):
            d = date(year, month, day)
            if d in overrides_map:
                if overrides_map[d]:
                    continue  # явно помечен как выходной
                else:
                    monthly_working_days += 1  # явно помечен как рабочий
            elif d.weekday() >= 5 or d in holiday_dates:
                continue  # Сб/Вс или праздник
            else:
                monthly_working_days += 1

        context = {
            "request": request,
            "year": year,
            "month": month,
            "month_label": f"{'Январь Февраль Март Апрель Май Июнь Июль Август Сентябрь Октябрь Ноябрь Декабрь'.split()[month-1]} {year}",
            "operators": operators,
            "monthly_working_days": monthly_working_days,
            "active_page": "my-schedule",
            "errors": [],
            "notices": [],
        }
        response = templates.TemplateResponse("select_employee.html", context)
        response.set_cookie('ekc_year', str(year), max_age=365*24*60*60)
        response.set_cookie('ekc_month', str(month), max_age=365*24*60*60)
        return response

    # Для сотрудников принудительно устанавливаем их имя
    if user_role != "admin" and employee_name != current_user:
        return RedirectResponse(f"/my-schedule?employee_name={current_user}", status_code=303)

    # Загружаем данные сотрудника
    unavailable = list_study_constraints(year, month, employee_name)
    preferences = list_schedule_preferences(year, month, employee_name)
    monthly_prefs = list_monthly_preferences(year, month, employee_name)
    shifts = list_schedule_assignments(year, month, employee_name)
    vacations = list_vacations_for_employee_in_month(employee_name, year, month)

    # Считаем фактически отработанные часы
    from datetime import datetime
    worked_hours = 0
    for shift in shifts:
        start = datetime.strptime(shift['start_time'], '%H:%M')
        end = datetime.strptime(shift['end_time'], '%H:%M')
        worked_hours += (end - start).total_seconds() / 3600

    # Находим профиль сотрудника
    employee = next((e for e in list_operator_profiles() if e.name == employee_name), None)

    # Рассчитываем норму часов с учётом выходных, overrides и отпусков
    holidays = list_holiday_entries()
    holiday_dates = {h.holiday_date for h in holidays if h.holiday_date.year == year and h.holiday_date.month == month}
    cal_ovrs = list_calendar_day_overrides()
    overrides_map = {}
    for o in cal_ovrs:
        if o.calendar_date.year == year and o.calendar_date.month == month:
            overrides_map[o.calendar_date] = o.is_non_working

    total_days = calendar.monthrange(year, month)[1]
    monthly_working_days = 0
    for day in range(1, total_days + 1):
        d = date(year, month, day)
        if d in overrides_map:
            if overrides_map[d]:
                continue  # явно помечен как выходной
            else:
                monthly_working_days += 1  # явно помечен как рабочий
        elif d.weekday() >= 5 or d in holiday_dates:
            continue  # Сб/Вс или праздник
        else:
            monthly_working_days += 1

    # Считаем дни отпуска
    vacation_days = get_vacation_days_in_month(employee_name, year, month) if employee else 0
    # Базовая норма = ставка × 8 часов × (рабочие дни - отпуск)
    base_norm = employee.rate * 8 * (monthly_working_days - vacation_days) if employee else 160
    # Добавляем корректировку из БД для текущего месяца
    adjustments_batch = get_employee_month_adjustments_batch(year, month)
    month_adjustment = adjustments_batch.get(employee_name, 0.0) if employee else 0
    norm_hours = base_norm + month_adjustment

    # Генерируем календарь на месяц с данными
    month_days = calendar.monthrange(year, month)[1]
    calendar_days = []
    for day in range(1, month_days + 1):
        current_date = date(year, month, day)
        weekday = current_date.weekday()
        # Выходной = суббота/воскресенье ИЛИ праздник из БД ИЛИ ручной override (is_non_working=True)
        is_nw_override = overrides_map.get(current_date, False)
        is_weekend = weekday >= 5 or current_date in holiday_dates or is_nw_override
        day_data = {
            'date': current_date.isoformat(),  # Строка для JSON сериализации
            'day': day,
            'weekday': weekday,
            'is_weekend': is_weekend,
            'unavailable': [
                {**u, 'date': u['date'].isoformat() if isinstance(u['date'], date) else u['date']}
                for u in unavailable if u['date'] == current_date
            ],
            'preferences': [
                {**p, 'date': p['date'].isoformat() if isinstance(p['date'], date) else p['date']}
                for p in preferences if p['date'] == current_date
            ],
            'monthly_preferences': monthly_prefs,  # Месячные пожелания для отображения в ячейке
            # Объединяем смежные смены (например, 09:00-15:00 + 15:00-21:00 = 09:00-21:00)
            'shifts': merge_adjacent_shifts([
                {**s, 'date': s['date'].isoformat() if isinstance(s['date'], date) else s['date']}
                for s in shifts if s['date'] == current_date
            ]),
            'vacations': [
                {
                    'date': v['date'].isoformat() if isinstance(v['date'], date) else v['date'],
                    'start_date': v['start_date'].isoformat() if isinstance(v['start_date'], date) else v['start_date'],
                    'end_date': v['end_date'].isoformat() if isinstance(v['end_date'], date) else v['end_date'],
                    'note': v.get('note', ''),
                }
                for v in vacations if v['date'] == current_date
            ],
        }
        calendar_days.append(day_data)

    context = {
        "request": request,
        "year": year,
        "month": month,
        "month_label": f"{'Январь Февраль Март Апрель Май Июнь Июль Август Сентябрь Октябрь Ноябрь Декабрь'.split()[month-1]} {year}",
        "employee_name": employee_name,
        "employee_type": employee.employee_type if employee else "operator",
        "rate": employee.rate if employee else 1.0,
        "norm_hours": round(norm_hours, 1),
        "worked_hours": round(worked_hours, 1),
        "calendar_days": calendar_days,
        "monthly_working_days": monthly_working_days,
        "vacation_days": vacation_days,
        "preferences": preferences,
        "monthly_preferences": monthly_prefs,
        "active_page": "my-schedule",
        "errors": [],
        "notices": [],
    }
    
    response = templates.TemplateResponse("my_schedule.html", context)
    response.set_cookie('ekc_year', str(year), max_age=365*24*60*60)
    response.set_cookie('ekc_month', str(month), max_age=365*24*60*60)
    return response


@app.post("/my-schedule/unavailable/add", response_class=HTMLResponse)
async def add_unavailable(
    request: Request,
    employee_name: str = Form(...),
    date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    note: str = Form(""),
    return_month: int = None,
    return_year: int = None,
):
    """Добавляет время, когда сотрудник не может работать."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    from .parsers import parse_date

    year, month = resolve_period(return_year, return_month)

    # Сотрудники могут добавлять ограничения только себе
    current_user = get_current_user(request)
    if request.session.get("user_role") != "admin" and employee_name != current_user:
        return RedirectResponse(f"/my-schedule?employee_name={current_user}", status_code=303)
    
    try:
        parsed_date = parse_date(date, "date")
        upsert_study_constraint(
            employee_name=employee_name,
            date_value=parsed_date,
            start_time=start_time,
            end_time=end_time,
            note=note,
            is_strict=True,
        )
    except Exception as e:
        logger.error("Failed to add study constraint: %s", e, exc_info=True)
        request.session["flash_error"] = "Не удалось добавить ограничение. Попробуйте ещё раз."

    return RedirectResponse(f"/my-schedule?employee_name={employee_name}&year={year}&month={month}", status_code=303)


@app.post("/my-schedule/unavailable/delete", response_class=HTMLResponse)
async def delete_unavailable(
    request: Request,
    employee_name: str = Form(...),
    date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    return_month: int = None,
    return_year: int = None,
):
    """Удаляет время недоступности."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    from .parsers import parse_date

    year, month = resolve_period(return_year, return_month)

    # Сотрудники могут удалять ограничения только свои
    current_user = get_current_user(request)
    if request.session.get("user_role") != "admin" and employee_name != current_user:
        return RedirectResponse(f"/my-schedule?employee_name={current_user}", status_code=303)
    
    try:
        parsed_date = parse_date(date, "date")
        delete_study_constraint(employee_name, parsed_date, start_time, end_time)
    except Exception as e:
        logger.error("Failed to delete study constraint: %s", e, exc_info=True)
        request.session["flash_error"] = "Не удалось удалить ограничение. Попробуйте ещё раз."

    return RedirectResponse(f"/my-schedule?employee_name={employee_name}&year={year}&month={month}", status_code=303)


@app.post("/my-schedule/preferences/add", response_class=HTMLResponse)
async def add_preference(
    request: Request,
    employee_name: str = Form(...),
    date: str = Form(...),
    preference_type: str = Form(...),
    note: str = Form(""),
    start_time: str = Form(""),
    end_time: str = Form(""),
    other_text: str = Form(""),  # Текст для типа "other"
    return_month: int = None,
    return_year: int = None,
):
    """Добавляет пожелание сотрудника."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    from .parsers import parse_date

    current_user = get_current_user(request)
    if request.session.get("user_role") != "admin" and employee_name != current_user:
        return RedirectResponse(f"/my-schedule?employee_name={current_user}", status_code=303)

    year, month = resolve_period(return_year, return_month)

    try:
        parsed_date = parse_date(date, "date")
        # Для типа "other" используем other_text как note, время не нужно
        final_note = other_text if preference_type == "other" and other_text else note
        final_start = start_time if preference_type != "other" else None
        final_end = end_time if preference_type != "other" else None

        upsert_schedule_preference(
            employee_name=employee_name,
            date_value=parsed_date,
            preference_type=preference_type,
            note=final_note,
            start_time=final_start if final_start and final_start.strip() else None,
            end_time=final_end if final_end and final_end.strip() else None,
        )
    except Exception as e:
        logger.error("Failed to add preference: %s", e, exc_info=True)
        request.session["flash_error"] = "Не удалось добавить пожелание. Попробуйте ещё раз."

    return RedirectResponse(f"/my-schedule?employee_name={employee_name}&year={year}&month={month}", status_code=303)


@app.post("/my-schedule/study/add-bulk", response_class=HTMLResponse)
async def add_study_bulk(
    request: Request,
    employee_name: str = Form(...),
    note: str = Form(""),
    start_time: str = Form(""),
    end_time: str = Form(""),
    study_selected_dates: str = Form(""),
    return_month: int = None,
    return_year: int = None,
):
    """Добавляет учебное ограничение к нескольким датам сразу."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    from .parsers import parse_date

    current_user = get_current_user(request)
    if request.session.get("user_role") != "admin" and employee_name != current_user:
        return RedirectResponse(f"/my-schedule?employee_name={current_user}", status_code=303)

    year, month = resolve_period(return_year, return_month)

    date_strings = [d.strip() for d in study_selected_dates.split(",") if d.strip()]

    success_count = 0
    error_count = 0

    for date_str in date_strings:
        try:
            parsed_date = parse_date(date_str, "date")
            upsert_study_constraint(
                employee_name=employee_name,
                date_value=parsed_date,
                start_time=start_time,
                end_time=end_time,
                note=note,
                is_strict=True,
            )
            success_count += 1
        except Exception as e:
            logger.error("Failed to add study (bulk): %s", e, exc_info=True)
            error_count += 1

    if error_count > 0:
        request.session["flash_error"] = f"Добавлено {success_count} учебных занятий, ошибок: {error_count}"
    else:
        request.session["flash_success"] = f"Добавлено {success_count} учебных занятий"

    return RedirectResponse(f"/my-schedule?employee_name={employee_name}&year={year}&month={month}", status_code=303)


@app.post("/my-schedule/preferences/add-bulk", response_class=HTMLResponse)
async def add_preference_bulk(
    request: Request,
    employee_name: str = Form(...),
    preference_type: str = Form(...),
    note: str = Form(""),
    start_time: str = Form(""),
    end_time: str = Form(""),
    other_text: str = Form(""),  # Текст для типа "other"
    selected_dates: str = Form(...),  # Comma-separated dates: "2026-04-01,2026-04-05,2026-04-10"
    return_month: int = None,
    return_year: int = None,
):
    """Добавляет пожелание сотрудника к нескольким датам сразу."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    from .parsers import parse_date

    current_user = get_current_user(request)
    if request.session.get("user_role") != "admin" and employee_name != current_user:
        return RedirectResponse(f"/my-schedule?employee_name={current_user}", status_code=303)

    year, month = resolve_period(return_year, return_month)

    # Parse comma-separated dates
    date_strings = [d.strip() for d in selected_dates.split(",") if d.strip()]

    success_count = 0
    error_count = 0

    # Для типа "other" используем other_text как note, время не нужно
    final_note = other_text if preference_type == "other" and other_text else note
    final_start = start_time if preference_type != "other" else None
    final_end = end_time if preference_type != "other" else None

    for date_str in date_strings:
        try:
            parsed_date = parse_date(date_str, "date")
            upsert_schedule_preference(
                employee_name=employee_name,
                date_value=parsed_date,
                preference_type=preference_type,
                note=final_note,
                start_time=final_start if final_start and final_start.strip() else None,
                end_time=final_end if final_end and final_end.strip() else None,
            )
            success_count += 1
        except Exception as e:
            logger.error("Failed to add preference (bulk): %s", e, exc_info=True)
            error_count += 1

    if error_count > 0:
        request.session["flash_error"] = f"Добавлено {success_count} пожеланий, ошибок: {error_count}"
    else:
        request.session["flash_success"] = f"Добавлено {success_count} пожеланий"

    return RedirectResponse(f"/my-schedule?employee_name={employee_name}&year={year}&month={month}", status_code=303)


@app.post("/my-schedule/preferences/delete", response_class=HTMLResponse)
async def delete_preference(
    request: Request,
    employee_name: str = Form(...),
    date: str = Form(...),
    preference_type: str = Form(...),
    return_month: int = None,
    return_year: int = None,
):
    """Удаляет пожелание."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    from .parsers import parse_date

    current_user = get_current_user(request)
    if request.session.get("user_role") != "admin" and employee_name != current_user:
        return RedirectResponse(f"/my-schedule?employee_name={current_user}", status_code=303)

    year, month = get_period_from_session_or_default(request, return_year, return_month)
    
    try:
        parsed_date = parse_date(date, "date")
        delete_schedule_preference(employee_name, parsed_date, preference_type)
    except Exception as e:
        logger.error("Failed to delete preference: %s", e, exc_info=True)
        request.session["flash_error"] = "Не удалось удалить пожелание. Попробуйте ещё раз."

    response = RedirectResponse(f"/my-schedule?employee_name={employee_name}", status_code=303)
    response.set_cookie('ekc_year', str(year), max_age=365*24*60*60)
    response.set_cookie('ekc_month', str(month), max_age=365*24*60*60)
    return response


@app.post("/my-schedule/monthly/add", response_class=HTMLResponse)
async def add_monthly_preference(
    request: Request,
    employee_name: str = Form(...),
    preference_type: str = Form(...),  # "not_before", "not_after", "other"
    time_value: str = Form(None),  # "08:00", "22:00" (не нужно для "other")
    note: str = Form(""),
    other_text: str = Form(""),  # Текст для типа "other"
    return_month: int = None,
    return_year: int = None,
):
    """Добавляет месячное пожелание сотрудника."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    from .parsers import parse_date

    current_user = get_current_user(request)
    if request.session.get("user_role") != "admin" and employee_name != current_user:
        return RedirectResponse(f"/my-schedule?employee_name={current_user}", status_code=303)

    year, month = resolve_period(return_year, return_month)

    try:
        # Для типа "other" используем other_text как note, time_value не нужен
        final_note = other_text if preference_type == "other" and other_text else note
        # time_value может быть пустой строкой из Form(None), конвертируем в None
        final_time = None if preference_type == "other" else (time_value if time_value and time_value.strip() else None)

        upsert_monthly_preference(
            employee_name=employee_name,
            year=year,
            month=month,
            preference_type=preference_type,
            time_value=final_time,
            note=final_note,
        )
    except Exception as e:
        logger.error("Failed to add monthly preference: %s", e, exc_info=True)
        request.session["flash_error"] = "Не удалось добавить пожелание. Попробуйте ещё раз."

    return RedirectResponse(f"/my-schedule?employee_name={employee_name}&year={year}&month={month}", status_code=303)


@app.post("/my-schedule/monthly/edit", response_class=HTMLResponse)
async def edit_monthly_preference(
    request: Request,
    employee_name: str = Form(...),
    old_preference_type: str = Form(...),
    preference_type: str = Form(...),
    time_value: str = Form(None),
    note: str = Form(""),
    return_month: int = None,
    return_year: int = None,
):
    """Редактирует месячное пожелание (удаляет старое и добавляет новое)."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    from .parsers import parse_date

    current_user = get_current_user(request)
    if request.session.get("user_role") != "admin" and employee_name != current_user:
        return RedirectResponse(f"/my-schedule?employee_name={current_user}", status_code=303)

    year, month = resolve_period(return_year, return_month)

    try:
        # Сначала удаляем старое пожелание
        delete_monthly_preference(
            employee_name=employee_name,
            year=year,
            month=month,
            preference_type=old_preference_type,
        )
        # Затем добавляем новое
        final_time = time_value if time_value and time_value.strip() else None
        upsert_monthly_preference(
            employee_name=employee_name,
            year=year,
            month=month,
            preference_type=preference_type,
            time_value=final_time,
            note=note,
        )
        request.session["flash_success"] = "Пожелание обновлено"
    except Exception as e:
        logger.error("Failed to update preference: %s", e, exc_info=True)
        request.session["flash_error"] = "Не удалось обновить пожелание. Попробуйте ещё раз."

    return RedirectResponse(f"/my-schedule?employee_name={employee_name}&year={year}&month={month}", status_code=303)


@app.post("/my-schedule/monthly/delete", response_class=HTMLResponse)
async def delete_monthly_pref_endpoint(
    request: Request,
    employee_name: str = Form(...),
    preference_type: str = Form(...),
    return_month: int = None,
    return_year: int = None,
):
    """Удаляет месячное пожелание."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    year, month = get_period_from_session_or_default(request, return_year, return_month)

    try:
        delete_monthly_preference(
            employee_name=employee_name,
            year=year,
            month=month,
            preference_type=preference_type,
        )
    except Exception as e:
        logger.error("Failed to delete monthly preference: %s", e, exc_info=True)
        request.session["flash_error"] = "Ошибка удаления. Попробуйте ещё раз."

    response = RedirectResponse(f"/my-schedule?employee_name={employee_name}&year={year}&month={month}", status_code=303)
    response.set_cookie('ekc_year', str(year), max_age=365*24*60*60)
    response.set_cookie('ekc_month', str(month), max_age=365*24*60*60)
    return response


# =============================================================================
# MY SCHEDULE - Unified constraint management (Calendar view)
# =============================================================================

@app.post("/my-schedule/constraint/add", response_class=HTMLResponse)
async def add_constraint(
    request: Request,
    employee_name: str = Form(...),
    date: str = Form(...),
    start_time: str = Form(""),
    end_time: str = Form(""),
    note: str = Form(""),
    constraint_type: str = Form("study"),
    preference_type: str = Form(""),
    return_month: int = None,
    return_year: int = None,
):
    """Добавляет ограничение (учёба или пожелание) из календаря."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    from .parsers import parse_date

    current_user = get_current_user(request)
    if request.session.get("user_role") != "admin" and employee_name != current_user:
        return RedirectResponse(f"/my-schedule?employee_name={current_user}", status_code=303)

    year, month = resolve_period(return_year, return_month)

    try:
        parsed_date = parse_date(date, "date")

        # Check if this is a study constraint or a preference
        is_study = constraint_type == "study"
        has_time = start_time and start_time.strip() and end_time and end_time.strip()
        is_preference = preference_type and preference_type.strip()

        if is_study or (not is_preference and has_time):
            # Учёба
            upsert_study_constraint(
                employee_name=employee_name,
                date_value=parsed_date,
                start_time=start_time,
                end_time=end_time,
                note=note,
                is_strict=True,
            )
        elif is_preference:
            # Пожелание (including full-day with empty time)
            upsert_schedule_preference(
                employee_name=employee_name,
                date_value=parsed_date,
                preference_type=preference_type,
                note=note,
                start_time=start_time if has_time else None,
                end_time=end_time if has_time else None,
            )
    except Exception as e:
        logger.error("Failed to add constraint: %s", e, exc_info=True)
        request.session["flash_error"] = "Не удалось добавить ограничение. Попробуйте ещё раз."

    return RedirectResponse(f"/my-schedule?employee_name={employee_name}&year={year}&month={month}", status_code=303)


@app.post("/my-schedule/constraint/delete", response_class=HTMLResponse)
async def delete_constraint(
    request: Request,
    employee_name: str = Form(...),
    date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    return_month: int = None,
    return_year: int = None,
):
    """Удаляет ограничение по учёбе."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    from .parsers import parse_date

    current_user = get_current_user(request)
    if request.session.get("user_role") != "admin" and employee_name != current_user:
        return RedirectResponse(f"/my-schedule?employee_name={current_user}", status_code=303)

    year, month = resolve_period(return_year, return_month)

    try:
        parsed_date = parse_date(date, "date")
        delete_study_constraint(
            employee_name=employee_name,
            date_value=parsed_date,
            start_time=start_time,
            end_time=end_time,
        )
    except Exception as e:
        logger.error("Failed to delete constraint: %s", e, exc_info=True)
        request.session["flash_error"] = "Не удалось удалить ограничение. Попробуйте ещё раз."

    return RedirectResponse(f"/my-schedule?employee_name={employee_name}&year={year}&month={month}", status_code=303)


@app.post("/my-schedule/constraint/edit", response_class=HTMLResponse)
async def edit_constraint(
    request: Request,
    employee_name: str = Form(...),
    date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    note: str = Form(""),
    old_date: str = Form(...),
    old_start_time: str = Form(...),
    old_end_time: str = Form(...),
    return_month: int = None,
    return_year: int = None,
):
    """Редактирует ограничение по учёбе."""
    from .parsers import parse_date

    current_user = get_current_user(request)
    user_role = request.session.get("user_role")

    # Проверка прав доступа: сотрудники могут редактировать только свои данные
    if user_role != "admin" and employee_name != current_user:
        return RedirectResponse("/my-schedule", status_code=303)

    year, month = resolve_period(return_year, return_month)

    try:
        # Сначала удаляем старую запись
        parsed_old_date = parse_date(old_date, "date")
        delete_study_constraint(
            employee_name=employee_name,
            date_value=parsed_old_date,
            start_time=old_start_time,
            end_time=old_end_time,
        )
        # Добавляем новую запись
        parsed_date = parse_date(date, "date")
        upsert_study_constraint(
            employee_name=employee_name,
            date_value=parsed_date,
            start_time=start_time,
            end_time=end_time,
            note=note,
        )
    except Exception as e:
        logger.error("Failed to edit study constraint: %s", e, exc_info=True)
        request.session["flash_error"] = "Ошибка редактирования. Попробуйте ещё раз."

    return RedirectResponse(f"/my-schedule?employee_name={employee_name}&year={year}&month={month}", status_code=303)


@app.post("/my-schedule/preferences/edit", response_class=HTMLResponse)
async def edit_preference(
    request: Request,
    employee_name: str = Form(...),
    date: str = Form(...),
    preference_type: str = Form(...),
    start_time: str = Form(""),
    end_time: str = Form(""),
    note: str = Form(""),
    old_date: str = Form(...),
    old_preference_type: str = Form(...),
    return_month: int = None,
    return_year: int = None,
):
    """Редактирует пожелание сотрудника."""
    from .parsers import parse_date

    current_user = get_current_user(request)
    user_role = request.session.get("user_role")

    # Проверка прав доступа: сотрудники могут редактировать только свои данные
    if user_role != "admin" and employee_name != current_user:
        return RedirectResponse("/my-schedule", status_code=303)

    year, month = resolve_period(return_year, return_month)

    try:
        # Сначала удаляем старую запись
        parsed_old_date = parse_date(old_date, "date")
        delete_schedule_preference(
            employee_name=employee_name,
            date_value=parsed_old_date,
            preference_type=old_preference_type,
        )
        # Добавляем новую запись
        parsed_date = parse_date(date, "date")
        upsert_schedule_preference(
            employee_name=employee_name,
            date_value=parsed_date,
            preference_type=preference_type,
            note=note,
            start_time=start_time if start_time and start_time.strip() else None,
            end_time=end_time if end_time and end_time.strip() else None,
        )
    except Exception as e:
        logger.error("Failed to edit preference: %s", e, exc_info=True)
        request.session["flash_error"] = "Ошибка редактирования. Попробуйте ещё раз."

    return RedirectResponse(f"/my-schedule?employee_name={employee_name}&year={year}&month={month}", status_code=303)


# =============================================================================
# AUTHENTICATION - Login/Logout/Change Password
# =============================================================================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    """Страница входа в систему."""
    # Если уже авторизован, перенаправляем на главную
    if request.session.get("logged_in_user"):
        return RedirectResponse("/", status_code=303)

    operators = list_operator_profiles()
    employees_data = [
        {"name": emp.name}
        for emp in operators
    ]

    context = {
        "request": request,
        "employees": employees_data,
        "error": None,
        "active_page": "login",
    }
    return templates.TemplateResponse("login.html", context)


@app.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    employee_name: str = Form(...),
    password: str = Form(...),
) -> HTMLResponse:
    """Обработка входа в систему."""
    client_ip = request.client.host if request.client else "unknown"
    if not login_rate_limiter.is_allowed(client_ip):
        context = {
            "request": request,
            "employees": [],
            "error": "Слишком много попыток входа. Попробуйте через минуту.",
            "active_page": "login",
        }
        return templates.TemplateResponse("login.html", context)

    success, message = await process_login(request, employee_name, password)

    if success:
        response = RedirectResponse("/", status_code=303)
        return response

    # Ошибка входа - показываем форму снова
    operators = list_operator_profiles()
    employees_data = [
        {"name": emp.name}
        for emp in operators
    ]

    context = {
        "request": request,
        "employees": employees_data,
        "error": message,
        "active_page": "login",
    }
    return templates.TemplateResponse("login.html", context)


@app.get("/logout", response_class=HTMLResponse)
async def logout(request: Request) -> HTMLResponse:
    """Выход из системы."""
    process_logout(request)
    return RedirectResponse("/login", status_code=303)


@app.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request) -> HTMLResponse:
    """Страница смены пароля."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    current_user = get_current_user(request)

    context = {
        "request": request,
        "current_user": current_user,
        "error": None,
        "success": None,
        "active_page": "change-password",
    }
    return templates.TemplateResponse("change_password.html", context)


@app.post("/change-password", response_class=HTMLResponse)
async def change_password_submit(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
) -> HTMLResponse:
    """Обработка смены пароля."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    # Проверка совпадения паролей
    if new_password != confirm_password:
        current_user = get_current_user(request)
        context = {
            "request": request,
            "current_user": current_user,
            "error": "Новые пароли не совпадают",
            "success": None,
            "active_page": "change-password",
        }
        return templates.TemplateResponse("change_password.html", context)

    success, message = await change_user_password(request, current_password, new_password)

    current_user = get_current_user(request)
    context = {
        "request": request,
        "current_user": current_user,
        "error": None if success else message,
        "success": message if success else None,
        "active_page": "change-password",
    }
    return templates.TemplateResponse("change_password.html", context)


# =============================================================================
# ADMIN - User Management
# =============================================================================

@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request) -> HTMLResponse:
    """Страница управления пользователями (только для админов)."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    if request.session.get("user_role") != "admin":
        return RedirectResponse("/", status_code=303)

    users = list_all_users_with_passwords()
    operators = list_operator_profiles()

    # Сопоставляем пользователей с операторами
    employees_list = [emp.name for emp in operators]

    context = {
        "request": request,
        "users": users,
        "employees_list": employees_list,
        "active_page": "admin-users",
        "errors": [],
        "notices": [],
    }
    return templates.TemplateResponse("admin_users.html", context)


@app.post("/admin/users/promote", response_class=HTMLResponse)
async def admin_promote_user(request: Request, employee_name: str = Form(...)) -> HTMLResponse:
    """Повышает пользователя до админа."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    if request.session.get("user_role") != "admin":
        return RedirectResponse("/", status_code=303)

    # Нельзя понизить самого себя
    if employee_name == request.session.get("logged_in_user"):
        return RedirectResponse("/admin/users", status_code=303)

    update_user_role(employee_name, "admin")
    return RedirectResponse("/admin/users", status_code=303)


@app.post("/admin/users/demote", response_class=HTMLResponse)
async def admin_demote_user(request: Request, employee_name: str = Form(...)) -> HTMLResponse:
    """Понижает админа до сотрудника."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    if request.session.get("user_role") != "admin":
        return RedirectResponse("/", status_code=303)

    # Нельзя понизить самого себя
    if employee_name == request.session.get("logged_in_user"):
        return RedirectResponse("/admin/users", status_code=303)

    update_user_role(employee_name, "employee")
    return RedirectResponse("/admin/users", status_code=303)


@app.post("/admin/users/create", response_class=HTMLResponse)
async def admin_create_user(
    request: Request,
    employee_name: str = Form(...),
    password: str = Form(...),
    role: str = Form("employee"),
) -> HTMLResponse:
    """Создает нового пользователя."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    if request.session.get("user_role") != "admin":
        return RedirectResponse("/", status_code=303)

    success = create_user_with_password(employee_name, password, role)

    if not success:
        # Пользователь уже существует
        return RedirectResponse("/admin/users?error=exists", status_code=303)

    return RedirectResponse("/admin/users", status_code=303)


@app.post("/admin/users/delete", response_class=HTMLResponse)
async def admin_delete_user(request: Request, employee_name: str = Form(...)) -> HTMLResponse:
    """Удаляет пользователя."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    if request.session.get("user_role") != "admin":
        return RedirectResponse("/", status_code=303)

    # Нельзя удалить самого себя
    if employee_name == request.session.get("logged_in_user"):
        return RedirectResponse("/admin/users", status_code=303)

    delete_user_credentials(employee_name)
    return RedirectResponse("/admin/users", status_code=303)


@app.post("/admin/users/reset-password", response_class=HTMLResponse)
async def admin_reset_password(
    request: Request,
    employee_name: str = Form(...),
    new_password: str = Form(...),
) -> HTMLResponse:
    """Сбрасывает пароль пользователя (админ)."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    if request.session.get("user_role") != "admin":
        return RedirectResponse("/", status_code=303)

    update_user_password(employee_name, new_password)

    return RedirectResponse("/admin/users", status_code=303)


# =============================================================================
# CHANGE PERIOD - Глобальное изменение периода
# =============================================================================

@app.post("/change-period", response_class=HTMLResponse)
async def change_period(
    request: Request,
    year: int = Form(...),
    month: int = Form(...),
    redirect: str = Form("/"),
):
    """Глобально изменяет период для всех страниц."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    request.session['selected_year'] = year
    request.session['selected_month'] = month
    
    response = RedirectResponse(redirect, status_code=303)
    response.set_cookie('ekc_year', str(year), max_age=365*24*60*60)
    response.set_cookie('ekc_month', str(month), max_age=365*24*60*60)
    
    return response


# =============================================================================
# EMPLOYEE HOUR ADJUSTMENTS - Корректировка нормы часов (по месяцам)
# =============================================================================

@app.post("/employees/adjust-hours", response_class=HTMLResponse)
async def adjust_employee_hours(
    request: Request,
    employee_name: str = Form(...),
    delta: float = Form(...),
    return_year: int = None,
    return_month: int = None,
):
    """Корректирует норму часов сотрудника для текущего месяца (только для админов). Сохраняет в БД."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)
    if request.session.get("user_role") != "admin":
        return RedirectResponse("/my-schedule", status_code=303)

    from .database import get_employee_month_adjustment, update_employee_month_adjustment

    year, month = get_period_from_session_or_default(request, return_year, return_month)

    # Получаем текущую корректировку для этого месяца
    current_adjustment = get_employee_month_adjustment(employee_name, year, month)
    new_adjustment = round(current_adjustment + delta, 1)

    # Сохраняем в БД
    update_employee_month_adjustment(employee_name, year, month, new_adjustment)

    response = RedirectResponse("/employees", status_code=303)
    response.set_cookie('ekc_year', str(year), max_age=365*24*60*60)
    response.set_cookie('ekc_month', str(month), max_age=365*24*60*60)
    return response


@app.post("/employees/update", response_class=HTMLResponse)
async def update_employee(
    request: Request,
    name: str = Form(...),
    employee_id: str = Form(...),
    rate: float = Form(...),
    employee_type: str = Form(...),
    original_name: str = Form(...),
    return_year: int = None,
    return_month: int = None,
):
    """Обновляет данные сотрудника (только для админов)."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)
    if request.session.get("user_role") != "admin":
        return RedirectResponse("/my-schedule", status_code=303)

    from .database import normalize_rate, normalize_employee_type, slugify_name, daily_hours_for_rate, list_holiday_entries, get_vacation_days_in_month

    year, month = get_period_from_session_or_default(request, return_year, return_month)

    # Рассчитываем норму часов с учётом выходных, overrides и отпусков
    holidays = list_holiday_entries()
    holiday_dates = {h.holiday_date for h in holidays if h.holiday_date.year == year and h.holiday_date.month == month}
    cal_ovrs = list_calendar_day_overrides()
    overrides_map = {}
    for o in cal_ovrs:
        if o.calendar_date.year == year and o.calendar_date.month == month:
            overrides_map[o.calendar_date] = o.is_non_working

    total_days = calendar.monthrange(year, month)[1]
    monthly_working_days = 0
    for day in range(1, total_days + 1):
        d = date(year, month, day)
        if d in overrides_map:
            if overrides_map[d]:
                continue
            else:
                monthly_working_days += 1
        elif d.weekday() >= 5 or d in holiday_dates:
            continue
        else:
            monthly_working_days += 1

    normalized_rate = normalize_rate(rate)
    # Считаем дни отпуска
    vacation_days = get_vacation_days_in_month(name, year, month)
    norm_hours = normalized_rate * 8 * (monthly_working_days - vacation_days)

    profile = OperatorProfile(
        name=name,
        employee_id=employee_id,
        rate=normalized_rate,
        employee_type=employee_type,
        norm_hours=norm_hours,
        max_hours=norm_hours * 1.2,
        max_consecutive_days=7,
        is_active=True,
    )

    upsert_operator_profile(profile, original_name=original_name if original_name else None)

    response = RedirectResponse("/employees", status_code=303)
    response.set_cookie('ekc_year', str(year), max_age=365*24*60*60)
    response.set_cookie('ekc_month', str(month), max_age=365*24*60*60)
    return response


@app.post("/employees/reset-adjustments", response_class=HTMLResponse)
async def reset_employee_adjustments(
    request: Request,
    employee_name: str = Form(...),
    return_year: int = None,
    return_month: int = None,
):
    """Сбрасывает корректировку нормы часов сотрудника для текущего месяца (только для админов). Сохраняет в БД."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)
    if request.session.get("user_role") != "admin":
        return RedirectResponse("/my-schedule", status_code=303)

    from .database import reset_employee_month_adjustment

    year, month = get_period_from_session_or_default(request, return_year, return_month)

    # Сбрасываем в БД
    reset_employee_month_adjustment(employee_name, year, month)

    response = RedirectResponse("/employees", status_code=303)
    response.set_cookie('ekc_year', str(year), max_age=365*24*60*60)
    response.set_cookie('ekc_month', str(month), max_age=365*24*60*60)
    return response


@app.post("/employees/deactivate", response_class=HTMLResponse)
async def deactivate_employee(
    request: Request,
    employee_name: str = Form(...),
):
    """Деактивирует сотрудника (только для админов)."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)
    if request.session.get("user_role") != "admin":
        return RedirectResponse("/my-schedule", status_code=303)

    from .database import deactivate_operator

    deactivate_operator(employee_name)

    request.session["flash_success"] = f"Сотрудник «{employee_name}» деактивирован"
    return RedirectResponse("/employees", status_code=303)


# =============================================================================
# VACATIONS - Отпуска
# =============================================================================

@app.post("/vacations/save", response_class=HTMLResponse)
async def save_vacation(
    request: Request,
    vacation_employee_name: str = Form(...),
    vacation_start_date: str = Form(...),
    vacation_end_date: str = Form(...),
    vacation_note: str = Form(""),
    vacation_id: int = Form(0),
    return_year: int = None,
    return_month: int = None,
):
    """Сохраняет отпуск сотрудника (для админа и сотрудника)."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    from .database import upsert_vacation_entry
    from .models import VacationEntry
    from .parsers import parse_date

    year, month = get_period_from_session_or_default(request, return_year, return_month)

    # Проверяем права: админ может добавлять любому, сотрудник - только себе
    if request.session.get("user_role") != "admin":
        # Сотрудник может добавлять отпуск только себе
        current_user = get_current_user(request)
        if vacation_employee_name != current_user:
            return RedirectResponse("/my-vacations", status_code=303)
        redirect_page = "/my-vacations"
    else:
        redirect_page = "/vacations"

    try:
        start_date = parse_date(vacation_start_date, "vacation_start_date")
        end_date = parse_date(vacation_end_date, "vacation_end_date")

        if end_date < start_date:
            raise ValueError("Дата окончания не может быть раньше даты начала")

        upsert_vacation_entry(
            VacationEntry(
                employee_name=vacation_employee_name,
                start_date=start_date,
                end_date=end_date,
                note=vacation_note,
                id=vacation_id,
            )
        )
    except Exception as e:
        logger.error("Failed to add vacation: %s", e, exc_info=True)
        request.session["flash_error"] = "Не удалось добавить отпуск. Попробуйте ещё раз."

    response = RedirectResponse(redirect_page, status_code=303)
    response.set_cookie('ekc_year', str(year), max_age=365*24*60*60)
    response.set_cookie('ekc_month', str(month), max_age=365*24*60*60)
    return response


@app.post("/vacations/delete", response_class=HTMLResponse)
async def delete_vacation(
    request: Request,
    vacation_id: int = Form(...),
    return_year: int = None,
    return_month: int = None,
):
    """Удаляет отпуск (для админа и сотрудника)."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    from .database import delete_vacation_entry, list_vacation_entries

    year, month = get_period_from_session_or_default(request, return_year, return_month)

    # Определяем права и redirect страницу
    if request.session.get("user_role") != "admin":
        # Сотрудник может удалять только свои отпуска
        current_user = get_current_user(request)
        vacation = None
        for v in list_vacation_entries():
            if v.id == vacation_id and v.employee_name == current_user:
                vacation = v
                break
        if not vacation:
            return RedirectResponse("/my-vacations", status_code=303)
        redirect_page = "/my-vacations"
    else:
        redirect_page = "/vacations"

    try:
        delete_vacation_entry(vacation_id)
    except Exception as e:
        logger.error("Failed to delete vacation: %s", e, exc_info=True)
        request.session["flash_error"] = "Не удалось удалить отпуск. Попробуйте ещё раз."

    response = RedirectResponse(redirect_page, status_code=303)
    response.set_cookie('ekc_year', str(year), max_age=365*24*60*60)
    response.set_cookie('ekc_month', str(month), max_age=365*24*60*60)
    return response


@app.get("/vacations", response_class=HTMLResponse)
async def vacations_page(request: Request):
    """Страница отпусков для администратора - все отпуска."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)
    if request.session.get("user_role") != "admin":
        return RedirectResponse("/login", status_code=303)

    year, month = get_period_from_session_or_default(request)
    month_label = f"{'Январь Февраль Март Апрель Май Июнь Июль Август Сентябрь Октябрь Ноябрь Декабрь'.split()[month-1]} {year}"

    # Загружаем все отпуска
    vacation_entries = list_vacation_entries()
    # Сортируем по имени сотрудника
    vacation_entries.sort(key=lambda v: v.employee_name.lower())

    # Загружаем сотрудников для фильтра (по алфавиту)
    operator_profiles = list_operator_profiles()
    employees_list = sorted([emp.name for emp in operator_profiles], key=lambda n: n.lower())

    context = {
        "request": request,
        "year": year,
        "month": month,
        "month_label": month_label,
        "vacation_entries": vacation_entries,
        "employees_list": employees_list,
        "active_page": "vacations",
        "errors": [],
        "notices": [],
    }
    return templates.TemplateResponse("vacations.html", context)
    return templates.TemplateResponse("vacations.html", context)


@app.get("/my-vacations", response_class=HTMLResponse)
async def my_vacations_page(request: Request):
    """Страница отпусков для сотрудника - только свои отпуска."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)

    current_user = get_current_user(request)
    year, month = get_period_from_session_or_default(request)
    month_label = f"{'Январь Февраль Март Апрель Май Июнь Июль Август Сентябрь Октябрь Ноябрь Декабрь'.split()[month-1]} {year}"

    # Загружаем только отпуска текущего сотрудника
    all_vacations = list_vacation_entries()
    vacation_entries = [v for v in all_vacations if v.employee_name == current_user]

    context = {
        "request": request,
        "year": year,
        "month": month,
        "month_label": month_label,
        "vacation_entries": vacation_entries,
        "current_user": current_user,
        "active_page": "my-vacations",
        "errors": [],
        "notices": [],
    }
    return templates.TemplateResponse("vacations.html", context)


# =============================================================================
# SCHEDULE EDITOR API - Сохранение/удаление смен
# =============================================================================

@app.post("/schedule/editor/save", response_class=HTMLResponse)
async def save_schedule_shift(
    request: Request,
    shift_id: str = Form(""),
    date: str = Form(...),
    employee_name: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    shift_type: str = Form("operator"),
    note: str = Form(""),
):
    """Сохраняет смену в базу данных (только для админов)."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)
    if request.session.get("user_role") != "admin":
        return RedirectResponse("/my-schedule", status_code=303)

    from .database import upsert_schedule_assignment
    from .parsers import parse_date

    try:
        parsed_date = parse_date(date, "date")
        upsert_schedule_assignment(
            employee_name=employee_name,
            date_value=parsed_date,
            start_time=start_time,
            end_time=end_time,
            shift_type=shift_type,
            note=note,
        )
    except Exception as e:
        logger.error("Failed to save schedule shift: %s", e, exc_info=True)
        request.session["flash_error"] = "Не удалось сохранить смену. Попробуйте ещё раз."

    # Сохраняем период в session
    year, month = get_period_from_session_or_default(request, None, None)
    # Определяем, откуда пришел запрос
    referer = request.headers.get("referer", "")
    redirect_path = "/schedule/editor"
    response = RedirectResponse(redirect_path, status_code=303)
    response.set_cookie('ekc_year', str(year), max_age=365*24*60*60)
    response.set_cookie('ekc_month', str(month), max_age=365*24*60*60)
    return response


@app.post("/schedule/editor/delete", response_class=HTMLResponse)
async def delete_schedule_shift(
    request: Request,
    shift_id: str = Form(...),
):
    """Удаляет смену из базы данных (только для админов)."""
    if not request.session.get("logged_in_user"):
        return RedirectResponse("/login", status_code=303)
    if request.session.get("user_role") != "admin":
        return RedirectResponse("/my-schedule", status_code=303)

    from .database import list_schedule_assignments, delete_schedule_assignment

    try:
        # Находим смену по ID
        year, month = get_period_from_session_or_default(request, None, None)
        all_shifts = list_schedule_assignments(year, month)
        shift = next((s for s in all_shifts if s['id'] == int(shift_id)), None)

        if shift:
            delete_schedule_assignment(
                shift['employee_name'],
                shift['date'],
                shift['start_time'],
                shift['end_time'],
            )
    except Exception as e:
        logger.error("Failed to delete schedule shift: %s", e, exc_info=True)
        request.session["flash_error"] = "Не удалось удалить смену. Попробуйте ещё раз."

    year, month = get_period_from_session_or_default(request, None, None)
    referer = request.headers.get("referer", "")
    redirect_path = "/schedule/editor"
    response = RedirectResponse(redirect_path, status_code=303)
    response.set_cookie('ekc_year', str(year), max_age=365*24*60*60)
    response.set_cookie('ekc_month', str(month), max_age=365*24*60*60)
    return response


@app.get("/schedule/editor/data", response_class=HTMLResponse)
async def schedule_editor_data(
    request: Request,
    year: int = None,
    month: int = None,
):
    """Возвращает данные смен в формате JSON для обновления редактора."""
    if not request.session.get("logged_in_user"):
        return Response(status_code=403)
    if request.session.get("user_role") != "admin":
        return Response(status_code=403)

    year, month = get_period_from_session_or_default(request, year, month)

    from .database import (
        list_schedule_assignments, list_operator_profiles, list_holiday_entries,
        list_vacation_entries, list_study_constraints,
        list_schedule_preferences, list_monthly_preferences,
        get_employee_month_adjustments_batch,
    )
    from .employee_hydration import _get_vacation_days_for_employee
    from .models import monthly_norm_hours, working_days_in_month
    from fastapi.responses import JSONResponse
    import calendar

    assignments = list_schedule_assignments(year, month)
    operators = list_operator_profiles()

    # Загружаем ограничения, пожелания и отпуска
    study_constraints = list_study_constraints(year, month)
    schedule_preferences = list_schedule_preferences(year, month)
    monthly_prefs = list_monthly_preferences(year, month)
    vacation_entries = list_vacation_entries()

    # Рассчитываем нормы часов для каждого сотрудника с учетом отпусков и корректировок
    holiday_entries = list_holiday_entries()
    holiday_date_objects = {h.holiday_date for h in holiday_entries if h.holiday_date.year == year and h.holiday_date.month == month}
    adjustments_batch = get_employee_month_adjustments_batch(year, month)
    employee_target_hours = {}
    for emp in operators:
        vacation_days = _get_vacation_days_for_employee(emp.name, year, month, vacation_entries)
        base_norm = monthly_norm_hours(emp.rate, year, month, holiday_date_objects, vacation_days)
        # Добавляем корректировку из БД для текущего месяца
        month_adjustment = adjustments_batch.get(emp.name, 0.0)
        max_hours = base_norm + month_adjustment
        employee_target_hours[emp.name] = round(max_hours, 1)

    # Конвертируем даты в строки
    result = {
        "assignments": [
            {
                "id": a["id"],
                "employee_name": a["employee_name"],
                "date": a["date"].isoformat() if isinstance(a["date"], date) else a["date"],
                "start_time": a["start_time"],
                "end_time": a["end_time"],
                "shift_type": a["shift_type"],
            }
            for a in assignments
        ],
        "employee_target_hours": employee_target_hours,
        # Добавляем ограничения по учёбе
        "study_constraints": [
            {
                "id": c["id"],
                "employee_name": c["employee_name"],
                "date": c["date"].isoformat() if isinstance(c["date"], date) else c["date"],
                "start_time": c["start_time"],
                "end_time": c["end_time"],
                "note": c["note"],
                "is_strict": c["is_strict"],
            }
            for c in study_constraints
        ],
        # Добавляем пожелания
        "schedule_preferences": [
            {
                "id": p["id"],
                "employee_name": p["employee_name"],
                "date": p["date"].isoformat() if isinstance(p["date"], date) else p["date"],
                "preference_type": p["preference_type"],
                "start_time": p["start_time"],
                "end_time": p["end_time"],
                "note": p["note"],
            }
            for p in schedule_preferences
        ],
        # Добавляем месячные пожелания
        "monthly_preferences": [
            {
                "id": mp["id"],
                "employee_name": mp["employee_name"],
                "year": mp["year"],
                "month": mp["month"],
                "preference_type": mp["preference_type"],
                "time_value": mp["time_value"],
                "note": mp["note"],
            }
            for mp in monthly_prefs
        ],
        # Добавляем отпуска
        "vacations": [
            {
                "id": v.id,
                "employee_name": v.employee_name,
                "start_date": v.start_date.isoformat() if isinstance(v.start_date, date) else v.start_date,
                "end_date": v.end_date.isoformat() if isinstance(v.end_date, date) else v.end_date,
                "note": v.note,
            }
            for v in vacation_entries
        ],
    }

    return JSONResponse(result)


@app.get("/schedule/editor/availability/hourly", response_class=JSONResponse)
async def get_hourly_availability(
    request: Request,
    date: str,
    employees: str = None,
):
    """Возвращает почасовую доступность сотрудников на указанную дату."""
    if not request.session.get("logged_in_user"):
        return JSONResponse({"error": "Unauthorized"}, status_code=403)
    if request.session.get("user_role") != "admin":
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    from .database import get_hourly_availability

    employee_list = None
    if employees:
        employee_list = [e.strip() for e in employees.split(",") if e.strip()]

    try:
        result = get_hourly_availability(date, employee_list)
        return JSONResponse(result)
    except Exception as e:
        logger.error("Error in get_hourly_availability: %s", e, exc_info=True)
        return JSONResponse({"error": "Произошла ошибка. Попробуйте ещё раз."}, status_code=500)

